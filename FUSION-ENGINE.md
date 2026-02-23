# Vitalis — Wearable Data Fusion Engine

**Version:** 1.0
**Purpose:** Ingest data from multiple wearable devices, fuse conflicting readings into a single best-estimate per metric using weighted confidence algorithms, and present a simple unified view.

---

## Design Principles

1. **Store everything, lose nothing.** Raw device data is always preserved. Fusion is a computed layer on top.
2. **Algorithms are editable.** All weights, equations, and fusion rules live in a single config file (`fusion_config.yaml`) that can be tweaked without code changes.
3. **Simple surface, deep drill-down.** User sees one number. Tap to see each device's reading.
4. **Historical backfill.** Full import of all historical data from day one of device usage.
5. **Device-agnostic schema.** New devices plug in without schema changes.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Device Adapters                     │
│  Garmin Connect │ Oura API │ Apple Health │ Whoop API │
└────────┬─────────────┬──────────┬────────────┬───────┘
         │             │          │            │
         ▼             ▼          ▼            ▼
┌──────────────────────────────────────────────────────┐
│              Raw Data Ingestion Layer                  │
│  Store raw JSON per device per day in raw_device_data │
│  Normalize timestamps to UTC                          │
│  Dedup: source + metric + timestamp                   │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│            Normalization & Alignment                  │
│  Map device-specific fields → canonical metrics       │
│  Align sleep sessions across devices (overlap match)  │
│  Handle timezone crossover (sleep day = wake date)    │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│               Fusion Engine (core)                    │
│  For each metric:                                     │
│    1. Gather all device readings                      │
│    2. Look up device weights from fusion_config.yaml  │
│    3. Check agreement (within tolerance?)             │
│    4. If agree: weighted average                      │
│    5. If disagree: flag conflict, use primary source  │
│    6. Compute confidence score                        │
│    7. Write to canonical daily record                 │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│             Canonical Daily Record                    │
│  wearable_daily / wearable_sleep / wearable_activities│
│  + fusion_metadata (which sources, weights, conflicts)│
└──────────────────────────────────────────────────────┘
```

---

## fusion_config.yaml — The Editable Brain

This file controls ALL fusion behavior. Change weights, add devices, adjust tolerances — no code changes needed.

```yaml
# ============================================================
# Vitalis Fusion Configuration
# ============================================================
# This file controls how multi-device data is merged.
# Edit weights, tolerances, and priorities here.
# Changes take effect on next sync or manual recompute.
# ============================================================

version: "1.0"

# ── Device Accuracy Weights ──────────────────────────────────
# Scale: 0.0 (ignore) to 1.0 (gold standard)
# Based on published validation studies and sensor physics.
# Weights are normalized at fusion time (don't need to sum to 1.0)

