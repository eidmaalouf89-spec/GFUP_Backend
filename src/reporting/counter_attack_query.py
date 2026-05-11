"""Phase 6B — Counter-Attack Read API.

Read-only screen-payload adapter over the Phase 6A artifact:

    output/intermediate/COUNTER_ATTACK_ITEMS.csv

This module exposes three public functions consumed by `app.Api`:

    get_counter_attack_home() -> dict
    get_counter_attack_queue(bucket: str, limit: int = 500) -> dict
    get_counter_attack_item(item_id: str) -> dict

It does NOT recompute action_bucket, ownership, deadline, secondary expiry,
MOEX exposure, attackability, onion score, chain state, or DCC tags. Every
business decision was already baked into the artifact by Phase 6A.

Identity columns (item_id, numero, indice, family_key, emetteur_code) are
always read as strings to preserve leading zeros (Phase 4 leading-zero bug
guard). `keep_default_na=False` keeps empty strings as `""` rather than NaN.

Empty-state contract: a missing artifact returns `available=False` payloads
matching the shapes specified in `docs/implementation/PHASE_6B_READ_API.md`.
No exceptions propagate from the public functions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# ── Artifact location ──────────────────────────────────────────
_MODULE_DIR = Path(__file__).resolve().parent
_BASE_DIR = _MODULE_DIR.parent.parent
_INTERMEDIATE_DIR = _BASE_DIR / "output" / "intermediate"


def _artifact_path() -> Path:
    """Return the path to COUNTER_ATTACK_ITEMS.csv.

    Exposed at module level so validation scripts can monkey-patch this
    function to test missing-artifact behaviour without deleting the real
    artifact.
    """
    return _INTERMEDIATE_DIR / "COUNTER_ATTACK_ITEMS.csv"


# ── Bucket display order (home cockpit; not the 6A assignment order) ──
BUCKET_DISPLAY_ORDER: List[str] = [
    "FERMER_MAINTENANT",
    "DECISION_MOEX",
    "ENTREPRISE_A_RELANCER",
    "CONSULTANT_A_ATTAQUER",
]

# Plain-French short labels for the home cards. The artifact already
# carries `action_label` per row; these labels are used in the home
# payload (where no row exists yet) to describe the bucket itself.
BUCKET_LABEL: Dict[str, str] = {
    "FERMER_MAINTENANT": "À fermer maintenant",
    "DECISION_MOEX": "Décision MOEX — arbitrage requis",
    "ENTREPRISE_A_RELANCER": "Entreprise à relancer",
    "CONSULTANT_A_ATTAQUER": "Consultant à attaquer",
}

BUCKET_DESCRIPTION: Dict[str, str] = {
    "FERMER_MAINTENANT": "Tous les avis sont disponibles, MOEX doit émettre le visa.",
    "DECISION_MOEX": "Plusieurs avis bloquants sur l'indice courant — MOEX doit arbitrer.",
    "ENTREPRISE_A_RELANCER": "L'entreprise doit resoumettre après refus MOEX.",
    "CONSULTANT_A_ATTAQUER": "Un consultant tarde à répondre — relance / escalade.",
}

EMPTY_MESSAGE: str = "Le module Contre-attaque n'est pas encore généré."
ITEM_NOT_FOUND_MESSAGE: str = "Élément introuvable dans la contre-attaque actuelle."


# ── Internal helpers ───────────────────────────────────────────
_IDENTITY_DTYPES: Dict[str, str] = {
    "item_id": "string",
    "numero": "string",
    "indice": "string",
    "family_key": "string",
    "emetteur_code": "string",
}


def _load_items_df() -> Optional[pd.DataFrame]:
    """Load COUNTER_ATTACK_ITEMS.csv with identity columns locked as strings.

    Returns None if the artifact is missing or unreadable. Never raises.
    """
    path = _artifact_path()
    if not path.exists():
        return None
    try:
        df = pd.read_csv(
            path,
            dtype=_IDENTITY_DTYPES,
            keep_default_na=False,
        )
    except Exception:
        return None
    return df


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, float) and pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any) -> bool:
    """Coerce CSV-read bool-ish values. Pandas may yield bool, numpy.bool_,
    or strings like 'True'/'False' depending on the column."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    if value is None:
        return False
    try:
        return bool(value)
    except Exception:
        return False


def _decode_json_column(value: Any) -> List[Any]:
    """Decode a JSON-encoded string column to a list. Returns [] on any
    parse failure, empty input, or non-list result."""
    s = _safe_str(value).strip()
    if not s:
        return []
    try:
        decoded = json.loads(s)
    except Exception:
        return []
    if isinstance(decoded, list):
        return decoded
    return []


def _resolve_actor(row: pd.Series) -> str:
    """Actor fallback chain documented in the Phase 6B prompt §8.2."""
    for column in ("actor_to_call", "primary_actor", "emetteur_name", "emetteur_code"):
        candidate = _safe_str(row.get(column)).strip()
        if candidate:
            return candidate
    return ""


