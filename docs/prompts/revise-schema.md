You are a Data Engineer revising SCHEMA.md and schema.sql based on QA critique.

Read these files in order:
1. PLAN.md — project context
2. SCHEMA.md — your original documentation
3. schema.sql — your original DDL
4. QA-SCHEMA-REVIEW.md — the QA Director's critique

Your job: Fix EVERY issue raised in the QA review. Rewrite both SCHEMA.md and schema.sql with all fixes applied. Do not skip any issue. The revised files must address:

1. Fix audit_mutation() trigger — use TG_ARGV for PK column, attach triggers to ALL tables
2. Add WITH CHECK clauses to ALL RLS policies (currently writes are unprotected)
3. Add FK constraints with ON DELETE CASCADE for partitioned wearable tables
4. Add missing document_id FKs on blood_panels, dexa_scans, epigenetic_tests
5. Fix deletion_requests FK to allow user deletion (ON DELETE SET NULL)
6. Fix current_setting() UUID cast crash — use NULLIF wrapper
7. Add RLS policy on accounts table
8. Fix all other Critical, High, and Medium priority issues from the review
9. Add missing indexes identified in the review
10. Fix enum limitations — consider using reference tables where noted
11. Address timezone handling gaps
12. Fix duplicate detection strategy

Write the complete revised SCHEMA.md and schema.sql. Do not truncate — write full documents.
