"""YouTube — the one platform where artists can actually link their account.

* Data API (API key): public subscriber and lifetime view totals for any channel.
* Analytics API (OAuth, per artist): daily views, watch time, likes and
  subscribers gained/lost for channels the artist owns. YouTube Music plays
  of the artist's uploads show up here too; there is no separate YT Music API.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from datetime import date, timedelta
from urllib.parse import urlencode

import httpx

from ..config import get_settings

DATA_API = "https://www.googleapis.com/youtube/v3"
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"
SCOPES = "https://www.googleapis.com/auth/yt-analytics.readonly https://www.googleapis.com/auth/youtube.readonly"

# YouTube Analytics column -> our metric name (all daily counts)
ANALYTICS_METRICS = {
    "views": "views",
    "estimatedMinutesWatched": "watch_minutes",
    "likes": "likes",
    "subscribersGained": "subs_gained",
    "subscribersLost": "subs_lost",
}


def api_key_enabled() -> bool:
    return bool(get_settings().youtube_api_key)


def oauth_enabled() -> bool:
    s = get_settings()
    return bool(s.youtube_oauth_client_id and s.youtube_oauth_client_secret)


# ---------- public Data API ----------

def resolve_channel(link_or_id: str) -> str | None:
    """Accepts a channel URL, /@handle URL, bare @handle or UC... id."""
    s = link_or_id.strip()
    m = re.search(r"(UC[A-Za-z0-9_-]{22})", s)
    if m:
        return m.group(1)
    m = re.search(r"@([A-Za-z0-9._-]+)", s)
    if m and api_key_enabled():
        r = httpx.get(f"{DATA_API}/channels", params={"part": "id", "forHandle": "@" + m.group(1), "key": get_settings().youtube_api_key}, timeout=20)
        r.raise_for_status()
        items = r.json().get("items") or []
        return items[0]["id"] if items else None
    return None


def channel_stats(channel_id: str) -> dict:
    r = httpx.get(
        f"{DATA_API}/channels",
        params={"part": "snippet,statistics", "id": channel_id, "key": get_settings().youtube_api_key},
        timeout=20,
    )
    r.raise_for_status()
    items = r.json().get("items") or []
    if not items:
        return {}
    st, sn = items[0]["statistics"], items[0]["snippet"]
    return {
        "name": sn.get("title"),
        "image_url": (sn.get("thumbnails", {}).get("high") or {}).get("url"),
        # hiddenSubscriberCount channels report no subscriberCount
        "subscribers": float(st["subscriberCount"]) if "subscriberCount" in st else None,
        "lifetime_views": float(st.get("viewCount", 0)),
    }


# ---------- OAuth ----------

def _sign(payload: dict) -> str:
    secret = get_settings().youtube_oauth_client_secret.encode()
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(secret, raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{sig}"


def verify_state(state: str) -> dict | None:
    try:
        raw, sig = state.rsplit(".", 1)
    except ValueError:
        return None
    secret = get_settings().youtube_oauth_client_secret.encode()
    good = hmac.new(secret, raw.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, good):
        return None
    return json.loads(base64.urlsafe_b64decode(raw.encode()))


def redirect_uri() -> str:
    return f"{get_settings().public_api_url}/api/auth/youtube/callback"


def authorize_url(artist_id: int) -> str:
    s = get_settings()
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": s.youtube_oauth_client_id,
            "redirect_uri": redirect_uri(),
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",  # always returns a refresh token
            "state": _sign({"artist_id": artist_id}),
        }
    )


def exchange_code(code: str) -> dict:
    s = get_settings()
    r = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": s.youtube_oauth_client_id,
            "client_secret": s.youtube_oauth_client_secret,
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def access_token(refresh_token: str) -> str:
    s = get_settings()
    r = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "refresh_token": refresh_token,
            "client_id": s.youtube_oauth_client_id,
            "client_secret": s.youtube_oauth_client_secret,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def my_channel(token: str) -> dict:
    r = httpx.get(f"{DATA_API}/channels", params={"part": "snippet", "mine": "true"}, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    r.raise_for_status()
    items = r.json().get("items") or []
    if not items:
        return {}
    return {"id": items[0]["id"], "name": items[0]["snippet"]["title"]}


def daily_analytics(refresh_token: str, start: date, end: date) -> list[dict]:
    """Rows of {day, metric, value} for the authorized channel."""
    token = access_token(refresh_token)
    r = httpx.get(
        ANALYTICS_API,
        params={
            "ids": "channel==MINE",
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "metrics": ",".join(ANALYTICS_METRICS),
            "dimensions": "day",
            "sort": "day",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    r.raise_for_status()
    body = r.json()
    headers = [h["name"] for h in body.get("columnHeaders", [])]
    out = []
    for row in body.get("rows") or []:
        rec = dict(zip(headers, row))
        for col, metric in ANALYTICS_METRICS.items():
            if col in rec:
                out.append({"day": date.fromisoformat(rec["day"]), "metric": metric, "value": float(rec[col])})
    return out


def backfill_window(years: int = 3) -> tuple[date, date]:
    end = date.today() - timedelta(days=2)  # analytics lag ~48h
    return end - timedelta(days=365 * years), end
