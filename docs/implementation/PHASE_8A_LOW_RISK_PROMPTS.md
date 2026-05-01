# Phase 8A — Low-Risk Sub-Step Prompts (Claude Code, Windows)

> **Purpose.** Self-contained Claude Code prompts for the four LOW-risk sub-steps of Phase 8A: 8A.1, 8A.3, 8A.5, 8A.7.
>
> **How to use.** Open a fresh Claude Code session in the repo root (`C:\Users\GEMO 050224\Desktop\cursor\GF updater v3`). Copy ONE prompt block at a time into Claude Code. Run it. Bring the execution report back here for trust-but-verify before moving to the next.
>
> **MEDIUM steps (8A.2, 8A.4)** and **8A.6** are deliberately not in this file. They require per-step approval and a separate session.
>
> **Spec reference.** Every prompt below points back to `docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md` (the self-contained plan doc) for the authoritative section. The prompts are tight on purpose — they restate only what the executing agent needs.
>
> **Recommended order.** 8A.1 → 8A.3 → 8A.5 first (independent; any order works). 8A.7 LAST and only after 8A.6 has shipped (which is in a later session).

---

## 1. Step 8A.1 — D-010 Focus-Visa Source Audit (LOW)

Copy the block below into a fresh Claude Code session.

```
You are executing Phase 8A.1 — D-010 Focus-Visa Source Audit. Authoritative
spec: docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md §7. Read that
section first, then proceed.

OBJECTIVE
  Find and prove every remaining direct compute_visa_global_with_date(...)
  call in src/reporting/ that bypasses the Phase-8 resolve_visa_global helper.
  Known suspect: _precompute_focus_columns in src/reporting/data_loader.py.
  There may be others.

HARD CONSTRAINTS
  - This is a read-only audit + new script under scripts/. Production source is
    NOT touched.
  - Phase 8 audit one-liner must remain unchanged after your run:
      AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
      UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match
  - Use the Read tool (not bash grep/wc/cat) for inspecting source files —
    bash on the Windows mount lies (hazard H-1 in context/11_TOOLING_HAZARDS.md).
  - Bash IS fine for executing python scripts.

FILES
  READ:
    src/reporting/data_loader.py
    src/reporting/aggregator.py
    src/reporting/focus_filter.py
    src/reporting/focus_ownership.py
    src/workflow_engine.py            (READ ONLY — for the function signature)
    scripts/audit_counts_lineage.py   (READ ONLY — pattern to follow)

  CREATE:
    scripts/audit_focus_visa_source.py
    output/debug/focus_visa_source_audit.json
    output/debug/focus_visa_source_audit.xlsx

  DO NOT TOUCH:
    src/flat_ged/*  src/reporting/*  src/workflow_engine.py
    src/effective_responses.py  ui/jansa/*  app.py  main.py
    run_chain_onion.py  data/*.db  runs/*  output/intermediate/FLAT_GED*

WHAT THE SCRIPT MUST DO
  1. AST-walk every file under src/reporting/ for compute_visa_global_with_date
     call sites.
  2. For each call site, record:
       function_name
       file_path
       line_number
       uses_workflow_engine_directly  (bool — True if we.compute_visa_global_with_date
                                        or ctx.workflow_engine.compute_visa_global_with_date)
       uses_flat_doc_meta             (bool — True if surrounding code reads
                                        ctx.flat_ged_doc_meta first)
       uses_resolve_visa_global_equivalent  (bool — True if wrapped by
                                              resolve_visa_global)
       affected_output_columns        (list — inferred from surrounding assignment context)
       count_of_docs_checked          (int — for live runs only; how many docs
                                        hit this call site in run 0)
       count_of_disagreements         (int — for each doc, does meta-visa equal
                                        engine-visa? Count rows where they differ)
  3. Write output/debug/focus_visa_source_audit.json with the full catalogue.
  4. Write output/debug/focus_visa_source_audit.xlsx with one sheet listing
     every call site.
  5. Print stdout summary line, exactly this shape:
       FOCUS_VISA_AUDIT: call_sites=<n> direct_engine=<n> via_resolver=<n> disagreements_total=<n>

VALIDATION (run all and paste verbatim output)
  python -m py_compile scripts/audit_focus_visa_source.py
  python scripts/audit_focus_visa_source.py
  python scripts/audit_counts_lineage.py
  # The Phase 8 audit one-liner must remain byte-identical to the contract above.

ACCEPTANCE
  - At least 1 direct_engine entry surfaces (the known _precompute_focus_columns
    site). If 0, you missed it — re-inspect data_loader.py manually.
  - count_of_disagreements should be 0 or small. Phase 8 verified flat_doc_meta
    and engine agreed on visa for every doc in run 0.
  - Phase 8 audit one-liner unchanged after your run.

RETURN REPORT (paste verbatim, no embellishment)
  1. Files created with absolute paths and line counts.
  2. Verbatim stdout from python scripts/audit_focus_visa_source.py.
  3. Verbatim stdout from python scripts/audit_counts_lineage.py.
  4. Top 3 entries from the JSON catalogue (so the orchestrator can spot-check
     via Read tool).
  5. Anything you did NOT do that the spec asked for, with reason.

TRUST-BUT-VERIFY (for you, the executing agent)
  Before you flip status to ✅, Read the actual file you wrote and confirm:
    - The stdout summary line matches the catalogue contents.
    - The JSON has the exact key set listed above.
    - The xlsx sheet exists.
  Phase 8 had three execution reports that lied about what was on disk.
  Don't be the fourth.
```

