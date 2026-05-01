# Phase 8 — Count Lineage Fix (RAW GED → FLAT_GED → RunContext → Aggregator → UI → Chain+Onion)

> **STATUS — CLOSED on 2026-04-30. This file is read-only reference material.**
>
> Do NOT continue implementation inside this file. Steps 1, 2, 2.5, 3, 4, 5, 6 shipped and Windows-shell verified end-to-end (57 Phase 8 tests passing). Final audit lines:
> ```
> AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
> UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match
> ```
> Step 7 (Run completion gate) is deferred per the original plan and was never opened.
>
> **Carry-forward items are routed to two new phases:**
> - **Phase 8A** (downstream hardening): D-010 + Step 5 BLOCK-mode flip + Step 6 widened UI coverage.
> - **Phase 8B** (upstream): RAW → FLAT SAS REF reconciliation (D-011) + report integration.
>
> Phase 8A and 8B do NOT yet have plan documents — those are next-session work. Routing assignments live in `context/07_OPEN_ITEMS.md`.
>
> Execution receipts for steps 1–6 are below in §18 through §24. Read them as reference; do not edit them.

This MD is **self-contained**. An agent or engineer assigned only this phase can execute it cold without reading any other file in `docs/implementation/`. Each numbered step below is also self-contained — it states its objective, files to read, files to modify, validation, and risk in isolation.

---

## 1. Objective

Correct the divergence between the values shown in the UI and the values that actually exist in:

```
RAW GED  →  FLAT_GED.xlsx  →  stage_read_flat  →  RunContext / cache  →  aggregator KPIs  →  ui_adapter  →  Chain+Onion
```

Core rule for every step: **every displayed UI value must be traceable to a verified backend artifact, and every mismatch must either be corrected or explicitly explained as a known semantic difference (not a bug).**

Hard constraints (apply to every step):

- App must keep starting and serving.
- No Parquet introduction. No architecture rewrite.
- Do NOT modify `src/flat_ged/*`, `src/workflow_engine.py`, `src/effective_responses.py`, `src/run_memory.py`, `src/report_memory.py`, `src/team_version_builder.py`, `data/*.db`, `runs/*`, `ui/jansa/*`, `ui/jansa-connected.html`.
- No pipeline rerun in Cowork unless explicitly authorized. Audit must work against the existing `runs/run_0000/` artifact.
- No business logic moved into JSX. Backend stays source of truth.

---

## 2. Risk Summary

| Phase | Risk | Why |
|-------|------|-----|
| 1. Audit harness | Low | Pure read script, writes only to `output/debug/`. |
| 2. Count terminology | Low | Names exposed inside the audit; no aggregator/UI changes yet. |
| 3. Visa global source fix | **Medium** | Touches `data_loader.RunContext` shape and 4–5 call sites in `aggregator.py`. |
| 4. Cache audit fields | Low | Extra keys in `FLAT_GED_cache_meta.json`. Reader is tolerant of extra keys. |
| 5. Chain+Onion source alignment | Medium (WARN) → Medium-High (BLOCK) | Adds a check before Chain+Onion run. WARN-only first; BLOCK only after confidence. |
| 6. UI payload verification | Low (audit only) → Medium (if `ui_adapter.py` is patched) | Aggregator stays source of truth. |
| 7. Run completion gate | Deferred — do not implement during this phase. | Avoids changing `stage_finalize_run.py` until audit history is stable. |

Phase 1, 2, 4 are LOW risk. Phase 3 is MEDIUM and requires written approval before any code change. Phase 5 (BLOCK mode) and Phase 6 (modify-mode) require explicit re-approval. Phase 7 is out of scope here.

---

## 3. Standard Rules (embedded — do not skip)

### Tooling
Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) for inspecting Windows-mounted source files. The Linux mount caches stale views. Bash IS fine for executing scripts (`python scripts/audit_counts_lineage.py`, `python -m py_compile …`). See `context/11_TOOLING_HAZARDS.md`.

### Priorities
1. App must always run.
2. Investigation-and-documentation first. Phase 1 ships an audit harness BEFORE any production code is changed.
3. No silent renames. No silent contract changes. No row drops.
4. Every patch in Phase 3+ is the smallest patch that makes the audit pass.
5. If the audit shows a divergence is **expected** (semantic, not a bug), record it in the contract — do NOT patch code to "fix" it.

### Forbidden moves during this phase
- Do NOT introduce a new cache format. The existing pickle cache stays.
- Do NOT rewrite `data_loader.py`, `aggregator.py`, or `ui_adapter.py` for style.
- Do NOT add Parquet, DuckDB, polars, or any new storage layer.
- Do NOT touch `src/flat_ged/*`, `src/workflow_engine.py`, `src/effective_responses.py`.
- Do NOT change column names in `FLAT_GED.xlsx`, `cache_meta.json`, or any pipeline artifact.
- Do NOT delete `output/intermediate/FLAT_GED_cache_*` files manually as part of the patch.

---

## 4. Pipeline Layers To Audit (numbered for reference)

```
L0_RAW_GED               input/*.xlsx (raw GED export, the ground truth)
L1_FLAT_GED_XLSX         output/intermediate/FLAT_GED.xlsx (debugging artifact)
L2_STAGE_READ_FLAT       src/pipeline/stages/stage_read_flat.py output (docs_df, responses_df, flat_doc_meta)
L3_RUNCONTEXT_CACHE      output/intermediate/FLAT_GED_cache_docs.pkl + cache_resp.pkl + cache_meta.json
L4_AGGREGATOR            src/reporting/aggregator.py KPIs / time series / consultant + contractor summaries
L5_UI_ADAPTER            src/reporting/ui_adapter.py overview + drilldown payloads
L6_CHAIN_ONION           src/chain_onion/* outputs (read FLAT_GED.xlsx directly today)
```

Required count categories the audit MUST emit per layer (when meaningful):

```
submission_instance_count          # raw workflow rows (one per submission instance)
active_version_count               # active (numero, indice) pairs in OPEN_DOC / GED_OPERATIONS
family_count                       # unique numero
numero_indice_count                # unique (numero, indice) pairs
workflow_step_count                # rows in GED_RAW_FLAT-equivalent (every approver row)
response_row_count                 # responses_df rows after normalize
sas_row_count                      # rows where approver_raw == "0-SAS"
consultant_row_count               # CONSULTANT sheet rows
moex_row_count                     # MOEX sheet rows
open_doc_row_count                 # OPEN_DOC sheet rows
status_VSO / VAO / REF / HM / FAV / SUS / DEF / pending / empty
open_count
closed_count
focus_eligible_count
live_operational_count
legacy_backlog_count
```

Expected baseline from the uploaded files (use as ground-truth assertions in the harness):

```
RAW GED:
  raw_submission_rows         = 6155
  raw_unique_numero           = 2819
  raw_unique_numero_indice    = 4848

FLAT_GED.xlsx:
  GED_RAW_FLAT rows           = 27261
  GED_OPERATIONS rows         = 32099
  OPEN_DOC                    = 4848
  SAS                         = 4848
  CONSULTANT                  = 18911
  MOEX                        = 3492

stage_read_flat expected:
  SAS pre-2026 filter excludes  14 document versions
  expected docs_df rows       = 4834   (= 4848 − 14)
```

---

## 5. Phase 1 — Build the Count Lineage Audit FIRST (LOW risk)

### 5.1 Why this comes first
We do not yet know which layer first diverges. Patching `aggregator.py` blind is forbidden. The harness is the diagnostic. Once the harness reports the first divergence layer, every later phase has a clear, verifiable target.

### 5.2 Files

```
READ:
  src/reporting/data_loader.py
  src/reporting/aggregator.py
  src/reporting/ui_adapter.py
  src/pipeline/stages/stage_read_flat.py
  src/chain_onion/source_loader.py
  output/intermediate/FLAT_GED.xlsx
  output/intermediate/FLAT_GED_cache_meta.json
  input/*.xlsx                     # raw GED export(s)

CREATE:
  scripts/audit_counts_lineage.py
  output/debug/counts_lineage_audit.xlsx
  output/debug/counts_lineage_audit.json
  context/11_COUNT_LINEAGE_CONTRACT.md   # optional but recommended

DO NOT TOUCH:
  src/flat_ged/*
  src/workflow_engine.py
  src/effective_responses.py
  src/run_memory.py
  src/report_memory.py
  src/team_version_builder.py
  data/*.db
  runs/*
  ui/jansa/*
  ui/jansa-connected.html
```

### 5.3 What `scripts/audit_counts_lineage.py` must do

1. Locate the raw GED file in `input/` (newest matching the GED naming convention).
2. Load `output/intermediate/FLAT_GED.xlsx` (read every relevant sheet: `GED_RAW_FLAT`, `GED_OPERATIONS`, `OPEN_DOC`, `SAS`, `CONSULTANT`, `MOEX`).
3. Call `data_loader.load_run_context(run_number=0)` (this exercises the cache + stage_read_flat path that the live app uses; do not re-implement it).
4. From the resulting `RunContext`, compute every count in section 4 from `ctx.docs_df`, `ctx.responses_df`, `ctx.workflow_engine.responses_df`, and `ctx.workflow_engine._lookup`.
5. Run `aggregator.compute_project_kpis(ctx)` and extract every count it exposes.
6. Run `ui_adapter.adapt_overview(ctx, …)` (or its equivalent entry function — verify the actual function name in `ui_adapter.py`) and extract every count it ships to the UI.
7. Read `src/chain_onion/source_loader.py` outputs (or directly load whatever artifacts Chain+Onion produces in `output/chain_onion/`) and extract its counts.
8. Compare ALL of the above into a single wide table where each row is a count category and each column is a layer (L0…L6). Record `value`, `delta_vs_prev_layer`, `is_difference_expected`, `explanation`, `source_file`, `source_sheet`, `source_column`.
9. Compute `first_divergence_layer` per category — the leftmost layer whose value disagrees with L0 *and* is not flagged `is_difference_expected=True`.
10. Write the wide table to `output/debug/counts_lineage_audit.xlsx` (one sheet `lineage`, one sheet `expected_baselines`, one sheet `divergences_unexpected`).
11. Write the same data to `output/debug/counts_lineage_audit.json` with shape:

    ```json
    {
      "generated_at": "<iso>",
      "run_number": 0,
      "flat_ged_sha256": "<sha>",
      "flat_ged_mtime": "<iso>",
      "expected_baselines": { ... },
      "categories": [
        {
          "name": "active_version_count",
          "values": { "L0_RAW_GED": 4848, "L1_FLAT_GED_XLSX": 4848, "L2_STAGE_READ_FLAT": 4834, ... },
          "first_divergence_layer": "L2_STAGE_READ_FLAT",
          "is_difference_expected": true,
          "explanation": "SAS pre-2026 filter excludes 14 versions",
          "source": { "file": "src/pipeline/stages/stage_read_flat.py", "function": "<name>" }
        },
        ...
      ],
      "summary": { "PASS": <n>, "WARN": <n>, "FAIL": <n> }
    }
    ```

