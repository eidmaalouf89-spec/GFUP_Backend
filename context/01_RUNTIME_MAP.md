# 01 — Runtime Map

> Reconstructed from `app.py`, `main.py`, `run_chain_onion.py`,
> `src/run_orchestrator.py`, `src/pipeline/runner.py`, and the JANSA UI files.

## Two distinct runtimes share the same repo

```
┌──────────────────────────────┐    ┌─────────────────────────────┐
│ DESKTOP / UI RUNTIME          │    │ HEADLESS PIPELINE RUNTIME    │
│ entry: python app.py          │    │ entry: python main.py        │
│ shell: PyWebView (webview)    │    │ shell: shell / IDE           │
│ UI:    ui/jansa-connected.html│    │ UI:    none                  │
└──────────────────────────────┘    └─────────────────────────────┘
                │                                  │
                └──────────────┬───────────────────┘
                               ▼
            src/run_orchestrator.run_pipeline_controlled(...)
                               │
                               ▼
                    src/pipeline/runner._run_pipeline_impl
                               │
                               ▼
              eleven src/pipeline/stages/* in order
```

A third runtime exists for the analytical layer:

```
┌──────────────────────────────┐
│ CHAIN + ONION RUNTIME         │   entry: python run_chain_onion.py
│ Reads: output/intermediate/  │   (independent of main pipeline run)
│        FLAT_GED.xlsx +        │
│        DEBUG_TRACE.csv        │
│        data/report_memory.db  │
│ Writes: output/chain_onion/* │
└──────────────────────────────┘
```

---

## A. Desktop / UI startup chain

File: `app.py` (top-level).

```
python app.py
  └─ app.main()
       ├─ _resolve_base_dir()                # PyInstaller-aware
       ├─ sys.path.insert(0, BASE_DIR/"src")  # so bare imports work
       ├─ _resolve_ui()                       # only ui/jansa-connected.html accepted
       ├─ Api.__init__()
       │    ├─ self._cache_ready        = threading.Event()
       │    ├─ self._chain_data_ready   = threading.Event()   # Phase 3
       │    └─ threading.Thread(_prewarm_cache, daemon=True)
       │         ├─ reporting.data_loader.load_run_context(BASE_DIR)
       │         ├─ self._cache_ready.set()                   # UI unblocks here
       │         ├─ _ensure_chain_data_fresh(ctx, BASE_DIR)   # Phase 3
       │         │    ├─ if chain_onion stale → subprocess run_chain_onion.py
       │         │    │    (treated as success if all 3 required CSVs were written
       │         │    │     even when exit code ≠ 0 — D19 harness quirk)
       │         │    └─ chain_timeline_attribution refresh →
       │         │       output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.{json,csv}
       │         └─ self._chain_data_ready.set()
       └─ webview.create_window(title="JANSA VISASIST — P17&CO T2",
                                url=ui_url,
                                js_api=api,
                                width=1400, height=900)
            └─ webview.start(debug="--debug" in sys.argv)
                 # → on failure: falls back to webbrowser.open(ui_url)
```

Browser-mode flag: `python app.py --browser` → opens the same HTML in the
default browser via `webbrowser.open()`. No pywebview bridge is available in
this mode. `data_bridge.js:waitForApi(5000)` times out and the UI falls back
to `_placeholderOverview()` / `_placeholderConsultants()`. This mode is
**read-only placeholder data only** — no backend calls succeed. Useful for
CSS/layout development but does NOT show real project data.

### What MUST exist for the UI to load (functional requirements)

| Requirement | File / location |
|---|---|
| Production HTML present | `ui/jansa-connected.html` |
| JANSA JSX components present | `ui/jansa/*.jsx` (loaded via `<script type="text/babel">`) |
| `data_bridge.js` present | `ui/jansa/data_bridge.js` |
| `tokens.js` present | `ui/jansa/tokens.js` (defines `window.JANSA_FONTS`, `window.applyJansaTheme`) |
| Babel + React from CDN reachable at boot | `https://unpkg.com/react@18`, `https://unpkg.com/@babel/standalone@7` |
| `data/run_memory.db` exists | for `get_app_state()` / `get_all_runs()` |

### What is NOT required for the UI to render

- A registered run. If `run_memory.db` exists but has no completed run,
  `get_app_state()` returns `has_baseline=False` with a warning, and the UI
  still renders.
- `data/report_memory.db`. Optional; consumed only by the pipeline and the
  Chain+Onion runner.
- `output/chain_onion/*`. If absent, `app._build_live_operational_numeros()`
  returns `(None, 0)` and Focus mode falls back to the unfiltered ownership
  set.

---

## B. Pipeline (controlled) execution path

Entry: any of three callers ends up here.

