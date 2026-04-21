"""
src/domain/classification.py
-----------------------------
Pure SAS-based and missing-document classifiers extracted from main.py.

Every function here is a pure helper: no globals, no file writes, no external state mutation.
"""

import datetime as _dt


NEW_SUBMITTAL_WINDOW_DAYS = 30


def _classify_missing_in_gf(
    family:     dict,
    sas_lookup: dict,
    data_date:  _dt.date,
) -> tuple:
    """
    Part 5: Classify MISSING_IN_GF using SAS timing.

    Returns (subtype_str, severity_str).

    Priority (highest to lowest):
      PENDING_SAS          — SAS not yet reached (NOT_CALLED or PENDING_IN_DELAY)
      RECENT_SAS_REMINDER  — doc has an active rappel reminder
      RECENT_REFUSAL       — REF within 30 days
      RECENT_ACCEPTED_SAS  — VSO-SAS / VSO within 14 days
      TRUE                 — everything else (genuinely missing)
      AMBIGUOUS            — no SAS data at all
    """
    all_doc_ids = family.get("all_doc_ids", set())
    if not all_doc_ids:
        return "MISSING_IN_GF_AMBIGUOUS", "INFO"

    # Aggregate across all doc_ids (multi-submission families can have multiple)
    best: dict = {}
    for did in sorted(str(did) for did in all_doc_ids if did is not None):
        info = sas_lookup.get(did)
        if info:
            best = info
            # Prefer answered over not-called; rappel takes priority
            if info.get("has_rappel"):
                break
            if info.get("sas_status_type") == "ANSWERED":
                break

    if not best:
        return "MISSING_IN_GF_AMBIGUOUS", "INFO"

    stype   = best["sas_status_type"]
    sresult = (best.get("sas_result") or "").upper()
    sdate   = best.get("sas_date")

    # Rule 1: SAS not yet reached
    if stype in ("NOT_CALLED", "PENDING_IN_DELAY"):
        return "MISSING_IN_GF_PENDING_SAS", "INFO"

    # Rule 2: Active rappel reminder
    # Note: pre-2026 rappels already removed by _apply_sas_filter -> remaining are recent
    if best.get("has_rappel"):
        if sdate and data_date:
            try:
                diff = abs((data_date - sdate).days)
                if diff <= 30:
                    return "MISSING_IN_GF_RECENT_SAS_REMINDER", "INFO"
            except Exception:
                pass
        # Still treat as INFO even if recency unclear (post-2026 rappel)
        return "MISSING_IN_GF_RECENT_SAS_REMINDER", "INFO"

    # Rule 3: Refusal (REF)
    if "REF" in sresult:
        if sdate and data_date:
            try:
                diff = abs((data_date - sdate).days)
                if diff <= 30:
                    return "MISSING_IN_GF_RECENT_REFUSAL", "INFO"
            except Exception:
                pass
        # Old refusal: still not a true missing from GF perspective
        return "MISSING_IN_GF_RECENT_REFUSAL", "INFO"

    # Rule 4: Recently accepted
    if sresult in ("VSO-SAS", "VSO"):
        if sdate and data_date:
            try:
                diff = abs((data_date - sdate).days)
                if diff <= 14:
                    return "MISSING_IN_GF_RECENT_ACCEPTED_SAS", "INFO"
            except Exception:
                pass

    # Rule 5: True missing (accepted SAS but not in GF, not recent)
    return "MISSING_IN_GF_TRUE", "REVIEW_REQUIRED"


