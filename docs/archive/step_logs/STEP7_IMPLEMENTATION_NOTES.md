# CLEAN Step 7 — Implementation Notes

**Date:** 2026-04-26  
**Step:** CLEAN Step 7 — Automatic Flat GED Build + Pipeline Wiring  
**Status:** ✅ COMPLETE

---

## Files Modified

| File | Change type | Summary |
|------|-------------|---------|
| `src/pipeline/paths.py` | 1-line edit | `FLAT_GED_FILE` default rerouted from `input/` to `output/intermediate/` |
| `src/run_orchestrator.py` | 3-block edit | `import os` added; `FLAT_GED_FILE`/`FLAT_GED_MODE` saved in context manager; auto-build block inserted |

## Files Created

| File | Summary |
|------|---------|
| `docs/STEP7_IMPLEMENTATION_NOTES.md` | This file |

## Files Not Modified (as required)

- `src/flat_ged/*` — frozen builder, untouched
- `src/flat_ged_runner.py` — Step 6 wrapper, used as-is
- `main.py` — entrypoint unchanged
- `src/pipeline/runner.py` — pipeline stages unchanged
- `src/pipeline/stages/*` — all stages unchanged
- `src/run_memory.py`, `src/report_memory.py` — unchanged
- `ui/` — no UI changes in this step

---

## Where the Auto-Build Was Integrated

Integration point: `src/run_orchestrator.py` → `run_pipeline_controlled()`

The flat GED build is invoked **after input validation and GF path resolution, but before the pipeline context manager and pipeline execution**. This means:

1. If the build fails, we return a clean `{"success": False, "errors": [...]}` dict immediately — no run is registered in `run_memory.db`, no partial pipeline is executed.
2. The resulting `flat_ged_path` is passed into the `with _patched_main_context(...)` block.
3. Inside the context block, `main_module.FLAT_GED_FILE` and `main_module.FLAT_GED_MODE` are set to the generated path and `"flat"` respectively.
4. The context manager (`_patched_main_context`) saves and restores these two globals alongside all other pipeline globals, so multi-run invocations remain isolated.

Exact location in `run_pipeline_controlled()`:
```
[validation]
[GF path resolution]
[execution_context build]
← NEW: auto-build block (lines 283–305)
[try:]
  [with _patched_main_context:]
    ← NEW: flat mode activation (lines 309–311)
    [main_module.run_pipeline()]
```

---

## How Flat Mode Is Now Selected

`runner.py` already reads `FLAT_GED_MODE` from the module namespace at runtime:
```python
_mode = getattr(ns, "FLAT_GED_MODE", "raw")
if _mode == "flat":
    stage_read_flat(ctx, log)
else:
    stage_read(ctx, log)
```

After Step 7, the orchestrator sets `FLAT_GED_MODE = "flat"` and `FLAT_GED_FILE = <generated path>` on `main_module` before the pipeline runs. This requires zero changes to `runner.py` or any stage.

---

## Fallback (Raw) Mode

**Method chosen: Option 1 — environment variable `GFUP_FORCE_RAW=1`.**

To use the legacy raw read path (bypassing the Flat GED builder):

```bash
GFUP_FORCE_RAW=1 python main.py
```

Behavior when set:
- Builder is not called
- `flat_ged_path` remains `None`
- `FLAT_GED_FILE` / `FLAT_GED_MODE` are not mutated by the orchestrator
- `FLAT_GED_MODE` defaults to `"raw"` (from `paths.py`), so `stage_read` runs instead of `stage_read_flat`
- A log line prints: `[orchestrator] GFUP_FORCE_RAW=1 — skipping Flat GED build, using raw mode.`

This fallback is intended for developers only. Normal user runs always use flat mode.

---

## Path Policy

`src/pipeline/paths.py` default changed:

```python
# Before Step 7:
FLAT_GED_FILE = INPUT_DIR / "FLAT_GED.xlsx"

# After Step 7:
FLAT_GED_FILE = OUTPUT_DIR / "intermediate" / "FLAT_GED.xlsx"
```

The `output/intermediate/` directory is created automatically by `build_flat_ged_artifacts()` via `intermediate_dir.mkdir(parents=True, exist_ok=True)`.

**Backward compatibility:** A developer who manually places `input/FLAT_GED.xlsx` and sets `GFUP_FORCE_RAW=1` can still run the old raw path — `stage_read` does not use `FLAT_GED_FILE`. The `FLAT_GED_FILE` path is only relevant when `FLAT_GED_MODE="flat"`.

---

## Failure Handling

If `build_flat_ged_artifacts()` raises a `RuntimeError` (builder failure, missing GED, missing output, etc.), `run_pipeline_controlled()` immediately returns:

```python
{
    "success": False,
    "run_number": None,
    "status": "FAILED",
    "errors": ["Flat GED build failed: <message>"],
    "warnings": [...],
    "outputs": {"final_gf": None},
}
```

The pipeline does NOT start. `run_memory.db` is not modified. No partial outputs are produced from the pipeline stages.

The builder's own `_cleanup_outputs()` in `flat_ged_runner.py` deletes any partial intermediate files before re-raising.

---

## Artifact Registration

Step 7 does **not** register Flat GED artifacts (`FLAT_GED`, `FLAT_GED_DEBUG_TRACE`, `FLAT_GED_RUN_REPORT`) in `run_memory.db`. This is deferred to **CLEAN Step 8** as specified in the step plan.

The existing pipeline's artifact registration (FINAL_GF, GF_TEAM_VERSION, DISCREPANCY_REPORT, etc.) is unchanged.

---

## How to Run

### Standard run (flat mode — default):
```bash
cd "GF updater v3"
python main.py
```

Expected log sequence:
```
[flat_ged_runner] Building FLAT GED from: .../input/GED_export.xlsx
[flat_ged_runner] Output dir: .../output/intermediate
[flat_ged_runner] Builder completed.
============================================================
GF UPDATER V3 — RUN 0 (CLEAN REBUILD) — Patch A+B+C+D
============================================================
[1/7] Reading GED export (flat)...
...
```

### Raw fallback (developer only):
```bash
GFUP_FORCE_RAW=1 python main.py
```

---

## Known Limitations / Deferred Items

| Item | Step |
|------|------|
| Flat GED artifacts not registered in `run_memory.db` (`FLAT_GED`, `FLAT_GED_DEBUG_TRACE`, `FLAT_GED_RUN_REPORT` types) | CLEAN Step 8 |
| UI data_loader still rebuilds from raw GED — does not consume flat artifacts | CLEAN Steps 10–12 |
| `stage_write_gf` still has `FLAT_GED_ADAPTER_MAP.md` M-03 stale sentence (noted in Step 2) | Step 14 cleanup |

---

## Syntax Validation

All four touched/used files pass `python -m py_compile`:

```
python -m py_compile main.py                   ✅
python -m py_compile src/run_orchestrator.py   ✅
python -m py_compile src/pipeline/paths.py     ✅
python -m py_compile src/flat_ged_runner.py    ✅
```
