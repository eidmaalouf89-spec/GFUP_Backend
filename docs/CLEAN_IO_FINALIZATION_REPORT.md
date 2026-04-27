# CLEAN Step 12 — Clean IO Finalization Report

**Date:** 2026-04-26
**Step:** CLEAN Step 12 — Clean Input / Clean Output Finalization
**Status:** COMPLETE

---

## 1. Files Modified

| File | Change |
|---|---|
| `src/pipeline/paths.py` | Added `INTERMEDIATE_DIR`, `RUNS_DIR`, `DATA_DIR` constants; `FLAT_GED_FILE` now uses `INTERMEDIATE_DIR`; `REPORT_MEMORY_DB` / `RUN_MEMORY_DB` now use `DATA_DIR` |
| `src/run_orchestrator.py` | `intermediate_dir` now reads from `main_module.INTERMEDIATE_DIR` instead of hardcoded `OUTPUT_DIR / "intermediate"` |
| `main.py` | Added `INTERMEDIATE_DIR.mkdir(exist_ok=True)` to startup |
| `README.md` | Rewrote: added Quick Start, Folder Structure, updated gate table, current state, removed stale "What Is Temporary" items, corrected all Step 7/11 outcomes |
| `GFUP_STEP_TRACKER.md` | Added CLEAN Step 12 entry |
| `docs/CLEAN_IO_FINALIZATION_REPORT.md` | This file (new) |

No files deleted. No files moved. No business logic modified.

---

## 2. Path Contracts — Before vs After

### Directory Constants in `paths.py`

| Constant | Before (Step 11) | After (Step 12) |
|---|---|---|
| `BASE_DIR` | `_MAIN_DIR` | unchanged |
| `INPUT_DIR` | `BASE_DIR / "input"` | unchanged |
| `OUTPUT_DIR` | `BASE_DIR / "output"` | unchanged |
| `INTERMEDIATE_DIR` | **did not exist** | `OUTPUT_DIR / "intermediate"` **(new)** |
| `DEBUG_DIR` | `OUTPUT_DIR / "debug"` | unchanged |
| `RUNS_DIR` | **did not exist** | `BASE_DIR / "runs"` **(new)** |
| `DATA_DIR` | **did not exist** | `BASE_DIR / "data"` **(new)** |
| `REPORT_MEMORY_DB` | `str(BASE_DIR / "data" / "report_memory.db")` | `str(DATA_DIR / "report_memory.db")` — equivalent |
| `RUN_MEMORY_DB` | `str(BASE_DIR / "data" / "run_memory.db")` | `str(DATA_DIR / "run_memory.db")` — equivalent |
| `FLAT_GED_FILE` | `OUTPUT_DIR / "intermediate" / "FLAT_GED.xlsx"` | `INTERMEDIATE_DIR / "FLAT_GED.xlsx"` — equivalent |

### What Was Already Correct (no change needed)

| Contract | Status |
|---|---|
| `GED_FILE = INPUT_DIR / "GED_export.xlsx"` | Correct since Step 7 |
| `GF_FILE = INPUT_DIR / "Grandfichier_v3.xlsx"` | Correct (always was) |
| `FLAT_GED_FILE` → `output/intermediate/` | Correct since Step 7 |
| `FLAT_GED_MODE = "raw"` default | Correct — overridden to `"flat"` by orchestrator at runtime |
| All `OUTPUT_*` constants → `OUTPUT_DIR` | Correct (always was) |
| `OUTPUT_GF_TEAM_VERSION` | Correct |
| `app.py` local path definitions | Consistent with `paths.py` |

### Hardcoded Paths Cleaned

| Location | Before | After |
|---|---|---|
| `run_orchestrator.py:363` | `Path(main_module.OUTPUT_DIR) / "intermediate"` | `Path(main_module.INTERMEDIATE_DIR)` |

---

## 3. Obsolete Paths Removed

| Path Reference | Context | Resolution |
|---|---|---|
| `input/FLAT_GED.xlsx` as pipeline input | Was eliminated in Step 7 | Confirmed: no runtime code references this. Only developer scripts and historical docs. |
| `OUTPUT_DIR / "intermediate"` hardcoded | `run_orchestrator.py` | Replaced with `INTERMEDIATE_DIR` constant |

### Stale References in Developer Scripts (not runtime — deferred)

| File | Reference | Impact |
|---|---|---|
| `scripts/_run_one_mode.py:36` | `input/FLAT_GED.xlsx` | Script obsolete; ARCHIVE_CANDIDATE |
| `scripts/clean_gf_diff.py:108` | `input/FLAT_GED.xlsx` | Parity tool; reads for comparison only |
| `scripts/ui_parity_harness.py:69` | `input/FLAT_GED.xlsx` | Parity tool; reads for comparison only |
| `scripts/repo_health_check.py:230` | Pattern grep for `input/FLAT_GED` | Health check correctly detects old pattern |

