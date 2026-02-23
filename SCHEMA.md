# SCHEMA.md — Vitalis Data Architecture

**Version:** 1.0
**Phase:** 1 — Data Architecture
**Scale target:** 100K users × 5 years of daily wearable data
**Database:** PostgreSQL 15+
**Multi-tenancy:** Row-Level Security (RLS) on all user-data tables

---

## 1. Entity-Relationship Overview

```
┌─────────────┐         ┌─────────────┐
│  accounts   │──1:N───▶│    users    │
│ (billing)   │         │  (auth/PII) │
└─────────────┘         └──────┬──────┘
                               │ 1:N to everything below
         ┌─────────────────────┼──────────────────────────────────────┐
         │                     │                                      │
         ▼                     ▼                                      ▼
┌─────────────────┐  ┌──────────────────────┐  ┌─────────────────────────┐
│connected_devices│  │    wearable_daily     │  │      blood_panels       │
│ (OAuth tokens)  │  │ (unified daily rows)  │  │  (lab visit header)     │
└─────────────────┘  │ PARTITIONED BY date  │  └──────────┬──────────────┘
                     └──────────────────────┘             │ 1:N
                     ┌──────────────────────┐             ▼
                     │    wearable_sleep    │  ┌──────────────────────────┐
                     │ PARTITIONED BY date  │  │      blood_markers       │
                     └──────────────────────┘  │ (biomarker_id FK →dict) │
                     ┌──────────────────────┐  └──────────────────────────┘
                     │  wearable_activities │
                     │ PARTITIONED BY date  │  ┌──────────────────────────┐
                     └──────────────────────┘  │   biomarker_dictionary   │
                                               │   (canonical + aliases)  │
┌──────────────────────┐                       └──────────────────────────┘
│      dexa_scans      │
│  (scan header)       │  ┌──────────────────────────┐
├──────────────────────┤  │    epigenetic_tests       │
│     dexa_regions     │  │  (pace, bio age, etc.)   │
│  (body comp by zone) │  ├──────────────────────────┤
├──────────────────────┤  │  epigenetic_organ_ages   │
│  dexa_bone_density   │  │  (11 organ system ages)  │
└──────────────────────┘  └──────────────────────────┘

┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│ lifting_sessions │  │   supplements    │  │    mood_journal     │
│  lifting_sets    │  │ supplement_logs  │  │ menstrual_cycles    │
│exercise_dict     │  └──────────────────┘  │  doctor_visits      │
└──────────────────┘                        │   measurements      │
                                            │  custom_metrics     │
                                            │custom_metric_entries│
                                            │  nutrition_logs     │
                                            └─────────────────────┘

┌──────────────┐  ┌───────────┐  ┌─────────────────┐  ┌───────────────┐
│    goals     │  │ insights  │  │ ingestion_jobs  │  │  audit_log    │
│ goal_alerts  │  │           │  │                 │  │ (partitioned) │
└──────────────┘  └───────────┘  └─────────────────┘  └───────────────┘

┌────────────┐  ┌──────────────────┐  ┌────────────────────────┐
│  documents │  │ deletion_requests│  │  data_export_requests  │
│  (S3 PDFs) │  │ (GDPR/CCPA)      │  │  (GDPR portability)    │
└────────────┘  └──────────────────┘  └────────────────────────┘
```

---

## 2. Table Definitions

### 2.1 Identity & Auth

#### `accounts`
Billing entity. One account can contain 1–4 user profiles (Family tier).

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| account_id | UUID | PK, DEFAULT gen_random_uuid() | |
| stripe_customer_id | TEXT | UNIQUE | Nullable until payment added |
| subscription_tier | ENUM | NOT NULL DEFAULT 'free' | free / pro / family |
| subscription_status | ENUM | NOT NULL DEFAULT 'active' | |
| subscription_expires_at | TIMESTAMPTZ | | |
| max_users | SMALLINT | NOT NULL DEFAULT 1 | 1 (free/pro), 4 (family) |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| deleted_at | TIMESTAMPTZ | | Soft delete |

#### `users`
Auth identity. One user maps to one account. Contains PII.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| user_id | UUID | PK, DEFAULT gen_random_uuid() | |
| account_id | UUID | FK → accounts, NOT NULL | |
| email | TEXT | UNIQUE, NOT NULL | Normalized lowercase |
| email_verified_at | TIMESTAMPTZ | | |
| password_hash | TEXT | | bcrypt; NULL if OAuth-only |
| display_name | TEXT | NOT NULL | |
| date_of_birth | DATE | | PII — encrypted at rest |
| biological_sex | TEXT | | 'male', 'female', 'other', NULL |
| role | TEXT | NOT NULL DEFAULT 'user' | 'user', 'admin' |
| last_login_at | TIMESTAMPTZ | | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| deleted_at | TIMESTAMPTZ | | Soft delete — triggers GDPR job |

**Indexes:** `email`, `account_id`

#### `oauth_identities`
Social login linkage (Google, Apple, etc.)

| Column | Type | Constraints |
|--------|------|-------------|
| identity_id | UUID | PK |
| user_id | UUID | FK → users |
| provider | TEXT | NOT NULL — 'google', 'apple' |
| provider_user_id | TEXT | NOT NULL |
| access_token_enc | TEXT | AES-256 encrypted |
| refresh_token_enc | TEXT | AES-256 encrypted |
| expires_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Unique:** (provider, provider_user_id)

#### `user_preferences`
Display units, notification settings, goals display.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| user_id | UUID | PK, FK → users | |
| weight_unit | TEXT | 'lbs' | 'lbs' or 'kg' |
| height_unit | TEXT | 'in' | 'in' or 'cm' |
| distance_unit | TEXT | 'miles' | 'miles' or 'km' |
| temperature_unit | TEXT | 'F' | 'F' or 'C' |
| energy_unit | TEXT | 'kcal' | 'kcal' or 'kJ' |
| timezone | TEXT | 'UTC' | IANA timezone string |
| notifications_enabled | BOOLEAN | TRUE | |
| notification_prefs | JSONB | '{}' | Per-category notification settings |
| dashboard_layout | JSONB | '{}' | Widget order/visibility |
| updated_at | TIMESTAMPTZ | NOW() | |

