# STEP10_VALIDATION.md
## Step 10 — Onion Scoring Engine: Validation Report

**Date:** 2026-04-27
**Status:** COMPLETE — 43 passed, 1 skipped, 0 failed (3.03s)

---

## What Was Analyzed

| File | Purpose |
|------|---------|
| `docs/CHAIN_ONION_MASTER_STRATEGY.md` | Architecture, protected files, six-layer taxonomy |
| `docs/CHAIN_ONION_STEP_TRACKER.md` | Step status registry |
| `docs/STEP03_ONION_CONTRACT.md` | Layer definitions, severity/confidence models, output schema |
| `docs/STEP07_VALIDATION.md` | `current_state`, `portfolio_bucket`, `operational_relevance_score` column contracts |
| `docs/STEP08_VALIDATION.md` | `pressure_index` formula, `chain_metrics_df` column contract (28 columns) |
| `docs/STEP09_VALIDATION.md` | `onion_layers_df` column contract (`OUTPUT_COLS`): `severity_raw`, `confidence_raw`, `pressure_index`, `evidence_count`, `latest_trigger_date`, `layer_code`, `layer_name` |
| `src/chain_onion/onion_engine.py` | `OUTPUT_COLS` exact list, `ENGINE_VERSION`, `_build_row` output structure |
| `src/chain_onion/chain_metrics.py` | `pressure_index` formula confirmed, `portfolio_bucket` values |

---

## What Was Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `src/chain_onion/onion_scoring.py` | **Created** | Onion Scoring Engine — `build_onion_scores()` + helpers (~310 lines) |
| `tests/test_onion_scoring.py` | **Created** | 43 synthetic unit tests across 8 test classes + 1 skipped live test |
| `docs/STEP10_VALIDATION.md` | **Created** | This file |

**Not modified:** `src/flat_ged/*`, existing pipeline stages, UI files, Steps 04–09 code, `CHAIN_ONION_MASTER_STRATEGY.md`, `src/query_library.py`, `onion_engine.py`, `chain_metrics.py`.

---

## Final Formulas

### Layer Score Formula

```
layer_score = severity_weight * confidence_factor * pressure_factor
              * recency_factor * evidence_factor

severity_weight  : LOW=10.0 | MEDIUM=25.0 | HIGH=50.0 | CRITICAL=80.0
confidence_factor: confidence_raw / 100  (confidence_raw ∈ [10, 100])
pressure_factor  : 0.60 + (pressure_index / 100)
                   → pressure=0 gives 0.60; pressure=100 gives 1.60
evidence_factor  : 1 + min(evidence_count, 5) × 0.08  — capped at 1.40
                   → 1 event = 1.08; 5+ events = 1.40
recency_factor   : days(data_date − latest_trigger_date)
                   ≤ 30d  → 1.20
                   31–90d → 1.00
                   91–180d→ 0.80
                   > 180d → 0.60
                   null   → 0.75
```

**Portfolio reference date:** `max(latest_trigger_date)` across all onion layer rows.

### Chain-Level Score

```
total_onion_score  = Σ layer_scores for all active layers of the family
normalized_score_100 = (total_onion_score / portfolio_max) × 100
                       clamped to [0, 100]
                       if portfolio_max == 0: normalized = 0
```

### Blended Confidence

```
blended_confidence = Σ(confidence_raw × layer_score) / Σ(layer_score)
                     0 if no layers (zero-score family)
```

### Action Priority Rank

Dense rank (1 = most urgent) by compound key:
1. `normalized_score_100` descending
2. `portfolio_bucket`: LIVE_OPERATIONAL < LEGACY_BACKLOG < ARCHIVED_HISTORICAL
3. `evidence_layers_count` descending
4. `family_key` ascending (stable tie-break, does not affect dense group boundaries)

### Escalation Flag Rules (OR logic)

