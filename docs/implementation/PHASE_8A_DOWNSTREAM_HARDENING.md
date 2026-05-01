# CLOSED FOR CURRENT RELEASE — Phase 8A Downstream Hardening

**Status: CLOSED for current release (2026-05-01).**

8A.6 proved no UI-visible mismatch:
`UI_PAYLOAD_FULL: surfaces=6 compared=45 matches=45 mismatches=0`.
Classification: NM=0, SF=0, ESD=0, TB=0. Decision (8A.7): KEEP ARCHITECTURE.
No UI snapshot layer needed. Phase 8C UI snapshot phase NOT opened.

LOW-risk audit steps closed: 8A.1, 8A.3, 8A.5, 8A.6, 8A.7.

MEDIUM-risk hardening steps deferred (not release blockers):
- **8A.2** (D-010 broad patch) — `disagreements_total=0` per 8A.1.
- **8A.2b** (consultant_fiche.py / contractor_fiche.py direct visa calls).
- **8A.4** (Chain+Onion BLOCK-mode flip) — WARN-only is operational.

See `context/07_OPEN_ITEMS.md` "Phase 8 family — closed for current release"
section for the full deferred backlog. Read-only reference. Do not continue
implementation in this file without explicit reopening.

---

# Phase 8A — Downstream Hardening

> **Original status (charter dated 2026-04-30) — superseded by closure banner above.**
>
> Plan doc only. No step has shipped. Risk ranges LOW (audits, documentation) to MEDIUM (D-010 patch, BLOCK-mode flip). Production source under `src/reporting/data_loader.py` and `src/chain_onion/source_loader.py` are touched in 8A.2 and 8A.4 respectively, with explicit per-step approval.

This MD is **self-contained**. An agent or engineer assigned only this phase can execute it cold without reading any other file in `docs/implementation/`. Each numbered step below is also self-contained — it states its objective, files to read, files to modify, validation, and risk in isolation.

Phase 8 (Count Lineage Fix, closed 2026-04-30) shipped the audit harness and the load-bearing aggregator / cache fixes. Phase 8A closes the remaining downstream gaps that Phase 8 deliberately deferred: D-010 (parallel `compute_visa_global_with_date` call site), the WARN→BLOCK flip on Chain+Onion source alignment, and a widened UI payload audit beyond Overview. See `docs/implementation/PHASE_8_COUNT_LINEAGE_FIX.md` (closed; reference only).

Phase 8A is the sibling of Phase 8B. Phase 8A operates **downstream** of FLAT_GED.xlsx; Phase 8B operates **upstream** (RAW → FLAT). The two phases do not depend on each other and can run in parallel if desired.

---

## 1. Mission

**One-line:** Phase 8A makes sure every downstream consumer after FLAT_GED uses the same verified truth, and surfaces any divergence as a recordable named gap rather than a silent UI artifact.

**Paragraph:** Phase 8 proved that `aggregator.py` resolves `visa_global` via the Phase-8 `resolve_visa_global` helper at 5 sites. It also proved that the audit one-liner stays at `PASS=16 WARN=0 FAIL=1` and that `UI_PAYLOAD: compared=10 matches=10 mismatches=0` for the Overview surface. What Phase 8 did NOT do: route `_precompute_focus_columns` (in `data_loader.py`) through the same resolver, flip the Chain+Onion source alignment from WARN-only to enforcement on real content mismatches, or extend the UI payload audit beyond Overview. Phase 8A closes those three gaps, plus produces a UI metric inventory so future audits know exactly which numbers to compare.

---

## 2. Hard Constraints

- App must keep starting and serving across every step.
- 8A.1, 8A.3, 8A.5 are read-only audits / documentation. No production source touched.
- 8A.2 (D-010 patch) and 8A.4 (BLOCK-mode flip) are MEDIUM-risk and require their own per-step approval before code lands.
- 8A.6 is audit-only first; production code is touched only if a true bug surfaces.
- 8A.7 is decision-only; opens a new phase (8C) if approved.
- No pipeline rerun in Cowork unless explicitly authorised.
- Phase 8A is **strictly downstream of FLAT_GED.xlsx**. RAW → FLAT differences belong to Phase 8B.

---

## 3. Risk Summary

| Step | Risk | Why |
|------|------|-----|
| 8A.1 D-010 focus-visa source audit | Low | Read-only. New script under `scripts/`. |
| 8A.2 D-010 implementation patch | **Medium** | Touches `src/reporting/data_loader.py` (`_precompute_focus_columns`) and creates a new `src/reporting/visa_resolver.py` module. Must not regress focus ownership counts. |
| 8A.3 Chain+Onion BLOCK-readiness audit | Low | Read-only check of `chain_onion_source_check.json`. |
| 8A.4 Chain+Onion BLOCK-mode flip | **Medium** | Can stop Chain+Onion if alignment fails. Owner-approved policy: BLOCK only on `WARN_PATH_AND_CONTENT_MISMATCH` or `UNDETERMINED`. |
| 8A.5 UI metric inventory | Low | Documentation only. New `context/12_UI_METRIC_INVENTORY.md`. |
| 8A.6 Widen UI payload audit | Low (audit-only) → Medium (if a true bug is found and a `ui_adapter.py` fix is approved) | Extends Phase 8 step 6 from Overview-only to all major UI surfaces. |
| 8A.7 UI snapshot decision | Low | Decision only; no code in 8A. |

Steps 8A.1, 8A.3, 8A.5, 8A.7 are LOW. Steps 8A.2 and 8A.4 are MEDIUM and require explicit re-approval before their code patches land. Step 8A.6 is LOW for the audit; promotes to MEDIUM only if a real mismatch needs a `ui_adapter.py` patch.

