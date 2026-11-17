---
name: Gateway Observability & Mesh Console
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
  on-surface-variant: '#434655'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#005e6e'
  on-tertiary: '#ffffff'
  tertiary-container: '#00788c'
  on-tertiary-container: '#d7f6ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#acedff'
  tertiary-fixed-dim: '#4cd7f6'
  on-tertiary-fixed: '#001f26'
  on-tertiary-fixed-variant: '#004e5c'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 22px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
  body-lg:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-md:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: '0'
  code-inline:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
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
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system establishes a high-density, mission-critical workspace for infrastructure architects, platform engineers, and site reliability teams managing complex distributed microservices and API gateways. 

The aesthetic is Modern Technical Minimalism engineered for high cognitive throughput. It couples a focused, commanding dark slate navigational core with an ultra-clean, clinical canvas optimized for scanning complex nested schemas, routing configurations, and real-time operational states. Visual noise is aggressively eliminated in favor of strict spatial cadence, structural borders, and purposeful chromatic status signals. The experience feels engineered, indestructible, and ultra-responsive—delivering immediate comprehension of the platform’s 3-tier hierarchy: Service Definition, Instance Deployment, and Alias & Credentials.

## Colors

The palette balances deep architectural chrome against a surgical daylight data canvas, using functional accents to encode operational reality:

- **Primary Canvas & Chrome:**
  - Sidebar & Deep System Shell: `#0f172a` (Slate 900) grounding primary nav and workspace contexts, paired with `#1e293b` (Slate 800) for active states and nested tree branches.
  - Worksurface Canvas: `#f8fafc` (Slate 50) base canvas, structured with pure white `#ffffff` panels for elevated data cards and tables.
  - System Boundaries: `#e2e8f0` (Slate 200) for structural lines, cell borders, and division grids. `#cbd5e1` (Slate 300) for interactive control borders.

- **Primary Interactive:**
  - Interactive Action & Focus: `#2563eb` (Blue 600) default, `#1d4ed8` (Blue 700) hover, with `#3b82f6` (Blue 500) dedicated to dark-chrome highlights and pathway traces.

- **Domain Semantics & 3-Tier Status Signifiers:**
  - *Ready / Operational:* Emerald `#10b981` (background: `#ecfdf5`, text: `#065f46`).
  - *Pending / Plate Sync / Warning:* Amber `#f59e0b` (background: `#fffbeb`, text: `#92400e`).
  - *Alias / Credentials / Key Auth:* Indigo/Purple `#8b5cf6` (background: `#f5f3ff`, text: `#5b21b6`).
  - *Environment Scope (Test/Staging/Prod):* Cyan/Sky `#06b6d4` (background: `#ecfeff`, text: `#155e75`).

## Typography

Typography prioritizes tabular legibility and rapid structural parsing. `Geist` provides an authoritative, neutral geometric backbone for interface structures, forms, and service definitions. `JetBrains Mono` handles technical telemetry, routing aliases, IP blocks, cryptographic fingerprint hashes, and environment variables.

- **Numerics & Tabular Figures:** All numeric rendering in tables, metric tickers, and status latency indicators must use font-variant-numeric: `tabular-nums` to ensure strict vertical column alignment across changing datasets.
- **Hierarchy Differentiation:** Primary service names use `headline-lg` (SemiBold), while nested Instance Deployments step down to `headline-md` paired with `label-sm` environment badges. Alias keys, URLs, and token hashes strictly default to `label-md` or `code-inline`.

## Layout & Spacing

The layout uses a docked application shell: a persistent 260px dark slate navigation sidebar anchored on the left, an auxiliary contextual tree sidebar (optional 300px collapsible panel for service hierarchies), and a fluid primary canvas.

- **Grid Discipline:** Main operational views use a fluid 12-column grid with a tight `1rem` (16px) gutter and `1.5rem` (24px) outer page margins. 
- **Density Profile:** Compact and data-dense. Component gaps adhere strictly to `space-xs` (4px) and `space-sm` (8px) for related form metadata, and `space-md` (12px) to `space-lg` (16px) between modular card panels.
- **Form Factor Adaptations:**
  - *Desktop (≥1440px):* Full 3-tier view showing Service Definition list, nested Instance nodes, and side-peek credential inspection drawers simultaneously.
  - *Tablet (1024px–1439px):* Left navigation collapses to an icon-only 64px rail; service tier renders as drill-down stacked master-detail views.
  - *Mobile (<1024px):* Administrative operations are view-only; grids collapse to a single column with scrollable horizontal tabular matrices.

