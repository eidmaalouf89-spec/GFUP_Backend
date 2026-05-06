"""
Phase 9A — Baseline Lifecycle Diagnostic harness.

Read-only-by-default. Each subcommand has explicit intent:

    backup           - copy input/, data/, runs/, output/ to <dest>/<ts>/
    hold-reports     - move input/consultant_reports -> _input_hold/
    restore-reports  - reverse hold-reports
    wipe-generated   - delete data/run_memory.db, data/report_memory.db,
                       runs/, output/  (--dry-run prints intent)
    snapshot <label> - copy data/, runs/, output/ to
                       _diagnostic_snapshots/<label>/ and emit summary files

Does NOT run the pipeline. Does NOT import from src/. Does NOT modify any
source code. Pure stdlib so it works from Cowork sandbox or Windows shell.

All operations append a JSON line to
_diagnostic_snapshots/lifecycle_log.jsonl in the repo root.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _log(event: dict) -> None:
    log_dir = REPO_ROOT / "_diagnostic_snapshots"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "lifecycle_log.jsonl"
    event = dict(event)
    event["ts"] = datetime.now().isoformat(timespec="seconds")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _print_result(result: dict) -> None:
    print(json.dumps(result, indent=2, ensure_ascii=False))


def _count_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.rglob("*") if p.is_file())


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------

def cmd_backup(args: argparse.Namespace) -> dict:
    dest_root = Path(args.dest).resolve()
    ts = _now_ts()
    dest = dest_root / ts
    dest_root.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        result = {
            "command": "backup",
            "status": "abort_dest_exists",
            "dest": str(dest),
        }
        _log(result)
        _print_result(result)
        return result

    dest.mkdir(parents=True, exist_ok=False)

    counts: dict[str, dict] = {}
    for sub in ("input", "data", "runs", "output"):
        src = REPO_ROOT / sub
        if not src.exists():
            counts[sub] = {"present": False, "files": 0, "bytes": 0}
            continue
        target = dest / sub
        n_files = _count_files(src)
        size_bytes = _dir_size_bytes(src)
        shutil.copytree(src, target)
        counts[sub] = {"present": True, "files": n_files, "bytes": size_bytes}

    result = {
        "command": "backup",
        "status": "ok",
        "dest": str(dest),
        "counts": counts,
        "totals": {
            "files": sum(c.get("files", 0) for c in counts.values()),
            "bytes": sum(c.get("bytes", 0) for c in counts.values()),
        },
    }
    _log(result)
    _print_result(result)
    return result


# ---------------------------------------------------------------------------
# hold / restore reports
# ---------------------------------------------------------------------------

def cmd_hold_reports(args: argparse.Namespace) -> dict:
    src = REPO_ROOT / "input" / "consultant_reports"
    hold = REPO_ROOT / "_input_hold" / "consultant_reports_DISABLED"

    if not src.exists():
        result = {
            "command": "hold-reports",
            "status": "src_absent",
            "src": str(src),
        }
        _log(result)
        _print_result(result)
        return result

    if hold.exists():
        result = {
            "command": "hold-reports",
            "status": "abort_hold_already_exists",
            "hold": str(hold),
        }
        _log(result)
        _print_result(result)
        return result

    hold.parent.mkdir(parents=True, exist_ok=True)
    n_files = _count_files(src)
    shutil.move(str(src), str(hold))
    result = {
        "command": "hold-reports",
        "status": "moved",
        "src": str(src),
        "hold": str(hold),
        "files": n_files,
    }
    _log(result)
    _print_result(result)
    return result


def cmd_restore_reports(args: argparse.Namespace) -> dict:
    src = REPO_ROOT / "input" / "consultant_reports"
    hold = REPO_ROOT / "_input_hold" / "consultant_reports_DISABLED"

    if not hold.exists():
        result = {
            "command": "restore-reports",
            "status": "no_hold",
            "hold": str(hold),
        }
        _log(result)
        _print_result(result)
        return result

    if src.exists():
        result = {
            "command": "restore-reports",
            "status": "abort_src_already_present",
            "src": str(src),
        }
        _log(result)
        _print_result(result)
        return result

    src.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(hold), str(src))
    n_files = _count_files(src)

    hold_parent = hold.parent
    try:
        if hold_parent.exists() and not any(hold_parent.iterdir()):
            hold_parent.rmdir()
    except OSError:
        pass

    result = {
        "command": "restore-reports",
        "status": "restored",
        "src": str(src),
        "files": n_files,
    }
    _log(result)
    _print_result(result)
    return result


# ---------------------------------------------------------------------------
# wipe
# ---------------------------------------------------------------------------

_WIPE_FILES = (
    Path("data") / "run_memory.db",
    Path("data") / "report_memory.db",
)
_WIPE_TREES = (
    Path("runs"),
    Path("output"),
)
_SCAFFOLD_DIRS = (
    Path("data"),
    Path("runs"),
    Path("output"),
    Path("output") / "intermediate",
    Path("output") / "debug",
    Path("output") / "exports",
    Path("output") / "chain_onion",
)


def cmd_wipe_generated(args: argparse.Namespace) -> dict:
    plan: list[dict] = []
    for rel in _WIPE_FILES:
        p = REPO_ROOT / rel
        if p.exists():
            plan.append({"kind": "file", "path": str(p), "bytes": p.stat().st_size})
    for rel in _WIPE_TREES:
        p = REPO_ROOT / rel
        if p.exists():
            plan.append(
                {
                    "kind": "tree",
                    "path": str(p),
                    "files": _count_files(p),
                    "bytes": _dir_size_bytes(p),
                }
            )

    notes: list[str] = []
    app_db = REPO_ROOT / "data" / "app.db"
    malformed_bak = REPO_ROOT / "data" / "report_memory.db.malformed_bak"
    if app_db.exists():
        notes.append(f"NOT WIPING (not in task spec): {app_db}")
    if malformed_bak.exists():
        notes.append(f"NOT WIPING (not in task spec): {malformed_bak}")

    if args.dry_run:
        result = {
            "command": "wipe-generated",
            "dry_run": True,
            "would_delete": plan,
            "would_recreate": [str(REPO_ROOT / d) for d in _SCAFFOLD_DIRS],
            "notes": notes,
        }
        _log(result)
        _print_result(result)
        return result

    deleted: list[dict] = []
    for item in plan:
        path = Path(item["path"])
        if item["kind"] == "file":
            path.unlink()
            deleted.append({"kind": "file", "path": str(path)})
        elif item["kind"] == "tree":
            shutil.rmtree(path)
            deleted.append({"kind": "tree", "path": str(path)})

    scaffolded: list[str] = []
    for rel in _SCAFFOLD_DIRS:
        p = REPO_ROOT / rel
        p.mkdir(parents=True, exist_ok=True)
        scaffolded.append(str(p))

    result = {
        "command": "wipe-generated",
        "status": "ok",
        "deleted": deleted,
        "scaffolded": scaffolded,
        "notes": notes,
    }
    _log(result)
    _print_result(result)
    return result


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------

_TOP_OUTPUT_ARTIFACTS = (
    "GF_V0_CLEAN.xlsx",
    "GF_TEAM_VERSION.xlsx",
    "DISCREPANCY_REPORT.xlsx",
    "DISCREPANCY_REVIEW_REQUIRED.xlsx",
    "ANOMALY_REPORT.xlsx",
    "AUTO_RESOLUTION_LOG.xlsx",
    "IGNORED_ITEMS_LOG.xlsx",
    "RECONCILIATION_LOG.xlsx",
    "MISSING_IN_GED_DIAGNOSIS.xlsx",
    "MISSING_IN_GED_TRUE_ONLY.xlsx",
    "MISSING_IN_GF_DIAGNOSIS.xlsx",
    "MISSING_IN_GF_TRUE_ONLY.xlsx",
    "INSERT_LOG.xlsx",
    "NEW_SUBMITTAL_ANALYSIS.xlsx",
    "SUSPICIOUS_ROWS_REPORT.xlsx",
    "consultant_match_report.xlsx",
    "consultant_reports.xlsx",
)

_INTERMEDIATE_ARTIFACTS = (
    "FLAT_GED.xlsx",
    "DEBUG_TRACE.csv",
    "flat_ged_run_report.json",
    "COUNTER_ATTACK_ITEMS.csv",
    "CHAIN_TIMELINE_ATTRIBUTION.json",
    "CHAIN_TIMELINE_ATTRIBUTION.csv",
    "FLAT_GED_cache_meta.json",
)

_CHAIN_ONION_ARTIFACTS = (
    "CHAIN_REGISTER.csv",
    "CHAIN_VERSIONS.csv",
    "CHAIN_EVENTS.csv",
    "CHAIN_METRICS.csv",
    "ONION_LAYERS.csv",
    "ONION_SCORES.csv",
    "CHAIN_NARRATIVES.csv",
    "CHAIN_ONION_SUMMARY.xlsx",
    "dashboard_summary.json",
    "top_issues.json",
)


def _file_meta(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    st = path.stat()
    return {"exists": True, "bytes": st.st_size, "mtime": st.st_mtime}


def _open_sqlite_via_tmp_copy(db_path: Path):
    """
    Return (connection, tmp_path) on a /tmp copy of db_path.

    SQLite reads through the Cowork cross-mount intermittently fail at first
    SELECT with 'unable to open database file', regardless of mode=ro URI
    form or path URL-encoding. Copying to a /tmp local path and querying
    that copy is the only reliable approach. Caller must close the
    connection and unlink tmp_path.
    """
    fd, tmp_path = tempfile.mkstemp(suffix=".db", prefix="lifecycle_diag_")
    os.close(fd)
    shutil.copy2(db_path, tmp_path)
    return sqlite3.connect(tmp_path), tmp_path


def _run_memory_summary(db_path: Path) -> dict:
    if not db_path.exists():
        return {"missing": True}
    tmp_path = None
    try:
        c, tmp_path = _open_sqlite_via_tmp_copy(db_path)
        with c:
            tables = [
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            out: dict = {"tables": tables}
            for t in tables:
                out[f"{t}_row_count"] = c.execute(
                    f"SELECT COUNT(*) FROM {t}"
                ).fetchone()[0]

            if "runs" in tables:
                out["status_distribution"] = dict(
                    c.execute(
                        "SELECT status, COUNT(*) FROM runs GROUP BY status"
                    ).fetchall()
                )
                row = c.execute(
                    "SELECT run_number, status, is_current, completed_at "
                    "FROM runs ORDER BY run_number DESC LIMIT 1"
                ).fetchone()
                if row:
                    out["latest_run"] = {
                        "run_number": row[0],
                        "status": row[1],
                        "is_current": row[2],
                        "completed_at": row[3],
                    }

            if "run_artifacts" in tables:
                out["artifact_type_distribution"] = dict(
                    c.execute(
                        "SELECT artifact_type, COUNT(*) FROM run_artifacts "
                        "GROUP BY artifact_type ORDER BY artifact_type"
                    ).fetchall()
                )
            return out
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass


def _report_memory_summary(db_path: Path) -> dict:
    if not db_path.exists():
        return {"missing": True}
    tmp_path = None
    try:
        c, tmp_path = _open_sqlite_via_tmp_copy(db_path)
        with c:
            tables = [
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            out: dict = {"tables": tables}
            for t in tables:
                out[f"{t}_row_count"] = c.execute(
                    f"SELECT COUNT(*) FROM {t}"
                ).fetchone()[0]
            if "persisted_report_responses" in tables:
                out["active_count"] = c.execute(
                    "SELECT COUNT(*) FROM persisted_report_responses WHERE is_active=1"
                ).fetchone()[0]
                out["confidence_distribution"] = dict(
                    c.execute(
                        "SELECT match_confidence, COUNT(*) FROM persisted_report_responses "
                        "GROUP BY match_confidence"
                    ).fetchall()
                )
                out["status_distribution"] = dict(
                    c.execute(
                        "SELECT report_status, COUNT(*) FROM persisted_report_responses "
                        "GROUP BY report_status"
                    ).fetchall()
                )
            if "ingested_reports" in tables:
                cols = [
                    r[1]
                    for r in c.execute("PRAGMA table_info(ingested_reports)").fetchall()
                ]
                if "status" in cols:
                    out["ingested_status_distribution"] = dict(
                        c.execute(
                            "SELECT status, COUNT(*) FROM ingested_reports GROUP BY status"
                        ).fetchall()
                    )
                else:
                    out["ingested_status_distribution"] = None
            return out
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass


def _csv_row_count(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)
            return sum(1 for _ in reader)
    except Exception:
        return -1


def _bucket_counts(ca_csv: Path) -> dict:
    counts: dict = {}
    if not ca_csv.exists():
        return counts
    try:
        with open(ca_csv, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                b = row.get("action_bucket", "") or ""
                counts[b] = counts.get(b, 0) + 1
    except Exception:
        return {}
    return counts


def _chain_onion_counts(co_dir: Path) -> dict:
    counts: dict = {}
    for name in _CHAIN_ONION_ARTIFACTS:
        p = co_dir / name
        if name.endswith(".csv"):
            counts[name] = _csv_row_count(p)
        elif name.endswith(".json"):
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        counts[name] = {"kind": "list", "len": len(data)}
                    elif isinstance(data, dict):
                        counts[name] = {"kind": "object", "keys": sorted(data.keys())}
                    else:
                        counts[name] = {"kind": type(data).__name__}
                except Exception as e:  # noqa: BLE001
                    counts[name] = {"error": str(e)}
            else:
                counts[name] = None
        else:
            counts[name] = _file_meta(p)
    return counts


def _compute_metrics() -> dict:
    metrics: dict = {}
    metrics["run_memory"] = _run_memory_summary(REPO_ROOT / "data" / "run_memory.db")
    metrics["report_memory"] = _report_memory_summary(
        REPO_ROOT / "data" / "report_memory.db"
    )

    output = REPO_ROOT / "output"
    metrics["output_artifacts"] = {
        n: _file_meta(output / n) for n in _TOP_OUTPUT_ARTIFACTS
    }

    inter = output / "intermediate"
    metrics["intermediate"] = {
        n: _file_meta(inter / n) for n in _INTERMEDIATE_ARTIFACTS
    }

    co = output / "chain_onion"
    metrics["chain_onion_files"] = {
        n: _file_meta(co / n) for n in _CHAIN_ONION_ARTIFACTS
    }
    metrics["chain_onion_counts"] = _chain_onion_counts(co)

    runs = REPO_ROOT / "runs"
    if runs.exists():
        run_dirs = sorted(p.name for p in runs.iterdir() if p.is_dir())
        metrics["runs_dir"] = {
            "present": True,
            "run_dirs": run_dirs,
            "count": len(run_dirs),
        }
    else:
        metrics["runs_dir"] = {"present": False}

    ca = inter / "COUNTER_ATTACK_ITEMS.csv"
    metrics["counter_attack"] = {
        "row_count": _csv_row_count(ca),
        "bucket_counts": _bucket_counts(ca),
    }

    return metrics


def cmd_snapshot(args: argparse.Namespace) -> dict:
    label = args.label
    snap_root = REPO_ROOT / "_diagnostic_snapshots" / label
    snap_root.mkdir(parents=True, exist_ok=True)

    copy_summary: dict = {}
    if args.metrics_only:
        copy_summary = {"skipped": True, "reason": "metrics_only"}
    else:
        for sub in ("data", "runs", "output"):
            src = REPO_ROOT / sub
            target = snap_root / sub
            if target.exists():
                shutil.rmtree(target)
            if src.exists():
                shutil.copytree(src, target)
                copy_summary[sub] = {
                    "files": _count_files(target),
                    "bytes": _dir_size_bytes(target),
                }
            else:
                copy_summary[sub] = {"present": False}

    metrics = _compute_metrics()
    (snap_root / f"{label}_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    bc = metrics.get("counter_attack", {}).get("bucket_counts", {})
    bc_path = snap_root / f"{label}_bucket_counts.csv"
    with open(bc_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bucket", "count"])
        for k in sorted(bc.keys()):
            w.writerow([k, bc[k]])

    ca_csv = REPO_ROOT / "output" / "intermediate" / "COUNTER_ATTACK_ITEMS.csv"
    if ca_csv.exists():
        shutil.copy2(ca_csv, snap_root / f"{label}_counter_attack_items.csv")

    (snap_root / f"{label}_chain_onion_counts.json").write_text(
        json.dumps(metrics["chain_onion_counts"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    (snap_root / f"{label}_report_memory_summary.json").write_text(
        json.dumps(metrics["report_memory"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    crosscheck = snap_root / f"{label}_latest_indice_crosscheck.csv"
    if not crosscheck.exists():
        with open(crosscheck, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "family_key",
                    "numero",
                    "flat_ged_latest_indice",
                    "chain_onion_latest_indice",
                    "counter_attack_indice",
                    "counter_attack_bucket",
                    "is_counter_attack_latest",
                    "mismatch_type",
                    "suspected_cause",
                ]
            )

    result = {
        "command": "snapshot",
        "label": label,
        "snap_root": str(snap_root),
        "copy_summary": copy_summary,
        "files_emitted": [
            f"{label}_metrics.json",
            f"{label}_bucket_counts.csv",
            f"{label}_counter_attack_items.csv (if present in output/)",
            f"{label}_chain_onion_counts.json",
            f"{label}_report_memory_summary.json",
            f"{label}_latest_indice_crosscheck.csv (header-only placeholder)",
        ],
        "metrics_top_level": list(metrics.keys()),
    }
    _log(result)
    _print_result(result)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 9A baseline lifecycle diagnostic harness"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_backup = sub.add_parser("backup")
    p_backup.add_argument("--dest", required=True)
    p_backup.set_defaults(func=cmd_backup)

    p_hold = sub.add_parser("hold-reports")
    p_hold.set_defaults(func=cmd_hold_reports)

    p_restore = sub.add_parser("restore-reports")
    p_restore.set_defaults(func=cmd_restore_reports)

    p_wipe = sub.add_parser("wipe-generated")
    p_wipe.add_argument("--dry-run", action="store_true")
    p_wipe.set_defaults(func=cmd_wipe_generated)

    p_snap = sub.add_parser("snapshot")
    p_snap.add_argument("label", choices=["A", "B", "C"])
    p_snap.add_argument("--metrics-only", action="store_true",
                        help="Skip data/runs/output copy; only regenerate metric files")
    p_snap.set_defaults(func=cmd_snapshot)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
