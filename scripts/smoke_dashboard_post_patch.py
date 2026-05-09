"""Smoke: dump the operational dashboard payload after the SAS-routing /
P5-removal patch. Used to capture post-patch baseline counts."""
from __future__ import annotations
import io
import json
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows so universe_definition (∉, ∧) doesn't crash.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))


def main():
    from reporting.data_loader import load_run_context
    from reporting.aggregator import compute_operational_dashboard

    ctx = load_run_context(BASE_DIR)
    op = compute_operational_dashboard(ctx)

    print("\n=== POST-PATCH operational dashboard payload ===")
    for k in sorted(op.keys()):
        print(f"  {k}: {op[k]}")

    # Owner / tier breakdown from dernier_df
    d = ctx.dernier_df
    print("\n=== _focus_owner_tier on dernier_df (full) ===")
    if "_focus_owner_tier" in d.columns:
        print(d["_focus_owner_tier"].value_counts().to_string())
    print("\n=== SAS REF docs by owner tier ===")
    if "_visa_global" in d.columns:
        sas_ref = d[d["_visa_global"] == "SAS REF"]
        print(f"  SAS REF total: {len(sas_ref)}")
        if len(sas_ref) and "_focus_owner_tier" in sas_ref.columns:
            print(sas_ref["_focus_owner_tier"].value_counts().to_string())

    print("\n=== _focus_owner == ['MOEX SAS'] (SAS pending pollution moved off normal MOEX) ===")
    if "_focus_owner" in d.columns:
        is_moex_sas = d["_focus_owner"].apply(
            lambda x: isinstance(x, list) and x == ["MOEX SAS"]
        )
        print(f"  count: {int(is_moex_sas.sum())}")

    print("\n=== Priority distribution (P5 must be 0) ===")
    if "_focus_priority" in d.columns:
        print(d["_focus_priority"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
