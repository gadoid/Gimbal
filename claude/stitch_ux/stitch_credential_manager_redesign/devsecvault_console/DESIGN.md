---
name: DevSecVault Console
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#424655'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0054d6'
  primary: '#004bc1'
  on-primary: '#ffffff'
  primary-container: '#1d63ea'
  on-primary-container: '#eceeff'
  inverse-primary: '#b3c5ff'
  secondary: '#006685'
  on-secondary: '#ffffff'
  secondary-container: '#90dbff'
  on-secondary-container: '#00617e'
  tertiary: '#824400'
  on-tertiary: '#ffffff'
  tertiary-container: '#a55900'
  on-tertiary-container: '#ffece0'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae1ff'
  primary-fixed-dim: '#b3c5ff'
  on-primary-fixed: '#001849'
  on-primary-fixed-variant: '#003fa4'
  secondary-fixed: '#bee9ff'
  secondary-fixed-dim: '#84d0f4'
  on-secondary-fixed: '#001f2a'
  on-secondary-fixed-variant: '#004d65'
  tertiary-fixed: '#ffdcc3'
  tertiary-fixed-dim: '#ffb77d'
  on-tertiary-fixed: '#2f1500'
  on-tertiary-fixed-variant: '#6e3900'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-lg:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  headline-md:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  body-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-code:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: -0.01em
  label-md:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-sm:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
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

This design system targets QA engineers, automation architects, and DevOps specialists operating within complex cloud-native test automation and CI/CD pipelines. Managing critical infrastructure secrets—such as dynamic runtime tokens, Bearer headers, session cookies, and basic authentication—requires high cognitive clarity, extreme precision, and rock-solid reliability.

The design style combines **Corporate / Modern Enterprise Precision** with a **Technical Developer Tools** aesthetic. It employs a contrast-rich dual layout: a compact, dark-mode navigation sidebar paired with a crisp, low-fatigue light workspace. This layout reduces visual noise, highlights multi-environment operational statuses, and ensures that sensitive security credentials can be audited, modified, and tested with confidence.

## Colors

The palette balances technical authority and operational safety:

- **Primary (`#1d63ea`)**: An active digital blue representing automated execution, primary CTA triggers, active tabs, and inline interaction points.
- **Secondary (`#0e7090`)**: A calm cyan-teal utilized for secondary indicators, environment context tags (`test`, `staging`, `production`), and data flow breadcrumbs.
- **Tertiary (`#d97706`)**: A precise amber-gold used for credential expiration alerts, slot variable injections (`${slot.X}`), and non-blocking security notices.
- **Neutral (`#0f172a`)**: Slate navy that serves as the deep background for the persistent sidebar navigation, high-contrast headings, and structured data tables.

### Functional Status & Semantic Tokens
- **Auth Type Tags**:
  - `Bearer` / `Authorization`: Subdued soft crimson badge (`#fef2f2`, border `#fecaca`, text `#dc2626`).
  - `Cookie` / `Session`: Muted violet tint (`#f5f3ff`, border `#ddd6fe`, text `#7c3aed`).
  - `Basic Auth`: Emerald neutral (`#ecfdf5`, border `#a7f3d0`, text `#059669`).
- **Sidebar Canvas**: Slate-950 (`#080c14`) to Slate-900 (`#0f172a`) with 1px border separation (`#1e293b`).
- **Main Canvas**: Warm off-white (`#f8fafc`) with pure white (`#ffffff`) surfaces for cards, tables, and modal dialogs.

## Typography

The type system pairs **Geist** for crisp, scalable structural UI elements with **JetBrains Mono** for developer-centric values (keys, token names, injected slot variables, endpoints, and expiration counters).

- **Data Tables & Key-Value Lists**: All account keys, IDs, hash masks, and parameter injection templates (`${slot.orgNo}`) use `label-code` in monospace, ensuring tabular vertical alignment and zero ambiguity between characters like `0` and `O`.
- **Form Controls & Headings**: `Geist` provides tight geometric proportions suitable for high-density settings screens, technical modals, and multi-tiered navigation bars.

