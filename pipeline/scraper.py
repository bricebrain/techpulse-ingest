"""Full article scraping using trafilatura with newspaper3k fallback."""

import logging
from newspaper import Article
import trafilatura

from .render_extractor import extract_article_remote
from .text_cleaning import clean_text

log = logging.getLogger(__name__)

SKIP_SCRAPE_STRATEGIES = {
    "metadata_only",
    "rss_content",
    "manual_parser",
    "youtube_transcript",
}

# Anciennement pilotées par la table Neon `source_extraction_rules`
# (migrations/005_source_extraction_rules.sql). D1 n'a pas cette table —
# ce petit dict en dur suffit pour un seul utilisateur.
SOURCE_EXTRACTION_RULES: dict[str, dict] = {
    "techcrunch": {"strategy": "trafilatura_fastapi", "use_fastapi": True, "use_local_fallback": True},
    "the verge": {"strategy": "trafilatura_fastapi", "use_fastapi": True, "use_local_fallback": True},
    "ars technica": {"strategy": "trafilatura_fastapi", "use_fastapi": True, "use_local_fallback": True},
    "bloomberg": {"strategy": "metadata_only", "use_fastapi": False, "use_local_fallback": True},
    "youtube": {"strategy": "youtube_transcript", "use_fastapi": False, "use_local_fallback": False},
    "reddit": {"strategy": "manual_parser", "use_fastapi": False, "use_local_fallback": False},
    "medium": {"strategy": "trafilatura_fastapi", "use_fastapi": True, "use_local_fallback": True},
}


def source_key(article: dict) -> str:
    return (article.get("source_name") or "").lower().strip()


def extraction_rule(article: dict, rules: dict[str, dict] | None = None) -> dict:
    rules = rules if rules is not None else SOURCE_EXTRACTION_RULES
    return rules.get(source_key(article), {})


def infer_strategy(article: dict, rule: dict) -> str:
    url = article.get("url") or ""
    if any(skip in url for skip in ["youtube.com", "youtu.be"]):
        return "youtube_transcript"
    if "reddit.com" in url:
        return "manual_parser"
    return rule.get("strategy") or "trafilatura_fastapi"


def should_skip_scraping(strategy: str, rule: dict) -> bool:
    if strategy in SKIP_SCRAPE_STRATEGIES:
        return True
    return rule and not rule.get("use_fastapi", True) and not rule.get("use_local_fallback", True)


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


def scrape_batch(
    articles: list[dict],
    extraction_rules: dict[str, dict] | None = None,
) -> tuple[list[dict], dict[str, str]]:
    """Scrape a batch of articles, returning results keyed by article hash."""
    results = []
    skipped = {}
    attempted = 0
    failed_hashes = []
    for article in articles:
        url = article["url"]
        rule = extraction_rule(article, extraction_rules)
        strategy = infer_strategy(article, rule)

        if should_skip_scraping(strategy, rule):
            skipped[article["hash"]] = strategy
            log.info("Extraction skipped by strategy=%s: %s", strategy, article["title"][:60])
            continue

        attempted += 1
        data = extract_article_remote(article) if rule.get("use_fastapi", True) else None
        if data:
            log.info("Extracted via Render: %s", article["title"][:60])
        elif rule.get("use_local_fallback", True):
            data = scrape_article(url)

        if data:
            results.append({
                "hash": article["hash"],
                "full_text": data["text"],
                "extraction_method": data.get("method", "local_scraper"),
            })
            log.info("Scraped: %s", article["title"][:60])
        else:
            failed_hashes.append(article["hash"])

    log.info("Scraped %d / %d attempted articles", len(results), attempted)
    for article_hash in failed_hashes:
        log.warning("Scraping failed for article hash=%s", article_hash)
    return results, skipped
