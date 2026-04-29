"""
contractor_quality.py — Per-contractor quality KPIs with peer benchmarking.

Computes 5 KPIs for one contractor and project-wide peer statistics across all
29 contractors (CONTRACTOR_REFERENCE keys). Consumed by the fiche UI (Step 6).

Public surface
--------------
build_contractor_quality_peer_stats(ctx, chain_timelines=None) -> dict
build_contractor_quality(ctx, contractor_code, peer_stats=None,
                          chain_timelines=None) -> dict
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .consultant_fiche import CONTRACTOR_REFERENCE
from .contractor_fiche import resolve_emetteur_name

logger = logging.getLogger(__name__)

# 13 histogram buckets: 12 intervals of 10 days + one 120+ catch-all
_BUCKET_EDGES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
_TERMINAL_VISAS = {"VSO", "VAO", "HM"}

# BENTIN legacy exception — mirrors ExclusionConfig.SHEET_YEAR_FILTERS
# (context/06_EXCEPTIONS_AND_MAPPINGS.md §D/§E). The FLAT_GED cache is built
# before the pipeline's year-filter exclusion runs, so pre-2026 BEN rows
# survive in ctx.docs_df and must be dropped here for BEN-only.
_BENTIN_OLD_SHEET = "OLD 31 à 34-IN-BX-CFO-BENTIN"
_BENTIN_SHEET = "LOT 31 à 34-IN-BX-CFO-BENTIN"
_BENTIN_LEGACY_MIN_YEAR = 2026


def _apply_legacy_filter(df: pd.DataFrame, contractor_code: str) -> pd.DataFrame:
    """Drop legacy BENTIN_OLD rows for contractor BEN.

    Per context/06_EXCEPTIONS_AND_MAPPINGS.md §D/§E:
      - drop any row on the legacy "OLD 31 à 34-IN-BX-CFO-BENTIN" sheet
      - drop pre-2026 rows on "LOT 31 à 34-IN-BX-CFO-BENTIN" (mirrors
        ExclusionConfig.SHEET_YEAR_FILTERS, applied downstream after FLAT_GED
        caching, so pre-2026 rows survive in ctx.docs_df).

    When gf_sheet_name is absent (FLAT_GED path): all BEN docs are on the
    BENTIN sheet (lots 31/33/34 only), so the year filter alone is applied.

    No-op for any contractor other than BEN.
    """
    if df is None or df.empty or contractor_code != "BEN":
        return df
    if "gf_sheet_name" in df.columns:
        out = df[df["gf_sheet_name"] != _BENTIN_OLD_SHEET]
        if "created_at" in out.columns:
            on_sheet = out["gf_sheet_name"] == _BENTIN_SHEET
            years = pd.to_datetime(out["created_at"], errors="coerce").dt.year
            legacy = on_sheet & (years < _BENTIN_LEGACY_MIN_YEAR).fillna(False)
            out = out[~legacy]
        return out
    # gf_sheet_name absent (FLAT_GED path): all BEN docs are on the BENTIN
    # sheet; apply the year filter directly.
    if "created_at" not in df.columns:
        return df
    years = pd.to_datetime(df["created_at"], errors="coerce").dt.year
    return df[(years >= _BENTIN_LEGACY_MIN_YEAR).fillna(True)]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _visa_col(df: pd.DataFrame) -> str:
    """Return the visa_global column name actually present in df."""
    if "_visa_global" in df.columns:
        return "_visa_global"
    if "visa_global" in df.columns:
        return "visa_global"
    return "_visa_global"


def _visa_date_col(df: pd.DataFrame) -> str:
    if "_visa_global_date" in df.columns:
        return "_visa_global_date"
    if "date_visa" in df.columns:
        return "date_visa"
    return "_visa_global_date"


def _infer_base_dir(ctx) -> Optional[Path]:
    """Try to derive project base_dir from ctx artifact paths."""
    candidates: list[Optional[Path]] = []
    if getattr(ctx, "gf_artifact_path", None):
        candidates.append(Path(ctx.gf_artifact_path))
    for ap in getattr(ctx, "artifact_paths", {}).values():
        if ap:
            candidates.append(Path(ap))
    for p in candidates:
        for parent in p.parents:
            if (parent / "output" / "intermediate").is_dir():
                return parent
    return None


def _load_chain_timelines(ctx) -> dict:
    """Load chain timeline artifact; raises RuntimeError if missing."""
    from .chain_timeline_attribution import load_chain_timeline_artifact
    base_dir = _infer_base_dir(ctx)
    if base_dir is None:
        raise RuntimeError(
            "Cannot infer project base_dir from ctx — pass chain_timelines explicitly"
        )
    try:
        return load_chain_timeline_artifact(base_dir / "output" / "intermediate")
    except FileNotFoundError as exc:
        raise RuntimeError(
            "chain attribution artifact missing — run pipeline"
        ) from exc


def _numero_set(emetteur_docs: pd.DataFrame) -> set:
    """Build the set of numero strings for this contractor's docs."""
    nums: set = set()
    for col in ("numero", "numero_normalized"):
        if col in emetteur_docs.columns:
            nums |= set(emetteur_docs[col].dropna().astype(str))
    return nums


