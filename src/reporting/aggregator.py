"""
aggregator.py — Project-wide KPIs and summaries
Computes dashboard data from a RunContext.
When a FocusResult is supplied, every iteration is filtered to focused_doc_ids only.
"""
import logging
import math
from collections import defaultdict
from typing import Optional, TYPE_CHECKING

import pandas as pd

from .data_loader import RunContext

if TYPE_CHECKING:
    from .focus_filter import FocusResult

logger = logging.getLogger(__name__)


def _safe_str(val, fallback="?"):
    """Convert a pandas cell value to a clean string, treating NaN/None/blank as fallback."""
    if val is None:
        return fallback
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return fallback
    s = str(val).strip()
    if s in ("", "nan", "None", "NaN"):
        return fallback
    return s


def compute_project_kpis(ctx: RunContext, focus_result: Optional["FocusResult"] = None) -> dict:
    """
    Compute project-wide KPI numbers.
    If ctx.degraded_mode: returns summary_json-based approximations.
    If ctx.ged_available: computes exact numbers from DataFrames.
    If focus_result is supplied: KPIs reflect only the focused (actionable) doc set,
    and extra focus keys are included (focus_stats, focus_priority_queue).
    """
    result = {
        "run_number": ctx.run_number,
        "run_date": ctx.run_date,
        "degraded_mode": ctx.degraded_mode,
        "warnings": ctx.warnings,
    }

    if ctx.degraded_mode:
        # Fallback to summary_json (limited fields)
        s = ctx.summary_json or {}
        result.update({
            "total_docs_current": s.get("final_gf_rows", 0),
            "total_docs_all_indices": s.get("docs_total", 0),
            "by_visa_global": {},
            "by_visa_global_pct": {},
            "by_building": {},
            "by_responsible": {},
            "avg_days_to_visa": None,
            "docs_pending_sas": None,
            "docs_sas_ref_active": None,
            "total_contractors": len(ctx.gf_sheets),
            "total_consultants": 0,
            "total_lots": len(ctx.gf_sheets),
            "discrepancies_count": s.get("discrepancies_count", 0),
        })
        return result

    # Full computation from GED data
    dernier = ctx.dernier_df
    we = ctx.workflow_engine
    resp = ctx.responsible_parties or {}

    # Apply focus filter if provided
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        dernier = dernier[dernier["doc_id"].isin(focus_result.focused_doc_ids)].copy()

    # Visa global distribution
    visa_counts = defaultdict(int)
    visa_dates = []
    for _, row in dernier.iterrows():
        did = row["doc_id"]
        visa, vdate = we.compute_visa_global_with_date(did)
        if visa:
            visa_counts[visa] += 1
            if vdate and row.get("created_at") is not None:
                try:
                    delta = (vdate - row["created_at"]).days
                    if delta >= 0:
                        visa_dates.append(delta)
                except Exception:
                    pass
        else:
            visa_counts["Open"] += 1

    # Building distribution
    building_counts = defaultdict(int)
    for _, row in dernier.iterrows():
        prefix = _safe_str(row.get("lot_prefix"))
        building_map = {"A": "AU", "B": "BX", "H": "HO", "I": "IN"}
        bldg = building_map.get(prefix, prefix)
        building_counts[bldg] += 1

    # Responsible party distribution (filtered to focused set if applicable)
    resp_counts = defaultdict(int)
    focus_ids = (focus_result.focused_doc_ids
                 if (focus_result is not None and focus_result.stats.get("focus_enabled"))
                 else None)
    for doc_id, party in resp.items():
        if focus_ids is not None and doc_id not in focus_ids:
            continue
        resp_counts[party or "Closed"] += 1

    # SAS stats
    sas_pending = 0
    sas_ref_active = 0
    sas_approver = "0-SAS"
    if ctx.responses_df is not None:
        sas_rows = ctx.responses_df[ctx.responses_df["approver_raw"] == sas_approver]
        for _, sr in sas_rows.iterrows():
            if sr["date_status_type"] in ("PENDING_IN_DELAY", "PENDING_LATE"):
                sas_pending += 1
            status = str(sr.get("status_clean") or "").upper()
            if status == "REF" and sr["date_status_type"] == "ANSWERED":
                sas_ref_active += 1

    # Consultant count
    consultants = set()
    if ctx.approver_names:
        for name in ctx.approver_names:
            if name and name != "0-SAS" and not name.startswith("Sollicitation"):
                consultants.add(name)

    result.update({
        "total_docs_current": len(ctx.dernier_df),
        "total_docs_all_indices": len(ctx.docs_df) if ctx.docs_df is not None else 0,
        "by_visa_global": dict(visa_counts),
        "by_visa_global_pct": {k: round(v / max(len(dernier), 1), 4) for k, v in visa_counts.items()},
        "by_building": dict(building_counts),
        "by_responsible": dict(resp_counts),
        "avg_days_to_visa": round(sum(visa_dates) / max(len(visa_dates), 1), 1) if visa_dates else None,
        "docs_pending_sas": sas_pending,
        "docs_sas_ref_active": sas_ref_active,
        "total_contractors": len(ctx.gf_sheets),
        "total_consultants": len(consultants),
        "total_lots": len(ctx.gf_sheets),
        "discrepancies_count": ctx.summary_json.get("discrepancies_count", 0),
    })

    # Attach focus-mode extras when active
    if focus_result is not None:
        result["focus_stats"] = focus_result.stats
        result["focus_priority_queue"] = focus_result.priority_queue[:50]  # cap at 50 for JSON payload

    return result


