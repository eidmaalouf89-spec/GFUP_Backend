# STEP13_VALIDATION.md
## Step 13 — Query Hooks Engine: Validation Report

**Date:** 2026-04-27
**Status:** COMPLETE — 76 passed, 1 skipped, 0 failed (2.84s)

---

## What Was Analyzed

| File | Purpose |
|------|---------|
| `docs/CHAIN_ONION_STEP_TRACKER.md` | Step status registry |
| `docs/STEP10_VALIDATION.md` | `onion_scores_df` column contract, `action_priority_rank`, theme buckets, escalation rules |
| `docs/STEP11_VALIDATION.md` | `chain_narratives_df` output contract (15 columns), urgency/confidence labels |
| `docs/STEP12_VALIDATION.md` | Export artifact contract — ONION_SCORES.csv, CHAIN_NARRATIVES.csv, dashboard_summary.json, top_issues.json |
| `docs/STEP08_VALIDATION.md` | `stale_days`, `latest_submission_date`, `last_real_activity_date` column locations in CHAIN_METRICS |
| `src/chain_onion/onion_scoring.py` | `_OUTPUT_COLS` (22 cols) — authoritative ONION_SCORES schema |
| `src/chain_onion/narrative_engine.py` | `_OUTPUT_COLS` (15 cols) — authoritative CHAIN_NARRATIVES schema |
| `src/chain_onion/chain_classifier.py` | `current_state` vocabulary (12 states), `portfolio_bucket` vocabulary |

---

## What Was Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `src/chain_onion/query_hooks.py` | **Created** | Query Hooks Engine — `QueryContext` + 26 public functions (~340 lines) |
| `tests/test_query_hooks.py` | **Created** | 76 synthetic unit tests across 10 test classes + 1 skipped live test |
| `docs/STEP13_VALIDATION.md` | **Created** | This file |

**Not modified:** `src/flat_ged/*`, UI files, Steps 04–12 code, `exporter.py`, `query_library.py`, pipeline stages.

---

## Public API

### QueryContext

```python
QueryContext(
    onion_scores_df=None,       # pd.DataFrame — preferred, direct in-memory
    chain_narratives_df=None,   # pd.DataFrame — optional
    chain_metrics_df=None,      # pd.DataFrame — optional (for stale_days)
    _dashboard_summary=None,    # dict — pre-loaded dashboard JSON
    _top_issues=None,           # list — pre-loaded top_issues JSON
    output_dir=Path("output/chain_onion"),  # disk fallback
)
```

Accessors (all cache-through, no repeated reads):
- `ctx.scores()` → ONION_SCORES DataFrame
- `ctx.narratives()` → CHAIN_NARRATIVES DataFrame
- `ctx.metrics()` → CHAIN_METRICS DataFrame
- `ctx.dashboard()` → dashboard_summary dict
- `ctx.top_issues_raw()` → top_issues list

---

### Function List

