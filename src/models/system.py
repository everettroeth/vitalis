"""Pydantic models for system tables: ingestion jobs, audit log, deletion/export requests, lookups."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from src.models.base import VitalisBase


# ---------- Enums ----------

class JobType(str, Enum):
    daily_sync = "daily_sync"
    backfill = "backfill"
    document_parse = "document_parse"
    export = "export"
    deletion = "deletion"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    dead_letter = "dead_letter"


class AuditAction(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    SOFT_DELETE = "SOFT_DELETE"
    EXPORT = "EXPORT"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"


# ---------- Ingestion Jobs ----------

class IngestionJobRead(VitalisBase):
    job_id: uuid.UUID
    user_id: uuid.UUID | None = None
    source: str | None = None
    job_type: JobType
    status: JobStatus = JobStatus.queued
    priority: int = Field(default=5, ge=1, le=10)
    payload: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    queued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    next_retry_at: datetime | None = None


# ---------- Audit Log ----------

class AuditLogRead(VitalisBase):
    audit_id: uuid.UUID
    user_id: uuid.UUID | None = None
    action_by: uuid.UUID | None = None
    table_name: str
    record_id: uuid.UUID
    action: AuditAction
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: uuid.UUID | None = None
    created_at: datetime


# ---------- Deletion Requests ----------

class DeletionRequestCreate(VitalisBase):
    pass  # created from auth context — no user input needed


class DeletionRequestRead(VitalisBase):
    request_id: uuid.UUID
    user_id: uuid.UUID | None = None
    user_email_snapshot: str | None = None
    requested_at: datetime
    grace_period_ends_at: datetime
    status: str
    completed_at: datetime | None = None
    tables_deleted: list[str] | None = None


# ---------- Data Export Requests ----------

class DataExportRequestCreate(VitalisBase):
    format: str = "json"  # json | csv


class DataExportRequestRead(VitalisBase):
    export_id: uuid.UUID
    user_id: uuid.UUID
    requested_at: datetime
    status: str
    format: str
    s3_key: str | None = None
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    file_size_bytes: int | None = None


# ---------- Lookup Tables ----------

class DataSourceRead(VitalisBase):
    source_id: str
    display_name: str
    category: str
    adapter_class: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class ActivityTypeRead(VitalisBase):
    type_id: str
    display_name: str
    category: str
    met_estimate: float | None = None
    created_at: datetime
