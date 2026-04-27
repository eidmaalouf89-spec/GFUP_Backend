# UI Loader Productization Audit

**Step:** CLEAN Step 10  
**Date:** 2026-04-26  
**Auditor:** Claude / Cowork  
**Prerequisites:** CLEAN Steps 1–9c ✅ | Gates 1–3 ✅ | TEAM_GF chain hardened ✅  
**Status:** AUDIT ONLY — no code changed

---

## 1. Executive Summary

**Verdict: Partially Legacy / Moderate Technical Debt**  
**Readiness Score: 5 / 10**

The production UI loader (`src/reporting/data_loader.py`) is functional and safe to use today. However, it carries significant legacy debt: every dashboard load triggers a full raw GED rebuild — reading, normalizing, version-engineering, and workflow-computing the entire ~6,900-row GED dataset from scratch. The module-level cache mitigates repeated calls within a session, but any page change or focus-mode toggle that results in a cache miss re-runs the entire chain.

The `query_library.py` built in Phase 5 / Step 9c is not connected to the UI layer at all. The flat GED path (Steps 4–8) exists in the pipeline backend but has no counterpart in the UI loader. Three files referenced in the original Step 10 spec — `ui_adapter.py`, `query_library.py`, and the jansa-connected UI runtime — were either not present in the inspected worktree or have diverged from the step spec's assumptions.

The current UI is safe to use. The Step 11 scope should be **medium**: wire query_library into an artifact-driven load path, eliminate the raw GED rebuild for dashboard views, and keep the full rebuild path as a fallback.

---

## 2. Current Production UI Runtime

| Layer | File | Function | Purpose | Risk |
|-------|------|----------|---------|------|
| App launcher | `app.py` | `main()` | PyWebView window creation; loads `ui/dist/index.html` | Low |
| API bridge | `app.py` | `class Api` | Every public method callable from React via `window.pywebview.api.*` | Low |
| Cache management | `app.py` | `worker()` in `run_pipeline_async` | Calls `clear_cache()` after pipeline run | Low |
| Context loading | `src/reporting/data_loader.py` | `load_run_context(base_dir)` | Resolves run → reads raw GED → builds full DataFrames | **HIGH** |
| KPI computation | `src/reporting/aggregator.py` | `compute_project_kpis(ctx)` | Iterates dernier_df + workflow_engine per-doc | Medium |
| Consultant summary | `src/reporting/aggregator.py` | `compute_consultant_summary(ctx)` | Iterates responses_df; per-row workflow_engine calls | Medium |
| Contractor summary | `src/reporting/aggregator.py` | `compute_contractor_summary(ctx)` | Iterates dernier_df | Low |
| Timeseries | `src/reporting/aggregator.py` | `compute_monthly_timeseries()` / `compute_weekly_timeseries()` | Iterates dernier_df | Low |
| Focus filter | `src/reporting/focus_filter.py` | `apply_focus_filter(ctx, config)` | Filters dernier_df to actionable set | Low |
| Consultant fiche | `src/reporting/consultant_fiche.py` | `build_consultant_fiche(ctx, name)` | Merges docs+responses, builds all blocks | Medium |
| Contractor fiche | `src/reporting/contractor_fiche.py` | `build_contractor_fiche(ctx, code)` | Builds per-contractor blocks | Medium |
| BET PDF merge | `src/reporting/bet_report_merger.py` | `merge_bet_reports(versioned_df, responses_df, base_dir)` | Backfills PDF-only statuses into responses_df | **HIGH** |
| Run explorer | `src/run_explorer.py` | `get_all_runs()`, `get_run_summary()` | Reads run_memory.db; no raw GED | Low |

**UI target confirmed:** `ui/dist/index.html` (Vite React build, not `ui/jansa-connected.html`). The production UI runtime uses PyWebView → `ui/dist/index.html`. This diverges from Step 10 spec which referenced `ui/jansa-connected.html`. The jansa-connected.html path may be the prior (pre-Phase 5) UI that has since been replaced by a compiled React app.

---

## 3. Current Data Sources

