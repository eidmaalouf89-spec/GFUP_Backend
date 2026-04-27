"""
src/chain_onion/narrative_engine.py
-------------------------------------
Step 11 — Narrative Engine.

Convert deterministic chain + onion outputs into short, neutral,
management-grade summaries. Template-driven only. No AI freeform writing.
No blame text. No legal commentary. No speculation.

Authoritative contract: STEP11 task brief.

Public API
----------
build_chain_narratives(
    chain_register_df,
    chain_metrics_df,
    onion_layers_df,
    onion_scores_df,
) -> pd.DataFrame  # chain_narratives_df

Output: one row per family_key. Zero-score families included.

Output column contract
----------------------
    family_key, numero,
    current_state, portfolio_bucket,
    executive_summary,
    primary_driver_text, secondary_driver_text, operational_note, recommended_focus,
    urgency_label, confidence_label,
    normalized_score_100, action_priority_rank,
    engine_version, generated_at
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

_LOG = logging.getLogger(__name__)

ENGINE_VERSION = "1.0.0"

# ── Urgency thresholds ────────────────────────────────────────────────────────
def _urgency_label(score: float) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "NONE"


# ── Confidence thresholds ─────────────────────────────────────────────────────
def _confidence_label(blended: float, has_layers: bool) -> str:
    if not has_layers:
        return "NONE"
    if blended >= 85:
        return "HIGH"
    if blended >= 65:
        return "MEDIUM"
    return "LOW"


# ── Executive summary templates ───────────────────────────────────────────────
def _executive_summary(portfolio_bucket: str, score: float) -> str:
    b = (portfolio_bucket or "").upper()
    if b == "LIVE_OPERATIONAL":
        if score >= 70:
            return "Active chain with elevated operational pressure requiring near-term attention."
        if score >= 40:
            return "Active chain showing moderate pressure and follow-up need."
        return "Active chain currently under controlled pressure."
    if b == "LEGACY_BACKLOG":
        return "Legacy open chain with limited current operational impact."
    if b == "ARCHIVED_HISTORICAL":
        return "Historical closed chain with no current action required."
    # Fallback for unexpected bucket values
    return "Chain status requires review."


# ── Primary driver templates (by top_layer_code) ─────────────────────────────
_PRIMARY_DRIVER: dict[str, str] = {
    "L1_CONTRACTOR_QUALITY":
        "Repeated rework or rejection cycles are the main efficiency drag.",
    "L2_SAS_GATE_FRICTION":
        "SAS gate activity is the main contributor to current delay pressure.",
    "L3_PRIMARY_CONSULTANT_DELAY":
        "Primary consultant response timing is the leading active constraint.",
    "L4_SECONDARY_CONSULTANT_DELAY":
        "Secondary consultant response timing is the leading active constraint.",
    "L5_MOEX_ARBITRATION_DELAY":
        "MOEX arbitration or final response timing is the leading constraint.",
    "L6_DATA_REPORT_CONTRADICTION":
        "Data or report contradictions are reducing workflow clarity.",
}
_PRIMARY_DRIVER_NONE = "No significant active friction signals detected."


def _primary_driver_text(top_layer_code: str | None) -> str:
    if not top_layer_code:
        return _PRIMARY_DRIVER_NONE
    return _PRIMARY_DRIVER.get(top_layer_code, _PRIMARY_DRIVER_NONE)


# ── Secondary driver templates (reuse same layer map) ────────────────────────
_SECONDARY_DRIVER_NONE = "No secondary material driver identified."


def _secondary_driver_text(second_layer_code: str | None) -> str:
    if not second_layer_code:
        return _SECONDARY_DRIVER_NONE
    return _PRIMARY_DRIVER.get(second_layer_code, _SECONDARY_DRIVER_NONE)


# ── Operational note templates (by current_state + stale_days) ───────────────
_STATE_NOTE: dict[str, str] = {
    "WAITING_CORRECTED_INDICE":
        "Awaiting corrected resubmission to restart chain progress.",
    "OPEN_WAITING_PRIMARY_CONSULTANT":
        "Current blocker sits with primary consultant review flow.",
    "OPEN_WAITING_SECONDARY_CONSULTANT":
        "Current blocker sits with secondary consultant review flow.",
    "OPEN_WAITING_MOEX":
        "Current blocker sits with MOEX finalization flow.",
    "OPEN_WAITING_MIXED_CONSULTANTS":
        "Current blocker sits with multiple consultant review flows.",
    "CHRONIC_REF_CHAIN":
        "Chain shows repeated rejection history and recycling risk.",
    "VOID_CHAIN":
        "Chain has no valid active version and may require administrative review.",
    "DEAD_AT_SAS_A":
        "Chain was rejected at initial SAS gate with no subsequent resubmission.",
    "ABANDONED_CHAIN":
        "Chain has had no recorded activity for an extended period.",
    "CLOSED_VAO":
        "Chain is closed with full approval — no operational action required.",
    "CLOSED_VSO":
        "Chain is closed with VSO approval — no operational action required.",
    "UNKNOWN_CHAIN_STATE":
        "Chain state could not be determined from available data.",
}
_STALE_LEGACY_NOTE = "Open status appears administrative rather than operational."
_OPERATIONAL_NOTE_NONE = "No exceptional operational note."


def _operational_note(current_state: str | None, stale_days, portfolio_bucket: str) -> str:
    state = (current_state or "").upper()
    bucket = (portfolio_bucket or "").upper()

    # Legacy + stale check takes precedence for LEGACY bucket
    if bucket == "LEGACY_BACKLOG":
        try:
            if stale_days is not None and float(stale_days) > 180:
                return _STALE_LEGACY_NOTE
        except (TypeError, ValueError):
            pass

    if state in _STATE_NOTE:
        return _STATE_NOTE[state]
    return _OPERATIONAL_NOTE_NONE


# ── Recommended focus templates ───────────────────────────────────────────────
def _recommended_focus(
    portfolio_bucket: str,
    current_state: str | None,
    score: float,
) -> str:
    bucket = (portfolio_bucket or "").upper()
    state = (current_state or "").upper()

    if bucket == "ARCHIVED_HISTORICAL":
        return "No immediate action required."

    if bucket == "LEGACY_BACKLOG":
        return "Review whether administrative closure or archive is appropriate."

    # LIVE_OPERATIONAL logic — high score takes priority over state-specific routing
    if score >= 60:
        return "Prioritize direct unblocking actions and response coordination."

    if state == "WAITING_CORRECTED_INDICE":
        return "Clarify resubmission timing and completeness requirements."

    if state in ("OPEN_WAITING_PRIMARY_CONSULTANT", "OPEN_WAITING_SECONDARY_CONSULTANT",
                 "OPEN_WAITING_MIXED_CONSULTANTS"):
        return "Confirm review owner, due date, and pending comments."

    return "Monitor progress and follow up at next scheduled review cycle."


# ── Severity rank for sorting layers ─────────────────────────────────────────
_SEV_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _second_layer_code(
    family_key: str,
    top_layer_code: str | None,
    layers_by_family: dict[str, pd.DataFrame],
) -> str | None:
    """Return the layer code with the second-highest severity for a family."""
    fam_layers = layers_by_family.get(family_key)
    if fam_layers is None or fam_layers.empty:
        return None

    others = fam_layers[fam_layers["layer_code"] != top_layer_code].copy()
    if others.empty:
        return None

    others["_sev_rank"] = others["severity_raw"].map(_SEV_RANK).fillna(0)
    others = others.sort_values(
        ["_sev_rank", "evidence_count"],
        ascending=[False, False],
    )
    return others.iloc[0]["layer_code"]


# ── Output column contract ────────────────────────────────────────────────────
_OUTPUT_COLS = [
    "family_key", "numero",
    "current_state", "portfolio_bucket",
    "executive_summary",
    "primary_driver_text", "secondary_driver_text",
    "operational_note", "recommended_focus",
    "urgency_label", "confidence_label",
    "normalized_score_100", "action_priority_rank",
    "engine_version", "generated_at",
]


# =============================================================================
# Public API
# =============================================================================

def build_chain_narratives(
    chain_register_df: pd.DataFrame,
    chain_metrics_df: pd.DataFrame,
    onion_layers_df: pd.DataFrame,
    onion_scores_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build one narrative row per family_key.

    All families from chain_register_df are included — even zero-score families.
    Text is deterministic: same inputs always produce the same outputs.
    No AI inference. No banned vocabulary.

    Returns
    -------
    pd.DataFrame with columns defined in _OUTPUT_COLS.
    """
    now_str = datetime.now(tz=timezone.utc).isoformat()

    # ── Build lookup dicts from scores ────────────────────────────────────────
    scores_by_fk: dict[str, dict] = {}
    if not onion_scores_df.empty:
        for _, row in onion_scores_df.iterrows():
            fk = str(row.get("family_key", ""))
            if fk:
                scores_by_fk[fk] = row.to_dict()

    # ── Build layer index for secondary driver lookup ─────────────────────────
    layers_by_family: dict[str, pd.DataFrame] = {}
    if not onion_layers_df.empty and "layer_code" in onion_layers_df.columns:
        for fk, grp in onion_layers_df.groupby("family_key"):
            layers_by_family[str(fk)] = grp.reset_index(drop=True)

    # ── Build stale_days lookup from chain_register ───────────────────────────
    stale_by_fk: dict[str, object] = {}
    if "stale_days" in chain_register_df.columns:
        for _, row in chain_register_df.iterrows():
            fk = str(row.get("family_key", ""))
            if fk:
                stale_by_fk[fk] = row.get("stale_days")

    # ── Enumerate all family_keys from chain_register ─────────────────────────
    all_fks = chain_register_df["family_key"].astype(str).unique().tolist()

    rows = []
    for fk in all_fks:
        sc = scores_by_fk.get(fk, {})

        # Identity
        numero = sc.get("numero") or _safe_reg_val(chain_register_df, fk, "numero")

        # Status
        current_state = (
            sc.get("current_state")
            or _safe_reg_val(chain_register_df, fk, "current_state")
            or "UNKNOWN_CHAIN_STATE"
        )
        portfolio_bucket = (
            sc.get("portfolio_bucket")
            or _safe_reg_val(chain_register_df, fk, "portfolio_bucket")
            or "ARCHIVED_HISTORICAL"
        )

        # Scores
        norm_score = float(sc.get("normalized_score_100") or 0.0)
        blended_conf = float(sc.get("blended_confidence") or 0.0)
        priority_rank = sc.get("action_priority_rank")
        top_layer_code = sc.get("top_layer_code") or None

        has_layers = fk in layers_by_family and not layers_by_family[fk].empty

        # Labels
        urgency = _urgency_label(norm_score)
        confidence = _confidence_label(blended_conf, has_layers)

        # Headline
        exec_summary = _executive_summary(portfolio_bucket, norm_score)

        # Driver texts
        primary = _primary_driver_text(top_layer_code)
        second_code = _second_layer_code(fk, top_layer_code, layers_by_family)
        secondary = _secondary_driver_text(second_code)

        # Operational note
        stale = stale_by_fk.get(fk)
        op_note = _operational_note(current_state, stale, portfolio_bucket)

        # Recommended focus
        focus = _recommended_focus(portfolio_bucket, current_state, norm_score)

        rows.append({
            "family_key": fk,
            "numero": numero,
            "current_state": current_state,
            "portfolio_bucket": portfolio_bucket,
            "executive_summary": exec_summary,
            "primary_driver_text": primary,
            "secondary_driver_text": secondary,
            "operational_note": op_note,
            "recommended_focus": focus,
            "urgency_label": urgency,
            "confidence_label": confidence,
            "normalized_score_100": norm_score,
            "action_priority_rank": priority_rank,
            "engine_version": ENGINE_VERSION,
            "generated_at": now_str,
        })

    result = pd.DataFrame(rows, columns=_OUTPUT_COLS)
    _validate(result)
    _LOG.info(
        "narrative_engine: %d families processed | urgency dist: %s",
        len(result),
        result["urgency_label"].value_counts().to_dict(),
    )
    return result


