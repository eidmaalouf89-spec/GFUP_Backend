"""
src/domain/family_builder.py
----------------------------
Pure GED family building and new-submittal analysis helpers extracted from main.py.

Every function here is a pure helper: no globals, no file writes, no external state mutation.
"""

import datetime as _dt

import pandas as pd

from domain.normalization import (
    normalize_numero_for_compare,
    normalize_indice_for_compare,
    normalize_title_for_compare,
    title_similarity,
)
from domain.classification import _classify_new_submittal_status


def _build_ged_families(
    ged_sheet_docs: pd.DataFrame,
    gf_numeros_in_sheet: set = None,
) -> list:
    """
    Part 2: Group GED rows into document FAMILIES for comparison against GF.

    A FAMILY = a set of GED rows that represent ONE logical document.

    Algorithm (two-pass):
      Pass 1 — Group by (numero_normalized).
        All GED rows with the same numero are the same logical document,
        regardless of indice.  The family representative is the row with
        the dernier indice (picked deterministically: last alpha order).

      Pass 2 — Merge proto-families with different numeros that share
        (lot_normalized, type_de_doc) AND title_similarity >= 0.75.
        This catches cases where GED submitted the same document under
        slightly different numbers.

    Returns: list of family dicts:
      {
        "family_id": str,
        "numero"   : str,    <- representative numero (may be list for merged)
        "indice"   : str,
        "title"    : str,    <- representative title (best normalized title)
        "date"     : any,
        "doc_code" : str,
        "all_numeros": set[str],
        "all_keys" : set[(num, ind)],
        "member_count": int,
      }
    """
    if ged_sheet_docs.empty:
        return []

    # ── Pass 1: group by numero_normalized ───────────────────────────────────
    proto_families: dict = {}  # num_clean -> {rows: [...], best_row: ...}

    for _, row in ged_sheet_docs.iterrows():
        num = normalize_numero_for_compare(
            row.get("numero_normalized") or row.get("numero")
        )
        ind     = normalize_indice_for_compare(row.get("indice"))
        title   = str(row.get("libelle_du_document", "") or "")
        date    = row.get("date_diffusion") or row.get("cree_le")
        doc_code = str(row.get("libelle_du_document", "") or "")[:80]
        doc_id  = str(row.get("doc_id", "") or "")

        if num not in proto_families:
            proto_families[num] = {
                "best_row":    {"num": num, "ind": ind, "title": title, "date": date, "doc_code": doc_code},
                "all_keys":    set(),
                "all_doc_ids": set(),   # <- Patch E: track doc_ids for SAS lookup
                "member_count": 0,
                "lot":  str(row.get("lot_normalized", "") or ""),
                "type_doc": str(row.get("type_de_doc", "") or ""),
            }
        pf = proto_families[num]
        pf["all_keys"].add((num, ind))
        pf["member_count"] += 1
        if doc_id:
            pf["all_doc_ids"].add(doc_id)

        # Choose best representative: prefer longer, more descriptive title
        cur_norm = normalize_title_for_compare(pf["best_row"]["title"])
        new_norm = normalize_title_for_compare(title)
        if len(new_norm) > len(cur_norm):
            pf["best_row"] = {"num": num, "ind": ind, "title": title, "date": date, "doc_code": doc_code}

    # ── Pass 2: merge proto-families with same (lot, type_doc) + title_sim >= 0.75
    # CRITICAL CONSTRAINT: only merge numeros that have NO exact GF match.
    # Rows whose numero IS in GF should each remain their own family so they can
    # independently match their own GF row. Merging GF-present numeros would
    # cause their GF rows to become "unmatched" -> false MISSING_IN_GED_HISTORICAL.
    gf_nums = gf_numeros_in_sheet or set()

    # Union-Find approach for merging
    parent = {num: num for num in proto_families}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    nums_list = list(proto_families.keys())
    for i in range(len(nums_list)):
        for j in range(i + 1, len(nums_list)):
            na, nb = nums_list[i], nums_list[j]
            # Only merge if NEITHER numero has a direct GF match.
            # If either is in GF, it must match its own GF row independently.
            if na in gf_nums or nb in gf_nums:
                continue
            pfa, pfb = proto_families[na], proto_families[nb]
            # Same (lot, type_doc) is prerequisite
            if pfa["lot"] != pfb["lot"] or pfa["type_doc"] != pfb["type_doc"]:
                continue
            # Check title similarity
            sim = title_similarity(pfa["best_row"]["title"], pfb["best_row"]["title"])
            if sim >= 0.75:
                union(na, nb)

    # ── Build final families from merged groups ───────────────────────────────
    groups: dict = {}  # root -> merged family dict
    for num in nums_list:
        root = find(num)
        if root not in groups:
            groups[root] = {
                "family_id":   root,
                "all_numeros": set(),
                "all_keys":    set(),
                "all_doc_ids": set(),   # Patch E
                "member_count": 0,
                "best_row": proto_families[root]["best_row"],
                "lot":      proto_families[root]["lot"],
                "type_doc": proto_families[root]["type_doc"],
            }
        g = groups[root]
        g["all_numeros"].add(num)
        g["all_keys"].update(proto_families[num]["all_keys"])
        g["all_doc_ids"].update(proto_families[num]["all_doc_ids"])   # Patch E
        g["member_count"] += proto_families[num]["member_count"]

        # Keep best representative (longest normalized title)
        cur_n  = normalize_title_for_compare(g["best_row"]["title"])
        cand_n = normalize_title_for_compare(proto_families[num]["best_row"]["title"])
        if len(cand_n) > len(cur_n):
            g["best_row"] = proto_families[num]["best_row"]

    # ── Convert to list of family dicts ──────────────────────────────────────
    families = []
    for root, g in groups.items():
        br = g["best_row"]
        families.append({
            "family_id":   g["family_id"],
            "numero":      br["num"],
            "indice":      br["ind"],
            "title":       br["title"],
            "date":        br["date"],
            "doc_code":    br["doc_code"],
            "all_numeros": g["all_numeros"],
            "all_keys":    g["all_keys"],
            "all_doc_ids": g["all_doc_ids"],   # Patch E
            "member_count": g["member_count"],
            "lot":      g["lot"],
            "type_doc": g["type_doc"],
        })

    return families


