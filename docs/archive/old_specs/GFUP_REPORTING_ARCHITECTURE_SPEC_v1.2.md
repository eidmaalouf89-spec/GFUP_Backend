# GFUP Reporting - Architecture Specification

**Version:** 1.2  
**Date:** 2026-04-15  
**Author:** GEMO/MOEX - Eid Maalouf  
**Project:** P17&CO Tranche 2  
**Status:** Design phase - no code exists yet for reporting/UI layers  

**Revision 1.2 notes:**  
- Fixed: reporting data source is now run-centric (artifact registry), not input/-centric  
- Fixed: pipeline execution uses `run_pipeline_controlled()`, not raw `run_pipeline()`  
- Fixed: historical/cross-run reporting states reproducibility limits explicitly  
- Fixed: all new modules marked as TO BE BUILT  
- Fixed: orchestrator behavior (GF inheritance, FULL without reports) documented accurately  
- Fixed: historical fiche wording now matches real GED provenance rules  
- Fixed: async pipeline API no longer promises a fake predicted run number  
- Fixed: run terminology is consistent (`current run`, `latest run`, `selected run`)  
- Fixed: degraded reporting behavior is specified when GED provenance cannot be verified  
- Fixed: the remaining critical encoding issues in the corrected sections  

---

## 1. Executive Summary

This document specifies the architecture of the GFUP Reporting tool — a desktop application that combines the existing GF Updater V3 pipeline with a visual reporting and dashboard interface. The tool is delivered as a single Windows `.exe` and serves one user on one PC for one project.

The tool provides two core capabilities:

1. **Pipeline execution** - Run the GED to GF reconstruction pipeline (existing `main.py` logic) with a visual interface replacing the CLI
2. **Reporting and dashboard** - Visual reporting on VISA workflow status, consultant response tracking, and contractor document submission quality

---

## 2. Constraints & Ground Rules

### 2.1 Deployment model
- Single Windows `.exe` built with PyInstaller
- One user, one PC, one project (P17&CO Tranche 2)
- No server, no network, no multi-user
- All data is local files + SQLite databases

### 2.2 Data access model
- **Run-centric, not input-centric.** Reporting reads data from a selected run's registered artifacts via `run_memory.db`, NOT by re-reading raw files in `input/`. This guarantees that dashboards and fiches are reproducible: even if `input/GED_export.xlsx` changes on disk, the reporting view for Run N still shows Run N's truth.
- `run_memory.db` is the artifact registry. Each completed run has a `FINAL_GF` artifact, plus discrepancy reports, anomaly reports, and debug outputs - all copied into `runs/run_NNNN/` and registered with file paths and hashes.
- `report_memory.db` provides persistent consultant response truth across runs.
- `input/` folder is only used by the pipeline execution page (to detect which files are available for the next run). Reporting pages never read from `input/` directly.
- **Reproducibility limit for historical runs:** The backend registers output artifacts per run but does NOT currently snapshot the raw GED/GF input files as run artifacts. It stores input provenance (filename, hash, path) in `run_inputs`, but does not copy the source files into `runs/run_NNNN/`. Full fiche recomputation is only possible for runs whose GED source file is still available at the recorded path and still matches the stored hash. If that provenance check fails, the reporting layer must fall back to artifact-only and summary-level reporting. Cross-run trending is limited to what `summary_json` captures (see section 10.2).

### 2.3 What the backend already provides
The existing `GFUP_Backend` codebase (frozen, stable) provides:
- Full pipeline: GED read, normalize, version engine, workflow engine, routing, GF reconstruction, reconciliation, discrepancy reports, anomaly reports, consultant integration
- Run memory: SQLite DB tracking every pipeline execution, artifacts, lineage, stale propagation
- Report memory: SQLite DB persisting consultant report responses across runs
- Run explorer: service layer for listing/summarizing/comparing/exporting runs (`src/run_explorer.py`)
- Controlled execution: `run_pipeline_controlled()` in `src/run_orchestrator.py` — the ONLY valid production entrypoint. Handles input validation, mode enforcement, inherited GF resolution, and error handling.
- Four execution modes: `GED_ONLY`, `GED_GF`, `GED_REPORT`, `FULL` (defined in `src/run_orchestrator.py:23-26`)

**Orchestrator behavior notes (must be reflected accurately in UI):**
- `current run` means the run marked current in `run_memory.db`. `selected run` means the run currently displayed in the reporting UI. On app launch, the selected run defaults to the latest COMPLETED non-stale run.
- When GF is not provided, the orchestrator resolves one from run history: latest COMPLETED non-stale run with a `FINAL_GF` artifact, falling back to Run 0. The UI must show this inheritance to the user.
- `GED_ONLY` is not a pure no-GF execution path. In practice it is GED execution with an inherited GF baseline when GF is not explicitly provided.
- `FULL` mode without `reports_dir` warns and continues (consultant ingestion is skipped, not blocked).
- `GED_REPORT` mode without `reports_dir` fails validation.
- `GF_REPORT` mode is not implemented in the current backend and is out of scope for V1.
- `REPORT_ONLY` mode does not exist and is not supported - the consultant matching path depends on a fresh GED-derived document universe.

**Per-run artifact inventory** (registered in `run_artifacts` table):
- `FINAL_GF` — the reconstructed GF workbook (primary reporting source)
- `DISCREPANCY_REPORT`, `DISCREPANCY_REVIEW_REQUIRED` — GED vs GF comparison
- `ANOMALY_REPORT` — per-contractor anomaly flags
- `INSERT_LOG` — newly inserted rows
- `NEW_SUBMITTAL_ANALYSIS` — new doc classification
- `RECONCILIATION_LOG` — fuzzy matching results
- `MISSING_IN_GED_*`, `MISSING_IN_GF_*` — diagnosis reports
- `CONSULTANT_REPORTS`, `CONSULTANT_MATCH_REPORT` — consultant integration output
- `GF_TEAM_VERSION`, `CONSULTANT_ENRICHED_STAGE1/2` — enriched GF variants
- `SUSPICIOUS_ROWS_REPORT` — quality flags
- `REPORT_MEMORY_DB` — snapshot of report_memory.db at run time
- Debug artifacts: routing, exclusion, reconciliation summaries, etc.

