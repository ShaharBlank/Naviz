from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from naviz_api.engine_adapters import OpenTripPlannerAdapter, TransitousAdapter, ValhallaAdapter
from naviz_api.geometry import encode_polyline, haversine_m
from naviz_api.models import (
    Coordinate,
    RoutePlanRequest,
    TravelMode,
    VehicleKind,
    VehicleProfile,
)

TZ = ZoneInfo("Asia/Jerusalem")
ORIGIN = Coordinate(latitude=32.0733, longitude=34.7799)
DESTINATION = Coordinate(latitude=32.0791, longitude=34.7682)


def test_valhalla_request_preserves_truck_dimensions() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        depart_at=datetime(2026, 8, 2, 9, 0, tzinfo=TZ),
        mode=TravelMode.TRUCK,
        vehicle=VehicleProfile(height_m=3.8, width_m=2.4, weight_t=18),
    )
    payload = ValhallaAdapter.request_payload(request)
    assert payload["costing"] == "truck"
    assert payload["costing_options"] == {
        "truck": {"height": 3.8, "width": 2.4, "weight": 18.0}
    }
    assert payload["date_time"] == {"type": 1, "value": "2026-08-02T09:00"}


def test_otp_drops_full_size_bike_trip_with_unknown_permission() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        depart_at=datetime(2026, 8, 2, 9, 0, tzinfo=TZ),
        mode=TravelMode.BIKE_TRANSIT,
        vehicle=VehicleProfile(kind=VehicleKind.FULL_SIZE_BIKE),
    )
    geometry = encode_polyline([ORIGIN, DESTINATION], precision=5)
    payload = {
        "plan": {
            "itineraries": [
                {
                    "startTime": 1_786_002_000_000,
                    "endTime": 1_786_003_800_000,
                    "legs": [
                        {
                            "mode": "BUS",
                            "distance": 3000,
                            "duration": 1800,
                            "legGeometry": {"points": geometry},
                            "from": {"name": "A"},
                            "to": {"name": "B"},
                        }
                    ],
                }
            ]
        }
    }
    assert OpenTripPlannerAdapter.normalize(payload, request) == []


def test_transitous_uses_bike_transport_rules_and_polyline6() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        depart_at=datetime(2026, 8, 2, 9, 0, tzinfo=TZ),
        mode=TravelMode.BIKE_TRANSIT,
        vehicle=VehicleProfile(kind=VehicleKind.FULL_SIZE_BIKE),
    )
    parameters = TransitousAdapter.request_parameters(request)
    assert parameters["preTransitModes"] == "BIKE"
    assert parameters["postTransitModes"] == "BIKE"
    assert parameters["requireBikeTransport"] == "true"

    geometry = encode_polyline([ORIGIN, DESTINATION], precision=6)
    payload = {
        "itineraries": [
            {
                "startTime": "2026-08-02T06:00:00Z",
                "endTime": "2026-08-02T06:20:00Z",
                "legs": [
                    {
                        "mode": "BUS",
                        "distance": 3_000,
                        "duration": 1_200,
                        "startTime": "2026-08-02T06:00:00Z",
                        "endTime": "2026-08-02T06:20:00Z",
                        "legGeometry": {"points": geometry},
                        "from": {"name": "A"},
                        "to": {"name": "B"},
                        "bikesAllowed": True,
                        "agencyName": "Dan",
                        "displayName": "82",
                        "headsign": "Ramat Gan_Terminal",
                    }
                ],
            }
        ]
    }
    itineraries = TransitousAdapter.normalize(payload, request)
    assert len(itineraries) == 1
    assert itineraries[0].legs[0].bicycle_permission == "ALLOWED_GTFS"
    assert itineraries[0].legs[0].geometry == (ORIGIN, DESTINATION)
    assert itineraries[0].legs[0].headsign == "Ramat Gan · Terminal"


