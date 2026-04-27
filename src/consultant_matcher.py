"""
consultant_matcher.py
JANSA VISASIST — Consultant ↔ GED Document Matcher
Version 2.0 — April 2026

Matches each consultant report row back to the normalized GED document universe.

Matching cascade (deterministic-first, fallback-explicit):
  1. EXACT_MATCH              — full P17 REF_DOC identity match in GED
  2. MATCH_BY_NUMERO_INDICE   — NUMERO + INDICE both confirmed, single GED candidate
  3. MATCH_BY_NUMERO_INDICE   — NUMERO + INDICE both confirmed, duplicate candidates → most recent
  3. MATCH_BY_NUMERO_INDICE   — NUMERO only, single GED candidate (INDICE not confirmed)
  3.5 MATCH_BY_DATE_PROXIMITY — NUMERO matches multiple GED docs; closest created_at to date_fiche (≤180 d, unique)
  3.6 MATCH_BY_MIXED_HEURISTIC — SAS VAO/VSO lifecycle filter + most recent among survivors
  4. AMBIGUOUS_UNRESOLVED     — no safe single choice found
  5. MATCH_BY_MIXED_HEURISTIC — LOT + SPECIALITE + NIVEAU heuristic (single survivor)
  6. UNMATCHED                — NUMERO not in GED at all

Every match result carries the full trace required by the transparency spec:
  consultant_match_method       : public method label
  consultant_match_confidence   : HIGH | MEDIUM | LOW | AMBIGUOUS_UNRESOLVED | NONE
  candidate_count               : GED candidates evaluated at the decisive step
  candidate_ids_considered      : truncated list of doc_ids evaluated
  winning_candidate_id          : chosen GED doc_id (or empty)
  match_rationale               : human-readable explanation (no "took first")
  date_distance_days            : gap in days if date proximity was used
  indice_fallback_used          : YES / NO
  deterministic_match_used      : YES / NO
"""

import logging
import re
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical source mapping
# ---------------------------------------------------------------------------

CONSULTANT_CANONICAL = {
    "LE_SOMMER":   "AMO HQE LE SOMMER",
    "LESOMMER":    "AMO HQE LE SOMMER",
    "AVLS":        "ACOUSTICIEN AVLS",
    "TERRELL":     "BET STR-TERRELL",
    "SOCOTEC":     "SOCOTEC",
    "BC_SOCOTEC":  "SOCOTEC",
}

# ---------------------------------------------------------------------------
# Public method labels  (consultant_match_method field)
# ---------------------------------------------------------------------------

CMM_EXACT          = "EXACT_MATCH"
CMM_NUM_IND        = "MATCH_BY_NUMERO_INDICE"
CMM_DATE_PROX      = "MATCH_BY_DATE_PROXIMITY"
CMM_RECENT_INDICE  = "MATCH_BY_RECENT_INDICE_FALLBACK"
CMM_MIXED          = "MATCH_BY_MIXED_HEURISTIC"
CMM_AMBIGUOUS      = "AMBIGUOUS_UNRESOLVED"
CMM_UNMATCHED      = "UNMATCHED"

# Public confidence per method (defaults — callers may override for sub-cases)
CMM_CONFIDENCE = {
    CMM_EXACT:         "HIGH",
    CMM_NUM_IND:       "HIGH",     # overridden to MEDIUM when INDICE not confirmed
    CMM_DATE_PROX:     "MEDIUM",
    CMM_RECENT_INDICE: "LOW",
    CMM_MIXED:         "MEDIUM",   # overridden to LOW for lot/spec/niv heuristic
    CMM_AMBIGUOUS:     "AMBIGUOUS_UNRESOLVED",
    CMM_UNMATCHED:     "NONE",
}

