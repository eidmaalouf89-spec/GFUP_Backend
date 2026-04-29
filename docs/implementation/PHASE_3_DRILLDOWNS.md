# Phase 3 — Dashboard Drilldowns (KPIs, Charts, Visa Flow)

This MD is **self-contained**. An agent assigned only this phase can execute it cold without reading any other file in `docs/implementation/`.

---

## 1. Objective

Make the Overview dashboard interactive: every KPI tile, chart segment, and visa flow band opens a right-side **backend-driven dashboard drilldown drawer** listing the underlying documents, **sorted from newest to oldest**. The drawer is a thin, dashboard-scoped renderer (NOT a generic reusable component shared with the rest of the app). The data is computed in the backend; the UI never calculates anything.

Drill-downs to implement:

| Trigger | List opened |
|---|---|
| KPI: "Documents soumis" | All submitted documents (entire project) |
| KPI: "Bloquants en attente" | All currently pending/blocking documents |
| Visa Flow: any segment (Soumis/Répondus/VSO/VAO/REF/HM/En attente/Dans les délais/En retard) | Documents matching that segment |
| Weekly chart: any week bin | Documents **opened** that ISO week (MVP scope — see §7 Step 2) |
| Focus radial: any priority ring (P1/P2/P3/P4) | Focus-filtered documents at that priority |

Each row in every drawer carries: `numero`, `indice`, `titre`, `emetteur` (canonical company name), `lot`, `last_action_date`, `latest_status`, `primary_owner`. Clicking any row opens the existing Document Command Center (`window.openDocumentCommandCenter(numero, indice)`).

---

## 2. Risk

**MEDIUM.** Touches `app.py` (new endpoint), `src/reporting/` (new builder), `ui/jansa/data_bridge.js` (new bridge method), and `ui/jansa/overview.jsx` (multiple click bindings + new drawer mount). No pipeline change, no chain_onion change, no schema change.

If the agent finds it has to modify any pipeline stage, focus_filter, or data_loader **stop and escalate** — the design assumes existing pre-computed columns are sufficient.

---

## 3. Standard Rules (embedded — do not skip)

### Tooling note — read before any investigation
Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) to verify file content, file size, or function presence in Windows-mounted source files (`app.py`, `ui/jansa/*.jsx`, `src/**/*.py`, etc.). The Cowork sandbox's Linux mount caches a stale view of Windows files and has, in past sessions, falsely reported `app.py` as 864 lines when it was actually ~1200, and missed methods like `get_chain_onion_intel` that demonstrably existed. If a bash inspection contradicts the Read tool, the Read tool wins. Do not raise "repo is broken / method missing / file truncated" alarms from bash-only evidence — cross-check with Read first. Bash is fine for *executing* scripts (running `python main.py`, `pytest`, etc.); just don't use it to reason about source-file state. See `context/11_TOOLING_HAZARDS.md`.

### Priorities
1. App must always run.
2. Backend stays source of truth — UI calculates nothing.
3. Preserve working logic.
4. Minimal safe changes.
5. No fake certainty.

### Mandatory behavior
- The new endpoint takes a `kind` discriminator and optional filters; it returns a fully shaped payload.
- All sorting, filtering, joining, and ownership resolution happen in the backend.
- The UI sends a request and renders the response. Period.
- Default sort across every drilldown: `last_action_date DESC` (newest first), tie-break by `numero` ascending for determinism.
- Result cap: hard limit of 1000 rows server-side; if the bucket exceeds the cap, return the most recent 1000 and include `truncated: true` + `total_count` in the payload metadata.

### Forbidden moves
- Do not edit `src/pipeline/stages/*`.
- Do not edit `src/flat_ged/`.
- Do not edit `src/chain_onion/`.
- Do not modify `data_loader.py` schemas — only consume existing columns.
- Do not edit `focus_filter.py` (Phase 5 territory).
- Do not introduce a new database, no caching layer, no async queue.
- Do not call `chain_onion` artifacts. Drilldown reads from `RunContext.dernier_df` + workflow_engine + (optional) FocusResult only.
- The drilldown drawer is a popover; **route never changes** when it opens.

### Risk policy
MEDIUM. Stop after the plan and wait for approval if you find that Visa Flow segment definitions in `compute_visa_global_with_date` differ from what the Visa Flow chart shows. Otherwise apply directly.

---

## 4. Current State (Findings)