---

### 2.2 Device Connections

#### `connected_devices`
OAuth tokens and sync state per user per source.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| device_id | UUID | PK | |
| user_id | UUID | FK → users, NOT NULL | |
| source | data_source ENUM | NOT NULL | garmin, oura, apple_health, etc. |
| display_name | TEXT | | e.g. "Garmin Forerunner 965" |
| access_token_enc | TEXT | | AES-256 encrypted |
| refresh_token_enc | TEXT | | AES-256 encrypted |
| token_expires_at | TIMESTAMPTZ | | |
| scope | TEXT[] | | OAuth scopes granted |
| external_user_id | TEXT | | User ID in source system |
| last_sync_at | TIMESTAMPTZ | | |
| last_sync_status | TEXT | | 'success', 'error', 'partial' |
| last_sync_error | TEXT | | |
| sync_cursor | JSONB | '{}' | Pagination/checkpoint state |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

**Unique:** (user_id, source) — one active connection per source
**Indexes:** (user_id), (source, last_sync_at) for batch sync jobs

---

### 2.3 Wearable Data

All wearable tables are **declaratively partitioned by date (RANGE)** with yearly partitions. Each partition is ~36.5M rows at 100K users.

#### `wearable_daily`
Unified daily summary. One row per (user_id, date, source). Multiple sources per day is valid and expected.

| Column | Type | Notes |
|--------|------|-------|
| daily_id | UUID | PK |
| user_id | UUID | FK → users, NOT NULL |
| date | DATE | NOT NULL |
| source | data_source ENUM | NOT NULL |
| resting_hr_bpm | SMALLINT | |
| max_hr_bpm | SMALLINT | |
| hrv_rmssd_ms | NUMERIC(6,2) | HRV in ms |
| steps | INTEGER | |
| active_calories_kcal | SMALLINT | |
| total_calories_kcal | SMALLINT | |
| active_minutes | SMALLINT | |
| moderate_intensity_minutes | SMALLINT | |
| vigorous_intensity_minutes | SMALLINT | |
| distance_m | INTEGER | |
| floors_climbed | SMALLINT | Garmin/Apple |
| spo2_avg_pct | NUMERIC(4,1) | |
| spo2_min_pct | NUMERIC(4,1) | |
| respiratory_rate_avg | NUMERIC(4,1) | breaths/min |
| stress_avg | SMALLINT | 0-100 |
| body_battery_start | SMALLINT | Garmin (0-100) |
| body_battery_end | SMALLINT | Garmin (0-100) |
| readiness_score | SMALLINT | Oura/WHOOP (0-100) |
| recovery_score | SMALLINT | WHOOP (0-100) |
| skin_temp_deviation_c | NUMERIC(4,2) | Oura deviation from baseline |
| vo2_max_ml_kg_min | NUMERIC(4,1) | If measured that day |
| raw_data | JSONB | Source-specific raw API response |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Partition:** RANGE (date), yearly
**Unique:** (user_id, date, source)
**Indexes:** (user_id, date DESC), (user_id, source, date DESC)

#### `wearable_sleep`
Detailed sleep data. One row per (user_id, sleep_date, source).

| Column | Type | Notes |
|--------|------|-------|
| sleep_id | UUID | PK |
| user_id | UUID | FK → users |
| sleep_date | DATE | NOT NULL — date the sleep ended (morning of) |
| source | data_source ENUM | NOT NULL |
| sleep_start | TIMESTAMPTZ | |
| sleep_end | TIMESTAMPTZ | |
| total_sleep_minutes | SMALLINT | |
| rem_minutes | SMALLINT | |
| deep_minutes | SMALLINT | |
| light_minutes | SMALLINT | |
| awake_minutes | SMALLINT | |
| sleep_latency_minutes | SMALLINT | Minutes to fall asleep |
| sleep_efficiency_pct | NUMERIC(4,1) | |
| sleep_score | SMALLINT | 0-100 (source-specific) |
| interruptions | SMALLINT | Wake events |
| avg_hr_bpm | SMALLINT | |
| min_hr_bpm | SMALLINT | |
| avg_hrv_ms | NUMERIC(6,2) | |
| avg_respiratory_rate | NUMERIC(4,1) | |
| avg_spo2_pct | NUMERIC(4,1) | |
| avg_skin_temp_deviation_c | NUMERIC(4,2) | |
| hypnogram | JSONB | Stage-by-stage timeline [{t, stage}] |
| raw_data | JSONB | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Partition:** RANGE (sleep_date), yearly
**Unique:** (user_id, sleep_date, source)
**Indexes:** (user_id, sleep_date DESC)

#### `wearable_activities`
Individual workouts and activities.

| Column | Type | Notes |
|--------|------|-------|
| activity_id | UUID | PK |
| user_id | UUID | FK → users |
| activity_date | DATE | NOT NULL — for partition key |
| source | data_source ENUM | NOT NULL |
| source_activity_id | TEXT | External ID for deduplication |
| activity_type | activity_type ENUM | NOT NULL |
| activity_name | TEXT | User-visible label |
| start_time | TIMESTAMPTZ | |
| end_time | TIMESTAMPTZ | |
| duration_seconds | INTEGER | |
| distance_m | NUMERIC(10,2) | |
| calories_kcal | SMALLINT | |
| avg_hr_bpm | SMALLINT | |
| max_hr_bpm | SMALLINT | |
| hr_zone_1_seconds | INTEGER | |
| hr_zone_2_seconds | INTEGER | |
| hr_zone_3_seconds | INTEGER | |
| hr_zone_4_seconds | INTEGER | |
| hr_zone_5_seconds | INTEGER | |
| avg_pace_sec_per_km | NUMERIC(7,2) | |
| avg_speed_kmh | NUMERIC(5,2) | |
| elevation_gain_m | NUMERIC(7,2) | |
| avg_power_watts | SMALLINT | Cycling/rowing |
| normalized_power_watts | SMALLINT | Cycling |
| training_stress_score | NUMERIC(6,1) | |
| training_effect_aerobic | NUMERIC(3,1) | 0.0–5.0 |
| training_effect_anaerobic | NUMERIC(3,1) | 0.0–5.0 |
| vo2_max_ml_kg_min | NUMERIC(4,1) | If estimated this activity |
| notes | TEXT | |
| raw_data | JSONB | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Partition:** RANGE (activity_date), yearly
**Unique:** (user_id, source, source_activity_id)
**Indexes:** (user_id, activity_date DESC), (user_id, activity_type, activity_date DESC)

