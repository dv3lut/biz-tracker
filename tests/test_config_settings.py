from __future__ import annotations

from sqlalchemy.engine import URL

from app import config


def test_permissive_json_loads_handles_numbers_and_strings():
    assert config._permissive_json_loads("42") == 42
    assert config._permissive_json_loads("  true  ") is True
    assert config._permissive_json_loads("not-json") == "not-json"
    assert config._permissive_json_loads("   ") == "   "
    assert config._permissive_json_loads("-12.5") == -12.5
    assert config._permissive_json_loads("{not valid}") == "{not valid}"
    assert config._permissive_json_loads("0") == 0
    # Numeric strings with invalid JSON formatting (leading zeroes) should be returned as-is.
    assert config._permissive_json_loads("01.0") == "01.0"


def test_database_settings_builds_url_from_parts():
    settings = config.DatabaseSettings(
        host="db",
        port=6543,
        name="testdb",
        user="biz",
        password="secret",
    )

    url = settings.sqlalchemy_url

    assert isinstance(url, URL)
    assert url.database == "testdb"
    assert url.host == "db"
    assert url.username == "biz"


def test_database_settings_honors_prebuilt_url():
    settings = config.DatabaseSettings(url="postgresql+psycopg://user:pass@db/custom")

    url = settings.sqlalchemy_url

    assert url.host == "db"
    assert url.database == "custom"


def test_email_settings_apply_provider_defaults_and_normalize():
    settings = config.EmailSettings(
        provider="mailhog",
        smtp_host=" ",
        smtp_username="NONE",
        smtp_password="null",
        from_address=" ops@example.com ",
    )

    assert settings.smtp_host == "localhost"
    assert settings.smtp_port == 1025
    assert settings.use_tls is False
    assert settings.smtp_username is None
    assert settings.from_address == "ops@example.com"

    mailjet = config.EmailSettings(provider="mailjet", smtp_host=None)
    assert mailjet.smtp_host == "in-v3.mailjet.com"
    assert mailjet.smtp_port == 587
    assert mailjet.use_tls is True


def test_google_settings_enabled_flag():
    settings = config.GoogleSettings(api_key="  abc123  ")

    assert settings.enabled is True
    assert config.GoogleSettings(api_key=" none ").enabled is False
    assert config.GoogleSettings(api_key="  NONE  ").api_key is None


def test_settings_instance_reports_local_environment():
    settings = config.Settings(
        environment="Local",
        database={"url": "postgresql+psycopg://user:pass@localhost/db"},
        sirene={"api_token": "token"},
    )

    assert settings.is_local is True


def test_logging_settings_bool_normalization():
    settings = config.LoggingSettings(
        elasticsearch={
            "enabled": "yes",
            "verify_certs": "0",
        }
    )

    assert settings.elasticsearch.enabled is True
    assert settings.elasticsearch.verify_certs is False


def test_api_settings_split_allowed_origins_string():
    settings = config.ApiSettings(allowed_origins=" https://a.test , ,https://b.test ")

    assert settings.allowed_origins == ["https://a.test", "https://b.test"]


def test_email_settings_nullable_validator_preserves_non_strings():
    assert config.EmailSettings._normalize_nullable_field(123) == 123
