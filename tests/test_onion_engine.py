"""
tests/test_onion_engine.py
--------------------------
Step 09 — Onion Layer Engine synthetic unit tests.

Tests 1–8 use synthetic DataFrames.
Test 9 (live full run) is skipped — Claude Code / Codex only.

Coverage:
  1  Clean closed chain           → 0 rows
  2  Primary delay only           → L3 only
  3  Mixed consultant + churn     → L1 + L3 + L4
  4  SAS dead chain               → L2 HIGH/CRITICAL
  5  MOEX waiting                 → L5
  6  Contradiction signal         → L6
  7  Duplicate prevention         → no duplicate (family_key, layer_code)
  8  Evidence rule                → all rows evidence_count >= 1
  9  Live full run                → SKIPPED
"""
from __future__ import annotations

import importlib
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

# ── ensure src/ is importable ─────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
_SRC  = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from chain_onion.onion_engine import build_onion_layers, OUTPUT_COLS  # noqa: E402


# =============================================================================
# Synthetic data helpers
# =============================================================================

_EVENT_DATE = pd.Timestamp("2024-06-01")
_DATA_DATE  = pd.Timestamp("2024-08-01")


def _make_register(family_key: str, current_state: str = "CLOSED_APPROVED") -> pd.DataFrame:
    return pd.DataFrame([{
        "family_key":               family_key,
        "total_versions":           1,
        "total_versions_requiring_cycle": 0,
        "current_state":            current_state,
        "portfolio_bucket":         "LIVE_OPERATIONAL",
        "current_blocking_actor_count": 0,
        "operational_relevance_score": 50,
        "first_submission_date":    pd.Timestamp("2024-01-01"),
        "latest_submission_date":   pd.Timestamp("2024-06-01"),
        "last_real_activity_date":  pd.Timestamp("2024-06-01"),
        "stale_days":               61,
        "chronic_flag":             False,
        "void_flag":                False,
        "abandoned_flag":           False,
    }])


def _make_metrics(family_key: str, current_state: str = "CLOSED_APPROVED", **kwargs) -> pd.DataFrame:
    row = {
        "family_key":         family_key,
        "numero":             family_key,
        "current_state":      current_state,
        "portfolio_bucket":   "LIVE_OPERATIONAL",
        "operational_relevance_score": 50,
        "total_versions":     1,
        "rejection_cycles":   0,
        "pressure_index":     50,
        "total_events":       1,
        "total_blocking_events": 0,
        "primary_wait_days":  0,
        "secondary_wait_days": 0,
        "moex_wait_days":     0,
        "sas_wait_days":      0,
        "cumulative_delay_days": 0,
        "stale_days":         61,
        "churn_ratio":        0.0,
    }
    row.update(kwargs)
    return pd.DataFrame([row])


def _ev_row(**kwargs) -> dict:
    """Build a minimal chain_events row with defaults."""
    defaults = {
        "family_key":             "FK001",
        "version_key":            "FK001_A",
        "instance_key":           "FK001_A_main",
        "event_seq":              1,
        "event_date":             _EVENT_DATE,
        "source":                 "OPS",
        "source_priority":        1,
        "actor":                  "CONTRACTOR_X",
        "actor_type":             "CONTRACTOR",
        "step_type":              "SUBMITTAL",
        "status":                 "VAO",
        "is_blocking":            False,
        "is_completed":           True,
        "requires_new_cycle":     False,
        "delay_contribution_days": 0,
        "issue_signal":           "NONE",
        "raw_reference":          "",
        "notes":                  "",
    }
    defaults.update(kwargs)
    return defaults


# =============================================================================
# Test 1 — Clean closed chain → 0 rows
# =============================================================================