---

### 2.4 Lab Work

#### `blood_panels`
Header for a lab visit / panel order.

| Column | Type | Notes |
|--------|------|-------|
| panel_id | UUID | PK |
| user_id | UUID | FK → users |
| lab_name | TEXT | Quest, Labcorp, etc. |
| lab_provider | TEXT | Ordering provider name |
| panel_name | TEXT | e.g. "Comprehensive Metabolic Panel" |
| collected_at | TIMESTAMPTZ | |
| reported_at | TIMESTAMPTZ | |
| fasting | BOOLEAN | |
| specimen_id | TEXT | Lab's specimen identifier |
| document_id | UUID | FK → documents (source PDF) |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, collected_at DESC)

#### `blood_markers`
Individual marker results, linked to a panel and the canonical dictionary.

| Column | Type | Notes |
|--------|------|-------|
| marker_id | UUID | PK |
| user_id | UUID | FK → users (denormalized for RLS) |
| panel_id | UUID | FK → blood_panels |
| biomarker_id | UUID | FK → biomarker_dictionary (nullable if unknown) |
| raw_name | TEXT | NOT NULL — exact name from report |
| sub_panel | TEXT | e.g. "CBC", "CMP", "Cardio IQ" |
| value_numeric | NUMERIC(12,4) | NULL for qualitative results |
| value_text | TEXT | For qualitative ("NEGATIVE", "A", "POSITIVE") |
| unit | TEXT | As reported by lab |
| value_canonical | NUMERIC(12,4) | Converted to canonical unit |
| ref_range_low | NUMERIC(12,4) | |
| ref_range_high | NUMERIC(12,4) | |
| ref_range_text | TEXT | Full text as printed |
| flag | TEXT | 'H', 'L', 'HH', 'LL', 'ABNORMAL', NULL |
| in_range | BOOLEAN | |
| optimal_low | NUMERIC(12,4) | From dictionary (at time of entry) |
| optimal_high | NUMERIC(12,4) | |
| lab_code | TEXT | Lab site code |
| parse_confidence | NUMERIC(3,2) | 0.00–1.00 if AI-parsed |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** (user_id, biomarker_id, panel_id), (user_id, collected_at via panel JOIN hint: index on panel collected_at)
**Note:** Add index on (user_id, biomarker_id) for trend queries across panels.

#### `biomarker_dictionary`
Canonical reference for all known biomarkers. Shared across all users (no RLS).

| Column | Type | Notes |
|--------|------|-------|
| biomarker_id | UUID | PK |
| canonical_name | TEXT | UNIQUE NOT NULL — slug: 'glucose', 'hdl_cholesterol' |
| display_name | TEXT | NOT NULL — "Glucose", "HDL Cholesterol" |
| category | biomarker_category ENUM | NOT NULL |
| subcategory | TEXT | "CBC", "CMP", "Cardio IQ", "Thyroid Panel" |
| canonical_unit | TEXT | NOT NULL — canonical storage unit |
| common_units | TEXT[] | All acceptable input units |
| loinc_code | TEXT | LOINC interoperability code |
| description | TEXT | Clinical description |
| aliases | TEXT[] | All known synonyms for AI matching |
| sex_specific_ranges | BOOLEAN | NOT NULL DEFAULT FALSE |
| optimal_low_male | NUMERIC(12,4) | |
| optimal_high_male | NUMERIC(12,4) | |
| optimal_low_female | NUMERIC(12,4) | |
| optimal_high_female | NUMERIC(12,4) | |
| normal_low | NUMERIC(12,4) | General population low |
| normal_high | NUMERIC(12,4) | General population high |
| is_qualitative | BOOLEAN | NOT NULL DEFAULT FALSE |
| sort_order | INTEGER | Display ordering within category |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** GIN on `aliases`, BTREE on `canonical_name`, BTREE on `category`

---

### 2.5 Body Composition (DEXA)

#### `dexa_scans`
Scan header — one row per scan session.

| Column | Type | Notes |
|--------|------|-------|
| scan_id | UUID | PK |
| user_id | UUID | FK → users |
| provider | TEXT | "DexaFit", "BodySpec", etc. |
| scan_date | DATE | NOT NULL |
| age_at_scan | NUMERIC(4,1) | |
| height_in | NUMERIC(5,2) | Height in inches as measured |
| weight_lbs | NUMERIC(6,2) | Scale weight same day |
| total_mass_lbs | NUMERIC(6,2) | From DEXA (may differ from scale) |
| total_fat_lbs | NUMERIC(6,2) | |
| total_lean_lbs | NUMERIC(6,2) | |
| total_bmc_lbs | NUMERIC(6,2) | Bone Mineral Content |
| total_body_fat_pct | NUMERIC(4,1) | |
| visceral_fat_lbs | NUMERIC(6,3) | |
| visceral_fat_in3 | NUMERIC(7,2) | Volume in cubic inches |
| android_gynoid_ratio | NUMERIC(4,2) | A/G ratio |
| document_id | UUID | FK → documents |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, scan_date DESC)

#### `dexa_regions`
Body fat % and composition by anatomical region. Normalized rows.

