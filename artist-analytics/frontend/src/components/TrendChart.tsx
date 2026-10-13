import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Series } from "../types";
import { PLATFORM_LABEL } from "../types";
import { fmtNum, metricLabel, shortDate } from "../format";

interface Row {
  day: string;
  actual?: number;
  estimated?: number;
  forecast?: number;
  band?: [number, number];
}

/**
 * One series per chart (one platform + metric), so no legend box is needed for identity;
 * the small legend below explains the line styles: solid = reported, dashed = estimated
 * between uploads, dotted + band = forecast with 80% range. Events are vertical markers.
 */
export default function TrendChart({ series, height = 300 }: { series: Series; height?: number }) {
  const color = `var(--${series.platform})`;
  const byDay = new Map<string, Row>();
  const get = (d: string) => byDay.get(d) ?? byDay.set(d, { day: d }).get(d)!;

  let lastActual: { day: string; value: number } | null = null;
  for (const p of series.points) {
    if (p.estimated) get(p.day).estimated = p.value;
    else {
      get(p.day).actual = p.value;
      lastActual = p;
    }
  }
  // Join the dashed/dotted lines to the last solid point so there's no visual gap.
  const est = series.points.filter((p) => p.estimated);
  if (lastActual && est.length) get(lastActual.day).estimated = lastActual.value;
  const lastShown = est.length ? est[est.length - 1] : lastActual;
  if (lastShown && series.forecast.length) {
    const r = get(lastShown.day);
    r.forecast = lastShown.value;
    r.band = [lastShown.value, lastShown.value];
  }
  for (const f of series.forecast) {
    const r = get(f.day);
    r.forecast = f.value;
    r.band = [f.low, f.high];
  }
  const rows = [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day));
  const first = rows[0]?.day;
  const events = series.events.filter((e) => first && e.day >= first);

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={rows} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="day" tickFormatter={shortDate} minTickGap={40} tick={{ fill: "var(--muted)", fontSize: 11 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
          <YAxis tickFormatter={(v) => fmtNum(v)} width={52} tick={{ fill: "var(--muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip content={<ChartTooltip metric={series.metric} events={series.events} />} cursor={{ stroke: "var(--muted)", strokeDasharray: "3 3" }} />
          {events.map((e) => (
            <ReferenceLine
              key={e.id}
              x={e.day}
              stroke="var(--muted)"
              strokeDasharray="2 4"
              label={{ value: e.kind === "release" ? "♪" : e.kind[0].toUpperCase(), position: "top", fill: "var(--text-2)", fontSize: 11 }}
            />
          ))}
          <Area dataKey="band" stroke="none" fill={color} fillOpacity={0.15} isAnimationActive={false} connectNulls />
          <Line dataKey="actual" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
          <Line dataKey="estimated" stroke={color} strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} connectNulls />
          <Line dataKey="forecast" stroke={color} strokeWidth={2} strokeDasharray="2 3" dot={false} isAnimationActive={false} connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="legend">
        <span><span className="swatch" style={{ borderColor: color }} />Reported</span>
        {est.length > 0 && <span><span className="swatch dashed" style={{ borderColor: color }} />Estimated until your next upload</span>}
        {series.forecast.length > 0 && (
          <span>
            <span className="swatch dashed" style={{ borderColor: color, borderTopStyle: "dotted" }} />
            Forecast ({series.forecast_method}) <span className="swatch band" style={{ background: color }} /> 80% range
          </span>
        )}
        {events.length > 0 && <span>♪ release · P playlist · other letters = event type</span>}
      </div>
      <p className="muted small" style={{ margin: "4px 0 0" }}>{PLATFORM_LABEL[series.platform]} · {metricLabel(series.metric)}</p>
    </div>
  );
}

type TooltipProps = { active?: boolean; payload?: { payload: Row }[]; label?: string; metric: string; events: Series["events"] };

function ChartTooltip({ active, payload, label, metric, events }: TooltipProps) {
  if (!active || !payload?.length || !label) return null;
  const r = payload[0].payload;
  const evs = events.filter((e) => e.day === label);
  return (
    <div className="tooltip">
      <strong>{new Date(label + "T00:00:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" })}</strong>
      {r.actual !== undefined && <div className="t-row"><span>{metricLabel(metric)}</span><span>{Math.round(r.actual).toLocaleString()}</span></div>}
      {r.estimated !== undefined && r.actual === undefined && <div className="t-row"><span>Estimated</span><span>{Math.round(r.estimated).toLocaleString()}</span></div>}
      {r.forecast !== undefined && r.actual === undefined && r.estimated === undefined && (
        <>
          <div className="t-row"><span>Forecast</span><span>{Math.round(r.forecast).toLocaleString()}</span></div>
          {r.band && <div className="t-row muted"><span>80% range</span><span>{fmtNum(r.band[0])}–{fmtNum(r.band[1])}</span></div>}
        </>
      )}
      {evs.map((e) => (
        <div key={e.id} className="small" style={{ marginTop: 4 }}>{e.kind}: {e.title}</div>
      ))}
    </div>
  );
}
