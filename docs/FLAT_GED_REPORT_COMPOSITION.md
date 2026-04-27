# FLAT_GED_REPORT_COMPOSITION.md

**Step:** 7 — Flat GED + Report Memory Composition Spec  
**Plan version:** v2  
**Date:** 2026-04-24  
**Status:** COMPLETE — authoritative design document  
**Depends on:** `docs/FLAT_GED_CONTRACT.md` (v1.0), `docs/BACKEND_SEMANTIC_CONTRACT.md`, `docs/GED_ENTRY_AUDIT.md`, `docs/REPORTS_INGESTION_AUDIT.md`  
**Consumed by:** Step 8 (clean_GF reconstruction), Step 9c (Flat GED query library), Step 10 (UI source-of-truth map)

---

## 1. Executive Summary

The effective response for any consultant step is produced by a **single, pipeline-owned composition engine** that left-joins `GED_OPERATIONS` rows (Flat GED) with eligible enrichment rows from `report_memory.db`. There is one composition path and one output: `effective_responses_df`, produced by `stage_report_memory` inside the main pipeline.

**The chosen model in one sentence:**  
Flat GED `GED_OPERATIONS` rows are the structural left side. Report memory may enrich rows that are `PENDING` in Flat GED, subject to confidence, freshness, active-flag, and key-match gates. Every output row carries an explicit provenance tag. No other merge path is authoritative.

**What this model retires:**  
`bet_report_merger` (UI-layer merge) is **retired** as an independent truth source. `consultant_gf_writer` direct Excel write is **deprecated** from the truth path.

**What this model preserves:**  
The four merge rules in `effective_responses.py` (Rules 1–4) are sound and are carried forward with the anchor upgraded from raw GED `responses_df` to `GED_OPERATIONS` rows.

---

## 2. Source Hierarchy

| Rank | Source | Scope | Can Override Flat GED ANSWERED? | Notes |
|------|--------|-------|---------------------------------|-------|
| 1 | **Flat GED — `GED_OPERATIONS`** | All documents, all approver steps | N/A — primary truth | Left-side anchor for all compositions. Only ACTIVE instance rows. `OPEN_DOC` rows excluded from effective response computation. |
| 2 | **`report_memory.db` — `persisted_report_responses`** | Eligible (doc_id, approver_canonical) pairs only | **NO** — cannot override ANSWERED Flat GED rows | May enrich PENDING rows only. Subject to all gates in §4. |
| 3 | **Manual comment enrichment** | Additive text only, not status | NO | A report comment may be appended to an ANSWERED row's `observation` field, tagged with provenance. It cannot change `status_clean` or `date_answered` of an ANSWERED row. |
| 4 | ~~`bet_report_merger` (UI layer)~~ | ~~(doc_id, approver) via NUMERO match~~ | **RETIRED** | Was an independent UI-only merge reading `consultant_reports.xlsx`. Source of pipeline/UI truth split. Retired in this step. |
| 5 | ~~`consultant_gf_writer` (direct Excel write)~~ | ~~Selected GF cells~~ | **DEPRECATED** | Wrote DATE + STATUT directly to GF Excel cells outside run history. No longer a truth path. See §9. |

---

## 3. Composition Anchor

**`GED_OPERATIONS` rows from Flat GED are the left side of every composition join.**

This is a change from the legacy path, where `build_effective_responses()` received the output of `normalize_responses()` (raw GED `responses_df`) as its left anchor. In the Flat GED path, `GED_OPERATIONS` replaces that input entirely.

**Why `GED_OPERATIONS`, not `GED_RAW_FLAT`:**  
`GED_OPERATIONS` is already at the step-typed, workflow-oriented grain that downstream consumers (`WorkflowEngine`, `stage_write_gf`) require. It carries pre-computed fields — `is_completed`, `is_blocking`, `status_family`, `phase_deadline`, `delay_contribution_days` — that eliminate re-derivation in the adapter. `GED_RAW_FLAT` is the raw approver-level source; it lacks step ordering, cycle closure signals, and delay columns.

