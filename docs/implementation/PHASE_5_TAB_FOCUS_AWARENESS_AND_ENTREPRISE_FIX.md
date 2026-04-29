# Phase 5 Report — Focus-Aware Consultant/Contractor Tabs & Entreprise Card Fix

> Status: **DONE** (2026-04-29). This file replaces the original Phase 5 plan.
> The plan content is preserved through git history if reconstruction is ever needed.

---

## 1. What shipped

Three coordinated changes resolved the long-standing "empty entreprise cards"
bug and made both Consultant and Contractor tabs Focus-aware.

1. **Entreprise cards fix** — `adapt_contractors_list` no longer returns only
   the top-5 contractors by approval rate. All eligible emetteurs (≥5 docs,
   29 today) are now rendered as enriched cards. Sort is operational weight
   (`docs DESC` normally; `(focus_owned, docs) DESC` in focus mode), never
   pass-rate (which buried large emetteurs behind small high-pass-rate ones).
   Card limit is `[:50]` defensive ceiling.

2. **Canonical entreprise names everywhere** — A new helper
   `src/reporting/contractor_fiche.resolve_emetteur_name(code)` resolves raw
   3-letter emetteur codes (`BEN`, `LGD`, `SNI`, …) to canonical company
   names (`Bentin`, `Legendre`, `SNIE`, …) using the existing
   `CONTRACTOR_REFERENCE` map in `src/reporting/consultant_fiche.py`. The
   helper is the single source of truth for emetteur name resolution.
   Applied in both `adapt_contractors_list` and `adapt_contractors_lookup`,
   so cards AND chip fallback both display canonical names.

3. **Focus-aware tabs** — Both Consultants and Contractors tabs reorient
   their card KPIs around `focus_owned` when Focus mode is active, with the
   all-time number kept visible in a smaller secondary slot. A
   `P1·P2·P3·P4` mini-bar (4 width-proportional segments, colors
   `#FF453A / #FF9F0A / #FFD60A / #30D158`, identical to
   `FocusByConsultant` in `overview.jsx`) appears under each card whose
   actor has an entry in `window.OVERVIEW.focus.by_consultant` /
   `by_contractor`. The mini-bar renders whenever data exists, regardless
   of focus mode.

   To support the contractor mini-bar, `focus_filter.apply_focus_filter`
   now emits a new `by_contractor` aggregation alongside the existing
   `by_consultant`. Both have identical structure: list of
   `{code|slug, name, p1, p2, p3, p4, total}` sorted by `total DESC`.

---

## 2. Files changed

### Backend (Python)

| File | Change |
|---|---|
| `src/reporting/contractor_fiche.py` | +1 import (`CONTRACTOR_REFERENCE`), +9-line `resolve_emetteur_name(code)` helper at module scope |
| `src/reporting/ui_adapter.py` | `adapt_contractors_list` signature changed to `(contractor_list, focus=False)`; dropped `[:5]` slice → `[:50]`; `pass_rate` sort replaced with operational-weight sort; `focus_owned` field added; canonical name applied via `resolve_emetteur_name`. `adapt_contractors_lookup` applies canonical names. `adapt_overview` focus_stats dict + `_empty_focus` placeholder gain a `by_contractor: []` key |
| `src/reporting/focus_filter.py` | +1 import (`resolve_emetteur_name`), +20-line `by_contractor` aggregation block immediately after the existing `by_consultant` block; uses `pq_records` items where `owner_tier=="CONTRACTOR"`; mirrors `by_consultant` shape exactly |
| `app.py` | Single-character wiring change in `get_contractors_for_ui`: `adapt_contractors_list(raw)` → `adapt_contractors_list(raw, focus=focus)`. Signature unchanged externally |

### Frontend (JSX)

