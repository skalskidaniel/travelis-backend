import pytest
from datetime import date
from pydantic import ValidationError
from app.user.schemas import UserPreferencesUpdate
from core.models.user import UserPreferences
from core.models.common import BoardType


def test_user_preferences_update_valid():
    data = {
        "countries": ["GR", "DE"],
        "adults": 3,
        "board": ["all-inclusive", "half-board"],
    }
    update = UserPreferencesUpdate(**data)
    assert update.countries == ["GR", "DE"]
    assert update.adults == 3
    assert update.board == [BoardType.ALL_INCLUSIVE, BoardType.HALF_BOARD]


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
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(board=["invalid_board"])
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(board=[])


def test_user_preferences_update_invalid_country():
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(countries=["XX"])


def test_user_preferences_domain_invalid_country():
    with pytest.raises(ValidationError):
        UserPreferences(countries=["PL"])


def test_user_preferences_adults_limit():
    with pytest.raises(ValidationError):
        UserPreferences(adults=7)
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(adults=7)


def test_user_preferences_airport_validation():
    # valid
    update = UserPreferencesUpdate(departure_airports=["WAW", "KRK"])
    assert update.departure_airports == ["WAW", "KRK"]

    # invalid format
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(departure_airports=["waw"])
    with pytest.raises(ValidationError):
        UserPreferences(departure_airports=["WAXX"])

    # list length limit (max 17)
    with pytest.raises(ValidationError):
        UserPreferences(departure_airports=["WAW"] * 18)
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(departure_airports=["WAW"] * 18)


def test_user_preferences_date_range_validation():
    # invalid date range
    with pytest.raises(ValidationError):
        UserPreferences(date_from=date(2026, 8, 10), date_to=date(2026, 8, 5))
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(date_from=date(2026, 8, 10), date_to=date(2026, 8, 5))


def test_user_preferences_duration_range_validation():
    # invalid duration range
    with pytest.raises(ValidationError):
        UserPreferences(duration_min=7, duration_max=5)
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(duration_min=7, duration_max=5)


def test_user_preferences_countries_count_limit():
    with pytest.raises(ValidationError):
        UserPreferences(countries=["GR"] * 21)
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(countries=["GR"] * 21)


def test_user_preferences_children_count_limit():
    with pytest.raises(ValidationError):
        UserPreferences(children=[date(2020, 1, 1)] * 6)
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(children=[date(2020, 1, 1)] * 6)


def test_user_preferences_total_occupants_limit():
    # adults (6) + children (3) = 9 occupants total (max is 8)
    with pytest.raises(ValidationError):
        UserPreferences(adults=6, children=[date(2020, 1, 1)] * 3)
    with pytest.raises(ValidationError):
        UserPreferencesUpdate(adults=6, children=[date(2020, 1, 1)] * 3)