**Why only ACTIVE instance rows:**  
Per `FLAT_GED_CONTRACT.md` §3 and `BACKEND_SEMANTIC_CONTRACT.md` §3, `GED_OPERATIONS` exposes only the ACTIVE instance per `(numero, indice)`. Non-ACTIVE instances (`SEPARATE_INSTANCE`, `INACTIVE_DUPLICATE`, `INCOMPLETE_BUT_TRACKED`) are visible only in `DEBUG_TRACE` and are outside Phase 2 scope. The composition engine must not attempt to resolve multi-instance conflicts — that is deferred to Step 12 (Chain/Onion).

**Why `OPEN_DOC` rows are excluded:**  
`OPEN_DOC` is a synthetic step that models the document submittal event. It has no approver, no status, no response, and no approval semantics. Downstream logic must filter it out (`step_type != "OPEN_DOC"`) before constructing effective responses.

**Grain of the composition output:**  
One row per `(numero, indice, approver_canonical)` — identical to the grain of `GED_OPERATIONS` CONSULTANT and SAS rows after `OPEN_DOC` exclusion.

---

## 4. Eligibility Rules for Report Rows

A report row from `persisted_report_responses` must pass **all** gates to be eligible for composition. Failing any single gate blocks the row entirely.

| # | Rule | Condition | Pass / Fail | Effect of Fail |
|---|------|-----------|-------------|----------------|
| E1 | **Active flag** | `is_active = 1` | Pass if 1; Fail if 0 | Row silently skipped. Deactivated rows are historical only. |
| E2 | **Confidence gate** | `match_confidence` is HIGH or MEDIUM | Pass; Fail if LOW or UNKNOWN or NULL | Row blocked. LOW/UNKNOWN confidence matches must not enter composition. This closes the asymmetry found in Step 6 Scenario 4. |
| E3 | **`doc_id` match** | Report `doc_id` must match a `GED_OPERATIONS` row's `(numero, indice)` identity key | Pass if match found; Fail if no GED row with that `doc_id` exists | Row has no anchor; silently skipped. |
| E4 | **Canonical approver match** | Report `consultant` (normalized to `approver_canonical`) must match an `actor_clean` or `approver_canonical` value present in `GED_OPERATIONS` for that document | Pass if match found; Fail if no step with that approver exists for that document | Row has no composition target; silently skipped. |
| E5 | **Report date presence** | `report_response_date` must be non-null and non-empty | Pass if present; Fail if NULL or empty | Row is not date-eligible. It may still carry a `report_status` and pass for status enrichment only if E6 passes — but it cannot be used to set `date_answered` on a PENDING row. A report row with neither date nor status is inert. |
| E6 | **Minimum answer content** | At least one of `report_status` or `report_response_date` must be non-null/non-empty | Pass if either present; Fail if both empty | Row carries no meaningful answer; blocked entirely. |
| E7 | **Freshness gate** | If Flat GED row is ANSWERED: `report_response_date` must be > Flat GED `response_date`. If Flat GED row is PENDING: `report_response_date` must be > Flat GED `data_date` minus 730 days (2-year floor) | Pass if fresher; Fail if stale | Stale report does not override an ANSWERED row. Stale report for a PENDING row is still eligible (PENDING rows have no answer date to compare against) — the 2-year floor prevents obviously ancient reports from contaminating current runs. |
| E8 | **No synthetic SAS target** | Report row must not target a synthetic SAS row (`operation_rule_used` contains `"SYNTHETIC_SAS"`) | Pass if real step; Fail if synthetic | Synthetic SAS represents SAS absence, not a real approver. Reports cannot assign answers to it. |

**Confidence gate detail (E2):**  
Only `HIGH` and `MEDIUM` confidence matches are eligible. `LOW`, `UNKNOWN`, and null confidence values are blocked. This gate must be applied at **two enforcement points**: (a) during ingestion into `persisted_report_responses` via `stage_report_memory` and `bootstrap_report_memory.py` — LOW/UNKNOWN rows must not be written to the DB; and (b) during composition — as a secondary check, any row that survived with LOW/UNKNOWN confidence is ignored.