# ---------------------------------------------------------------------------
# Internal cascade codes (kept for backward-compat logging only)
# ---------------------------------------------------------------------------
M_EXACT_REF = "EXACT_REF_DOC"
M_NUM_IND   = "NUMERO_INDICE_EXACT"
M_NUM_ONLY  = "NUMERO_EXACT"
M_DATE_PROX = "NUMERO_DATE_PROXIMITY"
M_SAS       = "NUMERO_SAS_FILTER"
M_NUM_AMB   = "NUMERO_AMBIGUOUS"
M_FALLBACK  = "FALLBACK"
M_UNMATCHED = "UNMATCHED"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_str(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() in ("none", "nan") else s


def _normalize_numero(v) -> str:
    s = _clean_str(v)
    if not s:
        return ""
    digits = re.sub(r'\D', '', s)
    if not digits:
        return ""
    try:
        return str(int(digits))
    except ValueError:
        return digits


def _normalize_indice(v) -> str:
    return _clean_str(v).upper()


def _extract_p17_numero(ref_doc: str) -> str:
    if not ref_doc:
        return ""
    matches = re.findall(r'(\d{5,6})', ref_doc)
    return str(int(matches[-1])) if matches else ""


def _extract_p17_indice(ref_doc: str) -> str:
    if not ref_doc:
        return ""
    m = re.search(r'_([A-Z])(?:_.*)?$', ref_doc.rstrip('_'))
    return m.group(1).upper() if m else ""


def _candidate_ids_str(candidates: list, limit: int = 8) -> str:
    """Return comma-separated truncated doc_ids for trace field."""
    return ", ".join(str(c.get("doc_id", ""))[:12] for c in candidates[:limit])


# ---------------------------------------------------------------------------
# GED lookup index builder
# ---------------------------------------------------------------------------

def build_ged_index(docs_df: pd.DataFrame) -> dict:
    """
    Build fast lookup indexes from normalized GED docs DataFrame.

    Returns dict with:
        by_numero   : {numero_str: [doc_row_dict, ...]}
        by_num_ind  : {(numero_str, indice_str): [doc_row_dict, ...]}
        by_ref_doc  : {ref_doc_str: doc_row_dict}
        all_rows    : list of all row dicts (for fallback)
    """
    index = {
        "by_numero":  {},
        "by_num_ind": {},
        "by_ref_doc": {},
        "all_rows":   [],
    }

    has_ref_doc = "ref_doc" in docs_df.columns
    has_libelle = "libelle_du_document" in docs_df.columns

    for _, row in docs_df.iterrows():
        rec = row.to_dict()
        num = _normalize_numero(rec.get("numero_normalized") or rec.get("numero", ""))
        ind = _normalize_indice(rec.get("indice", ""))
        rec["_num_key"] = num
        rec["_ind_key"] = ind
        rec["_libelle"] = _clean_str(rec.get("libelle_du_document")) if has_libelle else ""

        if num:
            index["by_numero"].setdefault(num, []).append(rec)
            index["by_num_ind"].setdefault((num, ind), []).append(rec)

        if has_ref_doc:
            ref = _clean_str(rec.get("ref_doc"))
            if ref:
                index["by_ref_doc"][ref] = rec

        index["all_rows"].append(rec)

    logger.info(
        "GED index built: %d docs, %d unique NUMEROs, %d unique NUMERO+INDICE combos",
        len(index["all_rows"]),
        len(index["by_numero"]),
        len(index["by_num_ind"]),
    )
    return index


# ---------------------------------------------------------------------------
# Date / timestamp helpers
# ---------------------------------------------------------------------------

_DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y"]


def _parse_date_str(s: str) -> Optional[datetime]:
    s = _clean_str(s)
    if not s:
        return None
    s_short = s[:19]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s_short, fmt)
        except (ValueError, TypeError):
            pass
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _parse_ged_date(v) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        import pandas as _pd
        if isinstance(v, _pd.Timestamp):
            return v.to_pydatetime()
    except Exception:
        pass
    return _parse_date_str(str(v))


