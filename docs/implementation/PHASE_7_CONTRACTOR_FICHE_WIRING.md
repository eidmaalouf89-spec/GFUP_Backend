# Phase 7 — Contractor Fiche Wiring  *[SUPERSEDED 2026-04-29]*

> ⚠ **This plan has been superseded by `PHASE_7_CONTRACTOR_QUALITY_FICHE.md`.** Do not execute the steps below.
>
> **Reason:** Inspection during execution revealed that `ui/jansa/fiche_base.jsx` is a monolithic consultant fiche (only `ConsultantFiche` and `DrilldownDrawer` are exposed; ~20 internal components are not). The contractor builder's payload shape (`block1_submission_timeline`, `block2_visa_chart`, `block3_document_table`, `block4_quality`) does not map onto consultant components. The "brutal reuse" approach assumed a primitive layer that does not exist.
>
> **What survives from this plan:** Step 2 (`get_contractor_fiche_for_ui` thin wrapper in `app.py`) and Step 3 (`loadContractorFiche` bridge method in `data_bridge.js`) were implemented and are reused by the new plan. The new plan extends the wrapper to merge a quality payload from a new sibling backend module.
>
> **Original plan kept as historical record only.**

---

This MD is **self-contained**. An agent assigned only this phase can execute it cold without reading any other file in `docs/implementation/`.

---

## 1. Objective

Wire the existing backend `get_contractor_fiche` builder to the UI so that:

1. Clicking **"Entreprise de la semaine"** on the dashboard opens that contractor's fiche directly.
2. Clicking any contractor card on the Contractors page opens its fiche.
3. The fiche page renders contractor-specific KPIs, lots, and document lists pulled from `src/reporting/contractor_fiche.py`.

The backend builder already exists per `README.md` §Contractors Page ("`get_contractor_fiche` exists in `src/reporting/contractor_fiche.py` but the bridge call from the UI is not wired"). This phase is the wiring.

---

## 2. Risk

**MEDIUM-HIGH.** New shell route, new fiche page component, new bridge method, new app.py UI adapter method that wraps the existing builder. The fiche page itself is a meaningful new surface, comparable in scope to the existing consultant fiche.

If the agent finds that `get_contractor_fiche` does not actually exist in the backend, **stop and escalate** — this phase assumes the builder is real and complete (per the README claim). If only a stub exists, this phase becomes a much larger backend task.

---

## 3. Standard Rules (embedded — do not skip)

### Tooling note — read before any investigation
Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) to verify file content, file size, or function presence in Windows-mounted source files (`app.py`, `src/reporting/contractor_fiche.py`, `ui/jansa/*.jsx`, etc.). The Cowork sandbox's Linux mount caches a stale view of Windows files and has, in past sessions, falsely reported `app.py` as 864 lines when it was actually ~1200, and missed methods like `get_contractor_fiche` / `get_chain_onion_intel` that demonstrably existed. If a bash inspection contradicts the Read tool, the Read tool wins. Do not raise "backend builder is missing / file truncated" alarms from bash-only evidence — cross-check with Read first. Bash is fine for *executing* scripts (running `python main.py`, `pytest`, etc.); just don't use it to reason about source-file state. See `context/11_TOOLING_HAZARDS.md`.

### Priorities
1. App must always run.
2. Backend stays source of truth — UI calculates nothing.
3. Preserve working logic.
4. Minimal safe changes.
5. No fake certainty.
6. Match the existing consultant fiche pattern wherever possible. Do not invent new UI primitives.

