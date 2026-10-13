"""Forecasts and what-if scenarios.

Uses the trained PyTorch model when one exists; otherwise a transparent
heuristic (recent level x weekday pattern x damped trend x event uplift, with
uplift sizes learned from this artist's own past releases/playlists when
possible). The response says which method was used.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..analytics.trends import event_lift
from .features import EVENT_DECAY, H, make_input

log = logging.getLogger(__name__)

# Fallback uplift per unit magnitude at the event day, used when the artist has no history for that kind.
DEFAULT_LIFT = {"release": 0.35, "playlist": 0.25, "promo": 0.12, "tour": 0.10, "viral": 1.0, "press": 0.08, "collab": 0.2}
Z80 = 1.2816

_model_cache: dict = {"mtime": None, "model": None}


@dataclass
class Forecast:
    days: pd.DatetimeIndex
    mean: np.ndarray
    low: np.ndarray
    high: np.ndarray
    method: str


def _load_model():
    try:
        import torch

        from .model import ScenarioForecaster
        from .train import model_path
    except ImportError:
        return None
    p = model_path()
    if not p.exists():
        return None
    mtime = p.stat().st_mtime
    if _model_cache["mtime"] != mtime:
        ckpt = torch.load(p, map_location="cpu")
        m = ScenarioForecaster(ckpt["config"]["hidden"])
        m.load_state_dict(ckpt["state_dict"])
        m.eval()
        _model_cache.update(mtime=mtime, model=m)
    return _model_cache["model"]


def _torch_forecast(model, s, events, platform, metric, anchor, horizon) -> Forecast | None:
    import torch

    inp = make_input(s, events, platform, metric, anchor, horizon)
    if inp is None:
        return None
    past, fut, st, level, fut_idx = inp
    with torch.no_grad():
        mean, lv = model(torch.tensor(past)[None], torch.tensor(fut)[None], torch.tensor(st)[None])
    mean, sd = mean[0, :horizon].numpy(), (lv[0, :horizon].exp() ** 0.5).numpy()
    to = lambda x: np.maximum(np.expm1(x + level), 0)
    return Forecast(fut_idx, to(mean), to(mean - Z80 * sd), to(mean + Z80 * sd), "pytorch")


def learned_lifts(s: pd.Series, history_events: pd.DataFrame) -> dict[str, float]:
    lifts = dict(DEFAULT_LIFT)
    if history_events is None or history_events.empty:
        return lifts
    rows = pd.DataFrame(event_lift(s, history_events, before=14, after=7))  # caller filters by platform
    if rows.empty:
        return lifts
    rows = rows.dropna(subset=["lift_pct"])
    for kind, g in rows.groupby("kind"):
        if len(g) >= 2:
            # after/before over a week ~ average of the decaying bump; scale up to the peak.
            lifts[kind] = float(np.clip(g["lift_pct"].median() / 100 * 1.6, 0.0, 3.0))
    return lifts


def _event_multiplier(days: pd.DatetimeIndex, events: pd.DataFrame, platform: str, lifts: dict[str, float]) -> np.ndarray:
    """1 + sum of decaying bumps from every event (past or planned) on each day."""
    mult = np.ones(len(days))
    if events is None or events.empty:
        return mult
    ev = events[(events["platform"].isna()) | (events["platform"] == platform)]
    for r in ev.itertuples():
        if r.kind not in EVENT_DECAY:
            continue
        dt = (days - pd.Timestamp(r.day)).days.values
        on = dt >= 0
        mult[on] += lifts.get(r.kind, 0.1) * float(r.magnitude or 1) * np.exp(-dt[on] / EVENT_DECAY[r.kind])
    return mult


def _heuristic_forecast(s, events, platform, anchor, horizon, lifts) -> Forecast | None:
    logs = np.log1p(s.asfreq("D").clip(lower=0)).loc[:anchor].dropna()
    if len(logs) < 14:
        return None
    recent = logs.iloc[-84:]
    # Strip out the bumps from recent events so a fading release isn't mistaken for a trend.
    recent = recent - np.log(_event_multiplier(recent.index, events, platform, lifts))
    # Weekday pattern (log-space offsets)
    dow = recent.groupby(recent.index.dayofweek).mean()
    dow = (dow - dow.mean()).reindex(range(7), fill_value=0.0)
    deseason = recent - dow.reindex(recent.index.dayofweek).values
    last28 = deseason.iloc[-28:]
    level = float(last28.mean())
    x = np.arange(len(last28))
    slope = float(np.polyfit(x, last28.values, 1)[0]) if len(last28) >= 14 else 0.0
    slope = float(np.clip(slope, -0.01, 0.01))  # cap at ~±7%/week
    resid_sd = float((deseason - deseason.rolling(7, min_periods=3).mean()).std() or 0.1)

    fut_idx = pd.date_range(start=anchor + pd.Timedelta(days=1), periods=horizon, freq="D")
    h = np.arange(1, horizon + 1)
    # Damped trend: contributes less the further out we go. last28's mean sits ~14 days back.
    trend = slope * 14 + slope * (1 - 0.97**h) / (1 - 0.97)
    base = level + trend + dow.reindex(fut_idx.dayofweek).values
    # Past events keep decaying into the future; planned ones add new bumps.
    mean = base + np.log(_event_multiplier(fut_idx, events, platform, lifts))
    sd = resid_sd * np.sqrt(1 + h / 7)
    to = lambda v: np.maximum(np.expm1(v), 0)
    return Forecast(fut_idx, to(mean), to(mean - Z80 * sd), to(mean + Z80 * sd), "heuristic")


def forecast(s: pd.Series, events: pd.DataFrame, platform: str, metric: str, anchor: pd.Timestamp | None = None, horizon: int = 28) -> Forecast | None:
    """Forecast `horizon` days after `anchor` (default: last observed day), given events."""
    horizon = int(min(horizon, H))
    clean = s.dropna()
    if clean.empty:
        return None
    anchor = anchor or clean.index[-1]
    model = _load_model()
    if model is not None:
        try:
            f = _torch_forecast(model, s, events, platform, metric, anchor, horizon)
            if f is not None:
                return f
        except Exception:  # noqa: BLE001
            log.exception("pytorch forecast failed; falling back to heuristic")
    hist = events
    if events is not None and not events.empty:
        hist = events[(pd.to_datetime(events["day"]) <= anchor) & (events["platform"].isna() | (events["platform"] == platform))]
    return _heuristic_forecast(s, events, platform, anchor, horizon, learned_lifts(s, hist))


def scenario(s: pd.Series, known_events: pd.DataFrame, hypothetical: pd.DataFrame, platform: str, metric: str, horizon: int = 28) -> tuple[Forecast, Forecast] | None:
    """Baseline (known plans only) vs scenario (known + hypothetical), from the same anchor."""
    base = forecast(s, known_events, platform, metric, horizon=horizon)
    both = pd.concat([known_events, hypothetical], ignore_index=True) if not hypothetical.empty else known_events
    scen = forecast(s, both, platform, metric, horizon=horizon)
    if base is None or scen is None:
        return None
    return base, scen


def gap_estimates(s: pd.Series, events: pd.DataFrame, platform: str, metric: str, until: pd.Timestamp) -> Forecast | None:
    """Estimate days between the last upload and `until` so charts aren't blank between CSV uploads."""
    clean = s.dropna()
    if clean.empty:
        return None
    gap = (until - clean.index[-1]).days
    if gap <= 0:
        return None
    return forecast(s, events, platform, metric, anchor=clean.index[-1], horizon=min(gap, H))
