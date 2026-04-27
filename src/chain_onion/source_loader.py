"""
src/chain_onion/source_loader.py
---------------------------------
Step 04 — Read-only normalized source loader for Chain + Onion.

Loads and standardizes three data sources required by the Chain + Onion
analytical layer, adding identity keys per the STEP02 contract.

DOES NOT classify chains, compute onion layers, or modify source data.
All returned DataFrames have the original source columns preserved plus
identity columns added via .assign() (no in-place mutation of source arrays).

Identity model (STEP02 Section A):
    FAMILY_KEY   = str(numero)
    VERSION_KEY  = "{numero}_{indice}"
    INSTANCE_KEY = "{numero}_{indice}_{submission_instance_id}"
                   OR "{version_key}_seq_{N}" (synthetic ordinal fallback)

Exception logic discovered in repo (MANDATORY EXCEPTION / EXCLUSION RULE):
    Defined in: src/flat_ged/input/source_main/consultant_mapping.py
    Constants:  EXCEPTION_COLUMNS (32 entries), RAW_TO_CANONICAL -> "Exception List"
    Applied by: src/flat_ged/transformer.py (build_raw_flat)
    Effect:     Exception List rows are excluded from GED_RAW_FLAT and never
                written to GED_OPERATIONS. This loader sees clean data — no
                re-filtering required. BENTIN: not found in this codebase.

SAS RAPPEL filter note:
    The pre-2026 SAS RAPPEL filter (_apply_sas_filter_flat in stage_read_flat)
    is a pipeline stage concern — it is NOT baked into FLAT_GED.xlsx.
    This source loader reads GED_OPERATIONS as-is. The chain_classifier
    (Step 07) is responsible for portfolio_bucket assignment using data_date.

doc_id / stable identity rule (STEP02 Section A.3):
    doc_id is a UUID generated fresh per loader call. It is session-scoped
    and must NEVER be persisted to any chain output CSV or used as a
    cross-run identifier. family_key / version_key are the stable keys.
"""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Ensure src/ is importable (mirrors flat_ged_runner.py pattern) ────────
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_LOG = logging.getLogger(__name__)

# ── Required columns ───────────────────────────────────────────────────────

_REQUIRED_OPS_COLS: frozenset = frozenset({
    "numero", "indice", "step_order", "step_type",
    "actor_clean", "submittal_date", "response_date",
    "is_blocking", "is_completed", "requires_new_cycle",
    "delay_contribution_days", "cumulative_delay_days",
    "status_clean", "data_date",
})

_REQUIRED_DEBUG_COLS: frozenset = frozenset({
    "numero", "doc_code", "submission_instance_id",
    "instance_role", "instance_resolution_reason",
})

# Bool columns in GED_OPERATIONS stored as string "True"/"False" in xlsx
_OPS_BOOL_COLS: tuple = ("is_completed", "is_blocking", "requires_new_cycle")

# Schema for an empty debug_df returned when DEBUG_TRACE is absent
_DEBUG_EMPTY_COLS: list = [
    "numero", "doc_code", "submission_instance_id",
    "instance_role", "instance_resolution_reason",
    "approver_raw", "actor_type", "date_status_type",
    "family_key", "version_key", "instance_key",
]

# Schema for an empty effective_df
_EFFECTIVE_EMPTY_COLS: list = [
    "doc_id", "approver_canonical", "date_status_type",
    "status_clean", "effective_source", "report_memory_applied",
    "family_key", "version_key",
]

