"""Claude as the analyst: reads the pandas fact sheet (+ forecasts) and writes
trend reports, explains what-if scenarios, and answers questions.

Claude never sees raw rows — it gets the computed facts, so its claims are
grounded in numbers the app can show. Without an API key, a plain rule-based
summary is returned instead so the app still works.
"""

from __future__ import annotations

import json
import logging

from ..config import get_settings

log = logging.getLogger(__name__)

SYSTEM = """You are the analyst inside a multi-platform music analytics app (Spotify, Apple Music, YouTube).
You receive a JSON fact sheet computed with pandas from the artist's daily telemetry, plus forecasts from a model.

How to write:
- Lead with what matters most right now, in plain language an artist or manager can act on.
- Every claim cites a number from the data (e.g. "Spotify streams +18% over the last 28 days").
- Separate what the data shows from what you infer. Events that line up with a spike are correlation unless the pattern repeats across several events.
- When predicting, give a direction, a rough size, a time frame and your confidence, and say what would change your mind.
- Use the cross-platform lead/lag readings: if one platform tends to move first, say what it currently signals for the others.
- Flag data problems: stale uploads (freshness.stale), short history, or estimated values. Never present estimates as actuals.
- Metric names: 'streams' on Apple Music are plays of 30s+. YouTube 'views' may be derived from lifetime totals when the channel isn't connected.
- Don't invent data that isn't in the fact sheet. If something important is missing, say what upload or connection would provide it.
- Use short sections with headings and bullets. Keep it under ~400 words unless asked for more."""


def enabled() -> bool:
    return bool(get_settings().anthropic_api_key)


def _call(user: str, max_tokens: int = 1500) -> tuple[str, str]:
    import anthropic

    s = get_settings()
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    msg = client.messages.create(
        model=s.anthropic_model,
        max_tokens=max_tokens,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return text, s.anthropic_model


def trend_report(artist_name: str, facts: dict, extras: dict) -> tuple[str, str]:
    if not enabled():
        return fallback_report(artist_name, facts), "rule-based"
    user = (
        f"Artist: {artist_name}\n\nFact sheet:\n```json\n{json.dumps(facts, default=str)}\n```\n\n"
        f"Top songs / playlists / 28-day forecasts:\n```json\n{json.dumps(extras, default=str)}\n```\n\n"
        "Write the trend report: 1) What's happening now, 2) What's driving it, "
        "3) What to expect over the next 4 weeks, 4) Recommended actions, 5) Data gaps."
    )
    return _call(user)


def explain_scenario(artist_name: str, facts: dict, scenario: dict) -> tuple[str, str]:
    if not enabled():
        return fallback_scenario(scenario), "rule-based"
    user = (
        f"Artist: {artist_name}\n\nFact sheet:\n```json\n{json.dumps(facts, default=str)}\n```\n\n"
        f"The user is exploring this what-if scenario (baseline = current plans only; scenario = with the hypothetical events):\n"
        f"```json\n{json.dumps(scenario, default=str)}\n```\n\n"
        "Explain in under 250 words: the predicted effect and when it peaks and fades, how it compares with this artist's "
        "past events of the same kind, how confident the prediction is (method, history length, band width), "
        "and one or two changes to the plan (timing, stacking, platform) that the data suggests would help."
    )
    return _call(user, 900)


def answer(artist_name: str, facts: dict, extras: dict, question: str) -> tuple[str, str]:
    if not enabled():
        return "Add an ANTHROPIC_API_KEY to .env to ask Claude questions about the data.", "rule-based"
    user = (
        f"Artist: {artist_name}\n\nFact sheet:\n```json\n{json.dumps(facts, default=str)}\n```\n\n"
        f"Extra context:\n```json\n{json.dumps(extras, default=str)}\n```\n\nQuestion: {question}"
    )
    return _call(user, 1000)


# ---------- fallbacks (no API key) ----------

def _fmt_pct(p):
    return "n/a" if p is None else f"{p:+.1f}%"


def fallback_report(artist_name: str, facts: dict) -> str:
    lines = [f"## {artist_name}: trend summary", "", "_Rule-based summary. Add ANTHROPIC_API_KEY for Claude's analysis._", ""]
    for m in facts.get("metrics", []):
        if m["kind"] != "daily":
            continue
        g28 = m["growth_28d"]["change_pct"]
        wk = m["trend_pct_per_week"]
        lines.append(f"- **{m['platform']} {m['metric']}**: 28-day change {_fmt_pct(g28)}, trend {_fmt_pct(wk)}/week")
        for a in m["anomalies"][-2:]:
            lines.append(f"  - {a['type']} on {a['day']}: {a['value']:,.0f} vs ~{a['expected']:,.0f} expected")
    for k, v in facts.get("cross_platform_lead_lag", {}).items():
        lines.append(f"- {v['reading']} (correlation {v['correlation']})")
    stale = [p for p, f in facts.get("freshness", {}).items() if f["stale"]]
    if stale:
        lines.append(f"- Data is stale or missing for: {', '.join(stale)}")
    return "\n".join(lines)


def fallback_scenario(sc: dict) -> str:
    return (
        f"Predicted {sc['metric']} on {sc['platform']} over {len(sc['points'])} days: "
        f"{sc['scenario_total']:,.0f} with the planned events vs {sc['baseline_total']:,.0f} without "
        f"({sc['lift_pct']:+.1f}%). Method: {sc['method']}. Add ANTHROPIC_API_KEY for Claude's explanation."
    )
