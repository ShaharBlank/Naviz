from datetime import datetime
from zoneinfo import ZoneInfo

from naviz_api.engine_adapters import OpenTripPlannerAdapter, ValhallaAdapter
from naviz_api.geometry import encode_polyline
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
