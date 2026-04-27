"""
src/chain_onion/exporter.py
-----------------------------
Step 12 — Chain + Onion Export Engine.

Converts all Chain + Onion pipeline outputs into reusable export artifacts:
  - 7 deterministic CSVs
  - 1 multi-sheet XLSX workbook
  - 2 JSON dashboard files

Public API
----------
export_chain_onion_outputs(
    chain_register_df,
    chain_versions_df,
    chain_events_df,
    chain_metrics_df,
    onion_layers_df,
    onion_scores_df,
    chain_narratives_df,
    portfolio_metrics,
    onion_portfolio_summary,
    output_dir="output/chain_onion",
) -> dict[str, str]   # artifact_name -> absolute file path

Rules
-----
- Never mutates inputs.
- Creates output_dir if missing.
- Stable deterministic sort on all exports.
- Empty DataFrames export with headers only.
- Dates serialised safely (isoformat strings).
- No UI code. No invented data.
"""
from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

_LOG = logging.getLogger(__name__)

ENGINE_VERSION = "1.0.0"

# ── Sort keys per CSV ──────────────────────────────────────────────────────────

_SORT: dict[str, list[str]] = {
    "CHAIN_REGISTER": ["family_key"],
    "CHAIN_VERSIONS": ["family_key", "version_number"],
    "CHAIN_EVENTS": ["family_key", "event_date", "event_type"],
    "CHAIN_METRICS": ["family_key"],
    "ONION_LAYERS": ["family_key", "layer_code"],
    "ONION_SCORES": ["action_priority_rank", "family_key"],
    "CHAIN_NARRATIVES": ["action_priority_rank", "family_key"],
}

# ── XLSX sheet definitions ─────────────────────────────────────────────────────

_SHEET_ORDER = [
    "Executive Priorities",
    "Live Operational Chains",
    "Consultant Delays",
    "Contractor Quality",
    "MOEX-SAS Blocking",
    "Legacy Backlog Cleanup",
    "Archived Historical",
    "Portfolio KPIs",
    "Full Chain Metrics",
    "Full Onion Scores",
    "Narratives",
]


# ── Public entry point ─────────────────────────────────────────────────────────

