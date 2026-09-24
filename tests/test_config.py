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