device_weights:
  sleep_duration:
    oura:         0.90   # Finger PPG — best sleep onset/offset detection
    apple_watch:  0.75   # Wrist PPG — good but more motion artifact
    garmin:       0.70   # Wrist PPG — similar to Apple, slightly less validated
    whoop:        0.80   # Wrist PPG — strong algorithm, well-validated
    
  sleep_stages:  # deep, light, REM, awake
    oura:         0.90   # Temp + HRV + movement — best staging combo
    apple_watch:  0.65   # HRV + movement only
    garmin:       0.60   # Movement-heavy algorithm, less accurate staging
    whoop:        0.80   # HRV-focused, good staging
    
  hrv:  # Heart rate variability (ms, RMSSD)
    oura:         0.95   # Finger PPG — gold standard for consumer wearables
    apple_watch:  0.70   # Wrist PPG — more noise
    garmin:       0.65   # Wrist PPG — known to underread in some models
    whoop:        0.85   # Wrist PPG — strong HRV algorithm
    
  resting_heart_rate:
    oura:         0.90   # Measured during sleep — most accurate context
    apple_watch:  0.80   # Multiple readings throughout day
    garmin:       0.80   # Similar to Apple
    whoop:        0.85   # Strong algorithm
    
  spo2:  # Blood oxygen
    oura:         0.85   # Finger — better perfusion
    apple_watch:  0.70   # Wrist — decent
    garmin:       0.60   # Wrist — varies by model
    whoop:        0.65   # Wrist
    
  steps:
    garmin:       0.85   # Wrist accelerometer — well-calibrated
    apple_watch:  0.85   # Similar quality
    oura:         0.50   # Ring accelerometer — undercounts
    whoop:        0.40   # Not primary use case
    
  calories_burned:
    garmin:       0.80   # HR + movement + GPS
    apple_watch:  0.80   # Similar approach
    whoop:        0.75   # HR-based
    oura:         0.55   # Less accurate for active calories
    
  respiratory_rate:
    oura:         0.85   # Sleep-measured, finger-based
    whoop:        0.80   # Sleep-measured
    apple_watch:  0.70   # Available but less validated
    garmin:       0.65   # Newer feature, less validated
    
  skin_temperature:
    oura:         0.90   # Finger temp sensor — best consumer device for this
    apple_watch:  0.75   # Wrist temp (Series 8+)
    garmin:       0.0    # Not available on most models
    whoop:        0.70   # Skin temp available
    
  body_battery_readiness:
    # Each device has a proprietary score. We DON'T fuse these.
    # Instead, Vitalis computes its own readiness from fused raw metrics.
    # Set to 0.0 to exclude from fusion.
    oura:         0.0
    garmin:       0.0
    apple_watch:  0.0
    whoop:        0.0

  menstrual_cycle:
    # Cycle tracking priority — temp-based predictions are most accurate
    oura:         0.90   # Temp tracking — best predictor
    apple_watch:  0.75   # Wrist temp (Series 8+) + manual logging
    garmin:       0.50   # Manual logging only on most models
    whoop:        0.60   # Some cycle features
    # Note: All devices supplement, not replace, manual period logging.
    # User-entered period dates are always weight 1.0 (ground truth).

# ── Fusion Tolerances ────────────────────────────────────────
# When two devices disagree by MORE than the tolerance,
# it's flagged as a conflict and primary source wins.

tolerances:
  sleep_duration_minutes: 30     # >30min disagreement = conflict
  sleep_stage_minutes: 20        # >20min disagreement per stage
  hrv_ms: 15                     # >15ms RMSSD disagreement
  resting_hr_bpm: 5              # >5bpm disagreement
  spo2_pct: 3                    # >3% disagreement
  steps_count: 2000              # >2000 steps disagreement
  skin_temp_celsius: 0.5         # >0.5°C disagreement
  respiratory_rate_brpm: 3       # >3 breaths/min disagreement

# ── Sleep Session Matching ───────────────────────────────────
# How we determine two devices recorded the "same" sleep session

sleep_matching:
  min_overlap_pct: 60            # Sessions must overlap by 60%+ to be "same sleep"
  max_start_diff_minutes: 60     # Start times can differ by up to 60min
  sleep_day_cutoff_hour: 18      # Sleep before 6PM = previous day's sleep
  
# ── Vitalis Readiness Score ──────────────────────────────────
# Our own readiness score computed from fused raw metrics.
# NOT a copy of any device's proprietary score.

readiness_score:
  enabled: true
  components:
    hrv_vs_baseline:
      weight: 0.30
      description: "HRV compared to personal 30-day rolling average"
    resting_hr_vs_baseline:
      weight: 0.20
      description: "RHR compared to personal 30-day average (lower = better)"
    sleep_quality:
      weight: 0.25
      description: "Composite: duration + deep% + efficiency"
    sleep_consistency:
      weight: 0.10
      description: "How consistent sleep/wake times are vs 7-day pattern"
    recovery_time:
      weight: 0.15
      description: "Days since last high-intensity workout"
  scale: 0-100
  thresholds:
    thriving: 75    # 75+ = green/thriving
    watch: 50       # 50-74 = amber/watch
    concern: 0      # 0-49 = clay/attention

