import logging
import re

import trafilatura

from app.schemas.extraction import ArticleExtractionRequest, ArticleExtractionResponse

logger = logging.getLogger(__name__)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"\s+", " ", value).strip()
    return text


class ExtractionService:
    min_text_length = 80
    max_text_length = 15000

    def extract_article(self, payload: ArticleExtractionRequest) -> ArticleExtractionResponse:
        url = str(payload.url)
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return ArticleExtractionResponse(
                    success=False,
                    url=url,
                    status_code=None,
                    error="trafilatura_fetch_returned_empty",
                )

            text = trafilatura.extract(
                downloaded,
                output_format="txt",
                include_comments=False,
                include_tables=False,
                favor_recall=True,
            )
            text = clean_text(text)
            if len(text) < self.min_text_length:
                return ArticleExtractionResponse(
                    success=False,
                    url=url,
                    text=text or None,
                    extraction_method="trafilatura",
                    error="trafilatura_returned_short_text",
                )

            metadata = trafilatura.extract_metadata(downloaded)
            title = clean_text(getattr(metadata, "title", None)) or None if metadata else None
            excerpt = clean_text(getattr(metadata, "description", None)) or None if metadata else None
            image_url = getattr(metadata, "image", None) if metadata else None
            authors = getattr(metadata, "author", None) if metadata else None
            published_at = getattr(metadata, "date", None) if metadata else None

            if isinstance(authors, str):
                authors = [authors]
            if not isinstance(authors, list):
                authors = []

            return ArticleExtractionResponse(
                success=True,
                url=url,
                title=title,
                text=text[: self.max_text_length],
                excerpt=excerpt,
                image_url=image_url,
                authors=authors,
                published_at=str(published_at) if published_at else None,
                extraction_method="trafilatura_fastapi",
                status_code=200,
                error=None,
            )
        except Exception as exc:
            logger.warning("Article extraction failed for %s: %s", url, exc)
            return ArticleExtractionResponse(
                success=False,
                url=url,
                extraction_method="trafilatura_fastapi",
                error=str(exc)[:500],
            )


extraction_service = ExtractionService()
