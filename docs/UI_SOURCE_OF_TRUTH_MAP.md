# UI Source of Truth Map
**Step 10 — FLAT GED → Backend Integration Plan v2**
**Date:** 2026-04-26
**Author:** Audit by Claude / Step 10 execution

---

## 1. Executive Summary

**Is the UI currently trustworthy?**

Conditionally yes. The UI consumes `effective_responses_df` (the composed truth from `build_effective_responses`), which correctly integrates report memory. The retired `bet_report_merger` is fully commented out and not called. The data path is sound.

**Biggest risks:**

1. **Duplicated derivation logic.** The fiche builder (`consultant_fiche.py`) and the API drilldown method (`app.py:get_doc_details`, ~140 lines) independently re-implement `_attach_derived()`, `_filter_for_consultant()`, and `_resolve_status_labels()`. Any divergence between them produces UI inconsistencies that are currently untested.

2. **`query_library.py` is not yet called by the UI.** The UI uses `aggregator.py` and `consultant_fiche.py` for all metrics. `query_library.py` uses `flat_ged_ops_df` and `effective_responses_df` directly — a different identity model (doc_key vs doc_id). The parity bridge between these two identity systems is not yet built.

3. **Four "Not yet connected" fields in OVERVIEW.** `visa_flow.on_time`, `visa_flow.late`, all `*_delta` comparison fields, and all `trend` sparklines in the consultant list are hardcoded `None`/`[]`. The UI handles these gracefully (shows "délais non calculés") but Step 11 must flag them explicitly.

4. **`refus_rate` semantic mismatch.** `adapt_overview()` computes refusal rate as `(REF + SAS_REF docs) / total_docs` (document-level). `query_library.get_status_breakdown()` computes it at step level. These will not match numerically. Step 11 must account for this explicitly.

5. **Two dead UI code paths.** `ui/src/App.jsx` + `ui/dist/` (old Vite build) and `JANSA Dashboard - Standalone.html` (archived bundle) are not loaded by `app.py`. They are dead code and should not be confused with the active runtime.

**Can `query_library` replace the scattered logic?**

Yes, for portfolio KPIs and consultant KPIs. Not directly for fiche timeline blocks (bloc1/bloc2/bloc3), which require per-consultant, per-lot time-series aggregation that is not yet in `query_library`. Step 11 should treat fiche blocks as a future concern and focus parity comparison on the scalar KPIs.

---

## 2. UI Runtime Inventory

| Runtime | Entry Point | Files | Status | Why |
|---|---|---|---|---|
| **PyWebView + JSX (Babel standalone)** | `ui/jansa-connected.html` | `ui/jansa/*.jsx`, `ui/jansa/data_bridge.js`, `ui/jansa/tokens.js` | **ACTIVE** | `app.py._resolve_ui()` explicitly looks for and loads this file. All API calls flow through `window.pywebview.api`. |
| **Vite/React dev build** | `ui/index.html`, `ui/src/App.jsx` | `ui/src/`, `ui/vite.config.js` | **DEAD** | Not referenced by `app.py`. Built into `ui/dist/` which is also not loaded. The `ui/src/components/ConsultantFiche.jsx` is a legacy JSX component replaced by `ui/jansa/fiche_base.jsx`. |
| **Vite dist bundle** | `ui/dist/index.html` | `ui/dist/assets/index-BNCEp8m7.js` | **DEAD** | Not referenced by `app.py`. The `_resolve_ui()` function only checks `ui/jansa-connected.html`. |
| **Standalone HTML** | `JANSA Dashboard - Standalone.html` (root) | Single self-contained file | **DEAD** | Not referenced by `app.py`. Appears to be an archived or experimental self-contained bundle. Never loaded in production. |
| **Browser fallback** | `_ui_target_for_browser(ui_url)` | Same `jansa-connected.html` | **ACTIVE (fallback)** | `app.py` falls back to `webbrowser.open()` if PyWebView fails. Loads same HTML in the OS default browser — no pywebview API available, bridge uses placeholder data. |

---

## 3. Current Data Flow

### Full pipeline → UI path

