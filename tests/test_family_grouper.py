"""
tests/test_family_grouper.py
-----------------------------
Step 05 — Synthetic unit tests for the Family Grouper Engine.

Tests covered:
  Test 1 — Synthetic grouping math (2 families, multiple indices)
  Test 3 — Key consistency (every chain_versions family_key exists in chain_register)
  Test 4 — latest_indice matches max(version_sort_order) per family
  Test 5 — Primary/secondary flags use repo classifier only
  Test 6 — No duplicate keys in either output

Test 2 (live dataset full run) is marked xfail — requires live FLAT_GED.xlsx
and is intended for Claude Code / Codex execution per the HYBRID execution model.

All tests use in-memory synthetic DataFrames only.
No file I/O. No imports of live artifacts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# ── Add src/ to path so chain_onion imports work ──────────────────────────
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from chain_onion.family_grouper import (
    build_chain_versions,
    build_chain_register,
    _indice_sort_key,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_ops_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal ops_df from a list of row dicts."""
    df = pd.DataFrame(rows)
    # Ensure identity keys
    df["numero"] = df["numero"].astype(str)
    df["indice"] = df["indice"].astype(str)
    df["family_key"] = df["numero"]
    df["version_key"] = df["numero"] + "_" + df["indice"]
    # Default missing bool columns
    for col in ("is_blocking", "is_completed", "requires_new_cycle"):
        if col not in df.columns:
            df[col] = False
    # Ensure bool dtype
    for col in ("is_blocking", "is_completed", "requires_new_cycle"):
        df[col] = df[col].astype(bool)
    # Default missing date columns
    for col in ("submittal_date", "response_date"):
        if col not in df.columns:
            df[col] = pd.NaT
        else:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    # Default actor_clean
    if "actor_clean" not in df.columns:
        df["actor_clean"] = ""
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Synthetic grouping math
# ─────────────────────────────────────────────────────────────────────────────

