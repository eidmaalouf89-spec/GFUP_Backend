"""
normalize.py
------------
All normalization logic:
  - Lot number normalization (A041 → 41, I041 → 41)
  - Status cleaning (.VAO → VAO)
  - Date réponse interpretation (text → status enum)
  - Approver name mapping (hardcoded)
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


def _extract_date_limite(raw: str):
    """Extract deadline date from parenthesized YYYY/MM/DD in GED date field."""
    import re
    import datetime as _dt
    m = re.search(r'\((\d{4})/(\d{2})/(\d{2})\)', raw)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


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
      - 'En attente visa (YYYY/MM/DD)' → PENDING_IN_DELAY (first request)
      - 'Rappel : En attente visa (YYYY/MM/DD)' → PENDING_LATE (reminder sent)

    The date in parentheses is the date_limite (deadline).

    Returns dict: {date: ..., date_status_type: ..., date_limite: date|None}
    """
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return {"date": None, "date_status_type": "NOT_CALLED", "date_limite": None}

    if isinstance(raw, str):
        lower = raw.strip().lower()

        # Extract date_limite from parentheses: (YYYY/MM/DD)
        dl = _extract_date_limite(raw)

        # "Rappel" prefix means a reminder was sent — indicates lateness
        if lower.startswith("rappel"):
            return {"date": None, "date_status_type": "PENDING_LATE", "date_limite": dl}

        # "En attente" without "Rappel" — first request, still in delay window
        if "en attente" in lower:
            return {"date": None, "date_status_type": "PENDING_IN_DELAY", "date_limite": dl}

        # Non-matching text — treat as unknown pending
        return {"date": None, "date_status_type": "PENDING_IN_DELAY", "date_limite": dl}

    # datetime or date object → ANSWERED
    import datetime as _dt
    if isinstance(raw, (_dt.datetime, _dt.date)):
        return {"date": raw, "date_status_type": "ANSWERED", "date_limite": None}

    # Fallback
    return {"date": None, "date_status_type": "NOT_CALLED", "date_limite": None}


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

