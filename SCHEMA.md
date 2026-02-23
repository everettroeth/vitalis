# SCHEMA.md — Vitalis Data Architecture

**Version:** 2.0 (QA-Revised)
**Phase:** 1 — Data Architecture
**Scale target:** 100K users × 5 years of daily wearable data
**Database:** PostgreSQL 15+
**Multi-tenancy:** Row-Level Security (RLS) on all user-data tables
**QA Revision Date:** 2026-02-22 — All Critical, High, and Medium issues from QA-SCHEMA-REVIEW.md resolved.

---

## 1. Entity-Relationship Overview

```
┌─────────────┐         ┌─────────────┐         ┌──────────────────┐
│  accounts   │──1:N───▶│    users    │──1:N───▶│  user_sessions   │
│ (billing)   │         │  (auth/PII) │         │ (refresh tokens) │
└─────────────┘         └──────┬──────┘         └──────────────────┘
                               │                 ┌──────────────────┐
                               │                 │  user_consents   │
                               │ 1:N to below    │  (GDPR/opt-ins)  │
                               │                 └──────────────────┘
         ┌─────────────────────┼──────────────────────────────────────┐
         │                     │                                      │
         ▼                     ▼                                      ▼
┌─────────────────┐  ┌──────────────────────┐  ┌─────────────────────────┐
│connected_devices│  │    wearable_daily     │  │      blood_panels       │
│ (OAuth tokens)  │  │ PARTITIONED BY date  │  │  (lab visit header)     │
└─────────────────┘  └──────────────────────┘  └──────────┬──────────────┘
                     ┌──────────────────────┐             │ 1:N
                     │    wearable_sleep    │             ▼
                     │ PARTITIONED BY date  │  ┌──────────────────────────┐
                     └──────────────────────┘  │      blood_markers       │
                     ┌──────────────────────┐  │ (biomarker_id FK → dict) │
                     │  wearable_activities │  └──────────────────────────┘
                     │ PARTITIONED BY date  │
                     └──────────────────────┘  ┌──────────────────────────┐
                                               │   biomarker_dictionary   │
                                               │   (canonical + aliases)  │
                                               └──────────────────────────┘
                                               ┌──────────────────────────┐
                                               │    biomarker_ranges      │
                                               │  (age+sex-specific)      │
                                               └──────────────────────────┘

┌──────────────────────┐                       ┌──────────────────────────┐
│      dexa_scans      │                       │    epigenetic_tests       │
│  (scan header)       │                       │  (pace, bio age, etc.)   │
├──────────────────────┤                       ├──────────────────────────┤
│     dexa_regions     │                       │  epigenetic_organ_ages   │
│  (body comp by zone) │                       │  (11 organ system ages)  │
├──────────────────────┤                       └──────────────────────────┘
│  dexa_bone_density   │
└──────────────────────┘

┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│ lifting_sessions │  │   supplements    │  │    mood_journal     │
│  lifting_sets    │  │ supplement_logs  │  │ menstrual_cycles    │
│ exercise_dict    │  └──────────────────┘  │  doctor_visits      │
└──────────────────┘                        │   measurements      │
                                            │  custom_metrics     │
                                            │custom_metric_entries│
                                            │  nutrition_logs     │
                                            │  notifications      │
                                            └─────────────────────┘

┌──────────────┐  ┌───────────┐  ┌─────────────────────┐  ┌───────────────┐
│    goals     │  │ insights  │  │  ingestion_jobs     │  │  audit_log    │
│ goal_alerts  │  │           │  │  (PARTITIONED)      │  │ (partitioned) │
└──────────────┘  └───────────┘  └─────────────────────┘  └───────────────┘

┌────────────┐  ┌──────────────────┐  ┌────────────────────────┐
│  documents │  │ deletion_requests│  │  data_export_requests  │
│  (S3 PDFs) │  │ (GDPR/CCPA)      │  │  (GDPR portability)    │
└────────────┘  └──────────────────┘  └────────────────────────┘

┌───────────────────┐  ┌────────────────────┐
│   data_sources    │  │   activity_types   │
│  (lookup table)   │  │  (lookup table)    │
└───────────────────┘  └────────────────────┘
```

---

## 2. Table Definitions

### 2.1 Identity & Auth

#### `accounts`
Billing entity. One account contains 1–4 user profiles (Family tier).
**v2 change:** RLS enabled. `account_isolation` policy restricts access to the user's own account.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| account_id | UUID | PK, DEFAULT gen_random_uuid() | |
| stripe_customer_id | TEXT | UNIQUE | Nullable until payment added |
| account_type | ENUM | NOT NULL DEFAULT 'individual' | individual / household |
| subscription_tier | ENUM | NOT NULL DEFAULT 'free' | free / pro / family |
| subscription_status | ENUM | NOT NULL DEFAULT 'active' | active / past_due / canceled / trialing |
| subscription_expires_at | TIMESTAMPTZ | | |
| max_users | SMALLINT | NOT NULL DEFAULT 1, CHECK 1–4 | 1 (free/pro), 4 (family) |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| deleted_at | TIMESTAMPTZ | | Soft delete |

**RLS (C7 fix):** Enabled. Policy restricts access to accounts containing the current user.

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
| biological_sex | TEXT | CHECK IN ('male','female','other') | |
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
| user_id | UUID | FK → users ON DELETE CASCADE |
| provider | TEXT | NOT NULL CHECK IN ('google','apple','microsoft') |
| provider_user_id | TEXT | NOT NULL |
| access_token_enc | TEXT | AES-256 encrypted |
| refresh_token_enc | TEXT | AES-256 encrypted |
| expires_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Unique:** (provider, provider_user_id)

#### `user_preferences`
Display units, notification settings, goals display.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| user_id | UUID | PK, FK → users ON DELETE CASCADE | |
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

#### `user_sessions` *(New in v2 — MT1)*
Active sessions and refresh token tracking.

| Column | Type | Notes |
|--------|------|-------|
| session_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| refresh_token_hash | TEXT | NOT NULL UNIQUE — bcrypt/SHA-256 of token |
| ip_address | INET | |
| user_agent | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| expires_at | TIMESTAMPTZ | NOT NULL |
| last_active_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| revoked_at | TIMESTAMPTZ | |
| revoke_reason | TEXT | 'logout', 'password_change', 'admin', 'expired', 'security' |

**Indexes:** (user_id, expires_at), (refresh_token_hash)

#### `user_consents` *(New in v2 — G2)*
GDPR consent tracking for opt-in features.

| Column | Type | Notes |
|--------|------|-------|
| consent_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| consent_type | TEXT | NOT NULL — 'benchmarks', 'ai_coaching', 'doctor_sharing', 'marketing', 'analytics' |
| granted_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| revoked_at | TIMESTAMPTZ | NULL = currently active |
| ip_address | INET | Consent recorded from |

**Unique:** (user_id, consent_type)

---

### 2.2 Reference / Lookup Tables

#### `data_sources` *(New in v2 — E1 fix)*
Replaces the `data_source` ENUM. Adding new adapters requires only an INSERT, not a migration.

| Column | Type | Notes |
|--------|------|-------|
| source_id | TEXT | PK — 'garmin', 'oura', etc. |
| display_name | TEXT | NOT NULL |
| category | TEXT | NOT NULL — 'wearable', 'lab', 'manual', 'api' |
| adapter_class | TEXT | Python class name for ingestion adapter |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Seeded values:** garmin, apple_health, oura, whoop, strong, manual, quest, labcorp, dexafit, blueprint, trudiagnostic, withings, fitbit, samsung_health, dexcom, levels, eight_sleep, api, other

#### `activity_types` *(New in v2 — E1 fix)*
Replaces the `activity_type` ENUM. Users can add custom types (bouldering, paddleboarding, etc.) without migrations.

| Column | Type | Notes |
|--------|------|-------|
| type_id | TEXT | PK — 'running', 'cycling', etc. |
| display_name | TEXT | NOT NULL |
| category | TEXT | NOT NULL — 'cardio', 'strength', 'flexibility', 'sports', 'other' |
| met_estimate | NUMERIC(4,1) | Metabolic equivalent for calorie estimation |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

---

### 2.3 Device Connections