def test_transitous_uses_second_precision_and_derives_missing_leg_distance() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        depart_at=datetime(2026, 8, 2, 9, 0, 0, 458_535, tzinfo=TZ),
        mode=TravelMode.TRANSIT,
    )
    assert TransitousAdapter.request_parameters(request)["time"] == "2026-08-02T09:00:00+03:00"
    geometry = encode_polyline([ORIGIN, DESTINATION], precision=6)
    payload = {
        "itineraries": [
            {
                "startTime": "2026-08-02T06:00:00Z",
                "endTime": "2026-08-02T06:10:00Z",
                "legs": [
                    {
                        "mode": "BUS",
                        "distance": 0,
                        "duration": 600,
                        "legGeometry": {"points": geometry},
                        "from": {"name": "A"},
                        "to": {"name": "B"},
                    }
                ],
            }
        ]
    }

    itinerary = TransitousAdapter.normalize(payload, request)[0]
    assert itinerary.legs[0].distance_m == pytest.approx(haversine_m(ORIGIN, DESTINATION))


def test_transitous_rejects_provider_itinerary_from_before_requested_time() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        depart_at=datetime(2026, 8, 2, 9, 0, tzinfo=TZ),
        mode=TravelMode.TRANSIT,
    )
    geometry = encode_polyline([ORIGIN, DESTINATION], precision=6)
    payload = {
        "itineraries": [
            {
                "startTime": "2026-08-01T06:00:00Z",
                "endTime": "2026-08-01T06:10:00Z",
                "legs": [
                    {
                        "mode": "BUS",
                        "distance": 1_000,
                        "duration": 600,
                        "legGeometry": {"points": geometry},
                        "from": {"name": "A"},
                        "to": {"name": "B"},
                    }
                ],
            }
        ]
    }

    assert TransitousAdapter.normalize(payload, request) == []


def test_transitous_rejects_explicitly_denied_personal_bike() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        mode=TravelMode.BIKE_TRANSIT,
        vehicle=VehicleProfile(kind=VehicleKind.FULL_SIZE_BIKE),
    )
    geometry = encode_polyline([ORIGIN, DESTINATION], precision=6)
    payload = {
        "itineraries": [
            {
                "startTime": "2026-08-02T06:00:00Z",
                "endTime": "2026-08-02T06:20:00Z",
                "legs": [
                    {
                        "mode": "BUS",
                        "distance": 3_000,
                        "duration": 1_200,
                        "legGeometry": {"points": geometry},
                        "from": {"name": "A"},
                        "to": {"name": "B"},
                        "bikesAllowed": False,
                    }
                ],
            }
        ]
    }
    assert TransitousAdapter.normalize(payload, request) == []


def test_transitous_rejects_unknown_full_size_bike_permission() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        mode=TravelMode.BIKE_TRANSIT,
        vehicle=VehicleProfile(kind=VehicleKind.FULL_SIZE_BIKE),
    )
    geometry = encode_polyline([ORIGIN, DESTINATION], precision=6)
    payload = {
        "itineraries": [
            {
                "startTime": "2026-08-02T06:00:00Z",
                "endTime": "2026-08-02T06:20:00Z",
                "legs": [
                    {
                        "mode": "BUS",
                        "distance": 3_000,
                        "duration": 1_200,
                        "legGeometry": {"points": geometry},
                        "from": {"name": "A"},
                        "to": {"name": "B"},
                    }
                ],
            }
        ]
    }
    assert TransitousAdapter.normalize(payload, request) == []


def test_transitous_applies_cited_folded_vehicle_policy() -> None:
    request = RoutePlanRequest(
        origin=ORIGIN,
        destination=DESTINATION,
        depart_at=datetime(2026, 8, 2, 9, 0, tzinfo=TZ),
        mode=TravelMode.BIKE_TRANSIT,
        vehicle=VehicleProfile(kind=VehicleKind.FOLDING_BIKE, can_fold=True),
    )
    assert TransitousAdapter.request_parameters(request)["requireBikeTransport"] == "false"
    geometry = encode_polyline([ORIGIN, DESTINATION], precision=6)
    payload = {
        "itineraries": [
            {
                "startTime": "2026-08-02T06:00:00Z",
                "endTime": "2026-08-02T06:20:00Z",
                "legs": [
                    {
                        "mode": "BUS",
                        "distance": 3_000,
                        "duration": 1_200,
                        "legGeometry": {"points": geometry},
                        "from": {"name": "A"},
                        "to": {"name": "B"},
                    }
                ],
            }
        ]
    }
    itinerary = TransitousAdapter.normalize(payload, request)[0]
    assert itinerary.legs[0].bicycle_permission == "ALLOWED_FOLDED_POLICY"
