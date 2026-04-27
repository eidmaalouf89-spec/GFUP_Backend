"""
src/chain_onion/chain_metrics.py
----------------------------------
Step 08 — Chain Metrics Engine.

Produces two outputs from classified chains:
    chain_metrics_df       : one row per family_key — per-chain numeric intelligence
    portfolio_metrics_dict : global portfolio KPI summary

No new chain state classification.
No onion blame attribution.
No narrative text.
Numeric truth only.

Public API
----------
build_chain_metrics(
    chain_register_df,
    chain_versions_df,
    chain_events_df,
    ops_df,
) -> tuple[pd.DataFrame, dict]

Inputs (all read-only)
----------------------
chain_register_df   : output of classify_chains() — one row per family_key
                      must have: current_state, portfolio_bucket,
                      operational_relevance_score, stale_days,
                      last_real_activity_date, first_submission_date,
                      latest_submission_date, total_versions,
                      current_blocking_actor_count,
                      total_versions_requiring_cycle
chain_versions_df   : output of build_chain_versions() — one row per version_key
chain_events_df     : output of build_chain_events() — one row per event
ops_df              : GED_OPERATIONS — used only to extract data_date

Pressure index formula (documented exactly once here)
------------------------------------------------------
    base = operational_relevance_score
    +15 if LIVE_OPERATIONAL AND current_blocking_actor_count >= 1
    +10 if 15 <= stale_days <= 45
    +10 if rejection_cycles >= 2
    +10 if current_state in {WAITING_CORRECTED_INDICE, CHRONIC_REF_CHAIN}
    -20 if ARCHIVED_HISTORICAL
    -10 if LEGACY_BACKLOG
    clamp to [0, 100]

Rejection cycles definition
----------------------------
    total_versions_requiring_cycle from chain_register_df.
    This equals the count of distinct version_keys for the family where
    requires_new_cycle_flag is True, as computed by family_grouper.py (Step 05).
    Rule: a version counts as a rejection cycle when it required the submitter
    to produce a corrected new revision (requires_new_cycle = True in ops_df).

Wait day allocation
-------------------
    For each chain_events row with delay_contribution_days > 0:
        actor_type PRIMARY_CONSULTANT   → primary_wait_days
        actor_type SECONDARY_CONSULTANT → secondary_wait_days
        actor_type MOEX                 → moex_wait_days
        actor_type SAS                  → sas_wait_days
    Zero is used when no delay_contribution_days is available (no invented values).

Portfolio dormant_ghost_ratio
------------------------------
    legacy_chains / max(open_chains, 1)
    open_chains = live_chains + legacy_chains   (non-archived)
    Strategic KPI for this project.
"""

from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_LOG = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

CHURN_RATIO_CAP: float = 10.0
RESPONSE_VELOCITY_WINDOW_DAYS: int = 90
PRESSURE_MIN: int = 0
PRESSURE_MAX: int = 100

_LIVE_BUCKET  = "LIVE_OPERATIONAL"
_LEGACY_BUCKET = "LEGACY_BACKLOG"
_ARCHIVED_BUCKET = "ARCHIVED_HISTORICAL"

_HIGH_PRESSURE_STATES = frozenset({
    "WAITING_CORRECTED_INDICE",
    "CHRONIC_REF_CHAIN",
})

# actor_type values produced by chain_builder.py (Step 06)
_ACTOR_PRIMARY   = "PRIMARY_CONSULTANT"
_ACTOR_SECONDARY = "SECONDARY_CONSULTANT"
_ACTOR_MOEX      = "MOEX"
_ACTOR_SAS       = "SAS"

# States counted as "live waiting by type" for portfolio backlog metrics
_STATE_WAITING_MOEX      = "OPEN_WAITING_MOEX"
_STATE_WAITING_PRIMARY   = "OPEN_WAITING_PRIMARY_CONSULTANT"
_STATE_WAITING_SECONDARY = "OPEN_WAITING_SECONDARY_CONSULTANT"
_STATE_WAITING_MIXED     = "OPEN_WAITING_MIXED_CONSULTANTS"
_STATE_WAITING_CORRECTED = "WAITING_CORRECTED_INDICE"
_STATE_CHRONIC           = "CHRONIC_REF_CHAIN"