#### `connected_devices`
OAuth tokens and sync state per user per source.
**v2 change:** `source` column is now `TEXT NOT NULL REFERENCES data_sources(source_id)`.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| device_id | UUID | PK | |
| user_id | UUID | FK → users ON DELETE CASCADE | |
| source | TEXT | FK → data_sources, NOT NULL | garmin, oura, apple_health, etc. |
| display_name | TEXT | | e.g. "Garmin Forerunner 965" |
| access_token_enc | TEXT | | AES-256 encrypted |
| refresh_token_enc | TEXT | | |
| token_expires_at | TIMESTAMPTZ | | |
| scope | TEXT[] | | OAuth scopes granted |
| external_user_id | TEXT | | User ID in source system |
| last_sync_at | TIMESTAMPTZ | | |
| last_sync_status | TEXT | CHECK IN ('success','error','partial') | |
| last_sync_error | TEXT | | |
| sync_cursor | JSONB | '{}' | Pagination/checkpoint state |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | |

**Unique:** (user_id, source)
**Indexes:** (user_id), (source, last_sync_at) WHERE is_active = TRUE

---

### 2.4 Wearable Data

All wearable tables are **declaratively partitioned by date (RANGE)** with yearly partitions. Partitions exist from **2018 to 2028** plus a DEFAULT partition to catch any out-of-range data (v2 fix for EC6/P5).

**v2 changes on all wearable tables:**
- Added `REFERENCES users(user_id) ON DELETE CASCADE` (C3 fix — GDPR deletion now cascades)
- `source` column is now TEXT FK to `data_sources`
- Added DEFAULT partition for pre-2018 and post-2028 data

#### `wearable_daily`
Unified daily summary. One row per (user_id, date, source).

| Column | Type | Notes |
|--------|------|-------|
| daily_id | UUID | PK (with date for partition) |
| user_id | UUID | FK → users ON DELETE CASCADE (C3 fix) |
| date | DATE | NOT NULL. **User's local calendar date** as reported by source. |
| source | TEXT | FK → data_sources, NOT NULL |
| resting_hr_bpm | SMALLINT | CHECK 20–300 |
| max_hr_bpm | SMALLINT | CHECK 20–300 |
| hrv_rmssd_ms | NUMERIC(6,2) | CHECK 1–300 |
| steps | INTEGER | CHECK 0–100000 |
| active_calories_kcal | SMALLINT | |
| total_calories_kcal | SMALLINT | |
| active_minutes | SMALLINT | CHECK 0–1440 |
| moderate_intensity_minutes | SMALLINT | |
| vigorous_intensity_minutes | SMALLINT | |
| distance_m | INTEGER | |
| floors_climbed | SMALLINT | |
| spo2_avg_pct | NUMERIC(4,1) | CHECK 70–100 |
| spo2_min_pct | NUMERIC(4,1) | |
| respiratory_rate_avg | NUMERIC(4,1) | CHECK 4–60 |
| stress_avg | SMALLINT | CHECK 0–100 |
| body_battery_start | SMALLINT | Garmin (0-100) |
| body_battery_end | SMALLINT | |
| readiness_score | SMALLINT | Oura/WHOOP (0-100) |
| recovery_score | SMALLINT | WHOOP (0-100) |
| skin_temp_deviation_c | NUMERIC(4,2) | Oura deviation from baseline |
| vo2_max_ml_kg_min | NUMERIC(4,1) | CHECK 10–100 |
| extended_metrics | JSONB | DEFAULT '{}' — non-core metrics without ALTER TABLE (E2 fix) |
| raw_data | JSONB | Source-specific full API response. Move to raw_s3_key for large responses. |
| raw_s3_key | TEXT | S3 key when raw_data has been offloaded to S3 (P1 migration path) |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Partition:** RANGE (date), yearly 2018–2028 + DEFAULT
**Unique:** (user_id, date, source)
**Indexes:**
- (user_id, date DESC)
- (user_id, source, date DESC)
- Covering: (user_id, date DESC) INCLUDE (resting_hr_bpm, hrv_rmssd_ms, steps, readiness_score, recovery_score) — for dashboard queries (P4 fix)

**Timezone note (EC3):** `date` represents the user's local calendar date as reported by the source device/API. This is NOT UTC midnight — a Garmin user in Tokyo records Jan 2 as "Jan 2" in their local timezone. When partitioning by date, rows are routed to the partition covering the device-reported local date.

#### `wearable_sleep`
Detailed sleep data. One row per (user_id, sleep_date, source).

| Column | Type | Notes |
|--------|------|-------|
| sleep_id | UUID | PK (with sleep_date) |
| user_id | UUID | FK → users ON DELETE CASCADE |
| sleep_date | DATE | NOT NULL. **Date sleep ended (morning of), in user's local timezone.** |
| source | TEXT | FK → data_sources, NOT NULL |
| sleep_start | TIMESTAMPTZ | |
| sleep_end | TIMESTAMPTZ | |
| total_sleep_minutes | SMALLINT | CHECK 0–1440 |
| rem_minutes | SMALLINT | CHECK 0–720 |
| deep_minutes | SMALLINT | |
| light_minutes | SMALLINT | |
| awake_minutes | SMALLINT | |
| sleep_latency_minutes | SMALLINT | CHECK 0–240 |
| sleep_efficiency_pct | NUMERIC(4,1) | CHECK 0–100 |
| sleep_score | SMALLINT | CHECK 0–100 |
| interruptions | SMALLINT | |
| avg_hr_bpm | SMALLINT | CHECK 20–200 |
| min_hr_bpm | SMALLINT | |
| avg_hrv_ms | NUMERIC(6,2) | |
| avg_respiratory_rate | NUMERIC(4,1) | |
| avg_spo2_pct | NUMERIC(4,1) | |
| avg_skin_temp_deviation_c | NUMERIC(4,2) | |
| hypnogram | JSONB | [{t: epoch_sec, stage: 'rem'/'deep'/'light'/'awake'}] |
| raw_data | JSONB | |
| raw_s3_key | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Partition:** RANGE (sleep_date), yearly 2018–2028 + DEFAULT
**Unique:** (user_id, sleep_date, source)
**Indexes:** (user_id, sleep_date DESC)

#### `wearable_activities`
Individual workouts and activities.

| Column | Type | Notes |
|--------|------|-------|
| activity_id | UUID | PK (with activity_date) |
| user_id | UUID | FK → users ON DELETE CASCADE |
| activity_date | DATE | NOT NULL. **User's local date of activity start.** |
| source | TEXT | FK → data_sources, NOT NULL |
| source_activity_id | TEXT | External ID for idempotent re-sync |
| activity_type | TEXT | FK → activity_types, NOT NULL |
| activity_name | TEXT | |
| start_time | TIMESTAMPTZ | |
| end_time | TIMESTAMPTZ | |
| duration_seconds | INTEGER | CHECK >= 0 |
| distance_m | NUMERIC(10,2) | |
| calories_kcal | SMALLINT | |
| avg_hr_bpm | SMALLINT | CHECK 20–300 |
| max_hr_bpm | SMALLINT | |
| hr_zone_1_seconds – hr_zone_5_seconds | INTEGER | |
| avg_pace_sec_per_km | NUMERIC(7,2) | |
| avg_speed_kmh | NUMERIC(5,2) | |
| elevation_gain_m | NUMERIC(7,2) | |
| avg_power_watts | SMALLINT | |
| normalized_power_watts | SMALLINT | |
| training_stress_score | NUMERIC(6,1) | |
| training_effect_aerobic | NUMERIC(3,1) | CHECK 0–5 |
| training_effect_anaerobic | NUMERIC(3,1) | |
| vo2_max_ml_kg_min | NUMERIC(4,1) | |
| notes | TEXT | |
| raw_data | JSONB | |
| raw_s3_key | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Partition:** RANGE (activity_date), yearly 2018–2028 + DEFAULT
**Unique dedup:** (user_id, source, source_activity_id) WHERE source_activity_id IS NOT NULL
**Indexes:** (user_id, activity_date DESC), (user_id, activity_type, activity_date DESC)

