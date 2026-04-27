# STEP 01 — Repository Source Map
Chain + Onion Reconnaissance

**Status:** COMPLETE — No code modified.
**Date:** 2026-04-27
**Strategy ref:** CHAIN_ONION_MASTER_STRATEGY.md

---

## 0. Chain Identity Model (Binding — applies from Step 02 onward)

This three-level model is the official identity contract for Chain + Onion.
It was established as a refinement of Step 01 findings before Step 02 opened.
**Every subsequent step must use these keys exactly as defined here.**

| Level | Key | Definition | Used for |
|-------|-----|------------|----------|
| Family | `FAMILY_KEY` | `numero` | Grouping all versions and submissions of one document family |
| Version | `VERSION_KEY` | `numero + indice` | One revision of a document (e.g. A, B, C) |
| Instance | `INSTANCE_KEY` | `numero + indice + submission_instance_id` — if known; else `numero + indice + seq_N` (synthetic sequence) | One submission event within a version |

**Rules:**

- `FAMILY_KEY` is the top-level chain grouping. A chain spans all indices of one `numero`.
- `VERSION_KEY` is stable across pipeline runs. Use it as the chain segment identifier.
- `INSTANCE_KEY` uses `submission_instance_id` from `DEBUG_TRACE.csv` when available. When DEBUG_TRACE is absent or the field is blank, generate a deterministic synthetic sequence: `seq_1`, `seq_2`, … ordered by `step_order` ascending within the version group.
- `doc_id` (UUID in `effective_responses_df`) is **session-scoped** and must never be used as a chain identity key.
- `(numero, indice)` = `VERSION_KEY`. This is what GED_OPERATIONS uses natively. It is the primary join key between `ops_df` and all chain structures.

---

## 1. Files Inspected

| File | Purpose |
|------|---------|
| `src/flat_ged/__init__.py` | Public API wrapper for the frozen builder |
| `src/flat_ged/cli.py` | Builder entry point (`run_batch`, `run_single`) |
| `src/flat_ged/reader.py` | GED workbook I/O + header parsing |
| `src/flat_ged/transformer.py` | Full per-document pipeline: raw_flat → operations → debug |
| `src/flat_ged/writer.py` | FLAT_GED.xlsx + DEBUG_TRACE.csv + run_report.json output |
| `src/flat_ged/config.py` | Phase windows (SAS=15d, Global=30d), canonical constants |
| `src/flat_ged_runner.py` | Safe wrapper — calls builder in batch mode, validates outputs |
| `src/effective_responses.py` | Composition layer: GED_OPERATIONS + report_memory → truth |
| `src/query_library.py` | Read-only query layer over flat GED + effective_responses |
| `src/reporting/data_loader.py` | UI RunContext loader (artifact-first path + legacy fallback) |
| `src/pipeline/stages/stage_read_flat.py` | Flat GED adapter: parses FLAT_GED.xlsx → docs_df + responses_df |
| `output/intermediate/FLAT_GED.xlsx` | Live artifact: sheets GED_RAW_FLAT, GED_OPERATIONS |
| `output/intermediate/DEBUG_TRACE.csv` | Live artifact: full audit trail (one row per approver per doc) |
| `output/intermediate/flat_ged_run_report.json` | Live artifact: builder summary stats |

---

## 2. Key Functions and Their Signatures

### 2a. FLAT_GED Loading

**Entry point:** `src/flat_ged/__init__.py → build_flat_ged()`

```python
build_flat_ged(
    ged_xlsx_path: Path,
    output_dir: Path,
    *,
    mode: str = "batch",   # "batch" or "single"
    numero: int | None = None,
    indice: str | None = None,
) -> dict   # contents of run_report.json
```

Side effects: writes `FLAT_GED.xlsx`, `DEBUG_TRACE.csv` (batch mode only), `run_report.json` to `output_dir`.

**Safe wrapper:** `src/flat_ged_runner.py → build_flat_ged_artifacts()`

```python
build_flat_ged_artifacts(ged_path: Path, intermediate_dir: Path) -> dict
# Returns:
# {
#   "success": True,
#   "flat_ged_path": str,
#   "debug_trace_path": str | None,
#   "run_report_path": str,
#   "builder_result": dict,
# }
```

