# FLAT BUILDER INTEGRATION AUDIT

**Version:** 1.0  
**Created:** 2026-04-26 (CLEAN Step 5)  
**Owner:** Eid  
**Status:** FINAL — feeds Step 6 Orchestrator Design Spec and Step 7 Implementation

---

## 1. Executive Summary

**Verdict: Builder is READY for orchestrator integration.**

The frozen Flat GED builder (`src/flat_ged/`) exposes a clean Python API (`build_flat_ged()`) that can be called from a thin wrapper module (`src/flat_ged_runner.py`) without touching any builder business logic.

Three findings require explicit handling in Steps 6/7:

1. **File name mismatch:** Builder writes `run_report.json`; Clean IO Contract requires `flat_ged_run_report.json`. The wrapper must rename the file after the builder completes.
2. **`sys.exit()` on fatal error:** The builder calls `sys.exit()` (not `raise`) for unrecoverable parse errors. The wrapper must catch `SystemExit` to prevent process termination.
3. **Path migration:** `FLAT_GED_FILE` currently points to `input/FLAT_GED.xlsx`. After Step 7, it must point to `output/intermediate/FLAT_GED.xlsx` (generated automatically, not user-provided).

Everything else is wiring and path configuration — no business logic changes are required.

---

## 2. Builder API Inventory

| Item | Value |
|------|-------|
| Import path | `from src.flat_ged import build_flat_ged` |
| Function name | `build_flat_ged` |
| Module | `src/flat_ged/__init__.py` |
| Delegate | `_cli.run_batch(args, output_dir)` or `_cli.run_single(args, output_dir)` (cli.py = renamed main.py from upstream) |
| Snapshot version | v1.0 (2026-04-23, no-git-history) |

**Signature:**

```python
def build_flat_ged(
    ged_xlsx_path: Path,
    output_dir: Path,
    *,
    mode: str = "batch",       # "batch" or "single"
    numero: int | None = None, # [single mode] document NUMERO
    indice: str | None = None, # [single mode] document INDICE
) -> dict:
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ged_xlsx_path` | `Path` | Yes | Path to `GED_export.xlsx` |
| `output_dir` | `Path` | Yes | Target directory (created by builder if absent) |
| `mode` | `str` | No (default `"batch"`) | `"batch"` or `"single"` |
| `numero` | `int \| None` | No (required in single) | Document NUMERO |
| `indice` | `str \| None` | No (required in single) | Document INDICE (e.g. `"A"`, `"B"`) |

**Return value:**

`dict` — parsed contents of `run_report.json` written by the builder. Contains:

```json
{
  "mode":                    "batch",
  "input_file":              "...",
  "data_date":               "YYYY-MM-DD",
  "total_rows_scanned":      6901,
  "rows_excluded_no_numero": 0,
  "unique_doc_codes":        4848,
  "docs_with_duplicates":    0,
  "synthetic_sas_count":     0,
  "pending_sas_count":       0,
  "closure": {
    "MOEX_VISA":             0,
    "ALL_RESPONDED_NO_MOEX": 0,
    "WAITING_RESPONSES":     0
  },
  "success_count": 4848,
  "skipped_count": 0,
  "failure_count": 0,
  "warning_count": 0,
  "failures": [],
  "timers": {}
}
```

**Side effects (batch mode):**

- Creates `output_dir` if absent
- Writes `output_dir/FLAT_GED.xlsx` (2 sheets: GED_RAW_FLAT, GED_OPERATIONS; write_only streaming)
- Writes `output_dir/DEBUG_TRACE.csv` (CSV, utf-8-sig for Excel BOM)
- Writes `output_dir/run_report.json`

**Side effects (single mode):**

- Creates `output_dir` if absent
- Writes `output_dir/FLAT_GED.xlsx` (3 sheets: GED_RAW_FLAT, GED_OPERATIONS, DEBUG_TRACE; full cell styling)
- Writes `output_dir/run_report.json`
- **No separate `DEBUG_TRACE.csv`** in single mode

**Critical: fatal error behavior:**

The builder calls `sys.exit(str(e))` (not `raise`) for unrecoverable errors. This means `build_flat_ged()` will terminate the entire Python process on parse failure if not intercepted. The wrapper must catch `SystemExit`.

