# REPORTS_INGESTION_AUDIT.md

**Step 6 — Reports Ingestion Audit**
Plan: FLAT_GED_INTEGRATION_EXECUTION_PLAN_v2.md
Date: 2026-04-24
Status: COMPLETE (read-only audit)

---

## 1. Executive Summary

Report memory is a **real, load-bearing enrichment layer** that is active in every pipeline run. It is not trivial, not chaotic, but it is **structurally split across two independent merge paths** that can produce different results for the same (doc_id, approver) pair — with no reconciliation between them.

**What it is:**
`report_memory.db` is a SQLite database that stores consultant-reported answers (status + date + comment) matched to GED document IDs. It was populated from 85 historical PDF report batches covering 1,245 (consultant, doc_id) pairs. When a GED row is `PENDING`, the pipeline upgrades it to `ANSWERED` using the persisted report data. GED-`ANSWERED` rows are **never touched** by the main pipeline merge.

**How important is it?**
It is the mechanism by which hundreds of consultant responses that exist in PDF form — but not yet back-propagated into GED — enter the final GF output. Without it, those rows remain `PENDING` in the output even though they have real answers.

**Primary / Secondary / Chaotic?**
The `report_memory.db` path inside the main pipeline is **well-designed**: GED is the structural anchor, reports are a fill-in-the-gaps enrichment, and ANSWERED GED rows are protected. However, a **second independent merge path** (`bet_report_merger`) runs exclusively in the UI data-loader (`reporting/data_loader.py`) and bypasses the pipeline entirely. This creates a **UI/pipeline truth split** — the main GF file and the UI dashboard can show different answers for the same document. Additionally, `consultant_gf_writer.py` can write report data directly to GF Excel cells as a **third path**, completely outside run history tracking.

The overall system is: **primary and coherent in the pipeline, but fragmented at the UI and direct-write layers.**

---

## 2. Storage Inventory

| Store | Type | Location | Purpose | Active? | Notes |
|---|---|---|---|---|---|
| `report_memory.db` | SQLite | `data/report_memory.db` | Persistent consultant response cache | **YES** | Production DB; primary report truth store. NOTE: production file is malformed — use run snapshot copy. |
| `run_memory.db` | SQLite | `data/run_memory.db` | Run registry, artifact provenance, correction log | **YES** | Does NOT store report content; only tracks that report_memory.db was used (via snapshot hash) |
| Per-run `report_memory.db` snapshot | SQLite | `runs/run_NNNN/report_memory.db` | Point-in-time copy of report_memory.db for each run | **YES** | Registered in run_artifacts as `REPORT_MEMORY_DB`. The run_0000 copy (1,245 rows, 85 reports) is clean. |
| `consultant_match_report.xlsx` | Excel | `output/consultant_match_report.xlsx` | Intermediate: matched consultant rows → GED doc_ids | **YES** | Primary ingestion source for report_memory. Produced by `consultant_integration.py`. |
| `consultant_reports.xlsx` | Excel | `output/consultant_reports.xlsx` (and `output/repports output/`) | Pre-matched per-consultant rows from PDF parse | **YES** | Feed for `bet_report_merger` in UI. Also produced by `consultant_integration.py`. |
| `GF_consultant_enriched_stage1.xlsx` | Excel | `output/GF_consultant_enriched_stage1.xlsx` | GF with consultant DATE+STATUT written directly | CONDITIONAL | Produced only when `consultant_integration.py` runs. Not in main pipeline. |
| `GF_consultant_enriched_stage2.xlsx` | Excel | `output/GF_consultant_enriched_stage2.xlsx` | GF with consultant DATE+STATUT+OBSERVATIONS | CONDITIONAL | Same. Third independent write path. |

**Confirmed live data in `runs/run_0000/report_memory.db`:**
- `ingested_reports`: 85 rows (all AVLS batch reports, ingested 2026-04-22)
- `persisted_report_responses`: 1,245 rows (is_active=1)
- By consultant: SOCOTEC 449, ACOUSTICIEN AVLS 432, BET STR-TERRELL 193, AMO HQE LE SOMMER 171
- Status distribution: VAO 552, FAV 282, VSO 130, SUS 108, DEF 59, REF 53, VAOB 35, HM 26

---

## 3. Ingestion Paths

### Path 1 — bootstrap_report_memory.py (manual seed)

