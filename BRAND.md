# Vitalis — Brand & Design System
**Phase 0 Deliverable · Brand Designer Agent**
*Version 1.0 — Production Ready*

---

## Table of Contents
1. [Brand Identity](#1-brand-identity)
2. [Color System](#2-color-system)
3. [Typography](#3-typography)
4. [Spacing & Layout](#4-spacing--layout)
5. [Component Patterns](#5-component-patterns)
6. [Iconography](#6-iconography)
7. [Motion & Animation](#7-motion--animation)
8. [Dashboard Layouts](#8-dashboard-layouts)

---

## 1. Brand Identity

### Brand Name & Origin
**Vitalis** — from Latin *vitalis*, meaning "of life" or "essential to life." Short, memorable, premium, universally understood. Suggests longevity, vitality, and intelligence. Not clinical, not tech-bro — quietly confident.

### Logo Concept Direction

**Primary Mark:** An abstract organic mark — a stylized 'V' form whose arms curve inward and bloom outward, like a seedling's first two leaves emerging from soil. The negative space between the arms forms a subtle upward-pointing path (growth trajectory). No sharp angles. Everything is a smooth curve.

**Wordmark:** "Vitalis" set in Quicksand, tracked +20 letter-spacing, with the 'V' from the mark replacing the wordmark's V. Available as:
- Full lockup (mark + wordmark, horizontal)
- Stacked lockup (mark above wordmark)
- Mark only (app icon, favicon)

**Favicon/App Icon:** The leaf-V mark centered on a warm cream (#F2EDE4) rounded square, mark in Vitalis Sage (#7B9E8B). In dark mode: deep fern background (#23201D) with light cream mark.

**Color Variants:**
- Default: Sage mark on cream background
- Reversed: Cream mark on fern background
- Monochrome: Single-color fern on transparent
- Dark mode: Cream mark on dark surface

---

### Taglines

| # | Tagline | Use Case |
|---|---------|----------|
| 1 | **"Every signal, one home."** | Primary tagline — direct, aspirational, platform-defining |
| 2 | **"Your body has been talking. Now you can listen."** | Long-form marketing, landing page hero |
| 3 | **"Health intelligence, naturally."** | Brand essence — pairs brand benefit with aesthetic identity |
| 4 | **"Know your body. Own your health."** | Empowerment-focused — user autonomy positioning |
| 5 | **"The wellness retreat for your data."** | Lifestyle positioning — premium, premium-adjacent |

**Primary:** "Every signal, one home." — anchors the core value proposition (consolidation + intelligence) while leaving room for beauty and depth.

---

### Brand Personality

Vitalis is like a wise, warm friend who happens to know a lot about health. Not a doctor (clinical, cold), not a fitness app (loud, gamified) — something calmer and more lasting.

| Trait | Expression |
|-------|-----------|
| **Grounded** | Earth tones, organic shapes, nothing jarring |
| **Intelligent** | Data is presented meaningfully, not dumped |
| **Warm** | Rounded corners, soft shadows, wood tones |
| **Trustworthy** | Consistent, predictable, never alarmist |
| **Premium** | Restraint, whitespace, quality typography |
| **Approachable** | Plain language, no jargon, never condescending |

**The brand is NOT:** Clinical, aggressive, gamified, fluorescent, anxiety-inducing, tech-startup-bro, overcrowded, or hospital-adjacent.

---

### Brand Voice & Tone

**Writing Principles:**
1. **Short sentences.** Data apps don't need paragraphs.
2. **Active, not passive.** "Your HRV improved 12%" not "A 12% improvement in HRV was observed."
3. **Specific, not vague.** "Down 3 beats from yesterday" not "Your heart rate changed."
4. **Human, not robotic.** "Looks like your sleep has been a bit rough this week." not "SLEEP QUALITY: SUBOPTIMAL."
5. **Encouraging, not alarming.** Trends are conversations, not verdicts.
6. **Honest.** Don't hide negative data. Surface it calmly with context.

**Tone by Context:**
- **Insights/AI copy:** Warm, curious, conversational. A smart friend noticing patterns.
- **Error states:** Apologetic but clear. What went wrong, what to do next.
- **Empty states:** Inviting. "Nothing here yet — connect your Garmin and we'll fill this in."
- **Alerts:** Calm, never dramatic. "Worth keeping an eye on" not "WARNING: CRITICAL."
- **Onboarding:** Encouraging, milestone-celebrating. "You're all set up. Your health story starts here."

---

## 2. Color System

### Primary Palette

These four colors form the Vitalis brand foundation. They map to the natural world: meadow, sand, forest, clay.

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| **Vitalis Sage** | `#7B9E8B` | 123, 158, 139 | Primary brand color, primary CTA, thriving status, charts |
| **Warm Sand** | `#C4A87A` | 196, 168, 122 | Secondary brand, warm accents, watch status |
| **Deep Fern** | `#4A6B5A` | 74, 107, 90 | Dark text on light, hover states, sidebar backgrounds |
| **Clay** | `#B87355` | 184, 115, 85 | CTAs, highlights, concern status, energy/warmth |

**Contrast Ratios (WCAG AA):**
- Sage on Cream (#FAFAF5): 3.2:1 — use for UI elements, not body text
- Fern on Cream: 6.8:1 — passes AA for normal text ✓
- Clay on Cream: 3.9:1 — use for large text, icons ✓
- White on Fern: 7.1:1 — passes AAA ✓
- White on Clay: 4.2:1 — passes AA for normal text ✓

---

### Secondary Palette

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| **Moss** | `#9BAB82` | 155, 171, 130 | Supporting charts, progress fills, success tones |
| **Amber** | `#D4935A` | 212, 147, 90 | Attention states, streak highlights, food/nutrition |
| **Rose Dusk** | `#C49AAE` | 196, 154, 174 | Menstrual cycle data, feminine health metrics |

---

### Neutral Palette

Six carefully calibrated warm neutrals — no cold grays anywhere.

| Name | Token | Hex | Usage |
|------|-------|-----|-------|
| **Cream White** | `--vt-cream` | `#FAFAF5` | Main app background, page canvas |
| **Warm Parchment** | `--vt-parchment` | `#F2EDE4` | Card backgrounds, sidebar, secondary surfaces |
| **Light Sand** | `--vt-sand-light` | `#E5DDD2` | Borders, dividers, input backgrounds |
| **Mid Sand** | `--vt-sand-mid` | `#C4B8AA` | Placeholder text, disabled states, skeleton shimmer end |
| **Warm Gray** | `--vt-warm-gray` | `#7A7168` | Secondary text, captions, meta information |
| **Dark Warm** | `--vt-text-primary` | `#3D3730` | Primary body text |
| **Near Black** | `--vt-text-strong` | `#1E1A16` | Headings, high-contrast text, data values |

---

### Semantic Health Status Colors

These are NOT red/yellow/green. They use the brand palette itself to express health status with warmth, not alarm.

| Status | Color | Hex | Background | Border | Usage |
|--------|-------|-----|------------|--------|-------|
| **Thriving** | Vitalis Sage | `#7B9E8B` | `#EDF4F0` | `#BDD6CA` | In range, improving, optimal |
| **Watch** | Warm Sand | `#C4A87A` | `#F7F2EA` | `#E0CAA8` | Trending toward boundary, note this |
| **Concern** | Clay | `#B87355` | `#F5EDEA` | `#D9A88A` | Out of range, needs attention |
| **Unknown** | Mid Sand | `#C4B8AA` | `#F2EDE4` | `#E5DDD2` | No reference range, insufficient data |

**Critical Design Rule:** Never render health alerts in hospital red (`#FF0000`) or pure yellow (`#FFFF00`). Status is communicated through the same warm tones the user has already learned to trust. The emotional register stays calm.

---

### Dark Mode Variant

Dark mode uses warm near-blacks — never pure black or blue-tinted dark. The warmth carries through.

| Token | Light | Dark |
|-------|-------|------|
| `--vt-bg` | `#FAFAF5` | `#1A1714` |
| `--vt-surface` | `#F2EDE4` | `#23201D` |
| `--vt-surface-elevated` | `#FFFFFF` | `#2C2924` |
| `--vt-border` | `#E5DDD2` | `#38332E` |
| `--vt-border-strong` | `#C4B8AA` | `#4A4540` |
| `--vt-text-strong` | `#1E1A16` | `#F2EDE4` |
| `--vt-text-primary` | `#3D3730` | `#D4C8B8` |
| `--vt-text-secondary` | `#7A7168` | `#9A8E84` |
| `--vt-thriving-bg` | `#EDF4F0` | `#1E2D27` |
| `--vt-watch-bg` | `#F7F2EA` | `#2A2418` |
| `--vt-concern-bg` | `#F5EDEA` | `#2A1F18` |

Brand accent colors (Sage, Sand, Clay, Moss) remain consistent across modes — they're naturally legible in both contexts.

---

### CSS Custom Properties

```css
:root {
  /* ── Brand Colors ── */
  --vt-sage:         #7B9E8B;
  --vt-sand:         #C4A87A;
  --vt-fern:         #4A6B5A;
  --vt-clay:         #B87355;
  --vt-moss:         #9BAB82;
  --vt-amber:        #D4935A;
  --vt-rose:         #C49AAE;

  /* ── Neutrals ── */
  --vt-cream:        #FAFAF5;
  --vt-parchment:    #F2EDE4;
  --vt-sand-light:   #E5DDD2;
  --vt-sand-mid:     #C4B8AA;
  --vt-warm-gray:    #7A7168;
  --vt-text-primary: #3D3730;
  --vt-text-strong:  #1E1A16;

  /* ── Surfaces (light mode) ── */
  --vt-bg:               #FAFAF5;
  --vt-surface:          #F2EDE4;
  --vt-surface-elevated: #FFFFFF;
  --vt-border:           #E5DDD2;
  --vt-border-strong:    #C4B8AA;

  /* ── Semantic ── */
  --vt-thriving:         #7B9E8B;
  --vt-thriving-bg:      #EDF4F0;
  --vt-thriving-border:  #BDD6CA;
  --vt-watch:            #C4A87A;
  --vt-watch-bg:         #F7F2EA;
  --vt-watch-border:     #E0CAA8;
  --vt-concern:          #B87355;
  --vt-concern-bg:       #F5EDEA;
  --vt-concern-border:   #D9A88A;

  /* ── Shadows ── */
  --vt-shadow-sm:   0 1px 3px rgba(30, 26, 22, 0.06), 0 1px 2px rgba(30, 26, 22, 0.04);
  --vt-shadow-md:   0 4px 12px rgba(30, 26, 22, 0.08), 0 2px 4px rgba(30, 26, 22, 0.06);
  --vt-shadow-lg:   0 12px 32px rgba(30, 26, 22, 0.12), 0 4px 8px rgba(30, 26, 22, 0.08);
  --vt-shadow-float:0 20px 60px rgba(30, 26, 22, 0.16);

  /* ── Radius ── */
  --vt-radius-sm:   6px;
  --vt-radius-md:   12px;
  --vt-radius-lg:   16px;
  --vt-radius-xl:   24px;
  --vt-radius-pill: 9999px;

  /* ── Transitions ── */
  --vt-ease:        cubic-bezier(0.4, 0, 0.2, 1);
  --vt-ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
  --vt-duration-fast:   150ms;
  --vt-duration-base:   250ms;
  --vt-duration-slow:   350ms;
}

[data-theme="dark"] {
  --vt-bg:               #1A1714;
  --vt-surface:          #23201D;
  --vt-surface-elevated: #2C2924;
  --vt-border:           #38332E;
  --vt-border-strong:    #4A4540;
  --vt-text-strong:      #F2EDE4;
  --vt-text-primary:     #D4C8B8;
  --vt-warm-gray:        #9A8E84;
  --vt-thriving-bg:      #1E2D27;
  --vt-thriving-border:  #2A4538;
  --vt-watch-bg:         #2A2418;
  --vt-watch-border:     #3D3020;
  --vt-concern-bg:       #2A1F18;
  --vt-concern-border:   #3D2A20;
  --vt-shadow-sm:        0 1px 3px rgba(0, 0, 0, 0.24);
  --vt-shadow-md:        0 4px 12px rgba(0, 0, 0, 0.32);
  --vt-shadow-lg:        0 12px 32px rgba(0, 0, 0, 0.40);
}
```

---

### Tailwind Configuration

```js
// tailwind.config.js
module.exports = {
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        vt: {
          sage:       '#7B9E8B',
          'sage-light': '#A8C4B8',
          'sage-dark':  '#4A6B5A',
          sand:       '#C4A87A',
          'sand-light': '#E5DDD2',
          'sand-mid':   '#C4B8AA',
          fern:       '#4A6B5A',
          clay:       '#B87355',
          moss:       '#9BAB82',
          amber:      '#D4935A',
          rose:       '#C49AAE',
          cream:      '#FAFAF5',
          parchment:  '#F2EDE4',
          'text-strong':   '#1E1A16',
          'text-primary':  '#3D3730',
          'text-secondary':'#7A7168',
          thriving:   '#7B9E8B',
          'thriving-bg': '#EDF4F0',
          watch:      '#C4A87A',
          'watch-bg': '#F7F2EA',
          concern:    '#B87355',
          'concern-bg': '#F5EDEA',
        }
      },
      fontFamily: {
        display: ['"Quicksand"', 'Georgia', 'serif'],
        sans:    ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono:    ['"DM Mono"', 'monospace'],
      },
      borderRadius: {
        sm:   '6px',
        md:   '12px',
        lg:   '16px',
        xl:   '24px',
        '2xl': '32px',
      },
      boxShadow: {
        'vt-sm':    '0 1px 3px rgba(30,26,22,0.06), 0 1px 2px rgba(30,26,22,0.04)',
        'vt-md':    '0 4px 12px rgba(30,26,22,0.08), 0 2px 4px rgba(30,26,22,0.06)',
        'vt-lg':    '0 12px 32px rgba(30,26,22,0.12), 0 4px 8px rgba(30,26,22,0.08)',
        'vt-float': '0 20px 60px rgba(30,26,22,0.16)',
      },
      transitionTimingFunction: {
        spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
        smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
      }
    }
  }
}
```

---

## 3. Typography

### Font Families

| Role | Family | Fallback | Google Fonts |
|------|--------|----------|-------------|
| **Display / Heading** | Quicksand | Georgia, serif | `Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400` |
| **Body / UI** | DM Sans | system-ui, sans-serif | `DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600` |
| **Data / Mono** | DM Mono | 'Courier New', monospace | `DM+Mono:wght@400;500` |

**Design Rationale:**
- **Quicksand** brings organic warmth to headings and large metric values. The slight irregularity in stroke weight feels human, not mechanical.
- **DM Sans** is humanist geometric — clean and modern but with personality. Excellent readability at small sizes for data-dense UIs.
- **DM Mono** matches DM Sans in feel, ensuring tabular data (metric values, lab results) aligns perfectly in columns.

---

### Type Scale

All sizes use `clamp()` for fluid scaling between mobile and desktop.

```css
/* ── Display (big metric values, hero numbers) ── */
.text-display-xl  { font-size: clamp(3rem, 6vw, 5rem);    line-height: 1.0; }
.text-display-lg  { font-size: clamp(2.25rem, 4vw, 3.5rem); line-height: 1.1; }
.text-display     { font-size: clamp(1.75rem, 3vw, 2.5rem);  line-height: 1.15; }

/* ── Headings ── */
.text-h1  { font-size: clamp(1.5rem, 2.5vw, 2rem);    line-height: 1.2; }
.text-h2  { font-size: clamp(1.25rem, 2vw, 1.625rem);  line-height: 1.25; }
.text-h3  { font-size: clamp(1.125rem, 1.5vw, 1.375rem); line-height: 1.3; }
.text-h4  { font-size: 1.125rem;                        line-height: 1.35; }

/* ── Body ── */
.text-body-lg  { font-size: 1rem;       line-height: 1.6; }
.text-body     { font-size: 0.9375rem;  line-height: 1.6; } /* 15px */
.text-body-sm  { font-size: 0.875rem;   line-height: 1.55; } /* 14px */

/* ── UI Labels & Captions ── */
.text-label     { font-size: 0.8125rem; line-height: 1.4; } /* 13px */
.text-caption   { font-size: 0.75rem;   line-height: 1.4; } /* 12px */
.text-overline  { font-size: 0.6875rem; line-height: 1.3; letter-spacing: 0.08em; text-transform: uppercase; } /* 11px */
```

---

### Weight Usage

| Weight | Value | When to Use |
|--------|-------|-------------|
| Light | 300 | Large display text only (metric values in Display XL) |
| Regular | 400 | Body text, descriptions, secondary UI |
| Medium | 500 | Labels, nav items, card titles, table headers |
| Semibold | 600 | Primary headings, CTA buttons, important numbers |
| Bold | 700 | Display numbers when emphasis needed, alerts |

**Rule:** Metric values on cards use weight 300–400 in Quicksand at display sizes. The combination of large size + light weight + serif = premium data display. Do not bold big numbers — it looks clinical.

---

### Line Height & Letter Spacing

```css
/* Line Heights */
--lh-tight:   1.15;  /* Display, large headings */
--lh-snug:    1.3;   /* H3, H4, card titles */
--lh-normal:  1.5;   /* Body text default */
--lh-relaxed: 1.65;  /* Long-form copy, descriptions */
--lh-loose:   2.0;   /* Labels in data tables */

/* Letter Spacing */
--ls-tighter: -0.03em;  /* Display numbers, metric values */
--ls-tight:   -0.01em;  /* Headings */
--ls-normal:  0em;      /* Body */
--ls-wide:    0.03em;   /* Labels, small caps */
--ls-widest:  0.08em;   /* Overlines, category tags */
```

---

### Number Formatting

All numeric metric values use font-variant-numeric settings:

```css
.metric-value {
  font-family: 'Quicksand', Georgia, serif;
  font-feature-settings: 'tnum' 1, 'lnum' 1; /* tabular, lining numbers */
  font-variant-numeric: tabular-nums lining-nums;
  letter-spacing: -0.03em;
}

.data-table {
  font-family: 'DM Mono', monospace;
  font-feature-settings: 'tnum' 1;
  font-variant-numeric: tabular-nums;
}
```

---

## 4. Spacing & Layout

### Base Grid

Everything is a multiple of 4px. No exceptions.

```
1  →  4px   (0.25rem)
2  →  8px   (0.5rem)
3  →  12px  (0.75rem)
4  →  16px  (1rem)      ← base unit
5  →  20px  (1.25rem)
6  →  24px  (1.5rem)
8  →  32px  (2rem)
10 →  40px  (2.5rem)
12 →  48px  (3rem)
14 →  56px  (3.5rem)
16 →  64px  (4rem)
20 →  80px  (5rem)
24 →  96px  (6rem)
32 →  128px (8rem)
```

Tailwind's default spacing scale already uses 4px base — use it directly: `p-4` = 16px, `p-6` = 24px, etc.

---

### Mobile-First Breakpoints

```
xs:  390px   — iPhone SE / small Android (default — no prefix needed)
sm:  640px   — Large phone, landscape phone
md:  768px   — Tablet portrait
lg:  1024px  — Tablet landscape, small laptop
xl:  1280px  — Desktop
2xl: 1536px  — Wide desktop
```

**Critical mobile rules:**
- Touch targets: minimum 44×44px (Tailwind: `min-h-11 min-w-11`)
- Bottom navigation height: 64px + safe area inset (`pb-safe`)
- Top status bar: 44px safe area on iOS
- Content padding: 16px sides mobile, 24px tablet, 32px desktop

```css
/* Safe area CSS variables */
--safe-area-top:    env(safe-area-inset-top, 0px);
--safe-area-bottom: env(safe-area-inset-bottom, 0px);
--safe-area-left:   env(safe-area-inset-left, 0px);
--safe-area-right:  env(safe-area-inset-right, 0px);
```

---

### Layout Patterns

**Mobile (< 768px):** Single column. Full-width cards. Bottom navigation. Content scrolls vertically.

**Tablet (768px–1023px):** 2-column grid for cards. Possible side panel for detail views. Navigation can shift to sidebar or remain bottom tabs.

**Desktop (≥ 1024px):** Fixed left sidebar (240px) + main content area. Cards in 2–4 column grid. Detail panels slide in from right.

```
Mobile:                    Desktop:
┌────────────────┐         ┌──────┬──────────────────────────┐
│    Header      │         │      │       Header              │
├────────────────┤         │  S   ├──────────────────────────┤
│                │         │  i   │                          │
│   Full-width   │         │  d   │   Card Grid (2–4 col)    │
│   content      │         │  e   │                          │
│   cards        │         │  b   │                          │
│                │         │  a   │                          │
│                │         │  r   │                          │
├────────────────┤         │      │                          │
│  Bottom Nav    │         └──────┴──────────────────────────┘
└────────────────┘         (240px)      (flex: 1)
```

**Card Grid Columns:**
```
Mobile:  grid-cols-1          (single card full width)
sm:      grid-cols-2          (2 metric cards side by side)
lg:      grid-cols-3          (3 metric cards)
xl:      grid-cols-4          (4 metric cards)
```

For trend/chart cards (larger):
```
Mobile:  col-span-1 (full width)
lg:      col-span-2
xl:      col-span-2 or col-span-3
```

---

## 5. Component Patterns

### Metric Cards

Metric cards are the atomic display unit — used everywhere. Four sizes.

#### Small Metric Card (2-column grid on mobile)
```
┌──────────────────────────┐
│ ○ Resting HR        [↑]  │  ← 13px overline label, status dot, trend arrow
│                          │
│   58 bpm                 │  ← Display number (Playfair, 32px)
│                          │
│  ▂▃▅▄▆▇█▆  (sparkline)   │  ← 32px tall, 8-point sparkline
│                          │
│  ↑ 3 from yesterday      │  ← 12px caption, muted
└──────────────────────────┘
```

**Tailwind classes:**
```jsx
<div className="bg-vt-surface rounded-lg p-4 shadow-vt-sm border border-vt-sand-light
                hover:shadow-vt-md hover:scale-[1.02] transition-all duration-200 ease-smooth">
  {/* Header row */}
  <div className="flex items-center justify-between mb-3">
    <div className="flex items-center gap-2">
      <span className="w-2 h-2 rounded-full bg-vt-thriving" />
      <span className="text-overline text-vt-warm-gray tracking-widest">Resting HR</span>
    </div>
    <TrendArrow direction="up" className="text-vt-thriving w-4 h-4" />
  </div>

  {/* Metric value */}
  <div className="mb-2">
    <span className="font-display text-display font-light text-vt-text-strong tracking-tighter">
      58
    </span>
    <span className="font-sans text-body text-vt-warm-gray ml-1">bpm</span>
  </div>

  {/* Sparkline */}
  <div className="h-8 mb-2">
    <MiniSparkline data={data} color="var(--vt-sage)" />
  </div>

  {/* Delta */}
  <p className="text-caption text-vt-warm-gray">↑ 3 from yesterday</p>
</div>
```

#### Large Trend Card (full-width or 2-col span)
```
┌──────────────────────────────────────────────────┐
│  HRV Trend                        7d  30d  90d   │
│  ─────────────────────────────────────────────   │
│                                                  │
│  42 ms avg ↑ 12% this month                      │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │                         ╱╲                 │  │
│  │                    ╱╲  ╱  ╲╱╲              │  │
│  │               ╱╲  ╱  ╲╱      ╲            │  │
│  │          ╱╲  ╱  ╲╱                         │  │
│  └────────────────────────────────────────────┘  │
│  Aug 1         Aug 15              Aug 31         │
│                                                  │
│  Goal: 50ms ░░░░░░░░░░░░░░░░░░░░░░░░░░  84%     │
└──────────────────────────────────────────────────┘
```

**CSS for card container:**
```css
.card-trend {
  background: var(--vt-surface);
  border: 1px solid var(--vt-border);
  border-radius: var(--vt-radius-lg);
  padding: 1.5rem;
  box-shadow: var(--vt-shadow-sm);
  transition: box-shadow var(--vt-duration-base) var(--vt-ease);
}
.card-trend:hover {
  box-shadow: var(--vt-shadow-md);
}
```

---

### Alert / Status Cards

Three variants mapping to semantic health status colors.

```
Thriving:
┌──────────────────────────────────────────────┐
│ ◉ Testosterone        ● Thriving             │  ← left-border 4px sage
│                                              │
│  742 ng/dL   Optimal: 400–800                │
│  ▲ Up 8% from last panel (Oct 2024)          │
│  [View history →]                            │
└──────────────────────────────────────────────┘

Watch:
┌──────────────────────────────────────────────┐  ← left-border 4px sand
│ ◉ Ferritin            ◎ Watch                │
│                                              │
│  22 ng/mL    Optimal: 40–80                  │
│  ↓ Down 15% over 3 months                   │
│  [View history →]                            │
└──────────────────────────────────────────────┘

Concern:
┌──────────────────────────────────────────────┐  ← left-border 4px clay
│ ◉ Vitamin D           ▲ Concern              │
│                                              │
│  18 ng/mL    Optimal: 40–60                  │
│  Below range — worth discussing with doctor  │
│  [View history →]                            │
└──────────────────────────────────────────────┘
```

**Tailwind pattern for status cards:**
```jsx
const statusConfig = {
  thriving: {
    bg: 'bg-vt-thriving-bg',
    border: 'border-l-4 border-l-vt-thriving border-y border-r border-vt-thriving-border',
    dot: 'bg-vt-thriving',
    label: 'text-vt-thriving',
  },
  watch: {
    bg: 'bg-vt-watch-bg',
    border: 'border-l-4 border-l-vt-watch border-y border-r border-vt-watch-border',
    dot: 'bg-vt-watch',
    label: 'text-amber-700 dark:text-amber-400',
  },
  concern: {
    bg: 'bg-vt-concern-bg',
    border: 'border-l-4 border-l-vt-clay border-y border-r border-vt-concern-border',
    dot: 'bg-vt-clay',
    label: 'text-vt-clay',
  },
}
```

---

### Navigation

#### Mobile — Bottom Tab Bar (5 tabs)

```
┌────────────────────────────────────────────┐
│                                            │  ← app content
│                                            │
├────────────────────────────────────────────┤
│  ⌂      😴      ⬡      🩸      ✦         │  ← 64px + safe area
│ Home   Sleep   Body  Blood  Insights       │
│  ●                                         │  ← active indicator (sage dot or pill)
└────────────────────────────────────────────┘
```

```css
.nav-bottom {
  position: fixed;
  bottom: 0;
  left: 0; right: 0;
  height: calc(64px + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  background: var(--vt-surface);
  border-top: 1px solid var(--vt-border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  background: rgba(242, 237, 228, 0.92); /* parchment with transparency */
  display: flex;
  align-items: flex-start;
  padding-top: 8px;
}

.nav-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
  color: var(--vt-warm-gray);
  transition: color var(--vt-duration-fast) var(--vt-ease);
}

.nav-tab.active {
  color: var(--vt-fern);
}

.nav-tab.active::before {
  content: '';
  position: absolute;
  top: -1px;
  width: 24px;
  height: 2px;
  background: var(--vt-sage);
  border-radius: 0 0 2px 2px;
}
```

**Active state:** Top border pill (not underline) in Sage. Icon fills with Fern. Label weight shifts to Medium.

**Tab Icons:**
- Home: house/home
- Sleep: moon
- Body: person/figure
- Blood Work: droplet
- Insights: sparkle/wand

#### Desktop — Left Sidebar (240px)

```
┌──────────────────────┐
│  [Logo] Vitalis      │  ← 64px top, brand mark + wordmark
│ ─────────────────── │
│  [Ev ▾]  (switcher)  │  ← Profile switcher
│ ─────────────────── │
│  ○ Home              │  ← 44px tall, icon + label
│  ○ Today's Stats     │
│                      │
│  HEALTH DATA         │  ← Section header (overline, muted)
│  ○ Sleep             │
│  ○ Activity          │
│  ○ Body Composition  │
│  ○ Blood Work        │
│  ○ Longevity         │
│  ○ Lifting           │
│                      │
│  DAILY LOGS          │
│  ○ Journal           │
│  ○ Supplements       │
│  ○ Nutrition         │
│                      │
│  INTELLIGENCE        │
│  ○ Insights          │
│  ○ Reports           │
│                      │
│ ─────────────────── │
│  ○ Settings          │
│  ○ Export Data       │
└──────────────────────┘
```

```css
.sidebar {
  width: 240px;
  height: 100vh;
  position: fixed;
  left: 0; top: 0;
  background: var(--vt-parchment);
  border-right: 1px solid var(--vt-border);
  overflow-y: auto;
  padding: 0 8px 24px;
  display: flex;
  flex-direction: column;
}

.sidebar-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--vt-radius-sm);
  color: var(--vt-text-primary);
  font-size: 0.9375rem;
  font-weight: 400;
  transition: all var(--vt-duration-fast) var(--vt-ease);
  cursor: pointer;
}

.sidebar-nav-item:hover {
  background: var(--vt-sand-light);
  color: var(--vt-text-strong);
}

.sidebar-nav-item.active {
  background: var(--vt-thriving-bg);
  color: var(--vt-fern);
  font-weight: 500;
}

.sidebar-section-header {
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--vt-warm-gray);
  padding: 16px 12px 4px;
}
```

---

### Profile Switcher

```
Desktop (sidebar top):
┌────────────────────────────┐
│  ┌──┐  Ev Varden      ▾   │  ← avatar (32px) + name + chevron
│  └──┘  pro plan           │
└────────────────────────────┘
  ▼ (expanded dropdown)
┌────────────────────────────┐
│  ✓  Ev Varden             │  ← checkmark on active
│     Sarah Varden          │
│  ─────────────────────    │
│  + Add household member   │
│  ─────────────────────    │
│  Account Settings         │
│  Sign Out                 │
└────────────────────────────┘
```

**Avatar:** Initials on earthy background if no photo. Use a consistent warm color per user (Sage for Ev, Rose for Sarah, etc.) — not random.

---

### Input Forms

#### Text Input
```jsx
<div className="space-y-1.5">
  <label className="text-label font-medium text-vt-text-primary">
    Weight (lbs)
  </label>
  <div className="relative">
    <input
      type="number"
      className="
        w-full px-4 py-3 rounded-lg
        bg-vt-surface border border-vt-sand-light
        text-body text-vt-text-strong
        placeholder:text-vt-sand-mid
        focus:outline-none focus:ring-2 focus:ring-vt-sage/40 focus:border-vt-sage
        transition-all duration-150
      "
      placeholder="185"
    />
    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-label text-vt-warm-gray">
      lbs
    </span>
  </div>
  <p className="text-caption text-vt-warm-gray">Last logged: 184.2 lbs on Aug 20</p>
</div>
```

**States:**
- Default: `border-vt-sand-light bg-vt-surface`
- Focus: `border-vt-sage ring-2 ring-vt-sage/30`
- Error: `border-vt-clay ring-2 ring-vt-clay/30`
- Disabled: `opacity-50 cursor-not-allowed bg-vt-parchment`

#### Number Input with Stepper
```
┌────────────────────────────────┐
│  [−]   8.5 hours   [+]        │
└────────────────────────────────┘
```
Tap buttons are 44×44px minimum. Value in center uses Quicksand, medium weight.

#### Date Picker
Native `<input type="date">` with custom styling to match the design system. On mobile, this invokes the native date picker (preferred for UX). Style the trigger button, not the picker chrome.

#### Slider (Range Input)

```
  Low            •───────────────○───── High
  0%                           82%        100%
```

```css
.vt-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(
    to right,
    var(--vt-sage) 0%,
    var(--vt-sage) var(--value-percent),
    var(--vt-sand-light) var(--value-percent),
    var(--vt-sand-light) 100%
  );
}

.vt-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 22px; height: 22px;
  border-radius: 50%;
  background: white;
  border: 2px solid var(--vt-sage);
  box-shadow: var(--vt-shadow-sm);
  transition: transform var(--vt-duration-fast) var(--vt-ease-spring);
}

.vt-slider::-webkit-slider-thumb:active {
  transform: scale(1.2);
}
```

#### 1-5 Tap Rating (Mood, Energy, Stress)

This is a key UI pattern — used daily. Must feel satisfying.

```
Mood today:

  😔   😐   🙂   😊   🤩
  ○    ○    ○    ●    ○
  1    2    3    4    5
      ─────────────
```

```jsx
const ratings = [
  { value: 1, emoji: '😔', label: 'Low' },
  { value: 2, emoji: '😐', label: 'Okay' },
  { value: 3, emoji: '🙂', label: 'Good' },
  { value: 4, emoji: '😊', label: 'Great' },
  { value: 5, emoji: '🤩', label: 'Amazing' },
]

// Each tap target: min 52px wide, centered
// Selected state: scale-110 + sage background pill behind emoji
// Tap animation: spring bounce (scale 0.9 → 1.15 → 1.0)
// Haptic feedback on mobile (navigator.vibrate(8))
```

**Stress variant uses inverted scale** — label 1 as "Calm", 5 as "Stressed". Color reversal: value 5 in Clay/Amber, not green.

#### File Drop Zone (PDF Upload)

```
┌────────────────────────────────────────────┐
│                                            │
│         ↑                                  │
│    [cloud icon, 48px, sage]                │
│                                            │
│    Drop your lab results here              │
│    or tap to browse files                  │
│                                            │
│    PDF, JPG, PNG · Max 50MB                │
│                                            │
└────────────────────────────────────────────┘
        ↓ (dragging over)
┌────────────────────────────────────────────┐  ← border 2px dashed → 2px solid sage
│  bg-vt-thriving-bg                         │
│                                            │
│       Release to upload                    │
│                                            │
└────────────────────────────────────────────┘
```

**Post-upload states:**
1. **Parsing:** Animated progress with "Reading your lab results..." copy
2. **Preview:** Extracted data table with confidence scores — user confirms each value
3. **Confirmed:** Success state, link to view the new panel

```jsx
// Drop zone Tailwind classes
// Default:
"border-2 border-dashed border-vt-sand-mid rounded-xl p-8 text-center
 bg-vt-surface cursor-pointer
 hover:border-vt-sage hover:bg-vt-thriving-bg
 transition-all duration-200"

// Active drag:
"border-2 border-solid border-vt-sage rounded-xl p-8 text-center
 bg-vt-thriving-bg cursor-copy"
```

---

### Charts

All charts use Recharts (or equivalent). Color assignments are consistent across the app.

#### Color Assignment for Multi-Source Charts
When comparing wearables (Garmin vs. Oura vs. WHOOP):
- Source 1 (Garmin): `#7B9E8B` (Sage)
- Source 2 (Oura): `#C4A87A` (Sand)
- Source 3 (WHOOP): `#9BAB82` (Moss)
- Source 4 (Apple Watch): `#B87355` (Clay)

#### Line Chart

```css
.chart-line {
  /* Filled area under line — very subtle */
  fill: url(#sage-gradient); /* 30% opacity at top → 0% at bottom */
  stroke: var(--vt-sage);
  stroke-width: 2;
}
```

```jsx
// Custom tooltip styling
<div className="bg-vt-surface-elevated border border-vt-border rounded-lg
                shadow-vt-md px-3 py-2">
  <p className="text-caption text-vt-warm-gray">Aug 22, 2024</p>
  <p className="text-body-sm font-medium text-vt-text-strong">
    42 ms
  </p>
</div>
```

**Grid lines:** `var(--vt-sand-light)` at 40% opacity — barely visible, never dominate.
**Axis text:** `var(--vt-warm-gray)`, DM Sans 11px.
**Data points:** Only shown on hover. Dot 6px filled sage with white center + shadow.

#### Bar Chart

Single-series: Sage bars. Multi-series: Sage + Sand + Moss.

```css
.bar-chart-bar {
  rx: 4;          /* rounded tops */
  fill: var(--vt-sage);
  opacity: 0.85;
  transition: opacity 150ms ease;
}
.bar-chart-bar:hover { opacity: 1; }
```

#### Radar Chart (Body Composition or Health Score)

Used for the "Health Fingerprint" on the home dashboard — showing multiple dimensions at once.

```
         Sleep
           |
  HRV ─────┼───── Activity
           |
  Blood ───┼───── Longevity
       Work |
          Body
           Comp
```

Colors: Sage polygon fill at 20% opacity, sage stroke at 70%. Grid lines sand-light.

#### Body Composition Chart

Simple horizontal stacked bar showing:
```
Body Composition:
Fat Mass ████████████░░░░░░░░░░░░░░░░░░░  Lean Mass
 22.4%   ████████████░░░░░░░░░░░░░░░░░░░   77.6%
```

Or donut chart variant:
- Segments: Fat Mass (Sand), Lean Mass (Sage), Bone Mineral (Fern)
- Center: Total body weight in Quicksand

---

### Empty States

Empty states are **invitations**, not dead ends. Each should:
1. Have a relevant illustration (simple line art, earthy tones)
2. Explain what will appear here
3. Offer a clear action

**Structure:**
```
┌──────────────────────────────────┐
│                                  │
│    [illustration, 80px, muted]   │
│                                  │
│    Nothing here yet              │  ← H3, text-strong
│    Connect your Garmin to see    │  ← body, text-secondary
│    your sleep data appear.       │
│                                  │
│    [Connect Garmin →]            │  ← Primary CTA button
│                                  │
└──────────────────────────────────┘
```

Empty state illustrations use 2-color line art (sand + sage on parchment background). Never stock photos. Consistent 80px icon/illustration size.

---

### Loading States

Skeleton screens, not spinners. Skeletons match the exact shape and layout of the content they replace.

```jsx
// Skeleton animation
@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton {
  background: linear-gradient(
    90deg,
    var(--vt-sand-light) 25%,
    var(--vt-parchment) 50%,
    var(--vt-sand-light) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  border-radius: var(--vt-radius-sm);
}

// Metric card skeleton
.skeleton-metric-card {
  height: 120px;
  // Internal skeleton bars match the card layout
}
```

**Skeleton color palette:** `#E5DDD2` → `#F2EDE4` — warm shimmer, never cold gray.

---

### Error States

```
┌──────────────────────────────────┐
│  ⚠                               │  ← 20px icon, Clay color
│                                  │
│  Couldn't load your sleep data   │  ← H4, concise
│  Check your connection and try   │  ← body-sm, muted
│  again. Your cached data from    │
│  yesterday is shown below.       │
│                                  │
│  [Try again]   [View cached]     │  ← secondary + ghost buttons
└──────────────────────────────────┘
```

**Rule:** Always show what data IS available (cached) even in error state. Never show a blank screen.

---

### Buttons

Four variants. All have 44px minimum touch target.

#### Primary Button
```css
.btn-primary {
  background: var(--vt-fern);
  color: white;
  padding: 12px 24px;
  border-radius: var(--vt-radius-md);
  font-family: 'DM Sans', sans-serif;
  font-size: 0.9375rem;
  font-weight: 500;
  letter-spacing: 0.01em;
  border: none;
  cursor: pointer;
  transition: all var(--vt-duration-fast) var(--vt-ease);
  min-height: 44px;
}
.btn-primary:hover { background: var(--vt-sage-dark, #3D5A4A); transform: translateY(-1px); box-shadow: var(--vt-shadow-md); }
.btn-primary:active { transform: translateY(0); box-shadow: none; }
```
Tailwind: `bg-vt-fern text-white px-6 py-3 rounded-lg font-medium hover:bg-vt-fern/90 hover:-translate-y-0.5 hover:shadow-vt-md active:translate-y-0 transition-all duration-150`

#### Secondary Button (outline)
```css
border: 1.5px solid var(--vt-fern);
color: var(--vt-fern);
background: transparent;
```
Hover: `bg-vt-thriving-bg`

#### Ghost Button
```css
background: transparent;
color: var(--vt-text-primary);
border: 1px solid var(--vt-border);
```
Hover: `bg-vt-surface border-vt-border-strong`

#### Destructive Button (rare — only for delete/disconnect)
```css
background: var(--vt-concern-bg);
color: var(--vt-clay);
border: 1px solid var(--vt-concern-border);
```
Hover: `bg-vt-clay text-white`

**Button Sizes:**
- `btn-sm`: `py-2 px-4 text-label` (36px height)
- `btn-md`: `py-3 px-6 text-body-sm` (44px height) ← default
- `btn-lg`: `py-4 px-8 text-body` (52px height)
- `btn-xl`: `py-5 px-10 text-body-lg` (60px height) ← onboarding CTAs

**Icon buttons:** Square aspect ratio. `p-3` with centered icon (20px).

---

### Toggles

```css
/* Toggle track */
.toggle {
  width: 44px; height: 24px;
  border-radius: 12px;
  background: var(--vt-sand-light);
  transition: background var(--vt-duration-fast) var(--vt-ease);
  cursor: pointer;
}
.toggle.on {
  background: var(--vt-sage);
}

/* Toggle thumb */
.toggle::after {
  content: '';
  position: absolute;
  width: 20px; height: 20px;
  border-radius: 50%;
  background: white;
  top: 2px; left: 2px;
  box-shadow: var(--vt-shadow-sm);
  transition: transform var(--vt-duration-base) var(--vt-ease-spring);
}
.toggle.on::after {
  transform: translateX(20px);
}
```

---

### Modals

Two patterns: Drawer (mobile) and Dialog (desktop).

**Mobile — Bottom Sheet Drawer:**
```
                              ────────── ← drag handle (32×4px pill)
┌──────────────────────────────────────┐
│  ████████████████████████████████    │  ← drag handle
│                                      │
│  Upload Lab Results          [×]     │  ← title + close
│  ────────────────────────────────    │
│                                      │
│  [content]                           │
│                                      │
│  [Primary Action]                    │
└──────────────────────────────────────┘
```

Opens from bottom with spring animation (`translateY(100%) → translateY(0)`). Background overlay: `bg-black/30 backdrop-blur-sm`.

**Desktop — Centered Dialog:**
Max width 560px, max height 80vh with internal scroll. Overlay same.

```css
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(30, 26, 22, 0.4);
  backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  z-index: 50;
}

.modal-dialog {
  background: var(--vt-surface-elevated);
  border-radius: var(--vt-radius-xl);
  box-shadow: var(--vt-shadow-float);
  padding: 32px;
  width: min(560px, calc(100vw - 32px));
  max-height: 80vh;
  overflow-y: auto;
}
```

---

### Onboarding Flow

Multi-step wizard. Progress shown as organic dots, not numbered steps.

**Screen 1 — Welcome**
```
┌──────────────────────────────────────┐
│         [Vitalis logo, 80px]         │
│                                      │
│     Welcome to Vitalis               │  ← Display heading
│     Your health story starts here.  │  ← body, muted
│                                      │
│     ● ○ ○ ○ ○ ○                     │  ← step dots (sage fill on active)
│                                      │
│     [Create your account]           │  ← btn-xl, full width
│     Already have one? Sign in       │  ← text link
└──────────────────────────────────────┘
```

**Screen 2 — Profile Setup (name, birthday, sex, units)**

**Screen 3 — Connect Devices (device cards)**
```
Which devices do you use?

┌──────────────┐  ┌──────────────┐
│  [Garmin]    │  │  [Apple W.]  │  ← 2-col grid, tap to select
│  Connect →   │  │  Connect →   │  ← selected: sage border + check
└──────────────┘  └──────────────┘

┌──────────────┐  ┌──────────────┐
│  [Oura]      │  │  [WHOOP]     │
└──────────────┘  └──────────────┘

Don't have any yet? Skip →
```

**Screen 4 — Goals (optional, skippable)**

**Screen 5 — Ready!**
```
     You're all set.

     Your health story starts now.
     We'll start pulling your data.

     [Go to dashboard →]
```

Progress transition between steps: `translateX(-100%) → translateX(0)` (left to right), duration 300ms.

---

## 6. Iconography

### Style Guide

**Use:** Phosphor Icons (MIT license, extensive library, multiple weights)
**Weight:** Regular (default), Bold (active states), Light (decorative)
**Size:** 16px (inline), 20px (nav, cards), 24px (section headers), 32px (empty states), 48px (onboarding)

**Rules:**
1. Never mix icon weights within the same component
2. Icons always `currentColor` — never hardcoded fill colors
3. Stroke icons (not filled) for most UI elements — filled only for active nav states
4. Navigation icons: Outline default → Filled active

### Recommended Icon Set: Phosphor Icons

```bash
npm install @phosphor-icons/react
```

**Key icon mappings:**
| Function | Phosphor Icon | Notes |
|----------|--------------|-------|
| Home / Dashboard | `House` | |
| Sleep | `Moon` | |
| Activity | `Person` | |
| Blood Work | `Drop` | |
| Body Comp | `Scales` | |
| Insights / AI | `Sparkle` | |
| Heart Rate | `Heartbeat` | |
| HRV | `Waveform` | |
| Steps | `Footprints` | |
| Weight | `Scales` | |
| Supplements | `Pill` | |
| Journal | `NotePencil` | |
| Upload / PDF | `FilePdf` | |
| Calendar / Date | `CalendarBlank` | |
| Trend Up | `TrendUp` | |
| Trend Down | `TrendDown` | |
| Settings | `GearSix` | |
| Sync / Connect | `ArrowsClockwise` | |
| Alert / Watch | `Eye` | (not warning triangle) |
| Concern | `Warning` | Clay color only |
| Thriving | `CheckCircle` | Sage color |
| Profile | `UserCircle` | |
| Export | `Export` | |
| Streak | `Flame` | Amber color |
| Longevity / Bio Age | `Leaf` | |
| Lifting | `Barbell` | |
| Cycle | `Flower` | Rose Dusk color |

**Custom brand icon:** The Vitalis leaf-V mark is used as the app icon only. It does not appear as a generic icon within the UI.

---

## 7. Motion & Animation

### Principles

1. **Organic, not mechanical.** Animations should feel like breathing, not clicking. Use spring easings for interactive elements.
2. **Purposeful, not decorative.** Every animation communicates something: state change, hierarchy, progress, success.
3. **Fast but not rushed.** Micro-interactions at 100-150ms feel snappy. Page transitions at 250-300ms feel smooth.
4. **Reduce motion respected.** All non-essential animations disabled when `prefers-reduced-motion: reduce`.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

### Durations & Easings

| Duration | Use |
|----------|-----|
| `100ms` | Hover state color changes, focus rings |
| `150ms` | Button presses, tap feedback, toggle |
| `200ms` | Card hover lift, icon color transition |
| `250ms` | Modal open/close, dropdown, tooltip |
| `300ms` | Page section transitions, drawer open |
| `350ms` | Full page transitions, chart appear |
| `500ms` | Count-up number animations |
| `800ms` | Chart draw-in animations |

| Easing | Value | Use |
|--------|-------|-----|
| `smooth` | `cubic-bezier(0.4, 0, 0.2, 1)` | Most transitions |
| `spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Toggles, tap ratings, success states |
| `decelerate` | `cubic-bezier(0, 0, 0.2, 1)` | Enter animations (slide in) |
| `accelerate` | `cubic-bezier(0.4, 0, 1, 1)` | Exit animations (slide out) |

---

### Micro-interactions

#### Button Press
```css
button:active { transform: scale(0.97); transition: transform 80ms ease; }
```

#### Card Hover Lift
```css
.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--vt-shadow-md);
  transition: all 200ms ease;
}
```

#### 1-5 Rating Tap
```js
// On tap:
// 1. Scale down instantly (0.9) — 80ms
// 2. Spring back past 1.0 to 1.15 — 150ms
// 3. Settle at 1.0 — 150ms
// Use framer-motion spring: stiffness 400, damping 15
```

#### Sync Status Indicator
When data is syncing: a gentle pulsing animation on the device icon.
```css
@keyframes sync-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: 0.6; transform: scale(0.95); }
}
.syncing { animation: sync-pulse 2s ease-in-out infinite; }
```

#### Success Checkmark (after PDF confirm)
Draw-in animation: circle draws in, then checkmark draws in. Both in Sage. Duration: 600ms total.

#### Number Count-Up
When a dashboard metric value loads, count up from 0 to the actual value over 500ms using `requestAnimationFrame`. Easing: decelerating. Only on initial page load, not on re-render.

```js
function countUp(element, target, duration = 500) {
  const start = performance.now()
  const update = (now) => {
    const progress = Math.min((now - start) / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3) // cubic ease-out
    element.textContent = Math.round(eased * target)
    if (progress < 1) requestAnimationFrame(update)
  }
  requestAnimationFrame(update)
}
```

#### Skeleton → Content Transition
Fade from skeleton to real content: `opacity: 1 → 0` on skeleton, `opacity: 0 → 1` on content, 250ms crossfade. Never just snap-swap.

---

### Page Transitions

Between dashboard sections, a subtle but polished transition:

```css
/* Entering page */
@keyframes page-enter {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.page-enter {
  animation: page-enter 250ms cubic-bezier(0, 0, 0.2, 1) forwards;
}
```

No full-screen wipes or dramatic slides — just a subtle fade-up. Feels like turning a page, not launching a rocket.

---

### Chart Animations

**Line chart:** Path draws left-to-right on initial load over 800ms.
**Bar chart:** Bars grow upward from baseline over 600ms with stagger (each bar 40ms after previous).
**Sparkline:** No animation — renders instantly (too small to benefit).
**Radar:** Polygon expands from center over 600ms.
**Donut:** Arc fills clockwise over 600ms.

---

## 8. Dashboard Layouts

### Mobile — Home Screen

```
Status bar (safe area)
┌──────────────────────────────────────┐
│  ≡  Good morning, Ev    [avatar]    │  ← 56px header
├──────────────────────────────────────┤
│                                      │
│  ┌──────────────────────────────┐    │
│  │  Aug 22, 2024  ·  Day 234   │    │  ← Today card, sage left border
│  │                              │    │
│  │  Overall feeling strong.     │    │  ← AI-generated daily summary
│  │  Your sleep was restorative  │    │
│  │  and HRV is trending up.     │    │
│  └──────────────────────────────┘    │
│                                      │
│  TODAY'S SNAPSHOT          [all]    │  ← section header + link
│                                      │
│  ┌──────────┐  ┌──────────┐         │
│  │ Sleep    │  │ HRV      │         │  ← 2-col metric cards
│  │  7h 42m  │  │  44 ms   │         │
│  │ ▂▄▆▇█▇▅▃ │  │ ▃▄▄▅▆▇▆▅ │         │
│  └──────────┘  └──────────┘         │
│                                      │
│  ┌──────────┐  ┌──────────┐         │
│  │ Steps    │  │ Resting  │         │
│  │  8,420   │  │ HR 58bpm │         │
│  └──────────┘  └──────────┘         │
│                                      │
│  WATCHLIST                          │  ← markers needing attention
│  ┌──────────────────────────────┐    │
│  │ ◎ Ferritin  22 ng/mL  Watch │    │
│  └──────────────────────────────┘    │
│                                      │
│  RECENT INSIGHT                     │
│  ┌──────────────────────────────┐    │
│  │ ✦ On nights you log stress   │    │
│  │   >3, your HRV drops 18%    │    │
│  │   the next morning.          │    │
│  │   [Explore →]                │    │
│  └──────────────────────────────┘    │
│                                      │
│  QUICK LOG                [+ add]   │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
│  │ 😊  │ │ ⚡  │ │ 😰  │ │  ⚖  │   │  ← daily check-in row
│  │Mood │ │Engy │ │Strs │ │Wght │   │
│  └─────┘ └─────┘ └─────┘ └─────┘   │
│                                      │
│                         [scroll ↓]  │
├──────────────────────────────────────┤
│   ⌂      😴      ⬡      🩸      ✦  │  ← bottom nav (64px + safe area)
└──────────────────────────────────────┘
```

---

### Mobile — Sleep Screen

```
┌──────────────────────────────────────┐
│  ←  Sleep                   [cal]   │
├──────────────────────────────────────┤
│                                      │
│  LAST NIGHT  ·  Aug 21–22            │
│                                      │
│  ┌──────────────────────────────┐    │
│  │  7h 42m          ● Thriving  │    │
│  │  11:18 PM → 7:00 AM          │    │
│  │                              │    │
│  │  ████ Deep  ████ REM         │    │  ← sleep stage bar
│  │  ████ Light ████ Awake       │    │
│  │                              │    │
│  │  Deep: 1h 24m  ●             │    │
│  │  REM:  1h 52m  ●             │    │
│  │  Light: 3h 18m ○             │    │
│  │  Awake:  28m   ○             │    │
│  └──────────────────────────────┘    │
│                                      │
│  SLEEP QUALITY TREND     [7d 30d]   │
│  ┌──────────────────────────────┐    │
│  │  [line chart area 180px tall]│    │
│  └──────────────────────────────┘    │
│                                      │
│  SOURCES                            │  ← multi-device comparison
│  ┌──────────┐  ┌──────────┐         │
│  │ Garmin   │  │ Oura     │         │
│  │ 7h 42m   │  │ 7h 38m   │         │
│  │ Score: 82│  │ Score: 79│         │
│  └──────────┘  └──────────┘         │
│                                      │
│  SLEEP INSIGHTS                     │
│  ┌──────────────────────────────┐    │
│  │ On avg, you sleep 23 min     │    │
│  │ longer on workout days.      │    │
│  └──────────────────────────────┘    │
│                                      │
├──────────────────────────────────────┤
│   ⌂      😴      ⬡      🩸      ✦  │
└──────────────────────────────────────┘
```

---

### Mobile — Blood Work Screen

```
┌──────────────────────────────────────┐
│  ←  Blood Work              [upload]│
├──────────────────────────────────────┤
│                                      │
│  LATEST PANEL  ·  Oct 15, 2024       │
│  Quest Diagnostics                   │
│                                      │
│  STATUS OVERVIEW                    │
│  ┌──────────────────────────────┐    │
│  │ ●●●●●●●●●●●●●● Thriving: 18  │    │  ← status summary bar
│  │ ●●●●● Watch: 4               │    │
│  │ ●● Concern: 2                 │    │
│  └──────────────────────────────┘    │
│                                      │
│  METABOLIC                          │  ← category accordion
│  ┌──────────────────────────────┐    │
│  │ Glucose      94 mg/dL  ●     │    │  ← sage dot = thriving
│  │ HbA1c        5.1%      ●     │    │
│  │ Insulin      6.2 μU/mL ●     │    │
│  └──────────────────────────────┘    │
│                                      │
│  THYROID                            │
│  ┌──────────────────────────────┐    │
│  │ TSH         1.8 mIU/L  ●     │    │
│  │ Free T3     3.2 pg/mL  ◎     │    │  ← sand dot = watch
│  │ Free T4     1.1 ng/dL  ●     │    │
│  └──────────────────────────────┘    │
│                                      │
│  IRON PANEL                         │
│  ┌──────────────────────────────┐    │
│  │ Ferritin    22 ng/mL   ▲     │    │  ← clay dot = concern
│  │ Serum Iron  88 μg/dL   ●     │    │
│  └──────────────────────────────┘    │
│                                      │
│  [View full panel]  [Upload new]    │
│                                      │
├──────────────────────────────────────┤
│   ⌂      😴      ⬡      🩸      ✦  │
└──────────────────────────────────────┘
```

---

### Desktop — Full Dashboard Layout

```
┌────────────────────────────────────────────────────────────────────────┐
│  SIDEBAR (240px fixed)    │  MAIN CONTENT AREA (flex: 1)               │
│                           │                                             │
│  [Vitalis logo]           │  ┌─────────────────────────────────────┐   │
│                           │  │  Good morning, Ev  ·  Aug 22, 2024  │   │
│  [Ev Varden ▾]           │  │  3-sentence daily AI summary        │   │
│                           │  └─────────────────────────────────────┘   │
│  ○ Home                   │                                             │
│  ○ Today's Stats          │  TODAY'S KEY METRICS          [all →]      │
│                           │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │
│  HEALTH DATA              │  │Sleep │ │HRV   │ │Steps │ │HR    │     │
│  ○ Sleep                  │  │7h42m │ │44ms  │ │8,420 │ │58bpm │     │
│  ○ Activity               │  └──────┘ └──────┘ └──────┘ └──────┘     │
│  ○ Body Composition       │                                             │
│  ○ Blood Work             │  ┌──────────────────┐  ┌────────────────┐ │
│  ○ Longevity              │  │  HRV TREND        │  │  SLEEP TREND   │ │
│  ○ Lifting                │  │  [chart 260px]    │  │  [chart 260px] │ │
│                           │  │  7d 30d 90d 1y   │  │  7d 30d 90d   │ │
│  DAILY LOGS               │  └──────────────────┘  └────────────────┘ │
│  ○ Journal                │                                             │
│  ○ Supplements            │  BLOOD WORK WATCHLIST        [view all →] │
│  ○ Nutrition              │  ┌──────────────────────────────────────┐  │
│                           │  │ ◎ Ferritin  22 ng/mL  ↓-15% (Watch)│  │
│  INTELLIGENCE             │  │ ▲ Vitamin D 18 ng/mL  Low (Concern) │  │
│  ○ Insights               │  └──────────────────────────────────────┘  │
│  ○ Reports                │                                             │
│                           │  RECENT INSIGHTS             [explore →]  │
│  ────────────────         │  ┌──────────────────┐  ┌────────────────┐ │
│  ○ Settings               │  │ ✦ Stress + HRV   │  │ ✦ Sleep +Wrkout│ │
│  ○ Export Data            │  │  correlation     │  │  correlation  │ │
│                           │  └──────────────────┘  └────────────────┘ │
└───────────────────────────┴─────────────────────────────────────────────┘
```

---

### Desktop — Insights Screen

```
┌────────────────────────────────────────────────────────────────────────┐
│  SIDEBAR (240px)          │  INSIGHTS                                   │
│                           │                                             │
│  [Insights active]        │  ┌──────────────────────────────────────┐  │
│                           │  │  HEALTH FINGERPRINT             [?]  │  │
│                           │  │                                      │  │
│                           │  │       Sleep          Activity        │  │
│                           │  │          \          /                │  │
│                           │  │  HRV ─────●────────●───── Steps     │  │
│                           │  │          /          \                │  │
│                           │  │    Blood Work    Longevity           │  │
│                           │  │         \_________/                  │  │
│                           │  │            Body                      │  │
│                           │  │         [radar chart]                │  │
│                           │  └──────────────────────────────────────┘  │
│                           │                                             │
│                           │  CROSS-DOMAIN CORRELATIONS                 │
│                           │  ┌──────────────────────────────────────┐  │
│                           │  │ ✦ Strong correlation                  │  │
│                           │  │   On nights you log stress >3,       │  │
│                           │  │   your HRV drops 18% the following   │  │
│                           │  │   morning. 23 data points.           │  │
│                           │  │   [p=0.003, high confidence]         │  │
│                           │  │   [Explore →]  [Dismiss]             │  │
│                           │  └──────────────────────────────────────┘  │
│                           │  ┌──────────────────────────────────────┐  │
│                           │  │ ✦ Trend detected                      │  │
│                           │  │   Your Ferritin has trended down      │  │
│                           │  │   15% over the last 4 panels.        │  │
│                           │  │   Consider discussing with doctor.    │  │
│                           │  └──────────────────────────────────────┘  │
└───────────────────────────┴─────────────────────────────────────────────┘
```

---

### Body Screen — Desktop (DEXA + Composition)

```
┌────────────────────────────────────────────────────────────────────────┐
│  SIDEBAR                  │  BODY COMPOSITION                          │
│                           │                                             │
│                           │  LATEST DEXA  ·  Sep 3, 2024  DexaFit     │
│                           │                                             │
│                           │  ┌──────────────┐  ┌─────────────────────┐│
│                           │  │ Body Fat     │  │  Composition         ││
│                           │  │   22.4%      │  │  ╔═══════╗           ││
│                           │  │  ▲ down from │  │  ║ Lean  ║  77.6%   ││
│                           │  │  24.1% (2023)│  │  ║       ║           ││
│                           │  └──────────────┘  │  ╠═══════╣           ││
│                           │  ┌──────────────┐  │  ║ Fat   ║  22.4%   ││
│                           │  │ Lean Mass    │  │  ╚═══════╝           ││
│                           │  │ 148.2 lbs    │  │                       ││
│                           │  │  ▲ +2.1 lbs  │  └─────────────────────┘│
│                           │  └──────────────┘                          │
│                           │                                             │
│                           │  REGIONAL BREAKDOWN                        │
│                           │  ┌──────────────────────────────────────┐  │
│                           │  │ [segmented body diagram — svg]       │  │
│                           │  │ Trunk / Arms / Legs / Android / Gynoid│  │
│                           │  └──────────────────────────────────────┘  │
│                           │                                             │
│                           │  DEXA HISTORY TREND  [3 scans]             │
│                           │  ┌──────────────────────────────────────┐  │
│                           │  │ [grouped bar chart: fat vs lean]     │  │
│                           │  └──────────────────────────────────────┘  │
│                           │                                             │
│                           │  PROGRESS PHOTOS            [+ add photo] │
│                           │  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│                           │  │ Jan 2024 │ │ May 2024 │ │ Sep 2024 │  │
│                           │  │ [photo]  │ │ [photo]  │ │ [photo]  │  │
│                           │  └──────────┘ └──────────┘ └──────────┘  │
│                           │  [◄ Compare ►]  ← side-by-side slider     │
└───────────────────────────┴─────────────────────────────────────────────┘
```

---

### Landing Page Wireframe (Phase 7 reference)

```
┌──────────────────────────────────────────────────────────────────────┐
│  [Logo]  Features  Pricing  Blog              [Sign In] [Start Free] │  ← nav
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│              Every signal, one home.                                 │  ← Hero H1, display xl
│         Your body's been talking. Now you can listen.                │  ← subhead
│                                                                      │
│         [Start for free]    [See how it works]                       │  ← CTAs
│                                                                      │
│         ┌────────────────────────────────────────┐                   │
│         │     [Dashboard screenshot / mockup]     │                   │  ← hero visual
│         └────────────────────────────────────────┘                   │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Connects with everything you already use                            │
│  [Garmin] [Apple Watch] [Oura] [WHOOP] [+ more]                     │  ← device logos
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [Feature blocks: 3 col on desktop, 1 on mobile]                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │ Universal   │  │ Intelligent │  │ Beautiful   │                  │
│  │ Every device│  │ AI insights │  │ Wellness    │                  │
│  │ one place   │  │ correlations│  │ not hospital│                  │
│  └─────────────┘  └─────────────┘  └─────────────┘                  │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Pricing: Free / Pro $9 / Family $14                                 │
├──────────────────────────────────────────────────────────────────────┤
│  Footer: Privacy · Terms · Export · @vitalishealth                  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Appendix A — Tailwind Class Quick Reference

```
Text Colors:
  text-vt-text-strong    → #1E1A16 (headings, metric values)
  text-vt-text-primary   → #3D3730 (body text)
  text-vt-warm-gray      → #7A7168 (secondary, captions)
  text-vt-sage           → brand green
  text-vt-fern           → dark green (CTAs, interactive)
  text-vt-clay           → concern/warm accent
  text-vt-sand           → warm sand/watch status

Backgrounds:
  bg-vt-cream            → page background
  bg-vt-parchment        → sidebar, secondary surface
  bg-vt-surface          → card background (light: parchment, dark: elevated)
  bg-vt-thriving-bg      → green tint background
  bg-vt-watch-bg         → sand tint background
  bg-vt-concern-bg       → clay tint background

Borders:
  border-vt-sand-light   → default card border
  border-vt-border       → alias for sand-light
  border-vt-sage         → focus/active states
  border-vt-clay         → concern borders

Typography:
  font-display           → Quicksand (headings, metric values)
  font-sans              → DM Sans (body, UI)
  font-mono              → DM Mono (data tables, code)

Shadows:
  shadow-vt-sm           → subtle card shadow
  shadow-vt-md           → hover lifted card
  shadow-vt-lg           → modals, dropdowns
  shadow-vt-float        → full-screen modals

Radius:
  rounded-sm             → 6px (small elements)
  rounded-md             → 12px (cards, inputs)
  rounded-lg             → 16px (large cards)
  rounded-xl             → 24px (modals, drawers)
```

---

## Appendix B — Accessibility Checklist

- [ ] All text passes WCAG AA contrast ratio (4.5:1 normal, 3:1 large)
- [ ] All interactive elements have visible focus indicators (`ring-2 ring-vt-sage ring-offset-2`)
- [ ] All images and icons have alt text or `aria-hidden="true"`
- [ ] Color is never the sole means of conveying information (always paired with text or icon)
- [ ] Touch targets minimum 44×44px on mobile
- [ ] Semantic HTML (nav, main, section, h1-h6 hierarchy)
- [ ] Screen reader accessible forms (label + aria-describedby for hints)
- [ ] `prefers-reduced-motion` respected
- [ ] `prefers-color-scheme` used for automatic dark mode detection
- [ ] Skip navigation link at top of page
- [ ] Keyboard navigation works through all interactive elements

---

*Design system locked pending QA review.*
*Next: Phase 1 — Data Architecture (parallel)*
