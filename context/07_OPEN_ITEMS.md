# 07 — Open Items

> Things observed in the actual code/data that look unfinished, weakly
> connected, or likely to bite future work. Not a wishlist — a punch list.

---

## ⚠ ACTIVE — Phase 0 Backend Audit (opened 2026-04-29)

Phase 7 (contractor quality fiche) reached visual smoke and surfaced data
integrity issues across pipeline stages. Phase 7 is paused; Phase 0 is the
gate. Plan: `docs/implementation/PHASE_0_BACKEND_DEBUGGING.md`. README
section: "Phase 0 — Backend Data Audit (current, blocking)".

### Phase 0 status (Step 0.6 closed 2026-04-29)

| Step | Status | Deliverable |
|---|---|---|
| 0.1 Pipeline-stage inventory | ✅ done | `docs/audit/PIPELINE_INVENTORY.md` |
| 0.2 Canary contractor BEN | ✅ done | `docs/audit/CANARY_BEN.md` |
| 0.3 Verification scripts | ✅ done | `scripts/audit/_common.py` + 8 audit scripts |
| 0.4 Run audits | ✅ done | `docs/audit/DIVERGENCE_REPORT.md` (1,901 lines) |
| 0.5 Triage | ✅ done | `docs/audit/TRIAGE.md` (10 rows, 3 fix-now) |
| 0.6 Apply fix-now patches | ✅ done | D-001, D-004, D-005 landed and verified |
| 0.7 Update context docs | (in progress — this file) | |
| 0.8 Sign-off | pending | `docs/audit/SIGN_OFF.md` |

### Closed by Phase 0 (fix-now landed)

