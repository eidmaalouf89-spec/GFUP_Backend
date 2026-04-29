"""
src/reporting/ui_adapter.py

Transforms backend reporting data into the shapes expected by the JANSA
standalone dashboard (window.OVERVIEW, window.CONSULTANTS, etc.).

This is a pure adapter layer — no new computation. It reshapes existing
output from aggregator.py / consultant_fiche.py into the UI contract
defined in codex prompts/facelift/prototype/jansa/data.js.
"""

from __future__ import annotations
import math
from datetime import date, datetime
from typing import Optional

from .data_loader import RunContext
from .consultant_fiche import (
    CONSULTANT_DISPLAY_NAMES,
    ROLE_BY_CANONICAL,
    CONTRACTOR_REFERENCE,
)


# ── Group assignment for consultants ─────────────────────────────────────
# Maps canonical consultant name → UI group (MOEX / Primary / Secondary)

_CONSULTANT_GROUPS = {
    "Maître d'Oeuvre EXE":  "MOEX",
    "MOEX SAS":             "MOEX",
    "ARCHITECTE":           "Primary",
    "BET Structure":        "Primary",
    "BET CVC":              "Primary",
    "BET Electricité":      "Primary",
    "BET Plomberie":        "Primary",
    "Bureau de Contrôle":   "Primary",
}
# Everything not listed above is "Secondary"


def _slugify(name: str) -> str:
    """Turn a canonical name into a URL-safe slug."""
    import re
    s = name.upper().replace(" ", "_").replace("'", "_")
    s = re.sub(r"[^A-Z0-9_]", "", s)
    return s


def _safe_pct(num, denom, decimals=1):
    if not denom:
        return 0.0
    return round(num / denom * 100, decimals)


def _iso_week_label(d):
    """Format a date as '26-S14' (short year + ISO week)."""
    iso = d.isocalendar()
    return f"{iso[0] % 100}-S{iso[1]:02d}"


