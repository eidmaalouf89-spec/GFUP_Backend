# STEP 9C — TEAM_GF HARDENING NOTES

**Step:** CLEAN Step 9c  
**Date:** 2026-04-26  
**Status:** DONE  
**Precondition:** Step 9b wired `build_team_version()` into the pipeline stage sequence.

---

## Objective

Replace the fragile Step 9b implementation (GF_FILE-or-skip, non-fatal) with a
production-grade stage that handles three cases:

1. OGF template resolution with run_memory.db fallback
2. Retry on transient build failures
3. Fatal vs non-fatal behavior by run mode

---

## Changes Made

### Only file modified: `src/pipeline/stages/stage_build_team_version.py`

Complete rewrite of the stage. `runner.py`, `__init__.py`, `stage_finalize_run.py`,
and `team_version_builder.py` were not touched.

---

## A — OGF Template Resolution

`_resolve_ogf_path(ctx, log)` checks in priority order:

| Priority | Source | Condition |
|----------|--------|-----------|
| 1 | `ctx.GF_FILE` | File exists on disk |
| 2 | Latest `GF_TEAM_VERSION` artifact from `run_memory.db` | File exists on disk |
| 3 | Latest `FINAL_GF` artifact from `run_memory.db` | File exists on disk |
| 4 | None — trigger skip or fatal | — |

**Why GF_TEAM_VERSION before FINAL_GF:**
`GF_TEAM_VERSION` preserves the team-known multi-sheet OGF format (consultant date/num/status columns, row 7-9 headers, original cell structure). `FINAL_GF` is a reconstructed GF_V0_CLEAN — it works as an OGF input but may have slightly different column widths, merged cell regions, or formatting. Using a prior `GF_TEAM_VERSION` produces a more stable patch result.

### `_resolve_latest_artifact_path(db_path, artifact_type)`

Private helper. Queries:
```sql
SELECT file_path FROM run_artifacts
WHERE artifact_type = ?
ORDER BY run_number DESC LIMIT 1
```
Returns the path string only if the file exists. Handles repo relocation:
if the stored absolute path is absent, scans `runs/run_*/<filename>` newest-first.
All exceptions are caught and return `None` (never raises).

---

## B — Retry Policy

```python
_RETRY_DELAYS = (0, 1, 2)   # seconds before attempt 1, 2, 3
```

- Attempt 1: immediate
- Attempt 2: after 1 second
- Attempt 3: after 2 seconds

The import of `build_team_version` is inside the retry loop's outer scope (not inside the except), so the import overhead is paid once and the retry loop only re-calls the builder.

On success: return immediately, log attempt number + match/update/insert counts.  
On per-attempt failure: log `[team_version] Attempt N failed: <exc>`, continue.  
After all 3 exhausted: apply fatal/non-fatal policy.

Rationale for retry: `team_version_builder` opens and saves openpyxl workbooks.
On Windows, brief file-lock contention (antivirus scan, cloud sync) can cause
`PermissionError` on the output file. 1–2 s is enough to clear such locks.

---

## C — Fatal vs Non-Fatal Policy

```python
_FATAL_MODES = {"FULL", "GED_REPORT"}
```

Run mode is read from `ctx._RUN_CONTROL_CONTEXT["run_mode"]` (set by
`run_orchestrator._patched_main_context`). If `_RUN_CONTROL_CONTEXT` is None
(e.g., direct `run_pipeline()` call without orchestrator), `run_mode` defaults to
`""` which is not in `_FATAL_MODES` — non-fatal.

| Condition | Behaviour |
|-----------|-----------|
| OGF template not found + FULL/GED_REPORT | `RuntimeError` raised immediately (no retry needed) |
| OGF template not found + other mode | `[WARN]` logged, stage returns |
| All 3 build attempts fail + FULL/GED_REPORT | `RuntimeError` raised with full error message |
| All 3 build attempts fail + other mode | `[WARN]` logged, stage returns |

The `RuntimeError` propagates up through `runner._run_pipeline_impl` and is caught
by `run_orchestrator.run_pipeline_controlled`'s `except Exception as exc:` block,
which marks the run as FAILED and returns `{"success": False, "errors": [...]}`.

---

## Guard conditions (unchanged from Step 9b)

| Check | Action |
|-------|--------|
| `OUTPUT_GF_TEAM_VERSION is None` | Log + return (disabled mode) |
| `OUTPUT_GF` does not exist | `[WARN]` + return |

The `OUTPUT_GF_TEAM_VERSION is None` check handles the `disabled_root` case in
GED_ONLY mode. The `OUTPUT_GF` check ensures `build_team_version`'s `clean_path`
argument always points to an actual file.

---

## What Was NOT Changed

| File | Status |
|------|--------|
| `src/team_version_builder.py` | Untouched — business logic frozen |
| `src/pipeline/runner.py` | Untouched — stage call already in place from Step 9b |
| `src/pipeline/stages/__init__.py` | Untouched |
| `src/pipeline/stages/stage_finalize_run.py` | Untouched |
| `src/run_orchestrator.py` | Untouched |
| `app.py` | Untouched |

---

## Validation

```
python -m py_compile src/pipeline/stages/stage_build_team_version.py   OK
python -m py_compile src/pipeline/runner.py                             OK
```

Helper unit tests (run in-process via bash):
- `_resolve_latest_artifact_path` with missing DB → None ✅
- `_resolve_latest_artifact_path` with DB, no rows → None ✅
- `_resolve_latest_artifact_path` with non-existent path → None ✅
- `_resolve_latest_artifact_path` with existing file → correct path ✅
- `_FATAL_MODES` contains FULL and GED_REPORT ✅
- `_RETRY_DELAYS == (0, 1, 2)` ✅

---

## Remaining Risks

| Risk | Severity | Notes |
|------|----------|-------|
| `GF_TEAM_VERSION` fallback may use a stale OGF from a different GED snapshot | LOW | Acceptable: it is the best available template. The user should provide `GF_FILE` for clean runs. |
| `FINAL_GF` fallback produces slightly different team version formatting | LOW | Known trade-off. Better than no team version at all in FULL mode. |
| 3 retries × 3 s overhead in worst case | LOW | Only triggered on actual failures; normal runs pay zero retry cost. |
| Relocation glob `runs/run_*/<name>` may match wrong file if two runs produced same filename | NEGLIGIBLE | Sorted newest-first; the most recent match wins. |
| `_RUN_CONTROL_CONTEXT` absent on direct `run_pipeline()` call | LOW | Defaults to non-fatal, which is the safe side for CLI debugging. |
