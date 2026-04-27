"""
run_orchestrator.py
-------------------
Controlled execution layer for GF Updater V3.

This module adds:
  - explicit run modes
  - input validation
  - deterministic execution context
  - a safe user-facing pipeline entrypoint
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sqlite3

from src.run_explorer import export_final_gf, get_run_summary
from src.run_memory import register_run_artifact, sha256_file

RUN_MODE_GED_ONLY = "GED_ONLY"
RUN_MODE_GED_GF = "GED_GF"
RUN_MODE_GED_REPORT = "GED_REPORT"
RUN_MODE_FULL = "FULL"

_VALID_RUN_MODES = {
    RUN_MODE_GED_ONLY,
    RUN_MODE_GED_GF,
    RUN_MODE_GED_REPORT,
    RUN_MODE_FULL,
}


def _resolve_inherited_gf_record(db_path: str) -> tuple[int, str]:
    """Resolve the FINAL_GF artifact from the most recent completed run.

    Tries stored path first. If that fails (repo relocated), falls back
    to resolving relative to the project base directory (parent of data/).
    """
    base_dir = Path(db_path).resolve().parent.parent  # data/run_memory.db → project root

    def _try_resolve(file_path: str) -> Optional[str]:
        """Try stored path, then relocation-aware fallback."""
        if not file_path:
            return None
        p = Path(file_path)
        if p.exists():
            return str(p.resolve())
        # Extract tail from "runs/" or "output/" onward, resolve against base_dir
        path_str = str(p)
        for anchor in ("runs/", "runs\\", "output/", "output\\"):
            idx = path_str.find(anchor)
            if idx >= 0:
                candidate = base_dir / path_str[idx:]
                if candidate.exists():
                    return str(candidate.resolve())
        # Last resort: search by filename in run dirs
        if p.name:
            for run_dir in sorted(base_dir.glob("runs/run_*")):
                candidate = run_dir / p.name
                if candidate.exists():
                    return str(candidate.resolve())
        return None

    with sqlite3.connect(db_path, timeout=5) as conn:
        conn.execute("PRAGMA busy_timeout=5000")
        rows = conn.execute(
            """
            SELECT r.run_number, a.file_path
            FROM runs r
            JOIN run_artifacts a
              ON a.run_number = r.run_number
            WHERE r.status = 'COMPLETED'
              AND r.is_stale = 0
              AND a.artifact_type = 'FINAL_GF'
            ORDER BY r.run_number DESC
            """
        ).fetchall()

        for run_number, file_path in rows:
            resolved = _try_resolve(file_path)
            if resolved:
                return int(run_number), resolved

        row = conn.execute(
            """
            SELECT a.file_path
            FROM run_artifacts a
            WHERE a.run_number = 0
              AND a.artifact_type = 'FINAL_GF'
            ORDER BY a.created_at DESC
            LIMIT 1
            """
        ).fetchone()

    if row is not None and row[0]:
        resolved = _try_resolve(row[0])
        if resolved:
            return 0, resolved

    raise RuntimeError(
        "No saved GF baseline available. Provide a GF or bootstrap a valid baseline first."
    )


def resolve_inherited_gf(db_path: str) -> str:
    return _resolve_inherited_gf_record(db_path)[1]


def validate_run_inputs(run_mode, paths_dict) -> dict:
    errors = []
    warnings = []

    if run_mode not in _VALID_RUN_MODES:
        errors.append(f"Unsupported run_mode: {run_mode}")
        return {"valid": False, "errors": errors, "warnings": warnings}

    ged_path = paths_dict.get("ged_path")
    gf_path = paths_dict.get("gf_path")
    reports_dir = paths_dict.get("reports_dir")

    def _check_xlsx(path_value, label, required=True):
        if not path_value:
            if required:
                errors.append(f"Missing required input: {label}")
            return
        path = Path(path_value)
        if not path.exists():
            errors.append(f"{label} not found: {path}")
            return
        if not path.is_file():
            errors.append(f"{label} is not a file: {path}")
            return
        if path.suffix.lower() != ".xlsx":
            errors.append(f"{label} must be a .xlsx file: {path}")

    _check_xlsx(ged_path, "GED file", required=True)
    _check_xlsx(gf_path, "GF file", required=False)
    if not gf_path:
        warnings.append("GF file not provided; orchestrator will attempt inheritance from run history")

    if reports_dir:
        rpath = Path(reports_dir)
        if not rpath.exists():
            errors.append(f"reports_dir not found: {rpath}")
        elif not rpath.is_dir():
            errors.append(f"reports_dir is not a directory: {rpath}")
    elif run_mode in {RUN_MODE_FULL, RUN_MODE_GED_REPORT}:
        if run_mode == RUN_MODE_GED_REPORT:
            errors.append("Missing required input: reports_dir")
        else:
            warnings.append("FULL mode requested without reports_dir; consultant report ingestion will be skipped")
    elif run_mode == RUN_MODE_FULL:
        warnings.append("FULL mode requested without reports_dir; consultant report ingestion will be skipped")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def _build_execution_context(
    run_mode: str,
    ged_path: str,
    gf_path: Optional[str],
    reports_dir: Optional[str],
    *,
    gf_provided_by_user: bool,
    inherited_from_run: Optional[int],
) -> dict:
    return {
        "run_mode": run_mode,
        "inputs": {
            "ged_path": str(Path(ged_path).resolve()) if ged_path else None,
            "gf_path": str(Path(gf_path).resolve()) if gf_path else None,
            "reports_dir": str(Path(reports_dir).resolve()) if reports_dir else None,
        },
        "input_files": {
            "ged": Path(ged_path).name if ged_path else None,
            "gf": Path(gf_path).name if gf_path else None,
            "reports_dir": Path(reports_dir).name if reports_dir else None,
            "gf_provided_by_user": gf_provided_by_user,
            "inherited_from_run": inherited_from_run,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@contextmanager
def _patched_main_context(main_module, execution_context: dict):
    disabled_root = main_module.OUTPUT_DIR / "_orchestrator_disabled" / execution_context["run_mode"].lower()
    saved = {
        "FLAT_GED_FILE": getattr(main_module, "FLAT_GED_FILE", None),
        "FLAT_GED_MODE":  getattr(main_module, "FLAT_GED_MODE", "raw"),
        "GED_FILE": main_module.GED_FILE,
        "GF_FILE": main_module.GF_FILE,
        "CONSULTANT_REPORTS_ROOT": main_module.CONSULTANT_REPORTS_ROOT,
        "CONSULTANT_MATCH_REPORT": main_module.CONSULTANT_MATCH_REPORT,
        "OUTPUT_CONSULTANT_REPORTS_WB": main_module.OUTPUT_CONSULTANT_REPORTS_WB,
        "OUTPUT_GF_STAGE1": main_module.OUTPUT_GF_STAGE1,
        "OUTPUT_GF_STAGE2": main_module.OUTPUT_GF_STAGE2,
        "OUTPUT_GF_TEAM_VERSION": main_module.OUTPUT_GF_TEAM_VERSION,
        "OUTPUT_SUSPICIOUS_ROWS": main_module.OUTPUT_SUSPICIOUS_ROWS,
        "_RUN_CONTROL_CONTEXT": getattr(main_module, "_RUN_CONTROL_CONTEXT", None),
    }

    main_module.GED_FILE = Path(execution_context["inputs"]["ged_path"])
    if execution_context["inputs"]["gf_path"]:
        main_module.GF_FILE = Path(execution_context["inputs"]["gf_path"])
    else:
        main_module.GF_FILE = Path(disabled_root / "_missing_gf.xlsx")

    use_reports = (
        execution_context["run_mode"] in {RUN_MODE_FULL, RUN_MODE_GED_REPORT}
        and execution_context["inputs"]["reports_dir"] is not None
    )
    if use_reports:
        main_module.CONSULTANT_REPORTS_ROOT = Path(execution_context["inputs"]["reports_dir"])
    else:
        main_module.CONSULTANT_REPORTS_ROOT = Path(disabled_root / "reports")
        main_module.CONSULTANT_MATCH_REPORT = disabled_root / "consultant_match_report.xlsx"
        main_module.OUTPUT_CONSULTANT_REPORTS_WB = disabled_root / "consultant_reports.xlsx"
        main_module.OUTPUT_GF_STAGE1 = disabled_root / "GF_consultant_enriched_stage1.xlsx"
        main_module.OUTPUT_GF_STAGE2 = disabled_root / "GF_consultant_enriched_stage2.xlsx"
        main_module.OUTPUT_GF_TEAM_VERSION = disabled_root / "GF_TEAM_VERSION.xlsx"
        main_module.OUTPUT_SUSPICIOUS_ROWS = disabled_root / "SUSPICIOUS_ROWS_REPORT.xlsx"

    main_module._RUN_CONTROL_CONTEXT = execution_context
    try:
        yield
    finally:
        for key, value in saved.items():
            setattr(main_module, key, value)


def _register_flat_ged_artifacts(db_path: str, run_number: int, build_result: dict) -> None:
    """Register FLAT_GED, FLAT_GED_RUN_REPORT, and (if present) FLAT_GED_DEBUG_TRACE
    artifacts into run_memory for the given run_number.

    Called only when force_raw=False and run_number is known after a successful pipeline run.
    Never raises — registration failures are warned but do not abort the run.
    """
    import logging as _logging
    _log = _logging.getLogger(__name__)

    def _safe_hash(path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        try:
            return sha256_file(path)
        except Exception:
            return None

    # FLAT_GED — mandatory
    flat_ged_path = build_result.get("flat_ged_path")
    if flat_ged_path:
        try:
            register_run_artifact(
                db_path=db_path,
                run_number=run_number,
                artifact_type="FLAT_GED",
                artifact_name="FLAT_GED.xlsx",
                file_path=str(flat_ged_path),
                file_hash=_safe_hash(flat_ged_path),
                format="xlsx",
            )
        except Exception as exc:
            _log.warning("Could not register FLAT_GED artifact: %s", exc)
    else:
        _log.warning("FLAT_GED path missing from build_result; skipping FLAT_GED registration")

    # FLAT_GED_RUN_REPORT — mandatory
    run_report_path = build_result.get("run_report_path")
    if run_report_path:
        try:
            register_run_artifact(
                db_path=db_path,
                run_number=run_number,
                artifact_type="FLAT_GED_RUN_REPORT",
                artifact_name="flat_ged_run_report.json",
                file_path=str(run_report_path),
                file_hash=_safe_hash(run_report_path),
                format="json",
            )
        except Exception as exc:
            _log.warning("Could not register FLAT_GED_RUN_REPORT artifact: %s", exc)
    else:
        _log.warning("flat_ged_run_report.json missing from build_result; skipping FLAT_GED_RUN_REPORT registration")

    # FLAT_GED_DEBUG_TRACE — optional (None is normal when builder skips it)
    debug_trace_path = build_result.get("debug_trace_path")
    if debug_trace_path:
        try:
            register_run_artifact(
                db_path=db_path,
                run_number=run_number,
                artifact_type="FLAT_GED_DEBUG_TRACE",
                artifact_name="DEBUG_TRACE.csv",
                file_path=str(debug_trace_path),
                file_hash=_safe_hash(debug_trace_path),
                format="csv",
            )
        except Exception as exc:
            _log.warning("Could not register FLAT_GED_DEBUG_TRACE artifact: %s", exc)
    # If debug_trace_path is None, skip silently — this is expected in non-batch modes


def run_pipeline_controlled(
    run_mode: str,
    ged_path: str,
    gf_path: Optional[str] = None,
    reports_dir: Optional[str] = None,
) -> dict:
    import main as main_module

    validation = validate_run_inputs(
        run_mode,
        {
            "ged_path": ged_path,
            "gf_path": gf_path,
            "reports_dir": reports_dir,
        },
    )
    if not validation["valid"]:
        return {
            "success": False,
            "run_number": None,
            "status": "FAILED",
            "errors": validation["errors"],
            "warnings": validation["warnings"],
            "outputs": {"final_gf": None},
        }

    resolved_gf_path = gf_path
    inherited_from_run = None
    gf_provided_by_user = gf_path is not None
    if not resolved_gf_path:
        inherited_from_run, resolved_gf_path = _resolve_inherited_gf_record(main_module.RUN_MEMORY_DB)

    execution_context = _build_execution_context(
        run_mode=run_mode,
        ged_path=ged_path,
        gf_path=resolved_gf_path,
        reports_dir=reports_dir,
        gf_provided_by_user=gf_provided_by_user,
        inherited_from_run=inherited_from_run,
    )

    run_number = None
    status = "FAILED"
    errors = []
    warnings = list(validation["warnings"])
    final_gf = None
    artifact_count = 0

    # -- Auto-build Flat GED (skip with GFUP_FORCE_RAW=1 for developer raw fallback) --
    force_raw = os.environ.get("GFUP_FORCE_RAW", "").strip() == "1"
    flat_ged_path = None
    if not force_raw:
        print("[orchestrator] FLAT MODE -- building Flat GED intermediate artifact.")
        try:
            from src.flat_ged_runner import build_flat_ged_artifacts
            intermediate_dir = Path(main_module.INTERMEDIATE_DIR)
            build_result = build_flat_ged_artifacts(
                ged_path=Path(ged_path),
                intermediate_dir=intermediate_dir,
            )
            flat_ged_path = build_result["flat_ged_path"]
        except RuntimeError as exc:
            return {
                "success": False,
                "run_number": None,
                "status": "FAILED",
                "errors": [f"Flat GED build failed: {exc}"],
                "warnings": warnings,
                "outputs": {"final_gf": None},
            }
    else:
        print("[orchestrator] RAW FALLBACK -- GFUP_FORCE_RAW=1, skipping Flat GED build.")

    try:
        with _patched_main_context(main_module, execution_context):
            if flat_ged_path is not None:
                main_module.FLAT_GED_FILE = Path(flat_ged_path)
                main_module.FLAT_GED_MODE = "flat"
            main_module.run_pipeline(verbose=True)
            run_number = main_module._ACTIVE_RUN_NUMBER
            if run_number is not None:
                # Register Flat GED artifacts produced before this run started
                if not force_raw:
                    _register_flat_ged_artifacts(
                        db_path=main_module.RUN_MEMORY_DB,
                        run_number=run_number,
                        build_result=build_result,
                    )
                run_summary = get_run_summary(main_module.RUN_MEMORY_DB, run_number)
                status = run_summary["status"]
                artifact_count = run_summary["artifact_count"]
                if status == "STARTED":
                    orphaned_reason = "Pipeline returned without finalizing run state"
                    errors.append(orphaned_reason)
                    if not getattr(main_module, "_ACTIVE_RUN_FINALIZED", False):
                        try:
                            main_module.finalize_run_failure(
                                main_module.RUN_MEMORY_DB,
                                run_number,
                                orphaned_reason,
                            )
                        except Exception as finalize_exc:
                            errors.append(
                                f"Could not finalize orphaned run {run_number}: {finalize_exc}"
                            )
                    run_summary = get_run_summary(main_module.RUN_MEMORY_DB, run_number)
                    status = run_summary["status"]
                    artifact_count = run_summary["artifact_count"]
                try:
                    final_gf = export_final_gf(main_module.RUN_MEMORY_DB, run_number)
                except Exception as exc:
                    warnings.append(f"FINAL_GF export lookup failed for run {run_number}: {exc}")
            else:
                status = "FAILED"
                errors.append("Pipeline did not register a run_number")
    except Exception as exc:
        run_number = getattr(main_module, "_ACTIVE_RUN_NUMBER", None)
        if run_number is not None and not getattr(main_module, "_ACTIVE_RUN_FINALIZED", False):
            try:
                main_module.finalize_run_failure(
                    main_module.RUN_MEMORY_DB,
                    run_number,
                    f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                pass
        status = "FAILED"
        errors.append(f"{type(exc).__name__}: {exc}")

    return {
        "success": status == "COMPLETED",
        "run_number": run_number,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "outputs": {"final_gf": final_gf},
        "artifact_count": artifact_count,
        "gf_provided_by_user": gf_provided_by_user,
        "inherited_from_run": inherited_from_run,
        "resolved_gf_path": resolved_gf_path,
    }