class TestGroupingMath:
    """
    Two families:
      - Family "100": indices A (3 rows), B (2 rows)
      - Family "200": indices A (1 row), B (1 row), C (1 row)

    Verifies exact row counts, date aggregations, and flag derivations.
    """

    @pytest.fixture
    def ops_df(self):
        return _make_ops_df([
            # Family 100 / A — 3 rows
            {
                "numero": "100", "indice": "A",
                "submittal_date": "2024-01-10", "response_date": "2024-01-20",
                "is_blocking": False, "is_completed": True, "requires_new_cycle": False,
                "actor_clean": "EGIS",
            },
            {
                "numero": "100", "indice": "A",
                "submittal_date": "2024-01-10", "response_date": "2024-01-25",
                "is_blocking": False, "is_completed": True, "requires_new_cycle": False,
                "actor_clean": "BET SPK",
            },
            {
                "numero": "100", "indice": "A",
                "submittal_date": "2024-01-10", "response_date": None,
                "is_blocking": True, "is_completed": False, "requires_new_cycle": True,
                "actor_clean": "Bureau Signalétique",
            },
            # Family 100 / B — 2 rows, no blocking
            {
                "numero": "100", "indice": "B",
                "submittal_date": "2024-03-01", "response_date": "2024-03-15",
                "is_blocking": False, "is_completed": True, "requires_new_cycle": False,
                "actor_clean": "EGIS",
            },
            {
                "numero": "100", "indice": "B",
                "submittal_date": "2024-03-01", "response_date": "2024-03-20",
                "is_blocking": False, "is_completed": True, "requires_new_cycle": False,
                "actor_clean": "TERRELL",
            },
            # Family 200 / A — 1 row
            {
                "numero": "200", "indice": "A",
                "submittal_date": "2024-02-01", "response_date": None,
                "is_blocking": True, "is_completed": False, "requires_new_cycle": False,
                "actor_clean": "Commission Voirie",
            },
            # Family 200 / B — 1 row
            {
                "numero": "200", "indice": "B",
                "submittal_date": "2024-04-01", "response_date": None,
                "is_blocking": True, "is_completed": False, "requires_new_cycle": False,
                "actor_clean": "TERRELL",
            },
            # Family 200 / C — 1 row
            {
                "numero": "200", "indice": "C",
                "submittal_date": "2024-06-01", "response_date": None,
                "is_blocking": True, "is_completed": False, "requires_new_cycle": False,
                "actor_clean": "EGIS",
            },
        ])

    @pytest.fixture
    def chain_versions(self, ops_df):
        return build_chain_versions(ops_df)

    @pytest.fixture
    def chain_register(self, ops_df, chain_versions):
        return build_chain_register(ops_df, chain_versions)

    def test_version_row_counts(self, chain_versions):
        """chain_versions has one row per VERSION_KEY."""
        assert len(chain_versions) == 5, f"Expected 5, got {len(chain_versions)}"
        assert chain_versions["version_key"].nunique() == 5

    def test_version_row_count_ops(self, chain_versions):
        """row_count_ops per version is correct."""
        cv = chain_versions.set_index("version_key")
        assert cv.at["100_A", "row_count_ops"] == 3
        assert cv.at["100_B", "row_count_ops"] == 2
        assert cv.at["200_A", "row_count_ops"] == 1
        assert cv.at["200_B", "row_count_ops"] == 1
        assert cv.at["200_C", "row_count_ops"] == 1

    def test_has_blocking_rows(self, chain_versions):
        """has_blocking_rows is True only for versions with at least one blocking row."""
        cv = chain_versions.set_index("version_key")
        assert cv.at["100_A", "has_blocking_rows"]
        assert not cv.at["100_B", "has_blocking_rows"]
        assert cv.at["200_A", "has_blocking_rows"]
        assert cv.at["200_B", "has_blocking_rows"]
        assert cv.at["200_C", "has_blocking_rows"]

    def test_blocking_actor_count(self, chain_versions):
        """blocking_actor_count is distinct actor_clean where is_blocking."""
        cv = chain_versions.set_index("version_key")
        # 100_A: 1 blocking actor (Bureau Signalétique)
        assert cv.at["100_A", "blocking_actor_count"] == 1
        # 100_B: 0 blocking actors
        assert cv.at["100_B", "blocking_actor_count"] == 0

    def test_requires_new_cycle_flag(self, chain_versions):
        """requires_new_cycle_flag is True iff any row has requires_new_cycle=True."""
        cv = chain_versions.set_index("version_key")
        assert cv.at["100_A", "requires_new_cycle_flag"]
        assert not cv.at["100_B", "requires_new_cycle_flag"]

    def test_completed_row_count(self, chain_versions):
        """completed_row_count counts is_completed=True rows."""
        cv = chain_versions.set_index("version_key")
        assert cv.at["100_A", "completed_row_count"] == 2   # 2 completed, 1 not
        assert cv.at["100_B", "completed_row_count"] == 2   # both completed

    def test_first_latest_submission_date(self, chain_versions):
        """first/latest submission dates are min/max of submittal_date."""
        cv = chain_versions.set_index("version_key")
        assert str(cv.at["100_A", "first_submission_date"])[:10] == "2024-01-10"
        assert str(cv.at["100_A", "latest_submission_date"])[:10] == "2024-01-10"
        assert str(cv.at["100_B", "first_submission_date"])[:10] == "2024-03-01"

    def test_latest_response_date(self, chain_versions):
        """latest_response_date is max non-null response_date."""
        cv = chain_versions.set_index("version_key")
        # 100_A has responses on 2024-01-20 and 2024-01-25; one None
        assert str(cv.at["100_A", "latest_response_date"])[:10] == "2024-01-25"
        # 100_B has 2024-03-15 and 2024-03-20
        assert str(cv.at["100_B", "latest_response_date"])[:10] == "2024-03-20"
        # 200_A has no response dates — should be NaT
        assert pd.isna(cv.at["200_A", "latest_response_date"])

    def test_register_row_counts(self, chain_register):
        """chain_register has one row per family_key."""
        assert len(chain_register) == 2
        assert chain_register["family_key"].nunique() == 2

    def test_register_total_versions(self, chain_register):
        """total_versions is correct per family."""
        cr = chain_register.set_index("family_key")
        assert cr.at["100", "total_versions"] == 2
        assert cr.at["200", "total_versions"] == 3

    def test_register_total_rows_ops(self, chain_register):
        """total_rows_ops is total ops_df rows per family."""
        cr = chain_register.set_index("family_key")
        assert cr.at["100", "total_rows_ops"] == 5
        assert cr.at["200", "total_rows_ops"] == 3

    def test_register_total_blocking_versions(self, chain_register):
        """total_blocking_versions counts versions with has_blocking_rows=True."""
        cr = chain_register.set_index("family_key")
        # Family 100: version A has blocking rows, B does not → 1
        assert cr.at["100", "total_blocking_versions"] == 1
        # Family 200: all 3 versions have blocking rows → 3
        assert cr.at["200", "total_blocking_versions"] == 3

    def test_register_total_versions_requiring_cycle(self, chain_register):
        """total_versions_requiring_cycle counts versions with requires_new_cycle_flag=True."""
        cr = chain_register.set_index("family_key")
        assert cr.at["100", "total_versions_requiring_cycle"] == 1  # only A
        assert cr.at["200", "total_versions_requiring_cycle"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Live dataset full run (xfail — Claude Code / Codex only)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="Live data test (Test 2) — requires full 32k / 407k row run; execute in Claude Code / Codex per HYBRID execution model")
