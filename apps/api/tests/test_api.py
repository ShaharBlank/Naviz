from fastapi.testclient import TestClient
from naviz_api.main import app


def test_health_and_data_status() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        status = client.get("/v1/data/status")
        assert status.status_code == 200
        payload = status.json()
        assert payload["engine_profile"] == "compact"
        assert payload["coverage"] == "Tel Aviv-Yafo test fixture"
        assert payload["service_coverage_bbox"] == [34.15, 29.35, 35.95, 33.4]
        assert payload["feature_coverage_bbox"] is None
        assert payload["capabilities"]["street_routing"]["available"]


def test_search_and_route_vertical_slice() -> None:
    with TestClient(app) as client:
        search = client.get("/v1/search", params={"q": "Hab"})
        assert search.status_code == 200
        route = client.post(
            "/v1/routes/plan",
            json={
                "origin": {"latitude": 32.0733, "longitude": 34.7799},
                "destination": {"latitude": 32.0791, "longitude": 34.7682},
                "depart_at": "2026-08-02T13:00:00+03:00",
                "mode": "walk",
                "preference": "balanced_shade",
                "locale": "he",
            },
        )
        assert route.status_code == 200, route.text
        assert route.json()["routes"][0]["encoded_polyline"]
        assert route.headers["X-Request-ID"] == route.json()["request_id"]


def test_invalid_request_uses_problem_details() -> None:
    with TestClient(app) as client:
        response = client.post("/v1/routes/plan", json={})
        assert response.status_code == 422
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == "validation_error"


def test_road_route_exposes_a_total_traffic_light_count() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/routes/plan",
            json={
                "origin": {"latitude": 32.0733, "longitude": 34.7799},
                "destination": {"latitude": 32.0832, "longitude": 34.7957},
                "depart_at": "2026-08-02T09:00:00+03:00",
                "mode": "car",
                "preference": "fastest",
                "include_comparisons": True,
            },
        )

        assert response.status_code == 200, response.text
        routes = response.json()["routes"]
        assert routes[0]["label_key"] == "route.fastest"
        assert isinstance(routes[0]["metrics"]["traffic_signals"], int)
        assert routes[0]["metrics"]["traffic_signals"] >= 0


def test_compact_profile_reports_shadow_scene_as_unavailable() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/shadows/scene",
            json={
                "encoded_polyline": "_p~iF~ps|U_ulLnnqC",
                "at": "2026-08-17T12:00:00+03:00",
                "corridor_m": 180,
            },
        )

        assert response.status_code == 200
        assert response.json()["available"] is False
        assert response.json()["model_version"] == "unavailable"


def test_demo_account_sync_requires_explicit_token() -> None:
    with TestClient(app) as client:
        assert client.get("/v1/me/favorites").status_code == 401
        assert (
            client.get(
                "/v1/me/favorites", headers={"Authorization": "Bearer demo-user"}
            ).status_code
            == 200
        )
