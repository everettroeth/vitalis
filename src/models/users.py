"""Pydantic models for identity & auth tables: accounts, users, preferences, sessions, consents."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import EmailStr, Field

from src.models.base import SoftDeleteMixin, TimestampMixin, VitalisBase


# ---------- Enums ----------

class AccountType(str, Enum):
    individual = "individual"
    household = "household"


class SubscriptionTier(str, Enum):
    free = "free"
    pro = "pro"
    family = "family"


class SubscriptionStatus(str, Enum):
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    trialing = "trialing"


class BiologicalSex(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class UserRole(str, Enum):
    user = "user"
    admin = "admin"


class OAuthProvider(str, Enum):
    google = "google"
    apple = "apple"
    microsoft = "microsoft"


class ConsentType(str, Enum):
    benchmarks = "benchmarks"
    ai_coaching = "ai_coaching"
    doctor_sharing = "doctor_sharing"
    marketing = "marketing"
    analytics = "analytics"


# ---------- Accounts ----------

class AccountBase(VitalisBase):
    account_type: AccountType = AccountType.individual
    subscription_tier: SubscriptionTier = SubscriptionTier.free
    subscription_status: SubscriptionStatus = SubscriptionStatus.active
    max_users: int = Field(default=1, ge=1, le=4)


class AccountCreate(AccountBase):
    pass


class AccountUpdate(VitalisBase):
    account_type: AccountType | None = None
    subscription_tier: SubscriptionTier | None = None
    subscription_status: SubscriptionStatus | None = None
    subscription_expires_at: datetime | None = None
    max_users: int | None = Field(default=None, ge=1, le=4)


class AccountRead(AccountBase, TimestampMixin, SoftDeleteMixin):
    account_id: uuid.UUID
    stripe_customer_id: str | None = None
    subscription_expires_at: datetime | None = None


# ---------- Users ----------

class UserBase(VitalisBase):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    date_of_birth: date | None = None
    biological_sex: BiologicalSex | None = None


class UserCreate(UserBase):
    account_id: uuid.UUID
    role: UserRole = UserRole.user


class UserUpdate(VitalisBase):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    date_of_birth: date | None = None
    biological_sex: BiologicalSex | None = None


class UserRead(UserBase, TimestampMixin, SoftDeleteMixin):
    user_id: uuid.UUID
    account_id: uuid.UUID
    role: UserRole
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None


# ---------- User Preferences ----------

class UserPreferencesBase(VitalisBase):
    weight_unit: str = "lbs"
    height_unit: str = "in"
    distance_unit: str = "miles"
    temperature_unit: str = "F"
    energy_unit: str = "kcal"
    timezone: str = "UTC"
    notifications_enabled: bool = True
    notification_prefs: dict[str, Any] = Field(default_factory=dict)
    dashboard_layout: dict[str, Any] = Field(default_factory=dict)


class UserPreferencesUpdate(VitalisBase):
    weight_unit: str | None = None
    height_unit: str | None = None
    distance_unit: str | None = None
    temperature_unit: str | None = None
    energy_unit: str | None = None
    timezone: str | None = None
    notifications_enabled: bool | None = None
    notification_prefs: dict[str, Any] | None = None
    dashboard_layout: dict[str, Any] | None = None


class UserPreferencesRead(UserPreferencesBase):
    user_id: uuid.UUID
    updated_at: datetime


# ---------- OAuth Identities ----------

class OAuthIdentityRead(VitalisBase):
    identity_id: uuid.UUID
    user_id: uuid.UUID
    provider: OAuthProvider
    provider_user_id: str
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ---------- User Sessions ----------

class UserSessionRead(VitalisBase):
    session_id: uuid.UUID
    user_id: uuid.UUID
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    expires_at: datetime
    last_active_at: datetime
    revoked_at: datetime | None = None
    revoke_reason: str | None = None


# ---------- User Consents ----------

class UserConsentCreate(VitalisBase):
    consent_type: ConsentType
    ip_address: str | None = None


class UserConsentRead(VitalisBase):
    consent_id: uuid.UUID
    user_id: uuid.UUID
    consent_type: ConsentType
    granted_at: datetime
    revoked_at: datetime | None = None
    ip_address: str | None = None
