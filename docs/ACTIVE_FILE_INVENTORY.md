# ACTIVE FILE INVENTORY
## Step 2 — CLEAN BASE + CLEAN IO Plan

**Date:** 2026-04-26
**Auditor:** Cowork / Claude — file tools scan (bash unavailable; all reads via Read/Glob/Grep)
**Repo root:** `GF updater v3/` on Desktop
**Step 1 BLOCKER count:** 0 (all 5 blockers resolved before this step began)

---

## 1. Executive Summary

| Label | Count (approx.) |
|---|---|
| ACTIVE | 52 |
| ACTIVE_TEMPORARY | 8 |
| ACTIVE_PROTECTED | 18 |
| LEGACY_REFERENCE | 10 |
| GENERATED_OUTPUT | 9 |
| ARCHIVE_CANDIDATE | 21 |
| DELETE_CANDIDATE | 9 |
| UNKNOWN | 0 |

**Total classified items (excluding input/consultant_reports PDFs and ui/node_modules):** ~127

**Conclusion:** The repo's active runtime is well-defined and healthy. The production code path runs through `main.py → app.py → pipeline/ → flat_ged/ → report_memory / run_memory → ui/jansa/`. The two largest risks for Step 3 are: (1) docs still describe aspects of the old raw-GED-first architecture, and (2) `src/pipeline/paths.py` still points `FLAT_GED_FILE` at `input/` instead of a generated intermediate — a known Step 7 target. A second structural issue is the `.claude/worktrees/` folder containing 6 stale Cowork git worktrees; these are not tracked by git but consume significant disk space and create noise in file tool scans.

**Workspace contamination check:** `GFUP CLEAN BASE + CLEAN IO/` folder — **NOT FOUND** ✅. The bash sandbox error (failing to mount that path) is a stale Cowork mount reference, not a real folder in the repo.

---

## 2. Runtime Entry Points

| Path | Role | Label | Notes |
|---|---|---|---|
| `main.py` | Pipeline CLI entry point — configures paths, calls `run_pipeline()`, sets `FLAT_GED_MODE` | ACTIVE | Imports `from pipeline.paths import *`; orchestrated externally by `run_orchestrator.py` |
| `app.py` | Flask/pywebview UI entry point — serves jansa UI, exposes API routes, `export_team_version()` | ACTIVE | Fixed (B-02 null bytes resolved). Ends cleanly at line 842. |
| `api_server.py` | Listed in spec — **does not exist** | DELETE_CANDIDATE | Not needed. Would only be created if FastAPI is revived in a future phase. No action required now. (Eid decision 2026-04-26) |
| `src/run_orchestrator.py` | Controlled pipeline runner — wraps `main.run_pipeline()` with mode switching and artifact registration | ACTIVE | Used by UI executer; sets `FLAT_GED_MODE`, `FLAT_GED_FILE`, `_ACTIVE_RUN_NUMBER` |

**Note on `api_server.py`:** This file is referenced in the CLEAN BASE plan spec but does not exist in the repo. It may be a future file (Step 6 target) or it may have been merged into `app.py`. Flagged as UNKNOWN — see Section 8.

---

## 3. Core Backend Inventory

