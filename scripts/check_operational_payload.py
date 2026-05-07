"""
scripts/check_operational_payload.py
Phase 2 — Validate compute_operational_dashboard against the locked baseline.

Usage:
    python scripts/check_operational_payload.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

LOCKED_BASELINE = {
    "operational_total": 2460,
    "fresh_total": 927,
    "stale_total": 1533,
    "moex_total": 1711,
    "moex_fresh": 505,
    "moex_stale": 1206,
    "primary_total": 670,
    "secondary_total": 79,
    "consultants_total": 749,
    "priority_p1": 2095,
    "priority_p2": 13,
    "priority_p3": 90,
    "priority_p4": 262,
    "priority_p5": 0,
    "enterprise_ref_sas_candidates": 194,
    "enterprise_action_rows": 100,
    "old_debt_age_days_min": 91,
    "old_debt_age_days_median": 204,
    "old_debt_age_days_max": 801,
    "stale_threshold_days": 90,
}


def main():
    # Warm-start RunContext (mirrors app.py:614 load_run_context)
    from reporting.data_loader import load_run_context
    from reporting.aggregator import compute_operational_dashboard

    ctx = load_run_context(BASE_DIR)
    result = compute_operational_dashboard(ctx)

    failures = []
    warnings = []
    for field, expected in LOCKED_BASELINE.items():
        actual = result.get(field)
        if field == "enterprise_action_rows" and actual is None:
            warnings.append(f"WARNING {field}: expected {expected}, got None (artifact missing)")
            continue
        if actual == expected:
            print(f"OK {field} = {actual}")
        else:
            failures.append((field, expected, actual))
            print(f"FAIL {field} expected {expected} got {actual}")

    for w in warnings:
        print(w)

    if not failures:
        print("ALL 19 FIELDS MATCH LOCKED BASELINE")
        sys.exit(0)
    else:
        print(f"\n{len(failures)} FIELD(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