| Rule | Condition |
|------|-----------|
| High score | `normalized_score_100 >= 85` |
| Critical top layer | `top_layer severity == CRITICAL` |
| 3+ active layers on live | `evidence_layers_count >= 3 AND portfolio_bucket == "LIVE_OPERATIONAL"` |
| Contradiction + pressure | `L6 layer present AND normalized_score_100 >= 70` |

---

## Layer → Responsibility Theme Map

| Layer Code | Theme Bucket Column |
|------------|-------------------|
| `L1_CONTRACTOR_QUALITY` | `contractor_impact_score` |
| `L2_SAS_GATE_FRICTION` | `sas_impact_score` |
| `L3_PRIMARY_CONSULTANT_DELAY` | `consultant_primary_impact_score` |
| `L4_SECONDARY_CONSULTANT_DELAY` | `consultant_secondary_impact_score` |
| `L5_MOEX_ARBITRATION_DELAY` | `moex_impact_score` |
| `L6_DATA_REPORT_CONTRADICTION` | `contradiction_impact_score` |

`total_onion_score = Σ all six theme buckets` (exact equality enforced by Test 6).

---

## Design Decisions

1. **Zero-score families included** — All families from `chain_register_df` are included even when absent from `onion_layers_df`, with all scores set to 0. This preserves portfolio completeness and allows the export layer to know which families were evaluated.
2. **Portfolio reference date from onion data** — `data_date` is derived as the max `latest_trigger_date` across all onion layer rows, not from `ops_df`. This keeps Step 10 downstream-only (no raw source reads).
3. **State context priority** — For each family: `chain_metrics_df` > `chain_register_df` > `onion_layers_df` row. First non-empty string wins. This ensures the most enriched classification is used.
4. **Vectorised layer score computation** — `_compute_layer_scores` uses pandas Series operations (not row-level `apply`) for all factors except recency (which requires per-row date parsing).
5. **Neutral language enforced** — No words "guilty", "liable", "responsible legally", or "misconduct" appear anywhere in the engine output. All columns describe operational impact metrics only.

---

## Live Outputs

**Skipped — Claude Code / Codex full-run required (32k ops / 407k debug rows).**

Run manually:
```
pytest tests/test_onion_scoring.py -k TestLiveRun -s
```

Expected output format defined in `TestLiveRun.test_live_run`:
- Total scored chains / bucket split
- avg, p90, max normalized scores
- live / legacy / archived avg scores
- escalated chain count
- top theme by total impact
- Top 20 chains by normalized_score_100
- Score histogram in bands [0,10), [10,25), [25,50), [50,75), [75,90), [90,100)

---

## Escalation Stats (Synthetic Tests)

From `TestCriticalLiveChain`:
- 1 CRITICAL live chain with LIVE_OPERATIONAL bucket, pressure=80, recent trigger
- Escalation reason: `"critical top layer"` (confirmed by test)
- 1 LOW legacy chain: escalation_flag = False (confirmed)

From `TestBounds` (4-family portfolio):
- `escalated_chain_count >= 0` confirmed
- CRITICAL chain with score=100.0 is escalated by the "high normalized score" rule

---

## Test Results

