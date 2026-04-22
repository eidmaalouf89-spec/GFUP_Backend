# JANSA Dashboard Integration Notes
**Date**: 2026-04-22
**Status**: First connected version — data bridge in place

---

## What Was Done

### Architecture
The standalone JANSA dashboard prototype (`JANSA Dashboard - Standalone.html`) was converted into a connected UI that calls the existing PyWebView backend API. The approach:

1. **Prototype source files** (from `codex prompts/facelift/prototype/jansa/`) were copied to `ui/jansa/` — visual components are **unchanged**.
2. **`data.js`** (static mock data) was **replaced** by `data_bridge.js` — an async bridge that calls `window.pywebview.api.*` methods.
3. **`shell.jsx`** was minimally modified: the `App()` function now waits for data to load before rendering, reloads on focus toggle, and loads per-consultant fiche data dynamically.
4. **`fiche_page.jsx`** was modified to handle missing/error fiche data gracefully.
5. **`ui/jansa-connected.html`** — new entry point that loads React+Babel from CDN and mounts the JANSA components.

### Backend Changes
- **`src/reporting/ui_adapter.py`** (NEW) — pure adapter that transforms `aggregator.py` / `consultant_fiche.py` output into the shapes expected by the JANSA UI (`window.OVERVIEW`, `window.CONSULTANTS`, etc.).
- **`app.py`** — added 4 new API methods:
  - `get_overview_for_ui(focus)` → OVERVIEW payload
  - `get_consultants_for_ui(focus)` → CONSULTANTS list
  - `get_contractors_for_ui(focus)` → CONTRACTORS lookup + list
  - `get_fiche_for_ui(consultant_name, focus)` → FICHE_DATA (pass-through)
- **`app.py`** — `_resolve_ui()` now prefers `ui/jansa-connected.html` over `ui/dist/index.html`.
- **`app.py`** — fixed truncated `main()` function (was cut off at line 774).

### Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `ui/jansa-connected.html` | Created | Connected dashboard entry point |
| `ui/jansa/data_bridge.js` | Created | Async data loader (replaces mock data.js) |
| `ui/jansa/shell.jsx` | Modified | App root with data loading lifecycle |
| `ui/jansa/fiche_page.jsx` | Modified | Error handling for dynamic fiche load |
| `ui/jansa/tokens.js` | Copied | Design tokens (unchanged) |
| `ui/jansa/overview.jsx` | Copied | Overview page (unchanged) |
| `ui/jansa/consultants.jsx` | Copied | Consultants page (unchanged) |
| `ui/jansa/fiche_base.jsx` | Copied | Consultant fiche component (unchanged) |
| `src/reporting/ui_adapter.py` | Created | Backend → UI data shape adapter |
| `app.py` | Modified | New UI API methods + fixed main() + UI resolution |

---

## What Is Connected (Working)

| UI Element | Data Source | Status |
|------------|------------|--------|
| Overview total docs | `aggregator.compute_project_kpis()` → `total_docs_current` | ✅ Connected |
| Overview run number | `get_app_state()` → `current_run` | ✅ Connected |
| Overview visa flow (VSO/VAO/REF/Open) | `by_visa_global` | ✅ Connected |
| Overview refus rate | Computed from `by_visa_global` | ✅ Connected |
| Overview best consultant | Highest approval rate from `consultant_summary` | ✅ Connected |
| Overview best contractor | Highest approval rate from `contractor_summary` | ✅ Connected |
| Overview weekly/monthly chart | `compute_monthly_timeseries()` or `compute_weekly_timeseries()` | ✅ Connected |
| Consultants list | `compute_consultant_summary()` → adapted with groups/roles | ✅ Connected |
| Consultant fiche (all blocks) | `build_consultant_fiche()` — already matching shape | ✅ Connected |
| Sidebar badges (runs, consultants, contractors) | Dynamic from loaded data | ✅ Connected |
| Sidebar project pill (run number) | From OVERVIEW data | ✅ Connected |
| Focus mode toggle | Triggers data reload with `focus=True` | ✅ Connected |
| Focus stats in topbar | From `focus_result.stats` | ✅ Connected |
| Theme toggle (dark/light) | localStorage persistence | ✅ Connected |

---

## What Lacks Data (Shown as null / Not yet connected)

| UI Field | Reason | Fix Required |
|----------|--------|-------------|
| `total_docs_delta` | Requires comparing current run with previous run | Add run diff to `ui_adapter` |
| `pending_blocking_delta` | Same — run-to-run comparison | Add run diff |
| `refus_rate_delta` | Same | Add run diff |
| `best_consultant.delta` | Same | Add run diff |
| `best_contractor.delta` | Same | Add run diff |
| `visa_flow.on_time` / `.late` | Backend `aggregator` doesn't compute on-time/late split for all open docs | Add deadline check in aggregator |
| `consultant.trend[]` (sparkline) | Requires historical run data (8-week series) | Store KPIs per run in run_memory.db |
| Focus `by_consultant` breakdown | Focus stats exist but structured differently than UI expects | Map `focus_result.stats` fields |

---

## What Remains Unsupported (Stub Pages)

These pages render a placeholder message — no backend wiring attempted:

- **Executer** — Pipeline execution (has backend support, not wired to JANSA UI)
- **Runs** — Run history explorer (has backend support, not wired)
- **Contractors** — Contractor fiche page (has backend support, not wired)
- **Discrepancies** — Gap analysis
- **Reports** — Export/deliverables
- **Settings** — Preferences

---

## How to Run

```bash
# From the project root:
python app.py          # Opens PyWebView with connected dashboard
python app.py --debug  # Same, with DevTools enabled
python app.py --browser  # Opens in default browser (no pywebview API — preview mode)
```

When opened without PyWebView (e.g., directly in a browser), the dashboard shows placeholder data and a "Backend not connected" warning.

---

## Known Limitations

1. **Babel in-browser**: The connected HTML uses `@babel/standalone` for JSX compilation. This adds ~200ms startup time. For production, the prototype should be pre-compiled (Vite build or custom bundler).
2. **CDN dependency**: React and Babel are loaded from unpkg.com. For offline/air-gapped use, bundle these locally.
3. **No incremental update**: When focus mode toggles, the entire dataset is reloaded. This is fast enough for the current data size but could be optimized.
4. **Consultant name resolution**: The bridge passes `consultant.canonical_name` (added by `adapt_consultants`) to the fiche API. If this field is missing, it falls back to `consultant.name`, which may not resolve correctly for display names that differ from canonical.
