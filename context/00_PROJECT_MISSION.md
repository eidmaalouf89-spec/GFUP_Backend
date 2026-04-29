# 00 — Project Mission

> **Status:** Reconstructed from actual code, April 2026.
> **Source of truth for this doc:** `app.py`, `main.py`, `src/**`, `ui/**`, `runs/`, `output/`.
> **NOT the source:** README.md, GFUP_STEP_TRACKER.md, FLAT_GED_INTEGRATION plans, JANSA notes.
> Those are secondary references; where they conflict with code, code wins.

---

## What the software actually does today

The GF Updater V3 is a **single-user, single-project desktop application** that runs the
**P17&CO Tranche 2** site visa workflow (the "JANSA VISASIST" tool). It is not a SaaS,
not multi-tenant, not a generic Excel updater.

Two responsibilities:

1. **Rebuild the team Grand Fichier (GF) from a fresh GED export.**
   The pipeline reads the raw GED, normalises it to a Flat GED intermediate,
   reconstructs lifecycles, applies persistent consultant report memory,
   reconciles against the prior GF, and writes the cleaned/team-version GF + a
   battery of diagnostic outputs.

2. **Surface operational intelligence over those outputs through a desktop UI.**
   `app.py` boots a PyWebView shell and exposes a Python `Api` class to a React
   front-end (`ui/jansa-connected.html`). The UI shows KPIs, consultant fiches,
   contractor summaries, run history, the priority queue (Focus mode), and
   triggers pipeline runs / exports.

Two analytical layers are stacked on top of the pipeline outputs:

- `src/reporting/*` — the live UI feed: KPIs, fiches, focus filter, ownership.
- `src/chain_onion/*` — a separate portfolio-intelligence layer (Steps 04–14)
  that builds chains, scores impact through a six-layer onion, and emits its
  own register/scores/narratives. Run via `run_chain_onion.py`. Currently
  consumed by `app.py` only to narrow Focus to the LIVE_OPERATIONAL bucket.

---

## Core business purpose

The user (Eid Maalouf, OPC at GEMO) is responsible for keeping the Grand Fichier
synchronised with the GED on P17&CO Tranche 2. Every week:

- The GED export changes (new submittals, new consultant answers, MOEX SAS
  decisions, contractor revisions).
- The GF must be regenerated to reflect the new state, **without losing**
  consultant truth that lives in PDF/XLSX consultant reports outside the GED.
- Discrepancies (rows in GF not in GED, rows in GED not in GF, indice/title
  mismatches, BENTIN legacy noise) must be surfaced in a review queue.
- A team-facing GF (`GF_TEAM_VERSION.xlsx`, exported as
  `Tableau de suivi de visa DD_MM_YYYY.xlsx`) must be produced for distribution.
- Per-consultant fiches and per-contractor summaries are needed for steering
  meetings.

The Focus mode + Chain+Onion layer aim to convert the raw output into
"who owes me what, ranked by urgency" — backlog trimming and live priority.

---

## Current strengths (observed in code)

- **Determinism + reproducibility.** `data/run_memory.db` registers every artifact
  with sha256 and a `run_number`; runs can be replayed and exported as bundles.
- **Persistent consultant memory.** `data/report_memory.db` stores ingested
  consultant responses across runs (HIGH/MEDIUM confidence gate). A response
  promoted by report memory survives future GED rebuilds without re-import.
- **Staged pipeline.** Eleven discrete stages in `src/pipeline/stages/`, each
  with a documented context-read/context-write contract. Easy to reason about
  per-stage failure.
- **Frozen FLAT_GED builder.** `src/flat_ged/` is treated as a read-only
  snapshot; adapter changes go in `stage_read_flat.py`.
- **Mature UI bridge.** `data_bridge.js` + `Api` class is a clean
  request/response surface (`window.pywebview.api.*` → Python). Generation
  counters guard against stale responses.
