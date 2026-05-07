#repo-map #protected #do-not-touch #risk

# Don't Touch Without Explicit Scope

> Areas that require a named task and explicit approval before modification.
> Source: `README.md §What Not To Touch`, `context/08_DO_NOT_TOUCH.md`.

---

## A. Frozen / business-critical code

### `src/flat_ged/` — frozen builder snapshot

**Why:** `src/flat_ged/__init__.py` line 4 explicitly: "DO NOT edit business rules in this package." The package uses a careful `sys.path.insert / sys.modules cleanup` dance to avoid shadowing identically-named modules at `src/`. Adapter changes must go in `src/pipeline/stages/stage_read_flat.py` instead.

**Risk:** Any change here may alter how FLAT_GED.xlsx is built, silently changing document counts and downstream pipeline behavior.

### `src/run_memory.py`

**Why:** Holds the artifact registry schema (`runs`, `run_inputs`, `run_artifacts`, `run_corrections`, `run_invalidation_log`). Schema changes are NOT automated. Migrations require explicit plans. sha256 verification is the integrity contract.

### `src/report_memory.py`

**Why:** Holds 1,245+ active consultant memory rows. Changes ripple to `stage_report_memory.py` and `data_loader.py`. Lowering the HIGH/MEDIUM confidence gate pollutes the consultant truth.

### `src/effective_responses.py`

**Why:** Composition layer used by BOTH pipeline (`stage_report_memory`) and UI (`data_loader`). Both paths must produce identical shapes. Changes here affect every downstream consumer of `effective_responses_df`.

### `src/pipeline/stages/stage_report_memory.py`

**Why:** Ingestion ORDER matters: deactivate answered → ingest new → load persisted → build effective. Reordering stages can corrupt the response composition.

### `src/pipeline/stages/stage_finalize_run.py`

**Why:** Registers every artifact in `run_memory.db`. If this fails mid-registration, the orchestrator's rollback path must activate. Replacing the registration loop requires preserving that path.

### `src/team_version_builder.py`

**Why:** Surgical patch of OGF preserving date formats, conditional fills, frozen panes. Cosmetic refactors here = direct user-visible regressions in the team deliverable.

---

## B. Production UI

### `ui/jansa-connected.html`

**Why:** The only production entrypoint. `app._resolve_ui()` raises `FileNotFoundError` if it's missing. No fallback exists.

### `ui/jansa/*.jsx` and `ui/jansa/*.js`

**Why:** Any shape change in `adapt_*` functions must be reflected in the corresponding JSX. The `data_bridge.js` contract (four window globals) is the shared interface between Python and React. Breaking it silently breaks all UI data.

Specifically sensitive:
- `shell.jsx` — App root, routing, focus toggle
- `data_bridge.js` — `window.OVERVIEW / CONSULTANTS / CONTRACTORS / FICHE_DATA` contract
- `tokens.js` — required by every component; missing = blank UI

### `src/reporting/document_command_center.py`

**Why:** Sole source of business logic for DCC: tag computation, search ranking, response grouping. Constants like `ENTREPRISE_DELAY_THRESHOLD_DAYS=15` have direct user-visible meaning. See `context/06_EXCEPTIONS_AND_MAPPINGS.md §I.3` before touching.

### `src/reporting/contractor_quality.py`

**Why:** Phase 7 business logic includes BENTIN_OLD legacy filter, dormant-time extension, strip-dormant patch (Phase 0 D-004). Read-only; modify only via a new phase plan.

### `src/reporting/chain_timeline_attribution.py`

**Why:** Reads `output/chain_onion/CHAIN_*.csv` + RunContext, applies the 10-day secondary cap (not enforced by chain_onion itself), produces DCC Chronologie data. Auto-refreshed at startup.

---

## C. Persistent state

### `data/run_memory.db`

**Why:** Currently holds run 0 only. Deleting it invalidates every cross-run artifact claim in the UI. `scripts/bootstrap_run_zero.py` exists for re-bootstrapping but starts from scratch.

