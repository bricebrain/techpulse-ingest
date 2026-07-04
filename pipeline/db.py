"""HTTP client for the techpulse-worker /pipeline/* bridge to D1.

Replaces the old psycopg2/Neon connection: this pipeline never opens a
database connection directly anymore, it calls the Worker over HTTP.
"""

import logging
import os

import httpx

log = logging.getLogger(__name__)

WORKER_URL = os.environ.get(
    "TECHPULSE_WORKER_URL", "https://techpulse-worker.bricebrain.workers.dev"
).rstrip("/")
WORKER_SECRET = os.environ.get("TECHPULSE_WORKER_SECRET", "")


def _headers() -> dict:
    return {"Authorization": f"Bearer {WORKER_SECRET}"}


def fetch_new_articles(hours: int = 72, limit: int = 200) -> list[dict]:
    """Get articles pending full-text scraping/transcription from D1."""
    resp = httpx.get(
        f"{WORKER_URL}/pipeline/articles",
        params={"stage": "fulltext", "hours": hours, "limit": limit},
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("articles", [])


def update_article_full_text(updates: list[dict]) -> int:
    """Push scraped/transcribed content back to D1.

    Each update: {hash, content?, fulltext_status: 'done'|'skipped'|'failed',
                  audio_url?, audio_duration?}
    Sent in batches of 300 (Worker limit).
    """
    if not updates:
        return 0

    total = 0
    for i in range(0, len(updates), 300):
        batch = updates[i : i + 300]
        resp = httpx.post(
            f"{WORKER_URL}/pipeline/articles/fulltext",
            json={"articles": batch},
            headers=_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        total += resp.json().get("updated", 0)
    return total


def insert_pipeline_run(job_type: str = "ingest") -> str:
    resp = httpx.post(
        f"{WORKER_URL}/pipeline/jobs",
        json={"job_type": job_type},
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def complete_pipeline_run(run_id: str, stats: dict):
    import json

    resp = httpx.patch(
        f"{WORKER_URL}/pipeline/jobs/{run_id}",
        json={"status": "success", "stats_json": json.dumps(stats)},
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()


def fail_pipeline_run(run_id: str, errors: list[str]):
    import json

    resp = httpx.patch(
        f"{WORKER_URL}/pipeline/jobs/{run_id}",
        json={"status": "failed", "error": json.dumps(errors)},
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()


def send_logs(logs: list[dict]):
    """Best-effort log shipping. Never raises."""
    if not logs:
        return
    try:
        resp = httpx.post(
            f"{WORKER_URL}/pipeline/logs",
            json={"logs": logs[:100]},
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        log.warning("Failed to send logs to Worker: %s", e)
