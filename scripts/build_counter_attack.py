"""
Standalone runner for Phase 6A — Counter-Attack Action Kernel.

Builds output/intermediate/COUNTER_ATTACK_ITEMS.csv from the existing
DCC / chain-onion / focus / responses truth. NOT integrated into a
pipeline stage in 6A; consumers (6B/6C) read the produced CSV.

Run:
    python scripts/build_counter_attack.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from reporting.data_loader import load_run_context  # noqa: E402
from reporting.counter_attack_builder import build_counter_attack_items  # noqa: E402


def main() -> int:
    ctx = load_run_context(BASE_DIR)
    out_dir = BASE_DIR / "output" / "intermediate"
    path = build_counter_attack_items(ctx, out_dir)
    print(f"wrote: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
