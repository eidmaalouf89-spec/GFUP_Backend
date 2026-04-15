"""
effective_responses.py
----------------------
Merge layer that combines GED-normalized responses with persisted
consultant report responses.

Business goal:
  GED may still show a consultant as "En attente" (pending) even though
  a consultant report already confirmed they answered.  This module
  upgrades those GED-pending rows to ANSWERED using the persisted data.

Design constraints:
  - LEFT-ANCHORED on GED responses: we only enrich rows that already
    exist in GED.  We do NOT inject brand-new workflow rows from reports.
  - The output DataFrame must be drop-in compatible with what
    WorkflowEngine.__init__ expects (same column schema as normalize_responses).
  - No raw GED columns are re-parsed here.
"""

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# GED date_status_type values that can be upgraded by report memory
_UPGRADEABLE_STATUSES = {"PENDING_IN_DELAY", "PENDING_LATE"}

# Provenance tags added to the output
_SOURCE_GED           = "GED"
_SOURCE_REPORT_MEMORY = "REPORT_MEMORY"

# Text → float confidence map (canonical keys in upper-case)
_CONF_TEXT_MAP = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_confidence(v) -> float:
    """
    Convert any confidence representation to a float in [0, 1].

    Accepts:
      - float / int already in numeric form  → cast directly
      - text labels "HIGH" / "MEDIUM" / "LOW" (case-insensitive)
      - None or unrecognised values           → -1.0 (sorts last)
    """
    if v is None:
        return -1.0
    if isinstance(v, (int, float)):
        return float(v)
    mapped = _CONF_TEXT_MAP.get(str(v).strip().upper())
    return mapped if mapped is not None else -1.0


def _parse_date_flexible(value) -> Optional[pd.Timestamp]:
    """
    Try to parse a date value coming from consultant reports.
    Handles: None, datetime strings ("23/12/2025", "2025-12-23"), pd.Timestamp.
    Returns pd.NaT if parsing fails.
    """
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


# ---------------------------------------------------------------------------
# Helper: normalise persisted responses for merge
# ---------------------------------------------------------------------------

