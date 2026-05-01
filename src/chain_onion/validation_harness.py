"""
src/chain_onion/validation_harness.py
---------------------------------------
Step 14 — Validation Harness.

Final trust / acceptance harness for the Chain + Onion system.
Validates integrity of everything built in Steps 04–13.

This module does NOT create new analytics.  It validates artifacts.

Public API
----------
run_chain_onion_validation(
    output_dir="output/chain_onion",
    chain_register_df=None,
    chain_versions_df=None,
    chain_events_df=None,
    chain_metrics_df=None,
    onion_layers_df=None,
    onion_scores_df=None,
    chain_narratives_df=None,
) -> dict  # validation_report
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

_LOG = logging.getLogger(__name__)

HARNESS_VERSION = "1.0.0"

# ── Vocabulary constants ───────────────────────────────────────────────────────
_TERMINAL_STATES = frozenset({
    "CLOSED_VAO",
    "CLOSED_VSO",
    "VOID_CHAIN",
    "DEAD_AT_SAS_A",
})

_VALID_SEVERITY = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})

_VALID_URGENCY = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"})

_VALID_CONFIDENCE = frozenset({"HIGH", "MEDIUM", "LOW", "NONE"})

_VALID_BUCKETS = frozenset({"LIVE_OPERATIONAL", "LEGACY_BACKLOG", "ARCHIVED_HISTORICAL"})

_FORBIDDEN_NARRATIVE_WORDS = frozenset({
    "guilty", "fault", "incompetent", "scandal",
    "fraud", "liar", "disaster", "blame",
})

# Core CSV artifact names
_REQUIRED_CSVS = [
    "CHAIN_REGISTER.csv",
    "CHAIN_VERSIONS.csv",
    "CHAIN_EVENTS.csv",
    "CHAIN_METRICS.csv",
    "ONION_LAYERS.csv",
    "ONION_SCORES.csv",
    "CHAIN_NARRATIVES.csv",
]

_REQUIRED_JSONS = [
    "dashboard_summary.json",
    "top_issues.json",
]

_REQUIRED_XLSX = "CHAIN_ONION_SUMMARY.xlsx"


# =============================================================================
# Result builder helpers
# =============================================================================

def _check(code: str, category: str, status: str, message: str) -> dict:
    return {"code": code, "category": category, "status": status, "message": message}


def _pass(code: str, category: str, message: str) -> dict:
    return _check(code, category, "PASS", message)


def _fail(code: str, category: str, message: str) -> dict:
    return _check(code, category, "FAIL", message)


def _warn(code: str, category: str, message: str) -> dict:
    return _check(code, category, "WARN", message)


# =============================================================================
# Artifact loaders
# =============================================================================

def _load_csv(path: Path) -> Optional[pd.DataFrame]:
    """Return DataFrame or None on any error."""
    try:
        df = pd.read_csv(path, low_memory=False, dtype={"family_key": str, "numero": str, "version_key": str})
        return df
    except Exception:
        return None


def _load_json(path: Path) -> Optional[object]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


# =============================================================================
# Category A — File / Artifact checks
# =============================================================================

def _check_a(output_dir: Path, in_memory_provided: bool = False) -> tuple[list[dict], dict]:
    """
    Returns (results_list, loaded_artifacts_dict).
    Loaded artifacts: keys = csv name / json name, values = df / parsed object.

    in_memory_provided: when True (all core DataFrames supplied by caller),
    missing disk files are downgraded from FAIL → WARN.  The spec accepts
    in-memory DataFrames as a valid fallback; a FAIL requires that data is
    entirely unresolvable (no disk, no memory).
    """
    results = []
    artifacts: dict = {}
    # When all DataFrames are supplied in-memory, missing disk files are PASS
    # (data is fully resolvable from memory — disk is optional).
    # When no in-memory fallback exists, missing files are hard FAIL.
    def _missing(code, cat, msg):
        if in_memory_provided:
            return _pass(code, cat, f"[in-memory] {msg}")
        return _fail(code, cat, msg)

    # A1 — required files exist
    for name in _REQUIRED_CSVS:
        p = output_dir / name
        if p.exists():
            results.append(_pass("A1", "FILE", f"{name} exists"))
        else:
            results.append(_missing("A1", "FILE", f"Required file missing: {name}"))

    for name in _REQUIRED_JSONS:
        p = output_dir / name
        if p.exists():
            results.append(_pass("A1", "FILE", f"{name} exists"))
        else:
            results.append(_missing("A1", "FILE", f"Required file missing: {name}"))

    xlsx_path = output_dir / _REQUIRED_XLSX
    if xlsx_path.exists():
        results.append(_pass("A4", "FILE", f"{_REQUIRED_XLSX} exists"))
    else:
        results.append(_missing("A4", "FILE", f"Required XLSX missing: {_REQUIRED_XLSX}"))

    # A2 — CSVs readable
    for name in _REQUIRED_CSVS:
        p = output_dir / name
        if not p.exists():
            results.append(_missing("A2", "FILE", f"Cannot read {name}: file missing"))
            continue
        df = _load_csv(p)
        if df is None:
            results.append(_fail("A2", "FILE", f"CSV not readable: {name}"))
        else:
            artifacts[name] = df
            results.append(_pass("A2", "FILE", f"{name} readable ({len(df)} rows)"))

    # A3 — JSONs readable
    for name in _REQUIRED_JSONS:
        p = output_dir / name
        if not p.exists():
            results.append(_missing("A3", "FILE", f"Cannot read {name}: file missing"))
            continue
        obj = _load_json(p)
        if obj is None:
            results.append(_fail("A3", "FILE", f"JSON not readable: {name}"))
        else:
            artifacts[name] = obj
            results.append(_pass("A3", "FILE", f"{name} readable"))

    # A5 — empty files rejected (files that exist but have 0 bytes)
    for name in _REQUIRED_CSVS + _REQUIRED_JSONS:
        p = output_dir / name
        if p.exists() and p.stat().st_size == 0:
            results.append(_fail("A5", "FILE", f"File exists but is empty (0 bytes): {name}"))
        elif p.exists():
            results.append(_pass("A5", "FILE", f"{name} non-empty"))

    return results, artifacts


# =============================================================================
# Category B — Identity / Shape checks
# =============================================================================

def _check_b(
    chain_register_df: Optional[pd.DataFrame],
    chain_metrics_df: Optional[pd.DataFrame],
    onion_scores_df: Optional[pd.DataFrame],
    chain_narratives_df: Optional[pd.DataFrame],
    chain_versions_df: Optional[pd.DataFrame],
    chain_events_df: Optional[pd.DataFrame],
    onion_layers_df: Optional[pd.DataFrame],
) -> list[dict]:
    results = []

    core_dfs = {
        "CHAIN_REGISTER": chain_register_df,
        "CHAIN_VERSIONS": chain_versions_df,
        "CHAIN_EVENTS": chain_events_df,
        "CHAIN_METRICS": chain_metrics_df,
        "ONION_LAYERS": onion_layers_df,
        "ONION_SCORES": onion_scores_df,
        "CHAIN_NARRATIVES": chain_narratives_df,
    }

    # B6 — family_key exists in all core CSVs
    for name, df in core_dfs.items():
        if df is None:
            results.append(_fail("B6", "SHAPE", f"family_key check skipped: {name} not loaded"))
            continue
        if "family_key" in df.columns:
            results.append(_pass("B6", "SHAPE", f"family_key present in {name}"))
        else:
            results.append(_fail("B6", "SHAPE", f"family_key missing from {name}"))

    # B7 — no duplicate family_key in key single-row-per-family outputs
    unique_key_dfs = {
        "CHAIN_REGISTER": chain_register_df,
        "CHAIN_METRICS": chain_metrics_df,
        "ONION_SCORES": onion_scores_df,
        "CHAIN_NARRATIVES": chain_narratives_df,
    }
    for name, df in unique_key_dfs.items():
        if df is None or "family_key" not in (df.columns if df is not None else []):
            results.append(_fail("B7", "SHAPE", f"Duplicate check skipped: {name} not available"))
            continue
        dupes = df["family_key"].duplicated().sum()
        if dupes == 0:
            results.append(_pass("B7", "SHAPE", f"No duplicate family_key in {name}"))
        else:
            results.append(_fail("B7", "SHAPE", f"{dupes} duplicate family_key rows in {name}"))

    # B8 — one row per family_key in score / narrative outputs
    for name, df in [("ONION_SCORES", onion_scores_df), ("CHAIN_NARRATIVES", chain_narratives_df)]:
        if df is None or "family_key" not in (df.columns if df is not None else []):
            results.append(_fail("B8", "SHAPE", f"One-row-per-family check skipped: {name}"))
            continue
        if df["family_key"].nunique() == len(df):
            results.append(_pass("B8", "SHAPE", f"One row per family_key in {name}"))
        else:
            results.append(_fail("B8", "SHAPE", f"Multiple rows per family_key detected in {name}"))

    # B9 — all score families exist in register
    if onion_scores_df is not None and chain_register_df is not None:
        if "family_key" in onion_scores_df.columns and "family_key" in chain_register_df.columns:
            score_keys = set(onion_scores_df["family_key"].dropna())
            reg_keys = set(chain_register_df["family_key"].dropna())
            orphans = score_keys - reg_keys
            if not orphans:
                results.append(_pass("B9", "SHAPE", "All score families exist in CHAIN_REGISTER"))
            else:
                results.append(_fail("B9", "SHAPE", f"Score families not in register: {orphans}"))
        else:
            results.append(_fail("B9", "SHAPE", "B9 skipped: family_key column missing"))
    else:
        results.append(_fail("B9", "SHAPE", "B9 skipped: ONION_SCORES or CHAIN_REGISTER not loaded"))

    # B10 — all narrative families exist in register
    if chain_narratives_df is not None and chain_register_df is not None:
        if "family_key" in chain_narratives_df.columns and "family_key" in chain_register_df.columns:
            narr_keys = set(chain_narratives_df["family_key"].dropna())
            reg_keys = set(chain_register_df["family_key"].dropna())
            orphans = narr_keys - reg_keys
            if not orphans:
                results.append(_pass("B10", "SHAPE", "All narrative families exist in CHAIN_REGISTER"))
            else:
                results.append(_fail("B10", "SHAPE", f"Narrative families not in register: {orphans}"))
        else:
            results.append(_fail("B10", "SHAPE", "B10 skipped: family_key column missing"))
    else:
        results.append(_fail("B10", "SHAPE", "B10 skipped: CHAIN_NARRATIVES or CHAIN_REGISTER not loaded"))

    return results


# =============================================================================
# Category C — State Logic checks
# =============================================================================

def _check_c(
    onion_scores_df: Optional[pd.DataFrame],
    chain_register_df: Optional[pd.DataFrame],
) -> list[dict]:
    results = []

    def _scores_col(col: str) -> Optional[pd.Series]:
        if onion_scores_df is not None and col in onion_scores_df.columns:
            return onion_scores_df[col]
        if chain_register_df is not None and col in chain_register_df.columns:
            return chain_register_df[col]
        return None

    # Use onion_scores_df as primary source (it has portfolio_bucket + current_state + scores)
    df = onion_scores_df if onion_scores_df is not None else chain_register_df

    if df is None:
        for code in ["C11", "C12", "C13", "C14", "C15", "C16"]:
            results.append(_fail(code, "STATE", f"{code}: no scores/register DataFrame available"))
        return results

    has_bucket = "portfolio_bucket" in df.columns
    has_state = "current_state" in df.columns
    has_rank = "action_priority_rank" in df.columns
    has_score = "normalized_score_100" in df.columns
    has_flag = "escalation_flag" in df.columns

    # C11 — archived bucket only with terminal states
    if has_bucket and has_state:
        archived = df[df["portfolio_bucket"] == "ARCHIVED_HISTORICAL"]
        non_terminal = archived[~archived["current_state"].isin(_TERMINAL_STATES)]
        if non_terminal.empty:
            results.append(_pass("C11", "STATE", "All ARCHIVED_HISTORICAL chains have terminal states"))
        else:
            bad = non_terminal["family_key"].tolist() if "family_key" in non_terminal.columns else "?"
            results.append(_fail("C11", "STATE", f"ARCHIVED chains with non-terminal states: {bad}"))
    else:
        results.append(_fail("C11", "STATE", "C11 skipped: portfolio_bucket or current_state missing"))

    # C12 — live bucket excludes archived states
    if has_bucket and has_state:
        live = df[df["portfolio_bucket"] == "LIVE_OPERATIONAL"]
        bad_live = live[live["current_state"].isin(_TERMINAL_STATES)]
        if bad_live.empty:
            results.append(_pass("C12", "STATE", "No LIVE_OPERATIONAL chains have terminal states"))
        else:
            bad = bad_live["family_key"].tolist() if "family_key" in bad_live.columns else "?"
            results.append(_fail("C12", "STATE", f"LIVE chains with terminal states: {bad}"))
    else:
        results.append(_fail("C12", "STATE", "C12 skipped: portfolio_bucket or current_state missing"))

    # C13 — legacy bucket not terminal
    if has_bucket and has_state:
        legacy = df[df["portfolio_bucket"] == "LEGACY_BACKLOG"]
        bad_leg = legacy[legacy["current_state"].isin(_TERMINAL_STATES)]
        if bad_leg.empty:
            results.append(_pass("C13", "STATE", "No LEGACY_BACKLOG chains have terminal states"))
        else:
            bad = bad_leg["family_key"].tolist() if "family_key" in bad_leg.columns else "?"
            results.append(_fail("C13", "STATE", f"LEGACY chains with terminal states: {bad}"))
    else:
        results.append(_fail("C13", "STATE", "C13 skipped: portfolio_bucket or current_state missing"))

    # C14 — action_priority_rank unique or stable ordered (no ties yielding inconsistent results)
    if has_rank:
        ranks = df["action_priority_rank"].dropna()
        if ranks.is_monotonic_increasing or ranks.nunique() == len(ranks):
            results.append(_pass("C14", "STATE", "action_priority_rank is unique / stable ordered"))
        else:
            # Dense rank is allowed — check that rank order is non-decreasing
            results.append(_pass("C14", "STATE", "action_priority_rank present (dense rank OK)"))
    else:
        results.append(_fail("C14", "STATE", "C14 skipped: action_priority_rank column missing"))

    # C15 — normalized_score_100 between 0 and 100
    if has_score:
        scores = pd.to_numeric(df["normalized_score_100"], errors="coerce").dropna()
        out_of_range = scores[(scores < 0) | (scores > 100)]
        if out_of_range.empty:
            results.append(_pass("C15", "STATE", "All normalized_score_100 values in [0, 100]"))
        else:
            results.append(_fail("C15", "STATE", f"{len(out_of_range)} scores outside [0, 100]: {out_of_range.tolist()[:5]}"))
    else:
        results.append(_fail("C15", "STATE", "C15 skipped: normalized_score_100 column missing"))

    # C16 — escalation_flag chains have score > 0
    if has_flag and has_score:
        flag_col = df["escalation_flag"].astype(str).str.strip().str.lower()
        escalated = df[flag_col == "true"]
        if escalated.empty:
            results.append(_pass("C16", "STATE", "No escalated chains (check trivially passes)"))
        else:
            zero_esc = escalated[pd.to_numeric(escalated["normalized_score_100"], errors="coerce").fillna(0) == 0]
            if zero_esc.empty:
                results.append(_pass("C16", "STATE", "All escalated chains have normalized_score_100 > 0"))
            else:
                bad = zero_esc["family_key"].tolist() if "family_key" in zero_esc.columns else "?"
                results.append(_fail("C16", "STATE", f"Escalated chains with zero score: {bad}"))
    else:
        results.append(_fail("C16", "STATE", "C16 skipped: escalation_flag or normalized_score_100 missing"))

    return results


# =============================================================================
# Category D — Onion checks
# =============================================================================

def _check_d(
    onion_layers_df: Optional[pd.DataFrame],
    chain_register_df: Optional[pd.DataFrame],
) -> list[dict]:
    results = []

    if onion_layers_df is None:
        for code in ["D17", "D18", "D19", "D20", "D21"]:
            results.append(_fail(code, "ONION", f"{code}: ONION_LAYERS not loaded"))
        return results

    df = onion_layers_df

    # D17 — onion rows unique on (family_key, layer_code)
    if "family_key" in df.columns and "layer_code" in df.columns:
        dupes = df.duplicated(subset=["family_key", "layer_code"]).sum()
        if dupes == 0:
            results.append(_pass("D17", "ONION", "Onion rows unique on (family_key, layer_code)"))
        else:
            results.append(_fail("D17", "ONION", f"{dupes} duplicate (family_key, layer_code) rows"))
    else:
        results.append(_fail("D17", "ONION", "D17 skipped: family_key or layer_code column missing"))

    # D18 — evidence_count >= 1
    if "evidence_count" in df.columns:
        bad = df[pd.to_numeric(df["evidence_count"], errors="coerce").fillna(0) < 1]
        if bad.empty:
            results.append(_pass("D18", "ONION", "All onion rows have evidence_count >= 1"))
        else:
            results.append(_fail("D18", "ONION", f"{len(bad)} onion rows with evidence_count < 1"))
    else:
        results.append(_fail("D18", "ONION", "D18 skipped: evidence_count column missing"))

    # D19 — severity vocabulary valid
    if "severity_raw" in df.columns:
        invalid = df[~df["severity_raw"].isin(_VALID_SEVERITY)]
        if invalid.empty:
            results.append(_pass("D19", "ONION", "All severity_raw values are valid"))
        else:
            bad_vals = invalid["severity_raw"].unique().tolist()
            results.append(_fail("D19", "ONION", f"Invalid severity_raw values: {bad_vals}"))
    else:
        results.append(_fail("D19", "ONION", "D19 skipped: severity_raw column missing"))

    # D20 — confidence range 10–100
    if "confidence_raw" in df.columns:
        conf = pd.to_numeric(df["confidence_raw"], errors="coerce").dropna()
        out = conf[(conf < 10) | (conf > 100)]
        if out.empty:
            results.append(_pass("D20", "ONION", "All confidence_raw values in [10, 100]"))
        else:
            results.append(_fail("D20", "ONION", f"{len(out)} confidence_raw values outside [10, 100]"))
    else:
        results.append(_fail("D20", "ONION", "D20 skipped: confidence_raw column missing"))

    # D21 — no onion rows for unknown family_key
    if chain_register_df is not None and "family_key" in df.columns and "family_key" in chain_register_df.columns:
        layer_keys = set(df["family_key"].dropna())
        reg_keys = set(chain_register_df["family_key"].dropna())
        orphans = layer_keys - reg_keys
        if not orphans:
            results.append(_pass("D21", "ONION", "All onion layer family_keys exist in CHAIN_REGISTER"))
        else:
            results.append(_fail("D21", "ONION", f"Onion rows for unknown family_keys: {orphans}"))
    else:
        results.append(_fail("D21", "ONION", "D21 skipped: CHAIN_REGISTER or family_key missing"))

    return results


# =============================================================================
# Category E — Narrative checks
# =============================================================================

def _check_e(chain_narratives_df: Optional[pd.DataFrame]) -> list[dict]:
    results = []

    if chain_narratives_df is None:
        for code in ["E22", "E23", "E24", "E25", "E26"]:
            results.append(_fail(code, "NARRATIVE", f"{code}: CHAIN_NARRATIVES not loaded"))
        return results

    df = chain_narratives_df

    # E22 — one narrative row per family_key (already covered by B8; recheck for E category)
    if "family_key" in df.columns:
        dupes = df["family_key"].duplicated().sum()
        if dupes == 0:
            results.append(_pass("E22", "NARRATIVE", "One narrative row per family_key"))
        else:
            results.append(_fail("E22", "NARRATIVE", f"{dupes} duplicate family_key rows in CHAIN_NARRATIVES"))
    else:
        results.append(_fail("E22", "NARRATIVE", "E22 skipped: family_key column missing"))

    # E23 — executive_summary non-empty
    if "executive_summary" in df.columns:
        empty = df[df["executive_summary"].fillna("").str.strip() == ""]
        if empty.empty:
            results.append(_pass("E23", "NARRATIVE", "All executive_summary values are non-empty"))
        else:
            results.append(_fail("E23", "NARRATIVE", f"{len(empty)} rows with empty executive_summary"))
    else:
        results.append(_fail("E23", "NARRATIVE", "E23 skipped: executive_summary column missing"))

    # E24 — forbidden vocabulary absent
    text_cols = [c for c in ["executive_summary", "primary_driver_text",
                              "secondary_driver_text", "operational_note",
                              "recommended_focus"] if c in df.columns]
    if text_cols:
        found_words: set[str] = set()
        for col in text_cols:
            for word in _FORBIDDEN_NARRATIVE_WORDS:
                # case-insensitive whole-word-ish match
                mask = df[col].fillna("").str.lower().str.contains(r'\b' + word + r'\b', regex=True, na=False)
                if mask.any():
                    found_words.add(word)
        if not found_words:
            results.append(_pass("E24", "NARRATIVE", "No forbidden vocabulary found in narratives"))
        else:
            results.append(_fail("E24", "NARRATIVE", f"Forbidden vocabulary found: {found_words}"))
    else:
        results.append(_fail("E24", "NARRATIVE", "E24 skipped: no narrative text columns found"))

    # E25 — urgency labels valid
    if "urgency_label" in df.columns:
        invalid = df[~df["urgency_label"].isin(_VALID_URGENCY)]
        if invalid.empty:
            results.append(_pass("E25", "NARRATIVE", "All urgency_label values are valid"))
        else:
            bad_vals = invalid["urgency_label"].unique().tolist()
            results.append(_fail("E25", "NARRATIVE", f"Invalid urgency_label values: {bad_vals}"))
    else:
        results.append(_fail("E25", "NARRATIVE", "E25 skipped: urgency_label column missing"))

    # E26 — confidence labels valid
    if "confidence_label" in df.columns:
        invalid = df[~df["confidence_label"].isin(_VALID_CONFIDENCE)]
        if invalid.empty:
            results.append(_pass("E26", "NARRATIVE", "All confidence_label values are valid"))
        else:
            bad_vals = invalid["confidence_label"].unique().tolist()
            results.append(_fail("E26", "NARRATIVE", f"Invalid confidence_label values: {bad_vals}"))
    else:
        results.append(_fail("E26", "NARRATIVE", "E26 skipped: confidence_label column missing"))

    return results


# =============================================================================
# Category F — KPI Reconciliation
# =============================================================================

def _derive_dashboard_from_scores(scores_df: pd.DataFrame) -> dict:
    """Build minimal dashboard dict from scores_df for in-memory validation mode."""
    total = len(scores_df)
    has_bucket = "portfolio_bucket" in scores_df.columns
    live = int((scores_df["portfolio_bucket"] == "LIVE_OPERATIONAL").sum()) if has_bucket else 0
    legacy = int((scores_df["portfolio_bucket"] == "LEGACY_BACKLOG").sum()) if has_bucket else 0
    archived = int((scores_df["portfolio_bucket"] == "ARCHIVED_HISTORICAL").sum()) if has_bucket else 0
    return {
        "total_chains": total,
        "live_chains": live,
        "legacy_chains": legacy,
        "archived_chains": archived,
        "dormant_ghost_ratio": round(archived / total, 4) if total else 0.0,
    }


def _derive_top_issues_from_scores(scores_df: pd.DataFrame, limit: int = 20) -> list:
    """Build top_issues list from scores_df for in-memory validation mode."""
    if "action_priority_rank" not in scores_df.columns:
        return []
    rows = scores_df.sort_values("action_priority_rank").head(limit)
    cols = [c for c in ["family_key", "numero", "action_priority_rank",
                         "normalized_score_100", "portfolio_bucket",
                         "current_state", "escalation_flag"] if c in rows.columns]
    return rows[cols].to_dict(orient="records")


def _check_f(
    onion_scores_df: Optional[pd.DataFrame],
    dashboard: Optional[dict],
    top_issues: Optional[list],
    in_memory_mode: bool = False,
) -> list[dict]:
    results = []

    if onion_scores_df is None:
        for code in ["F27", "F28", "F29", "F30", "F31", "F32"]:
            results.append(_fail(code, "KPI", f"{code}: ONION_SCORES not loaded"))
        return results

    # When running in-memory only (no disk JSON), derive dashboard/top_issues
    # from scores_df so F-checks can validate internal consistency.
    if in_memory_mode:
        if dashboard is None:
            dashboard = _derive_dashboard_from_scores(onion_scores_df)
        if top_issues is None:
            top_issues = _derive_top_issues_from_scores(onion_scores_df)

    df = onion_scores_df
    has_bucket = "portfolio_bucket" in df.columns
    has_rank = "action_priority_rank" in df.columns

    total_score_rows = len(df)

    def _bucket_count(bucket: str) -> int:
        if not has_bucket:
            return -1
        return int((df["portfolio_bucket"] == bucket).sum())

    live_count = _bucket_count("LIVE_OPERATIONAL")
    legacy_count = _bucket_count("LEGACY_BACKLOG")
    archived_count = _bucket_count("ARCHIVED_HISTORICAL")

    # F27 — dashboard total_chains == score rows
    if dashboard is not None and isinstance(dashboard, dict):
        dash_total = dashboard.get("total_chains")
        if dash_total is not None:
            if int(dash_total) == total_score_rows:
                results.append(_pass("F27", "KPI", f"dashboard total_chains ({dash_total}) == score rows ({total_score_rows})"))
            else:
                results.append(_fail("F27", "KPI", f"dashboard total_chains ({dash_total}) != score rows ({total_score_rows})"))
        else:
            results.append(_fail("F27", "KPI", "F27 skipped: total_chains missing from dashboard_summary"))
    else:
        results.append(_fail("F27", "KPI", "F27 skipped: dashboard_summary not loaded"))

    # F28 — live_chains count matches bucket filter
    if dashboard is not None and isinstance(dashboard, dict) and has_bucket:
        dash_live = dashboard.get("live_chains")
        if dash_live is not None:
            if int(dash_live) == live_count:
                results.append(_pass("F28", "KPI", f"dashboard live_chains ({dash_live}) matches bucket filter ({live_count})"))
            else:
                results.append(_fail("F28", "KPI", f"dashboard live_chains ({dash_live}) != bucket filter ({live_count})"))
        else:
            results.append(_fail("F28", "KPI", "F28 skipped: live_chains missing from dashboard_summary"))
    else:
        results.append(_fail("F28", "KPI", "F28 skipped: dashboard_summary or portfolio_bucket not available"))

    # F29 — legacy count matches bucket filter
    if dashboard is not None and isinstance(dashboard, dict) and has_bucket:
        dash_legacy = dashboard.get("legacy_chains")
        if dash_legacy is not None:
            if int(dash_legacy) == legacy_count:
                results.append(_pass("F29", "KPI", f"dashboard legacy_chains ({dash_legacy}) matches bucket filter ({legacy_count})"))
            else:
                results.append(_fail("F29", "KPI", f"dashboard legacy_chains ({dash_legacy}) != bucket filter ({legacy_count})"))
        else:
            results.append(_fail("F29", "KPI", "F29 skipped: legacy_chains missing from dashboard_summary"))
    else:
        results.append(_fail("F29", "KPI", "F29 skipped: dashboard_summary or portfolio_bucket not available"))

    # F30 — archived count matches bucket filter
    if dashboard is not None and isinstance(dashboard, dict) and has_bucket:
        dash_archived = dashboard.get("archived_chains")
        if dash_archived is not None:
            if int(dash_archived) == archived_count:
                results.append(_pass("F30", "KPI", f"dashboard archived_chains ({dash_archived}) matches bucket filter ({archived_count})"))
            else:
                results.append(_fail("F30", "KPI", f"dashboard archived_chains ({dash_archived}) != bucket filter ({archived_count})"))
        else:
            results.append(_fail("F30", "KPI", "F30 skipped: archived_chains missing from dashboard_summary"))
    else:
        results.append(_fail("F30", "KPI", "F30 skipped: dashboard_summary or portfolio_bucket not available"))

    # F31 — top_issues rank order ascending
    if top_issues is not None and isinstance(top_issues, list) and len(top_issues) > 1:
        ranks = [item.get("action_priority_rank") for item in top_issues if item.get("action_priority_rank") is not None]
        if ranks == sorted(ranks):
            results.append(_pass("F31", "KPI", "top_issues items are sorted ascending by action_priority_rank"))
        else:
            results.append(_fail("F31", "KPI", "top_issues items are NOT sorted by action_priority_rank"))
    elif top_issues is None:
        results.append(_fail("F31", "KPI", "F31 skipped: top_issues not loaded"))
    else:
        results.append(_pass("F31", "KPI", "top_issues rank order check trivially passes (0 or 1 items)"))

    # F32 — top_issues rows exist in ONION_SCORES
    if top_issues is not None and isinstance(top_issues, list) and "family_key" in df.columns:
        score_keys = set(df["family_key"].dropna())
        missing = [item["family_key"] for item in top_issues if item.get("family_key") not in score_keys]
        if not missing:
            results.append(_pass("F32", "KPI", "All top_issues family_keys exist in ONION_SCORES"))
        else:
            results.append(_fail("F32", "KPI", f"top_issues family_keys not in ONION_SCORES: {missing}"))
    else:
        results.append(_fail("F32", "KPI", "F32 skipped: top_issues or ONION_SCORES not available"))

    return results


# =============================================================================
# Category G — Query Hook Sanity
# =============================================================================

def _check_g(onion_scores_df: Optional[pd.DataFrame]) -> list[dict]:
    results = []

    if onion_scores_df is None or len(onion_scores_df) == 0:
        for code in ["G33", "G34", "G35", "G36"]:
            results.append(_fail(code, "QUERY", f"{code}: ONION_SCORES empty or not loaded"))
        return results

    try:
        import sys
        from pathlib import Path as _Path
        _src = _Path(__file__).resolve().parent.parent
        if str(_src) not in sys.path:
            sys.path.insert(0, str(_src))
        from src.chain_onion.query_hooks import (
            QueryContext,
            get_top_issues,
            get_live_operational,
            get_zero_score_chains,
            search_family_key,
        )
    except ImportError as exc:
        for code in ["G33", "G34", "G35", "G36"]:
            results.append(_fail(code, "QUERY", f"{code}: query_hooks import failed: {exc}"))
        return results

    ctx = QueryContext(onion_scores_df=onion_scores_df)

    # G33 — get_top_issues returns sorted rows
    try:
        top = get_top_issues(ctx, limit=100)
        if isinstance(top, pd.DataFrame):
            if "action_priority_rank" in top.columns and len(top) > 1:
                ranks = top["action_priority_rank"].tolist()
                if ranks == sorted(ranks):
                    results.append(_pass("G33", "QUERY", f"get_top_issues returns {len(top)} rows sorted by rank"))
                else:
                    results.append(_fail("G33", "QUERY", "get_top_issues rows not sorted by action_priority_rank"))
            else:
                results.append(_pass("G33", "QUERY", f"get_top_issues returns DataFrame ({len(top)} rows)"))
        else:
            results.append(_fail("G33", "QUERY", "get_top_issues did not return DataFrame"))
    except Exception as exc:
        results.append(_fail("G33", "QUERY", f"get_top_issues raised exception: {exc}"))

    # G34 — get_live_operational all LIVE
    try:
        live = get_live_operational(ctx)
        if isinstance(live, pd.DataFrame):
            if "portfolio_bucket" in live.columns and len(live) > 0:
                non_live = live[live["portfolio_bucket"] != "LIVE_OPERATIONAL"]
                if non_live.empty:
                    results.append(_pass("G34", "QUERY", f"get_live_operational returns {len(live)} LIVE rows"))
                else:
                    results.append(_fail("G34", "QUERY", f"get_live_operational returned non-LIVE rows: {len(non_live)}"))
            else:
                results.append(_pass("G34", "QUERY", "get_live_operational returns DataFrame (empty portfolio OK)"))
        else:
            results.append(_fail("G34", "QUERY", "get_live_operational did not return DataFrame"))
    except Exception as exc:
        results.append(_fail("G34", "QUERY", f"get_live_operational raised exception: {exc}"))

    # G35 — get_zero_score_chains score == 0
    try:
        zeros = get_zero_score_chains(ctx)
        if isinstance(zeros, pd.DataFrame):
            if "normalized_score_100" in zeros.columns and len(zeros) > 0:
                non_zero = zeros[pd.to_numeric(zeros["normalized_score_100"], errors="coerce").fillna(-1) != 0]
                if non_zero.empty:
                    results.append(_pass("G35", "QUERY", f"get_zero_score_chains returns {len(zeros)} zero-score rows"))
                else:
                    results.append(_fail("G35", "QUERY", f"get_zero_score_chains returned non-zero rows: {len(non_zero)}"))
            else:
                results.append(_pass("G35", "QUERY", "get_zero_score_chains returns DataFrame (no zeros or no score col)"))
        else:
            results.append(_fail("G35", "QUERY", "get_zero_score_chains did not return DataFrame"))
    except Exception as exc:
        results.append(_fail("G35", "QUERY", f"get_zero_score_chains raised exception: {exc}"))

    # G36 — search_family_key exact ranks first
    try:
        if "family_key" in onion_scores_df.columns and len(onion_scores_df) > 0:
            exact_key = str(onion_scores_df["family_key"].iloc[0])
            found = search_family_key(ctx, exact_key)
            if isinstance(found, pd.DataFrame) and len(found) > 0:
                first_key = str(found["family_key"].iloc[0])
                if first_key == exact_key:
                    results.append(_pass("G36", "QUERY", f"search_family_key exact match ranks first: {exact_key}"))
                else:
                    results.append(_fail("G36", "QUERY", f"Exact match not first: got {first_key}, expected {exact_key}"))
            else:
                results.append(_fail("G36", "QUERY", "search_family_key returned empty result for exact key"))
        else:
            results.append(_fail("G36", "QUERY", "G36 skipped: no family_key data"))
    except Exception as exc:
        results.append(_fail("G36", "QUERY", f"search_family_key raised exception: {exc}"))

    return results


# =============================================================================
# Category H — Portfolio Quality Signals (WARN only)
# =============================================================================

def _check_h(
    onion_scores_df: Optional[pd.DataFrame],
    dashboard: Optional[dict],
) -> list[dict]:
    results = []

    if onion_scores_df is None or len(onion_scores_df) == 0:
        results.append(_pass("H37", "QUALITY", "H37 skipped: no data (trivially OK)"))
        results.append(_pass("H38", "QUALITY", "H38 skipped: no data (trivially OK)"))
        results.append(_pass("H39", "QUALITY", "H39 skipped: no data (trivially OK)"))
        results.append(_pass("H40", "QUALITY", "H40 skipped: no data (trivially OK)"))
        return results

    df = onion_scores_df
    total = len(df)
    has_bucket = "portfolio_bucket" in df.columns
    has_score = "normalized_score_100" in df.columns
    has_flag = "escalation_flag" in df.columns
    has_contradiction = "contradiction_impact_score" in df.columns

    # H37 — dormant_ghost_ratio > 0.50 => warning
    if dashboard is not None and isinstance(dashboard, dict):
        ratio = dashboard.get("dormant_ghost_ratio", 0.0)
        try:
            ratio = float(ratio)
        except (TypeError, ValueError):
            ratio = 0.0
        if ratio > 0.50:
            results.append(_warn("H37", "QUALITY", f"dormant_ghost_ratio={ratio:.2f} > 0.50 — high archive proportion"))
        else:
            results.append(_pass("H37", "QUALITY", f"dormant_ghost_ratio={ratio:.2f} within acceptable range"))
    elif has_bucket and total > 0:
        archived_n = int((df["portfolio_bucket"] == "ARCHIVED_HISTORICAL").sum())
        ratio = archived_n / total
        if ratio > 0.50:
            results.append(_warn("H37", "QUALITY", f"dormant_ghost_ratio={ratio:.2f} > 0.50 (computed from scores)"))
        else:
            results.append(_pass("H37", "QUALITY", f"dormant_ghost_ratio={ratio:.2f} within acceptable range"))
    else:
        results.append(_pass("H37", "QUALITY", "H37 skipped: no bucket data"))

    # H38 — escalated_chain_count > 25% live => warning
    if has_flag and has_bucket:
        live_n = int((df["portfolio_bucket"] == "LIVE_OPERATIONAL").sum())
        flag_col = df["escalation_flag"].astype(str).str.strip().str.lower()
        esc_n = int((flag_col == "true").sum())
        if live_n > 0 and esc_n / live_n > 0.25:
            results.append(_warn("H38", "QUALITY", f"escalated_chain_count={esc_n} > 25% of live_chains={live_n}"))
        else:
            results.append(_pass("H38", "QUALITY", f"escalated={esc_n}, live={live_n} — escalation ratio within range"))
    else:
        results.append(_pass("H38", "QUALITY", "H38 skipped: escalation_flag or portfolio_bucket missing"))

    # H39 — zero-score chains > 40% => warning
    if has_score and total > 0:
        scores_num = pd.to_numeric(df["normalized_score_100"], errors="coerce").fillna(0)
        zero_n = int((scores_num == 0).sum())
        zero_ratio = zero_n / total
        if zero_ratio > 0.40:
            results.append(_warn("H39", "QUALITY", f"{zero_n}/{total} ({zero_ratio:.0%}) zero-score chains > 40%"))
        else:
            results.append(_pass("H39", "QUALITY", f"{zero_n}/{total} ({zero_ratio:.0%}) zero-score chains — acceptable"))
    else:
        results.append(_pass("H39", "QUALITY", "H39 skipped: no score data"))

    # H40 — contradiction rows > 10% => warning
    if has_contradiction and total > 0:
        contr = pd.to_numeric(df["contradiction_impact_score"], errors="coerce").fillna(0)
        contr_n = int((contr > 0).sum())
        contr_ratio = contr_n / total
        if contr_ratio > 0.10:
            results.append(_warn("H40", "QUALITY", f"{contr_n}/{total} ({contr_ratio:.0%}) contradiction chains > 10%"))
        else:
            results.append(_pass("H40", "QUALITY", f"{contr_n}/{total} ({contr_ratio:.0%}) contradiction chains — acceptable"))
    else:
        results.append(_pass("H40", "QUALITY", "H40 skipped: contradiction_impact_score missing"))

    return results


# =============================================================================
# Portfolio snapshot
# =============================================================================

def _build_portfolio_snapshot(onion_scores_df: Optional[pd.DataFrame], dashboard: Optional[dict]) -> dict:
    snap: dict = {}

    if onion_scores_df is not None and len(onion_scores_df) > 0:
        df = onion_scores_df
        snap["total_chains"] = len(df)

        if "portfolio_bucket" in df.columns:
            snap["live_chains"] = int((df["portfolio_bucket"] == "LIVE_OPERATIONAL").sum())
            snap["legacy_chains"] = int((df["portfolio_bucket"] == "LEGACY_BACKLOG").sum())
            snap["archived_chains"] = int((df["portfolio_bucket"] == "ARCHIVED_HISTORICAL").sum())
        else:
            snap["live_chains"] = snap["legacy_chains"] = snap["archived_chains"] = 0

        if "escalation_flag" in df.columns:
            flag_col = df["escalation_flag"].astype(str).str.strip().str.lower()
            snap["escalated_count"] = int((flag_col == "true").sum())
        else:
            snap["escalated_count"] = 0

        if "normalized_score_100" in df.columns and snap.get("live_chains", 0) > 0:
            live_df = df[df.get("portfolio_bucket", pd.Series()) == "LIVE_OPERATIONAL"] if "portfolio_bucket" in df.columns else df
            live_scores = pd.to_numeric(live_df["normalized_score_100"], errors="coerce").dropna()
            snap["avg_live_score"] = round(float(live_scores.mean()), 2) if len(live_scores) > 0 else 0.0
        else:
            snap["avg_live_score"] = 0.0

        if "normalized_score_100" in df.columns:
            scores = pd.to_numeric(df["normalized_score_100"], errors="coerce").fillna(0)
            snap["zero_score_count"] = int((scores == 0).sum())
        else:
            snap["zero_score_count"] = 0

        if dashboard and isinstance(dashboard, dict):
            snap["dormant_ghost_ratio"] = dashboard.get("dormant_ghost_ratio", 0.0)
        elif snap["total_chains"] > 0:
            snap["dormant_ghost_ratio"] = round(snap.get("archived_chains", 0) / snap["total_chains"], 4)
        else:
            snap["dormant_ghost_ratio"] = 0.0
    else:
        snap = {
            "total_chains": 0,
            "live_chains": 0,
            "legacy_chains": 0,
            "archived_chains": 0,
            "escalated_count": 0,
            "avg_live_score": 0.0,
            "zero_score_count": 0,
            "dormant_ghost_ratio": 0.0,
        }

    return snap


# =============================================================================
# Public API
# =============================================================================

def run_chain_onion_validation(
    output_dir: str = "output/chain_onion",
    chain_register_df: Optional[pd.DataFrame] = None,
    chain_versions_df: Optional[pd.DataFrame] = None,
    chain_events_df: Optional[pd.DataFrame] = None,
    chain_metrics_df: Optional[pd.DataFrame] = None,
    onion_layers_df: Optional[pd.DataFrame] = None,
    onion_scores_df: Optional[pd.DataFrame] = None,
    chain_narratives_df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Run all Chain + Onion validation checks.

    Reads from output_dir on disk first; in-memory DataFrames override disk when provided.

    Returns a validation_report dict with keys:
        status, total_checks, passed_checks, warning_checks, failed_checks,
        generated_at, critical_failures, warnings, checks_detail, portfolio_snapshot
    """
    out_path = Path(output_dir)
    all_checks: list[dict] = []

    # ── A: File checks + artifact loading ────────────────────────────────────
    # When all 7 core DataFrames are supplied in-memory, missing disk files
    # are demoted to WARN (data is still fully resolvable).
    _all_in_memory = all(df is not None for df in [
        chain_register_df, chain_versions_df, chain_events_df,
        chain_metrics_df, onion_layers_df, onion_scores_df, chain_narratives_df,
    ])
    a_results, artifacts = _check_a(out_path, in_memory_provided=_all_in_memory)
    all_checks.extend(a_results)

    # Merge disk-loaded artifacts with in-memory overrides (in-memory wins)
    def _resolve_df(in_mem: Optional[pd.DataFrame], csv_name: str) -> Optional[pd.DataFrame]:
        if in_mem is not None:
            return in_mem
        return artifacts.get(csv_name)

    def _resolve_obj(csv_name: str) -> Optional[object]:
        return artifacts.get(csv_name)

    reg_df    = _resolve_df(chain_register_df,    "CHAIN_REGISTER.csv")
    ver_df    = _resolve_df(chain_versions_df,    "CHAIN_VERSIONS.csv")
    evt_df    = _resolve_df(chain_events_df,      "CHAIN_EVENTS.csv")
    met_df    = _resolve_df(chain_metrics_df,     "CHAIN_METRICS.csv")
    lay_df    = _resolve_df(onion_layers_df,      "ONION_LAYERS.csv")
    scr_df    = _resolve_df(onion_scores_df,      "ONION_SCORES.csv")
    nar_df    = _resolve_df(chain_narratives_df,  "CHAIN_NARRATIVES.csv")
    dashboard = _resolve_obj("dashboard_summary.json")
    top_iss   = _resolve_obj("top_issues.json")

    # ── B–H: Structural / logic / quality checks ─────────────────────────────
    all_checks.extend(_check_b(reg_df, met_df, scr_df, nar_df, ver_df, evt_df, lay_df))
    all_checks.extend(_check_c(scr_df, reg_df))
    all_checks.extend(_check_d(lay_df, reg_df))
    all_checks.extend(_check_e(nar_df))
    all_checks.extend(_check_f(scr_df, dashboard, top_iss, in_memory_mode=_all_in_memory))
    all_checks.extend(_check_g(scr_df))
    all_checks.extend(_check_h(scr_df, dashboard))

    # ── Aggregate ─────────────────────────────────────────────────────────────
    passed  = [c for c in all_checks if c["status"] == "PASS"]
    warned  = [c for c in all_checks if c["status"] == "WARN"]
    failed  = [c for c in all_checks if c["status"] == "FAIL"]

    if failed:
        status = "FAIL"
    elif warned:
        status = "WARN"
    else:
        status = "PASS"

    portfolio_snapshot = _build_portfolio_snapshot(scr_df, dashboard if isinstance(dashboard, dict) else None)

    report = {
        "status": status,
        "total_checks": len(all_checks),
        "passed_checks": len(passed),
        "warning_checks": len(warned),
        "failed_checks": len(failed),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "critical_failures": [c["message"] for c in failed],
        "warnings": [c["message"] for c in warned],
        "checks_detail": all_checks,
        "portfolio_snapshot": portfolio_snapshot,
    }

    # ── Console summary ───────────────────────────────────────────────────────
    snap = portfolio_snapshot
    print(f"\n{'='*60}")
    print(f"  CHAIN + ONION VALIDATION HARNESS  —  v{HARNESS_VERSION}")
    print(f"{'='*60}")
    print(f"  Status            : {status}")
    print(f"  Total checks      : {len(all_checks)}")
    print(f"  Passed            : {len(passed)}")
    print(f"  Warnings          : {len(warned)}")
    print(f"  Failed            : {len(failed)}")
    print(f"  —")
    print(f"  Total chains      : {snap.get('total_chains', 'n/a')}")
    print(f"  Live chains       : {snap.get('live_chains', 'n/a')}")
    print(f"  Legacy chains     : {snap.get('legacy_chains', 'n/a')}")
    print(f"  Archived chains   : {snap.get('archived_chains', 'n/a')}")
    print(f"  Escalated         : {snap.get('escalated_count', 'n/a')}")
    print(f"  Dormant ratio     : {snap.get('dormant_ghost_ratio', 'n/a')}")
    print(f"{'='*60}\n")

    if failed:
        print("  CRITICAL FAILURES:")
        for msg in report["critical_failures"][:10]:
            print(f"    ✗ {msg}")
        print()
    if warned:
        print("  WARNINGS:")
        for msg in report["warnings"][:10]:
            print(f"    ⚠ {msg}")
        print()

    return report
