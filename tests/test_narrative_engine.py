"""
tests/test_narrative_engine.py
---------------------------------
Step 11 — Narrative Engine unit tests.

Tests 1–7: synthetic, fast, run in CI.
Test 8: live full-run — SKIPPED (Claude Code / Codex only).

Test plan:
    1  Archived zero-score chain         → no action required wording
    2  Live critical consultant chain    → CRITICAL urgency, consultant wording
    3  Legacy stale chain (>180 days)    → administrative cleanup wording
    4  Multi-layer chain                 → primary + secondary driver populated
    5  No onion rows chain               → safe neutral wording
    6  Forbidden vocabulary scan         → no banned words in any text column
    7  Deterministic repeat run          → same input produces same output
    8  Live full run (Claude Code only)  → SKIPPED
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

# ── Ensure src/ is importable ────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from chain_onion.narrative_engine import (  # noqa: E402
    build_chain_narratives,
    _urgency_label,
    _confidence_label,
    _executive_summary,
    _primary_driver_text,
    _secondary_driver_text,
    _operational_note,
    _recommended_focus,
    _FORBIDDEN,
    _OUTPUT_COLS,
)


# =============================================================================
# Helpers
# =============================================================================

def _make_register(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "family_key": "X",
        "numero": "X",
        "current_state": "UNKNOWN_CHAIN_STATE",
        "portfolio_bucket": "ARCHIVED_HISTORICAL",
        "stale_days": None,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def _make_scores(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "family_key": "X",
        "numero": "X",
        "current_state": "UNKNOWN_CHAIN_STATE",
        "portfolio_bucket": "ARCHIVED_HISTORICAL",
        "normalized_score_100": 0.0,
        "blended_confidence": 0.0,
        "action_priority_rank": 1,
        "top_layer_code": None,
        "top_layer_name": None,
        "top_layer_score": 0.0,
        "engine_version": "1.0.0",
        "generated_at": "2026-04-27T00:00:00+00:00",
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def _make_layers(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "family_key": "X",
        "layer_code": "L1_CONTRACTOR_QUALITY",
        "severity_raw": "LOW",
        "confidence_raw": 70,
        "evidence_count": 1,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def _empty_layers() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "family_key", "layer_code", "severity_raw", "confidence_raw", "evidence_count"
    ])


def _empty_metrics() -> pd.DataFrame:
    return pd.DataFrame(columns=["family_key"])


# =============================================================================
# Test 1 — Archived zero-score chain
# =============================================================================

class TestArchivedZeroScore:
    """Archived chain with score=0 must produce 'no action required' wording."""

    def setup_method(self):
        self.register = _make_register([{
            "family_key": "ARC001", "numero": "111000",
            "current_state": "CLOSED_VAO",
            "portfolio_bucket": "ARCHIVED_HISTORICAL",
        }])
        self.scores = _make_scores([{
            "family_key": "ARC001", "numero": "111000",
            "current_state": "CLOSED_VAO",
            "portfolio_bucket": "ARCHIVED_HISTORICAL",
            "normalized_score_100": 0.0,
            "blended_confidence": 0.0,
        }])
        self.result = build_chain_narratives(
            self.register, _empty_metrics(), _empty_layers(), self.scores
        )
        self.row = self.result[self.result["family_key"] == "ARC001"].iloc[0]

    def test_one_row(self):
        assert len(self.result) == 1

    def test_urgency_none(self):
        assert self.row["urgency_label"] == "NONE"

    def test_confidence_none(self):
        assert self.row["confidence_label"] == "NONE"

    def test_summary_contains_historical(self):
        assert "Historical" in self.row["executive_summary"]

    def test_no_action_required(self):
        assert "no" in self.row["recommended_focus"].lower()
        assert "action" in self.row["recommended_focus"].lower()

    def test_no_primary_driver(self):
        assert self.row["primary_driver_text"] == "No significant active friction signals detected."

    def test_required_columns_present(self):
        for col in _OUTPUT_COLS:
            assert col in self.result.columns, f"Missing column: {col}"


# =============================================================================
# Test 2 — Live critical consultant chain
# =============================================================================

class TestLiveCriticalConsultant:
    """Live chain with CRITICAL consultant layer must produce CRITICAL urgency and consultant wording."""

    def setup_method(self):
        self.register = _make_register([{
            "family_key": "LIVE001", "numero": "248000",
            "current_state": "OPEN_WAITING_PRIMARY_CONSULTANT",
            "portfolio_bucket": "LIVE_OPERATIONAL",
            "stale_days": 5,
        }])
        self.scores = _make_scores([{
            "family_key": "LIVE001", "numero": "248000",
            "current_state": "OPEN_WAITING_PRIMARY_CONSULTANT",
            "portfolio_bucket": "LIVE_OPERATIONAL",
            "normalized_score_100": 88.0,
            "blended_confidence": 87.0,
            "action_priority_rank": 1,
            "top_layer_code": "L3_PRIMARY_CONSULTANT_DELAY",
        }])
        self.layers = _make_layers([{
            "family_key": "LIVE001",
            "layer_code": "L3_PRIMARY_CONSULTANT_DELAY",
            "severity_raw": "CRITICAL",
            "confidence_raw": 90,
            "evidence_count": 3,
        }])
        self.result = build_chain_narratives(
            self.register, _empty_metrics(), self.layers, self.scores
        )
        self.row = self.result[self.result["family_key"] == "LIVE001"].iloc[0]

    def test_urgency_critical(self):
        assert self.row["urgency_label"] == "CRITICAL"

    def test_confidence_high(self):
        assert self.row["confidence_label"] == "HIGH"

    def test_primary_driver_consultant(self):
        assert "consultant" in self.row["primary_driver_text"].lower()

    def test_summary_elevated(self):
        assert "elevated" in self.row["executive_summary"].lower()

    def test_operational_note_primary(self):
        assert "primary consultant" in self.row["operational_note"].lower()

    def test_recommended_unblocking(self):
        assert "unblocking" in self.row["recommended_focus"].lower()

    def test_action_rank_populated(self):
        assert self.row["action_priority_rank"] == 1


# =============================================================================
# Test 3 — Legacy stale chain (>180 days)
# =============================================================================

class TestLegacyStaleChain:
    """Legacy chain stale >180 days must produce administrative cleanup wording."""

    def setup_method(self):
        self.register = _make_register([{
            "family_key": "LEG001", "numero": "312500",
            "current_state": "OPEN_WAITING_PRIMARY_CONSULTANT",
            "portfolio_bucket": "LEGACY_BACKLOG",
            "stale_days": 250,
        }])
        self.scores = _make_scores([{
            "family_key": "LEG001", "numero": "312500",
            "current_state": "OPEN_WAITING_PRIMARY_CONSULTANT",
            "portfolio_bucket": "LEGACY_BACKLOG",
            "normalized_score_100": 15.0,
            "blended_confidence": 55.0,
        }])
        self.result = build_chain_narratives(
            self.register, _empty_metrics(), _empty_layers(), self.scores
        )
        self.row = self.result[self.result["family_key"] == "LEG001"].iloc[0]

    def test_summary_legacy(self):
        assert "Legacy" in self.row["executive_summary"]

    def test_operational_note_administrative(self):
        assert "administrative" in self.row["operational_note"].lower()

    def test_focus_closure(self):
        assert "closure" in self.row["recommended_focus"].lower() or \
               "archive" in self.row["recommended_focus"].lower()

    def test_urgency_low(self):
        assert self.row["urgency_label"] == "LOW"


# =============================================================================
# Test 4 — Multi-layer chain (primary + secondary driver)
# =============================================================================

class TestMultiLayerChain:
    """Chain with L3 (CRITICAL) + L2 (HIGH) must populate both primary and secondary driver texts."""

    def setup_method(self):
        self.register = _make_register([{
            "family_key": "MULTI001", "numero": "99999",
            "current_state": "OPEN_WAITING_MIXED_CONSULTANTS",
            "portfolio_bucket": "LIVE_OPERATIONAL",
        }])
        self.scores = _make_scores([{
            "family_key": "MULTI001", "numero": "99999",
            "current_state": "OPEN_WAITING_MIXED_CONSULTANTS",
            "portfolio_bucket": "LIVE_OPERATIONAL",
            "normalized_score_100": 75.0,
            "blended_confidence": 80.0,
            "top_layer_code": "L3_PRIMARY_CONSULTANT_DELAY",
        }])
        self.layers = _make_layers([
            {
                "family_key": "MULTI001",
                "layer_code": "L3_PRIMARY_CONSULTANT_DELAY",
                "severity_raw": "CRITICAL",
                "confidence_raw": 90,
                "evidence_count": 4,
            },
            {
                "family_key": "MULTI001",
                "layer_code": "L2_SAS_GATE_FRICTION",
                "severity_raw": "HIGH",
                "confidence_raw": 85,
                "evidence_count": 2,
            },
        ])
        self.result = build_chain_narratives(
            self.register, _empty_metrics(), self.layers, self.scores
        )
        self.row = self.result[self.result["family_key"] == "MULTI001"].iloc[0]

    def test_primary_driver_is_consultant(self):
        assert "consultant" in self.row["primary_driver_text"].lower()

    def test_secondary_driver_is_sas(self):
        assert "SAS" in self.row["secondary_driver_text"]

    def test_primary_and_secondary_differ(self):
        assert self.row["primary_driver_text"] != self.row["secondary_driver_text"]

    def test_urgency_high(self):
        assert self.row["urgency_label"] in ("HIGH", "CRITICAL")

    def test_confidence_medium_or_high(self):
        assert self.row["confidence_label"] in ("MEDIUM", "HIGH")


# =============================================================================
# Test 5 — No onion rows
# =============================================================================

class TestNoOnionRows:
    """Chain with no onion layer activity must produce safe neutral wording."""

    def setup_method(self):
        self.register = _make_register([{
            "family_key": "CLEAN001", "numero": "500001",
            "current_state": "OPEN_WAITING_MOEX",
            "portfolio_bucket": "LIVE_OPERATIONAL",
        }])
        self.scores = _make_scores([{
            "family_key": "CLEAN001", "numero": "500001",
            "current_state": "OPEN_WAITING_MOEX",
            "portfolio_bucket": "LIVE_OPERATIONAL",
            "normalized_score_100": 0.0,
            "blended_confidence": 0.0,
            "top_layer_code": None,
        }])
        self.result = build_chain_narratives(
            self.register, _empty_metrics(), _empty_layers(), self.scores
        )
        self.row = self.result[self.result["family_key"] == "CLEAN001"].iloc[0]

    def test_primary_driver_is_none_text(self):
        assert self.row["primary_driver_text"] == "No significant active friction signals detected."

    def test_secondary_driver_is_none_text(self):
        assert self.row["secondary_driver_text"] == "No secondary material driver identified."

    def test_confidence_none(self):
        assert self.row["confidence_label"] == "NONE"

    def test_urgency_none(self):
        assert self.row["urgency_label"] == "NONE"


# =============================================================================
# Test 6 — Forbidden vocabulary scan
# =============================================================================

class TestForbiddenVocabulary:
    """No banned words must appear in any text output column."""

    def setup_method(self):
        register = _make_register([
            {"family_key": f"F{i}", "numero": str(i),
             "current_state": state, "portfolio_bucket": bucket}
            for i, (state, bucket) in enumerate([
                ("CLOSED_VAO",                    "ARCHIVED_HISTORICAL"),
                ("OPEN_WAITING_PRIMARY_CONSULTANT","LIVE_OPERATIONAL"),
                ("CHRONIC_REF_CHAIN",              "LIVE_OPERATIONAL"),
                ("LEGACY_BACKLOG",                 "LEGACY_BACKLOG"),
                ("WAITING_CORRECTED_INDICE",       "LIVE_OPERATIONAL"),
                ("OPEN_WAITING_MOEX",              "LIVE_OPERATIONAL"),
            ])
        ])
        scores = _make_scores([
            {"family_key": f"F{i}", "normalized_score_100": s, "blended_confidence": 70.0}
            for i, s in enumerate([0, 92, 55, 10, 75, 40])
        ])
        self.result = build_chain_narratives(
            register, _empty_metrics(), _empty_layers(), scores
        )

    TEXT_COLS = [
        "executive_summary", "primary_driver_text", "secondary_driver_text",
        "operational_note", "recommended_focus",
    ]

    def test_no_forbidden_words(self):
        for col in self.TEXT_COLS:
            for word in _FORBIDDEN:
                hits = self.result[col].str.contains(word, case=False, na=False)
                assert not hits.any(), (
                    f"Forbidden word '{word}' found in column '{col}': "
                    f"{self.result.loc[hits, col].tolist()}"
                )

    def test_no_null_text(self):
        for col in self.TEXT_COLS:
            nulls = self.result[col].isna().sum()
            assert nulls == 0, f"Null text in column '{col}': {nulls} rows"


# =============================================================================
# Test 7 — Deterministic repeat run
# =============================================================================

class TestDeterministicRepeat:
    """Same inputs must produce identical text outputs across two calls."""

    def setup_method(self):
        register = _make_register([{
            "family_key": "DET001", "numero": "777001",
            "current_state": "OPEN_WAITING_PRIMARY_CONSULTANT",
            "portfolio_bucket": "LIVE_OPERATIONAL",
            "stale_days": 30,
        }])
        scores = _make_scores([{
            "family_key": "DET001", "numero": "777001",
            "current_state": "OPEN_WAITING_PRIMARY_CONSULTANT",
            "portfolio_bucket": "LIVE_OPERATIONAL",
            "normalized_score_100": 65.0,
            "blended_confidence": 78.0,
            "top_layer_code": "L3_PRIMARY_CONSULTANT_DELAY",
        }])
        layers = _make_layers([{
            "family_key": "DET001",
            "layer_code": "L3_PRIMARY_CONSULTANT_DELAY",
            "severity_raw": "HIGH",
            "confidence_raw": 80,
            "evidence_count": 2,
        }])
        self.r1 = build_chain_narratives(register, _empty_metrics(), layers, scores)
        self.r2 = build_chain_narratives(register, _empty_metrics(), layers, scores)

    TEXT_COLS = [
        "executive_summary", "primary_driver_text", "secondary_driver_text",
        "operational_note", "recommended_focus", "urgency_label", "confidence_label",
    ]

    def test_text_columns_identical(self):
        for col in self.TEXT_COLS:
            assert self.r1[col].tolist() == self.r2[col].tolist(), \
                f"Non-deterministic output in column '{col}'"

    def test_scores_identical(self):
        assert self.r1["normalized_score_100"].tolist() == self.r2["normalized_score_100"].tolist()
        assert self.r1["urgency_label"].tolist() == self.r2["urgency_label"].tolist()


# =============================================================================
# Test 8 — Live full run (Claude Code / Codex only)
# =============================================================================

@pytest.mark.skip(reason="Live full-run — Claude Code / Codex only (32k ops rows)")
class TestLiveRun:
    def test_live_run(self):
        """
        Full portfolio narrative generation on live dataset.

        Expected output format:
            - Total narratives generated
            - Top 20 narratives by action_priority_rank
            - Urgency distribution (CRITICAL/HIGH/MEDIUM/LOW/NONE counts)
            - Confidence distribution (HIGH/MEDIUM/LOW/NONE counts)
        """
        from chain_onion.source_loader import load_chain_sources
        from chain_onion.chain_builder import build_chain_versions, build_chain_events
        from chain_onion.chain_classifier import classify_chains
        from chain_onion.chain_metrics import build_chain_metrics
        from chain_onion.onion_engine import build_onion_layers
        from chain_onion.onion_scoring import build_onion_scores
        from chain_onion.narrative_engine import build_chain_narratives

        sources = load_chain_sources()
        ops_df = sources["ops_df"]
        debug_df = sources["debug_df"]
        effective_df = sources["effective_df"]

        chain_versions_df = build_chain_versions(ops_df)
        chain_register_df = build_chain_events(ops_df, chain_versions_df, debug_df, effective_df)
        chain_events_df = build_chain_events(ops_df, debug_df, effective_df)
        chain_register_df = classify_chains(chain_register_df, chain_versions_df, chain_events_df, ops_df)
        chain_metrics_df, portfolio_metrics = build_chain_metrics(
            chain_register_df, chain_versions_df, chain_events_df, ops_df
        )
        onion_layers_df = build_onion_layers(chain_register_df, chain_events_df, chain_metrics_df)
        onion_scores_df, onion_portfolio_summary = build_onion_scores(
            onion_layers_df, chain_metrics_df, chain_register_df
        )

        narratives_df = build_chain_narratives(
            chain_register_df, chain_metrics_df, onion_layers_df, onion_scores_df
        )

        print(f"\nTotal narratives: {len(narratives_df)}")
        print("\nUrgency distribution:")
        print(narratives_df["urgency_label"].value_counts().to_string())
        print("\nConfidence distribution:")
        print(narratives_df["confidence_label"].value_counts().to_string())
        print("\nTop 20 by action_priority_rank:")
        top20 = narratives_df.sort_values("action_priority_rank").head(20)
        for _, r in top20.iterrows():
            print(
                f"  rank={r['action_priority_rank']:>4} | "
                f"fk={r['family_key']:<12} | "
                f"urgency={r['urgency_label']:<8} | "
                f"score={r['normalized_score_100']:>6.1f} | "
                f"{r['executive_summary']}"
            )

        assert len(narratives_df) > 0
        assert set(narratives_df["urgency_label"].unique()).issubset(
            {"CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"}
        )
        assert set(narratives_df["confidence_label"].unique()).issubset(
            {"HIGH", "MEDIUM", "LOW", "NONE"}
        )
