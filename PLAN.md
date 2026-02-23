# Vitalis — Master Build Plan

**Vision:** The personal health intelligence platform that replaces 10 apps with one beautiful, durable home for all your health data.
**Phase 1 Users:** Ev + Wife (dogfood)
**Phase 2 Users:** Mass distribution (SaaS product)
**Guiding Principle:** Build for scale from day one, but ship for two people first.

---

## Why This Wins

Most health apps are:
- Siloed (Garmin only talks to Garmin, Apple only to Apple)
- Ugly (clinical dashboards, not wellness experiences)
- Ephemeral (startups die, your data dies with them)
- Shallow (show you numbers, don't connect them)

Vitalis is:
- **Universal** — every wearable, every lab, every scan, one home
- **Beautiful** — earthy, calm, premium wellness aesthetic
- **Durable** — you own your data, export anytime, runs for decades
- **Intelligent** — cross-domain correlations no single app can see

---

## Architecture (Product-Grade from Day One)

```
┌─────────────────────────────────────────────┐
│          PWA + Mobile (React + Tailwind)     │
│   Installable · Offline-capable · Mobile-first│
├─────────────────────────────────────────────┤
│          API Gateway (FastAPI)               │
│   Auth · Rate Limiting · Multi-tenant        │
├──────────────┬──────────────────────────────┤
│  Ingestion   │  Analysis Engine             │
│  Service     │  Correlations · Anomalies    │
│  (pluggable  │  Reports · Insights          │
│   adapters)  │  Goal Tracking               │
├──────────────┴──────────────────────────────┤
│          PostgreSQL (multi-tenant)           │
│   Row-level security · Per-user encryption   │
├─────────────────────────────────────────────┤
│          Infrastructure                      │
│   Fly.io / Railway · S3 · Redis (queues)     │
│   Stripe (billing) · Resend (email)          │
└─────────────────────────────────────────────┘
```

### Key Architecture Shifts (Personal → Product)

| Decision | Personal | Product |
|----------|----------|---------|
| Database | SQLite | **PostgreSQL** (multi-tenant, row-level security) |
| Auth | Profile switcher | **Proper auth** (email/password, OAuth, magic link) |
| File storage | Local disk | **S3/R2** (scalable, per-user isolated) |
| Ingestion | Cron scripts | **Job queue** (Redis/BullMQ, retry, monitoring) |
| PDF parsing | Local LLM call | **Async worker** (queue → parse → confirm → insert) |
| Billing | N/A | **Stripe** (free tier + paid plans) |
| Onboarding | Manual | **Guided flow** (connect devices, import history) |
| Privacy | Household trust | **Per-user encryption**, HIPAA-awareness, data isolation |
| Export | Nice-to-have | **Mandatory** (regulatory, trust, portability) |
| API | Internal only | **Public API** (for integrations, partner apps) |

---

## Data Sources (Adapter Pattern)

Each source is a pluggable adapter. Adding new ones never touches core code.

### Launch Adapters (v1)
| Source | Method | Auto-sync |
|--------|--------|-----------|
| Garmin | Connect API (OAuth) | ✅ Daily |
| Apple Watch | Apple Health via iOS Shortcut or HealthKit web | ✅ Daily |
| Oura Ring | Oura Cloud API (OAuth) | ✅ Daily |
| WHOOP | WHOOP API (OAuth) | ✅ Daily |
| Blood Work (any lab) | PDF upload → AI parse | Manual |
| DEXA (any provider) | PDF upload → AI parse | Manual |
| Epigenetics (TruDiagnostic) | PDF upload → AI parse | Manual |
| Strong (lifting) | CSV import / API | Manual/Auto |
| Manual Entry | In-app forms | Manual |

### Future Adapters (v2+)
| Source | Method |
|--------|--------|
| Fitbit | API (OAuth) |
| Samsung Health | API |
| Continuous Glucose Monitor (Levels, Dexcom) | API |
| MyFitnessPal / Cronometer | API |
| Eight Sleep | API |
| Withings (smart scale) | API |
| Apple Health (direct HealthKit via native app) | Native SDK |

The adapter pattern means any developer (or agent) can add a new source without understanding the whole system.

---

## Feature Set

### Core (v1 — Launch)
1. **Multi-device wearable sync** — Garmin, Apple Watch, Oura, WHOOP
2. **AI-powered document ingestion** — blood work, DEXA, epigenetics PDFs
3. **Manual input system** — weight, BP, measurements, custom metrics
4. **Supplement & medication tracking** — log inputs, correlate with outcomes
5. **Biomarker goals & alerts** — set targets, visual status, trend warnings
6. **Progress photos** — timestamped, linked to scans, side-by-side
7. **Mood/energy/stress journal** — daily 1-tap rating
8. **Doctor visits & notes** — linked to relevant labs
9. **Menstrual cycle tracking** — correlates with all other metrics
10. **Cross-domain insights** — AI-generated correlations
11. **Annual health report** — auto-generated PDF
12. **Data export** — full CSV/JSON, one-click, always available
13. **Custom metrics** — define and track anything
14. **Household/family** — shared accounts with individual data isolation

### Growth (v2)
15. **AI health coach** — conversational analysis ("Why is my HRV dropping?")
16. **Doctor sharing** — generate reports to share with your physician
17. **Community benchmarks** — opt-in anonymous comparison (how do I compare to others my age?)
18. **Nutrition integration** — deeper meal tracking, macro correlations
19. **Guided protocols** — supplement stacks, sleep protocols with tracking
20. **Native mobile app** — iOS + Android (React Native)
21. **Partner API** — let other apps push data into Vitalis
22. **Wearable comparison** — "Your Garmin says X, your Oura says Y, here's what's likely true"

---

## Agent Team (Product Company)

| Agent | Role | Model | Active Phases |
|-------|------|-------|---------------|
| **CEO / Architect** | Product vision, system design, orchestration, final decisions | Opus | All |
| **QA Director** | Reviews every deliverable, enforces correctness, security review | Opus | All |
| **Brand Designer** | Visual identity, design system, UI/UX patterns, marketing assets | Sonnet | 0, 3, 7 |
| **Data Engineer** | Schema, migrations, data modeling, ingestion architecture, validation | Sonnet | 1, 2 |
| **Backend Engineer** | API, auth, integrations, file handling, job queues | Sonnet | 2, 3, 5 |
| **Frontend Engineer** | React PWA, design system implementation, all views, mobile UX | Sonnet | 3, 4 |
| **Analysis Engineer** | Correlations, anomaly detection, reports, insight generation | Sonnet | 4 |
| **Infra / DevOps Engineer** | Deployment, CI/CD, monitoring, backups, scaling | Sonnet | 5 |
| **Product Marketer** | Landing page, positioning, pricing, launch strategy | Sonnet | 7 |

---

## Build Phases

### Phase 0: Brand & Design System
**Goal:** Complete visual identity and component library before any UI code.
**Duration:** 1 session

**Deliverables:**
- [ ] Brand name finalization + logo concept direction
- [ ] Mood board (earthy, natural, calm — tans, sage greens, warm wood, cream)
- [ ] Color system:
  - Primary palette (earthy naturals)
  - Semantic colors (health status: thriving/watch/concern — NOT clinical red/yellow/green)
  - Dark mode variant
- [ ] Typography system (headings, body, data display, labels)
- [ ] Spacing, grid, and layout system (mobile-first, 4px base)
- [ ] Component library (Figma-level spec):
  - Metric cards, trend cards, alert cards
  - Charts (line, bar, radar, body comp visualization)
  - Forms (inputs, date pickers, sliders, 1-5 tap ratings)
  - Navigation (bottom tabs mobile, sidebar desktop)
  - Profile/account switcher
  - File drop zone with preview
  - Empty states, loading states, error states
  - Onboarding flow screens
- [ ] Icon style guide
- [ ] Motion/animation principles
- [ ] Dashboard layout wireframes (mobile + desktop + tablet)
- [ ] Landing page wireframe

**Quality Gate:**
1. Brand Designer delivers complete design system
2. QA Director critiques (consistency, accessibility, WCAG AA, mobile usability)
3. Revise
4. QA Director critiques (edge cases: long names, dense data, empty states, one data point vs 100)
5. Revise → CEO approves → **Design system locked**

---

### Phase 1: Data Architecture
**Goal:** Design a schema that serves two people today and millions later. 20-year durability.
**Duration:** 1 session

**Deliverables:**
- [ ] Entity-relationship diagram (full system)
- [ ] PostgreSQL schema with multi-tenancy:
  - `accounts` (billing entity — individual or household)
  - `users` (auth, profile, linked to account)
  - `user_preferences` (units, goals display, notification settings)
  - `connected_devices` (OAuth tokens, sync status per user per source)
  - `wearable_daily` (unified daily metrics: source, HR, HRV, sleep, steps, SpO2, stress, readiness)
  - `wearable_sleep` (detailed sleep stages, per-source)
  - `wearable_activities` (workouts, type, duration, HR zones, calories)
  - `blood_panels` (date, lab, provider, source document, status)
  - `blood_markers` (marker_id, value, unit, ref range, linked to panel)
  - `biomarker_dictionary` (canonical names, aliases, categories, units, optimal ranges)
  - `dexa_scans` (total + regional composition, bone density)
  - `epigenetic_tests` (bio age, pace, telomere, immune age, methylation data)
  - `lifting_sessions` + `lifting_sets` (exercise, volume, intensity)
  - `exercise_dictionary` (canonical exercise names, muscle groups)
  - `supplements` (name, dose, frequency, start/end, linked to user)
  - `nutrition_logs` (date, type, data JSON — flexible)
  - `measurements` (date, metric, value, unit — generic)
  - `custom_metrics` + `custom_metric_entries`
  - `mood_journal` (date, mood, energy, stress, notes)
  - `menstrual_cycles` (date, phase, flow, symptoms)
  - `doctor_visits` (date, provider, specialty, notes, linked labs)
  - `photos` (date, type, S3 key, notes)
  - `documents` (original files, S3 key, parse status)
  - `goals` (metric, target, direction, alert threshold)
  - `insights` (generated correlations, cached for dashboard)
  - `ingestion_jobs` (queue status, source, errors, retries)
  - `audit_log` (all data mutations for compliance)
- [ ] Row-level security policies (users only see their own data)
- [ ] Migration framework (Alembic)
- [ ] Backup strategy (automated daily + point-in-time recovery)
- [ ] Data validation layer (Pydantic models for every entity)
- [ ] Canonical biomarker dictionary (seed data: 200+ common markers with aliases)
- [ ] Unit conversion service
- [ ] Data retention and deletion policy (GDPR/CCPA ready)
- [ ] Performance: indexes, partitioning strategy for time-series data at scale

**Quality Gate:**
1. Data Engineer delivers schema + ERD + docs
2. QA Director critiques (normalization, extensibility, security, compliance)
3. Revise
4. QA Director critiques (scale: what happens with 100K users × 5 years of daily data?)
5. Revise → CEO approves → **Schema locked**

---

### Phase 2: Backend & Ingestion
**Goal:** Build the API, auth, and all data pipelines.
**Duration:** 2 sessions

**Sub-phase 2A: Core API + Auth**
- [ ] FastAPI project structure (modular, clean separation)
- [ ] Auth system (email/password + magic link + OAuth social login)
- [ ] JWT tokens, refresh tokens, session management
- [ ] Account + user management endpoints
- [ ] CRUD for all entities
- [ ] File upload to S3/R2 (PDFs, photos)
- [ ] Rate limiting
- [ ] Request logging + error tracking
- [ ] API versioning (v1 from day one)
- [ ] OpenAPI docs (auto-generated)
- [ ] CORS, security headers, input sanitization

**Sub-phase 2B: Ingestion Pipelines**
- [ ] Job queue system (Redis + worker processes)
- [ ] Garmin Connect OAuth flow + daily sync adapter
- [ ] Oura Cloud OAuth flow + daily sync adapter
- [ ] Apple Health receiver endpoint (iOS Shortcut POST)
- [ ] WHOOP OAuth flow + daily sync adapter
- [ ] Strong import (CSV parser)
- [ ] Adapter interface (standardized for future sources)
- [ ] Duplicate detection + idempotent writes
- [ ] Sync status dashboard (per user, per source)
- [ ] Error handling + retry logic + dead letter queue

**Sub-phase 2C: AI Document Parsing**
- [ ] PDF text extraction (pymupdf + pdfplumber)
- [ ] LLM parsing pipeline:
  - Blood work: extract all markers, map to canonical dictionary
  - DEXA: extract body comp, regional, bone density
  - Epigenetics: extract bio age, pace, telomere, methylation
- [ ] Confidence scoring per extracted value
- [ ] Human confirmation flow (parse → preview → confirm/edit → insert)
- [ ] Original document archival (S3, linked to parsed data)
- [ ] Support for: Quest, Labcorp, DexaFit, TruDiagnostic (priority)
- [ ] Extensible to new formats without core changes

**Quality Gates:** Each sub-phase gets the 3x critique loop independently.

---

### Phase 3: Frontend — Core Dashboard
**Goal:** Build the PWA implementing the brand design system. Beautiful, intuitive, fast.
**Duration:** 2 sessions

**Sub-phase 3A: Foundation**
- [ ] React + Vite + Tailwind + design system tokens
- [ ] PWA manifest + service worker
- [ ] Auth flows (signup, login, magic link, OAuth)
- [ ] Onboarding wizard (connect devices, set goals, profile setup)
- [ ] Responsive layout system (mobile-first)
- [ ] Navigation (bottom tabs mobile, sidebar desktop)
- [ ] Profile switcher (household accounts)
- [ ] API client with auth token management
- [ ] Offline caching for recent data

**Sub-phase 3B: Dashboard Views**
- [ ] **Home** — today's snapshot, streaks, upcoming goals, recent insights
- [ ] **Sleep** — last night + trends, multi-source comparison
- [ ] **Activity** — workouts, steps, HR zones, training load
- [ ] **Body** — weight, DEXA history, measurements, progress photos (side-by-side slider)
- [ ] **Blood Work** — all markers, history charts, reference ranges, goal status
- [ ] **Longevity** — epigenetics, biological age trend, pace of aging
- [ ] **Lifting** — exercise progression, PRs, volume trends
- [ ] **Supplements** — current stack, timeline, linked outcome markers
- [ ] **Journal** — mood/energy/stress timeline, doctor notes
- [ ] **Insights** — AI correlations, anomalies, recommendations
- [ ] **Settings** — connected devices, goals, export, account

**Sub-phase 3C: Input & Upload**
- [ ] Quick log (tap → metric → number → save)
- [ ] PDF drop zone with live parse preview + confirm
- [ ] Photo capture/upload with date linking
- [ ] Daily check-in (mood/energy/stress — beautiful 1-5 tap)
- [ ] Supplement logger
- [ ] Meal/fasting logger (lightweight)
- [ ] Custom metric creator
- [ ] Menstrual cycle logger
- [ ] Doctor visit form

**Quality Gates:** 3x critique per sub-phase + Brand Designer reviews visual fidelity.

---

### Phase 4: Analysis & Intelligence
**Goal:** Make the data smart. This is the moat.
**Duration:** 1 session

- [ ] Time-series engine (rolling averages, trend lines, seasonality)
- [ ] Z-score anomaly detection
- [ ] Cross-domain correlation engine:
  - Sleep ↔ next-day HRV and performance
  - Supplements ↔ blood marker changes (lagged correlation)
  - Training load ↔ recovery metrics
  - Menstrual phase ↔ HRV/sleep/mood
  - Mood/stress ↔ sleep quality
  - Nutrition ↔ body composition
  - Biological age pace ↔ lifestyle factors
- [ ] Goal tracking with projected trajectories
- [ ] Insight generator (natural language cards)
- [ ] Annual health report (PDF):
  - Year summary with visualizations
  - Biggest wins and concerns
  - YoY comparison
  - Recommendations
  - Shareable with doctors
- [ ] Wearable cross-validation ("Garmin says X, Oura says Y — here's the truth")

**Quality Gate:** 3x critique, focus on statistical validity and sparse-data handling.

---

### Phase 5: Infrastructure & Deployment
**Goal:** Production-grade deployment with monitoring and reliability.
**Duration:** 1 session

- [ ] Dockerfiles (API, worker, frontend — multi-stage builds)
- [ ] Docker Compose for local dev
- [ ] Fly.io deployment (API + worker + Postgres)
- [ ] S3/R2 bucket for documents and photos
- [ ] Redis for job queues
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Database migrations on deploy
- [ ] Automated backups (daily + PITR)
- [ ] Health monitoring + uptime alerts
- [ ] Error tracking (Sentry)
- [ ] Log aggregation
- [ ] SSL/HTTPS enforced
- [ ] Environment management (staging + production)
- [ ] Load testing (target: 10K concurrent users)

**Quality Gate:** 3x critique, focus on security, reliability, failure recovery.

---

### Phase 6: Dogfood & Backfill
**Goal:** Load all your real data, use it daily, find every rough edge.
**Duration:** 1 session

- [ ] Ev: Garmin 2-year backfill
- [ ] Ev: All historical blood work PDFs
- [ ] Ev: All DEXA scan PDFs
- [ ] Ev: Epigenetic test results
- [ ] Ev: Lifting history from Strong
- [ ] Ev: Set biomarker goals, log current supplements
- [ ] Wife: Apple Watch sync setup
- [ ] Wife: Oura Ring sync setup
- [ ] Wife: Historical blood work + DEXA
- [ ] Wife: Menstrual cycle baseline
- [ ] Both: PWA installed on phones
- [ ] Both: Daily use for 2 weeks
- [ ] Bug list → fix → iterate
- [ ] UX friction log → smooth → iterate

---

### Phase 7: Launch Prep
**Goal:** Get ready for public users.
**Duration:** 1 session

- [ ] Landing page (brand-aligned, conversion-optimized)
- [ ] Pricing tiers:
  - **Free** — 1 device, manual entry, basic charts
  - **Pro ($9/mo)** — unlimited devices, AI parsing, insights, reports
  - **Family ($14/mo)** — up to 4 profiles, shared household
- [ ] Stripe integration
- [ ] Onboarding flow polished for strangers (not just you)
- [ ] Help docs / FAQ
- [ ] Privacy policy + terms (HIPAA-aware, GDPR/CCPA compliant)
- [ ] App Store listing prep (if native app built)
- [ ] Launch marketing:
  - Product Hunt
  - Reddit (r/longevity, r/Biohackers, r/garmin, r/ouraring)
  - Twitter/X
  - HN (Show HN)
- [ ] Feedback collection system (in-app)
- [ ] Support channel

---

## Quality Assurance Philosophy

### 3x Critique Loop (Every Phase)
```
Draft → QA Critique #1 → Revise → QA Critique #2 → Revise → CEO Final Review → Lock
```

### Invariants
- Nothing ships without passing the critique loop
- No phase begins until the prior phase is locked
- Phase 0 and Phase 1 run in parallel (no dependency)
- All other phases are sequential
- Every data write is validated (Pydantic)
- Every ingestion is idempotent
- Every PDF parse requires human confirmation
- Every view has empty, loading, and error states
- Schema changes require migrations (never raw ALTER TABLE)
- All original documents archived permanently
- All user data is isolated (row-level security)
- Full data export is always available
- Audit log captures all mutations

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| Wearable API changes/deprecation | Adapter pattern; store raw responses; swap adapters without core changes |
| Hosting provider shuts down | Postgres dump + Docker = redeploy anywhere in 30 min |
| LLM parsing errors | Human confirmation required; confidence scoring; never auto-insert |
| HIPAA compliance questions | Data encrypted at rest + transit; audit log; no PHI in logs; privacy-first design |
| Scale beyond Fly.io | Horizontally scalable architecture; migrate to AWS/GCP when needed |
| Competitor launches similar product | Moat is data portability + beauty + intelligence layer; hard to copy all three |
| User data loss | Automated daily backups + PITR + S3 document archive |
| Adding new wearable source | Adapter interface: ~1 day of work per new device |

---

## Estimated Costs

### Build
| Item | Cost |
|------|------|
| Agent compute (all phases) | ~$50-80 |

### Ongoing (Pre-Revenue)
| Item | Monthly |
|------|---------|
| Fly.io (API + worker + DB) | ~$15 |
| S3/R2 (documents, photos) | ~$2 |
| Redis | ~$5 |
| Domain | ~$1 |
| **Total** | **~$23/mo** |

### Revenue Model
| Tier | Price | Target |
|------|-------|--------|
| Free | $0 | Acquisition, habit formation |
| Pro | $9/mo | Power users, biohackers |
| Family | $14/mo | Households |

**Break-even:** ~3 paying users covers infrastructure.

---

## Success Criteria

### Dogfood (Phase 6)
- [ ] Both users check the dashboard daily
- [ ] All wearable data syncs automatically
- [ ] PDF parsing works on real documents without errors
- [ ] Dashboard feels premium — something you'd show friends
- [ ] Data is visibly correct and trustworthy

### Launch (Phase 7)
- [ ] 100 signups in first month
- [ ] 10 paying users in first quarter
- [ ] NPS > 50 from early users
- [ ] Zero data integrity incidents
- [ ] Page load < 2 seconds globally

### Year 1
- [ ] 1,000+ users
- [ ] Profitable on infrastructure costs
- [ ] 5+ wearable integrations
- [ ] Featured on Product Hunt / HN

---

*Phase 0 (Brand) and Phase 1 (Schema) begin in parallel.*
*This is a product. Build it like one.*