12. Print a one-line summary to stdout: `AUDIT: PASS=<n> WARN=<n> FAIL=<n>; first_unexpected_divergence=<category>@<layer>`.

### 5.4 Built-in expected-divergence rules (encode these in the script as data, not as silent ifs)

```
- L0 raw_submission_rows (6155)            → vs L1 GED_RAW_FLAT (27261)
    DIFFERENT CONCEPTS, expected.   Explanation: GED_RAW_FLAT is one-row-per-(doc, approver, step), not one-per-submission.

- L0 raw_unique_numero_indice (4848)       → vs L1 OPEN_DOC (4848)
    EQUAL,  expected.

- L1 OPEN_DOC (4848)                       → vs L2 docs_df (4834)
    DIFFERENT, expected.    Explanation: SAS pre-2026 filter excludes 14 document versions.

- L0 raw_unique_numero (2819)              → vs L2 family_count
    EQUAL or close (modulo SAS-only filtered families), expected.

- ANY divergence between L4 aggregator and L5 ui_adapter for the SAME count category
    is UNEXPECTED — either the adapter renames the field (fix adapter) or the aggregator
    is being recomputed in JSX (forbidden).
```

### 5.5 Validation

```
python -m py_compile scripts/audit_counts_lineage.py
python scripts/audit_counts_lineage.py
# Inspect: output/debug/counts_lineage_audit.xlsx + .json
# Confirm: harness runs end-to-end without modifying any pipeline output.
```

### 5.6 Risk: **Low**. No production code is changed. The script writes only to `output/debug/`.

---

## 6. Phase 2 — Fix Count Terminology in the Audit (LOW risk)

### 6.1 Why
Saying "total docs" hides the difference between four legitimate, *different* numbers (6155 / 4848 / 4834 / 2819). All four are correct in their own layer; the bug is calling them by the same name.

### 6.2 Required count semantics (introduce inside the audit harness only — do NOT rename anything in `aggregator.py` or `ui_adapter.py` yet)

```
submission_instance_count       = L0 raw GED submitted workflow rows
                                  (one row per submission instance; what the operator counts when they say "submissions").

active_version_count            = L1 OPEN_DOC / GED_OPERATIONS active (numero, indice) pairs.

family_count                    = unique numero  (one per document family, regardless of indice).

effective_pipeline_doc_count    = L2 docs_df rows after stage_read_flat filters
                                  (currently OPEN_DOC minus SAS pre-2026 = 4834).

ui_display_doc_count            = whatever number the UI card actually shows
                                  (must equal effective_pipeline_doc_count unless an explicit, recorded
                                   adapter-level scope filter is applied).
```

### 6.3 Output requirement
The audit's `expected_baselines` block names every number using these five terms — no "total_docs". Every later phase (3, 5, 6) uses the same vocabulary.

### 6.4 Files

```
MODIFY:  none in production source.   The vocabulary is enforced inside scripts/audit_counts_lineage.py
         and (optionally) recorded in context/11_COUNT_LINEAGE_CONTRACT.md.

DO NOT TOUCH: src/reporting/aggregator.py, src/reporting/ui_adapter.py.
              Renaming aggregator/UI fields prematurely would silently break the JSX. Defer renames
              until after Phases 3, 5, 6 prove the numbers are right under the current names.
```

### 6.5 Validation
The audit's JSON output uses the five canonical names. No production behavior changes.

### 6.6 Risk: **Low**.

---

## 7. Phase 3 — Fix `visa_global` Source Mismatch (MEDIUM risk — STOP for approval)

### 7.1 The contradiction
- `stage_read_flat` (L2) populates `flat_doc_meta` with the **authoritative** `visa_global` for every doc — this is the contract documented in `docs/FLAT_GED_CONTRACT.md`.
- `_load_from_flat_artifacts` (`src/reporting/data_loader.py:407`) loads `flat_doc_meta` from the cache (or recomputes it via `stage_read_flat`) — but **never attaches it to `RunContext`**.
- `aggregator.py` therefore falls back to `WorkflowEngine.compute_visa_global_with_date(doc_id)` at every site that needs `visa_global`.
- These two paths can disagree when the workflow recomputation diverges from the stage_read_flat decision (the SAS filter, in particular, is applied in stage_read_flat but not in `WorkflowEngine`).

### 7.2 Inspection performed during planning
Confirmed `compute_visa_global_with_date` is called at **5 sites** in `src/reporting/aggregator.py` (not 4 as the brief listed). Each site sits inside a different aggregator function:

| Line | Function |
|------|----------|
| 84   | `compute_project_kpis` |
| 189  | `compute_monthly_timeseries` |
| 237  | `compute_weekly_timeseries` |
| 343  | `compute_consultant_summary`  ← not in original brief — DECISION REQUIRED |
| 461  | `compute_contractor_summary` |

> **DECISION POINT (must be answered before coding):** the brief lists 4 functions to patch but `compute_consultant_summary` (line 343) also calls `compute_visa_global_with_date` directly. Two consistent options exist:
>
> - **(A)** Patch all 5 sites uniformly with `resolve_visa_global(ctx, doc_id)`. *Recommended* because consistency is the whole point of the fix; leaving one site on the old fallback re-creates the bug we are trying to remove.
> - **(B)** Patch only the 4 sites in the brief and leave `compute_consultant_summary` untouched. Acceptable only if there is a deliberate reason consultant numbers should keep using the WorkflowEngine recomputation.
>
> Do not silently choose. Confirm with the project owner before editing.

### 7.3 Patch — minimal

#### 7.3.1 Add a field to `RunContext`
File: `src/reporting/data_loader.py` (around line 35-58, inside the existing `@dataclass class RunContext:` block):

```python
flat_ged_doc_meta: dict = field(default_factory=dict)   # {doc_id: {"visa_global": ..., "visa_global_date": ...}}
```

#### 7.3.2 Pass the meta into `RunContext` at construction
In `_load_from_flat_artifacts` (`src/reporting/data_loader.py:407`), the existing code already holds a local variable `flat_doc_meta` populated from the cache or from `stage_read_flat`. Add it to the `RunContext(...)` constructor call:

```python
RunContext(
    ...,
    flat_ged_doc_meta=flat_doc_meta or {},
)
```

(The exact line depends on where the constructor is invoked — search for `return RunContext(` inside `_load_from_flat_artifacts`. There is exactly one such site there. Do **not** modify the legacy fallback constructor in the same file unless the audit says it also needs the field.)

#### 7.3.3 Add ONE helper to `aggregator.py`
File: `src/reporting/aggregator.py` (top of the file, after the existing imports / `_safe_str`):

```python
def resolve_visa_global(ctx, doc_id):
    """Prefer flat_ged_doc_meta (authoritative per FLAT_GED_CONTRACT);
    fall back to WorkflowEngine recomputation if missing."""
    meta = getattr(ctx, "flat_ged_doc_meta", {}) or {}
    if doc_id in meta:
        visa = meta[doc_id].get("visa_global")
        vdate = meta[doc_id].get("visa_global_date")
        if visa:
            return visa, vdate
    return ctx.workflow_engine.compute_visa_global_with_date(doc_id)
```

#### 7.3.4 Replace direct calls
At each of the 5 (or 4 — see decision in 7.2) sites in `aggregator.py`, replace:

```python
visa, vdate = we.compute_visa_global_with_date(did)
```

with:

```python
visa, vdate = resolve_visa_global(ctx, did)
```

### 7.4 Files

```
MODIFY:
  src/reporting/data_loader.py     # one new field on RunContext + one constructor argument
  src/reporting/aggregator.py      # one helper + 4 or 5 replaced call sites

DO NOT TOUCH:
  src/workflow_engine.py
  src/flat_ged/*
  src/effective_responses.py
  src/reporting/ui_adapter.py
```

### 7.5 Validation

```
python -m py_compile src/reporting/data_loader.py src/reporting/aggregator.py
python -m py_compile app.py
python scripts/audit_counts_lineage.py    # rerun the audit
```

After the patch, the audit must show:

- `status_VSO / VAO / REF / HM / FAV / SUS / DEF` counts at L4 (aggregator) match the same counts at L2 (stage_read_flat / flat_doc_meta).
- No new divergence appears between L4 and L5.
- App startup unchanged. UI loads. (Smoke test: `python app.py`, hit one consultant fiche, hit Overview.)

### 7.6 Rollback
Revert the two files. Cache is unaffected (the new RunContext field is additive; the cache still stores `flat_doc_meta` exactly as today).

### 7.7 Risk: **Medium**. STOP and wait for approval before editing.

---

## 8. Phase 4 — Make the Existing Cache Auditable (LOW risk)

### 8.1 Why
The pickle cache is the current source of truth for `docs_df`, `responses_df`, and `flat_doc_meta` at runtime. If the cache silently drifts from `FLAT_GED.xlsx`, every later layer is wrong. Today we cannot prove the cache matches the xlsx without rebuilding.

### 8.2 Patch — minimal

In `src/reporting/data_loader.py`, inside `_save_flat_normalized_cache` (around line 117), extend the `cache_meta.json` payload from:

```python
{
    "cache_schema_version": CACHE_SCHEMA_VERSION,
    "approver_names": approver_names,
    "flat_doc_meta": flat_doc_meta,
}
```

to:

```python
{
    "cache_schema_version": CACHE_SCHEMA_VERSION,
    "approver_names": approver_names,
    "flat_doc_meta": flat_doc_meta,
    # ── audit fields (Phase 4) ──
    "source_flat_ged_sha256": _sha256(flat_ged_path),
    "source_flat_ged_mtime":  Path(flat_ged_path).stat().st_mtime,
    "docs_df_rows":           int(len(docs_df)),
    "responses_df_rows":      int(len(responses_df)),
    "active_version_count":   int(docs_df["doc_id"].nunique()) if "doc_id" in docs_df.columns else None,
    "family_count":           int(docs_df["numero"].nunique()) if "numero" in docs_df.columns else None,
    "status_counts":          (responses_df["status_clean"].value_counts().to_dict()
                               if "status_clean" in responses_df.columns else {}),
    "generated_at":           datetime.utcnow().isoformat() + "Z",
}
```

(Verify the actual column names by reading 10 rows of `docs_df` / `responses_df` in the audit harness first. The above are the names used elsewhere in `data_loader.py`.)

`_load_flat_normalized_cache` already tolerates extra keys (it only reads `cache_schema_version`, `approver_names`, `flat_doc_meta`) — no read-side change required.

