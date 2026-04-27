# STEP04_VALIDATION.md
## Step 04 — Source Loader: Validation Report

**Date:** 2026-04-27
**Status:** ✅ COMPLETE — All 7 tests passed (235s / ~4 min on local machine)

---

## What Was Analyzed

- `docs/CHAIN_ONION_MASTER_STRATEGY.md` — architecture, protected files, output targets
- `docs/STEP01_SOURCE_MAP.md` — identity model, GED_OPERATIONS (37 cols), DEBUG_TRACE (23 cols), integration risks
- `docs/STEP02_CHAIN_CONTRACT.md` — authoritative return key (`"ops_df"`), key schema per DataFrame
- `docs/STEP03_ONION_CONTRACT.md` — onion layer model (not implemented here; documented for awareness)
- `docs/STEP03_5_BACKLOG_SEGMENTATION.md` — portfolio bucket segmentation rules (consumed by Step 07)
- `src/query_library.py` — `_PRIMARY_APPROVER_KEYWORDS`, `_is_primary_approver()`, `QueryContext`
- `src/effective_responses.py` — `build_effective_responses()` signature and `effective_source` vocabulary
- `src/flat_ged/input/source_main/consultant_mapping.py` — `EXCEPTION_COLUMNS` (32 entries), `RAW_TO_CANONICAL`
- `src/flat_ged/config.py` — phase window constants
- `src/pipeline/stages/stage_read_flat.py` — bool normalization pattern, SAS filter, response composition

---

## Files Inspected

| File | Purpose |
|------|---------|
| `output/intermediate/FLAT_GED.xlsx` | Live artifact — GED_OPERATIONS sheet (32,099 rows, 37 cols) |
| `output/intermediate/DEBUG_TRACE.csv` | Live artifact — batch debug log (407,288 rows, 23 cols) |
| `data/report_memory.db` | Optional SQLite — persisted report responses (not present in this env) |
| `src/flat_ged/input/source_main/consultant_mapping.py` | Exception column definitions |
| `src/effective_responses.py` | Effective response composition logic |
| `src/pipeline/stages/stage_read_flat.py` | Bool normalization and response build patterns |

---

## What Was Created / Modified

### Created

| File | Description |
|------|-------------|
| `src/chain_onion/__init__.py` | Package init; version `0.1.0-step04` |
| `src/chain_onion/source_loader.py` | Read-only normalized source loader (~340 lines) |
| `tests/test_chain_onion_loader.py` | 6-test validation suite (Test 3 has 2 sub-cases = 7 pytest items) |
| `docs/STEP04_VALIDATION.md` | This file |

### Not Modified

- `src/flat_ged/*` — untouched (protected)
- All existing pipeline stages — untouched
- `CHAIN_ONION_STEP_TRACKER.md` — updated only (status field)

---

## Loader Behavior

### `load_flat_ged(path) → pd.DataFrame`
- Reads sheet `GED_OPERATIONS` from FLAT_GED.xlsx with `dtype=str`
- Normalizes boolean columns (`is_completed`, `is_blocking`, `requires_new_cycle`) from string `"True"`/`"False"` to Python bools
- Validates required columns (raises `ValueError` if any missing)
- Adds `family_key = str(numero)`, `version_key = f"{numero}_{indice}"`
- **Result:** 32,099 rows, 39 columns (37 original + 2 identity keys)

### `load_debug_trace(path) → pd.DataFrame`
- Reads DEBUG_TRACE.csv with `encoding="utf-8-sig"`, `dtype=str`
- Derives `indice` by splitting `doc_code` on `"|"` — takes index `[1]`
- Adds `family_key`, `version_key` identically to ops_df
- Adds `instance_key = f"{version_key}_{submission_instance_id}"` where real id exists; falls back to `f"{version_key}_seq_{N}"` (synthetic sequential) for blank ids, with warning
- Returns empty DataFrame with correct 7-column schema if file is missing (no exception raised)
- **Result:** 407,288 rows, 27 columns (23 original + 4 derived: `indice`, `family_key`, `version_key`, `instance_key`)

