#repo-map #pipeline #stages

# Pipeline Stages

> The 11 ordered stages in `src/pipeline/stages/`. Run via `src/pipeline/runner.py`.
> See [[03_EXECUTION_FLOW]] for the overall flow, [[02_SOURCE_OF_TRUTH_HIERARCHY]] for layer authority.

---

## Stage order and contracts

| # | Stage file | Role | Key input | Key output |
|---|---|---|---|---|
| 0 | `flat_ged_runner.py` (pre-pipeline) | Auto-builds FLAT_GED | `input/GED_export.xlsx` | `output/intermediate/FLAT_GED.xlsx` |
| 1 | `stage_init_run.py` | Creates run record | `run_memory.db` | New row in `runs` table; creates `runs/run_NNNN/` |
| 2 | `stage_read_flat.py` | Reads FLAT_GED into context | `FLAT_GED.xlsx` (GED_OPERATIONS sheet) | `ctx.docs_df`, `ctx.responses_df` |
| 2' | `stage_read.py` | (raw fallback, `GFUP_FORCE_RAW=1`) | `input/GED_export.xlsx` | same as stage 2 |
| 3 | `stage_normalize.py` | Normalizes docs + responses; SAS RAPPEL pre-2026 filter | `ctx.docs_df`, `ctx.responses_df` | Normalized frames; `ctx.sas_filtered_df` |
| 4 | `stage_version.py` | Versioning engine | `ctx.docs_df` | `ctx.versioned_df` with `is_dernier_indice`, `lifecycle_id`, `chain_position`; `ctx.dernier_df` |
| 5 | `stage_route.py` | Routing table + GF sheet structures | `ctx.versioned_df`, `input/Grandfichier_v3.xlsx` | `ctx.routing_table`; applies `ExclusionConfig` |
| 6 | `stage_report_memory.py` | Ingests consultant matches; builds effective responses | `consultant_match_report.xlsx`, `report_memory.db` | `ctx.effective_responses_df` via `effective_responses.build_effective_responses` |
| 7 | `stage_write_gf.py` | Reconstructs GF | `ctx.effective_responses_df`, routing | `output/GF_V0_CLEAN.xlsx`, ANOMALY_REPORT, AUTO_RESOLUTION_LOG, IGNORED_ITEMS_LOG |
| 8 | `stage_build_team_version.py` | Builds team export | `GF_V0_CLEAN.xlsx`, OGF | `output/GF_TEAM_VERSION.xlsx` (with retry + fallback) |
| 9 | `stage_discrepancy.py` | Discrepancy analysis | `ctx.dernier_df`, `GF_V0_CLEAN.xlsx` | `DISCREPANCY_REPORT.xlsx`, `DISCREPANCY_REVIEW_REQUIRED.xlsx` |
| 10 | `stage_diagnosis.py` | Diagnosis reports | pipeline context | `MISSING_IN_GED/GF_DIAGNOSIS*.xlsx`, `INSERT_LOG.xlsx`, etc. |
| 11 | `stage_finalize_run.py` | Registers all artifacts | `output/*` | sha256-verified entries in `run_artifacts`; `mark_run_current`; copies to `runs/run_NNNN/` |

---

## Stage detail notes

### stage_read_flat (stage 2 default)

- Reads `GED_OPERATIONS` sheet from the registered FLAT_GED artifact (via `run_memory.db`)
- Has `TEMPORARY_COMPAT_LAYER` markers — cosmetic, not functional
- Adapter for the frozen `src/flat_ged/` builder — schema adaptations go here, NOT in flat_ged/

### stage_normalize (stage 3)

- Applies `normalize_docs()` and `normalize_responses()`
- **SAS RAPPEL pre-2026 filter:** strips SAS rows before 2026 to avoid counting old SAS decisions as active blocks

### stage_route (stage 5)

- Reads `ExclusionConfig` from `src/config_loader.py` — this is where EXCLUDED_SHEETS and SHEET_YEAR_FILTERS live
- Reads the current GF xlsx to understand existing sheet structures
- Part H-1 BENTIN_LEGACY_EXCEPTION pass happens at `stage_discrepancy.py`

### stage_report_memory (stage 6)

- Ingestion order matters: deactivate answered → ingest new → load persisted → build effective
- Confidence gate: `_ELIGIBLE_CONFIDENCE_VALUES = {"HIGH", "MEDIUM"}` — do not lower casually
- Both pipeline (here) and UI (`data_loader`) call `build_effective_responses` — shapes must stay identical

### stage_write_gf (stage 7)

- `WorkflowEngine` is constructed inside this stage from `effective_responses_df`
- `WorkflowEngine.__init__` strips `is_exception_approver == True` rows — all SAS rows disappear from the engine view
- **IMPORTANT:** `ctx.workflow_engine.responses_df` ≠ `ctx.responses_df` after this point (see [[11_DEBUGGING_SEAMS]])

### stage_build_team_version (stage 8)

- `src/team_version_builder.build_team_version` does a surgical patch of OGF
- Has retry + fallback logic; registered as run artifact
- UI export via `app.py::export_team_version()` uses atomic-rename pattern

### stage_finalize_run (stage 11)

- If this fails after artifacts are written, the run row stays STARTED
- Orchestrator detects this and calls `finalize_run_failure`
- Do not replace the registration loop without preserving the rollback path

---

## PipelineState / RunContext context object

`src/pipeline/context.py` defines the shared `PipelineState` that flows through all stages.

Key attributes populated progressively:

| Attribute | Set by | Consumers |
|---|---|---|
| `ctx.docs_df` | stage_read_flat | normalize, version, route |
| `ctx.responses_df` | stage_read_flat | normalize, report_memory |
| `ctx.dernier_df` | stage_version | discrepancy, reporting |
| `ctx.effective_responses_df` | stage_report_memory | stage_write_gf, reporting |
| `ctx.workflow_engine` | stage_write_gf | reporting adapters |
| `ctx.flat_ged_doc_meta` | stage_read_flat | aggregator (visa_global authoritative source) |
| `ctx.data_date` | stage_init_run | chain timeline, reporting |

---

## paths.py — single source of truth for directories

`src/pipeline/paths.py` is the canonical home for all directory path constants (`OUTPUT_DIR`, `INTERMEDIATE_DIR`, `DEBUG_DIR`, `CONSULTANT_REPORTS_ROOT`, etc.). Do NOT compute paths from CWD. Do NOT make constants relative.

---

*Back to [[00_START_HERE]]*