def test_live_dataset_row_counts():
    """
    Live dataset validation.
    Expected: chain_versions rows ≈ unique version_key count in ops_df.
    Expected: chain_register rows ≈ unique family_key count in ops_df.
    This test is marked xfail and must be run outside the Cowork sandbox.
    """
    from chain_onion.source_loader import load_chain_sources

    _FLAT_GED = Path(__file__).resolve().parent.parent / "output/intermediate/FLAT_GED.xlsx"
    _DEBUG    = Path(__file__).resolve().parent.parent / "output/intermediate/DEBUG_TRACE.csv"

    sources = load_chain_sources(_FLAT_GED, _DEBUG)
    ops_df = sources["ops_df"]

    cv = build_chain_versions(ops_df)
    cr = build_chain_register(ops_df, cv, sources["debug_df"], sources["effective_df"])

    expected_versions = ops_df["version_key"].nunique()
    expected_families = ops_df["family_key"].nunique()

    assert len(cv) == expected_versions, f"chain_versions: {len(cv)} != {expected_versions}"
    assert len(cr) == expected_families, f"chain_register: {len(cr)} != {expected_families}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — Key consistency
# ─────────────────────────────────────────────────────────────────────────────

class TestKeyConsistency:
    """Every chain_versions family_key must exist in chain_register."""

    @pytest.fixture
    def both_dfs(self):
        ops = _make_ops_df([
            {"numero": "300", "indice": "A", "submittal_date": "2024-01-01"},
            {"numero": "300", "indice": "B", "submittal_date": "2024-02-01"},
            {"numero": "400", "indice": "A", "submittal_date": "2024-03-01"},
        ])
        cv = build_chain_versions(ops)
        cr = build_chain_register(ops, cv)
        return cv, cr

    def test_all_version_families_in_register(self, both_dfs):
        cv, cr = both_dfs
        version_families = set(cv["family_key"].unique())
        register_families = set(cr["family_key"].unique())
        missing = version_families - register_families
        assert not missing, f"Families in chain_versions but not chain_register: {missing}"

    def test_register_has_no_extra_families(self, both_dfs):
        cv, cr = both_dfs
        version_families = set(cv["family_key"].unique())
        register_families = set(cr["family_key"].unique())
        extra = register_families - version_families
        assert not extra, f"Families in chain_register but not chain_versions: {extra}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — latest_indice consistency
# ─────────────────────────────────────────────────────────────────────────────