### `load_effective_responses(ops_df, report_memory_db_path) → pd.DataFrame`
- Builds session-scoped UUID bridge: one `doc_id` per unique `(numero, indice)` pair
- Constructs `responses_df` from GED_OPERATIONS columns matching `build_effective_responses()` signature
- Loads persisted report_memory from SQLite if `db_path` exists; skips with log message if not
- Calls `build_effective_responses(flat_mode=True)` from `src/effective_responses.py`
- Attaches `family_key`/`version_key` via `id_to_pair` bridge; strips `doc_id` from output
- Returns empty DataFrame with `["family_key", "version_key"]` schema on any failure
- **Result (GED-only):** 27,251 rows — all `effective_source = "GED"`; 0 null family_key

### `load_chain_sources(flat_ged_path, debug_trace_path, report_memory_db_path, output_dir) → dict`
- Orchestrates all three loaders in sequence
- Creates `output/chain_onion/` directory (or custom `output_dir`)
- Returns:
  ```python
  {
      "ops_df":        pd.DataFrame,   # GED_OPERATIONS + family_key/version_key
      "debug_df":      pd.DataFrame,   # DEBUG_TRACE + all three identity keys
      "effective_df":  pd.DataFrame,   # composed effective responses + session keys
      "data_date":     str,            # ISO date string from ops_df["data_date"]
      "metadata":      dict,           # row_counts, paths, warnings, missing_sources,
                                       # exception_logic, debug_trace_available
  }
  ```

---

## Existing Exception Logic Found

| Property | Value |
|----------|-------|
| Found | ✅ Yes |
| Source file | `src/flat_ged/input/source_main/consultant_mapping.py` |
| Definition | `EXCEPTION_COLUMNS` — 32 GED column headers mapped to `"Exception List"` via `RAW_TO_CANONICAL` |
| BENTIN found | ❌ No — searched entire codebase, not present |
| Chain + Onion action | **None required.** Exception rows are excluded from GED_OPERATIONS by the upstream FLAT_GED builder. `ops_df` contains zero `actor_clean == "Exception List"` rows. Exception logic is documented in `metadata["exception_logic"]` only. |

---

## Test Results

| # | Test Name | Result | Notes |
|---|-----------|--------|-------|
| 1 | `test_all_sources_present` | ✅ PASSED | ops_df=32,099 rows, debug_df=407,288 rows |
| 2 | `test_debug_trace_missing` | ✅ PASSED | Empty debug_df with correct schema; warning in metadata |
| 3a | `test_effective_responses_graceful_on_empty_ops` | ✅ PASSED | Empty ops → empty effective_df, correct schema |
| 3b | `test_effective_responses_missing_db` | ✅ PASSED | 27,251 GED-only rows; 0 null family_key |
| 4 | `test_key_integrity` | ✅ PASSED | 0 null family_keys, 0 version_key mismatches, reproducible |
| 5 | `test_row_reconciliation` | ✅ PASSED | Row counts match direct reads; +2 cols ops_df, +4 cols debug_df |
| 6 | `test_exception_logic_metadata` | ✅ PASSED | `found=True`, `bentin_found=False`, 0 exception rows in ops_df |

**Suite total:** 7 passed, 0 failed, 0 skipped — 235s on local machine

---

## Warnings

- DEBUG_TRACE.csv takes ~3–4 minutes to load in local Python (407,288 rows). No workaround needed for production; sandbox-only limitation.
- `effective_df` uses session-scoped UUIDs for `doc_id` internally. These are **not** persisted to CSV and must not be used as stable identity keys in downstream steps. Use `family_key`/`version_key` only.
- `report_memory.db` was not present in this environment. `effective_df` is GED-only (all rows `effective_source = "GED"`). When the DB is connected, persisted report responses will be merged and `effective_source` values will vary.

---

## Ready for Step 05?

**Yes.**

- `load_chain_sources()` returns the exact dict shape specified in STEP02 contract
- All three DataFrames have correct identity key columns
- `ops_df` is the clean GED_OPERATIONS backbone needed by Step 05 (Family Grouping Engine)
- No exception list contamination in `ops_df`
- All 7 validation tests pass against live artifacts

### Blockers for Step 05

None. Proceed to `src/chain_onion/family_grouper.py`.

---

## Next Blockers (for downstream steps)

- **Step 06+:** `effective_df` only has GED-sourced responses until `report_memory.db` is connected. Timeline events from persisted memory will be absent.
- **Step 07:** `OPERATIONAL_HORIZON_DATE = 2025-09-01` must be applied to `ops_df["submittal_date"]` for portfolio bucket segmentation. The field is loaded and available.
- **Step 09+:** `_is_primary_approver()` keywords are loaded in `query_library.py` — no changes needed in Step 04.