def compute_monthly_timeseries(
    ctx: RunContext,
    focus_result: Optional["FocusResult"] = None,
) -> list:
    """
    Monthly visa distribution. Non-cumulative: each month counts new activity.
    Returns [] in degraded mode.
    When focus_result supplied, only counts documents in focused_doc_ids.
    """
    if ctx.degraded_mode or ctx.dernier_df is None or ctx.workflow_engine is None:
        return []

    we = ctx.workflow_engine
    dernier = ctx.dernier_df
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        dernier = dernier[dernier["doc_id"].isin(focus_result.focused_doc_ids)]

    monthly = defaultdict(lambda: {"vso": 0, "vao": 0, "ref": 0, "sas_ref": 0, "open": 0, "total": 0})

    for _, row in dernier.iterrows():
        did = row["doc_id"]
        created = row.get("created_at")
        if created is None or pd.isna(created):
            continue
        month_key = created.strftime("%Y-%m")

        visa, _ = we.compute_visa_global_with_date(did)
        monthly[month_key]["total"] += 1
        if visa == "VSO":
            monthly[month_key]["vso"] += 1
        elif visa == "VAO":
            monthly[month_key]["vao"] += 1
        elif visa == "REF":
            monthly[month_key]["ref"] += 1
        elif visa == "SAS REF":
            monthly[month_key]["sas_ref"] += 1
        else:
            monthly[month_key]["open"] += 1

    result = []
    for month in sorted(monthly.keys()):
        entry = {"month": month}
        entry.update(monthly[month])
        result.append(entry)
    return result


def compute_weekly_timeseries(ctx: RunContext, focus_result=None) -> list:
    """
    Weekly visa distribution for Focus Mode. Same structure as monthly
    but keyed by ISO week: "2026-S14", "2026-S15", etc.
    Returns [] in degraded mode.
    """
    if ctx.degraded_mode or ctx.dernier_df is None or ctx.workflow_engine is None:
        return []

    we = ctx.workflow_engine
    dernier = ctx.dernier_df
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        dernier = dernier[dernier["doc_id"].isin(focus_result.focused_doc_ids)]

    weekly = defaultdict(lambda: {"vso": 0, "vao": 0, "ref": 0, "sas_ref": 0, "open": 0, "total": 0})

    for _, row in dernier.iterrows():
        did = row["doc_id"]
        created = row.get("created_at")
        if created is None or pd.isna(created):
            continue
        iso = created.isocalendar()
        week_key = f"{iso[0]}-S{iso[1]:02d}"

        visa, _ = we.compute_visa_global_with_date(did)
        weekly[week_key]["total"] += 1
        if visa == "VSO":
            weekly[week_key]["vso"] += 1
        elif visa == "VAO":
            weekly[week_key]["vao"] += 1
        elif visa == "REF":
            weekly[week_key]["ref"] += 1
        elif visa == "SAS REF":
            weekly[week_key]["sas_ref"] += 1
        else:
            weekly[week_key]["open"] += 1

    result = []
    for week in sorted(weekly.keys()):
        entry = {"month": week}  # reuse "month" key for UI compat
        entry.update(weekly[week])
        result.append(entry)

    # Limit to last 26 weeks (6 months)
    if len(result) > 26:
        result = result[-26:]

    return result


