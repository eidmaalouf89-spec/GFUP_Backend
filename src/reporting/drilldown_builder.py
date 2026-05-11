"""
drilldown_builder.py — Backend-driven dashboard drilldowns
Builds document lists for Overview KPI, chart, and visa-stage drilldowns.

kind taxonomy:
  • submitted:                All dernier docs
  • pending_blocking:         Docs with no terminal visa
  • visa_segment:             Docs matching a specific VISA status or deadline state
  • weekly:                   Docs submitted in a specific ISO week
  • focus_priority:           Focused docs at a specific priority tier (requires focus_result)
  • operational_total:        All rows in the operational universe (Step 2)
  • operational_fresh:        Operational rows with last activity ≤ stale threshold
  • operational_stale:        Operational rows with last activity > stale threshold
  • operational_moex:         Operational rows with tier=="MOEX" (excl. MOEX SAS owner).
                              Optional params.scope ∈ {"fresh","stale"} narrows.
  • operational_consultants:  Operational rows with tier ∈ {"PRIMARY","SECONDARY"}.
                              Optional params.tier ∈ {"PRIMARY","SECONDARY"} narrows.
  • operational_enterprise_ref: REF/SAS REF rows in the broad operational bucket
                              (mirrors aggregator.enterprise_ref_sas_candidates).
  • operational_priority:     Operational rows by priority bucket (params.priority 1..4).
"""
from typing import Optional
import pandas as pd
import math
from datetime import datetime

from .data_loader import RunContext
from .contractor_fiche import resolve_emetteur_name
from .aggregator import compute_operational_universe, _OPERATIONAL_STALE_THRESHOLD
from .latest_chain_view import latest_enriched_view

if False:
    from .focus_filter import FocusResult

ROW_LIMIT = 1000


def _to_iso(val):
    """Convert pandas Timestamp/datetime/date/None to ISO 8601 date string
    (YYYY-MM-DD). If null/NaT, return None."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    try:
        # plain datetime.date does not have a .date() method; check first.
        from datetime import date as _date_cls, datetime as _dt_cls
        if isinstance(val, _dt_cls):
            return val.date().isoformat()
        if isinstance(val, _date_cls):
            return val.isoformat()
        if hasattr(val, 'date'):
            return val.date().isoformat()
        if isinstance(val, str):
            # Try to parse and re-format
            try:
                dt = pd.to_datetime(val)
                return dt.date().isoformat()
            except:
                return None
        return None
    except:
        return None


def _primary_owner(row):
    """Extract primary owner from _focus_owner list or None."""
    owners = row.get("_focus_owner")
    if isinstance(owners, list) and len(owners) > 0:
        return owners[0]
    return None


def _row_to_payload(row, latest_status, primary_owner, code=None) -> dict:
    """Convert a dernier_df row + computed values to drilldown row shape.

    Adds the columns required by ui/jansa/fiche_base.jsx::DrilldownDrawer
    (date_soumission, date_limite, remaining_days, status, emetteur)
    so the dashboard drilldowns can render via the same drawer as the
    consultant fiche. Existing keys (last_action_date, latest_status,
    emetteur_code, emetteur_name, primary_owner) are preserved.
    """
    if code is None:
        code = (row.get("emetteur") or "").strip()
    emetteur_name = resolve_emetteur_name(code)
    # Earliest pending-response deadline (post 30d-fallback) and days-to-deadline
    # are pre-computed on dernier_df by data_loader._precompute_focus_columns.
    date_limite_iso = _to_iso(row.get("_earliest_deadline"))
    rd = row.get("_days_to_deadline")
    if rd is None or (isinstance(rd, float) and math.isnan(rd)):
        remaining_days = None
    else:
        try:
            remaining_days = int(rd)
        except Exception:
            remaining_days = None
    # dernier_df carries `libelle_du_document` (FLAT_GED column) rather than
    # `titre`; mirror app.py::get_doc_details (which reads
    # libelle_du_document) so the row title is non-empty in the drawer.
    titre_val = row.get("titre") or row.get("libelle_du_document")
    # dernier_df carries `created_at` (from FLAT_GED `cree_le`) rather than
    # `submittal_date`; mirror app.py::get_doc_details which reads
    # `created_at` for the soumission date.
    soumission_val = (
        row.get("submittal_date")
        or row.get("created_at")
        or row.get("cree_le")
    )
    return {
        "numero": row.get("numero"),
        "indice": row.get("indice"),
        "titre": titre_val,
        "emetteur_code": code,
        "emetteur_name": emetteur_name,
        # Drawer reads `emetteur` directly; surface the canonical name there.
        "emetteur": emetteur_name or code,
        "lot": row.get("lot_normalized") or row.get("lot"),
        "last_action_date": _to_iso(
            row.get("last_real_activity_date") or
            row.get("response_date") or
            row.get("submittal_date") or
            row.get("created_at")
        ),
        "date_soumission": _to_iso(soumission_val),
        "date_limite": date_limite_iso,
        "remaining_days": remaining_days,
        "latest_status": latest_status,
        # Drawer reads `status`; mirror latest_status (kept for back-compat).
        "status": latest_status,
        "primary_owner": primary_owner,
    }


def _parse_week_label(week_label: str):
    """Parse week label like '26-S14' into (year, week_num).
    Returns (year, week_num) or (None, None) if parse fails."""
    try:
        if not week_label or "-S" not in week_label:
            return None, None
        parts = week_label.split("-S")
        if len(parts) != 2:
            return None, None
        year_short = parts[0].strip()
        week_str = parts[1].strip()

        # Expand short year (e.g. "26" -> "2026")
        year = int(year_short)
        if year < 100:
            year = 2000 + year

        week_num = int(week_str)
        return year, week_num
    except:
        return None, None


def _matches_week(row, target_year, target_week):
    """Check if a row's submittal_date falls in the target ISO week."""
    try:
        created = row.get("submittal_date") or row.get("created_at")
        if created is None or pd.isna(created):
            return False
        iso = created.isocalendar()
        return iso[0] == target_year and iso[1] == target_week
    except:
        return False