| Path | Purpose | Label | Why |
|---|---|---|---|
| `src/config_loader.py` | Loads project config (paths, flags) | ACTIVE | Used by pipeline startup |
| `src/read_raw.py` | Reads raw GED Excel → DataFrame | ACTIVE | Raw-mode read path (stage_read.py calls this) |
| `src/normalize.py` | Normalizes raw GED docs | ACTIVE | Raw-mode normalization |
| `src/version_engine.py` | Computes version/revision state from raw GED | ACTIVE | Raw-mode path; has `is_dernier_indice` logic |
| `src/workflow_engine.py` | Derives workflow state, visa_global, approver status | ACTIVE | Used by both raw path and UI; Step 5d bug noted (multi-candidate) |
| `src/effective_responses.py` | Builds effective responses from report_memory composition | ACTIVE_PROTECTED | Core of GF reconstruction logic; rewritten in Step 8 |
| `src/report_memory.py` | SQLite-backed report memory — stores consultant report ingestion results | ACTIVE_PROTECTED | Long-term memory system; must not be broken |
| `src/run_memory.py` | SQLite-backed run memory — stores pipeline run artifacts | ACTIVE_PROTECTED | Artifact registry for GF_TEAM_VERSION, FLAT_GED, etc. |
| `src/run_orchestrator.py` | Orchestrated pipeline runner (Step 6 of old plan) | ACTIVE | See entry points table |
| `src/run_explorer.py` | Browses run history and artifacts from run_memory | ACTIVE | Used by UI runs page |
| `src/team_version_builder.py` | Builds GF_TEAM_VERSION from GF_V0_CLEAN | ACTIVE_PROTECTED | Required product feature — team export chain |
| `src/consultant_integration.py` | Orchestrates consultant PDF ingestion, matching, optional GF enrichment | ACTIVE | Contains live import of deprecated `write_gf_enriched` (risk — see M-01 from Step 1) |
| `src/consultant_gf_writer.py` | Deprecated: writes consultant responses directly to GF cells | ACTIVE_TEMPORARY | Deprecated from truth path. Still imported in `consultant_integration.py`. Must not be called from main pipeline. Step 13 will remove. |
| `src/consultant_matcher.py` | Matches consultant reports to GED docs | ACTIVE | Core consultant ingestion |
| `src/consultant_match_report.py` | Writes consultant match report to Excel | ACTIVE | Diagnostic output for consultant ingestion |
| `src/debug_writer.py` | Writes debug/trace Excel outputs | ACTIVE | Used by pipeline stages |
| `src/reconciliation_engine.py` | Reconciles discrepancies between GED and GF | ACTIVE | Post-version processing |
| `src/routing.py` | Routes docs to appropriate pipeline stages | ACTIVE | Part of pipeline compute |
| `src/writer.py` | Writes GF Excel output | ACTIVE | Core output writer |
| `src/query_library.py` | 22-function query API over flat GED context | ACTIVE | Fixed (B-01). Used by UI via data_loader |
| `src/domain/classification.py` | Domain classification helpers | ACTIVE | Used throughout pipeline |
| `src/domain/discrepancy.py` | Discrepancy domain model | ACTIVE | Used by stage_discrepancy |
| `src/domain/family_builder.py` | Builds document families | ACTIVE | Used by normalization |
| `src/domain/gf_helpers.py` | GF cell/row helpers | ACTIVE | Used by writer |
| `src/domain/normalization.py` | Domain normalization rules | ACTIVE | Used by stage_normalize |
| `src/domain/sas_helpers.py` | SAS (visa) domain helpers | ACTIVE | Used by adapter and stage_version |

---

## 4. Pipeline and Flat GED Inventory

