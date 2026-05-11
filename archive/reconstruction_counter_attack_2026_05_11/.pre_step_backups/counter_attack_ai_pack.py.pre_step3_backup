"""Phase 6D — JANSA AI Audit Pack generator.

Builds a deterministic ZIP under output/exports/ that bundles JANSA evidence
artifacts (Counter-Attack items, Chain+Onion CSVs, chain timeline attribution,
Flat-GED extract, optional dossiers) plus a French-first README and five
French-first PROMPTS for an external AI audit.

Public entrypoint:
    build_ai_audit_pack(ctx: RunContext, output_dir: Path) -> dict

Contract:
- No AI API call. No DB write. No deterministic-artifact mutation.
- Identity columns (numero, indice, doc_id, family_key, emetteur_code,
  item_id) are read and written as strings, leading zeros preserved.
- Missing required source files -> clean error payload, no exception.
- Missing optional source files -> recorded in missing_optional_files,
  pack still ships.
- Same RunContext + same on-disk artifacts -> byte-identical pack
  contents (modulo the timestamp embedded in the ZIP filename).
"""
from __future__ import annotations

import csv
import io
import logging
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ── Module-level constants ─────────────────────────────────────
PACK_FILENAME_TEMPLATE: str = "JANSA_AI_AUDIT_PACK_{ts}.zip"

REQUIRED_FILES: Dict[str, str] = {
    "DATA/01_COUNTER_ATTACK_ITEMS.csv":         "output/intermediate/COUNTER_ATTACK_ITEMS.csv",
    "DATA/02_CHAIN_EVENTS.csv":                 "output/chain_onion/CHAIN_EVENTS.csv",
    "DATA/03_CHAIN_REGISTER.csv":               "output/chain_onion/CHAIN_REGISTER.csv",
    "DATA/04_CHAIN_VERSIONS.csv":               "output/chain_onion/CHAIN_VERSIONS.csv",
    "DATA/05_CHAIN_NARRATIVES.csv":             "output/chain_onion/CHAIN_NARRATIVES.csv",
    "DATA/06_ONION_LAYERS.csv":                 "output/chain_onion/ONION_LAYERS.csv",
    "DATA/07_ONION_SCORES.csv":                 "output/chain_onion/ONION_SCORES.csv",
    "DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv":   "output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv",
    "DATA/09_FLAT_GED_EXTRACT.csv":             "<BUILT>",
    "README_FOR_AI.md":                         "<GENERATED>",
    "PROMPTS/01_GENERAL_MOEX_AUDIT.md":         "<GENERATED>",
    "PROMPTS/02_SIX_ATTACK_ANGLES.md":          "<GENERATED>",
    "PROMPTS/03_CONTRACTOR_BEHAVIOR_AUDIT.md":  "<GENERATED>",
    "PROMPTS/04_CONSULTANT_BEHAVIOR_AUDIT.md":  "<GENERATED>",
    "PROMPTS/05_MEETING_AGENDA_GENERATOR.md":   "<GENERATED>",
}

OPTIONAL_FILES: Dict[str, str] = {
    "DATA/SUBJECT_RISK_DOSSIERS.csv":           "output/intermediate/SUBJECT_RISK_DOSSIERS.csv",
    "DATA/ACTOR_ATTACK_DOSSIERS.csv":           "output/intermediate/ACTOR_ATTACK_DOSSIERS.csv",
    "DATA/dashboard_summary.json":              "output/chain_onion/dashboard_summary.json",
    "DATA/top_issues.json":                     "output/chain_onion/top_issues.json",
}

_IDENTITY_DTYPES: Dict[str, str] = {
    "numero":          "string",
    "indice":          "string",
    "family_key":      "string",
    "doc_id":          "string",
    "emetteur_code":   "string",
    "item_id":         "string",
    "version_key":     "string",
}

_BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Final column order for 09_FLAT_GED_EXTRACT.csv (per §10.3 of the phase plan).
_FLAT_GED_COLUMNS_FULL: List[str] = [
    "numero",
    "indice",
    "doc_id",
    "emetteur_code",
    "emetteur_canonical",
    "titre",
    "lot",
    "lot_normalized",
    "created_at",
    "visa_global",
    "approver_raw",
    "approver_canonical",
    "is_exception_approver",
    "status_clean",
    "date_status_type",
    "date_answered",
    "date_limite",
    "response_comment",
    "effective_source",
    "report_memory_applied",
]