### `data/report_memory.db`

**Why:** Holds all accumulated consultant truth. Deleting loses all report memory. `scripts/bootstrap_report_memory.py` starts from empty — you lose 1,245+ rows.

### `runs/run_0000/`

**Why:** Immutable baseline. sha256 verification will fail on the next run if any file is manually edited. Only `nuke_and_rebuild_run0.py` and `reset_to_clean_run0.py` are authorized to mutate it.

---

## D. Pipeline orchestration

### `src/run_orchestrator.py`

**Why:** `_patched_main_context` mutates path globals on the calling `main` module's namespace. This indirection is what allows multiple callers (UI, headless main, tests) to share the same pipeline. Do not replace with a configuration object.

### `src/pipeline/runner.py::_run_pipeline_impl`

**Why:** Reads paths from `ns = sys.modules["main"]`, NOT from `pipeline.paths`. Intentional — do not switch to direct imports.

### `src/pipeline/paths.py`

**Why:** Single source of truth for all directory constants. Do NOT compute paths from CWD.

---

## E. Chain+Onion

### `src/chain_onion/source_loader.py`

**Why:** Documents the identity model; `doc_id` UUID is session-scoped and must NOT be persisted to chain output CSVs.

### `src/chain_onion/exporter.py`

**Why:** Owns the contract for all 7 CSVs + XLSX + 2 JSONs. UI's chain_onion narrowing depends on `ONION_SCORES.csv` shape.

---

## F. Hardcoded business knowledge (sensitive, not forbidden)

Every value below has direct user-visible or contractual meaning. Changing them changes operational behavior.

| File | Constants |
|---|---|
| `src/config_loader.py` | `EXCLUDED_SHEETS`, `SHEET_YEAR_FILTERS` (pre-2026 BENTIN/LGD exclusion), `SHEET_EMETTEUR_FILTER` |
| `src/flat_ged/input/source_main/consultant_mapping.py` | `RAW_TO_CANONICAL`, `EXCEPTION_COLUMNS`, `CANONICAL_TO_DISPLAY`, `SPECIAL_CASES` |
| `src/flat_ged/input/source_main/status_mapping.py` | `VALID_STATUSES`, `BUREAU_CONTROLE_STATUSES`, `PENDING_KEYWORDS`, `DEADLINE_DATE_PATTERN` |
| `src/flat_ged/input/source_main/ged_parser_contract.py` | Header layout, `CORE_COLUMNS`, `APPROVER_SUB_FIELDS` |
| `src/reporting/focus_ownership.py` | PRIMARY/SECONDARY/MOEX classification, `TERMINAL_VISA`, `SECONDARY_WINDOW_DAYS=10` |
| `src/reporting/consultant_fiche.py` | `CONSULTANT_DISPLAY_NAMES`, `STATUS_LABELS_BY_CANONICAL`, `BET_MERGE_KEYS`, `COMPANY_TO_CANONICAL`, `CONTRACTOR_REFERENCE` |
| `src/pipeline/stages/stage_discrepancy.py` | Part H-1 `BENTIN_LEGACY_EXCEPTION` pass |
| `src/pipeline/stages/stage_report_memory.py` | `_ELIGIBLE_CONFIDENCE_VALUES` |

---

## G. Files that look orphaned but aren't

| File | Why keep |
|---|---|
| `src/normalize.py::_GED_APPROVER_MAPPING` | Historical; may still be referenced; verify before removing |
| `src/reporting/bet_report_merger.py` | RETIRED per README; import commented out; archive, don't delete |
| `input/Mapping.xlsx` | Not consumed at pipeline runtime; may be source for hardcoded values that get refreshed periodically |

---

**Related:** [[10_PERSISTENCE_RUN_AND_REPORT_MEMORY]] · [[04_PIPELINE_STAGES]] · [[11_DEBUGGING_SEAMS]] · [[13_SAFE_DEBUGGING_PROTOCOL]]

*Back to [[00_START_HERE]]*
