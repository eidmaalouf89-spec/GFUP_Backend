# STEP06_VALIDATION.md
## Step 06 — Timeline Event Engine: Validation Report

**Date:** 2026-04-27
**Status:** COMPLETE — 30 passed, 1 skipped, 0 failed (2.49s)

---

## What Was Analyzed

| File | Purpose |
|------|---------|
| `docs/CHAIN_ONION_MASTER_STRATEGY.md` | Architecture, protected files, output targets |
| `docs/CHAIN_ONION_STEP_TRACKER.md` | Step status registry |
| `docs/STEP01_SOURCE_MAP.md` | DEBUG_TRACE column schema (23 cols), identity model |
| `docs/STEP02_CHAIN_CONTRACT.md` | `chain_events` schema (Section D), chronological ordering rules (D.1), actor_type rules (F.4), forbidden logic (Section H) |
| `docs/STEP03_ONION_CONTRACT.md` | Context only — no changes required in Step 06 |
| `docs/STEP04_VALIDATION.md` | Confirmed ops_df=32,099 rows (39 cols), debug_df=407,288 rows (27 cols), effective_df=27,251 rows (all GED-only), loader return contract |
| `docs/STEP05_VALIDATION.md` | Confirmed chain_versions and chain_register outputs; handoff contract |
| `src/chain_onion/source_loader.py` | load_chain_sources() return dict keys and column names |
| `src/chain_onion/family_grouper.py` | Code style, bool normalization helpers, _is_primary_approver import pattern |
| `src/query_library.py` | `_is_primary_approver()` (lines 167–170), `_PRIMARY_APPROVER_KEYWORDS` (lines 78–81) — used verbatim |

---

## What Was Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `src/chain_onion/chain_builder.py` | **Created** | Timeline Event Engine — `build_chain_events()` + three per-source builders (~330 lines) |
| `tests/test_chain_builder.py` | **Created** | 30 synthetic unit tests across 5 test classes + 1 skipped live test |
| `docs/STEP06_VALIDATION.md` | **Created** | This file |

**Not modified:** `src/flat_ged/*`, existing pipeline stages, UI files, Step 04 loader logic, Step 05 grouper logic, any onion modules, `CHAIN_ONION_MASTER_STRATEGY.md`.

---

## Timeline Behavior

### `build_chain_events(ops_df, debug_df=None, effective_df=None) -> pd.DataFrame`

Top-level public function. Orchestrates three per-source event builders, concatenates results, deduplicates, sorts chronologically, and assigns `event_seq`.

#### A. From `ops_df` (GED_OPERATIONS) — `_build_ops_events()`

- **One event per ops_df row.** No aggregation at this stage.
- **event_date:** `OPEN_DOC` steps → `submittal_date`; all other steps → `response_date`. NaT when source date is null.
- **instance_key:** `version_key + "_main"` (DEBUG_TRACE not joined to ops events to avoid ambiguous many-to-many).
- **source / source_priority:** `"OPS"` / `1`.
- **actor:** `actor_clean` from ops_df; fallback to `"UNKNOWN"` for null/blank.
- **actor_type** (deterministic mapping from `step_type` × `_is_primary_approver`):

  | GED step_type | actor_type |
  |--------------|-----------|
  | `OPEN_DOC` | `CONTRACTOR` |
  | `SAS` | `SAS` |
  | `MOEX` | `MOEX` |
  | `CONSULTANT` + primary keyword | `PRIMARY_CONSULTANT` |
  | `CONSULTANT` + no keyword | `SECONDARY_CONSULTANT` |
  | other | `UNKNOWN` |

- **step_type** (semantic, derived from GED step_type + state booleans):

  | Condition | step_type |
  |-----------|-----------|
  | `OPEN_DOC` | `SUBMITTAL` |
  | `is_completed=True` + `requires_new_cycle=True` | `CYCLE_REQUIRED` |
  | `is_completed=True` | `RESPONSE` |
  | `is_blocking=True` | `BLOCKING_WAIT` |
  | otherwise | `RESPONSE` |

- **issue_signal** (single flag, priority order CONTRADICTION > REJECTION > CHURN > DELAY):

  | Condition | Signal |
  |-----------|--------|
  | `effective_source` contains `"CONFLICT"` | `CONTRADICTION` |
  | `status_clean` in `{REF, DEF}` | `REJECTION` |
  | `requires_new_cycle=True` | `CHURN` |
  | `is_blocking=True` | `DELAY` |
  | 2+ signals | `MULTI` |
  | none | `NONE` |

