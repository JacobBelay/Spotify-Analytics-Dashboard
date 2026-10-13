export type Platform = "spotify" | "apple_music" | "youtube";

export const PLATFORM_LABEL: Record<Platform, string> = {
  spotify: "Spotify",
  apple_music: "Apple Music",
  youtube: "YouTube",
};

export interface Artist {
  id: number;
  name: string;
  spotify_id: string | null;
  youtube_channel_id: string | null;
  apple_music_id: string | null;
  owned: boolean;
  genres: string[] | null;
  image_url: string | null;
}

export interface Freshness {
  last_day: string | null;
  days_old: number | null;
  stale: boolean;
  has_data: boolean;
}

export interface InstructionGroup {
  title: string;
  steps: string[];
}

export interface OnboardingStep {
  id: "profile" | Platform;
  title: string;
  done: boolean;
  open_url?: string;
  instructions?: InstructionGroup[];
  freshness?: Freshness;
  available?: boolean;
  connect_url?: string | null;
  account_name?: string | null;
}

export interface Reminder {
  platform: Platform;
  days_old: number;
  message: string;
}

export interface Onboarding {
  artist_id: number;
  steps: OnboardingStep[];
  complete: boolean;
  reminders: Reminder[];
  recent_uploads: { platform: Platform; file_type: string; filename: string | null; rows: number; first_day: string | null; last_day: string | null; at: string }[];
}

export interface UploadPreview {
  file_type: "timeline" | "songs" | "playlists" | "unknown";
  platform: Platform | null;
  columns_found: Record<string, string>;
  ignored_columns: string[];
  warnings: string[];
  days?: number;
  first_day?: string;
  last_day?: string;
  metrics?: string[];
  songs?: number;
  playlists?: number;
  top_songs?: Record<string, unknown>[];
  top_playlists?: Record<string, unknown>[];
  release_match?: number | null;
}

export interface Growth {
  days: number;
  current: number | null;
  previous: number | null;
  change_pct: number | null;
}

export interface MetricFacts {
  platform: Platform;
  metric: string;
  kind: "daily" | "total";
  latest: { day: string; value: number };
  history_days: number;
  growth_7d: Growth;
  growth_28d: Growth;
  trend_pct_per_week: number | null;
  anomalies: { day: string; type: "spike" | "dip"; value: number; expected: number; score: number }[];
  event_lift: { day: string; kind: string; title: string | null; avg_before: number; avg_after: number; lift_pct: number | null }[];
}

export interface Summary {
  as_of: string;
  freshness: Record<Platform, Freshness>;
  metrics: MetricFacts[];
  cross_platform_lead_lag: Record<string, { best_lag_days: number; correlation: number; reading: string }>;
}

export interface EventItem {
  id: number;
  day: string;
  kind: string;
  platform: Platform | null;
  magnitude: number;
  title: string | null;
  source: string;
}

export interface Series {
  platform: Platform;
  metric: string;
  kind: "daily" | "total";
  points: { day: string; value: number; estimated: boolean }[];
  forecast: { day: string; value: number; low: number; high: number }[];
  forecast_method: string | null;
  events: EventItem[];
}

export interface Available {
  platform: Platform;
  metric: string;
  kind: "daily" | "total";
  days: number;
}

export interface NewEvent {
  day: string;
  kind: string;
  platform: Platform | null;
  magnitude: number;
  title: string;
}

export interface ScenarioResult {
  platform: Platform;
  metric: string;
  method: string;
  points: { day: string; baseline: number; scenario: number; low: number; high: number }[];
  baseline_total: number;
  scenario_total: number;
  lift_pct: number;
  explanation: string | null;
}

export interface Insight {
  id: number;
  kind: "report" | "scenario" | "question";
  question: string | null;
  content: string;
  model: string;
  created_at: string;
}

export const EVENT_KINDS = ["release", "playlist", "promo", "tour", "viral", "press", "collab"] as const;
