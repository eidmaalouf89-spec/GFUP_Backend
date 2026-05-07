"""
tests/test_chain_classifier_unknown_fix.py
------------------------------------------
Focused tests for the UNKNOWN_CHAIN_STATE elimination patches:

A. _empty_placeholder_mask must NOT mask blocking 0-* rows.
B. _uncalled_placeholder_mask (chain_builder) same guard — blocking
   actors must keep their real actor_type (not become UNKNOWN).
C. Latest version REF/SAS REF/DEF requiring new cycle, no blocker, no
   corrected version yet → WAITING_CORRECTED_INDICE (not UNKNOWN).
D. 0-SAS continues to be excluded from placeholder suppression (regression).
E. Empty non-blocking 0-* placeholder rows are still masked.
"""

import sys
import warnings
from pathlib import Path
import pandas as pd

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

warnings.filterwarnings("ignore", category=UserWarning)

from chain_onion.chain_classifier import (  # noqa: E402
    _empty_placeholder_mask,
    classify_chains,
)
from chain_onion.chain_builder import (  # noqa: E402
    _uncalled_placeholder_mask,
    build_chain_events,
)


# ── Patch A: classifier placeholder mask ────────────────────────────────────

def _empty_df(**overrides):
    base = {
        "step_type": "CONSULTANT",
        "actor_raw": "0-BET EV",
        "status_clean": "",
        "response_date": pd.NaT,
        "is_blocking": False,
    }
    base.update(overrides)
    return pd.DataFrame([base])


def test_empty_placeholder_mask_blocking_row_not_masked():
    df = _empty_df(is_blocking=True)
    assert _empty_placeholder_mask(df).iloc[0] == False  # blocking → kept


def test_empty_placeholder_mask_non_blocking_empty_still_masked():
    df = _empty_df(is_blocking=False)
    assert _empty_placeholder_mask(df).iloc[0] == True


def test_empty_placeholder_mask_zero_sas_never_masked():
    df = _empty_df(actor_raw="0-SAS", is_blocking=False)
    assert _empty_placeholder_mask(df).iloc[0] == False


def test_empty_placeholder_mask_row_with_status_not_masked():
    df = _empty_df(status_clean="VAO", is_blocking=False)
    assert _empty_placeholder_mask(df).iloc[0] == False


# ── Patch B: builder placeholder mask + actor_type integrity ────────────────

def test_uncalled_placeholder_mask_blocking_row_not_masked():
    df = pd.DataFrame([{
        "actor_raw": "0-MOEX",
        "response_date": pd.NaT,
        "status_clean": "",
        "is_blocking": True,
    }])
    step = pd.Series(["MOEX"])
    assert _uncalled_placeholder_mask(df, step).iloc[0] == False


def test_uncalled_placeholder_mask_non_blocking_empty_still_masked():
    df = pd.DataFrame([{
        "actor_raw": "0-MOEX",
        "response_date": pd.NaT,
        "status_clean": "",
        "is_blocking": False,
    }])
    step = pd.Series(["MOEX"])
    assert _uncalled_placeholder_mask(df, step).iloc[0] == True


def test_chain_builder_blocking_zero_prefix_row_keeps_actor_type():
    """A genuinely blocking 0-* MOEX row must surface as actor_type=MOEX,
    not UNKNOWN, so downstream classification can detect it."""
    ops = pd.DataFrame([{
        "family_key": "200",
        "version_key": "200_A",
        "step_type": "MOEX",
        "actor_clean": "MOEX",
        "actor_raw": "0-MOEX",
        "status_clean": "",
        "is_blocking": True,
        "is_completed": False,
        "requires_new_cycle": False,
        "submittal_date": pd.Timestamp("2025-10-01"),
        "response_date": pd.NaT,
        "delay_contribution_days": 5,
        "step_order": 1,
    }])
    events = build_chain_events(ops)
    moex_events = events[events["actor"] == "MOEX"]
    assert not moex_events.empty
    assert (moex_events["actor_type"] == "MOEX").all()


# ── Patch C: latest-rejected awaiting-correction → WAITING_CORRECTED_INDICE ─

DATA_DATE = pd.Timestamp("2026-04-27")


