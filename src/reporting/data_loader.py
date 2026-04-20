"""
data_loader.py — Run-centric data access layer
Reads from run_memory.db artifact registry, NOT from input/ directly.
Verifies GED provenance before loading. Falls back to degraded mode if unverifiable.
"""
import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Import existing backend modules (src/ is already in sys.path from app.py)
from read_raw import read_ged
from normalize import load_mapping, normalize_docs, normalize_responses
from version_engine import VersionEngine
from workflow_engine import WorkflowEngine, compute_responsible_party


@dataclass
class RunContext:
    run_number: int
    run_status: str
    run_date: str
    summary_json: dict
    gf_artifact_path: Optional[Path]
    ged_available: bool
    degraded_mode: bool
    docs_df: Optional[pd.DataFrame] = None
    responses_df: Optional[pd.DataFrame] = None
    approver_names: Optional[list] = None
    dernier_df: Optional[pd.DataFrame] = None          # dernier indice docs only
    workflow_engine: Optional[WorkflowEngine] = None
    responsible_parties: Optional[dict] = None          # {doc_id: responsible_party}
    gf_sheets: dict = field(default_factory=dict)       # {sheet_name: {lots, contractor}}
    artifact_paths: dict = field(default_factory=dict)  # {artifact_type: file_path}
    warnings: list = field(default_factory=list)
    data_date: Optional[date] = None                    # from GED Détails sheet
    ged_status_labels: dict = field(default_factory=dict)  # e.g. {"Terrell": {"s1": "VSO", "s2": "OBS", "s3": "REF"}}


# Module-level cache
_cached_context: Optional[RunContext] = None
_cached_run_number: Optional[int] = None


def clear_cache():
    """Call this when a pipeline run completes or the user switches runs."""
    global _cached_context, _cached_run_number
    _cached_context = None
    _cached_run_number = None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _query_db(db_path, sql, params=()):
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _resolve_latest_run(db_path: str) -> Optional[int]:
    """Find latest COMPLETED non-stale run number."""
    rows = _query_db(db_path,
        "SELECT run_number FROM runs "
        "WHERE status='COMPLETED' AND is_stale=0 "
        "ORDER BY run_number DESC LIMIT 1")
    return rows[0]["run_number"] if rows else None


def _get_artifact_path(db_path: str, run_number: int, artifact_type: str) -> Optional[str]:
    rows = _query_db(db_path,
        "SELECT file_path FROM run_artifacts "
        "WHERE run_number=? AND artifact_type=? "
        "ORDER BY created_at DESC LIMIT 1",
        (run_number, artifact_type))
    if rows and rows[0]["file_path"]:
        p = Path(rows[0]["file_path"])
        if p.exists():
            return str(p)
    return None


def _verify_ged_provenance(db_path: str, run_number: int) -> tuple:
    """
    Returns (ged_path, verified: bool).
    Checks if the GED file used for this run still exists and has the same hash.
    """
    rows = _query_db(db_path,
        "SELECT source_path, source_file_hash FROM run_inputs "
        "WHERE run_number=? AND input_type='GED'",
        (run_number,))
    if not rows:
        return None, False
    row = rows[0]
    source_path = row.get("source_path")
    stored_hash = row.get("source_file_hash")
    if not source_path or not Path(source_path).exists():
        return source_path, False
    if not stored_hash:
        return source_path, True  # No hash stored — trust it
    actual_hash = _sha256(source_path)
    return source_path, (actual_hash == stored_hash)


def _get_mapping_path(db_path: str, run_number: int, base_dir: Path) -> Optional[str]:
    """Resolve mapping file: try run provenance first, then fallback to input/."""
    rows = _query_db(db_path,
        "SELECT source_path FROM run_inputs "
        "WHERE run_number=? AND input_type='MAPPING'",
        (run_number,))
    if rows and rows[0]["source_path"] and Path(rows[0]["source_path"]).exists():
        return rows[0]["source_path"]
    # Fallback
    for f in (base_dir / "input").glob("*.xlsx"):
        if "mapping" in f.name.lower():
            return str(f)
    return None