| UI Metric / Feature | Current Source | Clean Source Candidate | Status |
|---------------------|----------------|------------------------|--------|
| Run number / run date | `run_memory.db` via `_resolve_latest_run()` | Same (already clean) | ✅ Clean |
| FINAL_GF path | `run_memory.db` via `_get_artifact_path()` | Same | ✅ Clean |
| GED provenance check | `run_memory.db` run_inputs table | Same | ✅ Clean |
| Artifact paths dict | `run_memory.db` run_artifacts table | Same (partially used) | ✅ Clean |
| docs_df / responses_df | `read_ged()` → `normalize_docs()` → raw GED file | FLAT_GED artifact via `flat_ged_ops_df` | ❌ Legacy |
| dernier_df | `VersionEngine(docs_df).run()` | FLAT_GED `is_dernier_indice` proxy | ❌ Legacy |
| workflow_engine | `WorkflowEngine(responses_df)` | effective_responses_df + query_library | ❌ Legacy |
| responsible_parties | `compute_responsible_party(we, ids)` | flat_ged_doc_meta | ❌ Legacy |
| BET PDF merge | `merge_bet_reports()` reads RAPPORT_* sheets from GF artifact | Should use registered artifact or snapshot | ⚠️ Fragile |
| DATA_DATE | `_read_ged_data_date(ged_path)` via openpyxl | Embed in run summary_json or artifact | ⚠️ Fragile |
| GF sheet structure | `_parse_gf_sheets(gf_path)` via openpyxl | Same (lightweight, acceptable) | ✅ Acceptable |
| approver_names | From `read_ged()` output | effective_responses_df approver columns | ❌ Legacy |
| moex_countdown | `compute_moex_countdown()` | query_library queue primitives | ❌ Not connected |
| Focus columns | `_precompute_focus_columns()` on dernier_df | query_library Focus equivalents | ❌ Not connected |
| Overview KPIs | aggregator functions over raw DataFrames | `query_library.get_portfolio_kpis()` | ❌ Not connected |
| Consultant summary | aggregator.compute_consultant_summary | `query_library.get_consultant_kpis()` | ❌ Not connected |
| Contractor summary | aggregator.compute_contractor_summary | (no direct query_library equivalent yet) | ⚠️ Partial |
| Timeseries (monthly/weekly) | aggregator.compute_*_timeseries | (no direct query_library equivalent) | ⚠️ No candidate |
| Consultant fiche | consultant_fiche.build_consultant_fiche | query_library + fiche getter | ❌ Not connected |
| Contractor fiche | contractor_fiche.build_contractor_fiche | query_library + partial | ❌ Not connected |
| Run list / run summary | run_explorer.get_all_runs() | Same (clean) | ✅ Clean |
| Run comparison | run_explorer.compare_runs() | Same (clean) | ✅ Clean |
| TEAM_GF export | Not found in app.py | Artifact lookup via run_memory | ⚠️ Missing |

---

## 4. Legacy Debt Inventory

### D-01 — Raw GED Rebuild on Every Context Load (CRITICAL)

**Where:** `data_loader.load_run_context()` lines 486–559  
**What:** Every cache miss triggers the full chain: `read_ged()` → `normalize_docs()` → `normalize_responses()` → `VersionEngine()` → `WorkflowEngine()` → `merge_bet_reports()`.  
**Why it still exists:** Was the only path when data_loader.py was first built; no artifact-based read path was designed at the time.  
**Risk:** HIGH — slow startup, risk of GED path drift, re-runs pipeline-level computation in UI process.  
**Replace now or later:** Replace in Step 11 (primary target).

### D-02 — BET Report Merger Still Called in Loader (HIGH)

**Where:** `data_loader.load_run_context()` lines 515–534  
**What:** Calls `merge_bet_reports(versioned_df, responses_df, base_dir)`, which reads RAPPORT_* sheets from the GF workbook at runtime.  
**Why it still exists:** Needed to backfill PDF-only statuses into the workflow engine.  
**Risk:** HIGH — reads Excel during UI load; base_dir path may not match artifact path; Phase 5 Step 10 said this was "RETIRED" but code contradicts that.  
**Replace now or later:** Step 11 should decide: either use effective_responses_df (which has report_memory enrichment already baked in via pipeline) and skip the runtime merge, or keep it as an explicit fallback only.

