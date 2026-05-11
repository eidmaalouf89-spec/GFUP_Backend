"""
Standalone HTML Snapshot — read-only frozen JANSA cockpit.

Gathers composed UI payloads from `app.Api` (the same payloads that already
feed the live UI), bundles them as one JSON blob, and writes a single
self-contained HTML file under ``output/exports/``.

Rules:
- No business logic is recomputed here. Every field is sourced from existing
  composed payloads (Api.get_overview_for_ui, get_consultants_for_ui, etc.).
- The generated HTML embeds the production UI assets (tokens.js, JSX
  components) inline and replaces ``window.jansaBridge`` with a snapshot
  bridge that resolves all read calls from embedded JSON.
- Mutating actions (Generate GF, AI audit pack, imports, pipeline, save) are
  disabled by the snapshot bridge regardless of which UI surface invokes them.
"""

from __future__ import annotations

import html as _html
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _log(msg: str) -> None:
    print(f"[snapshot] {msg}", flush=True)


# ── JSON sanitizer (mirrors app._sanitize_for_json) ────────────
def _sanitize(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (int, bool, str)):
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(x) for x in obj]
    try:
        import pandas as pd
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat() if not pd.isna(obj) else None
        if pd.isna(obj):
            return None
    except Exception:
        pass
    try:
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            f = float(obj)
            return None if (math.isnan(f) or math.isinf(f)) else f
        if isinstance(obj, np.bool_):
            return bool(obj)
    except Exception:
        pass
    try:
        return str(obj)
    except Exception:
        return None


# ── Drilldown shape constants ──────────────────────────────────
_BUCKET_NAMES = [
    "FERMER_MAINTENANT",
    "DECISION_MOEX",
    "ENTREPRISE_A_RELANCER",
    "CONSULTANT_A_ATTAQUER",
]

# Dashboard drilldown kinds the UI can request. params=None means "no params"
# (single key). Lists of params expand to multiple cached entries.
_DASHBOARD_DRILLDOWNS: List[tuple] = [
    ("submitted", [None]),
    ("pending_blocking", [None]),
    ("focus_priority", [{"priority": p} for p in (1, 2, 3, 4)]),
    ("operational_total", [None]),
    ("operational_fresh", [None]),
    ("operational_stale", [None]),
    ("operational_moex", [None, {"scope": "fresh"}, {"scope": "stale"}]),
    ("operational_consultants", [None, {"tier": "PRIMARY"}, {"tier": "SECONDARY"}]),
    ("operational_enterprise_ref", [None]),
    ("operational_priority", [{"priority": p} for p in (1, 2, 3, 4)]),
    # visa_segment expanded dynamically from overview.visa_flow
]

# Consultant fiche filter keys the UI can request at the global/header level
# (no lot, no period).
_FICHE_FILTER_KEYS_NO_LOT = [
    "answered", "open_count", "open_blocking",
    "s1", "s2", "s3", "hm",
    "open_ok", "open_late",
    "open_blocking_ok", "open_blocking_late", "open_non_blocking",
]

# Per-lot filter keys (bloc3.lots → clickable cells).
_FICHE_FILTER_KEYS_PER_LOT = [
    "total", "s1", "s2", "s3", "hm",
    "open_blocking_ok", "open_blocking_late", "open_non_blocking",
]

# Per-period filter keys (bloc1 row cells → clickable with periodLabel).
_FICHE_FILTER_KEYS_PER_PERIOD = [
    "period_opened", "period_closed",
    "s1", "s2", "s3", "hm",
    "open_blocking_ok", "open_blocking_late", "open_non_blocking",
]

# DCC panel cap: 0 (or None) means "build for every harvested numero".
_DCC_PANEL_CAP = 0


