"""Guided onboarding: the checklist, the export instructions, and CSV upload."""

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..analytics.trends import build_series, freshness
from ..config import get_settings
from ..connectors import apple_music, spotify, youtube
from ..connectors.csv_import import parse_export, title_overlap
from ..db import get_db
from ..ingest import import_parsed_csv, known_release_titles
from ..models import Connection, Upload
from ..store import load_snapshots
from .artists import get_artist

router = APIRouter(prefix="/api/artists/{artist_id}", tags=["onboarding"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

# Shown in the side panel while the user is in the other tab. Menu names drift
# over time; keep these short and update them if Spotify/Apple rename things.
SPOTIFY_STEPS = [
    {"title": "Audience timeline (most important)", "steps": [
        "Open the Audience tab.",
        "Set the date range to 'Since 2015' the first time (after that, 'Last 28 days' is enough).",
        "Click the download icon next to the chart to save the CSV.",
    ]},
    {"title": "Songs (optional)", "steps": [
        "Open the Music tab, then Songs.",
        "Pick the date range and click the download icon.",
    ]},
    {"title": "Playlists (optional)", "steps": [
        "Open the Music tab, then Playlists.",
        "Click the download icon. Playlist add dates become events on your timeline.",
    ]},
]

APPLE_STEPS = [
    {"title": "Catalog data", "steps": [
        "Open the Music section and click 'See All'.",
        "Choose the full date range the first time.",
        "Download the CSV. Plays, listeners and Shazams are all picked up.",
    ]},
    {"title": "Heads-up", "steps": ["Apple's numbers run about 2 days behind and use UTC dates."]},
]


@router.get("/onboarding")
def onboarding_status(artist_id: int, db: Session = Depends(get_db)):
    a = get_artist(db, artist_id)
    s = get_settings()
    series = build_series(load_snapshots(db, artist_id))
    fresh = freshness(series, date.today(), s.stale_after_days)
    yt_conn = db.scalar(select(Connection).where(Connection.artist_id == artist_id, Connection.provider == "youtube"))
    uploads = db.scalars(select(Upload).where(Upload.artist_id == artist_id).order_by(Upload.created_at.desc()).limit(10)).all()

    def has(platform: str, file_type: str = "timeline") -> bool:
        return any(u.platform == platform and u.file_type == file_type for u in uploads)

    steps = [
        {"id": "profile", "title": "Connect your artist profiles", "done": bool(a.spotify_id or a.apple_music_id or a.youtube_channel_id)},
        {
            "id": "spotify",
            "title": "Upload your Spotify for Artists export",
            "done": has("spotify"),
            "open_url": spotify.for_artists_url(a.spotify_id),
            "instructions": SPOTIFY_STEPS,
            "freshness": fresh["spotify"],
        },
        {
            "id": "apple_music",
            "title": "Upload your Apple Music for Artists export",
            "done": has("apple_music"),
            "open_url": apple_music.for_artists_url(),
            "instructions": APPLE_STEPS,
            "freshness": fresh["apple_music"],
        },
        {
            "id": "youtube",
            "title": "Connect YouTube",
            "done": yt_conn is not None,
            "available": youtube.oauth_enabled(),
            "connect_url": f"/api/auth/youtube/start?artist_id={artist_id}" if youtube.oauth_enabled() else None,
            "account_name": yt_conn.account_name if yt_conn else None,
            "freshness": fresh["youtube"],
        },
    ]
    reminders = [
        {"platform": p, "days_old": f["days_old"], "message": f"Your {p.replace('_', ' ').title()} data is {f['days_old']} days old. Upload a fresh export to replace the estimates."}
        for p, f in fresh.items()
        if p != "youtube" and f["has_data"] and f["stale"]
    ]
    return {
        "artist_id": artist_id,
        "steps": steps,
        "complete": all(st["done"] for st in steps if st["id"] != "apple_music"),  # Apple is optional
        "reminders": reminders,
        "recent_uploads": [
            {"platform": u.platform, "file_type": u.file_type, "filename": u.filename, "rows": u.rows, "first_day": u.first_day, "last_day": u.last_day, "at": u.created_at}
            for u in uploads
        ],
    }


@router.post("/upload")
async def upload_csv(
    artist_id: int,
    file: UploadFile = File(...),
    platform: str | None = Form(None),
    dry_run: bool = Form(True),
    db: Session = Depends(get_db),
):
    """Drop a CSV. With dry_run=true (default) you get a preview; send again with dry_run=false to import."""
    a = get_artist(db, artist_id)
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 20 MB.")
    parsed = parse_export(raw, file.filename or "", platform)
    preview = parsed.summary()

    # Sanity check: do the songs in this file belong to this artist?
    if parsed.songs is not None:
        overlap = title_overlap(parsed.songs["song"].tolist(), known_release_titles(db, artist_id))
        preview["release_match"] = overlap
        if overlap is not None and overlap < 0.2:
            preview["warnings"].append(f"Few of these songs match {a.name}'s releases. Double-check this is the right artist's export.")

    if dry_run or parsed.file_type == "unknown":
        return {"preview": preview, "imported": False}
    try:
        result = import_parsed_csv(db, a, parsed, file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"preview": preview, "imported": True, **result}
