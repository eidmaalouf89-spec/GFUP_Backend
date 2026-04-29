# Phase 0 — Backend Data Audit & Streamlining

This MD is **self-contained**. An agent or engineer assigned only this phase can execute it cold without reading any other file in `docs/implementation/`. It is a STANDALONE entry point: open a fresh chat, hand it this file, work top to bottom.

---

## 1. Objective

End-to-end verification that **every number visible in the UI is traceable backwards through every pipeline stage to its raw source** (raw GED + consultant reports). Goal: 100% data lineage; zero silent transformations; every filter documented; every divergence either fixed or explicitly catalogued as a known limitation.

This phase produces three permanent assets:
1. A reusable verification harness under `scripts/audit/` that any future engineer can re-run.
2. A divergence report (`docs/audit/DIVERGENCE_REPORT.md`) showing where numbers diverge across stages.
3. A triage record (`docs/audit/TRIAGE.md`) classifying each divergence as fixed, known limitation, or upstream ticket.

---

## 2. Origin — why this phase exists

Phase 7 (contractor quality fiche) reached the visual smoke stage and surfaced multiple data integrity issues that revealed a systemic gap: **the codebase has no test harness comparing numbers across pipeline stages**. Concretely:

- A stale `FLAT_GED_cache_resp.pkl` silently served zero SAS-track rows for an unknown duration (cache freshness check uses file mtime only — does not detect schema drift in upstream code).
- `WorkflowEngine.__init__` filters `is_exception_approver == True`, which strips ALL SAS rows from `ctx.workflow_engine.responses_df` while leaving them in `ctx.responses_df`. Two attributes named the same way return different data.
- SNI SAS REF count diverged across three sources: 0 (cached/stale), 52 (fresh flat_ged via `ctx.responses_df`), ~184 (operator's count from raw GED).
- Contractor AMP showed `share_contractor_in_long_chains = 199%` in the long-chains panel — mathematically impossible (numerator > denominator). Suspected double-count after the dormant-time extension landed in `_contractor_delay_for_chain` (numerator now includes dormant time; denominator `chain.totals.delay_days` does not).
- An unspecified raw GED ↔ flat GED discrepancy noted by the project owner during Phase 7 visual smoke; details live in his personal notes.

Each issue would have been caught immediately by a stage-by-stage divergence harness. None was.

---

## 3. Standard Rules (embedded — do not skip)

### Tooling
Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) for inspecting Windows-mounted source files. The Linux mount caches stale views. Bash IS fine for executing scripts (`python scripts/audit/...`, `pytest`, `python -m py_compile`). See `context/11_TOOLING_HAZARDS.md`.

### Priorities
1. App must always run.
2. Phase 0 is INVESTIGATION + DOCUMENTATION-FIRST. No code changes during steps 0.1–0.5. Code patches only in step 0.6, after triage.
3. No pipeline rerun in Cowork unless explicitly authorized. The audit must work against the existing `runs/run_0000/` artifact.
4. No edits to UI files during Phase 0. The contractor quality fiche stays exactly as Phase 7 left it.

### Forbidden moves during Phase 0
- Do NOT rewrite `contractor_quality.py` business logic during steps 0.1–0.5. You may patch ONLY in step 0.6 and ONLY for items the triage marks "fix-now."
- Do NOT modify `chain_timeline_attribution.py`, `aggregator.py`, `consultant_fiche.py`, `contractor_fiche.py`, or any pipeline stage during the audit.
- Do NOT change UI files, `app.py` UI methods, or `data_bridge.js`. Phase 0 is purely backend.
- Do NOT trigger a fresh pipeline run. Verify against current cached state. If a stage's data is suspect because of cache staleness, delete the relevant cache file (a non-pipeline operation; the next `load_run_context` will re-parse from FLAT_GED.xlsx in ~30s).

---

## 4. Pipeline Stages To Audit (numbered for reference)

