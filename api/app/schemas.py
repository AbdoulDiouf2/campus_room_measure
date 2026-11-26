from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    owner: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    owner: str | None
    created_at: datetime
    measurement_count: int


class LineError(BaseModel):
    line: int = Field(ge=1)
    reason: str


class IngestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    filename: str
    status: Literal["pending", "running", "succeeded", "failed"]
    rows_accepted: int = Field(ge=0)
    rows_rejected: int = Field(ge=0)
    rows_duplicate: int = Field(ge=0)
    errors: list[LineError]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class StatsRow(BaseModel):
    room: str
    measurement_count: int = Field(ge=0)
    co2_avg: float
    co2_min: int
    co2_max: int
    temperature_avg: float
    humidity_avg: float
    last_measured_at: datetime
