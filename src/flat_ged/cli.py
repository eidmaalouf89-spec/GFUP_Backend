"""
main.py — GED Flat Builder CLI entry point.

Usage:
  Batch mode (process all documents):
    python main.py --input input/GED_export.xlsx --output output --mode batch

  Batch mode — skip Excel output (fast smoke test, JSON report only):
    python main.py --input input/GED_export.xlsx --output output --mode batch --skip-xlsx

  Single mode (debug one document):
    python main.py --input input/GED_export.xlsx --output output --mode single \
        --numero 248000 --indice A

    Optional: --row-index 1842  (override candidate selection)

Performance path separation:
  batch  — uses read_only=True + SAX streaming + single-pass row grouping
  single — uses read_only=False + full materialisation (needed for cell-ref tracing)
"""

import sys
import time
import argparse
import contextlib
import datetime
from pathlib import Path

from reader      import (open_workbook, open_workbook_fast,
                          read_data_date, read_data_date_fast,
                          read_ged_sheet, parse_ged_header, parse_ged_header_batch,
                          GEDParseError)
from resolver    import (resolve_document, resolve_from_group,
                          print_resolution_report,
                          GEDDocumentSkip, GEDCandidateNotFound)
from transformer import process_document, GEDValidationError
from validator   import check_delay_invariants, check_global_delay_consistency, print_delay_summary
from writer      import (write_flat_ged, write_flat_ged_batch,
                          write_debug_trace_csv, write_run_report)


# ── Timer ─────────────────────────────────────────────────────────────────────

@contextlib.contextmanager
def _timer(label: str):
    t0 = time.time()
    yield
    print(f"[TIMER] {label}: {time.time() - t0:.2f}s")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_valid_numero(val) -> bool:
    """A valid NUMERO is a non-empty, non-zero value."""
    if val is None:
        return False
    s = str(val).strip()
    return s not in ("", "0", "nan", "None")


def _stream_group_rows(
    data_rows_iter,
    base_cols: dict,
) -> tuple[dict, int, int]:
    """Single-pass streaming grouper.

    Iterates data rows exactly once, grouping by (numero, indice).
    Returns:
        groups:         {(numero, indice): [(ged_row_index, row_data), ...]}
        total_rows:     count of data rows scanned
        no_numero_cnt:  count of rows excluded for missing/invalid NUMERO
    """
    col_by_name = {v: k for k, v in base_cols.items()}
    numero_col  = col_by_name.get("NUMERO")
    indice_col  = col_by_name.get("INDICE")

    if numero_col is None or indice_col is None:
        sys.exit("[FAIL] NUMERO or INDICE column not found in GED header.")

    groups        = {}   # (numero, indice) → list of (ridx, row_data)
    total_rows    = 0
    no_numero_cnt = 0
    ridx          = 3    # GED data starts at row 3 (1-indexed Excel row)

    for row_tuple in data_rows_iter:
        total_rows += 1
        row_data    = list(row_tuple)

        numero = row_data[numero_col] if numero_col < len(row_data) else None
        if not _is_valid_numero(numero):
            no_numero_cnt += 1
            ridx += 1
            continue

        indice_val = row_data[indice_col] if indice_col < len(row_data) else None
        indice     = str(indice_val).strip() if indice_val is not None else ""

        key = (numero, indice)
        if key not in groups:
            groups[key] = []
        groups[key].append((ridx, row_data))
        ridx += 1

    return groups, total_rows, no_numero_cnt


# ── Batch mode ────────────────────────────────────────────────────────────────

