from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel
from pydantic_settings.sources.types import ForceDecode, NoDecode
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

    mailjet.smtp_host = None
    mailjet._apply_provider_defaults()
    assert mailjet.smtp_host == "in-v3.mailjet.com"


def test_google_settings_enabled_flag():
    settings = config.GoogleSettings(api_key="  abc123  ")

    assert settings.enabled is True
    assert config.GoogleSettings(api_key=" none ").enabled is False
    assert config.GoogleSettings(api_key="  NONE  ").api_key is None
    assert config.GoogleSettings._normalize_api_key(None) is None
    assert config.GoogleSettings._normalize_api_key(123) == 123


def test_settings_instance_reports_local_environment():
    settings = config.Settings(
        environment="Local",
        database={"url": "postgresql+psycopg://user:pass@localhost/db"},
        sirene={"api_token": "token"},
    )

    assert settings.is_local is True


def test_settings_includes_public_contact_defaults_and_overrides():
    settings = config.Settings(
        environment="Local",
        database={"url": "postgresql+psycopg://user:pass@localhost/db"},
        sirene={"api_token": "token"},
    )

    assert settings.public_contact.enabled is True
    assert settings.public_contact.inbox_address

    overridden = config.Settings(
        environment="Local",
        database={"url": "postgresql+psycopg://user:pass@localhost/db"},
        sirene={"api_token": "token"},
        public_contact={"enabled": False, "inbox_address": "sales@business-tracker.fr"},
    )

    assert overridden.public_contact.enabled is False
    assert overridden.public_contact.inbox_address == "sales@business-tracker.fr"


def test_logging_settings_bool_normalization():
    settings = config.LoggingSettings(
        elasticsearch={
            "enabled": "yes",
            "verify_certs": "0",
        }
    )

    assert settings.elasticsearch.enabled is True
    assert settings.elasticsearch.verify_certs is False
    assert config.ElasticsearchLoggingSettings._normalize_bool(123) == 123


def test_api_settings_split_allowed_origins_string():
    settings = config.ApiSettings(allowed_origins=" https://a.test , ,https://b.test ")

    assert settings.allowed_origins == ["https://a.test", "https://b.test"]


def test_api_settings_normalizes_allowed_origins_trailing_slash():
    settings = config.ApiSettings(allowed_origins="https://admin.test/, https://foo.test")

    assert settings.allowed_origins == ["https://admin.test", "https://foo.test"]


def test_api_settings_normalizes_allowed_origins_list():
    settings = config.ApiSettings(allowed_origins=["https://admin.test/", " https://foo.test "])

    assert settings.allowed_origins == ["https://admin.test", "https://foo.test"]


def test_email_settings_nullable_validator_preserves_non_strings():
    assert config.EmailSettings._normalize_nullable_field(123) == 123


def test_api_settings_allows_none_and_empty_values():
    assert config.ApiSettings._split_allowed_origins(None) is None
    assert config.ApiSettings._split_allowed_origins(" ") == []
    assert config.ApiSettings._split_allowed_origins([" ", "https://ok.test/"]) == ["https://ok.test"]
    assert config.ApiSettings._split_allowed_origins(123) == 123


def test_api_settings_log_admin_requests_defaults_to_false_and_is_overridable():
    default_settings = config.ApiSettings()
    assert default_settings.log_admin_requests is False

    enabled = config.ApiSettings(log_admin_requests=True)
    assert enabled.log_admin_requests is True


def test_apify_settings_normalizes_token_and_enabled_flag():
    settings = config.ApifySettings(api_token="  token ")
    assert settings.api_token == "token"
    assert settings.enabled is True

    disabled = config.ApifySettings(api_token=" none ")
    assert disabled.api_token is None
    assert disabled.enabled is False
    assert config.ApifySettings._normalize_api_token(None) is None
    assert config.ApifySettings._normalize_api_token(123) == 123


def test_decode_complex_value_respects_no_decode_metadata():
    class DummyModel(BaseModel):
        value: Annotated[str, NoDecode]

    field = DummyModel.model_fields["value"]

    class DummySource:
        def __init__(self, enable_decoding: bool) -> None:
            self.config = {"enable_decoding": enable_decoding}

    source = DummySource(enable_decoding=True)
    raw = '"hello"'
    assert config._decode_complex_value_with_permissive_json(source, "value", field, raw) == raw


def test_decode_complex_value_force_decode_overrides_disabled_config():
    class DummyModel(BaseModel):
        value: Annotated[str, ForceDecode]

    field = DummyModel.model_fields["value"]

    class DummySource:
        def __init__(self, enable_decoding: bool) -> None:
            self.config = {"enable_decoding": enable_decoding}

    source = DummySource(enable_decoding=False)
    assert config._decode_complex_value_with_permissive_json(source, "value", field, b'"foo"') == "foo"


def test_decode_complex_value_skips_decoding_when_disabled():
    class DummyModel(BaseModel):
        value: str

    field = DummyModel.model_fields["value"]

    class DummySource:
        def __init__(self, enable_decoding: bool) -> None:
            self.config = {"enable_decoding": enable_decoding}

    source = DummySource(enable_decoding=False)
    raw = "[1, 2, 3]"
    assert config._decode_complex_value_with_permissive_json(source, "value", field, raw) == raw


def test_decode_complex_value_raises_on_non_string_payload():
    class DummyModel(BaseModel):
        value: str

    field = DummyModel.model_fields["value"]

    class DummySource:
        def __init__(self, enable_decoding: bool) -> None:
            self.config = {"enable_decoding": enable_decoding}

    source = DummySource(enable_decoding=True)
    with pytest.raises(TypeError):
        config._decode_complex_value_with_permissive_json(source, "value", field, {"a": 1})