**Per-run summary data** (stored in `runs.summary_json`):
```json
{
  "docs_total": int,
  "responses_total": int,
  "final_gf_rows": int,
  "discrepancies_count": int,
  "artifacts_registered_count": int,
  "consultant_report_memory_rows_loaded": int,
  "run_mode": str,
  "input_files": {ged, gf, mapping, ...}
}
```

### 2.4 What the backend does NOT provide (and the reporting tool must compute)
- Aggregated KPIs (totals, percentages, trends over time)
- Per-consultant fiche data structures
- Per-contractor fiche data structures
- Monthly time-series (non-cumulative snapshots)
- Cross-run trend analysis
- Export-ready fiche workbooks

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    PyInstaller .exe bundle                        │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  PyWebView native window                                   │  │
│  │  ┌──────────────────────────────────────────────────────┐  │  │
│  │  │  React app (Vite build → static HTML/JS/CSS)         │  │  │
│  │  │  ┌──────────┬──────────┬──────────┬───────────────┐  │  │  │
│  │  │  │Dashboard │Consultant│Contractor│ Run Pipeline   │  │  │  │
│  │  │  │          │ Fiches   │ Fiches   │               │  │  │  │
│  │  │  ├──────────┼──────────┼──────────┼───────────────┤  │  │  │
│  │  │  │ Run      │ Settings │ Per-Lot  │ Export        │  │  │  │
│  │  │  │ Explorer │          │ Drilldown│ Engine        │  │  │  │
│  │  │  └──────────┴──────────┴──────────┴───────────────┘  │  │  │
│  │  └───────────────────────┬──────────────────────────────┘  │  │
│  │                          │ JS Bridge                        │  │
│  │                          │ window.pywebview.api.*            │  │
│  │  ┌───────────────────────┴──────────────────────────────┐  │  │
│  │  │  Python API layer (app.py)                           │  │  │
│  │  │  ┌────────────┬────────────────┬──────────────────┐  │  │  │
│  │  │  │ Reporting  │ Pipeline       │ Run Explorer     │  │  │  │
│  │  │  │ Engine     │ Controller     │ (existing)       │  │  │  │
│  │  │  └─────┬──────┴───────┬────────┴─────────┬────────┘  │  │  │
│  │  └────────┼──────────────┼──────────────────┼───────────┘  │  │
│  └───────────┼──────────────┼──────────────────┼──────────────┘  │
│              │              │                  │                  │
│  ┌───────────┴──────────────┴──────────────────┴──────────────┐  │
│  │  Persistent data layer (disk)                              │  │
│  │  ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌───────────┐ │  │
│  │  │run_memory│ │report_memory │ │runs/     │ │input/     │ │  │
│  │  │.db       │ │.db           │ │run_NNNN/ │ │GED+GF+Map│ │  │
│  │  └──────────┘ └──────────────┘ └──────────┘ └───────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.1 Technology stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Desktop shell | PyWebView 5.x | Native window, no browser needed, Python-native |
| Frontend | React 18 + Vite | Component-based, fast builds, known from JANSA v4.2 |
| Charts | Recharts | React-native charting library, supports combo charts |
| Styling | Tailwind CSS | Utility-first, fast prototyping |
| Python-JS bridge | PyWebView JS API | `window.pywebview.api.*` — no HTTP server needed |
| Backend logic | Python 3.11+ | Existing codebase, no changes to frozen pipeline |
| Data storage | SQLite (existing) | run_memory.db, report_memory.db |
| Bundling | PyInstaller | Single `.exe`, includes Python + React dist + all deps |

### 3.2 Communication model

PyWebView exposes Python class methods directly to JavaScript. The React frontend calls them as async functions:

```javascript
// React side
const data = await window.pywebview.api.get_dashboard_data();
```

```python
# Python side (app.py)
class Api:
    def get_dashboard_data(self):
        return {...}  # returns dict, auto-serialized to JSON
```

There is no HTTP server, no port binding, no CORS. This is simpler and more reliable than FastAPI for single-user desktop apps.

---

## 4. Reporting Scope — Two Axes

The reporting tool serves two distinct reporting axes, each with its own set of fiches:

### 4.1 Axis 1: Consultant reporting (VISA tracking)

**Purpose:** Track how fast and thoroughly each consultant (BET/MOE) reviews documents submitted by contractors.

**Who are the consultants?** They are the approvers in the GED workflow — the columns in the GF header Row 8. Detected dynamically from the GED export, not hardcoded. The Arboretum template shows ~18 consultant fiche sheets (VISA ARCHI, VISA CT, VISA BET STR, VISA BET FLUIDES, VISA MOEX GEMO, VISA BET ACOUS AVLS, etc.).

**What each consultant fiche shows:**

| Block | Content | Data source |
|-------|---------|-------------|
| Header | Consultant name, mission, total docs called, response rate | Selected run context, using verified GED-derived response data when available; otherwise degraded artifact-only fallback |
| Block 1 - Monthly table | Per-month snapshot: total docs, VSO count/%, VAO count/%, REF count/%, HM count/%, open count/% | Selected run context, using verified GED-derived response data grouped by month of `date_answered` when available; otherwise degraded fallback |
| Block 2 — Combo chart | Stacked bars (VSO/VAO/REF/HM/Open) + total line overlay, one bar per month | Same data as Block 1 |
| Block 3 - Per-lot table | One row per LOT, columns: total docs, VSO, VAO, REF, HM, Open, % approved, % refused | Selected run context, using verified GED-derived response data grouped by `lot_normalized` when available; otherwise degraded fallback |
| Infographic | Key stats: avg response time, most-refused lot, most-delayed lot | Computed from the selected run context |