| Column | Type | Notes |
|--------|------|-------|
| region_id | UUID | PK |
| scan_id | UUID | FK → dexa_scans |
| user_id | UUID | FK → users (for RLS) |
| region | dexa_region ENUM | total, arms, arm_right, etc. |
| body_fat_pct | NUMERIC(4,1) | |
| fat_lbs | NUMERIC(6,2) | |
| lean_lbs | NUMERIC(6,2) | |
| bmc_lbs | NUMERIC(5,3) | |
| total_mass_lbs | NUMERIC(6,2) | |

**Unique:** (scan_id, region)
**Indexes:** (user_id, scan_id)

#### `dexa_bone_density`
BMD T-scores and Z-scores by skeletal region.

| Column | Type | Notes |
|--------|------|-------|
| density_id | UUID | PK |
| scan_id | UUID | FK → dexa_scans |
| user_id | UUID | FK → users (for RLS) |
| region | bone_density_region ENUM | |
| bmd_g_cm2 | NUMERIC(6,3) | Bone mineral density |
| t_score | NUMERIC(4,1) | vs. young adult (30-35yr peak) |
| z_score | NUMERIC(4,1) | vs. age-matched |

**Unique:** (scan_id, region)

---

### 2.6 Epigenetics

#### `epigenetic_tests`
Header for one test kit (Blueprint, TruDiagnostic, etc.)

| Column | Type | Notes |
|--------|------|-------|
| test_id | UUID | PK |
| user_id | UUID | FK → users |
| provider | TEXT | "Blueprint Biomarkers", "TruDiagnostic" |
| kit_id | TEXT | External kit identifier |
| collected_at | DATE | |
| reported_at | DATE | |
| chronological_age | NUMERIC(4,1) | |
| biological_age | NUMERIC(4,1) | Overall epigenetic age |
| pace_score | NUMERIC(4,2) | DunedinPACE — rate of aging |
| pace_percentile | NUMERIC(5,2) | % of population aging slower |
| telomere_length | NUMERIC(6,3) | kb, if measured |
| methylation_clock | TEXT | Algorithm used ('dunedinpace', 'horvath', etc.) |
| document_id | UUID | FK → documents |
| raw_data | JSONB | Full provider data |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, collected_at DESC)

#### `epigenetic_organ_ages`
Per-organ system biological age from one test. 11–12 rows per test.

| Column | Type | Notes |
|--------|------|-------|
| organ_age_id | UUID | PK |
| test_id | UUID | FK → epigenetic_tests |
| user_id | UUID | FK → users (for RLS) |
| organ_system | organ_system ENUM | lung, metabolic, heart, etc. |
| biological_age | NUMERIC(4,1) | |
| chronological_age | NUMERIC(4,1) | Repeated for convenience |
| delta_years | NUMERIC(4,1) | bio_age - chronological_age |
| direction | TEXT | 'younger', 'older', 'same' |

**Unique:** (test_id, organ_system)

---

### 2.7 Fitness (Lifting)

#### `lifting_sessions`
A single workout session.

| Column | Type | Notes |
|--------|------|-------|
| session_id | UUID | PK |
| user_id | UUID | FK → users |
| session_date | DATE | NOT NULL |
| source | data_source ENUM | 'strong', 'manual', 'garmin', etc. |
| source_session_id | TEXT | Dedup key |
| name | TEXT | "Upper A", "Push Day" |
| duration_seconds | INTEGER | |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, session_date DESC)

#### `lifting_sets`
Individual sets within a session.

| Column | Type | Notes |
|--------|------|-------|
| set_id | UUID | PK |
| session_id | UUID | FK → lifting_sessions |
| user_id | UUID | FK → users (for RLS) |
| exercise_id | UUID | FK → exercise_dictionary |
| set_number | SMALLINT | Order within exercise block |
| exercise_order | SMALLINT | Order of exercise in session |
| weight_lbs | NUMERIC(6,2) | |
| reps | SMALLINT | |
| rpe | NUMERIC(3,1) | Rate of Perceived Exertion 0-10 |
| is_warmup | BOOLEAN | DEFAULT FALSE |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** (user_id, session_id), (exercise_id, user_id) for PR lookup

#### `exercise_dictionary`
Canonical exercise catalog.

| Column | Type | Notes |
|--------|------|-------|
| exercise_id | UUID | PK |
| canonical_name | TEXT | UNIQUE NOT NULL |
| display_name | TEXT | NOT NULL |
| aliases | TEXT[] | For fuzzy CSV import matching |
| primary_muscle | TEXT | |
| secondary_muscles | TEXT[] | |
| equipment | TEXT | |
| category | TEXT | 'compound', 'isolation', 'cardio' |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

---

### 2.8 Manual Tracking

#### `measurements`
Generic scalar body metrics (weight, BP, temperature, etc.)

| Column | Type | Notes |
|--------|------|-------|
| measurement_id | UUID | PK |
| user_id | UUID | FK → users |
| metric | measurement_metric ENUM | weight, blood_pressure_systolic, etc. |
| value | NUMERIC(10,3) | NOT NULL |
| unit | TEXT | NOT NULL |
| measured_at | TIMESTAMPTZ | NOT NULL |
| source | data_source ENUM | manual, garmin, withings, etc. |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, metric, measured_at DESC)

#### `custom_metrics`
User-defined metric definitions.

| Column | Type | Notes |
|--------|------|-------|
| metric_id | UUID | PK |
| user_id | UUID | FK → users |
| name | TEXT | NOT NULL |
| unit | TEXT | |
| data_type | TEXT | 'numeric', 'boolean', 'text', 'scale_1_5' |
| min_value | NUMERIC | For validation |
| max_value | NUMERIC | |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Unique:** (user_id, name)

#### `custom_metric_entries`
Values for custom metrics.

| Column | Type | Notes |
|--------|------|-------|
| entry_id | UUID | PK |
| metric_id | UUID | FK → custom_metrics |
| user_id | UUID | FK → users (for RLS) |
| value_numeric | NUMERIC | |
| value_text | TEXT | |
| measured_at | TIMESTAMPTZ | NOT NULL |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** (user_id, metric_id, measured_at DESC)

