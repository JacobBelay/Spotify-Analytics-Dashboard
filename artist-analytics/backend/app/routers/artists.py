from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..connectors import apple_music, spotify, youtube
from ..db import get_db
from ..ingest import refresh_profile, snapshot_youtube
from ..models import Artist, Event
from ..schemas import ArtistIn, ArtistOut, ConnectIn, EventIn, EventOut

router = APIRouter(prefix="/api/artists", tags=["artists"])


def get_artist(db: Session, artist_id: int) -> Artist:
    a = db.get(Artist, artist_id)
    if not a:
        raise HTTPException(404, "Artist not found")
    return a


@router.get("", response_model=list[ArtistOut])
def list_artists(db: Session = Depends(get_db)):
    return db.scalars(select(Artist).order_by(Artist.name)).all()


@router.post("/connect")
def connect(body: ConnectIn, db: Session = Depends(get_db)):
    """Onboarding step 1: paste profile links; we look up the artist and pull releases."""
    sp = spotify.parse_artist_id(body.spotify_url) if body.spotify_url else None
    am = apple_music.parse_artist_id(body.apple_music_url) if body.apple_music_url else None
    problems = []
    if body.spotify_url and not sp:
        problems.append("That Spotify link doesn't look like an artist link (open.spotify.com/artist/...).")
    if body.apple_music_url and not am:
        problems.append("That Apple Music link doesn't look like an artist link (music.apple.com/.../artist/...).")
    yt = None
    if body.youtube_url:
        try:
            yt = youtube.resolve_channel(body.youtube_url)
        except Exception as e:  # noqa: BLE001
            problems.append(f"Couldn't look up that YouTube channel: {e}")
        if not yt and not problems:
            problems.append("Couldn't find that YouTube channel. Paste the channel URL (youtube.com/channel/UC... or youtube.com/@handle).")
    if not (sp or am or yt or body.name):
        raise HTTPException(400, {"problems": problems or ["Paste at least one profile link."]})

    existing = None
    if sp:
        existing = db.scalar(select(Artist).where(Artist.spotify_id == sp))
    artist = existing or Artist(name=body.name or "", owned=True)
    artist.spotify_id = sp or artist.spotify_id
    artist.apple_music_id = am or artist.apple_music_id
    artist.youtube_channel_id = yt or artist.youtube_channel_id
    if not existing:
        db.add(artist)
    db.commit()

    prof = refresh_profile(db, artist)
    yt_res = snapshot_youtube(db, artist)
    if not artist.name and artist.youtube_channel_id and youtube.api_key_enabled():
        artist.name = youtube.channel_stats(artist.youtube_channel_id).get("name") or ""
    artist.name = artist.name or "Untitled artist"
    db.commit()
    return {
        "artist": ArtistOut.model_validate(artist),
        "releases_found": prof["releases_added"],
        "problems": problems + prof["errors"] + yt_res["errors"],
    }


@router.post("", response_model=ArtistOut)
def create_artist(body: ArtistIn, db: Session = Depends(get_db)):
    """Add an artist by IDs directly (e.g. a public artist to compare against)."""
    a = Artist(**body.model_dump())
    db.add(a)
    db.commit()
    return a


@router.get("/{artist_id}", response_model=ArtistOut)
def read_artist(artist_id: int, db: Session = Depends(get_db)):
    return get_artist(db, artist_id)


@router.delete("/{artist_id}")
def delete_artist(artist_id: int, db: Session = Depends(get_db)):
    db.delete(get_artist(db, artist_id))
    db.commit()
    return {"ok": True}


@router.post("/{artist_id}/refresh")
def refresh(artist_id: int, db: Session = Depends(get_db)):
    a = get_artist(db, artist_id)
    return {"profile": refresh_profile(db, a), "youtube": snapshot_youtube(db, a)}


@router.get("/{artist_id}/events", response_model=list[EventOut])
def list_events(artist_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(Event).where(Event.artist_id == artist_id).order_by(Event.day)).all()


@router.post("/{artist_id}/events", response_model=EventOut)
def add_event(artist_id: int, body: EventIn, db: Session = Depends(get_db)):
    """Log a real circumstance (promo push, tour, press) so trends and forecasts account for it."""
    get_artist(db, artist_id)
    ev = Event(artist_id=artist_id, source="manual", **body.model_dump())
    db.add(ev)
    db.commit()
    return ev


@router.delete("/{artist_id}/events/{event_id}")
def delete_event(artist_id: int, event_id: int, db: Session = Depends(get_db)):
    ev = db.get(Event, event_id)
    if not ev or ev.artist_id != artist_id:
        raise HTTPException(404)
    db.delete(ev)
    db.commit()
    return {"ok": True}
