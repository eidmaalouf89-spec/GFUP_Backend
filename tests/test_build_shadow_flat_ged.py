"""
tests/test_build_shadow_flat_ged.py — Phase 8B.9 companion tests.

Mock-only fast tests for the §5 taxonomy projection logic in
scripts/build_shadow_flat_ged.py.  We exercise the per-row classifier on
synthetic RAW rows + synthetic audit indices.

Run fast tests:
    python -m pytest tests/test_build_shadow_flat_ged.py -v -m "not slow"
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_shadow_flat_ged.py"
_spec   = importlib.util.spec_from_file_location("build_shadow_flat_ged", _SCRIPT)
_mod    = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_classify_raw_event_for_shadow = _mod._classify_raw_event_for_shadow
project_shadow                 = _mod.project_shadow
_step_type_from_actor          = _mod._step_type_from_actor
assign_step_order              = _mod.assign_step_order


def _row(numero="100", indice="A", actor="ARCHITECTE", status="VAO",
         event_type="RESPONSE", cycle="C1", excel_row=1):
    return {
        "numero": numero, "indice": indice, "actor_canonical": actor,
        "status_clean": status, "event_type": event_type, "cycle_id": cycle,
        "source_excel_row": str(excel_row),
        "lot": "L1", "emetteur": "X", "titre": "T",
        "status_raw": status, "submission_date": "2026-01-01",
        "response_date": "2026-01-15", "deadline_date": "",
        "date_status_type": "ANSWERED", "comment_raw": "",
        "pj_flag": "0",
    }


def test_drop_missing_numero():
    row = _row(numero="_MISSING_3017")
    v, r = _classify_raw_event_for_shadow(row, {}, {}, {})
    assert v == "DROP"
    assert r == "MALFORMED_RESPONSE"


def test_drop_exception_list_actor():
    row = _row(actor="Exception List")
    v, r = _classify_raw_event_for_shadow(row, {}, {}, {})
    assert v == "DROP"
    assert r == "UNKNOWN_ACTOR"


def test_drop_non_operational_response_status():
    row = _row(status="WEIRD")
    v, r = _classify_raw_event_for_shadow(row, {}, {}, {})
    assert v == "DROP"
    assert r == "NON_OPERATIONAL_RESPONSE"


def test_keep_operational_response():
    row = _row(status="VAO")
    v, r = _classify_raw_event_for_shadow(row, {}, {}, {"100": 0, ("100","A","ARCHITECTE"): 1})
    assert v == "KEEP"
    assert r == "OPERATIONAL_KEEP"


def test_drop_active_version_projection_via_audit():
    row = _row()
    drop_index = {("100", "A", "ARCHITECTE"): "ACTIVE_VERSION_PROJECTION"}
    v, r = _classify_raw_event_for_shadow(row, drop_index, {}, {})
    assert v == "DROP"
    assert r == "ACTIVE_VERSION_PROJECTION"


def test_drop_duplicate_merged_via_audit():
    row = _row()
    drop_index = {("100", "A", "ARCHITECTE"): "DUPLICATE_MERGED"}
    v, r = _classify_raw_event_for_shadow(row, drop_index, {}, {})
    assert v == "DROP"
    assert r == "DUPLICATE_MERGED"


def test_drop_sas_ref_duplicate_favorable_kept():
    row = _row(actor="0-SAS", status="REF")
    sheet07 = {("100", "A", "0-SAS"):
               {"classification": "DUPLICATE_FAVORABLE_KEPT", "raw": {}}}
    v, r = _classify_raw_event_for_shadow(row, {}, sheet07, {})
    assert v == "DROP"
    assert r == "DUPLICATE_FAVORABLE_KEPT"


def test_keep_sas_ref_unexplained_residual():
    row = _row(actor="0-SAS", status="REF")
    sheet07 = {("100", "A", "0-SAS"):
               {"classification": "UNEXPLAINED", "raw": {}}}
    counts = {("100", "A", "0-SAS"): 1}
    v, r = _classify_raw_event_for_shadow(row, {}, sheet07, counts)
    assert v == "KEEP"
    assert r == "UNEXPLAINED_KEEP"


def test_sas_ref_matched_passes_through():
    """A SAS REF that matched cleanly (sheet 07 cls=MATCHED) → OPERATIONAL_KEEP."""
    row = _row(actor="0-SAS", status="REF")
    sheet07 = {("100", "A", "0-SAS"):
               {"classification": "MATCHED", "raw": {}}}
    counts = {("100", "A", "0-SAS"): 1}
    v, r = _classify_raw_event_for_shadow(row, {}, sheet07, counts)
    assert v == "KEEP"
    assert r == "OPERATIONAL_KEEP"


def test_step_type_from_actor():
    assert _step_type_from_actor("0-SAS") == "SAS"
    assert _step_type_from_actor("ARCHITECTE") == "CONSULTANT"
    assert _step_type_from_actor("") == ""


def test_project_shadow_end_to_end_minimal():
    raw_rows = [
        _row(numero="100", indice="A", actor="ARCHITECTE", status="VAO", excel_row=1),
        _row(numero="_MISSING_5", indice="A", actor="ARCHITECTE", status="VAO", excel_row=2),
        _row(numero="200", indice="A", actor="Exception List", status="", excel_row=3),
        _row(numero="300", indice="B", actor="0-SAS", status="REF", excel_row=4),
    ]
    sheet07_index = {("300", "B", "0-SAS"):
                     {"classification": "DUPLICATE_FAVORABLE_KEPT", "raw": {}}}
    audit_index = {
        "drop_index": {},
        "sheet07_index": sheet07_index,
        "unexplained_07": [],
    }
    out = project_shadow(raw_rows, audit_index)

    # 1 KEEP (the 100/A/ARCHITECTE), the other 3 dropped
    assert len(out["shadow_rows"]) == 1
    assert out["shadow_rows"][0]["numero"] == "100"
    assert out["rule_buckets"]["MALFORMED_RESPONSE"]
    assert out["rule_buckets"]["UNKNOWN_ACTOR"]
    assert out["rule_buckets"]["DUPLICATE_FAVORABLE_KEPT"]
    assert out["unexplained_residual"] == []


def test_assign_step_order_per_pair():
    rows = [
        {"numero": "100", "indice": "A"},
        {"numero": "100", "indice": "A"},
        {"numero": "200", "indice": "B"},
    ]
    assign_step_order(rows)
    assert rows[0]["step_order"] == 1
    assert rows[1]["step_order"] == 2
    assert rows[2]["step_order"] == 1
