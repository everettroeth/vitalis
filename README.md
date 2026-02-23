# Vitalis

Personal health intelligence platform. One home for all your health data.

## Structure

```
vitalis/
├── src/                    # Backend API (Python/FastAPI)
│   ├── models/             # Database models
│   ├── routers/            # API endpoints
│   ├── parsers/            # Lab report parsers (Quest, Labcorp, DEXA, epigenetic)
│   │   ├── adapters/       # Format-specific parsers
│   │   └── tests/          # Parser tests
│   ├── wearables/          # Wearable device integrations (Garmin, Oura, Whoop, Apple)
│   │   ├── adapters/       # Device-specific adapters
│   │   ├── menstrual/      # Menstrual cycle tracking
│   │   ├── sync/           # Data sync, dedup, backfill
│   │   └── tests/          # Wearable tests
│   ├── services/           # External services (Supabase, R2)
│   └── middleware/         # Auth, rate limiting, security
├── frontend/               # Web app (Next.js/React/TypeScript)
│   └── src/
│       ├── app/            # Pages (blood, sleep, activity, body, longevity, insights)
│       ├── components/     # UI components
│       └── lib/            # Utilities, API client
├── docs/                   # Documentation (NOT deployed)
│   ├── architecture/       # Schema, data models, engine specs
│   ├── brand/              # Brand guide, design previews
│   ├── design/             # Design system prototypes
│   ├── prompts/            # AI build prompts (historical)
│   └── qa/                 # QA review documents
├── sample-data/            # Test PDFs and extracted text
├── scripts/                # Build/utility scripts
└── tests/                  # Integration/E2E tests
```

## Quick Start

```bash
# Backend
pip install -r requirements.txt
uvicorn src.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

## Tech Stack
- **Backend:** Python, FastAPI, Supabase (Postgres)
- **Frontend:** Next.js, React, TypeScript, Tailwind
- **Auth:** Clerk
- **Storage:** Cloudflare R2
- **Parsers:** 11 adapters (Quest, Labcorp, InsideTracker, Function Health, DexaFit, BodySpec, TruDiagnostic, Elysium, + generics)
- **Wearables:** Garmin, Oura, Whoop, Apple Health
