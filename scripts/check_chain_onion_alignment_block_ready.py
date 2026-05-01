"""
Phase 8A.3 — Chain+Onion BLOCK-Mode Readiness Audit
====================================================
Reads chain_onion_source_check.json and run_memory.db (read-only) to decide
whether the alignment check is clean enough to flip from WARN to BLOCK in 8A.4.

Writes output/debug/chain_onion_block_readiness.json and prints:
    BLOCK_READINESS: ready=<true|false> reason=<...>
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Resolve project root (this script lives in scripts/) ─────────────────────
_ROOT = Path(__file__).resolve().parent.parent
_CHECK_JSON = _ROOT / "output" / "debug" / "chain_onion_source_check.json"
_DB_PATH = _ROOT / "data" / "run_memory.db"
_OUT_JSON = _ROOT / "output" / "debug" / "chain_onion_block_readiness.json"

_ACCEPTABLE_RESULTS = {"OK", "WARN_MTIME_ADVISORY"}


def _fail(reason: str, data: dict) -> None:
    data["block_mode_ready"] = False
    data["reason"] = reason
    _write(data)
    print(f"BLOCK_READINESS: ready=false reason={reason}")
    sys.exit(0)


def _write(data: dict) -> None:
    _OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(
        json.dumps(data, ensure_ascii=False, default=str, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    now_iso = datetime.now(timezone.utc).isoformat()

    out: dict = {
        "checked_at": now_iso,
        "block_mode_ready": False,
        "reason": "",
        "latest_check_result": None,
        "latest_run_completed_at": None,
        "latest_flat_ged_mtime": None,
        "helper_first_seen_at": None,
    }

    # ── 1. Load chain_onion_source_check.json ─────────────────────────────
    if not _CHECK_JSON.exists():
        _fail("chain_onion_source_check.json not found — helper has never run", out)
        return

    try:
        check = json.loads(_CHECK_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail(f"cannot parse chain_onion_source_check.json: {exc}", out)
        return

    result = check.get("result")
    registered_path = check.get("registered_flat_ged_path")
    using_path = check.get("using_flat_ged_path")
    sha_match = check.get("sha_match")
    checked_at_str = check.get("checked_at")

    out["latest_check_result"] = result
    # Use the JSON's checked_at as helper_first_seen_at proxy:
    # this is the latest known invocation; any pipeline run before it
    # pre-dates the WARN check being active.
    out["helper_first_seen_at"] = checked_at_str

    # ── 2. Verify source_check fields ──────────────────────────────────────
    if result not in _ACCEPTABLE_RESULTS:
        _fail(
            f"latest check result is {result!r} — must be OK or WARN_MTIME_ADVISORY "
            "before flipping to BLOCK; investigate divergence first",
            out,
        )
        return

    if not registered_path:
        _fail("registered_flat_ged_path is null — helper could not locate run_memory.db "
              "or FLAT_GED was not registered; re-run main.py", out)
        return

    if not using_path:
        _fail("using_flat_ged_path is null — helper produced incomplete receipt", out)
        return

    # sha_match must be true or null (null is OK when paths are identical)
    if sha_match is False:
        _fail("sha_match is false — content divergence recorded; investigate before blocking", out)
        return

    # ── 3. Query run_memory.db (read-only) ─────────────────────────────────
    if not _DB_PATH.exists():
        _fail(f"run_memory.db not found at {_DB_PATH}", out)
        return

    db_uri = f"file:{_DB_PATH}?mode=ro"
    try:
        con = sqlite3.connect(db_uri, uri=True)
    except Exception as exc:
        _fail(f"cannot open run_memory.db in read-only mode: {exc}", out)
        return

    try:
        cur = con.cursor()

        # Latest completed run
        cur.execute(
            "SELECT completed_at FROM runs WHERE status='COMPLETED' "
            "ORDER BY run_number DESC LIMIT 1"
        )
        row = cur.fetchone()
        latest_run_completed_at = row[0] if row else None
        out["latest_run_completed_at"] = latest_run_completed_at

        # Latest registered FLAT_GED file path
        cur.execute(
            "SELECT file_path FROM run_artifacts WHERE artifact_type='FLAT_GED' "
            "ORDER BY run_number DESC LIMIT 1"
        )
        art_row = cur.fetchone()
        latest_flat_ged_file = art_row[0] if art_row else None
    finally:
        con.close()

    # File mtime of the latest registered FLAT_GED artifact
    flat_ged_mtime: float | None = None
    if latest_flat_ged_file:
        try:
            flat_ged_mtime = os.stat(latest_flat_ged_file).st_mtime
        except Exception:
            pass
    out["latest_flat_ged_mtime"] = flat_ged_mtime

    # ── 4. Compare timestamps ──────────────────────────────────────────────
    # Parse helper_first_seen_at to a comparable datetime
    helper_dt: datetime | None = None
    if checked_at_str:
        try:
            helper_dt = datetime.fromisoformat(checked_at_str)
        except Exception:
            pass

    # Parse latest run completed_at
    run_dt: datetime | None = None
    if latest_run_completed_at:
        try:
            run_dt = datetime.fromisoformat(latest_run_completed_at)
        except Exception:
            pass

    # Condition A: at least one run completed AFTER the helper's first known invocation
    if run_dt is None:
        _fail("no completed pipeline run found in run_memory.db; run main.py first", out)
        return

    if helper_dt is not None and run_dt <= helper_dt:
        _fail(
            f"latest pipeline run ({run_dt.date().isoformat()}) pre-dates the helper's "
            f"first known invocation ({helper_dt.date().isoformat()}); "
            "re-run main.py to register a fresh FLAT_GED cycle after the WARN check was added",
            out,
        )
        return

    # Condition B: latest FLAT_GED artifact mtime > helper's first invocation timestamp
    if flat_ged_mtime is None:
        _fail("could not read FLAT_GED artifact mtime; run main.py to regenerate", out)
        return

    if helper_dt is not None:
        helper_ts = helper_dt.timestamp()
        if flat_ged_mtime <= helper_ts:
            _fail(
                f"FLAT_GED artifact mtime ({datetime.fromtimestamp(flat_ged_mtime, tz=timezone.utc).date()}) "
                f"is not newer than helper's first invocation ({helper_dt.date()}); "
                "re-run main.py to produce a fresh FLAT_GED artifact after the WARN check was added",
                out,
            )
            return

    # ── 5. All checks passed ───────────────────────────────────────────────
    reason = (
        f"check result={result}; fresh pipeline run at {run_dt.date()} "
        f"after helper first seen at {helper_dt.date() if helper_dt else 'unknown'}; "
        "FLAT_GED mtime is current; safe to flip to BLOCK in 8A.4"
    )
    out["block_mode_ready"] = True
    out["reason"] = reason
    _write(out)
    print(f"BLOCK_READINESS: ready=true reason={reason}")


if __name__ == "__main__":
    main()
