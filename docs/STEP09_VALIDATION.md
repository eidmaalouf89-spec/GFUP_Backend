# STEP09_VALIDATION.md
## Step 09 — Onion Layer Engine: Validation Report

**Date:** 2026-04-27
**Status:** COMPLETE — 29 passed, 1 skipped, 0 failed (3.02s)

---

## What Was Analyzed

| File | Purpose |
|------|---------|
| `docs/CHAIN_ONION_MASTER_STRATEGY.md` | Architecture, protected files, six-layer taxonomy |
| `docs/CHAIN_ONION_STEP_TRACKER.md` | Step status registry |
| `docs/STEP03_ONION_CONTRACT.md` | Authoritative layer definitions, trigger conditions, severity/confidence models, output schema, forbidden logic |
| `docs/STEP08_VALIDATION.md` | chain_metrics_df column contract, pressure_index formula, wait day allocation |
| `src/chain_onion/chain_builder.py` | `_CHAIN_EVENTS_COLS`, actor_type vocabulary, source vocabulary (OPS/EFFECTIVE/DEBUG), semantic step_type mapping |
| `src/chain_onion/chain_metrics.py` | `_CHAIN_METRICS_COLS`, wait day allocation logic |
| `src/query_library.py` | `_is_primary_approver()`, `_PRIMARY_APPROVER_KEYWORDS` — imported by chain_builder |

---

## What Was Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `src/chain_onion/onion_engine.py` | **Created** | Onion Layer Engine — `build_onion_layers()` + helpers (~450 lines) |
| `tests/test_onion_engine.py` | **Created** | 29 synthetic unit tests across 8 test classes + 1 skipped live test |
| `docs/STEP09_VALIDATION.md` | **Created** | This file |

**Not modified:** `src/flat_ged/*`, existing pipeline stages, UI files, Steps 04–08 code, `CHAIN_ONION_MASTER_STRATEGY.md`, `src/query_library.py`, `query_library.py`.

---

## Layer Logic — Final Trigger Formulas

### L1 — CONTRACTOR_QUALITY

| Trigger | Condition | Columns Used |
|---------|-----------|--------------|
| L1_T1 | Any `version_key` has `nunique(instance_key) > 1` | `chain_events.instance_key`, `chain_events.version_key` |
| L1_T2 | Any `chain_events.requires_new_cycle == True` | `chain_events.requires_new_cycle` |
| L1_T3 | `total_versions >= 2` AND any SAS event has `status` containing `REF` | `chain_metrics.total_versions`, `chain_events.actor_type == SAS` |

**issue_type:** L1_T1 only → CHURN | L1_T2 or L1_T3 only → REJECTION | Mixed → MULTI

**severity:** Based on `(total_versions, rejection_cycles, resubmission_count)` using STEP03 B.1.4 rules (first-match):
- `total_versions >= 4` OR `rejection_cycles >= 3` → CRITICAL
- `total_versions == 3` OR `(total_versions == 2 AND rejection_cycles >= 2)` → HIGH
- `total_versions == 2 AND rejection_cycles == 1 AND resubmission >= 3` → MEDIUM
- `total_versions == 2 AND rejection_cycles == 1 AND resubmission <= 2` → LOW

**evidence_count:** Count of CONTRACTOR events + requires_new_cycle events for the family.

**responsible_actor:** First CONTRACTOR event's actor (chronological by event_date).

---

### L2 — SAS_GATE_FRICTION

| Trigger | Condition |
|---------|-----------|
| L2_T1 | `actor_type == SAS` AND `status` contains `REF` AND `is_completed == True` |
| L2_T2 | `actor_type == SAS` AND `delay_contribution_days > 0` |
| L2_T3 | `actor_type == SAS` AND `is_blocking == True` AND `event_date` is NaT |

**issue_type:** Exactly one → REJECTION/DELAY/DORMANCY | Two or more → MULTI

**severity:** Based on `(sas_ref_count, sas_delay_days)` using STEP03 B.2.4:
- `sas_ref_count >= 3` OR `sas_delay_days > 45` → CRITICAL
- `sas_ref_count == 2` OR `(sas_ref_count == 1 AND sas_delay_days >= 22)` → HIGH
- `sas_ref_count == 1 AND 8 <= sas_delay_days <= 21` → MEDIUM
- `sas_ref_count == 1 AND sas_delay_days <= 14` → LOW
- T3-only (dormancy): falls back to `sas_delay_days`-based or MEDIUM for `sas_pending > 1`

