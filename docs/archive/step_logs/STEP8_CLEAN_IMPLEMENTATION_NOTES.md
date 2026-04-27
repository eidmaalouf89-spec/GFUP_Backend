# CLEAN Step 8 — Artifact Registration Implementation Notes

**Date completed:** 2026-04-26  
**Status:** ✅ DONE

---

## 1. Files Changed

| File | Change |
|------|--------|
| `src/run_orchestrator.py` | Added import, added `_register_flat_ged_artifacts()` helper, called it inside `run_pipeline_controlled()` |

`src/run_memory.py` — **no changes required**.  
`main.py` — **not touched**.  
`src/pipeline/stages/stage_finalize_run.py` — **not touched** (does not exist; finalization happens in orchestrator).  
`src/flat_ged/*` — **not touched** (frozen builder).

---

## 2. Integration Point

**Option A chosen:** inside `run_orchestrator.py → run_pipeline_controlled()`, after pipeline succeeds and `run_number` is known, before `get_run_summary()` is called.

```python
if run_number is not None:
    # Register Flat GED artifacts produced before this run started
    if not force_raw:
        _register_flat_ged_artifacts(
            db_path=main_module.RUN_MEMORY_DB,
            run_number=run_number,
            build_result=build_result,
        )
    run_summary = get_run_summary(main_module.RUN_MEMORY_DB, run_number)
```

**Why Option A:**
- `run_orchestrator.py` already owns `build_result` (built before the pipeline `try:` block)
- `run_number` is resolved from `main_module._ACTIVE_RUN_NUMBER` after `run_pipeline()` returns
- Smallest patch: no other file needs to know about Flat GED artifacts
- `get_run_summary()` is called after registration, so `artifact_count` in the return dict will include the new artifacts

---

## 3. Artifact Types Added

| Type | File | Mandatory | Format |
|------|------|-----------|--------|
| `FLAT_GED` | `output/intermediate/FLAT_GED.xlsx` | Yes | xlsx |
| `FLAT_GED_RUN_REPORT` | `output/intermediate/flat_ged_run_report.json` | Yes | json |
| `FLAT_GED_DEBUG_TRACE` | `output/intermediate/DEBUG_TRACE.csv` | No (skipped silently if None) | csv |

Artifact names stored exactly as the filenames produced by `flat_ged_runner.py`.

---

## 4. Paths Stored

Absolute path strings, as returned by `flat_ged_runner.build_flat_ged_artifacts()`. This is consistent with the existing `FINAL_GF` artifact registration which also uses absolute paths.

---

## 5. DB Schema Changes

**None.** The existing `run_artifacts` schema already supports free-string `artifact_type`, a `format` column, a `file_hash` column, and a `metadata_json` column. The `ON CONFLICT DO UPDATE` in `register_run_artifact` makes the insert idempotent.

UNIQUE constraint `(run_number, artifact_type, artifact_name)` — one row per type per run, which is correct for these artifacts.

---

## 6. Implementation Details

### New module-level import (1 line)
```python
from src.run_memory import register_run_artifact, sha256_file
```

### New helper function `_register_flat_ged_artifacts()`
- Takes `db_path`, `run_number`, `build_result` dict
- Registers FLAT_GED (mandatory), FLAT_GED_RUN_REPORT (mandatory), FLAT_GED_DEBUG_TRACE (optional)
- Each call individually wrapped in `try/except` — a single failure does not block the others
- Uses `sha256_file()` for file hashing, wrapped in `_safe_hash()` to swallow IO errors
- Missing mandatory files emit a `logging.warning`; missing optional `debug_trace_path` is silently skipped
- `format` populated: "xlsx" / "json" / "csv"
- `metadata_json` left as None (no overengineering; run_report.json on disk is the authoritative metadata)

### Condition guard
Registration only fires when `not force_raw` — consistent with when `build_result` is defined. `GFUP_FORCE_RAW=1` skips both the build and the registration.

---

## 7. Test Evidence

**Syntax validation:**
- Bash sandbox unavailable (stale mount — same condition as CLEAN Steps 1–7).
- Full file read-back performed: all three edits verified in place (lines 23, 236–305, 388–394).
- `Optional` type annotation in `_safe_hash` is in scope via existing `from typing import Optional` at line 19.
- `build_result` is always defined when `not force_raw` guard is true — no NameError possible.

**DB schema compatibility:**
- `run_artifacts` table schema confirmed from `run_memory.py` DDL (lines 118–131).
- All inserted column types match: TEXT artifact_type/name/path/format, TEXT file_hash, NULL row_count, NULL metadata_json.
- `INSERT ... ON CONFLICT DO UPDATE` confirmed in `register_run_artifact` (lines 568–578 of run_memory.py).

**Expected DB rows after next successful run (example run 12):**

```sql
SELECT run_number, artifact_type, artifact_name, format, file_path
FROM run_artifacts
WHERE run_number = 12 AND artifact_type LIKE 'FLAT_GED%';

-- Expected:
-- 12 | FLAT_GED            | FLAT_GED.xlsx             | xlsx | /abs/path/output/intermediate/FLAT_GED.xlsx
-- 12 | FLAT_GED_RUN_REPORT | flat_ged_run_report.json  | json | /abs/path/output/intermediate/flat_ged_run_report.json
-- 12 | FLAT_GED_DEBUG_TRACE | DEBUG_TRACE.csv          | csv  | /abs/path/output/intermediate/DEBUG_TRACE.csv
```

---

## 8. Known Limitations

1. **Flat GED artifacts are not copied into `runs/run_NNNN/`** — they live in `output/intermediate/` and are shared across all runs that produce them. The registered `file_path` points to `output/intermediate/`. If a later run overwrites `FLAT_GED.xlsx`, the `file_path` in earlier run registrations will still point to the same (now-updated) file. This is acceptable at current scale; a future hardening step could copy artifacts into the run dir.

2. **Bash sandbox unavailable** — `python -m py_compile` could not be executed. Syntax verified by manual code inspection.

3. **EFFECTIVE_RESPONSES** artifact type deferred to Step 11 as specified — not implemented here.

4. **`artifact_count` in the orchestrator return dict** will now include Flat GED artifacts (since `get_run_summary()` is called after registration). This is correct behaviour — `artifact_count` becomes a more accurate picture of run completeness.

---

## 9. Artifacts Preserved / Unchanged

- FINAL_GF registration: **untouched**
- GF_TEAM_VERSION registration: **untouched**
- DISCREPANCY_REPORT, ANOMALY_REPORT, and all other artifact types: **untouched**
- Run 0 baseline: **not touched**
- `src/flat_ged/*` builder: **not touched**
- `report_memory` logic: **not touched**
- UI code: **not touched**
