"""
workflow_engine.py
------------------
For each document (specifically its dernier indice), computes the
latest workflow state per approver.

Logic:
  - NOT_CALLED: no date, no status
  - PENDING_IN_DELAY: date field = 'en attente'
  - PENDING_LATE: date field = 'Rappel en attente'
  - ANSWERED: date field is a real date

Also computes global workflow state:
  - ALL_PRIMARY_DONE
  - SECONDARY_PENDING
  - MOEX_DONE
  - FULLY_COMPLETE
"""

from typing import Optional, List, Dict
import pandas as pd


# Primary approvers (must complete before "done")
PRIMARY_APPROVERS_KEYWORDS = [
    "TERRELL", "EGIS", "BET SPK", "BET ASC", "BET EV",
    "BET FACADES", "ARCHI MOX", "MOEX",
]

MOEX_KEYWORDS = ["MOEX", "GEMO", "OEUVRE"]   # "OEUVRE" matches canonical "Maître d'Oeuvre EXE"


def _is_primary(approver: str) -> bool:
    """Check if an approver is a primary consultant."""
    upper = approver.upper()
    return any(kw in upper for kw in PRIMARY_APPROVERS_KEYWORDS)


def _is_moex(approver: str) -> bool:
    """Check if an approver is MOEX/GEMO."""
    upper = approver.upper()
    return any(kw in upper for kw in MOEX_KEYWORDS)