def run_batch(args, output_dir: Path):
    """Batch mode — streaming fast path.

    Stages:
      1. Open workbook (read_only=True)
      2. Read DATA_DATE via iteration (no direct cell access needed)
      3. Parse GED header (consume rows 1-2 from iterator, no full materialisation)
      4. Single-pass row streaming → group by (numero, indice)
      5. Per-group: resolve → transform → validate
      6. Write output (FLAT_GED.xlsx optional, run_report.json always)
    """
    input_path = str(args.input)
    skip_xlsx  = getattr(args, "skip_xlsx", False)

    print(f"[INFO] Batch mode  |  skip-xlsx: {skip_xlsx}")
    print()

    # ── Stage 1: open ─────────────────────────────────────────────────────────
    with _timer("workbook_open"):
        try:
            wb = open_workbook_fast(input_path)
        except GEDParseError as e:
            sys.exit(str(e))

    # ── Stage 2: DATA_DATE ────────────────────────────────────────────────────
    with _timer("data_date_read"):
        try:
            data_date = read_data_date_fast(wb)
        except GEDParseError as e:
            sys.exit(str(e))
    print(f"[OK] DATA_DATE = {data_date}  (Détails!D15)")

    # ── Stage 3: header ───────────────────────────────────────────────────────
    with _timer("header_parse"):
        try:
            ws_ged = read_ged_sheet(wb)
            base_cols, approver_groups, data_rows_iter = parse_ged_header_batch(ws_ged)
        except GEDParseError as e:
            sys.exit(str(e))
    print(f"[OK] Approver groups detected: {len(approver_groups)}")

    # ── Stage 4: single-pass row scan + grouping ──────────────────────────────
    with _timer("row_scan_and_group"):
        groups, total_rows, no_numero_cnt = _stream_group_rows(data_rows_iter, base_cols)

    # Close the read_only workbook as soon as streaming is done
    wb.close()

    n_docs = len(groups)
    print(f"[INFO] Total GED data rows:        {total_rows}")
    print(f"[INFO] Rows excluded (no NUMERO):  {no_numero_cnt}")
    print(f"[INFO] Unique document codes:      {n_docs}")
    print()

    # ── Stage 5: per-document processing ─────────────────────────────────────
    all_raw_flat = []
    all_ops      = []
    all_debug    = []

    stats = {
        "mode":                    "batch",
        "input_file":              input_path,
        "data_date":               str(data_date),
        "total_rows_scanned":      total_rows,
        "rows_excluded_no_numero": no_numero_cnt,
        "unique_doc_codes":        n_docs,
        "docs_with_duplicates":    0,
        "synthetic_sas_count":     0,
        "pending_sas_count":       0,
        "closure": {
            "MOEX_VISA":             0,
            "ALL_RESPONDED_NO_MOEX": 0,
            "WAITING_RESPONSES":     0,
        },
        "success_count": 0,
        "skipped_count": 0,
        "failure_count": 0,
        "warning_count": 0,
        "failures":      [],
        "timers":        {},
    }

    t_transform = 0.0

    doc_list = list(groups.items())
    with _timer("transform_validate_all"):
        for i, ((numero, indice), grupo) in enumerate(doc_list, 1):
            doc_label = f"{numero}|{indice}"
            t_doc = time.time()
            try:
                # Resolve candidates from pre-grouped rows (O(1) per doc)
                selected, candidates = resolve_from_group(
                    grupo, base_cols, approver_groups, numero, indice
                )
                if len(candidates) > 1:
                    stats["docs_with_duplicates"] += 1

                # Transform
                raw_flat, ops, debug_rows, doc_stats, cycle_state, closure_mode, \
                    eff_end, sas_state, cm_dl_source, global_deadline = \
                    process_document(selected, base_cols, approver_groups, data_date, quiet=True)

                # Validate (business invariants — never skipped)
                check_delay_invariants(ops)
                check_global_delay_consistency(
                    ops, sas_state, closure_mode, cm_dl_source,
                    global_deadline, eff_end,
                )

                # Accumulate output rows
                all_raw_flat.extend(raw_flat)
                all_ops.extend(ops)
                all_debug.extend(debug_rows)

                # Update stats
                if doc_stats["sas_not_called"]:
                    stats["synthetic_sas_count"] += 1
                if sas_state == "PENDING":
                    stats["pending_sas_count"] += 1
                stats["closure"][closure_mode] += 1
                stats["success_count"] += 1

            except (GEDCandidateNotFound, GEDDocumentSkip):
                stats["skipped_count"] += 1

            except (GEDValidationError, Exception) as e:
                stats["failure_count"] += 1
                stats["failures"].append({"doc": doc_label, "reason": str(e)})
                print(f"  [FAIL] {doc_label}: {e}")

            t_transform += time.time() - t_doc

            if i % 100 == 0 or i == n_docs:
                print(f"  [{i}/{n_docs}] processed  "
                      f"(ok={stats['success_count']} fail={stats['failure_count']})")

    print(f"[TIMER] transform_validate_per_doc_total: {t_transform:.2f}s")

    # ── Stage 6: write output ─────────────────────────────────────────────────
    print()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not skip_xlsx:
        with _timer("output_write_xlsx"):
            flat_path = write_flat_ged_batch(output_dir, all_raw_flat, all_ops)
        print(f"[DONE] {flat_path}")
        print(f"       GED_RAW_FLAT:   {len(all_raw_flat)} rows")
        print(f"       GED_OPERATIONS: {len(all_ops)} steps")
        print(f"       (DEBUG_TRACE written separately as CSV)")

        with _timer("output_write_debug_csv"):
            csv_path = write_debug_trace_csv(output_dir, all_debug)
        print(f"[DONE] {csv_path}  ({len(all_debug)} rows)")
    else:
        print("[INFO] --skip-xlsx: FLAT_GED.xlsx and DEBUG_TRACE.csv not written")

    with _timer("output_write_json"):
        report_path = write_run_report(output_dir, stats)
    print(f"[DONE] {report_path}")

    print()
    print(f"── Batch summary ─────────────────────────────────────────")
    print(f"  Documents processed:   {n_docs}")
    print(f"  Success:               {stats['success_count']}")
    print(f"  Skipped:               {stats['skipped_count']}")
    print(f"  Failures:              {stats['failure_count']}")
    print(f"  Synthetic SAS:         {stats['synthetic_sas_count']}")
    print(f"  Pending SAS:           {stats['pending_sas_count']}")
    print(f"  Duplicates resolved:   {stats['docs_with_duplicates']}")
    print(f"  Closure — MOEX_VISA:   {stats['closure']['MOEX_VISA']}")
    print(f"  Closure — ALL_RESP:    {stats['closure']['ALL_RESPONDED_NO_MOEX']}")
    print(f"  Closure — WAITING:     {stats['closure']['WAITING_RESPONSES']}")
    print(f"──────────────────────────────────────────────────────────")


