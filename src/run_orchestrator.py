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

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sqlite3

from src.run_explorer import export_final_gf, get_run_summary

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
    with sqlite3.connect(db_path) as conn:
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
            resolved = Path(file_path).resolve()
            if resolved.exists():
                return int(run_number), str(resolved)

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
        resolved = Path(row[0]).resolve()
        if resolved.exists():
            return 0, str(resolved)

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
    mapping_path = paths_dict.get("mapping_path")
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
    _check_xlsx(mapping_path, "Mapping file", required=True)
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
    mapping_path: str,
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
            "mapping_path": str(Path(mapping_path).resolve()) if mapping_path else None,
            "gf_path": str(Path(gf_path).resolve()) if gf_path else None,
            "reports_dir": str(Path(reports_dir).resolve()) if reports_dir else None,
        },
        "input_files": {
            "ged": Path(ged_path).name if ged_path else None,
            "mapping": Path(mapping_path).name if mapping_path else None,
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
        "GED_FILE": main_module.GED_FILE,
        "GF_FILE": main_module.GF_FILE,
        "MAPPING_FILE": main_module.MAPPING_FILE,
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
    main_module.MAPPING_FILE = Path(execution_context["inputs"]["mapping_path"])
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


def run_pipeline_controlled(
    run_mode: str,
    ged_path: str,
    mapping_path: str,
    gf_path: Optional[str] = None,
    reports_dir: Optional[str] = None,
) -> dict:
    import main as main_module

    validation = validate_run_inputs(
        run_mode,
        {
            "ged_path": ged_path,
            "gf_path": gf_path,
            "mapping_path": mapping_path,
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
        mapping_path=mapping_path,
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

    try:
        with _patched_main_context(main_module, execution_context):
            main_module.run_pipeline(verbose=True)
            run_number = main_module._ACTIVE_RUN_NUMBER
            if run_number is not None:
                run_summary = get_run_summary(main_module.RUN_MEMORY_DB, run_number)
                status = run_summary["status"]
                artifact_count = run_summary["artifact_count"]
                final_gf = export_final_gf(main_module.RUN_MEMORY_DB, run_number)
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
