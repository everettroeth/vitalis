# QA-SCHEMA-REVIEW.md — Data Architecture Critique

**Reviewer:** QA Director (Opus)
**Date:** 2026-02-22
**Documents Reviewed:** PLAN.md, SCHEMA.md, schema.sql
**Verdict:** SIGNIFICANT ISSUES — schema must NOT be locked until Critical and High-priority items are resolved.

---

## Critical Issues (must fix before locking)

### C1. Audit trigger `audit_mutation()` is fundamentally broken

The `record_id` extraction logic is wrong in all three branches:

```sql
-- INSERT branch:
v_record_id := (NEW.*)::text::json->>'user_id';   -- Sets to user_id (wrong — that's not the PK)
BEGIN
    v_record_id := (row_to_json(NEW))->>'panel_id'; -- Only works for blood_panels table
EXCEPTION WHEN OTHERS THEN NULL;                    -- Silently swallows failure
END;

-- UPDATE and DELETE branches:
-- v_record_id is NEVER reassigned. It retains whatever garbage value
-- was left from a prior trigger invocation or is NULL.
```

**Impact:** Every audit_log row has an incorrect or NULL `record_id`. The audit trail is useless for compliance. This is a regulatory and debugging disaster.

**Fix:** Use `TG_ARGV` to pass the PK column name per-table, or use a dynamic lookup:
```sql
v_record_id := (row_to_json(CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END))
    ->> TG_ARGV[0]; -- Pass PK column name as trigger argument
```

Also: **the trigger is defined but never attached to any table.** There are no `CREATE TRIGGER ... EXECUTE FUNCTION audit_mutation()` statements anywhere in the SQL. The entire audit system is inert.

### C2. RLS policies are read-only — writes are completely unprotected

Every RLS policy uses only `USING` (controls SELECT/UPDATE/DELETE visibility) but has no `WITH CHECK` clause:

```sql
CREATE POLICY user_isolation ON wearable_daily
    USING (user_id = current_setting('app.current_user_id', TRUE)::uuid);
```

**Impact:** Any authenticated user can INSERT rows with **any** `user_id`, or UPDATE the `user_id` column to hijack another user's data. This is a complete data isolation failure.

**Fix:** Every policy needs `WITH CHECK`:
```sql
CREATE POLICY user_isolation ON wearable_daily
    USING (user_id = current_setting('app.current_user_id', TRUE)::uuid)
    WITH CHECK (user_id = current_setting('app.current_user_id', TRUE)::uuid);
```

### C3. Partitioned wearable tables have no FK to `users` — orphan data on deletion

`wearable_daily`, `wearable_sleep`, `wearable_activities` declare `user_id UUID NOT NULL` but have **no REFERENCES clause** and **no ON DELETE CASCADE**. When a user is deleted via the GDPR flow, this data will remain as orphans forever.

**Impact:** GDPR deletion is incomplete. User health data persists after account deletion.

**Fix:** PostgreSQL 15+ supports FKs from partitioned tables. Add:
```sql
user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE
```
Alternatively, ensure the GDPR deletion job explicitly DELETEs from these tables by user_id before deleting the user row.

### C4. Missing FK constraints create referential integrity gaps

The following FK relationships are declared in SCHEMA.md but absent from schema.sql:

| Table | Column | Expected FK | Actual |
|-------|--------|-------------|--------|
| `blood_panels` | `document_id` | `→ documents(document_id)` | No FK, just a bare UUID column |
| `dexa_scans` | `document_id` | `→ documents(document_id)` | No FK |
| `epigenetic_tests` | `document_id` | `→ documents(document_id)` | No FK |

**Impact:** Documents can be deleted while panels/scans still reference them. Orphaned references will cause application errors.

### C5. `deletion_requests` FK prevents user deletion

```sql
CREATE TABLE deletion_requests (
    user_id UUID NOT NULL REFERENCES users(user_id),  -- No ON DELETE clause
```

Default FK behavior is `NO ACTION` / `RESTRICT`. The GDPR deletion flow hard-deletes the user row, but `deletion_requests` still references it. The DELETE will fail with a FK violation.

