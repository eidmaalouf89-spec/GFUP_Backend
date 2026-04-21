"""
src/domain/gf_helpers.py
------------------------
Pure GF parsing and key-building helpers extracted from main.py.

Every function here is a pure helper: no globals, no file writes, no external state mutation.
"""

import json
import hashlib
from collections import defaultdict as _defaultdict

from domain.normalization import (
    normalize_numero_for_compare,
    normalize_indice_for_compare,
    normalize_title_for_compare,
    normalize_date_for_compare,
    normalize_status_for_compare,
)


def _build_input_signature(input_entries: list[dict]) -> str:
    """Build a stable hash of the concrete inputs that affected a run."""
    payload = json.dumps(input_entries, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _gf_row_stable_key(gf_row: dict) -> tuple:
    """Stable ordering for duplicate GF rows representing the same key."""
    return (
        normalize_title_for_compare(gf_row.get("titre", "")),
        normalize_date_for_compare(gf_row.get("date_diffusion")),
        normalize_status_for_compare(gf_row.get("gf_visa_global")),
        str(gf_row.get("document", "") or ""),
        str(gf_row.get("numero_normalized", "") or ""),
        str(gf_row.get("indice_normalized", "") or ""),
    )


def _sorted_family_doc_ids(family: dict) -> list[str]:
    """Stable ordering for family doc ids when the caller stops on the first eligible SAS hit."""
    return sorted(str(did) for did in family.get("all_doc_ids", set()) if did is not None)


def _parse_gf_sheet_data(ws, struct: dict) -> dict:
    """
    Part 1 / Patch E: Parse a GF sheet's data rows.

    Returns {(numero_clean, indice_clean): [row_dict, row_dict, ...]}
    — a LIST per key to handle duplicate rows correctly.

    Patch E additions:
      - gf_visa_global: raw value from VISA GLOBAL column (col 15)
      - gf_has_sas_ref: True if any approver column contains "SAS" + "REF"
        (or any "SAS" variant used as a status in the approbateurs section)
    """
    col_map    = struct.get("col_map", {})
    data_start = struct.get("data_start_row", 10)
    approvers  = struct.get("approvers", [])   # [{name, date_col, num_col, statut_col}, ...]

    num_col = col_map.get("numero", 7)
    ind_col = col_map.get("indice", 8)
    doc_col = col_map.get("document", 0)
    tit_col = col_map.get("titre", 1)
    dat_col = col_map.get("date_diffusion", 2)
    lot_col = col_map.get("lot", 3)
    typ_col = col_map.get("type_doc", 4)
    vg_col  = col_map.get("visa_global", 15)   # Patch E

    # Build set of all approver data columns (num + statut) for SAS scan
    approver_data_cols: set = set()
    for ap in approvers:
        approver_data_cols.add(ap.get("num_col", 999))
        approver_data_cols.add(ap.get("statut_col", 999))
    # Also scan all columns from approbateurs start onwards (robust fallback)
    app_start = col_map.get("approbateurs", 16)

    gf_docs: dict = _defaultdict(list)
    max_row = ws.max_row or 5000
    for row in ws.iter_rows(min_row=data_start, max_row=max_row, values_only=True):
        if not row or row[0] is None:
            continue
        if str(row[0]).strip().upper() in ("", "DOCUMENT", "NONE"):
            continue

        numero_raw = row[num_col] if len(row) > num_col else None
        if numero_raw is None:
            continue

        numero_clean = normalize_numero_for_compare(numero_raw)
        indice_raw   = row[ind_col] if len(row) > ind_col else None
        indice_clean = normalize_indice_for_compare(indice_raw)

        # Patch E: visa_global and gf_has_sas_ref
        visa_global_raw = row[vg_col] if len(row) > vg_col else None

        # Scan all approver-section columns (app_start onwards) for SAS text
        gf_has_sas_ref = False
        for col_idx in range(app_start, len(row)):
            val = row[col_idx]
            if val is None:
                continue
            val_str = str(val).lower().replace("\n", " ").strip()
            if "sas" in val_str and "ref" in val_str:
                gf_has_sas_ref = True
                break

        key = (numero_clean, indice_clean)
        gf_docs[key].append({
            "document":          row[doc_col] if len(row) > doc_col else None,
            "titre":             row[tit_col] if len(row) > tit_col else None,
            "date_diffusion":    row[dat_col] if len(row) > dat_col else None,
            "lot":               row[lot_col] if len(row) > lot_col else None,
            "type_doc":          row[typ_col] if len(row) > typ_col else None,
            "numero":            numero_raw,
            "indice":            indice_raw,
            "numero_normalized": numero_clean,
            "indice_normalized": indice_clean,
            # Patch E
            "gf_visa_global":  visa_global_raw,
            "gf_has_sas_ref":  gf_has_sas_ref,
        })
    for key, rows in gf_docs.items():
        gf_docs[key] = sorted(rows, key=_gf_row_stable_key)
    return dict(gf_docs)
