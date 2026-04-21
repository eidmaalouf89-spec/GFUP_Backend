# GF Updater v3

Deterministic GED → GF reconstruction, enrichment, discrepancy analysis, and run-tracked baseline engine for the **17&CO Tranche 2** workflow.

This repository is not a simple Excel updater or ETL script. It is a deterministic operational engine that rebuilds a clean and traceable Grand Fichier (GF) from unstable chantier inputs while preserving consultant truth, run history, lineage, and artifacts across executions.

---

## 1. What this repository is

GF Updater v3 is a single-project, single-team, local operational engine that:

- reads a raw GED export
- reconstructs document truth and workflow state
- rebuilds a clean Grand Fichier (GF)
- compares GED and GF to detect discrepancies
- persists consultant-report truth across runs
- persists run history, artifacts, lineage, and baseline state
- allows future runs to inherit trusted context from previous completed runs

It is intentionally:

- **single project** (17&CO Tranche 2)
- **single user / local usage**
- **currently not designed for multi-project usage**
- **currently not designed for SaaS / multi-tenant use**

---

## 2. Current validated state

The repository has been structurally stabilized and validated after a staged architecture refactor.

Current stable state:

- thin `main.py` entrypoint
- staged pipeline architecture with explicit `PipelineState`
- deterministic domain helpers extracted out of the old monolithic pipeline
- validated baseline reset completed successfully
- new clean **Run 0** recreated and confirmed equivalent to the historical baseline
- `report_memory.db` preserved and still contains 1242 persisted consultant responses
- input signature of new Run 0 matches original baseline exactly

This repository should now be treated as:

> **architecturally stabilized, behaviorally validated, and safe for scoped future development**

UI/reporting remains partially unfinished and should still be considered evolving.

---

## 3. Scope and intended usage

This system is designed to solve one specific operational workflow:

- project: **17&CO Tranche 2**
- document universe: GED export + GF + consultant reports (118 PDFs)
- objective: reconstruct and enrich a reliable working GF while preserving lineage and traceability

The repo is not currently intended to be a generic framework for arbitrary projects.

---

## 4. Core business problem

The real-world inputs are inconsistent:

- GED data is fragmented, duplicated, and workflow-oriented
- the Grand Fichier is manually maintained and may contain errors
- consultant reports are incomplete, inconsistent, and often arrive outside GED timing

The software builds a traceable working truth by combining:

1. **GED normalized truth**
2. **persisted report-derived consultant truth**
3. **run baseline / inherited context**

---

## 5. Source-of-truth model

### GED is the primary operational truth

GED is the authoritative base for document identity, workflow rows, mission calling, and primary lifecycle structure.

### Consultant reports are persistent secondary truth

Consultant reports are not primary, but once matched and persisted they become reusable project truth across future runs.

Example: GED still shows a consultant as pending, but `report_memory.db` already contains a matched consultant answer — the system upgrades the effective response to `ANSWERED`.

### GF is a reconstruction target

GF is **not** the truth source. It is a rebuilt, enriched, operational output.

---

## 6. High-level architecture

```text
GED Export
   ↓
Read / Normalization
   ↓
Version Engine
   ↓
Routing / GF structure mapping
   ↓
Report Memory Merge (effective responses)
   ↓
Workflow computation
   ↓
Reconciliation / discrepancy analysis
   ↓
GF Reconstruction / Enrichment
   ↓
Run Memory / Artifact Persistence
```

The system has three persistent layers:

**A. Core pipeline** — builds the operational outputs.

**B. Report memory** — persists consultant-derived truth across runs.

**C. Run memory** — persists execution history, baseline, artifacts, lineage, and stale propagation.

Long-term architectural direction:

```text
core deterministic engine
    ↓
stable structured output model
    ↓
presentation adapters (UI / reports / Excel exports / dashboards)
```

---

## 7. Current code architecture

The old monolithic `main.py` has been refactored into a staged architecture.

### Entry layer

- `main.py` — thin entrypoint
- `src/run_orchestrator.py` — controlled execution layer with mode resolution and inherited GF logic

### Pipeline layer