Performs prechecks, calls `build_flat_ged(mode="batch")`, validates outputs, renames `run_report.json → flat_ged_run_report.json`.

**UI consumption:** `src/reporting/data_loader.py → _load_from_flat_artifacts()`

Reads the registered `FLAT_GED` artifact from `run_memory.db`, calls `stage_read_flat()` to parse both sheets into `docs_df` and `responses_df`, then runs `WorkflowEngine` and report memory composition on top.

**Flat adapter:** `src/pipeline/stages/stage_read_flat.py → stage_read_flat(ctx)`

Reads sheets `GED_RAW_FLAT` and `GED_OPERATIONS` from `FLAT_GED.xlsx`, reconstructs `docs_df` + `responses_df` in legacy-compatible shape. Exposes:
- `ctx.flat_ged_ops_df` — raw GED_OPERATIONS DataFrame (37 cols)
- `ctx.flat_ged_doc_meta` — per-doc dict `{doc_id: {closure_mode, visa_global, responsible_party, data_date}}`
- `ctx.flat_ged_mode = "flat"`

**Internal reader:** `src/flat_ged/reader.py`

- `open_workbook_fast(path)` — SAX streaming, read_only=True (batch mode, ~40× faster)
- `open_workbook(path)` — full load (single/debug mode)
- `read_data_date_fast(wb)` — reads DATA_DATE from `Détails!D15` via row iteration
- `parse_ged_header_batch(ws)` → `(base_cols, approver_groups, data_rows_iterator)` — streaming, does not materialise full sheet

---

### 2b. DEBUG_TRACE Handling

**Producer:** `src/flat_ged/transformer.py`

DEBUG_TRACE rows are built by `build_raw_flat()` (one entry per approver column, including skipped ones — unlike `GED_RAW_FLAT` which skips Exception List and NOT_CALLED). Columns:

```
numero, approver_raw, actor_type, ged_ref_date, ged_ref_resp, ged_ref_cmt,
raw_date, raw_status, raw_comment, mapped_canonical, mapped_status_clean,
status_code, status_scope, ged_extracted_deadline, date_status_type,
computed_sas_deadline, computed_phase_deadline, deadline_source, data_date_used,
doc_code, submission_instance_id, instance_role, instance_resolution_reason
```

Computed fields (`computed_sas_deadline`, `computed_phase_deadline`, `deadline_source`, `data_date_used`) are back-filled in-place by `fill_debug_deadlines()` after phase deadline computation.

Synthetic SAS rows (when SAS was never called in GED) are appended to both `raw_flat` and `debug_rows` by `add_synthetic_sas()`, with tag `[SYNTHETIC]` in `approver_raw`.

**Writer (batch):** `src/flat_ged/writer.py → write_debug_trace_csv(output_dir, all_debug) → Path`

Writes `DEBUG_TRACE.csv` with UTF-8 BOM. In batch mode, this is always a CSV (Excel write_only at 400k+ rows would take ~47s vs 0.5s for CSV).

**Writer (single mode):** `write_flat_ged()` — embeds DEBUG_TRACE as Sheet 3 in FLAT_GED.xlsx (styled, with conditional fills).

**Lifetime:** DEBUG_TRACE is a **build-time audit artifact** only. It is NOT loaded by the UI or `stage_read_flat`. It is not part of `ctx` after the pipeline run.

---

### 2c. effective_responses Generation

**Module:** `src/effective_responses.py`

Two public functions:

**`normalize_persisted_report_responses_for_merge(df) → pd.DataFrame`**
- Applies gates E2 (confidence HIGH/MEDIUM only) and E6 (at least status or date present)
- Deduplicates to one row per `(doc_id, approver_canonical)` — winner = highest confidence → latest date → latest ingested_at
- Returns standardised columns: `doc_id, approver_canonical, report_status, report_response_date, report_comment, source_filename, source_file_hash, match_confidence, match_method`

