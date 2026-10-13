"""Glue between connectors and the database. Used by the API and the daily worker."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .connectors import apple_music, spotify, youtube
from .connectors.csv_import import ParsedCSV
from .models import Artist, Connection, Event, PlaylistStat, TrackStat, Upload
from .store import add_event_if_new, upsert_snapshots

log = logging.getLogger(__name__)


def refresh_profile(db: Session, artist: Artist) -> dict:
    """Pull name/genres/image and release dates from whichever APIs are configured.

    Returns {"releases_added": n, "errors": [...]} — failures on one platform
    never block the others.
    """
    added, errors = 0, []

    def _releases(items: list[dict], platform_label: str) -> int:
        n = 0
        for rel in items:
            try:
                day = date.fromisoformat(rel["day"])
            except ValueError:
                continue
            n += add_event_if_new(
                db,
                artist.id,
                day=day,
                kind="release",
                platform=None,  # a release moves every platform
                magnitude=2.0 if rel.get("type") == "album" else 1.0,
                title=rel.get("title"),
                source=platform_label,
                external_id=rel["external_id"],
            )
        return n

    if artist.spotify_id and spotify.enabled():
        try:
            prof = spotify.artist_profile(artist.spotify_id)
            artist.name = artist.name or prof["name"]
            artist.genres = prof["genres"] or artist.genres
            artist.image_url = prof["image_url"] or artist.image_url
            added += _releases(spotify.releases(artist.spotify_id), "spotify")
        except Exception as e:  # noqa: BLE001
            errors.append(f"spotify: {e}")

    if artist.apple_music_id and apple_music.enabled():
        try:
            prof = apple_music.artist_profile(artist.apple_music_id)
            artist.genres = artist.genres or prof["genres"]
            artist.image_url = artist.image_url or prof["image_url"]
            # Same release usually exists on both; skip Apple ones that match a Spotify title+day.
            existing = {(e.title or "").lower() + str(e.day) for e in artist.events if e.kind == "release"}
            rels = [r for r in apple_music.releases(artist.apple_music_id) if (r["title"] or "").lower() + r["day"] not in existing]
            added += _releases(rels, "apple_music")
        except Exception as e:  # noqa: BLE001
            errors.append(f"apple_music: {e}")

    db.commit()
    return {"releases_added": added, "errors": errors}


def snapshot_youtube(db: Session, artist: Artist, backfill: bool = False) -> dict:
    rows: list[dict] = []
    errors: list[str] = []
    today = date.today()

    if artist.youtube_channel_id and youtube.api_key_enabled():
        try:
            st = youtube.channel_stats(artist.youtube_channel_id)
            if st.get("subscribers") is not None:
                rows.append(dict(artist_id=artist.id, platform="youtube", metric="subscribers", day=today, value=st["subscribers"], kind="total", source="api"))
            if st.get("lifetime_views") is not None:
                rows.append(dict(artist_id=artist.id, platform="youtube", metric="lifetime_views", day=today, value=st["lifetime_views"], kind="total", source="api"))
            if not artist.image_url:
                artist.image_url = st.get("image_url")
        except Exception as e:  # noqa: BLE001
            errors.append(f"youtube data api: {e}")

    conn = db.scalar(select(Connection).where(Connection.artist_id == artist.id, Connection.provider == "youtube"))
    if conn and youtube.oauth_enabled():
        try:
            start, end = youtube.backfill_window() if backfill else (today - timedelta(days=10), today - timedelta(days=2))
            for r in youtube.daily_analytics(conn.refresh_token, start, end):
                rows.append(dict(artist_id=artist.id, platform="youtube", metric=r["metric"], day=r["day"], value=r["value"], kind="daily", source="api"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"youtube analytics: {e}")

    n = upsert_snapshots(db, rows)
    return {"rows": n, "errors": errors}


def import_parsed_csv(db: Session, artist: Artist, parsed: ParsedCSV, filename: str | None) -> dict:
    platform = parsed.platform
    if platform not in ("spotify", "apple_music"):
        raise ValueError("Pick which platform this export is from.")
    rows = 0
    first = last = None

    if parsed.file_type == "timeline" and parsed.timeline is not None:
        t = parsed.timeline
        recs = [
            dict(artist_id=artist.id, platform=platform, metric=r.metric, day=r.day.date(), value=float(r.value), kind=r.kind, source="csv")
            for r in t.itertuples()
        ]
        rows = upsert_snapshots(db, recs)
        first, last = t["day"].min().date(), t["day"].max().date()

    elif parsed.file_type == "songs" and parsed.songs is not None:
        db.query(TrackStat).filter(TrackStat.artist_id == artist.id, TrackStat.platform == platform).delete()
        for r in parsed.songs.to_dict("records"):
            song = r.pop("song")
            r.pop("isrc", None)
            db.add(TrackStat(artist_id=artist.id, platform=platform, song=song, stats={k: (None if pd.isna(v) else float(v)) for k, v in r.items()}))
            rows += 1

    elif parsed.file_type == "playlists" and parsed.playlists is not None:
        db.query(PlaylistStat).filter(PlaylistStat.artist_id == artist.id, PlaylistStat.platform == platform).delete()
        for r in parsed.playlists.to_dict("records"):
            added = r.pop("date_added", None)
            added = added.date() if isinstance(added, pd.Timestamp) and not pd.isna(added) else None
            name, curator = r.pop("playlist"), r.pop("curator", None)
            stats = {k: (None if pd.isna(v) else float(v)) for k, v in r.items()}
            db.add(PlaylistStat(artist_id=artist.id, platform=platform, playlist=name, curator=curator, date_added=added, stats=stats))
            rows += 1
            # A playlist add is a "circumstance" the models should know about.
            if added:
                streams = stats.get("streams") or 0
                add_event_if_new(
                    db,
                    artist.id,
                    day=added,
                    kind="playlist",
                    platform=platform,
                    magnitude=2.0 if streams > 10000 else 1.0,
                    title=f"Added to {name}" + (f" ({curator})" if curator else ""),
                    source="csv",
                    external_id=f"{platform}:playlist:{name}"[:100],
                )
    else:
        raise ValueError("Unrecognized file; nothing imported.")

    db.add(Upload(artist_id=artist.id, platform=platform, file_type=parsed.file_type, filename=filename, rows=rows, first_day=first, last_day=last))
    db.commit()
    return {"imported_rows": rows, "file_type": parsed.file_type, "platform": platform}


def known_release_titles(db: Session, artist_id: int) -> list[str]:
    return [t for (t,) in db.execute(select(Event.title).where(Event.artist_id == artist_id, Event.kind == "release")) if t]
