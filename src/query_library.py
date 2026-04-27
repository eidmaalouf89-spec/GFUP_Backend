"""
query_library.py
----------------
Step 9c — Flat GED Query Library

Centralized, read-only query layer for the Flat GED + effective_responses truth model.

All public functions are pure: same inputs → same outputs. No writes, no side effects,
no mutations of ctx DataFrames.

Design:
  flat_ged_ops_df (GED_OPERATIONS) is the structural ground truth.
    → Used for doc counts, document lifecycle, queue engine primitives.
    → Document identity: (numero, indice); doc_key = f"{numero}_{indice}".

  effective_responses_df (composed via build_effective_responses) is the status truth.
    → Used for step metrics, consultant KPIs, status mix, provenance analysis.
    → Document identity: doc_id (UUID, pipeline-session-specific).
    → Reflects report-memory upgrades — a pending step promoted by report memory
      appears as ANSWERED here, not in the raw ops_df.

  flat_ged_doc_meta (optional) supplies pre-computed per-doc fields:
    closure_mode, visa_global, responsible_party, data_date.
    Keys are UUID doc_ids (same as effective_responses_df).

  flat_ged_df (GED_RAW_FLAT, optional) is used only for raw provenance checks.

Identity bridging note:
  flat_ged_ops_df uses (numero, indice); effective_responses_df uses UUID doc_id.
  These two identity systems are NOT automatically bridged here.
  Functions based on flat_ged_ops_df return doc_key = "{numero}_{indice}".
  Functions based on effective_responses_df return doc_id (UUID).
  Callers who need to correlate both can supply the pipeline's id_to_pair mapping
  (from stage_read_flat) separately. Step 10 (UI parity) will formalize this bridge.

Status vocabulary (mirrors effective_responses.py):
  effective_source:  GED | GED+REPORT_STATUS | GED+REPORT_COMMENT |
                     GED_CONFLICT_REPORT | REPORT_ONLY
  date_status_type:  ANSWERED | PENDING_IN_DELAY | PENDING_LATE | NOT_CALLED
  status_clean:      VAO | VSO | FAV | HM | VAOB | REF | DEF | (empty)
  VAOB = VAO (approval-family, per Eid decision 2026-04-24)

References:
  docs/FLAT_GED_CONTRACT.md        — column contracts for GED_OPERATIONS
  docs/FLAT_GED_REPORT_COMPOSITION.md — merge rules and provenance vocabulary
  docs/BACKEND_SEMANTIC_CONTRACT.md   — semantic definitions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

_LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status vocabulary constants
# ---------------------------------------------------------------------------

_APPROVAL_FAMILY   = frozenset({"VAO", "VSO", "FAV", "HM", "VAOB"})
_REJECTION_FAMILY  = frozenset({"REF", "DEF"})
_PENDING_TYPES     = frozenset({"PENDING_IN_DELAY", "PENDING_LATE"})
_ANSWERED_TYPE     = "ANSWERED"
_NOT_CALLED        = "NOT_CALLED"

# Effective source vocabulary (five-value closed set)
EFF_SRC_GED         = "GED"
EFF_SRC_RPT_STATUS  = "GED+REPORT_STATUS"
EFF_SRC_RPT_COMMENT = "GED+REPORT_COMMENT"
EFF_SRC_CONFLICT    = "GED_CONFLICT_REPORT"
EFF_SRC_RPT_ONLY    = "REPORT_ONLY"  # should not appear; logged if found

# Primary approver keywords (mirrors workflow_engine.py)
_PRIMARY_APPROVER_KEYWORDS = [
    "TERRELL", "EGIS", "BET SPK", "BET ASC", "BET EV",
    "BET FACADES", "ARCHI MOX", "MOEX",
]


# ---------------------------------------------------------------------------
# QueryContext
# ---------------------------------------------------------------------------

@dataclass
class QueryContext:
    """
    Lightweight context for the query library.

    flat_ged_ops_df
        GED_OPERATIONS sheet (37 cols). One step per (doc, actor). ACTIVE instances only.
        Document identity: (numero, indice).

    effective_responses_df
        Composed truth from build_effective_responses(). One row per (doc, approver).
        Document identity: doc_id (UUID — pipeline-session-specific).
        Columns include: doc_id, approver_canonical, date_status_type, status_clean,
        date_answered, response_comment, effective_source, report_memory_applied,
        flat_* pass-through columns.

    flat_ged_df
        GED_RAW_FLAT sheet (21 cols, optional). Used only for raw provenance checks.

    flat_ged_doc_meta
        Per-doc metadata dict {doc_id: {visa_global, closure_mode, responsible_party,
        data_date}}. Keys are UUID doc_ids matching effective_responses_df.
    """
    flat_ged_ops_df:        pd.DataFrame
    effective_responses_df: pd.DataFrame
    flat_ged_df:            Optional[pd.DataFrame] = None
    flat_ged_doc_meta:      Optional[dict]         = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_df(ctx: QueryContext, attr: str) -> pd.DataFrame:
    """Return ctx.<attr> or raise clearly if missing or empty."""
    df = getattr(ctx, attr, None)
    if df is None:
        raise ValueError(
            f"QueryContext.{attr} is None — this DataFrame is required. "
            f"Populate it from the pipeline's PipelineState before calling this function."
        )
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"QueryContext.{attr} must be a pandas DataFrame, got {type(df).__name__}.")
    if df.empty:
        raise ValueError(
            f"QueryContext.{attr} is empty — no data available for this query."
        )
    return df


def _ops_steps(ctx: QueryContext) -> pd.DataFrame:
    """
    GED_OPERATIONS rows excluding OPEN_DOC.
    OPEN_DOC is a synthetic anchor (submittal event), not an approval step.
    """
    ops = _require_df(ctx, "flat_ged_ops_df")
    return ops[ops["step_type"] != "OPEN_DOC"].copy()


def _pending_mask(df: pd.DataFrame, col: str = "date_status_type") -> pd.Series:
    """True for rows where date_status_type is PENDING_IN_DELAY or PENDING_LATE."""
    return df[col].isin(_PENDING_TYPES)


def _overdue_mask(df: pd.DataFrame) -> pd.Series:
    """True for rows where date_status_type is PENDING_LATE (past deadline)."""
    return df["date_status_type"] == "PENDING_LATE"


def _approval_family_mask(series: pd.Series) -> pd.Series:
    """True for VAO / VSO / FAV / HM / VAOB. VAOB treated as VAO (approval-family)."""
    return series.str.strip().str.upper().isin(_APPROVAL_FAMILY)


def _rejection_family_mask(series: pd.Series) -> pd.Series:
    """True for REF / DEF."""
    return series.str.strip().str.upper().isin(_REJECTION_FAMILY)


def _is_primary_approver(name: str) -> bool:
    """True if actor name contains any primary approver keyword (case-insensitive)."""
    u = str(name).upper()
    return any(kw in u for kw in _PRIMARY_APPROVER_KEYWORDS)


def _parse_date(val) -> Optional[pd.Timestamp]:
    """Parse any date-like value to pd.Timestamp. Returns pd.NaT on failure."""
    if val is None:
        return pd.NaT
    if isinstance(val, pd.Timestamp):
        return val
    ts = pd.to_datetime(str(val).strip(), errors="coerce")
    return ts if not pd.isna(ts) else pd.NaT


def _get_data_date(ctx: QueryContext) -> Optional[pd.Timestamp]:
    """
    Extract the reference data_date from the context.
    Prefers flat_ged_ops_df.data_date; falls back to effective_responses_df.flat_data_date.
    """
    # From ops_df
    try:
        ops = _require_df(ctx, "flat_ged_ops_df")
        if "data_date" in ops.columns:
            val = ops["data_date"].dropna().iloc[0]
            ts = _parse_date(val)
            if ts is not pd.NaT:
                return ts
    except Exception:
        pass
    # From effective_responses_df
    try:
        eff = _require_df(ctx, "effective_responses_df")
        if "flat_data_date" in eff.columns:
            val = eff["flat_data_date"].dropna().iloc[0]
            ts = _parse_date(val)
            if ts is not pd.NaT:
                return ts
    except Exception:
        pass
    _LOG.warning("_get_data_date: data_date not found in context — date-relative queries may be inaccurate.")
    return None


def _derive_visa_global(group: pd.DataFrame) -> Optional[str]:
    """
    Derive visa_global from a single document's GED_OPERATIONS rows.

    Logic (mirrors stage_read_flat._compute_doc_meta):
      1. MOEX step completed with non-SAS-scoped status → that status is visa_global.
      2. SAS step completed with REF and no MOEX step → "SAS REF".
      3. Otherwise → None (cycle not yet closed or no decisive MOEX vote).
    """
    moex = group[group["step_type"] == "MOEX"]
    if not moex.empty:
        m = moex.iloc[0]
        if bool(m.get("is_completed", False)):
            status = str(m.get("status_clean", "") or "").strip().upper()
            scope  = str(m.get("status_scope",  "") or "").strip().upper()
            if scope == "SAS":
                return None  # SAS-scoped visa does not count as global visa
            if status:
                return status

    sas = group[group["step_type"] == "SAS"]
    if not sas.empty:
        s = sas.iloc[0]
        if bool(s.get("is_completed", False)):
            if str(s.get("status_clean", "") or "").strip().upper() == "REF":
                return "SAS REF"

    return None


def _safe_first(series: pd.Series, default=None):
    """Return first non-null value in series, or default."""
    vals = series.dropna()
    return vals.iloc[0] if not vals.empty else default


def _eff_step_type(eff: pd.DataFrame) -> pd.Series:
    """
    Step type column from effective_responses_df.
    Uses flat_step_type pass-through if available; falls back to empty string.
    """
    if "flat_step_type" in eff.columns:
        return eff["flat_step_type"].fillna("").str.strip()
    return pd.Series("", index=eff.index)


# ---------------------------------------------------------------------------
# A. Portfolio KPIs
# ---------------------------------------------------------------------------

def get_total_docs(ctx: QueryContext) -> int:
    """
    Total number of distinct documents in Flat GED.

    Source: flat_ged_ops_df (numero, indice).
    Returns: int — count of unique (numero, indice) pairs.
    """
    ops = _require_df(ctx, "flat_ged_ops_df")
    return int(ops[["numero", "indice"]].drop_duplicates().shape[0])


def get_open_docs(ctx: QueryContext) -> int:
    """
    Count of documents with at least one blocking step (workflow cycle not yet closed).

    A document is open if any non-OPEN_DOC step has is_blocking=True.
    Source: flat_ged_ops_df.
    Returns: int
    """
    steps = _ops_steps(ctx)
    return int(
        steps[steps["is_blocking"] == True][["numero", "indice"]]
        .drop_duplicates()
        .shape[0]
    )


def get_closed_docs(ctx: QueryContext) -> int:
    """
    Count of documents with no blocking steps (workflow cycle closed).

    A document is closed if no non-OPEN_DOC step has is_blocking=True.
    This covers MOEX_VISA and ALL_RESPONDED_NO_MOEX closure modes.
    Source: flat_ged_ops_df.
    Returns: int
    """
    steps = _ops_steps(ctx)
    all_docs     = set(zip(steps["numero"], steps["indice"]))
    blocking_docs = set(
        zip(
            steps.loc[steps["is_blocking"] == True, "numero"],
            steps.loc[steps["is_blocking"] == True, "indice"],
        )
    )
    return int(len(all_docs - blocking_docs))


def get_pending_steps(ctx: QueryContext) -> int:
    """
    Count of steps where date_status_type in {PENDING_IN_DELAY, PENDING_LATE}.

    Reflects report-memory composition: a step promoted from PENDING to ANSWERED
    via report_memory is NOT counted here.
    Source: effective_responses_df.
    Returns: int
    """
    eff = _require_df(ctx, "effective_responses_df")
    return int(_pending_mask(eff).sum())


def get_answered_steps(ctx: QueryContext) -> int:
    """
    Count of steps where date_status_type == ANSWERED.

    Includes steps promoted from PENDING to ANSWERED via report_memory.
    Source: effective_responses_df.
    Returns: int
    """
    eff = _require_df(ctx, "effective_responses_df")
    return int((eff["date_status_type"] == _ANSWERED_TYPE).sum())


def get_overdue_steps(ctx: QueryContext) -> int:
    """
    Count of steps that are both pending AND past their phase_deadline.

    Mapped to date_status_type == PENDING_LATE in effective_responses_df
    (set by the adapter when is_blocking=True and retard_avance_status=RETARD).
    Source: effective_responses_df.
    Returns: int
    """
    eff = _require_df(ctx, "effective_responses_df")
    return int(_overdue_mask(eff).sum())


def get_due_next_7_days(ctx: QueryContext) -> int:
    """
    Count of pending steps whose phase_deadline falls within the next 7 days
    from data_date (inclusive). Steps already past deadline (PENDING_LATE) are excluded.

    Source: effective_responses_df (flat_phase_deadline + flat_data_date columns).
    Returns: int
    """
    eff       = _require_df(ctx, "effective_responses_df")
    data_date = _get_data_date(ctx)
    if data_date is None:
        _LOG.warning("get_due_next_7_days: data_date unavailable — returning 0.")
        return 0

    in_delay = eff[eff["date_status_type"] == "PENDING_IN_DELAY"].copy()
    if in_delay.empty:
        return 0

    if "flat_phase_deadline" not in in_delay.columns:
        _LOG.warning("get_due_next_7_days: flat_phase_deadline column missing — returning 0.")
        return 0

    dl = pd.to_datetime(in_delay["flat_phase_deadline"], errors="coerce")
    cutoff = data_date + pd.Timedelta(days=7)
    return int(((dl >= data_date) & (dl <= cutoff)).sum())


# ---------------------------------------------------------------------------
# B. Workflow Status Mix
# ---------------------------------------------------------------------------

def get_status_breakdown(ctx: QueryContext) -> dict:
    """
    Count of steps by status category across all documents.

    Source: effective_responses_df.
    VAOB is counted in approval-family (VAO equivalence per project decision).

    Returns dict:
      approval    — ANSWERED steps with approval-family status (VAO/VSO/FAV/HM/VAOB)
      rejection   — ANSWERED steps with rejection-family status (REF/DEF)
      pending     — PENDING_IN_DELAY steps (within deadline)
      overdue     — PENDING_LATE steps (past deadline)
      not_called  — NOT_CALLED steps (post-MOEX de-flagged or genuinely absent)
      hm          — HM steps specifically (subset of approval)
      sas_ref     — REF steps where step_type == SAS (SAS-level refusal)
      report_upgraded — steps promoted from PENDING to ANSWERED via report_memory
      total_decisive  — approval + rejection (complete, decisive answers)
    """
    eff = _require_df(ctx, "effective_responses_df")

    dst = eff["date_status_type"]
    answered = eff[dst == _ANSWERED_TYPE]
    ans_status = answered["status_clean"].fillna("").str.strip().str.upper()
    step_type  = _eff_step_type(eff)

    approval_n  = int(_approval_family_mask(ans_status).sum())
    rejection_n = int(_rejection_family_mask(ans_status).sum())
    hm_n        = int((ans_status == "HM").sum())

    # SAS REF: REF answer on a SAS step
    sas_ref_mask = (
        (dst == _ANSWERED_TYPE) &
        (step_type == "SAS") &
        (eff["status_clean"].fillna("").str.strip().str.upper() == "REF")
    )
    sas_ref_n = int(sas_ref_mask.sum())

    # Report-memory promoted steps
    promoted_n = 0
    if "report_memory_applied" in eff.columns:
        promoted_n = int(eff["report_memory_applied"].astype(bool).sum())

    return {
        "approval":        approval_n,
        "rejection":       rejection_n,
        "pending":         int((dst == "PENDING_IN_DELAY").sum()),
        "overdue":         int((dst == "PENDING_LATE").sum()),
        "not_called":      int((dst == _NOT_CALLED).sum()),
        "hm":              hm_n,
        "sas_ref":         sas_ref_n,
        "report_upgraded": promoted_n,
        "total_decisive":  approval_n + rejection_n,
    }


# ---------------------------------------------------------------------------
# C. Consultant Performance
# ---------------------------------------------------------------------------

def get_consultant_kpis(ctx: QueryContext) -> pd.DataFrame:
    """
    Per approver / actor performance metrics.

    Source: effective_responses_df.
    OPEN_DOC rows are excluded (they have no approver_canonical).

    Returns DataFrame with columns:
      approver_canonical, assigned_steps, answered, pending, overdue,
      avg_delay_days, median_delay_days, approval_pct, rejection_pct, hm_pct,
      open_load (= pending count; current queue depth for this actor)

    Sorted by open_load DESC, then overdue DESC.
    """
    eff = _require_df(ctx, "effective_responses_df")

    # Exclude OPEN_DOC (no real approver)
    step_type = _eff_step_type(eff)
    df = eff[step_type != "OPEN_DOC"].copy()

    has_delay_col = "flat_step_delay_days" in df.columns

    rows = []
    for actor, grp in df.groupby("approver_canonical", sort=True):
        dst        = grp["date_status_type"]
        answered   = grp[dst == _ANSWERED_TYPE]
        pending_n  = int(_pending_mask(grp).sum())
        overdue_n  = int(_overdue_mask(grp).sum())

        ans_status = answered["status_clean"].fillna("").str.strip().str.upper()
        approval_n  = int(_approval_family_mask(ans_status).sum())
        rejection_n = int(_rejection_family_mask(ans_status).sum())
        hm_n        = int((ans_status == "HM").sum())
        n_answered  = len(answered)

        def _pct(n: int) -> float:
            return round(100.0 * n / n_answered, 1) if n_answered > 0 else 0.0

        # Delay: flat_step_delay_days is max(0, effective_date - phase_deadline) per step
        avg_delay = med_delay = 0.0
        if has_delay_col:
            delays = pd.to_numeric(grp["flat_step_delay_days"], errors="coerce").dropna()
            if not delays.empty:
                avg_delay = round(float(delays.mean()), 1)
                med_delay = round(float(delays.median()), 1)

        rows.append({
            "approver_canonical": actor,
            "assigned_steps":     len(grp),
            "answered":           n_answered,
            "pending":            pending_n,
            "overdue":            overdue_n,
            "avg_delay_days":     avg_delay,
            "median_delay_days":  med_delay,
            "approval_pct":       _pct(approval_n),
            "rejection_pct":      _pct(rejection_n),
            "hm_pct":             _pct(hm_n),
            "open_load":          pending_n,
        })

    if not rows:
        return pd.DataFrame(columns=[
            "approver_canonical", "assigned_steps", "answered", "pending", "overdue",
            "avg_delay_days", "median_delay_days", "approval_pct", "rejection_pct",
            "hm_pct", "open_load",
        ])

    return (
        pd.DataFrame(rows)
        .sort_values(["open_load", "overdue"], ascending=[False, False])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# D. Document Lifecycle
# ---------------------------------------------------------------------------

def get_doc_lifecycle(ctx: QueryContext) -> pd.DataFrame:
    """
    Per-document lifecycle summary. One row per (numero, indice).

    Source: flat_ged_ops_df (primary). Uses _derive_visa_global() internally.
    Note on source_counts: bridging from ops doc_key to effective_responses doc_id
    requires the pipeline's id_to_pair map (not held in QueryContext). Source counts
    are therefore not included here. Use get_effective_source_mix() for aggregate
    provenance analysis.

    Returns DataFrame with columns:
      doc_key, numero, indice, lot, emetteur, titre,
      is_open, visa_global, responsible_party,
      pending_actors, overdue_actors, total_delay_days,
      submittal_date, data_date
    """
    ops = _require_df(ctx, "flat_ged_ops_df")

    rows = []
    for (numero, indice), group in ops.groupby(["numero", "indice"], sort=False):
        doc_key = f"{numero}_{indice}"
        steps   = group[group["step_type"] != "OPEN_DOC"]

        is_open      = bool((steps["is_blocking"] == True).any()) if not steps.empty else False
        visa_global  = _derive_visa_global(group)

        # Responsible party: actor of the highest-priority blocking step
        # (first blocking actor in step_order, which mirrors workflow_engine logic)
        responsible_party = None
        if not steps.empty and "step_order" in steps.columns:
            blocking = steps[steps["is_blocking"] == True].sort_values("step_order")
            if not blocking.empty:
                responsible_party = str(blocking["actor_clean"].iloc[0])

        # Pending and overdue actors
        pending_rows  = steps[steps["is_blocking"] == True]
        overdue_rows  = steps[
            (steps["is_blocking"] == True) &
            (steps.get("retard_avance_status", pd.Series("", index=steps.index)) == "RETARD")
        ] if "retard_avance_status" in steps.columns else pd.DataFrame()

        pending_actors = "|".join(sorted(pending_rows["actor_clean"].dropna().unique()))
        overdue_actors = "|".join(sorted(overdue_rows["actor_clean"].dropna().unique())) if not overdue_rows.empty else ""

        # Total delay: max cumulative_delay_days across all steps for this doc
        total_delay = 0
        if "cumulative_delay_days" in group.columns:
            vals = pd.to_numeric(group["cumulative_delay_days"], errors="coerce").dropna()
            total_delay = int(vals.max()) if not vals.empty else 0

        # OPEN_DOC carries submittal_date
        open_doc_rows = group[group["step_type"] == "OPEN_DOC"]
        submittal_date = str(_safe_first(open_doc_rows.get("submittal_date", pd.Series(dtype=str)), ""))
        data_date_val  = str(_safe_first(group.get("data_date", pd.Series(dtype=str)), ""))

        rows.append({
            "doc_key":           doc_key,
            "numero":            numero,
            "indice":            indice,
            "lot":               str(_safe_first(group.get("lot", pd.Series(dtype=str)), "")),
            "emetteur":          str(_safe_first(group.get("emetteur", pd.Series(dtype=str)), "")),
            "titre":             str(_safe_first(group.get("titre", pd.Series(dtype=str)), "")),
            "is_open":           is_open,
            "visa_global":       visa_global,
            "responsible_party": responsible_party,
            "pending_actors":    pending_actors,
            "overdue_actors":    overdue_actors,
            "total_delay_days":  total_delay,
            "submittal_date":    submittal_date,
            "data_date":         data_date_val,
        })

    return pd.DataFrame(rows).reset_index(drop=True)


# ---------------------------------------------------------------------------
# E. Queue Engine Primitives
# ---------------------------------------------------------------------------

def get_easy_wins(ctx: QueryContext) -> pd.DataFrame:
    """
    Documents where only MOEX remains blocking AND all answered consultants gave
    approval-family responses (VAO/VSO/FAV/HM/VAOB). No rejections, no conflicts.

    These documents are ready for MOEX visa and represent the fastest path to closure.
    Source: flat_ged_ops_df.

    Returns DataFrame: doc_key, numero, indice, lot, emetteur, titre, total_delay_days.
    """
    steps = _ops_steps(ctx)

    easy = []
    for (numero, indice), grp in steps.groupby(["numero", "indice"], sort=False):
        blocking = grp[grp["is_blocking"] == True]
        if blocking.empty:
            continue  # Already closed — not in play

        # All blocking steps must be MOEX
        if not (blocking["step_type"] == "MOEX").all():
            continue

        # All answered non-MOEX steps must be approval-family
        answered_non_moex = grp[
            (grp["step_type"] != "MOEX") & (grp["is_completed"] == True)
        ]
        if answered_non_moex.empty:
            continue  # No answered non-MOEX steps — not a clean easy win

        ans_status = answered_non_moex["status_clean"].fillna("").str.strip().str.upper()
        if not _approval_family_mask(ans_status).all():
            continue  # Some non-approval answers — not a clean alignment

        delay_vals = pd.to_numeric(grp.get("cumulative_delay_days", pd.Series(dtype=float)), errors="coerce").dropna()
        easy.append({
            "doc_key":          f"{numero}_{indice}",
            "numero":           numero,
            "indice":           indice,
            "lot":              str(_safe_first(grp.get("lot", pd.Series(dtype=str)), "")),
            "emetteur":         str(_safe_first(grp.get("emetteur", pd.Series(dtype=str)), "")),
            "titre":            str(_safe_first(grp.get("titre", pd.Series(dtype=str)), "")),
            "total_delay_days": int(delay_vals.max()) if not delay_vals.empty else 0,
        })

    return pd.DataFrame(easy).reset_index(drop=True) if easy else pd.DataFrame(
        columns=["doc_key", "numero", "indice", "lot", "emetteur", "titre", "total_delay_days"]
    )


def get_conflicts(ctx: QueryContext) -> pd.DataFrame:
    """
    Documents with contradictory step statuses or report-GED conflicts.

    Two detection paths:
      1. flat_ged_ops_df: docs where answered steps contain BOTH approval-family
         AND rejection-family statuses (internal GED conflict).
      2. effective_responses_df: docs where any step has effective_source ==
         GED_CONFLICT_REPORT (report contradicts GED).

    Returns DataFrame: doc_key (or doc_id), source, conflict_type, detail.
    """
    results = []

    # Path 1: GED-internal conflicts from ops_df
    steps = _ops_steps(ctx)
    for (numero, indice), grp in steps.groupby(["numero", "indice"], sort=False):
        answered = grp[grp["is_completed"] == True]
        if answered.empty:
            continue
        ans_s = answered["status_clean"].fillna("").str.strip().str.upper()
        has_approval   = _approval_family_mask(ans_s).any()
        has_rejection  = _rejection_family_mask(ans_s).any()
        if has_approval and has_rejection:
            results.append({
                "doc_key":       f"{numero}_{indice}",
                "numero":        numero,
                "indice":        indice,
                "source":        "GED_OPERATIONS",
                "conflict_type": "MIXED_STATUS",
                "detail":        f"Approval and rejection both present among answered steps.",
            })

    # Path 2: Report-GED conflicts from effective_responses_df
    try:
        eff = _require_df(ctx, "effective_responses_df")
        if "effective_source" in eff.columns:
            conflict_rows = eff[eff["effective_source"] == EFF_SRC_CONFLICT]
            for _, row in conflict_rows.iterrows():
                results.append({
                    "doc_key":       str(row.get("doc_id", "UNKNOWN")),
                    "numero":        None,
                    "indice":        None,
                    "source":        "REPORT_MEMORY",
                    "conflict_type": "GED_CONFLICT_REPORT",
                    "detail": (
                        f"approver={row.get('approver_canonical', '')} "
                        f"ged_status={row.get('status_clean', '')} "
                        f"comment={str(row.get('response_comment', ''))[:80]}"
                    ),
                })
    except ValueError:
        pass  # effective_responses_df not available — skip path 2

    return pd.DataFrame(results).reset_index(drop=True) if results else pd.DataFrame(
        columns=["doc_key", "numero", "indice", "source", "conflict_type", "detail"]
    )


def get_waiting_secondary(ctx: QueryContext) -> pd.DataFrame:
    """
    Documents where ONLY secondary (non-primary) consultants are blocking.

    Primary approvers: TERRELL, EGIS, BET SPK, BET ASC, BET EV, BET FACADES,
    ARCHI MOX, MOEX (keywords matched case-insensitively).
    Secondary = any actor not matching primary keywords.

    These documents have resolved all primary reviews and are waiting only on
    secondary consultants.
    Source: flat_ged_ops_df.

    Returns DataFrame: doc_key, numero, indice, blocking_actors.
    """
    steps = _ops_steps(ctx)

    results = []
    for (numero, indice), grp in steps.groupby(["numero", "indice"], sort=False):
        blocking = grp[grp["is_blocking"] == True]
        if blocking.empty:
            continue

        actors = blocking["actor_clean"].fillna("").unique()
        all_secondary = all(not _is_primary_approver(a) for a in actors)
        if all_secondary:
            results.append({
                "doc_key":        f"{numero}_{indice}",
                "numero":         numero,
                "indice":         indice,
                "blocking_actors": "|".join(sorted(actors)),
            })

    return pd.DataFrame(results).reset_index(drop=True) if results else pd.DataFrame(
        columns=["doc_key", "numero", "indice", "blocking_actors"]
    )


def get_waiting_moex(ctx: QueryContext) -> pd.DataFrame:
    """
    Documents where MOEX is the only blocking step (regardless of response alignment).

    Broader than get_easy_wins(): includes docs with rejections or HM among
    answered consultants — the cycle still hinges on MOEX.
    Source: flat_ged_ops_df.

    Returns DataFrame: doc_key, numero, indice, lot, emetteur, titre, total_delay_days.
    """
    steps = _ops_steps(ctx)

    results = []
    for (numero, indice), grp in steps.groupby(["numero", "indice"], sort=False):
        blocking = grp[grp["is_blocking"] == True]
        if blocking.empty:
            continue
        if (blocking["step_type"] == "MOEX").all():
            delay_vals = pd.to_numeric(grp.get("cumulative_delay_days", pd.Series(dtype=float)), errors="coerce").dropna()
            results.append({
                "doc_key":          f"{numero}_{indice}",
                "numero":           numero,
                "indice":           indice,
                "lot":              str(_safe_first(grp.get("lot", pd.Series(dtype=str)), "")),
                "emetteur":         str(_safe_first(grp.get("emetteur", pd.Series(dtype=str)), "")),
                "titre":            str(_safe_first(grp.get("titre", pd.Series(dtype=str)), "")),
                "total_delay_days": int(delay_vals.max()) if not delay_vals.empty else 0,
            })

    return pd.DataFrame(results).reset_index(drop=True) if results else pd.DataFrame(
        columns=["doc_key", "numero", "indice", "lot", "emetteur", "titre", "total_delay_days"]
    )


def get_stale_pending(ctx: QueryContext, days: int = 30) -> pd.DataFrame:
    """
    Pending steps that are past their phase_deadline by more than `days`.

    Uses step_delay_days from flat_ged_ops_df:
      step_delay_days = max(0, data_date - phase_deadline) for blocking steps.
    Stale = is_blocking=True AND step_delay_days > days.

    Source: flat_ged_ops_df.

    Args:
      days: threshold in days past deadline (default 30).

    Returns DataFrame: doc_key, numero, indice, actor_clean, step_type,
      step_delay_days, phase_deadline, data_date.
    """
    steps = _ops_steps(ctx)
    blocking = steps[steps["is_blocking"] == True].copy()
    if blocking.empty or "step_delay_days" not in blocking.columns:
        return pd.DataFrame(columns=[
            "doc_key", "numero", "indice", "actor_clean", "step_type",
            "step_delay_days", "phase_deadline", "data_date",
        ])

    blocking["step_delay_days"] = pd.to_numeric(blocking["step_delay_days"], errors="coerce").fillna(0)
    stale = blocking[blocking["step_delay_days"] > days].copy()

    if stale.empty:
        return pd.DataFrame(columns=[
            "doc_key", "numero", "indice", "actor_clean", "step_type",
            "step_delay_days", "phase_deadline", "data_date",
        ])

    stale["doc_key"] = stale["numero"].astype(str) + "_" + stale["indice"].astype(str)
    cols = ["doc_key", "numero", "indice", "actor_clean", "step_type",
            "step_delay_days", "phase_deadline", "data_date"]
    return (
        stale[[c for c in cols if c in stale.columns]]
        .sort_values("step_delay_days", ascending=False)
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# F. Fiche Inputs
# ---------------------------------------------------------------------------

def get_doc_fiche(ctx: QueryContext, doc_key: str) -> dict:
    """
    Full lifecycle record for a single document.

    Args:
      doc_key: "{numero}_{indice}" string identifying the document.
               Example: "248000_A".

    Source: flat_ged_ops_df (primary).

    Returns dict with keys:
      doc_key, numero, indice, lot, emetteur, titre,
      is_open, visa_global, responsible_party,
      submittal_date, data_date, global_deadline,
      pending_actors (list), overdue_actors (list),
      total_delay_days, step_details (list of dicts per step)
    """
    ops = _require_df(ctx, "flat_ged_ops_df")

    # Parse doc_key → numero, indice
    parts = doc_key.split("_", 1)
    if len(parts) != 2:
        raise ValueError(
            f"get_doc_fiche: doc_key must be '{{numero}}_{{indice}}', got '{doc_key}'."
        )
    numero_str, indice_str = parts[0].strip(), parts[1].strip()

    # Filter — handle numeric vs string numero
    try:
        numero_int = int(numero_str)
        mask = (ops["numero"].astype(str).str.strip() == numero_str) & \
               (ops["indice"].astype(str).str.strip() == indice_str)
    except ValueError:
        mask = (ops["numero"].astype(str).str.strip() == numero_str) & \
               (ops["indice"].astype(str).str.strip() == indice_str)

    group = ops[mask]
    if group.empty:
        raise ValueError(
            f"get_doc_fiche: doc_key '{doc_key}' not found in flat_ged_ops_df. "
            f"Available keys are '{numero_str}_{indice_str}' — check numero/indice values."
        )

    steps = group[group["step_type"] != "OPEN_DOC"]
    open_doc_row = group[group["step_type"] == "OPEN_DOC"]

    is_open   = bool((steps["is_blocking"] == True).any())
    visa_gl   = _derive_visa_global(group)

    blocking       = steps[steps["is_blocking"] == True]
    overdue_rows   = steps[
        (steps["is_blocking"] == True) &
        (steps.get("retard_avance_status", pd.Series("", index=steps.index)) == "RETARD")
    ] if "retard_avance_status" in steps.columns else pd.DataFrame()

    responsible = None
    if not blocking.empty and "step_order" in blocking.columns:
        responsible = str(blocking.sort_values("step_order")["actor_clean"].iloc[0])

    delay_vals = pd.to_numeric(group.get("cumulative_delay_days", pd.Series(dtype=float)), errors="coerce").dropna()
    total_delay = int(delay_vals.max()) if not delay_vals.empty else 0

    step_cols = [
        "step_order", "step_type", "actor_clean", "status_clean", "status_family",
        "is_completed", "is_blocking", "response_date", "phase_deadline",
        "retard_avance_days", "step_delay_days", "delay_contribution_days",
    ]
    step_details = steps[[c for c in step_cols if c in steps.columns]].to_dict(orient="records")

    return {
        "doc_key":           doc_key,
        "numero":            numero_str,
        "indice":            indice_str,
        "lot":               str(_safe_first(group.get("lot", pd.Series(dtype=str)), "")),
        "emetteur":          str(_safe_first(group.get("emetteur", pd.Series(dtype=str)), "")),
        "titre":             str(_safe_first(group.get("titre", pd.Series(dtype=str)), "")),
        "is_open":           is_open,
        "visa_global":       visa_gl,
        "responsible_party": responsible,
        "submittal_date":    str(_safe_first(open_doc_row.get("submittal_date", pd.Series(dtype=str)), "")),
        "global_deadline":   str(_safe_first(group.get("global_deadline", pd.Series(dtype=str)), "")),
        "data_date":         str(_safe_first(group.get("data_date", pd.Series(dtype=str)), "")),
        "pending_actors":    sorted(blocking["actor_clean"].dropna().unique().tolist()),
        "overdue_actors":    sorted(overdue_rows["actor_clean"].dropna().unique().tolist()) if not overdue_rows.empty else [],
        "total_delay_days":  total_delay,
        "step_details":      step_details,
    }


def get_actor_fiche(ctx: QueryContext, actor: str) -> dict:
    """
    Full performance record for a single approver.

    Args:
      actor: approver_canonical string (exact match, case-sensitive).
             Example: "BET Structure".

    Source: effective_responses_df (primary).

    Returns dict with keys:
      actor, assigned_steps, answered, pending, overdue, not_called,
      approval_pct, rejection_pct, hm_pct,
      avg_delay_days, median_delay_days, max_delay_days,
      open_load, report_upgraded,
      answered_docs (list of doc_ids), pending_docs (list of doc_ids),
      overdue_docs (list of doc_ids)
    """
    eff = _require_df(ctx, "effective_responses_df")

    if "approver_canonical" not in eff.columns:
        raise ValueError("get_actor_fiche: effective_responses_df missing 'approver_canonical' column.")

    grp = eff[eff["approver_canonical"] == actor]
    if grp.empty:
        raise ValueError(
            f"get_actor_fiche: actor '{actor}' not found in effective_responses_df. "
            f"Check approver_canonical values."
        )

    dst = grp["date_status_type"]
    answered_rows = grp[dst == _ANSWERED_TYPE]
    pending_rows  = grp[_pending_mask(grp)]
    overdue_rows  = grp[_overdue_mask(grp)]
    nc_rows       = grp[dst == _NOT_CALLED]

    ans_status  = answered_rows["status_clean"].fillna("").str.strip().str.upper()
    n_answered  = len(answered_rows)
    approval_n  = int(_approval_family_mask(ans_status).sum())
    rejection_n = int(_rejection_family_mask(ans_status).sum())
    hm_n        = int((ans_status == "HM").sum())

    def _pct(n: int) -> float:
        return round(100.0 * n / n_answered, 1) if n_answered > 0 else 0.0

    delay_vals = pd.to_numeric(
        grp.get("flat_step_delay_days", pd.Series(0, index=grp.index)),
        errors="coerce"
    ).dropna()

    promoted_n = int(grp.get("report_memory_applied", pd.Series(False, index=grp.index)).astype(bool).sum())

    answered_docs = sorted(answered_rows["doc_id"].dropna().unique().tolist()) if "doc_id" in answered_rows.columns else []
    pending_docs  = sorted(pending_rows["doc_id"].dropna().unique().tolist())  if "doc_id" in pending_rows.columns  else []
    overdue_docs  = sorted(overdue_rows["doc_id"].dropna().unique().tolist())  if "doc_id" in overdue_rows.columns  else []

    return {
        "actor":             actor,
        "assigned_steps":   len(grp),
        "answered":         n_answered,
        "pending":          len(pending_rows),
        "overdue":          len(overdue_rows),
        "not_called":       len(nc_rows),
        "approval_pct":     _pct(approval_n),
        "rejection_pct":    _pct(rejection_n),
        "hm_pct":           _pct(hm_n),
        "avg_delay_days":   round(float(delay_vals.mean()), 1) if not delay_vals.empty else 0.0,
        "median_delay_days": round(float(delay_vals.median()), 1) if not delay_vals.empty else 0.0,
        "max_delay_days":   int(delay_vals.max()) if not delay_vals.empty else 0,
        "open_load":        len(pending_rows),
        "report_upgraded":  promoted_n,
        "answered_docs":    answered_docs,
        "pending_docs":     pending_docs,
        "overdue_docs":     overdue_docs,
    }


# ---------------------------------------------------------------------------
# G. Provenance & Quality
# ---------------------------------------------------------------------------

def get_effective_source_mix(ctx: QueryContext) -> dict:
    """
    Distribution of effective_source values across all steps.

    Reveals how much of the composed truth comes from GED alone vs report memory.
    Source: effective_responses_df.

    Returns dict:
      GED                 — steps sourced entirely from GED (no report enrichment)
      GED+REPORT_STATUS   — steps where report memory promoted PENDING → ANSWERED
      GED+REPORT_COMMENT  — steps where report memory added a comment only
      GED_CONFLICT_REPORT — steps where report contradicts GED answer
      REPORT_ONLY         — steps with no GED anchor (should be 0; indicates bug)
      total               — total rows
      report_influence_pct — pct of steps with any report enrichment
    """
    eff = _require_df(ctx, "effective_responses_df")

    if "effective_source" not in eff.columns:
        _LOG.warning("get_effective_source_mix: 'effective_source' column not in effective_responses_df — returning zeros.")
        return {s: 0 for s in [
            EFF_SRC_GED, EFF_SRC_RPT_STATUS, EFF_SRC_RPT_COMMENT,
            EFF_SRC_CONFLICT, EFF_SRC_RPT_ONLY, "total", "report_influence_pct"
        ]}

    counts = eff["effective_source"].value_counts().to_dict()
    total  = len(eff)

    ged_n       = counts.get(EFF_SRC_GED, 0)
    status_n    = counts.get(EFF_SRC_RPT_STATUS, 0)
    comment_n   = counts.get(EFF_SRC_RPT_COMMENT, 0)
    conflict_n  = counts.get(EFF_SRC_CONFLICT, 0)
    rpt_only_n  = counts.get(EFF_SRC_RPT_ONLY, 0)

    if rpt_only_n > 0:
        _LOG.error(
            "get_effective_source_mix: %d REPORT_ONLY rows detected — composition bug. "
            "Report rows must not create GED workflow steps.",
            rpt_only_n,
        )

    influenced = status_n + comment_n + conflict_n + rpt_only_n
    influence_pct = round(100.0 * influenced / total, 1) if total > 0 else 0.0

    return {
        EFF_SRC_GED:         ged_n,
        EFF_SRC_RPT_STATUS:  status_n,
        EFF_SRC_RPT_COMMENT: comment_n,
        EFF_SRC_CONFLICT:    conflict_n,
        EFF_SRC_RPT_ONLY:    rpt_only_n,
        "total":             total,
        "report_influence_pct": influence_pct,
    }


def get_report_upgrades(ctx: QueryContext) -> pd.DataFrame:
    """
    Steps where report_memory promoted a PENDING step to ANSWERED.

    These are the rows where the report_memory composition (Step 8) made a
    substantive difference to the pipeline output.
    Source: effective_responses_df.

    Returns DataFrame: doc_id, approver_canonical, status_clean, date_answered,
      effective_source, response_comment.
    """
    eff = _require_df(ctx, "effective_responses_df")

    if "effective_source" not in eff.columns:
        return pd.DataFrame(columns=[
            "doc_id", "approver_canonical", "status_clean",
            "date_answered", "effective_source", "response_comment",
        ])

    upgrades = eff[eff["effective_source"] == EFF_SRC_RPT_STATUS].copy()
    cols = ["doc_id", "approver_canonical", "status_clean",
            "date_answered", "effective_source", "response_comment"]
    return upgrades[[c for c in cols if c in upgrades.columns]].reset_index(drop=True)


def get_conflict_rows(ctx: QueryContext) -> pd.DataFrame:
    """
    Steps where the effective_source is GED_CONFLICT_REPORT:
    report memory carries a status that contradicts the GED answer.

    GED always wins in these cases (Rule R1d from composition spec).
    These rows require manual review.
    Source: effective_responses_df.

    Returns DataFrame: doc_id, approver_canonical, status_clean, date_answered,
      effective_source, response_comment.
    """
    eff = _require_df(ctx, "effective_responses_df")

    if "effective_source" not in eff.columns:
        return pd.DataFrame(columns=[
            "doc_id", "approver_canonical", "status_clean",
            "date_answered", "effective_source", "response_comment",
        ])

    conflicts = eff[eff["effective_source"] == EFF_SRC_CONFLICT].copy()
    cols = ["doc_id", "approver_canonical", "status_clean",
            "date_answered", "effective_source", "response_comment"]
    return conflicts[[c for c in cols if c in conflicts.columns]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Smoke test helper (run directly for quick validation)
# ---------------------------------------------------------------------------

def _smoke_test(ctx: QueryContext) -> None:
    """
    Quick sanity check for all function groups.
    Prints results; raises on any exception.
    Call after constructing a QueryContext from a real run.

    Example:
        from src.query_library import QueryContext, _smoke_test
        ctx = QueryContext(
            flat_ged_ops_df=ops_df,
            effective_responses_df=eff_df,
        )
        _smoke_test(ctx)
    """
    print("=" * 60)
    print("QUERY LIBRARY SMOKE TEST")
    print("=" * 60)

    print("\n── A. Portfolio KPIs ──")
    print(f"  get_total_docs        = {get_total_docs(ctx)}")
    print(f"  get_open_docs         = {get_open_docs(ctx)}")
    print(f"  get_closed_docs       = {get_closed_docs(ctx)}")
    print(f"  get_pending_steps     = {get_pending_steps(ctx)}")
    print(f"  get_answered_steps    = {get_answered_steps(ctx)}")
    print(f"  get_overdue_steps     = {get_overdue_steps(ctx)}")
    print(f"  get_due_next_7_days   = {get_due_next_7_days(ctx)}")

    print("\n── B. Status Mix ──")
    bkdn = get_status_breakdown(ctx)
    for k, v in bkdn.items():
        print(f"  {k:25s} = {v}")

    print("\n── C. Consultant KPIs ──")
    kpis = get_consultant_kpis(ctx)
    print(kpis.head(5).to_string(index=False))

    print("\n── D. Document Lifecycle (first 3 rows) ──")
    lifecycle = get_doc_lifecycle(ctx)
    print(lifecycle.head(3).to_string(index=False))

    print("\n── E. Queue Primitives ──")
    print(f"  get_easy_wins         → {len(get_easy_wins(ctx))} docs")
    print(f"  get_conflicts         → {len(get_conflicts(ctx))} entries")
    print(f"  get_waiting_secondary → {len(get_waiting_secondary(ctx))} docs")
    print(f"  get_waiting_moex      → {len(get_waiting_moex(ctx))} docs")
    print(f"  get_stale_pending(30) → {len(get_stale_pending(ctx, 30))} steps")

    print("\n── G. Provenance ──")
    mix = get_effective_source_mix(ctx)
    for k, v in mix.items():
        print(f"  {k:30s} = {v}")
    print(f"  get_report_upgrades   → {len(get_report_upgrades(ctx))} rows")
    print(f"  get_conflict_rows     → {len(get_conflict_rows(ctx))} rows")

    print("\n── F. Fiche (sample) ──")
    ops = ctx.flat_ged_ops_df
    if not ops.empty:
        row = ops.iloc[0]
        sample_key = f"{row['numero']}_{row['indice']}"
        fiche = get_doc_fiche(ctx, sample_key)
        print(f"  get_doc_fiche('{sample_key}'):")
        for k, v in fiche.items():
            if k != "step_details":
                print(f"    {k:25s} = {v}")
        print(f"    {'step_details':25s} = [{len(fiche['step_details'])} steps]")

    eff = ctx.effective_responses_df
    if "approver_canonical" in eff.columns and not eff.empty:
        sample_actor = eff["approver_canonical"].dropna().iloc[0]
        af = get_actor_fiche(ctx, sample_actor)
        print(f"\n  get_actor_fiche('{sample_actor}'):")
        for k, v in af.items():
            if not isinstance(v, list):
                print(f"    {k:25s} = {v}")

    print("\n" + "=" * 60)
    print("SMOKE TEST PASSED — no exceptions raised.")
    print("=" * 60)
