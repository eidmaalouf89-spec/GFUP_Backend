# Phase 5 Report — DCC follow-ups & polish

**Date:** 2026-04-29
**Mods completed:** 1, 2, 3, 4
**Status:** COMPLETE ✅ — all mods verified 2026-04-29

---

## Mod 1 — Earlier comments get `indice + status` prefix

**Status:** ✅ Complete — validated by Eid 2026-04-29

**Files modified:**
- `src/reporting/document_command_center.py` — `_build_comments_section`: added `status` key to the earlier_comment dict
- `ui/jansa/document_panel.jsx` — earlier_comments label span extended to render `"{indice}) {status}:"`

**Bonus fix:** `_build_revision_history` was truncated on disk; closing lines recovered from `.pyc` and restored.

**Result:** earlier comments now display as `"A) REF: <text>"` in the panel.

---

## Mod 2 — All doc references clickable to open panel

**Status:** ✅ Complete — validated by Eid 2026-04-29

**Inventory (5 candidates reviewed):**

| # | File | Component | Doc reference | Action |
|---|---|---|---|---|
| 1 | `ui/jansa/overview.jsx` ~884 | `ChainOnionPanel` | Issue row renders `issue.family_key` | **WIRED** |
| 2 | `ui/jansa/fiche_base.jsx` ~1212 | `DrilldownDrawer` | `<tr>` per doc | Already wired (Phase 4C) |
| 3 | `ui/jansa/fiche_page.jsx` ~197 | `ConsultantFichePage` | `onRowClick` | Already wired (Phase 4C) |
| 4 | `ui/jansa/consultants.jsx` | all cards | KPIs only, no doc numero | N/A |
| 5 | `ui/jansa/contractors.jsx` | all cards | KPIs only, no doc numero | N/A |

**Files modified:** `ui/jansa/overview.jsx` only (1 site, under the 4-file threshold — no approval needed).

**Smoke test:** Overview → Chain+Onion panel → row click → DCC panel opens correctly. ✓

---

## Mod 3 — Decorative search bar wired to DCC panel

**Status:** ✅ Complete — validated by Eid 2026-04-29

**Scope change:** original plan was deletion; deletion caused black screen on smoke test (JSX structural issue). Revised: wire the bar instead of removing it.

**Files modified:** `ui/jansa/shell.jsx` lines 197–219 — outer `<div>` gets `onClick → setPanelState({mode:'search'})` + `cursor:pointer`; `<input>` set `readOnly` + `pointerEvents:none`.

**Result:** clicking the search bar opens the DCC search panel; magnifier button works independently.

---

## Mod 4 — UNKNOWN attribution resolution

**Status:** ✅ Complete — verified 2026-04-29

### What was done

**Analysis:** All 47 UNKNOWN rows classified across 6 action buckets via manual worksheet review with Eid.

**Files modified:**
- `src/reporting/chain_timeline_attribution.py` — 5 targeted fixes (see below)
- `context/dead_version_overrides.csv` — created: 26 DEAD + 4 NO_ATTRIBUTION version keys

**Code fixes applied:**

| Fix | Location | Change |
|---|---|---|
| 1 — Override map | `write_chain_timeline_artifact` | Load `dead_version_overrides.csv` as `dict[version_key → reason]` instead of flat set; apply `reason` as actor/tier label |
| 2 — SAS in Change 4 | `_build_indice_phases` L296 | Added `"SAS"` to exclusion set so SAS CYCLE_REQUIRED REF doesn't false-trigger the BET_COMPLETE_NO_MOEX path |
| 3 — attributed_days cap | `_build_indice_phases` L333 | `min(..., review_delay)` — prevents over-attribution on SAS-REF indice A cases |
| 4 — rework guard | `_build_indice_phases` L369 | `and review_end is not None` — prevents crash when SAS-REF open case has a following version |
| 5 — DEAD override guard | `write_chain_timeline_artifact` | Removed `actor == "UNKNOWN"` guard so override fires regardless of prior attribution |

**Overrides file** (`context/dead_version_overrides.csv`, 30 entries):
- 26 entries `DEAD` — abandoned/obsolete versions; attributed_days=0, excluded from delay stats
- 4 entries `NO_ATTRIBUTION` — 3 MOEX-not-called + 1 within-tolerance review (142080_A, 4 days)

### Verified output (`output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv`)

| Check | Result |
|---|---|
| `UNKNOWN` version_keys | `['028245_C']` ✓ |
| `DEAD` unique version_keys | 26 ✓ |
| `NO_ATTRIBUTION` rows | 4 ✓ |

---

## Files changed (Phase 5 total)

| File | Mod |
|---|---|
| `src/reporting/document_command_center.py` | Mod 1 |
| `ui/jansa/document_panel.jsx` | Mod 1 |
| `ui/jansa/overview.jsx` | Mod 2 |
| `ui/jansa/shell.jsx` | Mod 3 |
| `src/reporting/chain_timeline_attribution.py` | Mod 4 (5 fixes) |
| `context/dead_version_overrides.csv` | Mod 4 (new file, 30 entries) |

---

## Open questions / surprises

- Mod 3: deletion of the search bar block caused a black-screen regression (JSX structural issue at runtime). Root cause not fully diagnosed — chose wire-instead-of-delete as safer fix. If the dead block ever needs removing, investigate JSX parse order in `shell.jsx` Topbar first.
- Mod 4: the previous pipeline run that produced the current `CHAIN_TIMELINE_ATTRIBUTION.json` was incomplete (JSON truncated at line 176237). This is why 328511 and 332350 were absent from the CSV. A clean rerun will regenerate both files fully.
- Mod 4: 3 MOEX-not-called cases (245002_A, 228520_A, 049220_E) have real delays (40/33/5 days) but effective-end-date overrides would require a separate manual exceptions mechanism. Accepted as NO_ATTRIBUTION for now.
