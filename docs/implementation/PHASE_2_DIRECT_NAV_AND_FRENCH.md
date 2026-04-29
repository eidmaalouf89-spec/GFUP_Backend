# Phase 2 — Direct Navigation to Fiches & French Operational Synthesis — REPORT

**Status:** ✅ COMPLETED
**Date:** 2026-04-29
**Risk:** LOW (executed as planned)
**Scope:** UI + thin backend overlay. No pipeline, no schema, no chain_onion code touched.

This file replaces the original Phase 2 plan. The plan content is no longer reproduced here; what follows is the as-built record.

---

## 1. Objective (recap)

Two surgical, read-side changes:

1. **Direct fiche navigation** — clicking "Consultant de la semaine" or any row of "Focus · par consultant" must open that consultant's fiche page directly, not the consultants list.
2. **French operational synthesis** — the Chain+Onion table's `executive_summary` column rendered English text from `narrative_engine.py`. Translate at the read-side adapter so the UI renders French. `narrative_engine.py` left untouched. English fields preserved as fallback.

---

## 2. As-built — French translation overlay

### Files

| File | Change |
|---|---|
| `src/reporting/narrative_translation.py` | NEW. Three deterministic EN→FR dictionaries + `translate_top_issue(issue: dict) -> dict`. |
| `app.py` | `get_chain_onion_intel` (~line 1070) post-processes `top_issues` with `translate_top_issue` before returning. |
| `ui/jansa/overview.jsx` | `ChainOnionPanel` Synthèse cell renders `issue.executive_summary_fr || issue.executive_summary || ''`. |

### Translation dictionary scope

The dictionaries in `narrative_translation.py` cover the **complete bounded template space** emitted by `narrative_engine.py` — not just the strings that happened to land in the current snapshot. Counts:

| Field | EN templates | Source |
|---|---:|---|
| `executive_summary` | 6 | `narrative_engine._executive_summary` (LIVE_OPERATIONAL ×3 score buckets, LEGACY_BACKLOG, ARCHIVED_HISTORICAL, fallback) |
| `primary_driver_text` | 7 | `narrative_engine._PRIMARY_DRIVER` (6 layer codes) + `_PRIMARY_DRIVER_NONE` |
| `recommended_focus` | 6 | `narrative_engine._recommended_focus` (ARCHIVED, LEGACY, LIVE high-score, WAITING_CORRECTED_INDICE, waiting-consultant states, default) |

### Output shape

`get_chain_onion_intel` return is unchanged structurally. Each entry in `top_issues` now carries three additive keys:

```
executive_summary_fr
primary_driver_fr
recommended_focus_fr
```

The original English fields (`executive_summary`, `primary_driver_text`, `recommended_focus`) remain in the payload — they are the fallback if a future regeneration of `top_issues.json` introduces a template not yet in the dict.

### Fallback contract

If a template is not in the dict, the FR field **equals the English original** — never `None`, never `""` (unless the EN input was already empty/None). Verified via runtime smoke (Phase 2 / Step 1 validation step 4).

### Currently rendered

Only `executive_summary_fr` is rendered today (the Synthèse column in `ChainOnionPanel`). `primary_driver_fr` and `recommended_focus_fr` are present in the payload for future use (Phase 4 territory) but not surfaced.

---

## 3. As-built — Direct fiche navigation

### Files

| File | Change |
|---|---|
| `ui/jansa/shell.jsx` (1 line, ~676) | `<OverviewPage … onOpenConsultant={(c) => navigateTo('ConsultantFiche', c)}/>`. Reuses the same closure pattern already used by `<ConsultantsPage onOpen={(c) => navigateTo('ConsultantFiche', c)}/>`. |
| `ui/jansa/overview.jsx` | Six surgical touches: `OverviewPage`, `KpiRow`, `FocusPanel`, `FocusByConsultant` accept and thread `onOpenConsultant`; "Consultant de la semaine" `BestPerformerCard` and `FocusByConsultant` per-row buttons replace `onNavigate('Consultants')` with `onOpenConsultant(...)`. |

### Click targets affected

| Click target | Before | After |
|---|---|---|
| KPI card "Consultant de la semaine" | navigated to Consultants list | opens that consultant's fiche directly |
| Each row of Focus · par consultant (Focus mode on) | navigated to Consultants list | opens that row's fiche directly |
| KPI card "Entreprise de la semaine" | unchanged (`onNavigate('Contractors')`) — Phase 7 territory |
| Quick Actions, fiche back button, Consultants list cards, etc. | unchanged |

