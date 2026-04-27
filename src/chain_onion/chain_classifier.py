"""
src/chain_onion/chain_classifier.py
-------------------------------------
Step 07 — Chain Classifier Engine.

Populates chain_register_df with:
    current_state               : chain state from STEP02 Section E vocabulary
    portfolio_bucket            : LIVE_OPERATIONAL / LEGACY_BACKLOG / ARCHIVED_HISTORICAL
    stale_days                  : integer days since last_real_activity_date (null if no dates)
    last_real_activity_date     : most recent non-null human event date
    operational_relevance_score : deterministic int [0, 100]
    classifier_reason           : short explanation string
    classifier_priority_hit     : priority level that fired (int 1–12)

Public API
----------
classify_chains(
    chain_register_df, chain_versions_df, chain_events_df, ops_df
) -> pd.DataFrame

Classification priority (evaluated in this exact order)
---------------------------------------------------------
 1  CLOSED_VAO            — terminal positive: VAO/VAOB/FAV/HM
 2  CLOSED_VSO            — terminal positive: VSO
 3  DEAD_AT_SAS_A         — single-version SAS death, no follow-up
 4  VOID_CHAIN            — all versions rejected, no activity > VOID_DAYS
 5  CHRONIC_REF_CHAIN     — CHRONIC_REJECTION_COUNT+ rejected versions, still open
 6  WAITING_CORRECTED_INDICE — prior version rejected, corrected version now blocking
 7  OPEN_WAITING_MOEX     — only MOEX blocking
 8  OPEN_WAITING_PRIMARY_CONSULTANT
 9  OPEN_WAITING_SECONDARY_CONSULTANT
10  OPEN_WAITING_MIXED_CONSULTANTS
11  ABANDONED_CHAIN       — open but no activity > ABANDONED_DAYS
12  UNKNOWN_CHAIN_STATE   — fallback

Forbidden logic (STEP02 Section H + STEP03_5 Section H)
---------------------------------------------------------
- No AI guesses, no silent fallback to CLOSED
- No hard-coded magic numbers (all thresholds are named constants)
- No mutation of input DataFrames
- OPERATIONAL_HORIZON_DATE appears exactly once in this file
"""

from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

# ── importability ──────────────────────────────────────────────────────────
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_LOG = logging.getLogger(__name__)

# ── Primary approver (authoritative source: query_library.py) ─────────────
try:
    from query_library import _is_primary_approver  # type: ignore
    from query_library import _derive_visa_global    # type: ignore
    _LOG.debug("chain_classifier: helpers loaded from query_library")
except ImportError as _ie:
    _LOG.warning(
        "chain_classifier: cannot import from query_library (%s) — using inline fallbacks", _ie
    )
    _PRIMARY_APPROVER_KEYWORDS_FALLBACK = [
        "TERRELL", "EGIS", "BET SPK", "BET ASC", "BET EV",
        "BET FACADES", "ARCHI MOX", "MOEX",
    ]

    def _is_primary_approver(name: str) -> bool:  # type: ignore[misc]
        u = str(name).upper()
        return any(kw in u for kw in _PRIMARY_APPROVER_KEYWORDS_FALLBACK)

    def _derive_visa_global(group: pd.DataFrame) -> Optional[str]:  # type: ignore[misc]
        moex = group[group["step_type"] == "MOEX"]
        if not moex.empty:
            m = moex.iloc[0]
            if bool(m.get("is_completed", False)):
                status = str(m.get("status_clean", "") or "").strip().upper()
                scope  = str(m.get("status_scope",  "") or "").strip().upper()
                if scope == "SAS":
                    return None
                if status:
                    return status
        sas = group[group["step_type"] == "SAS"]
        if not sas.empty:
            s = sas.iloc[0]
            if bool(s.get("is_completed", False)):
                if str(s.get("status_clean", "") or "").strip().upper() == "REF":
                    return "SAS REF"
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Threshold constants — all classification thresholds must use these; no magic
# numbers may appear in classification logic.
# ─────────────────────────────────────────────────────────────────────────────