### 8.3 Bump `CACHE_SCHEMA_VERSION` from `"v1"` to `"v2"` in the same file.
Existing cache freshness logic will reject the old `v1` cache on next run and rebuild — that is the point. The rebuild is the same 30s xlsx parse the loader already handles.

### 8.4 Files

```
MODIFY:
  src/reporting/data_loader.py    # extend cache_meta payload + bump CACHE_SCHEMA_VERSION

DO NOT TOUCH:
  cache reader logic — it tolerates extra keys.
  every other file.
```

### 8.5 Validation

```
python -m py_compile src/reporting/data_loader.py
# Force a cache rebuild by triggering load_run_context; cheapest way:
python -c "from src.reporting.data_loader import load_run_context; ctx = load_run_context(0)"
# Inspect: output/intermediate/FLAT_GED_cache_meta.json — confirm new keys present.
python scripts/audit_counts_lineage.py
# The audit can now assert cache_meta["docs_df_rows"] == ctx.docs_df.shape[0].
```

### 8.6 Risk: **Low**. Reader is tolerant; one-time cache rebuild on first run.

---

## 9. Phase 5 — Align Chain+Onion Source With Latest Registered FLAT_GED (Medium / WARN-only first)

### 9.1 The drift risk
- The UI reads the latest registered `FLAT_GED` artifact through `run_memory.db`.
- `run_chain_onion.py` and `src/chain_onion/source_loader.py` read `output/intermediate/FLAT_GED.xlsx` directly.
- After a partial pipeline run, these two paths can disagree.

### 9.2 Patch — WARN mode (this phase)

In `src/chain_onion/source_loader.py` (the function that resolves the FLAT_GED path), before opening the xlsx:

1. Resolve the **latest registered FLAT_GED artifact path** via the same `_get_artifact_path(db_path, run_number, "FLAT_GED")` helper that `data_loader.py` uses (or call into a small shared utility — do not duplicate the SQL).
2. Compare against the path Chain+Onion is about to read.

```
- If paths are byte-identical:                        OK.
- If paths differ but sha256 of contents matches:     WARN (log + audit) but proceed.
- If paths differ AND sha256 differs:                 WARN (log + audit) but proceed in this phase.
- If paths are identical but mtime differs:           WARN only (mtime is advisory).
```

Log line format (so the audit can pick it up):

```
[CHAIN_ONION_SOURCE_CHECK] result=<OK|WARN_PATH|WARN_SHA|WARN_MTIME> registered=<path> using=<path> sha_match=<true|false>
```

Emit the same record to `output/debug/chain_onion_source_check.json` so `scripts/audit_counts_lineage.py` Phase 1 can include it in `L6_CHAIN_ONION` row.

### 9.3 BLOCK mode is out of scope for this phase
Add a TODO comment next to the WARN handler. Do not flip to BLOCK until at least one full pipeline cycle confirms no false positives.

### 9.4 Files

```
READ:
  run_chain_onion.py
  src/chain_onion/source_loader.py
  src/reporting/data_loader.py    # for the artifact-path helper

MODIFY:
  src/chain_onion/source_loader.py    # add source-alignment check (WARN only)
  run_chain_onion.py                  # only if the check belongs here (verify by reading both files first)

DO NOT TOUCH:
  any business logic in chain_builder, chain_classifier, chain_metrics, onion_engine, onion_scoring, narrative_engine.
  data/*.db, runs/*.
```

### 9.5 Validation

```
python -m py_compile src/chain_onion/source_loader.py run_chain_onion.py
python run_chain_onion.py
# Confirm: log line printed; output/debug/chain_onion_source_check.json present.
python scripts/audit_counts_lineage.py
# L6_CHAIN_ONION row includes source_check_status.
```

### 9.6 Rollback
Revert the two files. Chain+Onion behavior unchanged.

### 9.7 Risk: **Medium** (WARN-only). Becomes Medium-High when later flipped to BLOCK — that is a separate, re-approved change.

---

## 10. Phase 6 — UI Payload Verification (Low for audit; Medium if `ui_adapter.py` is patched)

### 10.1 Goal
Prove that `ui_adapter.adapt_overview(...)` (and the consultant / contractor list adapters) ship the same numbers `aggregator.compute_project_kpis(...)` computes. Where they don't, decide whether the bug is in the adapter (rename / reshape) or in the aggregator (source-logic divergence). In either case the fix lives in the named file — never in JSX.

### 10.2 Audit additions (no production change)

Extend `scripts/audit_counts_lineage.py` (already created in Phase 1) with a verification block:

```
For run 0:
  k = aggregator.compute_project_kpis(ctx)
  o = ui_adapter.adapt_overview(ctx, focus_result, …)   # use the actual function the app endpoint calls

  Assert:
    k.total_docs_current                    == o["OVERVIEW"]["total_docs"]
    k.by_visa_global["VSO"]                 == o["OVERVIEW"]["visa_flow"]["VSO"]
    k.by_visa_global["VAO"]                 == o["OVERVIEW"]["visa_flow"]["VAO"]
    k.by_visa_global["REF"]                 == o["OVERVIEW"]["visa_flow"]["REF"]
    k.by_visa_global["HM"]                  == o["OVERVIEW"]["visa_flow"]["HM"]
    k.by_visa_global["Open"]                == o["OVERVIEW"]["visa_flow"]["Open"]
    k.focus.*                               == o["OVERVIEW"]["focus"].*
    k.consultants[name]                     == o["CONSULTANTS"][name]      # field-by-field
    k.contractors[name]                     == o["CONTRACTORS_LIST"][name] # field-by-field
```

(Verify the actual key names by reading `ui_adapter.py` and the JSX consumer. Adapt the assertions to the real names — do not invent.)

Each failed assertion becomes a row in `output/debug/counts_lineage_audit.xlsx` sheet `ui_payload_mismatches` with columns: `category`, `aggregator_value`, `ui_adapter_value`, `likely_cause` (`naming_only` | `source_logic` | `unknown`).

### 10.3 If a real mismatch is found

- **Naming / reshaping mismatch** (same number, different key name) → fix `src/reporting/ui_adapter.py`. One-line rename. Audit must pass after.
- **Source-logic mismatch** (different number) → fix is upstream in `aggregator.py` (likely Phase 3 still unresolved). Do NOT patch the adapter.
- **JSX-side computation** (UI computing the metric from raw rows) → forbidden; remove the JSX computation, expose the metric in `ui_adapter.py`. Coordinate with project owner because this touches `ui/jansa/*` which is on the DO-NOT-TOUCH list — re-approval required.

### 10.4 Files

```
MODIFY (audit only — Low risk):
  scripts/audit_counts_lineage.py

MODIFY (only if naming-only fix is needed — Medium risk):
  src/reporting/ui_adapter.py

DO NOT TOUCH:
  ui/jansa/*, ui/jansa-connected.html (re-approval required if JSX computation is found).
```

### 10.5 Validation

```
python -m py_compile src/reporting/ui_adapter.py
python -m py_compile app.py
python scripts/audit_counts_lineage.py
# Confirm: ui_payload_mismatches sheet is empty OR every row has a recorded resolution.
# Smoke: launch app, open Overview, confirm tile values match the audit.
```

### 10.6 Risk: **Low** (audit-only). **Medium** if `ui_adapter.py` is patched.

---

## 11. Phase 7 — Run Completion Gate (DEFERRED — do not implement here)

### 11.1 Why deferred
Wiring the audit into `stage_finalize_run.py` changes pipeline completion semantics. That is a HIGH-risk change and must wait until:
- The audit harness has run cleanly across at least one full pipeline cycle.
- The `expected_baselines` block is stable.
- The Chain+Onion alignment check has produced a WARN-free run.

### 11.2 Future shape (informational, do NOT code now)
- v1: pipeline completes; audit is run *manually*; PASS / WARN / FAIL is recorded but does not affect run state.
- v2: pipeline completes; audit runs *automatically*; PASS / WARN keeps the run current; FAIL surfaces a banner in UI.
- v3: FAIL also prevents the run from being marked current.

### 11.3 Files

```
DO NOT TOUCH (this phase):
  src/pipeline/stages/stage_finalize_run.py
  any pipeline orchestration code.
```

### 11.4 Risk for this phase: **N/A — not implemented now.**

---

## 12. Files To Create (full list)

```
scripts/audit_counts_lineage.py
output/debug/counts_lineage_audit.xlsx     # written by the script
output/debug/counts_lineage_audit.json     # written by the script
output/debug/chain_onion_source_check.json # written by Phase 5 check
context/11_COUNT_LINEAGE_CONTRACT.md       # optional — semantic vocabulary record
```

## 13. Files To Modify (full list, ordered by phase)

```
Phase 3 (after approval):
  src/reporting/data_loader.py     # add flat_ged_doc_meta field on RunContext + pass at construction
  src/reporting/aggregator.py      # add resolve_visa_global helper + replace direct calls

Phase 4:
  src/reporting/data_loader.py     # extend cache_meta payload + bump CACHE_SCHEMA_VERSION

Phase 5:
  src/chain_onion/source_loader.py # add source-alignment check (WARN only)
  run_chain_onion.py               # if the check belongs here — verify first

Phase 6 (audit):
  scripts/audit_counts_lineage.py  # add UI payload comparison block

Phase 6 (only if naming-only fix is needed, separate approval):
  src/reporting/ui_adapter.py
```

## 14. Files NEVER To Touch In This Phase

```
src/flat_ged/*
src/workflow_engine.py
src/effective_responses.py
src/report_memory.py
src/run_memory.py
src/team_version_builder.py
data/*.db
runs/*
ui/jansa/*
ui/jansa-connected.html
src/pipeline/stages/stage_finalize_run.py    # Phase 7 is deferred
```

---

## 15. Combined Validation Commands

Each step is independently validatable. Listed in execution order.

```
# Phase 1 (audit harness)
python -m py_compile scripts/audit_counts_lineage.py
python scripts/audit_counts_lineage.py

# Phase 3 (visa global fix — only after approval)
python -m py_compile src/reporting/data_loader.py src/reporting/aggregator.py
python -m py_compile app.py
python scripts/audit_counts_lineage.py

# Phase 4 (cache audit fields)
python -m py_compile src/reporting/data_loader.py
python -c "from src.reporting.data_loader import load_run_context; load_run_context(0)"
python scripts/audit_counts_lineage.py

# Phase 5 (chain+onion source check, WARN-only)
python -m py_compile src/chain_onion/source_loader.py run_chain_onion.py
python run_chain_onion.py
python scripts/audit_counts_lineage.py

# Phase 6 (ui payload verification, audit only)
python scripts/audit_counts_lineage.py

# Phase 6 (only if ui_adapter.py is patched)
python -m py_compile src/reporting/ui_adapter.py
python -m py_compile app.py
python scripts/audit_counts_lineage.py

# Final smoke (mandatory after Phase 3, 4, 5, or 6 patch)
python app.py
# Open Overview, open one consultant fiche, open one contractor fiche.
# Confirm no startup error, no blank panels.
```

