# 04 — Pipeline Stages

> Order, inputs, outputs, and side-effects per stage.
> Reconstructed from `src/pipeline/runner.py` and each
> `src/pipeline/stages/stage_*.py`.

The runner reads its path constants from the **calling module's namespace**
(`sys.modules["main"]`), not from `pipeline.paths`. This is intentional:
`run_orchestrator._patched_main_context` mutates those constants per run
(e.g. swaps `GED_FILE`, sets `FLAT_GED_FILE`, redirects `OUTPUT_GF_TEAM_VERSION`
when reports are disabled).

The pipeline state is a `pipeline.context.PipelineState` dataclass-ish object;
each stage reads/writes attributes on it.

---

## Order of execution (`_run_pipeline_impl`)

```
0. PipelineState ctx = ...                 # built from main module's namespace
1. stage_init_run(ctx, log)
2. stage_read_flat(ctx, log)               # if FLAT_GED_MODE == "flat" (default at runtime)
   stage_read(ctx, log)                    # if FLAT_GED_MODE == "raw" (GFUP_FORCE_RAW=1)
3. stage_normalize(ctx, log)
4. stage_version(ctx, log)
5. stage_route(ctx, log)
6. stage_report_memory(ctx, log)
7. stage_write_gf(ctx, log)
8. stage_build_team_version(ctx, log)
9. stage_discrepancy(ctx, log)
10. stage_diagnosis(ctx, log)
11. stage_finalize_run(ctx, log)           # returns the result dict
```

---

## Per-stage detail

### 1. `stage_init_run`

- **Reads:** `ctx.BASE_DIR`, `ctx.RUN_MEMORY_DB`, `ctx.RUN_MEMORY_CORE_VERSION`,
  `ctx._RUN_CONTROL_CONTEXT`.
- **Writes (DB):** initialises `data/run_memory.db` if missing; creates a
  `runs` row with status `STARTED`; allocates next `run_number`; creates
  `runs/run_NNNN/` directory.
- **Writes (ctx):** `_ACTIVE_RUN_NUMBER`, `_ACTIVE_RUN_FINALIZED=False`.
- **Depends on:** `src.run_memory` (DB schema lives there).

### 2a. `stage_read` (raw fallback only)

- **Reads:** `ctx.GED_FILE`, `ctx.MAPPING` not used here (mapping is
  consumed via `normalize.load_mapping` in the next stage today, kept
  optional).
- **Calls:** `read_raw.read_ged(ged_file)`; `normalize.load_mapping(...)`;
  registers run inputs in `run_memory` with sha256.
- **Writes (ctx):** `docs_df`, `responses_df`, `mapping`, `approver_names`.

### 2b. `stage_read_flat` (active path)

- **Reads:** `ctx.FLAT_GED_FILE` (i.e. `output/intermediate/FLAT_GED.xlsx`).
- **Reads sheets:** `GED_RAW_FLAT` and `GED_OPERATIONS`.
- **Reconstructs** `docs_df` and `responses_df` to the same shape as
  `stage_read` so downstream stages run unchanged.
- **Encapsulates** SAS RAPPEL pre-2026 filter (Decision 3) and synthesises
  legacy `response_date_raw` strings ("En attente visa (YYYY/MM/DD)",
  "Rappel : …") so that `normalize_responses` → `interpret_date_field` works
  unchanged. This is documented as TEMPORARY_COMPAT_LAYER inside the file.
- **Writes (ctx):** `docs_df`, `responses_df`, `mapping`, `approver_names`.

### 3. `stage_normalize`

- **Reads (ctx):** `docs_df`, `responses_df`, `mapping`.
- **Calls:** `normalize.normalize_docs`, `normalize.normalize_responses`,
  `domain.sas_helpers._apply_sas_filter`.
- **Writes (ctx):** mutated `docs_df` and `responses_df`; `sas_filtered_df`
  (rows excluded by SAS RAPPEL pre-2026 filter, kept for audit trail).

### 4. `stage_version`

- **Reads (ctx):** `docs_df`.
- **Calls:** `version_engine.VersionEngine` to reconstruct lifecycles from
  `(emetteur, lot_normalized, type_doc, numero_normalized)`.
- **Writes (ctx):** `versioned_df` with `is_dernier_indice`,
  `lifecycle_id`, `chain_position`, `anomaly_flags`, `confidence`,
  `is_excluded_lifecycle`. Also: `total`, `dernier_count`, `anomaly_count`,
  `excluded_count`. Derives `dernier_df` for downstream consumers.

### 5. `stage_route`