def adapt_overview(dashboard_data: dict, app_state: dict) -> dict:
    """
    Transform get_dashboard_data() output → window.OVERVIEW shape.

    Fields that have no backend source are set to None with a
    '_missing' annotation so the UI can display 'Not yet connected'.
    """
    kpis = dashboard_data.get("kpis", {})
    monthly = dashboard_data.get("monthly", [])
    consultants = dashboard_data.get("consultants", [])
    contractors = dashboard_data.get("contractors", [])
    focus = dashboard_data.get("focus", {})

    # Run metadata
    run_number = kpis.get("run_number") or app_state.get("current_run") or 0
    total_runs = app_state.get("total_runs", run_number)
    run_date = kpis.get("run_date")

    # Parse data_date
    data_date = None
    if run_date:
        if isinstance(run_date, str):
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
                try:
                    data_date = datetime.strptime(run_date[:19], fmt).date()
                    break
                except (ValueError, TypeError):
                    pass
        elif isinstance(run_date, (date, datetime)):
            data_date = run_date if isinstance(run_date, date) else run_date.date()
    if data_date is None:
        data_date = date.today()

    week_num = data_date.isocalendar()[1]
    data_date_str = data_date.strftime("%d/%m/%Y")

    # KPI totals
    visa = kpis.get("by_visa_global", {})
    total_docs = kpis.get("total_docs_current", 0)
    vso = visa.get("VSO", 0)
    vao = visa.get("VAO", 0)
    ref = visa.get("REF", 0)
    sas_ref = visa.get("SAS REF", 0)
    hm = visa.get("HM", 0)
    open_count = visa.get("Open", 0)
    answered = vso + vao + ref + sas_ref + hm

    refus_rate = _safe_pct(ref + sas_ref, total_docs)

    # Best consultant (highest approval rate with >= 10 docs)
    best_consultant = {"name": "—", "slug": "", "pass_rate": 0, "delta": None}
    for c in consultants:
        called = c.get("docs_called", 0)
        if called >= 10:
            rate = _safe_pct(c.get("vso", 0) + c.get("vao", 0), called)
            if rate > best_consultant["pass_rate"]:
                best_consultant = {
                    "name": c["name"],
                    "slug": _slugify(c["name"]),
                    "pass_rate": rate,
                    "delta": None,  # Not yet connected — requires run comparison
                }

    # Best contractor (highest approval rate with >= 10 docs)
    best_contractor = {"code": "—", "name": "—", "pass_rate": 0, "delta": None}
    for ct in contractors:
        total = ct.get("total_submitted", 0)
        if total >= 10:
            rate = _safe_pct(ct.get("visa_vso", 0) + ct.get("visa_vao", 0), total)
            if rate > best_contractor["pass_rate"]:
                best_contractor = {
                    "code": ct.get("code", ct["name"]),
                    "name": ct["name"],
                    "pass_rate": rate,
                    "delta": None,  # Not yet connected
                }

    # Visa flow
    visa_flow = {
        "submitted": total_docs,
        "answered": answered,
        "vso": vso,
        "vao": vao,
        "ref": ref + sas_ref,
        "hm": hm,
        "pending": open_count,
        "on_time": None,   # Not yet connected — requires per-doc deadline check
        "late": None,       # Not yet connected
    }

    # Weekly/monthly activity → convert to UI format
    weekly = []
    for entry in monthly:
        label = entry.get("month", "")
        # Convert "2026-01" → "26-S02" style, or pass through if already week format
        if "-S" in label:
            weekly.append({
                "label": label.replace("20", "", 1) if label.startswith("20") else label,
                "opened": entry.get("total", 0),
                "closed": entry.get("vso", 0) + entry.get("vao", 0),
                "refused": entry.get("ref", 0) + entry.get("sas_ref", 0),
            })
        else:
            # Monthly: format as "Jan 26"
            try:
                dt = datetime.strptime(label, "%Y-%m")
                short = dt.strftime("%b %y")
            except (ValueError, TypeError):
                short = label
            weekly.append({
                "label": short,
                "opened": entry.get("total", 0),
                "closed": entry.get("vso", 0) + entry.get("vao", 0),
                "refused": entry.get("ref", 0) + entry.get("sas_ref", 0),
            })

    # Focus stats — normalize backend shape to UI-expected shape
    # Backend uses focus_result.stats keys like "focused_count", "stale_excluded", etc.
    # UI expects "focused", "stale", "excluded", "by_consultant" (array).
    _empty_focus = {
        "focused": 0, "p1_overdue": 0, "p2_urgent": 0, "p3_soon": 0, "p4_ok": 0,
        "total_dernier": total_docs, "excluded": 0, "stale": 0, "resolved": 0,
        "by_consultant": [],
        "by_contractor": [],
    }
    if focus and isinstance(focus, dict) and focus.get("focus_enabled"):
        focus_stats = {
            "focused":      focus.get("focused_count", focus.get("focused", 0)),
            "p1_overdue":   focus.get("p1_overdue", 0),
            "p2_urgent":    focus.get("p2_urgent", 0),
            "p3_soon":      focus.get("p3_soon", 0),
            "p4_ok":        focus.get("p4_ok", 0),
            "total_dernier": focus.get("total_dernier", total_docs),
            "excluded":     focus.get("stale_excluded", 0) + focus.get("resolved_excluded", 0),
            "stale":        focus.get("stale_excluded", 0),
            "resolved":     focus.get("resolved_excluded", 0),
            "by_consultant": focus.get("by_consultant", []),
            "by_contractor": focus.get("by_contractor", []),
        }
    else:
        focus_stats = _empty_focus

    return {
        "week_num": week_num,
        "data_date_str": data_date_str,
        "run_number": run_number,
        "total_runs": total_runs,
        "total_docs": total_docs,
        "total_docs_delta": None,           # Not yet connected — requires run comparison
        "pending_blocking": open_count,
        "pending_blocking_delta": None,     # Not yet connected
        "refus_rate": refus_rate,
        "refus_rate_delta": None,           # Not yet connected
        "best_consultant": best_consultant,
        "best_contractor": best_contractor,
        "visa_flow": visa_flow,
        "weekly": weekly,
        "focus": focus_stats,
        # --- Overview parity fields (Step 03) ---
        "degraded_mode": bool(kpis.get("degraded_mode", False)),
        "warnings": list(kpis.get("warnings") or []) + list(app_state.get("warnings") or []),
        "project_stats": {
            "total_consultants": kpis.get("total_consultants") or 0,
            "total_contractors": kpis.get("total_contractors") or 0,
            "avg_days_to_visa":  kpis.get("avg_days_to_visa"),
            "docs_pending_sas":  kpis.get("docs_pending_sas"),
        },
        "system_status": {
            "has_baseline":     bool(app_state.get("has_baseline", False)),
            "ged_file_detected": bool(app_state.get("ged_file_detected")),
            "gf_file_detected":  bool(app_state.get("gf_file_detected")),
            "pipeline_running":  bool(app_state.get("pipeline_running", False)),
        },
        # --- Utilities parity (Step 11) ---
        # Priority queue (top-50 focus documents) — populated only when focus=True
        "priority_queue": list(dashboard_data.get("priority_queue", [])),
        "legacy_backlog_count": dashboard_data.get("legacy_backlog_count", 0),
    }


