from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ArtistIn(BaseModel):
    name: str
    spotify_id: str | None = None
    youtube_channel_id: str | None = None
    apple_music_id: str | None = None
    owned: bool = False


class ArtistOut(ArtistIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    genres: list[str] | None = None
    image_url: str | None = None


class EventIn(BaseModel):
    day: date
    kind: str = Field(description="release | playlist | promo | tour | viral | press | collab")
    platform: str | None = None
    magnitude: float = 1.0
    title: str | None = None


class EventOut(EventIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str


class Point(BaseModel):
    day: date
    value: float
    estimated: bool = False  # filled in between CSV uploads; replaced when real data arrives


class BandPoint(BaseModel):
    day: date
    value: float
    low: float
    high: float


class SeriesOut(BaseModel):
    platform: str
    metric: str
    kind: str
    points: list[Point]
    forecast: list[BandPoint]
    forecast_method: str | None
    events: list[EventOut]


class ConnectIn(BaseModel):
    """Step 1 of onboarding: paste any of the artist's profile links."""

    name: str | None = None
    spotify_url: str | None = None
    apple_music_url: str | None = None
    youtube_url: str | None = None


class ScenarioIn(BaseModel):
    platform: str
    metric: str
    horizon: int = Field(28, ge=7, le=56)
    events: list[EventIn] = Field(default_factory=list, description="Hypothetical future circumstances")
    explain: bool = True


class ForecastPoint(BaseModel):
    day: date
    baseline: float
    scenario: float
    low: float
    high: float


class ScenarioOut(BaseModel):
    platform: str
    metric: str
    method: str
    points: list[ForecastPoint]
    baseline_total: float
    scenario_total: float
    lift_pct: float
    explanation: str | None = None


class QuestionIn(BaseModel):
    question: str


class InsightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    question: str | None
    content: str
    model: str
    created_at: datetime