| Path | Purpose | Label | Why |
|---|---|---|---|
| `src/pipeline/paths.py` | Canonical path constants for all pipeline I/O | ACTIVE | **H-01**: `FLAT_GED_FILE` still points at `input/` — Step 7 will fix this. `OUTPUT_GF_TEAM_VERSION` confirmed present. |
| `src/pipeline/context.py` | PipelineContext dataclass — carries state between stages | ACTIVE | Includes `flat_ged_ops_df`, `flat_ged_doc_meta`, GF_TEAM_VERSION field |
| `src/pipeline/runner.py` | Executes pipeline stages in sequence | ACTIVE | Dispatches based on `FLAT_GED_MODE`; passes `OUTPUT_GF_TEAM_VERSION` |
| `src/pipeline/compute.py` | Shared computation helpers for stages | ACTIVE | |
| `src/pipeline/utils.py` | Pipeline utilities | ACTIVE | |
| `src/pipeline/stages/stage_init_run.py` | Initializes run in run_memory | ACTIVE | |
| `src/pipeline/stages/stage_read.py` | Raw GED read stage | ACTIVE | Used when `FLAT_GED_MODE = "raw"` |
| `src/pipeline/stages/stage_read_flat.py` | Flat GED read/adapter stage | ACTIVE_TEMPORARY | `TEMPORARY_COMPAT_LAYER` markers present. Step 7 will make this permanent default. Current default is still `raw`. |
| `src/pipeline/stages/stage_normalize.py` | Normalization stage | ACTIVE | |
| `src/pipeline/stages/stage_version.py` | Version computation stage | ACTIVE | |
| `src/pipeline/stages/stage_route.py` | Routing stage | ACTIVE | |
| `src/pipeline/stages/stage_discrepancy.py` | Discrepancy detection stage | ACTIVE | |
| `src/pipeline/stages/stage_diagnosis.py` | Missing-doc diagnosis stage | ACTIVE | |
| `src/pipeline/stages/stage_write_gf.py` | GF Excel write stage | ACTIVE | Writes GF_V0_CLEAN.xlsx |
| `src/pipeline/stages/stage_report_memory.py` | Upserts effective responses into report_memory | ACTIVE_PROTECTED | E2 confidence filter, stale row deactivation; repaired in Step 8/9 |
| `src/pipeline/stages/stage_finalize_run.py` | Registers artifacts in run_memory including `GF_TEAM_VERSION` | ACTIVE_PROTECTED | GF_TEAM_VERSION chain confirmed here (I-01 from Step 1) |
| `src/flat_ged/` (entire folder) | Frozen builder snapshot from GED_FLAT_Builder | ACTIVE_PROTECTED | Must not be edited. Business logic frozen. Contains: `reader.py`, `transformer.py`, `resolver.py`, `validator.py`, `writer.py`, `config.py`, `utils.py`, `cli.py`, `__init__.py`, `input/source_main/`, `VERSION.txt`, `BUILD_SOURCE.md` |
| `src/effective_responses.py` | Effective response builder (report_memory + GED composition) | ACTIVE_PROTECTED | Rewritten in Step 8; `build_effective_responses()` with five-value provenance vocab |
| `src/query_library.py` | Flat GED query API (22 functions) | ACTIVE | Step 9c output; fixed B-01 |
| `src/consultant_ingest/` | PDF report ingestion for all consultants | ACTIVE | `avls_ingest.py`, `socotec_ingest.py`, `terrell_ingest.py`, `lesommer_ingest.py`, plus `consultant_report_builder.py`, `consultant_transformers.py`, `consultant_excel_exporter.py`, `validate_consultant_reports.py` |

---

## 5. UI Inventory

