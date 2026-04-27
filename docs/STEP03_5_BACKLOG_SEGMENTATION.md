# STEP 03.5 — Backlog Segmentation Amendment

**Status:** COMPLETE  
**Date:** 2026-04-27  
**Amendment to:** STEP02_CHAIN_CONTRACT.md (chain_register schema), STEP03_ONION_CONTRACT.md (severity model)  
**Strategy ref:** CHAIN_ONION_MASTER_STRATEGY.md  
**Feeds:** Steps 05, 07, 09 (family grouper, chain classifier, onion engine) and dashboard layer

---

## Purpose

The GF portfolio contains a large body of chains submitted in 2024–2025 that remain administratively
open in GED but have had no real operational activity for many months. Treating these legacy chains
identically to actively contested chains produces misleading KPIs: inflated blocking counts, false
CRITICAL onion layers, and dashboard noise that obscures the chains actually requiring action.

This amendment introduces a **portfolio bucket** segmentation layer that is computed deterministically
from dates and chain states already available in `chain_register` and `chain_events`. It does not
modify chain states (Section E of STEP02). It adds four new fields to `chain_register`, defines
three mutually exclusive buckets, specifies how the dashboard must filter by default, and defines
severity downgrade rules for the Onion engine.

**Operational horizon date:** `2025-09-01` (configurable — see Section B.4).  
All references to "September 2025" in this document mean `OPERATIONAL_HORIZON_DATE = "2025-09-01"`.

No code was modified in the production of this document.

---

## SECTION A — Portfolio Bucket Definitions

Three mutually exclusive values for `portfolio_bucket`:

---

### A.1 `LIVE_OPERATIONAL`

**Definition:** The chain is open AND has evidence of real activity at or after `OPERATIONAL_HORIZON_DATE`.
These chains are the primary focus of daily and weekly management reviews. All KPIs, onion scoring,
and dashboard alerts apply at full weight.

**Criteria:**
- `current_state` is NOT in `{CLOSED_VAO, CLOSED_VSO, VOID_CHAIN, DEAD_AT_SAS_A}`
- AND (`last_real_activity_date >= OPERATIONAL_HORIZON_DATE`
        OR `latest_submission_date >= OPERATIONAL_HORIZON_DATE`)

**Operational meaning:** Something real happened on this chain after the cutoff. A consultant
responded, a SAS review was issued, or the document was resubmitted. This chain is alive.

---

### A.2 `LEGACY_BACKLOG`

**Definition:** The chain is open (not finally resolved) but all recorded activity predates
`OPERATIONAL_HORIZON_DATE`. The chain is administratively open in GED — no closure event has been
recorded — but operationally dead: no actor has touched it since before the cutoff.

**Criteria:**
- `current_state` is NOT in `{CLOSED_VAO, CLOSED_VSO, VOID_CHAIN, DEAD_AT_SAS_A}`
- AND `last_real_activity_date < OPERATIONAL_HORIZON_DATE` (or `last_real_activity_date` is null)
- AND `latest_submission_date < OPERATIONAL_HORIZON_DATE`

**Operational meaning:** This chain exists in GED as open but no stakeholder has acted on it for
months. It may represent a document that was superseded informally without a GED closure, a
project that was cancelled, or a genuine oversight. It should not drive blocking counts or
escalation alerts, but it must remain visible for audit and recovery purposes.

---

### A.3 `ARCHIVED_HISTORICAL`

**Definition:** The chain has reached a terminal state — either a final approval, a void outcome,
or a dead-at-SAS outcome — regardless of when that occurred.

**Criteria:**
- `current_state` ∈ `{CLOSED_VAO, CLOSED_VSO, VOID_CHAIN, DEAD_AT_SAS_A}`

**Operational meaning:** No further workflow action is expected or possible for this chain.
It is retained for historical reporting, contractor quality audits, and trend analysis.
It must not appear in live dashboards unless explicitly requested.

---

## SECTION B — Deterministic Assignment Logic

### B.1 Classification Priority

The following three conditions are evaluated in strict order. The first condition that evaluates
to True determines the `portfolio_bucket`. Only one bucket is assigned per `family_key`.