def compute_consultant_summary(
    ctx: RunContext,
    focus_result: Optional["FocusResult"] = None,
) -> list:
    """
    Summary row per consultant: docs called, answered, rates, visa breakdown.
    Returns [] in degraded mode.
    When focus_result supplied, only counts responses on focused (dernier) doc_ids —
    this implements F3 (superseded responses excluded) and F2/F4 together.
    """
    if ctx.degraded_mode or ctx.responses_df is None:
        return []

    resp = ctx.responses_df
    # Exclude exception approvers and SAS
    filtered = resp[
        (~resp["is_exception_approver"]) &
        (resp["approver_raw"] != "0-SAS") &
        (~resp["approver_raw"].str.startswith("Sollicitation", na=False))
    ]

    # Apply focus filter: restrict to responses whose doc_id is in focused set
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        filtered = filtered[filtered["doc_id"].isin(focus_result.focused_doc_ids)].copy()

    summaries = []
    for name, grp in filtered.groupby("approver_canonical"):
        # Skip invalid/NaN group keys
        if name is None or (isinstance(name, float)) or str(name).strip() in ("", "nan", "None"):
            continue
        called = len(grp[grp["date_status_type"] != "NOT_CALLED"])
        answered = len(grp[grp["date_status_type"] == "ANSWERED"])
        vso = len(grp[grp["status_clean"] == "VSO"])
        vao = len(grp[grp["status_clean"] == "VAO"])
        ref = len(grp[grp["status_clean"] == "REF"])
        hm = len(grp[grp["status_clean"] == "HM"])

        # Avg response time
        answered_rows = grp[grp["date_status_type"] == "ANSWERED"]
        avg_days = None
        if not answered_rows.empty and ctx.docs_df is not None:
            days_list = []
            for _, ar in answered_rows.iterrows():
                if ar["date_answered"] is not None:
                    doc_row = ctx.docs_df[ctx.docs_df["doc_id"] == ar["doc_id"]]
                    if not doc_row.empty:
                        created = doc_row.iloc[0].get("created_at")
                        if created is not None and not pd.isna(created):
                            try:
                                delta = (ar["date_answered"] - created).days
                                if 0 <= delta <= 365:
                                    days_list.append(delta)
                            except Exception:
                                pass
            if days_list:
                avg_days = round(sum(days_list) / len(days_list), 1)

        # Count blocking opens (no visa global yet)
        blocking = 0
        if ctx.workflow_engine is not None:
            for _, ar in grp.iterrows():
                if ar["date_status_type"] in ("PENDING_IN_DELAY", "PENDING_LATE"):
                    doc_id = ar["doc_id"]
                    visa, _ = ctx.workflow_engine.compute_visa_global_with_date(doc_id)
                    if visa is None:
                        blocking += 1

        if called > 0:
            summaries.append({
                "name": name,
                "docs_called": called,
                "docs_answered": answered,
                "response_rate": round(answered / max(called, 1), 4),
                "avg_response_days": avg_days,
                "vso": vso, "vao": vao, "ref": ref, "hm": hm,
                "open": called - answered,
                "open_blocking": blocking,
            })

    summaries.sort(key=lambda x: x["docs_called"], reverse=True)

    # ── Add MOEX SAS synthetic summary row ──────────────────────────────
    sas_rows = resp[resp["approver_raw"] == "0-SAS"]
    if not sas_rows.empty:
        sas_called = len(sas_rows[sas_rows["date_status_type"] != "NOT_CALLED"])
        sas_answered = len(sas_rows[sas_rows["date_status_type"] == "ANSWERED"])

        def _sas_norm(s):
            s = str(s).upper().strip()
            if "VSO" in s: return "VSO"
            if "VAO" in s: return "VAO"
            if s == "REF": return "REF"
            return s

        sas_rows_copy = sas_rows.copy()
        sas_rows_copy["_sas_status"] = sas_rows_copy["status_clean"].apply(_sas_norm)
        sas_vso = len(sas_rows_copy[sas_rows_copy["_sas_status"] == "VSO"])
        sas_vao = len(sas_rows_copy[sas_rows_copy["_sas_status"] == "VAO"])
        sas_ref = len(sas_rows_copy[sas_rows_copy["_sas_status"] == "REF"])

        sas_avg = None
        sas_answered_rows = sas_rows_copy[sas_rows_copy["date_status_type"] == "ANSWERED"]
        if not sas_answered_rows.empty and ctx.docs_df is not None:
            days_list = []
            for _, ar in sas_answered_rows.iterrows():
                if ar["date_answered"] is not None:
                    doc_row = ctx.docs_df[ctx.docs_df["doc_id"] == ar["doc_id"]]
                    if not doc_row.empty:
                        created = doc_row.iloc[0].get("created_at")
                        if created is not None and not pd.isna(created):
                            try:
                                delta = (ar["date_answered"] - created).days
                                if 0 <= delta <= 365:
                                    days_list.append(delta)
                            except Exception:
                                pass
            if days_list:
                sas_avg = round(sum(days_list) / len(days_list), 1)

        if sas_called > 0:
            summaries.append({
                "name": "MOEX SAS",
                "docs_called": sas_called,
                "docs_answered": sas_answered,
                "response_rate": round(sas_answered / max(sas_called, 1), 4),
                "avg_response_days": sas_avg,
                "vso": sas_vso, "vao": sas_vao, "ref": sas_ref, "hm": 0,
                "open": sas_called - sas_answered,
                "open_blocking": sas_called - sas_answered,
                "is_sas": True,
            })

    # Scrub any NaN that may have leaked through
    _math = math
    for entry in summaries:
        for k, v in entry.items():
            if isinstance(v, float) and (_math.isnan(v) or _math.isinf(v)):
                entry[k] = None

    return summaries