**Fix:** Either `ON DELETE SET NULL` (and make user_id nullable) or `ON DELETE CASCADE`. Since the request record is needed for compliance, SET NULL with a snapshot of user info is preferred.

### C6. `current_setting()` cast to UUID will crash on empty string

```sql
USING (user_id = current_setting('app.current_user_id', TRUE)::uuid)
```

The `TRUE` parameter means "missing_ok" — returns empty string `''` instead of erroring when not set. But `''::uuid` throws:
```
ERROR: invalid input syntax for type uuid: ""
```

**Impact:** Any query against an RLS-protected table without the session variable set will throw a hard error instead of returning empty results. This will crash background workers, migration scripts, monitoring queries, and any connection that forgets to SET the variable.

**Fix:** Use `NULLIF`:
```sql
USING (user_id = NULLIF(current_setting('app.current_user_id', TRUE), '')::uuid)
```
When NULL, `user_id = NULL` evaluates to FALSE (no rows), which is the safe default.

### C7. `accounts` table has no RLS and no access control

SCHEMA.md says accounts has "account-level RLS instead of user-level" but **no RLS policy is defined** on `accounts`. The table has `ENABLE ROW LEVEL SECURITY` also **missing** from the SQL.

**Impact:** Any authenticated API user can `SELECT * FROM accounts` and read all billing info, subscription tiers, and Stripe customer IDs.

**Fix:** Enable RLS and add a policy that restricts access to the user's own account:
```sql
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY account_isolation ON accounts
    USING (account_id IN (
        SELECT account_id FROM users
        WHERE user_id = current_setting('app.current_user_id', TRUE)::uuid
    ));
```

---

## Normalization Issues

### N1. Imperial-only storage in DEXA and lifting tables

`dexa_scans` stores `height_in`, `weight_lbs`, `total_fat_lbs`, etc. `lifting_sets` stores `weight_lbs`. There is no canonical metric storage and no `value_canonical` equivalent like blood_markers has.

**Impact:** International users see unnecessary conversion on every read. If canonical units change later, you need a data migration of every row. Blood markers got this right with dual storage — DEXA and lifting did not.

**Fix:** Either add `_canonical` columns in metric units, or rename columns to be unit-agnostic (`total_fat_mass`, `weight`) with a separate unit column and conversion service.

### N2. `epigenetic_organ_ages.chronological_age` duplicated from parent

Copied "for convenience" from `epigenetic_tests`. Classic denormalization that drifts on parent updates.

**Impact:** If a user corrects their chronological_age on the test header, the organ_ages rows become stale. `delta_years` is then also wrong.

**Fix:** Compute `chronological_age` and `delta_years` via JOIN at query time, or enforce consistency via a trigger.

### N3. `doctor_visit_panels` join table has no `user_id` — breaks RLS

This join table has no `user_id` column and no RLS policy. An attacker could enumerate all visit_id/panel_id relationships across all users.

**Fix:** Add `user_id` column, FK, and an RLS policy. Or rely on the fact that visits and panels already have RLS — but the join table itself is still exposed.

### N4. Redundant `user_id` denormalization without consistency enforcement

Tables like `dexa_regions`, `dexa_bone_density`, `epigenetic_organ_ages`, `lifting_sets`, `supplement_logs`, `custom_metric_entries`, `goal_alerts` have `user_id` denormalized for RLS. But there is **no CHECK or trigger** ensuring the denormalized `user_id` matches the parent's `user_id`.

**Impact:** A bug in the application layer could insert a `dexa_region` with user_id=A into a scan owned by user_id=B. RLS would then show this region to user A while hiding the parent scan. Data corruption that's invisible until someone audits.

**Fix:** Add CHECK constraints or triggers to enforce parent-child user_id consistency.

---

## Performance Concerns

### P1. `raw_data` JSONB columns will dominate storage

At 100K users × 365 days × ~2 sources = 73M rows/year in `wearable_daily` alone, each carrying a full API response in `raw_data` (typically 2–10 KB). That's 146 GB–730 GB per year just for raw wearable JSON.

