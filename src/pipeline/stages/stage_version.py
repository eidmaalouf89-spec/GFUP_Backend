"""
stage_version — Run version engine.

Lines 452-465 of run_pipeline().
Runs the version engine to determine document versions and anomalies.
"""

from version_engine import VersionEngine
from pipeline.utils import _safe_console_print


def stage_version(ctx, log):
    """
    Run version engine to version documents.

    Context reads:
      - ctx.docs_df

    Context writes:
      - ctx.versioned_df
      - ctx.total
      - ctx.dernier_count
      - ctx.anomaly_count
      - ctx.excluded_count
    """
    # ── STEP 4: Version Engine ────────────────────────────────
    _safe_console_print("\n[4/7] Running Version Engine...")
    engine = VersionEngine(ctx.docs_df)
    versioned_df = engine.run()

    total = len(versioned_df)
    dernier_count = versioned_df["is_dernier_indice"].sum()
    anomaly_count = versioned_df["anomaly_flags"].apply(lambda x: len(x) > 0).sum()
    excluded_count = versioned_df["is_excluded_lifecycle"].sum()

    log(f"Total document versions: {total}")
    log(f"Dernier indices (latest versions): {dernier_count}")
    log(f"Documents with anomaly flags: {anomaly_count}")
    log(f"Excluded (old lifecycle): {excluded_count}")

    # Write to context
    ctx.versioned_df = versioned_df
    ctx.total = total
    ctx.dernier_count = dernier_count
    ctx.anomaly_count = anomaly_count
    ctx.excluded_count = excluded_count
