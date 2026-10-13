import type { MetricFacts, Summary } from "../types";
import { PLATFORM_LABEL } from "../types";
import { fmtNum, fmtPct, metricLabel } from "../format";

// The headline numbers per platform, in a fixed order.
const TILES: [MetricFacts["platform"], string][] = [
  ["spotify", "streams"],
  ["spotify", "listeners"],
  ["apple_music", "streams"],
  ["youtube", "views"],
  ["spotify", "followers"],
  ["youtube", "subscribers"],
];

export default function KpiRow({ summary, onPick }: { summary: Summary; onPick: (platform: MetricFacts["platform"], metric: string) => void }) {
  const tiles = TILES.map(([p, m]) => summary.metrics.find((x) => x.platform === p && x.metric === m)).filter(Boolean) as MetricFacts[];
  if (!tiles.length) return null;
  return (
    <div className="kpis">
      {tiles.map((t) => {
        const g = t.growth_28d;
        const isTotal = t.kind === "total";
        const value = isTotal ? t.latest.value : g.current;
        const stale = summary.freshness[t.platform]?.stale;
        return (
          <button key={t.platform + t.metric} className="card kpi" style={{ textAlign: "left", cursor: "pointer" }} onClick={() => onPick(t.platform, t.metric)}>
            <div className="label">
              <span className="dot" style={{ background: `var(--${t.platform})` }} />
              {PLATFORM_LABEL[t.platform]} · {metricLabel(t.metric)}
            </div>
            <div className="value">{fmtNum(value)}</div>
            <div className={`delta ${g.change_pct === null ? "" : g.change_pct >= 0 ? "up" : "down"}`}>
              {g.change_pct === null ? "not enough history" : `${g.change_pct >= 0 ? "▲" : "▼"} ${fmtPct(g.change_pct)} vs previous 28 days`}
            </div>
            <div className="muted small">{isTotal ? `total as of ${t.latest.day}` : "last 28 days"}{stale ? " · ⚠ data is old" : ""}</div>
          </button>
        );
      })}
    </div>
  );
}
