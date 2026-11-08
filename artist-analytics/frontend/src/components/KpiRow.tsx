/**
 * KpiRow.tsx — the row of headline number tiles at the top of the dashboard.
 *
 * NEW TO REACT? This is a good first component to read. It is "presentational":
 * it fetches nothing and stores no state. It takes data in through props,
 * returns JSX, and reports clicks back through a callback prop. Components
 * like this are the easiest to reason about — given the same props they always
 * render the same thing.
 *
 * Styling note: each tile is a real <button>, not a clickable <div>. That gets
 * keyboard focus and screen-reader support for free; `.kpi` in styles.css adds
 * the sky-blue hover border and focus ring.
 */

import type { MetricFacts, Summary } from "../types";
import { PLATFORM_LABEL } from "../types";
import { fmtNum, fmtPct, metricLabel } from "../format";

// Which tiles to show, in a fixed order. Kept outside the component on
// purpose: module-level constants are created once, while anything defined
// inside the function body is rebuilt on every single render.
const TILES: [MetricFacts["platform"], string][] = [
  ["spotify", "streams"],
  ["spotify", "listeners"],
  ["apple_music", "streams"],
  ["youtube", "views"],
  ["spotify", "followers"],
  ["youtube", "subscribers"],
];

// The props are destructured straight out of the object in the parameter list,
// with their types written inline. `summary` is data flowing down; `onPick` is
// a function flowing up — the parent decides what a click actually does.
export default function KpiRow({ summary, onPick }: { summary: Summary; onPick: (platform: MetricFacts["platform"], metric: string) => void }) {
  // Look up the real numbers for each wanted tile and drop the ones with no
  // data. Computed on every render, which is fine — it's just array work.
  const tiles = TILES.map(([p, m]) => summary.metrics.find((x) => x.platform === p && x.metric === m)).filter(Boolean) as MetricFacts[];

  // Returning null renders nothing at all. An "early return" like this keeps
  // the main JSX below free of extra nesting.
  if (!tiles.length) return null;

  return (
    <div className="kpis">
      {tiles.map((t) => {
        // Per-item values worked out before the JSX, so the markup stays
        // readable. A `{ ... return ... }` body (rather than an arrow
        // shorthand) is what lets us declare these.
        const g = t.growth_28d;
        const isTotal = t.kind === "total";
        const value = isTotal ? t.latest.value : g.current;
        const stale = summary.freshness[t.platform]?.stale;

        return (
          // `key` must be unique among siblings and stable across renders;
          // platform + metric is both. Without it React can reuse the wrong
          // tile when the list changes.
          <button key={t.platform + t.metric} className="card kpi" style={{ textAlign: "left", cursor: "pointer" }} onClick={() => onPick(t.platform, t.metric)}>
            <div className="label">
              {/* The `style` prop takes an object, not a string, and its keys
                  are camelCase. Here it's the right call: the color is only
                  known at runtime, so we point the dot at the platform's CSS
                  variable (--spotify, --youtube…) defined in styles.css.
                  Fixed styling belongs in the stylesheet instead. */}
              <span className="dot" style={{ background: `var(--${t.platform})` }} />
              {PLATFORM_LABEL[t.platform]} · {metricLabel(t.metric)}
            </div>

            <div className="value">{fmtNum(value)}</div>

            {/* A template literal builds the class list, so the extra class is
                "up", "down" or "" depending on the data. This is how CSS
                state classes get applied conditionally in React. */}
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