### 4a. Existing components
- `ui/jansa/overview.jsx`:
  - `HeroKpi` (~line 54): supports an optional `onClick`. Currently passed for KPI tiles only when explicitly provided. The "Documents soumis" and "Bloquants en attente" tiles do **not** pass `onClick` today.
  - `VisaStage` (~line 303): renders horizontal stacked segments. Each segment is a `<div>` with no click handler.
  - `WeeklyActivity` (~line 346): SVG chart with `<rect>` bars and area paths. No interaction layer.
  - `FocusRadial` (~line 476): SVG concentric arcs. Visual only.
- `ui/jansa/fiche_base.jsx` (~56k characters): contains `DrilldownDrawer` component (per `README.md` UI module table). Reuse it; do not duplicate.
- `ui/jansa/document_panel.jsx`: holds the Document Command Center drawer. Triggered by `window.openDocumentCommandCenter(numero, indice)`.

### 4b. Existing backend hooks
- `app.py` already has `get_overview_for_ui`, `get_consultants_for_ui`, `get_contractors_for_ui`, `search_documents`, `get_document_command_center`. Drilldown endpoint will sit alongside these.
- `RunContext.dernier_df` (built by `data_loader.py`) carries the latest indice per numero. It contains: `doc_id`, `numero`, `indice`, `titre`, `emetteur`, `lot`, `_visa_global`, `_days_since_last_activity`, `_days_to_deadline`, `_focus_priority`, `_focus_owner`, `_focus_owner_tier`, plus various date columns.
- `workflow_engine.compute_visa_global_with_date(doc_id)` returns `(visa, date)` where `visa ∈ {VSO, VAO, REF, SAS REF, HM, None}`. Use this for segment classification — do not invent new logic.

### 4c. Existing emetteur naming gap
The `emetteur` column carries 3-letter codes (BEN, LGD, SNI, …). A canonical name map exists in `src/reporting/consultant_fiche.py` (~line 99): `{"BEN": {"name": "Bentin", "lots": [...]}, ...}`. Drilldown must apply this map before returning rows so the UI displays "Bentin" not "BEN". Phase 4 and Phase 5 will use the same map; in this phase, **do not centralize it yet** — read it where it is. If the agent prefers, expose a small helper `resolve_emetteur_name(code) -> str` in `src/reporting/contractor_fiche.py` (already exists) and use it. Do not duplicate the map in this phase.

---

## 5. User Value

- One click from any KPI / chart / band to the underlying documents.
- Always sorted newest first — operational priority is "what just happened".
- Clicking through to the Document Command Center is preserved (one extra click reveals everything else).

---

## 6. Files

### READ (required, before any edit)
- `ui/jansa/overview.jsx` — full file (~955 lines)
- `ui/jansa/fiche_base.jsx` — locate and read the `DrilldownDrawer` component
- `ui/jansa/document_panel.jsx` — confirm `window.openDocumentCommandCenter` signature
- `ui/jansa/data_bridge.js` — full file
- `app.py` — UI adapter section (~line 1015 onward)
- `src/reporting/data_loader.py` — confirm available `dernier_df` columns
- `src/reporting/aggregator.py` — patterns for iterating `dernier_df`
- `src/reporting/focus_filter.py` — read `_focus_priority` semantics, do not modify
- `src/reporting/contractor_fiche.py` — locate or add `resolve_emetteur_name`
- `README.md` §What Not To Touch

### MODIFY
- `app.py` — add `get_documents_drilldown(self, kind, params={}) -> dict` method.
- `ui/jansa/data_bridge.js` — add `loadDrilldown(kind, params) -> Promise<payload>`.
- `ui/jansa/overview.jsx` — add `onClick` to:
  - HeroKpi for "Documents soumis" and "Bloquants en attente"
  - Each `VisaStage` segment
  - Each `WeeklyActivity` bin (SVG `<rect>` overlay or transparent hit-target)
  - Each `FocusRadial` ring (transparent annular slice hit-targets)
  - Mount the drilldown drawer (or trigger the existing `DrilldownDrawer` from `fiche_base.jsx`)

### CREATE
- `src/reporting/drilldown_builder.py` — new module exposing:
  ```python
  def build_drilldown(ctx: RunContext, kind: str, params: dict, focus_result=None) -> dict:
      """Returns {rows: [...], total_count: int, truncated: bool, kind: str, params: dict}"""
  ```
  Rows are dicts with: `numero, indice, titre, emetteur_code, emetteur_name, lot, last_action_date, latest_status, primary_owner`.

