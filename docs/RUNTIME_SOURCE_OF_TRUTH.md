# RUNTIME SOURCE OF TRUTH

**Created:** 2026-04-26 (Step 3 — Architecture Truth Reset)

This document defines which layer is the authoritative source of truth for each concern at runtime. When two layers disagree, the higher-ranked layer wins.

---

## Source-Of-Truth Layer Table

| Layer | Source File / DB | Current Status | Target Status | Owner Module |
|---|---|---|---|---|
| **Raw GED dump** | `input/GED_export.xlsx` | ACTIVE — user-placed operational input | UNCHANGED — always user-facing input | `src/read_raw.py`, `src/flat_ged/` (consumes) |
| **Flat GED** | `FLAT_GED.xlsx` (currently `input/`; target `output/intermediate/`) | ACTIVE_TEMPORARY — manually placed by user at `input/FLAT_GED.xlsx` | AUTO-GENERATED — orchestrator builds from raw GED into `output/intermediate/` (Step 7) | `src/flat_ged/` (builder), `src/pipeline/stages/stage_read_flat.py` (consumer) |
| **report_memory** | `data/report_memory.db` | ACTIVE_PROTECTED — 1,245 active rows; persists across runs | UNCHANGED — persistent secondary truth | `src/report_memory.py` |
| **effective_responses_df** | Composed at runtime from `GED_OPERATIONS` + `report_memory.db` | ACTIVE — produced by `stage_report_memory` via `src/effective_responses.py` | UNCHANGED — single composition path | `src/effective_responses.py`, `src/pipeline/stages/stage_report_memory.py` |
| **GF_V0_CLEAN** | `output/GF_V0_CLEAN.xlsx` | ACTIVE — primary pipeline output; registered as FINAL_GF artifact | UNCHANGED — reconstructed output | `src/pipeline/stages/stage_write_gf.py` |
| **GF_TEAM_VERSION** | `output/GF_TEAM_VERSION.xlsx` | ACTIVE_PROTECTED — team-facing export; registered as run artifact | UNCHANGED — protected team export | `src/team_version_builder.py`, `stage_finalize_run.py` |
| **UI** | `ui/jansa-connected.html` + `ui/jansa/` | ACTIVE_PROTECTED — PyWebView + Babel standalone, no build step | UNCHANGED for now; Step 12 will refactor data_loader to consume run artifacts | `app.py`, `ui/jansa/data_bridge.js` |
| **query_library** | `src/query_library.py` | ACTIVE — 22-function read-only query API over Flat GED context | UNCHANGED — single query layer for all UI metrics | `src/query_library.py` |
| **run_memory** | `data/run_memory.db` | ACTIVE_PROTECTED — artifact registry; contains Run 0 baseline | UNCHANGED — lineage system for runs and artifacts | `src/run_memory.py` |

---

## Layer Relationships

```text
input/GED_export.xlsx          ← user places
  ↓ (build_flat_ged — currently manual, Step 7 auto)
FLAT_GED.xlsx (GED_OPERATIONS)
  ↓ (stage_read_flat)
  ├─ + report_memory.db        ← persists across runs
  ↓ (stage_report_memory / effective_responses.py)
effective_responses_df         ← composed response truth
  ↓ (stage_write_gf)
GF_V0_CLEAN.xlsx               ← reconstructed output
  ↓ (team_version_builder)
GF_TEAM_VERSION.xlsx           ← protected team export
  ↓ (stage_finalize_run)
run_memory.db                  ← artifact registry
  ↓ (app.py export_team_version)
output/Tableau de suivi de visa DD_MM_YYYY.xlsx
```

---

## Override Rules

These override rules are invariant. They must not be changed without an explicit architectural decision:

1. **Raw GED always wins** over any GF-derived data for document identity and workflow universe.
2. **Flat GED `GED_OPERATIONS` rows are the left-side anchor** for all effective response composition. `report_memory` may only enrich rows that are `PENDING` in Flat GED — it cannot override ANSWERED rows.
3. **`effective_responses_df` is the single composition output.** There is one composition path. `bet_report_merger` is retired. `consultant_gf_writer` direct write is deprecated.
4. **GF_TEAM_VERSION is derived from GF_V0_CLEAN.** It is never the primary source of truth. It must be regenerated when GF_V0_CLEAN changes.
5. **UI is presentation only.** UI metrics are read-only views over `query_library.py`. UI must not write to or override backend truth layers.
6. **run_memory.db is the lineage authority.** Artifact paths, run numbers, baseline state, and stale propagation are authoritative in run_memory.

---

## Current vs Target: FLAT_GED Location

| Concern | Current (Dev/Temporary) | Target (Clean IO) |
|---|---|---|
| Who places FLAT_GED.xlsx | User manually places at `input/FLAT_GED.xlsx` | Orchestrator auto-generates at `output/intermediate/FLAT_GED.xlsx` |
| `FLAT_GED_FILE` in `paths.py` | `INPUT_DIR / "FLAT_GED.xlsx"` | `OUTPUT_DIR / "intermediate" / "FLAT_GED.xlsx"` |
| `FLAT_GED_MODE` default | `"raw"` | `"flat"` |
| Pipeline default read path | `stage_read.py` (raw GED) | `stage_read_flat.py` (Flat GED) |
| Flat GED registered as artifact | No | Yes — `FLAT_GED`, `FLAT_GED_DEBUG_TRACE`, `FLAT_GED_RUN_REPORT` |

Changes will be made in Steps 6/7. The raw path (`stage_read.py`) will remain as a developer fallback mode only.

---

## What Is NOT A Source Of Truth

The following are explicitly NOT authoritative sources of truth:

| Item | Why Not |
|---|---|
| `GF_V0_CLEAN.xlsx` (as input) | It is a reconstructed output. GED is the source; GF is the target. |
| `bet_report_merger` | Retired as UI-layer independent merge. No longer authoritative. |
| `consultant_gf_writer` direct Excel writes | Deprecated from truth path. Cannot produce authoritative GF outside run history. |
| `ui/src/` (old Vite app) | Legacy reference only — not the production runtime. |
| `input/FLAT_GED.xlsx` long-term | Temporary dev placement only. Not the target contract. |
| Any `data_loader.py` raw rebuild | Step 12 target for elimination. Will be replaced by run artifact loading. |