**Freshness gate detail (E7):**  
This gate guards ANSWERED Flat GED rows against being re-enriched by older report data. For PENDING rows, there is no GED answer date to compare against, so a 2-year floor is applied as a staleness proxy to prevent multi-year-old report data from silently entering current runs. The specific floor value (730 days) is a conservative default and may be tightened after operational experience.

---

## 5. Merge Rules by Flat GED State

The merge rules extend the existing Rules 1–4 from `effective_responses.py`, updated for the Flat GED anchor. The rule number mapping is preserved for continuity.

| # | Flat GED State | Report State | Action | Result `effective_source` | Provenance Tag | Notes |
|---|---------------|--------------|--------|--------------------------|----------------|-------|
| R1a | **ANSWERED** (`is_completed = True`) | No eligible report | Keep GED as-is | `GED` | `GED` | Core Rule 1 — GED truth is final. |
| R1b | **ANSWERED** | Report exists but `report_response_date` ≤ Flat GED `response_date` (stale) | Keep GED as-is; log stale report | `GED` | `GED` | Stale report cannot override a more recent GED answer. Report flagged as stale in log. |
| R1c | **ANSWERED** | Report exists, is fresh, and carries only a `report_comment` (no status override) | Keep GED status/date; **append** comment to `observation` field | `GED` | `GED+REPORT_COMMENT` | Additive comment enrichment only. Comment is tagged `[report: ...]`. Status and date are never touched for ANSWERED rows. |
| R1d | **ANSWERED** | Report exists and carries a **different status** from GED (e.g., GED says REF, report says VAO) | Keep GED status/date; log as **CONFLICT** | `GED` | `GED_CONFLICT_REPORT` | Status conflict is escalated to log with severity WARNING. GED wins. No override. |
| R2a | **PENDING** (`is_completed = False`, eligible report exists, all gates E1–E8 pass) | Report has status AND date | Upgrade row to ANSWERED: set `date_answered`, `status_clean`, append `observation` | `REPORT_MEMORY` | `GED+REPORT_STATUS` | Core Rule 2. Report fully answers the pending row. |
| R2b | **PENDING** | Report has date only (no status) | Upgrade `date_answered`; preserve existing GED `status_clean`; append `observation` | `REPORT_MEMORY` | `GED+REPORT_STATUS` | Partial upgrade — date confirmed, status not provided by report. Existing GED status (may be empty/PENDING) is preserved. |
| R2c | **PENDING** | Report has status only (no date, gate E5 passes partially) | Do NOT upgrade `date_answered`; do NOT change `date_status_type` to ANSWERED; optionally append comment | `GED` | `GED+REPORT_COMMENT` | Without a response date, the row cannot be promoted to ANSWERED. Status alone is insufficient. Comment may be appended. |
| R2d | **PENDING** | Report exists but fails freshness gate E7 (stale, older than 2-year floor) | Keep GED pending; log stale report | `GED` | `GED` | Stale data blocked from upgrading pending rows. |
| R3a | **PENDING** | No eligible report | Keep GED pending | `GED` | `GED` | Core Rule 3 — no report data available. |
| R3b | **PENDING** | Report exists but fails E2 (LOW confidence) | Keep GED pending; log blocked report | `GED` | `GED` | LOW confidence blocked. Pending row is not enriched. |
| R4a | **NOT_CALLED / ABSENT** (step not present in `GED_OPERATIONS`) | Any report | **Do not create a new workflow row** | — | — | Core Rule 4. Reports cannot invent GED workflow steps. No row is synthesized. |
| R4b | **PENDING SAS** (SAS step pending, no CONSULTANT rows in GED_OPERATIONS for that document) | Any report targeting a CONSULTANT approver for that document | Block entirely | — | — | If SAS is pending, no CONSULTANT step exists in GED_OPERATIONS for that document. There is no composition target. |
| HM | **ANSWERED with HM** (`status_clean = "HM"`) | Report has a subsequent VAO or REF | Keep GED HM status; log report as informational | `GED` | `GED_CONFLICT_REPORT` | HM (visa with remarks) is a real answer. A later report suggesting a different outcome is a conflict, not an upgrade. Requires manual review if report date is newer. |
| REF | **ANSWERED with REF** | Report has VAO or VSO | Keep GED REF; log as CONFLICT with severity ERROR | `GED` | `GED_CONFLICT_REPORT` | A REF in GED combined with an approval in a report is a high-severity conflict. GED wins. Escalate to `MANUAL_REVIEW` log entry. |

