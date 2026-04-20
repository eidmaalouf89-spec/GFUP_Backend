"""
JANSA VISASIST — Desktop application launcher
PyWebView + React, single-user, single-project
"""
import sys
import os
import json
import math
import threading
import subprocess
import sqlite3
import webbrowser
from pathlib import Path

import webview

# ── Path resolution ──────────────────────────────────────────
def _resolve_base_dir():
    """Resolve base directory. Handles both dev mode and PyInstaller frozen."""
    if getattr(sys, 'frozen', False):
        # PyInstaller: exe is in dist/, data is alongside it
        return Path(sys.executable).parent
    return Path(__file__).parent

BASE_DIR = _resolve_base_dir()
DATA_DIR = BASE_DIR / "data"
RUN_MEMORY_DB = str(DATA_DIR / "run_memory.db")
REPORT_MEMORY_DB = str(DATA_DIR / "report_memory.db")
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
RUNS_DIR = BASE_DIR / "runs"

# ── Add src/ to path so existing modules can find each other ──
sys.path.insert(0, str(BASE_DIR / "src"))

# ── UI resolution ────────────────────────────────────────────
def _resolve_ui():
    """Returns URL for PyWebView to load."""
    # Dev mode: check for Vite dev server
    if "--dev" in sys.argv:
        return "http://localhost:5173"
    # Production: load built files
    dist = BASE_DIR / "ui" / "dist" / "index.html"
    if dist.exists():
        return str(dist)
    # Fallback: try frozen bundle
    if getattr(sys, 'frozen', False):
        frozen_dist = Path(sys._MEIPASS) / "ui" / "dist" / "index.html"
        if frozen_dist.exists():
            return str(frozen_dist)
    raise FileNotFoundError(
        "UI not found. Run 'cd ui && npm run build' or use '--dev' flag."
    )


def _ui_target_for_browser(ui_url: str) -> str:
    """Return a browser-openable target for local dist files or dev URLs."""
    if ui_url.startswith("http://") or ui_url.startswith("https://"):
        return ui_url
    return Path(ui_url).resolve().as_uri()

# ── Database helpers ─────────────────────────────────────────
def _query_db(db_path, sql, params=()):
    """Execute a read query and return results as list of dicts."""
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# ── JSON sanitizer for PyWebView bridge ──────────────────────
def _sanitize_for_json(obj):
    """
    Recursively replace NaN, Infinity, -Infinity with None
    so the result is valid JSON for PyWebView's JS bridge.
    Also converts pandas Timestamps and other non-serializable types.
    """
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    if isinstance(obj, (int, bool, str)):
        return obj
    # Handle pandas Timestamp, numpy types, etc.
    try:
        import pandas as pd
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat() if not pd.isna(obj) else None
        if pd.isna(obj):
            return None
    except Exception:
        pass
    try:
        # numpy int64, float64, etc.
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return None if np.isnan(obj) else float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
    except Exception:
        pass
    # Fallback: convert to string
    return str(obj)

