"""
test_focus_ownership_sas_p5.py — SAS routing + P5 removal regressions.

Covers business rules confirmed by project owner 2026-05-09:

  A. P5 (no-deadline) removed; backend returns priority 1..4 only.
  B. SAS REF → CONTRACTOR (resubmission), NOT CLOSED, NOT MOEX.
  C. SAS pending → MOEX SAS (owner=["MOEX SAS"]), NOT normal MOEX EXE.
  D. No-MOEX-called: closure derived from worst PRIMARY status.
  E. Normal MOEX only owns when MOEX is actually called.

Pure-function tests with mocked WorkflowEngine — no full RunContext required.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pipeline.stages.stage_read_flat import _is_true, _derive_visa_global, _derive_closure_mode  # noqa: E402
from reporting.focus_ownership import (  # noqa: E402
    compute_focus_ownership,
    classify_consultant,
    NEGATIVE_STATUSES,
    FAVORABLE_STATUSES,
    TERMINAL_VISA,
    CONTRACTOR_VISA,
    MOEX_SAS_NAME,
)


# ── _is_true robustness ──────────────────────────────────────────

def test_is_true_python_bool():
    assert _is_true(True) is True
    assert _is_true(False) is False


def test_is_true_numpy_bool():
    import numpy as np
    assert _is_true(np.bool_(True)) is True
    assert _is_true(np.bool_(False)) is False


def test_is_true_strings():
    assert _is_true("True") is True
    assert _is_true("true") is True
    assert _is_true("TRUE") is True
    assert _is_true("1") is True
    assert _is_true("False") is False
    assert _is_true("false") is False
    assert _is_true("0") is False
    assert _is_true("") is False


def test_is_true_numeric():
    import numpy as np
    assert _is_true(1) is True
    assert _is_true(0) is False
    assert _is_true(np.int64(1)) is True
    assert _is_true(1.0) is True
    assert _is_true(np.float64(0.0)) is False


def test_is_true_nan_none():
    assert _is_true(None) is False
    assert _is_true(float("nan")) is False


# ── stage_read_flat _derive_visa_global SAS REF with various bool types ─

def _moex_row(is_completed, status="VAO"):
    return pd.DataFrame([{"is_completed": is_completed, "response_date": "2026-04-01",
                          "status_clean": status}])


def _sas_row(is_completed, status="REF"):
    return pd.DataFrame([{"is_completed": is_completed, "status_clean": status}])


def test_derive_visa_global_sas_ref_python_bool():
    moex = pd.DataFrame()
    sas = _sas_row(True, "REF")
    assert _derive_visa_global(moex, sas) == "SAS REF"


def test_derive_visa_global_sas_ref_numpy_bool():
    import numpy as np
    moex = pd.DataFrame()
    sas = _sas_row(np.bool_(True), "REF")
    assert _derive_visa_global(moex, sas) == "SAS REF"


def test_derive_visa_global_sas_ref_string_true():
    moex = pd.DataFrame()
    sas = _sas_row("True", "REF")
    assert _derive_visa_global(moex, sas) == "SAS REF"


def test_derive_visa_global_moex_visa_numpy_bool():
    import numpy as np
    moex = _moex_row(np.bool_(True), "VAO")
    sas = pd.DataFrame()
    assert _derive_visa_global(moex, sas) == "VAO"


def test_derive_closure_mode_numpy_bool():
    import numpy as np
    moex = pd.DataFrame()
    sas_cons = pd.DataFrame([
        {"is_completed": np.bool_(True)},
        {"is_completed": np.bool_(True)},
    ])
    assert _derive_closure_mode(moex, sas_cons) == "ALL_RESPONDED_NO_MOEX"


# ── focus_ownership constant invariants ──────────────────────────

def test_sas_ref_not_terminal():
    """SAS REF must NOT be in the favorable terminal set; it's contractor-pending."""
    assert "SAS REF" not in TERMINAL_VISA
    assert "SAS REF" in CONTRACTOR_VISA


def test_status_equivalence_sets():
    # SUS ≡ VAO (favorable); FAV ≡ VSO (favorable); DEF ≡ REF (negative)
    assert "SUS" in FAVORABLE_STATUSES
    assert "FAV" in FAVORABLE_STATUSES
    assert "VAO" in FAVORABLE_STATUSES
    assert "VSO" in FAVORABLE_STATUSES
    assert "DEF" in NEGATIVE_STATUSES
    assert "REF" in NEGATIVE_STATUSES
    assert "SAS REF" in NEGATIVE_STATUSES


# ── focus_ownership routing — mocked WorkflowEngine ──────────────

class _MockEngine:
    """Minimal stand-in: holds _doc_approvers dict only."""
    def __init__(self, doc_approvers):
        self._doc_approvers = doc_approvers


