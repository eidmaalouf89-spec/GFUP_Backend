"""
tests/test_chain_onion_loader.py
---------------------------------
Validation tests for src/chain_onion/source_loader.py (Step 04).

Tests
-----
1. All sources present      — all loaders succeed with non-empty DataFrames
2. DEBUG_TRACE missing      — empty debug_df + warning only (no exception)
3. effective_df graceful    — empty ops_df path returns empty effective_df
4. Key integrity            — family_key/version_key/instance_key non-null and reproducible
5. Row reconciliation       — loaded counts match artifact row counts

Run from repo root:
    python -m pytest tests/test_chain_onion_loader.py -v
"""

import sys
import logging
from pathlib import Path

import pandas as pd
import pytest

# ── Ensure src/ is importable ──────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR   = _REPO_ROOT / "src"
for _p in (_REPO_ROOT, _SRC_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from chain_onion.source_loader import (  # type: ignore
    load_flat_ged,
    load_debug_trace,
    load_effective_responses,
    load_chain_sources,
)

# ── Artifact paths (live artifacts in output/intermediate/) ───────────────
_FLAT_GED_PATH    = _REPO_ROOT / "output" / "intermediate" / "FLAT_GED.xlsx"
_DEBUG_TRACE_PATH = _REPO_ROOT / "output" / "intermediate" / "DEBUG_TRACE.csv"
_REPORT_MEMORY_DB = _REPO_ROOT / "data" / "report_memory.db"

_ARTIFACTS_AVAILABLE = _FLAT_GED_PATH.exists()

logging.basicConfig(level=logging.WARNING)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — All sources present
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _ARTIFACTS_AVAILABLE, reason="FLAT_GED.xlsx not available")
def test_all_sources_present():
    """
    Expected: all loaders succeed; ops_df and debug_df are non-empty;
    family_key and version_key columns are present on all DataFrames.
    """
    result = load_chain_sources(
        flat_ged_path=_FLAT_GED_PATH,
        debug_trace_path=_DEBUG_TRACE_PATH,
        report_memory_db_path=_REPORT_MEMORY_DB if _REPORT_MEMORY_DB.exists() else None,
    )

    ops_df    = result["ops_df"]
    debug_df  = result["debug_df"]
    metadata  = result["metadata"]

    # ops_df must be non-empty and have identity keys
    assert not ops_df.empty, "ops_df is empty — GED_OPERATIONS load failed"
    assert "family_key"  in ops_df.columns, "family_key missing from ops_df"
    assert "version_key" in ops_df.columns, "version_key missing from ops_df"

    # debug_df must be non-empty and have all three identity keys
    assert not debug_df.empty, "debug_df is empty — DEBUG_TRACE load failed"
    assert "family_key"   in debug_df.columns, "family_key missing from debug_df"
    assert "version_key"  in debug_df.columns, "version_key missing from debug_df"
    assert "instance_key" in debug_df.columns, "instance_key missing from debug_df"

    # data_date must be a non-empty string
    assert result["data_date"], "data_date is empty"

    # metadata must report row counts
    assert metadata["row_counts"]["ops_df"] > 0
    assert metadata["row_counts"]["debug_df"] > 0

    # FLAT_GED must not be in missing_sources
    assert str(_FLAT_GED_PATH) not in str(metadata["missing_sources"])

    print(f"\n[Test 1] ops_df={len(ops_df)} rows, debug_df={len(debug_df)} rows, "
          f"data_date={result['data_date']}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — DEBUG_TRACE missing
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _ARTIFACTS_AVAILABLE, reason="FLAT_GED.xlsx not available")
def test_debug_trace_missing(tmp_path):
    """
    Expected: debug_df is empty with expected schema + warning in metadata.
    No exception raised. ops_df still loads normally.
    """
    nonexistent = tmp_path / "DEBUG_TRACE_MISSING.csv"

    result = load_chain_sources(
        flat_ged_path=_FLAT_GED_PATH,
        debug_trace_path=nonexistent,
        report_memory_db_path=None,
        output_dir=tmp_path / "chain_onion",
    )

    ops_df   = result["ops_df"]
    debug_df = result["debug_df"]
    metadata = result["metadata"]

    # ops_df must still load
    assert not ops_df.empty, "ops_df should not be empty when only debug_trace is missing"

    # debug_df must be empty but have the expected columns
    assert debug_df.empty, "debug_df should be empty when DEBUG_TRACE is missing"
    for col in ("family_key", "version_key", "instance_key"):
        assert col in debug_df.columns, f"Expected schema column missing: {col}"

    # Missing source must be recorded in metadata
    assert len(metadata["missing_sources"]) >= 1, "missing_sources should list DEBUG_TRACE"
    assert len(metadata["warnings"]) >= 1, "warnings should mention synthetic seq_N"
    assert metadata["debug_trace_available"] is False

    print(f"\n[Test 2] debug_df empty as expected. warnings={metadata['warnings']}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — effective_responses fails gracefully
# ─────────────────────────────────────────────────────────────────────────────

def test_effective_responses_graceful_on_empty_ops():
    """
    Expected: passing empty ops_df returns empty effective_df — no exception.
    """
    empty_ops = pd.DataFrame()
    result = load_effective_responses(empty_ops, report_memory_db_path=None)

    assert isinstance(result, pd.DataFrame), "Must return a DataFrame"
    assert result.empty, "Should return empty DataFrame for empty ops_df"
    # Expected schema columns must be present
    for col in ("family_key", "version_key"):
        assert col in result.columns, f"Expected schema column missing: {col}"

    print("\n[Test 3] empty ops_df → empty effective_df, no exception raised")


@pytest.mark.skipif(not _ARTIFACTS_AVAILABLE, reason="FLAT_GED.xlsx not available")
def test_effective_responses_missing_db(tmp_path):
    """
    Expected: missing report_memory.db → effective_df is non-empty (GED-only),
    or gracefully empty. No exception either way.
    """
    ops_df = load_flat_ged(_FLAT_GED_PATH)
    nonexistent_db = tmp_path / "nonexistent_report_memory.db"

    result = load_effective_responses(ops_df, report_memory_db_path=nonexistent_db)

    assert isinstance(result, pd.DataFrame), "Must return a DataFrame"
    # May be non-empty (GED-only composition) or empty (if composition fails entirely)
    # Either is acceptable — the key requirement is no exception raised
    if not result.empty:
        assert "effective_source" in result.columns
        assert "family_key" in result.columns

    print(f"\n[Test 3b] missing report_memory.db → effective_df has {len(result)} rows (no exception)")


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — Key integrity
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _ARTIFACTS_AVAILABLE, reason="FLAT_GED.xlsx not available")
def test_key_integrity():
    """
    Expected:
    - family_key non-null where numero exists
    - version_key is "{numero}_{indice}" (reproducible)
    - instance_key unique enough within debug_df (no blanks)
    """
    ops_df   = load_flat_ged(_FLAT_GED_PATH)
    debug_df = load_debug_trace(_DEBUG_TRACE_PATH)

    # family_key must be non-null for all rows where numero is non-empty
    has_numero = ops_df["numero"].str.strip() != ""
    null_family = ops_df.loc[has_numero, "family_key"].isna().sum()
    assert null_family == 0, f"{null_family} rows have null family_key despite non-empty numero"

    # version_key must equal "{numero}_{indice}"
    expected_vk = ops_df["numero"].astype(str) + "_" + ops_df["indice"].astype(str)
    mismatched = (ops_df["version_key"] != expected_vk).sum()
    assert mismatched == 0, f"{mismatched} version_key values do not match '{'{numero}_{indice}'}'"

    # Load ops_df a second time — version_keys must be identical (reproducibility)
    ops_df2 = load_flat_ged(_FLAT_GED_PATH)
    vk_set1 = set(ops_df["version_key"].unique())
    vk_set2 = set(ops_df2["version_key"].unique())
    assert vk_set1 == vk_set2, "version_key set is not reproducible across two loads"

    if not debug_df.empty:
        # instance_key must have no null or empty values
        blank_ik = debug_df["instance_key"].isna().sum() + (debug_df["instance_key"] == "").sum()
        assert blank_ik == 0, f"{blank_ik} blank instance_key values in debug_df"

        # version_key in debug_df must match the pattern
        expected_debug_vk = debug_df["numero"].astype(str) + "_" + debug_df["indice"].astype(str)
        mismatched_debug = (debug_df["version_key"] != expected_debug_vk).sum()
        assert mismatched_debug == 0, f"{mismatched_debug} debug_df version_key mismatches"

    print(f"\n[Test 4] Key integrity: "
          f"ops_df={len(ops_df)} rows, "
          f"{ops_df['version_key'].nunique()} unique version_keys, "
          f"debug_df={len(debug_df)} rows, "
          f"{debug_df['instance_key'].nunique() if not debug_df.empty else 0} unique instance_keys")


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Row reconciliation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _ARTIFACTS_AVAILABLE, reason="FLAT_GED.xlsx not available")
def test_row_reconciliation():
    """
    Expected: loaded row counts match direct read of source artifacts.
    """
    # Direct reads for comparison
    ops_direct   = pd.read_excel(_FLAT_GED_PATH, sheet_name="GED_OPERATIONS", dtype=str)
    debug_direct = pd.read_csv(_DEBUG_TRACE_PATH, encoding="utf-8-sig", dtype=str, low_memory=False)

    # Load via source_loader
    ops_loaded   = load_flat_ged(_FLAT_GED_PATH)
    debug_loaded = load_debug_trace(_DEBUG_TRACE_PATH)

    # ops_df: same row count as direct read (no rows dropped)
    assert len(ops_loaded) == len(ops_direct), (
        f"ops_df row count mismatch: loader={len(ops_loaded)}, direct={len(ops_direct)}"
    )

    # debug_df: same row count as direct read (no rows dropped)
    assert len(debug_loaded) == len(debug_direct), (
        f"debug_df row count mismatch: loader={len(debug_loaded)}, direct={len(debug_direct)}"
    )

    # ops_df has exactly 2 more columns than the raw sheet (family_key, version_key)
    assert len(ops_loaded.columns) == len(ops_direct.columns) + 2, (
        f"Expected 2 extra columns in ops_loaded, "
        f"got {len(ops_loaded.columns) - len(ops_direct.columns)}"
    )

    # debug_df has exactly 3 more columns (indice, family_key, version_key, instance_key)
    # = 4 added, but indice is derived (not in original) — total added = 4
    added = len(debug_loaded.columns) - len(debug_direct.columns)
    assert added == 4, (
        f"Expected 4 extra columns in debug_loaded (indice, family_key, version_key, instance_key), "
        f"got {added}"
    )

    # load_chain_sources row counts must match
    result = load_chain_sources(
        flat_ged_path=_FLAT_GED_PATH,
        debug_trace_path=_DEBUG_TRACE_PATH,
        report_memory_db_path=None,
    )
    assert result["metadata"]["row_counts"]["ops_df"]   == len(ops_direct)
    assert result["metadata"]["row_counts"]["debug_df"] == len(debug_direct)

    print(f"\n[Test 5] Row reconciliation: "
          f"ops_df={len(ops_loaded)} rows (direct={len(ops_direct)}), "
          f"debug_df={len(debug_loaded)} rows (direct={len(debug_direct)})")


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — Exception logic metadata
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _ARTIFACTS_AVAILABLE, reason="FLAT_GED.xlsx not available")
def test_exception_logic_metadata():
    """
    Expected: metadata reports exception logic found in consultant_mapping.py,
    BENTIN not found, and no exception rows in ops_df.
    """
    result = load_chain_sources(
        flat_ged_path=_FLAT_GED_PATH,
        debug_trace_path=_DEBUG_TRACE_PATH,
        report_memory_db_path=None,
    )

    exc_summary = result["metadata"]["exception_logic"]
    assert exc_summary["found"] is True
    assert exc_summary["bentin_found"] is False
    assert "consultant_mapping.py" in exc_summary["source_file"]

    # ops_df must contain no "Exception List" actor_clean values
    ops_df = result["ops_df"]
    if "actor_clean" in ops_df.columns:
        exception_rows = ops_df[ops_df["actor_clean"] == "Exception List"]
        assert len(exception_rows) == 0, (
            f"{len(exception_rows)} 'Exception List' rows found in ops_df — "
            "builder should have excluded these"
        )

    print(f"\n[Test 6] Exception logic metadata: "
          f"found={exc_summary['found']}, bentin={exc_summary['bentin_found']}, "
          f"exception_rows_in_ops_df=0")


# ─────────────────────────────────────────────────────────────────────────────
# Run directly
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = [
        test_all_sources_present,
        test_debug_trace_missing,
        test_effective_responses_graceful_on_empty_ops,
        test_key_integrity,
        test_row_reconciliation,
        test_exception_logic_metadata,
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test_fn in tests:
        name = test_fn.__name__

        # Check skip condition
        skip_marker = getattr(test_fn, "pytestmark", None)
        if not _ARTIFACTS_AVAILABLE and "FLAT_GED" in str(
            getattr(test_fn, "__doc__", "")
        ):
            print(f"  SKIP  {name} (artifacts unavailable)")
            skipped += 1
            continue

        try:
            if "tmp_path" in test_fn.__code__.co_varnames:
                import tempfile, pathlib
                with tempfile.TemporaryDirectory() as td:
                    test_fn(tmp_path=pathlib.Path(td))
            else:
                test_fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    if failed:
        raise SystemExit(1)