**Total rows: 14 (covering all required cases plus HM and REF-conflict extensions).**

---

## 6. Provenance Vocabulary

Every effective response row must carry an `effective_source` column with one of the following controlled values. No other values are permitted. This vocabulary is finite and closed.

| Value | Meaning | When Applied |
|-------|---------|--------------|
| `GED` | Row is sourced entirely from Flat GED `GED_OPERATIONS`. No report enrichment applied. | Rules R1a, R1b, R2c (no date), R2d, R3a, R3b |
| `GED+REPORT_STATUS` | Flat GED base row; report memory provided status and/or date that upgraded a PENDING row to ANSWERED. | Rules R2a, R2b |
| `GED+REPORT_COMMENT` | Flat GED base row; report memory contributed only an additive comment to `observation`. No status or date was changed. | Rules R1c, R2c (comment only) |
| `GED_CONFLICT_REPORT` | Flat GED base row is ANSWERED; report memory carries a different status. GED wins. Conflict is logged. | Rules R1d, HM, REF |
| `REPORT_ONLY` | **NOT PERMITTED in Phase 2.** Reserved vocabulary for potential future use where a report answer exists for a step not present in GED. Currently: Rule 4 blocks all such cases. Any row tagged `REPORT_ONLY` in the output is a composition engine bug. | Prohibited |

**Implementation note:** The `effective_source` column must be present on every row of the composition output. Rows that had no report interaction receive `GED`. The column must be propagated downstream to `WorkflowEngine`, `stage_write_gf`, and the UI data layer without being dropped.

---

## 7. Conflict Handling Matrix

Conflicts arise when Flat GED and report memory disagree about the state of a row. All conflicts are resolved in favour of Flat GED. Conflicts are never silently dropped.

| # | Scenario | Flat GED State | Report State | Disposition | Log Action | Provenance |
|---|----------|---------------|--------------|-------------|------------|------------|
| C1 | GED says ANSWERED REF; report says VAO (fresher date) | ANSWERED / REF | VAO, newer date | **IGNORE** — GED wins | WARNING: status conflict, report overruled | `GED_CONFLICT_REPORT` |
| C2 | GED says ANSWERED VAO; report says REF (same date) | ANSWERED / VAO | REF, same date | **IGNORE** — GED wins | WARNING: same-date conflict, GED kept | `GED_CONFLICT_REPORT` |
| C3 | GED says PENDING; report says REF | PENDING | REF | **ENRICH** — upgrade PENDING to ANSWERED/REF | INFO: PENDING upgraded via report | `GED+REPORT_STATUS` |
| C4 | GED says ANSWERED 2026-03-01; report says VAO dated 2025-12-01 (stale) | ANSWERED | VAO, older date | **IGNORE** — report is stale (E7 fails) | DEBUG: stale report suppressed | `GED` |
| C5 | Two active report rows for same (doc_id, approver) disagree (VAO vs REF) | PENDING | VAO + REF both active | **Winner selection** — highest confidence wins; if tied, latest `report_response_date` wins; if still tied, latest `ingested_at` wins. `normalize_persisted_report_responses_for_merge()` handles this before merge. | INFO: multi-report dedup, winner selected | `GED+REPORT_STATUS` |
| C6 | GED says ANSWERED HM; report says FAV (subsequent approval) | ANSWERED / HM | FAV, newer date | **MANUAL_REVIEW** — HM + subsequent approval is architecturally significant. GED HM wins in pipeline. Flag for human inspection. | ERROR: HM/approval conflict — manual review required | `GED_CONFLICT_REPORT` |
| C7 | GED says PENDING SAS; report targets a CONSULTANT for that document | PENDING SAS (no CONSULTANT rows exist) | CONSULTANT report | **IGNORE** — no composition target (Rule R4b) | DEBUG: no CONSULTANT step exists, report skipped | — |
| C8 | GED row not present in `GED_OPERATIONS` (step was NOT_CALLED); report exists | ABSENT | Any | **IGNORE** — Rule 4, no synthetic row creation | DEBUG: NOT_CALLED step, report suppressed | — |
| C9 | GED says ANSWERED VSO or VAO; report says VAOB (`VAOB = VAO` — same approval family) | ANSWERED / VSO or VAO | VAOB | **ENRICH** — GED status/date unchanged; report VAOB is additive comment only, provenance-tagged | INFO: VAOB approval enrichment noted in observation | `GED+REPORT_COMMENT` |
| C10 | GED says ANSWERED; report carries only a new comment with no status change | ANSWERED | Comment only | **ENRICH** — append comment to `observation`, provenance-tagged | INFO: additive comment appended | `GED+REPORT_COMMENT` |

