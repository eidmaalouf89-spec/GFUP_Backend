# STEP12_VALIDATION.md
## Step 12 — Export Engine: Validation Report

**Date:** 2026-04-27
**Status:** COMPLETE — 45 passed, 1 skipped, 0 failed (17.85s)

---

## What Was Analyzed

| File | Purpose |
|------|---------|
| `docs/CHAIN_ONION_STEP_TRACKER.md` | Step status registry |
| `docs/STEP10_VALIDATION.md` | `onion_scores_df` column contract, `action_priority_rank`, theme buckets |
| `docs/STEP11_VALIDATION.md` | `chain_narratives_df` output contract (15 columns), sort key, urgency/confidence labels |
| `src/chain_onion/onion_scoring.py` | `_OUTPUT_COLS`, `portfolio_bucket` vocabulary |
| `src/chain_onion/narrative_engine.py` | Output column contract, `generated_at` audit field |

---

## What Was Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `src/chain_onion/exporter.py` | **Created** | Export Engine — `export_chain_onion_outputs()` + helpers (~370 lines) |
| `tests/test_exporter.py` | **Created** | 45 synthetic unit tests across 7 test classes + 1 skipped live test |
| `docs/STEP12_VALIDATION.md` | **Created** | This file |

**Not modified:** `src/flat_ged/*`, UI files, Steps 04–11 code, `CHAIN_ONION_MASTER_STRATEGY.md`, `src/query_library.py`, pipeline stages.

---

## Artifacts Exported

### CSV Files (7)

| Artifact | Sort Key | Description |
|----------|----------|-------------|
| `CHAIN_REGISTER.csv` | `family_key` | One row per family |
| `CHAIN_VERSIONS.csv` | `family_key`, `version_number` | All chain versions |
| `CHAIN_EVENTS.csv` | `family_key`, `event_date`, `event_type` | Timeline events |
| `CHAIN_METRICS.csv` | `family_key` | Computed chain metrics |
| `ONION_LAYERS.csv` | `family_key`, `layer_code` | Per-layer evidence rows |
| `ONION_SCORES.csv` | `action_priority_rank`, `family_key` | Scored chains, rank 1 = highest urgency |
| `CHAIN_NARRATIVES.csv` | `action_priority_rank`, `family_key` | Management summaries |

### JSON Files (2)

| Artifact | Description |
|----------|-------------|
| `dashboard_summary.json` | Portfolio-level KPI snapshot |
| `top_issues.json` | Top 20 chains by action_priority_rank |

### XLSX Workbook (1)

| Artifact | Sheets | Description |
|----------|--------|-------------|
| `CHAIN_ONION_SUMMARY.xlsx` | 11 | Full multi-sheet management workbook |

---

## XLSX Sheet List

| # | Sheet Name | Filter / Content | Sort |
|---|-----------|-----------------|------|
| 1 | Executive Priorities | Top 50 by `action_priority_rank` from narratives | `action_priority_rank`, `family_key` |
| 2 | Live Operational Chains | `portfolio_bucket == LIVE_OPERATIONAL` | `action_priority_rank`, `family_key` |
| 3 | Consultant Delays | `consultant_primary_impact_score > 0` OR `consultant_secondary_impact_score > 0` | `action_priority_rank`, `family_key` |
| 4 | Contractor Quality | `contractor_impact_score > 0` | `action_priority_rank`, `family_key` |
| 5 | MOEX-SAS Blocking | `moex_impact_score > 0` OR `sas_impact_score > 0` | `action_priority_rank`, `family_key` |
| 6 | Legacy Backlog Cleanup | `portfolio_bucket == LEGACY_BACKLOG` | `action_priority_rank`, `family_key` |
| 7 | Archived Historical | `portfolio_bucket == ARCHIVED_HISTORICAL` | `action_priority_rank`, `family_key` |
| 8 | Portfolio KPIs | Key/value rows from `portfolio_metrics` + `onion_portfolio_summary` | `source`, `key` |
| 9 | Full Chain Metrics | All rows from `chain_metrics_df` | `family_key` |
| 10 | Full Onion Scores | All rows from `onion_scores_df` | `action_priority_rank`, `family_key` |
| 11 | Narratives | All rows from `chain_narratives_df` | `action_priority_rank`, `family_key` |

