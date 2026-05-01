# 08 — Do Not Touch

> Files and modules that are sensitive enough that any change requires an
> explicit task. Verified against actual code, README, and runtime usage.

The point of this list is to slow Claude (and anyone else) down when about
to edit one of these. It is NOT a prohibition. It IS a "stop, name what you
intend to change, get approval".

---

## A. Frozen / business-critical

### `src/flat_ged/` — frozen builder snapshot

`src/flat_ged/__init__.py` line 4: "DO NOT edit business rules in this
package. See BUILD_SOURCE.md."

Logic for the FLAT_GED.xlsx artifact lives here. The builder is treated as
a read-only third-party module. Adapter changes go in
`src/pipeline/stages/stage_read_flat.py` instead.

The package directory's bare imports (`config`, `reader`, `resolver`,
`transformer`, `writer`, `validator`, `utils`) are loaded via a
sys.path.insert / sys.modules cleanup dance to avoid shadowing identically
named modules at `src/` (notably `writer.py`). Do not "improve" the import
mechanics.

### `src/run_memory.py` — persistent artifact registry

Schema: `runs`, `run_inputs`, `run_artifacts`, `run_corrections`,
`run_invalidation_log`. Migrations are NOT automated. Schema changes need
explicit migration plans. Sha256 verification is the integrity contract.

### `src/report_memory.py` — persistent consultant truth

Holds 1,245+ active rows (per README; verified at runtime). Survives across
runs. The HIGH/MEDIUM confidence gate is enforced in
`stage_report_memory.py` — do not lower it casually.

### `src/effective_responses.py` — effective response composer

Composes GED responses with persisted report memory. Used by both
`stage_report_memory` (pipeline path) and `data_loader` (UI path). Both
must produce identical shapes; changes here ripple everywhere.

### `src/pipeline/stages/stage_report_memory.py` — composition stage

Couples report memory ingestion with effective_responses build. The
ingestion order matters (deactivate answered → ingest new → load
persisted → build effective).

### `src/pipeline/stages/stage_finalize_run.py` — finalization

Registers every artifact in `run_memory.db`. If this stage fails after
artifacts are written, runs row stays `STARTED`; orchestrator detects
this and calls `finalize_run_failure`. Don't replace the registration
loop without preserving the rollback path.

### `src/team_version_builder.py` — team export builder

Surgical patch of OGF using GF_V0_CLEAN as truth. Preserves OGF formatting
(date formats, conditional fills, frozen panes). The team file is the
deliverable. Cosmetic refactors here = direct user-visible regressions.

### `app.py:export_team_version()` — UI hook for team export

Atomic-rename pattern (temp file → `unlink dest if exists` → `rename`).
Don't replace with `shutil.copy` over an in-use file.

---

## B. Production UI

### `ui/jansa-connected.html`

The only production UI entrypoint. `app._resolve_ui()` raises
`FileNotFoundError` if it's missing. Babel and React are loaded from CDN
at boot — no build step.

### `ui/jansa/*.jsx` and `ui/jansa/*.js`

The component library. Specifically:
- `shell.jsx` — App root, routing, focus toggle, theme toggle, DCC panel mount.
- `data_bridge.js` — `window.OVERVIEW / CONSULTANTS / CONTRACTORS / FICHE_DATA`
  contract + DCC bridge methods (`searchDocuments`,
  `loadDocumentCommandCenter`). Backend response shapes are coupled to it.
- `tokens.js` — `window.JANSA_FONTS`, `window.applyJansaTheme`. Required by
  every other component.
- `overview.jsx`, `consultants.jsx`, `fiche_base.jsx`, `fiche_page.jsx`,
  `runs.jsx`, `executer.jsx` — visual components.
- `document_panel.jsx` — Document Command Center drawer. Pure rendering
  of `Api.get_document_command_center` payload. Backend
  (`src/reporting/document_command_center.py`) is the source of truth
  for tag computation, response grouping, etc. Don't move logic into
  this JSX.

A change in any of these probably forces a backend shape change. Touch
both sides together.

### `src/reporting/document_command_center.py` (DCC backend builder)

Sole source of business logic for the panel:
- 7 primary tags + 6 secondary tags computation
- Search ranking
- Response/comment/revision-history composition

Constants in this file (`ENTREPRISE_DELAY_THRESHOLD_DAYS=15`,
`TRES_ANCIEN_THRESHOLD_DAYS=60`, etc.) have direct user-visible meaning.
See `context/06_EXCEPTIONS_AND_MAPPINGS.md` § I.3 before touching.

### `src/reporting/contractor_quality.py` — Phase 7 backend module

Business logic includes the BENTIN_OLD legacy filter, the dormant-time extension on `_contractor_delay_for_chain`, and the strip-dormant patch on `_long_chains` share (Phase 0 D-004). Read-only; modify only via a new phase plan.

### `src/reporting/chain_timeline_attribution.py` (DCC chain-time layer)

Reads `output/chain_onion/CHAIN_*.csv` + RunContext, applies the 10-day
secondary-cap correction (Phase 1 verified chain_onion does not enforce
it), produces per-chain timelines with per-segment attribution. Output
artifact `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.{json,csv}`
is consumed by `Api.get_chain_timeline` and the panel's Chronologie
section. Auto-refreshed at app startup by `_ensure_chain_data_fresh`
(in `app.py`).