def export_chain_onion_outputs(
    chain_register_df: pd.DataFrame,
    chain_versions_df: pd.DataFrame,
    chain_events_df: pd.DataFrame,
    chain_metrics_df: pd.DataFrame,
    onion_layers_df: pd.DataFrame,
    onion_scores_df: pd.DataFrame,
    chain_narratives_df: pd.DataFrame,
    portfolio_metrics: dict,
    onion_portfolio_summary: dict,
    output_dir: str = "output/chain_onion",
) -> dict[str, str]:
    """Export all Chain + Onion artifacts. Returns dict of artifact_name -> path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Work on copies so inputs are never mutated.
    reg = _safe_copy(chain_register_df)
    ver = _safe_copy(chain_versions_df)
    evn = _safe_copy(chain_events_df)
    mtr = _safe_copy(chain_metrics_df)
    lay = _safe_copy(onion_layers_df)
    scr = _safe_copy(onion_scores_df)
    nar = _safe_copy(chain_narratives_df)

    artifacts: dict[str, str] = {}

    # ── CSVs ──────────────────────────────────────────────────────────────────
    artifacts.update(_export_csvs(reg, ver, evn, mtr, lay, scr, nar, out))

    # ── JSON ──────────────────────────────────────────────────────────────────
    artifacts.update(_export_json(scr, nar, portfolio_metrics, onion_portfolio_summary, out))

    # ── XLSX ──────────────────────────────────────────────────────────────────
    artifacts.update(_export_xlsx(reg, ver, evn, mtr, lay, scr, nar, portfolio_metrics, onion_portfolio_summary, out))

    _LOG.info("Step 12 export complete — %d artifacts written to %s", len(artifacts), out)
    return artifacts


# ── CSV exports ───────────────────────────────────────────────────────────────

def _export_csvs(reg, ver, evn, mtr, lay, scr, nar, out: Path) -> dict[str, str]:
    pairs = [
        ("CHAIN_REGISTER", reg),
        ("CHAIN_VERSIONS", ver),
        ("CHAIN_EVENTS", evn),
        ("CHAIN_METRICS", mtr),
        ("ONION_LAYERS", lay),
        ("ONION_SCORES", scr),
        ("CHAIN_NARRATIVES", nar),
    ]
    results = {}
    for name, df in pairs:
        df_sorted = _sort_df(df, _SORT.get(name, []))
        df_safe = _safe_dates(df_sorted)
        path = out / f"{name}.csv"
        df_safe.to_csv(path, index=False)
        results[name + ".csv"] = str(path)
        _LOG.debug("  CSV %s — %d rows", name, len(df_safe))
    return results


# ── JSON exports ──────────────────────────────────────────────────────────────

def _export_json(scr, nar, portfolio_metrics, onion_portfolio_summary, out: Path) -> dict[str, str]:
    results = {}

    # dashboard_summary.json
    summary = _build_dashboard_summary(scr, nar, portfolio_metrics, onion_portfolio_summary)
    dash_path = out / "dashboard_summary.json"
    _write_json(summary, dash_path)
    results["dashboard_summary.json"] = str(dash_path)

    # top_issues.json
    top_issues = _build_top_issues(nar, scr)
    issues_path = out / "top_issues.json"
    _write_json(top_issues, issues_path)
    results["top_issues.json"] = str(issues_path)

    return results


def _build_dashboard_summary(scr, nar, portfolio_metrics: dict, onion_portfolio_summary: dict) -> dict:
    total_chains = int(len(scr)) if not scr.empty else 0

    def _bucket_count(df, bucket):
        if df.empty or "portfolio_bucket" not in df.columns:
            return 0
        return int((df["portfolio_bucket"] == bucket).sum())

    live_chains = _bucket_count(scr, "LIVE_OPERATIONAL")
    legacy_chains = _bucket_count(scr, "LEGACY_BACKLOG")
    archived_chains = _bucket_count(scr, "ARCHIVED_HISTORICAL")

    # dormant ghost ratio: archived / total
    dormant_ghost_ratio = round(archived_chains / total_chains, 4) if total_chains > 0 else 0.0

    # avg pressure for live chains
    avg_pressure_live = 0.0
    if not scr.empty and "normalized_score_100" in scr.columns and live_chains > 0:
        live_mask = scr["portfolio_bucket"] == "LIVE_OPERATIONAL"
        avg_pressure_live = round(float(scr.loc[live_mask, "normalized_score_100"].mean()), 2)

    # escalated chain count
    escalated_chain_count = 0
    if not scr.empty and "escalation_flag" in scr.columns:
        escalated_chain_count = int(scr["escalation_flag"].sum())

    # top theme by total impact (from onion_portfolio_summary if present, else derive)
    top_theme = _derive_top_theme(scr, onion_portfolio_summary)

    return {
        "total_chains": total_chains,
        "live_chains": live_chains,
        "legacy_chains": legacy_chains,
        "archived_chains": archived_chains,
        "dormant_ghost_ratio": dormant_ghost_ratio,
        "avg_pressure_live": avg_pressure_live,
        "escalated_chain_count": escalated_chain_count,
        "top_theme_by_impact": top_theme,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": ENGINE_VERSION,
    }


def _derive_top_theme(scr: pd.DataFrame, onion_portfolio_summary: dict) -> str:
    # Prefer pre-computed value from portfolio summary
    if isinstance(onion_portfolio_summary, dict):
        for key in ("top_theme_by_impact", "top_theme", "top_layer_by_total"):
            if key in onion_portfolio_summary and onion_portfolio_summary[key]:
                return str(onion_portfolio_summary[key])

    # Derive from impact columns if present
    theme_cols = {
        "L1_CONTRACTOR_QUALITY": "contractor_impact_score",
        "L2_SAS_GATE_FRICTION": "sas_impact_score",
        "L3_PRIMARY_CONSULTANT_DELAY": "consultant_primary_impact_score",
        "L4_SECONDARY_CONSULTANT_DELAY": "consultant_secondary_impact_score",
        "L5_MOEX_ARBITRATION_DELAY": "moex_impact_score",
        "L6_DATA_REPORT_CONTRADICTION": "contradiction_impact_score",
    }
    if not scr.empty:
        totals = {}
        for layer, col in theme_cols.items():
            if col in scr.columns:
                totals[layer] = float(scr[col].sum())
        if totals:
            return max(totals, key=totals.__getitem__)

    return "UNKNOWN"


def _build_top_issues(nar: pd.DataFrame, scr: pd.DataFrame) -> list[dict]:
    if nar.empty:
        return []

    base = nar.copy()
    if "action_priority_rank" in base.columns:
        base = base.sort_values(["action_priority_rank", "family_key"]).head(20)
    else:
        base = base.head(20)

    # Enrich with escalation_flag if not already in narratives
    if "escalation_flag" not in base.columns and not scr.empty and "escalation_flag" in scr.columns:
        base = base.merge(
            scr[["family_key", "escalation_flag"]].drop_duplicates("family_key"),
            on="family_key",
            how="left",
        )

    records = []
    for _, row in base.iterrows():
        rec: dict[str, Any] = {
            "family_key": _safe_val(row.get("family_key")),
            "numero": _safe_val(row.get("numero")),
            "action_priority_rank": _safe_val(row.get("action_priority_rank")),
            "normalized_score_100": _safe_val(row.get("normalized_score_100")),
            "urgency_label": _safe_val(row.get("urgency_label")),
            "portfolio_bucket": _safe_val(row.get("portfolio_bucket")),
            "current_state": _safe_val(row.get("current_state")),
            "executive_summary": _safe_val(row.get("executive_summary")),
            "primary_driver_text": _safe_val(row.get("primary_driver_text")),
            "recommended_focus": _safe_val(row.get("recommended_focus")),
            "escalation_flag": bool(row.get("escalation_flag", False)),
        }
        records.append(rec)
    return records


# ── XLSX export ───────────────────────────────────────────────────────────────

def _export_xlsx(reg, ver, evn, mtr, lay, scr, nar, portfolio_metrics, onion_portfolio_summary, out: Path) -> dict[str, str]:
    path = out / "CHAIN_ONION_SUMMARY.xlsx"

    sheets = _build_xlsx_sheets(reg, ver, evn, mtr, lay, scr, nar, portfolio_metrics, onion_portfolio_summary)

    with pd.ExcelWriter(str(path), engine="openpyxl") as writer:
        for sheet_name in _SHEET_ORDER:
            df = sheets.get(sheet_name, pd.DataFrame())
            df_safe = _safe_dates(df)
            df_safe.to_excel(writer, sheet_name=sheet_name, index=False)
            _LOG.debug("  XLSX sheet '%s' — %d rows", sheet_name, len(df_safe))

    return {"CHAIN_ONION_SUMMARY.xlsx": str(path)}


def _build_xlsx_sheets(reg, ver, evn, mtr, lay, scr, nar, portfolio_metrics, onion_portfolio_summary) -> dict[str, pd.DataFrame]:
    sheets: dict[str, pd.DataFrame] = {}

    # 1. Executive Priorities — top 50 by action_priority_rank from narratives
    exec_cols = _select_cols(nar, ["numero", "current_state", "normalized_score_100", "urgency_label",
                                   "executive_summary", "recommended_focus", "action_priority_rank",
                                   "portfolio_bucket", "family_key"])
    exec_df = _sort_df(nar[exec_cols], ["action_priority_rank", "family_key"]).head(50)
    sheets["Executive Priorities"] = exec_df.reset_index(drop=True)

    # 2. Live Operational Chains
    sheets["Live Operational Chains"] = _bucket_filter(scr, "LIVE_OPERATIONAL")

    # 3. Consultant Delays — primary or secondary consultant impact > 0
    sheets["Consultant Delays"] = _consultant_filter(scr)

    # 4. Contractor Quality — contractor_impact_score > 0
    sheets["Contractor Quality"] = _col_gt_zero(scr, "contractor_impact_score")

    # 5. MOEX-SAS Blocking — moex_impact_score > 0 OR sas_impact_score > 0
    sheets["MOEX-SAS Blocking"] = _moex_sas_filter(scr)

    # 6. Legacy Backlog Cleanup
    sheets["Legacy Backlog Cleanup"] = _bucket_filter(scr, "LEGACY_BACKLOG")

    # 7. Archived Historical
    sheets["Archived Historical"] = _bucket_filter(scr, "ARCHIVED_HISTORICAL")

    # 8. Portfolio KPIs — key/value table
    sheets["Portfolio KPIs"] = _build_kpi_sheet(portfolio_metrics, onion_portfolio_summary)

    # 9. Full Chain Metrics
    sheets["Full Chain Metrics"] = _sort_df(mtr, ["family_key"]).reset_index(drop=True)

    # 10. Full Onion Scores
    sheets["Full Onion Scores"] = _sort_df(scr, ["action_priority_rank", "family_key"]).reset_index(drop=True)

    # 11. Narratives
    sheets["Narratives"] = _sort_df(nar, ["action_priority_rank", "family_key"]).reset_index(drop=True)

    return sheets


# ── Sheet helper filters ───────────────────────────────────────────────────────

def _bucket_filter(df: pd.DataFrame, bucket: str) -> pd.DataFrame:
    if df.empty or "portfolio_bucket" not in df.columns:
        return df.iloc[0:0].copy()
    mask = df["portfolio_bucket"] == bucket
    return _sort_df(df[mask].copy(), ["action_priority_rank", "family_key"]).reset_index(drop=True)


def _consultant_filter(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.iloc[0:0].copy()
    primary_col = "consultant_primary_impact_score"
    secondary_col = "consultant_secondary_impact_score"
    mask = pd.Series([False] * len(df), index=df.index)
    if primary_col in df.columns:
        mask = mask | (df[primary_col].fillna(0) > 0)
    if secondary_col in df.columns:
        mask = mask | (df[secondary_col].fillna(0) > 0)
    return _sort_df(df[mask].copy(), ["action_priority_rank", "family_key"]).reset_index(drop=True)


def _col_gt_zero(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return df.iloc[0:0].copy()
    mask = df[col].fillna(0) > 0
    return _sort_df(df[mask].copy(), ["action_priority_rank", "family_key"]).reset_index(drop=True)


def _moex_sas_filter(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.iloc[0:0].copy()
    mask = pd.Series([False] * len(df), index=df.index)
    if "moex_impact_score" in df.columns:
        mask = mask | (df["moex_impact_score"].fillna(0) > 0)
    if "sas_impact_score" in df.columns:
        mask = mask | (df["sas_impact_score"].fillna(0) > 0)
    return _sort_df(df[mask].copy(), ["action_priority_rank", "family_key"]).reset_index(drop=True)


def _build_kpi_sheet(portfolio_metrics: dict, onion_portfolio_summary: dict) -> pd.DataFrame:
    rows = []
    for src_name, src in [("portfolio_metrics", portfolio_metrics), ("onion_portfolio_summary", onion_portfolio_summary)]:
        if not isinstance(src, dict):
            continue
        for k, v in src.items():
            rows.append({"source": src_name, "key": str(k), "value": _safe_val(v)})
    if not rows:
        return pd.DataFrame(columns=["source", "key", "value"])
    return pd.DataFrame(rows).sort_values(["source", "key"]).reset_index(drop=True)


# ── Utility helpers ────────────────────────────────────────────────────────────

def _safe_copy(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    return df.copy()


def _sort_df(df: pd.DataFrame, sort_cols: list[str]) -> pd.DataFrame:
    if df.empty or not sort_cols:
        return df
    valid = [c for c in sort_cols if c in df.columns]
    if not valid:
        return df
    return df.sort_values(valid, na_position="last").reset_index(drop=True)


def _safe_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert datetime columns to ISO-format strings so CSV/XLSX never breaks."""
    if df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)
        elif out[col].dtype == object:
            # Detect mixed date objects row by row (safe, not expensive for typical sizes)
            pass
    return out


def _select_cols(df: pd.DataFrame, preferred: list[str]) -> list[str]:
    """Return subset of preferred cols that exist in df; always includes all df cols as fallback."""
    if df.empty:
        return list(df.columns)
    available = [c for c in preferred if c in df.columns]
    # Add any remaining columns not in preferred list
    extra = [c for c in df.columns if c not in available]
    return available + extra


def _safe_val(v: Any) -> Any:
    """Convert pandas NA / numpy scalar to plain Python type for JSON."""
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, bool):
        return v
    try:
        import numpy as np  # optional dependency present since pandas depends on it
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return None if pd.isna(v) else float(v)
        if isinstance(v, (np.bool_,)):
            return bool(v)
    except ImportError:
        pass
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return v


def _write_json(obj: Any, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, default=str)