def _classify_new_submittal_status(
    doc_id:      str,
    is_absent:   bool,   # True if NOT found in original GF
    sas_lookup:  dict,
    data_date:   _dt.date,
    window_days: int = NEW_SUBMITTAL_WINDOW_DAYS,
) -> tuple:
    """
    Classify a single GED current doc as a new submittal or not.

    Returns: (new_submittal_status, days_from_data_date, rationale)

    new_submittal_status values:
      ALREADY_IN_GF        — doc matches a row in the original GF
      NEW_PENDING_SAS      — absent + SAS not yet answered (Case A)
      NEW_RECENT_SAS_REF   — absent + SAS REF within window (Case B)
      NEW_RECENT_SAS_APPROVED — absent + SAS VAO/VSO within window (Case C)
      NOT_NEW_BACKLOG      — absent + SAS older / doesn't fit new-window (Case D)
      AMBIGUOUS            — absent + no SAS data
    """
    if not is_absent:
        return "ALREADY_IN_GF", None, "Present in original GF"

    sas_info = sas_lookup.get(doc_id, {})
    if not sas_info:
        return "AMBIGUOUS", None, "No SAS data found for this doc"

    sas_type   = sas_info.get("sas_status_type", "NOT_CALLED")
    sas_result = (sas_info.get("sas_result") or "").upper()
    sas_date   = sas_info.get("sas_date")

    # Days from data_date (positive = sas_date is in the past relative to data_date)
    days_diff = None
    if sas_date and data_date:
        try:
            days_diff = (data_date - sas_date).days
        except Exception:
            pass

    # Case A: SAS not yet answered (pending / en attente / rappel)
    if sas_type in ("NOT_CALLED", "PENDING_IN_DELAY", "RAPPEL"):
        return "NEW_PENDING_SAS", days_diff, f"SAS pending (type={sas_type})"

    # Case B: SAS REF within window
    if "REF" in sas_result:
        if days_diff is not None and 0 <= days_diff <= window_days:
            return "NEW_RECENT_SAS_REF", days_diff, \
                f"SAS REF within {window_days} days (diff={days_diff})"
        return "NOT_NEW_BACKLOG", days_diff, \
            f"SAS REF but outside window (diff={days_diff})"

    # Case C: SAS approved (any accepted SAS status) within window
    if sas_result in ("VSO-SAS", "VAO-SAS", "VSO", "VAO"):
        if days_diff is not None and 0 <= days_diff <= window_days:
            return "NEW_RECENT_SAS_APPROVED", days_diff, \
                f"SAS {sas_result} within {window_days} days (diff={days_diff})"
        return "NOT_NEW_BACKLOG", days_diff, \
            f"SAS {sas_result} outside window (diff={days_diff})"

    # Case D: anything else (HM, SUS, unknown) not within window -> backlog
    return "NOT_NEW_BACKLOG", days_diff, \
        f"SAS result={sas_result}, type={sas_type}, diff={days_diff}"


def _classify_missing_in_ged(
    gf_num:           str,
    gf_ind:           str,
    gf_rows:          list,
    is_historical:    bool,
    is_excluded:      bool,
    gf_dup_counts:    dict,
    sheet_name:       str,
) -> str:
    """
    Part 4: Classify MISSING_IN_GED into subtypes.

    MISSING_IN_GED_TRUE             — genuinely absent from GED, actionable
    MISSING_IN_GED_HISTORICAL       — GED has this numero at a newer indice
    MISSING_IN_GED_GF_SAS_REF       — GF row was refused at SAS; may have been retracted
    MISSING_IN_GED_GF_DUPLICATE_ROW — GF has >1 row for same (num, ind)
    MISSING_IN_GED_EXCLUDED         — filtered by year threshold
    """
    if is_excluded:
        return "MISSING_IN_GED_EXCLUDED"

    if is_historical:
        return "MISSING_IN_GED_HISTORICAL"

    # GF row has SAS REF — may have been retracted from GED after refusal
    if any((row or {}).get("gf_has_sas_ref") for row in gf_rows):
        return "MISSING_IN_GED_GF_SAS_REF"

    # GF key is duplicated (>1 rows for same num/ind on same sheet)
    if gf_dup_counts.get((sheet_name, gf_num, gf_ind), 1) > 1:
        return "MISSING_IN_GED_GF_DUPLICATE_ROW"

    return "MISSING_IN_GED_TRUE"
