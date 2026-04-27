# Flat GED → Backend Integration — Execution Plan (v2)

**Starting point:** Flat GED builder is stable and frozen. Produces `FLAT_GED.xlsx` (sheets `GED_RAW_FLAT`, `GED_OPERATIONS`, `DEBUG_TRACE`) + `run_report.json`. Batch mode emits `DEBUG_TRACE.csv` separately.

**Ending point:** Dashboard UI values are traceable back to flat GED truth via a shared query library, `clean_GF` is reconstructed from flat GED, and the codebase is ready for Chain/Onion and the cue engine.

**Target codebase:** `eidmaalouf89-spec/GFUP_Backend` (engine in `src/`, dashboard in `ui/`).

**Changes from v1** (in response to review):
- Step 2: adds version stamp and "do not edit business rules" rule to prevent snapshot drift.
- Step 3b: new — backend semantic contract, defining what must survive integration.
- Step 4: adapter must include a mapping table; no black-box imitation of old semantics.
- Step 5: `OLD_PATH_BUG` added as a parity bucket; gate reframed as "does not break downstream" not "matches old exactly".
- Step 7: classifies report fields (`augments_operational_truth` / `fills_missing_evidence` / `presentation_only`).
- Step 8/9: explicit constraint that reconstruction is document-code level; submission-instance differences deliberately collapsed for this phase.
- Step 9b: formatting fidelity, explicit placeholder.
- Step 9c: new — shared flat-GED query library, extracted from Step 8 and used by Steps 10–13.
- Step 10: UI values classified as `document-code level` vs `submission-instance level`.
- Step 11: harness uses query library, does not reimplement inline.

---

## Part 1 — Executive roadmap

```
Phase 2 — Integration                (Steps 1–5)
  1  Freeze flat builder + define Flat GED Input Contract
  2  Vendor flat builder as frozen snapshot (VERSION stamp)
  3  Audit current GED entry points
  3b Backend semantic contract
  4  Add flat-GED mode behind a feature flag
  5  Old-vs-new parity harness            ⚠ GATE 1

Phase 3 — Reports ingestion audit    (Steps 6–7)
  6  Map where reports enter + override vs enrich
  7  Composition spec + field classification

Phase 4 — clean_GF reconstruction    (Steps 8–9c)
  8  Logical reconstruction (document-code level)
  9  Row-level diff vs current GF         ⚠ GATE 2
  9b Formatting fidelity (DEFERRED PLACEHOLDER)
  9c Shared flat-GED query library

Phase 5 — UI validation              (Steps 10–11)
  10 UI source-of-truth map (uses 9c)
  11 UI parity harness (uses 9c)          ⚠ GATE 3

Phase 6 — Chain + Onion              (Step 12, placeholder)
Phase 7 — Cue engine                 (Step 13, placeholder)
```

**Design principles:**

1. Foundation before intelligence — flat GED is the base layer.
2. Old path is a transition reference, not gold standard. Differences can be flat-GED-correct.
3. Every step is an independent Cowork chat input.
4. Three hard gates between phases.
5. Shared definitions live in one query library — not duplicated across clean_GF, UI, and cue engine.

---

## Part 2 — Detailed Cowork steps

### STEP 1 — Freeze flat builder + define Flat GED Input Contract (FGIC)

**Objective.** Produce a single source-of-truth document (`docs/FLAT_GED_CONTRACT.md`) that any downstream code can rely on without reading the builder's source.

**Inputs.**
- `ged_flat_builder/` (frozen source, already working)
- `ged_flat_builder/README.md`
- `ged_flat_builder/writer.py` (column lists `R_COLS`, `O_COLS`, `D_COLS`)
- `ged_flat_builder/source_main/ged_parser_contract.py`

**Work.**
1. Create `docs/FLAT_GED_CONTRACT.md`.
2. Document the three output tables by column, with type and meaning (copy schema from `writer.py`; do not invent fields). For each column: `name`, `type`, `nullable (Y/N)`, `one-line meaning`, `source` (raw GED vs computed).
3. Document the `run_report.json` schema.
4. Document the **batch vs single** difference (batch emits CSV for DEBUG_TRACE, single emits in workbook).
5. Document the nine business rules from the README verbatim.
6. Declare contract version (`v1.0`).

**Outputs.** `docs/FLAT_GED_CONTRACT.md`

**Acceptance criteria.**
- Every column in `GED_RAW_FLAT`, `GED_OPERATIONS`, `DEBUG_TRACE` listed.
- Every `run_report.json` field listed.
- A reader who has never seen the builder can describe what a single ops row means from the doc alone.
- No business rule in the doc contradicts `ged_flat_builder/README.md` §"Business rules preserved from prototype_v4.py".

