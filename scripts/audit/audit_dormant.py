"""audit_dormant.py — Dormant REF and Dormant SAS REF counts per contractor.

Stages:
  C7   _visa_global == 'REF' / 'SAS REF' on dernier (legacy-filtered)
  E2   build_contractor_quality dormant_ref / dormant_sas_ref list lengths
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import audit_main, filter_emetteur  # noqa: E402

METRIC = "Dormant REF + Dormant SAS REF"


def compute(ctx, code, shared):
    from reporting.contractor_quality import _dormant_list  # noqa: WPS433

    dernier_filt = filter_emetteur(ctx.dernier_df, code, apply_legacy=True)
    if dernier_filt is None or dernier_filt.empty:
        c7_ref = 0
        c7_sas = 0
    elif "_visa_global" in dernier_filt.columns:
        c7_ref = int((dernier_filt["_visa_global"] == "REF").sum())
        c7_sas = int((dernier_filt["_visa_global"] == "SAS REF").sum())
    else:
        c7_ref = 0
        c7_sas = 0

    ref_today = ctx.data_date or date.today()
    e2_ref = len(_dormant_list(dernier_filt, "REF", ref_today))
    e2_sas = len(_dormant_list(dernier_filt, "SAS REF", ref_today))

    return [
        ("C7_REF", "_visa_global == 'REF' on dernier (filt)", c7_ref, ""),
        ("E2_REF", "build_contractor_quality.dormant_ref length", e2_ref, ""),
        ("C7_SAS", "_visa_global == 'SAS REF' on dernier (filt)", c7_sas, ""),
        ("E2_SAS", "build_contractor_quality.dormant_sas_ref length", e2_sas, ""),
    ]


if __name__ == "__main__":
    sys.exit(audit_main(METRIC, compute))