---

## 2. Step 8A.3 — Chain+Onion BLOCK-Mode Readiness Audit (LOW)

Copy the block below into a fresh Claude Code session.

```
You are executing Phase 8A.3 — Chain+Onion BLOCK-Mode Readiness Audit.
Authoritative spec: docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md §9.
Read that section first, then proceed.

OBJECTIVE
  Before flipping the Chain+Onion alignment check from WARN to BLOCK in 8A.4
  (a separate MEDIUM-risk session), prove the alignment check has been clean
  across at least one full pipeline cycle that exercised registry writes.

HARD CONSTRAINTS
  - Read-only audit + new script under scripts/. Production source is NOT
    touched. src/chain_onion/source_loader.py is read-only here.
  - Phase 8 audit one-liner must remain unchanged after your run:
      AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
      UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match
  - Use the Read tool (not bash) for inspecting source files. Bash IS fine
    for executing python scripts.
  - data/run_memory.db must be opened in read-only mode (sqlite3 mode=ro).

FILES
  READ:
    output/debug/chain_onion_source_check.json   (latest)
    data/run_memory.db                            (READ ONLY — sqlite3 mode=ro)
    src/chain_onion/source_loader.py              (READ ONLY — find _check_flat_ged_alignment
                                                    helper from Phase 8 §23)

  CREATE:
    scripts/check_chain_onion_alignment_block_ready.py
    output/debug/chain_onion_block_readiness.json

  DO NOT TOUCH:
    src/chain_onion/source_loader.py   (no code change here — that is 8A.4)
    everything else on the Phase 8A do-not-touch list (§4 of the spec).

WHAT THE SCRIPT MUST DO
  1. Load the latest output/debug/chain_onion_source_check.json.
  2. Verify:
       - File exists and was produced by the helper added in Phase 8 §23.
       - result is one of OK or WARN_MTIME_ADVISORY (NOT WARN_*_MISMATCH or
         UNDETERMINED).
       - registered_flat_ged_path is non-null.
       - using_flat_ged_path is non-null.
       - sha_match is true or null (null is acceptable when paths are
         identical — sha is not computed).
  3. Verify a fresh pipeline run + Chain+Onion run has happened since the
     WARN check landed:
       - Open data/run_memory.db in read-only mode.
       - Confirm at least one run with completed_at more recent than the
         helper's first invocation.
       - Confirm the latest registered FLAT_GED artifact's mtime is greater
         than the helper's first-invocation timestamp.
  4. Write output/debug/chain_onion_block_readiness.json with this exact
     schema:
       {
         "checked_at": "<iso>",
         "block_mode_ready": true | false,
         "reason": "<one-line explanation>",
         "latest_check_result": "<OK|WARN_*|UNDETERMINED>",
         "latest_run_completed_at": "<iso or null>",
         "latest_flat_ged_mtime": <float>,
         "helper_first_seen_at": "<iso or null>"
       }
  5. Print stdout summary, exactly this shape:
       BLOCK_READINESS: ready=<true|false> reason=<...>

VALIDATION (run all and paste verbatim output)
  python -m py_compile scripts/check_chain_onion_alignment_block_ready.py
  python scripts/check_chain_onion_alignment_block_ready.py
  python scripts/audit_counts_lineage.py
  # The Phase 8 audit one-liner must remain byte-identical to the contract.

ACCEPTANCE
  - block_mode_ready is true OR block_mode_ready is false with a documented,
    actionable reason.
  - No production code changed.
  - Phase 8 audit one-liner unchanged.

RETURN REPORT (paste verbatim)
  1. Files created with absolute paths and line counts.
  2. Verbatim stdout from python scripts/check_chain_onion_alignment_block_ready.py.
  3. Verbatim stdout from python scripts/audit_counts_lineage.py.
  4. Full contents of output/debug/chain_onion_block_readiness.json.
  5. Anything you did NOT do that the spec asked for, with reason.

TRUST-BUT-VERIFY (for you, the executing agent)
  Before you flip status to ✅, Read the actual JSON file you wrote and
  confirm the key set matches the schema in step 4 above (exactly those keys,
  no more, no fewer). Then re-read scripts/check_chain_onion_alignment_block_ready.py
  and confirm the SQL is read-only.
```

