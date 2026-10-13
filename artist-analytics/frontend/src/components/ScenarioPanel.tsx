import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import type { NewEvent, Platform, ScenarioResult } from "../types";
import { EVENT_KINDS, PLATFORM_LABEL } from "../types";
import { addDays, fmtNum, fmtPct, metricLabel, shortDate, today } from "../format";

/**
 * "What if…": describe upcoming circumstances, get baseline vs scenario forecasts,
 * and Claude's read on it. Nothing is saved as a real plan until you click "Save as plan".
 */
export default function ScenarioPanel({ artistId, platform, metric }: { artistId: number; platform: Platform; metric: string }) {
  const [events, setEvents] = useState<NewEvent[]>([{ day: addDays(today(), 14), kind: "release", platform: null, magnitude: 1, title: "New single" }]);
  const [horizon, setHorizon] = useState(42);
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Turning a scenario into the plan: saved events become part of every future baseline forecast.
  const savePlan = async () => {
    await Promise.all(events.map((e) => api.addEvent(artistId, e)));
    setSaved(true);
  };

  const update = (i: number, patch: Partial<NewEvent>) => setEvents(events.map((e, j) => (j === i ? { ...e, ...patch } : e)));

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setSaved(false);
      setResult(await api.scenario(artistId, { platform, metric, horizon, events, explain: true }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const color = `var(--${platform})`;
  return (
    <div className="card">
      <h2>What if…</h2>
      <p className="muted small">
        Plan upcoming circumstances and see how they'd change {PLATFORM_LABEL[platform]} {metricLabel(metric).toLowerCase()} over the next {horizon} days.
        Effect sizes come from this artist's own past releases and playlist adds when there's enough history.
      </p>

      {events.map((e, i) => (
        <div key={i} className="event-row">
          <input type="date" value={e.day} onChange={(x) => update(i, { day: x.target.value })} aria-label="Date" />
          <select value={e.kind} onChange={(x) => update(i, { kind: x.target.value })} aria-label="Type">
            {EVENT_KINDS.map((k) => <option key={k}>{k}</option>)}
          </select>
          <input value={e.title} onChange={(x) => update(i, { title: x.target.value })} placeholder="Description" aria-label="Description" />
          <select value={e.magnitude} onChange={(x) => update(i, { magnitude: Number(x.target.value) })} aria-label="Size">
            <option value={0.5}>small</option>
            <option value={1}>normal</option>
            <option value={2}>big</option>
          </select>
          <button className="btn secondary" onClick={() => setEvents(events.filter((_, j) => j !== i))} aria-label="Remove">×</button>
        </div>
      ))}
      <div className="row" style={{ marginTop: 8 }}>
        <button className="btn secondary" onClick={() => setEvents([...events, { day: addDays(today(), 21), kind: "playlist", platform: null, magnitude: 1, title: "" }])}>+ Add circumstance</button>
        <label className="small row">
          Horizon
          <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
            {[14, 28, 42, 56].map((h) => <option key={h} value={h}>{h} days</option>)}
          </select>
        </label>
        <button className="btn" onClick={run} disabled={busy}>{busy ? "Predicting…" : "Predict"}</button>
      </div>
      {error && <p className="err small">{error}</p>}

      {result && (
        <div style={{ marginTop: 14 }}>
          <div className="row">
            <strong>{fmtNum(result.scenario_total)}</strong>
            <span className="muted small">vs {fmtNum(result.baseline_total)} without these plans</span>
            <span className={`delta ${result.lift_pct >= 0 ? "up" : "down"}`}>{fmtPct(result.lift_pct)}</span>
            <span className="pill">method: {result.method}</span>
            <button className="btn secondary" onClick={savePlan} disabled={saved}>{saved ? "Saved to timeline" : "Save as plan"}</button>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={result.points.map((p) => ({ ...p, band: [p.low, p.high] }))} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="day" tickFormatter={shortDate} minTickGap={30} tick={{ fill: "var(--muted)", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
              <YAxis tickFormatter={(v) => fmtNum(v)} width={48} tick={{ fill: "var(--muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                formatter={(v, name) => [Array.isArray(v) ? `${fmtNum(Number(v[0]))}–${fmtNum(Number(v[1]))}` : Math.round(Number(v)).toLocaleString(), name]}
                labelFormatter={(l) => shortDate(String(l))}
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
              />
              <Area dataKey="band" name="80% range" stroke="none" fill={color} fillOpacity={0.15} isAnimationActive={false} />
              <Line dataKey="baseline" name="Without plans" stroke="var(--muted)" strokeWidth={2} strokeDasharray="4 4" dot={false} isAnimationActive={false} />
              <Line dataKey="scenario" name="With plans" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
          <div className="legend">
            <span><span className="swatch" style={{ borderColor: color }} />With plans</span>
            <span><span className="swatch dashed" style={{ borderColor: "var(--muted)" }} />Without plans</span>
            <span><span className="swatch band" style={{ background: color }} />80% range</span>
          </div>
          {result.explanation && (
            <div className="insight">
              <ReactMarkdown>{result.explanation}</ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
