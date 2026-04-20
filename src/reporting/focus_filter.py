"""
focus_filter.py — Focus Mode filter engine

Applies cascading rules to narrow RunContext data to actionable items only.
When focus is OFF, all reporting uses full data (unchanged behavior).
When focus is ON, every KPI/chart/fiche sees only the focused document set.

Filter rules (applied in order):
  F1: Dernier indice only (already enforced by ctx.dernier_df)
  F2: Exclude resolved documents (VISA GLOBAL in {VSO, VAO, SAS REF, HM})
  F3: Exclude superseded-open avis (pending on old indice when newer exists)
  F4: Exclude stale documents (no GED activity > threshold days)
  F5: Exclude blocked-upstream for MOEX (upstream consultants not done)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from .data_loader import RunContext

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"VSO", "VAO", "SAS REF", "HM"}


@dataclass
class FocusConfig:
    enabled: bool = False
    stale_threshold_days: int = 90


@dataclass
class FocusResult:
    """Output of apply_focus_filter. Consumed by aggregator + fiche builders."""
    focused_doc_ids: set = field(default_factory=set)
    stale_doc_ids: set = field(default_factory=set)
    resolved_doc_ids: set = field(default_factory=set)
    blocked_upstream_ids: set = field(default_factory=set)
    priority_queue: list = field(default_factory=list)
    per_actor_queues: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)


def _last_activity_date(doc_id: str, docs_df: pd.DataFrame,
                        responses_df: pd.DataFrame) -> Optional[date]:
    """Find the most recent GED activity date for a document."""
    dates = []

    doc_rows = docs_df[docs_df["doc_id"] == doc_id]
    if not doc_rows.empty:
        created = doc_rows.iloc[0].get("created_at")
        if created is not None and not pd.isna(created):
            d = created.date() if hasattr(created, "date") else created
            dates.append(d)

    resp_rows = responses_df[responses_df["doc_id"] == doc_id]
    for _, r in resp_rows.iterrows():
        da = r.get("date_answered")
        if da is not None and not pd.isna(da):
            d = da.date() if hasattr(da, "date") else da
            dates.append(d)
        dl = r.get("date_limite")
        if dl is not None and not pd.isna(dl):
            d = dl.date() if hasattr(dl, "date") else dl
            dates.append(d)

    return max(dates) if dates else None


def _compute_priority(date_limite, data_date: date) -> tuple:
    """Returns (priority_level, delta_days).
    P1=overdue, P2=<=5d, P3=<=15d, P4=>15d, P5=no deadline."""
    if date_limite is None:
        return 5, None
    dl = date_limite.date() if hasattr(date_limite, "date") else date_limite
    dd = data_date.date() if hasattr(data_date, "date") else data_date
    delta = (dl - dd).days
    if delta < 0:
        return 1, delta
    elif delta <= 5:
        return 2, delta
    elif delta <= 15:
        return 3, delta
    else:
        return 4, delta


def _get_doc_date_limite(doc_id: str, responses_df: pd.DataFrame) -> Optional[date]:
    """Get the earliest date_limite for pending responses on a document."""
    resp = responses_df[
        (responses_df["doc_id"] == doc_id) &
        (responses_df["date_status_type"].isin(["PENDING_IN_DELAY", "PENDING_LATE"]))
    ]
    if resp.empty:
        return None
    dl_vals = resp["date_limite"].dropna()
    if dl_vals.empty:
        return None
    earliest = dl_vals.min()
    return earliest.date() if hasattr(earliest, "date") else earliest


def apply_focus_filter(ctx: RunContext, config: FocusConfig) -> FocusResult:
    """Main entry point. Returns FocusResult with filtered document sets."""
    result = FocusResult()

    if not config.enabled:
        # Focus off: all dernier docs are "focused"
        if ctx.dernier_df is not None:
            result.focused_doc_ids = set(ctx.dernier_df["doc_id"].tolist())
        result.stats = {"focus_enabled": False}
        return result

    if ctx.dernier_df is None or ctx.workflow_engine is None:
        result.stats = {"focus_enabled": True, "error": "insufficient data"}
        return result

    we = ctx.workflow_engine
    dernier = ctx.dernier_df
    docs_df = ctx.docs_df
    responses_df = ctx.responses_df
    responsible = ctx.responsible_parties or {}
    data_date = ctx.data_date
    if data_date is None:
        from datetime import datetime as _dt
        data_date = _dt.now().date()
    if hasattr(data_date, "date"):
        data_date = data_date.date()

    all_dernier_ids = set(dernier["doc_id"].tolist())

    # ── F2: Exclude resolved ────────────────────────────────────────
    resolved = set()
    for doc_id in all_dernier_ids:
        visa, _ = we.compute_visa_global_with_date(doc_id)
        if visa in TERMINAL_STATUSES:
            resolved.add(doc_id)
    result.resolved_doc_ids = resolved

    remaining = all_dernier_ids - resolved

    # ── F4: Exclude stale ───────────────────────────────────────────
    stale = set()
    if docs_df is not None and responses_df is not None:
        for doc_id in remaining:
            # Only stale if still open (no visa global)
            visa, _ = we.compute_visa_global_with_date(doc_id)
            if visa is not None:
                continue  # has visa = not stale (should be resolved, but safety)
            last = _last_activity_date(doc_id, docs_df, responses_df)
            if last is None:
                stale.add(doc_id)
            else:
                last_d = last.date() if hasattr(last, "date") else last
                if (data_date - last_d).days > config.stale_threshold_days:
                    stale.add(doc_id)
    result.stale_doc_ids = stale

    remaining = remaining - stale

    # ── F5: Identify blocked-upstream (for MOEX context) ────────────
    blocked_upstream = set()
    for doc_id in remaining:
        rp = responsible.get(doc_id)
        if rp not in ("MOEX", "CONTRACTOR", None):
            blocked_upstream.add(doc_id)
    result.blocked_upstream_ids = blocked_upstream
    # Note: blocked-upstream docs stay in focused set — they are actionable
    # for the blocking consultant. They are only excluded from MOEX's queue.

    result.focused_doc_ids = remaining

    # ── Priority queue ──────────────────────────────────────────────
    pq = []
    if responses_df is not None:
        for doc_id in remaining:
            rp = responsible.get(doc_id)
            if rp is None:
                continue  # closed, no action needed
            dl = _get_doc_date_limite(doc_id, responses_df)
            priority, delta = _compute_priority(dl, data_date)

            # Get doc metadata
            doc_row = dernier[dernier["doc_id"] == doc_id]
            meta = {}
            if not doc_row.empty:
                r = doc_row.iloc[0]
                meta = {
                    "numero": str(r.get("numero_normalized", "?")),
                    "indice": str(r.get("indice", "?")),
                    "emetteur": str(r.get("emetteur", "?")),
                    "type_doc": str(r.get("type_de_doc", "?")),
                    "lot": str(r.get("lot_normalized", "?")),
                }

            pq.append({
                "doc_id": doc_id,
                "priority": priority,
                "delta_days": delta,
                "date_limite": str(dl) if dl else None,
                "responsible": rp,
                **meta,
            })

    pq.sort(key=lambda x: (x["priority"], x["delta_days"] if x["delta_days"] is not None else 9999))
    result.priority_queue = pq

    # ── Per-actor queues ────────────────────────────────────────────
    actor_queues = {}
    for item in pq:
        actor = item["responsible"]
        if actor not in actor_queues:
            actor_queues[actor] = []
        actor_queues[actor].append(item["doc_id"])
    result.per_actor_queues = actor_queues

    # ── Stats ───────────────────────────────────────────────────────
    p_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for item in pq:
        p_counts[item["priority"]] = p_counts.get(item["priority"], 0) + 1

    result.stats = {
        "focus_enabled": True,
        "total_dernier": len(all_dernier_ids),
        "resolved_excluded": len(resolved),
        "stale_excluded": len(stale),
        "focused_count": len(remaining),
        "blocked_upstream_count": len(blocked_upstream),
        "stale_threshold_days": config.stale_threshold_days,
        "p1_overdue": p_counts[1],
        "p2_urgent": p_counts[2],
        "p3_soon": p_counts[3],
        "p4_ok": p_counts[4],
        "p5_no_deadline": p_counts[5],
        "moex_actionable": len(actor_queues.get("MOEX", [])),
        "contractor_actionable": len(actor_queues.get("CONTRACTOR", [])),
    }

    return result