class WorkflowEngine:

    def __init__(self, responses_df: pd.DataFrame):
        """
        responses_df must have columns:
          doc_id, approver_canonical, date_answered, date_status_type,
          status_clean, is_exception_approver
        """
        self.responses_df = responses_df.copy()
        # Filter out exception approvers
        self.responses_df = self.responses_df[
            ~self.responses_df["is_exception_approver"]
        ]
        # Precompute lookup: {(doc_id, approver_canonical): {date, status, type}}
        # Priority rule: ANSWERED beats PENDING beats NOT_CALLED.
        # Within ANSWERED, keep the most recent by date_answered.
        # This prevents a later NOT_CALLED entry from overwriting an earlier ANSWERED one.
        self._lookup: Dict = {}
        for _, row in self.responses_df.iterrows():
            key = (row["doc_id"], row["approver_canonical"])
            new_entry = {
                "date_answered": row.get("date_answered"),
                "status_clean": row.get("status_clean"),
                "date_status_type": row.get("date_status_type", "NOT_CALLED"),
                "comment": str(row.get("response_comment", "") or "").strip(),
                # Track raw approver name so we can detect SAS-stage responses
                "approver_raw": str(row.get("approver_raw", "") or ""),
            }
            existing = self._lookup.get(key)
            if existing is None:
                self._lookup[key] = new_entry
            else:
                new_type = new_entry["date_status_type"]
                old_type = existing["date_status_type"]
                _priority = {"ANSWERED": 2, "PENDING_LATE": 1, "PENDING_IN_DELAY": 1, "NOT_CALLED": 0}
                new_p = _priority.get(new_type, 0)
                old_p = _priority.get(old_type, 0)
                if new_p > old_p:
                    # New entry is strictly better state
                    self._lookup[key] = new_entry
                elif new_p == old_p == 2:
                    # Both ANSWERED — keep the more recent one
                    new_date = new_entry.get("date_answered")
                    old_date = existing.get("date_answered")
                    if new_date is not None and (old_date is None or new_date > old_date):
                        self._lookup[key] = new_entry
                # else: keep existing (old is equal or better state)
        # Precompute doc_id → list of {approver, date_answered, status_clean, date_status_type}
        self._doc_approvers: Dict[str, list] = {}
        for key, val in self._lookup.items():
            doc_id, approver = key
            if doc_id not in self._doc_approvers:
                self._doc_approvers[doc_id] = []
            self._doc_approvers[doc_id].append({"approver": approver, **val})

    def compute_for_docs(self, doc_ids: List[str]) -> pd.DataFrame:
        """
        Compute workflow state for a list of doc_ids.
        Returns a DataFrame with one row per (doc_id, approver_canonical).
        """
        filtered = self.responses_df[self.responses_df["doc_id"].isin(doc_ids)]
        return filtered.copy()

    def compute_global_state(self, doc_id: str) -> Dict[str, bool]:
        """
        Compute global workflow flags for a single document.
        """
        rows = self.responses_df[self.responses_df["doc_id"] == doc_id]

        if rows.empty:
            return {
                "ALL_PRIMARY_DONE": False,
                "MOEX_DONE": False,
                "FULLY_COMPLETE": False,
                "any_pending": False,
            }

        primary_rows = rows[rows["approver_canonical"].apply(_is_primary)]
        moex_rows = rows[rows["approver_canonical"].apply(_is_moex)]

        def is_answered(row_series):
            return (row_series["date_status_type"] == "ANSWERED") and \
                   (row_series["status_clean"] is not None)

        all_primary_done = (
            len(primary_rows) > 0 and
            all(is_answered(r) for _, r in primary_rows.iterrows())
        )

        moex_done = (
            len(moex_rows) > 0 and
            all(is_answered(r) for _, r in moex_rows.iterrows())
        )

        any_pending = any(
            r["date_status_type"] in ("PENDING_IN_DELAY", "PENDING_LATE")
            for _, r in rows.iterrows()
        )

        return {
            "ALL_PRIMARY_DONE": all_primary_done,
            "MOEX_DONE": moex_done,
            "FULLY_COMPLETE": all_primary_done and moex_done,
            "any_pending": any_pending,
        }

    def get_approver_status(self, doc_id: str, approver_canonical: str,
                             gf_name_to_ged: Optional[Dict] = None) -> Dict:
        """
        Get the latest status for a specific approver on a specific document.
        Uses precomputed lookup for O(1) performance.

        If gf_name_to_ged is provided, maps GF display names to GED canonical names first.
        For GED approvers that map to multiple (e.g. BET EGIS → BET CVC + BET PLB),
        returns the first match found.
        """
        # Try direct lookup
        result = self._lookup.get((doc_id, approver_canonical))
        if result:
            return result

        # Try via GF→GED mapping
        if gf_name_to_ged:
            ged_names = gf_name_to_ged.get(approver_canonical)
            if ged_names:
                if isinstance(ged_names, str):
                    ged_names = [ged_names]
                for ged_name in ged_names:
                    result = self._lookup.get((doc_id, ged_name))
                    if result:
                        return result

        return {
            "date_answered": None,
            "status_clean": None,
            "date_status_type": "NOT_CALLED",
            "comment": "",
        }

    def get_all_approver_statuses(self, doc_id: str) -> pd.DataFrame:
        """
        Get all approver statuses for one document.
        Returns a DataFrame with columns:
            approver_canonical, date_answered, status_clean, date_status_type

        Reads from self._doc_approvers (the pre-resolved per-approver cache)
        so each approver appears exactly once with its winning state.
        The DataFrame is NOT indexed by approver_canonical; the column is a
        regular column.
        Returns an empty DataFrame with the correct columns if doc_id is not found.
        """
        COLUMNS = ["approver_canonical", "date_answered", "status_clean", "date_status_type"]

        cached_rows = self._doc_approvers.get(doc_id)
        if not cached_rows:
            return pd.DataFrame(columns=COLUMNS)

        records = [
            {
                "approver_canonical": row["approver"],   # internal key is "approver"
                "date_answered":      row.get("date_answered"),
                "status_clean":       row.get("status_clean"),
                "date_status_type":   row.get("date_status_type", "NOT_CALLED"),
            }
            for row in cached_rows
        ]
        return pd.DataFrame(records, columns=COLUMNS)

    def compute_visa_global(self, doc_id: str) -> Optional[str]:
        """
        PATCH 3: VISA GLOBAL = MOEX visa only.
        NOT aggregated from other approvers.

        SAS REF handling:
          - If MOEX refusal came from the 0-SAS workflow track (first-pass stage)
            → return "SAS REF"  (this ends the workflow at SAS stage)
          - If MOEX refusal came from the full workflow track
            → return "REF"
        All other statuses (VSO, VSO-SAS, VAO, HM, SUS) are returned directly.
        """
        status, _ = self.compute_visa_global_with_date(doc_id)
        return status

    def compute_visa_global_with_date(self, doc_id: str):
        """
        Returns (visa_global_status, visa_global_date) derived from the SAME
        winning MOEX entry, guaranteeing semantic consistency:

          Date réel de visa is non-null ↔ VISA GLOBAL is non-null.

        Return values:
          (None, None)                — no final MOEX visa yet (incl. SAS-only)
          ("SAS REF", date)           — SAS-stage refusal, date = SAS refusal date
          ("VAO"|"VSO"|"REF"|"HM"|…, date) — final MOEX visa and its date

        Business rules:
          • VAO-SAS / VSO-SAS → (None, None)  [SAS approval, no final visa yet]
          • 0-SAS REF         → ("SAS REF", date)
          • full-workflow REF → ("REF", date)
          • all other ANSWERED MOEX statuses → (status, date)
        """
        doc_entries = self._doc_approvers.get(doc_id, [])
        # Find the MOEX entry (Maître d'Oeuvre EXE / GEMO)
        moex_entries = [e for e in doc_entries if _is_moex(e["approver"])]
        if not moex_entries:
            return None, None

        moex = moex_entries[0]
        status = moex.get("status_clean")

        # Only return a status if MOEX has an actual ANSWERED response
        if not status or moex.get("date_status_type") != "ANSWERED":
            return None, None

        date = moex.get("date_answered")

        # SAS REF distinction: check whether the winning MOEX entry
        # came from the 0-SAS approver track (SAS first-pass) vs full workflow.
        if status == "REF":
            source_raw = moex.get("approver_raw", "")
            if source_raw == "0-SAS":
                return "SAS REF", date
            return "REF", date

        # SAS-stage non-refusal statuses (VSO-SAS, VAO-SAS) must NOT appear in
        # VISA GLOBAL or Date réel de visa.  They indicate the SAS first-pass
        # approved the doc for full review, but the final MOEX visa has not been
        # issued yet → both columns must remain empty.
        if status.endswith("-SAS"):
            return None, None

        return status, date


