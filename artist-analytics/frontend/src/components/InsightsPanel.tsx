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

  useEffect(() => {
    api.insights(artistId).then(setItems).catch(() => setItems([]));
  }, [artistId]);

  const run = async (kind: "report" | "ask", question?: string) => {
    setBusy(kind);
    setError(null);
    try {
      const ins = kind === "report" ? await api.report(artistId) : await api.ask(artistId, question!);
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
        <h2 style={{ margin: 0 }}>Claude's analysis</h2>
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
        <button className="btn secondary" disabled={busy !== null || !q.trim()}>{busy === "ask" ? "Thinking…" : "Ask"}</button>
      </form>
      <div className="row" style={{ marginTop: 6 }}>
        {SUGGESTIONS.map((s) => (
          <button key={s} className="pill" style={{ cursor: "pointer" }} onClick={() => run("ask", s)} disabled={busy !== null}>{s}</button>
        ))}
      </div>
      {error && <p className="err small">{error}</p>}
      {items.length === 0 && <p className="muted small" style={{ marginTop: 12 }}>No reports yet. Generate one to get Claude's read on your trends.</p>}
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