- **Source-of-truth hierarchy is explicit** in code and in `paths.py`.
- **Hardcoded exception handling is tightly scoped.** The two known exception
  categories — `LOT 31 à 34-IN-BX-CFO-BENTIN` (pre-2026) and `LOT 03-GOE-LGD`
  (pre-2026) — are codified in `src/config_loader.py:SHEET_YEAR_FILTERS` and
  `src/pipeline/stages/stage_discrepancy.py:Part H-1`.

---

## Current pain points (observed in code or trackers, NOT speculative)

- **`output/` is a flat dump of last-run artifacts AND historical parity
  experiments.** Folders `parity/`, `parity_raw_r1/`, `parity_raw_run1/`,
  `parity_raw_run2/`, `step9/legacy/`, plus `tmp63o7zaid.xlsx` and
  `tmpxkmaioec.db`/`tmpyw_386pd.db` at repo root are leftovers from validation
  steps. No code references them at runtime, but they confuse the artifact
  picture.
- **Two parallel "tree" outputs.** `output/` holds the latest run; `runs/run_0000/`
  holds the immutable baseline. `runs/run_0001/` etc. would extend it. Today
  only run 0 exists. The docs talk about "Run #N" but only run 0 is registered.
- **README, FLAT_GED_INTEGRATION_EXECUTION_PLAN, GFUP_STEP_TRACKER all narrate
  steps and gates that are largely complete but each tells the story
  differently.** No single rolled-up state doc — that gap is what this
  /context folder fills.
- **`docs/` contains 60+ planning/audit markdowns**, many step-specific
  (STEP01_…STEP15_…). These are historical execution records, not living docs.
- **UI Contractors page is a stub.** `shell.jsx` line 653 renders
  `<StubPage title="Entreprises" note="Laissé intact volontairement…">`. The
  backend (`get_contractor_list`, `get_contractor_fiche`,
  `get_contractors_for_ui`) is fully wired and returns data, but the UI does
  not yet consume it.
- **UI Discrepancies + Settings pages are stubs** for the same reason.
- **Chain + Onion outputs feed the UI only narrowly.** Today the UI uses
  `query_hooks.get_live_operational` + `get_legacy_backlog` to narrow Focus
  scope. The richer onion scores, narratives, and top-issues are not yet
  surfaced as a UI screen.
- **Mapping.xlsx role is unclear.** The Executer page exposes a "Mapping" file
  picker but `app.py:run_pipeline_async` does NOT pass it to the orchestrator.
  Comment in UI: `"informatif — non transmis au backend"`.
- **"Tableau de suivi de visa 10_04_2026.xlsx" is in `output/`** alongside the
  current run. Indicates the team-version export path is exercised regularly,
  but the file is stale relative to today (2026-04-27).
- **`docs/UI_RUNTIME_ARCHITECTURE.md` is referenced by README** but lives in
  /docs alongside many other UI docs of unclear current authority.

---

## What this software is NOT

- Not multi-project. All paths, role lists, contractor codes, exclusion rules
  are hardcoded for **17&CO Tranche 2**.
- Not a SaaS. Single-user PyWebView desktop, single working dir.
- Not configurable through a settings file at runtime. Configuration lives in
  Python constants (`src/config_loader.py`, `src/flat_ged/input/source_main/*`,
  `src/reporting/consultant_fiche.py`).
- Not a multi-tenant data platform. `data/run_memory.db` and
  `data/report_memory.db` are project-scoped.
- Not headless-first. `main.py` runs the pipeline standalone but the canonical
  entrypoint for non-developer use is `app.py`.

---

## TL;DR for someone new

1. `python app.py` boots the desktop UI.
2. The UI's Executer page calls `run_pipeline_async`, which goes through
   `run_orchestrator.run_pipeline_controlled` → builds Flat GED → runs the 11
   pipeline stages → registers artifacts in `run_memory.db`.
3. The UI's Overview / Consultants / Fiche / Runs / Reports pages are read-only
   over the registered artifacts (loaded by `src/reporting/data_loader.py`
   into a `RunContext`, then aggregated/adapted in `src/reporting/*`).
4. `run_chain_onion.py` is a **separate** runner producing `output/chain_onion/*`
   which is read by `chain_onion/query_hooks.py`. The main UI uses it only to
   narrow Focus to the live-operational subset.
