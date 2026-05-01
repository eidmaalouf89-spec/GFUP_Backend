# 10 — Validation Commands

> Concrete commands to inspect, smoke-test, and validate this repo.
> All paths are relative to the repo root.

---

## A. Parse / compile checks (zero side-effects)

```bash
# Syntax-check the entrypoints and orchestrator without running anything.
python -m py_compile app.py main.py run_chain_onion.py
python -m py_compile src/run_orchestrator.py src/pipeline/runner.py
python -m py_compile $(git ls-files 'src/**/*.py')   # all of src/
```

A successful py_compile only proves the file parses; it does not import
or execute. Combine with import smoke tests below if you need more.

---

## B. Import smoke tests (cheap)

```bash
# Import the orchestrator without running anything.
python - <<'PY'
import sys
sys.path.insert(0, "src")
from run_orchestrator import validate_run_inputs, run_pipeline_controlled  # noqa
print("orchestrator import OK")
PY

# Import the UI adapter and reporting layer.
python - <<'PY'
import sys
sys.path.insert(0, "src")
from reporting.ui_adapter import adapt_overview, adapt_consultants, adapt_contractors_list, adapt_contractors_lookup  # noqa
from reporting.aggregator import (
    compute_project_kpis, compute_monthly_timeseries, compute_weekly_timeseries,
    compute_consultant_summary, compute_contractor_summary,
)  # noqa
print("reporting import OK")
PY

# Import chain_onion.
python - <<'PY'
import sys
sys.path.insert(0, "src")
from chain_onion.source_loader import load_chain_sources  # noqa
from chain_onion.query_hooks import QueryContext, get_top_issues  # noqa
print("chain_onion import OK")
PY
```

---

## C. UI startup smoke test (no pipeline run)

```bash
# Launch the embedded webview UI.
python app.py
# OR (recommended for dev — opens in default browser, no PyWebView dep):
python app.py --browser
# Look for: window opens, "JANSA · VisaSist — P17&CO" title, page renders.
# If chain_onion is missing it will still render — Focus stats just degrade.
```

Visual checks:
- Sidebar shows project pill "P17&CO Tranche 2 · Run #N" (where N is
  the latest completed run number).
- Overview KPIs render (totals can be 0 if no data).
- Click `Runs` — list of runs renders.
- Click `Executer` — file pickers show detected GED/GF from `input/`.

Console (browser dev tools or pywebview --debug):
- No `pywebview API not available` after 5 s (means bridge connected).
- No backend exceptions printed by the embedded console.

---

## D. Pipeline rerun (only when authorized)

```bash
# Default mode (uses input/GED_export.xlsx, inherited GF if missing).
python main.py

# Force raw fallback (skips Flat GED build):
GFUP_FORCE_RAW=1 python main.py

# Validate after run:
python - <<'PY'
import sqlite3
c = sqlite3.connect("data/run_memory.db")
print("LATEST RUNS:")
for r in c.execute(
    "SELECT run_number, status, is_current, is_stale, completed_at "
    "FROM runs ORDER BY run_number DESC LIMIT 5"
).fetchall():
    print(" ", r)
print("ARTIFACTS for latest:")
last = c.execute("SELECT MAX(run_number) FROM runs").fetchone()[0]
for r in c.execute(
    "SELECT artifact_type, file_path FROM run_artifacts WHERE run_number=? "
    "ORDER BY artifact_type", (last,)
).fetchall():
    print(" ", r)
PY
```

Expect: `status=COMPLETED`, `is_current=1`, ~33 artifacts for FULL mode.

---

## E. Chain + Onion rerun (independent of pipeline)

```bash
python run_chain_onion.py
# Expect verdict line:
#   "Chain + Onion pipeline complete — PASS"

# Inspect outputs:
ls -la output/chain_onion/
# Should include: CHAIN_*.csv (5), ONION_*.csv (2), CHAIN_NARRATIVES.csv,
# CHAIN_ONION_SUMMARY.xlsx, dashboard_summary.json, top_issues.json.

# Validate just the harness (without rebuilding):
python - <<'PY'
import sys
sys.path.insert(0, "src")
from chain_onion.validation_harness import run_chain_onion_validation
report = run_chain_onion_validation(output_dir="output/chain_onion")
print("status:", report["status"])
print("passed:", report["passed_checks"], "warned:", report["warning_checks"], "failed:", report["failed_checks"])
PY
```

---

## F. Repo health check script

```bash
python scripts/repo_health_check.py
# Prints a pass/fail line per check. Reads run_memory.db and the on-disk
# inventory; safe to run anytime.
```

Other scripts under `scripts/` (read each before running — these mutate state):
- `bootstrap_run_zero.py` — initialise run 0 from scratch.
- `bootstrap_report_memory.py` — initialise report_memory.db.
- `nuke_and_rebuild_run0.py` — destructive reset.
- `reset_to_clean_run0.py` — same family of destructive ops.

