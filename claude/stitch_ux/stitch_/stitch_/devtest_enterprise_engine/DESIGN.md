---
name: DevTest Enterprise Engine
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#414755'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#727786'
  outline-variant: '#c1c6d7'
  surface-tint: '#0059c7'
  primary: '#0057c2'
  on-primary: '#ffffff'
  primary-container: '#006ef2'
  on-primary-container: '#fefcff'
  inverse-primary: '#afc6ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#256a00'
  on-tertiary: '#ffffff'
  tertiary-container: '#308600'
  on-tertiary-container: '#f8ffee'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d9e2ff'
  primary-fixed-dim: '#afc6ff'
  on-primary-fixed: '#001a43'
  on-primary-fixed-variant: '#004398'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#88fd54'
  tertiary-fixed-dim: '#6de039'
  on-tertiary-fixed: '#062100'
  on-tertiary-fixed-variant: '#1a5200'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system targets modern software engineers, QA automation specialists, and engineering managers who require an authoritative, reliable, and high-velocity testing operations environment. It draws directly from enterprise design language (modern Corporate / B2B SaaS inspired by Ant Design 5.0 and Arco Design), balancing structural clarity with engineering precision.

### Character & Tone
- **Technical Rigor & Dependability:** Clean, razor-sharp visual rhythm without unnecessary visual noise. Focuses on data scanning, fast decision-making, and execution confidence.
- **Dual-Pane Contrast:** High-contrast dark navigation anchor on the left (`#141414` / `#1f1f1f`) creates an immersive tool-like shell, while the main work canvas stays crisp, bright, and legible (`#f8fafc` / `#ffffff`).
- **Dense yet Airy Information Architecture:** Prioritizes dense tables, comprehensive breadcrumbs, tabbed navigation counters, and rich metadata tags (suites, priorities, system scopes) while retaining sufficient breathing room to prevent cognitive fatigue.

## Colors

The palette leverages a split dual-mode architecture: an inverted sidebar chrome paired with a high-efficiency light canvas for the test workbench.

### Primary & Functional Accents
- **Primary Brand (`#1677ff`):** Engineering blue for key CTA triggers, active primary tabs, selected table pagination, and focus outlines.
- **Secondary Shell (`#141414` base, `#1f1f1f` surface, `#2a2a2a` active):** Anchors the side navigation, group section titles, and user profile badge tray.
- **Success (`#52c41a` / Light Tint `#f6ffed` / Border `#b7eb8f`):** Automated test runs passed, health checks 100%, active integration sync.
- **Warning / P1 Priority (`#fa8c16` / `#faad14` / Light Tint `#fffbe6`):** Critical test suites, pending approvals, intermediate risk items.
- **Danger / Error (`#ff4d4f` / Light Tint `#fff2f0` / Border `#ffccc7`):** Assertion failure, failed runs, deletion/destructive modal triggers.
- **Informational & System Metadata:**
  - Violet/Purple (`#722ed1` / Tint `#f9f0ff`): Microservice & orchestrator labels (`fin`, `auth`, `order`).
  - Cyan/Teal (`#13c2c2` / Tint `#e6fffb`): Environment indicators and mocking endpoints.

### Neutral Scale (Light Canvas)
- **Canvas Base:** `#f8fafc`
- **Card / Surface Container:** `#ffffff`
- **Dividers & Table Borders:** `#e2e8f0` (secondary dividers at `#f1f5f9`)
- **Text Primary:** `#0f172a`
- **Text Secondary / Metadata:** `#64748b`
- **Text Disabled / Watermark:** `#94a3b8`

## Typography

The typographical hierarchy is engineered for high-density tabular records, code-level schema paths, and UI controls.

- **Primary UI & Text (`Inter`):** Applied across global controls, headers, buttons, navigation items, and descriptions. Provides exceptional horizontal density and vertical alignment with Asian and Latin character mixing.
- **Code & Identifier Labels (`JetBrains Mono`):** Applied to scenario IDs (`sc-scenario-icxz4vrk3`), JSON expressions (`$.headers.X-Trace-Id`), HTTP verbs, status codes, and environment parameters.
- **Numeric Counters:** Tab badges (e.g. `场景 2`, `用例集 0`) use tabular figures (`font-variant-numeric: tabular-nums`) to prevent horizontal jitter during dynamic queries and updates.

## Layout & Spacing

### Layout Structure
- **Sidebar (Fixed Chrome):** Fixed at `240px` expanded width, collapsible to `64px`. Anchored to the left with dark background `#141414`, full height (`100vh`), internal vertical scroll.
- **Workspace Canvas (Fluid Grid):** Extends across the remainder of the viewport (`calc(100vw - 240px)`). The outer container uses `1.5rem` (`24px`) margin on standard enterprise displays (`1440px+`) and scales to `1rem` on compact displays (`1024px`).
- **Header & Breadcrumbs Zone:** Fixed top operational bar housing project title, global status, and sub-module navigation tabs (`场景`, `用例集`, `集成任务`, `配置`).
- **Toolbar & Filter Zone:** Compact horizontal bar featuring search inputs (`320px` max), quick filter segmented controls, preset selectors, and primary action buttons.
- **Data Table Layout:** Full-width fluid table with fixed action column pinned to the right. Header height strictly `40px`, content row height `52px` (standard density) or `40px` (high-density compact mode).

