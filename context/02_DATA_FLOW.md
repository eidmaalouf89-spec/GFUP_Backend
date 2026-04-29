# 02 — Data Flow

> End-to-end: what enters, what is generated, what is consumed.
> Reconstructed from `paths.py`, `run_orchestrator.py`, all 11 stages,
> `flat_ged_runner.py`, `data_loader.py`, `aggregator.py`, `consultant_fiche.py`,
> `chain_onion/source_loader.py`.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                INPUTS                                       │
└────────────────────────────────────────────────────────────────────────────┘
input/
  GED_export.xlsx                ← required (sheet "Doc. sous workflow, x versions")
  Grandfichier_v3.xlsx           ← optional; if missing, last-good FINAL_GF inherited
                                   from runs/run_*/ via run_memory.db
  Mapping.xlsx                   ← present in repo, but NOT consumed at pipeline
                                   runtime today (UI exposes it as informational).
  consultant_reports/            ← optional folder of PDFs/XLSXs
    AMO HQE/                       (Le Sommer)
    BET Acoustique AVLS/           (AVLS)
    BET Structure TERRELL/         (Terrell)
    socotec/                       (SOCOTEC)
                                                  │
                                                  ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       FLAT GED BUILDER (auto, pre-pipeline)                 │
└────────────────────────────────────────────────────────────────────────────┘
src/flat_ged_runner.build_flat_ged_artifacts(ged_path, output/intermediate/)
  src/flat_ged.build_flat_ged(...) [FROZEN MODULE]
    ├─ reader.py        : reads GED via the parser contract
    ├─ resolver.py      : per-doc resolution
    ├─ transformer.py   : applies consultant_mapping + status_mapping
    │                     EXCEPTION_COLUMNS rows go to "Exception List" → excluded
    ├─ validator.py
    └─ writer.py        : writes FLAT_GED.xlsx + DEBUG_TRACE.csv
Output:
  output/intermediate/FLAT_GED.xlsx           (sheets GED_RAW_FLAT + GED_OPERATIONS)
  output/intermediate/DEBUG_TRACE.csv
  output/intermediate/flat_ged_run_report.json
  Then registered as run_memory artifacts: FLAT_GED, FLAT_GED_DEBUG_TRACE,
  FLAT_GED_RUN_REPORT.
                                                  │
                                                  ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       11-STAGE PIPELINE (src/pipeline/stages/)              │
└────────────────────────────────────────────────────────────────────────────┘
stage_init_run         → row in runs table (run_memory.db); creates runs/run_NNNN/
stage_read_flat        → ctx.docs_df, ctx.responses_df from FLAT_GED.xlsx
                          (or stage_read in raw fallback when GFUP_FORCE_RAW=1)
stage_normalize        → normalize_docs / normalize_responses + SAS RAPPEL pre-2026
                          filter; writes ctx.sas_filtered_df
stage_version          → version_engine.VersionEngine: ctx.versioned_df with
                          is_dernier_indice / lifecycle_id / chain_position;
                          ctx.dernier_df derived
stage_route            → routing.build_routing_table + route_documents +
                          read_all_gf_sheet_structures (reads GF .xlsx);
                          applies ExclusionConfig (from config_loader)
stage_report_memory    → init/load report_memory.db; ingests new
                          consultant_match_report.xlsx (HIGH/MEDIUM gate);
                          builds ctx.effective_responses_df via
                          effective_responses.build_effective_responses
stage_write_gf         → workflow_engine.WorkflowEngine; writes GF_V0_CLEAN.xlsx
                          + ANOMALY_REPORT, AUTO_RESOLUTION_LOG, IGNORED_ITEMS_LOG
stage_build_team_version → team_version_builder.build_team_version: surgical
                          patch of OGF (Grandfichier_v3.xlsx) using
                          GF_V0_CLEAN.xlsx → GF_TEAM_VERSION.xlsx
stage_discrepancy      → reconciliation_engine.run_reconciliation;
                          classify_discrepancy; Part H-1 BENTIN exception pass
                          → DISCREPANCY_REPORT.xlsx + REVIEW_REQUIRED + ignored