- **File:** `scripts/bootstrap_report_memory.py`
- **Function:** `run_bootstrap()` → `_bootstrap_from_match_report()`
- **Trigger:** Manual CLI execution: `python scripts/bootstrap_report_memory.py`
- **Source input:** `output/consultant_match_report.xlsx`
- **Expected columns consumed:** `Rapport ID`, `Consultant Source`, `Matched GED doc_id`, `STATUT_NORM`, `DATE_FICHE`, `COMMENTAIRE`, `Confidence`, `Match Method`
- **Output written:** `data/report_memory.db` (tables: `ingested_reports`, `persisted_report_responses`)
- **Hash strategy:** SHA-256 of the actual PDF if found under `input/consultant_reports/`; falls back to sentinel `BOOTSTRAP::<rapport_id>` if PDF not present.
- **Deduplication gate:** `is_report_already_ingested()` checks `source_file_hash` in `ingested_reports` before writing. Same hash → skip entirely.
- **Confidence:** HIGH — clean, well-documented, idempotent.

### Path 2 — stage_report_memory (pipeline auto-ingest)

- **File:** `src/pipeline/stages/stage_report_memory.py`
- **Function:** `stage_report_memory(ctx, log)`
- **Trigger:** Called automatically by `pipeline/runner.py` on every pipeline run (after stage_route, before stage_write_gf)
- **Source input:** `CONSULTANT_MATCH_REPORT` path (ctx) → same `consultant_match_report.xlsx`
- **Expected columns consumed:** same as Path 1 (`Rapport ID`, `Consultant Source`, `Matched GED doc_id`, `STATUT_NORM`, `DATE_FICHE`, `COMMENTAIRE`, `Confidence`, `Match Method`)
- **Output written:** `REPORT_MEMORY_DB` (ctx path), then `ctx.effective_responses_df` (the merged result used by all downstream stages)
- **Hash strategy:** identical to Path 1 (real SHA-256 or sentinel)
- **Deduplication gate:** same `is_report_already_ingested()` check per rapport_id
- **Failure mode:** wrapped in try/except — any error is logged as WARNING and pipeline continues without report enrichment. Reports are declared non-fatal.
- **Confidence:** HIGH.

### Path 3 — consultant_integration.py (standalone pre-pipeline step)

- **File:** `src/consultant_integration.py`
- **Function:** `run_consultant_integration()`
- **Trigger:** Run manually BEFORE the main pipeline: `python src/consultant_integration.py` (or programmatically with `rebuild_consultant_wb=True`)
- **Source input:** Raw PDF files under `input/consultant_reports/` (folders: `lesommer/`, `avls/`, `terrell/`, `socotec/`)
- **Processing chain:**
  1. PDF parse → `consultant_reports.xlsx` (via `consultant_ingest/` sub-modules)
  2. Match against GED → `consultant_match_report.xlsx` (via `consultant_matcher.py`)
  3. Optionally: write directly to GF Excel cells via `consultant_gf_writer.py` (Stages 1 and 2)
- **Output written:** `output/consultant_reports.xlsx`, `output/consultant_match_report.xlsx`, and optionally `output/GF_consultant_enriched_stage1.xlsx`, `output/GF_consultant_enriched_stage2.xlsx`
- **Confidence gate at enrichment step:** Only HIGH and MEDIUM confidence matches enter `build_enrichment_records()` for direct GF write. LOW confidence is excluded from direct GF write but NOT excluded from report_memory upsert.
- **Confidence:** HIGH for the PDF→Excel part; MEDIUM for the direct GF write part (it bypasses run history).

### Path 4 — bet_report_merger (UI data-loader, background merge)

- **File:** `src/reporting/bet_report_merger.py`
- **Function:** `merge_bet_reports(docs_df, responses_df, base_dir)` called from `src/reporting/data_loader.py` inside `load_run_context()`
- **Trigger:** Automatically on every UI data load (every time the dashboard renders or a user opens the app). NOT called from the main pipeline.
- **Source input:** `consultant_reports.xlsx` from `output/repports output/` or `output/` (whichever exists)
- **Expected columns consumed:** `NUMERO`, `INDICE`, `STATUT_NORM`, `COMMENTAIRE`, `DATE_FICHE` from each RAPPORT sheet
- **Output written:** Mutates `responses_df` in memory (adds `response_source`, `observation_pdf` columns). If status backfill occurs, also rebuilds `WorkflowEngine` and `responsible_parties`. Does NOT write to `report_memory.db` or `run_memory.db`.
- **Failure mode:** wrapped in try/except — any error is logged as WARNING, execution continues with `response_source="GED"` column added.
- **Confidence:** MEDIUM — no persistent record that this merge happened.

