# STEP 03 — Onion Data Contract

**Status:** COMPLETE  
**Date:** 2026-04-27  
**Strategy ref:** CHAIN_ONION_MASTER_STRATEGY.md  
**Depends on:** STEP01_SOURCE_MAP.md, STEP02_CHAIN_CONTRACT.md  
**Feeds:** Step 09 (onion_engine.py, onion_scoring.py, onion_narrative.py)

---

## Purpose

This document is the authoritative definition of what an **Onion** is in this software.

It defines the six responsibility layers, their trigger conditions, their scoring models, the
`onion_responsibility` output schema, and the handoff specification for Step 09.

A developer must be able to implement Step 09 using only this document, STEP02_CHAIN_CONTRACT.md,
and STEP01_SOURCE_MAP.md — without inspecting any other file.

No code was modified in the production of this document.

---

## SECTION A — Onion Philosophy

### A.1 Layers Represent Stacked Causes, Not Statuses

A chain has a **state** (defined in STEP02_CHAIN_CONTRACT.md Section E).  
An onion has **layers** — each layer is an evidence-backed attribution of responsibility for
a specific type of problem.

The fundamental distinction:

- **Chain state** answers: _"Where is this document right now?"_
- **Onion layer** answers: _"Who is responsible for blocking, delaying, or degrading this document, and why?"_

A chain in state `WAITING_CORRECTED_INDICE` may simultaneously carry:
- Layer 1 (Contractor Quality) — because the submitter produced a document that was rejected twice
- Layer 2 (SAS Gate Friction) — because SAS was slow to respond before issuing the REF
- Layer 3 (Primary Consultant Delay) — because EGIS is still late on the corrected version

These three layers are independent. They answer different responsibility questions. They are not
mutually exclusive.

### A.2 One Chain May Have Multiple Active Layers Simultaneously

There is no upper limit on the number of layers that may fire for a single `family_key`. Layers
do not replace each other — they stack. Each fired layer adds one row to `onion_responsibility`.

A `family_key` that fires all six layers simultaneously produces six rows in `onion_responsibility`
— one per layer. This is expected and correct for severely distressed chains.

### A.3 Evidence-Backed Attribution Only

No layer may fire without a traceable, source-backed trigger. Every row in `onion_responsibility`
must link back to at least one `chain_events` row (via `family_key` + `layer_id`) from which the
`trigger_reason` and `evidence_count` are derived.

A layer that cannot point to at least one qualifying `chain_events` row must not fire.
An empty `evidence_count = 0` is a contract violation, not a valid output.

### A.4 Responsibility Attribution Is Forensic, Not Decorative

Onion output is intended for:
- Management review of chronic or blocked chains
- Identification of systemic failures (e.g., a SAS gate that is consistently slow)
- Contractor quality scoring over time

It is **not** a sentiment score, a penalty calculation, or a UI cosmetic layer.
Every attribution claim in the `narrative` column must be reproducible by re-running the engine
against the same `chain_events` input.

---

## SECTION B — Mandatory 6 Layers

---

### Layer 1 — Contractor Quality

**layer_id:** `L1_CONTRACTOR_QUALITY`  
**responsible_actor:** Submitter / emetteur (derived from `GED_OPERATIONS.actor_clean` on `OPEN_DOC` step)

#### B.1.1 Trigger Conditions

Layer fires when at least ONE of the following is true for a given `family_key`:

| Condition Code | Condition | Source |
|----------------|-----------|--------|
| `L1_T1` | `chain_versions.instance_count > 1` for any version | `DEBUG_TRACE.submission_instance_id` (or synthetic seq_N) |
| `L1_T2` | `chain_versions.requires_new_cycle_flag = True` for any version | `GED_OPERATIONS.requires_new_cycle` |
| `L1_T3` | `chain_register.total_versions >= 2` AND at least one version has `version_final_status = "SAS REF"` | `chain_register`, `chain_versions` |

If none of these conditions is true, Layer 1 does not fire. No row is written.

#### B.1.2 Metrics Used

| Metric | Source Column | Description |
|--------|--------------|-------------|
| `resubmission_count` | `chain_versions.instance_count` (sum across all versions for family) | Total number of submission instances beyond the first |
| `rejection_version_count` | `chain_versions.requires_new_cycle_flag` (count of True) | How many distinct versions ended in a SAS REF |
| `total_versions` | `chain_register.total_versions` | Total number of distinct indices submitted |
| `delay_days` | Max `chain_versions.version_delay_days` across all rejected versions | Delay accumulated during rejected-version cycles |

#### B.1.3 Issue Type Assignment

| Dominant Condition | issue_type |
|--------------------|-----------|
| Only `L1_T1` fires (multiple submissions of same version, no SAS REF) | `CHURN` |
| Only `L1_T2` or `L1_T3` fires (SAS REF, new cycle required) | `REJECTION` |
| Both `L1_T1` and (`L1_T2` or `L1_T3`) fire | `MULTI` |

#### B.1.4 Severity Model

Severity is computed from `rejection_version_count` and `total_versions`:

| Condition | Severity |
|-----------|----------|
| `total_versions = 2` AND `rejection_version_count = 1` AND `resubmission_count <= 2` | `LOW` |
| `total_versions = 2` AND `rejection_version_count = 1` AND `resubmission_count >= 3` | `MEDIUM` |
| `total_versions = 3` OR (`total_versions = 2` AND `rejection_version_count = 2`) | `HIGH` |
| `total_versions >= 4` OR `rejection_version_count >= 3` | `CRITICAL` |

First matching rule wins (evaluated top to bottom).

#### B.1.5 Confidence Model

| Condition | Confidence |
|-----------|-----------|
| `DEBUG_TRACE` available AND `submission_instance_id` confirmed (not synthetic) for all qualifying versions | 90 |
| `DEBUG_TRACE` available but some instances use synthetic seq_N | 70 |
| `DEBUG_TRACE` absent — all `instance_count` values are defaulted to 1 in `chain_versions` | 40 |