#### `supplements`
Supplement and medication tracking.

| Column | Type | Notes |
|--------|------|-------|
| supplement_id | UUID | PK |
| user_id | UUID | FK → users |
| name | TEXT | NOT NULL |
| brand | TEXT | |
| dose_amount | NUMERIC(8,3) | |
| dose_unit | TEXT | 'mg', 'g', 'IU', 'mcg' |
| frequency | TEXT | 'daily', '2x_daily', 'weekly', etc. |
| timing | TEXT | 'morning', 'evening', 'with_meal' |
| started_at | DATE | |
| ended_at | DATE | NULL = currently taking |
| purpose | TEXT | Free text or category |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, started_at DESC), (user_id) WHERE ended_at IS NULL

#### `supplement_logs`
Daily intake log for correlation analysis.

| Column | Type | Notes |
|--------|------|-------|
| log_id | UUID | PK |
| supplement_id | UUID | FK → supplements |
| user_id | UUID | FK → users (for RLS) |
| taken_at | TIMESTAMPTZ | NOT NULL |
| dose_amount | NUMERIC(8,3) | May differ from default dose |
| dose_unit | TEXT | |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** (user_id, taken_at DESC), (supplement_id, taken_at)

#### `nutrition_logs`
Flexible meal and fasting logs. JSONB for meal data to support multiple nutrition sources.

| Column | Type | Notes |
|--------|------|-------|
| nutrition_id | UUID | PK |
| user_id | UUID | FK → users |
| log_date | DATE | NOT NULL |
| meal_type | TEXT | 'breakfast', 'lunch', 'dinner', 'snack', 'fast' |
| calories_kcal | SMALLINT | |
| protein_g | NUMERIC(6,2) | |
| carbs_g | NUMERIC(6,2) | |
| fat_g | NUMERIC(6,2) | |
| fiber_g | NUMERIC(6,2) | |
| source | data_source ENUM | |
| raw_data | JSONB | Full source data for any schema |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, log_date DESC)

#### `mood_journal`
Daily mood, energy, and stress check-in.

| Column | Type | Notes |
|--------|------|-------|
| journal_id | UUID | PK |
| user_id | UUID | FK → users |
| journal_date | DATE | NOT NULL |
| mood_score | SMALLINT | CHECK (1–5) |
| energy_score | SMALLINT | CHECK (1–5) |
| stress_score | SMALLINT | CHECK (1–5) |
| notes | TEXT | Free text journal |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Unique:** (user_id, journal_date)

#### `menstrual_cycles`
Cycle tracking with phase and symptom data.

| Column | Type | Notes |
|--------|------|-------|
| cycle_id | UUID | PK |
| user_id | UUID | FK → users |
| cycle_date | DATE | NOT NULL |
| phase | menstrual_phase ENUM | |
| flow_intensity | SMALLINT | CHECK (0–4): 0=none, 1=spotting, 4=heavy |
| symptoms | TEXT[] | ['cramps', 'headache', 'bloating', ...] |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Unique:** (user_id, cycle_date)
**Indexes:** (user_id, cycle_date DESC)

#### `doctor_visits`
Medical appointments and notes.

| Column | Type | Notes |
|--------|------|-------|
| visit_id | UUID | PK |
| user_id | UUID | FK → users |
| visit_date | DATE | NOT NULL |
| provider_name | TEXT | |
| specialty | TEXT | 'Primary Care', 'Cardiology', etc. |
| notes | TEXT | |
| follow_up_date | DATE | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

#### `doctor_visit_panels`
Link table: visits to blood panels ordered that day.

| Column | Type |
|--------|------|
| visit_id | UUID FK → doctor_visits |
| panel_id | UUID FK → blood_panels |

**PK:** (visit_id, panel_id)

#### `photos`
Progress photos linked to date and optional DEXA scan.

| Column | Type | Notes |
|--------|------|-------|
| photo_id | UUID | PK |
| user_id | UUID | FK → users |
| photo_date | DATE | NOT NULL |
| photo_type | TEXT | 'front', 'back', 'left', 'right', 'other' |
| s3_key | TEXT | NOT NULL — path in S3/R2 |
| s3_thumbnail_key | TEXT | |
| file_size_bytes | INTEGER | |
| linked_scan_id | UUID | FK → dexa_scans (optional) |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, photo_date DESC)

#### `documents`
Source PDFs uploaded by the user.

| Column | Type | Notes |
|--------|------|-------|
| document_id | UUID | PK |
| user_id | UUID | FK → users |
| document_type | document_type ENUM | blood_work, dexa, epigenetics, etc. |
| provider_name | TEXT | Quest, DexaFit, Blueprint, etc. |
| original_filename | TEXT | |
| s3_key | TEXT | NOT NULL |
| file_size_bytes | INTEGER | |
| mime_type | TEXT | DEFAULT 'application/pdf' |
| parse_status | parse_status ENUM | DEFAULT 'pending' |
| parse_confidence | NUMERIC(3,2) | 0.00–1.00 |
| parse_result | JSONB | Raw LLM extraction |
| parsed_at | TIMESTAMPTZ | |
| confirmed_at | TIMESTAMPTZ | |
| confirmed_by | UUID | FK → users (could be different user) |
| linked_record_id | UUID | UUID of resulting panel/scan/test |
| linked_record_type | TEXT | 'blood_panel', 'dexa_scan', 'epigenetic_test' |
| error_message | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, created_at DESC), (parse_status) WHERE parse_status = 'pending'

---

### 2.9 Goals & Insights

#### `goals`
User-defined targets for any trackable metric.

| Column | Type | Notes |
|--------|------|-------|
| goal_id | UUID | PK |
| user_id | UUID | FK → users |
| metric_type | TEXT | 'blood_marker', 'measurement', 'wearable', 'custom' |
| biomarker_id | UUID | FK → biomarker_dictionary (if blood_marker) |
| metric_name | TEXT | Canonical metric name |
| target_value | NUMERIC(12,4) | |
| target_unit | TEXT | |
| direction | goal_direction ENUM | minimize / maximize / target |
| alert_threshold_low | NUMERIC(12,4) | Alert if below this |
| alert_threshold_high | NUMERIC(12,4) | Alert if above this |
| alert_enabled | BOOLEAN | DEFAULT TRUE |
| notes | TEXT | |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