---

## C. Persistent state

### `data/run_memory.db`

Currently holds run 0 only. **Do not** delete or recreate without an
explicit task; `bootstrap_run_zero.py` exists for that. Deleting it
invalidates every cross-run claim in the UI.

### `data/report_memory.db`

Holds the persisted consultant truth. Deleting it loses all the report
memory accumulated outside the GED. `bootstrap_report_memory.py` exists
for re-bootstrapping but starts from empty.

### `runs/run_0000/`

Immutable baseline. `nuke_and_rebuild_run0.py` and `reset_to_clean_run0.py`
are the only scripts allowed to mutate it. Manual editing breaks sha256
verification on the next run.

---

## D. Pipeline orchestration

### `src/run_orchestrator.py`

The main_module mutation contract is fragile by design. `_patched_main_context`
mutates `main.GED_FILE`, `main.GF_FILE`, `main.CONSULTANT_REPORTS_ROOT`, etc.
on the calling main module's namespace. The runner reads from that
namespace. The contextmanager restores values in `finally`. Don't replace
this with a configuration object — the indirection is what allows
multiple callers (UI, headless main, tests) to share the same pipeline
without copying paths everywhere.

### `src/pipeline/runner.py:_run_pipeline_impl`

Reads paths from `ns = sys.modules["main"]`, NOT from `pipeline.paths`.
This is intentional. Don't switch to direct imports.

### `src/pipeline/paths.py`

Single source of truth for default paths. Do NOT make any of these names
relative or compute them from CWD; everything here resolves relative to
`main.py`'s directory.

### `main.py`

Top-level globals (`_ACTIVE_RUN_NUMBER`, `_ACTIVE_RUN_FINALIZED`,
`_RUN_CONTROL_CONTEXT`) are MUTABLE and are written from
`run_orchestrator` and `pipeline.runner`. Every line here exists for a
reason; the file is intentionally tiny.

---

## E. Chain + Onion

### `src/chain_onion/source_loader.py`

Step 04 source loader; documents the identity model and exception logic
expectations. The `doc_id` UUID is session-scoped and must NOT be persisted
to chain output CSVs (line 32 of file docstring).

### `src/chain_onion/exporter.py`

Owns the contract for the 7 CSVs + XLSX + 2 JSONs. UI's chain_onion
narrowing depends on `ONION_SCORES.csv` shape (`family_key`,
`portfolio_bucket`, etc.).

---

## F. Hardcoded business knowledge — read carefully before modifying

These are NOT off-limits, but every value below has a direct user-visible
or contractual meaning. Changing them changes operational behavior.

- `src/config_loader.py:EXCLUDED_SHEETS` — sheets removed from clean GF.
- `src/config_loader.py:SHEET_YEAR_FILTERS` — pre-2026 BENTIN/LGD exclusion.
- `src/config_loader.py:SHEET_EMETTEUR_FILTER` — routing emetteur whitelist
  per sheet.
- `src/flat_ged/input/source_main/consultant_mapping.py` —
  RAW_TO_CANONICAL, EXCEPTION_COLUMNS, CANONICAL_TO_DISPLAY, SPECIAL_CASES.
- `src/flat_ged/input/source_main/status_mapping.py` —
  VALID_STATUSES, BUREAU_CONTROLE_STATUSES, PENDING_KEYWORDS,
  DEADLINE_DATE_PATTERN.
- `src/flat_ged/input/source_main/ged_parser_contract.py` — header layout,
  CORE_COLUMNS, APPROVER_SUB_FIELDS.
- `src/reporting/focus_ownership.py` — PRIMARY/SECONDARY/MOEX classification,
  TERMINAL_VISA, SECONDARY_WINDOW_DAYS=10.
- `src/reporting/consultant_fiche.py:CONSULTANT_DISPLAY_NAMES`,
  `STATUS_LABELS_BY_CANONICAL`, `BET_MERGE_KEYS`, `COMPANY_TO_CANONICAL`,
  `CONTRACTOR_REFERENCE`.
- `src/pipeline/stages/stage_discrepancy.py:Part H-1` — BENTIN_LEGACY_EXCEPTION
  pass.
- `src/pipeline/stages/stage_report_memory.py:_ELIGIBLE_CONFIDENCE_VALUES`.

---

## G. Do not delete (cleanup candidates that LOOK orphaned but aren't yet)

- `src/normalize.py:_GED_APPROVER_MAPPING` — historical version of the
  consultant mapping. Was extracted to
  `flat_ged/input/source_main/consultant_mapping.py`. May still be
  referenced by old code paths; verify before removing.
- `src/reporting/bet_report_merger.py` — README and `data_loader.py`
  comment say it is RETIRED, but the file is still on disk. Confirm no
  imports remain (a recent grep finds the import line commented out).
  Archive, don't delete.
- `Mapping.xlsx` — present in `input/`. Not consumed at runtime today.
  Don't delete; the file may still be the source for hardcoded values
  that get refreshed periodically.

---

## H. Worktree under `.claude/worktrees/`

`.claude/worktrees/interesting-hopper-ee96ab/` holds a parallel checkout
created by Claude's worktree tooling. It is a sibling tree, not active
runtime. Don't edit; let the tool manage it.