```
PRIORITY 1 — ARCHIVED_HISTORICAL
  IF current_state ∈ {CLOSED_VAO, CLOSED_VSO, VOID_CHAIN, DEAD_AT_SAS_A}
  → portfolio_bucket = ARCHIVED_HISTORICAL

PRIORITY 2 — LIVE_OPERATIONAL
  ELIF (last_real_activity_date >= OPERATIONAL_HORIZON_DATE)
       OR (latest_submission_date >= OPERATIONAL_HORIZON_DATE)
  → portfolio_bucket = LIVE_OPERATIONAL

PRIORITY 3 — LEGACY_BACKLOG
  ELSE
  → portfolio_bucket = LEGACY_BACKLOG
```

**Design rationale for priority ordering:**

Priority 1 (ARCHIVED before LIVE) is intentional. A chain that was submitted in October 2025
and has already reached `CLOSED_VAO` should be classified as ARCHIVED_HISTORICAL, not
LIVE_OPERATIONAL. The terminal state is more operationally significant than the submission date.
A recently closed chain is done — it should leave the live dashboard.

Priority 2 (LIVE before LEGACY) ensures that a chain submitted before the cutoff but with a
recent response (e.g., a consultant finally replied in November 2025 to a 2024 submission) is
treated as operationally live. Recency of activity takes precedence over age of submission.

### B.2 `last_real_activity_date` Definition

`last_real_activity_date` is the most recent recorded date across all of the following source
columns for all `chain_events` rows belonging to this `family_key`:

| Source column | Step type | Counts as real activity? |
|--------------|-----------|:------------------------:|
| `event_date` where `actor_type = "OPEN_DOC"` (= `submittal_date`) | Submission | ✅ Yes |
| `event_date` where `actor_type = "SAS"` (= `response_date` or `sas_response_date`) | SAS review | ✅ Yes |
| `event_date` where `actor_type = "CONSULTANT"` (= `response_date`) | Consultant response | ✅ Yes |
| `event_date` where `actor_type = "MOEX"` (= `response_date`) | MOEX decision | ✅ Yes |
| `computed_sas_deadline`, `computed_phase_deadline` | Any | ❌ No — system-computed dates are not real activity |
| `event_date = null` (pending, no response recorded) | Any | ❌ No — absence of a date is not activity |

**Computation:** `last_real_activity_date = max(event_date) where event_date IS NOT NULL`
across all `chain_events` rows for this `family_key`.

If ALL `chain_events` rows for a `family_key` have `event_date = null` (which would mean even
the OPEN_DOC submittal date is missing), then `last_real_activity_date = null`. In this case:
- `stale_days = null` (logged as WARNING — cannot compute staleness without a date)
- `portfolio_bucket` assignment falls back to date-comparison on `latest_submission_date` alone
- If `latest_submission_date` is also null, `portfolio_bucket = LEGACY_BACKLOG` and a WARNING
  is logged: `"family_key {X}: no activity date available — assigned LEGACY_BACKLOG by default"`

### B.3 `stale_days` Definition

```
stale_days = data_date - last_real_activity_date   (integer, days)
```

Where `data_date` is the pipeline run date from `GED_OPERATIONS` (the `data_date_used` field
from `DEBUG_TRACE.csv`, or the `data_date` returned by `build_chain_source()` in Step 04).

- If `last_real_activity_date` is null: `stale_days = null` (logged WARNING).
- `stale_days` is always ≥ 0. If computed as negative (data_date before last_real_activity_date
  due to a data anomaly), set to 0 and log a WARNING with the family_key.
- `stale_days` is computed at chain_register build time (Step 05). It is a point-in-time
  snapshot — it reflects staleness at the time of the pipeline run, not an absolute property.

### B.4 `OPERATIONAL_HORIZON_DATE` — Configurable Constant

`OPERATIONAL_HORIZON_DATE` must be exposed as a named constant in
`src/chain_onion/chain_classifier.py` (Step 07):

```python
OPERATIONAL_HORIZON_DATE: date = date(2025, 9, 1)
```

It must never be hard-coded as a string literal inside logic branches. All date comparisons
for `portfolio_bucket` assignment must reference this constant by name.