#### `wearable_daily_canonical` *(View — EC5)*
When a user has data from multiple sources on the same day, this view exposes one "best" row per (user_id, date) by applying a priority ordering. Priority: oura > whoop > garmin > apple_health > others. This resolves device-switching trend discontinuities and provides a single clean timeline for analysis.

```sql
-- View picks the highest-priority source row per (user, date)
CREATE OR REPLACE VIEW wearable_daily_canonical AS
SELECT DISTINCT ON (user_id, date) *
FROM wearable_daily
ORDER BY user_id, date, CASE source
    WHEN 'oura'         THEN 1
    WHEN 'whoop'        THEN 2
    WHEN 'garmin'       THEN 3
    WHEN 'apple_health' THEN 4
    ELSE 99
END;
```

Consider materializing this view and refreshing nightly for large datasets.

---

### 2.5 Lab Work

#### `biomarker_dictionary`
Canonical reference for all known biomarkers. Shared read-only across all users (no RLS).
**v2 change:** Aliases are stored as **lowercase** (B3 fix). A trigger enforces this on insert/update. Queries must lowercase input before matching: `WHERE aliases @> ARRAY[lower('Glucose')]`.

| Column | Type | Notes |
|--------|------|-------|
| biomarker_id | UUID | PK |
| canonical_name | TEXT | UNIQUE NOT NULL — slug: 'glucose', 'hdl_cholesterol' |
| display_name | TEXT | NOT NULL |
| category | biomarker_category ENUM | NOT NULL |
| subcategory | TEXT | "CBC", "CMP", "Thyroid Panel" |
| canonical_unit | TEXT | NOT NULL — all value_canonical use this unit |
| common_units | TEXT[] | All accepted input units |
| loinc_code | TEXT | LOINC interoperability code |
| description | TEXT | |
| aliases | TEXT[] | All synonyms — **always lowercase** |
| sex_specific_ranges | BOOLEAN | NOT NULL DEFAULT FALSE |
| optimal_low_male | NUMERIC(12,4) | |
| optimal_high_male | NUMERIC(12,4) | |
| optimal_low_female | NUMERIC(12,4) | |
| optimal_high_female | NUMERIC(12,4) | |
| optimal_low | NUMERIC(12,4) | Sex-neutral optimal |
| optimal_high | NUMERIC(12,4) | |
| normal_low | NUMERIC(12,4) | Standard population range |
| normal_high | NUMERIC(12,4) | |
| is_qualitative | BOOLEAN | NOT NULL DEFAULT FALSE |
| sort_order | INTEGER | Display ordering within category |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** GIN on `aliases` (use `@>` operator — see §6 Query Patterns), BTREE on `canonical_name`, `category`
**RLS:** None — shared reference table. vitalis_api can read but NOT write.
**Alias matching:** Always use `WHERE aliases @> ARRAY[lower(:input)]` for GIN index utilization (P6 fix).

#### `blood_panels`
Header for a lab visit / panel order.

| Column | Type | Notes |
|--------|------|-------|
| panel_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| lab_name | TEXT | |
| lab_provider | TEXT | |
| panel_name | TEXT | |
| collected_at | TIMESTAMPTZ | **Not NULL in practice — required for dedup** |
| reported_at | TIMESTAMPTZ | |
| fasting | BOOLEAN | |
| specimen_id | TEXT | |
| document_id | UUID | FK → documents ON DELETE SET NULL (C4 fix) |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, collected_at DESC)

#### `blood_markers`
Individual marker results. One row per biomarker per panel.
**v2 changes:** Added `collected_at` (P2 fix), added UNIQUE (panel_id, raw_name) (EC1 fix), added index for unmatched markers (EC7 fix).

| Column | Type | Notes |
|--------|------|-------|
| marker_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE (denorm for RLS) |
| panel_id | UUID | FK → blood_panels ON DELETE CASCADE |
| biomarker_id | UUID | FK → biomarker_dictionary (NULL if unmatched) |
| collected_at | TIMESTAMPTZ | **Denormalized from blood_panels.collected_at** for efficient trend queries (P2 fix) |
| raw_name | TEXT | NOT NULL — verbatim name from report |
| sub_panel | TEXT | "CBC", "CMP", "Cardio IQ" |
| value_numeric | NUMERIC(12,4) | NULL for qualitative |
| value_text | TEXT | Qualitative: "NEGATIVE", "POSITIVE" |
| unit | TEXT | As reported by lab |
| value_canonical | NUMERIC(12,4) | Converted to biomarker_dictionary.canonical_unit |
| ref_range_low | NUMERIC(12,4) | |
| ref_range_high | NUMERIC(12,4) | |
| ref_range_text | TEXT | Full text as printed |
| flag | TEXT | CHECK IN ('H','L','HH','LL','ABNORMAL','CRITICAL') |
| in_range | BOOLEAN | |
| optimal_low | NUMERIC(12,4) | Snapshot of dict optimal at ingestion |
| optimal_high | NUMERIC(12,4) | |
| lab_code | TEXT | Lab site code |
| parse_confidence | NUMERIC(3,2) | 0.00–1.00 if AI-parsed |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Unique:** (panel_id, raw_name) — prevents duplicate imports of same report (EC1 fix)
**Indexes:**
- (user_id, biomarker_id, collected_at DESC) — trend queries (P2 fix)
- (panel_id) — panel detail page
- (user_id, panel_id)
- (user_id, created_at DESC) WHERE biomarker_id IS NULL — unmatched markers queue (EC7 fix)

#### `biomarker_ranges` *(New in v2 — B1)*
Age- and sex-specific optimal and normal ranges. Overrides the dictionary-level ranges when an age/sex match exists.

| Column | Type | Notes |
|--------|------|-------|
| range_id | UUID | PK |
| biomarker_id | UUID | FK → biomarker_dictionary ON DELETE CASCADE |
| sex | TEXT | CHECK IN ('male','female') — NULL = universal |
| age_low | SMALLINT | Age range start (inclusive). NULL = any age |
| age_high | SMALLINT | Age range end (exclusive). NULL = no upper limit |
| optimal_low | NUMERIC(12,4) | |
| optimal_high | NUMERIC(12,4) | |
| normal_low | NUMERIC(12,4) | |
| normal_high | NUMERIC(12,4) | |
| source | TEXT | Clinical guideline source (e.g., "Endocrine Society 2020") |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** (biomarker_id, sex, age_low, age_high)
**Query pattern:** At display time, look up age/sex-specific range first; fall back to dictionary general ranges.

---

### 2.6 Body Composition (DEXA)

#### `dexa_scans`
Scan header — one row per scan session.
**v2 changes:** Added canonical metric columns (N1 fix). `document_id` FK added (C4 fix).

| Column | Type | Notes |
|--------|------|-------|
| scan_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| provider | TEXT | "DexaFit", "BodySpec", etc. |
| scan_date | DATE | NOT NULL. **User's local calendar date.** |
| age_at_scan | NUMERIC(4,1) | |
| height_in | NUMERIC(5,2) | Source-reported height in inches |
| height_cm | NUMERIC(5,2) | **Canonical metric** — always store both (N1 fix) |
| weight_lbs | NUMERIC(6,2) | Scale weight day of scan |
| weight_kg | NUMERIC(6,2) | **Canonical metric** |
| total_mass_lbs | NUMERIC(6,2) | DEXA total mass |
| total_mass_kg | NUMERIC(6,2) | Canonical |
| total_fat_lbs | NUMERIC(6,2) | |
| total_fat_kg | NUMERIC(6,2) | Canonical |
| total_lean_lbs | NUMERIC(6,2) | |
| total_lean_kg | NUMERIC(6,2) | Canonical |
| total_bmc_lbs | NUMERIC(6,2) | Bone Mineral Content |
| total_bmc_kg | NUMERIC(6,2) | Canonical |
| total_body_fat_pct | NUMERIC(4,1) | CHECK 1–80 |
| visceral_fat_lbs | NUMERIC(6,3) | |
| visceral_fat_kg | NUMERIC(6,3) | Canonical |
| visceral_fat_in3 | NUMERIC(7,2) | Volume in cubic inches |
| visceral_fat_cm3 | NUMERIC(7,2) | Canonical |
| android_gynoid_ratio | NUMERIC(4,2) | |
| document_id | UUID | FK → documents ON DELETE SET NULL (C4 fix) |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, scan_date DESC)

