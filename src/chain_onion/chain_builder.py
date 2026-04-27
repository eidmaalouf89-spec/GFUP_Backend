"""
src/chain_onion/chain_builder.py
----------------------------------
Step 06 — Timeline Event Engine.

Produces chain_events_df: one normalized chronological event stream for
every chain. This is the forensic backbone for Steps 07–11.

No chain classification. No onion blame scoring.

Public API
----------
build_chain_events(ops_df, debug_df=None, effective_df=None) -> pd.DataFrame

Event sources
-------------
OPS       : GED_OPERATIONS — one event per ops row (source_priority=1)
EFFECTIVE : effective_responses — EFFECTIVE_OVERRIDE rows only (priority=2)
DEBUG     : DEBUG_TRACE — INSTANCE_CREATED / INSTANCE_SUPERSEDED (priority=3)

Identity model (STEP02 Section A)
----------------------------------
FAMILY_KEY   = str(numero)
VERSION_KEY  = "{numero}_{indice}"
INSTANCE_KEY = version_key + "_main"  (ops/effective; DEBUG preserves real key)

Chronological ordering within a family
---------------------------------------
1. event_date ASC  (NaT rows sort last)
2. source_priority ASC  (OPS before EFFECTIVE before DEBUG)
3. version_key ASC
4. original stable index

actor_type vocabulary (deterministic, from step_type + _is_primary_approver)
-----------------------------------------------------------------------------
MOEX / SAS / PRIMARY_CONSULTANT / SECONDARY_CONSULTANT / CONTRACTOR / SYSTEM / UNKNOWN

step_type vocabulary (semantic)
--------------------------------
SUBMITTAL / RESPONSE / BLOCKING_WAIT / CYCLE_REQUIRED /
EFFECTIVE_OVERRIDE / INSTANCE_SUPERSEDED / INSTANCE_CREATED / UNKNOWN

issue_signal vocabulary (lightweight flag for Steps 08–11)
-----------------------------------------------------------
NONE / DELAY / REJECTION / CHURN / DORMANCY / CONTRADICTION / MULTI

Primary vs Secondary uses exclusively _is_primary_approver() from query_library.
No custom keyword list is defined here.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# ── ensure src/ is importable ──────────────────────────────────────────────
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_LOG = logging.getLogger(__name__)

# ── Primary approver import (authoritative source: query_library.py) ───────
try:
    from query_library import _is_primary_approver  # type: ignore
    _LOG.debug("chain_builder: _is_primary_approver loaded from query_library")
except ImportError as _ie:
    _LOG.warning(
        "chain_builder: cannot import _is_primary_approver from query_library (%s) "
        "— using inline fallback that mirrors repo definition exactly",
        _ie,
    )
    _PRIMARY_APPROVER_KEYWORDS_FALLBACK = [
        "TERRELL", "EGIS", "BET SPK", "BET ASC", "BET EV",
        "BET FACADES", "ARCHI MOX", "MOEX",
    ]

    def _is_primary_approver(name: str) -> bool:  # type: ignore[misc]
        u = str(name).upper()
        return any(kw in u for kw in _PRIMARY_APPROVER_KEYWORDS_FALLBACK)


# ── Source vocabulary ──────────────────────────────────────────────────────
SRC_OPS       = "OPS"
SRC_EFFECTIVE = "EFFECTIVE"
SRC_DEBUG     = "DEBUG"

SOURCE_PRIORITY: dict[str, int] = {
    SRC_OPS: 1,
    SRC_EFFECTIVE: 2,
    SRC_DEBUG: 3,
}

# ── Status sets ────────────────────────────────────────────────────────────
_REJECTION_STATUSES = frozenset({"REF", "DEF"})

# ── Output column order (contract) ────────────────────────────────────────
_CHAIN_EVENTS_COLS: list[str] = [
    "family_key",
    "version_key",
    "instance_key",
    "event_seq",
    "event_date",
    "source",
    "source_priority",
    "actor",
    "actor_type",
    "step_type",
    "status",
    "is_blocking",
    "is_completed",
    "requires_new_cycle",
    "delay_contribution_days",
    "issue_signal",
    "raw_reference",
    "notes",
]


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_bool_series(s: pd.Series) -> pd.Series:
    """Coerce string 'True'/'False' or native bool to dtype=bool, NaN → False."""
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False).astype(bool)
    return (
        s.map({"True": True, "False": False, True: True, False: False})
        .fillna(False)
        .astype(bool)
    )


def _safe_str_series(s: pd.Series, default: str = "UNKNOWN") -> pd.Series:
    """Return string series with NaN/empty replaced by default."""
    result = s.fillna("").astype(str).str.strip()
    return result.where(result != "", default)


def _map_actor_type(step_type_upper: str, actor_name: str) -> str:
    """Deterministic actor_type from GED step_type + primary approver check."""
    if step_type_upper == "MOEX":
        return "MOEX"
    if step_type_upper == "SAS":
        return "SAS"
    if step_type_upper == "OPEN_DOC":
        return "CONTRACTOR"
    if step_type_upper == "CONSULTANT":
        return (
            "PRIMARY_CONSULTANT"
            if _is_primary_approver(actor_name)
            else "SECONDARY_CONSULTANT"
        )
    return "UNKNOWN"


def _map_step_type(
    step_type_upper: str,
    is_blocking: bool,
    is_completed: bool,
    requires_new_cycle: bool,
) -> str:
    """Map GED step_type to semantic Step 06 step_type."""
    if step_type_upper == "OPEN_DOC":
        return "SUBMITTAL"
    if is_completed and requires_new_cycle:
        return "CYCLE_REQUIRED"
    if is_completed:
        return "RESPONSE"
    if is_blocking:
        return "BLOCKING_WAIT"
    return "RESPONSE"


def _map_issue_signal(
    status_upper: str,
    is_blocking: bool,
    requires_new_cycle: bool,
    effective_source: str = "GED",
) -> str:
    """
    Single lightweight issue flag (NONE/DELAY/REJECTION/CHURN/CONTRADICTION/MULTI).
    No scoring — just detection for Steps 08–11.
    """
    signals: list[str] = []
    if "CONFLICT" in str(effective_source).upper():
        signals.append("CONTRADICTION")
    if status_upper in _REJECTION_STATUSES:
        signals.append("REJECTION")
    if requires_new_cycle:
        signals.append("CHURN")
    if is_blocking:
        signals.append("DELAY")
    if len(signals) >= 2:
        return "MULTI"
    return signals[0] if signals else "NONE"


def _assign_event_seq(df: pd.DataFrame) -> pd.Series:
    """
    Assign event_seq 1..N gapless within each family_key.
    Assumes df is already sorted in the desired chronological order.
    """
    return df.groupby("family_key", sort=False).cumcount() + 1


def _sort_events(df: pd.DataFrame) -> pd.DataFrame:
    """
    Chronological sort within each family:
      1. event_date ASC  (NaT last via has_date sentinel)
      2. source_priority ASC  (OPS=1, EFFECTIVE=2, DEBUG=3)
      3. version_key ASC
      4. stable row index (reset_index preserves original concat order)
    """
    df = df.copy()
    # Sentinel: 0 = has date (sort first), 1 = NaT (sort last)
    df["_nat_last"] = df["event_date"].isna().astype(int)
    sorted_df = df.sort_values(
        ["family_key", "_nat_last", "event_date", "source_priority", "version_key"],
        ascending=[True, True, True, True, True],
        kind="stable",
    ).drop(columns=["_nat_last"])
    return sorted_df


# ─────────────────────────────────────────────────────────────────────────────
# Per-source event builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_ops_events(ops_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build one event row per GED_OPERATIONS row.

    event_date: OPEN_DOC → submittal_date; all other steps → response_date.
    instance_key: version_key + "_main"  (DEBUG_TRACE not joined here).
    """
    if ops_df is None or ops_df.empty:
        return pd.DataFrame(columns=[c for c in _CHAIN_EVENTS_COLS if c != "event_seq"])

    df = ops_df.copy()

    # ── Bool normalization ─────────────────────────────────────────────────
    for col in ("is_blocking", "is_completed", "requires_new_cycle"):
        if col in df.columns:
            df[col] = _normalize_bool_series(df[col])
        else:
            df[col] = False

    is_blocking      = df["is_blocking"]
    is_completed     = df["is_completed"]
    requires_new_cycle = df["requires_new_cycle"]

    # ── Dates ──────────────────────────────────────────────────────────────
    submittal = pd.to_datetime(df.get("submittal_date", pd.NaT), errors="coerce")
    response  = pd.to_datetime(df.get("response_date",  pd.NaT), errors="coerce")

    step_type_raw = (
        df.get("step_type", pd.Series("", index=df.index))
        .fillna("").astype(str).str.strip().str.upper()
    )
    is_open_doc = step_type_raw == "OPEN_DOC"

    # OPEN_DOC → submittal_date; others → response_date
    event_date = submittal.where(is_open_doc, response)

    # ── Actor ──────────────────────────────────────────────────────────────
    actor = _safe_str_series(
        df.get("actor_clean", pd.Series("", index=df.index)), "UNKNOWN"
    )

    # ── actor_type (vectorized via list comprehension — 32k rows, negligible) ──
    actor_type = [
        _map_actor_type(st, ac)
        for st, ac in zip(step_type_raw, actor)
    ]

    # ── semantic step_type ─────────────────────────────────────────────────
    semantic_step_type = [
        _map_step_type(st, bl, co, cy)
        for st, bl, co, cy in zip(
            step_type_raw, is_blocking, is_completed, requires_new_cycle
        )
    ]

    # ── status ────────────────────────────────────────────────────────────
    status_raw = (
        df.get("status_clean", pd.Series("", index=df.index))
        .fillna("").astype(str).str.strip()
    )
    status_out = status_raw.where(status_raw != "", None)

    # ── delay_contribution_days ────────────────────────────────────────────
    delay_days = (
        pd.to_numeric(
            df.get("delay_contribution_days", pd.Series(0, index=df.index)),
            errors="coerce",
        )
        .fillna(0)
        .astype(int)
    )

    # ── identity keys ──────────────────────────────────────────────────────
    family_key  = df.get("family_key",  pd.Series("", index=df.index)).fillna("").astype(str)
    version_key = df.get("version_key", pd.Series("", index=df.index)).fillna("").astype(str)
    instance_key = version_key + "_main"

    # ── raw_reference ──────────────────────────────────────────────────────
    step_order = (
        df.get("step_order", pd.Series("", index=df.index))
        .fillna("").astype(str)
    )
    raw_reference = "ops:" + version_key + ":" + step_order

    # ── issue_signal ───────────────────────────────────────────────────────
    status_upper = status_raw.str.upper()
    issue_signal = [
        _map_issue_signal(su, bl, cy)
        for su, bl, cy in zip(status_upper, is_blocking, requires_new_cycle)
    ]

    # ── notes ──────────────────────────────────────────────────────────────
    notes = pd.Series(None, index=df.index, dtype=object)
    notes[requires_new_cycle] = "SAS rejection requires new cycle"

    return pd.DataFrame(
        {
            "family_key":            family_key.values,
            "version_key":           version_key.values,
            "instance_key":          instance_key.values,
            "event_date":            event_date.values,
            "source":                SRC_OPS,
            "source_priority":       SOURCE_PRIORITY[SRC_OPS],
            "actor":                 actor.values,
            "actor_type":            actor_type,
            "step_type":             semantic_step_type,
            "status":                status_out.values,
            "is_blocking":           is_blocking.values,
            "is_completed":          is_completed.values,
            "requires_new_cycle":    requires_new_cycle.values,
            "delay_contribution_days": delay_days.values,
            "issue_signal":          issue_signal,
            "raw_reference":         raw_reference.values,
            "notes":                 notes.values,
        }
    )