**`build_effective_responses(ged_responses_df, persisted_report_responses_df, flat_mode=False) → pd.DataFrame`**
- Left-join: GED is always the anchor. Reports cannot create new rows.
- Merge rules:
  - **Rule 1** (GED ANSWERED): GED wins. Reports may add comment (`GED+REPORT_COMMENT`) or flag conflict (`GED_CONFLICT_REPORT`). Never change status/date.
  - **Rule 2** (GED PENDING + eligible report with date): upgrade to ANSWERED (`GED+REPORT_STATUS`)
  - **Rule 3** (GED PENDING, no eligible report): remain pending
  - **Rule 4** (NOT_CALLED): reports cannot create a new step
- Adds two columns to every row:
  - `effective_source` — five-value vocabulary: `GED | GED+REPORT_STATUS | GED+REPORT_COMMENT | GED_CONFLICT_REPORT | REPORT_ONLY`
  - `report_memory_applied` — `bool`, True only on Rule 2 upgrades

**Call sites:**
- `src/reporting/data_loader.py` → both flat-artifact path and legacy raw-GED path call `build_effective_responses()` before returning `RunContext`
- `src/pipeline/stages/stage_report_memory.py` → pipeline-side call (same function)

**VAOB rule (2026-04-24 Eid decision):** `VAOB` is treated as approval-family (= VAO). Not a conflict against VSO/VAO. On ANSWERED GED rows, VAOB enriches comment only. On PENDING, VAOB may upgrade like VAO.

---

### 2d. Exports

**FLAT_GED.xlsx** (batch mode — 2 sheets, write_only streaming):
- Sheet `GED_RAW_FLAT` — 21 columns, one row per called non-exception approver per document. Columns defined in `writer.py::R_COLS`.
- Sheet `GED_OPERATIONS` — 37 columns (`O_COLS`), one step per actor per document (OPEN_DOC + SAS + CONSULTANTs + MOEX), in step_order. Contains all delay/deadline/cycle fields.

**FLAT_GED.xlsx** (single mode — 3 sheets, styled):
- Same as batch + Sheet `DEBUG_TRACE` with per-cell conditional fills.

**DEBUG_TRACE.csv** (batch mode only):
- 23 columns (`D_COLS`), UTF-8 BOM, one row per approver column per document (including skipped/NOT_CALLED).

**flat_ged_run_report.json** (renamed from `run_report.json`):
- Builder summary: counts, config, timing, error tallies.

**Output directory:** `output/intermediate/` (confirmed live: `FLAT_GED.xlsx`, `DEBUG_TRACE.csv`, `flat_ged_run_report.json` all present).

**run_memory.db artifact registry** (`data/run_memory.db`):
- Stores artifact paths by `artifact_type` in `run_artifacts` table. `FLAT_GED` is the registered type.
- `data_loader.py` queries `run_artifacts WHERE artifact_type='FLAT_GED'` to locate the file.

---

### 2e. Query Library Hooks

**Module:** `src/query_library.py`

**Entry point:** `QueryContext` dataclass

```python
@dataclass
class QueryContext:
    flat_ged_ops_df:        pd.DataFrame   # GED_OPERATIONS — structural truth
    effective_responses_df: pd.DataFrame   # composed truth (status + report memory)
    flat_ged_df:            Optional[pd.DataFrame] = None  # GED_RAW_FLAT (provenance checks only)
    flat_ged_doc_meta:      Optional[dict]         = None  # {doc_id: {visa_global, closure_mode, ...}}
```

**Identity note:** `flat_ged_ops_df` uses `(numero, indice)` as doc identity; `effective_responses_df` uses `doc_id` (UUID, pipeline-session-specific). These are NOT automatically bridged in `QueryContext`. Cross-querying requires the `id_to_pair` map from `stage_read_flat`.

**Function groups:**

| Group | Functions | Source df |
|-------|-----------|-----------|
| A. Portfolio KPIs | `get_total_docs`, `get_open_docs`, `get_closed_docs`, `get_pending_steps`, `get_answered_steps`, `get_overdue_steps`, `get_due_next_7_days` | ops_df / eff_df |
| B. Status Mix | `get_status_breakdown` → dict with approval/rejection/pending/overdue/hm/sas_ref/report_upgraded | eff_df |
| C. Consultant KPIs | `get_consultant_kpis` → DataFrame per actor | eff_df |
| D. Document Lifecycle | `get_doc_lifecycle` → DataFrame per (numero, indice) | ops_df |
| E. Queue Primitives | `get_easy_wins`, `get_conflicts`, `get_waiting_secondary`, `get_waiting_moex`, `get_stale_pending` | ops_df + eff_df |
| F. Fiche Inputs | `get_doc_fiche(ctx, doc_key)`, `get_actor_fiche(ctx, actor)` | ops_df + eff_df |
| G. Provenance & Quality | `get_effective_source_mix`, `get_report_upgrades`, `get_conflict_rows` | eff_df |