def _most_recent(candidates: list) -> Optional[dict]:
    """Return the candidate with the largest created_at, or first if no dates."""
    def _ts(c):
        d = _parse_ged_date(c.get("created_at"))
        return d if d is not None else datetime.min
    return max(candidates, key=_ts) if candidates else None


def _date_proximity_resolve(
    candidates: list,
    date_fiche_str: str,
    max_gap_days: int = 180,
) -> tuple[Optional[dict], Optional[int]]:
    """
    Among multiple GED candidates, pick the one whose created_at is closest
    to date_fiche, within max_gap_days.

    Returns (best_doc, gap_days) or (None, None) if not resolvable.
    Requires a unique minimum-gap candidate (no ties).
    """
    d_fiche = _parse_date_str(date_fiche_str)
    if d_fiche is None:
        return None, None

    best_doc = None
    best_gap = None
    tied     = False

    for doc in candidates:
        created = _parse_ged_date(doc.get("created_at"))
        if created is None:
            continue
        gap = abs((d_fiche - created).days)
        if gap > max_gap_days:
            continue
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best_doc = doc
            tied     = False
        elif gap == best_gap:
            tied = True

    if best_doc is None or tied:
        return None, None
    return best_doc, best_gap


# ---------------------------------------------------------------------------
# SAS response helpers
# ---------------------------------------------------------------------------

_SAS_POSITIVE = {"VAOSAS", "VSOSAS"}


def _is_sas_positive(sas_val: str) -> bool:
    v = str(sas_val).upper().replace(" ", "").replace("-", "")
    return any(k in v for k in _SAS_POSITIVE)


def _sas_filter_resolve(candidates: list) -> Optional[dict]:
    """
    Filter candidates to those with a positive SAS response (VAO-SAS / VSO-SAS).
    Among survivors, pick the most recently created.
    Returns None if no SAS-positive candidate exists.
    """
    sas_positive = [c for c in candidates if _is_sas_positive(c.get("sas_reponse", ""))]
    return _most_recent(sas_positive) if sas_positive else None


# ---------------------------------------------------------------------------
# Result builders
# ---------------------------------------------------------------------------

def _build_result(
    c_row: dict,
    g_doc: dict,
    *,
    public_method: str,
    confidence: str,
    match_rationale: str,
    candidate_count: int = 1,
    candidate_ids_considered: str = "",
    date_distance_days: Optional[int] = None,
    indice_fallback_used: bool = False,
    deterministic_match_used: bool = True,
    # Legacy internal code — kept for backward compat
    _internal_method: str = "",
) -> dict:
    """Build a full match result with all trace fields."""
    winning_id = str(g_doc.get("doc_id", ""))
    if not candidate_ids_considered:
        candidate_ids_considered = winning_id[:12]

    match_status = (
        "MATCHED"    if confidence in ("HIGH", "MEDIUM", "LOW") else
        "AMBIGUOUS"  if confidence == "AMBIGUOUS_UNRESOLVED" else
        "UNMATCHED"
    )

    return {
        # ── Consultant input fields ──────────────────────────────────────
        "consultant_source":  _clean_str(c_row.get("SOURCE")),
        "rapport_id":         _clean_str(c_row.get("RAPPORT_ID")),
        "c_ref_doc":          _clean_str(c_row.get("REF_DOC")),
        "c_numero":           _clean_str(c_row.get("NUMERO")),
        "c_indice":           _clean_str(c_row.get("INDICE")),
        "c_statut_norm":      _clean_str(c_row.get("STATUT_NORM")),
        "c_commentaire":      _clean_str(c_row.get("COMMENTAIRE")),
        "c_date_fiche":       _clean_str(c_row.get("DATE_FICHE")),
        # ── Matched GED document fields ──────────────────────────────────
        "matched_doc_id":     winning_id,
        "matched_numero":     str(g_doc.get("numero", "")),
        "matched_indice":     str(g_doc.get("indice", "")),
        "matched_lot":        str(g_doc.get("lot", "")),
        "matched_emetteur":   str(g_doc.get("emetteur", "")),
        "matched_titre":      str(g_doc.get("libelle_du_document", "")),
        "matched_type_doc":   str(g_doc.get("type_de_doc", "")),
        "matched_specialite": str(g_doc.get("specialite", "")),
        "matched_niveau":     str(g_doc.get("niveau", "")),
        # ── Traceability fields ──────────────────────────────────────────
        "consultant_match_method":     public_method,
        "consultant_match_confidence": confidence,
        "candidate_count":             candidate_count,
        "candidate_ids_considered":    candidate_ids_considered,
        "winning_candidate_id":        winning_id,
        "match_rationale":             match_rationale,
        "date_distance_days":          "" if date_distance_days is None else str(date_distance_days),
        "indice_fallback_used":        "YES" if indice_fallback_used else "NO",
        "deterministic_match_used":    "YES" if deterministic_match_used else "NO",
        # ── Derived status ───────────────────────────────────────────────
        "match_status":     match_status,
        # ── Legacy fields (backward compat) ─────────────────────────────
        "match_method":  _internal_method or public_method,
        "confidence":    confidence,
        "rationale":     match_rationale,
    }


