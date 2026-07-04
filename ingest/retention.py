"""Retention / purge step — disabled since the migration to Cloudflare D1.

The old implementation called the Postgres function `prune_techpulse(...)`
(see migrations/007_retention_policy.sql), which has no D1 equivalent yet.
Reimplementing retention against D1 is out of scope for the Neon->D1
migration; retention is handled separately, on the Worker/D1 side.
This module is kept as a no-op so `ingest.py` doesn't need restructuring
if/when D1-side retention lands.
"""

import logging
import os

log = logging.getLogger(__name__)


def retention_enabled() -> bool:
    return os.getenv("TECHPULSE_RETENTION_ENABLED", "1") not in ("0", "false", "False")


def run_retention() -> None:
    log.info(
        "Retention/purge is a no-op in this pipeline since the D1 migration; "
        "handled separately on the Worker/D1 side (out of scope here)."
    )