| File | Change |
|---|---|
| `ui/jansa/shell.jsx` | Added `focusMode={focusMode}` to `<ConsultantsPage>` and `<ContractorsPage>` mounts (lines 677, 679) |
| `ui/jansa/consultants.jsx` | New `FocusPriBar` component at top of file (~22 lines). `ConsultantsPage` accepts `focusMode`; builds `focusByName` lookup from `window.OVERVIEW.focus.by_consultant` (key on canonical actor name). All three card types (`MoexCard`, `PrimaryCard`, `SecondaryChip`) accept `focusMode` + `focusEntry`, swap the headline KPI to `focus_owned` ("À traiter") in focus mode while keeping `c.total` in a smaller secondary slot, and append the `FocusPriBar`. Existing `FOCUS {n}` / `F{n}` chips preserved |
| `ui/jansa/contractors.jsx` | New identical `FocusPriBar` (acceptable duplication — each file self-contained). `ContractorsPage` accepts `focusMode`; builds `focusByCode` lookup keyed on uppercase code. `ContractorCard` now renders 3 slots in focus mode (focus_owned headline / total docs / pass_rate as a soft-pill chip) and 2 slots otherwise; appends `FocusPriBar`. `ContractorChip` untouched |

### Files NOT touched

`aggregator.py`, `data_loader.py`, `focus_ownership.py`, `chain_onion/*`,
`flat_ged/*`, `team_version_builder.py`, `effective_responses.py`,
all `pipeline/stages/*`, `runs/run_0000/*`, `data/*.db`,
`ui/jansa-connected.html`, `overview.jsx`, `fiche*.jsx`, `runs.jsx`,
`executer.jsx`, `reports*.jsx`, `document_panel.jsx`. No schema change to
`pq_records`, `dernier_df`, or `RunContext`.

---

## 3. Verification evidence

**Helper smoke (Round A):**

```text
resolve_emetteur_name('BEN') → 'Bentin'
resolve_emetteur_name('LGD') → 'Legendre'
resolve_emetteur_name('SNI') → 'SNIE'
resolve_emetteur_name('XYZ') → 'XYZ'    (fallback to code)
resolve_emetteur_name('')    → ''       (empty)
```

**End-to-end Focus-on shape (Round B):**

```text
data = Api().get_overview_for_ui(focus=True, stale_days=90)
data['focus']['by_contractor']  →  18 entries, all keyed canonical
sample[0]: {'code': 'LGD', 'name': 'Legendre', 'p1': 0, 'p2': 0, 'p3': 0, 'p4': 119, 'total': 119}
sample[1]: {'code': 'SNI', 'name': 'SNIE',     'p1': 0, 'p2': 0, 'p3': 0, 'p4': 48,  'total': 48}
sample[2]: {'code': 'BEN', 'name': 'Bentin',   'p1': 0, 'p2': 0, 'p3': 0, 'p4': 42,  'total': 42}
```

Operational note (data, not code): every contractor-owned focus item is
currently in the P4 ("ok on deadline") bucket. No P1/P2/P3 contractor
work in this snapshot. The mini-bar therefore renders as a single green
segment for every contractor card today — visually correct and faithful
to the data. P1–P3 segments will appear automatically once contractor
deadlines tighten.

**UI verification (Round C):**

- Contractors tab shows 29 enriched cards (was 5). Bentin/BEN visible in
  the top-3 in normal mode (374 docs).
- All cards display canonical names; no raw 3-letter codes leak into
  card or chip text.
- Toggling Focus on swaps each consultant card's headline to "À traiter"
  / `focus_owned` with `total` demoted to a secondary slot; mini-bar
  appears under cards whose `canonical_name` has a `by_consultant`
  entry.
- Toggling Focus on swaps each contractor card to a 3-slot layout
  (`focus_owned` headline / total docs / pass_rate as a soft chip);
  mini-bar appears under cards whose code has a `by_contractor` entry
  (18 today).
- Toggling Focus off returns both tabs to all-time KPIs unchanged.
- Phases 1–4 functionality verified unaffected: dashboard overview,
  drilldowns, Chain+Onion table, FR synthese all render correctly.
- Console clean across all toggles.

---

## 4. Deviations from plan

1. **Plan reference correction.** The original plan §7 step 1 used
   placeholder `_CONTRACTOR_DISPLAY_MAP` for the canonical map symbol;
   the actual symbol's name is `CONTRACTOR_REFERENCE` (already imported
   into `ui_adapter.py` line 21 long before this phase). The Round A
   prompt issued the corrected name, and the helper was implemented
   against `CONTRACTOR_REFERENCE` directly.

