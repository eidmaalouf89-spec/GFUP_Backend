"""
consultant_transformers.py
JANSA VISASIST — Consultant Report Builder
Version 1.2 — April 2026

Converts raw parser records into final output row dicts
for each of the 4 workbook sheets.

Each transformer:
  - maps parser fields → exact final column names
  - normalises blanks to ""
  - generates strengthened UPSERT_KEY (collision-resistant, deterministic)
  - injects shared LAST_UPDATED timestamp
  - deduplicates technical duplicates (full-row, then UPSERT_KEY-based)
  - never invents data

Agreed output schema — core columns (positions 1–11) are identical for all sheets:
  SOURCE | RAPPORT_ID | DATE_FICHE | NUMERO | INDICE | REF_DOC |
  STATUT_NORM | COMMENTAIRE | PDF_PAGE | UPSERT_KEY | LAST_UPDATED
Consultant-specific extra columns are appended after LAST_UPDATED.

UPSERT_KEY formulas (v1.2):
  Le Sommer : RAPPORT_ID|REF_DOC|STATUT_NORM|SECTION|TABLE_TYPE|PDF_PAGE
  AVLS       : RAPPORT_ID|REF_DOC|LOT_LABEL|N_VISA|STATUT_NORM|PDF_PAGE
  Terrell    : RAPPORT_ID|REF_DOC|STATUT_NORM|PDF_PAGE
               fallback (no REF_DOC): RAPPORT_ID|NUMERO|INDICE|BAT|LOT|PDF_PAGE
  Socotec    : RAPPORT_ID|REF_DOC|STATUT_NORM|OBS_NUM  (when OBS_NUM present)
               RAPPORT_ID|REF_DOC|STATUT_NORM|PDF_PAGE  (when OBS_NUM blank)
               fallback (no REF_DOC): RAPPORT_ID|NUMERO|STATUT_NORM|OBS_NUM|PDF_PAGE

Socotec native statuses FAV/SUS/DEF are preserved — never changed to VSO/VAO/REF.
"""

import re
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _clean(value) -> str:
    """Convert any value to clean string; returns '' for None/nan/empty."""
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in ("none", "nan", ""):
        return ""
    return s


def _indice_from_ref(ref: str) -> str:
    """Extract trailing single uppercase letter from a P17 ref (_X at end)."""
    m = re.search(r'_([A-Z])$', ref.rstrip("_"))
    return m.group(1) if m else ""


def _numero_from_ref(ref: str) -> str:
    """Extract last 5-6 digit NUMERO from a P17 ref."""
    matches = re.findall(r'\d{5,6}', ref)
    return matches[-1] if matches else ""


def _dedup_full_row(rows: list[dict]) -> list[dict]:
    """
    Remove rows that are completely identical across ALL fields.
    Conservative: only drops a row when every single value matches another.
    """
    seen: set = set()
    result = []
    for row in rows:
        identity = tuple(sorted(row.items()))
        if identity in seen:
            continue
        seen.add(identity)
        result.append(row)
    return result


def _dedup_by_upsert_key(rows: list[dict]) -> list[dict]:
    """
    Keep only the first occurrence of each UPSERT_KEY.
    Used after full-row dedup to collapse duplicates from identical files
    that produce slightly different PDF metadata (e.g., different PDF_PAGE).
    """
    seen: set = set()
    result = []
    for row in rows:
        key = row.get("UPSERT_KEY", "")
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


# ---------------------------------------------------------------------------
# Le Sommer transformer
# ---------------------------------------------------------------------------

# RAPPORT_LE_SOMMER — exact column contract (14 cols)
LS_COLUMNS = [
    "SOURCE", "RAPPORT_ID", "DATE_FICHE", "NUMERO", "INDICE",
    "REF_DOC", "STATUT_NORM", "COMMENTAIRE", "PDF_PAGE",
    "UPSERT_KEY", "LAST_UPDATED",
    "LOT_TYPE", "SECTION", "TABLE_TYPE",
]


def _build_lesommer_upsert_key(
    rapport_id: str, ref_doc: str, statut_norm: str,
    section: str, table_type: str, pdf_page: str,
) -> str:
    return f"{rapport_id}|{ref_doc}|{statut_norm}|{section}|{table_type}|{pdf_page}"


