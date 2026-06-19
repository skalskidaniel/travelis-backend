import pytest
from pydantic import ValidationError
from app.user.schemas import UserPreferencesUpdate
from core.models.common import BoardType


def test_user_preferences_update_valid():
    data = {
        "countries": ["PL", "DE"],
        "adults": 3,
        "board": "all-inclusive",
    }
    update = UserPreferencesUpdate(**data)
    assert update.countries == ["PL", "DE"]
    assert update.adults == 3
    assert update.board == BoardType.ALL_INCLUSIVE


def test_user_preferences_update_empty():
    update = UserPreferencesUpdate()
    assert update.countries is None
    assert update.adults is None


def test_user_preferences_update_invalid_adults():
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(adults=0)


def test_user_preferences_update_invalid_board():
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(board="invalid_board")
