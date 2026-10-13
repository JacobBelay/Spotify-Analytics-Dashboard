from app.analytics.trends import artist_summary
from app.synthetic import generate


def test_summary_finds_structure_in_synthetic_data():
    snap, ev = generate(seed=1)
    s = artist_summary(snap, ev)
    streams = next(m for m in s["metrics"] if m["platform"] == "spotify" and m["metric"] == "streams")
    assert streams["growth_28d"]["change_pct"] is not None
    assert streams["weekday_profile"]["Fri"] > streams["weekday_profile"]["Mon"]  # built-in Friday bump
    releases = [e for e in streams["event_lift"] if e["kind"] == "release"]
    assert releases and sum(e["lift_pct"] > 0 for e in releases) >= len(releases) * 0.7
    # YouTube was generated to lead Spotify by 3 days
    ll = s["cross_platform_lead_lag"]["spotify|youtube"]
    assert ll["best_lag_days"] < 0 and "youtube tends to move" in ll["reading"]


def test_freshness_flags_stale_platform():
    snap, ev = generate(seed=2)
    snap = snap[~((snap.platform == "spotify") & (snap.day > snap.day.max() - __import__("pandas").Timedelta(days=12)))]
    s = artist_summary(snap, ev, stale_after=7)
    assert s["freshness"]["spotify"]["stale"] and not s["freshness"]["youtube"]["stale"]
