"""
src/chain_onion/onion_engine.py
-------------------------------
Step 09 — Onion Layer Engine.

Builds forensic responsibility layers from chain evidence.
One chain can carry 0–6 active layers simultaneously.
Each layer represents a distinct cause of chain distress.

Layers are stacked causes, not mutually exclusive statuses.

Authoritative contract: docs/STEP03_ONION_CONTRACT.md

Public API
----------
build_onion_layers(
    chain_register_df,
    chain_events_df,
    chain_metrics_df,
) -> pd.DataFrame  # onion_layers_df

Output: one row per (family_key, layer_code). Only active layers emitted.
No narrative prose. No AI inference. No state reclassification. Evidence only.

Layer definitions (STEP03 Section B)
-------------------------------------
L1  CONTRACTOR_QUALITY         — churn / rejection by submitter
L2  SAS_GATE_FRICTION          — SAS conformity gate delay or rejection
L3  PRIMARY_CONSULTANT_DELAY   — primary consultant blocking / delay / rejection
L4  SECONDARY_CONSULTANT_DELAY — secondary consultant blocking / delay / rejection
L5  MOEX_ARBITRATION_DELAY     — MOEX arbitration pending or delayed
L6  DATA_REPORT_CONTRADICTION  — GED ↔ report source conflict

Severity thresholds (STEP03 Section D)
----------------------------------------
Delay-based:  1–7 LOW | 8–21 MEDIUM | 22–45 HIGH | >45 CRITICAL
Count-based:  1 LOW   | 2 MEDIUM    | 3 HIGH      | ≥4 CRITICAL
MULTI:        max of contributing components
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

_LOG = logging.getLogger(__name__)

ENGINE_VERSION = "0.9.0"

# ── Actor type vocabulary (from chain_builder.py Step 06) ─────────────────────
_SAS  = "SAS"
_PCON = "PRIMARY_CONSULTANT"
_SCON = "SECONDARY_CONSULTANT"
_MOEX = "MOEX"
_CONT = "CONTRACTOR"

# ── Layer registry (code, name, rank) ─────────────────────────────────────────
_LAYER_L1 = ("L1_CONTRACTOR_QUALITY",         "Contractor Quality",          1)
_LAYER_L2 = ("L2_SAS_GATE_FRICTION",          "SAS Gate Friction",           2)
_LAYER_L3 = ("L3_PRIMARY_CONSULTANT_DELAY",   "Primary Consultant Delay",    3)
_LAYER_L4 = ("L4_SECONDARY_CONSULTANT_DELAY", "Secondary Consultant Delay",  4)
_LAYER_L5 = ("L5_MOEX_ARBITRATION_DELAY",     "MOEX Arbitration Delay",      5)
_LAYER_L6 = ("L6_DATA_REPORT_CONTRADICTION",  "Data/Report Contradiction",   6)

# ── Severity ordering (for max-of-components in MULTI) ────────────────────────
_SEV_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

# ── Rejection statuses (from chain_builder.py / STEP02) ──────────────────────
_REF_STATUSES = frozenset({"REF", "DEF", "REFSO"})

# ── Output column contract ────────────────────────────────────────────────────
OUTPUT_COLS = [
    "family_key", "numero",
    "layer_code", "layer_name", "layer_rank",
    "issue_type", "severity_raw", "confidence_raw",
    "evidence_count", "evidence_event_refs", "trigger_metrics",
    "first_trigger_date", "latest_trigger_date",
    "current_state", "portfolio_bucket", "pressure_index",
    "engine_version", "generated_at",
]


# =============================================================================
# Private helpers
# =============================================================================

def _normalize_bool(s: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False).astype(bool)
    return (
        s.map({"True": True, "False": False, True: True, False: False})
        .fillna(False)
        .astype(bool)
    )


def _fmt_date(ts) -> Optional[str]:
    if ts is None or (isinstance(ts, float) and pd.isna(ts)):
        return None
    try:
        t = pd.Timestamp(ts)
        return None if pd.isna(t) else str(t.date())
    except Exception:
        return None


def _event_refs(seqs: pd.Series) -> str:
    valid = seqs.dropna()
    if valid.empty:
        return ""
    vals = sorted(int(v) for v in valid.unique())[:30]
    return ",".join(str(v) for v in vals)


def _max_severity(*severities: str) -> str:
    if not severities:
        return "LOW"
    return max(severities, key=lambda s: _SEV_RANK.get(s, 0))


def _prep_events(ev_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize chain_events_df for onion evaluation."""
    ev = ev_df.copy()

    for col in ("is_blocking", "is_completed", "requires_new_cycle"):
        if col in ev.columns:
            ev[col] = _normalize_bool(ev[col])
        else:
            ev[col] = False

    if "delay_contribution_days" in ev.columns:
        ev["delay_contribution_days"] = (
            pd.to_numeric(ev["delay_contribution_days"], errors="coerce").fillna(0)
        )
    else:
        ev["delay_contribution_days"] = 0.0

    if "event_date" in ev.columns:
        ev["event_date"] = pd.to_datetime(ev["event_date"], errors="coerce")
    else:
        ev["event_date"] = pd.NaT

    ev["status_upper"] = (
        ev["status"].fillna("").astype(str).str.upper().str.strip()
        if "status" in ev.columns else ""
    )

    ev["source_str"] = (
        ev["source"].fillna("").astype(str).str.upper()
        if "source" in ev.columns else ""
    )

    if "actor_type" not in ev.columns:
        ev["actor_type"] = "UNKNOWN"

    if "actor" not in ev.columns:
        ev["actor"] = "UNKNOWN"

    if "notes" not in ev.columns:
        ev["notes"] = ""

    if "event_seq" not in ev.columns:
        ev["event_seq"] = range(len(ev))

    if "instance_key" not in ev.columns:
        ev["instance_key"] = ev.get("version_key", "")

    if "version_key" not in ev.columns:
        ev["version_key"] = ""

    if "issue_signal" not in ev.columns:
        ev["issue_signal"] = "NONE"

    return ev