- **Reads (ctx):** `GF_FILE`, `versioned_df`, `dernier_df`.
- **Calls:** `routing.build_routing_table`, `routing.route_documents`,
  `routing.read_all_gf_sheet_structures`,
  `config_loader.load_exclusion_config()`.
- **Writes (ctx):** `dernier_df_for_gf` (annotated), `sheet_structures`,
  `exclusion_config`, `gf_sas_lookup`.
- **Side effect:** writes `output/debug/routing_summary.xlsx`,
  `output/debug/exclusion_summary.xlsx`.
- **Reads `src/config_loader.py`** for:
  - `EXCLUDED_SHEETS = {"LOT I01-VDSTP", "LOT I02-FKI"}`
  - `SHEET_YEAR_FILTERS = {"LOT 03-GOE-LGD": 2026,
    "LOT 31 à 34-IN-BX-CFO-BENTIN": 2026}`
  - `SHEET_EMETTEUR_FILTER` (35+ sheets, contractor code ↔ sheet rules).

### 6. `stage_report_memory`

- **Reads (ctx):** `responses_df`, `CONSULTANT_MATCH_REPORT`,
  `REPORT_MEMORY_DB`.
- **Calls:** `report_memory.init_report_memory_db`,
  `report_memory.is_report_already_ingested`,
  `report_memory.upsert_report_responses`,
  `report_memory.load_persisted_report_responses`,
  `report_memory.deactivate_answered_report_rows`,
  `effective_responses.build_effective_responses`.
- **Confidence gate:** only HIGH and MEDIUM responses are stored
  (`_ELIGIBLE_CONFIDENCE_VALUES = {"HIGH", "MEDIUM"}`).
- **Writes (ctx):** `effective_responses_df` (GED rows ⨝ persisted
  consultant truth).

### 7. `stage_write_gf`

- **Reads (ctx):** `effective_responses_df`, `dernier_df_for_gf`,
  `responses_df`, `sheet_structures`, `versioned_df`, `dernier_df`,
  `sas_filtered_df`, `OUTPUT_GF`, `GF_FILE`,
  `OUTPUT_ANOMALY`, `OUTPUT_AUTO_RESOLUTION`, `OUTPUT_IGNORED`.
- **Calls:** `workflow_engine.WorkflowEngine`,
  `routing.build_gf_to_ged_map`, `domain.sas_helpers._build_sas_lookup`,
  `writer.GFWriter.write`, `writer.write_anomaly_report`,
  `writer.write_auto_resolution_log`, `writer.write_ignored_items_log`.
- **Writes (filesystem):**
  - `output/GF_V0_CLEAN.xlsx`
  - `output/ANOMALY_REPORT.xlsx`
  - `output/AUTO_RESOLUTION_LOG.xlsx`
  - `output/IGNORED_ITEMS_LOG.xlsx`
- **Writes (ctx):** `wf_engine`, `gf_sas_lookup`, `mismatch_count`.

### 8. `stage_build_team_version`

- **Reads (ctx):** `OUTPUT_GF` (just-written `GF_V0_CLEAN.xlsx`),
  `GF_FILE` (the OGF template).
- **Resolution order for OGF template** (per file docstring):
  1. `ctx.GF_FILE` if it exists on disk.
  2. Most recent `GF_TEAM_VERSION` artifact from `run_memory.db`.
  3. Most recent `FINAL_GF` artifact from `run_memory.db`.
  4. Skip or fail with clear message.
- **Calls:** `team_version_builder.build_team_version`.
- **Retry policy:** 3 attempts (immediate, +1 s, +2 s).
- **Fatal policy:** in `FULL` / `GED_REPORT` modes, raises `RuntimeError`
  after 3 failed attempts. Other modes: warning logged, pipeline continues.
- **Writes (filesystem):** `output/GF_TEAM_VERSION.xlsx`.

### 9. `stage_discrepancy`

- **Reads (ctx):** `dernier_df_for_gf`, `GF_FILE`, `DEBUG_DIR`,
  `exclusion_config`, `responses_df`, `versioned_df`, `GED_FILE`.
- **Calls:**
  - `pipeline.compute._determine_data_date` → `data_date`.
  - `pipeline.compute._compute_discrepancies`.
  - `reconciliation_engine.run_reconciliation` (post-processing fuzzy match).
  - `reconciliation_engine.write_reconciliation_outputs`.
  - `domain.discrepancy.classify_discrepancy` for severity.