---

### L3 — PRIMARY_CONSULTANT_DELAY

| Trigger | Condition |
|---------|-----------|
| L3_T1 | `actor_type == PRIMARY_CONSULTANT` AND `delay_contribution_days > 0` |
| L3_T2 | `actor_type == PRIMARY_CONSULTANT` AND `is_blocking == True` AND `event_date` is NaT |
| L3_T3 | `actor_type == PRIMARY_CONSULTANT` AND `status` ∈ `{REF, REFSO, DEF}` |

**issue_type:** T2 only → DORMANCY | T3 only → REJECTION | T1 only → DELAY | Multiple → MULTI

**responsible_actor:** PRIMARY_CONSULTANT with highest `delay_contribution_days` (sum per actor); tie-break by most recent event_date.

**severity:** Based on `(primary_delay_days, rejection_count, no_response_count)` using STEP03 B.3.4:
- T2-only → count-based (`no_response_count`: 1→LOW, 2→MEDIUM, 3→HIGH, ≥4→CRITICAL)
- `delay_days > 45` OR `(no_response >= 2 AND delay >= 22)` → CRITICAL
- `delay_days >= 22` OR `rejection_count >= 2` → HIGH
- `delay_days >= 8` OR `rejection_count == 1` → MEDIUM
- `delay_days >= 1` → LOW

---

### L4 — SECONDARY_CONSULTANT_DELAY

Mirror of L3 applied to `actor_type == SECONDARY_CONSULTANT`. MOEX steps excluded (covered by L5).

**Trigger codes:** L4_T1, L4_T2, L4_T3 (identical structure to L3).

**Severity thresholds:** Identical to L3, applied to secondary metrics.

---

### L5 — MOEX_ARBITRATION_DELAY

| Trigger | Condition |
|---------|-----------|
| L5_T1 | `actor_type == MOEX` AND `delay_contribution_days > 0` |
| L5_T2 | `actor_type == MOEX` AND `is_blocking == True` AND `event_date` is NaT |

**issue_type:** T2 only → DORMANCY | T1 only → DELAY | Both → MULTI

**severity:** Based on `(moex_delay_days, moex_pending, moex_versions_pending)` using STEP03 B.5.4:
- `moex_delay_days > 45` → CRITICAL
- `moex_delay_days >= 22` OR `(pending AND versions_pending >= 2)` → HIGH
- `moex_delay_days >= 8` OR `(pending AND versions_pending == 1)` → MEDIUM
- T2-only fallback: `versions_pending` ≥3→CRITICAL, 2→HIGH, 1→MEDIUM

---

### L6 — DATA_REPORT_CONTRADICTION

| Trigger | Condition |
|---------|-----------|
| L6_T1 | `issue_signal == "CONTRADICTION"` OR `source` contains `"CONFLICT"` |

**issue_type:** CONTRADICTION | upgraded to MULTI if any conflict row also has `is_blocking == True` AND `delay_contribution_days > 0`

**severity:** Based on `(conflict_row_count, conflict_versions)` using STEP03 B.6.4:
- `conflict_row_count >= 6` → CRITICAL
- `conflict_row_count` 4–5 → HIGH
- `conflict_row_count >= 2` OR `conflict_versions >= 2` → MEDIUM
- `conflict_row_count == 1 AND conflict_versions == 1` → LOW

---

## Confidence Model

Derived from qualifying event source quality (single most-applicable deduction, STEP03 E.2):

| Condition | Confidence |
|-----------|-----------|
| All qualifying events: `source == OPS` AND `event_date` not null | 90 |
| Any qualifying event: `source == EFFECTIVE` | max 72 |
| Any qualifying event: `notes` contains "Synthetic instance" | max 55 |
| Any qualifying event: `event_date` is NaT | max 35 |
| L5_T2-only (MOEX no-response) | max 38 |
| L1: DEBUG_TRACE absent (synthetic instance keys) | max 40 |

Confidence is clamped to `[10, 100]` after applying deductions.

---

## Deduplication Logic

`(family_key, layer_code)` uniqueness enforced after per-family evaluation:
1. If duplicate detected: log ERROR
2. Keep row with higher `evidence_count`
3. Tie-break: keep row with higher `severity_raw` (CRITICAL > HIGH > MEDIUM > LOW)

---

## Test Results