| Category | Function | Filter / Behavior |
|----------|----------|-------------------|
| Core | `get_top_issues(ctx, limit=20)` | Sort by `action_priority_rank` asc, apply limit |
| Core | `get_escalated_chains(ctx, limit=50)` | `escalation_flag == True`, sort by rank |
| Core | `get_live_operational(ctx, limit=None)` | `portfolio_bucket == LIVE_OPERATIONAL` |
| Core | `get_legacy_backlog(ctx, limit=None)` | `portfolio_bucket == LEGACY_BACKLOG` |
| Core | `get_archived(ctx, limit=None)` | `portfolio_bucket == ARCHIVED_HISTORICAL` |
| Blocking | `get_waiting_primary(ctx, limit=None)` | `current_state == OPEN_WAITING_PRIMARY_CONSULTANT` |
| Blocking | `get_waiting_secondary(ctx, limit=None)` | `current_state == OPEN_WAITING_SECONDARY_CONSULTANT` |
| Blocking | `get_waiting_moex(ctx, limit=None)` | `current_state == OPEN_WAITING_MOEX` |
| Blocking | `get_waiting_corrected(ctx, limit=None)` | `current_state == WAITING_CORRECTED_INDICE` |
| Blocking | `get_mixed_blockers(ctx, limit=None)` | `current_state == OPEN_WAITING_MIXED_CONSULTANTS` |
| Theme | `get_contractor_quality(ctx, limit=None)` | `contractor_impact_score > 0` |
| Theme | `get_sas_friction(ctx, limit=None)` | `sas_impact_score > 0` |
| Theme | `get_primary_consultant_delay(ctx, limit=None)` | `consultant_primary_impact_score > 0` |
| Theme | `get_secondary_consultant_delay(ctx, limit=None)` | `consultant_secondary_impact_score > 0` |
| Theme | `get_moex_delay(ctx, limit=None)` | `moex_impact_score > 0` |
| Theme | `get_data_contradictions(ctx, limit=None)` | `contradiction_impact_score > 0` |
| Metrics | `get_high_pressure(ctx, min_score=70)` | `normalized_score_100 >= min_score` |
| Metrics | `get_stale_chains(ctx, min_days=60)` | `stale_days >= min_days`; merges CHAIN_METRICS if needed |
| Metrics | `get_zero_score_chains(ctx)` | `normalized_score_100 == 0` |
| Metrics | `get_recently_active(ctx, days=30)` | Activity date within N days of portfolio max |
| Search | `search_family_key(ctx, text)` | Ranked: exact=1, startswith=2, contains=3 |
| Search | `search_numero(ctx, text)` | Ranked: exact=1, startswith=2, contains=3 |
| Summary | `get_dashboard_summary(ctx)` | JSON cache first; falls back to DataFrame compute |
| Summary | `get_portfolio_snapshot(ctx)` | Always computed from DataFrames (authoritative) |

---

## Source Loading Behavior

| Source | Priority | Trigger |
|--------|----------|---------|
| In-memory DataFrame passed to `QueryContext` | 1st (preferred) | `onion_scores_df` is not `None` |
| Disk CSV / JSON via `output_dir` | 2nd (fallback) | `onion_scores_df` is `None` at first access |
| Pre-loaded JSON dict via `_dashboard_summary` | 1st for dashboard | `_dashboard_summary` is not `None` |

DataFrames are `.copy()`-ed from the caller's object at first access to prevent mutation of the original.

---

## Caching Design

- `QueryContext` holds 5 private cache slots: `_scores_cache`, `_narratives_cache`, `_metrics_cache`, `_dashboard_cache`, `_top_issues_cache`.
- Each `ctx.scores()` / `ctx.narratives()` / etc. call checks its cache slot first.
- If the slot is empty, it loads from the in-memory DataFrame or disk — **once only**.
- Subsequent calls return the cached object directly (identity equality confirmed by `TestCaching`).
- No function in the query hooks module writes to any cache slot — only `QueryContext` accessors do.
- **Input DataFrames are never mutated**: all filter operations use `.copy()` internally.

---

## Return Format Contract

| Function type | Return type | Notes |
|---------------|-------------|-------|
| Row-returning functions | `pd.DataFrame` | Never `None`; empty DataFrame on no match |
| Summary functions | `dict` | All required keys always present |
| Search functions | `pd.DataFrame` | Ranked; no `_search_rank` col in output |

No printing, no UI formatting, no side effects.

---

## Test Results