**Impact:** Table scans become I/O bound. VACUUM takes hours. Backup sizes balloon. The `raw_data` column is rarely queried but always fetched unless excluded.

**Fix:** Move `raw_data` to a separate `wearable_daily_raw` table with a 1:1 FK. Or store raw responses in S3 with an S3 key reference. Or use TOAST compression (automatic but still in-table).

### P2. Blood marker trend queries require a JOIN for dates

The most common query pattern — "show me glucose over time" — requires:
```sql
SELECT bm.value_canonical, bp.collected_at
FROM blood_markers bm
JOIN blood_panels bp ON bm.panel_id = bp.panel_id
WHERE bm.user_id = ? AND bm.biomarker_id = ?
ORDER BY bp.collected_at DESC;
```

The index on `blood_markers(user_id, biomarker_id)` finds the markers, but the ORDER BY is on the joined table.

**Fix:** Denormalize `collected_at` into `blood_markers` and index `(user_id, biomarker_id, collected_at DESC)`.

### P3. `ingestion_jobs` is not partitioned and will grow unbounded

Every sync, parse, and export creates a job row that's never deleted. At 100K users with daily syncs from 2 sources = 200K jobs/day = 73M jobs/year.

**Impact:** Worker polling queries `WHERE status IN ('queued', 'failed')` will scan the partial index, but the table's overall size will slow VACUUM, ANALYZE, and pg_dump.

**Fix:** Partition by `queued_at` (monthly). Archive or delete completed/dead_letter jobs older than 90 days.

### P4. No covering indexes for dashboard queries

The home dashboard needs "last 30 days of daily data" but the query fetches 20+ columns. The index `(user_id, date DESC)` finds the rows but then does 30 random I/O lookups for the heap pages.

**Fix:** Consider a covering index for the most-queried columns:
```sql
CREATE INDEX ON wearable_daily (user_id, date DESC)
    INCLUDE (resting_hr_bpm, hrv_rmssd_ms, steps, sleep_score, readiness_score);
```

### P5. Missing partition for pre-2023 historical data

Partitions start at 2023. Users backfilling Garmin data from 2020–2022 will get:
```
ERROR: no partition of relation "wearable_daily" found for row
```

**Fix:** Add partitions back to 2018 (or a reasonable backfill horizon), or add a `DEFAULT` partition as a catch-all.

### P6. GIN index on `aliases` doesn't support the common query pattern

To match a lab report name to a biomarker, the query would be:
```sql
SELECT * FROM biomarker_dictionary WHERE 'Glucose' = ANY(aliases);
```

GIN indexes on TEXT[] support `@>` (array contains) but NOT the `= ANY()` pattern efficiently.

**Fix:** Use `WHERE aliases @> ARRAY['Glucose']` in queries, which the GIN index does support. Document this pattern requirement for all consumers.

### P7. Audit log write amplification

Every single INSERT/UPDATE/DELETE on ~30 tables fires a trigger that writes to `audit_log`, doubling write load. On high-frequency tables like `wearable_daily` (bulk ingestion of 365 rows per backfill per source), this creates massive write amplification.

**Fix:** Consider: (a) async audit via logical replication/CDC instead of synchronous triggers, (b) skip audit on bulk ingestion paths, (c) batch audit entries.

---

## Security & RLS Issues

### S1. Worker role needs careful RLS bypass

SCHEMA.md mentions `vitalis_worker` can do "cross-user job management." But the SQL defines identical RLS policies for all roles. If workers use the `vitalis_api` role with a system user_id, they can only see their own jobs.

**Fix:** Define separate policies for the worker role:
```sql
CREATE POLICY worker_access ON ingestion_jobs
    FOR ALL TO vitalis_worker USING (TRUE);
```

### S2. No database roles are created

The SQL creates no roles (`vitalis_api`, `vitalis_worker`, `vitalis_admin`, `vitalis_readonly`). RLS is meaningless without role-based policy attachment. Currently all policies apply to all roles by default.