# =============================================================================
# Severity models (STEP03 Sections B + D)
# =============================================================================

def _sev_delay(days: float) -> str:
    if days > 45:
        return "CRITICAL"
    if days >= 22:
        return "HIGH"
    if days >= 8:
        return "MEDIUM"
    if days >= 1:
        return "LOW"
    return "LOW"


def _sev_count(count: int) -> str:
    if count >= 4:
        return "CRITICAL"
    if count == 3:
        return "HIGH"
    if count == 2:
        return "MEDIUM"
    return "LOW"


def _l1_severity(total_versions: int, rejection_version_count: int, resubmission_count: int) -> str:
    """STEP03 B.1.4 — first matching rule wins."""
    if total_versions >= 4 or rejection_version_count >= 3:
        return "CRITICAL"
    if total_versions == 3 or (total_versions == 2 and rejection_version_count >= 2):
        return "HIGH"
    if total_versions == 2 and rejection_version_count == 1 and resubmission_count >= 3:
        return "MEDIUM"
    if total_versions == 2 and rejection_version_count == 1 and resubmission_count <= 2:
        return "LOW"
    # Fallback for edge cases not covered by the spec rules above
    return _sev_count(max(rejection_version_count, 1))


def _l2_severity(sas_ref_count: int, sas_delay_days: float, t3_only: bool, sas_pending: int) -> str:
    """STEP03 B.2.4 — first matching rule wins."""
    if sas_ref_count >= 3 or sas_delay_days > 45:
        return "CRITICAL"
    if sas_ref_count == 2 or (sas_ref_count == 1 and sas_delay_days >= 22):
        return "HIGH"
    if sas_ref_count == 1 and 8 <= sas_delay_days <= 21:
        return "MEDIUM"
    if sas_ref_count == 1 and sas_delay_days <= 14:
        return "LOW"
    if sas_ref_count == 0 and 1 <= sas_delay_days <= 7:
        return "LOW"
    # L2_T3 only (pure dormancy, no completed REF)
    if t3_only:
        if sas_pending > 1:
            return "HIGH"
        return _sev_delay(sas_delay_days) if sas_delay_days > 0 else "MEDIUM"
    return "LOW"


def _consultant_severity(
    delay_days: float,
    rejection_count: int,
    no_response_count: int,
    t2_only: bool,
) -> str:
    """STEP03 B.3.4/B.4.4."""
    if t2_only:
        if no_response_count >= 4:
            return "CRITICAL"
        if no_response_count == 3:
            return "HIGH"
        if no_response_count == 2:
            return "MEDIUM"
        return "LOW"
    if delay_days > 45 or (no_response_count >= 2 and delay_days >= 22):
        return "CRITICAL"
    if delay_days >= 22 or rejection_count >= 2:
        return "HIGH"
    if delay_days >= 8 or rejection_count == 1:
        return "MEDIUM"
    if delay_days >= 1:
        return "LOW"
    return "LOW"


