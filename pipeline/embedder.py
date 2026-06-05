"""Batch embedding computation using sentence-transformers."""

import logging
import os

from .text_cleaning import clean_text, select_representative_text

log = logging.getLogger(__name__)

MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        log.info("Loading embedding model %s...", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        log.info("Embedding model loaded")
    return _model


def build_text_for_embedding(article: dict) -> str:
    """Build the text string to embed from article fields."""
    parts = []
    if article.get("title"):
        parts.append(f"Title: {clean_text(article['title'])}")
    if article.get("source_name"):
        parts.append(f"Source: {clean_text(article['source_name'])}")
    if article.get("description"):
        parts.append(f"Summary: {clean_text(article['description'])[:700]}")
    if article.get("full_text"):
        parts.append(f"Content: {select_representative_text(article['full_text'], 2500)}")
    return "\n".join(part for part in parts if part.strip())


def compute_embeddings(articles: list[dict], batch_size: int = 16) -> list[dict]:
    """Compute embeddings for a batch of articles.

    Returns list of {id, embedding} dicts.
    """
    if not articles:
        return []

    model = _get_model()
    texts = [build_text_for_embedding(a) for a in articles]

    log.info("Computing embeddings for %d articles...", len(texts))
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    results = []
    for article, emb in zip(articles, embeddings):
        results.append({
            "id": article["id"],
            "embedding": emb.tolist(),
        })

    log.info("Computed %d embeddings", len(results))
    return results