def normalize_persisted_report_responses_for_merge(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise persisted_report_responses DataFrame for use in
    build_effective_responses.

    Input columns (as loaded from report_memory.load_persisted_report_responses):
        consultant, doc_id, report_status, report_response_date,
        report_comment, source_filename, source_file_hash,
        ingested_at, match_confidence, match_method

    Output:
        One row per (doc_id, approver_canonical), keeping the best answer
        when duplicates exist.

    A row is considered MERGE-ELIGIBLE if at least one of these is present:
        - non-empty  report_status
        - non-empty  report_response_date

    Winner selection priority:
        1. Highest normalised confidence (float, DESCENDING)
        2. Latest  report_response_date  (DESCENDING; NaT sorts last)
        3. Latest  ingested_at           (DESCENDING)

    Returns an empty DataFrame with the correct columns if input is empty.
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

    # Rename 'consultant' → 'approver_canonical' to match GED schema
    work = work.rename(columns={"consultant": "approver_canonical"})

    # Drop rows without the core identity fields
    work = work.dropna(subset=["doc_id", "approver_canonical"])
    work = work[
        (work["doc_id"].astype(str).str.strip() != "") &
        (work["approver_canonical"].astype(str).str.strip() != "")
    ]

    if work.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    # ── Eligibility filter ────────────────────────────────────────────────────
    # Keep a row only when it carries at least one meaningful answer field.
    has_status = work["report_status"].apply(lambda v: not _is_blank(v))
    has_date   = work["report_response_date"].apply(lambda v: not _is_blank(v))
    work = work[has_status | has_date].copy()

    if work.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    # ── Confidence normalisation ──────────────────────────────────────────────
    # DB stores REAL (float); source data may arrive as text ("HIGH") or float.
    # Build a normalised float column for sorting (higher = better).
    work["_conf_norm"] = work["match_confidence"].apply(_normalize_confidence)

    # ── Date columns for sorting ──────────────────────────────────────────────
    work["_parsed_date"]      = work["report_response_date"].apply(_parse_date_flexible)
    work["_parsed_ingested"]  = pd.to_datetime(
        work["ingested_at"], errors="coerce", utc=True
    )

    # ── Sort: best answer first ───────────────────────────────────────────────
    # 1. _conf_norm           DESC  (higher confidence wins)
    # 2. _parsed_date         DESC  (more recent response date wins; NaT → last)
    # 3. _parsed_ingested     DESC  (more recently ingested wins; NaT → last)
    work = work.sort_values(
        ["doc_id", "approver_canonical",
         "_conf_norm", "_parsed_date", "_parsed_ingested"],
        ascending=[True, True, False, False, False],
        na_position="last",
    )

    # Keep first (= winner) per (doc_id, approver_canonical)
    best = work.drop_duplicates(subset=["doc_id", "approver_canonical"], keep="first")

    # Drop temporary sort columns
    best = best.drop(
        columns=["_conf_norm", "_parsed_date", "_parsed_ingested"],
        errors="ignore",
    )

    logger.debug(
        "normalize_persisted_report_responses_for_merge: "
        "%d unique (doc_id, approver) pairs after eligibility filter",
        len(best),
    )

    # Return only the expected columns (extras dropped for safety)
    return best[[c for c in _OUT_COLS if c in best.columns]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Main merge function
# ---------------------------------------------------------------------------

def build_effective_responses(
    ged_responses_df: pd.DataFrame,
    persisted_report_responses_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge GED-normalized responses with persisted consultant report responses.

    Merge rules (applied per (doc_id, approver_canonical) pair):

      Rule 1 — GED already ANSWERED:
        Keep GED as source of truth.  Report memory is not applied.

      Rule 2 — GED is PENDING (PENDING_IN_DELAY / PENDING_LATE) and report
               memory has an eligible response for the same pair:
        An "eligible" report response has a non-empty report_response_date
        OR a non-empty report_status (at least one must be present).
        → Upgrade to ANSWERED using report data.
        → Sets: date_status_type="ANSWERED", date_answered (from report date),
                effective_source="REPORT_MEMORY", report_memory_applied=True.
        → Sets status_clean from report ONLY when report_status is non-empty;
          otherwise the existing GED status_clean is preserved.
        → Appends report_comment to existing GED response_comment.

      Rule 3 — GED is PENDING and no eligible report answer exists:
        Keep GED pending.  effective_source="GED".

      Rule 4 — GED is NOT_CALLED:
        Left as-is.  We do NOT promote NOT_CALLED rows from report memory
        (would invent workflow routes not present in GED).

    Parameters
    ----------
    ged_responses_df : pd.DataFrame
        Output of normalize_responses() — the GED-only normalized responses.
        Must contain: doc_id, approver_canonical, date_answered,
                      date_status_type, status_clean, response_comment,
                      is_exception_approver.

    persisted_report_responses_df : pd.DataFrame
        Output of normalize_persisted_report_responses_for_merge() (or the
        raw load from report_memory.load_persisted_report_responses()).
        Must contain: doc_id, approver_canonical, report_status,
                      report_response_date, report_comment.

    Returns
    -------
    pd.DataFrame
        Same shape as ged_responses_df plus two extra columns:
          effective_source      : "GED" | "REPORT_MEMORY"
          report_memory_applied : bool
    """
    if ged_responses_df is None or ged_responses_df.empty:
        logger.warning("build_effective_responses: ged_responses_df is empty — returning as-is")
        result = ged_responses_df.copy() if ged_responses_df is not None else pd.DataFrame()
        result["effective_source"]      = _SOURCE_GED
        result["report_memory_applied"] = False
        return result

    # Work on a copy — never mutate the caller's DataFrame
    effective = ged_responses_df.copy()
    effective["effective_source"]      = _SOURCE_GED
    effective["report_memory_applied"] = False

    # If there are no persisted responses, return GED as-is (fast path)
    norm_report = normalize_persisted_report_responses_for_merge(persisted_report_responses_df)
    if norm_report.empty:
        logger.info("build_effective_responses: no persisted report responses — using GED only")
        return effective

    # ── Left join: attach best report answer to each GED row ─────────────────
    # We join on (doc_id, approver_canonical).
    # Only GED rows that are PENDING will actually be upgraded (see loop below).
    effective = effective.merge(
        norm_report[[
            "doc_id", "approver_canonical",
            "report_status", "report_response_date", "report_comment",
        ]],
        on=["doc_id", "approver_canonical"],
        how="left",
        suffixes=("", "_report"),
    )

    # ── Identify upgrade candidates ───────────────────────────────────────────
    # Condition: GED row is PENDING  AND  report carries at least one answer field
    pending_mask = effective["date_status_type"].isin(_UPGRADEABLE_STATUSES)

    report_has_status = effective["report_status"].apply(lambda v: not _is_blank(v))
    report_has_date   = effective["report_response_date"].apply(lambda v: not _is_blank(v))
    report_eligible   = report_has_status | report_has_date

    upgrade_mask = pending_mask & report_eligible

    # Rule 1: already ANSWERED in GED → log count, leave untouched
    answered_mask = effective["date_status_type"] == "ANSWERED"
    already_answered_with_report = int((answered_mask & report_eligible).sum())

    # Apply Rule 2: upgrade PENDING rows where report has an eligible answer
    upgrades_applied = 0

    for idx in effective[upgrade_mask].index:
        row = effective.loc[idx]

        report_date_raw  = row.get("report_response_date")
        report_date_parsed = _parse_date_flexible(report_date_raw)

        report_status  = None if _is_blank(row.get("report_status"))  else str(row.get("report_status")).strip()
        report_comment = None if _is_blank(row.get("report_comment")) else str(row.get("report_comment")).strip()

        # Core upgrade: mark as ANSWERED, set response date
        effective.at[idx, "date_status_type"]    = "ANSWERED"
        effective.at[idx, "date_answered"]        = report_date_parsed
        effective.at[idx, "effective_source"]     = _SOURCE_REPORT_MEMORY
        effective.at[idx, "report_memory_applied"] = True

        # Only overwrite status_clean when report actually provides a status
        if report_status is not None:
            effective.at[idx, "status_clean"] = report_status
        # else: preserve existing GED status_clean unchanged

        # Append report comment to existing GED comment (or replace if GED empty)
        if report_comment:
            existing_comment = str(row.get("response_comment", "") or "").strip()
            if existing_comment:
                effective.at[idx, "response_comment"] = (
                    f"{existing_comment} [report: {report_comment}]"
                )
            else:
                effective.at[idx, "response_comment"] = f"[report: {report_comment}]"

        upgrades_applied += 1

    logger.info(
        "build_effective_responses: %d rows upgraded from PENDING→ANSWERED via report memory "
        "| %d already-ANSWERED rows had report data (GED kept) "
        "| total GED rows: %d",
        upgrades_applied, already_answered_with_report, len(effective),
    )

    # Drop the temporary report columns we joined — keep output schema clean
    effective = effective.drop(
        columns=["report_status", "report_response_date", "report_comment"],
        errors="ignore",
    )

    return effective