def build_drilldown(ctx: RunContext, kind: str, params: Optional[dict] = None,
                     focus_result: Optional["FocusResult"] = None) -> dict:
    """
    Build a drilldown payload for the Overview dashboard.

    Args:
        ctx: RunContext with dernier_df, workflow_engine
        kind: drilldown type (submitted, pending_blocking, visa_segment, weekly, focus_priority)
        params: drilldown-specific parameters (segment, week_label, priority, etc.)
        focus_result: FocusResult for focus mode queries

    Returns:
        {rows: [...], total_count: int, truncated: bool, kind: str, params: dict}
    """
    params = params or {}

    if ctx.dernier_df is None or ctx.workflow_engine is None:
        return {"rows": [], "total_count": 0, "truncated": False, "kind": kind, "params": params}

    df = latest_enriched_view(ctx)
    we = ctx.workflow_engine
    selected = []

    # ── Dispatch by kind ──────────────────────────────────────────

    if kind == "submitted":
        # All docs in dernier_df
        for _, row in df.iterrows():
            doc_id = row.get("doc_id")
            visa, _ = we.compute_visa_global_with_date(doc_id)
            latest_status = visa or "En attente"
            owner = _primary_owner(row)
            code = (row.get("emetteur") or "").strip()
            selected.append(_row_to_payload(row, latest_status, owner, code))

    elif kind == "pending_blocking":
        # Docs with _visa_global is None
        for _, row in df.iterrows():
            visa_global = row.get("_visa_global")
            if visa_global is None or (isinstance(visa_global, float) and pd.isna(visa_global)):
                owner = _primary_owner(row)
                code = (row.get("emetteur") or "").strip()
                selected.append(_row_to_payload(row, "En attente", owner, code))

    elif kind == "visa_segment":
        segment = params.get("segment")

        if segment in ("VSO", "VAO", "REF", "HM"):
            # Direct match on _visa_global
            for _, row in df.iterrows():
                visa_global = row.get("_visa_global")
                if visa_global == segment:
                    owner = _primary_owner(row)
                    code = (row.get("emetteur") or "").strip()
                    selected.append(_row_to_payload(row, segment, owner, code))

        elif segment == "SAS_REF":
            # _visa_global stores "SAS REF" (with space), but we normalize on entry
            for _, row in df.iterrows():
                visa_global = row.get("_visa_global")
                if visa_global == "SAS REF":
                    owner = _primary_owner(row)
                    code = (row.get("emetteur") or "").strip()
                    selected.append(_row_to_payload(row, "SAS REF", owner, code))

        elif segment == "PENDING_ON_TIME":
            # _visa_global is None and _days_to_deadline >= 0
            for _, row in df.iterrows():
                visa_global = row.get("_visa_global")
                days_to_deadline = row.get("_days_to_deadline")
                if (visa_global is None or (isinstance(visa_global, float) and pd.isna(visa_global))) and \
                   (days_to_deadline is not None and not (isinstance(days_to_deadline, float) and pd.isna(days_to_deadline)) and days_to_deadline >= 0):
                    owner = _primary_owner(row)
                    code = (row.get("emetteur") or "").strip()
                    selected.append(_row_to_payload(row, "En attente · dans les délais", owner, code))

        elif segment == "PENDING_LATE":
            # _visa_global is None and _days_to_deadline < 0
            for _, row in df.iterrows():
                visa_global = row.get("_visa_global")
                days_to_deadline = row.get("_days_to_deadline")
                if (visa_global is None or (isinstance(visa_global, float) and pd.isna(visa_global))) and \
                   (days_to_deadline is not None and not (isinstance(days_to_deadline, float) and pd.isna(days_to_deadline)) and days_to_deadline < 0):
                    owner = _primary_owner(row)
                    code = (row.get("emetteur") or "").strip()
                    selected.append(_row_to_payload(row, "En attente · en retard", owner, code))
        else:
            return {"error": f"unknown segment: {segment}", "rows": [], "total_count": 0, "truncated": False, "kind": kind, "params": params}

    elif kind == "weekly":
        metric = params.get("metric")
        week_label = params.get("week_label")

        if metric not in ("opened", "closed", "refused"):
            return {"error": f"unknown metric: {metric}", "rows": [], "total_count": 0, "truncated": False, "kind": kind, "params": params}

        target_year, target_week = _parse_week_label(week_label)
        if target_year is None:
            return {"error": f"invalid week_label: {week_label}", "rows": [], "total_count": 0, "truncated": False, "kind": kind, "params": params}

        if metric == "opened":
            # Docs submitted (submittal_date) in this ISO week
            for _, row in df.iterrows():
                if _matches_week(row, target_year, target_week):
                    doc_id = row.get("doc_id")
                    visa, _ = we.compute_visa_global_with_date(doc_id)
                    latest_status = visa or "En attente"
                    owner = _primary_owner(row)
                    code = (row.get("emetteur") or "").strip()
                    selected.append(_row_to_payload(row, latest_status, owner, code))
        else:
            # closed / refused: defensive implementation (not wired in this phase)
            # For now, return empty
            pass

    elif kind == "focus_priority":
        if focus_result is None:
            return {"error": "focus mode required", "rows": [], "total_count": 0, "truncated": False, "kind": kind, "params": params}

        priority = params.get("priority")
        if priority not in (1, 2, 3, 4):
            return {"error": f"invalid priority: {priority}", "rows": [], "total_count": 0, "truncated": False, "kind": kind, "params": params}

        # Filter by _focus_priority == priority AND _focus_owner_tier != "CLOSED"
        for _, row in df.iterrows():
            focus_priority = row.get("_focus_priority")
            focus_owner_tier = row.get("_focus_owner_tier")
            if focus_priority == priority and focus_owner_tier != "CLOSED":
                doc_id = row.get("doc_id")
                visa, _ = we.compute_visa_global_with_date(doc_id)
                latest_status = visa or "En attente"
                owner = _primary_owner(row)
                code = (row.get("emetteur") or "").strip()
                selected.append(_row_to_payload(row, latest_status, owner, code))

    elif kind in (
        "operational_total",
        "operational_fresh",
        "operational_stale",
        "operational_moex",
        "operational_consultants",
        "operational_enterprise_ref",
        "operational_priority",
    ):
        # Reuse the exact aggregator masking — no recomputation.
        op_broad, op = compute_operational_universe(ctx)

        def _emit(sub_df):
            for _, row in sub_df.iterrows():
                visa_global = row.get("_visa_global")
                if visa_global is None or (isinstance(visa_global, float) and pd.isna(visa_global)):
                    latest_status = "En attente"
                else:
                    latest_status = str(visa_global)
                owner = _primary_owner(row)
                code = (row.get("emetteur") or "").strip()
                selected.append(_row_to_payload(row, latest_status, owner, code))

        if kind == "operational_total":
            _emit(op)

        elif kind == "operational_fresh":
            _emit(op[op["_days_since_last_activity"] <= _OPERATIONAL_STALE_THRESHOLD])

        elif kind == "operational_stale":
            _emit(op[op["_days_since_last_activity"] > _OPERATIONAL_STALE_THRESHOLD])

        elif kind == "operational_moex":
            # Normal Maître d'Œuvre EXE only; excludes owner ["MOEX SAS"].
            # Mirrors compute_operational_dashboard moex_mask.
            def _is_moex_sas(owner_val):
                try:
                    return isinstance(owner_val, list) and owner_val == ["MOEX SAS"]
                except Exception:
                    return False
            tier_mask = op["_focus_owner_tier"] == "MOEX"
            sas_mask = op["_focus_owner"].apply(_is_moex_sas)
            sub = op[tier_mask & (~sas_mask)]
            scope = params.get("scope")
            if scope == "fresh":
                sub = sub[sub["_days_since_last_activity"] <= _OPERATIONAL_STALE_THRESHOLD]
            elif scope == "stale":
                sub = sub[sub["_days_since_last_activity"] > _OPERATIONAL_STALE_THRESHOLD]
            _emit(sub)

        elif kind == "operational_consultants":
            tier_param = params.get("tier")
            if tier_param == "PRIMARY":
                sub = op[op["_focus_owner_tier"] == "PRIMARY"]
            elif tier_param == "SECONDARY":
                sub = op[op["_focus_owner_tier"] == "SECONDARY"]
            else:
                sub = op[op["_focus_owner_tier"].isin(["PRIMARY", "SECONDARY"])]
            _emit(sub)

        elif kind == "operational_enterprise_ref":
            # Mirrors aggregator.enterprise_ref_sas_candidates: REF/SAS REF over
            # the BROAD bucket (op_broad), not the narrowed op.
            _emit(op_broad[op_broad["_visa_global"].isin(["REF", "SAS REF"])])

        elif kind == "operational_priority":
            priority = params.get("priority")
            if priority not in (1, 2, 3, 4):
                return {"error": f"invalid priority: {priority}", "rows": [], "total_count": 0, "truncated": False, "kind": kind, "params": params}
            _emit(op[op["_focus_priority"] == priority])

    else:
        return {"error": "unknown kind", "rows": [], "total_count": 0, "truncated": False, "kind": kind, "params": params}

    # Stable two-pass sort: numero ASC first, then last_action_date DESC.
    # Python's sort is stable, so ties on date preserve numero ASC order.
    selected.sort(key=lambda r: str(r.get("numero") or ""))
    selected.sort(key=lambda r: r.get("last_action_date") or "", reverse=True)

    # ── Cap at ROW_LIMIT ──
    total = len(selected)
    truncated = total > ROW_LIMIT
    rows = selected[:ROW_LIMIT]

    return {
        "rows": rows,
        "total_count": total,
        "truncated": truncated,
        "kind": kind,
        "params": params,
    }