def _l5_severity(moex_delay: float, pending: bool, pending_versions: int, t2_only: bool) -> str:
    """STEP03 B.5.4."""
    if moex_delay > 45:
        return "CRITICAL"
    if moex_delay >= 22 or (pending and pending_versions >= 2):
        return "HIGH"
    if moex_delay >= 8 or (pending and pending_versions == 1):
        return "MEDIUM"
    if t2_only:
        if pending_versions >= 3:
            return "CRITICAL"
        if pending_versions >= 2:
            return "HIGH"
        return "MEDIUM"
    if moex_delay >= 1:
        return "LOW"
    return "LOW"


def _l6_severity(conflict_row_count: int, conflict_versions: int) -> str:
    """STEP03 B.6.4."""
    if conflict_row_count >= 6:
        return "CRITICAL"
    if 4 <= conflict_row_count <= 5:
        return "HIGH"
    if conflict_row_count >= 2 or conflict_versions >= 2:
        return "MEDIUM"
    return "LOW"


# =============================================================================
# Confidence models (STEP03 Section E)
# =============================================================================

def _confidence_from_events(qualifying: pd.DataFrame) -> int:
    """
    Derive confidence from source quality of qualifying events.
    Returns integer 10–100.

    Tier logic (STEP03 E.1/E.2 — single most applicable deduction):
      - All event_date non-null AND source OPS → ≥85
      - Any event_date null → max 35
      - Any source EFFECTIVE → max 72
      - Any notes "Synthetic instance" → max 55
    """
    if qualifying.empty:
        return 10

    has_null_date = qualifying["event_date"].isna().any()
    if has_null_date:
        return 35

    has_effective = (qualifying["source_str"] == "EFFECTIVE").any()
    if has_effective:
        return 72

    has_synthetic = qualifying["notes"].fillna("").str.contains("Synthetic instance", case=False).any()
    if has_synthetic:
        return 55

    return 90


# =============================================================================
# Per-layer evaluators — each takes the family's events + metrics row → dict|None
# =============================================================================

def _eval_l1(
    fk: str,
    fam_ev: pd.DataFrame,
    metrics_row: dict,
    register_row: dict,
) -> Optional[dict]:
    """
    L1 — CONTRACTOR_QUALITY (STEP03 B.1)

    Triggers:
      L1_T1: any version has instance_count > 1
      L1_T2: any event has requires_new_cycle = True
      L1_T3: total_versions >= 2 AND any SAS event has status = REF
    """
    # L1_T1: count distinct instance_keys per version_key
    if fam_ev.empty:
        return None

    version_instances = (
        fam_ev.groupby("version_key")["instance_key"].nunique()
    )
    l1_t1 = bool((version_instances > 1).any())
    resubmission_count = int((version_instances - 1).clip(lower=0).sum())

    # L1_T2
    l1_t2 = bool(fam_ev["requires_new_cycle"].any())

    # L1_T3
    total_versions = int(metrics_row.get("total_versions", 0) or 0)
    sas_ref_rows = fam_ev[
        (fam_ev["actor_type"] == _SAS) &
        fam_ev["status_upper"].str.contains("REF", na=False)
    ]
    l1_t3 = total_versions >= 2 and not sas_ref_rows.empty

    triggers = []
    if l1_t1:
        triggers.append("L1_T1")
    if l1_t2:
        triggers.append("L1_T2")
    if l1_t3:
        triggers.append("L1_T3")

    if not triggers:
        return None

    # issue_type (STEP03 B.1.3)
    has_rejection = l1_t2 or l1_t3
    if l1_t1 and has_rejection:
        issue_type = "MULTI"
    elif l1_t1:
        issue_type = "CHURN"
    else:
        issue_type = "REJECTION"

    # Metrics for severity
    rejection_version_count = int(metrics_row.get("rejection_cycles", 0) or 0)

    severity = _l1_severity(total_versions, rejection_version_count, resubmission_count)

    # Evidence — SUBMITTAL events + CYCLE_REQUIRED events
    qualifying = fam_ev[
        (fam_ev["actor_type"] == _CONT) | fam_ev["requires_new_cycle"]
    ]
    if qualifying.empty:
        qualifying = fam_ev[fam_ev["actor_type"] == _CONT]
    evidence_count = len(qualifying)
    if evidence_count == 0:
        return None  # contract violation — do not emit

    confidence = _confidence_from_events(qualifying)
    # Synthetic note degrades confidence to max 40 for L1 (STEP03 B.1.5)
    if fam_ev["notes"].fillna("").str.contains("Synthetic instance", case=False).any():
        confidence = min(confidence, 40)

    # responsible_actor: first CONTRACTOR event's actor
    contractor_rows = fam_ev[fam_ev["actor_type"] == _CONT].sort_values("event_date")
    responsible = (
        contractor_rows["actor"].iloc[0]
        if not contractor_rows.empty else "UNKNOWN"
    )

    trigger_metrics = (
        f"total_versions={total_versions};"
        f"rejection_cycles={rejection_version_count};"
        f"resubmission_count={resubmission_count}"
    )

    dates = qualifying["event_date"].dropna()
    return _build_row(
        fk=fk, layer=_LAYER_L1,
        issue_type=issue_type,
        severity=severity,
        confidence=confidence,
        evidence_count=evidence_count,
        evidence_seqs=qualifying["event_seq"],
        trigger_metrics=trigger_metrics,
        first_date=dates.min() if not dates.empty else None,
        latest_date=dates.max() if not dates.empty else None,
        metrics_row=metrics_row,
        trigger_codes=",".join(triggers),
    )


