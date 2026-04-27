"""
reset_to_clean_run0.py
======================
CLEAN Step 17A — Reset run history and rebuild a clean Run 0 baseline.

What it does (in order):
  1. Backs up current run history + key artifacts to backup/pre_rc1_run_history_<TS>/
  2. Deletes data/run_memory.db and the entire runs/ tree
  3. Recreates an empty runs/ directory
  4. Executes `python main.py` to regenerate Run 0
  5. Validates the rebuilt state:
       - DB: exactly one run, run_number=0, status=COMPLETED, error_message=NULL
       - Artifacts: FLAT_GED, FLAT_GED_RUN_REPORT, FINAL_GF, GF_TEAM_VERSION (mandatory);
                    FLAT_GED_DEBUG_TRACE (warn-only — optional in non-batch modes)
       - Filesystem: runs/run_0000/, output/GF_V0_CLEAN.xlsx, output/GF_TEAM_VERSION.xlsx,
                     output/intermediate/FLAT_GED.xlsx, flat_ged_run_report.json
       - UI loader: clear_cache + load_run_context returns (0, False, True)

Preserved (never deleted by this script):
  - data/report_memory.db
  - input/ (GED_export.xlsx, Grandfichier_v3.xlsx, consultant_reports/, ...)
  - src/, ui/, docs/

Usage:
    python scripts/reset_to_clean_run0.py            # interactive confirm
    python scripts/reset_to_clean_run0.py --yes      # non-interactive
    python scripts/reset_to_clean_run0.py --skip-rebuild   # only backup+delete (debug)
    python scripts/reset_to_clean_run0.py --skip-validate  # backup+delete+rebuild only

Exit codes:
    0  = success, all validations passed
    1  = aborted by user
    2  = backup or deletion failed
    3  = `python main.py` failed
    4  = post-rebuild validation failed
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent

DB_PATH         = _PROJECT_ROOT / "data" / "run_memory.db"
REPORT_DB_PATH  = _PROJECT_ROOT / "data" / "report_memory.db"
RUNS_DIR        = _PROJECT_ROOT / "runs"
OUTPUT_DIR      = _PROJECT_ROOT / "output"
INTERMEDIATE    = OUTPUT_DIR / "intermediate"
BACKUP_PARENT   = _PROJECT_ROOT / "backup"

# Items to copy into backup if they exist (relative to project root)
_BACKUP_ITEMS = [
    "data/run_memory.db",
    "runs",
    "output/GF_V0_CLEAN.xlsx",
    "output/GF_TEAM_VERSION.xlsx",
    "output/intermediate/FLAT_GED.xlsx",
    "output/intermediate/flat_ged_run_report.json",
    "output/intermediate/DEBUG_TRACE.csv",
]

# Mandatory artifact types that MUST be registered for Run 0
_MANDATORY_ARTIFACTS = [
    "FLAT_GED",
    "FLAT_GED_RUN_REPORT",
    "FINAL_GF",
    "GF_TEAM_VERSION",
]
# Soft-check: warn but don't fail if missing (optional in non-batch modes)
_OPTIONAL_ARTIFACTS = [
    "FLAT_GED_DEBUG_TRACE",
]

# Files expected on disk after rebuild
_EXPECTED_FILES = [
    OUTPUT_DIR / "GF_V0_CLEAN.xlsx",
    OUTPUT_DIR / "GF_TEAM_VERSION.xlsx",
    INTERMEDIATE / "FLAT_GED.xlsx",
    INTERMEDIATE / "flat_ged_run_report.json",
]
_EXPECTED_FILES_OPTIONAL = [
    INTERMEDIATE / "DEBUG_TRACE.csv",
]


# ── Console helpers ───────────────────────────────────────────────────────
def _hr(title: str = "") -> None:
    print()
    print("=" * 72)
    if title:
        print(title)
        print("=" * 72)


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _err(msg: str) -> None:
    print(f"  [FAIL] {msg}")


# ── Step 1: Backup ────────────────────────────────────────────────────────
def make_backup() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    target = BACKUP_PARENT / f"pre_rc1_run_history_{ts}"
    target.mkdir(parents=True, exist_ok=True)

    _hr(f"[1/5] BACKUP → {target}")
    copied = 0
    for rel in _BACKUP_ITEMS:
        src = _PROJECT_ROOT / rel
        if not src.exists():
            print(f"  [skip] {rel} (not present)")
            continue
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        _ok(f"copied {rel}")
        copied += 1

    if copied == 0:
        _warn("no items copied — there may be nothing to back up.")
    print(f"  Backup written: {target}")
    return target


# ── Step 2: Destructive delete ────────────────────────────────────────────
def wipe_run_history() -> None:
    _hr("[2/5] DELETE run_memory.db + runs/")

    if DB_PATH.exists():
        DB_PATH.unlink()
        _ok(f"deleted {DB_PATH.relative_to(_PROJECT_ROOT)}")
    else:
        print(f"  [skip] {DB_PATH.relative_to(_PROJECT_ROOT)} (not present)")

    # Clean WAL/SHM/journal stragglers if any
    for suf in ("-wal", "-shm", "-journal"):
        side = DB_PATH.with_name(DB_PATH.name + suf)
        if side.exists():
            side.unlink()
            _ok(f"deleted {side.relative_to(_PROJECT_ROOT)}")

    if RUNS_DIR.exists():
        shutil.rmtree(RUNS_DIR)
        _ok(f"deleted {RUNS_DIR.relative_to(_PROJECT_ROOT)}/")
    else:
        print(f"  [skip] {RUNS_DIR.relative_to(_PROJECT_ROOT)}/ (not present)")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    _ok(f"recreated empty {RUNS_DIR.relative_to(_PROJECT_ROOT)}/")

    # Confirm preserved items
    if REPORT_DB_PATH.exists():
        _ok(f"preserved {REPORT_DB_PATH.relative_to(_PROJECT_ROOT)}")
    else:
        _warn(f"{REPORT_DB_PATH.relative_to(_PROJECT_ROOT)} not found (was it ever there?)")

    for rel in ("input/GED_export.xlsx", "input/Grandfichier_v3.xlsx", "input/consultant_reports"):
        p = _PROJECT_ROOT / rel
        if p.exists():
            _ok(f"preserved {rel}")
        else:
            _warn(f"{rel} not found")


# ── Step 3: Rebuild via main.py ───────────────────────────────────────────
def rebuild_run_zero() -> None:
    _hr("[3/5] REBUILD via `python main.py`")
    cmd = [sys.executable, "main.py"]
    print(f"  cwd : {_PROJECT_ROOT}")
    print(f"  cmd : {' '.join(cmd)}")
    print("  (pipeline output streams below) ...")
    print("-" * 72)
    result = subprocess.run(cmd, cwd=str(_PROJECT_ROOT))
    print("-" * 72)
    if result.returncode != 0:
        _err(f"main.py exited with code {result.returncode}")
        sys.exit(3)
    _ok("main.py completed successfully")


# ── Step 4: Validation ────────────────────────────────────────────────────
def _query_runs() -> list[tuple[int, str, str | None]]:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(str(DB_PATH)) as conn:
        rows = conn.execute(
            "SELECT run_number, status, error_message FROM runs ORDER BY run_number"
        ).fetchall()
    return [(int(r[0]), r[1], r[2]) for r in rows]


def _query_artifact_types(run_number: int) -> set[str]:
    if not DB_PATH.exists():
        return set()
    with sqlite3.connect(str(DB_PATH)) as conn:
        rows = conn.execute(
            "SELECT DISTINCT artifact_type FROM run_artifacts WHERE run_number = ?",
            (run_number,),
        ).fetchall()
    return {r[0] for r in rows}


def validate_db() -> tuple[bool, dict]:
    _hr("[4/5] VALIDATE")
    print("  -- DB state --")
    runs = _query_runs()

    summary: dict = {"runs": runs, "artifacts": [], "missing_artifacts": [],
                     "optional_missing": [], "files_missing": [],
                     "files_optional_missing": [], "ui_loader": None}

    if not runs:
        _err("no runs in DB after rebuild")
        return False, summary

    if len(runs) != 1:
        _err(f"expected exactly 1 run, found {len(runs)}: {runs}")
        return False, summary

    rn, status, err = runs[0]
    if rn != 0:
        _err(f"expected run_number=0, got {rn}")
        return False, summary
    if status != "COMPLETED":
        _err(f"expected status=COMPLETED, got {status!r} (error_message={err!r})")
        return False, summary
    if err is not None:
        _warn(f"error_message is not NULL: {err!r}")
    _ok(f"Run 0 | status=COMPLETED | error_message={err!r}")

    # Artifact types
    print("  -- Artifact registration (DB) --")
    types = _query_artifact_types(0)
    summary["artifacts"] = sorted(types)

    missing = [a for a in _MANDATORY_ARTIFACTS if a not in types]
    summary["missing_artifacts"] = missing
    for a in _MANDATORY_ARTIFACTS:
        if a in types:
            _ok(f"required artifact present: {a}")
        else:
            _err(f"required artifact missing: {a}")

    opt_missing = [a for a in _OPTIONAL_ARTIFACTS if a not in types]
    summary["optional_missing"] = opt_missing
    for a in _OPTIONAL_ARTIFACTS:
        if a in types:
            _ok(f"optional artifact present: {a}")
        else:
            _warn(f"optional artifact missing: {a} (expected only in batch mode)")

    if missing:
        return False, summary

    # Filesystem
    print("  -- Filesystem layout --")
    run0_dir = RUNS_DIR / "run_0000"
    if run0_dir.exists() and run0_dir.is_dir():
        _ok(f"{run0_dir.relative_to(_PROJECT_ROOT)}/ exists")
    else:
        _err(f"{run0_dir.relative_to(_PROJECT_ROOT)}/ missing")
        summary["files_missing"].append(str(run0_dir.relative_to(_PROJECT_ROOT)))

    for f in _EXPECTED_FILES:
        rel = f.relative_to(_PROJECT_ROOT)
        if f.exists():
            _ok(f"{rel} exists")
        else:
            _err(f"{rel} missing")
            summary["files_missing"].append(str(rel))

    for f in _EXPECTED_FILES_OPTIONAL:
        rel = f.relative_to(_PROJECT_ROOT)
        if f.exists():
            _ok(f"{rel} exists")
        else:
            _warn(f"{rel} missing (optional)")
            summary["files_optional_missing"].append(str(rel))

    if summary["files_missing"]:
        return False, summary

    return True, summary


def validate_ui_loader(summary: dict) -> bool:
    print("  -- UI loader smoke test --")
    snippet = (
        "from pathlib import Path; import sys; "
        "sys.path.insert(0, str(Path('src').resolve())); "
        "from reporting.data_loader import clear_cache, load_run_context; "
        "clear_cache(); "
        "ctx = load_run_context(Path('.')); "
        "print(ctx.run_number, ctx.degraded_mode, bool(ctx.artifact_paths.get('FLAT_GED')))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    # Pipeline stages (e.g. stage_read_flat) may emit informational lines
    # like "[1/7] Reading FLAT_GED (flat mode)..." to stdout before our
    # smoke `print(...)`. Match against the last non-empty line, not the
    # full buffer.
    last_line = next(
        (ln.strip() for ln in reversed(out.splitlines()) if ln.strip()),
        "",
    )
    summary["ui_loader"] = {
        "stdout": out,
        "stdout_last_line": last_line,
        "stderr": err,
        "returncode": proc.returncode,
    }

    if proc.returncode != 0:
        _err(f"UI loader smoke failed (rc={proc.returncode})")
        if err:
            print("  stderr:")
            for line in err.splitlines():
                print(f"    {line}")
        return False

    expected = "0 False True"
    if last_line == expected:
        _ok(f"UI loader last line: {last_line!r}")
        return True
    _err(
        f"UI loader output mismatch: last line = {last_line!r}, "
        f"expected {expected!r} (full stdout: {out!r})"
    )
    return False


# ── Orchestration ─────────────────────────────────────────────────────────
def confirm_destructive(yes: bool) -> None:
    if yes:
        return
    print()
    print("This will DELETE data/run_memory.db and runs/ for a fresh Run 0 rebuild.")
    print("A backup will be written to backup/pre_rc1_run_history_<timestamp>/ first.")
    response = input("Type 'RESET' to proceed, anything else to abort: ").strip()
    if response != "RESET":
        print("Aborted.")
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 17A — Clean Run 0 reset")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirm")
    parser.add_argument("--skip-rebuild", action="store_true",
                        help="Backup + delete only; do not run main.py")
    parser.add_argument("--skip-validate", action="store_true",
                        help="Skip post-rebuild validation")
    args = parser.parse_args()

    print("=" * 72)
    print("CLEAN Step 17A — Reset to Clean Run 0")
    print(f"Project root: {_PROJECT_ROOT}")
    print("=" * 72)

    confirm_destructive(args.yes)

    # 1+2 — backup, then wipe
    try:
        backup_target = make_backup()
        wipe_run_history()
    except Exception as exc:
        _err(f"backup or delete failed: {type(exc).__name__}: {exc}")
        return 2

    # 3 — rebuild
    if args.skip_rebuild:
        _hr("[3/5] REBUILD skipped (--skip-rebuild)")
        return 0
    rebuild_run_zero()

    # 4+5 — validate
    if args.skip_validate:
        _hr("[4/5] VALIDATE skipped (--skip-validate)")
        return 0

    db_ok, summary = validate_db()
    ui_ok = validate_ui_loader(summary)

    _hr("[5/5] SUMMARY")
    print(f"  Backup           : {backup_target}")
    print(f"  Runs in DB       : {summary['runs']}")
    print(f"  Artifacts (Run 0): {summary['artifacts']}")
    if summary["missing_artifacts"]:
        print(f"  MISSING required : {summary['missing_artifacts']}")
    if summary["optional_missing"]:
        print(f"  Missing optional : {summary['optional_missing']}")
    if summary["files_missing"]:
        print(f"  Files missing    : {summary['files_missing']}")
    if summary["files_optional_missing"]:
        print(f"  Files missing*   : {summary['files_optional_missing']}  (optional)")
    print(f"  UI loader smoke  : {summary['ui_loader']!r}")

    if db_ok and ui_ok:
        print()
        print("RESULT: PASS — Run 0 baseline is clean. Step 17B (RC1 freeze) can begin.")
        return 0

    print()
    print("RESULT: FAIL — see [FAIL] lines above. Do NOT proceed to RC1 freeze.")
    return 4


if __name__ == "__main__":
    sys.exit(main())