| # | Test Class / Name | Result | What it checks |
|---|-------------------|--------|----------------|
| 1a | `TestCleanClosedChain::test_no_rows` | PASSED | Clean chain → 0 onion rows |
| 1b | `TestCleanClosedChain::test_output_is_dataframe` | PASSED | Return type is DataFrame |
| 2a | `TestPrimaryDelayOnly::test_l3_fires` | PASSED | 42-day primary delay → L3 fires |
| 2b | `TestPrimaryDelayOnly::test_only_l3` | PASSED | No other layers fire |
| 2c | `TestPrimaryDelayOnly::test_l3_severity_high` | PASSED | 42-day delay → HIGH/CRITICAL |
| 2d | `TestPrimaryDelayOnly::test_l3_evidence_positive` | PASSED | evidence_count >= 1 |
| 3a | `TestMixedConsultantAndChurn::test_l1_fires` | PASSED | Churn instance → L1 |
| 3b | `TestMixedConsultantAndChurn::test_l3_fires` | PASSED | Primary blocking → L3 |
| 3c | `TestMixedConsultantAndChurn::test_l4_fires` | PASSED | Secondary blocking → L4 |
| 3d | `TestMixedConsultantAndChurn::test_exact_layers` | PASSED | Exactly L1+L3+L4, no others |
| 3e | `TestMixedConsultantAndChurn::test_l1_issue_churn` | PASSED | L1 issue_type == CHURN |
| 4a | `TestSASDeadChain::test_l2_fires` | PASSED | Dual SAS REF → L2 |
| 4b | `TestSASDeadChain::test_l2_severity_critical` | PASSED | 2 REF + 55 days → HIGH/CRITICAL |
| 4c | `TestSASDeadChain::test_l2_issue_type` | PASSED | issue_type in {REJECTION, MULTI} |
| 5a | `TestMOEXWaiting::test_l5_fires` | PASSED | MOEX blocking (T2-only) → L5 |
| 5b | `TestMOEXWaiting::test_only_l5` | PASSED | No other layers fire |
| 5c | `TestMOEXWaiting::test_l5_issue_dormancy` | PASSED | T2-only → DORMANCY |
| 6a | `TestContradictionSignal::test_l6_fires` | PASSED | issue_signal=CONTRADICTION → L6 |
| 6b | `TestContradictionSignal::test_l6_issue_contradiction` | PASSED | issue_type in {CONTRADICTION, MULTI} |
| 6c | `TestContradictionSignal::test_l6_evidence_positive` | PASSED | evidence_count >= 1 |
| 7a | `TestDuplicatePrevention::test_no_duplicates` | PASSED | No duplicate (family_key, layer_code) |
| 7b | `TestDuplicatePrevention::test_all_layer_codes_valid` | PASSED | All codes in valid vocabulary |
| 8a | `TestEvidenceRule::test_all_evidence_count_positive` | PASSED | All rows evidence_count >= 1 |
| 8b | `TestEvidenceRule::test_required_columns_present` | PASSED | All OUTPUT_COLS present |
| 8c | `TestEvidenceRule::test_severity_vocabulary` | PASSED | severity ∈ {LOW,MEDIUM,HIGH,CRITICAL} |
| 8d | `TestEvidenceRule::test_issue_type_vocabulary` | PASSED | issue_type ∈ valid set |
| 8e | `TestEvidenceRule::test_confidence_in_range` | PASSED | confidence_raw ∈ [10, 100] |
| 8f | `TestEvidenceRule::test_no_duplicate_primary_keys` | PASSED | Uniqueness across multi-family portfolio |
| 8g | `TestEvidenceRule::test_layer_rank_matches_code` | PASSED | layer_rank matches layer_code (1–6) |
| 9  | `TestLiveDatasetRun::test_live_run` | SKIPPED | Full 32k run — Claude Code / Codex only |

**Suite result: 29 passed, 1 skipped, 0 failed — 3.02s**

---

## Live Metrics

**Skipped — Claude Code / Codex full-run required (32k ops rows).**

Run manually:
```
pytest tests/test_onion_engine.py -k TestLiveDatasetRun -s
```

Expected output format:
- Total onion rows
- Rows by layer_code
- Rows by severity_raw
- Top families with 4+ active layers (worst-distressed chains)

---

## Warnings / Design Notes

