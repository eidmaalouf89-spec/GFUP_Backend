# JANSA UI Facelift Style Guide

This guide extracts the visual system from the Claude Design handoff so it can be applied step by step to the existing desktop UI. It is a styling reference only: do not rebuild the app architecture, do not introduce React/Vite into production if it is not already there, and do not modify backend or data contracts as part of this step.

## Source Files Reviewed

- `prototype/jansa/tokens.js`
- `prototype/jansa/shell.jsx`
- `prototype/jansa/overview.jsx`
- `prototype/jansa/consultants.jsx`
- `prototype/jansa/fiche_page.jsx`
- `prototype/jansa/fiche_base.jsx`
- `spec/design-tokens.md`
- `spec/ux-rules.md`

## Design Tokens

### Color Palette

| Token | Dark value | Light value | Usage |
|---|---:|---:|---|
| `--bg` | `#0A0A0B` | `#FAFAFA` | App canvas and main page background |
| `--bg-elev` | `#111113` | `#FFFFFF` | Cards, sidebar, framed panels |
| `--bg-elev-2` | `#18181B` | `#F4F4F5` | Hover states, active surfaces, secondary panels |
| `--bg-chip` | `#222226` | `#E8E8EA` | Chips, badges, chart tracks, progress tracks |
| `--line` | `rgba(255,255,255,0.08)` | `rgba(0,0,0,0.08)` | Default borders and dividers |
| `--line-2` | `rgba(255,255,255,0.14)` | `rgba(0,0,0,0.14)` | Hover borders and stronger separators |
| `--line-3` | `rgba(255,255,255,0.22)` | `rgba(0,0,0,0.22)` | Scrollbar hover and highest-contrast fine lines |
| `--text` | `#F5F5F7` | `#1C1C1E` | Primary text and key values |
| `--text-2` | `#A1A1A6` | `#48484A` | Secondary labels and supporting copy |
| `--text-3` | `#6E6E73` | `#8E8E93` | Metadata, section numbers, tertiary labels |
| `--accent` | `#0A84FF` | `#0A84FF` | Primary blue accent, links, focus mode, active nav |
| `--accent-soft` | `rgba(10,132,255,0.14)` | `rgba(10,132,255,0.10)` | Accent badge fills and active glows |
| `--good` | `#30D158` | `#1E8E3E` | VSO/FAV, positive deltas |
| `--good-soft` | `rgba(48,209,88,0.14)` | `rgba(30,142,62,0.10)` | Positive badge fills |
| `--warn` | `#FFD60A` | `#B58100` | VAO/SUS, warning states |
| `--warn-soft` | `rgba(255,214,10,0.14)` | `rgba(181,129,0,0.10)` | Warning badge fills |
| `--bad` | `#FF453A` | `#D70015` | REF/DEF, overdue, negative deltas |
| `--bad-soft` | `rgba(255,69,58,0.14)` | `rgba(215,0,21,0.10)` | Error/overdue badge fills |
| `--neutral` | `#8E8E93` | `#636366` | HM and neutral states |
| `--neutral-soft` | `rgba(142,142,147,0.14)` | `rgba(99,99,102,0.10)` | Neutral badge fills |
| `--shadow-lg` | `0 24px 48px -12px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)` | `0 24px 48px -12px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.04)` | Large floating surfaces only |
| `--blur-bg` | `rgba(10,10,11,0.72)` | `rgba(255,255,255,0.78)` | Translucent sticky top bar |

Status semantics are fixed and must not be remapped: `VSO/FAV` is green, `VAO/SUS` is yellow, `REF/DEF` is red, and `HM` is gray.

### Typography

| Role | Font | Size | Weight | Letter spacing | Usage |
|---|---|---:|---:|---:|---|
| Hero number | UI font | `72-104px` | `200-300` | `-0.035em` to `-0.05em` | Main fiche totals and large KPI numbers |
| Page title | UI font | `44px` | `300` | `-0.035em` | Page mastheads |
| Section title | UI font | `24-28px` | `600` | `-0.02em` | Numbered sections and block headers |
| Card title | UI font | `14-16px` | `600` | `-0.01em` | Card headings and performer names |
| Body | UI font | `13-14px` | `400` | `0` | Normal supporting text |
| Eyebrow | UI font | `10-11px` | `600` | `0.08-0.12em` | Uppercase metadata labels |
| Number label | Numeric font | `10-13px` | `400-600` | `0-0.04em` | Tables, badges, counters, chart axes |

UI font stack:

```css
'SF Pro Display', 'Inter', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif
```

Numeric font stack:

```css
'SF Mono', 'JetBrains Mono', 'Menlo', monospace
```