def adapt_consultants(consultant_list: list) -> list:
    """
    Transform compute_consultant_summary() output → window.CONSULTANTS shape.
    """
    result = []
    for i, c in enumerate(consultant_list):
        name = c.get("name", "")
        called = c.get("docs_called", 0)
        answered = c.get("docs_answered", 0)
        vso = c.get("vso", 0)
        vao = c.get("vao", 0)

        group = _CONSULTANT_GROUPS.get(name, "Secondary")
        role = ROLE_BY_CANONICAL.get(name, name)
        display = CONSULTANT_DISPLAY_NAMES.get(name)
        display_name = f"{name} — {display}" if display and display != name else name

        result.append({
            "id": i + 1,
            "slug": _slugify(name),
            "name": display_name,
            "canonical_name": name,  # Needed for fiche API call
            "role": role,
            "group": group,
            "total": called,
            "answered": answered,
            "pending": c.get("open", 0),
            "pass_rate": round(c.get("response_rate", 0) * 100),
            "trend": [],  # Not yet connected — requires historical run data
            "badge": "Pilote" if group == "MOEX" and not c.get("is_sas") else None,
            "is_sas": c.get("is_sas", False),
            "focus_owned": c.get("focus_owned", 0),
            "vso": vso,
            "vao": vao,
            "ref": c.get("ref", 0),
            "hm": c.get("hm", 0),
            "avg_response_days": c.get("avg_response_days"),
            "open_blocking": c.get("open_blocking", 0),
            "s1_label": c.get("s1_label", "VSO"),
            "s2_label": c.get("s2_label", "VAO"),
            "s3_label": c.get("s3_label", "REF"),
        })

    return result


def adapt_contractors_list(contractor_list: list, focus: bool = False) -> list:
    """
    Transform compute_contractor_summary() output → window.CONTRACTORS_LIST shape.
    Returns ALL eligible contractors (≥5 docs) with canonical names.
    Sort: by docs DESC normally; by (focus_owned, docs) DESC in focus mode.
    Pass-rate sort intentionally NOT used — it buries large emetteurs.
    """
    from .contractor_fiche import resolve_emetteur_name
    scored = []
    for ct in contractor_list:
        total = ct.get("total_submitted", 0)
        if total < 5:
            continue
        rate = _safe_pct(ct.get("visa_vso", 0) + ct.get("visa_vao", 0), total)
        code = ct.get("code", ct["name"])
        scored.append({
            "code":         code,
            "name":         resolve_emetteur_name(code) or ct["name"],
            "docs":         total,
            "pass_rate":    rate,
            "delta":        None,
            "focus_owned":  ct.get("focus_owned", 0),
        })
    if focus:
        scored.sort(key=lambda x: (x["focus_owned"], x["docs"]), reverse=True)
    else:
        scored.sort(key=lambda x: x["docs"], reverse=True)
    return scored[:50]


def adapt_contractors_lookup(contractor_list: list) -> dict:
    """Build window.CONTRACTORS code→canonical name lookup."""
    from .contractor_fiche import resolve_emetteur_name
    return {
        ct.get("code", ct["name"]): (resolve_emetteur_name(ct.get("code", ct["name"])) or ct["name"])
        for ct in contractor_list
    }
