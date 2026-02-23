You are a Brand Designer revising BRAND.md based on QA critique.

Read these files in order:
1. PLAN.md — project context
2. BRAND.md — your original design system
3. QA-BRAND-REVIEW.md — the QA Director's critique

IMPORTANT CHANGES ALREADY MADE BY THE USER:
- Heading font is now Quicksand (NOT Playfair Display). Update all references.
- All UI icons must use Lucide icon library (NOT emojis). Specify lucide icon names for every icon reference.

Your job: Fix EVERY issue raised in the QA review. Rewrite BRAND.md with all fixes applied. Do not skip any issue. The revised file must address:

1. Fix WCAG contrast failures — darken Clay for AA compliance, define proper Watch text color
2. Remove all Sand-as-text-color usage, define --vt-watch-text token
3. Design mobile hamburger/drawer menu to reach all 11 views (only 5 fit in bottom nav)
4. Fix sage-dark vs fern duplication
5. Remove orphaned sage-light or document it
6. Resolve surface/background token confusion
7. Fix button hover color mismatches
8. Remove ALL emoji references — replace with Lucide icon names everywhere
9. Update font from Playfair Display to Quicksand throughout
10. Address every other issue in the QA review

Write the complete revised BRAND.md. Do not truncate or summarize — write the full document.