---

## 3. Step 8A.5 — Full UI Metric Inventory (LOW, documentation only)

Copy the block below into a fresh Claude Code session.

```
You are executing Phase 8A.5 — Full UI Metric Inventory. Authoritative spec:
docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md §11. Read that section
first, then proceed.

OBJECTIVE
  Document every UI number and its backend source. This becomes the canonical
  reference future audits key off, and it is the input to Step 8A.6 (widened
  UI payload audit, deferred to a later session).

HARD CONSTRAINTS
  - This step is documentation only. NO Python, NO scripts, NO production
    source touched.
  - Use the Read tool for every source file. The Windows mount + bash combo
    is unreliable (H-1).
  - Output is exactly one new file: context/12_UI_METRIC_INVENTORY.md. No
    other context/* files modified.
  - The inventory is the input to 8A.6, so completeness matters. Missing a
    page = missing a future audit.

FILES
  READ (every one of these — do not skip):
    ui/jansa/overview.jsx
    ui/jansa/consultants.jsx
    ui/jansa/contractors.jsx
    ui/jansa/consultant_fiche.jsx           (or whichever fiche entry exists —
                                              verify by listing ui/jansa/)
    ui/jansa/contractor_fiche_page.jsx
    ui/jansa/dcc.jsx                         (Document Command Center; verify name)
    ui/jansa/data_bridge.js
    ui/jansa-connected.html
    app.py                                   (the Api methods exposed via pywebview)
    src/reporting/ui_adapter.py
    src/reporting/aggregator.py
    src/reporting/contractor_quality.py
    src/reporting/contractor_fiche.py
    src/reporting/consultant_fiche.py
    src/reporting/document_command_center.py

  CREATE:
    context/12_UI_METRIC_INVENTORY.md

  DO NOT TOUCH:
    Every file listed above is READ-ONLY.
    No scripts/ files created.
    No tests/ files created.
    No other context/*.md files modified.

WHAT THE INVENTORY MUST CONTAIN
  For every UI element that displays a number, percentage, or count, one row
  in a markdown table with these exact columns:

  | page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |

  Field meanings:
    page                 UI page or section name (e.g. "Overview", "Consultants tab")
    component            JSX component (e.g. "MoexCard", "ConsultantCard")
    label                visible UI text (e.g. "À traiter", "Total docs")
    js_field             JS property the component reads (e.g. "c.focus_owned")
    api_method           the app.Api.* method that supplies it
                         (e.g. "app.Api.get_overview_for_ui")
    py_function          the Python function that ultimately produces the value
                         (e.g. "aggregator.compute_consultant_summary")
    source_dataframe     what dataframe / artifact the value comes from
                         (e.g. "ctx.dernier_df", "ctx.workflow_engine.responses_df",
                          "output/chain_onion/top_issues.json")
    semantic_definition  one sentence describing what the number means
    audit_coverage       Yes / No / Partial — does scripts/audit_counts_lineage.py
                         check it today?
    audit_gap            if not fully covered, what is missing — one phrase

  Pages to cover (do NOT skip any; confirm by listing ui/jansa/ first):
    Overview
    Consultants tab
    Contractors tab
    Consultant fiche
    Contractor fiche
    Document Command Center
    Chain+Onion panel
    Runs page
    Export panel

  If your walk surfaces additional pages (Settings, Discrepancies, Reports,
  etc.), ADD them to the inventory. Do not shrink the list.

DOCUMENT STRUCTURE
  context/12_UI_METRIC_INVENTORY.md should open with:
    - Title.
    - Generated-at date (ISO).
    - One paragraph stating the purpose ("source-of-truth map between UI
      numbers and backend producers; input to Phase 8A.6").
    - One paragraph naming the active UI runtime (PyWebView + ui/jansa-connected.html
      + Babel standalone JSX, per CLEAN Step 11 / docs/UI_SOURCE_OF_TRUTH_MAP.md).
    - Then one section per page, each containing the table above.
  Close the document with a "Coverage summary" section listing:
    - Total rows.
    - Rows per page.
    - Rows where audit_coverage = Yes / No / Partial.
    - Rows flagged as inputs to 8A.6 (any audit_coverage != Yes).

VALIDATION (manual — no Python here)
  - Confirm context/12_UI_METRIC_INVENTORY.md exists and renders cleanly as
    Markdown (open it in any preview).
  - Confirm every page in the §11 list above has at least one row.
  - Confirm every row has a non-empty py_function value (or "UI-computed,
    no backend source" with a follow-up note in audit_gap).
  - Phase 8 audit must remain unchanged:
      python scripts/audit_counts_lineage.py
    Expected: PASS=16 WARN=0 FAIL=1 + UI_PAYLOAD compared=10 matches=10 mismatches=0.

ACCEPTANCE
  - Every displayed number on the listed pages has a row in the inventory.
  - Every row names a backend source (or explicitly marks UI-computed).
  - Rows with audit_coverage=No or Partial are listed in the closing summary
    so 8A.6 knows exactly what to add.

RETURN REPORT (paste verbatim)
  1. Path and line count of context/12_UI_METRIC_INVENTORY.md.
  2. The Coverage summary section verbatim.
  3. The full table for ONE page (e.g. Overview) so the orchestrator can
     spot-check structure.
  4. List of any additional pages you discovered beyond the §11 list.
  5. Anything you did NOT do that the spec asked for, with reason.

TRUST-BUT-VERIFY (for you, the executing agent)
  Before you flip status to ✅, Read context/12_UI_METRIC_INVENTORY.md back
  and confirm:
    - Every page header from the §11 list is present (Ctrl-F for each name).
    - The table columns match the spec exactly (10 columns, in order).
    - The Coverage summary numbers add up.
```

