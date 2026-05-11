"""Audit contractor exclusion: prove the 241-row excluded tag is
'Att Entreprise -- Dans les delais' (on-time), NOT 'Hors delais' (overdue).
Also count Hors-delais rows in the DCC and confirm they are routed to
ENTREPRISE_A_RELANCER, not silently dropped.
"""
from __future__ import annotations
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR / "src"))

import pandas as pd
from reporting.data_loader import load_run_context
from reporting.document_command_center import compute_dcc_tags_bulk
from reporting.counter_attack_builder import (
    TERMINAL_STATES, CONTRACTOR_OVERDUE_TAGS, _safe_str, _merge_sources, _assign_bucket,
)

ctx = load_run_context(BASE_DIR)
dcc_df = compute_dcc_tags_bulk(ctx)
merged = _merge_sources(dcc_df)
if "focus_owner_tier" in merged.columns:
    merged = merged[merged["focus_owner_tier"].map(_safe_str) != "CLOSED"].copy()
merged = merged[~merged["current_state"].map(_safe_str).isin(TERMINAL_STATES)].copy()

# All contractor-related tags in the DCC after filters
contractor_mask = merged["primary_tag"].map(_safe_str).str.startswith("Att Entreprise")
contractor_tags = merged.loc[contractor_mask, "primary_tag"].map(_safe_str).value_counts()

print("All 'Att Entreprise*' tags in filtered DCC:")
for tag, cnt in contractor_tags.items():
    # Print byte-level codepoints to disambiguate Dans vs Hors
    cps = " ".join(f"U+{ord(c):04X}" if ord(c) > 127 else c for c in tag)
    has_hors = "Hors" in tag
    has_dans = "Dans" in tag
    bucket_match = "OVERDUE_SET" if tag in CONTRACTOR_OVERDUE_TAGS else "EXCLUDED"
    label = "Hors delais (overdue)" if has_hors else ("Dans les delais (on-time)" if has_dans else "?")
    print(f"  count={cnt:>4} :: {label:<28} :: routes to {bucket_match}")
    print(f"           tag repr: {tag!r}")
    print(f"           codepoints: {cps}")

# Run the assign step and confirm where Hors-delais rows actually go
merged["_bucket"] = merged.apply(_assign_bucket, axis=1)
hors_only = merged[merged["primary_tag"].map(_safe_str).str.contains("Hors")]
print()
print(f"Hors-delais rows (any variant) in filtered DCC: {len(hors_only)}")
print("  Bucket distribution for those rows:")
print(hors_only["_bucket"].value_counts().to_string())

dans_only = merged[merged["primary_tag"].map(_safe_str).str.contains("Dans les")]
print()
print(f"Dans-les-delais rows in filtered DCC: {len(dans_only)}")
print("  Bucket distribution for those rows:")
print(dans_only["_bucket"].value_counts(dropna=False).to_string())
