"""Spotify Web API (client credentials).

Since the February 2026 dev-mode changes, artist followers/popularity and
top-tracks are gone. What's still useful here: name, genres, image and the
release list, which we turn into "release" events for the trend models.
Streams/listeners/followers come from Spotify for Artists CSV exports instead.
"""

from __future__ import annotations

import re
import time

import httpx

from ..config import get_settings

_token: dict = {"value": None, "exp": 0.0}


def parse_artist_id(link_or_id: str) -> str | None:
    s = link_or_id.strip()
    m = re.search(r"artist[/:]([A-Za-z0-9]{22})", s)
    if m:
        return m.group(1)
    return s if re.fullmatch(r"[A-Za-z0-9]{22}", s) else None


def for_artists_url(artist_id: str | None) -> str:
    """Deep link into Spotify for Artists' Audience page for this artist.

    The /c/artist/<id>/ URL pattern is what Spotify for Artists uses today; if it
    changes, the site still redirects logged-in users from the root.
    """
    if artist_id:
        return f"https://artists.spotify.com/c/artist/{artist_id}/audience/stats"
    return "https://artists.spotify.com/"


def enabled() -> bool:
    s = get_settings()
    return bool(s.spotify_client_id and s.spotify_client_secret)


def _get_token() -> str:
    if _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    s = get_settings()
    r = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(s.spotify_client_id, s.spotify_client_secret),
        timeout=20,
    )
    r.raise_for_status()
    body = r.json()
    _token.update(value=body["access_token"], exp=time.time() + body["expires_in"])
    return _token["value"]


def _get(path: str, params: dict | None = None) -> dict:
    r = httpx.get(
        f"https://api.spotify.com/v1{path}",
        params=params,
        headers={"Authorization": f"Bearer {_get_token()}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def artist_profile(artist_id: str) -> dict:
    a = _get(f"/artists/{artist_id}")
    return {
        "name": a.get("name"),
        "genres": a.get("genres") or [],
        "image_url": (a.get("images") or [{}])[0].get("url"),
    }


def releases(artist_id: str, max_items: int = 200) -> list[dict]:
    """Albums and singles with release dates, newest first."""
    out: list[dict] = []
    params = {"include_groups": "album,single", "limit": 10}
    page = _get(f"/artists/{artist_id}/albums", params)
    while page and len(out) < max_items:
        for alb in page.get("items", []):
            day = alb.get("release_date", "")
            if alb.get("release_date_precision") != "day":
                continue  # year-only dates are too coarse to line up with daily data
            out.append({"external_id": f"spotify:{alb['id']}", "title": alb.get("name"), "day": day, "type": alb.get("album_type")})
        nxt = page.get("next")
        if not nxt:
            break
        r = httpx.get(nxt, headers={"Authorization": f"Bearer {_get_token()}"}, timeout=20)
        r.raise_for_status()
        page = r.json()
    return out
