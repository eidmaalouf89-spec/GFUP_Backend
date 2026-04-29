# 07 — Open Items

> Things observed in the actual code/data that look unfinished, weakly
> connected, or likely to bite future work. Not a wishlist — a punch list.

---

## High-value, low-risk items (highest ROI for next fixes)

### 1. UI Contractors page is a stub but backend is fully wired

`ui/jansa/shell.jsx:653` renders `<StubPage title="Entreprises">`. The
backend already provides:

- `app.Api.get_contractor_list(focus, stale_days)`
- `app.Api.get_contractor_fiche(contractor_code, focus, stale_days)`
- `app.Api.get_contractors_for_ui(focus, stale_days)` shaped through
  `reporting.ui_adapter.adapt_contractors_list / adapt_contractors_lookup`
- `data_bridge.js` already populates `window.CONTRACTORS_LIST` and
  `window.CONTRACTORS`.

A `<ContractorsPage>` component and a `<ContractorFichePage>` would unlock
this without any backend work.

### 2. Mapping file picker on Executer is dead

`ui/jansa/executer.jsx:277` self-labels the Mapping field as
`"informatif — non transmis au backend"`, and `app.Api.run_pipeline_async`
does not accept or forward a mapping path. Either remove the field or wire
it through `run_pipeline_controlled` (and follow the chain to
`normalize.load_mapping` to confirm what file it would consume).

### 3. Discrepancies / Settings pages are stubs

The pipeline writes `DISCREPANCY_REPORT.xlsx`,
`DISCREPANCY_REVIEW_REQUIRED.xlsx`, `RECONCILIATION_LOG.xlsx`, and
`IGNORED_ITEMS_LOG.xlsx` every run. None are surfaced. A read-only
"Discrepancies — review queue" page over `DISCREPANCY_REVIEW_REQUIRED.xlsx`
is purely additive.

### 4. Chain + Onion narratives + top issues not in UI

`output/chain_onion/top_issues.json`, `CHAIN_NARRATIVES.csv`, and
`dashboard_summary.json` are produced by `run_chain_onion.py` but no UI
screen renders them. Backend has `chain_onion.query_hooks.get_top_issues`,
`get_dashboard_summary`, etc. ready.

---

## Architectural / connection gaps

### 5. Two registries, one decoupling

`output/chain_onion/*` is produced by `run_chain_onion.py` reading
`output/intermediate/FLAT_GED.xlsx` directly. It is **not** keyed by
`run_number` — if you regenerate intermediate without rerunning Chain+Onion,
your live UI Focus stats use stale chain data. Suggest either:
- have `stage_finalize_run` invoke chain_onion automatically, or
- register chain_onion outputs as artifacts in `run_memory.db` per run.

### 6. `paths.py` `FLAT_GED_MODE = "raw"` default is misleading

Anyone calling `pipeline.runner._run_pipeline_impl` without going through
the orchestrator will silently take the raw fallback path. The default
should match runtime behavior, OR the orchestrator should be the only
documented entrypoint. Decision needed.

### 7. `data_loader` legacy raw GED rebuild path

`data_loader.py` has a legacy raw GED rebuild fallback that fires when
`FLAT_GED` artifact is missing, logging `[LEGACY_RAW_FALLBACK]`. README
calls this "legacy fallback only" but the path is still in code. Verify
nothing real depends on it before retiring.

### 8. Two consultant mapping sources

`src/flat_ged/input/source_main/consultant_mapping.py:CANONICAL_TO_DISPLAY`
and `src/reporting/consultant_fiche.py:CONSULTANT_DISPLAY_NAMES` carry the
same map. They agree today. Pick one as authoritative and have the other
import it.

### 9. `team_version_builder.py` hardcoded paths

`team_version_builder.py` lines 13–17 hardcode:
```
OGF_PATH   = "input/Grandfichier_v3.xlsx"
CLEAN_PATH = "output/GF_V0_CLEAN.xlsx"
OUT_PATH   = "output/GF_TEAM_VERSION.xlsx"
```

Even though `paths.py` defines all three. Today this happens to be
consistent, but if a stage redirects (e.g. `_patched_main_context`) the
team builder won't follow. The stage already wraps it; verify the wrap
overrides via signature, not module globals.

### 10. Repo-root debug logs are uncontrolled