# ── Single mode ───────────────────────────────────────────────────────────────

def run_single(args, output_dir: Path):
    """Single/debug mode — full materialisation path.

    Uses read_only=False so cell references (e.g. D15) are accessible
    and the candidate resolution engine can print full GED row detail.
    """
    input_path = str(args.input)
    numero     = args.numero
    indice     = args.indice

    if numero is None or indice is None:
        sys.exit("[FAIL] --mode single requires --numero and --indice.")

    # Open workbook — full mode for single/debug
    try:
        with _timer("workbook_open"):
            wb = open_workbook(input_path)
        with _timer("data_date_read"):
            data_date = read_data_date(wb)
        with _timer("header_parse"):
            ws_ged = read_ged_sheet(wb)
            base_cols, approver_groups, all_rows = parse_ged_header(ws_ged)
    except GEDParseError as e:
        sys.exit(str(e))

    print(f"[OK] DATA_DATE = {data_date}  (Détails!D15)")
    print(f"[OK] Approver groups detected: {len(approver_groups)}")
    print(f"[OK] Target:    NUMERO={numero} | INDICE={indice}")
    print()

    # Resolve candidates (full scan — acceptable in single mode)
    selected, candidates = resolve_document(
        all_rows, base_cols, approver_groups, numero, indice
    )

    # Override selection by row index if requested
    if args.row_index is not None:
        override = next(
            (c for c in candidates if c["ged_row_index"] == args.row_index), None
        )
        if override is None:
            sys.exit(f"[FAIL] --row-index {args.row_index} not found among candidates.")
        for c in candidates:
            if c["ged_row_index"] == args.row_index:
                c["instance_role"]              = "ACTIVE"
                c["instance_resolution_reason"] = "FORCED_BY_ROW_INDEX"
            else:
                c["instance_role"]              = "INACTIVE_OVERRIDE"
                c["instance_resolution_reason"] = "OVERRIDDEN_BY_ROW_INDEX"
        selected = override
        print(f"[INFO] Row index override: using GED row {args.row_index}")

    # Print full resolution report (single mode is verbose)
    print_resolution_report(candidates)

    # Process document
    raw_flat, ops, debug_rows, doc_stats, cycle_state, closure_mode, \
        eff_end, sas_state, cm_dl_source, global_deadline = \
        process_document(selected, base_cols, approver_groups, data_date, quiet=False)

    # Validate
    try:
        check_delay_invariants(ops)
        print_delay_summary(ops)
        result = check_global_delay_consistency(
            ops, sas_state, closure_mode, cm_dl_source, global_deadline, eff_end
        )
        if result == "PASS":
            print(f"[PASS] Global delay consistency verified")
            print(f"       cycle_state: {cycle_state}  closure_mode: {closure_mode}")
            print(f"       effective_cycle_end_date: {eff_end}")
            print(f"       total delay: {ops[-1]['cumulative_delay_days']} days")
    except GEDValidationError as e:
        sys.exit(str(e))

    # Write output
    output_dir.mkdir(parents=True, exist_ok=True)
    with _timer("output_write_xlsx"):
        flat_path = write_flat_ged(output_dir, raw_flat, ops, debug_rows)

    stats = {
        "mode":                    "single",
        "input_file":              input_path,
        "data_date":               str(data_date),
        "numero":                  str(numero),
        "indice":                  indice,
        "total_rows_scanned":      len(all_rows) - 2,
        "rows_excluded_no_numero": 0,
        "unique_doc_codes":        1,
        "docs_with_duplicates":    1 if len(candidates) > 1 else 0,
        "synthetic_sas_count":     1 if doc_stats["sas_not_called"] else 0,
        "pending_sas_count":       1 if sas_state == "PENDING" else 0,
        "closure": {
            "MOEX_VISA":             1 if closure_mode == "MOEX_VISA" else 0,
            "ALL_RESPONDED_NO_MOEX": 1 if closure_mode == "ALL_RESPONDED_NO_MOEX" else 0,
            "WAITING_RESPONSES":     1 if closure_mode == "WAITING_RESPONSES" else 0,
        },
        "success_count": 1,
        "skipped_count": 0,
        "failure_count": 0,
        "warning_count": 0,
        "failures":      [],
    }
    with _timer("output_write_json"):
        report_path = write_run_report(output_dir, stats)

    print()
    print(f"[DONE] {flat_path}")
    print(f"       GED_RAW_FLAT:   {len(raw_flat)} rows")
    print(f"       GED_OPERATIONS: {len(ops)} steps")
    print(f"       DEBUG_TRACE:    {len(debug_rows)} rows")
    print(f"[DONE] {report_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="GED Flat Builder — converts a GED Excel export to FLAT_GED.xlsx",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument(
        "--input", required=True,
        help="Path to GED_export.xlsx",
    )
    p.add_argument(
        "--output", default="output",
        help="Output directory (default: output/)",
    )
    p.add_argument(
        "--mode", choices=["batch", "single"], default="batch",
        help="batch = all documents | single = one document (debug)",
    )
    p.add_argument(
        "--numero", type=int, default=None,
        help="[single mode] Document NUMERO",
    )
    p.add_argument(
        "--indice", type=str, default=None,
        help="[single mode] Document INDICE (e.g. A, B, C)",
    )
    p.add_argument(
        "--row-index", type=int, default=None, dest="row_index",
        help="[single mode] Override candidate selection by GED row index",
    )
    p.add_argument(
        "--skip-xlsx", action="store_true", dest="skip_xlsx",
        help="[batch mode] Skip FLAT_GED.xlsx; write run_report.json only. "
             "Use for smoke tests and validation runs.",
    )
    return p.parse_args()


def main():
    args       = parse_args()
    output_dir = Path(args.output)

    print(f"[INFO] Input:  {args.input}")
    print(f"[INFO] Output: {output_dir}")
    print(f"[INFO] Mode:   {args.mode}")
    print()

    if args.mode == "batch":
        run_batch(args, output_dir)
    else:
        run_single(args, output_dir)


if __name__ == "__main__":
    main()
