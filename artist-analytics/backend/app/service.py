"""Builds the per-artist fact sheet used by the dashboard, Claude and the worker."""

from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analytics.trends import HEADLINE, TOTAL_METRICS, artist_summary, build_series
from .config import get_settings
from .ml.forecast import forecast
from .models import PlaylistStat, TrackStat
from .store import load_events, load_snapshots


def artist_data(db: Session, artist_id: int) -> tuple[dict, pd.DataFrame]:
    snap = load_snapshots(db, artist_id)
    events = load_events(db, artist_id)
    return build_series(snap), events


def facts(db: Session, artist_id: int) -> dict:
    snap = load_snapshots(db, artist_id)
    events = load_events(db, artist_id)
    return artist_summary(snap, events, date.today(), get_settings().stale_after_days)


def extras(db: Session, artist_id: int) -> dict:
    """Song/playlist tables and 28-day headline forecasts, for Claude's context."""
    songs = db.scalars(select(TrackStat).where(TrackStat.artist_id == artist_id)).all()
    pls = db.scalars(select(PlaylistStat).where(PlaylistStat.artist_id == artist_id)).all()
    top_songs = sorted(songs, key=lambda t: -(t.stats.get("streams") or 0))[:10]
    top_pls = sorted(pls, key=lambda p: -(p.stats.get("streams") or 0))[:10]
    series, events = artist_data(db, artist_id)
    fc = {}
    for platform, metric in HEADLINE.items():
        s = series.get((platform, metric))
        if s is None or s.dropna().empty or metric in TOTAL_METRICS:
            continue
        f = forecast(s, events, platform, metric, horizon=28)
        if f is not None:
            fc[f"{platform}:{metric}"] = {
                "method": f.method,
                "from": f.days[0].date().isoformat(),
                "next_28d_total": round(float(f.mean.sum())),
                "last_28d_total": round(float(s.dropna().iloc[-28:].sum())),
                "band_80pct": [round(float(f.low.sum())), round(float(f.high.sum()))],
            }
    return {
        "top_songs": [{"platform": t.platform, "song": t.song, **t.stats} for t in top_songs],
        "top_playlists": [{"platform": p.platform, "playlist": p.playlist, "curator": p.curator, "date_added": p.date_added.isoformat() if p.date_added else None, **p.stats} for p in top_pls],
        "forecasts_28d": fc,
    }