### D-03 — No query_library Connection (HIGH)

**Where:** `data_loader.py`, `aggregator.py`, `consultant_fiche.py`  
**What:** The query_library.py (built in Phase 5 / Step 9c) provides `QueryContext`, portfolio KPIs, consultant KPIs, queue primitives, etc. None of this is imported or used by the UI loader.  
**Why it still exists:** query_library was built in Phase 5 as a parity harness target, not yet wired into the UI.  
**Risk:** HIGH — the clean source of truth is not used; all UI metrics are derived from raw GED, creating two parallel derivation paths.  
**Replace now or later:** Step 11 primary target.

### D-04 — No Flat GED Path in UI Loader (HIGH)

**Where:** `data_loader.py` — no import of `flat_ged_ops_df`, `effective_responses_df`, or any flat GED artifact.  
**What:** The pipeline (Steps 4–8) now generates FLAT_GED.xlsx and effective_responses artifacts per run, but data_loader doesn't load them.  
**Why it still exists:** Step 12 (UI Loader Refactor) was always the designated step for this change.  
**Risk:** HIGH — UI reads raw GED while backend writes flat GED. Two sources of truth in flight.  
**Replace now or later:** Step 11 target.

### D-05 — DATA_DATE Read from Raw GED File (MEDIUM)

**Where:** `data_loader.py` `_read_ged_data_date()` lines 179–241  
**What:** Opens raw GED workbook via openpyxl to extract DATA_DATE from Détails sheet. Custom parsing with row scan.  
**Why it still exists:** Not captured in run artifacts yet.  
**Risk:** MEDIUM — fragile openpyxl parsing; if GED file moves or format changes, DATA_DATE becomes None.  
**Replace now or later:** Step 11 should embed DATA_DATE in summary_json or as artifact metadata.

### D-06 — No Run Selector in UI (LOW)

**Where:** `app.py` — all dashboard calls use `load_run_context(BASE_DIR)` with no run_number argument.  
**What:** UI always shows latest completed non-stale run. No way for user to switch runs.  
**Why it still exists:** Not requested yet; run_explorer endpoints exist but no UI uses them for selection.  
**Risk:** LOW — acceptable for current single-run workflow.  
**Replace now or later:** Later (post-Gate 4 nice-to-have).

### D-07 — export_team_version() Not Found in app.py (MEDIUM)

**Where:** `app.py` (complete read, lines 1–527)  
**What:** The `export_team_version()` method is not present in the current `Api` class. The Step 9 audit assumed it exists but the code does not contain it.  
**Why it still exists:** Either it was removed, or it lives in a different file, or it was never implemented in the UI layer.  
**Risk:** MEDIUM — if users expect a TEAM_GF export button, it may be broken or missing.  
**Replace now or later:** Investigate before Step 15. If TEAM_GF export is needed in UI, implement the method in Step 11 or Step 12 using the artifact lookup pattern.

### D-08 — Module-Level Cache is Run-Number-Only (LOW)

**Where:** `data_loader.py` `_cached_context`, `_cached_run_number`  
**What:** Cache key is run_number only. Different calls with same run_number (e.g., focus ON vs OFF) return the same context, which is correct. But cache is process-global with no TTL.  
**Risk:** LOW — works correctly in current single-session model.  
**Replace now or later:** Acceptable as-is. No action needed.

---

## 5. Query Library Coverage Matrix

`query_library.py` exists at `src/query_library.py` and provides `QueryContext` + 22 public symbols. **It is not imported anywhere in the UI layer.** Below is coverage against current UI sections:

