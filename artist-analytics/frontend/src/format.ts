export const fmtNum = (n: number | null | undefined): string => {
  if (n === null || n === undefined || !isFinite(n)) return "–";
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (a >= 1e4) return (n / 1e3).toFixed(1) + "K";
  return Math.round(n).toLocaleString();
};

export const fmtPct = (p: number | null | undefined): string =>
  p === null || p === undefined ? "–" : `${p > 0 ? "+" : ""}${p.toFixed(1)}%`;

export const metricLabel = (m: string): string =>
  ({
    streams: "Streams",
    listeners: "Listeners",
    followers: "Followers",
    views: "Views",
    subscribers: "Subscribers",
    watch_minutes: "Watch minutes",
    shazams: "Shazams",
    likes: "Likes",
    saves: "Saves",
    playlist_adds: "Playlist adds",
    subs_gained: "Subs gained",
    subs_lost: "Subs lost",
    radio_spins: "Radio spins",
    purchases: "Purchases",
  })[m] ?? m;

export const shortDate = (iso: string): string =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });

export const addDays = (iso: string, n: number): string => {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
};

export const today = (): string => new Date().toISOString().slice(0, 10);