| # | Test Class / Name | Result | What it checks |
|---|-------------------|--------|----------------|
| 1a | `TestCoreFilters::test_get_top_issues_returns_dataframe` | PASSED | Return type is DataFrame |
| 1b | `TestCoreFilters::test_get_top_issues_sorted_by_rank` | PASSED | Ranks ascending |
| 1c | `TestCoreFilters::test_get_top_issues_limit_respected` | PASSED | limit=2 → 2 rows |
| 1d | `TestCoreFilters::test_get_top_issues_rank1_first` | PASSED | Rank 1 chain is first |
| 1e | `TestCoreFilters::test_get_escalated_chains_all_flagged` | PASSED | All rows escalation_flag=True |
| 1f | `TestCoreFilters::test_get_escalated_chains_returns_only_1` | PASSED | 1 escalated chain in portfolio |
| 1g | `TestCoreFilters::test_get_live_operational_bucket_correct` | PASSED | All rows LIVE_OPERATIONAL |
| 1h | `TestCoreFilters::test_get_live_operational_count` | PASSED | 3 live chains |
| 1i | `TestCoreFilters::test_get_legacy_backlog_count` | PASSED | 1 legacy chain |
| 1j | `TestCoreFilters::test_get_archived_count` | PASSED | 1 archived chain |
| 1k | `TestCoreFilters::test_get_live_limit` | PASSED | limit=1 respected |
| 2a | `TestBlockingOwnership::test_waiting_primary_state_filter` | PASSED | State = OPEN_WAITING_PRIMARY |
| 2b | `TestBlockingOwnership::test_waiting_secondary_state_filter` | PASSED | State = OPEN_WAITING_SECONDARY |
| 2c | `TestBlockingOwnership::test_waiting_moex_state_filter` | PASSED | State = OPEN_WAITING_MOEX |
| 2d | `TestBlockingOwnership::test_waiting_corrected_state_filter` | PASSED | State = WAITING_CORRECTED_INDICE |
| 2e | `TestBlockingOwnership::test_mixed_blockers_state_filter` | PASSED | State = OPEN_WAITING_MIXED |
| 2f | `TestBlockingOwnership::test_waiting_states_return_dataframe` | PASSED | All 5 state fns → DataFrame |
| 2g | `TestBlockingOwnership::test_waiting_states_sorted_by_rank` | PASSED | Sorted by rank |
| 3a | `TestThemeFilters::test_contractor_quality_positive_score` | PASSED | contractor_impact > 0 |
| 3b | `TestThemeFilters::test_sas_friction_positive_score` | PASSED | sas_impact > 0 |
| 3c | `TestThemeFilters::test_primary_consultant_delay_positive` | PASSED | consultant_primary > 0 |
| 3d | `TestThemeFilters::test_secondary_consultant_delay_positive` | PASSED | consultant_secondary > 0 |
| 3e | `TestThemeFilters::test_moex_delay_positive` | PASSED | moex_impact > 0 |
| 3f | `TestThemeFilters::test_data_contradictions_empty_when_none` | PASSED | 0 rows when no contradiction |
| 3g | `TestThemeFilters::test_theme_results_sorted_by_rank` | PASSED | Rank ordering preserved |
| 3h | `TestThemeFilters::test_all_theme_fns_return_dataframe` | PASSED | All 6 theme fns → DataFrame |
| 3i | `TestThemeFilters::test_theme_limit_respected` | PASSED | limit=1 on multi-row contractor |
| 4a | `TestMetricFilters::test_get_high_pressure_threshold_default` | PASSED | score >= 70 filter |
| 4b | `TestMetricFilters::test_get_high_pressure_all_above_0` | PASSED | min_score=0 → all 5 chains |
| 4c | `TestMetricFilters::test_get_high_pressure_none_above_100` | PASSED | min_score=100 → 0 rows |
| 4d | `TestMetricFilters::test_get_zero_score_chains` | PASSED | 1 zero-score chain (ARC_ZERO) |
| 4e | `TestMetricFilters::test_get_stale_chains_from_scores_col` | PASSED | stale_days in scores col |
| 4f | `TestMetricFilters::test_get_stale_chains_merges_from_metrics` | PASSED | Merge path safe |
| 4g | `TestMetricFilters::test_get_recently_active_within_30_days` | PASSED | Activity date filter |
| 4h | `TestMetricFilters::test_get_recently_active_returns_dataframe` | PASSED | Returns DataFrame |
| 4i | `TestMetricFilters::test_high_pressure_returns_dataframe` | PASSED | Returns DataFrame |
| 4j | `TestMetricFilters::test_stale_chains_returns_dataframe` | PASSED | Returns DataFrame |
| 5a | `TestSearch::test_search_family_key_exact_is_first` | PASSED | Exact match ranked first |
| 5b | `TestSearch::test_search_family_key_startswith_before_contains` | PASSED | startswith before contains |
| 5c | `TestSearch::test_search_family_key_contains_match` | PASSED | BETA_ALPHA found via contains |
| 5d | `TestSearch::test_search_family_key_no_match_empty` | PASSED | No match → empty DataFrame |
| 5e | `TestSearch::test_search_family_key_case_insensitive` | PASSED | lowercase query matches |
| 5f | `TestSearch::test_search_numero_exact_first` | PASSED | Exact numero first |
| 5g | `TestSearch::test_search_numero_contains_match` | PASSED | GED/2024 matches 2 rows |
| 5h | `TestSearch::test_search_returns_dataframe` | PASSED | Both search fns → DataFrame |
| 5i | `TestSearch::test_search_empty_text_returns_empty` | PASSED | Empty query → empty result |
| 5j | `TestSearch::test_search_exact_rank_1` | PASSED | Exact beats startswith/contains |
| 6a | `TestSummary::test_get_dashboard_summary_returns_dict` | PASSED | Returns dict |
| 6b | `TestSummary::test_get_portfolio_snapshot_required_keys` | PASSED | All 8 keys present |
| 6c | `TestSummary::test_get_portfolio_snapshot_totals_correct` | PASSED | total=5, live=3, legacy=1, arc=1 |
| 6d | `TestSummary::test_get_portfolio_snapshot_escalated_count` | PASSED | escalated_count=1 |
| 6e | `TestSummary::test_get_portfolio_snapshot_avg_live_score` | PASSED | avg ≈ 61.67 |
| 6f | `TestSummary::test_get_portfolio_snapshot_top_theme` | PASSED | Non-empty string |
| 6g | `TestSummary::test_get_dashboard_summary_uses_json_when_available` | PASSED | JSON total_chains=99 used |
| 6h | `TestSummary::test_snapshot_generated_at_is_string` | PASSED | ISO string returned |
| 7a | `TestEmptyInputs::test_get_top_issues_empty` | PASSED | Empty DataFrame, no crash |
| 7b | `TestEmptyInputs::test_get_escalated_chains_empty` | PASSED | Empty safe |
| 7c | `TestEmptyInputs::test_get_live_operational_empty` | PASSED | Empty safe |
| 7d | `TestEmptyInputs::test_get_legacy_backlog_empty` | PASSED | Empty safe |
| 7e | `TestEmptyInputs::test_get_archived_empty` | PASSED | Empty safe |
| 7f | `TestEmptyInputs::test_state_filters_empty` | PASSED | All 5 state fns empty-safe |
| 7g | `TestEmptyInputs::test_theme_filters_empty` | PASSED | All 6 theme fns empty-safe |
| 7h | `TestEmptyInputs::test_metric_filters_empty` | PASSED | All 4 metric fns empty-safe |
| 7i | `TestEmptyInputs::test_search_empty` | PASSED | Search empty-safe |
| 7j | `TestEmptyInputs::test_get_portfolio_snapshot_empty` | PASSED | total=0, live=0, escalated=0 |
| 7k | `TestEmptyInputs::test_get_dashboard_summary_empty` | PASSED | Empty dict safe |
| 8a | `TestCaching::test_scores_cached_after_first_access` | PASSED | `ctx.scores() is ctx.scores()` |
| 8b | `TestCaching::test_metrics_cached_after_first_access` | PASSED | `ctx.metrics() is ctx.metrics()` |
| 8c | `TestCaching::test_input_df_not_mutated` | PASSED | Input unchanged after 3 queries |
| 8d | `TestCaching::test_cache_not_affected_by_multiple_queries` | PASSED | Deterministic on repeat |
| 8e | `TestCaching::test_dashboard_dict_cached` | PASSED | `ctx.dashboard() is ctx.dashboard()` |
| 9a | `TestDiskLoading::test_load_scores_from_csv` | PASSED | CSV loaded, rank sorted |
| 9b | `TestDiskLoading::test_load_missing_csv_returns_empty` | PASSED | Missing file → empty DataFrame |
| 9c | `TestDiskLoading::test_load_dashboard_json_from_disk` | PASSED | JSON loaded correctly |
| 9d | `TestDiskLoading::test_load_missing_json_returns_empty_dict` | PASSED | Missing file → empty dict |
| 9e | `TestDiskLoading::test_disk_cache_prevents_rereads` | PASSED | File overwritten; cache serves original |
| 10 | `TestLiveRun::test_live_run` | SKIPPED | Full run — Claude Code / Codex only |