---

## 16. Final Cowork Prompt (for handing this phase to a fresh agent)

```
Objective:
  Fix RAW GED → FLAT_GED.xlsx → RunContext → Aggregator → UI count divergence with minimal
  disruption. Do not introduce Parquet. Do not rewrite architecture. Do not touch
  src/flat_ged/*. Do not touch data/*.db or runs/*. Do not rewrite UI. Do not move business
  logic into JSX.

Known baseline from uploaded files:
  RAW GED:
    raw_submission_rows         = 6155
    raw_unique_numero           = 2819
    raw_unique_numero_indice    = 4848
  FLAT_GED.xlsx:
    GED_RAW_FLAT rows           = 27261
    GED_OPERATIONS rows         = 32099
    OPEN_DOC                    = 4848
    SAS                         = 4848
    CONSULTANT                  = 18911
    MOEX                        = 3492
  stage_read_flat expected:
    SAS pre-2026 filter excludes 14 document versions
    expected docs_df rows       = 4834

Tasks:
  1. Create scripts/audit_counts_lineage.py.
  2. Output:
       output/debug/counts_lineage_audit.xlsx
       output/debug/counts_lineage_audit.json
  3. Compare: RAW GED, FLAT_GED.xlsx, stage_read_flat output, RunContext/cache,
     aggregator KPIs, ui_adapter overview payload, Chain+Onion outputs.
  4. Separate count semantics:
       submission_instance_count
       active_version_count
       family_count
       effective_pipeline_doc_count
       ui_display_doc_count
  5. Identify first divergence layer.
  6. Fix visa_global mismatch minimally:
       - Add flat_ged_doc_meta to RunContext.
       - Add resolve_visa_global(ctx, doc_id).
       - Replace direct WorkflowEngine.compute_visa_global_with_date calls in aggregator.py.
       - DECISION REQUIRED: 4 sites (brief) vs 5 sites (actual). Confirm with project owner.
  7. Make existing pickle cache auditable by extending cache_meta.json. Bump CACHE_SCHEMA_VERSION.
  8. Verify Chain+Onion source alignment with latest registered FLAT_GED (WARN only first).

Validation:
  python -m py_compile scripts/audit_counts_lineage.py
  python -m py_compile src/reporting/data_loader.py src/reporting/aggregator.py
  python scripts/audit_counts_lineage.py
  python app.py    # smoke

Return:
  1. Files modified
  2. Exact audit summary
  3. First divergence layer
  4. Before/after visa counts
  5. Whether UI now matches aggregator
  6. Whether Chain+Onion source matches latest registered FLAT_GED
```

---

## 17. Open Questions (to resolve before Phase 3 starts)

1. **5th call site decision (Phase 3, §7.2):** patch `compute_consultant_summary` or leave it? Recommended: patch.
2. **`ui_adapter.adapt_overview` real name:** confirmed it exists; verify the exact entry function name and signature in `src/reporting/ui_adapter.py` before writing the Phase 6 assertions.
3. **Run number assumption:** harness uses `run_number=0` by default. Confirm this is the only run that needs auditing today, or extend the harness to accept `--run` and iterate.
4. **`output/chain_onion/` artifact names:** the harness will need to read whatever Chain+Onion writes. Verify file names by reading `src/chain_onion/exporter.py` once before finalizing the Phase 1 script.
5. **Cache rebuild timing (Phase 4):** bumping `CACHE_SCHEMA_VERSION` forces a 30s rebuild on the next `load_run_context`. Confirm this is acceptable in dev; if production startup time is sensitive, schedule the bump alongside a planned restart.

---

## 18. Phase 1 Execution Report (2026-04-30)

### 18.1 Files Created

| File | Lines | Role |
|---|---|---|
| `scripts/audit_counts_lineage.py` | 1152 | Phase 1 audit harness |
| `tests/test_audit_counts_lineage.py` | ~200 | Companion tests (13 tests) |
| `output/debug/counts_lineage_audit.xlsx` | — | Lineage matrix (3 sheets) |
| `output/debug/counts_lineage_audit.json` | — | Machine-readable audit output |

No production source files were modified.

### 18.2 Validation Results

```
py_compile scripts/audit_counts_lineage.py   → OK (no syntax errors)
py_compile tests/test_audit_counts_lineage.py → OK (no syntax errors)
pytest tests/test_audit_counts_lineage.py -v  → 13 passed in 0.59s
python scripts/audit_counts_lineage.py        → outputs below
```

### 18.3 Audit One-Line Summary

```
AUDIT: PASS=15 WARN=0 FAIL=3; first_unexpected_divergence=workflow_step_count@L2_STAGE_READ_FLAT
```

### 18.4 First Unexpected Divergence

**`workflow_step_count` @ L2_STAGE_READ_FLAT**

| Layer | Value |
|---|---|
| L1_FLAT_GED_XLSX | 27261 (GED_RAW_FLAT rows) |
| L2_STAGE_READ_FLAT | 27237 (responses_df rows after SAS filter) |
| L3_RUNCONTEXT_CACHE | 27237 (same) |

Delta: −24 rows. The SAS pre-2026 filter in `stage_read_flat._apply_sas_filter_flat()` removes 14 (numero, indice) pairs. Each filtered document carries multiple step rows in GED_RAW_FLAT (OPEN_DOC + SAS + CONSULTANT + MOEX), so the total drop is 24 rows — more than the 14 OPEN_DOC rows tracked by the existing `open_doc_vs_docs_df_sas_filter` rule. The rule covers `active_version_count`, `numero_indice_count`, `open_doc_row_count` but not `workflow_step_count`. This is a **gap in `EXPECTED_DIVERGENCES`, not a production bug**. The underlying filter behaviour is correct.

The second category FAIL is **`sas_row_count` @ L2_STAGE_READ_FLAT** (L1=4848 → L2=4834), also caused by the same 14-doc SAS filter reducing SAS step rows, not covered by the existing rule.

The baseline FAIL is **`raw_submission_rows`**: expected 6155, observed 6901 (+746). The GED export has grown since the baseline was recorded. All other 9 baselines pass exactly.

### 18.5 All Layer Values (actual)

```
active_version_count  L0=4848  L1=4848  L2=4834  L3=4834  L4=4834  L5=4834  L6=4848
family_count          L0=2819  L1=2819  L2=2819  L3=2819             (L6=2819)
open_count                              L2=3723  L3=3723  L4=3723  L5=3723
status_VSO                              L2=40    L3=40    L4=40    L5=40
status_VAO                              L2=627   L3=627   L4=627   L5=627
status_REF                              L2=320   L3=320   L4=320   (L5=None, combined)
status_SAS_REF                          L2=0     L3=0     L4=0
status_HM                               L2=124   L3=124   L4=124   L5=124
workflow_step_count             L1=27261 L2=27237 L3=27237
sas_row_count                   L1=4848  L2=4834  L3=4834  L4=24 (different concept)
consultant_row_count            L1=18911 L2=18911 L3=18911 L4=78  L5=78 (unique names)
moex_row_count                  L1=3492  L2=3492  L3=3492
live_operational_count                                              L6=1968
legacy_backlog_count                                                L6=126
```

Visa total check at L4: 3723 (Open) + 40 + 627 + 320 + 0 + 124 = 4834 ✓

### 18.6 Gaps Identified

| # | Gap | Severity | Phase to fix |
|---|---|---|---|
| G-1 | `workflow_step_count` missing from `open_doc_vs_docs_df_sas_filter` expected-divergence rule — SAS filter drops 24 total response rows not just 14 OPEN_DOC rows | WARN | Phase 1 patch or Phase 2 |
| G-2 | `sas_row_count` missing from `open_doc_vs_docs_df_sas_filter` expected-divergence rule — L1→L2 drop from 4848→4834 flagged as FAIL when it is expected | WARN | Phase 1 patch or Phase 2 |
| G-3 | `raw_submission_rows` baseline stale — recorded 6155, current GED has 6901 (+746); GED export has grown | INFO | Update baseline before Phase 3 |
| G-4 | `status_SAS_REF = 0` across L2–L4 — no SAS REF events visible in current RunContext. Needs investigation to confirm this is a real data state (no SAS REF in current GED) vs. a residual H-2/H-3 hazard | WARN | Phase 2 investigation |
| G-5 | `flat_doc_meta` not attached to `RunContext` dataclass (confirmed: `RunContext` has no `flat_doc_meta` field) — visa_global at L3 comes from WorkflowEngine re-computation, not the authoritative cache values | KNOWN (Phase 3 fix target) | Phase 3 |

### 18.7 Decision Items for Phase 2

| # | Decision | Recommended action |
|---|---|---|
| D-1 | Add `workflow_step_count` and `sas_row_count` to `open_doc_vs_docs_df_sas_filter` expected-divergence rule in `EXPECTED_DIVERGENCES`, or create a separate `sas_filter_response_rows` rule, to eliminate the two FAIL → WARN promotion and get to FAIL=1 (only baseline `raw_submission_rows`) | Add categories to existing rule |
| D-2 | Update `raw_submission_rows` baseline from 6155 → 6901 to reflect current GED export state | Update `EXPECTED_BASELINES` |
| D-3 | Confirm `status_SAS_REF = 0` is expected data state. If so, add a note in §4. If not, investigate per H-2/H-3 hazard protocol | Verify against raw GED |
| D-4 | `adapt_overview` signature confirmed as `adapt_overview(dashboard_data: dict, app_state: dict)` — §17 Q2 resolved | ✓ Resolved |
| D-5 | `--run N` argument working; `run_number=0` resolves latest COMPLETED run — §17 Q3 resolved | ✓ Resolved |
| D-6 | `output/chain_onion/` artifact names confirmed from `src/chain_onion/exporter.py` — §17 Q4 resolved | ✓ Resolved |

---

## 19. Phase 2 Execution Report (2026-04-30T00:00:00Z)

### 19.1 Files modified

| File | Change |
|---|---|
| `scripts/audit_counts_lineage.py` | 1152 → 1686 lines (+534) |
| `tests/test_audit_counts_lineage.py` | 216 → 319 lines (+103) |
| `output/debug/counts_lineage_probe.json` | NEW |
| `output/debug/counts_lineage_probe.xlsx` | NEW |

Production source touched: **NONE** (`git status -- src/` → nothing to commit, working tree clean).

### 19.2 Validation results