# ── Menstrual Cycle Intelligence ─────────────────────────────
# Cycle tracking uses temperature data + manual logging for prediction.

menstrual_cycle:
  enabled: true
  prediction_model: "temperature_assisted"  # or "calendar_only", "ml_hybrid"
  temp_source_priority: ["oura", "apple_watch", "whoop", "garmin"]
  fertile_window:
    method: "temp_shift"           # Detect ovulation via 0.2°C+ sustained temp rise
    confirmation_days: 3           # 3 consecutive elevated days confirms ovulation
    predicted_window_days: 6       # Show 6-day fertile window (5 before + day of ovulation)
  cycle_length:
    rolling_average_cycles: 6      # Average last 6 cycles for prediction
    min_cycle_days: 21             # Flag cycles shorter than 21 days
    max_cycle_days: 45             # Flag cycles longer than 45 days
  symptoms:
    track: true                    # Enable symptom logging (cramps, mood, flow, etc.)
    correlation_engine: true       # Correlate symptoms with phase, sleep, HRV
  privacy:
    separate_data_flag: true       # Mark menstrual data with extra privacy flag
    explicit_opt_in: true          # User must explicitly enable cycle tracking
    excluded_from_sharing: true    # Never included in family/household shared view
    gdpr_sensitive_category: true  # Treated as special category data under GDPR

# ── Unit Preferences ─────────────────────────────────────────
default_units:
  temperature: "celsius"     # or "fahrenheit"
  distance: "miles"          # or "kilometers"  
  weight: "lbs"              # or "kg"
  height: "inches"           # or "cm"
  
# ── Backfill Settings ────────────────────────────────────────
backfill:
  enabled: true
  garmin_max_days: 3650      # Up to 10 years
  oura_max_days: 3650
  apple_health_max_days: 3650
  whoop_max_days: 3650
  batch_size_days: 30        # Process 30 days at a time
  rate_limit_ms: 500         # Wait between API calls to avoid throttling
```

---

## Database Additions

### raw_device_data (new table)
Stores the exact JSON payload from each device. Never modified. Source of truth for reprocessing.

```sql
CREATE TABLE raw_device_data (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    device_source   data_source NOT NULL,  -- garmin, oura, apple_health, whoop
    metric_type     TEXT NOT NULL,          -- sleep, daily, activity, cycle
    date            DATE NOT NULL,          -- the day this data belongs to
    raw_payload     JSONB NOT NULL,         -- exact API response
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    reprocessed_at  TIMESTAMPTZ,           -- last time fusion was recomputed
    UNIQUE (user_id, device_source, metric_type, date)
);
CREATE INDEX idx_raw_device_user_date ON raw_device_data(user_id, date);
```

### fusion_metadata (new table)
Records how each fused value was computed — which sources, weights, conflicts.

```sql
CREATE TABLE fusion_metadata (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    metric_group    TEXT NOT NULL,          -- 'sleep', 'daily', 'activity'
    sources_used    TEXT[] NOT NULL,        -- ['oura', 'garmin']
    weights_applied JSONB NOT NULL,        -- {"oura": 0.90, "garmin": 0.70}
    conflicts       JSONB,                 -- null or {"sleep_duration": {"oura": 432, "garmin": 408, "diff_min": 24}}
    fusion_config_version TEXT NOT NULL,   -- "1.0" — tracks which config was used
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, date, metric_group)
);
```

### menstrual_cycles (enhance existing table)
```sql
-- Add columns to existing menstrual_cycles table:
ALTER TABLE menstrual_cycles ADD COLUMN IF NOT EXISTS
    temp_based_ovulation_date DATE,        -- detected via temperature shift
    predicted_ovulation_date DATE,          -- algorithm prediction for next cycle
    fertile_window_start DATE,
    fertile_window_end DATE,
    cycle_phase TEXT,                       -- 'menstrual', 'follicular', 'ovulation', 'luteal'
    avg_bbt_follicular DECIMAL(4,2),       -- avg basal body temp in follicular phase
    avg_bbt_luteal DECIMAL(4,2),           -- avg temp in luteal phase
    temp_shift_detected BOOLEAN DEFAULT FALSE,
    symptoms JSONB,                        -- {"cramps": 3, "mood": "irritable", "flow": "heavy", ...}
    prediction_confidence DECIMAL(3,2);    -- 0.0-1.0

