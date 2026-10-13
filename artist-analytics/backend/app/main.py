from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .connectors import apple_music, spotify, youtube
from .db import init_db
from .insights import claude
from .routers import artists, auth, insights, metrics, onboarding

app = FastAPI(title="Artist Analytics", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_url, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    from .ml.forecast import _load_model

    return {
        "ok": True,
        "integrations": {
            "claude": claude.enabled(),
            "youtube_public": youtube.api_key_enabled(),
            "youtube_oauth": youtube.oauth_enabled(),
            "spotify_catalog": spotify.enabled(),
            "apple_catalog": apple_music.enabled(),
        },
        "forecaster": "pytorch" if _load_model() is not None else "heuristic",
    }


for r in (artists.router, onboarding.router, auth.router, metrics.router, insights.router):
    app.include_router(r)
