# Vitalis — Strategic Build Order

**Principle:** Build the hardest, highest-value thing first. The lab parser is our moat.

---

## Phase 2: Lab PDF Parser Engine (NEXT — highest priority)

**Why first:** This is the #1 unmet need in the market. If Vitalis can reliably parse a Quest Diagnostics PDF and extract 50+ biomarkers automatically, we've already beaten every competitor. This is also the hardest technical challenge — solve it early.

### Deliverables
1. **Parser framework** — pluggable adapter pattern for different lab formats
2. **Quest Diagnostics parser** — most common US lab
3. **Labcorp parser** — second most common
4. **Generic parser** — AI-powered fallback for unknown formats
5. **Test suite** — 10+ real-world PDF fixtures per parser, with expected output
6. **Confidence scoring** — parser reports confidence per marker (0-1.0)
7. **Human review queue** — low-confidence parses flagged for user confirmation

### Architecture
```
PDF Upload → Format Detection → Router → Adapter → Extract → Normalize → Confidence Score → Store
                                  ↓
                          Unknown format?
                                  ↓
                          AI fallback parser (GPT-4V / Claude Vision)
                                  ↓
                          Human review queue
```

### Test Strategy
- Each parser has a `/tests/fixtures/` folder with real PDFs (anonymized)
- Each fixture has a corresponding `.expected.json` with exact expected output
- CI runs `pytest` — every marker must match expected values
- Coverage target: 95%+ marker extraction accuracy per supported format
- Regression tests: any bug fix adds a new fixture

---

## Phase 3: Wearable Data Sync

### Deliverables
1. **Garmin Connect adapter** — OAuth + daily sync (sleep, HRV, steps, activities, body battery)
2. **Apple Health adapter** — HealthKit import via device
3. **Oura adapter** — OAuth + API sync
4. **Sync scheduler** — background jobs, dedup, backfill
5. **Test suite** — mock API responses, sync state machine tests

### Priority: Garmin first (Ev uses it), then Apple Health (largest market), then Oura.

---

## Phase 4: Frontend Dashboard

### Deliverables
1. **Next.js app** with Vitalis design system (Quicksand, Lucide, sage palette)
2. **Onboarding wizard** — connect device → upload lab → first insight in 5 min
3. **Home dashboard** — today's snapshot, recent trends, insights
4. **Blood work view** — marker trends over time, reference ranges, status
5. **Sleep view** — nightly breakdown, HRV trends, quality score
6. **Body composition view** — DEXA trends, measurements
7. **Mobile PWA** — installable, offline-capable, push notifications

### Test Strategy
- Component tests (React Testing Library)
- E2E tests (Playwright) — onboarding flow, upload flow, navigation
- Visual regression tests (Chromatic or Percy)
- Accessibility audit (axe-core in CI)

---

## Phase 5: Intelligence Engine

### Deliverables
1. **Correlation engine** — find statistically significant relationships across domains
2. **Insight generator** — natural language explanations of patterns
3. **Anomaly detection** — flag unusual readings
4. **Goal tracking** — "improve HRV by 10%" with progress monitoring
5. **Notification system** — proactive alerts when something matters

---

## Phase 6: DEXA + Epigenetic Parsers

### Deliverables
1. **DexaFit PDF parser** + fixtures
2. **BodySpec PDF parser** + fixtures
3. **Hologic DICOM/PDF parser** + fixtures
4. **TruDiagnostic parser** + fixtures
5. **Elysium Index parser** + fixtures
6. **GrimAge / DunedinPACE parser** + fixtures
7. **Biological age dashboard** — unified view of all aging metrics

---

## Phase 7: Family + Enterprise

### Deliverables
1. **Household accounts** — shared dashboard, individual privacy controls
2. **Doctor/practitioner view** — read-only access to patient data
3. **Corporate wellness admin** — team dashboards, aggregate trends
4. **SSO (SAML/OIDC)** — enterprise auth
5. **HIPAA compliance** — BAA, encryption at rest, audit logs

---

## Testing Philosophy

Every phase follows this testing pyramid:
```
        ╱ E2E Tests ╲           (Playwright — critical paths)
       ╱─────────────╲
      ╱Integration Tests╲       (API + DB — real Supabase)
     ╱───────────────────╲
    ╱     Unit Tests       ╲    (parsers, utils, components)
   ╱─────────────────────────╲
  ╱      Parser Fixtures       ╲ (real PDFs → expected JSON)
 ╱─────────────────────────────╲
```

**CI rules:**
- All tests pass before merge
- New parser = minimum 10 fixtures
- Coverage never decreases
- E2E tests run nightly + on release
- Parser accuracy tracked as a metric (dashboard it)