def _read_ged_data_date(ged_path: str) -> Optional[date]:
    """Extract DATA_DATE from the GED workbook's Détails sheet.

    Scans the first 30 rows of any sheet named 'Détails' or 'Details' for a cell
    containing 'Date d\\'extraction' or similar, then reads the adjacent value.
    Returns None if not found.
    """
    import openpyxl
    try:
        wb = openpyxl.load_workbook(ged_path, read_only=True, data_only=True)
        details_sheet = None
        for sn in wb.sheetnames:
            if sn.lower().replace("é", "e").replace("È", "e") in ("details", "détails"):
                details_sheet = wb[sn]
                break
        if details_sheet is None:
            wb.close()
            return None

        for row in details_sheet.iter_rows(min_row=1, max_row=30, max_col=10, values_only=False):
            for cell in row:
                val = str(cell.value or "").lower()
                if "date" in val and ("extraction" in val or "export" in val):
                    # The date value is typically in the next column or the row below
                    # Try adjacent cell first (same row, next col)
                    ws = cell.parent
                    adj = ws.cell(row=cell.row, column=cell.column + 1).value
                    if adj is not None:
                        if isinstance(adj, datetime):
                            wb.close()
                            return adj.date()
                        if isinstance(adj, date):
                            wb.close()
                            return adj
                        try:
                            wb.close()
                            return datetime.strptime(str(adj).strip(), "%d/%m/%Y").date()
                        except Exception:
                            pass
                    # Try cell below
                    below = ws.cell(row=cell.row + 1, column=cell.column).value
                    if below is not None:
                        if isinstance(below, datetime):
                            wb.close()
                            return below.date()
                        if isinstance(below, date):
                            wb.close()
                            return below
                        try:
                            wb.close()
                            return datetime.strptime(str(below).strip(), "%d/%m/%Y").date()
                        except Exception:
                            pass
        wb.close()
    except Exception:
        pass
    return None


def _parse_gf_sheets(gf_path: str) -> dict:
    """
    Parse GF sheet names to extract contractor info.
    Returns: {sheet_name: {"lots": [str], "contractor_code": str, "contractor_name": str}}
    """
    import openpyxl
    wb = openpyxl.load_workbook(gf_path, read_only=True)
    sheets = {}
    for name in wb.sheetnames:
        if name.upper().startswith("OLD"):
            continue
        # Parse: "LOT 41-CVC-AXIMA" -> lots=["41"], code="AXIMA"
        parts = name.replace("LOT ", "").replace("Lot ", "").split("-")
        code = parts[-1].strip() if len(parts) >= 2 else name
        sheets[name] = {
            "lots": [],  # Will be enriched by routing if needed
            "contractor_code": code,
            "contractor_name": code,
        }
    wb.close()
    return sheets