**Dependencies.** None.

---

### STEP 2 — Vendor flat builder as frozen snapshot

**Objective.** Bring the builder into `GFUP_Backend` as a **frozen snapshot**, not a second editable copy.

**Inputs.** Step 1, `ged_flat_builder/` folder.

**Work.**
1. Copy `ged_flat_builder/` → `src/flat_ged/` preserving file names: `config.py`, `utils.py`, `reader.py`, `resolver.py`, `transformer.py`, `validator.py`, `writer.py`, `main.py` → rename `main.py` to `cli.py`.
2. Move `source_main/` contents to `src/flat_ged/source_main/`.
3. Fix relative imports so the package imports cleanly.
4. Delete `__pycache__/` and `output/` artifacts. Leave `input/` out.
5. Add `src/flat_ged/__init__.py` exporting:
   ```python
   def build_flat_ged(ged_xlsx_path: Path, output_dir: Path, *, mode: str = "batch",
                      numero: int | None = None, indice: str | None = None) -> dict:
       """Returns run_report dict. Side effect: writes FLAT_GED.xlsx + run_report.json."""
   ```
6. **Frozen-snapshot discipline.** Create `src/flat_ged/VERSION.txt`:
   ```
   flat_ged_builder snapshot
   source_commit: <commit sha from ged_flat_builder/ — record even if manual>
   snapshot_date: YYYY-MM-DD
   contract_version: v1.0   (matches docs/FLAT_GED_CONTRACT.md)
   source_of_truth_location: <path or URL to the external builder repo>

   DO NOT edit business rules in this folder.
   Bug fixes flow upstream first, then a new snapshot is taken.
   Adapter changes go in src/pipeline/stages/stage_read_flat.py, never here.
   ```
7. Create `src/flat_ged/BUILD_SOURCE.md` explaining:
   - How to re-sync from upstream (manual copy procedure).
   - What files are allowed to change here (nothing in `config.py`, `resolver.py`, `transformer.py`, `validator.py`, `utils.py`, `source_main/`).
   - The only permitted local-only edits: import path fixes in `__init__.py`, `cli.py`, and `reader.py` file-path handling.
8. Add `tests/flat_ged/test_smoke.py` — runs batch mode on `input/GED_export.xlsx`, asserts workbook exists, asserts `run_report["failure_count"] == 0`.
9. Do NOT touch any other `src/` file. Do NOT wire into `main.py`.

**Outputs.**
- `src/flat_ged/` (vendored)
- `src/flat_ged/__init__.py` with `build_flat_ged()`
- `src/flat_ged/VERSION.txt`
- `src/flat_ged/BUILD_SOURCE.md`
- `tests/flat_ged/test_smoke.py`

**Acceptance criteria.**
- `python -c "from src.flat_ged import build_flat_ged; print(build_flat_ged)"` succeeds.
- Smoke test passes on real GED export.
- `git diff src/` outside `src/flat_ged/` shows zero lines changed.
- `VERSION.txt` and `BUILD_SOURCE.md` both exist and state the source commit + resync procedure.

**Dependencies.** Step 1.

---

### STEP 3 — Inventory current GED entry points in the engine

**Objective.** Map the exact points in the current pipeline where raw GED enters and what downstream consumers expect. Read-only audit.

**Inputs.** Repo (main). Files:
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

**Work.** Produce `docs/GED_ENTRY_AUDIT.md` with:
- **A. Read layer.** What `read_raw.py` returns — exact data structures. Read the code, don't infer.
- **B. Normalize layer.** What `normalize.py` does — every transformation, function names quoted.
- **C. SAS handling.** Where SAS state is classified. Compare against flat builder's three states (ABSENT / PENDING / ANSWERED) and note semantic differences.
- **D. Version/family.** What `version_engine.py` produces. Note flat GED produces NO equivalent.
- **E. Workflow engine inputs.** Exact structure `workflow_engine.py` consumes. Main integration target.
- **F. Pipeline stages.** For each file in `src/pipeline/stages/`: 2 sentences — what it reads, what it writes into `RunContext`.
- **Gap matrix.** Table `Engine artifact | Flat GED equivalent | Gap`. ≥6 rows. Each row states concretely which flat GED column/table fills the gap, or "nothing — needs new adapter".

**Outputs.** `docs/GED_ENTRY_AUDIT.md`

**Acceptance criteria.**
- Every listed file has a paragraph.
- Gap matrix has ≥6 rows with concrete fillers.
- No engine source file modified.