`evidence_count` = number of `chain_events` rows for this family where `step_type = "OPEN_DOC"` AND (`notes` contains `"Synthetic instance key"` triggers a confidence floor of 40 regardless of the above).

---

### Layer 2 — SAS Gate Friction

**layer_id:** `L2_SAS_GATE_FRICTION`  
**responsible_actor:** `"SAS"` (literal constant — the SAS review body is the actor)

#### B.2.1 Trigger Conditions

Layer fires when at least ONE of the following is true for the `family_key`, examining all
`chain_events` rows where `actor_type = "SAS"`:

| Condition Code | Condition | Source |
|----------------|-----------|--------|
| `L2_T1` | Any SAS event has `status = "REF"` AND `is_completed = True` | `chain_events.status`, `GED_OPERATIONS.is_completed` |
| `L2_T2` | Any SAS event has `delay_contribution_days > 0` | `chain_events.delay_contribution_days` |
| `L2_T3` | Any SAS event has `is_blocking = True` AND `event_date` is null (SAS has not responded) AND `version_delay_days > 14` | `chain_events.is_blocking`, `chain_events.event_date`, `chain_versions.version_delay_days` |

If no SAS step exists for this family, Layer 2 does not fire.

#### B.2.2 Metrics Used

| Metric | Source Column | Description |
|--------|--------------|-------------|
| `sas_ref_count` | `chain_events.status = "REF"` for SAS steps | Number of times SAS issued REF across all versions |
| `sas_delay_days` | `chain_events.delay_contribution_days` for SAS steps (sum) | Total days SAS contributed to delay across all versions |
| `sas_pending_versions` | Count of versions where SAS `is_blocking = True` and `event_date` is null | Versions still awaiting SAS response |

#### B.2.3 Issue Type Assignment

| Dominant Condition | issue_type |
|--------------------|-----------|
| `L2_T1` fires only (SAS REF, no abnormal delay) | `REJECTION` |
| `L2_T2` fires only (SAS delayed, no REF) | `DELAY` |
| `L2_T3` fires only (SAS blocking, no response) | `DORMANCY` |
| `L2_T1` AND `L2_T2` both fire | `MULTI` |
| `L2_T1` AND `L2_T3` both fire | `MULTI` |
| `L2_T2` AND `L2_T3` both fire | `MULTI` |

#### B.2.4 Severity Model

Computed from `sas_ref_count` and `sas_delay_days`:

| Condition | Severity |
|-----------|----------|
| `sas_ref_count = 0` AND `sas_delay_days` 1–7 | `LOW` |
| `sas_ref_count = 1` AND `sas_delay_days` <= 14 | `LOW` |
| `sas_ref_count = 1` AND `sas_delay_days` 8–21 | `MEDIUM` |
| `sas_ref_count = 1` AND `sas_delay_days` >= 22 | `HIGH` |
| `sas_ref_count = 2` OR (`sas_ref_count = 1` AND `sas_delay_days` >= 22) | `HIGH` |
| `sas_ref_count >= 3` OR `sas_delay_days` > 45 | `CRITICAL` |

First matching rule wins. When `L2_T3` is the sole trigger (pure dormancy, no completed REF),
`sas_ref_count = 0` — use `sas_delay_days` or `sas_pending_versions > 1` to determine MEDIUM/HIGH.

#### B.2.5 Confidence Model

| Condition | Confidence |
|-----------|-----------|
| `effective_source = "GED"` for all SAS events (raw GED data, SAS date confirmed) | 95 |
| `sas_response_date` present in `GED_OPERATIONS` for all completed SAS steps | 85 |
| SAS status derived from `status_clean` only (no `sas_response_date`) | 60 |
| `L2_T3` only (SAS blocking, no response, no date) — delay is computed, not recorded | 35 |

`evidence_count` = count of `chain_events` rows for this family where `actor_type = "SAS"`.

---

### Layer 3 — Primary Consultant Delay

**layer_id:** `L3_PRIMARY_CONSULTANT_DELAY`  
**responsible_actor:** `actor_clean` of the primary consultant with the highest `delay_contribution_days`
among all blocking primary consultants for the family. When multiple primary consultants are
equally culpable, the actor with the most recent non-null `event_date` is chosen as the
`responsible_actor` for the row. One row per family — the worst-offending primary consultant.

> Note: "Primary consultant" is defined exclusively by `_is_primary_approver(actor_clean) = True`
> using `_PRIMARY_APPROVER_KEYWORDS` from `src/query_library.py`. No alternative taxonomy is permitted.

#### B.3.1 Trigger Conditions

Layer fires when at least ONE `chain_events` row for this `family_key` satisfies:

| Condition Code | Condition | Source |
|----------------|-----------|--------|
| `L3_T1` | `actor_type = "CONSULTANT"` AND `_is_primary_approver(actor) = True` AND `delay_contribution_days > 0` | `chain_events` |
| `L3_T2` | `actor_type = "CONSULTANT"` AND `_is_primary_approver(actor) = True` AND `is_blocking = True` AND `event_date` is null | `chain_events` |
| `L3_T3` | `actor_type = "CONSULTANT"` AND `_is_primary_approver(actor) = True` AND `status` ∈ `{"REF", "REFSO"}` | `chain_events` |

#### B.3.2 Metrics Used

| Metric | Source Column | Description |
|--------|--------------|-------------|
| `primary_delay_days` | `chain_events.delay_contribution_days` for primary consultants (max per actor, then sum across all primaries) | Total primary consultant delay contribution |
| `primary_blocking_count` | Count of primary consultants with `is_blocking = True` | How many primary consultants are currently blocking |
| `primary_rejection_count` | Count of primary consultant events with `status` ∈ `{"REF", "REFSO"}` | How many primary rejection events occurred |
| `primary_no_response_count` | Count of primary consultants with `is_blocking = True` AND `event_date` null | Primary consultants who have not responded at all |