```
input/GED_export.xlsx
input/Grandfichier_v3.xlsx
    │
    ▼
pipeline/runner.py (main.py / run_orchestrator.py)
    ├── stage_read_flat.py       → flat_ged_ops_df (Flat GED builder output)
    ├── stage_normalize.py       → docs_df, responses_df
    ├── stage_version.py         → versioned_df, dernier_df
    ├── stage_report_memory.py   → effective_responses_df (via build_effective_responses)
    ├── stage_write_gf.py        → FINAL_GF artifact
    └── stage_finalize_run.py    → run_memory.db (artifact registry)
    
    data/report_memory.db        ← loaded separately
    │
    ▼
reporting/data_loader.load_run_context()
    ├── read_ged() + normalize_docs/responses() → raw docs_df, responses_df
    ├── VersionEngine.run() → dernier_df
    ├── load_persisted_report_responses(report_memory.db)
    │       + build_effective_responses() → effective_responses_df
    ├── WorkflowEngine(effective_responses_df) → workflow_engine
    ├── compute_responsible_party() → responsible_parties dict
    ├── _precompute_focus_columns() → adds _visa_global, _days_to_deadline, _focus_priority ...
    ├── compute_focus_ownership() → adds _focus_owner, _focus_owner_tier
    └── returns RunContext (ctx)
    │
    ▼
app.py API class (exposed to JS via window.pywebview.api)
    ├── get_overview_for_ui()
    │       → get_dashboard_data()
    │           → compute_project_kpis(ctx)          [aggregator.py]
    │           → compute_monthly/weekly_timeseries(ctx) [aggregator.py]
    │           → compute_consultant_summary(ctx)     [aggregator.py]
    │           → compute_contractor_summary(ctx)     [aggregator.py]
    │           → apply_focus_filter(ctx)             [focus_filter.py]
    │       → adapt_overview(dashboard, app_state)    [ui_adapter.py]
    │       → window.OVERVIEW
    │
    ├── get_consultants_for_ui()
    │       → compute_consultant_summary(ctx)
    │       → adapt_consultants(raw)                  [ui_adapter.py]
    │       → window.CONSULTANTS
    │
    ├── get_contractors_for_ui()
    │       → compute_contractor_summary(ctx)
    │       → adapt_contractors_lookup/list(raw)      [ui_adapter.py]
    │       → window.CONTRACTORS, window.CONTRACTORS_LIST
    │
    ├── get_fiche_for_ui(consultant_name)
    │       → build_consultant_fiche(ctx, canonical)  [consultant_fiche.py]
    │       → window.FICHE_DATA
    │
    ├── get_contractor_fiche(contractor_code)
    │       → build_contractor_fiche(ctx, code)       [contractor_fiche.py]
    │       → (no global; loaded on-demand)
    │
    └── get_doc_details(consultant, filter_key)
            → inline reimplementation of _filter_for_consultant
              + _attach_derived + filter logic         [app.py lines 448-590]
            → drilldown document list (no global)
```

### Legacy path (retired — do NOT restore)

```
bet_report_merger.merge_bet_reports()
    ← RETIRED in data_loader.py (Step 8 / FLAT_GED_REPORT_COMPOSITION.md §8)
    ← Import is commented out: "DO NOT RESTORE"
    ← File still exists: src/reporting/bet_report_merger.py
    ← Replaced by: build_effective_responses() + report_memory.db composition
```

---

## 4. UI Element Mapping

### 4.1 Overview Page — `window.OVERVIEW`