def _chains_for_contractor(emetteur_docs: pd.DataFrame,
                            chain_timelines: dict) -> list:
    if emetteur_docs.empty:
        return []
    nums = _numero_set(emetteur_docs)
    return [ch for ch in chain_timelines.values() if str(ch.get("numero")) in nums]


def _contractor_delay_for_chain(ch: dict, canonical: str, code: str,
                                 dormant_days_by_numero: dict | None = None) -> int:
    """Sum ENTREPRISE delay + named-contractor delay from attribution_breakdown,
    plus (if this chain is currently dormant in the contractor's hands) the
    days_dormant of that latest doc.

    This extension reflects that a chain ending in a sitting REF/SAS REF
    with no contractor resubmittal is contractor-attributable delay,
    even though no closed-cycle event has tagged it yet.

    dormant_days_by_numero: {numero_str: days_dormant_int} for THIS
    contractor's currently-dormant REF + SAS REF docs.
    """
    ab = ch.get("attribution_breakdown") or {}
    base = (
        ab.get("ENTREPRISE", 0)
        + ab.get(canonical, 0)
        + (ab.get(code, 0) if code != canonical else 0)
    )
    if dormant_days_by_numero:
        nm = str(ch.get("numero", "")).strip()
        base += dormant_days_by_numero.get(nm, 0)
    return base


def _sas_refusal_rate(ctx, emetteur_docs: pd.DataFrame) -> float:
    """HISTORICAL SAS REF rate via responses_df.

    Per the SAS-track workflow (workflow_engine.py:218-222):
      SAS REF event = a `responses_df` row where
          approver_raw == "0-SAS"  AND  status_clean == "REF"

    Rate = SAS-track REFs / SAS-track answered submissions for this
    contractor's docs. Captures the contractor's QA/QC track record:
    "of all submissions that went through the SAS gate, what % failed."

    Returns 0.0 if the contractor never had a SAS-track answer.
    """
    if emetteur_docs.empty or "doc_id" not in emetteur_docs.columns:
        return 0.0
    if ctx is None:
        return 0.0
    rdf = ctx.responses_df
    if rdf is None or rdf.empty:
        return 0.0
    doc_ids = set(emetteur_docs["doc_id"])
    sas_track = rdf[
        (rdf["approver_raw"] == "0-SAS")
        & rdf["doc_id"].isin(doc_ids)
    ]
    answered = sas_track[sas_track["date_answered"].notna()]
    if answered.empty:
        return 0.0
    ref_count = (answered["status_clean"] == "REF").sum()
    return float(ref_count) / len(answered)


def _socotec_sus_rate(ctx, contractor_code: str,
                      emetteur_doc_ids: set | None = None) -> Optional[float]:
    """Return SUS/(total Socotec answers) for this contractor, or None if no coverage.

    emetteur_doc_ids: pre-filtered set of doc_ids for this contractor (honors
    the legacy filter). When None, falls back to mapping via ctx.docs_df.
    """
    rdf = ctx.workflow_engine.responses_df
    soc = rdf[
        (rdf["approver_canonical"] == "Bureau de Contrôle")
        & rdf["status_clean"].notna()
        & rdf["date_answered"].notna()
    ]
    if soc.empty or ctx.docs_df is None:
        return None
    if emetteur_doc_ids is not None:
        my_soc = soc[soc["doc_id"].isin(emetteur_doc_ids)]
    else:
        doc_id_to_em = dict(zip(ctx.docs_df["doc_id"], ctx.docs_df["emetteur"]))
        my_soc = soc[soc["doc_id"].map(doc_id_to_em) == contractor_code]
    if my_soc.empty:
        return None
    return float((my_soc["status_clean"] == "SUS").sum()) / len(my_soc)


