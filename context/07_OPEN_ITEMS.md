# 07 — Open Items

> Things observed in the actual code/data that look unfinished, weakly
> connected, or likely to bite future work. Not a wishlist — a punch list.

---

## Phase 8 family — closed for current release (status as of 2026-05-01)

The Phase 8 family is closed for the current software finalisation cycle.
**The remaining Phase 8-family items are backlog/hardening/forensic items and are not blockers for software finalisation.**

| Phase | Status | Summary |
|---|---|---|
| **Phase 8 — Count Lineage Fix** | ✅ CLOSED | 57 tests pass on Windows-shell. `AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX`. `UI_PAYLOAD: compared=10 matches=10 mismatches=0`. All 10 baseline checks PASS. Cache-hit path works; cache metadata schema v2 stable. Chain+Onion source alignment OK. Remaining FAIL is D-011 RAW→FLAT SAS REF projection (not a Phase 8 blocker; routed to Phase 8B). |
| **Phase 8A — Downstream Hardening** | ✅ CLOSED FOR CURRENT RELEASE | LOW-risk audits 8A.1, 8A.3, 8A.5, 8A.6, 8A.7 all closed. `UI_PAYLOAD_FULL: surfaces=6 compared=45 matches=45 mismatches=0`. Classification: NM=0, SF=0, ESD=0, TB=0. Decision: KEEP ARCHITECTURE; no UI snapshot layer needed; Phase 8C UI snapshot phase NOT opened. MEDIUM-risk hardening deferred (see backlog). |
| **Phase 8B — RAW → FLAT Reconciliation** | ✅ CLOSED | Outcome C: existing reason logic incomplete + partially incorrect. Identity contract PASS (RAW unique numero == FLAT == 2,819; RAW unique numero+indice == FLAT == 4,848). SAS REF decomposition 99.3% covered (830/836). Sheet 07 SAS REF: 283 matched canonical, 345 DUPLICATE_FAVORABLE_KEPT, 143 DUPLICATE_MERGED, 32 ACTIVE_VERSION_PROJECTION, 27 MALFORMED_RESPONSE, 6 UNEXPLAINED. Reasons audit: 389 sites total — 40 VALID, 1 INVALID, 30 AMBIGUOUS, 318 MISSING. Report integration: 1,245 reports, 0 NO_MATCH, 942 enrich FLAT, 58 supply primary, 226 blocked on confidence. Shadow model: 27,134 shadow operational rows; UNEXPLAINED residual = 6. Audit one-liner unchanged throughout. |
| **Phase 8C** | ⏸ FUTURE BACKLOG ONLY / NOT ACTIVE | Not active for current release. See "Deferred backlog" below. |

### Deferred backlog — not release blockers

These are explicitly **not required for software finalisation**:

1. **D-010 broad cleanup** — direct WorkflowEngine visa call cleanup. 8 direct sites identified by 8A.1; `disagreements_total=0`, widened UI payload audit found 0 mismatches. Hardening only.
2. **Chain+Onion BLOCK-mode flip (8A.4)** — WARN-only is operational. BLOCK mode requires a fresh full pipeline cycle and is enforcement hardening, not a current correctness fix.
3. **Phase 8C unexplained RAW→FLAT triage** — investigate (a) the 6 remaining SAS REF UNEXPLAINED rows in the 28xxx /A C1 cluster, (b) the 67 non-SAS UNEXPLAINED response rows, (c) the 132 actor-call UNEXPLAINED rows that did not surface as response unexplained.
4. **GEDDocumentSkip cleanup** — Phase 8B recommended deleting or clarifying the dead-code/misleading docstring in `src/flat_ged/resolver.py:17`. Not required now.
5. **Optional UI snapshot layer** — Phase 8A.7 decision was KEEP ARCHITECTURE. Snapshot layer remains a future option if a refactor introduces new divergences.
6. **Optional rule-precedence reconciliation** — sheet 07 vs shadow classifier has a 31-row DUPLICATE_FAVORABLE_KEPT delta due to classifier precedence noise (not row loss).
7. **Optional `audit_counts_lineage.py` glob fix** — avoid picking up `~$GED_export.xlsx` Excel lock files.

These items can be reopened later as discrete, scoped tasks. None gate current release.

---

## ✅ CLOSED — Phase 8 Count Lineage Fix (fully closed 2026-04-30; reference only)

Phase 8 is read-only reference material. New work routes to **Phase 8A** (downstream hardening) and **Phase 8B** (upstream RAW → FLAT reconciliation + report integration) — see sections below.

**Final closure event 2026-04-30:** Windows-shell pytest pass over the four new test files and the audit script. **57 tests passed in 138.62s.** Audit one-liner verbatim:
```
AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match
```
All 10 baseline checks PASS. Cache-hit path fired (v2 cache from step-4 verification is current — no rebuild needed). D-012 verdict still PARTIAL_CONFIRMED. The remaining audit FAIL is the upstream D-011 SAS REF projection gap, intentionally not silenced — routed to Phase 8B.

Plan: `docs/implementation/PHASE_8_COUNT_LINEAGE_FIX.md` (closed; self-contained;
§18 = step 1 report, §19 = step 2 report, §20 = step 2.5 report,
§21 = step 3 report, §21.8 = step 3 vdate addendum, §22 = step 4 report,
§23 = step 5 report, §24 = step 6 report). Read-only after 2026-04-30.

### Phase 8 status

