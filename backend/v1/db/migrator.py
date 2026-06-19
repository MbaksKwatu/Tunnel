"""
Startup migration runner.

Re-runs every *.sql file in backend/migrations/ on every cold start. All
migration files must use IF NOT EXISTS / ADD COLUMN IF NOT EXISTS guards,
so re-applying an already-applied file is a no-op.

Deliberately does NOT trust an "already applied" tracking table to decide
what to skip — a staging DB restore/reset can roll back actual columns while
leaving tracking metadata untouched, which causes silent schema drift that
no skip-based migrator would ever catch. Always re-asserting the full
schema on every boot is what makes this self-healing.

Requires DATABASE_URL env var — the direct Postgres connection string from
Supabase: Project Settings -> Database -> Connection string (URI).
"""
import logging
import os
import pathlib
import re

import psycopg2

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = pathlib.Path(__file__).parent.parent.parent / "migrations"


def _get_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to Cloud Run env vars: "
            "Supabase -> Project Settings -> Database -> Connection string (URI)."
        )
    return psycopg2.connect(url)


def _migration_files() -> list[pathlib.Path]:
    if not _MIGRATIONS_DIR.exists():
        logger.warning("[migrator] migrations dir not found: %s", _MIGRATIONS_DIR)
        return []
    return sorted(f for f in _MIGRATIONS_DIR.glob("*.sql") if re.match(r"^\d+", f.name))


def run_pending_migrations() -> None:
    files = _migration_files()
    if not files:
        logger.info("[migrator] no migration files found — skipping")
        return

    try:
        conn = _get_conn()
    except RuntimeError as e:
        logger.warning("[migrator] %s — skipping migrations", e)
        return

    applied, failed = 0, []
    try:
        for mf in files:
            sql = mf.read_text()
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(sql)
                applied += 1
            except Exception:
                conn.rollback()
                failed.append(mf.name)
                logger.exception("[migrator] %s failed to apply", mf.name)
        logger.info(
            "[migrator] re-asserted %d migration file(s), %d failed",
            applied, len(failed),
        )
        if failed:
            logger.error("[migrator] failing migrations: %s", failed)
    finally:
        conn.close()
