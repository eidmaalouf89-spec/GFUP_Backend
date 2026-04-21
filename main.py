"""
main.py — GF UPDATER V3 entrypoint.

Usage:
    python main.py
"""

import sys
import traceback
from pathlib import Path

# ── Add src/ to import path ──────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent / "src"))

# ── Fix Windows console encoding ─────────────────────────────
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ── Path constants ────────────────────────────────────────────
# Defined in pipeline.paths; re-exported here at module level so
# run_orchestrator.py (which does ``import main as main_module``)
# can read AND mutate them (e.g. main_module.GED_FILE = …).
from pipeline.paths import *           # noqa: F401,F403

# Ensure output directories exist
OUTPUT_DIR.mkdir(exist_ok=True)        # noqa: F405
DEBUG_DIR.mkdir(exist_ok=True)         # noqa: F405

# ── Mutable globals (read/written by run_orchestrator.py) ────
_ACTIVE_RUN_NUMBER   = None
_ACTIVE_RUN_FINALIZED = False
_RUN_CONTROL_CONTEXT  = None

# ── Re-export for run_orchestrator.py (main_module.finalize_run_failure) ──
from run_memory import finalize_run_failure  # noqa: F401


def run_pipeline(verbose: bool = True):
    """Thin wrapper — delegates to pipeline.runner."""
    from pipeline.runner import _run_pipeline_impl
    return _run_pipeline_impl(sys.modules[__name__], verbose)


if __name__ == "__main__":
    try:
        from src.run_orchestrator import RUN_MODE_FULL, run_pipeline_controlled

        result = run_pipeline_controlled(
            run_mode=RUN_MODE_FULL,
            ged_path=str(GED_FILE),                                        # noqa: F405
            gf_path=str(GF_FILE),                                          # noqa: F405
            reports_dir=(
                str(CONSULTANT_REPORTS_ROOT)                               # noqa: F405
                if CONSULTANT_REPORTS_ROOT.exists() else None              # noqa: F405
            ),
        )
        if not result.get("success"):
            raise RuntimeError(
                "; ".join(result.get("errors", []) or ["Controlled execution failed"])
            )
    except Exception as exc:
        if _ACTIVE_RUN_NUMBER is not None and not _ACTIVE_RUN_FINALIZED:
            try:
                finalize_run_failure(
                    RUN_MEMORY_DB,                                         # noqa: F405
                    _ACTIVE_RUN_NUMBER,
                    f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                pass
        traceback.print_exc()
        raise