## Elevation & Depth

Visual hierarchy is communicated via clean structural boundaries and deliberate surface tonal stepping, avoiding heavy, muddy drop shadows.

- **Level 0 (Canvas Base):** `#f8fafc` — host canvas for the entire platform interface.
- **Level 1 (Card & Row Surfaces):** Pure `#ffffff` framed by a 1px solid border of `#e2e8f0`. Zero ambient shadow in resting state.
- **Level 2 (Active / Hover / Popovers):** Pure `#ffffff` surface, border shifted to `#cbd5e1`, supported by a subtle, tight ambient shadow: `0 4px 6px -1px rgba(15, 23, 42, 0.05), 0 2px 4px -2px rgba(15, 23, 42, 0.03)`.
- **Level 3 (Slide-over Drawers & Modals):** Pure `#ffffff` with an explicit `#0f172a` backdrop at 40% opacity, accompanied by `0 20px 25px -5px rgba(15, 23, 42, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.04)`.
- **Deep Sidebar:** Flat `#0f172a` with right border `1px solid #1e293b`. No drop shadow.

## Shapes

The design language uses compact, architectural geometry (`roundedness: 1`). 

- Standard inputs, buttons, table cell chips, and segment tabs use `0.25rem` (4px) corner radiuses.
- Enclosing workspace cards, modal dialogs, and slide-out credential drawers use `0.5rem` (8px) corner radiuses (`rounded-lg`).
- Status indicator pills (e.g., active sync dots, micro badges) use a pure pill treatment (`9999px`) to immediately distinguish live operational states from rectangular interactive controls.

## Components

### 3-Tier Hierarchy Tree & Rows
1. **Tier 1 (Service Definition):** Bold header row, white surface, full width. Displays service name, global routing protocol (e.g., `gRPC`, `REST`), aggregate instance count, and global health pill.
2. **Tier 2 (Instance Deployment):** Indented beneath Tier 1 by `1.5rem` with a subtle vertical guide rule (`#e2e8f0`). Contains instance ID, cluster host, scenario flag, and distinct environment tag badges.
3. **Tier 3 (Alias & Credentials):** Nested sub-grid under Instance or accessible via inline drawer. Displays key IDs, masked tokens with one-click copy, TLS cert validity countdowns, and routing aliases in `JetBrains Mono`.

### Badges & Status Indicators
- **Structure:** 20px fixed height, font size `11px`, `JetBrains Mono`, 4px radius or 9999px pill.
- **Health / Sync Badges:**
  - *Ready/Active:* `#ecfdf5` background, `#047857` text, with a 6px solid `#10b981` leading dot.
  - *Pending/Unconfigured Plate Sync:* `#fffbeb` background, `#b45309` text, paired with a slow pulse on a `#f59e0b` dot.
  - *Alias / Secret / Key Tag:* `#f5f3ff` background, `#6d28d9` text, `#8b5cf6` border at 50% opacity.
  - *Environment Identifiers:* `#ecfeff` background, `#0e7490` text, capitalized prefix (e.g., `[PROD]`, `[STAGE-EU]`).

### Data Tables
- Row height: Fixed 36px (compact) or 44px (default).
- Headers: `#f8fafc` background, uppercase 11px mono, letter-spacing `0.05em`, border bottom `1px solid #e2e8f0`.
- Hover state: Row background shifts to `#f1f5f9`.
- Selected state: Left edge 3px border accent in `#2563eb` with background `#eff6ff`.

### Buttons & Actions
- **Primary:** `#2563eb` background, `#ffffff` text, 32px height, 4px radius. Focused: 2px ring offset with `#93c5fd`.
- **Secondary / Ghost:** Transparent background, `1px solid #cbd5e1`, `#1e293b` text. Hover: `#f8fafc` background.
- **Table Action (Ghost Icon):** 28px square, `#64748b` icon stroke, hover background `#e2e8f0`.

### Form Controls & Inputs
- Height: 32px standard. Border `1px solid #cbd5e1`, background `#ffffff`.
- Active focus: Border color `#2563eb`, box-shadow `0 0 0 1px #2563eb`.
- Monospace variant: Compulsory for route path patterns (`/api/v1/...`), regex transforms, and upstream target ports.