---

## 4. Standard Rules (embedded — do not skip)

### Tooling

Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) for inspecting Windows-mounted source files (H-1 / H-1.1 — `context/11_TOOLING_HAZARDS.md`). Bash IS fine for executing scripts (`python scripts/...`, `python -m py_compile`, `python scripts/audit_counts_lineage.py`).

For pytest: H-4 still applies. Tests that import the reporting chain may hang in sandbox. Mock-only tests run fine. Plan to confirm test passes via Windows shell at each step.

For bulk xlsx I/O: H-5 still applies. Step 8A.6's widened audit might need a Windows-shell run for full-surface validation if it pulls additional aggregator outputs that trigger heavy reads.

### Priorities

1. App must always run.
2. Phase 8 audit one-liner stays at `PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX` AND `UI_PAYLOAD: compared=10 matches=10 mismatches=0` throughout. Any step that breaks either contract STOPS and reports.
3. No silent renames. No silent contract changes. No row drops.
4. Every patch is the smallest patch that closes the gap.
5. If the audit shows a divergence is **expected** (semantic, not a bug), record it — do NOT patch code to "fix" it.

### Forbidden moves during Phase 8A

- Do NOT modify `src/flat_ged/*`, `src/workflow_engine.py`, `src/effective_responses.py`, `src/run_memory.py`, `src/report_memory.py`, `src/team_version_builder.py`, `src/pipeline/*`, `data/*.db`, `runs/*`, `ui/jansa/*`, `ui/jansa-connected.html`, `app.py`, `main.py`, `run_chain_onion.py` *except where a step explicitly authorises it* (8A.2 → `data_loader.py`; 8A.4 → `chain_onion/source_loader.py`).
- Do NOT touch the production FLAT artifact (`output/intermediate/FLAT_GED.xlsx`) or the cache (`output/intermediate/FLAT_GED_cache_*`).
- Do NOT change column names anywhere in the pipeline.
- Do NOT introduce new frameworks, dependencies, or storage layers.
- Do NOT rewrite working logic for style.

### Trust-but-verify (carried forward from Phase 8)