**Consultant list detection rule:** Read Row 8 of each GF sheet (approbateur names) to build the full list. The `Mapping.xlsx` provides canonical names. Exclude "Exception List" entries.

### 4.2 Axis 2: Contractor reporting (document submission quality)

**Purpose:** Track how each contractor (entreprise) submits documents — volume, quality, revision cycles, and SAS refusal rates.

**Who are the contractors?** They are the EMETTEUR values in the GED, mapped to canonical names via Mapping.xlsx and routing logic. Each GF sheet corresponds to one LOT which is assigned to one contractor. The Arboretum template shows ~25 "Bilan Docs" sheets (03A GCC, 004 SNA, 031 SBE, 041 LFR, 042 BALAS, 051 OTIS, 061 BENTIN, etc.).

**What each contractor fiche shows:**

| Block | Content | Data source |
|-------|---------|-------------|
| Header | Contractor name, LOTs covered, total docs submitted, current indice distribution | Selected run context, using verified GED-derived document data when available; otherwise degraded artifact-only fallback |
| Block 1 - Submission timeline | Per-month: new submissions, re-submissions (indice B+), SAS REF count, SAS VAO count | Selected run context, using verified GED-derived document data plus SAS lookup when available |
| Block 2 - VISA result chart | Stacked bars per month: VISA GLOBAL results (VSO/VAO/REF/SAS REF/Open) | Selected run context, using verified GED/workflow-derived data when available; otherwise degraded fallback |
| Block 3 - Per-lot document table | One row per document or per indice chain: numero, indice, titre, SAS result, VISA GLOBAL, date submitted, date visa, responsible party | Selected run context, using current-document rows for this contractor when verified GED data is available; otherwise degraded fallback |
| Block 4 - Quality metrics | SAS refusal rate, avg revision cycles, avg time to visa, "documents a reprendre" count | Computed from the selected run context, with degraded fallback if GED provenance is unavailable |

**Contractor list detection rule:** Built from GF sheet names. Each sheet name contains the contractor code and name (e.g., "LOT 41-CVC-AXIMA" → contractor AXIMA, lot 41). The routing module already parses this.

### 4.3 Cross-cutting views

In addition to individual fiches, the dashboard provides project-wide views:

| View | Content |
|------|---------|
| Dashboard (home) | Project-wide KPIs: total docs, % approved, % pending, % refused, docs by building (AU/BX/HO/IN), trend over time |
| BILAN VISA MOE | Aggregated consultant response across ALL consultants (the Arboretum "BILAN VISA MOE" sheet) |
| REV DOC ENT | Aggregated contractor submission quality across ALL contractors (the Arboretum "REV DOC ENT" sheet) |
| Docs "A reprendre" SAS | Documents currently stuck at SAS REF — requires contractor action |

---

## 5. Folder Structure

All new code lives within the existing `GFUP_Backend` repository:

```
GFUP_Backend/
├── main.py                         # EXISTING — pipeline orchestrator (frozen)
├── app.py                          # TO BE BUILT — PyWebView launcher + API bridge
│
├── src/                            # EXISTING — pipeline modules (frozen)
│   ├── read_raw.py                 # EXISTING
│   ├── normalize.py                # EXISTING
│   ├── version_engine.py           # EXISTING
│   ├── workflow_engine.py          # EXISTING
│   ├── routing.py                  # EXISTING
│   ├── writer.py                   # EXISTING
│   ├── reconciliation_engine.py    # EXISTING
│   ├── effective_responses.py      # EXISTING
│   ├── report_memory.py            # EXISTING
│   ├── run_memory.py               # EXISTING
│   ├── run_orchestrator.py         # EXISTING — pipeline entrypoint for UI
│   ├── run_explorer.py             # EXISTING — run history service layer
│   ├── config_loader.py            # EXISTING
│   ├── consultant_matcher.py       # EXISTING
│   ├── consultant_integration.py   # EXISTING
│   ├── consultant_gf_writer.py     # EXISTING
│   ├── consultant_match_report.py  # EXISTING
│   ├── team_version_builder.py     # EXISTING
│   ├── debug_writer.py             # EXISTING
│   ├── consultant_ingest/          # EXISTING — BET PDF parsers
│   │
│   └── reporting/                  # TO BE BUILT — Reporting compute engine
│       ├── __init__.py
│       ├── data_loader.py          # Run-centric data access (reads artifacts, not input/)
│       ├── aggregator.py           # Project-wide KPIs and time-series
│       ├── consultant_fiche.py     # Per-consultant fiche data builder
│       ├── contractor_fiche.py     # Per-contractor fiche data builder
│       ├── lot_drilldown.py        # Per-lot detailed breakdown
│       └── export_writer.py        # Generates .xlsx fiche exports
│
├── ui/                             # TO BE BUILT — React frontend
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── src/
│   │   ├── main.jsx                # React entry point
│   │   ├── App.jsx                 # Root component with router/sidebar
│   │   ├── hooks/
│   │   │   └── usePyBridge.js      # Wrapper for window.pywebview.api
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx       # Home page with project KPIs
│   │   │   ├── ConsultantList.jsx  # List of all consultant fiches
│   │   │   ├── ConsultantFiche.jsx # Individual consultant fiche view
│   │   │   ├── ContractorList.jsx  # List of all contractor fiches
│   │   │   ├── ContractorFiche.jsx # Individual contractor fiche view
│   │   │   ├── LotDrilldown.jsx    # Per-lot document detail
│   │   │   ├── RunPipeline.jsx     # Pipeline execution page
│   │   │   ├── RunExplorer.jsx     # Run history + comparison
│   │   │   └── Settings.jsx        # App settings
│   │   └── components/
│   │       ├── Sidebar.jsx         # Navigation sidebar
│   │       ├── KPICard.jsx         # Dashboard KPI card
│   │       ├── ComboChart.jsx      # Block 2: stacked bars + line
│   │       ├── MonthlyTable.jsx    # Block 1: monthly data table
│   │       ├── StatusPills.jsx     # VISA status pill badges
│   │       ├── DocumentTable.jsx   # Block 3: per-document table
│   │       ├── PipelineProgress.jsx# Live pipeline progress bar
│   │       └── RunCard.jsx         # Run history card
│   └── dist/                       # Built output (not in git, generated by npm run build)
│
├── scripts/
│   ├── bootstrap_run_zero.py       # EXISTING
│   ├── bootstrap_report_memory.py  # EXISTING
│   └── build_exe.py                # TO BE BUILT — PyInstaller build script
│
├── data/                           # EXISTING — created at runtime
│   ├── run_memory.db
│   └── report_memory.db
│
├── runs/                           # EXISTING — run artifact storage
│   └── run_0000/
│
├── input/                          # EXISTING — pipeline inputs (used by RunPipeline page only)
│   ├── GED_export.xlsx
│   ├── Grandfichier_v3.xlsx
│   └── Mapping.xlsx
│
└── output/                         # EXISTING — pipeline outputs
```

