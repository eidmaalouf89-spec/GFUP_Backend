# Phase 8A — Remaining Work, Single Consolidated Prompt (Opus 4.7, 1M context)

> **Purpose.** One Claude Code prompt that closes the rest of Phase 8A: 8A.6 widened UI payload audit, 8A.2 D-010 patch (`_precompute_focus_columns` only), 8A.2b D-010 patch (consultant_fiche + contractor_fiche, conditional on 8A.6 impact), 8A.4 Chain+Onion BLOCK-mode flip, 8A.7 snapshot decision. Returns one consolidated verifiable report.
>
> **How to use.** Open ONE Claude Code session in the repo root with Opus 4.7 + 1M context. Paste the block below. The agent runs all five sub-steps in the spec's recommended order, with auto-stop conditions that the project owner cannot pre-approve (true_bug surfaces, readiness still false after main.py rerun, Phase 8 audit shifts).
>
> **Pre-approval scope (this is the critical line):** by issuing this prompt, the project owner pre-approves the locked-design patches:
> - 8A.2 (`src/reporting/visa_resolver.py` shared module per spec §8.1, smallest-blast-radius patch limited to `_precompute_focus_columns`)
> - 8A.2b (mechanical extension of the same resolver to consultant_fiche + 6× contractor_fiche sites — only if 8A.6 proves visible UI impact)
> - 8A.4 (BLOCK-mode flip per spec §10.2, raise on `WARN_PATH_AND_CONTENT_MISMATCH` or `UNDETERMINED`)
>
> Pre-approval does NOT cover: any `ui_adapter.py` change in 8A.6 (a true_bug stops execution); any change to the locked patch shapes; any change outside the spec's authorized files.

---

## The prompt

Copy the block below into one Claude Code session.