**Conflict disposition legend:**  
- `IGNORE` — GED wins, report discarded, conflict logged.  
- `ENRICH` — Report provides additive data; no GED fields overridden.  
- `MANUAL_REVIEW` — GED wins in the pipeline output, but a human-review entry is written to the run log for the conflict pair.  
- `WINNER_SELECTION` — Report deduplication logic picks the best row before the conflict reaches the composition engine.

---

## 8. UI Consumption Model

**`bet_report_merger` is retired.**

This is an explicit, unconditional decision.

### Current problem (Step 6 finding)
`bet_report_merger` runs inside `src/reporting/data_loader.py` on every UI load. It reads `consultant_reports.xlsx` directly — a different source file from `consultant_match_report.xlsx` that feeds the main pipeline. It uses simpler NUMERO-only matching logic, not the 6-step cascade from `consultant_matcher.py`. It produces a different merge result than `effective_responses_df` for the same document. The UI can show a different status from the GF output for the same row.

### Target model
The UI data loader (`data_loader.py`) must consume `ctx.effective_responses_df` as its sole source of response state. This is the DataFrame produced by `stage_report_memory` in the main pipeline — the single composed output that applies all eligibility gates, the four merge rules, and carries the `effective_source` provenance column.

### Migration path for `bet_report_merger`
1. `bet_report_merger.py` must be removed from the import graph of `data_loader.py`.
2. The call to `merge_bet_reports()` inside `load_run_context()` must be deleted.
3. The `response_source` and `observation_pdf` columns currently injected by `bet_report_merger` must instead be sourced from `effective_source` and `observation` in `effective_responses_df`.
4. `bet_report_merger.py` itself may be retained as a dead file with a deprecation comment, or deleted. It must not be called by any active code path.

### `WorkflowEngine` reconstruction in the UI
`data_loader.py` currently rebuilds `WorkflowEngine` after `bet_report_merger` runs. In the new model, `WorkflowEngine` must be built from `ctx.effective_responses_df` directly — the same input that `stage_write_gf` uses to produce `GF_V0_CLEAN.xlsx`. The UI and the GF output will then reflect identical state.

### `compute_consultant_summary` and `compute_project_kpis`
These aggregators in `src/reporting/aggregator.py` consume `responses_df` (which currently includes `bet_report_merger` enrichment). After retirement of `bet_report_merger`, they must consume `ctx.effective_responses_df` instead. The KPI numbers they produce will then match the pipeline output.

---

## 9. Direct Write Path Decision

**`consultant_gf_writer` is deprecated from the truth path.**

Specifically:
- `consultant_gf_writer.py` `write_gf_enriched()` / `_enrich_sheet_inplace()` must no longer be used to produce deliverable GF Excel files.
- `GF_consultant_enriched_stage1.xlsx` and `GF_consultant_enriched_stage2.xlsx` are **not authoritative GF outputs**. They are not registered in `run_memory.db`. They bypass pipeline composition entirely. They must not be treated as final deliverables.

