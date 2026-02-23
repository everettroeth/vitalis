"""Garmin Connect adapter using Garth library (unofficial API).

Uses stored OAuth tokens at ~/.garth for authentication.
No developer account needed — works with regular Garmin Connect login.
"""

import logging
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import garth
from garth.data import (
    SleepData, HRVData, DailySummary,
    BodyBatteryData, DailyHeartRate,
)

from src.wearables.base import (
    NormalizedSleep, NormalizedDaily, NormalizedActivity,
)

logger = logging.getLogger(__name__)


class GarminGarthAdapter:
    """Live Garmin adapter using garth library."""

    SOURCE_ID = "garmin"

    def __init__(self, token_path: str = "~/.garth"):
        self.token_path = token_path
        self._authenticated = False

    def authenticate(self) -> bool:
        try:
            garth.resume(self.token_path)
            self._authenticated = True
            logger.info("Garmin garth auth successful")
            return True
        except Exception as e:
            logger.error(f"Garmin auth failed: {e}")
            return False

    def get_sleep(self, target_date: date) -> NormalizedSleep | None:
        """Pull sleep data for a given date from Garmin Connect."""
        try:
            sleep = SleepData.get(target_date)
            dto = sleep.daily_sleep_dto
            if not dto:
                return None

            return NormalizedSleep(
                user_id=UUID("00000000-0000-0000-0000-000000000000"),
                sleep_date=target_date,
                source=self.SOURCE_ID,
                sleep_start=None,  # Would need timestamp conversion
                sleep_end=None,
                total_sleep_minutes=dto.sleep_time_seconds // 60 if dto.sleep_time_seconds else None,
                deep_minutes=dto.deep_sleep_seconds // 60 if dto.deep_sleep_seconds else None,
                light_minutes=dto.light_sleep_seconds // 60 if dto.light_sleep_seconds else None,
                rem_minutes=dto.rem_sleep_seconds // 60 if dto.rem_sleep_seconds else None,
                awake_minutes=dto.awake_sleep_seconds // 60 if dto.awake_sleep_seconds else None,
                sleep_score=dto.sleep_scores.overall.value if dto.sleep_scores else None,
                interruptions=dto.awake_count,
                avg_respiratory_rate=dto.average_respiration_value,
                avg_hrv_ms=None,  # Comes from HRV endpoint
                extended_metrics={
                    "sleep_stress": dto.avg_sleep_stress,
                    "rem_pct": dto.sleep_scores.rem_percentage.value if dto.sleep_scores else None,
                    "deep_pct": dto.sleep_scores.deep_percentage.value if dto.sleep_scores else None,
                    "light_pct": dto.sleep_scores.light_percentage.value if dto.sleep_scores else None,
                    "qualifier": dto.sleep_scores.overall.qualifier_key if dto.sleep_scores else None,
                },
                raw_payload=dto.__dict__ if hasattr(dto, '__dict__') else {},
            )
        except Exception as e:
            logger.error(f"Failed to get sleep for {target_date}: {e}")
            return None

    def get_hrv(self, target_date: date) -> dict | None:
        """Pull HRV data for a given date."""
        try:
            hrv = HRVData.get(target_date)
            if not hrv or not hrv.hrv_summary:
                return None
            s = hrv.hrv_summary
            return {
                "weekly_avg_ms": s.weekly_avg,
                "last_night_avg_ms": s.last_night_avg,
                "last_night_5min_high_ms": s.last_night_5_min_high,
                "status": s.status,
            }
        except Exception as e:
            logger.error(f"Failed to get HRV for {target_date}: {e}")
            return None

    def get_daily(self, target_date: date) -> NormalizedDaily | None:
        """Pull daily summary from Garmin Connect."""
        try:
            daily = DailySummary.get(target_date)
            if not daily:
                return None

            return NormalizedDaily(
                user_id=UUID("00000000-0000-0000-0000-000000000000"),
                date=target_date,
                source=self.SOURCE_ID,
                resting_hr_bpm=daily.resting_heart_rate,
                steps=daily.total_steps,
                active_calories_kcal=daily.active_kilocalories,
                total_calories_kcal=daily.total_kilocalories if hasattr(daily, 'total_kilocalories') else None,
                stress_avg=daily.average_stress_level,
                extended_metrics={
                    "body_battery_high": getattr(daily, 'body_battery_highest_value', None),
                    "body_battery_low": getattr(daily, 'body_battery_lowest_value', None),
                    "floors_ascended": getattr(daily, 'floors_ascended', None),
                    "floors_descended": getattr(daily, 'floors_descended', None),
                },
                raw_payload=daily.__dict__ if hasattr(daily, '__dict__') else {},
            )
        except Exception as e:
            logger.error(f"Failed to get daily for {target_date}: {e}")
            return None

    def backfill(self, start_date: date, end_date: date) -> list[dict]:
        """Pull historical data for a date range."""
        results = []
        current = start_date
        while current <= end_date:
            sleep = self.get_sleep(current)
            hrv = self.get_hrv(current)
            daily = self.get_daily(current)
            results.append({
                "date": current,
                "sleep": sleep,
                "hrv": hrv,
                "daily": daily,
            })
            current += timedelta(days=1)
        return results
