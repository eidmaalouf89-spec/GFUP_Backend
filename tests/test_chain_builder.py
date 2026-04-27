"""
tests/test_chain_builder.py
----------------------------
Step 06 unit tests for build_chain_events().

Tests
-----
Test 1 — Synthetic chain (A→REF→B→VAO): event_seq ordered correctly.
Test 2 — Mixed sources (ops + debug + effective): events merged correctly.
Test 3 — event_seq uniqueness: 1..N, no gaps, no duplicates per family.
Test 4 — actor_type classification: PRIMARY/SECONDARY/MOEX/SAS/CONTRACTOR.
Test 5 — Exact dedup: duplicate rows collapsed to one.
Test 6 — Live dataset (skipped — Claude Code / Codex only, full 32k run).

Execution model:
  Tests 1-5: pure synthetic data, < 1s total.
  Test 6: marked skip, run directly against live artifacts.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# ── ensure src/ is importable ─────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from chain_onion.chain_builder import (
    SRC_DEBUG,
    SRC_EFFECTIVE,
    SRC_OPS,
    _CHAIN_EVENTS_COLS,
    build_chain_events,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ops_row(**kwargs) -> dict:
    """Return a minimal ops_df row with sensible defaults."""
    defaults = dict(
        family_key="100",
        version_key="100_A",
        numero="100",
        indice="A",
        step_order="1",
        step_type="CONSULTANT",
        actor_clean="EGIS",
        submittal_date="2025-01-10",
        response_date=None,
        is_blocking=True,
        is_completed=False,
        requires_new_cycle=False,
        delay_contribution_days=0,
        status_clean="",
        data_date="2025-09-01",
    )
    defaults.update(kwargs)
    return defaults


def _make_ops(*rows) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _make_debug(**kwargs) -> dict:
    """Return a minimal debug_df row with sensible defaults."""
    defaults = dict(
        family_key="100",
        version_key="100_A",
        instance_key="100_A_inst_001",
        submission_instance_id="inst_001",
        instance_role="ACTIVE",
        instance_resolution_reason="Selected as active instance",
        raw_date="2025-01-10",
        doc_code="100|A",
    )
    defaults.update(kwargs)
    return defaults


def _make_eff(**kwargs) -> dict:
    """Return a minimal effective_df row with sensible defaults."""
    defaults = dict(
        family_key="100",
        version_key="100_A",
        actor_clean="EGIS",
        status_clean="VAO",
        response_date="2025-03-01",
        effective_source="GED+REPORT_STATUS",
    )
    defaults.update(kwargs)
    return defaults


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Synthetic chain A→REF→B→VAO: ordered event_seq
# ─────────────────────────────────────────────────────────────────────────────

class TestSyntheticChain:
    """
    Chain: family 248000
      Version A: OPEN_DOC (2025-01-05) → SAS REF (2025-01-20, requires_new_cycle)
      Version B: OPEN_DOC (2025-02-01) → EGIS VAO (2025-03-01)
    """

    def _build_ops(self):
        return _make_ops(
            _ops_row(
                family_key="248000", version_key="248000_A", indice="A",
                step_order="1", step_type="OPEN_DOC", actor_clean="CONTRACTOR_X",
                submittal_date="2025-01-05", response_date=None,
                is_blocking=False, is_completed=True, requires_new_cycle=False,
                status_clean="",
            ),
            _ops_row(
                family_key="248000", version_key="248000_A", indice="A",
                step_order="2", step_type="SAS", actor_clean="SAS",
                submittal_date="2025-01-05", response_date="2025-01-20",
                is_blocking=False, is_completed=True, requires_new_cycle=True,
                status_clean="REF",
            ),
            _ops_row(
                family_key="248000", version_key="248000_B", indice="B",
                step_order="1", step_type="OPEN_DOC", actor_clean="CONTRACTOR_X",
                submittal_date="2025-02-01", response_date=None,
                is_blocking=False, is_completed=True, requires_new_cycle=False,
                status_clean="",
            ),
            _ops_row(
                family_key="248000", version_key="248000_B", indice="B",
                step_order="2", step_type="CONSULTANT", actor_clean="EGIS",
                submittal_date="2025-02-01", response_date="2025-03-01",
                is_blocking=False, is_completed=True, requires_new_cycle=False,
                status_clean="VAO",
            ),
        )

    def test_event_count(self):
        events = build_chain_events(self._build_ops())
        assert len(events) == 4

    def test_event_seq_is_monotone(self):
        events = build_chain_events(self._build_ops())
        fam = events[events["family_key"] == "248000"].copy()
        assert list(fam["event_seq"]) == [1, 2, 3, 4]

    def test_event_seq_starts_at_one(self):
        events = build_chain_events(self._build_ops())
        assert events["event_seq"].min() == 1

    def test_chronological_order(self):
        """First event (seq=1) date < last event (seq=4) date."""
        events = build_chain_events(self._build_ops())
        fam = events[events["family_key"] == "248000"].copy()
        dates = fam["event_date"].tolist()
        # First OPEN_DOC on 2025-01-05, last EGIS VAO on 2025-03-01
        assert dates[0] < dates[-1]

    def test_submittal_step_is_submittal(self):
        events = build_chain_events(self._build_ops())
        submittal_events = events[events["step_type"] == "SUBMITTAL"]
        assert len(submittal_events) == 2  # one per version

    def test_sas_ref_is_cycle_required(self):
        events = build_chain_events(self._build_ops())
        cycle_events = events[events["step_type"] == "CYCLE_REQUIRED"]
        assert len(cycle_events) == 1
        assert cycle_events.iloc[0]["status"] == "REF"

    def test_egis_vao_is_response(self):
        events = build_chain_events(self._build_ops())
        egis_events = events[
            (events["actor"] == "EGIS") & (events["step_type"] == "RESPONSE")
        ]
        assert len(egis_events) == 1
        assert egis_events.iloc[0]["status"] == "VAO"

    def test_required_columns_present(self):
        events = build_chain_events(self._build_ops())
        for col in _CHAIN_EVENTS_COLS:
            assert col in events.columns, f"Missing column: {col}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Mixed sources: ops + debug + effective
# ─────────────────────────────────────────────────────────────────────────────

class TestMixedSources:
    def _ops(self):
        return _make_ops(
            _ops_row(
                family_key="200", version_key="200_A", step_type="CONSULTANT",
                actor_clean="EGIS", submittal_date="2025-01-10",
                response_date="2025-02-15", is_blocking=False,
                is_completed=True, status_clean="VAO",
            )
        )

    def _debug(self):
        return pd.DataFrame([
            _make_debug(
                family_key="200", version_key="200_A",
                instance_key="200_A_inst_001",
                instance_role="ACTIVE",
                raw_date="2025-01-10",
            )
        ])

    def _effective(self):
        return pd.DataFrame([
            _make_eff(
                family_key="200", version_key="200_A",
                effective_source="GED+REPORT_STATUS",
                response_date="2025-02-15",
            )
        ])

    def test_all_three_sources_present_in_output(self):
        events = build_chain_events(self._ops(), self._debug(), self._effective())
        sources = set(events["source"].unique())
        assert SRC_OPS in sources
        assert SRC_DEBUG in sources
        assert SRC_EFFECTIVE in sources

    def test_ged_only_effective_rows_not_in_output(self):
        eff = pd.DataFrame([_make_eff(family_key="200", version_key="200_A",
                                       effective_source="GED")])
        events = build_chain_events(self._ops(), effective_df=eff)
        assert SRC_EFFECTIVE not in events["source"].values

    def test_debug_event_step_type(self):
        events = build_chain_events(self._ops(), self._debug())
        dbg = events[events["source"] == SRC_DEBUG]
        assert len(dbg) == 1
        assert dbg.iloc[0]["step_type"] == "INSTANCE_CREATED"

    def test_effective_override_step_type(self):
        events = build_chain_events(self._ops(), effective_df=self._effective())
        eff = events[events["source"] == SRC_EFFECTIVE]
        assert len(eff) == 1
        assert eff.iloc[0]["step_type"] == "EFFECTIVE_OVERRIDE"

    def test_merged_events_all_share_family(self):
        events = build_chain_events(self._ops(), self._debug(), self._effective())
        assert (events["family_key"] == "200").all()

    def test_superseded_debug_step_type(self):
        dbg = pd.DataFrame([
            _make_debug(
                family_key="300", version_key="300_A",
                instance_key="300_A_inst_old",
                instance_role="SUPERSEDED",
                raw_date="2025-01-01",
            )
        ])
        ops = _make_ops(_ops_row(family_key="300", version_key="300_A"))
        events = build_chain_events(ops, dbg)
        dbg_events = events[events["source"] == SRC_DEBUG]
        assert dbg_events.iloc[0]["step_type"] == "INSTANCE_SUPERSEDED"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — event_seq uniqueness: 1..N gapless per family
# ─────────────────────────────────────────────────────────────────────────────

class TestEventSeqUniqueness:
    def _two_family_ops(self):
        return _make_ops(
            _ops_row(family_key="A1", version_key="A1_A", step_type="OPEN_DOC",
                     submittal_date="2025-01-01", response_date=None,
                     is_completed=True, is_blocking=False),
            _ops_row(family_key="A1", version_key="A1_A", step_type="CONSULTANT",
                     actor_clean="EGIS", submittal_date="2025-01-01",
                     response_date="2025-02-01", is_completed=True, is_blocking=False,
                     status_clean="VAO"),
            _ops_row(family_key="A1", version_key="A1_A", step_type="MOEX",
                     actor_clean="MOEX", submittal_date="2025-01-01",
                     response_date="2025-03-01", is_completed=True, is_blocking=False,
                     status_clean="VAO"),
            _ops_row(family_key="B2", version_key="B2_A", step_type="OPEN_DOC",
                     submittal_date="2025-01-15", response_date=None,
                     is_completed=True, is_blocking=False),
            _ops_row(family_key="B2", version_key="B2_A", step_type="SAS",
                     actor_clean="SAS", submittal_date="2025-01-15",
                     response_date="2025-01-30", is_completed=True, is_blocking=False,
                     status_clean="VSO"),
        )

    def test_seq_is_gapless_per_family(self):
        events = build_chain_events(self._two_family_ops())
        for fk, grp in events.groupby("family_key"):
            seqs = sorted(grp["event_seq"].tolist())
            expected = list(range(1, len(grp) + 1))
            assert seqs == expected, f"family {fk}: gaps in event_seq"

    def test_seq_no_duplicates_per_family(self):
        events = build_chain_events(self._two_family_ops())
        for fk, grp in events.groupby("family_key"):
            assert grp["event_seq"].nunique() == len(grp), \
                f"family {fk}: duplicate event_seq values"

    def test_each_family_starts_at_one(self):
        events = build_chain_events(self._two_family_ops())
        for fk, grp in events.groupby("family_key"):
            assert grp["event_seq"].min() == 1, f"family {fk}: does not start at 1"

    def test_two_families_independent_seq(self):
        events = build_chain_events(self._two_family_ops())
        a1 = events[events["family_key"] == "A1"]
        b2 = events[events["family_key"] == "B2"]
        assert len(a1) == 3
        assert len(b2) == 2
        assert list(a1["event_seq"]) == [1, 2, 3]
        assert list(b2["event_seq"]) == [1, 2]


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — actor_type classification
# ─────────────────────────────────────────────────────────────────────────────

class TestActorTypeClassification:
    def _make_single(self, step_type, actor_clean):
        return _make_ops(
            _ops_row(
                family_key="999", version_key="999_A",
                step_type=step_type, actor_clean=actor_clean,
                submittal_date="2025-01-01", response_date="2025-01-15",
                is_completed=True, is_blocking=False, status_clean="VAO",
            )
        )

    def test_moex_actor_type(self):
        events = build_chain_events(self._make_single("MOEX", "MOEX"))
        assert events.iloc[0]["actor_type"] == "MOEX"

    def test_sas_actor_type(self):
        events = build_chain_events(self._make_single("SAS", "SAS"))
        assert events.iloc[0]["actor_type"] == "SAS"

    def test_open_doc_is_contractor(self):
        ops = _make_ops(
            _ops_row(
                family_key="999", version_key="999_A",
                step_type="OPEN_DOC", actor_clean="EMETTEUR_X",
                submittal_date="2025-01-01", response_date=None,
                is_completed=True, is_blocking=False,
            )
        )
        events = build_chain_events(ops)
        assert events.iloc[0]["actor_type"] == "CONTRACTOR"

    def test_egis_is_primary_consultant(self):
        events = build_chain_events(self._make_single("CONSULTANT", "EGIS"))
        assert events.iloc[0]["actor_type"] == "PRIMARY_CONSULTANT"

    def test_terrell_is_primary_consultant(self):
        events = build_chain_events(self._make_single("CONSULTANT", "TERRELL STRUCTURES"))
        assert events.iloc[0]["actor_type"] == "PRIMARY_CONSULTANT"

    def test_bet_spk_is_primary_consultant(self):
        events = build_chain_events(self._make_single("CONSULTANT", "BET SPK FLUIDES"))
        assert events.iloc[0]["actor_type"] == "PRIMARY_CONSULTANT"

    def test_unknown_consultant_is_secondary(self):
        events = build_chain_events(self._make_single("CONSULTANT", "Bureau Signalétique"))
        assert events.iloc[0]["actor_type"] == "SECONDARY_CONSULTANT"

    def test_commission_is_secondary(self):
        events = build_chain_events(self._make_single("CONSULTANT", "Commission Voirie"))
        assert events.iloc[0]["actor_type"] == "SECONDARY_CONSULTANT"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Exact dedup
# ─────────────────────────────────────────────────────────────────────────────

class TestDedup:
    def _dup_ops(self):
        """Two identical rows that should collapse to one."""
        base = _ops_row(
            family_key="500", version_key="500_A", step_type="CONSULTANT",
            actor_clean="EGIS", submittal_date="2025-01-10",
            response_date="2025-02-01", is_completed=True, is_blocking=False,
            status_clean="VAO",
        )
        return _make_ops(base, dict(base))  # exact duplicate

    def test_exact_duplicates_removed(self):
        events = build_chain_events(self._dup_ops())
        assert len(events) == 1

    def test_different_status_not_deduped(self):
        row1 = _ops_row(
            family_key="501", version_key="501_A", step_type="CONSULTANT",
            actor_clean="EGIS", response_date="2025-02-01", status_clean="VAO",
            is_completed=True, is_blocking=False,
        )
        row2 = dict(row1)
        row2["status_clean"] = "REF"  # different status → different event
        events = build_chain_events(_make_ops(row1, row2))
        assert len(events) == 2

    def test_different_date_not_deduped(self):
        row1 = _ops_row(
            family_key="502", version_key="502_A", step_type="CONSULTANT",
            actor_clean="EGIS", response_date="2025-02-01", status_clean="VAO",
            is_completed=True, is_blocking=False,
        )
        row2 = dict(row1)
        row2["response_date"] = "2025-03-01"  # different date → different event
        events = build_chain_events(_make_ops(row1, row2))
        assert len(events) == 2

    def test_dedup_across_sources(self):
        """Same family_key/version_key/event_date/actor/step_type from OPS is not
        duplicated by a DEBUG event (different source → different row)."""
        ops = _make_ops(
            _ops_row(family_key="503", version_key="503_A", step_type="CONSULTANT",
                     actor_clean="EGIS", response_date="2025-02-01",
                     status_clean="VAO", is_completed=True, is_blocking=False)
        )
        dbg = pd.DataFrame([
            _make_debug(family_key="503", version_key="503_A",
                        instance_key="503_A_inst_001", raw_date="2025-02-01")
        ])
        events = build_chain_events(ops, dbg)
        # OPS and DEBUG rows differ on 'source' so they are NOT collapsed
        assert len(events) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — Live dataset (skipped in Cowork sandbox)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skip(
    reason="Full 32k / 407k row run — Claude Code / Codex only per HYBRID model"
)
def test_live_dataset_metrics():
    """
    Run against live artifacts. Confirm:
      - total events > 0
      - avg events/family > 1
      - max events/family > 1
      - row counts by source
      - event_seq gapless per family (spot check 50 families)
    """
    import os
    root = Path(__file__).resolve().parent.parent
    flat_ged_path = root / "output" / "intermediate" / "FLAT_GED.xlsx"
    debug_path    = root / "output" / "intermediate" / "DEBUG_TRACE.csv"

    assert flat_ged_path.exists(), f"FLAT_GED not found: {flat_ged_path}"

    from chain_onion.source_loader import load_chain_sources
    sources = load_chain_sources(str(flat_ged_path), str(debug_path))
    ops_df      = sources["ops_df"]
    debug_df    = sources["debug_df"]
    effective_df = sources["effective_df"]

    events = build_chain_events(ops_df, debug_df, effective_df)

    # Basic shape checks
    assert len(events) > 0, "No events produced"
    assert events["family_key"].nunique() > 0

    family_sizes = events.groupby("family_key").size()
    assert family_sizes.mean() > 1.0, "Expected > 1 event per family on average"
    assert family_sizes.max() > 1, "Expected at least one family with > 1 event"

    # Spot-check event_seq gapless for first 50 families
    for fk in list(events["family_key"].unique())[:50]:
        grp = events[events["family_key"] == fk]
        seqs = sorted(grp["event_seq"].tolist())
        expected = list(range(1, len(grp) + 1))
        assert seqs == expected, f"family {fk}: event_seq not gapless"

    # Report
    print("\n=== LIVE DATASET METRICS ===")
    print(f"Total events       : {len(events)}")
    print(f"Unique families    : {events['family_key'].nunique()}")
    print(f"Avg events/family  : {family_sizes.mean():.1f}")
    print(f"Max events/family  : {family_sizes.max()}")
    print(f"NaT dates          : {events['event_date'].isna().sum()}")
    print(f"OPS events         : {(events['source'] == 'OPS').sum()}")
    print(f"EFFECTIVE events   : {(events['source'] == 'EFFECTIVE').sum()}")
    print(f"DEBUG events       : {(events['source'] == 'DEBUG').sum()}")
    print("============================")