All counters, table values, badges, and chart labels should use `font-variant-numeric: tabular-nums`.

### Spacing Scale

| Value | Usage |
|---:|---|
| `4px` | Tiny gaps inside labels or glyphs |
| `6px` | Badge internals, table micro spacing |
| `8px` | Compact controls, search input, small gaps |
| `10px` | Sidebar and chip padding, compact card gaps |
| `12px` | Button padding, avatar gaps, topbar controls |
| `14px` | Grid gaps, KPI row gaps, common card spacing |
| `16px` | Dense card padding, section separators |
| `18px` | Section title spacing, chart legends |
| `20px` | Standard card padding and page card gaps |
| `22px` | KPI card padding |
| `24px` | Header margins, chart/card inner spacing |
| `28px` | Large card padding, topbar horizontal padding |
| `32px` | Overview page padding and masthead top rhythm |
| `40px` | Consultants page horizontal padding and major section rhythm |
| `48px` | Stub pages and narrative spacing |
| `56px` | Fiche page horizontal padding |
| `60-64px` | Major fiche block separation |
| `80px` | Footer separation after final content |

### Border Radius

| Radius | Usage |
|---:|---|
| `4px` | Keyboard shortcut badge, tiny chart segments |
| `6px` | Stacked bars and compact segment tracks |
| `8px` | Search box, secondary chips, compact rows |
| `9-10px` | Sidebar nav items, brand glyph, project pill |
| `12px` | Secondary consultant chips, small buttons |
| `14px` | Avatar blocks and best-performer portraits |
| `16px` | Default data cards, tables, side panels |
| `18px` | Overview shared cards |
| `20px` | Hero cards and glass KPI cards |
| `99px` | Pills, badges, circular controls, progress tracks |

### Shadows And Effects

| Pattern | Rule |
|---|---|
| Card frame | `background: var(--bg-elev)` with `1px solid var(--line)` |
| Elevated hover | Border moves to `var(--line-2)` or accent; element lifts `translateY(-2px)` |
| Large shadow | Use `--shadow-lg` sparingly for floating or modal-level surfaces |
| Accent halo | Radial gradient placed off-corner, usually `top/right: -80px` with `width/height: 180-200px` |
| Topbar glass | `background: var(--blur-bg)` with `backdrop-filter: saturate(1.4) blur(20px)` |
| Focus vignette | Main area receives inset blue border plus soft inset glow |
| Scrollbars | Transparent track; thumb uses `--line-2`, hover uses `--line-3` |

### Motion

| Motion | Rule |
|---|---|
| Page enter | `fadeInUp 0.4s cubic-bezier(.4,0,.2,1)` |
| Hover lift | `transform: translateY(-2px)` with `border-color`, `0.15-0.2s` |
| Focus cinema | Radial halo plus 3 aperture rings plus label, `650-800ms` |
| Theme toggle | Sun/moon crossfade and rotate, `400ms` |
| Chart lines | Stroke dash animation `drawLine`, `1.2-1.4s` |
| Bar growth | Width transition `0.6s cubic-bezier(.4,0,.2,1)` |

## Component Styling Rules

### Cards

- Use `var(--bg-elev)` with a `1px solid var(--line)` border as the default card surface.
- Default card radius is `16-18px`; hero or glass KPI cards use `20px`.
- Default content padding is `20-24px`; dense cards can use `16px`.
- Cards should feel quiet and data-first. Use one subtle corner halo only when a card needs emphasis.
- Hoverable cards should lift by `-2px` and brighten the border, without changing layout.
- Repeated cards should avoid heavy shadows; rely on border, surface contrast, and spacing.

### Buttons And Controls

- Primary controls are compact, pill-like, and icon-led where possible.
- Focus toggle is a pill: `7px 13px`, `border-radius: 99px`, icon plus label, accent fill only when active.
- Theme toggle is a circular `34px` icon button with animated sun/moon states.
- Back button in consultant fiche is an inline top-left masthead control, not a floating button.
- Search field uses a compact rounded rectangle: `6px 12px`, `8px` radius, `var(--bg-elev-2)` fill, `var(--line)` border.
- Badges use `border-radius: 99px`, soft semantic fills, and visible labels. Color must not be the only signal.

### Sidebar

- Fixed width: `232px`.
- Surface: `var(--bg-elev)` with right border `1px solid var(--line)`.
- Brand block uses a small `32px` gradient glyph and compact JANSA/VISASIST typography.
- Project pill sits below the brand with `var(--bg-elev-2)`, `10px` radius, and a green live dot.
- Navigation is grouped with uppercase section labels.
- Active navigation uses three combined signals:
  - left accent bar, `3px` wide;
  - soft horizontal blue gradient background;
  - accent-colored icon and stronger label weight.
