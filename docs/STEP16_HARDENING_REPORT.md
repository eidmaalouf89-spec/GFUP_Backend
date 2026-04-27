# STEP 16 - Hardening Report

**Date:** 2026-04-27
**Step:** CLEAN Step 16 - Performance, reliability, and operator hardening
**Result:** PASS

---

## Scope

Step 16 was kept intentionally narrow:

- no business-rule changes
- no pipeline redesign
- no changes to `src/flat_ged/`
- no changes to discrepancy logic, routing logic, or report-memory composition rules

The work focused on runtime hardening around SQLite access, operator-facing execution state, and small safe caching.

---

## Files Changed

- `app.py`
- `src/reporting/data_loader.py`
- `src/run_memory.py`
- `src/run_orchestrator.py`

---

## Changes Applied

### 1. SQLite read hardening in UI/runtime read paths

**Files:** `app.py`, `src/reporting/data_loader.py`

Added:

- short retry loop for transient `database is locked` cases
- `PRAGMA busy_timeout=5000`
- read-only immutable SQLite fallback for read queries when the normal connection path fails

Effect:

- UI reads are less brittle when the DB is briefly busy
- read-only inspection remains possible during transient lock contention

### 2. Artifact-path resolution cache with explicit invalidation

**File:** `src/reporting/data_loader.py`

Added:

- `@lru_cache(maxsize=1024)` on `_resolve_artifact_file()`
- `clear_cache()` now also clears the artifact-path cache

Effect:

- repeated artifact-path relocation checks no longer rescan the filesystem on every call
- cache is explicitly invalidated when the app already refreshes reporting state

### 3. SQLite write-path retry for run memory

**File:** `src/run_memory.py`

Added:

- short retry loop in `_conn()` for transient locked DB cases
- preserved existing WAL + busy timeout behavior
- clearer raised error message when the DB still cannot be opened

Effect:

- run registration/finalization is more resilient to brief lock contention

### 4. Orchestrator execution-state hardening

**File:** `src/run_orchestrator.py`

Added:

- explicit operator banner for `FLAT MODE`
- clearer operator banner for raw-mode fallback via `GFUP_FORCE_RAW=1`
- `busy_timeout` on inherited-GF DB reads
- guard for the case where the pipeline returns but leaves the run in `STARTED`

Behavior:

- if `run_pipeline()` returns and the run is still `STARTED`, the orchestrator now marks it `FAILED` with a clear reason instead of leaving ambiguous state behind

### 5. Non-fatal final-GF export lookup

**File:** `src/run_orchestrator.py`

Changed:

- failure in `export_final_gf()` lookup no longer downgrades an otherwise completed run
- it is recorded as a warning instead

Effect:

- post-run reporting issues do not misreport a completed pipeline as failed

---

## Validation

### Syntax

Passed:

```bash
python -m py_compile app.py src/reporting/data_loader.py src/run_memory.py src/run_orchestrator.py
```

### Import smoke

Passed:

```bash
python -c "from src.run_orchestrator import run_pipeline_controlled; from src.run_memory import _conn; print(...)"
```

Passed in supported app-style context:

```bash
python -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path('src').resolve())); from reporting.data_loader import clear_cache, load_run_context; ..."
```

### Full pipeline run

Passed:

```bash
python main.py
```

Observed result:

- latest run: `11`
- status: `COMPLETED`
- error: `None`
- registered artifacts: `33`

Required artifact set confirmed on run 11:

- `FLAT_GED`
- `FLAT_GED_RUN_REPORT`
- `FLAT_GED_DEBUG_TRACE`
- `FINAL_GF`
- `GF_TEAM_VERSION`

`load_run_context()` also successfully loaded run 11 in non-degraded artifact-first mode.

---

## Performance Notes

- Artifact-path relocation work is now cached instead of repeated.
- Locked SQLite reads now prefer retry before falling back.
- Locked SQLite writes now retry before failing.
- The full pipeline still takes several minutes on the user dataset; Step 16 improved resilience more than raw throughput.

---

## Reliability Score

**8.8 / 10**

Reasoning:

- end-to-end run succeeds
- latest run finalizes correctly
- required artifacts register correctly
- DB access is more tolerant of transient contention
- operator logs are clearer

Remaining deductions:

- openpyxl date warnings still appear during reads
- direct package-style imports of reporting modules still depend on the established `src/` path bootstrap model
- older historical runs `7`, `8`, and `9` remain `STARTED`

---

## Step 17 Readiness

**Step 17 can begin.**

Step 16 did not expose any new structural blocker. The current state is suitable for the next cleanup or acceptance step.
