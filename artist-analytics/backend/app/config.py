from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://analytics:analytics@localhost:5432/analytics"
    model_dir: str = "./models"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"

    youtube_api_key: str = ""
    youtube_oauth_client_id: str = ""
    youtube_oauth_client_secret: str = ""

    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    apple_music_team_id: str = ""
    apple_music_key_id: str = ""
    apple_music_private_key_path: str = ""
    apple_music_storefront: str = "us"

    ingest_interval_hours: int = 24

    # Where the API and the web app are reachable (used for OAuth redirects).
    public_api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    # Spotify/Apple data older than this triggers the "upload a fresh export" reminder.
    stale_after_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
