"""Apple HealthKit adapter for Vitalis.

For web access, Apple Health data is imported via:
1. **JSON export**: Parsed from the structured HealthKit export format
2. **XML export**: Parsed from Apple Health's native XML export file
3. **Future native**: Structured to accept native HealthKit data from an iOS app

Apple does not provide a server-side API — data is exported from the device
and uploaded to Vitalis.  This adapter handles that import.

There is no OAuth flow; authentication is handled by the user's Vitalis session.
The ``authenticate()`` method is a no-op that returns a placeholder token.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import AsyncIterator
from uuid import UUID
from xml.etree import ElementTree as ET

from src.wearables.base import (
    NormalizedActivity,
    NormalizedDaily,
    NormalizedSleep,
    OAuthTokens,
    RawDevicePayload,
    WearableAdapter,
)

logger = logging.getLogger("vitalis.wearables.apple_health")

# HKQuantityTypeIdentifier → canonical Vitalis field
_HK_SLEEP_ANALYSIS = "HKCategoryTypeIdentifierSleepAnalysis"
_HK_STEP_COUNT = "HKQuantityTypeIdentifierStepCount"
_HK_HEART_RATE = "HKQuantityTypeIdentifierHeartRate"
_HK_HRV = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
_HK_RESTING_HR = "HKQuantityTypeIdentifierRestingHeartRate"
_HK_SPO2 = "HKQuantityTypeIdentifierOxygenSaturation"
_HK_RESPIRATORY = "HKQuantityTypeIdentifierRespiratoryRate"
_HK_ACTIVE_ENERGY = "HKQuantityTypeIdentifierActiveEnergyBurned"
_HK_BASAL_ENERGY = "HKQuantityTypeIdentifierBasalEnergyBurned"
_HK_DISTANCE = "HKQuantityTypeIdentifierDistanceWalkingRunning"
_HK_FLIGHTS = "HKQuantityTypeIdentifierFlightsClimbed"
_HK_SKIN_TEMP = "HKQuantityTypeIdentifierAppleSleepingWristTemperature"

# Sleep stage values from HealthKit
_SLEEP_STAGE_MAP: dict[str, str] = {
    "HKCategoryValueSleepAnalysisAsleepUnspecified": "light",
    "HKCategoryValueSleepAnalysisAsleepCore": "light",
    "HKCategoryValueSleepAnalysisAsleepDeep": "deep",
    "HKCategoryValueSleepAnalysisAsleepREM": "rem",
    "HKCategoryValueSleepAnalysisAwake": "awake",
    "HKCategoryValueSleepAnalysisInBed": "awake",
}

# HKWorkoutActivityType → Vitalis canonical activity type
_WORKOUT_TYPE_MAP: dict[str, str] = {
    "HKWorkoutActivityTypeRunning": "running",
    "HKWorkoutActivityTypeCycling": "cycling",
    "HKWorkoutActivityTypeSwimming": "swimming",
    "HKWorkoutActivityTypeWalking": "walking",
    "HKWorkoutActivityTypeTraditionalStrengthTraining": "strength_training",
    "HKWorkoutActivityTypeHighIntensityIntervalTraining": "hiit",
    "HKWorkoutActivityTypeYoga": "yoga",
    "HKWorkoutActivityTypeRowing": "rowing",
    "HKWorkoutActivityTypeElliptical": "elliptical",
    "HKWorkoutActivityTypeStairClimbing": "stair_climbing",
    "HKWorkoutActivityTypeHiking": "hiking",
    "HKWorkoutActivityTypePilates": "pilates",
}


class AppleHealthAdapter(WearableAdapter):
    """Apple HealthKit adapter (web import path).

    Processes Apple Health XML and JSON exports into canonical Vitalis models.
    Structured to accept native HealthKit data from a future iOS app via the
    same normalize_sleep() / normalize_daily() interface.
    """

    SOURCE_ID = "apple_health"
    DISPLAY_NAME = "Apple Health"

    async def authenticate(self, user_id: UUID, auth_code: str) -> OAuthTokens:
        """No OAuth flow for Apple Health — data is uploaded directly.

        Returns a placeholder token for API consistency.

        Args:
            user_id:   Internal Vitalis user UUID.
            auth_code: Not used.

        Returns:
            Placeholder OAuthTokens.
        """
        logger.debug("Apple Health: no OAuth required, returning placeholder token")
        return OAuthTokens(
            access_token="apple_health_import",
            token_type="upload",
        )

    async def refresh_token(self, user_id: UUID, refresh_token: str) -> OAuthTokens:
        """No token refresh required for Apple Health uploads."""
        return OAuthTokens(access_token="apple_health_import", token_type="upload")

    async def sync_daily(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload:
        """Not applicable for import-based sync.

        Apple Health data is pushed via upload, not pulled.
        This method is a placeholder for interface compatibility.
        """
        logger.warning(
            "Apple Health: sync_daily() called but data is import-based. "
            "Use parse_xml_export() or parse_json_export() instead."
        )
        return RawDevicePayload(
            user_id=user_id,
            device_source=self.SOURCE_ID,
            metric_type="daily",
            date=target_date,
            raw_payload={},
        )

    async def sync_sleep(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> RawDevicePayload:
        """Not applicable for import-based sync."""
        logger.warning("Apple Health: sync_sleep() not applicable for import-based integration")
        return RawDevicePayload(
            user_id=user_id,
            device_source=self.SOURCE_ID,
            metric_type="sleep",
            date=target_date,
            raw_payload={},
        )

    async def sync_activities(
        self, user_id: UUID, target_date: date, access_token: str
    ) -> list[RawDevicePayload]:
        """Not applicable for import-based sync."""
        return []

    async def backfill(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
        access_token: str,
    ) -> AsyncIterator[RawDevicePayload]:
        """Not applicable for Apple Health. Backfill via bulk XML/JSON upload."""
        logger.warning("Apple Health backfill: use parse_xml_export() for bulk import")
        return
        yield  # Make this a generator

    # ------------------------------------------------------------------
    # XML export parsing (primary import path)
    # ------------------------------------------------------------------

    def parse_xml_export(
        self, xml_bytes: bytes, user_id: UUID
    ) -> list[RawDevicePayload]:
        """Parse a full Apple Health XML export (export.xml).

        The XML contains all health records.  This method extracts and groups
        records by date and type, returning RawDevicePayloads for each day.

        Args:
            xml_bytes: Contents of Apple Health's export.xml file.
            user_id:   Internal Vitalis user UUID.

        Returns:
            List of RawDevicePayload grouped by date+type.
        """
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            logger.error("Apple Health XML parse error: %s", exc)
            raise ValueError(f"Invalid Apple Health XML: {exc}") from exc

        # Group records by date
        by_date: dict[str, dict] = {}  # date_str → collected data

        for record in root.findall("Record"):
            rec_type = record.get("type", "")
            start_str = record.get("startDate", "")
            value = record.get("value", "")
            unit = record.get("unit", "")

            if not start_str:
                continue

            try:
                dt = datetime.fromisoformat(start_str.replace(" ", "T")[:19])
                day_str = dt.date().isoformat()
            except ValueError:
                continue

            if day_str not in by_date:
                by_date[day_str] = {"records": [], "sleep_records": [], "workouts": []}

            by_date[day_str]["records"].append({
                "type": rec_type, "value": value, "unit": unit,
                "startDate": start_str, "endDate": record.get("endDate", ""),
            })

            if rec_type == _HK_SLEEP_ANALYSIS:
                by_date[day_str]["sleep_records"].append({
                    "type": rec_type, "value": value, "unit": unit,
                    "startDate": start_str, "endDate": record.get("endDate", ""),
                })

        for workout in root.findall("Workout"):
            start_str = workout.get("startDate", "")
            if start_str:
                try:
                    dt = datetime.fromisoformat(start_str.replace(" ", "T")[:19])
                    day_str = dt.date().isoformat()
                    if day_str not in by_date:
                        by_date[day_str] = {"records": [], "sleep_records": [], "workouts": []}
                    by_date[day_str]["workouts"].append({
                        "type": workout.get("workoutActivityType", ""),
                        "duration": workout.get("duration", "0"),
                        "totalEnergyBurned": workout.get("totalEnergyBurned", "0"),
                        "totalDistance": workout.get("totalDistance", "0"),
                        "startDate": start_str,
                        "endDate": workout.get("endDate", ""),
                    })
                except ValueError:
                    continue

        payloads = []
        for day_str, data in by_date.items():
            try:
                day = date.fromisoformat(day_str)
            except ValueError:
                continue

            if data["records"]:
                payloads.append(
                    RawDevicePayload(
                        user_id=user_id,
                        device_source=self.SOURCE_ID,
                        metric_type="daily",
                        date=day,
                        raw_payload=data,
                    )
                )
            if data["sleep_records"]:
                payloads.append(
                    RawDevicePayload(
                        user_id=user_id,
                        device_source=self.SOURCE_ID,
                        metric_type="sleep",
                        date=day,
                        raw_payload={"sleep_records": data["sleep_records"]},
                    )
                )

        logger.info(
            "Apple Health XML: parsed %d days from %d records",
            len(by_date), sum(len(d["records"]) for d in by_date.values()),
        )
        return payloads

    def parse_json_export(
        self, json_data: dict, user_id: UUID
    ) -> list[RawDevicePayload]:
        """Parse a structured JSON export (from iOS Shortcuts or third-party apps).

        The JSON format expected is::

            {
                "sleep": [{"startDate": "...", "endDate": "...", "value": "..."}],
                "heartRate": [...],
                "steps": [...],
                "hrv": [...],
                ...
            }

        This is the format used by apps like Health Auto Export.

        Args:
            json_data: Parsed JSON dict from the export.
            user_id:   Internal Vitalis user UUID.

        Returns:
            List of RawDevicePayload grouped by date.
        """
        by_date: dict[str, dict] = {}

        for metric_key, records in json_data.items():
            if not isinstance(records, list):
                continue
            for record in records:
                start_str = record.get("startDate") or record.get("date", "")
                if not start_str:
                    continue
                try:
                    dt = datetime.fromisoformat(start_str[:19].replace(" ", "T"))
                    day_str = dt.date().isoformat()
                except ValueError:
                    continue

                if day_str not in by_date:
                    by_date[day_str] = {}
                if metric_key not in by_date[day_str]:
                    by_date[day_str][metric_key] = []
                by_date[day_str][metric_key].append(record)

        payloads = []
        for day_str, data in by_date.items():
            try:
                day = date.fromisoformat(day_str)
            except ValueError:
                continue
            payloads.append(
                RawDevicePayload(
                    user_id=user_id,
                    device_source=self.SOURCE_ID,
                    metric_type="daily",
                    date=day,
                    raw_payload=data,
                )
            )

        return payloads

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def normalize_sleep(self, raw: dict) -> NormalizedSleep:
        """Convert Apple Health sleep records to canonical NormalizedSleep.

        Args:
            raw: Dict with 'sleep_records' list from parse_xml_export().

        Returns:
            NormalizedSleep.
        """
        user_id_placeholder = UUID("00000000-0000-0000-0000-000000000000")

        sleep_records = raw.get("sleep_records", raw.get("sleep", []))

        # Calculate sleep metrics from individual records
        total_sleep_secs = 0
        deep_secs = 0
        rem_secs = 0
        light_secs = 0
        awake_secs = 0
        sleep_start: datetime | None = None
        sleep_end: datetime | None = None
        hypnogram = []
        sleep_date = date.today()

        for rec in sleep_records:
            value = rec.get("value", "")
            if not value or "InBed" in value and "Asleep" not in value:
                continue

            try:
                start_dt = datetime.fromisoformat(
                    rec.get("startDate", "")[:19].replace(" ", "T")
                )
                end_dt = datetime.fromisoformat(
                    rec.get("endDate", "")[:19].replace(" ", "T")
                )
            except (ValueError, TypeError):
                continue

            duration_secs = int((end_dt - start_dt).total_seconds())
            if duration_secs <= 0:
                continue

            stage = _SLEEP_STAGE_MAP.get(value, "light")

            if sleep_start is None or start_dt < sleep_start:
                sleep_start = start_dt
                sleep_date = end_dt.date()

            if sleep_end is None or end_dt > sleep_end:
                sleep_end = end_dt

            hypnogram.append({
                "t": int(start_dt.timestamp()),
                "stage": stage,
            })

            if stage == "deep":
                deep_secs += duration_secs
            elif stage == "rem":
                rem_secs += duration_secs
            elif stage == "awake":
                awake_secs += duration_secs
            else:
                light_secs += duration_secs
            total_sleep_secs += duration_secs

        # Extract scalar metrics from records
        all_records = raw.get("records", [])
        hrv_values = [
            float(r["value"]) for r in all_records
            if r.get("type") == _HK_HRV and r.get("value")
        ]
        rhr_values = [
            float(r["value"]) for r in all_records
            if r.get("type") == _HK_RESTING_HR and r.get("value")
        ]
        spo2_values = [
            float(r["value"]) * 100 for r in all_records
            if r.get("type") == _HK_SPO2 and r.get("value")
        ]
        rr_values = [
            float(r["value"]) for r in all_records
            if r.get("type") == _HK_RESPIRATORY and r.get("value")
        ]
        temp_values = [
            float(r["value"]) for r in all_records
            if r.get("type") == _HK_SKIN_TEMP and r.get("value")
        ]

        avg_hrv = sum(hrv_values) / len(hrv_values) if hrv_values else None
        avg_rhr = int(round(sum(rhr_values) / len(rhr_values))) if rhr_values else None
        avg_spo2 = sum(spo2_values) / len(spo2_values) if spo2_values else None
        avg_rr = sum(rr_values) / len(rr_values) if rr_values else None
        avg_temp = sum(temp_values) / len(temp_values) if temp_values else None

        total_bed_secs = (
            int((sleep_end - sleep_start).total_seconds())
            if sleep_start and sleep_end
            else 0
        )
        efficiency = (
            round((total_sleep_secs / total_bed_secs) * 100, 1)
            if total_bed_secs > 0 and total_sleep_secs > 0
            else None
        )

        return NormalizedSleep(
            user_id=user_id_placeholder,
            sleep_date=sleep_date,
            source=self.SOURCE_ID,
            sleep_start=sleep_start,
            sleep_end=sleep_end,
            total_sleep_minutes=total_sleep_secs // 60 if total_sleep_secs else None,
            rem_minutes=rem_secs // 60 if rem_secs else None,
            deep_minutes=deep_secs // 60 if deep_secs else None,
            light_minutes=light_secs // 60 if light_secs else None,
            awake_minutes=awake_secs // 60 if awake_secs else None,
            sleep_efficiency_pct=efficiency,
            avg_hr_bpm=avg_rhr,
            avg_hrv_ms=avg_hrv,
            avg_respiratory_rate=avg_rr,
            avg_spo2_pct=avg_spo2,
            avg_skin_temp_deviation_c=avg_temp,
            hypnogram=hypnogram,
            raw_payload=raw,
        )

    def normalize_daily(self, raw: dict) -> NormalizedDaily:
        """Convert Apple Health daily records to canonical NormalizedDaily.

        Args:
            raw: Dict of metric_key → list of records (from parse_xml_export).

        Returns:
            NormalizedDaily.
        """
        user_id_placeholder = UUID("00000000-0000-0000-0000-000000000000")

        all_records = raw.get("records", [])

        def _sum_records(hk_type: str) -> float | None:
            values = [
                float(r["value"]) for r in all_records
                if r.get("type") == hk_type and r.get("value")
            ]
            return sum(values) if values else None

        def _avg_records(hk_type: str) -> float | None:
            values = [
                float(r["value"]) for r in all_records
                if r.get("type") == hk_type and r.get("value")
            ]
            return sum(values) / len(values) if values else None

        steps = _sum_records(_HK_STEP_COUNT)
        active_kcal = _sum_records(_HK_ACTIVE_ENERGY)
        basal_kcal = _sum_records(_HK_BASAL_ENERGY)
        total_kcal = (
            int(active_kcal or 0) + int(basal_kcal or 0)
            if active_kcal or basal_kcal
            else None
        )
        distance_m = _sum_records(_HK_DISTANCE)
        floors = _sum_records(_HK_FLIGHTS)
        rhr = _avg_records(_HK_RESTING_HR)
        hrv = _avg_records(_HK_HRV)
        spo2 = _avg_records(_HK_SPO2)
        rr = _avg_records(_HK_RESPIRATORY)
        temp = _avg_records(_HK_SKIN_TEMP)

        # Infer date from first record
        daily_date = date.today()
        if all_records:
            try:
                daily_date = datetime.fromisoformat(
                    all_records[0].get("startDate", "")[:10]
                ).date()
            except (ValueError, TypeError):
                pass

        return NormalizedDaily(
            user_id=user_id_placeholder,
            date=daily_date,
            source=self.SOURCE_ID,
            resting_hr_bpm=int(round(rhr)) if rhr else None,
            hrv_rmssd_ms=hrv,
            steps=int(steps) if steps else None,
            active_calories_kcal=int(active_kcal) if active_kcal else None,
            total_calories_kcal=int(total_kcal) if total_kcal else None,
            distance_m=int(distance_m) if distance_m else None,
            floors_climbed=int(floors) if floors else None,
            spo2_avg_pct=round(spo2 * 100, 1) if spo2 else None,
            respiratory_rate_avg=rr,
            skin_temp_deviation_c=temp,
            raw_payload=raw,
        )