def compute_responsible_party(engine: WorkflowEngine, doc_ids: list) -> dict:
    """
    Determine the responsible party for each document based solely on
    WorkflowEngine computed outputs — no raw GED columns are touched here.

    Returns:
        { doc_id: responsible_party }

    Possible responsible_party values:
        "CONTRACTOR"           — REF or SAS REF (bad submission / final refusal)
        "<approver_canonical>" — single consultant with a pending response
        "MULTIPLE_CONSULTANTS" — more than one consultant is pending
        "MOEX"                 — all consultants answered but MOEX hasn't issued visa yet
        None                   — document is closed (visa issued, not a REF)
    """
    result = {}

    for doc_id in doc_ids:

        # ── Step 1: Retrieve the computed visa global status ──────────────────
        # compute_visa_global_with_date is the single source of truth for visa.
        # We only need the status string, not the date.
        visa, _ = engine.compute_visa_global_with_date(doc_id)

        # ── Rule 1: Final REF → Contractor is responsible ────────────────────
        # MOEX issued a full-workflow refusal; the contractor must resubmit.
        if visa == "REF":
            # No dedicated contractor field is exposed by WorkflowEngine,
            # so we fall back to the generic sentinel "CONTRACTOR".
            result[doc_id] = "CONTRACTOR"
            continue

        # ── Rule 2: SAS REF → Contractor is responsible ──────────────────────
        # The SAS first-pass was refused, meaning the submission itself was bad.
        # Counted against the contractor, not against any consultant.
        if visa == "SAS REF":
            result[doc_id] = "CONTRACTOR"
            continue

        # ── Step 2: Inspect per-approver statuses to find pending consultants ─
        # get_all_approver_statuses returns a DataFrame with columns:
        #   approver_canonical, date_answered, status_clean, date_status_type
        approvers_df = engine.get_all_approver_statuses(doc_id)

        pending = []  # will hold canonical names of consultants who are late/pending

        if not approvers_df.empty:
            for _, row in approvers_df.iterrows():
                approver = row["approver_canonical"]
                status_type = row["date_status_type"]

                # Exclude MOEX/GEMO — they are handled separately in Rule 4.
                if _is_moex(approver):
                    continue

                # Exclude approvers that have never been called yet (NOT_CALLED
                # means the document hasn't reached this approver's stage).
                if status_type == "NOT_CALLED":
                    continue

                # A consultant is "pending" if they are overdue or in delay.
                if status_type in ("PENDING_IN_DELAY", "PENDING_LATE"):
                    pending.append(approver)

        # ── Rule 3: One or more consultants are pending ───────────────────────
        if len(pending) == 1:
            # Exactly one consultant is blocking the document.
            result[doc_id] = pending[0]
            continue

        if len(pending) > 1:
            # Multiple consultants are blocking simultaneously.
            result[doc_id] = "MULTIPLE_CONSULTANTS"
            continue

        # ── Rule 4: No pending consultants and no visa → MOEX must act ───────
        # All called consultants have answered but MOEX hasn't issued its
        # visa chapeau yet — MOEX is the responsible party.
        if visa is None:
            result[doc_id] = "MOEX"
            continue

        # ── Rule 5: No pending, visa exists and it isn't a REF → Closed ──────
        # REF was already handled in Rule 1, so any non-None visa here means
        # the document is fully approved (VSO, VAO, etc.) — no one is responsible.
        result[doc_id] = None

    return result
