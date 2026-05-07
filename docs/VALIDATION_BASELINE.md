# VALIDATION BASELINE

This file defines the pipeline regression baseline. It is separate from JANSA
UI parity validation.

## Pipeline Baseline

Reference run: **Run 0**

Baseline state: clean FULL Run 0 rebuilt on 2026-05-07 from `input/`, with
`run_memory.db` and `report_memory.db` nuked first and then rebuilt. This
baseline intentionally retires the old 4,848 Flat GED document baseline:
BENTIN/BEN source qualification now excludes 701 raw rows before Flat GED
grouping, leaving 4,374 Flat GED document versions and 4,360 RunContext docs
after the existing SAS filter.

## Source-Exclusion Canaries

| Metric | Expected value |
|---|---:|
| raw BEN total | 912 |
| BEN included | 211 |
| BENTIN_SOURCE_OLD_NOT_LISTED | 701 |
| BEN unresolved | 0 |
| active PRE_2026:LOT 03-GOE-LGD | 0 |
| active PRE_2026:LOT 31 à 34-IN-BX-CFO-BENTIN | 0 |

`output/intermediate/RAW_GED_SOURCE_EXCLUSIONS.csv` is an expected artifact.
Debug preview files under `output/debug/` are validation evidence only and are
not production source-of-truth.

## Flat / Pipeline Counts

| Metric | Expected value |
|---|---:|
| raw GED data rows | 6901 |
| raw unique NUMERO | 2819 |
| raw unique NUMERO+INDICE | 4848 |
| Flat source exclusions | 701 |
| Flat unique document codes | 4374 |
| GED_RAW_FLAT rows | 24812 |
| GED_OPERATIONS rows | 29176 |
| stage_read_flat docs_df rows | 4360 |
| stage_read_flat responses_df rows | 24788 |
| final GF rows | 4349 |
| GF team workbook rows | 6041 |
| discrepancies rows | 2946 |
| discrepancies REVIEW_REQUIRED rows | 39 |
| anomaly report rows | 9 |
| ignored log rows | 47 |
| auto-resolution rows | 562 |
| reconciliation events | 172 |
| artifacts registered in run_memory | 33 |
| consultant report memory rows loaded | 1045 |
| ingested reports | 81 |

## Operational Dashboard Baseline

| Metric | Expected value |
|---|---:|
| operational_total | 2141 |
| fresh_total | 829 |
| stale_total | 1312 |
| moex_total | 1434 |
| moex_fresh | 425 |
| moex_stale | 1009 |
| primary_total | 628 |
| secondary_total | 79 |
| consultants_total | 707 |
| priority_p1 | 1814 |
| priority_p2 | 13 |
| priority_p3 | 90 |
| priority_p4 | 224 |
| priority_p5 | 0 |
| enterprise_ref_sas_candidates | 162 |
| enterprise_action_rows | 87 |
| old_debt_age_days_min | 91 |
| old_debt_age_days_median | 204 |
| old_debt_age_days_max | 801 |
| stale_threshold_days | 90 |

## Chain+Onion Baseline

| Metric | Expected value |
|---|---:|
| CHAIN_VERSIONS rows | 4374 |
| CHAIN_REGISTER rows | 2554 |
| live chains | 1276 |
| legacy chains | 96 |
| archived chains | 1182 |
| validation passed | 72 |
| validation warnings | 1 |
| validation failed | 0 |

## Validation Commands

Required after backend/pipeline changes:

```bash
python scripts/check_bentin_source_exclusion.py
python scripts/audit_counts_lineage.py
python scripts/check_operational_payload.py
python scripts/check_overview_operational_keys.py
python run_chain_onion.py
```

Expected audit headline:

```text
AUDIT: PASS=17 WARN=0 FAIL=0; first_unexpected_divergence=none
UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK
```

Unexpected mismatch means regression until proven otherwise. A mismatch is
allowed only when the task intentionally changes business behavior and this
baseline is updated with evidence.