### Mandatory behavior
- Read `src/reporting/contractor_fiche.py` end-to-end before writing the wrapper. Confirm `get_contractor_fiche` (or whatever the public function is called) accepts a code or name and returns a structured payload.
- **REUSE THE CONSULTANT FICHE STRUCTURE BRUTALLY.** The contractor fiche page is a near-copy of `ui/jansa/fiche_page.jsx` with field renames. No new layout invention. No new visual language. No new sections beyond what consultant fiche already has. If the contractor payload lacks a field that consultant fiche shows (e.g. "consultant role" → "lots intervened"), pass a conceptually-equivalent string and reuse the same primitive verbatim. If a section makes no sense for contractors at all, hide it (`null`) but do not redesign around the gap.
- Do NOT fork or duplicate the layout system in `fiche_base.jsx`. If a primitive is consultant-specific and won't fit, add a small adapter prop — do not rewrite the primitive.
- Navigation pattern matches the consultant fiche: shell holds the active page; an `onOpenContractor(c)` handler loads fiche data via the bridge and sets `active = 'ContractorFiche'`. Same lifecycle as `ConsultantFiche`.
- Fiche payload is shaped by the backend. UI never recomputes.
- Loading and error states must be explicit (spinner during load, friendly message if fiche payload is `{error: ...}`).

### Forbidden moves
- Do NOT modify `src/reporting/contractor_fiche.py` business logic. Read only. If a thin export shim is missing, add it minimally.
- Do NOT redefine the fiche layout — reuse `fiche_base.jsx` primitives.
- Do NOT modify pipeline stages, chain_onion, run_memory, report_memory.
- Do NOT change the routing names of existing routes (`Consultants`, `ConsultantFiche`, `Contractors`).
- Do NOT introduce a new state-management library.
- Do NOT cache the fiche payload on the Python side — let the existing app cache (if any) handle it. New caching is out of scope.

### Risk policy
MEDIUM-HIGH. Stop and escalate if:
- `get_contractor_fiche` doesn't exist or returns a placeholder.
- The fiche layout primitives are too tightly coupled to consultant-specific data shapes for clean reuse.
- The shell's existing fiche-navigation handler can't be straightforwardly adapted.

Otherwise apply directly after restating the plan.

---

## 4. Current State (Findings)

### 4a. Backend builder
File: `src/reporting/contractor_fiche.py`. Per `README.md`:
> `get_contractor_fiche` exists in `src/reporting/contractor_fiche.py` but the bridge call from the UI is not wired.

Verify the actual signature on read. Expected shape (mirrors `consultant_fiche`):
```python
def get_contractor_fiche(ctx: RunContext, code_or_name: str, focus_result=None, ...) -> dict:
    """Return: {header, kpis, lots[], documents[], visa_breakdown, focus_summary, ...}"""
```

If a helper `resolve_emetteur_name` was added in Phase 3/4/5, reuse it for the header display name.

### 4b. UI fiche pattern (existing)
- `ui/jansa/fiche_base.jsx` — layout primitives: `OvCard`-equivalent, headers, KPI grid, document drilldown panel, breadcrumb. Shared.
- `ui/jansa/fiche_page.jsx` — `ConsultantFichePage` wrapper. ~250 lines. This is the model to follow.
- `ui/jansa/shell.jsx` — current consultant nav handler (~lines 600–680). Loads fiche data via `jansaBridge.loadFiche(name, focusMode, staleDays)` then sets `active = 'ConsultantFiche'`. Phase 2 already exposed `onOpenConsultant` to the dashboard.

### 4c. Dashboard "Entreprise de la semaine"
File: `ui/jansa/overview.jsx`. `BestPerformerCard` for the contractor (~line 154) currently does `onClick={() => onNavigate('Contractors')}`. After Phase 2, the consultant equivalent goes directly to a fiche; the contractor side was deferred to this phase.

### 4d. Contractors tab
File: `ui/jansa/contractors.jsx`. `ContractorCard` (~line 119) has `cursor: 'default'` and no click handler. After Phase 5, all 29 enriched cards render. This phase adds click → fiche.

### 4e. Existing bridge
File: `ui/jansa/data_bridge.js`. Methods today: `init`, `refreshForFocus`, `loadFiche` (consultant), `searchDocuments`, `loadDocumentCommandCenter`. Add `loadContractorFiche(code, focusMode, staleDays)` mirroring `loadFiche`.