---

## 4. Merge / Consumption Paths

| Consumer | File / Function | Uses Report Data For | Type | Risk |
|---|---|---|---|---|
| `stage_write_gf` (pipeline) | `stage_write_gf.py` / `WorkflowEngine(effective_responses_df)` | Builds WorkflowEngine from effective_responses_df; this is what writes GF_V0_CLEAN.xlsx | ENRICHMENT (PENDING→ANSWERED only) | LOW — GED-anchored, ANSWERED rows protected |
| `build_effective_responses` | `effective_responses.py` | Upgrades PENDING rows to ANSWERED; sets status_clean, date_answered, response_comment | ENRICHMENT | MEDIUM — no timestamp ordering; old report could upgrade a row that GED later answered differently |
| `WorkflowEngine` (UI) | `data_loader.py` → `bet_report_merger` → `WorkflowEngine` | Same fields (status_clean, date_status_type, date_answered, response_comment) as main pipeline but via a different source file | OVERRIDE (Track A) + ENRICHMENT (Track B) | HIGH — UI can show different state than final GF output |
| `consultant_gf_writer.write_gf_enriched` | `consultant_gf_writer.py` / `_enrich_sheet_inplace()` | Writes DATE and STATUT columns directly into GF Excel cells; Stage 2 also writes OBSERVATIONS | OVERRIDE (cell-level) | HIGH — bypasses run history; no deduplication; will overwrite whatever pipeline wrote |
| `compute_consultant_summary` (UI) | `reporting/aggregator.py` | Counts calls/answers/VSO/VAO/REF from `ctx.responses_df` (which includes bet_report_merger enrichment) | ENRICHMENT (read-only aggregation) | MEDIUM — aggregation numbers reflect BET-merged data, not pure GED |
| `compute_project_kpis` (UI) | `reporting/aggregator.py` | Uses `workflow_engine` (which was rebuilt after BET merge) for visa_global counts | ENRICHMENT | MEDIUM — same BET merge propagation |
| `run_memory.db` (provenance only) | `run_memory.py` / `register_run_input` | Registers `report_memory.db` hash as input to run (`REPORT_MEMORY` input type) | PROVENANCE only | LOW — hash snapshot means you can detect if report_memory changed between runs |

---

## 5. Truth Hierarchy (Current State)

**In the main pipeline (GF_V0_CLEAN.xlsx production):**

```
1. GED ANSWERED  →  Always wins. Reports cannot touch it. (Rule 1, effective_responses.py)
2. Report memory →  Wins over GED only when GED is PENDING. (Rule 2, effective_responses.py)
3. GED PENDING with no report answer → GED pending stays as-is. (Rule 3)
4. GED NOT_CALLED → Untouched. Reports cannot inject new workflow rows. (Rule 4)
```

This is a clean, explicit, GED-first hierarchy with report memory as a fill-in layer. The rules are implemented, documented, and testable.

**In the UI data-loader (dashboard):**

```
1. bet_report_merger Track A (status backfill):
   PENDING in GED + PDF has status → PDF wins (OVERRIDE).
   Source tagged: response_source = "PDF_REPORT"

2. bet_report_merger Track B (observation enrichment):
   GED comment is empty or placeholder → PDF observation replaces it.
   Source tagged: response_source = "GED+PDF_OBS"

3. If no consultant_reports.xlsx found → GED only.
```

**Critical observation:** The UI merge (bet_report_merger) and the pipeline merge (effective_responses.py) are **completely independent**. They read from different source files (`consultant_reports.xlsx` vs `consultant_match_report.xlsx`) and write to different targets (in-memory `responses_df` for the UI vs persistent `report_memory.db` for the pipeline). **There is no shared source of truth between them.**

**In consultant_integration.py (direct GF write):**

```
Last write wins. consultant_gf_writer overwrites GF Excel cells with no check of current cell state.
Confidence gate excludes LOW confidence from direct GF write, but HIGH and MEDIUM both write unconditionally.
```

**Summary table:**

