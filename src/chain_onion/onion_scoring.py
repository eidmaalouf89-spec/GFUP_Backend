"""
src/chain_onion/onion_scoring.py
----------------------------------
Step 10 — Onion Scoring Engine.

Convert onion evidence layers into operational impact scores.

This is NOT guilt scoring.
This is NOT legal blame scoring.
This is: Which active issues are harming workflow most right now?

Authoritative contract: task specification in STEP10 brief and
docs/STEP03_ONION_CONTRACT.md (layer definitions).

Public API
----------
build_onion_scores(
    onion_layers_df,
    chain_metrics_df,
    chain_register_df,
) -> tuple[pd.DataFrame, dict]   # (onion_scores_df, onion_portfolio_summary)

Layer score formula (per spec)
-------------------------------
    layer_score = severity_weight * confidence_factor * pressure_factor
                  * recency_factor * evidence_factor

    severity_weight  : LOW=10, MEDIUM=25, HIGH=50, CRITICAL=80
    confidence_factor: confidence_raw / 100
    pressure_factor  : 0.60 + (pressure_index / 100)
    evidence_factor  : 1 + min(evidence_count, 5) * 0.08  — capped at 1.40
    recency_factor   : <= 30d=1.20 | 31–90d=1.00 | 91–180d=0.80 | >180d=0.60 | null=0.75

Chain level
-----------
    total_onion_score  = sum(layer_scores for family)
    normalized_score_100 = total_onion_score / portfolio_max * 100  — capped [0, 100]

Ranking
-------
    Dense rank descending by: normalized_score_100,
    LIVE_OPERATIONAL before LEGACY before ARCHIVED,
    more evidence_layers_count, family_key stable tie-break.
    Rank 1 = most operationally impacted.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, date
from typing import Optional

import pandas as pd

_LOG = logging.getLogger(__name__)

ENGINE_VERSION = "1.0.0"

# ── Severity weights ───────────────────────────────────────────────────────────
_SEV_WEIGHT: dict[str, float] = {
    "LOW": 10.0,
    "MEDIUM": 25.0,
    "HIGH": 50.0,
    "CRITICAL": 80.0,
}

# ── Layer code → responsibility theme ─────────────────────────────────────────
_LAYER_THEME: dict[str, str] = {
    "L1_CONTRACTOR_QUALITY":         "contractor",
    "L2_SAS_GATE_FRICTION":          "sas",
    "L3_PRIMARY_CONSULTANT_DELAY":   "consultant_primary",
    "L4_SECONDARY_CONSULTANT_DELAY": "consultant_secondary",
    "L5_MOEX_ARBITRATION_DELAY":     "moex",
    "L6_DATA_REPORT_CONTRADICTION":  "contradiction",
}

# ── Theme → output column name ────────────────────────────────────────────────
_THEME_COL: dict[str, str] = {
    "contractor":           "contractor_impact_score",
    "sas":                  "sas_impact_score",
    "consultant_primary":   "consultant_primary_impact_score",
    "consultant_secondary": "consultant_secondary_impact_score",
    "moex":                 "moex_impact_score",
    "contradiction":        "contradiction_impact_score",
}

# Portfolio bucket sort order (lower = higher priority)
_BUCKET_ORDER: dict[str, int] = {
    "LIVE_OPERATIONAL":    0,
    "LEGACY_BACKLOG":      1,
    "ARCHIVED_HISTORICAL": 2,
}

# Output column contract
_OUTPUT_COLS = [
    "family_key", "numero",
    "current_state", "portfolio_bucket",
    "total_onion_score", "normalized_score_100", "action_priority_rank",
    "top_layer_code", "top_layer_name", "top_layer_score",
    "contractor_impact_score", "sas_impact_score",
    "consultant_primary_impact_score", "consultant_secondary_impact_score",
    "moex_impact_score", "contradiction_impact_score",
    "blended_confidence", "evidence_layers_count",
    "escalation_flag", "escalation_reason",
    "engine_version", "generated_at",
]


# =============================================================================
# Private helpers
# =============================================================================

def _portfolio_date(onion_layers_df: pd.DataFrame) -> Optional[date]:
    """Derive reference date as the max non-null latest_trigger_date across the portfolio."""
    col = "latest_trigger_date"
    if col not in onion_layers_df.columns:
        return None
    parsed = pd.to_datetime(onion_layers_df[col], errors="coerce").dropna()
    if parsed.empty:
        return None
    return parsed.max().date()


def _recency_factor(trigger_date_str: object, data_date: Optional[date]) -> float:
    """Recency factor based on days between trigger date and portfolio reference date."""
    if data_date is None or trigger_date_str is None:
        return 0.75
    try:
        if pd.isna(trigger_date_str):
            return 0.75
    except (TypeError, ValueError):
        pass
    try:
        td = pd.Timestamp(trigger_date_str).date()
        days_ago = (data_date - td).days
        if days_ago <= 30:
            return 1.20
        if days_ago <= 90:
            return 1.00
        if days_ago <= 180:
            return 0.80
        return 0.60
    except Exception:
        return 0.75


def _compute_layer_scores(layers: pd.DataFrame, data_date: Optional[date]) -> pd.Series:
    """Vectorised layer score computation."""
    sev_weights = layers["severity_raw"].map(_SEV_WEIGHT).fillna(10.0)

    conf_raw = pd.to_numeric(layers["confidence_raw"], errors="coerce").fillna(50.0)
    confidence_factors = (conf_raw.clip(0, 100) / 100.0)

    pressure_raw = pd.to_numeric(layers["pressure_index"], errors="coerce").fillna(0.0)
    pressure_factors = 0.60 + (pressure_raw.clip(0, 100) / 100.0)

    evidence_raw = pd.to_numeric(layers["evidence_count"], errors="coerce").fillna(1.0)
    evidence_factors = (1.0 + evidence_raw.clip(lower=0).clip(upper=5) * 0.08).clip(upper=1.40)

    recency_factors = layers["latest_trigger_date"].apply(
        lambda d: _recency_factor(d, data_date)
    )

    return sev_weights * confidence_factors * pressure_factors * recency_factors * evidence_factors


def _compute_escalation(
    normalized_score: float,
    top_sev: str,
    active_layers: int,
    portfolio_bucket: str,
    has_contradiction: bool,
) -> tuple[bool, str]:
    """
    Escalation rules (OR logic):
      - normalized_score_100 >= 85
      - top layer severity == CRITICAL
      - 3+ active onion layers AND LIVE_OPERATIONAL
      - contradiction layer + normalized_score_100 >= 70
    """
    reasons: list[str] = []

    if normalized_score >= 85:
        reasons.append("high normalized score")
    if top_sev == "CRITICAL":
        reasons.append("critical top layer")
    if active_layers >= 3 and portfolio_bucket == "LIVE_OPERATIONAL":
        reasons.append("3 active causes on live chain")
    if has_contradiction and normalized_score >= 70:
        reasons.append("high contradiction pressure")

    if reasons:
        return True, "; ".join(reasons)
    return False, ""


def _dense_rank(df: pd.DataFrame) -> pd.Series:
    """
    Dense rank (starting at 1, best = 1) by compound key:
      1. normalized_score_100 descending
      2. portfolio_bucket: LIVE_OPERATIONAL < LEGACY_BACKLOG < ARCHIVED_HISTORICAL
      3. evidence_layers_count descending
      4. family_key ascending (stable tie-break)
    """
    bucket_rank = df["portfolio_bucket"].map(_BUCKET_ORDER).fillna(3).astype(int)

    df_sort = df.assign(
        _s_score=(-df["normalized_score_100"]).round(8),
        _s_bucket=bucket_rank,
        _s_layers=(-df["evidence_layers_count"]),
        _s_fk=df["family_key"].astype(str),
    ).sort_values(["_s_score", "_s_bucket", "_s_layers", "_s_fk"])

    # Dense rank: same (_s_score, _s_bucket, _s_layers) → same rank
    rank_key = list(zip(
        df_sort["_s_score"],
        df_sort["_s_bucket"],
        df_sort["_s_layers"],
    ))
    seen: dict[tuple, int] = {}
    current_rank = 1
    for rk in rank_key:
        if rk not in seen:
            seen[rk] = current_rank
            current_rank += 1

    ranks = pd.Series(
        [seen[rk] for rk in rank_key],
        index=df_sort.index,
        name="action_priority_rank",
    )
    return ranks.reindex(df.index)


# =============================================================================
# Portfolio summary
# =============================================================================

def _empty_portfolio_summary() -> dict:
    return {
        "total_scored_chains":              0,
        "avg_score":                        0.0,
        "p90_score":                        0.0,
        "max_score":                        0.0,
        "live_avg_score":                   0.0,
        "legacy_avg_score":                 0.0,
        "archived_avg_score":               0.0,
        "contractor_total_impact":          0.0,
        "sas_total_impact":                 0.0,
        "consultant_primary_total_impact":  0.0,
        "consultant_secondary_total_impact": 0.0,
        "moex_total_impact":                0.0,
        "contradiction_total_impact":       0.0,
        "top_10_family_keys":               [],
        "escalated_chain_count":            0,
        "top_theme_by_impact":              "",
    }


def _build_portfolio_summary(df: pd.DataFrame) -> dict:
    total = len(df)
    scores = df["normalized_score_100"]

    live     = df[df["portfolio_bucket"] == "LIVE_OPERATIONAL"]
    legacy   = df[df["portfolio_bucket"] == "LEGACY_BACKLOG"]
    archived = df[df["portfolio_bucket"] == "ARCHIVED_HISTORICAL"]

    theme_totals = {
        "contractor_total_impact":           float(df["contractor_impact_score"].sum()),
        "sas_total_impact":                  float(df["sas_impact_score"].sum()),
        "consultant_primary_total_impact":   float(df["consultant_primary_impact_score"].sum()),
        "consultant_secondary_total_impact": float(df["consultant_secondary_impact_score"].sum()),
        "moex_total_impact":                 float(df["moex_impact_score"].sum()),
        "contradiction_total_impact":        float(df["contradiction_impact_score"].sum()),
    }

    top_theme_key = (
        max(theme_totals, key=lambda k: theme_totals[k])
        if any(v > 0 for v in theme_totals.values())
        else ""
    )
    top_theme_name = (
        top_theme_key.replace("_total_impact", "").replace("_", " ").title()
        if top_theme_key else ""
    )

    top_10 = df.nlargest(10, "normalized_score_100")["family_key"].tolist()

    return {
        "total_scored_chains":              total,
        "avg_score":                        float(scores.mean()) if total > 0 else 0.0,
        "p90_score":                        float(scores.quantile(0.90)) if total > 0 else 0.0,
        "max_score":                        float(scores.max()) if total > 0 else 0.0,
        "live_avg_score":                   float(live["normalized_score_100"].mean()) if not live.empty else 0.0,
        "legacy_avg_score":                 float(legacy["normalized_score_100"].mean()) if not legacy.empty else 0.0,
        "archived_avg_score":               float(archived["normalized_score_100"].mean()) if not archived.empty else 0.0,
        **theme_totals,
        "top_10_family_keys":               top_10,
        "escalated_chain_count":            int(df["escalation_flag"].sum()),
        "top_theme_by_impact":              top_theme_name,
    }


# =============================================================================
# Public API
# =============================================================================

def build_onion_scores(
    onion_layers_df: pd.DataFrame,
    chain_metrics_df: pd.DataFrame,
    chain_register_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """
    Build operational impact scores from onion evidence layers.

    Parameters
    ----------
    onion_layers_df   : output of build_onion_layers() — one row per (family_key, layer_code)
    chain_metrics_df  : output of build_chain_metrics() — one row per family_key
    chain_register_df : output of classify_chains() — one row per family_key

    Returns
    -------
    onion_scores_df         : one row per family_key
                              Families with zero onion layers are included with zero scores.
    onion_portfolio_summary : dict of aggregate KPIs
    """
    generated_at = datetime.now(timezone.utc).isoformat()

    if onion_layers_df is None or onion_layers_df.empty:
        _LOG.warning("onion_scoring: onion_layers_df is empty — returning empty scores")
        return pd.DataFrame(columns=_OUTPUT_COLS), _empty_portfolio_summary()

    # ── Build lookup tables ───────────────────────────────────────────────────
    metrics_by_fk: dict[str, dict] = {}
    if chain_metrics_df is not None and not chain_metrics_df.empty:
        for _, row in chain_metrics_df.iterrows():
            fk = str(row.get("family_key", ""))
            if fk:
                metrics_by_fk[fk] = row.to_dict()

    register_by_fk: dict[str, dict] = {}
    if chain_register_df is not None and not chain_register_df.empty:
        for _, row in chain_register_df.iterrows():
            fk = str(row.get("family_key", ""))
            if fk:
                register_by_fk[fk] = row.to_dict()

    # ── Portfolio reference date ──────────────────────────────────────────────
    data_date = _portfolio_date(onion_layers_df)
    if data_date is None:
        _LOG.warning("onion_scoring: no valid trigger dates — recency factor defaults to 0.75")

    # ── Compute per-layer scores ──────────────────────────────────────────────
    layers = onion_layers_df.copy()
    layers["family_key"] = layers["family_key"].fillna("").astype(str)

    # Ensure required columns exist
    for col, default in [
        ("confidence_raw", 50),
        ("pressure_index", 0),
        ("evidence_count", 1),
        ("severity_raw", "LOW"),
        ("layer_code", ""),
        ("layer_name", ""),
        ("latest_trigger_date", None),
        ("current_state", ""),
        ("portfolio_bucket", ""),
        ("numero", ""),
    ]:
        if col not in layers.columns:
            layers[col] = default

    layers["_layer_score"] = _compute_layer_scores(layers, data_date)
    layers["_theme"] = layers["layer_code"].map(_LAYER_THEME)

    # ── All family keys: union of onion families + register families ──────────
    onion_fks  = set(layers["family_key"].unique())
    register_fks = set(register_by_fk.keys())
    all_fks = sorted(onion_fks | register_fks)

    score_rows: list[dict] = []

    for fk in all_fks:
        fam = layers[layers["family_key"] == fk]
        m = metrics_by_fk.get(fk, {})
        r = register_by_fk.get(fk, {})

        # State context — prefer metrics_df, fallback to register, fallback to onion row
        def _first(*vals: object) -> str:
            for v in vals:
                if v and str(v).strip():
                    return str(v)
            return ""

        current_state    = _first(m.get("current_state"), r.get("current_state"),
                                   fam["current_state"].iloc[0] if not fam.empty else "")
        portfolio_bucket = _first(m.get("portfolio_bucket"), r.get("portfolio_bucket"),
                                   fam["portfolio_bucket"].iloc[0] if not fam.empty else "")
        numero           = _first(m.get("numero"), r.get("numero"),
                                   (fam["numero"].iloc[0] if "numero" in fam.columns and not fam.empty else fk))

        if fam.empty:
            score_rows.append(_zero_score_row(
                fk, numero, current_state, portfolio_bucket, generated_at
            ))
            continue

        total_score = float(fam["_layer_score"].sum())

        # Theme bucket totals
        theme_scores: dict[str, float] = {t: 0.0 for t in _THEME_COL}
        for _, lr in fam.iterrows():
            theme = lr.get("_theme")
            if theme in theme_scores:
                theme_scores[theme] += float(lr["_layer_score"])

        # Top driver
        top_idx  = fam["_layer_score"].idxmax()
        top_row  = fam.loc[top_idx]
        top_code = str(top_row.get("layer_code", ""))
        top_name = str(top_row.get("layer_name", ""))
        top_ls   = float(top_row["_layer_score"])
        top_sev  = str(top_row.get("severity_raw", "LOW"))

        # Blended confidence
        score_sum = fam["_layer_score"].sum()
        if score_sum > 0:
            conf_raw_series = pd.to_numeric(fam["confidence_raw"], errors="coerce").fillna(50.0)
            blended_conf = float((conf_raw_series * fam["_layer_score"]).sum() / score_sum)
        else:
            blended_conf = 0.0

        has_contradiction = "L6_DATA_REPORT_CONTRADICTION" in fam["layer_code"].values

        score_rows.append({
            "family_key":                        fk,
            "numero":                            numero,
            "current_state":                     current_state,
            "portfolio_bucket":                  portfolio_bucket,
            "total_onion_score":                 total_score,
            "normalized_score_100":              0.0,   # set after portfolio_max
            "action_priority_rank":              0,     # set after normalization
            "top_layer_code":                    top_code,
            "top_layer_name":                    top_name,
            "top_layer_score":                   top_ls,
            "contractor_impact_score":           theme_scores["contractor"],
            "sas_impact_score":                  theme_scores["sas"],
            "consultant_primary_impact_score":   theme_scores["consultant_primary"],
            "consultant_secondary_impact_score": theme_scores["consultant_secondary"],
            "moex_impact_score":                 theme_scores["moex"],
            "contradiction_impact_score":        theme_scores["contradiction"],
            "blended_confidence":                blended_conf,
            "evidence_layers_count":             len(fam),
            "_top_sev":                          top_sev,
            "_has_contradiction":                has_contradiction,
            "escalation_flag":                   False,
            "escalation_reason":                 "",
            "engine_version":                    ENGINE_VERSION,
            "generated_at":                      generated_at,
        })

    if not score_rows:
        return pd.DataFrame(columns=_OUTPUT_COLS), _empty_portfolio_summary()

    df = pd.DataFrame(score_rows)

    # ── Normalize against portfolio max ───────────────────────────────────────
    portfolio_max = float(df["total_onion_score"].max())
    if portfolio_max > 0:
        df["normalized_score_100"] = (
            (df["total_onion_score"] / portfolio_max * 100).clip(0, 100)
        )
    else:
        df["normalized_score_100"] = 0.0

    # ── Escalation (requires normalized_score_100) ────────────────────────────
    escalation_results = df.apply(
        lambda row: _compute_escalation(
            row["normalized_score_100"],
            row.get("_top_sev", "LOW"),
            row["evidence_layers_count"],
            row["portfolio_bucket"],
            bool(row.get("_has_contradiction", False)),
        ),
        axis=1,
        result_type="expand",
    )
    df["escalation_flag"]   = escalation_results[0]
    df["escalation_reason"] = escalation_results[1]

    # ── Action priority rank ──────────────────────────────────────────────────
    df["action_priority_rank"] = _dense_rank(df)

    # ── Drop internal columns and select output ───────────────────────────────
    _internal = ["_top_sev", "_has_contradiction"]
    df = df.drop(columns=[c for c in _internal if c in df.columns])
    out_cols = [c for c in _OUTPUT_COLS if c in df.columns]
    df = df[out_cols].reset_index(drop=True)

    # ── Portfolio summary ─────────────────────────────────────────────────────
    summary = _build_portfolio_summary(df)

    _LOG.info(
        "onion_scoring: %d families scored | portfolio_max=%.2f | escalated=%d | data_date=%s",
        len(df), portfolio_max, int(df["escalation_flag"].sum()), data_date,
    )

    return df, summary


def _zero_score_row(
    fk: str,
    numero: str,
    current_state: str,
    portfolio_bucket: str,
    generated_at: str,
) -> dict:
    return {
        "family_key":                        fk,
        "numero":                            numero,
        "current_state":                     current_state,
        "portfolio_bucket":                  portfolio_bucket,
        "total_onion_score":                 0.0,
        "normalized_score_100":              0.0,
        "action_priority_rank":              0,
        "top_layer_code":                    "",
        "top_layer_name":                    "",
        "top_layer_score":                   0.0,
        "contractor_impact_score":           0.0,
        "sas_impact_score":                  0.0,
        "consultant_primary_impact_score":   0.0,
        "consultant_secondary_impact_score": 0.0,
        "moex_impact_score":                 0.0,
        "contradiction_impact_score":        0.0,
        "blended_confidence":                0.0,
        "evidence_layers_count":             0,
        "_top_sev":                          "LOW",
        "_has_contradiction":                False,
        "escalation_flag":                   False,
        "escalation_reason":                 "",
        "engine_version":                    ENGINE_VERSION,
        "generated_at":                      generated_at,
    }