---

## 5. User Value

- Click "Entreprise de la semaine" on the dashboard → land on Bentin's full fiche.
- Click any contractor card on the Contractors tab → same.
- One screen with all the contractor's documents, visa breakdown, lots, focus snapshot — exactly like consultants.

---

## 6. Files

### READ (required, before any edit)
- `src/reporting/contractor_fiche.py` — full file
- `src/reporting/consultant_fiche.py` — for comparison
- `src/reporting/data_loader.py` — RunContext shape (read only)
- `app.py` — `get_fiche_for_ui` method (~line 1066) for pattern; UI adapter section
- `ui/jansa/fiche_page.jsx` — full file (~250 lines)
- `ui/jansa/fiche_base.jsx` — full file (large; locate the layout primitives and the DrilldownDrawer)
- `ui/jansa/data_bridge.js` — full file
- `ui/jansa/shell.jsx` — focus on the consultant fiche nav handler and the route map (~lines 600–680, 670–700)
- `ui/jansa/overview.jsx` — `BestPerformerCard` for "Entreprise de la semaine" (~line 154) and `KpiRow`
- `ui/jansa/contractors.jsx` — `ContractorCard` (~line 119)
- `ui/jansa-connected.html` — script tag list
- `README.md` §Contractors Page, §JANSA UI Architecture, §What Not To Touch
- This MD

### MODIFY
- `app.py` — add `get_contractor_fiche_for_ui(self, code_or_name, focus=False, stale_days=90) -> dict`. Mirror `get_fiche_for_ui` pattern.
- `ui/jansa/data_bridge.js` — add `loadContractorFiche(code, focusMode, staleDays)`.
- `ui/jansa/shell.jsx` —
  - Add `onOpenContractor(c)` handler mirroring the consultant one. It calls `jansaBridge.loadContractorFiche(c.code, focusMode, staleDays)`, sets `selectedContractor`, sets `active = 'ContractorFiche'`.
  - Add route `{active === 'ContractorFiche' && <ContractorFichePage contractor={selectedContractor} onBack={() => navigateTo('Contractors')} focusMode={focusMode}/>}`.
  - Pass `onOpenContractor` to `OverviewPage` and `ContractorsPage`.
- `ui/jansa/overview.jsx` —
  - `OverviewPage` accepts `onOpenContractor`.
  - `KpiRow` passes `onOpenContractor` and `data.best_contractor` to the contractor `BestPerformerCard`.
  - `BestPerformerCard` for Entreprise: replace `onClick={() => onNavigate('Contractors')}` with `onClick={() => onOpenContractor(data.best_contractor)}`.
- `ui/jansa/contractors.jsx` —
  - `ContractorsPage` accepts `onOpenContractor`.
  - `ContractorCard` accepts an `onOpen` prop; root `<div>` becomes clickable (cursor pointer); calls `onOpen(c)`.
  - `ContractorChip` (low-doc fallback) — keep non-clickable in this phase OR enable click only if backend supports < 5 doc fiches. Default: keep chip non-clickable, document why.
- `ui/jansa-connected.html` — add `<script src="ui/jansa/contractor_fiche_page.jsx">` tag.

### CREATE
- `ui/jansa/contractor_fiche_page.jsx` — new file, contractor counterpart to `fiche_page.jsx`. Exports `ContractorFichePage`. Uses `fiche_base.jsx` primitives.

### DO NOT TOUCH
- `src/reporting/contractor_fiche.py` business logic (only add a thin shim if absolutely required and approved)
- `src/reporting/consultant_fiche.py`
- `src/reporting/data_loader.py`
- `src/reporting/aggregator.py`, `focus_filter.py`, `focus_ownership.py`, `ui_adapter.py`
- `src/chain_onion/`
- `src/flat_ged/`, `src/run_memory.py`, `src/report_memory.py`, `src/team_version_builder.py`, `src/effective_responses.py`, `src/pipeline/stages/*`
- `runs/run_0000/`, `data/*.db`
- `ui/jansa/fiche_base.jsx` (read only — reuse primitives, do not edit)
- `ui/jansa/fiche_page.jsx` (read only)
- `ui/jansa/document_panel.jsx`
- All other UI files except those in §MODIFY/CREATE

