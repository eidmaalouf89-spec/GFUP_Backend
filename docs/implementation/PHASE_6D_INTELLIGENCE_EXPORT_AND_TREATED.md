# Phase 6D — Intelligence Bulk Export + Treated-State Tracking

This MD is **self-contained**. An agent assigned only this phase can execute it cold without reading any other file in `docs/implementation/`.

> **Phase 6 has been split into four sub-phases (6A → 6B → 6C → 6D).** This is 6D. **Phases 6A, 6B, and 6C must already be merged.** This phase adds the "claim kitchen" affordances on top of the working Intelligence page.

---

## 1. Objective

Add two operator-grade affordances to the Intelligence page built in 6C:

1. **Bulk export** — per-row checkboxes, a bulk-action footer, and an XLSX export of selected rows to `output/exports/Intelligence_<timestamp>.xlsx`.
2. **Treated state** — an operator can mark a document as "traité localement"; treated rows are visually de-emphasized and excluded from selection. Treated state lives in `localStorage` keyed by run number + numero + indice, so it persists across reloads in the same session and resets automatically on the next pipeline run (different run number).

Both features are local-only — **no backend mutation, no DB write**. The pipeline stays deterministic.

---

## 2. Risk

**MEDIUM.** New bulk-action UI surface, new XLSX export endpoint in `app.py`, new `localStorage` keys.

If the agent finds it has to mutate any pipeline output or any DB table, **stop and escalate** — the design forbids backend mutation.

---

## 3. Standard Rules (embedded — do not skip)

### Tooling note — read before any investigation
Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) to verify file content, file size, or function presence in Windows-mounted source files (`app.py`, `ui/jansa/*.jsx`, `src/reporting/*.py`, etc.). The Cowork sandbox's Linux mount caches a stale view of Windows files and has, in past sessions, falsely reported `app.py` as 864 lines when it was actually ~1200, and missed methods like `get_chain_onion_intel` that demonstrably existed. If a bash inspection contradicts the Read tool, the Read tool wins. Do not raise "repo is broken / method missing / file truncated" alarms from bash-only evidence — cross-check with Read first. Bash is fine for *executing* scripts (running `python main.py`, `pytest`, etc.); just don't use it to reason about source-file state. See `context/11_TOOLING_HAZARDS.md`.

### Priorities
1. App must always run.
2. Pipeline determinism is sacred — no backend mutation, no DB write.
3. Backend stays source of truth — UI calculates nothing.
4. Preserve working logic.
5. Minimal safe changes.
6. No fake certainty.

### Mandatory behavior
- Read every listed file fully before editing.
- The export endpoint accepts a list of selected document refs (`[{numero, indice}, ...]`) and writes an XLSX to `output/exports/`. It looks up the rows from `INTELLIGENCE_TAGS.csv` server-side; the UI only sends keys, not full rows.
- Filename pattern: `Intelligence_YYYY-MM-DD_HH-MM-SS.xlsx`.
- Treated state is stored in `localStorage` with the key pattern `intelligence_treated_<run_number>__<numero>__<indice>` (run number scoped). On run-number change, the keys silently become stale and the UI ignores them — no eager cleanup needed.
- After every export, the UI auto-marks the exported rows as treated (matches operator workflow: "I exported, I'm done with this batch").
- Treated rows render greyed/struck-through and their checkboxes are disabled.
- "Reset treated (this run)" button in the footer clears all treated keys for the current run number.

