import pytest

from app.config import Settings


def test_production_requires_api_key() -> None:
    settings = Settings(app_env="production", api_key=None)
    with pytest.raises(ValueError, match="API_KEY"):
        settings.validate_production()


def test_production_accepts_required_security_settings() -> None:
    settings = Settings(
        app_env="production",
        api_key="test-secret",
        trusted_hosts="api.example.com",
    )
    settings.validate_production()


def test_development_does_not_require_api_key() -> None:
    settings = Settings(app_env="development", api_key=None)
    settings.validate_production()


def test_bare_postgresql_url_is_forced_to_psycopg_driver() -> None:
    settings = Settings(database_url="postgresql://user:pass@localhost:5432/sporty")
    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/sporty"


def test_legacy_postgres_scheme_is_forced_to_psycopg_driver() -> None:
    settings = Settings(database_url="postgres://user:pass@localhost:5432/sporty")
    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/sporty"


def test_explicit_driver_and_sqlite_urls_are_untouched() -> None:
    settings = Settings(database_url="postgresql+psycopg://user:pass@localhost:5432/sporty")
    assert settings.database_url == "postgresql+psycopg://user:pass@localhost:5432/sporty"
    assert Settings(database_url="sqlite:///:memory:").database_url == "sqlite:///:memory:"