- `src/pipeline/context.py` — `PipelineState` (shared state across all stages, 77 fields)
- `src/pipeline/stages/` — ordered pipeline stages (see section 8)
- `src/pipeline/compute.py` — heavy non-pure pipeline computation (discrepancies, etc.)

### Domain logic

- `src/domain/normalization.py`
- `src/domain/discrepancy.py`
- `src/domain/classification.py`
- `src/domain/sas_helpers.py`
- `src/domain/family_builder.py`
- `src/domain/gf_helpers.py`

### Persistence

- `src/run_memory.py` — run history, inputs, artifacts, corrections, invalidation logs
- `src/report_memory.py` — consultant report ingestion and matched responses
- `src/run_explorer.py` — listing runs, summaries, exports, comparisons

### Existing core business modules

- `src/read_raw.py` — GED export reader
- `src/normalize.py` — GED field and response normalization
- `src/version_engine.py` — document family and index lineage
- `src/workflow_engine.py` — workflow state, SAS/MOEX handling, visa logic
- `src/reconciliation_engine.py` — GED vs GF comparison and discrepancy classification
- `src/effective_responses.py` — GED + report memory merge (left-anchored on GED rows)
- `src/routing.py` — GF structure mapping
- `src/writer.py` — GF output writer
- `src/debug_writer.py` — debug artifact writer
- `src/consultant_matcher.py` — report-to-GED matching with confidence model
- `src/consultant_integration.py` — report ingestion orchestration

---

## 8. Pipeline stage flow

Current stage order:

1. `stage_init_run` — initialize run history and execution context
2. `stage_read` — read GED inputs, mapping, and register inputs
3. `stage_normalize` — normalize GED docs and responses, apply SAS filter
4. `stage_version` — build version lineage and latest/historical state
5. `stage_route` — apply routing, exclusions, and read GF structures
6. `stage_report_memory` — merge persisted consultant truth into effective responses
7. `stage_write_gf` — compute workflow outputs, write reconstructed GF, and generate the team GF/VISA workbook
8. `stage_discrepancy` — compute discrepancies and run reconciliation
9. `stage_diagnosis` — produce diagnosis, insert log, and new-submittal analysis
10. `stage_finalize_run` — register artifacts, persist summary, finalize run

`main.py` coordinates these stages through a shared `PipelineState`.

---

## 9. Persistent memory layers

### Report memory (`data/report_memory.db`)

Purpose: persist ingested consultant files, matched consultant responses, and consultant truth across runs. This is project memory for consultant responses.

Key behavior: if a report was ingested once, future runs can reuse that answer even if the user does not re-import the same report file again.

### Run memory (`data/run_memory.db`)

Purpose: persist runs, run inputs, run artifacts, corrections, invalidation logs, and baseline/lineage state. This is the execution history system.

---

## 10. Supported execution modes

Supported modes are defined through the orchestrated execution layer (`src/run_orchestrator.py`).

### `GED_ONLY`

User provides: GED. Internal behavior: GF is inherited from the latest valid completed run, otherwise Run 0. Note: the core still requires a GF workbook internally — this mode means the user does not provide one explicitly and the system resolves one from run history.

### `GED_GF`

User provides: GED + GF.

### `GED_REPORT`

User provides: GED + reports. Internal behavior: GF inherited from latest valid completed run or Run 0.

### `FULL`

User provides: GED + reports + GF (directly, or inherited if omitted and resolvable from run history).

### Explicitly not supported

**`REPORT_ONLY`** — not supported. Consultant matching/enrichment depends on a GED-derived document/workflow universe.

### Inherited GF resolution order

If the user does not provide a GF, the orchestrator resolves one: (1) latest run where status = COMPLETED, is_stale = 0, FINAL_GF artifact exists on disk; (2) fallback to Run 0 FINAL_GF; (3) if nothing usable exists, fail clearly.

---

## How to run

Standard production/local execution:

```bash
python main.py
```

This runs the orchestrated pipeline using the configured inputs under `input/` and persists outputs, artifacts, and run history.

Important:

- Do not bypass the orchestrated path for production runs.
- Do not delete `data/report_memory.db` unless performing a deliberate full memory reset.

---