| UI Element | Current Source File | Current Function | Current Data | Risk | Future Query Function | Bridge Required |
|---|---|---|---|---|---|---|
| Total docs (soumis) | `aggregator.py` | `compute_project_kpis` | `len(ctx.dernier_df)` — count of dernier-indice docs | LOW | `query_library.get_total_docs()` | YES — ops_df uses (numero,indice); dernier_df uses doc_id |
| Pending blocking | `aggregator.py` | `compute_project_kpis` | `by_visa_global["Open"]` — docs with no terminal visa | MEDIUM — computed per doc via workflow_engine loop | `query_library.get_open_docs()` | YES |
| Refusal rate | `ui_adapter.py` | `adapt_overview` | `(REF + SAS_REF docs) / total_docs` — document level | HIGH — semantic mismatch with step-level query_library | `query_library.get_status_breakdown()["rejection"] / total_steps` | YES (different unit) |
| Week number | `ui_adapter.py` | `adapt_overview` | `ctx.run_date` parsed as date → isocalendar | LOW | N/A (metadata) | NO |
| Data date string | `ui_adapter.py` | `adapt_overview` | `ctx.run_date` | LOW | N/A | NO |
| Run number | `data_loader.py` | `load_run_context` | `run_memory.db → latest COMPLETED run` | LOW | N/A | NO |
| Total docs delta | `ui_adapter.py` | `adapt_overview` | `None` — **NOT CONNECTED** | HIGH | Requires run-to-run comparison | NO |
| Pending blocking delta | `ui_adapter.py` | `adapt_overview` | `None` — **NOT CONNECTED** | HIGH | Requires run-to-run comparison | NO |
| Refusal rate delta | `ui_adapter.py` | `adapt_overview` | `None` — **NOT CONNECTED** | HIGH | Requires run-to-run comparison | NO |
| Best consultant (name, pass_rate) | `ui_adapter.py` | `adapt_overview` | Derived from `compute_consultant_summary` — highest (VSO+VAO)/called with ≥10 docs | LOW | `query_library.get_consultant_kpis()` | YES |
| Best consultant delta | `ui_adapter.py` | `adapt_overview` | `None` — **NOT CONNECTED** | HIGH | Requires run comparison | NO |
| Best contractor (name, pass_rate) | `ui_adapter.py` | `adapt_overview` | Derived from `compute_contractor_summary` — highest (VSO+VAO)/total with ≥10 docs | LOW | `query_library.get_consultant_kpis()` | YES |
| Visa flow: submitted | `aggregator.py` | `compute_project_kpis` | `total_docs_current = len(dernier_df)` | LOW | `get_total_docs()` | YES |
| Visa flow: answered (répondus) | `aggregator.py` | `compute_project_kpis` | `VSO + VAO + REF + SAS_REF + HM` doc counts | LOW | `get_status_breakdown()["total_decisive"]` | YES |
| Visa flow: VSO | `aggregator.py` | `compute_project_kpis` | `by_visa_global["VSO"]` | LOW | `get_status_breakdown()["approval"]` (approx) | YES |
| Visa flow: VAO | `aggregator.py` | `compute_project_kpis` | `by_visa_global["VAO"]` | LOW | same | YES |
| Visa flow: REF | `aggregator.py` | `compute_project_kpis` | `by_visa_global["REF"] + by_visa_global["SAS REF"]` | LOW | `get_status_breakdown()["rejection"]` | YES |
| Visa flow: pending | `aggregator.py` | `compute_project_kpis` | `by_visa_global["Open"]` | LOW | `get_open_docs()` | YES |
| Visa flow: on_time | `ui_adapter.py` | `adapt_overview` | `None` — **NOT CONNECTED** | HIGH — UI shows "délais non calculés" | `get_pending_steps()` minus overdue | NO |
| Visa flow: late | `ui_adapter.py` | `adapt_overview` | `None` — **NOT CONNECTED** | HIGH | `get_overdue_steps()` | NO |
| Weekly/monthly chart | `aggregator.py` | `compute_monthly_timeseries` / `compute_weekly_timeseries` | Per-month/week: vso/vao/ref/open doc counts from dernier_df via workflow_engine | LOW | No direct equivalent (time-series not in query_library) | NO (different granularity) |
| Focus: total focused | `focus_filter.py` | `apply_focus_filter` | `focus_result.stats["focused_count"]` | LOW | N/A (focus_filter handles this) | NO |
| Focus: P1/P2/P3/P4 counts | `focus_filter.py` | `apply_focus_filter` | Pre-computed `_focus_priority` on dernier_df | LOW | N/A | NO |
| Focus: by_consultant breakdown | `focus_filter.py` | `apply_focus_filter` | `focus_result.stats["by_consultant"]` | LOW | N/A | NO |
| Project stats: total_consultants | `aggregator.py` | `compute_project_kpis` | Unique approver_canonical in responses_df (excl SAS/Sollicitation) | LOW | `get_consultant_kpis().shape[0]` | YES |
| Project stats: total_contractors | `aggregator.py` | `compute_project_kpis` | `len(ctx.gf_sheets)` — GF sheet count | LOW | Not in query_library | NO |
| Project stats: avg_days_to_visa | `aggregator.py` | `compute_project_kpis` | Mean of (visa_date - created_at).days across completed docs | LOW | Not in query_library | NO |
| Project stats: docs_pending_sas | `aggregator.py` | `compute_project_kpis` | Rows where approver_raw=="0-SAS" AND PENDING | LOW | `get_status_breakdown()` + SAS filter | YES |
| System status (baseline, GED, GF, pipeline) | `app.py` | `get_app_state` | `run_memory.db` + file existence checks | LOW | N/A (infra metadata) | NO |
| Warnings list | `data_loader.py` | `load_run_context` | `ctx.warnings` (populated during load) | LOW | N/A | NO |

### 4.2 Consultants Page — `window.CONSULTANTS`