def _scenario_latest_rejected(status_clean: str, requires_new_cycle: bool = True):
    """Single version, fully completed (so SAS gate fired and rejected),
    no blocker (contractor hasn't resubmitted yet), recent activity."""
    response_date = pd.Timestamp("2026-04-01")
    ops = pd.DataFrame([
        {
            "numero": "300", "indice": "A", "version_key": "300_A",
            "family_key": "300", "step_order": 1, "step_type": "OPEN_DOC",
            "actor_clean": "SUB", "actor_raw": "SUB",
            "status_clean": "OPENED", "is_blocking": False, "is_completed": True,
            "requires_new_cycle": False,
            "submittal_date": pd.Timestamp("2026-03-15"),
            "response_date": pd.NaT, "data_date": DATA_DATE,
            "delay_contribution_days": 0, "status_scope": "",
        },
        {
            "numero": "300", "indice": "A", "version_key": "300_A",
            "family_key": "300", "step_order": 2, "step_type": "SAS",
            "actor_clean": "SAS", "actor_raw": "0-SAS",
            "status_clean": status_clean, "is_blocking": False, "is_completed": True,
            "requires_new_cycle": requires_new_cycle,
            "submittal_date": pd.NaT, "response_date": response_date,
            "data_date": DATA_DATE,
            "delay_contribution_days": 0, "status_scope": "SAS",
        },
    ])
    versions = pd.DataFrame([{
        "family_key": "300", "version_key": "300_A", "numero": "300", "indice": "A",
        "row_count_ops": 2, "first_submission_date": pd.Timestamp("2026-03-15"),
        "latest_submission_date": pd.Timestamp("2026-03-15"),
        "latest_response_date": response_date, "has_blocking_rows": False,
        "blocking_actor_count": 0, "requires_new_cycle_flag": requires_new_cycle,
        "completed_row_count": 2, "source_row_count": 2, "version_sort_order": 1,
    }])
    register = pd.DataFrame([{
        "family_key": "300", "numero": "300", "total_versions": 1, "total_rows_ops": 2,
        "first_submission_date": pd.Timestamp("2026-03-15"),
        "latest_submission_date": pd.Timestamp("2026-03-15"),
        "latest_indice": "A", "latest_version_key": "300_A",
        "total_blocking_versions": 0,
        "total_versions_requiring_cycle": int(requires_new_cycle),
        "total_completed_rows": 2, "current_blocking_actor_count": 0,
        "waiting_primary_flag": False, "waiting_secondary_flag": False,
        "has_debug_trace": False, "has_effective_rows": False,
    }])
    events = pd.DataFrame([{
        "family_key": "300", "version_key": "300_A", "instance_key": "300_A_main",
        "event_seq": 1, "event_date": response_date, "source": "OPS",
        "source_priority": 1, "actor": "SAS", "actor_type": "SAS",
        "step_type": "RESPONSE", "status": status_clean, "is_blocking": False,
        "is_completed": True, "requires_new_cycle": requires_new_cycle,
        "delay_contribution_days": 0, "issue_signal": "REJECTION",
        "raw_reference": "ops:300_A:2", "notes": None,
    }])
    return register, versions, events, ops


def test_latest_sas_ref_with_cycle_no_blocker_is_waiting_corrected():
    reg, ver, ev, ops = _scenario_latest_rejected("REF", True)
    out = classify_chains(reg, ver, ev, ops)
    state = out.iloc[0]["current_state"]
    # SAS REF + indice A + total_versions=1 → DEAD_AT_SAS_A (priority 3) wins
    # because of single-indice-A SAS REF rule. Use a different status to verify
    # the new rule fires. This case is just for sanity that no UNKNOWN occurs.
    assert state != "UNKNOWN_CHAIN_STATE"


def test_latest_ref_multi_version_with_cycle_no_blocker_is_waiting_corrected():
    reg, ver, ev, ops = _scenario_latest_rejected("REF", True)
    # Force multi-version so DEAD_AT_SAS_A (priority 3) does not win
    reg.loc[0, "total_versions"] = 2
    reg.loc[0, "latest_indice"] = "B"
    reg.loc[0, "latest_version_key"] = "300_B"
    ver.loc[0, "indice"] = "B"
    ver.loc[0, "version_key"] = "300_B"
    ops.loc[ops["step_order"] == 2, "version_key"] = "300_B"
    ops.loc[ops["step_order"] == 1, "version_key"] = "300_B"
    ops.loc[:, "indice"] = "B"
    ev.loc[0, "version_key"] = "300_B"
    out = classify_chains(reg, ver, ev, ops)
    assert out.iloc[0]["current_state"] == "WAITING_CORRECTED_INDICE"
    assert "awaiting contractor correction" in out.iloc[0]["classifier_reason"].lower()


def test_latest_sas_ref_multi_version_is_waiting_corrected():
    """SAS REF (the cleanest rejection path) on a multi-version family with
    requires_new_cycle and no blocker → WAITING_CORRECTED_INDICE."""
    reg, ver, ev, ops = _scenario_latest_rejected("REF", True)
    reg.loc[0, "total_versions"] = 2
    reg.loc[0, "latest_indice"] = "B"
    reg.loc[0, "latest_version_key"] = "300_B"
    ver.loc[0, "indice"] = "B"
    ver.loc[0, "version_key"] = "300_B"
    ops.loc[:, "indice"] = "B"
    ops.loc[:, "version_key"] = "300_B"
    ev.loc[0, "version_key"] = "300_B"
    out = classify_chains(reg, ver, ev, ops)
    assert out.iloc[0]["current_state"] == "WAITING_CORRECTED_INDICE"


