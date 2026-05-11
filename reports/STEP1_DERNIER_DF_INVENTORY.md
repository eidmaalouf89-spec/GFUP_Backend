# STEP 1 — ctx.dernier_df Diagnostic Inventory

**Date**: 2026-05-11
**Author**: Eid Maalouf + Claude Code
**Scope**: READ-ONLY census of every operational consumer of `ctx.dernier_df`, `dernier_df` parameter passthroughs, and `is_dernier_indice` across the GF Updater V3 codebase.
**Purpose**: Prepare for replacing `ctx.dernier_df` with a canonical `latest_chain_df` view.

---

## Section 1 — Source of Contamination

**File**: `src/reporting/data_loader.py`

### Flat path (active, line 467-468)

```python
docs_df["is_dernier_indice"] = True      # line 467
dernier_df = docs_df.copy()              # line 468
```

**Problem**: ALL docs (every indice of every numero) are stamped `is_dernier_indice=True` and copied wholesale into `dernier_df`. The documented RunContext contract (line 47: `# dernier indice docs only`) is violated. Result: 4360 rows for 2554 numeros — every row claims to be the latest indice.

### Legacy path (inactive, line 876)

```python
dernier_df = versioned_df[versioned_df["is_dernier_indice"] == True].copy()
```

**Note**: Legacy VersionEngine path correctly filters. Not active under flat GED mode.

### RunContext dataclass (line 35-58)

17 fields. `dernier_df` at line 47 with type `Optional[pd.DataFrame]`. The field comment `# dernier indice docs only` is the stated contract.

---

## Section 2 — Complete Inventory Table

### Classification rubric

| Risk | Meaning |
|------|---------|
| **HIGH** | Assumes one row per numero. Inflated counts or wrong lookups under contaminated dernier_df. Migrate Step 4+. |
| **MEDIUM** | Uses dernier_df but tolerates duplicates OR has a local guard. Still should migrate. Step 4+. |
| **LOW** | Reference/docstring only, or local parameter passthrough that inherits caller's risk. Step 7+. |
| **LEGACY** | Dead code, backup file, retired module. Do not migrate. |

### Active production code