---

## G. Useful greps for inspection

```bash
# Where is BENTIN handled?
grep -nE 'BENTIN' -r src/ | grep -v __pycache__

# Where is LGD/LOT 03 handled?
grep -nE '(LGD|LOT 03|LOT 03-GOE)' -r src/

# Find all UI ↔ backend method bindings.
grep -nE 'pywebview\.api\.|jansaBridge\.api\.' -r ui/

# What does the data bridge populate?
grep -nE 'window\.(OVERVIEW|CONSULTANTS|CONTRACTORS|FICHE_DATA)' -r ui/

# All registered artifact types (read-only on db).
python - <<'PY'
import sqlite3
c = sqlite3.connect("data/run_memory.db")
for r in c.execute(
    "SELECT DISTINCT artifact_type FROM run_artifacts ORDER BY artifact_type"
).fetchall():
    print(r[0])
PY

# All exception list canonicals.
grep -nA1 'EXCEPTION_COLUMNS' src/flat_ged/input/source_main/consultant_mapping.py

# What stage produces what artifact (loose proxy).
grep -nE 'OUTPUT_[A-Z_]+ ' src/pipeline/paths.py
```

---

## H. Pytest suite (if test changes touch testable areas)

```bash
# Tests live under tests/ and tests/flat_ged/.
python -m pytest tests/ -x --tb=short

# Single file:
python -m pytest tests/test_chain_onion_loader.py -x -v

# Most tests assume the repo working dir; do NOT run from elsewhere.
```

---

## I. Sanity checks for "did Claude break something"

Before claiming a task is done:

```bash
# 1. App still parses.
python -m py_compile app.py main.py

# 2. UI loads in browser mode.
timeout 10 python app.py --browser   # process should not crash within 10s

# 3. Bridge contract intact (window globals still expected).
grep -E 'window\.(OVERVIEW|CONSULTANTS|CONTRACTORS|FICHE_DATA)\s*=' ui/jansa/data_bridge.js

# 4. No orphan imports introduced.
python - <<'PY'
import ast, sys, pathlib
roots = ["src", "scripts", "."]
fails = []
for r in roots:
    for p in pathlib.Path(r).rglob("*.py"):
        if "__pycache__" in p.parts or ".pytest_cache" in p.parts: continue
        try:
            ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            fails.append((str(p), e.msg, e.lineno))
print("syntax errors:", len(fails))
for f in fails: print("  ", f)
PY
```

These are read-only checks — they cannot mutate state.

---

## J. Cleanups that need explicit authorization (do NOT run casually)

```bash
# Wipe parity / step9 / temp leftovers from output/.
# DO NOT RUN without an explicit cleanup task.
# rm -rf output/parity output/parity_raw_r1 output/parity_raw_run1 output/parity_raw_run2
# rm -rf output/step9
# rm output/parity_report.xlsx output/ui_parity_report.xlsx output/clean_gf_diff_report.xlsx
# rm output/tmp63o7zaid.xlsx tmpxkmaioec.db tmpyw_386pd.db
# rm run_a.log run_b.log run_c.log run_d.log run_e.log run_f.log
# rm step15_debug.log pipeline_run.log fix_gf_schema_main.log
# rm test1_main_no_baseline.log test2_*.log test_write_permission.tmp
```

---

## L. Count Lineage Audit (Phase 8, last touched 2026-04-30 step 2)

```bash
# Compile + run the harness (read-only, writes only to output/debug/).
python -m py_compile scripts/audit_counts_lineage.py
python scripts/audit_counts_lineage.py
# Optional: pick a different run.
python scripts/audit_counts_lineage.py --run 0

# Probe mode (Phase 8 step 2): emits provenance for every (category, layer).
python scripts/audit_counts_lineage.py --probe

# Companion tests.
python -m pytest tests/test_audit_counts_lineage.py -q
```

Expected stdout one-liner shape (default audit run):
```
AUDIT: PASS=<n> WARN=<n> FAIL=<n>; first_unexpected_divergence=<category>@<layer>
```

Outputs:
- `output/debug/counts_lineage_audit.xlsx` (sheets: `lineage`,
  `expected_baselines`, `divergences_unexpected`). The
  `expected_baselines.raw_submission_rows.provenance` field carries the source
  file + mtime + sheet + row range used for the baseline (refreshed step 2).
- `output/debug/counts_lineage_audit.json` (machine-readable; shape in
  `docs/implementation/PHASE_8_COUNT_LINEAGE_FIX.md` §5.3 step 11).