---

## 6. Module Specifications

### 6.1 `app.py` — Application launcher & API bridge (TO BE BUILT)

**Responsibilities:**
1. Resolve base directory (PyInstaller `sys._MEIPASS` vs dev mode)
2. Initialize SQLite databases if not present
3. Create PyWebView window pointing to `ui/dist/index.html`
4. Expose the `Api` class to the JavaScript frontend
5. Manage pipeline execution in a background thread

**Path resolution logic:**
```
If frozen (PyInstaller):
    BASE_DIR = directory containing the .exe
    UI_DIR = sys._MEIPASS / "ui" / "dist"
Else (dev mode):
    BASE_DIR = __file__.parent
    UI_DIR = BASE_DIR / "ui" / "dist"
    (or dev server at http://localhost:5173 if UI_DIR/index.html missing)
```

**Thread model:**
- Main thread: PyWebView event loop (UI)
- Worker thread: Pipeline execution (spawned by `run_pipeline_async`)
- Shared state: `_pipeline_status` dict protected by `threading.Lock`

### 6.2 `src/reporting/data_loader.py` - Data access layer (TO BE BUILT)

**Responsibilities:**
- Resolve the selected run from `run_memory.db` (default: latest COMPLETED non-stale)
- Load that run's registered artifacts from `run_artifacts` table (file paths on disk)
- Read `FINAL_GF` artifact into openpyxl structures for GF sheet layout and approver detection
- Read GED export to build normalized DataFrames - **but only the GED that was used for the selected run**, located via `run_inputs` provenance (source_path + source_file_hash). If the original GED file no longer matches the stored hash, do not silently substitute another GED file. Instead, mark the context as degraded and fall back to artifact-only reporting for that run.
- Provide a cached `RunContext` object to avoid re-reading on every API call

**Why run-centric matters:** If the user drops a new GED into `input/` after Run 5 completed, the dashboard for Run 5 must still show Run 5's truth - not whatever is currently in `input/`. The reporting layer reads from the run's artifact registry, not from `input/` directly.

**Key functions:**
```python
def load_run_context(base_dir: Path, run_number: int = None) -> RunContext
    # If run_number is None: resolve latest COMPLETED non-stale run
    # Steps:
    #   1. Query run_memory.db for run record + status check
    #   2. Query run_artifacts for FINAL_GF path and verify file exists on disk
    #   3. Query run_inputs for GED provenance (path + hash)
    #   4. If GED source still exists and hash matches, read it via read_raw + normalize
    #   5. If GED source is missing or hash-mismatched, set ged_available=False in context
    #   6. Read GF artifact for sheet structure (approvers, lots, routing)
    #   7. Build and return RunContext with all loaded data

def get_gf_sheet_structure(gf_artifact_path: Path) -> dict
    # Returns: {sheet_name: {lots, contractor_code, contractor_name, approvers}}
    # Reuses src.routing.read_all_gf_sheet_structures

def get_available_runs(base_dir: Path) -> list[dict]
    # Returns list of all runs with status, for run selector dropdown
```

**RunContext object:**
```python
@dataclass
class RunContext:
    run_number: int
    run_status: str                    # COMPLETED / FAILED
    run_date: str                      # completed_at ISO timestamp
    summary_json: dict                 # parsed from runs.summary_json
    gf_artifact_path: Path             # FINAL_GF file on disk
    ged_available: bool                # True if the recorded GED source is readable and hash-verified
    degraded_mode: bool                # True when reporting must fall back to artifact-only data
    docs_df: pd.DataFrame | None       # normalized GED docs (None if ged_available=False)
    responses_df: pd.DataFrame | None  # normalized GED responses
    approver_names: list[str] | None   # from GED header
    gf_sheets: dict                    # {sheet_name: {lots, contractor, approvers}}
    artifact_paths: dict               # {artifact_type: file_path}
    warnings: list[str]                # provenance or artifact warnings for UI display
```

### 6.3 `src/reporting/aggregator.py` — Project-wide KPIs (TO BE BUILT)

**Responsibilities:**
- Compute project-wide statistics from the loaded run context
- Build time-series data for dashboard charts

