# 05 â€” Output Artifacts

> Every artifact produced by a pipeline run, plus chain_onion outputs.
> Reconstructed from `pipeline/paths.py`, the eleven stages, the registered
> artifacts in `data/run_memory.db`, and the on-disk inventory in `output/`.

Three places hold artifacts after a run:

1. `output/` â€” flat copy of the latest run's outputs (UI consumes this).
2. `runs/run_NNNN/` â€” immutable per-run snapshot (registered with sha256).
3. `data/run_memory.db` (`run_artifacts` table) â€” registry of the above.

`run_explorer.export_run_bundle(run_number)` ZIPs the `runs/run_NNNN/`
folder and writes it to `output/exports/run_N_bundle.zip`.

---

## Primary outputs (top of `output/`)

| File | Producer stage | Producer module | Consumer | Notes |
|---|---|---|---|---|
| `GF_V0_CLEAN.xlsx` | `stage_write_gf` | `writer.GFWriter.write` | `stage_build_team_version` (template patch base); `data_loader` (registered as `FINAL_GF`) | Reconstructed GF â€” internal, NOT the team file |
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
| `RAW_GED_SOURCE_EXCLUSIONS.csv` | `flat_ged.source_exclusions` during Flat GED batch build | Audit/debug; source-exclusion validation | Document-level source exclusions before Raw GED rows enter Flat GED. Current code: `BENTIN_SOURCE_OLD_NOT_LISTED` for BEN/BENTIN rows before 2026-03-10 not listed in `context/source_exclusions/remaining bentin.csv`. Expected current count: 701. |
| `CHAIN_TIMELINE_ATTRIBUTION.json` | `reporting.chain_timeline_attribution.write_chain_timeline_artifact` | (Phase 4: Document Command Center) | Per-chain timeline + per-segment responsibility. NOT registered in run_memory.db. Auto-refreshed at app startup (Phase 3). |
| `CHAIN_TIMELINE_ATTRIBUTION.csv` | same | Excel inspection | Flat per-segment-per-attribution rows. |
| `FLAT_GED_cache_docs.pkl` / `FLAT_GED_cache_resp.pkl` / `FLAT_GED_cache_meta.json` | `data_loader._save_flat_normalized_cache` (writes alongside `FLAT_GED.xlsx`) | `data_loader._load_flat_normalized_cache` (skips xlsx re-parse on hot loads) | Pickle cache for normalized `docs_df` + `responses_df`. `cache_meta.json` carries `cache_schema_version` (currently `"v2"` post Phase 8 step 4), `approver_names`, `flat_doc_meta`, plus 8 audit fields: `source_flat_ged_sha256`, `source_flat_ged_mtime`, `docs_df_rows`, `responses_df_rows`, `active_version_count`, `family_count`, `status_counts`, `generated_at`. Freshness check rejects schema-version mismatches per Phase 0 D-001. Bump `CACHE_SCHEMA_VERSION` whenever stage_read_flat schema or pickle compatibility changes. NOT registered in `run_memory.db`. |
| `COUNTER_ATTACK_ITEMS.csv` | `scripts/build_counter_attack.py` â†’ `reporting.counter_attack_builder.build_counter_attack_items` (Phase 6A/6X; standalone, NOT a pipeline stage) | Phase 6B read API; future Counter-Attack UI page | 28-column deterministic action artifact (1524 rows after Phase 6X R3 validation). Inputs: `compute_dcc_tags_bulk(ctx)` + chain_onion CSVs (CHAIN_REGISTER, CHAIN_METRICS, ONION_SCORES, CHAIN_NARRATIVES) + CHAIN_TIMELINE_ATTRIBUTION + ctx.responses_df for evidence. Uses DCC deadline truth (`primary_consultant_days_remaining`, `secondary_consultant_days_remaining`, `consultant_days_remaining`) and secondary backlog ladder. NOT registered in `run_memory.db`. |