> **Note:** Excel disallows `/` in sheet names. "MOEX / SAS Blocking" is stored as **"MOEX-SAS Blocking"** in the workbook. The filter logic is unchanged.

---

## Row Counts (Synthetic Test Suite — 3-family portfolio)

| Artifact | Rows |
|----------|------|
| CHAIN_REGISTER.csv | 3 |
| CHAIN_VERSIONS.csv | 6 (3 families × 2 versions) |
| CHAIN_EVENTS.csv | 3 |
| CHAIN_METRICS.csv | 3 |
| ONION_LAYERS.csv | 3 |
| ONION_SCORES.csv | 3 |
| CHAIN_NARRATIVES.csv | 3 |
| Executive Priorities (XLSX) | 3 (capped at 50) |
| Live Operational Chains (XLSX) | 1 |
| Consultant Delays (XLSX) | 2 |
| Contractor Quality (XLSX) | 1 |
| MOEX-SAS Blocking (XLSX) | 1 |
| Legacy Backlog Cleanup (XLSX) | 1 |
| Archived Historical (XLSX) | 1 |
| Portfolio KPIs (XLSX) | 8 (3 from portfolio_metrics + 5 from onion_summary) |
| Full Chain Metrics (XLSX) | 3 |
| Full Onion Scores (XLSX) | 3 |
| Narratives (XLSX) | 3 |
| top_issues.json | 3 items (capped at 20) |

---

## JSON Keys

### dashboard_summary.json

| Key | Type | Description |
|-----|------|-------------|
| `total_chains` | int | Total families in onion_scores_df |
| `live_chains` | int | Families with `portfolio_bucket == LIVE_OPERATIONAL` |
| `legacy_chains` | int | Families with `portfolio_bucket == LEGACY_BACKLOG` |
| `archived_chains` | int | Families with `portfolio_bucket == ARCHIVED_HISTORICAL` |
| `dormant_ghost_ratio` | float | `archived_chains / total_chains` (0 if total = 0) |
| `avg_pressure_live` | float | Mean `normalized_score_100` for live chains |
| `escalated_chain_count` | int | Count of rows where `escalation_flag == True` |
| `top_theme_by_impact` | str | Dominant layer by total portfolio impact |
| `generated_at` | str | ISO-8601 UTC timestamp of export run |
| `engine_version` | str | Exporter version (`1.0.0`) |

### top_issues.json (per item)

| Key | Description |
|-----|-------------|
| `family_key` | Family identifier |
| `numero` | Administrative number |
| `action_priority_rank` | Priority rank (1 = most urgent) |
| `normalized_score_100` | Overall onion score 0–100 |
| `urgency_label` | CRITICAL / HIGH / MEDIUM / LOW / NONE |
| `portfolio_bucket` | LIVE_OPERATIONAL / LEGACY_BACKLOG / ARCHIVED_HISTORICAL |
| `current_state` | Operational state label |
| `executive_summary` | One-line management summary |
| `primary_driver_text` | Primary friction driver sentence |
| `recommended_focus` | Recommended action |
| `escalation_flag` | Boolean escalation indicator |

---

## Test Results

