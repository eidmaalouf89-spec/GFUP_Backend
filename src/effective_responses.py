"""
effective_responses.py
----------------------
Composition layer: Flat GED (GED_OPERATIONS) + eligible report_memory enrichment
= effective_responses_df = logical clean_GF truth.

Design constraints (Step 8 / FLAT_GED_REPORT_COMPOSITION.md):
  - LEFT-ANCHORED on GED rows (responses_df from GED_OPERATIONS in flat mode,
    or normalize_responses() output in raw mode). We do NOT inject brand-new
    workflow rows from reports.
  - The output DataFrame must be drop-in compatible with WorkflowEngine.__init__.
  - No raw GED columns are re-parsed here.
  - effective_source is a five-value controlled vocabulary on every output row.

Merge rules (see FLAT_GED_REPORT_COMPOSITION.md §5):
  Rule 1 — GED ANSWERED: GED is source of truth. Reports cannot override.
            Reports may add additive comments (GED+REPORT_COMMENT) or flag
            conflicts (GED_CONFLICT_REPORT) but never change status/date.
  Rule 2 — GED PENDING + eligible report with date → upgrade to ANSWERED.
  Rule 3 — GED PENDING + no eligible report → remain pending.
  Rule 4 — GED NOT_CALLED / absent step → reports cannot create a new row.

Eligibility gates (E1–E8, see FLAT_GED_REPORT_COMPOSITION.md §4):
  E1  is_active = 1 (enforced by load_persisted_report_responses)
  E2  match_confidence is HIGH or MEDIUM (enforced here + at ingestion)
  E3  doc_id match (enforced at join level)
  E4  canonical approver match (enforced at join level)
  E5  report_response_date present (for promotion to ANSWERED)
  E6  at least one of report_status or report_response_date present
  E7  freshness gate (stale reports blocked)
  E8  no synthetic SAS target (not enforceable here; enforced upstream)

VAOB = VAO (Eid decision 2026-04-24):
  VAOB is approval-family. Not a conflict against VSO/VAO.
  On ANSWERED GED rows, VAOB enriches comment only (GED+REPORT_COMMENT).
  On PENDING rows, VAOB may upgrade like VAO.
"""

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provenance vocabulary (five-value, closed set — §6 of composition spec)
# ---------------------------------------------------------------------------

EFFECTIVE_SOURCE_GED              = "GED"
EFFECTIVE_SOURCE_REPORT_STATUS    = "GED+REPORT_STATUS"
EFFECTIVE_SOURCE_REPORT_COMMENT   = "GED+REPORT_COMMENT"
EFFECTIVE_SOURCE_CONFLICT         = "GED_CONFLICT_REPORT"
EFFECTIVE_SOURCE_REPORT_ONLY      = "REPORT_ONLY"   # PROHIBITED in Phase 2

# Backward-compat alias (previously used; internally replaced by full vocab)
_SOURCE_GED           = EFFECTIVE_SOURCE_GED
_SOURCE_REPORT_MEMORY = EFFECTIVE_SOURCE_REPORT_STATUS   # legacy alias

# ---------------------------------------------------------------------------
# Status family classification
# ---------------------------------------------------------------------------

# GED statuses where the document workflow is ANSWERED (complete)
_ANSWERED_STATUS_TYPE = "ANSWERED"

# GED date_status_type values that can be upgraded by report memory
_UPGRADEABLE_STATUSES = {"PENDING_IN_DELAY", "PENDING_LATE"}

# Approval-family statuses (same family → no conflict, VAOB treated as VAO)
_APPROVAL_FAMILY = frozenset({"VAO", "VSO", "FAV", "HM", "VAOB"})

# Rejection-family statuses
_REJECTION_FAMILY = frozenset({"REF", "DEF"})

# E2 — confidence values that are eligible for composition
_ELIGIBLE_CONFIDENCE = {"HIGH", "MEDIUM"}

# Text → float confidence map (canonical keys in upper-case)
_CONF_TEXT_MAP = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}

# E7 — freshness floor for PENDING rows (days before data_date that report is still valid)
_FRESHNESS_FLOOR_DAYS = 730


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_confidence(v) -> float:
    """Convert any confidence representation to float in [0, 1]. Returns -1 for unknown."""
    if v is None:
        return -1.0
    if isinstance(v, (int, float)):
        return float(v)
    mapped = _CONF_TEXT_MAP.get(str(v).strip().upper())
    return mapped if mapped is not None else -1.0


