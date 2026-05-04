"""Reconstructed Phase 6A Counter-Attack artifact builder.

R1 scope: minimal deterministic implementation of the public builder API.
It writes only to the caller-provided output directory.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from reporting.contractor_fiche import resolve_emetteur_name
from reporting.document_command_center import compute_dcc_tags_bulk


OUTPUT_COLUMNS = [
    "item_id",
    "numero",
    "indice",
    "family_key",
    "subject_label",
    "emetteur_code",
    "emetteur_name",
    "primary_actor",
    "actor_to_call",
    "action_bucket",
    "action_label",
    "plain_reason",
    "recommended_action",
    "risk_level",
    "evidence_summary",
    "days_open",
    "days_late",
    "current_state",
    "normalized_score_100",
    "is_internal_moex_exposure",
    "is_external_attackable",
    "chain_observations_summary",
    "chain_observations_full",
    "chain_observations_refs",
    "consultant_reports_summary",
    "consultant_reports_full",
    "consultant_reports_refs",
    "consultant_reports_available",
]

IDENTITY_COLUMNS = ["item_id", "numero", "indice", "family_key", "emetteur_code"]

TERMINAL_STATES = {
    "CLOSED_VAO",
    "CLOSED_VSO",
    "DEAD_AT_SAS_A",
    "ABANDONED_CHAIN",
    "VOID_CHAIN",
    "UNKNOWN_CHAIN_STATE",
}

CONTRACTOR_TAGS = {
    "Att Entreprise - Dans les delais",
    "Att Entreprise - Hors delais",
    "Att Entreprise — Dans les délais",
    "Att Entreprise — Hors délais",
    "Att Entreprise â€” Dans les dÃ©lais",
    "Att Entreprise â€” Hors dÃ©lais",
}

MOEX_FACILE_TAGS = {"Att MOEX - Facile", "Att MOEX — Facile", "Att MOEX â€” Facile"}
MOEX_ARBITRAGE_TAGS = {"Att MOEX - Arbitrage", "Att MOEX — Arbitrage", "Att MOEX â€” Arbitrage"}
PRIMARY_TAGS = {"Att BET Primaire"}
SECONDARY_TAGS = {"Att BET Secondaire"}

ACTION_LABELS = {
    "ENTREPRISE_A_RELANCER": "Entreprise à relancer",
    "CONSULTANT_A_ATTAQUER": "Consultant à attaquer",
    "FERMER_MAINTENANT": "À fermer maintenant",
    "DECISION_MOEX": "Décision MOEX — arbitrage requis",
    "SECONDAIRE_EXPIRE": "Secondaire expiré — décision MOEX requise",
    "MOEX_SHAME_INTERNAL": "MOEX interne — exposition à traiter",
    "SUJET_REUNION": "Sujet réunion critique",
}

REPORT_SOURCE_VALUES = {
    "GED+REPORT_STATUS",
    "GED+REPORT_COMMENT",
    "GED_CONFLICT_REPORT",
}


def _base_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none", "<na>"}:
        return ""
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = _safe_str(value).lower()
    return text in {"1", "true", "yes", "y", "oui"}


def _norm_key(value: Any) -> str:
    return _safe_str(value)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype={"numero": "string", "family_key": "string", "indice": "string"}, keep_default_na=False)


def _load_chain_register() -> pd.DataFrame:
    return _read_csv(_base_dir() / "output" / "chain_onion" / "CHAIN_REGISTER.csv")


def _load_chain_metrics() -> pd.DataFrame:
    return _read_csv(_base_dir() / "output" / "chain_onion" / "CHAIN_METRICS.csv")


def _load_onion_scores() -> pd.DataFrame:
    return _read_csv(_base_dir() / "output" / "chain_onion" / "ONION_SCORES.csv")


def _load_chain_narratives() -> pd.DataFrame:
    return _read_csv(_base_dir() / "output" / "chain_onion" / "CHAIN_NARRATIVES.csv")


def _load_timeline_attribution() -> pd.DataFrame:
    return _read_csv(_base_dir() / "output" / "intermediate" / "CHAIN_TIMELINE_ATTRIBUTION.csv")


def _prepare_key_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in ("numero", "family_key", "indice", "latest_indice"):
        if col in out.columns:
            out[col] = out[col].map(_norm_key)
    return out


def _merge_sources(dcc_df: pd.DataFrame) -> pd.DataFrame:
    dcc = _prepare_key_columns(dcc_df)
    register = _prepare_key_columns(_load_chain_register())
    metrics = _prepare_key_columns(_load_chain_metrics())
    scores = _prepare_key_columns(_load_onion_scores())
    narratives = _prepare_key_columns(_load_chain_narratives())

    if dcc.empty:
        return pd.DataFrame()

    merged = dcc.copy()
    if "family_key" not in merged.columns:
        merged["family_key"] = merged["numero"]
    merged["family_key"] = merged["family_key"].map(_norm_key)

    if not register.empty:
        keep = [
            c for c in (
                "family_key",
                "numero",
                "latest_indice",
                "current_state",
                "portfolio_bucket",
                "waiting_primary_flag",
                "waiting_secondary_flag",
                "stale_days",
            )
            if c in register.columns
        ]
        merged = merged.merge(register[keep].drop_duplicates("family_key"), on="family_key", how="left", suffixes=("", "_register"))

    if not metrics.empty:
        keep = [
            c for c in (
                "family_key",
                "open_days",
                "stale_days",
                "primary_wait_days",
                "secondary_wait_days",
                "moex_wait_days",
                "current_state",
            )
            if c in metrics.columns
        ]
        merged = merged.merge(metrics[keep].drop_duplicates("family_key"), on="family_key", how="left", suffixes=("", "_metrics"))

    if not scores.empty:
        keep = [
            c for c in (
                "family_key",
                "normalized_score_100",
                "top_layer_code",
                "top_layer_name",
                "escalation_flag",
            )
            if c in scores.columns
        ]
        merged = merged.merge(scores[keep].drop_duplicates("family_key"), on="family_key", how="left")

    if not narratives.empty:
        keep = [
            c for c in (
                "family_key",
                "executive_summary",
                "primary_driver_text",
                "operational_note",
                "urgency_label",
            )
            if c in narratives.columns
        ]
        merged = merged.merge(narratives[keep].drop_duplicates("family_key"), on="family_key", how="left")

    if "current_state_metrics" in merged.columns:
        merged["current_state"] = merged.get("current_state", "").where(
            merged.get("current_state", "").map(_safe_str) != "",
            merged["current_state_metrics"],
        )
    if "stale_days_metrics" in merged.columns:
        merged["stale_days"] = merged["stale_days_metrics"]
    return merged


def _secondary_tags(row: pd.Series) -> list[str]:
    value = row.get("secondary_tags")
    if isinstance(value, list):
        return [_safe_str(v) for v in value if _safe_str(v)]
    text = _safe_str(value)
    if not text:
        return []
    if text.startswith("["):
        try:
            decoded = json.loads(text.replace("'", '"'))
            if isinstance(decoded, list):
                return [_safe_str(v) for v in decoded if _safe_str(v)]
        except Exception:
            pass
    return [text]


def _is_contractor_tag(tag: str) -> bool:
    return tag in CONTRACTOR_TAGS or tag.startswith("Att Entreprise")


def _is_moex_facile(tag: str) -> bool:
    return tag in MOEX_FACILE_TAGS


def _is_moex_arbitrage(tag: str) -> bool:
    return tag in MOEX_ARBITRAGE_TAGS


def _is_moex_tag(tag: str) -> bool:
    return _is_moex_facile(tag) or _is_moex_arbitrage(tag)


def _is_primary_tag(tag: str) -> bool:
    return tag in PRIMARY_TAGS


def _is_secondary_tag(tag: str) -> bool:
    return tag in SECONDARY_TAGS


def _is_direct_moex_wait(row: pd.Series) -> bool:
    tag = _safe_str(row.get("primary_tag"))
    tier = _safe_str(row.get("focus_owner_tier"))
    return tier == "MOEX" or _is_moex_tag(tag)


def _consultant_days_remaining(row: pd.Series, tag: str) -> tuple[int | None, str]:
    if _is_primary_tag(tag) and "primary_consultant_days_remaining" in row.index:
        value = row.get("primary_consultant_days_remaining")
        if _safe_str(value) != "":
            return _safe_int(value), "primary_consultant_days_remaining"
    if _is_secondary_tag(tag) and "secondary_consultant_days_remaining" in row.index:
        value = row.get("secondary_consultant_days_remaining")
        if _safe_str(value) != "":
            return _safe_int(value), "secondary_consultant_days_remaining"
    value = row.get("consultant_days_remaining")
    if _safe_str(value) != "":
        return _safe_int(value), "consultant_days_remaining"
    return None, ""


def _secondary_backlog_age(row: pd.Series) -> int | None:
    value = row.get("secondary_wait_days")
    if _safe_str(value) != "":
        return max(0, _safe_int(value))
    return None

def _assign_bucket(row: pd.Series) -> str:
    current_state = _safe_str(row.get("current_state"))
    primary_tag = _safe_str(row.get("primary_tag"))
    if current_state in TERMINAL_STATES:
        return ""

    if current_state == "WAITING_CORRECTED_INDICE":
        if _is_contractor_tag(primary_tag):
            return "ENTREPRISE_A_RELANCER"
        return ""

    if current_state == "CHRONIC_REF_CHAIN":
        if _is_contractor_tag(primary_tag):
            return "ENTREPRISE_A_RELANCER"
        return ""

    if _is_primary_tag(primary_tag):
        value = row.get("primary_consultant_days_remaining")
        if _safe_str(value) == "":
            return ""
        remaining = _safe_int(value)
        if remaining < 0:
            return "CONSULTANT_A_ATTAQUER"
        return ""

    if current_state == "OPEN_WAITING_MOEX":
        moex_wait_days = _safe_int(row.get("moex_wait_days"))
        if moex_wait_days > 100:
            return "MOEX_SHAME_INTERNAL"
        if _is_moex_facile(primary_tag):
            return "FERMER_MAINTENANT"
        if _is_moex_arbitrage(primary_tag):
            return "DECISION_MOEX"

    secondary_age = _secondary_backlog_age(row)
    if secondary_age is not None and secondary_age > 0:
        if secondary_age <= 10:
            return ""
        if secondary_age <= 30:
            if _is_moex_facile(primary_tag):
                return "FERMER_MAINTENANT"
            if _is_moex_arbitrage(primary_tag):
                return "DECISION_MOEX"
            return ""
        if secondary_age <= 100:
            return "SECONDAIRE_EXPIRE"
        return "MOEX_SHAME_INTERNAL"

    if (
        _safe_bool(row.get("escalation_flag"))
        and _safe_str(row.get("urgency_label")).upper() in {"CRITICAL", "HIGH"}
    ):
        return "SUJET_REUNION"

    return ""

def _subject_label(row: pd.Series, emetteur_name: str) -> str:
    title = _safe_str(row.get("libelle_du_document"))
    lot = _safe_str(row.get("lot"))
    if emetteur_name and title:
        return f"{emetteur_name} — {title}"
    if lot and title:
        return f"{lot} / {title}"
    return title or lot


def _pick_primary_actor(row: pd.Series) -> str:
    timeline = _load_timeline_attribution()
    numero = _safe_str(row.get("numero"))
    indice = _safe_str(row.get("indice") or row.get("latest_indice"))
    if not timeline.empty:
        sub = timeline[
            (timeline["numero"].map(_safe_str) == numero)
            & (timeline["indice"].map(_safe_str) == indice)
            & (timeline["is_open"].map(_safe_bool))
        ].copy()
        if not sub.empty and "attributed_days" in sub.columns:
            sub["_days"] = sub["attributed_days"].map(_safe_int)
            actor = _safe_str(sub.sort_values("_days", ascending=False).iloc[0].get("attributed_to_actor"))
            if actor:
                return actor
    return _safe_str(row.get("top_layer_name"))


def _actor_to_call(bucket: str, row: pd.Series, emetteur_name: str, primary_actor: str) -> str:
    if bucket in {"FERMER_MAINTENANT", "DECISION_MOEX", "SECONDAIRE_EXPIRE", "MOEX_SHAME_INTERNAL", "SUJET_REUNION"}:
        return "MOEX"
    if bucket == "ENTREPRISE_A_RELANCER":
        return emetteur_name
    if bucket == "CONSULTANT_A_ATTAQUER":
        return primary_actor
    return ""


def _plain_reason(bucket: str, row: pd.Series, primary_actor: str, emetteur_name: str) -> str:
    driver = _safe_str(row.get("primary_driver_text"))
    stale = _safe_int(row.get("stale_days"))
    if bucket == "ENTREPRISE_A_RELANCER":
        return f"L'entreprise doit resoumettre apr?s refus MOEX. Bloqu? depuis {stale} jours."
    if bucket == "CONSULTANT_A_ATTAQUER":
        return f"En attente de {primary_actor} depuis {_days_late(bucket, row)} jours."
    if bucket == "FERMER_MAINTENANT":
        return "Tous les avis sont disponibles. MOEX doit ?mettre le visa."
    if bucket == "DECISION_MOEX":
        return f"MOEX doit arbitrer les avis bloquants. {driver}".strip()
    if bucket == "SECONDAIRE_EXPIRE":
        return f"Le BET secondaire n'a pas r?pondu dans la fen?tre. {driver}".strip()
    if bucket == "MOEX_SHAME_INTERNAL":
        return f"Cette cha?ne expose MOEX en interne depuis {_days_late(bucket, row)} jours. {driver}".strip()
    if bucket == "SUJET_REUNION":
        return f"Sujet ? escalader en r?union. {_safe_str(row.get('executive_summary'))}".strip()
    return ""

def _recommended_action(bucket: str, actor_to_call: str, emetteur_name: str, primary_actor: str) -> str:
    if bucket == "ENTREPRISE_A_RELANCER":
        return f"Relancer {emetteur_name} pour resoumission de l'indice corrigé."
    if bucket == "CONSULTANT_A_ATTAQUER":
        return f"Relancer {primary_actor}; escalader si pas de réponse sous 5 jours."
    if bucket == "FERMER_MAINTENANT":
        return "Émettre le visa global maintenant."
    if bucket == "DECISION_MOEX":
        return "MOEX doit trancher entre les avis BET avant émission du visa."
    if bucket == "SECONDAIRE_EXPIRE":
        return "MOEX doit reprendre la main et émettre/arbitrer le visa."
    if bucket == "MOEX_SHAME_INTERNAL":
        return "Décision MOEX requise immédiatement; remettre le sujet à l'ordre du jour interne."
    if bucket == "SUJET_REUNION":
        return "Mettre à l'ordre du jour de la prochaine réunion de chantier."
    return ""


def _risk_level(row: pd.Series) -> str:
    risk = _safe_str(row.get("urgency_label")).upper()
    if risk in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
        return risk
    score = _safe_float(row.get("normalized_score_100"))
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


def _evidence_summary(row: pd.Series) -> str:
    parts = [_safe_str(row.get("executive_summary")), _safe_str(row.get("operational_note"))]
    text = " | ".join(part for part in parts if part)
    return text[:500]


def _days_late(bucket: str, row: pd.Series) -> int:
    if bucket == "CONSULTANT_A_ATTAQUER":
        primary_value = row.get("primary_consultant_days_remaining")
        if _safe_str(primary_value) != "":
            return max(0, -_safe_int(primary_value))
        remaining, _ = _consultant_days_remaining(row, _safe_str(row.get("primary_tag")))
        if remaining is None:
            return 0
        return max(0, -remaining)

    secondary_age = _secondary_backlog_age(row)
    current_state = _safe_str(row.get("current_state"))
    if bucket == "SECONDAIRE_EXPIRE":
        return secondary_age or 0
    if bucket in {"FERMER_MAINTENANT", "DECISION_MOEX"}:
        if current_state != "OPEN_WAITING_MOEX" and secondary_age is not None and secondary_age > 10:
            return secondary_age
        return _safe_int(row.get("moex_wait_days"))
    if bucket == "MOEX_SHAME_INTERNAL":
        if current_state == "OPEN_WAITING_MOEX":
            return _safe_int(row.get("moex_wait_days"))
        return secondary_age or 0
    return _safe_int(row.get("stale_days") or row.get("open_days"))

def _internal_moex_exposure(bucket: str, row: pd.Series) -> bool:
    return bucket == "MOEX_SHAME_INTERNAL" or (
        _safe_str(row.get("top_layer_code")) == "L5_MOEX_ARBITRATION_DELAY" and _is_direct_moex_wait(row)
    )


def _external_attackable(bucket: str, row: pd.Series) -> bool:
    if bucket in {"ENTREPRISE_A_RELANCER", "CONSULTANT_A_ATTAQUER"}:
        return True
    return _safe_str(row.get("top_layer_code")) in {
        "L1_CONTRACTOR_QUALITY",
        "L3_PRIMARY_CONSULTANT_DELAY",
        "L4_SECONDARY_CONSULTANT_DELAY",
    }


def _rows_for_numero(df: pd.DataFrame, numero: str) -> pd.DataFrame:
    if df is None or df.empty or "numero" not in df.columns:
        return pd.DataFrame()
    return df[df["numero"].map(_safe_str) == numero].copy()


def _collect_evidence(ctx: Any, numero: str) -> dict[str, Any]:
    docs = _rows_for_numero(getattr(ctx, "docs_df", pd.DataFrame()), numero)
    responses = getattr(ctx, "responses_df", pd.DataFrame())
    if docs.empty or responses is None or responses.empty or "doc_id" not in docs.columns:
        empty_json = "[]"
        return {
            "chain_observations_summary": "",
            "chain_observations_full": empty_json,
            "chain_observations_refs": empty_json,
            "consultant_reports_summary": "",
            "consultant_reports_full": empty_json,
            "consultant_reports_refs": empty_json,
            "consultant_reports_available": False,
        }

    doc_id_to_indice = {row["doc_id"]: _safe_str(row.get("indice")) for _, row in docs.iterrows()}
    sub = responses[responses["doc_id"].isin(doc_id_to_indice.keys())].copy()
    observations = []
    reports = []
    for _, resp in sub.iterrows():
        comment = _safe_str(resp.get("response_comment"))
        status = _safe_str(resp.get("status_clean"))
        reviewer = _safe_str(resp.get("approver_canonical") or resp.get("approver_raw"))
        if not (comment or status):
            continue
        record = {
            "indice": doc_id_to_indice.get(resp.get("doc_id"), ""),
            "reviewer": reviewer,
            "status": status,
            "comment": comment,
        }
        observations.append(record)
        source = _safe_str(resp.get("effective_source"))
        if source in REPORT_SOURCE_VALUES:
            report = dict(record)
            report["effective_source"] = source
            reports.append(report)

    obs_summary = "; ".join(
        f"{r['indice']} {r['reviewer']} {r['status']}".strip()
        for r in observations[:3]
        if r.get("reviewer") or r.get("status")
    )
    report_summary = "; ".join(
        f"{r['indice']} {r['reviewer']} {r['status']}".strip()
        for r in reports[:3]
        if r.get("reviewer") or r.get("status")
    )
    return {
        "chain_observations_summary": obs_summary,
        "chain_observations_full": json.dumps(observations, ensure_ascii=False),
        "chain_observations_refs": json.dumps([r.get("indice", "") for r in observations if r.get("indice")], ensure_ascii=False),
        "consultant_reports_summary": report_summary,
        "consultant_reports_full": json.dumps(reports, ensure_ascii=False),
        "consultant_reports_refs": json.dumps([r.get("indice", "") for r in reports if r.get("indice")], ensure_ascii=False),
        "consultant_reports_available": bool(reports),
    }


def _build_output_row(ctx: Any, row: pd.Series, bucket: str) -> dict[str, Any]:
    numero = _safe_str(row.get("numero"))
    indice = _safe_str(row.get("indice") or row.get("latest_indice"))
    family_key = _safe_str(row.get("family_key") or numero)
    emetteur_code = _safe_str(row.get("emetteur"))
    emetteur_name = resolve_emetteur_name(emetteur_code) if emetteur_code else ""
    primary_actor = _pick_primary_actor(row)
    actor = _actor_to_call(bucket, row, emetteur_name, primary_actor)
    evidence = _collect_evidence(ctx, numero)

    out = {
        "item_id": f"{family_key}__{indice}",
        "numero": numero,
        "indice": indice,
        "family_key": family_key,
        "subject_label": _subject_label(row, emetteur_name),
        "emetteur_code": emetteur_code,
        "emetteur_name": emetteur_name,
        "primary_actor": primary_actor,
        "actor_to_call": actor,
        "action_bucket": bucket,
        "action_label": ACTION_LABELS.get(bucket, bucket),
        "plain_reason": _plain_reason(bucket, row, primary_actor, emetteur_name),
        "recommended_action": _recommended_action(bucket, actor, emetteur_name, primary_actor),
        "risk_level": _risk_level(row),
        "evidence_summary": _evidence_summary(row),
        "days_open": _safe_int(row.get("open_days")),
        "days_late": _days_late(bucket, row),
        "current_state": _safe_str(row.get("current_state")),
        "normalized_score_100": _safe_float(row.get("normalized_score_100")),
        "is_internal_moex_exposure": _internal_moex_exposure(bucket, row),
        "is_external_attackable": _external_attackable(bucket, row),
    }
    out.update(evidence)
    return out


def build_counter_attack_items(ctx: Any, output_dir: Path) -> Path:
    """Build the reconstructed Counter-Attack CSV and return its path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "COUNTER_ATTACK_ITEMS.csv"

    dcc_df = compute_dcc_tags_bulk(ctx)
    if dcc_df is None or dcc_df.empty:
        empty = pd.DataFrame(columns=OUTPUT_COLUMNS)
        empty.to_csv(out_path, index=False, encoding="utf-8")
        return out_path

    merged = _merge_sources(dcc_df)
    if merged.empty:
        empty = pd.DataFrame(columns=OUTPUT_COLUMNS)
        empty.to_csv(out_path, index=False, encoding="utf-8")
        return out_path

    if "focus_owner_tier" in merged.columns:
        merged = merged[merged["focus_owner_tier"].map(_safe_str) != "CLOSED"].copy()

    rows = []
    for _, row in merged.iterrows():
        bucket = _assign_bucket(row)
        if not bucket:
            continue
        rows.append(_build_output_row(ctx, row, bucket))

    result = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if not result.empty:
        result = result.drop_duplicates(subset=["family_key"], keep="first")
        result = result.drop_duplicates(subset=["numero", "indice"], keep="first")
        result = result.sort_values(["action_bucket", "days_late", "numero", "indice"], kind="mergesort")
    for column in OUTPUT_COLUMNS:
        if column not in result.columns:
            result[column] = ""
    result = result[OUTPUT_COLUMNS]
    for column in IDENTITY_COLUMNS:
        result[column] = result[column].map(_safe_str)
    result.to_csv(out_path, index=False, encoding="utf-8")
    return out_path