# Output column order for chain_metrics_df
_CHAIN_METRICS_COLS: list[str] = [
    # Identity
    "family_key",
    "numero",
    # Inherited
    "current_state",
    "portfolio_bucket",
    "operational_relevance_score",
    # Lifecycle time
    "first_submission_date",
    "latest_submission_date",
    "last_real_activity_date",
    "open_days",
    "stale_days",
    "active_days",
    # Volumes
    "total_versions",
    "total_events",
    "rejection_cycles",
    "total_blocking_events",
    # Wait days by actor type
    "primary_wait_days",
    "secondary_wait_days",
    "moex_wait_days",
    "sas_wait_days",
    # Delay
    "cumulative_delay_days",
    "avg_delay_per_event",
    "max_single_event_delay",
    # Efficiency
    "churn_ratio",
    "response_velocity_90d",
    "pressure_index",
    # Flags
    "is_live_operational",
    "is_legacy_backlog",
    "is_archived",
]


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_data_date(ops_df: pd.DataFrame) -> Optional[pd.Timestamp]:
    """Extract data_date from ops_df. Returns None if unavailable."""
    if ops_df is None or ops_df.empty or "data_date" not in ops_df.columns:
        _LOG.warning("chain_metrics: data_date not in ops_df — date-based metrics will be null")
        return None
    vals = ops_df["data_date"].dropna()
    if vals.empty:
        _LOG.warning("chain_metrics: data_date is all-null — date-based metrics will be null")
        return None
    raw = vals.iloc[0]
    try:
        ts = pd.Timestamp(raw)
        return ts if pd.notna(ts) else None
    except Exception:
        _LOG.warning("chain_metrics: data_date parse failed — date-based metrics will be null")
        return None


def _normalize_bool_col(s: pd.Series) -> pd.Series:
    """Coerce string/object bool column to dtype bool, NaN → False."""
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False).astype(bool)
    return (
        s.map({"True": True, "False": False, True: True, False: False})
        .fillna(False)
        .astype(bool)
    )


def _safe_days(ts_end: pd.Timestamp, ts_start) -> Optional[float]:
    """Return (ts_end - ts_start).days or None if either is NaT/None."""
    if pd.isna(ts_end) or ts_start is None or pd.isna(ts_start):
        return None
    try:
        delta = pd.Timestamp(ts_end) - pd.Timestamp(ts_start)
        return max(delta.days, 0)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Event-level aggregations from chain_events_df
# ─────────────────────────────────────────────────────────────────────────────