### DO NOT TOUCH
- `src/pipeline/stages/*`
- `src/flat_ged/`
- `src/chain_onion/`
- `src/run_memory.py`, `src/report_memory.py`, `src/team_version_builder.py`, `src/effective_responses.py`
- `src/reporting/focus_filter.py` — read only (Phase 5 modifies it)
- `src/reporting/data_loader.py` — read only
- `runs/run_0000/`, `data/*.db`
- `ui/jansa-connected.html` (no new script tag needed since `DrilldownDrawer` is already in `fiche_base.jsx`)

---

## 7. Plan

### Step 1 — Define the `kind` taxonomy (frozen contract)
The endpoint accepts these `kind` values and parameter shapes (inputs to `build_drilldown`):

```
kind = "submitted"          params = {}                              → all dernier docs
kind = "pending_blocking"   params = {}                              → _visa_global is None / pending
kind = "visa_segment"       params = {"segment": "VSO"|"VAO"|"REF"|"SAS_REF"|"HM"|"PENDING_ON_TIME"|"PENDING_LATE"}
kind = "weekly"             params = {"week_label": "26-S14", "metric": "opened"|"closed"|"refused"}
kind = "focus_priority"     params = {"priority": 1|2|3|4}           → requires focus_result
```

Document this taxonomy at the top of `drilldown_builder.py` as a docstring. Any unknown `kind` returns `{"error": "unknown kind", "rows": []}`.

### Step 2 — Build `drilldown_builder.py`
Skeleton:

```python
from typing import Optional
import pandas as pd
from .data_loader import RunContext
from .focus_filter import FocusResult
from .contractor_fiche import resolve_emetteur_name  # add helper if missing

ROW_LIMIT = 1000

def _row_to_payload(row, latest_status, primary_owner) -> dict:
    code = (row.get("emetteur") or "").strip()
    return {
        "numero":        row.get("numero"),
        "indice":        row.get("indice"),
        "titre":         row.get("titre"),
        "emetteur_code": code,
        "emetteur_name": resolve_emetteur_name(code),
        "lot":           row.get("lot_normalized") or row.get("lot"),
        "last_action_date": _to_iso(row.get("last_real_activity_date") or row.get("response_date") or row.get("submittal_date")),
        "latest_status": latest_status,
        "primary_owner": primary_owner,
    }

def build_drilldown(ctx, kind, params=None, focus_result=None) -> dict:
    params = params or {}
    df = ctx.dernier_df
    if df is None or ctx.workflow_engine is None:
        return {"rows": [], "total_count": 0, "truncated": False, "kind": kind, "params": params}

    we = ctx.workflow_engine
    selected = []
    # ... per-kind selection logic, reading existing columns only
    # populate `selected` as a list of dicts via _row_to_payload

    selected.sort(key=lambda r: (r["last_action_date"] or ""), reverse=True)
    total = len(selected)
    truncated = total > ROW_LIMIT
    rows = selected[:ROW_LIMIT]
    return {"rows": rows, "total_count": total, "truncated": truncated, "kind": kind, "params": params}
```

Implementation notes per kind:

- `submitted`: every row in `dernier_df`. `latest_status` = result of `we.compute_visa_global_with_date(doc_id)[0]` or `"En attente"` if None.
- `pending_blocking`: rows where `_visa_global` is None (i.e., no terminal visa yet). Use the existing pre-computed column rather than recomputing.
- `visa_segment`:
  - `"VSO" | "VAO" | "REF" | "SAS_REF" | "HM"` → rows where `_visa_global == segment`.
  - `"PENDING_ON_TIME"` → `_visa_global is None and _days_to_deadline is not None and _days_to_deadline >= 0`.
  - `"PENDING_LATE"` → `_visa_global is None and _days_to_deadline is not None and _days_to_deadline < 0`.
- `weekly`: **MVP scope: only `metric=="opened"` is wired in this phase.** Parse `week_label` (e.g. `"26-S14"`) into ISO year+week; filter by submittal_date for opened. The endpoint should validate `metric ∈ {"opened","closed","refused"}` and accept all three values — but the UI only triggers `metric:"opened"` in this phase. Closed/refused wiring is intentionally deferred. Reuse the same week parsing logic that produced the labels in `ui_adapter.py:adapt_overview` weekly section — locate it and import or replicate the exact format.
- `focus_priority`: requires `focus_result` (passed in). Filter `dernier_df` rows where `_focus_priority == params["priority"]` and `_focus_owner_tier != "CLOSED"`. If `focus_result` is `None`, return empty + `error: "focus mode required"`.

