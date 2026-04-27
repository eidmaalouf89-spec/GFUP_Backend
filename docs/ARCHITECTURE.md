# ARCHITECTURE

**Last updated:** 2026-04-26 (Step 3 — Architecture Truth Reset)

GF Updater v3 is a deterministic GED → GF reconstruction engine with a production JANSA desktop UI runtime.

The backend is the source of truth. The JANSA UI is the operational presentation layer over backend adapters and a pywebview bridge.

---

## Runtime Entrypoints

| Entrypoint | Role |
|---|---|
| `main.py` | Pipeline CLI entrypoint — imports path constants, calls `run_pipeline()` |
| `src/run_orchestrator.py` | Controlled execution layer — mode switching, input validation, artifact registration |
| `app.py` | Desktop JANSA launcher — Flask + PyWebView, exposes `export_team_version()` and all UI API methods |
| `ui/jansa-connected.html` | Single production UI entry point — loaded by PyWebView, bootstraps JSX via Babel standalone |

The old Vite UI under `ui/src/`, `ui/index.html`, and `ui/dist/` is legacy/reference only. It is not a production runtime target. `api_server.py` does not exist and is not required unless a future FastAPI revival is explicitly scoped.

---

## Input Truth

### User-Facing Operational Inputs

These files are placed by the user and are the authoritative operational source:

| Input | Path | Role |
|---|---|---|
| Raw GED dump | `input/GED_export.xlsx` | Primary truth for document identity, workflow rows, mission calling, lifecycle structure |
| Grand Fichier source | `input/Grandfichier_v3.xlsx` | GF baseline/template — enriched and reconstructed into output |
| Consultant reports | `input/consultant_reports/` | Optional secondary inputs — ingested into `report_memory.db` |

### Internal Artifact (NOT user input long-term)

| Artifact | Path | Role |
|---|---|---|
| Flat GED | `FLAT_GED.xlsx` | Normalized operational layer — currently manually placed at `input/FLAT_GED.xlsx` as a temporary dev behavior; Step 7 will auto-generate it into `output/intermediate/` from the raw GED dump |

**`input/FLAT_GED.xlsx` is a temporary dev-only behavior. The long-term target is that the user never manually places this file. The orchestrator will build it automatically.**

---

## Current Architecture (as of 2026-04-26)

### Current state summary

- `FLAT_GED_MODE = "raw"` is the default in `src/pipeline/paths.py`
- The flat adapter (`stage_read_flat.py`) exists and is parity-verified (Gate 1, Gate 2, Gate 3), but is not yet the automatic default
- `FLAT_GED_FILE` in `paths.py` points to `input/FLAT_GED.xlsx` — manually placed
- `data_loader.py` in `src/reporting/` still calls raw-rebuild functions (`read_ged()`, `normalize_docs()`, `normalize_responses()`, `VersionEngine()`) — this is a known Step 12 target
- `stage_read_flat.py` carries `TEMPORARY_COMPAT_LAYER` markers — these will be resolved in later cleanup

```text
main.py
  -> src/run_orchestrator.py
  -> src/pipeline/runner.py
      [FLAT_GED_MODE == "raw"]  -> stage_read.py (reads raw GED directly)
      [FLAT_GED_MODE == "flat"] -> stage_read_flat.py (reads FLAT_GED.xlsx from input/)
  -> stage_normalize
  -> stage_version
  -> stage_route
  -> stage_report_memory    (effective_responses composition)
  -> stage_write_gf         (writes GF_V0_CLEAN.xlsx)
  -> stage_discrepancy
  -> stage_diagnosis
  -> stage_finalize_run     (registers artifacts including GF_TEAM_VERSION)
  -> output/
  -> runs/run_NNNN/
  -> data/run_memory.db
  -> data/report_memory.db
```

### Known temporary layers (do not remove before their designated step)

| Layer | Location | Temporary Reason | Resolved In |
|---|---|---|---|
| `FLAT_GED_MODE = "raw"` default | `src/pipeline/paths.py` line 39 | Not yet default "flat" | Step 7 |
| `FLAT_GED_FILE = input/FLAT_GED.xlsx` | `src/pipeline/paths.py` line 34 | Manually placed; not auto-generated | Step 7 |
| `stage_read_flat.py` `TEMPORARY_COMPAT_LAYER` markers | `src/pipeline/stages/stage_read_flat.py` | Adapter compatibility shims | Step 14 cleanup |
| `data_loader.py` raw rebuild path | `src/reporting/data_loader.py` | Still calls raw-GED rebuild functions | Step 12 |
| `scripts/_run_one_mode.py` hardcoded `input/FLAT_GED.xlsx` | `scripts/_run_one_mode.py` | Hardcoded dev path | Step 7 (obsolete after) |

---

