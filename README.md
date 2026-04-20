# GF Updater v3

Deterministic GED → GF reconstruction, enrichment, and run-tracked baseline engine for the **17&CO Tranche 2** workflow.

---

## Revision status

Current UI/revision note for GitHub:

- **Revision**: `Rev 0`
- **UI Step 1**: done
- **UI Step 2**: done
- **UI Step 3**: done
- **UI Step 4**: done
- **Major corrections**: still to be done
- **Reporting**: still not done

This repository state should be treated as an early UI integration milestone, not as a finished reporting release.

### Corrections since the last GitHub push

The changes currently in the worktree close several defects found after `backfill GED, to be verfied`.

- consultant fiche fixes were implemented in the ingestion layer
- AVLS report ingestion now derives `INDICE` from `REF_DOC` instead of reusing the report revision counter
- SOCOTEC ingestion now repairs wrapped P17 references where the indice letter is split onto the next line
- BET report merge no longer backfills all historical versions when a report row has no usable indice; it now targets only the `dernier` version
- reporting data loading now resolves artifact and GED provenance paths after repo relocation and uses the versioned dataset for BET merge backfill
- inherited GF lookup now survives project moves by resolving saved artifact paths relative to the current project root
- `python main.py` can now rebuild and register `Run 0` directly after a full nuke instead of ending with `Pipeline did not register a run_number`
- generated pipeline outputs and data artifacts are now ignored by git

### Still missing

The following items are still not finished and must remain explicit in GitHub history:

- finished workflow doc
- MOEX module
- reports

---

## What this system is

GF Updater v3 is **not** a simple ETL script.

It is a deterministic project engine that:

- reads a raw GED export
- reconstructs document truth and workflow state
- rebuilds a clean Grand Fichier (GF)
- persists consultant-report truth across runs
- persists run history, artifacts, lineage, and baseline state
- allows future runs to inherit trusted context from previous runs

The system is designed for:

- **one project**
- **one team**
- **one user / local usage**

It is intentionally **not** multi-project, multi-user, or SaaS-oriented.

---

## Current freeze status

Backend status at the time of this README:

- **Run 0 baseline model**: implemented
- **Report memory persistence**: implemented
- **Run memory persistence**: implemented
- **Recursive invalidation / stale propagation**: implemented
- **Run lifecycle state (`STARTED` / `COMPLETED` / `FAILED`)**: implemented
- **DB-backed artifact export**: implemented
- **Run explorer backend**: implemented
- **Standalone untracked consultant entrypoint**: blocked for production use

This backend is intended to be treated as **frozen/stable** unless a real defect is found.

---

## Core business problem

The real-world inputs are inconsistent:

- GED data is fragmented, duplicated, and workflow-oriented
- the Grand Fichier is manually maintained and may contain errors
- consultant reports are incomplete, inconsistent, and often arrive outside the GED timing

The software builds a traceable working truth by combining:

1. **GED normalized truth**
2. **persisted report-derived consultant truth**
3. **run baseline / inherited context**

---

## Source-of-truth philosophy

### 1. GED is the primary operational truth

GED remains the authoritative base for:

- document identity
- workflow rows
- mission calling
- primary lifecycle structure

### 2. Consultant reports are secondary but persistent truth

Consultant reports are **not primary**, but once matched and persisted they become reusable project truth across future runs.

Example:

- GED still shows a consultant as pending
- report memory already contains a matched answered consultant response
- the system upgrades the effective response to `ANSWERED`

### 3. GF is an operational reconstruction target

GF is **not** the truth source.
It is a rebuilt, enriched working output.

---

## High-level architecture

```text
GED Export
   ↓
Raw Read / Normalization
   ↓
Version Engine
   ↓
Workflow Engine
   ↓
Report Memory Merge (effective responses)
   ↓
Reconciliation Engine (GED ↔ GF)
   ↓
GF Reconstruction / Enrichment
   ↓
Run Memory / Artifact Persistence
```

In practice, the system has **three persistent layers**:

### A. Core pipeline
Builds the operational outputs.

### B. Report memory
Persists consultant-derived truth across runs.