# ── Public entrypoint ──────────────────────────────────────────
def build_ai_audit_pack(ctx: "RunContext", output_dir: Path) -> dict:
    """Build the JANSA AI Audit Pack ZIP under output_dir.

    Returns a dict matching the success or failure payload shape defined in
    §10.8 of the phase plan. Never raises to the caller.
    """
    try:
        err = _validate_inputs(ctx, output_dir)
        if err is not None:
            return _failure_payload(err)

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return _failure_payload(
                f"output/exports/ not writable: {type(e).__name__}: {e}"
            )

        missing_required = _check_required_sources_on_disk()
        if missing_required:
            first_pack_path = missing_required[0]
            disk = REQUIRED_FILES[first_pack_path]
            return _failure_payload(
                f"Required source missing: {disk}. "
                f"Run scripts/build_counter_attack.py first."
            )

        try:
            flat_df = _build_flat_ged_extract(ctx)
        except Exception as e:
            return _failure_payload(
                f"Flat-GED extract failed: {type(e).__name__}: {e}"
            )

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = PACK_FILENAME_TEMPLATE.format(ts=ts)
        zip_path = output_dir / filename

        included: List[str] = []
        missing_optional = _check_optional_sources_on_disk()

        try:
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for pack_path, src in REQUIRED_FILES.items():
                    if src == "<BUILT>":
                        _write_built_csv(flat_df, zf, pack_path)
                        included.append(pack_path)
                    elif src == "<GENERATED>":
                        text = _render_generated_text(pack_path, ctx)
                        _write_generated_text(text, zf, pack_path)
                        included.append(pack_path)
                    else:
                        disk_path = _BASE_DIR / src
                        _copy_required_csv(disk_path, zf, pack_path)
                        included.append(pack_path)

                for pack_path, src in OPTIONAL_FILES.items():
                    disk_path = _BASE_DIR / src
                    if disk_path.exists():
                        zf.write(disk_path, arcname=pack_path)
                        included.append(pack_path)
        except Exception as e:
            try:
                if zip_path.exists():
                    zip_path.unlink()
            except Exception:
                pass
            return _failure_payload(
                f"ZIP write failed: {type(e).__name__}: {e}"
            )

        return _success_payload(zip_path, included, missing_optional)
    except Exception as e:
        return _failure_payload(f"Unexpected: {type(e).__name__}: {e}")


# ── Internal helpers ───────────────────────────────────────────
def _validate_inputs(ctx, output_dir) -> Optional[str]:
    if ctx is None:
        return "ctx is None"
    if output_dir is None:
        return "output_dir is None"
    docs = getattr(ctx, "docs_df", None)
    if docs is None:
        return "ctx.docs_df is None"
    try:
        if hasattr(docs, "empty") and docs.empty:
            return "ctx.docs_df is empty"
    except Exception:
        pass
    resp = getattr(ctx, "responses_df", None)
    if resp is None:
        return "ctx.responses_df is None"
    try:
        if hasattr(resp, "empty") and resp.empty:
            return "ctx.responses_df is empty"
    except Exception:
        pass
    return None


def _check_required_sources_on_disk() -> List[str]:
    missing: List[str] = []
    for pack_path, src in REQUIRED_FILES.items():
        if src in ("<BUILT>", "<GENERATED>"):
            continue
        if not (_BASE_DIR / src).exists():
            missing.append(pack_path)
    return missing


def _check_optional_sources_on_disk() -> List[str]:
    missing: List[str] = []
    for pack_path, src in OPTIONAL_FILES.items():
        if not (_BASE_DIR / src).exists():
            missing.append(pack_path)
    return missing