# ─────────────────────────────────────────────────────────────
# HARDCODED APPROVER MAPPING — P17&CO Tranche 2
# Replaces Mapping.xlsx (2026-04-20).
# Maps every raw GED approver column header → canonical name.
# Per-building prefixes (0-, A-, B-, H-) all collapse to the same canonical.
# 'Exception List' entries are lot-specific columns that are not consultants.
# ─────────────────────────────────────────────────────────────
_GED_APPROVER_MAPPING: dict[str, str] = {
    # ── 0- prefix (global / no building) ────────────────────
    "0-AMO HQE":              "AMO HQE",
    "0-ARCHITECTE":           "ARCHITECTE",
    "0-BET Acoustique":       "BET Acoustique",
    "0-BET Ascenseur":        "BET Ascenseur",
    "0-BET CVC":              "BET CVC",
    "0-BET Electricité":      "BET Electricité",
    "0-BET EV":               "BET EV",
    "0-BET Façade":           "BET Façade",
    "0-BET Géotech":          "Exception List",
    "0-BET Plomberie":        "BET Plomberie",
    "0-BET POL":              "BET POL",
    "0-BET SPK":              "BET SPK",
    "0-BET Structure":        "BET Structure",
    "0-BET Synthèse":         "Exception List",
    "0-BET VRD":              "BET VRD",
    "0-BIM Manager":          "Exception List",
    "0-Bureau de Contrôle":   "Bureau de Contrôle",
    "0-CSPS":                 "Exception List",
    "0-Maître d'Oeuvre EXE":  "Maître d'Oeuvre EXE",
    "0-SAS":                  "0-SAS",   # conformity gate — kept as-is, excluded by normalize_responses
    # ── A- prefix (building A) ───────────────────────────────
    "A-AMO HQE":              "AMO HQE",
    "A-ARCHITECTE":           "ARCHITECTE",
    "A-BET Acoustique":       "BET Acoustique",
    "A-BET Ascenseur":        "BET Ascenseur",
    "A-BET CVC":              "BET CVC",
    "A-BET Electricité":      "BET Electricité",
    "A-BET Façade":           "BET Façade",
    "A-BET Plomberie":        "BET Plomberie",
    "A-BET Structure":        "BET Structure",
    "A-Maître d'Oeuvre EXE":  "Maître d'Oeuvre EXE",
    # ── B- prefix (building B) ───────────────────────────────
    "B-AMO HQE":              "AMO HQE",
    "B-ARCHITECTE":           "ARCHITECTE",
    "B-BET Acoustique":       "BET Acoustique",
    "B-BET Ascenseur":        "BET Ascenseur",
    "B-BET CVC":              "BET CVC",
    "B-BET Electricité":      "BET Electricité",
    "B-BET Façade":           "BET Façade",
    "B-BET Plomberie":        "BET Plomberie",
    "B-BET Structure":        "BET Structure",
    "B-Maître d'Oeuvre EXE":  "Maître d'Oeuvre EXE",
    # ── H- prefix (building H) ───────────────────────────────
    "H-AMO HQE":              "AMO HQE",
    "H-ARCHITECTE":           "ARCHITECTE",
    "H-BET Acoustique":       "BET Acoustique",
    "H-BET Ascenseur":        "BET Ascenseur",
    "H-BET CVC":              "BET CVC",
    "H-BET Electricité":      "BET Electricité",
    "H-BET Façade":           "BET Façade",
    "H-BET Plomberie":        "BET Plomberie",
    "H-BET Structure":        "BET Structure",
    "H-Maître d'Oeuvre EXE":  "Maître d'Oeuvre EXE",
    # ── Exception List — lot/trade-specific GED columns ─────
    "A05-MNS EXT":                    "Exception List",
    "A06-REVET FAC":                  "Exception List",
    "A07-CSQ PREFA":                  "Exception List",
    "A08-MR":                         "Exception List",
    "A22-SDB Préfa":                  "Exception List",
    "A31-33-34-ELEC":                 "Exception List",
    "A41-CVC":                        "Exception List",
    "A42 PLB":                        "Exception List",
    "B05-MNS EXT":                    "Exception List",
    "B06 - REVÊTEMENT EXT":           "Exception List",
    "B13 - METALLERIE SERRURERIE":    "Exception List",
    "B31-33-34-CFO-CFA":              "Exception List",
    "B35-GTB":                        "Exception List",
    "B41-CVC":                        "Exception List",
    "B42 PLB":                        "Exception List",
    "H05-MNS EXT":                    "Exception List",
    "H06-REVET FAC":                  "Exception List",
    "H07-CSQ PREFA":                  "Exception List",
    "H08-MUR RIDEAUX":                "Exception List",
    "H31-33-34-CFO-CFA":              "Exception List",
    "H35-GTB":                        "Exception List",
    "H41-CVC":                        "Exception List",
    "H42 PLB":                        "Exception List",
    "H51-ASC":                        "Exception List",
    "00-TCE":                         "Exception List",
    "01-TERRASSEMENTS":               "Exception List",
    "02-FONDATIONS SPECIALES":        "Exception List",
    "03-GOE":                         "Exception List",
    "08-MURS RIDEAUX":                "Exception List",
    "35-GTB":                         "Exception List",
    "41-CVC":                         "Exception List",
    "42-PLB":                         "Exception List",
    "Sollicitation supplémentaire":   "Exception List",
}


def load_mapping(mapping_file: str = "") -> dict:
    """Return the hardcoded GED approver mapping for P17&CO Tranche 2.

    The mapping_file argument is accepted but ignored — the mapping is now
    fully hardcoded and no longer requires Mapping.xlsx on disk.
    """
    return dict(_GED_APPROVER_MAPPING)


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

    # SAS is a conformity gate, not a consultant — must never merge with MOEX
    df.loc[df["approver_raw"] == "0-SAS", "approver_canonical"] = "0-SAS"
    df.loc[df["approver_raw"] == "0-SAS", "is_exception_approver"] = True

    # Interpret date field (includes date_limite extraction)
    date_interp = df["response_date_raw"].apply(interpret_date_field)
    df["date_answered"] = date_interp.apply(lambda x: x["date"])
    df["date_status_type"] = date_interp.apply(lambda x: x["date_status_type"])
    df["date_limite"] = date_interp.apply(lambda x: x.get("date_limite"))

    # Clean status
    df["status_clean"] = df["response_status_raw"].apply(clean_status)

    return df
