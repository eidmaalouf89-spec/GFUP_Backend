"""
src/pipeline/runner.py
----------------------
Pipeline execution logic extracted from main.run_pipeline().

The implementation receives the calling module's namespace so that path
constants mutated by run_orchestrator.py (via ``main_module.GED_FILE = …``)
are picked up correctly, and mutable globals (_ACTIVE_RUN_NUMBER, etc.)
are written back to the same namespace.
"""

from pipeline.context import PipelineState
from pipeline.utils import _safe_console_print
from pipeline.stages import (
    stage_init_run,
    stage_read,
    stage_read_flat,
    stage_normalize,
    stage_version,
    stage_route,
    stage_report_memory,
    stage_write_gf,
    stage_build_team_version,
    stage_discrepancy,
    stage_diagnosis,
    stage_finalize_run,
)


def _run_pipeline_impl(ns, verbose: bool = True):
    """Execute the full GF Updater pipeline.

    Parameters
    ----------
    ns : module
        The calling module's namespace (``sys.modules["main"]``).
        Path constants are read from *ns* (not from pipeline.paths)
        because run_orchestrator.py may have overridden them.
        Mutable globals (_ACTIVE_RUN_NUMBER, _ACTIVE_RUN_FINALIZED)
        are written back to *ns* so the caller sees them.
    verbose : bool
        Enable per-stage progress logging.

    Returns
    -------
    dict
        Pipeline result summary.
    """

    def log(msg: str):
        if verbose:
            _safe_console_print(f"  {msg}")

    # ── Feature flag: 'raw' (default) or 'flat' ───────────────
    _mode = getattr(ns, "FLAT_GED_MODE", "raw")
    _mode_label = "FLAT MODE" if _mode == "flat" else "RAW FALLBACK"

    _safe_console_print("=" * 60)
    _safe_console_print(f"GF UPDATER V3 — {_mode_label}")
    _safe_console_print("=" * 60)

    # ── Build pipeline context with all path constants ─────────
    ctx = PipelineState(
        BASE_DIR                      = ns.BASE_DIR,
        INPUT_DIR                     = ns.INPUT_DIR,
        OUTPUT_DIR                    = ns.OUTPUT_DIR,
        DEBUG_DIR                     = ns.DEBUG_DIR,
        GED_FILE                      = ns.GED_FILE,
        GF_FILE                       = ns.GF_FILE,
        OUTPUT_GF                     = ns.OUTPUT_GF,
        OUTPUT_DISCREPANCY            = ns.OUTPUT_DISCREPANCY,
        OUTPUT_DISCREPANCY_REVIEW     = ns.OUTPUT_DISCREPANCY_REVIEW,
        OUTPUT_ANOMALY                = ns.OUTPUT_ANOMALY,
        OUTPUT_AUTO_RESOLUTION        = ns.OUTPUT_AUTO_RESOLUTION,
        OUTPUT_IGNORED                = ns.OUTPUT_IGNORED,
        OUTPUT_MISSING_GED_DIAGNOSIS  = ns.OUTPUT_MISSING_GED_DIAGNOSIS,
        OUTPUT_MISSING_GED_TRUE       = ns.OUTPUT_MISSING_GED_TRUE,
        OUTPUT_MISSING_GF_DIAGNOSIS   = ns.OUTPUT_MISSING_GF_DIAGNOSIS,
        OUTPUT_MISSING_GF_TRUE        = ns.OUTPUT_MISSING_GF_TRUE,
        OUTPUT_RECONCILIATION_LOG     = ns.OUTPUT_RECONCILIATION_LOG,
        OUTPUT_RECONCILIATION_SUMMARY = ns.OUTPUT_RECONCILIATION_SUMMARY,
        OUTPUT_INSERT_LOG             = ns.OUTPUT_INSERT_LOG,
        OUTPUT_NEW_SUBMITTAL_ANALYSIS = ns.OUTPUT_NEW_SUBMITTAL_ANALYSIS,
        OUTPUT_NEW_SUBMITTAL_SUMMARY  = ns.OUTPUT_NEW_SUBMITTAL_SUMMARY,
        OUTPUT_CONSULTANT_REPORTS_WB  = ns.OUTPUT_CONSULTANT_REPORTS_WB,
        OUTPUT_GF_STAGE1              = ns.OUTPUT_GF_STAGE1,
        OUTPUT_GF_STAGE2              = ns.OUTPUT_GF_STAGE2,
        OUTPUT_GF_TEAM_VERSION        = ns.OUTPUT_GF_TEAM_VERSION,
        OUTPUT_SUSPICIOUS_ROWS        = ns.OUTPUT_SUSPICIOUS_ROWS,
        RUN_MEMORY_DB                 = ns.RUN_MEMORY_DB,
        REPORT_MEMORY_DB              = ns.REPORT_MEMORY_DB,
        RUN_MEMORY_CORE_VERSION       = ns.RUN_MEMORY_CORE_VERSION,
        CONSULTANT_MATCH_REPORT       = ns.CONSULTANT_MATCH_REPORT,
        CONSULTANT_REPORTS_ROOT       = ns.CONSULTANT_REPORTS_ROOT,
        _RUN_CONTROL_CONTEXT          = ns._RUN_CONTROL_CONTEXT,
        FLAT_GED_FILE                 = getattr(ns, "FLAT_GED_FILE", None),
        flat_ged_mode                 = _mode,
    )

    # ── Execute pipeline stages in order ─────────────────────
    stage_init_run(ctx, log)
    ns._ACTIVE_RUN_NUMBER   = ctx._ACTIVE_RUN_NUMBER
    ns._ACTIVE_RUN_FINALIZED = ctx._ACTIVE_RUN_FINALIZED

    # ── Read path: raw (existing) or flat (adapter) ───────────
    if _mode == "flat":
        stage_read_flat(ctx, log)
    else:
        stage_read(ctx, log)
    stage_normalize(ctx, log)
    stage_version(ctx, log)
    stage_route(ctx, log)
    stage_report_memory(ctx, log)
    stage_write_gf(ctx, log)
    stage_build_team_version(ctx, log)
    stage_discrepancy(ctx, log)
    stage_diagnosis(ctx, log)
    result = stage_finalize_run(ctx, log)

    ns._ACTIVE_RUN_FINALIZED = ctx._ACTIVE_RUN_FINALIZED

    return result