All functions are **pure** (no writes, no mutations). All raise `ValueError` on missing required DataFrames rather than silently returning zeros (except documented fallbacks).

---

## 3. Integration Opportunities for Chain + Onion

The following integration points are directly available without modifying any existing code:

### 3a. Primary source: GED_OPERATIONS via `flat_ged_ops_df`

`GED_OPERATIONS` (37 cols) is the richest single source for chain reconstruction. It contains:
- `numero`, `indice` → family identity
- `submission_instance_id` → instance disambiguation (one row = one submission instance + one actor step)
- `step_type` (OPEN_DOC / SAS / CONSULTANT / MOEX), `step_order` → event sequencing
- `response_date`, `submittal_date`, `sas_response_date` → timeline
- `status_clean`, `status_scope`, `status_family`, `is_completed`, `is_blocking`, `requires_new_cycle` → lifecycle state
- `step_delay_days`, `delay_contribution_days`, `cumulative_delay_days`, `delay_actor` → responsibility attribution
- `closure_mode` (MOEX_VISA / ALL_RESPONDED_NO_MOEX / WAITING_RESPONSES) → cycle closure

**Chain + Onion can load this directly from `output/intermediate/FLAT_GED.xlsx`, sheet `GED_OPERATIONS`, using `pd.read_excel()`.**

### 3b. DEBUG_TRACE for instance resolution context

`DEBUG_TRACE.csv` carries `doc_code`, `submission_instance_id`, `instance_role`, `instance_resolution_reason` — fields that explain why a given GED row was selected as ACTIVE over other submissions of the same document. This is useful for Onion Layer 1 (contractor quality: how many submission cycles, why was a submission superseded).

### 3c. effective_responses for composed status truth

`build_effective_responses()` in `src/effective_responses.py` can be called by `source_loader.py` to get the composed truth view (report memory upgrades applied). The `effective_source` column gives per-step provenance. This is Onion Layer 6 material (data/report discrepancy).

### 3d. query_library.py as a model

`QueryContext` and the query library's function structure are a direct template for `chain_onion/query_hooks.py`. The identity bridging note (ops uses numero/indice; eff_df uses UUID doc_id) is a known gap that Step 04 must resolve.

---

## 4. Risks