| Check | Result |
|---|---|
| py_compile scripts/audit_counts_lineage.py | PASS |
| py_compile tests/test_audit_counts_lineage.py | PASS |
| pytest tests/test_audit_counts_lineage.py -q | **19 passed** (0 failed) |
| --probe run | PASS — 119 records, 0 missing_origin_with_value |
| default audit run | PASS — files produced, shape unchanged |
| one-line stdout summary | `AUDIT: PASS=14 WARN=0 FAIL=3; first_unexpected_divergence=workflow_step_count@L2_STAGE_READ_FLAT` |

Note on PASS count change (15→14): Phase 1 had `status_SAS_REF` all-null/all-zero (PASS, no divergence). Phase 2 now measures L0=836 and L1=284, which creates an L0→L1 divergence flagged as FAIL. Simultaneously, the `raw_submission_rows` baseline FAIL (6155 vs 6901) is now PASS (6901 vs 6901). Net: FAIL count stays 3, PASS count decreases by 1.

### 19.3 Probe summary

| Field | Value |
|---|---|
| Rows in probe output | 119 |
| Layers covered | L0_RAW_GED .. L6_CHAIN_ONION |
| Categories covered | 17 |
| Rows where value_origin_type == "expected_baseline_literal" BEFORE fix | 0 (lineage table values were always measured from files, not hardcoded literals) |
| Rows where value_origin_type == "expected_baseline_literal" AFTER fix | 0 (same) |
| Rows where value_origin_type == "missing" and value is not None | 0 |

Breakdown of 119 records by origin type:
- `missing`: 58 (null values — layers where a category is not applicable)
- `computed_dataframe`: 19
- `aggregator_output`: 8
- `measured_excel`: 14
- `computed_runcontext`: 10
- `ui_adapter_output`: 6
- `chain_onion_artifact`: 4
- `expected_baseline_literal`: 0

The BASELINE_PROVENANCE constant was added to the script and mirrored into the `expected_baselines` block of `counts_lineage_audit.json` (key `raw_submission_rows_provenance`).

### 19.4 Previously hardcoded values

| category | layer | old (hardcoded/wrong) | new (measured) | source |
|---|---|---|---|---|
| `raw_submission_rows` | EXPECTED_BASELINES | 6155 (stale literal from §4 plan date) | 6901 (re-measured 2026-04-30) | input/GED_export.xlsx, "Doc. sous workflow, x versions", data rows 3..6903 |
| `status_SAS_REF` | L0_RAW_GED | null (not measured) | 836 (measured_excel) | input/GED_export.xlsx, "Doc. sous workflow, x versions", Réponse=="REF" OR-count under any 0-SAS section header |
| `status_SAS_REF` | L1_FLAT_GED_XLSX | null (not measured) | 284 (measured_excel) | output/intermediate/FLAT_GED.xlsx, sheet GED_RAW_FLAT, is_sas==True AND response_status_clean=="REF" |
| `status_SAS_REF` | L2_STAGE_READ_FLAT | 0 (incorrectly from visa_wf["SAS REF"], H-3 hazard) | 282 (computed_dataframe) | ctx.responses_df, approver_raw=="0-SAS" AND status_clean=="REF" |
| `status_SAS_REF` | L3_RUNCONTEXT_CACHE | 0 (same wrong source) | 282 (computed_dataframe) | same |
| `status_SAS_REF` | L4_AGGREGATOR | 0 (same wrong source) | 282 (computed_dataframe) | ctx.responses_df via collect_l4 |
| OPEN_DOC/SAS/CONSULTANT/MOEX | L1_FLAT_GED_XLSX | These were ALREADY measured in Phase 1 via GED_OPERATIONS["step_type"].value_counts(); never hardcoded literals in the lineage table. The §4 plan listed them as expected baselines used for comparison only. | unchanged | GED_OPERATIONS step_type |

### 19.5 Corrected SAS REF counts by layer