**Key functions:**
```python
def compute_project_kpis(ctx: RunContext) -> dict
    # Returns: {
    #   total_docs_current: int,          # dernier indice only
    #   total_docs_all_indices: int,
    #   by_visa_global: {VSO: n, VAO: n, REF: n, SAS_REF: n, open: n},
    #   by_visa_global_pct: {VSO: 0.xx, ...},
    #   by_building: {AU: n, BX: n, HO: n, IN: n},
    #   by_responsible: {CONTRACTOR: n, MOEX: n, consultant_X: n, ...},
    #   avg_days_to_visa: float,
    #   docs_pending_sas: int,
    #   docs_sas_ref_active: int,
    #   total_contractors: int,
    #   total_consultants: int,
    #   total_lots: int,
    #   run_number: int,
    #   run_date: str,
    # }

def compute_monthly_timeseries(ctx: RunContext) -> list[dict]
    # Returns: [{month: "2025-01", total: n, vso: n, vao: n, ref: n, open: n}, ...]
    # Non-cumulative: each month is a snapshot of new activity in that month

def compute_consultant_summary(ctx: RunContext) -> list[dict]
    # Returns: [{name: str, docs_called: n, docs_answered: n, response_rate: 0.xx,
    #            avg_response_days: float, vso: n, vao: n, ref: n}, ...]

def compute_contractor_summary(ctx: RunContext) -> list[dict]
    # Returns: [{name: str, lots: [str], total_submitted: n,
    #            sas_ref_rate: 0.xx, avg_revision_cycles: float,
    #            visa_vso: n, visa_vao: n, visa_ref: n, visa_open: n}, ...]
```

### 6.4 `src/reporting/consultant_fiche.py` — Per-consultant fiche builder (TO BE BUILT)

**Responsibilities:**
- Build the complete data structure for one consultant fiche
- Produces Block 1 (monthly table), Block 2 (chart data), Block 3 (per-lot table)

**Key function:**
```python
def build_consultant_fiche(ctx: RunContext, consultant_name: str) -> dict
    # Returns: {
    #   consultant_name: str,
    #   mission: str,                     # e.g., "BET Acoustique"
    #   total_docs_called: int,
    #   total_docs_answered: int,
    #   response_rate: float,
    #   avg_response_days: float,
    #
    #   block1_monthly: [
    #     {month: "2025-01", total: n, vso: n, vso_pct: 0.xx,
    #      vao: n, vao_pct: 0.xx, ref: n, ref_pct: 0.xx,
    #      hm: n, hm_pct: 0.xx, open: n, open_pct: 0.xx},
    #     ...
    #   ],
    #
    #   block2_chart: [
    #     {month: "2025-01", vso: n, vao: n, ref: n, hm: n, open: n, total: n},
    #     ...
    #   ],
    #
    #   block3_per_lot: [
    #     {lot: str, sheet_name: str, total: n,
    #      vso: n, vao: n, ref: n, hm: n, open: n,
    #      pct_approved: 0.xx, pct_refused: 0.xx},
    #     ...
    #   ],
    #
    #   infographic: {
    #     most_refused_lot: str,
    #     most_delayed_lot: str,
    #     fastest_response_lot: str,
    #   }
    # }
```

### 6.5 `src/reporting/contractor_fiche.py` — Per-contractor fiche builder (TO BE BUILT)

**Responsibilities:**
- Build the complete data structure for one contractor fiche
- Covers document submission volume, SAS quality, VISA results, revision cycles

**Key function:**
```python
def build_contractor_fiche(ctx: RunContext, contractor_code: str) -> dict
    # Returns: {
    #   contractor_name: str,             # e.g., "AXIMA"
    #   contractor_code: str,             # e.g., "AXI"
    #   lots: [str],                      # e.g., ["41"]
    #   buildings: [str],                 # e.g., ["I", "B", "A", "H"]
    #   gf_sheets: [str],                 # e.g., ["LOT 41-CVC-AXIMA"]
    #   total_submitted: int,             # all indices
    #   total_current: int,               # dernier indice only
    #
    #   block1_submission_timeline: [
    #     {month: "2025-01", new_submissions: n, re_submissions: n,
    #      sas_ref: n, sas_vao: n, sas_pending: n},
    #     ...
    #   ],
    #
    #   block2_visa_chart: [
    #     {month: "2025-01", vso: n, vao: n, ref: n, sas_ref: n, open: n, total: n},
    #     ...
    #   ],
    #
    #   block3_document_table: [
    #     {numero: str, indice: str, titre: str, type_doc: str,
    #      sas_result: str, visa_global: str, date_submitted: str,
    #      date_visa: str, responsible_party: str, status: str},
    #     ...
    #   ],
    #
    #   block4_quality: {
    #     sas_refusal_rate: float,         # % of submissions that got SAS REF
    #     avg_revision_cycles: float,      # avg number of indices per document
    #     avg_days_to_visa: float,         # from submission to VISA GLOBAL
    #     docs_a_reprendre: int,           # currently refused, needs contractor action
    #     docs_pending_consultant: int,    # waiting for consultant response
    #     docs_pending_moex: int,          # waiting for MOEX visa chapeau
    #   }
    # }
```

### 6.6 `src/reporting/lot_drilldown.py` — Per-lot detail (TO BE BUILT)

**Responsibilities:**
- Build per-lot document-level detail for drilldown views
- Can be accessed from either a consultant fiche (clicking on a lot) or a contractor fiche

**Key function:**
```python
def build_lot_drilldown(ctx: RunContext, sheet_name: str) -> dict
    # Returns: {
    #   sheet_name: str,
    #   contractor: str,
    #   lot_numbers: [str],
    #   total_documents: int,
    #   documents: [
    #     {numero: str, indice: str, titre: str, type_doc: str,
    #      created_at: str, sas_result: str, visa_global: str,
    #      visa_date: str, responsible_party: str,
    #      consultants: {name: {status: str, date: str, comment: str}}},
    #     ...
    #   ],
    #   summary: {vso: n, vao: n, ref: n, sas_ref: n, open: n}
    # }
```

### 6.7 `src/reporting/export_writer.py` — Excel/PDF fiche export (TO BE BUILT)

**Responsibilities:**
- Generate downloadable `.xlsx` files matching the Arboretum template format
- One workbook per fiche type, or an "all-in-one" workbook

**Key functions:**
```python
def export_consultant_fiche_xlsx(fiche_data: dict, output_path: str) -> str
def export_contractor_fiche_xlsx(fiche_data: dict, output_path: str) -> str
def export_all_fiches_xlsx(all_data: dict, output_path: str) -> str
    # Produces a single workbook with all fiches as separate sheets
```

---

