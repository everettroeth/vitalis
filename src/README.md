# Vitalis API — Phase 2A Backend

FastAPI backend for the Vitalis personal health intelligence platform.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI (Python 3.12+) |
| Database | Supabase (PostgreSQL + TimescaleDB + RLS) |
| Auth | Clerk (JWT verification, webhooks) |
| File Storage | Cloudflare R2 (S3-compatible) |
| Validation | Pydantic v2 |

## Project Structure

```
src/
├── main.py                  # App entry point, middleware, router registration
├── config.py                # Settings from env vars (pydantic-settings)
├── dependencies.py          # Shared FastAPI dependencies (auth context)
├── middleware/
│   ├── clerk_auth.py        # Clerk JWT verification middleware
│   ├── rate_limit.py        # Per-IP sliding window rate limiter
│   └── security.py          # Security headers (HSTS, CSP, etc.)
├── models/
│   ├── base.py              # Shared Pydantic base models
│   ├── users.py             # Accounts, users, preferences, sessions, consents
│   ├── wearables.py         # Daily summaries, sleep, activities, devices
│   ├── blood_work.py        # Panels, markers, biomarker dictionary
│   ├── body_composition.py  # DEXA scans, regions, bone density
│   ├── epigenetics.py       # Epigenetic tests, organ ages
│   ├── fitness.py           # Lifting sessions, sets, exercise dictionary
│   ├── tracking.py          # Supplements, mood, measurements, cycles, etc.
│   ├── goals.py             # Goals, alerts, insights
│   ├── documents.py         # File uploads, parse status
│   └── system.py            # Ingestion jobs, audit log, lookups
├── routers/
│   ├── health.py            # GET /health
│   ├── webhooks.py          # POST /api/v1/webhooks/clerk
│   ├── users.py             # /api/v1/users/*
│   ├── wearables.py         # /api/v1/wearables/*
│   ├── blood_work.py        # /api/v1/blood-work/*
│   ├── supplements.py       # /api/v1/supplements/*
│   ├── mood_journal.py      # /api/v1/mood-journal/*
│   ├── goals.py             # /api/v1/goals/*
│   ├── measurements.py      # /api/v1/measurements/*
│   └── documents.py         # /api/v1/documents/*
└── services/
    ├── supabase.py          # asyncpg pool with RLS session variables
    └── r2.py                # Cloudflare R2 upload/download/delete
```

## Setup

### Prerequisites

- Python 3.12+
- A Supabase project with the schema from SCHEMA.md applied
- A Clerk application (for auth)
- A Cloudflare R2 bucket (for file storage)

### Install

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configure

```bash
# Copy env template and fill in your values
cp .env.example .env
```

### Run

```bash
# Development server with hot reload
uvicorn src.main:app --reload --port 8000

# Production
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Docs

Once running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

## Authentication Flow

1. Frontend authenticates users via Clerk (OAuth, magic link, etc.)
2. Clerk issues a JWT with the user's ID in the `sub` claim
3. Frontend sends the JWT as `Authorization: Bearer <token>` on every API request
4. `ClerkAuthMiddleware` validates the JWT against Clerk's JWKS endpoint
5. Route handlers receive the authenticated context via `CurrentUser` dependency
6. Database queries use `SET LOCAL app.current_user_id` for RLS enforcement

## Clerk Webhook (User Provisioning)

When a user signs up in Clerk, the `user.created` webhook:
1. Creates an `accounts` row (billing entity, defaults to free tier)
2. Creates a `users` row linked to the account
3. Creates default `user_preferences`

Configure in Clerk dashboard: Webhooks → Add Endpoint → URL: `https://your-api.com/api/v1/webhooks/clerk`

## API Versioning

All API routes are prefixed with `/api/v1`. When v2 is needed, add new routers
under `/api/v2` while keeping v1 stable.

## Key Design Decisions

- **asyncpg over Supabase Python client** — the Supabase client doesn't support `SET LOCAL` for RLS session variables, so we use asyncpg directly
- **RLS enforced at DB level** — every query runs within a transaction where `app.current_user_id` is set, so even a bug in application code can't leak data across users
- **Soft deletes** — most entities use `deleted_at` timestamps rather than hard deletes for audit trail compliance
- **Idempotent writes** — wearable data uses unique constraints on `(user_id, date, source)` to prevent duplicate imports
- **File deduplication** — document uploads are SHA-256 hashed to prevent storing the same PDF twice
