"""Database connection and helpers for PostgreSQL (Neon or Supabase)."""

import os
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

import psycopg2
import psycopg2.extras


def get_connection():
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL (or NEON_DATABASE_URL) is required")
    return psycopg2.connect(db_url, sslmode="require")


@contextmanager
def get_cursor():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def gen_id() -> str:
    return uuid.uuid4().hex[:16]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def fetch_new_articles(cur, limit: int = 200) -> list[dict]:
    """Get articles that need processing (status='new')."""
    cur.execute(
        """
        SELECT id, title, url, source_name, source_type, description, image_url
        FROM articles
        WHERE status = 'new'
        ORDER BY fetched_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    return cur.fetchall()


def fetch_unembedded_articles(cur, limit: int = 500) -> list[dict]:
    """Get articles that have content but no embedding yet."""
    cur.execute(
        """
        SELECT id, title, source_name, description, full_text
        FROM articles
        WHERE embedding IS NULL
          AND status IN ('new', 'scraped')
        ORDER BY fetched_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    return cur.fetchall()


def fetch_source_extraction_rules(cur) -> dict[str, dict]:
    cur.execute(
        """
        SELECT source_name, strategy, use_fastapi, use_local_fallback,
               timeout_ms, max_retries, requires_browser, is_blocked_often
        FROM source_extraction_rules
        """
    )
    return {
        row["source_name"].lower().strip(): row
        for row in cur.fetchall()
        if row.get("source_name")
    }


def update_article_full_text(
    cur,
    article_id: str,
    full_text: str,
    image_url: str | None = None,
    extraction_method: str = "local_scraper",
):
    if image_url:
        cur.execute(
            """
            UPDATE articles
            SET full_text = %s,
                image_url = %s,
                status = 'scraped',
                pipeline_status = 'extracted',
                extraction_status = 'extracted',
                extraction_method = %s,
                extracted_at = NOW(),
                last_error = NULL,
                last_processed_at = NOW()
            WHERE id = %s
            """,
            (full_text, image_url, extraction_method, article_id),
        )
    else:
        cur.execute(
            """
            UPDATE articles
            SET full_text = %s,
                status = 'scraped',
                pipeline_status = 'extracted',
                extraction_status = 'extracted',
                extraction_method = %s,
                extracted_at = NOW(),
                last_error = NULL,
                last_processed_at = NOW()
            WHERE id = %s
            """,
            (full_text, extraction_method, article_id),
        )


def update_article_embedding(cur, article_id: str, embedding: list[float]):
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    model_name = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
    cur.execute(
        """
        UPDATE articles
        SET embedding = %s::vector,
            status = 'processed',
            pipeline_status = 'embedded',
            embedding_status = 'embedded',
            embedding_model = %s,
            embedding_dimensions = %s,
            embedded_at = NOW(),
            last_error = NULL,
            last_processed_at = NOW()
        WHERE id = %s
        """,
        (embedding_str, model_name, len(embedding), article_id),
    )


def mark_article_extraction_failed(cur, article_id: str, error: str):
    cur.execute(
        """
        UPDATE articles
        SET extraction_status = 'failed',
            pipeline_status = 'extraction_failed',
            last_error = %s,
            retry_count = COALESCE(retry_count, 0) + 1,
            last_processed_at = NOW()
        WHERE id = %s
        """,
        (error[:1000], article_id),
    )


def mark_article_extraction_skipped(cur, article_id: str, method: str, reason: str):
    cur.execute(
        """
        UPDATE articles
        SET extraction_status = 'skipped',
            pipeline_status = 'extraction_skipped',
            extraction_method = %s,
            last_error = %s,
            last_processed_at = NOW()
        WHERE id = %s
        """,
        (method, reason[:1000], article_id),
    )


def mark_article_embedding_failed(cur, article_id: str, error: str):
    cur.execute(
        """
        UPDATE articles
        SET embedding_status = 'failed',
            pipeline_status = 'embedding_failed',
            last_error = %s,
            retry_count = COALESCE(retry_count, 0) + 1,
            last_processed_at = NOW()
        WHERE id = %s
        """,
        (error[:1000], article_id),
    )


def insert_pipeline_run(cur, pipeline_type: str) -> str:
    run_id = gen_id()
    cur.execute(
        """
        INSERT INTO pipeline_runs (id, pipeline_type, status, started_at)
        VALUES (%s, %s, 'running', NOW())
        """,
        (run_id, pipeline_type),
    )
    return run_id


def complete_pipeline_run(cur, run_id: str, stats: dict):
    cur.execute(
        """
        UPDATE pipeline_runs
        SET status = 'completed',
            completed_at = NOW(),
            articles_fetched = %(articles_fetched)s,
            articles_embedded = %(articles_embedded)s,
            clusters_created = %(clusters_created)s,
            clusters_updated = %(clusters_updated)s,
            analyses_generated = %(analyses_generated)s,
            duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::int
        WHERE id = %(run_id)s
        """,
        {**stats, "run_id": run_id},
    )


def fail_pipeline_run(cur, run_id: str, errors: list[str]):
    import json

    cur.execute(
        """
        UPDATE pipeline_runs
        SET status = 'failed',
            completed_at = NOW(),
            errors = %s::jsonb,
            duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::int
        WHERE id = %s
        """,
        (json.dumps(errors), run_id),
    )