| layer | category | value | source |
|---|---|---|---|
| L0_RAW_GED | status_SAS_REF | **836** | input/GED_export.xlsx, "Doc. sous workflow, x versions", Réponse column under any 0-SAS section header (OR-distinct row count) |
| L1_FLAT_GED_XLSX | status_SAS_REF | **284** | output/intermediate/FLAT_GED.xlsx, sheet GED_RAW_FLAT, filter is_sas==True AND response_status_clean=="REF" |
| L2_STAGE_READ_FLAT | status_SAS_REF | **282** | ctx.responses_df, approver_raw=="0-SAS" AND status_clean=="REF" (2 rows fewer than L1 — SAS pre-2026 filter) |
| L3_RUNCONTEXT_CACHE | status_SAS_REF | **282** | same |
| L4_AGGREGATOR | status_SAS_REF | **282** | same (harness-computed from ctx.responses_df; aggregator's by_visa_global["SAS REF"] is still 0 — Phase 3 gap) |
| L5_UI_ADAPTER | status_SAS_REF | None | merged into visa_flow["ref"] by adapt_overview |

**L0 note:** The prior investigation (§18) reported 837 (836 in cycle 1 + 1 in cycle 2) by summing per-column counts. The actual OR-distinct row count is **836** because the single cycle-2 REF row is the same physical submission row as a cycle-1 REF row. 836 is the correct distinct-row value. The stop condition threshold (<500 or >900) was not triggered.

---

**PROPOSED OPEN ITEM (for project owner to log in 07_OPEN_ITEMS.md):**

RAW SAS REF rows 836 (input/GED_export.xlsx, "Doc. sous workflow, x versions", "Réponse" under both 0-SAS blocks, OR-distinct count) vs FLAT_GED SAS REF rows 284 (output/intermediate/FLAT_GED.xlsx, sheet GED_RAW_FLAT, filter is_sas=True AND response_status_clean="REF"). A further 2-row gap exists between FLAT_GED L1 (284) and RunContext L2 (282) — likely the SAS pre-2026 filter in stage_read_flat removing 2 SAS REF docs. Likely active-version / instance-resolution projection in src/flat_ged/* — NOT a confirmed bug. Do not touch src/flat_ged/*. Requires a read-only RAW → FLAT SAS REF trace as a separate ticket.

---

### 19.6 Is D-1 safe to apply now?

**YES.**

The probe output confirms:
- `workflow_step_count` at L1 is `value_origin_type="measured_excel"` from `GED_RAW_FLAT` row count; at L2 is `computed_dataframe` from `ctx.responses_df` row count. Neither is a hardcoded baseline.
- `sas_row_count` at L1 is `value_origin_type="measured_excel"` from `GED_OPERATIONS["step_type"].value_counts()["SAS"]`; at L2 is `computed_dataframe` from `ctx.responses_df` where `approver_raw=="0-SAS"`.

Both are real measured sources. Extending `open_doc_vs_docs_df_sas_filter` to cover `workflow_step_count` and `sas_row_count` would correctly classify the L1→L2 drop as the known SAS pre-2026 filter cascade and reduce FAIL from 3 to 1 (only `status_SAS_REF@L1`, which is the newly surfaced RAW→FLAT SAS REF projection gap — a legitimate unexplained divergence that deserves its own tracking ticket).

### 19.7 Risk confirmation

- **production source untouched:** `git status -- src/` → `nothing to commit, working tree clean` ✓
- **no pipeline rerun** ✓
- **no cache rebuild forced** ✓ (cache hit on both default and probe runs)
- **no context/* or README.md edits** ✓

---

## §20 — Step 2.5 Report: D-1 Rule Extension + D-012 SAS Pre-2026 Confirmation

**Closed 2026-04-30.**

### 20.1 Objective

Two audit-only tasks:

- **D-1 (TASK A):** Extend the `open_doc_vs_docs_df_sas_filter` divergence rule in `EXPECTED_DIVERGENCES` to cover `workflow_step_count` and `sas_row_count` for the `L1_FLAT_GED_XLSX → L2_STAGE_READ_FLAT` layer pair, reclassifying 2 FAILs as expected.
- **D-012 (TASK B):** Confirm (or characterise) the 2-row gap between L1 `status_SAS_REF` (284) and L2 (282) via a programmatic helper that writes `output/debug/sas_pre2026_confirmation.json`.

### 20.2 Files changed

| File | Change |
|---|---|
| `scripts/audit_counts_lineage.py` | Extended `open_doc_vs_docs_df_sas_filter` categories; added `_confirm_sas_pre2026_gap` helper; wired into `run_audit` |
| `tests/test_audit_counts_lineage.py` | 6 new tests (4 for D-1, 2 for D-012 shape + verdict) |
| `context/07_OPEN_ITEMS.md` | D-012 closed PARTIAL_CONFIRMED; step 2.5 row updated |

No `src/`, `ui/`, `app.py`, `main.py`, `data/*`, or `runs/*` files were touched.

### 20.3 D-1 result

`open_doc_vs_docs_df_sas_filter` now covers five categories:

```
active_version_count, numero_indice_count, open_doc_row_count,
workflow_step_count, sas_row_count
```

Audit result:

```
AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
```

The sole remaining FAIL is `status_SAS_REF@L1_FLAT_GED_XLSX` (D-011 — the RAW→FLAT SAS REF projection gap, 836→284, tracked separately, not silenced).

### 20.4 D-012 result: PARTIAL_CONFIRMED

The 2-row gap (L1 row_count=284, L2 row_count=282, row_gap=2) is explained by two distinct mechanisms:

| Component | Mechanism | Pair | Rows |
|---|---|---|---|
| `sas_filter_component = CONFIRMED` | SAS pre-2026 filter (`_apply_sas_filter_flat`) excludes `051020\|A` (submittal_date 2025-04-07, year < 2026) | `051020\|A` | 1 |
| `structural_component = PRESENT` | GED_RAW_FLAT contains 2 rows for `152012\|A` (multi-cycle SAS, one-row-per-(doc,approver,step) schema); RunContext normalises to 1 representation | `152012\|A` | 1 |

Pair-level gap: `pair_gap = l1_unique_pairs(283) − l2_unique_pairs(282) = 1` — fully explained by the SAS filter.
Row-level gap: `row_gap = l1_rows(284) − l2_rows(282) = 2` — 1 from SAS filter + 1 from structural normalisation.

**Overall verdict: PARTIAL_CONFIRMED.**

Evidence artifact: `output/debug/sas_pre2026_confirmation.json` (written on every default audit run).

### 20.5 No production code change required

Both mechanisms are expected behaviour:
- The SAS pre-2026 filter is intentional and documented in `stage_read_flat._apply_sas_filter_flat`.
- GED_RAW_FLAT multi-cycle duplicate rows are structurally normal for its one-row-per-(doc,approver,step) schema; RunContext deduplicates by design.

D-011 (RAW 836 → FLAT 284) remains open and is not affected by this step.

### 20.6 Test results

```
25 passed, 0 failed, 0 skipped
```

All 6 new tests pass. `test_d012_confirmation_emits_file` validates JSON shape against `_D012_REQUIRED_KEYS`. `test_d012_excluded_count` asserts `verdict == "PARTIAL_CONFIRMED"`, `sas_filter_component == "CONFIRMED"`, `structural_component == "PRESENT"`, `pair_gap == 1`, `row_gap == 2`, `sas_filter_explained_rows == 1`, `structural_normalization_rows == 1`, `sas_filter_excluded_pair == "051020|A"`, `"152012|A" in structural_duplicate_pairs`.

---

## 21. Phase 8 Step 3 Execution Report (2026-04-30T00:00:00Z)

### 21.1 Files modified

| File | Change | Notes |
|---|---|---|
| `src/reporting/data_loader.py` | +2 lines (914 → 916) | TASK A: `flat_ged_doc_meta` field on `RunContext`; TASK B: `flat_ged_doc_meta=flat_doc_meta or {}` kwarg in `_load_from_flat_artifacts` constructor call |
| `src/reporting/aggregator.py` | +17 lines net, −9 lines (511 → 519) | TASK C: `resolve_visa_global` helper (17 lines) inserted; TASK D: 5 call-site replacements + 4 now-dead `we = ctx.workflow_engine` lines removed |
| `tests/test_resolve_visa_global.py` | NEW, 80 lines | 12 pure-unit tests for `resolve_visa_global` |
| `tests/test_audit_counts_lineage.py` | +27 lines (496 → 523) | `test_runcontext_carries_flat_ged_doc_meta` integration test added |
| `output/debug/counts_lineage_audit.PRE_STEP3.json` | NEW (snapshot) | Copy of audit JSON taken before any code edit |

Production source modified: `data_loader.py`, `aggregator.py`.

`git status -- src/`:
```
warning: in the working copy of 'src/reporting/data_loader.py', LF will be replaced by CRLF the next time Git touches it
 src/reporting/aggregator.py  | 33 ++++++++++++++++++++++++---------
 src/reporting/data_loader.py |  2 ++
 2 files changed, 26 insertions(+), 9 deletions(-))
```

### 21.2 Validation results

| Check | Result |
|---|---|
| py_compile (data_loader.py, aggregator.py) | **PASS** |
| py_compile (app.py, main.py, run_chain_onion) | **PASS** |
| pytest test_resolve_visa_global.py | **12 passed, 0 failed** |
| pytest test_audit_counts_lineage.py | **26 passed, 0 failed, 0 skipped** |
| default audit run | **PASS** |
| audit one-liner | `AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX` |
| --probe run | **PASS** — 119 records, 0 missing_origin_with_value, 0 expected_baseline_literal |
| app smoke (`python -c "import app"`) | exit code 0, `app import OK` — no traceback |

### 21.3 KPI shifts after the patch (BEFORE → AFTER)

**No L4/L5 KPI shifts detected.** Diffing `counts_lineage_audit.PRE_STEP3.json` vs the new `counts_lineage_audit.json` shows zero changes at L4_AGGREGATOR or L5_UI_ADAPTER for any category.

Explanation: the WorkflowEngine and `flat_doc_meta` are in agreement for all docs in the current run. The patch is **preventative** — it ensures the authoritative flat_doc_meta source is used going forward. In any future run where the two paths diverge (e.g. a new SAS REF doc whose `compute_visa_global_with_date` returns `(None, None)` while flat_doc_meta has `"SAS REF"`), the aggregator will now correctly use the flat value instead of the WorkflowEngine fallback.

No L4 number moved away from its corresponding L2/L3 value — stop condition not triggered.

### 21.4 Patch summary

- **RunContext**: new field `flat_ged_doc_meta: dict = field(default_factory=dict)` appended after `moex_countdown`. Default is `{}`, so the legacy raw-GED fallback constructor (which does not pass `flat_doc_meta`) produces a safe empty dict automatically.
- **`_load_from_flat_artifacts`**: passes `flat_ged_doc_meta=flat_doc_meta or {}` to the single `RunContext(...)` constructor call (line ~552). Legacy constructor not modified.
- **`resolve_visa_global(ctx, doc_id)` added** to `aggregator.py` immediately before `compute_project_kpis`. Returns `(visa, None)` for flat_doc_meta hits; delegates to `ctx.workflow_engine.compute_visa_global_with_date(doc_id)` when doc absent or visa falsy.
- **5 call sites in aggregator.py** now route through the helper. Orphaned `we = ctx.workflow_engine` assignments at 4 sites were removed (CLAUDE.md §3 — surgical changes: remove dead code created by your edit).

**flat_doc_meta key names verified against `stage_read_flat.py:_compute_doc_meta` (lines 316-323):**

| Key expected by brief | Actual key in flat_doc_meta | Status |
|---|---|---|
| `visa_global` | `visa_global` | ✅ present — used |
| `visa_global_date` | *absent* | ⚠ not stored by stage_read_flat |

**Phase 3 accepted limitation (Option A, project-owner approved 2026-04-30):** `vdate` is always `None` for flat_doc_meta hits. This is consistent with `stage_read_flat.get_visa_global()`'s documented behaviour ("date is not pre-computed by the adapter"). As a result, `avg_days_to_visa` in `compute_project_kpis` will fall back to WorkflowEngine vdate only when the engine's visa matches. This is a minor sample-size effect, non-crashing, and accepted for Phase 3.

### 21.5 Out-of-scope items NOT touched (recap)

- **D-010** (`_precompute_focus_columns` in `data_loader.py` also calls `compute_visa_global_with_date` directly) — separate ticket, left as-is.
- **Legacy raw-GED RunContext constructor** — `default_factory=dict` on the new field handles it; constructor not modified.
- **`CACHE_SCHEMA_VERSION`** — unchanged. Cache already carries `flat_doc_meta`. No cache rebuild forced. Cache file mtimes (all 2026-04-29) confirm this.
- **`src/pipeline/stages/stage_read_flat.py`** — READ ONLY throughout step 3; not modified.
- **`ui_adapter.py`** — Phase 8 step 6 territory; not touched.

### 21.6 Proposed open-item updates (for project owner to log in 07_OPEN_ITEMS.md)

```
PROPOSED in 07_OPEN_ITEMS.md:
  - G-5 → CLOSED. flat_ged_doc_meta now reaches RunContext (TASK A + TASK B).
  - Phase 8 status table: step 3 → ✅ closed 2026-04-30.
  - D-010 → still open (out of scope, untouched — _precompute_focus_columns
    calls compute_visa_global_with_date directly; separate ticket needed).
```

### 21.7 Risk confirmation

- Production diff is exactly the four edits stated in §21.4. `git diff --stat -- src/` shows only `data_loader.py` (+2) and `aggregator.py` (+17/−9).
- No pipeline rerun.
- No cache rebuild forced. `output/intermediate/FLAT_GED_cache_*` mtimes all read 2026-04-29 22:24:41 — unchanged.
- No edits to `context/*` or `README.md`.

---

### 21.8 Step 3 vdate addendum (2026-04-30)

#### What was wrong

The original step-3 `resolve_visa_global` returned `(visa, None)` for all `flat_doc_meta` hits. `compute_project_kpis` builds `avg_days_to_visa` via:

```python
_, vdate = resolve_visa_global(ctx, doc_id)
if vdate and row.get("created_at") is not None:
    visa_dates.append((vdate - row["created_at"]).days)
```

Because `vdate` was always `None` for flat hits, the guard `if vdate` never fired for any doc whose visa came from `flat_doc_meta`. `visa_dates` accumulated zero samples and `avg_days_to_visa` became `None` (or remained 0 if no engine hits existed for those docs).

#### What changed

`resolve_visa_global` now calls `ctx.workflow_engine.compute_visa_global_with_date(doc_id)` **even when `flat_doc_meta` supplies the visa**, to obtain the real vdate:

```python
def resolve_visa_global(ctx, doc_id):
    meta = getattr(ctx, "flat_ged_doc_meta", None) or {}
    entry = meta.get(doc_id)
    if entry:
        visa = entry.get("visa_global")
        if visa:
            _, vdate = ctx.workflow_engine.compute_visa_global_with_date(doc_id)
            return visa, vdate
    return ctx.workflow_engine.compute_visa_global_with_date(doc_id)
```

This preserves the flat_doc_meta visa (authoritative, fixes SAS REF gaps) while pulling the date from the WorkflowEngine (which does carry vdate for docs it resolves). The two can diverge only for SAS REF docs where the engine returns `(None, None)` — those docs contribute `visa` from meta and `vdate=None` from the engine, so they are still excluded from the `avg_days_to_visa` sample, which is the correct behaviour (no decision date to measure against).

#### Files modified

| File | Change |
|---|---|
| `src/reporting/aggregator.py` | `resolve_visa_global` body updated (lines 33–50) |
| `tests/test_resolve_visa_global.py` | `test_vdate_is_none_for_flat_meta_hit` renamed → `test_meta_hit_uses_engine_vdate`; assertion updated from `vdate is None` → `vdate == "WE_DATE"`. Parametrize test simplified. New test `test_meta_visa_uses_engine_vdate` added. Total: 13 tests. |

#### Validation results

| Check | Result |
|---|---|
| `pytest tests/test_resolve_visa_global.py` | **13 passed, 0 failed** |
| `pytest tests/test_audit_counts_lineage.py` | **26 passed, 0 failed** |
| `avg_days_to_visa` (compute_project_kpis, run 0) | **79.1** (non-null float — fix confirmed) |
| audit one-liner | `AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX` |

`avg_days_to_visa = 79.1` is a non-null float, satisfying the stop condition. The value is plausible for the portfolio (approx. 11 weeks average time to visa decision).

#### Risk

No new call sites touched. The only behavioural change is that `vdate` is no longer `None` for flat-meta hits where the WorkflowEngine can resolve the date. For SAS REF docs (engine returns `(None, None)`), behaviour is unchanged. No KPI shifts at L4/L5 relative to the §21.3 baseline (no new audit diff triggered — the flat and engine visas still agree for current run data).

---

## 22. Phase 8 Step 4 Execution Report (2026-04-30)

This section is being written by the project owner from the chat session,
not by Claude Code. Claude Code's step-4 execution report claimed both
`CACHE_SCHEMA_VERSION = "v2"` and "§22 appended" — verification against the
on-disk state showed neither was actually true: the constant remained `"v1"`
and §22 did not exist. Both were corrected from this chat (the constant via
direct Edit, §22 by writing this section). The 8-field payload extension
that Claude Code did apply landed correctly. Recording the discrepancy
here as a "trust but verify" data point for future agent-driven phases.

### 22.1 Files modified
- `src/reporting/data_loader.py` — `+24/-2` (8 audit fields appended to
  `_save_flat_normalized_cache` payload + comment-block bullet for the
  schema-version trigger). `+1/-1` correction by direct Edit (`CACHE_SCHEMA_VERSION = "v1"` → `"v2"`).
- `tests/test_cache_meta_v2.py` — NEW (3 read-only tests).

Production source touched: `data_loader.py` only. App.py / main.py /
run_chain_onion.py unaffected.

### 22.2 Validation results

**py_compile** (Windows + sandbox):
- `src/reporting/data_loader.py` — PASS
- `app.py` / `main.py` / `run_chain_onion.py` — PASS

**Cache rebuild trace** (Windows shell, post version-bump correction):
```
[FLAT_CACHE] Cache schema version mismatch (cache='v1' want='v2') — rejecting cache, will rebuild from FLAT_GED.xlsx
[1/7] Reading FLAT_GED (flat mode)...
[FLAT_CACHE] Cache written (schema=v2): C:\Users\GEMO 050224\Desktop\cursor\GF updater v3\output\intermediate
RunContext loaded: 4834 docs, 4834 dernier, 27237 responses
```

**Audit baseline checks** — all 10 PASS:
```
raw_submission_rows=6901, raw_unique_numero=2819, raw_unique_numero_indice=4848,
ged_raw_flat_rows=27261, ged_operations_rows=32099, open_doc_rows=4848,
sas_rows=4848, consultant_rows=18911, moex_rows=3492, stage_read_flat_docs_df_rows=4834
```

**Audit one-liner** (verbatim, post-rebuild):
```
AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
```
Unchanged vs. step 3 close. The remaining FAIL is the upstream D-011 SAS
REF projection gap, intentionally not silenced.

**App smoke** — `python -c "import app"` exit code 0 (sandbox).

**Pytest** — `tests/test_cache_meta_v2.py` not yet executed against the
fresh v2 cache; carried forward to the joint Windows-shell verification
pass alongside step 3's `tests/test_resolve_visa_global.py` per H-4.

### 22.3 Cache contents post-rebuild (verbatim from `output/intermediate/FLAT_GED_cache_meta.json`)

| Field | Value |
|---|---|
| `cache_schema_version` | `"v2"` |
| `source_flat_ged_sha256` | `0d960f8e2483f24873da29ae8b5e5f29579a575364848b0e6816996396a15b97` |
| `source_flat_ged_mtime` | `1777280366.6103282` |
| `docs_df_rows` | `4834` |
| `responses_df_rows` | `27237` |
| `active_version_count` | `4834` |
| `family_count` | `2819` |
| `status_counts` | `{VAO: 4622, VSO-SAS: 4365, HM: 3535, REF: 1535, VSO: 1233, FAV: 697, SUS: 136, DEF: 53, SYNTHETIC_VSO-SAS: 34}` |
| `generated_at` | `"2026-04-30T11:02:16.349163+00:00"` |

Cross-check vs. RunContext after `load_run_context(0)`:
- `docs_df_rows == ctx.docs_df.shape[0]` → 4834 == 4834 ✓
- `responses_df_rows == ctx.responses_df.shape[0]` → 27237 == 27237 ✓
- `active_version_count == ctx.docs_df["doc_id"].nunique()` → 4834 == 4834 ✓
- `family_count == ctx.docs_df["numero"].nunique()` → 2819 == 2819 ✓

### 22.4 Patch summary

- `CACHE_SCHEMA_VERSION` bumped `"v1"` → `"v2"` (final state on disk
  confirmed by reading `src/reporting/data_loader.py` line 89 after the
  direct-Edit correction).
- Comment block above the constant gained one bullet:
  `#   - cache_meta payload gains audit fields (Phase 8 step 4, 2026-04-30)`.
- `_save_flat_normalized_cache` payload extended with 8 audit fields
  (sha256 / mtime / docs_df_rows / responses_df_rows / active_version_count /
  family_count / status_counts / generated_at).
- Reader (`_load_flat_normalized_cache`) untouched. `_flat_cache_is_fresh`
  untouched — its existing schema-version check correctly rejected the
  v1 cache and forced the rebuild.
- `from datetime import date, datetime, timezone` — `timezone` added
  alongside the existing `datetime` import.

### 22.5 Out-of-scope items NOT touched (recap)

- `D-010` (`_precompute_focus_columns` parallel `compute_visa_global_with_date`
  call in `data_loader.py`) — separate ticket.
- `D-011` (RAW 836 → FLAT 284 SAS REF projection in `src/flat_ged/*`) —
  separate ticket; intentionally NOT silenced by step 4.
- `ui_adapter.py`, `aggregator.py` (other than the step-3 changes already
  landed), `runs/`, `data/*.db`, `ui/jansa/*` — untouched.

### 22.6 Risk confirmation

- Production source diff is exactly the one file (`data_loader.py`).
- No pipeline rerun.
- Cache rebuild was triggered by the schema-version bump (intended); ran
  in ~30s on Windows native; would have taken substantially longer in the
  Cowork sandbox (see H-5).
- No edits to `context/*` or `README.md` from Claude Code (those updates
  happen in the project chat per protocol).
- No manual `rm` of cache files.

### 22.7 Step 4 closed

Cache audit fields shipped, schema bump verified end-to-end via Windows
rebuild trace, audit one-liner unchanged. Step 5 (Chain+Onion source
alignment, MEDIUM risk) is the next decision.

---

## 23. Phase 8 Step 5 Execution Report (2026-04-30T11:23:00Z)

### 23.1 Files modified
- `src/chain_onion/source_loader.py`  (619 → 725 lines, +106)
- `tests/test_chain_onion_source_check.py`  (NEW, 136 lines, 7 tests)

Production source touched: `source_loader.py` only. `app.py` / `main.py` /
`run_chain_onion.py` unaffected.

```diff
diff --git a/src/chain_onion/source_loader.py b/src/chain_onion/source_loader.py
index b7cfa5b..fe371a5 100644
--- a/src/chain_onion/source_loader.py
+++ b/src/chain_onion/source_loader.py
@@ -196,6 +196,112 @@ def _build_ged_responses_for_composition(
     return pd.DataFrame(records)
 
 
+def _check_flat_ged_alignment(flat_ged_path: Path) -> None:
+    """
+    Compare flat_ged_path against the FLAT_GED artifact registered in
+    run_memory.db for the latest completed run.
+    WARN-only — never raises, never blocks. Writes receipts to
+    <flat_ged_parent>/../debug/chain_onion_source_check.json on every call.
+    """
+    import hashlib
+    import json as _json
+    from datetime import datetime, timezone
+
+    _arg = Path(flat_ged_path)
+    receipts: dict = {
+        "result": "UNDETERMINED",
+        "registered_flat_ged_path": None,
+        "using_flat_ged_path": str(_arg),
+        "sha_match": None,
+        "reason": "",
+        "checked_at": datetime.now(timezone.utc).isoformat(),
+    }
+
+    def _write() -> None:
+        try:
+            debug_dir = _arg.parent.parent / "debug"
+            debug_dir.mkdir(parents=True, exist_ok=True)
+            (debug_dir / "chain_onion_source_check.json").write_text(
+                _json.dumps(receipts, ensure_ascii=False, default=str),
+                encoding="utf-8",
+            )
+        except Exception:
+            pass
+
+    try:
+        resolved_using = _arg.resolve()
+
+        # Locate run_memory.db: try flat_ged-derived root first, then module root
+        db_path: Optional[Path] = None
+        for candidate in (
+            resolved_using.parent.parent.parent / "data" / "run_memory.db",
+            _SRC_DIR.parent / "data" / "run_memory.db",
+        ):
+            if candidate.exists():
+                db_path = candidate
+                break
+
+        if db_path is None:
+            receipts["reason"] = "run_memory.db not found"
+            _LOG.info("_check_flat_ged_alignment: result=UNDETERMINED — %s", receipts["reason"])
+            return
+
+        from reporting.data_loader import _get_artifact_path, _resolve_latest_run  # type: ignore
+
+        run_number = _resolve_latest_run(str(db_path))
+        if run_number is None:
+            receipts["reason"] = "no completed run in run_memory.db"
+            _LOG.info("_check_flat_ged_alignment: result=UNDETERMINED — %s", receipts["reason"])
+            return
+
+        registered_str = _get_artifact_path(str(db_path), run_number, "FLAT_GED")
+        if registered_str is None:
+            receipts["reason"] = f"FLAT_GED not registered for run {run_number}"
+            _LOG.info("_check_flat_ged_alignment: result=UNDETERMINED — %s", receipts["reason"])
+            return
+
+        resolved_registered = Path(registered_str).resolve()
+        receipts["registered_flat_ged_path"] = str(resolved_registered)
+
+        if resolved_using == resolved_registered:
+            receipts["result"] = "OK"
+        else:
+            def _sha256(p: Path) -> str:
+                h = hashlib.sha256()
+                with open(p, "rb") as f:
+                    for chunk in iter(lambda: f.read(65536), b""):
+                        h.update(chunk)
+                return h.hexdigest()
+
+            sha_match = _sha256(resolved_using) == _sha256(resolved_registered)
+            receipts["sha_match"] = sha_match
+            if sha_match:
+                receipts["result"] = "WARN_PATH_MISMATCH_SAME_CONTENT"
+                receipts["reason"] = (
+                    f"path mismatch, content identical — "
+                    f"using={resolved_using} registered={resolved_registered}"
+                )
+            else:
+                receipts["result"] = "WARN_PATH_AND_CONTENT_MISMATCH"
+                receipts["reason"] = (
+                    f"path and content differ — "
+                    f"using={resolved_using} registered={resolved_registered}"
+                )
+
+        _LOG.info(
+            "_check_flat_ged_alignment: result=%s using=%s registered=%s",
+            receipts["result"], resolved_using, receipts.get("registered_flat_ged_path"),
+        )
+
+    except Exception as exc:
+        receipts["result"] = "UNDETERMINED"
+        receipts["reason"] = str(exc)
+        _LOG.info("_check_flat_ged_alignment: result=UNDETERMINED reason=%s", exc)
+
+    finally:
+        _write()
+
+
 # ─────────────────────────────────────────────────────────────────────────────
 # Public functions
 # ─────────────────────────────────────────────────────────────────────────────
@@ -223,6 +329,7 @@ def load_flat_ged(flat_ged_path: Path) -> pd.DataFrame:
         )
 
     _LOG.info("load_flat_ged: reading GED_OPERATIONS from %s", flat_ged_path)
+    _check_flat_ged_alignment(flat_ged_path)
     ops_df = pd.read_excel(flat_ged_path, sheet_name="GED_OPERATIONS", dtype=str)
```

### 23.2 Validation results
- py_compile (`source_loader.py` / `run_chain_onion.py` / `app.py` / `main.py`): **PASS**
- `run_chain_onion.py` exit code: **0** (completed in 105.7s)
- `chain_onion_source_check.json` result: **OK**
- audit one-liner: `AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX`
  (expected: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX ✓)
- pytest `test_chain_onion_source_check.py`: **7 passed** in 1.45s
- app smoke: exit code **0**

### 23.3 Receipts file shape (verbatim from `output/debug/chain_onion_source_check.json`)

```json
{"result": "OK", "registered_flat_ged_path": "C:\\Users\\GEMO 050224\\Desktop\\cursor\\GF updater v3\\output\\intermediate\\FLAT_GED.xlsx", "using_flat_ged_path": "C:\\Users\\GEMO 050224\\Desktop\\cursor\\GF updater v3\\output\\intermediate\\FLAT_GED.xlsx", "sha_match": null, "reason": "", "checked_at": "2026-04-30T11:21:43.696481+00:00"}
```

### 23.4 Patch summary
- Helper `_check_flat_ged_alignment` added to `src/chain_onion/source_loader.py` at module scope,
  in the Private helpers section after `_build_ged_responses_for_composition`.
- Helper invoked once at `load_flat_ged`, line 332, immediately before the existing
  `pd.read_excel(flat_ged_path, sheet_name="GED_OPERATIONS", ...)` call.
- Helper is wrapped in `try/except` internally — never raises.
- Logs one INFO line per Chain+Onion run.
- Writes `output/debug/chain_onion_source_check.json` per run.
- No business logic in chain_onion modified.
- WARN-only. BLOCK mode NOT implemented.

### 23.5 Edge cases observed
- On the live run, paths matched exactly → result `OK`, `sha_match=null` (SHA not
  computed when paths are identical, by design).
- No UNDETERMINED cases hit during production validation.
- `run_memory.db` located via flat_ged-derived root heuristic
  (`flat_ged_path.parent.parent.parent / "data" / "run_memory.db"`), which is the
  standard project layout. Module-root fallback (`_SRC_DIR.parent / "data" / "run_memory.db"`)
  present as secondary for non-standard placements.

### 23.6 Out-of-scope items NOT touched
- BLOCK mode (separate later decision per §9.3 of the plan).
- `run_chain_onion.py` — pre-read confirmed it opens FLAT_GED.xlsx only through
  `load_chain_sources()` in `source_loader.py`. No direct open; READ ONLY, no edit.
- Any chain_onion module other than `source_loader.py`.

### 23.7 Risk confirmation
- Production source diff from this step is exactly `src/chain_onion/source_loader.py`.
  Note: `git diff --stat -- src/` also shows pre-existing uncommitted changes to
  `src/reporting/aggregator.py` and `src/reporting/data_loader.py` from prior steps
  (both were already marked `M` in git status at session start). Neither was touched
  by this step.
- No pipeline rerun.
- Chain+Onion produced its usual output artifacts (exit 0, 72 passed / 1 warning / 0 failed
  in validation harness, same as baseline).
- No edits to `context/*` or `README.md`.

---

## 24. Phase 8 Step 6 Execution Report (2026-04-30T UTC)

### 24.1 Files modified
- `scripts/audit_counts_lineage.py`  (1970 → 2293 lines, +323)
- `tests/test_audit_counts_lineage.py`  (525 → 797 lines, +272)

Production source touched: NONE.

```
git diff --stat -- src/
warning: in the working copy of 'src/chain_onion/source_loader.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'src/reporting/data_loader.py', LF will be replaced by CRLF the next time Git touches it
 src/chain_onion/source_loader.py | 107 +++++++++++++++++++++++++++++++++++++++
 src/reporting/aggregator.py      |  34 +++++++++++---
 src/reporting/data_loader.py     |  26 +++++++++-
 3 files changed, 156 insertions(+), 11 deletions(-)
```
(All three src/ files were already modified before this step — pre-existing M status in git at session start. This step did not touch any src/ file.)

### 24.2 Field-mapping table

| aggregator_path | ui_adapter_path | comparison_kind | notes |
|---|---|---|---|
| kpis.total_docs_current | overview.total_docs | numeric_equal | |
| kpis.total_docs_current | overview.visa_flow.submitted | numeric_equal | visa_flow.submitted mirrors total_docs_current |
| kpis.total_docs_all_indices | — | skipped | total_docs_all_indices not surfaced in adapt_overview |
| kpis.total_contractors | overview.project_stats.total_contractors | numeric_equal | |
| kpis.total_consultants | overview.project_stats.total_consultants | numeric_equal | |
| kpis.total_lots | — | skipped | total_lots not surfaced in adapt_overview |
| kpis.discrepancies_count | — | skipped | discrepancies_count not surfaced in adapt_overview |
| kpis.avg_days_to_visa | overview.project_stats.avg_days_to_visa | identity | float or None; passed through as-is |
| kpis.docs_pending_sas | overview.project_stats.docs_pending_sas | numeric_equal | |
| kpis.docs_sas_ref_active | — | skipped | docs_sas_ref_active not surfaced in adapt_overview |
| kpis.by_visa_global.VSO | overview.visa_flow.vso | numeric_equal | |
| kpis.by_visa_global.VAO | overview.visa_flow.vao | numeric_equal | |
| kpis.by_visa_global.HM | overview.visa_flow.hm | numeric_equal | |
| kpis.by_visa_global.Open | overview.visa_flow.pending | numeric_equal | open_count maps to visa_flow.pending |
| kpis.by_visa_global.REF | — | skipped | adapt_overview merges REF+SAS_REF into visa_flow.ref |
| kpis.by_visa_global.SAS REF | — | skipped | adapt_overview merges REF+SAS_REF into visa_flow.ref |
| kpis.by_visa_global_pct | — | skipped | pct dict not surfaced in adapt_overview |
| kpis.by_building | — | skipped | by_building not surfaced in adapt_overview |
| kpis.by_responsible | — | skipped | by_responsible not surfaced in adapt_overview |
| kpis.focus_stats | overview.focus | skipped | focus fields only present when focus_result active |

Total: 20 entries (9 numeric_equal, 1 identity, 10 skipped).

### 24.3 Validation results
- py_compile                            : PASS
- default audit run                     : PASS
- --probe run                           : PASS
- pytest (new Step 6 tests only, 7 tests): 7 passed in ~75s (test_existing_one_liner_unchanged calls run_audit once; full suite times out at 30s due to pre-existing slow run_audit callers — inconclusive for full suite, see H-4)
- audit one-liner                       : `AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX`
  (expected: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX ✓)
- UI_PAYLOAD line                       : `UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match`
- app smoke                             : exit code 0

### 24.4 ui_payload_comparison block (verbatim from JSON)

```json
{
  "fields_compared": 10,
  "matches": 10,
  "mismatches": 0,
  "mismatch_rows": [],
  "skipped": [
    {
      "aggregator_path": "kpis.total_docs_all_indices",
      "ui_adapter_path": null,
      "comparison_kind": "skipped",
      "notes": "total_docs_all_indices not surfaced in adapt_overview",
      "reason": "total_docs_all_indices not surfaced in adapt_overview"
    },
    {
      "aggregator_path": "kpis.total_lots",
      "ui_adapter_path": null,
      "comparison_kind": "skipped",
      "notes": "total_lots not surfaced in adapt_overview",
      "reason": "total_lots not surfaced in adapt_overview"
    },
    {
      "aggregator_path": "kpis.discrepancies_count",
      "ui_adapter_path": null,
      "comparison_kind": "skipped",
      "notes": "discrepancies_count not surfaced in adapt_overview",
      "reason": "discrepancies_count not surfaced in adapt_overview"
    },
    {
      "aggregator_path": "kpis.docs_sas_ref_active",
      "ui_adapter_path": null,
      "comparison_kind": "skipped",
      "notes": "docs_sas_ref_active not surfaced in adapt_overview",
      "reason": "docs_sas_ref_active not surfaced in adapt_overview"
    },
    {
      "aggregator_path": "kpis.by_visa_global.REF",
      "ui_adapter_path": null,
      "comparison_kind": "skipped",
      "notes": "adapt_overview merges REF+SAS_REF into visa_flow.ref; individual REF not comparable",
      "reason": "adapt_overview merges REF+SAS_REF into visa_flow.ref; individual REF not comparable"
    },
    {
      "aggregator_path": "kpis.by_visa_global.SAS REF",
      "ui_adapter_path": null,
      "comparison_kind": "skipped",
      "notes": "adapt_overview merges REF+SAS_REF into visa_flow.ref; individual SAS_REF not comparable",
      "reason": "adapt_overview merges REF+SAS_REF into visa_flow.ref; individual SAS_REF not comparable"
    },
    {
      "aggregator_path": "kpis.by_visa_global_pct",
      "ui_adapter_path": null,
      "comparison_kind": "skipped",
      "notes": "pct dict not surfaced in adapt_overview",
      "reason": "pct dict not surfaced in adapt_overview"
    },
    {
      "aggregator_path": "kpis.by_building",
      "ui_adapter_path": null,
      "comparison_kind": "skipped",
      "notes": "by_building not surfaced in adapt_overview",
      "reason": "by_building not surfaced in adapt_overview"
    },
    {
      "aggregator_path": "kpis.by_responsible",
      "ui_adapter_path": null,
      "comparison_kind": "skipped",
      "notes": "by_responsible not surfaced in adapt_overview",
      "reason": "by_responsible not surfaced in adapt_overview"
    },
    {
      "aggregator_path": "kpis.focus_stats",
      "ui_adapter_path": "overview.focus",
      "comparison_kind": "skipped",
      "notes": "focus fields only present when focus_result is active; not comparable in unfocused audit run",
      "reason": "focus fields only present when focus_result is active; not comparable in unfocused audit run"
    }
  ]
}
```

### 24.5 Mismatches found
**None.** `mismatches=0`. All 10 compared fields match exactly between aggregator and ui_adapter.
No follow-up ticket required.

### 24.6 Out-of-scope items NOT touched
- `ui_adapter.py` / `aggregator.py` — production source untouched.
- JSX files — untouched.
- The existing AUDIT one-liner — byte-identical to before.
- `context/*`, `README.md` — untouched.

### 24.7 Risk confirmation
Production source diff: NONE (all `src/` diffs are pre-existing from prior steps).

```
git status -- src/
        modified:   src/chain_onion/source_loader.py
        modified:   src/reporting/aggregator.py
        modified:   src/reporting/data_loader.py
```
(Pre-existing M status before this step began — not introduced by this step.)

No pipeline rerun. No edits to `context/*` or `README.md`.
