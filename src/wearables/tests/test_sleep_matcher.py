"""Tests for the sleep matcher — overlap detection and session grouping."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import pytest

from src.wearables.base import NormalizedSleep
from src.wearables.config_loader import FusionConfig
from src.wearables.sleep_matcher import (
    SleepMatchGroup,
    SleepMatcher,
    _overlap_pct,
    _overlap_seconds,
    _sessions_are_same_sleep,
)
from src.wearables.tests.conftest import TEST_DATE, TEST_USER_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_sleep(
    source: str,
    start: datetime,
    end: datetime,
    sleep_date: date | None = None,
) -> NormalizedSleep:
    return NormalizedSleep(
        user_id=TEST_USER_ID,
        sleep_date=sleep_date or start.date(),
        source=source,
        sleep_start=start,
        sleep_end=end,
        total_sleep_minutes=int((end - start).total_seconds() / 60),
    )


# ---------------------------------------------------------------------------
# Unit tests: overlap helpers
# ---------------------------------------------------------------------------


class TestOverlapHelpers:
    def test_full_overlap(self) -> None:
        s = datetime(2026, 2, 22, 23, 0)
        e = datetime(2026, 2, 23, 7, 0)
        assert _overlap_seconds(s, e, s, e) == int((e - s).total_seconds())

    def test_no_overlap(self) -> None:
        a_start = datetime(2026, 2, 22, 22, 0)
        a_end = datetime(2026, 2, 22, 23, 0)
        b_start = datetime(2026, 2, 23, 1, 0)
        b_end = datetime(2026, 2, 23, 7, 0)
        assert _overlap_seconds(a_start, a_end, b_start, b_end) == 0

    def test_partial_overlap(self) -> None:
        a = (datetime(2026, 2, 22, 22, 0), datetime(2026, 2, 23, 2, 0))
        b = (datetime(2026, 2, 23, 0, 0), datetime(2026, 2, 23, 6, 0))
        overlap = _overlap_seconds(*a, *b)
        assert overlap == 2 * 3600  # 2 hours

    def test_overlap_pct_full(self) -> None:
        s = datetime(2026, 2, 22, 23, 0)
        e = datetime(2026, 2, 23, 7, 0)
        assert _overlap_pct(s, e, s, e) == pytest.approx(100.0)

    def test_overlap_pct_zero(self) -> None:
        a = (datetime(2026, 2, 22, 12, 0), datetime(2026, 2, 22, 13, 0))
        b = (datetime(2026, 2, 22, 14, 0), datetime(2026, 2, 22, 15, 0))
        assert _overlap_pct(*a, *b) == pytest.approx(0.0)

    def test_overlap_pct_partial(self) -> None:
        # Session A: 22:00–06:00 (8h), Session B: 23:15–06:45 (7.5h)
        a = (datetime(2026, 2, 22, 22, 0), datetime(2026, 2, 23, 6, 0))
        b = (datetime(2026, 2, 22, 23, 15), datetime(2026, 2, 23, 6, 45))
        pct = _overlap_pct(*a, *b)
        # overlap = 23:15 to 06:00 = 6h45m = 24300s, shorter = b = 27000s
        assert pct == pytest.approx(24300 / 27000 * 100, rel=0.01)


class TestSessionsAreSameSleep:
    def test_same_start_within_tolerance(self) -> None:
        a = make_sleep("oura", datetime(2026, 2, 22, 23, 0), datetime(2026, 2, 23, 6, 45))
        b = make_sleep("garmin", datetime(2026, 2, 22, 23, 15), datetime(2026, 2, 23, 6, 40))
        # 15 min diff ≤ 60 min max_start_diff → same sleep
        assert _sessions_are_same_sleep(a, b, min_overlap_pct=60.0, max_start_diff_minutes=60)

    def test_large_start_diff_but_high_overlap(self) -> None:
        # Start diff > 60 min, but 85% overlap → same sleep
        a = make_sleep("oura", datetime(2026, 2, 22, 21, 0), datetime(2026, 2, 23, 6, 0))
        b = make_sleep("garmin", datetime(2026, 2, 22, 23, 30), datetime(2026, 2, 23, 6, 30))
        # b duration = 7h, overlap from 23:30 to 6:00 = 6.5h → 92.8%
        assert _sessions_are_same_sleep(a, b, min_overlap_pct=60.0, max_start_diff_minutes=60)

    def test_afternoon_nap_not_same_as_night_sleep(self) -> None:
        night = make_sleep("oura", datetime(2026, 2, 22, 23, 0), datetime(2026, 2, 23, 6, 45))
        nap = make_sleep("whoop", datetime(2026, 2, 22, 13, 0), datetime(2026, 2, 22, 14, 30))
        assert not _sessions_are_same_sleep(night, nap, min_overlap_pct=60.0, max_start_diff_minutes=60)

    def test_same_date_no_timing_falls_back_to_date(self) -> None:
        a = NormalizedSleep(
            user_id=TEST_USER_ID, sleep_date=TEST_DATE, source="oura",
            sleep_start=None, sleep_end=None,
        )
        b = NormalizedSleep(
            user_id=TEST_USER_ID, sleep_date=TEST_DATE, source="garmin",
            sleep_start=None, sleep_end=None,
        )
        assert _sessions_are_same_sleep(a, b, min_overlap_pct=60.0, max_start_diff_minutes=60)

    def test_different_dates_no_timing_not_same(self) -> None:
        a = NormalizedSleep(
            user_id=TEST_USER_ID, sleep_date=date(2026, 2, 22), source="oura",
            sleep_start=None, sleep_end=None,
        )
        b = NormalizedSleep(
            user_id=TEST_USER_ID, sleep_date=date(2026, 2, 23), source="garmin",
            sleep_start=None, sleep_end=None,
        )
        assert not _sessions_are_same_sleep(a, b, min_overlap_pct=60.0, max_start_diff_minutes=60)


# ---------------------------------------------------------------------------
# Integration tests: SleepMatcher
# ---------------------------------------------------------------------------


class TestSleepMatcher:
    def test_empty_input_returns_empty(self, fusion_config: FusionConfig) -> None:
        matcher = SleepMatcher(fusion_config)
        assert matcher.match([]) == []

    def test_single_session_forms_singleton_group(
        self, fusion_config: FusionConfig, normalized_oura_sleep: NormalizedSleep
    ) -> None:
        matcher = SleepMatcher(fusion_config)
        groups = matcher.match([normalized_oura_sleep])
        assert len(groups) == 1
        assert groups[0].sources == ["oura"]

    def test_two_overlapping_sessions_merged(
        self,
        fusion_config: FusionConfig,
        normalized_oura_sleep: NormalizedSleep,
        normalized_garmin_sleep: NormalizedSleep,
    ) -> None:
        matcher = SleepMatcher(fusion_config)
        groups = matcher.match([normalized_oura_sleep, normalized_garmin_sleep])
        assert len(groups) == 1
        assert set(groups[0].sources) == {"oura", "garmin"}

    def test_nap_not_merged_with_night_sleep(
        self,
        fusion_config: FusionConfig,
        normalized_oura_sleep: NormalizedSleep,
        normalized_garmin_sleep: NormalizedSleep,
        overlapping_sleep_raw: dict,
    ) -> None:
        nap = NormalizedSleep(
            user_id=TEST_USER_ID,
            sleep_date=date(2026, 2, 22),
            source="whoop",
            sleep_start=datetime(2026, 2, 22, 13, 0),
            sleep_end=datetime(2026, 2, 22, 14, 30),
            total_sleep_minutes=90,
        )
        matcher = SleepMatcher(fusion_config)
        groups = matcher.match([normalized_oura_sleep, normalized_garmin_sleep, nap])
        # Should be 2 groups: night sleep (oura+garmin) and nap (whoop singleton)
        assert len(groups) == 2
        group_sources = [set(g.sources) for g in groups]
        assert {"oura", "garmin"} in group_sources
        assert {"whoop"} in group_sources

    def test_two_sessions_same_device_not_merged(
        self, fusion_config: FusionConfig
    ) -> None:
        s1 = make_sleep("oura", datetime(2026, 2, 22, 23, 0), datetime(2026, 2, 23, 7, 0))
        s2 = make_sleep("oura", datetime(2026, 2, 22, 23, 10), datetime(2026, 2, 23, 7, 10))
        matcher = SleepMatcher(fusion_config)
        groups = matcher.match([s1, s2])
        # Same device → two singleton groups
        assert len(groups) == 2

    def test_match_for_date_filters_correctly(
        self,
        fusion_config: FusionConfig,
        normalized_oura_sleep: NormalizedSleep,
    ) -> None:
        other_night = make_sleep(
            "garmin",
            datetime(2026, 2, 21, 23, 0),
            datetime(2026, 2, 22, 7, 0),
            sleep_date=date(2026, 2, 22),
        )
        matcher = SleepMatcher(fusion_config)
        groups = matcher.match_for_date(
            [normalized_oura_sleep, other_night], TEST_DATE
        )
        assert len(groups) == 1
        assert groups[0].sources == ["oura"]

    def test_group_overlap_pct_computed(
        self,
        fusion_config: FusionConfig,
        normalized_oura_sleep: NormalizedSleep,
        normalized_garmin_sleep: NormalizedSleep,
    ) -> None:
        matcher = SleepMatcher(fusion_config)
        groups = matcher.match([normalized_oura_sleep, normalized_garmin_sleep])
        assert len(groups) == 1
        # Oura: 23:00–06:45, Garmin: 23:15–06:40 → very high overlap
        assert groups[0].overlap_pct > 90.0

    def test_select_primary_returns_highest_weight(
        self, fusion_config: FusionConfig
    ) -> None:
        group = SleepMatchGroup(
            sessions=[
                make_sleep("garmin", datetime(2026, 2, 22, 23, 0), datetime(2026, 2, 23, 7, 0)),
                make_sleep("oura", datetime(2026, 2, 22, 23, 5), datetime(2026, 2, 23, 6, 55)),
            ]
        )
        weights = fusion_config.device_weights.get("sleep_duration", {})
        primary = SleepMatcher.select_primary(group, weights)
        assert primary is not None
        assert primary.source == "oura"  # Oura has higher weight

    def test_estimate_sleep_date_after_cutoff(self) -> None:
        # Sleep starts at 22:30 (after 18:00 cutoff) → assign to next morning
        sleep_start = datetime(2026, 2, 22, 22, 30)
        d = SleepMatcher.estimate_sleep_date_from_start(sleep_start, cutoff_hour=18)
        assert d == date(2026, 2, 23)

    def test_estimate_sleep_date_before_cutoff(self) -> None:
        # Sleep starts at 02:00 (before 18:00 cutoff) → assign to same date
        sleep_start = datetime(2026, 2, 23, 2, 0)
        d = SleepMatcher.estimate_sleep_date_from_start(sleep_start, cutoff_hour=18)
        assert d == date(2026, 2, 23)

    def test_three_sources_merged_into_one_group(
        self, fusion_config: FusionConfig
    ) -> None:
        oura = make_sleep("oura", datetime(2026, 2, 22, 23, 0), datetime(2026, 2, 23, 7, 0))
        garmin = make_sleep("garmin", datetime(2026, 2, 22, 23, 15), datetime(2026, 2, 23, 6, 45))
        whoop = make_sleep("whoop", datetime(2026, 2, 22, 23, 20), datetime(2026, 2, 23, 7, 5))
        matcher = SleepMatcher(fusion_config)
        groups = matcher.match([oura, garmin, whoop])
        # All three start within 25 minutes → should merge
        assert len(groups) == 1
        assert set(groups[0].sources) == {"oura", "garmin", "whoop"}
