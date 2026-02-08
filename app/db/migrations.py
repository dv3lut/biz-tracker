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
            use_subcategory_label_in_client_alerts BOOLEAN NOT NULL DEFAULT FALSE,
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
            name VARCHAR(255) NOT NULL,
            description TEXT,
            naf_code VARCHAR(10) NOT NULL,
            price_cents INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS naf_category_subcategories (
            category_id UUID NOT NULL REFERENCES naf_categories(id) ON DELETE CASCADE,
            subcategory_id UUID NOT NULL REFERENCES naf_subcategories(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (category_id, subcategory_id)
        )
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'naf_subcategories_naf_code_key'
            ) THEN
                ALTER TABLE naf_subcategories DROP CONSTRAINT naf_subcategories_naf_code_key;
            END IF;
        END $$;
        """,
        """
        DO $$
        DECLARE
            idx_name text;
        BEGIN
            SELECT i.relname
            INTO idx_name
            FROM pg_class t
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_attribute a ON a.attrelid = t.oid
            WHERE t.relname = 'naf_subcategories'
              AND ix.indisunique
              AND a.attname = 'naf_code'
              AND a.attnum = ANY(ix.indkey)
              AND array_length(ix.indkey, 1) = 1
            LIMIT 1;

            IF idx_name IS NOT NULL THEN
                EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
            END IF;
        END $$;
        """,
        """
        ALTER TABLE IF EXISTS naf_subcategories
        ADD COLUMN IF NOT EXISTS description TEXT
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_naf_subcategories_naf_code
        ON naf_subcategories (naf_code)
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_naf_subcategories_naf_code
        ON naf_subcategories (naf_code)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_naf_category_subcategories_category_id
        ON naf_category_subcategories (category_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_naf_category_subcategories_subcategory_id
        ON naf_category_subcategories (subcategory_id)
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'naf_subcategories'
                  AND column_name = 'category_id'
            ) THEN
                INSERT INTO naf_category_subcategories (category_id, subcategory_id, created_at)
                SELECT category_id, id, created_at
                FROM naf_subcategories
                WHERE category_id IS NOT NULL
                ON CONFLICT DO NOTHING;
            END IF;
        END $$;
        """,
        """
        ALTER TABLE IF EXISTS naf_subcategories
        DROP CONSTRAINT IF EXISTS naf_subcategories_category_id_fkey
        """,
        """
        DROP INDEX IF EXISTS uq_naf_subcategories_category_code
        """,
        """
        DROP INDEX IF EXISTS ix_naf_subcategories_category_id
        """,
        """
        ALTER TABLE IF EXISTS naf_subcategories
        DROP COLUMN IF EXISTS category_id
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
        CREATE TABLE IF NOT EXISTS departments (
            id UUID PRIMARY KEY,
            region_id UUID NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
            code VARCHAR(8) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            order_index INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_departments_code
        ON departments (code)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_departments_region_id
        ON departments (region_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS client_departments (
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            department_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (client_id, department_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_client_departments_client_id
        ON client_departments (client_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_client_departments_department_id
        ON client_departments (department_id)
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
    ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS category_ids JSONB NOT NULL DEFAULT '[]'::jsonb
    """,
    """
    ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS include_admins_in_client_alerts BOOLEAN NOT NULL DEFAULT FALSE
    """,
        """
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS use_subcategory_label_in_client_alerts BOOLEAN NOT NULL DEFAULT FALSE
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
        ADD COLUMN IF NOT EXISTS months_back INTEGER
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
        """
        ALTER TABLE establishments
        ADD COLUMN IF NOT EXISTS legal_unit_name VARCHAR(512)
        """,
        """
        CREATE TABLE IF NOT EXISTS directors (
            id UUID PRIMARY KEY,
            establishment_siret VARCHAR(14) NOT NULL REFERENCES establishments(siret) ON DELETE CASCADE,
            type_dirigeant VARCHAR(32) NOT NULL,
            first_names VARCHAR(512),
            last_name VARCHAR(255),
            quality VARCHAR(255),
            birth_month INTEGER,
            birth_year INTEGER,
            siren VARCHAR(9),
            denomination VARCHAR(512),
            nationality VARCHAR(128),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_directors_establishment_siret
        ON directors (establishment_siret)
        """,
        """
        ALTER TABLE IF EXISTS directors
        ADD COLUMN IF NOT EXISTS linkedin_profile_url VARCHAR(1024)
        """,
        """
        ALTER TABLE IF EXISTS directors
        ADD COLUMN IF NOT EXISTS linkedin_profile_data JSONB
        """,
        """
        ALTER TABLE IF EXISTS directors
        ADD COLUMN IF NOT EXISTS linkedin_last_checked_at TIMESTAMP
        """,
        """
        ALTER TABLE IF EXISTS directors
        ADD COLUMN IF NOT EXISTS linkedin_check_status VARCHAR(32) NOT NULL DEFAULT 'pending'
        """,
        """
        ALTER TABLE establishments
        DROP COLUMN IF EXISTS director_first_names
        """,
        """
        ALTER TABLE establishments
        DROP COLUMN IF EXISTS director_last_name
        """,
        """
        ALTER TABLE establishments
        DROP COLUMN IF EXISTS director_birth_month
        """,
        """
        ALTER TABLE establishments
        DROP COLUMN IF EXISTS director_birth_year
        """,
        # LinkedIn progress columns on sync_runs
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS linkedin_queue_count INTEGER NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS linkedin_searched_count INTEGER NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS linkedin_found_count INTEGER NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS linkedin_not_found_count INTEGER NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE sync_runs
        ADD COLUMN IF NOT EXISTS linkedin_error_count INTEGER NOT NULL DEFAULT 0
        """,
    ]

    with engine.begin() as connection:
        for stmt in statements:
            connection.execute(text(stmt))
