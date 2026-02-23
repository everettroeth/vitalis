# QA Brand Review — Vitalis Design System
**QA Director · Critique #1**
*Reviewing: BRAND.md v1.0*

---

## Critical Issues (Must Fix Before Locking)

### 1. WCAG Contrast Ratio Error: White on Clay Claimed as AA-Passing
**BRAND.md line 111:** Claims "White on Clay: 4.2:1 — passes AA for normal text ✓"

This is **factually wrong**. WCAG AA for normal text requires **4.5:1**. A 4.2:1 ratio **fails** AA for normal text. It only passes AA for large text (≥ 3:1). This means any body-size white text on Clay backgrounds is non-compliant. Since Clay is used for concern status labels, CTAs, and highlights, this affects a significant surface area of the app.

**Fix:** Either darken Clay to achieve 4.5:1 with white (approximately `#A5623F` or darker), or restrict white-on-Clay to large text only and document this constraint explicitly. Update the contrast table to be honest.

### 2. Sage (#7B9E8B) Cannot Be Used for Text — Even the Doc Admits It
**BRAND.md line 107:** "Sage on Cream: 3.2:1 — use for UI elements, not body text"

But then the entire metric card pattern (line 547–568) uses Sage for status dots (2×2px — too small to read anyway), trend arrows, and the `text-vt-thriving` color class. The Appendix (line 1861) describes `text-vt-sage` as usable for "brand green" text. At 3.2:1, Sage **fails even AA large text** on cream backgrounds (needs 3.0:1 — actually it barely passes at 3.2, but only for large/bold text ≥ 18.66px bold or ≥ 24px regular). Any Sage text below 24px regular weight on cream is non-compliant.

The same color is listed as "primary CTA" in the color table (line 101) but the actual button implementation (line 1167) uses Fern for primary buttons. This is contradictory — which is it?

**Fix:** Resolve the role of Sage vs Fern for interactive elements. Sage should be restricted to decorative fills, chart lines, and large UI elements (dots, sparkline fills). All text-bearing uses of Sage need Fern instead. Update the color table's "Usage" column to be precise.

### 3. Sand (#C4A87A) on Cream Has No Documented Contrast Ratio
Sand is used for "Watch" status text (line 102), but its contrast ratio against Cream is conspicuously absent from the contrast table. Sand is **lighter** than Sage, so its contrast with Cream is **less than** 3.2:1 — likely around 2.3–2.7:1. This fails even AA large text.

In the status card config (line 651), the Watch variant inexplicably uses `text-amber-700 dark:text-amber-400` — reaching outside the brand palette to Tailwind defaults — which strongly suggests the designer knew Sand couldn't be used as text color and patched it silently.

**Fix:** Document the actual Sand-on-Cream contrast ratio honestly. Define a darker "Watch text" color (perhaps a dark sand/amber around `#8A6D3A`) that passes AA. Never use raw Sand as text color. Remove the `text-amber-700` escape hatch — it breaks the design system.

### 4. Watch Status Card Uses Tailwind Default Colors, Breaking Design System
**BRAND.md line 651:** `label: 'text-amber-700 dark:text-amber-400'`

This directly contradicts the core design rule on line 152: "Never render health alerts in hospital red or pure yellow. Status is communicated through the same warm tones the user has already learned to trust."

Tailwind's `amber-700` (#B45309) and `amber-400` (#FBBF24) are not Vitalis brand colors. The Watch status visually breaks from Thriving (uses `text-vt-thriving`) and Concern (uses `text-vt-clay`). This inconsistency means Watch status will look like it belongs to a different app.

**Fix:** Define a dedicated `--vt-watch-text` token. Use a darkened variant of Sand that passes AA contrast requirements on both light and dark backgrounds.

### 5. No Mobile Navigation Path to 10+ Dashboard Sections
**BRAND.md line 669:** Mobile bottom nav has 5 tabs: Home, Sleep, Body, Blood, Insights.