def transform_lesommer_records(
    raw_records: list[dict],
    last_updated: str,
) -> list[dict]:
    """
    Transform raw Le Sommer parser records into RAPPORT_LE_SOMMER rows.

    Parser → output mapping:
      DATE_VISA → DATE_FICHE  (back-filled with file-level report date)
      COMMENTAIRE → COMMENTAIRE (truncated at 500 chars in parser)
      UPSERT_KEY = RAPPORT_ID|REF_DOC|STATUT_NORM|SECTION|TABLE_TYPE|PDF_PAGE
    """
    rows = []
    for r in raw_records:
        rapport_id  = _clean(r.get("RAPPORT_ID"))
        numero      = _clean(r.get("NUMERO"))
        indice      = _clean(r.get("INDICE"))
        ref_doc     = _clean(r.get("REF_DOC"))
        statut_norm = _clean(r.get("STATUT_NORM"))
        pdf_page    = _clean(r.get("PDF_PAGE"))
        section     = _clean(r.get("SECTION"))
        table_type  = _clean(r.get("TABLE_TYPE"))

        # Fill INDICE from trailing letter of REF_DOC when blank
        if not indice and ref_doc:
            indice = _indice_from_ref(ref_doc)

        # Fill NUMERO from REF_DOC digit sequence when blank
        if not numero and ref_doc:
            numero = _numero_from_ref(ref_doc)

        upsert_key = _build_lesommer_upsert_key(
            rapport_id, ref_doc, statut_norm, section, table_type, pdf_page
        )

        rows.append({
            "SOURCE":       _clean(r.get("SOURCE")) or "LE_SOMMER",
            "RAPPORT_ID":   rapport_id,
            "DATE_FICHE":   _clean(r.get("DATE_VISA")),
            "NUMERO":       numero,
            "INDICE":       indice,
            "REF_DOC":      ref_doc,
            "STATUT_NORM":  statut_norm,
            "COMMENTAIRE":  _clean(r.get("COMMENTAIRE")),
            "PDF_PAGE":     pdf_page,
            "UPSERT_KEY":   upsert_key,
            "LAST_UPDATED": last_updated,
            "LOT_TYPE":     _clean(r.get("LOT_TYPE")),
            "SECTION":      section,
            "TABLE_TYPE":   table_type,
        })

    # Step 1: full-row identity dedup
    before = len(rows)
    rows = _dedup_full_row(rows)
    after_full = len(rows)

    # Step 2: UPSERT_KEY-based dedup (collapses same-business-entity duplicates)
    rows = _dedup_by_upsert_key(rows)
    after_key = len(rows)

    removed = before - after_key
    if removed:
        logger.info(
            "LE_SOMMER dedup: removed %d rows (%d full-row, %d by UPSERT_KEY)",
            removed, before - after_full, after_full - after_key,
        )
    return rows


# ---------------------------------------------------------------------------
# AVLS transformer
# ---------------------------------------------------------------------------

# RAPPORT_AVLS — exact column contract (15 cols)
AVLS_COLUMNS = [
    "SOURCE", "RAPPORT_ID", "DATE_FICHE", "NUMERO", "INDICE",
    "REF_DOC", "STATUT_NORM", "COMMENTAIRE", "PDF_PAGE",
    "UPSERT_KEY", "LAST_UPDATED",
    "LOT_LABEL", "LOT_NUM", "N_VISA", "REVIEWER",
]


def _build_avls_upsert_key(
    rapport_id: str, ref_doc: str, lot_label: str,
    n_visa: str, statut_norm: str, pdf_page: str,
) -> str:
    return f"{rapport_id}|{ref_doc}|{lot_label}|{n_visa}|{statut_norm}|{pdf_page}"


def transform_avls_records(
    raw_records: list[dict],
    last_updated: str,
) -> list[dict]:
    """
    Transform raw AVLS parser records into RAPPORT_AVLS rows.

    UPSERT_KEY = RAPPORT_ID|REF_DOC|LOT_LABEL|N_VISA|STATUT_NORM|PDF_PAGE
    """
    rows = []
    for r in raw_records:
        rapport_id  = _clean(r.get("RAPPORT_ID"))
        ref_doc     = _clean(r.get("REF_DOC"))
        lot_label   = _clean(r.get("LOT_LABEL"))
        n_visa      = _clean(r.get("N_VISA"))
        numero      = _clean(r.get("NUMERO"))
        statut_norm = _clean(r.get("STATUT_NORM"))
        pdf_page    = _clean(r.get("PDF_PAGE"))

        # AVLS: ALWAYS derive INDICE from the trailing letter in REF_DOC.
        # The parser's "INDICE" field contains the report revision number
        # (IND column from the AVLS header: 1, 2, 3...) which is NOT the
        # document version letter (A, B, C...).
        indice = _indice_from_ref(ref_doc) if ref_doc else ""
        if not numero and ref_doc:
            numero = _numero_from_ref(ref_doc)

        upsert_key = _build_avls_upsert_key(
            rapport_id, ref_doc, lot_label, n_visa, statut_norm, pdf_page
        )

        rows.append({
            "SOURCE":       _clean(r.get("SOURCE")) or "AVLS",
            "RAPPORT_ID":   rapport_id,
            "DATE_FICHE":   _clean(r.get("DATE_FICHE")),
            "NUMERO":       numero,
            "INDICE":       indice,
            "REF_DOC":      ref_doc,
            "STATUT_NORM":  statut_norm,
            "COMMENTAIRE":  _clean(r.get("COMMENTAIRE")),
            "PDF_PAGE":     pdf_page,
            "UPSERT_KEY":   upsert_key,
            "LAST_UPDATED": last_updated,
            "LOT_LABEL":    lot_label,
            "LOT_NUM":      _clean(r.get("LOT_NUM")),
            "N_VISA":       n_visa,
            "REVIEWER":     _clean(r.get("REVIEWER")),
        })
    return rows