**Dependencies.** Step 2.

---

### STEP 3b — Backend semantic contract

**Objective.** Define the backend concepts that must survive flat-GED integration. This is the checklist Step 4 adapter must satisfy. Without this, Step 4 risks imitating old *implementation* instead of preserving *semantics*.

**Inputs.**
- `docs/GED_ENTRY_AUDIT.md` (Step 3)
- `docs/FLAT_GED_CONTRACT.md` (Step 1)
- `src/effective_responses.py`, `src/workflow_engine.py`, `src/domain/` (reference)

**Work.** Produce `docs/BACKEND_SEMANTIC_CONTRACT.md` with one subsection per concept. For each:
- **Definition** in one sentence.
- **Where it's computed today** — file + function.
- **What flat GED provides** — which column/field.
- **Gap** — what the adapter (or a post-adapter step) must fill.
- **Invariants** — conditions that must hold after integration.

Required concepts (minimum):

1. **Effective response.** GED response + report memory overlay.
2. **Blocking.** Which rows hold up progression.
3. **Cycle closure.** `MOEX_VISA` / `ALL_RESPONDED_NO_MOEX` / `WAITING_RESPONSES`.
4. **VISA GLOBAL.** Never computed by pipeline — equals MOEX GEMO column verbatim. Must survive.
5. **Responsibility.** Contractor / consultant(s) / MOEX / closed.
6. **Pending vs late.** Distinction using `data_date` from GED `Détails!D15`, never `datetime.now()`.
7. **SAS semantics.** Three states + two-phase deadline model.
8. **Delay contribution.** No double-counting, four invariants from flat builder §6.

**Outputs.** `docs/BACKEND_SEMANTIC_CONTRACT.md`

**Acceptance criteria.**
- All 8 concepts documented.
- Each has a cited source location in `src/`.
- Each has at least one invariant that can be expressed as a programmatic check.
- Eid accepts the doc before Step 4 starts.

**Dependencies.** Steps 1, 3.

---

### STEP 4 — Add Flat-GED mode behind a feature flag (parallel, not replacement)

**Objective.** Add a new input path that consumes flat GED instead of raw GED, **running alongside** the existing path. Adapter is transparent, not black-box.

**Inputs.**
- `docs/BACKEND_SEMANTIC_CONTRACT.md` (Step 3b) — concepts the adapter must preserve.
- `docs/GED_ENTRY_AUDIT.md` gap matrix (Step 3).
- `src/pipeline/runner.py`, `src/pipeline/context.py`, `src/pipeline/stages/stage_read.py`, `src/pipeline/stages/stage_normalize.py`.

**Work.**
1. Add config flag `flat_ged_mode: bool = False` (default OFF) to `RunContext`. Honour env var `GFUP_FLAT_GED=1`.
2. Create `src/pipeline/stages/stage_read_flat.py` that:
   - Takes `ctx`
   - Calls `src.flat_ged.build_flat_ged()` to produce `FLAT_GED.xlsx` in the run's working directory
   - Loads the two batch sheets into in-memory structures consumable by the next stage
3. **Mapping table — mandatory deliverable.** Create `docs/FLAT_GED_ADAPTER_MAP.md` with a table, one row per old-artifact field that `stage_read_flat` produces. Columns:
   - `old_artifact_field` — the field name the downstream stage expects today
   - `flat_ged_source` — which table + column in flat GED it comes from
   - `transformation` — "pass-through" / "rename" / "type-coerce" / "synthesize-from-X-and-Y" / "placeholder (gap)"
   - `semantic_contract_ref` — which concept from Step 3b this preserves (if any)
   - `notes` — any subtlety

   **No entry may be transformation = "synthesize" without pointing at the corresponding Step 3b concept.** This prevents the adapter from silently inventing semantics.
4. Modify `runner.py` so read stage is chosen based on `ctx.flat_ged_mode`:
   - Flag OFF → `stage_read` (unchanged)
   - Flag ON → `stage_read_flat`
5. Add `tests/pipeline/test_flat_ged_mode_smoke.py` — runs both modes on the same input, asserts both produce non-empty outputs, prints row count summary.
6. Do NOT modify `stage_read.py`. Do NOT modify any stage after `stage_read`.

**Outputs.**
- `src/pipeline/stages/stage_read_flat.py`
- `docs/FLAT_GED_ADAPTER_MAP.md`
- Modified `src/pipeline/runner.py`, `src/pipeline/context.py`
- `tests/pipeline/test_flat_ged_mode_smoke.py`