The first three (`FLAT_GED.xlsx`, `DEBUG_TRACE.csv`, `flat_ged_run_report.json`)
are registered in `run_memory.db` as `FLAT_GED`, `FLAT_GED_DEBUG_TRACE`,
`FLAT_GED_RUN_REPORT`. The builder writes `run_report.json` and
`flat_ged_runner.py` renames it to `flat_ged_run_report.json` (contract
naming).

Clean Run 0 baseline after the BENTIN source-exclusion patch (2026-05-07):
`RAW_GED_SOURCE_EXCLUSIONS.csv` has 701
`BENTIN_SOURCE_OLD_NOT_LISTED` rows; `FLAT_GED.xlsx` has 4,374 OPEN_DOC
versions, 24,812 `GED_RAW_FLAT` rows, and 29,176 `GED_OPERATIONS` rows. The
old 4,848 Flat document baseline is retired.

`CHAIN_TIMELINE_ATTRIBUTION.*` is intentionally NOT registered in
`run_memory.db` â€” it is computed on-demand from chain_onion CSVs +
RunContext, and disk-only persistence is enough. Its JSON shape is the
contract consumed by Phase 4. See `context/02_DATA_FLOW.md` and
`docs/implementation/02_PHASE_2_REPORT.md` for the schema.

`COUNTER_ATTACK_ITEMS.csv` (Phase 6A/6X) is similarly NOT registered in
`run_memory.db`. It is generated on-demand by `scripts/build_counter_attack.py`
after a pipeline run. Binding rules:

- **Pre-bucket filter:** rows are excluded when `chain_register.current_state`
  is in the terminal/non-actionable set:
  `{"CLOSED_VAO", "CLOSED_VSO", "DEAD_AT_SAS_A", "ABANDONED_CHAIN", "VOID_CHAIN", "UNKNOWN_CHAIN_STATE"}`.
- **`ENTREPRISE_A_RELANCER`:** fires only when
  `current_state == "WAITING_CORRECTED_INDICE"` and the DCC `primary_tag`
  confirms contractor-owned action (`Att Entreprise ...`). This route is
  evaluated before secondary backlog routing so correction-pending REF rows
  do not become MOEX exposure rows.
- **Primary consultant lateness:** `CONSULTANT_A_ATTAQUER` is deadline-truth
  only. It requires `primary_consultant_days_remaining < 0` (or trusted
  `consultant_days_remaining < 0` fallback from DCC), computed against
  `ctx.data_date`, never `date.today()` and never chain dwell.
- **Secondary backlog ladder:** `secondary_wait_days` is used only as backlog
  age for secondary/MOEX routing: `<=10` no bucket, `10..30` MOEX facile or
  arbitrage buckets when DCC tag says so, `30..100` `SECONDAIRE_EXPIRE`,
  `>100` `MOEX_SHAME_INTERNAL`. This is not consultant contractual lateness.
- **Direct MOEX wait:** `OPEN_WAITING_MOEX` routes to `MOEX_SHAME_INTERNAL`
  only when `moex_wait_days > 100`; otherwise DCC `Att MOEX - Facile` /
  `Att MOEX - Arbitrage` select `FERMER_MAINTENANT` / `DECISION_MOEX`.
- **`days_late` semantics after Phase 6X:** consultant rows use deadline
  lateness, secondary backlog rows use `secondary_wait_days`, direct MOEX rows
  use `moex_wait_days`, contractor rows use chain dwell (`stale_days` or
  `open_days` fallback).- **Forbidden label:** the user-facing label for `MOEX_SHAME_INTERNAL` is
  `"MOEX interne â€” exposition Ã  traiter"`. The string `"Honte MOEX"` must
  not appear anywhere in the artifact, code, or documentation.
- **Evidence columns (`chain_observations_*`, `consultant_reports_*`) are
  enrichment-only.** They never influence `action_bucket`, `actor_to_call`,
  `is_internal_moex_exposure`, `is_external_attackable`, or
  `normalized_score_100`.
- **Determinism:** same inputs â†’ byte-identical 28-column CSV. Verified by
  consecutive sha256 match.
