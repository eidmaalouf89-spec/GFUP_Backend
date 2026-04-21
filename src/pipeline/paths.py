"""
src/pipeline/paths.py
---------------------
Default path constants for the GF Updater V3 pipeline.

These are the *default* values.  run_orchestrator.py may override some of
them on main's module namespace before calling run_pipeline().  Because of
that, run_pipeline reads paths from the calling module (main), not from
this module.  This file exists so the definitions live in one place and
main.py can do ``from pipeline.paths import *`` to populate its namespace.
"""

from pathlib import Path

# ─────────────────────────────────────────────────────────────
# Resolve relative to main.py (two levels up from this file)
# ───────���─────────────────────────────────────────────────────
_MAIN_DIR = Path(__file__).resolve().parent.parent.parent

BASE_DIR   = _MAIN_DIR
INPUT_DIR  = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
DEBUG_DIR  = OUTPUT_DIR / "debug"

# ── Database paths ────────────────────────────────────────────
REPORT_MEMORY_DB = str(BASE_DIR / "data" / "report_memory.db")
RUN_MEMORY_DB    = str(BASE_DIR / "data" / "run_memory.db")

# ── Input paths ───────────────────────────────────────────────
CONSULTANT_REPORTS_ROOT = INPUT_DIR / "consultant_reports"
CONSULTANT_MATCH_REPORT = OUTPUT_DIR / "consultant_match_report.xlsx"
GED_FILE = INPUT_DIR / "GED_export.xlsx"
GF_FILE  = INPUT_DIR / "Grandfichier_v3.xlsx"

# ── Primary output paths ─────────────────────────────────────
OUTPUT_GF                      = OUTPUT_DIR / "GF_V0_CLEAN.xlsx"
OUTPUT_DISCREPANCY             = OUTPUT_DIR / "DISCREPANCY_REPORT.xlsx"
OUTPUT_DISCREPANCY_REVIEW      = OUTPUT_DIR / "DISCREPANCY_REVIEW_REQUIRED.xlsx"
OUTPUT_ANOMALY                 = OUTPUT_DIR / "ANOMALY_REPORT.xlsx"
OUTPUT_AUTO_RESOLUTION         = OUTPUT_DIR / "AUTO_RESOLUTION_LOG.xlsx"
OUTPUT_IGNORED                 = OUTPUT_DIR / "IGNORED_ITEMS_LOG.xlsx"

# ── Diagnosis outputs (Part E) ───────────────────────────────
OUTPUT_MISSING_GED_DIAGNOSIS   = OUTPUT_DIR / "MISSING_IN_GED_DIAGNOSIS.xlsx"
OUTPUT_MISSING_GED_TRUE        = OUTPUT_DIR / "MISSING_IN_GED_TRUE_ONLY.xlsx"
OUTPUT_MISSING_GF_DIAGNOSIS    = OUTPUT_DIR / "MISSING_IN_GF_DIAGNOSIS.xlsx"
OUTPUT_MISSING_GF_TRUE         = OUTPUT_DIR / "MISSING_IN_GF_TRUE_ONLY.xlsx"

# ── Reconciliation outputs (Patch F) ─────────────────────────
OUTPUT_RECONCILIATION_LOG      = OUTPUT_DIR / "RECONCILIATION_LOG.xlsx"
OUTPUT_RECONCILIATION_SUMMARY  = DEBUG_DIR  / "reconciliation_summary.xlsx"

# ── Insert log ────────────────────────────────────────────────
OUTPUT_INSERT_LOG              = OUTPUT_DIR / "INSERT_LOG.xlsx"

# ── New submittal + consultant outputs ────────────────────────
OUTPUT_NEW_SUBMITTAL_ANALYSIS  = OUTPUT_DIR / "NEW_SUBMITTAL_ANALYSIS.xlsx"
OUTPUT_NEW_SUBMITTAL_SUMMARY   = DEBUG_DIR  / "new_submittal_summary.xlsx"
OUTPUT_CONSULTANT_REPORTS_WB   = OUTPUT_DIR / "consultant_reports.xlsx"
OUTPUT_GF_STAGE1               = OUTPUT_DIR / "GF_consultant_enriched_stage1.xlsx"
OUTPUT_GF_STAGE2               = OUTPUT_DIR / "GF_consultant_enriched_stage2.xlsx"
OUTPUT_GF_TEAM_VERSION         = OUTPUT_DIR / "GF_TEAM_VERSION.xlsx"
OUTPUT_SUSPICIOUS_ROWS         = OUTPUT_DIR / "SUSPICIOUS_ROWS_REPORT.xlsx"

# ── Versioning ────────────────────────────────────────────────
RUN_MEMORY_CORE_VERSION = "P1"