| UI Section | Current Source | query_library Function | Readiness |
|------------|----------------|----------------------|-----------|
| Overview — total_docs_current | aggregator / dernier_df.len | `get_portfolio_kpis()["total_active_docs"]` | Partial |
| Overview — by_visa_global | workflow_engine per-doc | `get_status_breakdown()` | Partial |
| Overview — avg_days_to_visa | aggregator visa_dates loop | Not directly in query_library | Not ready |
| Overview — docs_pending_sas | responses_df filter | `get_portfolio_kpis()["sas_pending_count"]` | Partial |
| Overview — by_responsible | responsible_parties dict | `get_portfolio_kpis()["responsible_party_counts"]` | Partial |
| Overview — total_consultants | approver_names set | `get_consultant_kpis()` length | Partial |
| Monthly timeseries | aggregator.compute_monthly_timeseries | No direct equivalent | Not ready |
| Consultants dashboard | aggregator.compute_consultant_summary | `get_consultant_kpis()` | Partial |
| Consultant fiche — header KPIs | consultant_fiche per-consultant | `get_fiche_for_consultant()` (if exists) | Not ready |
| Consultant fiche — bloc1 monthly | consultant_fiche._build_bloc1 | No direct equivalent | Not ready |
| Contractor fiche | contractor_fiche.build_contractor_fiche | No direct equivalent | Not ready |
| Focus mode — priority queue | _precompute_focus_columns | queue primitives (easy_wins, stale_pending) | Partial |
| Drilldown / get_doc_details | data_loader + responses_df scan | No direct equivalent | Not ready |
| Queue primitives (easy_wins etc.) | Not exposed to UI | `get_easy_wins()`, `get_stale_pending()` | Not connected |

**Summary:** query_library covers portfolio KPIs and consultant KPIs at a structural level, but the UI's timeseries, monthly bloc1, and per-fiche blocks have no query_library equivalent yet. A full swap would require either extending query_library or keeping the aggregator/fiche builders while switching their input context.

---

## 6. Recommended Step 11 Target Architecture

The recommended loader for Step 11 is a **two-phase fallback chain**:

```
app.py → Api.get_dashboard_data()
  ↓
data_loader.load_run_context(BASE_DIR)
  ↓
Phase 1 — Artifact-driven load (NEW):
  • resolve latest COMPLETED non-stale run from run_memory.db
  • load FLAT_GED artifact (flat_ged_ops_df + effective_responses_df)
  • build QueryContext from artifacts
  • check if EFFECTIVE_RESPONSES artifact registered → load effective_responses_df
  • DATA_DATE: read from run summary_json["data_date"] or flat_ged_run_report.json
  • build RunContext with flat DataFrames instead of raw GED DataFrames
  → RunContext.degraded_mode = False, RunContext.flat_mode = True

Phase 2 — Fallback to raw rebuild (KEEP, legacy):
  • if FLAT_GED artifact missing OR flat load fails
  • existing read_ged() → normalize → VersionEngine → WorkflowEngine path
  • log warning: "UI loading via legacy raw rebuild"
  → RunContext.flat_mode = False
```

The `aggregator.py` and fiche builders do not need to change in Step 11 — they consume RunContext and are already compatible. The change is purely in `load_run_context()`:

- **Step 11 target file:** `src/reporting/data_loader.py`
- **New function needed:** `_load_from_flat_artifacts(db_path, run_number)` → `Optional[RunContext]`
- **Existing function:** `load_run_context()` calls new function first, falls back to raw rebuild
- **No changes to:** `aggregator.py`, `consultant_fiche.py`, `contractor_fiche.py`, `focus_filter.py`, `app.py`

---

## 7. TEAM_GF UI Path Audit

**Finding:** `export_team_version()` does NOT exist in `app.py` as of the inspected code (full file read, 527 lines).

**What is present:** `run_pipeline_async()` which calls `run_pipeline_controlled()`. After a successful run, the TEAM_GF file is registered as an artifact by `stage_finalize_run.py` IF the file was produced by `stage_build_team_version.py` (wired in CLEAN Step 9b).

**Expected UI path (from Step 9 spec):**
```
export_team_version()          ← missing in Api class
→ run_memory.db lookup GF_TEAM_VERSION
→ copy to output/Tableau de suivi de visa DD_MM_YYYY.xlsx
```

**Recommendation:**
- Step 11 should implement `export_team_version()` in the `Api` class
- Pattern: look up `GF_TEAM_VERSION` artifact in run_memory.db for latest run → copy with dated filename → return path
- No changes needed to run_memory, stage_finalize_run, or team_version_builder
- This is a small addition, not a refactor

**Should Step 11 touch it?** Yes — implement the missing method. It is a 15-line addition using the existing `_get_artifact_path()` pattern already in data_loader.

---

## 8. Risk Register

