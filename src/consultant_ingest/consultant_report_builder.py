"""
consultant_report_builder.py
JANSA VISASIST — Consultant Report Builder
Version 2.0 — April 2026  (integrated into main GF Updater V3 pipeline)

Main entry point for the reporting module.

Usage from Python (package import):
    from src.consultant_ingest import build_consultant_reports
    from pathlib import Path
    summary = build_consultant_reports(
        input_root=Path("input/consultant_reports"),
        output_path=Path("output/consultant_reports.xlsx"),
    )
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Package-relative imports
# ---------------------------------------------------------------------------

from .lesommer_ingest import ingest_lesommer_folder
from .avls_ingest     import ingest_avls_folder
from .terrell_ingest  import ingest_terrell_folder
from .socotec_ingest  import ingest_socotec_folder

from .consultant_transformers import (
    transform_lesommer_records,
    transform_avls_records,
    transform_terrell_records,
    transform_socotec_records,
)
from .consultant_excel_exporter import export_workbook

# ---------------------------------------------------------------------------
# Folder routing — deterministic by folder name
# ---------------------------------------------------------------------------

FOLDER_MAP = {
    "lesommer": "AMO HQE",
    "avls":     "BET Acoustique AVLS",
    "terrell":  "BET Structure TERRELL",
    "socotec":  "socotec",
}

OUTPUT_FILENAME = "consultant_reports.xlsx"


# ---------------------------------------------------------------------------
# Ingestion wrapper
# ---------------------------------------------------------------------------

def _find_folder(input_root: Path, subfolder_name: str) -> Path | None:
    """
    Find a consultant subfolder inside input_root.
    Case-insensitive search to tolerate minor OS-level naming differences.
    """
    target = subfolder_name.lower()
    for child in input_root.iterdir():
        if child.is_dir() and child.name.lower() == target:
            return child
    logger.warning("Subfolder not found in '%s': '%s'", input_root, subfolder_name)
    return None


def _ingest_consultant(
    key: str,
    ingest_fn,
    input_root: Path,
) -> tuple[list[dict], list[dict]]:
    """
    Locate the consultant folder and run its ingest function.
    Returns (records, skipped).
    """
    folder = _find_folder(input_root, FOLDER_MAP[key])
    if folder is None:
        logger.warning("[%s] Folder '%s' not found — 0 records.", key.upper(), FOLDER_MAP[key])
        return [], []

    pdf_count = len(list(folder.glob("*.pdf")))
    logger.info("[%s] Found %d PDF(s) in '%s'", key.upper(), pdf_count, folder)

    records, skipped = ingest_fn(folder)

    logger.info(
        "[%s] Ingested %d records | %d files skipped",
        key.upper(), len(records), len(skipped)
    )
    for s in skipped:
        logger.warning("  SKIP [%s] %s  (reason: %s)", key.upper(), s.get("file"), s.get("reason"))

    return records, skipped


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_consultant_reports(
    input_root:   Path,
    output_path:  Path | None = None,
    output_root:  Path | None = None,
) -> dict:
    """
    Full pipeline: ingest → transform → export.

    Parameters
    ----------
    input_root   : path to 'input/consultant_reports' folder
    output_path  : explicit output .xlsx path (preferred, new API)
    output_root  : legacy parameter — if set, output_path = output_root / "consultant_reports.xlsx"
                   Ignored when output_path is given directly.

    Returns
    -------
    dict with keys:
        output_path   : Path to generated workbook
        counts        : dict[consultant_key → int] row counts per sheet
        skipped_total : total files skipped across all consultants
        ls_rows       : list of Le Sommer transformed rows
        avls_rows     : list of AVLS transformed rows
        terrell_rows  : list of Terrell transformed rows
        socotec_rows  : list of Socotec transformed rows
    """
    # Resolve output path
    if output_path is None:
        if output_root is not None:
            output_path = output_root / OUTPUT_FILENAME
        else:
            raise ValueError("Must supply either output_path or output_root")

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("=" * 70)
    logger.info("JANSA VISASIST — Consultant Report Builder")
    logger.info("Run timestamp : %s", run_ts)
    logger.info("Input root    : %s", input_root.resolve())
    logger.info("Output path   : %s", output_path.resolve())
    logger.info("=" * 70)

    # ── 1. Ingest ─────────────────────────────────────────────────────────
    ls_raw,      ls_skip      = _ingest_consultant("lesommer", ingest_lesommer_folder, input_root)
    avls_raw,    avls_skip    = _ingest_consultant("avls",     ingest_avls_folder,     input_root)
    terrell_raw, terrell_skip = _ingest_consultant("terrell",  ingest_terrell_folder,  input_root)
    socotec_raw, socotec_skip = _ingest_consultant("socotec",  ingest_socotec_folder,  input_root)

    total_skipped = len(ls_skip) + len(avls_skip) + len(terrell_skip) + len(socotec_skip)

    # ── 2. Transform ─────────────────────────────────────────────────────
    logger.info("Transforming records...")
    ls_rows      = transform_lesommer_records(ls_raw,      run_ts)
    avls_rows    = transform_avls_records(avls_raw,        run_ts)
    terrell_rows = transform_terrell_records(terrell_raw,  run_ts)
    socotec_rows = transform_socotec_records(socotec_raw,  run_ts)

    counts = {
        "RAPPORT_LE_SOMMER": len(ls_rows),
        "RAPPORT_AVLS":       len(avls_rows),
        "RAPPORT_TERRELL":    len(terrell_rows),
        "RAPPORT_SOCOTEC":    len(socotec_rows),
    }
    logger.info("Row counts: %s", counts)

    # ── 3. Export ─────────────────────────────────────────────────────────
    logger.info("Exporting workbook → %s", output_path.resolve())

    export_workbook(
        ls_rows=ls_rows,
        avls_rows=avls_rows,
        terrell_rows=terrell_rows,
        socotec_rows=socotec_rows,
        output_path=output_path,
    )

    # ── Summary ───────────────────────────────────────────────────────────
    logger.info("=" * 70)
    logger.info("BUILD COMPLETE")
    logger.info("  Output  : %s", output_path.resolve())
    total_rows = sum(counts.values())
    logger.info("  Total rows : %d  (skipped files: %d)", total_rows, total_skipped)
    for sheet, count in counts.items():
        logger.info("    %-22s : %d rows", sheet, count)
    logger.info("=" * 70)

    return {
        "output_path":   output_path,
        "counts":        counts,
        "skipped_total": total_skipped,
        "ls_rows":       ls_rows,
        "avls_rows":     avls_rows,
        "terrell_rows":  terrell_rows,
        "socotec_rows":  socotec_rows,
    }


# ---------------------------------------------------------------------------
# Script entry point — runs from project root
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Paths relative to project root (two levels up from this file)
    _HERE = Path(__file__).resolve().parent
    project_root = _HERE.parent.parent   # src/consultant_ingest → src → project root
    input_root  = project_root / "input" / "consultant_reports"
    output_path = project_root / "output" / "consultant_reports.xlsx"

    if not input_root.exists():
        logger.error("Input folder not found: %s", input_root)
        sys.exit(1)

    result = build_consultant_reports(input_root=input_root, output_path=output_path)
    print(f"\nWorkbook written to: {result['output_path'].resolve()}")
    sys.exit(0)