def _bucket_label(row: pd.Series) -> str:
    """Per-row bucket label. Prefer the row's `action_label` (authored by 6A)
    so per-bucket French labels stay consistent with the artifact, fall back
    to the BUCKET_LABEL map."""
    label = _safe_str(row.get("action_label")).strip()
    if label:
        return label
    bucket = _safe_str(row.get("action_bucket")).strip()
    return BUCKET_LABEL.get(bucket, bucket)


def _row_to_queue_row(row: pd.Series) -> Dict[str, Any]:
    numero = _safe_str(row.get("numero"))
    indice = _safe_str(row.get("indice"))
    return {
        "item_id": _safe_str(row.get("item_id")),
        "numero": numero,
        "indice": indice,
        "subject_label": _safe_str(row.get("subject_label")),
        "actor": _resolve_actor(row),
        "reason": _safe_str(row.get("plain_reason")),
        "recommended_action": _safe_str(row.get("recommended_action")),
        "risk_level": _safe_str(row.get("risk_level")),
        "days_open": _safe_int(row.get("days_open")),
        "days_late": _safe_int(row.get("days_late")),
        "warning_tags": _safe_str(row.get("warning_tags")),
        "open_dcc_ref": {"numero": numero, "indice": indice},
    }


def _format_observation_evidence(record: Dict[str, Any]) -> str:
    indice = _safe_str(record.get("indice"))
    reviewer = _safe_str(record.get("reviewer"))
    comment = _safe_str(record.get("comment"))
    head = " ".join(part for part in (indice, reviewer) if part).strip()
    if head and comment:
        return f"[{head}] {comment}"
    return comment or head


def _format_consultant_report_evidence(record: Dict[str, Any]) -> str:
    indice = _safe_str(record.get("indice"))
    reviewer = _safe_str(record.get("reviewer"))
    source = _safe_str(record.get("effective_source"))
    comment = _safe_str(record.get("comment"))
    head_parts = [p for p in (indice, reviewer) if p]
    head = " ".join(head_parts).strip()
    if source:
        head = f"{head} <{source}>" if head else f"<{source}>"
    if head and comment:
        return f"[{head}] {comment}"
    return comment or head


def _build_evidence(row: pd.Series) -> List[str]:
    """Compose plain-French evidence strings from observations + consultant
    reports already authored by 6A. Caps at the most recent 3 of each kind
    so the cockpit detail panel stays readable. Raw JSON is never exposed.
    """
    evidence: List[str] = []

    summary = _safe_str(row.get("evidence_summary")).strip()
    if summary:
        evidence.append(summary)

    obs = _decode_json_column(row.get("chain_observations_full"))
    for record in obs[-3:]:
        if isinstance(record, dict):
            line = _format_observation_evidence(record)
            if line:
                evidence.append(line)

    reports = _decode_json_column(row.get("consultant_reports_full"))
    for record in reports[-3:]:
        if isinstance(record, dict):
            line = _format_consultant_report_evidence(record)
            if line:
                evidence.append(line)

    return evidence


def _build_why_here(row: pd.Series) -> List[str]:
    """Return the human-readable reasons the item exists in this bucket.
    Only uses fields already on the row — no reasoning is invented."""
    reasons: List[str] = []
    plain = _safe_str(row.get("plain_reason")).strip()
    if plain:
        reasons.append(plain)
    days_late = _safe_int(row.get("days_late"))
    days_open = _safe_int(row.get("days_open"))
    if days_late > 0:
        reasons.append(f"Retard accumulé : {days_late} jours.")
    if days_open > 0:
        reasons.append(f"Sujet ouvert depuis {days_open} jours.")
    return reasons


def _empty_home_payload(message: str = EMPTY_MESSAGE) -> Dict[str, Any]:
    return {
        "available": False,
        "message": message,
        "summary": {"total_today": 0, "recommended_first_bucket": None},
        "buckets": [],
    }


def _empty_queue_payload(bucket: str, message: str = EMPTY_MESSAGE) -> Dict[str, Any]:
    return {
        "available": False,
        "message": message,
        "bucket": bucket,
        "bucket_label": BUCKET_LABEL.get(bucket, bucket),
        "count": 0,
        "rows": [],
    }


def _empty_item_payload(message: str = EMPTY_MESSAGE) -> Dict[str, Any]:
    return {
        "available": False,
        "found": False,
        "message": message,
    }


