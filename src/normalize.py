"""
normalize.py
------------
All normalization logic:
  - Lot number normalization (A041 → 41, I041 → 41)
  - Status cleaning (.VAO → VAO)
  - Date réponse interpretation (text → status enum)
  - Emetteur mapping via Mapping.xlsx
  - NUMERO normalization
"""

import re
from pathlib import Path
from typing import Optional

import pandas as pd


# ─────────────────────────────────────────────────────────────
# 1. STATUS NORMALIZATION
# ─────────────────────────────────────────────────────────────

VALID_STATUSES = {"VAO", "VSO", "REF", "HM", "SUS"}

PENDING_KEYWORDS = {
    "en attente": "PENDING_IN_DELAY",
    "rappel en attente": "PENDING_LATE",
    "retard": "PENDING_LATE",
}


def clean_status(raw: Optional[str]) -> Optional[str]:
    """Remove leading dots and normalize status strings."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s.lower() in ("", "none", "nan"):
        return None
    # Remove leading dots
    s = s.lstrip(".")
    s = s.strip()
    if not s:
        return None
    return s.upper()


def interpret_date_field(raw) -> dict:
    """
    The 'Date réponse' field can contain:
      - empty/None → NOT_CALLED
      - a datetime → ANSWERED
      - text like 'en attente' → PENDING_IN_DELAY
      - text like 'Rappel en attente' → PENDING_LATE

    Returns dict: {date: ..., status_type: NOT_CALLED|PENDING_IN_DELAY|PENDING_LATE|ANSWERED}
    """
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return {"date": None, "date_status_type": "NOT_CALLED"}

    if isinstance(raw, str):
        lower = raw.strip().lower()
        for keyword, status_type in PENDING_KEYWORDS.items():
            if keyword in lower:
                return {"date": None, "date_status_type": status_type}
        # Non-matching text — treat as unknown pending
        return {"date": None, "date_status_type": "PENDING_IN_DELAY"}

    # datetime or date object
    import datetime
    if isinstance(raw, (datetime.datetime, datetime.date)):
        return {"date": raw, "date_status_type": "ANSWERED"}

    # Fallback
    return {"date": None, "date_status_type": "NOT_CALLED"}


# ─────────────────────────────────────────────────────────────
# 2. LOT NORMALIZATION
# ─────────────────────────────────────────────────────────────

def normalize_lot(lot_raw: Optional[str]) -> Optional[str]:
    """
    Extract the lot identifier from raw LOT field.
    Returns: numeric part + optional A/B suffix, e.g.:
      A041  → 41
      I041  → 41
      I013A → 13A
      I013B → 13B
      A12B  → 12B
      B12A  → 12A
      B16A  → 16A
      B16B  → 16B
      041   → 41
    """
    if lot_raw is None:
        return None
    s = str(lot_raw).strip()
    # Pattern: optional letter prefix(es) + digits + optional trailing A/B letter
    m = re.match(r'^[A-Za-z]+(\d+)([A-Za-z]?)$', s)
    if m:
        num = m.group(1)
        suffix = m.group(2).upper() if m.group(2) else ""
        num_int = str(int(num))
        return num_int + suffix if suffix else num_int

    m2 = re.match(r'^(\d+)([A-Za-z]?)$', s)
    if m2:
        num_int = str(int(m2.group(1)))
        suffix = m2.group(2).upper() if m2.group(2) else ""
        return num_int + suffix if suffix else num_int

    return s  # Can't parse, return as-is


def get_lot_prefix(lot_raw: Optional[str]) -> Optional[str]:
    """Return the building prefix (A, B, H, I, 0, etc.) from a lot code."""
    if lot_raw is None:
        return None
    s = str(lot_raw).strip()
    m = re.match(r'^([A-Za-z]+)\d', s)
    if m:
        return m.group(1).upper()
    return None


# ─────────────────────────────────────────────────────────────
# 3. NUMERO NORMALIZATION
# ─────────────────────────────────────────────────────────────

def normalize_numero(numero) -> Optional[str]:
    """
    Normalize document number for grouping.
    GED stores as integer (248000) or string.
    Returns string with leading zeros stripped.
    """
    if numero is None:
        return None
    try:
        return str(int(numero))
    except (ValueError, TypeError):
        return str(numero).strip()


# ─────────────────────────────────────────────────────────────
# 4. EMETTEUR MAPPING
# ─────────────────────────────────────────────────────────────

def load_mapping(mapping_file: str) -> dict:
    """
    Load Mapping.xlsx (GED column → canonical name or 'Exception List').
    Returns dict: {ged_name_normalized: canonical_name}
    'Exception List' entries are preserved as-is — caller decides what to do.
    """
    path = Path(mapping_file)
    if not path.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_file}")

    df = pd.read_excel(mapping_file, header=0)
    df.columns = ["ged_name", "canonical_name"]
    df = df.dropna(subset=["ged_name"])

    mapping = {}
    for _, row in df.iterrows():
        ged = str(row["ged_name"]).strip()
        canonical = str(row["canonical_name"]).strip() if pd.notna(row["canonical_name"]) else "Exception List"
        mapping[ged] = canonical

    return mapping


def map_approver(raw_name: str, mapping: dict) -> str:
    """
    Map a raw GED approver name to its canonical name.
    Returns 'Exception List' if not found or explicitly mapped as such.
    """
    raw = str(raw_name).strip()
    return mapping.get(raw, raw)  # fallback: use raw name if not in mapping


def is_exception(canonical_name: str) -> bool:
    """Return True if this approver/emetteur should be excluded."""
    return canonical_name == "Exception List"


# ─────────────────────────────────────────────────────────────
# 5. NORMALIZE FULL DOCS DATAFRAME
# ─────────────────────────────────────────────────────────────

def normalize_docs(docs_df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Apply all normalizations to the docs DataFrame.
    Adds columns:
      - lot_normalized (numeric string)
      - lot_prefix (A/B/H/I/0...)
      - numero_normalized
      - emetteur_canonical
      - is_excluded
    """
    df = docs_df.copy()

    # Lot
    df["lot_normalized"] = df["lot"].apply(normalize_lot)
    df["lot_prefix"] = df["lot"].apply(get_lot_prefix)

    # Numero
    df["numero_normalized"] = df["numero"].apply(normalize_numero)

    # Emetteur canonical — map using Mapping.xlsx
    # In GED, EMETTEUR is a short code (API, AXI...).
    # The Mapping keys are full names like "0-AMO HQE".
    # We'll also store the raw emetteur and map it to canonical via lot+emetteur combo.
    # NOTE: The Mapping maps GED *approver column names* (not EMETTEUR values).
    # We'll handle emetteur mapping separately for routing.
    df["emetteur_canonical"] = df["emetteur"]  # will be updated in routing step

    # Clean indice
    df["indice"] = df["indice"].apply(lambda x: str(x).strip() if x is not None else None)

    # Ensure created_at is datetime
    # Find the date column (handles different encodings of 'Créé le')
    date_col = None
    for c in ["cree_le", "cr_e_le", "cr__e_le", "créé_le"]:
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        # Try to find by partial match
        for c in df.columns:
            if "cr" in c and "le" in c:
                date_col = c
                break
    if date_col:
        df["created_at"] = pd.to_datetime(df[date_col], errors="coerce")
    else:
        df["created_at"] = pd.NaT

    return df


