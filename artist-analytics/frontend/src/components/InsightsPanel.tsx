/**
 * InsightsPanel.tsx — generated trend reports plus a free-text question box.
 *
 * NEW TO REACT? Note how `busy` is a *string* union rather than a boolean:
 * "report" | "ask" | null. One value tells you both whether something is
 * loading and which button started it, so the right label changes while every
 * button disables. Reach for a union whenever two booleans can't both be true.
 */

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api";
import type { Insight } from "../types";

const SUGGESTIONS = [
  "Why did streams jump last month?",
  "Which platform is growing fastest, and is it sustainable?",
  "When should I release my next single?",
  "What does YouTube activity say about next week on Spotify?",
];

export default function InsightsPanel({ artistId }: { artistId: number }) {
  const [items, setItems] = useState<Insight[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState<"report" | "ask" | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load past insights once per artist. An empty list on failure is fine
  // here — this panel is a bonus, not the point of the page.
  useEffect(() => {
    api.insights(artistId).then(setItems).catch(() => setItems([]));
  }, [artistId]);

  const run = async (kind: "report" | "ask", question?: string) => {
    setBusy(kind);
    setError(null);
    try {
      const ins = kind === "report" ? await api.report(artistId) : await api.ask(artistId, question!);
      // New array, newest first — not items.unshift(), which would mutate.
      setItems([ins, ...items]);
      if (kind === "ask") setQ("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="card">
      <div className="row">
        <p className="eyebrow ember" style={{ margin: 0 }}>Claude's analysis</p>
        <span className="spacer" style={{ flex: 1 }} />
        <button className="btn" onClick={() => run("report")} disabled={busy !== null}>{busy === "report" ? "Analyzing…" : "New trend report"}</button>
      </div>
      <form
        className="row"
        style={{ marginTop: 10 }}
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) run("ask", q.trim());
        }}
      >
        <input style={{ flex: 1, minWidth: 200 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about your numbers…" aria-label="Question" />
        <button className="btn outline" disabled={busy !== null || !q.trim()}>{busy === "ask" ? "Thinking…" : "Ask"}</button>
      </form>
      <div className="row" style={{ marginTop: 6 }}>
        {/* Reusing the `.pill` class on a <button>: same sky-blue chip look,
            but focusable and keyboard-operable because the element is right. */}
        {SUGGESTIONS.map((s) => (
          <button key={s} className="pill" style={{ cursor: "pointer" }} onClick={() => run("ask", s)} disabled={busy !== null}>{s}</button>
        ))}
      </div>
      {error && <p className="err small">{error}</p>}
      {items.length === 0 && (
        <div className="empty" style={{ padding: "26px 10px" }}>
          <p className="title">No reports yet.</p>
          <p className="small">Generate one to get Claude's read on your trends.</p>
        </div>
      )}
      {/* Real database ids, so these keys are stable even as the list grows. */}
      {items.map((i) => (
        <div key={i.id} className="insight">
          <div className="muted small">
            {i.kind === "question" ? `Q: ${i.question}` : i.kind === "scenario" ? "What-if scenario" : "Trend report"} · {new Date(i.created_at).toLocaleString()} · {i.model}
          </div>
          <ReactMarkdown>{i.content}</ReactMarkdown>
        </div>
      ))}
    </div>
  );
}
