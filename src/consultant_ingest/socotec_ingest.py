"""
socotec_ingest.py — Parser #4: SOCOTEC (Contrôle Technique)
JANSA VISASIST — BET PDF Report Ingestion
Version 1.0 — April 2026

Public API:
    ingest_socotec_folder(folder_path) -> (records, skipped)
"""

import re
import logging
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Avis normalisation (F/S/D → FAV/SUS/DEF — native Socotec labels preserved)
# ---------------------------------------------------------------------------

AVIS_NORM = {
    'F': 'FAV', 'FAVORABLE': 'FAV',
    'S': 'SUS', 'SUSPENDU': 'SUS',
    'D': 'DEF', 'DÉFAVORABLE': 'DEF', 'DEFAVORABLE': 'DEF',
    'D\u00c9FAVORABLE': 'DEF',
}


def normalize_avis(raw: str) -> str | None:
    """Normalise SOCOTEC avis code (F/S/D or full word) to FAV/SUS/DEF (native labels)."""
    cleaned = raw.strip().upper()
    # Normalise accented characters
    cleaned = cleaned.replace('\u00c9', 'E').replace('\u00e9', 'e').upper()
    return AVIS_NORM.get(cleaned)


# ---------------------------------------------------------------------------
# Body metadata extraction — DATE_FICHE and CT_REF from PDF text
# ---------------------------------------------------------------------------

# CT ref variants: CT/204C0/1024/0037 or CT-204C0-1024-0037 or CT 204C0 1024 0037
_CT_BODY_RE = re.compile(
    r'CT[/\-\s]204C0[/\-\s](\d{4})[/\-\s](\d{4})',
    re.IGNORECASE,
)

# Emission date: "Date d'émission : 03/06/2025" or just the most-frequent date on pg1
_DATE_RE = re.compile(r'\b(\d{2}/\d{2}/\d{4})\b')


def _extract_body_ct_ref(text: str) -> str | None:
    """
    Extract and normalize a CT/204C0 reference from PDF body text.
    Returns canonical form CT-204C0-MMYY-NNNN or None if not found.
    """
    m = _CT_BODY_RE.search(text)
    if m:
        return f"CT-204C0-{m.group(1)}-{m.group(2)}"
    return None


def _extract_body_date(page1_text: str) -> str:
    """
    Extract the fiche date from page 1 body text.

    Strategy: the dominant (most frequent) date on page 1 is the fiche date.
    The document list rows all share the same 'Reçu le' date which equals
    the fiche emission date, so the mode is deterministic.

    Returns the dominant date string (dd/mm/yyyy) or '' if none found.
    """
    dates = _DATE_RE.findall(page1_text)
    if not dates:
        return ''
    from collections import Counter
    most_common, count = Counter(dates).most_common(1)[0]
    # Only trust it if it appears at least twice (genuine fiche date) OR is the only one
    if count >= 2 or len(dates) == 1:
        return most_common
    return dates[0]   # first date as weak fallback


def extract_body_metadata(pdf) -> dict:
    """
    Extract CT_REF and DATE_FICHE from PDF page content.
    Reads pages 1 and last to maximise coverage.
    Returns dict: {ct_ref_body, date_fiche_body}
    """
    result = {'ct_ref_body': '', 'date_fiche_body': ''}

    try:
        # Page 1 text
        pg1_text = pdf.pages[0].extract_text() or '' if pdf.pages else ''
        result['date_fiche_body'] = _extract_body_date(pg1_text)

        # CT ref — try page 1 first, then last page
        ct = _extract_body_ct_ref(pg1_text)
        if not ct and len(pdf.pages) > 1:
            last_text = pdf.pages[-1].extract_text() or ''
            ct = _extract_body_ct_ref(last_text)
        if ct:
            result['ct_ref_body'] = ct
    except Exception:
        pass  # non-fatal — fallback to filename metadata

    return result


# ---------------------------------------------------------------------------
# File classification — skip non-parseable files
# ---------------------------------------------------------------------------