---

## 4. Step 8A.7 — UI Snapshot Layer Decision (LOW, decision only)

> **Run this LAST**, and only after Step 8A.6 (widened UI payload audit) has shipped in a separate session. 8A.7 is decision-only; it has no value before 8A.6 produces the brittleness signal.

Copy the block below into a fresh Claude Code session AFTER 8A.6.

```
You are executing Phase 8A.7 — UI Snapshot Layer Decision. Authoritative
spec: docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md §13. Read that
section first, then proceed.

OBJECTIVE
  After Step 8A.6 has landed, decide whether the current
  aggregator → ui_adapter flow is sustainable, or whether a single UI
  snapshot artifact (RunContext → UI_METRICS_SNAPSHOT.json → UI) is
  warranted as a future Phase 8C.

PRECONDITIONS (verify before you write the decision)
  - context/12_UI_METRIC_INVENTORY.md exists (from 8A.5).
  - output/debug/ui_payload_full_surface_audit.{json,xlsx} exists (from 8A.6).
  - scripts/audit_counts_lineage.py has been run at least 3 times since
    8A.6 landed, and you have the verdict line from each.

HARD CONSTRAINTS
  - Decision-only step. NO Python, NO scripts, NO production source.
  - Modify ONE file: context/07_OPEN_ITEMS.md (Phase 8A section). Append a
    new entry; do not rewrite anything else in the file.
  - If decision = open Phase 8C, also CREATE
    docs/implementation/PHASE_8C_UI_SNAPSHOT.md as a stub spec for the
    next session — do not implement anything in it now.

DECISION CRITERIA (locked from §13.3 of the spec)
  - If the 8A.6 widened audit is STABLE (mismatches consistently 0 across
    runs, naming_only entries documented and rare):
      → decision = "keep architecture"
  - If the 8A.6 widened audit is BRITTLE (mismatches keep appearing, the
    field map needs frequent updates, refactors in ui_adapter.py keep
    diverging):
      → decision = "open Phase 8C"

  Brittleness threshold (suggested in §13.3): more than 2 naming_only
  mismatches in 3 consecutive runs of audit_counts_lineage.py.

FILES
  READ:
    docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md   (§13)
    context/12_UI_METRIC_INVENTORY.md
    output/debug/ui_payload_full_surface_audit.json
    output/debug/ui_payload_full_surface_audit.xlsx
    context/07_OPEN_ITEMS.md                                (existing content)

  MODIFY:
    context/07_OPEN_ITEMS.md   (append a new Phase 8A.7 decision entry)

  CREATE (only if decision = open Phase 8C):
    docs/implementation/PHASE_8C_UI_SNAPSHOT.md   (stub spec, not implemented)

  DO NOT TOUCH:
    Every other file on the Phase 8A do-not-touch list.

WHAT THE 07_OPEN_ITEMS.md ENTRY MUST CONTAIN
  - Date (ISO, today).
  - The decision verbatim ("keep architecture" or "open Phase 8C").
  - The brittleness signal that triggered the decision: counts of
    mismatches per run for the last 3 runs of audit_counts_lineage.py,
    plus the count of naming_only / scope_filter / true_bug entries from
    the 8A.6 audit JSON.
  - One sentence on rationale.
  - If decision = open Phase 8C: link to docs/implementation/PHASE_8C_UI_SNAPSHOT.md.

VALIDATION
  - context/07_OPEN_ITEMS.md still contains all pre-existing content
    (verify by reading it before and after, line count and a sample
    section header should match).
  - Phase 8 audit unchanged:
      python scripts/audit_counts_lineage.py
    Expected: PASS=16 WARN=0 FAIL=1; UI_PAYLOAD line per spec.

ACCEPTANCE
  - context/07_OPEN_ITEMS.md has a new dated Phase 8A.7 entry with the
    decision and the supporting numbers.
  - If "open Phase 8C", docs/implementation/PHASE_8C_UI_SNAPSHOT.md exists
    as a stub.
  - Phase 8 audit one-liner unchanged.

RETURN REPORT (paste verbatim)
  1. The new entry appended to context/07_OPEN_ITEMS.md (verbatim).
  2. Pre-edit and post-edit line counts for context/07_OPEN_ITEMS.md.
  3. If created, path and stub contents of
     docs/implementation/PHASE_8C_UI_SNAPSHOT.md.
  4. Verbatim stdout from python scripts/audit_counts_lineage.py.

TRUST-BUT-VERIFY (for you, the executing agent)
  Before you flip status to ✅, Read context/07_OPEN_ITEMS.md back and
  confirm:
    - The new entry is present at the end (or in the Phase 8A section if
      one already exists).
    - No prior content was deleted or reformatted.
    - The dated header matches today's date.
```