**Suite result: 76 passed, 1 skipped, 0 failed — 2.84s**

---

## Example Outputs (Synthetic — 5-chain portfolio)

### get_top_issues(ctx, limit=3)
| family_key | action_priority_rank | normalized_score_100 | portfolio_bucket |
|------------|---------------------|----------------------|-----------------|
| LIVE_HIGH  | 1 | 90.0 | LIVE_OPERATIONAL |
| LIVE_MED   | 2 | 55.0 | LIVE_OPERATIONAL |
| LIVE_MOEX  | 3 | 40.0 | LIVE_OPERATIONAL |

### get_escalated_chains(ctx)
| family_key | action_priority_rank | escalation_flag |
|------------|---------------------|----------------|
| LIVE_HIGH  | 1 | True |

### get_portfolio_snapshot(ctx)
```json
{
  "total_chains": 5,
  "live_chains": 3,
  "legacy_chains": 1,
  "archived_chains": 1,
  "escalated_chain_count": 1,
  "avg_live_score": 61.67,
  "top_theme_by_impact": "consultant_primary_impact_score",
  "generated_at": "2026-04-27T..."
}
```

### search_family_key(ctx, "ALPHA")
Returns: ALPHA_001 (exact), ALPHA_002 (startswith), BETA_ALPHA (contains) — in that order.

