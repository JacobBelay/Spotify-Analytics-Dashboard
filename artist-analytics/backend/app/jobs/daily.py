"""Daily worker: snapshot YouTube, refresh releases, retrain the forecaster.

    python -m app.jobs.daily          # run once
    python -m app.jobs.daily --loop   # run every INGEST_INTERVAL_HOURS (docker 'worker' service)
"""

import argparse
import logging
import time

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal, init_db
from ..ingest import refresh_profile, snapshot_youtube
from ..models import Artist

log = logging.getLogger("worker")


def run_once() -> None:
    with SessionLocal() as db:
        for a in db.scalars(select(Artist)).all():
            try:
                p = refresh_profile(db, a)
                y = snapshot_youtube(db, a)
                log.info("%s: +%d releases, %d youtube rows, errors=%s", a.name, p["releases_added"], y["rows"], p["errors"] + y["errors"])
            except Exception:  # noqa: BLE001
                db.rollback()
                log.exception("ingest failed for %s", a.name)
    try:
        from ..ml.train import train_from_db

        log.info("retrained forecaster: %s", train_from_db())
    except ImportError:
        log.warning("torch not installed; using heuristic forecaster")
    except RuntimeError as e:
        log.info("skipped training: %s", e)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true")
    args = ap.parse_args()
    init_db()
    while True:
        run_once()
        if not args.loop:
            break
        time.sleep(get_settings().ingest_interval_hours * 3600)


if __name__ == "__main__":
    main()
