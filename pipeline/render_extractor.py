"""Remote article extraction through the FastAPI service on Render."""

import logging
import os

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
        return float(os.getenv("TECHPULSE_RENDER_EXTRACT_TIMEOUT", "20"))
    except ValueError:
        return 20.0


def extract_article_remote(article: dict) -> dict | None:
    base_url = render_api_base_url()
    if not base_url:
        return None

    headers = {}
    secret = render_api_secret()
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

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
    except Exception as exc:
        log.warning("Render extraction request failed for %s: %s", article["url"], exc)
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