| # | File | Function/scope | Line(s) | Usage shape | Assumes 1-row/numero? | Risk | Migrate | Proposed replacement |
|---|------|---------------|---------|-------------|----------------------|------|---------|---------------------|
| 1 | `data_loader.py` | `load_run_context` (flat path) | 467-468 | **SOURCE**: stamps all rows `is_dernier_indice=True`, copies to `dernier_df` | YES — violates contract | **HIGH** | Step 4 | Build `latest_chain_df` from `docs_df` using `max(indice)` per numero; assign to `ctx.dernier_df` (or new field) |
| 2 | `data_loader.py` | `_precompute_focus_columns` | 586+ | Parameter passthrough: mutates `dernier_df` in-place adding `_visa_global`, `_days_since_last_activity`, `_focus_priority`, etc. | Inherits caller | **MEDIUM** | Step 4 | Pass `latest_chain_df` instead |
| 3 | `data_loader.py` | `load_run_context` (legacy path) | 876 | Proper filter: `versioned_df[is_dernier_indice == True]` | No (correct) | **LOW** | Step 7 | No change needed (legacy path) |
| 4 | `aggregator.py` | `compute_project_kpis` | 91, 161 | `dernier = ctx.dernier_df`; `len(ctx.dernier_df)` for total_docs_current | YES — inflated count | **HIGH** | Step 4 | Use `latest_chain_df` |
| 5 | `aggregator.py` | `compute_monthly_timeseries` | 193, 196 | Iterates `ctx.dernier_df` for monthly grouping | YES — inflated series | **HIGH** | Step 4 | Use `latest_chain_df` |
| 6 | `aggregator.py` | `compute_weekly_timeseries` | 236, 241 | Iterates `ctx.dernier_df` for weekly grouping | YES — inflated series | **HIGH** | Step 4 | Use `latest_chain_df` |
| 7 | `aggregator.py` | `compute_contractor_summary` | 461, 469 | Iterates `ctx.dernier_df` per contractor | YES — inflated per-contractor counts | **HIGH** | Step 4 | Use `latest_chain_df` |
| 8 | `aggregator.py` | `compute_operational_universe` | 565 | `dernier = ctx.dernier_df` — drives operational dashboard | YES — inflated universe | **HIGH** | Step 4 | Use `latest_chain_df` |
| 9 | `aggregator.py` | `compute_operational_dashboard` | 591 | Docstring references `ctx.dernier_df` | N/A (doc only) | **LOW** | Step 7 | Update docstring |
| 10 | `aggregator.py` | `universe_definition` string | 674 | String literal mentions dernier_df | N/A (doc only) | **LOW** | Step 7 | Update string |
| 11 | `consultant_fiche.py` | `build_sas_fiche` | 338 | `docs = ctx.dernier_df` — iterates for SAS fiche build | YES — old indices leak into SAS fiche | **HIGH** | Step 4 | Use `latest_chain_df` |
| 12 | `consultant_fiche.py` | `_filter_for_consultant` | 1373, 1378, 1382 | `ctx.dernier_df` filtered by consultant name | YES — old indices inflate consultant doc lists | **HIGH** | Step 4 | Use `latest_chain_df` |
| 13 | `contractor_quality.py` | `_dormant_list` (docstring) | 258-259 | Documents the bug: "dernier_df may contain multiple indices" | N/A (known-bug doc) | **LOW** | Step 7 | Update when fixed |
| 14 | `contractor_quality.py` | `build_contractor_quality` | 392-393 | `ctx.dernier_df[emetteur == code]` | YES — inflated per-contractor metrics | **HIGH** | Step 4 | Use `latest_chain_df` |
| 15 | `contractor_quality.py` | `build_contractor_quality_peer_stats` | 482-483 | Same pattern as #14 | YES — inflated peer stats | **HIGH** | Step 4 | Use `latest_chain_df` |
| 16 | `contractor_fiche.py` | `build_contractor_fiche` | 76-77 | `ctx.dernier_df[emetteur == contractor_code]` | YES — inflated contractor fiche | **HIGH** | Step 4 | Use `latest_chain_df` |
| 17 | `counter_attack_export.py` | `_resolve_dernier_row` | 120-121 | `getattr(ctx, "dernier_df", None)` — lookup by (numero, indice) | Partial — keyed lookup, may hit wrong indice | **MEDIUM** | Step 4 | Use `latest_chain_df` or chain register |
| 18 | `counter_attack_export.py` | Export enrichment | 164, 176 | Uses dernier_row for titre and reception date | Inherits #17 | **MEDIUM** | Step 4 | Same as #17 |
| 19 | `counter_attack_export.py` | Module docstring | 4, 17 | References dernier_df | N/A (doc only) | **LOW** | Step 7 | Update docstring |
| 20 | `document_command_center.py` | `search_documents` | 63, 75, 78 | Reads `ctx.dernier_df` for search results | YES — search returns old indices | **HIGH** | Step 4 | Use `latest_chain_df` |
| 21 | `document_command_center.py` | `build_document_command_center` | 171, 226, 230 | Reads `ctx.dernier_df` for DCC panel | YES — panel shows old indices | **HIGH** | Step 4 | Use `latest_chain_df` |
| 22 | `document_command_center.py` | `_build_comments_section` | 641-642 | Looks up `ctx.dernier_df` by doc_id | MEDIUM — single doc_id lookup | **MEDIUM** | Step 4 | Use `latest_chain_df` |
| 23 | `document_command_center.py` | `compute_dcc_tags_bulk` | 676, 686, 699, 701 | Iterates `ctx.dernier_df` for tag computation | YES — feeds counter_attack_builder; tags computed on old indices | **HIGH** | Step 4 | Use `latest_chain_df` |
| 24 | `document_command_center.py` | `compute_dcc_tags_bulk` (v2) | 767, 777, 790, 792 | Duplicate/variant of #23 | YES — same risk | **HIGH** | Step 4 | Use `latest_chain_df` |
| 25 | `document_command_center.py` | Module docstring | 9 | References `dernier_df._focus_owner_tier` | N/A (doc only) | **LOW** | Step 7 | Update docstring |
| 26 | `focus_filter.py` | `apply_focus_filter` | 4, 163, 164, 168, 172, 178 | Reads `ctx.dernier_df` for focus mode filtering | YES — focus filter sees old indices | **HIGH** | Step 4 | Use `latest_chain_df` |
| 27 | `focus_ownership.py` | `compute_focus_ownership` | 144, 148, 162, 175, 319, 320 | Parameter `dernier_df`; mutates in-place adding `_focus_owner`, `_focus_owner_tier` | YES — ownership computed on all indices | **HIGH** | Step 4 | Pass `latest_chain_df` |
| 28 | `drilldown_builder.py` | `_row_to_payload` | 74, 86, 96, 100 | Docstring/comments reference dernier_df column names | N/A (doc only) | **LOW** | Step 7 | Update comments |
| 29 | `drilldown_builder.py` | `build_drilldown` | 174, 184, 187, 194 | `df = ctx.dernier_df`; iterates for drilldown rows | YES — drilldown lists old indices | **HIGH** | Step 4 | Use `latest_chain_df` |
| 30 | `chain_timeline_attribution.py` | `_build_chain_timeline_for_family` | 453, 475-476 | `dernier_df = getattr(ctx, "dernier_df", None)` — focus_owner lookup by family_key | MEDIUM — keyed lookup, may hit multiple rows | **MEDIUM** | Step 4 | Use `latest_chain_df` |
| 31 | `chain_timeline_attribution.py` | `write_chain_timeline_artifact` | 560-561 | None-guard: `ctx.dernier_df is None` | N/A (guard only) | **LOW** | Step 7 | Update guard to new field name |