### Shape compatibility

`navigateTo('ConsultantFiche', payload)` extracts `payload.canonical_name || payload.name`. Both call sites already provide `name`:

- `data.best_consultant` from `adapt_overview` → carries `name`, `slug`, `pass_rate`, `delta`. ✓
- Each `c` in `FocusByConsultant`'s `items` → carries `name`, `slug`, `p1/p2/p3/p4`. ✓

No normalization wrapper added; the existing handler contract is sufficient.

### Defensive guards

Both new `onClick` handlers wrap the call: `() => onOpenConsultant && onOpenConsultant(...)`. If a future call site forgets to pass the prop, the click is a no-op rather than a crash. This matches the existing JSX style used elsewhere in `overview.jsx`.

---

## 4. Validation results

| Check | Result |
|---|---|
| `python -m py_compile app.py` | ✓ pass |
| `python -m py_compile src/reporting/narrative_translation.py` | ✓ pass |
| `translate_top_issue` known-template smoke (3 distinct EN strings → 3 distinct FR strings) | ✓ pass |
| `translate_top_issue` unknown-template smoke (random EN string → returned as-is in `_fr` field) | ✓ pass |
| App boots (`python app.py`) | ✓ pass |
| Dashboard Chain+Onion table — Synthèse column renders French (LIVE_OPERATIONAL high-score template dominant) | ✓ visual |
| English fields still present in `window.CHAIN_INTEL.top_issues[0]` payload | ✓ pass |
| Click "Consultant de la semaine" → lands on fiche page (not list) | ✓ visual |
| Click row in Focus · par consultant → lands on that fiche | ✓ visual |
| "Entreprise de la semaine" still routes to Contractors (regression check) | ✓ visual |
| Browser console — no JS errors | ✓ visual |

---

## 5. What was NOT touched (per the plan)

- `src/chain_onion/narrative_engine.py` — frozen
- `src/chain_onion/exporter.py` — Phase 4 territory
- `output/chain_onion/top_issues.json` — read-only artifact
- `output/chain_onion/dashboard_summary.json` — read-only artifact
- The `_for_ui` adapter family in `app.py` (`get_overview_for_ui`, `get_consultants_for_ui`, etc.)
- `ui/jansa-connected.html`
- `src/flat_ged/`, `src/report_memory.py`, `src/run_memory.py`, `src/team_version_builder.py`, `src/effective_responses.py`, `src/pipeline/stages/*`, `runs/run_0000/`, `data/*.db`

---

## 6. Notes for future phases

- **Phase 4** (Chain+Onion table émetteur + titre enrichment) — the FR translation overlay defined here is preserved by `get_chain_onion_intel`'s post-process step. Any new fields added by Phase 4 to `top_issues.json` (e.g. `emetteur_code`, `emetteur_name`, `titre`) flow through `translate_top_issue` unchanged because the helper does a shallow copy and only adds three keys.
- **If `narrative_engine.py` ever introduces a new template** — until a corresponding entry is added to `_EXEC_SUMMARY_FR` / `_DRIVER_FR` / `_FOCUS_FR`, the UI will render the English original for that template (fallback contract). This is by design.
- **Phase 7** (Contractor fiche wiring) — "Entreprise de la semaine" KPI card is the natural entry point. The `onOpenContractor` prop pattern would mirror `onOpenConsultant` exactly.

---

## 7. Lessons learned (Cowork session record)

The execution flagged a perceived "missing endpoint" alarm — `bash` from the sandbox reported `app.py` at 864 lines and no match for `def get_chain_onion_intel`. Verifying via the `Read` tool against the live Windows disk confirmed the method exists at line 1070 exactly as the plan stated. Bash inspection of Windows-mounted source files in the Cowork sandbox is not reliable — see `context/11_TOOLING_HAZARDS.md` H-1. The Phase 2 plan was correct; the alarm was retracted and execution proceeded.

The Step 1 prompt issued to Claude Code carried the `context/11_TOOLING_HAZARDS.md` H-1 reminder block at the top, and the Step 2 prompt did the same. No further bash-cache surprises occurred.
