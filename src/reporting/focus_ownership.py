"""
focus_ownership.py — Focus Mode document ownership resolver

Implements the 6 ownership rules for Focus Mode.
Every open document has exactly one owner tier and a list of
specific owner names. This determines which consultant/contractor
fiche shows the doc in Focus Mode.

Rules:
  1. Primary pending      → pending primary consultants own it
  2. Secondary pending    → pending secondary consultants own it (within 10-day window)
  3. Secondary expired    → MOEX owns it (10-day window passed)
  4. All replied          → MOEX owns it (must issue VISA GLOBAL)
  5. MOEX replied REF     → CONTRACTOR owns it (must resubmit)
  6. MOEX replied terminal→ CLOSED (nobody owns it)

Classification (hardcoded from project P17&CO T2, validated by MOEX):
  PRIMARY:   ARCHITECTE, BET Structure, BET CVC, BET Electricité,
             BET Plomberie, BET Ascenseur, BET EV, BET SPK,
             BET Façade, BET POL, BET VRD
  SECONDARY: Bureau de Contrôle, BET Acoustique, AMO HQE
  MOEX:      Maître d'Oeuvre EXE
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Classification tables ───────────────────────────────────────
# These use CANONICAL names from Mapping.xlsx (via normalize.py).

PRIMARY_CANONICAL = frozenset({
    "ARCHITECTE",
    "BET Structure",
    "BET CVC",
    "BET Electricité",
    "BET Plomberie",
    "BET Ascenseur",
    "BET EV",
    "BET SPK",
    "BET Façade",
    "BET POL",
    "BET VRD",
})

SECONDARY_CANONICAL = frozenset({
    "Bureau de Contrôle",
    "BET Acoustique",
    "AMO HQE",
})

MOEX_CANONICAL = frozenset({
    "Maître d'Oeuvre EXE",
})

TERMINAL_VISA = frozenset({"VSO", "VAO", "SAS REF", "HM"})

SECONDARY_WINDOW_DAYS = 10


def classify_consultant(canonical_name: str) -> str:
    """Returns 'PRIMARY', 'SECONDARY', 'MOEX', or 'UNKNOWN'."""
    if canonical_name in MOEX_CANONICAL:
        return "MOEX"
    if canonical_name in PRIMARY_CANONICAL:
        return "PRIMARY"
    if canonical_name in SECONDARY_CANONICAL:
        return "SECONDARY"
    return "UNKNOWN"


def compute_focus_ownership(dernier_df: pd.DataFrame,
                            workflow_engine,
                            data_date: date) -> None:
    """Add _focus_owner and _focus_owner_tier columns to dernier_df IN PLACE.

    _focus_owner:      list of canonical consultant names that own this doc,
                       OR "MOEX", OR "CONTRACTOR", OR empty list (closed).
    _focus_owner_tier: str — "PRIMARY", "SECONDARY", "MOEX", "CONTRACTOR", "CLOSED"

    Uses the pre-computed _visa_global column (from Patch 3).
    Uses WorkflowEngine._doc_approvers for O(1) per-doc approver lookup.

    Args:
        dernier_df: DataFrame with _visa_global column already set.
        workflow_engine: WorkflowEngine instance with precomputed lookups.
        data_date: DATA_DATE as date object.
    """
    dd = data_date.date() if hasattr(data_date, 'date') else data_date

    owners_list = []
    tiers_list = []

    for _, row in dernier_df.iterrows():
        doc_id = row["doc_id"]
        visa = row.get("_visa_global")

        # ── Rule 6: Terminal VISA → CLOSED ──────────────────────
        if visa is not None and visa in TERMINAL_VISA:
            owners_list.append([])
            tiers_list.append("CLOSED")
            continue

        # ── Rule 5: REF → CONTRACTOR ────────────────────────────
        if visa == "REF":
            owners_list.append(["CONTRACTOR"])
            tiers_list.append("CONTRACTOR")
            continue

        # ── Inspect approver statuses for this doc ──────────────
        approver_entries = workflow_engine._doc_approvers.get(doc_id, [])
        if not approver_entries:
            # No approvers at all — shouldn't happen, but treat as MOEX
            owners_list.append(["MOEX"])
            tiers_list.append("MOEX")
            continue

        # Classify each approver and find pending ones
        pending_primary = []
        pending_secondary = []
        primary_answered_dates = []
        all_primary_answered = True
        moex_has_answered = False

        for entry in approver_entries:
            approver = entry["approver"]  # canonical name
            status_type = entry.get("date_status_type", "NOT_CALLED")
            date_answered = entry.get("date_answered")
            tier = classify_consultant(approver)

            if tier == "MOEX":
                if status_type == "ANSWERED":
                    moex_has_answered = True
                continue  # MOEX is the closer, not a reviewer

            if tier == "UNKNOWN":
                # Exception approvers or unknown — skip
                continue

            if status_type == "NOT_CALLED":
                # Never solicited — not relevant to ownership
                continue

            if tier == "PRIMARY":
                if status_type == "ANSWERED" and date_answered is not None:
                    da = date_answered.date() if hasattr(date_answered, 'date') else date_answered
                    primary_answered_dates.append(da)
                elif status_type in ("PENDING_IN_DELAY", "PENDING_LATE"):
                    pending_primary.append(approver)
                    all_primary_answered = False
                else:
                    # Other status (shouldn't happen) — treat as not answered
                    all_primary_answered = False

            elif tier == "SECONDARY":
                if status_type in ("PENDING_IN_DELAY", "PENDING_LATE"):
                    pending_secondary.append(approver)
                # If ANSWERED, secondary is done — no action needed

        # ── Rule 1: Primary consultants still pending ───────────
        if pending_primary:
            owners_list.append(sorted(pending_primary))
            tiers_list.append("PRIMARY")
            continue

        # At this point all primaries have answered (or were NOT_CALLED).

        # ── Rules 2 & 3: Secondary pending — check 10-day window
        if pending_secondary and primary_answered_dates:
            last_primary_date = max(primary_answered_dates)
            deadline = last_primary_date + timedelta(days=SECONDARY_WINDOW_DAYS)

            if dd <= deadline:
                # Rule 2: Within 10-day window → secondary owns it
                owners_list.append(sorted(pending_secondary))
                tiers_list.append("SECONDARY")
                continue
            else:
                # Rule 3: Past 10-day window → MOEX owns it
                owners_list.append(["MOEX"])
                tiers_list.append("MOEX")
                continue

        # ── Rule 4: Everyone replied, MOEX hasn't issued VISA ───
        # (visa is None at this point — checked at top)
        owners_list.append(["MOEX"])
        tiers_list.append("MOEX")

    dernier_df["_focus_owner"] = owners_list
    dernier_df["_focus_owner_tier"] = tiers_list

    # Log summary
    from collections import Counter
    tier_counts = Counter(tiers_list)
    logger.info(
        "Focus ownership computed: %s",
        ", ".join(f"{k}={v}" for k, v in sorted(tier_counts.items()))
    )
