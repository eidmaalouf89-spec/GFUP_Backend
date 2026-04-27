"""
stage_read — Read GED export, load mapping, register inputs in run memory.

Lines 335-427 of run_pipeline().
Reads GED export file, loads approver mapping, and registers inputs in run memory.
"""

import json
from pathlib import Path

import pandas as pd

from read_raw import read_ged
from normalize import load_mapping
from run_memory import (
    register_run_input,
    sha256_file as _sha256,
    update_run_metadata,
)
from domain.gf_helpers import _build_input_signature
from pipeline.utils import _safe_console_print


def stage_read(ctx, log):
    """
    Read GED export, load mapping, and register inputs in run memory.

    Context reads:
      - ctx.GED_FILE
      - ctx.GF_FILE
      - ctx._run_number
      - ctx.RUN_MEMORY_DB
      - ctx.REPORT_MEMORY_DB
      - ctx.CONSULTANT_MATCH_REPORT
      - ctx.CONSULTANT_REPORTS_ROOT
      - ctx._run_input_entries

    Context writes:
      - ctx.docs_df
      - ctx.responses_df
      - ctx.ged_approver_names
      - ctx.mapping
    """
    # ── STEP 1: Read GED ──────────────────────────────────────
    _safe_console_print("\n[1/7] Reading GED export...")
    docs_df, responses_df, ged_approver_names = read_ged(str(ctx.GED_FILE))
    log(f"Documents: {len(docs_df)} rows")
    log(f"Responses: {len(responses_df)} rows")
    log(f"Approvers discovered: {len(ged_approver_names)}")

    # ── STEP 2: Load Mapping (hardcoded) ─────────────────────
    _safe_console_print("\n[2/7] Loading Mapping...")
    mapping = load_mapping()
    log(f"Mapping entries: {len(mapping)} (hardcoded)")

    exception_count = sum(1 for v in mapping.values() if v == "Exception List")
    log(f"Exception List entries: {exception_count}")

    # ── RUN HISTORY: register inputs ─────────────────────────
    if ctx._run_number is not None:
        try:
            def _register_input_entry(
                input_type: str,
                source_path: Path,
                source_filename: str,
                metadata: dict | None = None,
            ) -> None:
                _inp_hash = None
                if source_path.exists() and source_path.is_file():
                    try:
                        _inp_hash = _sha256(str(source_path))
                    except Exception:
                        pass
                metadata_json = json.dumps(metadata, sort_keys=True) if metadata else None
                register_run_input(
                    db_path          = ctx.RUN_MEMORY_DB,
                    run_number       = ctx._run_number,
                    input_type       = input_type,
                    source_filename  = source_filename,
                    source_file_hash = _inp_hash,
                    source_path      = str(source_path) if source_path.exists() else None,
                    metadata_json    = metadata_json,
                )
                ctx._run_input_entries.append({
                    "input_type": input_type,
                    "source_filename": source_filename,
                    "source_file_hash": _inp_hash,
                    "source_path": str(source_path) if source_path.exists() else None,
                    "metadata": metadata or {},
                })

            for _inp_path, _inp_type, _inp_name in [
                (ctx.GED_FILE,     "GED",     "GED_export.xlsx"),
                (ctx.GF_FILE,      "GF",      ctx.GF_FILE.name),
            ]:
                _register_input_entry(_inp_type, Path(_inp_path), _inp_name)

            _register_input_entry(
                "REPORT_MEMORY",
                Path(ctx.REPORT_MEMORY_DB),
                Path(ctx.REPORT_MEMORY_DB).name,
            )

            if ctx.CONSULTANT_MATCH_REPORT.exists():
                _register_input_entry(
                    "CONSULTANT_MATCH_REPORT",
                    ctx.CONSULTANT_MATCH_REPORT,
                    ctx.CONSULTANT_MATCH_REPORT.name,
                )

            if ctx.CONSULTANT_REPORTS_ROOT.exists():
                _pdf_files = sorted(ctx.CONSULTANT_REPORTS_ROOT.rglob("*.pdf"))
                _register_input_entry(
                    "REPORT",
                    ctx.CONSULTANT_REPORTS_ROOT,
                    "consultant_reports/",
                    metadata={
                        "pdf_count": len(_pdf_files),
                        "sample_files": [p.name for p in _pdf_files[:10]],
                    },
                )
                for _pdf_path in _pdf_files:
                    _register_input_entry(
                        "REPORT_FILE",
                        _pdf_path,
                        _pdf_path.name,
                    )

            update_run_metadata(
                ctx.RUN_MEMORY_DB,
                ctx._run_number,
                input_signature=_build_input_signature(ctx._run_input_entries),
            )
        except Exception as _ri_err:
            log(f"[WARN] Run history input registration error (non-fatal): {_ri_err}")

    # Write to context
    ctx.docs_df = docs_df
    ctx.responses_df = responses_df
    ctx.ged_approver_names = ged_approver_names
    ctx.mapping = mapping