# ---------------------------------------------------------------------------
# Terrell transformer
# ---------------------------------------------------------------------------

# RAPPORT_TERRELL — exact column contract (19 cols)
TERRELL_COLUMNS = [
    "SOURCE", "RAPPORT_ID", "DATE_FICHE", "NUMERO", "INDICE",
    "REF_DOC", "STATUT_NORM", "COMMENTAIRE", "PDF_PAGE",
    "UPSERT_KEY", "LAST_UPDATED",
    "BAT", "LOT", "SPECIALITE", "TYPE_DOC", "NIVEAU", "DATE_SOURCE", "DESIGNATION",
]


def _build_terrell_upsert_key(
    rapport_id: str, ref_doc: str, statut_norm: str, pdf_page: str,
    numero: str, indice: str, bat: str, lot: str,
) -> str:
    if ref_doc:
        return f"{rapport_id}|{ref_doc}|{statut_norm}|{pdf_page}"
    return f"{rapport_id}|{numero}|{indice}|{bat}|{lot}|{pdf_page}"


def transform_terrell_records(
    raw_records: list[dict],
    last_updated: str,
) -> list[dict]:
    """
    Transform raw Terrell parser records into RAPPORT_TERRELL rows.

    Parser → output mapping:
      DATE_RECEPT → DATE_FICHE  (back-filled with fiche-level date where blank)
      OBSERVATIONS → COMMENTAIRE
      UPSERT_KEY = RAPPORT_ID|REF_DOC|STATUT_NORM|PDF_PAGE
    """
    rows = []
    for r in raw_records:
        rapport_id  = _clean(r.get("RAPPORT_ID"))
        numero      = _clean(r.get("NUMERO"))
        indice      = _clean(r.get("INDICE"))
        bat         = _clean(r.get("BAT"))
        lot         = _clean(r.get("LOT"))
        ref_doc     = _clean(r.get("REF_DOC"))
        statut_norm = _clean(r.get("STATUT_NORM"))
        pdf_page    = _clean(r.get("PDF_PAGE"))

        if not indice and ref_doc:
            indice = _indice_from_ref(ref_doc)
        if not numero and ref_doc:
            numero = _numero_from_ref(ref_doc)

        upsert_key = _build_terrell_upsert_key(
            rapport_id, ref_doc, statut_norm, pdf_page,
            numero, indice, bat, lot,
        )

        rows.append({
            "SOURCE":       _clean(r.get("SOURCE")) or "TERRELL",
            "RAPPORT_ID":   rapport_id,
            "DATE_FICHE":   _clean(r.get("DATE_RECEPT")),
            "NUMERO":       numero,
            "INDICE":       indice,
            "REF_DOC":      ref_doc,
            "STATUT_NORM":  statut_norm,
            "COMMENTAIRE":  _clean(r.get("OBSERVATIONS")),
            "PDF_PAGE":     pdf_page,
            "UPSERT_KEY":   upsert_key,
            "LAST_UPDATED": last_updated,
            "BAT":          bat,
            "LOT":          lot,
            "SPECIALITE":   _clean(r.get("SPECIALITE")),
            "TYPE_DOC":     _clean(r.get("TYPE_DOC")),
            "NIVEAU":       _clean(r.get("NIVEAU")),
            "DATE_SOURCE":  _clean(r.get("DATE_SOURCE")),
            "DESIGNATION":  _clean(r.get("DESIGNATION")),
        })

    # Step 1: full-row identity dedup
    before = len(rows)
    rows = _dedup_full_row(rows)
    after_full = len(rows)

    # Step 2: UPSERT_KEY-based dedup (same ref/status/page in two tables on one page)
    rows = _dedup_by_upsert_key(rows)
    after_key = len(rows)

    removed = before - after_key
    if removed:
        logger.info(
            "TERRELL dedup: removed %d rows (%d full-row, %d by UPSERT_KEY)",
            removed, before - after_full, after_full - after_key,
        )
    return rows