Across Phase 8, three Claude Code execution reports carried inaccuracies that mattered:
1. Step 3 vdate regression — `(visa, None)` silently broke `avg_days_to_visa`.
2. Step 4 — claimed `CACHE_SCHEMA_VERSION = "v2"` and `§22 appended`; neither was true on disk.
3. Step 5 — minor schema deviation (`checked_at` vs prompt's `generated_at`).

The pattern that catches these reliably: **after any Claude Code-generated step, read the actual file via the Read tool** before propagating into context. Spot-check version constants, section headers, key names, line counts. Bash grep / wc on the cross-mount lies (H-1) — the Read tool does not.

For any execution report claiming "§N appended" or "FOO = bar bumped", do a one-second Read to verify before flipping status to ✅. Treat sandbox pytest hangs as inconclusive (H-4), not failures. Confirm via direct `python -c` invocation, then defer pytest to Windows shell.

---

## 5. Scope

### In scope

- D-010: `_precompute_focus_columns` still uses `WorkflowEngine.compute_visa_global_with_date` directly (Phase 8 §7.5 deferred; it lives in `data_loader.py`, not `aggregator.py`).
- Phase 8 Step 5 BLOCK-mode flip: WARN-only landed in §23. Flip to BLOCK on real content mismatches.
- Phase 8 Step 6 widened UI coverage: extend beyond Overview to consultants list, contractors list, fiches, document command center, chain/onion panel.
- UI metric inventory documentation.
- Optional: UI snapshot layer decision (8A.7).

### Out of scope (Phase 8B's territory)

- RAW GED → FLAT GED reconciliation.
- D-011 SAS REF projection (RAW 836 → FLAT 284).
- Any `src/flat_ged/*` change.
- Report integration into FLAT GED.

---

## 6. Layer Map (downstream of FLAT_GED.xlsx)

```
L1_FLAT_GED_XLSX        output/intermediate/FLAT_GED.xlsx                      (Phase 8A treats as accepted truth)
L2_STAGE_READ_FLAT      src/pipeline/stages/stage_read_flat.py                 (untouched)
L3_RUNCONTEXT_CACHE     output/intermediate/FLAT_GED_cache_*                   (untouched)
L3.5_FOCUS              src/reporting/focus_filter.py + focus_ownership.py     (referenced by 8A.1)
L3.6_FOCUS_PRECOMPUTE   data_loader._precompute_focus_columns                  (8A.2 patches the visa source here)
L4_AGGREGATOR           src/reporting/aggregator.py                            (untouched after Phase 8)
L5_UI_ADAPTER           src/reporting/ui_adapter.py                            (referenced by 8A.6; possibly patched if mismatch)
L6_CHAIN_ONION          src/chain_onion/*                                      (8A.4 patches source_loader.py for BLOCK)
UI                      ui/jansa/*                                             (referenced by 8A.5; never touched)
```

---

## 7. Step 8A.1 — D-010 Focus-Visa Source Audit (LOW risk)

### 7.1 Goal

Find and prove every remaining direct `compute_visa_global_with_date(...)` call that bypasses the Phase-8 `resolve_visa_global` helper. Known suspect: `_precompute_focus_columns` in `data_loader.py`. There may be others.

### 7.2 Files

```
READ:
  src/reporting/data_loader.py
  src/reporting/aggregator.py
  src/reporting/focus_filter.py
  src/reporting/focus_ownership.py
  src/workflow_engine.py            (READ ONLY — for compute_visa_global_with_date signature)
  scripts/audit_counts_lineage.py   (READ ONLY — for the existing pattern)

CREATE:
  scripts/audit_focus_visa_source.py
  output/debug/focus_visa_source_audit.json
  output/debug/focus_visa_source_audit.xlsx
```

### 7.3 What the script must do

1. AST-walk `src/reporting/*.py` (and any other reachable file under `src/reporting/`) for every call site of `compute_visa_global_with_date`.
2. For each call site, record:
   - `function_name`
   - `file_path`
   - `line_number`
   - `uses_workflow_engine_directly` (bool — True if `we.compute_visa_global_with_date` or `ctx.workflow_engine.compute_visa_global_with_date`)
   - `uses_flat_doc_meta` (bool — True if the surrounding code reads `ctx.flat_ged_doc_meta` first)
   - `uses_resolve_visa_global_equivalent` (bool — True if the call is wrapped by `resolve_visa_global` or the new `visa_resolver.resolve_visa_global`)
   - `affected_output_columns` (list — what dataframe columns or RunContext attributes does this call ultimately populate? Inferred from surrounding assignment context)
   - `count_of_docs_checked` (int — for live runs only; how many docs hit this call site in run 0)
   - `count_of_disagreements` (int — for each doc, does meta-visa equal engine-visa? Count rows where they differ)
3. Write `output/debug/focus_visa_source_audit.json` with the catalogue.
4. Write `output/debug/focus_visa_source_audit.xlsx` with one sheet listing every call site.
5. Print stdout summary:
   ```
   FOCUS_VISA_AUDIT: call_sites=<n> direct_engine=<n> via_resolver=<n> disagreements_total=<n>
   ```

### 7.4 Validation

```
python -m py_compile scripts/audit_focus_visa_source.py
python scripts/audit_focus_visa_source.py
# Expect: at least 1 direct_engine entry (the known _precompute_focus_columns site).
# count_of_disagreements should be measured against current run 0; expect 0 or small (Phase 8 verified flat_doc_meta and engine agreed on visa for every doc in run 0).
```

### 7.5 Risk: **Low**.

---

## 8. Step 8A.2 — D-010 Implementation Patch (MEDIUM risk — STOP for approval)

### 8.1 Pre-flight finding (locked design choice)

`aggregator.py` already imports `from .data_loader import RunContext` (line 13). `data_loader.py` does NOT import from `aggregator.py`. Routing `_precompute_focus_columns` through `aggregator.resolve_visa_global` would create a circular import (`data_loader → aggregator → data_loader`) and break app startup.

**Design choice (locked):** create a new shared module `src/reporting/visa_resolver.py` and route both `aggregator.py` and `data_loader.py` through it.

### 8.2 Files

```
READ:
  src/reporting/data_loader.py
  src/reporting/aggregator.py
  src/reporting/focus_ownership.py
  src/workflow_engine.py            (READ ONLY)

CREATE:
  src/reporting/visa_resolver.py    (NEW — minimal shared helper)
  tests/test_visa_resolver.py       (NEW — same shape as the old test_resolve_visa_global.py)

MODIFY:
  src/reporting/aggregator.py       (replace inline resolve_visa_global with `from .visa_resolver import resolve_visa_global`)
  src/reporting/data_loader.py      (route _precompute_focus_columns through `resolve_visa_global` from visa_resolver)
  tests/test_resolve_visa_global.py (update import path; rename if convenient OR keep as backward-compat alias)

DO NOT TOUCH:
  src/workflow_engine.py
  src/flat_ged/*
  src/effective_responses.py
  ui/jansa/*
  data/*.db
  runs/*
```

### 8.3 The patch shape

#### 8.3.1 New file `src/reporting/visa_resolver.py`

```python
"""Tiny shared helper. Phase 8A.2 (2026-04-30).

Both src/reporting/aggregator.py and src/reporting/data_loader.py
need to resolve visa_global the same way: prefer
ctx.flat_ged_doc_meta[doc_id]["visa_global"] (authoritative per
FLAT_GED_CONTRACT) and fall back to
WorkflowEngine.compute_visa_global_with_date(doc_id) for the date
because flat_doc_meta does not carry visa_global_date today.

This helper lives in its own module to avoid the circular-import
risk that would arise if data_loader imported from aggregator.
"""


def resolve_visa_global(ctx, doc_id):
    """See module docstring. Returns (visa, vdate) tuple."""
    meta = getattr(ctx, "flat_ged_doc_meta", None) or {}
    entry = meta.get(doc_id)
    if entry:
        visa = entry.get("visa_global")
        if visa:
            _, vdate = ctx.workflow_engine.compute_visa_global_with_date(doc_id)
            return visa, vdate
    return ctx.workflow_engine.compute_visa_global_with_date(doc_id)
```

#### 8.3.2 In `src/reporting/aggregator.py`

Replace the inline `def resolve_visa_global(ctx, doc_id): ...` (lines 33–50 today) with:

```python
from .visa_resolver import resolve_visa_global   # noqa: F401  (re-exported for callers)
```

Keep the existing 5 call sites (`compute_project_kpis`, `compute_monthly_timeseries`, `compute_weekly_timeseries`, `compute_consultant_summary`, `compute_contractor_summary`) untouched — they already call `resolve_visa_global(ctx, did)` and the import keeps the name in scope.

#### 8.3.3 In `src/reporting/data_loader.py` — `_precompute_focus_columns`

Read the function first; identify the `we.compute_visa_global_with_date(doc_id)` (or equivalent) call site. Replace it with:

```python
from .visa_resolver import resolve_visa_global
visa, vdate = resolve_visa_global(ctx, doc_id)
```

(Place the import at module top, not inside the function — the existing import block in `data_loader.py` already contains other reporting-internal imports.)

Verify `_precompute_focus_columns` actually has access to `ctx` (i.e. `RunContext`) at the call site. The function signature today takes `ctx` per Phase 0 D-010 in `07_OPEN_ITEMS.md` — verify by reading.

#### 8.3.4 Update `tests/test_resolve_visa_global.py`

Change the import line from `from reporting.aggregator import resolve_visa_global` to `from reporting.visa_resolver import resolve_visa_global`. Either rename the file to `test_visa_resolver.py` or leave the filename and update only the import path; either is acceptable. Tests themselves should not change — the behaviour of `resolve_visa_global` is identical.

### 8.4 Validation

```
python -m py_compile src/reporting/visa_resolver.py
python -m py_compile src/reporting/aggregator.py src/reporting/data_loader.py
python -m py_compile app.py main.py run_chain_onion.py

# Phase 8 audit must remain unchanged
python scripts/audit_counts_lineage.py
# Expected:
#   AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
#   UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match

# 8A.1 audit should now show ZERO direct_engine entries
python scripts/audit_focus_visa_source.py
# Expected: FOCUS_VISA_AUDIT: call_sites=<n> direct_engine=0 via_resolver=<n>

# Pytest (H-4 may bite in sandbox; Windows shell is authoritative)
timeout 30 python -m pytest tests/test_resolve_visa_global.py tests/test_visa_resolver.py -q

# App smoke
timeout 15 python -c "import app"
```

### 8.5 Acceptance

- D-010 closed: zero direct `compute_visa_global_with_date` call sites remain in `src/reporting/`.
- Phase 8 audit one-liner unchanged.
- Phase 8 UI_PAYLOAD line unchanged.
- Focus ownership counts (`Focus ownership computed: CLOSED=…, CONTRACTOR=…, MOEX=…, PRIMARY=…, SECONDARY=…`) are byte-identical to before the patch (Phase 8 closure observed `CLOSED=791, CONTRACTOR=320, MOEX=2647, PRIMARY=987, SECONDARY=89` — that's the comparison baseline).
- App imports cleanly.

### 8.6 Rollback

Revert the three modified files. The new `visa_resolver.py` becomes orphaned but harmless; delete it as part of the rollback.

### 8.7 Risk: **Medium**. STOP and wait for approval before editing.

---

## 9. Step 8A.3 — Chain+Onion BLOCK-Mode Readiness Audit (LOW risk)

### 9.1 Goal

Before flipping WARN to BLOCK in 8A.4, prove the alignment check has been clean across at least one full pipeline cycle that exercised registry writes. Phase 8 §23 verified the WARN check ran clean once (`result=OK`); this step confirms it stays clean across a real cycle.

### 9.2 Files

```
READ:
  output/debug/chain_onion_source_check.json    (latest)
  data/run_memory.db                            (READ ONLY — confirm at least one new completed run exists since the WARN check was added)

CREATE:
  scripts/check_chain_onion_alignment_block_ready.py
  output/debug/chain_onion_block_readiness.json

DO NOT TOUCH:
  src/chain_onion/source_loader.py              (no code change yet — that is 8A.4)
```

### 9.3 What the script must do

1. Load the latest `output/debug/chain_onion_source_check.json`.
2. Verify:
   - File exists and was produced by the helper added in Phase 8 §23.
   - `result` is one of `OK` or `WARN_MTIME_ADVISORY` (not `WARN_*_MISMATCH` or `UNDETERMINED`).
   - `registered_flat_ged_path` is non-null.
   - `using_flat_ged_path` is non-null.
   - `sha_match` is `true` or `null` (null is acceptable when paths are identical — sha is not computed).
3. Verify a fresh pipeline run + Chain+Onion run has happened since the WARN check landed:
   - Read `data/run_memory.db` (read-only via `sqlite3` `mode=ro`).
   - Confirm at least one run with `completed_at` more recent than the helper's first invocation.
   - Confirm the latest registered `FLAT_GED` artifact's mtime is > the helper's first invocation timestamp.
4. Write `output/debug/chain_onion_block_readiness.json`:
   ```json
   {
     "checked_at": "<iso>",
     "block_mode_ready": true | false,
     "reason": "<one-line explanation>",
     "latest_check_result": "<OK|WARN_*|UNDETERMINED>",
     "latest_run_completed_at": "<iso or null>",
     "latest_flat_ged_mtime": <float>,
     "helper_first_seen_at": "<iso or null>"
   }
   ```
5. Print stdout summary:
   ```
   BLOCK_READINESS: ready=<true|false> reason=<...>
   ```

### 9.4 Validation

```
python -m py_compile scripts/check_chain_onion_alignment_block_ready.py
python scripts/check_chain_onion_alignment_block_ready.py
# Expected (best case): BLOCK_READINESS: ready=true reason=clean across <n> runs
# Expected (worst case): BLOCK_READINESS: ready=false reason=<actionable>
```

### 9.5 Acceptance

- `block_mode_ready` is true OR `block_mode_ready` is false with a documented reason.
- No production code changed.

### 9.6 Risk: **Low**.

---

## 10. Step 8A.4 — Chain+Onion BLOCK-Mode Flip (MEDIUM risk — STOP for approval)

### 10.1 Goal

Promote the alignment check from WARN-only to enforcement, but only on real content mismatches.

### 10.2 The policy (locked from charter)

```
result = OK                                   → proceed (no block, no warning)
result = WARN_MTIME_ADVISORY                  → proceed (log warning only)
result = WARN_PATH_MISMATCH_SAME_CONTENT      → proceed with warning
                                                (paths differ, content identical;
                                                 not a real misalignment)
result = WARN_PATH_AND_CONTENT_MISMATCH       → BLOCK  (real misalignment;
                                                Chain+Onion exits non-zero)
result = UNDETERMINED                         → BLOCK  (cannot verify;
                                                fail closed, not open)
```

The blocking policy is intentionally conservative: only on confirmed content divergence or undeterminable state. Path mismatches with matching sha proceed because they reflect path-resolution variance (e.g. different absolute path roots) rather than actual data drift.

### 10.3 Files

```
READ:
  src/chain_onion/source_loader.py    (find _check_flat_ged_alignment from Phase 8 §23, line ~199)
  output/debug/chain_onion_block_readiness.json  (from 8A.3 — must say ready=true)

MODIFY:
  src/chain_onion/source_loader.py    (extend _check_flat_ged_alignment to raise on the two BLOCK results)

CREATE / EXTEND:
  tests/test_chain_onion_block_mode.py   (NEW — assert the four result-to-action rules above)

DO NOT TOUCH everything else (same do-not-touch list as 8A.2).
```

### 10.4 The patch shape

The Phase 8 §23 helper currently writes receipts and returns `None` regardless of result. The 8A.4 patch wraps the receipts-write in a final block:

```python
# After receipts are written and the INFO log line is emitted:
if receipts["result"] in ("WARN_PATH_AND_CONTENT_MISMATCH", "UNDETERMINED"):
    raise RuntimeError(
        f"[CHAIN_ONION_SOURCE_CHECK] BLOCK: result={receipts['result']} "
        f"reason={receipts.get('reason')}. "
        "FLAT_GED path/content does not align with the latest registered "
        "FLAT_GED artifact. Re-run the pipeline (`python main.py`) to "
        "regenerate the registered artifact, or investigate the divergence."
    )
```

The existing try/except wrap in the helper's caller does NOT swallow this exception — the patch deliberately propagates the BLOCK to Chain+Onion, which exits non-zero. Verify by reading the call site.

### 10.5 Validation

```
python -m py_compile src/chain_onion/source_loader.py
python -m py_compile run_chain_onion.py app.py main.py

# Real-cycle smoke (Windows shell preferred per H-5)
python run_chain_onion.py
# Expected exit 0; receipts file shows result=OK; no BLOCK fires.

# Phase 8 audit
python scripts/audit_counts_lineage.py
# Expected: PASS=16 WARN=0 FAIL=1 (unchanged)

# Pytest (H-4 may bite; mock-based tests should still run)
timeout 30 python -m pytest tests/test_chain_onion_block_mode.py tests/test_chain_onion_source_check.py -q
```

### 10.6 Acceptance

- Chain+Onion exits 0 on `result=OK` (the only case observed in production today).
- Helper raises on `WARN_PATH_AND_CONTENT_MISMATCH` and `UNDETERMINED`.
- Helper does NOT raise on `OK`, `WARN_MTIME_ADVISORY`, or `WARN_PATH_MISMATCH_SAME_CONTENT`.
- Phase 8 audit one-liner unchanged.
- Tests cover all four result classes.

### 10.7 Rollback

Revert `src/chain_onion/source_loader.py` to its post-Phase-8-§23 state. The receipts file is unaffected.

### 10.8 Risk: **Medium**. STOP for approval before editing.

---

## 11. Step 8A.5 — Full UI Metric Inventory (LOW risk; documentation only)

### 11.1 Goal

Document every UI number and its backend source. This is the canonical reference future audits will key off.

### 11.2 Files

```
READ:
  ui/jansa/overview.jsx
  ui/jansa/consultants.jsx
  ui/jansa/contractors.jsx
  ui/jansa/consultant_fiche.jsx           (or whichever fiche entry exists)
  ui/jansa/contractor_fiche_page.jsx
  ui/jansa/dcc.jsx                         (Document Command Center; verify name)
  ui/jansa/data_bridge.js
  ui/jansa-connected.html
  app.py                                   (the API methods exposed via pywebview)
  src/reporting/ui_adapter.py
  src/reporting/aggregator.py
  src/reporting/contractor_quality.py
  src/reporting/contractor_fiche.py
  src/reporting/consultant_fiche.py
  src/reporting/document_command_center.py

CREATE:
  context/12_UI_METRIC_INVENTORY.md
```

### 11.3 What the inventory must contain

For every UI element that displays a number, percentage, or count:

```
| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
```

Pages to cover:
- Overview
- Consultants tab
- Contractors tab
- Consultant fiche
- Contractor fiche
- Document Command Center
- Chain+Onion panel
- Runs page
- Export panel

For each row:
- `page` — UI page or section name.
- `component` — JSX component (e.g. `MoexCard`, `ConsultantCard`).
- `label` — visible UI text (e.g. "À traiter", "Total docs").
- `js_field` — the JS property the component reads (e.g. `c.focus_owned`).
- `api_method` — the `app.Api.*` method that supplies it (e.g. `app.Api.get_overview_for_ui`).
- `py_function` — the Python function that ultimately produces the value (e.g. `aggregator.compute_consultant_summary`).
- `source_dataframe` — what dataframe / artifact the value comes from (e.g. `ctx.dernier_df`, `ctx.workflow_engine.responses_df`, `output/chain_onion/top_issues.json`).
- `semantic_definition` — one sentence describing what the number means.
- `audit_coverage` — Yes / No / Partial (does the existing `audit_counts_lineage.py` check it?).
- `audit_gap` — if not fully covered, what's missing.

### 11.4 Validation

Manual review of `context/12_UI_METRIC_INVENTORY.md` for completeness. The inventory is the input to 8A.6.

### 11.5 Acceptance

- Every displayed number on the listed pages has a row in the inventory.
- Every row names a backend source.
- Rows with `audit_coverage=No` or `Partial` are explicitly listed for 8A.6 to address.

### 11.6 Risk: **Low**.

---

## 12. Step 8A.6 — Widen UI Payload Audit Beyond Overview (LOW risk audit; MEDIUM if patch needed)

### 12.1 Goal

Phase 8 §24 compared `compute_project_kpis` vs `adapt_overview` field-by-field (10 fields, 0 mismatches). 8A.6 extends that to every UI surface listed in the 8A.5 inventory.

### 12.2 Files

```
READ:
  context/12_UI_METRIC_INVENTORY.md          (from 8A.5)
  scripts/audit_counts_lineage.py            (Phase 8 step 6 wiring)
  src/reporting/ui_adapter.py
  src/reporting/aggregator.py
  src/reporting/contractor_quality.py
  src/reporting/contractor_fiche.py
  src/reporting/consultant_fiche.py
  src/reporting/document_command_center.py

CREATE:
  scripts/audit_ui_payload_full_surface.py
  tests/test_ui_payload_full_surface.py
  output/debug/ui_payload_full_surface_audit.xlsx
  output/debug/ui_payload_full_surface_audit.json

MODIFY (optional):
  scripts/audit_counts_lineage.py            (only if extending the existing UI_PAYLOAD_FIELD_MAP is cleaner than a new script; verify before deciding)
```

### 12.3 What the new script must do

1. For each UI surface in the inventory, build a per-surface field-mapping table (same shape as Phase 8 §24's `UI_PAYLOAD_FIELD_MAP`).
2. Invoke each adapter function once:
   - `adapt_overview(ctx, focus_result, …)`
   - `adapt_consultants(ctx, …)`
   - `adapt_contractors_list(ctx, …)`
   - `adapt_contractors_lookup(ctx, …)`
   - any fiche / DCC / chain+onion adapter exposed via `app.Api.*`
3. Walk the corresponding aggregator output for each surface.
4. Compare field-by-field with the same `comparison_kind` taxonomy from Phase 8 §24:
   - `identity`, `numeric_equal`, `set_equal`, `dict_equal`, `skipped`.
5. Emit per-surface mismatch sheets in `output/debug/ui_payload_full_surface_audit.xlsx`:
   - `consultants_list_mismatches`
   - `contractors_list_mismatches`
   - `consultant_fiche_mismatches`
   - `contractor_fiche_mismatches`
   - `dcc_mismatches`
   - `chain_onion_panel_mismatches`
   - …
6. Write `output/debug/ui_payload_full_surface_audit.json` with totals per surface and a global `unexplained_mismatches` count.
7. Print stdout summary:
   ```
   UI_PAYLOAD_FULL: surfaces=<n> compared=<n> matches=<n> mismatches=<n>; <verdict>
   ```

### 12.4 Mismatch classification

For each mismatch, classify per the charter:
```
naming_only                 — same number, different key path (fix in ui_adapter.py)
scope_filter                — different filter applied at adapter vs aggregator (fix or document)
expected_semantic_difference — adapter intentionally reshapes (e.g. REF + SAS_REF merge in Overview's visa_flow.ref); document, do not patch
true_bug                    — real divergence in arithmetic; investigate
```

### 12.5 Targets

```
true_bug = 0
naming_only and scope_filter mismatches → enumerate; each becomes a mini-decision (fix-in-ui_adapter or document-as-expected)
expected_semantic_difference → record in the inventory as an annotation
```

### 12.6 Validation

```
python -m py_compile scripts/audit_ui_payload_full_surface.py
python scripts/audit_ui_payload_full_surface.py
# Expected: UI_PAYLOAD_FULL: surfaces=<n> compared=<n> matches=<n> mismatches=<n>; <verdict>
# Phase 8 audit must remain unchanged
python scripts/audit_counts_lineage.py
```

### 12.7 Acceptance

- Every UI surface from 8A.5 has a comparison row count > 0.
- `true_bug = 0`.
- Any `naming_only` / `scope_filter` mismatches are catalogued and either fixed (separate Medium-risk approval) or recorded as expected.
- Phase 8 audit one-liner unchanged.

### 12.8 If a `true_bug` is found

STOP. Do not patch `ui_adapter.py` or `aggregator.py` in 8A.6 directly. The mismatch becomes input to a separate Medium-risk approval — same pattern as Phase 8 step 6's "if mismatch > 0" stop condition.

### 12.9 Risk: **Low** for the audit; **Medium** if a patch is later approved.

---

## 13. Step 8A.7 — UI Snapshot Layer Decision (LOW risk; decision only)

### 13.1 Goal

After 8A.6 lands, decide whether the current `aggregator → ui_adapter` flow is sustainable or whether a single UI snapshot artifact is warranted.

### 13.2 Possible future target

```
RunContext
  → UI_METRICS_SNAPSHOT.json   (single artifact, all UI numbers, frozen per run)
  → UI
```

### 13.3 Decision criteria

- If the 8A.6 widened audit is **stable** (mismatches consistently 0 across runs, naming_only entries documented and rare), keep the current architecture.
- If the 8A.6 widened audit is **brittle** (mismatches keep appearing, the field map needs frequent updates, refactors in `ui_adapter.py` keep diverging), open Phase 8C for the snapshot layer.

"Brittle" needs a concrete threshold. Suggested: if 8A.6 surfaces > 2 `naming_only` mismatches in 3 consecutive runs of `audit_counts_lineage.py`, that counts as brittle.

### 13.4 Files

```
NO files modified in 8A.7.

If decision = open Phase 8C:
  CREATE docs/implementation/PHASE_8C_UI_SNAPSHOT.md  (next-session work, separate scaffolding)
```

### 13.5 Acceptance

A written decision in `context/07_OPEN_ITEMS.md` (Phase 8A section) saying "keep architecture" or "open Phase 8C", with the brittleness signal that triggered the decision.

### 13.6 Risk: **Low**.

---

## 14. What Must Stay Unchanged Across Phase 8A

```
RAW GED parser                      (input/* → src/flat_ged/* — Phase 8B's territory)
FLAT GED builder                    (src/flat_ged/* — never touched in 8A)
report_memory semantics             (src/report_memory.py — never touched)
Clean GF / Team GF generation       (src/team_version_builder.py + writer — never touched)
UI visual design                    (ui/jansa/* — referenced for inventory only)
Run 0 baseline                      (runs/run_0000/ — never touched)
Database schemas                    (data/*.db — read-only)
Phase 8 audit one-liner             (PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX)
Phase 8 UI_PAYLOAD line             (compared=10 matches=10 mismatches=0 — UNTIL 8A.6 extends the surface count, then a new line emerges from the new script)
```

If any step's validation reveals one of the above changing, STOP and report.

---

## 15. Files To Create

```
docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md          (this file — already created)

scripts/audit_focus_visa_source.py                            (8A.1)
scripts/check_chain_onion_alignment_block_ready.py            (8A.3)
scripts/audit_ui_payload_full_surface.py                      (8A.6)

src/reporting/visa_resolver.py                                (8A.2 — NEW)

context/12_UI_METRIC_INVENTORY.md                             (8A.5)

tests/test_visa_resolver.py                                   (8A.2 — same content as test_resolve_visa_global.py with updated import)
tests/test_chain_onion_block_mode.py                          (8A.4)
tests/test_ui_payload_full_surface.py                         (8A.6)

output/debug/focus_visa_source_audit.{json,xlsx}              (8A.1)
output/debug/chain_onion_block_readiness.json                 (8A.3)
output/debug/ui_payload_full_surface_audit.{json,xlsx}        (8A.6)
```

## 16. Files To Modify (per-step approval required)

```
8A.2 (D-010 patch — MEDIUM):
  src/reporting/aggregator.py        (replace inline helper with import from visa_resolver)
  src/reporting/data_loader.py       (route _precompute_focus_columns through visa_resolver)
  tests/test_resolve_visa_global.py  (import path update; possibly rename file)

8A.4 (BLOCK-mode flip — MEDIUM):
  src/chain_onion/source_loader.py   (add raise on WARN_PATH_AND_CONTENT_MISMATCH / UNDETERMINED)

8A.6 (only if true_bug found and approved — MEDIUM, separate approval):
  src/reporting/ui_adapter.py        (rename / reshape fix; one-by-one)
```

## 17. Files NEVER To Touch In This Phase

```
src/flat_ged/*
src/workflow_engine.py
src/effective_responses.py
src/run_memory.py
src/report_memory.py
src/team_version_builder.py
src/pipeline/*
data/*.db                             (READ ONLY)
runs/*
ui/jansa/*                            (READ for inventory; never modified)
ui/jansa-connected.html
app.py                                (READ for inventory; never modified in 8A)
main.py
run_chain_onion.py                    (READ only)
output/intermediate/FLAT_GED*         (production FLAT — never overwritten)
context/*.md OTHER THAN 12_UI_METRIC_INVENTORY.md  (project owner updates other context in chat per protocol)
README.md                             (same — owner updates)
docs/implementation/PHASE_8_COUNT_LINEAGE_FIX.md   (closed; reference only)
docs/implementation/PHASE_8B_*.md     (Phase 8B's territory)
```

---

## 18. Combined Validation Commands

Each step is independently validatable. Listed in execution order.

```
# 8A.1 — focus visa source audit
python -m py_compile scripts/audit_focus_visa_source.py
python scripts/audit_focus_visa_source.py
# Expect: at least 1 direct_engine entry (pre-patch).

# 8A.2 — D-010 patch (after approval)
python -m py_compile src/reporting/visa_resolver.py
python -m py_compile src/reporting/aggregator.py src/reporting/data_loader.py
python -m py_compile app.py main.py run_chain_onion.py
python scripts/audit_focus_visa_source.py
# Expect: direct_engine=0
python scripts/audit_counts_lineage.py
# Expect (unchanged): PASS=16 WARN=0 FAIL=1; UI_PAYLOAD compared=10 matches=10 mismatches=0
timeout 15 python -c "import app"
timeout 30 python -m pytest tests/test_visa_resolver.py -q

# 8A.3 — BLOCK readiness audit
python -m py_compile scripts/check_chain_onion_alignment_block_ready.py
python scripts/check_chain_onion_alignment_block_ready.py
# Expect: BLOCK_READINESS: ready=true reason=...

# 8A.4 — BLOCK flip (after approval and after 8A.3 says ready=true)
python -m py_compile src/chain_onion/source_loader.py run_chain_onion.py
python run_chain_onion.py    # may be slow in sandbox per H-5; Windows shell preferred
# Expect: exit 0; result=OK on receipts.
python scripts/audit_counts_lineage.py
# Expect (unchanged)
timeout 30 python -m pytest tests/test_chain_onion_block_mode.py tests/test_chain_onion_source_check.py -q

# 8A.5 — UI metric inventory (manual)
# Verify context/12_UI_METRIC_INVENTORY.md exists and covers every page in §11.3.

# 8A.6 — widened UI payload audit
python -m py_compile scripts/audit_ui_payload_full_surface.py
python scripts/audit_ui_payload_full_surface.py
# Expect: UI_PAYLOAD_FULL: surfaces=<n> compared=<n> matches=<n> mismatches=<n>; <verdict>
python scripts/audit_counts_lineage.py
# Expect (unchanged): PASS=16 WARN=0 FAIL=1; UI_PAYLOAD compared=10 matches=10 mismatches=0
timeout 30 python -m pytest tests/test_ui_payload_full_surface.py -q

# 8A.7 — decision only; no validation needed.
```

---

## 19. Final Cowork Prompt (for handing this phase to a fresh agent)

```
Objective:
  Harden every downstream consumer after FLAT_GED.xlsx is accepted as
  source of truth. Close D-010 (focus visa source), promote Chain+Onion
  alignment from WARN to BLOCK on real content mismatches, widen the UI
  payload audit beyond Overview, and produce a UI metric inventory.

Plan: docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md (self-contained).

Hard constraints:
  - Phase 8 audit one-liner must remain
    "PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX"
    AND
    "UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match"
    throughout.
  - src/flat_ged/* is forbidden — that's Phase 8B.
  - 8A.2 and 8A.4 are MEDIUM-risk and require per-step approval.
  - Trust-but-verify on every Claude Code report (read the file, check
    constants / headers / key names).

Tasks (one self-contained Claude Code prompt per step):
  8A.1  D-010 focus-visa source audit       (LOW)
  8A.2  D-010 patch via visa_resolver.py    (MEDIUM — STOP for approval)
  8A.3  Chain+Onion BLOCK readiness audit   (LOW)
  8A.4  Chain+Onion BLOCK flip              (MEDIUM — STOP for approval)
  8A.5  UI metric inventory                 (LOW; documentation only)
  8A.6  Widened UI payload audit            (LOW audit; MEDIUM if patch later)
  8A.7  UI snapshot decision                (LOW; decision only)

Acceptance:
  D-010 closed.
  Chain+Onion BLOCK enabled or documented reason to remain WARN.
  UI metric inventory exists.
  UI payload audit covers all major UI surfaces; true_bug = 0.
  Phase 8 audit stable throughout.

Validation per step: see §18 of the plan doc.

Return per step:
  1. Files created (paths + line counts).
  2. Validation results (verbatim).
  3. Stdout summary line(s).
  4. UI_PAYLOAD-style audit lines if applicable.
  5. Proposed §-report content for the project owner to verify before
     context updates.
```

---

## 20. Open Questions

1. **Step 8A.2 design — RESOLVED before plan opened.** Pre-flight inspection 2026-04-30 confirmed `aggregator.py` imports `from .data_loader import RunContext`. A reverse import from `data_loader.py` to `aggregator.py` would create a circular import. **Locked: create `src/reporting/visa_resolver.py` as a tiny shared module; both `aggregator.py` and `data_loader.py` import from it.** No technical-debt path needed.

2. **Step 8A.4 — what happens on `WARN_PATH_MISMATCH_SAME_CONTENT`?** Charter says "proceed with warning, or block depending on owner decision." The plan locks "proceed with warning" because path-only mismatches with identical sha reflect path-resolution variance, not actual data drift. If the project owner prefers BLOCK on this case, the patch in §10.4 is one line different (add the third result string to the raise condition). Default in 8A.4: proceed with warning.

3. **Step 8A.5 — UI surface enumeration completeness.** The charter lists 9 surfaces. If the inventory walk surfaces additional pages (e.g. Settings, Discrepancies, Reports if any of those becomes live during 8A.5), they should be added to the inventory and to 8A.6's audit scope. The author of 8A.5 has discretion to expand the list — but should NOT shrink it.

4. **Step 8A.6 — overlap with `audit_counts_lineage.py`.** The charter says "Create / Modify: scripts/audit_counts_lineage.py + scripts/audit_ui_payload_full_surface.py". The plan defaults to creating a NEW script that runs alongside the Phase 8 audit (not extending the field map in `audit_counts_lineage.py`) to keep concerns separated. If during execution it becomes obviously cleaner to extend the existing field map, that's acceptable — but the AUDIT one-liner MUST keep its byte-identical contract. Add a new line for the full-surface verdict; do not change the existing UI_PAYLOAD line.

5. **Step 8A.7 — brittleness threshold.** §13.3 suggests "> 2 naming_only mismatches in 3 consecutive runs of `audit_counts_lineage.py`" as the trigger. Project owner can refine this when 8A.7 is opened.

6. **Pytest in sandbox.** The Phase 8B doc carries the same warning. All Phase 8A pytest invocations should be expected to need a Windows-shell run for full confirmation. Sandbox can validate compile + small mock-based tests.

7. **Order of operations.** The three sub-tracks (D-010, Chain+Onion BLOCK, UI widening) are roughly independent. Recommended ship order: LOW first (8A.1, 8A.3, 8A.5 in any order), then MEDIUM after their per-step approvals (8A.2, 8A.4, 8A.6), then 8A.7 as a closing decision.
