"""
Stage 8: Discrepancy computation, reconciliation, and severity classification.

Computes discrepancies, runs reconciliation engine, applies relaxation passes,
classifies severity, and writes discrepancy reports.
"""

import pandas as pd
from pipeline.compute import _determine_data_date, _compute_discrepancies
from reconciliation_engine import run_reconciliation, write_reconciliation_outputs
from domain.discrepancy import classify_discrepancy
from writer import write_discrepancy_report
from pipeline.utils import _safe_console_print


def stage_discrepancy(ctx, log):
    """
    Discrepancy computation and reconciliation stage.

    Reads from ctx:
        - dernier_df_for_gf, GF_FILE, DEBUG_DIR, exclusion_config, responses_df
        - versioned_df, GED_FILE
        - OUTPUT_DISCREPANCY, OUTPUT_DISCREPANCY_REVIEW, OUTPUT_RECONCILIATION_LOG
        - OUTPUT_RECONCILIATION_SUMMARY, OUTPUT_IGNORED

    Writes to ctx:
        - data_date, discrepancies, gf_by_sheet, recon_log
        - disc_review, disc_cosmetic, disc_excluded, disc_info
        - mid_before, mid_after, mif_before, mif_after
    """
    dernier_df_for_gf = ctx.dernier_df_for_gf
    GF_FILE = ctx.GF_FILE
    DEBUG_DIR = ctx.DEBUG_DIR
    exclusion_config = ctx.exclusion_config
    responses_df = ctx.responses_df
    versioned_df = ctx.versioned_df
    GED_FILE = ctx.GED_FILE

    OUTPUT_DISCREPANCY = ctx.OUTPUT_DISCREPANCY
    OUTPUT_DISCREPANCY_REVIEW = ctx.OUTPUT_DISCREPANCY_REVIEW
    OUTPUT_RECONCILIATION_LOG = ctx.OUTPUT_RECONCILIATION_LOG
    OUTPUT_RECONCILIATION_SUMMARY = ctx.OUTPUT_RECONCILIATION_SUMMARY
    OUTPUT_IGNORED = ctx.OUTPUT_IGNORED

    # ── Discrepancy computation (Patch B+C+D+E) ───────────────
    # Patch C: only dernier_df_for_gf is passed — exclusions already applied
    # Patch B: normalization happens inside _compute_discrepancies
    # Patch E: responses_df and data_date for SAS-based MISSING subtypes
    data_date = _determine_data_date(str(GED_FILE))
    log(f"Data reference date (from GED file mtime): {data_date}")
    log("Computing discrepancies (Patch B+C+E: normalized + SAS subtypes)...")
    discrepancies, gf_by_sheet = _compute_discrepancies(
        dernier_df_for_gf,
        str(GF_FILE),
        debug_dir=str(DEBUG_DIR),
        excluded_sheets=exclusion_config.excluded_sheets,
        sheet_year_filters=exclusion_config.sheet_year_filters,
        responses_df=responses_df,
        data_date=data_date,
    )

    # ── Patch F: Reconciliation engine — runs before severity classification ──
    # Build dernier_df_all: ALL GED dernier docs (before exclusions/routing filter)
    # This lets the reconciliation engine find docs that were unrouted or excluded
    dernier_df_all = versioned_df[versioned_df["is_dernier_indice"] == True].copy()

    log("Running reconciliation engine (Patch F)...")
    mid_before = sum(1 for d in discrepancies if d.get("flag_type") in (
        "MISSING_IN_GED_TRUE", "MISSING_IN_GED"))
    mif_before = sum(1 for d in discrepancies if d.get("flag_type") in (
        "MISSING_IN_GF_TRUE", "MISSING_IN_GF"))
    log(f"  Before reconciliation: MIG_TRUE={mid_before}, MIF_TRUE={mif_before}")

    discrepancies, recon_log = run_reconciliation(
        discrepancies=discrepancies,
        dernier_df_all=dernier_df_all,
        gf_by_sheet=gf_by_sheet,
        responses_df=responses_df,
    )

    mid_after = sum(1 for d in discrepancies if d.get("flag_type") in (
        "MISSING_IN_GED_TRUE", "MISSING_IN_GED"))
    mif_after = sum(1 for d in discrepancies if d.get("flag_type") in (
        "MISSING_IN_GF_TRUE", "MISSING_IN_GF"))
    log(f"  After  reconciliation: MIG_TRUE={mid_after} (−{mid_before - mid_after}), "
        f"MIF_TRUE={mif_after} (−{mif_before - mif_after})")
    log(f"  Reconciliation events logged: {len(recon_log)}")

    log("Writing RECONCILIATION_LOG.xlsx...")
    write_reconciliation_outputs(
        recon_log,
        str(OUTPUT_RECONCILIATION_LOG),
        str(OUTPUT_RECONCILIATION_SUMMARY),
    )
    log(f"  → {OUTPUT_RECONCILIATION_LOG}")
    log(f"  → debug/reconciliation_summary.xlsx")

    # ── Patch G-C: TITRE_MISMATCH relaxation ─────────────────────────────────
    # Identity is already confirmed (same sheet/numero/indice) — title alone
    # is not a blocking discrepancy.  Keep only truly-foreign-document cases.
    titre_relaxed = 0
    for rec in discrepancies:
        if rec.get("flag_type") != "TITRE_MISMATCH":
            continue
        sim = float(rec.get("title_similarity") or 0)
        # Keep REVIEW_REQUIRED only when titles suggest completely different docs
        # (sim < 0.30 — very low overlap, possibly wrong document filed under same numero)
        if sim >= 0.30:
            rec["flag_type"] = "TITRE_VARIANT_ACCEPTED"
            rec["reconciliation_note"] = (
                f"Title variant accepted (sim={sim:.2f}): "
                "numero+indice+emetteur all aligned; title difference is cosmetic"
            )
            titre_relaxed += 1
    log(f"  Patch G-C: TITRE_MISMATCH relaxed → TITRE_VARIANT_ACCEPTED: {titre_relaxed}")

    # ── Patch G-D: INDICE_MISMATCH relaxation ────────────────────────────────
    # If the GED and GF dates are within 7 days, the document identity is clear.
    # Use GED indice for reconstruction; downgrade to COSMETIC.
    #
    # NOTE: title_sim is NOT required here. INDICE_MISMATCH already guarantees
    # an exact numero match; GF rows for different indices often have empty titles
    # (titre="" → title_sim=0.0). Since numero is exact, date proximity alone is
    # sufficient to confirm identity and accept the indice variant.
    indice_accepted = 0
    for rec in discrepancies:
        if rec.get("flag_type") != "INDICE_MISMATCH":
            continue
        diff = rec.get("date_diff_days")
        title_sim_ind = float(rec.get("title_similarity") or 0)
        # Accept if: date within 7 days (numero already matched exactly)
        if diff is not None and diff <= 7:
            rec["flag_type"] = "INDICE_VARIANT_ACCEPTED_BY_GED"
            rec["reconciliation_note"] = (
                f"Indice variant accepted: date_diff={diff}d"
                + (f", title_sim={title_sim_ind:.2f}" if title_sim_ind > 0 else ", title_sim=n/a (GF row has no titre)")
                + f". Exact numero match; GED indice '{rec.get('ged_value')}' wins over "
                f"GF indice '{rec.get('gf_value')}'."
            )
            indice_accepted += 1
    log(f"  Patch G-D: INDICE_MISMATCH accepted → INDICE_VARIANT_ACCEPTED_BY_GED: {indice_accepted}")

    # ── Part H-1: BENTIN legacy exception pass ───────────────────────────────
    # The BENTIN sheet (LOT 31 à 34-IN-BX-CFO-BENTIN) contains legacy
    # inconsistencies from an old contractor batch that predates the current
    # GF structure.  All MISSING_IN_GF discrepancies on this sheet are excluded.
    BENTIN_SHEET = "LOT 31 à 34-IN-BX-CFO-BENTIN"
    BENTIN_TARGET_TYPES = {
        "MISSING_IN_GF_TRUE",
        "MISSING_IN_GF_AMBIGUOUS_TITLE_MATCH",
        "INDICE_MISMATCH",          # now INFO globally, but explicit BENTIN trace
        "DATE_MISMATCH",            # now INFO globally, but explicit BENTIN trace
    }
    bentin_count = 0
    for rec in discrepancies:
        if (rec.get("sheet_name") == BENTIN_SHEET
                and rec.get("flag_type") in BENTIN_TARGET_TYPES):
            rec["flag_type"] = "BENTIN_LEGACY_EXCEPTION"
            rec["reconciliation_note"] = (
                "BENTIN legacy: excluded from review queue. "
                "This sheet contains pre-2026 contractor inconsistencies."
            )
            bentin_count += 1
    log(f"  Part H-1: BENTIN legacy exceptions flagged: {bentin_count}")

    # ── Part H-2: Global title reconciliation — promote AMBIGUOUS to INFO ────
    # MISSING_IN_GED_AMBIGUOUS_TITLE_MATCH and MISSING_IN_GF_AMBIGUOUS_TITLE_MATCH
    # were already matched by the reconciliation engine at title_sim >= TITLE_SIM_PROBABLE
    # (0.65).  The "ambiguous" label means the score was [0.65, 0.80).
    # These are NOT unresolved — they have a probable match.
    # Per the final pass rules, they become REVIEW_REQUIRED but with low urgency.
    # No reclassification here; they remain REVIEW_REQUIRED as the spec requires.
    # (Kept as a documented no-op for clarity.)

    # ── Severity classification (must come after all flag_type mutations) ──
    for rec in discrepancies:
        rec["severity"] = classify_discrepancy(rec)

    disc_review = [d for d in discrepancies if d["severity"] == "REVIEW_REQUIRED"]
    disc_cosmetic = [d for d in discrepancies if d["severity"] == "COSMETIC"]
    disc_excluded = [d for d in discrepancies if d["severity"] == "EXCLUDED"]
    disc_info = [d for d in discrepancies if d["severity"] == "INFO"]

    log(f"Discrepancies total: {len(discrepancies)}")
    log(f"  REVIEW_REQUIRED:  {len(disc_review)}")
    log(f"  COSMETIC:         {len(disc_cosmetic)}")
    log(f"  EXCLUDED:         {len(disc_excluded)}")
    log(f"  INFO:             {len(disc_info)}")
    # Final counts for Patch G validation
    mid_final = sum(1 for d in discrepancies if d.get("flag_type") in ("MISSING_IN_GED_TRUE","MISSING_IN_GED"))
    mif_final = sum(1 for d in discrepancies if d.get("flag_type") in ("MISSING_IN_GF_TRUE","MISSING_IN_GF"))
    log(f"  MISSING_IN_GED_TRUE remaining: {mid_final}")
    log(f"  MISSING_IN_GF_TRUE remaining:  {mif_final}")
    titre_remaining = sum(1 for d in discrepancies if d.get("flag_type") == "TITRE_MISMATCH")
    indice_remaining = sum(1 for d in discrepancies if d.get("flag_type") == "INDICE_MISMATCH")
    log(f"  TITRE_MISMATCH remaining (blocked):  {titre_remaining}")
    log(f"  INDICE_MISMATCH remaining (blocked): {indice_remaining}")

    if discrepancies:
        disc_df = pd.DataFrame(discrepancies)
        counts = disc_df["flag_type"].value_counts()
        log("Breakdown by flag_type:")
        for ftype, cnt in counts.items():
            log(f"    {ftype}: {cnt}")

    log("Writing DISCREPANCY_REPORT.xlsx (all, with severity)...")
    write_discrepancy_report(str(OUTPUT_DISCREPANCY), discrepancies)
    log(f"  → {OUTPUT_DISCREPANCY}")

    log("Writing DISCREPANCY_REVIEW_REQUIRED.xlsx...")
    write_discrepancy_report(str(OUTPUT_DISCREPANCY_REVIEW), disc_review,
                             title_suffix=" — REVIEW REQUIRED ONLY")
    log(f"  → {OUTPUT_DISCREPANCY_REVIEW}")

    # ── Part H-1: Append BENTIN_LEGACY_EXCEPTION to IGNORED_ITEMS_LOG ────────
    bentin_excluded = [d for d in discrepancies if d.get("flag_type") == "BENTIN_LEGACY_EXCEPTION"]
    if bentin_excluded:
        bentin_df = pd.DataFrame([{
            "numero":           d.get("numero"),
            "indice":           d.get("indice"),
            "sheet":            d.get("sheet_name"),
            "document_code":    d.get("document_code"),
            "exclusion_reason": "BENTIN_LEGACY_EXCEPTION",
            "reconciliation_note": d.get("reconciliation_note", ""),
            "anomaly_flags":    ["BENTIN_LEGACY"],
        } for d in bentin_excluded])
        # Reload existing ignored log and append
        try:
            existing_ignored = pd.read_excel(str(OUTPUT_IGNORED))
            combined_with_bentin = pd.concat([existing_ignored, bentin_df], ignore_index=True)
        except Exception:
            combined_with_bentin = bentin_df
        combined_with_bentin.to_excel(str(OUTPUT_IGNORED), index=False)
        log(f"  Part H-1: {len(bentin_excluded)} BENTIN exceptions appended to IGNORED_ITEMS_LOG")

    # Write to ctx
    ctx.data_date = data_date
    ctx.discrepancies = discrepancies
    ctx.gf_by_sheet = gf_by_sheet
    ctx.recon_log = recon_log
    ctx.disc_review = disc_review
    ctx.disc_cosmetic = disc_cosmetic
    ctx.disc_excluded = disc_excluded
    ctx.disc_info = disc_info
    ctx.mid_before = mid_before
    ctx.mid_after = mid_after
    ctx.mif_before = mif_before
    ctx.mif_after = mif_after