- **No new ownership / tag / score logic.** The builder reuses
  `compute_dcc_tags_bulk` (additive bulk wrapper around DCC private
  helpers, no new rules) and the existing chain_onion CSVs.
- **First consumer (Phase 6B):** `src/reporting/counter_attack_query.py`
  exposes three read-only screen-payload functions
  (`get_counter_attack_home`, `get_counter_attack_queue`,
  `get_counter_attack_item`) over this artifact, surfaced as
  `Api.get_counter_attack_home/queue/item` in `app.py` and as
  `jansaBridge.loadCounterAttackHome/Queue/Item` in
  `ui/jansa/data_bridge.js`. The query module reads the CSV with
  identity columns (`item_id`, `numero`, `indice`, `family_key`,
  `emetteur_code`) locked as `string` to preserve leading zeros, and
  returns `available=false` empty-state payloads when the artifact is
  missing. No artifact mutation. See
  `docs/implementation/PHASE_6B_READ_API.md`.

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
| `counts_lineage_audit.xlsx` | `scripts/audit_counts_lineage.py` (Phase 8 step 1; extended through step 6) | manual review | Sheets: `lineage`, `expected_baselines`, `divergences_unexpected`, `ui_payload_mismatches` (added step 6 â€” empty when all aligned, sheet always present). Compares L0_RAW_GED â†’ L6_CHAIN_ONION counts. NOT registered in `run_memory.db`. |
| `counts_lineage_audit.json` | same | same | Machine-readable companion. Top-level keys: lineage matrix, `expected_baselines` (with `raw_submission_rows.provenance` capturing source file / sheet / mtime as of step 2), `ui_payload_comparison` (added step 6 â€” `fields_compared`, `matches`, `mismatches`, `mismatch_rows[]`, `skipped[]`). Shape documented in `docs/implementation/PHASE_8_COUNT_LINEAGE_FIX.md` Â§5.3 + Â§24. |
| `counts_lineage_probe.xlsx` | `python scripts/audit_counts_lineage.py --probe` (Phase 8 step 2) | manual review | One row per (count_category, layer). Columns: `value`, `value_origin_type`, `source_file`, `source_sheet`, `source_column`, `source_filter`, `function_or_code_path`, `is_hardcoded_baseline`, `confidence`. Use to prove provenance of every audit number. NOT registered. |
| `counts_lineage_probe.json` | same | same | Same content as the xlsx, machine-readable. |
| `sas_pre2026_confirmation.json` | `scripts/audit_counts_lineage.py:_confirm_sas_pre2026_gap` (Phase 8 step 2.5; refreshed every default audit run) | manual review; D-012 receipts | Decomposes the L1â†’L2 SAS REF row gap. Fields: `l1_sas_ref_row_count`, `l2_sas_ref_row_count`, `row_gap`, `excluded_unique_pair_count`, `excluded_l1_row_count`, `pair_to_l1_row_count`, `structural_duplicate_pairs`, `sas_filter_component`, `structural_component`, `verdict` (`CONFIRMED` / `PARTIAL_CONFIRMED` / `UNCONFIRMED` / `UNDETERMINED`). NOT registered. |
| `chain_onion_source_check.json` | `src/chain_onion/source_loader.py:_check_flat_ged_alignment` (Phase 8 step 5; refreshed every Chain+Onion run) | manual review; step 5 receipts | WARN-only Chain+Onion source alignment receipts. Compares the FLAT_GED.xlsx path source_loader is reading against the latest registered FLAT_GED artifact in `data/run_memory.db`. Fields: `result` (`OK` / `WARN_PATH_MISMATCH_SAME_CONTENT` / `WARN_PATH_AND_CONTENT_MISMATCH` / `WARN_MTIME_ADVISORY` / `UNDETERMINED`), `registered_flat_ged_path`, `using_flat_ged_path`, `sha_match` (bool / null when paths identical), `reason`, `checked_at`. Helper never raises and never blocks Chain+Onion. NOT registered. |
| `focus_visa_source_audit.xlsx` | `scripts/audit_focus_visa_source.py` (Phase 8A.1) | manual review; D-010 scope receipts | One sheet `call_sites` (10 rows, 9 columns). AST-walk catalogue of every `compute_visa_global_with_date` call site in `src/reporting/`. Columns: `function_name`, `file_path`, `line_number`, `uses_workflow_engine_directly`, `uses_flat_doc_meta`, `uses_resolve_visa_global_equivalent`, `affected_output_columns`, `count_of_docs_checked`, `count_of_disagreements`. NOT registered. |
| `focus_visa_source_audit.json` | same | same | Machine-readable companion. Top-level keys: `generated_at`, `target_function`, `reporting_dir`, `call_sites[]`. |
| `chain_onion_block_readiness.json` | `scripts/check_chain_onion_alignment_block_ready.py` (Phase 8A.3) | manual review; gate check before Phase 8A.4 BLOCK-mode flip | Verifies the WARN-only check has been clean across a fresh full pipeline cycle. Fields: `checked_at`, `block_mode_ready` (bool), `reason`, `latest_check_result`, `latest_run_completed_at`, `latest_flat_ged_mtime`, `helper_first_seen_at`. NOT registered. |
| `ui_payload_full_surface_audit.{xlsx,json}` | `scripts/audit_ui_payload_full_surface.py` (Phase 8A.6) | manual review; widened UI payload audit | Compares aggregator/builder vs adapter outputs across 6 UI surfaces (overview, consultants_list, contractors_list, consultant_fiche, contractor_fiche, dcc, chain_onion_panel). Final result (2026-05-01): `UI_PAYLOAD_FULL: surfaces=6 compared=45 matches=45 mismatches=0; OK - all compared fields match`. Classification: NM=0, SF=0, ESD=0, TB=0. NOT registered. |
| `raw_flat_reconcile.xlsx` | `scripts/raw_flat_reconcile.py` (Phase 8B) | manual review; RAWâ†”FLAT identity / projection audit | 11-sheet workbook (~695 KB). Sheets cover identity contract, SAS REF decomposition, reasons audit, report integration trace, shadow-model rows. Output of Phase 8B reconciliation. NOT registered. |
| `flat_ged_trace.{csv,xlsx}` | `scripts/raw_flat_reconcile.py` (Phase 8B) | manual review | Per-row FLAT projection trace with classification (CANONICAL / DUPLICATE_FAVORABLE_KEPT / DUPLICATE_MERGED / ACTIVE_VERSION_PROJECTION / MALFORMED_RESPONSE / UNEXPLAINED). NOT registered. |
| `raw_ged_trace.csv` | `scripts/raw_flat_reconcile.py` (Phase 8B) | manual review | Per-row RAW GED trace used as comparator for the FLAT projection. NOT registered. |
| `report_to_flat_trace.{json,xlsx}` | `scripts/raw_flat_reconcile.py` (Phase 8B) | manual review | Report-integration trace: `data/report_memory.db` rows mapped to FLAT destinations. Phase 8B totals: 1,245 reports â†’ 0 NO_MATCH, 942 enrich FLAT, 58 supply primary, 226 blocked on confidence. NOT registered. |
| `SHADOW_FLAT_GED_OPERATIONS.csv` | `scripts/raw_flat_reconcile.py` (Phase 8B) | manual review; never overwrites production FLAT | Phase 8B shadow-corrected operational layer. 27,134 rows; UNEXPLAINED residual = 6. Disk-only diagnostic; NOT registered, NOT consumed by runtime. |
| `SHADOW_FLAT_GED_TRACE.xlsx` | `scripts/raw_flat_reconcile.py` (Phase 8B) | manual review | Per-row shadow-FLAT trace. Companion to `SHADOW_FLAT_GED_OPERATIONS.csv`. NOT registered. |
| `PHASE_8B_FINAL_REPORT.md` | Phase 8B closure | reference | Final report and Â§17 decision gate (Outcome C). Identity contract PASS; SAS REF gap 99.3% explained; 6 SAS REF rows remain UNEXPLAINED. NOT registered. |

