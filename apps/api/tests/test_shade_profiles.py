from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from naviz_api.shade_profiles import DirectionalHorizon, interpolate_daily_bins


def test_horizon_visibility_interpolates_azimuth() -> None:
    horizon = DirectionalHorizon((10, 20, 30, 40))
    assert horizon.obstruction_at(45) == pytest.approx(15)
    assert horizon.sun_visible(45, 16)
    assert not horizon.sun_visible(45, 14)
    assert not horizon.sun_visible(45, -1)


def test_five_minute_bins_interpolate_at_predicted_arrival_time() -> None:
    values = [0.0] * 288
    values[144] = 1.0  # Noon.
    values[145] = 0.0
    at = datetime(2026, 8, 2, 12, 2, 30, tzinfo=ZoneInfo("Asia/Jerusalem"))
    assert interpolate_daily_bins(values, at) == pytest.approx(0.5)


def test_solar_position_requires_timezone_and_is_reasonable_for_tel_aviv() -> None:
    pytest.importorskip("astral")
    from naviz_api.solar import solar_position

    with pytest.raises(ValueError):
        solar_position(datetime(2026, 6, 8, 12, 0), 32.0853, 34.7818)
    position = solar_position(
        datetime(2026, 6, 8, 12, 0, tzinfo=ZoneInfo("Asia/Jerusalem")),
        32.0853,
        34.7818,
    )
    assert 0 <= position.azimuth_degrees <= 360
    assert position.elevation_degrees > 0