| UI Element | Current Source File | Current Function | Current Data | Risk | Future Query Function | Bridge Required |
|---|---|---|---|---|---|---|
| Consultant cards (all) | `aggregator.py` + `ui_adapter.py` | `compute_consultant_summary` + `adapt_consultants` | `ctx.responses_df` grouped by `approver_canonical` | LOW | `query_library.get_consultant_kpis()` | YES |
| name, role, group | `consultant_fiche.py` + `ui_adapter.py` | `ROLE_BY_CANONICAL`, `_CONSULTANT_GROUPS` | **HARDCODED** in Python files | LOW (intentional) | Stays hardcoded | NO |
| total (docs_called) | `aggregator.py` | `compute_consultant_summary` | `len(grp[date_status_type != "NOT_CALLED"])` | LOW | `get_consultant_kpis()["assigned_steps"]` | YES |
| answered | `aggregator.py` | `compute_consultant_summary` | `len(grp[date_status_type == "ANSWERED"])` | LOW | `get_consultant_kpis()["answered"]` | YES |
| pending | `aggregator.py` | `compute_consultant_summary` | `called - answered` | LOW | `get_consultant_kpis()["pending"]` | YES |
| pass_rate (taux de conformité) | `ui_adapter.py` | `adapt_consultants` | `round(response_rate * 100)` where response_rate = answered/called | MEDIUM — "conformité" actually means "réponse" rate, not quality | `get_consultant_kpis()["approval_pct"]` (more accurate) | YES |
| VSO / VAO / REF / HM counts | `aggregator.py` | `compute_consultant_summary` | `status_clean` value counts on effective_responses_df | LOW | `get_consultant_kpis()` (approval_pct × answered) | YES |
| avg_response_days | `aggregator.py` | `compute_consultant_summary` | Mean of (date_answered - doc.created_at).days | LOW | `get_consultant_kpis()["avg_delay_days"]` | YES |
| open_blocking | `aggregator.py` | `compute_consultant_summary` | PENDING steps where workflow_engine.visa_global is None | LOW | `get_consultant_kpis()["overdue"]` (approx, not identical) | YES |
| focus_owned | `focus_filter.py` + `aggregator.py` | `apply_focus_filter` + `compute_consultant_summary` | Count of focused_df rows where consultant appears in `_focus_owner` | LOW | N/A | NO |
| trend (sparkline) | `ui_adapter.py` | `adapt_consultants` | `[]` — **NOT CONNECTED** | HIGH | Requires historical run data | NO |
| s1_label / s2_label / s3_label | `aggregator.py` | `compute_consultant_summary` | From `_CONSULTANT_STATUS_VOCAB` (hardcoded) | LOW | Stays hardcoded | NO |

### 4.3 Consultant Fiche — `window.FICHE_DATA`

| UI Element | Current Source File | Current Function | Current Data | Risk | Future Query Function | Bridge Required |
|---|---|---|---|---|---|---|
| header.total | `consultant_fiche.py` | `_build_header` | `len(docs)` from `_filter_for_consultant()` — inner-join of dernier_df × responses_df for this consultant | LOW | `get_actor_fiche()["assigned_steps"]` | YES |
| header.answered | `consultant_fiche.py` | `_build_header` | Docs with `_status_for_consultant` in {s1, s2, s3, HM} | LOW | `get_actor_fiche()["answered"]` | YES |
| header.s1_count / s2_count / s3_count | `consultant_fiche.py` | `_build_header` | Status counts from effective_responses_df | LOW | `get_actor_fiche()["approval_pct"]` × answered | YES |
| header.hm_count | `consultant_fiche.py` | `_build_header` | Count of HM status from effective_responses_df | LOW | `get_actor_fiche()["hm_pct"]` × answered | YES |
| header.open_count | `consultant_fiche.py` | `_build_header` | Count of `_is_open == True` rows | LOW | `get_actor_fiche()["pending"]` | YES |
| header.open_late | `consultant_fiche.py` | `_build_header` | Open AND `_on_time == False` (deadline < data_date) | LOW | `get_actor_fiche()["overdue"]` | YES |
| header.open_blocking | `consultant_fiche.py` | `_build_header` | Open AND no visa_global (workflow_engine check per doc) | LOW | `get_actor_fiche()["pending"]` (approx) | YES |
| header.open_blocking_ok | `consultant_fiche.py` | `_build_header` | Blocking AND on_time | LOW | Not directly | YES |
| header.open_blocking_late | `consultant_fiche.py` | `_build_header` | Blocking AND NOT on_time | LOW | `get_actor_fiche()["overdue"]` | YES |
| header.week_num / data_date_str | `consultant_fiche.py` | `_resolve_data_date` | `ctx.data_date` (from GED Détails sheet) | LOW | N/A | NO |
| week_delta (all fields) | `consultant_fiche.py` | `_build_week_delta` | Diff between stats at data_date vs data_date-7 | LOW | Not in query_library | NO |
| bloc1 (monthly/weekly timeline) | `consultant_fiche.py` | `_build_bloc1` / `_build_bloc1_weekly` | Per-month/week: new docs, closed docs, s1/s2/s3/HM/open counts | LOW | Not in query_library (time-series) | NO |
| bloc2 (cumulative chart series) | `consultant_fiche.py` | `_build_bloc2` | Cumulative sums from bloc1 | LOW | Not in query_library | NO |
| bloc3 (per-lot breakdown table) | `consultant_fiche.py` | `_build_bloc3` | Grouped by `_gf_sheet` → VSO/VAO/REF/HM/open per lot | LOW | Not in query_library | NO |
| non_saisi badge | `consultant_fiche.py` | `_build_non_saisi` | `response_source == "PDF_REPORT"` count from effective_responses_df | LOW | `get_effective_source_mix()["GED+REPORT_STATUS"]` (similar intent, different granularity) | YES |
| focus_priority strip | `consultant_fiche.py` | `build_consultant_fiche` | Filtered `focus_result.priority_queue` for this consultant | LOW | N/A | NO |
| MOEX SAS fiche (all fields) | `consultant_fiche.py` | `build_sas_fiche` | `responses_df[approver_raw == "0-SAS"]` merged with dernier_df | LOW | Partially: `get_consultant_kpis()` for 0-SAS | YES |