---

## 7. Plan

### Step 1 — Inspect the backend builder
Read `src/reporting/contractor_fiche.py` fully. Confirm:
- The public function name (likely `get_contractor_fiche`).
- Its inputs (probably `ctx, code_or_name, focus_result=None, stale_days=90` or similar).
- Its return shape — list every top-level key.

If the function doesn't exist or returns a dict with `{"todo": True}` or similar placeholder, **stop and escalate**. Phase 7 cannot proceed.

If the function exists but does not handle canonical name mapping (BEN→Bentin), don't fix it here — that's Phase 5's territory. Use whatever shape it currently returns and accept code OR name for the input.

### Step 2 — Wrap in `app.py`
Mirror `get_fiche_for_ui`:
```python
def get_contractor_fiche_for_ui(self, code_or_name, focus=False, stale_days=90):
    """Return contractor fiche payload for one emetteur. Mirrors get_fiche_for_ui."""
    self._cache_ready.wait()
    try:
        ctx = self._get_run_context_cached()    # use whatever accessor is already in app.py
        focus_result = self._get_focus_result(ctx, focus, stale_days) if focus else None
        from reporting.contractor_fiche import get_contractor_fiche
        payload = get_contractor_fiche(ctx, code_or_name, focus_result=focus_result, stale_days=stale_days)
        return _sanitize_for_json(payload)
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"error": str(exc)}
```

If `app.py`'s existing accessors are differently named, locate them (search for `dernier_df` or `RunContext`) and use what is in place. Do not introduce new caching.

### Step 3 — Add bridge method
In `ui/jansa/data_bridge.js`:
```js
loadContractorFiche: async function (code, focusMode, staleDays) {
  if (!bridge.api) {
    window.CONTRACTOR_FICHE_DATA = null;
    return;
  }
  try {
    var result = await bridge.api.get_contractor_fiche_for_ui(
      String(code),
      !!focusMode,
      staleDays != null ? staleDays : 90
    );
    if (result && !result.error) {
      window.CONTRACTOR_FICHE_DATA = result;
    } else {
      console.error("[data_bridge] Contractor fiche load error:", result && result.error);
      window.CONTRACTOR_FICHE_DATA = null;
    }
  } catch (e) {
    console.error("[data_bridge] Contractor fiche load exception:", e);
    window.CONTRACTOR_FICHE_DATA = null;
  }
}
```

### Step 4 — Create `contractor_fiche_page.jsx`
**Brutally mirror** `fiche_page.jsx`. Take it as a starting copy, rename `Consultant` → `Contractor`, swap the data field reads, and stop. No layout reinvention, no new section types, no new design tokens.
```jsx
function ContractorFichePage({ contractor, onBack, focusMode }) {
  const data = window.CONTRACTOR_FICHE_DATA;
  if (!data) return <FicheLoading onBack={onBack}/>;
  if (data.error) return <FicheError message={data.error} onBack={onBack}/>;
  return (
    <FicheLayout
      header={...}        // emetteur_name + code, lots, role
      kpis={...}          // total_submitted, approval_rate, ref_rate, focus_owned
      visaBreakdown={...} // VSO/VAO/REF/SAS REF/HM
      lotsCard={...}      // lots[]
      documents={...}     // documents[] — drilldown drawer
      focusPanel={...}    // when focusMode
      onBack={onBack}
    />
  );
}
Object.assign(window, { ContractorFichePage });
```

Use the existing `FicheLayout` (or whatever the fiche_base.jsx primitive is called) verbatim. Pass contractor-shaped props.

