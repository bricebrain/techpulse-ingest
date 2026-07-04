"""Main ingestion pipeline — entry point for GitHub Actions.

Steps:
  1. Fetch articles pending full-text (stage=fulltext) from D1 via Worker bridge
  2. Scrape full text (trafilatura/newspaper3k, with Render FastAPI first)
  3. Transcribe YouTube videos (yt-dlp + Whisper)
  3b. Transcribe podcast episodes (Render FastAPI + Deepgram Nova-3)
  4. Push results back to D1 via /pipeline/articles/fulltext
  5. Trigger techpulse-intelligence repo (repository_dispatch) — clustering/analysis
     happens there, not in this pipeline.
"""

import logging
import os
import sys

import httpx

from . import db
from .scraper import scrape_batch
from .youtube_transcriber import transcribe_youtube_articles
from .podcast_transcriber import transcribe_podcast_episodes
from .retention import retention_enabled, run_retention

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest")


def trigger_intelligence_pipeline():
    """Trigger the techpulse-intelligence repo via GitHub repository_dispatch."""
    token = os.environ.get("GITHUB_TRIGGER_TOKEN")
    repo = os.environ.get("INTELLIGENCE_REPO", "")

    if not token or not repo:
        log.warning("GITHUB_TRIGGER_TOKEN or INTELLIGENCE_REPO not set, skipping trigger")
        return

    log.info("Triggering intelligence pipeline: %s", repo)
    resp = httpx.post(
        f"https://api.github.com/repos/{repo}/dispatches",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        json={"event_type": "ingest_complete"},
        timeout=30,
    )
    if resp.status_code == 204:
        log.info("Intelligence pipeline triggered successfully")
    else:
        log.warning("Failed to trigger: %d %s", resp.status_code, resp.text[:200])


def run():
    log.info("=" * 60)
    log.info("TechPulse Ingestion Pipeline — Starting")
    log.info("=" * 60)

    run_id = db.insert_pipeline_run("ingest")

    stats = {
        "articles_fetched": 0,
        "articles_scraped": 0,
        "videos_transcribed": 0,
        "podcasts_transcribed": 0,
    }
    errors = []

    try:
        # ── Step 1: Fetch articles pending full-text from D1 ──
        log.info("Step 1: Fetching articles pending full-text from D1...")
        new_articles = db.fetch_new_articles(hours=72, limit=200)
        stats["articles_fetched"] = len(new_articles)
        log.info("Found %d articles to process", len(new_articles))

        if not new_articles:
            log.info("No new articles. Pipeline complete.")
            db.complete_pipeline_run(run_id, stats)
            return

        updates: list[dict] = []

        # ── Step 2: Scrape full text ──
        log.info("Step 2: Scraping full articles...")
        try:
            scraped, skipped_extractions = scrape_batch(new_articles)
            scraped_hashes = {item["hash"] for item in scraped}
            skipped_hashes = set(skipped_extractions)

            for item in scraped:
                updates.append({
                    "hash": item["hash"],
                    "content": item["full_text"],
                    "fulltext_status": "done",
                })
            for article_hash, strategy in skipped_extractions.items():
                updates.append({
                    "hash": article_hash,
                    "fulltext_status": "skipped",
                })
            for article in new_articles:
                if article["hash"] not in scraped_hashes and article["hash"] not in skipped_hashes:
                    updates.append({
                        "hash": article["hash"],
                        "fulltext_status": "failed",
                    })
            stats["articles_scraped"] = len(scraped)
            log.info("Scraped %d articles", len(scraped))
        except Exception as e:
            log.error("Scraping error: %s", e)
            errors.append(f"scraping: {e}")

        # ── Step 3: Transcribe YouTube videos ──
        log.info("Step 3: Transcribing YouTube videos...")
        try:
            transcribed = transcribe_youtube_articles(new_articles, max_videos=4)
            for item in transcribed:
                updates.append({
                    "hash": item["hash"],
                    "content": item["full_text"],
                    "fulltext_status": "done",
                })
            stats["videos_transcribed"] = len(transcribed)
            log.info("Transcribed %d videos", len(transcribed))
        except Exception as e:
            log.error("Transcription error: %s", e)
            errors.append(f"transcription: {e}")

        # ── Step 3b: Transcribe podcast episodes via Render FastAPI (Deepgram) ──
        log.info("Step 3b: Transcribing podcast episodes...")
        try:
            # Mots-clés de filtrage (anti-coût) — utilisés si définis
            podcast_keywords_str = os.getenv("TECHPULSE_PODCAST_KEYWORDS", "")
            podcast_keywords = [
                k.strip() for k in podcast_keywords_str.split(",") if k.strip()
            ] or None
            max_podcast = int(os.getenv("TECHPULSE_PODCAST_MAX_EPISODES", "8"))

            transcribed_pods = transcribe_podcast_episodes(
                new_articles,
                keywords=podcast_keywords,
                max_episodes=max_podcast,
            )
            for item in transcribed_pods:
                updates.append({
                    "hash": item["hash"],
                    "content": item["full_text"],
                    "fulltext_status": "done",
                })
            stats["podcasts_transcribed"] = len(transcribed_pods)
            log.info("Transcribed %d podcast episodes", len(transcribed_pods))
        except Exception as e:
            log.error("Podcast transcription error: %s", e)
            errors.append(f"podcast_transcription: {e}")

        # ── Step 4: Push results back to D1 ──
        log.info("Step 4: Writing results back to D1 (%d updates)...", len(updates))
        try:
            updated = db.update_article_full_text(updates)
            log.info("Updated %d articles in D1", updated)
        except Exception as e:
            log.error("D1 write-back error: %s", e)
            errors.append(f"d1_writeback: {e}")

        # ── Step 4b: Rétention / purge ──
        if retention_enabled():
            run_retention()

        # ── Step 5: Finalize ──
        # Les erreurs par étape sont best-effort (loggées, pipeline continue) ;
        # seule une exception fatale (bloc except plus bas) marque le job "failed".
        stats["errors"] = errors
        db.complete_pipeline_run(run_id, stats)

        log.info("=" * 60)
        log.info("Pipeline complete: %s", stats)
        log.info("=" * 60)

        # ── Step 6: Trigger intelligence pipeline ──
        trigger_intelligence_pipeline()

    except Exception as e:
        log.error("Pipeline failed: %s", e)
        errors.append(f"fatal: {e}")
        db.fail_pipeline_run(run_id, errors)
        sys.exit(1)


if __name__ == "__main__":
    run()
