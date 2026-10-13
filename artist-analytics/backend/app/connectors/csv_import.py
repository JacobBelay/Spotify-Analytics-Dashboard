"""Import CSV exports from Spotify for Artists and Apple Music for Artists.

Neither platform documents its export columns, and they change, so this module
does not hard-code a layout. It normalizes column names, matches them against
lists of known synonyms, and works out what kind of file it is:

  timeline  - one row per day (date + streams / listeners / followers / plays / shazams ...)
  songs     - one row per song (title + totals for the chosen date range)
  playlists - one row per playlist (name + streams, maybe a date added)

If you hit a file it can't read, add the new column name to SYNONYMS.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field

import pandas as pd

# normalized column name -> our field. Normalization = lowercase, alphanumerics only.
SYNONYMS: dict[str, list[str]] = {
    "date": ["date", "day", "datetime", "dateutc", "timestamp", "week", "period"],
    "streams": ["streams", "streamcount", "totalstreams", "plays", "totalplays", "playcount"],
    "listeners": ["listeners", "averagedailylisteners", "avgdailylisteners", "uniquelisteners", "monthlylisteners"],
    "followers": ["followers", "followercount", "totalfollowers"],
    "saves": ["saves", "savecount"],
    "playlist_adds": ["playlistadds", "playlistadd"],
    "shazams": ["shazams", "shazamcount", "shazam"],
    "radio_spins": ["radiospins", "spins"],
    "views": ["videoviews", "views"],
    "purchases": ["purchases", "sales"],
    # identity columns
    "song": ["song", "songtitle", "songname", "track", "tracktitle", "trackname", "title", "name"],
    "playlist": ["playlist", "playlistname", "playlisttitle"],
    "curator": ["madeby", "curator", "owner", "author"],
    "date_added": ["dateadded", "added", "addedon", "addeddate"],
    "isrc": ["isrc"],
    "artist": ["artist", "artistname"],
}

# Which fields are running totals rather than per-day counts.
TOTAL_FIELDS = {"followers"}
METRIC_FIELDS = ["streams", "listeners", "followers", "saves", "playlist_adds", "shazams", "radio_spins", "views", "purchases"]

SPOTIFY_HINTS = {"followers", "saves", "playlist_adds"}
APPLE_HINTS = {"shazams", "radio_spins", "purchases"}


def _norm(col: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(col).lower())


def _to_number(s: pd.Series) -> pd.Series:
    cleaned = s.astype(str).str.replace(r"[,\s]", "", regex=True).str.replace("%", "", regex=False)
    cleaned = cleaned.replace({"": None, "-": None, "nan": None, "None": None})
    return pd.to_numeric(cleaned, errors="coerce")


@dataclass
class ParsedCSV:
    file_type: str  # timeline | songs | playlists | unknown
    platform: str | None
    columns: dict[str, str]  # our field -> original column
    ignored_columns: list[str]
    timeline: pd.DataFrame | None = None  # day, metric, value, kind
    songs: pd.DataFrame | None = None
    playlists: pd.DataFrame | None = None
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        out: dict = {
            "file_type": self.file_type,
            "platform": self.platform,
            "columns_found": self.columns,
            "ignored_columns": self.ignored_columns,
            "warnings": self.warnings,
        }
        if self.timeline is not None and not self.timeline.empty:
            t = self.timeline
            out["days"] = int(t["day"].nunique())
            out["first_day"] = t["day"].min().date().isoformat()
            out["last_day"] = t["day"].max().date().isoformat()
            out["metrics"] = sorted(t["metric"].unique().tolist())
        if self.songs is not None:
            out["songs"] = int(len(self.songs))
            out["top_songs"] = _records(self.songs.head(5))
        if self.playlists is not None:
            out["playlists"] = int(len(self.playlists))
            out["top_playlists"] = _records(self.playlists.head(5))
        return out


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _read(raw: bytes) -> pd.DataFrame:
    text = raw.decode("utf-8-sig", errors="replace")
    # Some exports put a title line or two above the header. Find the first line
    # that looks like a header (has a delimiter and at least one known column).
    lines = text.splitlines()
    known = {s for syns in SYNONYMS.values() for s in syns}
    start = 0
    for i, line in enumerate(lines[:10]):
        cells = [_norm(c) for c in re.split(r"[,;\t]", line)]
        if len(cells) > 1 and any(c in known for c in cells):
            start = i
            break
    body = "\n".join(lines[start:])
    return pd.read_csv(io.StringIO(body), sep=None, engine="python")


def _map_columns(df: pd.DataFrame) -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    normed = {c: _norm(c) for c in df.columns}
    # Exact synonym match first, in synonym priority order.
    for fld, syns in SYNONYMS.items():
        for syn in syns:
            for orig, n in normed.items():
                if orig not in used and n == syn and fld not in mapping:
                    mapping[fld] = orig
                    used.add(orig)
    # Then prefix/contains match for leftovers, e.g. "Streams (28 days)".
    for orig, n in normed.items():
        if orig in used:
            continue
        for fld in METRIC_FIELDS + ["date"]:
            if fld in mapping:
                continue
            if any(n.startswith(s) for s in SYNONYMS[fld] if len(s) > 4):
                mapping[fld] = orig
                used.add(orig)
                break
    ignored = [c for c in df.columns if c not in used]
    return mapping, ignored


def _guess_platform(fields: set[str], hint: str | None, filename: str) -> str | None:
    if hint in ("spotify", "apple_music"):
        return hint
    name = filename.lower()
    if "spotify" in name:
        return "spotify"
    if "apple" in name:
        return "apple_music"
    if fields & APPLE_HINTS:
        return "apple_music"
    if fields & SPOTIFY_HINTS:
        return "spotify"
    return None


def parse_export(raw: bytes, filename: str = "", platform_hint: str | None = None) -> ParsedCSV:
    try:
        df = _read(raw)
    except Exception as e:  # noqa: BLE001
        return ParsedCSV("unknown", platform_hint, {}, [], warnings=[f"Couldn't read this file as CSV: {e}"])

    df = df.dropna(how="all")
    mapping, ignored = _map_columns(df)
    fields = set(mapping)
    metrics = [f for f in METRIC_FIELDS if f in fields]
    platform = _guess_platform(fields, platform_hint, filename)
    parsed = ParsedCSV("unknown", platform, mapping, ignored)

    if platform is None:
        parsed.warnings.append("Couldn't tell which platform this is from; choose Spotify or Apple Music.")

    if "playlist" in fields:
        parsed.file_type = "playlists"
        out = pd.DataFrame({"playlist": df[mapping["playlist"]].astype(str)})
        if "curator" in fields:
            out["curator"] = df[mapping["curator"]].astype(str)
        for m in metrics:
            out[m] = _to_number(df[mapping[m]])
        if "date_added" in fields:
            out["date_added"] = pd.to_datetime(df[mapping["date_added"]], errors="coerce", format="mixed")
        sort_col = "streams" if "streams" in out else out.columns[-1]
        parsed.playlists = out.sort_values(sort_col, ascending=False, na_position="last").reset_index(drop=True)
        return parsed

    if "date" in fields and metrics:
        parsed.file_type = "timeline"
        days = pd.to_datetime(df[mapping["date"]], errors="coerce", format="mixed")
        bad = int(days.isna().sum())
        if bad:
            parsed.warnings.append(f"Skipped {bad} rows with unreadable dates.")
        frames = []
        for m in metrics:
            vals = _to_number(df[mapping[m]])
            f = pd.DataFrame({"day": days, "value": vals}).dropna()
            f["metric"] = m
            f["kind"] = "total" if m in TOTAL_FIELDS else "daily"
            frames.append(f)
        tl = pd.concat(frames, ignore_index=True)
        tl["day"] = tl["day"].dt.normalize()
        # Duplicate days (e.g. hourly rows) collapse: sum daily counts, keep the last total.
        daily = tl[tl["kind"] == "daily"].groupby(["day", "metric", "kind"], as_index=False)["value"].sum()
        totals = tl[tl["kind"] == "total"].sort_values("day").groupby(["day", "metric", "kind"], as_index=False)["value"].last()
        parsed.timeline = pd.concat([daily, totals], ignore_index=True).sort_values(["metric", "day"]).reset_index(drop=True)
        span = (parsed.timeline["day"].max() - parsed.timeline["day"].min()).days + 1
        if span > 7 and parsed.timeline["day"].nunique() < span * 0.5:
            parsed.warnings.append("Rows look weekly or monthly rather than daily; trends will be coarser.")
        return parsed

    if "song" in fields and metrics:
        parsed.file_type = "songs"
        out = pd.DataFrame({"song": df[mapping["song"]].astype(str)})
        if "isrc" in fields:
            out["isrc"] = df[mapping["isrc"]].astype(str)
        for m in metrics:
            out[m] = _to_number(df[mapping[m]])
        sort_col = "streams" if "streams" in out else metrics[0]
        parsed.songs = out.sort_values(sort_col, ascending=False, na_position="last").reset_index(drop=True)
        return parsed

    parsed.warnings.append(
        "Didn't recognize this layout. Expected a date column plus streams/listeners/followers "
        "(timeline), a song column plus stats (songs), or a playlist column (playlists)."
    )
    return parsed


def title_overlap(song_titles: list[str], known_titles: list[str]) -> float | None:
    """Share of songs in the file that match a release title we know from the API.

    Used as a sanity check that someone uploaded the right artist's export.
    """
    if not song_titles or not known_titles:
        return None
    clean = lambda t: re.sub(r"\s*[\(\[].*?[\)\]]", "", t).strip().lower()  # drop "(feat. X)", "[Remix]"
    known = {clean(t) for t in known_titles}
    hits = sum(1 for t in song_titles if clean(t) in known)
    return hits / len(song_titles)
