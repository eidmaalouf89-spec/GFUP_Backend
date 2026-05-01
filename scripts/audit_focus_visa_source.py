"""
scripts/audit_focus_visa_source.py
Phase 8A.1 — D-010 Focus-Visa Source Audit

AST-walks src/reporting/*.py for every compute_visa_global_with_date call site.
For each site, records resolver-bypass flags and (for direct-engine sites) a
live-run disagreement count comparing engine visa vs meta-preferred visa.

Outputs:
  output/debug/focus_visa_source_audit.json
  output/debug/focus_visa_source_audit.xlsx

Stdout:
  FOCUS_VISA_AUDIT: call_sites=<n> direct_engine=<n> via_resolver=<n> disagreements_total=<n>
"""
from __future__ import annotations

import ast
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = BASE_DIR / "src"
for _p in (BASE_DIR, _SRC_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pandas as pd

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stderr)
_LOG = logging.getLogger(__name__)

TARGET_FUNC = "compute_visa_global_with_date"
REPORTING_DIR = _SRC_DIR / "reporting"
OUTPUT_DIR = BASE_DIR / "output" / "debug"


# ── AST helpers ───────────────────────────────────────────────────────────────

class _CallSiteVisitor(ast.NodeVisitor):
    """Collect every call site of compute_visa_global_with_date with its enclosing function."""

    def __init__(self):
        self._func_stack: list[str] = []
        self.sites: list[dict] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == TARGET_FUNC:
            enclosing = self._func_stack[-1] if self._func_stack else "<module>"
            try:
                obj_repr = ast.unparse(node.func.value)
            except Exception:
                obj_repr = repr(node.func.value)
            self.sites.append({
                "enclosing_func": enclosing,
                "line": node.lineno,
                "obj_repr": obj_repr,
            })
        self.generic_visit(node)


def _normalize_visa(v: object) -> object:
    """Normalise NaN/blank to None for safe comparison."""
    if v is None:
        return None
    if isinstance(v, float):
        import math
        if math.isnan(v):
            return None
    s = str(v).strip()
    if s in ("", "nan", "None", "NaN"):
        return None
    return s