### What `consultant_gf_writer` may become
If there is an operational need to produce an Excel snapshot of effective responses for a specific consultant, `consultant_gf_writer` may be repurposed as a **pipeline artifact writer**: it reads from `ctx.effective_responses_df` (the composed output), filters to the requested consultant, and writes to a file registered as a `run_artifact` in `run_memory.db` with type `CONSULTANT_SNAPSHOT`. In this form, it is a reporting exporter, not a truth writer. It does not modify `GF_V0_CLEAN.xlsx` or any primary pipeline output.

Until that repurposing is explicitly implemented and registered in `run_memory.db`, `consultant_gf_writer` is considered dormant and must not be invoked in production runs.

### `consultant_integration.py`
`consultant_integration.py` (the standalone pre-pipeline PDF → Excel → match step) remains valid as a **data preparation tool**, not a truth tool. Its outputs (`consultant_match_report.xlsx`) are the ingestion source for `stage_report_memory`. The pipeline continues to read from `consultant_match_report.xlsx` to populate `report_memory.db`. Only the direct-write final stages of `consultant_integration.py` (Steps 1 and 2 of the enrichment chain) are deprecated.

---

## 10. Database Governance

### 10.1 Production DB repair (immediate prerequisite)

The production `data/report_memory.db` is **malformed** (sqlite3: `database disk image is malformed` — confirmed in Step 6 Scenario 6). Before Step 8 work begins:

1. **Replace** `data/report_memory.db` with the clean snapshot from `runs/run_0000/report_memory.db` (1,245 rows, 85 ingested reports, confirmed clean).
2. **Verify** the replacement by running `sqlite3 data/report_memory.db "PRAGMA integrity_check;"` — must return `ok`.
3. **Register** the repair as a note in `GFUP_STEP_TRACKER.md` and in the run log.

### 10.2 Confidence filtering at ingestion (gate enforcement)

The confidence gate (E2) must be enforced at the ingestion layer, not only at composition time. Both `stage_report_memory` and `bootstrap_report_memory.py` must:
- Filter `consultant_match_report.xlsx` rows to `Confidence IN ('HIGH', 'MEDIUM')` before calling `upsert_report_responses()`.
- Log the count of blocked LOW/UNKNOWN confidence rows per run.
- Never write a LOW or UNKNOWN confidence row to `persisted_report_responses`.

This closes the gap identified in Step 6: currently, LOW confidence rows enter `report_memory.db` with `is_active=1` and can upgrade PENDING GED rows.

### 10.3 Per-run snapshots

The existing per-run snapshot strategy is preserved and extended:
- Each pipeline run continues to produce a `report_memory.db` snapshot registered as `run_artifact` with type `REPORT_MEMORY_DB` in `run_memory.db`.
- The snapshot captures the DB state **after** the run's ingestion completes, not before.
- Snapshot hash continues to be registered in `run_memory.db` under `REPORT_MEMORY` input type, enabling run-to-run reproducibility checks.

### 10.4 Sentinel hash replacement

The current sentinel hash strategy (`BOOTSTRAP::<rapport_id>`) prevents re-ingestion when `consultant_match_report.xlsx` is rebuilt from updated PDFs for the same `rapport_id`. This must be replaced:

- **New deduplication key:** `source_file_hash = SHA256(sorted(extracted_row_values))` — a hash of the actual extracted data, not the PDF identity alone.
- This allows re-ingestion when the extracted data changes, even if the `rapport_id` is the same.
- A force-update flag (`--force-reingest`) must be added to `bootstrap_report_memory.py` to explicitly re-process a `rapport_id` regardless of hash match.

### 10.5 Stale row deactivation

Report rows can become stale when the GED later records an ANSWERED state for the same (doc_id, approver) pair. The pipeline must deactivate such rows on each run:

- After `build_effective_responses()` resolves a row via Rule 1 (GED ANSWERED wins), if a matching report row exists in `persisted_report_responses` with `is_active=1`, it must be set to `is_active=0` with a `deactivated_reason` of `"GED_ANSWERED_SUPERSEDES"`.
- Deactivation is logged per row at DEBUG level.
- Deactivated rows are never deleted; they remain as audit history.

