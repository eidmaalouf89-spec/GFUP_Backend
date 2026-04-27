# Flat GED → Backend Integration — Execution Plan

**Starting point:** Flat GED builder is stable and frozen. Produces `FLAT_GED.xlsx` (sheets `GED_RAW_FLAT`, `GED_OPERATIONS`, `DEBUG_TRACE`) + `run_report.json`. Batch mode emits `DEBUG_TRACE.csv` separately.

**Ending point:** Dashboard UI values are traceable back to flat GED truth, `clean_GF` is reconstructed from flat GED, and the codebase is ready for Chain/Onion and the cue engine.

**Target codebase:** `eidmaalouf89-spec/GFUP_Backend` (engine in `src/`, dashboard in `ui/`). The engine is the Phase 2–5 target; the dashboard is validated in Phase 5.

---

## Part 1 — Executive roadmap

```
Phase 2 — Integration                (Steps 1–4)
  Freeze flat builder · define input contract · vendor into repo ·
  add flat-GED mode to pipeline behind a flag · parity harness old-vs-new

Phase 3 — Reports ingestion audit    (Steps 5–6)
  Map where reports enter today · document override semantics ·
  define how flat GED + report memory compose

Phase 4 — clean_GF reconstruction    (Steps 7–9)
  Build clean_GF from flat GED (logical fidelity first, formatting last) ·
  row-level diff against current GF output

Phase 5 — UI validation              (Steps 10–11)
  Every dashboard number traceable to a flat-GED query · KPI / backlog / late /
  drilldown parity · conflict handling spec

VALIDATION GATE — before any enrichment

Phase 6 — Chain + Onion              (Step 12, placeholder only)
Phase 7 — Cue engine                 (Step 13, placeholder only)
```

**Design principles enforced throughout:**

1. Foundation before intelligence — flat GED is the base layer.
2. Old path runs in parallel until parity is proven — no silent cutovers.
3. Every step is an independent Cowork chat input.
4. Hard validation gates between phases.

---

## Part 2 — Detailed Cowork steps

Each step below is structured so it can be pasted into a fresh Cowork chat. The **Work** section is the technical scope; the **Acceptance criteria** section is what Eid checks before marking the step done.

---

### STEP 1 — Freeze flat builder + define Flat GED Input Contract (FGIC)

**Objective.** Produce a single source-of-truth document (`docs/FLAT_GED_CONTRACT.md`) that any downstream code can rely on without reading the builder's source. This is the formal handshake between the builder and the engine.

**Inputs.**
- `ged_flat_builder/` (frozen source, already working)
- `ged_flat_builder/README.md`
- `ged_flat_builder/writer.py` (column lists `R_COLS`, `O_COLS`, `D_COLS`)
- `ged_flat_builder/source_main/ged_parser_contract.py`

**Work.**
1. Create `docs/FLAT_GED_CONTRACT.md` in the repo.
2. Document the three output tables by column, with type and meaning (copy schema from `writer.py`; do not invent fields). For each column state: `name`, `type`, `nullable (Y/N)`, `one-line meaning`, `source` (raw GED vs computed).
3. Document the `run_report.json` schema.
4. Document the **batch vs single** difference explicitly (batch emits CSV for DEBUG_TRACE, single emits it inside the workbook).
5. Document the nine business rules from the README verbatim (DATA_DATE, no-NUMERO exclusion, status normalization, SAS three states, two-phase deadline, delay contribution, cycle closure, candidate resolution, step ordering).
6. Declare the contract version (`v1.0`).

**Outputs.**
- `docs/FLAT_GED_CONTRACT.md`

**Acceptance criteria.**
- Every column in `GED_RAW_FLAT`, `GED_OPERATIONS`, `DEBUG_TRACE` is listed.
- Every field in `run_report.json` is listed.
- A reader who has never seen the builder can describe what a single ops row means from the doc alone.
- No business rule in the doc contradicts `ged_flat_builder/README.md` §"Business rules preserved from prototype_v4.py".

**Dependencies.** None (starts from frozen builder).

---

### STEP 2 — Vendor flat builder into repo as `src/flat_ged/`

**Objective.** Bring the builder into `GFUP_Backend` as an importable package, without changing its behaviour and without wiring it into the pipeline yet.

**Inputs.**
- Step 1 outputs.
- `ged_flat_builder/` (entire folder).

