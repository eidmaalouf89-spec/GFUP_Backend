# GF Updater v3

Deterministic GED → GF reconstruction, enrichment, discrepancy analysis, run tracking, and JANSA desktop operations UI for the **17&CO Tranche 2** workflow.

This repository is not a generic Excel updater. It is a single-project operational engine that rebuilds a clean and traceable Grand Fichier from unstable chantier inputs while preserving consultant truth, run history, lineage, and artifacts across executions.

---

## Phase 8 family — release status (2026-05-01)

| Phase | Status |
|---|---|
| **Phase 8 — Count Lineage Fix** | ✅ CLOSED |
| **Phase 8A — Downstream Hardening** | ✅ CLOSED FOR CURRENT RELEASE (LOW-risk audits closed 2026-05-01; MEDIUM-risk hardening deferred) |
| **Phase 8B — RAW → FLAT GED Reconciliation** | ✅ CLOSED (Outcome C; identity contract passed; SAS REF gap 99.3% explained) |
| **Phase 8C — Future optional cleanup** | ⏸ FUTURE BACKLOG ONLY / NOT ACTIVE |

The remaining Phase 8-family items (D-010 broad WorkflowEngine cleanup, Chain+Onion BLOCK-mode flip, the 6 SAS REF UNEXPLAINED rows, the 67 non-SAS UNEXPLAINED response rows, the 132 actor-call UNEXPLAINED rows, GEDDocumentSkip cleanup, optional UI snapshot layer, optional audit glob lock-file fix) are backlog / hardening / forensic items and are **not blockers for software finalisation**. See `context/07_OPEN_ITEMS.md` for the full list.

**Current priority:** product finalisation, app stabilisation, final delivery items.

---

## Phase 0 — Backend Data Audit (completed 2026-04-29)

**Status:** ✅ Completed and signed-off 2026-04-29 by project owner. Phase 7 (contractor quality fiche) resumed and shipped 2026-05-01 — see next section. Audit harness (8 scripts under `scripts/audit/`) and findings (`docs/audit/DIVERGENCE_REPORT.md`, `TRIAGE.md`, `SIGN_OFF.md`) remain in repo for future re-runs.

**Why we paused.** Phase 7's visual smoke surfaced a series of data integrity issues that revealed a systemic gap: there is no test harness comparing numbers across pipeline stages. Specifically:

