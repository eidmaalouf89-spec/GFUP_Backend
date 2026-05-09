"""
focus_ownership.py — Focus Mode document ownership resolver

Implements the ownership rules for Focus Mode. Every open document has
exactly one owner tier and a list of specific owner names. This determines
which consultant/contractor fiche shows the doc in Focus Mode.

Business rules (project owner, 2026-05-09):

  A. Global workflow duration: 30 days. There is no valid "no deadline"
     concept for open submittals (P5 has been removed).
  B. SAS REF is NOT terminal. SAS REF means contractor must resubmit
     a corrected indice. Routes to CONTRACTOR.
  C. SAS pending (SAS gate row pending) belongs to "MOEX SAS / GEMO SAS",
     a distinct consultant from "Maître d'Œuvre EXE". Owner = ["MOEX SAS"],
     tier = "MOEX" (consultant fiche routing handles the SAS variant).
  D. No-MOEX-called workflow:
       - primary pending → PRIMARY
       - secondary pending, within 10d of last primary → SECONDARY
       - secondary expired (>10d), no MOEX called → close with worst primary
       - secondary replied → close with worst across primary+secondary
       - worst ∈ {REF, DEF, SAS REF} → CONTRACTOR
       - worst ∈ {VAO, VSO, FAV, SUS, HM} → CLOSED
  E. MOEX chapeau (normal Maître d'Œuvre EXE) only owns when MOEX is
     actually called/required (i.e., MOEX appears in the approver list).
     Do NOT default to MOEX merely because all visible consultants answered.

Status equivalence:
  SUS ≡ VAO (favorable, no new cycle by itself)
  FAV ≡ VSO (favorable)
  DEF ≡ REF (negative, requires resubmission)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Classification tables ───────────────────────────────────────
# Use CANONICAL names from Mapping.xlsx (via normalize.py).

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

# ── Status equivalence (per project owner) ─────────────────────
# Negative = requires contractor corrected indice.
NEGATIVE_STATUSES = frozenset({"REF", "DEF", "SAS REF"})
# Favorable terminal — close the submittal.
FAVORABLE_STATUSES = frozenset({"VAO", "VSO", "FAV", "SUS", "HM"})

# ── Visa-level routing ─────────────────────────────────────────
# SAS REF is NOT terminal — it routes to CONTRACTOR (rule B).
# SUS/FAV are not produced as visa_global today, but listed for safety.
TERMINAL_VISA = frozenset({"VSO", "VAO", "HM", "FAV", "SUS"})
CONTRACTOR_VISA = frozenset({"REF", "DEF", "SAS REF"})

SECONDARY_WINDOW_DAYS = 10

# Canonical name for the SAS variant of MOEX (distinct fiche, see
# src/reporting/consultant_fiche.py — CONSULTANT_DISPLAY_NAMES).
MOEX_SAS_NAME = "MOEX SAS"


def classify_consultant(canonical_name: str) -> str:
    """Returns 'PRIMARY', 'SECONDARY', 'MOEX', or 'UNKNOWN'."""
    if canonical_name in MOEX_CANONICAL:
        return "MOEX"
    if canonical_name in PRIMARY_CANONICAL:
        return "PRIMARY"
    if canonical_name in SECONDARY_CANONICAL:
        return "SECONDARY"
    return "UNKNOWN"


def _derive_closure_owner(answered_statuses) -> tuple:
    """Given the iterable of status_clean values from primaries (+ replied
    secondaries when applicable), return (owner_list, tier).

    Per business rule D5/D6:
      worst ∈ NEGATIVE_STATUSES → CONTRACTOR
      worst ∈ FAVORABLE_STATUSES → CLOSED
      ambiguous / no answers     → CLOSED (defensive — unreachable in
                                    well-formed data; logged at call site)
    """
    has_negative = False
    has_favorable = False
    for s in answered_statuses:
        if s is None:
            continue
        s = str(s).strip()
        if s in NEGATIVE_STATUSES:
            has_negative = True
        elif s in FAVORABLE_STATUSES:
            has_favorable = True
    if has_negative:
        return (["CONTRACTOR"], "CONTRACTOR")
    if has_favorable:
        return ([], "CLOSED")
    return ([], "CLOSED")


def _build_sas_pending_lookup(responses_df) -> set:
    """Doc_ids that have a SAS gate row currently pending (PENDING_IN_DELAY
    or PENDING_LATE). Used to route otherwise-unowned docs to MOEX SAS
    rather than normal Maître d'Œuvre EXE."""
    if responses_df is None or len(responses_df) == 0:
        return set()
    if "approver_raw" not in responses_df.columns:
        return set()
    sas_mask = responses_df["approver_raw"] == "0-SAS"
    if "date_status_type" in responses_df.columns:
        pend_mask = responses_df["date_status_type"].isin(
            ("PENDING_IN_DELAY", "PENDING_LATE")
        )
        sas_mask = sas_mask & pend_mask
    return set(responses_df.loc[sas_mask, "doc_id"].astype(str).unique().tolist())


