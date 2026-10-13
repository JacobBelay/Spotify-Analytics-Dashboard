"""Postgres schema.

metric_snapshots is the core telemetry table: one row per
(artist, platform, metric, day). Everything else — trends, forecasts,
Claude's reports — is derived from it plus the events ("circumstances") table.
"""

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

PLATFORMS = ("spotify", "youtube", "apple_music")

# Metrics we know how to store. Not every platform has every metric.
METRICS = (
    "streams",       # spotify / apple (CSV export)
    "listeners",     # spotify / apple (CSV export)
    "followers",     # spotify (CSV export)
    "saves",         # spotify (CSV export)
    "playlist_adds", # spotify (CSV export)
    "shazams",       # apple (CSV export)
    "views",         # youtube
    "subscribers",   # youtube (running total, Data API)
    "lifetime_views",# youtube (running total, Data API; daily views derived from it)
    "subs_gained",   # youtube analytics
    "subs_lost",     # youtube analytics
    "watch_minutes", # youtube analytics (owned channels)
    "likes",         # youtube
    "radio_spins",   # apple (CSV export)
    "purchases",     # apple (CSV export)
)

# Kinds of "circumstances" the forecaster and Claude reason about.
EVENT_KINDS = ("release", "playlist", "promo", "tour", "viral", "press", "collab")


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    spotify_id: Mapped[str | None] = mapped_column(String(64))
    youtube_channel_id: Mapped[str | None] = mapped_column(String(64))
    apple_music_id: Mapped[str | None] = mapped_column(String(64))
    genres: Mapped[list | None] = mapped_column(JSON)
    image_url: Mapped[str | None] = mapped_column(Text)
    # True when you control the artist's accounts (OAuth + CSV exports available).
    owned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    snapshots: Mapped[list["MetricSnapshot"]] = relationship(back_populates="artist", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="artist", cascade="all, delete-orphan")


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (UniqueConstraint("artist_id", "platform", "metric", "day", name="uq_snapshot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(20))
    metric: Mapped[str] = mapped_column(String(30))
    day: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float)
    # "daily" = count for that day (streams, views gained); "total" = running total (subscribers).
    kind: Mapped[str] = mapped_column(String(10), default="daily")
    source: Mapped[str] = mapped_column(String(20), default="api")  # api | csv | seed

    artist: Mapped[Artist] = relationship(back_populates="snapshots")


class Event(Base):
    """Something that happened (or is planned) that can move the numbers."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(20))
    platform: Mapped[str | None] = mapped_column(String(20))  # null = all platforms
    magnitude: Mapped[float] = mapped_column(Float, default=1.0)  # e.g. 2.0 = major playlist
    title: Mapped[str | None] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(20), default="manual")
    external_id: Mapped[str | None] = mapped_column(String(100))

    artist: Mapped[Artist] = relationship(back_populates="events")


class Insight(Base):
    """A saved Claude report so you can see how its read on trends changed over time."""

    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # report | scenario | question
    question: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON)
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    n_series: Mapped[int] = mapped_column(Integer)
    n_samples: Mapped[int] = mapped_column(Integer)
    val_mape: Mapped[float | None] = mapped_column(Float)
    baseline_mape: Mapped[float | None] = mapped_column(Float)
    path: Mapped[str] = mapped_column(Text)


class TrackStat(Base):
    """Per-song totals from a 'songs' CSV export (for a stated date range)."""

    __tablename__ = "track_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(20))
    song: Mapped[str] = mapped_column(String(300))
    stats: Mapped[dict] = mapped_column(JSON)  # {"streams": .., "listeners": .., "saves": ..}
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PlaylistStat(Base):
    """Per-playlist totals from a 'playlists' CSV export."""

    __tablename__ = "playlist_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(20))
    playlist: Mapped[str] = mapped_column(String(300))
    curator: Mapped[str | None] = mapped_column(String(200))
    date_added: Mapped[date | None] = mapped_column(Date)
    stats: Mapped[dict] = mapped_column(JSON)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Connection(Base):
    """An OAuth link an artist made (currently YouTube only; Spotify/Apple have no artist OAuth)."""

    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("artist_id", "provider", name="uq_connection"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    # NOTE: encrypt at rest before production (e.g. pgcrypto or a KMS-wrapped key).
    refresh_token: Mapped[str] = mapped_column(Text)
    account_id: Mapped[str | None] = mapped_column(String(100))  # e.g. YouTube channel id
    account_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Upload(Base):
    """Log of every CSV import, used for 'your data is N days old' reminders."""

    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artists.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(20))
    file_type: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str | None] = mapped_column(String(300))
    rows: Mapped[int] = mapped_column(Integer)
    first_day: Mapped[date | None] = mapped_column(Date)
    last_day: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