**PLAN.md line 296–307** specifies 11 dashboard views: Home, Sleep, Activity, Body, Blood Work, Longevity, Lifting, Supplements, Journal, Insights, Settings.

That's 6 views with **no way to reach them** on mobile: Activity, Longevity, Lifting, Supplements, Journal, Settings. The hamburger icon (≡) appears in the Home screen wireframe (line 1551) but is never defined — no menu component, no drawer spec, no interaction pattern. This is a critical navigation gap that will block the frontend build.

**Fix:** Design a hamburger/drawer menu for mobile that houses all sections. Or redesign the bottom nav as 4 tabs + "More" tab that opens a full navigation sheet. Define the component spec completely: animation, layout, grouping, close behavior.

### 6. Primary Button Hover Color Mismatch
**BRAND.md line 1181:** `.btn-primary:hover` uses `var(--vt-sage-dark, #3D5A4A)`.
**BRAND.md line 274:** Tailwind config defines `'sage-dark': '#4A6B5A'`.

The CSS fallback value (`#3D5A4A`) doesn't match the Tailwind definition (`#4A6B5A`). There is no CSS custom property `--vt-sage-dark` defined anywhere in the `:root` block (lines 181–237). This means the CSS will always use the fallback `#3D5A4A`, while any Tailwind usage of `bg-vt-sage-dark` will use `#4A6B5A`. Two different hover colors for the same button depending on implementation path.