**Fix:** Add:
```sql
CREATE ROLE vitalis_api LOGIN;
CREATE ROLE vitalis_worker LOGIN;
CREATE ROLE vitalis_admin LOGIN BYPASSRLS;
CREATE ROLE vitalis_readonly LOGIN;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES TO vitalis_api;
GRANT SELECT ON ALL TABLES TO vitalis_readonly;
-- etc.
```

### S3. `ingestion_jobs.payload` and `result` JSONB may contain PII after user deletion

When a user is deleted, `ingestion_jobs.user_id` is SET NULL, but `payload` (which may contain tokens, API responses with names, health data) and `result` remain intact.

**Fix:** The GDPR deletion job must scrub `payload` and `result` JSONB fields, or hard-delete completed jobs for the user.

### S4. No encryption-at-rest strategy for PII columns

SCHEMA.md says `date_of_birth` is "encrypted at application layer" and tokens are "AES-256 encrypted." But:
- No encryption key management strategy is documented
- Per-user encryption (promised in PLAN.md) is not reflected anywhere in the schema
- If the app-layer encryption key is shared across all users, a key compromise exposes all users' PII

**Fix:** Document the key management strategy. Consider per-user encryption keys derived from a master key + user_id (envelope encryption via AWS KMS or similar).

### S5. `photos.s3_key` and `documents.s3_key` stored as plaintext

If someone gains read access to these tables (SQL injection, backup theft), they can construct direct S3 URLs.

**Fix:** Ensure S3 bucket policies require signed URLs and never allow public access. Document that S3 keys are internal references, not public URLs. Consider encrypting S3 keys at rest.

---

## Multi-Tenancy Issues

### M1. Family plan data sharing is entirely application-level

Household members on the same account share no data at the DB level. The SCHEMA.md says the API must "check account membership before allowing cross-user read access." This means the API must `SET app.current_user_id` to the **target** user, not the requesting user, to bypass RLS.

**Impact:** This is a massive foot-gun. A single API bug that sets the wrong user_id exposes arbitrary user data. And since there's no audit distinction between "user viewed their own data" and "family member viewed their data," you can't detect misuse.

**Fix:** Add an `app.current_account_id` session variable and create account-level read policies for family plans:
```sql
CREATE POLICY family_read ON wearable_daily FOR SELECT
    USING (user_id IN (
        SELECT u.user_id FROM users u
        WHERE u.account_id = current_setting('app.current_account_id')::uuid
    ));
```

### M2. No query-level resource limits

A single user with 5 years of hourly CGM data (future) could issue a `SELECT *` that returns millions of rows, consuming all connection pool slots.

**Fix:** Enforce `statement_timeout` per role, and paginate all list endpoints at the API layer. Add `LIMIT` guardrails in the RLS policies or views.

### M3. Shared dictionaries have no protection against corruption

`biomarker_dictionary` and `exercise_dictionary` have no RLS and no write protection. The `vitalis_api` role can INSERT/UPDATE/DELETE dictionary entries, affecting all users.

**Fix:** Make dictionaries read-only for `vitalis_api`:
```sql
REVOKE INSERT, UPDATE, DELETE ON biomarker_dictionary FROM vitalis_api;
GRANT INSERT, UPDATE, DELETE ON biomarker_dictionary TO vitalis_admin;
```

---

## Migration & Evolution Concerns

### E1. ENUMs are migration landmines

PostgreSQL ENUMs cannot have values removed, only added. The schema defines 14 ENUM types. Some problems:

- `data_source`: Adding a new wearable requires `ALTER TYPE data_source ADD VALUE 'new_source'`. This can't be done inside a transaction (PG < 16). It contradicts the "adapter pattern" promise of zero-core-change extensibility.
- `activity_type`: What happens when a user does "bouldering" or "paddleboarding"? Another migration.
- `measurement_metric`: Adding "grip_strength" needs a migration.
- `biomarker_category`: If clinical taxonomy changes, you can't rename or remove categories.

**Fix:** Replace ENUMs with TEXT + CHECK constraints, or TEXT with a lookup table. TEXT + lookup table is the most evolvable:
```sql
CREATE TABLE data_sources (source TEXT PRIMARY KEY, display_name TEXT, is_active BOOLEAN);
```

### E2. Column-per-metric design in `wearable_daily` is rigid