# ── API class exposed to JavaScript ──────────────────────────
class Api:
    """
    Every public method here is callable from React via:
        window.pywebview.api.method_name(args)

    Returns are auto-serialized to JSON by PyWebView.
    """

    def __init__(self):
        self._pipeline_lock = threading.Lock()
        self._pipeline_status = {
            "running": False,
            "message": "",
            "error": None,
            "completed_run": None,
            "warnings": [],
        }

    def get_app_state(self):
        """Called by React on mount. Returns system state."""
        has_baseline = False
        current_run = None
        current_run_date = None
        total_runs = 0
        warnings = []

        if Path(RUN_MEMORY_DB).exists():
            runs = _query_db(RUN_MEMORY_DB,
                "SELECT run_number, status, is_stale, is_current, completed_at "
                "FROM runs ORDER BY run_number DESC")
            total_runs = len(runs)
            has_baseline = any(r["run_number"] == 0 for r in runs)

            # Find latest COMPLETED non-stale run
            for r in runs:
                if r["status"] == "COMPLETED" and not r["is_stale"]:
                    current_run = r["run_number"]
                    current_run_date = r["completed_at"]
                    break

            if not has_baseline:
                warnings.append("Run 0 baseline not found. Run bootstrap_run_zero.py first.")
        else:
            warnings.append("run_memory.db not found. Initialize the database first.")

        # Detect input files
        ged = None
        for f in INPUT_DIR.glob("*.xlsx"):
            if "GED" in f.name.upper() or "17CO" in f.name.upper():
                ged = str(f)
                break
        gf = None
        for f in INPUT_DIR.glob("*.xlsx"):
            if "grandfichier" in f.name.lower():
                gf = str(f)
                break

        return _sanitize_for_json({
            "has_baseline": has_baseline,
            "current_run": current_run,
            "current_run_date": current_run_date,
            "total_runs": total_runs,
            "ged_file_detected": ged,
            "gf_file_detected": gf,
            "data_dir": str(DATA_DIR),
            "pipeline_running": False,
            "app_version": "1.0.0",
            "warnings": warnings,
        })

    # ── Run explorer — delegate to existing service layer ──────

    def get_all_runs(self):
        """Delegate to src.run_explorer.get_all_runs."""
        try:
            from run_explorer import get_all_runs
            return _sanitize_for_json(get_all_runs(RUN_MEMORY_DB))
        except Exception as exc:
            return {"error": str(exc)}

    def get_run_summary(self, run_number):
        """Delegate to src.run_explorer.get_run_summary."""
        try:
            from run_explorer import get_run_summary
            return _sanitize_for_json(get_run_summary(RUN_MEMORY_DB, run_number))
        except Exception as exc:
            return {"error": str(exc)}

    def compare_runs(self, run_a, run_b):
        """Delegate to src.run_explorer.compare_runs."""
        try:
            from run_explorer import compare_runs
            return _sanitize_for_json(compare_runs(RUN_MEMORY_DB, run_a, run_b))
        except Exception as exc:
            return {"error": str(exc)}

    def export_run_bundle(self, run_number):
        """
        Export run artifacts as ZIP. Returns file path to the ZIP.
        Saves to output/exports/run_N_bundle.zip
        """
        try:
            export_dir = OUTPUT_DIR / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)
            zip_path = str(export_dir / f"run_{run_number}_bundle.zip")

            from run_explorer import export_run_bundle
            result_path = export_run_bundle(RUN_MEMORY_DB, run_number, zip_path)
            return _sanitize_for_json({"success": True, "path": result_path})
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ── Pipeline execution (background thread) ───────────────

    def run_pipeline_async(self, run_mode, ged_path=None, gf_path=None,
                           reports_dir=None):
        """
        Start pipeline in a background thread.
        Uses src.run_orchestrator.run_pipeline_controlled().
        Returns: {"started": True} or {"started": False, "errors": [...]}
        """
        with self._pipeline_lock:
            if self._pipeline_status["running"]:
                return _sanitize_for_json({"started": False, "errors": ["Pipeline is already running"]})

        # Use defaults from input/ if paths not provided
        if not ged_path:
            ged_path = self._detect_file("GED")
        if not gf_path:
            gf_path = self._detect_file("GF")

        # Pre-validate via orchestrator
        from run_orchestrator import validate_run_inputs
        validation = validate_run_inputs(run_mode, {
            "ged_path": ged_path,
            "gf_path": gf_path,
            "reports_dir": reports_dir,
        })
        if not validation["valid"]:
            return _sanitize_for_json({"started": False, "errors": validation["errors"],
                    "warnings": validation.get("warnings", [])})

        # Reset status and start worker thread
        with self._pipeline_lock:
            self._pipeline_status = {
                "running": True,
                "message": "Starting pipeline...",
                "error": None,
                "completed_run": None,
                "warnings": validation.get("warnings", []),
            }

        def worker():
            try:
                from run_orchestrator import run_pipeline_controlled
                self._update_status("Executing run_pipeline_controlled...")
                result = run_pipeline_controlled(
                    run_mode=run_mode,
                    ged_path=ged_path,
                    gf_path=gf_path,
                    reports_dir=reports_dir,
                )
                with self._pipeline_lock:
                    if result.get("success"):
                        # Invalidate reporting cache so dashboard reloads fresh data
                        try:
                            from reporting.data_loader import clear_cache
                            clear_cache()
                        except Exception:
                            pass
                        self._pipeline_status["completed_run"] = result.get("run_number")
                        self._pipeline_status["message"] = (
                            f"Run {result.get('run_number')} completed — "
                            f"{result.get('artifact_count', 0)} artifacts"
                        )
                        self._pipeline_status["warnings"] = result.get("warnings", [])
                    else:
                        self._pipeline_status["error"] = "; ".join(
                            result.get("errors", ["Unknown error"])
                        )
                        self._pipeline_status["message"] = "Pipeline failed"
            except Exception as exc:
                with self._pipeline_lock:
                    self._pipeline_status["error"] = f"{type(exc).__name__}: {exc}"
                    self._pipeline_status["message"] = "Pipeline failed with exception"
            finally:
                with self._pipeline_lock:
                    self._pipeline_status["running"] = False

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return _sanitize_for_json({"started": True, "warnings": validation.get("warnings", [])})

    def get_pipeline_status(self):
        """Polled by React every 500ms during execution."""
        with self._pipeline_lock:
            return _sanitize_for_json(dict(self._pipeline_status))

    def _update_status(self, msg):
        with self._pipeline_lock:
            self._pipeline_status["message"] = msg

    # ── Dashboard / reporting data ─────────────────────────────

    def get_dashboard_data(self, focus=False, stale_days=90):
        """Full dashboard payload: KPIs + monthly chart + consultant/contractor summaries."""
        try:
            from reporting.data_loader import load_run_context
            from reporting.aggregator import (
                compute_project_kpis,
                compute_monthly_timeseries,
                compute_weekly_timeseries,
                compute_consultant_summary,
                compute_contractor_summary,
            )
            from reporting.focus_filter import apply_focus_filter, FocusConfig

            ctx = load_run_context(BASE_DIR)
            focus_config = FocusConfig(enabled=bool(focus), stale_threshold_days=int(stale_days))
            focus_result = apply_focus_filter(ctx, focus_config)

            kpis = compute_project_kpis(ctx, focus_result=focus_result)
            consultants = compute_consultant_summary(ctx, focus_result=focus_result)
            contractors = compute_contractor_summary(ctx, focus_result=focus_result)

            if focus:
                timeseries = compute_weekly_timeseries(ctx, focus_result=focus_result)
            else:
                timeseries = compute_monthly_timeseries(ctx)

            payload = {
                "kpis": kpis,
                "monthly": timeseries,
                "consultants": consultants,
                "contractors": contractors,
                "focus": focus_result.stats,
            }
            if focus:
                payload["priority_queue"] = focus_result.priority_queue[:50]

            return _sanitize_for_json(payload)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return {"error": str(exc), "kpis": {}, "monthly": [], "consultants": [], "contractors": []}

    def get_consultant_list(self, focus=False, stale_days=90):
        """Consultant summary list for the Consultants page."""
        try:
            from reporting.data_loader import load_run_context
            from reporting.aggregator import compute_consultant_summary
            from reporting.focus_filter import apply_focus_filter, FocusConfig
            ctx = load_run_context(BASE_DIR)
            focus_config = FocusConfig(enabled=bool(focus), stale_threshold_days=int(stale_days))
            focus_result = apply_focus_filter(ctx, focus_config)
            return _sanitize_for_json(compute_consultant_summary(ctx, focus_result=focus_result))
        except Exception as exc:
            return {"error": str(exc)}

    def get_contractor_list(self, focus=False, stale_days=90):
        """Contractor summary list for the Contractors page."""
        try:
            from reporting.data_loader import load_run_context
            from reporting.aggregator import compute_contractor_summary
            from reporting.focus_filter import apply_focus_filter, FocusConfig
            ctx = load_run_context(BASE_DIR)
            focus_config = FocusConfig(enabled=bool(focus), stale_threshold_days=int(stale_days))
            focus_result = apply_focus_filter(ctx, focus_config)
            return _sanitize_for_json(compute_contractor_summary(ctx, focus_result=focus_result))
        except Exception as exc:
            return {"error": str(exc)}

    def get_consultant_fiche(self, consultant_name, focus=False, stale_days=90):
        """Full fiche data for one consultant."""
        import traceback
        try:
            from reporting.data_loader import load_run_context
            from reporting.consultant_fiche import build_consultant_fiche, resolve_consultant_name
            from reporting.focus_filter import apply_focus_filter, FocusConfig
            ctx = load_run_context(BASE_DIR)
            canonical = resolve_consultant_name(consultant_name)
            focus_config = FocusConfig(enabled=bool(focus), stale_threshold_days=int(stale_days))
            focus_result = apply_focus_filter(ctx, focus_config)
            result = build_consultant_fiche(ctx, canonical, focus_result=focus_result)
            return _sanitize_for_json(result)
        except Exception as exc:
            traceback.print_exc()
            return _sanitize_for_json({"error": str(exc), "consultant_name": consultant_name})

    def get_contractor_fiche(self, contractor_code, focus=False, stale_days=90):
        """Full fiche data for one contractor."""
        import traceback
        try:
            from reporting.data_loader import load_run_context
            from reporting.contractor_fiche import build_contractor_fiche
            from reporting.focus_filter import apply_focus_filter, FocusConfig
            ctx = load_run_context(BASE_DIR)
            focus_config = FocusConfig(enabled=bool(focus), stale_threshold_days=int(stale_days))
            focus_result = apply_focus_filter(ctx, focus_config)
            result = build_contractor_fiche(ctx, contractor_code, focus_result=focus_result)
            return _sanitize_for_json(result)
        except Exception as exc:
            traceback.print_exc()
            return _sanitize_for_json({"error": str(exc), "contractor_code": contractor_code})

    # ── Input validation (pre-flight check) ──────────────────

    def validate_inputs(self, run_mode, ged_path=None, gf_path=None,
                        reports_dir=None):
        """
        Pre-validates without running. Delegates to run_orchestrator.validate_run_inputs().
        Called by UI on mode/file change for inline validation.
        """
        from run_orchestrator import validate_run_inputs
        return _sanitize_for_json(validate_run_inputs(run_mode, {
            "ged_path": ged_path or self._detect_file("GED"),
            "gf_path": gf_path or self._detect_file("GF"),
            "reports_dir": reports_dir,
        }))

    # ── File selection (native OS dialog) ────────────────────

    def select_file(self, file_type):
        """
        Opens native file dialog. Returns selected path or None.
        file_type: "ged" | "gf" | "mapping" | "report_dir"
        """
        windows = webview.windows
        if not windows:
            return None
        win = windows[0]

        if file_type == "report_dir":
            result = win.create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=str(INPUT_DIR),
            )
            return result[0] if result else None
        else:
            result = win.create_file_dialog(
                webview.OPEN_DIALOG,
                directory=str(INPUT_DIR),
                file_types=("Excel files (*.xlsx)",),
            )
            return result[0] if result else None

    # ── Open file in Windows Explorer ────────────────────────

    def open_file_in_explorer(self, file_path):
        """Open the containing folder in Windows Explorer and select the file."""
        path = Path(file_path)
        if path.exists():
            subprocess.Popen(f'explorer /select,"{path}"')
            return _sanitize_for_json({"success": True})
        elif path.parent.exists():
            subprocess.Popen(f'explorer "{path.parent}"')
            return _sanitize_for_json({"success": True})
        return _sanitize_for_json({"success": False, "error": "Path not found"})

    # ── Helpers ──────────────────────────────────────────────

    def _detect_file(self, file_type):
        """Auto-detect input files from input/ directory."""
        if file_type == "GED":
            for f in INPUT_DIR.glob("*.xlsx"):
                if "GED" in f.name.upper() or "17CO" in f.name.upper():
                    return str(f)
        elif file_type == "GF":
            for f in INPUT_DIR.glob("*.xlsx"):
                if "grandfichier" in f.name.lower():
                    return str(f)
        return None

# ── Main ─────────────────────────────────────────────────────
def main():
    api = Api()
    ui_url = _resolve_ui()
    browser_mode = "--browser" in sys.argv

    if browser_mode:
        target = _ui_target_for_browser(ui_url)
        print(f"[app] Opening browser mode: {target}")
        webbrowser.open(target)
        return

    webview.create_window(
        title="JANSA VISASIST \u2014 P17&CO T2",
        url=ui_url,
        js_api=api,
        width=1400,
        height=900,
        min_size=(1024, 700),
        text_select=False,
    )

    try:
        webview.start(
            debug="--debug" in sys.argv,
        )
    except Exception as exc:
        target = _ui_target_for_browser(ui_url)
        print(f"[app] Embedded WebView startup failed: {exc}")
        print(f"[app] Falling back to browser mode: {target}")
        webbrowser.open(target)
        return


if __name__ == "__main__":
    main()