---

## 3. CLI Inventory

The builder can be run directly as a CLI script via `src/flat_ged/cli.py` (the upstream `main.py`, renamed during vendoring):

```bash
# Batch mode — all documents
python -m src.flat_ged.cli --input input/GED_export.xlsx --output output/intermediate --mode batch

# Batch mode — smoke test (no XLSX output, JSON report only, ~2x faster)
python -m src.flat_ged.cli --input input/GED_export.xlsx --output output/intermediate --mode batch --skip-xlsx

# Single mode — debug one document
python -m src.flat_ged.cli --input input/GED_export.xlsx --output output/intermediate --mode single \
    --numero 248000 --indice A

# Single mode with row override
python -m src.flat_ged.cli --input input/GED_export.xlsx --output output/intermediate --mode single \
    --numero 248000 --indice A --row-index 1842
```

**CLI flags summary:**

| Flag | Required | Description |
|------|----------|-------------|
| `--input` | Yes | Path to GED_export.xlsx |
| `--output` | No (default `output/`) | Output directory |
| `--mode` | No (default `batch`) | `batch` or `single` |
| `--numero` | Single only | Document NUMERO (int) |
| `--indice` | Single only | Document INDICE (str) |
| `--row-index` | No | Override candidate selection by GED row index |
| `--skip-xlsx` | No | Batch only: skip FLAT_GED.xlsx, write run_report.json only |

**Exit behavior:** exits 0 on success, non-zero on `sys.exit()` call (fatal parse error).

**Note:** The CLI is NOT the integration path for Step 7. The Python API (`build_flat_ged()`) is the correct integration point. The CLI is useful for developer smoke testing.

---

## 4. Input Contract

| Requirement | Actual Source | Risk | Orchestrator Handling |
|-------------|--------------|------|-----------------------|
| GED file exists | `reader.open_workbook_fast(path)` | HIGH — `GEDParseError` → `sys.exit()` if missing | Validate file exists before calling builder; catch `SystemExit` |
| GED file is a valid `.xlsx` | `openpyxl.load_workbook(read_only=True)` | HIGH — openpyxl raises on corrupt file | Catch `SystemExit` from builder |
| GED file not locked by Excel | openpyxl open | MEDIUM — Windows file lock causes read failure | Pre-check: open in binary read mode, close; catch `SystemExit` |
| Sheet `"Détails"` exists | `reader.read_data_date_fast()` | HIGH — `sys.exit("[FAIL] Sheet 'Détails' not found.")` | Catch `SystemExit` |
| `Détails!D15` contains a date | `reader.read_data_date_fast()` | HIGH — `sys.exit()` if D15 is None or not a date | Catch `SystemExit` |
| Sheet `"Doc. sous workflow, x versions"` exists | `reader.read_ged_sheet()` | HIGH — `sys.exit("[FAIL] Sheet '…' not found in workbook.")` | Catch `SystemExit` |
| GED sheet has NUMERO and INDICE columns | `_stream_group_rows()` | HIGH — `sys.exit("[FAIL] NUMERO or INDICE column not found")` | Catch `SystemExit` |
| GED sheet has at least 2 header rows | `parse_ged_header_batch()` | HIGH — `GEDParseError` on empty sheet | Catch `SystemExit` |
| `src/flat_ged/input/source_main/*.py` present | `config.py` imports at module load | HIGH — `ImportError` if path broken | Verified intact at `src/flat_ged/input/source_main/`; do not move |
| `output_dir` writeable | `output_dir.mkdir(parents=True, exist_ok=True)` | LOW — builder creates it | Ensure parent `output/intermediate/` is on a writeable path |

**Fragile assumptions identified:**

- The GED sheet name `"Doc. sous workflow, x versions"` is hard-coded in `ged_parser_contract.py`. If Jansa renames the sheet, the builder will fail with `sys.exit()`.
- `Détails!D15` date cell position is hard-coded. If the Détails sheet layout changes, the builder will fail silently (reads wrong cell) or with `sys.exit()`.
- The source_main files at `src/flat_ged/input/source_main/` must not be moved. `config.py` resolves the path at import time relative to `__file__`.

