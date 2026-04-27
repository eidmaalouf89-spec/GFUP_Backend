# STEP08_VALIDATION.md
## Step 08 — Chain Metrics Engine: Validation Report

**Date:** 2026-04-27
**Status:** COMPLETE — 50 passed, 1 skipped, 0 failed (4.16s)

---

## What Was Analyzed

| File | Purpose |
|------|---------|
| `docs/CHAIN_ONION_MASTER_STRATEGY.md` | Architecture, protected files, HYBRID execution mode |
| `docs/CHAIN_ONION_STEP_TRACKER.md` | Step status registry |
| `docs/STEP02_CHAIN_CONTRACT.md` | chain_register schema (Section B), chain_events schema (Section D), actor_type vocabulary (Section F) |
| `docs/STEP03_5_BACKLOG_SEGMENTATION.md` | Portfolio bucket constants, operational_relevance_score formula |
| `docs/STEP04_VALIDATION.md` | ops_df=32,099 rows, debug_df=407,288 rows, data_date column confirmed |
| `docs/STEP05_VALIDATION.md` | chain_register / chain_versions column contracts — `total_versions_requiring_cycle` confirmed |
| `docs/STEP06_VALIDATION.md` | chain_events column contract — actor_type vocabulary (PRIMARY_CONSULTANT / SECONDARY_CONSULTANT / MOEX / SAS), `delay_contribution_days` confirmed |
| `docs/STEP07_VALIDATION.md` | classifier output columns — `current_state`, `portfolio_bucket`, `stale_days`, `last_real_activity_date`, `operational_relevance_score` |
| `src/chain_onion/family_grouper.py` | `_CHAIN_REGISTER_COLS`, `_CHAIN_VERSIONS_COLS` — exact column names; `total_versions_requiring_cycle` confirmed |
| `src/chain_onion/chain_builder.py` | `_CHAIN_EVENTS_COLS`, actor_type mapping, `delay_contribution_days`, `is_blocking` |
| `src/chain_onion/chain_classifier.py` | New columns added in Step 07; `ARCHIVED_TERMINAL_STATES` |

---

## What Was Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `src/chain_onion/chain_metrics.py` | **Created** | Chain Metrics Engine — `build_chain_metrics()` + helpers (~340 lines) |
| `tests/test_chain_metrics.py` | **Created** | 50 synthetic unit tests across 8 test classes + 1 skipped live test |
| `docs/STEP08_VALIDATION.md` | **Created** | This file |

**Not modified:** `src/flat_ged/*`, existing pipeline stages, UI files, Steps 04–07 code, any onion modules, `CHAIN_ONION_MASTER_STRATEGY.md`, `src/query_library.py`.

---

## Metric Definitions

### `build_chain_metrics(chain_register_df, chain_versions_df, chain_events_df, ops_df) -> (chain_metrics_df, portfolio_metrics_dict)`

Returns one row per `family_key` in `chain_metrics_df` plus a global `portfolio_metrics_dict`.

---

### Lifecycle Time

| Column | Formula |
|--------|---------|
| `open_days` | `data_date - first_submission_date` (days). Null if `first_submission_date` is null. Always ≥ 0. |
| `stale_days` | Inherited from classifier (`data_date - last_real_activity_date`). Null if no activity dates. |
| `active_days` | `last_real_activity_date - first_submission_date` (days). Null if either date is missing. Always ≥ 0. |

### Volumes

| Column | Rule |
|--------|------|
| `total_events` | Count of `chain_events_df` rows for this `family_key`. |
| `total_blocking_events` | Count of `chain_events_df` rows where `is_blocking == True` for this family. |
| `rejection_cycles` | `total_versions_requiring_cycle` from `chain_register_df`. This equals the count of distinct version_keys where `requires_new_cycle = True` in ops_df, as computed by Step 05 `family_grouper.py`. A version is counted as a rejection cycle when it required the submitter to produce a corrected new revision. |

### Wait Day Allocation