If a needed primitive doesn't exist (e.g. consultant fiche has a "consultant role" header field with no contractor analogue), pass `null` and let the primitive render gracefully. Do not edit the primitive.

### Step 5 — Wire shell
In `ui/jansa/shell.jsx`:
- Add `selectedContractor` state alongside `selectedConsultant`.
- Add `onOpenContractor` handler:
  ```js
  async function onOpenContractor(contractor) {
    setSelectedContractor(contractor);
    await window.jansaBridge.loadContractorFiche(contractor.code, focusModeRef.current, staleDaysRef.current);
    navigateTo('ContractorFiche');
  }
  ```
- Add route in the page-switch block:
  ```jsx
  {active === 'ContractorFiche' && (
    <ContractorFichePage contractor={selectedContractor}
                         onBack={() => navigateTo('Contractors')}
                         focusMode={focusMode}/>
  )}
  ```
- Pass `onOpenContractor` to `<OverviewPage onOpenContractor={onOpenContractor} ...>` and `<ContractorsPage onOpenContractor={onOpenContractor} ...>`.

### Step 6 — Wire dashboard
In `ui/jansa/overview.jsx`:
- `OverviewPage(focusMode, onNavigate, onOpenConsultant, onOpenContractor)` — accept the new prop.
- `KpiRow` accepts `onOpenContractor` and passes it down.
- `BestPerformerCard` for Entreprise: change `onClick` to `onOpenContractor(data.best_contractor)`.

`data.best_contractor` shape: `{code, name, pass_rate, delta}` — from `adapt_overview`. The shell handler signature accepts a `{code}`; you may also pass `name` for display fallback if loadContractorFiche fails.

### Step 7 — Wire Contractors tab
In `ui/jansa/contractors.jsx`:
- `ContractorsPage(focusMode, onOpenContractor)` accepts the prop.
- Pass `onOpen={onOpenContractor}` to each `ContractorCard`.
- `ContractorCard` adds `onClick={() => onOpen(c)}`, `cursor: 'pointer'`, hover styling consistent with existing consultant cards.

`ContractorChip` (the low-doc fallback): keep non-clickable for this phase. Document with a comment why ("backend builder gates on min doc count" or similar — confirm during Step 1).

### Step 8 — Register the new JSX file
In `ui/jansa-connected.html`, add:
```html
<script type="text/babel" data-presets="react" src="ui/jansa/contractor_fiche_page.jsx"></script>
```
Place it next to the other JSX `<script>` tags. Order matters only if `ContractorFichePage` depends on a globally exported component — make sure `fiche_base.jsx` is registered earlier.

---

## 8. Validation

| Check | How |
|---|---|
| App starts | `python -m py_compile app.py`; `python app.py` |
| Bridge method | `window.jansaBridge.loadContractorFiche` is a function |
| Best entreprise click | Click "Entreprise de la semaine" → fiche page renders for that contractor |
| Contractor card click | Click any enriched card on the Contractors tab → fiche renders |
| Back nav | "Back" / breadcrumb returns to the Contractors list |
| Header correct | Fiche header shows canonical name (e.g. "Bentin") not raw code |
| KPIs match | Top KPIs match what the card preview showed (docs, pass_rate) |
| Visa breakdown | VSO/VAO/REF totals match aggregator output |
| Documents drilldown | List of contractor's documents renders, sorted (preferred newest first); each row clickable into DCC |
| Focus mode | When focus mode is on, fiche shows focus_owned panel |
| Error state | Force `get_contractor_fiche` to return `{"error":...}` (e.g. unknown code) → friendly error renders, no crash |
| No regression | Phase 1–6 functionality intact (consultant fiche still works, dashboard drilldowns still work, intelligence tab still loads) |
| No console errors | All flows |
| Chip non-clickable | Plain `ContractorChip` items (low-doc fallback) do not navigate |

Smoke command:
```python
python -c "
from app import Api
api = Api()
api._cache_ready.wait()
print(api.get_contractor_fiche_for_ui('BEN'))
"
```