def _aggregate_events(
    chain_events_df: pd.DataFrame,
    data_date: Optional[pd.Timestamp],
) -> pd.DataFrame:
    """
    Group chain_events_df by family_key and compute event-derived columns.

    Returns a DataFrame indexed by family_key with columns:
        total_events, total_blocking_events,
        primary_wait_days, secondary_wait_days, moex_wait_days, sas_wait_days,
        cumulative_delay_days, avg_delay_per_event, max_single_event_delay,
        response_velocity_90d
    """
    if chain_events_df is None or chain_events_df.empty:
        _LOG.warning("chain_metrics: chain_events_df is empty — all event metrics will be 0")
        return pd.DataFrame()

    ev = chain_events_df.copy()

    # Normalize booleans
    for col in ("is_blocking",):
        if col in ev.columns:
            ev[col] = _normalize_bool_col(ev[col])

    # Ensure numeric delay column
    if "delay_contribution_days" in ev.columns:
        ev["delay_contribution_days"] = pd.to_numeric(
            ev["delay_contribution_days"], errors="coerce"
        ).fillna(0)
    else:
        _LOG.warning("chain_metrics: delay_contribution_days not in chain_events — delay metrics = 0")
        ev["delay_contribution_days"] = 0

    # actor_type column
    if "actor_type" not in ev.columns:
        _LOG.warning("chain_metrics: actor_type not in chain_events — wait day metrics = 0")
        ev["actor_type"] = "UNKNOWN"

    # ── Base aggregations ──────────────────────────────────────────────────

    agg = (
        ev.groupby("family_key", sort=False)
        .agg(
            total_events=("family_key", "count"),
            total_blocking_events=("is_blocking", "sum"),
        )
        .reset_index()
    )

    # ── Delay metrics (positive contributions only) ──────────────────────

    pos = ev[ev["delay_contribution_days"] > 0].copy()

    delay_agg = (
        pos.groupby("family_key", sort=False)["delay_contribution_days"]
        .agg(
            cumulative_delay_days="sum",
            avg_delay_per_event="mean",
            max_single_event_delay="max",
        )
        .reset_index()
    )

    # ── Wait days by actor type ──────────────────────────────────────────

    def _wait_sum(actor_label: str) -> pd.Series:
        mask = (ev["actor_type"] == actor_label) & (ev["delay_contribution_days"] > 0)
        return (
            ev[mask]
            .groupby("family_key", sort=False)["delay_contribution_days"]
            .sum()
        )

    primary_wait   = _wait_sum(_ACTOR_PRIMARY).rename("primary_wait_days")
    secondary_wait = _wait_sum(_ACTOR_SECONDARY).rename("secondary_wait_days")
    moex_wait      = _wait_sum(_ACTOR_MOEX).rename("moex_wait_days")
    sas_wait       = _wait_sum(_ACTOR_SAS).rename("sas_wait_days")

    wait_df = pd.concat(
        [primary_wait, secondary_wait, moex_wait, sas_wait], axis=1
    ).reset_index().rename(columns={"index": "family_key"})

    # ── Response velocity (events in last 90 days / 90) ──────────────────

    velocity_series: pd.Series
    if data_date is not None and "event_date" in ev.columns:
        ev["event_date"] = pd.to_datetime(ev["event_date"], errors="coerce")
        cutoff = data_date - pd.Timedelta(days=RESPONSE_VELOCITY_WINDOW_DAYS)
        recent = ev[ev["event_date"] >= cutoff]
        velocity_series = (
            recent.groupby("family_key", sort=False)["event_date"]
            .count()
            .divide(RESPONSE_VELOCITY_WINDOW_DAYS)
            .rename("response_velocity_90d")
        )
    else:
        velocity_series = pd.Series(dtype=float, name="response_velocity_90d")

    # ── Merge all event aggregations ──────────────────────────────────────

    result = agg.merge(delay_agg, on="family_key", how="left")
    result = result.merge(wait_df, on="family_key", how="left")
    result = result.merge(
        velocity_series.reset_index(), on="family_key", how="left"
    )

    # Fill missing numerics with 0
    for col in [
        "cumulative_delay_days", "avg_delay_per_event", "max_single_event_delay",
        "primary_wait_days", "secondary_wait_days", "moex_wait_days", "sas_wait_days",
        "response_velocity_90d",
    ]:
        if col not in result.columns:
            result[col] = 0.0
        else:
            result[col] = result[col].fillna(0.0)

    result["total_blocking_events"] = result["total_blocking_events"].fillna(0).astype(int)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Pressure index
# ─────────────────────────────────────────────────────────────────────────────

