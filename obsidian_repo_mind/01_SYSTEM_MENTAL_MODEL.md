#repo-map #mental-model #pipeline #architecture

# System Mental Model

> **One-page view of the entire system.** See [[02_SOURCE_OF_TRUTH_HIERARCHY]] for layer authority, [[03_EXECUTION_FLOW]] for runtime detail.

---

## Core pipeline (write path)

```
input/GED_export.xlsx          ← required raw GED dump
         │
         ▼
[src/flat_ged_runner.py]
  → src/flat_ged/              ← FROZEN BUILDER (do not edit business rules)
         │
         ▼
output/intermediate/FLAT_GED.xlsx
  └─ sheet GED_OPERATIONS      ← active document rows (normalized)
  └─ sheet GED_RAW_FLAT        ← all raw rows

         │
[consultant integration]
  src/consultant_integration.py  ← optional, when PDF reports provided
         │
         ▼
[11-stage pipeline — src/pipeline/stages/]
  stage_init_run → stage_read_flat → stage_normalize → stage_version
  → stage_route → stage_report_memory → stage_write_gf
  → stage_build_team_version → stage_discrepancy → stage_diagnosis
  → stage_finalize_run
         │
         ▼
data/report_memory.db          ← persistent consultant truth (survives runs)
data/run_memory.db             ← artifact registry (sha256)
output/GF_V0_CLEAN.xlsx        ← reconstructed GF
output/GF_TEAM_VERSION.xlsx    ← team-facing export
output/DISCREPANCY_REPORT.xlsx ← + other reports
runs/run_NNNN/                 ← immutable snapshot
```

---

## Read path (UI feed)

```
data/run_memory.db
         │  resolves latest COMPLETED run
         ▼
src/reporting/data_loader.py   ← builds RunContext (with pickle cache)
  → builds effective_responses_df via src/effective_responses.py
         │
         ▼
src/reporting/aggregator.py    ← compute_project_kpis / consultant / contractor
src/reporting/consultant_fiche.py  ← per-consultant payload
src/reporting/contractor_quality.py ← per-contractor quality payload
src/reporting/document_command_center.py ← DCC search + panel
src/reporting/drilldown_builder.py ← drilldown drawer rows
src/reporting/ui_adapter.py    ← shapes output to window.OVERVIEW / CONSULTANTS / CONTRACTORS
         │
         ▼
app.py (Api class)             ← PyWebView bridge methods
         │
         ▼
ui/jansa/data_bridge.js        ← populates window.OVERVIEW / CONSULTANTS / CONTRACTORS / FICHE_DATA
         │
         ▼
ui/jansa/*.jsx                 ← presentation layer ONLY — no business logic
ui/jansa-connected.html        ← production UI entry point (single file)
```

---

## Independent intelligence path (Chain+Onion)

```
python run_chain_onion.py
         │  reads FLAT_GED.xlsx + report_memory.db
         ▼
src/chain_onion/ (Steps 04–14)
         │
         ▼
output/chain_onion/*.csv + *.json + *.xlsx

         │  consumed by:
         ├─ app.py → Api._build_live_operational_numeros → Focus narrowing
         ├─ src/reporting/chain_timeline_attribution.py → DCC Chronologie section
         └─ (Phase 6A) src/reporting/counter_attack_builder.py → Action MOEX artifact
```

---

## Key invariants

| Invariant | Authority |
|---|---|
| GF is a reconstruction **target**, not source of truth | [[02_SOURCE_OF_TRUTH_HIERARCHY]] |
| UI is **presentation only** — no business logic in JSX | `context/08_DO_NOT_TOUCH.md §B` |
| `src/flat_ged/` is a **frozen** snapshot — adapter changes go in `stage_read_flat.py` | `README §What Not To Touch` |
| `report_memory.db` contains 1,245+ rows of consultant truth — **never delete casually** | [[10_PERSISTENCE_RUN_AND_REPORT_MEMORY]] |
| `doc_id` (UUID) is session-scoped — **never persist** to chain output CSVs | `src/chain_onion/source_loader.py docstring` |
| `WorkflowEngine.responses_df` ≠ `RunContext.responses_df` — engine strips SAS rows | [[11_DEBUGGING_SEAMS]] |

---

## Production entry points

| Command | What it does |
|---|---|
| `python main.py` | Runs full headless pipeline via `run_orchestrator.run_pipeline_controlled` |
| `python app.py` | Boots JANSA PyWebView desktop app, serves `ui/jansa-connected.html` |
| `python app.py --browser` | Opens same HTML in system browser — **no backend bridge, placeholder data only** |
| `python run_chain_onion.py` | Runs Chain+Onion pipeline → `output/chain_onion/` |
| `python scripts/audit_counts_lineage.py` | Cross-layer data audit (L0 RAW → L6 UI) |

---

*Back to [[00_START_HERE]]*
