"""audit_chains.py — Chain count, chain_long count, attribution_breakdown
sums per contractor.

Stages:
  D2  CHAIN_REGISTER.csv distinct family_keys whose numero matches a BEN doc
  D1  CHAIN_TIMELINE_ATTRIBUTION.json (tolerant) chains for contractor
  E2  contractor_quality._chains_for_contractor result count

Long chains:
  D1.long  count of chains with chain_long==True
  E2.long  contractor_quality long_chains list length
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    BASE_DIR, audit_main, filter_emetteur,
)

METRIC = "Chain count + chain_long count"


def _ben_numeros(ctx, code):
    docs = filter_emetteur(ctx.docs_df, code, apply_legacy=True)
    if docs is None or docs.empty:
        return set()
    nums = set()
    for col in ("numero", "numero_normalized"):
        if col in docs.columns:
            nums |= set(docs[col].dropna().astype(str))
    return nums


def compute(ctx, code, shared):
    import pandas as pd

    chain_timelines = shared["chain_timelines"]
    nums = _ben_numeros(ctx, code)

    # ── D1: chain timelines for this emetteur ─────────────────
    matched = [ch for ch in chain_timelines.values()
               if str(ch.get("numero")) in nums]
    d1_total = len(matched)
    d1_long = sum(1 for ch in matched if ch.get("chain_long"))

    # ── D2: CHAIN_REGISTER count ──────────────────────────────
    reg_path = BASE_DIR / "output" / "chain_onion" / "CHAIN_REGISTER.csv"
    if reg_path.exists():
        reg = pd.read_csv(reg_path, dtype={"family_key": str, "numero": str})
        d2_total = int(reg["numero"].astype(str).isin(nums).sum())
    else:
        d2_total = None

    # ── E2: contractor_quality result ─────────────────────────
    from reporting.contractor_quality import _chains_for_contractor  # noqa: WPS433
    docs = filter_emetteur(ctx.docs_df, code, apply_legacy=True)
    e2_chains = _chains_for_contractor(docs, chain_timelines)
    e2_total = len(e2_chains)
    e2_long = sum(1 for ch in e2_chains if ch.get("chain_long"))

    return [
        ("D2", "CHAIN_REGISTER.csv numeros for emetteur", d2_total, ""),
        ("D1", "CHAIN_TIMELINE_ATTRIBUTION (tolerant) for emetteur", d1_total, ""),
        ("E2", "contractor_quality._chains_for_contractor", e2_total, ""),
        ("D1_LONG", "chain_long==True for emetteur", d1_long, ""),
        ("E2_LONG", "contractor_quality.long_chains length", e2_long, ""),
    ]


if __name__ == "__main__":
    sys.exit(audit_main(METRIC, compute))
