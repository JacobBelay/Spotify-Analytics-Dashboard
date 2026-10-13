from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import service
from ..analytics.trends import TOTAL_METRICS
from ..db import get_db
from ..insights import claude
from ..ml.forecast import gap_estimates, scenario
from ..models import Event, Insight
from ..schemas import BandPoint, EventOut, ForecastPoint, Point, ScenarioIn, ScenarioOut, SeriesOut
from .artists import get_artist

router = APIRouter(prefix="/api/artists/{artist_id}", tags=["metrics"])

# Only CSV-fed platforms get estimates between uploads; YouTube updates daily.
ESTIMATE_PLATFORMS = {"spotify", "apple_music"}


@router.get("/summary")
def summary(artist_id: int, db: Session = Depends(get_db)):
    get_artist(db, artist_id)
    return service.facts(db, artist_id)


@router.get("/available")
def available(artist_id: int, db: Session = Depends(get_db)):
    series, _ = service.artist_data(db, artist_id)
    return [
        {"platform": p, "metric": m, "kind": "total" if m in TOTAL_METRICS else "daily", "days": int(s.notna().sum())}
        for (p, m), s in sorted(series.items())
        if m != "lifetime_views"
    ]


@router.get("/series", response_model=SeriesOut)
def series(
    artist_id: int,
    platform: str,
    metric: str,
    days: int = Query(180, ge=14, le=3650),
    forecast_days: int = Query(28, ge=0, le=56),
    db: Session = Depends(get_db),
):
    get_artist(db, artist_id)
    all_series, events = service.artist_data(db, artist_id)
    s = all_series.get((platform, metric))
    if s is None:
        raise HTTPException(404, "No data for that platform/metric yet.")
    total = metric in TOTAL_METRICS
    today = pd.Timestamp(date.today())
    start = today - pd.Timedelta(days=days)
    obs = s.loc[start:].dropna()
    points = [Point(day=d.date(), value=float(v)) for d, v in obs.items()]

    method = None
    last_known = obs.index[-1] if len(obs) else None
    if not total and platform in ESTIMATE_PLATFORMS:
        gap = gap_estimates(s, events, platform, metric, until=today - pd.Timedelta(days=1))
        if gap is not None:
            method = gap.method
            points += [Point(day=d.date(), value=float(v), estimated=True) for d, v in zip(gap.days, gap.mean)]
            last_known = gap.days[-1]

    fc: list[BandPoint] = []
    if forecast_days and not total and last_known is not None:
        from ..ml.forecast import forecast

        # Forecast from the real data; skip the part that overlaps the gap estimates.
        f = forecast(s, events, platform, metric, horizon=min(56, forecast_days + (last_known - s.dropna().index[-1]).days))
        if f is not None:
            method = f.method
            fc = [BandPoint(day=d.date(), value=float(m), low=float(lo), high=float(hi)) for d, m, lo, hi in zip(f.days, f.mean, f.low, f.high) if d > last_known]

    evs = db.scalars(select(Event).where(Event.artist_id == artist_id, Event.day >= start.date()).order_by(Event.day)).all()
    evs = [e for e in evs if e.platform in (None, platform)]
    return SeriesOut(platform=platform, metric=metric, kind="total" if total else "daily", points=points, forecast=fc, forecast_method=method, events=[EventOut.model_validate(e) for e in evs])


@router.post("/scenario", response_model=ScenarioOut)
def run_scenario(artist_id: int, body: ScenarioIn, db: Session = Depends(get_db)):
    """What-if: how would these circumstances change the next N days?"""
    a = get_artist(db, artist_id)
    all_series, events = service.artist_data(db, artist_id)
    s = all_series.get((body.platform, body.metric))
    if s is None or body.metric in TOTAL_METRICS:
        raise HTTPException(400, "Pick a daily metric that has data (e.g. streams or views).")
    hyp = pd.DataFrame([{"day": pd.Timestamp(e.day), "kind": e.kind, "platform": e.platform, "magnitude": e.magnitude, "title": e.title} for e in body.events])
    if events.empty:
        events = pd.DataFrame(columns=["day", "kind", "platform", "magnitude", "title"])
    res = scenario(s, events, hyp, body.platform, body.metric, body.horizon)
    if res is None:
        raise HTTPException(400, "Not enough history to forecast yet (need at least 2 weeks).")
    base, scen = res
    bt, st = float(base.mean.sum()), float(scen.mean.sum())
    out = ScenarioOut(
        platform=body.platform,
        metric=body.metric,
        method=scen.method,
        points=[
            ForecastPoint(day=d.date(), baseline=float(b), scenario=float(x), low=float(lo), high=float(hi))
            for d, b, x, lo, hi in zip(scen.days, base.mean, scen.mean, scen.low, scen.high)
        ],
        baseline_total=bt,
        scenario_total=st,
        lift_pct=round((st / bt - 1) * 100, 1) if bt else 0.0,
    )
    if body.explain:
        sc = out.model_dump(mode="json")
        sc["hypothetical_events"] = [e.model_dump(mode="json") for e in body.events]
        sc["history_days"] = int(s.notna().sum())
        sc["points"] = sc["points"][::7]  # weekly samples are plenty for the explanation
        text, model = claude.explain_scenario(a.name, service.facts(db, artist_id), sc)
        out.explanation = text
        db.add(Insight(artist_id=artist_id, kind="scenario", question=None, context=sc, content=text, model=model))
        db.commit()
    return out