def _eval_l2(
    fk: str,
    fam_ev: pd.DataFrame,
    metrics_row: dict,
    register_row: dict,
) -> Optional[dict]:
    """
    L2 — SAS_GATE_FRICTION (STEP03 B.2)

    Triggers:
      L2_T1: actor_type=SAS AND status=REF AND is_completed=True
      L2_T2: actor_type=SAS AND delay_contribution_days > 0
      L2_T3: actor_type=SAS AND is_blocking=True AND event_date null
    """
    sas_ev = fam_ev[fam_ev["actor_type"] == _SAS]
    if sas_ev.empty:
        return None

    l2_t1_rows = sas_ev[
        sas_ev["status_upper"].str.contains("REF", na=False) &
        sas_ev["is_completed"]
    ]
    l2_t2_rows = sas_ev[sas_ev["delay_contribution_days"] > 0]
    l2_t3_rows = sas_ev[
        sas_ev["is_blocking"] &
        sas_ev["event_date"].isna()
    ]

    l2_t1 = not l2_t1_rows.empty
    l2_t2 = not l2_t2_rows.empty
    l2_t3 = not l2_t3_rows.empty

    triggers = []
    if l2_t1:
        triggers.append("L2_T1")
    if l2_t2:
        triggers.append("L2_T2")
    if l2_t3:
        triggers.append("L2_T3")

    if not triggers:
        return None

    active = (l2_t1, l2_t2, l2_t3)
    active_count = sum(active)
    if active_count >= 2:
        issue_type = "MULTI"
    elif l2_t1:
        issue_type = "REJECTION"
    elif l2_t2:
        issue_type = "DELAY"
    else:
        issue_type = "DORMANCY"

    sas_ref_count = len(l2_t1_rows)
    sas_delay_days = float(l2_t2_rows["delay_contribution_days"].sum())
    sas_pending = len(l2_t3_rows)
    t3_only = l2_t3 and not l2_t1 and not l2_t2

    severity = _l2_severity(sas_ref_count, sas_delay_days, t3_only, sas_pending)

    qualifying = pd.concat(
        [l2_t1_rows, l2_t2_rows, l2_t3_rows]
    ).drop_duplicates()
    evidence_count = len(qualifying)
    if evidence_count == 0:
        return None

    confidence = _confidence_from_events(qualifying)
    if t3_only:
        confidence = min(confidence, 35)

    trigger_metrics = (
        f"sas_ref_count={sas_ref_count};"
        f"sas_delay_days={int(sas_delay_days)};"
        f"sas_pending_versions={sas_pending}"
    )

    dates = qualifying["event_date"].dropna()
    return _build_row(
        fk=fk, layer=_LAYER_L2,
        issue_type=issue_type, severity=severity, confidence=confidence,
        evidence_count=evidence_count,
        evidence_seqs=qualifying["event_seq"],
        trigger_metrics=trigger_metrics,
        first_date=dates.min() if not dates.empty else None,
        latest_date=dates.max() if not dates.empty else None,
        metrics_row=metrics_row,
        trigger_codes=",".join(triggers),
    )