- **D-001 — `CACHE_SCHEMA_VERSION`** added to `data_loader.py`. Cache freshness now rejects schema-mismatched pickles. Production-confirmed pandas StringDtype unpickle drift (canary §13). See `context/11_TOOLING_HAZARDS.md` H-2.
- **D-004 — AMP 199% bug fixed.** `contractor_quality.py:486-498` now computes `share_contractor_in_long_chains` over closed-cycle attribution only. AMP 1.9945 → 0.9115. Zero contractors over 1.0 across all 29. `avg_contractor_delay_days` unchanged (dormant extension preserved). See `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B.2.
- **D-005 — `CHAIN_TIMELINE_ATTRIBUTION.json` truncation fixed.** `write_chain_timeline_artifact` now uses atomic write (tmp + `os.replace`). Artifact regenerated: 2,819 chains parse cleanly (was 2,687 via tolerant parse). 6 contractors no longer missing chains.

### Open (handed forward — out of Phase 0 scope)

| ID | Issue | Suspected location | Classification |
|---|---|---|---|
| **D-003** | SNI SAS REF count: raw GED ~184 vs flat_ged 52. Operator's count from raw was never directly audited (we read `FLAT_GED.xlsx::GED_OPERATIONS`, not the raw GED workbook). | raw → flat_ged extraction in `src/flat_ged/transformer.py` | **upstream rework** — open a separate ticket. Document the raw vs flat scope difference. |
| **D-006** | AAI shows B1=7 (`GED_OPERATIONS` SAS+REF) vs C3=6 (`ctx.responses_df` SAS-track REF). 1 SAS REF row lost between layers. | `stage_read_flat._apply_sas_filter_flat` (`stage_read_flat.py:202-274`) OR doc_id null filter (`stage_read_flat.py:548`) | **needs investigation** — single-row scope; low priority. |
| **D-010** | `_precompute_focus_columns` calls `we.compute_visa_global_with_date(doc_id)` directly but `flat_ged_doc_meta` is the documented authoritative source in flat mode (engine returns `(None, None)` for SAS REF docs). | `data_loader.py:550` vs `stage_read_flat.py:80-105` | **needs investigation** — write a spot-check comparing the two sources across all dernier docs. |

### Still documented as known limitation (no code change)

- **D-002 — H-3 dual-attribute hazard** (`ctx.responses_df` vs `ctx.workflow_engine.responses_df`). Already documented; Phase 0 added the empirical sanity-check identity (Δ = dernier count). See `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B.0.
- **D-007 — two `total` fields under one fiche payload.** See `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B.1.
- **D-008 — two `sas_refusal_rate` formulas under the same name.** See `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B.1.
- **D-009 — share_long collateral.** SCH and LGD share values dropped post-fix (0.8843→0.3263, 0.7407→0.3311). Operationally correct: dormant time is captured by `avg_contractor_delay_days`, not the share metric. See `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B.2.

### Resumption path

Phase 7 closes (Step 11b) only after Phase 0 `SIGN_OFF.md` is signed.
Phase 7 Steps 1–10 + 4b + 12a + 12a-fix2 + 12b are landed and untouched
during Phase 0.

**Operational note for the next pipeline run.** The FLAT_GED pickle cache files on disk predate the D-001 patch and lack the `cache_schema_version` key. The next `load_run_context` call will reject them and rebuild from `FLAT_GED.xlsx` (~30 s one-time cost), then write a new cache with `cache_schema_version: "v1"`. This is expected behavior, not a regression.

---

## High-value, low-risk items (highest ROI for next fixes)

### 1. UI Contractors page — ✅ RESOLVED (Phase 5, 2026-04-29)

The Contractors page is live and Focus-aware. Phase 5 fixed the
"empty entreprise cards" bug (29 enriched cards now visible, was 5),
applied canonical names everywhere (BEN→Bentin, LGD→Legendre, …), and
added focus-aware KPI reorientation + a `P1·P2·P3·P4` mini-bar fed by
the new `OVERVIEW.focus.by_contractor` payload. See
`docs/implementation/PHASE_5_TAB_FOCUS_AWARENESS_AND_ENTREPRISE_FIX.md`.

**Still open:** `app.Api.get_contractor_fiche(contractor_code, …)` is
fully implemented in the backend but the UI does not yet render an
individual contractor fiche page on click — Phase 7 territory.

**Phase 5 residual — to re-analyse after Phase 6 closes:** the
"Maître d'Oeuvre EXE — GEMO" card in the Consultants tab still appears
to display all-time data when Focus mode is on, despite the Phase 5
headline-swap rule. Two plausible causes (need to confirm during
re-analysis, do not pre-fix):
- `c.focus_owned` for the MOEX consultant ≈ `c.total` because MOEX
  owns most actionable items at any given time, so the swap fires but
  is visually indistinguishable. If true, this is faithful to the data
  and not a bug — but the card may need a second visual cue (e.g.
  emphasize the À traiter label / colorize) to communicate the focus
  state.
- The swap is not firing at all on `MoexCard` specifically (e.g.
  `focusMode` not threading correctly to it, or the conditional
  rendering is shadowed by another StatBlock that dominates the card's
  visual weight). Inspect `ui/jansa/consultants.jsx:MoexCard` (KPI row
  ~lines 233–242) and the props passed by `ConsultantsPage`'s
  `moex.map` call.

Cross-check the data: in the focus-on payload, compare
`window.CONSULTANTS[i].focus_owned` and `.total` for canonical_name =
"Maître d'Oeuvre EXE". If they're equal, root cause is data, not UI.

Reason for deferral: Phase 6 (Intelligence layer) may add new
MOEX-specific KPI surfaces (`PHASE_6A`–`6D`) that change what the MOEX
card should display. Re-analysing after 6 avoids fixing twice.

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

### 4. Chain + Onion narratives + top issues — partially wired (2026-04-29)

`output/chain_onion/top_issues.json` and `dashboard_summary.json` are now
rendered in the dashboard's `ChainOnionPanel` (`ui/jansa/overview.jsx`)
via `app.Api.get_chain_onion_intel(20)` → `window.CHAIN_INTEL`. Synthèse
column is rendered in French (Phase 2, see
`docs/implementation/PHASE_2_DIRECT_NAV_AND_FRENCH.md` and
`context/06_EXCEPTIONS_AND_MAPPINGS.md` § K). Issue rows are clickable —
they open the Document Command Center (Phase 5 Mod 2).

**Still not surfaced:**
- `CHAIN_NARRATIVES.csv` per-chain detail (only the top 20 from
  `top_issues.json` are exposed).
- `primary_driver_fr` and `recommended_focus_fr` are present in the
  payload but not rendered — Phase 4 enrichment territory.
- `dashboard_summary` fields beyond what `ChainOnionPanel` already shows
  (live/escalated/avg_pressure pills + top theme).

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
| `output/chain_onion/CHAIN_NARRATIVES.csv` | Per-chain plain-language summary; could populate a "Top issues" UI panel. (Top 20 already surfaced via `top_issues.json` — this would expose the rest.) |
| `output/chain_onion/top_issues.json` | ✅ Wired 2026-04-29 — top 20 rendered in dashboard `ChainOnionPanel` via `Api.get_chain_onion_intel`, FR overlay applied (Phase 2). |
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
2. ~~**Wire chain+onion priority into the UI** (#4).~~ ✅ Done 2026-04-29
   (Phase 2). `ChainOnionPanel` in `overview.jsx` renders the top 20 from
   `top_issues.json` with FR synthese. Remaining: per-chain narrative detail
   from `CHAIN_NARRATIVES.csv` is still un-surfaced.
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
