#repo-map #reporting #adapters #ui-feed

# Reporting and UI Adapters

> Maps `src/reporting/*` modules to the UI screens they feed.
> See [[06_JANSA_UI_RUNTIME]] for the UI layer, [[03_EXECUTION_FLOW]] for the full read path.

---

## Module map: `src/reporting/`

| File | Role | Consumers |
|---|---|---|
| `data_loader.py` | Builds `RunContext` from `run_memory.db`; manages FLAT_GED pickle cache; resolves latest run | `app.py` — all `Api` methods start here |
| `aggregator.py` | Computes project KPIs, monthly/weekly timeseries, consultant/contractor summaries | `app.py::get_dashboard_data` |
| `ui_adapter.py` | Shapes aggregator output to `window.OVERVIEW / CONSULTANTS / CONTRACTORS` shapes | `app.py::get_*_for_ui` |
| `focus_filter.py` | Applies Focus mode (stale_days + live_numeros narrowing) | `app.py::_apply_focus_filter` |
| `focus_ownership.py` | Computes `_focus_owner` (list) + `_focus_owner_tier` per document. Tiers: `PRIMARY`, `SECONDARY`, `MOEX` (incl. owner `["MOEX SAS"]` variant), `CONTRACTOR`, `CLOSED`. Implements no-MOEX-called closure derivation; SAS REF → CONTRACTOR; SAS-pending → MOEX SAS. (Rewritten 2026-05-09.) | `data_loader._precompute_focus_columns`, `aggregator` |
| `consultant_fiche.py` | Builds per-consultant fiche payload | `app.py::get_consultant_fiche` |
| `contractor_fiche.py` | Builds per-contractor fiche payload; `resolve_emetteur_name` canonical name resolver | `app.py::get_contractor_fiche_for_ui` |
| `contractor_quality.py` | Phase 7: per-contractor quality KPIs (peer stats, polar histogram, long-chains, dormant queues) | `app.py::get_contractor_fiche_for_ui` (merges with fiche header) |
| `document_command_center.py` | DCC backend: search, full panel payload, 7 sections, tag computation | `app.py::search_documents`, `get_document_command_center` |
| `chain_timeline_attribution.py` | Per-chain timing + delay attribution; reads chain_onion CSVs; applies 10-day secondary cap | `app.py::get_chain_timeline`; DCC Chronologie section |
| `drilldown_builder.py` | Builds drilldown drawer rows for KPI tile / VisaFlow / WeeklyActivity / Focus clicks | `app.py::get_documents_drilldown` |
| `counter_attack_builder.py` | Phase 6A: builds `COUNTER_ATTACK_ITEMS.csv` artifact (Action MOEX items) | `scripts/build_counter_attack.py` |
| `counter_attack_query.py` | Phase 6B: query API over `COUNTER_ATTACK_ITEMS.csv` (home, queue, item detail) | `app.py::get_counter_attack_home/queue/item` |
| `counter_attack_ai_pack.py` | Phase 6D: builds `JANSA_AI_AUDIT_PACK_*.zip` export | `app.py::generate_counter_attack_ai_audit_pack` |
| `narrative_translation.py` | FR overlay translations for chain_onion top_issues entries | `app.py::get_chain_onion_intel` |
| `aggregator.py` | Also: `compute_contractor_summary`, `compute_monthly_timeseries`, `compute_weekly_timeseries` | various |
| `bet_report_merger.py` | RETIRED — still on disk, import commented out | — |

---

## UI screen → backend module mapping

| UI Screen | `app.py` method | Backend module | Window global |
|---|---|---|---|
| **Overview** | `get_overview_for_ui` | `aggregator.compute_project_kpis` + `compute_monthly/weekly_timeseries` + `compute_consultant_summary` + `compute_contractor_summary` + `focus_filter.apply_focus_filter` → `ui_adapter.adapt_overview` | `window.OVERVIEW` |
| **Consultants list** | `get_consultants_for_ui` | `aggregator.compute_consultant_summary` → `ui_adapter.adapt_consultants` | `window.CONSULTANTS` |
| **Consultant fiche** | `get_fiche_for_ui` | `consultant_fiche.build_consultant_fiche` (or `build_sas_fiche` for MOEX SAS) | `window.FICHE_DATA` |
| **Contractors list** | `get_contractors_for_ui` | `aggregator.compute_contractor_summary` → `ui_adapter.adapt_contractors_lookup` + `adapt_contractors_list` | `window.CONTRACTORS` + `window.CONTRACTORS_LIST` |
| **Contractor fiche** | `get_contractor_fiche_for_ui` | `contractor_quality.build_contractor_quality` (+ `contractor_fiche.build_contractor_fiche` for header) | `window.CONTRACTOR_FICHE_DATA` |
| **Chain+Onion panel** | `get_chain_onion_intel` | reads `output/chain_onion/top_issues.json` + `dashboard_summary.json`; `narrative_translation.translate_top_issue` per item | `window.CHAIN_INTEL` |
| **DCC — search** | `search_documents` | `document_command_center.search_documents` | — (on-demand) |
| **DCC — panel** | `get_document_command_center` | `document_command_center.build_document_command_center` | — (on-demand) |
| **DCC — Chronologie** | `get_chain_timeline` | `chain_timeline_attribution.load_chain_timeline_artifact` | — (on-demand) |
| **Drilldown drawer** | `get_documents_drilldown` | `drilldown_builder.build_drilldown` | — (on-demand) |
| **Action MOEX — home** | `get_counter_attack_home` | `counter_attack_query.get_counter_attack_home` | — (on-demand) |
| **Action MOEX — queue** | `get_counter_attack_queue` | `counter_attack_query.get_counter_attack_queue` | — (on-demand) |
| **Action MOEX — item** | `get_counter_attack_item` | `counter_attack_query.get_counter_attack_item` | — (on-demand) |
| **Reports — Tableau VISA** | `export_team_version` | `data_loader` + shutil atomic copy | — |
| **Reports — Pack Audit IA** | `generate_counter_attack_ai_audit_pack` | `counter_attack_ai_pack.build_ai_audit_pack` | — |
| **Runs page** | `get_all_runs` / `export_run_bundle` | `run_explorer.get_all_runs` (SQLite) | — |
| **Executer** | `run_pipeline_async` / `get_pipeline_status` | `run_orchestrator.run_pipeline_controlled` | — |