# ── Public API ─────────────────────────────────────────────────
def get_counter_attack_home() -> Dict[str, Any]:
    """Return home-screen payload: bucket counts in display order + summary.

    Display order is fixed (FERMER_MAINTENANT first), distinct from the
    Phase 6A first-match-wins assignment order. Buckets with zero rows are
    still returned so the cockpit always renders all 7 cards.
    """
    df = _load_items_df()
    if df is None:
        return _empty_home_payload()

    if "action_bucket" not in df.columns:
        return _empty_home_payload(EMPTY_MESSAGE)

    counts = df["action_bucket"].astype(str).value_counts().to_dict()
    total_today = int(sum(counts.get(b, 0) for b in BUCKET_DISPLAY_ORDER))

    buckets: List[Dict[str, Any]] = []
    for priority, bucket in enumerate(BUCKET_DISPLAY_ORDER, start=1):
        buckets.append({
            "bucket": bucket,
            "label": BUCKET_LABEL.get(bucket, bucket),
            "count": int(counts.get(bucket, 0)),
            "priority": priority,
            "description": BUCKET_DESCRIPTION.get(bucket, ""),
        })

    recommended: Optional[str] = None
    for entry in buckets:
        if entry["count"] > 0:
            recommended = entry["bucket"]
            break

    return {
        "available": True,
        "summary": {
            "total_today": total_today,
            "recommended_first_bucket": recommended,
        },
        "buckets": buckets,
    }


def get_counter_attack_queue(bucket: str, limit: int = 500) -> Dict[str, Any]:
    """Return up to `limit` queue rows for a given bucket key.

    Unknown bucket keys produce `available=True` with `count=0` (artifact is
    present, the bucket simply has no rows). Limit is clamped to >= 0.
    """
    bucket_str = str(bucket or "")
    try:
        limit_int = int(limit)
    except (TypeError, ValueError):
        limit_int = 500
    if limit_int < 0:
        limit_int = 0

    df = _load_items_df()
    if df is None:
        return _empty_queue_payload(bucket_str)

    if "action_bucket" not in df.columns:
        return _empty_queue_payload(bucket_str)

    sub = df[df["action_bucket"].astype(str) == bucket_str]
    rows: List[Dict[str, Any]] = []
    if not sub.empty and limit_int > 0:
        # ACTION MOEX correction Set 1 step S1 — present queue rows sorted by
        # least days_late first (the freshest backlog floats to the top; long
        # tails sink). Numeric coercion routes blank/NaN days_late to the last
        # position. Tie-breakers: days_open ascending, then (numero, indice)
        # for deterministic ordering. Stable mergesort preserves any
        # pre-existing order on full ties. Pure presentation order — no new
        # business logic, no field hiding, no recomputation.
        sub_sorted = sub.assign(
            __am_late_key=pd.to_numeric(sub["days_late"], errors="coerce"),
            __am_open_key=pd.to_numeric(sub["days_open"], errors="coerce"),
        ).sort_values(
            by=["__am_late_key", "__am_open_key", "numero", "indice"],
            ascending=[True, True, True, True],
            na_position="last",
            kind="mergesort",
        )
        for _, row in sub_sorted.head(limit_int).iterrows():
            rows.append(_row_to_queue_row(row))

    return {
        "available": True,
        "bucket": bucket_str,
        "bucket_label": BUCKET_LABEL.get(bucket_str, bucket_str),
        "count": int(len(sub)),
        "rows": rows,
    }


def get_counter_attack_item(item_id: str) -> Dict[str, Any]:
    """Return the full detail payload for a single item_id.

    `timeline` is intentionally [] — Phase 6B does not invent timeline data;
    the cockpit can later reach the existing chain timeline through the
    Document Command Center via `open_dcc_ref`.
    """
    item_id_str = str(item_id or "")

    df = _load_items_df()
    if df is None:
        return _empty_item_payload()

    if "item_id" not in df.columns or not item_id_str:
        return {
            "available": True,
            "found": False,
            "message": ITEM_NOT_FOUND_MESSAGE,
        }

    sub = df[df["item_id"].astype(str) == item_id_str]
    if sub.empty:
        return {
            "available": True,
            "found": False,
            "message": ITEM_NOT_FOUND_MESSAGE,
        }

    row = sub.iloc[0]
    numero = _safe_str(row.get("numero"))
    indice = _safe_str(row.get("indice"))
    bucket = _safe_str(row.get("action_bucket"))

    header = {
        "item_id": _safe_str(row.get("item_id")),
        "numero": numero,
        "indice": indice,
        "subject_label": _safe_str(row.get("subject_label")),
        "actor": _resolve_actor(row),
        "bucket": bucket,
        "bucket_label": _bucket_label(row),
        "risk_level": _safe_str(row.get("risk_level")),
    }

    return {
        "available": True,
        "found": True,
        "header": header,
        "what_is_it": _safe_str(row.get("subject_label")),
        "why_here": _build_why_here(row),
        "recommended_action": _safe_str(row.get("recommended_action")),
        "evidence": _build_evidence(row),
        "warning_tags": _safe_str(row.get("warning_tags")),
        "timeline": [],
        "open_dcc_ref": {"numero": numero, "indice": indice},
    }