```
caller A: app.py Api.run_pipeline_async (UI Executer)
caller B: main.py __main__ (headless)
caller C: direct import in tests / scripts
        ↓
src/run_orchestrator.run_pipeline_controlled(run_mode, ged_path, gf_path?, reports_dir?)
        ↓
   validate_run_inputs()                     # validates xlsx existence + mode
        ↓
   _resolve_inherited_gf_record() if gf_path is None
        ↓
   _build_execution_context()
        ↓
   (unless GFUP_FORCE_RAW=1):
     src/flat_ged_runner.build_flat_ged_artifacts(ged_path, intermediate_dir)
       └─ src/flat_ged.build_flat_ged(ged_xlsx_path, output_dir, mode="batch")
            └─ src/flat_ged/cli.run_batch(...)   # frozen builder
       returns {flat_ged_path, debug_trace_path, run_report_path, ...}
        ↓
   _patched_main_context(main_module, execution_context):
     # mutates main_module.GED_FILE / GF_FILE / CONSULTANT_REPORTS_ROOT etc.
     main_module.FLAT_GED_FILE = flat_ged_path
     main_module.FLAT_GED_MODE = "flat"
        ↓
     main_module.run_pipeline(verbose=True)
        └─ pipeline.runner._run_pipeline_impl(sys.modules["main"], verbose=True)
             ↓
          PipelineState ctx = ...               # copy of main_module path constants
          stage_init_run(ctx, log)              # creates run_N row in run_memory.db
          stage_read_flat(ctx, log)  | stage_read(ctx, log)   # mode == "flat" / "raw"
          stage_normalize(ctx, log)
          stage_version(ctx, log)
          stage_route(ctx, log)
          stage_report_memory(ctx, log)
          stage_write_gf(ctx, log)              # GF_V0_CLEAN.xlsx
          stage_build_team_version(ctx, log)    # GF_TEAM_VERSION.xlsx
          stage_discrepancy(ctx, log)           # incl. Part H-1 BENTIN exception
          stage_diagnosis(ctx, log)             # missing/insert/new-submittal/debug
          stage_finalize_run(ctx, log)          # registers all artifacts to run_memory.db
        ↓
   _register_flat_ged_artifacts(...)           # FLAT_GED + DEBUG_TRACE + RUN_REPORT
   export_final_gf(db_path, run_number)         # locates registered FINAL_GF
   returns {success, run_number, status, errors, warnings, outputs, ...}
```

Run modes (`_VALID_RUN_MODES` in `run_orchestrator.py`):
`GED_ONLY`, `GED_GF`, `GED_REPORT`, `FULL`. UI exposes the first three;
`main.py __main__` uses `RUN_MODE_FULL`.

### Important nuance: main.py's mutable globals

`main.py` does `from pipeline.paths import *` AND defines mutable globals
(`_ACTIVE_RUN_NUMBER`, `_ACTIVE_RUN_FINALIZED`, `_RUN_CONTROL_CONTEXT`).
`run_orchestrator._patched_main_context` writes to those constants on the
main module namespace and `pipeline.runner._run_pipeline_impl` reads from
that namespace via `ns = sys.modules["main"]`. **Do not change this
indirection without understanding why** — comments explicitly call out that
paths must be read from main, not from `pipeline.paths`, because the
orchestrator mutates them at runtime.

---

## C. The PyWebView Api surface (window.pywebview.api.*)

All public methods on `app.Api`, sorted by feature area. Every JS call
returns a JSON-serialisable dict (sanitised through `_sanitize_for_json`).

### App state / runs

| JS call | Purpose | Backing module |
|---|---|---|
| `get_app_state()` | baseline status, latest run, detected GED/GF in `input/` | direct sqlite read of `run_memory.db` |
| `get_all_runs()` | run history with status flags | `src.run_explorer.get_all_runs` |
| `get_run_summary(n)` | one run's metadata | `src.run_explorer.get_run_summary` |
| `compare_runs(a, b)` | diff between two runs | `src.run_explorer.compare_runs` |
| `export_run_bundle(n)` | ZIP all artifacts of run N | `src.run_explorer.export_run_bundle` |

### Pipeline control

| JS call | Purpose | Backing |
|---|---|---|
| `validate_inputs(run_mode, ged, gf, reports_dir)` | pre-flight | `run_orchestrator.validate_run_inputs` |
| `run_pipeline_async(run_mode, ged, gf, reports_dir)` | launch in worker thread | `run_orchestrator.run_pipeline_controlled` |
| `get_pipeline_status()` | poll progress (running/message/error/completed_run) | internal status dict |
| `select_file(file_type)` | native open dialog | `webview.create_file_dialog` |

### Reporting (UI feeds)

| JS call | Purpose | Backing |
|---|---|---|
| `get_dashboard_data(focus, stale_days)` | KPIs + monthly + consultants + contractors + focus | `reporting.aggregator.compute_*` + `reporting.focus_filter` + chain_onion narrowing |
| `get_consultant_list(focus, stale_days)` | list of consultants with KPIs | `reporting.aggregator.compute_consultant_summary` |
| `get_contractor_list(focus, stale_days)` | list of contractors with KPIs | `reporting.aggregator.compute_contractor_summary` |
| `get_consultant_fiche(name, focus, stale_days)` | one consultant fiche | `reporting.consultant_fiche.build_consultant_fiche` |
| `get_contractor_fiche(code, focus, stale_days)` | one contractor fiche | `reporting.contractor_fiche.build_contractor_fiche` |
| `get_doc_details(name, filter_key, lot, focus, stale_days)` | drilldown rows for a fiche cell | `reporting.consultant_fiche._filter_for_consultant` + `_attach_derived` |
| `export_drilldown_xlsx(...)` | xlsx of drilldown | inline openpyxl |

