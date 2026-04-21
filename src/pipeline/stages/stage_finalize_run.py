"""
Stage 10: Run finalization and artifact registration.

Registers artifacts in run memory, finalizes the run, and returns summary dict.
This is the terminal stage that RETURNS the result dict.
"""

import json
from pathlib import Path
from run_memory import (
    sha256_file as _sha256_art,
    copy_artifact_to_run_dir,
    register_run_artifact,
    mark_run_current,
    update_run_metadata,
    finalize_run_success,
)
from pipeline.utils import _safe_console_print


def stage_finalize_run(ctx, log):
    """
    Run finalization stage. Registers artifacts and returns summary dict.

    Reads from ctx:
        - _run_number, _run_dir, _arts_registered, _RUN_CONTROL_CONTEXT
        - RUN_MEMORY_DB, RUN_MEMORY_CORE_VERSION, REPORT_MEMORY_DB
        - OUTPUT_GF, OUTPUT_DISCREPANCY, OUTPUT_DISCREPANCY_REVIEW, OUTPUT_ANOMALY
        - OUTPUT_AUTO_RESOLUTION, OUTPUT_IGNORED, OUTPUT_INSERT_LOG
        - OUTPUT_RECONCILIATION_LOG, OUTPUT_MISSING_GED_DIAGNOSIS, OUTPUT_MISSING_GED_TRUE
        - OUTPUT_MISSING_GF_DIAGNOSIS, OUTPUT_MISSING_GF_TRUE
        - OUTPUT_NEW_SUBMITTAL_ANALYSIS, OUTPUT_CONSULTANT_REPORTS_WB
        - CONSULTANT_MATCH_REPORT, OUTPUT_GF_TEAM_VERSION, OUTPUT_GF_STAGE1, OUTPUT_GF_STAGE2
        - OUTPUT_SUSPICIOUS_ROWS, OUTPUT_RECONCILIATION_SUMMARY, OUTPUT_NEW_SUBMITTAL_SUMMARY
        - DEBUG_DIR, OUTPUT_DIR
        - docs_df, responses_df, dernier_df_for_gf, ancien_df, discrepancies
        - persisted_df, total, dernier_count, anomaly_count, ok_count
        - ambiguous_count, unrouted, mismatch_count, disc_review, disc_cosmetic
        - recon_log, mid_before, mid_after, mif_before, mif_after

    Returns:
        - The result summary dict (not written to ctx)
    """
    _run_number = ctx._run_number
    _run_dir = ctx._run_dir
    _arts_registered = ctx._arts_registered if hasattr(ctx, '_arts_registered') else 0
    _RUN_CONTROL_CONTEXT = ctx._RUN_CONTROL_CONTEXT

    RUN_MEMORY_DB = ctx.RUN_MEMORY_DB
    RUN_MEMORY_CORE_VERSION = ctx.RUN_MEMORY_CORE_VERSION
    REPORT_MEMORY_DB = ctx.REPORT_MEMORY_DB

    OUTPUT_GF = ctx.OUTPUT_GF
    OUTPUT_DISCREPANCY = ctx.OUTPUT_DISCREPANCY
    OUTPUT_DISCREPANCY_REVIEW = ctx.OUTPUT_DISCREPANCY_REVIEW
    OUTPUT_ANOMALY = ctx.OUTPUT_ANOMALY
    OUTPUT_AUTO_RESOLUTION = ctx.OUTPUT_AUTO_RESOLUTION
    OUTPUT_IGNORED = ctx.OUTPUT_IGNORED
    OUTPUT_INSERT_LOG = ctx.OUTPUT_INSERT_LOG
    OUTPUT_RECONCILIATION_LOG = ctx.OUTPUT_RECONCILIATION_LOG
    OUTPUT_MISSING_GED_DIAGNOSIS = ctx.OUTPUT_MISSING_GED_DIAGNOSIS
    OUTPUT_MISSING_GED_TRUE = ctx.OUTPUT_MISSING_GED_TRUE
    OUTPUT_MISSING_GF_DIAGNOSIS = ctx.OUTPUT_MISSING_GF_DIAGNOSIS
    OUTPUT_MISSING_GF_TRUE = ctx.OUTPUT_MISSING_GF_TRUE
    OUTPUT_NEW_SUBMITTAL_ANALYSIS = ctx.OUTPUT_NEW_SUBMITTAL_ANALYSIS
    OUTPUT_CONSULTANT_REPORTS_WB = ctx.OUTPUT_CONSULTANT_REPORTS_WB
    CONSULTANT_MATCH_REPORT = ctx.CONSULTANT_MATCH_REPORT
    OUTPUT_GF_TEAM_VERSION = ctx.OUTPUT_GF_TEAM_VERSION
    OUTPUT_GF_STAGE1 = ctx.OUTPUT_GF_STAGE1
    OUTPUT_GF_STAGE2 = ctx.OUTPUT_GF_STAGE2
    OUTPUT_SUSPICIOUS_ROWS = ctx.OUTPUT_SUSPICIOUS_ROWS
    OUTPUT_RECONCILIATION_SUMMARY = ctx.OUTPUT_RECONCILIATION_SUMMARY
    OUTPUT_NEW_SUBMITTAL_SUMMARY = ctx.OUTPUT_NEW_SUBMITTAL_SUMMARY
    DEBUG_DIR = ctx.DEBUG_DIR
    OUTPUT_DIR = ctx.OUTPUT_DIR

    docs_df = ctx.docs_df
    responses_df = ctx.responses_df
    dernier_df_for_gf = ctx.dernier_df_for_gf
    ancien_df = ctx.ancien_df
    discrepancies = ctx.discrepancies
    persisted_df = ctx.persisted_df

    total = ctx.total
    dernier_count = ctx.dernier_count
    anomaly_count = ctx.anomaly_count
    ok_count = ctx.ok_count
    ambiguous_count = ctx.ambiguous_count
    unrouted = ctx.unrouted
    mismatch_count = ctx.mismatch_count
    disc_review = ctx.disc_review
    disc_cosmetic = ctx.disc_cosmetic
    recon_log = ctx.recon_log
    mid_before = ctx.mid_before
    mid_after = ctx.mid_after
    mif_before = ctx.mif_before
    mif_after = ctx.mif_after

    # ── RUN HISTORY: copy artifacts + register ───────────────
    if _run_number is not None and _run_dir is not None:
        try:
            # Map: (source_path, artifact_type, is_debug)
            _artifacts_to_register = [
                # Primary outputs
                (OUTPUT_GF,                    "FINAL_GF",                    False),
                (OUTPUT_DISCREPANCY,           "DISCREPANCY_REPORT",          False),
                (OUTPUT_DISCREPANCY_REVIEW,    "DISCREPANCY_REVIEW_REQUIRED", False),
                (OUTPUT_ANOMALY,               "ANOMALY_REPORT",              False),
                (OUTPUT_AUTO_RESOLUTION,       "AUTO_RESOLUTION_LOG",         False),
                (OUTPUT_IGNORED,               "IGNORED_ITEMS_LOG",           False),
                (OUTPUT_INSERT_LOG,            "INSERT_LOG",                  False),
                (OUTPUT_RECONCILIATION_LOG,    "RECONCILIATION_LOG",          False),
                (OUTPUT_MISSING_GED_DIAGNOSIS, "MISSING_IN_GED_DIAGNOSIS",    False),
                (OUTPUT_MISSING_GED_TRUE,      "MISSING_IN_GED_TRUE",         False),
                (OUTPUT_MISSING_GF_DIAGNOSIS,  "MISSING_IN_GF_DIAGNOSIS",     False),
                (OUTPUT_MISSING_GF_TRUE,       "MISSING_IN_GF_TRUE",          False),
                (OUTPUT_NEW_SUBMITTAL_ANALYSIS,"NEW_SUBMITTAL_ANALYSIS",      False),
                (OUTPUT_CONSULTANT_REPORTS_WB, "CONSULTANT_REPORTS",          False),
                (CONSULTANT_MATCH_REPORT,      "CONSULTANT_MATCH_REPORT",     False),
                (OUTPUT_GF_TEAM_VERSION,       "GF_TEAM_VERSION",             False),
                (OUTPUT_GF_STAGE1,             "CONSULTANT_ENRICHED_STAGE1",  False),
                (OUTPUT_GF_STAGE2,             "CONSULTANT_ENRICHED_STAGE2",  False),
                (OUTPUT_SUSPICIOUS_ROWS,       "SUSPICIOUS_ROWS_REPORT",      False),
                # Debug outputs
                (OUTPUT_RECONCILIATION_SUMMARY,       "DEBUG_RECONCILIATION_SUMMARY", True),
                (OUTPUT_NEW_SUBMITTAL_SUMMARY,         "DEBUG_NEW_SUBMITTAL_SUMMARY",  True),
                (DEBUG_DIR / "routing_summary.xlsx",   "DEBUG_ROUTING_SUMMARY",        True),
                (DEBUG_DIR / "exclusion_summary.xlsx", "DEBUG_EXCLUSION_SUMMARY",      True),
                (DEBUG_DIR / "missing_in_ged_summary.xlsx", "DEBUG_MISSING_IN_GED_SUMMARY", True),
                (DEBUG_DIR / "missing_in_gf_summary.xlsx",  "DEBUG_MISSING_IN_GF_SUMMARY",  True),
                (DEBUG_DIR / "coarse_groups.xlsx",     "DEBUG_COARSE_GROUPS",          True),
                (DEBUG_DIR / "family_clusters.xlsx",   "DEBUG_FAMILY_CLUSTERS",        True),
                (DEBUG_DIR / "lifecycle_resolution.xlsx","DEBUG_LIFECYCLE_RESOLUTION",  True),
                (DEBUG_DIR / "discrepancy_sample.xlsx","DEBUG_DISCREPANCY_SAMPLE",      True),
                (DEBUG_DIR / "gf_duplicates.xlsx",     "DEBUG_GF_DUPLICATES",           True),
                (DEBUG_DIR / "gf_sheet_schema.xlsx",   "DEBUG_GF_SHEET_SCHEMA",         True),
            ]
            _arts_registered = 0
            for _ap, _atype, _is_debug in _artifacts_to_register:
                _ap = Path(_ap)
                if not _ap.exists():
                    continue
                _subfolder = "debug" if _is_debug else None
                _dest = copy_artifact_to_run_dir(str(_ap), _run_dir, subfolder=_subfolder)
                if _dest is None:
                    continue
                try:
                    _ahash = _sha256_art(str(_ap))
                except Exception:
                    _ahash = None
                register_run_artifact(
                    db_path       = RUN_MEMORY_DB,
                    run_number    = _run_number,
                    artifact_type = _atype,
                    artifact_name = _ap.name,
                    file_path     = _dest,
                    file_hash     = _ahash,
                    format        = "xlsx",
                )
                _arts_registered += 1

            # Register report_memory.db as artifact
            _rdb_path = Path(REPORT_MEMORY_DB)
            if _rdb_path.exists():
                _rdb_dest = copy_artifact_to_run_dir(str(_rdb_path), _run_dir)
                try:
                    _rdb_hash = _sha256_art(str(_rdb_path))
                except Exception:
                    _rdb_hash = None
                register_run_artifact(
                    db_path       = RUN_MEMORY_DB,
                    run_number    = _run_number,
                    artifact_type = "REPORT_MEMORY_DB",
                    artifact_name = "report_memory.db",
                    file_path     = _rdb_dest or str(_rdb_path),
                    file_hash     = _rdb_hash,
                    format        = "sqlite",
                )
                _arts_registered += 1

            mark_run_current(RUN_MEMORY_DB, _run_number)
            log(f"Run history: run {_run_number} registered ({_arts_registered} artifacts)")

        except Exception as _ra_err:
            _safe_console_print(f"  [WARN] Run history artifact registration error (non-fatal): {_ra_err}")

    _safe_console_print("\n✅ Pipeline complete!")
    _safe_console_print(f"   Output folder: {OUTPUT_DIR}")

    if _run_number is not None:
        try:
            _run_summary = {
                "docs_total": int(len(docs_df)),
                "responses_total": int(len(responses_df)),
                "final_gf_rows": int(len(dernier_df_for_gf) + len(ancien_df)),
                "discrepancies_count": int(len(discrepancies)),
                "artifacts_registered_count": int(_arts_registered),
                "consultant_report_memory_rows_loaded": int(len(persisted_df)),
            }
            if _RUN_CONTROL_CONTEXT:
                _run_summary["run_mode"] = _RUN_CONTROL_CONTEXT.get("run_mode")
                _run_summary["input_files"] = _RUN_CONTROL_CONTEXT.get("input_files", {})

            update_run_metadata(
                RUN_MEMORY_DB,
                _run_number,
                core_version=RUN_MEMORY_CORE_VERSION,
                summary_json=json.dumps(_run_summary, sort_keys=True),
            )
            finalize_run_success(RUN_MEMORY_DB, _run_number)
            ctx._ACTIVE_RUN_FINALIZED = True
        except Exception as _run_finalize_err:
            _safe_console_print(f"  [WARN] Run history finalize error (non-fatal): {_run_finalize_err}")

    return {
        "total_versions": total,
        "dernier_indices": int(dernier_count),
        "anomalies": int(anomaly_count),
        "routed_ok": int(ok_count),
        "routed_ambiguous": int(ambiguous_count),
        "unrouted": int(unrouted),
        "emetteur_mismatch": int(mismatch_count),
        "discrepancies_total": len(discrepancies),
        "discrepancies_review_required": len(disc_review),
        "discrepancies_cosmetic": len(disc_cosmetic),
        "recon_mid_before": mid_before,
        "recon_mid_after": mid_after,
        "recon_mif_before": mif_before,
        "recon_mif_after": mif_after,
        "recon_events": len(recon_log),
    }