stage_diagnosis        → MISSING_IN_GED_DIAGNOSIS / TRUE_ONLY,
                          MISSING_IN_GF_DIAGNOSIS / TRUE_ONLY,
                          INSERT_LOG, NEW_SUBMITTAL_ANALYSIS,
                          debug_writer.write_all_debug
stage_finalize_run     → register every artifact in run_memory.db with sha256;
                          mark_run_current; copies into runs/run_NNNN/
                                                  │
                                                  ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      OUTPUTS (under output/ and runs/run_N/)                │
└────────────────────────────────────────────────────────────────────────────┘
output/                                 ← latest artifacts (mirrors runs/run_N/)
output/intermediate/                    ← FLAT_GED.xlsx etc.
output/debug/                           ← *_summary.xlsx debug aids
runs/run_0000/ … run_NNNN/              ← immutable per-run snapshot
data/run_memory.db                      ← artifact registry (sha256 keyed)
data/report_memory.db                   ← persistent consultant truth
```

---

## Read-side flow (UI feed)

`app.py` UI calls go through `src/reporting/data_loader.load_run_context`.

```
load_run_context(BASE_DIR)
  → resolves latest COMPLETED run from data/run_memory.db
  → reads registered artifact paths
  → resolves the registered FLAT_GED artifact, then:

  ┌─ FLAT_GED pickle cache layer ────────────────────────────────────┐
  │  _flat_cache_is_fresh(flat_ged_path):                            │
  │    1. xlsx mtime ≥ cache file mtime → REJECT (run wrote new xlsx)│
  │    2. cache_schema_version != CACHE_SCHEMA_VERSION → REJECT      │
  │       (D-001 fix, 2026-04-29: catches pandas pickle drift +      │
  │        upstream stage_read_flat.py schema changes)               │
  │  HIT  → unpickle docs_df + responses_df + flat_doc_meta (~3s)    │
  │  MISS → run stage_read_flat → normalize_docs → normalize_responses│
  │         (~30s one-time cost) → _save_flat_normalized_cache(...)  │
  │         writes new pkl + meta with current schema version.       │
  └──────────────────────────────────────────────────────────────────┘

  → docs_df["is_dernier_indice"] = True; dernier_df = docs_df.copy()
    (in flat mode, all rows are ACTIVE → docs_df ≡ dernier_df)

  ┌─ WorkflowEngine construction ────────────────────────────────────┐
  │  workflow_engine = WorkflowEngine(responses_df)                  │
  │  Inside __init__ (workflow_engine.py:54-57):                     │
  │    self.responses_df = responses_df[~is_exception_approver]      │
  │    → STRIPS every SAS row + Exception List approver row.         │
  │    → ctx.workflow_engine.responses_df is therefore SMALLER       │
  │      than ctx.responses_df by ~len(dernier_df) rows (one SAS     │
  │      per active doc).                                            │
  │    → SAS-track signal lives ONLY on ctx.responses_df.            │
  │    → workflow_engine._lookup is built from the FILTERED frame —  │
  │      correct for visa_global / deadline / non-SAS use cases.     │
  │  See context/06_EXCEPTIONS_AND_MAPPINGS.md §B.0 (H-3 hazard).    │
  └──────────────────────────────────────────────────────────────────┘

  → builds effective_responses_df via effective_responses.build_effective_responses
    (composes report_memory enrichment over the GED responses)
  → REBUILDS workflow_engine over the effective_responses_df
  → ctx.responses_df is replaced with the effective frame for downstream
  → calls reporting.focus_ownership.compute_focus_ownership IN PLACE on dernier_df
  → returns RunContext (cached at module level; cleared by clear_cache()
    after a new pipeline run)