def _compute_pressure_index(row: pd.Series) -> int:
    """
    Deterministic urgency score [0, 100].

    Formula:
        base = operational_relevance_score
        +15 if LIVE_OPERATIONAL AND current_blocking_actor_count >= 1
        +10 if 15 <= stale_days <= 45
        +10 if rejection_cycles >= 2
        +10 if current_state in {WAITING_CORRECTED_INDICE, CHRONIC_REF_CHAIN}
        -20 if ARCHIVED_HISTORICAL
        -10 if LEGACY_BACKLOG
        clamp to [0, 100]
    """
    score = int(row.get("operational_relevance_score", 0) or 0)

    bucket = str(row.get("portfolio_bucket", "") or "")
    state  = str(row.get("current_state", "") or "")

    blocking_count = int(row.get("current_blocking_actor_count", 0) or 0)
    stale_days     = row.get("stale_days")
    rejection_cycles = int(row.get("rejection_cycles", 0) or 0)

    if bucket == _LIVE_BUCKET and blocking_count >= 1:
        score += 15

    if stale_days is not None and not pd.isna(stale_days):
        sd = int(stale_days)
        if 15 <= sd <= 45:
            score += 10

    if rejection_cycles >= 2:
        score += 10

    if state in _HIGH_PRESSURE_STATES:
        score += 10

    if bucket == _ARCHIVED_BUCKET:
        score -= 20

    if bucket == _LEGACY_BUCKET:
        score -= 10

    return int(max(PRESSURE_MIN, min(PRESSURE_MAX, score)))


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_chain_metrics(
    chain_register_df: pd.DataFrame,
    chain_versions_df: pd.DataFrame,
    chain_events_df: pd.DataFrame,
    ops_df: pd.DataFrame,
) -> tuple:
    """
    Build per-family chain metrics and portfolio KPI summary.

    Parameters
    ----------
    chain_register_df : classified chain register (output of classify_chains)
    chain_versions_df : chain versions table (output of build_chain_versions)
    chain_events_df   : chain events table (output of build_chain_events)
    ops_df            : GED_OPERATIONS — used only to extract data_date

    Returns
    -------
    (chain_metrics_df, portfolio_metrics_dict)
    """
    if chain_register_df is None or chain_register_df.empty:
        _LOG.warning("chain_metrics: chain_register_df is empty — returning empty metrics")
        return pd.DataFrame(columns=_CHAIN_METRICS_COLS), {}

    data_date = _get_data_date(ops_df)

    # ── Work on a copy — never mutate inputs ─────────────────────────────
    reg = chain_register_df.copy()

    # ── Normalise key columns ─────────────────────────────────────────────

    for col in ("waiting_primary_flag", "waiting_secondary_flag"):
        if col in reg.columns:
            reg[col] = _normalize_bool_col(reg[col])

    for date_col in ("first_submission_date", "latest_submission_date", "last_real_activity_date"):
        if date_col in reg.columns:
            reg[date_col] = pd.to_datetime(reg[date_col], errors="coerce")

    if "stale_days" in reg.columns:
        reg["stale_days"] = pd.to_numeric(reg["stale_days"], errors="coerce")

    if "operational_relevance_score" in reg.columns:
        reg["operational_relevance_score"] = (
            pd.to_numeric(reg["operational_relevance_score"], errors="coerce").fillna(0).astype(int)
        )
    else:
        _LOG.warning("chain_metrics: operational_relevance_score not in register — defaulting to 0")
        reg["operational_relevance_score"] = 0

    if "current_blocking_actor_count" in reg.columns:
        reg["current_blocking_actor_count"] = (
            pd.to_numeric(reg["current_blocking_actor_count"], errors="coerce").fillna(0).astype(int)
        )
    else:
        reg["current_blocking_actor_count"] = 0

    # ── rejection_cycles from chain_register ─────────────────────────────
    # Uses total_versions_requiring_cycle (Step 05 output): count of distinct
    # versions where requires_new_cycle = True in ops_df. This is the
    # authoritative version-level rejection count without re-reading raw data.
    if "total_versions_requiring_cycle" in reg.columns:
        reg["rejection_cycles"] = (
            pd.to_numeric(reg["total_versions_requiring_cycle"], errors="coerce")
            .fillna(0)
            .astype(int)
        )
    else:
        _LOG.warning(
            "chain_metrics: total_versions_requiring_cycle not in register — rejection_cycles = 0"
        )
        reg["rejection_cycles"] = 0

    # ── Lifecycle time columns ─────────────────────────────────────────────

    if data_date is not None:
        reg["open_days"] = reg["first_submission_date"].apply(
            lambda d: _safe_days(data_date, d)
        )
    else:
        reg["open_days"] = None

    reg["active_days"] = reg.apply(
        lambda r: _safe_days(r.get("last_real_activity_date"), r.get("first_submission_date")),
        axis=1,
    )
    # active_days: null if either date is missing
    reg.loc[reg["active_days"].isna(), "active_days"] = None

    # ── Merge event aggregations ───────────────────────────────────────────

    event_agg = _aggregate_events(chain_events_df, data_date)

    if not event_agg.empty:
        reg = reg.merge(event_agg, on="family_key", how="left")
    else:
        for col in [
            "total_events", "total_blocking_events",
            "primary_wait_days", "secondary_wait_days", "moex_wait_days", "sas_wait_days",
            "cumulative_delay_days", "avg_delay_per_event", "max_single_event_delay",
            "response_velocity_90d",
        ]:
            reg[col] = 0

    # Fill event columns for families with no events
    for col in [
        "total_events", "total_blocking_events",
        "primary_wait_days", "secondary_wait_days", "moex_wait_days", "sas_wait_days",
        "cumulative_delay_days", "avg_delay_per_event", "max_single_event_delay",
        "response_velocity_90d",
    ]:
        if col not in reg.columns:
            reg[col] = 0.0
        else:
            reg[col] = reg[col].fillna(0.0)

    reg["total_events"] = reg["total_events"].fillna(0).astype(int)
    reg["total_blocking_events"] = reg["total_blocking_events"].fillna(0).astype(int)

    # ── Efficiency metrics ────────────────────────────────────────────────

    total_versions_safe = reg["total_versions"].clip(lower=1) if "total_versions" in reg.columns else 1
    reg["churn_ratio"] = (
        (reg["rejection_cycles"] / total_versions_safe)
        .clip(upper=CHURN_RATIO_CAP)
        .round(4)
    )

    # ── Pressure index ────────────────────────────────────────────────────

    reg["pressure_index"] = reg.apply(_compute_pressure_index, axis=1)

    # ── Boolean flags ────────────────────────────────────────────────────

    reg["is_live_operational"] = reg.get("portfolio_bucket", pd.Series(dtype=str)) == _LIVE_BUCKET
    reg["is_legacy_backlog"]   = reg.get("portfolio_bucket", pd.Series(dtype=str)) == _LEGACY_BUCKET
    reg["is_archived"]         = reg.get("portfolio_bucket", pd.Series(dtype=str)) == _ARCHIVED_BUCKET

    # ── Select and order output columns ───────────────────────────────────

    out_cols = [c for c in _CHAIN_METRICS_COLS if c in reg.columns]
    missing = [c for c in _CHAIN_METRICS_COLS if c not in reg.columns]
    if missing:
        _LOG.warning("chain_metrics: output columns missing from result: %s", missing)
    chain_metrics_df = reg[out_cols].reset_index(drop=True)

    # ── Portfolio KPIs ────────────────────────────────────────────────────

    portfolio_metrics_dict = _build_portfolio_metrics(chain_metrics_df, data_date)

    _LOG.info(
        "chain_metrics: built %d family rows — live=%d legacy=%d archived=%d",
        len(chain_metrics_df),
        int(portfolio_metrics_dict.get("live_chains", 0)),
        int(portfolio_metrics_dict.get("legacy_chains", 0)),
        int(portfolio_metrics_dict.get("archived_chains", 0)),
    )

    return chain_metrics_df, portfolio_metrics_dict