def _confidence_eligible(v) -> bool:
    """Return True only for HIGH or MEDIUM confidence (gate E2)."""
    if v is None:
        return False
    if isinstance(v, (int, float)):
        # float: 1.0=HIGH, 0.7=MEDIUM, 0.4=LOW → threshold at 0.7
        return float(v) >= 0.7
    return str(v).strip().upper() in _ELIGIBLE_CONFIDENCE


def _parse_date_flexible(value) -> Optional[pd.Timestamp]:
    """Parse a date value from consultant reports. Returns pd.NaT on failure."""
    if value is None:
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    try:
        return pd.to_datetime(str(value), dayfirst=True, errors="coerce")
    except Exception:
        return pd.NaT


def _is_blank(val) -> bool:
    """Return True for None, NaN, NaT, empty string, 'nan', 'None', 'NaT'."""
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    try:
        if pd.isna(val):
            return True
    except (TypeError, ValueError):
        pass
    return str(val).strip() in ("", "nan", "None", "NaT")


def _status_family(status: Optional[str]) -> Optional[str]:
    """Return 'APPROVAL', 'REJECTION', or None for a status_clean value."""
    if not status:
        return None
    s = str(status).strip().upper()
    if s in _APPROVAL_FAMILY:
        return "APPROVAL"
    if s in _REJECTION_FAMILY:
        return "REJECTION"
    return None


def _is_vaob(status: Optional[str]) -> bool:
    """Return True if status is VAOB (treated as VAO approval-family)."""
    if not status:
        return False
    return str(status).strip().upper() == "VAOB"


def _is_conflict(ged_status: Optional[str], report_status: Optional[str]) -> bool:
    """
    Return True when GED and report carry conflicting status families.
    VAOB is treated as approval-family (= VAO), so VAOB vs VAO/VSO is NOT a conflict.
    """
    if not ged_status or not report_status:
        return False
    gf = _status_family(ged_status)
    rf = _status_family(report_status)
    if gf is None or rf is None:
        return False
    return gf != rf


def _freshness_passes(
    ged_is_answered: bool,
    ged_answer_date,
    report_date,
    data_date,
) -> bool:
    """
    Gate E7 — freshness check.

    For ANSWERED GED rows: report_date must be > ged_answer_date.
    For PENDING GED rows:  report_date must be within 730 days before data_date.
    """
    rdate = _parse_date_flexible(report_date)
    if pd.isna(rdate):
        # No report date → cannot be fresher; block
        return False

    if ged_is_answered:
        gdate = _parse_date_flexible(ged_answer_date)
        if pd.isna(gdate):
            return True  # no GED answer date → freshness can't be checked, allow
        return rdate > gdate

    # PENDING row: report must not be older than 2-year floor
    ddate = _parse_date_flexible(data_date)
    if pd.isna(ddate):
        return True  # no data_date → skip floor check
    floor = ddate - pd.Timedelta(days=_FRESHNESS_FLOOR_DAYS)
    return rdate >= floor


# ---------------------------------------------------------------------------
# normalize_persisted_report_responses_for_merge
# ---------------------------------------------------------------------------