| Context | Who wins for PENDING? | Who wins for ANSWERED? | Formal rule? |
|---|---|---|---|
| Main pipeline | Report memory | GED | YES — coded in effective_responses.py |
| UI dashboard | bet_report_merger (PDF) | bet_report_merger (PDF) for Track A | YES — coded in bet_report_merger.py |
| Direct GF write | consultant_gf_writer | consultant_gf_writer | NO — unconditional cell write |

---

## 6. Conflict Scenarios

**Scenario 1 — Stale report upgrades a GED row that was later answered in GED**

A report ingested in run_0000 upgrades doc_id X / SOCOTEC from PENDING to VAO (report date: 2025-11-01). In a later GED export, GED records a REF answer for the same row (date: 2026-01-15). The pipeline correctly applies Rule 1 (GED ANSWERED wins). BUT: the report_memory row is still `is_active=1`. On a future run where the GED export is for an older snapshot, the report memory would incorrectly upgrade again.
**Risk level: MEDIUM. Current code handles it correctly via Rule 1, but the stale row remains in the DB and could re-activate under edge conditions.**

**Scenario 2 — Pipeline vs UI divergence on the same PENDING row**

GED shows doc_id Y / AVLS as PENDING. The pipeline loads report_memory and upgrades it to ANSWERED (via `effective_responses.py`). The final GF shows ANSWERED. Meanwhile, the UI data-loader runs `bet_report_merger` independently on a different source file (`consultant_reports.xlsx`). If `consultant_reports.xlsx` is older or contains a different status than the report_memory data, the UI could show a different status for the same row. The user sees ANSWERED in the GF but a different status on the dashboard (or vice versa).
**Risk level: HIGH. This is an architectural split with no reconciliation mechanism.**

**Scenario 3 — consultant_gf_writer overwrites GF output after pipeline run**

User runs `consultant_integration.py` after the main pipeline completes. `consultant_gf_writer` writes DATE and STATUT directly into `GF_V0_CLEAN.xlsx` cells (Stages 1/2 output files). These outputs are NOT registered in `run_memory.db`. They are not tracked artifacts. If a user opens `GF_consultant_enriched_stage2.xlsx` as the "final" output, they are using a GF that has been modified outside run history.
**Risk level: HIGH. No provenance, no deduplication, no freshness rule.**

**Scenario 4 — LOW confidence match enters report_memory but not direct GF enrichment**

`build_enrichment_records()` (used by `consultant_gf_writer`) excludes LOW confidence matches. BUT `stage_report_memory` reads `consultant_match_report.xlsx` and calls `upsert_report_responses()` without filtering by confidence. A LOW confidence match therefore enters `report_memory.db` with full `is_active=1` status. `build_effective_responses()` then treats it like any other row and can upgrade a PENDING GED row to ANSWERED based on a LOW confidence match.
**Risk level: MEDIUM. There is an asymmetry: LOW confidence is excluded from direct GF write (good) but not from report_memory ingestion (gap).**

**Scenario 5 — Sentinel hash prevents deduplication across bootstraps**

Most ingested reports use sentinel hashes (`BOOTSTRAP::<rapport_id>`). If `consultant_match_report.xlsx` is rebuilt from new PDFs (same rapport_id, different extracted data), the sentinel hash is identical to the previous ingestion. `is_report_already_ingested()` returns True and the new data is silently skipped.
**Risk level: MEDIUM. New consultant data from updated PDFs will not enter report_memory if the rapport_id was previously bootstrapped with a sentinel hash. Stale data persists.**

**Scenario 6 — Multiple report_memory.db snapshots with divergent state**

The disk contains at least 20+ `report_memory.db` files across runs, backups, worktrees, and parity output directories. The production `data/report_memory.db` was found **malformed** during this audit (sqlite3: `database disk image is malformed`). The pipeline currently reads from the production path. If the malformed DB causes `init_report_memory_db()` to silently fail, the run proceeds with zero persisted responses — all PENDING rows remain PENDING in the output.
**Risk level: HIGH. The production report_memory.db is malformed and needs immediate attention.**

**Scenario 7 — bet_report_merger uses different NUMERO matching logic than consultant_matcher**

`bet_report_merger` matches by `NUMERO` + optional `INDICE` using `_normalize_numero()`. `consultant_matcher` uses a full 6-step cascade with date proximity, SAS filter, fallback heuristics, and confidence scoring. The two paths can match different GED docs for the same report row. A report row that was correctly matched to doc_id X by `consultant_matcher` could be mapped to doc_id Y by `bet_report_merger` if the NUMERO is shared across multiple docs and bet_report_merger's simpler logic resolves differently.
**Risk level: MEDIUM. No deduplication or reconciliation exists between the two matchers.**