2. **Pre-flight finding — pq_records already carry the join keys.**
   The plan §7 step 4 conditionally allowed for "deriving emetteur by
   joining doc_id back to dernier_df" if `pq_records` did not carry the
   needed fields. They do — `owner_tier` (line 149) and `emetteur`
   (line 152) are both already on every record. No producer-side change
   was needed; the `by_contractor` aggregation reads those fields
   directly.

3. **Cosmetic style mismatch in `consultants.jsx`.** Pre-existing lines
   used the JSX escape sequence `' '` (French narrow no-break space)
   in `replace(/,/g,' ')` thousands-separator formatting calls. The
   Round C agent stored the literal U+202F character in those positions
   instead of the escape sequence. **Runtime output is byte-identical**
   (both render the same Unicode codepoint in the DOM); the only
   difference is source-code readability. Left in place — a pure
   stylistic revert is out of scope for this phase. If a future pass
   normalizes the codebase to one form, the canonical choice is the
   `' '` escape (matches `overview.jsx` line 11 and
   `fiche_base.jsx` line 89).

4. **No new schemas, no new artifacts, no new pre-computed columns.**
   As required by the plan's Hard Rules.

---

## 5. Operational impact

- **Bentin (BEN), Legendre (LGD), SNIE (SNI), and 26 other emetteurs**
  immediately get enriched KPI cards. The Contractors tab is now
  operationally useful for the full project, not just for the 5
  highest-pass-rate emetteurs.
- **Focus mode is now symmetric across the two actor tabs.** Operators
  see "what each consultant must act on now" AND "what each entreprise
  must act on now" with the same visual treatment.
- **Mini-bar** at the bottom of each card communicates priority mix at a
  glance — useful even in non-focus mode where actionable items still
  exist.
- **Backend remains source of truth.** The UI does no KPI computation
  beyond reading existing fields and looking up by name/code.

---

## 6. Context updates applied

- `context/02_DATA_FLOW.md` — added a one-line note in the Read-side
  flow section: focus stats now carry `by_contractor` mirroring
  `by_consultant`.
- `context/03_UI_FEED_MAP.md` — `OVERVIEW.focus` shape gains
  `by_contractor`. New §F covers Phase 5's card reorientation in
  Consultants and Contractors tabs.
- `context/06_EXCEPTIONS_AND_MAPPINGS.md` — §C.1 cross-references the
  new helper `src/reporting/contractor_fiche.resolve_emetteur_name`
  as the canonical name resolution point of use.
- `context/07_OPEN_ITEMS.md` — closed item #1 ("UI Contractors page
  is a stub but backend is fully wired") and the implicit "entreprise
  cards empty" item via §1's resolution note.
- `README.md` — added a one-line entry under "Current State Snapshot"
  noting Phase 5's user-visible Contractors tab change.

---

## 7. Done definition checklist

- [x] App launches cleanly.
- [x] Contractors tab shows all 29 eligible enriched cards with
      canonical names.
- [x] BEN displayed as "Bentin" everywhere.
- [x] Focus mode reorients KPIs in both Consultants and Contractors
      tabs; existing `FOCUS {n}` / `F{n}` chips preserved.
- [x] Mini-bar present on cards when focus data exists.
- [x] `by_contractor` available in `window.OVERVIEW.focus.by_contractor`
      with canonical names.
- [x] Phases 1–4 unaffected (dashboard, drilldowns, Chain+Onion, FR
      synthese).
- [x] Diff scoped to: `src/reporting/ui_adapter.py`,
      `src/reporting/focus_filter.py`,
      `src/reporting/contractor_fiche.py` (helper),
      `app.py` (1-char wiring),
      `ui/jansa/consultants.jsx`,
      `ui/jansa/contractors.jsx`,
      `ui/jansa/shell.jsx`.
- [x] No backend, pipeline, schema, or chain_onion changes.
- [x] Context docs and README updated.