def _build_ambiguous_result(
    c_row: dict, candidates: list, c_numero: str, c_indice: str,
) -> dict:
    ids_str  = _candidate_ids_str(candidates)
    indices  = ", ".join(str(c.get("indice", "")) for c in candidates[:8])
    numbers  = ", ".join(str(c.get("numero", "")) for c in candidates[:8])
    rationale = (
        f"NUMERO={c_numero} matched {len(candidates)} GED docs "
        f"with indices [{indices}]; no deterministic, date-proximity, "
        f"or SAS filter resolved it"
    )
    return {
        "consultant_source":  _clean_str(c_row.get("SOURCE")),
        "rapport_id":         _clean_str(c_row.get("RAPPORT_ID")),
        "c_ref_doc":          _clean_str(c_row.get("REF_DOC")),
        "c_numero":           _clean_str(c_row.get("NUMERO")),
        "c_indice":           _clean_str(c_row.get("INDICE")),
        "c_statut_norm":      _clean_str(c_row.get("STATUT_NORM")),
        "c_commentaire":      _clean_str(c_row.get("COMMENTAIRE")),
        "c_date_fiche":       _clean_str(c_row.get("DATE_FICHE")),
        "matched_doc_id":     f"[{len(candidates)} candidates: {ids_str}]",
        "matched_numero":     numbers,
        "matched_indice":     indices,
        "matched_lot":        "",
        "matched_emetteur":   "",
        "matched_titre":      "",
        "matched_type_doc":   "",
        "matched_specialite": "",
        "matched_niveau":     "",
        "consultant_match_method":     CMM_AMBIGUOUS,
        "consultant_match_confidence": "AMBIGUOUS_UNRESOLVED",
        "candidate_count":             len(candidates),
        "candidate_ids_considered":    ids_str,
        "winning_candidate_id":        "",
        "match_rationale":             rationale,
        "date_distance_days":          "",
        "indice_fallback_used":        "NO",
        "deterministic_match_used":    "NO",
        "match_status":   "AMBIGUOUS",
        "match_method":   M_NUM_AMB,
        "confidence":     "AMBIGUOUS_UNRESOLVED",
        "rationale":      rationale,
    }