| Path | Runtime Role | Label | Why |
|---|---|---|---|
| `ui/jansa-connected.html` | **Production UI entry point** — loaded by PyWebView, bootstraps JSX via Babel standalone | ACTIVE_PROTECTED | The real product UI. Referenced by `app.py`. Must not be deleted or renamed. |
| `ui/jansa/shell.jsx` | App shell — routing, layout, nav | ACTIVE_PROTECTED | Core UI component |
| `ui/jansa/overview.jsx` | Overview/KPI dashboard page | ACTIVE_PROTECTED | Core UI component |
| `ui/jansa/consultants.jsx` | Consultants list page | ACTIVE_PROTECTED | Core UI component |
| `ui/jansa/fiche_base.jsx` | Shared fiche/drilldown base component | ACTIVE_PROTECTED | Core UI component |
| `ui/jansa/fiche_page.jsx` | Consultant/contractor fiche page | ACTIVE_PROTECTED | Core UI component |
| `ui/jansa/runs.jsx` | Run history browser page | ACTIVE_PROTECTED | Core UI component |
| `ui/jansa/executer.jsx` | Pipeline execution trigger page | ACTIVE_PROTECTED | Core UI component |
| `ui/jansa/data_bridge.js` | JS bridge to Python API (pywebview.api calls) | ACTIVE_PROTECTED | All UI→backend calls go through here |
| `ui/jansa/tokens.js` | Design tokens (colors, spacing, fonts) | ACTIVE_PROTECTED | Shared design system |
| `ui/index.html` | Legacy Vite entry point | LEGACY_REFERENCE | Not loaded by `app.py`. Part of old Vite setup. |
| `ui/vite.config.js` | Legacy Vite build config | LEGACY_REFERENCE | Not used in production. Active UI uses no build step. |
| `ui/package.json` | Vite npm project file | LEGACY_REFERENCE | Belongs to old Vite setup. |
| `ui/package-lock.json` | Vite npm lockfile | LEGACY_REFERENCE | Part of old Vite setup. |
| `ui/src/` (all files) | Old Vite React app (`App.jsx`, `main.jsx`, `App.css`, `index.css`, `assets/`, `components/ConsultantFiche.jsx`) | LEGACY_REFERENCE | Superseded by `ui/jansa/`. Not loaded by `app.py`. |
| `ui/dist/` | Vite build output | GENERATED_OUTPUT | Gitignored but physically present on disk. Stale build artifact. |
| `ui/node_modules/` | Vite npm installed packages | GENERATED_OUTPUT | Gitignored. Physically present. Not used by production (no build step). |
| `JANSA Dashboard - Standalone.html` (root) | 1.7 MB standalone HTML blob — old prototype | DELETE_CANDIDATE | Not referenced by `app.py`. No active call site. Step 13 candidate. Confirmed by Step 1 M-04. |

**True production UI:** `ui/jansa-connected.html` + `ui/jansa/*.jsx` + `ui/jansa/data_bridge.js` — served directly by Flask/PyWebView, no build step required.

**Legacy UI:** `ui/src/`, `ui/index.html`, `ui/vite.config.js`, `ui/package.json`, `ui/package-lock.json` — old Vite-based React setup, superseded.

**Dead/unknown UI:** `JANSA Dashboard - Standalone.html` (root), `ui/dist/` (stale build), `codex prompts/facelift/prototype/JANSA Dashboard.html` (AI prototype).

---

## 6. Scripts Inventory

### Operational

| Path | Purpose | Label |
|---|---|---|
| `scripts/repo_health_check.py` | Step 1 output — ongoing repo health audit tool | ACTIVE |
| `scripts/bootstrap_run_zero.py` | Bootstraps Run 0 in run_memory.db | ACTIVE |
| `scripts/bootstrap_report_memory.py` | Bootstraps report_memory.db with E2 confidence filter | ACTIVE |

### Diagnostics / Development Helpers

| Path | Purpose | Label |
|---|---|---|
| `scripts/_run_one_mode.py` | Runs pipeline in one mode (raw or flat) in isolation | ACTIVE_TEMPORARY | Useful for developer testing. Hardcodes `input/FLAT_GED.xlsx` (H-02). Will be obsolete after Step 7. |
| `scripts/nuke_and_rebuild_run0.py` | Emergency: drops and rebuilds Run 0 from scratch | ACTIVE_TEMPORARY | Keep for emergency use; not part of normal flow |

### Validation Harnesses (Step-specific, One-Off)

| Path | Purpose | Label |
|---|---|---|
| `scripts/parity_harness.py` | Step 5 output — ran raw vs flat parity comparison | ARCHIVE_CANDIDATE | One-time validation. PARITY_PASS recorded. Can be archived. |
| `scripts/clean_gf_diff.py` | Step 9 output — diffed GF_V0_CLEAN between modes | ARCHIVE_CANDIDATE | One-time validation. REAL_REGRESSION=0 recorded. Hardcodes `input/FLAT_GED.xlsx`. |
| `scripts/ui_parity_harness.py` | Step 11 output — UI vs query_library parity | ARCHIVE_CANDIDATE | One-time validation. REAL_DIVERGENCE=0. Hardcodes `input/FLAT_GED.xlsx`. |

### Build Artifacts

