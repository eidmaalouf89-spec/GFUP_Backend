"""
src/flat_ged_runner.py — Safe wrapper around the frozen FLAT GED builder.

Public API
----------
build_flat_ged_artifacts(ged_path, intermediate_dir) -> dict
    Runs build_flat_ged in batch mode and returns normalised artifact metadata.

Contract
--------
- Never modifies src/flat_ged/* (builder internals).
- Deterministic: same inputs → same output file names, same return shape.
- Fails fast with clear RuntimeError on any precondition or output violation.
- Cleans up partial outputs on any failure after the builder has been called.
"""

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from src.flat_ged import build_flat_ged

# ── Expected output file names as produced by the builder ────────────────────
_FLAT_GED_NAME     = "FLAT_GED.xlsx"
_DEBUG_TRACE_NAME  = "DEBUG_TRACE.csv"
_RUN_REPORT_SRC    = "run_report.json"          # builder writes this name
_RUN_REPORT_DST    = "flat_ged_run_report.json"  # contract name


def _ensure_console_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def build_flat_ged_artifacts(
    ged_path: Path,
    intermediate_dir: Path,
) -> dict:
    """Run the FLAT GED builder and return normalised artifact metadata.

    Parameters
    ----------
    ged_path : Path
        Path to the raw GED export (.xlsx).
    intermediate_dir : Path
        Directory where output artifacts are written (created if absent).

    Returns
    -------
    dict with keys:
        success          : True
        flat_ged_path    : absolute path string to FLAT_GED.xlsx
        debug_trace_path : absolute path string to DEBUG_TRACE.csv, or None
        run_report_path  : absolute path string to flat_ged_run_report.json
        builder_result   : raw dict returned by build_flat_ged()

    Raises
    ------
    RuntimeError
        On any precondition failure, builder abort, or missing mandatory output.
        Partial outputs are deleted before re-raising.
    """
    # ── A. Prechecks ─────────────────────────────────────────────────────────
    if not ged_path.exists():
        raise RuntimeError(f"GED input file not found: {ged_path}")

    if ged_path.suffix.lower() != ".xlsx":
        raise RuntimeError(
            f"GED input must be an .xlsx file, got: {ged_path.suffix!r}"
        )

    intermediate_dir.mkdir(parents=True, exist_ok=True)
    _ensure_console_utf8()

    # ── B. Execute builder safely ─────────────────────────────────────────────
    builder_result: dict | None = None
    try:
        print(f"[flat_ged_runner] Building FLAT GED from: {ged_path}")
        print(f"[flat_ged_runner] Output dir: {intermediate_dir}")

        builder_result = build_flat_ged(
            ged_xlsx_path=ged_path,
            output_dir=intermediate_dir,
            mode="batch",
        )

        print("[flat_ged_runner] Builder completed.")

    except SystemExit:
        _cleanup_outputs(intermediate_dir)
        raise RuntimeError(
            "FLAT_GED builder aborted via SystemExit — check builder logs above."
        )
    except PermissionError as exc:
        _cleanup_outputs(intermediate_dir)
        raise RuntimeError(
            f"Cannot write to output directory — a file may be open in Excel: {exc}"
        ) from exc
    except Exception as exc:
        _cleanup_outputs(intermediate_dir)
        raise RuntimeError(f"FLAT_GED builder raised an unexpected error: {exc}") from exc

    # ── C. Validate mandatory outputs ─────────────────────────────────────────
    try:
        _validate_outputs(intermediate_dir)
    except RuntimeError:
        _cleanup_outputs(intermediate_dir)
        raise

    # ── D. Rename run_report.json → flat_ged_run_report.json ─────────────────
    src_report = intermediate_dir / _RUN_REPORT_SRC
    dst_report = intermediate_dir / _RUN_REPORT_DST

    try:
        src_report.replace(dst_report)  # atomic on same filesystem; overwrites if exists
    except PermissionError as exc:
        _cleanup_outputs(intermediate_dir)
        raise RuntimeError(
            f"Cannot rename {_RUN_REPORT_SRC} — file may be open in another application: {exc}"
        ) from exc
    except Exception as exc:
        _cleanup_outputs(intermediate_dir)
        raise RuntimeError(
            f"Failed to rename {_RUN_REPORT_SRC} → {_RUN_REPORT_DST}: {exc}"
        ) from exc

    # ── E. Return structured result ───────────────────────────────────────────
    flat_ged_path   = intermediate_dir / _FLAT_GED_NAME
    debug_trace     = intermediate_dir / _DEBUG_TRACE_NAME
    debug_trace_str = str(debug_trace.resolve()) if debug_trace.exists() else None

    return {
        "success":          True,
        "flat_ged_path":    str(flat_ged_path.resolve()),
        "debug_trace_path": debug_trace_str,
        "run_report_path":  str(dst_report.resolve()),
        "builder_result":   builder_result,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _validate_outputs(intermediate_dir: Path) -> None:
    """Raise RuntimeError if any mandatory output is missing."""
    mandatory = [_FLAT_GED_NAME, _RUN_REPORT_SRC]
    missing = [name for name in mandatory if not (intermediate_dir / name).exists()]
    if missing:
        raise RuntimeError(
            f"FLAT_GED builder did not produce expected outputs: {missing}"
        )


def _cleanup_outputs(intermediate_dir: Path) -> None:
    """Delete any partial builder outputs from intermediate_dir."""
    candidates = [
        _FLAT_GED_NAME,
        _DEBUG_TRACE_NAME,
        _RUN_REPORT_SRC,
        _RUN_REPORT_DST,
    ]
    for name in candidates:
        path = intermediate_dir / name
        if path.exists():
            try:
                path.unlink()
                print(f"[flat_ged_runner] Cleaned up: {path}")
            except Exception:
                pass  # best-effort cleanup; do not mask the original error
