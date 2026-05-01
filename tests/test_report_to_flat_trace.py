"""
tests/test_report_to_flat_trace.py — Phase 8B.8 companion tests.

Mock-only fast tests exercise the per-row classifier + the confidence
bucket helper.  One @pytest.mark.slow live test reads the real artifacts
and checks the summary distribution.

Run fast tests:
    python -m pytest tests/test_report_to_flat_trace.py -v -m "not slow"
Run all:
    python -m pytest tests/test_report_to_flat_trace.py -v
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "report_to_flat_trace.py"
_spec   = importlib.util.spec_from_file_location("report_to_flat_trace", _SCRIPT)
_mod    = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_classify_report_row    = _mod._classify_report_row
_confidence_bucket      = _mod._confidence_bucket
_is_conflict            = _mod._is_conflict
_MATCH_METHOD_TO_TYPE   = _mod._MATCH_METHOD_TO_TYPE
_CONSULTANT_SOURCE_TO_ACTOR = _mod._CONSULTANT_SOURCE_TO_ACTOR
compute_report_to_flat_trace = _mod.compute_report_to_flat_trace


def test_confidence_bucket_thresholds():
    assert _confidence_bucket(1.0)   == "HIGH"
    assert _confidence_bucket(0.97)  == "HIGH"
    assert _confidence_bucket(0.95)  == "HIGH"
    assert _confidence_bucket(0.94)  == "MEDIUM"
    assert _confidence_bucket(0.75)  == "MEDIUM"
    assert _confidence_bucket(0.74)  == "LOW"
    assert _confidence_bucket(0.0)   == "LOW"
    assert _confidence_bucket(None)  == "UNKNOWN"
    assert _confidence_bucket("foo") == "UNKNOWN"


def test_is_conflict_basic_pairs():
    assert _is_conflict("REF", "VAO") is True
    assert _is_conflict("VAO", "REF") is True
    assert _is_conflict("VAO", "VSO") is False  # both favorable
    assert _is_conflict("REF", "REF") is False
    assert _is_conflict("",    "VAO") is False  # empty side
    assert _is_conflict("HM",  "VAO") is False  # OUT_OF_SCOPE not refused


def test_classify_blocked_by_confidence_low():
    row = {
        "id": 1, "consultant": "SOCOTEC", "doc_id": "abc",
        "report_status": "VAO", "report_response_date": "2026-01-01",
        "report_comment": "ok", "source_filename": "f.xlsx",
        "match_confidence": 0.5, "match_method": "MATCH_BY_NUMERO_INDICE",
    }
    bridge = {"abc": {"numero": "100", "indice": "A",
                      "consultant_source": "SOCOTEC", "match_method_xlsx": "",
                      "confidence_xlsx": ""}}
    ged_lookup = {("100", "A", "Bureau de Contrôle"):
                  {"date_status_type": "PENDING_IN_DELAY", "status_clean": ""}}
    out = _classify_report_row(row, bridge, ged_lookup)
    assert out["report_confidence"] == "LOW"
    assert out["report_applied"] == "BLOCKED_BY_CONFIDENCE"
    assert out["report_match_type"] == "EXACT"


def test_classify_applied_as_primary_when_ged_pending():
    row = {
        "id": 2, "consultant": "ACOUSTICIEN AVLS", "doc_id": "xyz",
        "report_status": "VAO", "report_response_date": "2026-01-15",
        "report_comment": "", "source_filename": "f.xlsx",
        "match_confidence": 0.99, "match_method": "MATCH_BY_NUMERO_INDICE",
    }
    bridge = {"xyz": {"numero": "200", "indice": "B",
                      "consultant_source": "AVLS",
                      "match_method_xlsx": "", "confidence_xlsx": ""}}
    ged_lookup = {("200", "B", "BET Acoustique"):
                  {"date_status_type": "PENDING_IN_DELAY", "status_clean": ""}}
    out = _classify_report_row(row, bridge, ged_lookup)
    assert out["report_confidence"] == "HIGH"
    assert out["report_applied"]    == "APPLIED_AS_PRIMARY"
    assert out["effective_status"]  == "VAO"
    assert out["effective_source"]  == "GED+REPORT_STATUS"


def test_classify_applied_as_enrichment_when_ged_already_answered_no_conflict():
    row = {
        "id": 3, "consultant": "SOCOTEC", "doc_id": "def",
        "report_status": "VAO", "report_response_date": "2026-02-01",
        "report_comment": "extra detail", "source_filename": "f.xlsx",
        "match_confidence": 0.99, "match_method": "MATCH_BY_NUMERO_INDICE",
    }
    bridge = {"def": {"numero": "300", "indice": "A",
                      "consultant_source": "SOCOTEC",
                      "match_method_xlsx": "", "confidence_xlsx": ""}}
    ged_lookup = {("300", "A", "Bureau de Contrôle"):
                  {"date_status_type": "ANSWERED", "status_clean": "VAO"}}
    out = _classify_report_row(row, bridge, ged_lookup)
    assert out["report_applied"]   == "APPLIED_AS_ENRICHMENT"
    assert out["effective_status"] == "VAO"
    assert out["effective_source"] == "GED+REPORT_COMMENT"


def test_classify_blocked_by_ged_when_conflict():
    row = {
        "id": 4, "consultant": "SOCOTEC", "doc_id": "ghi",
        "report_status": "VAO", "report_response_date": "2026-02-01",
        "report_comment": "", "source_filename": "f.xlsx",
        "match_confidence": 0.99, "match_method": "MATCH_BY_NUMERO_INDICE",
    }
    bridge = {"ghi": {"numero": "400", "indice": "A",
                      "consultant_source": "SOCOTEC",
                      "match_method_xlsx": "", "confidence_xlsx": ""}}
    ged_lookup = {("400", "A", "Bureau de Contrôle"):
                  {"date_status_type": "ANSWERED", "status_clean": "REF"}}
    out = _classify_report_row(row, bridge, ged_lookup)
    assert out["report_applied"]   == "BLOCKED_BY_GED"
    assert out["effective_source"] == "GED_CONFLICT_REPORT"


def test_classify_not_applied_when_no_ged_row():
    row = {
        "id": 5, "consultant": "SOCOTEC", "doc_id": "jkl",
        "report_status": "VAO", "report_response_date": "",
        "report_comment": "", "source_filename": "f.xlsx",
        "match_confidence": 0.99, "match_method": "MATCH_BY_NUMERO_INDICE",
    }
    bridge = {"jkl": {"numero": "999", "indice": "Z",
                      "consultant_source": "SOCOTEC",
                      "match_method_xlsx": "", "confidence_xlsx": ""}}
    ged_lookup = {}  # nothing
    out = _classify_report_row(row, bridge, ged_lookup)
    assert out["report_applied"]   == "NOT_APPLIED"
    assert out["effective_source"] == "GED"


def test_classify_match_type_mapping_full():
    """Every documented match_method maps to a §15.3 match_type."""
    expected = {
        "MATCH_BY_NUMERO_INDICE":          "EXACT",
        "MATCH_BY_RECENT_INDICE_FALLBACK": "FAMILY",
        "MATCH_BY_DATE_PROXIMITY":         "FUZZY",
        "MATCH_BY_MIXED_HEURISTIC":        "FUZZY",
    }
    for method, mtype in expected.items():
        assert _MATCH_METHOD_TO_TYPE[method] == mtype


def test_classify_doc_id_unknown_in_bridge_is_not_applied():
    row = {
        "id": 6, "consultant": "SOCOTEC", "doc_id": "MISSING",
        "report_status": "VAO", "report_response_date": "",
        "report_comment": "", "source_filename": "f.xlsx",
        "match_confidence": 0.99, "match_method": "MATCH_BY_NUMERO_INDICE",
    }
    out = _classify_report_row(row, bridge={}, ged_lookup={})
    assert out["report_applied"] == "NOT_APPLIED"


# ── Live test ────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_compute_live_report_count_positive():
    result = compute_report_to_flat_trace()
    assert result["rows"], "no rows traced"
    assert result["counts_applied"], "no applied counts"
    assert result["summary_line"].startswith("REPORT_TO_FLAT: report_count=")
