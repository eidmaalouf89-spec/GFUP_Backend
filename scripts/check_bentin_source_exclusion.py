from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_loader import ExclusionConfig, SHEET_YEAR_FILTERS
from src.flat_ged.source_exclusions import BentinSourceExclusionPolicy


GED_PATH = ROOT / "input" / "GED_export.xlsx"
REGISTRY_PATH = ROOT / "context" / "source_exclusions" / "remaining bentin.csv"
LEDGER_PATH = ROOT / "output" / "intermediate" / "RAW_GED_SOURCE_EXCLUSIONS.csv"

EXPECTED_RAW_BEN = 912
EXPECTED_INCLUDED = 211
EXPECTED_EXCLUDED = 701

BASE_COLS = {
    0: "NUMERO",
    1: "INDICE",
    2: "Créé le",
    3: "EMETTEUR",
    4: "LOT",
    5: "Libellé du document",
}


def _row(numero, indice, created_at, emetteur="BEN"):
    return [numero, indice, created_at, emetteur, "I031", "Synthetic canary"]


def _read_raw_rows():
    wb = openpyxl.load_workbook(GED_PATH, read_only=True, data_only=True)
    try:
        ws = wb["Doc. sous workflow, x versions"]
        rows = ws.iter_rows(values_only=True)
        header = list(next(rows))
        next(rows)
        base_cols = {idx: value for idx, value in enumerate(header) if value}
        for raw_row_id, row_tuple in enumerate(rows, start=3):
            yield raw_row_id, list(row_tuple), base_cols
    finally:
        wb.close()


def _current_dataset_check():
    policy = BentinSourceExclusionPolicy(REGISTRY_PATH)
    excluded = 0
    for raw_row_id, row, base_cols in _read_raw_rows():
        if policy.should_exclude(raw_row_id, row, base_cols):
            excluded += 1
    summary = policy.summary
    included = (
        summary["included_listed_remaining_bentin"]
        + summary["included_new_after_2026_03_10"]
    )
    checks = {
        "raw BEN total": (summary["raw_ben_total"], EXPECTED_RAW_BEN),
        "BEN included": (included, EXPECTED_INCLUDED),
        "BENTIN_SOURCE_OLD_NOT_LISTED": (excluded, EXPECTED_EXCLUDED),
        "BEN unresolved": (summary["unresolved_ben_rows"], 0),
    }
    return checks, summary


def _future_canaries():
    future_policy = BentinSourceExclusionPolicy(REGISTRY_PATH)
    future_include = not future_policy.should_exclude(
        900001, _row("999999", "Z", dt.date(2026, 3, 11)), BASE_COLS
    )

    old_policy = BentinSourceExclusionPolicy(REGISTRY_PATH)
    old_exclude = old_policy.should_exclude(
        900002, _row("999998", "Z", dt.date(2026, 3, 9)), BASE_COLS
    )

    listed_numero, listed_indice = next(iter(BentinSourceExclusionPolicy(REGISTRY_PATH).registry_keys))
    listed_policy = BentinSourceExclusionPolicy(REGISTRY_PATH)
    listed_include = not listed_policy.should_exclude(
        900003, _row(listed_numero, listed_indice, dt.date(2026, 3, 9)), BASE_COLS
    )

    lgd_not_year_excluded = "LOT 03-GOE-LGD" not in SHEET_YEAR_FILTERS
    config = ExclusionConfig()
    lgd_excluded, reason = config._check_row({
        "gf_sheet_name": "LOT 03-GOE-LGD",
        "emetteur": "LGD",
        "created_at": "2025-01-15",
        "routing_status": "",
        "lot_prefix": "",
    })

    return {
        "synthetic BEN 2026-03-11 not in registry included": future_include,
        "synthetic BEN 2026-03-09 not in registry excluded": old_exclude,
        "synthetic BEN before cutoff but listed included": listed_include,
        "LGD retired year filter inactive": lgd_not_year_excluded,
        "LGD 2025 row not excluded by ExclusionConfig": (not lgd_excluded, reason),
    }


def _ledger_check():
    required = {
        "exclusion_code",
        "exclusion_reason",
        "raw_row_id",
        "source_sheet",
        "NUMERO",
        "INDICE",
        "Créé le",
        "EMETTEUR",
        "LOT",
        "Libellé du document",
        "matched_policy",
        "matched_reference_id",
        "source_module",
    }
    if not LEDGER_PATH.exists():
        return False, f"missing ledger: {LEDGER_PATH}"
    header = LEDGER_PATH.read_text(encoding="utf-8-sig").splitlines()[0].split(",")
    missing = sorted(required - set(header))
    if missing:
        return False, f"missing ledger columns: {missing}"
    count = sum(1 for _ in LEDGER_PATH.open(encoding="utf-8-sig")) - 1
    return count == EXPECTED_EXCLUDED, f"ledger rows={count}"


def main() -> int:
    if not REGISTRY_PATH.exists():
        print(f"FAIL registry missing: {REGISTRY_PATH}")
        return 1

    failures = 0
    checks, summary = _current_dataset_check()
    for name, (observed, expected) in checks.items():
        if observed == expected:
            print(f"OK {name} = {observed}")
        else:
            print(f"FAIL {name} expected {expected} got {observed}")
            failures += 1

    for name, result in _future_canaries().items():
        ok = result[0] if isinstance(result, tuple) else result
        detail = f" ({result[1]})" if isinstance(result, tuple) and result[1] else ""
        if ok:
            print(f"OK {name}{detail}")
        else:
            print(f"FAIL {name}{detail}")
            failures += 1

    ledger_ok, ledger_detail = _ledger_check()
    if ledger_ok:
        print(f"OK source ledger {ledger_detail}")
    else:
        print(f"FAIL source ledger {ledger_detail}")
        failures += 1

    print("SUMMARY", summary)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
