"""Sleep session matcher — identify which sleep records from different devices
represent the same night of sleep.

Uses temporal overlap detection with configurable thresholds from fusion_config.yaml.
Handles timezone edge cases (sleep crossing midnight, cutoff hour logic).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.wearables.base import NormalizedSleep
from src.wearables.config_loader import FusionConfig, get_fusion_config

logger = logging.getLogger("vitalis.wearables.sleep_matcher")


@dataclass
class SleepMatchGroup:
    """A set of sleep sessions from different devices that represent the same night.

    Attributes:
        sessions:     All matched sessions (one per device).
        overlap_pct:  Lowest overlap% among all pairs in the group.
        primary:      The highest-weight session (used as the fusion anchor).
        date:         Canonical sleep date (morning of the wake date).
    """

    sessions: list[NormalizedSleep] = field(default_factory=list)
    overlap_pct: float = 0.0
    primary: NormalizedSleep | None = None

    @property
    def sources(self) -> list[str]:
        return [s.source for s in self.sessions]


def _overlap_seconds(
    start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime
) -> int:
    """Return the number of seconds two time intervals overlap.

    Args:
        start_a, end_a: Interval A (UTC datetimes).
        start_b, end_b: Interval B (UTC datetimes).

    Returns:
        Overlap in seconds (0 if no overlap).
    """
    overlap_start = max(start_a, start_b)
    overlap_end = min(end_a, end_b)
    delta = (overlap_end - overlap_start).total_seconds()
    return int(max(0.0, delta))


def _overlap_pct(
    start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime
) -> float:
    """Return the overlap as a percentage of the shorter session.

    Args:
        start_a, end_a: Session A bounds.
        start_b, end_b: Session B bounds.

    Returns:
        Overlap percentage 0.0–100.0.
    """
    dur_a = (end_a - start_a).total_seconds()
    dur_b = (end_b - start_b).total_seconds()
    shorter = min(dur_a, dur_b)
    if shorter <= 0:
        return 0.0
    overlap = _overlap_seconds(start_a, end_a, start_b, end_b)
    return (overlap / shorter) * 100.0


def _sessions_are_same_sleep(
    a: NormalizedSleep,
    b: NormalizedSleep,
    min_overlap_pct: float,
    max_start_diff_minutes: int,
) -> bool:
    """Determine whether two sleep sessions represent the same night.

    Two sessions are the "same sleep" if:
    1. Both have valid start/end times.
    2. Their start times differ by at most max_start_diff_minutes, OR
    3. Their temporal overlap is at least min_overlap_pct of the shorter session.

    Args:
        a:                      First sleep session.
        b:                      Second sleep session.
        min_overlap_pct:        Minimum required overlap (0–100).
        max_start_diff_minutes: Maximum allowed start time difference.

    Returns:
        True if the sessions represent the same sleep period.
    """
    # Both sessions need timing data to compare
    if not (a.sleep_start and a.sleep_end and b.sleep_start and b.sleep_end):
        # Fall back to date equality if no timing data
        return a.sleep_date == b.sleep_date

    start_diff = abs((a.sleep_start - b.sleep_start).total_seconds() / 60.0)

    # Check start-time proximity first (fast path)
    if start_diff <= max_start_diff_minutes:
        return True

    # Check overlap percentage
    pct = _overlap_pct(a.sleep_start, a.sleep_end, b.sleep_start, b.sleep_end)
    return pct >= min_overlap_pct


class SleepMatcher:
    """Match sleep sessions from multiple devices into groups.

    Uses the parameters from FusionConfig.sleep_matching.

    Usage::

        matcher = SleepMatcher()
        groups = matcher.match(sessions)
        for group in groups:
            print(group.sources)   # ['oura', 'garmin']
    """

    def __init__(self, config: FusionConfig | None = None) -> None:
        self._config = config or get_fusion_config()

    def match(self, sessions: list[NormalizedSleep]) -> list[SleepMatchGroup]:
        """Group sleep sessions from different devices into matched pairs.

        Sessions from the same device are never merged into the same group
        (each device gets at most one session per group).  Sessions that
        don't match any other session form singleton groups.

        Algorithm:
            1. Sort sessions by sleep_start (earliest first).
            2. For each unassigned session, greedily match with unassigned sessions
               from different devices.
            3. Build a SleepMatchGroup for each cluster.

        Args:
            sessions: List of NormalizedSleep from any number of devices/dates.

        Returns:
            List of SleepMatchGroup, one per distinct sleep period.
        """
        if not sessions:
            return []

        cfg = self._config.sleep_matching
        min_overlap = cfg.min_overlap_pct
        max_start_diff = cfg.max_start_diff_minutes

        # Sort: sessions with timing data first, then by sleep_start
        def sort_key(s: NormalizedSleep) -> datetime:
            return s.sleep_start or datetime(1970, 1, 1)

        sorted_sessions = sorted(sessions, key=sort_key)

        assigned: set[int] = set()
        groups: list[SleepMatchGroup] = []

        for i, anchor in enumerate(sorted_sessions):
            if i in assigned:
                continue

            group_sessions = [anchor]
            assigned.add(i)

            for j, candidate in enumerate(sorted_sessions):
                if j in assigned:
                    continue
                # Never merge two sessions from the same device
                if candidate.source == anchor.source:
                    continue
                # Don't merge if the group already has this source
                if candidate.source in {s.source for s in group_sessions}:
                    continue

                # Check if candidate matches the anchor
                if _sessions_are_same_sleep(
                    anchor, candidate, min_overlap, max_start_diff
                ):
                    group_sessions.append(candidate)
                    assigned.add(j)

            # Compute group overlap stats
            group_overlap = 100.0
            if len(group_sessions) >= 2:
                pcts = []
                for idx_a in range(len(group_sessions)):
                    for idx_b in range(idx_a + 1, len(group_sessions)):
                        s_a = group_sessions[idx_a]
                        s_b = group_sessions[idx_b]
                        if s_a.sleep_start and s_a.sleep_end and s_b.sleep_start and s_b.sleep_end:
                            pcts.append(
                                _overlap_pct(
                                    s_a.sleep_start, s_a.sleep_end,
                                    s_b.sleep_start, s_b.sleep_end,
                                )
                            )
                if pcts:
                    group_overlap = min(pcts)

            groups.append(
                SleepMatchGroup(
                    sessions=group_sessions,
                    overlap_pct=group_overlap,
                )
            )

        logger.debug(
            "SleepMatcher: %d sessions → %d groups", len(sessions), len(groups)
        )
        return groups

    def match_for_date(
        self,
        sessions: list[NormalizedSleep],
        sleep_date: object,
    ) -> list[SleepMatchGroup]:
        """Match only sessions belonging to a specific sleep_date.

        Args:
            sessions:   All available sessions (any date).
            sleep_date: The date (datetime.date) to filter by.

        Returns:
            Match groups for just that date.
        """
        filtered = [s for s in sessions if s.sleep_date == sleep_date]
        return self.match(filtered)

    @staticmethod
    def select_primary(
        group: SleepMatchGroup, source_weights: dict[str, float]
    ) -> NormalizedSleep | None:
        """Select the primary (highest-weight) session in a group.

        Args:
            group:          A matched sleep group.
            source_weights: Dict of source→weight from the fusion config
                            (e.g. config.device_weights['sleep_duration']).

        Returns:
            The NormalizedSleep from the highest-weight source, or the
            first session if no weights are configured.
        """
        if not group.sessions:
            return None
        return max(
            group.sessions,
            key=lambda s: source_weights.get(s.source, 0.0),
        )

    @staticmethod
    def estimate_sleep_date_from_start(
        sleep_start: datetime,
        cutoff_hour: int = 18,
    ) -> object:
        """Determine which calendar date a sleep session belongs to.

        Sleep starting before cutoff_hour (default 18:00 / 6 PM) is
        considered the previous calendar day's sleep.  This handles afternoon
        naps and early-evening sleepers without misassigning the date.

        Args:
            sleep_start:  UTC datetime when sleep began.
            cutoff_hour:  Hour (0–23) below which sleep belongs to the prior day.

        Returns:
            datetime.date — the canonical sleep_date for this session.
        """
        from datetime import date

        d = sleep_start.date()
        if sleep_start.hour < cutoff_hour:
            # e.g. sleep started at 02:00 → still part of the previous day's sleep
            return d
        else:
            # e.g. fell asleep at 22:00 → next-morning wake date
            return d + timedelta(days=1)