`delay_days` in `onion_responsibility` = `primary_delay_days` (max `delay_contribution_days` of the single `responsible_actor`).

#### B.3.3 Issue Type Assignment

| Dominant Condition | issue_type |
|--------------------|-----------|
| `L3_T2` only (blocking, no response, no REF, no delay_contribution recorded) | `DORMANCY` |
| `L3_T3` only (primary consultant rejected) | `REJECTION` |
| `L3_T1` only (delay recorded, responding but late) | `DELAY` |
| Two or more of `L3_T1`, `L3_T2`, `L3_T3` fire | `MULTI` |

#### B.3.4 Severity Model

Based on `primary_delay_days` (max `delay_contribution_days` of `responsible_actor`):

| Condition | Severity |
|-----------|----------|
| `primary_delay_days` 1–7 AND `primary_rejection_count = 0` | `LOW` |
| `primary_delay_days` 8–21 OR `primary_rejection_count = 1` | `MEDIUM` |
| `primary_delay_days` 22–45 OR `primary_rejection_count >= 2` | `HIGH` |
| `primary_delay_days` > 45 OR (`primary_no_response_count >= 2` AND `primary_delay_days` >= 22) | `CRITICAL` |

When `L3_T2` is the sole trigger (no `delay_contribution_days` recorded — consultant pending):
severity is computed from `primary_no_response_count` alone: 1 → `LOW`, 2 → `MEDIUM`, 3 → `HIGH`, ≥ 4 → `CRITICAL`.

#### B.3.5 Confidence Model

| Condition | Confidence |
|-----------|-----------|
| `effective_source = "GED"` for all qualifying primary events AND `response_date` confirmed in GED | 90 |
| `effective_source = "GED+REPORT_STATUS"` — status upgraded by report memory | 72 |
| `effective_source = "GED+REPORT_COMMENT"` only | 60 |
| `L3_T2` only (no response date, delay inferred from `data_date` − `submittal_date`) | 35 |

`evidence_count` = count of `chain_events` rows for this family where `actor_type = "CONSULTANT"` AND `_is_primary_approver(actor) = True`.

---

### Layer 4 — Secondary Consultant Delay

**layer_id:** `L4_SECONDARY_CONSULTANT_DELAY`  
**responsible_actor:** `actor_clean` of the secondary consultant with the highest `delay_contribution_days`
among all blocking secondary consultants for the family. Selection logic is identical to Layer 3
(worst offender; tie-break by most recent `event_date`).

> Note: "Secondary consultant" is defined as `_is_primary_approver(actor_clean) = False`.
> The same `_PRIMARY_APPROVER_KEYWORDS` rule from `src/query_library.py` applies.
> MOEX steps (`step_type = "MOEX"`) are excluded from Layer 4 — they are covered by Layer 5.

#### B.4.1 Trigger Conditions

Same structure as Layer 3, applied to secondary consultants:

| Condition Code | Condition | Source |
|----------------|-----------|--------|
| `L4_T1` | `actor_type = "CONSULTANT"` AND `_is_primary_approver(actor) = False` AND `delay_contribution_days > 0` | `chain_events` |
| `L4_T2` | `actor_type = "CONSULTANT"` AND `_is_primary_approver(actor) = False` AND `is_blocking = True` AND `event_date` null | `chain_events` |
| `L4_T3` | `actor_type = "CONSULTANT"` AND `_is_primary_approver(actor) = False` AND `status` ∈ `{"REF", "REFSO"}` | `chain_events` |

#### B.4.2 Metrics Used

Same structure as Layer 3 with the prefix `secondary_` replacing `primary_`:
- `secondary_delay_days`, `secondary_blocking_count`, `secondary_rejection_count`, `secondary_no_response_count`

`delay_days` in `onion_responsibility` = max `delay_contribution_days` of the single `responsible_actor`.

#### B.4.3 Issue Type Assignment

Identical mapping to Layer 3, applied to secondary conditions:

| Dominant Condition | issue_type |
|--------------------|-----------|
| `L4_T2` only | `DORMANCY` |
| `L4_T3` only | `REJECTION` |
| `L4_T1` only | `DELAY` |
| Two or more of `L4_T1`, `L4_T2`, `L4_T3` | `MULTI` |

#### B.4.4 Severity Model

Identical thresholds to Layer 3 applied to `secondary_delay_days` and `secondary_rejection_count`.

| Condition | Severity |
|-----------|----------|
| `secondary_delay_days` 1–7 AND `secondary_rejection_count = 0` | `LOW` |
| `secondary_delay_days` 8–21 OR `secondary_rejection_count = 1` | `MEDIUM` |
| `secondary_delay_days` 22–45 OR `secondary_rejection_count >= 2` | `HIGH` |
| `secondary_delay_days` > 45 OR (`secondary_no_response_count >= 2` AND `secondary_delay_days` >= 22) | `CRITICAL` |

When `L4_T2` is the sole trigger: `secondary_no_response_count` → `LOW` / `MEDIUM` / `HIGH` / `CRITICAL` (same thresholds as Layer 3 dormancy).

#### B.4.5 Confidence Model

Identical to Layer 3:

| Condition | Confidence |
|-----------|-----------|
| `effective_source = "GED"` AND `response_date` confirmed | 90 |
| `effective_source = "GED+REPORT_STATUS"` | 72 |
| `effective_source = "GED+REPORT_COMMENT"` only | 60 |
| `L4_T2` only (no response date, delay inferred) | 35 |

`evidence_count` = count of `chain_events` rows where `actor_type = "CONSULTANT"` AND `_is_primary_approver(actor) = False`.

---

### Layer 5 — MOEX Arbitration Delay

**layer_id:** `L5_MOEX_ARBITRATION_DELAY`  
**responsible_actor:** `"MOEX"` (literal constant — the MOEX arbitration body is the actor)

#### B.5.1 Trigger Conditions

Layer fires when at least ONE `chain_events` row for this `family_key` satisfies:

| Condition Code | Condition | Source |
|----------------|-----------|--------|
| `L5_T1` | `actor_type = "MOEX"` AND `delay_contribution_days > 0` | `chain_events` |
| `L5_T2` | `actor_type = "MOEX"` AND `is_blocking = True` AND `event_date` null | `chain_events` |

If no MOEX step exists for this family, Layer 5 does not fire.

#### B.5.2 Metrics Used

| Metric | Source Column | Description |
|--------|--------------|-------------|
| `moex_delay_days` | `chain_events.delay_contribution_days` for MOEX steps (sum) | Total days MOEX contributed to delay |
| `moex_pending` | `True` if any MOEX step has `is_blocking = True` AND `event_date` null | MOEX has not responded at all |
| `moex_versions_pending` | Count of distinct versions where MOEX is blocking without response | Scope of MOEX blockage |

`delay_days` in `onion_responsibility` = `moex_delay_days`.

#### B.5.3 Issue Type Assignment

| Dominant Condition | issue_type |
|--------------------|-----------|
| `L5_T2` only (MOEX blocking, no response at all) | `DORMANCY` |
| `L5_T1` only (MOEX responded but late) | `DELAY` |
| Both `L5_T1` and `L5_T2` fire | `MULTI` |

#### B.5.4 Severity Model

| Condition | Severity |
|-----------|----------|
| `moex_delay_days` 1–7 AND `moex_pending = False` | `LOW` |
| `moex_delay_days` 8–21 OR (`moex_pending = True` AND `moex_versions_pending = 1`) | `MEDIUM` |
| `moex_delay_days` 22–45 OR (`moex_pending = True` AND `moex_versions_pending >= 2`) | `HIGH` |
| `moex_delay_days` > 45 | `CRITICAL` |

When `L5_T2` is the sole trigger: `moex_versions_pending` → 1 = `MEDIUM`, 2 = `HIGH`, ≥ 3 = `CRITICAL`.

#### B.5.5 Confidence Model

| Condition | Confidence |
|-----------|-----------|
| MOEX `response_date` confirmed in GED AND `effective_source = "GED"` | 92 |
| MOEX `response_date` from GED, no report memory involvement | 85 |
| `L5_T2` only (no response date — delay inferred from `data_date` − `submittal_date` of latest version) | 38 |

`evidence_count` = count of `chain_events` rows for this family where `actor_type = "MOEX"`.

---

### Layer 6 — Data / Report Contradiction

**layer_id:** `L6_DATA_REPORT_CONTRADICTION`  
**responsible_actor:** The `source_filename` from `effective_responses_df` that introduced the
conflicting record. If multiple conflicting source files exist, use the one with the most
conflict rows. If the source filename is unavailable, use `"UNKNOWN_REPORT_SOURCE"`.

#### B.6.1 Trigger Conditions

Layer fires when at least ONE `chain_events` row for this `family_key` has:

| Condition Code | Condition | Source |
|----------------|-----------|--------|
| `L6_T1` | `source = "GED_CONFLICT_REPORT"` | `chain_events.source` (from `effective_responses_df.effective_source`) |

Layer does NOT fire for `GED+REPORT_STATUS` or `GED+REPORT_COMMENT` — those are enrichments, not contradictions.

#### B.6.2 Metrics Used

| Metric | Source Column | Description |
|--------|--------------|-------------|
| `conflict_row_count` | Count of `chain_events` rows with `source = "GED_CONFLICT_REPORT"` for this family | How many steps have a GED ↔ report conflict |
| `conflict_actors` | Distinct `actor` values from conflicting rows | Which approvers have contradictory records |
| `conflict_versions` | Distinct `version_key` values from conflicting rows | How many versions are affected |

`delay_days` in `onion_responsibility` = 0 (contradiction does not directly produce a measured delay; it produces analytical uncertainty). If the contradiction has caused a step to remain `is_blocking = True` beyond its `computed_phase_deadline`, `delay_days` may be set to `delay_contribution_days` from that step — but only if directly traceable.

#### B.6.3 Issue Type Assignment

Layer 6 always produces `issue_type = "CONTRADICTION"` as a baseline.

Exception: if any conflicting `chain_events` row also has `is_blocking = True` AND `delay_contribution_days > 0`, the issue_type is upgraded to `MULTI` (contradiction + blocking delay).

#### B.6.4 Severity Model

Based on `conflict_row_count` and `conflict_versions`:

| Condition | Severity |
|-----------|----------|
| `conflict_row_count = 1` AND `conflict_versions = 1` | `LOW` |
| `conflict_row_count` 2–3 OR `conflict_versions >= 2` | `MEDIUM` |
| `conflict_row_count` 4–5 | `HIGH` |
| `conflict_row_count >= 6` | `CRITICAL` |

#### B.6.5 Confidence Model

| Condition | Confidence |
|-----------|-----------|
| `effective_source = "GED_CONFLICT_REPORT"` confirmed by `effective_responses.py` merge logic | 80 |
| `source_filename` is non-null and traceable to a specific uploaded report | 80 |
| `source_filename` is null (source of conflict is unknown) | 50 |

`evidence_count` = `conflict_row_count`.

---

## SECTION C — `onion_responsibility` Schema

**Granularity:** One row per `family_key` + `layer_id` that fires.  
**Output file:** `output/chain_onion/ONION_RESPONSIBILITY.csv`

A `family_key` that fires N layers produces exactly N rows in this table. A layer that does not
fire for a given `family_key` produces zero rows — it is not written with a null/empty record.

