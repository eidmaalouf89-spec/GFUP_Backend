# UX rules

These behaviors are part of the spec. Don't drop them in the port.

## Navigation
- Single persistent shell (sidebar + topbar). No full-page reloads.
- Active nav item: left accent bar + soft gradient background + accent-colored icon.
- Current page + focus state persist to `localStorage`.

## Focus mode
- Triggered from the pill in topbar.
- Plays the **Focus Cinema** animation once per toggle (halo + 3 aperture rings + label).
- Adds inset blue vignette to the main area.
- On Overview: swaps the default layout for the focus radial + per-consultant waterfall.
- Persists to localStorage as `jansa_focus`.

## Theme toggle
- Sun / moon crossfade with opposite rotation.
- Applies CSS vars via `applyTheme()` from `tokens.ts`.
- Persists as `jansa_theme`.

## Consultants page
- Three cercles:
  - **01 MOEX** — full-width hero card with orbit glyph
  - **02 Primary** — portrait cards, sparkline + 3 KPIs
  - **03 Secondary** — compact chips
- Clicking any card opens the fiche.

## Consultant fiche
- Back button at the TOP LEFT of the masthead, inline (not floating).
- Masthead includes project · week · consultant id out of total.
- Hero number uses a vertical white→gray gradient text fill.
- Bloc 1 (monthly table) highlights the current row in blue.
- Bloc 2 (cumulative) tooltip is pinned to the hovered week.
- Bloc 3 lot table: contractor human name on top line, code on second line.
- Bloc 3 legend ABOVE the table, lists all 6 segment meanings.
- Week labels use `YY-SNN` (e.g. `24-S14`) — never `YYYY-SNN`.

## Data refresh
- Runs happen hourly via APScheduler.
- A "Run" button in topbar (visible to OPC role only) triggers on-demand.
- Frontend uses React Query with `staleTime: 60_000` to avoid thrashing.

## Accessibility (minimum)
- Keyboard: tab through nav, Enter to open consultant, Esc closes fiche.
- Focus outlines preserved (don't blanket-remove `:focus`).
- Color isn't the only signal for status — every badge also has a label.