# ---------------------------------------------------------------------------
# Socotec transformer
# ---------------------------------------------------------------------------

# RAPPORT_SOCOTEC — exact column contract (13 cols)
SOCOTEC_COLUMNS = [
    "SOURCE", "RAPPORT_ID", "DATE_FICHE", "NUMERO", "INDICE",
    "REF_DOC", "STATUT_NORM", "COMMENTAIRE", "PDF_PAGE",
    "UPSERT_KEY", "LAST_UPDATED",
    "CT_REF", "OBS_NUM",
]


def _build_socotec_upsert_key(
    rapport_id: str, ref_doc: str, statut_norm: str,
    obs_num: str, numero: str, pdf_page: str,
) -> str:
    """
    UPSERT_KEY for Socotec rows (v1.2 — collision-resistant).

    When REF_DOC is present:
      - With OBS_NUM  : RAPPORT_ID|REF_DOC|STATUT_NORM|OBS_NUM
      - Without OBS_NUM: RAPPORT_ID|REF_DOC|STATUT_NORM|PDF_PAGE
        (adds PDF_PAGE so same-ref duplicate-file rows collide only on the same page)

    When REF_DOC is blank:
      RAPPORT_ID|NUMERO|STATUT_NORM|OBS_NUM|PDF_PAGE
    """
    if ref_doc:
        if obs_num:
            return f"{rapport_id}|{ref_doc}|{statut_norm}|{obs_num}"
        return f"{rapport_id}|{ref_doc}|{statut_norm}|{pdf_page}"
    return f"{rapport_id}|{numero}|{statut_norm}|{obs_num}|{pdf_page}"


def transform_socotec_records(
    raw_records: list[dict],
    last_updated: str,
) -> list[dict]:
    """
    Transform raw Socotec parser records into RAPPORT_SOCOTEC rows.

    Parser → output mapping:
      RAPPORT_ID    → RAPPORT_ID + CT_REF (same value — canonical CT-204C0-... ref)
      OBSERVATIONS  → COMMENTAIRE
      INDICE        ← derived from trailing letter of REF_DOC
      UPSERT_KEY    = see _build_socotec_upsert_key

    STATUT_NORM is already FAV/SUS/DEF from patched socotec_ingest.py.
    Native labels are preserved — they are never converted to VSO/VAO/REF.
    """
    rows = []
    for r in raw_records:
        rapport_id  = _clean(r.get("RAPPORT_ID"))
        numero      = _clean(r.get("NUMERO"))
        ref_doc     = _clean(r.get("REF_DOC"))
        statut_norm = _clean(r.get("STATUT_NORM"))
        obs_num     = _clean(r.get("OBS_NUM"))
        pdf_page    = _clean(r.get("PDF_PAGE"))

        # INDICE: derive deterministically from trailing letter of cleaned REF_DOC
        indice = _indice_from_ref(ref_doc) if ref_doc else ""

        # Fill NUMERO from REF_DOC digit sequence when blank
        if not numero and ref_doc:
            numero = _numero_from_ref(ref_doc)

        upsert_key = _build_socotec_upsert_key(
            rapport_id, ref_doc, statut_norm, obs_num, numero, pdf_page
        )

        rows.append({
            "SOURCE":       _clean(r.get("SOURCE")) or "SOCOTEC",
            "RAPPORT_ID":   rapport_id,
            "DATE_FICHE":   _clean(r.get("DATE_FICHE")),
            "NUMERO":       numero,
            "INDICE":       indice,
            "REF_DOC":      ref_doc,
            "STATUT_NORM":  statut_norm,
            "COMMENTAIRE":  _clean(r.get("OBSERVATIONS")),
            "PDF_PAGE":     pdf_page,
            "UPSERT_KEY":   upsert_key,
            "LAST_UPDATED": last_updated,
            "CT_REF":       rapport_id,  # CT ref IS the canonical RAPPORT_ID
            "OBS_NUM":      obs_num,
        })

    # Step 1: full-row identity dedup (handles exact file copies)
    before = len(rows)
    rows = _dedup_full_row(rows)
    after_full = len(rows)

    # Step 2: UPSERT_KEY-based dedup (collapses same-fiche duplicate files
    # that generate the same business-key but differ in minor metadata)
    rows = _dedup_by_upsert_key(rows)
    after_key = len(rows)

    removed = before - after_key
    if removed:
        logger.info(
            "SOCOTEC dedup: removed %d rows (%d full-row, %d by UPSERT_KEY)",
            removed, before - after_full, after_full - after_key,
        )
    return rows
