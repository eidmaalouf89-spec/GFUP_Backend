"""
report_memory.py
----------------
SQLite-backed persistence layer for consultant report responses.

Purpose:
  Once a consultant report is ingested, its matched response data becomes
  persistent truth for this project.  Future pipeline runs load this data
  from the DB so consultant answers are never lost even if GED still shows
  the consultant as pending.

Tables:
  ingested_reports           — registry of every processed source file
  persisted_report_responses — one row per (consultant, doc_id, file_hash)

All timestamps are stored as ISO-8601 strings.
Uses stdlib sqlite3 only — no extra dependencies.

Note on schema migration:
  If the DB was created by an older version that included a project_id column,
  init_report_memory_db() automatically drops and recreates the tables so the
  new schema is applied cleanly.  Run the bootstrap script afterward to re-seed.
"""

import hashlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL — current schema (no project_id)
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS ingested_reports (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type      TEXT    NOT NULL,
    source_filename  TEXT    NOT NULL,
    source_file_hash TEXT    NOT NULL,
    ingested_at      TEXT    NOT NULL,
    report_period    TEXT    NULL,
    row_count        INTEGER NOT NULL,
    status           TEXT    NOT NULL DEFAULT 'INGESTED',
    UNIQUE(source_file_hash)
);

CREATE TABLE IF NOT EXISTS persisted_report_responses (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    consultant           TEXT    NOT NULL,
    doc_id               TEXT    NOT NULL,
    report_status        TEXT    NULL,
    report_response_date TEXT    NULL,
    report_comment       TEXT    NULL,
    source_filename      TEXT    NOT NULL,
    source_file_hash     TEXT    NOT NULL,
    ingested_at          TEXT    NOT NULL,
    match_confidence     REAL    NULL,
    match_method         TEXT    NULL,
    is_active            INTEGER NOT NULL DEFAULT 1,
    UNIQUE(consultant, doc_id, source_file_hash)
);

CREATE INDEX IF NOT EXISTS idx_prr_doc_id    ON persisted_report_responses(doc_id);
CREATE INDEX IF NOT EXISTS idx_prr_consul    ON persisted_report_responses(consultant);
CREATE INDEX IF NOT EXISTS idx_prr_hash      ON persisted_report_responses(source_file_hash);
CREATE INDEX IF NOT EXISTS idx_ir_hash       ON ingested_reports(source_file_hash);
"""


# ---------------------------------------------------------------------------
# Schema migration helper
# ---------------------------------------------------------------------------

def _migrate_if_needed(conn: sqlite3.Connection) -> None:
    """
    Drop and recreate tables when an old project_id schema is detected.
    This is a one-time migration; run bootstrap afterward to re-seed.
    """
    cur = conn.execute("PRAGMA table_info(ingested_reports)")
    cols = [row[1] for row in cur.fetchall()]
    if "project_id" in cols:
        logger.warning(
            "report_memory: old schema with project_id detected — "
            "dropping tables and recreating with new schema. "
            "Re-run the bootstrap script to restore data."
        )
        conn.executescript("""
            DROP TABLE IF EXISTS persisted_report_responses;
            DROP TABLE IF EXISTS ingested_reports;
        """)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_report_memory_db(db_path: str) -> None:
    """
    Create the DB file and tables if they do not already exist.
    Automatically migrates old project_id schema if detected.
    Safe to call on every pipeline run (idempotent once schema is current).
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        _migrate_if_needed(conn)
        conn.executescript(_DDL)
        conn.commit()
        logger.debug("report_memory DB initialised: %s", db_path)
    finally:
        conn.close()


def sha256_file(file_path: str) -> str:
    """
    Compute a stable SHA-256 hex digest of a file's binary contents.
    Used as the canonical identity of a source report file.
    """
    h = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_report_already_ingested(db_path: str, file_hash: str) -> bool:
    """
    Return True if file_hash is already registered in ingested_reports.
    This is the primary deduplication gate — filename alone is NOT enough.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT 1 FROM ingested_reports WHERE source_file_hash = ? LIMIT 1",
            (file_hash,),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def register_ingested_report(
    db_path: str,
    report_type: str,
    source_filename: str,
    source_file_hash: str,
    row_count: int,
    report_period: Optional[str] = None,
    status: str = "INGESTED",
) -> None:
    """
    Register a source report file as ingested.
    Uses INSERT OR IGNORE so re-registering the same hash is a no-op.

    Parameters
    ----------
    db_path           : absolute path to the SQLite file
    report_type       : source category (e.g. "SOCOTEC", "TERRELL", "AVLS")
    source_filename   : original filename or logical identifier (for display)
    source_file_hash  : SHA-256 hex digest (or BOOTSTRAP::<name> sentinel)
    row_count         : number of matched response rows from this file
    report_period     : optional date/period string for human reference
    status            : lifecycle status, default "INGESTED"
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO ingested_reports
                (report_type, source_filename, source_file_hash,
                 ingested_at, report_period, row_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (report_type, source_filename, source_file_hash,
             now_iso, report_period, row_count, status),
        )
        conn.commit()
        logger.debug(
            "register_ingested_report: %s  hash=%s  rows=%d",
            source_filename, source_file_hash[:12], row_count,
        )
    finally:
        conn.close()