---

## Chain + Onion outputs (`output/chain_onion/`)

Produced by `python run_chain_onion.py`, NOT by the main pipeline.

| File | Producer (Step) | Consumer |
|---|---|---|
| `CHAIN_REGISTER.csv` | family_grouper (05) + classifier (07) | `chain_onion.query_hooks`, `validation_harness`; `app._build_live_operational_numeros`; Phase 9 (2026-05-11) — also consumed by `reporting.latest_chain_view.build_latest_chain_view` to populate `ctx.latest_chain_df` (~2,554 rows, one per chain) during context load |
| `CHAIN_VERSIONS.csv` | family_grouper (05) | `query_hooks`, `validation_harness` (~4,374 rows; all document versions) |
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

`output/chain_onion/top_issues.json` (Phase 4, 2026-05-01) carries 14 fields
per record: the 11 original keys (`family_key`, `numero`,
`action_priority_rank`, `normalized_score_100`, `urgency_label`,
`portfolio_bucket`, `current_state`, `executive_summary`,
`primary_driver_text`, `recommended_focus`, `escalation_flag`) plus three
new identity fields appended at export time: `emetteur_code` (3-letter
code), `emetteur_name` (canonical company name resolved via
`reporting.contractor_fiche.resolve_emetteur_name`), and `titre` (raw PDF
filename from GED_OPERATIONS). The three new fields are sourced from the
in-memory `ops_df` passed into `export_chain_onion_outputs(...)` as
`issue_meta_df`; the lookup picks `chain_register_df.latest_version_key`
for each family. Unmapped emetteur codes fall back to the code itself
(documented `resolve_emetteur_name` behavior).