- **Special pass — Part H-1: BENTIN legacy exception**.
  Sheet `"LOT 31 à 34-IN-BX-CFO-BENTIN"` × flag types
  `{MISSING_IN_GF_TRUE, MISSING_IN_GF_AMBIGUOUS_TITLE_MATCH,
  INDICE_MISMATCH, DATE_MISMATCH}` → relabelled `BENTIN_LEGACY_EXCEPTION`
  and appended to `IGNORED_ITEMS_LOG.xlsx`.
- **Writes (filesystem):**
  - `output/DISCREPANCY_REPORT.xlsx`
  - `output/DISCREPANCY_REVIEW_REQUIRED.xlsx`
  - `output/RECONCILIATION_LOG.xlsx`
  - `output/debug/reconciliation_summary.xlsx`
  - `output/IGNORED_ITEMS_LOG.xlsx` (appended)
- **Writes (ctx):** `data_date`, `discrepancies`, `gf_by_sheet`.

### 10. `stage_diagnosis`

- **Reads (ctx):** `discrepancies`, `dernier_df_for_gf`, `wf_engine`,
  `gf_sas_lookup`, `data_date`, `dernier_df`, `versioned_df`, plus all
  `OUTPUT_MISSING_*` paths.
- **Calls:**
  - `pipeline.compute._write_missing_in_ged_diagnosis`
  - `pipeline.compute._write_missing_in_gf_diagnosis`
  - `writer.write_insert_log`
  - `writer.write_new_submittal_analysis`
  - `domain.family_builder._build_new_submittal_analysis`
  - `debug_writer.write_all_debug`
- **Writes (filesystem):**
  - `output/MISSING_IN_GED_DIAGNOSIS.xlsx`, `MISSING_IN_GED_TRUE_ONLY.xlsx`
  - `output/MISSING_IN_GF_DIAGNOSIS.xlsx`, `MISSING_IN_GF_TRUE_ONLY.xlsx`
  - `output/INSERT_LOG.xlsx`
  - `output/NEW_SUBMITTAL_ANALYSIS.xlsx`
  - `output/SUSPICIOUS_ROWS_REPORT.xlsx`
  - `output/debug/*_summary.xlsx` (lifecycle, family, gf_duplicates,
    coarse_groups, missing_in_*_summary, etc.)

### 11. `stage_finalize_run`

- **Reads (ctx):** all artifact paths.
- **Calls:**
  - `run_memory.copy_artifact_to_run_dir` (per artifact → `runs/run_NNNN/`).
  - `run_memory.register_run_artifact` with sha256.
  - `run_memory.mark_run_current`.
  - `run_memory.update_run_metadata`.
  - `run_memory.finalize_run_success` (or `finalize_run_failure` on error).
- **Returns:** result dict
  ```python
  {
    "success": True,
    "run_number": int,
    "status": "COMPLETED",
    "errors": [],
    "warnings": [...],
    "outputs": {...},
    "artifact_count": int,
  }
  ```

---

## Stage dependency graph (read/write)

```
init_run     → DB row, run_number, runs/run_NNNN/ dir
read_flat    → docs_df, responses_df, mapping (FROM init)
normalize    → mutates docs_df, responses_df; produces sas_filtered_df
version      → versioned_df, dernier_df  (FROM normalize)
route        → dernier_df_for_gf, sheet_structures, exclusion_config
                                            (FROM version + GF_FILE)
report_memory→ effective_responses_df  (FROM route + DB + match_report)
write_gf     → GF_V0_CLEAN.xlsx, anomaly/auto/ignored
                                            (FROM report_memory + sheet_structures)
build_team   → GF_TEAM_VERSION.xlsx  (FROM write_gf + GF_FILE/registry)
discrepancy  → DISCREPANCY_REPORT, RECONCILIATION_LOG, ignored++, data_date
                                            (FROM write_gf + dernier_df_for_gf)
diagnosis    → MISSING_*, INSERT_LOG, NEW_SUBMITTAL, SUSPICIOUS, debug/*
                                            (FROM discrepancy + version + wf_engine)
finalize_run → register all artifacts in run_memory.db; mark current
```

A failure in any stage triggers `finalize_run_failure` (called by
`run_orchestrator` if the run never reached `finalize_run_success`),
ensuring the runs row never stays `STARTED`.

---

## Re-running the pipeline

There is no granular "re-run from stage X" mode in code today. The pipeline
runs end-to-end every time. Stage skipping is achieved indirectly via run
modes (e.g. `GED_ONLY` redirects consultant-related output paths to a
disabled root in `_patched_main_context`, so consultant ingestion produces
files into a sandbox).
