"""
run_chain_onion.py
------------------
Standalone runner for the Chain + Onion analytical pipeline (Steps 04-14).

Reads from:
  output/intermediate/FLAT_GED.xlsx
  output/intermediate/DEBUG_TRACE.csv
  data/report_memory.db

Writes to:
  output/chain_onion/   (7 CSVs + XLSX + 2 JSON)

Usage:
  python run_chain_onion.py
"""
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
_LOG = logging.getLogger("chain_onion_runner")

# ── Path setup ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR   = REPO_ROOT / "src"
for _p in (REPO_ROOT, SRC_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

FLAT_GED_PATH    = REPO_ROOT / "output" / "intermediate" / "FLAT_GED.xlsx"
DEBUG_TRACE_PATH = REPO_ROOT / "output" / "intermediate" / "DEBUG_TRACE.csv"
REPORT_MEMORY_DB = REPO_ROOT / "data" / "report_memory.db"
OUTPUT_DIR       = REPO_ROOT / "output" / "chain_onion"


def _step(name):
    _LOG.info("── %s", name)
    return time.time()

def _done(t0):
    _LOG.info("   done in %.1fs", time.time() - t0)


def run():
    total_t0 = time.time()

    # ── Pre-flight ──────────────────────────────────────────────────────────
    missing = [p for p in (FLAT_GED_PATH, DEBUG_TRACE_PATH) if not p.exists()]
    if missing:
        _LOG.error("Missing required inputs: %s", missing)
        _LOG.error("Run the main pipeline first (python main.py or via the Executer page).")
        sys.exit(1)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 04 — Source Loader ─────────────────────────────────────────────
    t0 = _step("Step 04 — Source Loader")
    from chain_onion.source_loader import load_chain_sources
    sources = load_chain_sources(
        flat_ged_path=FLAT_GED_PATH,
        debug_trace_path=DEBUG_TRACE_PATH,
        report_memory_db_path=REPORT_MEMORY_DB if REPORT_MEMORY_DB.exists() else None,
        output_dir=OUTPUT_DIR,
    )
    ops_df       = sources["ops_df"]
    debug_df     = sources["debug_df"]
    effective_df = sources["effective_df"]
    _LOG.info("   ops_df: %d rows  debug_df: %d rows  effective_df: %d rows",
              len(ops_df), len(debug_df), len(effective_df))
    _done(t0)

    # ── Step 05 — Family Grouper ────────────────────────────────────────────
    t0 = _step("Step 05 — Family Grouper")
    from chain_onion.family_grouper import build_chain_versions, build_chain_register
    chain_versions_df = build_chain_versions(ops_df)
    chain_register_df = build_chain_register(ops_df, chain_versions_df, debug_df, effective_df)
    _LOG.info("   chain_register: %d families  chain_versions: %d rows",
              len(chain_register_df), len(chain_versions_df))
    _done(t0)

    # ── Step 06 — Chain Builder (Timeline Events) ───────────────────────────
    t0 = _step("Step 06 — Chain Builder")
    from chain_onion.chain_builder import build_chain_events
    chain_events_df = build_chain_events(ops_df, debug_df, effective_df)
    _LOG.info("   chain_events: %d rows", len(chain_events_df))
    _done(t0)

    # ── Step 07 — Chain Classifier ──────────────────────────────────────────
    t0 = _step("Step 07 — Chain Classifier")
    from chain_onion.chain_classifier import classify_chains
    chain_register_df = classify_chains(
        chain_register_df, chain_versions_df, chain_events_df, ops_df
    )
    buckets = chain_register_df["portfolio_bucket"].value_counts().to_dict() if "portfolio_bucket" in chain_register_df.columns else {}
    _LOG.info("   buckets: %s", buckets)
    _done(t0)

    # ── Step 08 — Chain Metrics ─────────────────────────────────────────────
    t0 = _step("Step 08 — Chain Metrics")
    from chain_onion.chain_metrics import build_chain_metrics
    chain_metrics_df, portfolio_metrics = build_chain_metrics(
        chain_register_df, chain_versions_df, chain_events_df, ops_df
    )
    _LOG.info("   chain_metrics: %d rows  portfolio_metrics keys: %d",
              len(chain_metrics_df), len(portfolio_metrics))
    _done(t0)

    # ── Step 09 — Onion Layer Engine ────────────────────────────────────────
    t0 = _step("Step 09 — Onion Layer Engine")
    from chain_onion.onion_engine import build_onion_layers
    onion_layers_df = build_onion_layers(chain_register_df, chain_events_df, chain_metrics_df)
    _LOG.info("   onion_layers: %d rows", len(onion_layers_df))
    _done(t0)

    # ── Step 10 — Onion Scoring ─────────────────────────────────────────────
    t0 = _step("Step 10 — Onion Scoring")
    from chain_onion.onion_scoring import build_onion_scores
    onion_scores_df, onion_portfolio_summary = build_onion_scores(
        onion_layers_df, chain_metrics_df, chain_register_df
    )
    _LOG.info("   onion_scores: %d rows  portfolio_summary keys: %d",
              len(onion_scores_df), len(onion_portfolio_summary))
    _done(t0)

    # ── Step 11 — Narrative Engine ──────────────────────────────────────────
    t0 = _step("Step 11 — Narrative Engine")
    from chain_onion.narrative_engine import build_chain_narratives
    chain_narratives_df = build_chain_narratives(
        chain_register_df, chain_metrics_df, onion_layers_df, onion_scores_df
    )
    _LOG.info("   chain_narratives: %d rows", len(chain_narratives_df))
    _done(t0)

    # ── Step 12 — Export ────────────────────────────────────────────────────
    t0 = _step("Step 12 — Export Engine")
    from chain_onion.exporter import export_chain_onion_outputs
    artifacts = export_chain_onion_outputs(
        chain_register_df=chain_register_df,
        chain_versions_df=chain_versions_df,
        chain_events_df=chain_events_df,
        chain_metrics_df=chain_metrics_df,
        onion_layers_df=onion_layers_df,
        onion_scores_df=onion_scores_df,
        chain_narratives_df=chain_narratives_df,
        portfolio_metrics=portfolio_metrics,
        onion_portfolio_summary=onion_portfolio_summary,
        output_dir=str(OUTPUT_DIR),
        issue_meta_df=ops_df,
    )
    for name, path in artifacts.items():
        _LOG.info("   → %s", path)
    _done(t0)

    # ── Step 14 — Validation Harness ────────────────────────────────────────
    t0 = _step("Step 14 — Validation Harness")
    from chain_onion.validation_harness import run_chain_onion_validation
    try:
        report = run_chain_onion_validation(
            output_dir=str(OUTPUT_DIR),
            chain_register_df=chain_register_df,
            chain_versions_df=chain_versions_df,
            chain_events_df=chain_events_df,
            chain_metrics_df=chain_metrics_df,
            onion_layers_df=onion_layers_df,
            onion_scores_df=onion_scores_df,
            chain_narratives_df=chain_narratives_df,
        )
    except UnicodeEncodeError:
        # Windows cp1252 terminal can't print unicode check marks — re-run with PYTHONUTF8=1
        _LOG.warning("   Harness print crashed (cp1252 encoding). Re-running silently...")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            report = run_chain_onion_validation(
                output_dir=str(OUTPUT_DIR),
                chain_register_df=chain_register_df,
                chain_versions_df=chain_versions_df,
                chain_events_df=chain_events_df,
                chain_metrics_df=chain_metrics_df,
                onion_layers_df=onion_layers_df,
                onion_scores_df=onion_scores_df,
                chain_narratives_df=chain_narratives_df,
            )
    passed   = report.get("passed_checks", 0)
    warnings = report.get("warning_checks", 0)
    failed   = report.get("failed_checks", 0)
    _LOG.info("   Validation: %d passed  %d warnings  %d failed", passed, warnings, failed)
    if report.get("critical_failures"):
        for f in report["critical_failures"]:
            _LOG.error("   CRITICAL: %s", f)
    for w in report.get("warnings_detail", []):
        _LOG.warning("   WARN: %s", w)
    _done(t0)

    verdict = "PASS" if failed == 0 else "FAIL"
    _LOG.info("")
    _LOG.info("═══════════════════════════════════════════")
    _LOG.info("  Chain + Onion pipeline complete — %s", verdict)
    _LOG.info("  Total time: %.1fs", time.time() - total_t0)
    _LOG.info("  Output dir: %s", OUTPUT_DIR)
    _LOG.info("═══════════════════════════════════════════")

    return verdict == "PASS"


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