`run_a.log` … `run_f.log`, `step15_debug.log`, `pipeline_run.log`,
`fix_gf_schema_main.log`, `test1_main_no_baseline.log`, `test2_*.log`,
`run_e.log` (empty), all live at repo root. They look one-off but no
.gitignore rule nets them. Consider moving `*.log` outside the working
tree or adding to `.gitignore`.

---

## Probable bugs / smells (to be confirmed before action)

### 11. `_resolve_inherited_gf_record` walks a base computed from `data/`

```python
base_dir = Path(db_path).resolve().parent.parent  # data/run_memory.db → root
```

If `data/run_memory.db` is moved (e.g. to `data/sub/run_memory.db`), this
walk to root breaks silently. Low risk today, but worth a hardening pass.

### 12. `app.Api._build_live_operational_numeros` swallows exceptions

```python
except Exception as exc:
    print(exc)
    return None, 0
```

In a degraded state (chain_onion missing), prints to stdout and continues
without surfacing in the UI. Acceptable today (UI has fallback) but
emitting through the warnings list of the dashboard payload would help.

### 13. `consultant_match_report.xlsx` ingestion priority

`stage_report_memory` ingests this file each run. The artifact is also
registered each run, which means run N+1 ingests the file produced by
run N. Looks correct, but verify the dedup gate
(`is_report_already_ingested`) doesn't skip a file that was newly enriched
by reading it from a slightly different path.

### 14. `output/parity*` and `output/step9/legacy/` are dormant

No code path writes there in the active runtime. Safe to archive once
confirmed via `grep -r parity_raw_run src/`. (Confirmed empty in current
code.)

### 15. `runs/run_0000/` is the ONLY registered run

`data/run_memory.db` shows one row: `(0, 'COMPLETED', is_current=1, is_stale=0)`.
No `run_0001/` exists yet. The UI's `total_runs=1` matches. After the next
production run we should see `run_0001/` and the artifact registry should
grow to ~33 × 2 entries.

### 18. `run_chain_onion.py` Step 14 D19 validation harness exits 1

Verified 2026-04-28 (Phase 3 of DCC project, see
`docs/implementation/03_PHASE_3_REPORT.md` OQ-1).

`python run_chain_onion.py` exits with code 1 because Step 14 Validation
Harness check D19 prints "CRITICAL: D19 skipped: severity column missing"
and `sys.exit(1)` is reached. **All 10 expected artifacts (CHAIN_REGISTER.csv,
CHAIN_EVENTS.csv, CHAIN_VERSIONS.csv, CHAIN_METRICS.csv, ONION_LAYERS.csv,
ONION_SCORES.csv, CHAIN_NARRATIVES.csv, CHAIN_ONION_SUMMARY.xlsx,
dashboard_summary.json, top_issues.json) ARE written correctly** — 71/73
checks pass.

**Workaround in app.py (Phase 3 patch):** `_run_chain_onion_subprocess`
treats "exit code ≠ 0 BUT all required CSVs present" as `partial success`
and continues. So the auto-refresh path works regardless of this bug.

**Real fix (when convenient):** investigate D19 in chain_onion (likely
a missing column in CHAIN_NARRATIVES or ONION_SCORES that the harness
expected). Then chain_onion will exit 0 cleanly and the partial-success
fallback in app.py becomes dead code that can be removed.

---

### 17. `chain_timeline_attribution` UNKNOWN attribution edge cases — ✅ RESOLVED (Phase 5 Mod 4)

**Resolved 2026-04-29.** All 47 rows classified and addressed via manual worksheet + 4 code fixes.

**Resolution summary:**
- 26 rows → `DEAD` (abandoned/obsolete versions, attributed_days=0): listed in `context/dead_version_overrides.csv`
- 12 rows → `CONTRACTOR` (SAS issued CYCLE_REQUIRED REF; delay = max(0, review_end−sas_ref_date−15) capped at review_delay)
- 2 rows → focus-fallback resolved (136000_C → GEMO, 245502_D → AVLS)
- 4 rows → `NO_ATTRIBUTION` (3 MOEX-not-called, 1 within-tolerance 4-day review): listed in `context/dead_version_overrides.csv`
- 1 row → unchanged UNKNOWN (028245_C, 10 days, no issue identified)

**Code changes:** `src/reporting/chain_timeline_attribution.py` (5 fixes) + `context/dead_version_overrides.csv` (new, 30 entries).

**Verified 2026-04-29:** `CHAIN_TIMELINE_ATTRIBUTION.csv` regenerated. UNKNOWN=`['028245_C']`, DEAD unique keys=26, NO_ATTRIBUTION rows=4. ✓

