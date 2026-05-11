#repo-map #artifacts #data #outputs

# Data Artifact Index

> All important output artifacts. For module descriptions, see [[14_MODULE_INDEX]].

---

## User-facing outputs (`output/`)

| Artifact | Producer | Consumer | Source-of-truth role | Risk if stale |
|---|---|---|---|---|
| `output/GF_V0_CLEAN.xlsx` | `stage_write_gf.py` | `stage_build_team_version`, discrepancy engine | Reconstruction target (NOT source of truth) | Team deliverable built from stale data |
| `output/GF_TEAM_VERSION.xlsx` | `stage_build_team_version.py` | UI export → `app.py::export_team_version()` | Team deliverable | Wrong data distributed to team |
| `output/DISCREPANCY_REPORT.xlsx` | `stage_discrepancy.py` | UI Discrepancies (stub) | Discrepancy record | Missing or wrong discrepancies shown |
| `output/DISCREPANCY_REVIEW_REQUIRED.xlsx` | `stage_discrepancy.py` | Manual review | Review queue | Wrong items in review queue |
| `output/ANOMALY_REPORT.xlsx` | `stage_write_gf.py` | (manual review) | Anomaly record | — |
| `output/AUTO_RESOLUTION_LOG.xlsx` | `stage_write_gf.py` | (manual review) | Reconciliation trace | — |
| `output/Tableau de suivi de visa DD_MM_YYYY.xlsx` | `app.py::export_team_version()` | Team distribution | Team export (copy of GF_TEAM_VERSION) | Outdated version distributed |

---

## Internal generated artifacts (`output/intermediate/`)

| Artifact | Producer | Consumer | Source-of-truth role | Risk if stale |
|---|---|---|---|---|
| `output/intermediate/FLAT_GED.xlsx` | `src/flat_ged_runner.py` | All pipeline stages (via `stage_read_flat`); Chain+Onion `source_loader` | Normalized operational truth (Rank 2) | All downstream pipeline outputs wrong; Chain+Onion from wrong version |
| `output/intermediate/DEBUG_TRACE.csv` | `src/flat_ged/writer.py` | `chain_onion/source_loader.py` (reads for debug context) | Debug trace | Chain+Onion narrative quality reduced |
| `output/intermediate/FLAT_GED_cache_docs.pkl` | `data_loader._save_flat_normalized_cache` | `data_loader._load_flat_normalized_cache` | Perf cache only | Stale: all UI metrics from wrong data (delete to force rebuild) |
| `output/intermediate/FLAT_GED_cache_resp.pkl` | same | same | Perf cache only | same |
| `output/intermediate/FLAT_GED_cache_meta.json` | same | same | Cache version + audit fields | Schema version mismatch forces rebuild (correct behavior) |
| `output/intermediate/RAW_GED_SOURCE_EXCLUSIONS.csv` | `src/flat_ged/source_exclusions.py` | BENTIN/LGD source-exclusion canary; manual audit | Source-level document exception ledger. Current code: `BENTIN_SOURCE_OLD_NOT_LISTED` | Missing ledger hides document-level source exclusions |
| `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json` | `src/reporting/chain_timeline_attribution.py` | DCC Chronologie section; `app.py::get_chain_timeline` | Per-chain timing | DCC Chronologie shows wrong/missing timing |
| `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv` | same | (tabular form) | Same | Same |
| `output/intermediate/COUNTER_ATTACK_ITEMS.csv` | `src/reporting/counter_attack_builder.py` (via `scripts/build_counter_attack.py`); Phase 9 Step 4 — builder now filters merged rows by `ctx.latest_chain_df` before bucket assignment | `counter_attack_query.py`; Action MOEX UI; `contractor_quality._load_dormant_ref_from_artifact` (canonical post-Phase-9 — §F-2) | Action MOEX item list (stable counts 687/98/107/146 = 1,038) | Action MOEX shows outdated priorities; contractor fiche `dormant_ref` desyncs |

---

## Chain+Onion outputs (`output/chain_onion/`)

Not registered in `run_memory.db`. Coupled to "most recent run that wrote `output/intermediate/`".

