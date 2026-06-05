"""Batch embedding computation using sentence-transformers (bge-small-en)."""

import logging

log = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
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
        parts.append(article["title"])
    if article.get("description"):
        parts.append(article["description"][:300])
    if article.get("full_text"):
        parts.append(article["full_text"][:500])
    return " ".join(parts)


def compute_embeddings(articles: list[dict], batch_size: int = 32) -> list[dict]:
    """Compute embeddings for a batch of articles.

    Returns list of {id, embedding} dicts.
    """
    if not articles:
        return []

    model = _get_model()
    texts = [build_text_for_embedding(a) for a in articles]

    log.info("Computing embeddings for %d articles...", len(texts))
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=True)

    results = []
    for article, emb in zip(articles, embeddings):
        results.append({
            "id": article["id"],
            "embedding": emb.tolist(),
        })

    log.info("Computed %d embeddings", len(results))
    return results