def enrich_docs_with_sas(docs_df: pd.DataFrame, responses_df: pd.DataFrame) -> pd.DataFrame:
    """
    Join the SAS approver's response value onto the docs DataFrame.

    The GED has a '0-SAS' approver column (Bureau de Contrôle Safety Assurance).
    Its 'Réponse' sub-column contains values like 'VSO-SAS', 'VAO-SAS', 'REF', etc.
    We merge the best (non-null) SAS response per doc_id into docs_df['sas_reponse'].

    Priority: if a doc has multiple SAS response rows (two '0-SAS' columns exist in
    some GED exports), prefer the one containing VAO/VSO over an empty one.
    """
    df = docs_df.copy()

    # Filter to SAS approver rows only
    sas_mask = responses_df["approver_raw"].str.strip().str.upper().isin(["0-SAS"])
    sas_df = responses_df[sas_mask][["doc_id", "response_status_raw"]].copy()
    sas_df["response_status_raw"] = sas_df["response_status_raw"].apply(
        lambda v: str(v).strip() if v is not None else ""
    )

    def pick_best_sas(group):
        """Among multiple SAS rows, prefer one with VAO/VSO content."""
        vals = group["response_status_raw"].tolist()
        for v in vals:
            u = v.upper().replace(" ", "").replace("-", "")
            if "VAOSAS" in u or "VSOSAS" in u:
                return v
        # Fallback: first non-empty
        for v in vals:
            if v:
                return v
        return ""

    if sas_df.empty:
        df["sas_reponse"] = ""
    else:
        best = sas_df.groupby("doc_id").apply(pick_best_sas).rename("sas_reponse").reset_index()
        df = df.merge(best, on="doc_id", how="left")
        df["sas_reponse"] = df["sas_reponse"].fillna("")

    return df


def normalize_responses(responses_df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Apply all normalizations to the responses DataFrame.
    Adds:
      - approver_canonical
      - is_exception_approver
      - date_answered (actual date or None)
      - date_status_type (NOT_CALLED / PENDING_IN_DELAY / PENDING_LATE / ANSWERED)
      - status_clean (cleaned response status)
    """
    df = responses_df.copy()

    # Map approver names
    df["approver_canonical"] = df["approver_raw"].apply(
        lambda x: map_approver(x, mapping)
    )
    df["is_exception_approver"] = df["approver_canonical"].apply(is_exception)

    # Interpret date field
    date_interp = df["response_date_raw"].apply(interpret_date_field)
    df["date_answered"] = date_interp.apply(lambda x: x["date"])
    df["date_status_type"] = date_interp.apply(lambda x: x["date_status_type"])

    # Clean status
    df["status_clean"] = df["response_status_raw"].apply(clean_status)

    return df
