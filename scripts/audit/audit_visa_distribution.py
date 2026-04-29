"""audit_visa_distribution.py — VSO/VAO/REF/SAS REF/HM/Open distribution on
dernier for one or all contractors.

Compares three independent computation paths for the same distribution:
  C7  dernier_df["_visa_global"] (precomputed)
  E5  aggregator.compute_contractor_summary visa_* fields (no legacy filter)
  E2  contractor_quality.build_contractor_quality (legacy filter applied)

Convergence is verified PER-VISA. The header row of each contractor block
shows the dernier count; subsequent rows show per-visa convergence.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    audit_main, filter_emetteur, render_stage_table,
)

METRIC = "Visa distribution (dernier)"


def _visa_counts_from_visa_col(dernier):
    """Return {VSO: int, VAO: int, REF: int, SAS REF: int, HM: int, Open: int}."""
    out = {"VSO": 0, "VAO": 0, "REF": 0, "SAS REF": 0, "HM": 0, "Open": 0}
    if dernier is None or dernier.empty:
        return out
    if "_visa_global" not in dernier.columns:
        return out
    s = dernier["_visa_global"].fillna("Open").replace("", "Open")
    for k in out:
        out[k] = int((s == k).sum())
    out["Open"] += int(((~s.isin(list(out.keys()))) & s.notna()).sum())
    return out


def _visa_counts_from_engine(dernier, we):
    out = {"VSO": 0, "VAO": 0, "REF": 0, "SAS REF": 0, "HM": 0, "Open": 0}
    if dernier is None or dernier.empty or we is None:
        return out
    for did in dernier["doc_id"]:
        v, _ = we.compute_visa_global_with_date(did)
        if v in out:
            out[v] += 1
        else:
            out["Open"] += 1
    return out


def compute(ctx, code, shared):
    """We deviate from the standard render_stage_table here because the
    metric is multi-valued (one row per visa). Each row of the output is
    a stage-by-stage convergence check for one visa label."""
    dernier_filt = filter_emetteur(ctx.dernier_df, code, apply_legacy=True)
    dernier_unfilt = filter_emetteur(ctx.dernier_df, code, apply_legacy=False)

    cnt_filt = _visa_counts_from_visa_col(dernier_filt)
    cnt_unfilt = _visa_counts_from_visa_col(dernier_unfilt)
    cnt_engine = _visa_counts_from_engine(dernier_filt, ctx.workflow_engine)

    rows = [
        ("C2_unfilt", "ctx.dernier_df rows (no legacy filter)",
            len(dernier_unfilt) if dernier_unfilt is not None else 0, ""),
        ("C2_filt", "ctx.dernier_df rows (legacy filter)",
            len(dernier_filt) if dernier_filt is not None else 0, ""),
    ]
    for visa in ("VSO", "VAO", "REF", "SAS REF", "HM", "Open"):
        rows.append(
            (f"C7[{visa}]",
             "_visa_global col",
             cnt_filt.get(visa, 0),
             f"engine={cnt_engine.get(visa, 0)} unfilt={cnt_unfilt.get(visa, 0)}"),
        )
    return rows


if __name__ == "__main__":
    sys.exit(audit_main(METRIC, compute))