---

## 5. Output Contract

| Artifact | Actual Filename | Target Filename (Clean IO Contract) | Batch? | Single? | Consumed By | Notes |
|----------|----------------|--------------------------------------|--------|---------|-------------|-------|
| Flat GED workbook | `FLAT_GED.xlsx` | `FLAT_GED.xlsx` | ✅ | ✅ | `stage_read_flat` via `ctx.FLAT_GED_FILE` | Batch: 2 sheets; Single: 3 sheets (includes DEBUG_TRACE) |
| Debug trace | `DEBUG_TRACE.csv` | `DEBUG_TRACE.csv` | ✅ | ❌ (in XLSX sheet) | Developer inspection, parity harness | CSV: 90× faster than Excel for 400k+ rows |
| Run report | **`run_report.json`** | **`flat_ged_run_report.json`** | ✅ | ✅ | Artifact registration (Step 8), orchestrator result | **⚠ NAME MISMATCH — wrapper must rename** |

**Contract mismatch resolution:**

The Clean IO Contract (`docs/CLEAN_IO_CONTRACT.md`) specifies `flat_ged_run_report.json`. The builder writes `run_report.json`. The wrapper (`src/flat_ged_runner.py`) must rename `run_report.json` → `flat_ged_run_report.json` after the builder completes. Do NOT modify the builder.

```python
# In wrapper: after build_flat_ged() returns
src = intermediate_dir / "run_report.json"
dst = intermediate_dir / "flat_ged_run_report.json"
src.rename(dst)
```

**What `stage_read_flat` requires:**

`stage_read_flat.py` reads `ctx.FLAT_GED_FILE` (path to `FLAT_GED.xlsx`) and loads sheets `GED_RAW_FLAT` and `GED_OPERATIONS`. It does not consume `DEBUG_TRACE.csv` or `run_report.json` directly. The report and trace are consumed only by artifact registration (Step 8).

---

## 6. Performance / Scalability

| Metric | Value | Source |
|--------|-------|--------|
| GED rows scanned | ~6,901 | Step 2 smoke test (2026-04-23) |
| Documents processed | ~4,848 | Step 2 smoke test |
| Full batch runtime (batch mode) | ~32 seconds | Post CSV-debug optimization |
| DEBUG_TRACE rows | ~400,000+ | Confirmed by writer comment: "400k rows / 0.5s as CSV vs 47s in Excel" |
| DEBUG_TRACE CSV write time | ~0.5 seconds | writer.py comment |
| FLAT_GED.xlsx write time (batch, write_only) | Included in 32s | Estimated 2–5s for 2-sheet streaming write |

**Key performance design decisions already in place:**

- Batch mode uses `openpyxl read_only=True` (SAX streaming, ~40× faster open)
- Single-pass row streaming: all 6,901 rows iterated exactly once, grouped by `(numero, indice)` in memory
- DEBUG_TRACE written as CSV (not as Excel sheet) to avoid the 47-second write cost
- FLAT_GED.xlsx uses `write_only=True` streaming mode (no per-cell fill in batch — headers only are styled)

**Large file risk:** If GED grows significantly (2×–3×), runtime scales roughly linearly. At 20,000+ rows, memory overhead of holding all `all_ops` rows in RAM before the batch write could become an issue. Not a concern for current dataset.

---

## 7. Failure Modes and Required Handling

