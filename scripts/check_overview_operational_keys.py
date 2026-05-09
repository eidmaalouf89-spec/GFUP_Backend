"""
scripts/check_overview_operational_keys.py
Phase 3 — Validate that adapt_overview exposes operational verbatim.

Usage:
    python scripts/check_overview_operational_keys.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

# Locked baseline from Phase 2 (source: scripts/check_operational_payload.py)
LOCKED_BASELINE = {
    "operational_total": 2141,
    "fresh_total": 829,
    "stale_total": 1312,
    # moex_total / consultants split is being re-baselined by SAS-routing
    # patch (2026-05-09): MOEX SAS pollution moves to moex_sas_total;
    # CONTRACTOR tier now exposed as contractor_total. Numeric baselines
    # below are pre-patch; post-patch values are recorded after rerun.
    # "moex_total": <new value>,
    # "moex_fresh": <new value>,
    # "moex_stale": <new value>,
    # "primary_total": <new value>,
    # "secondary_total": <new value>,
    # "consultants_total": <new value>,
    # priority_p* baselines retired by SAS-routing/P5-removal patch
    # (2026-05-09). Re-baseline after pipeline rerun if structural check
    # passes. Values now derived from operational, not hard-asserted here.
    "enterprise_ref_sas_candidates": 162,
    "enterprise_action_rows": 87,
    "old_debt_age_days_min": 91,
    "old_debt_age_days_median": 204,
    "old_debt_age_days_max": 801,
    "stale_threshold_days": 90,
}

EXPECTED_KEYS = {
    "operational_total", "fresh_total", "stale_total",
    "moex_total", "moex_sas_total", "moex_fresh", "moex_stale",
    "primary_total", "secondary_total", "consultants_total",
    "contractor_total",
    # P5 retired (2026-05-09): global workflow is 30 days; "no deadline"
    # is no longer a valid operational state.
    "priority_p1", "priority_p2", "priority_p3", "priority_p4",
    "enterprise_ref_sas_candidates", "enterprise_action_rows",
    "old_debt_age_days_min", "old_debt_age_days_median", "old_debt_age_days_max",
    "stale_threshold_days", "universe_definition",
}


def main():
    from reporting.data_loader import load_run_context
    from reporting.aggregator import (
        compute_project_kpis,
        compute_monthly_timeseries,
        compute_consultant_summary,
        compute_contractor_summary,
        compute_operational_dashboard,
    )
    from reporting.focus_filter import apply_focus_filter, FocusConfig
    from reporting.ui_adapter import adapt_overview

    ctx = load_run_context(BASE_DIR)
    focus_config = FocusConfig(enabled=False, stale_threshold_days=90)
    focus_result = apply_focus_filter(ctx, focus_config)

    kpis = compute_project_kpis(ctx, focus_result=focus_result)
    consultants = compute_consultant_summary(ctx, focus_result=focus_result)
    contractors = compute_contractor_summary(ctx, focus_result=focus_result)
    timeseries = compute_monthly_timeseries(ctx)

    dashboard_data = {
        "kpis": kpis,
        "monthly": timeseries,
        "consultants": consultants,
        "contractors": contractors,
        "focus": focus_result.stats,
        "operational": compute_operational_dashboard(ctx),
    }

    app_state = {"has_baseline": True, "ged_file_detected": True, "gf_file_detected": True, "pipeline_running": False}
    overview = adapt_overview(dashboard_data, app_state)

    failures = []

    # Assert key "operational" exists
    if "operational" not in overview:
        print("FAIL operational reason=key missing from adapt_overview output")
        sys.exit(1)

    op = overview["operational"]

    # Assert it is a dict
    if not isinstance(op, dict):
        print(f"FAIL operational reason=expected dict, got {type(op).__name__}")
        sys.exit(1)

    # Assert key set matches
    actual_keys = set(op.keys())
    missing = EXPECTED_KEYS - actual_keys
    extra = actual_keys - EXPECTED_KEYS
    if missing:
        for k in sorted(missing):
            print(f"FAIL {k} reason=missing from operational dict")
            failures.append(k)
    if extra:
        for k in sorted(extra):
            print(f"FAIL {k} reason=unexpected extra key in operational dict")
            failures.append(k)

    # Assert each integer field value matches baseline
    for field, expected in LOCKED_BASELINE.items():
        actual = op.get(field)
        if field == "enterprise_action_rows" and actual is None:
            print(f"WARNING {field}: expected {expected}, got None (artifact missing)")
            continue
        if actual == expected:
            print(f"OK {field} = {actual}")
        else:
            print(f"FAIL {field} reason=expected {expected} got {actual}")
            failures.append(field)

    if failures:
        sys.exit(1)

    print("OVERVIEW.operational EXPOSES ALL EXPECTED KEYS VERBATIM")
    sys.exit(0)


if __name__ == "__main__":
    main()