def _params_key(params: Optional[Dict[str, Any]]) -> str:
    """Stable cache key for (kind, params, focus) — matches what the JS side
    will build to look the entry up.
    """
    if not params:
        return ""
    return json.dumps(params, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _add_numero(numero_set: Dict[str, Optional[str]], numero, indice=None):
    if numero is None:
        return
    key = str(numero).strip()
    if not key:
        return
    if key not in numero_set or numero_set[key] is None:
        numero_set[key] = (str(indice).strip() if indice else None)


def _harvest_rows(rows, numero_set: Dict[str, Optional[str]]):
    for row in (rows or []):
        if isinstance(row, dict):
            _add_numero(numero_set, row.get("numero"), row.get("indice"))


# ── Snapshot payload builder ───────────────────────────────────
def build_snapshot_payload(api, base_dir: Path) -> Dict[str, Any]:
    """Collect every composed UI payload needed for the snapshot, for BOTH
    focus modes (so the snapshot UI Focus toggle keeps working offline).

    `api` is an instance of app.Api (already initialized + cache-ready).
    """
    meta = _build_meta(api, base_dir)
    data: Dict[str, Any] = {}

    # Two-mode loader: returns (focus_off_payload, focus_on_payload)
    def _both(loader):
        off = loader(False, 90)
        try:
            on = loader(True, 90)
        except Exception as exc:
            on = {"error": str(exc)}
        return off, on

    t_start = time.time()
    _log("core dashboards (dual focus) …")
    ov_off, ov_on = _both(api.get_overview_for_ui)
    cs_off, cs_on = _both(api.get_consultants_for_ui)
    ct_off, ct_on = _both(api.get_contractors_for_ui)
    data["overview"] = {"focus_off": ov_off, "focus_on": ov_on}
    data["consultants"] = {"focus_off": cs_off, "focus_on": cs_on}
    data["contractors"] = {"focus_off": ct_off, "focus_on": ct_on}
    data["chain_intel"] = api.get_chain_onion_intel(50)
    _log(f"core done ({time.time()-t_start:.1f}s)")

    _log("action MOEX home + queues …")
    data["counter_attack_home"] = api.get_counter_attack_home()
    queues: Dict[str, Any] = {}
    for b in _BUCKET_NAMES:
        try:
            queues[b] = api.get_counter_attack_queue(b, 500)
        except Exception as exc:
            queues[b] = {"available": False, "error": str(exc), "bucket": b, "rows": []}
    data["counter_attack_queues"] = queues

    _log("action MOEX items …")
    ca_items: Dict[str, Any] = {}
    for qpayload in queues.values():
        for row in ((qpayload or {}).get("rows") or []):
            item_id = row.get("item_id") or row.get("id")
            if not item_id or item_id in ca_items:
                continue
            try:
                ca_items[str(item_id)] = api.get_counter_attack_item(str(item_id))
            except Exception as exc:
                ca_items[str(item_id)] = {"available": False, "found": False, "error": str(exc)}
    data["counter_attack_items"] = ca_items
    _log(f"action MOEX items: {len(ca_items)} ({time.time()-t_start:.1f}s)")

    # ── Per-consultant fiches (dual focus)
    consultant_fiches: Dict[str, Dict[str, Any]] = {}
    roster = list(cs_off or [])
    _log(f"consultant fiches: {len(roster)} × 2 focus …")
    for i, c in enumerate(roster, 1):
        name = c.get("canonical_name") or c.get("name")
        if not name or name in consultant_fiches:
            continue
        off, on = _both(lambda f, s, n=name: api.get_fiche_for_ui(n, f, s))
        consultant_fiches[name] = {"focus_off": off, "focus_on": on}
        if i % 10 == 0:
            _log(f"  consultant {i}/{len(roster)} ({time.time()-t_start:.1f}s)")
    data["consultant_fiches"] = consultant_fiches

    # ── Per-contractor fiches (dual focus)
    contractor_fiches: Dict[str, Dict[str, Any]] = {}
    contractors_list = (ct_off or {}).get("list") or []
    _log(f"contractor fiches: {len(contractors_list)} × 2 focus …")
    for i, c in enumerate(contractors_list, 1):
        code = c.get("code")
        if not code or code in contractor_fiches:
            continue
        off, on = _both(lambda f, s, k=code: api.get_contractor_fiche_for_ui(k, f, s))
        contractor_fiches[code] = {"focus_off": off, "focus_on": on}
        if i % 10 == 0:
            _log(f"  contractor {i}/{len(contractors_list)} ({time.time()-t_start:.1f}s)")
    data["contractor_fiches"] = contractor_fiches

    # ── Pre-build dashboard drilldowns for BOTH focus modes
    # Cache key: "<kind>|<paramsJSON>|<focus 0|1>"
    drilldowns: Dict[str, Any] = {}
    # Expand visa_segment dynamically from each overview.visa_flow
    visa_segments = set()
    for ov in (ov_off, ov_on):
        flow = (ov or {}).get("visa_flow") or {}
        for k in flow.keys():
            if k in ("submitted", "answered", "pending", "on_time", "late"):
                continue
            visa_segments.add(k)
    visa_segment_params = [{"segment": s} for s in sorted(visa_segments)] if visa_segments else []

    dashboard_specs = list(_DASHBOARD_DRILLDOWNS) + [
        ("visa_segment", visa_segment_params or [None]),
    ]
    numero_set: Dict[str, Optional[str]] = {}
    total_dd = sum(max(len(pl), 1) for _, pl in dashboard_specs) * 2
    _log(f"dashboard drilldowns: {total_dd} (kind × params × focus) …")
    done = 0
    for kind, param_list in dashboard_specs:
        for params in param_list:
            for focus in (False, True):
                key = f"{kind}|{_params_key(params)}|{1 if focus else 0}"
                try:
                    payload = api.get_documents_drilldown(kind, params or {}, focus, 90)
                except Exception as exc:
                    payload = {"rows": [], "total_count": 0, "truncated": False,
                               "kind": kind, "params": params, "error": str(exc)}
                drilldowns[key] = payload
                _harvest_rows((payload or {}).get("rows"), numero_set)
                done += 1
    data["drilldowns"] = drilldowns
    _log(f"dashboard drilldowns done ({time.time()-t_start:.1f}s)")

    # ── Pre-build consultant-fiche drilldowns (full 1:1 parity)
    # Cache keys:
    #   "<consultant>|<filterKey>||<focus 0|1>"            — global (no lot, no period)
    #   "<consultant>|<filterKey>|<lotName>|<focus 0|1>"   — bloc3 per-lot
    #   "<consultant>|<filterKey>||<focus 0|1>|<period>"   — bloc1 per-period
    fiche_drilldowns: Dict[str, Any] = {}

    def _call_doc_details(name, fk, lot, focus, period):
        try:
            return api.get_doc_details(name, fk, lot, focus, 90, period)
        except Exception as exc:
            return {"docs": [], "count": 0, "filter_key": fk, "lot": lot,
                    "consultant": name, "period_label": period, "error": str(exc)}

    # Collect per-consultant lot + period universes from both focus variants.
    fiche_universe: Dict[str, Dict[str, set]] = {}
    for name, both in consultant_fiches.items():
        lots: set = set()
        periods: set = set()
        for variant in (both.get("focus_off"), both.get("focus_on")):
            if not isinstance(variant, dict):
                continue
            for lot in ((variant.get("bloc3") or {}).get("lots") or []):
                if isinstance(lot, dict) and lot.get("name"):
                    lots.add(str(lot["name"]))
            for row in (variant.get("bloc1") or []):
                if isinstance(row, dict) and row.get("label"):
                    periods.add(str(row["label"]))
        fiche_universe[name] = {"lots": lots, "periods": periods}

    # Pre-compute totals for progress reporting.
    total_fd = 0
    for name, uni in fiche_universe.items():
        total_fd += 2 * len(_FICHE_FILTER_KEYS_NO_LOT)
        total_fd += 2 * len(uni["lots"]) * len(_FICHE_FILTER_KEYS_PER_LOT)
        total_fd += 2 * len(uni["periods"]) * len(_FICHE_FILTER_KEYS_PER_PERIOD)
    _log(f"fiche drilldowns: {total_fd} (global + per-lot + per-period × 2 focus) …")

    fd_done = 0
    for name, uni in fiche_universe.items():
        for focus in (False, True):
            f_flag = 1 if focus else 0
            # Global keys (no lot, no period)
            for fk in _FICHE_FILTER_KEYS_NO_LOT:
                key = f"{name}|{fk}||{f_flag}"
                payload = _call_doc_details(name, fk, None, focus, None)
                fiche_drilldowns[key] = payload
                _harvest_rows((payload or {}).get("docs"), numero_set)
                fd_done += 1
            # Per-lot keys
            for lot_name in uni["lots"]:
                for fk in _FICHE_FILTER_KEYS_PER_LOT:
                    key = f"{name}|{fk}|{lot_name}|{f_flag}"
                    payload = _call_doc_details(name, fk, lot_name, focus, None)
                    fiche_drilldowns[key] = payload
                    _harvest_rows((payload or {}).get("docs"), numero_set)
                    fd_done += 1
            # Per-period keys (bloc1 cells)
            for period in uni["periods"]:
                for fk in _FICHE_FILTER_KEYS_PER_PERIOD:
                    key = f"{name}|{fk}||{f_flag}|{period}"
                    payload = _call_doc_details(name, fk, None, focus, period)
                    fiche_drilldowns[key] = payload
                    _harvest_rows((payload or {}).get("docs"), numero_set)
                    fd_done += 1
            if fd_done > 0:
                _log(f"  fiche drilldown {fd_done}/{total_fd} ({time.time()-t_start:.1f}s)")
    data["fiche_drilldowns"] = fiche_drilldowns
    _log(f"fiche drilldowns done ({time.time()-t_start:.1f}s)")

    # ── DCC panel pre-builds: chain intel + CA queues + CA items + harvested drilldown rows
    for issue in (data["chain_intel"] or {}).get("top_issues", []):
        _add_numero(numero_set, issue.get("family_key") or issue.get("numero"), issue.get("indice"))
    for b in _BUCKET_NAMES:
        for row in (queues.get(b, {}).get("rows") or []):
            _add_numero(numero_set, row.get("numero"), row.get("indice"))
    for item in ca_items.values():
        if isinstance(item, dict):
            header = item.get("header") or {}
            _add_numero(numero_set, header.get("numero"), header.get("indice"))

    cap = _DCC_PANEL_CAP if _DCC_PANEL_CAP else len(numero_set)
    total_panels = min(len(numero_set), cap)
    _log(f"DCC panels: {total_panels} of {len(numero_set)} harvested numeros (cap={cap if _DCC_PANEL_CAP else 'none'}) …")
    dcc_panels: Dict[str, Any] = {}
    chain_timelines: Dict[str, Any] = {}
    for i, (numero, indice) in enumerate(numero_set.items()):
        if _DCC_PANEL_CAP and i >= _DCC_PANEL_CAP:
            break
        key = f"{numero}|{indice or ''}"
        try:
            dcc_panels[key] = api.get_document_command_center(numero, indice, False, 30)
        except Exception as exc:
            dcc_panels[key] = {"error": str(exc), "numero": numero, "indice": indice}
        if numero not in chain_timelines:
            try:
                chain_timelines[numero] = api.get_chain_timeline(numero)
            except Exception as exc:
                chain_timelines[numero] = {"error": str(exc), "numero": numero}
        if (i + 1) % 100 == 0:
            _log(f"  DCC panel {i+1}/{total_panels} ({time.time()-t_start:.1f}s)")
    data["dcc_panels"] = dcc_panels
    data["chain_timelines"] = chain_timelines
    _log(f"DCC panels done ({time.time()-t_start:.1f}s)")

    # ── Search index for offline DCC substring search
    search_index: List[Dict[str, Any]] = []
    seen: set = set()
    for key, panel in dcc_panels.items():
        if not isinstance(panel, dict):
            continue
        header = panel.get("header") or {}
        numero = header.get("numero") or key.split("|", 1)[0]
        indice = header.get("indice")
        sig = f"{numero}|{indice or ''}"
        if sig in seen:
            continue
        seen.add(sig)
        search_index.append({
            "numero": str(numero) if numero is not None else None,
            "indice": str(indice) if indice not in (None, "") else None,
            "titre": header.get("titre") or header.get("libelle_du_document"),
            "emetteur_code": header.get("emetteur_code") or header.get("emetteur"),
            "emetteur_name": header.get("emetteur_name"),
            "lot": header.get("lot"),
            "status": header.get("status") or header.get("latest_status"),
        })
    data["search_index"] = search_index

    return {"meta": meta, "data": _sanitize(data)}


def _build_meta(api, base_dir: Path) -> Dict[str, Any]:
    run_number = None
    data_date = None
    try:
        st = api.get_app_state() or {}
        run_number = st.get("current_run") or st.get("run_number") or st.get("latest_run")
        data_date = st.get("data_date") or st.get("data_date_str")
    except Exception:
        pass
    if run_number is None:
        try:
            ov = api.get_overview_for_ui(False, 90) or {}
            run_number = ov.get("run_number")
            data_date = data_date or ov.get("data_date_str")
        except Exception:
            pass
    return {
        "mode": "snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_number": run_number,
        "data_date": data_date,
        "source": "JANSA composed UI payloads (live run)",
        "disabled_features": [
            "generate_gf",
            "generate_ai_audit_pack",
            "import_ged",
            "import_reports",
            "run_pipeline",
            "save_corrections",
            "export_team_version",
            "export_drilldown_xlsx",
            "export_action_moex_bucket_xlsx",
        ],
    }


# ── HTML composer ──────────────────────────────────────────────

def _inline_script(text: str, type_attr: Optional[str] = None) -> str:
    # Make sure the content does not break out of the <script> tag.
    safe = text.replace("</script>", "<\\/script>")
    attr = f' type="{type_attr}"' if type_attr else ""
    return f"<script{attr}>\n{safe}\n</script>"


def _encode_json_for_html(payload: Any) -> str:
    s = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    # Defend against </script> escapes and HTML-comment boundaries.
    return (s.replace("<", "\\u003c")
              .replace(">", "\\u003e")
              .replace("&", "\\u0026")
              .replace(" ", "\\u2028")
              .replace(" ", "\\u2029"))


def _compose_html(payload: Dict[str, Any], ui_dir: Path) -> str:
    tokens_js = (ui_dir / "jansa" / "tokens.js").read_text(encoding="utf-8")
    # The live data_bridge.js has a snapshot-mode branch that activates when
    # window.JANSA_SNAPSHOT_DATA is set before it runs (single source of truth).
    data_bridge_js = (ui_dir / "jansa" / "data_bridge.js").read_text(encoding="utf-8")
    jsx_files = [
        "fiche_base.jsx", "overview.jsx", "consultants.jsx", "contractors.jsx",
        "fiche_page.jsx", "contractor_fiche_page.jsx", "runs.jsx", "executer.jsx",
        "document_panel.jsx", "counter_attack.jsx", "shell.jsx",
    ]
    jsx_blobs: List[str] = []
    for fname in jsx_files:
        p = ui_dir / "jansa" / fname
        if not p.exists():
            continue
        jsx_blobs.append(
            f"<!-- {fname} -->\n"
            + _inline_script(p.read_text(encoding="utf-8"), "text/babel")
        )

    # Read the production HTML to reuse its <style> block verbatim (print CSS).
    prod_html = (ui_dir / "jansa-connected.html").read_text(encoding="utf-8")
    style_block = ""
    s = prod_html.find("<style>")
    e = prod_html.find("</style>")
    if s != -1 and e != -1:
        style_block = prod_html[s:e + len("</style>")]

    meta = payload.get("meta", {})
    title_extra = ""
    if meta.get("run_number") is not None:
        title_extra = f" — run {meta['run_number']}"
    snapshot_data_json = _encode_json_for_html(payload.get("data", {}))
    snapshot_meta_json = _encode_json_for_html(meta)

    parts: List[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="fr"><head><meta charset="utf-8">')
    parts.append(f"<title>JANSA · Snapshot{_html.escape(title_extra)}</title>")
    parts.append(style_block or "<style>body{background:#0A0A0B;color:#fff;font-family:Inter,sans-serif;}</style>")
    parts.append("</head><body>")
    parts.append('<div id="root"></div>')

    # React + Babel from CDN (same as production HTML).
    parts.append('<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>')
    parts.append('<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>')
    parts.append('<script crossorigin src="https://unpkg.com/@babel/standalone@7/babel.min.js"></script>')

    # Embedded snapshot data — must come BEFORE the snapshot bridge.
    # The redundant id="jansa-snapshot-data" marker lets bridges detect
    # snapshot mode even before the window globals are set.
    parts.append('<div id="jansa-snapshot-data" hidden></div>')
    parts.append(_inline_script(
        "window.JANSA_SNAPSHOT_META = "
        + snapshot_meta_json + ";\n"
        + "window.JANSA_SNAPSHOT_DATA = "
        + snapshot_data_json + ";"
    ))

    # Tokens + (snapshot-aware) data_bridge — runs BEFORE any JSX.
    parts.append(_inline_script(tokens_js))
    parts.append("<script>window.applyJansaTheme && window.applyJansaTheme('dark');</script>")
    parts.append(_inline_script(data_bridge_js))

    # Inline JSX components.
    parts.extend(jsx_blobs)

    # Mount the React tree. shell.jsx calls window.jansaBridge.init() already.
    parts.append(_inline_script(
        "ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(window.App));",
        "text/babel"
    ))

    parts.append("</body></html>")
    return "\n".join(parts)


def write_standalone_html_snapshot(
    api=None,
    base_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the snapshot and write the HTML file under ``output/exports/``.

    Returns the standard export envelope: {success, path, filename, size_bytes,
    rows_*, message?, error?}.
    """
    try:
        if base_dir is None:
            base_dir = Path(__file__).resolve().parents[2]
        base_dir = Path(base_dir)
        if api is None:
            # Defer import — only construct an Api when invoked without one.
            import sys
            sys.path.insert(0, str(base_dir))
            sys.path.insert(0, str(base_dir / "src"))
            from app import Api  # type: ignore
            api = Api()
            if hasattr(api, "_cache_ready"):
                api._cache_ready.wait()

        if output_dir is None:
            output_dir = base_dir / "output" / "exports"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        payload = build_snapshot_payload(api, base_dir)
        ui_dir = base_dir / "ui"
        body = _compose_html(payload, ui_dir)

        meta = payload.get("meta", {})
        run_number = meta.get("run_number")
        run_part = f"run_{int(run_number):04d}" if isinstance(run_number, (int, float)) and run_number else "run_X"
        ts = datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = f"JANSA_STANDALONE_HTML__{run_part}__{ts}.html"
        tmp = output_dir / (filename + ".tmp")
        final = output_dir / filename
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(final)
        size = final.stat().st_size

        return {
            "success": True,
            "path": str(final),
            "filename": filename,
            "size_bytes": size,
            "message": f"Snapshot HTML écrit ({size // 1024} KB).",
        }
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "path": None,
            "filename": None,
            "size_bytes": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }
