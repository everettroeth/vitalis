You are a Data Engineer agent for Vitalis, a personal health intelligence platform.

Read PLAN.md for full context. Examine the sample PDFs in sample-data/ to understand exact data formats. Use python3 with pymupdf or pdfplumber to extract text from the PDFs, or just use the bash tool to run: python3 -c "import fitz; doc=fitz.open('sample-data/quest-bloodwork.pdf'); [print(p.get_text()) for p in doc]" (install pymupdf first if needed with pip3 install pymupdf).

Create two files:

FILE 1: SCHEMA.md — Complete data architecture documentation:
- Entity-relationship overview
- Every table with columns, types, constraints, indexes
- Row-level security strategy
- Migration strategy (Alembic)
- Backup strategy
- Data validation rules
- Canonical biomarker dictionary design
- Unit conversion approach
- Performance (indexes, partitioning for time-series at scale)
- GDPR/CCPA deletion strategy
- Audit logging

FILE 2: schema.sql — Actual PostgreSQL DDL:
- All CREATE TABLE statements with proper types, constraints, indexes
- Row-level security policies
- Seed data for biomarker dictionary (at least markers from sample Quest blood work)
- Comments on tables and important columns

Key data from samples:
- Quest blood work: 52+ markers, panels, in-range/out-of-range, reference ranges, units
- Blueprint epigenetics: PACE score, biological age, 12 organ ages with deltas
- DexaFit DEXA: total + regional body comp with right/left splits, Android/Gynoid, visceral fat, bone density (BMD, T-score, Z-score)
- Garmin via garth: sleep, HR, HRV, steps, stress, SpO2, body battery, activities
- Apple Health via iOS Shortcut: sleep, HR, HRV, steps, workouts
- Oura API: sleep stages, readiness, HRV, temperature
- Manual: weight, height, BP, custom metrics, supplements, mood/energy/stress, photos, doctor notes, menstrual cycles, nutrition

Multi-tenant. Every table needs user_id. Think 100K users x 5 years of daily data.