## Repository structure

```text
main.py                    # thin entrypoint
src/
  run_orchestrator.py      # controlled execution layer
  run_memory.py            # run history persistence
  report_memory.py         # consultant truth persistence
  run_explorer.py          # run listing, export, comparison
  pipeline/
    context.py             # PipelineState
    compute.py             # heavy computation
    stages/                # ordered pipeline stages
  domain/                  # business logic helpers
  read_raw.py
  normalize.py
  version_engine.py
  workflow_engine.py
  reconciliation_engine.py
  effective_responses.py
  routing.py
  writer.py
  debug_writer.py
  consultant_matcher.py
  consultant_integration.py
input/                     # GED, GF, consultant reports
output/                    # pipeline outputs (mirrored to runs/)
runs/                      # run-specific artifact snapshots
data/                      # report_memory.db, run_memory.db
docs/                      # project documentation
```

---

## 11. Inputs

Typical inputs live under `input/`:

- `GED_export.xlsx` — raw GED export
- `Grandfichier_v3.xlsx` — Grand Fichier workbook
- `consultant_reports/` — consultant report PDFs (118 files in current baseline)

The pipeline also uses:

- `data/report_memory.db` — persistent consultant memory
- `data/run_memory.db` — persistent run history

---

## 12. Outputs and artifacts

Typical outputs live under `output/` and are also copied into `runs/run_NNNN/`.

Core artifacts:

- `GF_V0_CLEAN.xlsx` — reconstructed Grand Fichier
- `GF_TEAM_VERSION.xlsx` — team-facing Grand Fichier / Tableau de Suivi VISA generated automatically from the original GF plus `GF_V0_CLEAN.xlsx`
- `DISCREPANCY_REPORT.xlsx` — full discrepancy report
- `DISCREPANCY_REVIEW_REQUIRED.xlsx` — items requiring manual review
- `ANOMALY_REPORT.xlsx` — detected anomalies
- `AUTO_RESOLUTION_LOG.xlsx` — auto-resolved items
- `IGNORED_ITEMS_LOG.xlsx` — intentionally ignored items
- `INSERT_LOG.xlsx` — insert operations log
- `RECONCILIATION_LOG.xlsx` — reconciliation events
- `MISSING_IN_GED_DIAGNOSIS.xlsx` / `MISSING_IN_GED_TRUE_ONLY.xlsx`
- `MISSING_IN_GF_DIAGNOSIS.xlsx` / `MISSING_IN_GF_TRUE_ONLY.xlsx`
- `NEW_SUBMITTAL_ANALYSIS.xlsx`
- `report_memory.db` — snapshot of report memory at time of run
- Debug artifacts under `output/debug/`

Artifacts are registered in `run_memory.db`. Future export should come from the run registry, not random loose files.

### Team GF / Tableau de Suivi VISA workflow

During `stage_write_gf`, the pipeline calls `src/team_version_builder.py` through `build_team_version()`.

This workflow:

- starts from the original `input/Grandfichier_v3.xlsx`
- applies the clean reconstructed truth from `output/GF_V0_CLEAN.xlsx`
- writes `output/GF_TEAM_VERSION.xlsx`
- also writes `output/SUSPICIOUS_ROWS_REPORT.xlsx` for rows that need review
- registers both artifacts in run memory for the completed run

The UI exposes this artifact as **Tableau de Suivi VISA** from Overview Quick Actions, consultant fiche pages, and the Reports page. The export action copies the registered run artifact to:

```text
output/tableau_de_suivi_visa_DD_MM_YYYY.xlsx
```

If the artifact is missing, the UI reports that the pipeline must be run first.

---

## 13. Run history / baseline model

### Run lifecycle states

Each run can be: `STARTED`, `COMPLETED`, or `FAILED`.

### Run 0

Run 0 is the baseline truth. When `run_memory.db` is absent, the pipeline auto-assigns the first run as Run 0 (BASELINE). No separate bootstrap script is required in the current stabilized codebase.

### Later runs

Later runs derive from the baseline and may inherit trusted context from previous completed runs.

### Stale propagation

If a correction is applied against Run 0 or another run, descendant runs can be marked stale recursively.

