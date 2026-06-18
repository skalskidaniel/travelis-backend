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


def test_settings_loads_flat_environment_variables(env_vars):
    settings = Settings()

    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.users_table == "CustomUsers"
    assert settings.cells_table == "CustomCells"
    assert settings.offers_table == "CustomOffers"
    assert settings.user_offers_table == "CustomUserOffers"
    assert settings.vapid_public_key == "test-public-key"
    assert settings.vapid_private_key == "test-private-key"
    assert settings.attractiveness_z_threshold == -0.5


def test_settings_exposes_nested_views(env_vars):
    settings = Settings()

    assert settings.db is not None
    assert settings.db.users_table == "CustomUsers"
    assert settings.push is not None
    assert settings.push.vapid_public_key == "test-public-key"
    assert settings.scoring is not None
    assert settings.scoring.attractiveness_z_threshold == -0.5