-- Symptom options tracked:
-- flow: spotting, light, medium, heavy
-- cramps: 0-5 scale
-- mood: calm, happy, irritable, anxious, sad, emotional
-- energy: 1-5 scale
-- bloating: none, mild, moderate, severe
-- headache: none, mild, moderate, severe
-- breast_tenderness: none, mild, moderate, severe
-- acne: none, mild, moderate, severe
-- cravings: none, mild, moderate, severe
-- libido: low, normal, high
```

---

## Adapter Interface

Each device adapter implements:

```python
class WearableAdapter(ABC):
    """Base class for all wearable device adapters."""
    
    @abstractmethod
    async def authenticate(self, user_id: UUID, auth_code: str) -> OAuthTokens:
        """Exchange OAuth code for tokens."""
    
    @abstractmethod
    async def refresh_token(self, user_id: UUID) -> OAuthTokens:
        """Refresh expired OAuth token."""
    
    @abstractmethod
    async def sync_daily(self, user_id: UUID, date: date) -> RawDevicePayload:
        """Fetch daily summary (steps, calories, HR, etc.)"""
    
    @abstractmethod
    async def sync_sleep(self, user_id: UUID, date: date) -> RawDevicePayload:
        """Fetch sleep data for given night."""
    
    @abstractmethod
    async def sync_activities(self, user_id: UUID, date: date) -> list[RawDevicePayload]:
        """Fetch activities/workouts for given date."""
    
    @abstractmethod
    async def backfill(self, user_id: UUID, start_date: date, end_date: date) -> AsyncIterator[RawDevicePayload]:
        """Iterate over historical data in batches."""
    
    @abstractmethod
    def normalize_sleep(self, raw: dict) -> NormalizedSleep:
        """Convert device-specific sleep JSON → canonical format."""
    
    @abstractmethod
    def normalize_daily(self, raw: dict) -> NormalizedDaily:
        """Convert device-specific daily JSON → canonical format."""
    
    # Optional — not all devices support these
    async def sync_menstrual(self, user_id: UUID, date: date) -> RawDevicePayload | None:
        """Fetch menstrual/cycle data if available."""
        return None
    
    async def sync_temperature(self, user_id: UUID, date: date) -> RawDevicePayload | None:
        """Fetch body temperature data if available."""
        return None
```

---

## File Structure

```
src/wearables/
├── __init__.py
├── base.py                    # WearableAdapter ABC, NormalizedSleep/Daily models
├── fusion_engine.py           # Core fusion logic — reads fusion_config.yaml
├── fusion_config.yaml         # THE editable config file (weights, tolerances, etc.)
├── config_loader.py           # Load + validate + hot-reload fusion_config.yaml
├── readiness_score.py         # Vitalis readiness score calculator
├── sleep_matcher.py           # Match sleep sessions across devices
├── menstrual/
│   ├── __init__.py
│   ├── cycle_tracker.py       # Cycle prediction engine
│   ├── temp_ovulation.py      # Temperature-based ovulation detection
│   └── symptom_correlator.py  # Correlate symptoms with cycle phase + metrics
├── adapters/
│   ├── __init__.py
│   ├── garmin.py              # Garmin Connect API adapter
│   ├── oura.py                # Oura API v2 adapter
│   ├── apple_health.py        # Apple HealthKit adapter (web import + future native)
│   └── whoop.py               # Whoop API adapter
├── sync/
│   ├── __init__.py
│   ├── scheduler.py           # Background sync scheduler
│   ├── backfill.py            # Historical backfill orchestrator
│   └── dedup.py               # Deduplication logic
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_fusion_engine.py   # Fusion logic tests
    ├── test_sleep_matcher.py   # Sleep session matching tests
    ├── test_readiness.py       # Readiness score tests
    ├── test_garmin.py          # Garmin adapter tests
    ├── test_oura.py            # Oura adapter tests
    ├── test_menstrual.py       # Cycle tracking tests
    └── fixtures/
        ├── garmin_sleep.json
        ├── oura_sleep.json
        ├── overlapping_sleep.json  # Same night, two devices
        └── cycle_data.json