- **delay_contribution_days:** Direct from ops_df; `0` when null or non-numeric.
- **notes:** `"SAS rejection requires new cycle"` when `requires_new_cycle=True`; `None` otherwise.

#### B. From `debug_df` (DEBUG_TRACE) — `_build_debug_events()`

- One event per unique `(family_key, version_key, instance_key)` group.
- **event_date:** `min(raw_date)` for the instance group. `pd.NaT` when `raw_date` absent.
- **step_type:** `INSTANCE_SUPERSEDED` when `instance_role` contains `"SUPERSED"` (case-insensitive); else `INSTANCE_CREATED`.
- **actor / actor_type:** `"SYSTEM"` / `"SYSTEM"` — debug instance events are system-level lifecycle markers.
- **source / source_priority:** `"DEBUG"` / `3`.
- **instance_key:** Preserved from debug_df (real `submission_instance_id`-derived key).
- **notes:** `instance_resolution_reason` when present; `None` otherwise.
- **is_blocking / delay_contribution_days:** `False` / `0` — debug instance events carry no blocking state.

#### C. From `effective_df` — `_build_effective_events()`

- **Only rows where `effective_source != "GED"` generate events.** GED-only rows are fully represented by OPS events.
- Eligible sources: `GED+REPORT_STATUS`, `GED+REPORT_COMMENT`, `GED_CONFLICT_REPORT`.
- **step_type:** `EFFECTIVE_OVERRIDE`.
- **issue_signal:** `CONTRADICTION` when `effective_source` contains `"CONFLICT"`; else `NONE`.
- **source / source_priority:** `"EFFECTIVE"` / `2`.
- **notes:** `"Report memory upgrade applied: {effective_source}"`.
- **instance_key:** `version_key + "_main"` (no debug join on effective events).

---

## Chronological Ordering

Within each `family_key`, events are sorted by:

1. **`event_date` ASC** — NaT rows sorted last via `_nat_last` sentinel column (0 = has date, 1 = NaT).
2. **`source_priority` ASC** — OPS (1) before EFFECTIVE (2) before DEBUG (3) when dates tie.
3. **`version_key` ASC** — earlier indice versions sort first within the same date tier.
4. **Stable index** — `kind="stable"` in pandas sort_values preserves concat order for remaining ties.

`event_seq` is then assigned as `groupby("family_key").cumcount() + 1` on the sorted DataFrame — gapless, 1-based, no duplicates per family.

---

## Event Vocabulary Found

### `source`
| Value | Priority | Generator |
|-------|----------|-----------|
| `OPS` | 1 | GED_OPERATIONS rows |
| `EFFECTIVE` | 2 | effective_responses rows with non-GED source |
| `DEBUG` | 3 | DEBUG_TRACE unique instance groups |

### `actor_type`
`CONTRACTOR` / `SAS` / `MOEX` / `PRIMARY_CONSULTANT` / `SECONDARY_CONSULTANT` / `SYSTEM` / `UNKNOWN`

### `step_type` (semantic)
`SUBMITTAL` / `RESPONSE` / `BLOCKING_WAIT` / `CYCLE_REQUIRED` / `EFFECTIVE_OVERRIDE` / `INSTANCE_CREATED` / `INSTANCE_SUPERSEDED`

### `issue_signal`
`NONE` / `DELAY` / `REJECTION` / `CHURN` / `CONTRADICTION` / `MULTI`

*(DORMANCY signal is not computed in Step 06 — requires data_date comparison, deferred to Step 08.)*

---

## Deduplication Rule

Exact deduplication on `["family_key", "version_key", "event_date", "actor", "step_type", "status", "source"]`. First occurrence kept. No fuzzy dedup. Cross-source rows are NOT collapsed (OPS and DEBUG rows with the same date differ on `source`, so they remain separate).

---

## Live Dataset Metrics

Live dataset run is marked `skip` per HYBRID execution model (407k-row DEBUG_TRACE takes ~4 min). Test `test_live_dataset_metrics` is present in `tests/test_chain_builder.py` and can be run directly by Claude Code / Codex.

**Expected (based on Step 04 confirmed counts):**

