"""
document_command_center.py — Backend for the Document Command Center panel.

This module is the SOLE source of business logic for the Document Command Center.
It computes all tag chips, sections, and search results consumed by Phase 4B (UI).

Tag taxonomy (7 primary, 6 secondary):

PRIMARY (exactly one per doc, derived from dernier_df._focus_owner_tier):
  Att Entreprise — Dans les délais  tier==CONTRACTOR AND days_since_moex_ref <= 15
  Att Entreprise — Hors délais      tier==CONTRACTOR AND days_since_moex_ref > 15
  Att BET Primaire                  tier==PRIMARY
  Att BET Secondaire                tier==SECONDARY
  Att MOEX — Facile                 tier==MOEX AND no BET blocking status on latest indice
  Att MOEX — Arbitrage              tier==MOEX AND ≥1 BET blocking status on latest indice
  Clos / Visé                       tier==CLOSED

SECONDARY (multi-valued, optional):
  Refus multiples      ≥2 BET responses with status in {REF, DEF, SUS}
  Commentaire manquant Any response with decisive status AND empty comment
  Secondaire expiré    tier==MOEX AND moex_countdown.countdown_expired
  Très ancien          data_date − latest_indice_created_at > 60 days
  Cycle dépassé        chain_timeline[numero].cycle_depasse == True
  Chaîne longue        chain_timeline[numero].chain_long == True

Public API:
  search_documents(ctx, query, focus, stale_days, limit) -> list[dict]
  build_document_command_center(ctx, numero, indice, focus, stale_days) -> dict
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
ENTREPRISE_DELAY_THRESHOLD_DAYS = 15
TRES_ANCIEN_THRESHOLD_DAYS = 60
BLOCKING_STATUSES = frozenset({"REF", "DEF", "SUS"})
DECISIVE_STATUSES = frozenset({"REF", "DEF", "SUS", "VAO", "HM"})
MOEX_REF_STATUSES = frozenset({"REF", "SAS REF"})
MOEX_CANONICAL = "Maître d'Oeuvre EXE"

_MODULE_DIR = Path(__file__).parent
_CHAIN_TIMELINE_DIR = _MODULE_DIR.parent.parent / "output" / "intermediate"


# ── Public API ───────────────────────────────────────────────────────────────

def search_documents(
    ctx,
    query: str,
    focus: bool = False,
    stale_days: int = 30,
    limit: int = 50,
) -> list[dict]:
    """Substring match (case-insensitive) on dernier_df fields.

    Fields searched: numero, libelle_du_document, indice, emetteur, lot.
    Returns ranked list (exact numero match first, then prefix, then substring).

    Each dict: {numero, indice, titre, emetteur, lot, primary_tag, latest_status}
    Empty query returns [].
    """
    query = (query or "").strip()
    if not query:
        return []

    if ctx.degraded_mode or ctx.dernier_df is None:
        return []

    d = ctx.dernier_df
    q = query.lower()

    # Build a single "search text" mask across the 5 fields
    def _str(val):
        return str(val).lower() if val is not None and str(val) not in ("nan", "None") else ""

    mask = (
        d["numero"].apply(_str).str.contains(q, regex=False)
        | d["libelle_du_document"].apply(_str).str.contains(q, regex=False)
        | d["indice"].apply(_str).str.contains(q, regex=False)
        | d["emetteur"].apply(_str).str.contains(q, regex=False)
        | d["lot_normalized"].apply(_str).str.contains(q, regex=False)
    )
    subset = d[mask].copy()

    if focus:
        try:
            from reporting.focus_filter import apply_focus_filter, FocusConfig
            focus_config = FocusConfig(enabled=True, stale_threshold_days=int(stale_days))
            focus_result = apply_focus_filter(ctx, focus_config)
            focused_ids = getattr(focus_result, "focused_doc_ids", set())
            subset = subset[subset["doc_id"].isin(focused_ids)]
        except Exception as exc:
            logger.warning("search_documents: focus filter failed: %s", exc)

    if subset.empty:
        return []

    # Rank: exact numero match=0, prefix match=1, substring match=2
    def _rank(row):
        n = _str(row.get("numero"))
        if n == q:
            return 0
        if n.startswith(q):
            return 1
        return 2

    subset = subset.copy()
    subset["_rank"] = subset.apply(_rank, axis=1)
    subset = subset.sort_values("_rank").head(limit)

    # For each result compute primary_tag and latest_status summary
    results = []
    for _, row in subset.iterrows():
        doc_row = row.to_dict()
        try:
            resps = _get_latest_responses_for_doc(ctx, doc_row)
            days = _compute_days_since_moex_ref(ctx, resps)
            tier = str(doc_row.get("_focus_owner_tier") or "")
            primary_tag = _compute_primary_tag(tier, resps, days)
            status_info = _build_latest_status(resps, doc_row)
            latest_status = status_info.get("summary", "")
        except Exception:
            primary_tag = ""
            latest_status = ""

        results.append({
            "numero": doc_row.get("numero"),
            "indice": doc_row.get("indice"),
            "titre": doc_row.get("libelle_du_document"),
            "emetteur": doc_row.get("emetteur"),
            "lot": doc_row.get("lot"),
            "primary_tag": primary_tag,
            "latest_status": latest_status,
        })

    return results


def build_document_command_center(
    ctx,
    numero: str,
    indice: Optional[str] = None,
    focus: bool = False,
    stale_days: int = 30,
) -> dict:
    """Full panel payload for one document.

    Returns dict with keys: header, latest_status, responses, comments,
    revision_history, chronologie, tags, warnings.
    On error: {"error": "...", "numero": numero}
    """
    warnings_out = []

    try:
        if ctx.degraded_mode or ctx.dernier_df is None:
            return {"error": "Degraded mode — no GED data available", "numero": numero}

        # Load chain timeline once (disk read, small file)
        chain_timeline = {}
        try:
            from reporting.chain_timeline_attribution import load_chain_timeline_artifact
            chain_timeline = load_chain_timeline_artifact(_CHAIN_TIMELINE_DIR)
        except FileNotFoundError:
            warnings_out.append("CHAIN_TIMELINE_ATTRIBUTION.json not found — chronologie unavailable")
        except Exception as exc:
            logger.warning("Failed to load chain_timeline: %s", exc)
            warnings_out.append(f"Chain timeline load error: {exc}")

        # Resolve document row
        doc_row, resolved_indice = _resolve_doc_rows(ctx, numero, indice)

        # Get responses for the resolved indice
        latest_responses = _get_latest_responses_for_doc(ctx, doc_row)

        # Compute tags
        focus_owner_tier = str(doc_row.get("_focus_owner_tier") or "")
        days_since_moex_ref = _compute_days_since_moex_ref(ctx, latest_responses)
        primary_tag = _compute_primary_tag(focus_owner_tier, latest_responses, days_since_moex_ref)
        chain_payload = chain_timeline.get(numero)
        secondary_tags = _compute_secondary_tags(ctx, doc_row, latest_responses, chain_payload)

        return {
            "header": _build_header(doc_row, primary_tag, secondary_tags),
            "latest_status": _build_latest_status(latest_responses, doc_row),
            "responses": _build_responses_section(latest_responses),
            "comments": _build_comments_section(ctx, numero, latest_responses),
            "revision_history": _build_revision_history(ctx, numero, chain_timeline),
            "chronologie": chain_payload,
            "tags": {"primary": primary_tag, "secondary": secondary_tags},
            "warnings": warnings_out,
        }

    except ValueError as exc:
        return {"error": str(exc), "numero": numero}
    except Exception as exc:
        logger.exception("build_document_command_center failed for %s", numero)
        return {"error": str(exc), "numero": numero}


# ── Private helpers ──────────────────────────────────────────────────────────

def _resolve_doc_rows(ctx, numero: str, indice: Optional[str]):
    """Return (doc_row_dict, indice_str) for the given numero/indice.

    If indice is None, picks the alphabetically latest indice from dernier_df.
    Raises ValueError if the document is not found.
    """
    d = ctx.dernier_df
    mask = d["numero"] == numero
    subset = d[mask]
    if subset.empty:
        raise ValueError(f"Document numero {numero!r} not found in dernier_df")

    if indice is not None:
        row_df = subset[subset["indice"] == indice]
        if row_df.empty:
            raise ValueError(f"Document {numero!r} indice {indice!r} not found")
        row = row_df.iloc[0]
        return row.to_dict(), str(indice)

    # Pick alphabetically latest indice
    latest_indice = sorted(subset["indice"].tolist())[-1]
    row = subset[subset["indice"] == latest_indice].iloc[0]
    return row.to_dict(), latest_indice


def _get_latest_responses_for_doc(ctx, doc_row: dict) -> list[dict]:
    """Return list of response dicts for the given doc_row's doc_id.

    Keys per dict: reviewer, tier, status, response_date, deadline,
                   comment, is_open, date_status_type.
    """
    from reporting.focus_ownership import classify_consultant

    doc_id = doc_row["doc_id"]
    resp = ctx.responses_df
    rows = resp[resp["doc_id"] == doc_id]

    results = []
    for _, r in rows.iterrows():
        canonical = str(r.get("approver_canonical") or "")
        status_type = str(r.get("date_status_type") or "NOT_CALLED")

        da = r.get("date_answered")
        if da is not None and not pd.isna(da):
            response_date = da.date() if hasattr(da, "date") else da
        else:
            response_date = None

        dl = r.get("date_limite")
        if dl is not None and not pd.isna(dl):
            deadline = dl.date() if hasattr(dl, "date") else dl
        else:
            deadline = None

        is_open = status_type in ("PENDING_IN_DELAY", "PENDING_LATE") or response_date is None

        results.append({
            "reviewer": canonical,
            "tier": classify_consultant(canonical),
            "status": str(r.get("status_clean") or ""),
            "response_date": response_date,
            "deadline": deadline,
            "comment": str(r.get("response_comment") or "").strip(),
            "is_open": is_open,
            "date_status_type": status_type,
        })

    return results


def _compute_days_since_moex_ref(ctx, latest_responses: list[dict]) -> Optional[int]:
    """Return days since MOEX answered REF/SAS REF on the latest indice.

    Finds the response where reviewer == MOEX_CANONICAL and status in MOEX_REF_STATUSES.
    Returns (ctx.data_date - response_date).days if found, else None.
    """
    data_date = ctx.data_date
    if data_date is None:
        return None
    dd = data_date.date() if hasattr(data_date, "date") else data_date

    for r in latest_responses:
        if r["reviewer"] == MOEX_CANONICAL and r["status"] in MOEX_REF_STATUSES:
            rd = r["response_date"]
            if rd is not None:
                return (dd - rd).days
    return None


def _compute_primary_tag(
    focus_owner_tier: str,
    latest_responses: list[dict],
    days_since_moex_ref: Optional[int],
) -> str:
    """Return the single primary tag for a document per the locked taxonomy."""
    if focus_owner_tier == "CLOSED":
        return "Clos / Visé"
    if focus_owner_tier == "CONTRACTOR":
        if days_since_moex_ref is None or days_since_moex_ref <= ENTREPRISE_DELAY_THRESHOLD_DAYS:
            return "Att Entreprise — Dans les délais"
        return "Att Entreprise — Hors délais"
    if focus_owner_tier == "PRIMARY":
        return "Att BET Primaire"
    if focus_owner_tier == "SECONDARY":
        return "Att BET Secondaire"
    if focus_owner_tier == "MOEX":
        bet_statuses = [
            r["status"] for r in latest_responses
            if r["reviewer"] != MOEX_CANONICAL and r.get("status")
        ]
        has_blocking = any(s in BLOCKING_STATUSES for s in bet_statuses)
        return "Att MOEX — Arbitrage" if has_blocking else "Att MOEX — Facile"
    return "Inconnu"


def _compute_secondary_tags(
    ctx,
    doc_row: dict,
    latest_responses: list[dict],
    chain_timeline_payload: Optional[dict],
) -> list[str]:
    """Return list of secondary tags (may be empty)."""
    tags = []

    # Refus multiples: ≥2 BET responses with blocking status
    bet_responses = [r for r in latest_responses if r["reviewer"] != MOEX_CANONICAL]
    blocking_count = sum(1 for r in bet_responses if r.get("status") in BLOCKING_STATUSES)
    if blocking_count >= 2:
        tags.append("Refus multiples")

    # Commentaire manquant: any response with decisive status AND empty comment
    has_missing_comment = any(
        r.get("status") in DECISIVE_STATUSES and not r.get("comment", "").strip()
        for r in latest_responses
    )
    if has_missing_comment:
        tags.append("Commentaire manquant")

    # Secondaire expiré: tier==MOEX AND moex_countdown.countdown_expired
    if doc_row.get("_focus_owner_tier") == "MOEX":
        doc_id = doc_row.get("doc_id")
        cd = ctx.moex_countdown.get(doc_id, {})
        if cd.get("countdown_expired"):
            tags.append("Secondaire expiré")

    # Très ancien: data_date − latest_indice_created_at > 60 days
    created_at = doc_row.get("created_at")
    data_date = ctx.data_date
    if created_at is not None and data_date is not None:
        try:
            ca = created_at.date() if hasattr(created_at, "date") else created_at
            dd = data_date.date() if hasattr(data_date, "date") else data_date
            if (dd - ca).days > TRES_ANCIEN_THRESHOLD_DAYS:
                tags.append("Très ancien")
        except Exception:
            pass

    # Cycle dépassé / Chaîne longue from chain_timeline payload
    if chain_timeline_payload:
        if chain_timeline_payload.get("cycle_depasse"):
            tags.append("Cycle dépassé")
        if chain_timeline_payload.get("chain_long"):
            tags.append("Chaîne longue")

    return tags


def _build_header(doc_row: dict, primary_tag: str, secondary_tags: list[str]) -> dict:
    """Build the header section of the command center payload."""
    return {
        "numero": doc_row.get("numero"),
        "titre": doc_row.get("libelle_du_document"),
        "indice_latest": doc_row.get("indice"),
        "emetteur": doc_row.get("emetteur"),
        "lot": doc_row.get("lot"),
        "primary_tag": primary_tag,
        "secondary_tags": secondary_tags,
    }


def _build_latest_status(latest_responses: list[dict], doc_row: dict) -> dict:
    """Build the latest_status section."""
    visa_global = doc_row.get("_visa_global")
    visa_date = doc_row.get("_visa_global_date")

    # Normalize visa_date
    if visa_date is not None and not (isinstance(visa_date, float) and visa_date != visa_date):
        vd = visa_date.date() if hasattr(visa_date, "date") else visa_date
        visa_date_str = str(vd)
    else:
        visa_date_str = None

    # Build 1-line summary
    if visa_global and str(visa_global) not in ("nan", "None", ""):
        summary = f"VISA {visa_global}"
        if visa_date_str:
            summary += f" ({visa_date_str})"
    else:
        pending = [r for r in latest_responses if r.get("is_open") and r.get("reviewer")]
        if pending:
            names = ", ".join(r["reviewer"] for r in pending[:2])
            summary = f"En attente: {names}"
            if len(pending) > 2:
                summary += f" (+{len(pending) - 2})"
        else:
            answered = [r for r in latest_responses if not r.get("is_open") and r.get("status")]
            if answered:
                last = answered[-1]
                summary = f"Répondu: {last['reviewer']} ({last['status']})"
            else:
                summary = "Statut inconnu"

    return {
        "visa_global": str(visa_global) if visa_global and str(visa_global) not in ("nan", "None") else None,
        "visa_date": visa_date_str,
        "summary": summary,
    }


def _build_responses_section(latest_responses: list[dict]) -> list[dict]:
    """Build the responses section (one entry per reviewer)."""
    result = []
    for r in latest_responses:
        result.append({
            "reviewer": r["reviewer"],
            "tier": r["tier"],
            "status": r["status"],
            "response_date": str(r["response_date"]) if r["response_date"] else None,
            "deadline": str(r["deadline"]) if r["deadline"] else None,
            "comment": r["comment"],
            "is_open": r["is_open"],
        })
    return result


def _build_comments_section(ctx, numero: str, latest_responses: list[dict]) -> list[dict]:
    """Build the comments section grouped by reviewer across all indices."""
    from collections import defaultdict

    # Get all (numero, indice) rows from docs_df, sorted by indice
    all_rows = ctx.docs_df[ctx.docs_df["numero"] == numero].copy()
    if all_rows.empty:
        # Fall back to latest_responses only
        result = []
        for r in latest_responses:
            if r.get("comment"):
                result.append({
                    "reviewer": r["reviewer"],
                    "latest_comment": r["comment"],
                    "earlier_comments": [],
                })
        return result

    all_rows = all_rows.sort_values("indice")
    latest_indice = sorted(all_rows["indice"].tolist())[-1]
    latest_doc_ids = set(all_rows[all_rows["indice"] == latest_indice]["doc_id"].tolist())
    all_doc_ids = set(all_rows["doc_id"].tolist())

    # Get all responses for all indices
    resp = ctx.responses_df[ctx.responses_df["doc_id"].isin(all_doc_ids)]
    doc_id_to_indice = all_rows.set_index("doc_id")["indice"].to_dict()

    reviewer_data: dict = defaultdict(lambda: {"latest_comment": "", "earlier_comments": []})

    for _, r in resp.iterrows():
        canonical = str(r.get("approver_canonical") or "")
        raw_comment = str(r.get("response_comment") or "").strip()
        if not raw_comment or raw_comment == "nan":
            continue
        doc_id = r["doc_id"]
        indice = doc_id_to_indice.get(doc_id, "")
        if doc_id in latest_doc_ids:
            reviewer_data[canonical]["latest_comment"] = raw_comment
        else:
            status_str = str(r.get("status_clean") or "").strip()
            reviewer_data[canonical]["earlier_comments"].append(
                {"indice": indice, "status": status_str, "comment": raw_comment}
            )

    result = []
    for reviewer, data in reviewer_data.items():
        if data["latest_comment"] or data["earlier_comments"]:
            result.append({
                "reviewer": reviewer,
                "latest_comment": data["latest_comment"],
                "earlier_comments": sorted(
                    data["earlier_comments"], key=lambda x: x["indice"]
                ),
            })
    return result


def _build_revision_history(ctx, numero: str, chain_timeline: dict = None) -> list[dict]:
    """Build revision history from docs_df rows for this numero, sorted by indice."""
    rows = ctx.docs_df[ctx.docs_df["numero"] == numero].copy()
    if rows.empty:
        return []

    rows = rows.sort_values("indice")

    # Build indice → closure_type from chain_timeline if available
    closure_by_indice: dict = {}
    if chain_timeline and numero in chain_timeline:
        for entry in chain_timeline[numero].get("indices", []):
            closure_by_indice[entry["indice"]] = entry.get("closure_type")

    # Get response counts per doc_id
    resp = ctx.responses_df
    resp_counts = resp.groupby("doc_id").size().to_dict()

    result = []
    for _, row in rows.iterrows():
        doc_id = row["doc_id"]
        indice = row["indice"]

        # Status summary: use _visa_global from dernier_df if available
        dernier_match = ctx.dernier_df[ctx.dernier_df["doc_id"] == doc_id]
        if not dernier_match.empty:
            vg = dernier_match.iloc[0].get("_visa_global")
            status_summary = str(vg) if vg and str(vg) not in ("nan", "None") else "open"
        else:
            status_summary = "historical"

        created_at = row.get("created_at")
        if created_at is not None and not (isinstance(created_at, float) and created_at != created_at):
            ca = created_at.date() if hasattr(created_at, "date") else created_at
            ca_str = str(ca)
        else:
            ca_str = None

        result.append({
            "indice": indice,
            "status_summary": status_summary,
            "response_count": resp_counts.get(doc_id, 0),
            "created_at": ca_str,
            "closure_type": closure_by_indice.get(indice),
        })

    return result