**Work.**
1. Copy `ged_flat_builder/` → `src/flat_ged/` preserving file names: `config.py`, `utils.py`, `reader.py`, `resolver.py`, `transformer.py`, `validator.py`, `writer.py`, `main.py` → rename `main.py` to `cli.py` to avoid confusion with repo-root `main.py`.
2. Move `source_main/` contents to `src/flat_ged/source_main/` (keep the same filenames).
3. Fix relative imports so the package imports cleanly (`from src.flat_ged import ...`).
4. Delete `__pycache__/` and `output/` artifacts. Leave `input/` out — not committed.
5. Add `src/flat_ged/__init__.py` exporting a single public function:
   ```python
   def build_flat_ged(ged_xlsx_path: Path, output_dir: Path, *, mode: str = "batch",
                      numero: int | None = None, indice: str | None = None) -> dict:
       """Returns run_report dict. Side effect: writes FLAT_GED.xlsx + run_report.json."""
   ```
6. Add `tests/flat_ged/test_smoke.py` — runs batch mode on `input/GED_export.xlsx`, asserts the workbook exists, asserts `run_report["failure_count"] == 0`.
7. Do **not** touch any other `src/` file. Do **not** wire into `main.py`.

**Outputs.**
- `src/flat_ged/` (vendored package)
- `src/flat_ged/__init__.py` with `build_flat_ged()`
- `tests/flat_ged/test_smoke.py`

**Acceptance criteria.**
- `python -c "from src.flat_ged import build_flat_ged; print(build_flat_ged)"` succeeds.
- Smoke test passes on the real GED export.
- `git diff src/` outside `src/flat_ged/` shows zero lines changed.
- `pytest tests/flat_ged/` completes in < 60s and reports 0 failures.

**Dependencies.** Step 1.

---

### STEP 3 — Inventory current GED entry points in the engine

**Objective.** Before adding flat-GED as a new input mode, map the exact points in the current pipeline where raw GED enters and what downstream consumers expect. This is a **read-only audit** — no code changes.

**Inputs.**
- Repo (main).
- Key files to inspect (from repo tree):
  - `src/read_raw.py`
  - `src/normalize.py`
  - `src/version_engine.py`
  - `src/workflow_engine.py`
  - `src/domain/normalization.py`
  - `src/domain/sas_helpers.py`
  - `src/pipeline/stages/stage_read.py`
  - `src/pipeline/stages/stage_normalize.py`
  - `src/pipeline/stages/stage_version.py`
  - `src/pipeline/runner.py`
  - `src/pipeline/context.py`

**Work.**
1. Produce `docs/GED_ENTRY_AUDIT.md` with these sections:
   - **A. Read layer.** What `read_raw.py` returns — exact data structures (dict keys, DataFrame columns, list-of-tuples, whatever it actually is). Read the code, do not infer.
   - **B. Normalize layer.** What `normalize.py` does to raw GED — list every transformation (status codes, pending keywords, NOT_CALLED logic, date parsing). Quote the function names.
   - **C. SAS handling.** Where SAS state is classified — `src/domain/sas_helpers.py` + any other location. Compare against flat builder §4 (ABSENT / PENDING / ANSWERED) and note semantic differences.
   - **D. Version/family.** What `version_engine.py` produces — family IDs, latest-index logic. Note whether flat GED produces anything equivalent (it does NOT — flat GED is per (numero, indice)).
   - **E. Workflow engine inputs.** What exact structure `workflow_engine.py` consumes. This is the main integration target.
   - **F. Pipeline stages.** For each file in `src/pipeline/stages/`, write 2 sentences: what it reads, what it writes into `RunContext`.
3. At the end, produce a **Gap matrix** table with columns: `Engine artifact | Flat GED equivalent | Gap`. Example rows: `"normalized responses"`, `"effective responses"`, `"SAS classification"`, `"cycle closure"`, `"delay computation"`.

**Outputs.**
- `docs/GED_ENTRY_AUDIT.md`

**Acceptance criteria.**
- Every file listed above has a paragraph in the audit.
- The gap matrix has at least 6 rows and each row states concretely which flat GED column or table fills the gap (or explicitly "nothing — needs new adapter").
- No engine source file is modified.

**Dependencies.** Step 2.

---

### STEP 4 — Add Flat-GED mode behind a feature flag (parallel, not replacement)

**Objective.** Add a new input path that consumes flat GED instead of raw GED, **running alongside** the existing path. No existing behaviour changes when the flag is off.

