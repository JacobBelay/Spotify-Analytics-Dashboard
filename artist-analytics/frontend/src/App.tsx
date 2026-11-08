/**
 * App.tsx — the root component and the app's "router".
 *
 * NEW TO REACT? The three ideas this file demonstrates:
 *
 *   COMPONENT  A function that returns JSX (HTML-like markup). React calls it
 *              to produce a screen. `App` below is one.
 *   STATE      Values that change over time. `useState` gives you the current
 *              value plus a setter; calling the setter re-runs the component
 *              so the screen matches the new value. You never touch the DOM.
 *   EFFECT     `useEffect` runs code *after* a render — for things outside
 *              React, like fetching from the server. Rendering itself must
 *              stay side-effect free.
 *
 * This app has no routing library. Which screen you see is just a state
 * value (`view`), and the JSX at the bottom picks a component from it.
 */

// Hooks are plain functions, imported from React. Their names start with
// "use" and they may only be called at the top level of a component.
import { useEffect, useState } from "react";
import { api, BACKEND_DOWN } from "./api";
// `import type` pulls in a TypeScript type only. It vanishes at build time —
// types describe the shape of data, they are not values you can use.
import type { Artist } from "./types";
// Each of these is a component in its own file, rendered as <ConnectForm /> etc.
import ConnectForm from "./components/ConnectForm";
import Onboarding from "./components/Onboarding";
import Dashboard from "./components/Dashboard";

// A union type: `view` can only ever be one of these three strings, so a typo
// like "dashbord" is a compile error rather than a blank screen.
type View = "connect" | "onboarding" | "dashboard";

// `export default` is what lets main.tsx write `import App from "./App"`.
export default function App() {
  // Read the ?query=string from the URL, e.g. /?artist=3&youtube=connected.
  const params = new URLSearchParams(window.location.search);

  // --- State ---
  // useState(initialValue) returns [currentValue, setterFunction]. The square
  // brackets are array destructuring; the names are ours to choose.
  // Rule: call the setter, never assign to the variable.
  const [artists, setArtists] = useState<Artist[]>([]);
  const [artistId, setArtistId] = useState<number | null>(params.get("artist") ? Number(params.get("artist")) : null);

  // Which screen is showing. Coming back from the YouTube sign-in redirect
  // lands on the onboarding checklist instead of the dashboard.
  const [view, setView] = useState<View>(params.get("youtube") ? "onboarding" : "dashboard");

  // A one-off message shown in a banner, derived from the redirect result.
  const [flash, setFlash] = useState<string | null>(
    params.get("youtube") === "connected" ? "YouTube connected. Pulling your channel history in the background." : params.get("youtube") === "error" ? "YouTube connection didn't finish. Try again." : null,
  );

  // Loading and error flags are state too — that's how the UI can show a
  // spinner or a warning without any extra machinery.
  const [loading, setLoading] = useState(true);
  const [backendDown, setBackendDown] = useState(false);

  // Fetch the artist list and update state. `async`/`await` because the
  // network call returns a promise. Defined inside the component so it can
  // see the setters; passed down to children as a callback below.
  const reload = async (select?: number) => {
    const list = await api.artists();
    setArtists(list);
    if (select) setArtistId(select);
    else if (!artistId && list.length) setArtistId(list[0].id);
    if (!list.length) setView("connect");
    setLoading(false);
  };

  // useEffect(fn, deps) runs fn after render. The `deps` array controls when:
  // `[]` means "once, after the first render" — exactly right for initial
  // data loading. (Omit it entirely and it runs after *every* render, which
  // with a fetch inside becomes an infinite loop.)
  useEffect(() => {
    reload().catch((e: Error) => {
      if (e.message === BACKEND_DOWN) setBackendDown(true);
      setLoading(false);
    });
    // Strip ?youtube=... from the address bar so a refresh doesn't replay it.
    if (params.get("youtube")) window.history.replaceState({}, "", "/");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Derived value: computed fresh on every render from state above. It needs
  // no state of its own — deriving beats storing, because stored copies go
  // stale. `?? null` means "if find() returned undefined, use null".
  const artist = artists.find((a) => a.id === artistId) ?? null;

  // --- The returned JSX is what gets drawn. ---
  return (
    // `className`, not `class` — `class` is a reserved word in JavaScript.
    // These strings are the selectors defined in styles.css.
    <div className="app">
      <header className="topbar">
        {/* The wordmark is deliberately NOT the serif headline. Small, caps,
            letterspaced, with a glowing dot — it anchors the corner so the
            one big serif line on the page keeps all the weight. */}
        <span className="wordmark">Artist Analytics</span>
        {/* The flexbox spacer: pushes everything after it to the right. */}
        <span className="spacer" />

        {/* `condition && <jsx/>` renders the JSX only when the condition is
            true, and nothing when it's false. The standard way to show
            something conditionally. */}
        {artists.length > 0 && (
          // A "controlled input": its `value` comes from state and `onChange`
          // writes back to state. React owns the value, not the DOM.
          <select value={artistId ?? ""} onChange={(e) => { setArtistId(Number(e.target.value)); setView("dashboard"); }} aria-label="Artist">
            {/* Rendering a list: .map() turns an array of data into an array
                of elements. Each needs a stable, unique `key` so React can
                tell which item is which between renders. Never use the index
                if the list can reorder. */}
            {artists.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        )}

        {/* onClick takes a function. Writing `() => setView(...)` passes the
            function; writing `setView(...)` would call it during render. */}
        {artist && view !== "onboarding" && <button className="btn secondary" onClick={() => setView("onboarding")}>Data sources</button>}
        {artist && view !== "dashboard" && <button className="btn secondary" onClick={() => setView("dashboard")}>Dashboard</button>}
        <button className="btn" onClick={() => setView("connect")}>+ Add artist</button>
      </header>

      {backendDown && (
        // role="alert" tells screen readers to announce this immediately.
        // Styling alone never conveys meaning to assistive technology.
        <div className="banner" role="alert">
          {/* aria-hidden hides decoration from screen readers, so they don't
              read "warning sign" before the sentence that follows. */}
          <span aria-hidden>⚠</span>
          <span>
            <strong>The backend isn't running.</strong> You can look around, but nothing can be saved or loaded. To start it, open
            PowerShell in the <code>artist-analytics</code> folder and run <code>docker compose up</code>.
          </span>
          <button className="btn outline" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {flash && (
        <div className="banner" role="status">
          {/* Curly braces drop a JavaScript value into the markup. */}
          <span>{flash}</span>
          {/* Setting flash to null makes the `flash &&` test above fail, so
              this whole banner disappears. That is the entire mechanism. */}
          <button className="btn secondary" onClick={() => setFlash(null)}>Dismiss</button>
        </div>
      )}

      {/* Chained ternaries (`cond ? a : b`) pick one of several screens.
          Used instead of `&&` because here we need "this OR that". */}
      {loading ? (
        <p className="loading">Loading</p>
      ) : view === "connect" || !artist ? (
        // Values passed into a component are "props" — like HTML attributes,
        // but they can be any JavaScript value, functions included. Passing a
        // callback down is how a child tells its parent something happened.
        <ConnectForm
          onCreated={async (a) => {
            await reload(a.id);
            setView("onboarding");
          }}
        />
      ) : view === "onboarding" ? (
        <Onboarding artist={artist} onDone={() => setView("dashboard")} />
      ) : (
        <Dashboard artist={artist} onOpenSources={() => setView("onboarding")} />
      )}
    </div>
  );
}
