"""
Stage 7: Write GF and anomaly reports.

Builds workflow engine, writes GF_V0_CLEAN.xlsx, and writes anomaly/ignored reports.
"""

import datetime as _dt
import pandas as pd
from workflow_engine import WorkflowEngine
from routing import build_gf_to_ged_map
from domain.sas_helpers import _build_sas_lookup
from writer import GFWriter, write_anomaly_report, write_auto_resolution_log, write_ignored_items_log
from pipeline.utils import _safe_console_print


def stage_write_gf(ctx, log):
    """
    Write GF and anomaly reports stage.

    Reads from ctx:
        - effective_responses_df, dernier_df_for_gf, responses_df, sheet_structures
        - versioned_df, dernier_df, sas_filtered_df, mismatch_count
        - OUTPUT_GF, GF_FILE, OUTPUT_ANOMALY, OUTPUT_AUTO_RESOLUTION, OUTPUT_IGNORED

    Writes to ctx:
        - wf_engine, gf_to_ged_map, ancien_df, gf_sas_lookup
    """
    effective_responses_df = ctx.effective_responses_df
    dernier_df_for_gf = ctx.dernier_df_for_gf
    responses_df = ctx.responses_df
    sheet_structures = ctx.sheet_structures
    versioned_df = ctx.versioned_df
    dernier_df = ctx.dernier_df
    sas_filtered_df = ctx.sas_filtered_df
    mismatch_count = ctx.mismatch_count

    OUTPUT_GF = ctx.OUTPUT_GF
    GF_FILE = ctx.GF_FILE
    OUTPUT_ANOMALY = ctx.OUTPUT_ANOMALY
    OUTPUT_AUTO_RESOLUTION = ctx.OUTPUT_AUTO_RESOLUTION
    OUTPUT_IGNORED = ctx.OUTPUT_IGNORED

    # ── Step 6: Build workflow engine using EFFECTIVE responses ───────────────
    wf_engine = WorkflowEngine(effective_responses_df)

    # Build GF→GED approver name map (use effective_responses_df for full canonical list)
    ged_canonical_approvers = effective_responses_df["approver_canonical"].unique().tolist()
    gf_to_ged_map = build_gf_to_ged_map(ged_canonical_approvers)
    log(f"GF→GED approver mappings: {len(gf_to_ged_map)} entries")

    # ── Build ancien_df: VALID_HISTORICAL rows only ──────────────────────────
    # Distinguish two conceptually different row types:
    #
    #   VALID_HISTORICAL — older indices of an active document family.
    #     • is_dernier_indice == False
    #     • is_excluded_lifecycle == False  (no superseded/reused-numero lifecycle)
    #     • lifecycle_id belongs to a DI row that made it into dernier_df_for_gf
    #       (i.e. the family is not config-excluded / emetteur-mismatch excluded)
    #     • has a valid routing destination (gf_sheet_name not null)
    #     → Written to GF_V0_CLEAN with ANCIEN="1" and FULL approver_statuses.
    #
    #   EXCEPTION — must NOT appear in GF_V0_CLEAN:
    #     • SAS_OLD_UNRESOLVED docs → already removed before VersionEngine runs
    #     • is_excluded_lifecycle == True → superseded lifecycles (reused numero)
    #     • Config-excluded families → filtered by lifecycle_id not in active set
    #     → Written only to IGNORED / DEBUG outputs.
    #
    active_lifecycle_ids = set(dernier_df_for_gf["lifecycle_id"].dropna().unique())
    ancien_df = versioned_df[
        (versioned_df["is_dernier_indice"] == False) &
        (versioned_df["is_excluded_lifecycle"] == False) &   # VALID_HISTORICAL only
        (versioned_df["lifecycle_id"].isin(active_lifecycle_ids)) &  # active families
        (versioned_df["gf_sheet_name"].notna())              # routed to a GF sheet
    ].copy()
    log(f"Ancien VALID_HISTORICAL rows for GF: {len(ancien_df)}")

    # ── Build SAS lookup for DATE CONTRACTUELLE Case B (Round 2 Patch 2) ──
    # sas_lookup[doc_id] = {sas_result, sas_date, ...}
    # Case B: SAS passed (VSO-SAS / VAO-SAS) → DATE CONTRACT = SAS date + 15
    # Case A: SAS not yet passed → DATE CONTRACT = date_diffusion + 15
    log("Building SAS lookup for DATE CONTRACTUELLE...")
    gf_sas_lookup = _build_sas_lookup(responses_df)
    sas_case_b_count = sum(
        1 for v in gf_sas_lookup.values()
        if v.get("sas_result", "") in ("VSO-SAS", "VAO-SAS", "VSO", "VAO")
        and v.get("sas_date") is not None
    )
    log(f"  SAS lookup: {len(gf_sas_lookup)} docs with SAS data, {sas_case_b_count} Case B (SAS passed + date)")

    # Write GF
    log("Writing GF_V0_CLEAN.xlsx...")
    gf_writer = GFWriter(str(OUTPUT_GF), str(GF_FILE))
    gf_writer.write_all(
        docs_df=dernier_df_for_gf,
        responses_df=responses_df,
        workflow_engine=wf_engine,
        sheet_structures=sheet_structures,
        gf_to_ged_map=gf_to_ged_map,
        ancien_df=ancien_df,
        sas_lookup=gf_sas_lookup,
    )
    gf_writer.save()
    log(f"  → {OUTPUT_GF}")

    # Split anomalies by resolution_status
    # Include excluded docs from config in IGNORED bucket
    excluded_flags_df = dernier_df[dernier_df["is_excluded_config"] == True].copy()
    excluded_flags_df["anomaly_flags"] = excluded_flags_df.apply(
        lambda r: (r.get("anomaly_flags") or []) + [f"EXCLUDED:{r.get('exclusion_reason','')}"],
        axis=1
    )

    all_anomaly_df = pd.concat([
        versioned_df[versioned_df["anomaly_flags"].apply(lambda x: len(x) > 0)],
        excluded_flags_df[~excluded_flags_df["doc_id"].isin(
            versioned_df[versioned_df["anomaly_flags"].apply(lambda x: len(x) > 0)]["doc_id"]
        )]
    ], ignore_index=True).copy()

    review_df   = all_anomaly_df[all_anomaly_df["resolution_status"] == "REVIEW_REQUIRED"]
    auto_df     = all_anomaly_df[all_anomaly_df["resolution_status"] == "AUTO_RESOLVED"]
    ignored_df  = all_anomaly_df[all_anomaly_df["resolution_status"] == "IGNORED"]

    log(f"Anomalies — REVIEW_REQUIRED: {len(review_df)}, AUTO_RESOLVED: {len(auto_df)}, IGNORED: {len(ignored_df)}")

    log("Writing ANOMALY_REPORT.xlsx (REVIEW_REQUIRED only)...")
    write_anomaly_report(str(OUTPUT_ANOMALY), review_df)
    log(f"  → {OUTPUT_ANOMALY}")

    log("Writing AUTO_RESOLUTION_LOG.xlsx...")
    write_auto_resolution_log(str(OUTPUT_AUTO_RESOLUTION), auto_df)
    log(f"  → {OUTPUT_AUTO_RESOLUTION}")

    log("Writing IGNORED_ITEMS_LOG.xlsx...")
    # Merge workflow-level ignored_df with SAS-filtered docs
    if len(sas_filtered_df) > 0:
        sas_log_df = sas_filtered_df.copy()
        sas_log_df["resolution_status"] = "IGNORED"
        sas_log_df["anomaly_flags"] = sas_log_df.apply(lambda _: ["SAS_OLD_UNRESOLVED"], axis=1)
        sas_log_df["exclusion_reason"] = "SAS_OLD_UNRESOLVED"
        combined_ignored = pd.concat([ignored_df, sas_log_df], ignore_index=True)
    else:
        combined_ignored = ignored_df
    write_ignored_items_log(str(OUTPUT_IGNORED), combined_ignored)
    log(f"  → {OUTPUT_IGNORED} ({len(combined_ignored)} rows total, {len(sas_filtered_df)} SAS_OLD_UNRESOLVED)")

    # Write to ctx
    ctx.wf_engine = wf_engine
    ctx.gf_to_ged_map = gf_to_ged_map
    ctx.ancien_df = ancien_df
    ctx.gf_sas_lookup = gf_sas_lookup

    # Build GF TEAM VERSION (surgical OGF patch)
    _team_out = ctx.OUTPUT_GF_TEAM_VERSION
    if _team_out is not None:
        try:
            from team_version_builder import build_team_version
            log("Building GF_TEAM_VERSION...")
            _team_report = build_team_version(
                ogf_path=str(GF_FILE),
                clean_path=str(OUTPUT_GF),
                out_path=str(_team_out),
            )
            log(f"  -> {_team_out}  (matched={_team_report['total_matched']}, "
                f"updated={_team_report['total_updated']}, "
                f"inserted={_team_report['total_inserted']})")
        except Exception as _tv_err:
            log(f"  [WARN] GF_TEAM_VERSION build failed (non-fatal): {_tv_err}")