## Target Clean IO Architecture (Steps 6–12)

After Steps 6–12 are complete, the architecture will be:

```text
input/
  GED_export.xlsx           <- user places this
  Grandfichier_v3.xlsx      <- user places this
  consultant_reports/       <- user places these (optional)

main.py
  -> src/run_orchestrator.py
      -> validate GED input
      -> build_flat_ged(GED_export.xlsx)   <- NEW: auto-generates Flat GED
      -> sets FLAT_GED_MODE = "flat"       <- always flat in production
      -> sets FLAT_GED_FILE = output/intermediate/FLAT_GED.xlsx
      -> run_pipeline()
          -> stage_read_flat (default)
          -> stage_normalize
          -> stage_version
          -> stage_route
          -> stage_report_memory          (effective_responses composition)
          -> stage_write_gf               (writes GF_V0_CLEAN.xlsx)
          -> stage_discrepancy
          -> stage_diagnosis
          -> stage_finalize_run           (registers all artifacts in run_memory)

output/intermediate/
  FLAT_GED.xlsx             <- auto-generated by orchestrator
  DEBUG_TRACE.csv           <- Flat GED builder debug output
  flat_ged_run_report.json  <- Flat GED build report

output/
  GF_V0_CLEAN.xlsx
  GF_TEAM_VERSION.xlsx
  DISCREPANCY_REPORT.xlsx
  ANOMALY_REPORT.xlsx
  ... other artifacts ...

runs/run_NNNN/
  immutable registered artifacts snapshot
```

---

## Flat GED Internal Artifact Model

The Flat GED (`FLAT_GED.xlsx`) is the normalized internal operational layer. It is produced by `src/flat_ged/` (frozen builder snapshot) and consumed by `stage_read_flat.py`.

### Flat GED sheets

| Sheet | Role |
|---|---|
| `GED_RAW_FLAT` | Raw normalized GED rows — R_COLS (21 columns) |
| `GED_OPERATIONS` | Step-typed workflow rows — O_COLS (37 columns). One row per `(numero, indice, actor)`. ACTIVE instances only. |
| `DEBUG_TRACE` | Non-ACTIVE instances and intermediate state — D_COLS (23 columns). Not consumed by pipeline. |

### Key GED_OPERATIONS properties

- Grain: one row per `(numero, indice, step_type, actor_clean)` — ACTIVE instances only
- Pre-computed: `is_completed`, `is_blocking`, `status_family`, `phase_deadline`, `delay_contribution_days`
- `OPEN_DOC` rows represent document submittal — excluded from effective response composition
- `closure_mode` captures per-document cycle closure state
- Non-ACTIVE instances are visible only in DEBUG_TRACE (deferred to Chain/Onion phase)

### Flat GED builder contract

The builder is frozen at `src/flat_ged/`. The public API is `from src.flat_ged import build_flat_ged`. The column contract is in `docs/FLAT_GED_CONTRACT.md` (v1.0). **Do not modify business logic in `src/flat_ged/`.**

---

## Report Memory Composition Model

`effective_responses_df` is the composed response truth. It is produced by `stage_report_memory` via `src/effective_responses.py`.

Composition model: `GED_OPERATIONS` rows (Flat GED) are the left-side anchor. `report_memory.db` enriches rows that are `PENDING` in Flat GED, subject to 8 eligibility gates (E1–E8). See `docs/FLAT_GED_REPORT_COMPOSITION.md` for the complete spec.

### Source hierarchy

| Rank | Source | Can Override Flat GED ANSWERED? |
|---|---|---|
| 1 | Flat GED `GED_OPERATIONS` | N/A — primary structural anchor |
| 2 | `report_memory.db` `persisted_report_responses` | NO — may only enrich PENDING rows |
| 3 | Manual comment enrichment | NO — additive text only |
| RETIRED | `bet_report_merger` (UI-layer merge) | RETIRED — no longer authoritative |
| DEPRECATED | `consultant_gf_writer` (direct Excel write) | DEPRECATED — no longer truth path |

Every output row in `effective_responses_df` carries an explicit provenance tag (GED_ONLY, REPORT_ENRICHED, REPORT_CONFLICT, etc.).

---

## Query Library Role

`src/query_library.py` is the single query layer for all dashboard, KPI, fiche, and queue metrics. Any metric displayed in the UI or exported to a report must be computable by calling one function from `query_library.py`.

The `QueryContext` dataclass wraps 4 inputs: `flat_ged_ops_df`, `effective_responses_df`, `flat_ged_df` (optional), `flat_ged_doc_meta` (optional).

22 public symbols across 7 groups: Portfolio KPIs (A), Status Mix (B), Consultant KPIs (C), Doc Lifecycle (D), Queue Primitives (E), Fiche getters (F), Provenance functions (G).