def compute_contractor_summary(
    ctx: RunContext,
    focus_result: Optional["FocusResult"] = None,
) -> list:
    """
    Summary row per contractor (GF sheet).
    Returns [] in degraded mode.
    When focus_result supplied, only counts documents in focused_doc_ids.
    """
    if ctx.degraded_mode or ctx.dernier_df is None or ctx.workflow_engine is None:
        return []

    we = ctx.workflow_engine
    # Group dernier docs by emetteur
    by_emetteur = defaultdict(lambda: {"docs": 0, "vso": 0, "vao": 0, "ref": 0, "sas_ref": 0, "open": 0, "lots": set()})

    dernier_iter = ctx.dernier_df
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        dernier_iter = ctx.dernier_df[ctx.dernier_df["doc_id"].isin(focus_result.focused_doc_ids)]

    for _, row in dernier_iter.iterrows():
        em = _safe_str(row.get("emetteur"))
        lot = _safe_str(row.get("lot_normalized"))
        did = row["doc_id"]

        by_emetteur[em]["docs"] += 1
        by_emetteur[em]["lots"].add(lot)

        visa, _ = we.compute_visa_global_with_date(did)
        if visa == "VSO":
            by_emetteur[em]["vso"] += 1
        elif visa == "VAO":
            by_emetteur[em]["vao"] += 1
        elif visa == "REF":
            by_emetteur[em]["ref"] += 1
        elif visa == "SAS REF":
            by_emetteur[em]["sas_ref"] += 1
        else:
            by_emetteur[em]["open"] += 1

    result = []
    for em, data in by_emetteur.items():
        total = data["docs"]
        result.append({
            "name": em,
            "code": em,
            "lots": sorted(data["lots"]),
            "total_submitted": total,
            "visa_vso": data["vso"],
            "visa_vao": data["vao"],
            "visa_ref": data["ref"],
            "visa_sas_ref": data["sas_ref"],
            "visa_open": data["open"],
            "sas_ref_rate": round((data["ref"] + data["sas_ref"]) / max(total, 1), 4),
            "approval_rate": round((data["vso"] + data["vao"]) / max(total, 1), 4),
        })

    result.sort(key=lambda x: x["total_submitted"], reverse=True)

    # Scrub any NaN that may have leaked through
    _math = math
    for entry in result:
        for k, v in entry.items():
            if isinstance(v, float) and (_math.isnan(v) or _math.isinf(v)):
                entry[k] = None

    return result