def _build_unmatched_result(
    c_row: dict, c_numero: str, c_indice: str, ref_doc_raw: str,
) -> dict:
    reasons = []
    if not c_numero:
        reasons.append("no NUMERO extracted from consultant row")
    else:
        reasons.append(f"NUMERO={c_numero} not found in GED index")
    if c_indice:
        reasons.append(f"INDICE={c_indice}")
    if ref_doc_raw:
        reasons.append("REF_DOC present but yielded no GED match")
    rationale = "; ".join(reasons) if reasons else "No matching GED document found"

    return {
        "consultant_source":  _clean_str(c_row.get("SOURCE")),
        "rapport_id":         _clean_str(c_row.get("RAPPORT_ID")),
        "c_ref_doc":          ref_doc_raw,
        "c_numero":           _clean_str(c_row.get("NUMERO")),
        "c_indice":           _clean_str(c_row.get("INDICE")),
        "c_statut_norm":      _clean_str(c_row.get("STATUT_NORM")),
        "c_commentaire":      _clean_str(c_row.get("COMMENTAIRE")),
        "c_date_fiche":       _clean_str(c_row.get("DATE_FICHE")),
        "matched_doc_id":     "",
        "matched_numero":     "",
        "matched_indice":     "",
        "matched_lot":        "",
        "matched_emetteur":   "",
        "matched_titre":      "",
        "matched_type_doc":   "",
        "matched_specialite": "",
        "matched_niveau":     "",
        "consultant_match_method":     CMM_UNMATCHED,
        "consultant_match_confidence": "NONE",
        "candidate_count":             0,
        "candidate_ids_considered":    "",
        "winning_candidate_id":        "",
        "match_rationale":             rationale,
        "date_distance_days":          "",
        "indice_fallback_used":        "NO",
        "deterministic_match_used":    "NO",
        "match_status":   "UNMATCHED",
        "match_method":   M_UNMATCHED,
        "confidence":     "NONE",
        "rationale":      rationale,
    }


# ---------------------------------------------------------------------------
# Fallback heuristic
# ---------------------------------------------------------------------------

def _fallback_match(c_row: dict, all_docs: list) -> Optional[dict]:
    """
    LOT + SPECIALITE + NIVEAU heuristic.
    Returns a candidate only when exactly ONE doc survives the filter.
    """
    lot_raw    = _clean_str(c_row.get("LOT") or c_row.get("LOT_LABEL") or "")
    specialite = _clean_str(c_row.get("SPECIALITE") or "")
    niveau     = _clean_str(c_row.get("NIVEAU") or "")

    if not (lot_raw or specialite or niveau):
        return None

    lot_num = re.sub(r'[^0-9A-Za-z]', '', lot_raw.upper())
    candidates = []
    for doc in all_docs:
        if lot_raw:
            doc_lot = re.sub(r'[^0-9A-Za-z]', '', str(doc.get("lot", "")).upper())
            if lot_num and lot_num not in doc_lot and doc_lot not in lot_num:
                continue
        if specialite:
            doc_spec = str(doc.get("specialite", "")).upper()
            if specialite.upper() not in doc_spec and doc_spec not in specialite.upper():
                continue
        if niveau:
            doc_niv = str(doc.get("niveau", "")).upper()
            if niveau.upper() not in doc_niv and doc_niv not in niveau.upper():
                continue
        candidates.append(doc)

    return candidates[0] if len(candidates) == 1 else None


# ---------------------------------------------------------------------------
# Single-row matching — full cascade
# ---------------------------------------------------------------------------

