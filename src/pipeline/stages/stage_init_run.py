"""
stage_init_run — Initialize run memory DB and determine run number.

Lines 270-333 of run_pipeline().
Initializes run memory DB, determines run number, creates run directory.
"""

import os as _os
from run_memory import (
    init_run_memory_db as init_run_memory_db_fn,
    baseline_run_exists,
    get_next_run_number,
    get_current_run,
    get_run_dir,
    create_run,
)
from pipeline.utils import _safe_console_print


def stage_init_run(ctx, log):
    """
    Initialize run history and determine run number.

    Context reads:
      - ctx.BASE_DIR
      - ctx.RUN_MEMORY_DB
      - ctx.RUN_MEMORY_CORE_VERSION
      - ctx._RUN_CONTROL_CONTEXT

    Context writes:
      - ctx._run_number
      - ctx._run_dir
      - ctx._run_input_entries
      - ctx._arts_registered
      - ctx._is_baseline_bootstrap
      - ctx._ACTIVE_RUN_NUMBER
      - ctx._ACTIVE_RUN_FINALIZED
    """
    # ── RUN HISTORY: initialise and determine run number ──────
    _run_number = None
    _run_dir    = None
    _run_input_entries = []
    _arts_registered = 0
    _is_baseline_bootstrap = False
    _ACTIVE_RUN_NUMBER = None
    _ACTIVE_RUN_FINALIZED = False
    try:
        init_run_memory_db_fn(ctx.RUN_MEMORY_DB)
        _baseline_exists = baseline_run_exists(ctx.RUN_MEMORY_DB)
        _run_number = get_next_run_number(ctx.RUN_MEMORY_DB)

        if not _baseline_exists:
            if _run_number != 0:
                raise RuntimeError(
                    "run_memory baseline missing while non-baseline runs exist: "
                    "rebuild Run 0 first or clean run history"
                )
            _run_type = "BASELINE"
            _parent_run_number = None
            _root_run_number = 0
            _is_baseline_bootstrap = True
        else:
            _run_type = "INCREMENTAL"
            _current_run_df = get_current_run(ctx.RUN_MEMORY_DB)
            _parent_run_number = (
                int(_current_run_df.iloc[0]["run_number"])
                if not _current_run_df.empty else None
            )
            _root_run_number = 0

        _run_dir = get_run_dir(str(ctx.BASE_DIR), _run_number)
        _os.makedirs(_run_dir, exist_ok=True)
        _os.makedirs(_run_dir + "/debug", exist_ok=True)

        _run_notes = "Auto-created by run_pipeline()"
        if ctx._RUN_CONTROL_CONTEXT and ctx._RUN_CONTROL_CONTEXT.get("run_mode"):
            _run_notes = f"{_run_notes} | run_mode={ctx._RUN_CONTROL_CONTEXT['run_mode']}"
        if _is_baseline_bootstrap:
            _run_notes = f"{_run_notes} | bootstrap_baseline=1"

        create_run(
            db_path              = ctx.RUN_MEMORY_DB,
            run_number           = _run_number,
            run_type             = _run_type,
            parent_run_number    = _parent_run_number,
            root_run_number      = _root_run_number,
            based_on_run_number  = _parent_run_number,
            is_baseline          = _is_baseline_bootstrap,
            run_label            = (
                "Run 0 - baseline"
                if _is_baseline_bootstrap else f"Run {_run_number}"
            ),
            notes                = _run_notes,
            core_version         = ctx.RUN_MEMORY_CORE_VERSION,
        )
        log(f"Run history: run {_run_number} ({_run_type}) — folder: runs/run_{_run_number:04d}/")
        _ACTIVE_RUN_NUMBER = _run_number
    except Exception as _rm_init_err:
        _safe_console_print(f"  [WARN] Run history init error (non-fatal): {_rm_init_err}")
        _run_number = None
        _run_dir    = None

    # Write to context
    ctx._run_number = _run_number
    ctx._run_dir = _run_dir
    ctx._run_input_entries = _run_input_entries
    ctx._arts_registered = _arts_registered
    ctx._is_baseline_bootstrap = _is_baseline_bootstrap
    ctx._ACTIVE_RUN_NUMBER = _ACTIVE_RUN_NUMBER
    ctx._ACTIVE_RUN_FINALIZED = _ACTIVE_RUN_FINALIZED