Changing `OPERATIONAL_HORIZON_DATE` changes which chains fall into `LIVE_OPERATIONAL` vs
`LEGACY_BACKLOG`. The value `2025-09-01` is the default binding for this project and reflects
the project owner's judgment that chains with no activity before September 2025 are not
operationally meaningful for current management decisions.

---

## SECTION C — New Fields for `chain_register`

The following four columns are added to `chain_register` (STEP02_CHAIN_CONTRACT.md Section B).
They are appended after the existing columns and are computed by Step 07 (chain_classifier).

| Column | Type | Nullable? | Description |
|--------|------|:---------:|-------------|
| `portfolio_bucket` | string | No | One of: `LIVE_OPERATIONAL`, `LEGACY_BACKLOG`, `ARCHIVED_HISTORICAL`. Assigned by the logic in Section B.1. Never null — use `LEGACY_BACKLOG` as fallback if date data is missing (see Section B.2). |
| `stale_days` | int | Yes | Integer days between `last_real_activity_date` and `data_date`. Null only when `last_real_activity_date` is null. Zero when activity is from the same day as `data_date`. |
| `last_real_activity_date` | date | Yes | Most recent recorded real activity date across all `chain_events` for this family (see Section B.2 definition). Null only when no `event_date` exists anywhere in the family's chain events. |
| `operational_relevance_score` | int | No | Integer 0–100. Computed from bucket, recency, and blocking state per Section D. Zero for ARCHIVED_HISTORICAL. Floor of 1 for LIVE_OPERATIONAL. |

### C.1 Source Mapping

| Field | Computed by | Source data |
|-------|-------------|-------------|
| `portfolio_bucket` | Step 07 chain_classifier | `current_state`, `last_real_activity_date`, `latest_submission_date`, `OPERATIONAL_HORIZON_DATE` constant |
| `stale_days` | Step 07 chain_classifier | `last_real_activity_date` (from chain_events), `data_date` (from build_chain_source) |
| `last_real_activity_date` | Step 06 timeline engine / Step 05 family grouper | `chain_events.event_date` (non-null values only; excludes computed deadlines) |
| `operational_relevance_score` | Step 07 chain_classifier | `portfolio_bucket`, `stale_days`, `is_blocking`, `current_state`, `waiting_primary_flag`, `waiting_secondary_flag` |

### C.2 Null Policy Extension

The general null policy from STEP02 Section B applies. Additionally:
- `portfolio_bucket` is never null (fallback: `LEGACY_BACKLOG` with WARNING).
- `operational_relevance_score` is never null (fallback: `0` for ARCHIVED, `10` for LEGACY with missing dates).
- `stale_days` and `last_real_activity_date` may legitimately be null (see Section B.2).

---

## SECTION D — `operational_relevance_score` Computation

`operational_relevance_score` is a deterministic integer in [0, 100] that ranks how much
management attention a chain deserves relative to the current operational context.

It is not a health score, a quality score, or a completion percentage. It is purely an
**attention-routing score**: higher values should appear first in sorted dashboard views.

### D.1 ARCHIVED_HISTORICAL

`operational_relevance_score = 0` always.  
No computation required. Archived chains do not compete for management attention.

### D.2 LEGACY_BACKLOG

Base score: `10`.

| Adjustment | Condition | Delta |
|------------|-----------|------:|
| Recent legacy | `stale_days` < 180 (less than 6 months stale) | +15 |
| Moderate legacy | `stale_days` 180–364 | +5 |
| Old legacy | `stale_days` >= 365 | +0 |
| Multiple versions | `total_versions >= 3` (chronic pattern even if legacy) | +5 |

Cap: `max(score, 0)`, `min(score, 30)`.

A LEGACY_BACKLOG chain scores at most 30 — it can never rank above a LIVE_OPERATIONAL chain.

### D.3 LIVE_OPERATIONAL

Base score: `50`.