## Elevation & Depth

This design system avoids heavy shadows, using a combination of **low-contrast outlines** and **subtle ambient layering** typical of modern engineering control planes:

- **Surface Tier 0 (App Shell)**: `#f8fafc` workspace canvas.
- **Surface Tier 1 (Containers & Cards)**: `#ffffff` background with a crisp border (`1px solid #e2e8f0`).
- **Surface Tier 2 (Interactive Floating Popovers & Modals)**: `#ffffff` overlaid on an ambient dark veil (`rgba(15, 23, 42, 0.4)`), elevated with a restrained technical shadow: `0 10px 25px -5px rgba(15, 23, 42, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.06)`.
- **Sidebar Surface**: Dark zinc-slate `#0b111e` accented with inner 1px border lines `#1e293b` to visually distinguish operational categories without elevation.

## Shapes

The design uses standard rounded contours (`roundedness: 2`, base radius `0.5rem` / `8px`):

- **Inputs, Buttons, and Select Triggers**: `6px` to `8px` corner radius for a precise tool feel.
- **Badges, Filter Pills, and Tag Counters**: Subtle pill shaping (`9999px`) or `4px` soft tags for inline credential types (`Bearer`, `Basic`, `Cookie`).
- **Dialogs & Sliding Drawers**: `12px` corner radius with crisp edge boundaries.

## Components

### 1. Buttons
- **Primary Action (`+ 新增账户` / `保存`)**: Solid `#1d63ea` fill, white text, 8px radius, subtle hover transition to `#1552c6`. Height `36px`, padding `0 14px`.
- **Secondary / Ghost Action (`取消` / `测试`)**: Subtle slate border (`#cbd5e1`), white background, text `#334155`. Hover state brings `#f1f5f9`.
- **Inline Row Actions (`测试`, `···`)**: Borderless text buttons in primary blue, with an icon trigger for overflow dropdown actions.

### 2. Filter & Capsule Chips
- **Status & Type Filters (`全部类型`, `Bearer`, `Cookie`, etc.)**: Light border (`#e2e8f0`), `#ffffff` background. Selected state uses primary blue outline or solid dark slate fill with high contrast text.
- **Badge Indicators**:
  - `Default / 默认`: Subdued neutral chip (`#f1f5f9`, text `#475569`, font size `11px`).
  - `Bearer / Authorization`: High-visibility soft warning red (`#fef2f2`, text `#dc2626`).
  - `Active Quotes / 引用`: Soft pill badge displaying count of scenarios and linked test steps (`#f8fafc`, border `#e2e8f0`).

### 3. Credential Form Fields & Dynamic Slots
- **Text Inputs & Dropdowns**: Height `38px`, border `1px solid #d1d5db`, font size `14px`. Focused state features blue focus ring `0 0 0 3px rgba(29, 99, 234, 0.15)`.
- **Password / Secret Vault Field**: Masks content with bullet dots; features an inline action button to toggle visibility or copy to clipboard. Includes contextual helper text: *"留空表示不修改 (改密一处, 所有装载它的条目/场景同时生效)"*.
- **Dynamic Slot Configuration**: A collapsible nested card labeled *高级 (账号字段 / token 类型 / 有效期)*.
  - Supports dynamic key-value rows (`orgNo`, `tenantId`, `${slot.X}`) with a dedicated `+ 加字段` button.

### 4. Data Tables & System Groups
- **System Group Header Row**: Subtle grey backdrop (`#f8fafc`), strong font weight (`600`), displaying aggregate counts (`fin-service · 2 个账户`).
- **Data Rows**: White background with hover highlight (`#f8fafc`), vertical alignment centered, 1px divider lines (`#f1f5f9`).
- **Columns**: `username`, `状态`, `类型`, `环境 / 登录地址`, `引用`, `操作`.

### 5. Dialogs & Modals
- Fixed center modal with width `560px`.
- Top-right close icon, segmented sections with red asterisks for mandatory fields (`系统 *`, `环境 *`, `username *`).
- Sticky bottom footer containing grouped secondary (`取消`) and primary (`保存`) action triggers.