| Risk | Severity | Detail |
|------|----------|--------|
| **Identity gap: VERSION_KEY vs doc_id UUID** | HIGH | GED_OPERATIONS uses `(numero, indice)` = `VERSION_KEY`. `effective_responses_df` uses UUID `doc_id` (pipeline-session-specific). Chain + Onion uses the three-level model in §0. `FAMILY_KEY=numero` is the chain group; `VERSION_KEY=(numero, indice)` is the join key. Do NOT use `doc_id` as a stable cross-run identifier. |
| **submission_instance_id availability** | MEDIUM | `submission_instance_id` is present in `DEBUG_TRACE.csv` but NOT in `GED_OPERATIONS` (it is not in `O_COLS`). Chain reconstruction that needs to group by instance must join via `DEBUG_TRACE` or `GED_RAW_FLAT`. |
| **FLAT_GED is batch-mode only for DEBUG_TRACE** | LOW | In batch mode, DEBUG_TRACE is a CSV (not a sheet in FLAT_GED.xlsx). `source_loader.py` must read it separately from `output/intermediate/DEBUG_TRACE.csv`. |
| **frozen flat_ged/* package** | ENFORCED | `src/flat_ged/*` must not be touched. Chain + Onion is a consumer, not a modifier. All adapter code goes in `src/chain_onion/source_loader.py`. |
| **run_memory.db path dependency** | LOW | `data_loader.py` resolves FLAT_GED path via `run_memory.db`. Chain + Onion `source_loader.py` should accept the path as a parameter (not hard-code the DB lookup) to remain decoupled. |
| **effective_responses is session-scoped** | MEDIUM | `doc_id` UUIDs in `effective_responses_df` are generated fresh each pipeline run. They cannot be used as stable identifiers across runs. Chain history must key on `(numero, indice)`. |
| **No existing `output/chain_onion/` directory** | LOW | Target output dir does not exist yet. Step 04 source_loader must create it. |

---

## 5. Recommendation for Step 04 (Source Loader)

`src/chain_onion/source_loader.py` should implement:

```python
def load_flat_ged_ops(flat_ged_path: Path) -> pd.DataFrame:
    """Read GED_OPERATIONS sheet from FLAT_GED.xlsx. Read-only. No mutations."""

def load_debug_trace(debug_trace_path: Path) -> pd.DataFrame:
    """Read DEBUG_TRACE.csv. Provides submission_instance_id + instance_role fields."""

def load_effective_responses(
    flat_ged_ops_df: pd.DataFrame,
    report_memory_db_path: Path | None = None,
) -> pd.DataFrame:
    """
    Build effective_responses_df by calling build_effective_responses().
    If report_memory_db_path is None or db does not exist, return GED-only truth
    (no report memory enrichment).
    """

def build_chain_source(
    flat_ged_path: Path,
    debug_trace_path: Path,
    report_memory_db_path: Path | None = None,
) -> dict:
    """
    Top-level loader. Returns:
    {
        "ops_df":       pd.DataFrame,  # GED_OPERATIONS — chain backbone
        "debug_df":     pd.DataFrame,  # DEBUG_TRACE — instance resolution context
        "effective_df": pd.DataFrame,  # composed truth — status + provenance
        "data_date":    str,           # ISO date string from ops_df
    }
    """
```

**Key design rules for Step 04:**
1. Read FLAT_GED.xlsx and DEBUG_TRACE.csv directly by path — do not touch `run_memory.db`.
2. Apply the three-level identity model from §0: `FAMILY_KEY=numero`, `VERSION_KEY=(numero, indice)`, `INSTANCE_KEY=(numero, indice, submission_instance_id)`. Never use `doc_id` as a cross-run identifier.
3. Join `ops_df` and `debug_df` on `(numero, indice)` (`VERSION_KEY`). GED_OPERATIONS does not carry `submission_instance_id`; DEBUG_TRACE does. Use this join to attach instance resolution context to chain events.
4. When `submission_instance_id` is blank or DEBUG_TRACE is absent, synthesise `INSTANCE_KEY` as `(numero, indice, seq_N)` ordered by `step_order`.
5. All loads are read-only. No writes, no mutations of source DataFrames.
6. Log a clear warning if DEBUG_TRACE.csv is absent (batch mode only artifact — may be missing on single-mode runs).

---

## 6. What Now Works

- Full read path for FLAT_GED.xlsx (GED_RAW_FLAT + GED_OPERATIONS) is understood
- DEBUG_TRACE.csv schema is fully documented (23 columns, batch-only)
- `effective_responses` composition logic and merge rules are fully mapped
- `query_library.py` function catalogue confirmed — direct model for `chain_onion/query_hooks.py`
- Export artifact locations confirmed (`output/intermediate/`)
- Identity gap (numero/indice vs doc_id) is documented and risk-rated

## 7. What Does Not Yet Exist

- `src/chain_onion/` directory (to be created in Step 04)
- `output/chain_onion/` directory (to be created in Step 04)
- Any chain data contract (Step 02)
- Any onion data contract (Step 03)

## 8. Next Blockers

1. **Step 02** — Chain data contract: define what a "Chain" record looks like (columns, identity, event schema). Must resolve how to map `submission_instance_id` from DEBUG_TRACE into the chain event model.
2. **Step 03** — Onion data contract: define the six responsibility layers and their scoring inputs. Layer 1 (contractor quality) needs submission cycle count from DEBUG_TRACE `instance_resolution_reason`. Layer 3–4 (consultant delay/rejection) reads directly from `GED_OPERATIONS delay_contribution_days`.
3. **Step 04** — Source loader implementation (once contracts are defined). Blocked only on Steps 02 and 03.
