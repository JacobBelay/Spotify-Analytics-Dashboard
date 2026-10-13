"""Apple Music catalog API (developer token).

The public Apple Music API only covers the catalog, so we use it for the artist
profile and release dates. Plays/listeners/Shazams come from Apple Music for
Artists CSV exports. (Apple's Music Analytics API has real play counts but is
limited to labels/distributors with an iTunes Connect content-provider account.)
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import httpx

from ..config import get_settings

_token: dict = {"value": None, "exp": 0.0}


def parse_artist_id(link_or_id: str) -> str | None:
    s = link_or_id.strip()
    m = re.search(r"music\.apple\.com/.*/artist/(?:[^/]+/)?(\d+)", s)
    if m:
        return m.group(1)
    return s if s.isdigit() else None


def for_artists_url() -> str:
    return "https://artists.apple.com/"


def enabled() -> bool:
    s = get_settings()
    return bool(s.apple_music_team_id and s.apple_music_key_id and s.apple_music_private_key_path)


def _developer_token() -> str:
    if _token["value"] and time.time() < _token["exp"] - 300:
        return _token["value"]
    import jwt  # pyjwt[crypto]

    s = get_settings()
    now = int(time.time())
    exp = now + 60 * 60 * 12
    key = Path(s.apple_music_private_key_path).read_text()
    tok = jwt.encode(
        {"iss": s.apple_music_team_id, "iat": now, "exp": exp},
        key,
        algorithm="ES256",
        headers={"kid": s.apple_music_key_id},
    )
    _token.update(value=tok, exp=exp)
    return tok


def _get(path: str, params: dict | None = None) -> dict:
    r = httpx.get(
        f"https://api.music.apple.com{path}",
        params=params,
        headers={"Authorization": f"Bearer {_developer_token()}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def artist_profile(artist_id: str) -> dict:
    sf = get_settings().apple_music_storefront
    data = _get(f"/v1/catalog/{sf}/artists/{artist_id}")["data"][0]["attributes"]
    art = (data.get("artwork") or {}).get("url")
    return {
        "name": data.get("name"),
        "genres": data.get("genreNames") or [],
        "image_url": art.replace("{w}", "400").replace("{h}", "400") if art else None,
    }


def releases(artist_id: str, max_items: int = 200) -> list[dict]:
    sf = get_settings().apple_music_storefront
    out: list[dict] = []
    path = f"/v1/catalog/{sf}/artists/{artist_id}/albums"
    params: dict | None = {"limit": 25}
    while path and len(out) < max_items:
        page = _get(path, params)
        for alb in page.get("data", []):
            a = alb.get("attributes", {})
            day = a.get("releaseDate", "")
            if len(day) != 10:
                continue
            out.append({"external_id": f"apple:{alb['id']}", "title": a.get("name"), "day": day, "type": "single" if a.get("isSingle") else "album"})
        path, params = page.get("next"), None
    return out
