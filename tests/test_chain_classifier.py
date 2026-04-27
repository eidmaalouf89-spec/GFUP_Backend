"""
tests/test_chain_classifier.py
Step 07 — Chain Classifier: synthetic unit tests.

Test structure
--------------
Class 1: TestClosedChains           — CLOSED_VAO / CLOSED_VSO
Class 2: TestDeadAtSasA             — DEAD_AT_SAS_A
Class 3: TestWaitingCorrected       — WAITING_CORRECTED_INDICE
Class 4: TestBlockerIdentity        — MOEX / primary / secondary / mixed
Class 5: TestChronic                — CHRONIC_REF_CHAIN
Class 6: TestLegacyBacklog          — LEGACY_BACKLOG portfolio bucket
Class 7: TestLiveOperational        — LIVE_OPERATIONAL portfolio bucket
Class 8: TestScoreBounds            — score always in [0, 100]
Class 9: TestLiveDatasetMetrics     — SKIPPED (Claude Code / Codex only)
"""

import sys
import warnings
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import pytest

# ── importability ──────────────────────────────────────────────────────────
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Suppress query_library import warnings during tests
warnings.filterwarnings("ignore", category=UserWarning)

from chain_onion.chain_classifier import (  # noqa: E402
    classify_chains,
    VOID_DAYS,
    ABANDONED_DAYS,
    CHRONIC_REJECTION_COUNT,
    DEAD_AT_SAS_A_INACTIVITY_DAYS,
    OPERATIONAL_HORIZON_DATE,
    ARCHIVED_TERMINAL_STATES,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test data builders
# ─────────────────────────────────────────────────────────────────────────────

DATA_DATE = pd.Timestamp("2026-04-27")
DATA_DATE_STR = "2026-04-27"


def _make_ops_row(
    numero="100",
    indice="A",
    step_type="OPEN_DOC",
    actor_clean="SUBMITTER",
    status_clean=None,
    is_blocking=False,
    is_completed=True,
    requires_new_cycle=False,
    submittal_date="2025-10-01",
    response_date=None,
    data_date=DATA_DATE_STR,
    step_order=1,
):
    vk = f"{numero}_{indice}"
    return {
        "numero": numero,
        "indice": indice,
        "version_key": vk,
        "family_key": str(numero),
        "step_order": step_order,
        "step_type": step_type,
        "actor_clean": actor_clean,
        "status_clean": status_clean,
        "is_blocking": is_blocking,
        "is_completed": is_completed,
        "requires_new_cycle": requires_new_cycle,
        "submittal_date": pd.Timestamp(submittal_date) if submittal_date else pd.NaT,
        "response_date": pd.Timestamp(response_date) if response_date else pd.NaT,
        "data_date": pd.Timestamp(data_date),
        "delay_contribution_days": 0,
        "cumulative_delay_days": 0,
        "status_scope": "",
    }


def _make_ops_df(*rows):
    return pd.DataFrame(list(rows))


def _make_versions_row(
    numero="100",
    indice="A",
    has_blocking_rows=False,
    requires_new_cycle_flag=False,
    blocking_actor_count=0,
    version_sort_order=1,
    first_submission_date="2025-10-01",
    latest_response_date=None,
):
    vk = f"{numero}_{indice}"
    return {
        "family_key": str(numero),
        "version_key": vk,
        "numero": numero,
        "indice": indice,
        "row_count_ops": 1,
        "first_submission_date": pd.Timestamp(first_submission_date),
        "latest_submission_date": pd.Timestamp(first_submission_date),
        "latest_response_date": pd.Timestamp(latest_response_date) if latest_response_date else pd.NaT,
        "has_blocking_rows": has_blocking_rows,
        "blocking_actor_count": blocking_actor_count,
        "requires_new_cycle_flag": requires_new_cycle_flag,
        "completed_row_count": 0,
        "source_row_count": 1,
        "version_sort_order": version_sort_order,
    }


def _make_versions_df(*rows):
    return pd.DataFrame(list(rows))


def _make_register_row(
    numero="100",
    total_versions=1,
    latest_indice="A",
    latest_submission_date="2025-10-01",
    current_blocking_actor_count=0,
    waiting_primary_flag=False,
    waiting_secondary_flag=False,
    total_versions_requiring_cycle=0,
):
    return {
        "family_key": str(numero),
        "numero": numero,
        "total_versions": total_versions,
        "total_rows_ops": 2,
        "first_submission_date": pd.Timestamp("2025-10-01"),
        "latest_submission_date": pd.Timestamp(latest_submission_date),
        "latest_indice": latest_indice,
        "latest_version_key": f"{numero}_{latest_indice}",
        "total_blocking_versions": 0,
        "total_versions_requiring_cycle": total_versions_requiring_cycle,
        "total_completed_rows": 1,
        "current_blocking_actor_count": current_blocking_actor_count,
        "waiting_primary_flag": waiting_primary_flag,
        "waiting_secondary_flag": waiting_secondary_flag,
        "has_debug_trace": False,
        "has_effective_rows": False,
    }


def _make_register_df(*rows):
    return pd.DataFrame(list(rows))


def _make_event(
    family_key="100",
    version_key="100_A",
    event_date="2025-10-01",
    source="OPS",
    actor_type="CONTRACTOR",
    step_type="SUBMITTAL",
    is_blocking=False,
):
    return {
        "family_key": str(family_key),
        "version_key": version_key,
        "instance_key": version_key + "_main",
        "event_seq": 1,
        "event_date": pd.Timestamp(event_date) if event_date else pd.NaT,
        "source": source,
        "source_priority": 1,
        "actor": "ACTOR",
        "actor_type": actor_type,
        "step_type": step_type,
        "status": None,
        "is_blocking": is_blocking,
        "is_completed": True,
        "requires_new_cycle": False,
        "delay_contribution_days": 0,
        "issue_signal": "NONE",
        "raw_reference": "ops:x:1",
        "notes": None,
    }


def _make_events_df(*rows):
    return pd.DataFrame(list(rows))


# ─────────────────────────────────────────────────────────────────────────────
# Class 1 — Closed chains (CLOSED_VAO / CLOSED_VSO)
# ─────────────────────────────────────────────────────────────────────────────

class TestClosedChains:
    def _run_closed(self, status):
        """Build a single-version chain that is fully closed with given status."""
        numero = "111"
        ops = _make_ops_df(
            _make_ops_row(numero=numero, indice="A", step_type="OPEN_DOC", submittal_date="2025-10-01"),
            _make_ops_row(numero=numero, indice="A", step_type="MOEX", actor_clean="MOEX",
                          status_clean=status, is_completed=True, is_blocking=False,
                          response_date="2025-11-01"),
        )
        versions = _make_versions_df(_make_versions_row(numero=numero, has_blocking_rows=False))
        reg = _make_register_df(_make_register_row(numero=numero, current_blocking_actor_count=0))
        events = _make_events_df(
            _make_event(family_key=numero, event_date="2025-10-01"),
            _make_event(family_key=numero, event_date="2025-11-01", actor_type="MOEX"),
        )
        result = classify_chains(reg, versions, events, ops)
        assert len(result) == 1
        return result.iloc[0]

    def test_closed_vao(self):
        row = self._run_closed("VAO")
        assert row["current_state"] == "CLOSED_VAO"
        assert row["portfolio_bucket"] == "ARCHIVED_HISTORICAL"
        assert row["operational_relevance_score"] == 0

    def test_closed_vso(self):
        row = self._run_closed("VSO")
        assert row["current_state"] == "CLOSED_VSO"
        assert row["portfolio_bucket"] == "ARCHIVED_HISTORICAL"
        assert row["operational_relevance_score"] == 0

    def test_closed_fav_maps_to_vao(self):
        row = self._run_closed("FAV")
        assert row["current_state"] == "CLOSED_VAO"

    def test_closed_hm_maps_to_vao(self):
        row = self._run_closed("HM")
        assert row["current_state"] == "CLOSED_VAO"

    def test_closed_vaob_maps_to_vao(self):
        row = self._run_closed("VAOB")
        assert row["current_state"] == "CLOSED_VAO"

    def test_classifier_reason_contains_status(self):
        row = self._run_closed("VAO")
        assert "VAO" in row["classifier_reason"]

    def test_priority_hit_is_1_or_2(self):
        row_vao = self._run_closed("VAO")
        row_vso = self._run_closed("VSO")
        assert row_vao["classifier_priority_hit"] == 1
        assert row_vso["classifier_priority_hit"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# Class 2 — Dead at SAS A
# ─────────────────────────────────────────────────────────────────────────────

class TestDeadAtSasA:
    def _build(self, days_ago=60):
        numero = "222"
        ref_date = DATA_DATE - pd.Timedelta(days=days_ago)
        ops = _make_ops_df(
            _make_ops_row(numero=numero, indice="A", step_type="OPEN_DOC",
                          submittal_date=str(ref_date.date())),
            _make_ops_row(numero=numero, indice="A", step_type="SAS", actor_clean="SAS",
                          status_clean="REF", is_completed=True, is_blocking=False,
                          requires_new_cycle=True, response_date=str(ref_date.date()),
                          step_order=2),
        )
        versions = _make_versions_df(
            _make_versions_row(numero=numero, has_blocking_rows=False,
                               requires_new_cycle_flag=True)
        )
        reg = _make_register_df(_make_register_row(
            numero=numero, total_versions=1,
            latest_submission_date=str(ref_date.date()),
            current_blocking_actor_count=0,
        ))
        events = _make_events_df(
            _make_event(family_key=numero, event_date=str(ref_date.date())),
        )
        return classify_chains(reg, versions, events, ops)

    def test_dead_at_sas_a_fires(self):
        result = self._build(days_ago=60)
        assert result.iloc[0]["current_state"] == "DEAD_AT_SAS_A"

    def test_dead_at_sas_a_archived(self):
        result = self._build(days_ago=60)
        assert result.iloc[0]["portfolio_bucket"] == "ARCHIVED_HISTORICAL"

    def test_dead_at_sas_a_score_is_zero(self):
        result = self._build(days_ago=60)
        assert result.iloc[0]["operational_relevance_score"] == 0

    def test_dead_at_sas_a_priority_hit(self):
        result = self._build(days_ago=60)
        assert result.iloc[0]["classifier_priority_hit"] == 3

    def test_recent_sas_ref_not_dead(self):
        """SAS REF only 10 days ago — within inactivity threshold, must NOT be DEAD_AT_SAS_A."""
        result = self._build(days_ago=DEAD_AT_SAS_A_INACTIVITY_DAYS - 5)
        assert result.iloc[0]["current_state"] != "DEAD_AT_SAS_A"

    def test_multi_version_not_dead_at_sas_a(self):
        """Two versions → not eligible for DEAD_AT_SAS_A (requires total_versions=1)."""
        numero = "223"
        ref_date = DATA_DATE - pd.Timedelta(days=60)
        ops = _make_ops_df(
            _make_ops_row(numero=numero, indice="A", step_type="SAS", status_clean="REF",
                          is_completed=True, is_blocking=False, requires_new_cycle=True,
                          response_date=str(ref_date.date())),
            _make_ops_row(numero=numero, indice="B", step_type="SAS", actor_clean="SAS",
                          is_blocking=True, is_completed=False, step_order=1),
        )
        versions = _make_versions_df(
            _make_versions_row(numero=numero, indice="A", requires_new_cycle_flag=True,
                               version_sort_order=1),
            _make_versions_row(numero=numero, indice="B", has_blocking_rows=True,
                               blocking_actor_count=1, version_sort_order=2),
        )
        reg = _make_register_df(_make_register_row(
            numero=numero, total_versions=2, latest_indice="B",
            latest_submission_date=str(ref_date.date()),
            current_blocking_actor_count=1,
        ))
        events = _make_events_df(
            _make_event(family_key=numero, version_key=f"{numero}_B", event_date=str(ref_date.date()))
        )
        result = classify_chains(reg, versions, events, ops)
        assert result.iloc[0]["current_state"] != "DEAD_AT_SAS_A"


# ─────────────────────────────────────────────────────────────────────────────
# Class 3 — Waiting corrected indice
# ─────────────────────────────────────────────────────────────────────────────

class TestWaitingCorrected:
    def _build(self):
        """Indice A: SAS REF (requires_new_cycle). Indice B: blocking."""
        numero = "333"
        ops = _make_ops_df(
            _make_ops_row(numero=numero, indice="A", step_type="SAS", actor_clean="SAS",
                          status_clean="REF", is_completed=True, is_blocking=False,
                          requires_new_cycle=True, response_date="2025-08-01"),
            _make_ops_row(numero=numero, indice="B", step_type="OPEN_DOC",
                          submittal_date="2025-09-15"),
            _make_ops_row(numero=numero, indice="B", step_type="CONSULTANT", actor_clean="EGIS",
                          is_blocking=True, is_completed=False, step_order=2),
        )
        versions = _make_versions_df(
            _make_versions_row(numero=numero, indice="A", requires_new_cycle_flag=True,
                               version_sort_order=1),
            _make_versions_row(numero=numero, indice="B", has_blocking_rows=True,
                               blocking_actor_count=1, version_sort_order=2,
                               first_submission_date="2025-09-15"),
        )
        reg = _make_register_df(_make_register_row(
            numero=numero, total_versions=2, latest_indice="B",
            latest_submission_date="2025-09-15",
            current_blocking_actor_count=1,
            waiting_primary_flag=True,
        ))
        events = _make_events_df(
            _make_event(family_key=numero, version_key=f"{numero}_B",
                        event_date="2025-09-20", actor_type="PRIMARY_CONSULTANT"),
        )
        return classify_chains(reg, versions, events, ops)

    def test_waiting_corrected_state(self):
        result = self._build()
        assert result.iloc[0]["current_state"] == "WAITING_CORRECTED_INDICE"

    def test_waiting_corrected_priority(self):
        result = self._build()
        assert result.iloc[0]["classifier_priority_hit"] == 6

    def test_waiting_corrected_reason(self):
        result = self._build()
        reason = result.iloc[0]["classifier_reason"].lower()
        assert "prior version" in reason or "reject" in reason or "corrected" in reason

    def test_waiting_corrected_supersedes_primary_consultant_state(self):
        """Even though EGIS is blocking, WAITING_CORRECTED_INDICE fires before PRIMARY."""
        result = self._build()
        assert result.iloc[0]["current_state"] != "OPEN_WAITING_PRIMARY_CONSULTANT"


# ─────────────────────────────────────────────────────────────────────────────
# Class 4 — Blocker identity states
# ─────────────────────────────────────────────────────────────────────────────

class TestBlockerIdentity:
    def _build_blocker(
        self,
        actors,  # list of (actor_clean, step_type)
        numero="444",
        submission_date="2025-10-01",
        event_date="2025-11-01",
    ):
        """Build a chain with only the given blocking actors in indice A (no prior rejection)."""
        rows = [_make_ops_row(numero=numero, indice="A", step_type="OPEN_DOC",
                              submittal_date=submission_date)]
        for i, (actor, stype) in enumerate(actors):
            rows.append(_make_ops_row(
                numero=numero, indice="A", step_type=stype, actor_clean=actor,
                is_blocking=True, is_completed=False, step_order=i + 2,
            ))
        ops = _make_ops_df(*rows)
        versions = _make_versions_df(
            _make_versions_row(numero=numero, has_blocking_rows=True,
                               blocking_actor_count=len(actors))
        )
        waiting_primary = any(
            stype == "CONSULTANT" and any(kw in actor.upper() for kw in [
                "TERRELL", "EGIS", "BET SPK", "BET ASC", "BET EV", "BET FACADES", "ARCHI MOX", "MOEX"
            ])
            for actor, stype in actors
        )
        waiting_secondary = any(
            stype == "CONSULTANT" and not any(kw in actor.upper() for kw in [
                "TERRELL", "EGIS", "BET SPK", "BET ASC", "BET EV", "BET FACADES", "ARCHI MOX", "MOEX"
            ])
            for actor, stype in actors
        )
        reg = _make_register_df(_make_register_row(
            numero=numero, latest_submission_date=submission_date,
            current_blocking_actor_count=len(actors),
            waiting_primary_flag=waiting_primary,
            waiting_secondary_flag=waiting_secondary,
        ))
        events = _make_events_df(
            _make_event(family_key=numero, event_date=event_date),
        )
        return classify_chains(reg, versions, events, ops)

    def test_moex_only_blocking(self):
        result = self._build_blocker([("MOEX", "MOEX")])
        assert result.iloc[0]["current_state"] == "OPEN_WAITING_MOEX"
        assert result.iloc[0]["classifier_priority_hit"] == 7

    def test_primary_only_blocking(self):
        result = self._build_blocker([("EGIS STRUCTURE", "CONSULTANT")])
        assert result.iloc[0]["current_state"] == "OPEN_WAITING_PRIMARY_CONSULTANT"
        assert result.iloc[0]["classifier_priority_hit"] == 8

    def test_secondary_only_blocking(self):
        result = self._build_blocker([("Bureau Signalétique", "CONSULTANT")])
        assert result.iloc[0]["current_state"] == "OPEN_WAITING_SECONDARY_CONSULTANT"
        assert result.iloc[0]["classifier_priority_hit"] == 9

    def test_mixed_primary_secondary(self):
        result = self._build_blocker([
            ("TERRELL STRUCTURES", "CONSULTANT"),
            ("Commission Voirie", "CONSULTANT"),
        ])
        assert result.iloc[0]["current_state"] == "OPEN_WAITING_MIXED_CONSULTANTS"
        assert result.iloc[0]["classifier_priority_hit"] == 10

    def test_moex_plus_consultant_is_mixed(self):
        result = self._build_blocker([
            ("MOEX", "MOEX"),
            ("EGIS", "CONSULTANT"),
        ])
        assert result.iloc[0]["current_state"] == "OPEN_WAITING_MIXED_CONSULTANTS"

    def test_two_primaries_is_still_primary_state(self):
        result = self._build_blocker([
            ("EGIS STRUCTURE", "CONSULTANT"),
            ("BET SPK FLUIDES", "CONSULTANT"),
        ])
        assert result.iloc[0]["current_state"] == "OPEN_WAITING_PRIMARY_CONSULTANT"


# ─────────────────────────────────────────────────────────────────────────────
# Class 5 — Chronic ref chain
# ─────────────────────────────────────────────────────────────────────────────

class TestChronic:
    def _build_chronic(self, rejection_count=3, still_open=True):
        """
        Build a chain with rejection_count versions rejected (requires_new_cycle).
        If still_open, the last version has a blocking consultant.
        """
        numero = "555"
        rows_ops = []
        rows_ver = []

        indices = [chr(ord("A") + i) for i in range(rejection_count)]
        for idx_i, idx in enumerate(indices):
            rows_ops.append(_make_ops_row(
                numero=numero, indice=idx, step_type="SAS", actor_clean="SAS",
                status_clean="REF", is_completed=True, is_blocking=False,
                requires_new_cycle=True, response_date=f"2025-0{idx_i+1}-15",
            ))
            rows_ver.append(_make_versions_row(
                numero=numero, indice=idx,
                requires_new_cycle_flag=True,
                version_sort_order=idx_i + 1,
                first_submission_date=f"2025-0{idx_i+1}-01",
            ))

        # Latest version: open or closed
        last_indice = chr(ord("A") + rejection_count)
        if still_open:
            rows_ops.append(_make_ops_row(
                numero=numero, indice=last_indice, step_type="CONSULTANT",
                actor_clean="EGIS", is_blocking=True, is_completed=False, step_order=1,
            ))
            rows_ver.append(_make_versions_row(
                numero=numero, indice=last_indice, has_blocking_rows=True,
                blocking_actor_count=1, version_sort_order=rejection_count + 1,
            ))
            blocking_count = 1
        else:
            rows_ops.append(_make_ops_row(
                numero=numero, indice=last_indice, step_type="MOEX", actor_clean="MOEX",
                status_clean="VAO", is_completed=True, is_blocking=False,
                response_date="2025-11-15",
            ))
            rows_ver.append(_make_versions_row(
                numero=numero, indice=last_indice, version_sort_order=rejection_count + 1
            ))
            blocking_count = 0

        ops = _make_ops_df(*rows_ops)
        versions = _make_versions_df(*rows_ver)
        reg = _make_register_df(_make_register_row(
            numero=numero,
            total_versions=rejection_count + 1,
            latest_indice=last_indice,
            current_blocking_actor_count=blocking_count,
            total_versions_requiring_cycle=rejection_count,
        ))
        events = _make_events_df(
            _make_event(family_key=numero, event_date="2025-11-01"),
        )
        return classify_chains(reg, versions, events, ops)

    def test_chronic_fires_with_open_chain(self):
        result = self._build_chronic(rejection_count=CHRONIC_REJECTION_COUNT)
        assert result.iloc[0]["current_state"] == "CHRONIC_REF_CHAIN"

    def test_chronic_priority_hit(self):
        result = self._build_chronic(rejection_count=CHRONIC_REJECTION_COUNT)
        assert result.iloc[0]["classifier_priority_hit"] == 5

    def test_chronic_reason_contains_count(self):
        result = self._build_chronic(rejection_count=CHRONIC_REJECTION_COUNT)
        reason = result.iloc[0]["classifier_reason"]
        assert str(CHRONIC_REJECTION_COUNT) in reason

    def test_two_rejections_not_chronic(self):
        """CHRONIC_REJECTION_COUNT - 1 rejections must NOT produce CHRONIC_REF_CHAIN."""
        result = self._build_chronic(rejection_count=CHRONIC_REJECTION_COUNT - 1)
        assert result.iloc[0]["current_state"] != "CHRONIC_REF_CHAIN"

    def test_chronic_closed_chain_not_chronic(self):
        """Chain that got VAO after 3 rejections → CLOSED_VAO, not CHRONIC."""
        result = self._build_chronic(rejection_count=CHRONIC_REJECTION_COUNT, still_open=False)
        assert result.iloc[0]["current_state"] == "CLOSED_VAO"


# ─────────────────────────────────────────────────────────────────────────────
# Class 6 — Legacy backlog bucket
# ─────────────────────────────────────────────────────────────────────────────

class TestLegacyBacklog:
    def _build(self, activity_date="2025-07-01", submission_date="2025-07-01"):
        """Open chain with all activity before OPERATIONAL_HORIZON_DATE."""
        numero = "666"
        ops = _make_ops_df(
            _make_ops_row(numero=numero, indice="A", step_type="OPEN_DOC",
                          submittal_date=submission_date),
            _make_ops_row(numero=numero, indice="A", step_type="CONSULTANT", actor_clean="EGIS",
                          is_blocking=True, is_completed=False, step_order=2),
        )
        versions = _make_versions_df(
            _make_versions_row(numero=numero, has_blocking_rows=True, blocking_actor_count=1,
                               first_submission_date=submission_date)
        )
        reg = _make_register_df(_make_register_row(
            numero=numero, latest_submission_date=submission_date,
            current_blocking_actor_count=1, waiting_primary_flag=True,
        ))
        events = _make_events_df(
            _make_event(family_key=numero, event_date=activity_date),
        )
        return classify_chains(reg, versions, events, ops)

    def test_old_open_chain_is_legacy(self):
        result = self._build(activity_date="2025-07-01", submission_date="2025-07-01")
        assert result.iloc[0]["portfolio_bucket"] == "LEGACY_BACKLOG"

    def test_state_and_bucket_independent(self):
        """An OPEN_WAITING_PRIMARY chain can be LEGACY_BACKLOG simultaneously."""
        result = self._build()
        row = result.iloc[0]
        assert row["current_state"] == "OPEN_WAITING_PRIMARY_CONSULTANT"
        assert row["portfolio_bucket"] == "LEGACY_BACKLOG"

    def test_legacy_score_capped_at_30(self):
        result = self._build()
        assert result.iloc[0]["operational_relevance_score"] <= 30

    def test_legacy_score_non_negative(self):
        result = self._build()
        assert result.iloc[0]["operational_relevance_score"] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Class 7 — Live operational bucket
# ─────────────────────────────────────────────────────────────────────────────

class TestLiveOperational:
    def _build(self, activity_date="2026-01-15"):
        numero = "777"
        ops = _make_ops_df(
            _make_ops_row(numero=numero, indice="A", step_type="OPEN_DOC",
                          submittal_date="2025-10-01"),
            _make_ops_row(numero=numero, indice="A", step_type="CONSULTANT", actor_clean="EGIS",
                          is_blocking=True, is_completed=False, step_order=2),
        )
        versions = _make_versions_df(
            _make_versions_row(numero=numero, has_blocking_rows=True, blocking_actor_count=1)
        )
        reg = _make_register_df(_make_register_row(
            numero=numero, latest_submission_date="2025-10-01",
            current_blocking_actor_count=1, waiting_primary_flag=True,
        ))
        events = _make_events_df(
            _make_event(family_key=numero, event_date=activity_date),
        )
        return classify_chains(reg, versions, events, ops)

    def test_recent_activity_is_live(self):
        result = self._build(activity_date="2026-01-15")
        assert result.iloc[0]["portfolio_bucket"] == "LIVE_OPERATIONAL"

    def test_live_score_at_least_one(self):
        result = self._build()
        assert result.iloc[0]["operational_relevance_score"] >= 1

    def test_live_score_capped_at_100(self):
        result = self._build(activity_date=DATA_DATE_STR)  # activity today
        assert result.iloc[0]["operational_relevance_score"] <= 100

    def test_required_output_columns_present(self):
        result = self._build()
        for col in [
            "current_state", "portfolio_bucket", "stale_days",
            "last_real_activity_date", "operational_relevance_score",
            "classifier_reason", "classifier_priority_hit",
        ]:
            assert col in result.columns, f"Missing column: {col}"


# ─────────────────────────────────────────────────────────────────────────────
# Class 8 — Score bounds
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreBounds:
    def _run_various(self):
        """Run classify_chains on several distinct scenarios and collect all rows."""
        rows = []

        def add(numero, state_hint, activity_date, blocking, submission_date="2025-10-01"):
            ops_r = [
                _make_ops_row(numero=numero, indice="A", step_type="OPEN_DOC",
                              submittal_date=submission_date),
            ]
            if blocking:
                ops_r.append(_make_ops_row(
                    numero=numero, indice="A", step_type="MOEX", actor_clean="MOEX",
                    is_blocking=True, is_completed=False, step_order=2,
                ))
            else:
                ops_r.append(_make_ops_row(
                    numero=numero, indice="A", step_type="MOEX", actor_clean="MOEX",
                    status_clean="VAO", is_completed=True, is_blocking=False,
                    response_date=activity_date, step_order=2,
                ))
            return (ops_r, blocking, activity_date, submission_date)

        scenarios = [
            add("800", "live_blocking",   activity_date="2026-04-27", blocking=True,  submission_date="2026-04-01"),
            add("801", "live_quiet",      activity_date="2025-10-01", blocking=False, submission_date="2025-10-01"),
            add("802", "legacy_inactive", activity_date="2025-07-01", blocking=True,  submission_date="2025-07-01"),
            add("803", "closed_vao",      activity_date="2025-11-01", blocking=False, submission_date="2025-10-01"),
        ]

        all_ops, all_vers, all_reg, all_ev = [], [], [], []
        for idx, (ops_r, blocking, act_date, sub_date) in enumerate(scenarios):
            numero = str(800 + idx)
            for r in ops_r:
                all_ops.append(r)
            all_vers.append(_make_versions_row(
                numero=numero, has_blocking_rows=blocking, blocking_actor_count=1 if blocking else 0
            ))
            all_reg.append(_make_register_row(
                numero=numero, latest_submission_date=sub_date,
                current_blocking_actor_count=1 if blocking else 0,
            ))
            all_ev.append(_make_event(family_key=numero, event_date=act_date))

        ops = pd.DataFrame(all_ops)
        versions = pd.DataFrame(all_vers)
        reg = pd.DataFrame(all_reg)
        events = pd.DataFrame(all_ev)
        return classify_chains(reg, versions, events, ops)

    def test_all_scores_in_0_100(self):
        result = self._run_various()
        assert (result["operational_relevance_score"] >= 0).all()
        assert (result["operational_relevance_score"] <= 100).all()

    def test_archived_score_zero(self):
        result = self._run_various()
        archived = result[result["portfolio_bucket"] == "ARCHIVED_HISTORICAL"]
        if not archived.empty:
            assert (archived["operational_relevance_score"] == 0).all()

    def test_legacy_score_le_30(self):
        result = self._run_various()
        legacy = result[result["portfolio_bucket"] == "LEGACY_BACKLOG"]
        if not legacy.empty:
            assert (legacy["operational_relevance_score"] <= 30).all()

    def test_stale_days_non_negative(self):
        result = self._run_various()
        non_null = result["stale_days"].dropna()
        assert (non_null >= 0).all()

    def test_no_null_portfolio_bucket(self):
        result = self._run_various()
        assert result["portfolio_bucket"].notna().all()

    def test_no_null_current_state(self):
        result = self._run_various()
        assert result["current_state"].notna().all()

    def test_terminal_states_always_archived(self):
        result = self._run_various()
        from chain_onion.chain_classifier import ARCHIVED_TERMINAL_STATES
        terminal = result[result["current_state"].isin(ARCHIVED_TERMINAL_STATES)]
        if not terminal.empty:
            assert (terminal["portfolio_bucket"] == "ARCHIVED_HISTORICAL").all()


# ─────────────────────────────────────────────────────────────────────────────
# Class 9 — Full live dataset run (Claude Code / Codex only)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="Full live run — Claude Code / Codex only (>45s on live 32k dataset)")
class TestLiveDatasetMetrics:
    """
    Runs classify_chains on the real GED dataset.

    Expected metrics (indicative — will vary by run):
        - Every family gets one non-null current_state
        - Every family gets one portfolio_bucket
        - ARCHIVED_HISTORICAL score = 0 for all
        - LEGACY score <= 30 for all
        - LIVE score in [1, 100] for all
        - stale_days >= 0 for all non-null
    """

    def test_live_run(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

        from chain_onion.source_loader import load_chain_sources
        from chain_onion.family_grouper import build_chain_versions, build_chain_register
        from chain_onion.chain_builder import build_chain_events

        sources = load_chain_sources()
        ops_df        = sources["ops_df"]
        debug_df      = sources["debug_df"]
        effective_df  = sources["effective_df"]

        chain_versions_df  = build_chain_versions(ops_df)
        chain_register_df  = build_chain_register(ops_df, chain_versions_df, debug_df, effective_df)
        chain_events_df    = build_chain_events(ops_df, debug_df, effective_df)

        result = classify_chains(chain_register_df, chain_versions_df, chain_events_df, ops_df)

        assert result["current_state"].notna().all(), "Null current_state found"
        assert result["portfolio_bucket"].notna().all(), "Null portfolio_bucket found"

        state_counts  = result["current_state"].value_counts()
        bucket_counts = result["portfolio_bucket"].value_counts()
        score_series  = result["operational_relevance_score"]
        stale_series  = result["stale_days"].dropna()

        print("\n=== STEP 07 LIVE METRICS ===")
        print("State distribution:")
        print(state_counts.to_string())
        print("\nBucket distribution:")
        print(bucket_counts.to_string())
        print(f"\nScore: min={score_series.min()} avg={score_series.mean():.1f} "
              f"p90={score_series.quantile(0.9):.0f} max={score_series.max()}")
        print(f"Stale days: min={stale_series.min() if not stale_series.empty else 'N/A'} "
              f"avg={stale_series.mean():.1f if not stale_series.empty else 'N/A'} "
              f"null={int(result['stale_days'].isna().sum())}")

        archived = result[result["portfolio_bucket"] == "ARCHIVED_HISTORICAL"]
        legacy   = result[result["portfolio_bucket"] == "LEGACY_BACKLOG"]
        live     = result[result["portfolio_bucket"] == "LIVE_OPERATIONAL"]

        assert (archived["operational_relevance_score"] == 0).all()
        assert (legacy["operational_relevance_score"] <= 30).all()
        assert (live["operational_relevance_score"] >= 1).all()
        assert (live["operational_relevance_score"] <= 100).all()
        assert (stale_series >= 0).all()