| # | Test Class / Name | Result | What it checks |
|---|-------------------|--------|----------------|
| 1a | `TestCSVFiles::test_all_csvs_created` | PASSED | All 7 CSVs in artifacts dict and on disk |
| 1b | `TestCSVFiles::test_csv_row_counts` | PASSED | CHAIN_REGISTER has 3 rows |
| 1c | `TestCSVFiles::test_chain_versions_row_count` | PASSED | CHAIN_VERSIONS has 6 rows (3×2) |
| 1d | `TestCSVFiles::test_csv_has_headers` | PASSED | All CSVs have ≥1 column header |
| 1e | `TestCSVFiles::test_onion_scores_sorted_by_rank` | PASSED | ONION_SCORES sorted ascending by rank |
| 1f | `TestCSVFiles::test_narratives_sorted_by_rank` | PASSED | CHAIN_NARRATIVES sorted ascending by rank |
| 2a | `TestXLSXWorkbook::test_xlsx_created` | PASSED | CHAIN_ONION_SUMMARY.xlsx in artifacts and on disk |
| 2b | `TestXLSXWorkbook::test_all_sheets_present` | PASSED | All 11 sheet names present |
| 2c | `TestXLSXWorkbook::test_executive_priorities_max_50` | PASSED | Executive Priorities ≤ 50 rows |
| 2d | `TestXLSXWorkbook::test_live_operational_chains_filter` | PASSED | All rows in sheet are LIVE_OPERATIONAL |
| 2e | `TestXLSXWorkbook::test_legacy_backlog_filter` | PASSED | All rows in sheet are LEGACY_BACKLOG |
| 2f | `TestXLSXWorkbook::test_archived_historical_filter` | PASSED | All rows in sheet are ARCHIVED_HISTORICAL |
| 2g | `TestXLSXWorkbook::test_portfolio_kpis_has_rows` | PASSED | KPI sheet has ≥1 row |
| 2h | `TestXLSXWorkbook::test_portfolio_kpis_columns` | PASSED | KPI sheet has `source`, `key`, `value` columns |
| 2i | `TestXLSXWorkbook::test_consultant_delays_filter` | PASSED | All rows have consultant impact > 0 |
| 2j | `TestXLSXWorkbook::test_moex_sas_filter` | PASSED | All rows have moex or sas impact > 0 |
| 2k | `TestXLSXWorkbook::test_sheet_count_exactly_11` | PASSED | Exactly 11 sheets |
| 3a | `TestJSONDashboard::test_dashboard_summary_created` | PASSED | dashboard_summary.json on disk |
| 3b | `TestJSONDashboard::test_top_issues_created` | PASSED | top_issues.json on disk |
| 3c | `TestJSONDashboard::test_dashboard_parses` | PASSED | JSON parses as dict |
| 3d | `TestJSONDashboard::test_dashboard_required_keys` | PASSED | All 8 required keys present |
| 3e | `TestJSONDashboard::test_dashboard_total_chains` | PASSED | total_chains = 3 |
| 3f | `TestJSONDashboard::test_dashboard_live_chains` | PASSED | live_chains = 1 |
| 3g | `TestJSONDashboard::test_dashboard_dormant_ratio_in_range` | PASSED | dormant_ghost_ratio ∈ [0.0, 1.0] |
| 3h | `TestJSONDashboard::test_top_issues_parses_as_list` | PASSED | top_issues is a JSON array |
| 3i | `TestJSONDashboard::test_top_issues_max_20` | PASSED | ≤ 20 items |
| 3j | `TestJSONDashboard::test_top_issues_has_required_keys` | PASSED | All per-item keys present |
| 3k | `TestJSONDashboard::test_top_theme_from_summary` | PASSED | top_theme sourced from onion_portfolio_summary |
| 4a | `TestEmptyInputs::test_empty_runs_without_error` | PASSED | All-empty inputs → no crash |
| 4b | `TestEmptyInputs::test_empty_csvs_exist` | PASSED | Files created even for empty inputs |
| 4c | `TestEmptyInputs::test_empty_csv_has_zero_rows` | PASSED | Zero rows (or empty file) on empty input |
| 4d | `TestEmptyInputs::test_empty_xlsx_exists` | PASSED | XLSX created on empty input |
| 4e | `TestEmptyInputs::test_empty_xlsx_has_all_sheets` | PASSED | All 11 sheets present on empty input |
| 4f | `TestEmptyInputs::test_empty_dashboard_json_parseable` | PASSED | dashboard JSON valid; total_chains = 0 |
| 4g | `TestEmptyInputs::test_empty_top_issues_is_empty_list` | PASSED | top_issues = [] on empty input |
| 4h | `TestEmptyInputs::test_empty_kpi_sheet_has_headers` | PASSED | KPI sheet is valid DataFrame on empty dicts |
| 5a | `TestDeterministicSort::test_csv_identical_on_repeat` | PASSED | ONION_SCORES.csv byte-identical on two runs |
| 5b | `TestDeterministicSort::test_narratives_csv_identical_on_repeat` | PASSED | CHAIN_NARRATIVES.csv identical on two runs |
| 5c | `TestDeterministicSort::test_inputs_not_mutated` | PASSED | Input DataFrames unchanged after export |
| 5d | `TestDeterministicSort::test_chain_register_sorted_by_family_key` | PASSED | CHAIN_REGISTER sorted A→Z by family_key |
| 6a | `TestReturnDict::test_returns_dict` | PASSED | Return type is dict |
| 6b | `TestReturnDict::test_all_expected_keys_present` | PASSED | All 10 artifact keys in return dict |
| 6c | `TestReturnDict::test_all_paths_are_strings` | PASSED | All values are string paths |
| 6d | `TestReturnDict::test_all_paths_exist` | PASSED | All paths exist on disk |
| 6e | `TestReturnDict::test_output_dir_created` | PASSED | Nested output_dir created automatically |
| 7  | `TestLiveRun::test_live_run` | SKIPPED | Full run — Claude Code / Codex only |

