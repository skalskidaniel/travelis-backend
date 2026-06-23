import os
import pytest

from core.config import Settings


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("DYNAMODB_USERS_TABLE", "CustomUsers")
    monkeypatch.setenv("DYNAMODB_CELLS_TABLE", "CustomCells")
    monkeypatch.setenv("DYNAMODB_OFFERS_TABLE", "CustomOffers")
    monkeypatch.setenv("DYNAMODB_USER_OFFERS_TABLE", "CustomUserOffers")
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "test-public-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "test-private-key")
    monkeypatch.setenv("ATTRACTIVENESS_Z_THRESHOLD", "-0.5")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENVIRONMENT", "prod")


def test_settings_loads_flat_environment_variables(env_vars):
    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.users_table == "CustomUsers"
    assert settings.cells_table == "CustomCells"
    assert settings.offers_table == "CustomOffers"
    assert settings.user_offers_table == "CustomUserOffers"
    assert settings.vapid_public_key == "test-public-key"
    assert settings.vapid_private_key == "test-private-key"
    assert settings.attractiveness_z_threshold == -0.5
    assert settings.powertools_log_level == "DEBUG"
    assert settings.environment == "prod"


def test_settings_exposes_nested_views(env_vars):
    settings = Settings(_env_file=None)

    assert settings.db is not None
    assert settings.db.users_table == "CustomUsers"
    assert settings.push is not None
    assert settings.push.vapid_public_key == "test-public-key"
    assert settings.scoring is not None
    assert settings.scoring.attractiveness_z_threshold == -0.5


def test_settings_log_level_fallback(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("POWERTOOLS_LOG_LEVEL", raising=False)
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    settings = Settings(_env_file=None)
    assert settings.powertools_log_level == "WARNING"


def test_settings_sets_powertools_log_level_env_var(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("POWERTOOLS_LOG_LEVEL", raising=False)
    monkeypatch.setenv("LOG_LEVEL", "CRITICAL")

    Settings(_env_file=None)
    assert os.environ.get("POWERTOOLS_LOG_LEVEL") == "CRITICAL"


def test_settings_environment_loading(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    # 1. Default should be "dev"
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("STAGE", raising=False)
    settings_default = Settings(_env_file=None)
    assert settings_default.environment == "dev"

    # 2. ENVIRONMENT should take precedence
    monkeypatch.setenv("ENVIRONMENT", "prod")
    settings_env = Settings(_env_file=None)
    assert settings_env.environment == "prod"

    # 3. STAGE should act as fallback
    monkeypatch.delenv("ENVIRONMENT")
    monkeypatch.setenv("STAGE", "staging")
    settings_alias = Settings(_env_file=None)
    assert settings_alias.environment == "staging"


def test_settings_default_attractiveness_threshold_matches_scorer(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("ATTRACTIVENESS_Z_THRESHOLD", raising=False)

    from core.services.scoring.config import StatisticalScorerConfig

    settings = Settings(_env_file=None)
    assert settings.attractiveness_z_threshold == StatisticalScorerConfig().z_threshold