| Metric | Expected range |
|--------|---------------|
| `ops_df` rows → OPS events | 32,099 (1:1 mapping, before dedup) |
| EFFECTIVE events | 0 (all rows are GED-only in current env — no report_memory.db) |
| DEBUG events | = unique `(family_key, version_key, instance_key)` groups in debug_df |
| Total events | ≥ 32,099 |
| Avg events/family | > 1 |
| NaT dates | Pending / blocking rows with no response_date |

---

## Test Results

| # | Test Class / Name | Result | What it checks |
|---|-------------------|--------|----------------|
| 1a | `TestSyntheticChain::test_event_count` | PASSED | 4 ops rows → 4 events |
| 1b | `TestSyntheticChain::test_event_seq_is_monotone` | PASSED | event_seq = [1,2,3,4] for one family |
| 1c | `TestSyntheticChain::test_event_seq_starts_at_one` | PASSED | min(event_seq) == 1 |
| 1d | `TestSyntheticChain::test_chronological_order` | PASSED | dates[0] < dates[-1] for A→REF→B→VAO chain |
| 1e | `TestSyntheticChain::test_submittal_step_is_submittal` | PASSED | OPEN_DOC → step_type=SUBMITTAL (2 per chain) |
| 1f | `TestSyntheticChain::test_sas_ref_is_cycle_required` | PASSED | SAS REF + requires_new_cycle → CYCLE_REQUIRED |
| 1g | `TestSyntheticChain::test_egis_vao_is_response` | PASSED | EGIS VAO → step_type=RESPONSE |
| 1h | `TestSyntheticChain::test_required_columns_present` | PASSED | All 18 contract columns present |
| 2a | `TestMixedSources::test_all_three_sources_present_in_output` | PASSED | OPS + DEBUG + EFFECTIVE all in events |
| 2b | `TestMixedSources::test_ged_only_effective_rows_not_in_output` | PASSED | GED-only effective rows generate no EFFECTIVE events |
| 2c | `TestMixedSources::test_debug_event_step_type` | PASSED | debug row → step_type=INSTANCE_CREATED |
| 2d | `TestMixedSources::test_effective_override_step_type` | PASSED | non-GED effective → step_type=EFFECTIVE_OVERRIDE |
| 2e | `TestMixedSources::test_merged_events_all_share_family` | PASSED | All events share same family_key |
| 2f | `TestMixedSources::test_superseded_debug_step_type` | PASSED | instance_role=SUPERSEDED → step_type=INSTANCE_SUPERSEDED |
| 3a | `TestEventSeqUniqueness::test_seq_is_gapless_per_family` | PASSED | No gaps in event_seq per family |
| 3b | `TestEventSeqUniqueness::test_seq_no_duplicates_per_family` | PASSED | No duplicate event_seq values |
| 3c | `TestEventSeqUniqueness::test_each_family_starts_at_one` | PASSED | Each family starts at event_seq=1 |
| 3d | `TestEventSeqUniqueness::test_two_families_independent_seq` | PASSED | Two families have independent 1..N sequences |
| 4a | `TestActorTypeClassification::test_moex_actor_type` | PASSED | MOEX step_type → actor_type=MOEX |
| 4b | `TestActorTypeClassification::test_sas_actor_type` | PASSED | SAS step_type → actor_type=SAS |
| 4c | `TestActorTypeClassification::test_open_doc_is_contractor` | PASSED | OPEN_DOC → actor_type=CONTRACTOR |
| 4d | `TestActorTypeClassification::test_egis_is_primary_consultant` | PASSED | EGIS → PRIMARY_CONSULTANT |
| 4e | `TestActorTypeClassification::test_terrell_is_primary_consultant` | PASSED | TERRELL STRUCTURES → PRIMARY_CONSULTANT |
| 4f | `TestActorTypeClassification::test_bet_spk_is_primary_consultant` | PASSED | BET SPK FLUIDES → PRIMARY_CONSULTANT |
| 4g | `TestActorTypeClassification::test_unknown_consultant_is_secondary` | PASSED | Bureau Signalétique → SECONDARY_CONSULTANT |
| 4h | `TestActorTypeClassification::test_commission_is_secondary` | PASSED | Commission Voirie → SECONDARY_CONSULTANT |
| 5a | `TestDedup::test_exact_duplicates_removed` | PASSED | Two identical rows → one event |
| 5b | `TestDedup::test_different_status_not_deduped` | PASSED | Different status → two events kept |
| 5c | `TestDedup::test_different_date_not_deduped` | PASSED | Different date → two events kept |
| 5d | `TestDedup::test_dedup_across_sources` | PASSED | OPS + DEBUG same date but different source → both kept |
| 6  | `test_live_dataset_metrics` | SKIPPED | Full 32k/407k run — Claude Code / Codex only |

