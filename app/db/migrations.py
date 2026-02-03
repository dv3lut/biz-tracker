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
            listing_statuses JSONB NOT NULL DEFAULT '["recent_creation","recent_creation_missing_contact","not_recent_creation"]'::jsonb,
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
        CREATE TABLE IF NOT EXISTS naf_categories (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS naf_subcategories (
            id UUID PRIMARY KEY,
            category_id UUID NOT NULL REFERENCES naf_categories(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            naf_code VARCHAR(10) NOT NULL UNIQUE,
            price_cents INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        ALTER TABLE IF EXISTS naf_subcategories
        ADD COLUMN IF NOT EXISTS description TEXT
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_naf_subcategories_category_id
        ON naf_subcategories (category_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_naf_subcategories_naf_code
        ON naf_subcategories (naf_code)
        """,
        """
        CREATE TABLE IF NOT EXISTS client_subscriptions (
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            subcategory_id UUID NOT NULL REFERENCES naf_subcategories(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (client_id, subcategory_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS regions (
            id UUID PRIMARY KEY,
            code VARCHAR(16) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            order_index INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_regions_code
        ON regions (code)
        """,
        """
        CREATE TABLE IF NOT EXISTS client_regions (
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            region_id UUID NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (client_id, region_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_client_regions_client_id
        ON client_regions (client_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_client_regions_region_id
        ON client_regions (region_id)
        """,
        """
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)
        """,
        """
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255)
        """,
        """
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS stripe_subscription_status VARCHAR(64)
        """,
        """
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS stripe_current_period_end TIMESTAMP
        """,
        """
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS stripe_cancel_at TIMESTAMP
        """,
        """
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS stripe_plan_key VARCHAR(32)
        """,
        """
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS stripe_price_id VARCHAR(255)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_clients_stripe_customer_id
        ON clients (stripe_customer_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_clients_stripe_subscription_id
        ON clients (stripe_subscription_id)
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
        ALTER TABLE establishments
        ADD COLUMN IF NOT EXISTS google_match_confidence DOUBLE PRECISION
        """,
        """
        ALTER TABLE establishments
        ADD COLUMN IF NOT EXISTS google_category_match_confidence DOUBLE PRECISION
        """,
    """
    ALTER TABLE establishments
    ADD COLUMN IF NOT EXISTS google_listing_origin_at TIMESTAMP
    """,
    """
    ALTER TABLE establishments
    ADD COLUMN IF NOT EXISTS google_listing_origin_source VARCHAR(32) DEFAULT 'unknown'
    """,
    """
    ALTER TABLE establishments
    ADD COLUMN IF NOT EXISTS google_listing_age_status VARCHAR(32) DEFAULT 'unknown'
    """,
    """
    UPDATE establishments
    SET google_listing_age_status = 'unknown'
    WHERE google_listing_age_status IS NULL
    """,
    """
    UPDATE establishments
    SET google_listing_origin_source = 'unknown'
    WHERE google_listing_origin_source IS NULL
    """,
    """
    ALTER TABLE establishments
    ADD COLUMN IF NOT EXISTS google_contact_phone VARCHAR(64)
    """,
    """
    ALTER TABLE establishments
    ADD COLUMN IF NOT EXISTS google_contact_email VARCHAR(255)
    """,
    """
    ALTER TABLE establishments
    ADD COLUMN IF NOT EXISTS google_contact_website VARCHAR(512)
    """,
    """
    ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS listing_statuses JSONB NOT NULL DEFAULT '["recent_creation","recent_creation_missing_contact","not_recent_creation"]'::jsonb
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
    ALTER TABLE sync_runs
    ADD COLUMN IF NOT EXISTS mode VARCHAR(32) NOT NULL DEFAULT 'full'
    """,
    """
    ALTER TABLE sync_runs
    ADD COLUMN IF NOT EXISTS google_reset_state BOOLEAN NOT NULL DEFAULT FALSE
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
    ADD COLUMN IF NOT EXISTS replay_for_date DATE
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
    ALTER TABLE sync_runs
    ADD COLUMN IF NOT EXISTS target_naf_codes JSONB
    """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS initial_backfill BOOLEAN NOT NULL DEFAULT FALSE
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS target_client_ids JSONB
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS notify_admins BOOLEAN NOT NULL DEFAULT TRUE
        """,
    """
    ALTER TABLE sync_runs
    ADD COLUMN IF NOT EXISTS day_replay_force_google BOOLEAN NOT NULL DEFAULT FALSE
    """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS day_replay_reference VARCHAR(32) NOT NULL DEFAULT 'creation_date'
        """,
        """
        ALTER TABLE IF EXISTS naf_categories
        DROP COLUMN IF EXISTS order_index
        """,
        """
        ALTER TABLE IF EXISTS naf_subcategories
        DROP COLUMN IF EXISTS order_index
        """,
        """
        ALTER TABLE IF EXISTS naf_subcategories
        DROP COLUMN IF EXISTS naf_label
        """,
        """
        ALTER TABLE IF EXISTS naf_categories
        ADD COLUMN IF NOT EXISTS keywords JSONB NOT NULL DEFAULT '[]'::jsonb
        """,
        """
        UPDATE naf_categories
        SET keywords = '[]'::jsonb
        WHERE keywords IS NULL
        """,
        """
        CREATE TABLE IF NOT EXISTS google_retry_config (
            id SERIAL PRIMARY KEY,
            retry_weekdays JSONB NOT NULL DEFAULT '[]'::jsonb,
            default_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
            micro_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
            micro_company_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
            micro_legal_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
            retry_missing_contact_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            retry_missing_contact_frequency_days INTEGER NOT NULL DEFAULT 14,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        ALTER TABLE google_retry_config
        ADD COLUMN IF NOT EXISTS retry_missing_contact_enabled BOOLEAN NOT NULL DEFAULT TRUE
        """,
        """
        ALTER TABLE google_retry_config
        ADD COLUMN IF NOT EXISTS retry_missing_contact_frequency_days INTEGER NOT NULL DEFAULT 14
        """,
        """
        CREATE TABLE IF NOT EXISTS stripe_billing_settings (
            id SERIAL PRIMARY KEY,
            trial_period_days INTEGER NOT NULL DEFAULT 14,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        ALTER TABLE stripe_billing_settings
        ADD COLUMN IF NOT EXISTS last_weekly_summary_at TIMESTAMP
        """,
        """
        CREATE TABLE IF NOT EXISTS client_stripe_subscriptions (
            id UUID PRIMARY KEY,
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            stripe_subscription_id VARCHAR(255) NOT NULL UNIQUE,
            stripe_customer_id VARCHAR(255),
            status VARCHAR(64),
            plan_key VARCHAR(32),
            price_id VARCHAR(255),
            referrer_name VARCHAR(255),
            purchased_at TIMESTAMP,
            trial_start_at TIMESTAMP,
            trial_end_at TIMESTAMP,
            paid_start_at TIMESTAMP,
            current_period_start TIMESTAMP,
            current_period_end TIMESTAMP,
            cancel_at TIMESTAMP,
            canceled_at TIMESTAMP,
            ended_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_client_stripe_subscriptions_client_id
        ON client_stripe_subscriptions (client_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_client_stripe_subscriptions_subscription_id
        ON client_stripe_subscriptions (stripe_subscription_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_client_stripe_subscriptions_customer_id
        ON client_stripe_subscriptions (stripe_customer_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS client_subscription_events (
            id UUID PRIMARY KEY,
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            stripe_subscription_id VARCHAR(255),
            event_type VARCHAR(64) NOT NULL,
            from_plan_key VARCHAR(32),
            to_plan_key VARCHAR(32),
            from_category_ids JSONB,
            to_category_ids JSONB,
            effective_at TIMESTAMP,
            source VARCHAR(32),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_client_subscription_events_client_id
        ON client_subscription_events (client_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_client_subscription_events_subscription_id
        ON client_subscription_events (stripe_subscription_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_client_subscription_events_created_at
        ON client_subscription_events (created_at)
        """,
        """
        ALTER TABLE client_stripe_subscriptions
        ADD COLUMN IF NOT EXISTS referrer_name VARCHAR(255)
        """,
    ]

    with engine.begin() as connection:
        for stmt in statements:
            connection.execute(text(stmt))