def upsert_report_responses(
    db_path: str,
    responses_df: pd.DataFrame,
) -> int:
    """
    Store (or update) report-derived consultant responses.

    responses_df must contain these columns (extras are silently ignored):
        consultant           — canonical approver name (matches GED approver_canonical)
        doc_id               — matched GED document ID
        source_filename      — logical identifier of the source report file
        source_file_hash     — SHA-256 hex digest (or sentinel)

    Optional columns (NULL-safe if absent):
        report_status        — normalised status from consultant report (e.g. "VSO")
        report_response_date — date string from consultant report
        report_comment       — comment/observation text
        match_confidence     — confidence level: "HIGH" / "MEDIUM" / "LOW" or float
        match_method         — method string from consultant_matcher

    Confidence is normalised to float before storage:
        HIGH → 1.0 | MEDIUM → 0.7 | LOW → 0.4 | numeric → cast directly

    Returns number of rows written (inserted or updated).
    """
    if responses_df is None or responses_df.empty:
        logger.debug("upsert_report_responses: empty DataFrame, nothing to write")
        return 0

    now_iso = datetime.now(timezone.utc).isoformat()
    _conf_map = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}

    def _get(row, col, default=None):
        """Safe column accessor — returns default for absent, None, or blank values."""
        val = row.get(col, default) if isinstance(row, dict) else getattr(row, col, default)
        if val is None:
            return default
        s = str(val).strip()
        return s if s not in ("", "nan", "None", "NaT") else default

    conn = sqlite3.connect(db_path)
    written = 0
    try:
        for _, row in responses_df.iterrows():
            consultant = _get(row, "consultant")
            doc_id     = _get(row, "doc_id")
            src_file   = _get(row, "source_filename", "")
            src_hash   = _get(row, "source_file_hash", "")

            # Skip rows missing core identity fields
            if not consultant or not doc_id or not src_hash:
                continue

            report_status  = _get(row, "report_status")
            report_date    = _get(row, "report_response_date")
            report_comment = _get(row, "report_comment")
            raw_conf       = _get(row, "match_confidence")
            match_method   = _get(row, "match_method")

            # Normalise confidence to float
            conf_float: Optional[float] = None
            if raw_conf is not None:
                if isinstance(raw_conf, (int, float)):
                    conf_float = float(raw_conf)
                else:
                    conf_float = _conf_map.get(str(raw_conf).upper())

            conn.execute(
                """
                INSERT INTO persisted_report_responses
                    (consultant, doc_id,
                     report_status, report_response_date, report_comment,
                     source_filename, source_file_hash, ingested_at,
                     match_confidence, match_method, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(consultant, doc_id, source_file_hash)
                DO UPDATE SET
                    report_status        = excluded.report_status,
                    report_response_date = excluded.report_response_date,
                    report_comment       = excluded.report_comment,
                    ingested_at          = excluded.ingested_at,
                    match_confidence     = excluded.match_confidence,
                    match_method         = excluded.match_method,
                    is_active            = 1
                """,
                (
                    consultant, doc_id,
                    report_status, report_date, report_comment,
                    src_file, src_hash, now_iso,
                    conf_float, match_method,
                ),
            )
            written += 1

        conn.commit()
        logger.info("upsert_report_responses: %d rows written", written)
    finally:
        conn.close()

    return written


def load_persisted_report_responses(db_path: str) -> pd.DataFrame:
    """
    Load all active persisted report responses.

    Returns a DataFrame with columns:
        consultant, doc_id, report_status, report_response_date,
        report_comment, source_filename, source_file_hash,
        ingested_at, match_confidence, match_method

    Returns an empty DataFrame (with those columns) if nothing is found.
    """
    _COLUMNS = [
        "consultant", "doc_id", "report_status", "report_response_date",
        "report_comment", "source_filename", "source_file_hash",
        "ingested_at", "match_confidence", "match_method",
    ]

    if not Path(db_path).exists():
        logger.debug("load_persisted_report_responses: DB not found at %s", db_path)
        return pd.DataFrame(columns=_COLUMNS)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT consultant, doc_id, report_status, report_response_date,
                   report_comment, source_filename, source_file_hash,
                   ingested_at, match_confidence, match_method
            FROM persisted_report_responses
            WHERE is_active = 1
            """,
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        logger.info("load_persisted_report_responses: no persisted responses in DB")
        return pd.DataFrame(columns=_COLUMNS)

    df = pd.DataFrame(rows, columns=_COLUMNS)
    logger.info("load_persisted_report_responses: loaded %d rows", len(df))
    return df


def list_ingested_reports(db_path: str) -> pd.DataFrame:
    """
    Return an audit DataFrame of all ingested report registrations.
    Useful for debugging and human review.
    """
    _COLUMNS = [
        "id", "report_type", "source_filename",
        "source_file_hash", "ingested_at", "report_period", "row_count", "status",
    ]

    if not Path(db_path).exists():
        return pd.DataFrame(columns=_COLUMNS)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            """
            SELECT id, report_type, source_filename,
                   source_file_hash, ingested_at, report_period, row_count, status
            FROM ingested_reports
            ORDER BY ingested_at DESC
            """,
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    return pd.DataFrame(rows, columns=_COLUMNS) if rows else pd.DataFrame(columns=_COLUMNS)