def _build_flat_ged_extract(ctx) -> pd.DataFrame:
    """Build the 09_FLAT_GED_EXTRACT.csv DataFrame per §10.3."""
    docs = ctx.docs_df.copy()
    resp = ctx.responses_df.copy()

    # Runtime probe: numero dtype
    numero_dtype = str(docs["numero"].dtype) if "numero" in docs.columns else "<missing>"
    if numero_dtype in ("object", "string"):
        chosen_numero = "numero"
    else:
        chosen_numero = "numero_normalized"
        if "numero_normalized" in docs.columns:
            docs["numero"] = docs["numero_normalized"]
    print(f"[ai_pack] numero dtype: {numero_dtype}, source: {chosen_numero}")

    # Runtime probe: emetteur_code presence
    if "emetteur" in docs.columns:
        has_emetteur_code = True
        print("[ai_pack] emetteur source: docs_df['emetteur'] present (kept as emetteur_code)")
    else:
        has_emetteur_code = False
        print("[ai_pack] emetteur source: docs_df['emetteur'] missing -> drop emetteur_code, keep emetteur_canonical only")

    doc_cols = ["doc_id", "numero", "indice", "titre", "lot", "lot_normalized",
                "emetteur_canonical", "created_at"]
    if has_emetteur_code:
        doc_cols.append("emetteur")
    available = [c for c in doc_cols if c in docs.columns]
    doc_frame = docs[available].copy()
    if has_emetteur_code:
        doc_frame = doc_frame.rename(columns={"emetteur": "emetteur_code"})

    # visa_global from flat_ged_doc_meta (no engine call)
    fgdm = getattr(ctx, "flat_ged_doc_meta", None) or {}

    def _visa_for(did):
        meta = fgdm.get(did, {}) if isinstance(fgdm, dict) else {}
        if not isinstance(meta, dict):
            return ""
        v = meta.get("visa_global", "")
        return v if isinstance(v, str) else ""

    doc_frame["visa_global"] = doc_frame["doc_id"].map(_visa_for).fillna("")

    resp_cols = [
        "doc_id", "approver_raw", "approver_canonical", "is_exception_approver",
        "status_clean", "date_status_type", "date_answered", "date_limite",
        "response_comment", "effective_source", "report_memory_applied",
    ]
    resp_available = [c for c in resp_cols if c in resp.columns]
    resp_frame = resp[resp_available].copy()
    if "effective_source" not in resp_frame.columns:
        resp_frame["effective_source"] = ""
    if "report_memory_applied" not in resp_frame.columns:
        resp_frame["report_memory_applied"] = pd.NA

    merged = doc_frame.merge(resp_frame, on="doc_id", how="left")

    for col in ("created_at", "date_answered", "date_limite"):
        if col in merged.columns:
            merged[col] = (
                pd.to_datetime(merged[col], errors="coerce")
                .dt.strftime("%Y-%m-%d")
                .fillna("")
            )

    for col in ("numero", "indice", "doc_id", "emetteur_code"):
        if col in merged.columns:
            merged[col] = merged[col].astype("string")

    final_cols = list(_FLAT_GED_COLUMNS_FULL)
    if not has_emetteur_code:
        final_cols = [c for c in final_cols if c != "emetteur_code"]

    for c in final_cols:
        if c not in merged.columns:
            merged[c] = pd.NA

    out = merged[final_cols].copy()

    sort_keys = ["numero", "indice", "doc_id", "approver_canonical"]
    sort_keys = [k for k in sort_keys if k in out.columns]
    out = out.sort_values(
        by=sort_keys,
        kind="mergesort",
        na_position="last",
        ascending=True,
    ).reset_index(drop=True)

    return out


def _copy_required_csv(src_disk_path: Path, zf: zipfile.ZipFile, pack_path: str) -> None:
    """Byte-for-byte copy of a deterministic source CSV into the ZIP."""
    zf.write(src_disk_path, arcname=pack_path)


def _write_built_csv(df: pd.DataFrame, zf: zipfile.ZipFile, pack_path: str) -> None:
    """Serialize the in-memory DataFrame to CSV and write into the ZIP."""
    buf = io.StringIO()
    df.to_csv(
        buf,
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
        encoding="utf-8",
        index=False,
    )
    zf.writestr(pack_path, buf.getvalue().encode("utf-8"))


def _write_generated_text(text: str, zf: zipfile.ZipFile, pack_path: str) -> None:
    """Write a UTF-8 string as a file inside the ZIP, LF line endings, no BOM."""
    zf.writestr(pack_path, text.encode("utf-8"))


