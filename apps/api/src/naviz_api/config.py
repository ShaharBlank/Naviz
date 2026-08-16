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
    transitous_url: str | None = None
    photon_url: str | None = None
    overpass_url: str | None = None
    provider_contact: str = "https://github.com/ShaharBlank/Naviz"
    live_providers: bool = False
    coverage_bbox: tuple[float, float, float, float] = (34.69, 31.94, 34.93, 32.20)
    route_ttl_seconds: int = 900
    provider_cache_seconds: int = 300
    gbfs_ttl_seconds: int = 30
    gbfs_stale_seconds: int = 120

    @field_validator("allowed_origins", "gbfs_feeds", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("coverage_bbox", mode="before")
    @classmethod
    def split_bbox(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(float(part.strip()) for part in value.split(","))
        return value

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