class TestLatestIndiceConsistency:
    """latest_indice in chain_register must match the indice with max(version_sort_order)."""

    @pytest.fixture
    def dfs_alpha(self):
        ops = _make_ops_df([
            {"numero": "500", "indice": "A", "submittal_date": "2024-01-01"},
            {"numero": "500", "indice": "B", "submittal_date": "2024-02-01"},
            {"numero": "500", "indice": "C", "submittal_date": "2024-03-01"},
            {"numero": "600", "indice": "A", "submittal_date": "2024-01-15"},
            {"numero": "600", "indice": "AA", "submittal_date": "2024-05-01"},
        ])
        cv = build_chain_versions(ops)
        cr = build_chain_register(ops, cv)
        return cv, cr

    def test_latest_indice_matches_max_sort_order(self, dfs_alpha):
        cv, cr = dfs_alpha
        for _, reg_row in cr.iterrows():
            fk = reg_row["family_key"]
            family_versions = cv[cv["family_key"] == fk]
            max_sort_order_idx = family_versions["version_sort_order"].idxmax()
            expected_latest = family_versions.at[max_sort_order_idx, "indice"]
            actual_latest = reg_row["latest_indice"]
            assert actual_latest == expected_latest, (
                f"Family {fk}: latest_indice={actual_latest!r} "
                f"but max version_sort_order indice={expected_latest!r}"
            )

    def test_alpha_single_before_double(self):
        """Pure alpha: single-letter indices sort before double-letter."""
        assert _indice_sort_key("A") < _indice_sort_key("AA")
        assert _indice_sort_key("Z") < _indice_sort_key("AA")
        assert _indice_sort_key("A") < _indice_sort_key("B")
        assert _indice_sort_key("B") < _indice_sort_key("C")
        assert _indice_sort_key("AA") < _indice_sort_key("AB")

    def test_numeric_before_alpha(self):
        """Numeric indices sort before alphabetic."""
        assert _indice_sort_key("1") < _indice_sort_key("A")
        assert _indice_sort_key("10") < _indice_sort_key("A")
        assert _indice_sort_key("1") < _indice_sort_key("2") < _indice_sort_key("10")

    def test_latest_version_key_matches_latest_indice(self, dfs_alpha):
        """latest_version_key must be family_key + '_' + latest_indice."""
        for _, row in dfs_alpha[1].iterrows():
            expected_vk = f"{row['family_key']}_{row['latest_indice']}"
            assert row["latest_version_key"] == expected_vk, (
                f"Family {row['family_key']}: latest_version_key={row['latest_version_key']!r} "
                f"expected={expected_vk!r}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Primary/secondary flags use repo classifier only
# ─────────────────────────────────────────────────────────────────────────────

class TestPrimarySecondaryFlags:
    """
    waiting_primary_flag and waiting_secondary_flag must reflect
    _is_primary_approver() results on the latest version's blocking actors.
    No custom taxonomy permitted.
    """

    def _run(self, rows):
        ops = _make_ops_df(rows)
        cv = build_chain_versions(ops)
        return build_chain_register(ops, cv)

    def test_primary_only_blocking(self):
        """All blocking actors are primary → waiting_primary=True, waiting_secondary=False."""
        cr = self._run([
            {
                "numero": "700", "indice": "A",
                "submittal_date": "2024-01-01",
                "is_blocking": True, "actor_clean": "EGIS",
            },
            {
                "numero": "700", "indice": "A",
                "submittal_date": "2024-01-01",
                "is_blocking": True, "actor_clean": "BET SPK",
            },
        ])
        row = cr[cr["family_key"] == "700"].iloc[0]
        assert row["waiting_primary_flag"]
        assert not row["waiting_secondary_flag"]

    def test_secondary_only_blocking(self):
        """All blocking actors are secondary → waiting_primary=False, waiting_secondary=True."""
        cr = self._run([
            {
                "numero": "800", "indice": "A",
                "submittal_date": "2024-01-01",
                "is_blocking": True, "actor_clean": "Commission Voirie",
            },
            {
                "numero": "800", "indice": "A",
                "submittal_date": "2024-01-01",
                "is_blocking": True, "actor_clean": "Bureau Signalétique",
            },
        ])
        row = cr[cr["family_key"] == "800"].iloc[0]
        assert not row["waiting_primary_flag"]
        assert row["waiting_secondary_flag"]

    def test_mixed_blocking(self):
        """Mix of primary and secondary → both flags True."""
        cr = self._run([
            {
                "numero": "900", "indice": "A",
                "submittal_date": "2024-01-01",
                "is_blocking": True, "actor_clean": "TERRELL",
            },
            {
                "numero": "900", "indice": "A",
                "submittal_date": "2024-01-01",
                "is_blocking": True, "actor_clean": "Bureau Signalétique",
            },
        ])
        row = cr[cr["family_key"] == "900"].iloc[0]
        assert row["waiting_primary_flag"]
        assert row["waiting_secondary_flag"]

    def test_no_blocking_both_false(self):
        """No blocking rows → both flags False."""
        cr = self._run([
            {
                "numero": "950", "indice": "A",
                "submittal_date": "2024-01-01",
                "is_blocking": False, "is_completed": True, "actor_clean": "EGIS",
            },
        ])
        row = cr[cr["family_key"] == "950"].iloc[0]
        assert not row["waiting_primary_flag"]
        assert not row["waiting_secondary_flag"]

    def test_flags_based_on_latest_version_only(self):
        """
        Flags reflect only the LATEST version's blocking actors.
        Older versions with blocking rows should not affect the flags.
        """
        # Family "1000": version A has a blocking secondary actor, version B has a
        # blocking primary actor. Latest = B → waiting_primary=True, waiting_secondary=False.
        cr = self._run([
            {
                "numero": "1000", "indice": "A",
                "submittal_date": "2024-01-01",
                "is_blocking": True, "actor_clean": "Bureau Signalétique",
            },
            {
                "numero": "1000", "indice": "B",
                "submittal_date": "2024-06-01",
                "is_blocking": True, "actor_clean": "EGIS",
            },
        ])
        row = cr[cr["family_key"] == "1000"].iloc[0]
        assert row["latest_indice"] == "B"
        assert row["waiting_primary_flag"]
        assert not row["waiting_secondary_flag"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — No duplicate keys
# ─────────────────────────────────────────────────────────────────────────────

class TestNoDuplicateKeys:
    """version_key must be unique in chain_versions; family_key unique in chain_register."""

    @pytest.fixture
    def both_dfs(self):
        ops = _make_ops_df([
            {"numero": "10", "indice": "A", "submittal_date": "2024-01-01"},
            {"numero": "10", "indice": "A", "submittal_date": "2024-01-01"},  # duplicate row, same version
            {"numero": "10", "indice": "B", "submittal_date": "2024-02-01"},
            {"numero": "20", "indice": "A", "submittal_date": "2024-03-01"},
            {"numero": "20", "indice": "B", "submittal_date": "2024-04-01"},
            {"numero": "20", "indice": "C", "submittal_date": "2024-05-01"},
        ])
        cv = build_chain_versions(ops)
        cr = build_chain_register(ops, cv)
        return cv, cr

    def test_version_key_unique(self, both_dfs):
        cv, _ = both_dfs
        dupes = cv[cv.duplicated("version_key")]
        assert len(dupes) == 0, f"Duplicate version_keys: {dupes['version_key'].tolist()}"

    def test_family_key_unique(self, both_dfs):
        _, cr = both_dfs
        dupes = cr[cr.duplicated("family_key")]
        assert len(dupes) == 0, f"Duplicate family_keys: {dupes['family_key'].tolist()}"

    def test_duplicate_ops_rows_aggregated_correctly(self, both_dfs):
        """Duplicate ops rows for same version_key should aggregate, not duplicate the version."""
        cv, _ = both_dfs
        v = cv[cv["version_key"] == "10_A"]
        assert len(v) == 1
        # row_count_ops should be 2 (the two input rows are aggregated into one)
        assert v.iloc[0]["row_count_ops"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# Test — Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Guard against common edge cases: empty input, single-version family, null dates."""

    def test_empty_ops_df_returns_empty_versions(self):
        cv = build_chain_versions(pd.DataFrame())
        assert isinstance(cv, pd.DataFrame)
        assert len(cv) == 0

    def test_empty_versions_returns_empty_register(self):
        cr = build_chain_register(pd.DataFrame(), pd.DataFrame())
        assert isinstance(cr, pd.DataFrame)
        assert len(cr) == 0

    def test_single_version_family_sort_order_is_1(self):
        """A family with a single version must have version_sort_order=1."""
        ops = _make_ops_df([
            {"numero": "999", "indice": "A", "submittal_date": "2024-01-01"},
        ])
        cv = build_chain_versions(ops)
        assert cv.iloc[0]["version_sort_order"] == 1

    def test_null_response_dates_tolerated(self):
        """Null response_date must not crash; latest_response_date should be NaT."""
        ops = _make_ops_df([
            {"numero": "111", "indice": "A", "submittal_date": "2024-01-01", "response_date": None},
        ])
        cv = build_chain_versions(ops)
        assert pd.isna(cv.iloc[0]["latest_response_date"])

    def test_null_submittal_dates_tolerated(self):
        """Null submittal_date must not crash; first/latest_submission_date will be NaT."""
        ops = _make_ops_df([
            {"numero": "112", "indice": "A"},  # no submittal_date key at all
        ])
        cv = build_chain_versions(ops)
        assert pd.isna(cv.iloc[0]["first_submission_date"])