def _render_generated_text(pack_path: str, ctx) -> str:
    if pack_path == "README_FOR_AI.md":
        return _render_readme_for_ai(ctx)
    if pack_path == "PROMPTS/01_GENERAL_MOEX_AUDIT.md":
        return _render_prompt_general_moex_audit()
    if pack_path == "PROMPTS/02_SIX_ATTACK_ANGLES.md":
        return _render_prompt_six_attack_angles()
    if pack_path == "PROMPTS/03_CONTRACTOR_BEHAVIOR_AUDIT.md":
        return _render_prompt_contractor_behavior_audit()
    if pack_path == "PROMPTS/04_CONSULTANT_BEHAVIOR_AUDIT.md":
        return _render_prompt_consultant_behavior_audit()
    if pack_path == "PROMPTS/05_MEETING_AGENDA_GENERATOR.md":
        return _render_prompt_meeting_agenda_generator()
    raise ValueError(f"Unknown generated pack path: {pack_path}")


def _success_payload(zip_path: Path, included: List[str], missing_opt: List[str]) -> dict:
    return {
        "success": True,
        "path": os.fspath(zip_path.resolve()),
        "filename": zip_path.name,
        "included_files": list(included),
        "missing_optional_files": list(missing_opt),
        "error": None,
    }


def _failure_payload(error_msg: str) -> dict:
    return {
        "success": False,
        "path": None,
        "filename": None,
        "included_files": [],
        "missing_optional_files": [],
        "error": error_msg,
    }


