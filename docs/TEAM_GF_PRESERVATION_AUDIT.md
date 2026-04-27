# TEAM_GF PRESERVATION AUDIT

**Step:** CLEAN Step 9  
**Version:** 1.0  
**Date:** 2026-04-26  
**Author:** Claude (Cowork agent)  
**Status:** COMPLETE — CONDITIONALLY PRESERVED

---

## 1. Executive Summary

**Verdict: CONDITIONALLY PRESERVED**

The `GF_TEAM_VERSION` chain infrastructure is intact and unchanged by Steps 7/8. All path constants, context wiring, artifact registration slots, and UI export code are correct and operational.

**However, one pre-existing architectural gap is confirmed:** `build_team_version()` in `team_version_builder.py` is defined as a "pipeline-callable entry point" but is **not called by any pipeline stage**. `GF_TEAM_VERSION.xlsx` is therefore not automatically generated during a standard `python main.py` run. It can only be produced by running `team_version_builder.py` directly (via its standalone `main()`).

This gap predates Steps 7/8. Neither step introduced, widened, or narrowed it. The registration and UI export infrastructure remains ready to function as designed once the build call is wired in (a future wiring task, not scoped to Steps 1–9).

---

## 2. Chain Map

| # | Step | File / Function | Input | Output | Status |
|---|------|----------------|-------|--------|--------|
| 1 | Write primary GF | `stage_write_gf.py` | `GF_FILE`, pipeline data | `output/GF_V0_CLEAN.xlsx` | ✅ ACTIVE |
| 2 | Build team version | `team_version_builder.py → build_team_version()` | `GF_V0_CLEAN.xlsx` + `Grandfichier_v3.xlsx` | `output/GF_TEAM_VERSION.xlsx` | ⚠️ NOT WIRED INTO PIPELINE |
| 3 | Register artifact | `stage_finalize_run.py` | `OUTPUT_GF_TEAM_VERSION` path (if exists) | `run_memory.db` artifact row `GF_TEAM_VERSION` | ⚠️ CONDITIONAL (file must exist) |
| 4 | UI export | `app.py → export_team_version()` | `GF_TEAM_VERSION` artifact from `run_memory.db` | `output/Tableau de suivi de visa DD_MM_YYYY.xlsx` | ✅ CORRECT IMPLEMENTATION |

---

## 3. Generation Path

### 3.1 How GF_TEAM_VERSION.xlsx is intended to be created

`src/team_version_builder.py` contains two callable entry points:

- **`main()`** (lines 1228–1335): Standalone run. Uses hardcoded module-level constants `OGF_PATH = "input/Grandfichier_v3.xlsx"`, `CLEAN_PATH = "output/GF_V0_CLEAN.xlsx"`, `OUT_PATH = "output/GF_TEAM_VERSION.xlsx"`. Run via `python src/team_version_builder.py` directly.

- **`build_team_version(ogf_path, clean_path, out_path)`** (lines 1127–1225): "Pipeline-callable entry point. Same logic as main() but with explicit paths instead of module constants." Returns a report dict.

### 3.2 What actually happens in the pipeline

The standard pipeline execution sequence (`runner.py`) is:
```
stage_init_run → stage_read_flat → stage_normalize → stage_version
→ stage_route → stage_report_memory → stage_write_gf
→ stage_discrepancy → stage_diagnosis → stage_finalize_run
```

**None of these stages import or call `build_team_version`.**

A search across all `src/**/*.py` files for `build_team_version` and `team_version_builder` returns exactly two results:
1. `src/team_version_builder.py:1127` — the function definition itself.
2. `scripts/repo_health_check.py:310` — a regex pattern checking that the symbol *exists* in the file (not that it is called).

The `run_orchestrator.py` and `main.py` also contain no call to `build_team_version`.

### 3.3 Consequence

On a fresh environment (or after `output/` is cleaned), running `python main.py` will NOT produce `output/GF_TEAM_VERSION.xlsx`. The file at the registered path will be absent.

On subsequent runs, if the file persists on disk from a previous manual execution of `team_version_builder.py main()`, `stage_finalize_run` will find and register it — but it will be stale relative to the current run's `GF_V0_CLEAN.xlsx`.

---

## 4. Artifact Registration Path

### 4.1 Path constant definition

