"""
tests/test_chain_onion_source_check.py
Phase 8 Step 5 — 7 unit tests for _check_flat_ged_alignment.

Run: python -m pytest tests/test_chain_onion_source_check.py -q
Note: pytest may hang in sandbox (H-4); authoritative on Windows shell.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure src/ is importable
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from chain_onion.source_loader import _check_flat_ged_alignment

_RECEIPTS_NAME = "chain_onion_source_check.json"


def _receipts_path(flat_ged: Path) -> Path:
    return flat_ged.parent.parent / "debug" / _RECEIPTS_NAME


def _read_receipts(flat_ged: Path) -> dict:
    return json.loads(_receipts_path(flat_ged).read_text(encoding="utf-8"))


def _make_env(tmp_path: Path, content: bytes = b"fake-flat-ged") -> Path:
    """Create flat_ged at tmp_path/output/intermediate/FLAT_GED.xlsx plus dummy run_memory.db."""
    flat_ged = tmp_path / "output" / "intermediate" / "FLAT_GED.xlsx"
    flat_ged.parent.mkdir(parents=True, exist_ok=True)
    flat_ged.write_bytes(content)
    db = tmp_path / "data" / "run_memory.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_bytes(b"")  # dummy file so db_path.exists() passes
    return flat_ged


# ── Test 1 ──────────────────────────────────────────────────────────────────

def test_paths_identical_returns_ok(tmp_path):
    flat_ged = _make_env(tmp_path)
    with (
        patch("reporting.data_loader._resolve_latest_run", return_value=1),
        patch("reporting.data_loader._get_artifact_path", return_value=str(flat_ged)),
    ):
        _check_flat_ged_alignment(flat_ged)
    r = _read_receipts(flat_ged)
    assert r["result"] == "OK"


# ── Test 2 ──────────────────────────────────────────────────────────────────

def test_paths_differ_same_sha_warns_path(tmp_path):
    content = b"identical-content-xyz"
    flat_ged = _make_env(tmp_path, content)
    other = tmp_path / "other_dir" / "FLAT_GED.xlsx"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_bytes(content)
    with (
        patch("reporting.data_loader._resolve_latest_run", return_value=1),
        patch("reporting.data_loader._get_artifact_path", return_value=str(other)),
    ):
        _check_flat_ged_alignment(flat_ged)
    r = _read_receipts(flat_ged)
    assert r["result"] == "WARN_PATH_MISMATCH_SAME_CONTENT"


# ── Test 3 ──────────────────────────────────────────────────────────────────

def test_paths_differ_different_sha_warns_both(tmp_path):
    flat_ged = _make_env(tmp_path, b"content-A")
    other = tmp_path / "other_dir" / "FLAT_GED.xlsx"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_bytes(b"content-B")
    with (
        patch("reporting.data_loader._resolve_latest_run", return_value=1),
        patch("reporting.data_loader._get_artifact_path", return_value=str(other)),
    ):
        _check_flat_ged_alignment(flat_ged)
    r = _read_receipts(flat_ged)
    assert r["result"] == "WARN_PATH_AND_CONTENT_MISMATCH"


# ── Test 4 ──────────────────────────────────────────────────────────────────

def test_helper_returns_none_yields_undetermined(tmp_path):
    flat_ged = _make_env(tmp_path)
    with (
        patch("reporting.data_loader._resolve_latest_run", return_value=1),
        patch("reporting.data_loader._get_artifact_path", return_value=None),
    ):
        _check_flat_ged_alignment(flat_ged)
    r = _read_receipts(flat_ged)
    assert r["result"] == "UNDETERMINED"


# ── Test 5 ──────────────────────────────────────────────────────────────────

def test_helper_raises_yields_undetermined_with_reason(tmp_path):
    flat_ged = _make_env(tmp_path)
    with (
        patch("reporting.data_loader._resolve_latest_run", return_value=1),
        patch("reporting.data_loader._get_artifact_path", side_effect=RuntimeError("boom")),
    ):
        _check_flat_ged_alignment(flat_ged)
    r = _read_receipts(flat_ged)
    assert r["result"] == "UNDETERMINED"
    assert r.get("reason"), "reason field must be non-empty when helper raises"


# ── Test 6 ──────────────────────────────────────────────────────────────────

def test_check_never_raises(tmp_path):
    flat_ged = _make_env(tmp_path)
    with patch("reporting.data_loader._resolve_latest_run", side_effect=Exception("catastrophe")):
        try:
            _check_flat_ged_alignment(flat_ged)
        except Exception as exc:
            pytest.fail(f"_check_flat_ged_alignment raised unexpectedly: {exc}")


# ── Test 7 ──────────────────────────────────────────────────────────────────

def test_check_writes_receipts_file(tmp_path):
    flat_ged = _make_env(tmp_path)
    # Call without mocks — result will be UNDETERMINED (dummy db), but file must be written
    _check_flat_ged_alignment(flat_ged)
    assert _receipts_path(flat_ged).exists(), (
        f"receipts file not written at {_receipts_path(flat_ged)}"
    )