### 4.4 Contractor Fiche (on-demand, no global)

| UI Element | Current Source File | Current Function | Current Data | Risk | Future Query Function | Bridge Required |
|---|---|---|---|---|---|---|
| header (lots, buildings, total_submitted, total_current) | `contractor_fiche.py` | `build_contractor_fiche` | `docs_df[emetteur == code]` | LOW | `get_doc_lifecycle()` filtered by emetteur | YES |
| block1: submission timeline | `contractor_fiche.py` | `build_contractor_fiche` | Per-month new vs resubmissions from docs_df | LOW | Not in query_library | NO |
| block2: VISA result chart | `contractor_fiche.py` | `build_contractor_fiche` | Per-month visa_global from dernier_df via workflow_engine | LOW | Not in query_library | NO |
| block3: document table | `contractor_fiche.py` | `build_contractor_fiche` | Per-doc: numero, indice, titre, sas_result, visa_global, dates | LOW | `get_doc_lifecycle()` filtered by emetteur | YES |
| block4: quality metrics | `contractor_fiche.py` | `build_contractor_fiche` | sas_refusal_rate, avg_revision_cycles, avg_days_to_visa | LOW | Not directly | NO |
| focus_summary | `contractor_fiche.py` | `build_contractor_fiche` | Focus ownership count from `_focus_owner_tier == "CONTRACTOR"` | LOW | N/A | NO |

### 4.5 Drilldown Drawer (per click, from `app.py.get_doc_details`)

| UI Element | Current Source File | Current Function | Current Data | Risk | Future Query Function | Bridge Required |
|---|---|---|---|---|---|---|
| Document list (per filter) | `app.py` | `get_doc_details` | Re-calls `_filter_for_consultant` + `_attach_derived` — inline 140-line reimplementation | HIGH — duplicates consultant_fiche.py logic with no shared test | `get_actor_fiche()["pending_docs"]` + `get_doc_fiche()` | YES |
| numero, indice per row | `app.py` | `get_doc_details` | `docs_df["numero"]`, `docs_df["indice"]` | LOW | `get_doc_lifecycle()["numero"]`, `["indice"]` | NO (already uses numero/indice) |
| emetteur, titre, lot | `app.py` | `get_doc_details` | From merged `dernier_df` | LOW | `get_doc_lifecycle()` | NO |
| date_soumission | `app.py` | `get_doc_details` | `docs_df["created_at"]` | LOW | `get_doc_lifecycle()["submittal_date"]` | NO |
| date_limite | `app.py` | `get_doc_details` | `responses_df["date_limite_resp"]` or `"date_limite"` | LOW | `get_doc_fiche()["step_details"][]["phase_deadline"]` | YES |
| remaining_days | `app.py` | `get_doc_details` | `(date_limite - data_date).days` | LOW | Derivable from `get_doc_fiche()` | YES |
| status | `app.py` | `get_doc_details` | `_status_for_consultant` — from `_attach_derived()` | HIGH — logic duplicated from consultant_fiche.py | `get_doc_fiche()["visa_global"]` (not identical) | YES |
| Drilldown xlsx export | `app.py` | `export_drilldown_xlsx` | Calls `get_doc_details()` then writes openpyxl | LOW | N/A | NO |

### 4.6 Runs Page (from `get_all_runs()`)

| UI Element | Current Source File | Current Function | Current Data | Risk | Future Query Function | Bridge Required |
|---|---|---|---|---|---|---|
| Run list (number, status, date, artifacts) | `run_explorer.py` | `get_all_runs` | `run_memory.db` SELECT * | LOW | N/A (infrastructure data) | NO |
| Run summary | `run_explorer.py` | `get_run_summary` | `run_memory.db` + summary_json | LOW | N/A | NO |
| Run comparison | `run_explorer.py` | `compare_runs` | Cross-run delta from `run_memory.db` | LOW | N/A | NO |

### 4.7 Executer Page (pipeline control)

| UI Element | Current Source | Risk | Notes |
|---|---|---|---|
| Run mode selection / validation | `app.py` → `run_orchestrator.validate_run_inputs` | LOW | Pipeline control, not reporting |
| Pipeline status (progress bar) | `app.py._pipeline_status` | LOW | Polling every 500ms |
| File detection / selection | `app.py._detect_file()` + `select_file()` | LOW | File system operations |
| Team Version export button | `app.py.export_team_version()` | LOW | Copies FINAL_GF artifact |