VOID_DAYS: int = 180
ABANDONED_DAYS: int = 270
CHRONIC_REJECTION_COUNT: int = 3
DEAD_AT_SAS_A_INACTIVITY_DAYS: int = 30

# Operational horizon: chains with all activity before this date are LEGACY_BACKLOG.
# Appears exactly once in this file (STEP03_5 Section H.2).
OPERATIONAL_HORIZON_DATE: date = date(2025, 9, 1)

# Terminal states → always ARCHIVED_HISTORICAL bucket (STEP03_5 Section I.2)
ARCHIVED_TERMINAL_STATES: frozenset = frozenset({
    "CLOSED_VAO",
    "CLOSED_VSO",
    "VOID_CHAIN",
    "DEAD_AT_SAS_A",
})

# Approval-family statuses that produce CLOSED_VAO (STEP02 Section E)
_VAO_FAMILY_STATUSES: frozenset = frozenset({"VAO", "VAOB", "FAV", "HM"})

# New columns added by this module to chain_register_df
_NEW_COLS: list[str] = [
    "current_state",
    "portfolio_bucket",
    "stale_days",
    "last_real_activity_date",
    "operational_relevance_score",
    "classifier_reason",
    "classifier_priority_hit",
]


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_bool_series(s: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False).astype(bool)
    return (
        s.map({"True": True, "False": False, True: True, False: False})
        .fillna(False)
        .astype(bool)
    )


def _get_data_date(ops_df: pd.DataFrame) -> Optional[pd.Timestamp]:
    """Extract data_date from ops_df. Returns None if unavailable."""
    if ops_df is None or ops_df.empty or "data_date" not in ops_df.columns:
        _LOG.warning("chain_classifier: data_date column not in ops_df — stale_days will be null")
        return None
    vals = ops_df["data_date"].dropna()
    if vals.empty:
        _LOG.warning("chain_classifier: data_date column is all-null — stale_days will be null")
        return None
    raw = vals.iloc[0]
    ts = pd.Timestamp(raw) if pd.notna(raw) else None
    if ts is None:
        _LOG.warning("chain_classifier: data_date parse failed — stale_days will be null")
    return ts


def _compute_version_final_status(ops_df: pd.DataFrame) -> dict[str, Optional[str]]:
    """
    Apply _derive_visa_global to each version_key group in ops_df.
    Returns dict: version_key -> Optional[str]  (e.g. "VAO", "SAS REF", None)
    """
    result: dict[str, Optional[str]] = {}
    if ops_df is None or ops_df.empty or "version_key" not in ops_df.columns:
        return result
    for vk, group in ops_df.groupby("version_key", sort=False):
        result[str(vk)] = _derive_visa_global(group)
    return result


def _compute_last_real_activity_dates(
    chain_events_df: pd.DataFrame,
) -> dict[str, Optional[pd.Timestamp]]:
    """
    Per-family maximum event_date, excluding SYSTEM/DEBUG events and null dates.

    "Real activity" = any human workflow event (OPS or EFFECTIVE source).
    DEBUG (SYSTEM lifecycle markers) are excluded per task spec.
    """
    if chain_events_df is None or chain_events_df.empty:
        return {}

    df = chain_events_df.copy()

    # Exclude DEBUG/SYSTEM events
    if "source" in df.columns:
        df = df[df["source"].str.upper() != "DEBUG"]
    elif "actor_type" in df.columns:
        df = df[df["actor_type"].str.upper() != "SYSTEM"]

    # Only non-null dates
    df = df[df["event_date"].notna()]

    if df.empty:
        return {}

    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df[df["event_date"].notna()]

    result: dict[str, Optional[pd.Timestamp]] = {}
    for fk, grp in df.groupby("family_key", sort=False):
        max_date = grp["event_date"].max()
        result[str(fk)] = max_date if pd.notna(max_date) else None
    return result


