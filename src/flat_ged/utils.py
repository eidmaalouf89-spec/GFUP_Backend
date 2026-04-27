"""
utils.py — Pure parsing and computation helpers.

All functions here are stateless and free of side effects.
Business rules are preserved exactly from prototype_v4.py.
"""

import re
import datetime

from config import (
    VALID_STATUS_CODES,
    MOEX_CANONICAL,
    SAS_CANONICAL,
    PENDING_KEYWORDS,
    DEADLINE_DATE_PATTERN,
)

_DEADLINE_RE = re.compile(DEADLINE_DATE_PATTERN)


# ── Status parsing ────────────────────────────────────────────────────────────

def parse_status(raw) -> tuple[str | None, str | None]:
    """Return (status_code, status_scope) from a raw GED status string.

    Steps:
      A — normalise: str → strip → upper → remove leading dots
      B — split on '-': first token = candidate code, rest = suffixes
      C — validate code against VALID_STATUS_CODES; else "UNKNOWN"
      D — scope: any suffix containing 'SAS' → "SAS", else "STANDARD"

    Returns (None, None) for empty / null input.
    """
    if raw is None:
        return None, None
    s = str(raw).strip()
    if s.lower() in ("", "none", "nan"):
        return None, None
    s = s.upper().lstrip(".")
    if not s:
        return None, None
    parts     = s.split("-")
    candidate = parts[0].strip()
    suffixes  = parts[1:]
    status_code  = candidate if candidate in VALID_STATUS_CODES else "UNKNOWN"
    status_scope = "SAS" if any("SAS" in tok for tok in suffixes) else "STANDARD"
    return status_code, status_scope


# ── Date / deadline parsing ───────────────────────────────────────────────────

def extract_deadline(text) -> datetime.date | None:
    """Extract (YYYY/MM/DD) deadline embedded in pending-state text."""
    m = _DEADLINE_RE.search(str(text))
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def interpret_date(raw) -> tuple[str, datetime.date | None, str | None, datetime.date | None]:
    """Return (date_status_type, response_date, deadline_raw_text, deadline_date).

    date_status_type values:
      NOT_CALLED       — field is empty / None
      ANSWERED         — field contains a real date/datetime
      PENDING_IN_DELAY — text says request was sent, within deadline
      PENDING_LATE     — text starts with "rappel" (reminder sent, past deadline)
    """
    if raw is None:
        return "NOT_CALLED", None, None, None
    if isinstance(raw, (datetime.datetime, datetime.date)):
        rd = raw.date() if isinstance(raw, datetime.datetime) else raw
        return "ANSWERED", rd, None, None
    if isinstance(raw, str):
        s  = raw.strip().lower()
        dl = extract_deadline(raw)
        dl_raw = raw.strip() if dl else None
        if s.startswith("rappel"):
            return "PENDING_LATE", None, dl_raw, dl
        if "en attente" in s:
            return "PENDING_IN_DELAY", None, dl_raw, dl
        # Fallback: any other text → treat as pending
        return "PENDING_IN_DELAY", None, dl_raw, dl
    return "NOT_CALLED", None, None, None


# ── Actor classification ──────────────────────────────────────────────────────

def actor_type_for(canonical: str) -> str:
    if canonical == SAS_CANONICAL:    return "SAS"
    if canonical == MOEX_CANONICAL:   return "MOEX"
    return "CONSULTANT"


# ── Status family ─────────────────────────────────────────────────────────────

def calc_status_family(date_status: str, status_code: str | None) -> str:
    """Map (date_status, status_code) → status_family.

    status_code must be the extracted semantic code (e.g. "VSO"),
    not the full raw GED string (e.g. "VSO-SAS").
    """
    if date_status in ("PENDING_IN_DELAY", "PENDING_LATE"):
        return "PENDING"
    sc = (status_code or "").upper()
    if sc in ("VSO", "FAV"):          return "APPROVED"
    if sc in ("VAO", "SUS", "DEF"):   return "APPROVED_WITH_REMARKS"
    if sc == "REF":                   return "REFUSED"
    if sc == "HM":                    return "OUT_OF_SCOPE"
    if date_status == "ANSWERED":     return "OTHER"
    return "OTHER"


# ── Retard / avance ───────────────────────────────────────────────────────────

def calc_retard_avance(
    phase_deadline: datetime.date | None,
    response_date:  datetime.date | None,
    date_status:    str,
    data_date:      datetime.date,
) -> tuple[int | None, str | None]:
    """Compute days relative to phase_deadline and classify as RETARD/ON_TIME/AVANCE.

    For closed steps: uses response_date.
    For open steps:   uses data_date as effective date.
    Returns (None, None) if phase_deadline is absent or step is not active.
    """
    if phase_deadline is None:
        return None, None
    if date_status == "ANSWERED" and response_date is not None:
        delta = (phase_deadline - response_date).days
    elif date_status in ("PENDING_IN_DELAY", "PENDING_LATE"):
        delta = (phase_deadline - data_date).days
    else:
        return None, None
    status = "RETARD" if delta < 0 else ("ON_TIME" if delta == 0 else "AVANCE")
    return delta, status