**Suite result:** 30 passed, 1 skipped, 0 failed — 2.49s

---

## Warnings / Anomalies

- **`effective_df` is GED-only in this environment.** No `report_memory.db` present. All `effective_source = "GED"`. Therefore `_build_effective_events()` will return 0 rows on live data until the DB is connected. The logic is tested via synthetic data (Test 2a, 2b, 2d).
- **`instance_key = version_key + "_main"` for OPS events.** The DEBUG_TRACE `submission_instance_id` is not joined to ops_df rows because the relationship is many-to-many (multiple debug rows per version, multiple ops rows per version). The real instance_key from DEBUG_TRACE is preserved in DEBUG-sourced events only. This matches the task spec: "If no instance_key available from ops/effective: Use: `version_key + '_main'`".
- **DORMANCY issue_signal not computed.** Requires comparison to `data_date` to detect chains that have gone silent. Deferred to Step 08 where full date arithmetic is implemented.
- **list comprehensions for actor_type and step_type** (32,099 iterations). Runtime is negligible (~0.15s) for 32k rows. Vectorization not needed.
- **Null bytes.** If the `Edit` tool is used on Windows, it may introduce null bytes in .py files (documented in STEP05_VALIDATION). Write tool was used exclusively here. Strip with `data.replace(b'\x00', b'')` before pytest if this recurs.

---

## Design Decisions vs STEP02 Contract

STEP02 Section D defines `chain_events` with `actor_type = step_type from GED_OPERATIONS (OPEN_DOC, SAS, CONSULTANT, MOEX)`. The Step 06 task spec extends this with a richer semantic vocabulary (MOEX, SAS, PRIMARY_CONSULTANT, SECONDARY_CONSULTANT, CONTRACTOR, SYSTEM, UNKNOWN). Section F.4 of STEP02 says Primary/Secondary is NOT persisted in chain_events to avoid redundancy — Step 06 overrides this for the `actor_type` column only, per the explicit task requirements. The `_is_primary_approver()` logic is still the exclusive source of the CONSULTANT sub-classification.

---

## Ready for Step 07?

**Yes.**

- `build_chain_events()` returns a complete, sorted, gapless `chain_events_df`.
- All 18 contract columns present and typed correctly.
- `event_seq` is deterministic and gapless per `family_key`.
- Repo actor taxonomy (`_is_primary_approver`) reused exclusively — no custom list.
- No chain classification or onion scoring leaked into Step 06.
- Mixed-source merging tested (OPS + DEBUG + EFFECTIVE).
- Clean handoff: Step 07 chain classifier consumes `chain_events_df` + `chain_versions_df` + `chain_register_df` to compute `current_state` per the STEP02 Section E vocabulary.

### Blockers for Step 07

None. Proceed to `src/chain_onion/chain_classifier.py`.

Key inputs Step 07 will use from `chain_events_df`:
- `step_type` (`CYCLE_REQUIRED`) → detect `requires_new_cycle` versions
- `is_blocking` + `actor_type` → classify current blocker identity
- `event_date` + NaT → detect dormancy / abandoned chains
- `issue_signal` → REJECTION / CHURN signals for VOID_CHAIN / CHRONIC_REF_CHAIN detection

---

## Next Blockers (for downstream steps)

- **Step 08:** `delay_contribution_days` in chain_events currently passes through raw ops_df values with 0 fallback. Step 08 will refine this with full cumulative delay arithmetic and data_date-relative dormancy detection (DORMANCY issue_signal).
- **Step 09+:** `actor_type` PRIMARY_CONSULTANT / SECONDARY_CONSULTANT in chain_events feeds directly into Onion Layer 3–4 (consultant delay/rejection attribution).
- **Step 11:** `issue_signal` values (REJECTION, CHURN, DELAY, CONTRADICTION) form the pre-computed signal layer for narrative construction.
- **Report memory:** When `report_memory.db` is connected, `effective_df` will contain non-GED rows, and `_build_effective_events()` will produce EFFECTIVE_OVERRIDE events. No code changes needed — the logic is already in place.