| Column | Type | Description |
|--------|------|-------------|
| `family_key` | string | `FAMILY_KEY` = `str(numero)`. Foreign key → `chain_register.family_key`. Composite primary key with `layer_id`. |
| `layer_id` | string | One of: `L1_CONTRACTOR_QUALITY`, `L2_SAS_GATE_FRICTION`, `L3_PRIMARY_CONSULTANT_DELAY`, `L4_SECONDARY_CONSULTANT_DELAY`, `L5_MOEX_ARBITRATION_DELAY`, `L6_DATA_REPORT_CONTRADICTION`. Composite primary key with `family_key`. |
| `layer_name` | string | Human-readable layer name (see layer definitions in Section B). Example: `"Contractor Quality"`. |
| `responsible_actor` | string | The actor responsible for this layer. See per-layer definitions in Section B. Never null — use `"UNKNOWN"` with a logged warning if the actor cannot be determined. |
| `issue_type` | string | One of: `DELAY`, `REJECTION`, `CHURN`, `DORMANCY`, `CONTRADICTION`, `MULTI`. Assigned per the issue_type rules in each layer's Section B definition. Never null. Never defaulted to `DELAY` without meeting the `DELAY` trigger condition. |
| `severity` | string | One of: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. Computed from the deterministic thresholds in Section D. Never null. |
| `confidence` | int | Integer 10–100. Computed from the source quality rules in Section E. Never null. |
| `delay_days` | int | Days of delay attributable to this layer for this family. Zero (not null) when the layer is not delay-typed (e.g., pure `REJECTION` or `CONTRADICTION` with no measured delay). Must be sourced from `delay_contribution_days` in `chain_events` — never estimated. |
| `evidence_count` | int | Number of `chain_events` rows that satisfied at least one trigger condition for this layer. Must be ≥ 1. A value of 0 is a contract violation and must cause the row to be rejected with a logged error. |
| `trigger_reason` | string | Machine-readable code(s) of the trigger condition(s) that fired. Format: comma-separated list of condition codes, e.g. `"L3_T1,L3_T2"`. Never null. |
| `narrative` | string | Human-readable explanation of why this layer fired for this family. Must cite specific actors, dates, or counts from source data. Must not use subjective language. Maximum 280 characters. Example: `"EGIS contributed 18 delay days across version B (delay_contribution_days=18). Still blocking on version C (no response)."` |

### C.1 Composite Primary Key Constraint

The pair `(family_key, layer_id)` must be unique across all rows. The onion engine must validate
this constraint before writing output. If a duplicate pair is detected during engine execution,
log an ERROR and keep the row with the higher `evidence_count`. If `evidence_count` is equal,
keep the row with the higher `severity` (CRITICAL > HIGH > MEDIUM > LOW). Never silently drop rows.

### C.2 Null Policy

- `family_key`, `layer_id`, `layer_name`, `responsible_actor`, `issue_type`, `severity`, `trigger_reason`, `narrative`: never null.
- `confidence`: never null.
- `delay_days`: never null (use 0 for non-delay layers).
- `evidence_count`: never null, never zero (see above).

---

## SECTION D — Severity Model

The following four severity levels are the only permitted values for the `severity` column.
Thresholds are deterministic — they are computed from numeric source fields only. No human
judgment or AI inference is permitted in severity assignment.

| Severity | Definition |
|----------|-----------|
| `LOW` | The responsible actor has contributed a measurable but minor problem. The chain is recoverable without escalation. |
| `MEDIUM` | The responsible actor's contribution is significant enough to warrant attention in a routine review. |
| `HIGH` | The responsible actor's contribution is materially damaging the chain's progress. Escalation may be warranted. |
| `CRITICAL` | The responsible actor's contribution represents a systemic or severe failure. Immediate action is warranted. |

### D.1 Universal Thresholds (apply when layer-specific rules in Section B do not override)

These are the fallback thresholds when a layer's specific model does not cover a particular
combination of conditions.

**Delay-based severity (applies when `issue_type` ∈ `{DELAY, DORMANCY, MULTI}`):**

| `delay_days` | Severity |
|:------------:|----------|
| 1 – 7 | `LOW` |
| 8 – 21 | `MEDIUM` |
| 22 – 45 | `HIGH` |
| > 45 | `CRITICAL` |

**Count-based severity (applies when `issue_type` ∈ `{REJECTION, CHURN}`):**

| Event count (rejections or resubmissions) | Severity |
|:-----------------------------------------:|----------|
| 1 | `LOW` |
| 2 | `MEDIUM` |
| 3 | `HIGH` |
| ≥ 4 | `CRITICAL` |

**Contradiction severity (applies to Layer 6, `issue_type = CONTRADICTION`):**

| `conflict_row_count` | Severity |
|:--------------------:|----------|
| 1 | `LOW` |
| 2–3 | `MEDIUM` |
| 4–5 | `HIGH` |
| ≥ 6 | `CRITICAL` |

**MULTI severity:** When `issue_type = MULTI`, compute the severity for each contributing
component separately using the applicable rule above, then take the **maximum** severity across
all components. Do not average. Do not downgrade.

### D.2 Severity Escalation Lock

Once `CRITICAL` severity is assigned to a row, no downstream logic may downgrade it to a lower
level. The severity assigned at row-write time is final.

---

## SECTION E — Confidence Model

Confidence is an integer in the range **10 to 100** (inclusive). It represents the reliability
of the attribution for a given `onion_responsibility` row, based on the quality and directness
of the source evidence.

### E.1 Source Quality Hierarchy

From highest to lowest reliability:

| Tier | Source Description | Confidence Range |
|:----:|--------------------|:---------------:|
| 1 | **GED direct** — status and date both sourced from raw GED; `effective_source = "GED"` or `"GED_OPERATIONS"`; `submission_instance_id` confirmed in `DEBUG_TRACE.csv` | 85 – 100 |
| 2 | **DEBUG_TRACE** — `submission_instance_id` available and non-synthetic; supports instance attribution in Layers 1, 3, 4 | 70 – 84 |
| 3 | **Derived / composed** — `effective_source = "GED+REPORT_STATUS"` or `"GED+REPORT_COMMENT"`; report memory contributed to the evidence; or `visa_global` derived via `_derive_visa_global()` | 50 – 69 |
| 4 | **Heuristic / synthetic** — delay inferred from `data_date` minus `submittal_date` without a confirmed `response_date`; synthetic `seq_N` instance keys used; `DEBUG_TRACE` absent | 10 – 49 |