def compute_focus_ownership(dernier_df: pd.DataFrame,
                            workflow_engine,
                            data_date: date,
                            responses_df: Optional[pd.DataFrame] = None) -> None:
    """Add _focus_owner and _focus_owner_tier columns to dernier_df IN PLACE.

    _focus_owner:      list of canonical consultant names that own this doc,
                       OR ["MOEX"], ["MOEX SAS"], ["CONTRACTOR"], OR empty
                       list (closed).
    _focus_owner_tier: str — "PRIMARY", "SECONDARY", "MOEX", "CONTRACTOR",
                       "CLOSED". (MOEX SAS shares the "MOEX" tier — the
                       owner name distinguishes the fiche.)

    Uses the pre-computed _visa_global column (data_loader, prefers
    flat_doc_meta). Uses WorkflowEngine._doc_approvers for O(1) per-doc
    approver lookup.

    Args:
        dernier_df: DataFrame with _visa_global column already set.
        workflow_engine: WorkflowEngine instance with precomputed lookups.
        data_date: DATA_DATE as date object.
        responses_df: Optional. If provided, used to detect SAS-pending
                      docs (workflow_engine strips SAS rows).
    """
    dd = data_date.date() if hasattr(data_date, 'date') else data_date

    sas_pending_ids = _build_sas_pending_lookup(responses_df)

    owners_list = []
    tiers_list = []

    for _, row in dernier_df.iterrows():
        doc_id = row["doc_id"]
        visa = row.get("_visa_global")
        if visa is not None:
            visa = str(visa).strip()
            if visa == "":
                visa = None

        # ── Rule (B): SAS REF / REF / DEF → CONTRACTOR (resubmission) ──
        if visa is not None and visa in CONTRACTOR_VISA:
            owners_list.append(["CONTRACTOR"])
            tiers_list.append("CONTRACTOR")
            continue

        # ── Rule 6: Favorable terminal visa → CLOSED ───────────────
        if visa is not None and visa in TERMINAL_VISA:
            owners_list.append([])
            tiers_list.append("CLOSED")
            continue

        # ── Inspect approver statuses for this doc ────────────────
        approver_entries = workflow_engine._doc_approvers.get(doc_id, [])

        # MOEX-called detection (rule E): MOEX must actually appear
        # as an approver. If not, "all replied" must NOT default to MOEX.
        moex_called = any(
            classify_consultant(e.get("approver", "")) == "MOEX"
            for e in approver_entries
        )

        if not approver_entries:
            # No approvers and no visa — fallback to MOEX SAS if there is
            # a SAS pending row, otherwise treat as MOEX (genuine chapeau)
            if str(doc_id) in sas_pending_ids:
                owners_list.append([MOEX_SAS_NAME])
                tiers_list.append("MOEX")
            else:
                owners_list.append(["MOEX"])
                tiers_list.append("MOEX")
            continue

        # Classify approvers and collect statuses
        pending_primary = []
        pending_secondary = []
        primary_answered_dates = []
        secondary_answered = False
        primary_statuses = []
        secondary_statuses = []

        for entry in approver_entries:
            approver = entry["approver"]  # canonical name
            status_type = entry.get("date_status_type", "NOT_CALLED")
            date_answered = entry.get("date_answered")
            status_clean = entry.get("status_clean")
            tier = classify_consultant(approver)

            if tier == "MOEX":
                # MOEX is the closer/chapeau, not a reviewer used for
                # closure derivation. Skip in this loop.
                continue

            if tier == "UNKNOWN":
                # Exception approvers / unknown — skip.
                continue

            if status_type == "NOT_CALLED":
                continue

            if tier == "PRIMARY":
                if status_type == "ANSWERED" and date_answered is not None:
                    da = date_answered.date() if hasattr(date_answered, 'date') else date_answered
                    primary_answered_dates.append(da)
                    primary_statuses.append(status_clean)
                elif status_type in ("PENDING_IN_DELAY", "PENDING_LATE"):
                    pending_primary.append(approver)
                # other status types: ignore

            elif tier == "SECONDARY":
                if status_type == "ANSWERED":
                    secondary_answered = True
                    secondary_statuses.append(status_clean)
                elif status_type in ("PENDING_IN_DELAY", "PENDING_LATE"):
                    pending_secondary.append(approver)

        # ── Rule 1: Primary consultants still pending ────────────
        if pending_primary:
            owners_list.append(sorted(pending_primary))
            tiers_list.append("PRIMARY")
            continue

        # All primaries answered (or were NOT_CALLED).

        # ── Rules 2 & 3: Secondary pending — check 10-day window ─
        if pending_secondary and primary_answered_dates:
            last_primary_date = max(primary_answered_dates)
            deadline = last_primary_date + timedelta(days=SECONDARY_WINDOW_DAYS)

            if dd <= deadline:
                # Rule 2: within window → secondary owns it
                owners_list.append(sorted(pending_secondary))
                tiers_list.append("SECONDARY")
                continue
            else:
                # Rule 3: past 10-day window
                if moex_called:
                    # MOEX is the closer when MOEX is actually called.
                    owners_list.append(["MOEX"])
                    tiers_list.append("MOEX")
                    continue
                else:
                    # No-MOEX-called: close with worst PRIMARY response
                    # (secondaries forfeited their window).
                    owner, tier = _derive_closure_owner(primary_statuses)
                    owners_list.append(owner)
                    tiers_list.append(tier)
                    continue

        # ── Rule 4: Everyone (primary, possibly secondary) replied ──
        # MOEX has not yet issued visa_global (visa was None at top).
        if moex_called:
            # SAS-pending check: if SAS gate is still pending, route to
            # MOEX SAS instead of normal Maître d'Œuvre EXE.
            if str(doc_id) in sas_pending_ids:
                owners_list.append([MOEX_SAS_NAME])
                tiers_list.append("MOEX")
            else:
                owners_list.append(["MOEX"])
                tiers_list.append("MOEX")
        else:
            # No MOEX called → derive closure from worst primary +
            # any secondary that replied.
            statuses = list(primary_statuses)
            if secondary_answered:
                statuses.extend(secondary_statuses)
            owner, tier = _derive_closure_owner(statuses)
            # Preserve SAS-pending nuance when worst is favorable but
            # SAS gate hasn't cleared — route to MOEX SAS.
            if tier == "CLOSED" and str(doc_id) in sas_pending_ids:
                owners_list.append([MOEX_SAS_NAME])
                tiers_list.append("MOEX")
            else:
                owners_list.append(owner)
                tiers_list.append(tier)

    dernier_df["_focus_owner"] = owners_list
    dernier_df["_focus_owner_tier"] = tiers_list

    # Log summary
    from collections import Counter
    tier_counts = Counter(tiers_list)
    logger.info(
        "Focus ownership computed: %s",
        ", ".join(f"{k}={v}" for k, v in sorted(tier_counts.items()))
    )