# =============================================================================
# Private helpers
# =============================================================================

def _safe_reg_val(chain_register_df: pd.DataFrame, fk: str, col: str) -> object:
    """Retrieve a single value from chain_register_df by family_key."""
    if col not in chain_register_df.columns:
        return None
    mask = chain_register_df["family_key"].astype(str) == fk
    subset = chain_register_df.loc[mask, col]
    if subset.empty:
        return None
    val = subset.iloc[0]
    if pd.isna(val) if not isinstance(val, str) else not val:
        return None
    return val


# ── Forbidden vocabulary ──────────────────────────────────────────────────────
_FORBIDDEN = frozenset([
    "guilty", "fault", "incompetent", "disaster", "scandal",
    "liar", "fraud", "blame",
])


def _validate(df: pd.DataFrame) -> None:
    """Post-write contract check. Logs errors; does not raise."""
    text_cols = [
        "executive_summary", "primary_driver_text", "secondary_driver_text",
        "operational_note", "recommended_focus",
    ]
    forbidden_hits: list[str] = []
    null_counts: dict[str, int] = {}

    for col in _OUTPUT_COLS:
        if col not in df.columns:
            _LOG.error("narrative_engine validate: missing column '%s'", col)

    for col in text_cols:
        if col not in df.columns:
            continue
        nulls = df[col].isna().sum() + (df[col] == "").sum()
        if nulls > 0:
            null_counts[col] = int(nulls)
        for word in _FORBIDDEN:
            hits = df[col].str.contains(word, case=False, na=False).sum()
            if hits > 0:
                forbidden_hits.append(f"{col}:'{word}'({hits})")

    if null_counts:
        _LOG.warning("narrative_engine validate: null/empty text: %s", null_counts)
    if forbidden_hits:
        _LOG.error("narrative_engine validate: FORBIDDEN vocabulary found: %s", forbidden_hits)
    else:
        _LOG.info("narrative_engine validate: forbidden vocabulary scan — CLEAN")