---

## 7. Flat GED Transition Impact

| Use Case | Keep | Replace | Redesign | Remove |
|---|---|---|---|---|
| report_memory.db persistence layer (tables, DDL) | ✅ | | | |
| `upsert_report_responses` / `load_persisted_report_responses` API | ✅ | | | |
| `build_effective_responses` merge rules (GED anchored, Rule 1-4) | ✅ | | | |
| `stage_report_memory` pipeline stage | ✅ | | | |
| `bootstrap_report_memory.py` script | ✅ | | | |
| Source column mapping (`consultant` → `approver_canonical`) | | | ✅ Must re-verify against Flat GED canonical names | |
| `consultant_match_report.xlsx` as ingestion source | ✅ (short term) | | ✅ Long term: ingest from Flat GED ops directly | |
| `bet_report_merger` (UI-layer merge) | | | ✅ Must be aligned with pipeline report_memory path | |
| `consultant_gf_writer` direct Excel write (Stages 1/2) | | | ✅ Must go through pipeline + run history | |
| Sentinel hash strategy | | | ✅ Add freshness metadata to allow re-ingestion | |
| LOW confidence filtering asymmetry | | ✅ Add confidence gate to `stage_report_memory` ingestion | | |
| Per-run report_memory snapshot (`REPORT_MEMORY_DB` artifact) | ✅ | | | |

---

## 8. Recommendations for Step 7

The following are concrete inputs for the Step 7 composition spec. They reflect what is implemented in code today, not aspirational design.

- **Flat GED must become the structural anchor for effective responses.** The current GED-anchored left-join in `build_effective_responses()` must be updated to left-join on Flat GED ops rows, not raw GED `responses_df`. The merge rules (Rule 1-4) can remain unchanged.

- **Report memory fills pending gaps only — this rule is already coded.** Rule 1 (GED ANSWERED wins) must be preserved verbatim in the Flat GED transition. No redesign needed.

- **Reports cannot override ANSWERED Flat GED rows without a freshness rule.** Currently there is no timestamp comparison between `report_response_date` and the GED answer date. Add a guard: if `report_response_date` < GED `date_answered`, the report is not eligible to upgrade even a PENDING row.

- **All report rows need timestamp + author + provenance.** The `ingested_at` field exists but is set to the pipeline's system clock at ingest time, not to the date in the report. `report_response_date` is the closest proxy but is not always populated. Step 7 should mandate that eligibility requires a non-null `report_response_date`.

- **bet_report_merger must be reconciled with report_memory or removed as a separate path.** The UI must consume the same enriched responses_df that the pipeline produces (i.e., the `effective_responses_df` from stage_report_memory), not re-run an independent merge. This is the highest-priority architectural risk.

- **consultant_gf_writer stages 1/2 must be deprecated or brought into run history.** Any direct Excel write to a GF file should be registered as a `run_artifact`. The current pattern produces untracked GF variants that users may treat as authoritative.

- **LOW confidence matches should be filtered out at ingestion time** (not only at GF write time). Add a confidence gate to `stage_report_memory` and `bootstrap_report_memory.py`: only HIGH and MEDIUM rows enter `persisted_report_responses`.

- **Sentinel hashes must support re-ingestion.** Change the sentinel strategy so that a re-run with new data for the same `rapport_id` can force-update rather than skip. One approach: include a content hash of the extracted rows (not just the PDF identity) in the deduplication key.

- **The production `data/report_memory.db` is malformed and must be repaired or replaced** from the `runs/run_0000/report_memory.db` snapshot before any Step 7 work begins.

---

## Files Inspected

