"""audit_ref.py — REF event count (full track, all approvers) for one or all
contractors.

REF events are MOEX REFs; SAS REFs are tracked separately (audit_sas_ref.py).
A REF here is: completed MOEX response where status_clean=='REF'.

Stages:
  B1   GED_OPERATIONS rows step_type=='MOEX' AND is_completed AND status_clean=='REF'
  C3   ctx.responses_df rows approver_canonical contains MOEX/GEMO AND status_clean=='REF'
  C5   ctx.workflow_engine.responses_df same filter (MOEX is NOT exception_approver
       so this should equal C3)
  E5   aggregator.compute_contractor_summary visa_ref count for this emetteur (dernier only)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    audit_main, filter_emetteur, load_flat_ops_df,
)

METRIC = "REF count (MOEX-track)"


def compute(ctx, code, shared):
    # ── B1: GED_OPERATIONS ──────────────────────────────────────
    ops = load_flat_ops_df()
    moex_b1 = ops[
        (ops["emetteur"] == code)
        & (ops["step_type"] == "MOEX")
        & (ops["is_completed"].astype(str).str.lower() == "true")
        & (ops["status_clean"] == "REF")
    ]
    b1_count = len(moex_b1)

    # ── C3 / C5 ────────────────────────────────────────────────
    docs = filter_emetteur(ctx.docs_df, code, apply_legacy=True)
    doc_ids = set(docs["doc_id"]) if docs is not None and not docs.empty else set()
    rdf = ctx.responses_df
    we_rdf = ctx.workflow_engine.responses_df

    def _is_moex(canonical: str) -> bool:
        s = str(canonical or "").upper()
        return any(kw in s for kw in ("MOEX", "GEMO", "OEUVRE"))

    c3_rows = rdf[
        rdf["doc_id"].isin(doc_ids)
        & rdf["status_clean"].fillna("").eq("REF")
        & rdf["approver_canonical"].fillna("").map(_is_moex)
    ]
    c5_rows = we_rdf[
        we_rdf["doc_id"].isin(doc_ids)
        & we_rdf["status_clean"].fillna("").eq("REF")
        & we_rdf["approver_canonical"].fillna("").map(_is_moex)
    ]
    c3_count = len(c3_rows)
    c5_count = len(c5_rows)

    # ── E5: aggregator visa_ref over dernier ───────────────────
    dernier_filt = filter_emetteur(ctx.dernier_df, code, apply_legacy=True)
    if dernier_filt is None or dernier_filt.empty:
        e5_count = 0
    elif "_visa_global" in dernier_filt.columns:
        e5_count = int((dernier_filt["_visa_global"] == "REF").sum())
    else:
        # Fallback to the engine
        we = ctx.workflow_engine
        e5_count = sum(
            1 for did in dernier_filt["doc_id"]
            if (we.compute_visa_global_with_date(did)[0] == "REF")
        )

    return [
        ("B1", "FLAT_GED MOEX completed REF", b1_count, ""),
        ("C3", "ctx.responses_df MOEX REF (legacy-filt doc_ids)", c3_count, ""),
        ("C5", "workflow_engine.responses_df MOEX REF", c5_count, ""),
        ("E5", "_visa_global == 'REF' on dernier (legacy-filt)", e5_count, "dernier-only"),
    ]


if __name__ == "__main__":
    sys.exit(audit_main(METRIC, compute))