### app.py (API layer)

| # | File | Function/scope | Line(s) | Usage shape | Assumes 1-row/numero? | Risk | Migrate | Proposed replacement |
|---|------|---------------|---------|-------------|----------------------|------|---------|---------------------|
| 32 | `app.py` | `_prewarm_cache` | 285, 287 | `getattr(ctx, "dernier_df", None) is None` — existence check | No (guard only) | **LOW** | Step 7 | Update to new field name |
| 33 | `app.py` | `search_documents` docstring | 1007 | Docstring mentions dernier_df | N/A (doc only) | **LOW** | Step 7 | Update docstring |

### Scripts (diagnostic/audit, non-production)

| # | File | Line(s) | Risk | Migrate |
|---|------|---------|------|---------|
| 34 | `scripts/audit_focus_visa_source.py` | 191-213 | **LOW** | Step 7+ |
| 35 | `scripts/audit_counts_lineage.py` | 673-685, 2071 | **LOW** | Step 7+ |
| 36 | `scripts/audit_ui_payload_full_surface.py` | 431-447 | **LOW** | Step 7+ |
| 37 | `scripts/audit/audit_dormant.py` | 22 | **LOW** | Step 7+ |
| 38 | `scripts/audit/audit_peer_stats.py` | 47 | **LOW** | Step 7+ |
| 39 | `scripts/audit/audit_ref.py` | 62 | **LOW** | Step 7+ |
| 40 | `scripts/audit/audit_share_long.py` | 52 | **LOW** | Step 7+ |
| 41 | `scripts/audit/audit_visa_distribution.py` | 5, 56-57, 64, 66 | **LOW** | Step 7+ |
| 42 | `scripts/smoke_dashboard_post_patch.py` | 28-30 | **LOW** | Step 7+ |
| 43 | `scripts/diag/step1_equality_check.py` | (uses docs_df, not dernier_df) | **LOW** | N/A |

### Tests

| # | File | Line(s) | Risk | Migrate |
|---|------|---------|------|---------|
| 44 | `tests/test_document_command_center.py` | 46, 51 | **LOW** | Step 7+ (update mock) |
| 45 | `tests/test_focus_ownership_sas_p5.py` | 310, 314 | **LOW** | Step 7+ (update synthetic data) |
| 46 | `tests/test_contractor_quality.py` | 41, 54 | **LOW** | Step 7+ (update mock) |

### Legacy / backup (DO NOT MIGRATE)

| # | File | Notes |
|---|------|-------|
| 47 | `src/reporting/data_loader.py.pre_p4_nan_fix_backup` | Backup copy of data_loader |
| 48 | `src/reporting/document_command_center.R2B_PREWRITE.py` | Pre-write backup |
| 49 | `src/reporting/bet_report_merger.py` | RETIRED (import commented out, lines 188-189 reference is_dernier_indice) |

---

## Section 3 — Risk Summary

| Risk | Count | Files |
|------|-------|-------|
| **HIGH** | 19 | aggregator (5), consultant_fiche (2), contractor_quality (2), contractor_fiche (1), document_command_center (4), focus_filter (1), focus_ownership (1), drilldown_builder (1), data_loader-source (1), build_sas_fiche (1) |
| **MEDIUM** | 4 | counter_attack_export (2), chain_timeline_attribution (1), document_command_center (1) |
| **LOW** | 17 | Docstrings, guards, scripts, tests |
| **LEGACY** | 3 | Backup files, retired module |
| **Total** | **43** | |

---

## Section 4 — Known-Bad Site Cross-Check

### Cross-check 1: counter_attack_builder.py — local `latest_indice` filter

**Status**: CONFIRMED CLEAN. `counter_attack_builder.py` has **zero** references to `dernier_df` or `is_dernier_indice`. It uses `ctx.docs_df` directly and applies its own `latest_indice` filter (lines 631-634 per the Step 1 report). The builder is **not** a consumer of `ctx.dernier_df`.

