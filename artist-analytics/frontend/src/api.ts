import type {
  Artist,
  Available,
  EventItem,
  Insight,
  NewEvent,
  Onboarding,
  Platform,
  ScenarioResult,
  Series,
  Summary,
  UploadPreview,
} from "./types";

/**
 * A marker string used as an error message when the server can't be reached
 * at all (as opposed to the server answering with an error). App.tsx compares
 * against it to decide whether to show the "backend isn't running" banner.
 * Exported as a constant so the two files can't drift apart over a typo.
 */
export const BACKEND_DOWN = "BACKEND_DOWN";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    // fetch() only rejects when the request never completed — the server is
    // down, DNS failed, the connection dropped. An HTTP 500 is a *successful*
    // fetch, and is handled by the !res.ok branch below.
    throw new Error(BACKEND_DOWN);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => req<{ integrations: Record<string, boolean>; forecaster: string }>("/api/health"),
  artists: () => req<Artist[]>("/api/artists"),
  connect: (body: { name?: string; spotify_url?: string; apple_music_url?: string; youtube_url?: string }) =>
    req<{ artist: Artist; releases_found: number; problems: string[] }>("/api/artists/connect", json(body)),
  onboarding: (id: number) => req<Onboarding>(`/api/artists/${id}/onboarding`),
  upload: (id: number, file: File, platform: Platform | null, dryRun: boolean) => {
    const fd = new FormData();
    fd.append("file", file);
    if (platform) fd.append("platform", platform);
    fd.append("dry_run", String(dryRun));
    return req<{ preview: UploadPreview; imported: boolean; imported_rows?: number }>(`/api/artists/${id}/upload`, { method: "POST", body: fd });
  },
  summary: (id: number) => req<Summary>(`/api/artists/${id}/summary`),
  available: (id: number) => req<Available[]>(`/api/artists/${id}/available`),
  series: (id: number, platform: Platform, metric: string, days = 180) =>
    req<Series>(`/api/artists/${id}/series?platform=${platform}&metric=${metric}&days=${days}`),
  events: (id: number) => req<EventItem[]>(`/api/artists/${id}/events`),
  addEvent: (id: number, ev: NewEvent) => req<EventItem>(`/api/artists/${id}/events`, json(ev)),
  scenario: (id: number, body: { platform: Platform; metric: string; horizon: number; events: NewEvent[]; explain: boolean }) =>
    req<ScenarioResult>(`/api/artists/${id}/scenario`, json(body)),
  insights: (id: number) => req<Insight[]>(`/api/artists/${id}/insights`),
  report: (id: number) => req<Insight>(`/api/artists/${id}/insights/report`, { method: "POST" }),
  ask: (id: number, question: string) => req<Insight>(`/api/artists/${id}/insights/ask`, json({ question })),
};
