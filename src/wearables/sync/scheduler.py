"""Background sync scheduler for wearable devices.

Manages per-device sync intervals and coordinates the sync workflow:
1. Determine which devices need syncing
2. Refresh OAuth tokens if needed
3. Fetch new data from device APIs
4. Write to raw_device_data
5. Trigger fusion engine for new dates
6. Update sync status in connected_devices

Sync intervals (from PLAN.md):
    Garmin:      every 5 minutes
    Oura:        every 5 minutes (webhooks + polling)
    Apple Health: daily (manual push)
    Whoop:       daily
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Coroutine, Any
from uuid import UUID

logger = logging.getLogger("vitalis.wearables.sync.scheduler")

# Default sync intervals per source (seconds)
SYNC_INTERVALS: dict[str, int] = {
    "garmin": 300,        # 5 minutes
    "oura": 300,          # 5 minutes
    "apple_health": 86400, # 24 hours (import-based)
    "whoop": 86400,       # 24 hours
}


@dataclass
class SyncJob:
    """A scheduled sync job for one user + device.

    Attributes:
        user_id:         Internal Vitalis user UUID.
        source:          Device source slug.
        access_token:    Current OAuth access token.
        refresh_token:   Refresh token for token renewal.
        token_expires_at: UTC datetime when access_token expires.
        last_sync_at:    UTC datetime of last successful sync.
        sync_dates:      Specific dates to sync (None = today + yesterday).
        priority:        Lower = higher priority. 1–10.
        created_at:      When the job was created.
    """

    user_id: UUID
    source: str
    access_token: str
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    last_sync_at: datetime | None = None
    sync_dates: list[date] | None = None
    priority: int = 5
    created_at: datetime = field(default_factory=datetime.utcnow)

    def needs_token_refresh(self, buffer_seconds: int = 300) -> bool:
        """Return True if the access token needs refreshing.

        Considers the token expired if it expires within buffer_seconds.

        Args:
            buffer_seconds: Refresh this many seconds before actual expiry.

        Returns:
            True if token should be refreshed.
        """
        if self.token_expires_at is None:
            return False
        return (self.token_expires_at - datetime.utcnow()).total_seconds() < buffer_seconds

    @property
    def target_dates(self) -> list[date]:
        """Return the dates to sync (explicit list or [yesterday, today])."""
        if self.sync_dates:
            return self.sync_dates
        today = date.today()
        return [today - timedelta(days=1), today]


@dataclass
class SyncResult:
    """Result of a single sync job execution.

    Attributes:
        user_id:       Internal Vitalis user UUID.
        source:        Device source.
        dates_synced:  Dates that were successfully synced.
        records_saved: Number of records written.
        status:        'success', 'partial', 'error'.
        error:         Error message if status == 'error'.
        synced_at:     UTC timestamp of completion.
    """

    user_id: UUID
    source: str
    dates_synced: list[date] = field(default_factory=list)
    records_saved: int = 0
    status: str = "success"
    error: str | None = None
    synced_at: datetime = field(default_factory=datetime.utcnow)


class SyncScheduler:
    """Schedule and execute wearable sync jobs.

    The scheduler maintains a queue of pending sync jobs and processes them
    concurrently up to ``max_concurrent`` at a time.

    Usage::

        scheduler = SyncScheduler(
            on_save_payload=db_writer.save_raw_payload,
            on_refresh_token=token_service.refresh,
        )
        await scheduler.enqueue(sync_job)
        await scheduler.run_all()
    """

    def __init__(
        self,
        on_save_payload: Callable | None = None,
        on_refresh_token: Callable | None = None,
        max_concurrent: int = 5,
    ) -> None:
        """Initialize the scheduler.

        Args:
            on_save_payload:  Async callback(RawDevicePayload) → None.
                              Called for each fetched record.
            on_refresh_token: Async callback(user_id, source, refresh_token) → OAuthTokens.
                              Called when a token needs refreshing.
            max_concurrent:   Maximum number of simultaneous sync jobs.
        """
        self._on_save_payload = on_save_payload
        self._on_refresh_token = on_refresh_token
        self._max_concurrent = max_concurrent
        self._queue: list[SyncJob] = []
        self._results: list[SyncResult] = []

    def enqueue(self, job: SyncJob) -> None:
        """Add a sync job to the queue.

        Jobs are sorted by priority (ascending = higher priority).

        Args:
            job: The sync job to add.
        """
        self._queue.append(job)
        self._queue.sort(key=lambda j: j.priority)
        logger.debug(
            "Enqueued sync job: %s/%s (priority=%d)", job.user_id, job.source, job.priority
        )

    async def run_all(self) -> list[SyncResult]:
        """Execute all queued sync jobs.

        Processes jobs with max_concurrent parallelism.

        Returns:
            List of SyncResult for all executed jobs.
        """
        if not self._queue:
            logger.debug("SyncScheduler: no jobs in queue")
            return []

        logger.info("SyncScheduler: running %d jobs", len(self._queue))
        semaphore = asyncio.Semaphore(self._max_concurrent)
        tasks = [self._run_job(job, semaphore) for job in self._queue]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        self._queue.clear()
        self._results = []

        for r in results:
            if isinstance(r, Exception):
                logger.error("Sync job failed with exception: %s", r)
            elif isinstance(r, SyncResult):
                self._results.append(r)

        logger.info(
            "SyncScheduler: %d jobs complete, %d errors",
            len(self._results),
            sum(1 for r in self._results if r.status == "error"),
        )
        return self._results

    async def _run_job(self, job: SyncJob, semaphore: asyncio.Semaphore) -> SyncResult:
        """Execute a single sync job.

        Args:
            job:       The sync job to execute.
            semaphore: Concurrency limiter.

        Returns:
            SyncResult.
        """
        async with semaphore:
            return await self._execute(job)

    async def _execute(self, job: SyncJob) -> SyncResult:
        """Execute the sync logic for one user+device.

        Args:
            job: The sync job.

        Returns:
            SyncResult.
        """
        from src.wearables.adapters import get_adapter

        result = SyncResult(user_id=job.user_id, source=job.source)

        # Refresh token if needed
        access_token = job.access_token
        if job.needs_token_refresh() and self._on_refresh_token and job.refresh_token:
            try:
                new_tokens = await self._on_refresh_token(
                    job.user_id, job.source, job.refresh_token
                )
                access_token = new_tokens.access_token
                logger.info(
                    "Refreshed token for %s/%s", job.user_id, job.source
                )
            except Exception as exc:
                logger.warning(
                    "Token refresh failed for %s/%s: %s. Using existing token.",
                    job.user_id, job.source, exc,
                )

        try:
            adapter_cls = get_adapter(job.source)
        except KeyError:
            result.status = "error"
            result.error = f"No adapter registered for source '{job.source}'"
            return result

        adapter = adapter_cls()
        records_saved = 0
        errors: list[str] = []

        for target_date in job.target_dates:
            try:
                # Fetch daily
                payload = await adapter.sync_daily(job.user_id, target_date, access_token)
                if self._on_save_payload:
                    await self._on_save_payload(payload)
                records_saved += 1
                result.dates_synced.append(target_date)

                # Fetch sleep
                sleep_payload = await adapter.sync_sleep(job.user_id, target_date, access_token)
                if self._on_save_payload:
                    await self._on_save_payload(sleep_payload)
                records_saved += 1

                # Fetch activities
                activity_payloads = await adapter.sync_activities(
                    job.user_id, target_date, access_token
                )
                for ap in activity_payloads:
                    if self._on_save_payload:
                        await self._on_save_payload(ap)
                    records_saved += 1

                # Optional: temperature data
                temp_payload = await adapter.sync_temperature(
                    job.user_id, target_date, access_token
                )
                if temp_payload and self._on_save_payload:
                    await self._on_save_payload(temp_payload)
                    records_saved += 1

            except Exception as exc:
                error_msg = f"Sync error on {target_date}: {exc}"
                logger.warning(
                    "Sync error for %s/%s on %s: %s",
                    job.user_id, job.source, target_date, exc,
                )
                errors.append(error_msg)

        result.records_saved = records_saved

        if errors and records_saved == 0:
            result.status = "error"
            result.error = "; ".join(errors[:3])
        elif errors:
            result.status = "partial"
        else:
            result.status = "success"

        logger.info(
            "Sync complete: %s/%s → %d records, status=%s",
            job.user_id, job.source, records_saved, result.status,
        )
        return result

    def get_interval(self, source: str) -> int:
        """Return the sync interval in seconds for a given source.

        Args:
            source: Device source slug.

        Returns:
            Sync interval in seconds.
        """
        return SYNC_INTERVALS.get(source, 3600)

    def should_sync(self, source: str, last_sync_at: datetime | None) -> bool:
        """Return True if a device is due for a sync.

        Args:
            source:       Device source slug.
            last_sync_at: UTC datetime of last successful sync (None = never).

        Returns:
            True if it's time to sync.
        """
        if last_sync_at is None:
            return True
        interval = self.get_interval(source)
        elapsed = (datetime.utcnow() - last_sync_at).total_seconds()
        return elapsed >= interval