**Acceptance criteria.**
- Flag OFF: test suite passes identically to before Step 4.
- Flag ON: `python main.py` completes on real GED export.
- Smoke test passes.
- Every field `stage_read_flat` writes appears in the adapter map table.
- No adapter field is unexplained.

**Dependencies.** Steps 2, 3, 3b.

---

### STEP 5 — Old-vs-new parity harness

**Objective.** Compare the two read paths' downstream state. Framed as "new path does not break expected behaviour" — **not** "matches old exactly." Differences can be flat-GED-correct.

**Inputs.** Step 4 branching in place, real GED export.

**Work.**
1. Create `scripts/parity_harness.py` that:
   - Runs full pipeline twice (flag OFF, then flag ON) into separate output directories.
   - Loads both resulting `GF_V0_CLEAN.xlsx` files.
   - Compares cell-by-cell with openpyxl (formula-cached values).
   - For every differing cell: records `(sheet, cell_ref, old_value, new_value, row_context)`.
   - Writes `output/parity_report.xlsx` with sheets `SUMMARY`, `DIFFERENCES`, `IDENTICAL_CELL_COUNT`.
2. Classify each difference into one of **five** buckets:
   - `BENIGN_WHITESPACE` — trimmed spaces, case.
   - `SEMANTIC_EQUIVALENT` — `None` vs empty string, equivalent status codes.
   - `KNOWN_GAP` — flat builder deliberately doesn't produce this (e.g. version-family columns).
   - `OLD_PATH_BUG` — new path is correct, old path was wrong. Each entry includes a one-line justification citing the semantic contract (Step 3b) or flat GED rules.
   - `REAL_DIVERGENCE` — needs fix in the adapter.
3. Print verdict: `PARITY_PASS` if `REAL_DIVERGENCE` count is zero. `OLD_PATH_BUG` rows do not fail the gate but are listed in summary as "corrections".

**Outputs.**
- `scripts/parity_harness.py`
- `output/parity_report.xlsx`

**Acceptance criteria.**
- Harness runs in < 10 min on full database.
- Verdict prints clearly.
- If `PARITY_FAIL`: `REAL_DIVERGENCE` ≤ 50 rows before triage begins.
- Every `OLD_PATH_BUG` entry has a written justification referencing Step 3b or the flat GED contract.

**Dependencies.** Step 4.

**⚠ GATE 1.** Pass = (`REAL_DIVERGENCE` = 0) AND (`OLD_PATH_BUG` items are all documented corrections, not hidden divergences). Old path is NOT the gold standard; flat GED can be correct where old path was wrong.

---

### STEP 6 — Reports ingestion audit (read-only)

**Objective.** Document how consultant reports currently enter and interact with GED truth.

**Inputs.**
- `src/consultant_ingest/` (all files)
- `src/consultant_integration.py`
- `src/consultant_matcher.py`
- `src/consultant_match_report.py`
- `src/report_memory.py`
- `src/effective_responses.py`
- `src/pipeline/stages/stage_report_memory.py`
- `src/reporting/bet_report_merger.py`

**Work.** Produce `docs/REPORTS_INGESTION_AUDIT.md` with:
- **A. Ingest path** — per-consultant ingestor (AVLS, Socotec, Le Sommer, Terrell): what each extracts.
- **B. Matching** — numero/indice/title/date rules, confidence model, thresholds.
- **C. Persistence** — report memory schema, what persists across runs.
- **D. Merge semantics** — `effective_responses.py` exact conditions under which report upgrades a GED row. Quote the function.
- **E. Override vs enrich** — classify each merge rule: overrides GED truth, or only fills gaps.
- **F. Interaction with flat GED** — given flat GED already produces `response_status_clean`, `response_date`, `is_completed` — mapping table of which conceptual slot each report field touches.
- Flag any merge rule that would **conflict** with flat GED (e.g. flat GED says `ANSWERED` on date X, report memory says `ANSWERED` on date Y).

**Outputs.** `docs/REPORTS_INGESTION_AUDIT.md`

**Acceptance criteria.**
- All 4 consultant ingestors have subsections.
- Override-vs-enrich classification explicit for every rule.
- Mapping table has a row for every flat GED field report memory could touch.

**Dependencies.** Steps 1, 3. Can run in parallel with 4 and 5.

---

### STEP 7 — Flat GED + Report memory composition spec (with field classification)

**Objective.** Decide and document composition rules AND classify each report field by operational impact.

