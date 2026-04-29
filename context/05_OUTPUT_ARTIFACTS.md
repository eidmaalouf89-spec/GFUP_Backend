# 05 — Output Artifacts

> Every artifact produced by a pipeline run, plus chain_onion outputs.
> Reconstructed from `pipeline/paths.py`, the eleven stages, the registered
> artifacts in `data/run_memory.db`, and the on-disk inventory in `output/`.

Three places hold artifacts after a run:

1. `output/` — flat copy of the latest run's outputs (UI consumes this).
2. `runs/run_NNNN/` — immutable per-run snapshot (registered with sha256).
3. `data/run_memory.db` (`run_artifacts` table) — registry of the above.

`run_explorer.export_run_bundle(run_number)` ZIPs the `runs/run_NNNN/`
folder and writes it to `output/exports/run_N_bundle.zip`.

---

## Primary outputs (top of `output/`)

| File | Producer stage | Producer module | Consumer | Notes |
|---|---|---|---|---|
| `GF_V0_CLEAN.xlsx` | `stage_write_gf` | `writer.GFWriter.write` | `stage_build_team_version` (template patch base); `data_loader` (registered as `FINAL_GF`) | Reconstructed GF — internal, NOT the team file |
| `GF_TEAM_VERSION.xlsx` | `stage_build_team_version` | `team_version_builder.build_team_version` | `app.Api.export_team_version` (UI) | Surgical patch of OGF (Grandfichier_v3.xlsx) using GF_V0_CLEAN as truth |
| `Tableau de suivi de visa DD_MM_YYYY.xlsx` | `app.Api.export_team_version` | `data_loader` + shutil.copy2 | User (manual export) | Dated copy of GF_TEAM_VERSION; on-demand |
| `DISCREPANCY_REPORT.xlsx` | `stage_discrepancy` | `writer.write_discrepancy_report` | (no UI consumer today; Discrepancies page is a stub) | All flag_types with severity |
| `DISCREPANCY_REVIEW_REQUIRED.xlsx` | `stage_discrepancy` | `writer.write_discrepancy_report` | (none) | severity == REVIEW_REQUIRED only |
| `ANOMALY_REPORT.xlsx` | `stage_write_gf` | `writer.write_anomaly_report` | (none in UI) | Lifecycle anomalies |
| `AUTO_RESOLUTION_LOG.xlsx` | `stage_write_gf` | `writer.write_auto_resolution_log` | (none in UI) | What the resolver fixed silently |
| `IGNORED_ITEMS_LOG.xlsx` | `stage_write_gf` then appended in `stage_discrepancy` | `writer.write_ignored_items_log` then pandas append | (none in UI) | Excluded rows + BENTIN_LEGACY append |
| `RECONCILIATION_LOG.xlsx` | `stage_discrepancy` | `reconciliation_engine.write_reconciliation_outputs` | (none) | Patch F fuzzy reconciliation log |
| `MISSING_IN_GED_DIAGNOSIS.xlsx` | `stage_diagnosis` | `pipeline.compute._write_missing_in_ged_diagnosis` | (none) | Diagnosis layer A |
| `MISSING_IN_GED_TRUE_ONLY.xlsx` | `stage_diagnosis` | same | (none) | True misses only |
| `MISSING_IN_GF_DIAGNOSIS.xlsx` | `stage_diagnosis` | `pipeline.compute._write_missing_in_gf_diagnosis` | (none) | Diagnosis layer B |
| `MISSING_IN_GF_TRUE_ONLY.xlsx` | `stage_diagnosis` | same | (none) | True misses only |
| `INSERT_LOG.xlsx` | `stage_diagnosis` | `writer.write_insert_log` | (none) | New rows the reconstruction inserted |
| `NEW_SUBMITTAL_ANALYSIS.xlsx` | `stage_diagnosis` | `writer.write_new_submittal_analysis` + `domain.family_builder._build_new_submittal_analysis` | (none) | New-doc family analysis |
| `SUSPICIOUS_ROWS_REPORT.xlsx` | `stage_diagnosis` (or `stage_write_gf`) | `writer` | (none) | Suspicious GF rows |
| `consultant_match_report.xlsx` | `stage_route` / `consultant_integration` (when reports_dir provided) | `consultant_match_report` + `consultant_matcher` | `stage_report_memory` (next run picks it up) | Per-consultant matched rows |
| `consultant_reports.xlsx` | `consultant_ingest.consultant_excel_exporter` | `consultant_ingest.consultant_report_builder` | (none direct) | Standardised consultant report workbook |

All of these are registered in `run_memory.db.run_artifacts` under the
matching uppercase `artifact_type`. `data_loader._get_artifact_path` is
the lookup used by `app.Api.export_team_version`.

---

## Intermediate outputs (`output/intermediate/`)

| File | Producer | Consumer | Notes |
|---|---|---|---|
| `FLAT_GED.xlsx` | `flat_ged_runner.build_flat_ged_artifacts` (pre-pipeline) | `stage_read_flat`, `chain_onion.source_loader`, `data_loader` | Sheets: `GED_RAW_FLAT`, `GED_OPERATIONS` |
| `DEBUG_TRACE.csv` | same (batch mode) | `chain_onion.source_loader` | Builder debug trace |
| `flat_ged_run_report.json` | same | (none direct) | Builder run metadata |
| `CHAIN_TIMELINE_ATTRIBUTION.json` | `reporting.chain_timeline_attribution.write_chain_timeline_artifact` | (Phase 4: Document Command Center) | Per-chain timeline + per-segment responsibility. NOT registered in run_memory.db. Auto-refreshed at app startup (Phase 3). |
| `CHAIN_TIMELINE_ATTRIBUTION.csv` | same | Excel inspection | Flat per-segment-per-attribution rows. |

