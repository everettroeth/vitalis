You are a senior Python engineer building the Wearable Data Fusion Engine for Vitalis.

## Context
Read these files first:
- FUSION-ENGINE.md — the full architecture plan (READ THIS CAREFULLY)
- PLAN.md — project overview
- SCHEMA.md — data architecture
- schema.sql — existing tables (wearable_daily, wearable_sleep, wearable_activities, menstrual_cycles)
- src/parsers/ — see how the parser engine is structured (follow the same patterns)
- requirements.txt — current deps

## What to Build

Build the entire wearable fusion system following the architecture in FUSION-ENGINE.md exactly.

### File Structure
```
src/wearables/
├── __init__.py
├── base.py                    # WearableAdapter ABC + NormalizedSleep/Daily/Activity models
├── fusion_engine.py           # Core fusion: weighted merge, conflict detection
├── fusion_config.yaml         # THE editable config (copy from FUSION-ENGINE.md)
├── config_loader.py           # Load, validate, hot-reload fusion_config.yaml
├── readiness_score.py         # Vitalis readiness score from fused metrics
├── sleep_matcher.py           # Match sleep sessions across devices (overlap detection)
├── menstrual/
│   ├── __init__.py
│   ├── cycle_tracker.py       # Cycle prediction (calendar + temperature)
│   ├── temp_ovulation.py      # Temperature shift detection for ovulation
│   └── symptom_correlator.py  # Correlate symptoms with phase + wearable metrics
├── adapters/
│   ├── __init__.py
│   ├── garmin.py              # Garmin Connect Health API (OAuth1, push notifications)
│   ├── oura.py                # Oura API v2 (OAuth2, personal token support)
│   ├── apple_health.py        # Apple HealthKit (web import via JSON/XML + future native)
│   └── whoop.py               # Whoop API v1 (OAuth2)
├── sync/
│   ├── __init__.py
│   ├── scheduler.py           # Background sync (cron-based, per-device intervals)
│   ├── backfill.py            # Historical backfill orchestrator (batched, rate-limited)
│   └── dedup.py               # Dedup logic (source + timestamp + metric)
└── tests/
    ├── __init__.py
    ├── conftest.py            # Shared fixtures, mock API responses
    ├── test_fusion_engine.py  # Fusion logic: weighted merge, conflicts, tolerances
    ├── test_sleep_matcher.py  # Overlap detection, timezone handling
    ├── test_readiness.py      # Readiness score computation
    ├── test_garmin.py         # Garmin normalization + mock sync
    ├── test_oura.py           # Oura normalization + mock sync
    ├── test_menstrual.py      # Cycle prediction, temp detection, symptom correlation
    ├── test_config.py         # Config loading, validation, defaults
    └── fixtures/
        ├── garmin_sleep.json       # Sample Garmin sleep API response
        ├── garmin_daily.json       # Sample Garmin daily summary
        ├── oura_sleep.json         # Sample Oura sleep API response
        ├── oura_daily.json         # Sample Oura daily readiness
        ├── overlapping_sleep.json  # Same night from 2 devices
        └── cycle_data.json         # Menstrual cycle test data
```

### Key Implementation Details

1. **fusion_config.yaml** — Copy the exact config from FUSION-ENGINE.md. This is the single source of truth for all weights, tolerances, and equations. The config_loader must validate it on load and support runtime reload.

2. **WearableAdapter base class** — Abstract base with: authenticate(), refresh_token(), sync_daily(), sync_sleep(), sync_activities(), backfill(), normalize_sleep(), normalize_daily(). Optional: sync_menstrual(), sync_temperature().

3. **Garmin adapter** — Use OAuth1 (Garmin uses OAuth 1.0a). Endpoints:
   - /wellness-api/rest/dailies — daily summaries
   - /wellness-api/rest/epochs — epoch summaries
   - /wellness-api/rest/sleeps — sleep data
   - /wellness-api/rest/activities — activities
   - /wellness-api/rest/bodyComps — body composition
   Auth credentials from env: GARMIN_CONSUMER_KEY, GARMIN_CONSUMER_SECRET
   For now, use httpx for HTTP calls. Include realistic mock responses in test fixtures.

4. **Oura adapter** — OAuth2. Endpoints:
   - /v2/usercollection/daily_sleep
   - /v2/usercollection/sleep
   - /v2/usercollection/daily_activity
   - /v2/usercollection/heartrate
   - /v2/usercollection/daily_readiness
   - /v2/usercollection/ring_configuration
   Auth: OURA_CLIENT_ID, OURA_CLIENT_SECRET, or OURA_PERSONAL_TOKEN
   Include realistic mock responses.

5. **Apple Health adapter** — For web, accept HealthKit XML/JSON export upload. Parse into canonical format. Structure it so a future iOS native HealthKit integration slots in.

6. **Whoop adapter** — OAuth2. /v1/cycle, /v1/recovery, /v1/sleep, /v1/workout. WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET.

7. **Fusion engine** — The core algorithm:
   - Takes a date + user_id
   - Gathers all raw_device_data for that date
   - For each metric: collects values from all sources, looks up weights in config, checks tolerance
   - If within tolerance: weighted average
   - If outside tolerance: use highest-weight source, flag conflict
   - Records fusion_metadata (sources, weights, conflicts)
   - Writes to canonical tables (wearable_daily, wearable_sleep)

8. **Sleep matcher** — Given sleep sessions from multiple devices, match which ones are "the same sleep." Use timestamp overlap (configurable min_overlap_pct). Handle timezone edge cases.

9. **Readiness score** — Compute from fused metrics using the formula in fusion_config.yaml. Each component compares current value to personal 30-day rolling baseline.

10. **Menstrual cycle** — Temperature-based ovulation detection (0.2°C sustained shift over 3 days). Calendar prediction using rolling average of last 6 cycles. Symptom logging with phase correlation. Privacy flags on all cycle data.

11. **Dedup** — Prevent storing duplicate readings when same data comes through multiple paths (e.g., Garmin → Apple Health → Vitalis).

12. **Backfill** — Iterate historical data in configurable batch sizes with rate limiting. Resume-capable (track last backfilled date per device).

### Tests
Write comprehensive tests for everything. Mock all external API calls. Test:
- Fusion with 1 source, 2 sources, 3 sources
- Fusion with conflicts (outside tolerance)
- Sleep matching with overlapping and non-overlapping sessions
- Readiness score edge cases (no baseline data, all metrics perfect, all metrics bad)
- Garmin/Oura normalization of realistic API responses
- Menstrual cycle: regular cycles, irregular, first cycle, temperature detection
- Config loading: valid, invalid, missing fields, hot reload

Also add a router at src/routers/wearables.py with the endpoints listed in FUSION-ENGINE.md.

Update requirements.txt with: authlib (for OAuth), pyyaml (for config).

This is production code. Type hints, docstrings, error handling, logging throughout.
