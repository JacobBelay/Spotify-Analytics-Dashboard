import { useEffect, useState } from "react";
import { api, BACKEND_DOWN } from "./api";
import type { Artist } from "./types";
import ConnectForm from "./components/ConnectForm";
import Onboarding from "./components/Onboarding";
import Dashboard from "./components/Dashboard";

type View = "connect" | "onboarding" | "dashboard";

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const [artists, setArtists] = useState<Artist[]>([]);
  const [artistId, setArtistId] = useState<number | null>(params.get("artist") ? Number(params.get("artist")) : null);
  // Coming back from the YouTube sign-in lands on the onboarding checklist.
  const [view, setView] = useState<View>(params.get("youtube") ? "onboarding" : "dashboard");
  const [flash, setFlash] = useState<string | null>(
    params.get("youtube") === "connected" ? "YouTube connected. Pulling your channel history in the background." : params.get("youtube") === "error" ? "YouTube connection didn't finish. Try again." : null,
  );
  const [loading, setLoading] = useState(true);
  const [backendDown, setBackendDown] = useState(false);

  const reload = async (select?: number) => {
    const list = await api.artists();
    setArtists(list);
    if (select) setArtistId(select);
    else if (!artistId && list.length) setArtistId(list[0].id);
    if (!list.length) setView("connect");
    setLoading(false);
  };

  useEffect(() => {
    reload().catch((e: Error) => {
      if (e.message === BACKEND_DOWN) setBackendDown(true);
      setLoading(false);
    });
    if (params.get("youtube")) window.history.replaceState({}, "", "/");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const artist = artists.find((a) => a.id === artistId) ?? null;

  return (
    <div className="app">
      <header className="topbar">
        <h1>Artist Analytics</h1>
        <span className="spacer" />
        {artists.length > 0 && (
          <select value={artistId ?? ""} onChange={(e) => { setArtistId(Number(e.target.value)); setView("dashboard"); }} aria-label="Artist">
            {artists.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        )}
        {artist && view !== "onboarding" && <button className="btn secondary" onClick={() => setView("onboarding")}>Data sources</button>}
        {artist && view !== "dashboard" && <button className="btn secondary" onClick={() => setView("dashboard")}>Dashboard</button>}
        <button className="btn" onClick={() => setView("connect")}>+ Add artist</button>
      </header>

      {backendDown && (
        <div className="banner" role="alert">
          <span aria-hidden>⚠</span>
          <span>
            <strong>The backend isn't running.</strong> You can look around, but nothing can be saved or loaded. To start it, open
            PowerShell in the <code>artist-analytics</code> folder and run <code>docker compose up</code>.
          </span>
          <button className="btn secondary" onClick={() => window.location.reload()}>Retry</button>
        </div>
      )}

      {flash && (
        <div className="banner" role="status">
          <span>{flash}</span>
          <button className="btn secondary" onClick={() => setFlash(null)}>Dismiss</button>
        </div>
      )}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : view === "connect" || !artist ? (
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