These do not affect runtime. Cleanup deferred to Step 13/14.

---

## 4. Cleanup Classification

### DELETE_NOW

| Item | Reason |
|---|---|
| `.claude/worktrees/` (6 directories) | Stale agent worktrees. Already in `.gitignore`. Not tracked. Can be deleted safely. |

### ARCHIVE_CANDIDATE

| Item | Reason |
|---|---|
| `JANSA Dashboard - Standalone.html` | Old standalone bundle. Dead UI path confirmed Step 10. |
| `GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md` | Old spec superseded by current architecture docs |
| `COWORK_PATCH_consultant_fiche_bugs.md` | One-off patch doc, work completed |
| `codex prompts/` | Old prompt engineering scratch folder |
| `ui/index.html` | Old Vite dev entrypoint; production is `jansa-connected.html` |
| `ui/src/` | Old Vite React source (App.jsx, main.jsx, etc.) |
| `ui/vite.config.js` | Old Vite config |
| `ui/eslint.config.js` | Old ESLint config for Vite UI |
| `ui/dist/` | Old Vite build output |
| `ui/node_modules/` | Old npm dependencies for Vite UI |
| `scripts/_run_one_mode.py` | Obsolete dev mode runner; hardcodes `input/FLAT_GED.xlsx` |
| `scripts/parity_harness.py` | Gate 1 validation — historical, passed |
| `scripts/clean_gf_diff.py` | Gate 2 validation — historical, passed |
| `scripts/ui_parity_harness.py` | Gate 3 validation — historical, passed |

### KEEP_ACTIVE

| Item | Reason |
|---|---|
| `ui/jansa-connected.html` | Production UI entrypoint |
| `ui/jansa/` (all files) | Production UI components |
| `scripts/bootstrap_run_zero.py` | Run 0 bootstrap — operational |
| `scripts/bootstrap_report_memory.py` | Report memory bootstrap — operational |
| `scripts/nuke_and_rebuild_run0.py` | Baseline reset tool — operational |
| `scripts/repo_health_check.py` | Health audit tool — still useful |
| All `src/` runtime files | Active production code |
| All `docs/` | Active documentation |

### DEFER

| Item | Reason |
|---|---|
| `src/reporting/bet_report_merger.py` | Retired (import commented DO NOT RESTORE) but file still exists. Low risk. |
| `FLAT_GED_MODE = "raw"` default flip | Orchestrator overrides to "flat" at runtime. Flipping default would break scripts that bypass orchestrator. |

---

## 5. Product-Cleanliness Score: 8/10

**What's strong:**
- `input/` contains only user-provided files (GED, GF, consultant_reports)
- `output/` contains only user-facing deliverables + cleanly separated `intermediate/` and `debug/`
- `runs/` is authoritative immutable history
- `data/` contains only persistent databases
- All path constants centralized in `paths.py`
- Pipeline auto-builds Flat GED — no manual steps
- UI loads from artifacts by default
- README now shows clear Quick Start + Folder Structure
- `.gitignore` already covers runtime outputs, runs, data, node_modules, worktrees

**What could be better (-2):**
- Archive candidates not yet moved (Step 13/14 scope)
- Old Vite UI files still in `ui/` alongside production JANSA files
- `FLAT_GED_MODE = "raw"` default not yet flipped (safe but cosmetically misleading)

---

## 6. Next Step Recommendation

**Step 13 should be: Cleanup Delete/Archive Plan** (as specified in the project instructions).

Rationale: The cleanup candidates identified above need a formal plan before any deletions. The product is functionally clean and all contracts are satisfied, but the repo still carries archival weight from the Vite UI era, old parity scripts, and one-off patch docs.

Step 14 (Cleanup Implementation) would then execute the plan.

---

## 7. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Stale worktrees (`.claude/worktrees/`) consuming disk space | LOW | Already in `.gitignore`. Delete when convenient. |
| Old Vite UI files could confuse future developers | LOW | README now documents production UI is `jansa-connected.html` only |
| Developer scripts reference `input/FLAT_GED.xlsx` | LOW | Not runtime. Will be archived in Step 14. |
| `FLAT_GED_MODE = "raw"` default reads misleadingly | LOW | Orchestrator overrides at runtime. Comment in `paths.py` explains. |
| `bet_report_merger.py` file still exists (retired) | NEGLIGIBLE | Import commented with DO NOT RESTORE. Dead code. |
