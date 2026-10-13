"""YouTube OAuth: the "Connect YouTube" button in onboarding."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..connectors import youtube
from ..db import SessionLocal, get_db
from ..ingest import snapshot_youtube
from ..models import Artist, Connection

router = APIRouter(prefix="/api/auth/youtube", tags=["auth"])


@router.get("/start")
def start(artist_id: int):
    if not youtube.oauth_enabled():
        raise HTTPException(400, "YouTube OAuth isn't configured (set YOUTUBE_OAUTH_CLIENT_ID/SECRET).")
    return RedirectResponse(youtube.authorize_url(artist_id))


def _backfill(artist_id: int) -> None:
    with SessionLocal() as db:
        a = db.get(Artist, artist_id)
        if a:
            snapshot_youtube(db, a, backfill=True)


@router.get("/callback")
def callback(background: BackgroundTasks, code: str | None = None, state: str = "", error: str | None = None, db: Session = Depends(get_db)):
    front = get_settings().frontend_url
    payload = youtube.verify_state(state)
    if error or not code or not payload:
        return RedirectResponse(f"{front}/?youtube=error")
    artist_id = int(payload["artist_id"])
    tokens = youtube.exchange_code(code)
    refresh = tokens.get("refresh_token")
    if not refresh:
        return RedirectResponse(f"{front}/?artist={artist_id}&youtube=error")
    chan = youtube.my_channel(tokens["access_token"])

    conn = db.scalar(select(Connection).where(Connection.artist_id == artist_id, Connection.provider == "youtube"))
    if not conn:
        conn = Connection(artist_id=artist_id, provider="youtube", refresh_token=refresh)
        db.add(conn)
    conn.refresh_token = refresh
    conn.account_id, conn.account_name = chan.get("id"), chan.get("name")
    artist = db.get(Artist, artist_id)
    if artist and chan.get("id"):
        artist.youtube_channel_id = chan["id"]
    db.commit()
    background.add_task(_backfill, artist_id)  # up to 3 years of daily analytics
    return RedirectResponse(f"{front}/?artist={artist_id}&youtube=connected")