#### `goal_alerts`
Fired alerts when thresholds are crossed.

| Column | Type | Notes |
|--------|------|-------|
| alert_id | UUID | PK |
| goal_id | UUID | FK → goals |
| user_id | UUID | FK → users |
| triggered_at | TIMESTAMPTZ | NOT NULL |
| trigger_value | NUMERIC(12,4) | |
| message | TEXT | |
| acknowledged_at | TIMESTAMPTZ | |

#### `insights`
AI-generated correlations and recommendations, cached for dashboard.

| Column | Type | Notes |
|--------|------|-------|
| insight_id | UUID | PK |
| user_id | UUID | FK → users |
| insight_type | insight_type ENUM | |
| title | TEXT | NOT NULL |
| body | TEXT | NOT NULL |
| metric_a | TEXT | Primary metric involved |
| metric_b | TEXT | Secondary metric (correlation) |
| correlation_r | NUMERIC(4,3) | Pearson r if applicable |
| p_value | NUMERIC(8,6) | Statistical significance |
| data_points | INTEGER | n used in analysis |
| valid_from | DATE | |
| valid_until | DATE | Cache expiry |
| is_dismissed | BOOLEAN | DEFAULT FALSE |
| dismissed_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** (user_id, insight_type, created_at DESC)
**Note:** Refresh nightly for active users. Invalidate when new data arrives.

---

### 2.10 System & Operations

#### `ingestion_jobs`
Job queue for all async data work (syncs, parses, exports).

| Column | Type | Notes |
|--------|------|-------|
| job_id | UUID | PK |
| user_id | UUID | FK → users (nullable for system jobs) |
| source | data_source ENUM | |
| job_type | job_type ENUM | daily_sync, backfill, document_parse, etc. |
| status | job_status ENUM | DEFAULT 'queued' |
| priority | SMALLINT | DEFAULT 5 (1=highest, 10=lowest) |
| payload | JSONB | Input params |
| result | JSONB | Output / stats |
| error_message | TEXT | |
| attempts | SMALLINT | DEFAULT 0 |
| max_attempts | SMALLINT | DEFAULT 3 |
| queued_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| started_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |
| next_retry_at | TIMESTAMPTZ | |

**Indexes:** (status, next_retry_at) for worker polling, (user_id, job_type, queued_at DESC)

#### `audit_log`
Immutable record of all data mutations. Partitioned quarterly.

| Column | Type | Notes |
|--------|------|-------|
| audit_id | UUID | PK |
| user_id | UUID | Affected user's data |
| action_by | UUID | User performing the action |
| table_name | TEXT | NOT NULL |
| record_id | UUID | NOT NULL |
| action | audit_action ENUM | INSERT / UPDATE / DELETE |
| old_values | JSONB | Previous state (UPDATE/DELETE) |
| new_values | JSONB | New state (INSERT/UPDATE) |
| ip_address | INET | |
| user_agent | TEXT | |
| request_id | UUID | Trace ID from API |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Partition:** RANGE (created_at), quarterly
**Indexes:** (user_id, created_at DESC), (table_name, record_id), (action_by, created_at DESC)
**Note:** Audit log rows are NEVER deleted, even after GDPR deletion. PII is anonymized (user_id → NULL, old_values/new_values stripped of email/DOB fields) on account deletion.

#### `deletion_requests`
GDPR/CCPA deletion tracking with 30-day grace period.

| Column | Type | Notes |
|--------|------|-------|
| request_id | UUID | PK |
| user_id | UUID | FK → users |
| requested_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| grace_period_ends_at | TIMESTAMPTZ | = requested_at + 30 days |
| status | TEXT | 'pending', 'processing', 'completed', 'canceled' |
| completed_at | TIMESTAMPTZ | |
| tables_deleted | TEXT[] | Audit of what was deleted |

#### `data_export_requests`
GDPR data portability requests.

| Column | Type | Notes |
|--------|------|-------|
| export_id | UUID | PK |
| user_id | UUID | FK → users |
| requested_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| status | TEXT | 'queued', 'processing', 'ready', 'downloaded', 'expired' |
| format | TEXT | 'json', 'csv' |
| s3_key | TEXT | Temporary download location |
| expires_at | TIMESTAMPTZ | 7-day expiry |
| completed_at | TIMESTAMPTZ | |
| file_size_bytes | BIGINT | |

---

## 3. Row-Level Security Strategy

### Approach
All user-data tables have RLS enabled. A PostgreSQL session variable `app.current_user_id` is set at the start of every connection by the API layer. The variable is populated from the validated JWT.

```sql
-- Set at connection time by API (FastAPI + asyncpg)
SET app.current_user_id = '<user_uuid>';

-- RLS policy on every user-data table
CREATE POLICY user_isolation ON wearable_daily
    USING (user_id = current_setting('app.current_user_id')::uuid);
```

### Roles
| Role | Can Do | Notes |
|------|--------|-------|
| `vitalis_api` | SELECT/INSERT/UPDATE/DELETE on own rows | Subject to RLS |
| `vitalis_worker` | Same as api + cross-user job management | For ingestion workers |
| `vitalis_admin` | BYPASS RLS | Emergency access only, audited |
| `vitalis_readonly` | SELECT only | Analytics replica access |

### Tables with RLS
Every table except: `biomarker_dictionary`, `exercise_dictionary`, `accounts` (account-level RLS instead of user-level).

### Household Accounts
Family plan users can optionally share profile views. This is handled at the application layer, not at the database RLS layer — API checks account membership before allowing cross-user read access. Database row ownership stays with the individual user.

---

## 4. Migration Strategy (Alembic)

