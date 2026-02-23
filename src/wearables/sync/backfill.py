"""Historical backfill orchestrator for Vitalis wearable data.

Manages full historical imports from connected devices.  Designed to:
- Resume from where it left off (tracks last backfilled date in connected_devices.sync_cursor)
- Process in configurable batch sizes (default 30 days)
- Respect API rate limits (configurable delay between calls)
- Report progress back to the job queue

Usage::

    orchestrator = BackfillOrchestrator()
    async for progress in orchestrator.run(user_id, "garmin", start_date, end_date):
        logger.info("Backfill progress: %s", progress)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from src.wearables.adapters import get_adapter
from src.wearables.base import RawDevicePayload
from src.wearables.config_loader import get_fusion_config
from src.wearables.sync.dedup import InMemoryDedupCache, raw_payload_key

logger = logging.getLogger("vitalis.wearables.sync.backfill")


@dataclass
class BackfillProgress:
    """Progress update emitted during a backfill run.

    Attributes:
        user_id:        Internal Vitalis user UUID.
        source:         Device source slug.
        current_date:   Date currently being processed.
        processed_days: Total days processed so far.
        total_days:     Total days to process.
        records_saved:  Total records saved.
        errors:         List of error messages encountered.
        is_complete:    True when backfill finishes.
    """

    user_id: UUID
    source: str
    current_date: date
    processed_days: int
    total_days: int
    records_saved: int
    errors: list[str] = field(default_factory=list)
    is_complete: bool = False

    @property
    def pct_complete(self) -> float:
        if self.total_days == 0:
            return 100.0
        return round(self.processed_days / self.total_days * 100, 1)


@dataclass
class BackfillState:
    """Persistent state for resumable backfills.

    Stored as JSON in connected_devices.sync_cursor.

    Attributes:
        last_backfilled_date: The most recently successfully processed date.
        total_records:        Running count of saved records.
        errors:               Accumulated error log.
    """

    last_backfilled_date: date | None = None
    total_records: int = 0
    errors: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "last_backfilled_date": (
                self.last_backfilled_date.isoformat()
                if self.last_backfilled_date
                else None
            ),
            "total_records": self.total_records,
            "errors": self.errors[-50:],  # keep last 50 errors
        }

    @classmethod
    def from_json(cls, data: dict) -> "BackfillState":
        state = cls()
        if last := data.get("last_backfilled_date"):
            try:
                state.last_backfilled_date = date.fromisoformat(last)
            except ValueError:
                pass
        state.total_records = int(data.get("total_records", 0))
        state.errors = data.get("errors", [])
        return state


class BackfillOrchestrator:
    """Orchestrate historical data backfill for a user + device.

    Handles batching, rate limiting, error recovery, and progress reporting.
    All actual API calls are delegated to the device adapter.

    The backfill is resumable — if interrupted, it picks up from
    ``last_backfilled_date`` stored in the sync cursor.
    """

    def __init__(self) -> None:
        self._config = get_fusion_config()
        self._dedup = InMemoryDedupCache()

    async def run(
        self,
        user_id: UUID,
        source: str,
        access_token: str,
        start_date: date,
        end_date: date,
        existing_state: BackfillState | None = None,
        on_payload: "Callable[[RawDevicePayload], Awaitable[None]] | None" = None,
    ):
        """Run a backfill for a user+source.

        This is an async generator.  Yields BackfillProgress updates
        as processing proceeds.

        Args:
            user_id:        Internal Vitalis user UUID.
            source:         Device source slug ('garmin', 'oura', etc.).
            access_token:   Valid OAuth access token for the device.
            start_date:     Earliest date to backfill.
            end_date:       Latest date to backfill (usually today).
            existing_state: Resume state from a previous run.
            on_payload:     Optional async callback to process each payload
                            (e.g. write to database). If None, payloads are
                            just counted.

        Yields:
            BackfillProgress updates.
        """
        cfg = self._config.backfill
        rate_limit_s = cfg.rate_limit_ms / 1000.0

        # Resume from checkpoint if available
        state = existing_state or BackfillState()
        if state.last_backfilled_date and state.last_backfilled_date >= start_date:
            resume_from = state.last_backfilled_date + timedelta(days=1)
            logger.info(
                "Backfill resuming from %s for %s/%s", resume_from, user_id, source
            )
        else:
            resume_from = start_date

        if resume_from > end_date:
            logger.info("Backfill already complete for %s/%s", user_id, source)
            yield BackfillProgress(
                user_id=user_id, source=source, current_date=end_date,
                processed_days=0, total_days=0, records_saved=state.total_records,
                is_complete=True,
            )
            return

        total_days = (end_date - resume_from).days + 1
        processed_days = 0
        records_saved = state.total_records

        try:
            adapter_cls = get_adapter(source)
        except KeyError:
            logger.error("No adapter for source: %s", source)
            state.errors.append(f"No adapter for source: {source}")
            yield BackfillProgress(
                user_id=user_id, source=source, current_date=resume_from,
                processed_days=0, total_days=total_days, records_saved=records_saved,
                errors=state.errors, is_complete=True,
            )
            return

        adapter = adapter_cls()
        current = resume_from

        while current <= end_date:
            dedup_key = raw_payload_key(user_id, source, "backfill", current)
            if not self._dedup.is_seen(dedup_key):
                try:
                    async for payload in adapter.backfill(
                        user_id=user_id,
                        start_date=current,
                        end_date=min(
                            current + timedelta(days=cfg.batch_size_days - 1),
                            end_date,
                        ),
                        access_token=access_token,
                    ):
                        if on_payload:
                            try:
                                await on_payload(payload)
                            except Exception as cb_exc:
                                logger.warning(
                                    "Backfill callback error for %s/%s on %s: %s",
                                    user_id, source, payload.date, cb_exc,
                                )
                                state.errors.append(str(cb_exc))
                        records_saved += 1
                        state.total_records = records_saved

                    self._dedup.mark_seen(dedup_key)
                    state.last_backfilled_date = current

                except Exception as exc:
                    error_msg = f"Error on {current}: {exc}"
                    logger.warning("Backfill error for %s/%s: %s", user_id, source, exc)
                    state.errors.append(error_msg)

            processed_days += 1
            current += timedelta(days=cfg.batch_size_days)
            await asyncio.sleep(rate_limit_s)

            yield BackfillProgress(
                user_id=user_id,
                source=source,
                current_date=current,
                processed_days=processed_days,
                total_days=total_days,
                records_saved=records_saved,
                errors=state.errors[-5:],
                is_complete=current > end_date,
            )

        yield BackfillProgress(
            user_id=user_id,
            source=source,
            current_date=end_date,
            processed_days=processed_days,
            total_days=total_days,
            records_saved=records_saved,
            errors=state.errors,
            is_complete=True,
        )

    def get_max_start_date(self, source: str) -> date:
        """Return the furthest-back date to backfill for a given source.

        Based on backfill.{source}_max_days from fusion_config.yaml.

        Args:
            source: Device source slug.

        Returns:
            Earliest allowed backfill start date.
        """
        cfg = self._config.backfill
        max_days = cfg.max_days.get(source, 365)
        from datetime import date as _date

        return _date.today() - timedelta(days=max_days)
