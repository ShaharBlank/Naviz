import pytest
from naviz_api.mobility import MobilityService


@pytest.mark.asyncio
async def test_unconfigured_mobility_never_returns_fixture_vehicles() -> None:
    response = await MobilityService().nearby(
        minimum_latitude=32.0,
        minimum_longitude=34.7,
        maximum_latitude=32.2,
        maximum_longitude=34.9,
    )

    assert response.vehicles == []
    assert response.warnings == []
