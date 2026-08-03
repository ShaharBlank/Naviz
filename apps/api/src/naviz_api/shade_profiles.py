from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from math import floor


@dataclass(frozen=True, slots=True)
class DirectionalHorizon:
    """Maximum obstruction elevation sampled uniformly over a 360° horizon."""

    elevation_degrees: tuple[float, ...]

    def obstruction_at(self, azimuth_degrees: float) -> float:
        if not self.elevation_degrees:
            return 0.0
        position = (azimuth_degrees % 360) / 360 * len(self.elevation_degrees)
        left = floor(position) % len(self.elevation_degrees)
        right = (left + 1) % len(self.elevation_degrees)
        ratio = position - floor(position)
        return (
            self.elevation_degrees[left] * (1 - ratio)
            + self.elevation_degrees[right] * ratio
        )

    def sun_visible(self, azimuth_degrees: float, elevation_degrees: float) -> bool:
        return elevation_degrees > 0 and elevation_degrees > self.obstruction_at(azimuth_degrees)


def interpolate_daily_bins(values: Sequence[float], at: datetime) -> float:
    """Circularly interpolate any uniform daily profile (production uses five-minute bins)."""
    if not values:
        return 0.0
    seconds = at.hour * 3_600 + at.minute * 60 + at.second + at.microsecond / 1_000_000
    position = seconds / 86_400 * len(values)
    left = floor(position) % len(values)
    right = (left + 1) % len(values)
    ratio = position - floor(position)
    return max(0.0, min(1.0, values[left] * (1 - ratio) + values[right] * ratio))
