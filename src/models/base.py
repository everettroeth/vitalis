"""Shared Pydantic base models and utilities."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class VitalisBase(BaseModel):
    """Base model with shared config for all Vitalis schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class TimestampMixin(BaseModel):
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SoftDeleteMixin(BaseModel):
    deleted_at: datetime | None = None


# ---------- Generic pagination / response wrappers ----------


class PaginationParams(BaseModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    offset: int
    limit: int


class ErrorDetail(BaseModel):
    detail: str
