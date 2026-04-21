"""
src/reporting/consultant_fiche.py

Per-consultant fiche data builder. Output shape matches fiche.jsx's
window.FICHE_DATA contract (see GFUP_REPORTING_ARCHITECTURE_SPEC_v1_2.md §6.4
and the fiche.jsx field schema).

Source of truth: GED dump. GF is used only for sheet/lot structure.
DATA_DATE comes from ctx.data_date (extracted from GED's Détails sheet upstream).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from .data_loader import RunContext

# ══════════════════════════════════════════════════════════════════════════════
# DEFINITIVE PROJECT REFERENCE — P17&CO Tranche 2
# Hardcoded from full GED + Mapping.xlsx cross-reference (2026-04-20)
# ══════════════════════════════════════════════════════════════════════════════

# Canonical name (from Mapping.xlsx) → company display name
CONSULTANT_DISPLAY_NAMES = {
    "AMO HQE":              "Le Sommer Environnement",
    "ARCHITECTE":           "Hardel + Le Bihan Architectes",
    "BET Acoustique":       "AVLS",
    "BET Ascenseur":        "BET Ascenseur",
    "BET CVC":              "BET CVC",
    "BET Electricité":      "BET Electricité",
    "BET EV":               "BET EV",
    "BET Façade":           "BET Façade",
    "BET Plomberie":        "BET Plomberie",
    "BET POL":              "BET POL",
    "BET SPK":              "BET SPK",
    "BET Structure":        "Terrell",
    "BET VRD":              "BET VRD",
    "Bureau de Contrôle":   "SOCOTEC",
    "Maître d'Oeuvre EXE":  "GEMO",
    "MOEX SAS":             "GEMO (SAS)",
}

# Canonical name → role label for display
ROLE_BY_CANONICAL = {
    "AMO HQE":              "AMO HQE (Le Sommer)",
    "ARCHITECTE":           "Architecte (Hardel + Le Bihan)",
    "BET Acoustique":       "BET Acoustique (AVLS)",
    "BET Ascenseur":        "BET Ascenseur",
    "BET CVC":              "BET CVC",
    "BET Electricité":      "BET Electricité",
    "BET EV":               "BET Espaces Verts",
    "BET Façade":           "BET Façade",
    "BET Plomberie":        "BET Plomberie",
    "BET POL":              "BET Pollution",
    "BET SPK":              "BET Sprinkler",
    "BET Structure":        "BET Structure (Terrell)",
    "BET VRD":              "BET VRD",
    "Bureau de Contrôle":   "Bureau de Contrôle (SOCOTEC)",
    "Maître d'Oeuvre EXE":  "MOEX (GEMO)",
    "MOEX SAS":             "Conformité SAS (GEMO)",
}

# Status vocabulary per consultant.
# s1=approved, s2=approved-with-remarks, s3=refused.
# Most consultants use VSO/VAO/REF. Bureau de Contrôle uses FAV/SUS/DEF.
STATUS_LABELS_BY_CANONICAL = {
    "Bureau de Contrôle": {"s1": "FAV", "s2": "SUS", "s3": "DEF"},
    "MOEX SAS": {"s1": "VSO", "s2": "VAO", "s3": "REF"},
    # All others default to VSO/VAO/REF — no entry needed
}

# BET consultants with PDF report merge (non-saisi-GED tracking)
BET_MERGE_KEYS = {
    "BET Acoustique":     "AVLS",
    "Bureau de Contrôle": "SOCOTEC",
    "AMO HQE":            "LeSommer",
    "BET Structure":      "Terrell",    # OBS-ONLY: status from GED, observations from PDF
}

# Company short name → canonical (for reverse lookup from UI or legacy references)
COMPANY_TO_CANONICAL = {
    "SOCOTEC":    "Bureau de Contrôle",
    "AVLS":       "BET Acoustique",
    "Terrell":    "BET Structure",
    "Le Sommer":  "AMO HQE",
    "LeSommer":   "AMO HQE",
    "GEMO":       "Maître d'Oeuvre EXE",
    "MOX":        "ARCHITECTE",
}

# Contractor (EMETTEUR) code → display name + lots
# From GED docs analysis (2026-04-20)
CONTRACTOR_REFERENCE = {
    "LGD":  {"name": "Legendre",           "lots": ["03", "07", "06B"]},
    "BEN":  {"name": "Bentin",             "lots": ["31", "33", "34"]},
    "SNI":  {"name": "SNIE",               "lots": ["31", "33", "34"]},
    "AXI":  {"name": "Axima",              "lots": ["41"]},
    "UTB":  {"name": "UTB",                "lots": ["42"]},
    "DUV":  {"name": "Duval",              "lots": ["08", "13A"]},
    "LAC":  {"name": "Lacroix",            "lots": ["12", "12A"]},
    "AMP":  {"name": "AMP / CLD",          "lots": ["11", "16A"]},
    "AAI":  {"name": "AAI",                "lots": ["43"]},
    "SMA":  {"name": "SMAC",               "lots": ["04", "06B"]},
    "ICM":  {"name": "ICM",                "lots": ["05"]},
    "FRS":  {"name": "France Sols",         "lots": ["18", "19"]},
    "API":  {"name": "Apilog / Schneider",  "lots": ["35"]},
    "FER":  {"name": "Fermeté",            "lots": ["06", "13", "14"]},
    "CMF":  {"name": "CMF BAT",            "lots": ["18"]},
    "SPA":  {"name": "SEPA",               "lots": ["61", "62"]},
    "SCH":  {"name": "Schindler",          "lots": ["51"]},
    "LIN":  {"name": "Lindner",            "lots": ["16B"]},
    "IST":  {"name": "IST",                "lots": ["11", "16", "12B"]},
    "CHV":  {"name": "Atchouel",           "lots": ["13"]},
    "VAL":  {"name": "Vallée",             "lots": ["19"]},
    "CPL":  {"name": "CPLC",               "lots": ["12B"]},
    "VTP":  {"name": "VTP",                "lots": ["01"]},
    "CRE":  {"name": "Créa Diffusion",     "lots": ["42B"]},
    "FKI":  {"name": "FKI",                "lots": ["02"]},
    "BAN":  {"name": "Bangui",             "lots": ["17"]},
    "FMC":  {"name": "FMC",                "lots": ["13B"]},
    "JLE":  {"name": "Jean Letuvé",        "lots": ["20"]},
    "DBH":  {"name": "DBH",                "lots": ["20"]},
    "HVA":  {"name": "HVA Concept",        "lots": ["22"]},
}


def resolve_consultant_name(name: str) -> str:
    """Resolve a consultant name to its canonical form.

    Accepts either canonical names ('Bureau de Contrôle') or company
    shortnames ('SOCOTEC') and returns the canonical name.
    """
    if name in CONSULTANT_DISPLAY_NAMES:
        return name  # already canonical
    return COMPANY_TO_CANONICAL.get(name, name)


def build_consultant_fiche(ctx: RunContext, consultant_name: str,
                           focus_result=None) -> dict[str, Any]:
    """Build the fiche.jsx FICHE_DATA payload for one consultant.

    Args:
        ctx: Loaded RunContext (from data_loader.load_run_context).
        consultant_name: Canonical consultant name as used in GED Mission column.
        focus_result: Optional FocusResult from apply_focus_filter.

    Returns:
        Dict matching window.FICHE_DATA shape. Always returns a dict; on degraded
        mode, fields are zero/empty but structure is complete.
    """
    # Concept 3: MOEX SAS has its own dedicated fiche builder
    if consultant_name == "MOEX SAS":
        return build_sas_fiche(ctx, focus_result=focus_result)

    # ── Degraded mode short-circuit ──────────────────────────────────────────
    if not ctx.ged_available or ctx.docs_df is None:
        return _empty_fiche(consultant_name, ctx)

    # ── DATA_DATE (anchor for all "current" logic) ───────────────────────────
    data_date = _resolve_data_date(ctx)
    prev_date = data_date - timedelta(days=7)

    # ── Filter GED docs/responses for this consultant ────────────────────────
    docs = _filter_for_consultant(ctx, consultant_name)
    if docs.empty:
        return _empty_fiche(consultant_name, ctx,
                            warnings=[f"No GED rows matched consultant '{consultant_name}'"])

    # ── Focus: compute owned_ids for this consultant ────────────────────────
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    owned_ids = None
    if focus_enabled and not docs.empty:
        id_col = "doc_id_resp" if "doc_id_resp" in docs.columns else "doc_id"
        focused_df = getattr(focus_result, 'focused_df', None)
        if focused_df is not None and "_focus_owner" in focused_df.columns:
            owned_ids = set()
            for _, frow in focused_df.iterrows():
                owners = frow.get("_focus_owner", [])
                if isinstance(owners, list) and consultant_name in owners:
                    owned_ids.add(frow["doc_id"])
            if consultant_name == "Maître d'Oeuvre EXE":
                for _, frow in focused_df.iterrows():
                    if frow.get("_focus_owner_tier") == "MOEX":
                        owned_ids.add(frow["doc_id"])
        else:
            owned_ids = focus_result.focused_doc_ids

    # ── Status label resolution (s1/s2/s3) ───────────────────────────────────
    s1, s2, s3 = _resolve_status_labels(ctx, consultant_name)

    # ── Attach derived columns used by all blocks ────────────────────────────
    # Use ALL docs (full history) for charts and tables
    all_docs = _attach_derived(docs, data_date, s1=s1, s2=s2, s3=s3, ctx=ctx)

    # ── Build blocks ─────────────────────────────────────────────────────────
    # Bloc1, Bloc2: FULL HISTORY (all avis: VSO, VAO, REF, HM + open)
    # Header, Week delta: FULL HISTORY for totals/answered, FOCUSED for open
    # Bloc3: FULL HISTORY for status counts, FOCUSED for open column
    consultant = _build_consultant_meta(ctx, consultant_name)
    header     = _build_header(all_docs, data_date, s1, s2, s3)
    week_delta = _build_week_delta(all_docs, data_date, prev_date, s1, s2, s3)
    if focus_enabled:
        bloc1 = _build_bloc1_weekly(all_docs, data_date, s1, s2, s3)
    else:
        bloc1 = _build_bloc1(all_docs, data_date, s1, s2, s3)
    bloc2      = _build_bloc2(bloc1)
    bloc3      = _build_bloc3(all_docs, ctx, s1, s2, s3)

    # ── Focus: override open counts in header/bloc3 with ownership-filtered values
    if focus_enabled and owned_ids is not None:
        id_col = "doc_id_resp" if "doc_id_resp" in all_docs.columns else "doc_id"
        focused_docs = all_docs[all_docs[id_col].isin(owned_ids)]
        # Override header open counts
        open_mask = focused_docs["_is_open"]
        header["open_count"] = int(open_mask.sum())
        header["open_ok"] = int((open_mask & focused_docs["_on_time"]).sum())
        header["open_late"] = int((open_mask & ~focused_docs["_on_time"]).sum())
        blocking_mask = focused_docs["_is_blocking"]
        header["open_blocking"] = int(blocking_mask.sum())
        header["open_blocking_ok"] = int((blocking_mask & focused_docs["_on_time"]).sum())
        header["open_blocking_late"] = int((blocking_mask & ~focused_docs["_on_time"]).sum())
        header["open_non_blocking"] = int((open_mask & ~blocking_mask).sum())
        # Override bloc3 open counts per lot
        for lot_row in bloc3.get("lots", []):
            lot_name = lot_row["name"]
            lot_focused = focused_docs[focused_docs["_gf_sheet"] == lot_name]
            lot_open = lot_focused["_is_open"]
            lot_row["open_ok"] = int((lot_open & lot_focused["_on_time"]).sum())
            lot_row["open_late"] = int((lot_open & ~lot_focused["_on_time"]).sum())
            if "_is_blocking" in lot_focused.columns:
                lot_blk = lot_focused["_is_blocking"]
                lot_row["open_blocking_ok"] = int((lot_blk & lot_focused["_on_time"]).sum())
                lot_row["open_blocking_late"] = int((lot_blk & ~lot_focused["_on_time"]).sum())
                lot_row["open_nb"] = int((lot_open & ~lot_blk).sum())
        # Recalculate bloc3 totals and donut from overridden lot rows
        lots = bloc3.get("lots", [])
        def _sum(key):
            return int(sum(r.get(key, 0) for r in lots))
        bloc3["total_row"]["open_ok"] = _sum("open_ok")
        bloc3["total_row"]["open_late"] = _sum("open_late")
        bloc3["total_row"]["open_blocking_ok"] = _sum("open_blocking_ok")
        bloc3["total_row"]["open_blocking_late"] = _sum("open_blocking_late")
        bloc3["total_row"]["open_nb"] = _sum("open_nb")
        bloc3["donut_ok"] = _sum("open_blocking_ok")
        bloc3["donut_late"] = _sum("open_blocking_late")
        bloc3["donut_total"] = bloc3["donut_ok"] + bloc3["donut_late"]
        bloc3["donut_nb"] = _sum("open_nb")

    # ── Non-saisi GED badge (only for BET merge consultants) ──────────────
    non_saisi = _build_non_saisi(all_docs, consultant_name)

    # ── Focus: build priority strip for this consultant ──────────────
    focus_priority = None
    if focus_enabled:
        # Match by ownership: this consultant appears in the owners list
        my_pq = [item for item in (focus_result.priority_queue or [])
                 if consultant_name in item.get("owners", [])]
        # Also include MOEX-tier docs for MOEX fiche
        if consultant_name == "Maître d'Oeuvre EXE":
            moex_pq = [item for item in (focus_result.priority_queue or [])
                       if item.get("owner_tier") == "MOEX"]
            seen = {item["doc_id"] for item in my_pq}
            my_pq.extend(item for item in moex_pq if item["doc_id"] not in seen)
            my_pq.sort(key=lambda x: (x["priority"], x.get("delta_days") or 9999))
        p_counts = {}
        for item in my_pq:
            p = item["priority"]
            p_counts[p] = p_counts.get(p, 0) + 1
        focus_priority = {
            "p1": p_counts.get(1, 0),
            "p2": p_counts.get(2, 0),
            "p3": p_counts.get(3, 0),
            "p4": p_counts.get(4, 0),
            "p5": p_counts.get(5, 0),
            "total_focused": len(docs),
            "items": my_pq[:20],
        }

    return {
        "consultant":  consultant,
        "header":      header,
        "week_delta":  week_delta,
        "bloc1":       bloc1,
        "bloc2":       bloc2,
        "bloc3":       bloc3,
        "non_saisi":   non_saisi,
        "focus_priority": focus_priority,
        "focus_enabled": bool(focus_enabled),
        "degraded_mode": False,
        "warnings":    list(ctx.warnings or []),
    }


# ═════════════════════════════════════════════════════════════════════════════
# SAS Conformity Gate Fiche
# ═════════════════════════════════════════════════════════════════════════════

def build_sas_fiche(ctx: RunContext, focus_result=None) -> dict[str, Any]:
    """Build dedicated SAS conformity gate fiche.

    This is NOT a standard consultant fiche — it tracks submission quality
    and conformity discipline, not engineering review responses.

    SAS statuses (from clean_status on 0-SAS approver_raw):
      - VSO-SAS, VSO → passed clean
      - VAO-SAS, VAO → passed with minor remarks
      - REF → refused, contractor must correct and resubmit
      - empty/pending → SAS check not yet performed

    Key metrics:
      - SAS pass rate (VSO+VAO vs total checked)
      - SAS refusal rate per contractor (submission discipline)
      - SAS turnaround time (submission date → SAS response date)
      - Currently pending SAS checks (backlog)
    """
    if not ctx.ged_available or ctx.responses_df is None:
        return _empty_sas_fiche(ctx)

    data_date = _resolve_data_date(ctx)
    resp = ctx.responses_df
    docs = ctx.dernier_df

    # ── Filter to 0-SAS approver rows only ──────────────────────────────
    sas_resp = resp[
        (resp["approver_raw"] == "0-SAS") &
        (resp["date_status_type"] != "NOT_CALLED")
    ].copy()

    if sas_resp.empty or docs is None or docs.empty:
        return _empty_sas_fiche(ctx)

    # Merge with dernier docs
    merged = sas_resp.merge(docs, on="doc_id", how="inner", suffixes=("_resp", "_doc"))

    if merged.empty:
        return _empty_sas_fiche(ctx)

    # Focus filter: SAS fiche shows all focused docs (SAS is a gate, not an owner)
    # But exclude resolved docs (VISA GLOBAL is terminal)
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    if focus_enabled:
        focused_df = getattr(focus_result, 'focused_df', None)
        if focused_df is not None:
            focused_ids = set(focused_df["doc_id"].tolist())
        else:
            focused_ids = focus_result.focused_doc_ids
        merged = merged[merged["doc_id"].isin(focused_ids)].copy()
        if merged.empty:
            return _empty_sas_fiche(ctx)

    # ── Normalize SAS statuses ──────────────────────────────────────────
    def _normalize_sas_status(s):
        if s is None:
            return None
        s = str(s).upper().strip()
        if s in ("VSO-SAS", "VSO"):
            return "VSO"
        if s in ("VAO-SAS", "VAO"):
            return "VAO"
        if s == "REF":
            return "REF"
        if s in ("", "NONE", "NAN"):
            return None
        return s

    status_col = "status_clean_resp" if "status_clean_resp" in merged.columns else "status_clean"
    merged["_sas_status"] = merged[status_col].apply(_normalize_sas_status)

    # Date columns
    da_col = "date_answered_resp" if "date_answered_resp" in merged.columns else "date_answered"
    merged["_sas_date"] = pd.to_datetime(merged[da_col], errors="coerce")
    merged["_sas_date_d"] = merged["_sas_date"].dt.date

    created_col = "created_at_doc" if "created_at_doc" in merged.columns else "created_at"
    merged["_created"] = pd.to_datetime(merged[created_col], errors="coerce")
    merged["_created_d"] = merged["_created"].dt.date

    date_status_col = "date_status_type_resp" if "date_status_type_resp" in merged.columns else "date_status_type"

    # ── Classify ────────────────────────────────────────────────────────
    sas_closed_statuses = {"VSO", "VAO", "REF"}
    merged["_sas_is_closed"] = merged["_sas_status"].isin(sas_closed_statuses)
    merged["_sas_is_pending"] = ~merged["_sas_is_closed"]
    merged["_sas_is_late"] = merged[date_status_col] == "PENDING_LATE"

    # Emetteur (contractor) column
    em_col = "emetteur_doc" if "emetteur_doc" in merged.columns else (
             "emetteur" if "emetteur" in merged.columns else None)
    if em_col:
        merged["_emetteur"] = merged[em_col].fillna("?").astype(str)
    else:
        merged["_emetteur"] = "?"

    # Lot column
    lot_col = "lot_normalized_doc" if "lot_normalized_doc" in merged.columns else (
              "lot_normalized" if "lot_normalized" in merged.columns else None)
    if lot_col:
        merged["_lot"] = merged[lot_col].fillna("?").astype(str)
    else:
        merged["_lot"] = "?"

    # GF sheet for grouping
    for col in ("gf_sheet_doc", "gf_sheet", "_gf_sheet"):
        if col in merged.columns:
            merged["_gf_sheet"] = merged[col].fillna("").astype(str)
            break
    else:
        merged["_gf_sheet"] = merged["_lot"]

    total = len(merged)

    # ── HEADER ──────────────────────────────────────────────────────────
    checked = int(merged["_sas_is_closed"].sum())
    vso_count = int((merged["_sas_status"] == "VSO").sum())
    vao_count = int((merged["_sas_status"] == "VAO").sum())
    ref_count = int((merged["_sas_status"] == "REF").sum())
    pending_count = int(merged["_sas_is_pending"].sum())
    pending_late = int((merged["_sas_is_pending"] & merged["_sas_is_late"]).sum())
    pending_ok = pending_count - pending_late

    pass_rate = round(((vso_count + vao_count) / checked) * 100, 1) if checked else 0.0
    ref_rate = round((ref_count / checked) * 100, 1) if checked else 0.0

    # Turnaround time (submission → SAS response, in days)
    turnaround_days = []
    for _, row in merged[merged["_sas_is_closed"]].iterrows():
        if pd.notna(row["_sas_date"]) and pd.notna(row["_created"]):
            try:
                delta = (row["_sas_date"] - row["_created"]).days
                if 0 <= delta <= 365:
                    turnaround_days.append(delta)
            except Exception:
                pass
    avg_turnaround = round(sum(turnaround_days) / len(turnaround_days), 1) if turnaround_days else None

    header = {
        "week_num":        data_date.isocalendar()[1],
        "data_date_str":   data_date.strftime("%d/%m/%Y"),
        "total":           total,
        "checked":         checked,
        "vso_count":       vso_count,
        "vao_count":       vao_count,
        "ref_count":       ref_count,
        "pending_count":   pending_count,
        "pending_ok":      pending_ok,
        "pending_late":    pending_late,
        "pass_rate":       pass_rate,
        "ref_rate":        ref_rate,
        "avg_turnaround":  avg_turnaround,
        # Legacy compat fields
        "s1": "VSO", "s2": "VAO", "s3": "REF",
        "s1_count": vso_count, "s2_count": vao_count, "s3_count": ref_count,
        "hm_count": 0,
        "answered": checked,
        "open_count": pending_count,
        "open_ok": pending_ok,
        "open_late": pending_late,
        "open_blocking": pending_count,
        "open_blocking_ok": pending_ok,
        "open_blocking_late": pending_late,
        "open_non_blocking": 0,
    }

    # ── WEEK DELTA ──────────────────────────────────────────────────────
    prev_date = data_date - timedelta(days=7)
    cur = merged[merged["_created_d"] <= data_date]
    prv = merged[merged["_created_d"] <= prev_date]

    def _sas_stats(df):
        if df.empty:
            return {"total": 0, "checked": 0, "vso": 0, "vao": 0, "ref": 0,
                    "pending": 0, "pending_late": 0, "ref_rate": 0.0}
        chk = int(df["_sas_is_closed"].sum())
        v = int((df["_sas_status"] == "VSO").sum())
        a = int((df["_sas_status"] == "VAO").sum())
        r = int((df["_sas_status"] == "REF").sum())
        p = int(df["_sas_is_pending"].sum())
        pl = int((df["_sas_is_pending"] & df["_sas_is_late"]).sum())
        rr = round((r / chk) * 100, 1) if chk else 0.0
        return {"total": len(df), "checked": chk, "vso": v, "vao": a, "ref": r,
                "pending": p, "pending_late": pl, "ref_rate": rr}

    cs, ps = _sas_stats(cur), _sas_stats(prv)
    week_delta = {
        "total":        cs["total"] - ps["total"],
        "checked":      cs["checked"] - ps["checked"],
        "vso":          cs["vso"] - ps["vso"],
        "vao":          cs["vao"] - ps["vao"],
        "ref":          cs["ref"] - ps["ref"],
        "pending":      cs["pending"] - ps["pending"],
        "pending_late": cs["pending_late"] - ps["pending_late"],
        "ref_rate":     round(cs["ref_rate"] - ps["ref_rate"], 1),
        # Legacy compat
        "s1": cs["vso"] - ps["vso"],
        "s2": cs["vao"] - ps["vao"],
        "s3": cs["ref"] - ps["ref"],
        "hm": 0,
        "open": cs["pending"] - ps["pending"],
        "open_late": cs["pending_late"] - ps["pending_late"],
        "open_blocking": cs["pending"] - ps["pending"],
        "open_blocking_late": cs["pending_late"] - ps["pending_late"],
        "refus_rate_pct": round(cs["ref_rate"] - ps["ref_rate"], 1),
    }

    # ── BLOC 1 — Monthly SAS activity ───────────────────────────────────
    first_created = merged["_created_d"].dropna().min()
    months = _month_range(first_created, data_date) if first_created and not pd.isna(first_created) else []
    if len(months) > 18:
        months = months[-18:]

    current_ym = (data_date.year, data_date.month)
    bloc1 = []
    for y, m in months:
        month_start = date(y, m, 1)
        month_end = _month_last_day(y, m)

        created_in = merged[
            (merged["_created_d"] >= month_start) & (merged["_created_d"] <= month_end)
        ]
        checked_in = merged[
            merged["_sas_date_d"].notna() &
            (merged["_sas_date_d"] >= month_start) & (merged["_sas_date_d"] <= month_end) &
            merged["_sas_is_closed"]
        ]

        nvx = int(len(created_in))
        doc_ferme = int(len(checked_in))
        s1c = int((checked_in["_sas_status"] == "VSO").sum())
        s2c = int((checked_in["_sas_status"] == "VAO").sum())
        s3c = int((checked_in["_sas_status"] == "REF").sum())

        def _pct(c, d=doc_ferme):
            return round((c / d) * 100, 1) if d else None

        # End-of-month pending snapshot
        snapshot = merged[merged["_created_d"] <= month_end]
        closed_by_month_end = snapshot[
            snapshot["_sas_date_d"].notna() & (snapshot["_sas_date_d"] <= month_end) &
            snapshot["_sas_is_closed"]
        ]
        open_at_end = max(len(snapshot) - len(closed_by_month_end), 0)

        bloc1.append({
            "label":      f"{y:04d}-{m:02d}",
            "is_current": (y, m) == current_ym,
            "nvx":        nvx,
            "doc_ferme":  doc_ferme,
            "s1": s1c, "s1_pct": _pct(s1c),
            "s2": s2c, "s2_pct": _pct(s2c),
            "s3": s3c, "s3_pct": _pct(s3c),
            "hm": 0,   "hm_pct": None,
            "open_ok":   open_at_end,
            "open_late": 0,
            "pass_rate": round(((s1c + s2c) / doc_ferme) * 100, 1) if doc_ferme else None,
            "open_blocking_ok": open_at_end,
            "open_blocking_late": 0,
            "open_nb": 0,
        })

    # Focus mode: rebuild bloc1 as weekly
    if focus_enabled:
        weekly_bloc1 = []
        week_data: dict = {}
        for _, row in merged.iterrows():
            cd = row.get("_created_d")
            if cd is None:
                continue
            try:
                if pd.isna(cd):
                    continue
            except Exception:
                pass
            try:
                iso = cd.isocalendar()
                wk = (int(iso[0]), int(iso[1]))
                if wk not in week_data:
                    week_data[wk] = {"created": [], "checked": []}
                week_data[wk]["created"].append(row)
            except Exception:
                pass

        for _, row in merged[merged["_sas_is_closed"]].iterrows():
            sd = row.get("_sas_date_d")
            if sd is None:
                continue
            try:
                if pd.isna(sd):
                    continue
            except Exception:
                pass
            try:
                iso = sd.isocalendar()
                wk = (int(iso[0]), int(iso[1]))
                if wk not in week_data:
                    week_data[wk] = {"created": [], "checked": []}
                week_data[wk]["checked"].append(row)
            except Exception:
                pass

        current_iso = data_date.isocalendar()
        current_wk = (int(current_iso[0]), int(current_iso[1]))

        for (wy, ww) in sorted(week_data.keys())[-26:]:
            wd = week_data[(wy, ww)]
            nvx = len(wd["created"])
            doc_ferme = len(wd["checked"])
            s1c = sum(1 for r in wd["checked"] if r.get("_sas_status") == "VSO")
            s2c = sum(1 for r in wd["checked"] if r.get("_sas_status") == "VAO")
            s3c = sum(1 for r in wd["checked"] if r.get("_sas_status") == "REF")

            def _pct_w(c, d=doc_ferme):
                return round((c / d) * 100, 1) if d else None

            weekly_bloc1.append({
                "label": f"{wy}-S{ww:02d}",
                "is_current": (wy, ww) == current_wk,
                "nvx": nvx, "doc_ferme": doc_ferme,
                "s1": s1c, "s1_pct": _pct_w(s1c),
                "s2": s2c, "s2_pct": _pct_w(s2c),
                "s3": s3c, "s3_pct": _pct_w(s3c),
                "hm": 0, "hm_pct": None,
                "open_ok": 0, "open_late": 0,
                "pass_rate": round(((s1c + s2c) / doc_ferme) * 100, 1) if doc_ferme else None,
                "open_blocking_ok": 0, "open_blocking_late": 0, "open_nb": 0,
            })
        bloc1 = weekly_bloc1

    # ── BLOC 2 — reuse standard builder ────────────────────────────────
    bloc2 = _build_bloc2(bloc1)

    # ── BLOC 3 — SAS performance PER CONTRACTOR ─────────────────────────
    contractor_groups = merged.groupby("_emetteur", dropna=True)
    contractors = []
    for em, sub in contractor_groups:
        sub_checked = int(sub["_sas_is_closed"].sum())
        sub_vso = int((sub["_sas_status"] == "VSO").sum())
        sub_vao = int((sub["_sas_status"] == "VAO").sum())
        sub_ref = int((sub["_sas_status"] == "REF").sum())
        sub_pending = int(sub["_sas_is_pending"].sum())
        sub_total = int(len(sub))
        sub_ref_rate = round((sub_ref / sub_checked) * 100, 1) if sub_checked else 0.0
        sub_pass_rate = round(((sub_vso + sub_vao) / sub_checked) * 100, 1) if sub_checked else 0.0

        ct_days = []
        for _, row in sub[sub["_sas_is_closed"]].iterrows():
            if pd.notna(row["_sas_date"]) and pd.notna(row["_created"]):
                try:
                    d = (row["_sas_date"] - row["_created"]).days
                    if 0 <= d <= 365:
                        ct_days.append(d)
                except Exception:
                    pass
        ct_avg = round(sum(ct_days) / len(ct_days), 1) if ct_days else None

        lots = sorted(sub["_lot"].unique().tolist())

        contractors.append({
            "name":        str(em),
            "total":       sub_total,
            "checked":     sub_checked,
            "VSO":         sub_vso,
            "VAO":         sub_vao,
            "REF":         sub_ref,
            "HM":          0,
            "pending":     sub_pending,
            "ref_rate":    sub_ref_rate,
            "pass_rate":   sub_pass_rate,
            "avg_days":    ct_avg,
            "lots":        lots,
            # Legacy compat for LotHealthBar
            "open_ok":     sub_pending,
            "open_late":   0,
            "open_blocking_ok": sub_pending,
            "open_blocking_late": 0,
            "open_nb":     0,
        })

    contractors.sort(key=lambda r: -r["total"])

    def _sum_c(key):
        return int(sum(r[key] for r in contractors))

    total_row = {
        "total":              _sum_c("total"),
        "VSO":                _sum_c("VSO"),
        "VAO":                _sum_c("VAO"),
        "REF":                _sum_c("REF"),
        "HM":                 0,
        "open_ok":            _sum_c("pending"),
        "open_late":          0,
        "open_blocking_ok":   _sum_c("pending"),
        "open_blocking_late": 0,
        "open_nb":            0,
    }

    refus_scored = [(r, r["ref_rate"]) for r in contractors if r["checked"] >= 3]
    refus_scored.sort(key=lambda rp: -rp[1])
    refus_contractors = [
        [{"name": r["name"]}, p] for r, p in refus_scored[:5]
    ]

    pending_contractors = [
        {"name": r["name"], "open_late": r["pending"]}
        for r in sorted(contractors, key=lambda r: -r["pending"])
        if r["pending"] > 0
    ][:5]

    bloc3 = {
        "s1": "VSO", "s2": "VAO", "s3": "REF",
        "lots":          contractors,
        "total_row":     total_row,
        "donut_total":   _sum_c("pending"),
        "donut_ok":      _sum_c("pending"),
        "donut_late":    0,
        "donut_nb":      0,
        "critical_lots": pending_contractors,
        "refus_lots":    refus_contractors,
    }

    bloc4_contractor_ranking = sorted(
        [c for c in contractors if c["checked"] >= 1],
        key=lambda c: -c["ref_rate"]
    )

    return {
        "consultant": {
            "id":             0,
            "slug":           "MOEXSAS",
            "canonical_name": "MOEX SAS",
            "display_name":   "GEMO",
            "name":           "MOEX SAS",
            "role":           "Conformité SAS",
            "merge_key":      None,
        },
        "header":       header,
        "week_delta":   week_delta,
        "bloc1":        bloc1,
        "bloc2":        bloc2,
        "bloc3":        bloc3,
        "bloc4_sas":    bloc4_contractor_ranking,
        "non_saisi":    None,
        "degraded_mode": False,
        "warnings":     list(ctx.warnings or []),
        "is_sas_fiche": True,
    }


def _empty_sas_fiche(ctx: RunContext) -> dict[str, Any]:
    return {
        "consultant": {
            "id": 0, "slug": "MOEXSAS", "display_name": "GEMO",
            "canonical_name": "MOEX SAS", "name": "MOEX SAS",
            "role": "Conformité SAS", "merge_key": None,
        },
        "header": {
            "week_num": 0, "data_date_str": "",
            "total": 0, "checked": 0,
            "vso_count": 0, "vao_count": 0, "ref_count": 0,
            "pending_count": 0, "pending_ok": 0, "pending_late": 0,
            "pass_rate": 0.0, "ref_rate": 0.0, "avg_turnaround": None,
            "s1": "VSO", "s2": "VAO", "s3": "REF",
            "s1_count": 0, "s2_count": 0, "s3_count": 0, "hm_count": 0,
            "answered": 0, "open_count": 0, "open_ok": 0, "open_late": 0,
            "open_blocking": 0, "open_blocking_ok": 0,
            "open_blocking_late": 0, "open_non_blocking": 0,
        },
        "week_delta": {
            "total": 0, "s1": 0, "s2": 0, "s3": 0, "hm": 0,
            "open": 0, "open_late": 0, "refus_rate_pct": 0.0,
            "open_blocking": 0, "open_blocking_late": 0,
            "checked": 0, "vso": 0, "vao": 0, "ref": 0,
            "pending": 0, "pending_late": 0, "ref_rate": 0.0,
        },
        "bloc1": [],
        "bloc2": {"labels": [], "s1_series": [], "s2_series": [], "s3_series": [],
                  "hm_series": [], "open_series": [], "totals": [],
                  "open_blocking_series": [], "open_nb_series": []},
        "bloc3": {
            "s1": "VSO", "s2": "VAO", "s3": "REF",
            "lots": [],
            "total_row": {"total": 0, "VSO": 0, "VAO": 0, "REF": 0, "HM": 0,
                          "open_ok": 0, "open_late": 0,
                          "open_blocking_ok": 0, "open_blocking_late": 0, "open_nb": 0},
            "donut_total": 0, "donut_ok": 0, "donut_late": 0, "donut_nb": 0,
            "critical_lots": [], "refus_lots": [],
        },
        "bloc4_sas": [],
        "non_saisi": None,
        "degraded_mode": True,
        "warnings": list(ctx.warnings or []),
        "is_sas_fiche": True,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Builders
# ═════════════════════════════════════════════════════════════════════════════

def _build_consultant_meta(ctx: RunContext, name: str) -> dict[str, Any]:
    all_consultants = sorted(ctx.approver_names or [name])
    try:
        cid = all_consultants.index(name) + 1
    except ValueError:
        cid = 0

    merge_key = BET_MERGE_KEYS.get(name)
    role = ROLE_BY_CANONICAL.get(name, "Consultant")
    display = CONSULTANT_DISPLAY_NAMES.get(name, name)

    return {
        "id":            cid,
        "slug":          _slugify(name),
        "canonical_name": name,
        "display_name":  display,
        "name":          name,
        "role":          role,
        "merge_key":     merge_key,
    }


def _build_header(docs: pd.DataFrame, data_date: date,
                  s1: str, s2: str, s3: str) -> dict[str, Any]:
    total       = len(docs)
    closed_mask = docs["_status_for_consultant"].isin([s1, s2, s3, "HM"])
    answered    = int(closed_mask.sum())

    s1_count = int((docs["_status_for_consultant"] == s1).sum())
    s2_count = int((docs["_status_for_consultant"] == s2).sum())
    s3_count = int((docs["_status_for_consultant"] == s3).sum())
    hm_count = int((docs["_status_for_consultant"] == "HM").sum())

    open_mask = docs["_is_open"]
    open_count = int(open_mask.sum())
    open_ok    = int((open_mask & docs["_on_time"]).sum())
    open_late  = int((open_mask & ~docs["_on_time"]).sum())

    # Concept 1: split into blocking vs non-blocking
    blocking_mask = docs["_is_blocking"]
    non_blocking_mask = open_mask & ~blocking_mask
    open_blocking       = int(blocking_mask.sum())
    open_blocking_ok    = int((blocking_mask & docs["_on_time"]).sum())
    open_blocking_late  = int((blocking_mask & ~docs["_on_time"]).sum())
    open_non_blocking   = int(non_blocking_mask.sum())

    return {
        "week_num":       data_date.isocalendar()[1],
        "data_date_str":  data_date.strftime("%d/%m/%Y"),
        "total":          total,
        "answered":       answered,
        "s1": s1, "s2": s2, "s3": s3,
        "s1_count": s1_count, "s2_count": s2_count, "s3_count": s3_count,
        "hm_count":   hm_count,
        "open_count": open_count,
        "open_ok":    open_ok,
        "open_late":  open_late,
        "open_blocking":       open_blocking,
        "open_blocking_ok":    open_blocking_ok,
        "open_blocking_late":  open_blocking_late,
        "open_non_blocking":   open_non_blocking,
    }


def _build_week_delta(docs: pd.DataFrame, data_date: date, prev_date: date,
                      s1: str, s2: str, s3: str) -> dict[str, Any]:
    closed_statuses = {s1, s2, s3, "HM"}

    # Docs that existed at each anchor (based on _created_date)
    cur = docs[docs["_created_date"] <= data_date]
    prv = docs[docs["_created_date"] <= prev_date]

    def _stats(df: pd.DataFrame) -> dict:
        if df.empty:
            return {"total": 0, "s1": 0, "s2": 0, "s3": 0, "hm": 0,
                    "open": 0, "open_late": 0, "refus_rate_pct": 0.0,
                    "open_blocking": 0, "open_blocking_late": 0}
        closed   = df["_status_for_consultant"].isin(closed_statuses)
        answered = int(closed.sum())
        s1c = int((df["_status_for_consultant"] == s1).sum())
        s2c = int((df["_status_for_consultant"] == s2).sum())
        s3c = int((df["_status_for_consultant"] == s3).sum())
        hmc = int((df["_status_for_consultant"] == "HM").sum())
        opn = int(df["_is_open"].sum())
        olt = int((df["_is_open"] & ~df["_on_time"]).sum())
        refus_pct = round((s3c / answered) * 100, 1) if answered else 0.0
        blk = int(df["_is_blocking"].sum())
        blk_late = int((df["_is_blocking"] & ~df["_on_time"]).sum())
        return {
            "total": len(df), "s1": s1c, "s2": s2c, "s3": s3c, "hm": hmc,
            "open": opn, "open_late": olt, "refus_rate_pct": refus_pct,
            "open_blocking": blk, "open_blocking_late": blk_late,
        }

    c, p = _stats(cur), _stats(prv)
    return {
        "total":          c["total"] - p["total"],
        "s1":             c["s1"]    - p["s1"],
        "s2":             c["s2"]    - p["s2"],
        "s3":             c["s3"]    - p["s3"],
        "hm":             c["hm"]    - p["hm"],
        "open":           c["open"]  - p["open"],
        "open_late":      c["open_late"] - p["open_late"],
        "refus_rate_pct": round(c["refus_rate_pct"] - p["refus_rate_pct"], 1),
        "open_blocking":      c["open_blocking"] - p["open_blocking"],
        "open_blocking_late": c["open_blocking_late"] - p["open_blocking_late"],
    }


def _build_bloc1(docs: pd.DataFrame, data_date: date,
                 s1: str, s2: str, s3: str) -> list[dict[str, Any]]:
    if docs.empty:
        return []

    closed_statuses = {s1, s2, s3, "HM"}

    # Month range: from first doc creation to DATA_DATE month (inclusive).
    first_created = docs["_created_date"].min()
    months = _month_range(first_created, data_date)
    current_ym = (data_date.year, data_date.month)

    # Limit to last 18 months max.
    if len(months) > 18:
        months = months[-18:]

    rows = []
    for y, m in months:
        month_start = date(y, m, 1)
        month_end   = _month_last_day(y, m)

        created_in_month = docs[
            (docs["_created_date"] >= month_start) & (docs["_created_date"] <= month_end)
        ]
        closed_in_month = docs[
            docs["_date_answered"].notna() &
            (docs["_date_answered"] >= month_start) & (docs["_date_answered"] <= month_end) &
            docs["_status_for_consultant"].isin(closed_statuses)
        ]

        nvx       = int(len(created_in_month))
        doc_ferme = int(len(closed_in_month))

        def _count(label: str) -> int:
            return int((closed_in_month["_status_for_consultant"] == label).sum())

        s1c = _count(s1); s2c = _count(s2); s3c = _count(s3); hmc = _count("HM")

        def _pct(c: int) -> float | None:
            return round((c / doc_ferme) * 100, 1) if doc_ferme else None

        # End-of-month open snapshot: docs existing by month_end, still open at month_end,
        # evaluated against month_end itself for on-time/late classification.
        snapshot = docs[docs["_created_date"] <= month_end]
        # A doc is open at month_end if it wasn't closed by month_end
        open_at_end = snapshot[snapshot.apply(
            lambda r: r["_open_at_date"](month_end), axis=1
        )]
        # For month-end snapshots, use _on_time which is derived from date_status_type.
        # This is an approximation: the late/on-time status at DATA_DATE is used for
        # historical snapshots too (we don't have per-month deadline data).
        open_ok    = int(open_at_end["_on_time"].sum())
        open_late  = int(len(open_at_end)) - open_ok

        # Blocking subset of open_at_end (Concept 1)
        if "_is_blocking" in open_at_end.columns:
            blocking_at_end = open_at_end[open_at_end["_is_blocking"]]
            nb_at_end = open_at_end[~open_at_end["_is_blocking"]]
        else:
            blocking_at_end = open_at_end
            nb_at_end = open_at_end.iloc[0:0]

        open_blocking_ok   = int(blocking_at_end["_on_time"].sum())
        open_blocking_late = int(len(blocking_at_end)) - open_blocking_ok
        open_nb            = int(len(nb_at_end))

        rows.append({
            "label":      f"{y:04d}-{m:02d}",
            "is_current": (y, m) == current_ym,
            "nvx":        nvx,
            "doc_ferme":  doc_ferme,
            "s1": s1c, "s1_pct": _pct(s1c),
            "s2": s2c, "s2_pct": _pct(s2c),
            "s3": s3c, "s3_pct": _pct(s3c),
            "hm": hmc, "hm_pct": _pct(hmc),
            "open_ok":   open_ok,
            "open_late": open_late,
            "open_blocking_ok":   open_blocking_ok,
            "open_blocking_late": open_blocking_late,
            "open_nb":            open_nb,
        })
    return rows


def _build_bloc1_weekly(docs: pd.DataFrame, data_date: date,
                        s1: str, s2: str, s3: str) -> list[dict[str, Any]]:
    """Weekly version of bloc1 for Focus Mode.
    Same structure as monthly but keyed by ISO week."""
    if docs.empty:
        return []

    docs = docs.copy()
    for col in ("_created_date", "_date_answered"):
        if col in docs.columns:
            docs[col] = pd.to_datetime(docs[col], errors="coerce")

    closed_statuses = {s1, s2, s3, "HM"}

    # Collect all ISO weeks represented in created or answered dates
    weeks: dict = {}
    for _, row in docs.iterrows():
        for col in ("_created_date", "_date_answered"):
            cd = row.get(col)
            if cd is None or (hasattr(cd, '__class__') and cd.__class__.__name__ == 'float'):
                continue
            try:
                if pd.isna(cd):
                    continue
            except Exception:
                pass
            if isinstance(cd, pd.Timestamp):
                cd = cd.date()
            try:
                iso = cd.isocalendar()
                wk = (int(iso[0]), int(iso[1]))
                weeks[wk] = True
            except Exception:
                pass

    if not weeks:
        return []

    sorted_weeks = sorted(weeks.keys())
    if len(sorted_weeks) > 26:
        sorted_weeks = sorted_weeks[-26:]

    current_iso = data_date.isocalendar()
    current_wk = (int(current_iso[0]), int(current_iso[1]))

    rows = []
    for (y, w) in sorted_weeks:
        # ISO week boundaries (Monday to Sunday)
        jan4 = date(y, 1, 4)
        week_start = jan4 + timedelta(weeks=w - 1, days=-jan4.weekday())
        week_end = week_start + timedelta(days=6)
        week_start_ts = pd.Timestamp(week_start)
        week_end_ts = pd.Timestamp(week_end)

        created_in_week = docs[
            docs["_created_date"].notna() &
            (docs["_created_date"] >= week_start_ts) &
            (docs["_created_date"] <= week_end_ts)
        ]
        closed_in_week = docs[
            docs["_date_answered"].notna() &
            (docs["_date_answered"] >= week_start_ts) &
            (docs["_date_answered"] <= week_end_ts) &
            docs["_status_for_consultant"].isin(closed_statuses)
        ]

        nvx = int(len(created_in_week))
        doc_ferme = int(len(closed_in_week))

        def _count(label: str) -> int:
            return int((closed_in_week["_status_for_consultant"] == label).sum())

        s1c = _count(s1); s2c = _count(s2); s3c = _count(s3); hmc = _count("HM")

        def _pct(c: int) -> float | None:
            return round((c / doc_ferme) * 100, 1) if doc_ferme else None

        # Open snapshot at end of week
        snapshot = docs[docs["_created_date"].notna() & (docs["_created_date"] <= week_end_ts)]
        try:
            open_at_end = snapshot[snapshot.apply(
                lambda r: r["_open_at_date"](week_end), axis=1
            )]
        except Exception:
            open_at_end = snapshot.iloc[0:0]

        open_ok = int(open_at_end["_on_time"].sum()) if "_on_time" in open_at_end.columns else 0
        open_late = int(len(open_at_end)) - open_ok

        if "_is_blocking" in open_at_end.columns:
            blocking_at_end = open_at_end[open_at_end["_is_blocking"]]
            nb_at_end = open_at_end[~open_at_end["_is_blocking"]]
        else:
            blocking_at_end = open_at_end
            nb_at_end = open_at_end.iloc[0:0]

        open_blocking_ok = int(blocking_at_end["_on_time"].sum()) if "_on_time" in blocking_at_end.columns else 0
        open_blocking_late = int(len(blocking_at_end)) - open_blocking_ok
        open_nb = int(len(nb_at_end))

        rows.append({
            "label":      f"{y}-S{w:02d}",
            "is_current": (y, w) == current_wk,
            "nvx":        nvx,
            "doc_ferme":  doc_ferme,
            "s1": s1c, "s1_pct": _pct(s1c),
            "s2": s2c, "s2_pct": _pct(s2c),
            "s3": s3c, "s3_pct": _pct(s3c),
            "hm": hmc, "hm_pct": _pct(hmc),
            "open_ok":   open_ok,
            "open_late": open_late,
            "open_blocking_ok":   open_blocking_ok,
            "open_blocking_late": open_blocking_late,
            "open_nb":            open_nb,
        })
    return rows


def _build_bloc2(bloc1: list[dict]) -> dict[str, Any]:
    labels, s1s, s2s, s3s, hms, opens, tots = [], [], [], [], [], [], []
    open_blockings, open_nbs = [], []
    c1 = c2 = c3 = chm = 0
    for row in bloc1:
        c1  += row["s1"]
        c2  += row["s2"]
        c3  += row["s3"]
        chm += row["hm"]
        open_level = row["open_ok"] + row["open_late"]
        open_blocking_level = row.get("open_blocking_ok", 0) + row.get("open_blocking_late", 0)
        open_nb_level = row.get("open_nb", 0)
        total = c1 + c2 + c3 + chm + open_level
        labels.append(row["label"])
        s1s.append(c1); s2s.append(c2); s3s.append(c3)
        hms.append(chm); opens.append(open_level); tots.append(total)
        open_blockings.append(open_blocking_level)
        open_nbs.append(open_nb_level)
    return {
        "labels":               labels,
        "s1_series":            s1s,
        "s2_series":            s2s,
        "s3_series":            s3s,
        "hm_series":            hms,
        "open_series":          opens,
        "totals":               tots,
        "open_blocking_series": open_blockings,
        "open_nb_series":       open_nbs,
    }


def _build_bloc3(docs: pd.DataFrame, ctx: RunContext,
                 s1: str, s2: str, s3: str) -> dict[str, Any]:
    if docs.empty:
        return _empty_bloc3(s1, s2, s3)

    # Group by GF sheet (resolved from NUMERO → gf_sheet mapping in ctx).
    g = docs.groupby("_gf_sheet", dropna=True)

    lots = []
    for sheet_name, sub in g:
        vso = int((sub["_status_for_consultant"] == s1).sum())
        vao = int((sub["_status_for_consultant"] == s2).sum())
        ref = int((sub["_status_for_consultant"] == s3).sum())
        hm  = int((sub["_status_for_consultant"] == "HM").sum())
        ook = int((sub["_is_open"] & sub["_on_time"]).sum())
        olt = int((sub["_is_open"] & ~sub["_on_time"]).sum())
        blk_ok   = int((sub["_is_blocking"] & sub["_on_time"]).sum())
        blk_late = int((sub["_is_blocking"] & ~sub["_on_time"]).sum())
        nb_count = int((sub["_is_open"] & ~sub["_is_blocking"]).sum())
        total = int(len(sub))

        # Populate BOTH the dynamic-keyed fields (s1/s2/s3 values) AND the
        # canonical VSO/VAO/REF fields so the JSX can index either way.
        row = {
            "name":              str(sheet_name),
            "total":             total,
            "VSO":               vso,
            "VAO":               vao,
            "REF":               ref,
            "HM":                hm,
            "open_ok":           ook,
            "open_late":         olt,
            "open_blocking_ok":  blk_ok,
            "open_blocking_late": blk_late,
            "open_nb":           nb_count,
        }
        # If a consultant uses non-default s1/s2/s3 labels, also mirror them:
        row.setdefault(s1, vso)
        row.setdefault(s2, vao)
        row.setdefault(s3, ref)
        lots.append(row)

    lots.sort(key=lambda r: -r["total"])

    # Totals
    def _sum(key: str) -> int:
        return int(sum(r[key] for r in lots))

    total_row = {
        "total":              _sum("total"),
        "VSO":                _sum("VSO"),
        "VAO":                _sum("VAO"),
        "REF":                _sum("REF"),
        "HM":                 _sum("HM"),
        "open_ok":            _sum("open_ok"),
        "open_late":          _sum("open_late"),
        "open_blocking_ok":   _sum("open_blocking_ok"),
        "open_blocking_late": _sum("open_blocking_late"),
        "open_nb":            _sum("open_nb"),
    }
    total_row.setdefault(s1, total_row["VSO"])
    total_row.setdefault(s2, total_row["VAO"])
    total_row.setdefault(s3, total_row["REF"])

    donut_ok   = _sum("open_blocking_ok")
    donut_late = _sum("open_blocking_late")

    # Critical lots — top 5 by open_blocking_late desc (open_blocking_late > 0 only)
    critical_lots = [
        {"name": r["name"], "open_late": r["open_blocking_late"]}
        for r in sorted(lots, key=lambda r: -r.get("open_blocking_late", 0))
        if r.get("open_blocking_late", 0) > 0
    ][:5]

    # Rejection rate lots — lots with >=3 closed docs, top 5 by %
    def _refus_pct(r: dict) -> float:
        closed = r["VSO"] + r["VAO"] + r["REF"] + r["HM"]
        return round((r["REF"] / closed) * 100, 1) if closed >= 3 else -1.0

    refus_scored = [(r, _refus_pct(r)) for r in lots]
    refus_scored = [(r, p) for r, p in refus_scored if p >= 0]
    refus_scored.sort(key=lambda rp: -rp[1])
    refus_lots = [
        [{"name": r["name"]}, p] for r, p in refus_scored[:5]
    ]

    return {
        "s1": s1, "s2": s2, "s3": s3,
        "lots":          lots,
        "total_row":     total_row,
        "donut_total":   donut_ok + donut_late,
        "donut_ok":      donut_ok,
        "donut_late":    donut_late,
        "donut_nb":      _sum("open_nb"),
        "critical_lots": critical_lots,
        "refus_lots":    refus_lots,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _resolve_data_date(ctx: RunContext) -> date:
    d = getattr(ctx, "data_date", None)
    if d is None:
        # Fallback to run_date; warn.
        ctx.warnings.append("data_date missing on ctx; falling back to run_date")
        d = datetime.fromisoformat(ctx.run_date).date() if ctx.run_date else date.today()
    if isinstance(d, datetime):
        d = d.date()
    return d


def _resolve_status_labels(ctx: RunContext, name: str) -> tuple[str, str, str]:
    """Returns (s1, s2, s3) for the consultant.

    Bureau de Contrôle (SOCOTEC) uses FAV/SUS/DEF.
    All others use VSO/VAO/REF.
    """
    labels = STATUS_LABELS_BY_CANONICAL.get(name, {})
    return (labels.get("s1", "VSO"),
            labels.get("s2", "VAO"),
            labels.get("s3", "REF"))


def _filter_for_consultant(ctx: RunContext, name: str) -> pd.DataFrame:
    """Return a merged DataFrame of dernier-indice docs + this consultant's responses.

    Uses ctx.dernier_df (latest version per document) as the doc base,
    then inner-joins with this consultant's response rows.
    """
    if ctx.responses_df is None or ctx.responses_df.empty:
        return pd.DataFrame()
    if ctx.dernier_df is None or ctx.dernier_df.empty:
        return pd.DataFrame()

    resp = ctx.responses_df
    docs = ctx.dernier_df

    if name == "MOEX SAS":
        # SAS fiche: only 0-SAS approver rows
        cons_resp = resp[
            (resp["approver_raw"] == "0-SAS") &
            (resp["date_status_type"] != "NOT_CALLED")
        ].copy()
    elif name == "Maître d'Oeuvre EXE":
        # Real MOEX fiche: exclude 0-SAS rows
        cons_resp = resp[
            (resp["approver_canonical"] == name) &
            (resp["approver_raw"] != "0-SAS") &
            (resp["date_status_type"] != "NOT_CALLED")
        ].copy()
    else:
        # All other consultants: unchanged
        cons_resp = resp[
            (resp["approver_canonical"] == name) &
            (resp["date_status_type"] != "NOT_CALLED")
        ].copy()

    if cons_resp.empty:
        return pd.DataFrame()

    # Merge with dernier-indice docs only
    merged = cons_resp.merge(docs, on="doc_id", how="inner", suffixes=("_resp", "_doc"))

    return merged


def _attach_derived(df: pd.DataFrame, data_date: date,
                    s1: str, s2: str, s3: str,
                    ctx: RunContext | None = None) -> pd.DataFrame:
    """Attach all derived columns used by the block builders.

    The input df is a merged docs+responses DataFrame from _filter_for_consultant.
    Actual columns from the pipeline:
      - status_clean:      VSO / VAO / REF / HM / "" (from normalize_responses)
      - date_status_type:  ANSWERED / PENDING_IN_DELAY / PENDING_LATE
      - date_answered:     datetime or None (from normalize_responses)
      - created_at:        datetime (from normalize_docs)
      - lot_normalized:    str (from normalize_docs)

    Derived columns added:
      _status_for_consultant : str   (mapped from status_clean: s1/s2/s3/HM/"")
      _created_date          : date  (from created_at)
      _date_answered         : date  (from date_answered)
      _is_open               : bool  (not answered yet)
      _on_time               : bool  (PENDING_IN_DELAY, not PENDING_LATE)
      _gf_sheet              : str   (lot label for bloc3 grouping)
      _open_at_date          : callable (for bloc1 month-end snapshots)
    """
    closed_statuses = {s1, s2, s3, "HM"}

    # ── Status: use status_clean from responses (already normalised to VSO/VAO/REF/HM)
    if "status_clean" in df.columns:
        df["_status_for_consultant"] = df["status_clean"].fillna("").astype(str).str.upper()
    else:
        df["_status_for_consultant"] = ""

    # ── Dates: created_at comes from normalize_docs, date_answered from normalize_responses
    if "created_at" in df.columns:
        df["_created_date"] = pd.to_datetime(df["created_at"], errors="coerce").dt.date
    else:
        df["_created_date"] = pd.NaT

    # date_answered may exist from both tables after merge; prefer the response one
    da_col = "date_answered_resp" if "date_answered_resp" in df.columns else (
             "date_answered" if "date_answered" in df.columns else None)
    if da_col:
        df["_date_answered"] = pd.to_datetime(df[da_col], errors="coerce").dt.date
    else:
        df["_date_answered"] = pd.NaT

    # ── GF sheet: prefer gf_sheet, then lot_normalized, then lot
    for col in ("gf_sheet", "lot_normalized", "lot"):
        if col in df.columns:
            df["_gf_sheet"] = df[col].fillna("").astype(str)
            break
    else:
        df["_gf_sheet"] = ""

    # ── Open/closed: a doc is open if the consultant hasn't rendered a final status
    df["_is_open"] = ~df["_status_for_consultant"].isin(closed_statuses)

    # ── Blocking: open AND no VISA GLOBAL yet (Concept 1) ──────────────────
    if ctx is not None and ctx.workflow_engine is not None and "doc_id" in df.columns:
        doc_id_col = "doc_id_resp" if "doc_id_resp" in df.columns else "doc_id"
        def _has_visa_global(doc_id):
            visa, _ = ctx.workflow_engine.compute_visa_global_with_date(doc_id)
            return visa is not None
        df["_has_visa_global"] = df[doc_id_col].apply(_has_visa_global)
        df["_is_blocking"] = df["_is_open"] & ~df["_has_visa_global"]
    else:
        df["_has_visa_global"] = False
        df["_is_blocking"] = df["_is_open"]  # fallback: all open = blocking

    # ── On-time / late: compare date_limite against data_date ──────────────
    # A pending doc is late if its deadline (date_limite) is before data_date.
    # A closed doc is always "on time" (it's done).
    # If date_limite is missing, fall back to date_status_type heuristic.
    dl_col = "date_limite_resp" if "date_limite_resp" in df.columns else (
             "date_limite" if "date_limite" in df.columns else None)
    if dl_col and dl_col in df.columns:
        def _compute_on_time(row):
            if not row["_is_open"]:
                return True  # closed = not late
            dl = row.get(dl_col)
            if dl is not None and not pd.isna(dl):
                if isinstance(dl, pd.Timestamp):
                    dl = dl.date()
                return dl >= data_date
            # Fallback: PENDING_LATE from Rappel prefix
            return row.get("date_status_type") != "PENDING_LATE"
        df["_on_time"] = df.apply(_compute_on_time, axis=1)
    elif "date_status_type" in df.columns:
        df["_on_time"] = df.apply(
            lambda r: (not r["_is_open"]) or (r["date_status_type"] != "PENDING_LATE"),
            axis=1,
        )
    else:
        df["_on_time"] = True

    # ── Open-at-date-d helper: for bloc1 end-of-month snapshots
    def _make_open_checker(status, answered_date):
        def _check(d: date) -> bool:
            if status in closed_statuses and pd.notna(answered_date) and answered_date <= d:
                return False
            return True
        return _check

    df["_open_at_date"] = df.apply(
        lambda r: _make_open_checker(r["_status_for_consultant"], r["_date_answered"]),
        axis=1,
    )
    return df


def _month_range(start: date, end: date) -> list[tuple[int, int]]:
    if pd.isna(start) or pd.isna(end):
        return []
    y, m = start.year, start.month
    out = []
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _month_last_day(y: int, m: int) -> date:
    if m == 12:
        return date(y, 12, 31)
    return date(y, m + 1, 1) - timedelta(days=1)


def _slugify(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum())


def _empty_fiche(name: str, ctx: RunContext,
                 warnings: list[str] | None = None) -> dict[str, Any]:
    s1, s2, s3 = "VSO", "VAO", "REF"
    return {
        "consultant": {
            "id": 0, "slug": _slugify(name), "display_name": CONSULTANT_DISPLAY_NAMES.get(name, name),
            "canonical_name": name, "name": name, "role": ROLE_BY_CANONICAL.get(name, "Consultant"),
            "merge_key": BET_MERGE_KEYS.get(name),
        },
        "header": {
            "week_num": 0, "data_date_str": "",
            "total": 0, "answered": 0,
            "s1": s1, "s2": s2, "s3": s3,
            "s1_count": 0, "s2_count": 0, "s3_count": 0,
            "hm_count": 0, "open_count": 0, "open_ok": 0, "open_late": 0,
            "open_blocking": 0, "open_blocking_ok": 0,
            "open_blocking_late": 0, "open_non_blocking": 0,
        },
        "week_delta": {"total": 0, "s1": 0, "s2": 0, "s3": 0, "hm": 0,
                       "open": 0, "open_late": 0, "refus_rate_pct": 0.0,
                       "open_blocking": 0, "open_blocking_late": 0},
        "bloc1": [],
        "bloc2": {"labels": [], "s1_series": [], "s2_series": [], "s3_series": [],
                  "hm_series": [], "open_series": [], "totals": []},
        "bloc3": _empty_bloc3(s1, s2, s3),
        "non_saisi": None,
        "degraded_mode": True,
        "warnings": list(ctx.warnings or []) + (warnings or []),
    }


def _build_non_saisi(docs: pd.DataFrame, consultant_name: str) -> dict[str, Any] | None:
    """Compute non-saisi GED stats for BET merge consultants.

    Returns None for non-BET consultants (no badge shown).
    Returns dict with count, pct, badge color for BET consultants.
    """
    if consultant_name not in BET_MERGE_KEYS:
        return None

    if docs.empty or "response_source" not in docs.columns:
        return {"count": 0, "pct": 0.0, "badge": "green", "total_answered": 0}

    # Count answered docs (closed = has a final status)
    closed_mask = ~docs["_is_open"]
    total_answered = int(closed_mask.sum())

    if total_answered == 0:
        return {"count": 0, "pct": 0.0, "badge": "green", "total_answered": 0}

    # Count how many of the answered docs came from PDF only
    pdf_only = int(
        ((docs["response_source"] == "PDF_REPORT") & closed_mask).sum()
    ) if "response_source" in docs.columns else 0

    # Also count observation-enriched
    obs_enriched = int(
        (docs["response_source"] == "GED+PDF_OBS").sum()
    ) if "response_source" in docs.columns else 0

    pct = round((pdf_only / total_answered) * 100, 1) if total_answered else 0.0

    if pct < 5:
        badge = "green"
    elif pct < 10:
        badge = "orange"
    else:
        badge = "red"

    return {
        "count": pdf_only,
        "pct": pct,
        "badge": badge,
        "total_answered": total_answered,
        "obs_enriched": obs_enriched,
    }


def _empty_bloc3(s1: str, s2: str, s3: str) -> dict[str, Any]:
    return {
        "s1": s1, "s2": s2, "s3": s3,
        "lots": [],
        "total_row": {"total": 0, "VSO": 0, "VAO": 0, "REF": 0, "HM": 0,
                      "open_ok": 0, "open_late": 0,
                      "open_blocking_ok": 0, "open_blocking_late": 0, "open_nb": 0},
        "donut_total": 0, "donut_ok": 0, "donut_late": 0, "donut_nb": 0,
        "critical_lots": [], "refus_lots": [],
    }