def load_run_context(base_dir: Path, run_number: int = None) -> RunContext:
    """
    Load all data for a specific run. Uses cache if available.

    Steps:
    1. Resolve run number (default: latest COMPLETED non-stale)
    2. Load FINAL_GF artifact path
    3. Verify GED provenance
    4. If GED verified: read GED, normalize, run version engine + workflow engine
    5. If not: degraded mode (GF-only data)
    6. Parse GF sheet structure
    7. Cache and return
    """
    global _cached_context, _cached_run_number

    db_path = str(base_dir / "data" / "run_memory.db")

    if run_number is None:
        run_number = _resolve_latest_run(db_path)
    if run_number is None:
        return RunContext(
            run_number=0, run_status="UNKNOWN", run_date="",
            summary_json={}, gf_artifact_path=None,
            ged_available=False, degraded_mode=True,
            warnings=["No completed run found"],
        )

    # Return cache if same run
    if _cached_context and _cached_run_number == run_number:
        return _cached_context

    warnings = []

    # Get run metadata
    run_rows = _query_db(db_path,
        "SELECT status, completed_at, summary_json FROM runs WHERE run_number=?",
        (run_number,))
    if not run_rows:
        return RunContext(
            run_number=run_number, run_status="NOT_FOUND", run_date="",
            summary_json={}, gf_artifact_path=None,
            ged_available=False, degraded_mode=True,
            warnings=[f"Run {run_number} not found in database"],
        )

    run_meta = run_rows[0]
    summary = {}
    if run_meta.get("summary_json"):
        try:
            summary = json.loads(run_meta["summary_json"])
        except Exception:
            pass

    # Resolve FINAL_GF artifact
    gf_path = _get_artifact_path(db_path, run_number, "FINAL_GF")
    if not gf_path:
        warnings.append(f"FINAL_GF artifact not found for Run {run_number}")

    # Collect all artifact paths
    art_rows = _query_db(db_path,
        "SELECT artifact_type, file_path FROM run_artifacts WHERE run_number=?",
        (run_number,))
    artifact_paths = {}
    for r in art_rows:
        if r["file_path"] and Path(r["file_path"]).exists():
            artifact_paths[r["artifact_type"]] = r["file_path"]

    # Verify GED provenance
    ged_path, ged_verified = _verify_ged_provenance(db_path, run_number)
    ged_available = ged_verified and ged_path is not None
    degraded_mode = not ged_available

    if not ged_available:
        if ged_path:
            warnings.append(f"GED file hash mismatch for Run {run_number} — degraded mode")
        else:
            warnings.append(f"GED file not found for Run {run_number} — degraded mode")

    # Parse GF sheets
    gf_sheets = {}
    if gf_path:
        try:
            gf_sheets = _parse_gf_sheets(gf_path)
        except Exception as e:
            warnings.append(f"Error parsing GF sheets: {e}")

    # Extract DATA_DATE from GED Détails sheet
    data_date_val = None
    if ged_available and ged_path:
        try:
            data_date_val = _read_ged_data_date(ged_path)
            if data_date_val is None:
                warnings.append("DATA_DATE not found in GED Détails sheet")
        except Exception as e:
            warnings.append(f"Error reading DATA_DATE from GED: {e}")

    # Build DataFrames if GED is available
    docs_df = None
    responses_df = None
    approver_names = None
    dernier_df = None
    workflow_engine = None
    responsible_parties = None

    if ged_available:
        try:
            # Get mapping
            mapping_path = _get_mapping_path(db_path, run_number, base_dir)
            if not mapping_path:
                warnings.append("Mapping file not found — using raw approver names")
                mapping = {}
            else:
                mapping = load_mapping(mapping_path)

            # Read and normalize GED
            docs_df, responses_df, approver_names = read_ged(ged_path)
            docs_df = normalize_docs(docs_df, mapping)
            responses_df = normalize_responses(responses_df, mapping)

            # Run version engine
            ve = VersionEngine(docs_df)
            versioned_df = ve.run()
            dernier_df = versioned_df[versioned_df["is_dernier_indice"] == True].copy()

            # Run workflow engine
            workflow_engine = WorkflowEngine(responses_df)

            # Compute responsible parties for dernier docs
            dernier_ids = dernier_df["doc_id"].tolist()
            responsible_parties = compute_responsible_party(workflow_engine, dernier_ids)

            logger.info("RunContext loaded: %d docs, %d dernier, %d responses",
                        len(docs_df), len(dernier_df), len(responses_df))

        except Exception as e:
            warnings.append(f"Error loading GED data: {e}")
            ged_available = False
            degraded_mode = True
            docs_df = None
            responses_df = None

    ctx = RunContext(
        run_number=run_number,
        run_status=run_meta["status"],
        run_date=run_meta.get("completed_at") or "",
        summary_json=summary,
        gf_artifact_path=Path(gf_path) if gf_path else None,
        ged_available=ged_available,
        degraded_mode=degraded_mode,
        docs_df=docs_df,
        responses_df=responses_df,
        approver_names=approver_names,
        dernier_df=dernier_df,
        workflow_engine=workflow_engine,
        responsible_parties=responsible_parties,
        gf_sheets=gf_sheets,
        artifact_paths=artifact_paths,
        warnings=warnings,
        data_date=data_date_val,
        ged_status_labels={},
    )

    # Cache it
    _cached_context = ctx
    _cached_run_number = run_number
    return ctx
