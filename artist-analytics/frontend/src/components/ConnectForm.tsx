import { useState, type ChangeEvent, type FormEvent } from "react";
import { api } from "../api";
import type { Artist } from "../types";

export default function ConnectForm({ onCreated }: { onCreated: (a: Artist) => void }) {
  const [form, setForm] = useState({ name: "", spotify_url: "", apple_music_url: "", youtube_url: "" });
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  const set = (k: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setProblems([]);
    try {
      const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v.trim()));
      const res = await api.connect(body);
      if (res.problems.length) setProblems(res.problems);
      onCreated(res.artist);
    } catch (err) {
      setProblems([String((err as Error).message)]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card" onSubmit={submit} style={{ maxWidth: 640 }}>
      <h2>Step 1 · Connect your artist profiles</h2>
      <p className="muted">
        Paste the public links to your artist pages. We use them to find your name, photo and release dates, so your
        dashboard shows your releases on the timeline before you upload anything.
      </p>
      <div className="grid" style={{ marginTop: 12 }}>
        <label className="field">
          Spotify artist link
          <input placeholder="https://open.spotify.com/artist/…" value={form.spotify_url} onChange={set("spotify_url")} />
        </label>
        <label className="field">
          Apple Music artist link <span className="muted">(optional)</span>
          <input placeholder="https://music.apple.com/us/artist/…" value={form.apple_music_url} onChange={set("apple_music_url")} />
        </label>
        <label className="field">
          YouTube channel <span className="muted">(optional)</span>
          <input placeholder="https://youtube.com/@yourchannel" value={form.youtube_url} onChange={set("youtube_url")} />
        </label>
        <label className="field">
          Artist name <span className="muted">(only needed if you skip the links)</span>
          <input value={form.name} onChange={set("name")} />
        </label>
      </div>
      {problems.map((p) => (
        <div key={p} className="warn">{p}</div>
      ))}
      <div className="row" style={{ marginTop: 14 }}>
        <button className="btn" disabled={busy}>{busy ? "Looking you up…" : "Continue"}</button>
      </div>
    </form>
  );
}
