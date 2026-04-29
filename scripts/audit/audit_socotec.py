"""audit_socotec.py — SOCOTEC FAV/SUS/DEF counts and SUS rate per contractor.

Stages:
  C5   ctx.workflow_engine.responses_df where approver_canonical=='Bureau de Contrôle'
       AND status_clean.notna AND date_answered.notna, doc_ids in legacy-filtered emetteur
  E2   contractor_quality.kpis.socotec_sus_rate.value (back-derived count)

Note: Bureau de Contrôle is NOT an exception_approver, so C3 ≡ C5 here.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import audit_main, filter_emetteur  # noqa: E402

METRIC = "SOCOTEC SUS count"


def compute(ctx, code, shared):
    docs = filter_emetteur(ctx.docs_df, code, apply_legacy=True)
    doc_ids = set(docs["doc_id"]) if docs is not None and not docs.empty else set()
    we_rdf = ctx.workflow_engine.responses_df

    soc_all = we_rdf[
        (we_rdf["approver_canonical"] == "Bureau de Contrôle")
        & we_rdf["status_clean"].notna()
        & we_rdf["date_answered"].notna()
        & we_rdf["doc_id"].isin(doc_ids)
    ]
    answered_total = len(soc_all)
    fav_count = int((soc_all["status_clean"] == "FAV").sum())
    sus_count = int((soc_all["status_clean"] == "SUS").sum())
    def_count = int((soc_all["status_clean"] == "DEF").sum())

    sus_rate = (sus_count / answered_total) if answered_total else None
    rate_str = "n/a" if sus_rate is None else f"{sus_rate:.4f}"

    return [
        ("C5", "SOCOTEC answered (legacy-filtered)", answered_total, ""),
        ("C5_FAV", "FAV count", fav_count, ""),
        ("C5_SUS", "SUS count", sus_count, f"sus_rate={rate_str}"),
        ("C5_DEF", "DEF count", def_count, ""),
    ]


if __name__ == "__main__":
    sys.exit(audit_main(METRIC, compute))
