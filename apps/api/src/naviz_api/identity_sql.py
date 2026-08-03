from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .models import Favorite, HistoryEntry, Place, TravelMode, UserPreferences


class Base(DeclarativeBase):
    pass


class FavoriteRow(Base):
    __tablename__ = "naviz_favorites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), index=True)
    label: Mapped[str] = mapped_column(String(120))
    place: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PreferenceRow(Base):
    __tablename__ = "naviz_preferences"

    subject: Mapped[str] = mapped_column(String(255), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HistoryRow(Base):
    __tablename__ = "naviz_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), index=True)
    origin_label: Mapped[str] = mapped_column(String(200))
    destination: Mapped[dict[str, Any]] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SqlAlchemyIdentityRepository:
    """Neon/PostgreSQL adapter; coordinates and GPS fixes never enter these tables."""

    def __init__(self, database_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(
            _async_database_url(database_url),
            pool_pre_ping=True,
            pool_recycle=300,
        )
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    async def initialize(self) -> None:
        # Keeps the zero-ops beta deployable. Alembic owns controlled schema changes.
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()

    async def favorites(self, subject: str) -> list[Favorite]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(FavoriteRow)
                    .where(FavoriteRow.subject == subject)
                    .order_by(FavoriteRow.created_at.desc())
                )
            ).all()
        return [_favorite(row) for row in rows]

    async def save_favorite(self, subject: str, label: str, place: Place) -> Favorite:
        row = FavoriteRow(
            id=str(uuid4()),
            subject=subject,
            label=label,
            place=place.model_dump(mode="json"),
            created_at=datetime.now(UTC),
        )
        async with self._sessions() as session:
            session.add(row)
            await session.commit()
        return _favorite(row)

    async def delete_favorite(self, subject: str, favorite_id: str) -> None:
        async with self._sessions() as session:
            await session.execute(
                delete(FavoriteRow).where(
                    FavoriteRow.subject == subject,
                    FavoriteRow.id == favorite_id,
                )
            )
            await session.commit()

    async def preferences(self, subject: str) -> UserPreferences:
        async with self._sessions() as session:
            row = await session.get(PreferenceRow, subject)
        return UserPreferences.model_validate(row.payload) if row else UserPreferences()

    async def save_preferences(
        self, subject: str, preferences: UserPreferences
    ) -> UserPreferences:
        async with self._sessions() as session:
            row = await session.get(PreferenceRow, subject)
            if row is None:
                row = PreferenceRow(subject=subject, payload={}, updated_at=datetime.now(UTC))
                session.add(row)
            row.payload = preferences.model_dump(mode="json")
            row.updated_at = datetime.now(UTC)
            await session.commit()
        return preferences

    async def history(self, subject: str) -> list[HistoryEntry]:
        now = datetime.now(UTC)
        async with self._sessions() as session:
            await session.execute(
                delete(HistoryRow).where(
                    HistoryRow.subject == subject,
                    HistoryRow.expires_at <= now,
                )
            )
            rows = (
                await session.scalars(
                    select(HistoryRow)
                    .where(HistoryRow.subject == subject, HistoryRow.expires_at > now)
                    .order_by(HistoryRow.created_at.desc())
                    .limit(200)
                )
            ).all()
            await session.commit()
        return [_history(row) for row in rows]

    async def add_history(
        self, subject: str, origin_label: str, destination: Place, mode: TravelMode
    ) -> HistoryEntry | None:
        if not (await self.preferences(subject)).history_enabled:
            return None
        now = datetime.now(UTC)
        row = HistoryRow(
            id=str(uuid4()),
            subject=subject,
            origin_label=origin_label,
            destination=destination.model_dump(mode="json"),
            mode=mode.value,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
        async with self._sessions() as session:
            session.add(row)
            await session.commit()
        return _history(row)


def _favorite(row: FavoriteRow) -> Favorite:
    return Favorite(
        id=row.id,
        label=row.label,
        place=Place.model_validate(row.place),
        created_at=row.created_at,
    )


def _history(row: HistoryRow) -> HistoryEntry:
    return HistoryEntry(
        id=row.id,
        origin_label=row.origin_label,
        destination=Place.model_validate(row.destination),
        mode=TravelMode(row.mode),
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


def _async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return database_url