Date helper `_to_iso`: convert pandas Timestamp/datetime/None to ISO 8601 string `"YYYY-MM-DD"` (drop time). If null, return `None`.

`primary_owner`: take the first element of `_focus_owner` list if non-empty, else fall back to the canonical primary consultant from `_focus_owner_tier` aggregation. Do not invent a value — if both unknown, return `None`.

### Step 3 — Wire `app.py` endpoint
```python
def get_documents_drilldown(self, kind, params=None, focus=False, stale_days=90):
    self._cache_ready.wait()
    try:
        params = params or {}
        ctx = self._get_run_context_cached()         # use the existing cached context accessor
        focus_result = self._get_focus_result(ctx, focus, stale_days) if focus else None
        from reporting.drilldown_builder import build_drilldown
        payload = build_drilldown(ctx, kind, params, focus_result)
        return _sanitize_for_json(payload)
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"error": str(exc), "rows": [], "kind": kind}
```

If accessor names differ, locate them in `app.py` (search for `dernier_df` or `RunContext`) and use whatever is already in place. Do not invent new caching.

### Step 4 — `data_bridge.js` method
```js
loadDrilldown: async function (kind, params, focusMode, staleDays) {
  if (!bridge.api) return { rows: [], total_count: 0, truncated: false };
  try {
    var r = await bridge.api.get_documents_drilldown(
      String(kind),
      params || {},
      !!focusMode,
      staleDays != null ? staleDays : 90
    );
    if (r && r.error) { console.error("[data_bridge] drilldown error:", r.error); return r; }
    return r;
  } catch (e) {
    console.error("[data_bridge] drilldown exception:", e);
    return { rows: [], total_count: 0, truncated: false };
  }
}
```

### Step 5 — Mount the drawer + wire onClicks
In `overview.jsx`:

1. At the top of `OverviewPage`, add local state:
   ```js
   const [drill, setDrill] = useStateOv(null); // { kind, params } or null
   ```
2. Add a generic handler:
   ```js
   const openDrill = (kind, params = {}) => setDrill({ kind, params });
   const closeDrill = () => setDrill(null);
   ```
3. Pass `onClick` callbacks down:
   - `KpiRow` — receives `openDrill`. Wire `onClick={() => openDrill('submitted')}` for "Documents soumis" and `onClick={() => openDrill('pending_blocking')}` for "Bloquants en attente".
   - `VisaFlow` — receives `openDrill`. Each segment becomes a `<button>` calling `openDrill('visa_segment', { segment: 'VSO' })` etc. Map segment label to canonical key.
   - `WeeklyActivity` — overlay an invisible `<rect>` per week bin with `onClick={() => openDrill('weekly', { week_label: w.label, metric: 'opened' })}`. Visual: highlight on hover. For now wire `metric: 'opened'` only (closed/refused can come later — keep scope tight).
   - `FocusRadial` — overlay invisible annular slices per ring (P1/P2/P3/P4). Use SVG `<path>` with stroke matching ring radius and `pointerEvents:'stroke'` + transparent stroke. `onClick={() => openDrill('focus_priority', { priority: 1 })}` etc.
4. Render the drawer when `drill !== null`:
   ```jsx
   {drill && (
     <DrilldownDrawer
       kind={drill.kind}
       params={drill.params}
       focusMode={focusMode}
       onClose={closeDrill}
       onRowClick={(row) => window.openDocumentCommandCenter(row.numero, row.indice)}
     />
   )}
   ```
5. **Build a thin dashboard-scoped drawer inside `overview.jsx`** (do NOT promote it to a generic reusable component). It must:
   - On mount, call `window.jansaBridge.loadDrilldown(drill.kind, drill.params, focusMode, staleDays)`.
   - Render header (title derived from `kind` + `params` per §6 Step 6), show truncation banner if `truncated`, list rows with click handler, have a close button.
   - Inherit visual style from existing drawers (right-side, ~45% width, backdrop click closes).

Reusing `fiche_base.jsx`'s `DrilldownDrawer` is acceptable only if it accepts this exact API with zero changes. If it does not, **do NOT modify `fiche_base.jsx`** — keep the new drawer local to `overview.jsx`. Generic reusability is explicitly NOT a goal of this phase.

