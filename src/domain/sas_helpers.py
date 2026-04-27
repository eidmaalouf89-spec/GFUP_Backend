"""
src/domain/sas_helpers.py
-------------------------
Pure SAS filter and lookup helpers extracted from main.py.

Every function here is a pure helper: no globals, no file writes, no external state mutation.
"""

import re as _re
import datetime as _dt

import pandas as pd


def _apply_sas_filter(
    docs_df: pd.DataFrame,
    responses_df: pd.DataFrame,
) -> tuple:
    """
    Business rule: Documents that are simultaneously:
      (a) still pending SAS visa with a reminder ("Rappel : En attente visa ..."),
      (b) created BEFORE 2026

    are considered INVALID (old unresolved SAS items) and must be removed
    entirely from processing — before version engine, routing, discrepancy.

    Detection:
      - The '0-SAS' approver column in responses_df is the SAS visa track
      - If response_date_raw for 0-SAS contains "rappel" (case-insensitive)
        -> the SAS visa is still pending with a reminder = stale unresolved
      - Cross-reference doc created_at year < 2026

    Returns:
      (docs_df_clean, responses_df_clean, sas_filtered_df)
    """
    SAS_APPROVER = "0-SAS"
    RAPPEL_TOKEN = "rappel"

    # Step 1: Find doc_ids where 0-SAS has "Rappel" in date_raw
    sas_rows = responses_df[responses_df["approver_raw"] == SAS_APPROVER].copy()
    sas_rappel = sas_rows[
        sas_rows["response_date_raw"].apply(
            lambda x: isinstance(x, str) and RAPPEL_TOKEN in str(x).lower()
        )
    ]
    sas_rappel_doc_ids: set = set(sas_rappel["doc_id"].unique())

    if not sas_rappel_doc_ids:
        return docs_df, responses_df, pd.DataFrame()

    # Step 2: Cross with docs created before 2026
    sas_candidates = docs_df[docs_df["doc_id"].isin(sas_rappel_doc_ids)].copy()
    sas_candidates["_year"] = pd.to_datetime(
        sas_candidates["created_at"], errors="coerce"
    ).dt.year
    invalid_mask = sas_candidates["_year"] < 2026
    invalid_doc_ids: set = set(sas_candidates.loc[invalid_mask, "doc_id"].tolist())

    if not invalid_doc_ids:
        return docs_df, responses_df, pd.DataFrame()

    # Step 3: Extract filtered rows for logging
    sas_filtered_df = docs_df[docs_df["doc_id"].isin(invalid_doc_ids)].copy()
    sas_filtered_df["sas_status"] = "RAPPEL_EN_ATTENTE"

    # Step 4: Remove from both DataFrames
    docs_clean = docs_df[~docs_df["doc_id"].isin(invalid_doc_ids)].copy()
    responses_clean = responses_df[~responses_df["doc_id"].isin(invalid_doc_ids)].copy()

    return docs_clean, responses_clean, sas_filtered_df


def _build_sas_lookup(responses_df: pd.DataFrame) -> dict:
    """
    Build per-doc SAS status lookup from GED responses.

    Returns: {doc_id: {sas_status_type, sas_result, sas_date, has_rappel}}
      sas_status_type: ANSWERED | PENDING_IN_DELAY | NOT_CALLED | RAPPEL
      sas_result:      VSO-SAS | REF | VSO | HM | RAPPEL | None
      sas_date:        date object (response date) or None
      has_rappel:      bool
    """
    SAS_APPROVER = "0-SAS"
    RAPPEL_TOKEN = "rappel"
    DATE_RE      = _re.compile(r'\((\d{4}/\d{2}/\d{2})\)')

    sas = responses_df[responses_df["approver_raw"] == SAS_APPROVER].copy()
    if sas.empty:
        return {}

    lookup: dict = {}
    for doc_id, grp in sas.groupby("doc_id"):
        # Check for rappel in any response_date_raw
        has_rappel = grp["response_date_raw"].apply(
            lambda x: isinstance(x, str) and RAPPEL_TOKEN in str(x).lower()
        ).any()

        answered = grp[grp["date_status_type"] == "ANSWERED"]
        pending  = grp[grp["date_status_type"] == "PENDING_IN_DELAY"]

        if has_rappel:
            sas_status_type = "RAPPEL"
            sas_result      = "RAPPEL"
            sas_date        = None
            # Extract date from "Rappel : En attente visa (YYYY/MM/DD)"
            for _, r in grp[grp["response_date_raw"].apply(
                lambda x: isinstance(x, str) and RAPPEL_TOKEN in str(x).lower()
            )].iterrows():
                m = DATE_RE.search(str(r["response_date_raw"]))
                if m:
                    try:
                        sas_date = _dt.date.fromisoformat(m.group(1).replace("/", "-"))
                    except Exception:
                        pass
                    break
        elif not answered.empty:
            sas_status_type = "ANSWERED"
            best = answered.sort_values("date_answered", ascending=False, na_position="last").iloc[0]
            sas_result = str(best.get("status_clean") or best.get("response_status_raw") or "")
            raw_date   = best.get("date_answered")
            try:
                sas_date = pd.to_datetime(raw_date).date()
            except Exception:
                sas_date = None
        elif not pending.empty:
            sas_status_type = "PENDING_IN_DELAY"
            sas_result      = "PENDING"
            sas_date        = None
        else:
            sas_status_type = "NOT_CALLED"
            sas_result      = None
            sas_date        = None

        lookup[doc_id] = {
            "sas_status_type": sas_status_type,
            "sas_result":      sas_result,
            "sas_date":        sas_date,
            "has_rappel":      bool(has_rappel),
        }
    return lookup
