"""
run_memory.py
-------------
Run-history database for GF Updater V3.

Manages:
  - persistent run registry (runs table)
  - input provenance (run_inputs table)
  - output artifact registry (run_artifacts table)
  - correction log (run_corrections table)
  - stale-invalidation log (run_invalidation_log table)

Design:
  - SQLite for all metadata, lineage, and hashes
  - Artifact files live on disk under runs/run_NNNN/
  - DB stores file paths, hashes, and metadata — not binary blobs
  - Run 0 is the immutable baseline; all later runs derive from it
  - Stale-invalidation propagates when the baseline is corrected

Artifact folder layout:
    <base_dir>/
      data/
        run_memory.db          ← this DB
      runs/
        run_0000/              ← Run 0 artifacts
        run_0001/              ← Run 1 artifacts
        ...
"""

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn(db_path: str) -> sqlite3.Connection:
    os.makedirs(Path(db_path).parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def sha256_file(path: str) -> str:
    """Return SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_run_dir(base_dir: str, run_number: int) -> str:
    """
    Return the canonical artifact directory for a run.
    Example: get_run_dir("/project", 3) → "/project/runs/run_0003"
    """
    return str(Path(base_dir) / "runs" / f"run_{run_number:04d}")


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_number                  INTEGER NOT NULL UNIQUE,
    run_label                   TEXT    NULL,
    created_at                  TEXT    NOT NULL,
    run_type                    TEXT    NOT NULL,
    parent_run_number           INTEGER NULL,
    root_run_number             INTEGER NOT NULL,
    based_on_run_number         INTEGER NULL,
    is_baseline                 INTEGER NOT NULL DEFAULT 0,
    is_current                  INTEGER NOT NULL DEFAULT 0,
    is_stale                    INTEGER NOT NULL DEFAULT 0,
    stale_reason                TEXT    NULL,
    notes                       TEXT    NULL,
    core_version                TEXT    NULL,
    report_memory_snapshot_hash TEXT    NULL,
    input_signature             TEXT    NULL,
    summary_json                TEXT    NULL,
    status                      TEXT    NOT NULL DEFAULT 'STARTED',
    completed_at                TEXT    NULL,
    error_message               TEXT    NULL
);

CREATE TABLE IF NOT EXISTS run_inputs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_number        INTEGER NOT NULL,
    input_type        TEXT    NOT NULL,
    source_filename   TEXT    NULL,
    source_file_hash  TEXT    NULL,
    source_path       TEXT    NULL,
    imported_at       TEXT    NOT NULL,
    metadata_json     TEXT    NULL,
    FOREIGN KEY(run_number) REFERENCES runs(run_number) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS run_artifacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_number    INTEGER NOT NULL,
    artifact_type TEXT    NOT NULL,
    artifact_name TEXT    NOT NULL,
    file_path     TEXT    NOT NULL,
    file_hash     TEXT    NULL,
    created_at    TEXT    NOT NULL,
    format        TEXT    NULL,
    row_count     INTEGER NULL,
    metadata_json TEXT    NULL,
    UNIQUE(run_number, artifact_type, artifact_name),
    FOREIGN KEY(run_number) REFERENCES runs(run_number) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS run_corrections (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    source_run_number        INTEGER NOT NULL,
    correction_type          TEXT    NOT NULL,
    correction_key           TEXT    NOT NULL,
    correction_value_json    TEXT    NOT NULL,
    created_at               TEXT    NOT NULL,
    applies_from_run_number  INTEGER NOT NULL DEFAULT 0,
    notes                    TEXT    NULL,
    FOREIGN KEY(source_run_number) REFERENCES runs(run_number) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS run_invalidation_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    affected_run_number     INTEGER NOT NULL,
    invalidated_by_run_number INTEGER NOT NULL,
    reason                  TEXT    NOT NULL,
    created_at              TEXT    NOT NULL,
    FOREIGN KEY(affected_run_number) REFERENCES runs(run_number) ON DELETE CASCADE,
    FOREIGN KEY(invalidated_by_run_number) REFERENCES runs(run_number) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_run_number
    ON runs(run_number);
CREATE INDEX IF NOT EXISTS idx_runs_root
    ON runs(root_run_number);
CREATE INDEX IF NOT EXISTS idx_runs_parent
    ON runs(parent_run_number);
CREATE INDEX IF NOT EXISTS idx_runs_is_current
    ON runs(is_current);
CREATE INDEX IF NOT EXISTS idx_runs_is_stale
    ON runs(is_stale);

CREATE INDEX IF NOT EXISTS idx_ri_run_number
    ON run_inputs(run_number);

CREATE INDEX IF NOT EXISTS idx_ra_run_number
    ON run_artifacts(run_number);
CREATE INDEX IF NOT EXISTS idx_ra_artifact_type
    ON run_artifacts(artifact_type);

CREATE INDEX IF NOT EXISTS idx_rc_source_run
    ON run_corrections(source_run_number);

CREATE INDEX IF NOT EXISTS idx_ril_affected
    ON run_invalidation_log(affected_run_number);
"""


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _table_sql(conn: sqlite3.Connection, table_name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row[0] if row and row[0] else ""


def _recreate_table(conn: sqlite3.Connection, table_name: str, create_sql: str, copy_sql: str) -> None:
    temp_name = f"{table_name}__new"
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(f"DROP TABLE IF EXISTS {temp_name}")
    conn.execute(create_sql.replace(f"CREATE TABLE {table_name}", f"CREATE TABLE {temp_name}"))
    conn.execute(copy_sql.format(dst=temp_name, src=table_name))
    conn.execute(f"DROP TABLE {table_name}")
    conn.execute(f"ALTER TABLE {temp_name} RENAME TO {table_name}")
    conn.execute("PRAGMA foreign_keys=ON")


def _migrate_run_memory_schema(conn: sqlite3.Connection) -> None:
    run_cols = _table_columns(conn, "runs")
    if "status" not in run_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN status TEXT NOT NULL DEFAULT 'STARTED'")
        conn.execute(
            """
            UPDATE runs
            SET status = CASE
                WHEN is_current = 1 THEN 'COMPLETED'
                ELSE 'STARTED'
            END
            WHERE status IS NULL OR status = ''
            """
        )
    if "completed_at" not in run_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN completed_at TEXT NULL")
    if "error_message" not in run_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN error_message TEXT NULL")

    run_inputs_sql = _table_sql(conn, "run_inputs")
    if "REFERENCES runs(run_number)" not in run_inputs_sql:
        _recreate_table(
            conn,
            "run_inputs",
            """
            CREATE TABLE run_inputs (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                run_number        INTEGER NOT NULL,
                input_type        TEXT    NOT NULL,
                source_filename   TEXT    NULL,
                source_file_hash  TEXT    NULL,
                source_path       TEXT    NULL,
                imported_at       TEXT    NOT NULL,
                metadata_json     TEXT    NULL,
                FOREIGN KEY(run_number) REFERENCES runs(run_number) ON DELETE CASCADE
            )
            """,
            """
            INSERT INTO {dst}
                (id, run_number, input_type, source_filename, source_file_hash, source_path, imported_at, metadata_json)
            SELECT id, run_number, input_type, source_filename, source_file_hash, source_path, imported_at, metadata_json
            FROM {src}
            """,
        )

    run_artifacts_sql = _table_sql(conn, "run_artifacts")
    if "REFERENCES runs(run_number)" not in run_artifacts_sql or "UNIQUE(run_number, artifact_type, artifact_name)" not in run_artifacts_sql:
        _recreate_table(
            conn,
            "run_artifacts",
            """
            CREATE TABLE run_artifacts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                run_number    INTEGER NOT NULL,
                artifact_type TEXT    NOT NULL,
                artifact_name TEXT    NOT NULL,
                file_path     TEXT    NOT NULL,
                file_hash     TEXT    NULL,
                created_at    TEXT    NOT NULL,
                format        TEXT    NULL,
                row_count     INTEGER NULL,
                metadata_json TEXT    NULL,
                UNIQUE(run_number, artifact_type, artifact_name),
                FOREIGN KEY(run_number) REFERENCES runs(run_number) ON DELETE CASCADE
            )
            """,
            """
            INSERT OR IGNORE INTO {dst}
                (id, run_number, artifact_type, artifact_name, file_path, file_hash, created_at, format, row_count, metadata_json)
            SELECT id, run_number, artifact_type, artifact_name, file_path, file_hash, created_at, format, row_count, metadata_json
            FROM {src}
            ORDER BY id
            """,
        )

    run_corrections_sql = _table_sql(conn, "run_corrections")
    if "REFERENCES runs(run_number)" not in run_corrections_sql:
        _recreate_table(
            conn,
            "run_corrections",
            """
            CREATE TABLE run_corrections (
                id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                source_run_number        INTEGER NOT NULL,
                correction_type          TEXT    NOT NULL,
                correction_key           TEXT    NOT NULL,
                correction_value_json    TEXT    NOT NULL,
                created_at               TEXT    NOT NULL,
                applies_from_run_number  INTEGER NOT NULL DEFAULT 0,
                notes                    TEXT    NULL,
                FOREIGN KEY(source_run_number) REFERENCES runs(run_number) ON DELETE CASCADE
            )
            """,
            """
            INSERT INTO {dst}
                (id, source_run_number, correction_type, correction_key, correction_value_json, created_at, applies_from_run_number, notes)
            SELECT id, source_run_number, correction_type, correction_key, correction_value_json, created_at, applies_from_run_number, notes
            FROM {src}
            """,
        )

    run_invalidation_sql = _table_sql(conn, "run_invalidation_log")
    if "REFERENCES runs(run_number)" not in run_invalidation_sql:
        _recreate_table(
            conn,
            "run_invalidation_log",
            """
            CREATE TABLE run_invalidation_log (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                affected_run_number       INTEGER NOT NULL,
                invalidated_by_run_number INTEGER NOT NULL,
                reason                    TEXT    NOT NULL,
                created_at                TEXT    NOT NULL,
                FOREIGN KEY(affected_run_number) REFERENCES runs(run_number) ON DELETE CASCADE,
                FOREIGN KEY(invalidated_by_run_number) REFERENCES runs(run_number) ON DELETE CASCADE
            )
            """,
            """
            INSERT INTO {dst}
                (id, affected_run_number, invalidated_by_run_number, reason, created_at)
            SELECT id, affected_run_number, invalidated_by_run_number, reason, created_at
            FROM {src}
            """,
        )


def init_run_memory_db(db_path: str) -> None:
    """
    Create all run-history tables and indexes if they do not already exist.
    Safe to call on every pipeline start.
    """
    os.makedirs(Path(db_path).parent, exist_ok=True)
    with _conn(db_path) as conn:
        conn.executescript(_DDL)
        _migrate_run_memory_schema(conn)
        conn.executescript(_DDL)
    logger.debug("init_run_memory_db: schema ready at %s", db_path)


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------

def get_next_run_number(db_path: str) -> int:
    """
    Return the next run number to use.
    If no runs exist → 0 (Run 0 / baseline).
    Otherwise → max(run_number) + 1.
    """
    with _conn(db_path) as conn:
        row = conn.execute("SELECT MAX(run_number) FROM runs").fetchone()
    if row[0] is None:
        return 0
    return int(row[0]) + 1


def baseline_run_exists(db_path: str) -> bool:
    """Return True when Run 0 exists and is marked as the baseline."""
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM runs
            WHERE run_number = 0 AND is_baseline = 1
            LIMIT 1
            """
        ).fetchone()
    return row is not None


def create_run(
    db_path: str,
    run_number: int,
    run_type: str,
    parent_run_number: Optional[int],
    root_run_number: int,
    based_on_run_number: Optional[int],
    is_baseline: bool = False,
    run_label: Optional[str] = None,
    notes: Optional[str] = None,
    core_version: Optional[str] = None,
    report_memory_snapshot_hash: Optional[str] = None,
    input_signature: Optional[str] = None,
    summary_json: Optional[str] = None,
) -> None:
    """
    Insert a new run record.

    run_type examples: BASELINE, INCREMENTAL, REBUILD
    """
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_number, run_label, created_at, run_type,
                parent_run_number, root_run_number, based_on_run_number,
                is_baseline, is_current, is_stale, stale_reason, status,
                notes, core_version, report_memory_snapshot_hash,
                input_signature, summary_json
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, 0, 0, NULL, 'STARTED',
                ?, ?, ?,
                ?, ?
            )
            """,
            (
                run_number, run_label, _now_utc(), run_type,
                parent_run_number, root_run_number, based_on_run_number,
                1 if is_baseline else 0,
                notes, core_version, report_memory_snapshot_hash,
                input_signature, summary_json,
            ),
        )
    logger.debug("create_run: run %d (%s) created", run_number, run_type)


def update_run_metadata(
    db_path: str,
    run_number: int,
    *,
    core_version: Optional[str] = None,
    report_memory_snapshot_hash: Optional[str] = None,
    input_signature: Optional[str] = None,
    summary_json: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """Update selected metadata fields on an existing run."""
    updates = []
    params = []
    for col, value in (
        ("core_version", core_version),
        ("report_memory_snapshot_hash", report_memory_snapshot_hash),
        ("input_signature", input_signature),
        ("summary_json", summary_json),
        ("notes", notes),
    ):
        if value is not None:
            updates.append(f"{col} = ?")
            params.append(value)
    if not updates:
        return
    params.append(run_number)
    with _conn(db_path) as conn:
        conn.execute(
            f"UPDATE runs SET {', '.join(updates)} WHERE run_number = ?",
            params,
        )


def _clean_error_message(error_message: str) -> str:
    return " ".join(str(error_message or "").split())[:500]


def finalize_run_success(db_path: str, run_number: int) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET status = 'COMPLETED',
                completed_at = ?,
                error_message = NULL
            WHERE run_number = ?
            """,
            (_now_utc(), run_number),
        )


def finalize_run_failure(db_path: str, run_number: int, error_message: str) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            """
            UPDATE runs
            SET status = 'FAILED',
                completed_at = ?,
                error_message = ?
            WHERE run_number = ?
            """,
            (_now_utc(), _clean_error_message(error_message), run_number),
        )


def mark_run_current(db_path: str, run_number: int) -> None:
    """
    Mark the given run as the current run.
    Unsets the current flag on any previously-current run.
    """
    with _conn(db_path) as conn:
        conn.execute("UPDATE runs SET is_current = 0 WHERE is_current = 1")
        conn.execute(
            "UPDATE runs SET is_current = 1 WHERE run_number = ?",
            (run_number,),
        )
    logger.debug("mark_run_current: run %d is now current", run_number)


# ---------------------------------------------------------------------------
# Input registration
# ---------------------------------------------------------------------------

def register_run_input(
    db_path: str,
    run_number: int,
    input_type: str,
    source_filename: Optional[str],
    source_file_hash: Optional[str],
    source_path: Optional[str],
    metadata_json: Optional[str] = None,
) -> None:
    """
    Register a source file (or logical input) used by a run.

    input_type examples: GED, GF, REPORT, REPORT_MEMORY, BOOTSTRAP, MAPPING
    """
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO run_inputs
                (run_number, input_type, source_filename, source_file_hash,
                 source_path, imported_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_number, input_type, source_filename, source_file_hash,
             source_path, _now_utc(), metadata_json),
        )


# ---------------------------------------------------------------------------
# Artifact registration
# ---------------------------------------------------------------------------

def register_run_artifact(
    db_path: str,
    run_number: int,
    artifact_type: str,
    artifact_name: str,
    file_path: str,
    file_hash: Optional[str] = None,
    format: Optional[str] = None,
    row_count: Optional[int] = None,
    metadata_json: Optional[str] = None,
) -> None:
    """
    Register an output artifact produced by a run.

    artifact_type examples:
      FINAL_GF, DISCREPANCY_REPORT, ANOMALY_REPORT, AUTO_RESOLUTION_LOG,
      IGNORED_ITEMS_LOG, INSERT_LOG, RECONCILIATION_LOG,
      MISSING_IN_GED_DIAGNOSIS, MISSING_IN_GED_TRUE,
      MISSING_IN_GF_DIAGNOSIS, MISSING_IN_GF_TRUE,
      NEW_SUBMITTAL_ANALYSIS, CONSULTANT_MATCH_REPORT,
      EFFECTIVE_RESPONSES, DEBUG_EXPORT, OUTPUT_PACKAGE

    file_path should be an absolute path to the artifact copy inside the run dir.
    """
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO run_artifacts
                (run_number, artifact_type, artifact_name, file_path,
                 file_hash, created_at, format, row_count, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_number, artifact_type, artifact_name)
            DO UPDATE SET
                file_path = excluded.file_path,
                file_hash = excluded.file_hash,
                created_at = excluded.created_at,
                format = excluded.format,
                row_count = excluded.row_count,
                metadata_json = excluded.metadata_json
            """,
            (run_number, artifact_type, artifact_name, file_path,
             file_hash, _now_utc(), format, row_count, metadata_json),
        )


def list_run_artifacts(db_path: str, run_number: int) -> pd.DataFrame:
    """Return all artifacts registered for a run."""
    with _conn(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM run_artifacts WHERE run_number = ? ORDER BY artifact_type, artifact_name",
            conn,
            params=(run_number,),
        )
    return df


def get_artifact_by_type(
    db_path: str,
    run_number: int,
    artifact_type: str,
) -> pd.DataFrame:
    """
    Return artifacts of a specific type for a given run.
    Useful for UI export: e.g. get_artifact_by_type(db, run, "FINAL_GF").
    Returns empty DataFrame if not found.
    """
    with _conn(db_path) as conn:
        df = pd.read_sql_query(
            """
            SELECT * FROM run_artifacts
            WHERE run_number = ? AND artifact_type = ?
            ORDER BY created_at DESC
            """,
            conn,
            params=(run_number, artifact_type),
        )
    return df


# ---------------------------------------------------------------------------
# Run queries
# ---------------------------------------------------------------------------

def get_current_run(db_path: str) -> pd.DataFrame:
    """Return the row for the current run (or empty DataFrame if none)."""
    with _conn(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM runs WHERE is_current = 1 LIMIT 1",
            conn,
        )
    return df


def list_runs(db_path: str) -> pd.DataFrame:
    """Return all run rows ordered by run_number."""
    with _conn(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM runs ORDER BY run_number",
            conn,
        )
    return df


def get_run_status_summary(db_path: str, run_number: int) -> dict:
    with _conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT run_number, status, is_current, is_stale
            FROM runs
            WHERE run_number = ?
            """,
            (run_number,),
        ).fetchone()
        if row is None:
            return {}
        artifact_count = conn.execute(
            "SELECT COUNT(*) FROM run_artifacts WHERE run_number = ?",
            (run_number,),
        ).fetchone()[0]
        input_count = conn.execute(
            "SELECT COUNT(*) FROM run_inputs WHERE run_number = ?",
            (run_number,),
        ).fetchone()[0]
    return {
        "run_number": row[0],
        "status": row[1],
        "is_current": bool(row[2]),
        "is_stale": bool(row[3]),
        "artifact_count": int(artifact_count),
        "input_count": int(input_count),
    }


# ---------------------------------------------------------------------------
# Corrections and stale propagation
# ---------------------------------------------------------------------------

def register_correction(
    db_path: str,
    source_run_number: int,
    correction_type: str,
    correction_key: str,
    correction_value_json: str,
    applies_from_run_number: int = 0,
    notes: Optional[str] = None,
) -> None:
    """
    Record a correction against a run (typically Run 0).

    correction_type examples:
      AMBIGUOUS_REPORT_MATCH, MANUAL_OVERRIDE, BASELINE_FIX

    correction_key:
      A stable identifier for the item being corrected
      (e.g. "doc_id:CONC-ARC-0042|consultant:AMO HQE LE SOMMER")

    correction_value_json:
      JSON string encoding the correction payload.
    """
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO run_corrections
                (source_run_number, correction_type, correction_key,
                 correction_value_json, created_at, applies_from_run_number, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source_run_number, correction_type, correction_key,
             correction_value_json, _now_utc(), applies_from_run_number, notes),
        )
    logger.info(
        "register_correction: correction type=%s key=%s on run %d",
        correction_type, correction_key, source_run_number,
    )


def register_correction_and_invalidate_descendants(
    db_path: str,
    source_run_number: int,
    correction_type: str,
    correction_key: str,
    correction_value_json: str,
    reason: str,
    applies_from_run_number: int = 0,
    notes: Optional[str] = None,
) -> int:
    """
    Record a correction, then mark all descendant runs stale.

    Returns the number of runs newly invalidated.
    """
    register_correction(
        db_path=db_path,
        source_run_number=source_run_number,
        correction_type=correction_type,
        correction_key=correction_key,
        correction_value_json=correction_value_json,
        applies_from_run_number=applies_from_run_number,
        notes=notes,
    )
    return invalidate_descendant_runs(
        db_path=db_path,
        source_run_number=source_run_number,
        reason=reason,
    )


def invalidate_descendant_runs(
    db_path: str,
    source_run_number: int,
    reason: str,
) -> int:
    """
    Mark all runs that are derived from source_run_number as stale.

    A run is a "descendant" if:
      - it appears anywhere in the based_on_run_number lineage below source_run_number, OR
      - source_run_number is the baseline and root_run_number == source_run_number

    The source run itself is NOT marked stale.

    Writes entries into run_invalidation_log.
    Returns the count of runs newly marked stale.
    """
    now = _now_utc()
    with _conn(db_path) as conn:
        # Find all candidate descendant runs
        rows = conn.execute(
            """
            WITH RECURSIVE descendants(run_number) AS (
                SELECT run_number
                FROM runs
                WHERE based_on_run_number = ?
                UNION
                SELECT r.run_number
                FROM runs r
                JOIN descendants d
                  ON r.based_on_run_number = d.run_number
            )
            SELECT DISTINCT run_number
            FROM runs
            WHERE run_number != ?
              AND is_stale = 0
              AND (
                    run_number IN descendants
                 OR (? = 0 AND root_run_number = ?)
              )
            """,
            (
                source_run_number,
                source_run_number,
                source_run_number,
                source_run_number,
            ),
        ).fetchall()

        affected = [r[0] for r in rows]

        for rn in affected:
            conn.execute(
                "UPDATE runs SET is_stale = 1, stale_reason = ? WHERE run_number = ?",
                (reason, rn),
            )
            conn.execute(
                """
                INSERT INTO run_invalidation_log
                    (affected_run_number, invalidated_by_run_number, reason, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (rn, source_run_number, reason, now),
            )

    logger.info(
        "invalidate_descendant_runs: %d run(s) marked stale (source=%d, reason=%s)",
        len(affected), source_run_number, reason,
    )
    return len(affected)


# ---------------------------------------------------------------------------
# Artifact copy + bundle helpers
# ---------------------------------------------------------------------------

def copy_artifact_to_run_dir(
    src_path: str,
    run_dir: str,
    subfolder: Optional[str] = None,
) -> Optional[str]:
    """
    Copy a file into the run directory.
    Returns the destination absolute path, or None if src_path does not exist.

    sub_folder: optional sub-directory inside run_dir (e.g. "debug")
    """
    src = Path(src_path)
    if not src.exists():
        return None
    dest_dir = Path(run_dir)
    if subfolder:
        dest_dir = dest_dir / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(str(src), str(dest))
    return str(dest)


def export_run_artifacts_bundle(
    db_path: str,
    run_number: int,
    output_zip_path: str,
    artifact_types: Optional[list] = None,
) -> str:
    """
    Bundle all (or selected) artifact files for a run into a zip archive.

    artifact_types: if given, only those types are included.
                    if None, all artifacts for the run are bundled.

    Returns the absolute path to the created zip file.

    Files that no longer exist on disk are skipped with a warning.
    """
    artifacts = list_run_artifacts(db_path, run_number)

    if artifact_types is not None:
        artifacts = artifacts[artifacts["artifact_type"].isin(artifact_types)]

    output_zip_path = str(Path(output_zip_path).resolve())
    os.makedirs(Path(output_zip_path).parent, exist_ok=True)

    files_added = 0
    files_missing = 0

    with zipfile.ZipFile(output_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for _, row in artifacts.iterrows():
            fpath = row["file_path"]
            if not fpath or not Path(fpath).exists():
                logger.warning(
                    "export_run_artifacts_bundle: artifact not on disk, skipping: %s", fpath
                )
                files_missing += 1
                continue
            # Preserve relative path from inside the run dir for readability
            arcname = Path(fpath).name
            # Keep debug/ subfolder structure in the zip if the file is in a debug dir
            parts = Path(fpath).parts
            if "debug" in parts:
                arcname = "debug/" + Path(fpath).name
            zf.write(fpath, arcname)
            files_added += 1

    logger.info(
        "export_run_artifacts_bundle: run %d → %s (%d files, %d missing)",
        run_number, output_zip_path, files_added, files_missing,
    )
    return output_zip_path