| Column | Rule |
|--------|------|
| `primary_wait_days` | Sum of `delay_contribution_days > 0` for events where `actor_type == "PRIMARY_CONSULTANT"` |
| `secondary_wait_days` | Sum of `delay_contribution_days > 0` for events where `actor_type == "SECONDARY_CONSULTANT"` |
| `moex_wait_days` | Sum of `delay_contribution_days > 0` for events where `actor_type == "MOEX"` |
| `sas_wait_days` | Sum of `delay_contribution_days > 0` for events where `actor_type == "SAS"` |

**Zero-delay rows are excluded.** No durations are invented — if no `delay_contribution_days > 0` exists for an actor type, the bucket is 0.

### Delay Metrics

| Column | Formula |
|--------|---------|
| `cumulative_delay_days` | Sum of all `delay_contribution_days > 0` across all events for this family |
| `avg_delay_per_event` | `cumulative_delay_days / count(events with delay > 0)` |
| `max_single_event_delay` | Max of `delay_contribution_days` across positive-delay events |

### Efficiency Metrics

| Column | Formula |
|--------|---------|
| `churn_ratio` | `rejection_cycles / max(total_versions, 1)`, capped at 10.0 |
| `response_velocity_90d` | `count(events with event_date >= data_date - 90 days) / 90` |

### Pressure Index — Final Formula (exact)

```
base = operational_relevance_score

+15 if portfolio_bucket == "LIVE_OPERATIONAL" AND current_blocking_actor_count >= 1
+10 if 15 <= stale_days <= 45
+10 if rejection_cycles >= 2
+10 if current_state in {"WAITING_CORRECTED_INDICE", "CHRONIC_REF_CHAIN"}
-20 if portfolio_bucket == "ARCHIVED_HISTORICAL"
-10 if portfolio_bucket == "LEGACY_BACKLOG"

result = clamp(base, 0, 100)
```

All conditions are evaluated independently and additively. Clamping is applied last.

### Boolean Flags

| Column | Rule |
|--------|------|
| `is_live_operational` | `portfolio_bucket == "LIVE_OPERATIONAL"` |
| `is_legacy_backlog` | `portfolio_bucket == "LEGACY_BACKLOG"` |
| `is_archived` | `portfolio_bucket == "ARCHIVED_HISTORICAL"` |

---

### Portfolio Metrics

| Key | Formula |
|-----|---------|
| `total_chains` | `len(chain_metrics_df)` |
| `live_chains` | Count where `is_live_operational == True` |
| `legacy_chains` | Count where `is_legacy_backlog == True` |
| `archived_chains` | Count where `is_archived == True` |
| `dormant_ghost_ratio` | `legacy_chains / max(live_chains + legacy_chains, 1)` — **strategic KPI** |
| `avg_pressure_live` | Mean `pressure_index` for live chains |
| `avg_versions_per_chain` | Mean `total_versions` across all chains |
| `avg_events_per_chain` | Mean `total_events` across all chains |
| `live_waiting_moex` | Count live chains with `current_state == "OPEN_WAITING_MOEX"` |
| `live_waiting_primary` | Count live chains with `current_state == "OPEN_WAITING_PRIMARY_CONSULTANT"` |
| `live_waiting_secondary` | Count live chains with `current_state == "OPEN_WAITING_SECONDARY_CONSULTANT"` |
| `live_waiting_mixed` | Count live chains with `current_state == "OPEN_WAITING_MIXED_CONSULTANTS"` |
| `live_waiting_corrected` | Count live chains with `current_state == "WAITING_CORRECTED_INDICE"` |
| `live_chronic` | Count live chains with `current_state == "CHRONIC_REF_CHAIN"` |
| `total_cumulative_delay_days` | Sum of `cumulative_delay_days` across all chains |
| `avg_stale_live` | Mean `stale_days` for live chains (null excluded) |
| `p90_pressure_live` | 90th percentile `pressure_index` for live chains |
| `top_10_family_keys_by_pressure` | List of top 10 `family_key` values sorted by `pressure_index` descending |

---