---

## 5. Identity Bridge Requirement

### Two identity systems in use

**System A: doc_id (UUID)**
- Source: Generated by pipeline during normalization (`normalize_docs`)
- Location: `ctx.dernier_df["doc_id"]`, `ctx.responses_df["doc_id"]`, `focus_result.focused_doc_ids`
- Scope: Pipeline-session-specific. Same document gets a different doc_id on each pipeline run.
- Used by: `aggregator.py`, `consultant_fiche.py`, `contractor_fiche.py`, `focus_filter.py`, `focus_ownership.py`, `data_loader.py`, `query_library.get_actor_fiche()`, `query_library.get_effective_source_mix()`

**System B: (numero, indice) / doc_key**
- Source: GED fields as extracted by `read_raw.read_ged()` and carried through `normalize_docs`
- Format: `doc_key = f"{numero}_{indice}"` (e.g., `"248000_A"`)
- Scope: Stable across pipeline runs. GED-visible. Never changes for a given document version.
- Used by: `flat_ged_ops_df` (ALL columns), `query_library` "ops" functions, drilldown UI response (`numero`, `indice` fields), contractor block3 table

### Where the UI currently uses each system

The JSX layer itself never sees doc_id. It identifies:
- Consultants by `canonical_name` (string)
- Documents in drilldown by `numero` + `indice` (System B)
- Focus queue items by `doc_id` (in `priority_queue` payload) — BUT only for backend calls, not displayed

The Python backend uses doc_id (System A) for all run-time filtering and workflow operations. `numero`/`indice` are re-exposed to the JS only at the drilldown response level.

### Bridge object required for Step 11

The parity harness (Step 11) must cross-reference `aggregator.py` outputs (doc_id based) with `query_library.py` outputs (doc_key based). The bridge must be built from `ctx.dernier_df`:

```python
# Build in parity harness from ctx.dernier_df
id_bridge = {}
for _, row in ctx.dernier_df.iterrows():
    doc_id = row["doc_id"]
    numero = str(row.get("numero_normalized", ""))
    indice  = str(row.get("indice", ""))
    doc_key = f"{numero}_{indice}"
    id_bridge[doc_id] = {
        "numero":  numero,
        "indice":  indice,
        "doc_key": doc_key,
    }

# Reverse: doc_key → doc_id (for dernier only — may be 1-to-many across runs)
doc_key_to_doc_id = {v["doc_key"]: k for k, v in id_bridge.items()}
```

**Where to build it:** In `scripts/parity_harness.py` (Step 11), after calling `load_run_context()`. Do NOT add it to `data_loader.py` or `query_library.py` — it is a harness-only concern.

**Important constraint:** `flat_ged_ops_df` may contain (numero, indice) pairs that do not appear in `ctx.dernier_df` if they are superseded indices. The bridge only covers dernier docs. Non-dernier docs are not in scope for UI comparison.

---

## 6. Deprecated / Dangerous UI Logic

### 6.1 Retired — safe, no action needed

| File | Function | Status | Evidence |
|---|---|---|---|
| `src/reporting/bet_report_merger.py` | `merge_bet_reports()` | **RETIRED** — file exists, function NOT called | `data_loader.py` line 24-26: import commented with "DO NOT RESTORE". `app.py` never imports it. |

### 6.2 Dangerous — action needed before Step 11

| Risk | Location | Description |
|---|---|---|
| **Duplicated derivation logic** | `app.py:get_doc_details()` (lines 448–590) | Re-implements `_filter_for_consultant()`, `_attach_derived()`, `_resolve_status_labels()` inline. ~140 lines of logic that can silently diverge from `consultant_fiche.py`. Must be compared against fiche output in Step 11. |
| **`refus_rate` semantic mismatch** | `ui_adapter.py:adapt_overview()` line 108 | `_safe_pct(ref + sas_ref, total_docs)` counts DOCUMENTS with terminal REF/SAS_REF visa. `query_library.get_status_breakdown()["rejection"]` counts STEPS. These will produce different numbers. Step 11 must document the semantic difference explicitly, not treat it as a bug. |
| **`pass_rate` label misleading** | `ui_adapter.py:adapt_consultants()` | `pass_rate = round(response_rate * 100)` where `response_rate = answered/called`. Displayed as "taux de conformité" but actually measures response completion rate, not quality (VSO+VAO / total). |
| **`on_time` / `late` hardcoded None** | `ui_adapter.py:adapt_overview()` | `visa_flow.on_time = None`, `visa_flow.late = None`. UI displays "délais non calculés" branch gracefully. Step 11 must assert these remain None until wired. |
| **All `*_delta` fields hardcoded None** | `ui_adapter.py:adapt_overview()` and `adapt_consultants()` | `total_docs_delta`, `pending_blocking_delta`, `refus_rate_delta`, `best_consultant.delta`, all consultant `trend` arrays are None/[]. Not bugs — documented as "requires run comparison". |
| **`docs_pending_moex` hardcoded 0** | `contractor_fiche.py:build_contractor_fiche()` line 327 | `"docs_pending_moex": 0` with comment "Would need responsible_party computation". Not displayed in current UI but is in the API response. |
| **Hardcoded consultant mappings** | `consultant_fiche.py` lines 28–128 | `CONSULTANT_DISPLAY_NAMES`, `ROLE_BY_CANONICAL`, `BET_MERGE_KEYS`, `COMPANY_TO_CANONICAL`, `CONTRACTOR_REFERENCE` are hardcoded from 2026-04-20 analysis. Any new consultant or contractor code change requires a code edit. This is intentional but creates maintenance risk. |