# ── Generated text bodies (verbatim from §10.6 / §10.7) ─────────
def _render_readme_for_ai(ctx) -> str:
    return """# JANSA — Pack Audit IA (lecture obligatoire)

## 1. Objet du pack

Ce dossier ZIP contient les preuves opérationnelles d'un projet de chantier
suivi par l'équipe MOEX (Maîtrise d'Œuvre d'Exécution) JANSA. Votre rôle, en
tant qu'IA externe, est d'auditer ces preuves selon les six angles d'attaque
acceptés (voir §3) et de produire des constats sourcés.

Le pack a été généré automatiquement par JANSA. Aucune information n'a été
résumée, retraitée, ou inventée pour vous : vous lisez les mêmes données que
l'équipe MOEX.

## 2. Source des données

| Fichier | Origine | Niveau |
|---|---|---|
| `DATA/01_COUNTER_ATTACK_ITEMS.csv` | Plan d'action MOEX (Phase 6A/6X) | Sujet |
| `DATA/02_CHAIN_EVENTS.csv` | Moteur Chain+Onion | Événement |
| `DATA/03_CHAIN_REGISTER.csv` | Moteur Chain+Onion | Chaîne |
| `DATA/04_CHAIN_VERSIONS.csv` | Moteur Chain+Onion | Version d'indice |
| `DATA/05_CHAIN_NARRATIVES.csv` | Moteur Chain+Onion | Narratif par chaîne |
| `DATA/06_ONION_LAYERS.csv` | Moteur Onion | Couche d'enjeu |
| `DATA/07_ONION_SCORES.csv` | Moteur Onion | Score agrégé |
| `DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv` | Attribution de chronologie | Phase de cycle |
| `DATA/09_FLAT_GED_EXTRACT.csv` | GED projetée (docs ⨯ réponses) | Document/réponse |
| `DATA/SUBJECT_RISK_DOSSIERS.csv` (facultatif) | Dossier sujet | Sujet |
| `DATA/ACTOR_ATTACK_DOSSIERS.csv` (facultatif) | Dossier acteur | Acteur |
| `DATA/dashboard_summary.json` (facultatif) | Synthèse dashboard | Projet |
| `DATA/top_issues.json` (facultatif) | Top sujets prioritaires | Projet |

## 3. Six angles d'attaque acceptés

1. **CROSS_NUMERO_RESUBMISSION** — un document refusé sous un numéro réapparaît sous un autre.
2. **SAS_REF_DISEASE** — une entreprise accumule des SAS REF, surtout en indice A ou après correction.
3. **CONSULTANT_POSITION_SHIFT** — un consultant change d'avis entre indices (VAO puis REF).
4. **CONSULTANT_COMMENT_INFLATION** — un consultant ajoute beaucoup de commentaires tardivement, signe d'une première revue faible.
5. **LATE_SECONDARY_DISRUPTS_VISA** — un consultant secondaire répond après le visa MOEX, avec REF / SUS / avis contraire.
6. **CONTRACTOR_FAKE_CORRECTION** — l'entreprise resoumet mais les mêmes commentaires bloquants reviennent.

## 4. Ce que l'IA DOIT faire

- Lire les CSV avec les colonnes d'identité (`numero`, `indice`, `doc_id`, `family_key`, `emetteur_code`, `item_id`) en chaîne de caractères pour conserver les zéros de tête.
- Citer chaque constat avec au minimum `family_key` et `numero` (et `indice` si pertinent).
- Justifier chaque sévérité par les colonnes utilisées (ex. `CHAIN_EVENTS.is_blocking`, `ONION_SCORES.normalized_score_100`).
- Suivre les prompts dans `PROMPTS/` un à un, dans l'ordre.

## 5. Ce que l'IA NE DOIT PAS faire

- Inventer un numéro, un acteur, un commentaire, ou une date qui n'apparaît pas dans les CSV.
- Remplacer ou recalculer les buckets JANSA (`action_bucket` dans `01_COUNTER_ATTACK_ITEMS.csv`). Vous pouvez signaler des sujets, jamais réclasser.
- Reproduire des données personnelles au-delà de ce qui est déjà dans les CSV.
- Produire un constat sans citation `family_key` / `numero`.
- Sortir du périmètre des six angles d'attaque listés au §3.

## 6. Comment lire chaque CSV

- **`01_COUNTER_ATTACK_ITEMS.csv`** — 28 colonnes. Une ligne = un sujet à traiter. Colonnes clés : `item_id`, `numero`, `indice`, `family_key`, `subject_label`, `action_bucket`, `action_label`, `plain_reason`, `recommended_action`, `risk_level`, `evidence_summary`, `days_open`, `days_late`, `current_state`, `is_internal_moex_exposure`, `is_external_attackable`, `chain_observations_full`, `consultant_reports_full`.
- **`02_CHAIN_EVENTS.csv`** — 18 colonnes. Une ligne = un événement de chaîne. Colonnes clés : `family_key`, `version_key`, `event_seq`, `event_date`, `actor`, `actor_type`, `step_type`, `status`, `is_blocking`, `is_completed`, `requires_new_cycle`, `delay_contribution_days`, `issue_signal`.
- **`03_CHAIN_REGISTER.csv`** — 23 colonnes. Une ligne = une chaîne (un sujet documentaire suivi sur plusieurs indices). Colonnes clés : `family_key`, `numero`, `total_versions`, `latest_indice`, `current_state`, `portfolio_bucket`, `stale_days`, `operational_relevance_score`.
- **`04_CHAIN_VERSIONS.csv`** — 14 colonnes. Une ligne = une version d'indice. Colonnes clés : `family_key`, `version_key`, `numero`, `indice`, `has_blocking_rows`, `requires_new_cycle_flag`.
- **`05_CHAIN_NARRATIVES.csv`** — 15 colonnes. Une ligne = un narratif synthétique par chaîne. Colonnes clés : `family_key`, `executive_summary`, `primary_driver_text`, `secondary_driver_text`, `recommended_focus`, `urgency_label`, `confidence_label`, `normalized_score_100`.
- **`06_ONION_LAYERS.csv`** — 18 colonnes. Une ligne = une couche d'enjeu. Colonnes clés : `family_key`, `layer_code`, `layer_name`, `issue_type`, `severity_raw`, `confidence_raw`, `evidence_count`, `pressure_index`.
- **`07_ONION_SCORES.csv`** — 22 colonnes. Une ligne = score agrégé par chaîne. Colonnes clés : `family_key`, `total_onion_score`, `normalized_score_100`, `top_layer_code`, `contractor_impact_score`, `sas_impact_score`, `consultant_primary_impact_score`, `consultant_secondary_impact_score`, `moex_impact_score`, `contradiction_impact_score`, `escalation_flag`.
- **`08_CHAIN_TIMELINE_ATTRIBUTION.csv`** — 14 colonnes. Une ligne = une phase de cycle attribuée à un acteur. Colonnes clés : `family_key`, `numero`, `indice`, `phase`, `days_actual`, `days_expected`, `delay_days`, `attributed_to_actor`, `attributed_to_tier`, `attributed_days`.
- **`09_FLAT_GED_EXTRACT.csv`** — 20 colonnes. Une ligne = un document × une réponse (ou un document sans réponse). Colonnes clés : `numero`, `indice`, `doc_id`, `emetteur_canonical`, `titre`, `visa_global`, `approver_canonical`, `status_clean`, `date_status_type`, `date_answered`, `date_limite`, `response_comment`, `effective_source`.

## 7. Comment utiliser les fichiers PROMPTS/

Lisez les fichiers `PROMPTS/01` à `PROMPTS/05` dans l'ordre. Chaque prompt définit un objectif, les CSV à inspecter, le format de sortie attendu, et la règle d'or (interdiction d'inventer). N'enchaînez pas les prompts sans avoir produit la sortie du précédent.

## 8. Glossaire

- **MOEX** — Maîtrise d'Œuvre d'Exécution. L'équipe qui pilote le chantier côté maître d'ouvrage.
- **SAS** — Bureau de Contrôle Safety Assurance. Premier filtre conformité avant la chaîne consultant complète.
- **REF** — Refusé. Statut d'un visa.
- **VAO** — Visé Avec Observations.
- **VSO** — Visé Sans Observations.
- **EMD** — Émetteur (entreprise qui soumet le document).
- **family_key** — clé d'identification d'une chaîne documentaire (un sujet suivi sur plusieurs indices).
- **numero** — numéro GED du document (chaîne, zéros de tête conservés).
- **indice** — version du document (A, B, C...).

---

### Note for English-speaking AI

This pack contains French-language project data from a French construction
project. The CSV column names are stable identifiers (English-like) but the
free-text fields (`response_comment`, `executive_summary`,
`primary_driver_text`, `subject_label`, `plain_reason`,
`recommended_action`) are in French. The five PROMPTS files in `PROMPTS/`
are written in French and define the audit scope. Do not translate the
column names; do read the French free-text. Cite findings using
`family_key` and `numero`. Follow the §5 prohibition on invention.
"""