## Live Portfolio KPIs

**Skipped — Claude Code / Codex full-run required (32k ops / 407k debug rows).**

Run manually:
```
pytest tests/test_chain_metrics.py -k TestLiveDatasetRun -s
```

Expected output format defined in `TestLiveDatasetRun.test_live_run` — reports:
- total chains / bucket split
- dormant_ghost_ratio
- avg pressure live
- live backlog breakdown
- total_cumulative_delay_days, avg_stale_live, p90_pressure_live
- top 20 chains by pressure_index

---

## Top Risk Chains

Synthetic highest-pressure example (from Class 3 test):

| family_key | current_state | portfolio_bucket | pressure_index | stale_days | rejection_cycles |
|-----------|---------------|-----------------|:--------------:|:----------:|:----------------:|
| 100 | WAITING_CORRECTED_INDICE | LIVE_OPERATIONAL | 100 | 20 | 2 |

Formula trace: `60 (base) +15 (live+blocking) +10 (stale 15–45) +10 (cycles≥2) +10 (WAITING_CORRECTED) = 105 → clamped to 100`

---

## Test Results

| # | Test Class / Name | Result | What it checks |
|---|-------------------|--------|----------------|
| 1a | `TestBasicMetrics::test_one_row_per_family` | PASSED | Single family → 1 row output |
| 1b | `TestBasicMetrics::test_total_events` | PASSED | 3 events → total_events = 3 |
| 1c | `TestBasicMetrics::test_total_blocking_events` | PASSED | 2 blocking events correctly counted |
| 1d | `TestBasicMetrics::test_rejection_cycles_from_register` | PASSED | rejection_cycles uses total_versions_requiring_cycle |
| 1e | `TestBasicMetrics::test_cumulative_delay_days` | PASSED | Only positive delays summed (5+10=15) |
| 1f | `TestBasicMetrics::test_max_single_event_delay` | PASSED | Max single delay = 10 |
| 1g | `TestBasicMetrics::test_required_columns_present` | PASSED | All 28 required columns present |
| 1h | `TestBasicMetrics::test_open_days_positive` | PASSED | open_days > 0 |
| 1i | `TestBasicMetrics::test_active_days_positive` | PASSED | active_days > 0 |
| 1j | `TestBasicMetrics::test_churn_ratio_bounded` | PASSED | churn_ratio in [0, 10] |
| 2a | `TestClosedChainMetrics::test_is_archived_true` | PASSED | ARCHIVED_HISTORICAL → is_archived = True |
| 2b | `TestClosedChainMetrics::test_is_live_false` | PASSED | ARCHIVED → is_live_operational = False |
| 2c | `TestClosedChainMetrics::test_is_legacy_false` | PASSED | ARCHIVED → is_legacy_backlog = False |
| 2d | `TestClosedChainMetrics::test_pressure_low` | PASSED | ARCHIVED, base=0 → pressure = 0 |
| 2e | `TestClosedChainMetrics::test_rejection_cycles_zero` | PASSED | closed chain → 0 rejection cycles |
| 2f | `TestClosedChainMetrics::test_total_blocking_events_zero` | PASSED | no blocking events |
| 3a | `TestLiveBlockedChain::test_pressure_high` | PASSED | Live+blocked+stale+cycle+WAITING_CORRECTED → 100 |
| 3b | `TestLiveBlockedChain::test_is_live_true` | PASSED | LIVE_OPERATIONAL → is_live = True |
| 3c | `TestLiveBlockedChain::test_total_blocking_events` | PASSED | 2 blocking events |
| 3d | `TestLiveBlockedChain::test_cumulative_delay` | PASSED | 8+12 = 20 delay days |
| 3e | `TestLiveBlockedChain::test_rejection_cycles` | PASSED | 2 cycles from register |
| 4a | `TestChurnChain::test_high_rejection_cycles` | PASSED | 5 rejection cycles |
| 4b | `TestChurnChain::test_churn_ratio_is_one` | PASSED | 5/5 = 1.0 |
| 4c | `TestChurnChain::test_churn_ratio_capped` | PASSED | Cap at CHURN_RATIO_CAP=10.0 |
| 4d | `TestChurnChain::test_churn_ratio_zero_when_no_rejections` | PASSED | 0 cycles → churn = 0.0 |
| 5a | `TestWaitAllocation::test_primary_wait_days` | PASSED | 10+5 = 15 primary wait |
| 5b | `TestWaitAllocation::test_secondary_wait_days` | PASSED | 7 secondary wait |
| 5c | `TestWaitAllocation::test_moex_wait_days` | PASSED | 20 MOEX wait |
| 5d | `TestWaitAllocation::test_sas_wait_days` | PASSED | 3 SAS wait (zero-delay excluded) |
| 5e | `TestWaitAllocation::test_zero_delay_not_counted` | PASSED | delay=0 rows not summed |
| 5f | `TestWaitAllocation::test_all_four_buckets_present` | PASSED | All 4 wait day columns present |
| 6a | `TestPressureBounds::test_live_blocked_high_score_capped` | PASSED | Max score → 100 |
| 6b | `TestPressureBounds::test_archived_score_zero` | PASSED | Archived → 0 |
| 6c | `TestPressureBounds::test_legacy_score_non_negative` | PASSED | Legacy → ≥ 0 |
| 6d | `TestPressureBounds::test_all_scenarios_in_bounds` | PASSED | All 4 scenarios in [0, 100] |
| 7a | `TestPortfolioKPIs::test_total_chains` | PASSED | 7-family portfolio → total=7 |
| 7b | `TestPortfolioKPIs::test_live_chains` | PASSED | 5 live chains |
| 7c | `TestPortfolioKPIs::test_legacy_chains` | PASSED | 1 legacy chain |
| 7d | `TestPortfolioKPIs::test_archived_chains` | PASSED | 1 archived chain |
| 7e | `TestPortfolioKPIs::test_dormant_ghost_ratio` | PASSED | 1/6 ≈ 0.1667 |
| 7f | `TestPortfolioKPIs::test_all_required_portfolio_keys_present` | PASSED | All 19 portfolio keys present |
| 7g | `TestPortfolioKPIs::test_live_waiting_moex` | PASSED | 1 chain OPEN_WAITING_MOEX |
| 7h | `TestPortfolioKPIs::test_live_waiting_primary` | PASSED | 1 chain OPEN_WAITING_PRIMARY_CONSULTANT |
| 7i | `TestPortfolioKPIs::test_live_waiting_corrected` | PASSED | 1 chain WAITING_CORRECTED_INDICE |
| 7j | `TestPortfolioKPIs::test_live_chronic` | PASSED | 1 chain CHRONIC_REF_CHAIN |
| 7k | `TestPortfolioKPIs::test_top_10_is_list` | PASSED | top_10 is a list |
| 7l | `TestPortfolioKPIs::test_top_10_max_length` | PASSED | len ≤ 10 |
| 7m | `TestPortfolioKPIs::test_avg_pressure_live_positive` | PASSED | avg pressure > 0 for live chains |
| 7n | `TestPortfolioKPIs::test_p90_pressure_live_in_range` | PASSED | p90 in [0, 100] |
| 7o | `TestPortfolioKPIs::test_total_cumulative_delay_days_non_negative` | PASSED | Delay sum ≥ 0 |
| 8  | `TestLiveDatasetRun::test_live_run` | SKIPPED | Full 32k/407k run — Claude Code / Codex only |