`src/pipeline/paths.py` line 68:
```python
OUTPUT_GF_TEAM_VERSION = OUTPUT_DIR / "GF_TEAM_VERSION.xlsx"
# → <project_root>/output/GF_TEAM_VERSION.xlsx
```

This constant is correctly defined and never missing.

### 4.2 Context propagation

`runner.py` line 86 passes `OUTPUT_GF_TEAM_VERSION = ns.OUTPUT_GF_TEAM_VERSION` into `PipelineState`. The context dataclass (`pipeline/context.py` line 67) holds it as `Path | None`.

### 4.3 Orchestrator disabled_root behavior

`run_orchestrator.py` lines 213–226: when `use_reports` is False (i.e., run mode is `GED_ONLY`, `GED_GF`, or `FULL` without a `reports_dir`), the orchestrator redirects:
```python
main_module.OUTPUT_GF_TEAM_VERSION = disabled_root / "GF_TEAM_VERSION.xlsx"
```
where `disabled_root = OUTPUT_DIR / "_orchestrator_disabled" / run_mode.lower()`.

This path will not exist. `stage_finalize_run` uses `if not _ap.exists(): continue`, so registration is silently skipped. This is **intentional design**: team version output is tied to the consultant report workflow and is appropriately disabled when reports are not present.

When `use_reports` is True (FULL or GED_REPORT mode with `reports_dir`), the constant retains its default value `output/GF_TEAM_VERSION.xlsx` — but since `build_team_version` is never called, the file is still not generated.

### 4.4 Registration call in stage_finalize_run

`stage_finalize_run.py` lines 119–120:
```python
(OUTPUT_GF_TEAM_VERSION, "GF_TEAM_VERSION", False),
```
This entry is correctly placed in the artifact registration list with `is_debug=False`. The registration loop (lines 139–160) copies the file to `runs/run_NNNN/` and calls `register_run_artifact(... artifact_type="GF_TEAM_VERSION" ...)`. If the file exists at the path, registration succeeds. If absent, it is skipped without error.

---

## 5. UI Export Path

### 5.1 export_team_version() implementation

`app.py` lines 416–446. The method:

1. Loads `RunContext` via `load_run_context(BASE_DIR)`.
2. Looks up `GF_TEAM_VERSION` in `ctx.artifact_paths` (populated from `run_memory.db` by `data_loader._query_db`).
3. Falls back to `_get_artifact_path(run_memory.db, run_number, "GF_TEAM_VERSION")` — queries `run_artifacts` table directly.
4. If neither lookup returns a valid, existing file: returns `{"success": False, "error": "GF_TEAM_VERSION artifact not found for Run N. Run the pipeline first."}`.
5. If found: date-stamps the filename as `Tableau de suivi de visa DD_MM_YYYY.xlsx` using `ctx.data_date`, atomic-copies via `tempfile` + `tmp_path.rename(dest)`, returns `{"success": True, "path": str(dest)}`.

The implementation is correct, robust, and handles missing artifacts gracefully.

### 5.2 data_loader artifact_paths population

`data_loader.py` lines 447–450:
```python
artifact_paths = {}
for r in ...:
    artifact_paths[r["artifact_type"]] = r["file_path"]
```
All registered artifact types, including `GF_TEAM_VERSION`, are loaded into the RunContext at UI startup. If `GF_TEAM_VERSION` is registered in `run_memory.db`, it will appear here.

---

## 6. Flat GED Impact (Steps 7/8)

Steps 7 and 8 did **not** modify any component of the TEAM_GF chain. This is confirmed by targeted grep across all changed files:

| File | Change in Step 7 | Change in Step 8 | TEAM_GF touched? |
|------|-----------------|-----------------|-----------------|
| `src/run_orchestrator.py` | Added Flat GED build + `FLAT_GED_FILE`/`FLAT_GED_MODE` wiring | Added `_register_flat_ged_artifacts()` helper + call | NO |
| `src/pipeline/paths.py` | Changed `FLAT_GED_FILE` default path only | No change | NO |
| `src/flat_ged_runner.py` | New file (builder wrapper) | No change | NO |

Every touched line in Steps 7/8 traces directly to Flat GED concerns. The following TEAM_GF components were not modified in any way:

