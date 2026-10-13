import numpy as np
import pandas as pd

from app.ml import forecast as F
from app.ml.features import H, L, build_dataset
from app.ml.train import series_from_snapshots
from app.synthetic import generate


def _data():
    snap, ev = generate(seed=3)
    snap["artist_id"] = 1
    return series_from_snapshots(snap), ev


def test_dataset_shapes_no_nans():
    series, ev = _data()
    ds = build_dataset(series, {1: ev}, stride=7)
    assert ds["past"].shape[1:] == (L, 8) and ds["target"].shape[1] == H
    assert not any(np.isnan(ds[k]).any() for k in ("past", "future", "static", "target"))


def test_heuristic_beats_seasonal_naive():
    series, ev = _data()
    s = series[(1, "spotify", "streams")]
    errs, naive_errs = [], []
    for back in range(60, 400, 30):
        a = s.index[-back]
        f = F.forecast(s, ev, "spotify", "streams", anchor=a, horizon=28)
        act = s.loc[f.days].values
        errs.append(np.mean(np.abs(f.mean - act) / act))
        naive = np.tile(s.loc[:a].iloc[-7:].values, 4)
        naive_errs.append(np.mean(np.abs(naive - act) / act))
    assert np.mean(errs) < np.mean(naive_errs)


def test_release_scenario_lifts_forecast():
    series, ev = _data()
    s = series[(1, "spotify", "streams")]
    last = s.index[-1]
    hyp = pd.DataFrame([{"day": last + pd.Timedelta(days=5), "kind": "release", "platform": None, "magnitude": 1.0, "title": "x"}])
    base, scen = F.scenario(s, ev, hyp, "spotify", "streams", 28)
    assert scen.mean.sum() > base.mean.sum()
    assert np.allclose(scen.mean[:4], base.mean[:4])  # nothing changes before the release
    assert (scen.low <= scen.mean).all() and (scen.mean <= scen.high).all()
