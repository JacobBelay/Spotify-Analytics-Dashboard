"""Realistic synthetic telemetry for demos and tests (pure pandas/numpy).

Built so the analytics have something real to find: weekly seasonality,
release bumps that decay, playlist adds that step streams up, one viral spike,
and YouTube/Shazam activity that leads streaming by a few days.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd


def generate(days: int = 730, end: date | None = None, seed: int = 7, scale: float = 5000.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    end = end or date.today() - timedelta(days=3)
    idx = pd.date_range(end=pd.Timestamp(end), periods=days, freq="D")
    t = np.arange(days)

    events = []
    release_days = list(range(40, days - 20, 95))
    for i, d in enumerate(release_days):
        events.append({"day": idx[d], "kind": "release", "platform": None, "magnitude": 2.0 if i % 3 == 2 else 1.0, "title": f"{'Album' if i % 3 == 2 else 'Single'} {i + 1}"})
    playlist_days = [d + 9 for d in release_days[1::2]]
    for d in playlist_days:
        if d < days:
            events.append({"day": idx[d], "kind": "playlist", "platform": "spotify", "magnitude": 1.0, "title": "Added to an editorial playlist"})
    viral_day = int(days * 0.62)
    events.append({"day": idx[viral_day], "kind": "viral", "platform": None, "magnitude": 2.0, "title": "Short-form video trend"})
    tour_day = int(days * 0.8)
    events.append({"day": idx[tour_day], "kind": "tour", "platform": None, "magnitude": 1.0, "title": "Regional tour starts"})

    # Latent "interest" in the artist that every platform responds to.
    base = np.exp(0.0009 * t)  # ~39% growth per year
    bump = np.zeros(days)
    for ev in events:
        d = idx.get_loc(ev["day"])
        k = np.arange(days - d)
        if ev["kind"] == "release":
            bump[d:] += 0.9 * ev["magnitude"] * np.exp(-k / 18)
        elif ev["kind"] == "playlist":
            bump[d:] += 0.5 * np.exp(-k / 45)
        elif ev["kind"] == "viral":
            bump[d:] += 3.0 * np.exp(-k / 6) + 0.3 * np.exp(-k / 90)
        elif ev["kind"] == "tour":
            bump[d : d + 30] += 0.25
    interest = base * (1 + bump)

    weekday = np.array([0.93, 0.95, 0.97, 1.0, 1.1, 1.06, 0.99])[idx.dayofweek]

    def lagged(x: np.ndarray, lag: int) -> np.ndarray:
        return np.concatenate([np.full(lag, x[0]), x[:-lag]]) if lag > 0 else x

    def noisy(x: np.ndarray, sd: float = 0.06) -> np.ndarray:
        return x * np.exp(rng.normal(0, sd, len(x)))

    rows = []

    def add(platform: str, metric: str, vals: np.ndarray, kind: str = "daily") -> None:
        for d, v in zip(idx, vals):
            rows.append({"platform": platform, "metric": metric, "day": d, "value": float(round(v)), "kind": kind})

    # YouTube and Shazam move first; streaming follows.
    yt_views = noisy(interest * 0.6 * scale * weekday)
    sp_interest = lagged(interest, 3)
    sp_streams = noisy(sp_interest * scale * weekday)
    sp_listeners = noisy(sp_interest * scale * 0.38 * weekday, 0.04)
    sp_followers = 2000 + np.cumsum(noisy(sp_interest * scale * 0.004, 0.2))
    am_interest = lagged(interest, 2)
    am_streams = noisy(am_interest * scale * 0.28 * weekday)
    am_listeners = noisy(am_interest * scale * 0.1 * weekday, 0.05)
    shazams = noisy(interest * scale * 0.012, 0.15)
    yt_subs = 1500 + np.cumsum(noisy(interest * scale * 0.002, 0.25))
    yt_minutes = noisy(yt_views * 2.4, 0.05)

    add("spotify", "streams", sp_streams)
    add("spotify", "listeners", sp_listeners)
    add("spotify", "followers", sp_followers, "total")
    add("apple_music", "streams", am_streams)
    add("apple_music", "listeners", am_listeners)
    add("apple_music", "shazams", shazams)
    add("youtube", "views", yt_views)
    add("youtube", "watch_minutes", yt_minutes)
    add("youtube", "subscribers", yt_subs, "total")

    snap = pd.DataFrame(rows)
    ev = pd.DataFrame(events)
    return snap, ev