| Path | Purpose | Label |
|---|---|---|
| `scripts/__pycache__/` | Compiled `.pyc` files | GENERATED_OUTPUT | Gitignored. Physically present. |

---

## 7. Docs Inventory

### Current Truth Docs (active reference for ongoing development)

| Path | Purpose | Label |
|---|---|---|
| `docs/ARCHITECTURE.md` | System architecture overview | ACTIVE |
| `docs/DEVELOPMENT_RULES.md` | Development rules and conventions | ACTIVE |
| `docs/CLAUDE.md` | Project-specific AI instruction file | ACTIVE |
| `docs/CODEX.md` | AI coding guidelines | ACTIVE |
| `docs/FLAT_GED_CONTRACT.md` | Canonical column contract for flat GED (v1.0, 21R/37O/23D cols) | ACTIVE |
| `docs/BACKEND_SEMANTIC_CONTRACT.md` | 8 semantic concepts + Phase 2 decisions | ACTIVE |
| `docs/FLAT_GED_ADAPTER_MAP.md` | Stage_read_flat adapter mapping (Step 4). **M-03**: §225 still says FLAT_GED must be placed at `input/` — stale sentence | ACTIVE (with stale note) |
| `docs/FLAT_GED_REPORT_COMPOSITION.md` | Composition spec: report_memory + GED enrichment rules | ACTIVE |
| `docs/QUERY_LIBRARY_SPEC.md` | Step 9c: 22-function query API spec | ACTIVE |
| `docs/UI_SOURCE_OF_TRUTH_MAP.md` | Step 10: Maps every UI element to its data source | ACTIVE |
| `docs/UI_RUNTIME_ARCHITECTURE.md` | UI runtime architecture | ACTIVE |
| `docs/CLEAN_BASE_REPO_HEALTH_AUDIT.md` | Step 1 output of CLEAN BASE plan | ACTIVE |

### Migration History / Validation Records (useful but not living truth)

| Path | Purpose | Label |
|---|---|---|
| `docs/GED_ENTRY_AUDIT.md` | Step 3: Gap matrix between raw GED and flat GED | ARCHIVE_CANDIDATE |
| `docs/REPORTS_INGESTION_AUDIT.md` | Step 6: Consultant report ingestion audit | ARCHIVE_CANDIDATE |
| `docs/STEP8_IMPLEMENTATION_NOTES.md` | Step 8 implementation notes (written during coding) | ARCHIVE_CANDIDATE |
| `docs/CLEAN_GF_DIFF_SUMMARY.md` | Step 9: GF diff summary (REAL_REGRESSION=0) | ARCHIVE_CANDIDATE |
| `docs/UI_PARITY_SUMMARY.md` | Step 11: UI parity results (REAL_DIVERGENCE=0) | ARCHIVE_CANDIDATE |
| `docs/VALIDATION_BASELINE.md` | Early baseline validation doc | ARCHIVE_CANDIDATE |
| `docs/JANSA_PARITY_MASTER_PLAN.md` | Parity master plan (completed) | ARCHIVE_CANDIDATE |
| `docs/JANSA_PARITY_STEP_02_FOCUS.md` | Parity step 2 (completed) | ARCHIVE_CANDIDATE |
| `docs/JANSA_PARITY_STEP_03_OVERVIEW.md` | Parity step 3 (completed) | ARCHIVE_CANDIDATE |
| `docs/JANSA_PARITY_STEP_04_CONSULTANTS_LIST.md` | Parity step 4 (completed) | ARCHIVE_CANDIDATE |
| `docs/JANSA_PARITY_STEP_05_FICHE.md` | Parity step 5 (completed) | ARCHIVE_CANDIDATE |
| `docs/JANSA_PARITY_STEP_06_DRILLDOWNS.md` | Parity step 6 (completed) | ARCHIVE_CANDIDATE |
| `docs/JANSA_PARITY_STEP_07_EXPORTS.md` | Parity step 7 (ends mid-list — possible truncation, L-01 from Step 1) | ARCHIVE_CANDIDATE |
| `docs/JANSA_PARITY_STEP_09_RUNS.md` | Parity step 9 (completed) | ARCHIVE_CANDIDATE |
| `docs/JANSA_PARITY_STEP_10_EXECUTER.md` | Parity step 10 (completed) | ARCHIVE_CANDIDATE |
| `docs/JANSA_PARITY_STEP_11_UTILITIES.md` | Parity step 11 (completed) | ARCHIVE_CANDIDATE |
| `docs/JANSA_FINAL_AUDIT.md` | Final parity audit (completed) | ARCHIVE_CANDIDATE |
| `docs/Step12corrections.md` | Patch corrections for parity step 12 | ARCHIVE_CANDIDATE |