Adding a new metric (e.g., blood glucose from CGM, strain score from WHOOP, readiness from Apple Watch) requires `ALTER TABLE ADD COLUMN` on a partitioned table with 37M+ rows per partition.

**Impact:** Schema changes on huge partitioned tables require long-running migrations with table locks.

**Fix:** Consider an EAV (entity-attribute-value) overflow pattern for less common metrics, or a JSONB `extended_metrics` column for non-core fields.

### E3. No schema version table

There's no way to query the current schema version at runtime. Alembic handles migrations but the application has no way to verify it's running against the expected schema version.

**Fix:** Add:
```sql
CREATE TABLE schema_info (key TEXT PRIMARY KEY, value TEXT);
INSERT INTO schema_info VALUES ('version', '1.0'), ('applied_at', NOW()::text);
```

### E4. Lock timeout of 5s will fail on partition-level DDL

SCHEMA.md specifies `SET lock_timeout = '5s'` for migrations. But `ALTER TABLE ADD COLUMN` on a partitioned table acquires an ACCESS EXCLUSIVE lock on the parent, which requires all active queries to finish first. At 100K users with constant queries, 5 seconds is almost never enough.

**Fix:** Use `pg_repack` or concurrent migration strategies. For adding columns, use the pattern: add column with DEFAULT in PG14+ (instant, no rewrite).

---

## Biomarker Dictionary Issues

### B1. No age-specific reference ranges

Testosterone, DHEA-S, IGF-1, and many hormones have dramatically different normal ranges by age decade. The dictionary only supports sex-specific ranges (`optimal_low_male`, `optimal_high_male`).

**Impact:** A 25-year-old and a 65-year-old male will see the same "optimal" range for testosterone, making the goal/alert system useless for one of them.

**Fix:** Add an `age_ranges` JSONB column or a separate `biomarker_ranges` table:
```sql
CREATE TABLE biomarker_ranges (
    range_id UUID PRIMARY KEY,
    biomarker_id UUID REFERENCES biomarker_dictionary,
    sex TEXT, -- 'male', 'female', NULL for universal
    age_low SMALLINT, age_high SMALLINT,
    optimal_low NUMERIC(12,4), optimal_high NUMERIC(12,4),
    normal_low NUMERIC(12,4), normal_high NUMERIC(12,4)
);
```

### B2. Missing commonly-ordered biomarkers

Notable gaps in the 82-marker seed:
- **Vitamin B12** (serum B12 directly — MMA is only a proxy)
- **Folate / Folic Acid**
- **IGF-1** (critical for longevity tracking)
- **Cystatin C** (better kidney function marker than creatinine)
- **Fibrinogen** (cardiovascular risk)
- **Selenium**
- **Copper**
- **Vitamin B6**
- **GGT** has no subcategory (should be liver panel)
- **Omega-3 Index** (distinct from omega-3 total)
- **ApoA-I** (HDL particle marker)
- **Direct LDL** (measured, not calculated)
- **VLDL**

### B3. Alias matching is case-sensitive

The `aliases TEXT[]` column and GIN index do exact-match lookups. Lab reports vary wildly in casing: "GLUCOSE", "Glucose", "glucose", "Gluc.". The AI parser must lowercase-normalize before lookup, but this isn't enforced at the schema level.

**Fix:** Store aliases as lowercase, enforce via CHECK constraint or trigger, and require the parser to lowercase input before matching.

### B4. No LOINC codes in seed data

The `loinc_code` column exists but is NULL for all 82 seeded markers. LOINC codes are essential for EHR interoperability and future FHIR integration. This is technical debt being pushed forward.

### B5. No mechanism to handle one-lab-name mapping to multiple biomarkers

Some lab names are ambiguous. "Testosterone" could mean total or free. "Cholesterol" could mean total or LDL. The dictionary assumes a 1:1 mapping from alias to biomarker, but the GIN index will return multiple matches.

**Fix:** Document the disambiguation strategy. Consider a priority/specificity score on aliases.

---

## GDPR/CCPA Compliance Gaps

### G1. `documents` table has contradictory deletion policy

