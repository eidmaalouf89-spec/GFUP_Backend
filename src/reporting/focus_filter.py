"""
focus_filter.py — Focus Mode filter engine (v2)

Uses pre-computed columns on dernier_df (from data_loader + focus_ownership)
for instant DataFrame filtering. No per-doc loops.

Pre-computed columns used:
    _visa_global             : str|None — from workflow_engine
    _days_since_last_activity: int|None — DATA_DATE - last activity
    _days_to_deadline        : int|None — earliest deadline - DATA_DATE
    _focus_priority          : int 1-5  — urgency tier
    _focus_owner             : list     — canonical names of owners (Rules 1-6)
    _focus_owner_tier        : str      — PRIMARY/SECONDARY/MOEX/CONTRACTOR/CLOSED
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
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
    focused_df: Optional[pd.DataFrame] = None
    stale_doc_ids: set = field(default_factory=set)
    resolved_doc_ids: set = field(default_factory=set)
    blocked_upstream_ids: set = field(default_factory=set)
    priority_queue: list = field(default_factory=list)
    per_actor_queues: dict = field(default_factory=dict)
    stats: dict = field(default_factory=dict)


def apply_focus_filter(ctx: RunContext, config: FocusConfig) -> FocusResult:
    """Main entry point. Returns FocusResult with filtered document sets.

    When focus is OFF: focused_doc_ids = all dernier docs (unchanged behavior).
    When focus is ON: uses pre-computed columns for instant filtering.
    """
    result = FocusResult()

    if not config.enabled:
        if ctx.dernier_df is not None:
            result.focused_doc_ids = set(ctx.dernier_df["doc_id"].tolist())
        result.stats = {"focus_enabled": False}
        return result

    if ctx.dernier_df is None or ctx.workflow_engine is None:
        result.stats = {"focus_enabled": True, "error": "insufficient data"}
        return result

    dernier = ctx.dernier_df

    # Check that pre-computed columns exist (Patches 3+4)
    required_cols = ["_visa_global", "_days_since_last_activity", "_focus_owner_tier"]
    missing = [c for c in required_cols if c not in dernier.columns]
    if missing:
        logger.error("Focus columns missing from dernier_df: %s. "
                     "Patches 3+4 may not be applied.", missing)
        result.focused_doc_ids = set(dernier["doc_id"].tolist())
        result.stats = {"focus_enabled": True, "error": f"missing columns: {missing}"}
        return result

    all_ids = set(dernier["doc_id"].tolist())

    # ── F2: Resolved docs (VISA GLOBAL is terminal) ─────────────
    resolved_mask = dernier["_visa_global"].isin(TERMINAL_STATUSES)
    resolved_ids = set(dernier.loc[resolved_mask, "doc_id"].tolist())
    result.resolved_doc_ids = resolved_ids

    # ── F4: Stale docs (no activity beyond threshold, open only) ─
    stale_threshold = config.stale_threshold_days
    stale_mask = (
        dernier["_visa_global"].isna() &  # only open docs can be stale
        (
            dernier["_days_since_last_activity"].isna() |
            (dernier["_days_since_last_activity"] > stale_threshold)
        )
    )
    stale_ids = set(dernier.loc[stale_mask, "doc_id"].tolist())
    result.stale_doc_ids = stale_ids

    # ── Focused set = not resolved AND not stale ────────────────
    focused_mask = ~resolved_mask & ~stale_mask
    focused_df = dernier[focused_mask].copy()
    focused_ids = set(focused_df["doc_id"].tolist())
    result.focused_doc_ids = focused_ids
    result.focused_df = focused_df

    # ── Blocked upstream (for MOEX context) ─────────────────────
    blocked_mask = focused_df["_focus_owner_tier"].isin(["PRIMARY", "SECONDARY"])
    result.blocked_upstream_ids = set(focused_df.loc[blocked_mask, "doc_id"].tolist())

    # ── Priority queue from pre-computed columns ────────────────
    # Only include docs that have an owner (not CLOSED)
    actionable = focused_df[focused_df["_focus_owner_tier"] != "CLOSED"]

    pq_records = []
    for _, row in actionable.iterrows():
        owners = row.get("_focus_owner", [])
        tier = row.get("_focus_owner_tier", "")
        # Determine responsible label for priority queue display
        if tier == "CONTRACTOR":
            responsible = "CONTRACTOR"
        elif tier == "MOEX":
            responsible = "MOEX"
        elif isinstance(owners, list) and len(owners) == 1:
            responsible = owners[0]
        elif isinstance(owners, list) and len(owners) > 1:
            responsible = "MULTIPLE_CONSULTANTS"
        else:
            responsible = tier

        dtd = row.get("_days_to_deadline")
        priority = row.get("_focus_priority", 5)

        # Sanitize NaN
        if isinstance(dtd, float) and math.isnan(dtd):
            dtd = None
        if isinstance(priority, float) and math.isnan(priority):
            priority = 5

        dl = row.get("_earliest_deadline")
        dl_str = str(dl) if dl is not None and not (isinstance(dl, float) and math.isnan(dl)) else None

        pq_records.append({
            "doc_id": row["doc_id"],
            "priority": int(priority),
            "delta_days": int(dtd) if dtd is not None else None,
            "date_limite": dl_str,
            "responsible": responsible,
            "owners": owners if isinstance(owners, list) else [],
            "owner_tier": tier,
            "numero": str(row.get("numero_normalized", "?")),
            "indice": str(row.get("indice", "?")),
            "emetteur": str(row.get("emetteur", "?")),
            "type_doc": str(row.get("type_de_doc", "?")),
            "lot": str(row.get("lot_normalized", "?")),
        })

    pq_records.sort(key=lambda x: (
        x["priority"],
        x["delta_days"] if x["delta_days"] is not None else 9999
    ))
    result.priority_queue = pq_records

    # ── Per-actor queues ────────────────────────────────────────
    actor_queues = {}
    for item in pq_records:
        owners = item.get("owners", [])
        for owner in owners:
            if owner not in actor_queues:
                actor_queues[owner] = []
            actor_queues[owner].append(item["doc_id"])
    result.per_actor_queues = actor_queues

    # ── Stats ───────────────────────────────────────────────────
    p_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for item in pq_records:
        p_counts[item["priority"]] = p_counts.get(item["priority"], 0) + 1

    # Tier counts
    tier_counts = focused_df["_focus_owner_tier"].value_counts().to_dict()

    result.stats = {
        "focus_enabled": True,
        "total_dernier": len(all_ids),
        "resolved_excluded": len(resolved_ids),
        "stale_excluded": len(stale_ids),
        "focused_count": len(focused_ids),
        "blocked_upstream_count": len(result.blocked_upstream_ids),
        "stale_threshold_days": stale_threshold,
        "p1_overdue": p_counts[1],
        "p2_urgent": p_counts[2],
        "p3_soon": p_counts[3],
        "p4_ok": p_counts[4],
        "p5_no_deadline": p_counts[5],
        "moex_actionable": tier_counts.get("MOEX", 0),
        "contractor_actionable": tier_counts.get("CONTRACTOR", 0),
        "primary_pending": tier_counts.get("PRIMARY", 0),
        "secondary_pending": tier_counts.get("SECONDARY", 0),
        "excluded_total": len(resolved_ids) + len(stale_ids),
    }

    # ── Per-consultant breakdown for UI FocusByConsultant chart ─────
    by_consultant = []
    for actor_name, doc_ids in actor_queues.items():
        if actor_name in ("CONTRACTOR", "MOEX"):
            continue  # skip non-consultant entries
        actor_p = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for item in pq_records:
            if actor_name in item.get("owners", []):
                actor_p[item["priority"]] += 1
        total = sum(actor_p.values())
        if total > 0:
            by_consultant.append({
                "name": actor_name,
                "slug": actor_name.upper().replace(" ", "_").replace("'", "_"),
                "p1": actor_p[1],
                "p2": actor_p[2],
                "p3": actor_p[3],
                "p4": actor_p[4],
                "total": total,
            })
    by_consultant.sort(key=lambda x: x["total"], reverse=True)
    result.stats["by_consultant"] = by_consultant

    return result