| # | Test Class / Name | Result | What it checks |
|---|-------------------|--------|----------------|
| 1a | `TestSingleLowLayer::test_returns_dataframe` | PASSED | Return type is DataFrame |
| 1b | `TestSingleLowLayer::test_one_row` | PASSED | One family → 1 row |
| 1c | `TestSingleLowLayer::test_low_total_score` | PASSED | LOW layer score < 15 |
| 1d | `TestSingleLowLayer::test_normalized_is_100_for_single_chain` | PASSED | Single-chain → normalized = 100 |
| 1e | `TestSingleLowLayer::test_required_columns` | PASSED | All 22 output columns present |
| 1f | `TestSingleLowLayer::test_top_layer_is_l3` | PASSED | top_layer_code = L3 |
| 1g | `TestSingleLowLayer::test_consultant_primary_bucket_populated` | PASSED | L3 → primary bucket > 0 |
| 2a | `TestCriticalLiveChain::test_critical_chain_normalized_high` | PASSED | CRITICAL → normalized = 100 |
| 2b | `TestCriticalLiveChain::test_critical_chain_escalated` | PASSED | escalation_flag = True |
| 2c | `TestCriticalLiveChain::test_escalation_reason_mentions_critical` | PASSED | reason contains "critical top layer" |
| 2d | `TestCriticalLiveChain::test_low_chain_not_escalated` | PASSED | LOW legacy → no escalation |
| 2e | `TestCriticalLiveChain::test_crit_ranks_first` | PASSED | CRITICAL chain rank = 1 |
| 3a | `TestConfidenceInfluence::test_high_confidence_scores_higher` | PASSED | conf=90 > conf=30 for same severity |
| 3b | `TestConfidenceInfluence::test_high_confidence_ranks_first` | PASSED | High confidence ranks before low |
| 3c | `TestConfidenceInfluence::test_normalized_scores_differ` | PASSED | Normalized scores reflect confidence gap |
| 4a | `TestRecencyEffect::test_recent_scores_higher` | PASSED | Recent trigger scores higher than stale |
| 4b | `TestRecencyEffect::test_recency_ratio` | PASSED | Recency 1.20 / 0.60 = 2.0 ratio confirmed |
| 5a | `TestMultiLayerSum::test_single_row_for_family` | PASSED | Multi-layer chain → 1 output row |
| 5b | `TestMultiLayerSum::test_evidence_layers_count_is_3` | PASSED | 3 layers → evidence_layers_count = 3 |
| 5c | `TestMultiLayerSum::test_total_score_sums_layers` | PASSED | total = Σ(layer_scores) exact match |
| 5d | `TestMultiLayerSum::test_top_layer_is_highest_scorer` | PASSED | L3 HIGH beats L1 LOW and L5 MEDIUM |
| 6a | `TestThemeBucketing::test_contractor_bucket_positive` | PASSED | L1 → contractor_impact_score > 0 |
| 6b | `TestThemeBucketing::test_sas_bucket_positive` | PASSED | L2 → sas_impact_score > 0 |
| 6c | `TestThemeBucketing::test_primary_bucket_positive` | PASSED | L3 → consultant_primary > 0 |
| 6d | `TestThemeBucketing::test_secondary_bucket_positive` | PASSED | L4 → consultant_secondary > 0 |
| 6e | `TestThemeBucketing::test_moex_bucket_positive` | PASSED | L5 → moex_impact_score > 0 |
| 6f | `TestThemeBucketing::test_contradiction_bucket_positive` | PASSED | L6 → contradiction_impact_score > 0 |
| 6g | `TestThemeBucketing::test_total_equals_sum_of_buckets` | PASSED | total = Σ buckets (exact) |
| 6h | `TestThemeBucketing::test_evidence_layers_count_is_6` | PASSED | All 6 layers → count = 6 |
| 7a | `TestRankingStable::test_ranks_are_positive` | PASSED | All ranks ≥ 1 |
| 7b | `TestRankingStable::test_live_high_ranks_before_legacy_high` | PASSED | LIVE before LEGACY at equal score |
| 7c | `TestRankingStable::test_high_severity_ranks_before_low` | PASSED | Higher score → lower rank number |
| 7d | `TestRankingStable::test_ranks_are_dense` | PASSED | No gaps in rank sequence |
| 7e | `TestRankingStable::test_deterministic_on_repeat_call` | PASSED | Same input → same rank output |
| 8a | `TestBounds::test_normalized_in_0_100` | PASSED | All normalized scores in [0, 100] |
| 8b | `TestBounds::test_blended_confidence_in_0_100` | PASSED | All blended_confidence in [0, 100] |
| 8c | `TestBounds::test_zero_score_family_present` | PASSED | No-onion family included with zeros |
| 8d | `TestBounds::test_max_normalized_is_100` | PASSED | Portfolio max always = 100 |
| 8e | `TestBounds::test_portfolio_max_score_100` | PASSED | summary["max_score"] = 100 |
| 8f | `TestBounds::test_total_scored_chains_is_4` | PASSED | All 4 families in output |
| 8g | `TestBounds::test_top_10_at_most_10` | PASSED | top_10_family_keys len ≤ 10 |
| 8h | `TestBounds::test_escalated_count_non_negative` | PASSED | escalated_chain_count ≥ 0 |
| 8i | `TestBounds::test_evidence_layers_count_non_negative` | PASSED | evidence_layers_count ≥ 0 |
| 9  | `TestLiveRun::test_live_run` | SKIPPED | Full run — Claude Code / Codex only |