class TestCleanClosedChain:
    """
    A chain that was approved cleanly: one version, no delays, no SAS REF, no MOEX.
    No contractor churn. No contradiction.
    Expect: 0 onion rows.
    """

    def _build(self):
        fk = "CLEAN001"
        events = pd.DataFrame([
            _ev_row(family_key=fk, event_seq=1, actor="CONTRACTOR_X", actor_type="CONTRACTOR",
                    step_type="SUBMITTAL", status="OPEN", is_blocking=False, is_completed=False),
            _ev_row(family_key=fk, event_seq=2, actor="SAS", actor_type="SAS",
                    step_type="RESPONSE", status="VAO", is_blocking=False, is_completed=True,
                    delay_contribution_days=0),
            _ev_row(family_key=fk, event_seq=3, actor="EGIS", actor_type="PRIMARY_CONSULTANT",
                    step_type="RESPONSE", status="VAO", is_blocking=False, is_completed=True,
                    delay_contribution_days=0),
        ])
        register = _make_register(fk, "CLOSED_APPROVED")
        metrics  = _make_metrics(fk, "CLOSED_APPROVED")
        return register, events, metrics

    def test_no_rows(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        assert len(result) == 0, f"Expected 0 rows for clean chain, got {len(result)}: {result.to_dict('records')}"

    def test_output_is_dataframe(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        assert isinstance(result, pd.DataFrame)


# =============================================================================
# Test 2 — Primary delay chain → L3 only
# =============================================================================

class TestPrimaryDelayOnly:
    """
    Primary consultant (EGIS) blocking with 42 delay days, no response date.
    No other issues.
    Expect: L3_PRIMARY_CONSULTANT_DELAY only.
    """

    def _build(self):
        fk = "PRI001"
        events = pd.DataFrame([
            _ev_row(family_key=fk, event_seq=1, actor="CONTRACTOR_X", actor_type="CONTRACTOR",
                    step_type="SUBMITTAL"),
            _ev_row(family_key=fk, event_seq=2, actor="SAS", actor_type="SAS",
                    step_type="RESPONSE", status="VAO", is_completed=True),
            _ev_row(family_key=fk, event_seq=3, actor="EGIS", actor_type="PRIMARY_CONSULTANT",
                    step_type="BLOCKING_WAIT", status="EN_COURS",
                    is_blocking=True, is_completed=False, event_date=pd.NaT,
                    delay_contribution_days=42),
        ])
        register = _make_register(fk, "OPEN_WAITING_PRIMARY_CONSULTANT")
        metrics  = _make_metrics(
            fk, "OPEN_WAITING_PRIMARY_CONSULTANT",
            primary_wait_days=42, total_blocking_events=1,
        )
        return register, events, metrics

    def test_l3_fires(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        codes = result["layer_code"].tolist()
        assert "L3_PRIMARY_CONSULTANT_DELAY" in codes, f"L3 not found in {codes}"

    def test_only_l3(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        codes = result["layer_code"].tolist()
        assert codes == ["L3_PRIMARY_CONSULTANT_DELAY"], f"Expected only L3, got {codes}"

    def test_l3_severity_high(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        l3 = result[result["layer_code"] == "L3_PRIMARY_CONSULTANT_DELAY"]
        assert l3.iloc[0]["severity_raw"] in ("HIGH", "CRITICAL"), (
            f"Expected HIGH/CRITICAL for 42-day delay, got {l3.iloc[0]['severity_raw']}"
        )

    def test_l3_evidence_positive(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        l3 = result[result["layer_code"] == "L3_PRIMARY_CONSULTANT_DELAY"]
        assert l3.iloc[0]["evidence_count"] >= 1


# =============================================================================
# Test 3 — Mixed: contractor churn + primary + secondary → L1 + L3 + L4
# =============================================================================

class TestMixedConsultantAndChurn:
    """
    - Contractor submitted version A twice (churn) → L1
    - EGIS (primary) blocking with delay → L3
    - Bureau Signalétique (secondary) blocking with delay → L4
    Expect: L1 + L3 + L4
    """

    def _build(self):
        fk = "MIX001"
        events = pd.DataFrame([
            # Version A instance 1
            _ev_row(family_key=fk, version_key=f"{fk}_A", instance_key=f"{fk}_A_1",
                    event_seq=1, actor="CONTRACTOR_X", actor_type="CONTRACTOR",
                    step_type="SUBMITTAL", requires_new_cycle=False),
            # Version A instance 2 (churn)
            _ev_row(family_key=fk, version_key=f"{fk}_A", instance_key=f"{fk}_A_2",
                    event_seq=2, actor="CONTRACTOR_X", actor_type="CONTRACTOR",
                    step_type="SUBMITTAL", requires_new_cycle=False),
            # SAS VAO
            _ev_row(family_key=fk, version_key=f"{fk}_A", instance_key=f"{fk}_A_main",
                    event_seq=3, actor="SAS", actor_type="SAS",
                    step_type="RESPONSE", status="VAO", is_completed=True),
            # EGIS blocking (primary)
            _ev_row(family_key=fk, version_key=f"{fk}_A", instance_key=f"{fk}_A_main",
                    event_seq=4, actor="EGIS", actor_type="PRIMARY_CONSULTANT",
                    step_type="BLOCKING_WAIT", is_blocking=True, is_completed=False,
                    event_date=pd.NaT, delay_contribution_days=30),
            # Bureau Signalétique (secondary)
            _ev_row(family_key=fk, version_key=f"{fk}_A", instance_key=f"{fk}_A_main",
                    event_seq=5, actor="Bureau Signalétique", actor_type="SECONDARY_CONSULTANT",
                    step_type="BLOCKING_WAIT", is_blocking=True, is_completed=False,
                    event_date=pd.NaT, delay_contribution_days=10),
        ])
        register = _make_register(fk, "OPEN_WAITING_MIXED_CONSULTANTS")
        metrics  = _make_metrics(
            fk, "OPEN_WAITING_MIXED_CONSULTANTS",
            total_versions=1, rejection_cycles=0,
            primary_wait_days=30, secondary_wait_days=10,
        )
        return register, events, metrics

    def test_l1_fires(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        assert "L1_CONTRACTOR_QUALITY" in result["layer_code"].tolist()

    def test_l3_fires(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        assert "L3_PRIMARY_CONSULTANT_DELAY" in result["layer_code"].tolist()

    def test_l4_fires(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        assert "L4_SECONDARY_CONSULTANT_DELAY" in result["layer_code"].tolist()

    def test_exact_layers(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        codes = set(result["layer_code"].tolist())
        expected = {"L1_CONTRACTOR_QUALITY", "L3_PRIMARY_CONSULTANT_DELAY", "L4_SECONDARY_CONSULTANT_DELAY"}
        assert codes == expected, f"Expected {expected}, got {codes}"

    def test_l1_issue_churn(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        l1 = result[result["layer_code"] == "L1_CONTRACTOR_QUALITY"]
        assert l1.iloc[0]["issue_type"] == "CHURN"


# =============================================================================
# Test 4 — SAS dead chain → L2 HIGH/CRITICAL
# =============================================================================

class TestSASDeadChain:
    """
    SAS issued REF twice. Very high delay (50+ days). Chain stalled.
    Expect: L2 with severity HIGH or CRITICAL.
    """

    def _build(self):
        fk = "SAS001"
        events = pd.DataFrame([
            _ev_row(family_key=fk, version_key=f"{fk}_A", event_seq=1,
                    actor="CONTRACTOR_X", actor_type="CONTRACTOR", step_type="SUBMITTAL"),
            _ev_row(family_key=fk, version_key=f"{fk}_A", event_seq=2,
                    actor="SAS", actor_type="SAS",
                    step_type="RESPONSE", status="REF", is_blocking=False, is_completed=True,
                    delay_contribution_days=25),
            _ev_row(family_key=fk, version_key=f"{fk}_B", event_seq=3,
                    actor="CONTRACTOR_X", actor_type="CONTRACTOR", step_type="SUBMITTAL"),
            _ev_row(family_key=fk, version_key=f"{fk}_B", event_seq=4,
                    actor="SAS", actor_type="SAS",
                    step_type="RESPONSE", status="REF", is_blocking=False, is_completed=True,
                    delay_contribution_days=30,
                    event_date=pd.Timestamp("2024-07-01")),
        ])
        register = _make_register(fk, "DEAD_AT_SAS")
        metrics  = _make_metrics(
            fk, "DEAD_AT_SAS",
            total_versions=2, rejection_cycles=2,
            sas_wait_days=55,
        )
        return register, events, metrics

    def test_l2_fires(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        assert "L2_SAS_GATE_FRICTION" in result["layer_code"].tolist()

    def test_l2_severity_critical(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        l2 = result[result["layer_code"] == "L2_SAS_GATE_FRICTION"]
        assert l2.iloc[0]["severity_raw"] in ("HIGH", "CRITICAL"), (
            f"Expected HIGH/CRITICAL for SAS dead chain, got {l2.iloc[0]['severity_raw']}"
        )

    def test_l2_issue_type(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        l2 = result[result["layer_code"] == "L2_SAS_GATE_FRICTION"]
        assert l2.iloc[0]["issue_type"] in ("REJECTION", "MULTI")


# =============================================================================
# Test 5 — MOEX waiting → L5
# =============================================================================

class TestMOEXWaiting:
    """
    MOEX step is blocking with no response date (inferred 30-day wait).
    Expect: L5_MOEX_ARBITRATION_DELAY.
    """

    def _build(self):
        fk = "MOEX001"
        events = pd.DataFrame([
            _ev_row(family_key=fk, event_seq=1, actor="CONTRACTOR_X", actor_type="CONTRACTOR"),
            _ev_row(family_key=fk, event_seq=2, actor="SAS", actor_type="SAS",
                    status="VAO", is_completed=True),
            _ev_row(family_key=fk, event_seq=3, actor="EGIS", actor_type="PRIMARY_CONSULTANT",
                    status="VAO", is_completed=True, delay_contribution_days=0),
            _ev_row(family_key=fk, event_seq=4, actor="MOEX", actor_type="MOEX",
                    step_type="BLOCKING_WAIT", status="EN_COURS",
                    is_blocking=True, is_completed=False,
                    event_date=pd.NaT, delay_contribution_days=0),
        ])
        register = _make_register(fk, "OPEN_WAITING_MOEX")
        metrics  = _make_metrics(fk, "OPEN_WAITING_MOEX", moex_wait_days=0)
        return register, events, metrics

    def test_l5_fires(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        assert "L5_MOEX_ARBITRATION_DELAY" in result["layer_code"].tolist()

    def test_only_l5(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        codes = set(result["layer_code"].tolist())
        assert codes == {"L5_MOEX_ARBITRATION_DELAY"}, f"Expected only L5, got {codes}"

    def test_l5_issue_dormancy(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        l5 = result[result["layer_code"] == "L5_MOEX_ARBITRATION_DELAY"]
        assert l5.iloc[0]["issue_type"] == "DORMANCY"


# =============================================================================
# Test 6 — Contradiction signal → L6
# =============================================================================

class TestContradictionSignal:
    """
    An event carries issue_signal = "CONTRADICTION" (GED ↔ report conflict).
    Expect: L6_DATA_REPORT_CONTRADICTION.
    """

    def _build(self):
        fk = "CONTRA001"
        events = pd.DataFrame([
            _ev_row(family_key=fk, event_seq=1, actor="CONTRACTOR_X", actor_type="CONTRACTOR"),
            _ev_row(family_key=fk, event_seq=2, actor="SAS", actor_type="SAS",
                    status="VAO", is_completed=True),
            _ev_row(family_key=fk, event_seq=3, actor="EGIS", actor_type="PRIMARY_CONSULTANT",
                    status="VAO", is_completed=True,
                    source="EFFECTIVE", issue_signal="CONTRADICTION"),
        ])
        register = _make_register(fk, "CLOSED_APPROVED")
        metrics  = _make_metrics(fk, "CLOSED_APPROVED")
        return register, events, metrics

    def test_l6_fires(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        assert "L6_DATA_REPORT_CONTRADICTION" in result["layer_code"].tolist()

    def test_l6_issue_contradiction(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        l6 = result[result["layer_code"] == "L6_DATA_REPORT_CONTRADICTION"]
        assert l6.iloc[0]["issue_type"] in ("CONTRADICTION", "MULTI")

    def test_l6_evidence_positive(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        l6 = result[result["layer_code"] == "L6_DATA_REPORT_CONTRADICTION"]
        assert l6.iloc[0]["evidence_count"] >= 1


# =============================================================================
# Test 7 — Duplicate prevention
# =============================================================================

class TestDuplicatePrevention:
    """
    Even if engine logic somehow produces duplicate (family_key, layer_code) pairs,
    deduplication must ensure uniqueness in the output.
    We test using a deliberately complex scenario that could trigger multiple
    matching conditions for the same layer.
    """

    def _build(self):
        fk = "DEDUP001"
        events = pd.DataFrame([
            _ev_row(family_key=fk, version_key=f"{fk}_A", instance_key=f"{fk}_A_1",
                    event_seq=1, actor="CONTRACTOR_X", actor_type="CONTRACTOR",
                    step_type="SUBMITTAL", requires_new_cycle=True),
            _ev_row(family_key=fk, version_key=f"{fk}_A", instance_key=f"{fk}_A_2",
                    event_seq=2, actor="CONTRACTOR_X", actor_type="CONTRACTOR",
                    step_type="SUBMITTAL"),
            _ev_row(family_key=fk, version_key=f"{fk}_B", instance_key=f"{fk}_B_1",
                    event_seq=3, actor="CONTRACTOR_X", actor_type="CONTRACTOR",
                    step_type="SUBMITTAL", requires_new_cycle=True),
            _ev_row(family_key=fk, version_key=f"{fk}_B", instance_key=f"{fk}_B_2",
                    event_seq=4, actor="CONTRACTOR_X", actor_type="CONTRACTOR",
                    step_type="SUBMITTAL"),
            _ev_row(family_key=fk, event_seq=5, actor="SAS", actor_type="SAS",
                    status="REF", is_completed=True, delay_contribution_days=20),
        ])
        register = _make_register(fk, "WAITING_CORRECTED_INDICE")
        register["total_versions"] = 2
        register["total_versions_requiring_cycle"] = 2
        metrics  = _make_metrics(fk, "WAITING_CORRECTED_INDICE",
                                  total_versions=2, rejection_cycles=2)
        return register, events, metrics

    def test_no_duplicates(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        dupes = result.duplicated(["family_key", "layer_code"], keep=False)
        assert not dupes.any(), (
            f"Duplicate (family_key, layer_code) pairs found: "
            f"{result[dupes][['family_key','layer_code']].values.tolist()}"
        )

    def test_all_layer_codes_valid(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        valid_codes = {
            "L1_CONTRACTOR_QUALITY", "L2_SAS_GATE_FRICTION",
            "L3_PRIMARY_CONSULTANT_DELAY", "L4_SECONDARY_CONSULTANT_DELAY",
            "L5_MOEX_ARBITRATION_DELAY", "L6_DATA_REPORT_CONTRADICTION",
        }
        bad = set(result["layer_code"].tolist()) - valid_codes
        assert not bad, f"Invalid layer codes found: {bad}"


# =============================================================================
# Test 8 — Evidence rule: all rows evidence_count >= 1
# =============================================================================

class TestEvidenceRule:
    """
    Across a mixed portfolio, every emitted onion row must have evidence_count >= 1.
    This test exercises all six layers in a combined portfolio.
    """

    def _build(self):
        rows = []
        registers = []
        metrics = []

        # Family A: contractor churn + SAS REF
        fk = "EVID_A"
        rows += [
            _ev_row(family_key=fk, version_key=f"{fk}_A", instance_key=f"{fk}_A_1",
                    event_seq=1, actor="CONTRACTOR_X", actor_type="CONTRACTOR",
                    requires_new_cycle=True),
            _ev_row(family_key=fk, version_key=f"{fk}_A", instance_key=f"{fk}_A_2",
                    event_seq=2, actor="CONTRACTOR_X", actor_type="CONTRACTOR"),
            _ev_row(family_key=fk, version_key=f"{fk}_A", instance_key=f"{fk}_A_main",
                    event_seq=3, actor="SAS", actor_type="SAS",
                    status="REF", is_completed=True, delay_contribution_days=10),
        ]
        registers.append(_make_register(fk, "WAITING_CORRECTED_INDICE"))
        metrics.append(_make_metrics(fk, "WAITING_CORRECTED_INDICE", total_versions=1, rejection_cycles=1))

        # Family B: MOEX dormancy
        fk = "EVID_B"
        rows += [
            _ev_row(family_key=fk, event_seq=1, actor="CONTRACTOR_Y", actor_type="CONTRACTOR"),
            _ev_row(family_key=fk, event_seq=2, actor="MOEX", actor_type="MOEX",
                    is_blocking=True, event_date=pd.NaT, delay_contribution_days=20),
        ]
        registers.append(_make_register(fk, "OPEN_WAITING_MOEX"))
        metrics.append(_make_metrics(fk, "OPEN_WAITING_MOEX", moex_wait_days=20))

        # Family C: primary + secondary delays
        fk = "EVID_C"
        rows += [
            _ev_row(family_key=fk, event_seq=1, actor="CONTRACTOR_Z", actor_type="CONTRACTOR"),
            _ev_row(family_key=fk, event_seq=2, actor="EGIS", actor_type="PRIMARY_CONSULTANT",
                    is_blocking=True, event_date=pd.NaT, delay_contribution_days=15),
            _ev_row(family_key=fk, event_seq=3, actor="Bureau X", actor_type="SECONDARY_CONSULTANT",
                    is_blocking=True, event_date=pd.NaT, delay_contribution_days=8),
        ]
        registers.append(_make_register(fk, "OPEN_WAITING_MIXED_CONSULTANTS"))
        metrics.append(_make_metrics(fk, "OPEN_WAITING_MIXED_CONSULTANTS",
                                      primary_wait_days=15, secondary_wait_days=8))

        # Family D: contradiction
        fk = "EVID_D"
        rows += [
            _ev_row(family_key=fk, event_seq=1, actor="CONTRACTOR_X", actor_type="CONTRACTOR"),
            _ev_row(family_key=fk, event_seq=2, actor="TERRELL", actor_type="PRIMARY_CONSULTANT",
                    issue_signal="CONTRADICTION", source="EFFECTIVE"),
        ]
        registers.append(_make_register(fk, "CLOSED_APPROVED"))
        metrics.append(_make_metrics(fk, "CLOSED_APPROVED"))

        events_df = pd.DataFrame(rows)
        register_df = pd.concat(registers, ignore_index=True)
        metrics_df = pd.concat(metrics, ignore_index=True)
        return register_df, events_df, metrics_df

    def test_all_evidence_count_positive(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        assert len(result) > 0, "Expected at least some onion rows"
        bad = result[result["evidence_count"] < 1]
        assert bad.empty, (
            f"Rows with evidence_count < 1: {bad[['family_key','layer_code','evidence_count']].to_dict('records')}"
        )

    def test_required_columns_present(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        missing = [c for c in OUTPUT_COLS if c not in result.columns]
        assert not missing, f"Missing output columns: {missing}"

    def test_severity_vocabulary(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        valid = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        bad = set(result["severity_raw"].tolist()) - valid
        assert not bad, f"Invalid severity values: {bad}"

    def test_issue_type_vocabulary(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        valid = {"DELAY", "REJECTION", "CHURN", "DORMANCY", "CONTRADICTION", "MULTI"}
        bad = set(result["issue_type"].tolist()) - valid
        assert not bad, f"Invalid issue_type values: {bad}"

    def test_confidence_in_range(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        bad = result[(result["confidence_raw"] < 10) | (result["confidence_raw"] > 100)]
        assert bad.empty, f"Confidence out of [10,100]: {bad[['family_key','layer_code','confidence_raw']].to_dict('records')}"

    def test_no_duplicate_primary_keys(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        dupes = result.duplicated(["family_key", "layer_code"])
        assert not dupes.any()

    def test_layer_rank_matches_code(self):
        reg, ev, met = self._build()
        result = build_onion_layers(reg, ev, met)
        rank_map = {
            "L1_CONTRACTOR_QUALITY": 1,
            "L2_SAS_GATE_FRICTION": 2,
            "L3_PRIMARY_CONSULTANT_DELAY": 3,
            "L4_SECONDARY_CONSULTANT_DELAY": 4,
            "L5_MOEX_ARBITRATION_DELAY": 5,
            "L6_DATA_REPORT_CONTRADICTION": 6,
        }
        for _, row in result.iterrows():
            expected = rank_map[row["layer_code"]]
            assert row["layer_rank"] == expected, (
                f"layer_rank mismatch for {row['layer_code']}: expected {expected}, got {row['layer_rank']}"
            )


# =============================================================================
# Test 9 — Live full run (skipped — Claude Code / Codex only)
# =============================================================================

@pytest.mark.skip(reason="Full live run requires 32k/407k dataset — Claude Code / Codex only")
class TestLiveDatasetRun:
    """
    Run build_onion_layers against the full live pipeline outputs.

    Expected output format:
      - total onion rows
      - rows by layer_code
      - rows by severity_raw
      - top families with 4+ layers

    To run:
        pytest tests/test_onion_engine.py -k TestLiveDatasetRun -s
    """

    def test_live_run(self):
        import sys
        sys.path.insert(0, str(_SRC))
        from chain_onion.source_loader import load_chain_sources
        from chain_onion.family_grouper import build_chain_versions, build_chain_register
        from chain_onion.chain_builder import build_chain_events
        from chain_onion.chain_classifier import classify_chains
        from chain_onion.chain_metrics import build_chain_metrics
        from chain_onion.onion_engine import build_onion_layers

        FLAT_GED_PATH = _ROOT / "output/intermediate/FLAT_GED.xlsx"
        DEBUG_PATH    = _ROOT / "output/intermediate/DEBUG_TRACE.csv"

        if not FLAT_GED_PATH.exists():
            pytest.skip(f"FLAT_GED.xlsx not found at {FLAT_GED_PATH}")

        sources = load_chain_sources(str(FLAT_GED_PATH), str(DEBUG_PATH) if DEBUG_PATH.exists() else None)
        ops_df       = sources["ops_df"]
        debug_df     = sources["debug_df"]
        effective_df = sources["effective_df"]

        chain_versions_df = build_chain_versions(ops_df)
        chain_register_df = build_chain_register(ops_df, chain_versions_df, debug_df, effective_df)
        chain_events_df   = build_chain_events(ops_df, debug_df, effective_df)
        chain_register_df = classify_chains(chain_register_df, chain_versions_df, chain_events_df, ops_df)
        chain_metrics_df, portfolio_metrics = build_chain_metrics(
            chain_register_df, chain_versions_df, chain_events_df, ops_df,
        )

        result = build_onion_layers(chain_register_df, chain_events_df, chain_metrics_df)

        print(f"\n=== LIVE ONION LAYER RUN ===")
        print(f"Total onion rows:   {len(result)}")
        print(f"Rows by layer_code: {result.groupby('layer_code').size().to_dict()}")
        print(f"Rows by severity:   {result.groupby('severity_raw').size().to_dict()}")

        multi_layer = result.groupby("family_key").size()
        top = multi_layer[multi_layer >= 4].sort_values(ascending=False).head(10)
        print(f"Top families with 4+ layers:\n{top}")

        assert len(result) > 0, "Expected at least some onion rows on live data"
        assert not result.duplicated(["family_key", "layer_code"]).any()
        assert (result["evidence_count"] >= 1).all()