### 6.3 Dead code — not dangerous, but should not be confused with active runtime

| File | Description |
|---|---|
| `ui/src/App.jsx` | Legacy Vite-based app root. Not loaded by `app.py`. |
| `ui/src/components/ConsultantFiche.jsx` | Legacy Vite-based fiche component. Superseded by `ui/jansa/fiche_base.jsx`. |
| `ui/dist/index.html` + `ui/dist/assets/index-BNCEp8m7.js` | Compiled Vite build artifact. Not loaded by `app.py`. |
| `JANSA Dashboard - Standalone.html` (root) | Archived standalone bundle. Not referenced by `app.py._resolve_ui()`. |

---

## 7. Query Library Adoption Plan

`query_library.py` uses `QueryContext` (flat_ged_ops_df + effective_responses_df), not `RunContext`. To adopt it from the UI path, a `QueryContext` must be assembled from `ctx`:

```python
# In app.py or reporting/data_loader.py
from query_library import QueryContext
qctx = QueryContext(
    flat_ged_ops_df=stage_read_flat_output,       # from PipelineState
    effective_responses_df=ctx.responses_df,       # already the effective version
)
```

**Problem:** `flat_ged_ops_df` is produced by `stage_read_flat.py` during the pipeline run and stored as an artifact, but `load_run_context()` does NOT load it. It would need to be loaded from the `flat_ged/` artifact or from the pipeline state. This requires a new loader step.

### Priority adoption order for Step 11

| UI Area | Query Library Function | Priority | Notes |
|---|---|---|---|
| Overview: total_docs | `get_total_docs(qctx)` | P1 | Direct comparison vs `len(ctx.dernier_df)` |
| Overview: pending_blocking | `get_open_docs(qctx)` | P1 | Direct comparison vs `by_visa_global["Open"]` |
| Overview: visa distribution | `get_status_breakdown(qctx)` | P1 | Note semantic difference (steps vs docs) |
| Overview: overdue count | `get_overdue_steps(qctx)` | P1 | Step 11 primary comparison point |
| Consultant list: metrics | `get_consultant_kpis(qctx)` | P2 | Per-approver comparison |
| Consultant fiche: open/answered | `get_actor_fiche(qctx, actor)` | P2 | Header KPI comparison |
| Provenance: non_saisi / report upgrades | `get_effective_source_mix(qctx)` | P2 | Compare with non_saisi badge count |
| Document detail drilldown | `get_doc_fiche(qctx, doc_key)` | P3 | Semantic comparison only — units differ |
| Queue engine (easy_wins, conflicts) | `get_easy_wins(qctx)`, `get_conflicts(qctx)` | P3 | No current UI equivalent — validation only |

---

## 8. Step 11 UI Parity Harness Plan

**Goal:** `scripts/ui_parity_harness.py` — output `output/ui_parity_report.xlsx`

### Comparison targets

**C1 — Overview KPIs**
- `window.OVERVIEW.total_docs` vs `query_library.get_total_docs(qctx)`
- `window.OVERVIEW.pending_blocking` vs `query_library.get_open_docs(qctx)` 
- `window.OVERVIEW.visa_flow.answered` vs `query_library.get_answered_steps(qctx)`
- Overdue steps: via `query_library.get_overdue_steps(qctx)` vs no current UI equivalent (new metric)
- Note: refusal rate comparison requires semantic normalization (document-level vs step-level)

**C2 — Consultant summary list**
- For each consultant in `window.CONSULTANTS`: compare `answered`, `pending`, `open_blocking` vs `get_consultant_kpis(qctx)` row for same `approver_canonical`
- Expected divergences: `pass_rate` (response rate vs approval rate), `open_blocking` (workflow_engine vs is_blocking flag)

**C3 — Consultant fiche header**
- For each consultant: call `build_consultant_fiche(ctx, name)` → compare `header.open_count`, `header.answered`, `header.s1_count` vs `get_actor_fiche(qctx, name)["pending"]`, `["answered"]`, `["approval_pct"]`
- Expected divergences: fiche uses dernier-only docs joined with responses; actor_fiche covers all responses