| Adjustment | Condition | Delta |
|------------|-----------|------:|
| Actively blocking | `current_blocking_actor_count >= 1` (chain has open blocking steps) | +20 |
| Very recent activity | `stale_days` <= 7 | +20 |
| Recent activity | `stale_days` 8–14 | +15 |
| Moderate activity | `stale_days` 15–30 | +10 |
| Aging activity | `stale_days` 31–60 | +5 |
| Stale activity | `stale_days` > 60 | +0 |
| Primary consultant blocking | `waiting_primary_flag = True` | +5 |
| Secondary consultant blocking | `waiting_secondary_flag = True` | +2 |
| Chronic chain | `current_state = CHRONIC_REF_CHAIN` | +5 |
| Abandoned (open but silent) | `current_state = ABANDONED_CHAIN` | −10 |

Cap: `max(score, 1)`, `min(score, 100)`.

**Tie-breaking:** When two LIVE_OPERATIONAL chains have equal `operational_relevance_score`,
sort by `stale_days ASC` (less stale → higher priority). This tie-break is applied by the
dashboard layer, not stored in `chain_register`.

---

## SECTION E — Dashboard Default Filters

These rules define the default state of any dashboard or report view that consumes
`chain_register`. They are binding on the UI layer and on any exported summary reports.

### E.1 Default View (on first load / no user-set filters)

| portfolio_bucket | Shown in default view? | Reason |
|-----------------|:---------------------:|--------|
| `LIVE_OPERATIONAL` | ✅ Yes — always | These are the chains that require action |
| `LEGACY_BACKLOG` | ❌ No — hidden by default | Too numerous; would bury live signals |
| `ARCHIVED_HISTORICAL` | ❌ No — hidden by default | Terminal chains; no action expected |

### E.2 Explicit Toggle Availability

Users must be able to turn on legacy and archived chains via explicit UI controls:

| Control | Effect |
|---------|--------|
| "Include Legacy Backlog" toggle (off by default) | Adds `LEGACY_BACKLOG` chains to the current view |
| "Show Archived" toggle (off by default) | Adds `ARCHIVED_HISTORICAL` chains; intended for audit use only |

### E.3 KPI Computation Scope

All portfolio-level KPIs (blocking count, overdue count, delay totals, onion layer counts) must
be computed against **LIVE_OPERATIONAL only** by default.

When a user enables the "Include Legacy Backlog" toggle, KPIs recompute to include
LEGACY_BACKLOG chains — but the dashboard must display a visible warning:

> ⚠️ Legacy backlog chains included. Blocking and delay counts are not operationally actionable.

When "Show Archived" is enabled:
- Archived chains are shown in list views only.
- They are **never** added to KPI totals, even when the toggle is on.
- `ARCHIVED_HISTORICAL` chains are always excluded from `blocking_count`, `overdue_count`,
  and `onion_alert_count` regardless of user filter state.

### E.4 Sort Order Default

In default view (LIVE_OPERATIONAL only), the default sort is:

```
ORDER BY operational_relevance_score DESC, stale_days ASC
```

---

## SECTION F — Severity Downgrades for Legacy Backlog

When `portfolio_bucket = LEGACY_BACKLOG`, onion responsibility rows for that family must have
their `severity` downgraded by exactly one level before being surfaced in any dashboard view
or alert system. The stored value in `ONION_RESPONSIBILITY.csv` is the **pre-downgrade severity**
(the forensically correct value). The **display severity** is the downgraded value.

### F.1 Downgrade Map

| Stored severity (ONION_RESPONSIBILITY.csv) | Display severity for LEGACY_BACKLOG |
|:------------------------------------------:|:-----------------------------------:|
| `CRITICAL` | `HIGH` |
| `HIGH` | `MEDIUM` |
| `MEDIUM` | `LOW` |
| `LOW` | `LOW` (floor — no further downgrade) |

### F.2 Where Downgrade Is Applied

The downgrade is applied at the **read layer** (query_hooks.py, Step 13), not in the stored CSV.
`ONION_RESPONSIBILITY.csv` always stores the raw computed severity. The downgrade is a view-time
transformation applied when `portfolio_bucket = LEGACY_BACKLOG`.

This means:
- Historical forensic audits always see the original severity.
- Live dashboard alert counts reflect the downgraded severity.
- A LEGACY_BACKLOG chain with two CRITICAL layers produces zero CRITICAL alerts.