## 7. API Contract — `app.py` Exposed Methods

### 7.1 Application state

```python
def get_app_state(self) -> dict
    # Returns: {
    #   has_baseline: bool,              # Run 0 exists in run_memory.db?
    #   current_run: int | None,         # Default run selected at startup: latest COMPLETED non-stale run
    #   current_run_date: str | None,    # completed_at of that default selected run
    #   total_runs: int,
    #   ged_file_detected: str | None,   # Path if input/GED_export.xlsx exists
    #   gf_file_detected: str | None,    # Path if input/Grandfichier_v3.xlsx exists
    #   mapping_detected: str | None,    # Path if input/Mapping.xlsx exists
    #   reports_dir_detected: str | None,# Path if input/consultant_reports/ exists
    #   ged_verified_for_current_run: bool, # True if detected GED hash matches the default selected run's input
    #   current_run_artifact_ok: bool,   # True if FINAL_GF artifact exists on disk
    #   data_dir: str,                   # Absolute path to data/
    #   pipeline_running: bool,
    #   app_version: str,
    #   warnings: [str],                 # e.g., "GED file changed since Run 5"
    # }
```

### 7.2 Pipeline execution

```python
def run_pipeline_async(self, run_mode: str, ged_path: str = None,
                       gf_path: str = None, mapping_path: str = None,
                       reports_dir: str = None) -> dict
    # Validates inputs first via run_orchestrator.validate_run_inputs()
    # If validation fails: returns {started: False, errors: [...]}
    # If valid: spawns background thread calling run_pipeline_controlled()
    # Returns: {"started": True}
    # Raises if pipeline is already running
    #
    # IMPORTANT: never calls main.run_pipeline() directly.
    # Always delegates to src.run_orchestrator.run_pipeline_controlled().
    # The actual run_number is captured from the controlled result after the
    # worker completes. Do not promise a predicted run number up front.

def get_pipeline_status(self) -> dict
    # Polled by frontend every 500ms during pipeline execution
    # Returns: {
    #   running: bool,
    #   message: str,                    # Human-readable status
    #   error: str | None,
    #   completed_run: int | None,       # Set when pipeline finishes successfully
    #   warnings: [str],                 # e.g., "GF inherited from Run 3"
    # }
    #
    # V1 note: structured phase names and percentage progress are not emitted by
    # the backend today. The UI should treat message-based status as the baseline
    # contract unless explicit progress instrumentation is added later.

def select_file(self, file_type: str) -> str | None
    # Opens native file dialog via webview.create_file_dialog
    # file_type: "ged" | "gf" | "mapping" | "report_dir"
    # Returns selected file path or None if cancelled

def validate_inputs(self, run_mode: str, ged_path: str = None,
                    gf_path: str = None, mapping_path: str = None,
                    reports_dir: str = None) -> dict
    # Pre-validates without running. Delegates to
    # run_orchestrator.validate_run_inputs().
    # Returns: {valid: bool, errors: [str], warnings: [str]}
    # UI should call this on mode/file change to show inline validation
```

### 7.3 Dashboard data

```python
def get_dashboard_data(self) -> dict
    # Returns the full dashboard payload (project KPIs + summaries)
    # Calls aggregator.compute_project_kpis + compute_monthly_timeseries
    #        + compute_consultant_summary + compute_contractor_summary

def get_consultant_list(self) -> list[dict]
    # Returns: [{name: str, docs_called: int, response_rate: float}, ...]

def get_contractor_list(self) -> list[dict]
    # Returns: [{name: str, code: str, lots: [str], total_submitted: int}, ...]
```

### 7.4 Fiche data

```python
def get_consultant_fiche(self, consultant_name: str) -> dict
    # Returns full fiche data structure (see 6.4)

def get_contractor_fiche(self, contractor_code: str) -> dict
    # Returns full fiche data structure (see 6.5)

def get_lot_drilldown(self, sheet_name: str) -> dict
    # Returns per-lot document detail (see 6.6)
```

### 7.5 Run explorer

```python
def get_all_runs(self) -> list[dict]
    # Delegates to src.run_explorer.get_all_runs

def get_run_summary(self, run_number: int) -> dict
    # Delegates to src.run_explorer.get_run_summary

def compare_runs(self, run_a: int, run_b: int) -> dict
    # Delegates to src.run_explorer.compare_runs

def export_run_bundle(self, run_number: int) -> str
    # Delegates to src.run_explorer.export_run_bundle
    # Returns path to exported ZIP
```

### 7.6 Export

```python
def export_consultant_fiche(self, consultant_name: str) -> str
    # Generates .xlsx, returns file path

def export_contractor_fiche(self, contractor_code: str) -> str
    # Generates .xlsx, returns file path

def export_all_fiches(self) -> str
    # Generates combined workbook with all consultant + contractor fiches
    # Returns file path

def open_file_in_explorer(self, file_path: str) -> None
    # Opens the containing folder in Windows Explorer
```

### 7.7 Settings

```python
def get_settings(self) -> dict
    # Returns: {
    #   input_dir: str,
    #   output_dir: str,
    #   date_range_start: str | None,
    #   date_range_end: str | None,
    # }

def update_setting(self, key: str, value: str) -> dict
    # Updates a setting, returns new settings dict
```

---

## 8. UI Pages

### 8.1 Sidebar navigation

The sidebar is always visible and contains:
1. **Dashboard** (home icon) — project overview
2. **Consultants** (people icon) — consultant fiche list then individual fiche
3. **Entreprises** (building icon) — contractor fiche list then individual fiche
4. **Executer** (play icon) — pipeline execution
5. **Historique** (clock icon) — run explorer
6. **Parametres** (gear icon) — settings

The sidebar also shows at the bottom:
- Selected run number and date
- Pipeline status indicator (idle / running / error)

### 8.2 Dashboard page

**Top section:** 4-6 KPI cards showing:
- Total documents (dernier indice)
- % approved (VSO+VAO)
- % pending
- % refused (REF+SAS REF)
- Avg days to visa
- Active SAS REF count