def _compute_blocker_profile(
    ops_df: pd.DataFrame,
    latest_vk_set: set[str],
) -> dict[str, dict[str, bool]]:
    """
    For each family with blocking rows in its latest version, compute:
        has_moex_blocking      : bool
        has_primary_blocking   : bool
        has_secondary_blocking : bool
        has_sas_blocking       : bool

    Returns dict: family_key -> profile_dict
    """
    profile: dict[str, dict[str, bool]] = {}
    if ops_df is None or ops_df.empty:
        return profile

    df = ops_df.copy()
    for col in ("is_blocking",):
        if col in df.columns:
            df[col] = _normalize_bool_series(df[col])
        else:
            df[col] = False

    blocking = df[df["is_blocking"] & df["version_key"].isin(latest_vk_set)].copy()
    if blocking.empty:
        return profile

    step_upper = blocking["step_type"].fillna("").astype(str).str.upper()
    actor = blocking["actor_clean"].fillna("").astype(str)

    blocking = blocking.assign(
        _step_upper=step_upper,
        _is_moex=(step_upper == "MOEX"),
        _is_sas=(step_upper == "SAS"),
        _is_primary=(step_upper == "CONSULTANT") & actor.apply(_is_primary_approver),
        _is_secondary=(step_upper == "CONSULTANT") & ~actor.apply(_is_primary_approver),
    )

    for fk, grp in blocking.groupby("family_key", sort=False):
        profile[str(fk)] = {
            "has_moex_blocking":      bool(grp["_is_moex"].any()),
            "has_primary_blocking":   bool(grp["_is_primary"].any()),
            "has_secondary_blocking": bool(grp["_is_secondary"].any()),
            "has_sas_blocking":       bool(grp["_is_sas"].any()),
        }
    return profile


def _compute_family_version_facts(
    chain_versions_df: pd.DataFrame,
    version_final_status: dict[str, Optional[str]],
    latest_vk_by_family: dict[str, str],
) -> pd.DataFrame:
    """
    Aggregate per-family facts from chain_versions_df + version_final_status.

    Returns DataFrame with columns:
        family_key
        count_rejected_versions  : versions with requires_new_cycle OR SAS REF
        any_version_approved     : any version has a positive final status
        non_latest_requires_cycle: any non-latest version requires a new cycle
    """
    if chain_versions_df is None or chain_versions_df.empty:
        return pd.DataFrame(columns=[
            "family_key", "count_rejected_versions",
            "any_version_approved", "non_latest_requires_cycle",
        ])

    cv = chain_versions_df.copy()
    if "requires_new_cycle_flag" in cv.columns:
        cv["requires_new_cycle_flag"] = _normalize_bool_series(cv["requires_new_cycle_flag"])
    else:
        cv["requires_new_cycle_flag"] = False

    # Map final status per version
    cv["_vfinal"] = cv["version_key"].map(version_final_status)

    # Rejected = requires_new_cycle OR SAS REF
    cv["_is_rejected"] = (
        cv["requires_new_cycle_flag"] |
        (cv["_vfinal"].fillna("") == "SAS REF")
    )

    # Approved = final status in positive set
    _approved = _VAO_FAMILY_STATUSES | {"VSO"}
    cv["_is_approved"] = cv["_vfinal"].fillna("").isin(_approved)

    # Non-latest version requires cycle
    cv["_is_latest"] = cv.apply(
        lambda r: str(r["version_key"]) == latest_vk_by_family.get(str(r["family_key"]), ""),
        axis=1,
    )
    cv["_non_latest_requires_cycle"] = (~cv["_is_latest"]) & cv["requires_new_cycle_flag"]

    agg = (
        cv.groupby("family_key", sort=False)
        .agg(
            count_rejected_versions=("_is_rejected", "sum"),
            any_version_approved=("_is_approved", "any"),
            non_latest_requires_cycle=("_non_latest_requires_cycle", "any"),
        )
        .reset_index()
    )
    agg["count_rejected_versions"] = agg["count_rejected_versions"].astype(int)
    return agg


# ─────────────────────────────────────────────────────────────────────────────
# Per-family classification
# ─────────────────────────────────────────────────────────────────────────────