### F.3 Narrative Prefix for Legacy Rows

When `portfolio_bucket = LEGACY_BACKLOG` and a row is surfaced in a dashboard view (after the
user has toggled legacy chains on), the `narrative` field must be prefixed with:

```
[LEGACY — severity downgraded from {original_severity}] {original narrative}
```

This prefix is added at read time, not stored in the CSV.

### F.4 ARCHIVED_HISTORICAL Exclusion

Onion rows where `portfolio_bucket = ARCHIVED_HISTORICAL` are excluded from all dashboard
alert counts unconditionally. They may be surfaced in dedicated historical audit views only,
without any downgrade (their severity is presented as-is for forensic purposes).

---

## SECTION G — Interaction with Chain State Vocabulary

This amendment does not modify the chain state vocabulary defined in STEP02 Section E.
`portfolio_bucket` and `current_state` are independent fields that serve different purposes:

| Field | Answers | Source |
|-------|---------|--------|
| `current_state` | Where is this chain structurally? | Workflow logic (blocking, closed, void, chronic) |
| `portfolio_bucket` | Is this chain operationally relevant right now? | Activity dates vs `OPERATIONAL_HORIZON_DATE` |

A chain can be `OPEN_WAITING_PRIMARY_CONSULTANT` (current_state) and `LEGACY_BACKLOG`
(portfolio_bucket) simultaneously. The chain is structurally waiting for a consultant but that
wait has been inactive since 2024. Both facts are true and both are reported.

### G.1 State × Bucket Combinations — Expected and Forbidden

**Expected combinations:**

| current_state | portfolio_bucket | Interpretation |
|--------------|-----------------|----------------|
| `OPEN_WAITING_PRIMARY_CONSULTANT` | `LIVE_OPERATIONAL` | Active primary block requiring action |
| `OPEN_WAITING_PRIMARY_CONSULTANT` | `LEGACY_BACKLOG` | Old primary block, no recent activity |
| `CHRONIC_REF_CHAIN` | `LIVE_OPERATIONAL` | Chronic chain actively resubmitting |
| `CHRONIC_REF_CHAIN` | `LEGACY_BACKLOG` | Chronic chain that has gone silent |
| `ABANDONED_CHAIN` | `LIVE_OPERATIONAL` | Abandoned but within operational window |
| `ABANDONED_CHAIN` | `LEGACY_BACKLOG` | Doubly dormant — chain both abandoned and legacy |
| `CLOSED_VAO` | `ARCHIVED_HISTORICAL` | Correctly resolved and archived |
| `VOID_CHAIN` | `ARCHIVED_HISTORICAL` | Void and archived |
| `DEAD_AT_SAS_A` | `ARCHIVED_HISTORICAL` | Died at first gate, archived |
| `WAITING_CORRECTED_INDICE` | `LIVE_OPERATIONAL` | Active resubmission cycle |
| `WAITING_CORRECTED_INDICE` | `LEGACY_BACKLOG` | Resubmission initiated but stalled pre-cutoff |

**Forbidden combinations (must trigger a validation WARNING):**

| Forbidden | Reason |
|-----------|--------|
| `CLOSED_VAO` + `LIVE_OPERATIONAL` | Terminal state cannot be operationally live |
| `CLOSED_VAO` + `LEGACY_BACKLOG` | Terminal state cannot be backlog |
| `CLOSED_VSO` + `LIVE_OPERATIONAL` | Same as above |
| `CLOSED_VSO` + `LEGACY_BACKLOG` | Same as above |
| `VOID_CHAIN` + `LIVE_OPERATIONAL` | Void chain cannot be operational |
| `VOID_CHAIN` + `LEGACY_BACKLOG` | Void chain must be archived |
| `DEAD_AT_SAS_A` + `LIVE_OPERATIONAL` | Dead chain cannot be operational |
| `DEAD_AT_SAS_A` + `LEGACY_BACKLOG` | Dead chain must be archived |

Any row in `chain_register` with a forbidden combination must be logged as a validation WARNING
by Step 07 and by the validation harness (Step 14). The chain must be corrected to
`ARCHIVED_HISTORICAL` (ARCHIVED_HISTORICAL takes unconditional priority for terminal states
per Section B.1 Priority 1).

---

## SECTION H — Forbidden Logic

1. **No subjective bucket assignment.** `portfolio_bucket` must be assigned exclusively by the
   three-condition priority logic in Section B.1. The phrase "this document seems stale" is not
   a valid trigger.

2. **No `OPERATIONAL_HORIZON_DATE` hard-coding.** The date `2025-09-01` must appear exactly once
   in the codebase — as the named constant in `chain_classifier.py`. Every comparison against it
   must use the constant.

3. **No severity downgrade in stored CSV.** `ONION_RESPONSIBILITY.csv` must always store the
   pre-downgrade severity. The downgrade only happens at read time in `query_hooks.py`. Storing
   the downgraded value would make the CSV non-forensic.

4. **No ARCHIVED_HISTORICAL chains in KPI totals.** Even if a user enables the "Show Archived"
   toggle, archived chains must not contribute to `blocking_count`, `overdue_count`, or
   `onion_alert_count`. The exclusion is hard-coded at the KPI layer, not a user preference.

5. **No null `portfolio_bucket`.** Every row in `chain_register` must have a non-null
   `portfolio_bucket`. The fallback is `LEGACY_BACKLOG` (not null, not a special sentinel value)
   with a logged WARNING.

6. **No `operational_relevance_score` outside [0, 100].** The score must be clamped before
   writing. Negative intermediate values during computation must be floored to 0.

7. **No bucket used as a chain state.** `portfolio_bucket` is not a chain state. It must never
   be compared against chain state vocabulary codes (`CLOSED_VAO`, `VOID_CHAIN`, etc.) anywhere
   except in the Section B.1 and Section G validation logic. A query that filters `current_state`
   on a `portfolio_bucket` value is a programming error.

---

## SECTION I — Step 07 Implementation Handoff

Step 07 implements `src/chain_onion/chain_classifier.py`. In addition to classifying
`current_state` (defined in STEP02 Section E), it must now also assign the four new
`chain_register` fields defined in this amendment.

### I.1 Computation Order Within Step 07

```
For each family_key in chain_register:

1. Classify current_state (per STEP02 Section E priority rules).

2. Compute last_real_activity_date:
   → max(chain_events.event_date) where event_date IS NOT NULL for this family_key.
   → If all event_dates are null: last_real_activity_date = null, log WARNING.

3. Compute stale_days:
   → stale_days = data_date - last_real_activity_date (days).
   → If last_real_activity_date is null: stale_days = null.
   → If stale_days < 0: stale_days = 0, log WARNING.

4. Assign portfolio_bucket:
   → Apply Section B.1 priority logic.
   → Validate: check forbidden state × bucket combinations (Section G.1).
   → Log WARNING for any forbidden combination found, correct to ARCHIVED_HISTORICAL.

5. Compute operational_relevance_score:
   → Apply Section D rules for the assigned portfolio_bucket.
   → Clamp to [0, 100].
```

### I.2 Constants to Define in `chain_classifier.py`

```python
OPERATIONAL_HORIZON_DATE: date = date(2025, 9, 1)

ARCHIVED_TERMINAL_STATES = {
    "CLOSED_VAO",
    "CLOSED_VSO",
    "VOID_CHAIN",
    "DEAD_AT_SAS_A",
}

PORTFOLIO_BUCKET_VALUES = {
    "LIVE_OPERATIONAL",
    "LEGACY_BACKLOG",
    "ARCHIVED_HISTORICAL",
}
```

### I.3 What Downstream Steps Consume

| Step | Fields used from this amendment |
|------|---------------------------------|
| Step 09 (Onion engine) | `portfolio_bucket` — to apply severity downgrade at read time (Section F) |
| Step 13 (Query hooks) | `portfolio_bucket`, `operational_relevance_score`, `stale_days` — for dashboard filtering and KPI scoping |
| Step 14 (Validation harness) | `portfolio_bucket` vocabulary check, forbidden state × bucket check, `operational_relevance_score` range check, `stale_days` non-negative check |

### I.4 Additional Validation Harness Checks (Step 14 additions)

| Check | Pass Condition |
|-------|---------------|
| `portfolio_bucket` vocabulary | All values ∈ `{LIVE_OPERATIONAL, LEGACY_BACKLOG, ARCHIVED_HISTORICAL}` |
| No null `portfolio_bucket` | Zero null values in `portfolio_bucket` column |
| Terminal state → ARCHIVED | All rows where `current_state` ∈ `ARCHIVED_TERMINAL_STATES` have `portfolio_bucket = ARCHIVED_HISTORICAL` |
| `operational_relevance_score` range | All values in [0, 100] |
| ARCHIVED score = 0 | All rows where `portfolio_bucket = ARCHIVED_HISTORICAL` have `operational_relevance_score = 0` |
| LEGACY score ≤ 30 | All rows where `portfolio_bucket = LEGACY_BACKLOG` have `operational_relevance_score <= 30` |
| `stale_days` non-negative | All non-null `stale_days` values >= 0 |
| `last_real_activity_date` ≤ `data_date` | All non-null `last_real_activity_date` values are not in the future relative to `data_date` |

---

## What Was Analyzed

- `docs/STEP02_CHAIN_CONTRACT.md` — `chain_register` schema (Section B), chain state vocabulary
  (Section E), and forbidden logic (Section H) were reviewed to ensure this amendment does not
  conflict with any existing definition.
- `docs/STEP03_ONION_CONTRACT.md` — severity model (Section D) and forbidden logic (Section G)
  were reviewed to determine the correct point for severity downgrade injection (read-time, not
  stored) and to confirm that `issue_type` vocabulary and `evidence_count` constraints are unaffected.
- `docs/CHAIN_ONION_MASTER_STRATEGY.md` — confirmed that this amendment does not modify any
  protected file and remains within the `src/chain_onion/` module boundary.

## What Was Changed

- Created: `docs/STEP03_5_BACKLOG_SEGMENTATION.md` (this file).
- No `.py` files were modified.
- No existing contract fields were removed or redefined — only additive changes.

## What Now Works

- Three mutually exclusive `portfolio_bucket` values are formally defined with deterministic
  assignment logic and a clear priority order.
- Four new `chain_register` fields (`portfolio_bucket`, `stale_days`, `last_real_activity_date`,
  `operational_relevance_score`) are fully specified with computation rules and null policy.
- `OPERATIONAL_HORIZON_DATE = 2025-09-01` is established as a named constant (not a magic number).
- Dashboard default filters are binding: LIVE_OPERATIONAL only by default; legacy and archived
  are opt-in toggles.
- Severity downgrade for LEGACY_BACKLOG is defined as a read-time transformation (stored CSV
  is forensically intact).
- ARCHIVED_HISTORICAL chains are permanently excluded from KPI totals regardless of filter state.
- Eight forbidden `state × bucket` combinations are enumerated with corrective action.
- Step 07 and Step 14 have unambiguous implementation targets for the new logic.

## What Does Not Yet Exist

- `src/chain_onion/chain_classifier.py` (Step 07) — the named constants and computation order
  defined in Section I are the implementation target.
- `src/chain_onion/query_hooks.py` (Step 13) — must implement the read-time severity downgrade
  described in Section F.2.
- Any implementation code.

## Next Blockers

1. **Step 04** — Source loader is still the immediate next implementation step. This amendment
   adds no new source data requirements beyond what Step 04 already loads. `last_real_activity_date`
   is derived from `chain_events.event_date`, which Step 06 already computes.

2. **Step 07** — Chain classifier must implement the four new fields in the order defined in
   Section I.1. The constant `OPERATIONAL_HORIZON_DATE` must be defined before any bucket logic.

3. **Step 13** — Query hooks must apply the LEGACY_BACKLOG severity downgrade (Section F) and
   the dashboard filter defaults (Section E) at the read layer. It must not store the downgraded
   severity back into the CSV.

4. **`data_date` availability in Step 07** — `stale_days` requires `data_date` at classification
   time. Step 07 must receive `data_date` from `build_chain_source()` return dict (the
   `"data_date"` key defined in STEP02 Section I.1). This is already in the Step 04 output
   contract — no new plumbing is required.