| File | Purpose |
|---|---|
| `src/report_memory.py` | Core SQLite persistence layer — schema, DDL, API |
| `src/run_memory.py` | Run registry DB — schema, correction/invalidation logic |
| `src/pipeline/stages/stage_report_memory.py` | Pipeline stage 6: DB init, ingest, effective response build |
| `src/effective_responses.py` | Merge engine — Rules 1-4, left-join logic |
| `src/consultant_integration.py` | Standalone pre-pipeline: PDF→Excel→match→GF write |
| `src/consultant_ingest/consultant_report_builder.py` | PDF ingest orchestrator (LE_SOMMER, AVLS, TERRELL, SOCOTEC) |
| `src/consultant_matcher.py` | 6-step matching cascade, confidence scoring |
| `src/consultant_gf_writer.py` | Direct Excel cell writer (Stages 1+2) — third independent path |
| `src/pipeline/runner.py` | Pipeline stage order |
| `src/pipeline/context.py` | PipelineState dataclass — persisted_df, effective_responses_df |
| `src/pipeline/stages/stage_write_gf.py` | Uses effective_responses_df to build WorkflowEngine |
| `src/reporting/data_loader.py` | UI data loader — calls bet_report_merger |
| `src/reporting/bet_report_merger.py` | SECOND independent report merge (UI-only) |
| `src/reporting/aggregator.py` | Dashboard KPI computation |
| `scripts/bootstrap_report_memory.py` | One-time DB seed script |

## Databases Inspected

| Database | Location | Status | Rows |
|---|---|---|---|
| `report_memory.db` (production) | `data/report_memory.db` | **MALFORMED** — sqlite3 error | Unknown |
| `report_memory.db` (run_0000 snapshot) | `runs/run_0000/report_memory.db` | CLEAN | 1,245 responses, 85 ingested reports |
| `run_memory.db` (backup) | `backups/backup_20260421_phase_b/run_memory.db` | CLEAN | 2 runs (run_0000 BASELINE, run_0001 INCREMENTAL) |

---

## Summary of Trust Hierarchy

```
MAIN PIPELINE:
  GED ANSWERED   > Report Memory  (reports never touch answered rows)
  Report Memory  > GED PENDING    (reports upgrade pending to answered)
  Formal rule: YES — coded in effective_responses.py Rules 1-4

UI DATA LOADER:
  bet_report_merger (PDF) > GED PENDING  (Track A: status backfill)
  bet_report_merger (PDF) = GED ANSWERED (Track A applies to PENDING only)
  Formal rule: YES — coded in bet_report_merger.py
  BUT: independent of pipeline path — no reconciliation

DIRECT GF WRITE (consultant_integration):
  Last write wins — no check of existing cell content
  Formal rule: NONE
```

---

## Top 5 Risks

1. **Production `data/report_memory.db` is malformed.** If the pipeline silently fails to load it, every pending row that should be ANSWERED via report memory stays PENDING in the output. This is a live production risk that predates Step 6.

2. **Two independent merge paths (pipeline vs UI) can diverge on the same row.** `stage_report_memory` reads `consultant_match_report.xlsx` and uses confidence-scored matches. `bet_report_merger` reads `consultant_reports.xlsx` directly and uses simpler NUMERO-only matching. They can disagree. The user has no way to know which version they are looking at.

3. **consultant_gf_writer is a third untracked write path.** Stages 1/2 output files are not registered in run_memory.db and are not produced by the main pipeline. If a user uses `GF_consultant_enriched_stage2.xlsx` as the deliverable, that GF has data that cannot be reproduced by replaying the pipeline.

4. **LOW confidence matches enter report_memory without filtering.** The confidence gate exists at the direct-GF-write layer but not at the report_memory ingestion layer. A LOW confidence match can persist in the DB and upgrade a PENDING GED row to ANSWERED in the pipeline output.

5. **Sentinel hash collision blocks re-ingestion of updated report data.** If `consultant_match_report.xlsx` is rebuilt with corrected or updated data for the same rapport_id, the sentinel-hashed rows will be skipped by `is_report_already_ingested()`. Stale data will remain in report_memory.db indefinitely unless the DB is manually purged.

---

## Step 7 Readiness Assessment

**Can Step 7 (Composition Spec) proceed?**

YES, with the following preconditions:

1. The production `report_memory.db` must be repaired or replaced from the `runs/run_0000/report_memory.db` snapshot.
2. The composition spec must address both merge paths (pipeline + UI) and define which one is authoritative for Flat GED.
3. The composition spec must explicitly decide the fate of `bet_report_merger` — whether it is retired, aligned with the pipeline path, or preserved as a UI-only overlay with explicit provenance tags.

The merge logic itself (Rules 1-4 in `effective_responses.py`) is sound and can be adapted for Flat GED with minimal changes. The structural risk is in the fragmented architecture, not in the core merge algorithm.
