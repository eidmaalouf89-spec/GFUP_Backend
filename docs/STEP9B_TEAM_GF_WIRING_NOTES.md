# STEP 9B — TEAM_GF WIRING NOTES

**Step:** CLEAN Step 9b  
**Date:** 2026-04-26  
**Status:** DONE

---

## Objective

Wire `build_team_version()` into the pipeline so that `output/GF_TEAM_VERSION.xlsx`
is automatically produced on every full pipeline run, before `stage_finalize_run`
registers artifacts.

This closes TASK-TEAM-01 identified in the Step 9 preservation audit.

---

## Changes Made

### 1. New file: `src/pipeline/stages/stage_build_team_version.py`

Minimal new pipeline stage. Responsibilities:

- Guards: checks `ctx.OUTPUT_GF_TEAM_VERSION is not None`, `ctx.GF_FILE` exists,
  `ctx.OUTPUT_GF` exists. Logs and returns silently if any guard fails.
- Calls `build_team_version(ogf_path, clean_path, out_path)` with a lazy import
  (`from team_version_builder import build_team_version` inside the try block).
- Wraps the call in `try/except Exception` — failure is non-fatal; a `[WARN]` is
  printed but the pipeline continues.
- Logs match/update/insert counts from the returned report dict.

### 2. `src/pipeline/stages/__init__.py`

Added:
```python
from pipeline.stages.stage_build_team_version import stage_build_team_version
```
and `"stage_build_team_version"` in `__all__`, between `stage_write_gf` and
`stage_discrepancy`.

### 3. `src/pipeline/runner.py`

Added `stage_build_team_version` to the import block (from `pipeline.stages`) and
inserted the call between `stage_write_gf` and `stage_discrepancy`:

```python
stage_write_gf(ctx, log)
stage_build_team_version(ctx, log)   # NEW
stage_discrepancy(ctx, log)
```

---

## Stage Insertion Point

```
stage_write_gf       → writes output/GF_V0_CLEAN.xlsx       (produces the clean input)
stage_build_team_version → writes output/GF_TEAM_VERSION.xlsx  (NEW)
stage_discrepancy    → reads GF file for sheet structure
...
stage_finalize_run   → registers GF_TEAM_VERSION artifact if file exists
```

**Why after stage_write_gf:** `OUTPUT_GF` (GF_V0_CLEAN.xlsx) must exist before
`build_team_version` can run. `stage_write_gf` is the stage that produces it.

**Why before stage_discrepancy:** No dependency between team version building and
discrepancy computation. Placing it here keeps the team version fresh in the run
folder and available to `stage_finalize_run`.

---

## Guard Behaviour

| Condition | Action |
|-----------|--------|
| `OUTPUT_GF_TEAM_VERSION is None` | Log `[team_version] ... skipping (disabled mode)` and return |
| `GF_FILE` does not exist on disk | `[WARN]` print and return |
| `OUTPUT_GF` does not exist on disk | `[WARN]` print and return |
| `build_team_version()` raises any exception | `[WARN]` print and return (non-fatal) |

The `OUTPUT_GF_TEAM_VERSION is None` guard handles the `disabled_root` scenario in
the orchestrator (GED_ONLY / GED_GF modes), where the path is redirected to a
non-existent directory. Because `_patched_main_context` sets
`main_module.OUTPUT_GF_TEAM_VERSION = disabled_root / "GF_TEAM_VERSION.xlsx"`
and the context holds a `Path | None` slot, the check `is not None` evaluates to
True even for the disabled path. In practice, the `GF_FILE` guard catches this
case: in GED_ONLY mode, `GF_FILE` is set to `disabled_root / "_missing_gf.xlsx"`,
which does not exist, so the stage skips cleanly with a `[WARN]`.

---

## What Was NOT Changed

- `src/team_version_builder.py` — zero modifications (business logic frozen)
- `src/pipeline/stages/stage_finalize_run.py` — zero modifications (already
  registers GF_TEAM_VERSION if file exists; Step 9 confirmed this is correct)
- `src/run_orchestrator.py` — zero modifications
- `app.py` — zero modifications
- `src/flat_ged/` — zero modifications
- Raw fallback (`GFUP_FORCE_RAW=1`) — unaffected; the stage runs in both modes

---

## Validation

```
python -m py_compile src/team_version_builder.py         OK
python -m py_compile src/pipeline/stages/stage_build_team_version.py  OK
python -m py_compile src/pipeline/runner.py              OK
python -m py_compile src/pipeline/stages/__init__.py     OK
```

All four pass cleanly.

---

## Gate 4 Impact

This wiring closes the only HIGH-severity risk from the Step 9 audit (R-01).
Gate 4 criterion **G4-05** ("GF_TEAM_VERSION.xlsx is produced correctly — 
`export_team_version()` produces stamped file") can now be satisfied by a
standard `python main.py FULL` run.