#### `dexa_regions`
Body fat % and composition by anatomical region.
**v2 change:** Consistency trigger added — user_id must match dexa_scans.user_id (N4 fix).

| Column | Type | Notes |
|--------|------|-------|
| region_id | UUID | PK |
| scan_id | UUID | FK → dexa_scans ON DELETE CASCADE |
| user_id | UUID | FK → users ON DELETE CASCADE (denorm for RLS) |
| region | dexa_region ENUM | total, arms, arm_right, etc. |
| body_fat_pct | NUMERIC(4,1) | CHECK 0–100 |
| fat_lbs | NUMERIC(6,2) | |
| lean_lbs | NUMERIC(6,2) | |
| bmc_lbs | NUMERIC(5,3) | |
| total_mass_lbs | NUMERIC(6,2) | |

**Unique:** (scan_id, region)
**Consistency:** BEFORE INSERT OR UPDATE trigger enforces NEW.user_id = dexa_scans.user_id WHERE scan_id = NEW.scan_id

#### `dexa_bone_density`
BMD T-scores and Z-scores by skeletal region.
**v2 change:** Consistency trigger added (N4 fix).

| Column | Type | Notes |
|--------|------|-------|
| density_id | UUID | PK |
| scan_id | UUID | FK → dexa_scans ON DELETE CASCADE |
| user_id | UUID | FK → users ON DELETE CASCADE (denorm for RLS) |
| region | bone_density_region ENUM | |
| bmd_g_cm2 | NUMERIC(6,3) | CHECK > 0 |
| t_score | NUMERIC(4,1) | vs. 30-35yr peak |
| z_score | NUMERIC(4,1) | vs. age-matched |

**Unique:** (scan_id, region)

---

### 2.7 Epigenetics

#### `epigenetic_tests`
Header for one test kit.
**v2 change:** `document_id` FK added (C4 fix).

| Column | Type | Notes |
|--------|------|-------|
| test_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| provider | TEXT | "Blueprint Biomarkers", "TruDiagnostic" |
| kit_id | TEXT | External kit identifier |
| collected_at | DATE | **User's local date.** |
| reported_at | DATE | |
| chronological_age | NUMERIC(4,1) | CHECK 0–120 |
| biological_age | NUMERIC(4,1) | CHECK 0–120 |
| pace_score | NUMERIC(4,2) | CHECK 0.2–3.0 |
| pace_percentile | NUMERIC(5,2) | CHECK 0–100 |
| telomere_length | NUMERIC(6,3) | kb, if measured |
| methylation_clock | TEXT | 'dunedinpace', 'horvath', 'grimage' |
| document_id | UUID | FK → documents ON DELETE SET NULL (C4 fix) |
| raw_data | JSONB | Full provider response |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, collected_at DESC)

#### `epigenetic_organ_ages`
Per-organ system biological age. ~12 rows per test.
**v2 changes (N2 fix):** Removed `chronological_age` and `delta_years` — these are now computed via JOIN to the parent `epigenetic_tests` row to prevent stale denormalization. Use `epigenetic_organ_ages_enriched` view for those columns.

| Column | Type | Notes |
|--------|------|-------|
| organ_age_id | UUID | PK |
| test_id | UUID | FK → epigenetic_tests ON DELETE CASCADE |
| user_id | UUID | FK → users ON DELETE CASCADE (denorm for RLS) |
| organ_system | organ_system ENUM | lung, metabolic, heart, etc. |
| biological_age | NUMERIC(4,1) | |
| direction | TEXT | 'younger', 'older', 'same' |

**Unique:** (test_id, organ_system)

**`epigenetic_organ_ages_enriched` VIEW** (replaces raw table for most queries):
```sql
SELECT oa.*, et.chronological_age,
       ROUND(oa.biological_age - et.chronological_age, 1) AS delta_years
FROM epigenetic_organ_ages oa
JOIN epigenetic_tests et ON oa.test_id = et.test_id;
```

---

### 2.8 Fitness (Lifting)

#### `exercise_dictionary`
Canonical exercise catalog. Shared, no RLS.

| Column | Type | Notes |
|--------|------|-------|
| exercise_id | UUID | PK |
| canonical_name | TEXT | UNIQUE NOT NULL |
| display_name | TEXT | NOT NULL |
| aliases | TEXT[] | For fuzzy CSV import matching |
| primary_muscle | TEXT | |
| secondary_muscles | TEXT[] | |
| equipment | TEXT | 'barbell', 'dumbbell', 'machine', 'bodyweight', 'cable' |
| category | TEXT | 'compound', 'isolation', 'cardio', 'mobility' |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**RLS:** None — shared reference. vitalis_api can read but NOT write.

#### `lifting_sessions`

| Column | Type | Notes |
|--------|------|-------|
| session_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| session_date | DATE | NOT NULL. **User's local calendar date.** |
| source | TEXT | FK → data_sources, DEFAULT 'manual' |
| source_session_id | TEXT | Dedup key |
| name | TEXT | "Upper A", "Push Day" |
| duration_seconds | INTEGER | CHECK 0–86400 |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, session_date DESC)

#### `lifting_sets`
**v2 changes:** Fixed `reps` CHECK to minimum 1 (EC8 fix). Added `weight_kg` canonical column (N1 fix). Consistency trigger added (N4 fix).

| Column | Type | Notes |
|--------|------|-------|
| set_id | UUID | PK |
| session_id | UUID | FK → lifting_sessions ON DELETE CASCADE |
| user_id | UUID | FK → users ON DELETE CASCADE (denorm for RLS) |
| exercise_id | UUID | FK → exercise_dictionary |
| raw_exercise_name | TEXT | Verbatim if not matched |
| exercise_order | SMALLINT | NOT NULL DEFAULT 1 |
| set_number | SMALLINT | NOT NULL DEFAULT 1 |
| weight_lbs | NUMERIC(6,2) | CHECK 0–2000 |
| weight_kg | NUMERIC(6,2) | **Canonical metric** (N1 fix) |
| reps | SMALLINT | CHECK **1**–999 (EC8 fix — 0 reps is never valid) |
| rpe | NUMERIC(3,1) | CHECK 0–10 |
| is_warmup | BOOLEAN | NOT NULL DEFAULT FALSE |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Consistency:** BEFORE INSERT OR UPDATE trigger enforces NEW.user_id = lifting_sessions.user_id

---

### 2.9 Manual Tracking

#### `measurements`
Generic scalar body metrics.

| Column | Type | Notes |
|--------|------|-------|
| measurement_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| metric | measurement_metric ENUM | NOT NULL |
| value | NUMERIC(10,3) | NOT NULL |
| unit | TEXT | NOT NULL |
| measured_at | TIMESTAMPTZ | NOT NULL. **Local time of measurement.** |
| source | TEXT | FK → data_sources, DEFAULT 'manual' |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Indexes:** (user_id, metric, measured_at DESC)

#### `custom_metrics`

| Column | Type | Notes |
|--------|------|-------|
| metric_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| name | TEXT | NOT NULL |
| unit | TEXT | |
| data_type | TEXT | 'numeric', 'boolean', 'text', 'scale_1_5' |
| min_value | NUMERIC | |
| max_value | NUMERIC | |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Unique:** (user_id, name)

#### `custom_metric_entries`
**v2 change:** Consistency trigger added (N4 fix).

| Column | Type | Notes |
|--------|------|-------|
| entry_id | UUID | PK |
| metric_id | UUID | FK → custom_metrics ON DELETE CASCADE |
| user_id | UUID | FK → users ON DELETE CASCADE (denorm for RLS) |
| value_numeric | NUMERIC | |
| value_text | TEXT | |
| measured_at | TIMESTAMPTZ | NOT NULL |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** (user_id, metric_id, measured_at DESC)

#### `supplements`

| Column | Type | Notes |
|--------|------|-------|
| supplement_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| name | TEXT | NOT NULL |
| brand | TEXT | |
| dose_amount | NUMERIC(8,3) | CHECK > 0 |
| dose_unit | TEXT | 'mg', 'g', 'IU', 'mcg', 'ml' |
| frequency | TEXT | 'daily', '2x_daily', 'weekly', 'as_needed' |
| timing | TEXT | 'morning', 'evening', 'with_meal', 'pre_workout' |
| started_at | DATE | |
| ended_at | DATE | NULL = currently taking |
| purpose | TEXT | |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

