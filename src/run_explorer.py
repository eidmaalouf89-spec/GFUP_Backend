"""
run_explorer.py
---------------
Minimal UI-facing service layer on top of run_memory.

This layer is intentionally small and deterministic:
  - list runs
  - summarize a run
  - resolve the final GF artifact for a run
  - export a full run bundle
  - compare two runs at a high level
"""

import json
import sqlite3
from pathlib import Path

try:
    from run_memory import export_run_artifacts_bundle
except ModuleNotFoundError:
    from src.run_memory import export_run_artifacts_bundle


def _conn(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def _clean_scalar(value):
    # pandas/SQLite NULL-like values should be normalized for JSON-serializable output
    if value != value:  # NaN
        return None
    return value


def _parse_summary_json(value):
    value = _clean_scalar(value)
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return text
    return parsed


def _run_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "run_number": int(row["run_number"]),
        "run_label": row["run_label"],
        "run_type": row["run_type"],
        "is_baseline": bool(row["is_baseline"]),
        "is_current": bool(row["is_current"]),
        "is_stale": bool(row["is_stale"]),
        "stale_reason": row["stale_reason"],
        "status": row["status"],
        "created_at": row["created_at"],
        "completed_at": _clean_scalar(row["completed_at"]),
        "notes": row["notes"],
        "core_version": row["core_version"],
    }


def get_all_runs(db_path: str) -> list[dict]:
    with _conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                run_number,
                run_label,
                run_type,
                is_baseline,
                is_current,
                is_stale,
                stale_reason,
                status,
                created_at,
                completed_at,
                notes,
                core_version
            FROM runs
            ORDER BY run_number DESC
            """
        ).fetchall()
    return [_run_row_to_dict(row) for row in rows]


def get_run_summary(db_path: str, run_number: int) -> dict:
    with _conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT *
            FROM runs
            WHERE run_number = ?
            """,
            (run_number,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Run {run_number} not found in run memory")

        artifact_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM run_artifacts WHERE run_number = ?",
                (run_number,),
            ).fetchone()[0]
        )
        input_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM run_inputs WHERE run_number = ?",
                (run_number,),
            ).fetchone()[0]
        )
        artifact_types = sorted(
            {
                str(r[0])
                for r in conn.execute(
                    "SELECT artifact_type FROM run_artifacts WHERE run_number = ?",
                    (run_number,),
                ).fetchall()
                if r[0] is not None
            }
        )
        input_types = sorted(
            {
                str(r[0])
                for r in conn.execute(
                    "SELECT input_type FROM run_inputs WHERE run_number = ?",
                    (run_number,),
                ).fetchall()
                if r[0] is not None
            }
        )

    payload = {key: _clean_scalar(value) for key, value in dict(row).items()}
    payload["is_baseline"] = bool(payload["is_baseline"])
    payload["is_current"] = bool(payload["is_current"])
    payload["is_stale"] = bool(payload["is_stale"])
    payload["summary_json"] = _parse_summary_json(payload.get("summary_json"))
    payload["artifact_count"] = artifact_count
    payload["input_count"] = input_count
    payload["artifact_types"] = artifact_types
    payload["input_types"] = input_types
    return payload


def export_final_gf(db_path: str, run_number: int) -> str:
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT file_path
            FROM run_artifacts
            WHERE run_number = ? AND artifact_type = 'FINAL_GF'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (run_number,),
        ).fetchone()
    if row is None or not row[0]:
        raise RuntimeError(f"Run {run_number} does not have a FINAL_GF artifact")

    file_path = str(Path(row[0]).resolve())
    if not Path(file_path).exists():
        raise RuntimeError(
            f"Run {run_number} FINAL_GF artifact is registered but missing on disk: {file_path}"
        )
    return file_path


def export_run_bundle(db_path: str, run_number: int, output_zip_path: str) -> str:
    bundle_path = export_run_artifacts_bundle(
        db_path=db_path,
        run_number=run_number,
        output_zip_path=output_zip_path,
    )
    resolved = str(Path(bundle_path).resolve())
    if not Path(resolved).exists():
        raise RuntimeError(
            f"Run {run_number} bundle export did not produce a zip file: {resolved}"
        )
    return resolved


def compare_runs(db_path: str, run_a: int, run_b: int) -> dict:
    summary_a = get_run_summary(db_path, run_a)
    summary_b = get_run_summary(db_path, run_b)

    summary_json_a = summary_a.get("summary_json")
    summary_json_b = summary_b.get("summary_json")
    if not isinstance(summary_json_a, dict):
        summary_json_a = {}
    if not isinstance(summary_json_b, dict):
        summary_json_b = {}

    summary_differences = {}
    for key in sorted(set(summary_json_a.keys()) | set(summary_json_b.keys())):
        value_a = summary_json_a.get(key)
        value_b = summary_json_b.get(key)
        if value_a != value_b:
            summary_differences[key] = {"run_a": value_a, "run_b": value_b}

    artifact_types_a = set(summary_a["artifact_types"])
    artifact_types_b = set(summary_b["artifact_types"])

    return {
        "run_a": run_a,
        "run_b": run_b,
        "metadata": {
            "status_a": summary_a["status"],
            "status_b": summary_b["status"],
            "is_stale_a": summary_a["is_stale"],
            "is_stale_b": summary_b["is_stale"],
            "is_current_a": summary_a["is_current"],
            "is_current_b": summary_b["is_current"],
            "completed_at_a": summary_a["completed_at"],
            "completed_at_b": summary_b["completed_at"],
        },
        "artifact_count": {
            "run_a": summary_a["artifact_count"],
            "run_b": summary_b["artifact_count"],
            "delta": summary_b["artifact_count"] - summary_a["artifact_count"],
        },
        "input_count": {
            "run_a": summary_a["input_count"],
            "run_b": summary_b["input_count"],
            "delta": summary_b["input_count"] - summary_a["input_count"],
        },
        "artifact_types_only_in_a": sorted(artifact_types_a - artifact_types_b),
        "artifact_types_only_in_b": sorted(artifact_types_b - artifact_types_a),
        "summary_differences": summary_differences,
    }


def get_latest_run_number(db_path: str) -> int | None:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT MAX(run_number) FROM runs").fetchone()
    if row is None or row[0] is None:
        return None
    return int(row[0])
