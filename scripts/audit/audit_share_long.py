"""audit_share_long.py — share_contractor_in_long_chains for one or all
contractors. Surfaces the AMP 199% bug.

Reports four numbers per contractor:
  D1   total_delay_in_long  (sum of chain.totals.delay_days over long chains)
  E2_NUM_DORMANT  contractor_delay_in_long WITH dormant extension (current code)
  E2_NUM_NO_DORMANT  contractor_delay_in_long WITHOUT dormant extension (control)
  E2_SHARE  current code's share value (numerator/denominator)

Convergence rule (custom):
  PASS if E2_SHARE <= 1.0
  FAIL if E2_SHARE > 1.0  → flagged as the 199% pathology

The audit script returns 1 if ANY contractor exceeds 1.0.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    audit_main, filter_emetteur, render_stage_table, resolve_canonical,
)

METRIC = "share_contractor_in_long_chains"


def _build_dormant_map(dernier_filt, ref_today):
    from reporting.contractor_quality import _dormant_list  # noqa: WPS433
    dormant: dict = {}
    for d in (_dormant_list(dernier_filt, "REF", ref_today)
              + _dormant_list(dernier_filt, "SAS REF", ref_today)):
        nm = str(d.get("numero", "")).strip()
        if nm:
            dormant[nm] = max(
                dormant.get(nm, 0),
                int(d.get("days_dormant", 0)),
            )
    return dormant


def compute(ctx, code, shared):
    from reporting.contractor_quality import (  # noqa: WPS433
        _chains_for_contractor, _contractor_delay_for_chain,
    )

    chain_timelines = shared["chain_timelines"]
    canonical = resolve_canonical(code)
    docs = filter_emetteur(ctx.docs_df, code, apply_legacy=True)
    dernier = filter_emetteur(ctx.dernier_df, code, apply_legacy=True)

    chains = _chains_for_contractor(docs, chain_timelines)
    long_chains = [ch for ch in chains if ch.get("chain_long")]

    ref_today = ctx.data_date or date.today()
    dormant = _build_dormant_map(dernier, ref_today)

    total_delay_in_long = sum(
        (ch.get("totals") or {}).get("delay_days", 0) for ch in long_chains
    )
    contractor_delay_with = sum(
        _contractor_delay_for_chain(ch, canonical, code, dormant)
        for ch in long_chains
    )
    contractor_delay_without = sum(
        _contractor_delay_for_chain(ch, canonical, code, None)
        for ch in long_chains
    )
    share_with = (contractor_delay_with / total_delay_in_long
                  if total_delay_in_long > 0 else 0.0)
    share_without = (contractor_delay_without / total_delay_in_long
                     if total_delay_in_long > 0 else 0.0)

    flag = "OVER 100% (199% bug)" if share_with > 1.0 else "ok"

    return [
        ("D1_DENOM", "sum chain.totals.delay_days in long_chains",
         total_delay_in_long, ""),
        ("E2_NUM_NO_DORMANT", "contractor_delay_in_long (no dormant ext)",
         contractor_delay_without, ""),
        ("E2_NUM_DORMANT", "contractor_delay_in_long (current code)",
         contractor_delay_with, f"flag={flag}"),
        ("E2_SHARE", "share_contractor_in_long_chains",
         round(share_with, 4), f"control_no_dormant={share_without:.4f}"),
    ]


# Override convergence: standard table compares all values for equality.
# For this metric, equality is wrong — we want share_with <= 1.0. So we
# implement a custom main below instead of relying on audit_main's logic.

def _main():
    """Custom driver: standard table, but the convergence rule is share <= 1.0."""
    from _common import (  # noqa: WPS433
        get_contractor_codes, load_chain_timelines_tolerant, load_ctx,
    )
    import argparse

    ap = argparse.ArgumentParser(description="Phase 0 audit — " + METRIC)
    ap.add_argument("--contractor", default=None)
    args = ap.parse_args()

    ctx = load_ctx()
    chain_timelines, warns = load_chain_timelines_tolerant()
    shared = {"chain_timelines": chain_timelines}
    contractors = [args.contractor] if args.contractor else get_contractor_codes()

    any_bad = False
    for code in contractors:
        try:
            stages = compute(ctx, code, shared)
        except Exception as exc:
            print(f"=== AUDIT: {METRIC} for contractor={code} ===")
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            print(f"CONVERGENCE: ERROR")
            any_bad = True
            print()
            continue
        # Find the share value
        share = None
        for c, _lbl, val, _note in stages:
            if c == "E2_SHARE":
                share = val
                break
        text, _converges, _ = render_stage_table(METRIC, code, stages)
        print(text)
        # Override convergence verdict for this metric
        if share is not None and share > 1.0:
            print(f"VERDICT: 199% PATHOLOGY (share={share:.4f}>1.0)")
            any_bad = True
        else:
            print("VERDICT: share<=1.0 ok")
        print()

    for w in warns:
        print(f"WARN: {w}")
    return 1 if any_bad else 0


if __name__ == "__main__":
    sys.exit(_main())
