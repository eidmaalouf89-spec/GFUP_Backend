"""
stage_normalize — Normalize data and apply SAS filter.

Lines 429-450 of run_pipeline().
Normalizes documents and responses, applies SAS filter for old unresolved reminders.
"""

from normalize import normalize_docs, normalize_responses
from domain.sas_helpers import _apply_sas_filter
from pipeline.utils import _safe_console_print


def stage_normalize(ctx, log):
    """
    Normalize documents and responses, apply SAS filter.

    Context reads:
      - ctx.docs_df
      - ctx.responses_df
      - ctx.mapping

    Context writes:
      - ctx.docs_df (mutated)
      - ctx.responses_df (mutated)
      - ctx.sas_filtered_df
    """
    # ── STEP 3: Normalize ─────────────────────────────────────
    _safe_console_print("\n[3/7] Normalizing data...")
    docs_df = normalize_docs(ctx.docs_df, ctx.mapping)
    responses_df = normalize_responses(ctx.responses_df, ctx.mapping)

    # Filter out exception approvers
    non_exception_responses = responses_df[~responses_df["is_exception_approver"]]
    log(f"Non-exception responses: {len(non_exception_responses)}")

    # ── STEP 3b: SAS FILTER — RAPPEL_EN_ATTENTE + pre-2026 ───
    # Business rule: If 0-SAS approver has an unresolved reminder ("Rappel")
    # AND the document was created before 2026 → INVALID, remove entirely.
    # These are old unresolved SAS visa requests that are stale/superseded.
    _safe_console_print("\n  [3b] Applying SAS filter (RAPPEL_EN_ATTENTE + pre-2026)...")
    docs_df, responses_df, sas_filtered_df = _apply_sas_filter(docs_df, responses_df)
    sas_count = len(sas_filtered_df)
    if sas_count:
        log(f"SAS filter removed: {sas_count} docs (SAS_OLD_UNRESOLVED)")
        emetteur_counts = sas_filtered_df["emetteur"].value_counts()
        log(f"  By emetteur: {emetteur_counts.to_dict()}")
    else:
        log("SAS filter: no docs removed")

    # Write to context
    ctx.docs_df = docs_df
    ctx.responses_df = responses_df
    ctx.sas_filtered_df = sas_filtered_df