**Inputs.**
- `docs/FLAT_GED_CONTRACT.md` (Step 1)
- `docs/REPORTS_INGESTION_AUDIT.md` (Step 6)
- Parity report (Step 5)
- `docs/BACKEND_SEMANTIC_CONTRACT.md` (Step 3b)

**Work.** Produce `docs/FLAT_GED_REPORT_COMPOSITION.md` with:

1. **Precedence rule.** Propose: flat GED is truth for `is_completed=True` rows; report memory only upgrades flat-GED `PENDING` rows. Document and justify.
2. **Conflict rule.** When flat GED and report memory disagree on a completed row, which wins and why.
3. **New-response rule.** When report memory has an answer for a GED row flat GED classifies as `NOT_CALLED`.
4. **Date reconciliation.** When response dates differ.
5. **Field classification table — mandatory.** One row per report field (from Step 6 mapping table). Columns:
   - `field_name`
   - `class` — one of:
     - `augments_operational_truth` — changes `is_completed`, `response_date`, `status_code`, `is_blocking`, or cycle closure. Affects backlog/late counts.
     - `fills_missing_evidence` — adds a comment, observation, PJ flag, or reference that does not change operational state.
     - `presentation_only` — display-layer enrichment (labels, formatted dates, badges). No impact on computations.
   - `impact_on_fiche` — one line.
   - `impact_on_cue_engine_later` — one line (best-guess placeholder is fine).
6. **10 concrete examples** from the real database exercising each rule. Find (numero, indice) pairs in `output/FLAT_GED.xlsx` + existing report memory.

**Outputs.** `docs/FLAT_GED_REPORT_COMPOSITION.md`

**Acceptance criteria.**
- Every merge case from Step 6 has a rule.
- Every report field has a classification — no "unspecified".
- `augments_operational_truth` fields are explicitly listed (these drive counts).
- 10 real examples listed.
- Eid accepts before Step 8.

**Dependencies.** Steps 5, 6.

---

### STEP 8 — clean_GF reconstruction: logical layer (document-code level)

**Objective.** Rebuild `clean_GF` content from flat GED + report memory. **Content only, no formatting.**

**⚠ Constraint — stated explicitly.** This step reconstructs at **document-code level** — one output row per (numero, indice). Submission instances that flat GED distinguishes (`ACTIVE` / `INACTIVE_DUPLICATE` / `SEPARATE_INSTANCE` / `INCOMPLETE_BUT_TRACKED`) are collapsed to the `ACTIVE` instance only, with non-ACTIVE instances logged separately. This is accepted for this phase. Submission-instance fidelity is a future concern (Chain/Onion, Step 12).

**Inputs.**
- Step 7 composition spec.
- `src/flat_ged/` (frozen).
- `src/effective_responses.py` (reference only).
- `src/workflow_engine.py` (reference).
- `src/writer.py` (existing GF output shape reference).

**Work.**
1. Create `src/clean_gf/reconstruct.py`:
   ```python
   def reconstruct_clean_gf_rows(flat_ged_path: Path, report_memory_db: Path | None) -> tuple[list[dict], list[dict]]:
       """
       Returns (active_rows, collapsed_instances).
       active_rows: one dict per (numero, indice) — the ACTIVE instance only.
       collapsed_instances: rows where non-ACTIVE instances exist, for audit.
       """
   ```
2. Output dicts' keys exactly match content columns of current `GF_V0_CLEAN.xlsx` (no merged cells, no colours, no widths).
3. For each column: flat GED first (per Step 7 precedence), report memory overlay (per Step 7 rules), computed fields delegated to existing helpers in `src/workflow_engine.py` and `src/domain/`. Do NOT reimplement.
4. `collapsed_instances` is populated whenever flat GED's `instance_role` ≠ `ACTIVE` for any row sharing the (numero, indice) key. Schema: `numero, indice, submission_instance_id, instance_role, instance_resolution_reason, why_collapsed`.
5. Add `tests/clean_gf/test_reconstruct_content.py`:
   - Output length equals unique (numero, indice) count where at least one `ACTIVE` instance exists.
   - No row has both `is_completed=True` and null `response_date`.
   - Every row has non-null `LOT`.
   - `collapsed_instances` is non-empty (the real data has duplicates — verify the audit trail works).

**Outputs.**
- `src/clean_gf/reconstruct.py`
- `src/clean_gf/__init__.py`
- `tests/clean_gf/test_reconstruct_content.py`

