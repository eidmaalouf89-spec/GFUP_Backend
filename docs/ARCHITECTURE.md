# ARCHITECTURE

GF Updater v3 is a deterministic GED -> GF reconstruction engine with a production JANSA desktop UI runtime.

The backend remains the source of truth. The JANSA UI is the operational presentation layer over backend adapters and pywebview bridge methods.

## Runtime Entrypoints

- `main.py` -> pipeline entrypoint
- `app.py` -> desktop JANSA launcher
- `ui/jansa-connected.html` -> single production UI entrypoint

The old Vite UI under `ui/src/`, `ui/index.html`, and `ui/dist/` is legacy/reference only. It is not a production runtime target.

## Backend Pipeline

Execution path:

```text
main.py
  -> src/run_orchestrator.py
  -> src/pipeline/stages/*
  -> run memory / report memory / artifacts
```

Stage order:

1. `stage_init_run`
2. `stage_read`
3. `stage_normalize`
4. `stage_version`
5. `stage_route`
6. `stage_report_memory`
7. `stage_write_gf`
8. `stage_discrepancy`
9. `stage_diagnosis`
10. `stage_finalize_run`

## Source Of Truth Rules

- GED = primary operational truth
- `report_memory.db` = persistent secondary consultant truth
- GF = reconstructed/enriched output, not primary truth
- `run_memory.db` = lineage, artifacts, baseline, current-run state

Do not bypass `run_orchestrator.py` or the staged pipeline for production behavior.

## Current UI Architecture

JANSA runtime model:

```text
backend reporting data
  -> src/reporting/* adapters
  -> app.py pywebview API methods
  -> ui/jansa/data_bridge.js
  -> ui/jansa/*.jsx
  -> ui/jansa-connected.html
```

Implemented and validated JANSA areas:

- Focus mode
- Overview
- Consultants list
- Consultant fiche
- Drilldowns
- Drilldown exports
- Runs page
- Executer page
- Utilities, stale-days selector, reports export

Contractors are intentionally deferred for redesign and are outside the current validated scope.

## Review Surface

For backend changes, review the staged pipeline, domain helpers, persistence, and artifact contracts.

For UI/runtime changes, review:

- `app.py`
- `src/reporting/`
- `ui/jansa-connected.html`
- `ui/jansa/`
- `docs/UI_RUNTIME_ARCHITECTURE.md`
- `docs/JANSA_FINAL_AUDIT.md`

Do not revive dual-UI runtime assumptions.