- `src/team_version_builder.py` — untouched ✅
- `src/pipeline/stages/stage_finalize_run.py` — untouched ✅
- `app.py export_team_version()` — untouched ✅
- `OUTPUT_GF_TEAM_VERSION` constant in `paths.py` — untouched ✅
- `disabled_root` logic for `OUTPUT_GF_TEAM_VERSION` in orchestrator — untouched ✅

Additionally, the `_patched_main_context` save/restore in `run_orchestrator.py` correctly saves and restores `OUTPUT_GF_TEAM_VERSION` (line 202–203) alongside `FLAT_GED_FILE` and `FLAT_GED_MODE`. The context manager is not broken by Step 7/8 additions.

---

## 7. Risks

| ID | Risk | Severity | Origin | Notes |
|----|------|----------|--------|-------|
| R-01 | `build_team_version()` not called by any pipeline stage | HIGH | Pre-existing | Pipeline does not generate `GF_TEAM_VERSION.xlsx`. File must exist from a previous manual run of `team_version_builder.py`. If absent, registration is silently skipped and UI export fails with a clear error message. |
| R-02 | `disabled_root` redirects `OUTPUT_GF_TEAM_VERSION` in non-report modes | MEDIUM | Pre-existing (intended) | GED_ONLY and GED_GF modes do not produce or register GF_TEAM_VERSION. This is correct behavior — the team version is meaningless without consultant data. Risk is that FULL mode without `reports_dir` also silently skips. |
| R-03 | File path relocation breaks artifact lookup | LOW | Pre-existing | If `run_memory.db` stores absolute paths from a previous machine or repo location, `_get_artifact_path` uses a fallback resolver (`runs/` anchor) that usually succeeds. The resolver is implemented correctly in both `run_orchestrator.py` and `data_loader.py`. |
| R-04 | Registration succeeds with stale file | LOW | Pre-existing | If `output/GF_TEAM_VERSION.xlsx` persists from a prior manual run, `stage_finalize_run` will register it against the current run number — but the file was not built from the current run's `GF_V0_CLEAN.xlsx`. The hash is computed at registration time; there is no freshness check. |
| R-05 | `export_team_version()` date uses `ctx.data_date` | LOW | Pre-existing | If `ctx.data_date` is None (no GED data loaded), the date falls back to `datetime.date.today()`. This produces a valid filename but with the wrong date. The fallback path is implemented correctly. |

---

## 8. Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| AC-1 | `GF_TEAM_VERSION.xlsx` is still produced | ⚠️ CONDITIONAL | Not produced by pipeline automatically. Produced only by manual `python src/team_version_builder.py`. Gap pre-dates Steps 7/8. |
| AC-2 | It is still registered as a run artifact | ⚠️ CONDITIONAL | `stage_finalize_run.py` line 120 has the correct registration entry. Registration fires if and only if the file exists at the registered path. |
| AC-3 | UI can still export a dated Tableau de suivi de visa | ⚠️ CONDITIONAL | `app.py export_team_version()` is correctly implemented and handles missing artifact gracefully. Export succeeds if AC-2 succeeded. |
| AC-4 | Steps 7/8 did not modify the TEAM_GF chain | ✅ CONFIRMED | Zero TEAM_GF-related lines changed in Steps 7/8. Verified by grep across all modified files. |
| AC-5 | Raw fallback does not remove the feature | ✅ CONFIRMED | `GFUP_FORCE_RAW=1` only affects Flat GED build and Flat GED artifact registration. No impact on `GF_TEAM_VERSION` path. |

**Overall verdict: CONDITIONALLY PRESERVED.** The chain is architecturally intact and not harmed by recent work. The gap at AC-1/AC-2/AC-3 is pre-existing and requires a Step 7 follow-up wiring task (see Section 9).

---

## 9. Step 10 Inputs (UI Loader Productization)

The following items from this audit are relevant to Step 10:

| Item | Relevance to Step 10 |
|------|---------------------|
| `data_loader` loads `artifact_paths` from `run_memory.db` including `GF_TEAM_VERSION` | Step 10 must ensure that when `data_loader` refactors to artifact-based loading, `GF_TEAM_VERSION` artifact path is still exposed in `RunContext.artifact_paths`. |
| `export_team_version()` double lookup (ctx.artifact_paths → _get_artifact_path fallback) | This two-step lookup is correct. Step 10 must not remove or short-circuit either leg. |
| `GF_TEAM_VERSION` is not an artifact type used by the data loader for data loading | It is only used by `export_team_version()`. Step 10 does not need to handle it in the load-path redesign, only preserve its availability in `ctx.artifact_paths`. |