#### `supplement_logs`
**v2 change:** Consistency trigger added (N4 fix).

| Column | Type | Notes |
|--------|------|-------|
| log_id | UUID | PK |
| supplement_id | UUID | FK → supplements ON DELETE CASCADE |
| user_id | UUID | FK → users ON DELETE CASCADE (denorm for RLS) |
| taken_at | TIMESTAMPTZ | NOT NULL |
| dose_amount | NUMERIC(8,3) | May differ from default dose |
| dose_unit | TEXT | |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** (user_id, taken_at DESC), (supplement_id, taken_at)

#### `nutrition_logs`
**v2 change:** Added `updated_at` column + trigger (MT6 fix).

| Column | Type | Notes |
|--------|------|-------|
| nutrition_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| log_date | DATE | NOT NULL. **User's local calendar date.** |
| meal_type | TEXT | CHECK IN ('breakfast','lunch','dinner','snack','fast','other') |
| calories_kcal | SMALLINT | CHECK >= 0 |
| protein_g | NUMERIC(6,2) | |
| carbs_g | NUMERIC(6,2) | |
| fat_g | NUMERIC(6,2) | |
| fiber_g | NUMERIC(6,2) | |
| source | TEXT | FK → data_sources, DEFAULT 'manual' |
| raw_data | JSONB | Full source data |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| **updated_at** | TIMESTAMPTZ | NOT NULL DEFAULT NOW() (MT6 fix) |
| deleted_at | TIMESTAMPTZ | |

#### `mood_journal`

| Column | Type | Notes |
|--------|------|-------|
| journal_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| journal_date | DATE | NOT NULL. **User's local calendar date.** |
| mood_score | SMALLINT | CHECK 1–5 |
| energy_score | SMALLINT | CHECK 1–5 |
| stress_score | SMALLINT | CHECK 1–5 |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

**Unique:** (user_id, journal_date)

#### `menstrual_cycles`

| Column | Type | Notes |
|--------|------|-------|
| cycle_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| cycle_date | DATE | NOT NULL. **User's local calendar date.** |
| phase | menstrual_phase ENUM | |
| flow_intensity | SMALLINT | CHECK 0–4 |
| symptoms | TEXT[] | ['cramps', 'headache', 'bloating'] |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Unique:** (user_id, cycle_date)

#### `doctor_visits`

| Column | Type | Notes |
|--------|------|-------|
| visit_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| visit_date | DATE | NOT NULL. **User's local calendar date.** |
| provider_name | TEXT | |
| specialty | TEXT | |
| notes | TEXT | |
| follow_up_date | DATE | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

#### `doctor_visit_panels`
Link table: visits to blood panels.
**v2 change (N3 fix):** Added `user_id` column + RLS policy. Previously this table had no user_id and was fully exposed to all authenticated users.

| Column | Type |
|--------|------|
| visit_id | UUID FK → doctor_visits ON DELETE CASCADE |
| panel_id | UUID FK → blood_panels ON DELETE CASCADE |
| user_id | UUID FK → users ON DELETE CASCADE |

**PK:** (visit_id, panel_id)

#### `photos`

| Column | Type | Notes |
|--------|------|-------|
| photo_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| photo_date | DATE | NOT NULL. **User's local calendar date.** |
| photo_type | TEXT | CHECK IN ('front','back','left','right','other') |
| s3_key | TEXT | NOT NULL — internal S3 path, never exposed as public URL |
| s3_thumbnail_key | TEXT | |
| file_size_bytes | INTEGER | CHECK > 0 |
| linked_scan_id | UUID | FK → dexa_scans |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | |

#### `documents`
Source PDFs uploaded by users.
**v2 changes (G1 fix, MT7 fix):** Removed misleading "never hard-deleted" claim — documents ARE deleted on GDPR deletion. Added `file_hash` column for duplicate detection.

| Column | Type | Notes |
|--------|------|-------|
| document_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| document_type | document_type ENUM | blood_work, dexa, epigenetics, imaging, doctor_note, other |
| provider_name | TEXT | |
| original_filename | TEXT | |
| s3_key | TEXT | NOT NULL — internal S3 path, not a public URL |
| file_hash | TEXT | **SHA-256 of file content (hex)** — for duplicate detection (MT7 fix) |
| file_size_bytes | INTEGER | CHECK > 0 |
| mime_type | TEXT | DEFAULT 'application/pdf' |
| parse_status | parse_status ENUM | DEFAULT 'pending' |
| parse_confidence | NUMERIC(3,2) | 0.00–1.00 |
| parse_result | JSONB | Raw LLM extraction |
| parsed_at | TIMESTAMPTZ | |
| confirmed_at | TIMESTAMPTZ | |
| confirmed_by | UUID | FK → users |
| linked_record_id | UUID | UUID of resulting panel/scan/test |
| linked_record_type | TEXT | 'blood_panel', 'dexa_scan', 'epigenetic_test' |
| error_message | TEXT | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| deleted_at | TIMESTAMPTZ | **Documents are hard-deleted on GDPR deletion.** |

**Unique:** (user_id, file_hash) WHERE file_hash IS NOT NULL — prevents duplicate uploads (MT7 fix)
**Indexes:** (user_id, created_at DESC), (parse_status) WHERE parse_status = 'pending'

---

### 2.10 Goals & Insights

#### `goals`

| Column | Type | Notes |
|--------|------|-------|
| goal_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| metric_type | TEXT | CHECK IN ('blood_marker','measurement','wearable','custom') |
| biomarker_id | UUID | FK → biomarker_dictionary |
| metric_name | TEXT | NOT NULL |
| target_value | NUMERIC(12,4) | |
| target_unit | TEXT | |
| direction | goal_direction ENUM | minimize / maximize / target |
| alert_threshold_low | NUMERIC(12,4) | |
| alert_threshold_high | NUMERIC(12,4) | |
| alert_enabled | BOOLEAN | DEFAULT TRUE |
| notes | TEXT | |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

#### `goal_alerts`
**v2 change:** Consistency trigger added (N4 fix).

| Column | Type | Notes |
|--------|------|-------|
| alert_id | UUID | PK |
| goal_id | UUID | FK → goals ON DELETE CASCADE |
| user_id | UUID | FK → users ON DELETE CASCADE (denorm for RLS) |
| triggered_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| trigger_value | NUMERIC(12,4) | |
| message | TEXT | |
| acknowledged_at | TIMESTAMPTZ | |

#### `insights`

| Column | Type | Notes |
|--------|------|-------|
| insight_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| insight_type | insight_type ENUM | correlation, anomaly, trend, goal_progress, recommendation |
| title | TEXT | NOT NULL |
| body | TEXT | NOT NULL |
| metric_a | TEXT | Primary metric |
| metric_b | TEXT | Secondary metric |
| correlation_r | NUMERIC(4,3) | Pearson r |
| p_value | NUMERIC(8,6) | |
| data_points | INTEGER | n used |
| valid_from | DATE | |
| valid_until | DATE | Cache expiry |
| is_dismissed | BOOLEAN | DEFAULT FALSE |
| dismissed_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes:** (user_id, created_at DESC) WHERE is_dismissed = FALSE

#### `notifications` *(New in v2 — MT2)*

| Column | Type | Notes |
|--------|------|-------|
| notification_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| notification_type | TEXT | NOT NULL — 'sync_success', 'sync_failure', 'parse_complete', 'goal_alert', 'subscription', 'system' |
| title | TEXT | NOT NULL |
| body | TEXT | |
| payload | JSONB | DEFAULT '{}' — extra data (job_id, goal_id, etc.) |
| is_read | BOOLEAN | NOT NULL DEFAULT FALSE |
| read_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| expires_at | TIMESTAMPTZ | Auto-hide after expiry |

**Indexes:** (user_id, created_at DESC) WHERE is_read = FALSE

---

### 2.11 System & Operations