### C. Run memory
Persists execution history, baseline, artifacts, lineage, and stale propagation.

---

## Main modules

### `read_raw.py`
Reads GED export and extracts raw rows.

### `normalize.py`
Normalizes GED fields and response semantics.

Already implements key mission-state semantics:

- empty response field → `NOT_CALLED`
- `En attente` → `PENDING_IN_DELAY`
- `Rappel en attente` → `PENDING_LATE`
- real date → `ANSWERED`

### `version_engine.py`
Builds document families and index lineage.

Used to determine:

- latest index / current row
- historical valid rows
- previous versions

### `workflow_engine.py`
Computes workflow state per approver and per document.

Includes:

- MOEX/SAS handling
- `VISA GLOBAL`
- SAS-stage distinction (`SAS REF` vs final `REF`)
- document responsibility logic

### `reconciliation_engine.py`
Compares GED vs GF and classifies discrepancies.

Handles:

- missing in GED
- missing in GF
- typo-like mismatches
- duplicate situations
- fuzzy/contextual reconciliation

### `report_memory.py`
Persists report ingestion and matched report responses across runs.

This database is **project memory** for consultant truth.

### `effective_responses.py`
Builds effective responses by merging:

- GED normalized responses
- persisted report-memory answers

This merge is intentionally **left-anchored on GED rows**.

Meaning:

- GED `PENDING_*` rows can be upgraded from report memory
- GED `ANSWERED` rows are preserved
- GED `NOT_CALLED` rows are not forced into existence by reports

### `run_memory.py`
Persists run history.

This database stores:

- runs
- inputs
- artifacts
- corrections
- invalidation log

### `run_orchestrator.py`
Adds controlled execution modes and inherited GF resolution.

### `run_explorer.py`
Provides backend functions for:

- listing runs
- getting run summaries
- exporting final GF
- exporting full run bundles
- comparing runs

---

## Workflow model

The workflow logic is based on real chantier behavior and is already encoded in the system.

### SAS phase
MOEX first-pass compliance control.

- `SAS REF` = submission problem / bad dépôt
- counted against contractor-side quality/process
- no final MOEX visa yet

### Consultant phase
Consultants answer in parallel.

### MOEX final / visa chapeau
Final MOEX visa closes the loop.

### Responsibility logic
Current responsible party is computed from effective workflow state, using existing normalized workflow outputs.

Simplified responsibility rules:

- final `REF` → contractor responsible
- `SAS REF` → contractor responsible
- pending consultant(s) → consultant(s) responsible
- no pending consultants and no final visa → MOEX responsible
- final non-REF visa → closed

---

## Consultant report integration

### What consultant reports are used for

They enrich:

- missing consultant statuses
- missing consultant dates
- missing observations/comments
- pending GED workflow rows that already have real consultant responses outside GED

### Important constraint

Consultant reports are dirty and inconsistent.

So matching is explicit and traceable.

### Matching philosophy

The matching layer is GED-anchored.

Typical fields involved:

- document reference / numero
- indice
- title
- lot / emitter context
- date / consultant context

### Confidence model

The system already uses a confidence strategy and persists matched rows.

Rule of thumb:

- high and medium-confidence matches can be operationally reused
- low-confidence behavior must remain traceable and controlled

### Current important truth

Report-derived consultant truth is **persisted across runs**.

So if a report was ingested once, future runs can reuse that answer even if the user does not re-import the same report file again.

---

## Report memory

Report memory is stored separately from run history.

It is meant to preserve:

- which report files have already been ingested
- matched report-derived consultant responses
- consultant response truth across future runs

This is critical because users may not re-import the same reports every time.

### What report memory enables

Example:

- Socotec still appears pending in GED
- a previously ingested report already contains the Socotec answer
- effective responses upgrade the row to `ANSWERED`
- workflow / responsibility logic then uses the upgraded truth

---

## Run memory

Run memory is the execution history system.

It stores:

- one row per run
- inputs used by the run
- artifacts produced by the run
- corrections registered against a run
- invalidation propagation logs

### Run 0

Run 0 is the **baseline truth**.

It is bootstrapped explicitly and acts as the root baseline for all future runs.

### Later runs