---

## State databases

| File | Owner | Schema | Cleared by |
|---|---|---|---|
| `data/run_memory.db` | `src.run_memory` | tables: `runs`, `run_inputs`, `run_artifacts`, `run_corrections`, `run_invalidation_log` | manual; `scripts/nuke_and_rebuild_run0.py` |
| `data/report_memory.db` | `src.report_memory` | tables: `ingested_reports`, `persisted_report_responses` | `scripts/bootstrap_report_memory.py` |
| `data/report_memory.db.malformed_bak` | (artifact of past corruption) | â€” | manual cleanup candidate |

---

## On-disk leftovers (NOT current artifacts â€” candidates for cleanup)

These exist on disk today (`/output/`, repo root) but are not produced by
the active runtime:

- `output/parity/`, `output/parity_raw_r1/`, `output/parity_raw_run1/`,
  `output/parity_raw_run2/` â€” flat-vs-raw parity validation data, pre-Step 16.
- `output/step9/legacy/` â€” legacy Step 9 outputs.
- `output/parity_report.xlsx`, `output/ui_parity_report.xlsx`,
  `output/clean_gf_diff_report.xlsx` â€” one-off validation reports.
- `output/tmp63o7zaid.xlsx` â€” orphaned temp.
- Repo root: `tmpxkmaioec.db`, `tmpyw_386pd.db`,
  `run_explorer_bundle_latest.zip`, `test_write_permission.tmp`,
  `run_a.log` â€¦ `run_f.log`, `step15_debug.log`, `pipeline_run.log`,
  `fix_gf_schema_main.log`, `test1_main_no_baseline.log`,
  `test2_*.log`.
- `backup/`, `backups/` (date-stamped backup folders).

These are out of scope for runtime, but listed so future cleanups can
target them safely. **Do not delete without an explicit task.**

---

## “Tableau de suivi de visa 10_04_2026.xlsx”

Found in `output/`. Produced by a previous `export_team_version()` invocation
on 2026-04-10. `app.Api.export_team_version` overwrites by deleting the
existing dest before renaming the temp file in place, so a future export
will replace it (or leave it if a different date stamp is generated). Not
a leak â€” this is the user-facing dated team export.

---

## On-demand exports (`output/exports/`)

Produced on demand from the JANSA app UI. NOT registered in `run_memory.db`
and NOT part of any pipeline stage. Each export is independent — filename
carries a generation timestamp, not a run number. The directory is created
on first call with `mkdir(parents=True, exist_ok=True)`. The existing
`run_N_bundle.zip` exports (from `Api.export_run_bundle`) and the AI audit
pack both land in `output/exports/` but are distinct in naming, content,
and trigger path.

