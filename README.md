# GF Updater v3

Deterministic GED -> GF reconstruction, enrichment, discrepancy analysis, run tracking, and JANSA desktop operations UI for the **17&CO Tranche 2** workflow.

This repository is not a generic Excel updater. It is a single-project operational engine that rebuilds a clean and traceable Grand Fichier from unstable chantier inputs while preserving consultant truth, run history, lineage, and artifacts across executions.

## Current State Snapshot

**Backend status:** architecturally stabilized staged pipeline. `main.py` remains the pipeline entrypoint, `src/run_orchestrator.py` controls execution, and the Run 0 validation baseline remains the backend regression reference.

**Production UI status:** `app.py` launches the JANSA connected desktop UI. The single production UI entrypoint is `ui/jansa-connected.html`; old Vite UI files are legacy/reference only.

**Validated JANSA scope:** Focus mode, Overview, Consultants list, Consultant fiche, Drilldowns, Drilldown exports, Runs page, Executer page, Utilities, stale-days selector, and reports export.

**Deferred scope:** contractors are intentionally deferred for redesign. Do not treat contractor parity gaps as accidental regressions unless a task explicitly targets that area.

**Authoritative docs today:**

- `docs/ARCHITECTURE.md`
- `docs/UI_RUNTIME_ARCHITECTURE.md`
- `docs/VALIDATION_BASELINE.md`
- `docs/DEVELOPMENT_RULES.md`
- `docs/JANSA_FINAL_AUDIT.md`
- relevant `docs/JANSA_PARITY_STEP_*.md` files

Treat `docs/JANSA_FINAL_AUDIT.md` as the current truth sheet before push/review. Do not overclaim 100% parity.

## What This Repository Is

GF Updater v3 is a local, single-user, single-project operational system that:

- reads a raw GED export
- reconstructs document identity and workflow state
- rebuilds a clean Grand Fichier
- compares GED and GF to detect discrepancies
- persists consultant-report truth across runs
- persists run history, artifacts, lineage, baseline state, and stale propagation
- exposes operational workflows through the JANSA desktop UI

It is intentionally:

- single project: **17&CO Tranche 2**
- local / single-user
- not SaaS
- not multi-tenant
- not a generic multi-project framework

## Source-Of-Truth Model

GED is the primary operational truth for document identity, workflow rows, mission calling, and lifecycle structure.

Consultant reports are persistent secondary truth. Once matched and persisted in `report_memory.db`, consultant answers can be reused in future runs even if the report file is not re-imported.

GF is a reconstruction target. It is rebuilt and enriched from GED, report memory, routing, and workflow logic; it is not the source of truth.

`run_memory.db` is the lineage system for runs, inputs, artifacts, baseline/current state, corrections, and stale propagation.

## Runtime Entrypoints

Pipeline:

```bash
python main.py
```

Desktop app:

```bash
python app.py
```

`python app.py` resolves exactly one production UI path:

```text
ui/jansa-connected.html
```

There is no production fallback to `ui/dist/index.html` or a Vite dev server. See `docs/UI_RUNTIME_ARCHITECTURE.md`.

## Backend Architecture

```text
main.py
  -> src/run_orchestrator.py
  -> src/pipeline/stages/*
  -> output/
  -> runs/
  -> data/run_memory.db
  -> data/report_memory.db
```

Pipeline stage order:

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

Important modules:

- `src/run_orchestrator.py` - controlled execution, modes, inherited GF resolution
- `src/pipeline/context.py` - shared `PipelineState`
- `src/pipeline/stages/` - ordered execution stages
- `src/domain/` - deterministic business helpers
- `src/run_memory.py` - run history and artifacts
- `src/report_memory.py` - persisted consultant truth
- `src/reporting/` - JANSA/reporting data adapters and fiche builders

## JANSA UI Architecture

Production UI flow:

```text
backend reporting data
  -> src/reporting/* adapters
  -> app.py pywebview API methods
  -> ui/jansa/data_bridge.js
  -> ui/jansa/*.jsx
  -> ui/jansa-connected.html
```

Validated JANSA areas:

- Focus mode
- Overview
- Consultants list
- Consultant fiche
- Drilldowns
- Drilldown exports
- Runs page
- Executer page
- Utilities / stale-days selector / reports export

Old Vite UI files under `ui/src/`, `ui/index.html`, and generated `ui/dist/` output are archival/reference only. Do not add new production behavior there unless the runtime architecture is explicitly changed.

## Execution Modes

Supported orchestrated modes:

- `GED_ONLY` - user provides GED; GF is inherited from latest valid completed run or Run 0
- `GED_GF` - user provides GED + GF
- `GED_REPORT` - user provides GED + reports; GF is inherited
- `FULL` - GED + reports + GF, directly or inherited when resolvable

Not supported:

- `REPORT_ONLY` - consultant matching depends on a GED-derived document/workflow universe

If the user does not provide a GF, inherited GF resolution is:

1. latest completed non-stale run with a valid `FINAL_GF` artifact
2. Run 0 `FINAL_GF`
3. clear failure if no usable GF exists

## Inputs

Typical inputs:

- `input/GED_export.xlsx`
- `input/Grandfichier_v3.xlsx`
- consultant report PDFs
- `data/report_memory.db`
- `data/run_memory.db`

Do not delete `data/report_memory.db` casually. It is persistent project memory.

## Outputs And Artifacts

Outputs live under `output/` and are mirrored into `runs/run_NNNN/`.

Core artifacts include:

- `GF_V0_CLEAN.xlsx`
- `GF_TEAM_VERSION.xlsx`
- `DISCREPANCY_REPORT.xlsx`
- `DISCREPANCY_REVIEW_REQUIRED.xlsx`
- `ANOMALY_REPORT.xlsx`
- `AUTO_RESOLUTION_LOG.xlsx`
- `IGNORED_ITEMS_LOG.xlsx`
- `INSERT_LOG.xlsx`
- `RECONCILIATION_LOG.xlsx`
- diagnosis and new-submittal reports
- run/report memory snapshots
- debug artifacts

The JANSA UI exposes **Tableau de Suivi VISA** export from Overview, consultant fiche pages, and Reports. It copies the registered run artifact to:

```text
output/Tableau de suivi de visa DD_MM_YYYY.xlsx
```

## Validation

Backend validation and UI validation are different layers.

Backend/pipeline changes must validate against `docs/VALIDATION_BASELINE.md`.

Current Run 0 baseline: fresh post-reset FULL run created on 2026-04-22 from `input/`, with `report_memory.db` rebuilt from `input/consultant_reports`.

| Metric | Value |
|---|---:|
| `docs_total` | 6491 |
| `responses_total` | 545244 |
| `final_gf_rows` | 4728 |
| `discrepancies_count` | 3221 |
| `discrepancies_review_required` | 18 |
| `reconciliation_events` | 172 |
| `artifacts_registered_count` | 30 |
| `consultant_report_memory_rows_loaded` | 1245 |

JANSA UI/runtime changes must validate against:

- `docs/UI_RUNTIME_ARCHITECTURE.md`
- relevant `docs/JANSA_PARITY_STEP_*.md`
- `docs/JANSA_FINAL_AUDIT.md`

Passing old Vite build/lint checks does not prove JANSA runtime behavior. Old Vite-only issues are not production blockers unless they affect JANSA runtime.

## Known Deferred / Non-Blocking Areas

- Contractors are intentionally deferred for redesign.
- Discrepancies and Settings are not full operational workflows in the current JANSA scope.
- Some audit items remain documented in `docs/JANSA_FINAL_AUDIT.md`.
- Excel file hashes are not stable proof of correctness; use metrics and artifact registration instead.

## Working Rules

Never:

- treat GF as primary truth
- overwrite GED raw data
- delete `report_memory.db` casually
- bypass `run_orchestrator.py`
- change stage order casually
- silently change output filenames or artifact contracts
- reintroduce dual-UI runtime selection

Always:

- preserve deterministic behavior
- preserve traceability
- respect Run 0 as baseline
- keep backend and JANSA validation layers distinct
- prefer scoped changes over broad rewrites
- update docs when runtime, architecture, or validation truth changes

## Documentation Map

- `docs/ARCHITECTURE.md` - current backend and JANSA architecture
- `docs/UI_RUNTIME_ARCHITECTURE.md` - single production UI runtime policy
- `docs/VALIDATION_BASELINE.md` - pipeline regression baseline
- `docs/DEVELOPMENT_RULES.md` - scoped development and validation discipline
- `docs/JANSA_FINAL_AUDIT.md` - current UI parity/release truth sheet
- `docs/JANSA_PARITY_MASTER_PLAN.md` - JANSA parity execution plan
- `docs/JANSA_PARITY_STEP_*.md` - step-level validation records
- `docs/CLAUDE.md` - Claude working context
- `docs/CODEX.md` - Codex review context

## Mental Model

This codebase is:

> A deterministic reconstruction and enrichment engine with persistent project memory, validated staged execution, and a production JANSA desktop UI runtime.

It is not just an Excel updater, report parser, reconciliation script, or temporary chantier utility.