| Step | Status | Deliverable |
|---|---|---|
| 1. Audit harness | ✅ closed 2026-04-30 | `scripts/audit_counts_lineage.py`, `tests/test_audit_counts_lineage.py`, `output/debug/counts_lineage_audit.{xlsx,json}` |
| 2. Audit-the-audit (probe + reader fixes + baseline refresh) | ✅ closed 2026-04-30 | `--probe` mode, `output/debug/counts_lineage_probe.{xlsx,json}`, SAS REF reader fix, baseline 6155→6901 with provenance |
| 2.5. Apply D-1 + D-012 confirmation | ✅ closed 2026-04-30 | D-1 rule extended (workflow_step_count + sas_row_count); D-012 PARTIAL_CONFIRMED; FAIL 3→1 (only status_SAS_REF remains); 25 tests pass |
| 3. visa_global source fix | ✅ closed 2026-04-30 | `RunContext.flat_ged_doc_meta` field; `_load_from_flat_artifacts` passes through; `aggregator.resolve_visa_global` helper; 5 call sites replaced; vdate addendum preserves `avg_days_to_visa` |
| 4. Cache audit fields | ✅ closed 2026-04-30 | `CACHE_SCHEMA_VERSION` bumped `"v1"` → `"v2"`; `_save_flat_normalized_cache` writes 8 audit fields (sha256, mtime, docs_df_rows=4834, responses_df_rows=27237, active_version_count=4834, family_count=2819, status_counts populated, generated_at). Windows rebuild trace confirmed: `[FLAT_CACHE] Cache schema version mismatch (cache='v1' want='v2')` → 30s rebuild → `[FLAT_CACHE] Cache written (schema=v2)`. Audit one-liner `PASS=16 WARN=0 FAIL=1` unchanged. Cache_meta.json values cross-check against RunContext (4 invariants ✓). See §22 for full receipts. Note: Claude Code's step-4 report had two inaccuracies (claimed v2 bump that hadn't landed; claimed §22 appended that didn't exist) — both corrected from this chat via direct Edit. |
| 5. Chain+Onion source alignment (WARN-only) | ✅ closed 2026-04-30 | `_check_flat_ged_alignment` helper added to `src/chain_onion/source_loader.py` (line 199), invoked at line 332 immediately before `pd.read_excel`. Resolves latest registered FLAT_GED via `data_loader._resolve_latest_run` + `_get_artifact_path`. Writes `output/debug/chain_onion_source_check.json` per run. Logs `[CHAIN_ONION_SOURCE_CHECK] result=...`. WARN-only — wrapped in try/except, never raises. Verification run: `result=OK` (registered and using paths identical), `run_chain_onion.py` exit 0 in 105.7s sandbox, audit one-liner unchanged, 7/7 pytest passed. See §23. BLOCK-mode flip remains a separate later decision. |
| 6. UI payload verification | ✅ closed 2026-04-30 | `UI_PAYLOAD_FIELD_MAP` (20 entries, data-only) added to `scripts/audit_counts_lineage.py`. `_compare_ui_payload(...)` driver compares `compute_project_kpis` vs `adapt_overview` per audit run. Outputs: new `ui_payload_mismatches` sheet in `counts_lineage_audit.xlsx` + new `ui_payload_comparison` key in `counts_lineage_audit.json`. New stdout line `UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match`. Production source untouched. Existing audit one-liner byte-identical. 8 new tests. See §24. |
| 7. Run completion gate | deferred per plan | not in this phase |

### Step 2 probe summary (2026-04-30)
- 119 records covering L0..L6 × 17 categories; every non-null value has a classified `value_origin_type`.
- Zero hardcoded baseline literals masquerading as layer values (Phase 1 was already measuring; probe just made provenance explicit).
- SAS REF reader fixed: L0 = 836, L1 = 284, L2/L3/L4 = 282.
- `raw_submission_rows` baseline refreshed 6155 → 6901 with inline provenance (`input/GED_export.xlsx`, mtime `2026-04-22`, sheet `"Doc. sous workflow, x versions"`, rows 3..6903).

### Step 2.5 summary (2026-04-30)
- D-1 rule extension landed: `EXPECTED_DIVERGENCES.open_doc_vs_docs_df_sas_filter` now covers `workflow_step_count` (Δ −24) and `sas_row_count` (Δ −14) for L1→L2.
- Audit one-liner: `PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX`. The remaining FAIL is the real D-011 upstream gap, intentionally not silenced.
- D-012 verdict: **PARTIAL_CONFIRMED**. The 2-row L1→L2 SAS REF gap decomposes into two non-bug mechanisms:
  - `sas_filter_component=CONFIRMED`: pair `051020|A` (submittal_date 2025-04-07) excluded by `_apply_sas_filter_flat`, contributes 1 row.
  - `structural_component=PRESENT`: pair `152012|A` has 2 GED_RAW_FLAT SAS REF rows (multi-cycle SAS, one-row-per-step schema), normalised to 1 in RunContext, contributes 1 row.
- `pair_gap=1`, `sas_filter_explained_rows=1`, `structural_normalization_rows=1`, `structural_duplicate_pairs=["152012|A"]`. Receipts: `output/debug/sas_pre2026_confirmation.json`. 25 tests pass.

### Step 3 summary (2026-04-30)
- **Patch shape (production source):**
  - `RunContext` gains `flat_ged_doc_meta: dict = field(default_factory=dict)` in `src/reporting/data_loader.py`.
  - `_load_from_flat_artifacts` now passes `flat_doc_meta or {}` into the `RunContext(...)` constructor (one site).
  - `src/reporting/aggregator.py` gains `resolve_visa_global(ctx, doc_id)`. The helper prefers `ctx.flat_ged_doc_meta[doc_id]["visa_global"]` (authoritative per `FLAT_GED_CONTRACT`) and pulls `vdate` from `WorkflowEngine.compute_visa_global_with_date(doc_id)` because `flat_doc_meta` does not carry `visa_global_date` today.
  - All 5 direct call sites in aggregator.py now route through the helper: `compute_project_kpis`, `compute_monthly_timeseries`, `compute_weekly_timeseries`, `compute_consultant_summary`, `compute_contractor_summary`.
- **Audit one-liner:** `PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX` — unchanged. The remaining FAIL is the upstream D-011 SAS REF projection gap, intentionally not silenced.
- **KPI behaviour preserved.** WorkflowEngine and `flat_doc_meta` are in full agreement on `visa_global` for every doc in run 0, so no count-category shifted at L4. `avg_days_to_visa` was briefly broken by the original step-3 patch (helper returned `(visa, None)` and the date tile collapsed to null) — fixed in §21.8 addendum. Post-addendum: `avg_days_to_visa = 79.1`.
- **Snapshot retained for audit forensics:** `output/debug/counts_lineage_audit.PRE_STEP3.json` (transient — safe to delete after sign-off).
- **Pytest validation inconclusive in sandbox.** Three pytest invocations of `tests/test_resolve_visa_global.py` hung indefinitely in the Cowork Linux sandbox (probable cause: the import chain `reporting.aggregator → data_loader → workflow_engine → read_raw → normalize` blocks on cross-mount Windows reads when invoked through pytest). The 13 helper tests are structurally correct (pure unit tests, mocked engine, no real-data dependency); they need to be confirmed via a Windows shell run. See `context/11_TOOLING_HAZARDS.md` H-4. App smoke and the audit harness both PASS in the sandbox; the regression that the addendum fixed (`avg_days_to_visa = None` → `79.1`) was confirmed via direct `compute_project_kpis` invocation, not via pytest.

