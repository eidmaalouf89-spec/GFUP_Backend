"""
scripts/audit_counts_lineage.py
Phase 1 — Count Lineage Audit (PHASE_8_COUNT_LINEAGE_FIX.md §5)

Compares count categories across pipeline layers L0..L6 and identifies
the first layer where each category unexpectedly diverges.

Output:
  output/debug/counts_lineage_audit.xlsx  (sheets: lineage, expected_baselines, divergences_unexpected)
  output/debug/counts_lineage_audit.json

Stdout:
  AUDIT: PASS=<n> WARN=<n> FAIL=<n>; first_unexpected_divergence=<category>@<layer>

Usage:
  python scripts/audit_counts_lineage.py [--run <number>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Path setup (must happen before any src/ imports) ─────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = BASE_DIR / "src"
for _p in (BASE_DIR, _SRC_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    stream=sys.stderr,
)
_LOG = logging.getLogger(__name__)

# ── Layer definitions ─────────────────────────────────────────────────────────
LAYERS = [
    "L0_RAW_GED",
    "L1_FLAT_GED_XLSX",
    "L2_STAGE_READ_FLAT",
    "L3_RUNCONTEXT_CACHE",
    "L4_AGGREGATOR",
    "L5_UI_ADAPTER",
    "L6_CHAIN_ONION",
]

# ── Baseline provenance (Phase 2) ────────────────────────────────────────────
BASELINE_PROVENANCE = {
    # raw_submission_rows baseline refreshed 2026-04-30
    # observed in input/GED_export.xlsx
    #   mtime = 2026-04-22
    #   sheet = "Doc. sous workflow, x versions"
    #   data rows = 6901
    #   Excel rows = 3..6903
    "raw_submission_rows": (
        "observed in input/GED_export.xlsx | "
        "sheet: Doc. sous workflow, x versions | "
        "mtime: 2026-04-22 | data rows: 6901 | Excel rows: 3..6903 | "
        "refreshed: 2026-04-30"
    ),
}

# ── Expected baselines (§4) ───────────────────────────────────────────────────
EXPECTED_BASELINES = {
    # raw_submission_rows baseline refreshed 2026-04-30
    # observed in input/GED_export.xlsx
    #   mtime = 2026-04-22
    #   sheet = "Doc. sous workflow, x versions"
    #   data rows = 6901
    #   Excel rows = 3..6903
    "raw_submission_rows":          6901,
    "raw_unique_numero":            2819,
    "raw_unique_numero_indice":     4848,
    "ged_raw_flat_rows":            27261,
    "ged_operations_rows":          32099,
    "open_doc_rows":                4848,
    "sas_rows":                     4848,
    "consultant_rows":              18911,
    "moex_rows":                    3492,
    "stage_read_flat_docs_df_rows": 4834,
}

# ── Expected divergence rules (§5.4 — DATA, not silent ifs) ──────────────────
# Each rule describes a (category, from_layer, to_layer) transition where a
# difference is either expected or definitively unexpected.  The audit engine
# iterates this list; nothing about expected/unexpected divergences lives in
# conditionals elsewhere in this file.
EXPECTED_DIVERGENCES: list[dict] = [
    {
        "name":                   "raw_to_ged_raw_flat_different_concepts",
        "categories":             ["submission_instance_count", "workflow_step_count"],
        "from_layer":             "L0_RAW_GED",
        "to_layer":               "L1_FLAT_GED_XLSX",
        "is_difference_expected": True,
        "explanation": (
            "DIFFERENT CONCEPTS. GED_RAW_FLAT is one-row-per-(doc, approver, step), "
            "not one-per-submission. L0=6155 raw rows vs L1 GED_RAW_FLAT=27261 step rows."
        ),
    },
    {
        "name":                   "raw_numero_indice_vs_open_doc_equal",
        "categories":             ["active_version_count"],
        "from_layer":             "L0_RAW_GED",
        "to_layer":               "L1_FLAT_GED_XLSX",
        "is_difference_expected": True,
        "explanation": (
            "EQUAL expected. L0 raw_unique_numero_indice=4848 should equal "
            "L1 OPEN_DOC step_type count=4848."
        ),
    },
    {
        "name":                   "open_doc_vs_docs_df_sas_filter",
        "categories":             [
            "active_version_count", "numero_indice_count", "open_doc_row_count",
            "workflow_step_count", "sas_row_count",
        ],
        "from_layer":             "L1_FLAT_GED_XLSX",
        "to_layer":               "L2_STAGE_READ_FLAT",
        "is_difference_expected": True,
        "explanation": (
            "SAS pre-2026 filter (src/pipeline/stages/stage_read_flat.py:"
            "_apply_sas_filter_flat) excludes 14 document versions. "
            "active_version_count / open_doc_row_count: L1 OPEN_DOC=4848 → L2 docs_df=4834 (Δ −14). "
            "workflow_step_count: L1 GED_RAW_FLAT=27261 → L2 responses_df=27237 (Δ −24, "
            "each filtered doc carries multiple step rows). "
            "sas_row_count: L1 GED_OPERATIONS SAS rows=4848 → L2 approver_raw=='0-SAS'=4834 (Δ −14)."
        ),
    },
    {
        "name":                   "family_count_close_to_raw",
        "categories":             ["family_count"],
        "from_layer":             "L0_RAW_GED",
        "to_layer":               "L1_FLAT_GED_XLSX",
        "is_difference_expected": True,
        "explanation": (
            "EQUAL expected at L1. The SAS filter may reduce family_count slightly "
            "at L2 if any families had ONLY SAS-filtered docs. L0=2819 vs L1 unique numero."
        ),
    },
    {
        "name":                   "family_count_sas_filter_at_l2",
        "categories":             ["family_count"],
        "from_layer":             "L1_FLAT_GED_XLSX",
        "to_layer":               "L2_STAGE_READ_FLAT",
        "is_difference_expected": True,
        "explanation": (
            "Small reduction expected (modulo SAS-only filtered families). "
            "L2 family_count may be slightly below L1."
        ),
    },
    {
        "name":                   "chain_onion_no_sas_filter",
        "categories":             ["active_version_count", "family_count", "numero_indice_count"],
        "from_layer":             "L5_UI_ADAPTER",
        "to_layer":               "L6_CHAIN_ONION",
        "is_difference_expected": True,
        "explanation": (
            "Chain+Onion source_loader reads GED_OPERATIONS directly (no SAS filter). "
            "Its version/family counts reflect the full 4848 dataset, not the filtered 4834."
        ),
    },
    {
        "name":                   "chain_onion_no_sas_filter_from_l4",
        "categories":             ["active_version_count", "family_count"],
        "from_layer":             "L4_AGGREGATOR",
        "to_layer":               "L6_CHAIN_ONION",
        "is_difference_expected": True,
        "explanation": (
            "Chain+Onion reads GED_OPERATIONS without the pipeline SAS pre-2026 filter."
        ),
    },
    {
        "name":                   "sas_row_count_different_concepts_l3_l4",
        "categories":             ["sas_row_count"],
        "from_layer":             "L3_RUNCONTEXT_CACHE",
        "to_layer":               "L4_AGGREGATOR",
        "is_difference_expected": True,
        "explanation": (
            "DIFFERENT CONCEPTS. L3 sas_row_count = total SAS step rows in responses_df. "
            "L4 docs_pending_sas = docs with a pending SAS response. Different cardinality."
        ),
    },
    {
        "name":                   "consultant_row_count_different_concepts_l3_l4",
        "categories":             ["consultant_row_count"],
        "from_layer":             "L3_RUNCONTEXT_CACHE",
        "to_layer":               "L4_AGGREGATOR",
        "is_difference_expected": True,
        "explanation": (
            "DIFFERENT CONCEPTS. L3 = total CONSULTANT step rows. "
            "L4 total_consultants = count of unique consultant names."
        ),
    },
    {
        "name":                   "status_ref_combined_in_ui",
        "categories":             ["status_REF"],
        "from_layer":             "L4_AGGREGATOR",
        "to_layer":               "L5_UI_ADAPTER",
        "is_difference_expected": True,
        "explanation": (
            "adapt_overview combines REF + SAS_REF into visa_flow['ref']. "
            "L4 reports REF and SAS_REF separately; L5 cannot be split."
        ),
    },
]

# ── UI Payload field map (Phase 8 Step 6) ─────────────────────────────────────
# Each entry maps one aggregator KPI path to its ui_adapter equivalent.
# Paths use a 'kpis.' or 'overview.' prefix resolved against the dicts passed
# to _compare_ui_payload.  Entries with comparison_kind='skipped' or
# ui_adapter_path=None are recorded but not compared.
UI_PAYLOAD_FIELD_MAP: list[dict] = [
    # ── total_docs_current ───────────────────────────────────────────────────
    {
        "aggregator_path": "kpis.total_docs_current",
        "ui_adapter_path": "overview.total_docs",
        "comparison_kind": "numeric_equal",
        "notes": "",
    },
    {
        "aggregator_path": "kpis.total_docs_current",
        "ui_adapter_path": "overview.visa_flow.submitted",
        "comparison_kind": "numeric_equal",
        "notes": "visa_flow.submitted mirrors total_docs_current",
    },
    # ── total_docs_all_indices ───────────────────────────────────────────────
    {
        "aggregator_path": "kpis.total_docs_all_indices",
        "ui_adapter_path": None,
        "comparison_kind": "skipped",
        "notes": "total_docs_all_indices not surfaced in adapt_overview",
    },
    # ── contractor / consultant / lot counts ─────────────────────────────────
    {
        "aggregator_path": "kpis.total_contractors",
        "ui_adapter_path": "overview.project_stats.total_contractors",
        "comparison_kind": "numeric_equal",
        "notes": "",
    },
    {
        "aggregator_path": "kpis.total_consultants",
        "ui_adapter_path": "overview.project_stats.total_consultants",
        "comparison_kind": "numeric_equal",
        "notes": "",
    },
    {
        "aggregator_path": "kpis.total_lots",
        "ui_adapter_path": None,
        "comparison_kind": "skipped",
        "notes": "total_lots not surfaced in adapt_overview",
    },
    # ── discrepancies_count ───────────────────────────────────────────────────
    {
        "aggregator_path": "kpis.discrepancies_count",
        "ui_adapter_path": None,
        "comparison_kind": "skipped",
        "notes": "discrepancies_count not surfaced in adapt_overview",
    },
    # ── avg_days_to_visa ──────────────────────────────────────────────────────
    {
        "aggregator_path": "kpis.avg_days_to_visa",
        "ui_adapter_path": "overview.project_stats.avg_days_to_visa",
        "comparison_kind": "identity",
        "notes": "float or None; passed through as-is by adapt_overview",
    },
    # ── docs_pending_sas / docs_sas_ref_active ────────────────────────────────
    {
        "aggregator_path": "kpis.docs_pending_sas",
        "ui_adapter_path": "overview.project_stats.docs_pending_sas",
        "comparison_kind": "numeric_equal",
        "notes": "",
    },
    {
        "aggregator_path": "kpis.docs_sas_ref_active",
        "ui_adapter_path": None,
        "comparison_kind": "skipped",
        "notes": "docs_sas_ref_active not surfaced in adapt_overview",
    },
    # ── by_visa_global individual statuses ────────────────────────────────────
    {
        "aggregator_path": "kpis.by_visa_global.VSO",
        "ui_adapter_path": "overview.visa_flow.vso",
        "comparison_kind": "numeric_equal",
        "notes": "",
    },
    {
        "aggregator_path": "kpis.by_visa_global.VAO",
        "ui_adapter_path": "overview.visa_flow.vao",
        "comparison_kind": "numeric_equal",
        "notes": "",
    },
    {
        "aggregator_path": "kpis.by_visa_global.HM",
        "ui_adapter_path": "overview.visa_flow.hm",
        "comparison_kind": "numeric_equal",
        "notes": "",
    },
    {
        "aggregator_path": "kpis.by_visa_global.Open",
        "ui_adapter_path": "overview.visa_flow.pending",
        "comparison_kind": "numeric_equal",
        "notes": "open_count maps to visa_flow.pending in adapt_overview",
    },
    {
        "aggregator_path": "kpis.by_visa_global.REF",
        "ui_adapter_path": None,
        "comparison_kind": "skipped",
        "notes": "adapt_overview merges REF+SAS_REF into visa_flow.ref; individual REF not comparable",
    },
    {
        "aggregator_path": "kpis.by_visa_global.SAS REF",
        "ui_adapter_path": None,
        "comparison_kind": "skipped",
        "notes": "adapt_overview merges REF+SAS_REF into visa_flow.ref; individual SAS_REF not comparable",
    },
    # ── by_visa_global_pct ────────────────────────────────────────────────────
    {
        "aggregator_path": "kpis.by_visa_global_pct",
        "ui_adapter_path": None,
        "comparison_kind": "skipped",
        "notes": "pct dict not surfaced in adapt_overview",
    },
    # ── by_building / by_responsible ──────────────────────────────────────────
    {
        "aggregator_path": "kpis.by_building",
        "ui_adapter_path": None,
        "comparison_kind": "skipped",
        "notes": "by_building not surfaced in adapt_overview",
    },
    {
        "aggregator_path": "kpis.by_responsible",
        "ui_adapter_path": None,
        "comparison_kind": "skipped",
        "notes": "by_responsible not surfaced in adapt_overview",
    },
    # ── focus block ───────────────────────────────────────────────────────────
    {
        "aggregator_path": "kpis.focus_stats",
        "ui_adapter_path": "overview.focus",
        "comparison_kind": "skipped",
        "notes": "focus fields only present when focus_result is active; not comparable in unfocused audit run",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_expected_divergence(category: str, from_layer: str, to_layer: str) -> tuple[bool, str]:
    """Return (is_expected, explanation) for a category/layer-pair divergence.

    Walks EXPECTED_DIVERGENCES — the single authoritative data source.
    Default (no matching rule): unexpected.
    """
    for rule in EXPECTED_DIVERGENCES:
        cats = rule["categories"]
        if cats == ["ALL"] or category in cats:
            if rule["from_layer"] == from_layer and rule["to_layer"] == to_layer:
                return rule["is_difference_expected"], rule["explanation"]
    return False, ""


# ─────────────────────────────────────────────────────────────────────────────
# Layer collectors
# ─────────────────────────────────────────────────────────────────────────────

def collect_l0(base_dir: Path) -> dict:
    """Load raw GED export and compute L0 counts."""
    input_dir = base_dir / "input"
    candidates = [
        p for p in input_dir.glob("*.xlsx")
        if "GED" in p.name.upper()
        and "FLAT" not in p.name.upper()
        and "Grandfichier" not in p.name
        and "Mapping" not in p.name
    ]
    if not candidates:
        return {"_error": f"No GED export xlsx found in {input_dir}"}

    ged_path = max(candidates, key=lambda p: p.stat().st_mtime)
    _LOG.info("L0: GED file = %s", ged_path.name)

    try:
        xl = pd.ExcelFile(str(ged_path))
        workflow_sheet = next(
            (sn for sn in xl.sheet_names if "workflow" in sn.lower()), None
        )
        if workflow_sheet is None:
            return {
                "_error": (
                    f"No sheet containing 'workflow' found in {ged_path.name}. "
                    f"Available sheets: {xl.sheet_names}"
                )
            }

        # read_raw.py: 2-row merged header; data starts at row index 2
        raw = pd.read_excel(str(ged_path), sheet_name=workflow_sheet,
                             header=None, dtype=str)
        header_row = raw.iloc[0].tolist()

        # Locate NUMERO and INDICE column indices (BASE_FIELDS in read_raw.py)
        numero_idx, indice_idx = None, None
        for i, val in enumerate(header_row):
            v = str(val).strip().upper() if val is not None else ""
            if v == "NUMERO":
                numero_idx = i
            elif v == "INDICE":
                indice_idx = i

        data = raw.iloc[2:].dropna(how="all").reset_index(drop=True)
        result: dict = {
            "path": str(ged_path),
            "sheet": workflow_sheet,
            "raw_submission_rows": len(data),
        }

        if numero_idx is not None:
            nums = (data.iloc[:, numero_idx]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .pipe(lambda s: s[s != ""]))
            result["raw_unique_numero"] = int(nums.nunique())
            if indice_idx is not None:
                pairs = data[[numero_idx, indice_idx]].copy()
                pairs.columns = ["numero", "indice"]
                pairs = pairs.dropna(subset=["numero"])
                pairs["numero"] = pairs["numero"].astype(str).str.strip()
                pairs["indice"] = pairs["indice"].astype(str).str.strip()
                result["raw_unique_numero_indice"] = int(pairs.drop_duplicates().shape[0])
            else:
                result["raw_unique_numero_indice"] = None
                result["_warn"] = "INDICE column not found in header"
        else:
            result["raw_unique_numero"] = None
            result["raw_unique_numero_indice"] = None
            result["_warn"] = f"NUMERO column not found. Header (first 20): {header_row[:20]}"

        # L0 SAS REF: count rows where "Réponse" under any 0-SAS block == "REF"
        try:
            header_row_1 = raw.iloc[1].tolist()
            # Forward-fill row 0 to propagate section names over merged cells
            section_ffill: list = []
            current_sec = None
            for val in header_row:
                s = str(val).strip() if val is not None and str(val) not in ("nan", "None", "") else None
                if s:
                    current_sec = s
                section_ffill.append(current_sec)
            # Find column indices where section == "0-SAS" and sub-header == "Réponse"
            sas_reponse_cols = [
                i for i, (sec, sub) in enumerate(zip(section_ffill, header_row_1))
                if sec == "0-SAS" and str(sub).strip() == "Réponse"
            ]
            if sas_reponse_cols:
                sas_cols_data = data.iloc[:, sas_reponse_cols]
                sas_ref_mask = (sas_cols_data == "REF").any(axis=1)
                result["status_SAS_REF"] = int(sas_ref_mask.sum())
                result["_sas_reponse_col_count"] = len(sas_reponse_cols)
            else:
                unique_secs = list(dict.fromkeys(s for s in section_ffill if s))
                result["_warn_sas_ref"] = (
                    f"No '0-SAS' section with 'Réponse' sub-header found. "
                    f"Unique sections (first 10): {unique_secs[:10]}"
                )
        except Exception as sas_exc:
            result["_warn_sas_ref"] = f"L0 SAS REF reader failed: {sas_exc}"

        return result

    except Exception as exc:
        return {"_error": f"Failed to load L0: {exc}", "path": str(ged_path)}


def collect_l1(base_dir: Path) -> dict:
    """Load FLAT_GED.xlsx and compute L1 counts."""
    flat_path = base_dir / "output" / "intermediate" / "FLAT_GED.xlsx"
    if not flat_path.exists():
        return {"_error": f"FLAT_GED.xlsx not found at {flat_path}"}

    _LOG.info("L1: FLAT_GED.xlsx = %s", flat_path)
    try:
        raw_df = pd.read_excel(str(flat_path), sheet_name="GED_RAW_FLAT", dtype=str)
        ops_df = pd.read_excel(str(flat_path), sheet_name="GED_OPERATIONS", dtype=str)

        result: dict = {
            "path": str(flat_path),
            "sha256": _sha256(flat_path),
            "mtime": datetime.fromtimestamp(
                flat_path.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
            "ged_raw_flat_rows": int(len(raw_df)),
            "ged_operations_rows": int(len(ops_df)),
        }

        if "step_type" in ops_df.columns:
            sc = ops_df["step_type"].value_counts()
            result["open_doc_rows"]   = int(sc.get("OPEN_DOC",   0))
            result["sas_rows"]        = int(sc.get("SAS",        0))
            result["consultant_rows"] = int(sc.get("CONSULTANT", 0))
            result["moex_rows"]       = int(sc.get("MOEX",       0))
            result["step_type_counts"] = {k: int(v) for k, v in sc.items()}

            open_ops = ops_df[ops_df["step_type"] == "OPEN_DOC"]
            result["active_version_count"] = int(len(open_ops))
            result["open_doc_row_count"]   = int(len(open_ops))
            if "numero" in ops_df.columns and "indice" in ops_df.columns:
                result["family_count_l1"] = int(
                    open_ops["numero"].astype(str).str.strip().nunique()
                )
                result["numero_indice_count_l1"] = int(
                    open_ops[["numero", "indice"]].drop_duplicates().shape[0]
                )
        else:
            result["_warn"] = "step_type column absent from GED_OPERATIONS"

        # L1 SAS REF: GED_RAW_FLAT rows where is_sas==True AND status_clean=="REF"
        # GED_RAW_FLAT uses "response_status_clean"; ctx.responses_df uses "status_clean"
        _status_col = next(
            (c for c in ("status_clean", "response_status_clean") if c in raw_df.columns),
            None,
        )
        if "is_sas" in raw_df.columns and _status_col is not None:
            is_sas_mask = raw_df["is_sas"].astype(str).str.strip().str.lower() == "true"
            ref_mask = raw_df[_status_col].astype(str).str.strip() == "REF"
            result["status_SAS_REF"] = int((is_sas_mask & ref_mask).sum())
            result["_sas_ref_col_used"] = _status_col
        else:
            missing_cols = (
                ([] if "is_sas" in raw_df.columns else ["is_sas"])
                + ([] if _status_col else ["status_clean / response_status_clean"])
            )
            result["_warn_sas_ref"] = (
                f"Cannot compute status_SAS_REF at L1: missing columns {missing_cols}. "
                f"Available (first 20): {list(raw_df.columns)[:20]}"
            )

        # Visa distribution from MOEX step rows
        if "step_type" in ops_df.columns and "status_clean" in ops_df.columns:
            moex_ops = ops_df[ops_df["step_type"] == "MOEX"]
            result["visa_global_from_moex_steps"] = {
                k: int(v) for k, v in moex_ops["status_clean"].value_counts().items()
            }

        return result

    except Exception as exc:
        return {"_error": f"Failed to load L1: {exc}"}


def collect_l2_l3(base_dir: Path, run_number: int = 0) -> tuple[dict, Any]:
    """Load RunContext and compute L2/L3 counts. Returns (counts_dict, ctx)."""
    from reporting.data_loader import load_run_context

    _LOG.info("L2/L3: load_run_context(run_number=%d) ...", run_number)
    ctx = load_run_context(base_dir, run_number=run_number)

    if ctx is None:
        return {"_error": "load_run_context returned None"}, None
    if ctx.degraded_mode:
        return {
            "_error": (
                f"RunContext is in degraded mode. run_number={run_number}. "
                f"Warnings: {ctx.warnings}"
            )
        }, ctx
    if ctx.docs_df is None:
        return {"_error": "ctx.docs_df is None after load"}, ctx

    docs_df = ctx.docs_df
    resp_df  = ctx.responses_df
    we       = ctx.workflow_engine

    result: dict = {
        "run_number": ctx.run_number,
        "run_status": ctx.run_status,
        "run_date":   ctx.run_date,
        "degraded_mode": ctx.degraded_mode,
        "warnings": ctx.warnings,
        "docs_df_rows":        int(len(docs_df)),
        "active_version_count": int(len(docs_df)),
    }

    if "numero" in docs_df.columns:
        result["family_count"] = int(
            docs_df["numero"].astype(str).str.strip().nunique()
        )
    if "numero" in docs_df.columns and "indice" in docs_df.columns:
        result["numero_indice_count"] = int(
            docs_df[["numero", "indice"]].drop_duplicates().shape[0]
        )

    if resp_df is not None:
        result["responses_df_rows"] = int(len(resp_df))
        result["response_row_count"] = int(len(resp_df))

        if "approver_raw" in resp_df.columns:
            result["sas_row_count"] = int(
                (resp_df["approver_raw"] == "0-SAS").sum()
            )

        # status_SAS_REF: response-level count from ctx.responses_df (H-3: NOT workflow_engine.responses_df)
        # filter: is_sas == True AND status_clean == "REF"
        if "status_clean" in resp_df.columns:
            if "is_sas" in resp_df.columns:
                _sas_mask = resp_df["is_sas"].astype(str).str.strip().str.lower().isin(["true", "1"])
            elif "approver_raw" in resp_df.columns:
                _sas_mask = resp_df["approver_raw"].astype(str).str.strip() == "0-SAS"
            else:
                _sas_mask = None
            if _sas_mask is not None:
                result["status_SAS_REF"] = int(
                    (_sas_mask & (resp_df["status_clean"].astype(str).str.strip() == "REF")).sum()
                )

        # Use flat_step_type if present (stage_read_flat pass-through column)
        if "flat_step_type" in resp_df.columns:
            st = resp_df["flat_step_type"].value_counts()
            result["consultant_row_count"] = int(st.get("CONSULTANT", 0))
            result["moex_row_count"]       = int(st.get("MOEX",       0))
            result["step_type_in_responses"] = {k: int(v) for k, v in st.items()}
        else:
            result["_warn_step_type"] = (
                "flat_step_type not in responses_df; "
                "consultant_row_count / moex_row_count cannot be computed from L3"
            )

    # Visa global distribution — from workflow_engine (what aggregator uses at L4)
    if we is not None and ctx.dernier_df is not None:
        visa_wf: dict[str, int] = defaultdict(int)
        for _, row in ctx.dernier_df.iterrows():
            visa, _ = we.compute_visa_global_with_date(row["doc_id"])
            visa_wf[visa or "Open"] += 1
        result["visa_distribution_workflow_engine"] = dict(visa_wf)
        result["status_VSO"]     = int(visa_wf.get("VSO",     0))
        result["status_VAO"]     = int(visa_wf.get("VAO",     0))
        result["status_REF"]     = int(visa_wf.get("REF",     0))
        # status_SAS_REF is now computed from resp_df filter above (H-3 fix)
        result["status_HM"]      = int(visa_wf.get("HM",      0))
        result["open_count"]     = int(visa_wf.get("Open",    0))
        result["closed_count"]   = len(ctx.dernier_df) - result["open_count"]

    # Visa global from flat_doc_meta in cache_meta.json (authoritative per
    # stage_read_flat; NOT attached to RunContext — Phase 3 gap).
    cache_meta_path = base_dir / "output" / "intermediate" / "FLAT_GED_cache_meta.json"
    if cache_meta_path.exists():
        try:
            with open(str(cache_meta_path), encoding="utf-8") as fh:
                cache_meta = json.load(fh)
            fdm = cache_meta.get("flat_doc_meta") or {}
            if fdm:
                visa_fdm: dict[str, int] = defaultdict(int)
                for _doc_id, meta in fdm.items():
                    v = meta.get("visa_global") or "Open"
                    visa_fdm[v] += 1
                result["visa_distribution_flat_doc_meta"] = dict(visa_fdm)
                result["cache_schema_version"] = cache_meta.get("cache_schema_version")
                result["flat_doc_meta_count"]  = len(fdm)
        except Exception as exc:
            result["_warn_cache_meta"] = f"flat_doc_meta from cache: {exc}"

    return result, ctx


def collect_l4(ctx) -> dict:
    """Run aggregator.compute_project_kpis and extract counts."""
    from reporting.aggregator import compute_project_kpis

    _LOG.info("L4: compute_project_kpis ...")
    kpis = compute_project_kpis(ctx)
    visa = kpis.get("by_visa_global", {})

    # status_SAS_REF at L4: compute from ctx.responses_df (same filter as L1/L2)
    # aggregator's by_visa_global["SAS REF"] is typically 0 due to Phase 3 gap
    resp_l4 = getattr(ctx, "responses_df", None)
    sas_ref_l4 = None
    if resp_l4 is not None and "status_clean" in resp_l4.columns:
        if "is_sas" in resp_l4.columns:
            _m = resp_l4["is_sas"].astype(str).str.strip().str.lower().isin(["true", "1"])
        elif "approver_raw" in resp_l4.columns:
            _m = resp_l4["approver_raw"].astype(str).str.strip() == "0-SAS"
        else:
            _m = None
        if _m is not None:
            sas_ref_l4 = int((_m & (resp_l4["status_clean"].astype(str).str.strip() == "REF")).sum())

    return {
        "kpis_raw":             kpis,
        "active_version_count": kpis.get("total_docs_current"),
        "status_VSO":           int(visa.get("VSO",     0)),
        "status_VAO":           int(visa.get("VAO",     0)),
        "status_REF":           int(visa.get("REF",     0)),
        "status_SAS_REF":       sas_ref_l4,
        "status_HM":            int(visa.get("HM",      0)),
        "open_count":           int(visa.get("Open",    0)),
        "docs_pending_sas":     kpis.get("docs_pending_sas"),
        "total_consultants":    kpis.get("total_consultants"),
        "total_contractors":    kpis.get("total_contractors"),
        "avg_days_to_visa":     kpis.get("avg_days_to_visa"),
    }


def collect_l5(ctx) -> dict:
    """Assemble dashboard_data, call ui_adapter.adapt_overview, extract counts."""
    from reporting.aggregator import (
        compute_project_kpis,
        compute_monthly_timeseries,
        compute_consultant_summary,
        compute_contractor_summary,
    )
    from reporting.ui_adapter import adapt_overview

    _LOG.info("L5: adapt_overview ...")
    kpis        = compute_project_kpis(ctx)
    monthly     = compute_monthly_timeseries(ctx)
    consultants = compute_consultant_summary(ctx)
    contractors = compute_contractor_summary(ctx)

    dashboard_data = {
        "kpis":               kpis,
        "monthly":            monthly,
        "consultants":        consultants,
        "contractors":        contractors,
        "focus":              {},
        "priority_queue":     [],
        "legacy_backlog_count": 0,
    }
    overview = adapt_overview(dashboard_data, {})
    vf = overview.get("visa_flow", {})

    return {
        "adapt_overview_entry":     "adapt_overview",
        "adapt_overview_signature": "adapt_overview(dashboard_data: dict, app_state: dict) -> dict",
        "total_docs":               overview.get("total_docs"),
        "active_version_count":     overview.get("total_docs"),
        # NOTE: adapt_overview combines REF + SAS_REF into visa_flow["ref"]
        "status_VSO":               vf.get("vso"),
        "status_VAO":               vf.get("vao"),
        "status_REF_combined":      vf.get("ref"),   # REF + SAS_REF — cannot split
        "status_REF":               None,            # not separately available in L5
        "status_HM":                vf.get("hm"),
        "open_count":               vf.get("pending"),
        "answered_count":           vf.get("answered"),
        "total_consultants":        overview.get("project_stats", {}).get("total_consultants"),
        "total_contractors":        overview.get("project_stats", {}).get("total_contractors"),
        "overview_raw":             overview,
    }


def collect_l6(base_dir: Path) -> dict:
    """Read Chain+Onion outputs and compute L6 counts."""
    co_dir = base_dir / "output" / "chain_onion"
    result: dict = {"path": str(co_dir)}

    if not co_dir.exists():
        result["_error"] = f"output/chain_onion/ not found at {co_dir}"
        return result

    # CHAIN_REGISTER.csv — portfolio bucket counts + family_count
    reg_path = co_dir / "CHAIN_REGISTER.csv"
    if reg_path.exists():
        try:
            reg = pd.read_csv(str(reg_path), dtype=str)
            result["chain_register_rows"] = int(len(reg))
            if "family_key" in reg.columns:
                result["family_count"] = int(reg["family_key"].nunique())
            if "portfolio_bucket" in reg.columns:
                bc = reg["portfolio_bucket"].value_counts()
                result["portfolio_buckets"]          = {k: int(v) for k, v in bc.items()}
                result["live_operational_count"]     = int(bc.get("LIVE_OPERATIONAL",  0))
                result["legacy_backlog_count"]       = int(bc.get("LEGACY_BACKLOG",    0))
                result["archived_historical_count"]  = int(bc.get("ARCHIVED_HISTORICAL", 0))
        except Exception as exc:
            result["_warn_chain_register"] = f"CHAIN_REGISTER.csv: {exc}"
    else:
        result["_warn_chain_register"] = "CHAIN_REGISTER.csv not found"

    # CHAIN_VERSIONS.csv — active_version_count (numero_indice pairs)
    ver_path = co_dir / "CHAIN_VERSIONS.csv"
    if ver_path.exists():
        try:
            ver = pd.read_csv(str(ver_path), dtype=str)
            result["chain_versions_rows"] = int(len(ver))
            if "version_key" in ver.columns:
                result["active_version_count"] = int(ver["version_key"].nunique())
        except Exception as exc:
            result["_warn_chain_versions"] = f"CHAIN_VERSIONS.csv: {exc}"
    else:
        result["_warn_chain_versions"] = "CHAIN_VERSIONS.csv not found"

    # dashboard_summary.json — portfolio KPIs
    dash_path = co_dir / "dashboard_summary.json"
    if dash_path.exists():
        try:
            with open(str(dash_path), encoding="utf-8") as fh:
                dash = json.load(fh)
            result["dashboard_summary"]        = dash
            result["live_from_summary"]        = dash.get("live_chains")
            result["legacy_from_summary"]      = dash.get("legacy_chains")
            result["total_chains_from_summary"] = dash.get("total_chains")
        except Exception as exc:
            result["_warn_dashboard"] = f"dashboard_summary.json: {exc}"

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Baseline assertions
# ─────────────────────────────────────────────────────────────────────────────

def check_baselines(l0: dict, l1: dict, l2: dict) -> list[dict]:
    """Assert each baseline from §4. Returns list of check results."""
    checks: list[dict] = []

    def _chk(key: str, expected: int, observed: Any, tolerance: int = 2) -> None:
        if observed is None:
            status, note = "WARN", "not_computed"
        else:
            delta = int(observed) - expected
            if abs(delta) <= tolerance:
                status, note = "PASS", ""
            else:
                status, note = "FAIL", f"delta={delta:+d}"
        checks.append({
            "baseline_key": key,
            "expected":     expected,
            "observed":     observed,
            "status":       status,
            "note":         note,
        })

    _chk("raw_submission_rows",          EXPECTED_BASELINES["raw_submission_rows"],          l0.get("raw_submission_rows"))
    _chk("raw_unique_numero",            EXPECTED_BASELINES["raw_unique_numero"],            l0.get("raw_unique_numero"))
    _chk("raw_unique_numero_indice",     EXPECTED_BASELINES["raw_unique_numero_indice"],     l0.get("raw_unique_numero_indice"))
    _chk("ged_raw_flat_rows",            EXPECTED_BASELINES["ged_raw_flat_rows"],            l1.get("ged_raw_flat_rows"))
    _chk("ged_operations_rows",          EXPECTED_BASELINES["ged_operations_rows"],          l1.get("ged_operations_rows"))
    _chk("open_doc_rows",                EXPECTED_BASELINES["open_doc_rows"],                l1.get("open_doc_rows"))
    _chk("sas_rows",                     EXPECTED_BASELINES["sas_rows"],                     l1.get("sas_rows"))
    _chk("consultant_rows",              EXPECTED_BASELINES["consultant_rows"],              l1.get("consultant_rows"))
    _chk("moex_rows",                    EXPECTED_BASELINES["moex_rows"],                    l1.get("moex_rows"))
    _chk("stage_read_flat_docs_df_rows", EXPECTED_BASELINES["stage_read_flat_docs_df_rows"], l2.get("docs_df_rows"))
    return checks


# ─────────────────────────────────────────────────────────────────────────────
# Category table
# ─────────────────────────────────────────────────────────────────────────────

def build_category_table(
    l0: dict, l1: dict, l2: dict, l4: dict, l5: dict, l6: dict
) -> list[dict]:
    """Return list of {name, values: {layer: value}, source}."""
    # L2 and L3 come from the same collect_l2_l3() call.  Row counts are
    # identical (docs_df unchanged); visa distribution may differ only via
    # report_memory enrichment.  Both are reported from l2 dict.
    return [
        {
            "name": "submission_instance_count",
            "values": {
                "L0_RAW_GED":          l0.get("raw_submission_rows"),
                "L1_FLAT_GED_XLSX":    None,   # different concept: step rows, not submissions
                "L2_STAGE_READ_FLAT":  None,
                "L3_RUNCONTEXT_CACHE": None,
                "L4_AGGREGATOR":       None,
                "L5_UI_ADAPTER":       None,
                "L6_CHAIN_ONION":      None,
            },
            "source": {
                "file": "input/GED_export.xlsx",
                "sheet": "Doc. sous workflow, x versions",
                "note": "one row per submission instance in raw GED export",
            },
        },
        {
            "name": "active_version_count",
            "values": {
                "L0_RAW_GED":          l0.get("raw_unique_numero_indice"),
                "L1_FLAT_GED_XLSX":    l1.get("open_doc_rows"),
                "L2_STAGE_READ_FLAT":  l2.get("docs_df_rows"),
                "L3_RUNCONTEXT_CACHE": l2.get("active_version_count"),
                "L4_AGGREGATOR":       l4.get("active_version_count"),
                "L5_UI_ADAPTER":       l5.get("active_version_count"),
                "L6_CHAIN_ONION":      l6.get("active_version_count"),
            },
            "source": {
                "file": "output/intermediate/FLAT_GED.xlsx",
                "sheet": "GED_OPERATIONS",
                "column": "step_type == OPEN_DOC",
            },
        },
        {
            "name": "family_count",
            "values": {
                "L0_RAW_GED":          l0.get("raw_unique_numero"),
                "L1_FLAT_GED_XLSX":    l1.get("family_count_l1"),
                "L2_STAGE_READ_FLAT":  l2.get("family_count"),
                "L3_RUNCONTEXT_CACHE": l2.get("family_count"),
                "L4_AGGREGATOR":       None,   # aggregator exposes no family_count KPI
                "L5_UI_ADAPTER":       None,
                "L6_CHAIN_ONION":      l6.get("family_count"),
            },
            "source": {
                "file": "output/intermediate/FLAT_GED.xlsx",
                "sheet": "GED_OPERATIONS",
                "column": "numero (unique)",
            },
        },
        {
            "name": "numero_indice_count",
            "values": {
                "L0_RAW_GED":          l0.get("raw_unique_numero_indice"),
                "L1_FLAT_GED_XLSX":    l1.get("numero_indice_count_l1"),
                "L2_STAGE_READ_FLAT":  l2.get("numero_indice_count"),
                "L3_RUNCONTEXT_CACHE": l2.get("numero_indice_count"),
                "L4_AGGREGATOR":       None,
                "L5_UI_ADAPTER":       None,
                "L6_CHAIN_ONION":      None,
            },
            "source": {
                "file": "output/intermediate/FLAT_GED.xlsx",
                "sheet": "GED_OPERATIONS",
                "column": "(numero, indice) pairs",
            },
        },
        {
            "name": "workflow_step_count",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    l1.get("ged_raw_flat_rows"),
                "L2_STAGE_READ_FLAT":  l2.get("response_row_count"),
                "L3_RUNCONTEXT_CACHE": l2.get("responses_df_rows"),
                "L4_AGGREGATOR":       None,
                "L5_UI_ADAPTER":       None,
                "L6_CHAIN_ONION":      None,
            },
            "source": {
                "file": "output/intermediate/FLAT_GED.xlsx",
                "sheet": "GED_RAW_FLAT",
                "note": "all step rows including OPEN_DOC",
            },
        },
        {
            "name": "sas_row_count",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    l1.get("sas_rows"),
                "L2_STAGE_READ_FLAT":  l2.get("sas_row_count"),
                "L3_RUNCONTEXT_CACHE": l2.get("sas_row_count"),
                # L4: different concept — docs_pending_sas, not total SAS rows
                "L4_AGGREGATOR":       l4.get("docs_pending_sas"),
                "L5_UI_ADAPTER":       None,
                "L6_CHAIN_ONION":      None,
            },
            "source": {
                "file": "output/intermediate/FLAT_GED.xlsx",
                "sheet": "GED_OPERATIONS",
                "column": "step_type == SAS",
                "note": "L4 value is docs_pending_sas (different concept)",
            },
        },
        {
            "name": "consultant_row_count",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    l1.get("consultant_rows"),
                "L2_STAGE_READ_FLAT":  l2.get("consultant_row_count"),
                "L3_RUNCONTEXT_CACHE": l2.get("consultant_row_count"),
                # L4: total_consultants = unique consultant names, not row count
                "L4_AGGREGATOR":       l4.get("total_consultants"),
                "L5_UI_ADAPTER":       l5.get("total_consultants"),
                "L6_CHAIN_ONION":      None,
            },
            "source": {
                "file": "output/intermediate/FLAT_GED.xlsx",
                "sheet": "GED_OPERATIONS",
                "column": "step_type == CONSULTANT",
                "note": "L4/L5 values are unique consultant count (different concept)",
            },
        },
        {
            "name": "moex_row_count",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    l1.get("moex_rows"),
                "L2_STAGE_READ_FLAT":  l2.get("moex_row_count"),
                "L3_RUNCONTEXT_CACHE": l2.get("moex_row_count"),
                "L4_AGGREGATOR":       None,
                "L5_UI_ADAPTER":       None,
                "L6_CHAIN_ONION":      None,
            },
            "source": {
                "file": "output/intermediate/FLAT_GED.xlsx",
                "sheet": "GED_OPERATIONS",
                "column": "step_type == MOEX",
            },
        },
        {
            "name": "open_doc_row_count",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    l1.get("open_doc_rows"),
                "L2_STAGE_READ_FLAT":  l2.get("docs_df_rows"),
                "L3_RUNCONTEXT_CACHE": l2.get("active_version_count"),
                "L4_AGGREGATOR":       None,
                "L5_UI_ADAPTER":       None,
                "L6_CHAIN_ONION":      None,
            },
            "source": {
                "file": "output/intermediate/FLAT_GED.xlsx",
                "sheet": "GED_OPERATIONS",
                "column": "step_type == OPEN_DOC",
            },
        },
        {
            "name": "open_count",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    None,
                "L2_STAGE_READ_FLAT":  l2.get("open_count"),
                "L3_RUNCONTEXT_CACHE": l2.get("open_count"),
                "L4_AGGREGATOR":       l4.get("open_count"),
                "L5_UI_ADAPTER":       l5.get("open_count"),
                "L6_CHAIN_ONION":      None,
            },
            "source": {
                "file": "src/reporting/aggregator.py",
                "function": "compute_project_kpis",
                "note": "docs with visa_global == None (Open)",
            },
        },
        {
            "name": "status_VSO",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    None,
                "L2_STAGE_READ_FLAT":  l2.get("status_VSO"),
                "L3_RUNCONTEXT_CACHE": l2.get("status_VSO"),
                "L4_AGGREGATOR":       l4.get("status_VSO"),
                "L5_UI_ADAPTER":       l5.get("status_VSO"),
                "L6_CHAIN_ONION":      None,
            },
            "source": {"file": "src/reporting/aggregator.py", "function": "compute_project_kpis"},
        },
        {
            "name": "status_VAO",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    None,
                "L2_STAGE_READ_FLAT":  l2.get("status_VAO"),
                "L3_RUNCONTEXT_CACHE": l2.get("status_VAO"),
                "L4_AGGREGATOR":       l4.get("status_VAO"),
                "L5_UI_ADAPTER":       l5.get("status_VAO"),
                "L6_CHAIN_ONION":      None,
            },
            "source": {"file": "src/reporting/aggregator.py", "function": "compute_project_kpis"},
        },
        {
            "name": "status_REF",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    None,
                "L2_STAGE_READ_FLAT":  l2.get("status_REF"),
                "L3_RUNCONTEXT_CACHE": l2.get("status_REF"),
                "L4_AGGREGATOR":       l4.get("status_REF"),
                # L5 combines REF + SAS_REF — cannot isolate REF alone
                "L5_UI_ADAPTER":       None,
                "L6_CHAIN_ONION":      None,
            },
            "source": {
                "file": "src/reporting/aggregator.py",
                "function": "compute_project_kpis",
                "note": "L5 combines REF+SAS_REF; set None here (see status_REF_combined)",
            },
        },
        {
            "name": "status_SAS_REF",
            "values": {
                "L0_RAW_GED":          l0.get("status_SAS_REF"),
                "L1_FLAT_GED_XLSX":    l1.get("status_SAS_REF"),
                "L2_STAGE_READ_FLAT":  l2.get("status_SAS_REF"),
                "L3_RUNCONTEXT_CACHE": l2.get("status_SAS_REF"),
                "L4_AGGREGATOR":       l4.get("status_SAS_REF"),
                "L5_UI_ADAPTER":       None,   # merged into "ref" in adapt_overview
                "L6_CHAIN_ONION":      None,
            },
            "source": {"file": "src/reporting/aggregator.py", "function": "compute_project_kpis"},
        },
        {
            "name": "status_HM",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    None,
                "L2_STAGE_READ_FLAT":  l2.get("status_HM"),
                "L3_RUNCONTEXT_CACHE": l2.get("status_HM"),
                "L4_AGGREGATOR":       l4.get("status_HM"),
                "L5_UI_ADAPTER":       l5.get("status_HM"),
                "L6_CHAIN_ONION":      None,
            },
            "source": {"file": "src/reporting/aggregator.py", "function": "compute_project_kpis"},
        },
        {
            "name": "live_operational_count",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    None,
                "L2_STAGE_READ_FLAT":  None,
                "L3_RUNCONTEXT_CACHE": None,
                "L4_AGGREGATOR":       None,
                "L5_UI_ADAPTER":       None,
                "L6_CHAIN_ONION":      l6.get("live_operational_count"),
            },
            "source": {
                "file": "output/chain_onion/CHAIN_REGISTER.csv",
                "column": "portfolio_bucket == LIVE_OPERATIONAL",
            },
        },
        {
            "name": "legacy_backlog_count",
            "values": {
                "L0_RAW_GED":          None,
                "L1_FLAT_GED_XLSX":    None,
                "L2_STAGE_READ_FLAT":  None,
                "L3_RUNCONTEXT_CACHE": None,
                "L4_AGGREGATOR":       None,
                "L5_UI_ADAPTER":       None,   # not surfaced in adapt_overview payload
                "L6_CHAIN_ONION":      l6.get("legacy_backlog_count"),
            },
            "source": {
                "file": "output/chain_onion/CHAIN_REGISTER.csv",
                "column": "portfolio_bucket == LEGACY_BACKLOG",
            },
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Audit engine
# ─────────────────────────────────────────────────────────────────────────────

def compute_audit(categories_raw: list[dict]) -> list[dict]:
    """Annotate each category with first_divergence_layer, status."""
    result: list[dict] = []

    for cat in categories_raw:
        name   = cat["name"]
        values = cat["values"]

        # Non-None layer/value pairs in canonical order
        non_null = [(l, values[l]) for l in LAYERS if values.get(l) is not None]

        first_div_layer:       Optional[str] = None
        first_div_expected:    bool          = True
        first_div_explanation: str           = ""

        for i in range(len(non_null) - 1):
            from_layer, from_val = non_null[i]
            to_layer,   to_val   = non_null[i + 1]
            if from_val != to_val:
                is_exp, expl = _is_expected_divergence(name, from_layer, to_layer)
                if not is_exp:
                    first_div_layer       = to_layer
                    first_div_expected    = False
                    first_div_explanation = expl
                    break  # report only the first unexpected one

        status = "FAIL" if (first_div_layer and not first_div_expected) else "PASS"

        result.append({
            "name":                    name,
            "values":                  values,
            "first_divergence_layer":  first_div_layer,
            "is_difference_expected":  first_div_expected,
            "explanation":             first_div_explanation,
            "source":                  cat.get("source", {}),
            "status":                  status,
        })

    return result


# ─────────────────────────────────────────────────────────────────────────────
# UI Payload comparison (Phase 8 Step 6)
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_dotted_path(root: dict, path: str):
    """Resolve a dotted key path (e.g. 'visa_flow.vso') against a nested dict."""
    cur: Any = root
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(f"{part!r} not accessible on {type(cur).__name__}")
    return cur


def _compare_ui_payload(
    ctx,
    focus_result,
    kpis: dict,
    overview: dict,
) -> dict:
    """Compare aggregator KPI fields against ui_adapter output field-by-field.

    Iterates UI_PAYLOAD_FIELD_MAP.  For each non-skipped entry, resolves both
    paths, applies any value_transform, and compares by comparison_kind.
    Returns {"matches": [...], "mismatches": [...], "skipped": [...]}.
    """
    matches: list[dict] = []
    mismatches: list[dict] = []
    skipped: list[dict] = []

    def _roots(path: str):
        if path.startswith("kpis."):
            return kpis, path[5:]
        if path.startswith("overview."):
            return overview, path[9:]
        raise ValueError(f"Unknown root prefix in path {path!r}")

    for entry in UI_PAYLOAD_FIELD_MAP:
        agg_path = entry["aggregator_path"]
        ui_path  = entry.get("ui_adapter_path")
        kind     = entry["comparison_kind"]
        notes    = entry.get("notes", "")
        transform = entry.get("value_transform")

        if kind == "skipped" or ui_path is None:
            skipped.append({
                "aggregator_path": agg_path,
                "ui_adapter_path": ui_path,
                "comparison_kind": kind,
                "notes": notes,
                "reason": notes or "skipped by map",
            })
            continue

        # Resolve aggregator value
        try:
            agg_root, agg_key = _roots(agg_path)
            agg_val = _resolve_dotted_path(agg_root, agg_key)
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            skipped.append({
                "aggregator_path": agg_path,
                "ui_adapter_path": ui_path,
                "comparison_kind": kind,
                "notes": notes,
                "reason": f"resolution_error: {type(exc).__name__}: {exc}",
            })
            continue

        # Resolve ui_adapter value
        try:
            ui_root, ui_key = _roots(ui_path)
            ui_val = _resolve_dotted_path(ui_root, ui_key)
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            skipped.append({
                "aggregator_path": agg_path,
                "ui_adapter_path": ui_path,
                "comparison_kind": kind,
                "notes": notes,
                "reason": f"resolution_error: {type(exc).__name__}: {exc}",
            })
            continue

        # Apply value_transform (key renames on dicts)
        if transform and isinstance(transform, dict):
            if isinstance(agg_val, dict):
                agg_val = {transform.get(k, k): v for k, v in agg_val.items()}
            if isinstance(ui_val, dict):
                ui_val = {transform.get(k, k): v for k, v in ui_val.items()}

        # Compare
        try:
            if kind == "numeric_equal":
                a_int = int(agg_val) if agg_val is not None else 0
                b_int = int(ui_val)  if ui_val  is not None else 0
                ok = (a_int == b_int)
            elif kind == "identity":
                ok = (agg_val is ui_val) or (agg_val == ui_val)
            elif kind == "set_equal":
                a_set = set(agg_val) if isinstance(agg_val, (list, tuple, set)) else {agg_val}
                b_set = set(ui_val)  if isinstance(ui_val,  (list, tuple, set)) else {ui_val}
                ok = (a_set == b_set)
            elif kind == "dict_equal":
                ok = (agg_val == ui_val)
            else:
                skipped.append({
                    "aggregator_path": agg_path,
                    "ui_adapter_path": ui_path,
                    "aggregator_value": agg_val,
                    "ui_adapter_value": ui_val,
                    "comparison_kind": kind,
                    "notes": notes,
                    "reason": f"unknown comparison_kind: {kind!r}",
                })
                continue
        except (TypeError, ValueError, AttributeError) as exc:
            skipped.append({
                "aggregator_path": agg_path,
                "ui_adapter_path": ui_path,
                "comparison_kind": kind,
                "notes": notes,
                "reason": f"resolution_error: {type(exc).__name__}: {exc}",
            })
            continue

        row = {
            "aggregator_path":  agg_path,
            "ui_adapter_path":  ui_path,
            "aggregator_value": agg_val,
            "ui_adapter_value": ui_val,
            "comparison_kind":  kind,
            "notes":            notes,
        }
        if ok:
            matches.append(row)
        else:
            mismatches.append(row)

    return {"matches": matches, "mismatches": mismatches, "skipped": skipped}


# ─────────────────────────────────────────────────────────────────────────────
# Output writers
# ─────────────────────────────────────────────────────────────────────────────

def write_xlsx(
    categories: list[dict],
    baselines:  list[dict],
    out_path:   Path,
    comparison: Optional[dict] = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(str(out_path), engine="openpyxl") as writer:
        # Sheet: lineage
        rows = []
        for cat in categories:
            row: dict = {"category": cat["name"], "status": cat["status"]}
            for layer in LAYERS:
                row[layer] = cat["values"].get(layer)
            row["first_divergence_layer"]   = cat.get("first_divergence_layer") or ""
            row["is_difference_expected"]   = cat.get("is_difference_expected", True)
            row["explanation"]              = cat.get("explanation", "")
            row["source_file"]              = cat.get("source", {}).get("file", "")
            row["source_note"]              = cat.get("source", {}).get("note", "")
            rows.append(row)
        pd.DataFrame(rows).to_excel(writer, sheet_name="lineage", index=False)

        # Sheet: expected_baselines
        pd.DataFrame(baselines).to_excel(
            writer, sheet_name="expected_baselines", index=False
        )

        # Sheet: divergences_unexpected
        unexp = [c for c in categories if c.get("status") == "FAIL"]
        if unexp:
            ud_rows = []
            for cat in unexp:
                row = {
                    "category": cat["name"],
                    "first_divergence_layer": cat.get("first_divergence_layer"),
                    "explanation": cat.get("explanation", ""),
                }
                for layer in LAYERS:
                    row[layer] = cat["values"].get(layer)
                ud_rows.append(row)
            pd.DataFrame(ud_rows).to_excel(
                writer, sheet_name="divergences_unexpected", index=False
            )
        else:
            pd.DataFrame(columns=["category", "first_divergence_layer"]).to_excel(
                writer, sheet_name="divergences_unexpected", index=False
            )

        # Sheet: ui_payload_mismatches (always created, even if empty)
        _mismatch_cols = [
            "aggregator_path", "ui_adapter_path",
            "aggregator_value", "ui_adapter_value",
            "comparison_kind", "notes",
        ]
        mismatch_rows = (comparison or {}).get("mismatches", [])
        pd.DataFrame(mismatch_rows, columns=_mismatch_cols).to_excel(
            writer, sheet_name="ui_payload_mismatches", index=False
        )

    _LOG.info("XLSX written: %s", out_path)


def write_json(
    categories:     list[dict],
    baselines:      list[dict],
    run_number:     int,
    flat_ged_path:  str,
    out_path:       Path,
    comparison:     Optional[dict] = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fgp = Path(flat_ged_path) if flat_ged_path else None
    flat_sha  = _sha256(fgp) if fgp and fgp.exists() else "N/A"
    flat_mtime = (
        datetime.fromtimestamp(fgp.stat().st_mtime, tz=timezone.utc).isoformat()
        if fgp and fgp.exists() else "N/A"
    )

    pass_n = sum(1 for c in categories if c["status"] == "PASS")
    warn_n = sum(1 for b in baselines  if b["status"] == "WARN")
    fail_n = (
        sum(1 for c in categories if c["status"] == "FAIL") +
        sum(1 for b in baselines  if b["status"] == "FAIL")
    )

    _cmp = comparison or {"matches": [], "mismatches": [], "skipped": []}
    _compared = len(_cmp["matches"]) + len(_cmp["mismatches"])

    data = {
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "run_number":        run_number,
        "flat_ged_sha256":   flat_sha,
        "flat_ged_mtime":    flat_mtime,
        "expected_baselines": {
            **EXPECTED_BASELINES,
            **{f"{k}_provenance": v for k, v in BASELINE_PROVENANCE.items()},
        },
        "categories": [
            {
                "name":                   c["name"],
                "values":                 {k: v for k, v in c["values"].items()},
                "first_divergence_layer": c.get("first_divergence_layer"),
                "is_difference_expected": c.get("is_difference_expected", True),
                "explanation":            c.get("explanation", ""),
                "source":                 c.get("source", {}),
                "status":                 c.get("status", "PASS"),
            }
            for c in categories
        ],
        "baseline_checks": baselines,
        "summary": {"PASS": pass_n, "WARN": warn_n, "FAIL": fail_n},
        "ui_payload_comparison": {
            "fields_compared": _compared,
            "matches":         len(_cmp["matches"]),
            "mismatches":      len(_cmp["mismatches"]),
            "mismatch_rows":   _cmp["mismatches"],
            "skipped":         _cmp["skipped"],
        },
    }

    with open(str(out_path), "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, default=str)
    _LOG.info("JSON written: %s", out_path)


# ─────────────────────────────────────────────────────────────────────────────
# D-012 — Confirm SAS pre-2026 gap (L1 status_SAS_REF 284 → L2 282)
# ─────────────────────────────────────────────────────────────────────────────

def _confirm_sas_pre2026_gap(base_dir: Path, ctx) -> dict:
    """Confirm that the 2-row gap between L1 status_SAS_REF (284) and L2 (282)
    is caused by the SAS pre-2026 filter in stage_read_flat._apply_sas_filter_flat.

    Reads FLAT_GED.xlsx and ctx.responses_df / ctx.docs_df — does NOT re-run the
    pipeline.  Writes output/debug/sas_pre2026_confirmation.json.
    Returns the result dict.
    """
    flat_path = base_dir / "output" / "intermediate" / "FLAT_GED.xlsx"
    out_path  = base_dir / "output" / "debug" / "sas_pre2026_confirmation.json"

    # Verbatim from stage_read_flat._apply_sas_filter_flat (line ~234–249)
    _FILTER_THRESHOLD = (
        "submittal_date year (int) < 2026 — "
        "pd.to_datetime(submittal_date, errors='coerce').dt.year.astype(float) < 2026, "
        "applied to OPEN_DOC rows in GED_OPERATIONS; "
        "source: src/pipeline/stages/stage_read_flat.py:_apply_sas_filter_flat"
    )

    def _write(payload: dict) -> dict:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(out_path), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
        return payload

    # ── Load GED_RAW_FLAT and GED_OPERATIONS ─────────────────────────────────
    try:
        raw_df = pd.read_excel(str(flat_path), sheet_name="GED_RAW_FLAT",    dtype=str)
        ops_df = pd.read_excel(str(flat_path), sheet_name="GED_OPERATIONS",  dtype=str)
    except Exception as exc:
        return _write({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "UNDETERMINED",
            "verdict_reason": f"Cannot read FLAT_GED.xlsx: {exc}",
        })

    # ── Step 1: L1 set — same column detection as collect_l1 ─────────────────
    _status_col = next(
        (c for c in ("status_clean", "response_status_clean") if c in raw_df.columns),
        None,
    )
    if "is_sas" not in raw_df.columns or _status_col is None:
        return _write({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "UNDETERMINED",
            "verdict_reason": (
                f"GED_RAW_FLAT missing required columns. "
                f"is_sas present: {'is_sas' in raw_df.columns}. "
                f"status col found: {_status_col!r}."
            ),
        })

    is_sas_mask = raw_df["is_sas"].astype(str).str.strip().str.lower() == "true"
    ref_mask    = raw_df[_status_col].astype(str).str.strip() == "REF"
    l1_sas_ref  = raw_df[is_sas_mask & ref_mask].copy()
    l1_pairs: set[tuple] = set(
        zip(
            l1_sas_ref["numero"].astype(str).str.strip(),
            l1_sas_ref["indice"].astype(str).str.strip(),
        )
    )
    l1_sas_ref_row_count        = len(l1_sas_ref)
    l1_sas_ref_unique_pair_count = len(l1_pairs)
    l1_count = l1_sas_ref_unique_pair_count

    # ── Step 2: L2 set — same filter as collect_l2_l3 (H-3 compliant) ────────
    resp_df = getattr(ctx, "responses_df", None)
    docs_df = getattr(ctx, "docs_df", None)
    if resp_df is None or "status_clean" not in resp_df.columns:
        return _write({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "UNDETERMINED",
            "verdict_reason": "ctx.responses_df is None or missing status_clean column",
        })

    # Mirror the two-step filter from collect_l2_l3
    if "is_sas" in resp_df.columns:
        _sas_mask_l2 = resp_df["is_sas"].astype(str).str.strip().str.lower().isin(["true", "1"])
    elif "approver_raw" in resp_df.columns:
        _sas_mask_l2 = resp_df["approver_raw"].astype(str).str.strip() == "0-SAS"
    else:
        return _write({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "UNDETERMINED",
            "verdict_reason": "ctx.responses_df has neither is_sas nor approver_raw column",
        })

    l2_sas_ref   = resp_df[_sas_mask_l2 & (resp_df["status_clean"].astype(str).str.strip() == "REF")]
    l2_doc_ids   = set(l2_sas_ref["doc_id"].astype(str))

    # Translate UUID doc_ids → (numero, indice) via ctx.docs_df
    if (
        docs_df is None
        or "doc_id"  not in docs_df.columns
        or "numero"  not in docs_df.columns
        or "indice"  not in docs_df.columns
    ):
        return _write({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "UNDETERMINED",
            "verdict_reason": "ctx.docs_df missing doc_id / numero / indice columns",
        })

    docs_map: dict[str, tuple] = dict(
        zip(
            docs_df["doc_id"].astype(str),
            zip(
                docs_df["numero"].astype(str).str.strip(),
                docs_df["indice"].astype(str).str.strip(),
            ),
        )
    )
    l2_pairs: set[tuple] = {docs_map[d] for d in l2_doc_ids if d in docs_map}
    l2_sas_ref_row_count        = len(l2_sas_ref)
    l2_sas_ref_unique_pair_count = len(l2_pairs)
    l2_count = l2_sas_ref_unique_pair_count

    # ── Step 3: excluded set ──────────────────────────────────────────────────
    excluded_pairs = l1_pairs - l2_pairs
    excluded_doc_ids         = [f"{n}|{i}" for n, i in sorted(excluded_pairs)]
    excluded_count           = len(excluded_pairs)
    row_gap                  = l1_sas_ref_row_count - l2_sas_ref_row_count

    # Count how many L1 rows each excluded pair contributes
    l1_sas_ref["_pair_key"] = (
        l1_sas_ref["numero"].astype(str).str.strip()
        + "|"
        + l1_sas_ref["indice"].astype(str).str.strip()
    )
    pair_to_l1_row_count: dict[str, int] = {
        f"{n}|{i}": int(
            (
                (l1_sas_ref["numero"].astype(str).str.strip() == n)
                & (l1_sas_ref["indice"].astype(str).str.strip() == i)
            ).sum()
        )
        for n, i in excluded_pairs
    }

    # ── Step 4: per-doc details (date column = submittal_date from OPEN_DOC) ──
    open_ops = (
        ops_df[ops_df["step_type"] == "OPEN_DOC"][["numero", "indice", "submittal_date"]]
        .copy()
    )
    open_ops["numero"] = open_ops["numero"].astype(str).str.strip()
    open_ops["indice"] = open_ops["indice"].astype(str).str.strip()

    per_doc: list[dict] = []
    for (numero, indice) in sorted(excluded_pairs):
        doc_key = f"{numero}|{indice}"
        l1_row_count_for_pair = pair_to_l1_row_count.get(doc_key, 0)

        match = open_ops[(open_ops["numero"] == numero) & (open_ops["indice"] == indice)]
        if match.empty:
            per_doc.append({
                "doc_id":                f"{numero}|{indice}",
                "date_column":           "submittal_date",
                "date_value":            None,
                "would_be_excluded":     False,
                "match_with_hypothesis": False,
                "l1_row_count_for_pair": l1_row_count_for_pair,
            })
            continue

        raw_date = str(match.iloc[0]["submittal_date"]).strip()
        parsed   = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed):
            would_be_excluded = False
        else:
            would_be_excluded = bool(float(parsed.year) < 2026)

        per_doc.append({
            "doc_id":                f"{numero}|{indice}",
            "date_column":           "submittal_date",
            "date_value":            raw_date,
            "would_be_excluded":     would_be_excluded,
            "match_with_hypothesis": would_be_excluded,
            "l1_row_count_for_pair": l1_row_count_for_pair,
        })

    # ── Structural duplicates: L1 pairs with >1 row that are NOT excluded ────
    l1_pair_row_counts = l1_sas_ref["_pair_key"].value_counts()
    structural_duplicate_pairs = sorted(
        k for k, v in l1_pair_row_counts.items()
        if v > 1 and tuple(k.split("|", 1)) not in excluded_pairs
    )
    structural_normalization_rows = int(
        sum(l1_pair_row_counts[k] - 1 for k in structural_duplicate_pairs)
    )

    # ── Verdict (PARTIAL_CONFIRMED) ───────────────────────────────────────────
    excluded_l1_row_count = sum(d["l1_row_count_for_pair"] for d in per_doc)
    all_excluded          = all(d["would_be_excluded"] for d in per_doc) if per_doc else False
    pair_gap              = l1_sas_ref_unique_pair_count - l2_sas_ref_unique_pair_count
    sas_filter_explained_rows = excluded_l1_row_count

    sas_filter_component = (
        "CONFIRMED"
        if pair_gap == excluded_count and all_excluded
        else "UNCONFIRMED"
    )
    structural_component = "PRESENT" if row_gap > sas_filter_explained_rows else "ABSENT"

    if sas_filter_component == "CONFIRMED" and structural_component == "PRESENT":
        verdict = "PARTIAL_CONFIRMED"
        verdict_reason = (
            f"SAS filter component CONFIRMED: pair_gap={pair_gap} == "
            f"excluded_unique_pair_count={excluded_count} and all excluded pairs "
            f"have submittal_date year < 2026. "
            f"Structural component PRESENT: row_gap={row_gap} > "
            f"sas_filter_explained_rows={sas_filter_explained_rows}; "
            f"structural_normalization_rows={structural_normalization_rows} "
            f"from {structural_duplicate_pairs}."
        )
    elif sas_filter_component == "CONFIRMED":
        verdict = "CONFIRMED"
        verdict_reason = (
            f"excluded_l1_row_count={excluded_l1_row_count} == row_gap={row_gap} "
            f"and all {excluded_count} excluded pair(s) have submittal_date year < 2026."
        )
    else:
        verdict = "UNCONFIRMED"
        bad = sum(1 for d in per_doc if not d["would_be_excluded"])
        verdict_reason = (
            f"sas_filter_component={sas_filter_component}; "
            f"pair_gap={pair_gap} excluded_count={excluded_count}; "
            f"{bad}/{excluded_count} excluded pair(s) do not satisfy the filter condition."
        )

    result = {
        "generated_at":                    datetime.now(timezone.utc).isoformat(),
        "l1_sas_ref_row_count":            l1_sas_ref_row_count,
        "l1_sas_ref_unique_pair_count":    l1_sas_ref_unique_pair_count,
        "l1_sas_ref_doc_ids_count":        l1_count,
        "l2_sas_ref_row_count":            l2_sas_ref_row_count,
        "l2_sas_ref_unique_pair_count":    l2_sas_ref_unique_pair_count,
        "l2_sas_ref_doc_ids_count":        l2_count,
        "row_gap":                         row_gap,
        "pair_gap":                        pair_gap,
        "sas_filter_explained_rows":       sas_filter_explained_rows,
        "structural_normalization_rows":   structural_normalization_rows,
        "sas_filter_excluded_pair":        excluded_doc_ids[0] if excluded_doc_ids else None,
        "structural_duplicate_pairs":      structural_duplicate_pairs,
        "sas_filter_component":            sas_filter_component,
        "structural_component":            structural_component,
        "excluded_doc_ids":                excluded_doc_ids,
        "excluded_count":                  excluded_count,
        "excluded_unique_pair_count":      excluded_count,
        "excluded_l1_row_count":           excluded_l1_row_count,
        "pair_to_l1_row_count":            pair_to_l1_row_count,
        "filter_threshold":                _FILTER_THRESHOLD,
        "per_doc":                         per_doc,
        "verdict":                         verdict,
        "verdict_reason":                  verdict_reason,
    }
    _write(result)
    _LOG.info(
        "D-012 confirmation: verdict=%s sas_filter=%s structural=%s file=%s",
        verdict, sas_filter_component, structural_component, out_path,
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def run_audit(run_number: int = 0) -> dict:
    """Execute the full Phase 1 audit and return results dict."""
    _LOG.info("=== Phase 1 Count Lineage Audit (run_number=%d) ===", run_number)

    _LOG.info("--- L0: RAW GED ---")
    l0 = collect_l0(BASE_DIR)
    if "_error" in l0:
        raise RuntimeError(f"STOP (L0): {l0['_error']}")

    _LOG.info("--- L1: FLAT_GED.xlsx ---")
    l1 = collect_l1(BASE_DIR)
    if "_error" in l1:
        raise RuntimeError(f"STOP (L1): {l1['_error']}")

    _LOG.info("--- L2/L3: RunContext ---")
    l2, ctx = collect_l2_l3(BASE_DIR, run_number)
    if "_error" in l2:
        raise RuntimeError(f"STOP (L2/L3): {l2['_error']}")
    if ctx is None:
        raise RuntimeError("STOP: RunContext is None")

    _LOG.info("--- L4: Aggregator ---")
    l4 = collect_l4(ctx)

    _LOG.info("--- L5: UI Adapter ---")
    l5 = collect_l5(ctx)

    _LOG.info("--- L6: Chain+Onion ---")
    l6 = collect_l6(BASE_DIR)

    _LOG.info("--- Baseline checks ---")
    baselines = check_baselines(l0, l1, l2)
    for b in baselines:
        _LOG.info(
            "  %-40s expected=%6s  observed=%s  %s",
            b["baseline_key"], b["expected"], b["observed"], b["status"],
        )

    _LOG.info("--- Category table ---")
    cats_raw   = build_category_table(l0, l1, l2, l4, l5, l6)
    categories = compute_audit(cats_raw)

    pass_n = sum(1 for c in categories if c["status"] == "PASS")
    warn_n = sum(1 for b in baselines  if b["status"] == "WARN")
    fail_n = (
        sum(1 for c in categories if c["status"] == "FAIL") +
        sum(1 for b in baselines  if b["status"] == "FAIL")
    )

    first_unexp: Optional[str] = None
    for c in categories:
        if c["status"] == "FAIL":
            first_unexp = f"{c['name']}@{c.get('first_divergence_layer', '?')}"
            break
    if first_unexp is None:
        for b in baselines:
            if b["status"] == "FAIL":
                first_unexp = f"baseline:{b['baseline_key']}"
                break

    out_dir   = BASE_DIR / "output" / "debug"
    xlsx_path = out_dir / "counts_lineage_audit.xlsx"
    json_path = out_dir / "counts_lineage_audit.json"
    flat_ged  = str(BASE_DIR / "output" / "intermediate" / "FLAT_GED.xlsx")

    # UI payload comparison — uses already-computed kpis/overview (no re-invocation)
    _LOG.info("--- UI payload comparison ---")
    comparison: dict = {"matches": [], "mismatches": [], "skipped": []}
    try:
        comparison = _compare_ui_payload(ctx, None, l4["kpis_raw"], l5["overview_raw"])
    except Exception as _cmp_exc:
        _LOG.warning("UI payload comparison raised an exception: %s", _cmp_exc)

    write_xlsx(categories, baselines, xlsx_path, comparison=comparison)
    write_json(categories, baselines, run_number, flat_ged, json_path, comparison=comparison)

    # D-012: always run; writes sas_pre2026_confirmation.json as a side file
    _LOG.info("--- D-012: SAS pre-2026 gap confirmation ---")
    d012: dict = {}
    try:
        d012 = _confirm_sas_pre2026_gap(BASE_DIR, ctx)
    except Exception as _d012_exc:
        d012 = {"verdict": "UNDETERMINED", "verdict_reason": str(_d012_exc)}
        _LOG.warning("D-012 confirmation raised an exception: %s", _d012_exc)

    summary_line = (
        f"AUDIT: PASS={pass_n} WARN={warn_n} FAIL={fail_n}; "
        f"first_unexpected_divergence={first_unexp or 'none'}"
    )
    print(summary_line)

    _cmp_compared = len(comparison["matches"]) + len(comparison["mismatches"])
    _cmp_verdict = (
        "OK - all compared fields match"
        if not comparison["mismatches"]
        else f"MISMATCH - {len(comparison['mismatches'])} field(s) differ"
    )
    print(
        f"UI_PAYLOAD: compared={_cmp_compared} "
        f"matches={len(comparison['matches'])} "
        f"mismatches={len(comparison['mismatches'])}; {_cmp_verdict}"
    )

    return {
        "categories":                categories,
        "baselines":                 baselines,
        "summary":                   {"PASS": pass_n, "WARN": warn_n, "FAIL": fail_n},
        "first_unexpected_divergence": first_unexp,
        "xlsx_path":                 str(xlsx_path),
        "json_path":                 str(json_path),
        "d012":                      d012,
        "ui_payload_comparison":     comparison,
        "l0": l0, "l1": l1, "l2": l2, "l4": l4, "l5": l5, "l6": l6,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Probe mode (Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

# Static origin metadata keyed by (category, layer).
# value_origin_type choices: measured_excel | computed_dataframe |
#   computed_runcontext | aggregator_output | ui_adapter_output |
#   chain_onion_artifact | expected_baseline_literal | missing
_PROBE_ORIGIN: dict[tuple[str, str], dict] = {}

def _po(cat: str, layer: str, **kwargs) -> None:
    _PROBE_ORIGIN[(cat, layer)] = kwargs


# ── L0 origins ───────────────────────────────────────────────────────────────
for _cat in ("submission_instance_count",):
    _po(_cat, "L0_RAW_GED",
        value_origin_type="measured_excel",
        source_file="input/GED_export.xlsx",
        source_sheet="Doc. sous workflow, x versions",
        source_column=None,
        source_filter="data rows (Excel rows 3..N, dropna all)",
        function_or_code_path="audit_counts_lineage:collect_l0",
        is_hardcoded_baseline=False, confidence="high")

for _cat in ("active_version_count", "family_count", "numero_indice_count"):
    _po(_cat, "L0_RAW_GED",
        value_origin_type="measured_excel",
        source_file="input/GED_export.xlsx",
        source_sheet="Doc. sous workflow, x versions",
        source_column="NUMERO / INDICE",
        source_filter="unique (NUMERO, INDICE) pairs",
        function_or_code_path="audit_counts_lineage:collect_l0",
        is_hardcoded_baseline=False, confidence="high")

_po("status_SAS_REF", "L0_RAW_GED",
    value_origin_type="measured_excel",
    source_file="input/GED_export.xlsx",
    source_sheet="Doc. sous workflow, x versions",
    source_column='Réponse (under 0-SAS section headers)',
    source_filter='Réponse == "REF" in any 0-SAS block (forward-filled section header)',
    function_or_code_path="audit_counts_lineage:collect_l0",
    is_hardcoded_baseline=False, confidence="high")

# ── L1 origins ───────────────────────────────────────────────────────────────
_po("active_version_count", "L1_FLAT_GED_XLSX",
    value_origin_type="measured_excel",
    source_file="output/intermediate/FLAT_GED.xlsx",
    source_sheet="GED_OPERATIONS",
    source_column="step_type",
    source_filter='step_type == "OPEN_DOC"',
    function_or_code_path="audit_counts_lineage:collect_l1",
    is_hardcoded_baseline=False, confidence="high")

_po("open_doc_row_count", "L1_FLAT_GED_XLSX",
    value_origin_type="measured_excel",
    source_file="output/intermediate/FLAT_GED.xlsx",
    source_sheet="GED_OPERATIONS",
    source_column="step_type",
    source_filter='step_type == "OPEN_DOC"',
    function_or_code_path="audit_counts_lineage:collect_l1",
    is_hardcoded_baseline=False, confidence="high")

_po("sas_row_count", "L1_FLAT_GED_XLSX",
    value_origin_type="measured_excel",
    source_file="output/intermediate/FLAT_GED.xlsx",
    source_sheet="GED_OPERATIONS",
    source_column="step_type",
    source_filter='step_type == "SAS"',
    function_or_code_path="audit_counts_lineage:collect_l1",
    is_hardcoded_baseline=False, confidence="high")

_po("consultant_row_count", "L1_FLAT_GED_XLSX",
    value_origin_type="measured_excel",
    source_file="output/intermediate/FLAT_GED.xlsx",
    source_sheet="GED_OPERATIONS",
    source_column="step_type",
    source_filter='step_type == "CONSULTANT"',
    function_or_code_path="audit_counts_lineage:collect_l1",
    is_hardcoded_baseline=False, confidence="high")

_po("moex_row_count", "L1_FLAT_GED_XLSX",
    value_origin_type="measured_excel",
    source_file="output/intermediate/FLAT_GED.xlsx",
    source_sheet="GED_OPERATIONS",
    source_column="step_type",
    source_filter='step_type == "MOEX"',
    function_or_code_path="audit_counts_lineage:collect_l1",
    is_hardcoded_baseline=False, confidence="high")

_po("workflow_step_count", "L1_FLAT_GED_XLSX",
    value_origin_type="measured_excel",
    source_file="output/intermediate/FLAT_GED.xlsx",
    source_sheet="GED_RAW_FLAT",
    source_column=None,
    source_filter="all rows (dropna all)",
    function_or_code_path="audit_counts_lineage:collect_l1",
    is_hardcoded_baseline=False, confidence="high")

_po("family_count", "L1_FLAT_GED_XLSX",
    value_origin_type="measured_excel",
    source_file="output/intermediate/FLAT_GED.xlsx",
    source_sheet="GED_OPERATIONS",
    source_column="numero",
    source_filter='step_type == "OPEN_DOC", nunique(numero)',
    function_or_code_path="audit_counts_lineage:collect_l1",
    is_hardcoded_baseline=False, confidence="high")

_po("numero_indice_count", "L1_FLAT_GED_XLSX",
    value_origin_type="measured_excel",
    source_file="output/intermediate/FLAT_GED.xlsx",
    source_sheet="GED_OPERATIONS",
    source_column="(numero, indice)",
    source_filter='step_type == "OPEN_DOC", drop_duplicates',
    function_or_code_path="audit_counts_lineage:collect_l1",
    is_hardcoded_baseline=False, confidence="high")

_po("status_SAS_REF", "L1_FLAT_GED_XLSX",
    value_origin_type="measured_excel",
    source_file="output/intermediate/FLAT_GED.xlsx",
    source_sheet="GED_RAW_FLAT",
    source_column="is_sas, status_clean",
    source_filter='is_sas == True AND status_clean == "REF"',
    function_or_code_path="audit_counts_lineage:collect_l1",
    is_hardcoded_baseline=False, confidence="high")

# ── L2/L3 origins ────────────────────────────────────────────────────────────
_L2_LAYERS = ("L2_STAGE_READ_FLAT", "L3_RUNCONTEXT_CACHE")
for _layer in _L2_LAYERS:
    for _cat in ("active_version_count", "open_doc_row_count"):
        _po(_cat, _layer,
            value_origin_type="computed_dataframe",
            source_file="src/reporting/data_loader.py",
            source_sheet=None,
            source_column="doc_id",
            source_filter="ctx.docs_df row count",
            function_or_code_path="audit_counts_lineage:collect_l2_l3",
            is_hardcoded_baseline=False, confidence="high")
    for _cat in ("family_count",):
        _po(_cat, _layer,
            value_origin_type="computed_dataframe",
            source_file="src/reporting/data_loader.py",
            source_sheet=None,
            source_column="numero",
            source_filter="ctx.docs_df nunique(numero)",
            function_or_code_path="audit_counts_lineage:collect_l2_l3",
            is_hardcoded_baseline=False, confidence="high")
    for _cat in ("numero_indice_count",):
        _po(_cat, _layer,
            value_origin_type="computed_dataframe",
            source_file="src/reporting/data_loader.py",
            source_sheet=None,
            source_column="(numero, indice)",
            source_filter="ctx.docs_df drop_duplicates",
            function_or_code_path="audit_counts_lineage:collect_l2_l3",
            is_hardcoded_baseline=False, confidence="high")
    for _cat in ("workflow_step_count", "response_row_count"):
        _po(_cat, _layer,
            value_origin_type="computed_dataframe",
            source_file="src/reporting/data_loader.py",
            source_sheet=None,
            source_column=None,
            source_filter="ctx.responses_df row count",
            function_or_code_path="audit_counts_lineage:collect_l2_l3",
            is_hardcoded_baseline=False, confidence="high")
    for _cat in ("sas_row_count",):
        _po(_cat, _layer,
            value_origin_type="computed_dataframe",
            source_file="src/reporting/data_loader.py",
            source_sheet=None,
            source_column="approver_raw",
            source_filter='approver_raw == "0-SAS"',
            function_or_code_path="audit_counts_lineage:collect_l2_l3",
            is_hardcoded_baseline=False, confidence="high")
    for _cat in ("status_SAS_REF",):
        _po(_cat, _layer,
            value_origin_type="computed_dataframe",
            source_file="src/reporting/data_loader.py",
            source_sheet=None,
            source_column="is_sas, status_clean",
            source_filter='is_sas == True AND status_clean == "REF" (ctx.responses_df, H-3 compliant)',
            function_or_code_path="audit_counts_lineage:collect_l2_l3",
            is_hardcoded_baseline=False, confidence="high")
    for _cat in ("status_VSO", "status_VAO", "status_REF", "status_HM", "open_count"):
        _po(_cat, _layer,
            value_origin_type="computed_runcontext",
            source_file="src/workflow_engine.py",
            source_sheet=None,
            source_column="visa_global",
            source_filter="compute_visa_global_with_date(doc_id) per dernier_df",
            function_or_code_path="audit_counts_lineage:collect_l2_l3",
            is_hardcoded_baseline=False, confidence="medium")
    for _cat in ("consultant_row_count", "moex_row_count"):
        _po(_cat, _layer,
            value_origin_type="computed_dataframe",
            source_file="src/reporting/data_loader.py",
            source_sheet=None,
            source_column="flat_step_type",
            source_filter='flat_step_type == "CONSULTANT" / "MOEX"',
            function_or_code_path="audit_counts_lineage:collect_l2_l3",
            is_hardcoded_baseline=False, confidence="medium")

# ── L4 origins ───────────────────────────────────────────────────────────────
for _cat in ("active_version_count", "status_VSO", "status_VAO", "status_REF",
             "status_HM", "open_count"):
    _po(_cat, "L4_AGGREGATOR",
        value_origin_type="aggregator_output",
        source_file="src/reporting/aggregator.py",
        source_sheet=None,
        source_column=None,
        source_filter="compute_project_kpis(ctx)",
        function_or_code_path="reporting.aggregator:compute_project_kpis",
        is_hardcoded_baseline=False, confidence="high")

_po("status_SAS_REF", "L4_AGGREGATOR",
    value_origin_type="computed_dataframe",
    source_file="src/reporting/data_loader.py",
    source_sheet=None,
    source_column="is_sas, status_clean",
    source_filter='is_sas == True AND status_clean == "REF" (ctx.responses_df; aggregator by_visa_global["SAS REF"] is Phase-3-gap)',
    function_or_code_path="audit_counts_lineage:collect_l4",
    is_hardcoded_baseline=False, confidence="high")

for _cat in ("docs_pending_sas", "total_consultants", "total_contractors"):
    _po(_cat, "L4_AGGREGATOR",
        value_origin_type="aggregator_output",
        source_file="src/reporting/aggregator.py",
        source_sheet=None, source_column=None,
        source_filter="compute_project_kpis(ctx)",
        function_or_code_path="reporting.aggregator:compute_project_kpis",
        is_hardcoded_baseline=False, confidence="high")

# ── L5 origins ───────────────────────────────────────────────────────────────
for _cat in ("active_version_count", "status_VSO", "status_VAO",
             "status_HM", "open_count"):
    _po(_cat, "L5_UI_ADAPTER",
        value_origin_type="ui_adapter_output",
        source_file="src/reporting/ui_adapter.py",
        source_sheet=None, source_column=None,
        source_filter="adapt_overview(dashboard_data, {})",
        function_or_code_path="reporting.ui_adapter:adapt_overview",
        is_hardcoded_baseline=False, confidence="high")

for _cat in ("total_consultants", "total_contractors"):
    _po(_cat, "L5_UI_ADAPTER",
        value_origin_type="ui_adapter_output",
        source_file="src/reporting/ui_adapter.py",
        source_sheet=None, source_column=None,
        source_filter="adapt_overview → project_stats",
        function_or_code_path="reporting.ui_adapter:adapt_overview",
        is_hardcoded_baseline=False, confidence="high")

# ── L6 origins ───────────────────────────────────────────────────────────────
for _cat in ("active_version_count",):
    _po(_cat, "L6_CHAIN_ONION",
        value_origin_type="chain_onion_artifact",
        source_file="output/chain_onion/CHAIN_VERSIONS.csv",
        source_sheet=None, source_column="version_key",
        source_filter="nunique(version_key)",
        function_or_code_path="audit_counts_lineage:collect_l6",
        is_hardcoded_baseline=False, confidence="high")

for _cat in ("family_count",):
    _po(_cat, "L6_CHAIN_ONION",
        value_origin_type="chain_onion_artifact",
        source_file="output/chain_onion/CHAIN_REGISTER.csv",
        source_sheet=None, source_column="family_key",
        source_filter="nunique(family_key)",
        function_or_code_path="audit_counts_lineage:collect_l6",
        is_hardcoded_baseline=False, confidence="high")

for _cat in ("live_operational_count",):
    _po(_cat, "L6_CHAIN_ONION",
        value_origin_type="chain_onion_artifact",
        source_file="output/chain_onion/CHAIN_REGISTER.csv",
        source_sheet=None, source_column="portfolio_bucket",
        source_filter='portfolio_bucket == "LIVE_OPERATIONAL"',
        function_or_code_path="audit_counts_lineage:collect_l6",
        is_hardcoded_baseline=False, confidence="high")

for _cat in ("legacy_backlog_count",):
    _po(_cat, "L6_CHAIN_ONION",
        value_origin_type="chain_onion_artifact",
        source_file="output/chain_onion/CHAIN_REGISTER.csv",
        source_sheet=None, source_column="portfolio_bucket",
        source_filter='portfolio_bucket == "LEGACY_BACKLOG"',
        function_or_code_path="audit_counts_lineage:collect_l6",
        is_hardcoded_baseline=False, confidence="high")


_PROBE_RECORD_KEYS = (
    "category", "layer", "value", "value_origin_type",
    "source_file", "source_sheet", "source_column", "source_filter",
    "function_or_code_path", "is_hardcoded_baseline", "confidence",
)


def build_probe_records(categories: list[dict]) -> list[dict]:
    """Build one probe record per (category, layer) from lineage table."""
    records: list[dict] = []
    for cat in categories:
        name   = cat["name"]
        values = cat["values"]
        for layer in LAYERS:
            value = values.get(layer)
            meta  = _PROBE_ORIGIN.get((name, layer), {})
            if value is None and not meta:
                origin_type = "missing"
                src_file = src_sheet = src_col = src_filter = func = None
                is_hc = False
                conf = "low"
            elif value is None:
                origin_type = meta.get("value_origin_type", "missing")
                src_file  = meta.get("source_file")
                src_sheet = meta.get("source_sheet")
                src_col   = meta.get("source_column")
                src_filter = meta.get("source_filter")
                func      = meta.get("function_or_code_path")
                is_hc     = meta.get("is_hardcoded_baseline", False)
                conf      = meta.get("confidence", "low")
            else:
                origin_type = meta.get("value_origin_type", "missing")
                src_file  = meta.get("source_file")
                src_sheet = meta.get("source_sheet")
                src_col   = meta.get("source_column")
                src_filter = meta.get("source_filter")
                func      = meta.get("function_or_code_path")
                is_hc     = meta.get("is_hardcoded_baseline", False)
                conf      = meta.get("confidence", "medium")
                if origin_type == "missing":
                    # Value is present but no metadata — infer from layer
                    layer_defaults = {
                        "L0_RAW_GED":          "measured_excel",
                        "L1_FLAT_GED_XLSX":    "measured_excel",
                        "L2_STAGE_READ_FLAT":  "computed_dataframe",
                        "L3_RUNCONTEXT_CACHE": "computed_dataframe",
                        "L4_AGGREGATOR":       "aggregator_output",
                        "L5_UI_ADAPTER":       "ui_adapter_output",
                        "L6_CHAIN_ONION":      "chain_onion_artifact",
                    }
                    origin_type = layer_defaults.get(layer, "missing")
            records.append({
                "category":             name,
                "layer":                layer,
                "value":                value,
                "value_origin_type":    origin_type,
                "source_file":          src_file,
                "source_sheet":         src_sheet,
                "source_column":        src_col,
                "source_filter":        src_filter,
                "function_or_code_path": func,
                "is_hardcoded_baseline": is_hc,
                "confidence":           conf,
            })
    return records


def write_probe_json(records: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(out_path), "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2, default=str)
    _LOG.info("Probe JSON written: %s", out_path)


def write_probe_xlsx(records: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records, columns=list(_PROBE_RECORD_KEYS))
    with pd.ExcelWriter(str(out_path), engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="probe", index=False)
    _LOG.info("Probe XLSX written: %s", out_path)


def run_probe(run_number: int = 0) -> list[dict]:
    """Run probe mode: collect all layers, emit origin record per (category, layer)."""
    _LOG.info("=== Phase 2 Probe Mode (run_number=%d) ===", run_number)

    l0 = collect_l0(BASE_DIR)
    if "_error" in l0:
        raise RuntimeError(f"STOP (L0): {l0['_error']}")

    l1 = collect_l1(BASE_DIR)
    if "_error" in l1:
        raise RuntimeError(f"STOP (L1): {l1['_error']}")

    # Stop condition: L1 SAS REF must not be 0 after fix
    l1_sas_ref = l1.get("status_SAS_REF")
    if l1_sas_ref is not None and l1_sas_ref == 0:
        raise RuntimeError(
            f"STOP: L1 status_SAS_REF == 0 after fix. "
            f"Warn: {l1.get('_warn_sas_ref', 'no warning')}. "
            "Phase 2 FAILS — do not write §19."
        )

    l2, ctx = collect_l2_l3(BASE_DIR, run_number)
    if "_error" in l2:
        raise RuntimeError(f"STOP (L2/L3): {l2['_error']}")
    if ctx is None:
        raise RuntimeError("STOP: RunContext is None")

    l4 = collect_l4(ctx)
    l5 = collect_l5(ctx)
    l6 = collect_l6(BASE_DIR)

    cats_raw   = build_category_table(l0, l1, l2, l4, l5, l6)
    categories = compute_audit(cats_raw)

    records = build_probe_records(categories)

    out_dir    = BASE_DIR / "output" / "debug"
    json_path  = out_dir / "counts_lineage_probe.json"
    xlsx_path  = out_dir / "counts_lineage_probe.xlsx"

    write_probe_json(records, json_path)
    write_probe_xlsx(records, xlsx_path)

    n_missing  = sum(1 for r in records if r["value_origin_type"] == "missing" and r["value"] is not None)
    n_baseline = sum(1 for r in records if r["value_origin_type"] == "expected_baseline_literal")
    print(
        f"PROBE: {len(records)} records | "
        f"layers={LAYERS[0]}..{LAYERS[-1]} | "
        f"expected_baseline_literal={n_baseline} | "
        f"missing_origin_with_value={n_missing}"
    )
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 1/2 Count Lineage Audit")
    parser.add_argument("--run", type=int, default=0,
                        help="Run number to audit (default: 0)")
    parser.add_argument("--probe", action="store_true",
                        help="Run Phase 2 probe mode (origin analysis); writes counts_lineage_probe.{json,xlsx}")
    args = parser.parse_args()
    if args.probe:
        run_probe(run_number=args.run)
    else:
        run_audit(run_number=args.run)