### Step 6 — Drawer header copy (French)
- `submitted` → "Tous les documents soumis"
- `pending_blocking` → "Bloquants en attente"
- `visa_segment`:
  - `VSO` → "Documents en VSO"
  - `VAO` → "Documents en VAO"
  - `REF` → "Documents en refus (REF)"
  - `SAS_REF` → "Documents bloqués SAS"
  - `HM` → "Documents Hors Marché"
  - `PENDING_ON_TIME` → "En attente · dans les délais"
  - `PENDING_LATE` → "En attente · en retard"
- `weekly` → "Documents — semaine {week_label}"
- `focus_priority` → "Focus · P{priority}"

Show subtitle: `"Tri : du plus récent au plus ancien · {total_count} document(s)"` and (if truncated) `"Affichage limité aux 1 000 plus récents"`.

---

## 8. Validation

| Check | How |
|---|---|
| App starts | `python -m py_compile app.py`; `python app.py` |
| New module imports | `python -c "from reporting.drilldown_builder import build_drilldown"` |
| Submitted drill | Click "Documents soumis" → drawer opens, count matches the KPI (within truncation cap) |
| Pending drill | Click "Bloquants en attente" → drawer count matches the KPI |
| Visa segment | Click each VisaFlow band → drawer rows match expected segment |
| Weekly bin | Click a week bar → drawer shows that week's openings |
| Focus radial (focus mode on) | Click P1/P2/P3/P4 ring → drawer shows priority-filtered docs |
| Sort order | First row's `last_action_date` ≥ last row's `last_action_date` |
| Row click | Clicking a row opens the existing Document Command Center for that numero/indice |
| Emetteur name | Drawer shows "Bentin" not "BEN" (etc.) |
| Truncation | If a bucket > 1000, banner appears, total_count is correct |
| No console errors | Both modes |
| No regression | All Phase 1+2 functionality still works |

Smoke test command (sandbox):
```python
from reporting.drilldown_builder import build_drilldown
from app import _build_run_context_for_smoke   # use existing helper or inline
ctx = _build_run_context_for_smoke()
print(build_drilldown(ctx, "submitted")["total_count"])
print(build_drilldown(ctx, "pending_blocking")["total_count"])
print(build_drilldown(ctx, "visa_segment", {"segment": "VSO"})["total_count"])
```

---

## 9. Cowork Handoff Prompt (paste-ready)