### E.2 Confidence Computation Rules

1. Start at the tier 1 ceiling (100) for a given row.
2. Apply the first applicable deduction below (do not stack deductions — use the single most
   applicable rule):

| Condition | Confidence |
|-----------|-----------|
| All qualifying `chain_events` rows have `effective_source = "GED"` | 90–100 (see per-layer rules in Section B) |
| `effective_source = "GED+REPORT_STATUS"` for at least one qualifying event | max 72 |
| `effective_source = "GED+REPORT_COMMENT"` for at least one qualifying event, no `GED+REPORT_STATUS` | max 60 |
| `effective_source = "GED_CONFLICT_REPORT"` is the trigger itself (Layer 6) | max 80 |
| At least one qualifying `chain_events` row uses synthetic `instance_key` (`seq_N`) | max 55 |
| `DEBUG_TRACE` absent (all `instance_count` defaulted to 1) | max 40 |
| `event_date` is null for all qualifying events (no recorded date, delay inferred only) | max 35 |

3. The final confidence value is the **minimum** of the applicable per-layer rule (Section B)
   and the applicable row-level deduction above.
4. Confidence may never be set below 10 for any row that has `evidence_count >= 1`.
5. Confidence may never be set above the per-layer ceiling defined in Section B for that layer.

### E.3 Confidence Is Not a Score

Confidence does not represent how much responsibility the actor bears. It represents how certain
the engine is that the attribution is correct given the available data. A `confidence = 35`
row with `severity = HIGH` means: the actor almost certainly has HIGH-severity responsibility,
but the evidence is weaker than desired (e.g., no response date recorded).

---

## SECTION F — Cross-Layer Examples

The following examples illustrate how multiple layers may fire simultaneously for a single `family_key`.
All column values shown are derived deterministically from source data.

---

### F.1 Example: Three-Layer Activation

**Scenario:**  
Document `numero = 248000`. History:
- Indice A: submitted, SAS REF after 28-day review (computed_sas_deadline was 15 days → 13 days over).
  `requires_new_cycle = True`.
- Indice B: submitted, SAS VAO after 5 days. EGIS (primary) currently blocking — `is_blocking = True`,
  `delay_contribution_days = 22`. No response from EGIS (`event_date` null).
- `DEBUG_TRACE` available; `submission_instance_id` confirmed for indice A (2 instances of indice A submitted).

**Layers that fire:**

| family_key | layer_id | responsible_actor | issue_type | severity | confidence | delay_days | evidence_count | trigger_reason |
|------------|----------|-------------------|-----------|----------|-----------|-----------|---------------|----------------|
| 248000 | L1_CONTRACTOR_QUALITY | emetteur_of_248000 | MULTI | MEDIUM | 90 | 13 | 2 | L1_T1,L1_T2 |
| 248000 | L2_SAS_GATE_FRICTION | SAS | MULTI | HIGH | 85 | 13 | 2 | L2_T1,L2_T2 |
| 248000 | L3_PRIMARY_CONSULTANT_DELAY | EGIS | DORMANCY | HIGH | 35 | 22 | 1 | L3_T1,L3_T2 |

**Explanation:**
- L1 fires on `L1_T1` (indice A had 2 instances) + `L1_T2` (requires_new_cycle on indice A).
  `total_versions = 2`, `rejection_version_count = 1`, `resubmission_count = 2` → MEDIUM.
- L2 fires on `L2_T1` (SAS REF on indice A) + `L2_T2` (SAS delay 13 days over deadline) →
  `sas_ref_count = 1`, `sas_delay_days = 13` → HIGH.
- L3 fires on `L3_T1` (delay_contribution_days = 22) + `L3_T2` (is_blocking = True, no event_date).
  `delay_days = 22` → HIGH. Confidence = 35 because `event_date` is null (delay inferred, not recorded).

Layers L4, L5, L6 do not fire — no secondary consultant blocking, no MOEX, no GED conflicts.

---

### F.2 Example: MOEX Dormancy + Secondary Consultant CHURN

**Scenario:**  
Document `numero = 312500`. History:
- Indice A only. SAS VAO. All primary consultants VAO. Two secondary consultants (`Bureau Signalétique`,
  `Commission Voirie`) with `delay_contribution_days = 8` and `delay_contribution_days = 5` respectively.
  Both are now VAO (responded, not currently blocking). MOEX step: `is_blocking = True`, no response,
  no `event_date` — submitted 38 days ago.
- `DEBUG_TRACE` available; indice A has 3 instances (`instance_count = 3`) due to 2 re-submissions
  after MOEX requested clarifications (not a SAS rejection — `requires_new_cycle = False`).

**Layers that fire:**

| family_key | layer_id | responsible_actor | issue_type | severity | confidence | delay_days | evidence_count | trigger_reason |
|------------|----------|-------------------|-----------|----------|-----------|-----------|---------------|----------------|
| 312500 | L1_CONTRACTOR_QUALITY | emetteur_of_312500 | CHURN | LOW | 90 | 0 | 3 | L1_T1 |
| 312500 | L4_SECONDARY_CONSULTANT_DELAY | Bureau Signalétique | DELAY | MEDIUM | 90 | 8 | 2 | L4_T1 |
| 312500 | L5_MOEX_ARBITRATION_DELAY | MOEX | DORMANCY | HIGH | 38 | 0 | 1 | L5_T2 |

**Explanation:**
- L1: `instance_count = 3` → `L1_T1`. No SAS REF, so issue_type = `CHURN`. `resubmission_count = 2`,
  `rejection_version_count = 0`, `total_versions = 1` → LOW severity.
- L4: secondary consultants contributed delay. Responsible actor = `Bureau Signalétique` (higher `delay_contribution_days`).
  8 delay days → MEDIUM.