def _eval_consultant_layer(
    fk: str,
    fam_ev: pd.DataFrame,
    metrics_row: dict,
    actor_type_filter: str,
    layer_def: tuple,
    trigger_prefix: str,
) -> Optional[dict]:
    """
    Shared evaluator for L3 (PRIMARY) and L4 (SECONDARY) — STEP03 B.3/B.4.

    Triggers:
      T1: delay_contribution_days > 0
      T2: is_blocking=True AND event_date null
      T3: status in {REF, REFSO}
    """
    con_ev = fam_ev[fam_ev["actor_type"] == actor_type_filter]
    if con_ev.empty:
        return None

    t1_rows = con_ev[con_ev["delay_contribution_days"] > 0]
    t2_rows = con_ev[con_ev["is_blocking"] & con_ev["event_date"].isna()]
    t3_rows = con_ev[con_ev["status_upper"].isin(_REF_STATUSES)]

    t1 = not t1_rows.empty
    t2 = not t2_rows.empty
    t3 = not t3_rows.empty

    triggers = []
    if t1:
        triggers.append(f"{trigger_prefix}_T1")
    if t2:
        triggers.append(f"{trigger_prefix}_T2")
    if t3:
        triggers.append(f"{trigger_prefix}_T3")

    if not triggers:
        return None

    active_count = sum([t1, t2, t3])
    if active_count >= 2:
        issue_type = "MULTI"
    elif t2:
        issue_type = "DORMANCY"
    elif t3:
        issue_type = "REJECTION"
    else:
        issue_type = "DELAY"

    # Responsible actor: worst offender by delay, tie-break by most recent event_date
    delay_by_actor = (
        con_ev.groupby("actor")["delay_contribution_days"]
        .sum()
        .reset_index()
        .sort_values("delay_contribution_days", ascending=False)
    )
    if delay_by_actor.empty:
        responsible = con_ev["actor"].iloc[0] if not con_ev.empty else "UNKNOWN"
        max_delay = 0.0
    else:
        responsible = str(delay_by_actor["actor"].iloc[0])
        max_delay = float(delay_by_actor["delay_contribution_days"].iloc[0])

    rejection_count = len(con_ev[con_ev["status_upper"].isin(_REF_STATUSES)])
    blocking_count = int(con_ev["is_blocking"].sum())
    no_response_count = int((con_ev["is_blocking"] & con_ev["event_date"].isna()).sum())
    t2_only = t2 and not t1 and not t3

    severity = _consultant_severity(max_delay, rejection_count, no_response_count, t2_only)

    qualifying = pd.concat([t1_rows, t2_rows, t3_rows]).drop_duplicates()
    evidence_count = len(qualifying)
    if evidence_count == 0:
        return None

    confidence = _confidence_from_events(qualifying)
    if t2_only:
        confidence = min(confidence, 35)

    trigger_metrics = (
        f"delay_days={int(max_delay)};"
        f"rejection_count={rejection_count};"
        f"blocking_count={blocking_count};"
        f"no_response_count={no_response_count};"
        f"responsible_actor={responsible}"
    )

    dates = qualifying["event_date"].dropna()
    return _build_row(
        fk=fk, layer=layer_def,
        issue_type=issue_type, severity=severity, confidence=confidence,
        evidence_count=evidence_count,
        evidence_seqs=qualifying["event_seq"],
        trigger_metrics=trigger_metrics,
        first_date=dates.min() if not dates.empty else None,
        latest_date=dates.max() if not dates.empty else None,
        metrics_row=metrics_row,
        trigger_codes=",".join(triggers),
    )