### Configuration
```
alembic/
  env.py           # Connects to DB, sets search path
  versions/        # Migration scripts
  script.py.mako   # Template for new migrations
alembic.ini        # Points to DATABASE_URL env var
```

### Conventions
- Every schema change = one Alembic migration file
- Migration filenames: `{revision}_{short_description}.py`
- `upgrade()` is always idempotent where possible (IF NOT EXISTS)
- `downgrade()` is always implemented
- No raw `ALTER TABLE` in production — always via migration
- Data migrations in separate files from schema migrations
- Migrations run automatically on deploy (pre-start hook in Docker)
- Lock timeout set to 5s to avoid blocking prod (`SET lock_timeout = '5s'`)

### New Partition Creation
Yearly partitions for time-series tables must be created in advance. A cron job (or migration) runs each December to create the following year's partitions:

```python
# Automated partition management
def create_yearly_partitions(year: int):
    tables = ['wearable_daily', 'wearable_sleep', 'wearable_activities']
    for table in tables:
        # CREATE TABLE {table}_{year} PARTITION OF {table} ...
```

---

## 5. Backup Strategy

### Automated Backups
| Type | Frequency | Retention | Storage |
|------|-----------|-----------|---------|
| WAL archiving (PITR) | Continuous | 7 days | S3 |
| Daily logical dump | 02:00 UTC | 30 days | S3 |
| Weekly pg_dump | Sunday 03:00 | 12 weeks | S3 (separate bucket) |
| Monthly snapshot | 1st of month | 12 months | S3 Glacier |

### Point-in-Time Recovery
- WAL-G or pgBackRest configured for continuous WAL shipping to S3
- Recovery time objective (RTO): < 1 hour
- Recovery point objective (RPO): < 5 minutes

### Restore Testing
- Automated weekly restore-to-staging test
- Alert fires if restore fails

### S3 Bucket Layout
```
s3://vitalis-backups/
  wal/                    # WAL segments for PITR
  daily/{YYYY-MM-DD}/     # Daily dumps
  weekly/{YYYY-WW}/       # Weekly dumps
  monthly/{YYYY-MM}/      # Monthly snapshots
```

---

## 6. Data Validation Rules

All data entering the system is validated via **Pydantic v2 models** in the API and worker layers. Database constraints are the last line of defense.

### Key Validation Rules

| Entity | Rule |
|--------|------|
| `blood_markers.value_numeric` | Must be a finite float; reject Inf/NaN |
| `blood_markers.unit` | Must match one of `biomarker_dictionary.common_units` for the marker |
| `wearable_daily.resting_hr_bpm` | Range: 20–300 |
| `wearable_daily.hrv_rmssd_ms` | Range: 1–300 |
| `wearable_daily.spo2_avg_pct` | Range: 70–100 |
| `wearable_daily.steps` | Range: 0–100000 |
| `measurements.value` (weight) | Range: 20–1000 lbs |
| `mood_journal.*_score` | Integer 1–5 |
| `lifting_sets.weight_lbs` | Range: 0–2000 |
| `lifting_sets.reps` | Range: 1–999 |
| `dexa_regions.body_fat_pct` | Range: 1–80 |
| `epigenetic_tests.pace_score` | Range: 0.2–3.0 |
| `users.email` | Valid email format, lowercase normalized |
| `users.date_of_birth` | Must be in past, age 13–150 |

### Duplicate Detection
- Wearable sync uses `(user_id, source, source_activity_id)` for activities
- `(user_id, date, source)` unique constraint on daily and sleep tables
- Blood marker deduplication: same panel_id + biomarker_id (accept re-import override with confirmed flag)
- All writes are idempotent via `ON CONFLICT DO UPDATE` where appropriate

---

## 7. Canonical Biomarker Dictionary Design

### Philosophy
- One canonical slug per biomarker (e.g., `glucose`, `hdl_cholesterol`, `testosterone_total`)
- Comprehensive aliases array for AI-assisted parsing (e.g., `['glucose', 'blood glucose', 'serum glucose', 'GLUC']`)
- Sex-specific optimal ranges stored separately (hormones, ferritin, etc.)
- LOINC codes for EHR interoperability
- Categories enable dashboard grouping and filtering

### Seeding
The initial seed file contains 80+ markers extracted from the Quest blood work sample, organized by category:
- **Metabolic** (CMP: glucose, BUN, creatinine, eGFR, electrolytes, proteins, liver enzymes)
- **Lipids** (cholesterol, HDL, LDL, triglycerides, non-HDL)
- **Lipids Advanced** (LDL-P, LDL small/medium, HDL large, ApoB, Lp(a), pattern, peak size)
- **Fatty Acids** (omega-3/6, EPA, DPA, DHA, AA, LA)
- **Thyroid** (TSH, T3/T4, antibodies)
- **Hormones** (testosterone, estradiol, FSH, LH, prolactin, SHBG, DHEA-S, cortisol, insulin, leptin)
- **Hematology** (CBC with 5-part differential)
- **Inflammation** (hs-CRP, homocysteine, RF)
- **Nutrition/Vitamins** (Vitamin D, ferritin, iron, MMA/B12, zinc, magnesium)
- **Heavy Metals** (mercury, lead)
- **Immunology** (ANA screen)
- **Urinalysis** (qualitative dipstick + microscopy)

### Unit Conversion Service
See Section 8.

---

## 8. Unit Conversion Approach

### Design
A `UnitConverter` service maintains a conversion table covering all units used by biomarkers and measurements. Values are stored in both raw (as-reported) and canonical (converted) units.

### Conversion Pairs
| From | To | Factor |
|------|----|--------|
| ng/dL | nmol/L (testosterone) | × 0.03467 |
| pg/mL | pmol/L (estradiol) | × 3.671 |
| mg/dL | mmol/L (glucose) | × 0.05551 |
| mg/dL | mmol/L (cholesterol) | × 0.02586 |
| mg/dL | μmol/L (creatinine) | × 88.42 |
| lbs | kg | × 0.45359 |
| in | cm | × 2.54 |
| °F | °C | (F-32) × 5/9 |
| mcg/dL | nmol/L (DHEA-S) | × 0.02714 |