def normalize_persisted_report_responses_for_merge(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise persisted_report_responses DataFrame for use in
    build_effective_responses.

    Applies gate E2 (confidence filter) — LOW/UNKNOWN confidence rows are
    blocked here before they can enter composition.

    Returns one row per (doc_id, approver_canonical), keeping the best answer:
      1. Highest normalised confidence (DESCENDING)
      2. Latest report_response_date (DESCENDING; NaT sorts last)
      3. Latest ingested_at (DESCENDING)
    """
    _OUT_COLS = [
        "doc_id", "approver_canonical",
        "report_status", "report_response_date", "report_comment",
        "source_filename", "source_file_hash",
        "match_confidence", "match_method",
    ]

    if df is None or df.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    work = df.copy()

    # Rename 'consultant' → 'approver_canonical'
    work = work.rename(columns={"consultant": "approver_canonical"})

    # Drop rows missing core identity fields
    work = work.dropna(subset=["doc_id", "approver_canonical"])
    work = work[
        (work["doc_id"].astype(str).str.strip() != "") &
        (work["approver_canonical"].astype(str).str.strip() != "")
    ]
    if work.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    # ── Gate E2 — confidence filter (LOW/UNKNOWN blocked) ────────────────────
    e2_pass = work["match_confidence"].apply(_confidence_eligible)
    blocked_count = int((~e2_pass).sum())
    if blocked_count:
        logger.info(
            "normalize_persisted_report_responses_for_merge: "
            "%d rows blocked by E2 confidence gate (LOW/UNKNOWN/NULL)",
            blocked_count,
        )
    work = work[e2_pass].copy()
    if work.empty:
        logger.info("normalize_persisted_report_responses_for_merge: all rows blocked by E2")
        return pd.DataFrame(columns=_OUT_COLS)

    # ── Gate E6 — at least one of status or date present ────────────────────
    has_status = work["report_status"].apply(lambda v: not _is_blank(v))
    has_date   = work["report_response_date"].apply(lambda v: not _is_blank(v))
    work = work[has_status | has_date].copy()
    if work.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    # ── Winner selection ──────────────────────────────────────────────────────
    work["_conf_norm"]      = work["match_confidence"].apply(_normalize_confidence)
    work["_parsed_date"]    = work["report_response_date"].apply(_parse_date_flexible)
    work["_parsed_ingested"] = pd.to_datetime(work["ingested_at"], errors="coerce", utc=True)

    work = work.sort_values(
        ["doc_id", "approver_canonical",
         "_conf_norm", "_parsed_date", "_parsed_ingested"],
        ascending=[True, True, False, False, False],
        na_position="last",
    )
    best = work.drop_duplicates(subset=["doc_id", "approver_canonical"], keep="first")
    best = best.drop(columns=["_conf_norm", "_parsed_date", "_parsed_ingested"], errors="ignore")

    logger.debug(
        "normalize_persisted_report_responses_for_merge: "
        "%d unique (doc_id, approver) pairs after gates",
        len(best),
    )
    return best[[c for c in _OUT_COLS if c in best.columns]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main composition function
# ---------------------------------------------------------------------------

def build_effective_responses(
    ged_responses_df: pd.DataFrame,
    persisted_report_responses_df: pd.DataFrame,
    flat_mode: bool = False,
) -> pd.DataFrame:
    """
    Compose Flat GED (or raw GED) responses with eligible report_memory rows.

    Parameters
    ----------
    ged_responses_df
        In flat mode  : responses_df derived from GED_OPERATIONS (via stage_read_flat),
                        already normalized, with flat_* pass-through columns.
        In raw mode   : output of normalize_responses() on raw GED export.
        Must contain: doc_id, approver_canonical, date_answered,
                      date_status_type, status_clean, response_comment.
        Flat mode extras (used for E7 freshness gate): flat_data_date, flat_phase_deadline.

    persisted_report_responses_df
        Output of load_persisted_report_responses() from report_memory.
        Columns: consultant, doc_id, report_status, report_response_date,
                 report_comment, match_confidence, match_method, ...

    flat_mode
        If True, apply flat-mode-specific rules (VAOB, E7 with data_date, conflict detection).
        If False (raw mode), apply existing Rules 1-4 only with enhanced provenance vocab.

    Returns
    -------
    pd.DataFrame — same shape as ged_responses_df plus:
        effective_source      : controlled vocabulary (five values)
        report_memory_applied : bool (True when PENDING upgraded to ANSWERED)
    """
    if ged_responses_df is None or ged_responses_df.empty:
        logger.warning("build_effective_responses: ged_responses_df is empty — returning as-is")
        result = ged_responses_df.copy() if ged_responses_df is not None else pd.DataFrame()
        result["effective_source"]      = EFFECTIVE_SOURCE_GED
        result["report_memory_applied"] = False
        return result

    effective = ged_responses_df.copy()
    effective["effective_source"]      = EFFECTIVE_SOURCE_GED
    effective["report_memory_applied"] = False

    # Fast path — no persisted responses
    norm_report = normalize_persisted_report_responses_for_merge(persisted_report_responses_df)
    if norm_report.empty:
        logger.info("build_effective_responses: no eligible persisted responses — using GED only")
        return effective

    # ── Left join: attach best report answer to each GED row ─────────────────
    effective = effective.merge(
        norm_report[[
            "doc_id", "approver_canonical",
            "report_status", "report_response_date", "report_comment",
            "match_confidence",
        ]],
        on=["doc_id", "approver_canonical"],
        how="left",
        suffixes=("", "_report"),
    )

    # Counters for logging
    upgraded_count  = 0
    comment_count   = 0
    conflict_count  = 0
    stale_count     = 0
    already_ans_cnt = 0

    for idx in effective.index:
        row = effective.loc[idx]

        dst       = row.get("date_status_type", "")
        report_status_raw  = row.get("report_status")
        report_date_raw    = row.get("report_response_date")
        report_comment_raw = row.get("report_comment")

        # E6: skip rows with no meaningful report data at all
        has_r_status  = not _is_blank(report_status_raw)
        has_r_date    = not _is_blank(report_date_raw)
        if not has_r_status and not has_r_date:
            continue

        report_status  = str(report_status_raw).strip()  if has_r_status  else None
        report_comment = str(report_comment_raw).strip() if not _is_blank(report_comment_raw) else None

        # -- RULE 1: GED is ANSWERED --
        if dst == _ANSWERED_STATUS_TYPE:
            already_ans_cnt += 1
            ged_status = str(row.get("status_clean", "") or "").strip()

            if flat_mode and has_r_date:
                ged_ans_date = row.get("date_answered")
                if not _freshness_passes(True, ged_ans_date, report_date_raw, None):
                    stale_count += 1
                    continue

            if flat_mode and has_r_status and not _is_vaob(report_status):
                if _is_conflict(ged_status, report_status):
                    effective.at[idx, "effective_source"] = EFFECTIVE_SOURCE_CONFLICT
                    logger.warning(
                        "GED_CONFLICT_REPORT: doc_id=%s approver=%s ged_status=%s report_status=%s",
                        row.get("doc_id"), row.get("approver_canonical"), ged_status, report_status,
                    )
                    conflict_count += 1
                    continue

            if report_comment or has_r_status:
                _append_comment(
                    effective, idx,
                    comment_text=report_comment,
                    status_note=report_status if has_r_status and not _is_conflict(ged_status, report_status) else None,
                    tag="report",
                )
                effective.at[idx, "effective_source"] = EFFECTIVE_SOURCE_REPORT_COMMENT
                comment_count += 1
            continue

        # -- RULE 2: GED is PENDING --
        if dst in _UPGRADEABLE_STATUSES:
            data_date_val = None
            if flat_mode:
                data_date_val = row.get("flat_data_date") or row.get("data_date")
                if has_r_date and not _freshness_passes(False, None, report_date_raw, data_date_val):
                    stale_count += 1
                    if report_comment:
                        _append_comment(effective, idx, comment_text=report_comment)
                        effective.at[idx, "effective_source"] = EFFECTIVE_SOURCE_REPORT_COMMENT
                    continue

            if not has_r_date:
                if report_comment or has_r_status:
                    note = "status=" + str(report_status) if has_r_status else None
                    _append_comment(effective, idx, comment_text=report_comment, status_note=note, tag="report")
                    effective.at[idx, "effective_source"] = EFFECTIVE_SOURCE_REPORT_COMMENT
                    comment_count += 1
                continue

            report_date_parsed = _parse_date_flexible(report_date_raw)
            effective.at[idx, "date_status_type"]     = _ANSWERED_STATUS_TYPE
            effective.at[idx, "date_answered"]         = report_date_parsed
            effective.at[idx, "effective_source"]      = EFFECTIVE_SOURCE_REPORT_STATUS
            effective.at[idx, "report_memory_applied"] = True

            if has_r_status:
                effective.at[idx, "status_clean"] = report_status

            if report_comment:
                _append_comment(effective, idx, comment_text=report_comment, tag="report")

            upgraded_count += 1
            continue

        # -- RULE 3/4: NOT_CALLED -- leave as-is --

    logger.info(
        "build_effective_responses: upgraded=%d comment=%d conflict=%d stale=%d "
        "already-answered-with-report=%d total=%d flat_mode=%s",
        upgraded_count, comment_count, conflict_count, stale_count,
        already_ans_cnt, len(effective), flat_mode,
    )

    if "effective_source" in effective.columns:
        report_only = int((effective["effective_source"] == EFFECTIVE_SOURCE_REPORT_ONLY).sum())
        if report_only:
            logger.error(
                "build_effective_responses: %d REPORT_ONLY rows -- composition bug",
                report_only,
            )

    effective = effective.drop(
        columns=["report_status", "report_response_date", "report_comment", "match_confidence"],
        errors="ignore",
    )

    return effective


def _append_comment(df, idx, comment_text, status_note=None, tag="report"):
    parts = []
    if status_note:
        parts.append(str(status_note))
    if comment_text:
        parts.append(str(comment_text))
    if not parts:
        return
    addition = "[" + tag + ": " + " | ".join(parts) + "]"
    existing = str(df.at[idx, "response_comment"] or "").strip()
    df.at[idx, "response_comment"] = (existing + " " + addition).strip() if existing else addition