**Middle section:** Combo chart - monthly visa distribution (stacked bars + total line)

**Bottom section:** Two side-by-side summary tables:
- Top 5 consultants by response rate (linked to fiche)
- Top 5 contractors by SAS refusal rate (linked to fiche)

### 8.3 Consultant list page

Table with one row per consultant:
- Name, mission, docs called, docs answered, response rate, avg days
- Click row -> navigates to consultant fiche

### 8.4 Consultant fiche page

Full page view with:
- Header: name, mission, key stats
- Block 1: Monthly table (scrollable)
- Block 2: Combo chart
- Block 3: Per-lot table with clickable lot names -> lot drilldown
- Export button → generates .xlsx

### 8.5 Contractor list page

Table with one row per contractor:
- Name, code, lots, total submitted, SAS REF rate, avg revisions
- Click row -> navigates to contractor fiche

### 8.6 Contractor fiche page

Full page view with:
- Header: name, lots, buildings, key quality stats
- Block 1: Submission timeline chart
- Block 2: VISA result chart
- Block 3: Document table (scrollable, sortable, filterable)
- Block 4: Quality metrics panel
- Export button → generates .xlsx

### 8.7 Run pipeline page

- File selectors for GED, GF, Mapping (with auto-detection from input/)
- Run mode selector (GED_ONLY / GED_GF / GED_REPORT / FULL)
- "Run" button -> starts pipeline, shows running status and the latest status message
- Live status messages during execution
- On completion -> "View results" button refreshes dashboard

### 8.8 Run explorer page

- List of all runs with status badges
- Stale runs remain visible in Run Explorer and must be clearly marked as stale
- Click run -> details panel (summary, artifact list, lineage)
- If a stale run is selected, reporting pages should show a warning badge before displaying its data
- Compare button -> side-by-side comparison
- Export bundle button -> ZIP download
### 8.9 Settings page

- Input/output directory paths (display only - resolved from BASE_DIR)
- Date range filter for reporting (optional)
- About section with version info

---

## 9. Data Flow

### 9.1 On application launch

```
1. app.py resolves BASE_DIR (PyInstaller sys._MEIPASS or __file__.parent)
2. app.py checks data/run_memory.db and data/report_memory.db exist
   (initializes empty DBs if not — but warns that bootstrap is needed)
3. PyWebView window opens, loads ui/dist/index.html
4. React App.jsx mounts, calls api.get_app_state()
5. If has_baseline=true and current_run exists:
   a. data_loader resolves the selected run from run_memory.db, defaulting to the latest COMPLETED non-stale run on first load
   b. data_loader loads that run's FINAL_GF artifact from runs/run_NNNN/
   c. data_loader verifies GED input provenance (hash check against run_inputs)
   d. If GED verified: loads GED into DataFrames for full fiche computation
   e. If GED not verified: marks ged_available=false and degraded_mode=true, then limits fiches to artifact-only and GF-derived data
   f. Dashboard renders with run-centric data
6. If has_baseline=false:
   Show setup screen: "Run 0 baseline not found. Run bootstrap_run_zero.py first."
7. If current_run exists but its FINAL_GF artifact file is missing from disk:
   Show warning: "Run N artifacts missing. Re-run pipeline or restore files."
```

### 9.2 On pipeline execution

```
1. User clicks "Run" on RunPipeline page
2. React calls api.run_pipeline_async("GED_GF", ged_path, gf_path, mapping_path)
3. Python validates inputs, spawns worker thread
4. Worker thread calls src.run_orchestrator.run_pipeline_controlled(
       run_mode, ged_path, mapping_path, gf_path, reports_dir)
   — This is the ONLY valid production entrypoint. Never call main.run_pipeline() directly.
   — The orchestrator handles: input validation, GF inheritance when not provided,
     mode-specific behavior (FULL without reports_dir warns and continues),
     proper run memory registration, and error handling.
5. React polls api.get_pipeline_status() every 500ms
6. UI shows running status and the latest available status message
7. On completion:
   a. run_pipeline_controlled returns {success, run_number, status, errors, ...}
   b. get_pipeline_status returns {running: false, completed_run: N}
   c. React clears all cached RunContext data
   d. React calls api.get_dashboard_data() to refresh from new run
   e. User sees updated dashboard
8. On failure:
   a. run_pipeline_controlled returns {success: false, errors: [...]}
   b. UI shows error messages from the errors list
   c. Run is recorded as FAILED in run_memory.db (orchestrator handles this)
```

**Important:** The UI must reflect actual orchestrator behavior:
- If user provides no GF file, show "GF will be inherited from Run N" (resolved by orchestrator)
- If user selects FULL mode without reports_dir, show warning "Consultant ingestion will be skipped"
- If user selects GED_REPORT without reports_dir, show error before execution starts

### 9.3 On fiche request

```
1. User clicks a consultant name on ConsultantList page
2. React navigates to /consultant/:name
3. ConsultantFiche.jsx calls api.get_consultant_fiche("AVLS")
4. Python checks if RunContext is cached for the selected run
   a. If cached: reuse it
   b. If not cached: data_loader.load_run_context(base_dir) builds it from
      the selected run's artifacts + verified GED source
5. consultant_fiche.build_consultant_fiche(ctx, "AVLS") computes fiche data
6. If ctx.ged_available=false:
   Response includes degraded_mode=true and a warnings list.
   The fiche shows only GF-derived and artifact-derived data
   (for example document counts per lot from FINAL_GF), while response-level
   breakdowns, response-time metrics, and GED-only fields are omitted or null.
7. Returns JSON dict, React renders Block 1 + Block 2 + Block 3
```

---

## 10. Caching & Reproducibility

### 10.1 Caching strategy

The reporting engine must avoid re-reading Excel files and re-computing DataFrames on every API call. Caching strategy:

