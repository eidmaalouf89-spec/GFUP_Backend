"""
stage_route — Route to contractor sheets and read GF structures.

Lines 467-541 of run_pipeline().
Routes documents to contractor sheets, applies exclusion config, reads GF structures.
Covers STEP 5 (routing), STEP 5b (exclusion config), and STEP 6 (read GF structures).
"""

from routing import (
    build_routing_table,
    route_documents,
    write_routing_summary,
    read_all_gf_sheet_structures,
)
from config_loader import load_exclusion_config
from pipeline.utils import _safe_console_print


def stage_route(ctx, log):
    """
    Route documents to contractor sheets and read GF structures.

    Context reads:
      - ctx.GF_FILE
      - ctx.DEBUG_DIR
      - ctx.versioned_df

    Context writes:
      - ctx.routing_table
      - ctx.versioned_df (mutated)
      - ctx.dernier_df
      - ctx.dernier_df_for_gf
      - ctx.exclusion_config
      - ctx.ok_count
      - ctx.ambiguous_count
      - ctx.unmatched_count
      - ctx.unrouted
      - ctx.mismatch_count
      - ctx.sheet_structures
    """
    # ── STEP 5: Route to Contractor Sheets ───────────────────
    _safe_console_print("\n[5/7] Routing to contractor sheets...")
    routing_table = build_routing_table(str(ctx.GF_FILE))
    routing_entries = sum(1 for _ in routing_table.all_entries())
    log(f"Routing table entries: {routing_entries}")

    # Route all versions (not just dernier_indice) — uses emetteur now (Patch A)
    versioned_df = route_documents(ctx.versioned_df, routing_table)

    # Write routing summary debug artifact
    routing_summary_path = str(ctx.DEBUG_DIR / "routing_summary.xlsx")
    write_routing_summary(routing_summary_path, versioned_df, routing_table)
    log(f"  → debug/routing_summary.xlsx written")

    # Only keep dernier_indice docs for output
    dernier_df = versioned_df[versioned_df["is_dernier_indice"] == True].copy()

    # Count routing outcomes
    ok_count          = (dernier_df["routing_status"] == "OK").sum()
    ambiguous_count   = (dernier_df["routing_status"] == "ROUTING_AMBIGUOUS").sum()
    unmatched_count   = (dernier_df["routing_status"] == "ROUTING_UNMATCHED").sum()
    mismatch_count    = (dernier_df["routing_status"] == "ROUTING_EMETTEUR_MISMATCH").sum()
    routed = ok_count + ambiguous_count
    unrouted = unmatched_count

    log(f"Documents routed OK: {ok_count}")
    log(f"Documents routed (ambiguous): {ambiguous_count}")
    log(f"Documents unmatched (no sheet): {unmatched_count}")
    log(f"Documents with emetteur mismatch (wrong contractor): {mismatch_count}")

    if unrouted > 0:
        missing_lots = dernier_df[
            dernier_df["routing_status"] == "ROUTING_UNMATCHED"
        ]["lot_normalized"].value_counts()
        log(f"  Lots unmatched: {missing_lots.index.tolist()[:10]}")

    if mismatch_count > 0:
        mismatch_emetteurs = dernier_df[
            dernier_df["routing_status"] == "ROUTING_EMETTEUR_MISMATCH"
        ]["emetteur"].value_counts()
        log(f"  Emetteur mismatches: {mismatch_emetteurs.to_dict()}")

    # ── STEP 5b: Apply exclusion config (Patch C — BEFORE discrepancy) ──
    _safe_console_print("\n  [5b] Applying exclusion config (Patch C: before discrepancy generation)...")
    exclusion_config = load_exclusion_config()
    dernier_df = exclusion_config.apply(dernier_df)
    exclusion_summary = exclusion_config.summary(dernier_df)
    if exclusion_summary.get("total_excluded", 0) > 0:
        log(f"Excluded by config rules: {exclusion_summary['total_excluded']}")
        for reason, cnt in exclusion_summary["by_reason"].items():
            log(f"    {reason}: {cnt}")
        # Mark excluded docs in versioned_df for reporting
        excluded_doc_ids = set(dernier_df[dernier_df["is_excluded_config"]]["doc_id"].tolist())
        versioned_df.loc[
            versioned_df["doc_id"].isin(excluded_doc_ids), "resolution_status"
        ] = "IGNORED"

    # Write exclusion summary debug artifact (Patch C requirement)
    exclusion_config.write_exclusion_summary(
        dernier_df,
        str(ctx.DEBUG_DIR / "exclusion_summary.xlsx"),
    )

    # Only keep non-excluded dernier_indice docs for GF output AND discrepancy
    # Patch C: exclusions applied HERE before discrepancy in step 7
    dernier_df_for_gf = dernier_df[~dernier_df["is_excluded_config"]].copy()
    log(f"Dernier docs for GF (after exclusions): {len(dernier_df_for_gf)}")
    log(f"  Emetteur mismatch excluded: {mismatch_count}")

    # ── STEP 6: Read GF Sheet Structures ─────────────────────
    _safe_console_print("\n[6/7] Reading existing GF sheet structures...")
    sheet_names_to_read = list(dernier_df_for_gf["gf_sheet_name"].dropna().unique())
    sheet_structures = read_all_gf_sheet_structures(str(ctx.GF_FILE), sheet_names_to_read)
    for sheet_name, struct in sheet_structures.items():
        log(f"  {sheet_name}: {len(struct['approvers'])} approvers")

    # Write to context
    ctx.routing_table = routing_table
    ctx.versioned_df = versioned_df
    ctx.dernier_df = dernier_df
    ctx.dernier_df_for_gf = dernier_df_for_gf
    ctx.exclusion_config = exclusion_config
    ctx.ok_count = ok_count
    ctx.ambiguous_count = ambiguous_count
    ctx.unmatched_count = unmatched_count
    ctx.unrouted = unrouted
    ctx.mismatch_count = mismatch_count
    ctx.sheet_structures = sheet_structures