```
You are executing the remainder of Phase 8A — Downstream Hardening — in
ONE consolidated session. Authoritative spec:
docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md (read it cover to cover
before any code lands). Live status doc:
context/07_OPEN_ITEMS.md (Phase 8A — Downstream Hardening Status section).
Project rules: CLAUDE.md (root) — Surgical Changes, Goal-Driven Execution,
Trust-but-Verify discipline.

The project owner has pre-approved the locked-design MEDIUM patches in this
prompt (8A.2 visa_resolver per spec §8.1; 8A.4 BLOCK policy per spec §10.2;
8A.2b mechanical resolver extension to consultant_fiche + contractor_fiche).
The HARD STOP conditions below are the only places you must halt for human
input. Otherwise execute end to end and produce the consolidated report.

============================================================================
SECTION 0 — HARD STOPS (read before anything)
============================================================================

If ANY of these conditions trigger, stop immediately, write what you know
to a partial report, and exit non-zero. Do NOT attempt to "fix" them.

  S1. Phase 8 audit one-liner shifts from baseline at any check.
      Baseline (byte-identical):
        AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
        UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match

  S2. Focus ownership baseline shifts after 8A.2 or 8A.2b patch.
      Baseline:
        Focus ownership computed: CLOSED=791, CONTRACTOR=320, MOEX=2647, PRIMARY=987, SECONDARY=89

  S3. 8A.6 surfaces ANY mismatch classified as `true_bug` (>=1).
      Do not patch ui_adapter.py. Stop and report.

  S4. 8A.4 readiness check still returns ready=false after a fresh
      `python main.py` rerun. Stop and report. Do NOT flip BLOCK.

  S5. `python main.py` exits non-zero, OR the resulting run is not
      registered as COMPLETED in data/run_memory.db.

  S6. Any unit test in the new test files fails post-patch.

  S7. App import smoke (`python -c "import app"`) fails post-patch.

  S8. AST walk in 8A.1 verification reveals a NEW direct-engine call site
      not in the known catalogue of 8 (data_loader.py:604,
      consultant_fiche.py:1375, contractor_fiche.py:138/175/198/226/252/317).

============================================================================
SECTION 1 — PRE-FLIGHT (no writes)
============================================================================

  1.1 Read the spec end to end:
        docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md
        docs/implementation/PHASE_8A_LOW_RISK_PROMPTS.md (for closed-step context)
        context/07_OPEN_ITEMS.md (Phase 8A — Downstream Hardening Status section
                                  + closed Phase 8 reference)
        context/05_OUTPUT_ARTIFACTS.md (debug outputs table)
        context/10_VALIDATION_COMMANDS.md (sections L and M)
        context/11_TOOLING_HAZARDS.md (H-1, H-4, H-5)
        context/12_UI_METRIC_INVENTORY.md (ENTIRELY — 8A.6 needs every row)

  1.2 Read the closed-step artifacts produced by the LOW batch:
        output/debug/focus_visa_source_audit.json
        output/debug/focus_visa_source_audit.xlsx
        output/debug/chain_onion_block_readiness.json

  1.3 Establish the baseline:
        python -m py_compile app.py main.py run_chain_onion.py
        python scripts/audit_counts_lineage.py
      Capture stdout verbatim. Confirm Phase 8 audit one-liner matches S1
      baseline. If not, HALT (S1).

  1.4 Use the Read tool (NOT bash grep/wc/cat) for inspecting source files
      under src/. Bash IS fine for executing python scripts and for sqlite3
      read-only queries. (H-1 in context/11_TOOLING_HAZARDS.md.)

  1.5 Pytest in sandbox may hang (H-4). All pytest invocations must use
      `timeout 60 python -m pytest ... -q`. Treat timeouts as inconclusive,
      not failures — flag in the report and defer the failing assertion to
      the project owner's Windows shell.

============================================================================
SECTION 2 — 8A.6 WIDENED UI PAYLOAD AUDIT (LOW; STOP if true_bug)
============================================================================

Authoritative spec: §12.

  2.1 Files to create:
        scripts/audit_ui_payload_full_surface.py
        tests/test_ui_payload_full_surface.py
        output/debug/ui_payload_full_surface_audit.json
        output/debug/ui_payload_full_surface_audit.xlsx

  2.2 Files to read (input):
        context/12_UI_METRIC_INVENTORY.md          (§11 inventory — input)
        scripts/audit_counts_lineage.py            (Phase 8 §24 pattern to follow)
        src/reporting/ui_adapter.py
        src/reporting/aggregator.py
        src/reporting/contractor_quality.py
        src/reporting/contractor_fiche.py
        src/reporting/consultant_fiche.py
        src/reporting/document_command_center.py
        app.py                                     (Api method signatures)

  2.3 Do NOT modify:
        scripts/audit_counts_lineage.py            (preserve Phase 8 audit one-liner)
        src/reporting/ui_adapter.py                (NO patch in 8A.6 even if mismatches found)
        src/reporting/aggregator.py
        anything else on the Phase 8A do-not-touch list (spec §4 + §17)

  2.4 Script behaviour (per spec §12.3):
      - Per-surface field-mapping tables for: consultants_list, contractors_list,
        consultant_fiche, contractor_fiche, dcc, chain_onion_panel.
      - Invoke each adapter once with a real RunContext.
      - Walk the corresponding aggregator output for each surface.
      - Field-by-field comparison using the Phase 8 §24 taxonomy
        (identity, numeric_equal, set_equal, dict_equal, skipped).
      - Per-surface mismatch sheets in the xlsx; totals in the json.
      - Stdout summary line:
          UI_PAYLOAD_FULL: surfaces=<n> compared=<n> matches=<n> mismatches=<n>; <verdict>

  2.5 Mismatch classification (per spec §12.4):
        naming_only                  — same number, different key path (would fix in ui_adapter)
        scope_filter                 — different filter at adapter vs aggregator
        expected_semantic_difference — adapter intentionally reshapes (e.g. REF + SAS_REF merge)
        true_bug                     — real divergence in arithmetic. **HARD STOP S3.**

  2.6 Validation:
        python -m py_compile scripts/audit_ui_payload_full_surface.py
        python scripts/audit_ui_payload_full_surface.py
        python scripts/audit_counts_lineage.py            # baseline check
        timeout 60 python -m pytest tests/test_ui_payload_full_surface.py -q

  2.7 Acceptance:
        - Every UI surface from context/12_UI_METRIC_INVENTORY.md has a
          comparison row count > 0 (or an explicit "no comparable backend
          field" note in the report).
        - true_bug = 0 (else HALT per S3).
        - naming_only / scope_filter mismatches catalogued (will inform 8A.7
          decision).
        - Phase 8 audit one-liner unchanged.

  2.8 Trust-but-verify before continuing:
        Read output/debug/ui_payload_full_surface_audit.json back. Confirm
        the surface count, the compared count, and the per-classification
        breakdowns are internally consistent.

  Capture for the report:
      - 8A.6.STDOUT (verbatim summary line)
      - 8A.6.JSON_TOTALS (totals per classification per surface)
      - 8A.6.AUDIT_RECHECK (Phase 8 one-liner verbatim, post-script)

============================================================================
SECTION 3 — 8A.2 D-010 PATCH, MINIMAL (MEDIUM, pre-approved, locked design)
============================================================================

Authoritative spec: §8 (specifically §8.3 patch shape).

Scope: ONLY `_precompute_focus_columns` in src/reporting/data_loader.py.
Do NOT extend to consultant_fiche or contractor_fiche in this section —
those are 8A.2b, gated on 8A.6 impact (Section 4).

  3.1 Files to read (full file, not snippets):
        src/reporting/data_loader.py
        src/reporting/aggregator.py
        src/reporting/focus_ownership.py
        src/workflow_engine.py             (READ ONLY)
        tests/test_resolve_visa_global.py  (current test file)

  3.2 Files to create:
        src/reporting/visa_resolver.py
        tests/test_visa_resolver.py

  3.3 Files to modify:
        src/reporting/aggregator.py        (replace inline resolver with import)
        src/reporting/data_loader.py       (route _precompute_focus_columns
                                            through resolve_visa_global)
        tests/test_resolve_visa_global.py  (update import path; or rename file)

  3.4 Do NOT modify:
        src/workflow_engine.py
        src/flat_ged/*
        src/effective_responses.py
        src/reporting/consultant_fiche.py     (8A.2b territory)
        src/reporting/contractor_fiche.py     (8A.2b territory)
        ui/jansa/*
        data/*.db
        runs/*
        app.py / main.py / run_chain_onion.py

  3.5 Patch shape — verbatim from spec §8.3:

        # NEW src/reporting/visa_resolver.py
        """Tiny shared helper. Phase 8A.2 (2026-05-01).

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
            meta = getattr(ctx, "flat_ged_doc_meta", None) or {}
            entry = meta.get(doc_id)
            if entry:
                visa = entry.get("visa_global")
                if visa:
                    _, vdate = ctx.workflow_engine.compute_visa_global_with_date(doc_id)
                    return visa, vdate
            return ctx.workflow_engine.compute_visa_global_with_date(doc_id)

        # In src/reporting/aggregator.py — replace the inline
        # `def resolve_visa_global(ctx, doc_id): ...` (around lines 33–50)
        # with a single line:
        from .visa_resolver import resolve_visa_global   # noqa: F401  (re-exported)

        # In src/reporting/data_loader.py — at module top-level imports,
        # add:
        from .visa_resolver import resolve_visa_global

        # Then in _precompute_focus_columns, replace
        #     visa, vdate = we.compute_visa_global_with_date(doc_id)
        # (or whatever the exact local-var name is — read the function first)
        # with:
        #     visa, vdate = resolve_visa_global(ctx, doc_id)

        # In tests/test_resolve_visa_global.py — change the import line
        # from:
        #     from reporting.aggregator import resolve_visa_global
        # to:
        #     from reporting.visa_resolver import resolve_visa_global

  3.6 Read _precompute_focus_columns BEFORE patching to confirm:
        - The function takes `ctx` (RunContext) — verified in spec §8.3.3.
        - The exact local variable name used to access workflow_engine
          (`we`, `ctx.workflow_engine`, etc.).
        - The exact line number of the call site (was line 604 in 8A.1 audit).

  3.7 Validation (run all; STOP on any failure per the relevant S code):
        python -m py_compile src/reporting/visa_resolver.py
        python -m py_compile src/reporting/aggregator.py src/reporting/data_loader.py
        python -m py_compile app.py main.py run_chain_onion.py
        timeout 15 python -c "import app"                            # S7 if fails
        python scripts/audit_counts_lineage.py                       # S1 if shifts
        python scripts/audit_focus_visa_source.py                    # expect direct_engine drops by 1
        timeout 60 python -m pytest tests/test_visa_resolver.py -q   # S6 if fails

  3.8 Acceptance:
        - direct_engine count in focus_visa_source_audit.json drops from
          8 → 7 (the _precompute_focus_columns site now routes via resolver).
        - Phase 8 audit one-liner UNCHANGED.
        - Focus ownership baseline UNCHANGED:
            CLOSED=791, CONTRACTOR=320, MOEX=2647, PRIMARY=987, SECONDARY=89
          (visible in app import smoke or audit_focus_visa_source.py stdout)
        - tests/test_visa_resolver.py passes (or pytest timeout — flag).

  3.9 Trust-but-verify before continuing:
        Read src/reporting/visa_resolver.py back — confirm the docstring
        has the 2026-05-01 date and the function signature is exact.
        Read src/reporting/data_loader.py around line 604 — confirm the
        call site now reads `resolve_visa_global(ctx, doc_id)`.
        Read src/reporting/aggregator.py around line 33-50 — confirm the
        inline resolver is GONE and the import line is in place.

  Capture for the report:
      - 8A.2.FILES (paths + line counts of created/modified files)
      - 8A.2.AUDIT_RECHECK (Phase 8 one-liner, post-patch)
      - 8A.2.FOCUS_AUDIT (audit_focus_visa_source.py stdout, post-patch)
      - 8A.2.PYTEST (verbatim or timeout note)
      - 8A.2.SMOKE (app import result)

============================================================================
SECTION 4 — 8A.2b D-010 EXTENSION (CONDITIONAL ON 8A.6 IMPACT)
============================================================================

Run this section ONLY if 8A.6 surfaced ANY mismatch in any of these surfaces:
  - consultant_fiche
  - contractor_fiche
  - dcc (which renders contractor metrics)

Source: any naming_only / scope_filter / expected_semantic_difference whose
backing py_function is in src/reporting/consultant_fiche.py or
src/reporting/contractor_fiche.py.

If 8A.6 surfaced ZERO mismatches in those surfaces, SKIP this section.
Record in the report: "8A.2b deferred — no UI-visible impact from
consultant_fiche / contractor_fiche bypass sites in 8A.6 audit." Move
straight to Section 5.

If 8A.6 surfaced impact, proceed:

  4.1 Files to read (full files):
        src/reporting/consultant_fiche.py
        src/reporting/contractor_fiche.py
        src/reporting/visa_resolver.py            (just created in 8A.2)

  4.2 Files to modify:
        src/reporting/consultant_fiche.py         (1 site at line 1375)
        src/reporting/contractor_fiche.py         (6 sites: 138, 175, 198, 226, 252, 317)

  4.3 Patch shape:

      consultant_fiche.py — inside _has_visa_global (around line 1374-1376):
        Add at module top imports:
            from .visa_resolver import resolve_visa_global
        Replace:
            def _has_visa_global(doc_id):
                visa, _ = ctx.workflow_engine.compute_visa_global_with_date(doc_id)
                return visa is not None
        With:
            def _has_visa_global(doc_id):
                visa, _ = resolve_visa_global(ctx, doc_id)
                return visa is not None

      contractor_fiche.py — at each of 6 sites (138, 175, 198, 226, 252, 317):
        Add at module top imports:
            from .visa_resolver import resolve_visa_global
        Read each site first to confirm local-variable access pattern.
        Each call has shape:
            visa, vdate = we.compute_visa_global_with_date(did)
          OR:
            visa, _ = we.compute_visa_global_with_date(did)
        Replace with:
            visa, vdate = resolve_visa_global(ctx, did)
          OR:
            visa, _ = resolve_visa_global(ctx, did)
        respectively. The function ctx is in scope at every site (verify by
        reading the surrounding function signatures).

  4.4 Validation:
        python -m py_compile src/reporting/consultant_fiche.py src/reporting/contractor_fiche.py
        python -m py_compile app.py main.py
        timeout 15 python -c "import app"                  # S7
        python scripts/audit_counts_lineage.py             # S1
        python scripts/audit_focus_visa_source.py
            # Expect direct_engine drops from 7 (after 8A.2) to 0.
            # Expect via_resolver rises to 9 (was 2 + 7 sites).

  4.5 Acceptance:
        - direct_engine = 0 in focus_visa_source_audit.json. D-010 fully closed.
        - Phase 8 audit one-liner UNCHANGED.
        - Focus ownership baseline UNCHANGED.
        - App import smoke OK.

  4.6 Trust-but-verify:
        Read each modified file back at the affected line ranges. Confirm:
        - All 7 sites now use resolve_visa_global(ctx, ...).
        - The import is present at module top.
        - No unrelated lines were touched.

  Capture for the report:
      - 8A.2b.RAN (yes/no/skipped + reason)
      - 8A.2b.FILES (modified files + line ranges touched)
      - 8A.2b.AUDIT_RECHECK
      - 8A.2b.FOCUS_AUDIT (expect direct_engine=0)
      - 8A.2b.SMOKE

============================================================================
SECTION 5 — 8A.4 CHAIN+ONION BLOCK-MODE FLIP (MEDIUM, pre-approved, locked policy)
============================================================================

Authoritative spec: §10 (specifically §10.4 patch shape, §10.2 policy).

Precondition: 8A.3 must report ready=true. Today (2026-05-01) it reports
ready=false because the latest pipeline run predates the WARN helper. The
fix is one fresh `python main.py` cycle, then re-run 8A.3.

  5.1 Run a fresh full pipeline cycle:
        python main.py
      Expect: exit 0, run COMPLETED, ~33 artifacts. This may take several
      minutes. If it fails or the run is not COMPLETED, HALT (S5).

  5.2 Verify run registration:
        python - <<'PY'
        import sqlite3
        c = sqlite3.connect("file:data/run_memory.db?mode=ro", uri=True)
        rows = c.execute(
            "SELECT run_number, status, completed_at FROM runs "
            "ORDER BY run_number DESC LIMIT 1"
        ).fetchall()
        print("LATEST RUN:", rows)
        PY
      Expect: status=COMPLETED, completed_at > '2026-05-01T00:00:00'.

  5.3 Re-run 8A.3 readiness check:
        python scripts/check_chain_onion_alignment_block_ready.py
      Expect: BLOCK_READINESS: ready=true reason=...
      If still ready=false, HALT (S4) with the JSON contents in the report.

  5.4 Files to read:
        src/chain_onion/source_loader.py     (find _check_flat_ged_alignment;
                                                helper added Phase 8 §23, ~line 199)
        output/debug/chain_onion_block_readiness.json   (must say ready=true)

  5.5 Files to modify:
        src/chain_onion/source_loader.py     (extend _check_flat_ged_alignment
                                                to raise on the two BLOCK results)

  5.6 Files to create:
        tests/test_chain_onion_block_mode.py

  5.7 Patch shape — verbatim from spec §10.4:
      After receipts are written and the INFO log line is emitted, before
      the helper returns:

        if receipts["result"] in ("WARN_PATH_AND_CONTENT_MISMATCH", "UNDETERMINED"):
            raise RuntimeError(
                f"[CHAIN_ONION_SOURCE_CHECK] BLOCK: result={receipts['result']} "
                f"reason={receipts.get('reason')}. "
                "FLAT_GED path/content does not align with the latest registered "
                "FLAT_GED artifact. Re-run the pipeline (`python main.py`) to "
                "regenerate the registered artifact, or investigate the divergence."
            )

      Verify: the existing try/except at the helper's caller does NOT
      swallow this exception. Read the call site and confirm. (Spec §10.4.)

  5.8 Validation:
        python -m py_compile src/chain_onion/source_loader.py run_chain_onion.py
        python -m py_compile app.py main.py
        timeout 15 python -c "import app"                          # S7
        python run_chain_onion.py
            # Expect: exit 0; receipts file shows result=OK; no BLOCK fires.
            # If exit != 0, HALT — investigate before reporting success.
        python scripts/audit_counts_lineage.py                     # S1
        timeout 60 python -m pytest tests/test_chain_onion_block_mode.py -q
        timeout 60 python -m pytest tests/test_chain_onion_source_check.py -q
            # If pytest times out, capture and flag.

  5.9 Acceptance (per spec §10.6):
        - Chain+Onion exits 0 on result=OK (the only case observed today).
        - Helper raises on WARN_PATH_AND_CONTENT_MISMATCH and UNDETERMINED.
        - Helper does NOT raise on OK, WARN_MTIME_ADVISORY, or
          WARN_PATH_MISMATCH_SAME_CONTENT.
        - Phase 8 audit one-liner unchanged.
        - All 4 result classes covered by tests.

  5.10 Trust-but-verify:
        Read src/chain_onion/source_loader.py around the helper. Confirm
        the raise is wrapped only in the condition above and the receipts
        write happens BEFORE the raise (we want the receipts on disk even
        when the helper blocks).

  Capture for the report:
      - 8A.4.MAIN_PY (stdout summary, exit code, completed_at)
      - 8A.4.READINESS_RECHECK (full JSON post-rerun)
      - 8A.4.PATCH (modified file paths, exact line ranges touched)
      - 8A.4.RUN_CHAIN_ONION (exit code, receipts result)
      - 8A.4.AUDIT_RECHECK
      - 8A.4.PYTEST

============================================================================
SECTION 6 — 8A.7 UI SNAPSHOT-LAYER DECISION
============================================================================

Authoritative spec: §13. Brittleness threshold from spec §13.3 is
"> 2 naming_only mismatches in 3 consecutive runs of audit_counts_lineage.py".
Single-session adaptation (consistent with §13.3 being "suggested"):
use 8A.6 totals as the brittleness signal directly.

  6.1 Decision logic:
        Read output/debug/ui_payload_full_surface_audit.json.
        Let:
          NM = total naming_only mismatches across all surfaces
          SF = total scope_filter mismatches
          ESD = total expected_semantic_difference (informational)
          TB = total true_bug (must be 0 — else execution stopped at S3)

        Decision:
          if NM <= 2 and SF <= 2:
              decision = "keep architecture"
              rationale = "8A.6 audit clean: naming_only=NM, scope_filter=SF,
                           true_bug=0; current aggregator → ui_adapter flow
                           is sustainable."
          else:
              decision = "open Phase 8C"
              rationale = "8A.6 surfaced NM naming_only + SF scope_filter
                           mismatches across <n> surfaces; field map churn
                           expected; UI snapshot artifact warranted."

  6.2 Files to modify:
        context/07_OPEN_ITEMS.md   (append a new "### Phase 8A.7 decision"
                                    subsection inside the existing
                                    "## Phase 8A — Downstream Hardening Status"
                                    section)

  6.3 Files to create (only if decision = open Phase 8C):
        docs/implementation/PHASE_8C_UI_SNAPSHOT.md   (stub spec, not implemented)

  6.4 The 07_OPEN_ITEMS.md entry must contain:
        - Date (2026-05-01).
        - Decision verbatim ("keep architecture" or "open Phase 8C").
        - The brittleness signal: NM, SF, ESD, TB counts from 8A.6.
        - Per-surface mismatch counts (consultants_list, contractors_list,
          consultant_fiche, contractor_fiche, dcc, chain_onion_panel).
        - Rationale (one or two sentences).
        - If decision = open Phase 8C: link to
          docs/implementation/PHASE_8C_UI_SNAPSHOT.md.

  6.5 Phase 8C stub (only if decision = open Phase 8C):
        - Title: "Phase 8C — UI Snapshot Layer (stub spec, opened by 8A.7)"
        - One-paragraph mission carrying the brittleness signal forward.
        - Out-of-scope reminder: this file is a stub. Implementation is a
          new self-contained plan doc to be written in a future session.

  6.6 Validation:
        Read context/07_OPEN_ITEMS.md before and after; line-count delta
        should equal the appended block (no other content modified).
        python scripts/audit_counts_lineage.py     # S1 (paranoid final check)

  6.7 Trust-but-verify:
        Read the appended subsection back. Confirm the date is 2026-05-01,
        the decision text matches the logic in 6.1, and the per-surface
        counts are the verbatim totals from 8A.6's JSON.

  Capture for the report:
      - 8A.7.DECISION (keep / open 8C)
      - 8A.7.SIGNAL (NM, SF, ESD, TB + per-surface breakdown)
      - 8A.7.RATIONALE (one paragraph)
      - 8A.7.STUB_PATH (path of PHASE_8C_UI_SNAPSHOT.md if created, else "n/a")

============================================================================
SECTION 7 — FINAL VERIFICATION + CONSOLIDATED REPORT
============================================================================

  7.1 Final byte-identical Phase 8 audit check:
        python scripts/audit_counts_lineage.py
      Capture stdout verbatim. Confirm S1 baseline.

  7.2 Final D-010 closure check:
        python scripts/audit_focus_visa_source.py
      Expected:
        - If 8A.2b ran: direct_engine=0, via_resolver=9.
        - If 8A.2b skipped: direct_engine=7, via_resolver=3.

  7.3 Final BLOCK readiness check:
        python scripts/check_chain_onion_alignment_block_ready.py
      Expected: ready=true.

  7.4 Final test sweep (sandbox-safe; flag timeouts):
        timeout 60 python -m pytest tests/test_visa_resolver.py -q
        timeout 60 python -m pytest tests/test_chain_onion_block_mode.py -q
        timeout 60 python -m pytest tests/test_ui_payload_full_surface.py -q

  7.5 Final app smoke:
        timeout 15 python -c "import app"

  7.6 Final repo health:
        python scripts/repo_health_check.py

  7.7 Generate the consolidated report (see structure below).

============================================================================
SECTION 8 — CONSOLIDATED RETURN REPORT FORMAT
============================================================================

Output ONE Markdown block with these exact top-level sections, in this
order. Pad missing data with explicit "n/a — reason" rather than omitting
fields. Project owner uses this report verbatim for trust-but-verify.

# Phase 8A Remaining Work — Execution Report

## Executive summary
- Started: <iso>
- Completed: <iso>
- Hard stops triggered: <list of S codes, or "none">
- Sections executed: <list, e.g. 2, 3, 4, 5, 6, 7>
- Sections skipped: <list with reasons, e.g. "4 — 8A.2b skipped: 8A.6 found
  no consultant_fiche / contractor_fiche impact">
- D-010 final state: <fully closed | partially closed (1 site patched) | not patched>
- 8A.4 BLOCK-mode: <enabled | not enabled, reason>
- 8A.7 decision: <keep architecture | open Phase 8C>

## Phase 8 baseline checks (must all be byte-identical)
| Checkpoint | AUDIT line | UI_PAYLOAD line | Match? |
|---|---|---|---|
| Pre-flight (1.3) | <verbatim> | <verbatim> | yes/no |
| Post-8A.6 (2.6) | <verbatim> | <verbatim> | yes/no |
| Post-8A.2 (3.7) | <verbatim> | <verbatim> | yes/no |
| Post-8A.2b (4.4) | <verbatim or "skipped"> | <verbatim or "skipped"> | yes/no |
| Post-8A.4 (5.8) | <verbatim> | <verbatim> | yes/no |
| Final (7.1) | <verbatim> | <verbatim> | yes/no |

## Section 2 — 8A.6 widened UI payload audit
- Files created (paths + line counts):
- Stdout summary line (verbatim):
- Per-surface breakdown:
| surface | compared | matches | mismatches | naming_only | scope_filter | expected_semantic_difference | true_bug |
|---|---|---|---|---|---|---|---|
- Top 5 mismatches (one row each, with classification):
- Pytest result: <pass | timeout | fail with verbatim output>
- Verdict: <PASS | STOPPED at S3>

## Section 3 — 8A.2 D-010 patch (_precompute_focus_columns only)
- Files created:
| Path | Lines | Purpose |
|---|---|---|
- Files modified:
| Path | Lines changed | Purpose |
|---|---|---|
- Patch verification (Read tool, post-edit):
  - src/reporting/visa_resolver.py docstring date: <verbatim>
  - src/reporting/aggregator.py inline resolver removed: yes/no
  - src/reporting/data_loader.py:_precompute_focus_columns call shape: <verbatim line>
- audit_focus_visa_source.py stdout (verbatim):
- Focus ownership baseline (verbatim from app stdout):
- App import smoke: <OK | error>
- Pytest test_visa_resolver.py: <pass | timeout | fail>

## Section 4 — 8A.2b D-010 extension (consultant_fiche + contractor_fiche)
- Ran: <yes | no — reason>
- If yes:
  - Files modified (with affected line ranges):
  - audit_focus_visa_source.py post-patch stdout (verbatim):
  - direct_engine count: <should be 0 if ran>
  - Phase 8 audit recheck:
- If no:
  - Reason from 8A.6 results:
  - Open item carried forward to next session: yes/no

## Section 5 — 8A.4 Chain+Onion BLOCK-mode flip
- main.py rerun:
  - Exit code:
  - Run number:
  - Status:
  - completed_at:
  - Artifact count:
- Readiness recheck (full JSON, verbatim):
- Patch verification (Read tool, post-edit):
  - src/chain_onion/source_loader.py raise condition (verbatim):
- run_chain_onion.py:
  - Exit code:
  - Receipts result:
- Pytest results:
  - test_chain_onion_block_mode.py: <pass | timeout | fail>
  - test_chain_onion_source_check.py: <pass | timeout | fail>
- Phase 8 audit recheck:
- App import smoke:

## Section 6 — 8A.7 snapshot-layer decision
- Decision: <keep architecture | open Phase 8C>
- Brittleness signal:
  - naming_only total: <n>
  - scope_filter total: <n>
  - expected_semantic_difference total: <n>
  - true_bug total: <n>
- Per-surface mismatch breakdown: (mirror Section 2 table)
- Rationale (one paragraph):
- 07_OPEN_ITEMS.md appended subsection (verbatim):
- Phase 8C stub created? <yes — path | no>

## Section 7 — Final verification
- Final Phase 8 audit (verbatim):
- Final D-010 audit (verbatim):
- Final BLOCK readiness (verbatim):
- Final pytest sweep results:
- Final app import smoke:
- Final repo_health_check.py:

## Anomalies, deviations, things you did NOT do that the spec asked for
- <list each with a one-line reason>

## Trust-but-verify cross-checks performed
- For each modified production file, list the Read-tool spot-checks you
  did before flipping status to ✅. (This is the protection against
  Phase-8-style execution-report inaccuracies.)

============================================================================
END OF PROMPT
============================================================================

Begin execution. Start with Section 1 pre-flight.
```