### Conflicting/Stale Docs

| Path | Issue | Label |
|---|---|---|
| `docs/FLAT_GED_ADAPTER_MAP.md` §225 | States FLAT_GED must be placed at `input/` — contradicts Step 4 Clean IO Contract | ACTIVE (with stale sentence — fix in Step 3) |

### Unknown

| Path | Purpose | Label |
|---|---|---|
| `docs/UI_FACELIFT_STYLE_GUIDE.md` | UI facelift style guide — design tokens and visual spec from facelift campaign | LEGACY_REFERENCE | Not active runtime truth. Keep for reference if facelift resumes. (Eid decision 2026-04-26) |

---

## 8. Input / Data / Generated Artifacts

### input/

| Path | Classification | Label | Notes |
|---|---|---|---|
| `input/GED_export.xlsx` | Raw GED export — primary user input | ACTIVE | 3.9 MB. Committed intentionally. Step 4 target input. |
| `input/Grandfichier_v3.xlsx` | Grand Fichier source — user input | ACTIVE | 4.5 MB. Committed intentionally. |
| `input/Mapping.xlsx` | Consultant mapping reference | ACTIVE | 11 KB. |
| `input/consultant_reports/` | PDF reports (Socotec, BET Terrell, AVLS, LeSommer…) | ACTIVE | ~100+ PDFs. Gitignored per Step 1 I-02. User-provided inputs. |
| `input/FLAT_GED.xlsx` | Manual FLAT_GED placement location (gitignored) | ACTIVE_TEMPORARY | **H-01**: This is where `paths.py` currently points. Step 7 will move this to `output/intermediate/` and auto-generate it. |

### data/

| Path | Classification | Label | Notes |
|---|---|---|---|
| `data/run_memory.db` | Run artifact registry (SQLite) | ACTIVE_PROTECTED | Gitignored. Contains Run 0 and all run artifacts. |
| `data/report_memory.db` | Consultant report memory (SQLite, 1,245 active rows) | ACTIVE_PROTECTED | Gitignored. Repaired in Step 8. |
| `data/report_memory.db.malformed_bak` | Backup of the malformed DB from before Step 8 repair | DELETE_CANDIDATE | No longer needed. Safe to delete after Step 15 validation. |

### output/ (gitignored, physically present on disk)

| Path | Classification | Label | Notes |
|---|---|---|---|
| `output/GF_V0_CLEAN.xlsx` | Primary pipeline output | GENERATED_OUTPUT | Gitignored. Regenerated each run. |
| `output/GF_TEAM_VERSION.xlsx` | Team GF export artifact | ACTIVE_PROTECTED | Gitignored. Referenced by `export_team_version()`. Critical product output. |
| `output/parity_report.xlsx` | Step 5 parity report | GENERATED_OUTPUT | Gitignored. Historical validation artifact. |
| `output/clean_gf_diff_report.xlsx` | Step 9 diff report | GENERATED_OUTPUT | Gitignored. Historical validation artifact. |
| `output/ui_parity_report.xlsx` | Step 11 UI parity report | GENERATED_OUTPUT | Gitignored. Historical validation artifact. |
| `output/intermediate/` | Planned location for generated FLAT_GED (Step 7) | GENERATED_OUTPUT | Does not yet exist. Step 7 will create this. |

