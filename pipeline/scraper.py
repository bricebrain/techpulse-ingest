"""Full article scraping using newspaper3k."""

import logging
from newspaper import Article

log = logging.getLogger(__name__)


def scrape_article(url: str) -> dict | None:
    """Extract full text and metadata from an article URL.

    Returns dict with keys: text, authors, top_image, keywords
    or None if extraction fails.
    """
    try:
        article = Article(url, language="en")
        article.download()
        article.parse()

        if not article.text or len(article.text) < 50:
            return None

        return {
            "text": article.text[:15000],
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