However, `compute_dcc_tags_bulk` in `document_command_center.py` (inventory #23-24) iterates `ctx.dernier_df` and feeds tags into the counter_attack_builder pipeline — this **is** a HIGH-risk upstream contamination vector.

### Cross-check 2: contractor_quality.py — `_dormant_list` workaround

**Status**: CONFIRMED IN INVENTORY (#13-15). The file documents the known bug at line 258-259 and has the `_load_dormant_ref_from_artifact` workaround. Lines 392-393 and 482-483 still directly access `ctx.dernier_df` for non-dormant metrics — these are HIGH risk.

### Cross-check 3: counter_attack_export.py — dernier_df join for titre/date

**Status**: CONFIRMED IN INVENTORY (#17-19). `_resolve_dernier_row` at lines 120-121 fetches from `ctx.dernier_df` by (numero, indice). Risk is MEDIUM because the keyed lookup is scoped to a specific indice, but contaminated dernier_df may return a wrong-indice row for the same numero.

---

## Section 5 — Diagnostic Block Results

### Block A: Chain+Onion truth counts

```
reports/CHAIN_REGISTER.csv: NOT FOUND
reports/CHAIN_VERSIONS.csv: NOT FOUND
```

Chain+Onion artifacts have not yet been generated. The `reports/` directory contains only the `ACTION_MOEX_STEP1_STEP2_REPORT.md` documentation file. The canonical `latest_chain_df` cannot be validated against Chain Register counts until the chain_onion pipeline runs.

### Block B: RunContext shape

```
RunContext dataclass: 17 fields (static analysis, import failed due to missing read_raw dependency)
Key fields:
  docs_df:          Optional[pd.DataFrame]    — all documents, all indices
  dernier_df:       Optional[pd.DataFrame]    — SHOULD be latest-indice only; ACTUALLY is docs_df.copy()
  responses_df:     Optional[pd.DataFrame]    — all visa responses
  workflow_engine:  Optional[WorkflowEngine]  — per-doc visa computation
  flat_ged_doc_meta: dict                     — {doc_id: visa_global, ...} (flat mode)
  data_date:        Optional[date]            — reference date
```

Import fails at `read_raw` (native dependency not in path). RunContext definition confirmed statically at `data_loader.py:35-58`.

### Block C: File existence

```
  OK      78,062 bytes  app.py
  OK      41,856 bytes  src/reporting/data_loader.py
  OK      29,143 bytes  src/reporting/aggregator.py
  OK      69,977 bytes  src/reporting/consultant_fiche.py
  OK      24,348 bytes  src/reporting/contractor_quality.py
  OK      16,043 bytes  src/reporting/contractor_fiche.py
  OK      23,445 bytes  src/reporting/counter_attack_builder.py
  OK      15,909 bytes  src/reporting/counter_attack_export.py
  OK      15,210 bytes  src/reporting/counter_attack_query.py
  OK      35,115 bytes  src/reporting/document_command_center.py
  OK      14,248 bytes  src/reporting/focus_filter.py
  OK      13,094 bytes  src/reporting/focus_ownership.py
  OK      17,246 bytes  src/reporting/drilldown_builder.py
  OK      27,237 bytes  src/reporting/chain_timeline_attribution.py
  OK      13,839 bytes  src/reporting/bet_report_merger.py
  MISSING           0 bytes  reports/CHAIN_REGISTER.csv
  MISSING           0 bytes  reports/CHAIN_VERSIONS.csv
  MISSING           0 bytes  reports/COUNTER_ATTACK_ITEMS.csv
```

All source files present. Artifact CSVs not yet generated (expected — pipeline hasn't run in this environment).

---

## Section 6 — Zero-Hit Confirmations

| Scope | Pattern searched | Result |
|-------|-----------------|--------|
| `ui/jansa/**/*.js,*.jsx` | `dernier_df`, `is_dernier_indice` | **ZERO MATCHES** — UI layer is clean |
| `src/chain_onion/**/*.py` | `dernier_df`, `is_dernier_indice` | **ZERO MATCHES** — Chain+Onion layer is clean |
| `counter_attack_builder.py` | `dernier_df`, `is_dernier_indice` | **ZERO MATCHES** — uses `ctx.docs_df` with local filter |

---

## Section 7 — Migration Priority Map

### Step 4+ (immediate — HIGH risk, inflated counts)

These consumers assume one row per numero and produce wrong results:

1. **data_loader.py:467-468** — FIX THE SOURCE: build `latest_chain_df` with proper `max(indice)` dedup
2. **aggregator.py** — 5 functions (kpis, monthly, weekly, contractor_summary, operational_universe)
3. **consultant_fiche.py** — 2 functions (build_sas_fiche, _filter_for_consultant)
4. **contractor_quality.py** — 2 functions (build_contractor_quality, build_contractor_quality_peer_stats)
5. **contractor_fiche.py** — 1 function (build_contractor_fiche)
6. **document_command_center.py** — 4 call sites (search, panel, compute_dcc_tags_bulk x2)
7. **focus_filter.py** — 1 function (apply_focus_filter)
8. **focus_ownership.py** — 1 function (compute_focus_ownership, mutates in-place)
9. **drilldown_builder.py** — 1 function (build_drilldown)
10. **data_loader.py:_precompute_focus_columns** — parameter passthrough

### Step 4+ (MEDIUM risk — keyed lookups, partial exposure)

11. **counter_attack_export.py** — 2 call sites (_resolve_dernier_row, enrichment)
12. **chain_timeline_attribution.py** — 1 call site (focus_owner lookup)
13. **document_command_center.py** — 1 call site (_build_comments_section)

### Step 7+ (LOW risk — docstrings, guards, scripts, tests)

14. All docstring/comment references (inventory #9, 10, 19, 25, 28, 33)
15. All None-guards (inventory #31, 32)
16. All scripts (inventory #34-43)
17. All tests (inventory #44-46)

### DO NOT MIGRATE

18. All backup/legacy files (inventory #47-49)

---

## Section 8 — Observations and Hazards

### O-1: Contamination is total in flat mode

The flat path (`data_loader.py:467-468`) copies `docs_df` wholesale. Every downstream consumer that reads `ctx.dernier_df` operates on ALL indices of ALL numeros. The legacy VersionEngine path (line 876) filters correctly but is not active.

### O-2: compute_dcc_tags_bulk is an upstream contamination vector

Even though `counter_attack_builder.py` is clean (uses `ctx.docs_df`), the DCC tags it consumes are computed by `compute_dcc_tags_bulk` which iterates `ctx.dernier_df`. Tags from old indices may leak through this pipeline.

### O-3: focus_ownership mutates dernier_df in place

`compute_focus_ownership` (focus_ownership.py:144) adds `_focus_owner` and `_focus_owner_tier` columns directly to the `dernier_df` DataFrame. Every subsequent consumer sees these columns. If the fix changes the DataFrame identity (new object vs. mutation), all downstream focus-dependent code must be retested.

### O-4: _precompute_focus_columns also mutates in place

`data_loader.py:_precompute_focus_columns` adds `_visa_global`, `_last_activity_date`, `_days_since_last_activity`, `_earliest_deadline`, `_days_to_deadline`, `_focus_priority` columns to `dernier_df`. Same mutation hazard as O-3.

### O-5: Chain+Onion artifacts not yet available

`CHAIN_REGISTER.csv` and `CHAIN_VERSIONS.csv` do not exist. The `latest_chain_df` replacement cannot be validated against chain truth until these are generated. Plan: generate chain artifacts first (Step 2-3), then build `latest_chain_df` from them (Step 4).

### O-6: No production test coverage for dernier_df assumptions

The three test files that reference `dernier_df` use synthetic/mock data with correct one-row-per-numero shapes. No test exercises the contaminated path (all-indices-marked-dernier). Any fix should include a regression test that validates the dedup.

### O-7: counter_attack_export keyed lookup is fragile

`_resolve_dernier_row` (counter_attack_export.py:120) looks up `ctx.dernier_df` by `(numero, indice)`. Under contamination, multiple rows may match if the same (numero, indice) pair appears more than once. The first match wins (`iloc[0]`), but correctness depends on row ordering.

### O-8: Tooling hazard reminder

Per `context/11_TOOLING_HAZARDS.md` H-1: Linux sandbox mount is stale for Windows source files — all file inspection in this inventory used the Read tool, not bash cat/grep.

---

## Appendix — Grep Coverage

Patterns searched: `dernier_df`, `is_dernier_indice`, `dernier` (in counter_attack_builder only)

Roots searched:
- `src/reporting/*.py` — 14 files matched
- `src/chain_onion/*.py` — 0 matches
- `app.py` — 2 matches
- `scripts/**/*.py` — 10 files matched
- `tests/**/*.py` — 3 files matched
- `ui/jansa/**/*.js,*.jsx` — 0 matches

Total unique active consumer sites: **31** (excluding legacy/backup)
Total inventory entries: **49** (including legacy, scripts, tests, docstrings)
