#repo-map #modules #index

# Module Index

> Table of all important files and modules. For artifacts, see [[15_DATA_ARTIFACT_INDEX]].

---

## Entrypoints

| File/Path | Role | Consumers | Produces | Risk | Notes |
|---|---|---|---|---|---|
| `main.py` | Pipeline entrypoint | `run_orchestrator.py` (via import) | Delegates to runner | HIGH | Intentionally tiny; mutable globals written by orchestrator |
| `app.py` | JANSA desktop app launcher; `Api` class | PyWebView bridge | All UI data | HIGH | PyWebView + React; `_resolve_ui()` is hard-wired to `jansa-connected.html` |
| `run_chain_onion.py` | Chain+Onion independent runner | Manual / CI | `output/chain_onion/*` | MEDIUM | Separate from main pipeline; reads `output/intermediate/` directly |

---

## Pipeline core

| File/Path | Role | Consumers | Produces | Risk | Notes |
|---|---|---|---|---|---|
| `src/run_orchestrator.py` | Controlled pipeline execution + mode selection | `main.py`, `app.py` | Delegates to `pipeline/runner.py` | HIGH | `_patched_main_context` mutates main namespace — do not replace with config injection |
| `src/pipeline/runner.py` | `_run_pipeline_impl` — executes 11 stages | `run_orchestrator.py` | Calls all stages | HIGH | Reads paths from `sys.modules["main"]`, NOT from `pipeline.paths` |
| `src/pipeline/context.py` | `PipelineState` shared context | All stages | `ctx.*` attributes | HIGH | Stages read/write `ctx` progressively |
| `src/pipeline/paths.py` | Directory constants | `main.py`, `runner.py`, `app.py` | Path constants | HIGH | Single source of truth for all paths; never relative, never CWD-based |

---

## Pipeline stages

| File/Path | Role | Key input | Key output | Risk |
|---|---|---|---|---|
| `src/pipeline/stages/stage_init_run.py` | Creates run row | `run_memory.db` | Run number; `runs/run_NNNN/` | HIGH |
| `src/pipeline/stages/stage_read_flat.py` | Reads FLAT_GED into context | `FLAT_GED.xlsx` | `ctx.docs_df`, `ctx.responses_df` | HIGH |
| `src/pipeline/stages/stage_normalize.py` | Normalizes docs + responses | `ctx.docs_df/responses_df` | Normalized frames; `ctx.sas_filtered_df` | HIGH |
| `src/pipeline/stages/stage_version.py` | Versioning engine | `ctx.docs_df` | `ctx.versioned_df`, `ctx.dernier_df` | HIGH |
| `src/pipeline/stages/stage_route.py` | Routing + GF sheet structures | `ctx.versioned_df`, GF xlsx | `ctx.routing_table` | HIGH |
| `src/pipeline/stages/stage_report_memory.py` | Ingests matches; builds effective responses | `consultant_match_report.xlsx`, `report_memory.db` | `ctx.effective_responses_df` | HIGH |
| `src/pipeline/stages/stage_write_gf.py` | Reconstructs GF | `ctx.effective_responses_df` | `GF_V0_CLEAN.xlsx`, ANOMALY/AUTO_RESOLUTION/IGNORED logs | HIGH |
| `src/pipeline/stages/stage_build_team_version.py` | Team export | `GF_V0_CLEAN.xlsx` | `GF_TEAM_VERSION.xlsx` | HIGH |
| `src/pipeline/stages/stage_discrepancy.py` | Discrepancy analysis | `ctx.dernier_df`, GF | `DISCREPANCY_REPORT.xlsx` | MEDIUM |
| `src/pipeline/stages/stage_diagnosis.py` | Diagnosis reports | pipeline context | diagnostic XLSXs | MEDIUM |
| `src/pipeline/stages/stage_finalize_run.py` | Artifact registration | `output/*` | sha256 rows in `run_memory.db` | HIGH |

---

## Flat GED builder (frozen)

| File/Path | Role | Risk | Notes |
|---|---|---|---|
| `src/flat_ged/` (whole package) | FROZEN builder; reads raw GED → writes FLAT_GED.xlsx | HIGH | Do NOT edit business rules. Adapter changes in `stage_read_flat.py` only |
| `src/flat_ged_runner.py` | Calls flat_ged builder; called pre-pipeline | HIGH | Auto-builds `output/intermediate/FLAT_GED.xlsx` |
| `src/flat_ged/input/source_main/consultant_mapping.py` | `RAW_TO_CANONICAL`, `EXCEPTION_COLUMNS`, `SPECIAL_CASES` | HIGH | Hardcoded business knowledge |
| `src/flat_ged/input/source_main/status_mapping.py` | `VALID_STATUSES`, `BUREAU_CONTROLE_STATUSES` | HIGH | Hardcoded business knowledge |

---

## Reporting / UI adapters

