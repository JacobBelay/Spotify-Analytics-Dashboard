"""Load a demo artist with two years of realistic synthetic data.

    docker compose exec backend python -m app.seed

The Spotify/Apple data deliberately stops 10 days ago so you can see the
"data is stale" reminder and the dashed estimated days on the chart.
"""

from datetime import date, timedelta

from sqlalchemy import select

from .db import SessionLocal, init_db
from .models import Artist, Event
from .store import upsert_snapshots
from .synthetic import generate


def main() -> None:
    init_db()
    with SessionLocal() as db:
        if db.scalar(select(Artist).where(Artist.name == "Demo Artist")):
            print("Demo Artist already exists.")
            return
        a = Artist(name="Demo Artist", owned=True, genres=["indie pop"])
        db.add(a)
        db.commit()

        snap, ev = generate(end=date.today() - timedelta(days=1))
        cutoff = date.today() - timedelta(days=10)
        rows = []
        for r in snap.itertuples():
            d = r.day.date()
            if r.platform != "youtube" and d > cutoff:
                continue  # pretend the last CSV upload was 10 days ago
            rows.append(dict(artist_id=a.id, platform=r.platform, metric=r.metric, day=d, value=r.value, kind=r.kind, source="seed"))
        upsert_snapshots(db, rows)
        for e in ev.itertuples():
            db.add(Event(artist_id=a.id, day=e.day.date(), kind=e.kind, platform=e.platform, magnitude=e.magnitude, title=e.title, source="seed"))
        db.commit()
        print(f"Seeded Demo Artist (id={a.id}) with {len(rows)} rows and {len(ev)} events.")


if __name__ == "__main__":
    main()
