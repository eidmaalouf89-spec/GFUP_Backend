"""audit_peer_stats.py — Verify build_contractor_quality_peer_stats matches
the per-contractor distribution computed by audit_share_long / dormant /
sas_ref helpers.

Stages:
  RAW      Per-contractor 5-KPI values computed inline (29 numbers each)
  E3       build_contractor_quality_peer_stats result (median/p25/p75)
  RECOMPUTE  numpy percentiles of RAW (sanity check for E3)

The script verifies that E3 percentiles match a fresh percentile pass over
the RAW values. Convergence: median/p25/p75 must agree across E3 vs
RECOMPUTE for every KPI.

Output is project-wide (not per-contractor); --contractor is ignored.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    BASE_DIR, filter_emetteur, get_contractor_codes,
    load_chain_timelines_tolerant, load_ctx, resolve_canonical,
)

METRIC = "Peer stats (5 KPIs across 29 contractors)"


def _per_contractor_raw(ctx, chain_timelines):
    from reporting.contractor_quality import (  # noqa: WPS433
        _chains_for_contractor, _contractor_delay_for_chain,
        _dormant_list, _sas_refusal_rate, _socotec_sus_rate,
    )

    sas_rates: list = []
    ref_counts: list = []
    pct_longs: list = []
    avg_delays: list = []
    sus_rates: list = []
    ref_today = ctx.data_date or date.today()

    for code in get_contractor_codes():
        canonical = resolve_canonical(code)
        emetteur_docs = filter_emetteur(ctx.docs_df, code, apply_legacy=True)
        emetteur_dernier = filter_emetteur(ctx.dernier_df, code, apply_legacy=True)

        sas_rates.append(_sas_refusal_rate(ctx, emetteur_docs))
        if emetteur_dernier is not None and not emetteur_dernier.empty \
                and "_visa_global" in emetteur_dernier.columns:
            ref_counts.append(int((emetteur_dernier["_visa_global"] == "REF").sum()))
        else:
            ref_counts.append(0)

        chains = _chains_for_contractor(emetteur_docs, chain_timelines)
        n_chains = len(chains)
        n_long = sum(1 for ch in chains if ch.get("chain_long"))
        pct_longs.append(n_long / n_chains if n_chains > 0 else 0.0)

        dormant: dict = {}
        for d in (_dormant_list(emetteur_dernier, "REF", ref_today)
                  + _dormant_list(emetteur_dernier, "SAS REF", ref_today)):
            nm = str(d.get("numero", "")).strip()
            if nm:
                dormant[nm] = max(dormant.get(nm, 0),
                                  int(d.get("days_dormant", 0)))

        delays = [
            _contractor_delay_for_chain(ch, canonical, code, dormant)
            for ch in chains
        ]
        avg_delays.append(float(sum(delays) / len(delays)) if delays else 0.0)

        emetteur_doc_ids = (
            set(emetteur_docs["doc_id"])
            if emetteur_docs is not None and not emetteur_docs.empty
            else None
        )
        sus_rates.append(_socotec_sus_rate(ctx, code, emetteur_doc_ids))

    return {
        "sas_refusal_rate":          sas_rates,
        "dormant_ref_count":         ref_counts,
        "pct_chains_long":           pct_longs,
        "avg_contractor_delay_days": avg_delays,
        "socotec_sus_rate":          sus_rates,
    }


def _percentiles(values, exclude_none=False):
    import numpy as np
    if exclude_none:
        clean = [v for v in values if v is not None]
    else:
        clean = [v if v is not None else 0.0 for v in values]
    if not clean:
        return {"median": 0.0, "p25": 0.0, "p75": 0.0}
    arr = np.array(clean, dtype=float)
    return {
        "median": float(np.percentile(arr, 50)),
        "p25":    float(np.percentile(arr, 25)),
        "p75":    float(np.percentile(arr, 75)),
    }


def _main():
    ctx = load_ctx()
    chain_timelines, warns = load_chain_timelines_tolerant()

    raw = _per_contractor_raw(ctx, chain_timelines)
    recompute = {
        "sas_refusal_rate":          _percentiles(raw["sas_refusal_rate"]),
        "dormant_ref_count":         _percentiles(raw["dormant_ref_count"]),
        "pct_chains_long":           _percentiles(raw["pct_chains_long"]),
        "avg_contractor_delay_days": _percentiles(raw["avg_contractor_delay_days"]),
        "socotec_sus_rate":          _percentiles(raw["socotec_sus_rate"], exclude_none=True),
    }

    from reporting.contractor_quality import build_contractor_quality_peer_stats
    e3 = build_contractor_quality_peer_stats(ctx, chain_timelines=chain_timelines)
    e3.pop("_chain_timelines", None)

    any_div = False
    print("=== AUDIT: " + METRIC + " ===")
    for kpi, e3_val in e3.items():
        rc_val = recompute[kpi]
        equal = (
            abs(e3_val["median"] - rc_val["median"]) < 1e-9
            and abs(e3_val["p25"] - rc_val["p25"]) < 1e-9
            and abs(e3_val["p75"] - rc_val["p75"]) < 1e-9
        )
        verdict = "EQUAL" if equal else "DIVERGES"
        if not equal:
            any_div = True
        print(f"  {kpi}:")
        print(f"    E3 (build_contractor_quality_peer_stats): "
              f"median={e3_val['median']:.4f} p25={e3_val['p25']:.4f} p75={e3_val['p75']:.4f}")
        print(f"    RECOMPUTE (numpy percentiles of raw 29):    "
              f"median={rc_val['median']:.4f} p25={rc_val['p25']:.4f} p75={rc_val['p75']:.4f}")
        print(f"    {verdict}")

    # Also surface raw distributions
    print("\nRaw values per contractor:")
    codes = get_contractor_codes()
    for kpi in raw:
        vals = raw[kpi]
        zipped = list(zip(codes, vals))
        zipped.sort(key=lambda x: (-1 if x[1] is None else x[1]), reverse=True)
        top_5 = zipped[:5]
        print(f"  {kpi} top 5: {[(c, round(v, 4) if isinstance(v, float) else v) for c, v in top_5]}")

    print(f"\nCONVERGENCE: {'ALL EQUAL' if not any_div else 'DIVERGENCE'}")
    for w in warns:
        print(f"WARN: {w}")
    return 1 if any_div else 0


if __name__ == "__main__":
    sys.exit(_main())