- L5: MOEX blocking, no response, 38 inferred days since submission. Issue_type = `DORMANCY`.
  `moex_pending = True`, `moex_versions_pending = 1` → MEDIUM from count rule, but `moex_delay_days`
  is inferred at 38 days → HIGH (22–45 band). Take maximum → HIGH.
  Confidence = 38 (no event_date for MOEX step).

L2, L3, L6 do not fire — SAS gave VAO, all primaries responded with VAO, no GED conflicts.

---

### F.3 Example: Six-Layer Full Activation

**Scenario:**  
A severely distressed chain: `numero = 99999`.
- Indice A: SAS REF, indice B: SAS REF again, indice C: SAS VAO (but 35-day SAS review on indice C).
- Indice C: EGIS `delay_contribution_days = 52`. `Bureau Signalétique` has `is_blocking = True`,
  no response. MOEX blocking, no response, inferred 30 days pending. 3 `GED_CONFLICT_REPORT` rows.
  `instance_count` for indice B = 3 (three submissions of indice B before SAS issued REF).
  `effective_source = "GED_CONFLICT_REPORT"` on 3 rows involving `Bureau Signalétique`.

**All 6 layers fire.** Issue types: L1=MULTI, L2=MULTI, L3=DELAY, L4=DORMANCY, L5=DORMANCY, L6=MULTI.
Severities: L1=HIGH, L2=CRITICAL, L3=CRITICAL, L4=MEDIUM, L5=HIGH, L6=MEDIUM.

This is a fully documented CRITICAL chain requiring executive escalation.

---

## SECTION G — Forbidden Logic

The following practices are **explicitly prohibited** in Step 09 (onion engine) and all downstream
consumers of `ONION_RESPONSIBILITY.csv`. Violations invalidate the onion contract.

### G.1 No Blame Without Evidence

A layer must not fire unless at least one `chain_events` row satisfies a trigger condition from
Section B. Firing a layer because a chain "looks like it might have" a contractor quality problem
is forbidden. `evidence_count = 0` is a hard blocker — the row must not be written.

### G.2 No Duplicate Layer Rows

The pair `(family_key, layer_id)` must be unique. The engine must validate uniqueness before writing
output. If a duplicate is produced by a logic error, the engine must log an ERROR (not a warning),
resolve by the rules in Section C.1, and write exactly one row.

### G.3 No Subjective Wording in `narrative`

The `narrative` column must describe observable, source-traceable facts only. Prohibited words
and phrases include but are not limited to:

- _"appears to"_, _"seems like"_, _"probably"_, _"might be"_, _"we believe"_
- _"poor performance"_, _"negligent"_, _"unacceptable"_, _"irresponsible"_
- Any superlative that is not directly supported by the numeric evidence

Acceptable narrative style:
> `"EGIS has delay_contribution_days=52 on version C (event_seq=14). is_blocking=True. No event_date recorded."`

Unacceptable narrative style:
> `"EGIS appears to be ignoring this document and is probably responsible for the project delay."`

### G.4 No AI Guessing Inside the Engine

The onion engine (`onion_engine.py`, `onion_scoring.py`, `onion_narrative.py`) must be fully
deterministic Python code. No LLM inference, no probabilistic model, no NLP classification is
permitted inside the engine. The `narrative` column is assembled from string templates populated
with source values — it is not generated by a language model at runtime.

### G.5 No Collapsing All Responsibility into DELAY

`issue_type` must be set according to the per-layer rules in Section B. A rejection event must
produce `issue_type = REJECTION` or `MULTI` — it must never be reported as `DELAY` unless the
rejection also produced a measured `delay_contribution_days > 0`. A dormancy event must produce
`DORMANCY` — a step that has not responded at all has not "delayed" in the measured sense; it
has gone silent. Conflating all problem types into `DELAY` erases the forensic value of the
Onion and is explicitly forbidden.

### G.6 No Cross-Step Responsibility Transfer

Layer 3 (Primary Consultant Delay) may only be triggered by `chain_events` rows where
`actor_type = "CONSULTANT"` AND `_is_primary_approver(actor) = True`. It must not absorb MOEX
steps, SAS steps, or secondary consultant steps. Each layer's trigger scope is fixed in Section B.

### G.7 No Silent Null Propagation

A null value in a source column that a layer depends on must produce either:
- A layer that does not fire (if the null prevents satisfying a trigger condition), OR
- A reduced confidence value (if the null reduces evidence quality but the trigger still fires)

A null must never be silently treated as 0 (for day counts) or as False (for boolean fields)
without a logged WARNING.

---

## SECTION H — Step 09 Implementation Handoff

Step 09 implements `src/chain_onion/onion_engine.py`, `onion_scoring.py`, and `onion_narrative.py`.
This section defines exactly what Step 09 must consume, produce, and validate.

### H.1 Mandatory Inputs

Step 09 reads from the outputs of Steps 04–08. All inputs are in `output/chain_onion/`:

| Input | Source File | Key Columns Used |
|-------|-------------|-----------------|
| `chain_register` | `CHAIN_REGISTER.csv` | `family_key`, `total_versions`, `total_instances`, `cumulative_delay_days`, `current_state`, `chronic_flag`, `void_flag`, `abandoned_flag` |
| `chain_versions` | `CHAIN_EVENTS.csv` (versions sub-table, or `CHAIN_VERSIONS.csv` if separate) | `family_key`, `version_key`, `instance_count`, `requires_new_cycle_flag`, `version_final_status`, `version_delay_days` |
| `chain_events` | `CHAIN_EVENTS.csv` | `family_key`, `version_key`, `instance_key`, `actor`, `actor_type`, `status`, `event_date`, `source`, `is_blocking`, `delay_contribution_days`, `notes` |

Step 09 must **not** read directly from `FLAT_GED.xlsx` or `DEBUG_TRACE.csv`. All source data
must come through the chain output tables produced by Steps 04–08. This ensures the onion
engine is downstream-only and does not depend on raw artifact paths.

### H.2 Mandatory Output

Step 09 writes exactly one file:

`output/chain_onion/ONION_RESPONSIBILITY.csv`

