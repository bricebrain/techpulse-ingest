"""Fetch articles from the Cloudflare Worker API and insert into Neon.

This replaces the Worker-side Neon sync (which hit the 50-subrequest limit).
GitHub Actions has no such limits, so we fetch from Worker API → write to Neon.
"""

import hashlib
import logging
import os

import httpx

from . import db
from .text_cleaning import clean_text, parse_engagement

log = logging.getLogger(__name__)

WORKER_URL = os.environ.get("WORKER_URL", "https://techpulse-worker.bricebrain.workers.dev")
WORKER_SECRET = os.environ.get("WORKER_SECRET", "")


def fetch_articles_from_worker(hours: int = 12, limit: int = 200) -> list[dict]:
    """Fetch recent articles from the Worker API."""
    articles = []

    # Fetch recent cross-theme articles
    try:
        resp = httpx.get(
            f"{WORKER_URL}/articles/recent",
            params={"limit": limit, "hours": hours},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            articles.extend(data)
        elif isinstance(data, dict) and "articles" in data:
            articles.extend(data["articles"])
    except Exception as e:
        log.error("Failed to fetch recent articles: %s", e)

    # Also fetch by theme to get more coverage
    themes = ["general", "business", "ai", "finance", "science"]
    for theme in themes:
        try:
            resp = httpx.get(
                f"{WORKER_URL}/articles",
                params={"theme": theme, "limit": 60},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                articles.extend(data)
            elif isinstance(data, dict) and "articles" in data:
                articles.extend(data["articles"])
        except Exception as e:
            log.warning("Failed to fetch theme %s: %s", theme, e)

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for a in articles:
        url = a.get("url") or ""
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(a)

    log.info("Fetched %d unique articles from Worker API", len(unique))
    return unique


def map_source_type(theme: str) -> str:
    """Map Worker themes to our source_type."""
    mapping = {
        "general": "rss",
        "business": "rss",
        "finance": "rss",
        "ai": "rss",
        "science": "rss",
        "youtube": "youtube",
    }
    return mapping.get(theme, "rss")


def sync_to_neon(articles: list[dict]) -> int:
    """Insert Worker articles into Neon, skipping duplicates."""
    if not articles:
        return 0

    inserted = 0
    with db.get_cursor() as cur:
        for article in articles:
            url = article.get("url")
            if not url:
                continue

            # Check if already in Neon
            cur.execute("SELECT id FROM articles WHERE url = %s", (url,))
            if cur.fetchone():
                continue

            article_id = db.gen_id()
            title = clean_text(article.get("title", ""))
            source_name = article.get("source_name", "unknown")
            theme = article.get("theme", "general")
            content = clean_text(article.get("content", ""))
            external_score, comments_count = parse_engagement(article.get("content", ""))
            published_at = article.get("published_at")

            # Convert epoch ms to timestamp if needed
            pub_ts = None
            if published_at and isinstance(published_at, (int, float)):
                from datetime import datetime, timezone
                pub_ts = datetime.fromtimestamp(published_at / 1000, tz=timezone.utc)
            elif published_at and isinstance(published_at, str):
                pub_ts = published_at

            cur.execute(
                """
                INSERT INTO articles (id, title, url, source_name, source_type,
                                      description, published_at, fetched_at,
                                      external_score, comments_count, status,
                                      pipeline_status, extraction_status,
                                      embedding_status, clustering_status,
                                      analysis_status, retry_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, 'new',
                        'discovered', 'pending', 'pending', 'pending', 'pending', 0)
                ON CONFLICT (url) DO NOTHING
                """,
                (
                    article_id,
                    title[:500],
                    url,
                    source_name,
                    map_source_type(theme),
                    (content or "")[:500],
                    pub_ts,
                    external_score,
                    comments_count,
                ),
            )
            inserted += 1

    log.info("Inserted %d new articles into Neon", inserted)
    return inserted


def run_worker_fetch() -> int:
    """Main entry: fetch from Worker API → insert into Neon."""
    articles = fetch_articles_from_worker(hours=12, limit=200)
    return sync_to_neon(articles)
