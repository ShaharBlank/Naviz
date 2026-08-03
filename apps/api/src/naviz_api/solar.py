from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from astral import Observer
from astral.sun import azimuth, elevation


@dataclass(frozen=True, slots=True)
class SolarPosition:
    azimuth_degrees: float
    elevation_degrees: float


def solar_position(when: datetime, latitude: float, longitude: float) -> SolarPosition:
    """Ported from ShadoWalk for offline shade-profile preprocessing; no network call."""
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("Solar calculations require a timezone-aware datetime")
    observer = Observer(latitude=latitude, longitude=longitude)
    return SolarPosition(
        azimuth_degrees=float(azimuth(observer, when)),
        elevation_degrees=float(elevation(observer, when)),
    )