---

## 9. Cowork Handoff Prompt (paste-ready)

```
Objective:
Phase 7 — Wire the existing src/reporting/contractor_fiche.py:get_contractor_fiche backend builder to the UI. Add a contractor fiche page that renders when "Entreprise de la semaine" or any Contractors-tab card is clicked.

Repository: GFUP_Backend / GF Updater v3 / 17&CO Tranche 2. Risk level: MEDIUM-HIGH.

CRITICAL: Verify the backend builder exists and returns real data before any UI work. If it's a stub or missing, stop and escalate — Phase 7 does not include backend implementation.

Read fully before editing:
- src/reporting/contractor_fiche.py (full file — confirm public function name, inputs, return shape)
- src/reporting/consultant_fiche.py (comparison)
- src/reporting/data_loader.py (RunContext shape — read only)
- app.py get_fiche_for_ui (~line 1066) and the UI adapter section
- ui/jansa/fiche_page.jsx (full file — model for ContractorFichePage)
- ui/jansa/fiche_base.jsx (locate layout primitives and DrilldownDrawer; read only)
- ui/jansa/data_bridge.js (full file)
- ui/jansa/shell.jsx (consultant fiche nav handler ~lines 600–680, route map)
- ui/jansa/overview.jsx (BestPerformerCard for Entreprise ~line 154; KpiRow)
- ui/jansa/contractors.jsx (ContractorCard ~line 119)
- ui/jansa-connected.html (script tag list)
- README.md §Contractors Page, §JANSA UI Architecture, §What Not To Touch
- docs/implementation/PHASE_7_CONTRACTOR_FICHE_WIRING.md (this spec)

Do not touch:
- src/reporting/contractor_fiche.py business logic (read only — only add a public shim if absolutely required and approved)
- src/reporting/consultant_fiche.py
- src/reporting/aggregator.py, focus_filter.py, focus_ownership.py, ui_adapter.py
- src/chain_onion/, src/flat_ged/, src/run_memory.py, src/report_memory.py, src/team_version_builder.py, src/effective_responses.py, src/pipeline/stages/*
- runs/run_0000/, data/*.db
- ui/jansa/fiche_base.jsx (read only — reuse primitives)
- ui/jansa/fiche_page.jsx (read only — copy pattern, don't fork)
- ui/jansa/document_panel.jsx
- All other UI files except those listed in MODIFY/CREATE below

Implement:
1. Inspect contractor_fiche.py — confirm get_contractor_fiche signature and return shape. Stop and escalate if it's missing or returns placeholder.

2. app.py: add get_contractor_fiche_for_ui(code_or_name, focus=False, stale_days=90) mirroring get_fiche_for_ui. Returns _sanitize_for_json payload, {error: str} on exception.

3. ui/jansa/data_bridge.js: add loadContractorFiche(code, focusMode, staleDays). Populates window.CONTRACTOR_FICHE_DATA. Handles missing-api and error cases like the consultant equivalent.

4. Create ui/jansa/contractor_fiche_page.jsx exporting ContractorFichePage({contractor, onBack, focusMode}). Reads window.CONTRACTOR_FICHE_DATA. Reuses fiche_base.jsx primitives — do not invent new layout. Render header (emetteur_name + code + lots), KPIs (total_submitted, approval_rate, ref_rate, focus_owned), visa breakdown, lots card, documents drilldown, focus panel when focusMode. Handle loading + error states. Object.assign(window, { ContractorFichePage }).

5. ui/jansa/shell.jsx:
   • Add `selectedContractor` useState.
   • Add async `onOpenContractor(c)` handler — calls jansaBridge.loadContractorFiche then navigateTo('ContractorFiche').
   • Add route: {active === 'ContractorFiche' && <ContractorFichePage contractor={selectedContractor} onBack={() => navigateTo('Contractors')} focusMode={focusMode}/>}
   • Pass onOpenContractor to <OverviewPage> and <ContractorsPage>.

6. ui/jansa/overview.jsx:
   • OverviewPage accepts onOpenContractor.
   • KpiRow passes onOpenContractor and data.best_contractor to the Entreprise BestPerformerCard.
   • Replace `onClick={() => onNavigate('Contractors')}` with `onClick={() => onOpenContractor(data.best_contractor)}`.

7. ui/jansa/contractors.jsx:
   • ContractorsPage accepts onOpenContractor.
   • ContractorCard accepts onOpen prop; root div uses cursor:'pointer' and onClick={() => onOpen(c)}.
   • ContractorChip remains non-clickable (low-doc fallback). Add a brief code comment explaining why.

8. ui/jansa-connected.html: add <script type="text/babel" data-presets="react" src="ui/jansa/contractor_fiche_page.jsx"></script> next to existing JSX script tags.

Validation (must pass before reporting done):
- python -m py_compile app.py
- python -c "from app import Api; api = Api(); api._cache_ready.wait(); print(api.get_contractor_fiche_for_ui('BEN'))" → returns dict with header/kpis/etc., no error
- python app.py launches
- Click "Entreprise de la semaine" → fiche renders for that contractor (e.g. Bentin), header shows canonical name
- Click any enriched ContractorCard → fiche renders
- ContractorChip (plain fallback) does not navigate
- "Back" returns to Contractors list
- Visa/KPI numbers in fiche match the card preview
- Focus mode toggle reveals focus panel in fiche
- No console errors
- Phase 1–6 functionality intact (consultant fiche still works, dashboard drilldowns work, Intelligence tab still loads, BEN/Bentin everywhere)

Report back:
- get_contractor_fiche actual signature and return shape (top-level keys)
- Diff of all modified files + new file
- Sample fiche payload for code='BEN'
- Confirmation that all validation steps passed
- Any deviations and why

Hard rules:
- Backend stays source of truth — UI does not recompute KPIs.
- REUSE consultant fiche structure brutally. Take fiche_page.jsx as a starting copy, rename Consultant → Contractor, swap the field reads, and stop. NO new layout, NO new section types, NO new design tokens, NO new visual language.
- Reuse fiche_base.jsx primitives. Do not fork layout. If a primitive doesn't perfectly fit, pass a conceptually-equivalent value and use the primitive verbatim — do not redesign.
- Match the consultant fiche pattern; do not invent new patterns.
- Treat contractor_fiche.py as read-only business logic.
- Stop and escalate if the backend builder is a stub.
```