def _render_prompt_general_moex_audit() -> str:
    return """# Prompt 01 — Audit MOEX général

## Objectif
Identifier les 10 chaînes documentaires les plus dangereuses pour MOEX en ce moment, tous angles confondus.

## CSV à inspecter
- `DATA/01_COUNTER_ATTACK_ITEMS.csv`
- `DATA/03_CHAIN_REGISTER.csv`
- `DATA/05_CHAIN_NARRATIVES.csv`
- `DATA/07_ONION_SCORES.csv`
- `DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv`

## Méthode
1. Joindre `01_COUNTER_ATTACK_ITEMS` (sur `family_key`) avec `07_ONION_SCORES` (`normalized_score_100`, `escalation_flag`) et `05_CHAIN_NARRATIVES` (`urgency_label`, `recommended_focus`).
2. Filtrer sur `escalation_flag == True` OR `normalized_score_100 >= 70` OR `risk_level == "HIGH"`.
3. Trier par `normalized_score_100` décroissant.
4. Garder les 10 premières chaînes uniques par `family_key`.

## Format de sortie
Un tableau avec : `rang`, `family_key`, `numero`, `indice`, `subject_label`, `urgency_label`, `normalized_score_100`, `risque_principal_2_lignes`, `action_recommandée_1_ligne`.

## Règle d'or
Ne jamais inventer un `family_key` ou un `numero` qui n'apparaît pas dans les CSV. Ne jamais réécrire `action_bucket`. Si moins de 10 chaînes remplissent les critères, dites-le explicitement.
"""


