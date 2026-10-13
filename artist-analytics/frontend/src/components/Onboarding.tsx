import { useEffect, useState } from "react";
import { api } from "../api";
import type { Artist, Onboarding as OnboardingT, OnboardingStep } from "../types";
import UploadBox from "./UploadBox";

/**
 * The guided flow: each platform step has a button that opens the artist
 * portal in a new tab, the export steps to follow there, and the drop box to
 * come back to. The checklist refreshes after every import.
 */
export default function Onboarding({ artist, onDone }: { artist: Artist; onDone: () => void }) {
  const [data, setData] = useState<OnboardingT | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.onboarding(artist.id).then(setData).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [artist.id]);

  if (error) return <p className="err">{error}</p>;
  if (!data) return <p className="muted">Loading…</p>;

  return (
    <div className="grid">
      <div className="card">
        <div className="row">
          {artist.image_url && <img src={artist.image_url} alt="" width={48} height={48} style={{ borderRadius: 8 }} />}
          <div>
            <h2 style={{ margin: 0 }}>Get {artist.name}'s data in</h2>
            <p className="muted small" style={{ margin: 0 }}>
              Spotify and Apple don't let apps pull your artist stats directly, so you export them from their artist sites and
              drop them here. The first upload brings in your full history; after that, a quick weekly upload keeps things
              current.
            </p>
          </div>
        </div>
      </div>

      <div className="steps">
        {data.steps.map((s, i) => (
          <div key={s.id} className={`card step ${s.done ? "done" : ""}`}>
            <div className="step-num" aria-label={s.done ? "done" : `step ${i + 1}`}>{s.done ? "✓" : i + 1}</div>
            <StepBody step={s} artistId={artist.id} onChange={load} />
          </div>
        ))}
      </div>

      <div className="row">
        <button className="btn" onClick={onDone}>{data.complete ? "Go to dashboard" : "Skip for now → dashboard"}</button>
        <span className="muted small">You can come back here any time from "Data sources".</span>
      </div>
    </div>
  );
}

function StepBody({ step, artistId, onChange }: { step: OnboardingStep; artistId: number; onChange: () => void }) {
  const fresh = step.freshness;
  const status = fresh?.has_data ? (
    <span className="pill">
      Latest data: {fresh.last_day} ({fresh.days_old} days ago){fresh.stale ? " · update needed" : ""}
    </span>
  ) : null;

  if (step.id === "profile") {
    return (
      <div>
        <h3>{step.title}</h3>
        <p className="muted small">Done. Your releases are on the timeline.</p>
      </div>
    );
  }

  if (step.id === "youtube") {
    return (
      <div>
        <h3>{step.title}</h3>
        {step.done ? (
          <p className="small">Connected as <strong>{step.account_name}</strong>. Daily views, watch time and subscribers update automatically. {status}</p>
        ) : step.available ? (
          <>
            <p className="muted small">Sign in with the Google account that owns your channel. We only ask for read-only analytics access.</p>
            <a className="btn" href={step.connect_url ?? "#"}>Connect YouTube</a>
          </>
        ) : (
          <p className="muted small">
            YouTube sign-in isn't set up on this server yet (the admin needs to add a Google OAuth client to .env). Public
            subscriber and view counts still update daily if a channel link was added.
          </p>
        )}
      </div>
    );
  }

  // Spotify / Apple: open portal → follow steps → drop file
  const label = step.id === "spotify" ? "Spotify for Artists" : "Apple Music for Artists";
  return (
    <div>
      <div className="row">
        <h3 style={{ margin: 0 }}>{step.title}</h3>
        {status}
      </div>
      <div className="row" style={{ margin: "8px 0" }}>
        <a className="btn secondary" href={step.open_url} target="_blank" rel="noreferrer">Open {label} ↗</a>
        <span className="muted small">Opens in a new tab. Log in there, then follow these steps:</span>
      </div>
      <div className="instructions">
        {step.instructions?.map((g) => (
          <div key={g.title}>
            <strong className="small">{g.title}</strong>
            <ol className="small">
              {g.steps.map((t) => <li key={t}>{t}</li>)}
            </ol>
          </div>
        ))}
      </div>
      <UploadBox artistId={artistId} platform={step.id} onImported={onChange} />
    </div>
  );
}
