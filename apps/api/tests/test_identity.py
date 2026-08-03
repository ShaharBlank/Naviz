import asyncio

from naviz_api.demo_data import demo_places
from naviz_api.identity import InMemoryIdentityRepository
from naviz_api.models import TravelMode, UserPreferences


def test_history_is_opt_in() -> None:
    asyncio.run(_history_is_opt_in())


async def _history_is_opt_in() -> None:
    repository = InMemoryIdentityRepository()
    destination = demo_places()[0]
    assert (
        await repository.add_history("user", "Current location", destination, TravelMode.WALK)
        is None
    )
    await repository.save_preferences("user", UserPreferences(history_enabled=True))
    assert await repository.add_history("user", "Current location", destination, TravelMode.WALK)
    assert len(await repository.history("user")) == 1