**Suite result: 43 passed, 1 skipped, 0 failed — 3.03s**

---

## Warnings / Design Notes

- **`portfolio_date` from trigger dates only**: Step 10 does not read `ops_df` directly. The reference date for recency is derived as the max `latest_trigger_date` across all onion layer rows. If all trigger dates are null, recency defaults to 0.75 for all rows (WARNING logged).
- **Zero-score families included**: Families present in `chain_register_df` but absent from `onion_layers_df` are included with all impact scores = 0 and `evidence_layers_count = 0`. They receive the lowest possible ranks (after all scored chains). This is documented as the chosen behavior.
- **Blended confidence = 0 for zero-score families**: Correct by definition — no evidence, no confidence to blend.
- **`action_priority_rank` for zero-score families**: All receive the same dense rank (lowest), which is correct since they are indistinguishable by the ranking criteria. `family_key` stable tie-break applies within that group.
- **Escalation on single-chain portfolio**: A single chain with any severity will have `normalized_score_100 = 100.0` and will therefore trigger the "high normalized score" escalation rule. This is mathematically correct — it is the portfolio's most impactful issue — but operators should be aware that a single-chain portfolio always escalates by the score rule.
- **Recency ratio test (Test 4)**: Verified that `recency(today) / recency(208 days ago) = 1.20 / 0.60 = 2.0` exactly. All other factors are held constant, confirming the formula's isolability.

---

## Ready for Step 11?

**Yes.**

- `build_onion_scores()` returns `(onion_scores_df, onion_portfolio_summary)` — clean handoff.
- `onion_scores_df` provides one row per `family_key` with all 22 output columns populated.
- `total_onion_score`, `normalized_score_100`, and theme buckets are available as numeric inputs for the narrative engine.
- `top_layer_code`, `top_layer_name`, `top_layer_score` identify the dominant cause for each family.
- `escalation_flag` and `escalation_reason` are ready for narrative framing and export prioritization.
- `action_priority_rank` gives the export engine a deterministic sort order.
- `blended_confidence` gives the narrative engine a reliability signal for hedging language.
- No AI inference, no narrative text, no blame language in Step 10 outputs.
- Inputs are not mutated.

### Key inputs Step 11 (Narrative Engine) will consume:

- `onion_scores_df.normalized_score_100` — overall impact magnitude
- `onion_scores_df.top_layer_code` + `top_layer_score` — primary story for each chain
- `onion_scores_df.escalation_flag` + `escalation_reason` — urgency framing
- `onion_scores_df.blended_confidence` — hedging signal ("high confidence" vs "inferred")
- `onion_layers_df` (from Step 09) — layer-level `trigger_metrics` for per-layer detail sentences

---

## Next Blockers

- **Step 11** — Narrative Engine. Consumes `onion_scores_df` + `onion_layers_df` to produce per-chain narrative summaries. No blockers from Step 10.
- **Step 12** — Export Engine. Will write `onion_scores_df` to `output/chain_onion/ONION_SCORES.csv`. Column contract fully defined in `onion_scoring._OUTPUT_COLS`.
- **Step 14** — Validation Harness. Assertable invariants from Step 10: `normalized_score_100 ∈ [0, 100]`, `blended_confidence ∈ [0, 100]`, `action_priority_rank ≥ 1` for scored families, `top_10_family_keys` length ≤ 10.