### runs/ (gitignored)

| Path | Classification | Label | Notes |
|---|---|---|---|
| `runs/run_0000/` | Run 0 baseline artifacts | ACTIVE_PROTECTED | Gitignored. Contains immutable baseline artifacts including `report_memory.db` snapshot used in Step 8 repair. |

---

## 9. Protected Assets

The following assets are classified `ACTIVE_PROTECTED` and must not be accidentally removed, renamed, or modified outside their designated step:

| Asset | Why Protected |
|---|---|
| `src/team_version_builder.py` | Implements `build_team_version()` — the team GF export builder |
| `src/pipeline/stages/stage_finalize_run.py` | Registers `GF_TEAM_VERSION` artifact in run_memory |
| `src/pipeline/paths.py → OUTPUT_GF_TEAM_VERSION` | Path constant for the team export file |
| `app.py → export_team_version()` | UI API method that finds GF_TEAM_VERSION artifact and copies it with a date-stamped name |
| `output/GF_TEAM_VERSION.xlsx` | The actual team export file (gitignored, runtime output) |
| `src/flat_ged/` (entire folder) | Frozen builder snapshot. Verified correct. Business logic must not be modified. |
| `src/flat_ged/VERSION.txt` + `src/flat_ged/BUILD_SOURCE.md` | Freeze contract documentation |
| `src/report_memory.py` | Persistent consultant report memory system |
| `src/run_memory.py` | Persistent pipeline run artifact registry |
| `data/run_memory.db` | Run artifact registry database |
| `data/report_memory.db` | Consultant report memory database (1,245 active rows) |
| `src/effective_responses.py` | Effective response builder — rewritten in Step 8, must not regress |
| `src/pipeline/stages/stage_report_memory.py` | Upserts effective responses — repaired in Step 8/9 |
| `ui/jansa-connected.html` | Production UI entry point |
| `ui/jansa/` (all 9 files) | Production UI component library |
| `runs/run_0000/` | Baseline run artifacts (immutable) |

---

## 10. Cleanup Candidates

The following items are proposed for future cleanup. **Do not act on this table now — Step 13/14 only.**

| Path | Proposed Action | Risk | Timing |
|---|---|---|---|
| `.claude/worktrees/` (6 stale worktrees) | Delete entire folder — stale Cowork git worktrees | Low (not tracked by git; just disk space + scan noise) | Step 14 |
| `JANSA Dashboard - Standalone.html` (root) | Delete (1.7 MB legacy prototype) | Low (no active call site) | Step 14 |
| `package-lock.json` (root) | Delete (stale root-level npm lock) | Low (active one is in `ui/`) | Step 14 |
| `codex prompts/` (entire folder) | Delete (AI prompt scratch files, prototypes) | Low (not part of product) | Step 14 |
| `src/reporting/bet_report_merger.py` | Move to `docs/archive/` | Low (dead code, import already commented "DO NOT RESTORE") | Step 13/14 |
| `docs/archive/` (12 JANSA parity step docs) | Move all `JANSA_PARITY_STEP_*` docs to `docs/archive/` | Low (historical only) | Step 14 |
| `FLAT_GED_INTEGRATION_EXECUTION_PLAN.md` (root) | Move to `docs/archive/` | Low (v1 plan, superseded by v2) | Step 14 |
| `FLAT_GED_INTEGRATION_EXECUTION_PLAN_v2.md` (root) | Move to `docs/archive/` | Low (completed plan) | Step 14 |
| `GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md` (root) | Move to `docs/archive/` (superseded by new docs) | Low | Step 14 |
| `data/report_memory.db.malformed_bak` | Delete | None | Step 14 |
| `ui/src/` (legacy Vite app) | Archive or delete (superseded by ui/jansa/) | Low | Step 14 |
| `scripts/parity_harness.py`, `scripts/clean_gf_diff.py`, `scripts/ui_parity_harness.py` | Archive (one-off validation harnesses; steps complete) | Low | Step 14 |