**Suite result: 50 passed, 1 skipped, 0 failed — 4.16s**

---

## Warnings / Anomalies

- **`total_events` not in chain_register_df**: The Step 05 `_CHAIN_REGISTER_COLS` does not include `total_events`. Step 08 recomputes it from `chain_events_df` groupby — this is correct per spec ("Count from chain_events_df").
- **`rejection_cycles` uses `total_versions_requiring_cycle`**: This is the Step 05 column that counts versions where `requires_new_cycle = True`. The spec also mentions "REF / WAITING_CORRECTED lineage" as signals, but `requires_new_cycle_flag` is the single authoritative source for version-level rejection in Steps 02–07. Using this avoids re-parsing events and is consistent with how `chain_classifier.py` counts rejected versions.
- **`response_velocity_90d` requires `event_date` in `chain_events_df`**: If `event_date` is absent or `data_date` is null, velocity defaults to 0.0 with a WARNING log.
- **`avg_delay_per_event` is 0.0 when all delays are 0**: Only positive delay contributions are included. A chain with no delay rows gets `avg_delay_per_event = 0.0`, `cumulative_delay_days = 0`, `max_single_event_delay = 0`.
- **`active_days` can be null**: When `last_real_activity_date` or `first_submission_date` is null, `active_days` is null (no invented dates).
- **`open_days` uses data_date from ops_df**: If `data_date` is unavailable, `open_days` is null for all rows. This matches Step 07 behavior.
- **`dormant_ghost_ratio` denominator protection**: `max(open_chains, 1)` prevents division by zero when all chains are archived.

