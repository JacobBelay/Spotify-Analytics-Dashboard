"""pandas trend analytics over the telemetry table.

Everything here is pure pandas/numpy (no DB), so it's easy to test. The output
of `artist_summary` is the fact sheet Claude reads before it writes a report.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

# Metrics that are running totals; growth = day-over-day change.
TOTAL_METRICS = {"followers", "subscribers", "lifetime_views"}
# The headline metric per platform, used for cross-platform comparisons.
HEADLINE = {"spotify": "streams", "apple_music": "streams", "youtube": "views"}


def build_series(snap: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    """(platform, metric) -> daily Series with a continuous DatetimeIndex (gaps = NaN)."""
    out: dict[tuple[str, str], pd.Series] = {}
    if snap.empty:
        return out
    for (platform, metric), g in snap.groupby(["platform", "metric"]):
        s = g.set_index("day")["value"].sort_index()
        s = s[~s.index.duplicated(keep="last")]
        s = s.asfreq("D")
        s.name = f"{platform}:{metric}"
        out[(platform, metric)] = s

    # YouTube: without OAuth analytics we only have lifetime totals; derive daily views.
    if ("youtube", "views") not in out and ("youtube", "lifetime_views") in out:
        tot = out[("youtube", "lifetime_views")]
        daily = tot.interpolate(limit_area="inside").diff().clip(lower=0)
        out[("youtube", "views")] = daily.rename("youtube:views")
    return out


def _pct(a: float, b: float) -> float | None:
    if b is None or a is None or not np.isfinite(a) or not np.isfinite(b) or b == 0:
        return None
    return round((a - b) / abs(b) * 100, 1)


def window_growth(s: pd.Series, days: int, total: bool = False) -> dict:
    """Compare the last `days` to the `days` before them."""
    s = s.dropna()
    if len(s) < days * 2:
        return {"days": days, "current": None, "previous": None, "change_pct": None}
    if total:
        cur = s.iloc[-1] - s.iloc[-days - 1] if len(s) > days else None
        prev = s.iloc[-days - 1] - s.iloc[-2 * days - 1] if len(s) > 2 * days else None
    else:
        cur, prev = s.iloc[-days:].sum(), s.iloc[-2 * days : -days].sum()
    return {
        "days": days,
        "current": None if cur is None else round(float(cur), 1),
        "previous": None if prev is None else round(float(prev), 1),
        "change_pct": _pct(cur, prev),
    }


def weekly_trend(s: pd.Series, lookback: int = 56) -> float | None:
    """Log-linear slope over the lookback, as % change per week."""
    s = s.dropna().iloc[-lookback:]
    s = s[s > 0]
    if len(s) < 14:
        return None
    x = (s.index - s.index[0]).days.values.astype(float)
    slope = np.polyfit(x, np.log(s.values), 1)[0]
    return round((np.exp(slope * 7) - 1) * 100, 2)


def anomalies(s: pd.Series, window: int = 28, z: float = 3.5, recent_days: int = 120) -> list[dict]:
    """Robust spikes/dips: distance from rolling median, scaled by rolling MAD."""
    s = s.dropna()
    if len(s) < window + 7:
        return []
    med = s.rolling(window, min_periods=window // 2).median().shift(1)
    mad = (s - med).abs().rolling(window, min_periods=window // 2).median().shift(1)
    score = 0.6745 * (s - med) / mad.replace(0, np.nan)
    flagged = score[(score.abs() >= z)].dropna()
    flagged = flagged[flagged.index >= s.index[-1] - pd.Timedelta(days=recent_days)]
    out = []
    for day, sc in flagged.items():
        out.append(
            {
                "day": day.date().isoformat(),
                "type": "spike" if sc > 0 else "dip",
                "value": round(float(s[day]), 1),
                "expected": round(float(med[day]), 1),
                "score": round(float(sc), 1),
            }
        )
    # Collapse runs of consecutive days into their strongest day.
    collapsed: list[dict] = []
    for a in out:
        if collapsed and (pd.Timestamp(a["day"]) - pd.Timestamp(collapsed[-1]["day"])).days <= 2 and a["type"] == collapsed[-1]["type"]:
            if abs(a["score"]) > abs(collapsed[-1]["score"]):
                collapsed[-1] = a
        else:
            collapsed.append(a)
    return collapsed[-10:]


def event_lift(s: pd.Series, events: pd.DataFrame, before: int = 14, after: int = 14) -> list[dict]:
    """Average of the `after` days following each event vs the `before` days preceding it."""
    s = s.dropna()
    if s.empty or events.empty:
        return []
    out = []
    for ev in events.sort_values("day").itertuples():
        d = pd.Timestamp(ev.day)
        pre = s[(s.index >= d - pd.Timedelta(days=before)) & (s.index < d)]
        post = s[(s.index >= d) & (s.index < d + pd.Timedelta(days=after))]
        if len(pre) < before // 2 or len(post) < after // 2:
            continue
        out.append(
            {
                "day": d.date().isoformat(),
                "kind": ev.kind,
                "title": ev.title,
                "avg_before": round(float(pre.mean()), 1),
                "avg_after": round(float(post.mean()), 1),
                "lift_pct": _pct(post.mean(), pre.mean()),
            }
        )
    return out


def weekday_profile(s: pd.Series, lookback: int = 84) -> dict[str, float] | None:
    s = s.dropna().iloc[-lookback:]
    if len(s) < 28:
        return None
    by = s.groupby(s.index.dayofweek).mean()
    by = by / by.mean()
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {names[i]: round(float(v), 3) for i, v in by.items()}


def lead_lag(a: pd.Series, b: pd.Series, max_lag: int = 10) -> dict | None:
    """Does `a` move before `b`? Correlates day-over-day log changes at each lag.

    Positive best_lag = a leads b by that many days.
    """
    df = pd.concat([a, b], axis=1).dropna()
    df = df[(df > 0).all(axis=1)]
    if len(df) < 60:
        return None
    ra, rb = np.log(df.iloc[:, 0]).diff(), np.log(df.iloc[:, 1]).diff()
    best, best_c = 0, 0.0
    for lag in range(-max_lag, max_lag + 1):
        c = ra.shift(lag).corr(rb)
        if c is not None and np.isfinite(c) and abs(c) > abs(best_c):
            best, best_c = lag, c
    return {"best_lag_days": best, "correlation": round(float(best_c), 3)}


def freshness(series: dict[tuple[str, str], pd.Series], today: date, stale_after: int) -> dict:
    out = {}
    for platform in ("spotify", "apple_music", "youtube"):
        days = [s.dropna().index.max() for (p, _), s in series.items() if p == platform and not s.dropna().empty]
        if not days:
            out[platform] = {"last_day": None, "days_old": None, "stale": True, "has_data": False}
            continue
        last = max(days).date()
        age = (today - last).days
        out[platform] = {"last_day": last.isoformat(), "days_old": age, "stale": age > stale_after, "has_data": True}
    return out


def artist_summary(snap: pd.DataFrame, events: pd.DataFrame, today: date | None = None, stale_after: int = 7) -> dict:
    """Compact, JSON-safe fact sheet for one artist."""
    today = today or date.today()
    series = build_series(snap)
    metrics: list[dict] = []
    for (platform, metric), s in sorted(series.items()):
        if metric == "lifetime_views":
            continue
        total = metric in TOTAL_METRICS
        clean = s.dropna()
        if clean.empty:
            continue
        ev = events
        if not events.empty:
            ev = events[(events["platform"].isna()) | (events["platform"] == platform)]
        metrics.append(
            {
                "platform": platform,
                "metric": metric,
                "kind": "total" if total else "daily",
                "latest": {"day": clean.index[-1].date().isoformat(), "value": round(float(clean.iloc[-1]), 1)},
                "history_days": int(len(clean)),
                "growth_7d": window_growth(s, 7, total),
                "growth_28d": window_growth(s, 28, total),
                "trend_pct_per_week": None if total else weekly_trend(s),
                "anomalies": [] if total else anomalies(s),
                "event_lift": [] if total else event_lift(s, ev)[-8:],
                "weekday_profile": None if total else weekday_profile(s),
            }
        )

    cross = {}
    heads = {p: series.get((p, m)) for p, m in HEADLINE.items() if (p, m) in series}
    plats = list(heads)
    for i, a in enumerate(plats):
        for b in plats[i + 1 :]:
            ll = lead_lag(heads[a], heads[b])
            if ll and abs(ll["correlation"]) >= 0.2:
                lag = ll["best_lag_days"]
                ll["reading"] = (
                    f"{a} and {b} move together the same day" if lag == 0
                    else f"{a if lag > 0 else b} tends to move {abs(lag)} day(s) before {b if lag > 0 else a}"
                )
                cross[f"{a}|{b}"] = ll

    upcoming = []
    if not events.empty:
        fut = events[events["day"] >= pd.Timestamp(today)]
        upcoming = [
            {"day": r.day.date().isoformat(), "kind": r.kind, "platform": r.platform, "title": r.title, "magnitude": r.magnitude}
            for r in fut.sort_values("day").itertuples()
        ]

    return {
        "as_of": today.isoformat(),
        "freshness": freshness(series, today, stale_after),
        "metrics": metrics,
        "cross_platform_lead_lag": cross,
        "upcoming_events": upcoming,
    }