### Reset discipline

If run history is reset: `runs/` can be deleted, `output/` can be deleted, `data/run_memory.db` can be deleted. `data/report_memory.db` should generally be **preserved** unless a deliberate full memory wipe is intended.

---

## 14. Validation baseline

A healthy run must prove all of the following: pipeline completes, run row exists, latest run is COMPLETED and current, FINAL_GF exists, run artifacts are registered, report memory snapshot exists, no unexpected regression in operational metrics.

Current validated baseline (Run 0):

| Metric | Value |
|--------|-------|
| `docs_total` | 6491 |
| `responses_total` | 545244 |
| `final_gf_rows` | 4728 |
| `discrepancies_count` | 3221 |
| `discrepancies_review_required` | 18 |
| `reconciliation_events` | 171 |
| `artifacts_registered_count` | 26 |
| `consultant_report_memory_rows_loaded` | 1242 |

All future meaningful changes must be validated against this baseline.

---

## 15. UI / reporting status

The backend and staged architecture are stabilized. UI/reporting status is still transitional.

**Completed:**

- Early UI integration milestone reached
- React shell repaired and building in production mode
- Workflow/reporting aggregation improved (blocking pending items counted against real visa flow)
- SAS handling added to reporting with dedicated MOEX SAS fiche
- Backlog prioritization split into blocking vs non-blocking
- Consultant fiche rendering expanded with SAS KPIs, pass/refusal rates, queue state, and pressure indicators
- Desktop launcher supports browser fallback when embedded WebView2 fails

**Still unfinished:**

- Filtering noise reduction
- Backlog cleanup / verification
- Cleaner exploitation layer for rapidly adapting UI/reporting/export logic

**Important limitation:** the backend engine is strong, but UI/report/export exploitation is not yet cleanly separated from internal pipeline knowledge.

---

## 16. Known limitations

- `consultant_match_report.xlsx` is not auto-generated in the main pipeline flow — requires separate `consultant_integration.py` execution
- `report_memory.db` is a persistent dependency and should not be deleted casually
- `PipelineState` is large (77 fields) and carries many cross-stage values
- Discrepancy computation remains a high-complexity area — modify only in small isolated changes
- Excel file hashes are not stable across runs and cannot be used as regression proof
- Full validation currently relies on end-to-end execution rather than a formal unit/integration test suite
- UI/report/export exploitation is not yet cleanly decoupled from backend logic
- openpyxl date serial warnings are non-blocking and do not affect results

See: `docs/KNOWN_LIMITATIONS.md`

---

## 17. Developer and AI working rules

### NEVER

- treat GF as primary truth
- overwrite GED raw data
- silently invent unsupported modes
- silently downgrade execution mode
- bypass run memory for production outputs
- delete `report_memory.db` casually
- auto-accept weak consultant matches without traceability
- perform broad architectural rewrites during normal feature work

### ALWAYS

- preserve deterministic behavior first
- preserve traceability
- respect Run 0 as baseline
- use run history for inherited GF resolution
- use report memory as persisted consultant truth
- keep artifact registration complete
- validate against the baseline after meaningful changes
- prefer scoped changes over repo-wide rewrites

See: `docs/DEVELOPMENT_RULES.md`

---

## 18. Project docs

Read these first before important work:

- `docs/ARCHITECTURE.md` — entry points, stages, state model, critical rules
- `docs/PIPELINE_FLOW.md` — input/output flow and state passing
- `docs/VALIDATION_BASELINE.md` — reference metrics for regression checks
- `docs/DEVELOPMENT_RULES.md` — modification workflow and discipline
- `docs/KNOWN_LIMITATIONS.md` — current rough edges and constraints
- `docs/CLAUDE.md` — AI assistant working context
- `docs/CODEX.md` — project codex

---

## Mental model

This codebase should be understood as:

> A deterministic reconstruction and enrichment engine with persistent project memory and validated staged execution.

It is not just an Excel updater, a report parser, a reconciliation script, or a temporary chantier utility. It is a baseline-driven, lineage-aware operational engine for rebuilding and enriching a Grand Fichier from unstable chantier data.