#### `ingestion_jobs`
**v2 change (P3 fix):** Partitioned by RANGE(queued_at) quarterly for easy pruning of completed jobs older than 90 days.

| Column | Type | Notes |
|--------|------|-------|
| job_id | UUID | NOT NULL — part of composite PK |
| user_id | UUID | FK → users ON DELETE SET NULL |
| source | TEXT | FK → data_sources |
| job_type | job_type ENUM | daily_sync, backfill, document_parse, etc. |
| status | job_status ENUM | DEFAULT 'queued' |
| priority | SMALLINT | DEFAULT 5, CHECK 1–10 |
| payload | JSONB | Input params. **Scrubbed on GDPR deletion (S3 fix)** |
| result | JSONB | Output stats. Scrubbed on GDPR deletion. |
| error_message | TEXT | |
| attempts | SMALLINT | DEFAULT 0 |
| max_attempts | SMALLINT | DEFAULT 3 |
| queued_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() — partition key |
| started_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |
| next_retry_at | TIMESTAMPTZ | |

**Partition:** RANGE (queued_at), quarterly 2024+
**Primary Key:** (job_id, queued_at)
**Indexes:** (status, priority, next_retry_at) WHERE status IN ('queued','failed'), (user_id, job_type, queued_at DESC)
**Worker RLS:** vitalis_worker role has full access via separate policy (USING TRUE).

#### `audit_log`
Immutable record of all data mutations. Never hard-deleted. PII anonymized on GDPR deletion.
**v2 change:** Triggers are now attached to ALL user-data tables (C1 fix).

| Column | Type | Notes |
|--------|------|-------|
| audit_id | UUID | NOT NULL |
| user_id | UUID | Affected user. Set to NULL on GDPR deletion. |
| action_by | UUID | User performing action |
| table_name | TEXT | NOT NULL — logical table name (strips partition suffix) |
| record_id | UUID | NOT NULL — PK of affected row |
| action | audit_action ENUM | INSERT / UPDATE / DELETE / SOFT_DELETE / EXPORT / LOGIN / LOGOUT |
| old_values | JSONB | Previous state. PII stripped on GDPR deletion. |
| new_values | JSONB | New state. |
| ip_address | INET | |
| user_agent | TEXT | |
| request_id | UUID | Trace ID from API |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Partition:** RANGE (created_at), quarterly
**Primary Key:** (audit_id, created_at)
**Indexes:** (user_id, created_at DESC), (table_name, record_id), (action_by, created_at DESC)
**Audit skip:** Set `SET LOCAL app.audit_skip = '1'` for bulk ingestion operations to bypass write amplification (P7 partial fix).

#### `deletion_requests`
GDPR/CCPA deletion tracking.
**v2 changes (C5 fix):** `user_id` is now NULLABLE with ON DELETE SET NULL (allows user row deletion). Added `user_email_snapshot` for compliance records.

| Column | Type | Notes |
|--------|------|-------|
| request_id | UUID | PK |
| user_id | UUID | FK → users **ON DELETE SET NULL** (C5 fix) — nullable |
| user_email_snapshot | TEXT | Captured at request time for compliance record |
| requested_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| grace_period_ends_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() + 30 days |
| status | TEXT | 'pending', 'processing', 'completed', 'canceled' |
| completed_at | TIMESTAMPTZ | |
| tables_deleted | TEXT[] | Audit of what was deleted |

#### `data_export_requests`

| Column | Type | Notes |
|--------|------|-------|
| export_id | UUID | PK |
| user_id | UUID | FK → users ON DELETE CASCADE |
| requested_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| status | TEXT | 'queued', 'processing', 'ready', 'downloaded', 'expired' |
| format | TEXT | 'json', 'csv' |
| s3_key | TEXT | Temporary signed URL location |
| expires_at | TIMESTAMPTZ | 7-day expiry |
| completed_at | TIMESTAMPTZ | |
| file_size_bytes | BIGINT | |

---

## 3. Row-Level Security Strategy

### RLS Expression (C6 fix)
All policies use `NULLIF` to safely handle missing session variables:

```sql
-- WRONG (v1 — crashes when app.current_user_id is not set):
USING (user_id = current_setting('app.current_user_id', TRUE)::uuid)

-- CORRECT (v2 — returns no rows when not set):
USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
```

When `app.current_user_id` is not set, `NULLIF` returns NULL. `user_id = NULL` evaluates to false for all rows, returning an empty result. This is the safe default — background workers, migration scripts, and monitoring queries do not crash.

### Session Variables
Set at the start of every API connection:

```sql
-- Required for user data access:
SET LOCAL app.current_user_id = '<user_uuid>';

-- Required for family plan cross-user read access:
SET LOCAL app.current_account_id = '<account_uuid>';

-- Optional — skip audit logging for bulk operations:
SET LOCAL app.audit_skip = '1';

-- Optional — trace ID for audit log:
SET LOCAL app.request_id = '<request_uuid>';
```

### Policy Types

Every user-data table has two RLS policies:

1. **`user_isolation`** — Full CRUD access to own rows:
   ```sql
   CREATE POLICY user_isolation ON <table>
       USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
       WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
   ```

2. **`family_read`** — Read access for family account members (M1 fix):
   ```sql
   CREATE POLICY family_read ON <table> FOR SELECT TO vitalis_api
       USING (user_id IN (
           SELECT u.user_id FROM users u
           WHERE u.account_id = NULLIF(current_setting('app.current_account_id', TRUE), '')::uuid
             AND u.deleted_at IS NULL
       ));
   ```

3. **`worker_bypass`** on `ingestion_jobs` — Workers need cross-user job access (S1 fix):
   ```sql
   CREATE POLICY worker_bypass ON ingestion_jobs FOR ALL TO vitalis_worker
       USING (TRUE) WITH CHECK (TRUE);
   ```

### Accounts RLS (C7 fix)
```sql
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY account_isolation ON accounts
    USING (account_id IN (
        SELECT account_id FROM users
        WHERE user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid
          AND deleted_at IS NULL
    ))
    WITH CHECK (account_id IN (
        SELECT account_id FROM users
        WHERE user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid
          AND deleted_at IS NULL
    ));
```

### Roles (S2 fix)

| Role | Permissions | Notes |
|------|-------------|-------|
| `vitalis_api` | SELECT/INSERT/UPDATE/DELETE on user tables; SELECT on dictionaries | Subject to RLS |
| `vitalis_worker` | Same as api + BYPASS on ingestion_jobs (separate policy) | For sync workers |
| `vitalis_admin` | BYPASSRLS + all permissions | Emergency only — all access is audited |
| `vitalis_readonly` | SELECT only | Analytics replica |

**Dictionary protection (M3 fix):**
```sql
REVOKE INSERT, UPDATE, DELETE ON biomarker_dictionary FROM vitalis_api;
REVOKE INSERT, UPDATE, DELETE ON exercise_dictionary FROM vitalis_api;
```

### Tables with RLS Enabled
All tables except `biomarker_dictionary`, `exercise_dictionary`, `data_sources`, `activity_types`, `schema_info`.

---

## 4. Audit Logging (C1 fix)

### Fixed `audit_mutation()` Function
The v1 function had a critical bug: `record_id` was never correctly populated. The v2 function uses `TG_ARGV[0]` to receive the PK column name per table:

```sql
CREATE OR REPLACE FUNCTION audit_mutation()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_record      JSONB;
    v_record_id   UUID;
    v_user_id     UUID;
    v_table_name  TEXT;
    v_pk_col      TEXT;
BEGIN
    -- Skip audit for bulk operations (e.g., wearable backfills)
    IF current_setting('app.audit_skip', TRUE) = '1' THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END IF;

    -- TG_ARGV[0] = PK column name (required)
    -- TG_ARGV[1] = logical table name (optional, for partitioned tables)
    v_pk_col     := COALESCE(TG_ARGV[0], 'id');
    v_table_name := COALESCE(
        NULLIF(TG_ARGV[1], ''),
        regexp_replace(TG_TABLE_NAME, '_\d{4}(_q[1-4])?$', '')
    );

    IF TG_OP = 'DELETE' THEN
        v_record := row_to_json(OLD)::jsonb;
    ELSE
        v_record := row_to_json(NEW)::jsonb;
    END IF;

    v_record_id := (v_record ->> v_pk_col)::uuid;
    v_user_id   := (v_record ->> 'user_id')::uuid;

    CASE TG_OP
    WHEN 'INSERT' THEN
        INSERT INTO audit_log (user_id, action_by, table_name, record_id, action, new_values, request_id)
        VALUES (v_user_id,
                NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid,
                v_table_name, v_record_id, 'INSERT',
                v_record,
                NULLIF(current_setting('app.request_id', TRUE), '')::uuid);
        RETURN NEW;
    WHEN 'UPDATE' THEN
        INSERT INTO audit_log (user_id, action_by, table_name, record_id, action, old_values, new_values, request_id)
        VALUES (v_user_id,
                NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid,
                v_table_name, v_record_id, 'UPDATE',
                row_to_json(OLD)::jsonb, v_record,
                NULLIF(current_setting('app.request_id', TRUE), '')::uuid);
        RETURN NEW;
    WHEN 'DELETE' THEN
        INSERT INTO audit_log (user_id, action_by, table_name, record_id, action, old_values, request_id)
        VALUES (v_user_id,
                NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid,
                v_table_name, v_record_id, 'DELETE',
                v_record,
                NULLIF(current_setting('app.request_id', TRUE), '')::uuid);
        RETURN OLD;
    END CASE;
END;
$$;
```

### Trigger Attachment (C1 fix)
Every user-data table gets an audit trigger. Example:
```sql
CREATE TRIGGER audit_blood_panels
    AFTER INSERT OR UPDATE OR DELETE ON blood_panels
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('panel_id');

-- Partitioned tables pass logical name as TG_ARGV[1]:
CREATE TRIGGER audit_wearable_daily
    AFTER INSERT OR UPDATE OR DELETE ON wearable_daily
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('daily_id', 'wearable_daily');
```

See `schema.sql` Section 13 for the complete list of trigger attachments.

### High-Volume Tables: Bulk Ingestion Skip
For performance during backfills, set `app.audit_skip = '1'` to bypass audit logging:
```python
# In the ingestion worker:
await conn.execute("SET LOCAL app.audit_skip = '1'")
await conn.execute("INSERT INTO wearable_daily ...") # No audit written
```

This addresses the P7 write amplification concern at the application level without disabling auditing for interactive user operations.

---

## 5. Data Consistency: Parent-Child user_id (N4 fix)

Tables with denormalized `user_id` (for RLS performance) now have BEFORE INSERT/UPDATE triggers enforcing that the child's `user_id` matches the parent's `user_id`. This prevents data corruption where a bug inserts a region with user_id=A into a scan owned by user_id=B.

```sql
CREATE OR REPLACE FUNCTION enforce_user_id_consistency()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE parent_user UUID;
BEGIN
    EXECUTE format('SELECT user_id FROM %I WHERE %I = $1', TG_ARGV[0], TG_ARGV[2])
        USING (row_to_json(NEW) ->> TG_ARGV[1])::uuid
        INTO parent_user;
    IF parent_user IS DISTINCT FROM NEW.user_id THEN
        RAISE EXCEPTION 'user_id mismatch on %: child=% parent=%',
            TG_TABLE_NAME, NEW.user_id, parent_user;
    END IF;
    RETURN NEW;
END;
$$;
```

Applied to: `dexa_regions`, `dexa_bone_density`, `epigenetic_organ_ages`, `lifting_sets`, `supplement_logs`, `custom_metric_entries`, `goal_alerts`.

---

## 6. Migration Strategy (Alembic)

### Configuration
```
alembic/
  env.py           # Connects to DB, sets search path
  versions/        # Migration scripts
alembic.ini        # Points to DATABASE_URL env var
```

### Conventions
- Every schema change = one Alembic migration file
- `upgrade()` is idempotent where possible (IF NOT EXISTS)
- `downgrade()` always implemented
- No raw `ALTER TABLE` in production — always via migration
- Data migrations in separate files from schema migrations
- Lock timeout: `SET lock_timeout = '5s'` for standard DDL; use `pg_repack` for large table migrations (E4)
- New columns: Add with `DEFAULT` value (PG 14+) for instant ADD COLUMN on large tables

### ENUM Evolution (E1)
The three most volatile classifications (`data_source`, `activity_type`) are **lookup tables**, not ENUMs. Adding a new wearable adapter requires only:
```sql
INSERT INTO data_sources (source_id, display_name, category) VALUES ('levels', 'Levels CGM', 'wearable');
```

For remaining ENUMs, adding new values requires `ALTER TYPE ... ADD VALUE` which is safe in PG 15+ but cannot be rolled back. Plan additions carefully.

### Schema Version
```sql
SELECT value FROM schema_info WHERE key = 'version';
```

---

## 7. Partition Management

### Wearable Table Partitions
Yearly partitions exist from **2018 through 2028**, plus a DEFAULT partition for out-of-range data.

```python
# Automated partition management — run in December each year
def create_yearly_partitions(year: int):
    tables = ['wearable_daily', 'wearable_sleep', 'wearable_activities']
    for table in tables:
        execute(f"""
            CREATE TABLE IF NOT EXISTS {table}_{year}
            PARTITION OF {table}
            FOR VALUES FROM ('{year}-01-01') TO ('{year+1}-01-01')
        """)
```

### Ingestion Jobs Partitions (P3 fix)
Quarterly partitions, pruned after 90 days for completed/dead_letter jobs:
```sql
-- Run monthly to clean up old completed jobs:
DELETE FROM ingestion_jobs
WHERE status IN ('completed', 'dead_letter')
  AND completed_at < NOW() - INTERVAL '90 days';
```

### Audit Log Partitions
Quarterly partitions, never pruned. PII anonymized on GDPR deletion.

---

## 8. Backup Strategy

| Type | Frequency | Retention | Storage |
|------|-----------|-----------|---------|
| WAL archiving (PITR) | Continuous | 7 days | S3 |
| Daily logical dump | 02:00 UTC | 30 days | S3 |
| Weekly pg_dump | Sunday 03:00 | 12 weeks | S3 (separate bucket) |
| Monthly snapshot | 1st of month | 12 months | S3 Glacier |

**RTO:** < 1 hour | **RPO:** < 5 minutes

---

## 9. Data Validation Rules

| Entity | Rule |
|--------|------|
| `blood_markers.value_numeric` | Finite float; reject Inf/NaN |
| `blood_markers.unit` | Must be in `biomarker_dictionary.common_units` |
| `wearable_daily.resting_hr_bpm` | 20–300 (DB constraint) |
| `wearable_daily.hrv_rmssd_ms` | 1–300 |
| `wearable_daily.spo2_avg_pct` | 70–100 |
| `wearable_daily.steps` | 0–100000 |
| `measurements.value` (weight) | 20–1000 lbs |
| `mood_journal.*_score` | 1–5 (DB constraint) |
| `lifting_sets.weight_lbs` | 0–2000 |
| `lifting_sets.reps` | **1**–999 (EC8 fix) |
| `dexa_regions.body_fat_pct` | 0–100 |
| `epigenetic_tests.pace_score` | 0.2–3.0 |
| `users.email` | Valid email format, lowercase normalized |
| `users.date_of_birth` | Past date, age 13–150 |
| `biomarker_dictionary.aliases` | **Always lowercase** (B3 fix) |

### Duplicate Detection
- Wearable activities: `(user_id, source, source_activity_id)` where source_activity_id IS NOT NULL
- Wearable daily/sleep: `(user_id, date, source)` unique constraint
- Blood markers: `(panel_id, raw_name)` unique constraint (EC1 fix) — same raw name cannot appear twice in same panel
- Documents: `(user_id, file_hash)` unique constraint (MT7 fix) — same PDF cannot be uploaded twice

---

## 10. Canonical Biomarker Dictionary

### Alias Matching (B3 fix)
All aliases are stored **lowercase**. The application must lowercase input before matching:
```sql
-- CORRECT — uses GIN index:
SELECT * FROM biomarker_dictionary WHERE aliases @> ARRAY[lower('Glucose')];

-- WRONG — does NOT use GIN index:
SELECT * FROM biomarker_dictionary WHERE 'Glucose' = ANY(aliases);
```