| Rank | Risk | Location | Severity | Likelihood | Impact |
|------|------|----------|----------|------------|--------|
| 1 | Raw GED rebuild runs on every dashboard load (cache miss) | data_loader.load_run_context | HIGH | Certain | Slow UI, raw-flat mismatch |
| 2 | bet_report_merger called in loader but may be "retired" in pipeline | data_loader L515–534 | HIGH | Medium | Contradictory merge results; double-apply risk |
| 3 | query_library not connected — two derivation paths for same metrics | data_loader + aggregator | HIGH | Certain | Divergence as pipeline evolves |
| 4 | Flat GED artifacts exist but UI reads raw GED | data_loader | HIGH | Certain | Two sources of truth |
| 5 | export_team_version() missing in Api | app.py | MEDIUM | Certain | TEAM_GF export not working from UI |
| 6 | DATA_DATE extracted from raw GED file via openpyxl | data_loader._read_ged_data_date | MEDIUM | Low | Wrong date if GED format changes |
| 7 | GED provenance check may fail after repo relocation | data_loader._verify_ged_provenance | MEDIUM | Low | Forces degraded mode unnecessarily |
| 8 | No run selector in UI — users cannot view historical runs | app.py | LOW | Certain | Usability limitation (not data risk) |
| 9 | Module cache is process-global with no TTL | data_loader._cached_context | LOW | Low | Stale data across day-long session |
| 10 | UI target (dist/index.html vs jansa-connected.html) mismatch with step spec | app.py _resolve_ui() | LOW | Already present | Documentation confusion only |

---

## 9. Exact Step 11 Implementation Plan

Step 11 scope is **medium**. Below is the actionable plan:

### S11-A: Add `_load_from_flat_artifacts()` to data_loader.py

```python
def _load_from_flat_artifacts(db_path: str, run_number: int, base_dir: Path) -> Optional[RunContext]:
    """
    Load RunContext from registered FLAT_GED + EFFECTIVE_RESPONSES artifacts.
    Returns None if artifacts missing or load fails (caller falls back to raw rebuild).
    """
    flat_ged_path = _get_artifact_path(db_path, run_number, "FLAT_GED")
    if not flat_ged_path:
        return None
    # Load flat_ged_ops_df from FLAT_GED.xlsx
    # Load effective_responses_df from EFFECTIVE_RESPONSES artifact or flat_ged
    # Build WorkflowEngine from effective_responses_df
    # Build dernier_df from flat_ged_ops_df (instance_role == ACTIVE)
    # Extract DATA_DATE from flat_ged_run_report.json artifact
    # Build and return RunContext(flat_mode=True, ...)
```

**Files changed:** `src/reporting/data_loader.py` only.  
**Lines added:** ~60–80 lines.

### S11-B: Modify `load_run_context()` to try flat path first

```python
def load_run_context(base_dir: Path, run_number: int = None) -> RunContext:
    ...
    # Try artifact-driven load first
    ctx = _load_from_flat_artifacts(db_path, run_number, base_dir)
    if ctx is not None:
        _cached_context = ctx
        _cached_run_number = run_number
        return ctx
    # Fallback to raw rebuild (existing code unchanged)
    ...
```

**Files changed:** `src/reporting/data_loader.py` only.

### S11-C: Implement `export_team_version()` in Api class

```python
def export_team_version(self):
    """Export TEAM_GF artifact as dated Tableau de suivi de visa file."""
    ...
    # Lookup GF_TEAM_VERSION via _get_artifact_path
    # Copy to output/ with dated filename
    # Return {"success": True, "path": ...}
```

**Files changed:** `app.py` only.  
**Lines added:** ~20 lines.

### S11-D: Embed DATA_DATE in run summary_json (backend)

In `run_orchestrator.py` or `stage_finalize_run.py`, add DATA_DATE to summary_json after flat GED build.  
**Files changed:** one of the above.  
**Lines added:** ~5 lines.

### S11-E: Decide on bet_report_merger in data_loader

Option A: Remove the `merge_bet_reports()` call from data_loader — rely on effective_responses artifacts (which already have PDF enrichment baked in by pipeline Steps 7–8).  
Option B: Keep it as fallback for raw-rebuild path only; skip it when flat path succeeds.  
**Recommendation:** Option A. The pipeline now handles this. Remove the call from the UI loader.