---

## Composed truth principle

`context/guardrail.txt` states:

> *Use the highest-level existing composed truth first. Only fall back to raw artifacts when the composed layer does not expose the required field.*

Applied:
- **Never read** `FLAT_GED.xlsx` directly in a reporting module — go through `RunContext.docs_df` / `responses_df`
- **Never compute** `visa_global` independently — use `ctx.flat_ged_doc_meta` (authoritative, Phase 8 Step 3 fix)
- **Never read** `GF_V0_CLEAN.xlsx` in a UI adapter — read from RunContext layers

---

## Focus mode pipeline

When Focus mode is active (`focus=true` from UI):

1. `app.py::_apply_focus_filter()` calls `focus_filter.apply_focus_filter(ctx, stale_days)`
2. Then `app.py::_build_live_operational_numeros()` queries `chain_onion.query_hooks.get_live_operational(ctx)` to get the set of live-operational chain `numero`s
3. Then `app.py::_apply_live_narrowing()` intersects focus results with live-operational set

Focus result carries: `focused`, `p1_overdue`, `p2_urgent`, `p3_soon`, `p4_ok`, `total_dernier`, `excluded`, `stale`, `resolved`, `by_consultant`, `by_contractor`

---

## data_loader pickle cache (schema version)

`data_loader.py` caches parsed `docs_df` + `responses_df` + `flat_doc_meta` as `.pkl` files. Cache is rejected (forced rebuild) if:
1. `FLAT_GED.xlsx` mtime is newer than cache mtime
2. `cache_schema_version` in `FLAT_GED_cache_meta.json` ≠ `CACHE_SCHEMA_VERSION` constant

**After any change to `stage_read_flat.py` or `flat_ged/transformer.py`**: manually delete the three cache files (`FLAT_GED_cache_docs.pkl`, `FLAT_GED_cache_resp.pkl`, `FLAT_GED_cache_meta.json`) under `output/intermediate/`.

See [[11_DEBUGGING_SEAMS]] §H-2.

---

---

## Operational dashboard ownership (shipped 2026-05-07)

**Owner:** `src/reporting/aggregator.py::compute_operational_dashboard` (lines 554–660).

**Wire-up:** `app.py::get_dashboard_data` calls `compute_operational_dashboard(ctx)` and
merges the returned dict into the dashboard payload under key `"operational"`.

**UI bridge:** `src/reporting/ui_adapter.py::adapt_overview` (lines 236–239) passes
`dashboard["operational"]` through verbatim; no reshaping. Result is exposed as
`window.OVERVIEW.operational` with 21 keys.

**22 keys (verbatim from `compute_operational_dashboard` return dict, post-2026-05-09):**

```
operational_total, fresh_total, stale_total,
moex_total, moex_sas_total, moex_fresh, moex_stale,
primary_total, secondary_total, consultants_total, contractor_total,
priority_p1, priority_p2, priority_p3, priority_p4,
enterprise_ref_sas_candidates, enterprise_action_rows,
old_debt_age_days_min, old_debt_age_days_median, old_debt_age_days_max,
stale_threshold_days, universe_definition
```

**Changes 2026-05-09 (focus-ownership SAS routing + P5 removal patch):**
- `priority_p5` REMOVED. Global workflow is 30 days (business rule A); "no
  deadline" is no longer a valid operational state. Backend collapses
  missing-deadline rows into P1 via a `last_activity + 30d` fallback.
- `moex_total` is now **normal Maître d'Œuvre EXE only**. SAS-pending
  pollution moves to the new `moex_sas_total` field (owner `["MOEX SAS"]`,
  tier still `"MOEX"`).
- `contractor_total` NEW — counts tier `CONTRACTOR` rows inside `op` (REF /
  DEF / SAS REF / no-MOEX-called negative-worst closure).
- `op` universe now also excludes `tier=="CLOSED"` (rule D6 — no-MOEX-called
  favorable-worst closure); ownership-bucket sums reconcile to `operational_total`.

See `context/03_UI_FEED_MAP.md` (2026-05-09 section) and
`context/06_EXCEPTIONS_AND_MAPPINGS.md` ("SAS routing + P5 removal") for
the per-key description, status-equivalence table, and ownership matrix.

**UI screen mapping update:** `OverviewPage` in `ui/jansa/overview.jsx` now reads
`window.OVERVIEW.operational` as the primary tile source (default view). The legacy
`window.OVERVIEW.focus` (11 keys) remains populated but is no longer the default.

**Cross-reference:** `docs/implementation/OPERATIONAL_DASHBOARD_REDESIGN.md` — full
contract, locked baseline, and Phase 1 findings.

---

*Back to [[00_START_HERE]]*