def _polar_histogram(delays: list) -> dict:
    """13 raw buckets total, but the 0-10 bucket is excluded from
    the display sectors (Eid spec, Step 11a feedback). Returns:
      - buckets: 12 display buckets (10-20, 20-30, ..., 110-120, 120+)
      - under_10_count: chains with contractor-attributed delay < 10 days
      - max_count: max over the 12 displayed buckets (NOT including under_10)
    """
    display_edges = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120]
    buckets = [
        {"label": f"{lo}-{hi}", "lo": lo, "hi": hi, "count": 0}
        for lo, hi in zip(display_edges, display_edges[1:])
    ]
    buckets.append({"label": "120+", "lo": 120, "hi": None, "count": 0})
    under_10 = 0
    for d in delays:
        d_int = int(d)
        if d_int < 10:
            under_10 += 1
        elif d_int >= 120:
            buckets[-1]["count"] += 1
        else:
            # bucket index for [10,20)→0, [20,30)→1, ..., [110,120)→10
            buckets[(d_int // 10) - 1]["count"] += 1
    return {
        "buckets": buckets,
        "max_count": max((b["count"] for b in buckets), default=0),
        "under_10_count": under_10,
    }


def _dormant_list(emetteur_dernier: pd.DataFrame, visa_value: str,
                  ref_today: date) -> list:
    """Return sorted list of dormant docs with the given visa_global value."""
    if emetteur_dernier.empty:
        return []
    vcol = _visa_col(emetteur_dernier)
    date_col = _visa_date_col(emetteur_dernier)
    subset = emetteur_dernier[emetteur_dernier[vcol] == visa_value].copy()
    if subset.empty:
        return []
    subset["_days_dormant"] = (
        pd.to_datetime(ref_today) - pd.to_datetime(subset[date_col], errors="coerce")
    ).dt.days.fillna(0).astype(int)
    # Sort newest visa date first (least dormant at top per user spec)
    subset = subset.sort_values(date_col, ascending=False, na_position="last")
    result = []
    for _, r in subset.iterrows():
        result.append({
            "numero": str(r.get("numero_normalized") or r.get("numero") or "?"),
            "indice": str(r.get("indice", "?")),
            "titre": str(
                r.get("libelle_du_document")
                or r.get("lib_ll_du_document")
                or r.get("titre")
                or "?"
            ),
            "date_visa": str(r.get(date_col, "")),
            "days_dormant": int(r["_days_dormant"]),
            "lot_normalized": str(r.get("lot_normalized", "")),
        })
    return result


def _percentiles(values: list, exclude_none: bool = False) -> dict:
    if exclude_none:
        clean = [v for v in values if v is not None]
    else:
        clean = [v if v is not None else 0.0 for v in values]
    if not clean:
        return {"median": 0.0, "p25": 0.0, "p75": 0.0}
    arr = np.array(clean, dtype=float)
    return {
        "median": float(np.percentile(arr, 50)),
        "p25":    float(np.percentile(arr, 25)),
        "p75":    float(np.percentile(arr, 75)),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_contractor_quality_peer_stats(ctx, chain_timelines: dict | None = None) -> dict:
    """Compute project-wide peer statistics across all 29 contractors.

    Returns:
        {
            "sas_refusal_rate":          {"median": float, "p25": float, "p75": float},
            "dormant_ref_count":         {"median": float, "p25": float, "p75": float},
            "pct_chains_long":           {"median": float, "p25": float, "p75": float},
            "avg_contractor_delay_days": {"median": float, "p25": float, "p75": float},
            "socotec_sus_rate":          {"median": float, "p25": float, "p75": float},
            "_chain_timelines":          dict,  # loaded artifact, for reuse
        }
    """
    if chain_timelines is None:
        chain_timelines = _load_chain_timelines(ctx)

    ref_today = ctx.data_date or date.today()

    sas_rates: list = []
    ref_counts: list = []
    pct_longs: list = []
    avg_delays: list = []
    sus_rates: list = []

    for code in CONTRACTOR_REFERENCE:
        canonical = resolve_emetteur_name(code)
        emetteur_docs = (
            ctx.docs_df[ctx.docs_df["emetteur"] == code]
            if ctx.docs_df is not None else pd.DataFrame()
        )
        emetteur_dernier = (
            ctx.dernier_df[ctx.dernier_df["emetteur"] == code]
            if ctx.dernier_df is not None else pd.DataFrame()
        )
        # ── BENTIN_OLD legacy exception (context/06 §D/§E) ─────────────
        emetteur_docs = _apply_legacy_filter(emetteur_docs, code)
        emetteur_dernier = _apply_legacy_filter(emetteur_dernier, code)

        # SAS refusal rate (historical: all docs_df indices, not just dernier)
        sas_rates.append(_sas_refusal_rate(ctx, emetteur_docs))

        # Dormant REF count
        if not emetteur_dernier.empty:
            vcol = _visa_col(emetteur_dernier)
            ref_counts.append(int((emetteur_dernier[vcol] == "REF").sum()))
        else:
            ref_counts.append(0)

        # Chain metrics
        chains = _chains_for_contractor(emetteur_docs, chain_timelines)
        n_chains = len(chains)
        n_long = sum(1 for ch in chains if ch.get("chain_long"))
        pct_longs.append(n_long / n_chains if n_chains > 0 else 0.0)

        # Build dormant delay map for this contractor (REF + SAS REF sitting idle)
        dormant_days_by_numero: dict = {}
        for d in _dormant_list(emetteur_dernier, "REF", ref_today) + \
                 _dormant_list(emetteur_dernier, "SAS REF", ref_today):
            nm = str(d.get("numero", "")).strip()
            if nm:
                dormant_days_by_numero[nm] = max(
                    dormant_days_by_numero.get(nm, 0),
                    int(d.get("days_dormant", 0))
                )

        delays = [
            _contractor_delay_for_chain(ch, canonical, code, dormant_days_by_numero)
            for ch in chains
        ]
        avg_delays.append(float(sum(delays) / len(delays)) if delays else 0.0)

        # Socotec SUS rate (pass filtered doc_ids to honor legacy filter)
        emetteur_doc_ids = (
            set(emetteur_docs["doc_id"])
            if not emetteur_docs.empty and "doc_id" in emetteur_docs.columns
            else None
        )
        sus_rates.append(_socotec_sus_rate(ctx, code, emetteur_doc_ids))

    return {
        "sas_refusal_rate":          _percentiles(sas_rates),
        "dormant_ref_count":         _percentiles(ref_counts),
        "pct_chains_long":           _percentiles(pct_longs),
        "avg_contractor_delay_days": _percentiles(avg_delays),
        "socotec_sus_rate":          _percentiles(sus_rates, exclude_none=True),
        "_chain_timelines":          chain_timelines,
    }


def build_contractor_quality(ctx, contractor_code: str,
                              peer_stats: dict | None = None,
                              chain_timelines: dict | None = None) -> dict:
    """V1 quality payload for one contractor.

    Args:
        ctx:             Loaded RunContext.
        contractor_code: Emetteur code (e.g. "BEN"). Unknown codes return zero counts.
        peer_stats:      Pre-computed peer stats dict (fast path). If None, computed here.
        chain_timelines: Pre-loaded artifact dict (fast path). If None, taken from
                         peer_stats["_chain_timelines"] or loaded from disk.

    Returns dict matching plan §7 Step 4 shape.
    """
    # Resolve chain_timelines from peer_stats if available
    if chain_timelines is None and peer_stats is not None:
        chain_timelines = peer_stats.get("_chain_timelines")

    # Compute peer stats if not provided (slow path)
    if peer_stats is None:
        peer_stats = build_contractor_quality_peer_stats(ctx, chain_timelines)
        chain_timelines = peer_stats.get("_chain_timelines", chain_timelines)

    # Ensure chain_timelines is resolved (guard against edge cases)
    if chain_timelines is None:
        chain_timelines = peer_stats.get("_chain_timelines") or {}

    canonical = resolve_emetteur_name(contractor_code)

    # Filter docs and dernier for this contractor
    emetteur_docs = (
        ctx.docs_df[ctx.docs_df["emetteur"] == contractor_code]
        if ctx.docs_df is not None else pd.DataFrame()
    )
    emetteur_dernier = (
        ctx.dernier_df[ctx.dernier_df["emetteur"] == contractor_code]
        if ctx.dernier_df is not None else pd.DataFrame()
    )
    # ── BENTIN_OLD legacy exception (context/06 §D/§E) ─────────────────────
    emetteur_docs = _apply_legacy_filter(emetteur_docs, contractor_code)
    emetteur_dernier = _apply_legacy_filter(emetteur_dernier, contractor_code)

    # ── Open / finished ───────────────────────────────────────────────────────
    if not emetteur_dernier.empty:
        vcol = _visa_col(emetteur_dernier)
        is_finished = emetteur_dernier[vcol].isin(_TERMINAL_VISAS)
        open_count = int((~is_finished).sum())
        finished_count = int(is_finished.sum())
    else:
        open_count = 0
        finished_count = 0
    total = open_count + finished_count

    # ── SAS refusal rate (historical: all docs_df indices) ───────────────────
    sas_refusal_rate = _sas_refusal_rate(ctx, emetteur_docs)

    # ── Dormant REF / SAS REF lists (must precede delay computation) ─────────
    ref_today = ctx.data_date or date.today()
    dormant_ref = _dormant_list(emetteur_dernier, "REF", ref_today)
    dormant_sas_ref = _dormant_list(emetteur_dernier, "SAS REF", ref_today)

    # Build numero → days_dormant map for delay extension
    dormant_days_by_numero: dict = {}
    for d in dormant_ref + dormant_sas_ref:
        nm = str(d.get("numero", "")).strip()
        if nm:
            dormant_days_by_numero[nm] = max(
                dormant_days_by_numero.get(nm, 0),
                int(d.get("days_dormant", 0))
            )

    # ── Chain-based metrics ───────────────────────────────────────────────────
    chains = _chains_for_contractor(emetteur_docs, chain_timelines)
    n_chains = len(chains)
    n_long = sum(1 for ch in chains if ch.get("chain_long"))
    pct_chains_long = n_long / n_chains if n_chains > 0 else 0.0

    delays = [
        _contractor_delay_for_chain(ch, canonical, contractor_code, dormant_days_by_numero)
        for ch in chains
    ]
    avg_contractor_delay_days = float(sum(delays) / len(delays)) if delays else 0.0

    # ── Polar histogram ───────────────────────────────────────────────────────
    polar_histogram = _polar_histogram(delays)

    # ── Long-chains panel ─────────────────────────────────────────────────────
    long_chains = [ch for ch in chains if ch.get("chain_long")]
    total_delay_in_long = sum(
        (ch.get("totals") or {}).get("delay_days", 0) for ch in long_chains
    )
    # Phase 0 D-004 fix (2026-04-29): denominator total_delay_in_long uses
    # chain.totals.delay_days which does NOT include dormant time. Numerator
    # must use the same scope (closed-cycle attribution only) — passing None
    # for dormant_days_by_numero. The dormant-time extension stays in
    # avg_contractor_delay_days above. Pre-fix, AMP had share=1.9945 (199%).
    contractor_delay_in_long = sum(
        _contractor_delay_for_chain(ch, canonical, contractor_code, None)
        for ch in long_chains
    )
    share_contractor_in_long = (
        contractor_delay_in_long / total_delay_in_long
        if total_delay_in_long > 0 else 0.0
    )

    # ── Socotec SUS rate ──────────────────────────────────────────────────────
    emetteur_doc_ids = (
        set(emetteur_docs["doc_id"]) if "doc_id" in emetteur_docs.columns else None
    )
    socotec_sus_rate = _socotec_sus_rate(ctx, contractor_code, emetteur_doc_ids)

    return {
        "contractor_code": contractor_code,
        "kpis": {
            "sas_refusal_rate": {
                "value": sas_refusal_rate,
                "peer": peer_stats["sas_refusal_rate"],
            },
            "dormant_ref_count": {
                "value": len(dormant_ref),
                "peer": peer_stats["dormant_ref_count"],
            },
            "pct_chains_long": {
                "value": pct_chains_long,
                "peer": peer_stats["pct_chains_long"],
            },
            "avg_contractor_delay_days": {
                "value": avg_contractor_delay_days,
                "peer": peer_stats["avg_contractor_delay_days"],
            },
            "socotec_sus_rate": {
                "value": socotec_sus_rate,
                "peer": peer_stats["socotec_sus_rate"],
            },
        },
        "open_finished": {"open": open_count, "finished": finished_count, "total": total},
        "polar_histogram": polar_histogram,
        "long_chains": {
            "pct_long": pct_chains_long,
            "share_contractor_in_long_chains": share_contractor_in_long,
        },
        "dormant_ref": dormant_ref,
        "dormant_sas_ref": dormant_sas_ref,
    }