See `docs/QUERY_LIBRARY_SPEC.md` for the complete spec.

---

## TEAM_GF Export Preservation

**The GF_TEAM_VERSION chain must be preserved in all current and future pipeline changes.**

| Component | Role | Status |
|---|---|---|
| `src/team_version_builder.py` | Builds GF_TEAM_VERSION.xlsx from GF_V0_CLEAN | ACTIVE_PROTECTED |
| `src/pipeline/stages/stage_finalize_run.py` | Registers GF_TEAM_VERSION artifact in run_memory | ACTIVE_PROTECTED |
| `src/pipeline/paths.py → OUTPUT_GF_TEAM_VERSION` | Path constant for team export file | ACTIVE_PROTECTED |
| `app.py → export_team_version()` | UI API method that finds GF_TEAM_VERSION artifact and copies it date-stamped | ACTIVE_PROTECTED |
| `output/GF_TEAM_VERSION.xlsx` | Runtime output file | ACTIVE_PROTECTED |

The UI `export_team_version()` workflow:

```text
export_team_version()
  -> find latest GF_TEAM_VERSION artifact in run_memory
  -> copy to output/Tableau de suivi de visa DD_MM_YYYY.xlsx
```

This must not be marked as obsolete. It is a required product feature.

---

## Source-Of-Truth Rules

1. Raw GED dump = source for operational document universe
2. Flat GED = normalized internal operational layer
3. `report_memory.db` = persistent secondary consultant truth
4. `effective_responses_df` = composed response truth (GED + report memory)
5. `GF_V0_CLEAN.xlsx` = reconstructed output
6. `GF_TEAM_VERSION.xlsx` = protected team-facing export
7. UI = presentation layer only

Do not:
- treat GF as primary truth
- bypass `run_orchestrator.py` for production behavior
- reintroduce `bet_report_merger` as a truth path
- allow `consultant_gf_writer` to produce authoritative GF outside run history

---

## UI Architecture

### Production UI

```text
backend reporting data
  -> src/reporting/* adapters
  -> app.py pywebview API methods
  -> ui/jansa/data_bridge.js
  -> ui/jansa/*.jsx
  -> ui/jansa-connected.html
```

Production runtime components:

- `app.py`
- `ui/jansa-connected.html`
- `ui/jansa/tokens.js`
- `ui/jansa/data_bridge.js`
- `ui/jansa/*.jsx` (shell, overview, consultants, fiche_base, fiche_page, runs, executer)
- backend bridge methods exposed from `app.py`
- reporting adapters under `src/reporting/`

### Legacy / reference UI (not production)

| Path | Status |
|---|---|
| `ui/src/` (old Vite React app) | LEGACY_REFERENCE — superseded by `ui/jansa/` |
| `ui/index.html` | LEGACY_REFERENCE — not loaded by `app.py` |
| `ui/vite.config.js`, `ui/package.json` | LEGACY_REFERENCE — old Vite setup |
| `ui/dist/` | GENERATED_OUTPUT — stale Vite build artifact |
| `JANSA Dashboard - Standalone.html` (root) | DELETE_CANDIDATE — Step 14 |

`api_server.py` does not exist and is not part of the production runtime.

---

## Protected Assets

The following must not be modified outside their designated step:

| Asset | Why Protected |
|---|---|
| `src/flat_ged/` (entire folder) | Frozen builder snapshot; business logic must not be changed |
| `src/flat_ged/VERSION.txt`, `BUILD_SOURCE.md` | Freeze contract documentation |
| `src/report_memory.py` | Persistent consultant report memory |
| `src/run_memory.py` | Persistent run artifact registry |
| `src/effective_responses.py` | Effective response builder — rewritten in Step 8 |
| `src/pipeline/stages/stage_report_memory.py` | Upserts effective responses — repaired in Steps 8/9 |
| `src/pipeline/stages/stage_finalize_run.py` | Registers GF_TEAM_VERSION artifact |
| `src/team_version_builder.py` | Team GF export builder |
| `app.py → export_team_version()` | UI team export API |
| `ui/jansa-connected.html` | Production UI entry point |
| `ui/jansa/` (all files) | Production UI component library |
| `runs/run_0000/` | Immutable baseline artifacts |
| `data/report_memory.db` | Consultant report memory database |
| `data/run_memory.db` | Run artifact registry database |

---

## Review Surface

For backend changes, review the staged pipeline, domain helpers, persistence, and artifact contracts.

For UI/runtime changes, review:

- `app.py`
- `src/reporting/`
- `ui/jansa-connected.html`
- `ui/jansa/`
- `docs/UI_RUNTIME_ARCHITECTURE.md`
- `docs/JANSA_FINAL_AUDIT.md`

Do not revive dual-UI runtime assumptions. Do not treat `api_server.py` as a required file.
