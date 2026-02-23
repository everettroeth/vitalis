-- ============================================================
-- Vitalis — PostgreSQL Schema
-- Version: 1.0  |  Phase 1: Data Architecture
-- Target: PostgreSQL 15+
-- Scale: 100K users × 5 years of daily wearable data
-- ============================================================

-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============================================================
-- CUSTOM ENUM TYPES
-- ============================================================

-- Data source / wearable adapter
CREATE TYPE data_source AS ENUM (
    'garmin', 'apple_health', 'oura', 'whoop',
    'strong', 'manual', 'quest', 'labcorp',
    'dexafit', 'blueprint', 'trudiagnostic',
    'withings', 'fitbit', 'samsung_health',
    'dexcom', 'levels', 'eight_sleep', 'api', 'other'
);

-- Billing / subscription
CREATE TYPE subscription_tier   AS ENUM ('free', 'pro', 'family');
CREATE TYPE subscription_status AS ENUM ('active', 'past_due', 'canceled', 'trialing');
CREATE TYPE account_type        AS ENUM ('individual', 'household');

-- Document pipeline
CREATE TYPE parse_status   AS ENUM ('pending', 'processing', 'parsed', 'confirmed', 'failed', 'rejected');
CREATE TYPE document_type  AS ENUM ('blood_work', 'dexa', 'epigenetics', 'imaging', 'doctor_note', 'other');

-- Async job queue
CREATE TYPE job_status AS ENUM ('queued', 'processing', 'completed', 'failed', 'dead_letter');
CREATE TYPE job_type   AS ENUM ('daily_sync', 'backfill', 'document_parse', 'report_generate', 'data_export');

-- Audit
CREATE TYPE audit_action AS ENUM ('INSERT', 'UPDATE', 'DELETE', 'SOFT_DELETE', 'EXPORT', 'LOGIN', 'LOGOUT');

-- Measurements
CREATE TYPE measurement_metric AS ENUM (
    'weight', 'body_fat_pct', 'skeletal_muscle_mass',
    'blood_pressure_systolic', 'blood_pressure_diastolic',
    'resting_heart_rate', 'body_temperature',
    'height', 'waist_circumference', 'hip_circumference',
    'neck_circumference', 'chest_circumference',
    'thigh_circumference', 'bicep_circumference',
    'vo2_max', 'custom'
);

-- Activity types
CREATE TYPE activity_type AS ENUM (
    'running', 'cycling', 'swimming', 'walking',
    'strength_training', 'hiit', 'yoga', 'pilates',
    'rowing', 'elliptical', 'stair_climbing', 'hiking',
    'cross_country_skiing', 'indoor_cycling', 'treadmill',
    'other_cardio', 'other'
);

-- Biomarker categories (matches lab report sections)
CREATE TYPE biomarker_category AS ENUM (
    'metabolic', 'lipids', 'lipids_advanced', 'thyroid',
    'hormones', 'hematology', 'inflammation',
    'nutrition', 'vitamins', 'minerals', 'heavy_metals',
    'kidney', 'liver', 'pancreatic', 'electrolytes',
    'fatty_acids', 'immunology', 'cardiovascular',
    'urinalysis', 'other'
);

-- Epigenetic organ systems (Blueprint / TruDiagnostic)
CREATE TYPE organ_system AS ENUM (
    'lung', 'metabolic', 'musculoskeletal', 'blood',
    'liver', 'inflammation', 'kidney', 'heart',
    'hormone', 'immune', 'brain', 'overall'
);

-- Goal direction
CREATE TYPE goal_direction AS ENUM ('minimize', 'maximize', 'target');

-- Insight types
CREATE TYPE insight_type AS ENUM ('correlation', 'anomaly', 'trend', 'goal_progress', 'recommendation');

-- DEXA anatomical regions
CREATE TYPE dexa_region AS ENUM (
    'total', 'arms', 'arm_right', 'arm_left',
    'legs', 'leg_right', 'leg_left',
    'trunk', 'trunk_right', 'trunk_left',
    'android', 'gynoid', 'head'
);

-- Bone density skeletal regions
CREATE TYPE bone_density_region AS ENUM (
    'total', 'head', 'arms', 'legs',
    'trunk', 'ribs', 'spine', 'pelvis'
);

-- Menstrual cycle phase
CREATE TYPE menstrual_phase AS ENUM ('menstruation', 'follicular', 'ovulation', 'luteal', 'unknown');


-- ============================================================
-- UTILITY FUNCTION — updated_at auto-refresh trigger
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


-- ============================================================
-- SECTION 1: IDENTITY & AUTH
-- ============================================================

-- Billing entity — one per individual or household
CREATE TABLE accounts (
    account_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_customer_id  TEXT            UNIQUE,
    account_type        account_type    NOT NULL DEFAULT 'individual',
    subscription_tier   subscription_tier NOT NULL DEFAULT 'free',
    subscription_status subscription_status NOT NULL DEFAULT 'active',
    subscription_expires_at TIMESTAMPTZ,
    max_users           SMALLINT        NOT NULL DEFAULT 1 CHECK (max_users BETWEEN 1 AND 4),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ
);

COMMENT ON TABLE  accounts IS 'Billing entity. One per individual or household subscription.';
COMMENT ON COLUMN accounts.max_users IS '1=free/pro, 4=family tier.';

CREATE TRIGGER accounts_updated_at BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Auth identity + PII. One user per auth identity.
CREATE TABLE users (
    user_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID        NOT NULL REFERENCES accounts(account_id),
    email               TEXT        NOT NULL UNIQUE,
    email_verified_at   TIMESTAMPTZ,
    password_hash       TEXT,                   -- NULL for OAuth-only users
    display_name        TEXT        NOT NULL,
    date_of_birth       DATE,                   -- PII; encrypted at rest via app layer
    biological_sex      TEXT        CHECK (biological_sex IN ('male','female','other')),
    role                TEXT        NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin')),
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ             -- Soft delete; triggers GDPR deletion job
);

COMMENT ON TABLE  users IS 'Auth identity and PII. One per person. Email is canonical login.';
COMMENT ON COLUMN users.password_hash IS 'bcrypt hash. NULL if OAuth-only.';
COMMENT ON COLUMN users.date_of_birth IS 'PII. Encrypted at application layer before storage.';
COMMENT ON COLUMN users.deleted_at IS 'Soft delete. Sets off 30-day GDPR deletion grace period.';

CREATE INDEX idx_users_account_id ON users(account_id);
CREATE INDEX idx_users_email ON users(email);

CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Social login identities linked to a user
CREATE TABLE oauth_identities (
    identity_id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID    NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider            TEXT    NOT NULL CHECK (provider IN ('google','apple','microsoft')),
    provider_user_id    TEXT    NOT NULL,
    access_token_enc    TEXT,   -- AES-256 encrypted via pgcrypto or app layer
    refresh_token_enc   TEXT,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_user_id)
);

CREATE INDEX idx_oauth_identities_user_id ON oauth_identities(user_id);

CREATE TRIGGER oauth_identities_updated_at BEFORE UPDATE ON oauth_identities
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Per-user display preferences and settings
CREATE TABLE user_preferences (
    user_id             UUID        PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    weight_unit         TEXT        NOT NULL DEFAULT 'lbs' CHECK (weight_unit IN ('lbs','kg')),
    height_unit         TEXT        NOT NULL DEFAULT 'in'  CHECK (height_unit IN ('in','cm')),
    distance_unit       TEXT        NOT NULL DEFAULT 'miles' CHECK (distance_unit IN ('miles','km')),
    temperature_unit    TEXT        NOT NULL DEFAULT 'F'   CHECK (temperature_unit IN ('F','C')),
    energy_unit         TEXT        NOT NULL DEFAULT 'kcal' CHECK (energy_unit IN ('kcal','kJ')),
    timezone            TEXT        NOT NULL DEFAULT 'UTC',
    notifications_enabled BOOLEAN  NOT NULL DEFAULT TRUE,
    notification_prefs  JSONB       NOT NULL DEFAULT '{}', -- Per-category notification flags
    dashboard_layout    JSONB       NOT NULL DEFAULT '{}', -- Widget order and visibility
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE user_preferences IS 'User display and notification settings. One row per user.';

CREATE TRIGGER user_preferences_updated_at BEFORE UPDATE ON user_preferences
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ============================================================
-- SECTION 2: DEVICE CONNECTIONS
-- ============================================================

-- OAuth tokens and sync state per user per wearable source
CREATE TABLE connected_devices (
    device_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    source              data_source NOT NULL,
    display_name        TEXT,                   -- e.g. "Garmin Forerunner 965"
    access_token_enc    TEXT,                   -- AES-256 encrypted
    refresh_token_enc   TEXT,
    token_expires_at    TIMESTAMPTZ,
    scope               TEXT[],
    external_user_id    TEXT,                   -- User's ID in source system
    last_sync_at        TIMESTAMPTZ,
    last_sync_status    TEXT        CHECK (last_sync_status IN ('success','error','partial')),
    last_sync_error     TEXT,
    sync_cursor         JSONB       NOT NULL DEFAULT '{}', -- Pagination / checkpoint state
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, source)                    -- One active connection per source per user
);

COMMENT ON TABLE connected_devices IS 'OAuth tokens and sync state per user per wearable/lab source.';
COMMENT ON COLUMN connected_devices.sync_cursor IS 'Opaque JSON checkpoint for resuming incremental syncs.';

CREATE INDEX idx_connected_devices_user_id ON connected_devices(user_id);
CREATE INDEX idx_connected_devices_sync ON connected_devices(source, last_sync_at)
    WHERE is_active = TRUE;

CREATE TRIGGER connected_devices_updated_at BEFORE UPDATE ON connected_devices
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ============================================================
-- SECTION 3: WEARABLE DATA (PARTITIONED TIME-SERIES)
-- ============================================================

