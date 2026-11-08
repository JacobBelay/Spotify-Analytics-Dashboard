/**
 * Dashboard.tsx — the main screen: KPI tiles, a trend chart, and side panels.
 *
 * NEW TO REACT? This is the component that shows how effects and dependency
 * arrays really work. It runs two separate useEffects:
 *
 *   [artist.id]        -> reload everything when a different artist is picked
 *   [artist.id, sel, days] -> refetch only the chart when the metric or range
 *                             changes, leaving the rest of the screen alone
 *
 * Splitting them is the point. One big effect would refetch everything every
 * time you tapped a date-range button.
 */

import { useEffect, useState } from "react";
import { api } from "../api";
import type { Artist, Available, Onboarding, Platform, Series, Summary } from "../types";
import { PLATFORM_LABEL } from "../types";
import { metricLabel } from "../format";
import KpiRow from "./KpiRow";
import TrendChart from "./TrendChart";
import ScenarioPanel from "./ScenarioPanel";
import InsightsPanel from "./InsightsPanel";

// Static option lists live outside the component so they aren't rebuilt on
// every render.
const RANGES = [
  { label: "90 days", days: 90 },
  { label: "6 months", days: 180 },
  { label: "1 year", days: 365 },
  { label: "All", days: 3650 },
];

export default function Dashboard({ artist, onOpenSources }: { artist: Artist; onOpenSources: () => void }) {
  // A `T | null` state with null meaning "not loaded yet" is the simplest
  // loading pattern there is: no separate boolean to keep in sync.
  const [summary, setSummary] = useState<Summary | null>(null);
  const [onb, setOnb] = useState<Onboarding | null>(null);
  const [avail, setAvail] = useState<Available[]>([]);
  const [sel, setSel] = useState<{ platform: Platform; metric: string } | null>(null);
  const [days, setDays] = useState(180);
  const [series, setSeries] = useState<Series | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Effect 1: load everything for this artist.
  useEffect(() => {
    // Clear the old artist's data first, so you never see artist A's numbers
    // under artist B's name while the new request is in flight.
    setSummary(null);
    setSeries(null);
    setSel(null);
    // Promise.all fires all three requests at once and waits for the slowest,
    // instead of awaiting them one after another.
    Promise.all([api.summary(artist.id), api.onboarding(artist.id), api.available(artist.id)])
      .then(([s, o, a]) => {
        setSummary(s);
        setOnb(o);
        setAvail(a);
        const first = a.find((x) => x.platform === "spotify" && x.metric === "streams") ?? a.find((x) => x.kind === "daily") ?? a[0];
        if (first) setSel({ platform: first.platform, metric: first.metric });
      })
      .catch((e) => setError(e.message));
    // The dependency array: re-run this effect whenever artist.id changes.
  }, [artist.id]);

  // Effect 2: load just the chart series. Separate effect, separate deps.
  useEffect(() => {
    if (!sel) return;
    api.series(artist.id, sel.platform, sel.metric, days).then(setSeries).catch((e) => setError(e.message));
  }, [artist.id, sel, days]);

  // Early returns handle the error and loading screens, so the JSX at the
  // bottom can assume the data exists. Note that these come *after* all the
  // hook calls — hooks must run in the same order on every render, so they
  // can never sit below a conditional return.
  if (error) return <p className="err">{error}</p>;
  if (!summary) return <p className="muted">Loading…</p>;

  if (!avail.length) {
    return (
      <div className="card">
        <h2>No data yet for {artist.name}</h2>
        <p className="muted">Upload a Spotify for Artists export or connect YouTube to get started.</p>
        <button className="btn" onClick={onOpenSources}>Add data</button>
      </div>
    );
  }

  const selIsDaily = avail.find((a) => a.platform === sel?.platform && a.metric === sel?.metric)?.kind === "daily";
  const spikes = summary.metrics.flatMap((m) => m.anomalies.map((a) => ({ ...a, platform: m.platform, metric: m.metric }))).sort((a, b) => b.day.localeCompare(a.day)).slice(0, 6);
  const leadLag = Object.values(summary.cross_platform_lead_lag);

  return (
    <div className="grid">
      {onb?.reminders.map((r) => (
        <div key={r.platform} className="banner" role="status">
          <span aria-hidden>⚠</span>
          <span>{r.message}</span>
          <button className="btn" onClick={onOpenSources}>Upload now</button>
        </div>
      ))}

      {/* Passing a setter down as a callback: clicking a KPI tile changes
          `sel` here, which re-runs effect 2, which loads a new chart. The
          child knows nothing about any of that. */}
      <KpiRow summary={summary} onPick={(platform, metric) => setSel({ platform, metric })} />

      <div className="card">
        <p className="eyebrow">Trend</p>
        <div className="row" style={{ marginBottom: 8 }}>
          <select
            value={sel ? `${sel.platform}|${sel.metric}` : ""}
            onChange={(e) => {
              const [platform, metric] = e.target.value.split("|");
              setSel({ platform: platform as Platform, metric });
            }}
            aria-label="Metric"
          >
            {avail.map((a) => (
              <option key={a.platform + a.metric} value={`${a.platform}|${a.metric}`}>
                {PLATFORM_LABEL[a.platform]} · {metricLabel(a.metric)}
              </option>
            ))}
          </select>
          <div className="row" role="group" aria-label="Date range">
            {/* The selected button gets `.btn` (solid sky blue) and the rest
                get `.btn secondary` (quiet outline) — comparing state to the
                item is how you style the active one. */}
            {RANGES.map((r) => (
              <button key={r.days} className={`btn ${days === r.days ? "" : "secondary"}`} onClick={() => setDays(r.days)}>{r.label}</button>
            ))}
          </div>
        </div>
        {series ? <TrendChart series={series} /> : <p className="muted">Loading chart…</p>}
        {/* Every panel carries one of these micro-labels, which is what makes
            the separate cards read as a single system. */}
      </div>

      <div className="grid two">
        <div className="grid">
          {sel && selIsDaily && <ScenarioPanel artistId={artist.id} platform={sel.platform} metric={sel.metric} />}
          <div className="card">
            <p className="eyebrow">Signals</p>
            {leadLag.length > 0 && (
              <>
                <h3>Which platform moves first</h3>
                <ul className="small">
                  {leadLag.map((l) => (
                    <li key={l.reading}>{l.reading} <span className="muted">(correlation {l.correlation.toFixed(2)})</span></li>
                  ))}
                </ul>
              </>
            )}
            <h3>Recent spikes and dips</h3>
            {spikes.length === 0 ? (
              <p className="muted small">Nothing unusual in the last 4 months.</p>
            ) : (
              <table className="data">
                <tbody>
                  {spikes.map((s) => (
                    <tr key={s.platform + s.metric + s.day}>
                      <td>{s.day}</td>
                      <td>{PLATFORM_LABEL[s.platform]} {metricLabel(s.metric).toLowerCase()}</td>
                      <td>{s.type === "spike" ? "▲ spike" : "▼ dip"}</td>
                      <td>{Math.round(s.value).toLocaleString()} <span className="muted">vs ~{Math.round(s.expected).toLocaleString()}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        <InsightsPanel artistId={artist.id} />
      </div>
    </div>
  );
}