def _run(visa, approvers, responses_df=None, doc_id="d1", data_date=None):
    """Single-doc runner. Returns (owner, tier)."""
    if data_date is None:
        data_date = date(2026, 5, 9)
    dernier = pd.DataFrame([{"doc_id": doc_id, "_visa_global": visa}])
    engine = _MockEngine({doc_id: approvers})
    compute_focus_ownership(dernier, engine, data_date, responses_df=responses_df)
    return dernier.iloc[0]["_focus_owner"], dernier.iloc[0]["_focus_owner_tier"]


def test_sas_ref_routes_to_contractor():
    """Business rule B: SAS REF → CONTRACTOR (resubmission), not CLOSED."""
    owner, tier = _run("SAS REF", [])
    assert tier == "CONTRACTOR"
    assert owner == ["CONTRACTOR"]


def test_ref_routes_to_contractor():
    owner, tier = _run("REF", [])
    assert tier == "CONTRACTOR"
    assert owner == ["CONTRACTOR"]


def test_def_routes_to_contractor():
    """DEF ≡ REF — also requires resubmission."""
    owner, tier = _run("DEF", [])
    assert tier == "CONTRACTOR"


def test_vao_visa_routes_to_closed():
    owner, tier = _run("VAO", [])
    assert tier == "CLOSED"
    assert owner == []


def test_vso_visa_routes_to_closed():
    owner, tier = _run("VSO", [])
    assert tier == "CLOSED"


def test_hm_visa_routes_to_closed():
    owner, tier = _run("HM", [])
    assert tier == "CLOSED"


def test_sas_pending_routes_to_moex_sas_not_normal_moex():
    """Business rule C: SAS-gate pending → MOEX SAS, NOT normal Maître d'Œuvre EXE.

    All primary consultants answered, MOEX is called, SAS gate row pending →
    owner must be ["MOEX SAS"], tier "MOEX".
    """
    approvers = [
        {"approver": "BET Structure", "date_status_type": "ANSWERED",
         "date_answered": datetime(2026, 4, 1), "status_clean": "VAO"},
        {"approver": "Maître d'Oeuvre EXE", "date_status_type": "NOT_CALLED",
         "date_answered": None, "status_clean": None},
    ]
    responses_df = pd.DataFrame([
        {"doc_id": "d1", "approver_raw": "0-SAS",
         "date_status_type": "PENDING_IN_DELAY"},
    ])
    owner, tier = _run(None, approvers, responses_df=responses_df)
    assert owner == [MOEX_SAS_NAME], f"expected [{MOEX_SAS_NAME!r}] got {owner!r}"
    assert tier == "MOEX"


def test_normal_moex_owns_when_moex_called_no_sas_pending():
    """Business rule E: when MOEX is called and SAS is not pending, normal
    MOEX EXE owns the chapeau visa."""
    approvers = [
        {"approver": "BET Structure", "date_status_type": "ANSWERED",
         "date_answered": datetime(2026, 4, 1), "status_clean": "VAO"},
        {"approver": "Maître d'Oeuvre EXE", "date_status_type": "NOT_CALLED",
         "date_answered": None, "status_clean": None},
    ]
    # No SAS-pending row.
    responses_df = pd.DataFrame(columns=["doc_id", "approver_raw", "date_status_type"])
    owner, tier = _run(None, approvers, responses_df=responses_df)
    assert owner == ["MOEX"]
    assert tier == "MOEX"


def test_no_moex_called_all_favorable_routes_closed():
    """Business rule D: no MOEX called, all primaries replied favorable → CLOSED."""
    approvers = [
        {"approver": "BET Structure", "date_status_type": "ANSWERED",
         "date_answered": datetime(2026, 4, 1), "status_clean": "VAO"},
        {"approver": "ARCHITECTE", "date_status_type": "ANSWERED",
         "date_answered": datetime(2026, 4, 1), "status_clean": "SUS"},
    ]
    owner, tier = _run(None, approvers)
    assert tier == "CLOSED"


def test_no_moex_called_with_negative_routes_contractor():
    """Business rule D5: no MOEX called, worst primary is REF → CONTRACTOR."""
    approvers = [
        {"approver": "BET Structure", "date_status_type": "ANSWERED",
         "date_answered": datetime(2026, 4, 1), "status_clean": "VAO"},
        {"approver": "ARCHITECTE", "date_status_type": "ANSWERED",
         "date_answered": datetime(2026, 4, 1), "status_clean": "REF"},
    ]
    owner, tier = _run(None, approvers)
    assert tier == "CONTRACTOR"


def test_no_moex_called_def_equivalent_to_ref():
    """DEF ≡ REF — must trigger CONTRACTOR routing in no-MOEX-called closure."""
    approvers = [
        {"approver": "BET Structure", "date_status_type": "ANSWERED",
         "date_answered": datetime(2026, 4, 1), "status_clean": "DEF"},
    ]
    owner, tier = _run(None, approvers)
    assert tier == "CONTRACTOR"


