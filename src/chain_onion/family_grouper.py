"""
src/chain_onion/family_grouper.py
----------------------------------
Step 05 — Family Grouper Engine.

Transforms row-level ops_df into two structural chain layers:
  - chain_versions  : one row per VERSION_KEY  (numero + indice)
  - chain_register  : one row per FAMILY_KEY   (numero)

No chain state classification. No event timeline. No onion attribution.
Those belong to Steps 07, 06, and 09 respectively.

Identity model (STEP02 Section A):
    FAMILY_KEY  = str(numero)
    VERSION_KEY = "{numero}_{indice}"

Primary vs Secondary consultant classification uses exclusively:
    _is_primary_approver() from src/query_library.py
No parallel keyword list is defined here.

Indice sort order algorithm (version_sort_order):
    1. Numeric indices (e.g. "1", "2", "10") — sorted by integer value (lowest first)
    2. Pure alphabetic indices — sorted by (length ASC, alphabetical ASC)
       This gives: A < B < ... < Z < AA < AB < ... < ZZ < AAA ...
    3. Mixed/other — lexical fallback (tie-break by raw string)
    Each group produces 1-based ranks within its family_key.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Ensure src/ is importable (mirrors source_loader.py pattern) ──────────
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_LOG = logging.getLogger(__name__)

# ── Primary approver classifier — authoritative source is query_library.py ─
try:
    from query_library import _is_primary_approver  # type: ignore
    _LOG.debug("family_grouper: _is_primary_approver loaded from query_library")
except ImportError as _import_err:
    _LOG.warning(
        "family_grouper: cannot import _is_primary_approver from query_library (%s) — "
        "using inline fallback that mirrors the repo definition exactly",
        _import_err,
    )
    _PRIMARY_APPROVER_KEYWORDS_FALLBACK = [
        "TERRELL", "EGIS", "BET SPK", "BET ASC", "BET EV",
        "BET FACADES", "ARCHI MOX", "MOEX",
    ]

    def _is_primary_approver(name: str) -> bool:  # type: ignore[misc]
        """Fallback mirror of query_library._is_primary_approver."""
        u = str(name).upper()
        return any(kw in u for kw in _PRIMARY_APPROVER_KEYWORDS_FALLBACK)


# ── Output column definitions ─────────────────────────────────────────────

_CHAIN_VERSIONS_COLS: list = [
    "family_key", "version_key", "numero", "indice",
    "row_count_ops",
    "first_submission_date", "latest_submission_date", "latest_response_date",
    "has_blocking_rows", "blocking_actor_count",
    "requires_new_cycle_flag", "completed_row_count", "source_row_count",
    "version_sort_order",
]

_CHAIN_REGISTER_COLS: list = [
    "family_key", "numero",
    "total_versions", "total_rows_ops",
    "first_submission_date", "latest_submission_date",
    "latest_indice", "latest_version_key",
    "total_blocking_versions", "total_versions_requiring_cycle",
    "total_completed_rows", "current_blocking_actor_count",
    "waiting_primary_flag", "waiting_secondary_flag",
    "has_debug_trace", "has_effective_rows",
]


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _indice_sort_key(indice: str) -> tuple:
    """
    Deterministic sort key for document version indices.

    Algorithm (documented per Step 05 contract):
      - Empty string            → (3, 0, "")           — sorted last
      - Pure digits ("1","10")  → (0, int, raw)         — numeric order, first tier
      - Pure alpha ("A","AA")   → (1, len, upper_str)   — A-Z then AA-ZZ, second tier
      - Mixed/other ("A1","2B") → (2, 0, upper_str)     — lexical, third tier

    Rationale for alpha sort (1, len, s):
      Single-letter (len=1) always precedes double-letter (len=2), and within each
      length tier strings sort alphabetically.  This yields:
        A, B, ..., Z, AA, AB, ..., AZ, BA, ..., ZZ, AAA, ...
    """
    s = str(indice).strip().upper()
    if not s:
        return (3, 0, "")
    if s.isdigit():
        return (0, int(s), s)
    if s.isalpha():
        return (1, len(s), s)
    return (2, 0, s)


def _safe_date_col(df: pd.DataFrame, col: str) -> pd.Series:
    """Return datetime64 Series with NaT for missing/bad values."""
    if col not in df.columns:
        return pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    return pd.to_datetime(df[col], errors="coerce")


def _safe_bool_col(df: pd.DataFrame, col: str) -> pd.Series:
    """Return bool Series; handles already-bool, string 'True'/'False', and None."""
    if col not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)
    s = df[col]
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False).astype(bool)
    return (
        s.map({"True": True, "False": False, True: True, False: False})
        .fillna(False)
        .astype(bool)
    )


def _assign_version_sort_orders(agg_df: pd.DataFrame) -> pd.Series:
    """
    Assign 1-based version_sort_order within each family_key.

    Uses _indice_sort_key for ordering. Families with a single version
    receive version_sort_order = 1.

    Returns a pd.Series indexed like agg_df.
    """
    sort_key_series = agg_df["indice"].apply(_indice_sort_key)
    agg_with_sk = agg_df.assign(_sk=sort_key_series)
    sort_order = pd.Series(0, index=agg_df.index, dtype=int)

    for _, grp in agg_with_sk.groupby("family_key", sort=False):
        sorted_idx = grp.sort_values("_sk").index
        for rank, orig_idx in enumerate(sorted_idx, start=1):
            sort_order.at[orig_idx] = rank

    return sort_order


# ─────────────────────────────────────────────────────────────────────────────
# Public functions
# ─────────────────────────────────────────────────────────────────────────────

def build_chain_versions(ops_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build chain_versions: one row per VERSION_KEY.

    Parameters
    ----------
    ops_df
        GED_OPERATIONS DataFrame as returned by load_chain_sources().
        Must have: family_key, version_key, numero, indice,
                   submittal_date, response_date, is_blocking,
                   is_completed, requires_new_cycle, actor_clean.

    Returns
    -------
    pd.DataFrame — columns per _CHAIN_VERSIONS_COLS.
    One row per unique version_key.
    Sorted by (family_key, version_sort_order).
    """
    if ops_df is None or ops_df.empty:
        _LOG.warning("build_chain_versions: ops_df is empty — returning empty DataFrame")
        return pd.DataFrame(columns=_CHAIN_VERSIONS_COLS)

    df = ops_df.copy()

    # ── Normalize date and bool columns ───────────────────────────────────
    df["_submittal"] = _safe_date_col(df, "submittal_date")
    df["_response"]  = _safe_date_col(df, "response_date")
    df["_blocking"]  = _safe_bool_col(df, "is_blocking")
    df["_completed"] = _safe_bool_col(df, "is_completed")
    df["_new_cycle"] = _safe_bool_col(df, "requires_new_cycle")

    # ── Core aggregations (one pass over ops_df) ──────────────────────────
    agg = (
        df.groupby("version_key", sort=False)
        .agg(
            family_key=("family_key", "first"),
            numero=("numero", "first"),
            indice=("indice", "first"),
            row_count_ops=("version_key", "count"),
            first_submission_date=("_submittal", "min"),
            latest_submission_date=("_submittal", "max"),
            has_blocking_rows=("_blocking", "any"),
            requires_new_cycle_flag=("_new_cycle", "any"),
            completed_row_count=("_completed", "sum"),
        )
        .reset_index()
    )
    agg["completed_row_count"] = agg["completed_row_count"].astype(int)
    agg["source_row_count"] = agg["row_count_ops"]

    # ── latest_response_date: max non-null response_date per version ──────
    valid_resp = df.dropna(subset=["_response"])
    if not valid_resp.empty:
        latest_resp = (
            valid_resp.groupby("version_key")["_response"]
            .max()
            .rename("latest_response_date")
            .reset_index()
        )
        agg = agg.merge(latest_resp, on="version_key", how="left")
    else:
        agg["latest_response_date"] = pd.NaT

    # ── blocking_actor_count: distinct actor_clean where is_blocking ──────
    blocking_rows = df[df["_blocking"]]
    if not blocking_rows.empty:
        blocking_ac = (
            blocking_rows.groupby("version_key")["actor_clean"]
            .nunique()
            .rename("blocking_actor_count")
            .reset_index()
        )
        agg = agg.merge(blocking_ac, on="version_key", how="left")
    else:
        agg["blocking_actor_count"] = 0
    agg["blocking_actor_count"] = agg["blocking_actor_count"].fillna(0).astype(int)

    # ── version_sort_order: 1-based rank within each family ───────────────
    agg["version_sort_order"] = _assign_version_sort_orders(agg)

    # Warn on any anomalous indices (zero sort order means groupby had no rows — impossible)
    zero_order = agg["version_sort_order"] == 0
    if zero_order.any():
        _LOG.warning(
            "build_chain_versions: %d rows have version_sort_order=0 (unexpected)",
            int(zero_order.sum()),
        )

    _LOG.info(
        "build_chain_versions: %d version rows, %d families",
        len(agg), agg["family_key"].nunique(),
    )

    return (
        agg[_CHAIN_VERSIONS_COLS]
        .sort_values(["family_key", "version_sort_order"])
        .reset_index(drop=True)
    )