### Forbidden moves
- Do NOT mutate any pipeline artifact, including `INTELLIGENCE_TAGS.csv`.
- Do NOT write to `data/run_memory.db` or `data/report_memory.db`.
- Do NOT register the export file as a run artifact (it's an ad-hoc export, not part of the run).
- Do NOT introduce a new XLSX writer dependency. Use whatever pattern is already in `app.py` for the existing team-export (`export_team_version`).
- Do NOT modify `intelligence_query.py` to support write operations (read-only stays read-only).
- Do NOT modify `intelligence.jsx` filter/list logic from Phase 6C — only add the checkbox column, footer, and treated-row visual state.
- Do NOT use a new state-management library.
- Do NOT exceed 1000 rows in a single export. If the user has more rows selected, surface a warning and cap.

### Risk policy
MEDIUM. Apply directly after the plan is restated. Stop and escalate if the existing XLSX writer pattern in `app.py:export_team_version` is not reusable cleanly — that's a backend pattern question we want to avoid duplicating.

---

## 4. Current State (Findings)

### 4a. Existing XLSX export pattern
File: `app.py`. The `export_team_version()` method writes a registered team artifact and returns `{success: bool, path: str}`. Mirror its writing/return pattern for the new endpoint, **without** registering the file as a run artifact.

The shared XLSX helper (likely in `team_version_builder.py` or similar) is also reusable for the bulk-export sheet. Inspect to confirm — if it isn't cleanly callable in isolation, write a small standalone helper for the export sheet.

### 4b. Run number for keying treated state
The current run number is exposed to the UI in `window.OVERVIEW.run_number` (per `data_bridge.js`). Use that for the `localStorage` key prefix. If `OVERVIEW` is unavailable, fall back to the string `"unknown"` and warn in the console — treated state still works in-session.

### 4c. Phase 6C state
Phase 6C delivered the filter rail + work-tray with row click. Phase 6D extends only:
- The work-tray header gains "tout sélectionner" + per-row checkbox column.
- A footer panel appears when at least one row is selected.
- Treated rows render greyed.

The 6C debounce, sorting, filter semantics, empty state, and DCC row click stay unchanged.

---

## 5. User Value

- "Select 30 quick-win documents → click Export → take it to a meeting" workflow.
- Treated tracking lets the operator triage the same list across an afternoon without losing track.
- Resets automatically when a new pipeline run produces a fresh artifact.

---

## 6. Files

### READ (required, before any edit)
- `ui/jansa/intelligence.jsx` — full file (delivered in Phase 6C)
- `ui/jansa/data_bridge.js` — confirm structure for adding `exportIntelligenceSelection`
- `app.py` — `export_team_version` method and any XLSX writer it uses
- `src/team_version_builder.py` — XLSX writer pattern (read only — do not modify)
- `paths.py` — `OUTPUT_DIR` constant
- `ui/jansa/overview.jsx` — for the localStorage usage pattern (if any), and for `window.OVERVIEW.run_number` reference
- `README.md` §Output Artifacts (note: exports go in `output/exports/`)
- This MD

### MODIFY
- `ui/jansa/intelligence.jsx` — add checkbox column, bulk-action footer, treated-row visual state, "Reset treated" button.
- `ui/jansa/data_bridge.js` — add `exportIntelligenceSelection(selectedRefs)`.
- `app.py` — add `export_intelligence_selection(self, selected_refs: list) -> dict` returning `{success, path}` (NOT registered as run artifact).

### CREATE
- `src/reporting/intelligence_export.py` — small helper writing the XLSX. Mirror the existing team-export writer style. Single sheet `Intelligence`, columns identical to the work-tray columns, plus all `INTELLIGENCE_TAGS.csv` columns at the right. Sort: same as the UI (newest first).

### DO NOT TOUCH
- `src/pipeline/stages/*`
- `src/flat_ged/`, `src/chain_onion/`
- `src/reporting/intelligence_builder.py` (Phase 6A)
- `src/reporting/intelligence_query.py` (Phase 6B — read-only stays read-only; do not add write helpers there)
- `src/run_memory.py`, `src/report_memory.py`, `src/team_version_builder.py`, `src/effective_responses.py`
- `src/reporting/aggregator.py`, `data_loader.py`, `focus_filter.py`, `focus_ownership.py`, `ui_adapter.py`, `document_command_center.py`, `consultant_fiche.py`, `contractor_fiche.py`
- `output/intermediate/INTELLIGENCE_TAGS.csv` (Phase 6A artifact — read only)
- `runs/run_0000/`, `data/*.db`
- All other UI files except `intelligence.jsx` and `data_bridge.js`

---

## 7. Plan

### Step 1 — Backend export endpoint
Create `src/reporting/intelligence_export.py`:
```python
from datetime import datetime
from pathlib import Path
import pandas as pd
from paths import OUTPUT_DIR
from .intelligence_query import _load     # internal cache loader from Phase 6B; if private, expose a public wrapper

EXPORT_DIR = OUTPUT_DIR / "exports"
ROW_CAP = 1000

def export_selection(selected_refs: list) -> dict:
    """Write selected rows to output/exports/Intelligence_<ts>.xlsx.
    selected_refs: [{"numero": str, "indice": str}, ...]
    Returns {success, path, row_count, capped}.
    """
    if not selected_refs:
        return {"success": False, "error": "No selection."}
    selected_refs = selected_refs[:ROW_CAP]
    capped = len(selected_refs) > ROW_CAP

    df = _load()
    if df is None:
        return {"success": False, "error": "Intelligence artifact missing."}

    # Build a key set; preserve user order
    keys = {(r.get("numero",""), r.get("indice","")) for r in selected_refs}
    out = df[df.apply(lambda row: (str(row.get("numero","")), str(row.get("indice",""))) in keys, axis=1)]
    out = out.sort_values(["last_action_date", "numero"], ascending=[False, True], na_position="last")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = EXPORT_DIR / f"Intelligence_{ts}.xlsx"

    with pd.ExcelWriter(path, engine="openpyxl") as w:
        out.to_excel(w, sheet_name="Intelligence", index=False)

    return {"success": True, "path": str(path), "row_count": int(len(out)), "capped": capped}
```

Notes:
- If `_load` is private in 6B, add a public `load_dataframe()` wrapper there in this phase (small change explicitly allowed). Otherwise leave 6B alone.
- `openpyxl` is already in the project (used by `team_version_builder`). Confirm before writing.

### Step 2 — Wrap in `app.py`
```python
def export_intelligence_selection(self, selected_refs):
    self._cache_ready.wait()
    try:
        from reporting.intelligence_export import export_selection
        result = export_selection(selected_refs or [])
        if result.get("success") and self.open_file_in_explorer:
            self.open_file_in_explorer(result["path"])    # match existing team-export UX
        return _sanitize_for_json(result)
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"success": False, "error": str(exc)}
```
Mirror `export_team_version` style. **Do NOT register this file in `run_memory`.**

### Step 3 — Bridge method
In `ui/jansa/data_bridge.js`:
```js
exportIntelligenceSelection: async function (selectedRefs) {
  if (!bridge.api) return { success: false, error: "no backend" };
  try {
    var r = await bridge.api.export_intelligence_selection(selectedRefs || []);
    return r;
  } catch (e) { console.error("[data_bridge] export exception:", e); return { success: false, error: e.message }; }
}
```

### Step 4 — UI: checkbox column + selection state
In `ui/jansa/intelligence.jsx`:

1. Add `selected` state: `useState(new Set())` — keys are `${numero}|${indice}`.
2. Helper: `toggleRow(row)`, `selectAllVisible()`, `clearSelection()`.
3. Add a checkbox column at the front of the work-tray rows.
4. Header row checkbox = "select all visible (non-treated)".

### Step 5 — UI: treated-state via localStorage
1. Helper module-level functions:
   ```js
   function _runKey() { return (window.OVERVIEW && window.OVERVIEW.run_number) || "unknown"; }
   function _treatedKey(numero, indice) { return `intelligence_treated_${_runKey()}__${numero}__${indice}`; }
   function isTreated(numero, indice) { return !!localStorage.getItem(_treatedKey(numero, indice)); }
   function markTreated(refs) { refs.forEach(r => localStorage.setItem(_treatedKey(r.numero, r.indice), "1")); }
   function resetTreatedThisRun() {
     const prefix = `intelligence_treated_${_runKey()}__`;
     Object.keys(localStorage).filter(k => k.startsWith(prefix)).forEach(k => localStorage.removeItem(k));
   }
   ```
2. In the row render, if `isTreated(row.numero, row.indice)` is true:
   - Style row with reduced opacity (e.g. `0.45`), text-decoration `line-through` on numero/titre.
   - Disable the row checkbox.
   - Row click still opens DCC (operator may want to consult the doc).
3. Use a small force-rerender hook for treated-state changes (a `treatedTick` state incremented after `markTreated` / `resetTreatedThisRun`).

### Step 6 — UI: bulk-action footer
Render a sticky footer when `selected.size > 0`:
```
[ {N} sélectionné(s) ]   [ Effacer la sélection ]   [ Marquer traité ]   [ Exporter XLSX ]
```
Plus a separate, always-visible secondary action elsewhere on the page:
```
[ Réinitialiser les traités (run actuel) ]
```

Action handlers:
- "Marquer traité" → `markTreated([...selected].map(parseKey))` then `clearSelection()`.
- "Exporter XLSX" → calls `window.jansaBridge.exportIntelligenceSelection(selectedRefs)`. On success: show a transient toast "Export créé · {row_count} lignes", auto-mark exported rows as treated, clear selection.
- "Réinitialiser les traités (run actuel)" → confirm dialog, then `resetTreatedThisRun()`.

### Step 7 — Stop
Phase 6 complete after this. Validate against §8 and report.

---

## 8. Validation

| Check | How |
|---|---|
| App starts | `python -m py_compile app.py src/reporting/intelligence_export.py`; `python app.py` |
| Smoke export endpoint | `python -c "from reporting.intelligence_export import export_selection; print(export_selection([{'numero':'X','indice':'1'}]))"` returns success or graceful error |
| Checkbox visible | Each row has a checkbox; header has "select all visible" |
| Selection count | Footer appears when any row selected; shows correct count |
| Marquer traité | Click "Marquer traité" → selected rows render greyed/struck-through; checkboxes disabled; selection cleared |
| Persistence | Reload page → treated rows still greyed (within same run) |
| Run reset | Re-run pipeline (different run_number) → window.OVERVIEW.run_number changes → previously-treated rows render normal again |
| Export | Select 5 rows → click Export → file `output/exports/Intelligence_<ts>.xlsx` opens; contains those 5 rows + intelligence columns |
| Auto-treat after export | After export, the 5 exported rows render as treated |
| Cap | Select > 1000 rows (force test) → server caps at 1000 with `capped: true` warning |
| Reset button | "Réinitialiser les traités" clears localStorage prefix; rows revert to normal |
| No backend mutation | No changes to `INTELLIGENCE_TAGS.csv`, no DB writes; verify `git status data/`. |
| No regression | Phase 1–5 + 6A + 6B + 6C unaffected; filter rail, presets, debounce, row click → DCC all still work |

---

## 9. Cowork Handoff Prompt (paste-ready)

```
Objective:
Phase 6D — Add bulk export + local treated-state tracking to the Intelligence page from Phase 6C. Selection checkboxes, bulk-action footer, XLSX export to output/exports/, treated rows greyed, run-number-keyed localStorage. NO backend mutation. NO DB write.

Repository: GFUP_Backend / GF Updater v3 / 17&CO Tranche 2. Risk level: MEDIUM.

PREREQUISITE: Phase 6A, 6B, and 6C must already be merged. The Intelligence page must render and load filtered documents. If anything is missing, stop and escalate.

Read fully before editing:
- ui/jansa/intelligence.jsx (full file from Phase 6C)
- ui/jansa/data_bridge.js
- app.py — export_team_version pattern + open_file_in_explorer reference
- src/team_version_builder.py — XLSX writer pattern (read only — do not modify)
- src/reporting/intelligence_query.py — locate the cache loader (Phase 6B)
- paths.py (OUTPUT_DIR)
- ui/jansa/overview.jsx — for window.OVERVIEW.run_number reference
- README.md §Output Artifacts
- docs/implementation/PHASE_6D_INTELLIGENCE_EXPORT_AND_TREATED.md (this spec)

Do not touch:
- src/pipeline/stages/*, src/flat_ged/, src/chain_onion/
- src/reporting/intelligence_builder.py (Phase 6A)
- src/reporting/intelligence_query.py READ-ONLY semantics — but you MAY add a thin public load_dataframe() wrapper if the cache loader is private
- src/run_memory.py, src/report_memory.py, src/team_version_builder.py (read only), src/effective_responses.py
- src/reporting/aggregator.py, data_loader.py, focus_filter.py, focus_ownership.py, ui_adapter.py, document_command_center.py, consultant_fiche.py, contractor_fiche.py
- output/intermediate/INTELLIGENCE_TAGS.csv (Phase 6A artifact — read only)
- runs/run_0000/, data/*.db
- All other UI files except intelligence.jsx + data_bridge.js

Implement:

Backend:
1. Create src/reporting/intelligence_export.py with export_selection(selected_refs) -> {success, path, row_count, capped}. Caps at 1000 rows. Reuses the Phase 6B cache loader (add a thin public wrapper to intelligence_query.py if needed). Sorts newest first. Writes Intelligence_<ts>.xlsx to output/exports/ using openpyxl (already a project dependency). Single sheet. Same columns as INTELLIGENCE_TAGS.csv.
2. app.py: add export_intelligence_selection(selected_refs) — mirrors export_team_version style, returns _sanitize_for_json result. Calls open_file_in_explorer on success. DOES NOT register the file as a run_memory artifact.

UI:
3. data_bridge.js: add exportIntelligenceSelection(selectedRefs).
4. ui/jansa/intelligence.jsx:
   • Add `selected` Set state keyed by `${numero}|${indice}`.
   • Add checkbox column at front of each row; header "select all visible (non-treated)".
   • Helper functions: _runKey() reads window.OVERVIEW.run_number (fallback "unknown"), _treatedKey(numero, indice) = `intelligence_treated_${runKey}__${numero}__${indice}`, isTreated(numero, indice), markTreated(refs), resetTreatedThisRun() (delete all keys with that runKey prefix).
   • Treated rows render with opacity 0.45 + line-through; checkbox disabled. Row click still opens DCC.
   • Sticky footer when selected.size > 0: count + "Effacer la sélection" + "Marquer traité" + "Exporter XLSX".
   • "Marquer traité": markTreated(selected) then clearSelection().
   • "Exporter XLSX": call exportIntelligenceSelection(refs); on success → toast "Export créé · {row_count} lignes" + auto-markTreated(refs) + clearSelection().
   • Always-visible secondary action: "Réinitialiser les traités (run actuel)" with confirm dialog calling resetTreatedThisRun().
   • Force-rerender after treated changes (small treatedTick state).

Validation (must pass before reporting done):
- python -m py_compile app.py src/reporting/intelligence_export.py
- python -c "from reporting.intelligence_export import export_selection; print(export_selection([{'numero':'X','indice':'1'}]))" returns dict
- python app.py launches
- Intelligence page: each row has a checkbox; header select-all works
- Selecting rows shows the footer with count
- "Marquer traité": rows grey + line-through, checkboxes disabled, persist across reload
- Re-run pipeline (run_number changes) → previously-treated rows render normal again
- Export: file appears in output/exports/Intelligence_<ts>.xlsx with selected rows; auto-marked treated
- Cap > 1000 rows: server caps with capped:true; UI shows a warning toast
- "Réinitialiser les traités" clears localStorage prefix; rows revert
- INTELLIGENCE_TAGS.csv NOT modified (verify mtime unchanged)
- data/*.db NOT modified (verify with `git status data/`)
- Phase 1–5 + 6A + 6B + 6C unaffected; filter rail, presets, row click → DCC all work
- No console errors

Report back:
- Diff of all modified + new files
- Sample export run path + row count
- Confirmation of all validation steps including no-mutation checks

Hard rules:
- Pipeline determinism is sacred. NO mutation of INTELLIGENCE_TAGS.csv, NO writes to data/*.db, NO new run_memory artifact registration.
- Treated state is local-only, run-number-scoped, NEVER persisted to backend.
- Export caps at 1000 rows server-side.
- 6B's intelligence_query.py stays read-only (a thin public wrapper to expose the cache loader is OK; no business logic changes there).
- Auto-treat after successful export.
```

---

## 10. Context Update (after merge)

- `context/03_UI_FEED_MAP.md` — record `exportIntelligenceSelection` bridge method and `export_intelligence_selection` endpoint.
- `context/05_OUTPUT_ARTIFACTS.md` — note `output/exports/Intelligence_*.xlsx` (ad-hoc, not run-registered).
- `context/06_EXCEPTIONS_AND_MAPPINGS.md` — document the `localStorage` key pattern `intelligence_treated_<run_number>__<numero>__<indice>`.
- `README.md` §Output Artifacts — optionally note Intelligence ad-hoc exports.

If `context/` is missing the file, skip — do not create new context files in this phase.

---

## 11. Done Definition

- App launches cleanly.
- Intelligence page now offers per-row checkboxes, footer actions, and run-scoped treated state.
- Export writes XLSX to `output/exports/`; no backend mutation, no DB write, no run-artifact registration.
- Auto-treat after successful export.
- Run-number change resets treated state implicitly.
- Phase 1–5 + 6A + 6B + 6C unaffected.
- Diff scoped to: `src/reporting/intelligence_export.py` (new), optional small public wrapper added to `src/reporting/intelligence_query.py`, `app.py`, `ui/jansa/data_bridge.js`, `ui/jansa/intelligence.jsx`.