def _classify_one_family(
    fk: str,
    total_versions: int,
    latest_indice: str,
    latest_vk_final: Optional[str],
    current_blocking_actor_count: int,
    count_rejected_versions: int,
    any_version_approved: bool,
    non_latest_requires_cycle: bool,
    blocker_profile: dict[str, bool],
    last_real_activity_date: Optional[pd.Timestamp],
    latest_submission_date: Optional[pd.Timestamp],
    data_date: Optional[pd.Timestamp],
) -> tuple[str, str, int]:
    """
    Classify one family. Returns (state, reason, priority_hit).

    Evaluates priorities 1–12 in order; returns on first match.
    Never returns (None, ...) — falls through to UNKNOWN_CHAIN_STATE at worst.
    """
    has_blocking = current_blocking_actor_count > 0

    # ── PRIORITY 1: CLOSED_VAO ────────────────────────────────────────────
    if not has_blocking and latest_vk_final in _VAO_FAMILY_STATUSES:
        return ("CLOSED_VAO", f"latest status {latest_vk_final}", 1)

    # ── PRIORITY 2: CLOSED_VSO ────────────────────────────────────────────
    if not has_blocking and latest_vk_final == "VSO":
        return ("CLOSED_VSO", "latest status VSO", 2)

    # ── PRIORITY 3: DEAD_AT_SAS_A ─────────────────────────────────────────
    # Single version, first indice, SAS REF, no blocking, inactivity > threshold
    if (
        total_versions == 1
        and str(latest_indice).strip().upper() == "A"
        and latest_vk_final == "SAS REF"
        and not has_blocking
    ):
        if data_date is not None and last_real_activity_date is not None:
            inactivity = (data_date - last_real_activity_date).days
            if inactivity >= DEAD_AT_SAS_A_INACTIVITY_DAYS:
                return (
                    "DEAD_AT_SAS_A",
                    f"single indice A SAS REF, {inactivity} days inactive",
                    3,
                )
        elif data_date is None:
            # Cannot verify threshold without data_date — apply if inactivity unknowable
            return ("DEAD_AT_SAS_A", "single indice A SAS REF (data_date unavailable)", 3)

    # ── PRIORITY 4: VOID_CHAIN ────────────────────────────────────────────
    # All versions rejected, no approval ever, no active evaluation, stale enough
    if (
        not has_blocking
        and count_rejected_versions == total_versions
        and total_versions >= 1
        and not any_version_approved
    ):
        stale_enough = False
        if data_date is not None:
            ref_date = last_real_activity_date or latest_submission_date
            if ref_date is not None:
                stale_days_void = (data_date - ref_date).days
                stale_enough = stale_days_void >= VOID_DAYS
        if stale_enough:
            return (
                "VOID_CHAIN",
                f"all {total_versions} version(s) rejected, {stale_days_void} days since last activity",
                4,
            )

    # ── PRIORITY 5: CHRONIC_REF_CHAIN ─────────────────────────────────────
    # CHRONIC_REJECTION_COUNT+ rejection cycles, still open
    if count_rejected_versions >= CHRONIC_REJECTION_COUNT and not has_blocking:
        # Technically still "open" but no blocking — check it's not already closed
        if latest_vk_final not in (_VAO_FAMILY_STATUSES | {"VSO"}):
            return (
                "CHRONIC_REF_CHAIN",
                f"{count_rejected_versions} rejection cycles detected",
                5,
            )
    if count_rejected_versions >= CHRONIC_REJECTION_COUNT and has_blocking:
        return (
            "CHRONIC_REF_CHAIN",
            f"{count_rejected_versions} rejection cycles detected",
            5,
        )

    # ── PRIORITY 6: WAITING_CORRECTED_INDICE ──────────────────────────────
    # An older version required a new cycle AND the latest version is now blocking
    if non_latest_requires_cycle and has_blocking:
        return ("WAITING_CORRECTED_INDICE", "prior version rejected; corrected version blocking", 6)

    # ── From here: chain must have blocking rows to be in an active-wait state
    if has_blocking:
        has_moex = blocker_profile.get("has_moex_blocking", False)
        has_prim = blocker_profile.get("has_primary_blocking", False)
        has_sec  = blocker_profile.get("has_secondary_blocking", False)

        # ── PRIORITY 7: OPEN_WAITING_MOEX ─────────────────────────────────
        if has_moex and not has_prim and not has_sec:
            return ("OPEN_WAITING_MOEX", "only MOEX blocking", 7)

        # ── PRIORITY 8: OPEN_WAITING_PRIMARY_CONSULTANT ───────────────────
        if has_prim and not has_sec and not has_moex:
            return ("OPEN_WAITING_PRIMARY_CONSULTANT", "blocking primary consultants only", 8)

        # ── PRIORITY 9: OPEN_WAITING_SECONDARY_CONSULTANT ─────────────────
        if has_sec and not has_prim and not has_moex:
            return ("OPEN_WAITING_SECONDARY_CONSULTANT", "blocking secondary consultants only", 9)

        # ── PRIORITY 10: OPEN_WAITING_MIXED_CONSULTANTS ───────────────────
        # Mixed = (primary+secondary) or (MOEX+consultants) or any other combo
        return ("OPEN_WAITING_MIXED_CONSULTANTS", "mixed blocking actors", 10)

    # ── PRIORITY 11: ABANDONED_CHAIN ──────────────────────────────────────
    # No blocking but also no real activity for a long time
    if data_date is not None and last_real_activity_date is not None:
        inactivity = (data_date - last_real_activity_date).days
        if inactivity >= ABANDONED_DAYS:
            return (
                "ABANDONED_CHAIN",
                f"no activity {inactivity} days",
                11,
            )

    # ── PRIORITY 12: UNKNOWN_CHAIN_STATE ──────────────────────────────────
    _LOG.warning(
        "chain_classifier: UNKNOWN_CHAIN_STATE for family_key=%s — "
        "blocking=%s latest_vfinal=%s total_versions=%d rejected=%d",
        fk, has_blocking, latest_vk_final, total_versions, count_rejected_versions,
    )
    return (
        "UNKNOWN_CHAIN_STATE",
        f"no rule matched (blocking={has_blocking}, vfinal={latest_vk_final})",
        12,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio bucket + scoring
# ─────────────────────────────────────────────────────────────────────────────

def _assign_portfolio_bucket(
    state: str,
    last_activity: Optional[pd.Timestamp],
    latest_submission: Optional[pd.Timestamp],
    horizon: pd.Timestamp,
) -> tuple[str, bool]:
    """
    Returns (bucket, was_corrected_to_archived).
    was_corrected_to_archived is True when a forbidden combo was auto-corrected.
    """
    # Priority 1: terminal states → always ARCHIVED
    if state in ARCHIVED_TERMINAL_STATES:
        return ("ARCHIVED_HISTORICAL", False)

    # Priority 2: any post-horizon activity → LIVE_OPERATIONAL
    ref_activity = last_activity or latest_submission
    if ref_activity is not None and ref_activity >= horizon:
        return ("LIVE_OPERATIONAL", False)

    # Priority 3: everything else → LEGACY_BACKLOG (including null dates)
    return ("LEGACY_BACKLOG", False)


def _compute_score(
    bucket: str,
    state: str,
    stale_days: Optional[int],
    current_blocking_actor_count: int,
    waiting_primary_flag: bool,
    waiting_secondary_flag: bool,
    total_versions: int,
) -> int:
    """Deterministic operational_relevance_score in [0, 100] per STEP03_5 Section D."""
    if bucket == "ARCHIVED_HISTORICAL":
        return 0

    if bucket == "LEGACY_BACKLOG":
        score = 10
        if stale_days is not None:
            if stale_days < 180:
                score += 15
            elif stale_days < 365:
                score += 5
        if total_versions >= 3:
            score += 5
        return max(0, min(30, score))

    # LIVE_OPERATIONAL
    score = 50

    if current_blocking_actor_count >= 1:
        score += 20

    if stale_days is not None:
        if stale_days <= 7:
            score += 20
        elif stale_days <= 14:
            score += 15
        elif stale_days <= 30:
            score += 10
        elif stale_days <= 60:
            score += 5

    if waiting_primary_flag:
        score += 5
    if waiting_secondary_flag:
        score += 2

    if state == "CHRONIC_REF_CHAIN":
        score += 5
    if state == "ABANDONED_CHAIN":
        score -= 10

    return max(1, min(100, score))


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def classify_chains(
    chain_register_df: pd.DataFrame,
    chain_versions_df: pd.DataFrame,
    chain_events_df: pd.DataFrame,
    ops_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Classify every family in chain_register_df and populate backlog fields.

    Parameters
    ----------
    chain_register_df
        Output of build_chain_register(). One row per family_key.
        Must have: family_key, total_versions, latest_indice, latest_version_key,
                   latest_submission_date, current_blocking_actor_count,
                   waiting_primary_flag, waiting_secondary_flag.
    chain_versions_df
        Output of build_chain_versions(). One row per version_key.
        Must have: family_key, version_key, requires_new_cycle_flag.
    chain_events_df
        Output of build_chain_events(). One row per event.
        Must have: family_key, event_date, source.
    ops_df
        GED_OPERATIONS as returned by load_chain_sources().
        Must have: version_key, step_type, actor_clean, is_blocking,
                   is_completed, status_clean, data_date.

    Returns
    -------
    pd.DataFrame
        chain_register_df enriched with the columns in _NEW_COLS.
        Input DataFrame is NOT mutated.
    """
    if chain_register_df is None or chain_register_df.empty:
        _LOG.warning("classify_chains: chain_register_df is empty — nothing to classify")
        empty = pd.DataFrame(columns=list(chain_register_df.columns) + _NEW_COLS) if chain_register_df is not None else pd.DataFrame(columns=_NEW_COLS)
        return empty

    # ── Step 0: defensive copy ─────────────────────────────────────────────
    reg = chain_register_df.copy()

    # ── Step 1: data_date ──────────────────────────────────────────────────
    data_date_ts = _get_data_date(ops_df)

    # ── Step 2: version_final_status per version_key ──────────────────────
    version_final_status = _compute_version_final_status(ops_df)

    # ── Step 3: latest version_key per family (for non-latest cycle check) ─
    latest_vk_by_family: dict[str, str] = dict(
        zip(reg["family_key"].astype(str), reg["latest_version_key"].fillna("").astype(str))
    )

    # ── Step 4: per-family version facts ──────────────────────────────────
    version_facts = _compute_family_version_facts(
        chain_versions_df, version_final_status, latest_vk_by_family
    )

    # ── Step 5: blocker profile per family (MOEX / primary / secondary) ───
    latest_vk_set = set(latest_vk_by_family.values()) - {""}
    blocker_profile_by_family = _compute_blocker_profile(ops_df, latest_vk_set)

    # ── Step 6: last_real_activity_date per family ─────────────────────────
    last_activity_map = _compute_last_real_activity_dates(chain_events_df)

    # ── Step 7: merge version_facts into reg ──────────────────────────────
    reg = reg.merge(version_facts, on="family_key", how="left")
    reg["count_rejected_versions"] = reg["count_rejected_versions"].fillna(0).astype(int)
    reg["any_version_approved"] = reg["any_version_approved"].fillna(False).astype(bool)
    reg["non_latest_requires_cycle"] = reg["non_latest_requires_cycle"].fillna(False).astype(bool)

    # ── Step 8: normalize bool columns from chain_register ────────────────
    for col in ("waiting_primary_flag", "waiting_secondary_flag"):
        if col in reg.columns:
            reg[col] = _normalize_bool_series(reg[col])
        else:
            reg[col] = False

    # ── Step 9: classify each family ──────────────────────────────────────
    horizon_ts = pd.Timestamp(OPERATIONAL_HORIZON_DATE)
    states:     list[str] = []
    reasons:    list[str] = []
    priorities: list[int] = []
    buckets:    list[str] = []
    scores:     list[int] = []
    stale_days_list:     list[Optional[int]] = []
    last_activity_list:  list[Optional[pd.Timestamp]] = []

    for _, row in reg.iterrows():
        fk = str(row["family_key"])

        latest_vk_final = version_final_status.get(
            str(row.get("latest_version_key", "")), None
        )
        last_activity    = last_activity_map.get(fk)
        latest_submission = pd.Timestamp(row["latest_submission_date"]) if pd.notna(row.get("latest_submission_date")) else None

        # stale_days
        sd: Optional[int] = None
        if data_date_ts is not None and last_activity is not None:
            raw_sd = (data_date_ts - last_activity).days
            if raw_sd < 0:
                _LOG.warning(
                    "chain_classifier: negative stale_days (%d) for family_key=%s — clamped to 0",
                    raw_sd, fk,
                )
                raw_sd = 0
            sd = raw_sd

        # Classify
        state, reason, priority = _classify_one_family(
            fk=fk,
            total_versions=int(row.get("total_versions", 1)),
            latest_indice=str(row.get("latest_indice", "")),
            latest_vk_final=latest_vk_final,
            current_blocking_actor_count=int(row.get("current_blocking_actor_count", 0)),
            count_rejected_versions=int(row.get("count_rejected_versions", 0)),
            any_version_approved=bool(row.get("any_version_approved", False)),
            non_latest_requires_cycle=bool(row.get("non_latest_requires_cycle", False)),
            blocker_profile=blocker_profile_by_family.get(fk, {}),
            last_real_activity_date=last_activity,
            latest_submission_date=latest_submission,
            data_date=data_date_ts,
        )

        # Portfolio bucket
        bucket, _ = _assign_portfolio_bucket(
            state, last_activity, latest_submission, horizon_ts
        )

        # Validate forbidden state × bucket combos (STEP03_5 Section G.1)
        if state in ARCHIVED_TERMINAL_STATES and bucket != "ARCHIVED_HISTORICAL":
            _LOG.warning(
                "chain_classifier: forbidden state×bucket for family_key=%s "
                "(%s + %s) — corrected to ARCHIVED_HISTORICAL",
                fk, state, bucket,
            )
            bucket = "ARCHIVED_HISTORICAL"

        # Score
        score = _compute_score(
            bucket=bucket,
            state=state,
            stale_days=sd,
            current_blocking_actor_count=int(row.get("current_blocking_actor_count", 0)),
            waiting_primary_flag=bool(row.get("waiting_primary_flag", False)),
            waiting_secondary_flag=bool(row.get("waiting_secondary_flag", False)),
            total_versions=int(row.get("total_versions", 1)),
        )

        states.append(state)
        reasons.append(reason)
        priorities.append(priority)
        buckets.append(bucket)
        scores.append(score)
        stale_days_list.append(sd)
        last_activity_list.append(last_activity)

    reg["current_state"]               = states
    reg["portfolio_bucket"]            = buckets
    reg["stale_days"]                  = stale_days_list
    reg["last_real_activity_date"]     = last_activity_list
    reg["operational_relevance_score"] = scores
    reg["classifier_reason"]           = reasons
    reg["classifier_priority_hit"]     = priorities

    # Drop intermediate columns added by merge (not part of contract)
    for col in ("count_rejected_versions", "any_version_approved", "non_latest_requires_cycle"):
        if col in reg.columns:
            reg = reg.drop(columns=[col])

    # ── Summary log ───────────────────────────────────────────────────────
    state_counts = reg["current_state"].value_counts().to_dict()
    bucket_counts = reg["portfolio_bucket"].value_counts().to_dict()
    unknown_count = state_counts.get("UNKNOWN_CHAIN_STATE", 0)
    if unknown_count:
        _LOG.warning(
            "chain_classifier: %d families classified as UNKNOWN_CHAIN_STATE", unknown_count
        )
    _LOG.info(
        "classify_chains: DONE — %d families | states=%s | buckets=%s | "
        "avg_score=%.1f | null_activity=%d",
        len(reg),
        state_counts,
        bucket_counts,
        reg["operational_relevance_score"].mean() if len(reg) > 0 else 0.0,
        int(reg["last_real_activity_date"].isna().sum()),
    )

    return reg.reset_index(drop=True)
