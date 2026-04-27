# CLEAN INPUT / OUTPUT TARGET

**Created:** 2026-04-26 (Step 3 — Architecture Truth Reset)
**Target achieved by:** Steps 4–12 of the Clean IO plan

This document defines the target product IO contract — what the user places, what the system generates internally, and what it produces as output. It also defines what must NOT happen in the long-term.

---

## Target IO Structure

### User-Facing Input (user places these)

```text
input/
  GED_export.xlsx               <- raw GED dump (primary operational truth)
  Grandfichier_v3.xlsx          <- GF baseline/template
  consultant_reports/           <- PDF consultant reports (optional)
    *.pdf                       <- AVLS, Socotec, BET Terrell, LeSommer, etc.
```

The user places these files and runs the pipeline. That is the complete set of user-facing inputs.

---

### Generated Internal Artifacts (system generates, not user input)

```text
output/intermediate/
  FLAT_GED.xlsx                 <- Flat GED normalized operational layer
                                   Built automatically by orchestrator from GED_export.xlsx
                                   Consumed by stage_read_flat as the pipeline's read input
  DEBUG_TRACE.csv               <- Non-ACTIVE instances and build diagnostics
                                   Not consumed by pipeline; for developer inspection only
  flat_ged_run_report.json      <- Flat GED build statistics (doc count, build time, etc.)
```

Additionally, at runtime:

```text
data/
  run_memory.db                 <- SQLite run artifact registry (persistent)
  report_memory.db              <- SQLite consultant report memory (persistent, 1,245+ rows)
```

And effective responses are computed in-memory during the pipeline run:

```text
[in-memory at runtime]
  effective_responses_df        <- GED_OPERATIONS left-joined with report_memory enrichment
                                   Produced by stage_report_memory / src/effective_responses.py
                                   Future (Step 11): may be snapshotted as output artifact
```

---

### Pipeline Outputs (system produces these)

```text
output/
  GF_V0_CLEAN.xlsx              <- Primary pipeline output — reconstructed Grand Fichier
  GF_TEAM_VERSION.xlsx          <- Protected team-facing export (registered run artifact)
  DISCREPANCY_REPORT.xlsx       <- GED vs GF discrepancy analysis
  DISCREPANCY_REVIEW_REQUIRED.xlsx
  ANOMALY_REPORT.xlsx
  AUTO_RESOLUTION_LOG.xlsx
  IGNORED_ITEMS_LOG.xlsx
  INSERT_LOG.xlsx
  RECONCILIATION_LOG.xlsx
  MISSING_IN_GED_DIAGNOSIS.xlsx
  MISSING_IN_GF_DIAGNOSIS.xlsx
  consultant_match_report.xlsx
  ... diagnosis and new-submittal reports ...

  [team export — stamped on demand]
  Tableau de suivi de visa DD_MM_YYYY.xlsx   <- copied from GF_TEAM_VERSION by export_team_version()

  logs/
    ... run logs and debug traces ...
```

---

### Immutable Run Artifacts

```text
runs/run_NNNN/
  [snapshot of output/ artifacts at time of run completion]
  GF_V0_CLEAN.xlsx              <- registered as FINAL_GF
  GF_TEAM_VERSION.xlsx          <- registered as GF_TEAM_VERSION
  FLAT_GED.xlsx                 <- registered as FLAT_GED (Step 8 target)
  flat_ged_run_report.json      <- registered as FLAT_GED_RUN_REPORT (Step 8 target)
  report_memory.db              <- snapshot of report memory at run time
  run_report.json               <- run metadata and statistics
  ... other artifacts ...
```

`runs/run_0000/` is the immutable baseline. Do not overwrite it.

---

## Artifact Registration Targets (Steps 7–8)

After Steps 7 and 8, the following artifact types must be registered in `run_memory.db`:

| Artifact Type | File | Registered In |
|---|---|---|
| `FLAT_GED` | `FLAT_GED.xlsx` | Step 8 |
| `FLAT_GED_DEBUG_TRACE` | `DEBUG_TRACE.csv` | Step 8 |
| `FLAT_GED_RUN_REPORT` | `flat_ged_run_report.json` | Step 8 |
| `FINAL_GF` | `GF_V0_CLEAN.xlsx` | Existing — `stage_finalize_run` |
| `GF_TEAM_VERSION` | `GF_TEAM_VERSION.xlsx` | Existing — `stage_finalize_run` |
| `DISCREPANCY_REPORT` | `DISCREPANCY_REPORT.xlsx` | Existing |
| `ANOMALY_REPORT` | `ANOMALY_REPORT.xlsx` | Existing |

---

## What Must NOT Happen Long-Term

The following behaviors are acceptable temporarily but must be eliminated before Gate 4:

| Anti-Pattern | Why Prohibited | Eliminated In |
|---|---|---|
| User manually places `FLAT_GED.xlsx` in `input/` | Flat GED is an internal artifact, not a user input. Users should not need to know it exists. | Step 7 |
| Pipeline `FLAT_GED_MODE` default is `"raw"` | The production default must be flat mode. Raw mode is a developer fallback only. | Step 7 |
| UI rebuilding raw GED on every load | `data_loader.py` calling `read_ged()` + `VersionEngine()` is expensive and bypasses run artifacts. UI should load from registered artifacts. | Step 12 |
| `consultant_gf_writer` producing authoritative GF outside run history | Direct Excel writes to GF cells bypass the pipeline, run_memory, and traceability. This path is deprecated. | Step 13 cleanup |
| `bet_report_merger` returning as any form of UI truth path | It was a UI-layer independent merge that caused pipeline/UI truth split. It is retired. | Already retired (Step 7 composition spec) |
| Non-`run_memory`-registered Flat GED artifacts | Any FLAT_GED.xlsx used in a run must be registered as an artifact for traceability. | Step 8 |

---

## Current State vs Target Comparison

| Concern | Current (Dev/Temporary) | Target (Clean IO) |
|---|---|---|
| Who produces FLAT_GED | User manually | Orchestrator auto (from GED_export.xlsx) |
| FLAT_GED location | `input/FLAT_GED.xlsx` | `output/intermediate/FLAT_GED.xlsx` |
| Pipeline default mode | `"raw"` (raw GED path) | `"flat"` (Flat GED path) |
| FLAT_GED registered | No | Yes — 3 artifact types |
| UI load path | Raw rebuild (`read_ged()`, `VersionEngine()`, etc.) | Run artifacts + effective_responses snapshot |
| effective_responses snapshot | In-memory only | Optionally snapshotted as `EFFECTIVE_RESPONSES` artifact (Step 11) |

---

## TEAM_GF Preservation

The `GF_TEAM_VERSION` chain must survive unchanged through all IO refactoring steps:

```text
stage_write_gf           -> writes output/GF_V0_CLEAN.xlsx
team_version_builder.py  -> builds output/GF_TEAM_VERSION.xlsx from GF_V0_CLEAN
stage_finalize_run.py    -> registers GF_TEAM_VERSION artifact in run_memory
app.py export_team_version()
  -> reads GF_TEAM_VERSION artifact path from run_memory
  -> copies to output/Tableau de suivi de visa DD_MM_YYYY.xlsx
```

This chain is ACTIVE_PROTECTED. It must not be broken or marked as obsolete.

---

## Gate 4 Acceptance Criteria

Gate 4 passes when ALL of the following are true:

1. User no longer manually provides `FLAT_GED.xlsx`
2. Flat GED is generated internally by the orchestrator
3. Pipeline default mode is `"flat"`
4. `GF_V0_CLEAN.xlsx` is produced correctly
5. `GF_TEAM_VERSION.xlsx` is produced correctly
6. UI loads correctly (with improved artifact-based load path)
7. `report_memory.db` is not broken
8. Flat GED artifacts are registered in `run_memory`
9. Documentation reflects the actual runtime
10. Obsolete files are classified and cleaned per Steps 13–14
