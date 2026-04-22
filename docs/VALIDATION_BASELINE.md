# VALIDATION BASELINE

This file defines the pipeline regression baseline. It is separate from JANSA UI parity validation.

## Pipeline Baseline

Reference run: **Run 0**

Baseline state: fresh post-reset FULL run created on 2026-04-22 from `input/`, with `report_memory.db` rebuilt from `input/consultant_reports`.

| Metric | Expected value |
|---|---:|
| `docs_total` | 6491 |
| `responses_total` | 545244 |
| `final_gf_rows` | 4728 |
| `discrepancies_count` | 3221 |
| `discrepancies_review_required` | 18 |
| `reconciliation_events` | 172 |
| `artifacts_registered_count` | 30 |
| `consultant_report_memory_rows_loaded` | 1245 |

## Pipeline Validation Rules

A backend or pipeline change must prove:

- the run completes successfully
- run status is `COMPLETED`
- `FINAL_GF` exists
- artifacts are registered in run memory
- `report_memory.db` loads the persisted consultant responses
- baseline metrics remain explainable and unchanged unless the task intentionally changes business behavior

Unexpected mismatch means regression until proven otherwise.

## UI Validation Layer

JANSA UI validation is tracked separately through:

- `docs/UI_RUNTIME_ARCHITECTURE.md`
- `docs/JANSA_PARITY_MASTER_PLAN.md`
- `docs/JANSA_PARITY_STEP_02_FOCUS.md`
- `docs/JANSA_PARITY_STEP_03_OVERVIEW.md`
- `docs/JANSA_PARITY_STEP_04_CONSULTANTS_LIST.md`
- `docs/JANSA_PARITY_STEP_05_FICHE.md`
- `docs/JANSA_PARITY_STEP_06_DRILLDOWNS.md`
- `docs/JANSA_PARITY_STEP_07_EXPORTS.md`
- `docs/JANSA_PARITY_STEP_09_RUNS.md`
- `docs/JANSA_PARITY_STEP_10_EXECUTER.md`
- `docs/JANSA_PARITY_STEP_11_UTILITIES.md`
- `docs/JANSA_FINAL_AUDIT.md`

Treat `docs/JANSA_FINAL_AUDIT.md` as the current UI truth sheet before review or push. Do not overclaim 100% parity; contractors remain deferred for redesign.
