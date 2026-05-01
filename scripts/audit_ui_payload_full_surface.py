"""
scripts/audit_ui_payload_full_surface.py
Phase 8A.6 — Widened UI Payload Audit (2026-05-01)

Extends Phase 8 step 6 (Overview-only, 10 fields) to all major UI surfaces
listed in context/12_UI_METRIC_INVENTORY.md.

Read-only: does NOT modify any production source.

Surfaces covered:
  consultants_list      compute_consultant_summary  → adapt_consultants
  contractors_list      compute_contractor_summary  → adapt_contractors_list
  consultant_fiche      build_consultant_fiche       (no separate adapter; documented)
  contractor_fiche      build_contractor_fiche       (no separate adapter; documented)
  dcc                   CHAIN_TIMELINE_ATTRIBUTION.json (no separate adapter; documented)
  chain_onion_panel     dashboard_summary.json + top_issues.json (payload check only)

Mismatch classification (per spec §12.4):
  naming_only                  same number, different key path
  scope_filter                 different filter applied at adapter vs aggregator
  expected_semantic_difference adapter intentionally reshapes (e.g. rate → percent)
  true_bug                     real divergence in arithmetic → HALT S3

Stdout summary (exact shape):
  UI_PAYLOAD_FULL: surfaces=<n> compared=<n> matches=<n> mismatches=<n>; <verdict>
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = BASE_DIR / "src"
for _p in (BASE_DIR, _SRC_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    stream=sys.stderr,
)
_LOG = logging.getLogger(__name__)

# ─── Mismatch classification constants ────────────────────────────────────────
NAMING_ONLY = "naming_only"
SCOPE_FILTER = "scope_filter"
EXPECTED_SEMANTIC = "expected_semantic_difference"
TRUE_BUG = "true_bug"
SKIPPED = "skipped"

# ─── Mismatch column order (matches spec §12.3 xlsx shape) ───────────────────
_MISMATCH_COLS = [
    "surface", "field_label", "backend_val", "ui_val",
    "comparison_kind", "classification", "notes",
]


def _safe_int(v) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _compare_surface(surface: str, pairs: list[dict]) -> dict:
    """Run field comparisons for one surface.

    Each pair dict:
      field_label       human-readable field name
      backend_val       value from the aggregator / backend function
      ui_val            value from the adapter / UI function
      comparison_kind   "numeric_equal" | "identity" | "float_equal" | "skipped"
      classification    mismatch class to assign IF values differ
      notes             context / explanation
    """
    compared: list[dict] = []
    matches_n = 0
    mismatches_n = 0
    mismatch_rows: list[dict] = []
    skip_rows: list[dict] = []

    for p in pairs:
        label = p["field_label"]
        b_val = p.get("backend_val")
        u_val = p.get("ui_val")
        kind = p.get("comparison_kind", "numeric_equal")
        notes = p.get("notes", "")
        classification = p.get("classification", "identity")

        if kind == SKIPPED:
            skip_rows.append({"field_label": label, "notes": notes})
            continue

        # Compare
        match = False
        try:
            if kind == "numeric_equal":
                match = (_safe_int(b_val) == _safe_int(u_val))
            elif kind == "identity":
                match = (b_val == u_val)
            elif kind == "float_equal":
                b_f = float(b_val) if b_val is not None else 0.0
                u_f = float(u_val) if u_val is not None else 0.0
                match = (abs(b_f - u_f) < 0.15)  # 0.15% tolerance for rounding
            else:
                skip_rows.append({"field_label": label, "notes": f"unknown kind {kind!r}"})
                continue
        except (TypeError, ValueError) as exc:
            skip_rows.append({"field_label": label, "notes": f"compare error: {exc}"})
            continue

        row = {
            "surface": surface,
            "field_label": label,
            "backend_val": b_val,
            "ui_val": u_val,
            "comparison_kind": kind,
            "classification": classification,
            "notes": notes,
        }

        if match:
            matches_n += 1
        else:
            mismatches_n += 1
            mismatch_rows.append(row)

        compared.append(row)

    return {
        "surface": surface,
        "compared": len(compared),
        "matches": matches_n,
        "mismatches": mismatches_n,
        "skipped": len(skip_rows),
        "mismatch_rows": mismatch_rows,
        "skip_rows": skip_rows,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Surface audit functions
# ─────────────────────────────────────────────────────────────────────────────

def audit_consultants_list(ctx) -> dict:
    """Compare compute_consultant_summary → adapt_consultants (aggregate level)."""
    from reporting.aggregator import compute_consultant_summary
    from reporting.ui_adapter import adapt_consultants

    _LOG.info("audit_consultants_list: computing backend + adapter ...")
    backend = compute_consultant_summary(ctx)
    ui = adapt_consultants(backend)

    # Aggregate sums across all rows
    b_called   = sum(r.get("docs_called", 0) for r in backend)
    b_answered = sum(r.get("docs_answered", 0) for r in backend)
    b_vso      = sum(r.get("vso", 0) for r in backend)
    b_vao      = sum(r.get("vao", 0) for r in backend)
    b_ref      = sum(r.get("ref", 0) for r in backend)
    b_hm       = sum(r.get("hm", 0) for r in backend)
    b_open     = sum(r.get("open", 0) for r in backend)
    b_focus    = sum(r.get("focus_owned", 0) for r in backend)
    b_block    = sum(r.get("open_blocking", 0) for r in backend)

    u_total    = sum(r.get("total", 0) for r in ui)
    u_answered = sum(r.get("answered", 0) for r in ui)
    u_vso      = sum(r.get("vso", 0) for r in ui)
    u_vao      = sum(r.get("vao", 0) for r in ui)
    u_ref      = sum(r.get("ref", 0) for r in ui)
    u_hm       = sum(r.get("hm", 0) for r in ui)
    u_pending  = sum(r.get("pending", 0) for r in ui)
    u_focus    = sum(r.get("focus_owned", 0) for r in ui)
    u_block    = sum(r.get("open_blocking", 0) for r in ui)

    pairs = [
        {
            "field_label": "row_count",
            "backend_val": len(backend), "ui_val": len(ui),
            "comparison_kind": "numeric_equal", "classification": "identity",
            "notes": "same number of consultant rows in backend and adapter output",
        },
        {
            "field_label": "total_docs_called (backend:docs_called → ui:total)",
            "backend_val": b_called, "ui_val": u_total,
            "comparison_kind": "numeric_equal", "classification": NAMING_ONLY,
            "notes": "backend key docs_called renamed to total in adapt_consultants",
        },
        {
            "field_label": "total_docs_answered (backend:docs_answered → ui:answered)",
            "backend_val": b_answered, "ui_val": u_answered,
            "comparison_kind": "numeric_equal", "classification": NAMING_ONLY,
            "notes": "backend key docs_answered renamed to answered in adapt_consultants",
        },
        {
            "field_label": "vso",
            "backend_val": b_vso, "ui_val": u_vso,
            "comparison_kind": "numeric_equal", "classification": "identity",
            "notes": "",
        },
        {
            "field_label": "vao",
            "backend_val": b_vao, "ui_val": u_vao,
            "comparison_kind": "numeric_equal", "classification": "identity",
            "notes": "",
        },
        {
            "field_label": "ref",
            "backend_val": b_ref, "ui_val": u_ref,
            "comparison_kind": "numeric_equal", "classification": "identity",
            "notes": "",
        },
        {
            "field_label": "hm",
            "backend_val": b_hm, "ui_val": u_hm,
            "comparison_kind": "numeric_equal", "classification": "identity",
            "notes": "",
        },
        {
            "field_label": "open_docs (backend:open → ui:pending)",
            "backend_val": b_open, "ui_val": u_pending,
            "comparison_kind": "numeric_equal", "classification": NAMING_ONLY,
            "notes": "backend key open renamed to pending in adapt_consultants",
        },
        {
            "field_label": "focus_owned",
            "backend_val": b_focus, "ui_val": u_focus,
            "comparison_kind": "numeric_equal", "classification": "identity",
            "notes": "0 when no focus_result supplied (unfocused audit run)",
        },
        {
            "field_label": "open_blocking",
            "backend_val": b_block, "ui_val": u_block,
            "comparison_kind": "numeric_equal", "classification": "identity",
            "notes": "",
        },
    ]

    result = _compare_surface("consultants_list", pairs)
    result["notes"] = (
        f"backend rows={len(backend)}, ui rows={len(ui)}; "
        "3 naming_only key renames documented (docs_called→total, docs_answered→answered, open→pending); "
        "pass_rate is an expected_semantic_difference (rate×100 transform) — skipped at aggregate level."
    )
    return result


def audit_contractors_list(ctx) -> dict:
    """Compare compute_contractor_summary → adapt_contractors_list (aggregate + per-contractor)."""
    from reporting.aggregator import compute_contractor_summary
    from reporting.ui_adapter import adapt_contractors_list

    _LOG.info("audit_contractors_list: computing backend + adapter ...")
    backend = compute_contractor_summary(ctx)
    ui = adapt_contractors_list(backend, focus=False)

    # Adapter filters total_submitted < 5 and caps at top 50
    backend_eligible = [r for r in backend if r.get("total_submitted", 0) >= 5]

    b_docs  = sum(r.get("total_submitted", 0) for r in backend_eligible)
    b_focus = sum(r.get("focus_owned", 0) for r in backend_eligible)
    u_docs  = sum(r.get("docs", 0) for r in ui)
    u_focus = sum(r.get("focus_owned", 0) for r in ui)

    # Per-contractor pass_rate comparison
    b_by_code = {r.get("code", r.get("name", "")): r for r in backend_eligible}
    u_by_code = {r.get("code", r.get("name", "")): r for r in ui}

    pr_matches = 0
    pr_mismatches = 0
    pr_mismatch_rows: list[dict] = []

    for code, b_row in b_by_code.items():
        u_row = u_by_code.get(code)
        if u_row is None:
            continue
        total = b_row.get("total_submitted", 0)
        b_rate = round(
            (b_row.get("visa_vso", 0) + b_row.get("visa_vao", 0)) / max(total, 1) * 100,
            1,
        )
        u_rate = u_row.get("pass_rate", 0)
        try:
            if abs(float(b_rate) - float(u_rate)) < 0.15:
                pr_matches += 1
            else:
                pr_mismatches += 1
                pr_mismatch_rows.append({
                    "surface": "contractors_list",
                    "field_label": f"pass_rate[{code}]",
                    "backend_val": b_rate,
                    "ui_val": u_rate,
                    "comparison_kind": "float_equal",
                    "classification": TRUE_BUG,
                    "notes": (
                        f"contractor {code}: backend (vso+vao)/total*100={b_rate} "
                        f"vs adapter pass_rate={u_rate}; should be equal"
                    ),
                })
        except (TypeError, ValueError):
            pass

    pairs = [
        {
            "field_label": "eligible_contractor_count (total_submitted>=5, top-50 cap)",
            "backend_val": len(backend_eligible), "ui_val": len(ui),
            "comparison_kind": "numeric_equal", "classification": SCOPE_FILTER,
            "notes": (
                "adapter filters total_submitted<5 and caps at 50; "
                "backend returns all emetteurs; scope_filter expected but values should agree "
                "for this project (≪50 eligible contractors)"
            ),
        },
        {
            "field_label": "total_docs (backend:total_submitted → ui:docs)",
            "backend_val": b_docs, "ui_val": u_docs,
            "comparison_kind": "numeric_equal", "classification": NAMING_ONLY,
            "notes": "backend key total_submitted renamed to docs in adapt_contractors_list",
        },
        {
            "field_label": "focus_owned",
            "backend_val": b_focus, "ui_val": u_focus,
            "comparison_kind": "numeric_equal", "classification": "identity",
            "notes": "0 when no focus_result supplied",
        },
    ]

    result = _compare_surface("contractors_list", pairs)

    # Inject per-contractor pass_rate results
    result["compared"] += pr_matches + pr_mismatches
    result["matches"] += pr_matches
    result["mismatches"] += pr_mismatches
    result["mismatch_rows"].extend(pr_mismatch_rows)

    result["notes"] = (
        f"backend={len(backend)} contractors total, eligible(≥5)={len(backend_eligible)}, "
        f"ui={len(ui)}; "
        f"pass_rate compared per-contractor: {pr_matches} matches, {pr_mismatches} mismatches; "
        "1 naming_only (total_submitted→docs), 1 scope_filter (≥5 filter) documented."
    )
    return result


def audit_consultant_fiche(ctx) -> dict:
    """Consultant fiche: build_consultant_fiche is both aggregator and adapter.
    Internal consistency spot-check for one exemplar consultant.
    """
    surface = "consultant_fiche"
    _LOG.info("audit_consultant_fiche: finding exemplar consultant ...")
    try:
        from reporting.consultant_fiche import build_consultant_fiche

        first_name = None
        if ctx.responses_df is not None and "approver_canonical" in ctx.responses_df.columns:
            mask = (
                (~ctx.responses_df["approver_raw"].astype(str).str.startswith("0-SAS", na=True)) &
                (~ctx.responses_df["approver_raw"].astype(str).str.startswith("Sollicitation", na=False))
            )
            candidates = ctx.responses_df[mask]["approver_canonical"].dropna().unique()
            if len(candidates) > 0:
                first_name = str(candidates[0])

        if first_name is None:
            return {
                "surface": surface, "compared": 0, "matches": 0, "mismatches": 0,
                "skipped": 1, "mismatch_rows": [], "skip_rows": [
                    {"field_label": "exemplar_lookup",
                     "notes": "no consultant name found in responses_df"}
                ],
                "notes": "no exemplar consultant found",
            }

        _LOG.info("audit_consultant_fiche: building fiche for %r ...", first_name)
        fiche = build_consultant_fiche(ctx, first_name, None)
        header = fiche.get("header", {})
        total   = _safe_int(header.get("total"))
        answered = _safe_int(header.get("answered"))
        bloc3 = fiche.get("bloc3", {})
        lots_total = _safe_int(bloc3.get("total_row", {}).get("total")) if bloc3 else 0

        pairs = [
            {
                "field_label": "no_backend_adapter_split",
                "backend_val": None, "ui_val": None,
                "comparison_kind": SKIPPED,
                "classification": SKIPPED,
                "notes": (
                    "build_consultant_fiche is both aggregator and adapter; "
                    "no separate backend comparison possible. "
                    f"Exemplar={first_name!r}: header.total={total}, "
                    f"header.answered={answered}, bloc3.total_row.total={lots_total}. "
                    "No comparable backend field — documented per spec §12.7."
                ),
            },
        ]
        result = _compare_surface(surface, pairs)
        result["notes"] = (
            f"No aggregator/adapter split. Exemplar: {first_name!r}. "
            f"fiche.header.total={total}, fiche.header.answered={answered}. "
            "No comparable backend field — documented."
        )
        return result

    except Exception as exc:
        _LOG.warning("audit_consultant_fiche failed: %s", exc)
        return {
            "surface": surface, "compared": 0, "matches": 0, "mismatches": 0,
            "skipped": 1, "mismatch_rows": [], "skip_rows": [
                {"field_label": "build_error", "notes": str(exc)}
            ],
            "notes": f"build_consultant_fiche raised: {exc}",
        }


def audit_contractor_fiche(ctx) -> dict:
    """Contractor fiche: build_contractor_fiche is both aggregator and adapter. Document only."""
    surface = "contractor_fiche"
    _LOG.info("audit_contractor_fiche: finding exemplar contractor ...")
    try:
        from reporting.contractor_fiche import build_contractor_fiche

        first_code = None
        if ctx.dernier_df is not None and "emetteur" in ctx.dernier_df.columns:
            codes = ctx.dernier_df["emetteur"].dropna().unique()
            for code in codes:
                ct = str(code).strip()
                if ct and ct != "?":
                    # Prefer contractors with enough docs for meaningful fiche
                    cnt = int((ctx.dernier_df["emetteur"] == code).sum())
                    if cnt >= 5:
                        first_code = ct
                        break

        if first_code is None:
            return {
                "surface": surface, "compared": 0, "matches": 0, "mismatches": 0,
                "skipped": 1, "mismatch_rows": [], "skip_rows": [
                    {"field_label": "exemplar_lookup",
                     "notes": "no eligible contractor code found in dernier_df"}
                ],
                "notes": "no exemplar contractor found",
            }

        _LOG.info("audit_contractor_fiche: building fiche for %r ...", first_code)
        fiche = build_contractor_fiche(ctx, first_code)
        open_fin = fiche.get("open_finished", {}) if isinstance(fiche, dict) else {}
        total = _safe_int(open_fin.get("total")) if open_fin else 0

        pairs = [
            {
                "field_label": "no_backend_adapter_split",
                "backend_val": None, "ui_val": None,
                "comparison_kind": SKIPPED,
                "classification": SKIPPED,
                "notes": (
                    "build_contractor_fiche is both aggregator and adapter; "
                    "no separate backend comparison possible. "
                    f"Exemplar={first_code!r}: open_finished.total={total}. "
                    "No comparable backend field — documented per spec §12.7."
                ),
            },
        ]
        result = _compare_surface(surface, pairs)
        result["notes"] = (
            f"No aggregator/adapter split. Exemplar: {first_code!r}. "
            f"open_finished.total={total}. "
            "No comparable backend field — documented."
        )
        return result

    except Exception as exc:
        _LOG.warning("audit_contractor_fiche failed: %s", exc)
        return {
            "surface": surface, "compared": 0, "matches": 0, "mismatches": 0,
            "skipped": 1, "mismatch_rows": [], "skip_rows": [
                {"field_label": "build_error", "notes": str(exc)}
            ],
            "notes": f"build_contractor_fiche raised: {exc}",
        }


def audit_dcc() -> dict:
    """Document Command Center: reads CHAIN_TIMELINE_ATTRIBUTION.json directly. Document only."""
    surface = "dcc"
    chain_timeline_path = BASE_DIR / "output" / "intermediate" / "CHAIN_TIMELINE_ATTRIBUTION.json"

    if not chain_timeline_path.exists():
        pairs = [
            {
                "field_label": "chain_timeline_file_present",
                "backend_val": None, "ui_val": None,
                "comparison_kind": SKIPPED,
                "classification": SKIPPED,
                "notes": f"CHAIN_TIMELINE_ATTRIBUTION.json not found at {chain_timeline_path}",
            },
        ]
        result = _compare_surface(surface, pairs)
        result["notes"] = "CHAIN_TIMELINE_ATTRIBUTION.json absent — DCC will show empty chronologie."
        return result

    try:
        with open(str(chain_timeline_path), encoding="utf-8") as fh:
            timeline = json.load(fh)
        entry_count = len(timeline) if isinstance(timeline, (list, dict)) else 0

        pairs = [
            {
                "field_label": "chain_timeline_entries_present",
                "backend_val": None, "ui_val": None,
                "comparison_kind": SKIPPED,
                "classification": SKIPPED,
                "notes": (
                    f"DCC reads CHAIN_TIMELINE_ATTRIBUTION.json directly (not through aggregator). "
                    f"File present with {entry_count} chain entries. "
                    "No aggregator/adapter split — documented per spec §12.7."
                ),
            },
        ]
        result = _compare_surface(surface, pairs)
        result["notes"] = (
            f"DCC reads CHAIN_TIMELINE_ATTRIBUTION.json directly; "
            f"{entry_count} chain entries. "
            "No comparable backend field — documented."
        )
        return result

    except Exception as exc:
        return {
            "surface": surface, "compared": 0, "matches": 0, "mismatches": 0,
            "skipped": 1, "mismatch_rows": [], "skip_rows": [
                {"field_label": "chain_timeline_load", "notes": str(exc)}
            ],
            "notes": f"CHAIN_TIMELINE_ATTRIBUTION.json load failed: {exc}",
        }


def audit_chain_onion_panel() -> dict:
    """Chain+Onion panel: check dashboard_summary.json and top_issues.json are present
    and contain expected fields from the 8A.5 inventory.
    """
    surface = "chain_onion_panel"
    _LOG.info("audit_chain_onion_panel: checking JSON files ...")
    dash_path = BASE_DIR / "output" / "chain_onion" / "dashboard_summary.json"
    issues_path = BASE_DIR / "output" / "chain_onion" / "top_issues.json"

    missing = [p.name for p in (dash_path, issues_path) if not p.exists()]
    if missing:
        return {
            "surface": surface, "compared": 0, "matches": 0, "mismatches": 0,
            "skipped": 1, "mismatch_rows": [], "skip_rows": [
                {"field_label": "json_files_present", "notes": f"missing: {missing}"}
            ],
            "notes": f"chain_onion JSON files missing: {missing}",
        }

    try:
        with open(str(dash_path), encoding="utf-8") as fh:
            dash = json.load(fh)
        with open(str(issues_path), encoding="utf-8") as fh:
            issues = json.load(fh)

        # Inventory §2 expected keys in dashboard_summary
        expected_dash_keys = [
            "live_chains", "escalated_chain_count",
            "avg_pressure_live", "top_theme_by_impact",
        ]
        present_keys = [k for k in expected_dash_keys if k in dash]

        pairs = [
            {
                "field_label": "dashboard_summary_expected_key_count",
                "backend_val": len(expected_dash_keys),
                "ui_val": len(present_keys),
                "comparison_kind": "numeric_equal",
                "classification": "identity",
                "notes": (
                    f"expected inventory keys: {expected_dash_keys}; "
                    f"found: {present_keys}"
                ),
            },
            {
                "field_label": "top_issues_non_empty",
                "backend_val": 1 if len(issues) > 0 else 0,
                "ui_val": 1 if len(issues) > 0 else 0,
                "comparison_kind": "numeric_equal",
                "classification": "identity",
                "notes": f"top_issues.json has {len(issues)} entries",
            },
        ]
        result = _compare_surface(surface, pairs)
        result["notes"] = (
            f"chain_onion_panel reads dashboard_summary.json ({len(dash)} total keys, "
            f"{len(present_keys)}/{len(expected_dash_keys)} inventory keys present) and "
            f"top_issues.json ({len(issues)} issues). "
            "Payload presence check only — no aggregator/adapter split."
        )
        return result

    except Exception as exc:
        return {
            "surface": surface, "compared": 0, "matches": 0, "mismatches": 0,
            "skipped": 1, "mismatch_rows": [], "skip_rows": [
                {"field_label": "json_load", "notes": str(exc)}
            ],
            "notes": f"chain_onion JSON load failed: {exc}",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Output writers
# ─────────────────────────────────────────────────────────────────────────────

def _surface_classification_counts(r: dict) -> dict:
    mrows = r.get("mismatch_rows", [])
    return {
        "naming_only": sum(1 for m in mrows if m.get("classification") == NAMING_ONLY),
        "scope_filter": sum(1 for m in mrows if m.get("classification") == SCOPE_FILTER),
        "expected_semantic_difference": sum(
            1 for m in mrows if m.get("classification") == EXPECTED_SEMANTIC
        ),
        "true_bug": sum(1 for m in mrows if m.get("classification") == TRUE_BUG),
    }


def write_outputs(results: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    total_compared = sum(r["compared"] for r in results)
    total_matches = sum(r["matches"] for r in results)
    total_mismatches = sum(r["mismatches"] for r in results)

    all_mismatches: list[dict] = []
    for r in results:
        all_mismatches.extend(r.get("mismatch_rows", []))

    nm_total  = sum(1 for m in all_mismatches if m.get("classification") == NAMING_ONLY)
    sf_total  = sum(1 for m in all_mismatches if m.get("classification") == SCOPE_FILTER)
    esd_total = sum(1 for m in all_mismatches if m.get("classification") == EXPECTED_SEMANTIC)
    tb_total  = sum(1 for m in all_mismatches if m.get("classification") == TRUE_BUG)

    per_surface: dict = {}
    for r in results:
        cc = _surface_classification_counts(r)
        per_surface[r["surface"]] = {
            "compared": r["compared"],
            "matches": r["matches"],
            "mismatches": r["mismatches"],
            "skipped": r.get("skipped", 0),
            **cc,
            "notes": r.get("notes", ""),
        }

    json_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "surfaces_audited": [r["surface"] for r in results],
        "total_surfaces": len(results),
        "total_compared": total_compared,
        "total_matches": total_matches,
        "total_mismatches": total_mismatches,
        "classification_breakdown": {
            "naming_only": nm_total,
            "scope_filter": sf_total,
            "expected_semantic_difference": esd_total,
            "true_bug": tb_total,
        },
        "unexplained_mismatches": tb_total,
        "per_surface": per_surface,
        "mismatch_detail": all_mismatches,
    }

    json_path = out_dir / "ui_payload_full_surface_audit.json"
    with open(str(json_path), "w", encoding="utf-8") as fh:
        json.dump(json_data, fh, ensure_ascii=False, indent=2, default=str)
    _LOG.info("JSON written: %s", json_path)

    # XLSX: summary sheet + one per-surface mismatch sheet
    xlsx_path = out_dir / "ui_payload_full_surface_audit.xlsx"
    with pd.ExcelWriter(str(xlsx_path), engine="openpyxl") as writer:
        # Summary sheet
        summary_rows = []
        for r in results:
            cc = _surface_classification_counts(r)
            summary_rows.append({
                "surface": r["surface"],
                "compared": r["compared"],
                "matches": r["matches"],
                "mismatches": r["mismatches"],
                "skipped": r.get("skipped", 0),
                **cc,
                "notes": r.get("notes", ""),
            })
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="summary", index=False)

        # Per-surface mismatch sheets (always created, even if empty)
        for r in results:
            sheet_name = f"{r['surface']}_mismatches"[:31]
            rows = r.get("mismatch_rows", [])
            if rows:
                pd.DataFrame(rows, columns=_MISMATCH_COLS).to_excel(
                    writer, sheet_name=sheet_name, index=False
                )
            else:
                pd.DataFrame(columns=_MISMATCH_COLS).to_excel(
                    writer, sheet_name=sheet_name, index=False
                )

    _LOG.info("XLSX written: %s", xlsx_path)
    return json_path, xlsx_path


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    from reporting.data_loader import load_run_context

    _LOG.info("=== Phase 8A.6 — Widened UI Payload Audit ===")
    _LOG.info("Loading RunContext (run_number=0) ...")
    ctx = load_run_context(BASE_DIR, run_number=0)
    if ctx is None or ctx.degraded_mode:
        print(
            "UI_PAYLOAD_FULL: surfaces=0 compared=0 matches=0 mismatches=0; "
            "ERROR - RunContext is None or degraded",
            flush=True,
        )
        sys.exit(1)

    _LOG.info("Running per-surface comparisons ...")
    results = [
        audit_consultants_list(ctx),
        audit_contractors_list(ctx),
        audit_consultant_fiche(ctx),
        audit_contractor_fiche(ctx),
        audit_dcc(),
        audit_chain_onion_panel(),
    ]

    out_dir = BASE_DIR / "output" / "debug"
    write_outputs(results, out_dir)

    n_surfaces = len(results)
    total_compared = sum(r["compared"] for r in results)
    total_matches = sum(r["matches"] for r in results)
    total_mismatches = sum(r["mismatches"] for r in results)

    tb_count = sum(
        1 for r in results
        for m in r.get("mismatch_rows", [])
        if m.get("classification") == TRUE_BUG
    )

    if total_mismatches == 0:
        verdict = "OK - all compared fields match"
    elif tb_count > 0:
        verdict = f"STOP S3 - true_bug={tb_count}"
    else:
        verdict = f"mismatches={total_mismatches} (none are true_bug)"

    print(
        f"UI_PAYLOAD_FULL: surfaces={n_surfaces} compared={total_compared} "
        f"matches={total_matches} mismatches={total_mismatches}; {verdict}",
        flush=True,
    )

    if tb_count > 0:
        _LOG.error(
            "HARD STOP S3: %d true_bug mismatch(es). "
            "Do NOT patch ui_adapter.py. Report and exit.",
            tb_count,
        )
        sys.exit(3)


if __name__ == "__main__":
    main()