## Elevation & Depth

This system avoids heavy drop shadows and decorative 3D effects, opting for structural lines, border contrasts, and crisp ambient shadows for overlay layers.

- **Level 0 (Canvas Base):** Flat `#f8fafc`.
- **Level 1 (Card & Content Blocks):** Pure `#ffffff` surface enclosed by a fine, low-contrast border `1px solid #e2e8f0` with a subtle surface glow `0 1px 2px 0 rgba(0, 0, 0, 0.03)`.
- **Level 2 (Dropdowns, Popovers, & Select Panels):** Pinned under triggers with `0 4px 12px rgba(15, 23, 42, 0.08)`, border `1px solid #cbd5e1`.
- **Level 3 (Modal Dialogs & Side Drawers):** Centered floating modals and sliding scenario debug panels utilize `0 12px 32px rgba(15, 23, 42, 0.14)` combined with backdrop blur `rgba(15, 23, 42, 0.45)`.
- **Dark Sidebar Active Indicator:** Side navigation uses tonal depth `#1f1f1f` with a subtle white inset highlight or an active left border indicator in primary blue (`3px solid #1677ff`).

## Shapes

The design uses a clean, compact corner radius scale (`roundedness: 1`, default base radius `4px` / `0.25rem` up to `8px` for larger cards). This maintains maximum visual discipline for data grids, badges, and input groups.

- **Inputs, Buttons, and Selects:** `4px` (`0.25rem`) rounded corners.
- **Tags, Badges, and Pill Metadata:** `4px` radius for standard rectangular enterprise tags (`fin`, `P1`, `订单`), or `12px` for counter badges.
- **Main White Containers / Table Enclosures:** `8px` (`0.5rem`) for high-level module borders.
- **Modal Dialogs & Tooltips:** `8px` for modals, `4px` for dark tooltips.

## Components

### 1. Navigation & Sidebar
- **Group Headings:** `12px` uppercase tracking, color `#64748b`, with `12px` vertical padding.
- **Nav Items:** `36px` height, horizontal padding `12px`, SVG icon `16px`. Idle text `#94a3b8`, hover surface `rgba(255, 255, 255, 0.06)`, active state filled with `rgba(22, 119, 255, 0.15)` and text `#1677ff`.

### 2. Buttons
- **Primary:** Background `#1677ff`, hover `#4096ff`, text `#ffffff`. Height `32px` (compact) or `36px` (regular), padding `0 16px`, font weight `500`.
- **Secondary / Default:** Background `#ffffff`, border `1px solid #d9d9d9`, text `#0f172a`. Hover border `#1677ff` and text `#1677ff`.
- **Dashed / Outline:** Border `1px dashed #d9d9d9` for quick add triggers (e.g. `+ 存为分组`, `+ 添加成员`).
- **Icon / Ghost:** Flat background, `#64748b` icon; used for inline row actions (`...` options, favorite star).

### 3. Tabs & Counters
- Horizontal line tabs with an active underline indicator (`2px solid #1677ff`).
- Active tab text `#1677ff` (weight `600`), inactive `#64748b` (weight `400`).
- Numerical badge directly follows label with a font size of `12px` in subtle gray `#94a3b8`.

### 4. Form Inputs & Search Fields
- Integrated prefix icons (magnifying glass, filter). Height `32px` or `36px`.
- Border `1px solid #d9d9d9`, transition `all 0.2s ease`. Focus creates a `2px` ring halo `rgba(22, 119, 255, 0.2)` with border `#1677ff`.
- Placeholder text in `#94a3b8`.

### 5. Badges & Entity Tags
- **Microservice Tag:** Light purple background `#f9f0ff`, border `1px solid #d3adf7`, text `#722ed1`, monospaced font.
- **Priority Tag (P1):** Light amber background `#fffbe6`, border `1px solid #ffe58f`, text `#fa8c16`, bold font weight `600`.
- **Category Tag:** Cool gray background `#f1f5f9`, border `1px solid #e2e8f0`, text `#475569`.

### 6. Data Tables
- Header row uses subtle `#fafafa` background with uppercase `12px` font weight `600`, color `#475569`, border bottom `1px solid #e2e8f0`.
- Data rows have alternating subtle hover background `#f8fafc`.
- Fixed action columns include vertical divider separator on horizontal scroll overflow.

### 7. Empty States & Feedback
- Centered layout with muted gray icon, concise heading (`14px`, `#64748b`), accompanied by contextual guidance or quick primary creation CTA.