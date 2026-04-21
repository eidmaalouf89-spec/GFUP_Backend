"""
Stage 6: Report memory integration.

Init DB, load persisted responses, ingest new reports from consultant_match_report.xlsx,
and build effective responses by merging GED responses with report memory.
"""

import pandas as pd
from pathlib import Path
from report_memory import (
    init_report_memory_db,
    sha256_file,
    is_report_already_ingested,
    register_ingested_report,
    upsert_report_responses,
    load_persisted_report_responses,
)
from effective_responses import build_effective_responses
from run_memory import update_run_metadata
from pipeline.utils import _safe_console_print


def stage_report_memory(ctx, log):
    """
    Report memory integration stage.

    Reads from ctx:
        - responses_df
        - _run_number
        - RUN_MEMORY_DB, REPORT_MEMORY_DB, CONSULTANT_MATCH_REPORT, CONSULTANT_REPORTS_ROOT

    Writes to ctx:
        - persisted_df
        - effective_responses_df
    """
    responses_df = ctx.responses_df
    _run_number = ctx._run_number
    RUN_MEMORY_DB = ctx.RUN_MEMORY_DB
    REPORT_MEMORY_DB = ctx.REPORT_MEMORY_DB
    CONSULTANT_MATCH_REPORT = ctx.CONSULTANT_MATCH_REPORT
    CONSULTANT_REPORTS_ROOT = ctx.CONSULTANT_REPORTS_ROOT

    _safe_console_print("\n[7a/7] Report memory integration...")

    # ── Step 1: Init DB ───────────────────────────────────────────────────────
    init_report_memory_db(REPORT_MEMORY_DB)
    log(f"Report memory DB: {REPORT_MEMORY_DB}")

    # ── Step 2: Load previously persisted responses ───────────────────────────
    persisted_df = load_persisted_report_responses(REPORT_MEMORY_DB)
    log(f"Persisted report responses loaded: {len(persisted_df)}")

    # ── Step 3: Check for new reports in consultant_match_report.xlsx ─────────
    # This file is produced by consultant_integration.py.  If it exists and
    # contains rapport_ids not yet in the DB, we persist them now so the
    # current run already benefits from the latest consultant data.
    if CONSULTANT_MATCH_REPORT.exists():
        log(f"Checking {CONSULTANT_MATCH_REPORT.name} for new consultant responses...")
        try:
            match_df = pd.read_excel(str(CONSULTANT_MATCH_REPORT))

            # Keep only rows with a valid matched doc_id
            match_df = match_df[
                match_df["Matched GED doc_id"].notna() &
                (match_df["Matched GED doc_id"].astype(str).str.strip() != "")
            ].copy()

            # Canonical source → GED approver name mapping
            _src_canonical = {
                "LE_SOMMER":  "AMO HQE LE SOMMER",
                "LESOMMER":   "AMO HQE LE SOMMER",
                "AVLS":       "ACOUSTICIEN AVLS",
                "TERRELL":    "BET STR-TERRELL",
                "SOCOTEC":    "SOCOTEC",
                "BC_SOCOTEC": "SOCOTEC",
            }
            def _to_canonical(src: str) -> str:
                upper = src.upper().replace(" ", "_").replace("-", "_")
                for k, v in _src_canonical.items():
                    if k in upper:
                        return v
                return src

            # Group by rapport_id to process file-by-file
            new_rapport_ids_found = 0
            new_responses_persisted = 0

            for rapport_id, group in match_df.groupby("Rapport ID"):
                rapport_id_str = str(rapport_id).strip()

                # Compute hash: try real PDF first, fall back to sentinel
                file_hash = None
                if CONSULTANT_REPORTS_ROOT.exists():
                    for pdf_path in CONSULTANT_REPORTS_ROOT.rglob("*.pdf"):
                        if rapport_id_str in pdf_path.stem or rapport_id_str in pdf_path.name:
                            try:
                                file_hash = sha256_file(str(pdf_path))
                            except OSError:
                                pass
                            break
                if file_hash is None:
                    file_hash = f"BOOTSTRAP::{rapport_id_str}"

                # Skip if already ingested under this hash
                if is_report_already_ingested(REPORT_MEMORY_DB, file_hash):
                    continue

                new_rapport_ids_found += 1
                log(f"  New rapport: {rapport_id_str}")

                # Build persistence-ready DataFrame for this batch
                records = []
                for _, row in group.iterrows():
                    src = str(row.get("Consultant Source", "")).strip()
                    records.append({
                        "consultant":           _to_canonical(src),
                        "doc_id":               str(row.get("Matched GED doc_id", "")).strip(),
                        "report_status":        str(row.get("STATUT_NORM",  "") or "").strip() or None,
                        "report_response_date": str(row.get("DATE_FICHE",   "") or "").strip() or None,
                        "report_comment":       str(row.get("COMMENTAIRE",  "") or "").strip() or None,
                        "source_filename":      rapport_id_str,
                        "source_file_hash":     file_hash,
                        "match_confidence":     str(row.get("Confidence",   "") or "").strip() or None,
                        "match_method":         str(row.get("Match Method", "") or "").strip() or None,
                    })

                batch_df = pd.DataFrame(records)
                written  = upsert_report_responses(REPORT_MEMORY_DB, batch_df)
                new_responses_persisted += written

                # Register the source file
                source_type = str(group.iloc[0].get("Consultant Source", "UNKNOWN")).strip()
                is_sentinel = file_hash.startswith("BOOTSTRAP::")
                register_ingested_report(
                    db_path          = REPORT_MEMORY_DB,
                    report_type      = source_type,
                    source_filename  = rapport_id_str,
                    source_file_hash = file_hash,
                    row_count        = len(records),
                    status           = "INGESTED_BOOTSTRAP" if is_sentinel else "INGESTED",
                )

            log(
                f"  New rapport_ids ingested: {new_rapport_ids_found} "
                f"({new_responses_persisted} rows persisted)"
            )

            # ── Step 4: Reload from DB after any new ingestion ─────────────────
            if new_rapport_ids_found > 0:
                persisted_df = load_persisted_report_responses(REPORT_MEMORY_DB)
                log(f"  Persisted responses after new ingestion: {len(persisted_df)}")

        except Exception as _rm_err:
            # Report memory is an enrichment layer — never block the main pipeline
            _safe_console_print(
                f"  [WARN] Report memory ingestion error (non-fatal): {_rm_err}"
            )
            import traceback as _tb
            _tb.print_exc()
    else:
        log(f"  {CONSULTANT_MATCH_REPORT.name} not found — skipping new report ingestion")

    # ── Step 5: Build effective responses ─────────────────────────────────────
    # Merge GED responses (source of truth for structure) with report memory
    # (fills in answers that GED still shows as pending).
    if _run_number is not None:
        try:
            _report_memory_hash = None
            _report_memory_path = Path(REPORT_MEMORY_DB)
            if _report_memory_path.exists():
                _report_memory_hash = sha256_file(str(_report_memory_path))
            update_run_metadata(
                RUN_MEMORY_DB,
                _run_number,
                report_memory_snapshot_hash=_report_memory_hash,
            )
        except Exception as _rm_meta_err:
            log(f"[WARN] Run history report-memory snapshot error (non-fatal): {_rm_meta_err}")

    effective_responses_df = build_effective_responses(responses_df, persisted_df)

    upgraded_count = int(effective_responses_df.get("report_memory_applied", pd.Series(dtype=bool)).sum()) \
        if "report_memory_applied" in effective_responses_df.columns else 0
    log(
        f"Effective responses built: {len(effective_responses_df)} rows "
        f"({upgraded_count} upgraded from PENDING→ANSWERED via report memory)"
    )

    # Write to ctx
    ctx.persisted_df = persisted_df
    ctx.effective_responses_df = effective_responses_df