def _build_portfolio_metrics(
    chain_metrics_df: pd.DataFrame,
    data_date: Optional[pd.Timestamp],
) -> dict:
    """
    Compute global portfolio KPI summary from chain_metrics_df.

    Returns dict with all required portfolio metric keys.
    """
    if chain_metrics_df.empty:
        return _empty_portfolio()

    df = chain_metrics_df

    total_chains   = len(df)
    live_chains    = int(df["is_live_operational"].sum()) if "is_live_operational" in df.columns else 0
    legacy_chains  = int(df["is_legacy_backlog"].sum())  if "is_legacy_backlog"   in df.columns else 0
    archived_chains = int(df["is_archived"].sum())       if "is_archived"         in df.columns else 0

    open_chains = live_chains + legacy_chains
    dormant_ghost_ratio = round(legacy_chains / max(open_chains, 1), 4)

    # Health
    live_mask = df["is_live_operational"] if "is_live_operational" in df.columns else pd.Series(False, index=df.index)
    live_df = df[live_mask]

    avg_pressure_live = round(float(live_df["pressure_index"].mean()), 2) if not live_df.empty else 0.0
    avg_versions_per_chain = round(float(df["total_versions"].mean()), 2) if "total_versions" in df.columns else 0.0
    avg_events_per_chain = round(float(df["total_events"].mean()), 2) if "total_events" in df.columns else 0.0

    # Backlog by state (live chains only)
    def _live_state_count(state: str) -> int:
        if "current_state" not in df.columns:
            return 0
        return int((live_mask & (df["current_state"] == state)).sum())

    live_waiting_moex      = _live_state_count(_STATE_WAITING_MOEX)
    live_waiting_primary   = _live_state_count(_STATE_WAITING_PRIMARY)
    live_waiting_secondary = _live_state_count(_STATE_WAITING_SECONDARY)
    live_waiting_mixed     = _live_state_count(_STATE_WAITING_MIXED)
    live_waiting_corrected = _live_state_count(_STATE_WAITING_CORRECTED)
    live_chronic           = _live_state_count(_STATE_CHRONIC)

    # Delay
    total_cumulative_delay_days = int(df["cumulative_delay_days"].sum()) if "cumulative_delay_days" in df.columns else 0
    avg_stale_live = round(float(live_df["stale_days"].dropna().mean()), 2) if not live_df.empty and "stale_days" in live_df.columns else 0.0

    p90_pressure_live = 0.0
    if not live_df.empty and "pressure_index" in live_df.columns:
        p90_pressure_live = round(float(live_df["pressure_index"].quantile(0.9)), 2)

    # Top risk
    top_10_family_keys_by_pressure: list = []
    if "pressure_index" in df.columns and "family_key" in df.columns:
        top_10_family_keys_by_pressure = (
            df.nlargest(10, "pressure_index")["family_key"].tolist()
        )

    return {
        # Overall
        "total_chains":   total_chains,
        "live_chains":    live_chains,
        "legacy_chains":  legacy_chains,
        "archived_chains": archived_chains,
        # Health
        "dormant_ghost_ratio":     dormant_ghost_ratio,
        "avg_pressure_live":       avg_pressure_live,
        "avg_versions_per_chain":  avg_versions_per_chain,
        "avg_events_per_chain":    avg_events_per_chain,
        # Backlog
        "live_waiting_moex":       live_waiting_moex,
        "live_waiting_primary":    live_waiting_primary,
        "live_waiting_secondary":  live_waiting_secondary,
        "live_waiting_mixed":      live_waiting_mixed,
        "live_waiting_corrected":  live_waiting_corrected,
        "live_chronic":            live_chronic,
        # Delay
        "total_cumulative_delay_days": total_cumulative_delay_days,
        "avg_stale_live":              avg_stale_live,
        "p90_pressure_live":           p90_pressure_live,
        # Top risk
        "top_10_family_keys_by_pressure": top_10_family_keys_by_pressure,
    }


def _empty_portfolio() -> dict:
    return {
        "total_chains": 0, "live_chains": 0, "legacy_chains": 0, "archived_chains": 0,
        "dormant_ghost_ratio": 0.0, "avg_pressure_live": 0.0,
        "avg_versions_per_chain": 0.0, "avg_events_per_chain": 0.0,
        "live_waiting_moex": 0, "live_waiting_primary": 0, "live_waiting_secondary": 0,
        "live_waiting_mixed": 0, "live_waiting_corrected": 0, "live_chronic": 0,
        "total_cumulative_delay_days": 0, "avg_stale_live": 0.0, "p90_pressure_live": 0.0,
        "top_10_family_keys_by_pressure": [],
    }
