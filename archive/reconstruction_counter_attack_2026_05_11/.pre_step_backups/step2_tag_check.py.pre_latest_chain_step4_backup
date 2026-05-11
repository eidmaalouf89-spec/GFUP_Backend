"""Step 2 tag diagnostic -- Secondaire expire / MOEX interne tags."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
ARTIFACT = BASE / "output" / "intermediate" / "COUNTER_ATTACK_ITEMS.csv"

STEP1_BUCKETS = {
    "FERMER_MAINTENANT": 687,
    "DECISION_MOEX": 98,
    "ENTREPRISE_A_RELANCER": 107,
    "CONSULTANT_A_ATTAQUER": 146,
}

REMOVED_BUCKETS = ["MOEX_SHAME_INTERNAL", "SECONDAIRE_EXPIRE", "SUJET_REUNION"]

TAG_SEC = "Secondaire expiré"
TAG_MOEX = "MOEX interne"


def main() -> None:
    print("=" * 70)
    print("STEP 2 TAG CHECK -- warning_tags diagnostic")
    print("=" * 70)

    if not ARTIFACT.exists():
        print(f"FAIL: artifact not found at {ARTIFACT}")
        sys.exit(1)

    df = pd.read_csv(
        ARTIFACT,
        dtype={"item_id": "string", "numero": "string", "indice": "string",
               "family_key": "string", "emetteur_code": "string"},
        keep_default_na=False,
    )

    if "warning_tags" not in df.columns:
        print("FAIL: warning_tags column missing from artifact")
        sys.exit(1)

    has_sec = df["warning_tags"].str.contains(TAG_SEC, na=False)
    has_moex = df["warning_tags"].str.contains(TAG_MOEX, na=False)

    total_sec = int(has_sec.sum())
    total_moex = int(has_moex.sum())
    total_both = int((has_sec & has_moex).sum())

    print(f"\nTotal rows with '{TAG_SEC}': {total_sec}")
    print(f"Total rows with '{TAG_MOEX}': {total_moex}")
    print(f"Total rows with BOTH tags:  {total_both}")

    print("\n" + "-" * 70)
    print(f"Per-bucket breakdown for '{TAG_SEC}':")
    print("-" * 70)
    for bucket in STEP1_BUCKETS:
        count = int((has_sec & (df["action_bucket"] == bucket)).sum())
        print(f"  {bucket}: {count}")

    print(f"\nPer-bucket breakdown for '{TAG_MOEX}':")
    for bucket in STEP1_BUCKETS:
        count = int((has_moex & (df["action_bucket"] == bucket)).sum())
        print(f"  {bucket}: {count}")

    print("\n" + "-" * 70)
    print(f"5 example rows with '{TAG_SEC}':")
    print("-" * 70)
    sec_rows = df[has_sec].head(5)
    show_cols = ["numero", "indice", "family_key", "action_bucket",
                 "primary_tag", "warning_tags"]
    if not sec_rows.empty:
        for _, r in sec_rows.iterrows():
            parts = [f"{c}={r.get(c, '')}" for c in show_cols]
            print("  " + " | ".join(parts))
    else:
        print("  (none)")

    print(f"\n5 example rows with '{TAG_MOEX}':")
    moex_rows = df[has_moex].head(5)
    if not moex_rows.empty:
        for _, r in moex_rows.iterrows():
            parts = [f"{c}={r.get(c, '')}" for c in show_cols]
            print("  " + " | ".join(parts))
    else:
        print("  (none)")

    print("\n" + "-" * 70)
    print("INVARIANT CHECKS:")
    print("-" * 70)

    moex_without_sec = int((has_moex & ~has_sec).sum())
    if moex_without_sec == 0:
        print(f"  Subset invariant (MOEX interne => Secondaire expiré): PASS")
    else:
        print(f"  Subset invariant: FAIL ({moex_without_sec} rows have MOEX interne without Secondaire expiré)")

    tags_nonempty = df["warning_tags"].str.strip() != ""
    bucket_empty = df["action_bucket"].str.strip() == ""
    bad = int((tags_nonempty & bucket_empty).sum())
    if bad == 0:
        print("  Non-empty bucket when warning_tags present: PASS")
    else:
        print(f"  Non-empty bucket check: FAIL ({bad} rows have tags but empty bucket)")

    print("\n  Bucket count verification vs Step 1:")
    all_ok = True
    for bucket, expected in STEP1_BUCKETS.items():
        actual = int((df["action_bucket"] == bucket).sum())
        status = "OK" if actual == expected else "FAIL"
        if actual != expected:
            all_ok = False
        print(f"    {bucket}: {actual} (expected {expected}) [{status}]")

    for rb in REMOVED_BUCKETS:
        count = int((df["action_bucket"] == rb).sum())
        status = "OK" if count == 0 else "FAIL"
        if count != 0:
            all_ok = False
        print(f"    {rb}: {count} (expected 0) [{status}]")

    print("\n" + "=" * 70)
    if all_ok and moex_without_sec == 0 and bad == 0:
        print("RESULT: ALL STEP 2 GATES PASSED")
    else:
        print("RESULT: SOME GATES FAILED")
    print("=" * 70)


if __name__ == "__main__":
    main()