### UI-shaped wrappers (called by `data_bridge.js`)

| JS call | Backing |
|---|---|
| `get_overview_for_ui(focus, stale_days)` | calls `get_dashboard_data` + `get_app_state` then `reporting.ui_adapter.adapt_overview` |
| `get_consultants_for_ui(focus, stale_days)` | `reporting.ui_adapter.adapt_consultants` |
| `get_contractors_for_ui(focus, stale_days)` | `reporting.ui_adapter.adapt_contractors_lookup` + `adapt_contractors_list` (populates `window.CONTRACTORS` + `window.CONTRACTORS_LIST`) |
| `get_fiche_for_ui(name, focus, stale_days)` | thin alias for `get_consultant_fiche` |
| `get_contractor_fiche_for_ui(code, focus, stale_days)` | one contractor fiche payload; opens the `ContractorFiche` route in `ui/jansa/contractor_fiche_page.jsx` | `reporting.contractor_fiche.build_contractor_fiche` + `reporting.contractor_quality.build_contractor_quality` |

### Document Command Center

| JS call | Purpose | Backing |
|---|---|---|
| `search_documents(query, focus, stale_days, limit)` | Full-text search over `dernier_df` (numero, titre, emetteur, lot, indice) | `reporting.document_command_center.search_documents` |
| `get_document_command_center(numero, indice, focus, stale_days)` | Full panel payload for one document (header, responses, comments, revision_history, chronologie, tags) | `reporting.document_command_center.build_document_command_center` |
| `get_chain_timeline(numero)` | Per-chain timeline with delay attribution; blocks on `_chain_data_ready` | `reporting.chain_timeline_attribution.load_chain_timeline_artifact` (reads `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json`) |

> Note: `get_document_command_center` already embeds the `chronologie` field by
> calling `load_chain_timeline_artifact` internally. `get_chain_timeline` is the
> standalone API endpoint; in practice the panel consumes it via `get_document_command_center`.

### Misc

| JS call | Purpose | Backing |
|---|---|---|
| `export_team_version()` | copy `GF_TEAM_VERSION.xlsx` → `output/Tableau de suivi de visa DD_MM_YYYY.xlsx` | `data_loader.load_run_context` + shutil.copy2 |
| `open_file_in_explorer(path)` | Windows Explorer reveal | `subprocess.Popen("explorer /select,...")` |

---

## D. Boot-time invariants enforced by code

| Invariant | Where |
|---|---|
| Only `ui/jansa-connected.html` is accepted as production UI | `app._resolve_ui()` raises `FileNotFoundError` otherwise |
| `data/`, `output/`, `output/intermediate/`, `output/debug/` exist | `main.py` calls `OUTPUT_DIR.mkdir(...)` etc. |
| Default flat mode is `"raw"` in `paths.py`, but orchestrator overrides to `"flat"` | `pipeline.paths.FLAT_GED_MODE = "raw"` + `run_orchestrator` patch |
| All sqlite reads retry on lock and fall back to immutable mode | `_query_db` in both `app.py` and `data_loader.py` |
| `data_bridge.js` waits up to 5s for `window.pywebview.api`, then degrades | `data_bridge.js:waitForApi(5000)` |
| Cache pre-warm runs in a daemon thread on Api init | `Api.__init__` → `_prewarm_cache` |

---

## E. Quick trace: "what runs when I click 'Lancer le pipeline'?"

1. `executer.jsx:handleLaunch()` → `api.run_pipeline_async(runMode, gedPath, gfPath, reportsDir)`.
2. `app.Api.run_pipeline_async` validates via `run_orchestrator.validate_run_inputs`,
   sets `_pipeline_status.running=True`, spawns a worker thread.
3. Worker calls `run_orchestrator.run_pipeline_controlled(...)`.
4. Unless `GFUP_FORCE_RAW=1`, the orchestrator builds Flat GED first
   (`flat_ged_runner.build_flat_ged_artifacts`).
5. `_patched_main_context` mutates `main` module path globals.
6. `main.run_pipeline(verbose=True)` → `pipeline.runner._run_pipeline_impl` →
   eleven stages.
7. `stage_finalize_run` writes the run row, registers every artifact to
   `data/run_memory.db`, and returns the result dict.
8. Orchestrator registers FLAT_GED artifacts and returns to the worker.
9. Worker mutates `_pipeline_status` (`running=False`, `completed_run=N`).
10. UI's polling loop (`get_pipeline_status` every 600 ms) sees `running=False`,
    calls `onRunComplete()` which calls `jansaBridge.refreshForFocus()` to
    re-fetch overview/consultants/contractors with the new artifacts.

This is the single execution path the UI exercises. Everything else
(dashboard data, fiches, exports) is read-only over registered artifacts.