**Suite result: 45 passed, 1 skipped, 0 failed — 17.85s**

---

## Live Metrics

**Skipped — Claude Code / Codex full-run required.**

Run manually:
```
pytest tests/test_exporter.py -k TestLiveRun -s
```

Expected output format:
- Total artifacts created (10 files)
- Row counts per CSV
- Sheet row counts per XLSX sheet
- dashboard_summary.json printed
- top_issues.json first 5 items

---

## Warnings / Design Notes

- **"MOEX / SAS Blocking" → "MOEX-SAS Blocking"**: Excel's openpyxl rejects sheet names containing `/`. The sheet is stored as `MOEX-SAS Blocking`. The filter logic (`moex_impact_score > 0 OR sas_impact_score > 0`) is unchanged. Step 13 (Query Hooks) should reference the stored name `MOEX-SAS Blocking`.
- **`generated_at` is non-deterministic**: The `dashboard_summary.json` `generated_at` field is an audit timestamp. It changes on every call by design and is excluded from determinism assertions.
- **Empty DataFrame CSVs**: A fully empty `pd.DataFrame()` (no columns) writes an empty file with no headers. This is the correct pandas behavior. Any DataFrame with a defined schema writes a header-only file with zero data rows. Both are valid per spec.
- **`top_theme_by_impact` resolution order**: First tries `onion_portfolio_summary["top_theme_by_impact"]`; falls back to computing the highest summed impact column from `onion_scores_df`; falls back to `"UNKNOWN"` if no impact columns are present.
- **Inputs are never mutated**: All DataFrames are `.copy()`-ed at entry before any sorting or transformation.

---

## Ready for Step 13?

**Yes.**

- All 10 artifact files created deterministically from pipeline outputs.
- `ONION_SCORES.csv` and `CHAIN_NARRATIVES.csv` sorted by `action_priority_rank` for direct consumption by Query Hooks.
- `dashboard_summary.json` provides portfolio-level KPIs for dashboard wiring.
- `top_issues.json` provides a pre-ranked top-20 list for direct UI consumption.
- `CHAIN_ONION_SUMMARY.xlsx` workbook has all 11 management sheets ready for distribution.
- Empty inputs handled safely — no crashes, files created with correct structure.
- `export_chain_onion_outputs()` return dict provides explicit file paths for downstream chaining.

### Key outputs Step 13 (Query Hooks) will consume:

- `output/chain_onion/ONION_SCORES.csv` — full scored chain table for filtering queries
- `output/chain_onion/CHAIN_NARRATIVES.csv` — narratives table for text retrieval
- `output/chain_onion/dashboard_summary.json` — portfolio KPIs for dashboard binding
- `output/chain_onion/top_issues.json` — pre-ranked top-20 for priority views
- `output/chain_onion/CHAIN_ONION_SUMMARY.xlsx` — sheet-level data for ad-hoc queries
