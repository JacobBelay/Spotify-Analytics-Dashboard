"""Train the scenario forecaster on everything in the database.

    python -m app.ml.train            # train on DB data
    python -m app.ml.train --synthetic # train on generated demo data (no DB needed)

Uses a time-based split (last 20% of anchor dates = validation) and reports
MAPE against a seasonal-naive baseline, so you can see whether the model
actually beats "same as last week".
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import get_settings
from .features import H, build_dataset

log = logging.getLogger(__name__)
MODEL_FILE = "forecaster.pt"


def model_path() -> Path:
    p = Path(get_settings().model_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p / MODEL_FILE


def series_from_snapshots(snap: pd.DataFrame) -> dict[tuple[int, str, str], pd.Series]:
    from ..analytics.trends import TOTAL_METRICS, build_series

    out = {}
    for artist_id, g in snap.groupby("artist_id"):
        for (platform, metric), s in build_series(g).items():
            if metric not in TOTAL_METRICS:
                out[(int(artist_id), platform, metric)] = s
    return out


def _mape(pred_log, true_log, mask):
    """Percentage error on the original scale. Values are level-normalized log1p,
    so pred/true ~= exp(pred_log - true_log) for all but tiny counts."""
    err = np.abs(np.exp(pred_log - true_log) - 1)
    return float((err * mask).sum() / mask.sum() * 100)


def train(series, events_by_artist, epochs: int = 40, lr: float = 2e-3, seed: int = 0) -> dict:
    import torch

    from .model import CONFIG, ScenarioForecaster, masked_gaussian_nll

    torch.manual_seed(seed)
    ds = build_dataset(series, events_by_artist)
    if ds is None or len(ds["past"]) < 50:
        raise RuntimeError("Not enough history to train (need ~112+ days per series). Use the heuristic forecaster for now.")

    cut = np.quantile(ds["anchor"].astype(np.int64), 0.8)
    tr = ds["anchor"].astype(np.int64) <= cut
    va = ~tr
    T = {k: torch.tensor(v) for k, v in ds.items() if k != "anchor"}

    model = ScenarioForecaster(CONFIG["hidden"])
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    idx_tr = np.where(tr)[0]
    best, best_state = float("inf"), None

    for ep in range(epochs):
        model.train()
        np.random.shuffle(idx_tr)
        for b in range(0, len(idx_tr), 128):
            bi = torch.tensor(idx_tr[b : b + 128])
            mean, lv = model(T["past"][bi], T["future"][bi], T["static"][bi])
            loss = masked_gaussian_nll(mean, lv, T["target"][bi], T["mask"][bi])
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        sched.step()
        model.eval()
        with torch.no_grad():
            vi = torch.tensor(np.where(va)[0])
            mean, lv = model(T["past"][vi], T["future"][vi], T["static"][vi])
            vloss = masked_gaussian_nll(mean, lv, T["target"][vi], T["mask"][vi]).item()
        if vloss < best:
            best, best_state = vloss, {k: v.clone() for k, v in model.state_dict().items()}
        log.info("epoch %d val_nll %.4f", ep, vloss)

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        vi = torch.tensor(np.where(va)[0])
        mean, _ = model(T["past"][vi], T["future"][vi], T["static"][vi])
    past_v = ds["past"][va][:, :, 0]
    # Seasonal naive: repeat the last observed week.
    naive = np.tile(past_v[:, -7:], (1, int(np.ceil(H / 7))))[:, :H]
    model_mape = _mape(mean.numpy(), ds["target"][va], ds["mask"][va])
    naive_mape = _mape(naive, ds["target"][va], ds["mask"][va])

    path = model_path()
    torch.save({"state_dict": best_state, "config": CONFIG}, path)
    result = {
        "path": str(path),
        "n_series": len(series),
        "n_samples": int(len(ds["past"])),
        "val_mape": round(model_mape, 2),
        "baseline_mape": round(naive_mape, 2),
    }
    log.info("trained: %s", result)
    return result


def train_from_db() -> dict:
    from ..db import SessionLocal
    from ..models import ModelRun
    from ..store import load_events, load_snapshots

    with SessionLocal() as db:
        snap = load_snapshots(db)
        ev = load_events(db)
        series = series_from_snapshots(snap)
        by_artist = {int(a): g for a, g in ev.groupby("artist_id")} if not ev.empty else {}
        res = train(series, by_artist)
        db.add(ModelRun(n_series=res["n_series"], n_samples=res["n_samples"], val_mape=res["val_mape"], baseline_mape=res["baseline_mape"], path=res["path"]))
        db.commit()
    return res


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    args = ap.parse_args()
    if args.synthetic:
        from ..synthetic import generate

        series, by_artist = {}, {}
        for i in range(6):
            snap, ev = generate(seed=i, scale=1000 * (i + 1))
            snap["artist_id"] = i
            series.update(series_from_snapshots(snap))
            by_artist[i] = ev
        print(json.dumps(train(series, by_artist), indent=2))
    else:
        print(json.dumps(train_from_db(), indent=2))


if __name__ == "__main__":
    main()
