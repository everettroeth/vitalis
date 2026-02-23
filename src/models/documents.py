"""Pydantic models for documents and file uploads."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import Field

from src.models.base import SoftDeleteMixin, TimestampMixin, VitalisBase


# ---------- Enums ----------

class DocumentType(str, Enum):
    blood_work = "blood_work"
    dexa = "dexa"
    epigenetics = "epigenetics"
    imaging = "imaging"
    doctor_note = "doctor_note"
    other = "other"


class ParseStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    confirmed = "confirmed"


# ---------- Documents ----------

class DocumentBase(VitalisBase):
    document_type: DocumentType
    provider_name: str | None = None
    original_filename: str | None = None


class DocumentCreate(DocumentBase):
    s3_key: str
    file_hash: str | None = None
    file_size_bytes: int = Field(gt=0)
    mime_type: str = "application/pdf"


class DocumentUpdate(VitalisBase):
    document_type: DocumentType | None = None
    provider_name: str | None = None
    parse_status: ParseStatus | None = None
    parse_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    parse_result: dict[str, Any] | None = None
    parsed_at: datetime | None = None
    confirmed_at: datetime | None = None
    confirmed_by: uuid.UUID | None = None
    linked_record_id: uuid.UUID | None = None
    linked_record_type: str | None = None
    error_message: str | None = None


class DocumentRead(DocumentBase, TimestampMixin, SoftDeleteMixin):
    document_id: uuid.UUID
    user_id: uuid.UUID
    s3_key: str
    file_hash: str | None = None
    file_size_bytes: int
    mime_type: str
    parse_status: ParseStatus = ParseStatus.pending
    parse_confidence: Decimal | None = None
    parse_result: dict[str, Any] | None = None
    parsed_at: datetime | None = None
    confirmed_at: datetime | None = None
    confirmed_by: uuid.UUID | None = None
    linked_record_id: uuid.UUID | None = None
    linked_record_type: str | None = None
    error_message: str | None = None