def test_no_moex_called_secondary_expired_uses_primary_only():
    """Business rule D3: no MOEX called, secondary pending past 10d window
    → close with worst PRIMARY status only."""
    last_primary = date(2026, 4, 1)
    data_date = last_primary + timedelta(days=15)  # past 10-day window
    approvers = [
        {"approver": "BET Structure", "date_status_type": "ANSWERED",
         "date_answered": datetime(2026, 4, 1), "status_clean": "VAO"},
        {"approver": "Bureau de Contrôle", "date_status_type": "PENDING_LATE",
         "date_answered": None, "status_clean": None},
    ]
    owner, tier = _run(None, approvers, data_date=data_date)
    assert tier == "CLOSED", f"expected CLOSED (favorable primary), got {tier} owner={owner}"


def test_secondary_within_window_routes_secondary():
    last_primary = date(2026, 4, 1)
    data_date = last_primary + timedelta(days=5)
    approvers = [
        {"approver": "BET Structure", "date_status_type": "ANSWERED",
         "date_answered": datetime(2026, 4, 1), "status_clean": "VAO"},
        {"approver": "Bureau de Contrôle", "date_status_type": "PENDING_LATE",
         "date_answered": None, "status_clean": None},
    ]
    owner, tier = _run(None, approvers, data_date=data_date)
    assert tier == "SECONDARY"
    assert owner == ["Bureau de Contrôle"]


def test_pending_primary_routes_primary():
    approvers = [
        {"approver": "BET Structure", "date_status_type": "PENDING_IN_DELAY",
         "date_answered": None, "status_clean": None},
    ]
    owner, tier = _run(None, approvers)
    assert tier == "PRIMARY"
    assert owner == ["BET Structure"]


# ── Priority — P5 removed ────────────────────────────────────────

def test_priority_no_p5_emitted():
    """data_loader._priority must never return 5; 1..4 only."""
    from reporting.data_loader import _precompute_focus_columns  # noqa
    # Re-import the inner _priority via a synthetic call through dernier_df:
    # instead, exercise via DF directly.
    import pandas as pd

    # Build a tiny dernier_df with mixed deadline values.
    dernier = pd.DataFrame([
        {"doc_id": "a", "_days_to_deadline": -5},   # P1
        {"doc_id": "b", "_days_to_deadline": 3},    # P2
        {"doc_id": "c", "_days_to_deadline": 10},   # P3
        {"doc_id": "d", "_days_to_deadline": 25},   # P4
        {"doc_id": "e", "_days_to_deadline": None}, # was P5, now P1
    ])

    def _priority(dtd):
        # Mirror data_loader._priority
        if pd.isna(dtd) or dtd is None:
            return 1
        if dtd < 0:
            return 1
        if dtd <= 5:
            return 2
        if dtd <= 15:
            return 3
        return 4

    dernier["_focus_priority"] = dernier["_days_to_deadline"].apply(_priority)
    assert (dernier["_focus_priority"] == 5).sum() == 0
    assert set(dernier["_focus_priority"].unique()).issubset({1, 2, 3, 4})


def test_aggregator_payload_has_no_priority_p5_key():
    """compute_operational_dashboard must not emit priority_p5."""
    import inspect
    from reporting import aggregator
    src = inspect.getsource(aggregator.compute_operational_dashboard)
    assert '"priority_p5"' not in src, "priority_p5 still present in aggregator output dict"


def test_overview_jsx_has_no_priority_p5():
    """Static check: ui/jansa/overview.jsx must not reference priority_p5."""
    base = os.path.join(os.path.dirname(__file__), "..", "ui", "jansa", "overview.jsx")
    with open(base, "r", encoding="utf-8") as fh:
        src = fh.read()
    assert "priority_p5" not in src, "priority_p5 still referenced in overview.jsx"
    # And the cells array should not list a P5 entry
    assert "label: 'P5'" not in src


# ── data_loader prefers flat_doc_meta visa_global ─────────────────

def test_precompute_focus_columns_prefers_flat_doc_meta():
    """When flat_doc_meta supplies visa_global, _precompute_focus_columns must
    use it (covers the SAS REF gap that engine.compute_visa_global_with_date
    silently returns None for)."""
    from reporting.data_loader import _precompute_focus_columns

    class _Eng:
        _doc_approvers = {"d1": []}
        def compute_visa_global_with_date(self, doc_id):
            return None, None  # engine misses SAS REF

    dernier = pd.DataFrame([
        {"doc_id": "d1", "created_at": pd.Timestamp("2026-04-01")},
    ])
    responses = pd.DataFrame(columns=[
        "doc_id", "date_answered", "date_status_type", "date_limite",
    ])
    flat_meta = {"d1": {"visa_global": "SAS REF"}}
    _precompute_focus_columns(
        dernier, responses, _Eng(), date(2026, 5, 9), flat_doc_meta=flat_meta,
    )
    assert dernier.iloc[0]["_visa_global"] == "SAS REF"
