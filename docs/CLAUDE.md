# CLAUDE.md

Claude is used for repo understanding, scoped planning, implementation, refactoring, and documentation support. Claude is not the source of truth; the source of truth is the current code, current docs, and validated outputs.

## Read First

Before important work, read:

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/UI_RUNTIME_ARCHITECTURE.md`
4. `docs/VALIDATION_BASELINE.md`
5. `docs/DEVELOPMENT_RULES.md`
6. `docs/JANSA_FINAL_AUDIT.md`

For UI parity work, also read the relevant `docs/JANSA_PARITY_STEP_*.md` file.

## Current Repo Truth

This repo is still a deterministic GED -> GF reconstruction engine. It now also has a real production desktop UI runtime: JANSA connected UI.

Entrypoints:

- `main.py` runs the backend pipeline.
- `app.py` launches the JANSA desktop app.
- `ui/jansa-connected.html` is the single production UI entrypoint.

Old Vite/legacy UI files are reference only. Do not revive dual-UI behavior.

## Current Validated UI Scope

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

Contractors are intentionally deferred for redesign. Do not treat contractor gaps as accidental regressions unless a task explicitly targets contractors.

`docs/JANSA_FINAL_AUDIT.md` is the current truth sheet before push/review. Do not overclaim 100% parity.

## Backend Mental Model

Preserve these rules:

- GED is primary operational truth.
- `report_memory.db` is persistent secondary consultant truth.
- GF is reconstructed/enriched output.
- `run_memory.db` tracks runs, artifacts, lineage, baseline, and stale propagation.
- Pipeline execution belongs through `src/run_orchestrator.py` and staged pipeline files.

## Layer Routing

Backend/pipeline work:

- `main.py`
- `src/run_orchestrator.py`
- `src/pipeline/`
- `src/domain/`
- `src/run_memory.py`
- `src/report_memory.py`
- writer/reconciliation/version/workflow modules

JANSA runtime work:

- `app.py`
- `src/reporting/`
- `ui/jansa-connected.html`
- `ui/jansa/`
- `docs/UI_RUNTIME_ARCHITECTURE.md`
- `docs/JANSA_FINAL_AUDIT.md`

Legacy/reference UI:

- `ui/src/`
- `ui/index.html`
- `ui/dist/`

Do not add production behavior to legacy/reference UI unless the runtime architecture is explicitly changed.

## Working Rules

Never:

- treat GF as primary truth
- delete `report_memory.db` casually
- bypass `run_orchestrator.py`
- change stage order casually
- silently change output or artifact contracts
- reintroduce UI runtime fallback behavior
- broaden a scoped task into redesign

Always:

- identify the layer first
- make minimal deterministic changes
- preserve existing validated behavior
- validate the correct layer
- update docs when runtime or architecture truth changes

## Validation

Backend/pipeline changes require pipeline validation against `docs/VALIDATION_BASELINE.md`.

UI/runtime changes require JANSA validation against `docs/UI_RUNTIME_ARCHITECTURE.md`, relevant parity step docs, and `docs/JANSA_FINAL_AUDIT.md`.

These are separate validation layers. Passing one does not prove the other.