```

---

## Menstrual Cycle: Design Notes

This is critical for enterprise. Most health apps treat cycle tracking as an afterthought.

### What Makes Ours Different
1. **Temperature-based prediction** — Oura's nightly finger temp is the most accurate consumer-grade BBT proxy. We use sustained temp shifts to detect ovulation retroactively and predict future cycles.
2. **Multi-source** — combine temp data from Oura + Apple Watch for better accuracy
3. **Symptom correlation** — "Your cramps are worst on cycle days 1-2 when your HRV is also lowest. Your energy peaks around day 12-14."
4. **Cross-domain insights** — "Your sleep quality drops 15% in the luteal phase. Your lifting performance peaks in the follicular phase."
5. **Privacy-first** — menstrual data is marked as sensitive, opt-in only, excluded from household sharing, and treated as GDPR special category data.
6. **No assumptions** — works for irregular cycles, PCOS, perimenopause, post-partum. Doesn't assume 28-day cycles.

### Symptom Tracking
Users can log daily:
- Flow (spotting/light/medium/heavy)
- Pain/cramps (0-5)
- Mood (multi-select)
- Energy (1-5)
- Physical symptoms (bloating, headache, breast tenderness, acne)
- Cravings (0-5)
- Libido (low/normal/high)

All symptoms are correlated with cycle phase AND wearable metrics to surface patterns.

---

## API Endpoints

```
# Device connection
POST   /api/v1/devices/connect/{provider}      # Start OAuth flow
GET    /api/v1/devices/callback/{provider}      # OAuth callback
GET    /api/v1/devices                          # List connected devices
DELETE /api/v1/devices/{device_id}              # Disconnect device

# Sync
POST   /api/v1/sync/trigger                    # Manual sync all devices
POST   /api/v1/sync/backfill                   # Start historical backfill
GET    /api/v1/sync/status                     # Sync status per device

# Fused data
GET    /api/v1/daily/{date}                    # Fused daily summary
GET    /api/v1/sleep/{date}                    # Fused sleep for night
GET    /api/v1/sleep/{date}/sources            # Per-device breakdown
GET    /api/v1/readiness/{date}                # Vitalis readiness score
GET    /api/v1/trends/{metric}?days=30         # Trend data for any metric

# Menstrual
GET    /api/v1/cycle/current                   # Current cycle info + predictions
POST   /api/v1/cycle/log                       # Log period/symptoms
GET    /api/v1/cycle/history                   # Past cycles
GET    /api/v1/cycle/insights                  # Phase-based correlations

# Fusion config (admin/dev)
GET    /api/v1/admin/fusion-config             # Current config
PUT    /api/v1/admin/fusion-config             # Update config
POST   /api/v1/admin/recompute                 # Recompute all fused data with new config
```

---

## Build Order

1. **fusion_config.yaml** + config loader — the editable brain
2. **Base adapter + normalized models** — canonical data shapes
3. **Garmin adapter** — Ev's primary device, sync + backfill
4. **Oura adapter** — Ev's ring, sync + backfill
5. **Sleep matcher** — match sessions across devices
6. **Fusion engine** — weighted merge with conflict detection
7. **Readiness score** — Vitalis proprietary score
8. **Apple Health adapter** — wife's device
9. **Menstrual cycle tracker** — temperature + symptom based
10. **Whoop adapter** — if API allows
11. **Tests throughout** — every component tested before next