- `output/debug/counts_lineage_probe.xlsx` and `.json` (only when `--probe`
  is passed). One row per (category, layer) with `value_origin_type`,
  `source_file`, `source_sheet`, `source_column`, `source_filter`,
  `function_or_code_path`, `is_hardcoded_baseline`, `confidence`.

Known surviving FAILs after step 2 (per `07_OPEN_ITEMS.md`):
- `workflow_step_count` and `sas_row_count` flagged at L2_STAGE_READ_FLAT —
  resolved by extending the SAS-filter divergence rule (step 2.5, D-1).
- `status_SAS_REF` at L1 (RAW=836 → FLAT=284) is a real upstream projection
  gap (D-011) and not in scope for Phase 8.

This script DOES NOT modify any pipeline output, registry, or production
source. Safe to run anytime.

---

## M. Phase 8A downstream audits (last touched 2026-05-01)

```bash
# 8A.1 — D-010 focus/visa source audit (read-only AST walk).
python -m py_compile scripts/audit_focus_visa_source.py
python scripts/audit_focus_visa_source.py
# Expected stdout:
#   FOCUS_VISA_AUDIT: call_sites=<n> direct_engine=<n> via_resolver=<n> disagreements_total=<n>
# Last result (2026-05-01): call_sites=10 direct_engine=8 via_resolver=2 disagreements_total=0
# Outputs:
#   output/debug/focus_visa_source_audit.json
#   output/debug/focus_visa_source_audit.xlsx

# 8A.3 — Chain+Onion BLOCK-mode readiness audit (read-only DB + JSON inspection).
python -m py_compile scripts/check_chain_onion_alignment_block_ready.py
python scripts/check_chain_onion_alignment_block_ready.py
# Expected stdout:
#   BLOCK_READINESS: ready=<true|false> reason=<...>
# Last result (2026-05-01): ready=false (latest pipeline run predates WARN
# helper). Re-run after a fresh `python main.py` to clear the gate.
# Output:
#   output/debug/chain_onion_block_readiness.json

# 8A.6 — Widened UI payload audit (read-only; compares aggregator/builder vs
# adapter outputs across 6 UI surfaces).
python -m py_compile scripts/audit_ui_payload_full_surface.py
python scripts/audit_ui_payload_full_surface.py
# Expected stdout one-liner:
#   UI_PAYLOAD_FULL: surfaces=<n> compared=<n> matches=<n> mismatches=<n>; OK - all compared fields match
# Last result (2026-05-01): surfaces=6 compared=45 matches=45 mismatches=0
# Outputs:
#   output/debug/ui_payload_full_surface_audit.json
#   output/debug/ui_payload_full_surface_audit.xlsx
```

All three scripts are read-only. They do NOT modify pipeline output, registry,
or production source. Safe to run anytime.

---

## N. Phase 8B RAW → FLAT GED reconciliation (closed 2026-05-01)

```bash
# Phase 8B reconciliation harness (read-only). Produces the 11-sheet
# raw_flat_reconcile.xlsx workbook plus per-row trace files.
python -m py_compile scripts/raw_flat_reconcile.py
python scripts/raw_flat_reconcile.py
# Outputs (all under output/debug/, NOT registered in run_memory.db):
#   raw_flat_reconcile.xlsx           (11 sheets, ~695 KB)
#   flat_ged_trace.{csv,xlsx}         (per-row FLAT projection classification)
#   raw_ged_trace.csv                 (per-row RAW GED trace)
#   report_to_flat_trace.{json,xlsx}  (report-integration trace)
#   SHADOW_FLAT_GED_OPERATIONS.csv    (shadow-corrected operational layer)
#   SHADOW_FLAT_GED_TRACE.xlsx        (shadow-FLAT per-row trace)
#   PHASE_8B_FINAL_REPORT.md          (final report + §17 decision gate)
```

Phase 8B closure outcome (Outcome C): identity contract PASS, SAS REF gap
99.3% explained, 6 SAS REF rows remain UNEXPLAINED (28xxx /A C1 cluster).
The script never modifies production FLAT_GED.xlsx. See
`docs/RAW_TO_FLAT_GED_KNOWLEDGE.md` and `output/debug/PHASE_8B_FINAL_REPORT.md`
for the canonical reference.

---

## K. Diff/audit a candidate change

```bash
# What did Claude actually change?
git status
git diff --stat
git diff -- src/                   # source diff
git diff -- ui/                    # UI diff
git diff -- context/               # context updates

# Did Claude touch the do-not-touch list?
git diff --name-only | grep -E '(src/flat_ged/|src/run_memory\.py|src/report_memory\.py|src/team_version_builder\.py|app\.py|main\.py|ui/jansa-connected\.html|ui/jansa/)'

# Are run/data dbs intact?
git status data/ runs/             # SHOULD be empty (or only context/, output/ adds)
```
