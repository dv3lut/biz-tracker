"""Lightweight schema upgrades applied outside of Alembic."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def run_schema_upgrades(engine: Engine) -> None:
    """Apply idempotent schema upgrades required by the application."""

    statements = [
        """
        CREATE TABLE IF NOT EXISTS clients (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            start_date DATE NOT NULL,
            end_date DATE,
            emails_sent_count INTEGER NOT NULL DEFAULT 0,
            last_email_sent_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS client_recipients (
            id UUID PRIMARY KEY,
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_client_recipients_client_email
        ON client_recipients (client_id, email)
        """,
        """
        CREATE TABLE IF NOT EXISTS admin_recipients (
            id UUID PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
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
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS google_queue_count INTEGER DEFAULT 0
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS google_eligible_count INTEGER DEFAULT 0
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS google_matched_count INTEGER DEFAULT 0
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS google_pending_count INTEGER DEFAULT 0
        """,
        """
        ALTER TABLE sync_state
        ADD COLUMN IF NOT EXISTS last_creation_date DATE
        """,
    """
    ALTER TABLE sync_runs
    ADD COLUMN IF NOT EXISTS google_api_call_count INTEGER DEFAULT 0
    """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS google_immediate_matched_count INTEGER DEFAULT 0
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS google_late_matched_count INTEGER DEFAULT 0
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS updated_records INTEGER DEFAULT 0
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS summary JSONB
        """,
        """
        CREATE TABLE IF NOT EXISTS google_retry_config (
            id SERIAL PRIMARY KEY,
            retry_weekdays JSONB NOT NULL DEFAULT '[]'::jsonb,
            default_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
            micro_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
            micro_company_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
            micro_legal_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
    ]

    with engine.begin() as connection:
        for stmt in statements:
            connection.execute(text(stmt))