def _build_new_submittal_analysis(
    dernier_df_for_gf:    pd.DataFrame,
    dernier_df_excluded:  pd.DataFrame,
    discrepancies:        list,
    sas_lookup:           dict,
    data_date:            _dt.date,
) -> list:
    """
    Build the new-submittal classification for every current GED family.

    Returns a list of analysis record dicts (one per doc).

    Algorithm:
      1. Build `absent_keys` = set of (sheet, numero, indice) for all
         MISSING_IN_GF_* discrepancies.  Every doc NOT in this set is
         ALREADY_IN_GF.
      2. For each valid current GED doc (dernier_df_for_gf):
         - check absence -> classify via _classify_new_submittal_status
      3. For each config-excluded doc (dernier_df_excluded):
         - mark as EXCLUDED
    """
    # ── Step 1: build absent set from post-reconciliation discrepancies ───────
    # Only MISSING_IN_GF_* records signal genuine absence from original GF.
    # SHEET_MISMATCH, TITRE_MISMATCH etc. mean the doc IS in GF (just mismatched).
    absent_keys: set = set()
    for d in discrepancies:
        if str(d.get("flag_type", "")).startswith("MISSING_IN_GF"):
            absent_keys.add((
                str(d.get("sheet_name", "")),
                str(d.get("numero",     "")),
                str(d.get("indice",     "")),
            ))

    rows = []

    # ── Step 2: valid current GED docs ───────────────────────────────────────
    for _, doc in dernier_df_for_gf.iterrows():
        doc_id   = str(doc.get("doc_id", "") or "")
        sheet    = str(doc.get("gf_sheet_name", "") or "")
        num      = str(doc.get("numero_normalized", "") or "")
        ind      = str(doc.get("indice", "") or "")
        emetteur = str(doc.get("emetteur", "") or "")
        lot      = str(doc.get("lot_normalized", "") or "")
        titre    = str(doc.get("libelle_du_document", "") or "")[:80]
        type_doc = str(doc.get("type_de_doc", "") or "")

        is_absent = (sheet, num, ind) in absent_keys

        status, days_diff, rationale = _classify_new_submittal_status(
            doc_id, is_absent, sas_lookup, data_date
        )

        sas_info = sas_lookup.get(doc_id, {})
        rows.append({
            "Sheet target":          sheet,
            "Emetteur":              emetteur,
            "Lot":                   lot,
            "Numero":                num,
            "Indice":                ind,
            "Titre":                 titre,
            "SAS status type":       sas_info.get("sas_status_type", "") if sas_info else "",
            "SAS result":            sas_info.get("sas_result", "") if sas_info else "",
            "SAS date":              str(sas_info.get("sas_date", "") or "") if sas_info else "",
            "data_date":             str(data_date or ""),
            "days_from_data_date":   days_diff,
            "exists_in_original_gf": "no" if is_absent else "yes",
            "new_submittal_status":  status,
            "rationale":             rationale,
        })

    # ── Step 3: excluded docs -> EXCLUDED ─────────────────────────────────────
    for _, doc in dernier_df_excluded.iterrows():
        doc_id   = str(doc.get("doc_id", "") or "")
        sheet    = str(doc.get("gf_sheet_name", "") or doc.get("exclusion_reason", ""))
        num      = str(doc.get("numero_normalized", "") or "")
        ind      = str(doc.get("indice", "") or "")
        emetteur = str(doc.get("emetteur", "") or "")
        lot      = str(doc.get("lot_normalized", "") or "")
        titre    = str(doc.get("libelle_du_document", "") or "")[:80]
        type_doc = str(doc.get("type_de_doc", "") or "")
        reason   = str(doc.get("exclusion_reason", "config exclusion") or "config exclusion")

        sas_info = sas_lookup.get(doc_id, {})
        sas_date  = sas_info.get("sas_date")  if sas_info else None
        days_diff = None
        if sas_date and data_date:
            try:
                days_diff = (data_date - sas_date).days
            except Exception:
                pass

        rows.append({
            "Sheet target":          sheet,
            "Emetteur":              emetteur,
            "Lot":                   lot,
            "Numero":                num,
            "Indice":                ind,
            "Titre":                 titre,
            "SAS status type":       sas_info.get("sas_status_type", "") if sas_info else "",
            "SAS result":            sas_info.get("sas_result", "") if sas_info else "",
            "SAS date":              str(sas_info.get("sas_date", "") or "") if sas_info else "",
            "data_date":             str(data_date or ""),
            "days_from_data_date":   days_diff,
            "exists_in_original_gf": "?",
            "new_submittal_status":  "EXCLUDED",
            "rationale":             f"Config-excluded: {reason}",
        })

    return rows
