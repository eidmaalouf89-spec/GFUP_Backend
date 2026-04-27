"""
tests/flat_ged/test_smoke.py — Smoke test for the vendored flat_ged package.

Runs batch mode on the real GED export and verifies:
  - FLAT_GED.xlsx was written
  - run_report["failure_count"] == 0

Run from the project root:
    pytest tests/flat_ged/test_smoke.py
"""

import tempfile
from pathlib import Path

import pytest

# Project root — two levels up from this file (tests/flat_ged/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

GED_INPUT = PROJECT_ROOT / "input" / "GED_export.xlsx"


def test_build_flat_ged_batch_smoke():
    """Batch mode on real GED export: no failures, workbook written."""
    pytest.importorskip("openpyxl")  # skip cleanly if dependency missing

    if not GED_INPUT.exists():
        pytest.skip(f"GED input not found: {GED_INPUT}")

    from src.flat_ged import build_flat_ged

    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        report = build_flat_ged(GED_INPUT, output_dir, mode="batch")

        # Workbook was written (check inside the with-block while dir still exists)
        flat_ged_path = output_dir / "FLAT_GED.xlsx"
        assert flat_ged_path.exists(), "FLAT_GED.xlsx not written by build_flat_ged"

    # No processing failures
    assert report["failure_count"] == 0, (
        f"Expected 0 failures, got {report['failure_count']}. "
        f"Failures: {report.get('failures', [])}"
    )
