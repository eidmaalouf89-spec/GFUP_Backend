"""
contractor_fiche.py — Per-contractor fiche builder
Builds submission timeline, VISA chart, document table, quality metrics
"""
import math
import logging
from collections import defaultdict

import pandas as pd

from .data_loader import RunContext
from .consultant_fiche import CONTRACTOR_REFERENCE

logger = logging.getLogger(__name__)


def resolve_emetteur_name(code: str) -> str:
    """Return canonical company name for an emetteur code (e.g. 'BEN' → 'Bentin').
    Falls back to the input code if unmapped or empty."""
    if not code:
        return ""
    entry = CONTRACTOR_REFERENCE.get(str(code).strip().upper())
    if entry and entry.get("name"):
        return entry["name"]
    return str(code)


def _safe_str(val):
    if val is None:
        return "?"
    if isinstance(val, float) and math.isnan(val):
        return "?"
    s = str(val).strip()
    return s if s and s.lower() not in ("nan", "none", "") else "?"


def build_contractor_fiche(ctx: RunContext, contractor_code: str,
                           focus_result=None) -> dict:
    """
    Build the complete fiche for one contractor (emetteur).

    Filters docs_df for this emetteur, then computes:
      - Header KPIs
      - Block 1: submission timeline (monthly new + re-submissions)
      - Block 2: VISA result chart (monthly visa distribution)
      - Block 3: document table (per-document detail for dernier indice)
      - Block 4: quality metrics (SAS REF rate, avg revisions, avg delay)
    """
    if ctx.degraded_mode or ctx.docs_df is None:
        return {
            "contractor_name": contractor_code, "contractor_code": contractor_code,
            "degraded_mode": True, "warnings": ctx.warnings,
            "lots": [], "buildings": [], "gf_sheets": [],
            "total_submitted": 0, "total_current": 0,
            "block1_submission_timeline": [], "block2_visa_chart": [],
            "block3_document_table": [], "block4_quality": {},
        }

    docs = ctx.docs_df
    we = ctx.workflow_engine

    # Filter docs for this contractor
    contractor_docs = docs[docs["emetteur"] == contractor_code].copy()
    if contractor_docs.empty:
        return {
            "contractor_name": contractor_code, "contractor_code": contractor_code,
            "degraded_mode": False, "warnings": [f"No docs found for {contractor_code}"],
            "lots": [], "buildings": [], "gf_sheets": [],
            "total_submitted": 0, "total_current": 0,
            "block1_submission_timeline": [], "block2_visa_chart": [],
            "block3_document_table": [], "block4_quality": {},
        }

    # Get dernier indice docs for this contractor
    dernier = None
    if ctx.dernier_df is not None:
        dernier = ctx.dernier_df[ctx.dernier_df["emetteur"] == contractor_code].copy()

    # Focus filter: compute focused_ids but do NOT filter dernier yet
    # Charts and tables need full history; only open counts use focused set
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    focused_ids = None
    if focus_enabled and dernier is not None:
        focused_df = getattr(focus_result, 'focused_df', None)
        if focused_df is not None and "_focus_owner_tier" in focused_df.columns:
            contractor_focused = focused_df[
                focused_df["emetteur"] == contractor_code
            ]
            focused_ids = set(contractor_focused["doc_id"].tolist())
        else:
            focused_ids = set(
                did for did in focus_result.focused_doc_ids
                if did in set(dernier["doc_id"].tolist())
            )

    # Metadata
    lots = sorted(set(_safe_str(v) for v in contractor_docs["lot_normalized"].unique() if _safe_str(v) != "?"))
    buildings = sorted(set(_safe_str(v) for v in contractor_docs["lot_prefix"].unique() if _safe_str(v) != "?"))
    total_submitted = len(contractor_docs)
    total_current = len(dernier) if dernier is not None else 0

    # Match to GF sheets
    gf_sheets = []
    for sheet_name, info in ctx.gf_sheets.items():
        code = info.get("contractor_code", "")
        if code.upper() == contractor_code.upper():
            gf_sheets.append(sheet_name)

    # ── Block 1: Submission timeline ──────────────────────────────────
    monthly_sub = defaultdict(lambda: {"new_submissions": 0, "re_submissions": 0, "sas_ref": 0, "sas_vao": 0})

    for _, row in contractor_docs.iterrows():
        dt = row.get("created_at")
        if dt is None or pd.isna(dt):
            continue
        try:
            mk = dt.strftime("%Y-%m")
        except Exception:
            continue
        indice = _safe_str(row.get("indice"))
        if indice == "A" or indice == "?" or indice == "0" or indice == "1":
            monthly_sub[mk]["new_submissions"] += 1
        else:
            monthly_sub[mk]["re_submissions"] += 1

    # Enrich with SAS data if workflow engine available
    if we is not None:
        for _, row in contractor_docs.iterrows():
            did = row["doc_id"]
            dt = row.get("created_at")
            if dt is None or pd.isna(dt):
                continue
            try:
                mk = dt.strftime("%Y-%m")
            except Exception:
                continue
            visa, _ = we.compute_visa_global_with_date(did)
            if visa == "SAS REF":
                monthly_sub[mk]["sas_ref"] += 1
            elif visa in ("VSO", "VAO"):
                monthly_sub[mk]["sas_vao"] += 1

    block1 = [{"month": m, **monthly_sub[m]} for m in sorted(monthly_sub.keys())]

    # Focus mode: rebuild block1 as weekly
    if focus_enabled:
        weekly_sub = defaultdict(lambda: {"new_submissions": 0, "re_submissions": 0, "sas_ref": 0, "sas_vao": 0})
        for _, row in contractor_docs.iterrows():
            dt = row.get("created_at")
            if dt is None or pd.isna(dt):
                continue
            try:
                iso = dt.isocalendar()
                wk = f"{iso[0]}-S{iso[1]:02d}"
            except Exception:
                continue
            indice = _safe_str(row.get("indice"))
            if indice in ("A", "?", "0", "1"):
                weekly_sub[wk]["new_submissions"] += 1
            else:
                weekly_sub[wk]["re_submissions"] += 1
        # SAS enrichment
        if we is not None:
            for _, row in contractor_docs.iterrows():
                did = row["doc_id"]
                dt = row.get("created_at")
                if dt is None or pd.isna(dt):
                    continue
                try:
                    iso = dt.isocalendar()
                    wk = f"{iso[0]}-S{iso[1]:02d}"
                except Exception:
                    continue
                visa, _ = we.compute_visa_global_with_date(did)
                if visa == "SAS REF":
                    weekly_sub[wk]["sas_ref"] += 1
                elif visa in ("VSO", "VAO"):
                    weekly_sub[wk]["sas_vao"] += 1
        sorted_weeks = sorted(weekly_sub.keys())
        if len(sorted_weeks) > 26:
            sorted_weeks = sorted_weeks[-26:]
        block1 = [{"month": w, **weekly_sub[w]} for w in sorted_weeks]

    # ── Block 2: VISA result chart ────────────────────────────────────
    monthly_visa = defaultdict(lambda: {"vso": 0, "vao": 0, "ref": 0, "sas_ref": 0, "open": 0, "total": 0})

    if dernier is not None and we is not None:
        for _, row in dernier.iterrows():
            dt = row.get("created_at")
            if dt is None or pd.isna(dt):
                continue
            try:
                mk = dt.strftime("%Y-%m")
            except Exception:
                continue
            did = row["doc_id"]
            visa, _ = we.compute_visa_global_with_date(did)
            monthly_visa[mk]["total"] += 1
            if visa == "VSO":
                monthly_visa[mk]["vso"] += 1
            elif visa == "VAO":
                monthly_visa[mk]["vao"] += 1
            elif visa == "REF":
                monthly_visa[mk]["ref"] += 1
            elif visa == "SAS REF":
                monthly_visa[mk]["sas_ref"] += 1
            else:
                monthly_visa[mk]["open"] += 1

    block2 = [{"month": m, **monthly_visa[m]} for m in sorted(monthly_visa.keys())]

    # Focus mode: rebuild block2 as weekly
    if focus_enabled and dernier is not None and we is not None:
        weekly_visa = defaultdict(lambda: {"vso": 0, "vao": 0, "ref": 0, "sas_ref": 0, "open": 0, "total": 0})
        for _, row in dernier.iterrows():
            dt = row.get("created_at")
            if dt is None or pd.isna(dt):
                continue
            try:
                iso = dt.isocalendar()
                wk = f"{iso[0]}-S{iso[1]:02d}"
            except Exception:
                continue
            did = row["doc_id"]
            visa, _ = we.compute_visa_global_with_date(did)
            weekly_visa[wk]["total"] += 1
            if visa == "VSO":
                weekly_visa[wk]["vso"] += 1
            elif visa == "VAO":
                weekly_visa[wk]["vao"] += 1
            elif visa == "REF":
                weekly_visa[wk]["ref"] += 1
            elif visa == "SAS REF":
                weekly_visa[wk]["sas_ref"] += 1
            else:
                if focused_ids is not None:
                    if did in focused_ids:
                        weekly_visa[wk]["open"] += 1
                else:
                    weekly_visa[wk]["open"] += 1
        sorted_wks = sorted(weekly_visa.keys())
        if len(sorted_wks) > 26:
            sorted_wks = sorted_wks[-26:]
        block2 = [{"month": w, **weekly_visa[w]} for w in sorted_wks]

    # ── Block 3: Document table (dernier indice only) ─────────────────
    block3 = []
    if dernier is not None and we is not None:
        for _, row in dernier.iterrows():
            did = row["doc_id"]
            visa, vdate = we.compute_visa_global_with_date(did)

            # Get SAS result from responses
            sas_result = None
            if ctx.responses_df is not None:
                sas_rows = ctx.responses_df[
                    (ctx.responses_df["doc_id"] == did) &
                    (ctx.responses_df["approver_raw"] == "0-SAS")
                ]
                if not sas_rows.empty:
                    sas_result = _safe_str(sas_rows.iloc[0].get("status_clean"))

            created = row.get("created_at")
            # Add ownership info for focus mode
            owner_tier = None
            days_to_dl = None
            focus_priority = None
            if focus_enabled and "_focus_owner_tier" in row.index:
                owner_tier = _safe_str(row.get("_focus_owner_tier"))
                dtd = row.get("_days_to_deadline")
                if dtd is not None and not (isinstance(dtd, float) and math.isnan(dtd)):
                    days_to_dl = int(dtd)
                fp = row.get("_focus_priority")
                if fp is not None and not (isinstance(fp, float) and math.isnan(fp)):
                    focus_priority = int(fp)

            block3.append({
                "_doc_id": did,
                "numero": _safe_str(row.get("numero_normalized")),
                "indice": _safe_str(row.get("indice")),
                "titre": _safe_str(row.get("libelle_du_document") or row.get("lib_ll_du_document")),
                "type_doc": _safe_str(row.get("type_de_doc")),
                "sas_result": sas_result or "-",
                "visa_global": visa or "-",
                "date_submitted": str(created.date()) if created and not pd.isna(created) else "-",
                "date_visa": str(vdate.date()) if vdate and not pd.isna(vdate) else "-",
                "status": "Open" if visa is None else visa,
                "owner_tier": owner_tier,
                "days_to_deadline": days_to_dl,
                "focus_priority": focus_priority,
            })

    # Focus mode: mark non-focused open docs and filter block3 for display
    if focus_enabled and focused_ids is not None:
        for row_dict in block3:
            is_open = row_dict["status"] == "Open"
            doc_id_val = row_dict.get("_doc_id")
            if is_open and doc_id_val and doc_id_val not in focused_ids:
                row_dict["_excluded_by_focus"] = True
        # Remove excluded open docs from block3 (keep all resolved docs for history)
        block3 = [r for r in block3 if not r.get("_excluded_by_focus", False)]

    block3.sort(key=lambda x: x["numero"])

    # Clean up internal fields
    for row_dict in block3:
        row_dict.pop("_doc_id", None)
        row_dict.pop("_excluded_by_focus", None)

    # ── Block 4: Quality metrics ──────────────────────────────────────
    visa_counts = defaultdict(int)
    visa_days = []
    if dernier is not None and we is not None:
        for _, row in dernier.iterrows():
            did = row["doc_id"]
            visa, vdate = we.compute_visa_global_with_date(did)
            visa_counts[visa or "Open"] += 1
            if vdate and row.get("created_at") and not pd.isna(row["created_at"]):
                try:
                    delta = (vdate - row["created_at"]).days
                    if 0 <= delta <= 365:
                        visa_days.append(delta)
                except Exception:
                    pass

    # Avg revision cycles: count unique indices per numero for this contractor
    if not contractor_docs.empty:
        indices_per_num = contractor_docs.groupby("numero_normalized")["indice"].nunique()
        avg_revisions = round(indices_per_num.mean(), 1) if len(indices_per_num) > 0 else 1.0
    else:
        avg_revisions = 1.0

    block4 = {
        "sas_refusal_rate": round((visa_counts.get("SAS REF", 0) + visa_counts.get("REF", 0)) / max(total_current, 1), 4),
        "avg_revision_cycles": avg_revisions,
        "avg_days_to_visa": round(sum(visa_days) / len(visa_days), 1) if visa_days else None,
        "docs_a_reprendre": visa_counts.get("REF", 0) + visa_counts.get("SAS REF", 0),
        "docs_pending_consultant": visa_counts.get("Open", 0),
        "docs_pending_moex": 0,  # Would need responsible_party computation
    }

    # Focus summary: how many docs the contractor must act on
    focus_summary = None
    if focus_enabled and focused_ids is not None and dernier is not None and "_focus_owner_tier" in dernier.columns:
        focused_dernier = dernier[dernier["doc_id"].isin(focused_ids)]
        contractor_owned = int((focused_dernier["_focus_owner_tier"] == "CONTRACTOR").sum())
        in_review = int(
            focused_dernier["_focus_owner_tier"].isin(["PRIMARY", "SECONDARY", "MOEX"]).sum()
        )
        focus_summary = {
            "docs_to_resubmit": contractor_owned,
            "docs_in_review": in_review,
            "total_focused": len(focused_dernier),
        }

    return {
        "contractor_name": contractor_code,
        "contractor_code": contractor_code,
        "degraded_mode": False,
        "warnings": [],
        "lots": lots,
        "buildings": buildings,
        "gf_sheets": gf_sheets,
        "total_submitted": total_submitted,
        "total_current": total_current,
        "block1_submission_timeline": block1,
        "block2_visa_chart": block2,
        "block3_document_table": block3,
        "block4_quality": block4,
        "focus_enabled": bool(focus_enabled),
        "focus_summary": focus_summary,
    }