The first three (`FLAT_GED.xlsx`, `DEBUG_TRACE.csv`, `flat_ged_run_report.json`)
are registered in `run_memory.db` as `FLAT_GED`, `FLAT_GED_DEBUG_TRACE`,
`FLAT_GED_RUN_REPORT`. The builder writes `run_report.json` and
`flat_ged_runner.py` renames it to `flat_ged_run_report.json` (contract
naming).

`CHAIN_TIMELINE_ATTRIBUTION.*` is intentionally NOT registered in
`run_memory.db` — it is computed on-demand from chain_onion CSVs +
RunContext, and disk-only persistence is enough. Its JSON shape is the
contract consumed by Phase 4. See `context/02_DATA_FLOW.md` and
`docs/implementation/02_PHASE_2_REPORT.md` for the schema.

---

## Debug outputs (`output/debug/`)

All produced inside `stage_diagnosis` via `debug_writer.write_all_debug`
and a few earlier stages (`stage_route` for routing/exclusion). Registered
under `DEBUG_*` artifact types.

| File | Stage | Purpose |
|---|---|---|
| `coarse_groups.xlsx` | diagnosis | Coarse grouping by lot |
| `discrepancy_sample.xlsx` | diagnosis | Sample for manual review |
| `exclusion_summary.xlsx` | route | ExclusionConfig stats |
| `family_clusters.xlsx` | diagnosis | family_builder clusters |
| `gf_duplicates.xlsx` | diagnosis | Duplicate rows in GF |
| `gf_sheet_schema.xlsx` | route | Detected per-sheet schemas |
| `lifecycle_resolution.xlsx` | diagnosis | Lifecycle decision log |
| `missing_in_ged_summary.xlsx` | diagnosis | Aggregate over MISSING_IN_GED |
| `missing_in_gf_summary.xlsx` | diagnosis | Aggregate over MISSING_IN_GF |
| `new_submittal_summary.xlsx` | diagnosis | Aggregate over NEW_SUBMITTAL |
| `reconciliation_summary.xlsx` | discrepancy | Aggregate over reconciliation |
| `routing_summary.xlsx` | route | Per-document routing decision |

---

## Chain + Onion outputs (`output/chain_onion/`)

Produced by `python run_chain_onion.py`, NOT by the main pipeline.

| File | Producer (Step) | Consumer |
|---|---|---|
| `CHAIN_REGISTER.csv` | family_grouper (05) + classifier (07) | `chain_onion.query_hooks`, `validation_harness`; `app._build_live_operational_numeros` |
| `CHAIN_VERSIONS.csv` | family_grouper (05) | `query_hooks`, `validation_harness` |
| `CHAIN_EVENTS.csv` | chain_builder (06) | `validation_harness` |
| `CHAIN_METRICS.csv` | chain_metrics (08) | `query_hooks`, `validation_harness` |
| `ONION_LAYERS.csv` | onion_engine (09) | `query_hooks`, `validation_harness` |
| `ONION_SCORES.csv` | onion_scoring (10) | `query_hooks`, `app._build_live_operational_numeros` |
| `CHAIN_NARRATIVES.csv` | narrative_engine (11) | `query_hooks` |
| `dashboard_summary.json` | exporter (12) | `query_hooks.get_dashboard_summary` |
| `top_issues.json` | exporter (12) | `query_hooks.get_top_issues` |
| `CHAIN_ONION_SUMMARY.xlsx` | exporter (12) | (manual review only) |

`output/chain_onion/dashboard_summary.json` is NOT directly read by the
UI today; it would be the natural input for a future "Top issues" screen.

---

## State databases

| File | Owner | Schema | Cleared by |
|---|---|---|---|
| `data/run_memory.db` | `src.run_memory` | tables: `runs`, `run_inputs`, `run_artifacts`, `run_corrections`, `run_invalidation_log` | manual; `scripts/nuke_and_rebuild_run0.py` |
| `data/report_memory.db` | `src.report_memory` | tables: `ingested_reports`, `persisted_report_responses` | `scripts/bootstrap_report_memory.py` |
| `data/report_memory.db.malformed_bak` | (artifact of past corruption) | — | manual cleanup candidate |

---

## On-disk leftovers (NOT current artifacts — candidates for cleanup)

These exist on disk today (`/output/`, repo root) but are not produced by
the active runtime:

- `output/parity/`, `output/parity_raw_r1/`, `output/parity_raw_run1/`,
  `output/parity_raw_run2/` — flat-vs-raw parity validation data, pre-Step 16.
- `output/step9/legacy/` — legacy Step 9 outputs.
- `output/parity_report.xlsx`, `output/ui_parity_report.xlsx`,
  `output/clean_gf_diff_report.xlsx` — one-off validation reports.
- `output/tmp63o7zaid.xlsx` — orphaned temp.
- Repo root: `tmpxkmaioec.db`, `tmpyw_386pd.db`,
  `run_explorer_bundle_latest.zip`, `test_write_permission.tmp`,
  `run_a.log` … `run_f.log`, `step15_debug.log`, `pipeline_run.log`,
  `fix_gf_schema_main.log`, `test1_main_no_baseline.log`,
  `test2_*.log`.
- `backup/`, `backups/` (date-stamped backup folders).

These are out of scope for runtime, but listed so future cleanups can
target them safely. **Do not delete without an explicit task.**

---

## "Tableau de suivi de visa 10_04_2026.xlsx"

Found in `output/`. Produced by a previous `export_team_version()` invocation
on 2026-04-10. `app.Api.export_team_version` overwrites by deleting the
existing dest before renaming the temp file in place, so a future export
will replace it (or leave it if a different date stamp is generated). Not
a leak — this is the user-facing dated team export.
