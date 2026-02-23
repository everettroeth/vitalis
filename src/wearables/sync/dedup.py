"""Deduplication logic for wearable data ingestion.

Prevents storing duplicate readings when the same data arrives through
multiple paths (e.g., Garmin → Apple Health → Vitalis direct API).

Dedup keys:
    - raw_device_data:    (user_id, device_source, metric_type, date) — UNIQUE constraint
    - wearable_daily:     (user_id, date, source) — UNIQUE constraint
    - wearable_sleep:     (user_id, sleep_date, source) — UNIQUE constraint
    - wearable_activities: (user_id, source, source_activity_id) — UNIQUE constraint
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from uuid import UUID

logger = logging.getLogger("vitalis.wearables.sync.dedup")


def raw_payload_key(
    user_id: UUID, device_source: str, metric_type: str, target_date: date
) -> str:
    """Generate a dedup key for a raw device payload.

    This key matches the UNIQUE constraint on raw_device_data:
    (user_id, device_source, metric_type, date).

    Args:
        user_id:       Internal Vitalis user UUID.
        device_source: Provider slug (e.g. 'garmin').
        metric_type:   Data category (e.g. 'sleep', 'daily').
        target_date:   Date the data belongs to.

    Returns:
        Colon-separated dedup key string.
    """
    return f"{user_id}:{device_source}:{metric_type}:{target_date.isoformat()}"


def activity_key(user_id: UUID, source: str, source_activity_id: str) -> str:
    """Generate a dedup key for a wearable activity.

    Matches the UNIQUE constraint on wearable_activities:
    (user_id, source, source_activity_id).

    Args:
        user_id:            Internal Vitalis user UUID.
        source:             Provider slug.
        source_activity_id: External activity ID from the device.

    Returns:
        Dedup key string.
    """
    return f"{user_id}:{source}:{source_activity_id}"


def payload_content_hash(payload: dict) -> str:
    """Compute a content hash for detecting identical payloads.

    Used to detect when the exact same data arrives via multiple paths
    (e.g., Garmin syncs to Apple Health, then both sync to Vitalis).

    Args:
        payload: The raw API response dict.

    Returns:
        SHA-256 hex digest of the canonicalized JSON.
    """
    # Sort keys for deterministic serialization
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class InMemoryDedupCache:
    """In-process dedup cache for short-lived sync sessions.

    Not a replacement for database UNIQUE constraints — those are the
    authoritative dedup mechanism.  This cache prevents redundant API
    calls within a single sync run.

    Usage::

        cache = InMemoryDedupCache()
        if cache.is_seen(key):
            logger.debug("Skipping duplicate: %s", key)
        else:
            cache.mark_seen(key)
            # process the record
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_seen(self, key: str) -> bool:
        """Return True if this key has been processed in this session.

        Args:
            key: Dedup key (from raw_payload_key or activity_key).

        Returns:
            True if already seen.
        """
        return key in self._seen

    def mark_seen(self, key: str) -> None:
        """Record a key as processed.

        Args:
            key: Dedup key to mark.
        """
        self._seen.add(key)

    def clear(self) -> None:
        """Reset the cache."""
        self._seen.clear()

    def __len__(self) -> int:
        return len(self._seen)


def build_upsert_query(
    table: str,
    columns: list[str],
    conflict_columns: list[str],
    update_columns: list[str] | None = None,
) -> str:
    """Build a PostgreSQL INSERT ... ON CONFLICT DO UPDATE (upsert) query.

    Generates idempotent writes — safe to call multiple times with the same
    data.  On conflict, updates the non-key columns.

    Args:
        table:            Target table name.
        columns:          All columns to insert.
        conflict_columns: Columns that define the UNIQUE constraint.
        update_columns:   Columns to update on conflict (defaults to non-key columns).

    Returns:
        Parameterized SQL string.
    """
    if update_columns is None:
        update_columns = [c for c in columns if c not in conflict_columns]

    placeholders = ", ".join(f"${i + 1}" for i in range(len(columns)))
    col_list = ", ".join(columns)
    conflict_target = ", ".join(conflict_columns)

    if update_columns:
        update_set = ", ".join(
            f"{col} = EXCLUDED.{col}" for col in update_columns
        )
        update_set += ", updated_at = NOW()"
        do_clause = f"DO UPDATE SET {update_set}"
    else:
        do_clause = "DO NOTHING"

    return (
        f"INSERT INTO {table} ({col_list}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_target}) {do_clause}"
    )
