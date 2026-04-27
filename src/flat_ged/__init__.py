"""
src/flat_ged/__init__.py — Frozen snapshot of ged_flat_builder.

DO NOT edit business rules in this package. See BUILD_SOURCE.md.
All business logic lives in the upstream builder repo.
Adapter changes go in src/pipeline/stages/stage_read_flat.py, never here.

Public API
----------
build_flat_ged(ged_xlsx_path, output_dir, *, mode, numero, indice) -> dict
    Runs the flat GED builder and returns the run_report dict.
    Side effect: writes FLAT_GED.xlsx (unless skipped) and run_report.json
    to output_dir.
"""

import sys
import json
import types
from pathlib import Path

# Package directory — added to sys.path only during build, then cleaned up.
_pkg_dir = Path(__file__).parent

# Module names that live in src/flat_ged/ and use bare imports.
# These are tracked so we can remove them from sys.modules after the build
# to prevent shadowing identically-named modules in src/ (e.g. writer.py).
_FLAT_GED_BARE_MODULES = frozenset({
    "config", "reader", "resolver", "transformer", "processor",
    "validator", "writer", "utils",
})


def build_flat_ged(
    ged_xlsx_path: Path,
    output_dir: Path,
    *,
    mode: str = "batch",
    numero: int | None = None,
    indice: str | None = None,
) -> dict:
    """Run the flat GED builder and return the run_report dict.

    Side effect: writes FLAT_GED.xlsx + run_report.json into output_dir.
    In batch mode also writes DEBUG_TRACE.csv.

    Parameters
    ----------
    ged_xlsx_path : Path
        Path to the GED_export.xlsx input file.
    output_dir : Path
        Directory where output files are written (created if absent).
    mode : str
        "batch" (default) — processes all documents, fast streaming path.
        "single" — processes one document (requires numero + indice).
    numero : int | None
        [single mode] Document NUMERO.
    indice : str | None
        [single mode] Document INDICE (e.g. "A", "B").

    Returns
    -------
    dict
        Contents of run_report.json written by the builder.
    """
    # ── Snapshot sys.path and sys.modules before builder imports ──
    _need_path = str(_pkg_dir) not in sys.path
    _modules_before = set(sys.modules.keys())

    if _need_path:
        sys.path.insert(0, str(_pkg_dir))

    try:
        # Lazy import so sys.path insertion above is in effect.
        from . import cli as _cli  # noqa: F401

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        args = types.SimpleNamespace(
            input=Path(ged_xlsx_path),
            skip_xlsx=False,
            numero=numero,
            indice=indice,
            row_index=None,
        )

        if mode == "batch":
            _cli.run_batch(args, output_dir)
        elif mode == "single":
            _cli.run_single(args, output_dir)
        else:
            raise ValueError(f"mode must be 'batch' or 'single', got {mode!r}")

        report_path = output_dir / "run_report.json"
        with open(report_path, encoding="utf-8") as fh:
            return json.load(fh)

    finally:
        # ── Clean up: remove flat_ged package dir from sys.path ──
        if _need_path and str(_pkg_dir) in sys.path:
            sys.path.remove(str(_pkg_dir))

        # ── Clean up: remove bare-imported flat_ged modules from sys.modules
        # so they don't shadow identically-named modules in src/ (e.g. writer).
        for mod_name in _FLAT_GED_BARE_MODULES:
            if mod_name in sys.modules and mod_name not in _modules_before:
                del sys.modules[mod_name]