def _render_prompt_six_attack_angles() -> str:
    return """# Prompt 02 — Six angles d'attaque

## Objectif
Pour chacun des six angles définis au §3 du `README_FOR_AI.md`, produire les constats sourcés.

## Format de sortie commun (par constat)
| Champ | Description |
|---|---|
| `family_key` | clé de la chaîne |
| `numero` | numéro GED |
| `indice` | indice incriminé |
| `evidence_columns_cited` | liste des colonnes utilisées comme preuve |
| `severity_estimate` | LOW / MEDIUM / HIGH (avec justification chiffrée) |
| `recommended_action` | une phrase, en français, opérationnelle |

Si l'angle n'est pas soutenu par les données, écrivez explicitement : « Aucun constat — données insuffisantes » et passez au suivant.

## Angle 1 — CROSS_NUMERO_RESUBMISSION
- À chercher : un document refusé sous un `numero` qui réapparaît, sous un autre `numero`, avec le même `emetteur_code`/`emetteur_canonical` et un `titre` similaire.
- CSV : `09_FLAT_GED_EXTRACT.csv` (joindre par `emetteur_canonical` + similarité `titre`), recouper avec `03_CHAIN_REGISTER.csv` pour le `current_state`.
- Indices forts : `status_clean == "REF"` sur l'ancien `numero`, `created_at` postérieur sur le nouveau, mêmes mots-clés dans `titre`.

## Angle 2 — SAS_REF_DISEASE
- À chercher : entreprises avec un nombre élevé de réponses `0-SAS` REF ou `SAS REF`.
- CSV : `09_FLAT_GED_EXTRACT.csv` (`approver_raw == "0-SAS"` AND `status_clean` contient "REF") agrégé par `emetteur_canonical`. Recouper avec `07_ONION_SCORES.sas_impact_score`.
- Indices forts : ratio SAS REF / SAS total > 30 %, ou répétition après correction (même `family_key`, indice B+).

## Angle 3 — CONSULTANT_POSITION_SHIFT
- À chercher : un même `approver_canonical` change de statut (VAO → REF, ou inverse) entre deux indices d'une même chaîne.
- CSV : `09_FLAT_GED_EXTRACT.csv` agrégé par (`family_key` ou `numero`, `approver_canonical`), trier par `indice`. Recouper avec `02_CHAIN_EVENTS.csv` (`actor`, `status`, `is_blocking`).
- Indices forts : VAO en indice A puis REF en indice B sans nouveau commentaire substantiel.

## Angle 4 — CONSULTANT_COMMENT_INFLATION
- À chercher : un consultant primaire avec peu de commentaires en première revue, beaucoup en revue tardive.
- CSV : `09_FLAT_GED_EXTRACT.csv` (longueur de `response_comment` par `(family_key, approver_canonical, indice)`). Recouper avec `07_ONION_SCORES.consultant_primary_impact_score`.
- Indices forts : longueur de `response_comment` indice A < 50 caractères ET indice B > 300 caractères pour le même `approver_canonical`.

## Angle 5 — LATE_SECONDARY_DISRUPTS_VISA
- À chercher : un consultant secondaire (`actor_type` distinct de `MOEX_PRIMARY`) répond après le visa MOEX et provoque un nouveau cycle.
- CSV : `02_CHAIN_EVENTS.csv` (filtrer `actor_type` secondaire, `event_date` postérieur au MOEX visa de la même chaîne, `status ∈ {REF, SUS}` ou `requires_new_cycle == True`). Recouper avec `08_CHAIN_TIMELINE_ATTRIBUTION.csv` (`attributed_to_tier`, `attributed_days`).
- Indices forts : `is_blocking == True` côté secondaire APRÈS la phase MOEX, `attributed_days > 0` sur le secondaire.

## Angle 6 — CONTRACTOR_FAKE_CORRECTION
- À chercher : entreprise resoumet (nouvel `indice`) mais les mêmes commentaires bloquants reviennent.
- CSV : `09_FLAT_GED_EXTRACT.csv` (mêmes mots-clés dans `response_comment` entre indices). Recouper avec `02_CHAIN_EVENTS.csv` (`is_blocking`, `issue_signal`) et `07_ONION_SCORES.contractor_impact_score`.
- Indices forts : `requires_new_cycle == True` sur deux indices consécutifs avec `actor_type` consultant identique.

## Règle d'or
Aucun constat sans citation `family_key` + `numero`. Aucune réécriture des buckets JANSA. Si l'angle n'est pas soutenu : « Aucun constat — données insuffisantes ».
"""


def _render_prompt_contractor_behavior_audit() -> str:
    return """# Prompt 03 — Audit comportement entreprise (côté CONTRACTOR)

## Objectif
Identifier les entreprises (emetteur) dont le comportement de soumission révèle un risque opérationnel.

## CSV à inspecter
- `DATA/03_CHAIN_REGISTER.csv` (`family_key`, `numero`, `total_versions`, `total_blocking_versions`, `requires_new_cycle_flag`, `current_state`, `stale_days`)
- `DATA/04_CHAIN_VERSIONS.csv` (`requires_new_cycle_flag`, `has_blocking_rows`, `blocking_actor_count`)
- `DATA/06_ONION_LAYERS.csv` (filtrer `layer_code` côté contracteur, ex. `L1_CONTRACTOR_QUALITY`)
- `DATA/07_ONION_SCORES.csv` (`contractor_impact_score`, `sas_impact_score`)
- `DATA/09_FLAT_GED_EXTRACT.csv` (`emetteur_canonical`, `approver_raw == "0-SAS"`, `status_clean`)

## Patterns recherchés
1. **CONTRACTOR_FAKE_CORRECTION** : indice B+ avec `requires_new_cycle_flag == True` sur la même chaîne.
2. **SAS_REF répétés** : agrégation par `emetteur_canonical` du nombre de SAS REF ; outliers (>10 sur le projet, ou >30 % du total SAS de l'entreprise).
3. **Churn d'indices** : chaînes avec `total_versions > 4` et `current_state` toujours bloquant.

## Format de sortie
Un tableau par entreprise : `emetteur_canonical`, `nombre_chaînes_concernées`, `pattern`, `family_keys_exemples (max 3)`, `contractor_impact_score`, `sas_impact_score`, `recommended_action`.

## Règle d'or
Ne jamais inventer une entreprise. N'utilisez `emetteur_canonical` que tel qu'il apparaît dans les CSV. Si aucun pattern ne sort : « Aucun constat — données insuffisantes ».
"""


