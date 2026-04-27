"""
src/domain/normalization.py
---------------------------
Pure normalization and comparison helpers extracted from main.py.

Every function here is a pure helper: no globals, no file writes, no external state mutation.
"""

import re as _re
import datetime as _dt
from typing import Optional as _Optional

import pandas as pd


def normalize_date_for_compare(value) -> str:
    """
    Patch B1: Normalize a date value to YYYY-MM-DD string for comparison.
    Strips time-of-day component — only calendar date matters here.

    Returns '' (empty string) for None/invalid values.

    Examples:
      '2026-03-13 08:23:24' -> '2026-03-13'
      '2026-03-13 00:00:00' -> '2026-03-13'
      datetime(2026, 3, 13)  -> '2026-03-13'
      None / '' / 'N/A'     -> ''
    """
    if value is None:
        return ""
    if isinstance(value, (_dt.datetime, _dt.date)):
        return str(value.date() if isinstance(value, _dt.datetime) else value)
    s = str(value).strip()
    if not s or s.lower() in ("none", "n/a", ""):
        return ""
    try:
        return str(pd.to_datetime(s).date())
    except Exception:
        return ""


def normalize_title_for_compare(value) -> str:
    """
    Part 3 (v2): Normalize a document title for similarity comparison.

    1. Strip GED code-path prefix before ' - '
       'P17_T2_AU_EXE_LGD_GOE_A003_ARM_AZ_R7_228193_A - Armatures Poteaux'
       -> 'Armatures Poteaux'
    2. Lowercase
    3. Remove file extensions (.pdf .docx .xlsx .dwg .txt .pptx .zip)
    4. Normalize separators: underscores/dashes -> space
    5. Collapse whitespace
    6. Strip trailing/leading punctuation
    7. Remove consecutive duplicate tokens
    """
    if value is None:
        return ""
    s = str(value).strip()

    prefix_match = _re.match(r'^[A-Z0-9][A-Z0-9_\-]{10,}\s+-\s+(.+)$', s)
    if prefix_match:
        s = prefix_match.group(1).strip()

    s = s.lower()
    s = _re.sub(r'\.(pdf|docx?|xlsx?|dwg|txt|pptx?|zip)\s*$', '', s, flags=_re.IGNORECASE)
    s = _re.sub(r'[_\-]+', ' ', s)
    s = _re.sub(r'\s+', ' ', s)
    s = s.strip('.,;: ')

    tokens = s.split()
    deduped: list = []
    for t in tokens:
        if not deduped or t != deduped[-1]:
            deduped.append(t)
    return ' '.join(deduped)


def title_similarity(a: str, b: str) -> float:
    """
    Token-based similarity: max(Jaccard, Containment).

    Containment = |A intersection B| / min(|A|, |B|) — gives 1.0 when one set is a
    subset of the other, so a short GED title that is entirely contained
    in a longer GF title (e.g. GF appends building/level info) scores 1.0.

    Thresholds (used in classify_discrepancy):
      >= 0.85 -> suppress (COSMETIC or no discrepancy)
      0.65-0.84 -> COSMETIC
      < 0.65 -> REVIEW_REQUIRED
    """
    na = normalize_title_for_compare(a)
    nb = normalize_title_for_compare(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    ta = set(na.split())
    tb = set(nb.split())
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union_len = len(ta | tb)
    jaccard = inter / union_len if union_len else 0.0
    containment = inter / min(len(ta), len(tb)) if min(len(ta), len(tb)) else 0.0
    return max(jaccard, containment)


def date_diff_days(ged_date, gf_date) -> _Optional[int]:
    """
    Absolute calendar-day difference between two date values.
    Returns None if either is missing or unparseable.
    """
    gd = normalize_date_for_compare(ged_date)
    gf = normalize_date_for_compare(gf_date)
    if not gd or not gf:
        return None
    try:
        d1 = _dt.date.fromisoformat(gd)
        d2 = _dt.date.fromisoformat(gf)
        return abs((d1 - d2).days)
    except Exception:
        return None


def normalize_status_for_compare(value) -> str:
    """
    Patch B3: Normalize a visa/workflow status for comparison.
    Removes leading dots, uppercases, trims spaces.
    """
    if value is None:
        return ""
    s = str(value).strip().lstrip(".").strip().upper()
    return s


def normalize_numero_for_compare(value) -> str:
    """
    Normalize document numero: strip leading zeros and .0 suffix, cast to string.

    Handles:
      int     49202   -> '49202'
      float   49202.0 -> '49202'   (new GF stores as float)
      str    '49202'  -> '49202'
      str    '49202.0'-> '49202'   (via float->int)
    """
    if value is None:
        return ""
    try:
        # float() handles both int-strings and float-strings ('49202', '49202.0')
        return str(int(float(str(value).replace(",", "").strip())))
    except (ValueError, TypeError):
        return str(value).strip()


def normalize_indice_for_compare(value) -> str:
    """Normalize indice: strip whitespace, uppercase."""
    if value is None:
        return ""
    return str(value).strip().upper()