def _build_debug_events(debug_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build INSTANCE_CREATED / INSTANCE_SUPERSEDED events from DEBUG_TRACE.

    One event per unique instance_key. event_date = min(raw_date) for that
    instance. instance_role 'SUPERSED*' → INSTANCE_SUPERSEDED; otherwise
    INSTANCE_CREATED.
    """
    if debug_df is None or debug_df.empty:
        return pd.DataFrame(columns=[c for c in _CHAIN_EVENTS_COLS if c != "event_seq"])

    required = {"family_key", "version_key", "instance_key"}
    if not required.issubset(debug_df.columns):
        _LOG.warning(
            "chain_builder._build_debug_events: debug_df missing identity columns — skipping"
        )
        return pd.DataFrame(columns=[c for c in _CHAIN_EVENTS_COLS if c != "event_seq"])

    dc = debug_df.copy()

    # event_date from raw_date (earliest per instance)
    if "raw_date" in dc.columns:
        dc["_raw_date"] = pd.to_datetime(dc["raw_date"], errors="coerce")
    else:
        dc["_raw_date"] = pd.NaT

    grp_cols = ["family_key", "version_key", "instance_key"]
    grp = dc.groupby(grp_cols, sort=False)

    agg = grp["_raw_date"].min().rename("event_date").reset_index()

    if "instance_role" in dc.columns:
        first_role = (
            grp["instance_role"].first().rename("instance_role").reset_index()
        )
        agg = agg.merge(first_role, on=grp_cols, how="left")
    else:
        agg["instance_role"] = ""

    if "instance_resolution_reason" in dc.columns:
        first_reason = (
            grp["instance_resolution_reason"]
            .first()
            .rename("resolution_reason")
            .reset_index()
        )
        agg = agg.merge(first_reason, on=grp_cols, how="left")
    else:
        agg["resolution_reason"] = ""

    # Map semantic step_type
    role_upper = agg["instance_role"].fillna("").astype(str).str.upper()
    is_superseded = role_upper.str.contains("SUPERSED", regex=False)
    step_type_col = is_superseded.map(
        {True: "INSTANCE_SUPERSEDED", False: "INSTANCE_CREATED"}
    )

    # notes from resolution_reason
    reason_col = agg["resolution_reason"].fillna("").astype(str).str.strip()
    notes_col = reason_col.where(reason_col != "", None)

    vk = agg["version_key"].fillna("").astype(str)
    ik = agg["instance_key"].fillna("").astype(str)

    return pd.DataFrame(
        {
            "family_key":            agg["family_key"].fillna("").astype(str).values,
            "version_key":           vk.values,
            "instance_key":          ik.values,
            "event_date":            pd.to_datetime(agg["event_date"], errors="coerce").values,
            "source":                SRC_DEBUG,
            "source_priority":       SOURCE_PRIORITY[SRC_DEBUG],
            "actor":                 "SYSTEM",
            "actor_type":            "SYSTEM",
            "step_type":             step_type_col.values,
            "status":                None,
            "is_blocking":           False,
            "is_completed":          True,
            "requires_new_cycle":    False,
            "delay_contribution_days": 0,
            "issue_signal":          "NONE",
            "raw_reference":         ("debug:" + ik).values,
            "notes":                 notes_col.values,
        }
    )


def _build_effective_events(effective_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build EFFECTIVE_OVERRIDE events for rows where effective_source != 'GED'.

    GED-only rows are skipped (they are fully covered by OPS events).
    GED+REPORT_STATUS / GED+REPORT_COMMENT / GED_CONFLICT_REPORT rows
    generate one supplemental event each.
    """
    if effective_df is None or effective_df.empty:
        return pd.DataFrame(columns=[c for c in _CHAIN_EVENTS_COLS if c != "event_seq"])

    required = {"family_key", "version_key", "effective_source"}
    if not required.issubset(effective_df.columns):
        return pd.DataFrame(columns=[c for c in _CHAIN_EVENTS_COLS if c != "event_seq"])

    eff_src = effective_df["effective_source"].fillna("GED").astype(str)
    override_mask = eff_src.str.upper() != "GED"
    override_df = effective_df[override_mask].copy()

    if override_df.empty:
        return pd.DataFrame(columns=[c for c in _CHAIN_EVENTS_COLS if c != "event_seq"])

    eff_src_override = eff_src[override_mask]

    if "response_date" in override_df.columns:
        event_date = pd.to_datetime(override_df["response_date"], errors="coerce")
    else:
        event_date = pd.Series(pd.NaT, index=override_df.index, dtype="datetime64[ns]")

    actor_col = "actor_clean" if "actor_clean" in override_df.columns else "approver_canonical"
    actor = (
        override_df[actor_col].fillna("UNKNOWN").astype(str).str.strip()
        if actor_col in override_df.columns
        else pd.Series("UNKNOWN", index=override_df.index)
    )

    has_conflict = eff_src_override.str.contains("CONFLICT", case=False, regex=False)
    issue_signal = has_conflict.map({True: "CONTRADICTION", False: "NONE"})

    vk = override_df["version_key"].fillna("").astype(str)

    status_col = (
        override_df.get("status_clean", pd.Series(None, index=override_df.index))
        .where(
            override_df.get("status_clean", pd.Series("", index=override_df.index))
            .fillna("").astype(str).str.strip() != "",
            None,
        )
        if "status_clean" in override_df.columns
        else pd.Series(None, index=override_df.index)
    )

    notes = "Report memory upgrade applied: " + eff_src_override

    result = pd.DataFrame(
        {
            "family_key":            override_df["family_key"].fillna("").astype(str).values,
            "version_key":           vk.values,
            "instance_key":          (vk + "_main").values,
            "event_date":            event_date.values,
            "source":                SRC_EFFECTIVE,
            "source_priority":       SOURCE_PRIORITY[SRC_EFFECTIVE],
            "actor":                 actor.values,
            "actor_type":            "UNKNOWN",
            "step_type":             "EFFECTIVE_OVERRIDE",
            "status":                status_col.values,
            "is_blocking":           False,
            "is_completed":          True,
            "requires_new_cycle":    False,
            "delay_contribution_days": 0,
            "issue_signal":          issue_signal.values,
            "raw_reference":         ("effective:" + vk).values,
            "notes":                 notes.values,
        }
    )
    return result.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_chain_events(
    ops_df: pd.DataFrame,
    debug_df: Optional[pd.DataFrame] = None,
    effective_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Build chain_events_df: one normalized chronological event stream per chain.

    Parameters
    ----------
    ops_df
        GED_OPERATIONS DataFrame as returned by load_chain_sources().
        Must have family_key, version_key, step_type, actor_clean,
        submittal_date, response_date, is_blocking, is_completed,
        requires_new_cycle, delay_contribution_days, status_clean.
    debug_df
        Optional DEBUG_TRACE DataFrame. When provided, generates
        INSTANCE_CREATED / INSTANCE_SUPERSEDED events per unique instance_key.
    effective_df
        Optional effective_responses DataFrame. When provided, generates
        EFFECTIVE_OVERRIDE events for rows where effective_source != 'GED'.

    Returns
    -------
    pd.DataFrame
        One row per lifecycle event, columns per _CHAIN_EVENTS_COLS.
        Sorted chronologically within each family_key.
        event_seq is 1..N gapless per family, no gaps, no duplicates.
    """
    parts: list[pd.DataFrame] = []

    # 1. OPS events — primary backbone
    ops_events = _build_ops_events(ops_df)
    if not ops_events.empty:
        parts.append(ops_events)
        _LOG.info("build_chain_events: OPS events built: %d rows", len(ops_events))

    # 2. EFFECTIVE override events
    if effective_df is not None and not effective_df.empty:
        eff_events = _build_effective_events(effective_df)
        if not eff_events.empty:
            parts.append(eff_events)
            _LOG.info(
                "build_chain_events: EFFECTIVE override events: %d rows", len(eff_events)
            )

    # 3. DEBUG instance events
    if debug_df is not None and not debug_df.empty:
        dbg_events = _build_debug_events(debug_df)
        if not dbg_events.empty:
            parts.append(dbg_events)
            _LOG.info(
                "build_chain_events: DEBUG instance events: %d rows", len(dbg_events)
            )

    if not parts:
        _LOG.warning("build_chain_events: no events produced — returning empty DataFrame")
        return pd.DataFrame(columns=_CHAIN_EVENTS_COLS)

    combined = pd.concat(parts, ignore_index=True)

    # ── Ensure event_date is datetime64 ────────────────────────────────────
    combined["event_date"] = pd.to_datetime(combined["event_date"], errors="coerce")

    # ── Exact deduplication ────────────────────────────────────────────────
    dedup_keys = [
        "family_key", "version_key", "event_date",
        "actor", "step_type", "status", "source",
    ]
    before_dedup = len(combined)
    combined = combined.drop_duplicates(subset=dedup_keys, keep="first").copy()
    after_dedup = len(combined)
    if before_dedup > after_dedup:
        _LOG.info(
            "build_chain_events: dedup removed %d exact duplicates",
            before_dedup - after_dedup,
        )

    # ── Chronological sort ─────────────────────────────────────────────────
    combined = _sort_events(combined)

    # ── Assign event_seq (1..N per family, gapless) ────────────────────────
    combined["event_seq"] = _assign_event_seq(combined)

    # ── Finalize column order ──────────────────────────────────────────────
    result = combined[_CHAIN_EVENTS_COLS].reset_index(drop=True)

    _LOG.info(
        "build_chain_events: DONE — %d total events | %d families | "
        "avg %.1f events/family | max %d events/family | %d NaT dates | "
        "OPS=%d EFFECTIVE=%d DEBUG=%d",
        len(result),
        result["family_key"].nunique(),
        result.groupby("family_key").size().mean() if not result.empty else 0.0,
        result.groupby("family_key").size().max() if not result.empty else 0,
        int(result["event_date"].isna().sum()),
        int((result["source"] == SRC_OPS).sum()),
        int((result["source"] == SRC_EFFECTIVE).sum()),
        int((result["source"] == SRC_DEBUG).sum()),
    )

    return result