### 10.6 Retention

- `report_memory.db` rows are never hard-deleted. Deactivation (`is_active=0`) is the only removal mechanism.
- Per-run snapshots are retained indefinitely as part of the run archive.
- The production `data/report_memory.db` is the live working DB. It is always the source used by the pipeline (after the §10.1 repair).
- Backups under `backups/` are retained but are not used by the pipeline directly.

---

## 11. Step 8 Implementation Inputs

The following are concrete, actionable inputs for the Step 8 implementer. They describe what must change in code, in order of dependency.

1. **Replace the left-join anchor in `build_effective_responses()`.** The function currently receives `ged_responses_df` (output of `normalize_responses()` on raw GED). In the Flat GED path, it must receive a DataFrame derived from `GED_OPERATIONS` rows, filtered to `step_type != "OPEN_DOC"` and `instance_role == "ACTIVE"`. Column mapping must be verified via `FLAT_GED_ADAPTER_MAP.md` — specifically `is_completed → date_status_type`, `status_clean → status_clean`, `response_date → date_answered`, `is_blocking → blocking signal`.

2. **Enforce the confidence gate at ingestion time.** In `stage_report_memory.py`, before calling `upsert_report_responses()`, filter `consultant_match_report.xlsx` rows to `Confidence IN ('HIGH', 'MEDIUM')`. Identical filter must be added to `bootstrap_report_memory.py`. No code changes to `upsert_report_responses()` itself are needed.

3. **Add `effective_source` column to composition output.** `build_effective_responses()` already writes `effective_source` (`"GED"` or `"REPORT_MEMORY"`). Extend to the full five-value controlled vocabulary from §6: add `GED+REPORT_STATUS`, `GED+REPORT_COMMENT`, `GED_CONFLICT_REPORT` tags. Remove the binary string mapping and replace with the constants defined in §6.

4. **Add freshness gate (E7) to `build_effective_responses()`.** Before applying Rule 2 (upgrade PENDING to ANSWERED), compare `report_response_date` against Flat GED `data_date` using the 2-year floor rule. For ANSWERED rows, compare `report_response_date` against `response_date`. Stale rows must be skipped and logged.

5. **Add stale row deactivation after Rule 1 resolution.** When a GED ANSWERED row is confirmed (Rule 1 applied), check `persisted_report_responses` for active rows targeting the same `(doc_id, approver_canonical)`. Deactivate them with `is_active=0`, `deactivated_reason="GED_ANSWERED_SUPERSEDES"`.

6. **Add `GED_CONFLICT_REPORT` logging.** When an ANSWERED GED row is matched with a report carrying a different status (Rules R1d, HM, REF), write a structured conflict entry to the run log at WARNING/ERROR level. Include: `doc_id`, `approver_canonical`, `ged_status`, `ged_date`, `report_status`, `report_date`, `conflict_type`.

7. **Remove `bet_report_merger` from `data_loader.py`.** Delete the `merge_bet_reports()` call and its import from `data_loader.py`. Rebuild `WorkflowEngine` from `ctx.effective_responses_df` directly. Map `effective_source` to the `response_source` column that the UI currently reads from `bet_report_merger` output. This is a **required** change for Step 8 to be considered complete.

8. **Deprecate `consultant_gf_writer` direct-write stages.** Remove or guard the invocation of `write_gf_enriched()` in `consultant_integration.py`. Add a deprecation comment. Do not delete the file — it may be repurposed as a pipeline artifact writer later.

9. **Repair `data/report_memory.db` before any Step 8 run.** Copy from `runs/run_0000/report_memory.db`. Verify with `PRAGMA integrity_check`. This is a prerequisite, not a code change.

10. **Propagate `effective_source` downstream.** Ensure `stage_write_gf.py` and `data_loader.py` both receive and preserve the `effective_source` column from `effective_responses_df`. The column must appear in any per-run artifact that records response state.

---

## Final Summary

### Key decisions taken