def _eval_l5(
    fk: str,
    fam_ev: pd.DataFrame,
    metrics_row: dict,
    register_row: dict,
) -> Optional[dict]:
    """
    L5 — MOEX_ARBITRATION_DELAY (STEP03 B.5)

    Triggers:
      L5_T1: actor_type=MOEX AND delay_contribution_days > 0
      L5_T2: actor_type=MOEX AND is_blocking=True AND event_date null
    """
    moex_ev = fam_ev[fam_ev["actor_type"] == _MOEX]
    if moex_ev.empty:
        return None

    t1_rows = moex_ev[moex_ev["delay_contribution_days"] > 0]
    t2_rows = moex_ev[moex_ev["is_blocking"] & moex_ev["event_date"].isna()]

    t1 = not t1_rows.empty
    t2 = not t2_rows.empty

    triggers = []
    if t1:
        triggers.append("L5_T1")
    if t2:
        triggers.append("L5_T2")

    if not triggers:
        return None

    if t1 and t2:
        issue_type = "MULTI"
    elif t2:
        issue_type = "DORMANCY"
    else:
        issue_type = "DELAY"

    moex_delay = float(t1_rows["delay_contribution_days"].sum())
    pending = t2
    pending_versions = int(
        t2_rows["version_key"].nunique() if "version_key" in t2_rows.columns else len(t2_rows)
    )
    t2_only = t2 and not t1

    severity = _l5_severity(moex_delay, pending, pending_versions, t2_only)

    qualifying = pd.concat([t1_rows, t2_rows]).drop_duplicates()
    evidence_count = len(qualifying)
    if evidence_count == 0:
        return None

    confidence = _confidence_from_events(qualifying)
    if t2_only:
        confidence = min(confidence, 38)

    trigger_metrics = (
        f"moex_delay_days={int(moex_delay)};"
        f"moex_pending={pending};"
        f"moex_versions_pending={pending_versions}"
    )

    dates = qualifying["event_date"].dropna()
    return _build_row(
        fk=fk, layer=_LAYER_L5,
        issue_type=issue_type, severity=severity, confidence=confidence,
        evidence_count=evidence_count,
        evidence_seqs=qualifying["event_seq"],
        trigger_metrics=trigger_metrics,
        first_date=dates.min() if not dates.empty else None,
        latest_date=dates.max() if not dates.empty else None,
        metrics_row=metrics_row,
        trigger_codes=",".join(triggers),
    )


def _eval_l6(
    fk: str,
    fam_ev: pd.DataFrame,
    metrics_row: dict,
    register_row: dict,
) -> Optional[dict]:
    """
    L6 — DATA_REPORT_CONTRADICTION (STEP03 B.6)

    Trigger L6_T1:
      issue_signal == "CONTRADICTION"
      OR source contains "CONFLICT"
    """
    contradiction_rows = fam_ev[
        (fam_ev.get("issue_signal", pd.Series("NONE", index=fam_ev.index)).fillna("NONE") == "CONTRADICTION") |
        fam_ev["source_str"].str.contains("CONFLICT", na=False)
    ]

    if contradiction_rows.empty:
        return None

    conflict_row_count = len(contradiction_rows)
    conflict_versions = int(contradiction_rows["version_key"].nunique()) if "version_key" in contradiction_rows.columns else 1

    # issue_type upgrade: CONTRADICTION → MULTI if any conflict row is also blocking with delay
    upgraded = contradiction_rows[
        contradiction_rows["is_blocking"] &
        (contradiction_rows["delay_contribution_days"] > 0)
    ]
    issue_type = "MULTI" if not upgraded.empty else "CONTRADICTION"

    severity = _l6_severity(conflict_row_count, conflict_versions)

    confidence = 80 if not contradiction_rows.empty else 50

    trigger_metrics = (
        f"conflict_row_count={conflict_row_count};"
        f"conflict_versions={conflict_versions}"
    )

    dates = contradiction_rows["event_date"].dropna()
    return _build_row(
        fk=fk, layer=_LAYER_L6,
        issue_type=issue_type, severity=severity, confidence=confidence,
        evidence_count=conflict_row_count,
        evidence_seqs=contradiction_rows["event_seq"],
        trigger_metrics=trigger_metrics,
        first_date=dates.min() if not dates.empty else None,
        latest_date=dates.max() if not dates.empty else None,
        metrics_row=metrics_row,
        trigger_codes="L6_T1",
    )


# =============================================================================
# Row builder — assembles output dict from layer result
# =============================================================================

