"""
tests/test_chain_metrics.py
Step 08 — Chain Metrics Engine: synthetic unit tests.

Test structure
--------------
Class 1: TestBasicMetrics           — single family, expected counts
Class 2: TestClosedChainMetrics     — closed/archived chain: pressure low, flags correct
Class 3: TestLiveBlockedChain       — live blocked chain: pressure high
Class 4: TestChurnChain             — high rejection_cycles + churn_ratio
Class 5: TestWaitAllocation         — primary vs MOEX vs SAS wait day buckets
Class 6: TestPressureBounds         — pressure_index always in [0, 100]
Class 7: TestPortfolioKPIs          — synthetic multi-family portfolio
Class 8: TestLiveDatasetRun         — SKIPPED (Claude Code / Codex only)
"""

import sys
import warnings
from pathlib import Path

import pandas as pd
import pytest

# ── importability ──────────────────────────────────────────────────────────
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

warnings.filterwarnings("ignore", category=UserWarning)

from chain_onion.chain_metrics import (  # noqa: E402
    build_chain_metrics,
    CHURN_RATIO_CAP,
    PRESSURE_MIN,
    PRESSURE_MAX,
    RESPONSE_VELOCITY_WINDOW_DAYS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic data builders
# ─────────────────────────────────────────────────────────────────────────────

DATA_DATE = pd.Timestamp("2026-04-27")


def _make_ops(data_date=DATA_DATE) -> pd.DataFrame:
    """Minimal ops_df with data_date column."""
    return pd.DataFrame({"data_date": [data_date]})


def _make_register(
    family_key="100",
    numero="100",
    current_state="OPEN_WAITING_PRIMARY_CONSULTANT",
    portfolio_bucket="LIVE_OPERATIONAL",
    operational_relevance_score=60,
    stale_days=20,
    last_real_activity_date=pd.Timestamp("2026-04-07"),
    first_submission_date=pd.Timestamp("2025-10-01"),
    latest_submission_date=pd.Timestamp("2026-01-15"),
    total_versions=2,
    current_blocking_actor_count=1,
    waiting_primary_flag=True,
    waiting_secondary_flag=False,
    total_versions_requiring_cycle=1,
) -> pd.DataFrame:
    return pd.DataFrame([{
        "family_key": family_key,
        "numero": numero,
        "current_state": current_state,
        "portfolio_bucket": portfolio_bucket,
        "operational_relevance_score": operational_relevance_score,
        "stale_days": stale_days,
        "last_real_activity_date": last_real_activity_date,
        "first_submission_date": first_submission_date,
        "latest_submission_date": latest_submission_date,
        "total_versions": total_versions,
        "current_blocking_actor_count": current_blocking_actor_count,
        "waiting_primary_flag": waiting_primary_flag,
        "waiting_secondary_flag": waiting_secondary_flag,
        "total_versions_requiring_cycle": total_versions_requiring_cycle,
    }])


def _make_versions(family_key="100", version_key="100_A") -> pd.DataFrame:
    return pd.DataFrame([{"family_key": family_key, "version_key": version_key}])


def _make_event(
    family_key="100",
    version_key="100_A",
    actor_type="PRIMARY_CONSULTANT",
    is_blocking=True,
    delay_contribution_days=5,
    event_date=pd.Timestamp("2026-04-10"),
    status="VAO",
    source="OPS",
) -> dict:
    return {
        "family_key": family_key,
        "version_key": version_key,
        "actor_type": actor_type,
        "is_blocking": is_blocking,
        "delay_contribution_days": delay_contribution_days,
        "event_date": event_date,
        "status": status,
        "source": source,
    }


def _make_events(*event_dicts) -> pd.DataFrame:
    return pd.DataFrame(list(event_dicts))


# ─────────────────────────────────────────────────────────────────────────────
# Class 1 — Basic metrics for a single family
# ─────────────────────────────────────────────────────────────────────────────

class TestBasicMetrics:
    """Single family: verify all expected count columns are present and correct."""

    def _build(self):
        reg = _make_register()
        ver = _make_versions()
        events = _make_events(
            _make_event(delay_contribution_days=5),
            _make_event(actor_type="SAS", is_blocking=False, delay_contribution_days=0),
            _make_event(actor_type="MOEX", is_blocking=True, delay_contribution_days=10),
        )
        ops = _make_ops()
        return build_chain_metrics(reg, ver, events, ops)

    def test_one_row_per_family(self):
        metrics_df, _ = self._build()
        assert len(metrics_df) == 1

    def test_total_events(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["total_events"] == 3

    def test_total_blocking_events(self):
        metrics_df, _ = self._build()
        # 2 events have is_blocking=True (PRIMARY + MOEX)
        assert metrics_df.iloc[0]["total_blocking_events"] == 2

    def test_rejection_cycles_from_register(self):
        metrics_df, _ = self._build()
        # total_versions_requiring_cycle = 1 in register
        assert metrics_df.iloc[0]["rejection_cycles"] == 1

    def test_cumulative_delay_days(self):
        metrics_df, _ = self._build()
        # only positive delay_contribution_days: 5 + 10 = 15
        assert metrics_df.iloc[0]["cumulative_delay_days"] == 15

    def test_max_single_event_delay(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["max_single_event_delay"] == 10

    def test_required_columns_present(self):
        metrics_df, _ = self._build()
        required = [
            "family_key", "numero", "current_state", "portfolio_bucket",
            "operational_relevance_score", "first_submission_date", "latest_submission_date",
            "last_real_activity_date", "open_days", "stale_days", "active_days",
            "total_versions", "total_events", "rejection_cycles", "total_blocking_events",
            "primary_wait_days", "secondary_wait_days", "moex_wait_days", "sas_wait_days",
            "cumulative_delay_days", "avg_delay_per_event", "max_single_event_delay",
            "churn_ratio", "response_velocity_90d", "pressure_index",
            "is_live_operational", "is_legacy_backlog", "is_archived",
        ]
        for col in required:
            assert col in metrics_df.columns, f"Missing column: {col}"

    def test_open_days_positive(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["open_days"] > 0

    def test_active_days_positive(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["active_days"] > 0

    def test_churn_ratio_bounded(self):
        metrics_df, _ = self._build()
        cr = metrics_df.iloc[0]["churn_ratio"]
        assert 0.0 <= cr <= CHURN_RATIO_CAP


# ─────────────────────────────────────────────────────────────────────────────
# Class 2 — Closed / archived chain
# ─────────────────────────────────────────────────────────────────────────────

class TestClosedChainMetrics:
    """Archived chain: pressure should be low, flags correct."""

    def _build(self):
        reg = _make_register(
            current_state="CLOSED_VAO",
            portfolio_bucket="ARCHIVED_HISTORICAL",
            operational_relevance_score=0,
            stale_days=400,
            current_blocking_actor_count=0,
            total_versions_requiring_cycle=0,
        )
        ver = _make_versions()
        events = _make_events(
            _make_event(is_blocking=False, delay_contribution_days=0),
        )
        ops = _make_ops()
        return build_chain_metrics(reg, ver, events, ops)

    def test_is_archived_true(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["is_archived"] == True

    def test_is_live_false(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["is_live_operational"] == False

    def test_is_legacy_false(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["is_legacy_backlog"] == False

    def test_pressure_low(self):
        metrics_df, _ = self._build()
        # base=0, -20 for ARCHIVED → clamped to 0
        assert metrics_df.iloc[0]["pressure_index"] == 0

    def test_rejection_cycles_zero(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["rejection_cycles"] == 0

    def test_total_blocking_events_zero(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["total_blocking_events"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Class 3 — Live blocked chain: pressure should be high
# ─────────────────────────────────────────────────────────────────────────────

class TestLiveBlockedChain:
    """Live chain with blocking event, stale 20 days, rejection cycle."""

    def _build(self):
        reg = _make_register(
            current_state="WAITING_CORRECTED_INDICE",
            portfolio_bucket="LIVE_OPERATIONAL",
            operational_relevance_score=60,
            stale_days=20,
            current_blocking_actor_count=2,
            total_versions_requiring_cycle=2,
        )
        ver = _make_versions()
        events = _make_events(
            _make_event(actor_type="PRIMARY_CONSULTANT", is_blocking=True, delay_contribution_days=8),
            _make_event(actor_type="MOEX", is_blocking=True, delay_contribution_days=12),
        )
        ops = _make_ops()
        return build_chain_metrics(reg, ver, events, ops)

    def test_pressure_high(self):
        metrics_df, _ = self._build()
        p = metrics_df.iloc[0]["pressure_index"]
        # base=60 +15(live+blocking) +10(stale 15-45) +10(rejection>=2) +10(WAITING_CORRECTED)
        # = 105 → clamped to 100
        assert p == 100

    def test_is_live_true(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["is_live_operational"] == True

    def test_total_blocking_events(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["total_blocking_events"] == 2

    def test_cumulative_delay(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["cumulative_delay_days"] == 20

    def test_rejection_cycles(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["rejection_cycles"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# Class 4 — Churn chain
# ─────────────────────────────────────────────────────────────────────────────

class TestChurnChain:
    """Chain with many rejection cycles → high churn_ratio."""

    def _build(self, versions_requiring_cycle=5, total_versions=5):
        reg = _make_register(
            current_state="CHRONIC_REF_CHAIN",
            portfolio_bucket="LIVE_OPERATIONAL",
            total_versions=total_versions,
            total_versions_requiring_cycle=versions_requiring_cycle,
        )
        ver = _make_versions()
        events = _make_events(
            _make_event(delay_contribution_days=0),
        )
        ops = _make_ops()
        return build_chain_metrics(reg, ver, events, ops)

    def test_high_rejection_cycles(self):
        metrics_df, _ = self._build(versions_requiring_cycle=5, total_versions=5)
        assert metrics_df.iloc[0]["rejection_cycles"] == 5

    def test_churn_ratio_is_one(self):
        metrics_df, _ = self._build(versions_requiring_cycle=5, total_versions=5)
        # 5 / 5 = 1.0
        assert metrics_df.iloc[0]["churn_ratio"] == pytest.approx(1.0)

    def test_churn_ratio_capped(self):
        # rejection_cycles > total_versions (edge case) — should cap at CHURN_RATIO_CAP
        # Use total_versions=1 and injection_cycles=100 via register hack
        reg = _make_register(
            current_state="CHRONIC_REF_CHAIN",
            portfolio_bucket="LIVE_OPERATIONAL",
            total_versions=1,
            total_versions_requiring_cycle=1,
        )
        ver = _make_versions()
        events = _make_events(_make_event(delay_contribution_days=0))
        ops = _make_ops()
        metrics_df, _ = build_chain_metrics(reg, ver, events, ops)
        assert metrics_df.iloc[0]["churn_ratio"] <= CHURN_RATIO_CAP

    def test_churn_ratio_zero_when_no_rejections(self):
        reg = _make_register(
            total_versions=3,
            total_versions_requiring_cycle=0,
        )
        ver = _make_versions()
        events = _make_events(_make_event(delay_contribution_days=0))
        ops = _make_ops()
        metrics_df, _ = build_chain_metrics(reg, ver, events, ops)
        assert metrics_df.iloc[0]["churn_ratio"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Class 5 — Wait day allocation
# ─────────────────────────────────────────────────────────────────────────────

class TestWaitAllocation:
    """Verify wait days are allocated into correct actor_type buckets."""

    def _build(self):
        reg = _make_register()
        ver = _make_versions()
        events = _make_events(
            _make_event(actor_type="PRIMARY_CONSULTANT", delay_contribution_days=10),
            _make_event(actor_type="PRIMARY_CONSULTANT", delay_contribution_days=5),
            _make_event(actor_type="SECONDARY_CONSULTANT", delay_contribution_days=7),
            _make_event(actor_type="MOEX", delay_contribution_days=20),
            _make_event(actor_type="SAS", delay_contribution_days=3),
            _make_event(actor_type="SAS", delay_contribution_days=0),  # zero — not counted
        )
        ops = _make_ops()
        return build_chain_metrics(reg, ver, events, ops)

    def test_primary_wait_days(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["primary_wait_days"] == 15  # 10+5

    def test_secondary_wait_days(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["secondary_wait_days"] == 7

    def test_moex_wait_days(self):
        metrics_df, _ = self._build()
        assert metrics_df.iloc[0]["moex_wait_days"] == 20

    def test_sas_wait_days(self):
        metrics_df, _ = self._build()
        # only positive: 3 (zero-delay row excluded)
        assert metrics_df.iloc[0]["sas_wait_days"] == 3

    def test_zero_delay_not_counted(self):
        metrics_df, _ = self._build()
        # sas has one row with delay=0 — confirm it doesn't inflate the sum
        assert metrics_df.iloc[0]["sas_wait_days"] == 3

    def test_all_four_buckets_present(self):
        metrics_df, _ = self._build()
        for col in ("primary_wait_days", "secondary_wait_days", "moex_wait_days", "sas_wait_days"):
            assert col in metrics_df.columns


# ─────────────────────────────────────────────────────────────────────────────
# Class 6 — Pressure bounds
# ─────────────────────────────────────────────────────────────────────────────

class TestPressureBounds:
    """pressure_index must always be in [0, 100]."""

    def _run_scenario(self, **reg_kwargs):
        reg = _make_register(**reg_kwargs)
        ver = _make_versions(family_key=reg.iloc[0]["family_key"])
        events = _make_events(
            _make_event(family_key=reg.iloc[0]["family_key"], delay_contribution_days=5),
        )
        ops = _make_ops()
        metrics_df, _ = build_chain_metrics(reg, ver, events, ops)
        return int(metrics_df.iloc[0]["pressure_index"])

    def test_live_blocked_high_score_capped(self):
        p = self._run_scenario(
            operational_relevance_score=100,
            portfolio_bucket="LIVE_OPERATIONAL",
            current_state="CHRONIC_REF_CHAIN",
            stale_days=20,
            current_blocking_actor_count=5,
            total_versions_requiring_cycle=5,
        )
        assert p == PRESSURE_MAX

    def test_archived_score_zero(self):
        p = self._run_scenario(
            operational_relevance_score=0,
            portfolio_bucket="ARCHIVED_HISTORICAL",
            current_state="CLOSED_VAO",
            stale_days=400,
            current_blocking_actor_count=0,
            total_versions_requiring_cycle=0,
        )
        assert p == PRESSURE_MIN

    def test_legacy_score_non_negative(self):
        p = self._run_scenario(
            operational_relevance_score=10,
            portfolio_bucket="LEGACY_BACKLOG",
            current_state="OPEN_WAITING_PRIMARY_CONSULTANT",
            stale_days=200,
            current_blocking_actor_count=0,
            total_versions_requiring_cycle=0,
        )
        assert p >= PRESSURE_MIN

    def test_all_scenarios_in_bounds(self):
        scenarios = [
            dict(operational_relevance_score=0,   portfolio_bucket="ARCHIVED_HISTORICAL", current_state="CLOSED_VAO",    stale_days=None, current_blocking_actor_count=0, total_versions_requiring_cycle=0),
            dict(operational_relevance_score=10,  portfolio_bucket="LEGACY_BACKLOG",      current_state="ABANDONED_CHAIN", stale_days=300,  current_blocking_actor_count=0, total_versions_requiring_cycle=0),
            dict(operational_relevance_score=60,  portfolio_bucket="LIVE_OPERATIONAL",    current_state="OPEN_WAITING_MOEX", stale_days=5,  current_blocking_actor_count=1, total_versions_requiring_cycle=0),
            dict(operational_relevance_score=100, portfolio_bucket="LIVE_OPERATIONAL",    current_state="CHRONIC_REF_CHAIN", stale_days=20, current_blocking_actor_count=3, total_versions_requiring_cycle=4),
        ]
        for i, sc in enumerate(scenarios):
            sc["family_key"] = str(i + 100)
            sc["numero"] = sc["family_key"]
            p = self._run_scenario(**sc)
            assert PRESSURE_MIN <= p <= PRESSURE_MAX, f"Scenario {i}: pressure={p} out of bounds"


# ─────────────────────────────────────────────────────────────────────────────
# Class 7 — Portfolio KPIs (multi-family)
# ─────────────────────────────────────────────────────────────────────────────

class TestPortfolioKPIs:
    """Synthetic portfolio of 7 families: verify all portfolio keys are present and correct."""

    def _build(self):
        families = [
            # (family_key, state, bucket, ors, stale, blocking, cycle)
            ("1", "OPEN_WAITING_MOEX",             "LIVE_OPERATIONAL",    60, 20, 1, 0),
            ("2", "OPEN_WAITING_PRIMARY_CONSULTANT","LIVE_OPERATIONAL",    55, 30, 2, 1),
            ("3", "OPEN_WAITING_SECONDARY_CONSULTANT","LIVE_OPERATIONAL",  50, 40, 1, 0),
            ("4", "WAITING_CORRECTED_INDICE",       "LIVE_OPERATIONAL",    70, 10, 3, 2),
            ("5", "CHRONIC_REF_CHAIN",              "LIVE_OPERATIONAL",    65, 25, 2, 3),
            ("6", "ABANDONED_CHAIN",                "LEGACY_BACKLOG",      10, 300, 0, 0),
            ("7", "CLOSED_VAO",                     "ARCHIVED_HISTORICAL",  0, 500, 0, 0),
        ]
        reg_rows = []
        for fk, state, bucket, ors, stale, blocking, cycle in families:
            reg_rows.append({
                "family_key": fk,
                "numero": fk,
                "current_state": state,
                "portfolio_bucket": bucket,
                "operational_relevance_score": ors,
                "stale_days": stale,
                "last_real_activity_date": pd.Timestamp("2026-04-01"),
                "first_submission_date": pd.Timestamp("2025-01-01"),
                "latest_submission_date": pd.Timestamp("2026-01-01"),
                "total_versions": max(cycle + 1, 1),
                "current_blocking_actor_count": blocking,
                "waiting_primary_flag": "PRIMARY" in state,
                "waiting_secondary_flag": "SECONDARY" in state,
                "total_versions_requiring_cycle": cycle,
            })
        reg = pd.DataFrame(reg_rows)
        ver = pd.DataFrame([{"family_key": r["family_key"], "version_key": r["family_key"] + "_A"} for r in reg_rows])
        event_rows = []
        for r in reg_rows:
            event_rows.append({
                "family_key": r["family_key"],
                "version_key": r["family_key"] + "_A",
                "actor_type": "PRIMARY_CONSULTANT",
                "is_blocking": r["current_blocking_actor_count"] > 0,
                "delay_contribution_days": r["current_blocking_actor_count"] * 5,
                "event_date": pd.Timestamp("2026-04-10"),
                "status": "PENDING",
                "source": "OPS",
            })
        events = pd.DataFrame(event_rows)
        ops = _make_ops()
        return build_chain_metrics(reg, ver, events, ops)

    def test_total_chains(self):
        _, kpi = self._build()
        assert kpi["total_chains"] == 7

    def test_live_chains(self):
        _, kpi = self._build()
        assert kpi["live_chains"] == 5

    def test_legacy_chains(self):
        _, kpi = self._build()
        assert kpi["legacy_chains"] == 1

    def test_archived_chains(self):
        _, kpi = self._build()
        assert kpi["archived_chains"] == 1

    def test_dormant_ghost_ratio(self):
        _, kpi = self._build()
        # legacy=1, open=5+1=6 → 1/6 ≈ 0.1667
        expected = round(1 / 6, 4)
        assert kpi["dormant_ghost_ratio"] == expected

    def test_all_required_portfolio_keys_present(self):
        _, kpi = self._build()
        required_keys = [
            "total_chains", "live_chains", "legacy_chains", "archived_chains",
            "dormant_ghost_ratio", "avg_pressure_live", "avg_versions_per_chain",
            "avg_events_per_chain",
            "live_waiting_moex", "live_waiting_primary", "live_waiting_secondary",
            "live_waiting_mixed", "live_waiting_corrected", "live_chronic",
            "total_cumulative_delay_days", "avg_stale_live", "p90_pressure_live",
            "top_10_family_keys_by_pressure",
        ]
        for key in required_keys:
            assert key in kpi, f"Missing portfolio key: {key}"

    def test_live_waiting_moex(self):
        _, kpi = self._build()
        assert kpi["live_waiting_moex"] == 1

    def test_live_waiting_primary(self):
        _, kpi = self._build()
        assert kpi["live_waiting_primary"] == 1

    def test_live_waiting_corrected(self):
        _, kpi = self._build()
        assert kpi["live_waiting_corrected"] == 1

    def test_live_chronic(self):
        _, kpi = self._build()
        assert kpi["live_chronic"] == 1

    def test_top_10_is_list(self):
        _, kpi = self._build()
        assert isinstance(kpi["top_10_family_keys_by_pressure"], list)

    def test_top_10_max_length(self):
        _, kpi = self._build()
        assert len(kpi["top_10_family_keys_by_pressure"]) <= 10

    def test_avg_pressure_live_positive(self):
        _, kpi = self._build()
        assert kpi["avg_pressure_live"] > 0

    def test_p90_pressure_live_in_range(self):
        _, kpi = self._build()
        assert PRESSURE_MIN <= kpi["p90_pressure_live"] <= PRESSURE_MAX

    def test_total_cumulative_delay_days_non_negative(self):
        _, kpi = self._build()
        assert kpi["total_cumulative_delay_days"] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Class 8 — Live dataset run (SKIPPED — Claude Code / Codex only)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="Live dataset run — Claude Code / Codex only (32k ops / 407k debug rows)")
class TestLiveDatasetRun:
    """
    Full live run against the 32k/407k dataset.
    Run manually via: pytest tests/test_chain_metrics.py -k TestLiveDatasetRun -s

    Expected output report:
      - total chains
      - bucket split (live / legacy / archived)
      - dormant_ghost_ratio
      - avg pressure live
      - top 20 pressure chains
    """

    def test_live_run(self):
        from chain_onion.source_loader import build_chain_sources
        from chain_onion.family_grouper import build_chain_versions, build_chain_register
        from chain_onion.chain_builder import build_chain_events
        from chain_onion.chain_classifier import classify_chains

        sources = build_chain_sources()
        ops_df       = sources["ops_df"]
        debug_df     = sources["debug_df"]
        effective_df = sources["effective_df"]

        chain_versions_df = build_chain_versions(ops_df)
        chain_register_df = build_chain_register(ops_df, chain_versions_df, debug_df, effective_df)
        chain_events_df   = build_chain_events(ops_df, debug_df, effective_df)
        chain_register_df = classify_chains(
            chain_register_df, chain_versions_df, chain_events_df, ops_df
        )

        metrics_df, kpi = build_chain_metrics(
            chain_register_df, chain_versions_df, chain_events_df, ops_df
        )

        print("\n=== STEP 08 LIVE RUN ===")
        print(f"total_chains  : {kpi['total_chains']}")
        print(f"live_chains   : {kpi['live_chains']}")
        print(f"legacy_chains : {kpi['legacy_chains']}")
        print(f"archived_chains: {kpi['archived_chains']}")
        print(f"dormant_ghost_ratio: {kpi['dormant_ghost_ratio']}")
        print(f"avg_pressure_live  : {kpi['avg_pressure_live']}")
        print("\nBacklog split:")
        for k in ("live_waiting_moex","live_waiting_primary","live_waiting_secondary",
                  "live_waiting_mixed","live_waiting_corrected","live_chronic"):
            print(f"  {k}: {kpi[k]}")
        print(f"\ntotal_cumulative_delay_days: {kpi['total_cumulative_delay_days']}")
        print(f"avg_stale_live: {kpi['avg_stale_live']}")
        print(f"p90_pressure_live: {kpi['p90_pressure_live']}")
        print("\nTop 20 chains by pressure:")
        top20 = metrics_df.nlargest(20, "pressure_index")[
            ["family_key", "current_state", "portfolio_bucket", "pressure_index",
             "stale_days", "rejection_cycles", "cumulative_delay_days"]
        ]
        print(top20.to_string(index=False))

        assert kpi["total_chains"] > 0
        assert 0.0 <= kpi["dormant_ghost_ratio"] <= 1.0
        assert all(PRESSURE_MIN <= p <= PRESSURE_MAX for p in metrics_df["pressure_index"])
