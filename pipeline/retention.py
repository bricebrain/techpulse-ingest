"""Retention / purge step — keep the Neon free tier (0.5 GB) under control.

Calls the SQL function `prune_techpulse(...)` (see migrations/007_retention_policy.sql).
All windows are configurable via environment variables so a run can be tuned or
made more aggressive without code changes. The step is best-effort: a failure here
must never break ingestion.
"""

import logging
import os

log = logging.getLogger(__name__)


def retention_enabled() -> bool:
    return os.getenv("TECHPULSE_RETENTION_ENABLED", "1") not in ("0", "false", "False")


def _days(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def run_retention(cur) -> dict[str, int]:
    """Run the purge and return {step: rows_affected}. Cursor is committed by caller."""
    params = (
        _days("TECHPULSE_RETENTION_FULLTEXT_DAYS", 60),
        _days("TECHPULSE_RETENTION_ARTICLE_DELETE_DAYS", 180),
        _days("TECHPULSE_RETENTION_TREND_DAYS", 120),
        _days("TECHPULSE_RETENTION_ANALYSIS_DAYS", 90),
        _days("TECHPULSE_RETENTION_CLUSTER_IDLE_DAYS", 30),
        _days("TECHPULSE_RETENTION_PIPELINE_DAYS", 30),
    )

    cur.execute(
        "SELECT step, rows_affected FROM prune_techpulse(%s, %s, %s, %s, %s, %s)",
        params,
    )
    summary = {row[0]: int(row[1]) for row in cur.fetchall()}
    log.info("Retention summary: %s", summary)
    return summary
