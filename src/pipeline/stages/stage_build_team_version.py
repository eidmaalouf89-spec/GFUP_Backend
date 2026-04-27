"""
Stage: Build GF_TEAM_VERSION.

Calls team_version_builder.build_team_version() to produce
output/GF_TEAM_VERSION.xlsx from GF_V0_CLEAN.xlsx + OGF template.

OGF template resolution order:
  1. ctx.GF_FILE if it exists on disk
  2. Most recent GF_TEAM_VERSION artifact from run_memory.db
  3. Most recent FINAL_GF artifact from run_memory.db
  4. Skip or fail with clear message

Retry policy: 3 attempts (immediate, +1 s, +2 s).

Fatal policy:
  FULL / GED_REPORT modes  -> RuntimeError raised after 3 failed attempts
  All other modes          -> warning logged, pipeline continues

This stage runs after stage_write_gf and before stage_discrepancy.
stage_finalize_run registers the produced file as the GF_TEAM_VERSION artifact.
"""

import sqlite3
import time
from pathlib import Path

from pipeline.utils import _safe_console_print

_FATAL_MODES = {"FULL", "GED_REPORT"}
_RETRY_DELAYS = (0, 1, 2)   # seconds before attempt 1, 2, 3


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_latest_artifact_path(db_path, artifact_type):
    """Return the on-disk path for the most recent artifact of artifact_type.

    Queries run_memory.db ordered by run_number DESC and returns the stored
    file_path only if the file exists.  Handles repo-relocation by searching
    runs/run_*/<filename> newest-first when the stored path is absent.

    Returns a str path or None.
    """
    if not db_path or not Path(db_path).exists():
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT file_path FROM run_artifacts "
                "WHERE artifact_type = ? "
                "ORDER BY run_number DESC LIMIT 1",
                (artifact_type,),
            ).fetchone()
    except Exception:
        return None
    if not row or not row[0]:
        return None
    p = Path(row[0])
    if p.exists():
        return str(p)
    # Relocation fallback: search runs/run_*/<filename>, newest run first
    if p.name:
        base = Path(db_path).resolve().parent.parent  # data/run_memory.db -> project root
        for candidate in sorted(base.glob("runs/run_*/" + p.name), reverse=True):
            if candidate.exists():
                return str(candidate)
    return None


def _resolve_ogf_path(ctx, log):
    """Resolve the OGF template in priority order.

    Priority:
      1. ctx.GF_FILE (original Grandfichier_v3.xlsx)
      2. Latest GF_TEAM_VERSION artifact in run_memory.db
      3. Latest FINAL_GF artifact in run_memory.db

    Returns a str path or None.
    """
    db = ctx.RUN_MEMORY_DB

    # 1. User-supplied GF_FILE
    gf_file = ctx.GF_FILE
    if gf_file and Path(gf_file).exists():
        log("[team_version] OGF source: GF_FILE (" + Path(str(gf_file)).name + ")")
        return str(gf_file)

    # 2. Previous GF_TEAM_VERSION artifact
    team_path = _resolve_latest_artifact_path(db, "GF_TEAM_VERSION")
    if team_path:
        log("[team_version] OGF source: previous GF_TEAM_VERSION artifact (" + Path(team_path).name + ")")
        return team_path

    # 3. Previous FINAL_GF artifact
    final_path = _resolve_latest_artifact_path(db, "FINAL_GF")
    if final_path:
        log("[team_version] OGF source: previous FINAL_GF artifact (" + Path(final_path).name + ")")
        return final_path

    return None


# ---------------------------------------------------------------------------
# Stage entry point
# ---------------------------------------------------------------------------

def stage_build_team_version(ctx, log):
    """Build the GF_TEAM_VERSION output.

    Reads from ctx:
        GF_FILE                 Path  -- primary OGF template
        OUTPUT_GF               Path  -- freshly written GF_V0_CLEAN.xlsx
        OUTPUT_GF_TEAM_VERSION  Path | None -- destination
        RUN_MEMORY_DB           str   -- for OGF fallback artifact lookup
        _RUN_CONTROL_CONTEXT    dict | None -- for run_mode / fatal policy
    """
    output_team = ctx.OUTPUT_GF_TEAM_VERSION
    output_gf = ctx.OUTPUT_GF

    # ── Guard: destination must be defined ───────────────────────────────────
    if output_team is None:
        log("[team_version] OUTPUT_GF_TEAM_VERSION is None -- skipping (disabled mode)")
        return

    # ── Guard: clean GF must exist ───────────────────────────────────────────
    if not Path(str(output_gf)).exists():
        _safe_console_print(
            "  [WARN] stage_build_team_version: OUTPUT_GF not found: "
            + str(output_gf) + " -- skipping"
        )
        return

    # ── Resolve run mode for fatal policy ────────────────────────────────────
    run_ctrl = ctx._RUN_CONTROL_CONTEXT or {}
    run_mode = str(run_ctrl.get("run_mode", "")).upper()
    is_fatal_mode = run_mode in _FATAL_MODES

    # ── Resolve OGF template ─────────────────────────────────────────────────
    ogf_path = _resolve_ogf_path(ctx, log)
    if not ogf_path:
        msg = (
            "stage_build_team_version: no OGF template available -- "
            "GF_FILE missing and no previous GF_TEAM_VERSION / FINAL_GF artifact found"
        )
        if is_fatal_mode:
            raise RuntimeError(msg)
        _safe_console_print("  [WARN] " + msg + " -- skipping")
        return

    # ── Build with retry ─────────────────────────────────────────────────────
    log(
        "[team_version] Building GF_TEAM_VERSION from "
        + Path(str(output_gf)).name + " + " + Path(ogf_path).name + "..."
    )
    from team_version_builder import build_team_version

    last_exc = None
    for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
        if delay:
            time.sleep(delay)
        try:
            report = build_team_version(
                ogf_path=ogf_path,
                clean_path=str(output_gf),
                out_path=str(output_team),
            )
            log(
                "[team_version] Done (attempt " + str(attempt) + ") -- "
                "matched=" + str(report.get("total_matched", "?")) + ", "
                "updated=" + str(report.get("total_updated", "?")) + ", "
                "inserted=" + str(report.get("total_inserted", "?"))
            )
            log("  -> " + str(output_team))
            return  # success
        except Exception as exc:
            last_exc = exc
            log("[team_version] Attempt " + str(attempt) + " failed: " + str(exc))

    # All attempts exhausted
    msg = (
        "stage_build_team_version: build_team_version failed after "
        + str(len(_RETRY_DELAYS)) + " attempts -- last error: " + str(last_exc)
    )
    if is_fatal_mode:
        raise RuntimeError(msg)
    _safe_console_print("  [WARN] " + msg)