SKIP_FILENAME_PATTERNS = [
    re.compile(r'Fiche.+r[eé]ponse', re.IGNORECASE),
    re.compile(r'Rapport.+[eé]tape', re.IGNORECASE),
    re.compile(r'mises en tension', re.IGNORECASE),
    re.compile(r'Plan_EL', re.IGNORECASE),
    re.compile(r'PARKING', re.IGNORECASE),
    re.compile(r'^P231123', re.IGNORECASE),
    re.compile(r'^[A-F0-9]{10}\.pdf$', re.IGNORECASE),
]


def should_skip_file(filename: str) -> bool:
    """Return True if the file should be skipped entirely."""
    for pattern in SKIP_FILENAME_PATTERNS:
        if pattern.search(filename):
            return True
    return False


# ---------------------------------------------------------------------------
# Metadata extraction from filename
# ---------------------------------------------------------------------------

def extract_metadata(filename: str) -> dict:
    """
    Extract CT reference and date from filename.

    Examples:
      "02-03-26 - PARIS ... -CT-204C0-0326-0014.pdf" → date="02/03/26", ct="CT-204C0-0326-0014"
      "10-10-24 - -Fiche examen-CT-204C0-1024-0139.pdf" → date="10/10/24", ct="CT-204C0-1024-0139"
      "rapport 18 Socotec radier.pdf" → date="", ct="" (body fallback used later)

    Returns dict with:
      ct_ref      : canonical CT-204C0-MMYY-NNNN from filename, or '' if not found
      date_fiche  : dd/mm/yyyy from filename prefix, or '' if not found
      ct_ref_raw  : True if ct_ref came from filename (vs body fallback needed)
    """
    date_m = re.match(r'(\d{2})-(\d{2})-(\d{2,4})', filename)
    date_str = ''
    if date_m:
        d, mo, y = date_m.groups()
        if len(y) == 2:
            y = '20' + y
        date_str = f"{d}/{mo}/{y}"

    ct_m = re.search(r'CT[/-]204C0[/-](\d{4})[/-](\d{4})', filename, re.IGNORECASE)
    ct_ref = f"CT-204C0-{ct_m.group(1)}-{ct_m.group(2)}" if ct_m else ''

    return {'ct_ref': ct_ref, 'date_fiche': date_str}


# ---------------------------------------------------------------------------
# Table detection
# ---------------------------------------------------------------------------

def is_avis_table(table: list) -> bool:
    """
    Return True if the table is a SOCOTEC avis body table.
    Detection: header row must contain both 'Avis' and 'Observations'.
    """
    if not table:
        return False
    for row in table[:4]:
        row_text = ' '.join(str(c).strip() if c else '' for c in row)
        if ('Avis' in row_text or 'AVIS' in row_text) and 'Observations' in row_text:
            return True
    return False


def find_columns(header_row: list) -> dict:
    """
    Find the column indices for: elem, avis, obs, num.
    Returns dict with keys: elem_col, avis_col, obs_col, num_col.
    """
    cols: dict[str, int] = {}
    for i, cell in enumerate(header_row):
        h = (str(cell) or '').strip()
        h_upper = h.upper()
        if 'LEMENT' in h_upper or 'LÉMENT' in h_upper:
            cols['elem_col'] = i
        elif h in ('Avis*', 'Avis', 'AVIS'):
            cols['avis_col'] = i
        elif 'OBS' in h_upper:
            cols['obs_col'] = i
        elif h == 'N°' or h == 'N':
            cols['num_col'] = i
    # Defaults
    cols.setdefault('elem_col', 0)
    return cols


# ---------------------------------------------------------------------------
# P17 ref cleaning
# ---------------------------------------------------------------------------

P17_RE = re.compile(r'P17_T2_\S+')

# Fix for SOCOTEC Excel text-wrap: when a P17 ref is too long for the cell,
# the indice letter wraps to the next line. Handles all variants:
#   "...249618\n_A..."   (newline + _A)
#   "...249618_\nA..."   (underscore at end + newline + A)
#   "...249618\n_A"      (newline + _A at end of text)
# Does NOT match "...249523_A\nP17_T2_..." (two separate refs on separate lines)
# because the lookahead requires [-\s] or end-of-string after the letter.
_REJOIN_WRAPPED_INDICE = re.compile(r'(\d{5,6})_?\n_?([A-Z])(?=[-\s]|$)')