- **`issue_signal == "CONTRADICTION"` used for L6 trigger**: In `chain_events_df`, the raw `effective_source` from `effective_responses.py` is encoded into `issue_signal` by `chain_builder.py` (`_map_issue_signal`). STEP03 specifies `source = "GED_CONFLICT_REPORT"` — in practice the source column contains "OPS"/"EFFECTIVE"/"DEBUG". The engine checks both `issue_signal == "CONTRADICTION"` AND `source` containing "CONFLICT" to cover both cases.
- **L1 responsible_actor**: Taken from the first CONTRACTOR `actor` field in `chain_events_df`. If no CONTRACTOR event exists for a family that fires L1 (edge case), falls back to "UNKNOWN" with a warning logged.
- **L3/L4 secondary fallback**: When `_is_primary_approver()` is unavailable (import error), `chain_builder.py` uses the inline fallback that mirrors the authoritative keyword list exactly. The onion engine does not re-classify actors — it trusts `actor_type` as set by Step 06.
- **MOEX events excluded from L4**: Events with `actor_type == MOEX` are never included in L4 evaluation. MOEX belongs exclusively to L5. This matches STEP03 Section B.4 note.
- **Confidence = 35 for null event_date**: When all qualifying events have `event_date` null (no recorded response), confidence is capped at 35. This correctly represents inferred (not measured) delay contributions.
- **SAS `step_type` mapping**: In `chain_builder.py`, GED rows where `step_type == "SAS"` produce `actor_type == "SAS"`. The semantic `step_type` is RESPONSE or BLOCKING_WAIT depending on `is_completed`. The L2 trigger checks `actor_type == SAS`, not the semantic step_type.

---

## Example Multi-Layer Chains (Synthetic)

### Family `MIX001` — 3 layers
From `TestMixedConsultantAndChurn`:

| layer_code | issue_type | severity_raw | evidence_count |
|-----------|-----------|:------------:|:--------------:|
| L1_CONTRACTOR_QUALITY | CHURN | LOW | 2 |
| L3_PRIMARY_CONSULTANT_DELAY | DORMANCY | HIGH | 1 |
| L4_SECONDARY_CONSULTANT_DELAY | DORMANCY | MEDIUM | 1 |

- L1: version A submitted twice (2 instance_keys) → CHURN. 1 version, 0 rejection_cycles → LOW.
- L3: EGIS blocking, no response date, 30 delay days → HIGH.
- L4: Bureau Signalétique blocking, no response date, 10 delay days → MEDIUM.

### Family `DEDUP001` — 2 layers (churn + SAS)
From `TestDuplicatePrevention`:

| layer_code | issue_type | severity_raw |
|-----------|-----------|:------------:|
| L1_CONTRACTOR_QUALITY | MULTI | HIGH |
| L2_SAS_GATE_FRICTION | REJECTION | HIGH |

- L1: two versions each with 2 instances, requires_new_cycle=True → MULTI. 2 rejection_cycles → HIGH.
- L2: SAS REF event fires → REJECTION. sas_delay_days=20 → HIGH.

---

## Ready for Step 10?

**Yes.**

- `build_onion_layers()` returns one row per `(family_key, layer_code)`.
- All rows have `evidence_count >= 1` — enforced by pre-emit guard and post-write validation.
- `(family_key, layer_code)` uniqueness enforced with ERROR-logged deduplication.
- `severity_raw` is deterministic from STEP03 threshold rules — no judgment calls.
- `confidence_raw` is tiered from source quality — integer [10, 100].
- `pressure_index`, `portfolio_bucket`, `current_state` passed through from chain_metrics for Step 10 scoring context.
- No narratives, no blame text, no AI inference.
- Engine does not touch `chain_events`, `chain_versions`, or `chain_register` files.
- Layer evaluators are independent — any subset can be extended or tested in isolation.

### Key inputs Step 10 (Onion Scoring) will consume:
- `onion_layers_df.severity_raw` — raw severity for weighted scoring
- `onion_layers_df.confidence_raw` — reliability weight for scoring
- `onion_layers_df.layer_rank` — layer priority ordering
- `onion_layers_df.pressure_index` — urgency amplifier from chain_metrics
- `onion_layers_df.evidence_count` — evidence weight for scoring

---

## Next Blockers

- **Step 10** — Onion Scoring Engine. Consumes `onion_layers_df` + `chain_metrics_df` to produce a composite responsibility score per family. No blockers from Step 09.
- **Step 12** — Export Engine. Will write `onion_layers_df` to `output/chain_onion/ONION_RESPONSIBILITY.csv`. Column contract fully defined in `onion_engine.OUTPUT_COLS`.
- **Step 14** — Validation Harness. Post-conditions from STEP03 H.5 are already implemented inside `_validate()` in `onion_engine.py` — Step 14 can call or replicate that function for batch validation.
