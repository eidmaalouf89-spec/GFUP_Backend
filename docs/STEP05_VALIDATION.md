# STEP05_VALIDATION.md
## Step 05 — Family Grouper Engine: Validation Report

**Date:** 2026-04-27
**Status:** COMPLETE — 32 passed, 1 skipped, 0 failed (FutureWarning-clean)

---

## What Was Analyzed

| File | Purpose |
|------|---------|
| `docs/CHAIN_ONION_MASTER_STRATEGY.md` | Architecture, protected files, output targets |
| `docs/STEP02_CHAIN_CONTRACT.md` | FAMILY_KEY/VERSION_KEY identity model, chain_versions schema, chain_register schema, Section F primary/secondary classifier rules |
| `docs/STEP04_VALIDATION.md` | Confirmed ops_df shape (32,099 rows, 39 cols), loader return contract, identity key columns |
| `src/chain_onion/source_loader.py` | load_chain_sources() return dict keys and DataFrame column names |
| `src/query_library.py` | `_PRIMARY_APPROVER_KEYWORDS`, `_is_primary_approver()` (lines 78-81, 167-170) — used verbatim |

---

## What Was Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `src/chain_onion/family_grouper.py` | Created | Family grouper engine — two public functions, indice sort algorithm |
| `src/chain_onion/chain_models.py` | Created | Lightweight FamilySummary / VersionSummary dataclasses |
| `tests/test_family_grouper.py` | Created | 32 synthetic unit tests across 6 test classes + 1 skipped live test |
| `docs/STEP05_VALIDATION.md` | Created | This file |

**Not modified:** `src/flat_ged/*`, existing pipeline stages, UI files, Step 04 loader logic, any onion files.

---

## Grouper Behavior

### `build_chain_versions(ops_df) -> pd.DataFrame`

Aggregates `ops_df` (GED_OPERATIONS) to one row per `VERSION_KEY`. Performs a single `groupby("version_key").agg()` pass for core fields, then two additional filtered groupbys for `latest_response_date` (max non-null `response_date`) and `blocking_actor_count` (distinct `actor_clean` where `is_blocking=True`). Assigns `version_sort_order` using `_assign_version_sort_orders()`.

**Output columns (14):** `family_key`, `version_key`, `numero`, `indice`, `row_count_ops`, `first_submission_date`, `latest_submission_date`, `latest_response_date`, `has_blocking_rows`, `blocking_actor_count`, `requires_new_cycle_flag`, `completed_row_count`, `source_row_count`, `version_sort_order`.

### `build_chain_register(ops_df, chain_versions_df, debug_df, effective_df) -> pd.DataFrame`

Aggregates `chain_versions_df` to one row per `FAMILY_KEY`. Derives `latest_indice` and `latest_version_key` from the version with `max(version_sort_order)` per family. Computes `waiting_primary_flag` and `waiting_secondary_flag` by filtering `ops_df` to blocking rows in the latest version and calling `_is_primary_approver()` from `query_library`. Sets `has_debug_trace` / `has_effective_rows` by family-key membership check.

**Output columns (16):** `family_key`, `numero`, `total_versions`, `total_rows_ops`, `first_submission_date`, `latest_submission_date`, `latest_indice`, `latest_version_key`, `total_blocking_versions`, `total_versions_requiring_cycle`, `total_completed_rows`, `current_blocking_actor_count`, `waiting_primary_flag`, `waiting_secondary_flag`, `has_debug_trace`, `has_effective_rows`.

**NOT computed here (Step 07):** `current_state`, `portfolio_bucket`, `stale_days`, `operational_relevance_score`.

---

## Indice Sorting Method

**Function:** `_indice_sort_key(indice: str) -> tuple`

**Documented algorithm:**

The function returns a 3-tuple `(tier, rank_value, string_value)` that compares correctly with standard Python tuple ordering.

| Input type | Tier | Rank value | String | Example order |
|------------|------|------------|--------|---------------|
| Empty string | 3 | 0 | `""` | sorted last |
| Pure digits | 0 | `int(indice)` | raw string | `"1" < "2" < "10"` |
| Pure alpha | 1 | `len(indice)` | `upper(indice)` | `"A" < "B" < "Z" < "AA" < "AB"` |
| Mixed/other | 2 | 0 | `upper(indice)` | lexical |

**Rationale for alpha tier:** Using `(1, len, alpha_str)` causes single-letter indices (len=1) to sort before double-letter indices (len=2), and within each length tier the sort is alphabetical. This reproduces the Excel-column naming progression: A, B, ..., Z, AA, AB, ..., ZZ, AAA, ...

**`version_sort_order`:** 1-based integer assigned within each `family_key` after sorting by the tuple key above. A family with 3 versions (A, B, C) produces sort orders 1, 2, 3 respectively.

---

## Live Dataset Metrics

Live dataset test is marked `skip` per HYBRID execution model — full 32k / 407k row run is reserved for Claude Code / Codex. The test is present in `tests/test_family_grouper.py::test_live_dataset_row_counts` and can be run directly.

**Expected (based on Step 04 confirmed counts):**

| Metric | Expected |
|--------|---------|
| `ops_df` rows | 32,099 |
| `chain_versions` rows | = unique `version_key` count in ops_df |
| `chain_register` rows | = unique `family_key` count in ops_df |
| Avg versions per family | derivable from ratio above |
| Max versions in one family | depends on data |

---

## Test Results