Additionally, `sage-dark` in Tailwind is literally the same hex as `fern` (#4A6B5A). The button base is Fern, and hover is also Fern — meaning **no visual change on hover** via Tailwind. The CSS path uses a different, darker color. This is a mess.

**Fix:** Define `--vt-sage-dark` in the CSS custom properties block. Ensure it's a noticeably darker shade than Fern for hover contrast. Align the Tailwind config, CSS properties, and inline fallback to the same value.

---

## Design Consistency Issues

### 7. `sage-dark` and `fern` Are Identical
**Tailwind config line 274:** `'sage-dark': '#4A6B5A'`
**Tailwind config line 278:** `'fern': '#4A6B5A'`

Same hex value, two names. This creates developer confusion — "should I use `bg-vt-fern` or `bg-vt-sage-dark`?" — with no semantic distinction. One needs to be removed or differentiated.

### 8. `sage-light` (#A8C4B8) Is Orphaned
**Tailwind config line 273** defines `'sage-light': '#A8C4B8'` but this color appears nowhere else — not in the color tables, not in CSS custom properties, not in any component pattern, and not in the color system description. It's an undocumented ghost color.

**Fix:** Either document its purpose and add it to the CSS custom properties, or remove it from the Tailwind config.

### 9. Surface/Background Token Confusion
The document defines these overlapping concepts:
- `--vt-cream` (#FAFAF5) = "Main app background, page canvas"
- `--vt-bg` (#FAFAF5) = Same value, different token name
- `--vt-parchment` (#F2EDE4) = "Card backgrounds, sidebar, secondary surfaces"
- `--vt-surface` (#F2EDE4) = Same value, different token name
- `--vt-surface-elevated` (#FFFFFF) = "Elevated surfaces"

So `cream` = `bg` and `parchment` = `surface`. Having two names for the same semantic purpose guarantees inconsistent usage across the codebase. Developers will use `bg-vt-cream` and `bg-[--vt-bg]` interchangeably. When dark mode overrides `--vt-bg` but not `--vt-cream`, any component using the raw cream token will break in dark mode.

**Fix:** Choose one naming convention. Recommended: use the semantic tokens (`--vt-bg`, `--vt-surface`, `--vt-surface-elevated`) everywhere. Deprecate the named neutrals (`cream`, `parchment`) from Tailwind config or mark them as "raw color — not for direct use."

### 10. Border Token Aliasing
- `--vt-border` (#E5DDD2) is the same value as `--vt-sand-light`
- `border-vt-sand-light` and `border-vt-border` are documented as interchangeable (Appendix line 1877)

But only `--vt-border` gets a dark mode override (#38332E). Code using `border-vt-sand-light` directly will stay light-colored in dark mode — a subtle but real bug.

**Fix:** Use `--vt-border` exclusively for border colors. Remove `sand-light` from border usage examples.

### 11. Inconsistent Line Heights Between Type Scale and Variables
The type scale (lines 347–366) uses specific line-height values per class (1.0, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35, 1.6, 1.55, 1.4).

The line-height variables (lines 388–393) define a separate system: `--lh-tight: 1.15`, `--lh-snug: 1.3`, `--lh-normal: 1.5`, `--lh-relaxed: 1.65`, `--lh-loose: 2.0`.

The body text class uses `line-height: 1.6` but `--lh-normal` is `1.5`. These two systems don't map to each other, and neither references the other. Which does a developer use?

**Fix:** Align the line-height variables with the actual type scale values. Or eliminate the variables and let the type scale classes be the single source of truth.

### 12. Tailwind Border Radius Override Is Dangerous
**Tailwind config lines 301–306** override the default Tailwind border radius scale:
- `rounded-sm` becomes 6px (Tailwind default: 2px)
- `rounded-md` becomes 12px (Tailwind default: 6px)
- `rounded-lg` becomes 16px (Tailwind default: 8px)

Any developer using Tailwind's built-in `rounded-md` expecting the standard 6px will get 12px instead. Any external Tailwind component library (headless UI, shadcn, etc.) will have inflated border radii. This is a footgun.

**Fix:** Use namespaced values: `rounded-vt-sm`, `rounded-vt-md`, etc. Or document this override prominently and accept the tradeoff.

---

## Accessibility Concerns

### 13. Semantic Status Colors Are Indistinguishable for Colorblind Users
The three health statuses use: Sage (green), Sand (yellow-brown), Clay (orange-brown).

Under **deuteranopia** (red-green color blindness, ~8% of males): Sage and Clay will appear as similar muddy brown tones. Under **protanopia**: similar problem. The status system relies heavily on these color distinctions (dot colors, left-border colors, background tints).

The accessibility checklist (line 1905) says "Color is never the sole means of conveying information" but the status card wireframes (lines 613–638) show only a colored dot and the word "Thriving"/"Watch"/"Concern" — the text label is actually fine, but the dots, borders, and backgrounds all rely on color alone. The sparkline status dots on metric cards (line 547) are 2×2px colored circles with no text label.

**Fix:** Add a secondary visual indicator beyond color: different icon shapes (checkmark for thriving, eye for watch, triangle for concern — these are actually already in the icon set), or different border patterns (solid/dashed/dotted). Ensure every colored indicator has an adjacent text or icon label.

### 14. Chart Multi-Source Colors: Sage and Moss Are Nearly Identical
For multi-source charts (line 1004), the colors are:
- Source 1 (Garmin): Sage `#7B9E8B`
- Source 3 (WHOOP): Moss `#9BAB82`

Both are mid-tone greens. Their contrast ratio against each other is approximately 1.2:1 — essentially indistinguishable at small sizes, and even harder to tell apart for anyone with color vision deficiency. On a line chart with 2px strokes, overlapping lines would merge visually.

**Fix:** Replace Moss with a more distinct color for the third data source — perhaps Rose Dusk or a lighter/darker variant. Better yet, use dash patterns (solid, dashed, dotted) in addition to color for line charts. Add labeled legends that are always visible (not just on hover).

### 15. Small Button (btn-sm) Violates Touch Target Minimum
**BRAND.md line 1211:** `btn-sm` is specified as 36px height.
**BRAND.md line 465:** "Touch targets: minimum 44×44px."
**BRAND.md line 1163:** "All have 44px minimum touch target."

36px < 44px. This is a self-contradiction. Either remove `btn-sm` from mobile contexts entirely or increase it to 44px. As specified, a developer will use `btn-sm` on mobile and create an accessibility violation.

**Fix:** Set `btn-sm` to minimum 44px on mobile (`min-h-11`). Allow 36px only on desktop (`lg:min-h-9`). Or remove `btn-sm` and default to `btn-md`.

### 16. Toggle Track Size May Be Too Small
**BRAND.md line 1225:** Toggle is 44×24px. The thumb is 20×20px. The 44px width is fine for tap target, but the 24px height means the tap target is actually only 24px tall vertically — below the 44px minimum. Users with motor impairments will struggle.

**Fix:** Either increase the toggle height to 28–30px with appropriate padding, or add invisible padding to make the overall tappable area 44×44px minimum.

### 17. No Skip Navigation Link Defined in Component Patterns
The accessibility checklist (line 1911) mentions "Skip navigation link at top of page" but no component spec exists for it. It needs CSS that makes it visible only on focus, positioned correctly, and styled within the brand system.

### 18. Focus Ring Offset Not Specified for Dark Mode
The focus style uses `ring-offset-2` (line 1906) but no `ring-offset-color` is specified. In dark mode, `ring-offset-color` defaults to `background-color`, which may not always be the dark surface color, creating visible light gaps between the ring and the element.

**Fix:** Add `ring-offset-vt-bg` or `dark:ring-offset-[#1A1714]` to the focus ring pattern.

---

## Missing Pieces

### 19. Critical Missing Components (Referenced in PLAN.md But Absent from BRAND.md)

| Component | Referenced In | Status |
|-----------|--------------|--------|
| **Hamburger/drawer menu** (mobile nav overflow) | PLAN.md Phase 3A, BRAND.md header wireframe | Not specified |
| **Accordion** | Used in blood work wireframe (line 1667) | Not specified |
| **Tabs component** (7d / 30d / 90d selectors) | Used in trend card wireframe (line 575) | Not specified |
| **Progress bar** (goal tracking: "84%" fill) | Used in trend card wireframe (line 587) | Not specified |
| **Badge / Tag / Chip** (status labels, filter chips) | Implicit in many wireframes | Not specified |
| **Avatar component** | Referenced in profile switcher (line 838) | Mentioned, not spec'd |
| **Toast / Notification** (sync complete, errors) | Needed for sync, parsing, alerts | Not specified |
| **Data table** (sortable, filterable for blood markers) | Blood work panel with 200+ markers | Not specified |
| **Search / filter bar** (find markers, exercises, supplements) | Needed for 200+ biomarkers | Not specified |
| **Calendar / date range picker** (beyond native `<input>`) | Blood work history, trend date ranges | Not specified |
| **Multi-select / filter chips** | Device filters, metric filters | Not specified |
| **Confirmation dialog** (delete account, disconnect device) | Critical for destructive actions | Not specified |
| **Side-by-side photo slider** | Progress photos feature (PLAN.md #6) | Mentioned in wireframe, not spec'd |
| **Segmented body diagram (SVG)** | Regional DEXA breakdown (wireframe) | Mentioned, not spec'd |
| **Streak display** | Referenced with Flame icon (line 1398) | Not specified |
| **Device connection card** (OAuth flow UI) | Onboarding + Settings | Grid shown, interaction not spec'd |
| **Confidence score display** | PDF parse confirmation flow | Mentioned, not spec'd |
| **Goal setting interface** | PLAN.md feature #5 | Not specified |
| **Supplement logger UI** | PLAN.md feature #4 | Not specified |
| **Menstrual cycle logger** | PLAN.md feature #9 | Not specified |
| **Custom metric creator** | PLAN.md feature #13 | Not specified |

### 20. No Tooltip Component
Charts use tooltips (line 1022), the radar chart has a help icon [?] (line 1741), but there's no tooltip component specification — position logic, arrow, animation, max-width, mobile behavior (tap vs hover), accessibility (aria-describedby).

### 21. No Pagination / Infinite Scroll Pattern
Blood work history, lifting sessions, supplement timeline, doctor visits — all are list-based views that will grow over years. No pattern for handling long lists: virtual scrolling, pagination, or load-more.

### 22. No Annual Health Report PDF Design
**PLAN.md lines 339–345** describes an auto-generated PDF annual health report as a core v1 feature. No layout, typography, or visual treatment is specified in BRAND.md for print/PDF output.

### 23. No Offline Indicator
The app is a PWA (PLAN.md line 293, "Offline caching for recent data"). There's no visual indicator for when the user is offline, what data is cached vs stale, or how sync will resume.

---

## Scalability Concerns

### 24. Chart Rendering with 5 Years of Daily Data
A 5-year chart has ~1,825 data points. The line chart spec (line 1011) renders individual data points on hover (6px dots). At that density, the hover hit target per point is sub-pixel. No specification for:
- Data downsampling / aggregation at different time ranges
- What happens when the user selects "All time" instead of 7d/30d/90d
- Performance budget for chart rendering with large datasets

**Fix:** Define aggregation rules: >90 days shows weekly averages, >1 year shows monthly averages. Add "1y" and "All" time range options to the tab spec. Specify Recharts performance optimization (e.g., `isAnimationActive={false}` for large datasets).

### 25. Blood Work with 200+ Markers
The blood work wireframe shows an accordion pattern with categories. With 200+ markers across 10+ panels over years, the current design has:
- No search/filter mechanism
- No way to star/pin favorite markers
- No indication of which markers changed since last panel
- Category accordions will create very long scrollable views

**Fix:** Add a search bar at top of blood work view. Add a "changed since last panel" filter. Allow users to pin important markers to a favorites section. Consider a tabbed view by panel date, not just current-panel-with-history-links.

### 26. Sidebar Navigation Will Grow
The sidebar currently has ~15 items. If v2 features (Nutrition, Protocols, AI Coach, Community) are added, it becomes 20+. No collapsible sections, no favorites/pinning, no "frequently used" adaptation.

**Fix:** Make sidebar section headers collapsible. Add a quick-access/favorites section at top.

### 27. Long Metric Names and Values
The metric card wireframe (lines 527–537) shows "Resting HR" at 13px overline width. But custom metrics could have names like "Post-Prandial Blood Glucose Response" or "Erythrocyte Sedimentation Rate." No truncation, wrapping, or tooltip behavior is specified for long names. Similarly, values like "1,247,000 copies/mL" (viral load) would overflow the display number area.

**Fix:** Specify `text-overflow: ellipsis` with tooltip on hover for metric names. Define max character lengths and responsive text sizing for values.

### 28. Multi-User Household at Scale
The profile switcher (line 819) shows 2 users. A "Family" plan supports 4. The dropdown pattern doesn't define behavior for the maximum count, avatar collision (two users with same initials), or what happens if a household member has a very long name.

---

## Mobile UX Issues

### 29. Bottom Nav Covers Content
**BRAND.md line 686:** Bottom nav is `position: fixed` at 64px + safe area (roughly 98px on modern iPhones). No corresponding `padding-bottom` is defined for the main content scroll container. The last items in any scrollable view will be hidden behind the nav.

**Fix:** Add `padding-bottom: calc(64px + env(safe-area-inset-bottom) + 16px)` to the main content wrapper. Spec this explicitly.

### 30. Card Hover Effects Don't Apply on Touch Screens
Multiple components specify `:hover` interactions:
- Card hover lift with shadow (line 543, 1458)
- Button hover translate (line 1181)
- Bar chart hover opacity (line 1047)

None of these have touch/active equivalents. On mobile, `:hover` either doesn't fire or creates "sticky hover" on tap. The user gets no feedback.

**Fix:** Define `:active` states for all interactive elements on mobile. Add `@media (hover: hover)` guards around hover-only effects. Define tap feedback (brief opacity change, scale, or color shift).

### 31. 390px Minimum Is Tight
The smallest breakpoint is 390px (iPhone SE). But the SE has a **375px** viewport width. The 2-column metric card grid at 390px with 16px side padding leaves each card at ~171px — potentially too narrow for metric values + sparklines + labels.

**Fix:** Change minimum to 375px. Test the 2-column grid at 375px specifically. Consider going to 1-column below 390px.

### 32. Emoji Rendering Varies Across Platforms
The 1-5 rating system (line 930) uses emoji: 😔 😐 🙂 😊 🤩. Emoji rendering is dramatically different across iOS, Android (Google), and Samsung. The semantic meaning of facial expressions changes across platforms — Samsung's 🙂 historically looked uncomfortable, not pleasant.

**Fix:** Use custom SVG icons instead of platform emoji. This ensures consistent appearance, supports the brand aesthetic (earthy, warm), and allows animation (the spring bounce described on line 1467 works better with SVG).

### 33. `navigator.vibrate()` Unsupported on iOS
**BRAND.md line 951:** "Haptic feedback on mobile (navigator.vibrate(8))"

The `vibrate()` API is **not supported on iOS Safari** and will silently fail. For iOS haptics, you need the non-standard `navigator.vibrate` polyfill or UIKit's haptic engine via a native wrapper — neither available in a PWA.

**Fix:** Remove the `navigator.vibrate()` reference or note it as Android-only. For iOS PWAs, haptic feedback is not available.

### 34. Native Date Picker Styling Is Unreliable
**BRAND.md line 886:** "Native `<input type='date'>` with custom styling to match the design system."

Native date inputs have extremely limited CSS customizability, especially on iOS. The `::-webkit-calendar-picker-indicator` can be styled, but the actual picker chrome is entirely OS-controlled. "Custom styling to match the design system" is misleading — you can style the trigger, but the picker itself will look like iOS/Android defaults.

**Fix:** Acknowledge this limitation. Define what the trigger button looks like. For desktop, consider a custom date picker component (e.g., react-day-picker) that uses brand styles.

---

## Edge Cases Not Addressed

### 35. First-Time User with Zero Data
The home screen wireframe (line 1548) shows a fully populated dashboard. What does it look like with:
- No connected devices
- No blood work
- No metrics logged
- No insights generated

Individual empty states are described, but the full-page orchestration of multiple empty states simultaneously isn't addressed. If everything is empty, the home screen is just a stack of 6 empty state cards — overwhelming and discouraging.

**Fix:** Define a first-time experience: collapse empty sections, show one prominent "Get Started" flow, and progressively reveal dashboard sections as data arrives.

### 36. One Data Point on a Chart
The sparkline is described as "8-point sparkline" (line 536). What if the user has only 1 or 2 data points? A sparkline with 1 point is a dot. A trend line with 2 points is meaningless. No minimum data threshold is specified for when to show charts vs. a "not enough data yet" message.

**Fix:** Define minimum data thresholds: sparklines require ≥ 3 points, trend charts require ≥ 5, radar chart requires ≥ 2 data sources active, correlations require ≥ 14 points.

### 37. Very Long Text in Insight Cards
AI-generated insight text (line 1582) can vary in length. The wireframes show 2–3 lines, but a real correlation insight might be: "On days where you log stress above 3, complete fewer than 5,000 steps, and sleep less than 6 hours, your HRV the following morning drops by an average of 22% compared to your 30-day baseline, based on 47 data points over the past 6 months."

No truncation, expand/collapse, or max-height is specified for insight cards.

**Fix:** Define max visible lines (3–4) with "Read more" expand. Set a character limit for the AI insight generator.

### 38. Concurrent Sync States
Multiple devices can sync simultaneously. The sync pulse animation (line 1476) is defined per-icon, but there's no pattern for showing aggregate sync status (e.g., "3 of 4 sources syncing"), error on one source while others succeed, or partial sync.

### 39. PDF Parse Failures
The file drop zone (line 956) shows parsing → preview → confirmed states. But what about:
- Unreadable PDF (scanned image, no OCR)
- Low-confidence parse (AI extracts values but isn't sure)
- Partial parse (some markers found, others missed)
- Wrong document type (user uploads a bank statement)
- Duplicate document (already uploaded this panel)

Only the happy path is specified. The error and edge cases need their own UI treatments.

### 40. Timezone Handling in "Last Night" Sleep
Sleep data shows "Last night · Aug 21–22" (line 1609). But what about:
- User traveling across timezones
- Nap detection (midday sleep)
- Polyphasic sleepers
- Night shift workers (sleep from 8AM–4PM)

The "Last Night" framing assumes a single nighttime sleep period — a valid assumption for v1 but should be noted as a limitation.

---

## Dark Mode Issues

### 41. Multiple CSS Tokens Have No Dark Mode Override
The following CSS custom properties are defined in `:root` but **not overridden** in `[data-theme="dark"]`:

| Token | Light Value | Dark Mode Behavior |
|-------|------------|-------------------|
| `--vt-cream` | #FAFAF5 | **Stays light** — any direct usage will create bright spots |
| `--vt-parchment` | #F2EDE4 | **Stays light** — same problem |
| `--vt-sand-light` | #E5DDD2 | **Stays light** — used in skeleton shimmer, slider tracks |
| `--vt-sand-mid` | #C4B8AA | **Stays light** — used for placeholder text, disabled states |
| `--vt-sage` | #7B9E8B | Intentionally same (documented) |
| `--vt-sand` | #C4A87A | Intentionally same (documented) |
| `--vt-clay` | #B87355 | Intentionally same (documented) |

The first four are bugs. Any component using `var(--vt-sand-light)` directly instead of `var(--vt-border)` will render a light color on a dark background. The skeleton shimmer animation (line 1126) explicitly uses `var(--vt-sand-light)` and `var(--vt-parchment)` — it will be a bright shimmer on a dark background.

**Fix:** Add dark mode overrides for `--vt-cream`, `--vt-parchment`, `--vt-sand-light`, and `--vt-sand-mid`. Or refactor all component code to use only the semantic tokens that DO have dark overrides (`--vt-bg`, `--vt-surface`, `--vt-border`).

### 42. Dark Mode Shadows Use Pure Black, Losing Warmth
**Light mode shadows:** `rgba(30, 26, 22, ...)` — warm-tinted (line 219)
**Dark mode shadows:** `rgba(0, 0, 0, ...)` — pure cold black (line 254)

The brand explicitly prohibits cold tones ("no cold grays anywhere" — line 127). Using pure black shadows in dark mode introduces the cold tone the brand avoids.

**Fix:** Use warm-tinted dark shadows: `rgba(10, 8, 6, ...)` or similar warm near-black.

### 43. Dark Mode Semantic Status Backgrounds Are Too Similar
- `--vt-thriving-bg` dark: `#1E2D27`
- `--vt-watch-bg` dark: `#2A2418`
- `--vt-concern-bg` dark: `#2A1F18`

The watch and concern dark backgrounds differ only slightly in the green/red channel. On low-quality displays, OLED dark banding, or at low brightness, these will be nearly indistinguishable. Combined with the colorblind issues in #13, status differentiation in dark mode is very weak.

**Fix:** Increase the saturation or lightness spread between status backgrounds in dark mode. Consider adding a subtle pattern or opacity difference as a secondary signal.

### 44. Dark Mode Nav Bar Background Uses Light Mode Color
**BRAND.md line 693:** `.nav-bottom` has `background: rgba(242, 237, 228, 0.92)` (parchment with transparency) hardcoded. This is the light-mode-only value. No dark mode variant is specified. The frosted glass nav bar will be bright cream in dark mode.

**Fix:** Define dark mode nav background: `rgba(35, 32, 29, 0.92)` (surface with transparency) using the dark surface color.

### 45. `--vt-shadow-float` Has No Dark Mode Override
The float shadow (line 222) is defined for light mode only. The dark mode block (line 254) overrides sm, md, lg but not float. Modals in dark mode will use the light shadow value.

---

## Recommendations (Ranked by Priority)

### P0 — Must fix before any code is written

1. **Fix all contrast ratio failures.** Recalculate every ratio honestly. Define "text-safe" variants of Sage, Sand, and Clay that pass AA at normal text sizes. Remove the incorrect "passes AA" claim for White on Clay. Create a comprehensive contrast matrix covering both modes.

2. **Resolve Watch status color escape hatch.** Remove `text-amber-700` and define proper `--vt-watch-text` token within the brand palette.

3. **Design the mobile overflow navigation.** Spec a drawer menu or "More" tab pattern with full component definition. The app is mobile-first — this can't be an afterthought.

4. **Add dark mode overrides for all non-semantic neutral tokens** or mandate that only semantic tokens are used in components.

5. **Define the missing core components:** accordion, tabs, progress bar, toast, confirmation dialog, search bar. These block the frontend build.

### P1 — Must fix before first QA pass of frontend code

6. **Fix the colorblind accessibility problem** for status indicators and chart multi-source lines. Add shape/pattern differentiation.

7. **Fix the Sage/Fern role confusion.** One document should not list Sage as "primary CTA" while the button spec uses Fern.

8. **Resolve token aliasing** (cream/bg, parchment/surface, sand-light/border). Pick one naming convention.

9. **Fix dark mode nav background, shadow warmth, and skeleton colors.**

10. **Replace emoji with custom SVG for the rating component.**

11. **Define responsive data table, search, and pagination patterns** for blood work and other list-heavy views.

### P2 — Should fix before dogfood phase

12. **Define data aggregation rules** for charts at different time ranges.

13. **Spec the first-time empty state experience** as a holistic flow, not just individual empty cards.

14. **Add minimum data point thresholds** for when to show charts vs "not enough data."

15. **Define truncation behavior** for long metric names, insight text, and data values.

16. **Fix btn-sm touch target** — either remove it from mobile or enforce 44px minimum.

17. **Spec the mobile tap/active states** as counterparts to desktop hover.

18. **Define the offline indicator pattern** for the PWA.

19. **Add print/PDF stylesheet** for reports and blood work views.

### P3 — Track for later

20. RTL layout considerations if internationalization is planned.
21. Font loading strategy (subsetting, `font-display: swap`, preload) to minimize the performance impact of 3 font families × multiple weights.
22. Maximum content width for ultrawide displays.
23. Collapsible sidebar sections for nav scalability.
24. Timezone-aware sleep display.

---

## Summary

The brand system is **ambitious and well-articulated at the surface level**. The aesthetic direction is strong — earthy, warm, premium without being clinical. The typography choices are thoughtful. The component wireframes show genuine care for the user experience.

But it has **serious implementation problems lurking beneath the surface:**
- The contrast ratio claims contain at least one verifiable error and several suspicious gaps
- The Watch status color silently escapes the brand system
- A third of the dashboard views are unreachable on mobile
- Dark mode is about 70% complete — the remaining 30% will cause visible bugs
- At least 20 core components are either missing or merely gestured at
- Colorblind users will struggle with both status indicators and chart legend differentiation
- Scalability edge cases (long text, many data points, first-time empty state) are unaddressed

**This system is not ready to lock.** It needs a targeted revision pass addressing the P0 items, then a second QA critique before it can be approved for frontend implementation.

---

*QA Director — Critique #1 Complete*
*Next action: Brand Designer revises, QA critiques again.*