---

## Key Design Decisions

1. **`rejection_cycles` sourced from `chain_register.total_versions_requiring_cycle`** (not re-derived from events). This field is already computed in Step 05 from `requires_new_cycle = True` in ops_df. Using it avoids redundant computation and keeps the metric consistent with the classifier's own rejection logic.
2. **Wait day allocation uses `delay_contribution_days > 0` filter** — strictly positive delays only. Zero-contribution rows (blocking but no delay quantified) are not counted. No durations are invented.
3. **Pressure index is fully deterministic** — all inputs are columns in `chain_metrics_df`; no external lookups. Formula is documented in a single place in `chain_metrics.py`.
4. **`_aggregate_events` is vectorized** — uses pandas groupby for all event aggregations; no per-row Python loop over events.
5. **Portfolio metrics are derived entirely from `chain_metrics_df`** — not from raw inputs. This ensures portfolio KPIs are consistent with per-chain outputs.
6. **No new chain state codes** — `build_chain_metrics()` reads `current_state` from inputs; it does not classify or reclassify chains.
7. **No onion attribution** — wait day buckets (primary/secondary/moex/sas) are pure delay sums, not responsibility scores. Blame attribution belongs to Step 09 (Onion Layer Engine).

---

## Ready for Step 09?

**Yes.**

- `chain_metrics_df` provides one row per `family_key` with all required numeric columns.
- `pressure_index` is bounded [0, 100] and deterministic.
- `dormant_ghost_ratio` is computed as the strategic portfolio KPI.
- Live operational backlog is measurable by state bucket.
- No classifier logic is present in this module.
- Inputs are not mutated.
- All delay columns trace directly to `chain_events.delay_contribution_days`.

### Key inputs Step 09 (Onion Layer Engine) will consume:

- `chain_metrics_df.cumulative_delay_days` — total delay per chain for onion severity context
- `chain_metrics_df.rejection_cycles` — for chronic/churn layer scoring
- `chain_metrics_df.primary_wait_days`, `secondary_wait_days`, `moex_wait_days`, `sas_wait_days` — actor delay breakdown for onion responsibility layers
- `chain_metrics_df.pressure_index` — urgency signal for onion prioritization
- `chain_events_df` — event-level detail for per-instance forensic layers (Steps 09–11 consume directly)

---

## Next Blockers (for downstream steps)

- **Step 09** — Onion Layer Engine. Consumes `chain_metrics_df` + `chain_events_df` for per-instance forensic scoring. No blockers from Step 08.
- **Step 12** — Export Engine. Will export `chain_metrics_df` to `output/chain_onion/CHAIN_METRICS.csv`. Column contract fully defined here.
- **Step 13** — Query hooks. `pressure_index`, `dormant_ghost_ratio`, and `live_waiting_*` counts available for dashboard default filters.
- **Step 14** — Validation harness. `pressure_index in [0, 100]` and `churn_ratio <= 10` are assertable invariants.
