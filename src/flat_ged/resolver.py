"""
resolver.py — Candidate resolution engine.

Given all GED rows and a target (NUMERO, INDICE), collects every matching
row, scores each one by progression evidence, and selects the most advanced
submission as the ACTIVE instance.

All logic is preserved exactly from prototype_v4.py.
"""

import datetime

from config import RAW_TO_CANONICAL, MOEX_CANONICAL, SAS_CANONICAL
from utils  import interpret_date


class GEDDocumentSkip(Exception):
    """Raised when a document should be excluded from GED_FLAT (e.g. no NUMERO)."""


def resolve_from_group(
    grupo:           list[tuple[int, list]],
    base_cols:       dict,
    approver_groups: list,
    numero,
    indice:          str,
) -> tuple[dict, list[dict]]:
    """Resolve candidates from pre-grouped rows — no full worksheet scan.

    This is the fast-path equivalent of resolve_document() for batch mode.
    Instead of scanning all_rows per-document (O(N) per doc → O(N²) total),
    the caller groups rows once in a single pass, then calls this function
    per group (O(1) per doc → O(N) total).

    grupo: list of (ged_row_index, row_data) for rows that match (numero, indice).
    All resolution logic (scoring, classification) is identical to resolve_document().
    """
    doc_code = f"{numero}|{indice}"
    candidates = []

    for ridx, row_data in grupo:
        base_data = {field: row_data[idx]
                     for idx, field in base_cols.items()
                     if idx < len(row_data)}
        crl      = base_data.get("Créé le")
        sub_date = crl.date() if isinstance(crl, datetime.datetime) else crl
        score, reasons = score_candidate(row_data, approver_groups)

        candidates.append({
            "ged_row_index":              ridx,
            "row_data":                   row_data,
            "doc_code":                   doc_code,
            "submittal_date":             sub_date,
            "lot":                        base_data.get("LOT"),
            "emetteur":                   base_data.get("EMETTEUR"),
            "titre":                      base_data.get("Libellé du document"),
            "progression_score":          score,
            "score_reasons":              reasons,
            "submission_instance_id":     f"{numero}|{indice}|ROW{ridx}",
            "instance_role":              None,
            "instance_resolution_reason": None,
        })

    classify_candidates(candidates)
    selected = next(c for c in candidates if c["instance_role"] == "ACTIVE")
    return selected, candidates


class GEDCandidateNotFound(Exception):
    """Raised when (NUMERO, INDICE) is not found in the GED data."""


def score_candidate(row_data: list, approver_groups: list) -> tuple[int, list[str]]:
    """Additive progression scoring for a single GED candidate row.

    Points:
      MOEX answered       → +100
      Consultant answered → +50  (per consultant)
      SAS answered        → +20
      SAS pending         → +10
      No scored responses →   0

    Returns (score, reasons_list).
    """
    score   = 0
    reasons = []
    for ag in approver_groups:
        if ag["col_date"] >= len(row_data):
            continue
        date_raw  = row_data[ag["col_date"]]
        canonical = RAW_TO_CANONICAL.get(ag["name"], "UNKNOWN")
        if canonical in ("Exception List", "UNKNOWN"):
            continue
        ds, _, _, _ = interpret_date(date_raw)
        if ds == "ANSWERED":
            if canonical == MOEX_CANONICAL:
                score += 100; reasons.append("MOEX_ANSWERED(+100)")
            elif canonical == SAS_CANONICAL:
                score += 20;  reasons.append("SAS_ANSWERED(+20)")
            else:
                score += 50;  reasons.append("CONSULTANT_ANSWERED(+50)")
        elif ds in ("PENDING_IN_DELAY", "PENDING_LATE"):
            if canonical == SAS_CANONICAL:
                score += 10; reasons.append("SAS_PENDING(+10)")
    return score, reasons


def collect_candidates(
    all_rows:        list,
    base_cols:       dict,
    approver_groups: list,
    numero,
    indice:          str,
) -> list[dict]:
    """Collect ALL GED rows matching (NUMERO, INDICE).

    Rule: do NOT stop at first match — collect every row.
    Returns a list of candidate dicts with scoring information.
    """
    doc_code   = f"{numero}|{indice}"
    col_by_name = {v: k for k, v in base_cols.items()}
    numero_col  = col_by_name.get("NUMERO")
    indice_col  = col_by_name.get("INDICE")
    cree_le_col = col_by_name.get("Créé le")

    if numero_col is None or indice_col is None:
        raise GEDCandidateNotFound(f"[FAIL] NUMERO or INDICE column not found in header.")

    candidates = []
    # Data starts at row 3 (index 2 in all_rows), 1-indexed GED row = ridx
    for ridx, row in enumerate(all_rows[2:], start=3):
        if len(row) <= max(numero_col, indice_col):
            continue
        if row[numero_col] != numero:
            continue
        if str(row[indice_col]).strip() != str(indice).strip():
            continue

        row_data = list(row)
        base_data = {field: row_data[idx] for idx, field in base_cols.items()}
        crl      = base_data.get("Créé le")
        sub_date = crl.date() if isinstance(crl, datetime.datetime) else crl
        score, reasons = score_candidate(row_data, approver_groups)

        candidates.append({
            "ged_row_index":              ridx,
            "row_data":                   row_data,
            "doc_code":                   doc_code,
            "submittal_date":             sub_date,
            "lot":                        base_data.get("LOT"),
            "emetteur":                   base_data.get("EMETTEUR"),
            "titre":                      base_data.get("Libellé du document"),
            "progression_score":          score,
            "score_reasons":              reasons,
            "submission_instance_id":     f"{numero}|{indice}|ROW{ridx}",
            "instance_role":              None,
            "instance_resolution_reason": None,
        })

    return candidates