| Failure | Detection | Severity | Required Behavior |
|---------|-----------|----------|-------------------|
| GED file missing | `open_workbook_fast` → `GEDParseError` → `sys.exit()` | FATAL | Catch `SystemExit`; raise `RuntimeError("GED file not found: …")`; stop run |
| GED file locked (Windows) | openpyxl open error → `sys.exit()` | FATAL | Catch `SystemExit`; tell user to close Excel; stop run |
| GED file corrupt / not xlsx | openpyxl open error → `sys.exit()` | FATAL | Catch `SystemExit`; raise with file path; stop run |
| `Détails` sheet missing | `GEDParseError` → `sys.exit()` | FATAL | Catch `SystemExit`; stop run |
| `Détails!D15` empty or not a date | `GEDParseError` → `sys.exit()` | FATAL | Catch `SystemExit`; stop run |
| GED workflow sheet missing | `GEDParseError` → `sys.exit()` | FATAL | Catch `SystemExit`; stop run |
| NUMERO / INDICE column missing | `sys.exit("[FAIL] NUMERO or INDICE…")` | FATAL | Catch `SystemExit`; stop run |
| Per-document validation error | `GEDValidationError` / `Exception` → counted in `failure_count` | SOFT | Builder continues; wrapper checks `failure_count > 0` after return; warn or stop per policy |
| `failure_count > 0` in report | Checked in wrapper from returned dict | CONFIGURABLE | Default: warn but allow pipeline to proceed; Option: block if failure_count above threshold |
| `output/intermediate/` not writeable | `mkdir` / file write error | FATAL | Standard Python `IOError`; stop run |
| Partial output (builder crashed mid-write) | Missing expected files after `build_flat_ged()` | FATAL | Wrapper checks all 3 output files exist; clean up partial outputs; stop run |
| DEBUG_TRACE.csv missing (batch mode) | File check after builder | WARNING | Log warning; continue (CSV is not consumed by pipeline) |
| `run_report.json` missing | `json.load(report_path)` raises `FileNotFoundError` | FATAL | Already caught by `__init__.py`; re-raises; stop run |
| `source_main/*.py` import failure | `ImportError` at `config.py` load | FATAL | Indicates repo corruption; stop run; note files in error |

**Critical implementation note:** Because the builder uses `sys.exit()` (not `raise`) for fatal errors, the wrapper MUST wrap the `build_flat_ged()` call in a `try/except SystemExit` block. Failure to do so will terminate the entire `python main.py` process without any run cleanup, without writing a failure artifact, and without surfacing a useful error to the UI.

---

## 8. Proposed Step 6/7 Wiring

### New module: `src/flat_ged_runner.py`

This module is the ONLY integration point between the orchestrator and the frozen builder. It is thin by design — no business logic.

**Result dataclass:**

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class FlatGedBuildResult:
    flat_ged_path: Path           # output/intermediate/FLAT_GED.xlsx
    debug_trace_path: Path | None # output/intermediate/DEBUG_TRACE.csv (batch only)
    run_report_path: Path         # output/intermediate/flat_ged_run_report.json
    data_date: str | None         # ISO date string from report
    success_count: int | None
    failure_count: int | None
    elapsed_seconds: float | None
```

**Wrapper function:**

```python
import time
from pathlib import Path
from src.flat_ged import build_flat_ged
from src.flat_ged_runner import FlatGedBuildResult

def build_flat_ged_artifacts(
    ged_path: Path,
    intermediate_dir: Path,
) -> FlatGedBuildResult:
    """
    Build Flat GED artifacts from GED_export.xlsx.

    Calls the frozen builder in batch mode. Renames run_report.json to
    flat_ged_run_report.json. Validates all expected outputs exist.

    Does NOT modify any builder business logic.

    Raises:
        RuntimeError: on any unrecoverable failure (wraps sys.exit or missing files)
    """
    intermediate_dir = Path(intermediate_dir)
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    try:
        report = build_flat_ged(ged_path, intermediate_dir, mode="batch")
    except SystemExit as e:
        raise RuntimeError(
            f"Flat GED builder exited with error: {e}"
        ) from None

    elapsed = time.time() - t0

    # Rename run_report.json → flat_ged_run_report.json (contract compliance)
    raw_report = intermediate_dir / "run_report.json"
    final_report = intermediate_dir / "flat_ged_run_report.json"
    if raw_report.exists():
        raw_report.rename(final_report)
    elif not final_report.exists():
        raise RuntimeError("Builder did not produce run_report.json")

    # Validate required outputs
    flat_ged = intermediate_dir / "FLAT_GED.xlsx"
    debug_csv = intermediate_dir / "DEBUG_TRACE.csv"
    if not flat_ged.exists():
        raise RuntimeError("Builder did not produce FLAT_GED.xlsx")

    return FlatGedBuildResult(
        flat_ged_path=flat_ged,
        debug_trace_path=debug_csv if debug_csv.exists() else None,
        run_report_path=final_report,
        data_date=report.get("data_date"),
        success_count=report.get("success_count"),
        failure_count=report.get("failure_count"),
        elapsed_seconds=elapsed,
    )
