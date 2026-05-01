"""
drilldown_builder.py — Backend-driven dashboard drilldowns
Builds document lists for Overview KPI, chart, and visa-stage drilldowns.

kind taxonomy:
  • submitted:        All dernier docs
  • pending_blocking: Docs with no terminal visa
  • visa_segment:     Docs matching a specific VISA status or deadline state
  • weekly:          Docs submitted in a specific ISO week
  • focus_priority:   Focused docs at a specific priority tier (requires focus_result)
"""
from typing import Optional
import pandas as pd
import math
from datetime import datetime

from .data_loader import RunContext
from .contractor_fiche import resolve_emetteur_name

if False:
    from .focus_filter import FocusResult

ROW_LIMIT = 1000


def _to_iso(val):
    """Convert pandas Timestamp/datetime/None to ISO 8601 date string (YYYY-MM-DD).
    If null/NaT, return None."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    try:
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
    """Convert a dernier_df row + computed values to drilldown row shape."""
    if code is None:
        code = (row.get("emetteur") or "").strip()
    return {
        "numero": row.get("numero"),
        "indice": row.get("indice"),
        "titre": row.get("titre"),
        "emetteur_code": code,
        "emetteur_name": resolve_emetteur_name(code),
        "lot": row.get("lot_normalized") or row.get("lot"),
        "last_action_date": _to_iso(
            row.get("last_real_activity_date") or
            row.get("response_date") or
            row.get("submittal_date")
        ),
        "latest_status": latest_status,
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

    df = ctx.dernier_df
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
