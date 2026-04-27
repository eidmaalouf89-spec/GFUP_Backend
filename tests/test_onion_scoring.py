"""
tests/test_onion_scoring.py
---------------------------
Step 10 — Onion Scoring Engine synthetic unit tests.

Tests 1–8 use synthetic DataFrames (Cowork / fast mode).
Test 9 (live full run) is skipped — Claude Code / Codex only.

Coverage:
  1  Single LOW layer              → low total_onion_score
  2  Critical live chain           → high normalized_score_100 + escalation
  3  Same severity, diff confidence → higher confidence scores higher
  4  Old stale vs recent issue     → recent scores higher
  5  Multi-layer chain             → total score sums components
  6  Theme bucketing               → L1→contractor, L2→sas, L3→primary, etc.
  7  Ranking stable                → dense ranks deterministic, LIVE before LEGACY
  8  Bounds                        → normalized_score_100 in [0, 100]
  9  Live full run                 → SKIPPED (Claude Code / Codex only)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# ── ensure src/ is importable ─────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
_SRC  = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from chain_onion.onion_scoring import build_onion_scores, _OUTPUT_COLS  # noqa: E402


# =============================================================================
# Synthetic data helpers
# =============================================================================

_RECENT_DATE  = "2026-04-20"   # 7 days before portfolio_date 2026-04-27 → recency 1.20
_OLD_DATE     = "2025-10-01"   # ~208 days ago → recency 0.60
_PORTFOLIO_DATE = "2026-04-27" # max trigger date drives data_date

def _layer_row(
    family_key: str,
    layer_code: str,
    severity_raw: str = "LOW",
    confidence_raw: int = 90,
    pressure_index: int = 0,
    evidence_count: int = 1,
    latest_trigger_date: str = _RECENT_DATE,
    current_state: str = "OPEN_WAITING_PRIMARY_CONSULTANT",
    portfolio_bucket: str = "LIVE_OPERATIONAL",
    numero: str = None,
) -> dict:
    code_to_name = {
        "L1_CONTRACTOR_QUALITY":         "Contractor Quality",
        "L2_SAS_GATE_FRICTION":          "SAS Gate Friction",
        "L3_PRIMARY_CONSULTANT_DELAY":   "Primary Consultant Delay",
        "L4_SECONDARY_CONSULTANT_DELAY": "Secondary Consultant Delay",
        "L5_MOEX_ARBITRATION_DELAY":     "MOEX Arbitration Delay",
        "L6_DATA_REPORT_CONTRADICTION":  "Data/Report Contradiction",
    }
    rank_map = {f"L{i}": i for i in range(1, 7)}
    layer_rank = int(layer_code[1])
    return {
        "family_key":           family_key,
        "numero":               numero or family_key,
        "layer_code":           layer_code,
        "layer_name":           code_to_name.get(layer_code, layer_code),
        "layer_rank":           layer_rank,
        "issue_type":           "DELAY",
        "severity_raw":         severity_raw,
        "confidence_raw":       confidence_raw,
        "pressure_index":       pressure_index,
        "evidence_count":       evidence_count,
        "evidence_event_refs":  "1",
        "trigger_metrics":      "delay_days=10",
        "first_trigger_date":   latest_trigger_date,
        "latest_trigger_date":  latest_trigger_date,
        "current_state":        current_state,
        "portfolio_bucket":     portfolio_bucket,
        "engine_version":       "0.9.0",
        "generated_at":         "2026-04-27T00:00:00+00:00",
    }


def _make_onion(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _make_register(family_key: str, current_state: str = "OPEN_WAITING_PRIMARY_CONSULTANT",
                   portfolio_bucket: str = "LIVE_OPERATIONAL", numero: str = None) -> pd.DataFrame:
    return pd.DataFrame([{
        "family_key":     family_key,
        "numero":         numero or family_key,
        "current_state":  current_state,
        "portfolio_bucket": portfolio_bucket,
    }])


def _make_metrics(family_key: str, current_state: str = "OPEN_WAITING_PRIMARY_CONSULTANT",
                  portfolio_bucket: str = "LIVE_OPERATIONAL", pressure_index: int = 0) -> pd.DataFrame:
    return pd.DataFrame([{
        "family_key":     family_key,
        "numero":         family_key,
        "current_state":  current_state,
        "portfolio_bucket": portfolio_bucket,
        "pressure_index": pressure_index,
    }])


# =============================================================================
# Test 1 — Single LOW layer produces a low total_onion_score
# =============================================================================

class TestSingleLowLayer:
    """Test 1 — Single LOW layer → expected low score."""

    def setup_method(self):
        rows = [_layer_row("F001", "L3_PRIMARY_CONSULTANT_DELAY",
                           severity_raw="LOW", confidence_raw=90,
                           pressure_index=0, evidence_count=1,
                           latest_trigger_date=_RECENT_DATE)]
        self.onion = _make_onion(rows)
        self.register = _make_register("F001")
        self.metrics  = _make_metrics("F001")
        self.scores, self.summary = build_onion_scores(
            self.onion, self.metrics, self.register
        )

    def test_returns_dataframe(self):
        assert isinstance(self.scores, pd.DataFrame)

    def test_one_row(self):
        assert len(self.scores) == 1

    def test_low_total_score(self):
        # LOW severity_weight=10, confidence=0.9, pressure=0.60, evidence=1.08, recency=1.20
        # max = 10 * 0.9 * 0.60 * 1.20 * 1.08 = 6.998
        score = self.scores.iloc[0]["total_onion_score"]
        assert score < 15.0, f"Expected LOW layer score < 15, got {score}"

    def test_normalized_is_100_for_single_chain(self):
        # Single chain in portfolio → it's the max, so normalized = 100
        assert self.scores.iloc[0]["normalized_score_100"] == pytest.approx(100.0)

    def test_required_columns(self):
        for col in _OUTPUT_COLS:
            assert col in self.scores.columns, f"Missing column: {col}"

    def test_top_layer_is_l3(self):
        assert self.scores.iloc[0]["top_layer_code"] == "L3_PRIMARY_CONSULTANT_DELAY"

    def test_consultant_primary_bucket_populated(self):
        assert self.scores.iloc[0]["consultant_primary_impact_score"] > 0


# =============================================================================
# Test 2 — Critical live chain → high normalized score + escalation
# =============================================================================

class TestCriticalLiveChain:
    """Test 2 — Critical live chain with high pressure → escalation."""

    def setup_method(self):
        # CRITICAL chain at pressure 80, recent trigger
        rows = [
            _layer_row("CRIT001", "L3_PRIMARY_CONSULTANT_DELAY",
                       severity_raw="CRITICAL", confidence_raw=90,
                       pressure_index=80, evidence_count=5,
                       latest_trigger_date=_PORTFOLIO_DATE),
            _layer_row("LOW001", "L3_PRIMARY_CONSULTANT_DELAY",
                       severity_raw="LOW", confidence_raw=40,
                       pressure_index=0, evidence_count=1,
                       latest_trigger_date=_OLD_DATE,
                       portfolio_bucket="LEGACY_BACKLOG"),
        ]
        self.onion    = _make_onion(rows)
        self.register = pd.concat([
            _make_register("CRIT001", portfolio_bucket="LIVE_OPERATIONAL"),
            _make_register("LOW001",  portfolio_bucket="LEGACY_BACKLOG"),
        ]).reset_index(drop=True)
        self.metrics  = pd.concat([
            _make_metrics("CRIT001", portfolio_bucket="LIVE_OPERATIONAL", pressure_index=80),
            _make_metrics("LOW001",  portfolio_bucket="LEGACY_BACKLOG",   pressure_index=0),
        ]).reset_index(drop=True)

        self.scores, self.summary = build_onion_scores(
            self.onion, self.metrics, self.register
        )

    def _crit_row(self):
        return self.scores[self.scores["family_key"] == "CRIT001"].iloc[0]

    def test_critical_chain_normalized_high(self):
        assert self._crit_row()["normalized_score_100"] == pytest.approx(100.0)

    def test_critical_chain_escalated(self):
        assert bool(self._crit_row()["escalation_flag"]) is True

    def test_escalation_reason_mentions_critical(self):
        reason = self._crit_row()["escalation_reason"]
        assert "critical top layer" in reason or "high normalized" in reason

    def test_low_chain_not_escalated(self):
        low_row = self.scores[self.scores["family_key"] == "LOW001"].iloc[0]
        assert bool(low_row["escalation_flag"]) is False

    def test_crit_ranks_first(self):
        assert self._crit_row()["action_priority_rank"] == 1


# =============================================================================
# Test 3 — Same severity, different confidence → higher confidence scores higher
# =============================================================================

class TestConfidenceInfluence:
    """Test 3 — Same severity, different confidence → higher confidence scores higher."""

    def setup_method(self):
        rows = [
            _layer_row("HIGH_CONF", "L2_SAS_GATE_FRICTION",
                       severity_raw="MEDIUM", confidence_raw=90,
                       pressure_index=0, evidence_count=1,
                       latest_trigger_date=_RECENT_DATE),
            _layer_row("LOW_CONF", "L2_SAS_GATE_FRICTION",
                       severity_raw="MEDIUM", confidence_raw=30,
                       pressure_index=0, evidence_count=1,
                       latest_trigger_date=_RECENT_DATE),
        ]
        self.onion = _make_onion(rows)
        self.register = pd.concat([
            _make_register("HIGH_CONF"),
            _make_register("LOW_CONF"),
        ]).reset_index(drop=True)
        self.metrics = pd.concat([
            _make_metrics("HIGH_CONF"),
            _make_metrics("LOW_CONF"),
        ]).reset_index(drop=True)
        self.scores, _ = build_onion_scores(self.onion, self.metrics, self.register)

    def test_high_confidence_scores_higher(self):
        hc = self.scores[self.scores["family_key"] == "HIGH_CONF"].iloc[0]
        lc = self.scores[self.scores["family_key"] == "LOW_CONF"].iloc[0]
        assert hc["total_onion_score"] > lc["total_onion_score"]

    def test_high_confidence_ranks_first(self):
        hc = self.scores[self.scores["family_key"] == "HIGH_CONF"].iloc[0]
        lc = self.scores[self.scores["family_key"] == "LOW_CONF"].iloc[0]
        assert hc["action_priority_rank"] < lc["action_priority_rank"]

    def test_normalized_scores_differ(self):
        hc = self.scores[self.scores["family_key"] == "HIGH_CONF"].iloc[0]
        lc = self.scores[self.scores["family_key"] == "LOW_CONF"].iloc[0]
        assert hc["normalized_score_100"] > lc["normalized_score_100"]


# =============================================================================
# Test 4 — Old stale issue vs recent issue → recent scores higher
# =============================================================================

class TestRecencyEffect:
    """Test 4 — Old stale issue vs recent issue → recent issue scores higher."""

    def setup_method(self):
        rows = [
            _layer_row("RECENT", "L5_MOEX_ARBITRATION_DELAY",
                       severity_raw="HIGH", confidence_raw=85,
                       pressure_index=30, evidence_count=2,
                       latest_trigger_date=_PORTFOLIO_DATE),  # today → 0 days → recency 1.20
            _layer_row("STALE", "L5_MOEX_ARBITRATION_DELAY",
                       severity_raw="HIGH", confidence_raw=85,
                       pressure_index=30, evidence_count=2,
                       latest_trigger_date=_OLD_DATE),         # 208 days ago → recency 0.60
        ]
        self.onion = _make_onion(rows)
        self.register = pd.concat([
            _make_register("RECENT"),
            _make_register("STALE"),
        ]).reset_index(drop=True)
        self.metrics = pd.concat([
            _make_metrics("RECENT", pressure_index=30),
            _make_metrics("STALE",  pressure_index=30),
        ]).reset_index(drop=True)
        self.scores, _ = build_onion_scores(self.onion, self.metrics, self.register)

    def test_recent_scores_higher(self):
        recent = self.scores[self.scores["family_key"] == "RECENT"].iloc[0]
        stale  = self.scores[self.scores["family_key"] == "STALE"].iloc[0]
        assert recent["total_onion_score"] > stale["total_onion_score"]

    def test_recency_ratio(self):
        # recency 1.20 vs 0.60 → ratio should be exactly 2.0
        recent = self.scores[self.scores["family_key"] == "RECENT"].iloc[0]
        stale  = self.scores[self.scores["family_key"] == "STALE"].iloc[0]
        ratio = recent["total_onion_score"] / stale["total_onion_score"]
        assert ratio == pytest.approx(2.0, rel=1e-6)


# =============================================================================
# Test 5 — Multi-layer chain: total score = sum of components
# =============================================================================

class TestMultiLayerSum:
    """Test 5 — Multi-layer chain total score = sum of layer scores."""

    def setup_method(self):
        self.rows = [
            _layer_row("MULTI", "L1_CONTRACTOR_QUALITY",
                       severity_raw="LOW", confidence_raw=90, pressure_index=20,
                       evidence_count=2, latest_trigger_date=_RECENT_DATE),
            _layer_row("MULTI", "L3_PRIMARY_CONSULTANT_DELAY",
                       severity_raw="HIGH", confidence_raw=72, pressure_index=20,
                       evidence_count=3, latest_trigger_date=_RECENT_DATE),
            _layer_row("MULTI", "L5_MOEX_ARBITRATION_DELAY",
                       severity_raw="MEDIUM", confidence_raw=85, pressure_index=20,
                       evidence_count=1, latest_trigger_date=_RECENT_DATE),
        ]
        self.onion    = _make_onion(self.rows)
        self.register = _make_register("MULTI")
        self.metrics  = _make_metrics("MULTI", pressure_index=20)
        self.scores, _ = build_onion_scores(self.onion, self.metrics, self.register)

    def test_single_row_for_family(self):
        assert len(self.scores[self.scores["family_key"] == "MULTI"]) == 1

    def test_evidence_layers_count_is_3(self):
        row = self.scores[self.scores["family_key"] == "MULTI"].iloc[0]
        assert row["evidence_layers_count"] == 3

    def test_total_score_sums_layers(self):
        from chain_onion.onion_scoring import _recency_factor, _SEV_WEIGHT
        from datetime import date as dt_date

        data_date = dt_date(2026, 4, 27)
        expected_total = 0.0
        for lr in self.rows:
            sw   = _SEV_WEIGHT[lr["severity_raw"]]
            cf   = lr["confidence_raw"] / 100.0
            pf   = 0.60 + lr["pressure_index"] / 100.0
            ef   = min(1.40, 1.0 + min(lr["evidence_count"], 5) * 0.08)
            rf   = _recency_factor(lr["latest_trigger_date"], data_date)
            expected_total += sw * cf * pf * ef * rf

        actual = self.scores[self.scores["family_key"] == "MULTI"].iloc[0]["total_onion_score"]
        assert actual == pytest.approx(expected_total, rel=1e-6)

    def test_top_layer_is_highest_scorer(self):
        row = self.scores[self.scores["family_key"] == "MULTI"].iloc[0]
        # L3 HIGH should beat L1 LOW and L5 MEDIUM in this config
        assert row["top_layer_code"] == "L3_PRIMARY_CONSULTANT_DELAY"


# =============================================================================
# Test 6 — Theme bucketing: each layer maps to correct theme column
# =============================================================================

class TestThemeBucketing:
    """Test 6 — L1→contractor, L2→sas, L3→primary, L4→secondary, L5→moex, L6→contradiction."""

    def setup_method(self):
        rows = [
            _layer_row("FAM", "L1_CONTRACTOR_QUALITY",         severity_raw="LOW",    latest_trigger_date=_RECENT_DATE),
            _layer_row("FAM", "L2_SAS_GATE_FRICTION",          severity_raw="LOW",    latest_trigger_date=_RECENT_DATE),
            _layer_row("FAM", "L3_PRIMARY_CONSULTANT_DELAY",   severity_raw="MEDIUM", latest_trigger_date=_RECENT_DATE),
            _layer_row("FAM", "L4_SECONDARY_CONSULTANT_DELAY", severity_raw="MEDIUM", latest_trigger_date=_RECENT_DATE),
            _layer_row("FAM", "L5_MOEX_ARBITRATION_DELAY",     severity_raw="HIGH",   latest_trigger_date=_RECENT_DATE),
            _layer_row("FAM", "L6_DATA_REPORT_CONTRADICTION",  severity_raw="HIGH",   latest_trigger_date=_RECENT_DATE),
        ]
        self.onion    = _make_onion(rows)
        self.register = _make_register("FAM")
        self.metrics  = _make_metrics("FAM")
        self.row = build_onion_scores(self.onion, self.metrics, self.register)[0].iloc[0]

    def test_contractor_bucket_positive(self):
        assert self.row["contractor_impact_score"] > 0

    def test_sas_bucket_positive(self):
        assert self.row["sas_impact_score"] > 0

    def test_primary_bucket_positive(self):
        assert self.row["consultant_primary_impact_score"] > 0

    def test_secondary_bucket_positive(self):
        assert self.row["consultant_secondary_impact_score"] > 0

    def test_moex_bucket_positive(self):
        assert self.row["moex_impact_score"] > 0

    def test_contradiction_bucket_positive(self):
        assert self.row["contradiction_impact_score"] > 0

    def test_total_equals_sum_of_buckets(self):
        bucket_sum = (
            self.row["contractor_impact_score"]
            + self.row["sas_impact_score"]
            + self.row["consultant_primary_impact_score"]
            + self.row["consultant_secondary_impact_score"]
            + self.row["moex_impact_score"]
            + self.row["contradiction_impact_score"]
        )
        assert self.row["total_onion_score"] == pytest.approx(bucket_sum, rel=1e-6)

    def test_evidence_layers_count_is_6(self):
        assert self.row["evidence_layers_count"] == 6


# =============================================================================
# Test 7 — Ranking stable: dense ranks deterministic, LIVE before LEGACY
# =============================================================================

class TestRankingStable:
    """Test 7 — Dense ranks are deterministic and LIVE_OPERATIONAL ranks before LEGACY_BACKLOG."""

    def setup_method(self):
        rows = [
            # LIVE chain with HIGH severity
            _layer_row("LIVE_A", "L3_PRIMARY_CONSULTANT_DELAY",
                       severity_raw="HIGH", confidence_raw=90, pressure_index=50,
                       latest_trigger_date=_RECENT_DATE,
                       portfolio_bucket="LIVE_OPERATIONAL"),
            # LEGACY chain with same HIGH severity
            _layer_row("LEGACY_B", "L3_PRIMARY_CONSULTANT_DELAY",
                       severity_raw="HIGH", confidence_raw=90, pressure_index=50,
                       latest_trigger_date=_RECENT_DATE,
                       portfolio_bucket="LEGACY_BACKLOG"),
            # LIVE chain with LOW severity
            _layer_row("LIVE_C", "L2_SAS_GATE_FRICTION",
                       severity_raw="LOW", confidence_raw=90, pressure_index=50,
                       latest_trigger_date=_RECENT_DATE,
                       portfolio_bucket="LIVE_OPERATIONAL"),
        ]
        self.onion = _make_onion(rows)
        self.register = pd.concat([
            _make_register("LIVE_A",  portfolio_bucket="LIVE_OPERATIONAL"),
            _make_register("LEGACY_B", portfolio_bucket="LEGACY_BACKLOG"),
            _make_register("LIVE_C",  portfolio_bucket="LIVE_OPERATIONAL"),
        ]).reset_index(drop=True)
        self.metrics = pd.concat([
            _make_metrics("LIVE_A",   portfolio_bucket="LIVE_OPERATIONAL", pressure_index=50),
            _make_metrics("LEGACY_B", portfolio_bucket="LEGACY_BACKLOG",   pressure_index=50),
            _make_metrics("LIVE_C",   portfolio_bucket="LIVE_OPERATIONAL", pressure_index=50),
        ]).reset_index(drop=True)
        self.scores, _ = build_onion_scores(self.onion, self.metrics, self.register)

    def _rank(self, fk: str) -> int:
        return int(self.scores[self.scores["family_key"] == fk].iloc[0]["action_priority_rank"])

    def test_ranks_are_positive(self):
        for fk in ["LIVE_A", "LEGACY_B", "LIVE_C"]:
            assert self._rank(fk) >= 1

    def test_live_high_ranks_before_legacy_high(self):
        # LIVE_A and LEGACY_B have same score, but LIVE_A should rank better
        assert self._rank("LIVE_A") < self._rank("LEGACY_B")

    def test_high_severity_ranks_before_low(self):
        # LIVE_A (HIGH) should rank before LIVE_C (LOW) — higher score wins
        assert self._rank("LIVE_A") < self._rank("LIVE_C")

    def test_ranks_are_dense(self):
        ranks = sorted(self.scores["action_priority_rank"].unique())
        # Dense means no gaps: [1, 2, 3] not [1, 3, 5]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_deterministic_on_repeat_call(self):
        scores2, _ = build_onion_scores(self.onion, self.metrics, self.register)
        pd.testing.assert_frame_equal(
            self.scores[["family_key", "action_priority_rank"]].sort_values("family_key"),
            scores2[["family_key", "action_priority_rank"]].sort_values("family_key"),
        )


# =============================================================================
# Test 8 — Bounds: normalized_score_100 in [0, 100]
# =============================================================================

class TestBounds:
    """Test 8 — normalized_score_100 always in [0, 100], blended_confidence in [0, 100]."""

    def setup_method(self):
        rows = [
            _layer_row("A", "L1_CONTRACTOR_QUALITY",  severity_raw="CRITICAL", confidence_raw=100, pressure_index=100, evidence_count=10, latest_trigger_date=_PORTFOLIO_DATE),
            _layer_row("B", "L2_SAS_GATE_FRICTION",   severity_raw="HIGH",     confidence_raw=72,  pressure_index=50,  evidence_count=3,  latest_trigger_date=_RECENT_DATE),
            _layer_row("C", "L5_MOEX_ARBITRATION_DELAY", severity_raw="LOW",   confidence_raw=10,  pressure_index=0,   evidence_count=1,  latest_trigger_date=_OLD_DATE),
            # Zero-score family (not in onion but in register)
        ]
        register = pd.concat([
            _make_register("A"),
            _make_register("B"),
            _make_register("C"),
            _make_register("D"),  # no onion rows → zero score
        ]).reset_index(drop=True)
        metrics = pd.concat([
            _make_metrics("A", pressure_index=100),
            _make_metrics("B", pressure_index=50),
            _make_metrics("C", pressure_index=0),
            _make_metrics("D", pressure_index=0),
        ]).reset_index(drop=True)
        onion = _make_onion(rows)
        self.scores, self.summary = build_onion_scores(onion, metrics, register)

    def test_normalized_in_0_100(self):
        ns = self.scores["normalized_score_100"]
        assert (ns >= 0).all(), "Some normalized scores < 0"
        assert (ns <= 100).all(), "Some normalized scores > 100"

    def test_blended_confidence_in_0_100(self):
        bc = self.scores["blended_confidence"]
        assert (bc >= 0).all()
        assert (bc <= 100).all()

    def test_zero_score_family_present(self):
        d_row = self.scores[self.scores["family_key"] == "D"]
        assert len(d_row) == 1
        assert d_row.iloc[0]["total_onion_score"] == 0.0
        assert d_row.iloc[0]["normalized_score_100"] == 0.0

    def test_max_normalized_is_100(self):
        assert self.scores["normalized_score_100"].max() == pytest.approx(100.0)

    def test_portfolio_max_score_100(self):
        assert self.summary["max_score"] == pytest.approx(100.0)

    def test_total_scored_chains_is_4(self):
        assert self.summary["total_scored_chains"] == 4

    def test_top_10_at_most_10(self):
        assert len(self.summary["top_10_family_keys"]) <= 10

    def test_escalated_count_non_negative(self):
        assert self.summary["escalated_chain_count"] >= 0

    def test_evidence_layers_count_non_negative(self):
        assert (self.scores["evidence_layers_count"] >= 0).all()


# =============================================================================
# Test 9 — Live full run (Claude Code / Codex only)
# =============================================================================

@pytest.mark.skip(reason="Live full run — Claude Code / Codex only. Run: pytest -k TestLiveRun -s")
class TestLiveRun:
    """Test 9 — Live full dataset run. Execute manually with real chain outputs."""

    def test_live_run(self):
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root / "src"))

        from chain_onion.source_loader import load_chain_sources
        from chain_onion.family_grouper import build_chain_versions, build_chain_register
        from chain_onion.chain_builder import build_chain_events
        from chain_onion.chain_classifier import classify_chains
        from chain_onion.chain_metrics import build_chain_metrics
        from chain_onion.onion_engine import build_onion_layers
        from chain_onion.onion_scoring import build_onion_scores

        sources = load_chain_sources()
        ops_df   = sources["ops_df"]
        debug_df = sources["debug_df"]
        effective_df = sources["effective_df"]

        chain_versions_df  = build_chain_versions(ops_df)
        chain_register_df  = build_chain_register(ops_df, chain_versions_df, debug_df, effective_df)
        chain_events_df    = build_chain_events(ops_df, debug_df, effective_df)
        chain_register_df  = classify_chains(chain_register_df, chain_versions_df, chain_events_df, ops_df)
        chain_metrics_df, portfolio_metrics = build_chain_metrics(
            chain_register_df, chain_versions_df, chain_events_df, ops_df
        )
        onion_layers_df = build_onion_layers(
            chain_register_df, chain_events_df, chain_metrics_df
        )
        onion_scores_df, onion_portfolio_summary = build_onion_scores(
            onion_layers_df, chain_metrics_df, chain_register_df
        )

        print("\n=== STEP 10 LIVE RUN ===")
        print(f"Total scored chains : {onion_portfolio_summary['total_scored_chains']}")
        print(f"Avg normalized score: {onion_portfolio_summary['avg_score']:.2f}")
        print(f"P90 score           : {onion_portfolio_summary['p90_score']:.2f}")
        print(f"Max score           : {onion_portfolio_summary['max_score']:.2f}")
        print(f"Live avg score      : {onion_portfolio_summary['live_avg_score']:.2f}")
        print(f"Legacy avg score    : {onion_portfolio_summary['legacy_avg_score']:.2f}")
        print(f"Escalated chains    : {onion_portfolio_summary['escalated_chain_count']}")
        print(f"Top theme by impact : {onion_portfolio_summary['top_theme_by_impact']}")
        print(f"\nTop 20 chains by score:")
        top20 = onion_scores_df.nlargest(20, "normalized_score_100")[
            ["family_key", "normalized_score_100", "action_priority_rank",
             "top_layer_code", "escalation_flag", "portfolio_bucket"]
        ]
        print(top20.to_string())

        # Histogram bins
        bins = [0, 10, 25, 50, 75, 90, 100]
        scores = onion_scores_df["normalized_score_100"]
        print("\nScore histogram:")
        for lo, hi in zip(bins[:-1], bins[1:]):
            count = ((scores >= lo) & (scores < hi)).sum()
            print(f"  [{lo:3d}, {hi:3d}) : {count}")

        # Assertions
        assert len(onion_scores_df) > 0
        assert (onion_scores_df["normalized_score_100"] >= 0).all()
        assert (onion_scores_df["normalized_score_100"] <= 100).all()
        assert all(col in onion_scores_df.columns for col in _OUTPUT_COLS)