- Inactive nav items use `var(--text-2)` labels and `var(--text-3)` icons, with `var(--bg-elev-2)` hover.
- Footer user identity uses a circular gradient avatar and compact role text.

### Top Bar

- Height: `60px`.
- Sticky at top of main content.
- Surface: translucent `--blur-bg` plus blur/saturation filter.
- Content layout: breadcrumb on left, search centered with max width around `420px`, controls on right.
- Breadcrumb uses uppercase project metadata, slash divider, then current page in stronger text.
- Topbar controls should stay compact and should not dominate the page title hierarchy.

### Layout Grid

- Application shell: persistent sidebar plus main column, full viewport height, no full-page reload styling.
- Main content scrolls inside the shell under the sticky topbar.
- Overview page padding: `32px`.
- Consultants page padding: `32px 40px 60px`.
- Fiche article width: max `1200px`, centered, `0 56px 60px` padding.
- KPI overview row: 4 equal columns, `14px` gap, `20px` bottom margin.
- Two-column analytical layout: usually `1.2fr 1fr` or `1.4fr 1fr`, `14px` gap.
- Consultant primary cards: responsive grid with `minmax(260px, 1fr)`.
- Secondary consultant chips: responsive grid with `minmax(220px, 1fr)`.
- Fiche Bloc 3: main table and side panels in `1.7fr 1fr`, `28px` gap.

### KPI Blocks

- KPI cards use eyebrow labels, large low-weight numbers, optional deltas, and compact trend visuals.
- Hero KPI number sizes:
  - overview cards: about `56px`;
  - fiche hero stats: about `72px`;
  - fiche masthead total: about `104px`.
- Deltas are semantic pills with arrow/neutral mark and soft background.
- Positive/negative meaning can invert for backlog metrics, where reduction is good.
- Use sparklines with gradient fill and a visible final dot.
- Best performer cards combine avatar, name, large percentage, small explanatory label, and a thin progress gauge.

### Charts

- Use hand-rolled SVG visual style. Do not introduce a chart library for this facelift.
- Use subtle grid lines in `var(--line)` and numeric axis labels in the numeric font.
- Stacked bars use small gaps, `6px` radius, and visible legends.
- Status colors must follow the semantic palette exactly.
- Sparkline style: gradient area fill, `1.4-1.5px` line stroke, final point marker.
- Weekly activity style: blue bars for opened, green area/line for closed, red dashed line for refused.
- Focus radial style: concentric rings on `var(--bg-chip)` tracks with priority colors and soft glows.
- Lot health bars use segmented tracks with hatch styling for late items.
- Tooltips should be pinned to the hovered week or data point where the source behavior specifies it.

### Tables

- Table containers are card surfaces with `16px` radius and clipped overflow.
- Headers use uppercase UI font, `11px`, `600`, `0.06em` letter spacing, `var(--text-3)`.
- Cells use numeric font, `13px`, `10px` vertical padding, right alignment for values.
- First column uses UI font and left alignment for human-readable names.
- Current rows should be highlighted with an accent-soft blue treatment.
- Totals rows use stronger top border `var(--line-2)` and heavier weight.

## Layout Principles

### Section Rhythm

- Start each page with a compact masthead: small metadata line, then large page title.
- Use `24-28px` after page mastheads before primary content.
- Use `40px` between consultant grouping sections.
- Use `60-64px` between major fiche analytical blocks.
- Keep local card gaps tight (`14-20px`) so dashboards remain scan-friendly.

### Grouping Logic

- Overview groups by decision priority:
  - current run status and backlog KPIs first;
  - focus triage only when focus mode is active;
  - visa flow and weekly activity below.
- Consultants are not a flat list. They are grouped as:
  - `01 MOEX`: full-width orchestrator hero card;
  - `02 Primary`: portrait cards with sparkline and three KPIs;
  - `03 Secondary`: compact chips.
- Consultant fiche uses numbered blocks:
  - `01` monthly activity;
  - `02` cumulative evolution;
  - `03` lot performance.

### Hierarchy

- Highest emphasis: page title, hero numbers, active focus state, and blocking/late metrics.
- Medium emphasis: section titles, card titles, selected navigation, KPI deltas.
- Low emphasis: metadata, axis labels, helper text, inactive navigation, table sublabels.
- The design favors sparse contrast, large numbers, and precise labels over decorative UI.

### Navigation Structure