**Inputs.**
- Step 3 gap matrix.
- `src/pipeline/runner.py`, `src/pipeline/context.py`, `src/pipeline/stages/stage_read.py`, `src/pipeline/stages/stage_normalize.py`.

**Work.**
1. Add a config flag `flat_ged_mode: bool = False` (default OFF) to `RunContext`. Honour an environment variable `GFUP_FLAT_GED=1` to set it.
2. Create `src/pipeline/stages/stage_read_flat.py` that:
   - Takes `ctx`
   - Calls `src.flat_ged.build_flat_ged()` to produce `FLAT_GED.xlsx` under the run's working directory
   - Loads the two batch sheets (`GED_RAW_FLAT`, `GED_OPERATIONS`) into in-memory structures matching **exactly** what `stage_read.py` produces. The adapter does the translation — downstream stages stay untouched.
3. Modify `runner.py` so the read stage is chosen based on `ctx.flat_ged_mode`:
   - Flag OFF → `stage_read` (existing path, unchanged)
   - Flag ON  → `stage_read_flat` (new path)
4. Add `tests/pipeline/test_flat_ged_mode_smoke.py` — runs both modes on the same input, asserts both produce non-empty outputs, prints a summary of row counts from each.
5. Do NOT modify `stage_read.py`. Do NOT modify any stage after `stage_read`.

**Outputs.**
- `src/pipeline/stages/stage_read_flat.py`
- Modified `src/pipeline/runner.py` (branching)
- Modified `src/pipeline/context.py` (new flag)
- `tests/pipeline/test_flat_ged_mode_smoke.py`

**Acceptance criteria.**
- With the flag OFF, the test suite passes identically to before Step 4 (run `pytest` both pre- and post-change, compare output).
- With `GFUP_FLAT_GED=1`, `python main.py` completes end-to-end without crashing on the real GED export.
- `tests/pipeline/test_flat_ged_mode_smoke.py` passes.

**Dependencies.** Steps 2, 3.

---

### STEP 5 — Old-vs-new parity harness

**Objective.** Prove the two read paths produce equivalent downstream state. This is the gate before trusting flat GED as truth.

**Inputs.**
- Step 4 branching in place.
- A real GED export (`input/GED_export.xlsx`).

**Work.**
1. Create `scripts/parity_harness.py` that:
   - Runs the full pipeline twice on the same input (flag OFF, then flag ON), into two separate output directories.
   - Loads both resulting `GF_V0_CLEAN.xlsx` files.
   - Compares them cell-by-cell (openpyxl, not pandas — we need formula-cached values).
   - For every cell that differs: records `(sheet, cell_ref, old_value, new_value, row_context)`.
   - Writes `output/parity_report.xlsx` with sheets `SUMMARY`, `DIFFERENCES`, `IDENTICAL_CELL_COUNT`.