| File/Path | Role | Risk |
|---|---|---|
| `src/reporting/data_loader.py` | Builds `RunContext`; pickle cache management | HIGH |
| `src/reporting/aggregator.py` | KPIs, timeseries, consultant/contractor summaries | HIGH |
| `src/reporting/ui_adapter.py` | Shapes output to `window.*` globals | HIGH |
| `src/reporting/focus_filter.py` | Focus mode (stale_days + live_numeros narrowing) | HIGH |
| `src/reporting/focus_ownership.py` | PRIMARY/SECONDARY/MOEX tier per document | HIGH |
| `src/reporting/consultant_fiche.py` | Per-consultant fiche; `resolve_emetteur_name` canonical names | HIGH |
| `src/reporting/contractor_fiche.py` | Per-contractor fiche; `resolve_emetteur_name` | HIGH |
| `src/reporting/contractor_quality.py` | Phase 7: contractor quality KPIs (peer stats, polar, long-chains) | HIGH |
| `src/reporting/document_command_center.py` | DCC backend — search + panel + all business logic | HIGH |
| `src/reporting/chain_timeline_attribution.py` | Per-chain timing + 10-day secondary cap | HIGH |
| `src/reporting/drilldown_builder.py` | Drilldown drawer rows | MEDIUM |
| `src/reporting/counter_attack_builder.py` | Phase 6A: builds COUNTER_ATTACK_ITEMS.csv | HIGH |
| `src/reporting/counter_attack_query.py` | Phase 6B: read API over COUNTER_ATTACK_ITEMS.csv | MEDIUM |
| `src/reporting/counter_attack_ai_pack.py` | Phase 6D: AI Audit Pack export | MEDIUM |
| `src/reporting/narrative_translation.py` | FR overlay for top_issues | LOW |

---

## Chain+Onion

| File/Path | Step | Role | Risk |
|---|---|---|---|
| `src/chain_onion/source_loader.py` | 04 | Loads FLAT_GED + debug trace + report memory | HIGH |
| `src/chain_onion/family_grouper.py` | 05 | Groups rows into families | HIGH |
| `src/chain_onion/chain_builder.py` | 06 | Timeline events | HIGH |
| `src/chain_onion/chain_classifier.py` | 07 | `current_state` + `portfolio_bucket` | HIGH |
| `src/chain_onion/chain_metrics.py` | 08 | `stale_days`, pressure index | HIGH |
| `src/chain_onion/onion_engine.py` | 09 | Per-layer evidence rows | HIGH |
| `src/chain_onion/onion_scoring.py` | 10 | Chain-level scores + ranks | HIGH |
| `src/chain_onion/narrative_engine.py` | 11 | Management summaries | MEDIUM |
| `src/chain_onion/exporter.py` | 12 | 7 CSVs + XLSX + 2 JSONs (contract owner) | HIGH |
| `src/chain_onion/query_hooks.py` | 13 | 26 query functions over `QueryContext` | MEDIUM |
| `src/chain_onion/validation_harness.py` | 14 | 40-check acceptance harness | MEDIUM |

---

## Persistence

| File/Path | Role | Risk |
|---|---|---|
| `src/run_memory.py` | Artifact registry schema + query helpers | HIGH |
| `src/report_memory.py` | Consultant truth persistence | HIGH |
| `src/effective_responses.py` | Composition layer (GED + report_memory) | HIGH |
| `src/team_version_builder.py` | Team export builder (surgical OGF patch) | HIGH |

---

## Business logic helpers

| File/Path | Role | Risk |
|---|---|---|
| `src/config_loader.py` | `EXCLUDED_SHEETS`, `SHEET_YEAR_FILTERS`, `SHEET_EMETTEUR_FILTER` | HIGH |
| `src/domain/classification.py` | Document classification helpers | MEDIUM |
| `src/domain/normalization.py` | Normalization helpers | MEDIUM |
| `src/domain/family_builder.py` | Family grouping helpers | MEDIUM |
| `src/query_library.py` | 22-function query API over Flat GED context (Step 9c) | MEDIUM |
| `src/reconciliation_engine.py` | Discrepancy reconciliation | HIGH |

---

## UI

| File/Path | Role | Risk |
|---|---|---|
| `ui/jansa-connected.html` | Production UI entrypoint (only) | HIGH |
| `ui/jansa/shell.jsx` | App root, routing, focus toggle, DCC panel mount | HIGH |
| `ui/jansa/data_bridge.js` | PyWebView bridge; window.* contract | HIGH |
| `ui/jansa/tokens.js` | Design tokens; required by all components | HIGH |
| `ui/jansa/overview.jsx` | Dashboard KPIs + ChainOnionPanel | MEDIUM |
| `ui/jansa/consultants.jsx` | Consultants list | MEDIUM |
| `ui/jansa/fiche_base.jsx` | Fiche layout + DrilldownDrawer | MEDIUM |
| `ui/jansa/fiche_page.jsx` | Consultant fiche wrapper | MEDIUM |
| `ui/jansa/contractors.jsx` | Contractors page | MEDIUM |
| `ui/jansa/contractor_fiche_page.jsx` | Contractor quality fiche | MEDIUM |
| `ui/jansa/document_panel.jsx` | DCC drawer (pure rendering) | HIGH |
| `ui/jansa/counter_attack.jsx` | Action MOEX page | MEDIUM |
| `ui/jansa/runs.jsx` | Run history | LOW |
| `ui/jansa/executer.jsx` | Pipeline launcher | MEDIUM |

---

## Scripts (developer tools)

| File/Path | Role |
|---|---|
| `scripts/audit_counts_lineage.py` | Cross-layer audit L0→L6 (primary debug tool) |
| `scripts/audit/` | 8 targeted audit scripts (chains, dormant, REF, SAS REF, etc.) |
| `scripts/build_counter_attack.py` | Builds `COUNTER_ATTACK_ITEMS.csv` |
| `scripts/bootstrap_run_zero.py` | Rebuilds `run_memory.db` from scratch |
| `scripts/bootstrap_report_memory.py` | Rebuilds `report_memory.db` from scratch |
| `scripts/nuke_and_rebuild_run0.py` | Resets run 0 (destructive) |
| `scripts/reset_to_clean_run0.py` | Resets run 0 (safe) |
| `scripts/repo_health_check.py` | Repo health check |
| `scripts/audit_ui_payload_full_surface.py` | UI payload surface audit |

---

*Back to [[00_START_HERE]]*