| # | Test Class / Name | Result | What it checks |
|---|-------------------|--------|----------------|
| 1a | `TestGroupingMath::test_version_row_counts` | PASSED | 5 version rows from 8 input rows |
| 1b | `TestGroupingMath::test_version_row_count_ops` | PASSED | Per-version ops row counts correct |
| 1c | `TestGroupingMath::test_has_blocking_rows` | PASSED | has_blocking_rows per version |
| 1d | `TestGroupingMath::test_blocking_actor_count` | PASSED | Distinct blocking actors per version |
| 1e | `TestGroupingMath::test_requires_new_cycle_flag` | PASSED | any() of requires_new_cycle |
| 1f | `TestGroupingMath::test_completed_row_count` | PASSED | sum of is_completed=True |
| 1g | `TestGroupingMath::test_first_latest_submission_date` | PASSED | min/max submittal_date |
| 1h | `TestGroupingMath::test_latest_response_date` | PASSED | max non-null response_date + NaT when none |
| 1i | `TestGroupingMath::test_register_row_counts` | PASSED | 2 family rows |
| 1j | `TestGroupingMath::test_register_total_versions` | PASSED | total_versions per family |
| 1k | `TestGroupingMath::test_register_total_rows_ops` | PASSED | total_rows_ops per family |
| 1l | `TestGroupingMath::test_register_total_blocking_versions` | PASSED | count versions with blocking rows |
| 1m | `TestGroupingMath::test_register_total_versions_requiring_cycle` | PASSED | count versions needing cycle |
| 2  | `test_live_dataset_row_counts` | SKIPPED | Full 32k/407k run — Claude Code / Codex only |
| 3a | `TestKeyConsistency::test_all_version_families_in_register` | PASSED | Every cv family_key in cr |
| 3b | `TestKeyConsistency::test_register_has_no_extra_families` | PASSED | No extra families in cr |
| 4a | `TestLatestIndiceConsistency::test_latest_indice_matches_max_sort_order` | PASSED | latest_indice = max(version_sort_order) indice |
| 4b | `TestLatestIndiceConsistency::test_alpha_single_before_double` | PASSED | A<Z<AA<AB sort order |
| 4c | `TestLatestIndiceConsistency::test_numeric_before_alpha` | PASSED | "1" < "2" < "10" < "A" |
| 4d | `TestLatestIndiceConsistency::test_latest_version_key_matches_latest_indice` | PASSED | latest_version_key = family_key + "_" + latest_indice |
| 5a | `TestPrimarySecondaryFlags::test_primary_only_blocking` | PASSED | EGIS+BET SPK → primary=T, secondary=F |
| 5b | `TestPrimarySecondaryFlags::test_secondary_only_blocking` | PASSED | Non-keywords → primary=F, secondary=T |
| 5c | `TestPrimarySecondaryFlags::test_mixed_blocking` | PASSED | TERRELL + non-keyword → both=T |
| 5d | `TestPrimarySecondaryFlags::test_no_blocking_both_false` | PASSED | No blocking → both=F |
| 5e | `TestPrimarySecondaryFlags::test_flags_based_on_latest_version_only` | PASSED | Flags reflect latest version only |
| 6a | `TestNoDuplicateKeys::test_version_key_unique` | PASSED | version_key unique in chain_versions |
| 6b | `TestNoDuplicateKeys::test_family_key_unique` | PASSED | family_key unique in chain_register |
| 6c | `TestNoDuplicateKeys::test_duplicate_ops_rows_aggregated_correctly` | PASSED | Duplicate ops rows aggregate to one version row |
| E1 | `TestEdgeCases::test_empty_ops_df_returns_empty_versions` | PASSED | Empty input → empty output (no crash) |
| E2 | `TestEdgeCases::test_empty_versions_returns_empty_register` | PASSED | Empty versions → empty register |
| E3 | `TestEdgeCases::test_single_version_family_sort_order_is_1` | PASSED | Single version → sort order = 1 |
| E4 | `TestEdgeCases::test_null_response_dates_tolerated` | PASSED | Null response_date → latest_response_date = NaT |
| E5 | `TestEdgeCases::test_null_submittal_dates_tolerated` | PASSED | Null submittal_date → first/latest dates = NaT |

**Suite result:** 32 passed, 1 skipped, 0 failed — 1.75s — no FutureWarnings

---

## Warnings / Anomalies Discovered

- **`FutureWarning` (pandas 2.x downcasting):** Resolved. `waiting_primary_flag` / `waiting_secondary_flag` population now uses dict-lookup list comprehensions instead of `merge` + `fillna`, bypassing pandas' object-dtype downcast path entirely.
- **pytest 9 `== True` / `== False` rewriting:** pytest 9 rewrites `assert x == True` as `assert x is True` internally, which fails for `numpy.bool_` values (returned by `.agg("any")`). Tests use direct truthiness assertions (`assert x` / `assert not x`) throughout.
- **Null bytes in saved files:** The `Edit` tool on Windows can introduce null bytes at the end of files, causing pytest's source parser to fail with `ValueError: source code string cannot contain null bytes`. Both `family_grouper.py` and `test_family_grouper.py` were stripped of null bytes using `data.replace(b'\x00', b'')`. Future edits via the `Edit` tool may reintroduce them — strip before running pytest if this error recurs.

---

## Ready for Step 06?

**Yes.**

- `build_chain_versions()` produces one stable row per `VERSION_KEY` with all required columns.
- `build_chain_register()` produces one stable row per `FAMILY_KEY` with all required columns.
- No classification logic leaked into Step 05.
- `waiting_primary_flag` / `waiting_secondary_flag` use `_is_primary_approver()` from `query_library.py` exclusively.
- All 32 synthetic tests pass (0 failures, 0 warnings).
- Clean handoff: Step 06 timeline engine consumes `ops_df` + `debug_df` + `effective_df` to build `chain_events` (one row per lifecycle event). The `version_key` and `family_key` columns are already present on all three DataFrames from the Step 04 loader.

### Blockers for Step 06

None. Proceed to `src/chain_onion/chain_builder.py` (or `timeline_engine.py`).