```
Objective:
Phase 3 — Add backend-driven drilldowns to the Overview dashboard. KPI tiles, visa flow bands, weekly chart bins, and focus radial rings each open a right-side drawer listing the underlying documents (newest first). UI calculates nothing.

Repository: GFUP_Backend / GF Updater v3 / 17&CO Tranche 2. Risk level: MEDIUM.

Read fully before editing:
- ui/jansa/overview.jsx
- ui/jansa/fiche_base.jsx (locate the existing DrilldownDrawer)
- ui/jansa/document_panel.jsx (confirm window.openDocumentCommandCenter signature)
- ui/jansa/data_bridge.js
- app.py UI adapter section (~line 1015 onward)
- src/reporting/data_loader.py (confirm dernier_df columns: doc_id, numero, indice, titre, emetteur, lot_normalized, _visa_global, _days_since_last_activity, _days_to_deadline, _focus_priority, _focus_owner, _focus_owner_tier)
- src/reporting/aggregator.py (patterns for iterating dernier_df)
- src/reporting/focus_filter.py (read only — do not modify)
- src/reporting/contractor_fiche.py (locate or add resolve_emetteur_name)
- src/reporting/consultant_fiche.py ~line 99 (canonical name map BEN→Bentin etc.)
- README.md "What Not To Touch"
- docs/implementation/PHASE_3_DRILLDOWNS.md (this spec)

Do not touch:
- src/pipeline/stages/*
- src/flat_ged/
- src/chain_onion/
- src/reporting/data_loader.py (read only)
- src/reporting/focus_filter.py (read only — Phase 5 modifies it)
- src/run_memory.py, src/report_memory.py, src/team_version_builder.py, src/effective_responses.py
- runs/run_0000/, data/*.db
- ui/jansa-connected.html

Implement:
1. Create src/reporting/drilldown_builder.py with `build_drilldown(ctx, kind, params, focus_result=None) -> {rows, total_count, truncated, kind, params}`.
   Supported kinds and params:
     • submitted          {}
     • pending_blocking   {}
     • visa_segment       {segment: VSO|VAO|REF|SAS_REF|HM|PENDING_ON_TIME|PENDING_LATE}
     • weekly             {week_label, metric: opened|closed|refused}
     • focus_priority     {priority: 1|2|3|4}  — requires focus_result
   Each row carries: numero, indice, titre, emetteur_code, emetteur_name (canonical), lot, last_action_date (ISO), latest_status, primary_owner.
   Hard cap 1000 rows. Sort newest first by last_action_date DESC, tie-break by numero ASC. truncated/total_count reported.
   Reuse existing pre-computed columns; do not recompute. Use workflow_engine.compute_visa_global_with_date for status. resolve_emetteur_name for canonical company name (BEN→Bentin etc.).

2. Add app.py method get_documents_drilldown(kind, params={}, focus=False, stale_days=90) — wires drilldown_builder and returns _sanitize_for_json payload.

3. Add data_bridge.js method loadDrilldown(kind, params, focusMode, staleDays).

4. In ui/jansa/overview.jsx:
   • Add useState `drill` + `openDrill`/`closeDrill`.
   • Wire onClick for HeroKpi "Documents soumis" → openDrill('submitted').
   • Wire onClick for HeroKpi "Bloquants en attente" → openDrill('pending_blocking').
   • Make each VisaStage segment clickable → openDrill('visa_segment', {segment}).
   • Add transparent <rect> hit-targets per WeeklyActivity bin → openDrill('weekly', {week_label, metric: 'opened'}). MVP scope: only `metric: 'opened'` is wired. Closed/refused click bindings are intentionally deferred.
   • Add transparent annular hit-targets per FocusRadial ring → openDrill('focus_priority', {priority}).
   • Mount a drawer when drill !== null. Render header copy in French per spec §6 "Drawer header copy". Subtitle shows total + truncation. Each row clickable → window.openDocumentCommandCenter(row.numero, row.indice).
   • Prefer a thin local drawer component over editing fiche_base.jsx's DrilldownDrawer.

5. Default sort across every drilldown is last_action_date DESC, newest first. Always.

Validation (must pass before reporting done):
- python -m py_compile app.py
- python -c "from reporting.drilldown_builder import build_drilldown; print('ok')"
- python app.py launches
- Each KPI tile / visa segment / week bin / focus ring opens the correct drawer
- First row date ≥ last row date in every drawer
- Row click opens DCC drawer (existing behavior preserved)
- Emetteur shows canonical name (Bentin, Legendre, …), not raw 3-letter code
- Truncation banner appears for buckets > 1000 rows
- Phase 1 + 2 functionality still works (layout reorder, expand button, French synthesis, direct fiche nav)

Report back:
- Diff of all modified files + new file
- Sample payload for each kind
- Confirmation that all validation steps passed
- Any deviations and why

Hard rules:
- No calculation in UI. Backend builds the payload, UI renders.
- Read existing pre-computed columns only. Do not modify focus_filter.py, data_loader.py, or anything in src/pipeline/.
- Drawer is a popover; route does not change.
- Sort is always newest first.
- Always cap at 1000 rows server-side.
```

---

## 10. Context Update (after merge)

- `context/02_DATA_FLOW.md` — note that `get_documents_drilldown` reads from `RunContext.dernier_df` + workflow_engine, no new columns.
- `context/03_UI_FEED_MAP.md` — record the new KPI/chart/segment → drawer mapping.
- `context/05_OUTPUT_ARTIFACTS.md` — no new artifact (drilldown is in-memory only).
- `context/07_OPEN_ITEMS.md` — close items about "drilldowns missing on dashboard".

If `context/` is missing the file, skip — do not create new context files in this phase.

---

## 11. Done Definition

- App launches cleanly.
- Every drilldown trigger opens the correct drawer with newest-first sorted rows.
- Emetteur is canonical (Bentin, not BEN).
- Truncation handled.
- Row click opens DCC.
- No edit to pipeline, data_loader, focus_filter, chain_onion, or any frozen module.
- Diff scoped to: `app.py`, `ui/jansa/data_bridge.js`, `ui/jansa/overview.jsx`, `src/reporting/drilldown_builder.py` (new), optionally `src/reporting/contractor_fiche.py` (only if `resolve_emetteur_name` helper had to be added there).
