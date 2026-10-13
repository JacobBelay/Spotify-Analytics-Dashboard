"""Turn telemetry + events into model-ready arrays (numpy only, no torch).

One sample = (series, anchor day t):
  past     [L, 1+K]  normalized log values + event intensity per kind for days t-L+1..t
  future   [H, K+7]  planned event intensity per kind + weekday one-hot for t+1..t+H
  static   [S]       platform + metric-family one-hot
  target   [H]       normalized log values for t+1..t+H

Values are normalized per sample by the mean log level of the last 28 days,
so one global model learns shapes ("a release adds ~X% and decays over ~Y days")
that transfer across artists of any size.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

L = 56   # days of history the model sees
H = 56   # max days it forecasts
EVENT_KINDS = ["release", "playlist", "promo", "tour", "viral", "press", "collab"]
K = len(EVENT_KINDS)
PLATFORMS = ["spotify", "apple_music", "youtube"]
METRIC_FAMILY = {"streams": 0, "listeners": 1, "views": 2, "watch_minutes": 2, "shazams": 3}
N_FAMILY = 5  # last slot = other
S = len(PLATFORMS) + N_FAMILY
LEVEL_WINDOW = 28

# How long each kind of event keeps having an effect, in days (for the intensity channel).
EVENT_DECAY = {"release": 21, "playlist": 45, "promo": 10, "tour": 30, "viral": 10, "press": 7, "collab": 21}


def event_matrix(days: pd.DatetimeIndex, events: pd.DataFrame, platform: str) -> np.ndarray:
    """[len(days), K] decaying intensity of each event kind (0 before the event)."""
    m = np.zeros((len(days), K), dtype=np.float32)
    if events is None or events.empty:
        return m
    ev = events[(events["platform"].isna()) | (events["platform"] == platform)]
    day_num = days.values.astype("datetime64[D]").astype(np.int64)
    for r in ev.itertuples():
        if r.kind not in EVENT_KINDS:
            continue
        k = EVENT_KINDS.index(r.kind)
        e = np.datetime64(pd.Timestamp(r.day).date(), "D").astype(np.int64)
        dt = day_num - e
        mask = dt >= 0
        m[mask, k] += float(r.magnitude or 1.0) * np.exp(-dt[mask] / EVENT_DECAY[r.kind])
    return m


def weekday_onehot(days: pd.DatetimeIndex) -> np.ndarray:
    oh = np.zeros((len(days), 7), dtype=np.float32)
    oh[np.arange(len(days)), days.dayofweek] = 1
    return oh


def static_vec(platform: str, metric: str) -> np.ndarray:
    v = np.zeros(S, dtype=np.float32)
    if platform in PLATFORMS:
        v[PLATFORMS.index(platform)] = 1
    v[len(PLATFORMS) + METRIC_FAMILY.get(metric, N_FAMILY - 1)] = 1
    return v


def _prep(s: pd.Series) -> pd.Series:
    s = s.asfreq("D")
    return np.log1p(s.clip(lower=0))


def make_input(s: pd.Series, events: pd.DataFrame, platform: str, metric: str, anchor: pd.Timestamp, horizon: int = H):
    """Model input for forecasting after `anchor`. Returns None if history is too thin."""
    logs = _prep(s)
    past_idx = pd.date_range(end=anchor, periods=L, freq="D")
    past = logs.reindex(past_idx)
    if past.isna().mean() > 0.2:
        return None
    past = past.ffill().bfill()
    level = float(past.iloc[-LEVEL_WINDOW:].mean())
    fut_idx = pd.date_range(start=anchor + pd.Timedelta(days=1), periods=H, freq="D")
    all_idx = past_idx.append(fut_idx)
    evm = event_matrix(all_idx, events, platform)
    past_arr = np.concatenate([(past.values - level)[:, None].astype(np.float32), evm[:L]], axis=1)
    fut_arr = np.concatenate([evm[L:], weekday_onehot(fut_idx)], axis=1)
    return past_arr, fut_arr, static_vec(platform, metric), level, fut_idx[:horizon]


def build_dataset(series: dict[tuple[int, str, str], pd.Series], events_by_artist: dict[int, pd.DataFrame], stride: int = 3):
    """Sliding-window samples across every (artist, platform, metric) daily series.

    Returns arrays plus the anchor dates so the caller can do a time-based split.
    """
    P, F, St, Y, M, A = [], [], [], [], [], []
    for (artist_id, platform, metric), s in series.items():
        s = s.asfreq("D")
        if s.dropna().shape[0] < L + H:
            continue
        logs = _prep(s)
        ev = events_by_artist.get(artist_id, pd.DataFrame())
        idx = s.index
        for i in range(L - 1, len(idx) - H, stride):
            anchor = idx[i]
            inp = make_input(s, ev, platform, metric, anchor)
            if inp is None:
                continue
            past, fut, st, level, fut_idx = inp
            y = logs.reindex(fut_idx).values - level
            mask = ~np.isnan(y)
            if mask.mean() < 0.8:
                continue
            P.append(past)
            F.append(fut)
            St.append(st)
            Y.append(np.nan_to_num(y).astype(np.float32))
            M.append(mask.astype(np.float32))
            A.append(anchor)
    if not P:
        return None
    return {
        "past": np.stack(P),
        "future": np.stack(F),
        "static": np.stack(St),
        "target": np.stack(Y),
        "mask": np.stack(M),
        "anchor": np.array(A, dtype="datetime64[D]"),
    }