def build_chain_register(
    ops_df: pd.DataFrame,
    chain_versions_df: pd.DataFrame,
    debug_df: Optional[pd.DataFrame] = None,
    effective_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Build chain_register: one row per FAMILY_KEY.

    Parameters
    ----------
    ops_df
        GED_OPERATIONS DataFrame (same source as build_chain_versions).
        Used for total_rows_ops and waiting_*_flag derivations.
    chain_versions_df
        Output of build_chain_versions().
    debug_df
        Optional DEBUG_TRACE DataFrame. When provided, has_debug_trace is set
        for families present in debug_df.family_key.
    effective_df
        Optional effective_responses DataFrame. When provided, has_effective_rows
        is set for families present in effective_df.family_key.

    Returns
    -------
    pd.DataFrame — columns per _CHAIN_REGISTER_COLS.
    One row per unique family_key. Sorted by family_key.

    NOT computed here (Step 07):
        current_state, portfolio_bucket, stale_days, operational_relevance_score
    """
    if chain_versions_df is None or chain_versions_df.empty:
        _LOG.warning("build_chain_register: chain_versions_df is empty — returning empty DataFrame")
        return pd.DataFrame(columns=_CHAIN_REGISTER_COLS)

    cv = chain_versions_df.copy()

    # ── Family-level aggregations from chain_versions ─────────────────────
    reg = (
        cv.groupby("family_key", sort=False)
        .agg(
            numero=("numero", "first"),
            total_versions=("version_key", "count"),
            first_submission_date=("first_submission_date", "min"),
            latest_submission_date=("latest_submission_date", "max"),
            total_blocking_versions=("has_blocking_rows", "sum"),
            total_versions_requiring_cycle=("requires_new_cycle_flag", "sum"),
            total_completed_rows=("completed_row_count", "sum"),
        )
        .reset_index()
    )
    reg["total_blocking_versions"] = reg["total_blocking_versions"].astype(int)
    reg["total_versions_requiring_cycle"] = reg["total_versions_requiring_cycle"].astype(int)
    reg["total_completed_rows"] = reg["total_completed_rows"].astype(int)

    # ── total_rows_ops from ops_df ────────────────────────────────────────
    if ops_df is not None and not ops_df.empty:
        ops_counts = (
            ops_df.groupby("family_key")
            .size()
            .rename("total_rows_ops")
            .reset_index()
        )
        reg = reg.merge(ops_counts, on="family_key", how="left")
    else:
        reg["total_rows_ops"] = pd.NA
    reg["total_rows_ops"] = reg["total_rows_ops"].fillna(0).astype(int)

    # ── latest_indice and latest_version_key ──────────────────────────────
    # Derive from max version_sort_order per family (Test 4 criterion)
    latest = (
        cv.sort_values("version_sort_order", ascending=False)
        .groupby("family_key", sort=False)
        .first()[["indice", "version_key", "blocking_actor_count"]]
        .rename(columns={
            "indice": "latest_indice",
            "version_key": "latest_version_key",
            "blocking_actor_count": "current_blocking_actor_count",
        })
        .reset_index()
    )
    reg = reg.merge(latest, on="family_key", how="left")
    reg["current_blocking_actor_count"] = (
        reg["current_blocking_actor_count"].fillna(0).astype(int)
    )

    # ── waiting_primary_flag / waiting_secondary_flag ─────────────────────
    # Uses _is_primary_approver from query_library — no custom taxonomy
    # Logic: look at blocking actors in the LATEST version of each family
    reg["waiting_primary_flag"]   = False
    reg["waiting_secondary_flag"] = False

    if ops_df is not None and not ops_df.empty:
        latest_vk_set = set(reg["latest_version_key"].dropna())
        ops_bool_blocking = _safe_bool_col(ops_df, "is_blocking")
        blocking_latest = ops_df[
            ops_df["version_key"].isin(latest_vk_set) & ops_bool_blocking
        ].copy()

        if not blocking_latest.empty:
            blocking_latest["_is_primary"] = (
                blocking_latest["actor_clean"]
                .apply(lambda x: _is_primary_approver(str(x)) if pd.notna(x) else False)
            )

            # Build family → flag dicts; default False for families not in blocking_latest
            prim_by_family = (
                blocking_latest.groupby("family_key")["_is_primary"]
                .any()
                .to_dict()
            )
            sec_by_family = {
                fk: bool((~grp["_is_primary"]).any())
                for fk, grp in blocking_latest.groupby("family_key")
            }

            # Assign via list comprehension — avoids all pandas fillna/merge paths
            reg["waiting_primary_flag"]   = [bool(prim_by_family.get(fk, False)) for fk in reg["family_key"]]
            reg["waiting_secondary_flag"] = [bool(sec_by_family.get(fk, False))  for fk in reg["family_key"]]

    # ── has_debug_trace ───────────────────────────────────────────────────
    if debug_df is not None and not debug_df.empty and "family_key" in debug_df.columns:
        debug_families = set(debug_df["family_key"].dropna())
        reg["has_debug_trace"] = reg["family_key"].isin(debug_families)
    else:
        reg["has_debug_trace"] = False

    # ── has_effective_rows ────────────────────────────────────────────────
    if effective_df is not None and not effective_df.empty and "family_key" in effective_df.columns:
        eff_families = set(effective_df["family_key"].dropna())
        reg["has_effective_rows"] = reg["family_key"].isin(eff_families)
    else:
        reg["has_effective_rows"] = False

    _LOG.info(
        "build_chain_register: %d family rows | avg versions/family=%.2f | "
        "blocking families=%d",
        len(reg),
        reg["total_versions"].mean() if len(reg) > 0 else 0.0,
        int((reg["current_blocking_actor_count"] > 0).sum()),
    )

    return (
        reg[_CHAIN_REGISTER_COLS]
        .sort_values("family_key")
        .reset_index(drop=True)
    )