# Exception logic metadata (discovered from repo inspection — carry-forward only)
_EXCEPTION_LOGIC_SUMMARY: dict = {
    "found": True,
    "source_file": "src/flat_ged/input/source_main/consultant_mapping.py",
    "constants": ["EXCEPTION_COLUMNS", "RAW_TO_CANONICAL"],
    "exception_column_count": 32,
    "mapping_target": "Exception List",
    "applied_by": "src/flat_ged/transformer.py (build_raw_flat)",
    "effect": (
        "Exception List columns excluded from GED_RAW_FLAT; "
        "never written to GED_OPERATIONS. ops_df is clean."
    ),
    "bentin_found": False,
    "chain_onion_action": (
        "No re-filtering required. Exception rows absent from ops_df. "
        "Carried forward in metadata only per MANDATORY EXCEPTION RULE."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_bool_cols(df: pd.DataFrame, cols: tuple) -> None:
    """Convert string 'True'/'False' cells to Python bool, in-place."""
    for col in cols:
        if col in df.columns:
            df[col] = df[col].map(
                {"True": True, "False": False, True: True, False: False}
            ).fillna(False)


def _extract_indice_from_doc_code(doc_code_series: pd.Series) -> pd.Series:
    """
    Extract indice from doc_code column.
    Format: "numero|indice" (pipe-separated, e.g. "248000|A").
    Returns indice part or empty string on parse failure.
    """
    return doc_code_series.astype(str).str.split("|").str[1].fillna("")


def _build_ged_responses_for_composition(
    ops_df: pd.DataFrame,
    doc_code_to_id: dict,
) -> pd.DataFrame:
    """
    Build a minimal ged_responses_df from ops_df for build_effective_responses().

    Excludes OPEN_DOC rows (no approver role in workflow steps).
    Derives date_status_type from is_completed / is_blocking / retard_avance_status,
    mirroring the mapping used in stage_read_flat._build_responses_df().

    This is the only place in source_loader.py that replicates pipeline-stage
    logic. It is kept minimal and private — only the fields required by
    build_effective_responses(flat_mode=True) are populated.
    """
    steps = ops_df[ops_df["step_type"] != "OPEN_DOC"]

    records = []
    for _, row in steps.iterrows():
        numero = str(row["numero"]).strip()
        indice = str(row["indice"]).strip()
        doc_id = doc_code_to_id.get((numero, indice))
        if doc_id is None:
            continue

        is_completed = row.get("is_completed") is True
        is_blocking  = row.get("is_blocking")  is True
        retard       = str(row.get("retard_avance_status", "") or "").strip()

        if is_completed:
            dst = "ANSWERED"
        elif is_blocking and retard == "RETARD":
            dst = "PENDING_LATE"
        elif is_blocking:
            dst = "PENDING_IN_DELAY"
        else:
            dst = "NOT_CALLED"

        date_answered = None
        if is_completed:
            resp_raw = str(row.get("response_date", "") or "").strip()
            if resp_raw:
                try:
                    date_answered = pd.Timestamp(resp_raw)
                except Exception:
                    pass

        records.append({
            "doc_id":              doc_id,
            "approver_canonical":  str(row.get("actor_clean", "") or "").strip(),
            "date_status_type":    dst,
            "status_clean":        str(row.get("status_clean", "") or "").strip(),
            "date_answered":       date_answered,
            "response_comment":    str(row.get("observation", "") or "").strip(),
            "flat_data_date":      str(row.get("data_date", "") or "").strip(),
            "flat_phase_deadline": str(row.get("phase_deadline", "") or "").strip(),
            "flat_step_type":      str(row.get("step_type", "") or "").strip(),
        })

    if not records:
        return pd.DataFrame(columns=[
            "doc_id", "approver_canonical", "date_status_type", "status_clean",
            "date_answered", "response_comment", "flat_data_date",
            "flat_phase_deadline", "flat_step_type",
        ])
    return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────────────────────
# Public functions
# ─────────────────────────────────────────────────────────────────────────────

def load_flat_ged(flat_ged_path: Path) -> pd.DataFrame:
    """
    Load GED_OPERATIONS sheet from FLAT_GED.xlsx.

    Returns the original DataFrame plus two identity columns:
        family_key  = str(numero)
        version_key = "{numero}_{indice}"

    Raises
    ------
    FileNotFoundError
        If FLAT_GED.xlsx does not exist at the given path.
    ValueError
        If required columns are absent from GED_OPERATIONS.
    """
    flat_ged_path = Path(flat_ged_path)
    if not flat_ged_path.exists():
        raise FileNotFoundError(
            f"FLAT_GED.xlsx not found: {flat_ged_path}\n"
            f"Run the flat_ged builder first to produce this artifact."
        )

    _LOG.info("load_flat_ged: reading GED_OPERATIONS from %s", flat_ged_path)
    ops_df = pd.read_excel(flat_ged_path, sheet_name="GED_OPERATIONS", dtype=str)

    # Normalize bool columns (stored as "True"/"False" strings in xlsx)
    _normalise_bool_cols(ops_df, _OPS_BOOL_COLS)

    # Validate required columns
    missing = _REQUIRED_OPS_COLS - set(ops_df.columns)
    if missing:
        raise ValueError(
            f"load_flat_ged: GED_OPERATIONS is missing required columns: {sorted(missing)}"
        )

    # Normalize identity columns to string
    ops_df["numero"] = ops_df["numero"].astype(str).str.strip()
    ops_df["indice"] = ops_df["indice"].astype(str).str.strip()

    # Add identity keys (non-mutating)
    ops_df = ops_df.assign(
        family_key=ops_df["numero"].astype(str),
        version_key=ops_df["numero"].astype(str) + "_" + ops_df["indice"].astype(str),
    )

    _LOG.info(
        "load_flat_ged: loaded %d rows, %d unique version_keys",
        len(ops_df), ops_df["version_key"].nunique(),
    )
    return ops_df


def load_debug_trace(debug_trace_path: Path) -> pd.DataFrame:
    """
    Load DEBUG_TRACE.csv and add identity keys.

    doc_code format is "numero|indice" (pipe-separated). indice is derived
    from doc_code since DEBUG_TRACE has no separate indice column.

    Returns the original DataFrame plus:
        family_key   = str(numero)
        version_key  = "{numero}_{indice}"
        instance_key = "{numero}_{indice}_{submission_instance_id}"
                       OR "{version_key}_seq_{N}" (synthetic fallback when
                       submission_instance_id is blank — ordered by CSV row
                       position within the version group)

    If DEBUG_TRACE.csv is missing or unreadable, logs a WARNING and returns
    an empty DataFrame with the expected schema. No exception is raised.
    """
    debug_trace_path = Path(debug_trace_path)

    if not debug_trace_path.exists():
        _LOG.warning(
            "load_debug_trace: DEBUG_TRACE.csv not found at %s — "
            "INSTANCE_KEY will use synthetic ordinal seq_N for all versions. "
            "(Expected on single-mode pipeline runs.)",
            debug_trace_path,
        )
        return pd.DataFrame(columns=_DEBUG_EMPTY_COLS)

    _LOG.info("load_debug_trace: reading %s", debug_trace_path)
    try:
        debug_df = pd.read_csv(
            debug_trace_path, encoding="utf-8-sig", dtype=str, low_memory=False
        )
    except Exception as exc:
        _LOG.warning(
            "load_debug_trace: failed to read DEBUG_TRACE.csv (%s) — returning empty", exc
        )
        return pd.DataFrame(columns=_DEBUG_EMPTY_COLS)

    # Validate required columns
    missing = _REQUIRED_DEBUG_COLS - set(debug_df.columns)
    if missing:
        _LOG.warning(
            "load_debug_trace: DEBUG_TRACE.csv missing required columns %s — returning empty",
            sorted(missing),
        )
        return pd.DataFrame(columns=_DEBUG_EMPTY_COLS)

    # Normalize numero
    debug_df["numero"] = debug_df["numero"].astype(str).str.strip()

    # Derive indice from doc_code ("numero|indice")
    debug_df["indice"] = _extract_indice_from_doc_code(debug_df["doc_code"])

    # Add family_key and version_key
    debug_df = debug_df.assign(
        family_key=debug_df["numero"].astype(str),
        version_key=(
            debug_df["numero"].astype(str) + "_" + debug_df["indice"].astype(str)
        ),
    )

    # Build instance_key
    sub_id = debug_df["submission_instance_id"].astype(str).str.strip()
    has_real_id = sub_id.notna() & ~sub_id.isin(["", "nan", "None", "NaT"])

    # Synthetic seq_N fallback: counter per version_key, ordered by CSV row position
    seq_map: dict = {}
    instance_keys: list = []

    for idx in debug_df.index:
        vk = debug_df.at[idx, "version_key"]
        if has_real_id.at[idx]:
            ik = f"{vk}_{sub_id.at[idx]}"
        else:
            n = seq_map.get(vk, 0) + 1
            seq_map[vk] = n
            ik = f"{vk}_seq_{n}"
        instance_keys.append(ik)

    debug_df = debug_df.assign(instance_key=instance_keys)

    synthetic_count = int((~has_real_id).sum())
    if synthetic_count > 0:
        _LOG.warning(
            "load_debug_trace: %d rows use synthetic instance_key "
            "(submission_instance_id blank) — confidence floor applies per STEP03 Section E",
            synthetic_count,
        )

    _LOG.info(
        "load_debug_trace: loaded %d rows, %d unique version_keys, %d unique instance_keys",
        len(debug_df),
        debug_df["version_key"].nunique(),
        debug_df["instance_key"].nunique(),
    )
    return debug_df


def load_effective_responses(
    ops_df: pd.DataFrame,
    report_memory_db_path: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Build effective_responses_df from GED_OPERATIONS + optional report memory.

    Calls build_effective_responses(flat_mode=True) from src/effective_responses.py.
    Attaches session-scoped family_key and version_key via the doc_id →
    (numero, indice) bridge built internally from ops_df.

    WARNING: family_key / version_key in effective_df are SESSION-SCOPED only.
    They must NOT be persisted to any chain output CSV (STEP02 Section I.2).
    Use them only for intra-session joins to ops_df.

    Parameters
    ----------
    ops_df
        GED_OPERATIONS DataFrame as returned by load_flat_ged().
    report_memory_db_path
        Optional path to report_memory.db. When None or missing, returns
        GED-only composition (no report memory enrichment).

    Returns
    -------
    pd.DataFrame with effective_source, report_memory_applied, family_key,
    version_key columns added. Returns empty DataFrame on any failure.
    """
    if ops_df is None or ops_df.empty:
        _LOG.warning("load_effective_responses: ops_df is empty — returning empty")
        return pd.DataFrame(columns=_EFFECTIVE_EMPTY_COLS)

    try:
        from effective_responses import build_effective_responses  # type: ignore
    except ImportError as exc:
        _LOG.warning(
            "load_effective_responses: cannot import effective_responses (%s) — returning empty",
            exc,
        )
        return pd.DataFrame(columns=_EFFECTIVE_EMPTY_COLS)

    # ── Build doc_id ↔ (numero, indice) bridge ───────────────────────────
    pairs = ops_df[["numero", "indice"]].drop_duplicates()
    doc_code_to_id: dict = {
        (str(r["numero"]).strip(), str(r["indice"]).strip()): str(uuid.uuid4())
        for _, r in pairs.iterrows()
    }
    id_to_pair: dict = {v: k for k, v in doc_code_to_id.items()}

    # ── Build minimal responses_df from ops_df ───────────────────────────
    responses_df = _build_ged_responses_for_composition(ops_df, doc_code_to_id)
    if responses_df.empty:
        _LOG.warning("load_effective_responses: responses_df empty — returning empty")
        return pd.DataFrame(columns=_EFFECTIVE_EMPTY_COLS)

    # ── Load persisted report responses (optional) ────────────────────────
    persisted_df: pd.DataFrame = pd.DataFrame()

    if report_memory_db_path is not None:
        db_path = Path(report_memory_db_path)
        if db_path.exists():
            try:
                from report_memory import load_persisted_report_responses  # type: ignore
                persisted_df = load_persisted_report_responses(str(db_path))
                _LOG.info(
                    "load_effective_responses: loaded %d persisted report responses from %s",
                    len(persisted_df), db_path,
                )
            except Exception as exc:
                _LOG.warning(
                    "load_effective_responses: failed to load report_memory (%s) — using GED only",
                    exc,
                )
        else:
            _LOG.warning(
                "load_effective_responses: report_memory.db not found at %s — using GED only",
                db_path,
            )

    # ── Compose effective_responses ───────────────────────────────────────
    try:
        effective_df = build_effective_responses(
            ged_responses_df=responses_df,
            persisted_report_responses_df=persisted_df,
            flat_mode=True,
        )
    except Exception as exc:
        _LOG.warning(
            "load_effective_responses: build_effective_responses failed (%s) — returning empty",
            exc,
        )
        return pd.DataFrame(columns=_EFFECTIVE_EMPTY_COLS)

    # ── Attach family_key / version_key via bridge (session-scoped) ───────
    def _bridge(doc_id):
        pair = id_to_pair.get(str(doc_id))
        if pair is None:
            return None, None
        numero, indice = pair
        return str(numero), f"{numero}_{indice}"

    fks, vks = zip(*effective_df["doc_id"].map(_bridge)) if not effective_df.empty else ([], [])
    effective_df = effective_df.assign(family_key=list(fks), version_key=list(vks))

    null_bridge = int(effective_df["family_key"].isna().sum())
    if null_bridge > 0:
        _LOG.warning(
            "load_effective_responses: %d rows could not be bridged to (numero, indice)",
            null_bridge,
        )

    _LOG.info(
        "load_effective_responses: %d rows, report_memory=%s",
        len(effective_df),
        str(report_memory_db_path) if report_memory_db_path else "none",
    )
    return effective_df


def load_chain_sources(
    flat_ged_path: Path,
    debug_trace_path: Path,
    report_memory_db_path: Optional[Path] = None,
    *,
    output_dir: Optional[Path] = None,
) -> dict:
    """
    Master orchestrator: load all three sources and return a normalized package.

    Creates output/chain_onion/ directory (Step 04 is permitted to do this
    per STEP02 Section I.6).

    Parameters
    ----------
    flat_ged_path
        Path to FLAT_GED.xlsx (typically output/intermediate/FLAT_GED.xlsx).
    debug_trace_path
        Path to DEBUG_TRACE.csv (typically output/intermediate/DEBUG_TRACE.csv).
    report_memory_db_path
        Optional path to report_memory.db. When None, effective_df uses GED-only truth.
    output_dir
        Override for the output/chain_onion/ directory. Defaults to
        flat_ged_path.parent.parent / "chain_onion".

    Returns
    -------
    dict:
        ops_df        — GED_OPERATIONS DataFrame + family_key + version_key
        debug_df      — DEBUG_TRACE DataFrame + identity keys (empty if absent)
        effective_df  — composed effective_responses + session-scoped keys
        data_date     — ISO date string "YYYY-MM-DD" from ops_df, or ""
        metadata      — dict: row_counts, source paths, missing_sources,
                        warnings, exception_logic summary

    Note: The task spec uses "flat_df" for this key; STEP02 Section I.1 uses
    "ops_df". "ops_df" is used here for compliance with the authoritative
    contract that downstream Steps 05–14 will reference.
    """
    warnings_list: list = []
    missing_sources: list = []

    # ── 1. Load GED_OPERATIONS (mandatory) ───────────────────────────────
    try:
        ops_df = load_flat_ged(flat_ged_path)
    except FileNotFoundError as exc:
        missing_sources.append(str(flat_ged_path))
        warnings_list.append(f"FLAT_GED missing: {exc}")
        _LOG.error("load_chain_sources: FLAT_GED not found — %s", exc)
        return {
            "ops_df":       pd.DataFrame(),
            "debug_df":     pd.DataFrame(columns=_DEBUG_EMPTY_COLS),
            "effective_df": pd.DataFrame(columns=_EFFECTIVE_EMPTY_COLS),
            "data_date":    "",
            "metadata": {
                "flat_ged_path":         str(flat_ged_path),
                "debug_trace_path":      str(debug_trace_path),
                "report_memory_db_path": str(report_memory_db_path) if report_memory_db_path else None,
                "missing_sources":       missing_sources,
                "warnings":              warnings_list,
                "row_counts":            {"ops_df": 0, "debug_df": 0, "effective_df": 0},
                "exception_logic":       _EXCEPTION_LOGIC_SUMMARY,
            },
        }

    # ── 2. Load DEBUG_TRACE (optional) ────────────────────────────────────
    debug_df = load_debug_trace(debug_trace_path)
    if debug_df.empty:
        missing_sources.append(str(debug_trace_path))
        warnings_list.append(
            "DEBUG_TRACE.csv absent — INSTANCE_KEY will use synthetic seq_N. "
            "Layer 1 confidence floor: 40 (per STEP03 Section B.1.5)."
        )

    # ── 3. Load effective_responses (optional) ────────────────────────────
    effective_df = load_effective_responses(ops_df, report_memory_db_path)
    if effective_df.empty:
        missing_sources.append("effective_responses (in-memory composition unavailable)")
        warnings_list.append(
            "effective_df is empty — report memory composition failed or unavailable. "
            "Step 06 chain_events.source will default to 'GED_OPERATIONS' for all rows."
        )

    # ── 4. Extract data_date ──────────────────────────────────────────────
    data_date = ""
    if "data_date" in ops_df.columns:
        dates = ops_df["data_date"].dropna()
        dates = dates[dates.astype(str).str.strip() != ""]
        if not dates.empty:
            raw_val = str(dates.iloc[0]).strip()
            try:
                data_date = str(pd.Timestamp(raw_val).date())
            except Exception:
                data_date = raw_val

    # ── 5. Create output/chain_onion/ ────────────────────────────────────
    if output_dir is None:
        output_dir = Path(flat_ged_path).resolve().parent.parent / "chain_onion"
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        _LOG.info("load_chain_sources: output/chain_onion/ ready at %s", output_dir)
    except Exception as exc:
        warnings_list.append(f"Could not create output/chain_onion/: {exc}")

    # ── 6. Assemble metadata ──────────────────────────────────────────────
    metadata = {
        "flat_ged_path":          str(Path(flat_ged_path).resolve()),
        "debug_trace_path":       str(Path(debug_trace_path).resolve()),
        "report_memory_db_path":  (
            str(Path(report_memory_db_path).resolve()) if report_memory_db_path else None
        ),
        "output_chain_onion_dir": str(Path(output_dir).resolve()),
        "data_date":              data_date,
        "missing_sources":        missing_sources,
        "warnings":               warnings_list,
        "row_counts": {
            "ops_df":       len(ops_df),
            "debug_df":     len(debug_df),
            "effective_df": len(effective_df),
        },
        "unique_version_keys": (
            int(ops_df["version_key"].nunique())
            if "version_key" in ops_df.columns else 0
        ),
        "unique_family_keys": (
            int(ops_df["family_key"].nunique())
            if "family_key" in ops_df.columns else 0
        ),
        "debug_trace_available":  not debug_df.empty,
        "effective_available":    not effective_df.empty,
        "exception_logic":        _EXCEPTION_LOGIC_SUMMARY,
    }

    _LOG.info(
        "load_chain_sources: ops_df=%d rows | debug_df=%d rows | "
        "effective_df=%d rows | data_date=%s",
        len(ops_df), len(debug_df), len(effective_df), data_date,
    )
    return {
        "ops_df":       ops_df,
        "debug_df":     debug_df,
        "effective_df": effective_df,
        "data_date":    data_date,
        "metadata":     metadata,
    }
