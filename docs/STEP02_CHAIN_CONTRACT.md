# STEP 02 — Chain Data Contract

**Status:** COMPLETE  
**Date:** 2026-04-27  
**Strategy ref:** CHAIN_ONION_MASTER_STRATEGY.md  
**Depends on:** STEP01_SOURCE_MAP.md (identity model established in §0 of Step 01)  
**Feeds:** Steps 04 – 08 (source loader, family grouping, timeline, classifier, metrics)

---

## Purpose

This document is the authoritative definition of what a **Chain** is in this software.  
It defines the identity model, the three output schemas, the complete state vocabulary, and the
Primary vs Secondary consultant classification logic.

A developer must be able to implement Steps 04 – 08 using only this document and the source map
from Step 01 — without inspecting any other file.

No code was modified in the production of this document.

---

## SECTION A — Identity Model

### A.1 Three-Level Identity

A document family passes through multiple revisions and submission instances during its lifecycle.
Three stable keys govern all chain structures:

| Level | Key | Composition | Used for |
|-------|-----|-------------|----------|
| **Family** | `FAMILY_KEY` | `numero` | Top-level chain grouping. All indices of one document family share one `FAMILY_KEY`. |
| **Version** | `VERSION_KEY` | `numero + "_" + indice` | One revision of the document (e.g. `248000_A`, `248000_B`). Stable across pipeline runs. |
| **Instance** | `INSTANCE_KEY` | `numero + "_" + indice + "_" + submission_instance_id` (when known); else `numero + "_" + indice + "_seq_" + N` (synthetic ordinal) | One submission event within a version. Used for event-level reconstruction and instance deduplication. |

String format for all three keys uses underscore as separator and must be consistent throughout.
Examples: `FAMILY_KEY = "248000"`, `VERSION_KEY = "248000_B"`, `INSTANCE_KEY = "248000_B_inst_007"` or `"248000_B_seq_1"`.

### A.2 Synthetic INSTANCE_KEY Fallback

`submission_instance_id` is present in `DEBUG_TRACE.csv` but is **NOT** a column in `GED_OPERATIONS`.
When `DEBUG_TRACE` is absent (single-mode pipeline run) or when `submission_instance_id` is blank
for a given row:

1. Group all `GED_OPERATIONS` rows for the same `VERSION_KEY` (same `numero` + `indice`).
2. Sort by `(submittal_date ASC, step_order ASC)` — `submittal_date` distinguishes multiple
   submission events within the same version; `step_order` breaks ties within the same date.
3. Assign `seq_1`, `seq_2`, … in that order.
4. Compose `INSTANCE_KEY = VERSION_KEY + "_seq_" + N`.

This synthetic ordinal is deterministic given the same `GED_OPERATIONS` input, ensuring reproducibility
across pipeline runs even when `DEBUG_TRACE` is unavailable. The two-key sort is required because
a version may contain steps from different submittal dates (e.g. a resubmission within the same
indice); relying on `step_order` alone would produce unstable sequencing if step ordering is
non-contiguous across submittal events.

### A.3 Why `doc_id` UUID Must NOT Be Used as a Stable Key

`doc_id` is a UUID generated fresh by the pipeline at each run from `effective_responses.py`.
It is scoped to a single pipeline session and has no persistence across runs.

Consequences of using `doc_id` as a chain key:
- A document processed in two different pipeline runs will have two different `doc_id` values
  for the same physical document.
- Cross-run chain history, delay accumulation, and version tracking would become impossible.
- The chain register would duplicate or fragment records across runs.

**Rule:** `doc_id` may be used as a join key within a single pipeline session (to bridge
`effective_responses_df` and `ops_df`). It must never be persisted to any chain output table
or used as a cross-run identifier.

### A.4 Key Usage Summary

| Key | Used for | Cross-run stable? |
|-----|----------|:-----------------:|
| `FAMILY_KEY` | chain_register (one row per family), grouping all versions, cross-run history | ✅ Yes |
| `VERSION_KEY` | chain_versions (one row per version), primary join between ops_df and chain structures | ✅ Yes |
| `INSTANCE_KEY` | chain_events (event-level reconstruction), instance deduplication in onion engine | ✅ Yes (when `submission_instance_id` is stable; synthetic fallback is also deterministic) |
| `doc_id` (UUID) | Session-internal join between `effective_responses_df` and `ops_df` only | ❌ No |

---

## SECTION B — `chain_register` Schema

**Granularity:** One row per `FAMILY_KEY`.  
**Output file:** `output/chain_onion/CHAIN_REGISTER.csv`

This table is the top-level summary of a document family's full lifecycle across all its indices
and submission instances. It is the entry point for portfolio-level chain analytics.

| Column | Type | Description |
|--------|------|-------------|
| `family_key` | string | `FAMILY_KEY` = `numero`. Primary key of this table. |
| `numero` | string/int | The document's unique identifier as it appears in GED. Stored as string to preserve leading zeros if any. |
| `first_submission_date` | date | Earliest `submittal_date` found across all `GED_OPERATIONS` rows for this family. Marks when the family first entered the workflow. |
| `latest_submission_date` | date | Latest `submittal_date` found across all `GED_OPERATIONS` rows for this family (across all versions). |
| `latest_indice` | string | The indice of the most recently submitted version. Determined by `max(submittal_date)` across all `(numero, indice)` pairs; when dates are equal, use lexicographic maximum of indice. |
| `total_indices` | int | Count of distinct `indice` values for this `numero`. Equal to `total_versions` (each indice is one version). |
| `total_versions` | int | Count of distinct `VERSION_KEY` values for this family. Identical to `total_indices`; kept as an explicit alias for clarity in analytics. |
| `total_instances` | int | Count of distinct `submission_instance_id` values across all `DEBUG_TRACE` rows for this `numero`. When `DEBUG_TRACE` is absent, equals `total_versions`. |
| `total_events` | int | Total number of rows in `chain_events` for this `FAMILY_KEY`. One event per actor step per version. |
| `final_status` | string/null | `visa_global` of the latest closed version, using `_derive_visa_global()` logic from `query_library.py`. Null if the chain is still open or no version reached a decisive outcome. Values: `VAO`, `VSO`, `FAV`, `HM`, `VAOB`, `SAS REF`, or null. |
| `current_state` | string | Chain state from the Section E vocabulary. Always one of the defined state codes. Never null — use `UNKNOWN_CHAIN_STATE` if classification fails. |
| `chronic_flag` | bool | True when `total_indices >= 3` AND `current_state` is not in {`CLOSED_VAO`, `CLOSED_VSO`}. Indicates a family that has cycled through many revisions without resolution. |
| `void_flag` | bool | True when `current_state = VOID_CHAIN`. |
| `abandoned_flag` | bool | True when `current_state = ABANDONED_CHAIN`. |
| `cumulative_delay_days` | int | Maximum `cumulative_delay_days` from `GED_OPERATIONS` across all versions of this family. Represents the worst accumulated delay attributable to any single actor across the chain. |
| `current_blocking_actor_count` | int | Count of `GED_OPERATIONS` rows for the `latest_indice` version where `is_blocking = True`. Zero for closed chains. |
| `waiting_primary_flag` | bool | True when `current_state` ∈ {`OPEN_WAITING_PRIMARY_CONSULTANT`, `OPEN_WAITING_MIXED_CONSULTANTS`}. Signals at least one primary consultant is currently blocking. |
| `waiting_secondary_flag` | bool | True when `current_state` ∈ {`OPEN_WAITING_SECONDARY_CONSULTANT`, `OPEN_WAITING_MIXED_CONSULTANTS`}. Signals at least one secondary consultant is currently blocking. |

**Null policy:** No column in `chain_register` may contain a silent null that was derived from a
missing source field without a logged warning. Exception: `final_status` may legitimately be null
for open chains. All other null values must trigger a warning in the chain_builder.

---

## SECTION C — `chain_versions` Schema

**Granularity:** One row per `VERSION_KEY`.  
**Output file:** `output/chain_onion/CHAIN_EVENTS.csv` (as the versions sub-table, or optionally
a separate `CHAIN_VERSIONS.csv`)

This table captures the outcome and metrics of each individual revision of the document.
It enables version-level lifecycle analysis, including which versions were corrected, how many
cycles each version required, and what final outcome each version reached.

| Column | Type | Description |
|--------|------|-------------|
| `family_key` | string | Foreign key → `chain_register.family_key`. |
| `version_key` | string | `VERSION_KEY` = `numero + "_" + indice`. Primary key of this table. |
| `numero` | string/int | Document number. Redundant with `family_key` but included for direct joins to `GED_OPERATIONS`. |
| `indice` | string | Revision letter/number (e.g. `A`, `B`, `C`). |
| `first_submission_date` | date | `submittal_date` of the `OPEN_DOC` step for this `(numero, indice)` in `GED_OPERATIONS`. |
| `last_activity_date` | date | Most recent non-null `response_date` or `sas_response_date` among all `GED_OPERATIONS` rows for this version. Null if no response has been recorded. |
| `instance_count` | int | Count of distinct `submission_instance_id` values in `DEBUG_TRACE` for this `(numero, indice)`. When `DEBUG_TRACE` is absent, defaults to 1. |
| `version_final_status` | string/null | `visa_global` of this version using `_derive_visa_global()` logic from `query_library.py`. Null if this version is still open. Values: `VAO`, `VSO`, `FAV`, `HM`, `VAOB`, `SAS REF`, or null. |
| `requires_new_cycle_flag` | bool | True if any `GED_OPERATIONS` row for this version has `requires_new_cycle = True`. This signals that a step outcome (typically SAS REF) requires the submitter to produce a new revision before workflow can proceed. |
| `version_delay_days` | int | Maximum `cumulative_delay_days` across all `GED_OPERATIONS` rows for this version. Represents total delay accumulated within this revision. |

**Version outcome logic:**

A version is considered **closed** when all of the following hold:
1. No `GED_OPERATIONS` row for this `(numero, indice)` has `is_blocking = True`.
2. `_derive_visa_global(group)` returns a non-null value OR `requires_new_cycle = True` on the SAS step.

A version is considered **open** when at least one `GED_OPERATIONS` row for this `(numero, indice)`
has `is_blocking = True`.

A version is considered **rejected at SAS** when the SAS step has `is_completed = True` and
`status_clean = REF`, and the MOEX step (if present) has not completed with a non-SAS-scoped status.
In this case `version_final_status = "SAS REF"`.

A version is considered **superseded** when a higher-indice version exists within the same family AND
this version is closed (regardless of outcome). The superseded flag is not a column in this table
but is derivable by comparing `indice` order within a family.

---

## SECTION D — `chain_events` Schema

**Granularity:** One row per lifecycle event.  
**Output file:** `output/chain_onion/CHAIN_EVENTS.csv`

An event is any recorded workflow step for a document version — a submission (OPEN_DOC), a SAS
review, a consultant response, or a MOEX arbitration. Every `GED_OPERATIONS` row for a given
version produces exactly one event row after enrichment.

| Column | Type | Description |
|--------|------|-------------|
| `family_key` | string | Foreign key → `chain_register.family_key`. |
| `version_key` | string | Foreign key → `chain_versions.version_key`. |
| `instance_key` | string | `INSTANCE_KEY`. When `submission_instance_id` is available from `DEBUG_TRACE`, uses that; otherwise synthetic ordinal. |
| `event_seq` | int | Monotonically increasing integer, globally ordered within a `family_key`. Assigned after sorting by `(event_date ASC NULLS LAST, version_key ASC, step_order ASC)`. Starts at 1. |
| `actor` | string | `actor_clean` from `GED_OPERATIONS`. For `OPEN_DOC` steps, this is the submitter/emetteur. |
| `actor_type` | string | `step_type` from `GED_OPERATIONS`: `OPEN_DOC`, `SAS`, `CONSULTANT`, or `MOEX`. |
| `step_type` | string | Same as `actor_type`. Kept as an explicit alias to match `GED_OPERATIONS` column naming for direct joins. |
| `status` | string/null | `status_clean` from `GED_OPERATIONS`. Null if the step has not yet received a response (pending steps). |
| `event_date` | date/null | For `OPEN_DOC` steps: `submittal_date`. For all other steps: `response_date`. Null for steps still pending. |
| `source` | string | `effective_source` from `effective_responses_df` — one of: `GED`, `GED+REPORT_STATUS`, `GED+REPORT_COMMENT`, `GED_CONFLICT_REPORT`. For `OPEN_DOC` steps (not in `effective_responses_df`): `GED_OPERATIONS`. |
| `is_blocking` | bool | `is_blocking` from `GED_OPERATIONS`. True = this actor step is currently blocking the workflow. |
| `delay_contribution_days` | int | `delay_contribution_days` from `GED_OPERATIONS`. Zero for non-blocking or on-time steps. Represents days this actor specifically contributed to the chain's total delay. |
| `notes` | string/null | Derived explanatory text. Examples: `"SAS rejection requires new cycle"`, `"Report memory upgrade applied"`, `"Synthetic instance key: DEBUG_TRACE unavailable"`. Null if no notable condition. |

### D.1 Chronological Ordering Rules

Events within a `family_key` are sequenced by the following ordered sort keys:

1. **Primary:** `event_date ASC` — nulls (pending steps with no response date) sort last.
2. **Secondary:** `version_key ASC` — within the same date, earlier indice versions sort before later ones.
3. **Tertiary:** `step_order ASC` — within the same version and same date, use `GED_OPERATIONS.step_order`.

After sorting, assign `event_seq = 1, 2, 3, …` sequentially. This `event_seq` is the canonical
event order for all downstream analytics and narrative construction.

**Important:** Pending events (null `event_date`) receive the highest `event_seq` values within
their version, reflecting that they are the most recent pending items at the time of data extraction.

---

## SECTION E — Chain States Vocabulary (STRICT)

The following state codes form the complete, exhaustive vocabulary for `chain_register.current_state`.
No other state codes are permitted. Classification is fully deterministic — no AI inference,
no heuristic guessing, no silent fallback to a non-defined state.

The **classification priority** defines the order in which states are tested. The first condition
that evaluates to True for a given family determines its `current_state`.

---

### CLOSED States

#### `CLOSED_VAO`
**Definition:** The chain has reached a final positive approval of type VAO, VAOB, FAV, or HM.
The workflow cycle is complete for the latest version.

**Trigger logic (priority 1 among closed states, priority 3 overall):**
1. Latest version (`latest_indice`) has no `GED_OPERATIONS` row with `is_blocking = True`.
2. `_derive_visa_global(group)` for the latest version returns a value in `{VAO, VAOB, FAV, HM}`.

**Priority level:** 3 (checked after void/dead states; before resubmission, MOEX, and consultant-waiting states)

**Example scenario:** Document 248000 / indice B: all consultants gave VAO. MOEX issued final VAO.
`is_blocking = False` for all steps. `visa_global = "VAO"`. → `CLOSED_VAO`.

---

#### `CLOSED_VSO`
**Definition:** The chain has reached a final positive approval of type VSO (Visa Sans Observation).
The workflow cycle is complete with a clean approval.

**Trigger logic (priority 2 among closed states, priority 4 overall):**
1. Latest version has no `GED_OPERATIONS` row with `is_blocking = True`.
2. `_derive_visa_global(group)` for the latest version returns `"VSO"`.

**Priority level:** 4

**Example scenario:** Document 312500 / indice A: all consultants gave VSO. MOEX issued VSO.
`visa_global = "VSO"`. → `CLOSED_VSO`.

---

### Corrected Indice State

#### `WAITING_CORRECTED_INDICE`
**Definition:** The chain contains a previous version that received a rejection requiring a new
submission cycle (`requires_new_cycle = True`), AND a corrected version (newer indice) has been
submitted and is currently under evaluation (open — has `is_blocking = True` rows).

This state supersedes all MOEX and consultant waiting states. The chain narrative — that this
document is a resubmission after rejection — is analytically more significant than the identity
of the current blocker. A WAITING_CORRECTED_INDICE chain may have MOEX blocking, primary
consultants blocking, or secondary consultants blocking on its latest version; that information
is captured in `chain_events` and `current_blocking_actor_count`, but the top-level state
reflects the resubmission context.

**Trigger logic (priority 5 overall — evaluated before MOEX and all consultant states):**
1. At least one older version has `requires_new_cycle_flag = True` in `chain_versions`.
2. The latest version (`latest_indice`) has at least one `is_blocking = True` row in `GED_OPERATIONS`.
   (The latest version is actively being evaluated — it is the corrected submission.)

**Priority level:** 5

**Example scenario:** Document 248000 / indice A: SAS REF, `requires_new_cycle = True`. Indice B
submitted: SAS VAO. EGIS still pending. Even though EGIS (a Primary consultant) is the current
blocker, the chain state is `WAITING_CORRECTED_INDICE` — not `OPEN_WAITING_PRIMARY_CONSULTANT`.

---

### MOEX State

#### `OPEN_WAITING_MOEX`
**Definition:** The latest version is open and the only remaining blocking step is held by the MOEX
arbitration body. All consultant reviews have been completed (or are not required). No prior version
required a new cycle (otherwise `WAITING_CORRECTED_INDICE` would have fired first).

**Trigger logic (priority 6 overall):**
1. Latest version has at least one `GED_OPERATIONS` row with `is_blocking = True`.
2. ALL `is_blocking = True` rows for the latest version have `step_type = "MOEX"`.

This matches the logic of `get_waiting_moex()` from `query_library.py` applied to the latest version.

**Priority level:** 6

**Example scenario:** Document 248000 / indice B: SAS VAO. All consultants VAO. Only MOEX step
remains blocking. No prior version had `requires_new_cycle = True`. → `OPEN_WAITING_MOEX`.

---

### Consultant States

The following three states are mutually exclusive and apply only when MOEX is NOT the sole blocker
and no prior version required a new cycle (otherwise `WAITING_CORRECTED_INDICE` takes priority).
Primary vs Secondary classification uses exclusively the logic defined in Section F.

#### `OPEN_WAITING_PRIMARY_CONSULTANT`
**Definition:** The latest version is open. All currently blocking steps are CONSULTANT type and
every blocking actor is a Primary consultant (matches at least one keyword in
`_PRIMARY_APPROVER_KEYWORDS`). No MOEX step is blocking. No secondary consultant is blocking.
No prior version required a new cycle.

**Trigger logic (priority 7 overall):**
1. Latest version has at least one `is_blocking = True` row with `step_type = "CONSULTANT"`.
2. No `is_blocking = True` row has `step_type = "MOEX"`.
3. For every blocking `actor_clean`: `_is_primary_approver(actor_clean) is True`.

**Priority level:** 7

**Example scenario:** Document 312500 / indice A (first and only version, never rejected): EGIS
is blocking. BET SPK is blocking. No other actors blocking. Both are Primary keywords.
→ `OPEN_WAITING_PRIMARY_CONSULTANT`.

---

#### `OPEN_WAITING_SECONDARY_CONSULTANT`
**Definition:** The latest version is open. All currently blocking steps are CONSULTANT type and
every blocking actor is a Secondary consultant (does NOT match any keyword in
`_PRIMARY_APPROVER_KEYWORDS`). No MOEX step is blocking. No primary consultant is blocking.
No prior version required a new cycle.

**Trigger logic (priority 8 overall):**
1. Latest version has at least one `is_blocking = True` row.
2. No `is_blocking = True` row has `step_type = "MOEX"`.
3. For every blocking `actor_clean`: `_is_primary_approver(actor_clean) is False`.

This matches the exact logic of `get_waiting_secondary()` from `query_library.py` applied to the
latest version.

**Priority level:** 8

**Example scenario:** Document 248000 / indice C (first and only version, never rejected):
"Bureau Signalétique" is blocking. "Commission Voirie" is blocking. Neither matches any primary
keyword. → `OPEN_WAITING_SECONDARY_CONSULTANT`.

---

#### `OPEN_WAITING_MIXED_CONSULTANTS`
**Definition:** The latest version is open. Blocking steps include at least one Primary consultant
AND at least one Secondary consultant simultaneously. No MOEX step is blocking. No prior version
required a new cycle.

**Trigger logic (priority 9 overall):**
1. Latest version has at least one `is_blocking = True` row.
2. No `is_blocking = True` row has `step_type = "MOEX"`.
3. Among blocking `actor_clean` values: at least one satisfies `_is_primary_approver() is True`
   AND at least one satisfies `_is_primary_approver() is False`.

**Priority level:** 9

**Example scenario:** Document 248000 / indice B (first and only version, never rejected):
TERRELL is blocking (Primary). "Sécurité Incendie" is blocking (Secondary).
→ `OPEN_WAITING_MIXED_CONSULTANTS`.

---

#### `VOID_CHAIN`
**Definition:** The chain has been effectively nullified — all submitted versions ended in rejection
at SAS level, no approval-family outcome was ever achieved across any version, and no new corrected
version has been submitted within the operationally defined void window (default: 90 days since
latest `submittal_date`).

**Trigger logic (priority 1 overall — checked first):**
1. All versions in the family have `requires_new_cycle_flag = True` OR `version_final_status = "SAS REF"`.
2. No version has `version_final_status` in `{VAO, VAOB, FAV, HM, VSO}`.
3. `latest_submission_date` is more than 90 days before `data_date` (configurable threshold).
4. Latest version has no `is_blocking = True` rows (no active evaluation).

Note: The 90-day threshold is a parameter that Step 07 (chain_classifier) must expose as a
configurable constant. It must never be hard-coded as a magic number.

**Priority level:** 1 (highest — checked before all other states)

**Example scenario:** Document 312500 / indice A: SAS REF. Indice B submitted: SAS REF. No
indice C submitted. Last submittal was 120 days ago. → `VOID_CHAIN`.

---

#### `CHRONIC_REF_CHAIN`
**Definition:** The chain has accumulated three or more distinct versions (`total_indices >= 3`),
at least two of which received rejection outcomes (either `SAS REF` or `requires_new_cycle = True`),
and the chain is still open (not closed with a final approval).

**Trigger logic (priority 2 overall):**
1. `total_versions >= 3`.
2. At least 2 versions have `requires_new_cycle_flag = True` OR `version_final_status = "SAS REF"`.
3. `current_state` is not `CLOSED_VAO` or `CLOSED_VSO` (chain is still open).
4. Chain does not satisfy `VOID_CHAIN` conditions.

**Priority level:** 2

**Example scenario:** Document 248000: indice A SAS REF, indice B SAS REF, indice C currently
open with consultants blocking. → `CHRONIC_REF_CHAIN`.

---

#### `DEAD_AT_SAS_A`
**Definition:** A specific terminal sub-case: the document was submitted only once (single version,
indice A), that version received a SAS rejection (`version_final_status = "SAS REF"`), and no
corrected version was ever submitted. The chain is dead at its first gate with no follow-up action.

**Trigger logic (priority 1b — checked alongside VOID_CHAIN, priority level 1):**
1. `total_versions = 1`.
2. The single version's `indice = "A"` (or the lexicographically/logically first indice).
3. `version_final_status = "SAS REF"` (SAS step completed with REF).
4. No newer version exists (confirmed by step 2 above).
5. `last_activity_date` is at least 30 days before `data_date` (configurable threshold — confirms
   this is not a very recent rejection still in the resubmission window).

Note: `DEAD_AT_SAS_A` and `VOID_CHAIN` are checked at the same priority level (1). `DEAD_AT_SAS_A`
is more specific (exactly one version, exactly SAS REF, exactly first indice). When both conditions
could theoretically apply, `DEAD_AT_SAS_A` wins because it is more specific.

**Priority level:** 1 (same tier as VOID_CHAIN, more specific → takes precedence)

**Example scenario:** Document 312500 / indice A only: SAS issued REF 45 days ago. No B submitted.
→ `DEAD_AT_SAS_A`.

---

#### `ABANDONED_CHAIN`
**Definition:** The chain is technically still open (has `is_blocking = True` rows) but has had
no recorded activity (no new `response_date` or `sas_response_date`) for more than 60 days from
`data_date` (configurable threshold). The chain is neither closed nor voided — it has simply gone
silent.

**Trigger logic (priority 10 overall — checked after all active-state and corrected-indice conditions):**
1. Latest version has at least one `is_blocking = True` row (chain is open).
2. `last_activity_date` (most recent non-null `response_date` across all steps of all versions) is
   more than 60 days before `data_date` (configurable threshold).
3. Chain does not satisfy any higher-priority state condition.

**Priority level:** 10

**Example scenario:** Document 248000 / indice B: all consultants pending since 75 days. No response
recorded from any actor. Chain is open. → `ABANDONED_CHAIN`.

---

#### `UNKNOWN_CHAIN_STATE`
**Definition:** Fallback state. Applied when no other state condition evaluates to True, or when
required data is missing/inconsistent and a deterministic classification cannot be made.

**Trigger logic (priority 12 overall — last resort):**
Applied when no state above was triggered. Step 07 must log a structured warning for every family
assigned `UNKNOWN_CHAIN_STATE`, including the specific reason classification failed.

**Priority level:** 12 (lowest — true fallback)

**Example scenario:** `GED_OPERATIONS` rows exist for a `numero` but all dates are null and all
`is_blocking` values are null. Cannot determine if open or closed. → `UNKNOWN_CHAIN_STATE`.

---

### Classification Priority Summary

| Priority | State | Condition Type |
|:--------:|-------|----------------|
| 1 | `DEAD_AT_SAS_A` | Terminal — specific single-version SAS death |
| 1 | `VOID_CHAIN` | Terminal — multi-version void, no viable path |
| 2 | `CHRONIC_REF_CHAIN` | Escalated — 3+ versions with repeated rejection |
| 3 | `CLOSED_VAO` | Terminal positive — approval family (VAO/VAOB/FAV/HM) |
| 4 | `CLOSED_VSO` | Terminal positive — clean visa (VSO) |
| 5 | `WAITING_CORRECTED_INDICE` | Transitional — resubmission cycle, supersedes consultant buckets |
| 6 | `OPEN_WAITING_MOEX` | Active — only MOEX blocking |
| 7 | `OPEN_WAITING_PRIMARY_CONSULTANT` | Active — only primary consultants blocking |
| 8 | `OPEN_WAITING_SECONDARY_CONSULTANT` | Active — only secondary consultants blocking |
| 9 | `OPEN_WAITING_MIXED_CONSULTANTS` | Active — primary + secondary both blocking |
| 10 | `ABANDONED_CHAIN` | Dormant — open but silent |
| 12 | `UNKNOWN_CHAIN_STATE` | Fallback — classification failure |

**Design note — future CLOSED merge:** `CLOSED_VAO` and `CLOSED_VSO` are kept as distinct internal
states (priority 3 and 4 respectively) to preserve analytical granularity at the chain level. A
future dashboard layer may aggregate both into a single `CLOSED_APPROVED` bucket for display
purposes without changing the underlying classification logic.

---

## SECTION F — Primary vs Secondary Consultant Rules

This section is **mandatory**. The classification taxonomy defined here is the ONLY permitted
taxonomy for Primary vs Secondary consultant identification in the Chain + Onion module.

### F.1 Authoritative Source

The following constants and function are defined in `src/query_library.py` (read-only; must not be
modified). The Chain + Onion module must import or replicate them exactly.

**`_PRIMARY_APPROVER_KEYWORDS`** (lines 78–81 of `src/query_library.py`):
```python
_PRIMARY_APPROVER_KEYWORDS = [
    "TERRELL", "EGIS", "BET SPK", "BET ASC", "BET EV",
    "BET FACADES", "ARCHI MOX", "MOEX",
]
```

**`_is_primary_approver(name: str) -> bool`** (lines 167–170 of `src/query_library.py`):
```python
def _is_primary_approver(name: str) -> bool:
    """True if actor name contains any primary approver keyword (case-insensitive)."""
    u = str(name).upper()
    return any(kw in u for kw in _PRIMARY_APPROVER_KEYWORDS)
```

**Detection method:** substring match, case-insensitive. An actor is Primary if its `actor_clean`
string contains any of the keywords as a substring. Example: `"BET Structure SPK"` is Primary
because it contains `"BET SPK"`.

### F.2 Classification Rules

**Primary consultant:** Any actor whose `actor_clean` name contains at least one keyword from
`_PRIMARY_APPROVER_KEYWORDS` (case-insensitive substring match). These are the strategic and
core technical reviewers recognized by the existing repository workflow logic. They carry higher
analytical weight in delay attribution and chain state classification.

**Secondary consultant:** Any actor whose `actor_clean` name does NOT match any keyword in
`_PRIMARY_APPROVER_KEYWORDS`. These are all remaining non-primary blocking consultants.

**Mixed condition:** When at least one Primary AND at least one Secondary blocking consultant are
present simultaneously for the same version. This triggers `OPEN_WAITING_MIXED_CONSULTANTS`.

**Note on MOEX:** `"MOEX"` appears in `_PRIMARY_APPROVER_KEYWORDS`. However, MOEX has its own
dedicated chain state (`OPEN_WAITING_MOEX`), which takes priority 5 — evaluated before all
consultant states. When MOEX is the sole blocker, the chain is classified as `OPEN_WAITING_MOEX`,
not as a primary-consultant state. The MOEX keyword in `_PRIMARY_APPROVER_KEYWORDS` is therefore
only relevant when MOEX appears as a `CONSULTANT` step (unusual edge case) rather than as the
designated `MOEX` step type.

### F.3 Forbidden Alternatives

The following are explicitly forbidden:
- Inventing a new list of primary/secondary keywords.
- Classifying consultants by lot, emetteur, or any other GED attribute.
- Using AI/LLM inference to classify consultant type.
- Using any taxonomy that contradicts or extends `_PRIMARY_APPROVER_KEYWORDS`.

If the existing keyword list proves incomplete for new data, the resolution is to update
`_PRIMARY_APPROVER_KEYWORDS` in `src/query_library.py` through a tracked change request — not
to create a parallel list in `src/chain_onion/`.

### F.4 `actor_type` Field in `chain_events`

The `actor_type` column in `chain_events` uses `step_type` from `GED_OPERATIONS` (`OPEN_DOC`,
`SAS`, `CONSULTANT`, `MOEX`). It does not encode Primary/Secondary directly. Primary/Secondary
classification is derived on-the-fly by calling `_is_primary_approver(actor)` when needed by
the classifier (Step 07) and onion engine (Step 09). It is NOT persisted in `chain_events` to
avoid redundancy with the authoritative source logic.

---

## SECTION G — Source Mapping

For every field required by the three schemas, this table identifies the authoritative data source.
Use this table as the field-by-field implementation guide for `source_loader.py` (Step 04).

| Field | Table | Source | Column in Source | Notes |
|-------|-------|--------|-----------------|-------|
| `family_key` | all | derived | `numero` in `GED_OPERATIONS` | `str(numero)` |
| `version_key` | all | derived | `numero` + `indice` in `GED_OPERATIONS` | `f"{numero}_{indice}"` |
| `instance_key` | chain_events | DEBUG_TRACE + derived | `submission_instance_id` in `DEBUG_TRACE.csv` | Fallback: synthetic seq_N from step_order |
| `numero` | all | GED_OPERATIONS | `numero` | |
| `first_submission_date` | chain_register | GED_OPERATIONS | `submittal_date` (OPEN_DOC step) | `min()` across all versions |
| `latest_submission_date` | chain_register | GED_OPERATIONS | `submittal_date` (OPEN_DOC step) | `max()` across all versions |
| `latest_indice` | chain_register | GED_OPERATIONS | `indice` | indice of the version with `max(submittal_date)` |
| `total_indices` | chain_register | GED_OPERATIONS | `indice` | `nunique()` per numero |
| `total_versions` | chain_register | derived | — | `= total_indices` |
| `total_instances` | chain_register | DEBUG_TRACE | `submission_instance_id` | count distinct per numero; default to `total_versions` if DEBUG_TRACE absent |
| `total_events` | chain_register | chain_events | — | count of chain_events rows for this family_key |
| `final_status` | chain_register | derived | `visa_global` via `_derive_visa_global()` | Apply to latest_indice group from GED_OPERATIONS |
| `current_state` | chain_register | derived | — | Output of chain_classifier.py (Step 07) |
| `chronic_flag` | chain_register | derived | — | `total_indices >= 3 AND current_state NOT IN {CLOSED_VAO, CLOSED_VSO}` |
| `void_flag` | chain_register | derived | — | `current_state = VOID_CHAIN` |
| `abandoned_flag` | chain_register | derived | — | `current_state = ABANDONED_CHAIN` |
| `cumulative_delay_days` | chain_register | GED_OPERATIONS | `cumulative_delay_days` | `max()` across all rows for this numero |
| `current_blocking_actor_count` | chain_register | GED_OPERATIONS | `is_blocking` | count of `is_blocking=True` rows for latest_indice version |
| `waiting_primary_flag` | chain_register | derived | — | `current_state IN {OPEN_WAITING_PRIMARY_CONSULTANT, OPEN_WAITING_MIXED_CONSULTANTS}` |
| `waiting_secondary_flag` | chain_register | derived | — | `current_state IN {OPEN_WAITING_SECONDARY_CONSULTANT, OPEN_WAITING_MIXED_CONSULTANTS}` |
| `indice` | chain_versions | GED_OPERATIONS | `indice` | |
| `version_first_submission_date` | chain_versions | GED_OPERATIONS | `submittal_date` (OPEN_DOC row for this version) | |
| `last_activity_date` | chain_versions | GED_OPERATIONS | `response_date`, `sas_response_date` | `max()` non-null across all steps for this version |
| `instance_count` | chain_versions | DEBUG_TRACE | `submission_instance_id` | count distinct per (numero, indice); default 1 if absent |
| `version_final_status` | chain_versions | derived | `visa_global` via `_derive_visa_global()` | Apply to this version's group |
| `requires_new_cycle_flag` | chain_versions | GED_OPERATIONS | `requires_new_cycle` | `any()` per version |
| `version_delay_days` | chain_versions | GED_OPERATIONS | `cumulative_delay_days` | `max()` per version |
| `event_seq` | chain_events | derived | — | Monotonic int after chronological sort (see Section D.1) |
| `actor` | chain_events | GED_OPERATIONS | `actor_clean` | |
| `actor_type` | chain_events | GED_OPERATIONS | `step_type` | |
| `step_type` | chain_events | GED_OPERATIONS | `step_type` | Alias of actor_type |
| `status` | chain_events | GED_OPERATIONS | `status_clean` | Null for pending steps |
| `event_date` | chain_events | GED_OPERATIONS | `submittal_date` (OPEN_DOC), `response_date` (other steps) | |
| `source` | chain_events | effective_responses | `effective_source` | For OPEN_DOC rows: use literal `"GED_OPERATIONS"` |
| `is_blocking` | chain_events | GED_OPERATIONS | `is_blocking` | |
| `delay_contribution_days` | chain_events | GED_OPERATIONS | `delay_contribution_days` | |
| `notes` | chain_events | derived | — | Generated by chain_builder logic; null if no notable condition |

---

## SECTION H — Forbidden Logic

The following practices are **explicitly prohibited** in all Steps 04–08 implementations.
Violations invalidate the chain data contract and must be caught by the validation harness (Step 14).

1. **Using `doc_id` UUID as a stable chain key.** `doc_id` is a session-scoped UUID generated by
   `effective_responses.py`. It must never appear in `chain_register`, `chain_versions`, or
   `chain_events` as an identity key. It may only be used as a session-internal join handle
   between `effective_responses_df` and `ops_df` within a single pipeline execution.

2. **Mutating source files.** `src/flat_ged/*`, `src/query_library.py`, `src/effective_responses.py`,
   and all files listed in CHAIN_ONION_MASTER_STRATEGY.md § PROTECTED FILES must not be modified.
   Chain + Onion is a consumer layer only.

3. **Guessed or inferred dates.** Every date value in chain output tables must come from a
   recorded source column (`submittal_date`, `response_date`, `sas_response_date`) in
   `GED_OPERATIONS` or `DEBUG_TRACE`. If a date is not available, the field must be null with
   a logged warning. Interpolating, averaging, or estimating missing dates is forbidden.

4. **AI-generated classifications.** Chain state, actor type, delay attribution, and all
   analytical outputs must be computed deterministically from source data using explicit rules
   defined in this document. No LLM inference, no probabilistic scoring, no NLP-based classification
   is permitted inside the chain engine (Steps 04–08).

5. **Silent null replacement.** A null value in a source column must propagate as null (or a
   logged warning) in the output. It must never be silently replaced with 0, empty string, or any
   default value without a corresponding log entry at WARNING level or above.

6. **Alternative Primary/Secondary consultant taxonomy.** The only permitted taxonomy is
   `_PRIMARY_APPROVER_KEYWORDS` + `_is_primary_approver()` from `src/query_library.py`. Creating
   a parallel keyword list, a separate classification table, or any other method of categorizing
   consultants is forbidden.

7. **Writing to `output/intermediate/`.** The chain output directory is `output/chain_onion/`.
   Steps 04–08 must not write to `output/intermediate/` (which is owned by the flat_ged builder).

8. **Inventing chain state codes.** Only the 12 state codes defined in Section E are valid values
   for `current_state`. Any classification that does not map to one of these codes must result
   in `UNKNOWN_CHAIN_STATE` plus a structured warning log.

---

## SECTION I — Implementation Guidance for Step 04

Step 04 implements `src/chain_onion/source_loader.py`. This section defines exactly what it must
produce to satisfy this contract.

### I.1 Required Outputs

`build_chain_source()` must return a dict with the following structure:

```python
{
    "ops_df":       pd.DataFrame,  # GED_OPERATIONS — chain backbone
    "debug_df":     pd.DataFrame,  # DEBUG_TRACE — instance resolution context
    "effective_df": pd.DataFrame,  # composed truth — status + provenance
    "data_date":    str,           # ISO 8601 date string, e.g. "2026-04-15"
}
```

### I.2 Required Column Additions

After loading source DataFrames, `source_loader.py` must add the following computed columns:

**To `ops_df` (GED_OPERATIONS):**
- `family_key` — `str(numero)`
- `version_key` — `f"{numero}_{indice}"`

**To `debug_df` (DEBUG_TRACE):**
- `family_key` — `str(numero)`
- `version_key` — `f"{numero}_{indice}"`
- `instance_key` — `f"{numero}_{indice}_{submission_instance_id}"` when `submission_instance_id` is
  non-null and non-empty; else `f"{numero}_{indice}_seq_{N}"` where N is the 1-based ordinal within
  `(numero, indice)` sorted by `(submittal_date ASC, step_order ASC)` — matching Section A.2.

**To `effective_df` (effective_responses):**
- No key columns added. `effective_df` is joined to `ops_df` via session-internal `doc_id` only.
  `source_loader.py` must build the `doc_id → (numero, indice)` bridge map from `stage_read_flat`
  output (or from the join itself) and attach `family_key` and `version_key` as session-scoped
  columns. These columns in `effective_df` are for intra-session use only — they must not be
  persisted to any output CSV.

### I.3 Identity Gap Resolution

`GED_OPERATIONS` uses `(numero, indice)` as document identity.
`effective_responses_df` uses `doc_id` (UUID, session-scoped).

`source_loader.py` must resolve this gap explicitly:

1. After calling `stage_read_flat()`, extract the `id_to_pair` map: `{doc_id: (numero, indice)}`.
2. Reverse it: `{(numero, indice): doc_id}` (pair_to_id).
3. Use `pair_to_id` to attach `doc_id` to `ops_df` rows when calling `build_effective_responses()`.
4. Store the bridge map in the returned dict for use by downstream steps.

If `stage_read_flat` is not available (source loader running standalone), build the bridge by
matching on shared structural columns (e.g., `lot`, `emetteur`, `titre`, `submittal_date`).
Log a warning if the bridge cannot be fully established.

### I.4 `submission_instance_id` Availability

`submission_instance_id` is present only in `DEBUG_TRACE.csv` (a batch-mode-only artifact).
It is NOT a column in `GED_OPERATIONS`.

Step 04 must:
1. Attempt to load `DEBUG_TRACE.csv` from the provided path.
2. If `DEBUG_TRACE.csv` is absent or empty, log a WARNING: `"DEBUG_TRACE unavailable — INSTANCE_KEY
   will use synthetic ordinal seq_N for all versions."` Then proceed with synthetic keys.
3. Join `debug_df` to `ops_df` on `(numero, indice)` to transfer `submission_instance_id` to
   the ops context for event construction.
4. When `submission_instance_id` is present for a row, use it. When null or blank, use the
   synthetic fallback defined in Section A.2.

### I.5 Read-Only Guarantee

All three source DataFrames returned by `build_chain_source()` must be treated as read-only
by all downstream steps. The loader must not mutate source arrays — all key columns must be
added via `.assign()` or `.copy()` to avoid modifying the original DataFrames.

### I.6 Output Directory

Step 04 must create `output/chain_onion/` if it does not exist. This is the only directory
creation Step 04 is permitted to perform. All CSV outputs from Steps 05–08 must go here.

### I.7 What Downstream Steps Consume

| Step | Primary Input | Key Columns Used |
|------|---------------|-----------------|
| Step 05 — Family Grouping | `ops_df` | `family_key`, `version_key`, `numero`, `indice`, `step_type`, `step_order`, `submittal_date` |
| Step 06 — Timeline Events | `ops_df` + `debug_df` + `effective_df` | `instance_key`, `event_date`, `step_order`, `actor_clean`, `status_clean`, `is_blocking`, `delay_contribution_days`, `effective_source` |
| Step 07 — Chain Classifier | `ops_df` + `chain_versions` output | `is_blocking`, `step_type`, `actor_clean`, `requires_new_cycle`, `cumulative_delay_days`, `visa_global` (derived), `last_activity_date`, `total_versions` |
| Step 08 — Chain Metrics | `ops_df` + `chain_events` output | `delay_contribution_days`, `cumulative_delay_days`, `step_delay_days`, `is_blocking`, `event_date` |

---

## What Was Analyzed

- `src/query_library.py` — full read; `_PRIMARY_APPROVER_KEYWORDS`, `_is_primary_approver()`,
  `get_waiting_secondary()`, `get_waiting_moex()`, `_derive_visa_global()`, and all queue
  primitives were reviewed as authoritative business logic.
- `docs/STEP01_SOURCE_MAP.md` — full read; identity model (§0), GED_OPERATIONS column list,
  DEBUG_TRACE schema, effective_responses merge rules, and all risks from §4 were incorporated.
- `docs/CHAIN_ONION_MASTER_STRATEGY.md` — full read; output target structure and protected files
  confirmed.
- `docs/CHAIN_ONION_STEP_TRACKER.md` — read for context; updated as part of this step.

## What Was Changed

- Created: `docs/STEP02_CHAIN_CONTRACT.md` (this file).
- Updated: `docs/CHAIN_ONION_STEP_TRACKER.md` — Step 02 marked COMPLETE.
- No `.py` files were modified.

## What Now Works

- Complete authoritative definition of what a Chain is.
- Three output table schemas fully specified (chain_register, chain_versions, chain_events).
- Identity model (FAMILY_KEY / VERSION_KEY / INSTANCE_KEY) formally contracted.
- Full chain state vocabulary (12 states) with deterministic trigger logic and classification priority.
- Primary vs Secondary consultant classification formally tied to repo source logic.
- Source mapping table covers every field across all three schemas.
- Section H explicitly prohibits all known failure modes.
- Section I gives Step 04 an unambiguous implementation target.

## What Does Not Yet Exist

- `src/chain_onion/` directory (Step 04).
- `output/chain_onion/` directory (Step 04).
- Any Onion data contract (Step 03).
- Any implementation code.

## Next Blockers

1. **Step 03** — Onion data contract must be authored before Step 04 begins.
   Onion Layer 1 (contractor quality) needs `instance_count` and `requires_new_cycle_flag` from
   `chain_versions`. Layers 3–4 (consultant delay/rejection) read `delay_contribution_days` from
   `chain_events`. Layer 6 (data/report discrepancy) reads `effective_source` from `chain_events`.

   **Strategic requirement (confirmed before Step 03 opens):** The Onion must be **forensic**,
   not decorative. Each layer must produce evidence-backed attribution that can be audited row by
   row against source data. Responsibility scores must trace directly to specific events in
   `chain_events` — no aggregate heuristics, no unattributed penalty points. Step 03 must
   define exactly which `chain_events` fields feed each onion layer and what the minimum
   evidence threshold is before a layer fires.

2. **Step 04** — Blocked on Step 03. Once both contracts are complete, implementation may proceed.
   Main technical risk: `submission_instance_id` availability (DEBUG_TRACE batch-only) and the
   `doc_id` ↔ `(numero, indice)` identity bridge from `stage_read_flat`.

3. **Step 07** — Chain classifier thresholds (`void_window_days = 90`, `abandoned_threshold_days = 60`,
   `dead_at_sas_inactivity_days = 30`) must be exposed as configurable constants, not magic numbers.

4. **WAITING_CORRECTED_INDICE priority correction (v1.1):** Priority moved from 9 to 5 so that
   the resubmission cycle context supersedes consultant-bucket states. The rationale: when indice B
   exists because indice A was rejected, the chain narrative matters more than the current
   blocker identity for triage and Onion attribution. The current blocker remains accessible via
   `current_blocking_actor_count`, `waiting_primary_flag`, and `waiting_secondary_flag` in
   `chain_register`.