Later runs derive from the baseline and may inherit trusted context from previous completed runs.

### Stale propagation

If a correction is applied against Run 0 or any other run, descendant runs can be marked stale recursively.

---

## Official execution modes

Only the modes below should be considered supported.

### 1. `GED_ONLY`
User provides:

- GED
- Mapping

Internal behavior:

- GF is inherited from the latest valid completed run, otherwise Run 0

Important note:

This is **not** “pure no-GF execution.”
The core still requires a GF workbook internally for routing/writing.
The mode means:

> user does not provide GF explicitly; system resolves one from run history

### 2. `GED_GF`
User provides:

- GED
- GF
- Mapping

### 3. `GED_REPORT`
User provides:

- GED
- reports
- Mapping

Internal behavior:

- GF inherited from latest valid completed run or Run 0

### 4. `FULL`
User provides:

- GED
- GF (or inherited if omitted by current orchestration contract)
- reports
- Mapping

### Explicitly not implemented

#### `REPORT_ONLY`
Not supported.

Why:

The current consultant matching/enrichment path depends on a fresh GED-derived document/workflow universe.
There is no honest report-only path yet.

---

## Inherited GF behavior

If the user does not provide a GF, the orchestrator resolves one in this order:

1. latest run where:
   - `status = COMPLETED`
   - `is_stale = 0`
   - `FINAL_GF` artifact exists
   - artifact file still exists on disk
2. fallback to Run 0 `FINAL_GF`
3. if nothing usable exists, fail clearly

This is the intended behavior and should not be silently bypassed.

---

## Output model

### Core outputs
Typical artifacts include:

- `GF_V0_CLEAN.xlsx`
- discrepancy reports
- anomaly reports
- reconciliation logs
- consultant match report
- consultant enriched stage outputs
- suspicious rows report
- debug outputs
- `report_memory.db` snapshot artifact

### DB-backed artifact model

Successful runs copy artifacts into:

- `runs/run_0000/`
- `runs/run_0001/`
- etc.

Artifacts are also registered in `run_memory.db`.

This means future export should come from the run registry, not from random loose files.

---

## Run lifecycle states

Each run can be:

- `STARTED`
- `COMPLETED`
- `FAILED`

This is important because historical failed runs can exist in DB without being considered valid production runs.

---

## Baseline/bootstrap rules

### Official Run 0

Run 0 must be created explicitly by:

- `scripts/bootstrap_run_zero.py`

Normal pipeline execution must **not** silently invent Run 0.

### Reset discipline

If run history is reset:

- `runs/` can be deleted
- `data/run_memory.db` can be deleted
- `data/report_memory.db` should generally be preserved unless a deliberate full reset is intended

---

## Production execution rule

Do **not** use standalone side-entrypoints that bypass run memory.

In particular:

- direct production execution of `src/consultant_integration.py` is blocked on purpose

Production runs must go through:

- `main.py`
- or the orchestrated execution path that records run history

---

## Validation expectations

A healthy run should prove all of the following:

- pipeline completes
- run row exists
- latest run is `COMPLETED`
- latest run is current
- `FINAL_GF` exists
- run artifacts are registered
- run bundle export matches DB artifact rows
- report memory snapshot exists
- no value-level unexpected regression in GF output

---

## Critical rules for future AI / Codex / contributors

### NEVER

- treat GF as primary truth
- overwrite GED raw data
- silently invent unsupported modes
- silently downgrade execution mode
- bypass run memory for production outputs
- auto-accept weak consultant matches without traceability
- force report-only support unless GED anchor really exists

### ALWAYS

- preserve deterministic behavior first
- preserve traceability
- respect Run 0 as baseline
- use run history for inherited GF resolution
- use report memory as persisted consultant truth
- keep artifact registration complete for successful runs
- mark stale descendants instead of hiding lineage impact

---

## Mental model

This codebase should be understood as:

> a deterministic reconstruction and enrichment engine with persistent project memory

It is not just:

- an Excel updater
- a report parser
- or a reconciliation script

It is a baseline-driven, lineage-aware operational engine for rebuilding and enriching a Grand Fichier from unstable chantier data.
