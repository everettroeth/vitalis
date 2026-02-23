"""Wearable sync infrastructure for Vitalis.

Modules:
    scheduler — Background sync scheduler (cron-based, per-device intervals)
    backfill  — Historical backfill orchestrator (batched, rate-limited)
    dedup     — Deduplication logic (source + timestamp + metric)
"""