```

Two named transformations are explicit above so audit consumers can reason
about which `responses_df` view they are reading. The B-stage cache layer
and the C-stage WorkflowEngine filter both materially change downstream
counts; both have caused production bugs (Phase 7 12a-fix2 SNI SAS REF and
Phase 0 canary StringDtype unpickle drift).

Aggregators take a `RunContext` (+ optional `FocusResult`):

| Adapter | Produces |
|---|---|
| `aggregator.compute_project_kpis(ctx, focus_result)` | KPI dict |
| `aggregator.compute_monthly_timeseries(ctx)` | history (no focus) |
| `aggregator.compute_weekly_timeseries(ctx, focus_result)` | history (focus) |
| `aggregator.compute_consultant_summary(ctx, focus_result)` | list of consultant dicts |
| `aggregator.compute_contractor_summary(ctx, focus_result)` | list of contractor dicts |
| `consultant_fiche.build_consultant_fiche(ctx, name, focus_result)` | full fiche payload |
| `consultant_fiche.build_sas_fiche(ctx, focus_result)` | special MOEX SAS fiche |
| `contractor_fiche.build_contractor_fiche(ctx, code, focus_result)` | full contractor fiche |

Then UI-shaping (`reporting.ui_adapter.adapt_*`) flattens to the
`window.OVERVIEW / CONSULTANTS / CONTRACTORS / FICHE_DATA` shape.

**Phase 5 (2026-04-29):** focus stats produced by
`focus_filter.apply_focus_filter` now carry `by_contractor` (list of
`{code, name, p1, p2, p3, p4, total}`) alongside the existing
`by_consultant`, derived from `pq_records` items where
`owner_tier == "CONTRACTOR"`. `adapt_overview` passes both through into
`window.OVERVIEW.focus.{by_consultant, by_contractor}`. Canonical
emetteur names (Bentin, Legendre, …) are applied via
`reporting.contractor_fiche.resolve_emetteur_name` — the single source
of truth for code → company name.

---

## Chain Timeline Attribution layer (post-Phase 2 of DCC project)

`src/reporting/chain_timeline_attribution.py` consumes
`output/chain_onion/CHAIN_EVENTS.csv` + `CHAIN_REGISTER.csv` +
`CHAIN_VERSIONS.csv` and a `RunContext` (for `data_date` + `dernier_df`).
It produces:

- `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json`
- `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv`

Both are disk-only (NOT registered in run_memory.db). They are auto-
refreshed by Phase 3's `Api._ensure_chain_data_fresh()` at app startup.
Phase 4's Document Command Center consumes the JSON for the
"Chronologie de la chaîne" panel section.

What the module does on top of chain_onion:

1. **Caps secondary consultant delays at 10 days from `last_primary_date`**
   per chain version. Excess days are re-attributed to MOEX as synthetic
   `MOEX_CAP_REATTRIBUTED` rows. (The Flat GED transformer's
   `compute_delay_contribution` does NOT apply this cap — see
   `context/06_EXCEPTIONS_AND_MAPPINGS.md` § F.)
2. Computes per-indice review + rework phases with per-segment timing
   vs. expected (30d review + 15d rework).
3. **Implicit closure rule:** when contractor submits indice N+1 before
   MOEX has formally closed indice N, indice N's review is closed at
   indice N+1's submittal date. The rework window for N collapses to
   0 days (contractor used 0 of 15 allowed).
4. Per-indice `closure_type ∈ {MOEX_TERMINAL, MOEX_REF,
   IMPLICIT_NEXT_INDICE, OPEN}`.
5. Chain-level `chain_long` (total > 120d) and `cycle_depasse`
   (any phase over budget, open or closed).
6. `attribution_breakdown` aggregates `MOEX_CAP_REATTRIBUTED` into the
   `Maître d'Oeuvre EXE` bucket; sibling field
   `attribution_cap_reattributed` exposes how many days came from
   the cap re-attribution.

`compute_all_chain_timelines(ctx, ...)` raises `ValueError` if
`ctx.data_date` or `ctx.dernier_df` is missing — production callers
must always supply a real RunContext.

---

## Chain + Onion data flow (independent runner)