### Step 4 summary (2026-04-30)
- 8 audit fields ship in `output/intermediate/FLAT_GED_cache_meta.json` under `cache_schema_version: "v2"`. Cross-check vs. RunContext: docs_df_rows / responses_df_rows / active_version_count / family_count all match.
- Schema-version bump auto-rejected the v1 cache on the verification run, forcing a fresh ~30s Windows-shell rebuild that wrote the v2 cache. Trace captured verbatim in §22.2.
- Audit one-liner unchanged across the rebuild: `PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX`.
- **Trust-but-verify finding:** Claude Code's step-4 execution report claimed both `CACHE_SCHEMA_VERSION = "v2"` and `§22 appended`; chat-side verification showed the constant was still `"v1"` and §22 did not exist. Both were corrected from this chat via direct Edit tool. The 8-field payload extension that Claude Code did apply landed correctly. Recorded in §22 itself as a data point for future agent-driven phases. (Second time this has happened — the step-3 `(visa, None)` regression was the first.)

### Step 5 summary (2026-04-30)
- WARN-only Chain+Onion source alignment check landed in `src/chain_onion/source_loader.py` only (`+106` lines). Helper imports `_resolve_latest_run` and `_get_artifact_path` from `data_loader.py` (slight scope addition vs. the prompt; chosen to avoid hardcoding `run_number=0`).
- First production run: `result=OK`. The path source_loader is reading is the same canonical path registered in `run_memory.db` for the current run. `sha_match` skipped because paths are identical.
- Helper is fully defensive: try/except wrap, multiple `db_path` candidates, `UNDETERMINED` outcomes never raise, never block Chain+Onion. Validated: `run_chain_onion.py` exit 0 in 105.7s in sandbox, 7/7 pytest passed in 1.45s in sandbox (small mock-based tests don't trigger H-4), audit one-liner unchanged.
- Receipts schema deviation worth noting: prompt asked for `generated_at`, helper writes `checked_at`; missing `registered_mtime`/`using_mtime` advisory fields. Functionally fine — load-bearing fields (`result`, `registered_flat_ged_path`, `using_flat_ged_path`, `sha_match`, `reason`) are all present. Recorded for future schema cross-references.
- BLOCK-mode flip is a deliberate non-decision for now per §9.3 of the plan. Re-approve when there's confidence WARN runs produce no false positives across multiple pipeline cycles.

### Step 6 summary (2026-04-30)
- 20 UI_PAYLOAD_FIELD_MAP entries; 10 compared, 10 skipped (out-of-scope-by-design, not coverage gaps).
- Compared fields: 10/10 match. No `aggregator` ↔ `adapt_overview` divergence in current run.
- Skipped breakdown:
  - **Aggregator-only fields not on `adapt_overview` (7)**: `total_docs_all_indices`, `total_lots`, `discrepancies_count`, `docs_sas_ref_active`, `by_visa_global_pct`, `by_building`, `by_responsible`. May be exposed via other adapters (`adapt_consultants`, `adapt_contractors_list`) — out of scope for step 6's overview-only check.
  - **Intentional UI reshape (2)**: `by_visa_global.REF` and `by_visa_global.SAS REF` are merged by the adapter into `visa_flow.ref` (single bucket). 1:1 not possible; would require sum check as a follow-up.
  - **Conditional (1)**: `focus_stats` only populates when `focus_result` is active; the audit runs unfocused.
- Step 6 contract ("flag any field where `compute_project_kpis` and `adapt_overview` disagree on a value they BOTH expose") is satisfied. No follow-up Medium-risk decision triggered.
- Possible future enhancement (NOT a defect): widen the comparison to other adapter functions (`adapt_consultants`, `adapt_contractors_list`, `adapt_contractors_lookup`) to chase the 7 aggregator-only fields. Track separately if needed.

### Closed by Phase 8 steps 2 + 2.5 + 3 + 4 + 5 + 6

- **G-1, G-2** (workflow_step_count + sas_row_count not covered by SAS-filter rule) → CLOSED by D-1 rule extension in step 2.5.
- **G-3** (stale 6155 baseline) → updated to 6901 with provenance in `scripts/audit_counts_lineage.py` and `output/debug/counts_lineage_audit.json`.
- **G-4** (status_SAS_REF = 0) → reader bug, fixed. Real values are L0 = 836, L1 = 284, L2/L3/L4 = 282.
- **D-1** → APPLIED in step 2.5.
- **D-2** → APPLIED in step 2. Provenance captured.
- **D-3** → ANSWERED by step 2 reader fix and the new RAW→FLAT open item below. Not "no SAS REF this run"; the harness was simply not extracting them.
- **D-4, D-5, D-6** → resolved by step 1 (already noted).
- **D-012** → CLOSED FOR PHASE 8 (PARTIAL_CONFIRMED). Decomposition above. No production code change required; both mechanisms are documented behaviour.
- **G-5** → CLOSED by step 3. `flat_ged_doc_meta` now reaches `RunContext` and is consumed by `resolve_visa_global` at 5 aggregator sites.

### Routed onward (after Phase 8 closure)

| ID | Routed to | Why |
|---|---|---|
| **D-010** | Phase 8A | `_precompute_focus_columns` parallel `compute_visa_global_with_date` call site. MEDIUM risk; same pattern as Phase 8 step 3 in a different file. |
| **D-011** | Phase 8B | RAW 836 SAS REF → FLAT 284 SAS REF. Audit's only remaining FAIL. Lives upstream in `src/flat_ged/transformer.py` (do-not-touch list during Phase 8; becomes focus area in 8B). |
| **D-012** | ✅ closed by Phase 8 step 2.5 | PARTIAL_CONFIRMED. Decomposition: SAS pre-2026 filter excludes `051020\|A` (1 row) + RunContext normalises multi-cycle pair `152012\|A` from 2 rows to 1 (1 row). No production code change required. Evidence: `output/debug/sas_pre2026_confirmation.json`. |
| **G-5** | ✅ closed by Phase 8 step 3 | `flat_ged_doc_meta` now reaches `RunContext` and is consumed by `resolve_visa_global` at 5 aggregator sites. |
| **Step 5 BLOCK-mode flip** | Phase 8A | WARN-only landed clean in Phase 8 §23. Flip to BLOCK requires WARN-clean across at least one full pipeline cycle. |
| **Step 6 widened UI coverage** | Phase 8A | Extend `_compare_ui_payload` to walk `adapt_consultants` / `adapt_contractors_list` / `adapt_contractors_lookup`. Coverage deepening, not a defect. |

### Resumption path

**Phase 8 audit-side work is complete.** All in-scope steps (1, 2, 2.5,
3, 4, 5, 6) are closed. Only the deferred Step 7 remains, and it is
explicitly out of scope for this phase.

Phase 8 outcomes summary:
- Audit harness in production with provenance probe and 16-category
  cross-layer comparison.
- `raw_submission_rows` baseline refreshed (6155 → 6901 with provenance).
- SAS REF reader fixed at every layer.
- Aggregator now resolves `visa_global` from `flat_doc_meta`
  (authoritative source) with engine-vdate fallback.
- Cache schema bumped to v2 with 8 audit fields.
- Chain+Onion source alignment check (WARN-only) running per Chain+Onion run.
- UI payload comparison running per audit run, 10/10 matches.

Items carried forward — NOT Phase 8 work:
- **D-010** — parallel `_precompute_focus_columns` issue (separate ticket).
- **D-011** — RAW 836 → FLAT 284 SAS REF projection in `src/flat_ged/*`
  (separate ticket).
- **Step 5 BLOCK-mode flip** — separate later decision; flip after WARN
  has been clean across at least one full pipeline cycle that exercised
  registry writes.
- **Step 6 widened coverage** — possible future enhancement to compare
  against `adapt_consultants` / `adapt_contractors_list` /
  `adapt_contractors_lookup` to chase the 7 aggregator-only fields
  currently marked skipped. Not a defect.

Outstanding sandbox-only validation gaps — **all CLEARED 2026-04-30 by
single Windows-shell pytest pass: 57 tests passed in 138.62s.**
- Step 3: `tests/test_resolve_visa_global.py` — ✅ Windows-shell pass.
- Step 4: `tests/test_cache_meta_v2.py` — ✅ Windows-shell pass.
- Step 5: `tests/test_chain_onion_source_check.py` — ✅ already passed
  sandbox; Windows-shell pass confirmed.
- Step 6: new tests in `tests/test_audit_counts_lineage.py` — ✅
  Windows-shell pass.

Total Phase 8 test suite: 57 passing on Windows native.

---

## 🔜 NEXT — Phase 8A: Downstream Hardening (LOW audit steps closed 2026-05-01; MEDIUM steps gated)

Plan: `docs/implementation/PHASE_8A_DOWNSTREAM_HARDENING.md` (self-contained; charter received from project owner 2026-04-30; 7 steps).

Mission: harden every downstream consumer after FLAT_GED.xlsx is accepted as the operational source. Close D-010, promote Chain+Onion alignment from WARN to BLOCK on real content mismatches, widen the UI payload audit beyond Overview, and produce a UI metric inventory.

Scope:

| Step | Risk | Notes |
|---|---|---|
| **8A.1** D-010 focus-visa source audit | LOW | Read-only AST walk over `src/reporting/*` to enumerate every `compute_visa_global_with_date` call site. |
| **8A.2** D-010 patch | **MEDIUM** | New `src/reporting/visa_resolver.py` shared module (avoids the circular import that would arise if `data_loader.py` reached into `aggregator.py`). Routes both `aggregator.py` and `_precompute_focus_columns` through the same helper. Per-step approval required. |
| **8A.3** Chain+Onion BLOCK-readiness audit | LOW | Read-only check that the WARN-only check has been clean across a real pipeline cycle. |
| **8A.4** Chain+Onion BLOCK flip | **MEDIUM** | Promotes the alignment check from WARN to enforcement. Owner-approved policy: BLOCK only on `WARN_PATH_AND_CONTENT_MISMATCH` or `UNDETERMINED`. Per-step approval required. |
| **8A.5** UI metric inventory | LOW | Documentation only; produces `context/12_UI_METRIC_INVENTORY.md`. |
| **8A.6** Widened UI payload audit | LOW (audit-only) → MEDIUM if a true_bug surfaces | Extends Phase 8 §24's UI payload comparison from Overview-only to all UI surfaces in the inventory. |
| **8A.7** UI snapshot layer decision | LOW | Decision only; opens Phase 8C if 8A.6 proves the current architecture is brittle. |

**Pre-flight finding (locked):** `aggregator.py` imports `from .data_loader import RunContext`. A reverse import would deadlock startup. The `visa_resolver.py` module path is the only viable design — confirmed and locked in §8.1 of the plan.

Phase 8A entry point: hand the plan doc to a fresh agent. Suggested ship order: LOW first (8A.1, 8A.3, 8A.5 in any order), then MEDIUM after per-step approvals (8A.2, 8A.4, 8A.6), then 8A.7 as a closing decision. Same trust-but-verify discipline as Phase 8 (Read-tool spot-check after each Claude Code report).

---

## Phase 8A — Downstream Hardening Status

> Live status of the Phase 8A sub-steps. Updated 2026-05-01 after the LOW-risk batch (8A.1, 8A.3, 8A.5) closed. The "🔜 NEXT — Phase 8A" section above remains as the plan reference; this section carries the run-by-run state.

### 8A.1 — D-010 focus/visa source audit [CLOSED]

- Artifacts:
  - `scripts/audit_focus_visa_source.py`
  - `output/debug/focus_visa_source_audit.json`
  - `output/debug/focus_visa_source_audit.xlsx`
- Result:
  - `FOCUS_VISA_AUDIT: call_sites=10 direct_engine=8 via_resolver=2 disagreements_total=0`
  - Phase 8 audit unchanged:
    - `AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX`
    - `UI_PAYLOAD: compared=10 matches=10 mismatches=0`
- Material finding:
  D-010 scope is 8 direct WorkflowEngine visa call sites, not 1:
  - `data_loader.py`: `_precompute_focus_columns` (line 604)
  - `consultant_fiche.py`: `_has_visa_global` (line 1375)
  - `contractor_fiche.py`: 6 sites inside `build_contractor_fiche` using local variable `we` (lines 138, 175, 198, 226, 252, 317)
- Decision:
  Do not patch all 8 sites yet.
  Recommended sequence:
    1. Run 8A.6 widened UI payload audit first.
    2. Patch `_precompute_focus_columns` only in 8A.2.
    3. Open separate 8A.2b for `consultant_fiche.py` and `contractor_fiche.py` if 8A.6 proves visible impact.

### 8A.3 — Chain+Onion BLOCK-mode readiness audit [CLOSED, ready=false]

- Artifacts:
  - `scripts/check_chain_onion_alignment_block_ready.py`
  - `output/debug/chain_onion_block_readiness.json`
- Result:
  - `BLOCK_READINESS: ready=false`
  - Reason: latest pipeline run (2026-04-27) predates Chain+Onion WARN helper installation (2026-04-30).
- Action required before 8A.4:
  Run a fresh Windows-side full pipeline cycle:
    `python main.py`
  Then run:
    `python scripts/check_chain_onion_alignment_block_ready.py`
- Decision:
  Do not flip BLOCK mode yet.

### 8A.5 — UI metric inventory [CLOSED]

- Artifact:
  - `context/12_UI_METRIC_INVENTORY.md`
- Result:
  - 11 sections found:
    - 9 required UI pages
    - Shell / Sidebar & Focus pill (additional page discovered during walk)
    - Coverage Summary
  - Export panel documented as having 0 numeric rows.
- Next:
  Use this inventory as input to 8A.6 widened UI payload audit.

### 8A.6 — Widened UI payload audit [CLOSED 2026-05-01]

Audit script: `scripts/audit_ui_payload_full_surface.py`
Test file: `tests/test_ui_payload_full_surface.py` (13 tests, all pass)
Outputs: `output/debug/ui_payload_full_surface_audit.{json,xlsx}`

**Result verbatim:**
```
UI_PAYLOAD_FULL: surfaces=6 compared=45 matches=45 mismatches=0; OK - all compared fields match
```

Per-surface breakdown:
| Surface | Compared | Matches | Mismatches | Notes |
|---|---|---|---|---|
| consultants_list | 10 | 10 | 0 | 3 naming_only renames documented (docs_called→total, docs_answered→answered, open→pending) |
| contractors_list | 33 | 33 | 0 | 30 per-contractor pass_rate checks; 1 naming_only (total_submitted→docs), 1 scope_filter (≥5 filter) |
| consultant_fiche | 0 | 0 | 0 | build_consultant_fiche has no separate aggregator/adapter split — documented per spec §12.7 |
| contractor_fiche | 0 | 0 | 0 | build_contractor_fiche has no separate aggregator/adapter split — documented per spec §12.7 |
| dcc | 0 | 0 | 0 | DCC reads CHAIN_TIMELINE_ATTRIBUTION.json directly (2819 chain entries) — no split |
| chain_onion_panel | 2 | 2 | 0 | 4/4 inventory keys present in dashboard_summary.json; top_issues.json has 20 entries |

Classification breakdown: NM=0, SF=0, ESD=0, **TB=0**.
S1 baseline intact post-run: `AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX`
S7 app smoke: `app import OK`.

### 8A.7 — UI snapshot-layer decision [CLOSED 2026-05-01]

Decision rule (per spec §13): NM≤2 AND SF≤2 → **keep architecture**.

Inputs: NM=0, SF=0 → condition satisfied with wide margin.

**Decision: KEEP ARCHITECTURE. Phase 8C is NOT opened.**

Rationale: 45 field comparisons across 6 surfaces with 0 mismatches. The current
aggregator → adapter pipeline is internally consistent. No brittleness detected.
The naming_only renames (docs_called→total, docs_answered→answered, open→pending,
total_submitted→docs) and the scope_filter (≥5 contractor threshold) are stable and
documented. No snapshot layer is needed at this time.

Phase 8C remains available if a future refactor of the adapter layer creates new
divergences. Trigger: re-run 8A.6 and apply the decision rule again.

### Recommended next action

> **As of 2026-05-01: all items below are deferred backlog — see "Phase 8 family — closed for current release" at the top of this file. None are blockers for software finalisation.**

Do not proceed yet with (blocked/MEDIUM, deferred backlog):
- 8A.2 broad 8-site patch
- 8A.4 Chain+Onion BLOCK flip
- 8C RAW→FLAT cleanup

### Open items (Phase 8A) — deferred backlog

- **8A.2** — MEDIUM, gated: patch `_precompute_focus_columns` only. **(Deferred backlog — not a release blocker. `disagreements_total=0` per 8A.1.)**
- **8A.2b** — MEDIUM, separate future patch: `consultant_fiche.py` and `contractor_fiche.py` direct visa calls. **(Deferred backlog — not a release blocker.)**
- **8A.4** — MEDIUM, blocked until fresh pipeline run proves readiness. **(Deferred backlog — WARN-only is operational.)**
- ~~**8A.6**~~ ✅ CLOSED 2026-05-01. 45 fields, 0 mismatches.
- ~~**8A.7**~~ ✅ CLOSED 2026-05-01. Decision: keep architecture. Phase 8C not opened.
- **8C** — later, upstream unexplained RAW→FLAT cleanup. **(Future backlog only / NOT ACTIVE for current release.)**

---

## ✅ CLOSED — Phase 8B: Upstream RAW → FLAT Reconciliation + Report Integration (closed 2026-05-01)

Plan: `docs/implementation/PHASE_8B_RAW_TO_FLAT_RECONCILIATION.md` (closed; reference only). Final report: `output/debug/PHASE_8B_FINAL_REPORT.md`.

**Outcome (§17 decision gate): C — existing reason logic incomplete + partially incorrect.** Identity contract holds; SAS REF gap 99.3% explained; 6 SAS REF rows remain UNEXPLAINED (28xxx /A C1 cluster). Phase 8B closed for current release. Residual unexplained rows + GEDDocumentSkip cleanup are routed to future backlog (Phase 8C / not active).

Mission: prove every RAW GED event and every report event has a named destination — or a named reason for absence — in FLAT. Read-only investigation through 8B.9; production source under `src/flat_ged/*` becomes the focus area only after the §17 gate, with written approval.

Scope:

| Item | Step | Risk | Notes |
|---|---|---|---|
| **D-011** — RAW 836 SAS REF → FLAT 284 SAS REF (552-row drop) | 8B.5 (D-011 trace) | LOW (audit-only) → MEDIUM-HIGH at gate if patch needed | The audit's only remaining FAIL. Decomposition into the §5 explanation taxonomy is the headline target. |
| **Report integration trace** | 8B.8 | LOW (audit-only) → MEDIUM at gate if FLAT schema extension proposed | Records how `data/report_memory.db` reports would attach at the FLAT level with explicit confidence + provenance. The §17 gate decides whether reports stay downstream (current `effective_responses`) or move to FLAT. |
| **Existing reason logic audit** | 8B.7 | LOW (read-only) | Classify every existing exclusion / reason code in `src/flat_ged/*` as VALID / INVALID / MISSING / AMBIGUOUS. Do NOT modify reason code in this step. |
| **Shadow corrected FLAT model** | 8B.9 | LOW | Builds `output/debug/SHADOW_FLAT_GED_*` showing what FLAT would look like if all trace gaps were corrected. Never overwrites production FLAT. |
| **§17 Decision gate** | 8B.10 | n/a — checkpoint | Outcomes: A keep-current-builder / B controlled patch / C replace-reason-logic / D FLAT-schema-extension. Each outcome opens a separate sub-phase if pursued. |

10 steps total. Steps 8B.1 (RAW event extraction) and 8B.2 (FLAT event extraction) come first — they materialize both sides into a common event model so steps 8B.3 through 8B.9 can compare row-by-row.

Phase 8B entry point: hand the plan doc to a fresh agent, then ship one self-contained Claude Code prompt per step. Same trust-but-verify discipline as Phase 8 (Read-tool spot-check after each report).

---

## ✅ Phase 0 + Phase 7 — closed 2026-05-01

Phase 0 (backend audit) signed off 2026-04-29. Phase 7 (contractor quality fiche) shipped 2026-05-01 with 0 backend failures and 25/25 UI checklist items passing. See `docs/implementation/PHASE_7_REPORT.md`.

## V2 backlog — Phase 7 follow-ups

Carried forward, NOT blocking, owned outside Phase 7:

| Item | Source | Notes |
|---|---|---|
| Polar histogram visual polish | Step 12b smoke | "Still not pretty" per project owner; clearer scale + sector labels + palette ramp |
| Drilldowns from polar / long-chains / KPI tiles | Phase 7 §V2 | V1 only dormant queues drill; V2 should expand to chain-level drilldowns |
| Focus mode behavior on contractor fiche | Phase 7 Q4 | V1 shows "sans effet" notice; V2 should highlight/sort recent issues without filtering historical data |
| D-003 raw↔flat SAS REF gap | Phase 0 TRIAGE | Upstream rework; SNI raw ~184 vs flat 52 |
| D-006 AAI 1-row mystery | Phase 0 TRIAGE | Needs investigation |
| D-010 engine vs meta visa source spot-check | Phase 0 TRIAGE | Needs investigation |
| "Entreprise de la semaine" selection criteria | Phase 7 12b smoke | `ui_adapter.adapt_overview:125` — `(VSO+VAO)/total_submitted` is not the right taux de conformité per project owner |

---

## High-value, low-risk items (highest ROI for next fixes)

### 1. UI Contractors page — ✅ RESOLVED (Phase 5, 2026-04-29)

The Contractors page is live and Focus-aware. Phase 5 fixed the
"empty entreprise cards" bug (29 enriched cards now visible, was 5),
applied canonical names everywhere (BEN→Bentin, LGD→Legendre, …), and
added focus-aware KPI reorientation + a `P1·P2·P3·P4` mini-bar fed by
the new `OVERVIEW.focus.by_contractor` payload. See
`docs/implementation/PHASE_5_TAB_FOCUS_AWARENESS_AND_ENTREPRISE_FIX.md`.

**Still open:** `app.Api.get_contractor_fiche(contractor_code, …)` is
fully implemented in the backend but the UI does not yet render an
individual contractor fiche page on click — Phase 7 territory.

**Phase 5 residual — to re-analyse after Phase 6 closes:** the
"Maître d'Oeuvre EXE — GEMO" card in the Consultants tab still appears
to display all-time data when Focus mode is on, despite the Phase 5
headline-swap rule. Two plausible causes (need to confirm during
re-analysis, do not pre-fix):
- `c.focus_owned` for the MOEX consultant ≈ `c.total` because MOEX
  owns most actionable items at any given time, so the swap fires but
  is visually indistinguishable. If true, this is faithful to the data
  and not a bug — but the card may need a second visual cue (e.g.
  emphasize the À traiter label / colorize) to communicate the focus
  state.
- The swap is not firing at all on `MoexCard` specifically (e.g.
  `focusMode` not threading correctly to it, or the conditional
  rendering is shadowed by another StatBlock that dominates the card's
  visual weight). Inspect `ui/jansa/consultants.jsx:MoexCard` (KPI row
  ~lines 233–242) and the props passed by `ConsultantsPage`'s
  `moex.map` call.

Cross-check the data: in the focus-on payload, compare
`window.CONSULTANTS[i].focus_owned` and `.total` for canonical_name =
"Maître d'Oeuvre EXE". If they're equal, root cause is data, not UI.

Reason for deferral: Phase 6 (Intelligence layer) may add new
MOEX-specific KPI surfaces (`PHASE_6A`–`6D`) that change what the MOEX
card should display. Re-analysing after 6 avoids fixing twice.

### 2. Mapping file picker on Executer is dead

`ui/jansa/executer.jsx:277` self-labels the Mapping field as
`"informatif — non transmis au backend"`, and `app.Api.run_pipeline_async`
does not accept or forward a mapping path. Either remove the field or wire
it through `run_pipeline_controlled` (and follow the chain to
`normalize.load_mapping` to confirm what file it would consume).

### 3. Discrepancies / Settings pages are stubs

The pipeline writes `DISCREPANCY_REPORT.xlsx`,
`DISCREPANCY_REVIEW_REQUIRED.xlsx`, `RECONCILIATION_LOG.xlsx`, and
`IGNORED_ITEMS_LOG.xlsx` every run. None are surfaced. A read-only
"Discrepancies — review queue" page over `DISCREPANCY_REVIEW_REQUIRED.xlsx`
is purely additive.

### 4. Chain + Onion narratives + top issues — partially wired (2026-04-29)

`output/chain_onion/top_issues.json` and `dashboard_summary.json` are now
rendered in the dashboard's `ChainOnionPanel` (`ui/jansa/overview.jsx`)
via `app.Api.get_chain_onion_intel(20)` → `window.CHAIN_INTEL`. Synthèse
column is rendered in French (Phase 2, see
`docs/implementation/PHASE_2_DIRECT_NAV_AND_FRENCH.md` and
`context/06_EXCEPTIONS_AND_MAPPINGS.md` § K). Issue rows are clickable —
they open the Document Command Center (Phase 5 Mod 2).

**Still not surfaced:**
- `CHAIN_NARRATIVES.csv` per-chain detail (only the top 20 from
  `top_issues.json` are exposed).
- `primary_driver_fr` and `recommended_focus_fr` are present in the
  payload but not rendered — Phase 4 enrichment territory.
- `dashboard_summary` fields beyond what `ChainOnionPanel` already shows
  (live/escalated/avg_pressure pills + top theme).

---

## Architectural / connection gaps

### 5. Two registries, one decoupling

`output/chain_onion/*` is produced by `run_chain_onion.py` reading
`output/intermediate/FLAT_GED.xlsx` directly. It is **not** keyed by
`run_number` — if you regenerate intermediate without rerunning Chain+Onion,
your live UI Focus stats use stale chain data. Suggest either:
- have `stage_finalize_run` invoke chain_onion automatically, or
- register chain_onion outputs as artifacts in `run_memory.db` per run.

### 6. `paths.py` `FLAT_GED_MODE = "raw"` default is misleading

Anyone calling `pipeline.runner._run_pipeline_impl` without going through
the orchestrator will silently take the raw fallback path. The default
should match runtime behavior, OR the orchestrator should be the only
documented entrypoint. Decision needed.

### 7. `data_loader` legacy raw GED rebuild path

`data_loader.py` has a legacy raw GED rebuild fallback that fires when
`FLAT_GED` artifact is missing, logging `[LEGACY_RAW_FALLBACK]`. README
calls this "legacy fallback only" but the path is still in code. Verify
nothing real depends on it before retiring.

### 8. Two consultant mapping sources

`src/flat_ged/input/source_main/consultant_mapping.py:CANONICAL_TO_DISPLAY`
and `src/reporting/consultant_fiche.py:CONSULTANT_DISPLAY_NAMES` carry the
same map. They agree today. Pick one as authoritative and have the other
import it.

### 9. `team_version_builder.py` hardcoded paths

`team_version_builder.py` lines 13–17 hardcode:
```
OGF_PATH   = "input/Grandfichier_v3.xlsx"
CLEAN_PATH = "output/GF_V0_CLEAN.xlsx"
OUT_PATH   = "output/GF_TEAM_VERSION.xlsx"
```

Even though `paths.py` defines all three. Today this happens to be
consistent, but if a stage redirects (e.g. `_patched_main_context`) the
team builder won't follow. The stage already wraps it; verify the wrap
overrides via signature, not module globals.

### 10. Repo-root debug logs are uncontrolled

`run_a.log` … `run_f.log`, `step15_debug.log`, `pipeline_run.log`,
`fix_gf_schema_main.log`, `test1_main_no_baseline.log`, `test2_*.log`,
`run_e.log` (empty), all live at repo root. They look one-off but no
.gitignore rule nets them. Consider moving `*.log` outside the working
tree or adding to `.gitignore`.

---

## Probable bugs / smells (to be confirmed before action)

### 11. `_resolve_inherited_gf_record` walks a base computed from `data/`

```python
base_dir = Path(db_path).resolve().parent.parent  # data/run_memory.db → root
```

If `data/run_memory.db` is moved (e.g. to `data/sub/run_memory.db`), this
walk to root breaks silently. Low risk today, but worth a hardening pass.

### 12. `app.Api._build_live_operational_numeros` swallows exceptions

```python
except Exception as exc:
    print(exc)
    return None, 0
```

In a degraded state (chain_onion missing), prints to stdout and continues
without surfacing in the UI. Acceptable today (UI has fallback) but
emitting through the warnings list of the dashboard payload would help.

### 13. `consultant_match_report.xlsx` ingestion priority

`stage_report_memory` ingests this file each run. The artifact is also
registered each run, which means run N+1 ingests the file produced by
run N. Looks correct, but verify the dedup gate
(`is_report_already_ingested`) doesn't skip a file that was newly enriched
by reading it from a slightly different path.

### 14. `output/parity*` and `output/step9/legacy/` are dormant

No code path writes there in the active runtime. Safe to archive once
confirmed via `grep -r parity_raw_run src/`. (Confirmed empty in current
code.)

### 15. `runs/run_0000/` is the ONLY registered run

`data/run_memory.db` shows one row: `(0, 'COMPLETED', is_current=1, is_stale=0)`.
No `run_0001/` exists yet. The UI's `total_runs=1` matches. After the next
production run we should see `run_0001/` and the artifact registry should
grow to ~33 × 2 entries.

### 18. `run_chain_onion.py` Step 14 D19 validation harness exits 1

Verified 2026-04-28 (Phase 3 of DCC project, see
`docs/implementation/03_PHASE_3_REPORT.md` OQ-1).

`python run_chain_onion.py` exits with code 1 because Step 14 Validation
Harness check D19 prints "CRITICAL: D19 skipped: severity column missing"
and `sys.exit(1)` is reached. **All 10 expected artifacts (CHAIN_REGISTER.csv,
CHAIN_EVENTS.csv, CHAIN_VERSIONS.csv, CHAIN_METRICS.csv, ONION_LAYERS.csv,
ONION_SCORES.csv, CHAIN_NARRATIVES.csv, CHAIN_ONION_SUMMARY.xlsx,
dashboard_summary.json, top_issues.json) ARE written correctly** — 71/73
checks pass.

**Workaround in app.py (Phase 3 patch):** `_run_chain_onion_subprocess`
treats "exit code ≠ 0 BUT all required CSVs present" as `partial success`
and continues. So the auto-refresh path works regardless of this bug.

**Real fix (when convenient):** investigate D19 in chain_onion (likely
a missing column in CHAIN_NARRATIVES or ONION_SCORES that the harness
expected). Then chain_onion will exit 0 cleanly and the partial-success
fallback in app.py becomes dead code that can be removed.

---

### 17. `chain_timeline_attribution` UNKNOWN attribution edge cases — ✅ RESOLVED (Phase 5 Mod 4)

**Resolved 2026-04-29.** All 47 rows classified and addressed via manual worksheet + 4 code fixes.

**Resolution summary:**
- 26 rows → `DEAD` (abandoned/obsolete versions, attributed_days=0): listed in `context/dead_version_overrides.csv`
- 12 rows → `CONTRACTOR` (SAS issued CYCLE_REQUIRED REF; delay = max(0, review_end−sas_ref_date−15) capped at review_delay)
- 2 rows → focus-fallback resolved (136000_C → GEMO, 245502_D → AVLS)
- 4 rows → `NO_ATTRIBUTION` (3 MOEX-not-called, 1 within-tolerance 4-day review): listed in `context/dead_version_overrides.csv`
- 1 row → unchanged UNKNOWN (028245_C, 10 days, no issue identified)

**Code changes:** `src/reporting/chain_timeline_attribution.py` (5 fixes) + `context/dead_version_overrides.csv` (new, 30 entries).

**Verified 2026-04-29:** `CHAIN_TIMELINE_ATTRIBUTION.csv` regenerated. UNKNOWN=`['028245_C']`, DEAD unique keys=26, NO_ATTRIBUTION rows=4. ✓

---

### 16. `delay_contribution_days` ignores the 10-day secondary cap

Verified 2026-04-28 (Phase 1 of DCC project, see
`docs/implementation/01_PHASE_1_REPORT.md`).

`src/flat_ged/transformer.py:compute_delay_contribution` assigns delay
based on a single `cm_deadline` shared by all consultants regardless of
PRIMARY / SECONDARY tier. The 10-day window
(`focus_ownership.SECONDARY_WINDOW_DAYS=10`) is enforced only for
current-state ownership, not for historical attribution.

Empirical impact (current run):
- 7,851 SECONDARY rows with `delay_contribution_days > 10` (max 813d).
- `chain_metrics.secondary_wait_days` is over-attributed to secondary
  consultants.
- `onion_engine.py` scoring inputs (lines 491, 579, 668) consume the
  uncapped values; onion scores for chains with stale secondaries are
  likely inflated.

Phase 2 of the DCC project applies the cap inside the new
`reporting/chain_timeline_attribution.py` (read-only, doesn't modify
chain_onion). A separate HIGH-risk task would be needed to fix this at
the Flat GED transformer source if onion scoring needs correction.

---

## Disconnected data (present, not yet used)

| Asset | Purpose if connected |
|---|---|
| `output/chain_onion/CHAIN_NARRATIVES.csv` | Per-chain plain-language summary; could populate a "Top issues" UI panel. (Top 20 already surfaced via `top_issues.json` — this would expose the rest.) |
| `output/chain_onion/top_issues.json` | ✅ Wired 2026-04-29 — top 20 rendered in dashboard `ChainOnionPanel` via `Api.get_chain_onion_intel`, FR overlay applied (Phase 2). |
| `output/chain_onion/CHAIN_ONION_SUMMARY.xlsx` | Management workbook; useful for steering meetings. |
| `output/chain_onion/dashboard_summary.json` | Portfolio KPIs; complements `aggregator.compute_project_kpis`. |
| `MISSING_IN_GED_TRUE_ONLY.xlsx` / `MISSING_IN_GF_TRUE_ONLY.xlsx` | Curated review queues. |
| `INSERT_LOG.xlsx` | "What changed in GF this run?" — could feed a "Latest run diff" page. |
| `NEW_SUBMITTAL_ANALYSIS.xlsx` | New documents per family — useful for contractor performance. |
| `SUSPICIOUS_ROWS_REPORT.xlsx` | Rows the heuristics flagged. |
| `RECONCILIATION_LOG.xlsx` | Patch F fuzzy match decisions. |
| `consultant_match_report.xlsx` | Matched consultant rows; used by report_memory ingestion but not by UI. |

Several of these would benefit from a "Reports" page that lists them and
opens them via `open_file_in_explorer(path)` (the API already exists).

---

## Highest ROI first three fixes (ranking, not prescription)

1. **Wire the Contractors page** (#1). Pure frontend; backend has all the
   data. Big visible win.
2. ~~**Wire chain+onion priority into the UI** (#4).~~ ✅ Done 2026-04-29
   (Phase 2). `ChainOnionPanel` in `overview.jsx` renders the top 20 from
   `top_issues.json` with FR synthese. Remaining: per-chain narrative detail
   from `CHAIN_NARRATIVES.csv` is still un-surfaced.
3. **Decide the FLAT_GED_MODE default** (#6). This is a one-line change
   that reduces a foot-gun every time a developer calls the pipeline
   directly.

---

## Phase 3 residual (discovered 2026-04-28)

### D19 — `severity` column missing in chain_onion validation harness

`run_chain_onion.py` Step 14 (Validation Harness) checks for a `severity`
column that is not present in the current chain_onion output schema. This
causes check D19 to be skipped and the harness to exit with code 1 even
when all 10 artifacts are written correctly (71/73 checks pass).

**Workaround in place:** `app._run_chain_onion_subprocess` now detects the
partial-success case: if `returncode != 0` but all 3 required CSV files
exist, it logs "exit 1 but artifacts present — partial success" and
continues to chain_timeline refresh. Startup behavior is correct.

**Root fix needed:** Add the `severity` column to the chain_onion export
(likely in `src/chain_onion/exporter.py`) so the D19 check passes and the
harness exits 0. Low urgency — workaround fully covers startup path.

---

## Things that look risky but are working — leave alone

- The `main_module` namespace mutation in `run_orchestrator._patched_main_context`
  (it's intentional and documented).
- The flat_ged sys.path / sys.modules cleanup in `flat_ged/__init__.py`
  (prevents shadowing of `writer` and `config`).
- The `cache_ready.wait()` pattern in `Api.get_*_for_ui` (waits for
  pre-warm thread).
- The Babel-from-CDN approach in `jansa-connected.html` (works in pyWebView,
  no compile step needed).