```

### Integration in `run_orchestrator.py`

The call goes into `run_pipeline_controlled()`, before `_patched_main_context` enters:

```python
# Step 1: Validate GED input (existing code)
# Step 2: Build Flat GED (NEW — Step 7)
intermediate_dir = Path(main_module.OUTPUT_DIR) / "intermediate"
build_result = build_flat_ged_artifacts(
    ged_path=Path(ged_path),
    intermediate_dir=intermediate_dir,
)
if build_result.failure_count and build_result.failure_count > 0:
    warnings.append(
        f"Flat GED builder: {build_result.failure_count} document(s) failed"
    )

# Step 3: Override FLAT_GED_FILE + FLAT_GED_MODE on main_module
main_module.FLAT_GED_FILE = build_result.flat_ged_path
main_module.FLAT_GED_MODE = "flat"

# Step 4: Run pipeline (existing code — pipeline reads from main_module namespace)
with _patched_main_context(main_module, execution_context):
    main_module.run_pipeline(verbose=True)
```

**Why `FLAT_GED_MODE` is set on `main_module` (not in paths.py):**
`runner.py` reads `getattr(ns, "FLAT_GED_MODE", "raw")` from the calling module's namespace. Setting it on `main_module` before calling `run_pipeline()` is exactly the pattern already used by `_run_one_mode.py` (the parity harness script). No change to `runner.py` is needed.

### Where artifacts are registered (Step 8 responsibility)

After `stage_finalize_run` in the pipeline, `src/flat_ged_runner.py` should expose the `FlatGedBuildResult` so `run_orchestrator.py` can register:

| Artifact type | File |
|---------------|------|
| `FLAT_GED` | `output/intermediate/FLAT_GED.xlsx` |
| `FLAT_GED_DEBUG_TRACE` | `output/intermediate/DEBUG_TRACE.csv` |
| `FLAT_GED_RUN_REPORT` | `output/intermediate/flat_ged_run_report.json` |

This is Step 8 work. The `FlatGedBuildResult` object returned by `build_flat_ged_artifacts()` provides all the file paths needed.

---

## 9. Path Migration Notes

| State | FLAT_GED_FILE value | Who sets it | Status |
|-------|---------------------|-------------|--------|
| **Current (temporary)** | `input/FLAT_GED.xlsx` | `paths.py` default | User manually places file — **WRONG per contract** |
| **Target (Step 7)** | `output/intermediate/FLAT_GED.xlsx` | `run_orchestrator.py` after calling `build_flat_ged_artifacts()` | Auto-generated — correct |

**Path migration steps (Step 7 implementation):**

1. `paths.py`: Do NOT change `FLAT_GED_FILE` default. The orchestrator overrides it on `main_module` at runtime. The default stays as a fallback only.
2. `run_orchestrator.py`: After calling `build_flat_ged_artifacts()`, set `main_module.FLAT_GED_FILE = build_result.flat_ged_path`.
3. `run_orchestrator.py`: Set `main_module.FLAT_GED_MODE = "flat"` to activate flat read path.
4. `output/intermediate/` creation: handled by `build_flat_ged_artifacts()` (calls `intermediate_dir.mkdir(parents=True, exist_ok=True)`).

**Cleanup policy:**

- Old files in `output/intermediate/` from previous runs: leave in place. The builder overwrites `FLAT_GED.xlsx`, `DEBUG_TRACE.csv`, and `run_report.json` → `flat_ged_run_report.json` on each run. No pre-deletion needed.
- On failure: partial output files (e.g. `FLAT_GED.xlsx` written but `run_report.json` missing) should be removed by the wrapper before raising. This prevents a stale `FLAT_GED.xlsx` from a failed run being consumed by the pipeline.

**DEBUG_TRACE copy to runs/:**

The Clean IO Contract permits copying `DEBUG_TRACE.csv` into `runs/run_NNNN/` for immutable archiving. This is Step 8 work (artifact registration). The wrapper does not do this — it only confirms the file exists.

---

## 10. Protected / Off-Limits Items

The following must NEVER be modified in Steps 6, 7, or 8:

| File / folder | Protected because |
|---------------|-------------------|
| `src/flat_ged/config.py` | Business constants: SAS_WINDOW_DAYS=15, GLOBAL_WINDOW_DAYS=30. Change upstream only. |
| `src/flat_ged/resolver.py` | Candidate selection logic. Frozen. |
| `src/flat_ged/transformer.py` | Core GED row transformation. Frozen. |
| `src/flat_ged/validator.py` | Delay invariant checks. Frozen. |
| `src/flat_ged/utils.py` | Pure helpers. Frozen. |
| `src/flat_ged/reader.py` | GED file parser. Frozen. |
| `src/flat_ged/writer.py` | Output file generation: FLAT_GED.xlsx, DEBUG_TRACE.csv, run_report.json. Frozen. |
| `src/flat_ged/cli.py` | CLI entry point. Frozen (import path fixes only per BUILD_SOURCE.md). |
| `src/flat_ged/input/source_main/` | Mapping files. Change upstream only. |
| `src/flat_ged/VERSION.txt` | Only updated when upstream builder is re-synced. |
| `docs/FLAT_GED_CONTRACT.md` | Frozen unless a genuine contract mismatch is found and documented. |
| Delay computation logic | SAS_WINDOW_DAYS, GLOBAL_WINDOW_DAYS, `check_delay_invariants`, `check_global_delay_consistency`. Must not be recomputed or overridden. |
| Duplicate resolution logic | `resolve_from_group`, `resolve_document`. Frozen. |
| DEBUG_TRACE column semantics | 23 columns exactly as defined in `D_COLS` (writer.py). Do not add/remove. |

---

## 11. Open Questions

None that block Step 6 or Step 7.

**Tracked but deferred:**

- `failure_count > 0` policy: should the orchestrator block the pipeline run if some documents failed in the builder? Current recommendation: warn and allow (single-doc failures are non-fatal for the portfolio). Eid to confirm at Step 7 implementation.
- Single mode integration: `build_flat_ged_artifacts()` uses batch mode only. Single mode (debug) remains a developer CLI tool. No change needed.
- `skip_xlsx=True` path: the builder supports a fast smoke-test mode that skips FLAT_GED.xlsx. Not exposed in `build_flat_ged_artifacts()`. Available as a future optimization if needed (e.g. pre-flight validation before committing to a full run).

---

## 12. Step 6 Inputs

The Orchestrator Flat Mode Spec (Step 6) can be written directly from this document. Concrete inputs:

- **Default mode is flat.** After Step 7, `FLAT_GED_MODE` is always set to `"flat"` by the orchestrator. Raw mode (`"raw"`) is developer fallback only (requires manually placing `input/FLAT_GED.xlsx` and setting `FLAT_GED_MODE="raw"` in the calling script).
- **Flat GED is built automatically** from `input/GED_export.xlsx` by `build_flat_ged_artifacts(ged_path, intermediate_dir)`.
- **`FLAT_GED_MODE` and `FLAT_GED_FILE` are set on `main_module`** (not in `paths.py`) so they override the defaults without touching the file. This is already the established pattern from `_run_one_mode.py`.
- **Fatal failures stop the run cleanly.** `SystemExit` is caught; `run_orchestrator.run_pipeline_controlled()` returns `{"success": False, "errors": [...], ...}`.
- **Soft failures are warned.** `failure_count > 0` adds a warning to the result dict but does not stop the run (pending Eid policy confirmation).
- **All run modes (GED_ONLY, GED_GF, GED_REPORT, FULL) use flat mode internally.** The mode switch happens before the pipeline reads the GED — it is invisible to the run mode logic.
- **Artifacts registered as:** `FLAT_GED`, `FLAT_GED_DEBUG_TRACE`, `FLAT_GED_RUN_REPORT` (Step 8 work).
- **`output/intermediate/` is created by the wrapper.** The orchestrator does not need to pre-create it.
- **`FlatGedBuildResult` carries all paths** for downstream registration.

---

*CLEAN Step 5 — audit only. No code changes. All findings validated by direct source read.*