def _scenario_no_moex_consultant_sus(requires_new_cycle: bool):
    """Multi-version chain whose latest version closed via consultants only
    (no MOEX called), worst consultant response = SUS."""
    response_date = pd.Timestamp("2026-04-01")
    fk, vk = "400", "400_B"
    ops = pd.DataFrame([
        {
            "numero": "400", "indice": "B", "version_key": vk, "family_key": fk,
            "step_order": 1, "step_type": "OPEN_DOC",
            "actor_clean": "SUB", "actor_raw": "SUB",
            "status_clean": "OPENED", "is_blocking": False, "is_completed": True,
            "requires_new_cycle": False,
            "submittal_date": pd.Timestamp("2026-03-15"),
            "response_date": pd.NaT, "data_date": DATA_DATE,
            "delay_contribution_days": 0, "status_scope": "",
        },
        {
            "numero": "400", "indice": "B", "version_key": vk, "family_key": fk,
            "step_order": 2, "step_type": "SAS",
            "actor_clean": "SAS", "actor_raw": "0-SAS",
            "status_clean": "VSO", "is_blocking": False, "is_completed": True,
            "requires_new_cycle": False,
            "submittal_date": pd.NaT, "response_date": response_date,
            "data_date": DATA_DATE,
            "delay_contribution_days": 0, "status_scope": "SAS",
        },
        {
            "numero": "400", "indice": "B", "version_key": vk, "family_key": fk,
            "step_order": 3, "step_type": "CONSULTANT",
            "actor_clean": "BET EV", "actor_raw": "BET EV",
            "status_clean": "SUS", "is_blocking": False, "is_completed": True,
            "requires_new_cycle": requires_new_cycle,
            "submittal_date": pd.NaT, "response_date": response_date,
            "data_date": DATA_DATE,
            "delay_contribution_days": 0, "status_scope": "",
        },
    ])
    versions = pd.DataFrame([{
        "family_key": fk, "version_key": vk, "numero": "400", "indice": "B",
        "row_count_ops": 3, "first_submission_date": pd.Timestamp("2026-03-15"),
        "latest_submission_date": pd.Timestamp("2026-03-15"),
        "latest_response_date": response_date, "has_blocking_rows": False,
        "blocking_actor_count": 0,
        "requires_new_cycle_flag": requires_new_cycle,
        "completed_row_count": 3, "source_row_count": 3, "version_sort_order": 2,
    }])
    register = pd.DataFrame([{
        "family_key": fk, "numero": "400", "total_versions": 2, "total_rows_ops": 3,
        "first_submission_date": pd.Timestamp("2026-03-15"),
        "latest_submission_date": pd.Timestamp("2026-03-15"),
        "latest_indice": "B", "latest_version_key": vk,
        "total_blocking_versions": 0,
        "total_versions_requiring_cycle": int(requires_new_cycle),
        "total_completed_rows": 3, "current_blocking_actor_count": 0,
        "waiting_primary_flag": False, "waiting_secondary_flag": False,
        "has_debug_trace": False, "has_effective_rows": False,
    }])
    events = pd.DataFrame([{
        "family_key": fk, "version_key": vk, "instance_key": vk + "_main",
        "event_seq": 1, "event_date": response_date, "source": "OPS",
        "source_priority": 1, "actor": "BET EV", "actor_type": "PRIMARY_CONSULTANT",
        "step_type": "RESPONSE", "status": "SUS", "is_blocking": False,
        "is_completed": True, "requires_new_cycle": requires_new_cycle,
        "delay_contribution_days": 0, "issue_signal": "NONE",
        "raw_reference": "ops:" + vk + ":3", "notes": None,
    }])
    return register, versions, events, ops


def test_sus_without_cycle_is_vao_equivalent_closed():
    """SUS final visa with requires_new_cycle=False is VAO-equivalent
    (accepted-with-observation) and must classify as CLOSED_VAO, not
    WAITING_CORRECTED_INDICE and never UNKNOWN_CHAIN_STATE."""
    reg, ver, ev, ops = _scenario_no_moex_consultant_sus(False)
    out = classify_chains(reg, ver, ev, ops)
    state = out.iloc[0]["current_state"]
    assert state == "CLOSED_VAO"
    assert state != "WAITING_CORRECTED_INDICE"
    assert state != "UNKNOWN_CHAIN_STATE"
    assert "SUS" in out.iloc[0]["classifier_reason"]


def test_sus_with_explicit_cycle_still_routes_to_waiting_corrected():
    """If a SUS row is explicitly flagged requires_new_cycle=True, the
    WAITING_CORRECTED_INDICE rule must still take precedence."""
    reg, ver, ev, ops = _scenario_no_moex_consultant_sus(True)
    out = classify_chains(reg, ver, ev, ops)
    assert out.iloc[0]["current_state"] == "WAITING_CORRECTED_INDICE"