| Artifact | Location | Trigger | Generator | Purpose / Notes |
|---|---|---|---|---|
| `JANSA_STANDALONE_HTML__run_<NNNN>__<YYYY-MM-DD>_<HHMM>.html` | `output/exports/` | `Exporter snapshot HTML` button in `ReportsPage` (`ui/jansa/shell.jsx`) → `jansaBridge.exportStandaloneHtmlSnapshot()` → `Api.export_standalone_html_snapshot` | `src/reporting/standalone_html_snapshot.write_standalone_html_snapshot(api, base_dir)` | Read-only frozen JANSA cockpit. Self-contained HTML; opens directly in Chrome with no backend. Embeds composed UI payloads (overview, consultants, contractors, chain intel, action MOEX home + 4 queues + items, per-consultant & per-contractor fiches, pre-built DCC panels for numeros surfaced in chain intel / action MOEX queues, chain timelines, and a flat offline search index). Reuses the live UI assets (`tokens.js` + the snapshot-aware `data_bridge.js` + every `ui/jansa/*.jsx` component) inlined verbatim. Snapshot detection: `data_bridge.js` checks `window.JANSA_SNAPSHOT_DATA` / `#jansa-snapshot-data` and swaps every read method to resolve from the embedded blob. Mutating actions (Generate GF, AI audit pack, imports, pipeline, save corrections, every xlsx export) return a `{success:false, disabled:true}` envelope in snapshot mode and the corresponding Reports cards are dimmed via `bridge.isSnapshot`. A fixed yellow bottom banner ("MODE SNAPSHOT HTML — LECTURE SEULE — run … — data … — généré …") confirms read-only and is hidden from print preview. **Full 1:1 parity with the live software:** captures every payload for both focus modes (`focus_off`/`focus_on`) for overview, consultants, contractors, every consultant + contractor fiche; pre-builds the full dashboard-drilldown matrix (48 entries × both focus) and the full fiche-drilldown matrix (~15 000 entries: global + per-lot + per-period × both focus); pre-builds `get_document_command_center` + `get_chain_timeline` for every numero harvested across all drilldowns (no cap, ~2 500 at current run). File size ~80 MB (design ceiling 100 MB); build time ~40–45 min. NOT registered in `run_memory.db`. Full contract in `obsidian_repo_mind/06_JANSA_UI_RUNTIME.md` "Standalone HTML Snapshot". |
| `JANSA_AI_AUDIT_PACK_<YYYYMMDD>_<HHMMSS>.zip` | `output/exports/` | `Générer Pack Audit IA` button in `ReportsPage` (`ui/jansa/shell.jsx` post-edit lines 877–910) | `src/reporting/counter_attack_ai_pack.build_ai_audit_pack(ctx, output_dir)` | External-AI evidence pack. Contains 14 required entries: 8 verbatim-copied source CSVs (`DATA/01_COUNTER_ATTACK_ITEMS.csv` through `DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv`), 1 in-memory-built `DATA/09_FLAT_GED_EXTRACT.csv` (LEFT JOIN of `ctx.docs_df` × `ctx.responses_df`, 20 columns, sorted ascending by `(numero, indice, doc_id, approver_canonical)` with mergesort), 1 `README_FOR_AI.md` (French-first, short English note at end), and 5 `PROMPTS/*.md` files (French-first, covering the six accepted attack angles). Up to 4 optional entries included when present on disk: `DATA/SUBJECT_RISK_DOSSIERS.csv`, `DATA/ACTOR_ATTACK_DOSSIERS.csv`, `DATA/dashboard_summary.json`, `DATA/top_issues.json`. Missing required source → clean error payload (`success: false`), no crash. Missing optional source → recorded in `missing_optional_files`, pack still ships. NOT registered in `run_memory.db`. See `docs/implementation/PHASE_6D_TEAM_AI_AUDIT_PACK.md` §10. |
