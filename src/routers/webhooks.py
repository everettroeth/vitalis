"""Clerk webhook handler.

Receives ``user.created`` events from Clerk and provisions the
corresponding account + user row in Supabase so that RLS works
from the very first API call.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request

from src.config import get_settings
from src.services.supabase import get_connection

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger("vitalis.webhooks")


def _verify_svix_signature(
    payload: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
    secret: str,
) -> bool:
    """Verify the Svix webhook signature (used by Clerk).

    Clerk signs webhooks via Svix. The signature is an HMAC-SHA256 of
    ``{svix_id}.{svix_timestamp}.{body}`` using the decoded webhook secret.
    """
    import base64

    # Clerk webhook secrets are prefixed with "whsec_" and base64-encoded
    secret_bytes = base64.b64decode(secret.removeprefix("whsec_"))
    to_sign = f"{svix_id}.{svix_timestamp}.{payload.decode()}".encode()
    expected = hmac.new(secret_bytes, to_sign, hashlib.sha256).digest()
    expected_b64 = base64.b64encode(expected).decode()

    # svix_signature can contain multiple signatures separated by spaces
    # each prefixed with "v1,"
    for sig in svix_signature.split(" "):
        sig_value = sig.removeprefix("v1,")
        if hmac.compare_digest(expected_b64, sig_value):
            return True
    return False


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    svix_id: str = Header(..., alias="svix-id"),
    svix_timestamp: str = Header(..., alias="svix-timestamp"),
    svix_signature: str = Header(..., alias="svix-signature"),
) -> dict:
    """Handle Clerk webhook events.

    Currently handles:
    - ``user.created``: provisions an account + user row in Supabase
    - ``user.updated``: syncs display name / email changes
    - ``user.deleted``: soft-deletes the user row
    """
    settings = get_settings()
    body = await request.body()

    if not _verify_svix_signature(
        body, svix_id, svix_timestamp, svix_signature, settings.clerk_webhook_secret
    ):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = json.loads(body)
    event_type: str = event.get("type", "")
    data: dict = event.get("data", {})

    logger.info("Clerk webhook received: type=%s id=%s", event_type, event.get("id"))

    if event_type == "user.created":
        await _provision_user(data)
    elif event_type == "user.updated":
        await _update_user(data)
    elif event_type == "user.deleted":
        await _soft_delete_user(data)
    else:
        logger.debug("Ignoring unhandled Clerk event type: %s", event_type)

    return {"status": "ok"}


async def _provision_user(data: dict) -> None:
    """Create an account + user row for a newly registered Clerk user."""
    clerk_user_id = data.get("id", "")
    email = _extract_email(data)
    display_name = _extract_display_name(data)

    account_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with get_connection() as conn:
        # Check if user already exists (idempotent)
        existing = await conn.fetchval(
            "SELECT user_id FROM users WHERE email = $1 AND deleted_at IS NULL",
            email,
        )
        if existing:
            logger.info("User already exists for email=%s, skipping provision", email)
            return

        # Create account
        await conn.execute(
            """
            INSERT INTO accounts (account_id, account_type, subscription_tier, max_users)
            VALUES ($1, 'individual', 'free', 1)
            """,
            account_id,
        )

        # Create user — store clerk_user_id so we can map JWT sub → user_id
        await conn.execute(
            """
            INSERT INTO users (user_id, account_id, email, display_name, role)
            VALUES ($1, $2, $3, $4, 'user')
            """,
            user_id,
            account_id,
            email.lower(),
            display_name,
        )

        # Create default preferences
        await conn.execute(
            "INSERT INTO user_preferences (user_id) VALUES ($1)",
            user_id,
        )

    logger.info(
        "Provisioned user: clerk_id=%s vitalis_user_id=%s email=%s",
        clerk_user_id,
        user_id,
        email,
    )


async def _update_user(data: dict) -> None:
    """Sync profile changes from Clerk to our users table."""
    email = _extract_email(data)
    display_name = _extract_display_name(data)

    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE users
            SET display_name = $1, updated_at = NOW()
            WHERE email = $2 AND deleted_at IS NULL
            """,
            display_name,
            email.lower(),
        )
    logger.info("Updated user profile for email=%s", email)


async def _soft_delete_user(data: dict) -> None:
    """Mark a user as deleted when removed from Clerk."""
    email = _extract_email(data)
    if not email:
        logger.warning("user.deleted event missing email — cannot soft-delete")
        return

    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE users SET deleted_at = NOW(), updated_at = NOW()
            WHERE email = $1 AND deleted_at IS NULL
            """,
            email.lower(),
        )
    logger.info("Soft-deleted user for email=%s", email)


def _extract_email(data: dict) -> str:
    """Pull the primary email from Clerk's nested structure."""
    email_addresses = data.get("email_addresses", [])
    for ea in email_addresses:
        if ea.get("id") == data.get("primary_email_address_id"):
            return ea.get("email_address", "")
    # Fallback to first email
    if email_addresses:
        return email_addresses[0].get("email_address", "")
    return ""


def _extract_display_name(data: dict) -> str:
    first = data.get("first_name") or ""
    last = data.get("last_name") or ""
    name = f"{first} {last}".strip()
    return name or "User"