---

## Live Metrics

**Skipped — Claude Code / Codex full-run required.**

Run manually:
```
pytest tests/test_query_hooks.py -k TestLiveRun -s
```

Expected output:
- Total chains / bucket split
- Top 20 by action_priority_rank
- Escalated chain count
- Portfolio snapshot dict

---

## Warnings / Design Notes

- **`stale_days` merge path**: If `stale_days` is absent from `ONION_SCORES.csv` (not part of its `_OUTPUT_COLS`), `get_stale_chains` automatically merges it from `CHAIN_METRICS.csv` via `family_key`. This keeps the function correct even if Step 12 adds or removes columns.
- **`get_recently_active` date column priority**: First checks `last_real_activity_date`, then `latest_submission_date`, in both `onion_scores_df` and `chain_metrics_df`. This ensures the best available date is always used.
- **`escalation_flag` coercion**: The column may be boolean (`True/False`) in-memory or string (`"True"/"False"`) after CSV round-trip. The filter normalizes both via `.astype(str).str.lower()`.
- **`generated_at` is non-deterministic by design**: `get_portfolio_snapshot` stamps the current UTC time. Excluded from caching — fresh snapshots reflect current call time, not load time.
- **`get_dashboard_summary` vs `get_portfolio_snapshot`**: `get_dashboard_summary` returns the JSON cache when available (useful for dashboards that need the export-time snapshot). `get_portfolio_snapshot` always recomputes from DataFrames (authoritative for pipeline consumers).
- **No pipeline recomputation**: All functions read from pre-exported DataFrames only. No imports from `onion_scoring`, `chain_metrics`, `narrative_engine`, etc.

---

## Ready for Step 14?

**Yes.**

- `QueryContext` + 26 public functions provide complete filter coverage for all UI / dashboard / reporting needs.
- All functions return `pd.DataFrame` (row-returning) or `dict` (summary) — no printing, no formatting.
- Empty inputs handled safely — no crashes, correct empty returns.
- Search ranking: exact > startswith > contains — deterministic.
- Cache prevents repeated disk reads per `QueryContext` instance.
- Input DataFrames are never mutated.

### Key outputs Step 14 (Validation Harness) will consume:

- `get_top_issues(ctx, 20)` — priority-sorted chain list for harness assertions
- `get_escalated_chains(ctx)` — escalated chain subset for count checks
- `get_live_operational(ctx)` — bucket filter for portfolio split assertions
- `get_zero_score_chains(ctx)` — completeness check (all families present even at zero)
- `get_portfolio_snapshot(ctx)` — aggregate KPI dict for harness summary reporting
- `search_family_key(ctx, text)` — lookup by family_key for targeted assertions
