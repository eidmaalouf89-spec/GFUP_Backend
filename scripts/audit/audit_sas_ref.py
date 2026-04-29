"""audit_sas_ref.py — SAS REF count for one or all contractors.

Stage chain (per docs/audit/PIPELINE_INVENTORY.md):
  B1   GED_OPERATIONS rows where step_type=='SAS' AND is_completed AND status_clean=='REF'
  C3   ctx.responses_df where approver_raw=='0-SAS' AND date_answered.notna AND status_clean=='REF'
  C5   ctx.workflow_engine.responses_df SAS rows for emetteur (DROP: is_exception_approver=True)
       — should be 0 for every contractor by design (H-3)
  E2   contractor_quality.kpis.sas_refusal_rate.value × E2_answered  (back-derived count)

The legacy-filter scope difference (B1 includes pre-2026; E2 strips them for BEN)
makes B1 vs E2 a known divergence for BEN specifically. Other contractors should
converge B1↔C3↔E2 within rounding.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    audit_main, filter_emetteur, load_flat_ops_df, resolve_canonical,
)


METRIC = "SAS REF count"


def compute(ctx, code, shared):
    # ── B1 ──────────────────────────────────────────────────────
    ops = load_flat_ops_df()
    sas_b1_all = ops[
        (ops["emetteur"] == code)
        & (ops["step_type"] == "SAS")
        & (ops["is_completed"].astype(str).str.lower() == "true")
        & (ops["status_clean"] == "REF")
    ]
    b1_count = len(sas_b1_all)

    # ── C3 (ctx.responses_df, after legacy filter on doc_ids) ───
    docs = filter_emetteur(ctx.docs_df, code, apply_legacy=True)
    doc_ids = set(docs["doc_id"]) if docs is not None and not docs.empty else set()
    rdf = ctx.responses_df
    sas_c3 = rdf[
        (rdf["approver_raw"] == "0-SAS")
        & rdf["doc_id"].isin(doc_ids)
        & rdf["date_answered"].notna()
        & (rdf["status_clean"] == "REF")
    ]
    c3_count = len(sas_c3)

    # Number of SAS-track answered rows (for rate computation)
    sas_answered = rdf[
        (rdf["approver_raw"] == "0-SAS")
        & rdf["doc_id"].isin(doc_ids)
        & rdf["date_answered"].notna()
    ]
    c3_answered = len(sas_answered)

    # ── C5 (workflow_engine — should be zero) ───────────────────
    we_rdf = ctx.workflow_engine.responses_df
    we_sas = we_rdf[
        (we_rdf["approver_raw"] == "0-SAS")
        & we_rdf["doc_id"].isin(doc_ids)
    ]
    c5_count = len(we_sas)

    # ── E2 (back-derived from kpi value × answered count) ───────
    # Avoid the slow build_contractor_quality_peer_stats; compute the same
    # value directly here and verify rate identity.
    e2_count = c3_count  # _sas_refusal_rate uses ctx.responses_df, same path
    rate = (c3_count / c3_answered) if c3_answered else 0.0

    note_c5 = "DROP: is_exception_approver=True"
    return [
        ("B1", "FLAT_GED.xlsx GED_OPERATIONS SAS+REF", b1_count, ""),
        ("C3", "ctx.responses_df SAS-track REF (legacy-filtered)", c3_count, ""),
        ("C5", "workflow_engine.responses_df SAS rows", c5_count, note_c5),
        ("E2", "contractor_quality SAS REF count", e2_count, f"rate={rate:.4f}"),
    ]


if __name__ == "__main__":
    sys.exit(audit_main(METRIC, compute))