---

## 10. Context Update (after merge)

- `context/03_UI_FEED_MAP.md` — record the new `ContractorFiche` route, `loadContractorFiche` bridge method, `get_contractor_fiche_for_ui` endpoint.
- `context/01_RUNTIME_MAP.md` — note the `ContractorFiche` route is mounted in shell.jsx.
- `context/07_OPEN_ITEMS.md` — close the README open item: "`get_contractor_fiche` is not wired".
- `README.md` §Contractors Page — remove or update the line "fiche drill-down not yet wired" to reflect the new state.

If `context/` is missing the file, skip — do not create new context files in this phase.

---

## 11. Done Definition

- App launches cleanly.
- Backend builder confirmed real and returning structured data.
- Clicking "Entreprise de la semaine" or any enriched ContractorCard opens a working fiche.
- Fiche renders header, KPIs, visa breakdown, documents drilldown, lots card, focus panel.
- Plain `ContractorChip` items remain non-clickable.
- Phase 1–6 unaffected.
- Diff scoped to: `app.py`, `ui/jansa/data_bridge.js`, `ui/jansa/shell.jsx`, `ui/jansa/overview.jsx`, `ui/jansa/contractors.jsx`, `ui/jansa/contractor_fiche_page.jsx` (new), `ui/jansa-connected.html`. (`src/reporting/contractor_fiche.py` only if a thin shim absolutely had to be added.)
