"""
latest_chain_view — Canonical chain-truth views for operational reporting.

Two public functions
====================

build_latest_chain_view(base_dir, docs_df=None) -> pd.DataFrame
    Path-based. Reads CHAIN_REGISTER.csv + CHAIN_VERSIONS.csv from
    output/chain_onion/ and returns one row per chain (family_key).
    Used by data_loader to populate ctx.latest_chain_df during context
    construction. Optional docs_df kwarg enables sub-second emetteur/
    titre enrichment from already-loaded data instead of re-parsing
    FLAT_GED.xlsx (~17s).

latest_enriched_view(ctx) -> pd.DataFrame
    Context-based. Returns ctx.dernier_df filtered to actual latest-
    chain rows via intersection with ctx.latest_chain_df.(numero,
    latest_indice). Preserves all _precompute_focus_columns
    enrichments (_visa_global, _focus_owner_tier, _focus_priority,
    etc.) because the rows are inherited directly from dernier_df.

Use ctx.latest_chain_df when
----------------------------
- You only need chain identity / register metadata
  (family_key, numero, latest_indice, current_state,
   portfolio_bucket, stale_days, last_real_activity_date, ...).

Use latest_enriched_view(ctx) when
----------------------------------
- You need precomputed columns added by the focus-ownership /
  focus-precompute mutators (_visa_global, _focus_owner_tier,
  _focus_priority, _days_since_last_activity, etc.).
- This is the canonical view for operational reporting modules
  (aggregator, consultant_fiche, contractor_fiche, focus_filter,
  drilldown_builder, chain_timeline_attribution, counter_attack_export,
  document_command_center.compute_dcc_tags_bulk).

Use ctx.dernier_df DIRECTLY only when
-------------------------------------
- Showing revision history across all indices.
- Full-corpus search where all indices are legitimate hits.
- The mutators _precompute_focus_columns / compute_focus_ownership,
  which mutate dernier_df in place by design.

NEVER use ctx.dernier_df DIRECTLY for
-------------------------------------
- Operational counts / KPIs / aggregations.
- DCC operational tags (compute_dcc_tags_bulk).
- Action MOEX bucket assignment.
- Dormant REF / SAS REF detection.
- Per-consultant / per-contractor stats.

Decision-3 caveat
=================
_apply_sas_filter_flat() in src/pipeline/stages/stage_read_flat.py
drops pre-2026 PENDING_LATE SAS docs from dernier_df, while
CHAIN_REGISTER retains them. This creates a permanent N~=1
discrepancy between len(ctx.latest_chain_df) (chain count) and
len(latest_enriched_view(ctx)) (chain count minus Decision-3
victims). On the current dataset: 2,554 chains vs 2,553 enriched
rows. By design, not a bug. See context/11_TOOLING_HAZARDS.md H-9.

Migration history
=================
Steps 2-7 (2026-05-11) migrated all HIGH/MEDIUM-risk operational
consumers from ctx.dernier_df to latest_enriched_view(ctx). See
reports/STEP1_DERNIER_DF_INVENTORY.md for the inventory.
"""
import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

_REGISTER_COLS = [
    "family_key",
    "numero",
    "latest_indice",
    "latest_version_key",
    "current_state",
    "portfolio_bucket",
    "stale_days",
    "last_real_activity_date",
    "latest_submission_date",
    "current_blocking_actor_count",
    "waiting_primary_flag",
    "waiting_secondary_flag",
]

_VERSIONS_COLS = [
    "version_key",
    "indice",
    "latest_response_date",
    "requires_new_cycle_flag",
]

_IDENTITY_DTYPES = {
    "family_key": str,
    "numero": str,
    "latest_version_key": str,
    "latest_indice": str,
}

_VERSIONS_IDENTITY_DTYPES = {
    "family_key": str,
    "version_key": str,
    "numero": str,
    "indice": str,
}


