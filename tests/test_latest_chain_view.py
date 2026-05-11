"""
Integration tests for build_latest_chain_view against live Chain+Onion artifacts.
"""
import sys
from pathlib import Path

import pytest
import pandas as pd

# Ensure src/ is importable
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from reporting.latest_chain_view import build_latest_chain_view, latest_enriched_view

BASE_DIR = repo_root
REGISTER_PATH = BASE_DIR / "output" / "chain_onion" / "CHAIN_REGISTER.csv"


@pytest.fixture(scope="module")
def latest_chain_df():
    return build_latest_chain_view(BASE_DIR)


@pytest.fixture(scope="module")
def register_df():
    return pd.read_csv(REGISTER_PATH, dtype={"family_key": str, "numero": str})


REQUIRED_COLUMNS = [
    "family_key",
    "numero",
    "latest_indice",
    "latest_version_key",
    "current_state",
    "portfolio_bucket",
    "stale_days",
    "last_real_activity_date",
    "latest_submission_date",
    "current_blocking_actor_count",
    "waiting_primary_flag",
    "waiting_secondary_flag",
    "version_key",
    "indice",
    "latest_response_date",
    "requires_new_cycle_flag",
]


def test_helper_returns_dataframe(latest_chain_df):
    assert isinstance(latest_chain_df, pd.DataFrame)
    assert len(latest_chain_df) > 0


def test_row_count_equals_chain_register(latest_chain_df, register_df):
    assert len(latest_chain_df) == len(register_df)


def test_family_key_unique(latest_chain_df):
    assert latest_chain_df["family_key"].is_unique


def test_numero_unique(latest_chain_df):
    assert latest_chain_df["numero"].is_unique


def test_version_key_matches_latest_version_key(latest_chain_df):
    assert latest_chain_df["version_key"].equals(latest_chain_df["latest_version_key"])


def test_indice_matches_latest_indice(latest_chain_df):
    assert latest_chain_df["indice"].equals(latest_chain_df["latest_indice"])


def test_required_columns_present(latest_chain_df):
    missing = set(REQUIRED_COLUMNS) - set(latest_chain_df.columns)
    assert not missing, f"Missing required columns: {missing}"


def test_raises_when_chain_register_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_latest_chain_view(tmp_path)


def test_docs_df_enrichment_path():
    """When docs_df is passed, enrichment should still produce emetteur/titre columns."""
    synthetic = pd.DataFrame({
        "numero": ["DOC-001", "DOC-002"],
        "indice": ["A", "B"],
        "emetteur": ["EMT1", "EMT2"],
        "libelle_du_document": ["Title One", "Title Two"],
    })
    df = build_latest_chain_view(BASE_DIR, docs_df=synthetic)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == len(pd.read_csv(REGISTER_PATH, usecols=["family_key"]))
    assert "emetteur" in df.columns
    assert "titre" in df.columns


# ── latest_enriched_view contract tests (Step 8) ─────────────────────────────

def test_latest_enriched_view_filters_to_chain_keys():
    """latest_enriched_view keeps only rows whose (numero, indice) is
    present in ctx.latest_chain_df.(numero, latest_indice).
    Pollution rows (non-latest indice) are dropped."""
    from types import SimpleNamespace

    dernier = pd.DataFrame({
        "numero": ["100", "100", "200", "200"],
        "indice": ["A", "B", "A", "B"],
    })
    latest = pd.DataFrame({
        "numero": ["100", "200"],
        "latest_indice": ["B", "A"],
    })
    ctx = SimpleNamespace(dernier_df=dernier, latest_chain_df=latest)
    out = latest_enriched_view(ctx)
    assert len(out) == 2
    pairs = set(zip(out["numero"], out["indice"]))
    assert pairs == {("100", "B"), ("200", "A")}


def test_latest_enriched_view_legacy_fallback_returns_full_dernier_df():
    """When ctx.latest_chain_df is None, latest_enriched_view returns
    ctx.dernier_df unchanged (no filtering)."""
    from types import SimpleNamespace

    dernier = pd.DataFrame({
        "numero": ["100", "100", "200"],
        "indice": ["A", "B", "A"],
    })
    ctx = SimpleNamespace(dernier_df=dernier, latest_chain_df=None)
    out = latest_enriched_view(ctx)
    assert len(out) == 3
    assert out["numero"].tolist() == ["100", "100", "200"]
    assert out["indice"].tolist() == ["A", "B", "A"]


def test_latest_enriched_view_preserves_precomputed_columns():
    """Columns added to dernier_df by mutators (e.g. _visa_global)
    survive the intersection — they are inherited row-by-row."""
    from types import SimpleNamespace

    dernier = pd.DataFrame({
        "numero": ["100", "100"],
        "indice": ["A", "B"],
        "_visa_global": ["VAO", "REF"],
        "_focus_owner_tier": ["CLOSED", "CONTRACTOR"],
    })
    latest = pd.DataFrame({
        "numero": ["100"],
        "latest_indice": ["B"],
    })
    ctx = SimpleNamespace(dernier_df=dernier, latest_chain_df=latest)
    out = latest_enriched_view(ctx)
    assert len(out) == 1
    assert out.iloc[0]["_visa_global"] == "REF"
    assert out.iloc[0]["_focus_owner_tier"] == "CONTRACTOR"
