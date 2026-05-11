"""Step 1 equality diagnostic -- DCC primary_tag -> Action MOEX bucket.

Verifies the 4 target tag->bucket mappings by running the same full
builder pipeline (merge, filter, assign, dedup) and comparing to the
on-disk artifact. Read-only; does NOT modify any file other than its
own source.

Run:
    python scripts/diag/step1_equality_check.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR / "src"))

import pandas as pd
from reporting.data_loader import load_run_context
from reporting.document_command_center import compute_dcc_tags_bulk
from reporting.counter_attack_builder import (
    TERMINAL_STATES, MOEX_FACILE_TAGS, MOEX_ARBITRAGE_TAGS,
    CONTRACTOR_OVERDUE_TAGS, PRIMARY_TAGS,
    _merge_sources, _safe_str, _norm_key, _assign_bucket, _days_late,
)

ARTIFACT_PATH = BASE_DIR / "output" / "intermediate" / "COUNTER_ATTACK_ITEMS.csv"

MAPPINGS = [
    ("FERMER_MAINTENANT",     lambda t: t in MOEX_FACILE_TAGS),
    ("DECISION_MOEX",         lambda t: t in MOEX_ARBITRAGE_TAGS),
    ("ENTREPRISE_A_RELANCER", lambda t: t in CONTRACTOR_OVERDUE_TAGS),
    ("CONSULTANT_A_ATTAQUER", lambda t: t in PRIMARY_TAGS),
]

REMOVED_BUCKETS = ["MOEX_SHAME_INTERNAL", "SECONDAIRE_EXPIRE", "SUJET_REUNION"]


def main() -> None:
    print("=" * 70)
    print("STEP 1 EQUALITY CHECK -- DCC primary_tag -> Action MOEX bucket")
    print("=" * 70)

    ctx = load_run_context(BASE_DIR)

    # --- Run the same pipeline the builder uses ---
    dcc_df = compute_dcc_tags_bulk(ctx)
    if dcc_df is None or dcc_df.empty:
        print("ERROR: DCC is empty -- cannot run check.")
        sys.exit(1)

    merged = _merge_sources(dcc_df)
    if merged.empty:
        print("ERROR: merged df is empty -- cannot run check.")
        sys.exit(1)

    # focus_owner_tier != CLOSED (same as builder)
    if "focus_owner_tier" in merged.columns:
        merged = merged[merged["focus_owner_tier"].map(_safe_str) != "CLOSED"].copy()

    # Latest indice only (same as builder — canonical ctx.latest_chain_df path)
    lcv = getattr(ctx, "latest_chain_df", None)
    if lcv is not None and not lcv.empty and {"family_key", "latest_indice"}.issubset(lcv.columns):
        valid_keys = set(zip(
            lcv["family_key"].map(_norm_key),
            lcv["latest_indice"].map(_norm_key),
        ))
        fkeys = merged["family_key"].map(_norm_key)
        ikeys = merged["indice"].map(_norm_key)
        mask = [(fk, ik) in valid_keys for fk, ik in zip(fkeys, ikeys)]
        merged = merged[mask].copy()
    elif "latest_indice" in merged.columns:
        li = merged["latest_indice"].map(_norm_key)
        idx = merged["indice"].map(_norm_key)
        merged = merged[(idx == li) | (li == "")].copy()

    # Assign buckets (includes terminal-state exclusion)
    merged["_bucket"] = merged.apply(_assign_bucket, axis=1)

    # Dedup exactly as the builder does
    eligible = merged[merged["_bucket"] != ""].copy()
    if "family_key" in eligible.columns:
        eligible = eligible.drop_duplicates(subset=["family_key"], keep="first")
    if "numero" in eligible.columns and "indice" in eligible.columns:
        eligible = eligible.drop_duplicates(subset=["numero", "indice"], keep="first")

    # days_late > 0 filter (same as builder)
    eligible["_dl"] = eligible.apply(lambda r: _days_late(r["_bucket"], r), axis=1)
    eligible = eligible[eligible["_dl"] > 0].copy()

    print(f"\nDCC rows: {len(dcc_df)}")
    print(f"Merged rows after CLOSED filter: {len(merged)}")
    print(f"Eligible rows after assign+dedup: {len(eligible)}")

    # --- Artifact ---
    if not ARTIFACT_PATH.exists():
        print(f"ERROR: artifact not found at {ARTIFACT_PATH}")
        sys.exit(1)

    art_df = pd.read_csv(
        ARTIFACT_PATH,
        dtype={"item_id": "string", "numero": "string", "indice": "string",
               "family_key": "string", "emetteur_code": "string"},
        keep_default_na=False,
    )
    print(f"Artifact rows: {len(art_df)}")

    print()
    print("-" * 70)
    print("MAPPING EQUALITY (pipeline count vs artifact count):")
    print("-" * 70)

    all_pass = True

    for bucket, predicate in MAPPINGS:
        pipe_rows = eligible[eligible["_bucket"] == bucket].copy()
        art_rows  = art_df[art_df["action_bucket"].map(_safe_str) == bucket].copy()

        pipe_count = len(pipe_rows)
        art_count  = len(art_rows)
        delta = pipe_count - art_count

        status = "OK" if delta == 0 else "FAIL"
        if delta != 0:
            all_pass = False

        print(f"\n  {bucket}")
        print(f"    Pipeline count (assign+dedup): {pipe_count}")
        print(f"    Artifact count:                {art_count}")
        print(f"    Delta:                         {delta}  [{status}]")

        # Sample rows in pipeline but missing from artifact (by family_key)
        if "family_key" in pipe_rows.columns and "family_key" in art_rows.columns:
            art_fk = set(art_rows["family_key"].map(_safe_str).tolist())
            pipe_only = pipe_rows[~pipe_rows["family_key"].map(_safe_str).isin(art_fk)]
            if not pipe_only.empty:
                all_pass = False
                cols = [c for c in ("family_key", "numero", "primary_tag", "current_state")
                        if c in pipe_only.columns]
                print(f"    Pipeline-only rows (up to 5):")
                for _, r in pipe_only.head(5).iterrows():
                    print(f"      {dict(r[cols].items())}")
            else:
                print("    Pipeline-only rows: (empty) OK")
        else:
            print("    (family_key absent; cannot check pipeline-only rows)")

        # Sample rows in artifact whose primary_tag doesn't match
        if "primary_tag" in art_rows.columns:
            wrong = art_rows[~art_rows["primary_tag"].map(_safe_str).map(predicate)]
            if not wrong.empty:
                all_pass = False
                print(f"    Artifact wrong-tag rows (up to 5):")
                for _, r in wrong.head(5).iterrows():
                    print(f"      fk={_safe_str(r.get('family_key'))} tag={_safe_str(r.get('primary_tag'))}")
            else:
                print("    Artifact wrong-tag rows: (empty) OK")
        else:
            print("    (primary_tag absent from artifact)")

    print()
    print("-" * 70)
    print("REMOVED BUCKET COUNTS in artifact (must all be 0):")
    print("-" * 70)
    for b in REMOVED_BUCKETS:
        n = int((art_df["action_bucket"].map(_safe_str) == b).sum()) if "action_bucket" in art_df.columns else 0
        status = "OK" if n == 0 else "FAIL"
        if n != 0:
            all_pass = False
        print(f"  {b}: {n}  [{status}]")

    print()
    print("-" * 70)
    print("TERMINAL-STATE ROWS IN ARTIFACT (must be 0):")
    print("-" * 70)
    if "current_state" in art_df.columns:
        n_terminal = int(art_df["current_state"].map(_safe_str).isin(TERMINAL_STATES).sum())
        status = "OK" if n_terminal == 0 else "FAIL"
        if n_terminal != 0:
            all_pass = False
        print(f"  Terminal-state rows: {n_terminal}  [{status}]")
    else:
        print("  (current_state column absent)")

    print()
    print("-" * 70)
    print("DUPLICATE COUNTS (must all be 0):")
    print("-" * 70)
    if "numero" in art_df.columns and "indice" in art_df.columns:
        dup_ni = int(art_df.duplicated(subset=["numero", "indice"]).sum())
        status = "OK" if dup_ni == 0 else "FAIL"
        if dup_ni != 0:
            all_pass = False
        print(f"  Duplicates by numero+indice: {dup_ni}  [{status}]")
    if "family_key" in art_df.columns:
        dup_fk = int(art_df.duplicated(subset=["family_key"]).sum())
        status = "OK" if dup_fk == 0 else "FAIL"
        if dup_fk != 0:
            all_pass = False
        print(f"  Duplicates by family_key: {dup_fk}  [{status}]")
    if "item_id" in art_df.columns:
        dup_id = int(art_df.duplicated(subset=["item_id"]).sum())
        status = "OK" if dup_id == 0 else "FAIL"
        if dup_id != 0:
            all_pass = False
        print(f"  Duplicates by item_id: {dup_id}  [{status}]")

    print()
    print("-" * 70)
    print("EXCLUDED PRIMARY_TAG COUNTS (not emitted by design):")
    print("-" * 70)
    all_emitted = set(MOEX_FACILE_TAGS) | set(MOEX_ARBITRAGE_TAGS) | set(CONTRACTOR_OVERDUE_TAGS) | set(PRIMARY_TAGS)
    if "primary_tag" in merged.columns:
        non_emitted = merged[~merged["primary_tag"].map(_safe_str).isin(all_emitted)]
        by_tag = non_emitted["primary_tag"].map(_safe_str).value_counts()
        for tag, cnt in by_tag.items():
            print(f"  '{tag}': {cnt}")
        if by_tag.empty:
            print("  (none)")
    else:
        print("  (primary_tag absent from merged df)")

    # --- G-LCV gates (Step 4) ---
    lcv = getattr(ctx, "latest_chain_df", None)

    print()
    print("-" * 70)
    print("G-LCV-1: all artifact rows match ctx.latest_chain_df (numero, latest_indice)")
    print("-" * 70)
    if lcv is None or lcv.empty:
        print("  SKIP: ctx.latest_chain_df is None or empty")
    else:
        lcv_keys = set(zip(
            lcv["numero"].map(_safe_str),
            lcv["latest_indice"].map(_safe_str),
        ))
        art_nums = art_df["numero"].map(_safe_str)
        art_inds = art_df["indice"].map(_safe_str)
        mismatches = [(n, i) for n, i in zip(art_nums, art_inds) if (n, i) not in lcv_keys]
        if len(mismatches) == 0:
            print(f"  Mismatches: 0  [PASS]")
        else:
            all_pass = False
            print(f"  Mismatches: {len(mismatches)}  [FAIL]")
            for n, i in mismatches[:5]:
                print(f"    numero={n} indice={i}")

    print()
    print("-" * 70)
    print("G-LCV-2: no old-indice rows in artifact")
    print("-" * 70)
    if lcv is None or lcv.empty:
        print("  SKIP: ctx.latest_chain_df is None or empty")
    else:
        lcv_lookup = dict(zip(lcv["numero"].map(_safe_str), lcv["latest_indice"].map(_safe_str)))
        offenders = []
        for _, r in art_df.iterrows():
            n = _safe_str(r.get("numero"))
            i = _safe_str(r.get("indice"))
            expected = lcv_lookup.get(n)
            if expected is not None and i != expected:
                offenders.append((n, i, expected))
        if len(offenders) == 0:
            print(f"  Old-indice rows: 0  [PASS]")
        else:
            all_pass = False
            print(f"  Old-indice rows: {len(offenders)}  [FAIL]")
            for n, i, exp in offenders[:5]:
                print(f"    numero={n} indice={i} expected={exp}")

    print()
    print("-" * 70)
    print("G-LCV-3: bucket count baselines (informational)")
    print("-" * 70)
    baselines = {
        "FERMER_MAINTENANT": 687,
        "DECISION_MOEX": 98,
        "ENTREPRISE_A_RELANCER": 107,
        "CONSULTANT_A_ATTAQUER": 146,
    }
    total_baseline = 1038
    total_actual = 0
    for bucket, expected in baselines.items():
        actual = int((art_df["action_bucket"].map(_safe_str) == bucket).sum())
        total_actual += actual
        delta = actual - expected
        if delta != 0:
            print(f"  G-LCV-3 BASELINE DRIFT: bucket={bucket} expected={expected} got={actual}")
        else:
            print(f"  {bucket}: {actual} (expected {expected}) [OK]")
    total_delta = total_actual - total_baseline
    if total_delta != 0:
        print(f"  G-LCV-3 BASELINE DRIFT: bucket=Total expected={total_baseline} got={total_actual}")
    else:
        print(f"  Total: {total_actual} (expected {total_baseline}) [OK]")

    # --- Frozen baseline equality (loaded from step1_baseline.json) ---
    baseline_path = Path(__file__).resolve().parent / "step1_baseline.json"
    print()
    print("-" * 70)
    print("BASELINE EQUALITY (step1_baseline.json vs artifact):")
    print("-" * 70)
    if not baseline_path.exists():
        all_pass = False
        print(f"  FAIL: baseline file not found at {baseline_path}")
    else:
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline = json.load(f)
        for bucket, expected in baseline["buckets"].items():
            actual = int((art_df["action_bucket"].map(_safe_str) == bucket).sum())
            if actual != expected:
                all_pass = False
                print(
                    f"  BASELINE DRIFT: {bucket} {expected} -> {actual}"
                    f" -- Step 1 closure was modified silently."
                    f" See {baseline_path}."
                )
            else:
                print(f"  {bucket}: {actual} (baseline {expected}) [PASS]")

    print()
    print("=" * 70)
    if all_pass:
        print("RESULT: ALL GATES PASSED")
    else:
        print("RESULT: ONE OR MORE GATES FAILED -- see above")
    print("=" * 70)


if __name__ == "__main__":
    main()
