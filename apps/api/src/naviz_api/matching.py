from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from math import exp

from .geometry import bearing_degrees, haversine_m
from .models import Coordinate


@dataclass(frozen=True, slots=True)
class LocationFix:
    coordinate: Coordinate
    accuracy_m: float
    heading_degrees: float | None = None
    speed_mps: float | None = None


@dataclass(frozen=True, slots=True)
class MatchResult:
    geometry_index: int
    coordinate: Coordinate
    distance_m: float
    confidence: float
    off_route: bool


class RouteMatcher:
    """A bounded HMM/Viterbi matcher over a route corridor."""

    def __init__(self, route: Sequence[Coordinate]) -> None:
        if len(route) < 2:
            raise ValueError("A route matcher needs at least two geometry points")
        self._route = tuple(route)
        self._progress = _cumulative_distances(self._route)
        self._last_index = 0
        self._off_route_streak = 0

    def update(self, fixes: Sequence[LocationFix]) -> MatchResult:
        if not fixes:
            raise ValueError("At least one location fix is required")
        candidates = self._candidate_indices(fixes[-1])
        best_index, best_log_probability = self._viterbi(fixes, candidates)
        fix = fixes[-1]
        distance = haversine_m(fix.coordinate, self._route[best_index])
        threshold = max(30.0, fix.accuracy_m * 1.8)
        if distance > threshold:
            self._off_route_streak += 1
        else:
            self._off_route_streak = 0
            self._last_index = max(self._last_index, best_index)
        confidence = max(0.0, min(1.0, exp(best_log_probability / max(1, len(fixes)))))
        return MatchResult(
            geometry_index=best_index,
            coordinate=self._route[best_index],
            distance_m=distance,
            confidence=confidence,
            off_route=self._off_route_streak >= 3,
        )

    def _candidate_indices(self, fix: LocationFix) -> list[int]:
        start = max(0, self._last_index - 2)
        ranked = sorted(
            range(start, len(self._route)),
            key=lambda index: haversine_m(fix.coordinate, self._route[index]),
        )
        return ranked[: min(8, len(ranked))]

    def _viterbi(
        self, fixes: Sequence[LocationFix], candidates: Sequence[int]
    ) -> tuple[int, float]:
        scores: dict[int, float] = {}
        backtrack: dict[tuple[int, int], int] = {}
        first = fixes[0]
        for index in candidates:
            scores[index] = self._emission(first, index)
        for fix_index, fix in enumerate(fixes[1:], start=1):
            next_scores: dict[int, float] = {}
            for candidate in candidates:
                prior, score = max(
                    (
                        (prior_index, prior_score + self._transition(prior_index, candidate, fix))
                        for prior_index, prior_score in scores.items()
                    ),
                    key=lambda item: item[1],
                )
                next_scores[candidate] = score + self._emission(fix, candidate)
                backtrack[(fix_index, candidate)] = prior
            scores = next_scores
        return max(scores.items(), key=lambda item: item[1])

    def _emission(self, fix: LocationFix, index: int) -> float:
        sigma = max(5.0, fix.accuracy_m)
        distance = haversine_m(fix.coordinate, self._route[index])
        score = -(distance * distance) / (2 * sigma * sigma)
        if fix.heading_degrees is not None and index + 1 < len(self._route):
            route_heading = bearing_degrees(self._route[index], self._route[index + 1])
            delta = abs((fix.heading_degrees - route_heading + 180) % 360 - 180)
            score -= delta / 90
        return score

    def _transition(self, previous: int, current: int, fix: LocationFix) -> float:
        if current < previous - 1:
            return -12.0
        route_distance = abs(self._progress[current] - self._progress[previous])
        expected = max(0.0, fix.speed_mps or 0.0)
        return -abs(route_distance - expected) / 80


def _cumulative_distances(route: Sequence[Coordinate]) -> list[float]:
    distances = [0.0]
    for first, second in pairwise(route):
        distances.append(distances[-1] + haversine_m(first, second))
    return distances