def _render_prompt_consultant_behavior_audit() -> str:
    return """# Prompt 04 — Audit comportement consultant

## Objectif
Identifier les consultants (primaires et secondaires) dont le comportement révèle un risque opérationnel pour MOEX.

## CSV à inspecter
- `DATA/02_CHAIN_EVENTS.csv` (`actor`, `actor_type`, `step_type`, `status`, `is_blocking`, `event_date`, `delay_contribution_days`)
- `DATA/06_ONION_LAYERS.csv`
- `DATA/07_ONION_SCORES.csv` (`consultant_primary_impact_score`, `consultant_secondary_impact_score`, `contradiction_impact_score`)
- `DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv` (`attributed_to_actor`, `attributed_to_tier`, `attributed_days`)
- `DATA/09_FLAT_GED_EXTRACT.csv` (`approver_canonical`, `status_clean`, `response_comment`, `effective_source`)

## Patterns recherchés
1. **CONSULTANT_POSITION_SHIFT** (cf. Prompt 02 §3) — agréger côté consultant.
2. **CONSULTANT_COMMENT_INFLATION** (cf. Prompt 02 §4) — agréger longueur de `response_comment` par `(approver_canonical, indice)`.
3. **LATE_SECONDARY_DISRUPTS_VISA** (cf. Prompt 02 §5) — agréger les événements secondaires post-visa.
4. **Lenteur chronique** : `attributed_days` cumulés par `attributed_to_actor` côté consultant.

## Format de sortie
Un tableau par consultant : `approver_canonical`, `tier (PRIMARY/SECONDARY)`, `pattern`, `family_keys_exemples (max 3)`, `attributed_days_cumulés`, `consultant_*_impact_score`, `recommended_action`.

## Règle d'or
Aucune attaque ad hominem. Citez les colonnes. Si l'angle n'est pas soutenu : « Aucun constat — données insuffisantes ».
"""


def _render_prompt_meeting_agenda_generator() -> str:
    return """# Prompt 05 — Générateur d'ordre du jour réunion MOEX

## Objectif
Produire un ordre du jour d'une page pour la prochaine réunion MOEX, en français exclusivement.

## CSV à inspecter
- Toutes les sorties des Prompts 01 à 04 ci-dessus, plus :
- `DATA/01_COUNTER_ATTACK_ITEMS.csv` (`action_bucket`, `risk_level`, `recommended_action`)
- `DATA/05_CHAIN_NARRATIVES.csv` (`recommended_focus`, `urgency_label`)

## Structure de l'ordre du jour
1. **Top 5 sujets à décider** — chacun avec `family_key`, `numero`, une phrase de décision attendue.
2. **Top 3 entreprises à relancer** — chacune avec `emetteur_canonical`, motif (1 ligne), `family_keys_exemples`.
3. **Top 3 consultants à challenger** — chacun avec `approver_canonical`, motif (1 ligne), `family_keys_exemples`.
4. **Annexes** : la liste brute des `family_key` cités, dans l'ordre d'apparition.

## Format
Markdown, français exclusivement. Une seule page imprimable. Pas de tableaux multi-pages, pas d'annexes longues.

## Règle d'or
Aucune ligne sans citation `family_key` ou `numero`. Aucune décision inventée. Si une catégorie a moins d'éléments que demandé, écrivez « Aucun élément supplémentaire » plutôt que de combler.
"""