---

## 11. Step 3 Inputs

Step 3 (Architecture Truth Reset) should update the following first:

1. **`README.md`** — Likely still describes old raw-GED-first architecture. Needs to reflect flat GED as the production path and `input/` vs `output/intermediate/` distinction.

2. **`docs/ARCHITECTURE.md`** — Must be updated to say:
   - User input = `input/GED_export.xlsx` + `input/Grandfichier_v3.xlsx` + `input/consultant_reports/`
   - Flat GED = internal intermediate artifact (currently in `input/`, Step 7 will move to `output/intermediate/`)
   - Backend consumes Flat GED (not raw GED directly in production path)
   - Report memory enriches effective responses
   - GF_V0_CLEAN = reconstructed output
   - GF_TEAM_VERSION = protected team export
   - UI = presentation layer (PyWebView + jansa/)

3. **`docs/FLAT_GED_ADAPTER_MAP.md` §225** — Remove/replace the stale sentence that says `FLAT_GED.xlsx must be placed at input/FLAT_GED.xlsx`.

4. **New docs to create in Step 3:**
   - `docs/CLEAN_INPUT_OUTPUT_TARGET.md` — target IO contract
   - `docs/RUNTIME_SOURCE_OF_TRUTH.md` — which file is the runtime authority for each concern

5. **Root-level planning docs** — `FLAT_GED_INTEGRATION_EXECUTION_PLAN.md`, `FLAT_GED_INTEGRATION_EXECUTION_PLAN_v2.md`, `GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md` are archive candidates but should not be moved until Step 14. Step 3 should just reference them as historical.

6. **`api_server.py`** — Clarify whether this file should exist (Step 3 or Step 5 deliverable). Currently absent.

---

## Appendix A: Notable Structural Findings

### A1 — `.claude/worktrees/` — 6 stale git worktrees

The `.claude/worktrees/` directory contains 6 git worktrees created by Cowork during previous sessions:
- `objective-kilby-52554c`
- `dazzling-ardinghelli-6679ce`
- `silly-agnesi-77b86d`
- `blissful-hellman-c7e157`
- `exciting-nobel-377a41`
- `interesting-murdock-d39963`

These are not tracked by git. They duplicate the entire repo tree (source + input xlsx files) 6 times. They create significant scan noise (file tools pick them up alongside the real repo). They should be deleted via `git worktree remove` before Step 14. No risk to production.

### A2 — `api_server.py` — absent but required

The CLEAN BASE plan spec lists `api_server.py` as a Runtime Entry Point to classify. The file does not exist anywhere in the repo. Needs Eid decision: is this a future file (Step 6), or has it been merged into `app.py`?

### A3 — `FLAT_GED_MODE` default is still `"raw"`

`src/pipeline/paths.py` line 39: `FLAT_GED_MODE = "raw"`. This means the default pipeline run uses the old raw GED path, not the flat adapter. Steps 6/7 will flip this to `"flat"` as the default. This is expected and intentional at this stage.

### A4 — `data_loader.py` still calls raw-rebuild functions

Per Step 1 M-05 analysis and the Step 10 source-of-truth map: `src/reporting/data_loader.py` still calls `read_ged()`, `normalize_docs()`, `normalize_responses()`, `VersionEngine()` directly. This is a known Step 12 target. The UI currently works but rebuilds the full raw GED on every load. This is why the UI sees "huge response rows".

### A5 — `codex prompts/facelift/prototype/` is a shadow UI

The `codex prompts/facelift/prototype/` folder contains a full set of `.jsx` files mirroring `ui/jansa/` (overview, consultants, shell, fiche_base, fiche_page, tokens). These are AI-generated prototypes used during the facelift design phase — not part of the product runtime. DELETE_CANDIDATE for Step 14.

---

*This document was produced by Cowork file-tool scan on 2026-04-26. No files were created, moved, or deleted during this step.*
