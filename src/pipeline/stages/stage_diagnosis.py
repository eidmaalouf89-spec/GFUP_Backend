"""
Stage 9: Diagnosis outputs and debug artifacts.

Writes missing diagnosis outputs, insert log, new submittal analysis,
and additional debug artifacts.
"""

import datetime as _dt
import pandas as pd
from pipeline.compute import _write_missing_in_ged_diagnosis, _write_missing_in_gf_diagnosis
from writer import write_insert_log, write_new_submittal_analysis
from domain.family_builder import _build_new_submittal_analysis
from debug_writer import write_all_debug
from pipeline.utils import _safe_console_print


def stage_diagnosis(ctx, log):
    """
    Diagnosis outputs and debug artifacts stage.

    Reads from ctx:
        - discrepancies, dernier_df_for_gf, wf_engine, gf_sas_lookup, data_date
        - dernier_df, versioned_df
        - OUTPUT_MISSING_GED_DIAGNOSIS, OUTPUT_MISSING_GED_TRUE
        - OUTPUT_MISSING_GF_DIAGNOSIS, OUTPUT_MISSING_GF_TRUE
        - DEBUG_DIR, OUTPUT_INSERT_LOG, OUTPUT_NEW_SUBMITTAL_ANALYSIS
        - OUTPUT_NEW_SUBMITTAL_SUMMARY

    Writes to ctx:
        - (No new ctx writes for this stage — terminal output stage)
    """
    discrepancies = ctx.discrepancies
    dernier_df_for_gf = ctx.dernier_df_for_gf
    wf_engine = ctx.wf_engine
    gf_sas_lookup = ctx.gf_sas_lookup or {}
    data_date = ctx.data_date
    dernier_df = ctx.dernier_df
    versioned_df = ctx.versioned_df

    OUTPUT_MISSING_GED_DIAGNOSIS = ctx.OUTPUT_MISSING_GED_DIAGNOSIS
    OUTPUT_MISSING_GED_TRUE = ctx.OUTPUT_MISSING_GED_TRUE
    OUTPUT_MISSING_GF_DIAGNOSIS = ctx.OUTPUT_MISSING_GF_DIAGNOSIS
    OUTPUT_MISSING_GF_TRUE = ctx.OUTPUT_MISSING_GF_TRUE
    DEBUG_DIR = ctx.DEBUG_DIR
    OUTPUT_INSERT_LOG = ctx.OUTPUT_INSERT_LOG
    OUTPUT_NEW_SUBMITTAL_ANALYSIS = ctx.OUTPUT_NEW_SUBMITTAL_ANALYSIS
    OUTPUT_NEW_SUBMITTAL_SUMMARY = ctx.OUTPUT_NEW_SUBMITTAL_SUMMARY

    # ── Patch E: Diagnosis outputs ────────────────────────────
    log("Writing MISSING_IN_GED_DIAGNOSIS.xlsx and MISSING_IN_GED_TRUE_ONLY.xlsx...")
    _write_missing_in_ged_diagnosis(
        str(OUTPUT_MISSING_GED_DIAGNOSIS),
        str(OUTPUT_MISSING_GED_TRUE),
        str(DEBUG_DIR / "missing_in_ged_summary.xlsx"),
        discrepancies,
    )
    log(f"  → {OUTPUT_MISSING_GED_DIAGNOSIS}")
    log(f"  → {OUTPUT_MISSING_GED_TRUE}")

    log("Writing MISSING_IN_GF_DIAGNOSIS.xlsx and MISSING_IN_GF_TRUE_ONLY.xlsx...")
    _write_missing_in_gf_diagnosis(
        str(OUTPUT_MISSING_GF_DIAGNOSIS),
        str(OUTPUT_MISSING_GF_TRUE),
        str(DEBUG_DIR / "missing_in_gf_summary.xlsx"),
        discrepancies,
    )
    log(f"  → {OUTPUT_MISSING_GF_DIAGNOSIS}")
    log(f"  → {OUTPUT_MISSING_GF_TRUE}")

    # ── INSERT LOG: newly inserted rows in CLEAN GF ───────────────────────────
    # "Inserted" = MISSING_IN_GF_TRUE after reconciliation.
    # These are GED docs confirmed absent from the original GF and now written
    # into CLEAN GF as current DI rows.  All other MISSING subtypes
    # (PENDING_SAS, RECENT_REFUSAL, etc.) are explicitly excluded.
    #
    # Variables in scope: discrepancies, dernier_df_for_gf, wf_engine, gf_sas_lookup
    log("Building INSERT LOG...")

    # Index dernier_df_for_gf by (sheet, numero_normalized, indice) for O(1) join
    _gf_key_index: dict = {}
    for _, _dr in dernier_df_for_gf.iterrows():
        _k = (
            str(_dr.get("gf_sheet_name", "") or ""),
            str(_dr.get("numero_normalized", "") or ""),
            str(_dr.get("indice", "") or ""),
        )
        if _k not in _gf_key_index:
            _gf_key_index[_k] = _dr

    insert_log: list = []
    for _d in discrepancies:
        if _d.get("flag_type") != "MISSING_IN_GF_TRUE":
            continue

        _sheet = str(_d.get("sheet_name", "") or "")
        _num   = str(_d.get("numero", "") or "")
        _ind   = str(_d.get("indice", "") or "")

        # Join with GED row (doc metadata)
        _doc_row = _gf_key_index.get((_sheet, _num, _ind))
        _doc_id  = str(_doc_row.get("doc_id", "") or "") if _doc_row is not None else ""
        _emetteur = str(_doc_row.get("emetteur", "") or "") if _doc_row is not None else ""
        _date_reception = _doc_row.get("created_at") if _doc_row is not None else None

        # DATE CONTRACTUELLE: Case B if SAS passed, else Case A
        _sas_entry  = gf_sas_lookup.get(_doc_id, {})
        _sas_result = str(_sas_entry.get("sas_result") or "")
        _sas_passed = _sas_result in ("VSO-SAS", "VAO-SAS", "VSO", "VAO")
        _sas_date   = _sas_entry.get("sas_date") if _sas_passed else None
        _base_date  = _sas_date if _sas_date is not None else _date_reception
        _date_contract = None
        if _base_date is not None:
            try:
                _date_contract = pd.to_datetime(_base_date) + _dt.timedelta(days=15)
            except Exception:
                pass

        # VISA GLOBAL + Date réel de visa — derived from same MOEX entry
        _visa_global    = None
        _date_reel_visa = None
        if _doc_id and wf_engine is not None:
            _visa_global, _date_reel_visa = wf_engine.compute_visa_global_with_date(_doc_id)

        insert_log.append({
            "Sheet":             _sheet,
            "Emetteur":          _emetteur,
            "Lot":               str(_d.get("gfi_lot", "") or ""),
            "Numero":            _num,
            "Indice":            _ind,
            "Titre":             str(_d.get("gfi_titre", "") or ""),
            "Type Doc":          str(_d.get("gfi_type_doc", "") or ""),
            "Date réception":    _date_reception,
            "Date contract":     _date_contract,
            "Date réel de visa": _date_reel_visa,
            "VISA Global":       _visa_global or "",
            "Reason":            "MISSING_IN_GF_TRUE",
            "Confidence":        "HIGH",
        })

    log(f"  INSERT LOG: {len(insert_log)} newly inserted rows")
    write_insert_log(str(OUTPUT_INSERT_LOG), insert_log)
    log(f"  → {OUTPUT_INSERT_LOG}")

    # ── NEW SUBMITTAL ANALYSIS ───────────────────────────────────────────────
    log("Building new submittal analysis...")
    dernier_df_excluded_for_ns = dernier_df[dernier_df["is_excluded_config"]].copy()
    ns_rows = _build_new_submittal_analysis(
        dernier_df_for_gf=dernier_df_for_gf,
        dernier_df_excluded=dernier_df_excluded_for_ns,
        discrepancies=discrepancies,
        sas_lookup=gf_sas_lookup,
        data_date=data_date,
    )
    log(f"  New submittal analysis: {len(ns_rows)} docs analysed")
    _ns_by_status = {}
    for _r in ns_rows:
        _s = _r.get("new_submittal_status", "?")
        _ns_by_status[_s] = _ns_by_status.get(_s, 0) + 1
    for _s, _c in sorted(_ns_by_status.items(), key=lambda x: -x[1]):
        log(f"    {_s}: {_c}")
    write_new_submittal_analysis(
        analysis_path=str(OUTPUT_NEW_SUBMITTAL_ANALYSIS),
        summary_path=str(OUTPUT_NEW_SUBMITTAL_SUMMARY),
        rows=ns_rows,
    )
    log(f"  → {OUTPUT_NEW_SUBMITTAL_ANALYSIS}")
    log(f"  → {OUTPUT_NEW_SUBMITTAL_SUMMARY}")

    # Write additional debug artifacts
    log("Writing debug artifacts...")
    write_all_debug(
        debug_dir=str(DEBUG_DIR),
        versioned_df=versioned_df,
        discrepancies=discrepancies,
    )
    log(f"  → debug/coarse_groups.xlsx")
    log(f"  → debug/family_clusters.xlsx")
    log(f"  → debug/lifecycle_resolution.xlsx")
    log(f"  → debug/discrepancy_sample.xlsx")
