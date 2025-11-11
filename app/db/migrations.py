"""Lightweight schema upgrades applied outside of Alembic."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def run_schema_upgrades(engine: Engine) -> None:
    """Apply idempotent schema upgrades required by the application."""

    statements = [
        """
        ALTER TABLE establishments
        ADD COLUMN IF NOT EXISTS google_place_id VARCHAR(128)
        """,
        """
        ALTER TABLE establishments
        ADD COLUMN IF NOT EXISTS google_place_url VARCHAR(512)
        """,
        """
        ALTER TABLE establishments
        ADD COLUMN IF NOT EXISTS google_last_checked_at TIMESTAMP
        """,
        """
        ALTER TABLE establishments
        ADD COLUMN IF NOT EXISTS google_last_found_at TIMESTAMP
        """,
        """
        ALTER TABLE establishments
        ADD COLUMN IF NOT EXISTS google_check_status VARCHAR(32) DEFAULT 'pending'
        """,
        """
        UPDATE establishments
        SET google_check_status = 'pending'
        WHERE google_check_status IS NULL
        """,
    ]

    with engine.begin() as connection:
        for stmt in statements:
            connection.execute(text(stmt))
