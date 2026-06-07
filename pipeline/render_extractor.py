"""Remote article extraction through the FastAPI service on Render."""

import logging
import os
import time

import httpx

from .text_cleaning import clean_text

log = logging.getLogger(__name__)


def render_api_base_url() -> str | None:
    value = os.getenv("TECHPULSE_RENDER_API_URL") or os.getenv("FASTAPI_BASE_URL")
    return value.strip().rstrip("/") if value and value.strip() else None


def render_api_secret() -> str | None:
    value = os.getenv("TECHPULSE_RENDER_API_SECRET") or os.getenv("REDDIT_PROXY_SECRET")
    return value.strip() if value and value.strip() else None


def render_timeout() -> float:
    try:
        return float(os.getenv("TECHPULSE_RENDER_EXTRACT_TIMEOUT", "45"))
    except ValueError:
        return 45.0


def render_max_retries() -> int:
    try:
        return max(1, int(os.getenv("TECHPULSE_RENDER_EXTRACT_RETRIES", "2")))
    except ValueError:
        return 2


def extract_article_remote(article: dict) -> dict | None:
    base_url = render_api_base_url()
    if not base_url:
        return None

    headers = {}
    secret = render_api_secret()
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    data = None
    last_error = None
    for attempt in range(1, render_max_retries() + 1):
        try:
            resp = httpx.post(
                f"{base_url}/api/v1/extract/article",
                headers=headers,
                json={
                    "article_id": article["id"],
                    "url": article["url"],
                    "source": article.get("source_name"),
                },
                timeout=render_timeout(),
            )
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as exc:
            last_error = exc
            if attempt < render_max_retries():
                time.sleep(2 * attempt)

    if data is None:
        log.warning("Render extraction request failed for %s: %s", article["url"], last_error)
        return None

    if not data.get("success"):
        log.warning(
            "Render extraction returned no text for %s: %s",
            article["url"],
            data.get("error"),
        )
        return None

    text = clean_text(data.get("text"))
    if len(text) < 80:
        return None

    return {
        "text": text[:15000],
        "authors": data.get("authors") or [],
        "top_image": data.get("image_url"),
        "keywords": [],
        "method": data.get("extraction_method") or "trafilatura_fastapi",
    }
