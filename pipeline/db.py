"""Database connection and helpers for Neon PostgreSQL."""

import os
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

import psycopg2
import psycopg2.extras


def get_connection():
    return psycopg2.connect(os.environ["NEON_DATABASE_URL"], sslmode="require")


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
        SELECT id, title, url, source_type, description, image_url
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


def update_article_full_text(cur, article_id: str, full_text: str, image_url: str | None = None):
    if image_url:
        cur.execute(
            "UPDATE articles SET full_text = %s, image_url = %s, status = 'scraped' WHERE id = %s",
            (full_text, image_url, article_id),
        )
    else:
        cur.execute(
            "UPDATE articles SET full_text = %s, status = 'scraped' WHERE id = %s",
            (full_text, article_id),
        )


def update_article_embedding(cur, article_id: str, embedding: list[float]):
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    cur.execute(
        "UPDATE articles SET embedding = %s::vector, status = 'processed' WHERE id = %s",
        (embedding_str, article_id),
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
