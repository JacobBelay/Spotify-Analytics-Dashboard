/**
 * UploadBox.tsx — drag-and-drop CSV import with a confirmation preview.
 *
 * NEW TO REACT? This introduces `useRef`. State is for values you render;
 * a ref is for holding onto something without triggering a re-render — here,
 * the hidden <input type="file"> so a click on the pretty drop zone can
 * forward to it. Changing a ref never re-renders; changing state always does.
 */

import { useRef, useState } from "react";
import { api } from "../api";
import type { Platform, UploadPreview } from "../types";
import { PLATFORM_LABEL } from "../types";
import { metricLabel } from "../format";

/**
 * Drop a CSV → we parse it and show what we found (dry run) → user confirms → import.
 * The platform is known from which step the box sits in, so the user never has to pick it.
 */
export default function UploadBox({ artistId, platform, onImported }: { artistId: number; platform: Platform; onImported: () => void }) {
  const [over, setOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<UploadPreview | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // `over` drives the `.dropzone.over` sky-blue highlight while dragging.
  // `input` will point at the real DOM node after the first render.
  const input = useRef<HTMLInputElement>(null);

  const inspect = async (f: File) => {
    setFile(f);
    setStatus(null);
    setBusy(true);
    try {
      // dryRun = true: the server parses and reports, but saves nothing.
      const res = await api.upload(artistId, f, platform, true);
      setPreview(res.preview);
    } catch (e) {
      setStatus(`Couldn't read that file: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!file) return;
    setBusy(true);
    try {
      // dryRun = false — this one actually writes.
      const res = await api.upload(artistId, file, platform, false);
      setStatus(`Imported ${res.imported_rows?.toLocaleString()} rows from ${file.name}.`);
      setPreview(null);
      setFile(null);
      onImported();
    } catch (e) {
      setStatus(`Import failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div
        className={`dropzone ${over ? "over" : ""}`}
        role="button"
        tabIndex={0}
        // `.current` is the DOM node the ref is attached to. `?.` guards the
        // first render, when it is still null.
        onClick={() => input.current?.click()}
        // Because this is a <div> pretending to be a button, the keyboard
        // handling that a real <button> gives free has to be written by hand:
        // role, tabIndex, and Enter/Space. Prefer a real button where you can.
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        // preventDefault() on dragover and drop is mandatory — without it the
        // browser navigates away and opens the file instead.
        onDragOver={(e) => { e.preventDefault(); setOver(true); }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const f = e.dataTransfer.files[0];
          if (f) inspect(f);
        }}
      >
        <strong>Drop your {PLATFORM_LABEL[platform]} CSV here</strong>
        <div className="muted small">or click to choose a file. Nothing is saved until you confirm.</div>
        {/* The real file input, hidden because it can't be styled well.
            `ref={input}` is what connects it to the useRef above. */}
        <input ref={input} type="file" accept=".csv,text/csv" hidden onChange={(e) => e.target.files?.[0] && inspect(e.target.files[0])} />
      </div>

      {busy && <p className="muted small">Reading…</p>}

      {preview && (
        <div className="preview">
          {preview.file_type === "unknown" ? (
            <p className="err">We couldn't recognize this file. Make sure it's an export from {PLATFORM_LABEL[platform]} for Artists.</p>
          ) : (
            // <>…</> is a Fragment: it groups siblings without adding a
            // wrapper <div> to the page, which would disturb the layout.
            <>
              <h3>
                Found a {preview.file_type} export
                {preview.file_type === "timeline" && preview.days ? ` · ${preview.days.toLocaleString()} days` : ""}
                {preview.songs ? ` · ${preview.songs} songs` : ""}
                {preview.playlists ? ` · ${preview.playlists} playlists` : ""}
              </h3>
              {preview.first_day && (
                <p className="small">
                  {preview.first_day} → {preview.last_day} · {preview.metrics?.map(metricLabel).join(", ")}
                </p>
              )}
              {preview.top_songs && <SmallTable rows={preview.top_songs} />}
              {preview.top_playlists && <SmallTable rows={preview.top_playlists} />}
            </>
          )}
          {preview.warnings.map((w) => (
            <div key={w} className="warn">{w}</div>
          ))}
          {preview.ignored_columns.length > 0 && <p className="muted small">Ignored columns: {preview.ignored_columns.join(", ")}</p>}
          <div className="row" style={{ marginTop: 8 }}>
            <button className="btn" disabled={busy || preview.file_type === "unknown"} onClick={confirm}>Import</button>
            <button className="btn secondary" onClick={() => { setPreview(null); setFile(null); }}>Cancel</button>
          </div>
        </div>
      )}
      {status && <p className="small">{status}</p>}
    </div>
  );
}

// Renders any array of flat objects as a table by reading the column names
// off the first row.
function SmallTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return null;
  const cols = Object.keys(rows[0]);
  return (
    <table className="data">
      <thead>
        <tr>{cols.map((c) => <th key={c}>{metricLabel(c)}</th>)}</tr>
      </thead>
      <tbody>
        {/* Using the array index as a key is acceptable only because these
            rows are read-only and never reordered or filtered. Anywhere else,
            use a real id. */}
        {rows.map((r, i) => (
          <tr key={i}>
            {cols.map((c) => (
              <td key={c}>{typeof r[c] === "number" ? (r[c] as number).toLocaleString() : String(r[c] ?? "").slice(0, 40)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