```
A. RAW SOURCES
   A1. input/*.xlsx — raw GED export
   A2. input/*.xlsx — consultant reports (Socotec PDFs ingested → consultant_reports.xlsx)
   A3. runs/run_0000/consultant_reports.xlsx — normalized reports
   A4. data/report_memory.db — historical report state (SQLite)

B. FLAT_GED PIPELINE
   B1. stage_read_flat (src/pipeline/stages/stage_read_flat.py)
       - Builds docs_df + responses_df from raw GED
       - line 538-569 emits SAS rows with approver_raw="0-SAS"
   B2. FLAT_GED.xlsx (output/intermediate/) — debugging artifact
   B3. FLAT_GED_cache_docs.pkl + FLAT_GED_cache_resp.pkl + FLAT_GED_cache_meta.json
       - Cache layer (data_loader._load_flat_normalized_cache)
       - Freshness: cache mtime > FLAT_GED.xlsx mtime (NO code-version check)

C. RUN CONTEXT
   C1. RunContext.docs_df (≡ dernier_df in FLAT_GED mode per data_loader.py:414)
   C2. RunContext.dernier_df
   C3. RunContext.responses_df (UNFILTERED — includes SAS rows)
   C4. RunContext.workflow_engine
   C5. RunContext.workflow_engine.responses_df (FILTERED: drops is_exception_approver)
   C6. RunContext.workflow_engine._lookup ((doc_id, approver_canonical) → response)
   C7. RunContext.dernier_df._visa_global, ._visa_global_date, etc.
       (added by data_loader._precompute_focus_columns — DERNIER ONLY)

D. CHAIN ATTRIBUTION
   D1. output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json (loaded once per request)
   D2. output/chain_onion/CHAIN_REGISTER.csv, CHAIN_VERSIONS.csv, CHAIN_EVENTS.csv

E. REPORTING BUILDERS
   E1. contractor_fiche.build_contractor_fiche → block1/2/3/4_quality
   E2. contractor_quality.build_contractor_quality → kpis + polar + dormant + long_chains
   E3. contractor_quality.build_contractor_quality_peer_stats → median/p25/p75
   E4. consultant_fiche.build_consultant_fiche
   E5. aggregator.* (overview, contractors list, consultants list)
   E6. ui_adapter.adapt_overview / adapt_contractors_list / adapt_consultants

F. UI ADAPTERS (app.py)
   F1. get_overview_for_ui
   F2. get_consultants_for_ui
   F3. get_contractors_for_ui
   F4. get_fiche_for_ui (consultant)
   F5. get_contractor_fiche_for_ui (delegates to get_contractor_fiche +
       enriches name + merges quality)
   F6. _sanitize_for_json wrapping

G. BRIDGE + UI
   G1. ui/jansa/data_bridge.js → window.OVERVIEW, CONSULTANTS, CONTRACTORS,
       CONTRACTORS_LIST, FICHE_DATA, CONTRACTOR_FICHE_DATA, CHAIN_INTEL
   G2. JSX consumers (overview.jsx, contractors.jsx, contractor_fiche_page.jsx, etc.)
```

The audit reads "downstream stage shows N, upstream stage shows M, M ≠ N" and explains each transformation between them.

---

## 5. Metrics To Verify

Per-contractor (29 contractors):
- Total documents (active dernier count)
- Total submission attempts (all indices, all history available)
- VSO count + rate
- VAO count + rate
- REF count + rate
- SAS REF count + rate (currently shows historical via 0-SAS responses)
- VSO-SAS count
- HM count
- SUS count (MOEX visa, not Socotec)
- Dormant REF count (latest indice REF, not yet resubmitted)
- Dormant SAS REF count
- SOCOTEC FAV/SUS/DEF counts
- SOCOTEC SUS rate
- Chain count
- Long-chain count (chain_long flag)
- Per-chain attribution: ENTREPRISE total, named-contractor total, MOEX total, others
- avg_contractor_delay_days (NOW INCLUDES DORMANT TIME — verify denominator includes it too)
- pct_chains_long
- share_contractor_in_long_chains (the 199% bug lives here)
- Polar histogram bucket distribution

Per-consultant: same skeleton applied to consultant data.

Project-wide: peer stats (median, p25, p75) for the 5 KPIs.

---

## 6. Verification Scripts To Build (deliverables)

Create folder `scripts/audit/`. Each script takes a contractor code (or runs all 29 if none specified) and emits a stage-by-stage count table. Output goes to `docs/audit/`.

Required scripts:

