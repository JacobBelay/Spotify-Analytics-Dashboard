"""Data access helpers shared by routers, jobs and analytics."""

from collections.abc import Iterable
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Event, MetricSnapshot


def upsert_snapshots(db: Session, rows: Iterable[dict]) -> int:
    """Insert or update snapshot rows keyed on (artist, platform, metric, day).

    Each row: artist_id, platform, metric, day, value, [kind], [source].
    """
    rows = list(rows)
    if not rows:
        return 0
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:  # sqlite, handy for tests
        from sqlalchemy.dialects.sqlite import insert

    for i in range(0, len(rows), 1000):
        chunk = rows[i : i + 1000]
        stmt = insert(MetricSnapshot).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["artist_id", "platform", "metric", "day"],
            set_={"value": stmt.excluded.value, "source": stmt.excluded.source, "kind": stmt.excluded.kind},
        )
        db.execute(stmt)
    db.commit()
    return len(rows)


def add_event_if_new(db: Session, artist_id: int, **fields) -> bool:
    ext = fields.get("external_id")
    if ext:
        exists = db.scalar(select(Event.id).where(Event.artist_id == artist_id, Event.external_id == ext))
        if exists:
            return False
    db.add(Event(artist_id=artist_id, **fields))
    return True


def load_snapshots(db: Session, artist_id: int | None = None, since: date | None = None) -> pd.DataFrame:
    q = select(
        MetricSnapshot.artist_id,
        MetricSnapshot.platform,
        MetricSnapshot.metric,
        MetricSnapshot.day,
        MetricSnapshot.value,
        MetricSnapshot.kind,
    )
    if artist_id is not None:
        q = q.where(MetricSnapshot.artist_id == artist_id)
    if since is not None:
        q = q.where(MetricSnapshot.day >= since)
    df = pd.DataFrame(db.execute(q).all(), columns=["artist_id", "platform", "metric", "day", "value", "kind"])
    if not df.empty:
        df["day"] = pd.to_datetime(df["day"])
    return df


def load_events(db: Session, artist_id: int | None = None) -> pd.DataFrame:
    q = select(Event.artist_id, Event.day, Event.kind, Event.platform, Event.magnitude, Event.title)
    if artist_id is not None:
        q = q.where(Event.artist_id == artist_id)
    df = pd.DataFrame(db.execute(q).all(), columns=["artist_id", "day", "kind", "platform", "magnitude", "title"])
    if not df.empty:
        df["day"] = pd.to_datetime(df["day"])
    return df
