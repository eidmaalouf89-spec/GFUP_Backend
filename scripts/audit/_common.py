"""
scripts/audit/_common.py — Shared helpers for the Phase 0 audit scripts.

Every audit_<metric>.py script delegates CLI parsing, RunContext loading,
contractor iteration, and stage-table rendering to this module.

Hard rules (Phase 0 §3):
  - Reads only the cached runs/run_0000/ artifact. No pipeline rerun.
  - Reads via load_run_context (which goes through the FLAT_GED cache).
  - Tolerant of the truncated CHAIN_TIMELINE_ATTRIBUTION.json artifact
    (D-102 in CANARY_BEN.md). When the JSON is corrupt we fall back to a
    bracket-matched per-key parser; warnings are surfaced at the end.
  - Tolerant of stale .pyc shadowing resolve_emetteur_name (D-104 issue
    discovered in canary). When the symbol is missing from the cached pyc,
    we inject a runtime equivalent before any reporting module imports.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable, Iterable, Optional


# ─────────────────────────────────────────────────────────────────
# BASE_DIR resolution + sys.path bootstrap
# ─────────────────────────────────────────────────────────────────

def _find_base_dir() -> Path:
    """Walk up from this file looking for the project marker."""
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / "src" / "reporting").is_dir() and (p / "data").is_dir():
            return p
    raise RuntimeError("BASE_DIR not found from " + str(here))


BASE_DIR = _find_base_dir()
sys.path.insert(0, str(BASE_DIR / "src"))


# ─────────────────────────────────────────────────────────────────
# Stale-pyc shim — inject resolve_emetteur_name if cached pyc is older
# than the source change that added it (Phase 5, 2026-04-29).
# ─────────────────────────────────────────────────────────────────

def _ensure_resolve_emetteur_name() -> None:
    import reporting.contractor_fiche as cf  # noqa: WPS433
    if hasattr(cf, "resolve_emetteur_name"):
        return
    from reporting.consultant_fiche import CONTRACTOR_REFERENCE as CR

    def _resolve(code):  # type: ignore[no-untyped-def]
        if not code:
            return ""
        entry = CR.get(str(code).strip().upper())
        if entry and entry.get("name"):
            return entry["name"]
        return str(code)

    cf.resolve_emetteur_name = _resolve


_ensure_resolve_emetteur_name()


# ─────────────────────────────────────────────────────────────────
# RunContext + chain timeline loaders
# ─────────────────────────────────────────────────────────────────

from reporting.contractor_quality import _apply_legacy_filter  # noqa: E402
from reporting.data_loader import load_run_context  # noqa: E402


def load_ctx():
    """Load (or hit the in-process cache for) the RunContext."""
    return load_run_context(BASE_DIR)


def get_contractor_codes() -> list:
    """Return the 29 contractor codes (CONTRACTOR_REFERENCE keys)."""
    from reporting.consultant_fiche import CONTRACTOR_REFERENCE
    return list(CONTRACTOR_REFERENCE.keys())


def resolve_canonical(code: str) -> str:
    """Map emetteur code → canonical company name (e.g. BEN → Bentin)."""
    from reporting.contractor_fiche import resolve_emetteur_name
    return resolve_emetteur_name(code)


def filter_emetteur(df, code: str, apply_legacy: bool = True):
    """Filter df by emetteur code, optionally applying the BENTIN_OLD filter.

    Mirrors what contractor_quality.build_contractor_quality does.
    """
    if df is None or df.empty:
        return df
    out = df[df["emetteur"] == code]
    if apply_legacy:
        out = _apply_legacy_filter(out, code)
    return out


def load_chain_timelines_tolerant() -> tuple[dict, list[str]]:
    """Load CHAIN_TIMELINE_ATTRIBUTION.json, with a tolerant fallback for
    the corrupt-artifact case (D-102).

    Returns (timelines_dict, warnings_list).
    """
    p = BASE_DIR / "output" / "intermediate" / "CHAIN_TIMELINE_ATTRIBUTION.json"
    if not p.exists():
        return {}, [f"{p.name} missing"]
    text = p.read_text(encoding="utf-8")
    try:
        return json.loads(text), []
    except json.JSONDecodeError as exc:
        out: dict = {}
        i = text.find("{") + 1
        while True:
            m = re.search(r'\n  "(\d+)": \{', text[i:])
            if not m:
                break
            key = m.group(1)
            start = i + m.end() - 1
            depth, j, in_str, esc = 0, start, False, False
            recovered = False
            while j < len(text):
                c = text[j]
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = not in_str
                elif not in_str:
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                out[key] = json.loads(text[start:j + 1])
                            except Exception:
                                pass
                            i = j + 1
                            recovered = True
                            break
                j += 1
            if not recovered:
                break
        return out, [
            f"CHAIN_TIMELINE_ATTRIBUTION.json corrupt at byte {exc.pos} "
            f"(line {exc.lineno}, col {exc.colno}); recovered {len(out)} chains "
            f"via tolerant parse [D-102]"
        ]


def load_flat_ops_df():
    """Read the GED_OPERATIONS sheet of FLAT_GED.xlsx once, cached on the
    function attribute. Used by audits that need B1-stage counts."""
    if hasattr(load_flat_ops_df, "_cached"):
        return load_flat_ops_df._cached  # type: ignore[attr-defined]
    import pandas as pd
    flat_path = BASE_DIR / "output" / "intermediate" / "FLAT_GED.xlsx"
    df = pd.read_excel(flat_path, sheet_name="GED_OPERATIONS", dtype=str)
    load_flat_ops_df._cached = df  # type: ignore[attr-defined]
    return df


# ─────────────────────────────────────────────────────────────────
# Stage-table rendering
# ─────────────────────────────────────────────────────────────────

# A stage entry is (stage_code, label, value_or_None, optional_note).
StageRow = tuple  # (str, str, object, str)


def render_stage_table(metric: str, contractor: str, stages: list,
                       extra_note: str | None = None) -> tuple[str, bool, str | None]:
    """Render the §6 output format. Returns (text, converges, first_divergence_stage)."""
    lines = [f"=== AUDIT: {metric} for contractor={contractor} ==="]
    counted = [(c, lbl, v, n if len(_pad(s, 4)) >= 4 else "")
               for s in stages
               for (c, lbl, v, n) in [_pad(s, 4)]]
    # Build the printed lines
    for code, lbl, val, note in counted:
        val_str = "—" if val is None else str(val)
        suffix = f"  [{note}]" if note else ""
        lines.append(f"  Stage {code} ({lbl}): {val_str}{suffix}")
    # Convergence: ALL non-None counts equal
    counts = [v for (_c, _lbl, v, _n) in counted if v is not None]
    if not counts:
        converges = True
        first_div = None
    else:
        first = counts[0]
        converges = all(v == first for v in counts)
        first_div = None
        if not converges:
            prev_val = None
            for code, _lbl, v, _n in counted:
                if v is None:
                    continue
                if prev_val is not None and v != prev_val:
                    first_div = code
                    break
                prev_val = v
    if converges:
        lines.append("CONVERGENCE: ALL EQUAL")
    else:
        lines.append(f"CONVERGENCE: DIVERGENCE AT {first_div}")
    if extra_note:
        lines.append(f"NOTE: {extra_note}")
    return "\n".join(lines), converges, first_div


def _pad(t: tuple, n: int) -> tuple:
    """Pad a tuple to length n with empty strings at the tail."""
    return t + ("",) * max(0, n - len(t))


# ─────────────────────────────────────────────────────────────────
# Audit-script entrypoint
# ─────────────────────────────────────────────────────────────────

def audit_main(metric_name: str,
               compute_fn: Callable,
               default_all: bool = False) -> int:
    """Generic entrypoint used by every audit_<metric>.py.

    compute_fn(ctx, contractor_code, shared) -> list[StageRow]
        StageRow = (stage_code, stage_label, count_or_None, optional_note)

    Returns 0 if all contractors converge, 1 otherwise.
    """
    ap = argparse.ArgumentParser(description=f"Phase 0 audit — {metric_name}")
    ap.add_argument("--contractor", default=None,
                    help="One emetteur code (e.g. BEN). If omitted, runs all 29.")
    args = ap.parse_args()

    ctx = load_ctx()
    chain_timelines, warns = load_chain_timelines_tolerant()
    shared = {"chain_timelines": chain_timelines}

    contractors: Iterable[str]
    if args.contractor:
        contractors = [args.contractor]
    else:
        contractors = get_contractor_codes()

    any_divergence = False
    for code in contractors:
        try:
            stages = compute_fn(ctx, code, shared)
        except Exception as exc:
            print(f"=== AUDIT: {metric_name} for contractor={code} ===")
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            print(f"CONVERGENCE: ERROR")
            any_divergence = True
            print()
            continue
        text, converges, _ = render_stage_table(metric_name, code, stages)
        print(text)
        if not converges:
            any_divergence = True
        print()

    for w in warns:
        print(f"WARN: {w}")

    return 1 if any_divergence else 0