-- Unified daily summary metrics, one row per (user, date, source).
-- PARTITIONED BY RANGE(date) — yearly partitions.
-- At 100K users: ~37M rows per annual partition.
CREATE TABLE wearable_daily (
    daily_id                    UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id                     UUID        NOT NULL,
    date                        DATE        NOT NULL,
    source                      data_source NOT NULL,
    resting_hr_bpm              SMALLINT    CHECK (resting_hr_bpm BETWEEN 20 AND 300),
    max_hr_bpm                  SMALLINT    CHECK (max_hr_bpm BETWEEN 20 AND 300),
    hrv_rmssd_ms                NUMERIC(6,2) CHECK (hrv_rmssd_ms BETWEEN 1 AND 300),
    steps                       INTEGER     CHECK (steps BETWEEN 0 AND 100000),
    active_calories_kcal        SMALLINT    CHECK (active_calories_kcal >= 0),
    total_calories_kcal         SMALLINT    CHECK (total_calories_kcal >= 0),
    active_minutes              SMALLINT    CHECK (active_minutes BETWEEN 0 AND 1440),
    moderate_intensity_minutes  SMALLINT    CHECK (moderate_intensity_minutes BETWEEN 0 AND 1440),
    vigorous_intensity_minutes  SMALLINT    CHECK (vigorous_intensity_minutes BETWEEN 0 AND 1440),
    distance_m                  INTEGER     CHECK (distance_m >= 0),
    floors_climbed              SMALLINT    CHECK (floors_climbed >= 0),
    spo2_avg_pct                NUMERIC(4,1) CHECK (spo2_avg_pct BETWEEN 70 AND 100),
    spo2_min_pct                NUMERIC(4,1) CHECK (spo2_min_pct BETWEEN 70 AND 100),
    respiratory_rate_avg        NUMERIC(4,1) CHECK (respiratory_rate_avg BETWEEN 4 AND 60),
    stress_avg                  SMALLINT    CHECK (stress_avg BETWEEN 0 AND 100),
    body_battery_start          SMALLINT    CHECK (body_battery_start BETWEEN 0 AND 100),
    body_battery_end            SMALLINT    CHECK (body_battery_end BETWEEN 0 AND 100),
    readiness_score             SMALLINT    CHECK (readiness_score BETWEEN 0 AND 100),
    recovery_score              SMALLINT    CHECK (recovery_score BETWEEN 0 AND 100),
    skin_temp_deviation_c       NUMERIC(4,2),
    vo2_max_ml_kg_min           NUMERIC(4,1) CHECK (vo2_max_ml_kg_min BETWEEN 10 AND 100),
    raw_data                    JSONB,      -- Source-specific full API response
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (daily_id, date)
) PARTITION BY RANGE (date);

COMMENT ON TABLE wearable_daily IS 'Unified daily summary: one row per (user, date, source). Multiple sources per day is valid.';
COMMENT ON COLUMN wearable_daily.raw_data IS 'Full source API response archived for re-processing.';

-- Yearly partitions — create one per year in advance
CREATE TABLE wearable_daily_2023 PARTITION OF wearable_daily FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE wearable_daily_2024 PARTITION OF wearable_daily FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE wearable_daily_2025 PARTITION OF wearable_daily FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE wearable_daily_2026 PARTITION OF wearable_daily FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
CREATE TABLE wearable_daily_2027 PARTITION OF wearable_daily FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');
CREATE TABLE wearable_daily_2028 PARTITION OF wearable_daily FOR VALUES FROM ('2028-01-01') TO ('2029-01-01');

CREATE UNIQUE INDEX idx_wearable_daily_unique ON wearable_daily (user_id, date, source);
CREATE INDEX idx_wearable_daily_user_date ON wearable_daily (user_id, date DESC);
CREATE INDEX idx_wearable_daily_source ON wearable_daily (user_id, source, date DESC);


-- Detailed per-source sleep data. One row per (user, sleep_date, source).
CREATE TABLE wearable_sleep (
    sleep_id                UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id                 UUID        NOT NULL,
    sleep_date              DATE        NOT NULL, -- Date the sleep ended (morning of)
    source                  data_source NOT NULL,
    sleep_start             TIMESTAMPTZ,
    sleep_end               TIMESTAMPTZ,
    total_sleep_minutes     SMALLINT    CHECK (total_sleep_minutes BETWEEN 0 AND 1440),
    rem_minutes             SMALLINT    CHECK (rem_minutes BETWEEN 0 AND 720),
    deep_minutes            SMALLINT    CHECK (deep_minutes BETWEEN 0 AND 720),
    light_minutes           SMALLINT    CHECK (light_minutes BETWEEN 0 AND 720),
    awake_minutes           SMALLINT    CHECK (awake_minutes BETWEEN 0 AND 480),
    sleep_latency_minutes   SMALLINT    CHECK (sleep_latency_minutes BETWEEN 0 AND 240),
    sleep_efficiency_pct    NUMERIC(4,1) CHECK (sleep_efficiency_pct BETWEEN 0 AND 100),
    sleep_score             SMALLINT    CHECK (sleep_score BETWEEN 0 AND 100),
    interruptions           SMALLINT    CHECK (interruptions >= 0),
    avg_hr_bpm              SMALLINT    CHECK (avg_hr_bpm BETWEEN 20 AND 200),
    min_hr_bpm              SMALLINT    CHECK (min_hr_bpm BETWEEN 20 AND 200),
    avg_hrv_ms              NUMERIC(6,2) CHECK (avg_hrv_ms BETWEEN 1 AND 300),
    avg_respiratory_rate    NUMERIC(4,1) CHECK (avg_respiratory_rate BETWEEN 4 AND 60),
    avg_spo2_pct            NUMERIC(4,1) CHECK (avg_spo2_pct BETWEEN 70 AND 100),
    avg_skin_temp_deviation_c NUMERIC(4,2),
    hypnogram               JSONB,      -- [{t: epoch_seconds, stage: 'rem'|'deep'|'light'|'awake'}]
    raw_data                JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (sleep_id, sleep_date)
) PARTITION BY RANGE (sleep_date);

CREATE TABLE wearable_sleep_2023 PARTITION OF wearable_sleep FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE wearable_sleep_2024 PARTITION OF wearable_sleep FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE wearable_sleep_2025 PARTITION OF wearable_sleep FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE wearable_sleep_2026 PARTITION OF wearable_sleep FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
CREATE TABLE wearable_sleep_2027 PARTITION OF wearable_sleep FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');
CREATE TABLE wearable_sleep_2028 PARTITION OF wearable_sleep FOR VALUES FROM ('2028-01-01') TO ('2029-01-01');

CREATE UNIQUE INDEX idx_wearable_sleep_unique ON wearable_sleep (user_id, sleep_date, source);
CREATE INDEX idx_wearable_sleep_user ON wearable_sleep (user_id, sleep_date DESC);


-- Individual workout / activity records.
CREATE TABLE wearable_activities (
    activity_id             UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id                 UUID        NOT NULL,
    activity_date           DATE        NOT NULL, -- Partition key; date of activity start
    source                  data_source NOT NULL,
    source_activity_id      TEXT,                 -- External ID for idempotent re-sync
    activity_type           activity_type NOT NULL,
    activity_name           TEXT,
    start_time              TIMESTAMPTZ,
    end_time                TIMESTAMPTZ,
    duration_seconds        INTEGER     CHECK (duration_seconds >= 0),
    distance_m              NUMERIC(10,2) CHECK (distance_m >= 0),
    calories_kcal           SMALLINT    CHECK (calories_kcal >= 0),
    avg_hr_bpm              SMALLINT    CHECK (avg_hr_bpm BETWEEN 20 AND 300),
    max_hr_bpm              SMALLINT    CHECK (max_hr_bpm BETWEEN 20 AND 300),
    hr_zone_1_seconds       INTEGER     CHECK (hr_zone_1_seconds >= 0),
    hr_zone_2_seconds       INTEGER     CHECK (hr_zone_2_seconds >= 0),
    hr_zone_3_seconds       INTEGER     CHECK (hr_zone_3_seconds >= 0),
    hr_zone_4_seconds       INTEGER     CHECK (hr_zone_4_seconds >= 0),
    hr_zone_5_seconds       INTEGER     CHECK (hr_zone_5_seconds >= 0),
    avg_pace_sec_per_km     NUMERIC(7,2),
    avg_speed_kmh           NUMERIC(5,2),
    elevation_gain_m        NUMERIC(7,2),
    avg_power_watts         SMALLINT,
    normalized_power_watts  SMALLINT,
    training_stress_score   NUMERIC(6,1),
    training_effect_aerobic     NUMERIC(3,1) CHECK (training_effect_aerobic BETWEEN 0 AND 5),
    training_effect_anaerobic   NUMERIC(3,1) CHECK (training_effect_anaerobic BETWEEN 0 AND 5),
    vo2_max_ml_kg_min       NUMERIC(4,1) CHECK (vo2_max_ml_kg_min BETWEEN 10 AND 100),
    notes                   TEXT,
    raw_data                JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (activity_id, activity_date)
) PARTITION BY RANGE (activity_date);

CREATE TABLE wearable_activities_2023 PARTITION OF wearable_activities FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE wearable_activities_2024 PARTITION OF wearable_activities FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE wearable_activities_2025 PARTITION OF wearable_activities FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE wearable_activities_2026 PARTITION OF wearable_activities FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
CREATE TABLE wearable_activities_2027 PARTITION OF wearable_activities FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');
CREATE TABLE wearable_activities_2028 PARTITION OF wearable_activities FOR VALUES FROM ('2028-01-01') TO ('2029-01-01');

-- Dedup: one row per (user, source, source_activity_id) — partial index where source_activity_id is not null
CREATE UNIQUE INDEX idx_wearable_activities_dedup ON wearable_activities (user_id, source, source_activity_id)
    WHERE source_activity_id IS NOT NULL;
CREATE INDEX idx_wearable_activities_user ON wearable_activities (user_id, activity_date DESC);
CREATE INDEX idx_wearable_activities_type ON wearable_activities (user_id, activity_type, activity_date DESC);


-- ============================================================
-- SECTION 4: LAB WORK
-- ============================================================

-- Header for a lab visit / panel order
CREATE TABLE blood_panels (
    panel_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    lab_name        TEXT,                   -- "Quest Diagnostics", "Labcorp"
    lab_provider    TEXT,                   -- Ordering provider name
    panel_name      TEXT,                   -- e.g. "Comprehensive Metabolic Panel"
    collected_at    TIMESTAMPTZ,            -- Specimen collection time
    reported_at     TIMESTAMPTZ,            -- When results were released
    fasting         BOOLEAN,
    specimen_id     TEXT,                   -- Lab's specimen identifier
    document_id     UUID REFERENCES documents(document_id) ON DELETE SET NULL,  -- source PDF
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE blood_panels IS 'One row per lab visit / panel order. Groups related blood_markers together.';

CREATE INDEX idx_blood_panels_user ON blood_panels(user_id, collected_at DESC);

CREATE TRIGGER blood_panels_updated_at BEFORE UPDATE ON blood_panels
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Canonical biomarker reference dictionary — shared across all users, no RLS
CREATE TABLE biomarker_dictionary (
    biomarker_id        UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name      TEXT                NOT NULL UNIQUE,  -- slug: 'glucose', 'ldl_cholesterol'
    display_name        TEXT                NOT NULL,         -- "Glucose", "LDL Cholesterol"
    category            biomarker_category  NOT NULL,
    subcategory         TEXT,               -- "CBC", "CMP", "Cardio IQ", "Thyroid Panel"
    canonical_unit      TEXT                NOT NULL,         -- Unit for value_canonical storage
    common_units        TEXT[]              NOT NULL DEFAULT '{}',  -- All accepted input units
    loinc_code          TEXT,               -- LOINC interoperability code
    description         TEXT,               -- Clinical description
    aliases             TEXT[]              NOT NULL DEFAULT '{}',  -- Synonyms for AI parsing
    sex_specific_ranges BOOLEAN             NOT NULL DEFAULT FALSE,
    optimal_low_male    NUMERIC(12,4),
    optimal_high_male   NUMERIC(12,4),
    optimal_low_female  NUMERIC(12,4),
    optimal_high_female NUMERIC(12,4),
    optimal_low         NUMERIC(12,4),      -- General optimal (sex-neutral)
    optimal_high        NUMERIC(12,4),
    normal_low          NUMERIC(12,4),      -- Standard population reference range
    normal_high         NUMERIC(12,4),
    is_qualitative      BOOLEAN             NOT NULL DEFAULT FALSE,
    sort_order          INTEGER             NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE biomarker_dictionary IS 'Canonical reference for all known biomarkers. Shared read-only across all users.';
COMMENT ON COLUMN biomarker_dictionary.aliases IS 'All known lab report synonyms. GIN indexed for fast AI parsing lookup.';
COMMENT ON COLUMN biomarker_dictionary.canonical_unit IS 'All blood_markers.value_canonical values use this unit.';

CREATE INDEX idx_biomarker_dict_category ON biomarker_dictionary(category, sort_order);
CREATE INDEX idx_biomarker_dict_name ON biomarker_dictionary(canonical_name);
CREATE INDEX idx_biomarker_dict_aliases ON biomarker_dictionary USING GIN (aliases);

CREATE TRIGGER biomarker_dictionary_updated_at BEFORE UPDATE ON biomarker_dictionary
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Individual marker results linked to a panel and the canonical dictionary
CREATE TABLE blood_markers (
    marker_id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    panel_id            UUID        NOT NULL REFERENCES blood_panels(panel_id) ON DELETE CASCADE,
    biomarker_id        UUID        REFERENCES biomarker_dictionary(biomarker_id), -- NULL if unknown
    raw_name            TEXT        NOT NULL,       -- Exact name as it appeared on the report
    sub_panel           TEXT,                       -- "CBC", "CMP", "Cardio IQ", etc.
    value_numeric       NUMERIC(12,4),              -- NULL for qualitative results
    value_text          TEXT,                       -- Qualitative: "NEGATIVE", "POSITIVE", "A", "B"
    unit                TEXT,                       -- Unit as reported by lab
    value_canonical     NUMERIC(12,4),              -- Converted to biomarker_dictionary.canonical_unit
    ref_range_low       NUMERIC(12,4),
    ref_range_high      NUMERIC(12,4),
    ref_range_text      TEXT,                       -- Full reference range text from report
    flag                TEXT        CHECK (flag IN ('H','L','HH','LL','ABNORMAL','CRITICAL')),
    in_range            BOOLEAN,
    optimal_low         NUMERIC(12,4),              -- Snapshot of dictionary optimal at ingestion time
    optimal_high        NUMERIC(12,4),
    lab_code            TEXT,                       -- Lab site code (EN, NW, Z4M, etc.)
    parse_confidence    NUMERIC(3,2) CHECK (parse_confidence BETWEEN 0 AND 1),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE blood_markers IS 'Individual biomarker results. Linked to a panel and (where matched) the canonical dictionary.';
COMMENT ON COLUMN blood_markers.raw_name IS 'Preserved verbatim from source — never altered.';
COMMENT ON COLUMN blood_markers.value_canonical IS 'Converted to biomarker_dictionary.canonical_unit for trend analysis.';
COMMENT ON COLUMN blood_markers.parse_confidence IS '0.0-1.0 confidence score from AI extraction pipeline.';

CREATE INDEX idx_blood_markers_user_biomarker ON blood_markers(user_id, biomarker_id);
CREATE INDEX idx_blood_markers_panel ON blood_markers(panel_id);
CREATE INDEX idx_blood_markers_user_panel ON blood_markers(user_id, panel_id);

CREATE TRIGGER blood_markers_updated_at BEFORE UPDATE ON blood_markers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ============================================================
-- SECTION 5: BODY COMPOSITION (DEXA)
-- ============================================================

-- One row per DEXA scan session
CREATE TABLE dexa_scans (
    scan_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider            TEXT,                   -- "DexaFit", "BodySpec", "Other"
    scan_date           DATE        NOT NULL,
    age_at_scan         NUMERIC(4,1),
    height_in           NUMERIC(5,2),           -- Height in inches as measured
    weight_lbs          NUMERIC(6,2),           -- Scale weight day of scan
    total_mass_lbs      NUMERIC(6,2),           -- DEXA total mass (slightly differs from scale)
    total_fat_lbs       NUMERIC(6,2)  CHECK (total_fat_lbs >= 0),
    total_lean_lbs      NUMERIC(6,2)  CHECK (total_lean_lbs >= 0),
    total_bmc_lbs       NUMERIC(6,2)  CHECK (total_bmc_lbs >= 0), -- Bone Mineral Content
    total_body_fat_pct  NUMERIC(4,1)  CHECK (total_body_fat_pct BETWEEN 1 AND 80),
    visceral_fat_lbs    NUMERIC(6,3)  CHECK (visceral_fat_lbs >= 0),
    visceral_fat_in3    NUMERIC(7,2)  CHECK (visceral_fat_in3 >= 0), -- Volume in cubic inches
    android_gynoid_ratio NUMERIC(4,2) CHECK (android_gynoid_ratio > 0),
    document_id         UUID REFERENCES documents(document_id) ON DELETE SET NULL,  -- source doc
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ
);

COMMENT ON TABLE dexa_scans IS 'DEXA scan session header. Regional detail in dexa_regions and dexa_bone_density.';

CREATE INDEX idx_dexa_scans_user ON dexa_scans(user_id, scan_date DESC);

CREATE TRIGGER dexa_scans_updated_at BEFORE UPDATE ON dexa_scans
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Normalized body composition by anatomical region (one row per region per scan)
CREATE TABLE dexa_regions (
    region_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id         UUID        NOT NULL REFERENCES dexa_scans(scan_id) ON DELETE CASCADE,
    user_id         UUID        NOT NULL,   -- Denormalized for RLS
    region          dexa_region NOT NULL,
    body_fat_pct    NUMERIC(4,1) CHECK (body_fat_pct BETWEEN 0 AND 100),
    fat_lbs         NUMERIC(6,2) CHECK (fat_lbs >= 0),
    lean_lbs        NUMERIC(6,2) CHECK (lean_lbs >= 0),
    bmc_lbs         NUMERIC(5,3) CHECK (bmc_lbs >= 0),
    total_mass_lbs  NUMERIC(6,2) CHECK (total_mass_lbs >= 0),
    UNIQUE (scan_id, region)
);

COMMENT ON TABLE dexa_regions IS 'Body fat % and composition by anatomical region. Normalized from DEXA report.';

CREATE INDEX idx_dexa_regions_scan ON dexa_regions(scan_id);
CREATE INDEX idx_dexa_regions_user ON dexa_regions(user_id);


-- Bone mineral density by skeletal region (T-score, Z-score)
CREATE TABLE dexa_bone_density (
    density_id      UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id         UUID                    NOT NULL REFERENCES dexa_scans(scan_id) ON DELETE CASCADE,
    user_id         UUID                    NOT NULL,   -- Denormalized for RLS
    region          bone_density_region     NOT NULL,
    bmd_g_cm2       NUMERIC(6,3)            CHECK (bmd_g_cm2 > 0),  -- Bone mineral density
    t_score         NUMERIC(4,1),           -- vs. young adult (30-35yr peak); NULL for sub-regions
    z_score         NUMERIC(4,1),           -- vs. age-matched; NULL for sub-regions
    UNIQUE (scan_id, region)
);

COMMENT ON TABLE dexa_bone_density IS 'BMD T-scores and Z-scores by skeletal region. Total row has T/Z scores; sub-regions may not.';

CREATE INDEX idx_dexa_bone_density_scan ON dexa_bone_density(scan_id);
CREATE INDEX idx_dexa_bone_density_user ON dexa_bone_density(user_id);


-- ============================================================
-- SECTION 6: EPIGENETICS
-- ============================================================

-- Header for one epigenetic test kit
CREATE TABLE epigenetic_tests (
    test_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider            TEXT,               -- "Blueprint Biomarkers", "TruDiagnostic"
    kit_id              TEXT,               -- External kit identifier (e.g. "2MC9AZV")
    collected_at        DATE,
    reported_at         DATE,
    chronological_age   NUMERIC(4,1) CHECK (chronological_age BETWEEN 0 AND 120),
    biological_age      NUMERIC(4,1) CHECK (biological_age BETWEEN 0 AND 120),
    pace_score          NUMERIC(4,2) CHECK (pace_score BETWEEN 0.2 AND 3.0),
    pace_percentile     NUMERIC(5,2) CHECK (pace_percentile BETWEEN 0 AND 100),
    telomere_length     NUMERIC(6,3),       -- Telomere length in kb (if measured)
    methylation_clock   TEXT,               -- Algorithm: 'dunedinpace', 'horvath', 'grimage'
    document_id         UUID REFERENCES documents(document_id) ON DELETE SET NULL,  -- source doc
    raw_data            JSONB,              -- Full provider response
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ
);

COMMENT ON TABLE epigenetic_tests IS 'Epigenetic test results including PACE (speed of aging) and overall biological age.';
COMMENT ON COLUMN epigenetic_tests.pace_score IS 'DunedinPACE: <1.0 = aging slower, >1.0 = aging faster than chronological rate.';

CREATE INDEX idx_epigenetic_tests_user ON epigenetic_tests(user_id, collected_at DESC);

CREATE TRIGGER epigenetic_tests_updated_at BEFORE UPDATE ON epigenetic_tests
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Per-organ system biological age. ~12 rows per test (11 organs + overall).
CREATE TABLE epigenetic_organ_ages (
    organ_age_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id             UUID        NOT NULL REFERENCES epigenetic_tests(test_id) ON DELETE CASCADE,
    user_id             UUID        NOT NULL,   -- Denormalized for RLS
    organ_system        organ_system NOT NULL,
    biological_age      NUMERIC(4,1),
    chronological_age   NUMERIC(4,1),           -- Copied for convenience
    delta_years         NUMERIC(4,1),           -- biological_age - chronological_age
    direction           TEXT CHECK (direction IN ('younger','older','same')),
    UNIQUE (test_id, organ_system)
);

COMMENT ON TABLE epigenetic_organ_ages IS '11 organ system biological ages per test. delta_years < 0 = younger than chronological.';

CREATE INDEX idx_epigenetic_organ_ages_test ON epigenetic_organ_ages(test_id);
CREATE INDEX idx_epigenetic_organ_ages_user ON epigenetic_organ_ages(user_id, organ_system);


-- ============================================================
-- SECTION 7: FITNESS (LIFTING)
-- ============================================================

-- Canonical exercise catalog — shared, no RLS
CREATE TABLE exercise_dictionary (
    exercise_id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name      TEXT    NOT NULL UNIQUE,
    display_name        TEXT    NOT NULL,
    aliases             TEXT[]  NOT NULL DEFAULT '{}',
    primary_muscle      TEXT,
    secondary_muscles   TEXT[]  DEFAULT '{}',
    equipment           TEXT,   -- 'barbell', 'dumbbell', 'machine', 'bodyweight', 'cable'
    category            TEXT    CHECK (category IN ('compound','isolation','cardio','mobility')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE exercise_dictionary IS 'Canonical exercise catalog. Used for matching Strong CSV imports and manual entries.';

CREATE INDEX idx_exercise_dict_aliases ON exercise_dictionary USING GIN (aliases);


-- A single workout session
CREATE TABLE lifting_sessions (
    session_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_date    DATE        NOT NULL,
    source          data_source NOT NULL DEFAULT 'manual',
    source_session_id TEXT,                 -- For dedup on re-import
    name            TEXT,                   -- "Upper A", "Push Day"
    duration_seconds INTEGER    CHECK (duration_seconds BETWEEN 0 AND 86400),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_lifting_sessions_user ON lifting_sessions(user_id, session_date DESC);
CREATE UNIQUE INDEX idx_lifting_sessions_dedup ON lifting_sessions(user_id, source, source_session_id)
    WHERE source_session_id IS NOT NULL;

CREATE TRIGGER lifting_sessions_updated_at BEFORE UPDATE ON lifting_sessions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Individual sets within a lifting session
CREATE TABLE lifting_sets (
    set_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES lifting_sessions(session_id) ON DELETE CASCADE,
    user_id         UUID        NOT NULL,   -- Denormalized for RLS
    exercise_id     UUID        REFERENCES exercise_dictionary(exercise_id),
    raw_exercise_name TEXT,                 -- Verbatim from import if not matched to dictionary
    exercise_order  SMALLINT    NOT NULL DEFAULT 1,  -- Order of exercise in session
    set_number      SMALLINT    NOT NULL DEFAULT 1,  -- Set number within this exercise block
    weight_lbs      NUMERIC(6,2) CHECK (weight_lbs BETWEEN 0 AND 2000),
    reps            SMALLINT    CHECK (reps BETWEEN 0 AND 999),
    rpe             NUMERIC(3,1) CHECK (rpe BETWEEN 0 AND 10),
    is_warmup       BOOLEAN     NOT NULL DEFAULT FALSE,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE lifting_sets IS 'Individual sets. exercise_id may be NULL if raw import not yet matched to dictionary.';

CREATE INDEX idx_lifting_sets_session ON lifting_sets(session_id);
CREATE INDEX idx_lifting_sets_exercise ON lifting_sets(exercise_id, user_id);  -- For PR lookups


-- ============================================================
-- SECTION 8: MANUAL TRACKING
-- ============================================================

-- Generic scalar measurements: weight, BP, temperature, circumferences, etc.
CREATE TABLE measurements (
    measurement_id  UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID                NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    metric          measurement_metric  NOT NULL,
    value           NUMERIC(10,3)       NOT NULL,
    unit            TEXT                NOT NULL,
    measured_at     TIMESTAMPTZ         NOT NULL,
    source          data_source         NOT NULL DEFAULT 'manual',
    notes           TEXT,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE measurements IS 'Scalar body metrics: weight, blood pressure, temperature, circumferences. One row per reading.';
COMMENT ON COLUMN measurements.metric IS 'Use custom metric tables for anything not in the measurement_metric enum.';

CREATE INDEX idx_measurements_user_metric ON measurements(user_id, metric, measured_at DESC);

CREATE TRIGGER measurements_updated_at BEFORE UPDATE ON measurements
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- User-defined metric definitions (track anything)
CREATE TABLE custom_metrics (
    metric_id   UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID    NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    unit        TEXT,
    data_type   TEXT    NOT NULL DEFAULT 'numeric'
                        CHECK (data_type IN ('numeric','boolean','text','scale_1_5')),
    min_value   NUMERIC,
    max_value   NUMERIC,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, name)
);


-- Values for user-defined custom metrics
CREATE TABLE custom_metric_entries (
    entry_id        UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_id       UUID    NOT NULL REFERENCES custom_metrics(metric_id) ON DELETE CASCADE,
    user_id         UUID    NOT NULL,   -- Denormalized for RLS
    value_numeric   NUMERIC,
    value_text      TEXT,
    measured_at     TIMESTAMPTZ NOT NULL,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_custom_entries_user ON custom_metric_entries(user_id, metric_id, measured_at DESC);


-- Supplement and medication stack
CREATE TABLE supplements (
    supplement_id   UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID    NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    brand           TEXT,
    dose_amount     NUMERIC(8,3) CHECK (dose_amount > 0),
    dose_unit       TEXT,               -- 'mg', 'g', 'IU', 'mcg', 'ml'
    frequency       TEXT,               -- 'daily', '2x_daily', 'weekly', 'as_needed'
    timing          TEXT,               -- 'morning', 'evening', 'with_meal', 'pre_workout'
    started_at      DATE,
    ended_at        DATE,               -- NULL = currently taking
    purpose         TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_supplements_user_active ON supplements(user_id) WHERE ended_at IS NULL AND deleted_at IS NULL;
CREATE INDEX idx_supplements_user ON supplements(user_id, started_at DESC);

CREATE TRIGGER supplements_updated_at BEFORE UPDATE ON supplements
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Daily intake log for correlation analysis (supplements ↔ biomarkers)
CREATE TABLE supplement_logs (
    log_id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    supplement_id   UUID    NOT NULL REFERENCES supplements(supplement_id) ON DELETE CASCADE,
    user_id         UUID    NOT NULL,   -- Denormalized for RLS
    taken_at        TIMESTAMPTZ NOT NULL,
    dose_amount     NUMERIC(8,3),       -- May differ from default dose
    dose_unit       TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_supplement_logs_user ON supplement_logs(user_id, taken_at DESC);
CREATE INDEX idx_supplement_logs_supplement ON supplement_logs(supplement_id, taken_at);


-- Flexible meal, fasting, and nutrition logs
CREATE TABLE nutrition_logs (
    nutrition_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    log_date        DATE        NOT NULL,
    meal_type       TEXT        CHECK (meal_type IN ('breakfast','lunch','dinner','snack','fast','other')),
    calories_kcal   SMALLINT    CHECK (calories_kcal >= 0),
    protein_g       NUMERIC(6,2) CHECK (protein_g >= 0),
    carbs_g         NUMERIC(6,2) CHECK (carbs_g >= 0),
    fat_g           NUMERIC(6,2) CHECK (fat_g >= 0),
    fiber_g         NUMERIC(6,2) CHECK (fiber_g >= 0),
    source          data_source NOT NULL DEFAULT 'manual',
    raw_data        JSONB,      -- Full source data (MyFitnessPal, Cronometer, etc.)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_nutrition_logs_user ON nutrition_logs(user_id, log_date DESC);


-- Daily mood, energy, stress check-in (1–5 scale)
CREATE TABLE mood_journal (
    journal_id      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID    NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    journal_date    DATE    NOT NULL,
    mood_score      SMALLINT CHECK (mood_score BETWEEN 1 AND 5),
    energy_score    SMALLINT CHECK (energy_score BETWEEN 1 AND 5),
    stress_score    SMALLINT CHECK (stress_score BETWEEN 1 AND 5),
    notes           TEXT,   -- Free-text journal entry
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (user_id, journal_date)
);

CREATE INDEX idx_mood_journal_user ON mood_journal(user_id, journal_date DESC);

CREATE TRIGGER mood_journal_updated_at BEFORE UPDATE ON mood_journal
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Menstrual cycle tracking (correlates with HRV, sleep, mood)
CREATE TABLE menstrual_cycles (
    cycle_id        UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID                NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    cycle_date      DATE                NOT NULL,
    phase           menstrual_phase,
    flow_intensity  SMALLINT            CHECK (flow_intensity BETWEEN 0 AND 4),
                                        -- 0=none, 1=spotting, 2=light, 3=medium, 4=heavy
    symptoms        TEXT[]              DEFAULT '{}',
    notes           TEXT,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, cycle_date)
);

CREATE INDEX idx_menstrual_cycles_user ON menstrual_cycles(user_id, cycle_date DESC);


-- Medical appointments and notes
CREATE TABLE doctor_visits (
    visit_id        UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID    NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    visit_date      DATE    NOT NULL,
    provider_name   TEXT,
    specialty       TEXT,
    notes           TEXT,
    follow_up_date  DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_doctor_visits_user ON doctor_visits(user_id, visit_date DESC);

CREATE TRIGGER doctor_visits_updated_at BEFORE UPDATE ON doctor_visits
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Link table: doctor visits ↔ blood panels ordered that day
CREATE TABLE doctor_visit_panels (
    visit_id    UUID NOT NULL REFERENCES doctor_visits(visit_id) ON DELETE CASCADE,
    panel_id    UUID NOT NULL REFERENCES blood_panels(panel_id) ON DELETE CASCADE,
    PRIMARY KEY (visit_id, panel_id)
);


-- Progress photos linked to a date and optionally a DEXA scan
CREATE TABLE photos (
    photo_id            UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID    NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    photo_date          DATE    NOT NULL,
    photo_type          TEXT    CHECK (photo_type IN ('front','back','left','right','other')),
    s3_key              TEXT    NOT NULL,        -- Path in S3/R2 bucket
    s3_thumbnail_key    TEXT,
    file_size_bytes     INTEGER CHECK (file_size_bytes > 0),
    linked_scan_id      UUID    REFERENCES dexa_scans(scan_id),
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ
);

CREATE INDEX idx_photos_user ON photos(user_id, photo_date DESC);


-- Source PDFs uploaded by users — permanent archive
CREATE TABLE documents (
    document_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    document_type       document_type   NOT NULL,
    provider_name       TEXT,           -- "Quest Diagnostics", "DexaFit", "Blueprint Biomarkers"
    original_filename   TEXT,
    s3_key              TEXT            NOT NULL,
    file_size_bytes     INTEGER         CHECK (file_size_bytes > 0),
    mime_type           TEXT            NOT NULL DEFAULT 'application/pdf',
    parse_status        parse_status    NOT NULL DEFAULT 'pending',
    parse_confidence    NUMERIC(3,2)    CHECK (parse_confidence BETWEEN 0 AND 1),
    parse_result        JSONB,          -- Raw LLM extraction output
    parsed_at           TIMESTAMPTZ,
    confirmed_at        TIMESTAMPTZ,
    confirmed_by        UUID            REFERENCES users(user_id),
    linked_record_id    UUID,           -- UUID of resulting blood_panel / dexa_scan / epigenetic_test
    linked_record_type  TEXT            CHECK (linked_record_type IN ('blood_panel','dexa_scan','epigenetic_test')),
    error_message       TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ
);

COMMENT ON TABLE documents IS 'Uploaded PDFs. Source of truth for AI-parsed lab/scan data. Never hard-deleted.';
COMMENT ON COLUMN documents.s3_key IS 'S3 object key. Documents archived permanently even after account deletion.';

CREATE INDEX idx_documents_user ON documents(user_id, created_at DESC);
CREATE INDEX idx_documents_pending ON documents(parse_status) WHERE parse_status = 'pending';

CREATE TRIGGER documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ============================================================
-- SECTION 9: GOALS & INSIGHTS
-- ============================================================

-- User-defined targets for any trackable metric
CREATE TABLE goals (
    goal_id                 UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    metric_type             TEXT            NOT NULL CHECK (metric_type IN ('blood_marker','measurement','wearable','custom')),
    biomarker_id            UUID            REFERENCES biomarker_dictionary(biomarker_id),
    metric_name             TEXT            NOT NULL,   -- Canonical slug
    target_value            NUMERIC(12,4),
    target_unit             TEXT,
    direction               goal_direction  NOT NULL DEFAULT 'target',
    alert_threshold_low     NUMERIC(12,4),
    alert_threshold_high    NUMERIC(12,4),
    alert_enabled           BOOLEAN         NOT NULL DEFAULT TRUE,
    notes                   TEXT,
    is_active               BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_goals_user_active ON goals(user_id) WHERE is_active = TRUE;

CREATE TRIGGER goals_updated_at BEFORE UPDATE ON goals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Fired alerts when goal thresholds are crossed
CREATE TABLE goal_alerts (
    alert_id        UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id         UUID    NOT NULL REFERENCES goals(goal_id) ON DELETE CASCADE,
    user_id         UUID    NOT NULL,
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trigger_value   NUMERIC(12,4),
    message         TEXT,
    acknowledged_at TIMESTAMPTZ
);

CREATE INDEX idx_goal_alerts_user ON goal_alerts(user_id, triggered_at DESC);
CREATE INDEX idx_goal_alerts_unack ON goal_alerts(user_id) WHERE acknowledged_at IS NULL;


-- AI-generated correlations and recommendations, cached for dashboard display
CREATE TABLE insights (
    insight_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    insight_type    insight_type    NOT NULL,
    title           TEXT            NOT NULL,
    body            TEXT            NOT NULL,
    metric_a        TEXT,           -- Primary metric (e.g. 'sleep_efficiency_pct')
    metric_b        TEXT,           -- Secondary metric (e.g. 'hrv_rmssd_ms')
    correlation_r   NUMERIC(4,3),   -- Pearson r if correlation type
    p_value         NUMERIC(8,6),
    data_points     INTEGER,        -- n observations used
    valid_from      DATE,
    valid_until     DATE,           -- Cache expiry — regenerate when stale
    is_dismissed    BOOLEAN         NOT NULL DEFAULT FALSE,
    dismissed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE insights IS 'Pre-computed AI insights. Refreshed nightly. Invalidated on new data ingestion.';

CREATE INDEX idx_insights_user ON insights(user_id, created_at DESC) WHERE is_dismissed = FALSE;


-- ============================================================
-- SECTION 10: SYSTEM & OPERATIONS
-- ============================================================

-- Async job queue for wearable syncs, backfills, document parses, exports
CREATE TABLE ingestion_jobs (
    job_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        REFERENCES users(user_id) ON DELETE SET NULL,
    source          data_source,
    job_type        job_type    NOT NULL,
    status          job_status  NOT NULL DEFAULT 'queued',
    priority        SMALLINT    NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    payload         JSONB       NOT NULL DEFAULT '{}',
    result          JSONB,
    error_message   TEXT,
    attempts        SMALLINT    NOT NULL DEFAULT 0,
    max_attempts    SMALLINT    NOT NULL DEFAULT 3,
    queued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    next_retry_at   TIMESTAMPTZ
);

COMMENT ON TABLE ingestion_jobs IS 'Persistent job queue. Workers poll by (status, next_retry_at). Dead-letter jobs retained for debugging.';

CREATE INDEX idx_ingestion_jobs_worker ON ingestion_jobs(status, priority, next_retry_at)
    WHERE status IN ('queued', 'failed');
CREATE INDEX idx_ingestion_jobs_user ON ingestion_jobs(user_id, job_type, queued_at DESC);


-- Immutable audit log — partitioned quarterly, never hard-deleted
CREATE TABLE audit_log (
    audit_id    UUID            NOT NULL DEFAULT gen_random_uuid(),
    user_id     UUID,           -- Affected user. Set to NULL on GDPR deletion.
    action_by   UUID,           -- User performing the action (may differ for admin actions)
    table_name  TEXT            NOT NULL,
    record_id   UUID            NOT NULL,
    action      audit_action    NOT NULL,
    old_values  JSONB,          -- PII stripped on GDPR deletion
    new_values  JSONB,
    ip_address  INET,
    user_agent  TEXT,
    request_id  UUID,           -- Distributed trace ID from API layer
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (audit_id, created_at)
) PARTITION BY RANGE (created_at);

COMMENT ON TABLE audit_log IS 'Immutable audit trail. Rows never hard-deleted. PII anonymized on GDPR deletion.';

CREATE TABLE audit_log_2024_q1 PARTITION OF audit_log FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE audit_log_2024_q2 PARTITION OF audit_log FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE audit_log_2024_q3 PARTITION OF audit_log FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE audit_log_2024_q4 PARTITION OF audit_log FOR VALUES FROM ('2024-10-01') TO ('2025-01-01');
CREATE TABLE audit_log_2025_q1 PARTITION OF audit_log FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE audit_log_2025_q2 PARTITION OF audit_log FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE audit_log_2025_q3 PARTITION OF audit_log FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE audit_log_2025_q4 PARTITION OF audit_log FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE audit_log_2026_q1 PARTITION OF audit_log FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
CREATE TABLE audit_log_2026_q2 PARTITION OF audit_log FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');
CREATE TABLE audit_log_2026_q3 PARTITION OF audit_log FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');
CREATE TABLE audit_log_2026_q4 PARTITION OF audit_log FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');

CREATE INDEX idx_audit_log_user ON audit_log(user_id, created_at DESC);
CREATE INDEX idx_audit_log_record ON audit_log(table_name, record_id);
CREATE INDEX idx_audit_log_action_by ON audit_log(action_by, created_at DESC);


-- GDPR/CCPA deletion requests with 30-day grace period
CREATE TABLE deletion_requests (
    request_id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID    NOT NULL REFERENCES users(user_id),
    requested_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    grace_period_ends_at    TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days',
    status                  TEXT    NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending','processing','completed','canceled')),
    completed_at            TIMESTAMPTZ,
    tables_deleted          TEXT[]  DEFAULT '{}'
);

CREATE INDEX idx_deletion_requests_status ON deletion_requests(status, grace_period_ends_at)
    WHERE status = 'pending';


-- GDPR data portability export requests
CREATE TABLE data_export_requests (
    export_id           UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID    NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    requested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status              TEXT    NOT NULL DEFAULT 'queued'
                                CHECK (status IN ('queued','processing','ready','downloaded','expired')),
    format              TEXT    NOT NULL DEFAULT 'json' CHECK (format IN ('json','csv')),
    s3_key              TEXT,   -- Signed download URL (temporary object)
    expires_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    file_size_bytes     BIGINT
);


-- ============================================================
-- SECTION 11: ROW-LEVEL SECURITY
-- ============================================================

-- Enable RLS on all user-data tables.
-- The API layer sets app.current_user_id at connection time from the validated JWT.

ALTER TABLE users                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences        ENABLE ROW LEVEL SECURITY;
ALTER TABLE oauth_identities        ENABLE ROW LEVEL SECURITY;
ALTER TABLE connected_devices       ENABLE ROW LEVEL SECURITY;
ALTER TABLE wearable_daily          ENABLE ROW LEVEL SECURITY;
ALTER TABLE wearable_sleep          ENABLE ROW LEVEL SECURITY;
ALTER TABLE wearable_activities     ENABLE ROW LEVEL SECURITY;
ALTER TABLE blood_panels            ENABLE ROW LEVEL SECURITY;
ALTER TABLE blood_markers           ENABLE ROW LEVEL SECURITY;
ALTER TABLE dexa_scans              ENABLE ROW LEVEL SECURITY;
ALTER TABLE dexa_regions            ENABLE ROW LEVEL SECURITY;
ALTER TABLE dexa_bone_density       ENABLE ROW LEVEL SECURITY;
ALTER TABLE epigenetic_tests        ENABLE ROW LEVEL SECURITY;
ALTER TABLE epigenetic_organ_ages   ENABLE ROW LEVEL SECURITY;
ALTER TABLE lifting_sessions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE lifting_sets            ENABLE ROW LEVEL SECURITY;
ALTER TABLE measurements            ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_metrics          ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_metric_entries   ENABLE ROW LEVEL SECURITY;
ALTER TABLE supplements             ENABLE ROW LEVEL SECURITY;
ALTER TABLE supplement_logs         ENABLE ROW LEVEL SECURITY;
ALTER TABLE nutrition_logs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE mood_journal            ENABLE ROW LEVEL SECURITY;
ALTER TABLE menstrual_cycles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE doctor_visits           ENABLE ROW LEVEL SECURITY;
ALTER TABLE photos                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents               ENABLE ROW LEVEL SECURITY;
ALTER TABLE goals                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE goal_alerts             ENABLE ROW LEVEL SECURITY;
ALTER TABLE insights                ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_jobs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE deletion_requests       ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_export_requests    ENABLE ROW LEVEL SECURITY;


-- Accounts RLS (multi-tenant isolation)
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY account_member_isolation ON accounts
    USING (account_id IN (
        SELECT account_id FROM users 
        WHERE user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid
    ))
    WITH CHECK (account_id IN (
        SELECT account_id FROM users 
        WHERE user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid
    ));

-- Generic RLS policy for tables with user_id column.
-- The API sets: SET LOCAL app.current_user_id = '<uuid>';

CREATE POLICY user_isolation ON users
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON user_preferences
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON oauth_identities
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON connected_devices
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON wearable_daily
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON wearable_sleep
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON wearable_activities
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON blood_panels
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON blood_markers
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON dexa_scans
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON dexa_regions
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON dexa_bone_density
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON epigenetic_tests
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON epigenetic_organ_ages
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON lifting_sessions
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON lifting_sets
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON measurements
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON custom_metrics
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON custom_metric_entries
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON supplements
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON supplement_logs
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON nutrition_logs
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON mood_journal
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON menstrual_cycles
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON doctor_visits
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON photos
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON documents
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON goals
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON goal_alerts
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON insights
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON ingestion_jobs
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON deletion_requests
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);

CREATE POLICY user_isolation ON data_export_requests
    USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);
    WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid);


-- ============================================================
-- SECTION 12: AUDIT TRIGGER FUNCTION
-- ============================================================
-- Attach to any user-data table to capture mutations automatically.

CREATE OR REPLACE FUNCTION audit_mutation()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    v_record_id  TEXT;
    v_action     audit_action;
    v_pk_column  TEXT := TG_ARGV[0];  -- PK column name passed as trigger argument
    v_row        JSONB;
    v_user_id    UUID := NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid;
    v_request_id UUID := NULLIF(current_setting('app.request_id', TRUE), '')::uuid;
BEGIN
    -- Extract the record PK from the appropriate row
    IF TG_OP = 'DELETE' THEN
        v_row := row_to_json(OLD)::jsonb;
        v_action := 'DELETE';
    ELSE
        v_row := row_to_json(NEW)::jsonb;
        v_action := TG_OP::audit_action;
    END IF;
    
    v_record_id := v_row ->> v_pk_column;

    INSERT INTO audit_log(user_id, action_by, table_name, record_id, action, old_values, new_values, request_id)
    VALUES (
        v_user_id,
        v_user_id,
        TG_TABLE_NAME,
        v_record_id::uuid,
        v_action,
        CASE WHEN TG_OP IN ('UPDATE','DELETE') THEN row_to_json(OLD)::jsonb END,
        CASE WHEN TG_OP IN ('INSERT','UPDATE') THEN row_to_json(NEW)::jsonb END,
        v_request_id
    );

    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;

-- Attach audit triggers to all user-data tables
-- Pass the PK column name as the first argument
CREATE TRIGGER audit_users AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('user_id');
CREATE TRIGGER audit_blood_panels AFTER INSERT OR UPDATE OR DELETE ON blood_panels
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('panel_id');
CREATE TRIGGER audit_blood_markers AFTER INSERT OR UPDATE OR DELETE ON blood_markers
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('marker_id');
CREATE TRIGGER audit_dexa_scans AFTER INSERT OR UPDATE OR DELETE ON dexa_scans
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('scan_id');
CREATE TRIGGER audit_epigenetic_tests AFTER INSERT OR UPDATE OR DELETE ON epigenetic_tests
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('test_id');
CREATE TRIGGER audit_documents AFTER INSERT OR UPDATE OR DELETE ON documents
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('document_id');
CREATE TRIGGER audit_lifting_sessions AFTER INSERT OR UPDATE OR DELETE ON lifting_sessions
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('session_id');
CREATE TRIGGER audit_supplements AFTER INSERT OR UPDATE OR DELETE ON supplements
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('supplement_id');
CREATE TRIGGER audit_goals AFTER INSERT OR UPDATE OR DELETE ON goals
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('goal_id');
CREATE TRIGGER audit_deletion_requests AFTER INSERT OR UPDATE OR DELETE ON deletion_requests
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('request_id');
CREATE TRIGGER audit_connected_devices AFTER INSERT OR UPDATE OR DELETE ON connected_devices
    FOR EACH ROW EXECUTE FUNCTION audit_mutation('device_id');


-- ============================================================
-- SECTION 13: SEED DATA — BIOMARKER DICTIONARY
-- ============================================================
-- Source: Quest Diagnostics blood work sample + standard clinical panels
-- 82 markers across all major categories

INSERT INTO biomarker_dictionary
    (canonical_name, display_name, category, subcategory, canonical_unit, common_units, aliases,
     optimal_low, optimal_high, normal_low, normal_high, sex_specific_ranges, sort_order)
VALUES

-- ── METABOLIC / CMP ──────────────────────────────────────────
('glucose',              'Glucose',                    'metabolic',   'CMP', 'mg/dL',   ARRAY['mg/dL','mmol/L'],
 ARRAY['glucose','blood glucose','serum glucose','GLUC','fasting glucose'],
 70, 90, 65, 99, FALSE, 10),

('bun',                  'BUN (Urea Nitrogen)',         'metabolic',   'CMP', 'mg/dL',   ARRAY['mg/dL'],
 ARRAY['BUN','urea nitrogen','blood urea nitrogen','urea nitrogen BUN'],
 7, 20, 7, 25, FALSE, 20),

('creatinine',           'Creatinine',                 'kidney',      'CMP', 'mg/dL',   ARRAY['mg/dL','μmol/L','umol/L'],
 ARRAY['creatinine','serum creatinine','CREAT'],
 0.7, 1.0, 0.60, 1.24, TRUE, 30),

('egfr',                 'eGFR',                       'kidney',      'CMP', 'mL/min/1.73m²', ARRAY['mL/min/1.73m²'],
 ARRAY['eGFR','estimated GFR','glomerular filtration rate','EGFR'],
 90, NULL, 60, NULL, FALSE, 40),

('bun_creatinine_ratio', 'BUN/Creatinine Ratio',       'kidney',      'CMP', 'ratio',   ARRAY['ratio','calc'],
 ARRAY['BUN/creatinine ratio','BUN:creatinine'],
 10, 20, 6, 22, FALSE, 50),

('sodium',               'Sodium',                     'electrolytes','CMP', 'mmol/L',  ARRAY['mmol/L','mEq/L'],
 ARRAY['sodium','sodium serum','Na','serum sodium'],
 136, 142, 135, 146, FALSE, 60),

('potassium',            'Potassium',                  'electrolytes','CMP', 'mmol/L',  ARRAY['mmol/L','mEq/L'],
 ARRAY['potassium','serum potassium','K','K+'],
 3.5, 4.5, 3.5, 5.3, FALSE, 70),

('chloride',             'Chloride',                   'electrolytes','CMP', 'mmol/L',  ARRAY['mmol/L','mEq/L'],
 ARRAY['chloride','serum chloride','Cl'],
 98, 107, 98, 110, FALSE, 80),

('carbon_dioxide',       'Carbon Dioxide (CO₂)',       'electrolytes','CMP', 'mmol/L',  ARRAY['mmol/L','mEq/L'],
 ARRAY['carbon dioxide','CO2','bicarbonate','bicarb','HCO3'],
 22, 29, 20, 32, FALSE, 90),

('calcium',              'Calcium',                    'minerals',    'CMP', 'mg/dL',   ARRAY['mg/dL','mmol/L'],
 ARRAY['calcium','serum calcium','Ca','total calcium'],
 8.8, 10.0, 8.6, 10.3, FALSE, 100),

('protein_total',        'Total Protein',              'metabolic',   'CMP', 'g/dL',    ARRAY['g/dL'],
 ARRAY['total protein','protein total','protein serum'],
 6.4, 7.6, 6.1, 8.1, FALSE, 110),

('albumin',              'Albumin',                    'liver',       'CMP', 'g/dL',    ARRAY['g/dL'],
 ARRAY['albumin','serum albumin','ALB'],
 4.0, 5.0, 3.6, 5.1, FALSE, 120),

('globulin',             'Globulin',                   'liver',       'CMP', 'g/dL',    ARRAY['g/dL'],
 ARRAY['globulin','serum globulin','GLOB'],
 2.0, 3.5, 1.9, 3.7, FALSE, 130),

('albumin_globulin_ratio','A/G Ratio',                 'liver',       'CMP', 'ratio',   ARRAY['ratio','calc'],
 ARRAY['albumin globulin ratio','A/G ratio','AG ratio'],
 1.3, 2.0, 1.0, 2.5, FALSE, 140),

('bilirubin_total',      'Bilirubin, Total',           'liver',       'CMP', 'mg/dL',   ARRAY['mg/dL','μmol/L'],
 ARRAY['bilirubin total','total bilirubin','TBILI','T. bili'],
 0.1, 1.0, 0.2, 1.2, FALSE, 150),

('alkaline_phosphatase', 'Alkaline Phosphatase (ALP)', 'liver',       'CMP', 'U/L',     ARRAY['U/L','IU/L'],
 ARRAY['alkaline phosphatase','ALP','alk phos','ALK PHOS'],
 40, 90, 36, 130, FALSE, 160),

('ast',                  'AST (SGOT)',                  'liver',       'CMP', 'U/L',     ARRAY['U/L'],
 ARRAY['AST','SGOT','aspartate aminotransferase','aspartate transaminase'],
 10, 30, 10, 40, FALSE, 170),

('alt',                  'ALT (SGPT)',                  'liver',       'CMP', 'U/L',     ARRAY['U/L'],
 ARRAY['ALT','SGPT','alanine aminotransferase','alanine transaminase'],
 7, 30, 9, 46, FALSE, 180),

-- ── METABOLIC STANDALONE ─────────────────────────────────────
('hba1c',                'Hemoglobin A1c',              'metabolic',   NULL,  '%',       ARRAY['%'],
 ARRAY['HbA1c','hemoglobin A1c','HbA1C','glycated hemoglobin','A1c','A1C'],
 NULL, 5.4, NULL, 5.7, FALSE, 200),

('magnesium',            'Magnesium',                   'minerals',    NULL,  'mg/dL',   ARRAY['mg/dL','mmol/L'],
 ARRAY['magnesium','serum magnesium','Mg','Mg2+'],
 1.8, 2.3, 1.5, 2.5, FALSE, 210),

('uric_acid',            'Uric Acid',                   'metabolic',   NULL,  'mg/dL',   ARRAY['mg/dL','mmol/L','μmol/L'],
 ARRAY['uric acid','urate','serum urate','serum uric acid'],
 NULL, 6.0, 4.0, 8.0, TRUE, 220),

('ggt',                  'GGT',                         'liver',       NULL,  'U/L',     ARRAY['U/L'],
 ARRAY['GGT','gamma-glutamyl transferase','gamma GT','GGTP','gamma-glutamyl transpeptidase'],
 NULL, 25, 3, 70, TRUE, 230),

('amylase',              'Amylase',                     'pancreatic',  NULL,  'U/L',     ARRAY['U/L'],
 ARRAY['amylase','serum amylase','AMY'],
 21, 85, 21, 101, FALSE, 240),

('lipase',               'Lipase',                      'pancreatic',  NULL,  'U/L',     ARRAY['U/L'],
 ARRAY['lipase','serum lipase','LPS'],
 7, 45, 7, 60, FALSE, 250),

-- ── INFLAMMATION ─────────────────────────────────────────────
('hs_crp',               'hs-CRP',                      'inflammation',NULL,  'mg/L',    ARRAY['mg/L','mg/dL'],
 ARRAY['hs-CRP','high sensitivity CRP','hsCRP','C-reactive protein','CRP','HS CRP'],
 NULL, 1.0, NULL, 1.0, FALSE, 300),

('homocysteine',         'Homocysteine',                'cardiovascular',NULL,'umol/L',  ARRAY['umol/L','μmol/L','μM'],
 ARRAY['homocysteine','HCY','total homocysteine','plasma homocysteine'],
 NULL, 9.0, NULL, 12.9, FALSE, 310),

-- ── THYROID ──────────────────────────────────────────────────
('tsh',                  'TSH',                         'thyroid',     'Thyroid Panel','mIU/L',ARRAY['mIU/L','μIU/mL','uIU/mL'],
 ARRAY['TSH','thyroid stimulating hormone','thyrotropin'],
 0.5, 2.5, 0.40, 4.50, FALSE, 400),

('t4_free',              'Free T4 (FT4)',                'thyroid',     'Thyroid Panel','ng/dL', ARRAY['ng/dL','pmol/L'],
 ARRAY['free T4','FT4','T4 free','thyroxine free','free thyroxine'],
 1.0, 1.6, 0.8, 1.8, FALSE, 410),

('t3_free',              'Free T3 (FT3)',                'thyroid',     'Thyroid Panel','pg/mL', ARRAY['pg/mL','pmol/L'],
 ARRAY['free T3','FT3','T3 free','triiodothyronine free','free triiodothyronine'],
 3.0, 4.0, 2.3, 4.2, FALSE, 420),

('thyroglobulin_ab',     'Thyroglobulin Antibodies',    'thyroid',     'Thyroid Panel','IU/mL', ARRAY['IU/mL'],
 ARRAY['thyroglobulin antibodies','anti-TG','TgAb','antithyroglobulin'],
 NULL, 1, NULL, 1, FALSE, 430),

('tpo_ab',               'Thyroid Peroxidase Antibodies','thyroid',    'Thyroid Panel','IU/mL', ARRAY['IU/mL'],
 ARRAY['thyroid peroxidase antibodies','TPO antibodies','anti-TPO','TPOAb'],
 NULL, 9, NULL, 9, FALSE, 440),

-- ── HORMONES ─────────────────────────────────────────────────
('testosterone_total',   'Testosterone, Total',         'hormones',    NULL,  'ng/dL',   ARRAY['ng/dL','nmol/L'],
 ARRAY['testosterone total','total testosterone','testosterone','T total','TESTO'],
 NULL, NULL, NULL, NULL, TRUE, 500),

('testosterone_free',    'Testosterone, Free',          'hormones',    NULL,  'pg/mL',   ARRAY['pg/mL','pmol/L','ng/dL'],
 ARRAY['free testosterone','testosterone free','T free','free T'],
 NULL, NULL, NULL, NULL, TRUE, 510),

('estradiol',            'Estradiol (E2)',               'hormones',    NULL,  'pg/mL',   ARRAY['pg/mL','pmol/L'],
 ARRAY['estradiol','E2','17-beta estradiol','oestradiol'],
 NULL, NULL, NULL, NULL, TRUE, 520),

('shbg',                 'SHBG',                        'hormones',    NULL,  'nmol/L',  ARRAY['nmol/L','μg/dL'],
 ARRAY['SHBG','sex hormone binding globulin','sex hormone-binding globulin'],
 NULL, NULL, NULL, NULL, TRUE, 530),

('dhea_s',               'DHEA-S',                      'hormones',    NULL,  'mcg/dL',  ARRAY['mcg/dL','μg/dL','μmol/L','umol/L'],
 ARRAY['DHEA-S','DHEA sulfate','dehydroepiandrosterone sulfate','DHEAS'],
 NULL, NULL, NULL, NULL, TRUE, 540),

('fsh',                  'FSH',                         'hormones',    NULL,  'mIU/mL',  ARRAY['mIU/mL','IU/L'],
 ARRAY['FSH','follicle stimulating hormone'],
 NULL, NULL, NULL, NULL, TRUE, 550),

('lh',                   'LH',                          'hormones',    NULL,  'mIU/mL',  ARRAY['mIU/mL','IU/L'],
 ARRAY['LH','luteinizing hormone','luteinising hormone'],
 NULL, NULL, NULL, NULL, TRUE, 560),

('prolactin',            'Prolactin',                   'hormones',    NULL,  'ng/mL',   ARRAY['ng/mL','μg/L'],
 ARRAY['prolactin','PRL','serum prolactin'],
 2.0, 15.0, 2.0, 18.0, TRUE, 570),

('cortisol',             'Cortisol (AM)',                'hormones',    NULL,  'mcg/dL',  ARRAY['mcg/dL','μg/dL','nmol/L'],
 ARRAY['cortisol','cortisol total','serum cortisol','AM cortisol'],
 8.0, 18.0, 4.0, 22.0, FALSE, 580),

('insulin',              'Insulin (Fasting)',            'hormones',    NULL,  'uIU/mL',  ARRAY['uIU/mL','μIU/mL','pmol/L'],
 ARRAY['insulin','fasting insulin','serum insulin'],
 NULL, 6.0, NULL, 18.4, FALSE, 590),

('leptin',               'Leptin',                      'hormones',    NULL,  'ng/mL',   ARRAY['ng/mL'],
 ARRAY['leptin','serum leptin'],
 NULL, NULL, NULL, NULL, TRUE, 600),

('psa_total',            'PSA, Total',                  'hormones',    NULL,  'ng/mL',   ARRAY['ng/mL'],
 ARRAY['PSA','PSA total','prostate specific antigen','total PSA'],
 NULL, 2.5, NULL, 4.0, TRUE, 610),

-- ── HEMATOLOGY / CBC ─────────────────────────────────────────
('wbc',                  'White Blood Cell Count',      'hematology',  'CBC', 'Thousand/uL', ARRAY['Thousand/uL','10^3/μL','K/μL'],
 ARRAY['WBC','white blood cell count','leukocyte count','white cells'],
 4.5, 8.0, 3.8, 10.8, FALSE, 700),

('rbc',                  'Red Blood Cell Count',        'hematology',  'CBC', 'Million/uL', ARRAY['Million/uL','10^6/μL','M/μL'],
 ARRAY['RBC','red blood cell count','erythrocyte count','red cells'],
 NULL, NULL, NULL, NULL, TRUE, 710),

('hemoglobin',           'Hemoglobin',                  'hematology',  'CBC', 'g/dL',    ARRAY['g/dL'],
 ARRAY['hemoglobin','Hgb','Hb','haemoglobin'],
 NULL, NULL, NULL, NULL, TRUE, 720),

('hematocrit',           'Hematocrit',                  'hematology',  'CBC', '%',        ARRAY['%','L/L'],
 ARRAY['hematocrit','Hct','PCV','packed cell volume','haematocrit'],
 NULL, NULL, NULL, NULL, TRUE, 730),

('mcv',                  'MCV',                         'hematology',  'CBC', 'fL',       ARRAY['fL'],
 ARRAY['MCV','mean corpuscular volume','mean cell volume'],
 82, 95, 80, 100, FALSE, 740),

('mch',                  'MCH',                         'hematology',  'CBC', 'pg',       ARRAY['pg'],
 ARRAY['MCH','mean corpuscular hemoglobin','mean cell hemoglobin'],
 27, 32, 27, 33, FALSE, 750),

('mchc',                 'MCHC',                        'hematology',  'CBC', 'g/dL',     ARRAY['g/dL'],
 ARRAY['MCHC','mean corpuscular hemoglobin concentration'],
 32, 36, 32, 36, FALSE, 760),

('rdw',                  'RDW',                         'hematology',  'CBC', '%',        ARRAY['%'],
 ARRAY['RDW','red cell distribution width','red blood cell distribution width'],
 11, 14, 11, 15, FALSE, 770),

('platelets',            'Platelet Count',              'hematology',  'CBC', 'Thousand/uL', ARRAY['Thousand/uL','10^3/μL'],
 ARRAY['platelet count','platelets','PLT','thrombocyte count'],
 150, 350, 140, 400, FALSE, 780),

('mpv',                  'MPV',                         'hematology',  'CBC', 'fL',       ARRAY['fL'],
 ARRAY['MPV','mean platelet volume'],
 7.5, 12.0, 7.5, 12.5, FALSE, 790),

('neutrophils_abs',      'Absolute Neutrophils',        'hematology',  'CBC', 'cells/uL', ARRAY['cells/uL','10^3/μL'],
 ARRAY['absolute neutrophils','ANC','neutrophil count','NEUT absolute'],
 1500, 7000, 1500, 7800, FALSE, 800),

('lymphocytes_abs',      'Absolute Lymphocytes',        'hematology',  'CBC', 'cells/uL', ARRAY['cells/uL'],
 ARRAY['absolute lymphocytes','ALC','lymphocyte count','LYMPH absolute'],
 850, 3500, 850, 3900, FALSE, 810),

('monocytes_abs',        'Absolute Monocytes',          'hematology',  'CBC', 'cells/uL', ARRAY['cells/uL'],
 ARRAY['absolute monocytes','AMC','monocyte count','MONO absolute'],
 200, 800, 200, 950, FALSE, 820),

('eosinophils_abs',      'Absolute Eosinophils',        'hematology',  'CBC', 'cells/uL', ARRAY['cells/uL'],
 ARRAY['absolute eosinophils','AEC','eosinophil count','EOS absolute'],
 15, 400, 15, 500, FALSE, 830),

('basophils_abs',        'Absolute Basophils',          'hematology',  'CBC', 'cells/uL', ARRAY['cells/uL'],
 ARRAY['absolute basophils','ABC','basophil count','BASO absolute'],
 0, 100, 0, 200, FALSE, 840),

('neutrophils_pct',      'Neutrophils %',               'hematology',  'CBC', '%',        ARRAY['%'],
 ARRAY['neutrophils %','neutrophil percent','NEUT%','neutrophils percent'],
 50, 70, NULL, NULL, FALSE, 850),

('lymphocytes_pct',      'Lymphocytes %',               'hematology',  'CBC', '%',        ARRAY['%'],
 ARRAY['lymphocytes %','lymphocyte percent','LYMPH%'],
 20, 40, NULL, NULL, FALSE, 860),

('monocytes_pct',        'Monocytes %',                 'hematology',  'CBC', '%',        ARRAY['%'],
 ARRAY['monocytes %','monocyte percent','MONO%'],
 2, 10, NULL, NULL, FALSE, 870),

('eosinophils_pct',      'Eosinophils %',               'hematology',  'CBC', '%',        ARRAY['%'],
 ARRAY['eosinophils %','eosinophil percent','EOS%'],
 1, 4, NULL, NULL, FALSE, 880),

('basophils_pct',        'Basophils %',                 'hematology',  'CBC', '%',        ARRAY['%'],
 ARRAY['basophils %','basophil percent','BASO%'],
 0, 1, NULL, NULL, FALSE, 890),

-- ── IRON / NUTRITION ─────────────────────────────────────────
('iron',                 'Iron, Total',                 'nutrition',   'Iron Panel','mcg/dL',ARRAY['mcg/dL','μmol/L'],
 ARRAY['iron','serum iron','iron total','Fe','iron serum'],
 70, 170, 50, 195, TRUE, 900),

('tibc',                 'TIBC',                        'nutrition',   'Iron Panel','mcg/dL',ARRAY['mcg/dL'],
 ARRAY['TIBC','total iron binding capacity','iron binding capacity','IBC'],
 250, 370, 250, 425, FALSE, 910),

('iron_saturation',      'Iron Saturation',             'nutrition',   'Iron Panel','%',   ARRAY['%'],
 ARRAY['iron saturation','% saturation','transferrin saturation','iron sat','% iron sat'],
 20, 45, 20, 48, TRUE, 920),

('ferritin',             'Ferritin',                    'nutrition',   'Iron Panel','ng/mL',ARRAY['ng/mL','μg/L'],
 ARRAY['ferritin','serum ferritin'],
 NULL, NULL, NULL, NULL, TRUE, 930),

-- ── VITAMINS ─────────────────────────────────────────────────
('vitamin_d_25oh',       'Vitamin D, 25-OH',            'vitamins',    NULL,  'ng/mL',   ARRAY['ng/mL','nmol/L'],
 ARRAY['vitamin D','25-OH vitamin D','25-hydroxyvitamin D','Vit D','vitamin D 25-OH'],
 40, 80, 30, 100, FALSE, 1000),

('methylmalonic_acid',   'Methylmalonic Acid (MMA)',    'vitamins',    NULL,  'nmol/L',  ARRAY['nmol/L'],
 ARRAY['methylmalonic acid','MMA','methyl malonic acid'],
 55, 260, 55, 335, FALSE, 1010),

('zinc',                 'Zinc',                        'minerals',    NULL,  'mcg/dL',  ARRAY['mcg/dL','μmol/L'],
 ARRAY['zinc','serum zinc','Zn'],
 70, 115, 60, 130, FALSE, 1020),

-- ── HEAVY METALS ─────────────────────────────────────────────
('mercury',              'Mercury, Blood',              'heavy_metals',NULL,  'mcg/L',   ARRAY['mcg/L','μg/L'],
 ARRAY['mercury','blood mercury','Hg','mercury blood'],
 NULL, 10, NULL, 10, FALSE, 1100),

('lead',                 'Lead, Venous',                'heavy_metals',NULL,  'mcg/dL',  ARRAY['mcg/dL','μg/dL'],
 ARRAY['lead','blood lead','lead venous','Pb','lead serum'],
 NULL, 3.5, NULL, 3.5, FALSE, 1110),

-- ── LIPIDS ───────────────────────────────────────────────────
('cholesterol_total',    'Total Cholesterol',           'lipids',      'Lipid Panel','mg/dL',ARRAY['mg/dL','mmol/L'],
 ARRAY['cholesterol total','total cholesterol','CHOL','cholesterol'],
 NULL, 180, NULL, 200, FALSE, 1200),

('hdl_cholesterol',      'HDL Cholesterol',             'lipids',      'Lipid Panel','mg/dL',ARRAY['mg/dL','mmol/L'],
 ARRAY['HDL','HDL cholesterol','HDL-C','high density lipoprotein'],
 NULL, NULL, NULL, NULL, TRUE, 1210),

('ldl_cholesterol',      'LDL Cholesterol',             'lipids',      'Lipid Panel','mg/dL',ARRAY['mg/dL','mmol/L'],
 ARRAY['LDL','LDL cholesterol','LDL-C','low density lipoprotein','LDL-CHOLESTEROL'],
 NULL, 100, NULL, 100, FALSE, 1220),

('triglycerides',        'Triglycerides',               'lipids',      'Lipid Panel','mg/dL',ARRAY['mg/dL','mmol/L'],
 ARRAY['triglycerides','TG','TGL','trigs'],
 NULL, 100, NULL, 150, FALSE, 1230),

('chol_hdl_ratio',       'Cholesterol/HDL Ratio',       'lipids',      'Lipid Panel','ratio',ARRAY['ratio','calc'],
 ARRAY['chol/HDL ratio','cholesterol to HDL ratio','CHOL/HDLC ratio'],
 NULL, 3.5, NULL, 5.0, FALSE, 1240),

('non_hdl_cholesterol',  'Non-HDL Cholesterol',         'lipids',      'Lipid Panel','mg/dL',ARRAY['mg/dL'],
 ARRAY['non-HDL cholesterol','non HDL cholesterol','non-HDL-C'],
 NULL, 130, NULL, 130, FALSE, 1250),

('apolipoprotein_b',     'ApoB',                        'lipids',      'Cardio IQ','mg/dL',ARRAY['mg/dL'],
 ARRAY['ApoB','apolipoprotein B','apoB','apo B'],
 NULL, 80, NULL, 90, FALSE, 1260),

('lipoprotein_a',        'Lipoprotein(a)',               'lipids',      'Cardio IQ','nmol/L',ARRAY['nmol/L','mg/dL'],
 ARRAY['Lp(a)','lipoprotein a','lipoprotein(a)','LP(A)'],
 NULL, 75, NULL, 75, FALSE, 1270),

-- ── LIPIDS ADVANCED (Cardio IQ / NMR) ───────────────────────
('ldl_particle_number',  'LDL Particle Number',         'lipids_advanced','Cardio IQ','nmol/L',ARRAY['nmol/L'],
 ARRAY['LDL-P','LDL particle number','LDL particles'],
 NULL, 1000, NULL, 1138, FALSE, 1300),

('ldl_small',            'LDL Small Particles',         'lipids_advanced','Cardio IQ','nmol/L',ARRAY['nmol/L'],
 ARRAY['small LDL','LDL small','small dense LDL'],
 NULL, 100, NULL, 142, FALSE, 1310),

('ldl_medium',           'LDL Medium Particles',        'lipids_advanced','Cardio IQ','nmol/L',ARRAY['nmol/L'],
 ARRAY['medium LDL','LDL medium'],
 NULL, 200, NULL, 215, FALSE, 1320),

('hdl_large',            'HDL Large Particles',         'lipids_advanced','Cardio IQ','nmol/L',ARRAY['nmol/L'],
 ARRAY['large HDL','HDL large'],
 6729, NULL, 6729, NULL, TRUE, 1330),

('ldl_peak_size',        'LDL Peak Size',               'lipids_advanced','Cardio IQ','Angstrom',ARRAY['Angstrom','Å'],
 ARRAY['LDL peak size','LDL size'],
 222.9, NULL, 222.9, NULL, FALSE, 1340),

-- ── FATTY ACIDS (OmegaCheck) ─────────────────────────────────
('omega3_total',         'Omega-3 Total',               'fatty_acids', 'OmegaCheck','% by wt',ARRAY['% by wt','%'],
 ARRAY['omega-3 total','total omega-3','EPA+DPA+DHA'],
 5.5, NULL, 5.5, NULL, FALSE, 1400),

('epa',                  'EPA',                         'fatty_acids', 'OmegaCheck','% by wt',ARRAY['% by wt','%'],
 ARRAY['EPA','eicosapentaenoic acid'],
 0.5, 2.0, 0.2, 2.3, FALSE, 1410),

('dpa',                  'DPA',                         'fatty_acids', 'OmegaCheck','% by wt',ARRAY['% by wt','%'],
 ARRAY['DPA','docosapentaenoic acid'],
 0.8, 1.8, 0.8, 1.8, FALSE, 1420),

('dha',                  'DHA',                         'fatty_acids', 'OmegaCheck','% by wt',ARRAY['% by wt','%'],
 ARRAY['DHA','docosahexaenoic acid'],
 2.0, 5.0, 1.4, 5.1, FALSE, 1430),

('omega6_total',         'Omega-6 Total',               'fatty_acids', 'OmegaCheck','% by wt',ARRAY['% by wt','%'],
 ARRAY['omega-6 total','total omega-6'],
 NULL, 35.0, NULL, NULL, FALSE, 1440),

('arachidonic_acid',     'Arachidonic Acid (AA)',       'fatty_acids', 'OmegaCheck','% by wt',ARRAY['% by wt','%'],
 ARRAY['arachidonic acid','AA','arachidonate'],
 8.6, 15.6, 8.6, 15.6, FALSE, 1450),

('linoleic_acid',        'Linoleic Acid (LA)',          'fatty_acids', 'OmegaCheck','% by wt',ARRAY['% by wt','%'],
 ARRAY['linoleic acid','LA'],
 18.6, 29.5, 18.6, 29.5, FALSE, 1460),

('omega6_omega3_ratio',  'Omega-6/Omega-3 Ratio',       'fatty_acids', 'OmegaCheck','ratio',ARRAY['ratio'],
 ARRAY['omega-6/omega-3 ratio','omega6:omega3','n-6:n-3 ratio'],
 3.7, 8.0, 3.7, 14.4, FALSE, 1470),

('aa_epa_ratio',         'AA/EPA Ratio',                'fatty_acids', 'OmegaCheck','ratio',ARRAY['ratio'],
 ARRAY['AA/EPA ratio','arachidonic acid/EPA ratio','arachidonic acid EPA ratio'],
 3.0, 15.0, 3.7, 40.7, FALSE, 1480),

-- ── IMMUNOLOGY ───────────────────────────────────────────────
('rheumatoid_factor',    'Rheumatoid Factor',           'immunology',  NULL,  'IU/mL',   ARRAY['IU/mL'],
 ARRAY['rheumatoid factor','RF','RA factor'],
 NULL, 14, NULL, 14, FALSE, 1500),

('ana_screen',           'ANA Screen',                  'immunology',  NULL,  'qualitative',ARRAY['qualitative'],
 ARRAY['ANA','antinuclear antibodies','ANA screen','ANA IFA'],
 NULL, NULL, NULL, NULL, FALSE, 1510);


-- ============================================================
-- SECTION 14: SEED DATA — EXERCISE DICTIONARY (top 20)
-- ============================================================
INSERT INTO exercise_dictionary (canonical_name, display_name, primary_muscle, equipment, category, aliases)
VALUES
('barbell_squat',         'Barbell Squat',          'quadriceps',   'barbell',    'compound', ARRAY['squat','back squat','BB squat']),
('barbell_deadlift',      'Deadlift',                'hamstrings',   'barbell',    'compound', ARRAY['deadlift','conventional deadlift','DL']),
('barbell_bench_press',   'Barbell Bench Press',     'chest',        'barbell',    'compound', ARRAY['bench press','flat bench','BB bench']),
('barbell_overhead_press','Overhead Press',          'shoulders',    'barbell',    'compound', ARRAY['OHP','shoulder press','military press','overhead press']),
('barbell_row',           'Barbell Row',             'back',         'barbell',    'compound', ARRAY['bent over row','BB row','barbell bent over row']),
('pull_up',               'Pull-up',                 'back',         'bodyweight', 'compound', ARRAY['pull-up','pullup','chin-up','chinup']),
('dumbbell_curl',         'Dumbbell Curl',           'biceps',       'dumbbell',   'isolation',ARRAY['DB curl','dumbbell bicep curl','arm curl']),
('tricep_pushdown',       'Tricep Pushdown',         'triceps',      'cable',      'isolation',ARRAY['cable pushdown','tricep cable pushdown']),
('leg_press',             'Leg Press',               'quadriceps',   'machine',    'compound', ARRAY['machine leg press','leg press machine']),
('romanian_deadlift',     'Romanian Deadlift',       'hamstrings',   'barbell',    'compound', ARRAY['RDL','Romanian deadlift','stiff leg deadlift']),
('hip_thrust',            'Hip Thrust',              'glutes',       'barbell',    'compound', ARRAY['barbell hip thrust','glute bridge','hip thrusts']),
('incline_bench_press',   'Incline Bench Press',     'chest',        'barbell',    'compound', ARRAY['incline press','incline BB press']),
('cable_row',             'Cable Row',               'back',         'cable',      'compound', ARRAY['seated cable row','low row','cable seated row']),
('lat_pulldown',          'Lat Pulldown',            'back',         'machine',    'compound', ARRAY['lat pull down','pulldown']),
('face_pull',             'Face Pull',               'shoulders',    'cable',      'isolation',ARRAY['facepull','cable face pull']),
('plank',                 'Plank',                   'core',         'bodyweight', 'isolation',ARRAY['plank hold']),
('dumbbell_row',          'Dumbbell Row',            'back',         'dumbbell',   'compound', ARRAY['DB row','single arm row','one arm row']),
('calf_raise',            'Calf Raise',              'calves',       'machine',    'isolation',ARRAY['standing calf raise','calf raises']),
('lateral_raise',         'Lateral Raise',           'shoulders',    'dumbbell',   'isolation',ARRAY['side raise','DB lateral raise','shoulder raise']),
('chest_fly',             'Chest Fly',               'chest',        'dumbbell',   'isolation',ARRAY['dumbbell fly','pec fly','DB fly','cable fly']);


-- ============================================================
-- END OF SCHEMA
-- ============================================================
-- Alembic migration note:
--   This file is the canonical reference for the initial migration.
--   Run: alembic revision --autogenerate -m "initial_schema"
--   All subsequent changes MUST go through Alembic migrations.
-- ============================================================
