# Artist Analytics

A dashboard that tracks one artist across Spotify, Apple Music and YouTube. It stores daily stats in Postgres, analyzes trends with pandas, forecasts "what if" scenarios with PyTorch, and has Claude explain what's going on.

```
React + TypeScript (Vite, Recharts)  ──►  FastAPI  ──►  PostgreSQL
                                             │
               ┌─────────────────────────────┼──────────────────────────────┐
         connectors                     analytics                        insights
  YouTube Data + Analytics (OAuth)   pandas trends, spikes,      Claude: trend reports,
  Spotify / Apple catalog (releases)  release lift, lead/lag     scenario explanations, Q&A
  CSV import (S4A / Apple exports)   PyTorch scenario forecaster
```

## Where the data comes from (and why)

| Platform | How | What you get |
|---|---|---|
| **YouTube** | Artist clicks **Connect YouTube** (Google OAuth, read-only) | Daily views, watch time, likes, subscribers gained and lost, with up to 3 years of history on first connect. Updates automatically. |
| **Spotify** | Artist exports CSVs from **Spotify for Artists** and drops them in the app | Daily streams, listeners and followers, plus per-song and per-playlist stats |
| **Apple Music** | Artist exports a CSV from **Apple Music for Artists** | Plays (stored as "streams"), listeners, Shazams, radio spins |
| Spotify and Apple public APIs | Artist link | Name, photo, genres and **release dates**, which become events on the timeline |

Spotify for Artists and Apple Music for Artists have **no public API**. Since February 2026, Spotify's Web API also no longer returns artist followers, popularity or top tracks for apps in development mode. So CSV upload is the only free way to get real stream counts. The app makes this as painless as it can:

1. **Guided steps.** An "Open Spotify for Artists ↗" button, with the export steps shown next to the upload box.
2. **Auto-detection.** Timeline, songs and playlist files are recognized even when column names change. You see a preview before anything is saved.
3. **Overlap-safe.** Re-uploading overlapping dates just updates them, so weekly "last 28 days" uploads are enough after the first full-history upload.
4. **No blank charts between uploads.** Days after your last upload are filled with **estimates** (dashed line, labeled), and a reminder appears when data is more than 7 days old.

## Quick start (Windows, Mac or Linux)

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
cd artist-analytics
cp .env.example .env          # on Windows PowerShell: copy .env.example .env
docker compose up --build
```

Then:

- Load the demo artist: `docker compose exec backend python -m app.seed`
- Open **http://localhost:5173**. The dashboard shows two years of sample data, a "data is 10 days old" reminder and estimated days.
- API docs: **http://localhost:8000/docs**

Everything works without API keys. You just get a rule-based summary instead of Claude, and no live YouTube, Spotify or Apple lookups.

## Turning on each integration (`.env`)

| Setting | Where to get it | Enables |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com | Claude trend reports, scenario explanations, Q&A |
| `YOUTUBE_API_KEY` | Google Cloud Console → APIs → enable **YouTube Data API v3** → Credentials → API key | Public subscriber and view counts, @handle lookup |
| `YOUTUBE_OAUTH_CLIENT_ID/SECRET` | Same project → enable **YouTube Analytics API** → OAuth client ID (type "Web"). Redirect URI: `http://localhost:8000/api/auth/youtube/callback` | The **Connect YouTube** button |
| `SPOTIFY_CLIENT_ID/SECRET` | developer.spotify.com dashboard (a Premium account is required for dev mode) | Artist profile and release dates |
| `APPLE_MUSIC_TEAM_ID/KEY_ID/PRIVATE_KEY_PATH` | developer.apple.com → MusicKit key (.p8). Put the file in `backend/` and use the path `/app/yourkey.p8` | Apple profile and release dates |

While your Google OAuth app is in "Testing" mode, add the artists' Google accounts as test users.

## The forecaster

- **Heuristic (default).** Recent level × weekday pattern × damped trend × event bumps. The size of each bump is **learned from this artist's own past releases and playlist adds**, and fading bumps from recent releases are modeled so they aren't mistaken for a trend. In backtests on the sample data it was about 45% more accurate than "same as last week."
- **PyTorch (after training).** A GRU over the last 56 days, conditioned on the planned events for the next 56 days. It outputs a daily forecast with an 80% range. One global model learns from every artist in the database.

```bash
docker compose exec backend python -m app.ml.train              # train on your data
docker compose exec backend python -m app.ml.train --synthetic  # try it on demo data
```

The worker retrains every day. `GET /api/health` shows which forecaster is active, and the `model_runs` table records the model's accuracy (MAPE) against a seasonal-naive baseline, so you can check that it's actually better.

**What-if scenarios:** add future circumstances (release, playlist, promo, tour, press, collab), and the app compares the forecast with and without them, then Claude explains the result. **Save as plan** puts them on the timeline so every later forecast includes them.

## How Claude is used

Claude never sees raw rows. It gets the fact sheet the backend computes (`GET /api/artists/{id}/summary`): growth over 7 and 28 days, weekly trend, spikes and dips, lift from each release and playlist add, weekday patterns, **which platform moves first** (e.g. "YouTube tends to move 3 days before Spotify"), data freshness, top songs and playlists, and forecasts. The system prompt (`backend/app/insights/claude.py`) tells it to cite numbers, separate correlation from cause, give predictions with confidence levels, and flag stale or estimated data. Every report is saved in the `insights` table.

## Development without Docker

```bash
# backend (needs a local Postgres, or set DATABASE_URL)
cd backend
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest

# frontend
cd frontend
npm install
npm run dev        # proxies /api to localhost:8000
```

## Project layout

```
backend/app/
  connectors/   csv_import.py (auto-detecting importer), youtube.py, spotify.py, apple_music.py
  analytics/    trends.py (pandas: growth, spikes and dips, event lift, lead/lag, freshness)
  ml/           features.py, model.py (PyTorch), train.py, forecast.py (+ heuristic fallback)
  insights/     claude.py (prompts + no-key fallback)
  routers/      artists, onboarding (checklist + upload), auth (YouTube OAuth), metrics, insights
  jobs/daily.py worker: YouTube snapshots, release refresh, retraining
  seed.py       demo artist · synthetic.py realistic fake data
frontend/src/
  components/   ConnectForm, Onboarding, UploadBox, Dashboard, KpiRow, TrendChart, ScenarioPanel, InsightsPanel
```

## Before putting this online

- **Add user accounts.** Right now anyone who can reach the app sees every artist. Add login (e.g. Auth0, Clerk or FastAPI-Users) and scope artists to their owners.
- **Encrypt stored YouTube refresh tokens** (`connections.refresh_token`).
- **Use migrations** (Alembic) instead of `create_all` once the schema settles.
- **Check each platform's terms** for how you store and display their data.
- **Consider a paid data provider** (Chartmetric, Soundcharts, Songstats) if you want public stats for artists who haven't uploaded anything. It plugs into `connectors/` without changing the rest.

## Status

The pandas analytics, CSV importer and heuristic forecaster have tests (`backend/tests`, 10 passing). The API routes, PyTorch training and frontend were written and syntax/type-checked but **haven't been run end to end yet**. The first `docker compose up` is that run, so expect small fixes.
