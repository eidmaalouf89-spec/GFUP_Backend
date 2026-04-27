# STEP15 Late Failure Fix Report

Date: 2026-04-27

## 1. Root Cause

Step 15 had two late-stage null-handling failures in pipeline terminal stages:

1. `stage_diagnosis` assumed `gf_sas_lookup` and `wf_engine` were always present.
   In the flat-mode path they could be `None`, which caused the first crash during
   INSERT LOG construction.

2. `stage_finalize_run` assumed `persisted_df` and `ancien_df` were always present.
   In the flat-mode path one or both could be `None`, which caused the summary/finalization
   block to fail even after outputs and artifact registration had completed.

Because of (2), runs could physically produce outputs and register artifacts but still
remain `STARTED` instead of transitioning to `COMPLETED`.

## 2. Exact Line

### First late failure

File:

- `src/pipeline/stages/stage_diagnosis.py`

Exact failing line observed from direct pipeline traceback:

- line `106`

Code:

```python
_sas_entry = gf_sas_lookup.get(_doc_id, {})
```

Observed error:

```text
AttributeError: 'NoneType' object has no attribute 'get'
```

### Second late finalization blocker

File:

- `src/pipeline/stages/stage_finalize_run.py`

The finalize block emitted:

```text
[WARN] Run history finalize error (non-fatal): object of type 'NoneType' has no len()
```

The failing summary fields were the `len(...)` calls on nullable values:

```python
"final_gf_rows": int(len(dernier_df_for_gf) + len(ancien_df)),
"consultant_report_memory_rows_loaded": int(len(persisted_df)),
```

## 3. Files Changed

- `src/pipeline/stages/stage_diagnosis.py`
- `src/pipeline/stages/stage_finalize_run.py`

## 4. Exact Fixes

### `src/pipeline/stages/stage_diagnosis.py`

Applied minimal null-safe guards only:

```python
gf_sas_lookup = ctx.gf_sas_lookup or {}
```

and

```python
if _doc_id and wf_engine is not None:
    _visa_global, _date_reel_visa = wf_engine.compute_visa_global_with_date(_doc_id)
```

### `src/pipeline/stages/stage_finalize_run.py`

Applied minimal null-safe summary guards only:

```python
"final_gf_rows": int(len(dernier_df_for_gf) + (len(ancien_df) if ancien_df is not None else 0)),
"consultant_report_memory_rows_loaded": int(len(persisted_df)) if persisted_df is not None else 0,
```

No business logic was changed.

## 5. Validation Result

### Compile

Passed:

```text
python -m py_compile src/pipeline/stages/stage_diagnosis.py src/pipeline/stages/stage_finalize_run.py
```

### Full run from Windows shell context

Executed:

```text
python main.py
```

Validated result in `data/run_memory.db`:

- latest completed run: `run_number = 10`
- status: `COMPLETED`
- error_message: `None`

### Required artifacts for Step 15

Registered on run `10`:

- `FLAT_GED`
- `FLAT_GED_RUN_REPORT`
- `FLAT_GED_DEBUG_TRACE`
- `FINAL_GF`
- `GF_TEAM_VERSION`

Additional result:

- total registered artifacts on run `10`: `33`

## 6. Is Step 15 Now PASS?

Assessment: `Yes`

Reason:

- latest run is `COMPLETED`
- no runtime exception remains in the previously failing late stages
- all required artifacts are registered in run memory for the latest run

## 7. Notes

- Older runs `7`, `8`, and `9` remain in `STARTED` state from earlier failed attempts.
  They do not block the Step 15 pass because run `10` is the latest valid completed run.
- Openpyxl emitted non-blocking date warnings during the run; they did not prevent completion.
