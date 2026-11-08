/**
 * ConnectForm.tsx — step 1: paste your artist profile links.
 *
 * NEW TO REACT? This is the standard shape of a React form:
 *   1. One state object holds every field's value.
 *   2. Each <input> is "controlled": `value` reads from state, `onChange`
 *      writes back to it. React is the single source of truth, so the DOM
 *      can never hold a value your code doesn't know about.
 *   3. On submit, call preventDefault() to stop the browser's own full-page
 *      form submission, then do the work yourself.
 */

import { useState, type ChangeEvent, type FormEvent } from "react";
import { api } from "../api";
import type { Artist } from "../types";

export default function ConnectForm({ onCreated }: { onCreated: (a: Artist) => void }) {
  // All four fields in one state object. Start them as "" rather than
  // undefined — an input whose value is undefined silently becomes
  // uncontrolled, and React warns about it.
  const [form, setForm] = useState({ name: "", spotify_url: "", apple_music_url: "", youtube_url: "" });
  // `busy` disables the button while the request is in flight, which is what
  // stops double submissions. `problems` holds validation messages to show.
  const [busy, setBusy] = useState(false);
  const [problems, setProblems] = useState<string[]>([]);

  // A function that *returns* a handler, so each input can share one updater:
  // onChange={set("spotify_url")}. Note `{ ...form, [k]: value }` — we build a
  // brand-new object rather than editing `form`. React compares by identity,
  // so mutating state in place would not trigger a re-render.
  const set = (k: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    // Without this the browser reloads the page and your state is gone.
    e.preventDefault();
    setBusy(true);
    setProblems([]);
    try {
      // Send only the fields the user actually filled in.
      const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v.trim()));
      const res = await api.connect(body);
      if (res.problems.length) setProblems(res.problems);
      // Tell the parent (App.tsx) it happened. The child doesn't decide what
      // comes next — it just reports, and the parent changes the screen.
      onCreated(res.artist);
    } catch (err) {
      setProblems([String((err as Error).message)]);
    } finally {
      // `finally` runs whether or not it worked, so the button can never get
      // stuck in its loading state.
      setBusy(false);
    }
  };

  return (
    // onSubmit on the <form> (rather than onClick on the button) is what makes
    // pressing Enter in any field work.
    <form className="card" onSubmit={submit} style={{ maxWidth: 640 }}>
      <h2>Step 1 · Connect your artist profiles</h2>
      <p className="muted">
        Paste the public links to your artist pages. We use them to find your name, photo and release dates, so your
        dashboard shows your releases on the timeline before you upload anything.
      </p>

      {/* `.grid` from styles.css stacks these labels with even spacing. */}
      <div className="grid" style={{ marginTop: 12 }}>
        {/* Wrapping the <input> inside its <label> links the two without
            needing matching id/htmlFor attributes — so clicking the text
            focuses the field, and screen readers read the right name. */}
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

      {/* The message text is unique, so it works as the key here. */}
      {problems.map((p) => (
        <div key={p} className="warn">{p}</div>
      ))}

      <div className="row" style={{ marginTop: 14 }}>
        {/* `disabled` drives the dimmed `.btn:disabled` style in CSS — one
            state value changes both behaviour and appearance. */}
        <button className="btn" disabled={busy}>{busy ? "Looking you up…" : "Continue"}</button>
      </div>
    </form>
  );
}
