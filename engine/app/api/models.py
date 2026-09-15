from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt

Language = Literal["en", "de", "tr", "ar", "es"]
SourceLanguage = Literal["en", "de", "tr", "ar", "es", "mixed", "und"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LocationInput(Input):
    latitude: StrictFloat | StrictInt = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: StrictFloat | StrictInt = Field(ge=-180, le=180, allow_inf_nan=False)
    accuracy: StrictFloat | StrictInt = Field(gt=0, le=50000, allow_inf_nan=False)


class ContributionInput(Input):
    nickname: str = Field(min_length=1, max_length=32)
    body: str = Field(min_length=1, max_length=2000)
    language: SourceLanguage
    inputMode: Literal["text", "voice"]
    locationToken: str = Field(max_length=2000)
    idempotencyKey: UUID
    website: str = Field(default="", max_length=0)


class ContentInput(Input):
    kind: Literal["contribution", "chronicle"]
    id: str = Field(min_length=1, max_length=200)
    language: Language


class IdInput(Input):
    id: str = Field(min_length=1, max_length=200)


# Public response contracts also serve as a final serialization boundary.
class Neighborhood(BaseModel):
    id: str
    name: str
    district: str
    aliases: list[str]
    description: str
    color: str
    center: tuple[float, float]
    geometry: dict
    boundary_version: str


class Contribution(BaseModel):
    id: str
    neighborhood_id: str
    nickname: str
    body: str
    language: SourceLanguage
    input_mode: Literal["text", "voice"]
    created_at: datetime
    diary_date: str
    demo_dataset: str | None


class Chronicle(BaseModel):
    id: str
    neighborhood_id: str
    diary_date: str
    body: str
    language: Language
    title: str
    source_ids: list[str]
    contribution_count: int
    status: Literal["pending", "generating", "published", "failed", "review"]
    demo_dataset: str | None


class Summary(BaseModel):
    neighborhood: Neighborhood
    latest: Contribution | None
    count: int
    archiveCount: int


class SessionInfo(BaseModel):
    nickname: str


class LocationResult(BaseModel):
    neighborhood: Neighborhood
    token: str


class Publication(BaseModel):
    id: str
    neighborhood_id: str


class AcceptedJob(BaseModel):
    jobId: str
    status: Literal["pending"]


class JobStatus(BaseModel):
    id: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    result: dict | None = None
    error: str | None = None
    errorStatus: int | None = None


class FeaturedChronicle(BaseModel):
    neighborhood: Neighborhood
    story: Chronicle