### Age-Specific Ranges (B1 fix)
The `biomarker_ranges` table provides sex+age-specific optimal ranges. Lookup priority at display time:
1. Match `biomarker_ranges` row for user's sex + age bracket
2. Fall back to `biomarker_dictionary.optimal_low/optimal_high` (sex-specific if available)
3. Fall back to `biomarker_dictionary.normal_low/normal_high`

### v2 Additions to Seed Data (B2 fix)
Added 13 commonly-ordered markers not in v1:
- **vitamin_b12** (Vitamin B12, Serum)
- **folate_serum** (Folate, Serum)
- **igf_1** (IGF-1 / Somatomedin-C — critical for longevity tracking)
- **cystatin_c** (Cystatin C — better kidney function marker than creatinine alone)
- **fibrinogen** (Fibrinogen — cardiovascular risk)
- **selenium** (Selenium)
- **copper** (Copper, Serum)
- **vitamin_b6** (Vitamin B6 / Pyridoxal-5'-Phosphate)
- **omega3_index** (Omega-3 Index — EPA+DHA as % of total RBC fatty acids)
- **apoa1** (ApoA-I — HDL particle marker)
- **direct_ldl** (LDL Cholesterol, Direct — measured, not calculated)
- **vldl** (VLDL Cholesterol)
- **dht** (Dihydrotestosterone)

---

## 11. GDPR/CCPA Deletion Strategy

### Deletion Flow
```
User requests deletion
    → deletion_request created (status=pending, user_email_snapshot captured)
    → user_id stored in request (C5 fix: will be SET NULL after deletion)
    → Confirmation email sent (30-day grace period starts)
    → User can cancel within 30 days

After 30 days:
    → deletion_job runs
    → All user data hard-deleted (CASCADE from users row handles most tables)
    → Explicit DELETEs on partitioned wearable tables (user_id FK cascade works in PG15)
    → S3 objects deleted (PDFs, photos, exports)
    → audit_log: user_id set to NULL, old_values/new_values stripped of PII
    → ingestion_jobs: payload and result JSONB scrubbed (S3 fix)
    → deletion_request.status = 'completed'; user_id → NULL (SET NULL FK)
    → Stripe customer deleted
```

### Documents Deletion (G1 fix)
Documents **ARE deleted** on GDPR deletion. The v1 schema had a contradiction claiming documents are "never hard-deleted" while also listing them in the deletion flow. User consent withdrawal supersedes archival preferences. If legal hold is required, that is a separate exception flow outside the normal GDPR path.

### Consent Tracking (G2 fix)
The `user_consents` table tracks opt-in consent for: benchmarks, ai_coaching, doctor_sharing, marketing, analytics. Revocation is tracked with `revoked_at` (not a DELETE) to maintain consent history for compliance.

---

## 12. Changelog: v1.0 → v2.0

| Issue | Fix Applied |
|-------|-------------|
| C1: Broken audit trigger, never attached | Fixed `audit_mutation()` with TG_ARGV[0]; attached to all 38 user-data tables |
| C2: RLS missing WITH CHECK — writes unprotected | Added WITH CHECK to every RLS policy |
| C3: Partitioned tables missing FK to users | Added REFERENCES users(user_id) ON DELETE CASCADE to all wearable tables |
| C4: Missing document_id FKs | ALTER TABLE deferred FKs on blood_panels, dexa_scans, epigenetic_tests |
| C5: deletion_requests FK blocks user deletion | user_id nullable, ON DELETE SET NULL, added user_email_snapshot |
| C6: current_setting() UUID crash on empty string | NULLIF wrapper on all RLS expressions |
| C7: accounts table had no RLS | RLS enabled on accounts with account_isolation policy |
| S2: No database roles defined | Created vitalis_api, vitalis_worker, vitalis_admin, vitalis_readonly |
| S1: Worker role couldn't access all jobs | worker_bypass policy on ingestion_jobs for vitalis_worker |
| M3: Dictionaries writable by API role | REVOKE write on biomarker_dictionary, exercise_dictionary from vitalis_api |
| E1: ENUMs are migration landmines | data_source → data_sources lookup table; activity_type → activity_types lookup table |
| E2: wearable_daily column-per-metric rigidity | Added extended_metrics JSONB for non-core metrics |
| E3: No schema version table | Added schema_info table |
| N2: epigenetic_organ_ages denormalized fields | Removed chronological_age/delta_years; added epigenetic_organ_ages_enriched view |
| N3: doctor_visit_panels exposed without RLS | Added user_id + RLS policy |
| N4: Denormalized user_id inconsistency | Added enforce_user_id_consistency() trigger to 7 tables |
| P2: Blood marker trend queries require JOIN for date | Added collected_at to blood_markers; new compound index |
| P3: ingestion_jobs grows unbounded | Made partitioned by queued_at quarterly |
| P4: No covering indexes for dashboard queries | Added INCLUDE covering index on wearable_daily |
| P5/EC6: Pre-2023 partitions missing | Added partitions 2018–2022 + DEFAULT partition |
| G1: Documents deletion policy contradiction | Removed "never hard-deleted" claim; GDPR deletion applies |
| G2: No consent tracking | Added user_consents table |
| MT1: No sessions/refresh_tokens table | Added user_sessions table |
| MT2: No notifications table | Added notifications table |
| MT6: nutrition_logs missing updated_at | Added updated_at column and trigger |
| MT7: No file hash for duplicate detection | Added file_hash to documents + UNIQUE constraint |
| EC1: Blood marker duplicates on re-import | Added UNIQUE (panel_id, raw_name) on blood_markers |
| EC3: Timezone handling undocumented | Added COMMENT ON COLUMN to all DATE columns |
| EC7: Unmatched blood markers invisible | Added partial index WHERE biomarker_id IS NULL |
| EC8: lifting_sets.reps allows 0 | Changed CHECK to BETWEEN 1 AND 999 |
| B1: No age-specific biomarker ranges | Added biomarker_ranges table |
| B2: Missing common biomarkers in seed | Added 13 biomarkers including IGF-1, B12, folate, cystatin C |
| B3: Alias matching is case-sensitive | Lowercase enforcement trigger on biomarker_dictionary |
| N1: DEXA/lifting imperial-only storage | Added canonical _kg/_cm columns to dexa_scans and lifting_sets |
| M1: Family plan sharing fragile | Added family_read RLS policy on all user data tables |
| P1: raw_data JSONB bloat | Added raw_s3_key to wearable tables as migration path; kept raw_data nullable |

---

## 13. Performance

### Partitioning Strategy

| Table | Partition Key | Years | Estimated Rows @ 100K users, 5yr |
|-------|--------------|-------|-----------------------------------|
| `wearable_daily` | `date` (yearly) | 2018–2028 + DEFAULT | 182.5M total |
| `wearable_sleep` | `sleep_date` (yearly) | 2018–2028 + DEFAULT | 182.5M total |
| `wearable_activities` | `activity_date` (yearly) | 2018–2028 + DEFAULT | ~100M total |
| `audit_log` | `created_at` (quarterly) | 2024–2027 | High write volume |
| `ingestion_jobs` | `queued_at` (quarterly) | 2024+ | ~73M/year; prune after 90 days |

### Critical Indexes
See `schema.sql` for the full index list. Key additions in v2:
- `blood_markers(user_id, biomarker_id, collected_at DESC)` — trend queries without JOIN
- `wearable_daily(user_id, date DESC) INCLUDE (...)` — covering index for dashboard
- `blood_markers(user_id, created_at DESC) WHERE biomarker_id IS NULL` — unmatched marker queue

### Query Patterns
- **Dashboard home:** `WHERE user_id = ? AND date >= NOW() - 30` → partition pruning to current year + covering index
- **Biomarker trend:** `WHERE user_id = ? AND biomarker_id = ? ORDER BY collected_at DESC` → no JOIN needed
- **Family member view:** Set `app.current_account_id` → `family_read` policy handles access
- **Alias lookup:** `WHERE aliases @> ARRAY[lower(?)]` → GIN index

### Connection Pooling
PgBouncer in transaction mode. Pool size: 20 per API worker. `statement_timeout` per role to prevent runaway queries.
