"""
nuke_and_rebuild_run0.py
------------------------
Completely destroys Run 0 (DB records + artifact files + output folder)
so the next `python main.py` execution can rebuild a fresh baseline.

This is a destructive operation. Use when the pipeline code has changed
and the existing Run 0 artifacts are stale or invalid.

Usage:
    cd GFUP_Backend
    python scripts/nuke_and_rebuild_run0.py
"""

import os
import shutil
import sqlite3
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent

sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from run_memory import get_run_dir

# ── Configuration ─────────────────────────────────────────────────────────
DB_PATH     = _PROJECT_ROOT / "data" / "run_memory.db"
RUNS_DIR    = _PROJECT_ROOT / "runs"
OUTPUT_DIR  = _PROJECT_ROOT / "output"
DEBUG_DIR   = OUTPUT_DIR / "debug"


def nuke_run0():
    """Delete all traces of Run 0 from DB and filesystem."""
    print("=" * 64)
    print("NUKE RUN 0 — Complete Destruction")
    print("=" * 64)
    print()

    # ── Step 1: Delete from DB ────────────────────────────────────────────
    if DB_PATH.exists():
        print("[1/4] Deleting Run 0 from database...")
        # FUSE mounts can block sqlite3 from opening files directly.
        # Work around by staging to /tmp, operating, then writing back.
        import tempfile
        tmp_db = Path(tempfile.mktemp(suffix=".db"))
        shutil.copy2(str(DB_PATH), str(tmp_db))
        conn = sqlite3.connect(str(tmp_db))
        conn.execute("PRAGMA foreign_keys=ON")

        # Check what exists
        runs = conn.execute("SELECT run_number, status FROM runs ORDER BY run_number").fetchall()
        if runs:
            print(f"  Existing runs: {[(r[0], r[1]) for r in runs]}")
        else:
            print("  No runs in DB.")

        # Count child records before delete
        for table in ["run_inputs", "run_artifacts", "run_corrections", "run_invalidation_log"]:
            try:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE run_number = 0 "
                    f"OR source_run_number = 0 "
                    f"OR affected_run_number = 0 "
                    f"OR invalidated_by_run_number = 0"
                    if "invalidation" in table
                    else f"SELECT COUNT(*) FROM {table} WHERE run_number = 0"
                    if "source" not in table
                    else f"SELECT COUNT(*) FROM {table} WHERE source_run_number = 0"
                ).fetchone()[0]
                if count > 0:
                    print(f"    {table}: {count} rows to delete")
            except Exception:
                pass

        # CASCADE delete: deleting from runs cascades to all child tables
        conn.execute("DELETE FROM runs WHERE run_number = 0")
        conn.commit()
        print("  Run 0 deleted from DB (cascade to all child tables).")

        # Also delete ALL runs if any exist (clean slate)
        remaining = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        if remaining > 0:
            print(f"  WARNING: {remaining} other runs still exist.")
            print(f"  Deleting ALL runs for a clean slate...")
            conn.execute("DELETE FROM runs")
            conn.commit()
            print(f"  All runs deleted.")

        conn.close()
        # Write modified DB back to the FUSE-mounted location
        shutil.copy2(str(tmp_db), str(DB_PATH))
        tmp_db.unlink(missing_ok=True)
        print("  DB written back to original location.")
    else:
        print("[1/4] No database found — nothing to delete.")

    # ── Step 2: Delete runs/run_0000/ folder ──────────────────────────────
    run0_dir = RUNS_DIR / "run_0000"
    if run0_dir.exists():
        print(f"\n[2/4] Deleting {run0_dir}...")
        shutil.rmtree(run0_dir)
        print(f"  Deleted.")
    else:
        print(f"\n[2/4] {run0_dir} does not exist — skip.")

    # Also nuke entire runs/ dir if it only had run_0000
    if RUNS_DIR.exists():
        remaining_runs = list(RUNS_DIR.iterdir())
        if not remaining_runs:
            shutil.rmtree(RUNS_DIR)
            print(f"  Removed empty runs/ directory.")
        else:
            print(f"  runs/ still has: {[p.name for p in remaining_runs]}")

    # ── Step 3: Clean output/ folder (pipeline artifacts) ─────────────────
    print(f"\n[3/4] Cleaning output/ folder...")
    if OUTPUT_DIR.exists():
        # Delete all .xlsx files in output/ (but preserve subdirectories like repports output/)
        deleted = 0
        for f in OUTPUT_DIR.iterdir():
            if f.is_file() and f.suffix in ('.xlsx', '.md', '.json', '.txt', '.csv'):
                f.unlink()
                deleted += 1
        print(f"  Deleted {deleted} artifact files from output/")

        # Clean debug/ subfolder entirely
        if DEBUG_DIR.exists():
            shutil.rmtree(DEBUG_DIR)
            print(f"  Deleted output/debug/")
    else:
        print(f"  output/ does not exist — skip.")

    # ── Step 4: Optionally delete the DB itself for a fully clean slate ───
    print(f"\n[4/4] Deleting database file...")
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"  Deleted {DB_PATH}")
    else:
        print(f"  {DB_PATH} does not exist — skip.")

    print()
    print("=" * 64)
    print("NUKE COMPLETE — Run 0 fully destroyed.")
    print("Now run: python main.py")
    print("=" * 64)


if __name__ == "__main__":
    # Safety prompt
    if "--yes" not in sys.argv:
        print("This will PERMANENTLY DELETE Run 0 and all its artifacts.")
        print("Run with --yes to confirm, or Ctrl+C to abort.")
        response = input("Type 'NUKE' to confirm: ")
        if response.strip() != "NUKE":
            print("Aborted.")
            sys.exit(1)

    nuke_run0()