**C4 — Project visa distribution**
- `compute_project_kpis(ctx)["by_visa_global"]` vs `get_status_breakdown(qctx)` — document the semantic gap

**C5 — Focus queue**
- `focus_result.stats["p1_overdue"]` vs `get_overdue_steps(qctx)` — document the gap (focus uses dernier+ownership, query_library uses all steps)

**C6 — Report source / provenance**
- `compute_consultant_summary` non_saisi counts vs `get_effective_source_mix(qctx)` — aggregate comparison

**C7 — Identity bridge validation**
- For each doc_id in `ctx.dernier_df`: verify the corresponding doc_key exists in `flat_ged_ops_df`
- Count mismatches (pipeline alignment check)

### Harness architecture

```
scripts/ui_parity_harness.py
    1. load_run_context(BASE_DIR) → ctx
    2. Build QueryContext(flat_ged_ops_df=..., effective_responses_df=ctx.responses_df)
       [flat_ged_ops_df loaded from run artifact or re-built from stage_read_flat]
    3. Build id_bridge from ctx.dernier_df
    4. Run C1..C7 comparisons
    5. For each comparison: record (metric, ui_value, ql_value, delta, verdict)
       verdict: MATCH | SEMANTIC_GAP | REAL_DIVERGENCE | NOT_CONNECTED
    6. Write output/ui_parity_report.xlsx with one sheet per comparison target
    7. Print summary: REAL_DIVERGENCE count (gate condition)
```

**Gate condition (GATE 3):** REAL_DIVERGENCE = 0, or all divergences reviewed and classified as SEMANTIC_GAP / NOT_CONNECTED.

---

## 9. Open Questions / Risks

1. **`flat_ged_ops_df` loading in UI path.** `load_run_context()` does not load the flat GED operations DataFrame. To build a `QueryContext` in the parity harness, `flat_ged_ops_df` must be loaded from the run artifact registry. Confirm the artifact type name (`FLAT_GED_OPS` or similar) in `run_memory.db` before writing the harness.

2. **Semantic gap in `pass_rate`.** The UI displays `docs_answered / docs_called` as "taux de conformité" but this is a completion rate, not a quality rate. `query_library.get_consultant_kpis()["approval_pct"]` is the true quality measure. Step 11 must classify this as SEMANTIC_GAP, not REAL_DIVERGENCE.

3. **`_focus_priority` vs `date_status_type == "PENDING_LATE"`.** Focus P1 count uses pre-computed `_focus_priority == 1` (deadline < data_date on ANY pending step). `get_overdue_steps()` counts steps where `date_status_type == "PENDING_LATE"`. These may differ because focus applies dernier-only filtering. Classify as SEMANTIC_GAP unless counts diverge significantly.

4. **Non-dernier docs in flat_ged_ops_df.** `query_library` operates on ALL document versions (not just dernier). `ctx.dernier_df` covers only the latest indice per numero. Total docs reported by `get_total_docs(qctx)` may therefore exceed `len(ctx.dernier_df)`. This is expected and must be documented in Step 11 as SEMANTIC_GAP.

5. **MOEX SAS fiche.** `build_sas_fiche()` has a different structure than standard fiche (bloc4_sas instead of standard bloc3). No `query_library` function currently addresses SAS-specific metrics. Step 11 should skip SAS fiche parity for now.

---

## Appendix: Files Inspected

```
app.py
main.py
src/reporting/data_loader.py
src/reporting/aggregator.py
src/reporting/consultant_fiche.py
src/reporting/contractor_fiche.py
src/reporting/bet_report_merger.py
src/reporting/focus_filter.py
src/reporting/focus_ownership.py
src/reporting/ui_adapter.py
src/query_library.py
ui/jansa-connected.html
ui/jansa/data_bridge.js
ui/jansa/overview.jsx
ui/jansa/consultants.jsx
ui/jansa/fiche_page.jsx (header)
ui/src/App.jsx (existence check)
JANSA Dashboard - Standalone.html (existence check)
docs/ (directory listing)
```

---

## Appendix: Step 10 Verdict

| Success Criterion | Status |
|---|---|
| Every active UI path identified | ✅ One active path: PyWebView + `ui/jansa-connected.html` |
| Every displayed metric has a future query source | ✅ Mapped above — time-series blocks explicitly deferred |
| Identity bridge requirement is clear | ✅ doc_id ↔ doc_key bridge defined; build location: parity harness only |
| Deprecated UI logic is listed | ✅ bet_report_merger retired; get_doc_details duplication flagged |
| Step 11 can be written directly from this document | ✅ Section 8 provides the complete harness plan |

**Step 10: COMPLETE. Step 11 can proceed.**