def classify_candidates(candidates: list[dict]) -> None:
    """Assign instance_role and instance_resolution_reason to each candidate (in-place).

    Rules:
      1 candidate  → ACTIVE / SOLE_CANDIDATE
      N same dates → pick highest score; tie-break by earliest row index
      N mixed dates → winner = ACTIVE, others = SEPARATE_INSTANCE or INACTIVE_DUPLICATE
    """
    if not candidates:
        return

    if len(candidates) == 1:
        candidates[0]["instance_role"]              = "ACTIVE"
        candidates[0]["instance_resolution_reason"] = "SOLE_CANDIDATE"
        return

    all_dates = {c["submittal_date"] for c in candidates}
    sorted_cands = sorted(candidates,
                          key=lambda c: (-c["progression_score"], c["ged_row_index"]))
    winner = sorted_cands[0]

    if len(all_dates) == 1:
        # All rows have the same submittal date → duplicates
        if (len(sorted_cands) > 1
                and sorted_cands[0]["progression_score"] == sorted_cands[1]["progression_score"]):
            winner["instance_resolution_reason"] = \
                "ACTIVE_DUPLICATE_SELECTED_TIE_BREAK_EARLIEST_ROW"
        else:
            winner["instance_resolution_reason"] = "ACTIVE_DUPLICATE_SELECTED"
        winner["instance_role"] = "ACTIVE"
        for c in sorted_cands[1:]:
            c["instance_role"]              = "INACTIVE_DUPLICATE"
            c["instance_resolution_reason"] = "ACTIVE_DUPLICATE_SELECTED"
    else:
        # Mixed submittal dates → real separate submissions possible
        winner["instance_role"]              = "ACTIVE"
        winner["instance_resolution_reason"] = "ACTIVE_DUPLICATE_SELECTED"
        for c in sorted_cands[1:]:
            if c["submittal_date"] != winner["submittal_date"]:
                c["instance_role"]              = "SEPARATE_INSTANCE"
                c["instance_resolution_reason"] = "SEPARATE_REAL_SUBMISSION"
            else:
                c["instance_role"]              = "INACTIVE_DUPLICATE"
                c["instance_resolution_reason"] = "ACTIVE_DUPLICATE_SELECTED"

    # INCOMPLETE_BUT_TRACKED: winner has no progression evidence at all
    if winner["progression_score"] == 0:
        winner["instance_resolution_reason"] = "INCOMPLETE_BUT_TRACKED"


def resolve_document(
    all_rows:        list,
    base_cols:       dict,
    approver_groups: list,
    numero,
    indice:          str,
) -> tuple[dict, list[dict]]:
    """Full resolution for a (NUMERO, INDICE) pair.

    Returns (selected_candidate, all_candidates).
    Raises GEDCandidateNotFound if no matching rows exist.
    """
    candidates = collect_candidates(all_rows, base_cols, approver_groups, numero, indice)
    if not candidates:
        raise GEDCandidateNotFound(
            f"[FAIL] doc_code={numero}|{indice} not found in GED data."
        )
    classify_candidates(candidates)
    selected = next(c for c in candidates if c["instance_role"] == "ACTIVE")
    return selected, candidates


def print_resolution_report(candidates: list[dict]) -> None:
    """Print the candidate resolution engine report (single-mode verbose output)."""
    doc_code = candidates[0]["doc_code"] if candidates else "?"
    print(f"\n── Candidate Resolution Engine ───────────────────────────")
    print(f"  doc_code:   {doc_code}")
    print(f"  candidates: {len(candidates)}")
    for c in sorted(candidates, key=lambda x: x["ged_row_index"]):
        reasons_str = (", ".join(c["score_reasons"])
                       if c["score_reasons"] else "no scored responses")
        sel_tag     = "  ◀ SELECTED" if c["instance_role"] == "ACTIVE" else ""
        print(f"\n  GED row:      {c['ged_row_index']}")
        print(f"  doc_code:     {c['doc_code']}")
        print(f"  instance_id:  {c['submission_instance_id']}")
        print(f"  submittal:    {c['submittal_date']}")
        print(f"  score:        {c['progression_score']}  ({reasons_str})")
        print(f"  role:         {c['instance_role']}")
        print(f"  reason:       {c['instance_resolution_reason']}")
        print(f"  selected:     {'YES' + sel_tag if c['instance_role'] == 'ACTIVE' else 'no'}")
    print(f"\n──────────────────────────────────────────────────────────\n")