### Follow-up task (not in scope for Steps 9–10, flagged for Step 15 validation)

**TASK-TEAM-01:** Wire `build_team_version()` into the pipeline.

Recommended integration point: after `stage_write_gf` produces `GF_V0_CLEAN.xlsx`, in a new `stage_build_team_version` stage or as a call block within `stage_discrepancy` or `stage_diagnosis`. The call should only fire when `use_reports` is True (i.e., GF_FILE and GF_V0_CLEAN both available). Required inputs:
- `ogf_path = str(GF_FILE)` (the original Grandfichier_v3.xlsx)
- `clean_path = str(OUTPUT_GF)` (the freshly written GF_V0_CLEAN.xlsx)
- `out_path = str(OUTPUT_GF_TEAM_VERSION)`

This task must be completed before Gate 4 criterion G4-05 ("GF_TEAM_VERSION.xlsx is produced correctly — export_team_version() produces stamped file") can pass.

---

## 10. Syntax Verification

The Linux bash sandbox was unavailable during this step (stale virtiofs mount reference to the deleted `GFUP CLEAN BASE + CLEAN IO` directory — same constraint documented in Steps 1–8). Syntax verification was performed via direct source inspection.

| File | Verification Method | Result |
|------|-------------------|--------|
| `src/team_version_builder.py` | Source read — 1336 lines, all functions complete, balanced `if __name__ == '__main__'` guard | ✅ Syntax valid |
| `src/pipeline/stages/stage_finalize_run.py` | Source read — 239 lines, all sections complete, returns dict at line 222 | ✅ Syntax valid |
| `app.py` | Source read — 842 lines, all class methods complete, `if __name__ == "__main__"` guard at line 840 | ✅ Syntax valid |

**Note:** When the bash sandbox becomes available, verify with:
```bash
python -m py_compile src/team_version_builder.py
python -m py_compile src/pipeline/stages/stage_finalize_run.py
python -m py_compile app.py
```

---

## Appendix A — Key Symbol Map

| Symbol | File | Line | Role |
|--------|------|------|------|
| `OUT_PATH = "output/GF_TEAM_VERSION.xlsx"` | `team_version_builder.py` | 18 | Standalone run output path |
| `build_team_version(ogf_path, clean_path, out_path)` | `team_version_builder.py` | 1127 | Pipeline-callable entry point (not yet wired) |
| `main()` | `team_version_builder.py` | 1228 | Standalone entry point (uses module-level constants) |
| `OUTPUT_GF_TEAM_VERSION = OUTPUT_DIR / "GF_TEAM_VERSION.xlsx"` | `pipeline/paths.py` | 68 | Path constant |
| `OUTPUT_GF_TEAM_VERSION: Path | None = None` | `pipeline/context.py` | 67 | Context slot |
| `OUTPUT_GF_TEAM_VERSION = ns.OUTPUT_GF_TEAM_VERSION` | `pipeline/runner.py` | 86 | Context population |
| `"OUTPUT_GF_TEAM_VERSION": main_module.OUTPUT_GF_TEAM_VERSION` | `run_orchestrator.py` | 202 | Save before patching |
| `main_module.OUTPUT_GF_TEAM_VERSION = disabled_root / "GF_TEAM_VERSION.xlsx"` | `run_orchestrator.py` | 225 | Disabled in non-report modes |
| `(OUTPUT_GF_TEAM_VERSION, "GF_TEAM_VERSION", False)` | `stage_finalize_run.py` | 120 | Artifact registration entry |
| `def export_team_version(self)` | `app.py` | 416 | UI export function |
| `team_path = ctx.artifact_paths.get("GF_TEAM_VERSION")` | `app.py` | 423 | Primary artifact lookup |
| `_get_artifact_path(..., "GF_TEAM_VERSION")` | `app.py` | 426 | Fallback artifact lookup |
| `dest = OUTPUT_DIR / f"Tableau de suivi de visa {date_str}.xlsx"` | `app.py` | 435 | Dated export destination |
