from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import asin, atan2, cos, degrees, radians, sin, sqrt

from .models import Coordinate

EARTH_RADIUS_M = 6_371_008.8


def haversine_m(a: Coordinate, b: Coordinate) -> float:
    lat1, lat2 = radians(a.latitude), radians(b.latitude)
    dlat = lat2 - lat1
    dlon = radians(b.longitude - a.longitude)
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(min(1.0, sqrt(value)))


def bearing_degrees(a: Coordinate, b: Coordinate) -> float:
    lat1, lat2 = radians(a.latitude), radians(b.latitude)
    dlon = radians(b.longitude - a.longitude)
    y = sin(dlon) * cos(lat2)
    x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    return (degrees(atan2(y, x)) + 360) % 360


def turn_modifier(previous: float, current: float) -> str:
    delta = (current - previous + 540) % 360 - 180
    magnitude = abs(delta)
    if magnitude < 20:
        return "straight"
    if magnitude < 55:
        return "slight_right" if delta > 0 else "slight_left"
    if magnitude < 135:
        return "right" if delta > 0 else "left"
    return "uturn"


def bbox(points: Sequence[Coordinate]) -> tuple[float, float, float, float]:
    return (
        min(point.longitude for point in points),
        min(point.latitude for point in points),
        max(point.longitude for point in points),
        max(point.latitude for point in points),
    )


def encode_polyline(points: Iterable[Coordinate], precision: int = 6) -> str:
    factor = 10**precision
    previous_lat = previous_lon = 0
    encoded: list[str] = []
    for point in points:
        lat = round(point.latitude * factor)
        lon = round(point.longitude * factor)
        for value in (lat - previous_lat, lon - previous_lon):
            value = ~(value << 1) if value < 0 else value << 1
            while value >= 0x20:
                encoded.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            encoded.append(chr(value + 63))
        previous_lat, previous_lon = lat, lon
    return "".join(encoded)


def decode_polyline(value: str, precision: int = 6) -> list[Coordinate]:
    factor = 10**precision
    coordinates: list[Coordinate] = []
    index = latitude = longitude = 0
    while index < len(value):
        deltas: list[int] = []
        for _ in range(2):
            result = shift = 0
            while True:
                byte = ord(value[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        latitude += deltas[0]
        longitude += deltas[1]
        coordinates.append(Coordinate(latitude=latitude / factor, longitude=longitude / factor))
    return coordinates


def nearest_point_index(point: Coordinate, geometry: Sequence[Coordinate]) -> tuple[int, float]:
    best_index = 0
    best_distance = float("inf")
    for index, candidate in enumerate(geometry):
        distance = haversine_m(point, candidate)
        if distance < best_distance:
            best_index, best_distance = index, distance
    return best_index, best_distance