def _match_row(consultant_row: dict, ged_index: dict) -> dict:
    """
    Match one consultant row against the GED index.
    Returns a fully-traced match result dict.
    """
    source       = _clean_str(consultant_row.get("SOURCE"))
    ref_doc_raw  = _clean_str(consultant_row.get("REF_DOC"))
    c_numero_raw = _clean_str(consultant_row.get("NUMERO"))
    c_indice_raw = _clean_str(consultant_row.get("INDICE"))
    c_date_fiche = _clean_str(consultant_row.get("DATE_FICHE"))

    is_avls = "AVLS" in source.upper()

    p17_numero = _extract_p17_numero(ref_doc_raw)
    p17_indice = _extract_p17_indice(ref_doc_raw)

    if is_avls and p17_indice:
        c_indice = p17_indice          # AVLS: real indice is in REF_DOC trailing letter
    else:
        c_indice = _normalize_indice(c_indice_raw) or p17_indice

    c_numero = _normalize_numero(p17_numero or c_numero_raw)

    # ── Attempt 1: Exact REF_DOC match ────────────────────────────────────
    if ref_doc_raw and ref_doc_raw in ged_index["by_ref_doc"]:
        g = ged_index["by_ref_doc"][ref_doc_raw]
        return _build_result(
            consultant_row, g,
            public_method=CMM_EXACT,
            confidence="HIGH",
            match_rationale="Exact REF_DOC match against GED ref_doc index",
            candidate_count=1,
            candidate_ids_considered=str(g.get("doc_id", ""))[:12],
            deterministic_match_used=True,
            _internal_method=M_EXACT_REF,
        )

    # ── Attempt 2: NUMERO + INDICE exact match ────────────────────────────
    if c_numero and c_indice:
        cands = ged_index["by_num_ind"].get((c_numero, c_indice), [])
        n = len(cands)
        if n == 1:
            return _build_result(
                consultant_row, cands[0],
                public_method=CMM_NUM_IND,
                confidence="HIGH",
                match_rationale=(
                    f"Exact NUMERO={c_numero} + INDICE={c_indice} — "
                    f"1 unique GED candidate"
                ),
                candidate_count=1,
                candidate_ids_considered=_candidate_ids_str(cands),
                deterministic_match_used=True,
                _internal_method=M_NUM_IND,
            )
        if n > 1:
            # Multiple docs share the same NUMERO+INDICE (duplicate uploads / multi-lot).
            # Pick most recently created — NOT "took first".
            best = _most_recent(cands)
            created_str = ""
            d = _parse_ged_date(best.get("created_at"))
            if d:
                created_str = d.strftime("%d/%m/%Y")
            return _build_result(
                consultant_row, best,
                public_method=CMM_RECENT_INDICE,
                confidence="LOW",
                match_rationale=(
                    f"NUMERO={c_numero} + INDICE={c_indice} matched {n} duplicate GED docs "
                    f"(same NUMERO+INDICE, likely multi-lot or re-uploads); "
                    f"selected most recently created (created {created_str})"
                ),
                candidate_count=n,
                candidate_ids_considered=_candidate_ids_str(cands),
                indice_fallback_used=True,
                deterministic_match_used=False,
                _internal_method=M_NUM_IND,
            )

    # ── Attempt 3: NUMERO-only match ──────────────────────────────────────
    if c_numero:
        cands = ged_index["by_numero"].get(c_numero, [])
        n = len(cands)

        if n == 0:
            pass  # fall through to fallback/unmatched

        elif n == 1:
            return _build_result(
                consultant_row, cands[0],
                public_method=CMM_NUM_IND,
                confidence="MEDIUM",      # INDICE not confirmed
                match_rationale=(
                    f"NUMERO={c_numero} — 1 unique GED candidate "
                    f"(INDICE not confirmed from consultant data)"
                ),
                candidate_count=1,
                candidate_ids_considered=_candidate_ids_str(cands),
                deterministic_match_used=True,
                _internal_method=M_NUM_ONLY,
            )

        else:
            # ── Attempt 3.5: Date proximity ───────────────────────────────
            best, gap_days = _date_proximity_resolve(cands, c_date_fiche, max_gap_days=180)
            if best:
                return _build_result(
                    consultant_row, best,
                    public_method=CMM_DATE_PROX,
                    confidence="MEDIUM",
                    match_rationale=(
                        f"NUMERO={c_numero} — {n} candidates, resolved by date proximity: "
                        f"{gap_days} days between date_fiche ({c_date_fiche}) "
                        f"and GED created_at — unique closest within 180d"
                    ),
                    candidate_count=n,
                    candidate_ids_considered=_candidate_ids_str(cands),
                    date_distance_days=gap_days,
                    deterministic_match_used=False,
                    _internal_method=M_DATE_PROX,
                )

            # ── Attempt 3.6: SAS VAO/VSO filter + most recent ────────────
            sas_best = _sas_filter_resolve(cands)
            if sas_best:
                sas_val      = sas_best.get("sas_reponse", "")
                n_sas        = sum(1 for c in cands if _is_sas_positive(c.get("sas_reponse", "")))
                d_best       = _parse_ged_date(sas_best.get("created_at"))
                created_str  = d_best.strftime("%d/%m/%Y") if d_best else "unknown date"
                return _build_result(
                    consultant_row, sas_best,
                    public_method=CMM_MIXED,
                    confidence="MEDIUM",
                    match_rationale=(
                        f"NUMERO={c_numero} — {n} candidates, {n_sas} carry SAS "
                        f"VAO/VSO approval ({sas_val}); selected most recently created "
                        f"SAS-approved doc (created {created_str})"
                    ),
                    candidate_count=n,
                    candidate_ids_considered=_candidate_ids_str(cands),
                    indice_fallback_used=True,
                    deterministic_match_used=False,
                    _internal_method=M_SAS,
                )

            # ── No resolution — AMBIGUOUS ─────────────────────────────────
            return _build_ambiguous_result(consultant_row, cands, c_numero, c_indice)

    # ── Attempt 4: LOT + SPECIALITE + NIVEAU heuristic ───────────────────
    fb = _fallback_match(consultant_row, ged_index["all_rows"])
    if fb:
        lot_used   = _clean_str(consultant_row.get("LOT") or consultant_row.get("LOT_LABEL") or "")
        spec_used  = _clean_str(consultant_row.get("SPECIALITE") or "")
        niv_used   = _clean_str(consultant_row.get("NIVEAU") or "")
        signals    = [f"LOT={lot_used}" if lot_used else "",
                      f"SPECIALITE={spec_used}" if spec_used else "",
                      f"NIVEAU={niv_used}" if niv_used else ""]
        sig_str    = " + ".join(s for s in signals if s)
        return _build_result(
            consultant_row, fb,
            public_method=CMM_MIXED,
            confidence="LOW",
            match_rationale=(
                f"Heuristic LOT/SPECIALITE/NIVEAU match ({sig_str}); "
                f"NUMERO was absent or not in GED; 1 surviving candidate"
            ),
            candidate_count=1,
            candidate_ids_considered=str(fb.get("doc_id", ""))[:12],
            deterministic_match_used=False,
            _internal_method=M_FALLBACK,
        )

    # ── Unmatched ─────────────────────────────────────────────────────────
    return _build_unmatched_result(consultant_row, c_numero, c_indice, ref_doc_raw)


