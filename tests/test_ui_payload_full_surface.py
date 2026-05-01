"""
tests/test_ui_payload_full_surface.py
Unit tests for Phase 8A.6 widened UI payload audit.

Tests are mock-based to avoid the H-4 reporting import chain hang.
Only _compare_surface and mismatch-classification logic are tested.
"""
import importlib
import sys
import types
from pathlib import Path

import pytest

# ── Stub the reporting chain so import does not trigger H-4 hang ─────────────
_stub_reporting = types.ModuleType("reporting")
_stub_aggregator = types.ModuleType("reporting.aggregator")
_stub_ui_adapter = types.ModuleType("reporting.ui_adapter")
_stub_data_loader = types.ModuleType("reporting.data_loader")
sys.modules.setdefault("reporting", _stub_reporting)
sys.modules.setdefault("reporting.aggregator", _stub_aggregator)
sys.modules.setdefault("reporting.ui_adapter", _stub_ui_adapter)
sys.modules.setdefault("reporting.data_loader", _stub_data_loader)

# Patch sys.path so the script is importable from tests/
_BASE = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _BASE / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Import the module under test
import audit_ui_payload_full_surface as _m


# ── _compare_surface: basic happy path ───────────────────────────────────────

def test_compare_surface_all_match():
    pairs = [
        {"field_label": "a", "backend_val": 10, "ui_val": 10,
         "comparison_kind": "numeric_equal", "classification": "identity"},
        {"field_label": "b", "backend_val": 5, "ui_val": 5,
         "comparison_kind": "numeric_equal", "classification": "naming_only"},
    ]
    r = _m._compare_surface("test_surface", pairs)
    assert r["compared"] == 2
    assert r["matches"] == 2
    assert r["mismatches"] == 0
    assert r["mismatch_rows"] == []


def test_compare_surface_mismatch_classified():
    pairs = [
        {"field_label": "x", "backend_val": 10, "ui_val": 9,
         "comparison_kind": "numeric_equal", "classification": _m.TRUE_BUG,
         "notes": "arithmetic error"},
    ]
    r = _m._compare_surface("test_surface", pairs)
    assert r["mismatches"] == 1
    assert r["mismatch_rows"][0]["classification"] == _m.TRUE_BUG


def test_compare_surface_skipped_not_counted():
    pairs = [
        {"field_label": "s", "backend_val": None, "ui_val": None,
         "comparison_kind": _m.SKIPPED, "classification": _m.SKIPPED,
         "notes": "no split"},
    ]
    r = _m._compare_surface("test_surface", pairs)
    assert r["compared"] == 0
    assert r["skipped"] == 1
    assert r["matches"] == 0


def test_compare_surface_float_equal_within_tolerance():
    pairs = [
        {"field_label": "rate", "backend_val": 62.5, "ui_val": 62.6,
         "comparison_kind": "float_equal", "classification": "identity"},
    ]
    r = _m._compare_surface("test_surface", pairs)
    assert r["matches"] == 1
    assert r["mismatches"] == 0


def test_compare_surface_float_equal_outside_tolerance():
    pairs = [
        {"field_label": "rate", "backend_val": 62.5, "ui_val": 63.0,
         "comparison_kind": "float_equal", "classification": _m.TRUE_BUG},
    ]
    r = _m._compare_surface("test_surface", pairs)
    assert r["mismatches"] == 1
    assert r["mismatch_rows"][0]["classification"] == _m.TRUE_BUG


def test_compare_surface_identity_strings():
    pairs = [
        {"field_label": "name", "backend_val": "ALICE", "ui_val": "ALICE",
         "comparison_kind": "identity", "classification": "identity"},
        {"field_label": "name2", "backend_val": "BOB", "ui_val": "CAROL",
         "comparison_kind": "identity", "classification": _m.TRUE_BUG},
    ]
    r = _m._compare_surface("test_surface", pairs)
    assert r["matches"] == 1
    assert r["mismatches"] == 1


# ── Classification constants are stable ──────────────────────────────────────

def test_classification_constants():
    assert _m.NAMING_ONLY == "naming_only"
    assert _m.SCOPE_FILTER == "scope_filter"
    assert _m.EXPECTED_SEMANTIC == "expected_semantic_difference"
    assert _m.TRUE_BUG == "true_bug"
    assert _m.SKIPPED == "skipped"


# ── _safe_int edge cases ──────────────────────────────────────────────────────

def test_safe_int_handles_none():
    assert _m._safe_int(None) == 0

def test_safe_int_handles_float():
    assert _m._safe_int(3.7) == 3

def test_safe_int_handles_bad_string():
    assert _m._safe_int("not_a_number") == 0


# ── _surface_classification_counts ───────────────────────────────────────────

def test_surface_classification_counts_empty():
    r = {"mismatch_rows": []}
    cc = _m._surface_classification_counts(r)
    assert cc == {
        "naming_only": 0, "scope_filter": 0,
        "expected_semantic_difference": 0, "true_bug": 0,
    }


def test_surface_classification_counts_mixed():
    r = {
        "mismatch_rows": [
            {"classification": _m.NAMING_ONLY},
            {"classification": _m.NAMING_ONLY},
            {"classification": _m.TRUE_BUG},
            {"classification": _m.SCOPE_FILTER},
        ]
    }
    cc = _m._surface_classification_counts(r)
    assert cc["naming_only"] == 2
    assert cc["scope_filter"] == 1
    assert cc["true_bug"] == 1
    assert cc["expected_semantic_difference"] == 0


# ── write_outputs JSON shape ──────────────────────────────────────────────────

def test_write_outputs_json_shape(tmp_path):
    results = [
        {
            "surface": "s1", "compared": 3, "matches": 3, "mismatches": 0,
            "skipped": 0, "mismatch_rows": [], "skip_rows": [], "notes": "ok",
        },
        {
            "surface": "s2", "compared": 1, "matches": 0, "mismatches": 1,
            "skipped": 0,
            "mismatch_rows": [{
                "surface": "s2", "field_label": "f",
                "backend_val": 1, "ui_val": 2,
                "comparison_kind": "numeric_equal",
                "classification": _m.TRUE_BUG, "notes": "",
            }],
            "skip_rows": [], "notes": "bug",
        },
    ]
    json_path, xlsx_path = _m.write_outputs(results, tmp_path)

    import json as _json
    data = _json.loads(json_path.read_text(encoding="utf-8"))

    assert data["total_surfaces"] == 2
    assert data["total_compared"] == 4
    assert data["total_matches"] == 3
    assert data["total_mismatches"] == 1
    assert data["unexplained_mismatches"] == 1
    assert data["classification_breakdown"]["true_bug"] == 1
    assert set(data["per_surface"].keys()) == {"s1", "s2"}
    assert len(data["mismatch_detail"]) == 1
    assert xlsx_path.exists()