**Level 1 - RunContext cache:** When `get_dashboard_data()` is first called, `data_loader.py` reads the selected run's artifacts, builds DataFrames, and returns a `RunContext`. This object is cached in memory for the lifetime of the app session (or until the user switches to a different run).

**Level 2 - Fiche cache:** Individual fiche results are cached after first computation. Cache key = `(run_number, fiche_type, entity_name)`.

**Cache invalidation:** When a pipeline run completes, all caches are cleared. The next API call triggers a fresh load from the new run's artifacts. Switching the selected run in the UI also clears caches.

### 10.2 Cross-run reproducibility limits

**Current state:** The backend stores per-run output artifacts (GF_V0_CLEAN, reports) and input provenance (filename, hash, path), but does NOT copy raw GED/GF input files into `runs/run_NNNN/`. This has real consequences for reporting:

| Capability | Available now? | Why |
|-----------|---------------|-----|
| Full fiche for a selected run with verified GED provenance | Yes | The GED source still exists at the recorded path and still matches the stored hash in `run_inputs` |
| Full fiche for a selected run without verified GED provenance | No | If the recorded GED file is missing or hash-mismatched, raw GED data for that run is no longer trustworthy |
| Cross-run KPI trending | Yes (limited) | `summary_json` stores docs_total, responses_total, final_gf_rows, discrepancies_count per run |
| Cross-run visa distribution trending | No | Visa breakdown (VSO/VAO/REF counts) is not in `summary_json` |
| Diff two runs | Partially | Can compare `summary_json` fields and artifact counts; cannot diff GF content unless both artifacts are on disk |

**V1 design decision:** Accept this limitation. The reporting tool computes full fiches for any selected run whose GED provenance can still be verified. If GED provenance cannot be verified for a selected run, the UI must degrade gracefully to artifact-only and summary-level reporting. Cross-run trending is limited to the fields already stored in `summary_json`.

**Future enhancement (out of scope for V1):** Extend the pipeline to snapshot raw GED + GF as artifacts per run, or enrich `summary_json` with visa distribution counts. This would enable full historical fiche recomputation and richer cross-run analysis.

---

## 11. Build & Distribution

### 11.1 Development workflow

```bash
# Terminal 1: React dev server
cd ui && npm install && npm run dev

# Terminal 2: Python app in dev mode
python app.py --dev
# PyWebView points to http://localhost:5173 instead of ui/dist/
```

### 11.2 Production build

```bash
# Step 1: Build React
cd ui && npm run build
# Outputs to ui/dist/

# Step 2: Build EXE
python scripts/build_exe.py
# Uses PyInstaller to bundle:
#   - Python runtime
#   - All src/ modules
#   - ui/dist/ static files
#   - pywebview
# Outputs: dist/GFUP_Reporting.exe
```

### 11.3 PyInstaller spec notes

```python
# Key additions to .spec file:
datas = [
    ('ui/dist', 'ui/dist'),           # React build
    ('input/Mapping.xlsx', 'input'),   # Default mapping (optional)
]
hiddenimports = [
    'openpyxl', 'pandas', 'numpy',
    'webview', 'webview.platforms.edgechromium',
    'src.reporting', 'src.reporting.data_loader',
    # ... all src modules
]
```

---

## 12. Future Considerations (Out of Scope for V1)

- PDF fiche export (V1 = .xlsx only)
- Multi-run trend analysis (comparing KPIs across runs)
- Automated periodic pipeline execution (scheduled runs)
- Email report distribution
- Print-optimized views

---

## 13. Glossary

| Term | Definition |
|------|-----------|
| GED | Gestion Electronique de Documents — AxeoBIM document platform |
| GF | GrandFichier — master VISA tracking workbook (Excel, ~36 LOT tabs) |
| VISA | Approval status: VSO, VAO, REF, HM, SUS, ANN, FAV, DEF |
| VISA GLOBAL | Final MOEX/GEMO approval status (copied, never computed) |
| SAS | Conformity gate — SAS REF = returned to submitter before workflow |
| LOT | Trade package (e.g., Lot 41 = CVC, Lot 03 = Gros Œuvre) |
| EMETTEUR | Document submitter (contractor code) |
| INDICE | Revision letter (A, B, C...) |
| NUMERO | 6-digit document identifier (most stable matching key) |
| BET | Bureau d'Études Techniques — technical consultant |
| MOEX/GEMO | Maître d'Œuvre d'Exécution — execution architect (the user's role) |
| MOX | Architecte (Hardel + Le Bihan) — NOT MOEX |
| Dernier indice | Latest/current version of a document |
| Run 0 | Baseline truth — bootstrapped explicitly, immutable |
| Report memory | Persistent consultant responses surviving across pipeline runs |
| Run memory | Execution history: runs, artifacts, lineage, stale propagation |
| Arboretum | Reference reporting template (REPORTING_ARBORETUM_S372022__PBR.xlsx) |

---

## 14. Appendix: Arboretum Template Sheet Mapping

The Arboretum template (57 sheets) maps to GFUP Reporting as follows:

| Arboretum Sheet Category | Count | GFUP Equivalent |
|--------------------------|-------|-----------------|
| Cartouche + Sommaire | 2 | Dashboard home page |
| SUIVI VISA EXE (COMPLET, DI) | 2 | Dashboard KPIs + monthly chart |
| SUIVI OBS & REPONSES | 1 | Consultant fiche Block 3 detail |
| SUIVI FQR / SUIVI RVC / SUIVI PREV | 3 | Out of scope for V1 |
| BILAN VISA MOE + GRAPH | 2 | Dashboard aggregated consultant view |
| REV DOC ENT + GRAPH | 2 | Dashboard aggregated contractor view |
| Docs "A reprendre" SAS | 1 | Dashboard SAS REF panel |
| VISA [consultant] sheets (×18) | 18 | Individual consultant fiche pages |
| [Lot] Bilan Docs sheets (×25) | 25 | Individual contractor fiche pages |
| **Total** | **57** | — |

---

*End of specification.*