**Acceptance criteria.**
- Tests pass on real data.
- Completes in < 30s on full database.
- Does NOT write any file (that's Step 9).
- `collapsed_instances` count > 0 (proves submission-instance collapsing is captured, not silently dropped).

**Dependencies.** Step 7.

---

### STEP 9 — clean_GF row-level diff vs current output

**Objective.** Compare Step 8 output against current `GF_V0_CLEAN.xlsx`. Logical-fidelity proof.

**⚠ Scope constraint — stated explicitly.** Diff is indexed by (numero, indice) — same document-code level as Step 8. Submission-instance-level divergences are **not** detected by this diff; they're tracked via `collapsed_instances` from Step 8. This is accepted for this phase.

**Inputs.** Step 8 output, fresh `GF_V0_CLEAN.xlsx` from current engine.

**Work.**
1. Create `scripts/clean_gf_diff.py`:
   - Calls `reconstruct_clean_gf_rows()` → new rows.
   - Opens `GF_V0_CLEAN.xlsx` → old rows.
   - Indexes both by `(numero, indice)`.
   - Logs rows present in one but not the other.
   - For matched rows, compares all content columns.
2. Produces `output/clean_gf_diff.xlsx`:
   - `ONLY_IN_NEW`
   - `ONLY_IN_OLD`
   - `FIELD_DIFFS` (numero, indice, column, old, new, bucket)
   - `COLLAPSED_INSTANCES` (from Step 8's second return)
   - `SUMMARY`
3. Bucket field differences: `IDENTICAL` / `BENIGN` / `KNOWN_ENRICHMENT_GAP` / `OLD_PATH_BUG` / `REAL_DIVERGENCE`. (Same five-bucket scheme as Step 5.)

**Outputs.**
- `scripts/clean_gf_diff.py`
- `output/clean_gf_diff.xlsx`

**Acceptance criteria.**
- Script completes.
- `REAL_DIVERGENCE` = 0, or each divergence documented in `docs/clean_gf_reconstruction_gaps.md`.
- `OLD_PATH_BUG` entries each cite the semantic contract (Step 3b) or flat GED rule that makes new correct.
- `COLLAPSED_INSTANCES` sheet is non-empty — confirms the scope constraint is visible, not hidden.

**Dependencies.** Step 8.

**⚠ GATE 2.** Pass = (`REAL_DIVERGENCE` = 0) AND (all `OLD_PATH_BUG` entries justified). Submission-instance collapse is accepted per the declared scope constraint — it is NOT a divergence.

---

### STEP 9b — Formatting fidelity (DEFERRED PLACEHOLDER)

**Status.** Deferred. Listed here so it's not forgotten.

**Objective (when we pick it up).** Match the visual output of `clean_GF` — merged cells, colours, column widths, row heights, number formats, conditional formatting — against the human-maintained reference.

**Why deferred.** Content correctness (Steps 8, 9) must pass Gate 2 first. Formatting without correct content is wasted work; correct content in ugly formatting is still operationally useful.

**Trigger to activate.** Eid decides after Gate 2 that the dashboard users need the reconstructed GF visually identical to the human version.

**Not scoped here.** Inputs, work, outputs, acceptance to be defined when the step is activated.

---

### STEP 9c — Shared flat-GED query library

**Objective.** Extract the operational definitions used by clean_GF reconstruction into a reusable query layer. Prevents duplicated definitions across clean_GF, UI parity, and the cue engine.

**Why now.** After Step 8, we have working definitions of backlog, late, open, responsibility, etc. — in code. Extracting them into a library is a refactor, not a design exercise. Before Step 10, so the UI source-of-truth map can reference library function names instead of pseudocode.

**Inputs.**
- `src/clean_gf/reconstruct.py` (Step 8)
- `docs/BACKEND_SEMANTIC_CONTRACT.md` (Step 3b)
- `docs/FLAT_GED_REPORT_COMPOSITION.md` (Step 7)

**Work.**
1. Create `src/flat_ged_queries/` package with modules:
   - `loaders.py` — `load_operations(path) -> list[dict]`, `load_raw_flat(path) -> list[dict]`. Single source of the loading logic.
   - `filters.py` — pure predicates over operation rows: `is_open(row)`, `is_late(row, data_date)`, `is_blocking(row)`, `is_moex_step(row)`, `is_consultant_step(row)`, `is_sas_step(row)`, `is_completed(row)`.
   - `aggregates.py` — `backlog_by_consultant(ops, data_date) -> dict[str, int]`, `late_by_consultant(ops, data_date) -> dict[str, int]`, `open_docs_by_lot(ops) -> dict[str, int]`, `cycle_closure_counts(ops) -> dict[str, int]`, etc. One function per UI aggregate.
   - `instance.py` — `active_rows_only(ops) -> list[dict]`, `collapsed_instances(ops) -> list[dict]`. The document-code vs submission-instance boundary.
2. **No new semantics.** Every function in this library must correspond to a behaviour already in Step 8's `reconstruct.py` or to a definition in the semantic contract. Extraction, not invention.
3. **Refactor Step 8 to use the library.** `reconstruct.py` now imports from `src.flat_ged_queries`. The test suite from Step 8 must still pass.
4. Add `tests/flat_ged_queries/` — unit tests per filter and per aggregate. Use fixture rows, not the full GED export.
5. Document the library: `docs/FLAT_GED_QUERIES.md` — one-line description per function, pointer to the semantic contract concept it implements.

**Outputs.**
- `src/flat_ged_queries/` package
- Refactored `src/clean_gf/reconstruct.py`
- `tests/flat_ged_queries/`
- `docs/FLAT_GED_QUERIES.md`

**Acceptance criteria.**
- All Step 8 tests still pass.
- Library has ≥ 8 aggregate functions covering the UI surfaces identified in Step 10 (Step 10 runs in parallel; library adjusts if Step 10 uncovers missing aggregates).
- Every library function references a Step 3b concept in its docstring.
- `reconstruct.py` no longer contains inline filter/aggregate logic — all delegated.

**Dependencies.** Step 8. Can run in parallel with Step 9. Must complete before Step 10's doc is finalised.

---

### STEP 10 — UI source-of-truth map (with granularity classification)

**Objective.** For every number the dashboard displays, identify the flat-GED query that produces it. Each value tagged `document-code level` or `submission-instance level`.

**Inputs.**
- `ui/` and `ui/jansa/` prototype files.
- `src/reporting/` (`aggregator.py`, `consultant_fiche.py`, `contractor_fiche.py`, `data_loader.py`, `ui_adapter.py`, `focus_filter.py`, `focus_ownership.py`).
- `docs/JANSA_PARITY_STEP_*` docs.
- `src/flat_ged_queries/` (Step 9c) — reference library functions by name.

**Work.** Produce `docs/UI_SOURCE_OF_TRUTH_MAP.md` with one entry per UI surface:
- Overview KPIs (total docs, open docs, late docs, on-time rate)
- Consultant list (14 consultants, count columns)
- Consultant fiche — Block 1 monthly, Block 2 combo chart, Block 3 per-lot table
- Drilldowns
- Backlog counts
- Late counts

Per entry:
1. **Query** — by library function name from Step 9c, not inline pseudocode. If the library doesn't have it, the entry triggers a Step 9c extension.
2. **Granularity classification** — one of:
   - `document-code level` — the value is meaningful at (numero, indice). Step 8 reconstruction is sufficient.
   - `submission-instance level` — the value depends on distinguishing `ACTIVE` vs `INACTIVE_DUPLICATE` vs `SEPARATE_INSTANCE`. Currently collapsed; future Chain/Onion may surface.
3. **Date reference** — must be `flat_ged.data_date`, not `datetime.now()`. Explicitly stated per entry.
4. **Report-memory dependency** — flagged Y/N.

**Outputs.** `docs/UI_SOURCE_OF_TRUTH_MAP.md`

**Acceptance criteria.**
- Every KPI, badge, count, chart series in the dashboard has an entry.
- Every entry names a function in `src/flat_ged_queries/`.
- Every entry has a granularity classification.
- No entry references "current date".
- Report-memory dependencies flagged.
- Any missing library function triggers a Step 9c follow-up before Step 11.

**Dependencies.** Steps 8, 9c.

---

### STEP 11 — UI value validation harness

**Objective.** Compute every mapped UI value two ways — via existing dashboard data path, via the query library — and compare.

**Inputs.**
- `docs/UI_SOURCE_OF_TRUTH_MAP.md` (Step 10)
- `src/reporting/aggregator.py`, `src/reporting/ui_adapter.py` (existing data path)
- `src/flat_ged_queries/` (library from Step 9c) ← harness uses this, does NOT reimplement.

**Work.**
1. Create `scripts/ui_parity_harness.py`:
   - For each UI surface in Step 10, computes value using existing `reporting/` functions.
   - Computes same value via `src.flat_ged_queries` functions. **No inline query logic in the harness.** If the harness needs a query not in the library, add it to Step 9c first, then use it here.
   - Logs (surface, value_old, value_new, bucket).
2. Bucket: `IDENTICAL` / `BENIGN_ROUNDING` / `OLD_PATH_BUG` / `REAL_DIVERGENCE`.
3. Produces `output/ui_parity_report.xlsx`.

**Outputs.**
- `scripts/ui_parity_harness.py`
- `output/ui_parity_report.xlsx`

**Acceptance criteria.**
- Every UI surface in Step 10 appears in the report.
- `REAL_DIVERGENCE` = 0, or each documented in `docs/ui_parity_gaps.md`.
- `OLD_PATH_BUG` entries cite semantic contract or library definition.
- Harness contains zero inline filter/aggregate logic — only library calls.

**Dependencies.** Steps 9, 9c, 10.

**⚠ GATE 3.** Pass = (`REAL_DIVERGENCE` = 0) AND (all `OLD_PATH_BUG` entries justified). Last gate before enrichment is allowed.

---

### STEP 12 — Chain + Onion (placeholder)

**Objective.** Implement Chain + Onion methodology on a validated flat-GED foundation.

**Notes for when activated.**
- Prerequisite: Gate 3 passed.
- Prerequisite doc: `docs/CHAIN_ONION_METHODOLOGY.md` (not yet written — a separate planning pass).
- This is where the `submission-instance level` UI values from Step 10 get real semantics, reversing Step 8's collapse.
- Submission-instance fidelity in `clean_GF` likely becomes a Step 12 deliverable.

**Scope deferred.**

---

### STEP 13 — Cue engine (placeholder)

**Objective.** Add cue engine once Chain+Onion is in.

**Scope deferred. Depends on Step 12.**

---

## Part 3 — Execution order

**Strictly sequential backbone:**

```
1 → 2 → 3 → 3b → 4 → 5 (GATE 1) → 7 → 8 → 9 (GATE 2) → 9c → 10 → 11 (GATE 3) → 12 → 13
```

**Parallelisable:**

- **Step 6** (reports audit, read-only) runs in parallel with Steps 4 and 5 after Steps 1–3 are done. Step 7 needs both 5 and 6 done.
- **Step 9c** (query library) runs in parallel with Step 9 — library is extracted from Step 8, diff uses Step 8's `reconstruct.py` output. Both must complete before Step 10 finalises.
- **Step 9b** (formatting) is deferred — no parallelism.

**Critical path:** 1 → 2 → 3 → 3b → 4 → 5 → 7 → 8 → 9 → 9c → 10 → 11 = 12 steps.

Off critical path: 6, 9b, 12, 13.

---

## Part 4 — Validation gates

| Gate | After step | Pass criterion | Bucket rules | If it fails |
|------|-----------|----------------|--------------|-------------|
| **GATE 1** — Read-path parity | Step 5 | `REAL_DIVERGENCE` = 0 AND all `OLD_PATH_BUG` items justified | Old path is not gold standard; `OLD_PATH_BUG` corrections count as passes with documented justification | Debug adapter mismatch first (stage_read_flat). Do not start Step 7. |
| **GATE 2** — Logical GF fidelity | Step 9 | `REAL_DIVERGENCE` = 0 AND all `OLD_PATH_BUG` items justified. Submission-instance collapse per declared scope constraint is NOT a divergence | `COLLAPSED_INSTANCES` sheet is an audit trail, not a failure | Debug `reconstruct.py`; do not start Step 9c or 10. Do NOT change flat builder — frozen. |
| **GATE 3** — UI parity | Step 11 | `REAL_DIVERGENCE` = 0 AND all `OLD_PATH_BUG` items justified | Missing library function → extend Step 9c, do not inline in harness | Debug `reporting/` layer or query library. Do NOT start enrichment until clean. |

**Passing a gate requires one of:**
1. Zero real divergences.
2. Every real divergence has a written explanation, reviewed by Eid, stating either (a) why it's not actually a bug, (b) which future step will fix it, or (c) for `OLD_PATH_BUG` entries, why the new path is correct.

"Looks close enough" is not a pass.

---

## What this plan deliberately avoids

- **Flat builder modifications** — frozen. Step 2 makes this a written rule.
- **Formatting work on clean_GF** — Step 9b placeholder.
- **Chain/Onion logic** anywhere in Steps 1–11.
- **Cue engine** before UI parity.
- **New dashboard features** before old values are verified.
- **Silent cutovers** — flat-GED mode is flag-gated in Step 4.
- **Adapter black-box imitation** — Step 4 requires an explicit mapping table.
- **"Old path is truth" framing** — Step 5 and onwards treat old as transition reference, not gold standard.
- **Duplicated query definitions** — Step 9c forces one library, used by clean_GF, UI parity, and future cue engine.
- **Submission-instance drift** — Step 8 declares the collapse explicitly; `collapsed_instances` audit trail prevents silent loss.