def build_latest_chain_view(
    base_dir: Union[Path, str] = ".",
    docs_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Build the canonical latest-chain view from Chain+Onion artifacts.

    Returns one row per chain (family_key), keyed on CHAIN_REGISTER.latest_version_key.

    Args:
        base_dir: repo root. Artifacts are read from
                  {base_dir}/output/chain_onion/CHAIN_REGISTER.csv
                  {base_dir}/output/chain_onion/CHAIN_VERSIONS.csv
        docs_df:  optional pre-loaded docs DataFrame (from data_loader).
                  When provided, enrichment uses docs_df instead of
                  parsing FLAT_GED.xlsx (saves ~17s).

    Returns:
        pd.DataFrame with the required columns.

    Raises:
        FileNotFoundError: if either CHAIN_REGISTER.csv or CHAIN_VERSIONS.csv
                           is missing.
        ValueError: if a data integrity invariant fails.
    """
    base = Path(base_dir)
    register_path = base / "output" / "chain_onion" / "CHAIN_REGISTER.csv"
    versions_path = base / "output" / "chain_onion" / "CHAIN_VERSIONS.csv"

    if not register_path.exists():
        raise FileNotFoundError(f"CHAIN_REGISTER.csv not found at {register_path}")
    if not versions_path.exists():
        raise FileNotFoundError(f"CHAIN_VERSIONS.csv not found at {versions_path}")

    register_df = pd.read_csv(register_path, dtype=_IDENTITY_DTYPES)
    versions_df = pd.read_csv(versions_path, dtype=_VERSIONS_IDENTITY_DTYPES)

    # Select only the columns we need from each artifact
    reg = register_df[_REGISTER_COLS].copy()
    ver = versions_df[["family_key"] + _VERSIONS_COLS].copy()

    # Join: CHAIN_REGISTER.latest_version_key == CHAIN_VERSIONS.version_key
    #        AND CHAIN_REGISTER.family_key == CHAIN_VERSIONS.family_key
    df = reg.merge(
        ver,
        left_on=["family_key", "latest_version_key"],
        right_on=["family_key", "version_key"],
        how="left",
        indicator=True,
    )

    # --- Invariant 1: no row lost in join ---
    unmatched = df[df["_merge"] == "left_only"]
    if len(unmatched) > 0:
        bad_keys = unmatched["family_key"].tolist()
        raise ValueError(
            f"Invariant 1 FAILED: {len(unmatched)} CHAIN_REGISTER rows have no "
            f"matching CHAIN_VERSIONS row on (family_key, latest_version_key). "
            f"First 10 offending family_keys: {bad_keys[:10]}"
        )
    df = df.drop(columns=["_merge"])

    assert len(df) == len(register_df), (
        f"Invariant 1 FAILED: row count mismatch after join. "
        f"Expected {len(register_df)}, got {len(df)}."
    )

    # --- Invariant 2: family_key is unique ---
    if not df["family_key"].is_unique:
        dupes = df[df["family_key"].duplicated(keep=False)]["family_key"].unique().tolist()
        raise ValueError(
            f"Invariant 2 FAILED: family_key is not unique. "
            f"Duplicated family_keys ({len(dupes)}): {dupes[:10]}"
        )

    # --- Invariant 3: numero is unique ---
    if not df["numero"].is_unique:
        dupes = df[df["numero"].duplicated(keep=False)]["numero"].unique().tolist()
        raise ValueError(
            f"Invariant 3 FAILED: numero is not unique. "
            f"Duplicated numeros ({len(dupes)}): {dupes[:10]}"
        )

    # --- Invariant 4: version_key == latest_version_key ---
    if not df["version_key"].equals(df["latest_version_key"]):
        mismatch_count = (df["version_key"] != df["latest_version_key"]).sum()
        raise ValueError(
            f"Invariant 4 FAILED: version_key != latest_version_key "
            f"for {mismatch_count} rows."
        )

    # --- Invariant 5: indice == latest_indice ---
    if not df["indice"].equals(df["latest_indice"]):
        mismatch_count = (df["indice"] != df["latest_indice"]).sum()
        raise ValueError(
            f"Invariant 5 FAILED: indice != latest_indice "
            f"for {mismatch_count} rows."
        )

    # Optional enrichment: emetteur + titre from docs_df or FLAT_GED
    enrichment_omitted = []
    _enrichment_done = False

    if docs_df is not None:
        _enrich_required = {"numero", "indice", "emetteur", "libelle_du_document"}
        missing_cols = _enrich_required - set(docs_df.columns)
        if missing_cols:
            logger.warning(
                "docs_df missing columns %s — falling back to FLAT_GED.xlsx",
                missing_cols,
            )
        else:
            lookup = docs_df[["numero", "indice", "emetteur", "libelle_du_document"]].copy()
            lookup["numero"] = lookup["numero"].astype(str).str.strip()
            lookup["indice"] = lookup["indice"].astype(str).str.strip()
            lookup = lookup.rename(columns={"libelle_du_document": "titre"})

            dup_check = lookup.groupby(["numero", "indice"]).size()
            multi = dup_check[dup_check > 1]
            if len(multi) > 0:
                enrichment_omitted.append(
                    f"emetteur/titre: {len(multi)} (numero, indice) pairs have "
                    f"multiple rows in docs_df — ambiguous; omitted"
                )
                logger.warning(
                    "docs_df enrichment skipped: %d ambiguous (numero, indice) pairs",
                    len(multi),
                )
            else:
                lookup = lookup.drop_duplicates(subset=["numero", "indice"])
                df = df.merge(
                    lookup,
                    left_on=["numero", "latest_indice"],
                    right_on=["numero", "indice"],
                    how="left",
                    suffixes=("", "_docs"),
                )
                if "indice_docs" in df.columns:
                    df = df.drop(columns=["indice_docs"])
            _enrichment_done = True

    if not _enrichment_done:
        flat_ged_path = base / "output" / "intermediate" / "FLAT_GED.xlsx"
        if flat_ged_path.exists():
            try:
                ops_df = pd.read_excel(
                    flat_ged_path,
                    sheet_name="GED_OPERATIONS",
                    dtype={"numero": str, "indice": str},
                )
                open_docs = ops_df[ops_df["step_type"] == "OPEN_DOC"].copy()

                dup_check = open_docs.groupby(["numero", "indice"]).size()
                multi = dup_check[dup_check > 1]
                if len(multi) > 0:
                    enrichment_omitted.append(
                        f"emetteur/titre: {len(multi)} (numero, indice) pairs have "
                        f"multiple OPEN_DOC rows — ambiguous; omitted"
                    )
                    logger.warning(
                        "FLAT_GED enrichment skipped: %d ambiguous (numero, indice) pairs",
                        len(multi),
                    )
                else:
                    has_emetteur = "emetteur" in open_docs.columns
                    has_titre = "titre" in open_docs.columns
                    if not has_emetteur:
                        enrichment_omitted.append("emetteur: column not found in GED_OPERATIONS")
                    if not has_titre:
                        enrichment_omitted.append("titre: column not found in GED_OPERATIONS")

                    if has_emetteur or has_titre:
                        lookup_cols = ["numero", "indice"]
                        if has_emetteur:
                            lookup_cols.append("emetteur")
                        if has_titre:
                            lookup_cols.append("titre")
                        lookup = open_docs[lookup_cols].copy()
                        lookup["numero"] = lookup["numero"].astype(str).str.strip()
                        lookup["indice"] = lookup["indice"].astype(str).str.strip()

                        df = df.merge(
                            lookup,
                            left_on=["numero", "latest_indice"],
                            right_on=["numero", "indice"],
                            how="left",
                            suffixes=("", "_flat"),
                        )
                        if "indice_flat" in df.columns:
                            df = df.drop(columns=["indice_flat"])
            except Exception as exc:
                enrichment_omitted.append(f"emetteur/titre: FLAT_GED read failed — {exc}")
                logger.warning("FLAT_GED enrichment failed: %s", exc)
        else:
            enrichment_omitted.append("emetteur/titre: FLAT_GED.xlsx not found")

    if enrichment_omitted:
        for note in enrichment_omitted:
            logger.info("Enrichment omitted: %s", note)

    # Final column order: required columns first, then optional enrichment
    final_cols = list(_REGISTER_COLS) + list(_VERSIONS_COLS)
    for col in ["emetteur", "titre"]:
        if col in df.columns:
            final_cols.append(col)

    df = df[final_cols].reset_index(drop=True)
    return df


def latest_enriched_view(ctx) -> pd.DataFrame:
    """Return ctx.dernier_df filtered to actual latest-chain rows.

    Uses ctx.latest_chain_df.(numero, latest_indice) as the canonical
    row-set; PRESERVES all _precompute_focus_columns enrichments on
    ctx.dernier_df (_visa_global, _focus_owner_tier, _focus_priority,
    etc.) by inheriting column values via row intersection.

    Falls back to ctx.dernier_df unchanged when ctx.latest_chain_df is
    None or empty (legacy mode without Chain+Onion artifacts), so legacy
    projects keep working with the previous semantics.

    Step 5b numero-format hygiene applies: this function does NOT
    transform the numero column; the canonical zero-padded form from
    dernier_df is preserved.
    """
    if ctx.dernier_df is None or ctx.dernier_df.empty:
        return pd.DataFrame()
    lc = getattr(ctx, "latest_chain_df", None)
    if lc is None or lc.empty:
        return ctx.dernier_df
    lc_keys = set(zip(
        lc["numero"].astype(str).str.strip(),
        lc["latest_indice"].astype(str).str.strip(),
    ))
    dd = ctx.dernier_df
    dd_num = dd["numero"].astype(str).str.strip()
    dd_ind = dd["indice"].astype(str).str.strip()
    mask = [k in lc_keys for k in zip(dd_num, dd_ind)]
    return dd[mask].copy()