---

## Orchestrator notes (for me, after each prompt runs)

After each prompt comes back from Claude Code:

1. **Trust-but-verify by Read tool.**
   - 8A.1: Read `output/debug/focus_visa_source_audit.json` and confirm the key set matches the spec; spot-check 3 entries by Read on the named source files at the named line numbers.
   - 8A.3: Read `output/debug/chain_onion_block_readiness.json` and verify the schema matches §9.3 exactly.
   - 8A.5: Read `context/12_UI_METRIC_INVENTORY.md` and Ctrl-F for each page name from §11.3; spot-check 5 random rows by reading the named `py_function` to confirm it exists.
   - 8A.7: Read `context/07_OPEN_ITEMS.md` before and after; line-count delta should equal the appended block.
2. **Confirm Phase 8 audit one-liner unchanged.** Every step's report must include the verbatim `audit_counts_lineage.py` stdout. Match against:
   - `AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX`
   - `UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match`
3. **Update context.** After each successful step:
   - 8A.1 close → no context update needed beyond noting the artifact path in `context/07_OPEN_ITEMS.md` (D-010 gets the audit reference).
   - 8A.3 close → record the readiness verdict in `context/07_OPEN_ITEMS.md`.
   - 8A.5 close → `context/12_UI_METRIC_INVENTORY.md` is itself the context update.
   - 8A.7 close → `context/07_OPEN_ITEMS.md` is itself the context update.
4. **Mark the task done** in this session's task list.

---

## Out of scope for this session (deferred)

- **8A.2 D-010 patch** (MEDIUM) — needs explicit per-step approval. Will be a separate session.
- **8A.4 Chain+Onion BLOCK flip** (MEDIUM) — same. Depends on 8A.3 returning `ready=true`.
- **8A.6 Widened UI payload audit** (LOW audit / MEDIUM if patch) — requires `context/12_UI_METRIC_INVENTORY.md` from 8A.5 as input. Schedule after 8A.5 closes.