| Artifact | Producer | Consumer | Source-of-truth role | Risk if stale |
|---|---|---|---|---|
| `output/chain_onion/CHAIN_REGISTER.csv` | `chain_onion/exporter.py` | `query_hooks.py`, `chain_timeline_attribution.py`, Focus narrowing; Phase 9 (2026-05-11) — `reporting.latest_chain_view.build_latest_chain_view` → `ctx.latest_chain_df` (~2,554 rows) | One-row-per-family chain registry | Focus shows wrong chains; DCC Chronologie wrong; `latest_enriched_view` desyncs from on-disk truth |
| `output/chain_onion/CHAIN_VERSIONS.csv` | same | `chain_timeline_attribution.py` | All document versions | DCC Chronologie missing versions |
| `output/chain_onion/CHAIN_EVENTS.csv` | same | `chain_timeline_attribution.py` | Full event timeline | DCC Chronologie wrong timing |
| `output/chain_onion/CHAIN_METRICS.csv` | same | `query_hooks.py` | Pressure + staleness metrics | Stale metrics in query results |
| `output/chain_onion/ONION_LAYERS.csv` | same | `query_hooks.py` | Per-layer evidence | Query results missing evidence |
| `output/chain_onion/ONION_SCORES.csv` | same | `query_hooks.py`, Focus narrowing | Chain-level scores + portfolio_bucket | Focus shows wrong chains; scores wrong |
| `output/chain_onion/CHAIN_NARRATIVES.csv` | same | (not yet surfaced in UI) | Management summaries | — |
| `output/chain_onion/dashboard_summary.json` | same | `app.py::get_chain_onion_intel` → `window.CHAIN_INTEL` | Portfolio KPI snapshot | ChainOnionPanel summary wrong |
| `output/chain_onion/top_issues.json` | same | `app.py::get_chain_onion_intel` → `window.CHAIN_INTEL` | Top 20 chains by priority | ChainOnionPanel priority table wrong |
| `output/chain_onion/CHAIN_ONION_SUMMARY.xlsx` | same | (manual review / distribution) | 11-sheet management workbook | Stale intel distributed |

---

## In-memory derived views (NOT persisted, Phase 9, 2026-05-11)

| View | Producer | Consumer | Role | Notes |
|---|---|---|---|---|
| `ctx.latest_chain_df` | `reporting.latest_chain_view.build_latest_chain_view(base_dir, docs_df)` at context load | every operational reporting module | Canonical one-row-per-chain DataFrame (~2,554 rows) | Built from `CHAIN_REGISTER.csv` × `docs_df`; recomputed every context build, never written to disk |
| `latest_enriched_view(ctx)` | `reporting.latest_chain_view.latest_enriched_view(ctx)` on demand | every operational reporting module | Operational view (~2,553 rows): `ctx.dernier_df` intersected with `ctx.latest_chain_df.(numero, latest_indice)`, inheriting `_precompute_focus_columns` + `compute_focus_ownership` enrichments | Materialised per call; never written to disk. Decision-3 N≈1 gap vs chain count is by design (numero 253100; §F-3) |

See `README.md §Phase 9`, `context/11_TOOLING_HAZARDS.md` §H-9.

---

## Persistent state

| Artifact | Producer | Consumer | Source-of-truth role | Risk if stale |
|---|---|---|---|---|
| `data/run_memory.db` | `stage_init_run`, `stage_finalize_run` | `data_loader.py`, `run_explorer.py`, `app.py` | Artifact registry; cross-run identity | All artifact resolution fails; GF inheritance breaks |
| `data/report_memory.db` | `stage_report_memory.py` (ingests new rows) | `stage_report_memory`, `data_loader`, `chain_onion/source_loader` | Persistent consultant truth | Consultant answers lost; effective_responses falls back to GED only |

---

## Run snapshot (`runs/run_NNNN/`)

| Artifact | Content | Note |
|---|---|---|
| `runs/run_0000/` | Immutable baseline snapshot | Do NOT manually edit; sha256-verified |
| `runs/run_NNNN/` | Per-run artifact copies | Mirror of `output/` at finalization time |

---

## Debug outputs (`output/debug/`)

| Artifact | Producer | Purpose |
|---|---|---|
| `output/debug/counts_lineage_audit.{xlsx,json}` | `scripts/audit_counts_lineage.py` | Cross-layer count comparison |
| `output/debug/counts_lineage_probe.{xlsx,json}` | same `--probe` mode | 119-record provenance trace L0–L6 |
| `output/debug/chain_onion_source_check.json` | `chain_onion/source_loader.py` | FLAT_GED path alignment check (WARN-only) |
| `output/debug/sas_pre2026_confirmation.json` | `scripts/audit_counts_lineage.py` | D-012 SAS pre-2026 decomposition receipts |

---

## Consultant ingestion artifacts

| Artifact | Producer | Consumer |
|---|---|---|
| `output/consultant_reports.xlsx` | `src/consultant_integration.py` | `stage_report_memory.py` |
| `output/consultant_match_report.xlsx` | `src/consultant_match_report.py` | `stage_report_memory.py` (registered as artifact) |

---

## Exports

| Artifact | Producer | Consumer |
|---|---|---|
| `output/exports/JANSA_AI_AUDIT_PACK_*.zip` | `counter_attack_ai_pack.py` | User download |
| `output/exports/run_bundle_N.zip` | `app.py::export_run_bundle` | User download (run history bundle) |
| `output/Drilldown_<consultant>_<filter>_DDMMYYYY.xlsx` | `app.py::export_drilldown_xlsx` | User download |

---

*Back to [[00_START_HERE]]*