1. `GED_OPERATIONS` rows are the structural left anchor for all composition. Not raw `responses_df`.
2. Reports enrich PENDING rows only. ANSWERED Flat GED rows are immutable to report override.
3. Confidence gate (HIGH/MEDIUM only) is enforced at both ingestion and composition layers.
4. Freshness gate: stale reports (older than GED answer date, or older than 2-year floor for PENDING rows) are blocked.
5. `effective_source` column carries a five-value controlled provenance vocabulary on every row.
6. `bet_report_merger` is retired unconditionally. The UI consumes `effective_responses_df` from the pipeline.
7. `consultant_gf_writer` direct Excel write is deprecated from the truth path. It may be repurposed as a pipeline artifact writer only.
8. `data/report_memory.db` must be repaired from the `run_0000` snapshot before Step 8 begins.
9. Stale report rows in `persisted_report_responses` are deactivated (not deleted) when GED confirms the same row as ANSWERED.
10. Sentinel hashes are replaced with content-derived hashes to allow re-ingestion of updated report data.

### What is retired

- `bet_report_merger` as an independent truth path (entire function call chain in `data_loader.py`).
- `consultant_gf_writer` Stages 1/2 as deliverable GF output producers.
- `GF_consultant_enriched_stage1.xlsx` and `GF_consultant_enriched_stage2.xlsx` as authoritative outputs.
- LOW/UNKNOWN confidence matches entering `persisted_report_responses`.
- Sentinel hash strategy as the sole deduplication key.

### What is preserved

- The four merge rules (Rules 1–4) from `effective_responses.py` — reused verbatim with the Flat GED anchor.
- `report_memory.db` schema, DDL, and persistence API (`upsert_report_responses`, `load_persisted_report_responses`).
- `stage_report_memory` pipeline stage — extended, not replaced.
- `bootstrap_report_memory.py` — extended with confidence filter, not replaced.
- Per-run `REPORT_MEMORY_DB` snapshot strategy.
- `normalize_persisted_report_responses_for_merge()` winner selection logic (confidence → date → ingested_at).
- `run_memory.db` provenance hash tracking for report memory inputs.
- `consultant_integration.py` as a data preparation tool (PDF → `consultant_match_report.xlsx`).

### Unresolved edge cases

1. ~~**`VAOB` status from reports** — **RESOLVED (2026-04-24, Eid).**~~ `VAOB = VAO`. VAOB is in the approval family and is never a conflict against a GED ANSWERED `VSO` or `VAO`. Rule C9 is classified as `GED+REPORT_COMMENT`: GED status and date are unchanged; the report VAOB is recorded as additive observation only. Step 8 may code this directly.

2. **Multi-approver report rows:** Some report rows in `consultant_match_report.xlsx` carry ambiguous canonical approver names (e.g., `"BET Structure / TERRELL"` merged). `stage_report_memory` would fail gate E4 if `approver_canonical` does not match any single step in `GED_OPERATIONS`. Resolution: `consultant_matcher.py` should produce one row per canonical approver. If it does not, the split logic must be added to the ingestion path, not to the composition engine.

3. **`SEPARATE_INSTANCE` reports:** If a consultant report references a document revision that corresponds to a `SEPARATE_INSTANCE` (non-ACTIVE) in Flat GED, the composition engine will find no matching `GED_OPERATIONS` row (gate E3 fails) and will silently skip the report. This is correct behaviour for Phase 2. Step 12 (Chain/Onion) is the correct place to revisit this.

4. **2-year floor freshness value:** The 730-day floor in gate E7 for PENDING rows is conservative. It may block legitimate historical reports for long-standing pending rows. The correct floor should be calibrated against the actual project timeline once operational data is available.

### Confidence level for Step 8 readiness

**HIGH.** All architectural decisions are explicit. The four merge rules are preserved and extended. The composition anchor is specified. The UI path is decided. The provenance vocabulary is closed. All edge cases are resolved. The implementer has sufficient specification to code Step 8 directly from this document without returning for clarification.

---

*End of FLAT_GED_REPORT_COMPOSITION.md*