def _build_row(
    fk: str,
    layer: tuple,
    issue_type: str,
    severity: str,
    confidence: int,
    evidence_count: int,
    evidence_seqs: pd.Series,
    trigger_metrics: str,
    first_date,
    latest_date,
    metrics_row: dict,
    trigger_codes: str,
) -> dict:
    layer_code, layer_name, layer_rank = layer
    return {
        "family_key":         fk,
        "numero":             metrics_row.get("numero", fk),
        "layer_code":         layer_code,
        "layer_name":         layer_name,
        "layer_rank":         layer_rank,
        "issue_type":         issue_type,
        "severity_raw":       severity,
        "confidence_raw":     max(10, min(100, int(confidence))),
        "evidence_count":     evidence_count,
        "evidence_event_refs": _event_refs(evidence_seqs),
        "trigger_metrics":    trigger_metrics,
        "first_trigger_date":  _fmt_date(first_date),
        "latest_trigger_date": _fmt_date(latest_date),
        "current_state":      str(metrics_row.get("current_state", "") or ""),
        "portfolio_bucket":   str(metrics_row.get("portfolio_bucket", "") or ""),
        "pressure_index":     int(metrics_row.get("pressure_index", 0) or 0),
        "engine_version":     ENGINE_VERSION,
        "generated_at":       datetime.now(timezone.utc).isoformat(),
        # Not in output contract but needed for dedup validation
        "_trigger_codes":     trigger_codes,
    }


# =============================================================================
# Deduplication (STEP03 C.1)
# =============================================================================

def _dedup_rows(rows: list[dict]) -> list[dict]:
    """
    Enforce (family_key, layer_code) uniqueness.
    If duplicates exist: keep row with higher evidence_count.
    Tie-break: higher severity.
    Logs ERROR for each duplicate pair found.
    """
    seen: dict[tuple, dict] = {}
    for row in rows:
        key = (row["family_key"], row["layer_code"])
        if key not in seen:
            seen[key] = row
        else:
            existing = seen[key]
            _LOG.error(
                "onion_engine: DUPLICATE (family_key=%s, layer_code=%s) — resolving by evidence_count/severity",
                row["family_key"], row["layer_code"],
            )
            existing_rank = (
                existing["evidence_count"],
                _SEV_RANK.get(existing["severity_raw"], 0),
            )
            new_rank = (
                row["evidence_count"],
                _SEV_RANK.get(row["severity_raw"], 0),
            )
            if new_rank > existing_rank:
                seen[key] = row
    return list(seen.values())


# =============================================================================
# Validation (STEP03 H.5)
# =============================================================================

def _validate(df: pd.DataFrame) -> list[str]:
    """
    Post-write validation checks. Returns list of error messages.
    An empty list means all checks passed.
    """
    errors: list[str] = []

    # evidence_count >= 1
    bad_evidence = df[df["evidence_count"] < 1]
    if not bad_evidence.empty:
        errors.append(
            f"evidence_count < 1 for {len(bad_evidence)} rows: "
            f"{bad_evidence[['family_key','layer_code']].to_dict('records')}"
        )

    # (family_key, layer_code) uniqueness
    dupes = df.duplicated(["family_key", "layer_code"], keep=False)
    if dupes.any():
        errors.append(f"Duplicate (family_key, layer_code) pairs: {df[dupes][['family_key','layer_code']].values.tolist()}")

    # Vocabulary checks
    valid_issue_types = {"DELAY", "REJECTION", "CHURN", "DORMANCY", "CONTRADICTION", "MULTI"}
    bad_issue = df[~df["issue_type"].isin(valid_issue_types)]
    if not bad_issue.empty:
        errors.append(f"Invalid issue_type values: {bad_issue['issue_type'].unique().tolist()}")

    valid_severities = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    bad_sev = df[~df["severity_raw"].isin(valid_severities)]
    if not bad_sev.empty:
        errors.append(f"Invalid severity_raw values: {bad_sev['severity_raw'].unique().tolist()}")

    valid_layers = {
        "L1_CONTRACTOR_QUALITY", "L2_SAS_GATE_FRICTION",
        "L3_PRIMARY_CONSULTANT_DELAY", "L4_SECONDARY_CONSULTANT_DELAY",
        "L5_MOEX_ARBITRATION_DELAY", "L6_DATA_REPORT_CONTRADICTION",
    }
    bad_layer = df[~df["layer_code"].isin(valid_layers)]
    if not bad_layer.empty:
        errors.append(f"Invalid layer_code values: {bad_layer['layer_code'].unique().tolist()}")

    # Confidence range
    bad_conf = df[(df["confidence_raw"] < 10) | (df["confidence_raw"] > 100)]
    if not bad_conf.empty:
        errors.append(f"confidence_raw out of [10,100] for {len(bad_conf)} rows")

    return errors