def _func_references_flat_doc_meta(tree: ast.AST, func_name: str) -> bool:
    """True if the named function body references flat_ged_doc_meta in any form.

    Detects:  ctx.flat_ged_doc_meta            (ast.Attribute)
              flat_ged_doc_meta                 (ast.Name)
              getattr(ctx, "flat_ged_doc_meta") (ast.Constant string argument)
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute) and child.attr == "flat_ged_doc_meta":
                    return True
                if isinstance(child, ast.Name) and child.id == "flat_ged_doc_meta":
                    return True
                # getattr(obj, "flat_ged_doc_meta", ...) pattern
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "getattr"
                    and len(child.args) >= 2
                    and isinstance(child.args[1], ast.Constant)
                    and child.args[1].value == "flat_ged_doc_meta"
                ):
                    return True
    return False


def _infer_visa_columns(tree: ast.AST, func_name: str) -> list[str]:
    """Find DataFrame subscript assignments with '_visa' in the key, within func_name."""
    cols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assign):
                    for tgt in stmt.targets:
                        if isinstance(tgt, ast.Subscript) and isinstance(tgt.slice, ast.Constant):
                            key = str(tgt.slice.value)
                            if "_visa" in key or "visa_global" in key:
                                cols.add(key)
    return sorted(cols)


def audit_ast() -> list[dict]:
    """Return one catalogue record per compute_visa_global_with_date call in src/reporting/."""
    records = []
    for py_file in sorted(REPORTING_DIR.glob("*.py")):
        src = py_file.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src, filename=str(py_file))
        except SyntaxError as exc:
            _LOG.warning("AST parse error in %s: %s", py_file.name, exc)
            continue

        visitor = _CallSiteVisitor()
        visitor.visit(tree)

        for site in visitor.sites:
            func_name = site["enclosing_func"]

            # All compute_visa_global_with_date calls are WorkflowEngine method calls
            # regardless of the local variable name (workflow_engine, we, ctx.workflow_engine…)
            uses_we = True
            uses_flat = _func_references_flat_doc_meta(tree, func_name)
            via_resolver = func_name == "resolve_visa_global"
            cols = _infer_visa_columns(tree, func_name)

            records.append({
                "function_name": func_name,
                "file_path": str(py_file.relative_to(BASE_DIR)).replace("\\", "/"),
                "line_number": site["line"],
                "uses_workflow_engine_directly": uses_we,
                "uses_flat_doc_meta": uses_flat,
                "uses_resolve_visa_global_equivalent": via_resolver,
                "affected_output_columns": cols,
                "count_of_docs_checked": 0,
                "count_of_disagreements": 0,
            })
    return records


# ── Live run disagreement check ───────────────────────────────────────────────

def _live_disagreement_check(records: list[dict]) -> None:
    """Load run 0 and count visa disagreements for the _precompute_focus_columns site.

    Other direct-engine sites (_has_visa_global, build_contractor_fiche, etc.) operate
    per-contractor/per-consultant, so their doc set varies by call; their counts stay 0.
    Only _precompute_focus_columns runs on all dernier docs at context-load time.
    """
    precompute_site = next(
        (r for r in records if r["function_name"] == "_precompute_focus_columns"),
        None,
    )
    if precompute_site is None:
        _LOG.info("[LIVE_CHECK] _precompute_focus_columns not found — skipping.")
        return

    try:
        from reporting.data_loader import load_run_context
        from reporting.aggregator import resolve_visa_global

        ctx = None
        for rn in (0, None):
            try:
                ctx = load_run_context(BASE_DIR, run_number=rn)
                if ctx.dernier_df is not None and ctx.workflow_engine is not None:
                    _LOG.info("[LIVE_CHECK] Loaded run %s: %d dernier docs", rn, len(ctx.dernier_df))
                    break
            except Exception as exc:
                _LOG.warning("[LIVE_CHECK] Could not load run %s: %s", rn, exc)
                ctx = None

        if ctx is None or ctx.dernier_df is None or ctx.workflow_engine is None:
            _LOG.warning("[LIVE_CHECK] No usable RunContext — live counts remain 0.")
            return

        dernier_df = ctx.dernier_df
        n_docs = len(dernier_df)

        if "_visa_global" not in dernier_df.columns:
            _LOG.warning("[LIVE_CHECK] _visa_global column missing — precompute may not have run.")
            precompute_site["count_of_docs_checked"] = n_docs
            return

        # Compare engine visa (_visa_global) vs meta-preferred visa (resolve_visa_global).
        # NaN-normalise both sides: pandas .map() may store None as NaN in object columns.
        disagreements = 0
        for _, row in dernier_df.iterrows():
            doc_id = row["doc_id"]
            engine_visa = _normalize_visa(row.get("_visa_global"))
            resolver_visa = _normalize_visa(resolve_visa_global(ctx, doc_id)[0])
            if engine_visa != resolver_visa:
                disagreements += 1

        precompute_site["count_of_docs_checked"] = n_docs
        precompute_site["count_of_disagreements"] = disagreements

        _LOG.info(
            "[LIVE_CHECK] _precompute_focus_columns: %d docs, %d visa disagreements",
            n_docs, disagreements,
        )

    except Exception as exc:
        _LOG.warning("[LIVE_CHECK] Live check failed (non-fatal): %s", exc)


# ── Output writers ────────────────────────────────────────────────────────────

def _write_json(records: list[dict], path: Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_function": TARGET_FUNC,
        "reporting_dir": str(REPORTING_DIR.relative_to(BASE_DIR)).replace("\\", "/"),
        "call_sites": records,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _write_xlsx(records: list[dict], path: Path) -> None:
    ordered_cols = [
        "function_name",
        "file_path",
        "line_number",
        "uses_workflow_engine_directly",
        "uses_flat_doc_meta",
        "uses_resolve_visa_global_equivalent",
        "affected_output_columns",
        "count_of_docs_checked",
        "count_of_disagreements",
    ]
    rows = []
    for r in records:
        row = {k: r.get(k) for k in ordered_cols}
        row["affected_output_columns"] = ", ".join(r.get("affected_output_columns") or [])
        rows.append(row)
    df = pd.DataFrame(rows, columns=ordered_cols)
    df.to_excel(str(path), index=False, sheet_name="call_sites")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    _LOG.info("AST-walking %s for %s ...", REPORTING_DIR, TARGET_FUNC)
    records = audit_ast()
    _LOG.info("Found %d call site(s).", len(records))

    _live_disagreement_check(records)

    json_path = OUTPUT_DIR / "focus_visa_source_audit.json"
    xlsx_path = OUTPUT_DIR / "focus_visa_source_audit.xlsx"
    _write_json(records, json_path)
    _LOG.info("Written: %s", json_path)
    _write_xlsx(records, xlsx_path)
    _LOG.info("Written: %s", xlsx_path)

    n_total = len(records)
    n_direct = sum(1 for r in records if not r["uses_resolve_visa_global_equivalent"])
    n_via = sum(1 for r in records if r["uses_resolve_visa_global_equivalent"])
    n_disagree = sum(r["count_of_disagreements"] for r in records)

    print(
        f"FOCUS_VISA_AUDIT: call_sites={n_total} direct_engine={n_direct} "
        f"via_resolver={n_via} disagreements_total={n_disagree}"
    )


if __name__ == "__main__":
    main()