# ---------------------------------------------------------------------------
# Batch matching
# ---------------------------------------------------------------------------

def match_consultant_rows(
    consultant_rows: list[dict],
    ged_index: dict,
) -> list[dict]:
    results = []
    for row in consultant_rows:
        results.append(_match_row(row, ged_index))
    return results


def match_all_consultants(
    all_rows_by_source: dict,
    ged_index: dict,
) -> dict:
    """
    Match all consultant sources against GED.

    Returns dict with:
        results      : all match records
        matched      : MATCHED records (HIGH + MEDIUM + LOW confidence)
        unmatched    : UNMATCHED records
        ambiguous    : AMBIGUOUS_UNRESOLVED records
        stats        : per-source and overall counts
    """
    all_results = []

    for source_key, rows in all_rows_by_source.items():
        logger.info("[%s] Matching %d rows against GED...", source_key, len(rows))
        matched_rows = match_consultant_rows(rows, ged_index)
        all_results.extend(matched_rows)

        n_match = sum(1 for r in matched_rows if r["match_status"] == "MATCHED")
        n_amb   = sum(1 for r in matched_rows if r["match_status"] == "AMBIGUOUS")
        n_unm   = sum(1 for r in matched_rows if r["match_status"] == "UNMATCHED")
        logger.info(
            "[%s] Results: MATCHED=%d  AMBIGUOUS=%d  UNMATCHED=%d",
            source_key, n_match, n_amb, n_unm,
        )

    matched   = [r for r in all_results if r["match_status"] == "MATCHED"]
    ambiguous = [r for r in all_results if r["match_status"] == "AMBIGUOUS"]
    unmatched = [r for r in all_results if r["match_status"] == "UNMATCHED"]

    # Per-source stats
    stats = {}
    for src in {r["consultant_source"] for r in all_results}:
        rows = [r for r in all_results if r["consultant_source"] == src]
        stats[src] = {
            "total":     len(rows),
            "matched":   sum(1 for r in rows if r["match_status"] == "MATCHED"),
            "ambiguous": sum(1 for r in rows if r["match_status"] == "AMBIGUOUS"),
            "unmatched": sum(1 for r in rows if r["match_status"] == "UNMATCHED"),
        }

    logger.info(
        "TOTAL: %d rows | MATCHED=%d | AMBIGUOUS=%d | UNMATCHED=%d",
        len(all_results), len(matched), len(ambiguous), len(unmatched),
    )
    return {
        "results":   all_results,
        "matched":   matched,
        "ambiguous": ambiguous,
        "unmatched": unmatched,
        "stats":     stats,
    }