# =============================================================================
# Public API
# =============================================================================

def build_onion_layers(
    chain_register_df: pd.DataFrame,
    chain_events_df: pd.DataFrame,
    chain_metrics_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build the onion responsibility layer table.

    Parameters
    ----------
    chain_register_df : output of classify_chains() — one row per family_key
    chain_events_df   : output of build_chain_events() — one row per event
    chain_metrics_df  : output of build_chain_metrics() — one row per family_key

    Returns
    -------
    onion_layers_df : one row per (family_key, layer_code) — only active layers.
                      Columns: see OUTPUT_COLS.
    """
    if chain_register_df is None or chain_register_df.empty:
        _LOG.warning("onion_engine: chain_register_df is empty — returning empty onion_layers")
        return pd.DataFrame(columns=OUTPUT_COLS)

    if chain_events_df is None or chain_events_df.empty:
        _LOG.warning("onion_engine: chain_events_df is empty — no events to evaluate layers")
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Normalize events
    ev = _prep_events(chain_events_df)

    # Build lookup tables from metrics and register
    metrics_by_fk: dict[str, dict] = {}
    if chain_metrics_df is not None and not chain_metrics_df.empty:
        for _, row in chain_metrics_df.iterrows():
            fk = str(row.get("family_key", ""))
            metrics_by_fk[fk] = row.to_dict()

    register_by_fk: dict[str, dict] = {}
    for _, row in chain_register_df.iterrows():
        fk = str(row.get("family_key", ""))
        register_by_fk[fk] = row.to_dict()

    # Group events by family_key for O(1) per-family access
    ev["family_key"] = ev["family_key"].fillna("").astype(str)
    grouped = ev.groupby("family_key", sort=False)

    all_family_keys = sorted(register_by_fk.keys())
    rows: list[dict] = []

    generated_at = datetime.now(timezone.utc).isoformat()

    for fk in all_family_keys:
        if fk not in grouped.groups:
            fam_ev = pd.DataFrame(columns=ev.columns)
        else:
            fam_ev = grouped.get_group(fk)

        metrics_row = metrics_by_fk.get(fk, {})
        register_row = register_by_fk.get(fk, {})

        # If metrics_row is missing, try deriving numero from family_key
        if not metrics_row:
            metrics_row = {
                "numero": fk,
                "current_state": register_row.get("current_state", ""),
                "portfolio_bucket": register_row.get("portfolio_bucket", ""),
                "pressure_index": 0,
                "total_versions": register_row.get("total_versions", 0),
                "rejection_cycles": register_row.get("total_versions_requiring_cycle", 0),
            }

        # Evaluate all six layers
        for evaluator in [
            lambda: _eval_l1(fk, fam_ev, metrics_row, register_row),
            lambda: _eval_l2(fk, fam_ev, metrics_row, register_row),
            lambda: _eval_consultant_layer(fk, fam_ev, metrics_row, _PCON, _LAYER_L3, "L3"),
            lambda: _eval_consultant_layer(fk, fam_ev, metrics_row, _SCON, _LAYER_L4, "L4"),
            lambda: _eval_l5(fk, fam_ev, metrics_row, register_row),
            lambda: _eval_l6(fk, fam_ev, metrics_row, register_row),
        ]:
            result = evaluator()
            if result is not None:
                result["generated_at"] = generated_at
                rows.append(result)

    if not rows:
        _LOG.info("onion_engine: no layers fired across %d families", len(all_family_keys))
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Deduplicate
    rows = _dedup_rows(rows)

    df = pd.DataFrame(rows)

    # Drop internal-only column
    if "_trigger_codes" in df.columns:
        df = df.drop(columns=["_trigger_codes"])

    # Select and order output columns
    out_cols = [c for c in OUTPUT_COLS if c in df.columns]
    df = df[out_cols].reset_index(drop=True)

    # Validate
    errors = _validate(df)
    for err in errors:
        _LOG.error("onion_engine VALIDATION: %s", err)

    # Summary log
    by_layer = df.groupby("layer_code").size().to_dict()
    by_sev   = df.groupby("severity_raw").size().to_dict()
    _LOG.info(
        "onion_engine: %d rows from %d families | by_layer=%s | by_severity=%s",
        len(df), len(all_family_keys), by_layer, by_sev,
    )

    return df