| Script | What it counts | Stages compared |
|---|---|---|
| `audit_sas_ref.py` | SAS REF events | Raw GED 0-SAS REF rows → responses_df → workflow_engine.responses_df → contractor_quality output → UI |
| `audit_ref.py` | REF events (full track) | Same chain |
| `audit_visa_distribution.py` | VSO/VAO/REF/SAS REF/HM/SUS counts on dernier | docs_df.visa_global vs aggregator vs UI |
| `audit_socotec.py` | SOCOTEC FAV/SUS/DEF | Raw consultant_reports.xlsx → responses_df → contractor_quality SUS rate |
| `audit_dormant.py` | Dormant REF / SAS REF | docs_df + dernier_df → contractor_quality dormant lists → UI |
| `audit_chains.py` | Chain count, chain_long count, attribution_breakdown sums | CHAIN_REGISTER + CHAIN_TIMELINE_ATTRIBUTION → contractor_quality.long_chains |
| `audit_share_long.py` | share_contractor_in_long_chains | Verify numerator ≤ denominator, find the AMP 199% root cause |
| `audit_peer_stats.py` | median/p25/p75 across 29 contractors | Per-contractor raw → peer aggregation → UI |

Each script's output format:
```
=== AUDIT: <metric> for contractor=<code> ===
Stage A1 (raw GED):                  <count>
Stage B1 (stage_read_flat output):   <count>
Stage C3 (ctx.responses_df):         <count>
Stage C5 (workflow_engine.responses_df): <count>  [DROP: is_exception_approver=True]
Stage E2 (contractor_quality):       <count>
Stage F5 (app.py UI wrapper):        <count>
Stage G1 (window.CONTRACTOR_FICHE_DATA): <count>  [requires manual UI inspection]

CONVERGENCE: <ALL EQUAL | DIVERGENCE AT <stage>>
```

Scripts run in <30 seconds per contractor. Total audit: <10 minutes for all 29.

---

## 7. Files

### READ (required during audit, do NOT modify in steps 0.1–0.5)
- `src/pipeline/stages/stage_read_flat.py` (full)
- `src/reporting/data_loader.py` lines 70–600 (cache layer, RunContext build)
- `src/workflow_engine.py` lines 1–100 (responses_df filter, _lookup build)
- `src/reporting/contractor_quality.py` (full)
- `src/reporting/contractor_fiche.py` (full)
- `src/reporting/aggregator.py` (relevant per-metric sections)
- `src/reporting/chain_timeline_attribution.py` (loader + breakdown shape)
- `src/reporting/ui_adapter.py` (adapt_overview, adapt_contractors_list)
- `src/flat_ged/transformer.py` lines 200–520 (response row generation)
- `app.py` lines 600–1100 (contractor + UI methods)
- `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json` (sample 1-2 chains)
- `runs/run_0000/consultant_reports.xlsx` (sample inspection)