---

### 16. `delay_contribution_days` ignores the 10-day secondary cap

Verified 2026-04-28 (Phase 1 of DCC project, see
`docs/implementation/01_PHASE_1_REPORT.md`).

`src/flat_ged/transformer.py:compute_delay_contribution` assigns delay
based on a single `cm_deadline` shared by all consultants regardless of
PRIMARY / SECONDARY tier. The 10-day window
(`focus_ownership.SECONDARY_WINDOW_DAYS=10`) is enforced only for
current-state ownership, not for historical attribution.

Empirical impact (current run):
- 7,851 SECONDARY rows with `delay_contribution_days > 10` (max 813d).
- `chain_metrics.secondary_wait_days` is over-attributed to secondary
  consultants.
- `onion_engine.py` scoring inputs (lines 491, 579, 668) consume the
  uncapped values; onion scores for chains with stale secondaries are
  likely inflated.

Phase 2 of the DCC project applies the cap inside the new
`reporting/chain_timeline_attribution.py` (read-only, doesn't modify
chain_onion). A separate HIGH-risk task would be needed to fix this at
the Flat GED transformer source if onion scoring needs correction.

---

## Disconnected data (present, not yet used)

| Asset | Purpose if connected |
|---|---|
| `output/chain_onion/CHAIN_NARRATIVES.csv` | Per-chain plain-language summary; could populate a "Top issues" UI panel. |
| `output/chain_onion/top_issues.json` | Already a 20-row priority list; could replace or augment current `priority_queue` in OVERVIEW. |
| `output/chain_onion/CHAIN_ONION_SUMMARY.xlsx` | Management workbook; useful for steering meetings. |
| `output/chain_onion/dashboard_summary.json` | Portfolio KPIs; complements `aggregator.compute_project_kpis`. |
| `MISSING_IN_GED_TRUE_ONLY.xlsx` / `MISSING_IN_GF_TRUE_ONLY.xlsx` | Curated review queues. |
| `INSERT_LOG.xlsx` | "What changed in GF this run?" — could feed a "Latest run diff" page. |
| `NEW_SUBMITTAL_ANALYSIS.xlsx` | New documents per family — useful for contractor performance. |
| `SUSPICIOUS_ROWS_REPORT.xlsx` | Rows the heuristics flagged. |
| `RECONCILIATION_LOG.xlsx` | Patch F fuzzy match decisions. |
| `consultant_match_report.xlsx` | Matched consultant rows; used by report_memory ingestion but not by UI. |

Several of these would benefit from a "Reports" page that lists them and
opens them via `open_file_in_explorer(path)` (the API already exists).

---

## Highest ROI first three fixes (ranking, not prescription)

1. **Wire the Contractors page** (#1). Pure frontend; backend has all the
   data. Big visible win.
2. **Wire chain+onion priority into the UI** (#4). The data exists. A
   "Priority Queue" panel that exposes `top_issues.json` would convert
   the analytical layer into operational signal.
3. **Decide the FLAT_GED_MODE default** (#6). This is a one-line change
   that reduces a foot-gun every time a developer calls the pipeline
   directly.

---

## Phase 3 residual (discovered 2026-04-28)

### D19 — `severity` column missing in chain_onion validation harness

`run_chain_onion.py` Step 14 (Validation Harness) checks for a `severity`
column that is not present in the current chain_onion output schema. This
causes check D19 to be skipped and the harness to exit with code 1 even
when all 10 artifacts are written correctly (71/73 checks pass).

**Workaround in place:** `app._run_chain_onion_subprocess` now detects the
partial-success case: if `returncode != 0` but all 3 required CSV files
exist, it logs "exit 1 but artifacts present — partial success" and
continues to chain_timeline refresh. Startup behavior is correct.

**Root fix needed:** Add the `severity` column to the chain_onion export
(likely in `src/chain_onion/exporter.py`) so the D19 check passes and the
harness exits 0. Low urgency — workaround fully covers startup path.

---

## Things that look risky but are working — leave alone

- The `main_module` namespace mutation in `run_orchestrator._patched_main_context`
  (it's intentional and documented).
- The flat_ged sys.path / sys.modules cleanup in `flat_ged/__init__.py`
  (prevents shadowing of `writer` and `config`).
- The `cache_ready.wait()` pattern in `Api.get_*_for_ui` (waits for
  pre-warm thread).
- The Babel-from-CDN approach in `jansa-connected.html` (works in pyWebView,
  no compile step needed).
