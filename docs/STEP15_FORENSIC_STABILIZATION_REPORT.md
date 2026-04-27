# STEP15 Forensic Stabilization Report

Date: 2026-04-27

## Scope

Forensic stabilization pass only.

- No business logic rewrites
- No architecture redesign
- No pipeline/UI redesign
- No full pipeline run

## Files Checked

- Python files compiled: `81`
- Targeted high-risk files reviewed directly:
  - `main.py`
  - `src/run_orchestrator.py`
  - `src/pipeline/paths.py`
  - `src/flat_ged/__init__.py`
  - `src/flat_ged_runner.py`
  - `src/pipeline/runner.py`
  - `src/pipeline/stages/stage_build_team_version.py`
  - `src/reporting/data_loader.py`
  - `src/writer.py`
  - `src/flat_ged/writer.py`

## Audit Results

### 1. Syntax / compile audit

- `python -m py_compile` equivalent run across all repo Python files outside excluded runtime/archive areas
- Result: `81` files checked, `0` compile failures

### 2. Truncation / corruption audit

Checked for:

- null bytes
- missing trailing newline
- syntax failures
- likely truncation symptoms in high-risk files

Results:

- No null bytes found in targeted high-risk files
- No syntax failures found
- No evidence of current truncation in:
  - `main.py`
  - `src/run_orchestrator.py`
  - `src/pipeline/paths.py`
  - `src/flat_ged/__init__.py`
  - `src/flat_ged_runner.py`
  - `src/pipeline/runner.py`
  - `src/pipeline/stages/stage_build_team_version.py`
  - `src/reporting/data_loader.py`
  - `src/writer.py`
  - `src/flat_ged/writer.py`

Non-blocking file-integrity observations:

- `src/reporting/focus_filter.py` has no trailing newline
- `src/pipeline/stages/stage_write_gf.py` has no trailing newline

These are formatting anomalies, not runtime blockers.

### 3. Import isolation audit

#### Before fix

This smoke failed:

```bash
python -c "from src.flat_ged_runner import build_flat_ged_artifacts; from writer import GFWriter; print('OK')"
```

Failure:

- `ModuleNotFoundError: No module named 'writer'`

This exposed a runtime contract gap: the flat GED wrapper could be imported as
`src.flat_ged_runner`, but legacy bare imports such as `from writer import GFWriter`
were not guaranteed to resolve unless `main.py` had already inserted `src/` into
`sys.path`.

#### Fix applied

File fixed:

- `src/flat_ged_runner.py`

Exact fixes:

1. Added a minimal `src/` path bootstrap on import:
   - inserts the wrapper's parent `src/` directory into `sys.path` if absent
   - this is structural/runtime only
   - no business logic changed

2. Added best-effort UTF-8 console normalization in the wrapper before builder execution:
   - reconfigures `stdout` / `stderr` to UTF-8 when supported
   - avoids Windows `cp1252` console crashes during builder summary printing
   - no builder business rules changed

### 4. Import isolation verification after fix

Passed:

```bash
python -c "import sys; sys.path.insert(0,'src'); from writer import GFWriter; print(GFWriter)"
```

Passed:

```bash
python -c "from src.flat_ged_runner import build_flat_ged_artifacts; from writer import GFWriter; print('OK', GFWriter)"
```

Observed during package import:

- importing `src.flat_ged` does not leave bare `writer` stuck in `sys.modules`
- `src/flat_ged/__init__.py` cleanup behavior appears effective

### 5. Controlled flat GED smoke

Repo-local smoke run executed through:

```bash
build_flat_ged_artifacts(Path('input/GED_export.xlsx'), Path('.forensic_flat_smoke'))
```

Result:

- completed successfully
- produced:
  - `FLAT_GED.xlsx`
  - `DEBUG_TRACE.csv`
  - `run_report.json`
- wrapper returned structured result successfully
- `from writer import GFWriter` still resolved correctly after the builder call

Smoke scratch directory was removed after verification.

### 6. Prompt-requested smoke checks

Passed:

```bash
python -c "from src.flat_ged import build_flat_ged; print(build_flat_ged)"
```

Passed:

```bash
python -c "import main; print(main.RUN_MEMORY_CORE_VERSION)"
```

Observed value:

- `P1`

Passed:

```bash
python -c "from src.run_orchestrator import run_pipeline_controlled; print(run_pipeline_controlled)"
```

## Files Fixed

- `src/flat_ged_runner.py`

## Remaining Blockers

Structural/runtime blockers found in this pass:

- `0`

Non-blocking notes:

- repo worktree is dirty in unrelated areas outside this forensic pass
- full end-to-end pipeline validation was not executed in this pass
- two files without trailing newline remain as formatting-only anomalies

## Can `python main.py` now be run from Windows terminal?

Assessment: `Yes, structurally it can.`

Reasoning:

- `main.py` compiles
- `src/run_orchestrator.py` compiles and imports
- `src/pipeline/paths.py` exposes `RUN_MEMORY_CORE_VERSION`
- flat GED wrapper import isolation is repaired
- Windows console UTF-8 issue observed in wrapper smoke is mitigated in `src/flat_ged_runner.py`
- `main.py` already reconfigures console streams to UTF-8

This report does not claim full business-level pipeline success; it confirms that
the previously suspected structural/runtime corruption blockers have been cleared.

## Can Step 15 validation resume?

Assessment: `Yes.`

Reason:

- no current truncation evidence was found in the audited runtime-critical files
- compile/import audit is clean
- flat GED wrapper runtime contract is stabilized
- no structural blocker remains from this forensic pass
