"""Full article scraping using trafilatura with newspaper3k fallback."""

import logging
from newspaper import Article
import trafilatura

from .text_cleaning import clean_text

log = logging.getLogger(__name__)


def scrape_article(url: str) -> dict | None:
    """Extract full text and metadata from an article URL.

    Returns dict with keys: text, authors, top_image, keywords
    or None if extraction fails.
    """
    downloaded = None
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                output_format="txt",
                include_comments=False,
                include_tables=False,
                favor_recall=True,
            )
            text = clean_text(text)
            if len(text) >= 80:
                metadata = trafilatura.extract_metadata(downloaded)
                return {
                    "text": text[:15000],
                    "authors": [],
                    "top_image": getattr(metadata, "image", None) if metadata else None,
                    "keywords": [],
                }
    except Exception as e:
        log.warning("Trafilatura failed for %s: %s", url, e)

    try:
        article = Article(url, language="en")
        if downloaded:
            article.download(input_html=downloaded)
        else:
            article.download()
        article.parse()

        text = clean_text(article.text)
        if not text or len(text) < 50:
            return None

        return {
            "text": text[:15000],
            "authors": article.authors,
            "top_image": article.top_image,
            "keywords": article.keywords,
        }
    except Exception as e:
        log.warning("Failed to scrape %s: %s", url, e)
        return None


def scrape_batch(articles: list[dict]) -> list[dict]:
    """Scrape a batch of articles, returning results with article IDs."""
    results = []
    for article in articles:
        url = article["url"]
        if any(skip in url for skip in ["youtube.com", "youtu.be", "reddit.com"]):
            continue

        data = scrape_article(url)
        if data:
            results.append({
                "id": article["id"],
                "full_text": data["text"],
                "image_url": data["top_image"],
            })
            log.info("Scraped: %s", article["title"][:60])

    log.info("Scraped %d / %d articles", len(results), len(articles))
    return results
