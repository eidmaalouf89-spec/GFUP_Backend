"""
src/pipeline/context.py
-----------------------
Mutable namespace that carries all inter-stage pipeline state.

PipelineState is *not* a new business data structure — it is purely a
stage-orchestration transport.  It replaces the implicit local-variable
scope of the original monolithic run_pipeline() with an explicit object
so that each extracted stage function can read from / write to the same
shared state.

All attribute names are byte-exact copies of the original local variable
names (e.g. ``docs_df``, ``versioned_df``, ``ok_count``, ``unrouted``).
No variable was renamed during extraction.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PipelineState:
    """Stage-orchestration transport — not a business data structure.

    Attribute names mirror the original run_pipeline() local variables
    exactly.  No renames, no new semantics.

    Fields are grouped into three sections:
      1. Path constants — populated by run_pipeline() before any stage runs.
      2. Run-history state — written by stage_init_run, read/updated by
         later stages and by main.py after the pipeline returns.
      3. Stage outputs — written by each stage, consumed by downstream stages.
    """

    # ── 1. Path constants (set by run_pipeline before stages) ────

    BASE_DIR:                       Path | None = None
    INPUT_DIR:                      Path | None = None
    OUTPUT_DIR:                     Path | None = None
    DEBUG_DIR:                      Path | None = None

    GED_FILE:                       Path | None = None
    GF_FILE:                        Path | None = None

    OUTPUT_GF:                      Path | None = None
    OUTPUT_DISCREPANCY:             Path | None = None
    OUTPUT_DISCREPANCY_REVIEW:      Path | None = None
    OUTPUT_ANOMALY:                 Path | None = None
    OUTPUT_AUTO_RESOLUTION:         Path | None = None
    OUTPUT_IGNORED:                 Path | None = None
    OUTPUT_MISSING_GED_DIAGNOSIS:   Path | None = None
    OUTPUT_MISSING_GED_TRUE:        Path | None = None
    OUTPUT_MISSING_GF_DIAGNOSIS:    Path | None = None
    OUTPUT_MISSING_GF_TRUE:         Path | None = None
    OUTPUT_RECONCILIATION_LOG:      Path | None = None
    OUTPUT_RECONCILIATION_SUMMARY:  Path | None = None
    OUTPUT_INSERT_LOG:              Path | None = None
    OUTPUT_NEW_SUBMITTAL_ANALYSIS:  Path | None = None
    OUTPUT_NEW_SUBMITTAL_SUMMARY:   Path | None = None
    OUTPUT_CONSULTANT_REPORTS_WB:   Path | None = None
    OUTPUT_GF_STAGE1:               Path | None = None
    OUTPUT_GF_STAGE2:               Path | None = None
    OUTPUT_GF_TEAM_VERSION:         Path | None = None
    OUTPUT_SUSPICIOUS_ROWS:         Path | None = None

    RUN_MEMORY_DB:                  str | None = None
    REPORT_MEMORY_DB:               str | None = None
    RUN_MEMORY_CORE_VERSION:        str | None = None

    CONSULTANT_MATCH_REPORT:        Path | None = None
    CONSULTANT_REPORTS_ROOT:        Path | None = None

    # ── 2. Run-history state (stage_init_run + main.py) ──────────

    _RUN_CONTROL_CONTEXT:           dict | None = None
    _ACTIVE_RUN_NUMBER:             int | None = None
    _ACTIVE_RUN_FINALIZED:          bool = False

    _run_number:                    int | None = None
    _run_dir:                       str | None = None
    _run_input_entries:             list = field(default_factory=list)
    _arts_registered:               int = 0
    _is_baseline_bootstrap:         bool = False

    # ── 3. Stage outputs ─────────────────────────────────────────

    # stage_read / stage_read_flat
    docs_df:                        Any = None   # pd.DataFrame
    responses_df:                   Any = None   # pd.DataFrame
    ged_approver_names:             list | None = None
    mapping:                        dict | None = None

    # flat mode extras (stage_read_flat only — None/default in raw mode)
    FLAT_GED_FILE:                  Path | None = None
    flat_ged_mode:                  str = "raw"  # "raw" or "flat"; set by runner + stage_read_flat
    flat_ged_ops_df:                Any = None   # pd.DataFrame (GED_OPERATIONS)
    flat_ged_doc_meta:              dict | None = None  # per-doc closure/visa/responsible

    # stage_normalize (also mutates docs_df, responses_df in place)
    sas_filtered_df:                Any = None   # pd.DataFrame

    # stage_version
    versioned_df:                   Any = None   # pd.DataFrame
    total:                          int = 0
    dernier_count:                  int = 0
    anomaly_count:                  int = 0
    excluded_count:                 int = 0

    # stage_route (also mutates versioned_df in place)
    routing_table:                  Any = None   # RoutingTable
    dernier_df:                     Any = None   # pd.DataFrame
    dernier_df_for_gf:              Any = None   # pd.DataFrame
    exclusion_config:               Any = None   # ExclusionConfig
    ok_count:                       int = 0
    ambiguous_count:                int = 0
    unmatched_count:                int = 0
    unrouted:                       int = 0
    mismatch_count:                 int = 0
    sheet_structures:               dict | None = None

    # stage_report_memory
    persisted_df:                   Any = None   # pd.DataFrame
    effective_responses_df:         Any = None   # pd.DataFrame

    # stage_write_gf
    wf_engine:                      Any = None   # WorkflowEngine
    gf_to_ged_map:                  dict | None = None
    ancien_df:                      Any = None   # pd.DataFrame
    gf_sas_lookup:                  dict | None = None

    # stage_discrepancy
    data_date:                      datetime.datetime | None = None
    discrepancies:                  list = field(default_factory=list)
    gf_by_sheet:                    dict | None = None
    recon_log:                      list = field(default_factory=list)
    disc_review:                    list = field(default_factory=list)
    disc_cosmetic:                  list = field(default_factory=list)
    disc_excluded:                  list = field(default_factory=list)
    disc_info:                      list = field(default_factory=list)
    mid_before:                     int = 0
    mid_after:                      int = 0
    mif_before:                     int = 0
    mif_after:                      int = 0
