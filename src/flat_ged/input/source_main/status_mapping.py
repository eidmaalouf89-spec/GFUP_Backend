"""
status_mapping.py
-----------------
Extracted from: src/normalize.py (clean_status, interpret_date_field, PENDING_KEYWORDS)

Purpose: Normalize raw GED status strings and "Date réponse" text into clean values.

Use ONLY for: stripping dots from status values, detecting pending state from date text,
              handling empty/null edge cases.
DO NOT add: workflow priority, ownership, escalation, or reporting.
"""

# ── VALID STATUSES ────────────────────────────────────────────────────────────
# Standard approval status vocabulary used by all consultants.
VALID_STATUSES: set[str] = {"VAO", "VSO", "REF", "HM", "SUS"}

# Bureau de Contrôle uses a different vocabulary (FAV/SUS/DEF).
# SUS appears in both — same meaning (suspended/with reservations).
BUREAU_CONTROLE_STATUSES: set[str] = {"FAV", "SUS", "DEF"}


# ── STATUS CLEANING ────────────────────────────────────────────────────────────
# Applied to the "Réponse" sub-column of each approver group.
#
# Rule: strip leading dots → uppercase → treat empty/null as None.
# Examples:  ".VAO" → "VAO"   |   "vso" → "VSO"   |   None → None   |   "" → None
EMPTY_STATUS_VALUES: set[str] = {"", "none", "nan"}


# ── PENDING DETECTION ──────────────────────────────────────────────────────────
# Applied to the "Date réponse" sub-column of each approver group.
# This field contains either a real date/datetime (→ ANSWERED)
# or a French text string describing the pending state.

# Keyword → date_status_type (checked against lowercased text)
PENDING_KEYWORDS: dict[str, str] = {
    "rappel":      "PENDING_LATE",        # reminder sent — starts with "rappel"
    "en attente":  "PENDING_IN_DELAY",    # first request sent, within deadline
}

# All possible date_status_type values
DATE_STATUS_TYPES: dict[str, str] = {
    "NOT_CALLED":       "Approver never solicited (empty date field)",
    "PENDING_IN_DELAY": "Request sent, awaiting response, within deadline",
    "PENDING_LATE":     "Request sent, awaiting response, past deadline",
    "ANSWERED":         "A response date exists — approver replied",
}

# Detection priority order:
#   1. None / empty string       → NOT_CALLED
#   2. datetime / date object    → ANSWERED
#   3. text starts with "rappel" → PENDING_LATE
#   4. text contains "en attente"→ PENDING_IN_DELAY
#   5. any other text            → PENDING_IN_DELAY  (fallback)

# Deadline date is embedded in the text as (YYYY/MM/DD), e.g.:
#   "En attente visa (2025/11/30)"  or  "Rappel : En attente visa (2025/11/30)"
DEADLINE_DATE_PATTERN: str = r'\((\d{4})/(\d{2})/(\d{2})\)'