```
python run_chain_onion.py
  Inputs:
    output/intermediate/FLAT_GED.xlsx
    output/intermediate/DEBUG_TRACE.csv
    data/report_memory.db (optional)
  Sequence (Steps 04 → 14):
    source_loader.load_chain_sources       → ops_df, debug_df, effective_df
    family_grouper.build_chain_versions    → CHAIN_VERSIONS
    family_grouper.build_chain_register    → CHAIN_REGISTER
    chain_builder.build_chain_events       → CHAIN_EVENTS
    chain_classifier.classify_chains       → portfolio_bucket on CHAIN_REGISTER
    chain_metrics.build_chain_metrics      → CHAIN_METRICS
    onion_engine.build_onion_layers        → ONION_LAYERS
    onion_scoring.build_onion_scores       → ONION_SCORES
    narrative_engine.build_chain_narratives → CHAIN_NARRATIVES
    exporter.export_chain_onion_outputs    → 7 CSV + 1 XLSX + 2 JSON
    validation_harness.run_chain_onion_validation
  Outputs (output/chain_onion/):
    CHAIN_REGISTER.csv
    CHAIN_VERSIONS.csv
    CHAIN_EVENTS.csv
    CHAIN_METRICS.csv
    ONION_LAYERS.csv
    ONION_SCORES.csv
    CHAIN_NARRATIVES.csv
    CHAIN_ONION_SUMMARY.xlsx
    dashboard_summary.json
    top_issues.json
```

The main UI consumes Chain+Onion **only** through
`app.Api._build_live_operational_numeros` → `chain_onion.query_hooks`:

- `get_live_operational(ctx)` → `live_numeros` set, used to narrow Focus to
  the live-operational chains.
- `get_legacy_backlog(ctx)` → `legacy_count`, displayed under the Focus stats.

The other 24+ query functions (`get_top_issues`, `get_high_pressure`,
`get_contractor_quality`, `get_sas_friction`, etc.) are **not yet surfaced
in the UI**. They are accessible from Python but no button or screen
triggers them today.

---

## Three identity systems, one repo

| Identity | Where it's primary | Notes |
|---|---|---|
| `(numero, indice)` | `flat_ged/*`, `chain_onion/*` | Stable across runs |
| `doc_id` (UUID) | pipeline runtime + `effective_responses_df` + `RunContext` | **Session-scoped — never persist** |
| `family_key = str(numero)` | chain_onion outputs | Stable across runs |

`query_library.py` (`src/query_library.py`) explicitly notes: "These two
identity systems are NOT automatically bridged here." Be careful when
joining flat_ged_ops_df (numero/indice) with effective_responses_df (doc_id).

---

## Hand-off contracts (what each layer guarantees the next)

1. **Flat GED builder → pipeline.** `FLAT_GED.xlsx` always has
   `GED_OPERATIONS` (active rows only) and `GED_RAW_FLAT`; Exception List
   rows are excluded. `DEBUG_TRACE.csv` may be present (batch mode).

2. **Pipeline → reporting.** `run_memory.db` holds a row for the COMPLETED
   run with sha256-verified artifacts. `data_loader` resolves them by
   `artifact_type`.

3. **Pipeline → Chain+Onion.** Chain+Onion reads `output/intermediate/*` and
   `report_memory.db` directly (NOT `run_memory.db`). It is therefore
   coupled to "the most recent run that wrote intermediate", not to a
   specific run_number.

4. **Reporting → UI.** UI consumes only the four globals
   (`window.OVERVIEW / CONSULTANTS / CONTRACTORS / FICHE_DATA`) plus
   per-call results from `get_doc_details`, `export_*`, `get_pipeline_status`.

---

## What flows but is currently NOT consumed

(Useful for evaluating ROI of next steps.)

- `consultant_match_report.xlsx` is produced and registered as artifact, but
  the UI does not surface it as a screen — only `report_memory` ingests it.
- `MISSING_IN_GED_TRUE_ONLY.xlsx`, `MISSING_IN_GF_TRUE_ONLY.xlsx`,
  `INSERT_LOG.xlsx`, `NEW_SUBMITTAL_ANALYSIS.xlsx`, `SUSPICIOUS_ROWS_REPORT.xlsx`
  are written every run but the UI's Discrepancies / Reports tab is a stub
  for everything except Tableau de Suivi VISA export.
- `output/chain_onion/CHAIN_NARRATIVES.csv`, `top_issues.json`,
  `CHAIN_ONION_SUMMARY.xlsx` are produced but not surfaced in the UI.
- `output/debug/*_summary.xlsx` debug XLSXs are registered as artifacts
  (DEBUG_*) but not consumed by reporting.
