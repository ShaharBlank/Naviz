from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NAVIZ_",
        env_file=".env",
        extra="ignore",
        enable_decoding=False,
    )

    env: str = "development"
    data_bundle: str = "demo-2026-08-02"
    database_url: str | None = None
    auth_issuer: str | None = None
    auth_audience: str = "naviz-api"
    allowed_origins: tuple[str, ...] = (
        "http://localhost:8081",
        "http://localhost:19006",
    )
    gbfs_feeds: tuple[str, ...] = ()
    valhalla_url: str | None = None
    otp_url: str | None = None
    route_ttl_seconds: int = 900
    gbfs_ttl_seconds: int = 30
    gbfs_stale_seconds: int = 120

    @field_validator("allowed_origins", "gbfs_feeds", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