def clean_socotec_ref(raw: str) -> str:
    """
    Strip trailing description suffix from SOCOTEC P17 refs.

    Handles these patterns:
      "P17_T2_AU_EXE_AXI_CVC_A041_MAT_AZ_TX_249523_A-A. Pompes..."  → _249523_A
      "P17_T2_AU_EXE_AXI_CVC_A041_RSX_AZ_R8_249618"                → _R8_249618 (no indice)
      "P17_T2_IN_EXE_LGD_GOE_I003_ARM_I2_S5_028175_B-description"  → _028175_B
      "P17_T2_BX_EXE_BEN_CFO_B031_PLN_B1_R3_145173"               → no indice

    Strategy:
      1. Strip trailing `_` characters
      2. Try to match standard P17 ref ending in _NUMERO_LETTER (with indice)
      3. Try to match P17 ref ending in _RTOKEN_NUMERO (no indice, version code)
      4. Strip trailing description starting with `-` or space
      5. Return as-is (already clean or unknown format)
    """
    raw = raw.rstrip('_').strip()
    if not raw:
        return raw

    # Pattern 1: ends with _NUMERO_INDICE (6 or 5 digit numero + single uppercase letter)
    m = re.match(r'^(P17_T2_[\w]+_\d{5,6}_[A-Z])(?:[-\s].*)?$', raw)
    if m:
        return m.group(1)

    # Pattern 2: ends with _RTOKEN_NUMERO or _TX_NUMERO (no indice letter) — e.g. _R8_249618
    # These are complete refs without an indice
    m2 = re.match(r'^(P17_T2_[\w]+_\d{5,6})(?:[-\s].*)?$', raw)
    if m2:
        return m2.group(1)

    # Pattern 3: generic — strip anything starting with hyphen-space or space after last word char
    stripped = re.sub(r'[-\s][^_].*$', '', raw)
    if stripped and stripped.startswith('P17_T2_'):
        return stripped

    return raw


# ---------------------------------------------------------------------------
# Avis table parser — streaming row processor
# ---------------------------------------------------------------------------

AVIS_RE = re.compile(
    r'^([FSD])$|^(Favorable|Suspendu|D[eé]favorable)$',
    re.IGNORECASE
)