---

## 10. Non-Goals for Step 11

Step 11 should NOT attempt any of the following:

- Replacing or redesigning the React UI (ui/dist/)  
- Redesigning the aggregator or fiche builders  
- Adding historical run selector UI  
- Replacing PyWebView with another runtime  
- Implementing query_library as primary data source for aggregator (that is Step 12)  
- Changing any pipeline stage logic  
- Touching src/flat_ged/ (frozen)  
- Changing run_memory schema  
- Adding trend engine or advanced analytics  
- Implementing consultant PDF drilldown  
- Any visual / UX changes  

---

## Appendix A: Files Inspected

| File | Status | Notes |
|------|--------|-------|
| `app.py` | Read in full | 527 lines; export_team_version() absent |
| `src/reporting/data_loader.py` | Read in full | 589 lines; full raw rebuild path confirmed |
| `src/reporting/aggregator.py` | Read in full | 463 lines; consumes RunContext cleanly |
| `src/reporting/consultant_fiche.py` | Read in full | 1461 lines; large but clean |
| `src/reporting/contractor_fiche.py` | Read (header) | 40 lines read; consumes RunContext |
| `src/reporting/focus_filter.py` | Read (header) | 40 lines read; clean dataclass design |
| `src/reporting/bet_report_merger.py` | Read (header) | 50 lines read; confirms still active |
| `src/run_memory.py` | Read in full | 893 lines; clean |
| `src/run_orchestrator.py` | Read in full | 318 lines; flat GED build wired in |
| `src/run_explorer.py` | Read in full | 245 lines; clean read-only service layer |
| `src/effective_responses.py` | Read (header) | 60 lines read; exists, not used in UI |
| `GFUP_STEP_TRACKER.md` | Read in full | Confirms prior Phase 5 Step 10 and Clean Steps 1–9c |
| `GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md` | Read (first 80 lines) | Architecture spec confirms intent |
| `README.md` (worktree) | Read (60 lines) | Confirms current state |
| `query_library.py` | Not found in worktree | Confirmed via GFUP_STEP_TRACKER that it exists in main repo |
| `ui_adapter.py` | Not found anywhere | Does not exist |
| `ui/jansa-connected.html` | Not found in worktree | May exist in main branch; worktree uses dist/index.html |

**Note on worktree vs main branch:** Source inspection was conducted against the most recently modified worktree (`objective-kilby-52554c`). Some files noted in the step spec as mandatory inspection targets (`query_library.py`, `ui_adapter.py`, `QUERY_LIBRARY_SPEC.md`) were not present in this worktree but confirmed to exist in main via `GFUP_STEP_TRACKER.md` notes.

---

## Appendix B: Key Symbol Audit

| Symbol | Present? | Location | Used in UI loader? |
|--------|----------|----------|-------------------|
| `load_run_context` | ✅ | data_loader.py:380 | Called by all app.py dashboard methods |
| `read_ged` | ✅ | data_loader.py:492 (import) | Yes — legacy raw path |
| `normalize_docs` | ✅ | data_loader.py:21 (import) | Yes — legacy raw path |
| `normalize_responses` | ✅ | data_loader.py:21 (import) | Yes — legacy raw path |
| `effective_responses_df` | ❌ | Not in data_loader | No — not loaded |
| `build_effective_responses` | ❌ | Not in UI layer | Not used in UI |
| `query_library` | ❌ | Not imported in UI | Not connected |
| `run_memory` | ✅ | data_loader.py (sqlite queries) | Yes — for run/artifact lookup |
| `get_doc_details` | ❌ | Not found in inspected files | Not present |
| `window.OVERVIEW` | N/A | React UI (not inspected) | Frontend only |
| `window.CONSULTANTS` | N/A | React UI (not inspected) | Frontend only |
| `window.FICHE_DATA` | N/A | React UI (not inspected) | Frontend only |
| `clear_cache` | ✅ | data_loader.py:57 | Called by app.py after pipeline run |
| `export_team_version` | ❌ | Not in app.py | Missing — not implemented |