### CREATE
- `scripts/audit/audit_sas_ref.py`
- `scripts/audit/audit_ref.py`
- `scripts/audit/audit_visa_distribution.py`
- `scripts/audit/audit_socotec.py`
- `scripts/audit/audit_dormant.py`
- `scripts/audit/audit_chains.py`
- `scripts/audit/audit_share_long.py`
- `scripts/audit/audit_peer_stats.py`
- `scripts/audit/_common.py` (shared helpers: ctx loader, table formatter, etc.)
- `docs/audit/PIPELINE_INVENTORY.md` (the stage map from §4 with file:line references)
- `docs/audit/CANARY_BEN.md` (one canary contractor's full lineage)
- `docs/audit/DIVERGENCE_REPORT.md` (full output of all scripts for all 29 contractors)
- `docs/audit/TRIAGE.md` (one row per divergence: classification + action)
- `docs/audit/SIGN_OFF.md` (the green-light criteria checklist with results)

### MAY MODIFY (only in step 0.6, only after triage approves)
- `src/reporting/data_loader.py` — add `CACHE_SCHEMA_VERSION` constant + freshness check, IF triage classifies the cache-staleness risk as fix-now.
- `src/reporting/contractor_quality.py` — fix specific divergences (e.g. AMP 199%) IF triage classifies them as fix-now and within Phase 0 scope.
- `context/06_EXCEPTIONS_AND_MAPPINGS.md`, `context/11_TOOLING_HAZARDS.md`, `context/07_OPEN_ITEMS.md` — document findings (always).

### DO NOT TOUCH (in any step of Phase 0)
- `ui/jansa/contractor_fiche_page.jsx` and any other UI JSX
- `ui/jansa-connected.html`
- `ui/jansa/data_bridge.js`
- `app.py` UI methods (get_*_for_ui)
- `src/pipeline/stages/*` business logic (read-only audit)
- `src/chain_onion/`
- `src/team_version_builder.py`
- `runs/run_0000/`, `data/*.db`

---

## 8. Plan (steps)

### Step 0.1 — Pipeline-stage inventory
Read all files listed in §7 READ. Produce `docs/audit/PIPELINE_INVENTORY.md` with the §4 stage list expanded: for each stage, list the file:line references for every transformation, every filter, every dropna, every type-coercion. Identify and document EVERY place a row count can change (filter, exclusion, deduplication, normalization).

Special focus:
- `stage_read_flat.py` lines 538–569: how many rows enter, how many exit, per row type
- `data_loader._load_flat_normalized_cache`: cache freshness check logic
- `WorkflowEngine.__init__`: the `is_exception_approver` filter and what it removes
- `data_loader._precompute_focus_columns`: which fields are added on dernier_df vs docs_df
- `contractor_quality._apply_legacy_filter`: the BENTIN_OLD filter
- `aggregator`: every per-contractor count computation

Output: `docs/audit/PIPELINE_INVENTORY.md`. ~200-400 lines. Reference for all subsequent steps.

### Step 0.2 — Canary contractor: BEN
For BEN specifically, walk every metric backwards through every stage. Print actual counts at each stage. Compare to UI. This builds the template all other audit scripts follow.

Output: `docs/audit/CANARY_BEN.md`. One section per metric (§5). Each section ends with "AGREES" or "DIVERGES at stage X — reason: ...".

If any divergence is found here that wasn't already known (cache, is_exception_approver, BENTIN_OLD filter, raw↔flat gap), that's a new finding to track in TRIAGE.md.

### Step 0.3 — Build verification scripts
For each script in §6, write a small Python file that:
1. Loads ctx via `load_run_context(BASE_DIR)`
2. Computes the count at each pipeline stage independently
3. Prints the stage-by-stage table
4. Returns 0 if all equal, 1 if divergence detected
5. Accepts `--contractor BEN` or runs all 29 if no flag

Use `scripts/audit/_common.py` for shared helpers (ctx loader, table formatter, contractor list iteration).

Validate each script: `python scripts/audit/audit_<metric>.py --contractor BEN`. Each runs in <30s.

### Step 0.4 — Run all audits, produce divergence report
```
for script in scripts/audit/audit_*.py; do
    python "$script" >> docs/audit/DIVERGENCE_REPORT.md
done
```

`DIVERGENCE_REPORT.md` collects every script's output. Manually scan for "DIVERGES" lines. Each one becomes a TRIAGE.md row.

### Step 0.5 — Triage
For each divergence, classify in `docs/audit/TRIAGE.md`:

| ID | Stage | Metric | Contractor | Description | Classification | Action |
|---|---|---|---|---|---|---|
| D-001 | C5 vs C3 | SAS REF count | all | workflow_engine drops is_exception_approver | known limitation | document in 06_EXCEPTIONS |
| D-002 | A1 vs B1 | SAS REF count | SNI | raw GED has 184, flat_ged has 52 | requires upstream rework | escalate; not fixable in Phase 0 |
| D-003 | E2 long-chains | share_contractor | AMP | 199% (>100%) | fix-now | patch contractor_quality._long_chains math |
| ... | | | | | | |

Classifications:
- **fix-now**: clear bug with local fix; do in step 0.6
- **known limitation**: intentional behavior; document and move on
- **upstream rework**: requires changes to pipeline stages (out of Phase 0 scope); escalate as a separate ticket
- **needs investigation**: not enough info; schedule follow-up

### Step 0.6 — Fix critical
For each TRIAGE row classified "fix-now", apply the smallest safe patch. Re-run the relevant audit script to confirm convergence. Examples:
- Add `CACHE_SCHEMA_VERSION = "v1"` constant to `data_loader.py`; include in cache_meta.json; cache rebuild required when version differs. Bump manually whenever stage_read_flat or related code changes.
- Fix AMP 199%: most likely root cause is denominator `total_delay_in_long` is computed from `chain.totals.delay_days` (no dormant time) but numerator `contractor_delay_in_long` uses extended `_contractor_delay_for_chain` (includes dormant time). Either add dormant time to denominator OR strip it from numerator for this specific computation. Pick the option that matches Eid's operational intuition (recommendation: revert numerator to closed-cycle attribution only for the share computation; keep extension for the avg KPI).

### Step 0.7 — Document findings
Update permanent context:
- `context/06_EXCEPTIONS_AND_MAPPINGS.md` — add a section on the WorkflowEngine `is_exception_approver` filter behavior with the exact list of approver_raw values it strips. Add a note on the responses_df dual access pattern (`ctx.responses_df` vs `ctx.workflow_engine.responses_df`).
- `context/11_TOOLING_HAZARDS.md` — add a section on cache staleness: "FLAT_GED pickle cache freshness check uses file mtime only; if `stage_read_flat.py` schema changes, manually delete the three cache files OR bump CACHE_SCHEMA_VERSION." Reference the SAS-REF outage as the canary case.
- `context/07_OPEN_ITEMS.md` — add: "Phase 0 audit findings — see docs/audit/TRIAGE.md for upstream-rework items."
- `context/02_DATA_FLOW.md` — refine the data flow diagram to show the cache layer + the WorkflowEngine filter as named transformations.

### Step 0.8 — Sign-off
Produce `docs/audit/SIGN_OFF.md` with the §12 green-light checklist filled in. Each item: PASS / FAIL / DEFERRED. If everything PASS or DEFERRED-with-rationale, Phase 7 may resume.

---

## 9. Validation (per-step)

| Step | Validation |
|---|---|
| 0.1 | PIPELINE_INVENTORY.md exists; covers all stages A–G; every transformation has a file:line reference |
| 0.2 | CANARY_BEN.md covers all metrics in §5; each metric has a verdict (AGREES / DIVERGES) |
| 0.3 | All 8 audit scripts compile + run successfully on BEN |
| 0.4 | DIVERGENCE_REPORT.md contains output for all 29 contractors × 8 metrics = 232 stage tables |
| 0.5 | TRIAGE.md has one row per divergence; every divergence classified |
| 0.6 | All fix-now patches landed; relevant audit scripts now show convergence |
| 0.7 | All four context docs updated; diff scoped to documentation only |
| 0.8 | SIGN_OFF.md complete; Phase 7 resumption gated on all green |

---

## 10. Known Issues (priority order — fed into TRIAGE)

| Pri | Issue | Source | First-pass classification |
|---|---|---|---|
| P0 | Cache freshness check uses mtime only — schema drift in `stage_read_flat.py` invisible to consumers | discovered Phase 7 12a-fix2 | fix-now (add CACHE_SCHEMA_VERSION) |
| P0 | `WorkflowEngine.__init__` filters `is_exception_approver=True` → strips SAS rows from `workflow_engine.responses_df` | discovered Phase 7 12a-fix2 | known limitation; document and surface the dual-access pattern |
| P1 | SNI SAS REF count: raw GED says ~184, flat_ged extracts 52 | reported by Eid Phase 7 visual smoke | upstream rework — escalate raw↔flat audit |
| P1 | AMP `share_contractor_in_long_chains = 199%` (>100%) | reported by Eid Phase 7 12b smoke | fix-now (denominator/numerator mismatch in `_long_chains` after dormant-time extension) |
| P2 | KPI tooltip popup not opening in pywebview | reported by Eid Phase 7 12b smoke | UI scope, deferred (Phase 7 resumption) |
| P2 | Polar histogram readability | reported by Eid Phase 7 12b smoke | UI scope, deferred (Phase 7 resumption) |
| P3 | Other per-metric divergences to be discovered by audit scripts | TBD | TBD per triage |

---

## 11. Risk

**HIGH overall** because Phase 0 governs whether downstream phases can trust the data. Specific per-step risks:
- Step 0.1: low — read-only inventory.
- Step 0.2: low — read-only canary trace.
- Step 0.3: low — new scripts in a new folder, isolated.
- Step 0.4: low — runs the new scripts.
- Step 0.5: low — documentation.
- Step 0.6: **HIGH** — code patches in `data_loader.py` + `contractor_quality.py`. Each patch must be validated against the relevant audit script before next patch. Touch one file at a time. Re-run smoke before/after.
- Step 0.7: low — context docs only.
- Step 0.8: low — sign-off doc.

---

## 12. Green-Light Criteria To Resume Phase 7

Resume Phase 7 (Step 11a UI re-smoke + Step 11b wrap-up) ONLY when ALL of these hold:

1. **Cache schema versioning landed.** `CACHE_SCHEMA_VERSION` in `data_loader.py`; `cache_meta.json` includes the version; `_flat_cache_is_fresh` rejects mismatched versions. Verified by deleting one pkl, bumping version, confirming next load rebuilds.
2. **AMP 199% fixed (or explicitly documented).** Either the metric is corrected and the audit script for share_long converges, OR the 199% is explained as expected behavior with mathematical reasoning (preferred: fix it).
3. **Raw↔flat SAS REF gap addressed.** Either the gap is closed (fresh flat_ged extraction now matches raw GED count for SNI), OR the gap is documented in `context/06_EXCEPTIONS_AND_MAPPINGS.md` with an upstream remediation ticket linked.
4. **DIVERGENCE_REPORT.md complete.** All 29 contractors × 8 metrics audited. Each divergence classified.
5. **All "fix-now" TRIAGE items closed.** Re-run the relevant audit script post-fix to confirm convergence.
6. **All four context docs updated** per step 0.7.
7. **SIGN_OFF.md** signed by the project owner (not the agent).

---

## 13. What Phase 7 Work Is Preserved

NONE of these are touched during Phase 0:

| File | Status |
|---|---|
| `src/reporting/contractor_quality.py` | Verified by audit; may be patched in step 0.6 ONLY for triage fix-now items |
| `app.py::get_contractor_fiche_for_ui` | Untouched |
| `ui/jansa/data_bridge.js::loadContractorFiche` | Untouched |
| `ui/jansa/contractor_fiche_page.jsx` | Untouched (the tooltip popup issue and polar polish wait until Phase 7 resumes) |
| `ui/jansa/shell.jsx`, `overview.jsx`, `contractors.jsx` | Untouched |
| `ui/jansa-connected.html` script tag list | Untouched |
| `docs/implementation/PHASE_7_CONTRACTOR_QUALITY_FICHE.md` | Untouched |

The contractor quality fiche is FUNCTIONAL — its numbers are simply not yet certified. Users can navigate to it; numbers shown are the current backend output.

---

## 14. Resumption path after Phase 0

Once §12 is green:
1. Resume Phase 7 at **Step 11a** (re-run UI smoke checklist with the corrected backend numbers).
2. If the UI checklist passes, proceed to **Step 11b** (phase report, context final updates, README cleanup, plan-file deletion).
3. The Phase 7 plan (`docs/implementation/PHASE_7_CONTRACTOR_QUALITY_FICHE.md`) will be replaced by `PHASE_7_CONTRACTOR_QUALITY_FICHE_REPORT.md` at that point.

---

## 15. Cowork Handoff (paste-ready, fresh chat)

```
Objective:
Execute Phase 0 — backend data audit & streamlining for the GFUP_Backend
project. End-to-end verification that every UI-visible number is traceable
through every pipeline stage to its raw source.

Repository: GFUP_Backend / GF Updater v3 / 17&CO Tranche 2.
Risk level: HIGH overall (governs trust in all downstream metrics).

Read fully before starting:
- docs/implementation/PHASE_0_BACKEND_DEBUGGING.md (this file)
- README.md §"Phase 0 — Backend Data Audit (current)"
- context/00_PROJECT_MISSION.md
- context/01_RUNTIME_MAP.md
- context/02_DATA_FLOW.md
- context/06_EXCEPTIONS_AND_MAPPINGS.md
- context/07_OPEN_ITEMS.md
- context/11_TOOLING_HAZARDS.md

Execute steps 0.1–0.8 from §8 of the Phase 0 plan. Do NOT skip steps. Each
step has explicit validation in §9; produce its deliverable file before
moving on. Use the Read tool for source inspection (not bash).

Hard rules:
- No UI changes in any step.
- No pipeline rerun.
- No business-logic changes during steps 0.1–0.5 (audit-only).
- Code patches in step 0.6 only, and only for items the triage classifies
  "fix-now."
- Sign-off (§12) gates Phase 7 resumption.

Report back after each step with the deliverable file + the validation
result from §9.
```

---

## 16. Done Definition

- All 8 audit scripts exist and pass on at least the canary contractor (BEN).
- `docs/audit/DIVERGENCE_REPORT.md` exists and covers all 29 contractors × 8 metrics.
- `docs/audit/TRIAGE.md` exists with every divergence classified.
- All "fix-now" items closed; relevant audit scripts converge.
- Context docs (06, 07, 11, 02) updated.
- README §"Phase 0" updated to "completed" status (§17 of README protocol below).
- `docs/audit/SIGN_OFF.md` filled, all green-light criteria PASS or DEFERRED-with-rationale.
- Phase 7 resumes at Step 11a per §14.