def parse_avis_table(table: list, cols: dict, metadata: dict, page_num: int) -> list[dict]:
    """
    Parse a SOCOTEC avis block table using streaming accumulator.

    One avis letter covers a group of P17 refs.
    """
    records = []
    current_avis = None
    current_refs: list[str] = []
    current_obs = ''
    current_num = ''

    def flush():
        nonlocal current_refs
        if not current_avis or not current_refs:
            return
        norm = normalize_avis(current_avis)
        if not norm:
            return
        for ref in current_refs:
            ref_clean = clean_socotec_ref(ref)
            numero_m = re.search(r'(\d{5,6})', ref_clean)
            records.append({
                'SOURCE': 'SOCOTEC',
                'RAPPORT_ID': metadata['ct_ref'],
                'DATE_FICHE': metadata['date_fiche'],
                'REF_DOC': ref_clean,
                'NUMERO': numero_m.group(1) if numero_m else '',
                'STATUT_NORM': norm,
                'OBS_NUM': current_num,
                'OBSERVATIONS': current_obs[:500],
                'PDF_PAGE': page_num,
            })
        current_refs = []

    # Find header row index
    hdr_idx = None
    for i, row in enumerate(table[:4]):
        row_text = ' '.join(str(c).strip() if c else '' for c in row)
        if ('Avis' in row_text or 'AVIS' in row_text) and 'Observations' in row_text:
            hdr_idx = i
            break

    if hdr_idx is None:
        return records

    header = [str(c).strip() if c else '' for c in table[hdr_idx]]
    local_cols = find_columns(header)

    for row in table[hdr_idx + 1:]:
        cleaned = [str(c).strip() if c else '' for c in row]
        if not any(cleaned):
            continue

        elem_col = local_cols.get('elem_col', 0)
        avis_col = local_cols.get('avis_col')
        obs_col  = local_cols.get('obs_col')
        num_col  = local_cols.get('num_col')

        elem_text = cleaned[elem_col] if elem_col < len(cleaned) else ''
        avis_raw  = cleaned[avis_col] if avis_col is not None and avis_col < len(cleaned) else ''
        obs_text  = cleaned[obs_col]  if obs_col  is not None and obs_col  < len(cleaned) else ''
        num_text  = cleaned[num_col]  if num_col  is not None and num_col  < len(cleaned) else ''

        # Check if this row starts a new avis block
        avis_m = AVIS_RE.match(avis_raw) if avis_raw else None
        if avis_m:
            flush()  # emit previous block
            current_avis = avis_m.group(1) or avis_m.group(2)
            current_obs = obs_text
            current_num = num_text

        # Always scan elem_text for P17 refs (first and continuation rows)
        if elem_text and current_avis:
            # Fix SOCOTEC text-wrap: when Excel wraps a long P17 ref,
            # the indice letter (_A, _B...) falls onto the next line.
            # pdfplumber delivers this as "...249618\n_A-Description".
            # Rejoin: NUMERO + optional _ + newline + optional _ + letter
            # → NUMERO_LETTER (e.g. "249618_A-Description")
            elem_fixed = _REJOIN_WRAPPED_INDICE.sub(r'\1_\2', elem_text)
            refs = P17_RE.findall(elem_fixed)
            current_refs.extend(refs)

    flush()  # emit last block
    return records


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_socotec_folder(
    folder_path: str | Path,
) -> tuple[list[dict], list[dict]]:
    """
    Process all SOCOTEC PDF reports in a folder.

    Returns:
        records : list[dict]  — one dict per extracted avis (schema per spec §6)
        skipped : list[dict]  — {"file": str, "page": int, "reason": str}
    """
    folder_path = Path(folder_path)
    pdf_files = sorted(folder_path.glob('*.pdf'))
    all_records: list[dict] = []
    skipped: list[dict] = []

    for pdf_path in pdf_files:
        filename = pdf_path.name

        # Skip non-parseable files
        if should_skip_file(filename):
            logger.info("Skipping non-fiche file: %s", filename)
            skipped.append({'file': filename, 'page': 0, 'reason': 'non-parseable file type'})
            continue

        metadata = extract_metadata(filename)

        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                # Enrich metadata from PDF body where filename was insufficient
                body_meta = extract_body_metadata(pdf)

                # CT_REF: filename wins; fall back to body; fall back to stem
                if not metadata['ct_ref']:
                    metadata['ct_ref'] = body_meta['ct_ref_body'] or Path(filename).stem

                # DATE_FICHE: filename wins; fall back to body
                if not metadata['date_fiche']:
                    metadata['date_fiche'] = body_meta['date_fiche_body']

                logger.info(
                    "Processing SOCOTEC fiche: %s → %s  (date=%s)",
                    filename, metadata['ct_ref'], metadata['date_fiche'] or 'blank'
                )

                file_records = 0
                for page_num, page in enumerate(pdf.pages, 1):
                    # Skip page 1 (document list — no avis)
                    if page_num == 1:
                        continue

                    tables = page.extract_tables()
                    for table in tables:
                        if not table or not is_avis_table(table):
                            continue
                        recs = parse_avis_table(table, {}, metadata, page_num)
                        all_records.extend(recs)
                        file_records += len(recs)

                if file_records == 0:
                    logger.info("No avis records found in %s", filename)

        except Exception as e:
            logger.warning("Failed to process %s: %s", filename, e)
            skipped.append({'file': filename, 'page': 0, 'reason': str(e)})

    logger.info(
        "SOCOTEC ingest complete: %d records from %d files, %d skipped",
        len(all_records), len(pdf_files), len(skipped)
    )
    return all_records, skipped