- A stale `FLAT_GED_cache_resp.pkl` silently served zero SAS-track rows for an unknown duration. The cache freshness check uses file mtime only — schema drift in upstream code is invisible to consumers.
- `WorkflowEngine.__init__` filters `is_exception_approver == True`, which strips ALL SAS rows from `ctx.workflow_engine.responses_df` while leaving them in `ctx.responses_df`. Two attributes named the same way return different data sets.
- SNI SAS REF count diverged across three sources: 0 (cached/stale), 52 (fresh flat_ged via `ctx.responses_df`), ~184 (operator's count from raw GED). Three numbers, three sources, no validation.
- Contractor AMP showed `share_contractor_in_long_chains = 199 %` in the long-chains panel — mathematically impossible. Suspected double-count after the dormant-time extension landed in `_contractor_delay_for_chain` (numerator now includes dormant time; the denominator from `chain.totals.delay_days` does not).
- A separate raw GED ↔ flat GED discrepancy was noted by the project owner during smoke; details are parked in his personal notes.

**What Phase 0 will do.** End-to-end audit of every UI-visible number, tracing it back through `reporting → cache → flat_ged → raw_ged + reports`. Output: a permanent verification harness under `scripts/audit/` plus a divergence report and triage record. The full plan is `docs/implementation/PHASE_0_BACKEND_DEBUGGING.md` — it is standalone and can be executed in a fresh chat.

**Where Phase 7 stopped.** All wiring (Steps 1–10), backend module (Steps 4 + 4b), backend metric corrections (Steps 12a + 12a-fix2), and UI labels/tooltips/copy (Step 12b) have shipped. The contractor quality fiche is reachable, navigable, and renders. Its numbers are simply not yet certified. The remaining Phase 7 step (11b — phase report + final context updates + plan-file cleanup) is paused until Phase 0 sign-off.

**What stays untouched during Phase 0.**
- All UI files (`ui/jansa/contractor_fiche_page.jsx`, `shell.jsx`, `overview.jsx`, `contractors.jsx`, `data_bridge.js`, `jansa-connected.html`)
- `app.py` UI methods
- All pipeline stages
- `src/reporting/contractor_quality.py` business logic (audit only; patches in Phase 0 step 0.6 only for triage "fix-now" items)
- `docs/implementation/PHASE_7_CONTRACTOR_QUALITY_FICHE.md` (still the active plan)

**Green-light criteria to resume Phase 7** (verbatim from `PHASE_0_BACKEND_DEBUGGING.md` §12):
1. Cache schema versioning landed (`CACHE_SCHEMA_VERSION` constant + freshness check on it).
2. AMP 199 % fixed (or explicitly documented as expected with mathematical reasoning).
3. Raw↔flat SAS REF gap addressed (closed, OR documented with an upstream remediation ticket).
4. `docs/audit/DIVERGENCE_REPORT.md` complete: all 29 contractors × 8 metrics audited.
5. All "fix-now" TRIAGE items closed; relevant audit scripts converge.
6. Context docs (`02_DATA_FLOW.md`, `06_EXCEPTIONS_AND_MAPPINGS.md`, `07_OPEN_ITEMS.md`, `11_TOOLING_HAZARDS.md`) updated.
7. `docs/audit/SIGN_OFF.md` signed by the project owner.

**Resumption path.** Once §12 is green: Phase 7 resumes at Step 11a (re-run UI smoke checklist with corrected backend numbers), then Step 11b (report + final context + plan-file cleanup).

**Outcome.** All 7 green-light criteria met (3 fix-now items closed: cache-version mechanism, AMP 199 % long-chains share fix, chain attribution artifact regeneration with atomic-write hardening). 3 items deferred with rationale (D-003 raw↔flat SAS REF gap → upstream rework; D-006 AAI 1-row mystery → investigation; D-010 engine vs meta visa source → investigation). See `docs/audit/SIGN_OFF.md` for the full checklist.

---

## Phase 7 — Contractor Quality Fiche (completed 2026-05-01)

**Status:** ✅ Shipped. Per-contractor quality fiche live on the JANSA UI. Reachable from the dashboard "Entreprise de la semaine" card and from any enriched contractor card on the Contractors tab.

**What's live.** Header (canonical name, code, lots, buildings, "Documents Actifs") · 5-tile KPI strip with peer bands (Taux SAS REF historique · REF dormants · Chaînes > 120 j · Délai moyen entreprise · Taux SUS SOCOTEC) and React-popover ⓘ formula tooltips · 12-sector polar histogram of contractor-attributed delay per chain (with sub-10-day footer count) · long-chains panel · open/finished chains card · two dormant queues (REF + SAS REF) drilling into the existing Document Command Center · focus-mode notice (focus behavior deferred to V2).

**Backend.** New sibling module `src/reporting/contractor_quality.py`. Existing `contractor_fiche.py` untouched. Wrapper `app.py::get_contractor_fiche_for_ui` (line 1070) delegates to the original builder for header data + lots/buildings, then merges quality payload under `payload.quality`. Bridge: `loadContractorFiche` populates `window.CONTRACTOR_FICHE_DATA`.

**Documentation.** `docs/implementation/PHASE_7_REPORT.md` is the canonical record. The two plan files (`PHASE_7_CONTRACTOR_FICHE_WIRING.md`, `PHASE_7_CONTRACTOR_QUALITY_FICHE.md`) are kept for audit and clearly marked SUPERSEDED/CLOSED.

**V2 backlog.** Polar visual polish · drilldowns from polar/long-chains/KPI tiles · focus mode behavior on contractor fiche · 3 Phase 0 deferred items (D-003, D-006, D-010) · "Entreprise de la semaine" selection criteria. See `context/07_OPEN_ITEMS.md` "V2 backlog" section and `docs/implementation/PHASE_7_REPORT.md` §7.

---

## Phase 3 — Dashboard Drilldowns (completed 2026-05-01)

**Status:** ✅ Shipped. Backend wired via recovery cycle 2026-05-01. Every Overview interaction (KPI tile, VisaFlow segment, WeeklyActivity bar, Focus radial ring) opens a backend-driven drilldown drawer with rows and a row-click hand-off to the Document Command Center.

**What's live.** `Api.get_documents_drilldown(kind, params, focus, stale_days)` exposed on the `Api` class; delegates to `reporting.drilldown_builder.build_drilldown` (which had been authored in Phase 3 but never wired). Validated 2026-05-01: Documents soumis (4834), Bloquants en attente (3723), VisaFlow REF (320), WeeklyActivity bin (107), Focus P1 (3093) — all return rows. Row click opens DCC.

**Backend.** Single new method on `Api` in `app.py`. Focus-handling mirrors `get_dashboard_data` (FocusConfig + `apply_focus_filter` + `_build_live_operational_numeros` + `_apply_live_narrowing`). `drilldown_builder.py` was already on disk — no source changes there. JS bridge (`data_bridge.js:loadDrilldown`) was already correct. Drawer (`overview.jsx:DrilldownDrawer`) was already correct.

**Documentation.** `docs/implementation/PHASE_3_DRILLDOWNS.md` (closure stamp added). `context/02_DATA_FLOW.md` "Dashboard drilldown lane". `context/03_UI_FEED_MAP.md` updated with the new endpoint row.

**Optional polish.** Widen the Focus radial click target — current 9px arc with `pointerEvents:'stroke'` is precision-dependent. Switch to `pointerEvents:'visiblePainted'` on the parent `<g>` or add a clickable legend row. UI-only; LOW risk.

---

## Phase 4 — Chain+Onion Priority Table Enrichment (completed 2026-05-01)

**Status:** ✅ Shipped. Émetteur (canonical company name) and Titre (raw PDF filename) appended to every record in `output/chain_onion/top_issues.json` and surfaced in the Overview dashboard's Chain+Onion priority table.

**What's live.** `top_issues.json` carries 14 fields per record — the 11 original keys plus `emetteur_code`, `emetteur_name`, `titre` appended at export. `ChainOnionPanel` in `overview.jsx` extended from 6 to 8 columns (Émetteur and Titre between Numéro and Urgence). Ellipsis truncation; `title=` tooltip on the Titre cell. Row click → DCC preserved. LGD → "Legendre", BEN → "Bentin", etc. via the canonical `resolve_emetteur_name` helper.

**Backend.** `run_chain_onion.py` passes `issue_meta_df=ops_df` into `export_chain_onion_outputs`. Inside `_build_top_issues`, the join uses `chain_register_df.latest_version_key` to pick the latest `(emetteur, titre)` per family; documented sort+drop_duplicates fallback if `latest_version_key` is unavailable. Exporter remains pure — no Excel/CSV/parquet reads inside. CSV schemas unchanged.

**Bonus fix shipped alongside.** `validation_harness._load_csv` previously read identity columns with default dtype inference, casting `family_key`/`numero` to int64 and stripping leading zeros (e.g. `045080 → 45080`). Phase 4's new cross-reference exposed this latent bug as a false F32 failure. Fix: `pd.read_csv(path, ..., dtype={"family_key": str, "numero": str, "version_key": str})`. F32 now passes; harness status WARN for the pre-existing H38 escalation ratio only.

**Known warning (out of scope).** H38 — `escalated_chain_count=2453 > 25% of live_chains=1968`. Pre-existing; would need operational review of the escalation-trigger thresholds in `onion_scoring.py` if pursued.

**Documentation.** `docs/implementation/PHASE_4_CHAIN_ONION_TABLE_ENRICHMENT.md` (closure stamp added). `context/02_DATA_FLOW.md` Phase 4 enrichment paragraph + harness fix note. `context/05_OUTPUT_ARTIFACTS.md` `top_issues.json` field shape. `context/06_EXCEPTIONS_AND_MAPPINGS.md` `chain_onion.exporter._build_top_issues` added to the `resolve_emetteur_name` consumer list. `context/07_OPEN_ITEMS.md` Item 4 closure note.

---

## Implementation status (as of 2026-05-01)

Phases 0, 1, 2, 3, 4, 5, 7 are shipped. Phase 8 family is closed for the current release. The only remaining major implementation work is **Phase 6** — the Intelligence layer. Sub-plans `PHASE_6A_INTELLIGENCE_ARTIFACT.md`, `PHASE_6B_INTELLIGENCE_ENDPOINTS.md`, `PHASE_6C_INTELLIGENCE_UI_PAGE.md`, `PHASE_6D_INTELLIGENCE_EXPORT_AND_TREATED.md` exist but are unimplemented. This is the next "killer module" work-stream.

---

## Phase 8 — Count Lineage Fix (closed 2026-04-30 — read-only reference)

**Status:** ✅ Fully closed 2026-04-30. Steps 1 + 2 + 2.5 + 3 + 4 + 5 + 6 shipped and Windows-shell verified end-to-end. **57 Phase 8 tests passing on Windows native** (`pytest tests/test_resolve_visa_global.py tests/test_cache_meta_v2.py tests/test_chain_onion_source_check.py tests/test_audit_counts_lineage.py -q` → 57 passed in 138.62s). Final audit lines verbatim: `AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX` and `UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match`. The remaining audit FAIL is the upstream D-011 SAS REF projection gap, intentionally not silenced. Step 7 (Run completion gate) is deferred per the plan.

**Carry-forward routing.** Phase 8 carry-forward items are split into two new buckets, neither yet opened:
- **Phase 8A — Downstream Hardening:** D-010 (route `_precompute_focus_columns` through `resolve_visa_global`), Step 5 BLOCK-mode flip (after WARN-clean across a full pipeline cycle), Step 6 widened UI coverage (chase the 7 aggregator-only fields into `adapt_consultants` / `adapt_contractors_list` / `adapt_contractors_lookup`).
- **Phase 8B — Upstream RAW → FLAT Reconciliation + Report Integration:** D-011 (RAW 836 → FLAT 284 SAS REF projection in `src/flat_ged/transformer.py`) plus operator-facing report integration of the audit lineage / probe / D-012 receipts.

Bucket assignments live in `context/07_OPEN_ITEMS.md`. Plan documents for 8A and 8B are next-session work. The Phase 8 plan doc (`docs/implementation/PHASE_8_COUNT_LINEAGE_FIX.md`) is now read-only reference material — do not continue implementation inside it.

**Step 3 in one line:** the aggregator now resolves `visa_global` from `RunContext.flat_ged_doc_meta` (authoritative per `FLAT_GED_CONTRACT`) instead of recomputing it via `WorkflowEngine.compute_visa_global_with_date`. Date is still pulled from WorkflowEngine because `flat_doc_meta` does not carry `visa_global_date`. KPI behaviour preserved end-to-end (`avg_days_to_visa = 79.1`, no count-category shifts at L4 because the two sources happened to agree on every doc in run 0). The patch is preventative: any future doc whose engine recomputation would diverge from the meta now resolves to the meta.

**Step 4 in one line:** `CACHE_SCHEMA_VERSION` bumped `"v1"` → `"v2"`; `_save_flat_normalized_cache` now writes 8 audit fields into `FLAT_GED_cache_meta.json` (sha256, mtime, docs_df_rows=4834, responses_df_rows=27237, active_version_count=4834, family_count=2819, status_counts populated, generated_at). Schema bump auto-rejected the v1 cache on the verification run, forcing a fresh ~30s Windows-shell rebuild that wrote a clean v2 cache. Audit one-liner unchanged across the rebuild. Cross-check vs. RunContext: 4 invariants ✓. Reader untouched (already tolerates extra keys). Full receipts in §22 of `docs/implementation/PHASE_8_COUNT_LINEAGE_FIX.md`.

**Step 5 in one line:** `_check_flat_ged_alignment` helper added to `src/chain_onion/source_loader.py` (line 199, invoked at line 332 immediately before the existing `pd.read_excel`). Resolves the latest registered FLAT_GED via `data_loader._resolve_latest_run` + `_get_artifact_path`, compares against the path Chain+Onion is reading, and writes `output/debug/chain_onion_source_check.json` per run with a one-line `[CHAIN_ONION_SOURCE_CHECK] result=...` log. WARN-only — wrapped in try/except, never raises, never blocks Chain+Onion. First production run: `result=OK` (registered and using paths identical), `run_chain_onion.py` exit 0, audit one-liner unchanged. BLOCK-mode flip is a separate later decision. Full receipts in §23.

**Step 6 in one line:** UI payload verification block added to `scripts/audit_counts_lineage.py` (no production source touched). 20-entry `UI_PAYLOAD_FIELD_MAP` declared as data; `_compare_ui_payload` driver runs per audit and compares `compute_project_kpis` vs `adapt_overview` field-by-field. Outputs: new `ui_payload_mismatches` xlsx sheet + `ui_payload_comparison` block in JSON + new `UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match` stdout line below the existing AUDIT one-liner. The 10 skipped entries are out-of-scope-by-design (7 aggregator-only fields not on `adapt_overview`, 2 intentional REF/SAS_REF merge in adapter, 1 conditional focus_stats). 10/10 compared fields match — no aggregator/adapter divergence in current run. Full receipts in §24.

**Phase 8 outcome summary.** Audit harness in production with provenance probe and 16-category cross-layer comparison. RAW baseline refreshed with provenance. SAS REF reader fixed. Aggregator routes `visa_global` through `flat_doc_meta` (authoritative source) with engine-vdate fallback. Cache schema bumped to v2 with 8 audit fields. Chain+Onion source alignment WARN-check running per run. UI payload check running per audit. Outstanding: Windows-shell pytest pass for the 4 new test files (mechanical), plus separate D-010 / D-011 / step-5-BLOCK-flip tickets carried forward outside Phase 8.

**Why.** UI numbers, aggregator KPIs, RunContext, FLAT_GED.xlsx, and Chain+Onion outputs disagree in places, and there was no harness comparing them across layers. Phase 8 built that harness FIRST (read-only, writes only to `output/debug/`); the next steps apply the smallest patches needed to make the audit pass — visa_global source mismatch, cache audit fields, and Chain+Onion source alignment.

**Audit one-liner after step 2.5:** `PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX`. The single remaining FAIL is the real RAW→FLAT SAS REF projection gap (D-011), intentionally not silenced — it is upstream of Phase 8 and on the do-not-touch list.

**Deliverables on disk after step 2.5.**
- `scripts/audit_counts_lineage.py` (~1869 lines) — compares L0_RAW_GED → L1_FLAT_GED_XLSX → L2_STAGE_READ_FLAT → L3_RUNCONTEXT_CACHE → L4_AGGREGATOR → L5_UI_ADAPTER → L6_CHAIN_ONION. Default run plus `--probe` provenance mode plus the D-012 confirmation helper baked into every run.
- `tests/test_audit_counts_lineage.py` (~452 lines) — 25 tests, all passing.
- `output/debug/counts_lineage_audit.{xlsx,json}` — default audit output. `expected_baselines.raw_submission_rows` carries inline provenance after the step-2 baseline refresh (6155 → 6901, source `input/GED_export.xlsx` mtime 2026-04-22).
- `output/debug/counts_lineage_probe.{xlsx,json}` — 119 records covering L0..L6 × 17 categories, each tagged with `value_origin_type` so every reported number traces to a measured source, a computed dataframe, or a baseline literal. No hidden hardcoded layer values.
- `output/debug/sas_pre2026_confirmation.json` — D-012 receipts. The L1→L2 SAS REF 2-row gap decomposes into two non-bug mechanisms: (1) SAS pre-2026 filter excludes pair `051020|A` (1 row), (2) RunContext normalises the multi-cycle pair `152012|A` from 2 rows to 1 (1 row). Verdict: `PARTIAL_CONFIRMED`. Both are documented behaviour.

**SAS REF reader fix landed in step 2.** Real values are now: L0 = 836, L1 = 284, L2/L3/L4 = 282 (previously reported 0 across the board). The 836 → 284 RAW → FLAT drop is a separate upstream open item (D-011 in `07_OPEN_ITEMS.md`) — `src/flat_ged/*` is on the do-not-touch list during Phase 8.

**Plan.** `docs/implementation/PHASE_8_COUNT_LINEAGE_FIX.md` is self-contained. §17 lists open questions; §18 = step-1 execution report; §19 = step-2 execution report; §20 = step-2.5 execution report.

**What stays untouched.** No production source modified by steps 1, 2, or 2.5. Step 3 (visa_global), step 5 (Chain+Onion alignment in BLOCK mode), and step 6 (ui_adapter rename) all require explicit re-approval and only land via the Edit tool — never via in-place bash rewrites (see `context/11_TOOLING_HAZARDS.md` H-1.1).

**Validation.** `python scripts/audit_counts_lineage.py` (default) or `--probe` (provenance). Detailed in `context/10_VALIDATION_COMMANDS.md` §L.

---

## Quick Start

1. Place source files in `input/`:
   - `GED_export.xlsx` (required)
   - `Grandfichier_v3.xlsx` (optional — inherited from run history if absent)
   - `consultant_reports/` (optional PDFs)

2. Run the pipeline:
   ```bash
   python main.py
   ```

3. View outputs in `output/`:
   - `GF_V0_CLEAN.xlsx`, `GF_TEAM_VERSION.xlsx`, reports
   - Run history in `runs/`

4. Launch the desktop UI:
   ```bash
   python app.py
   ```

---

## Gate Status

| Gate | Description | Status |
|---|---|---|
| Gate 1 | Read Path Parity (raw vs flat, REAL_DIVERGENCE = 0) | ✅ PASS |
| Gate 2 | Logical GF Fidelity (REAL_REGRESSION = 0) | ✅ PASS |
| Gate 3 | UI Parity (REAL_DIVERGENCE = 0, 242 checks) | ✅ PASS |
| Clean Steps 1–16 | Repo health → hardening validation | ✅ COMPLETE |
| Chain + Onion Steps 04–14 | Portfolio intelligence layer — built and validated | ✅ COMPLETE |
| G1 — Final Acceptance Gate | Live portfolio run against real output artifacts | ⏳ PENDING |

**Next active phase:** G1 live run confirmation → Clean Step 17

---

## Current State Snapshot

**Backend status:** Stabilized staged pipeline with automatic Flat GED build. `main.py` is the pipeline entrypoint, `src/run_orchestrator.py` controls execution. Flat GED is auto-generated from raw GED on every run — users never need to provide `FLAT_GED.xlsx`.

**Flat GED mode:** The orchestrator automatically builds Flat GED into `output/intermediate/` and sets `FLAT_GED_MODE = "flat"` before each run. Developer raw-mode fallback available via `GFUP_FORCE_RAW=1` environment variable.

**UI loader:** Artifact-first. `data_loader.py` loads from registered FLAT_GED artifact by default. Raw GED rebuild is legacy fallback only (logged as `[LEGACY_RAW_FALLBACK]`).

**GF_TEAM_VERSION:** Auto-generated by `stage_build_team_version.py` with retry + fallback. Registered as run artifact. UI export via `export_team_version()`.

**Production UI:** `app.py` launches the JANSA connected desktop UI via `ui/jansa-connected.html`. Old Vite UI files are legacy/reference only.

**Tabs Focus parity (Phase 5, 2026-04-29):** Consultants and Contractors tabs reorient their card KPIs around `focus_owned` ("À traiter") when Focus mode is active, with the all-time total kept as a smaller secondary slot, and a 4-segment `P1·P2·P3·P4` mini-bar under each card. The Contractors tab now displays all 29 eligible emetteurs (≥5 docs) with canonical company names — Bentin, Legendre, SNIE, etc. — instead of the previous top-5-by-pass-rate slice.

**Clean IO phase:** Steps 1–12 complete. Filesystem productization done — `paths.py` is the single source of truth for all directory constants.

---

## What This Repository Is

GF Updater v3 is a local, single-user, single-project operational system that:

- reads a raw GED export
- builds a Flat GED internal artifact (normalized operational layer)
- rebuilds a clean Grand Fichier from Flat GED + report memory
- compares GED and GF to detect discrepancies
- persists consultant-report truth across runs
- persists run history, artifacts, lineage, baseline state, and stale propagation
- exposes operational workflows through the JANSA desktop UI

It is intentionally:

- single project: **17&CO Tranche 2**
- local / single-user
- not SaaS
- not multi-tenant
- not a generic multi-project framework

---

## Source-Of-Truth Hierarchy

| Rank | Layer | Role |
|---|---|---|
| 1 | Raw GED dump (`input/GED_export.xlsx`) | Primary operational truth for document identity, workflow rows, mission calling, lifecycle structure |
| 2 | Flat GED (`output/intermediate/FLAT_GED.xlsx`) | Normalized operational layer auto-generated from raw GED on each run |
| 3 | `report_memory.db` | Persistent secondary consultant truth. Once matched, consultant answers survive future runs without re-importing reports |
| 4 | `effective_responses_df` | Composed response truth: GED_OPERATIONS rows left-joined with eligible report_memory enrichment |
| 5 | `GF_V0_CLEAN.xlsx` | Reconstructed GF output — not source of truth |
| 6 | `GF_TEAM_VERSION.xlsx` | Protected team-facing export — derived from GF_V0_CLEAN, registered as run artifact |
| 7 | UI | Presentation layer only |

GF is a reconstruction target. It is not the source of truth. Never treat the GF as authoritative for document identity or workflow state.

> **Note — `Mapping.xlsx`:** The UI exposes a mapping-file picker, but `run_pipeline_async` in `app.py` does not currently pass the selection to the pipeline. `Mapping.xlsx` is informational only at this time (see `executer.jsx:277` and `app.py:run_pipeline_async`).

---

## Remaining Temporary Layers

- `FLAT_GED_MODE = "raw"` default in `paths.py` — overridden to `"flat"` by orchestrator at runtime. Default not yet flipped to avoid breaking scripts that import paths.py directly.
- `stage_read_flat.py` carries `TEMPORARY_COMPAT_LAYER` markers — cosmetic, to be cleaned in a future step.
- Legacy raw GED rebuild path in `data_loader.py` — fallback only, fires when FLAT_GED artifact missing.

---

## What Not To Touch

Do not modify, rename, move, or delete the following without an explicit step targeting that asset:

- `src/flat_ged/` — frozen builder snapshot; business logic must not be changed
- `src/report_memory.py` — persistent project memory
- `src/run_memory.py` — persistent artifact registry
- `src/team_version_builder.py` — team export builder
- `src/effective_responses.py` — effective response composer
- `src/pipeline/stages/stage_report_memory.py` — report memory composition
- `src/pipeline/stages/stage_finalize_run.py` — registers GF_TEAM_VERSION artifact
- `app.py → export_team_version()` — UI API for team export
- `output/GF_TEAM_VERSION.xlsx` — required team output
- `ui/jansa-connected.html` — production UI entry point
- `ui/jansa/` (all files) — production UI component library
- `runs/run_0000/` — immutable baseline artifacts
- `data/report_memory.db` — persistent consultant memory (1,245 active rows)
- `data/run_memory.db` — run artifact registry

---

## Runtime Entrypoints

Pipeline:

```bash
python main.py
```

Desktop app:

```bash
python app.py
```

`python app.py` resolves exactly one production UI path:

```text
ui/jansa-connected.html
```

There is no production fallback to `ui/dist/index.html` or a Vite dev server. See `docs/UI_RUNTIME_ARCHITECTURE.md`.

**Browser mode (`--browser` flag):** `python app.py --browser` opens the same HTML in the system default browser. The PyWebView JS bridge is unavailable in this mode — `data_bridge.js` times out after 5 seconds and renders placeholder data only. No backend calls succeed. Use only for CSS/layout development; it does not show real project data.

---

## Folder Structure

```text
input/                          User-provided source files only
  GED_export.xlsx                 Raw GED dump
  Grandfichier_v3.xlsx            GF source/template
  consultant_reports/             PDF consultant reports

output/                         Latest user-facing deliverables
  GF_V0_CLEAN.xlsx                Reconstructed GF
  GF_TEAM_VERSION.xlsx            Team export
  Tableau de suivi de visa *.xlsx Dated team export copy
  DISCREPANCY_REPORT.xlsx         ...and other reports
  intermediate/                 Generated internal artifacts (not user-facing)
    FLAT_GED.xlsx                 Auto-generated from GED
    DEBUG_TRACE.csv               Builder debug output
    flat_ged_run_report.json      Builder run metadata
    CHAIN_TIMELINE_ATTRIBUTION.json  Per-chain delay attribution (refreshed at app startup; not in run_memory.db)
    CHAIN_TIMELINE_ATTRIBUTION.csv   Same data, tabular form
  chain_onion/                  Chain + Onion portfolio intelligence outputs (produced by run_chain_onion.py; NOT registered as run-keyed artifacts in run_memory.db)
    CHAIN_REGISTER.csv            One row per family
    CHAIN_VERSIONS.csv            All document versions
    CHAIN_EVENTS.csv              Full event timeline
    CHAIN_METRICS.csv             Staleness and pressure metrics
    ONION_LAYERS.csv              Per-layer evidence rows
    ONION_SCORES.csv              Chain-level scores and ranks
    CHAIN_NARRATIVES.csv          Management summaries
    dashboard_summary.json        Portfolio KPI snapshot
    top_issues.json               Top 20 priority chains
    CHAIN_ONION_SUMMARY.xlsx      11-sheet management workbook
  debug/                        Debug outputs
  exports/                      Run bundle exports

runs/                           Immutable run history
  run_0000/                       Baseline
  run_0001/                       ...subsequent runs

data/                           Persistent state
  run_memory.db                   Run/artifact registry
  report_memory.db                Consultant report memory

src/                            Source code
  pipeline/                       Staged pipeline engine
  flat_ged/                       Frozen builder snapshot (DO NOT MODIFY)
  reporting/                      UI data adapters
  chain_onion/                    Chain + Onion portfolio intelligence layer
    source_loader.py                Step 04 — source file loader
    family_grouper.py               Step 05 — family grouper
    chain_builder.py                Step 06 — timeline builder
    chain_classifier.py             Step 07 — state / bucket classifier
    chain_metrics.py                Step 08 — pressure and staleness metrics
    onion_engine.py                 Step 09 — per-layer evidence builder
    onion_scoring.py                Step 10 — chain-level impact scoring
    narrative_engine.py             Step 11 — management narrative generator
    exporter.py                     Step 12 — CSV / JSON / XLSX export engine
    query_hooks.py                  Step 13 — 26 query functions (QueryContext)
    validation_harness.py           Step 14 — 40-check acceptance harness
  ...

ui/                             User interface
  jansa-connected.html            Production entrypoint
  jansa/                          Production UI components

docs/                           Documentation
context/                        Living operational repo map — machine-readable maps (software_tree.json, module_dependency_map.csv, ui_endpoint_map.csv) and runtime/data-flow docs used for maintenance and AI-assisted development
scripts/                        Developer tools
```

---

## Chain + Onion Portfolio Intelligence Layer

The Chain + Onion system is an analytical backend built on top of the GED pipeline. It groups document families into **chains** (one logical file = one chain across all its versions and events), scores each chain by operational impact through a layered **Onion** model, generates management narratives, and exports a complete portfolio intelligence package.

It is entirely read-only relative to the GED pipeline — it consumes finalized pipeline outputs and does not modify any source data.

### What a Chain Is

A **chain** is the full lifecycle of one administrative file across all its GED versions, consultant reports, SAS decisions, and MOEX interventions. Every document submitted, revised, rejected, corrected, or approved belongs to a single chain identified by `family_key`.

### What the Onion Is

The **Onion** is a six-layer impact scoring model. Each layer represents a distinct source of operational friction:

| Layer | Code | Theme |
|-------|------|-------|
| L1 | Contractor quality issues | `contractor_impact_score` |
| L2 | SAS gate friction | `sas_impact_score` |
| L3 | Primary consultant delay | `consultant_primary_impact_score` |
| L4 | Secondary consultant delay | `consultant_secondary_impact_score` |
| L5 | MOEX arbitration delay | `moex_impact_score` |
| L6 | Data / report contradiction | `contradiction_impact_score` |

Each layer is scored by: `severity_weight × confidence_factor × pressure_factor × recency_factor × evidence_factor`. Layer scores sum to a `total_onion_score` normalized to `normalized_score_100` (0–100). Chains are ranked by `action_priority_rank` (rank 1 = most operationally impacted).

### Module Map (`src/chain_onion/`)

| Module | Step | Role |
|--------|------|------|
| `source_loader.py` | 04 | Loads GED, consultant report, and SAS source files |
| `family_grouper.py` | 05 | Groups all GED rows into families by document identity |
| `chain_builder.py` | 06 | Builds timeline events per family |
| `chain_classifier.py` | 07 | Assigns `current_state` and `portfolio_bucket` to each chain |
| `chain_metrics.py` | 08 | Computes `stale_days`, pressure index, activity dates |
| `onion_engine.py` | 09 | Builds per-layer evidence rows (`ONION_LAYERS`) |
| `onion_scoring.py` | 10 | Aggregates layer scores into chain-level `ONION_SCORES` |
| `narrative_engine.py` | 11 | Generates neutral management summaries (`CHAIN_NARRATIVES`) |
| `exporter.py` | 12 | Exports all artifacts to `output/chain_onion/` |
| `query_hooks.py` | 13 | 26 query functions over `QueryContext` for UI / dashboard use |
| `validation_harness.py` | 14 | 40-check acceptance harness for system integrity |

### Portfolio Buckets

Every chain is assigned exactly one `portfolio_bucket`:

| Bucket | Meaning |
|--------|---------|
| `LIVE_OPERATIONAL` | Active chains with open workflow steps |
| `LEGACY_BACKLOG` | Old open chains with no recent activity |
| `ARCHIVED_HISTORICAL` | Terminal chains (closed, void, or dead at SAS) |

Terminal states: `CLOSED_VAO`, `CLOSED_VSO`, `VOID_CHAIN`, `DEAD_AT_SAS_A`.

### Output Artifacts (`output/chain_onion/`)

| Artifact | Description |
|----------|-------------|
| `CHAIN_REGISTER.csv` | One row per family — identity and state |
| `CHAIN_VERSIONS.csv` | All document versions per family |
| `CHAIN_EVENTS.csv` | Full timeline of events per family |
| `CHAIN_METRICS.csv` | Pressure index, stale days, activity dates |
| `ONION_LAYERS.csv` | Per-layer evidence rows |
| `ONION_SCORES.csv` | Chain-level scores, ranks, escalation flags |
| `CHAIN_NARRATIVES.csv` | Management summaries with urgency/confidence labels |
| `dashboard_summary.json` | Portfolio KPI snapshot (totals, ratios, top theme) |
| `top_issues.json` | Top 20 chains by `action_priority_rank`; each record includes `emetteur_code`, `emetteur_name`, `titre` sourced from in-memory `ops_df` via `chain_register_df.latest_version_key` |
| `CHAIN_ONION_SUMMARY.xlsx` | 11-sheet management workbook |

### Running the Chain + Onion Layer

The system is invoked after a full pipeline run. All required inputs are read from `output/chain_onion/` or passed as in-memory DataFrames.

**Validation only (no pipeline re-run):**
```python
from src.chain_onion.validation_harness import run_chain_onion_validation
report = run_chain_onion_validation(output_dir="output/chain_onion")
print(report["status"])  # PASS / WARN / FAIL
```

**Query hooks (UI / dashboard):**
```python
from src.chain_onion.query_hooks import QueryContext, get_top_issues, get_live_operational
ctx = QueryContext(output_dir="output/chain_onion")
top = get_top_issues(ctx, limit=20)
live = get_live_operational(ctx)
```

### Validation Harness (Step 14)

`run_chain_onion_validation()` runs 40 checks across 8 categories and returns a structured report:

```
status          PASS / WARN / FAIL
total_checks    64
passed_checks   ...
warning_checks  ...
failed_checks   ...
critical_failures  [list of FAIL messages]
warnings           [list of WARN messages]
portfolio_snapshot {total_chains, live_chains, legacy_chains, archived_chains, ...}
```

Quality signals that trigger WARN (not FAIL):
- `dormant_ghost_ratio > 0.50` — high archive proportion
- Escalated chains > 25% of live chains
- Zero-score chains > 40% of all chains
- Contradiction rows > 10% of all chains

**Test suite:** `tests/test_validation_harness.py` — 47 passed, 1 skipped (live run).

---

## Document Command Center

The Document Command Center (DCC) is a search and inspection panel embedded in the JANSA UI. Backend: `src/reporting/document_command_center.py`. Frontend: `ui/jansa/document_panel.jsx`.

**Search mode:** full-text search over `dernier_df` — `numero`, `titre`, `emetteur`, `lot`, `indice`. Returns a ranked list of matching documents.

**Document panel — 7 sections:**

| Section | Content |
|---|---|
| Header | Document identity and latest status |
| Responses | All workflow responses for the selected indice |
| Comments | Decisive responses with associated comments |
| Revision history | All indices for the same family |
| Chronologie | Chain timeline with delay attribution (from `CHAIN_TIMELINE_ATTRIBUTION.json`) |
| Tags | Primary ownership tag + secondary signal tags |
| Warnings | Data quality flags |

**Tag taxonomy:**
- Primary (exactly one per document): `Att Entreprise — Dans les délais`, `Att Entreprise — Hors délais`, `Att BET Primaire`, `Att BET Secondaire`, `Att MOEX — Facile`, `Att MOEX — Arbitrage`, `Clos / Visé`
- Secondary (multi-valued, optional): `Refus multiples`, `Commentaire manquant`, `Secondaire expiré`, `Très ancien`, `Cycle dépassé`, `Chaîne longue`

All tag computation is in the backend. The frontend renders backend payload without business logic.

**API endpoints:**

| Endpoint | Purpose |
|---|---|
| `search_documents(query, focus, stale_days, limit)` | Full-text search; returns match list |
| `get_document_command_center(numero, indice, focus, stale_days)` | Full panel payload including chronologie |
| `get_chain_timeline(numero)` | Standalone chain timeline endpoint |

Triggered from any JANSA page via `window.openDocumentCommandCenter(numero, indice)`.

---

## Contractors Page

`ui/jansa/contractors.jsx` is an active JANSA page populated at UI init by `get_contractors_for_ui`. The bridge populates:

- `window.CONTRACTORS_LIST` — top-N enriched contractors with KPIs (doc count, pass rate)
- `window.CONTRACTORS` — full code→name lookup for all emetteurs

The page renders enriched KPI cards for contractors with ≥5 documents and plain name chips for all others.

**Not yet wired:** `get_contractor_fiche` exists in `src/reporting/contractor_fiche.py` but the bridge call from the UI is not wired. Contractor fiche drill-down is a future step.

---

## Chain Timeline Attribution

`src/reporting/chain_timeline_attribution.py` reads Chain + Onion CSV outputs (`CHAIN_EVENTS`, `CHAIN_REGISTER`, `CHAIN_VERSIONS`) and produces per-chain timing and delay responsibility data for every document family.

It applies a secondary consultant delay cap (10 days) not present in the raw chain_onion outputs and re-attributes excess delay to synthetic `MOEX_CAP_REATTRIBUTED` rows. The original chain_onion CSVs are never modified.

**Output artifacts** (written to `output/intermediate/`, not registered in `run_memory.db`):

| Artifact | Content |
|---|---|
| `CHAIN_TIMELINE_ATTRIBUTION.json` | Structured per-chain attribution: `family_key`, `numero`, `totals`, `chain_long`, `cycle_depasse`, `attribution_breakdown` |
| `CHAIN_TIMELINE_ATTRIBUTION.csv` | Same data, tabular form |

These artifacts are refreshed at desktop app startup inside `app.py`'s `_prewarm_cache` thread. The DCC chronologie section and the `Cycle dépassé` / `Chaîne longue` secondary tags consume this data.

---

## Backend Architecture

```text
main.py
  -> src/run_orchestrator.py
    -> src/flat_ged_runner.py (auto-builds FLAT_GED)
  -> src/pipeline/stages/*
  -> output/
  -> runs/
  -> data/run_memory.db
  -> data/report_memory.db
```

Pipeline stage order:

1. `stage_init_run`
2. `stage_read_flat` (default flat path) / `stage_read` (raw fallback via GFUP_FORCE_RAW=1)
3. `stage_normalize`
4. `stage_version`
5. `stage_route`
6. `stage_report_memory`
7. `stage_write_gf`
8. `stage_build_team_version`
9. `stage_discrepancy`
10. `stage_diagnosis`
11. `stage_finalize_run`

Important modules:

- `src/run_orchestrator.py` — controlled execution, modes, inherited GF resolution
- `src/pipeline/context.py` — shared `PipelineState`
- `src/pipeline/stages/` — ordered execution stages
- `src/domain/` — deterministic business helpers
- `src/run_memory.py` — run history and artifacts
- `src/report_memory.py` — persisted consultant truth
- `src/query_library.py` — 22-function query API over Flat GED context (Step 9c)
- `src/effective_responses.py` — effective response composer (report_memory + GED)
- `src/reporting/` — JANSA/reporting data adapters, fiche builders, Document Command Center, Chain Timeline Attribution
- `src/reporting/document_command_center.py` — `search_documents` + `build_document_command_center`; sole source of tag computation and panel payload for the DCC
- `src/reporting/chain_timeline_attribution.py` — per-chain timing and delay attribution; reads chain_onion CSVs; writes `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.{json,csv}`

---

## JANSA UI Architecture

Production UI flow:

```text
backend reporting data
  -> src/reporting/* adapters
  -> app.py pywebview API methods
  -> ui/jansa/data_bridge.js
  -> ui/jansa/*.jsx
  -> ui/jansa-connected.html
```

Validated JANSA areas:

- Focus mode
- Overview
- Consultants list
- Consultant fiche
- Drilldowns
- Drilldown exports
- Contractors page (active — enriched KPI cards for top contractors + chip list for all others; fiche drill-down not yet wired)
- Document Command Center (search by numero / titre / lot / emetteur; document panel with 7 sections; triggered via `window.openDocumentCommandCenter`)
- Runs page
- Executer page
- Utilities / stale-days selector / reports export

Active UI modules (`ui/jansa/`):

| File | Role |
|---|---|
| `shell.jsx` | App root, sidebar/topbar/router |
| `overview.jsx` | Dashboard KPIs |
| `consultants.jsx` | Consultants list (3-tier) |
| `fiche_base.jsx` | Fiche layout primitives + DrilldownDrawer |
| `fiche_page.jsx` | Consultant fiche wrapper |
| `contractors.jsx` | Contractors page — enriched cards + chip list |
| `document_panel.jsx` | Document Command Center drawer (search mode + doc mode) |
| `runs.jsx` | Run history page |
| `executer.jsx` | Pipeline launcher |
| `data_bridge.js` | PyWebView bridge; populates `window.OVERVIEW/CONSULTANTS/CONTRACTORS/FICHE_DATA` |
| `tokens.js` | JANSA design tokens (fonts/theme) |

Old Vite UI files under `ui/src/`, `ui/index.html`, and generated `ui/dist/` output are archival/reference only.

---

## Execution Modes

Supported orchestrated modes:

- `GED_ONLY` — user provides GED; GF is inherited from latest valid completed run or Run 0
- `GED_GF` — user provides GED + GF
- `GED_REPORT` — user provides GED + reports; GF is inherited
- `FULL` — GED + reports + GF, directly or inherited when resolvable

If the user does not provide a GF, inherited GF resolution is:

1. latest completed non-stale run with a valid `FINAL_GF` artifact
2. Run 0 `FINAL_GF`
3. clear failure if no usable GF exists

---

## Inputs

User-provided operational inputs in `input/`:

- `input/GED_export.xlsx` — raw GED dump (required)
- `input/Grandfichier_v3.xlsx` — GF source/template (optional; inherited from run history if absent)
- `input/consultant_reports/` — PDF consultant reports (optional)

`FLAT_GED.xlsx` is NOT a user input. It is auto-generated into `output/intermediate/` by the pipeline.

Do not delete `data/report_memory.db` casually. It is persistent project memory.

---

## Outputs And Artifacts

Outputs live under `output/` and are mirrored into `runs/run_NNNN/`.

Core artifacts include:

- `GF_V0_CLEAN.xlsx`
- `GF_TEAM_VERSION.xlsx`
- `DISCREPANCY_REPORT.xlsx`
- `DISCREPANCY_REVIEW_REQUIRED.xlsx`
- `ANOMALY_REPORT.xlsx`
- `AUTO_RESOLUTION_LOG.xlsx`
- `IGNORED_ITEMS_LOG.xlsx`
- `INSERT_LOG.xlsx`
- `RECONCILIATION_LOG.xlsx`
- diagnosis and new-submittal reports
- run/report memory snapshots
- debug artifacts

The JANSA UI exposes **Tableau de Suivi VISA** export from Overview, consultant fiche pages, and Reports. It copies the registered run artifact to:

```text
output/Tableau de suivi de visa DD_MM_YYYY.xlsx
```

---

## Validation

Backend validation and UI validation are different layers.

Backend/pipeline changes must validate against `docs/VALIDATION_BASELINE.md`.

Current Run 0 baseline: fresh post-reset FULL run created on 2026-04-22 from `input/`, with `report_memory.db` rebuilt from `input/consultant_reports`.

| Metric | Value |
|---|---:|
| docs_total | 6491 |
| responses_total | 31586 |
| responses_cells_total | 545244 |
| final_gf_rows | 4728 |
| `discrepancies_count` | 3221 |
| `discrepancies_review_required` | 18 |
| `reconciliation_events` | 172 |
| `artifacts_registered_count` | 30 |
| `consultant_report_memory_rows_loaded` | 1245 |

JANSA UI/runtime changes must validate against:

- `docs/UI_RUNTIME_ARCHITECTURE.md`
- relevant `docs/JANSA_PARITY_STEP_*.md`
- `docs/JANSA_FINAL_AUDIT.md`

---

## Working Rules

Never:

- treat GF as primary truth
- overwrite GED raw data
- delete `report_memory.db` casually
- bypass `run_orchestrator.py`
- change stage order casually
- silently change output filenames or artifact contracts
- reintroduce dual-UI runtime selection
- place `FLAT_GED.xlsx` in `input/` — it is auto-generated into `output/intermediate/`

Always:

- preserve deterministic behavior
- preserve traceability
- respect Run 0 as baseline
- keep backend and JANSA validation layers distinct
- prefer scoped changes over broad rewrites
- update docs when runtime, architecture, or validation truth changes

---

## Documentation Map

### Active Truth (use these for development decisions)

- `docs/ARCHITECTURE.md` — current and target backend/UI architecture, including Flat GED model
- `docs/RUNTIME_SOURCE_OF_TRUTH.md` — layer-by-layer source-of-truth map *(new, Step 3)*
- `docs/CLEAN_INPUT_OUTPUT_TARGET.md` — target IO contract and what must not happen *(new, Step 3)*
- `docs/CLEAN_IO_CONTRACT.md` — full IO contract: folder zones, artifact matrix, naming rules, lifecycle, Gate 4 acceptance *(new, Step 4)*
- `docs/UI_RUNTIME_ARCHITECTURE.md` — single production UI runtime policy
- `docs/VALIDATION_BASELINE.md` — pipeline regression baseline
- `docs/DEVELOPMENT_RULES.md` — scoped development and validation discipline
- `docs/FLAT_GED_CONTRACT.md` — canonical column contract for Flat GED (v1.0)
- `docs/BACKEND_SEMANTIC_CONTRACT.md` — 8 semantic concepts and Phase 2 decisions
- `docs/FLAT_GED_ADAPTER_MAP.md` — `stage_read_flat` adapter mapping (Step 4)
- `docs/FLAT_GED_REPORT_COMPOSITION.md` — composition spec: report_memory + GED enrichment rules
- `docs/QUERY_LIBRARY_SPEC.md` — 22-function query API spec (Step 9c)
- `docs/UI_SOURCE_OF_TRUTH_MAP.md` — maps every UI element to its data source (Step 10)
- `docs/CLEAN_BASE_REPO_HEALTH_AUDIT.md` — Step 1 health audit output
- `docs/ACTIVE_FILE_INVENTORY.md` — Step 2 file classification inventory
- `docs/CLAUDE.md` — Claude working context
- `docs/CODEX.md` — Codex review context
- `docs/FLAT_BUILDER_INTEGRATION_AUDIT.md` — Step 5 builder runtime audit
- `docs/TEAM_GF_PRESERVATION_AUDIT.md` — Step 9 team export chain audit
- `docs/UI_LOADER_PRODUCTIZATION_AUDIT.md` — Step 10 UI loader audit
- `docs/CLEAN_IO_FINALIZATION_REPORT.md` — Step 12 IO finalization report
- `GFUP_STEP_TRACKER.md` — step execution tracker (Gates 1–3 + Clean Steps 1–12)
- `docs/CHAIN_ONION_STEP_TRACKER.md` — Chain + Onion step tracker (Steps 04–14, G1)
- `docs/CHAIN_ONION_MASTER_STRATEGY.md` — Chain + Onion design strategy and data contracts
- `docs/CHAIN_ONION_ACCEPTANCE.md` — Step 14 executive acceptance report
- `docs/STEP04_VALIDATION.md` through `docs/STEP14_VALIDATION.md` — per-step validation records for the Chain + Onion system

### Archive / Historical Validation Records

- `docs/GED_ENTRY_AUDIT.md` — Step 3: gap matrix between raw GED and flat GED
- `docs/REPORTS_INGESTION_AUDIT.md` — Step 6: report ingestion audit
- `docs/STEP8_IMPLEMENTATION_NOTES.md` — Step 8 implementation notes
- `docs/CLEAN_GF_DIFF_SUMMARY.md` — Step 9: GF diff summary (REAL_REGRESSION=0)
- `docs/UI_PARITY_SUMMARY.md` — Step 11: UI parity results (REAL_DIVERGENCE=0)
- `docs/JANSA_PARITY_STEP_*.md` — per-step JANSA parity validation records
- `docs/STEP7_IMPLEMENTATION_NOTES.md` — Step 7 auto-build wiring notes
- `docs/STEP9B_TEAM_GF_WIRING_NOTES.md` — Step 9b team version pipeline wiring
- `docs/STEP9C_TEAM_GF_HARDENING_NOTES.md` — Step 9c retry/fallback hardening
- `docs/STEP11_UI_ARTIFACT_LOADER_NOTES.md` — Step 11 artifact-first loader notes

---

## Mental Model

This codebase is:

> A deterministic reconstruction and enrichment engine with persistent project memory, validated staged execution, automatic Flat GED normalization, artifact-first UI loading, a production JANSA desktop UI runtime, and a Chain + Onion portfolio intelligence layer that scores, ranks, and narrates the full operational state of every active document chain.

It is not just an Excel updater, report parser, reconciliation script, or temporary chantier utility.
