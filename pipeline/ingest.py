"""Main ingestion pipeline — entry point for GitHub Actions.

Steps:
  0. Fetch articles from Worker API → insert into Neon
  1. Fetch new articles from Neon
  2. Scrape full text (newspaper3k)
  3. Transcribe YouTube videos (yt-dlp + Whisper)
  4. Compute embeddings (bge-small-en)
  5. Store everything back in Neon
  6. Trigger techpulse-intelligence repo (repository_dispatch)
"""

import logging
import os
import sys

import httpx

from . import db
from .worker_fetcher import run_worker_fetch
from .scraper import scrape_batch
from .youtube_transcriber import transcribe_youtube_articles
from .embedder import compute_embeddings
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

    with db.get_cursor() as cur:
        run_id = db.insert_pipeline_run(cur, "ingest")

    stats = {
        "articles_fetched": 0,
        "articles_embedded": 0,
        "clusters_created": 0,
        "clusters_updated": 0,
        "analyses_generated": 0,
    }
    errors = []

    try:
        # ── Step 0: Fetch articles from Worker API → Neon ──
        log.info("Step 0: Fetching articles from Worker API...")
        try:
            fetched = run_worker_fetch()
            stats["articles_fetched"] = fetched
            log.info("Fetched %d articles from Worker API into Neon", fetched)
        except Exception as e:
            log.error("Worker fetch error: %s", e)
            errors.append(f"worker_fetch: {e}")

        # ── Step 1: Fetch new articles from Neon ──
        log.info("Step 1: Fetching new articles from Neon...")
        with db.get_cursor() as cur:
            new_articles = db.fetch_new_articles(cur, limit=200)
        stats["articles_fetched"] = len(new_articles)
        log.info("Found %d new articles to process", len(new_articles))

        if not new_articles:
            log.info("No new articles. Pipeline complete.")
            with db.get_cursor() as cur:
                db.complete_pipeline_run(cur, run_id, stats)
            return

        # ── Step 2: Scrape full text ──
        log.info("Step 2: Scraping full articles...")
        try:
            with db.get_cursor() as cur:
                extraction_rules = db.fetch_source_extraction_rules(cur)

            scraped, skipped_extractions = scrape_batch(new_articles, extraction_rules)
            scraped_ids = {item["id"] for item in scraped}
            skipped_ids = set(skipped_extractions)
            with db.get_cursor() as cur:
                for item in scraped:
                    db.update_article_full_text(
                        cur,
                        item["id"],
                        item["full_text"],
                        item.get("image_url"),
                        item.get("extraction_method", "local_scraper"),
                    )
                for article_id, strategy in skipped_extractions.items():
                    db.mark_article_extraction_skipped(
                        cur,
                        article_id,
                        strategy,
                        f"source_extraction_rule:{strategy}",
                    )
                for article in new_articles:
                    if article["id"] not in scraped_ids and article["id"] not in skipped_ids:
                        db.mark_article_extraction_failed(cur, article["id"], "local_scraper_returned_no_text")
            log.info("Scraped %d articles", len(scraped))
        except Exception as e:
            log.error("Scraping error: %s", e)
            errors.append(f"scraping: {e}")

        # ── Step 3: Transcribe YouTube videos ──
        log.info("Step 3: Transcribing YouTube videos...")
        try:
            transcribed = transcribe_youtube_articles(new_articles, max_videos=8)
            with db.get_cursor() as cur:
                for item in transcribed:
                    db.update_article_full_text(
                        cur,
                        item["id"],
                        item["full_text"],
                        extraction_method="youtube_transcript",
                    )
            log.info("Transcribed %d videos", len(transcribed))
        except Exception as e:
            log.error("Transcription error: %s", e)
            errors.append(f"transcription: {e}")

        # ── Step 4: Compute embeddings ──
        log.info("Step 4: Computing embeddings...")
        try:
            with db.get_cursor() as cur:
                articles_to_embed = db.fetch_unembedded_articles(cur, limit=500)

            embedded = compute_embeddings(articles_to_embed)
            embedded_ids = {item["id"] for item in embedded}
            with db.get_cursor() as cur:
                for item in embedded:
                    db.update_article_embedding(cur, item["id"], item["embedding"])
                for article in articles_to_embed:
                    if article["id"] not in embedded_ids:
                        db.mark_article_embedding_failed(cur, article["id"], "embedding_model_returned_no_vector")
            stats["articles_embedded"] = len(embedded)
            log.info("Embedded %d articles", len(embedded))
        except Exception as e:
            log.error("Embedding error: %s", e)
            errors.append(f"embedding: {e}")
            with db.get_cursor() as cur:
                for article in articles_to_embed if 'articles_to_embed' in locals() else []:
                    db.mark_article_embedding_failed(cur, article["id"], str(e))

        # ── Step 4b: Rétention / purge (garde Neon sous le free tier) ──
        if retention_enabled():
            try:
                with db.get_cursor() as cur:
                    stats["retention"] = run_retention(cur)
            except Exception as e:
                log.warning("Retention step skipped after error: %s", e, exc_info=True)

        # ── Step 5: Finalize ──
        with db.get_cursor() as cur:
            db.complete_pipeline_run(cur, run_id, stats)

        log.info("=" * 60)
        log.info("Pipeline complete: %s", stats)
        log.info("=" * 60)

        # ── Step 6: Trigger intelligence pipeline ──
        trigger_intelligence_pipeline()

    except Exception as e:
        log.error("Pipeline failed: %s", e)
        errors.append(f"fatal: {e}")
        with db.get_cursor() as cur:
            db.fail_pipeline_run(cur, run_id, errors)
        sys.exit(1)


if __name__ == "__main__":
    run()