Schema: as defined in Section C. All columns required. No optional columns. No extra columns.

### H.3 Engine Processing Order

```
1. Load chain_register, chain_versions, chain_events into DataFrames.
2. For each unique family_key in chain_register:
   a. Extract all chain_versions rows for this family_key.
   b. Extract all chain_events rows for this family_key.
   c. Evaluate Layer 1 trigger conditions → write row if fires.
   d. Evaluate Layer 2 trigger conditions → write row if fires.
   e. Evaluate Layer 3 trigger conditions → write row if fires.
   f. Evaluate Layer 4 trigger conditions → write row if fires.
   g. Evaluate Layer 5 trigger conditions → write row if fires.
   h. Evaluate Layer 6 trigger conditions → write row if fires.
3. Validate (family_key, layer_id) uniqueness across all produced rows.
4. Validate evidence_count >= 1 for all rows.
5. Write ONION_RESPONSIBILITY.csv.
6. Log summary: total families processed, total rows written, layers fired by count, any validation errors.
```

### H.4 `_is_primary_approver` Import Rule

Step 09 must use `_is_primary_approver()` from `src/query_library.py` directly — or replicate it
verbatim in `src/chain_onion/onion_engine.py` if the import creates a circular dependency.
Under no circumstances may Step 09 define an alternative keyword list or classification method.

### H.5 Validation Harness Requirements

The validation harness (Step 14) must check the following post-conditions on `ONION_RESPONSIBILITY.csv`:

| Check | Pass Condition |
|-------|---------------|
| Primary key uniqueness | All `(family_key, layer_id)` pairs are unique |
| No null mandatories | All non-nullable columns (see Section C.2) contain non-null values |
| issue_type vocabulary | All `issue_type` values ∈ `{DELAY, REJECTION, CHURN, DORMANCY, CONTRADICTION, MULTI}` |
| severity vocabulary | All `severity` values ∈ `{LOW, MEDIUM, HIGH, CRITICAL}` |
| layer_id vocabulary | All `layer_id` values ∈ the six defined codes |
| evidence_count integrity | All `evidence_count` ≥ 1 |
| confidence range | All `confidence` values in [10, 100] |
| delay_days type | All `delay_days` values are non-negative integers |
| trigger_reason format | All `trigger_reason` values match pattern `L[1-6]_T[1-9](,L[1-6]_T[1-9])*` |
| family_key referential integrity | All `family_key` values exist in `CHAIN_REGISTER.csv` |

Any failed check must be reported as a validation error in `output/chain_onion/validation_report.md`.

### H.6 What Step 09 Must NOT Do

- Must not modify `chain_events`, `chain_versions`, or `chain_register` files.
- Must not read `FLAT_GED.xlsx`, `DEBUG_TRACE.csv`, or `effective_responses_df` directly.
- Must not call `build_effective_responses()` or any function from `src/effective_responses.py`.
- Must not generate `narrative` text using any AI/LLM at runtime.
- Must not write any file outside `output/chain_onion/`.

---

## What Was Analyzed

- `docs/CHAIN_ONION_MASTER_STRATEGY.md` — full read; six-layer taxonomy, input sources, output targets, and rules confirmed.
- `docs/STEP01_SOURCE_MAP.md` — full read; DEBUG_TRACE 23-column schema, GED_OPERATIONS 37-column schema, `effective_source` five-value vocabulary, `_is_primary_approver()` source location, and all identified risks incorporated.
- `docs/STEP02_CHAIN_CONTRACT.md` — full read; chain_register, chain_versions, chain_events schemas, chain state vocabulary, Primary/Secondary classification rules, and Section I (step 04 handoff) used as direct inputs to Section H of this document.

## What Was Changed

- Created: `docs/STEP03_ONION_CONTRACT.md` (this file).
- Updated: `docs/CHAIN_ONION_STEP_TRACKER.md` — Step 03 marked COMPLETE.
- No `.py` files were modified.

## What Now Works

- Complete authoritative definition of what an Onion layer is.
- Six layers fully specified with trigger conditions, metrics, issue_type mapping, severity model, and confidence model.
- `onion_responsibility` schema fully defined including mandatory `issue_type` column with restricted vocabulary.
- Severity model is deterministic and threshold-based — no judgment calls at runtime.
- Confidence model is tiered by source quality (GED direct > DEBUG_TRACE > derived > heuristic).
- Cross-layer examples in Section F show all five `issue_type` values and the MULTI upgrade path.
- Forbidden Logic (Section G) explicitly prevents the six most dangerous failure modes.
- Step 09 handoff (Section H) gives an unambiguous implementation target: inputs, output, processing order, validation checks.

## What Does Not Yet Exist

- `src/chain_onion/` directory (Step 04).
- `output/chain_onion/` directory (Step 04).
- Any implementation code (Steps 04–09).

## Next Blockers

1. **Step 04** — Source loader implementation (`source_loader.py`). Now unblocked: both Step 02 and Step 03 contracts are complete. Primary technical risks: `submission_instance_id` availability (DEBUG_TRACE batch-only artifact) and the `doc_id ↔ (numero, indice)` identity bridge from `stage_read_flat`.

2. **Step 09** — Onion engine implementation. Blocked on Steps 04–08 (chain tables must exist before the engine can run). Key implementation note: `_is_primary_approver()` must be imported from or replicated verbatim from `src/query_library.py` — no alternative.

3. **Layer 1 actor resolution** — The submitter/emetteur for `responsible_actor` in Layer 1 comes from the `OPEN_DOC` step's `actor_clean` in `chain_events`. Step 05 (family grouping) and Step 06 (timeline events) must ensure the `OPEN_DOC` event is present and correctly attributed before Step 09 runs.

4. **Layer 6 source_filename** — The `source_filename` for `responsible_actor` in Layer 6 requires the `effective_responses_df` to carry `source_filename` through to `chain_events.source` or as a supplementary column. Step 06 must capture this from `effective_responses.py`'s output before it is discarded.