- `documents` comment: "Never hard-deleted"
- `documents.s3_key` comment: "Documents archived permanently even after account deletion"
- GDPR deletion flow: lists `documents` as a table that gets hard-deleted

**Impact:** Either documents are retained (GDPR violation) or deleted (losing the comment's promise of permanence). Can't have both.

**Fix:** On GDPR deletion: hard-delete the `documents` row and the S3 object. Remove the "never hard-deleted" comment. User consent withdrawal overrides archival preferences. If legal hold is needed, document it as a separate exception flow.

### G2. No consent tracking table

PLAN.md mentions community benchmarks (opt-in anonymous comparison), AI coaching, and doctor sharing. None of these have a consent tracking mechanism in the schema.

**Fix:** Add:
```sql
CREATE TABLE user_consents (
    consent_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    consent_type TEXT NOT NULL, -- 'benchmarks', 'ai_coaching', 'doctor_sharing', 'marketing'
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    ip_address INET,
    UNIQUE (user_id, consent_type)
);
```

### G3. No data processing activity log

GDPR Article 30 requires a record of processing activities. The audit_log captures data mutations but not analytical processing (AI correlation generation, report creation, benchmark aggregation).

### G4. Audit log anonymization on deletion is underspecified

SCHEMA.md says "old_values/new_values stripped of email/DOB fields." But the JSONB structure varies by table. A generic PII stripping function needs to know every field name that could contain PII across all tables. This is fragile and will miss new PII fields added later.

**Fix:** Define a PII field registry (table_name → [pii_field_names]) and use it in the anonymization function. Or strip all `old_values`/`new_values` entirely on deletion (safer, simpler).

### G5. Export download link has no access control documented

`data_export_requests.s3_key` stores the key to a file containing ALL of a user's health data. The schema doesn't indicate how access is controlled. If S3 presigned URLs are used, they're time-limited but can be shared.

---

## Missing Tables or Columns

### MT1. No `sessions` / `refresh_tokens` table

PLAN.md specifies "JWT tokens, refresh tokens, session management" but there's no table to track active sessions, revoke refresh tokens, or enforce concurrent session limits.

### MT2. No `notifications` table

Goals can fire alerts (`goal_alerts`), but there's no general notification delivery system for: sync failures, parse completions, insight generation, subscription expiration, etc.

### MT3. No `api_keys` table

PLAN.md Phase 7 mentions "Public API" and "Partner API." No table exists for API key management, scoping, or rate limit tracking.

### MT4. No intraday / high-frequency data table

The wearable schema handles daily summaries, sleep sessions, and activities. But CGM (continuous glucose monitoring from Dexcom/Levels — listed as a v2 adapter) produces readings every 5 minutes = 288/day. No table exists for this granularity.

**Fix:** Add a `wearable_intraday` or `time_series_samples` table, heavily partitioned, for sub-daily time series.

### MT5. No push notification subscription table

PWA push notifications require storing push subscription endpoints (Web Push API). No table exists for this.

### MT6. Missing `updated_at` on `nutrition_logs`

Has `deleted_at` for soft delete but no `updated_at` to track modifications. If a user corrects their calorie count, there's no timestamp of the edit.

### MT7. No file hash / checksum on `documents`

No way to detect duplicate PDF uploads. Two uploads of the same file create two documents rows and potentially duplicate parsed data.

**Fix:** Add `file_hash TEXT` (SHA-256 of uploaded file content) and a unique constraint `(user_id, file_hash)`.

---

## Edge Cases

### EC1. Duplicate imports

**PDF uploads:** No deduplication. Same PDF uploaded twice → parsed twice → double entries in `blood_markers`. The `(panel_id, biomarker_id)` combination isn't unique, so the same glucose reading from the same panel can exist twice.

**Wearable syncs:** Better — `(user_id, date, source)` unique constraint catches daily duplicates. But activities only dedup when `source_activity_id IS NOT NULL`.

**Fix:** Add `file_hash` to documents. Add unique constraint on `(panel_id, biomarker_id)` for blood_markers (or `(panel_id, raw_name)` to handle unmapped markers).

### EC2. Partial PDF parses

If AI extracts 8 of 10 markers from a blood work PDF, there's no mechanism to:
- Record which markers were expected but not found
- Flag the parse as "partial" vs "complete" (parse_status is binary: parsed or failed)
- Allow the user to manually add the missing 2 markers and link them to the same document

**Fix:** Add `parse_status = 'partial'` to the enum. Add a `markers_expected` / `markers_found` count to `documents` or `parse_result` JSONB.

### EC3. Timezone handling is inconsistent

- `wearable_daily.date` is a bare DATE — represents a calendar day but in which timezone? The user's timezone (from `user_preferences.timezone`)? UTC? The device's timezone?
- `wearable_sleep.sleep_date` is documented as "date the sleep ended (morning of)" — but morning in which timezone?
- Partition boundaries are based on UTC. A user in UTC+12 who sleeps on "Jan 1 local time" has a sleep record dated Jan 1, but it may fall in the Dec 31 UTC partition.

**Impact:** Users crossing timezones (travel) will see data misattributed to wrong dates. Wearable APIs typically return data in the user's local timezone, so storing as UTC DATE can shift the calendar day.

**Fix:** Document and enforce that `date` columns represent the user's local calendar date (as reported by the device/source). Add a comment to this effect on every DATE column. Consider storing `timezone_at_record` for travel-aware analysis.

### EC4. Null values vs. zero vs. not measured

Most wearable columns are nullable. But there's no distinction between:
- `hrv_rmssd_ms = NULL` → sensor not worn / metric not available from this source
- `hrv_rmssd_ms = 0` → measured as zero (clinically impossible for HRV)
- `hrv_rmssd_ms = NULL` → API returned null / data point missing for this day

Dashboard aggregations like `AVG(hrv_rmssd_ms)` silently skip NULLs, which is correct. But users see gaps in their charts with no explanation.

**Fix:** Consider a `data_completeness` JSONB or bitmask column indicating which metrics were available from the source for that day.

### EC5. Device switching creates trend discontinuities

If a user switches from Garmin to Apple Watch:
- Historical data stays under `source = 'garmin'`
- New data arrives under `source = 'apple_health'`
- Trend charts filtered by source show incomplete histories
- Trend charts combining sources show apples-to-oranges comparisons (Garmin HRV algorithm ≠ Apple HRV algorithm)

The schema supports multi-source data but has no concept of a "preferred" or "canonical" reading for each metric on each day.

**Fix:** Consider a materialized view or nightly job that produces a `wearable_daily_canonical` table with one "best" value per metric per day, with source attribution.

### EC6. Historical backfill before 2023 fails

Partitions only exist for 2023–2028. A Garmin user with data from 2020 (which is realistic — Garmin has years of history) will get partition-not-found errors.

**Fix:** Add partitions back to at least 2018. Or add a DEFAULT partition as a catch-all (with a note to re-partition later).

### EC7. Blood markers with NULL `biomarker_id` are invisible to trend queries

If AI parsing fails to match a lab name to the dictionary, `biomarker_id` is NULL. These markers won't appear in any trend query that filters by `biomarker_id`. There's no workflow to surface, review, and resolve unmatched markers.

**Fix:** Add an index and API endpoint for unmatched markers:
```sql
CREATE INDEX idx_blood_markers_unmatched ON blood_markers(user_id, created_at DESC)
    WHERE biomarker_id IS NULL;
```
Build a UI queue for manual biomarker matching.

### EC8. `lifting_sets.reps` allows 0

`CHECK (reps BETWEEN 0 AND 999)` — zero reps is never valid for a completed set. Even failed attempts are typically tracked as a note, not reps=0.

**Fix:** Change to `CHECK (reps BETWEEN 1 AND 999)`. Represent failed sets with a boolean column or notes.

---

## Recommendations (prioritized)

### Priority 1 — Must fix before schema lock

| # | Issue | Effort |
|---|-------|--------|
| 1 | **C1:** Rewrite `audit_mutation()` with dynamic PK extraction; attach triggers to all tables | Medium |
| 2 | **C2:** Add `WITH CHECK` to all RLS policies | Low |
| 3 | **C3:** Add FK + CASCADE on partitioned wearable tables, or ensure GDPR job handles them explicitly | Low |
| 4 | **C4:** Add missing FK constraints (document_id references) | Low |
| 5 | **C5:** Fix `deletion_requests` FK to allow user deletion | Low |
| 6 | **C6:** Use `NULLIF` in RLS policy expressions | Low |
| 7 | **C7:** Add RLS to `accounts` table | Low |
| 8 | **S2:** Create database roles and assign permissions | Medium |

### Priority 2 — Fix before Phase 2 (Backend)

| # | Issue | Effort |
|---|-------|--------|
| 9 | **E1:** Replace ENUMs with TEXT + lookup tables (at least `data_source`, `activity_type`, `measurement_metric`) | High |
| 10 | **EC6:** Add pre-2023 partitions for historical backfill | Low |
| 11 | **P2:** Denormalize `collected_at` into `blood_markers` | Low |
| 12 | **G1:** Resolve documents deletion policy contradiction | Low |
| 13 | **N4:** Add parent-child user_id consistency enforcement | Medium |
| 14 | **MT7:** Add `file_hash` to documents for duplicate detection | Low |
| 15 | **EC1:** Add unique constraint on `(panel_id, biomarker_id)` or `(panel_id, raw_name)` | Low |
| 16 | **MT1:** Add sessions/refresh_tokens table | Medium |

### Priority 3 — Fix before Phase 6 (Dogfood)

| # | Issue | Effort |
|---|-------|--------|
| 17 | **B1:** Add age-specific biomarker ranges | Medium |
| 18 | **B2:** Add missing biomarkers (B12, folate, IGF-1, etc.) | Low |
| 19 | **N1:** Add canonical metric storage for DEXA/lifting | Medium |
| 20 | **P1:** Extract `raw_data` JSONB to separate tables or S3 | High |
| 21 | **EC3:** Document and enforce timezone semantics on DATE columns | Low |
| 22 | **EC5:** Design canonical/reconciled daily metrics view | Medium |
| 23 | **M1:** Implement account-level RLS for family plans | Medium |

### Priority 4 — Fix before Phase 7 (Launch)

| # | Issue | Effort |
|---|-------|--------|
| 24 | **G2:** Add consent tracking table | Low |
| 25 | **MT2:** Add notifications table | Medium |
| 26 | **MT3:** Add API keys table | Low |
| 27 | **S3:** Scrub PII from ingestion_jobs on user deletion | Low |
| 28 | **P3:** Partition and archive ingestion_jobs | Medium |
| 29 | **P7:** Consider async audit via CDC | High |
| 30 | **MT4:** Design intraday time-series table for CGM | Medium |

---

## Summary Scorecard

| Category | Grade | Notes |
|----------|-------|-------|
| Table Coverage | **B+** | Covers 90% of PLAN.md. Missing sessions, notifications, API keys, intraday. |
| Data Integrity | **D** | Broken audit trigger, missing FKs, no parent-child user_id checks, no file dedup. |
| Security / RLS | **D** | Write-side RLS completely missing. No roles created. accounts table exposed. |
| Performance Design | **B** | Partitioning strategy is sound. Indexes are mostly right. raw_data bloat is a time bomb. |
| GDPR Compliance | **C** | Deletion flow exists but has FK bugs, contradictory policies, no consent tracking. |
| Biomarker Dictionary | **B-** | Good foundation, missing age ranges and several common markers. Alias matching fragile. |
| Evolvability | **C-** | ENUMs will cause pain by year 2. Column-per-metric is rigid. No schema versioning. |
| Multi-Tenancy | **C** | User isolation works (once RLS is fixed). Family sharing is fragile app-level only. |

**Overall: This schema is a strong draft with dangerous gaps in security and data integrity. The foundation is good — table design, partitioning strategy, and biomarker normalization show real thought. But the execution has critical bugs (audit trigger, RLS write policies, missing FKs) that would cause data corruption and security breaches in production. Fix the Priority 1 items, and this becomes a solid base for 20 years of health data.**
