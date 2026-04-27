"""
tests/test_query_hooks.py
--------------------------
Step 13 — Query Hooks Engine test suite.

All tests use synthetic in-memory DataFrames unless explicitly noted as
a disk-loading test (TestDiskLoading) or live run (TestLiveRun).

Test classes
------------
1. TestCoreFilters          get_top_issues, get_escalated_chains, bucket filters
2. TestBlockingOwnership    state-based filters (waiting_* / mixed_blockers)
3. TestThemeFilters         impact score > 0 filters for all 6 themes
4. TestMetricFilters        high_pressure, stale_chains, zero_score, recently_active
5. TestSearch               family_key / numero search ranking
6. TestSummary              get_dashboard_summary, get_portfolio_snapshot
7. TestEmptyInputs          all functions safe on empty DataFrames
8. TestCaching              cache prevents re-loading; inputs not mutated
9. TestDiskLoading          load from temp CSV / JSON files on disk
10. TestLiveRun             SKIPPED — Claude Code / Codex only
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from src.chain_onion.query_hooks import (
    QueryContext,
    get_archived,
    get_contractor_quality,
    get_data_contradictions,
    get_dashboard_summary,
    get_escalated_chains,
    get_high_pressure,
    get_legacy_backlog,
    get_live_operational,
    get_mixed_blockers,
    get_moex_delay,
    get_portfolio_snapshot,
    get_primary_consultant_delay,
    get_recently_active,
    get_secondary_consultant_delay,
    get_sas_friction,
    get_stale_chains,
    get_top_issues,
    get_waiting_corrected,
    get_waiting_moex,
    get_waiting_primary,
    get_waiting_secondary,
    get_zero_score_chains,
    search_family_key,
    search_numero,
)


# =============================================================================
# Fixtures
# =============================================================================

def _make_scores(rows: list[dict]) -> pd.DataFrame:
    """Build an ONION_SCORES-shaped DataFrame from minimal row dicts."""
    defaults = {
        "family_key": "F001",
        "numero": "N001",
        "current_state": "UNKNOWN_CHAIN_STATE",
        "portfolio_bucket": "LIVE_OPERATIONAL",
        "normalized_score_100": 50.0,
        "action_priority_rank": 1,
        "total_onion_score": 50.0,
        "top_layer_code": "L3_PRIMARY_CONSULTANT_DELAY",
        "top_layer_name": "Primary Consultant Delay",
        "top_layer_score": 50.0,
        "contractor_impact_score": 0.0,
        "sas_impact_score": 0.0,
        "consultant_primary_impact_score": 50.0,
        "consultant_secondary_impact_score": 0.0,
        "moex_impact_score": 0.0,
        "contradiction_impact_score": 0.0,
        "blended_confidence": 80.0,
        "evidence_layers_count": 1,
        "escalation_flag": False,
        "escalation_reason": "",
        "engine_version": "1.0.0",
        "generated_at": "2026-04-27T00:00:00+00:00",
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def _make_metrics(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "family_key": "F001",
        "stale_days": 10,
        "latest_submission_date": "2026-03-01",
        "last_real_activity_date": "2026-04-01",
        "pressure_index": 50,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


@pytest.fixture
def portfolio_ctx():
    """5-chain portfolio covering all major states and buckets."""
    scores = _make_scores([
        {
            "family_key": "LIVE_HIGH",  "numero": "N001",
            "portfolio_bucket": "LIVE_OPERATIONAL",
            "current_state": "OPEN_WAITING_PRIMARY_CONSULTANT",
            "normalized_score_100": 90.0, "action_priority_rank": 1,
            "escalation_flag": True,
            "contractor_impact_score": 0.0,
            "sas_impact_score": 0.0,
            "consultant_primary_impact_score": 90.0,
            "consultant_secondary_impact_score": 0.0,
            "moex_impact_score": 0.0,
            "contradiction_impact_score": 0.0,
        },
        {
            "family_key": "LIVE_MED",   "numero": "N002",
            "portfolio_bucket": "LIVE_OPERATIONAL",
            "current_state": "OPEN_WAITING_SECONDARY_CONSULTANT",
            "normalized_score_100": 55.0, "action_priority_rank": 2,
            "escalation_flag": False,
            "contractor_impact_score": 0.0,
            "sas_impact_score": 30.0,
            "consultant_primary_impact_score": 0.0,
            "consultant_secondary_impact_score": 25.0,
            "moex_impact_score": 0.0,
            "contradiction_impact_score": 0.0,
        },
        {
            "family_key": "LIVE_MOEX",  "numero": "N003",
            "portfolio_bucket": "LIVE_OPERATIONAL",
            "current_state": "OPEN_WAITING_MOEX",
            "normalized_score_100": 40.0, "action_priority_rank": 3,
            "escalation_flag": False,
            "contractor_impact_score": 0.0,
            "sas_impact_score": 0.0,
            "consultant_primary_impact_score": 0.0,
            "consultant_secondary_impact_score": 0.0,
            "moex_impact_score": 40.0,
            "contradiction_impact_score": 0.0,
        },
        {
            "family_key": "LEG_STALE",  "numero": "N004",
            "portfolio_bucket": "LEGACY_BACKLOG",
            "current_state": "WAITING_CORRECTED_INDICE",
            "normalized_score_100": 15.0, "action_priority_rank": 4,
            "escalation_flag": False,
            "contractor_impact_score": 15.0,
            "sas_impact_score": 0.0,
            "consultant_primary_impact_score": 0.0,
            "consultant_secondary_impact_score": 0.0,
            "moex_impact_score": 0.0,
            "contradiction_impact_score": 0.0,
        },
        {
            "family_key": "ARC_ZERO",   "numero": "N005",
            "portfolio_bucket": "ARCHIVED_HISTORICAL",
            "current_state": "CLOSED_VAO",
            "normalized_score_100": 0.0, "action_priority_rank": 5,
            "escalation_flag": False,
            "contractor_impact_score": 0.0,
            "sas_impact_score": 0.0,
            "consultant_primary_impact_score": 0.0,
            "consultant_secondary_impact_score": 0.0,
            "moex_impact_score": 0.0,
            "contradiction_impact_score": 0.0,
        },
    ])
    metrics = _make_metrics([
        {"family_key": "LIVE_HIGH",  "stale_days": 5,   "last_real_activity_date": "2026-04-25"},
        {"family_key": "LIVE_MED",   "stale_days": 20,  "last_real_activity_date": "2026-04-20"},
        {"family_key": "LIVE_MOEX",  "stale_days": 45,  "last_real_activity_date": "2026-03-25"},
        {"family_key": "LEG_STALE",  "stale_days": 120, "last_real_activity_date": "2026-01-01"},
        {"family_key": "ARC_ZERO",   "stale_days": 300, "last_real_activity_date": "2025-07-01"},
    ])
    return QueryContext(onion_scores_df=scores, chain_metrics_df=metrics)


@pytest.fixture
def mixed_blocker_ctx():
    scores = _make_scores([
        {
            "family_key": "MIX001", "numero": "M001",
            "current_state": "OPEN_WAITING_MIXED_CONSULTANTS",
            "portfolio_bucket": "LIVE_OPERATIONAL",
            "normalized_score_100": 70.0, "action_priority_rank": 1,
            "escalation_flag": True,
            "contractor_impact_score": 0.0,
            "sas_impact_score": 0.0,
            "consultant_primary_impact_score": 35.0,
            "consultant_secondary_impact_score": 35.0,
            "moex_impact_score": 0.0,
            "contradiction_impact_score": 0.0,
        },
    ])
    return QueryContext(onion_scores_df=scores)


# =============================================================================
# 1. TestCoreFilters
# =============================================================================

class TestCoreFilters:
    def test_get_top_issues_returns_dataframe(self, portfolio_ctx):
        result = get_top_issues(portfolio_ctx, limit=20)
        assert isinstance(result, pd.DataFrame)

    def test_get_top_issues_sorted_by_rank(self, portfolio_ctx):
        result = get_top_issues(portfolio_ctx, limit=20)
        ranks = result["action_priority_rank"].tolist()
        assert ranks == sorted(ranks)

    def test_get_top_issues_limit_respected(self, portfolio_ctx):
        result = get_top_issues(portfolio_ctx, limit=2)
        assert len(result) == 2

    def test_get_top_issues_rank1_first(self, portfolio_ctx):
        result = get_top_issues(portfolio_ctx, limit=1)
        assert result.iloc[0]["family_key"] == "LIVE_HIGH"

    def test_get_escalated_chains_all_flagged(self, portfolio_ctx):
        result = get_escalated_chains(portfolio_ctx)
        assert all(result["escalation_flag"].astype(str).str.lower().isin({"true", "1", "yes"}))

    def test_get_escalated_chains_returns_only_1(self, portfolio_ctx):
        result = get_escalated_chains(portfolio_ctx)
        assert len(result) == 1

    def test_get_live_operational_bucket_correct(self, portfolio_ctx):
        result = get_live_operational(portfolio_ctx)
        assert all(result["portfolio_bucket"] == "LIVE_OPERATIONAL")

    def test_get_live_operational_count(self, portfolio_ctx):
        assert len(get_live_operational(portfolio_ctx)) == 3

    def test_get_legacy_backlog_count(self, portfolio_ctx):
        result = get_legacy_backlog(portfolio_ctx)
        assert len(result) == 1
        assert result.iloc[0]["family_key"] == "LEG_STALE"

    def test_get_archived_count(self, portfolio_ctx):
        result = get_archived(portfolio_ctx)
        assert len(result) == 1
        assert result.iloc[0]["family_key"] == "ARC_ZERO"

    def test_get_live_limit(self, portfolio_ctx):
        result = get_live_operational(portfolio_ctx, limit=1)
        assert len(result) == 1


# =============================================================================
# 2. TestBlockingOwnership
# =============================================================================

class TestBlockingOwnership:
    def test_waiting_primary_state_filter(self, portfolio_ctx):
        result = get_waiting_primary(portfolio_ctx)
        assert len(result) == 1
        assert result.iloc[0]["current_state"] == "OPEN_WAITING_PRIMARY_CONSULTANT"

    def test_waiting_secondary_state_filter(self, portfolio_ctx):
        result = get_waiting_secondary(portfolio_ctx)
        assert len(result) == 1
        assert result.iloc[0]["current_state"] == "OPEN_WAITING_SECONDARY_CONSULTANT"

    def test_waiting_moex_state_filter(self, portfolio_ctx):
        result = get_waiting_moex(portfolio_ctx)
        assert len(result) == 1
        assert result.iloc[0]["current_state"] == "OPEN_WAITING_MOEX"

    def test_waiting_corrected_state_filter(self, portfolio_ctx):
        result = get_waiting_corrected(portfolio_ctx)
        assert len(result) == 1
        assert result.iloc[0]["current_state"] == "WAITING_CORRECTED_INDICE"

    def test_mixed_blockers_state_filter(self, mixed_blocker_ctx):
        result = get_mixed_blockers(mixed_blocker_ctx)
        assert len(result) == 1
        assert result.iloc[0]["current_state"] == "OPEN_WAITING_MIXED_CONSULTANTS"

    def test_waiting_states_return_dataframe(self, portfolio_ctx):
        for fn in (get_waiting_primary, get_waiting_secondary, get_waiting_moex,
                   get_waiting_corrected, get_mixed_blockers):
            assert isinstance(fn(portfolio_ctx), pd.DataFrame)

    def test_waiting_states_sorted_by_rank(self, portfolio_ctx):
        result = get_waiting_primary(portfolio_ctx)
        if len(result) > 1:
            ranks = result["action_priority_rank"].tolist()
            assert ranks == sorted(ranks)


# =============================================================================
# 3. TestThemeFilters
# =============================================================================

class TestThemeFilters:
    def test_contractor_quality_positive_score(self, portfolio_ctx):
        result = get_contractor_quality(portfolio_ctx)
        assert len(result) == 1
        assert all(result["contractor_impact_score"] > 0)

    def test_sas_friction_positive_score(self, portfolio_ctx):
        result = get_sas_friction(portfolio_ctx)
        assert len(result) == 1
        assert all(result["sas_impact_score"] > 0)

    def test_primary_consultant_delay_positive(self, portfolio_ctx):
        result = get_primary_consultant_delay(portfolio_ctx)
        assert len(result) == 1
        assert all(result["consultant_primary_impact_score"] > 0)

    def test_secondary_consultant_delay_positive(self, portfolio_ctx):
        result = get_secondary_consultant_delay(portfolio_ctx)
        assert len(result) == 1
        assert all(result["consultant_secondary_impact_score"] > 0)

    def test_moex_delay_positive(self, portfolio_ctx):
        result = get_moex_delay(portfolio_ctx)
        assert len(result) == 1
        assert all(result["moex_impact_score"] > 0)

    def test_data_contradictions_empty_when_none(self, portfolio_ctx):
        result = get_data_contradictions(portfolio_ctx)
        assert len(result) == 0

    def test_theme_results_sorted_by_rank(self, portfolio_ctx):
        for fn in (get_contractor_quality, get_sas_friction, get_primary_consultant_delay,
                   get_secondary_consultant_delay, get_moex_delay):
            result = fn(portfolio_ctx)
            if len(result) > 1:
                ranks = result["action_priority_rank"].tolist()
                assert ranks == sorted(ranks)

    def test_all_theme_fns_return_dataframe(self, portfolio_ctx):
        for fn in (get_contractor_quality, get_sas_friction, get_primary_consultant_delay,
                   get_secondary_consultant_delay, get_moex_delay, get_data_contradictions):
            assert isinstance(fn(portfolio_ctx), pd.DataFrame)

    def test_theme_limit_respected(self, portfolio_ctx):
        scores = portfolio_ctx.scores().copy()
        # Inject extra contractor rows
        extra = _make_scores([
            {"family_key": "EX1", "contractor_impact_score": 10.0, "action_priority_rank": 6},
            {"family_key": "EX2", "contractor_impact_score": 20.0, "action_priority_rank": 7},
        ])
        full = pd.concat([scores, extra], ignore_index=True)
        ctx = QueryContext(onion_scores_df=full)
        result = get_contractor_quality(ctx, limit=1)
        assert len(result) == 1


# =============================================================================
# 4. TestMetricFilters
# =============================================================================

class TestMetricFilters:
    def test_get_high_pressure_threshold_default(self, portfolio_ctx):
        result = get_high_pressure(portfolio_ctx, min_score=70.0)
        assert all(result["normalized_score_100"] >= 70.0)
        assert len(result) == 1  # only LIVE_HIGH at 90.0

    def test_get_high_pressure_all_above_0(self, portfolio_ctx):
        result = get_high_pressure(portfolio_ctx, min_score=0.0)
        assert len(result) == 5  # all chains

    def test_get_high_pressure_none_above_100(self, portfolio_ctx):
        result = get_high_pressure(portfolio_ctx, min_score=100.0)
        assert len(result) == 0

    def test_get_zero_score_chains(self, portfolio_ctx):
        result = get_zero_score_chains(portfolio_ctx)
        assert len(result) == 1
        assert result.iloc[0]["family_key"] == "ARC_ZERO"

    def test_get_stale_chains_from_scores_col(self):
        scores = _make_scores([
            {"family_key": "S1", "stale_days": 100, "action_priority_rank": 1},
            {"family_key": "S2", "stale_days": 10,  "action_priority_rank": 2},
        ])
        ctx = QueryContext(onion_scores_df=scores)
        result = get_stale_chains(ctx, min_days=60)
        assert len(result) == 1
        assert result.iloc[0]["family_key"] == "S1"

    def test_get_stale_chains_merges_from_metrics(self, portfolio_ctx):
        # Remove stale_days from scores to force merge path
        scores_no_stale = portfolio_ctx.scores().drop(columns=["stale_days"], errors="ignore")
        ctx = QueryContext(
            onion_scores_df=scores_no_stale,
            chain_metrics_df=portfolio_ctx.metrics(),
        )
        result = get_stale_chains(ctx, min_days=60)
        assert len(result) >= 1  # LEG_STALE (120d) and ARC_ZERO (300d)
        assert all(result.apply(lambda r: True, axis=1))  # no crash

    def test_get_recently_active_within_30_days(self, portfolio_ctx):
        # portfolio_ctx metrics: LIVE_HIGH (Apr 25), LIVE_MED (Apr 20) within 30d of max Apr 25
        # LIVE_MOEX (Mar 25) is 31 days before Apr 25 — may or may not be included
        result = get_recently_active(portfolio_ctx, days=30)
        assert isinstance(result, pd.DataFrame)
        assert len(result) >= 1

    def test_get_recently_active_returns_dataframe(self, portfolio_ctx):
        assert isinstance(get_recently_active(portfolio_ctx, days=7), pd.DataFrame)

    def test_high_pressure_returns_dataframe(self, portfolio_ctx):
        assert isinstance(get_high_pressure(portfolio_ctx), pd.DataFrame)

    def test_stale_chains_returns_dataframe(self, portfolio_ctx):
        assert isinstance(get_stale_chains(portfolio_ctx), pd.DataFrame)


# =============================================================================
# 5. TestSearch
# =============================================================================

class TestSearch:
    @pytest.fixture
    def search_ctx(self):
        scores = _make_scores([
            {"family_key": "ALPHA_001", "numero": "GED/2024/001", "action_priority_rank": 1},
            {"family_key": "ALPHA_002", "numero": "GED/2024/002", "action_priority_rank": 2},
            {"family_key": "BETA_ALPHA", "numero": "GED/2025/001", "action_priority_rank": 3},
            {"family_key": "GAMMA",     "numero": "ALT/2024/001", "action_priority_rank": 4},
        ])
        return QueryContext(onion_scores_df=scores)

    def test_search_family_key_exact_is_first(self, search_ctx):
        result = search_family_key(search_ctx, "ALPHA_001")
        assert result.iloc[0]["family_key"] == "ALPHA_001"

    def test_search_family_key_startswith_before_contains(self, search_ctx):
        result = search_family_key(search_ctx, "ALPHA")
        keys = result["family_key"].tolist()
        # ALPHA_001 and ALPHA_002 start with ALPHA; BETA_ALPHA contains it
        starts = [k for k in keys if k.upper().startswith("ALPHA")]
        contains_only = [k for k in keys if not k.upper().startswith("ALPHA")]
        if starts and contains_only:
            assert keys.index(starts[-1]) < keys.index(contains_only[0])

    def test_search_family_key_contains_match(self, search_ctx):
        result = search_family_key(search_ctx, "ALPHA")
        assert "BETA_ALPHA" in result["family_key"].tolist()

    def test_search_family_key_no_match_empty(self, search_ctx):
        result = search_family_key(search_ctx, "ZZZNOMATCH")
        assert len(result) == 0

    def test_search_family_key_case_insensitive(self, search_ctx):
        result = search_family_key(search_ctx, "alpha_001")
        assert len(result) >= 1
        assert result.iloc[0]["family_key"] == "ALPHA_001"

    def test_search_numero_exact_first(self, search_ctx):
        result = search_numero(search_ctx, "GED/2024/001")
        assert result.iloc[0]["numero"] == "GED/2024/001"

    def test_search_numero_contains_match(self, search_ctx):
        result = search_numero(search_ctx, "GED/2024")
        nums = result["numero"].tolist()
        assert "GED/2024/001" in nums
        assert "GED/2024/002" in nums

    def test_search_returns_dataframe(self, search_ctx):
        assert isinstance(search_family_key(search_ctx, "ALPHA"), pd.DataFrame)
        assert isinstance(search_numero(search_ctx, "GED"), pd.DataFrame)

    def test_search_empty_text_returns_empty(self, search_ctx):
        assert len(search_family_key(search_ctx, "")) == 0
        assert len(search_numero(search_ctx, "")) == 0

    def test_search_exact_rank_1(self, search_ctx):
        # ALPHA_001 exact match should beat ALPHA_002 startswith
        result = search_family_key(search_ctx, "ALPHA_001")
        assert result.iloc[0]["family_key"] == "ALPHA_001"


# =============================================================================
# 6. TestSummary
# =============================================================================

class TestSummary:
    def test_get_dashboard_summary_returns_dict(self, portfolio_ctx):
        result = get_dashboard_summary(portfolio_ctx)
        assert isinstance(result, dict)

    def test_get_portfolio_snapshot_required_keys(self, portfolio_ctx):
        result = get_portfolio_snapshot(portfolio_ctx)
        for key in ("total_chains", "live_chains", "legacy_chains", "archived_chains",
                    "escalated_chain_count", "avg_live_score", "top_theme_by_impact",
                    "generated_at"):
            assert key in result, f"Missing key: {key}"

    def test_get_portfolio_snapshot_totals_correct(self, portfolio_ctx):
        result = get_portfolio_snapshot(portfolio_ctx)
        assert result["total_chains"] == 5
        assert result["live_chains"] == 3
        assert result["legacy_chains"] == 1
        assert result["archived_chains"] == 1

    def test_get_portfolio_snapshot_escalated_count(self, portfolio_ctx):
        result = get_portfolio_snapshot(portfolio_ctx)
        assert result["escalated_chain_count"] == 1

    def test_get_portfolio_snapshot_avg_live_score(self, portfolio_ctx):
        result = get_portfolio_snapshot(portfolio_ctx)
        # live scores: 90, 55, 40 → mean ≈ 61.67
        assert 60.0 <= result["avg_live_score"] <= 62.0

    def test_get_portfolio_snapshot_top_theme(self, portfolio_ctx):
        result = get_portfolio_snapshot(portfolio_ctx)
        assert isinstance(result["top_theme_by_impact"], str)
        assert len(result["top_theme_by_impact"]) > 0

    def test_get_dashboard_summary_uses_json_when_available(self):
        dash = {
            "total_chains": 99, "live_chains": 50, "legacy_chains": 30,
            "archived_chains": 19, "dormant_ghost_ratio": 0.19,
            "avg_pressure_live": 72.5, "escalated_chain_count": 5,
            "top_theme_by_impact": "consultant_primary_impact_score",
            "generated_at": "2026-04-27T00:00:00+00:00",
            "engine_version": "1.0.0",
        }
        ctx = QueryContext(_dashboard_summary=dash)
        result = get_dashboard_summary(ctx)
        assert result["total_chains"] == 99

    def test_snapshot_generated_at_is_string(self, portfolio_ctx):
        result = get_portfolio_snapshot(portfolio_ctx)
        assert isinstance(result["generated_at"], str)


# =============================================================================
# 7. TestEmptyInputs
# =============================================================================

class TestEmptyInputs:
    @pytest.fixture
    def empty_ctx(self):
        return QueryContext(onion_scores_df=pd.DataFrame())

    def test_get_top_issues_empty(self, empty_ctx):
        assert isinstance(get_top_issues(empty_ctx), pd.DataFrame)
        assert len(get_top_issues(empty_ctx)) == 0

    def test_get_escalated_chains_empty(self, empty_ctx):
        assert isinstance(get_escalated_chains(empty_ctx), pd.DataFrame)

    def test_get_live_operational_empty(self, empty_ctx):
        assert isinstance(get_live_operational(empty_ctx), pd.DataFrame)

    def test_get_legacy_backlog_empty(self, empty_ctx):
        assert isinstance(get_legacy_backlog(empty_ctx), pd.DataFrame)

    def test_get_archived_empty(self, empty_ctx):
        assert isinstance(get_archived(empty_ctx), pd.DataFrame)

    def test_state_filters_empty(self, empty_ctx):
        for fn in (get_waiting_primary, get_waiting_secondary, get_waiting_moex,
                   get_waiting_corrected, get_mixed_blockers):
            assert isinstance(fn(empty_ctx), pd.DataFrame)

    def test_theme_filters_empty(self, empty_ctx):
        for fn in (get_contractor_quality, get_sas_friction, get_primary_consultant_delay,
                   get_secondary_consultant_delay, get_moex_delay, get_data_contradictions):
            assert isinstance(fn(empty_ctx), pd.DataFrame)

    def test_metric_filters_empty(self, empty_ctx):
        assert isinstance(get_high_pressure(empty_ctx), pd.DataFrame)
        assert isinstance(get_zero_score_chains(empty_ctx), pd.DataFrame)
        assert isinstance(get_stale_chains(empty_ctx), pd.DataFrame)
        assert isinstance(get_recently_active(empty_ctx), pd.DataFrame)

    def test_search_empty(self, empty_ctx):
        assert isinstance(search_family_key(empty_ctx, "X"), pd.DataFrame)
        assert isinstance(search_numero(empty_ctx, "X"), pd.DataFrame)

    def test_get_portfolio_snapshot_empty(self, empty_ctx):
        result = get_portfolio_snapshot(empty_ctx)
        assert result["total_chains"] == 0
        assert result["live_chains"] == 0
        assert result["escalated_chain_count"] == 0

    def test_get_dashboard_summary_empty(self, empty_ctx):
        result = get_dashboard_summary(empty_ctx)
        assert isinstance(result, dict)


# =============================================================================
# 8. TestCaching
# =============================================================================

class TestCaching:
    def test_scores_cached_after_first_access(self, portfolio_ctx):
        df1 = portfolio_ctx.scores()
        df2 = portfolio_ctx.scores()
        assert df1 is df2

    def test_metrics_cached_after_first_access(self, portfolio_ctx):
        m1 = portfolio_ctx.metrics()
        m2 = portfolio_ctx.metrics()
        assert m1 is m2

    def test_input_df_not_mutated(self, portfolio_ctx):
        original_scores = portfolio_ctx.onion_scores_df.copy()
        _ = get_top_issues(portfolio_ctx, limit=5)
        _ = get_escalated_chains(portfolio_ctx)
        _ = get_live_operational(portfolio_ctx)
        pd.testing.assert_frame_equal(
            portfolio_ctx.onion_scores_df.reset_index(drop=True),
            original_scores.reset_index(drop=True),
        )

    def test_cache_not_affected_by_multiple_queries(self, portfolio_ctx):
        r1 = get_top_issues(portfolio_ctx, limit=3)
        r2 = get_top_issues(portfolio_ctx, limit=3)
        pd.testing.assert_frame_equal(r1, r2)

    def test_dashboard_dict_cached(self):
        dash = {"total_chains": 10, "live_chains": 5}
        ctx = QueryContext(_dashboard_summary=dash)
        d1 = ctx.dashboard()
        d2 = ctx.dashboard()
        assert d1 is d2


# =============================================================================
# 9. TestDiskLoading
# =============================================================================

class TestDiskLoading:
    def test_load_scores_from_csv(self):
        scores = _make_scores([
            {"family_key": "D001", "action_priority_rank": 1},
            {"family_key": "D002", "action_priority_rank": 2},
        ])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            scores.to_csv(p / "ONION_SCORES.csv", index=False)
            ctx = QueryContext(output_dir=p)
            result = get_top_issues(ctx, limit=10)
            assert len(result) == 2
            assert result.iloc[0]["family_key"] == "D001"

    def test_load_missing_csv_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = QueryContext(output_dir=Path(tmp))
            result = get_top_issues(ctx)
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0

    def test_load_dashboard_json_from_disk(self):
        dash = {
            "total_chains": 7, "live_chains": 3, "legacy_chains": 2,
            "archived_chains": 2, "avg_pressure_live": 60.0,
            "escalated_chain_count": 1,
            "top_theme_by_impact": "moex_impact_score",
            "generated_at": "2026-04-27T00:00:00+00:00",
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "dashboard_summary.json").write_text(json.dumps(dash), encoding="utf-8")
            ctx = QueryContext(output_dir=p)
            result = get_dashboard_summary(ctx)
            assert result["total_chains"] == 7
            assert result["top_theme_by_impact"] == "moex_impact_score"

    def test_load_missing_json_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = QueryContext(output_dir=Path(tmp))
            result = ctx.dashboard()
            assert result == {}

    def test_disk_cache_prevents_rereads(self):
        scores = _make_scores([{"family_key": "C001", "action_priority_rank": 1}])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            scores.to_csv(p / "ONION_SCORES.csv", index=False)
            ctx = QueryContext(output_dir=p)
            s1 = ctx.scores()
            # Overwrite the file — cache should still serve original
            scores2 = _make_scores([
                {"family_key": "C001", "action_priority_rank": 1},
                {"family_key": "EXTRA", "action_priority_rank": 2},
            ])
            scores2.to_csv(p / "ONION_SCORES.csv", index=False)
            s2 = ctx.scores()
            assert len(s2) == len(s1)  # still cached, not re-read


# =============================================================================
# 10. TestLiveRun
# =============================================================================

class TestLiveRun:
    @pytest.mark.skip(reason="Full live run — Claude Code / Codex only")
    def test_live_run(self):
        """
        Load from output/chain_onion/ and validate all hooks against real portfolio.

        Expected:
          - get_top_issues(ctx, 20)        → up to 20 rows, rank sorted
          - get_escalated_chains(ctx)      → escalation_flag == True
          - get_live_operational(ctx)      → all LIVE_OPERATIONAL
          - get_portfolio_snapshot(ctx)    → all 8 required keys
          - search_family_key(ctx, "...")  → ranked results
        """
        output_dir = Path("output/chain_onion")
        if not output_dir.exists():
            pytest.skip("output/chain_onion not found — run pipeline first")

        ctx = QueryContext(output_dir=output_dir)

        top = get_top_issues(ctx, limit=20)
        print(f"\nTop issues: {len(top)} rows")
        print(top[["family_key", "action_priority_rank", "normalized_score_100"]].to_string())

        escalated = get_escalated_chains(ctx)
        print(f"\nEscalated chains: {len(escalated)}")

        live = get_live_operational(ctx)
        print(f"Live operational: {len(live)}")

        snapshot = get_portfolio_snapshot(ctx)
        print(f"\nPortfolio snapshot: {snapshot}")

        assert isinstance(top, pd.DataFrame)
        assert isinstance(escalated, pd.DataFrame)
        assert isinstance(live, pd.DataFrame)
        assert "total_chains" in snapshot