- Navigation remains persistent in a single shell.
- Groups are `Pilotage`, `Acteurs`, `Qualite`, and `Systeme` in the prototype.
- Current page and focus mode are expected to persist in local storage in the prototype; in the existing desktop app, preserve equivalent state if that app already has a state mechanism.
- The focus mode is a visual/workflow mode, not a separate app route.

## Mapping To Existing UI Components

Apply these styles to the existing desktop UI incrementally. The target is visual restyling, not replacing working screens with the prototype.

| Existing UI area | Handoff style to apply | Notes |
|---|---|---|
| Main window background | `--bg` canvas with `--text` foreground | Start by adding theme-level color variables or equivalent constants in the existing UI toolkit |
| Primary content panels | Card surface rules from Overview and Fiche | Use `--bg-elev`, `--line`, `16-18px` radius, `20-24px` padding |
| Current run card | Overview hero KPI card | Eyebrow, large run number, supporting week/date metadata, optional sparkline if data already exists |
| Discrepancies/backlog card | Blocking KPI card | Use red for overdue/blocking counts; invert delta semantics so reductions are green |
| Visa distribution bar | Visa flow stacked bars | Keep current data shape; restyle bars and legends with semantic status colors |
| Project stats card | KPI row cards | Split into scan-friendly KPI blocks only if the current layout already supports multiple cards |
| Monthly chart | Weekly or cumulative chart visual style | Do not change calculation period unless the current app already exposes weekly data |
| Consultant list | Three-circle Consultants page hierarchy | If current UI has only a flat list, first restyle rows/cards; grouping can be adapted without changing navigation architecture |
| Consultant detail page | Fiche masthead, hero KPI band, numbered analytical blocks | Preserve current data bindings and screen lifecycle |
| Sidebar/menu | Shell sidebar styling | Apply active bar, grouped labels, compact badges, and muted inactive states to the existing navigation |
| Top toolbar | Topbar glass treatment | Apply height, blur/translucent surface, breadcrumb/search/control layout where supported |
| Run button | Topbar control style | Keep visibility tied to OPC role if that already exists |
| Search field | Compact topbar search styling | Do not add new search behavior if absent; only style existing search |
| Status badges | Semantic chip rules | Always include text labels in addition to color |
| Tables | Fiche table styling | Use uppercase headers, tabular numeric values, subtle borders, and highlighted current row |
| Charts | SVG visual language | If existing app uses another native drawing system, copy the visual treatment rather than importing a new charting dependency |
| Theme toggle | Prototype sun/moon toggle | Only apply if current app already supports themes or can support CSS/theming without architecture changes |
| Focus mode | Focus pill, vignette, and focus-only visual emphasis | Only adapt if current app already has or can support an equivalent mode without route/backend changes |

## Constraints And Adaptations

- The handoff is a React prototype with inline styles; the current desktop app should not be rebuilt to match it.
- Do not introduce a new frontend stack, Vite, React, Tailwind, Material UI, Recharts, or a backend layer as part of the facelift.
- Some prototype behaviors depend on browser APIs such as `localStorage`, CSS variables, SVG animations, and `backdrop-filter`. Desktop toolkit equivalents may need adaptation.
- The sidebar/topbar shell assumes a persistent single-page layout. If the current desktop app uses separate windows or tabs, apply the visual language to the existing navigation model instead of replacing it.
- The prototype includes focus mode visuals and local persistence. If the existing app has no focus-mode concept, treat this as an optional styling target, not a required feature for the first pass.
- The charts are custom SVG. In a non-web desktop UI, recreate the same colors, hierarchy, legends, and animation restraint with the native drawing system.
- The prototype uses large typography and generous spacing. Smaller desktop windows may need reduced hero sizes while preserving hierarchy.
- Consultant grouping into MOEX/Primary/Secondary may require data fields that the current app might not expose. If missing, keep the existing list structure and apply card/chip styling only.
- Fiche Bloc 3 expects contractor human names above lot codes. If the current data only has lot codes, add display-name mapping only where already available from existing data; do not invent mock data.
- Theme switching requires centralized tokens. If the current app has hard-coded colors, first introduce a small token layer in the current technology rather than porting prototype files.
- Accessibility requirements still apply: preserve focus outlines, keyboard navigation, Enter-to-open behavior where applicable, Esc-to-close for detail views/modals, and visible labels on colored badges.

## Recommended Application Order

1. Introduce token constants or CSS variables in the current UI layer.
2. Restyle global canvas, text, borders, and card surfaces.
3. Restyle sidebar and topbar without changing routes or app flow.
4. Restyle existing KPI cards and status badges.
5. Restyle tables and current chart surfaces.
6. Adapt consultant list/detail screens to the grouped/card visual language where the existing data supports it.
7. Add focus/theme visual refinements only after the base facelift is stable.