# ---------------------------------------------------------------------------
# Enrichment record builder — with confidence safety gate
# ---------------------------------------------------------------------------

#: Confidence levels that are allowed to auto-enrich GF
ENRICH_ALLOWED_CONFIDENCE = {"HIGH", "MEDIUM"}


def build_enrichment_records(
    matched_rows: list[dict],
) -> list[dict]:
    """
    Build enrichment records from MATCHED rows.

    Enrichment safety gate:
      - HIGH and MEDIUM → included automatically
      - LOW             → included but flagged; downstream writer checks the flag
      - AMBIGUOUS/NONE  → excluded entirely (should not appear here)

    Returns list of enrichment dicts.
    """
    enrichments = []
    skipped_low   = 0
    skipped_other = 0

    for r in matched_rows:
        confidence = r.get("consultant_match_confidence", r.get("confidence", ""))

        if confidence not in ENRICH_ALLOWED_CONFIDENCE:
            if confidence == "LOW":
                skipped_low += 1
            else:
                skipped_other += 1
            continue

        source = r.get("consultant_source", "")
        enrichments.append({
            "doc_id":                    r.get("matched_doc_id", ""),
            "consultant_source":         source,
            "gf_approver_canonical":     _source_to_gf_canonical(source),
            "consultant_date_fiche":     r.get("c_date_fiche", ""),
            "consultant_statut_norm":    r.get("c_statut_norm", ""),
            "consultant_commentaire":    r.get("c_commentaire", ""),
            "consultant_ref_doc":        r.get("c_ref_doc", ""),
            "consultant_rapport_id":     r.get("rapport_id", ""),
            "matched_numero":            r.get("matched_numero", ""),
            "matched_indice":            r.get("matched_indice", ""),
            "matched_lot":               r.get("matched_lot", ""),
            "matched_titre":             r.get("matched_titre", ""),
            "match_confidence":          confidence,
            "consultant_match_method":   r.get("consultant_match_method", ""),
            "match_method":              r.get("match_method", ""),
            "source":                    "consultant_report",
        })

    if skipped_low:
        logger.warning(
            "Enrichment safety gate: excluded %d LOW-confidence matches from GF enrichment",
            skipped_low,
        )
    if skipped_other:
        logger.warning(
            "Enrichment safety gate: excluded %d rows with unexpected confidence from GF enrichment",
            skipped_other,
        )

    logger.info("Enrichment records ready: %d (of %d matched rows)", len(enrichments), len(matched_rows))
    return enrichments


def _source_to_gf_canonical(source: str) -> str:
    upper = source.upper().replace(" ", "_").replace("-", "_")
    for key, canonical in CONSULTANT_CANONICAL.items():
        if key in upper:
            return canonical
    return source
