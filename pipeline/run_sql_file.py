"""Run a SQL migration file against Neon."""

import os
import sys
from pathlib import Path

from . import db


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m pipeline.run_sql_file <path.sql>")

    sql_path = Path(sys.argv[1])
    if not sql_path.exists():
        raise SystemExit(f"SQL file not found: {sql_path}")

    if "NEON_DATABASE_URL" not in os.environ:
        raise SystemExit("NEON_DATABASE_URL is required")

    sql = sql_path.read_text(encoding="utf-8")
    with db.get_cursor() as cur:
        cur.execute(sql)

    print(f"Applied migration: {sql_path}")


if __name__ == "__main__":
    main()