---

## Notes for the orchestrator (me, after the prompt comes back)

When the report lands here:

1. **Trust-but-verify the report.** The spec carries Phase 8's history of three execution reports that lied about file contents. Read every modified production file via the Read tool, spot-check the patch shape against the report, confirm Phase 8 audit one-liner is byte-identical at every checkpoint.
2. **Reconcile the section-by-section pass/fail.** Any STOPPED-at-S<n> section means the report is partial and the project owner has a decision to make.
3. **Update context once.** After the full execution report is verified, write a single consolidated update to `context/07_OPEN_ITEMS.md` (Phase 8A status section) covering 8A.2 / 8A.2b / 8A.4 / 8A.6 / 8A.7 closure.
4. **Verify Phase 8A is fully closed.** Final state should be: D-010 closed (or explicitly partial with documented reason), BLOCK-mode enabled, UI payload audit covers every surface in the inventory, snapshot-layer decision captured.

## Notes on what this prompt deliberately does NOT cover

- **Phase 8B work** (RAW → FLAT reconciliation, D-011, report integration). Separate session, separate plan doc.
- **Any rewrite of Phase 8A spec.** The locked designs in §8.1 (visa_resolver) and §10.2 (BLOCK policy) are inputs, not negotiable.
- **Cleanup of legacy artifacts** under `output/parity*` etc. Out of scope.
- **README updates.** Per Phase 8A §17 do-not-touch list.