### Implementation
```python
# canonical_unit stored in biomarker_dictionary
# value_canonical stored in blood_markers
class UnitConverter:
    def to_canonical(self, value: float, from_unit: str, biomarker_id: UUID) -> float:
        ...
```

### Storage Policy
Always store both `value_numeric` (raw) and `value_canonical` (normalized) in `blood_markers`. This allows re-conversion if the canonical unit changes.

---

## 9. Performance

### Partitioning Strategy

| Table | Partition Key | Partition Size | Estimated Rows @ 100K users, 5yr |
|-------|--------------|----------------|-----------------------------------|
| `wearable_daily` | `date` (yearly) | ~37M rows/partition | 182.5M total |
| `wearable_sleep` | `sleep_date` (yearly) | ~37M rows/partition | 182.5M total |
| `wearable_activities` | `activity_date` (yearly) | ~20M rows/partition | ~100M total |
| `audit_log` | `created_at` (quarterly) | ~20-50M rows/partition | High write volume |
| `blood_markers` | Not partitioned | ~800 rows/user × 5yr = 80M | Acceptable unpartitioned |

### Critical Indexes

```sql
-- Time-series range scans (most common query pattern)
CREATE INDEX ON wearable_daily (user_id, date DESC);
CREATE INDEX ON wearable_sleep (user_id, sleep_date DESC);
CREATE INDEX ON wearable_activities (user_id, activity_date DESC);

-- Biomarker trend queries
CREATE INDEX ON blood_markers (user_id, biomarker_id, panel_id);
CREATE INDEX ON blood_panels (user_id, collected_at DESC);

-- Biomarker dictionary alias search (for AI parsing)
CREATE INDEX ON biomarker_dictionary USING GIN (aliases);
CREATE INDEX ON biomarker_dictionary (canonical_name);
CREATE INDEX ON biomarker_dictionary (category);

-- Goal/insight lookups
CREATE INDEX ON goals (user_id) WHERE is_active = TRUE;
CREATE INDEX ON insights (user_id, created_at DESC) WHERE is_dismissed = FALSE;

-- Job queue worker polling
CREATE INDEX ON ingestion_jobs (status, next_retry_at)
    WHERE status IN ('queued', 'failed');

-- DEXA/Epigenetics history
CREATE INDEX ON dexa_scans (user_id, scan_date DESC);
CREATE INDEX ON epigenetic_tests (user_id, collected_at DESC);

-- Supplement correlation analysis
CREATE INDEX ON supplement_logs (user_id, taken_at DESC);
CREATE INDEX ON supplement_logs (supplement_id, taken_at);
```

### Connection Pooling
- **PgBouncer** in transaction mode between API and PostgreSQL
- Pool size: 20 connections per API worker
- Max overflow: 10
- Idle timeout: 300s

### Query Patterns & Optimization
- Dashboard home page: single user, last 30 days → hits (user_id, date DESC) index → partition pruning to current year partition
- Trend charts: single user, single biomarker, 2 years → (user_id, biomarker_id) index
- Cross-domain correlation: pre-computed nightly, stored in `insights` table
- Aggregate stats (benchmarks): read replica only, materialized views refreshed daily

---

## 10. GDPR/CCPA Deletion Strategy

### Deletion Flow
```
User requests deletion
    → deletion_request created (status=pending)
    → Confirmation email sent (30-day grace period starts)
    → User can cancel within 30 days

After 30 days:
    → deletion_job runs
    → All user data hard-deleted from:
        users, user_preferences, connected_devices,
        wearable_daily, wearable_sleep, wearable_activities,
        blood_panels, blood_markers,
        dexa_scans, dexa_regions, dexa_bone_density,
        epigenetic_tests, epigenetic_organ_ages,
        lifting_sessions, lifting_sets,
        measurements, custom_metrics, custom_metric_entries,
        supplements, supplement_logs, nutrition_logs,
        mood_journal, menstrual_cycles,
        doctor_visits, photos, documents,
        goals, goal_alerts, insights,
        deletion_requests (status updated to 'completed')
    → S3 objects deleted (PDFs, photos)
    → audit_log: user_id set to NULL, PII columns zeroed
    → Stripe customer deleted
    → deletion_request.status = 'completed'
```

### Soft Deletes
Tables with `deleted_at` column use soft deletes for:
- Accidental deletion recovery within grace period
- Maintaining referential integrity during grace period

### Data Minimization
- Session tokens expire and are not retained
- Raw API responses in `raw_data` JSONB can be purged after successful processing
- Anonymization: aggregated/analytical data (insights, benchmarks) retains no user_id link after processing

### Right to Access (Portability)
- `/api/v1/me/export` triggers a `data_export_request`
- Worker serializes all user data to JSON or CSV
- Files uploaded to S3 with signed URL, 7-day expiry
- User notified by email

---

## 11. Audit Logging

### What Gets Logged
Every INSERT, UPDATE, and DELETE on user-data tables is captured via PostgreSQL triggers.

```sql
-- Trigger function writes to audit_log
CREATE OR REPLACE FUNCTION audit_trigger_fn() RETURNS TRIGGER ...
```

Logged fields: `table_name`, `record_id`, `action`, `old_values`, `new_values`, timestamp, request_id (from session variable).

### What is NOT Logged
- SELECT queries (too high volume; use pg_stat_statements for query analytics)
- Reads on `biomarker_dictionary` (shared, non-sensitive)
- Heartbeat / health check queries

### Retention
- Audit log rows are **never hard-deleted**
- On GDPR deletion: `user_id` set to NULL, `old_values`/`new_values` stripped of email, DOB, name fields
- Quarterly partitions allow efficient range deletion if regulatory requirements change

### Security Events
Special `audit_action` values for security events:
- `LOGIN` — successful login (IP, user_agent)
- `LOGOUT` — explicit logout
- `EXPORT` — data export triggered

These are also captured in audit_log regardless of data changes.