2. Classify every difference into one of four buckets (add this as a column in `DIFFERENCES`):
   - `BENIGN_WHITESPACE` (trimmed spaces, case)
   - `SEMANTIC_EQUIVALENT` (e.g. `None` vs empty string, equivalent status codes)
   - `KNOWN_GAP` (flat builder deliberately doesn't produce this — e.g. version-family columns)
   - `REAL_DIVERGENCE` (requires fix)
3. Print a one-line verdict: `PARITY_PASS` / `PARITY_FAIL` based on whether REAL_DIVERGENCE count is zero.

**Outputs.**
- `scripts/parity_harness.py`
- `output/parity_report.xlsx`

**Acceptance criteria.**
- Harness runs in < 10 minutes on the full database.
- Verdict prints clearly.
- If `PARITY_FAIL`, the `REAL_DIVERGENCE` sheet has ≤ 50 rows (if more, we stop and debug before declaring Phase 2 done).

**Dependencies.** Step 4.

**⚠ GATE 1** — We do not proceed to Phase 3 until `PARITY_PASS` or the residual REAL_DIVERGENCE is explained and deliberately accepted.

---

### STEP 6 — Reports ingestion audit (read-only)

**Objective.** Document exactly how consultant reports currently enter the engine and interact with GED truth. No code changes.

**Inputs.**
- Repo files to inspect:
  - `src/consultant_ingest/` (all files)
  - `src/consultant_integration.py`
  - `src/consultant_matcher.py`
  - `src/consultant_match_report.py`
  - `src/report_memory.py`
  - `src/effective_responses.py`
  - `src/pipeline/stages/stage_report_memory.py`
  - `src/reporting/bet_report_merger.py`

**Work.**
1. Produce `docs/REPORTS_INGESTION_AUDIT.md` with:
   - **A. Ingest path.** Per-consultant ingestor (AVLS, Socotec, Le Sommer, Terrell) — what each extracts from its PDF/Excel.
   - **B. Matching.** How reports are matched to GED rows (by numero, indice, title, date). Confidence model. Thresholds.
   - **C. Persistence.** Report memory schema (read `report_memory.py`). What is persisted across runs.
   - **D. Merge semantics.** `effective_responses.py` — exactly under what conditions a report upgrades a GED row. Read the code, quote the function.
   - **E. Override vs enrich.** Classify each merge rule: does it override GED truth, or only fill gaps? This is the question the planning prompt specifically asked about.
   - **F. Interaction with flat GED.** Given flat GED already produces `response_status_clean`, `response_date`, `is_completed` — does report memory write into the same conceptual slot? Produce a mapping table.
2. Flag any merge rule that would **conflict** with flat GED truth (e.g. flat GED says `ANSWERED` on date X, report memory says `ANSWERED` on date Y).

**Outputs.**
- `docs/REPORTS_INGESTION_AUDIT.md`

**Acceptance criteria.**
- Each of the 4 consultant ingestors has its own subsection.
- The override-vs-enrich classification is explicit for every rule.
- The mapping table has a row for every flat GED field that report memory could touch.

**Dependencies.** Step 1 (contract), Step 3 (engine audit). Can run in parallel with Steps 4–5 because it's read-only.

---

### STEP 7 — Flat GED + Report memory composition spec

**Objective.** Given Steps 5 and 6, decide and document the composition rules. This is a **design step**, not code.

**Inputs.**
- `docs/FLAT_GED_CONTRACT.md` (Step 1)
- `docs/REPORTS_INGESTION_AUDIT.md` (Step 6)
- Parity report (Step 5)

**Work.**
1. Produce `docs/FLAT_GED_REPORT_COMPOSITION.md` specifying:
   - **Precedence rule.** Propose: flat GED is truth for `is_completed=True` rows; report memory only upgrades flat-GED `PENDING` rows. Document and justify.
   - **Conflict rule.** When flat GED and report memory disagree on a completed row, which wins and why.
   - **New-response rule.** When report memory has an answer for a GED row flat GED classifies as `NOT_CALLED`, what happens (hypothesis: flagged for review, not auto-accepted).
   - **Date reconciliation.** When response dates differ between sources.
2. List 10 concrete (numero, indice) examples from the real database that exercise each rule. Use `output/FLAT_GED.xlsx` + existing report memory to find them.

**Outputs.**
- `docs/FLAT_GED_REPORT_COMPOSITION.md`

**Acceptance criteria.**
- Every merge case from Step 6 has a rule in this doc.
- 10 real examples listed.
- Doc is reviewed and accepted by Eid before Step 8 starts.

**Dependencies.** Steps 5, 6.

---

### STEP 8 — clean_GF reconstruction: logical layer

**Objective.** Rebuild `clean_GF` content (rows, statuses, observations) from flat GED + report memory, **ignoring formatting**. One function in, one DataFrame-like structure out.

**Inputs.**
- Step 7 composition spec.
- `src/flat_ged/` (frozen).
- `src/effective_responses.py` (reference only).
- `src/workflow_engine.py` (reference for responsibility/VISA GLOBAL logic).
- `src/writer.py` (reference for the existing GF output shape).

**Work.**
1. Create `src/clean_gf/reconstruct.py` with a single entry point:
   ```python
   def reconstruct_clean_gf_rows(flat_ged_path: Path, report_memory_db: Path | None) -> list[dict]:
       """Returns one dict per (numero, indice) GF row, content-only, no formatting."""
   ```
2. The output is a list of dicts. Each dict's keys exactly match the content columns of the current `GF_V0_CLEAN.xlsx` (not its formatting — no merged cells, colours, column widths). Read the existing writer to get the column list.
3. For each GF column, populate from:
   - Flat GED first (per Step 7 precedence)
   - Report memory overlay (per Step 7 rules)
   - Computed fields (responsibility, `VISA GLOBAL`) — delegate to existing helpers in `src/workflow_engine.py` and `src/domain/` where possible. Do NOT reimplement.
4. Add `tests/clean_gf/test_reconstruct_content.py` asserting:
   - Output length equals number of unique (numero, indice) pairs in flat GED.
   - No row has both `is_completed=True` and null `response_date`.
   - Every row has a non-null `LOT`.

**Outputs.**
- `src/clean_gf/reconstruct.py`
- `src/clean_gf/__init__.py`
- `tests/clean_gf/test_reconstruct_content.py`

**Acceptance criteria.**
- Test passes on real data.
- Function completes in < 30s on the full database.
- Does NOT write any file (that's Step 9).

**Dependencies.** Step 7.

---

### STEP 9 — clean_GF row-level diff vs current output

**Objective.** Compare Step 8 output against the current `GF_V0_CLEAN.xlsx` produced by the existing engine. This is the logical-fidelity proof.

**Inputs.**
- Output of Step 8: `reconstruct_clean_gf_rows()`.
- Current pipeline's `GF_V0_CLEAN.xlsx` (run the engine once fresh to produce it).

**Work.**
1. Create `scripts/clean_gf_diff.py` that:
   - Calls `reconstruct_clean_gf_rows()` → new rows.
   - Opens `GF_V0_CLEAN.xlsx` from the reference run → old rows.
   - Indexes both by `(numero, indice)`.
   - For each row present in one but not the other → log.
   - For each matched row, compares all content columns → log differences.
2. Produce `output/clean_gf_diff.xlsx` with sheets:
   - `ONLY_IN_NEW` (rows flat-GED-based reconstruction has)
   - `ONLY_IN_OLD` (rows only the current GF has)
   - `FIELD_DIFFS` (one row per differing field: numero, indice, column, old, new, bucket)
   - `SUMMARY` (counts by bucket)
3. Bucket field differences into: `IDENTICAL`, `BENIGN` (whitespace/None-vs-empty), `KNOWN_ENRICHMENT_GAP` (fields set only by the old path because we haven't ported that step yet), `REAL_DIVERGENCE`.

**Outputs.**
- `scripts/clean_gf_diff.py`
- `output/clean_gf_diff.xlsx`

**Acceptance criteria.**
- Script completes without error.
- `REAL_DIVERGENCE` bucket count is triaged: either 0, or each difference has a documented reason in `docs/clean_gf_reconstruction_gaps.md`.

**Dependencies.** Step 8.

**⚠ GATE 2** — We do not proceed to Phase 5 until the logical diff is clean or every divergence is explained.

---

### STEP 10 — UI source-of-truth map

**Objective.** For every number the dashboard displays, identify the exact flat-GED query (or flat-GED + report memory query) that produces it. No UI changes yet.

**Inputs.**
- `ui/` and `ui/jansa/` prototype files.
- `src/reporting/` (`aggregator.py`, `consultant_fiche.py`, `contractor_fiche.py`, `data_loader.py`, `ui_adapter.py`, `focus_filter.py`, `focus_ownership.py`).
- `docs/JANSA_PARITY_STEP_*` docs (existing parity plans).

**Work.**
1. Produce `docs/UI_SOURCE_OF_TRUTH_MAP.md` with one entry per UI surface:
   - **Overview KPIs** (total docs, open docs, late docs, on-time rate) — each KPI gets a flat-GED query description.
   - **Consultant list** (14 consultants, count columns) — per-column query.
   - **Consultant fiche** — Block 1 (monthly n and %), Block 2 (combo chart), Block 3 (per-lot table) — each a flat-GED query.
   - **Drilldowns** — for each drilldown, the filter expression over flat GED.
   - **Backlog counts** — definition (open + date_limite past) expressed as a flat GED filter.
   - **Late counts** — definition using `DATA_DATE` (the from-Détails date, not `datetime.now`).
2. For each entry, write the query in pseudocode against the flat GED tables:
   ```
   backlog_for_consultant(c) =
     count(GED_OPERATIONS
           where step_type == "CONSULTANT"
             and actor_clean == c
             and is_completed == False)
   ```
3. Flag any UI value that **cannot** be produced from flat GED alone — those depend on report memory, and we make the dependency explicit.

**Outputs.**
- `docs/UI_SOURCE_OF_TRUTH_MAP.md`

**Acceptance criteria.**
- Every KPI, badge, count, chart series in the dashboard has a query.
- No query references "current date" — all use flat GED's `data_date`.
- Report-memory dependencies are flagged.

**Dependencies.** Steps 7, 8.

---

### STEP 11 — UI value validation harness

**Objective.** Compute every mapped UI value two ways — via the current dashboard data path, and via a direct flat-GED query. Compare.

**Inputs.**
- Step 10 source-of-truth map.
- Current `src/reporting/aggregator.py` and `src/reporting/ui_adapter.py` (existing data path).
- `src/flat_ged/` + flat GED output.

**Work.**
1. Create `scripts/ui_parity_harness.py` that:
   - For each UI surface in Step 10, computes the value using the existing `reporting/` functions (the dashboard's current data source).
   - Computes the same value using direct flat-GED queries (reimplemented minimally inline in the script — no new library yet).
   - Logs every (surface, value_old, value_new, bucket).
2. Bucket differences into `IDENTICAL`, `BENIGN_ROUNDING`, `REAL_DIVERGENCE`.
3. Produce `output/ui_parity_report.xlsx` with the full breakdown.

**Outputs.**
- `scripts/ui_parity_harness.py`
- `output/ui_parity_report.xlsx`

**Acceptance criteria.**
- Every UI surface listed in Step 10 appears in the report.
- `REAL_DIVERGENCE` count is zero, or each divergence is triaged in `docs/ui_parity_gaps.md`.

**Dependencies.** Steps 9, 10.

**⚠ GATE 3** — We do not proceed to Phase 6/7 (enrichment) until UI parity is clean. This is the last and most important gate — it means the dashboard the user sees is traceable to flat GED.

---

### STEP 12 — Chain + Onion (placeholder)

**Objective.** Implement the Chain + Onion methodology on top of a validated flat-GED foundation.

**Scope deferred.** This step is not specified in detail in the current plan. Its inputs will be: Steps 9, 11 both passed, and `docs/CHAIN_ONION_METHODOLOGY.md` (not yet written — a prerequisite).

**Explicit dependency.** Gate 3 passed.

---

### STEP 13 — Cue engine (placeholder)

**Objective.** Add the cue engine once Chain + Onion is in.

**Scope deferred.** Depends on Step 12.

---

## Part 3 — Execution order

**Strictly sequential backbone:**

```
1 → 2 → 3 → 4 → 5 (GATE 1) → 7 → 8 → 9 (GATE 2) → 10 → 11 (GATE 3) → 12 → 13
```

**Parallelisable:**

- **Step 6** (reports audit, read-only) can run in parallel with Steps 4 and 5 once Steps 1–3 are done. Step 7 needs both Step 5 and Step 6 to be done before it starts.
- **Step 10** (UI source-of-truth map, read-only doc) can start as soon as Step 8 is done — no need to wait for Step 9 (the diff) to finish. Step 11 still needs Step 9.

**Critical path length:** 1 → 2 → 3 → 4 → 5 → 7 → 8 → 9 → 10 → 11 = 10 steps. Steps 6, 12, 13 are off the critical path.

---

## Part 4 — Validation gates

These are the "do not move forward until this passes" checkpoints.

| Gate | After step | Pass criterion | If it fails |
|------|-----------|----------------|-------------|
| **GATE 1** — Read-path parity | Step 5 | `PARITY_PASS` or every REAL_DIVERGENCE documented and accepted | Debug differences; do not start Step 7. Root cause is usually a stage-read adapter mismatch — inspect that first. |
| **GATE 2** — Logical GF fidelity | Step 9 | `REAL_DIVERGENCE` = 0 or explained | Debug in `reconstruct.py`; do not start Step 10. Do NOT fix by changing the flat builder — flat builder is frozen. |
| **GATE 3** — UI parity | Step 11 | `REAL_DIVERGENCE` = 0 or explained | Debug in `reporting/` layer or in Step 10 query specs. Do NOT start enrichment (Chain/Onion, cue engine) until clean. |

**A gate can only be passed in one of two ways:**

1. Zero real divergences.
2. Every real divergence has a written explanation in a gaps document, reviewed by Eid, stating either (a) why it's not actually a bug, or (b) which future step will fix it.

No third path. "Looks close enough" is not a pass.

---

## What this plan deliberately avoids

- **No formatting work on clean_GF** until content is right (Step 8 is content-only).
- **No chain/onion logic** embedded anywhere in Steps 1–11.
- **No cue engine** before UI parity.
- **No new dashboard features** before old values are verified against flat GED.
- **No silent cutovers** — flat-GED mode is flag-gated in Step 4 and only becomes default after Gate 1 passes.
- **No builder modifications** — the flat GED builder is frozen. Every integration compromise happens on the engine side, never in the builder.
