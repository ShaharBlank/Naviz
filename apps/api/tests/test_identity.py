import asyncio
import json
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK
from naviz_api.demo_data import demo_places
from naviz_api.identity import InMemoryIdentityRepository, TokenVerifier
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


def test_token_verifier_accepts_cryptography_backed_rs256_jwk() -> None:
    asyncio.run(_token_verifier_accepts_cryptography_backed_rs256_jwk())


async def _token_verifier_accepts_cryptography_backed_rs256_jwk() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})

    class StaticTokenVerifier(TokenVerifier):
        async def _signing_key(self, key_id: str) -> PyJWK:
            assert key_id == "test-key"
            return PyJWK.from_dict(public_jwk)

    issuer = "https://accounts.example.test"
    token = jwt.encode(
        {
            "sub": "user-123",
            "iss": issuer,
            "aud": "naviz-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    principal = await StaticTokenVerifier(issuer, "naviz-api", development=False).verify(
        f"Bearer {token}"
    )
    assert principal.subject == "user-123"
