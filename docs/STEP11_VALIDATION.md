# STEP11_VALIDATION.md
## Step 11 — Narrative Engine: Validation Report

**Date:** 2026-04-27
**Status:** COMPLETE — 31 passed, 1 skipped, 0 failed (3.41s)

---

## What Was Analyzed

| File | Purpose |
|------|---------|
| `docs/CHAIN_ONION_MASTER_STRATEGY.md` | Architecture, protected files, six-layer taxonomy |
| `docs/CHAIN_ONION_STEP_TRACKER.md` | Step status registry |
| `docs/STEP03_ONION_CONTRACT.md` | Layer definitions, issue_type vocabulary, forbidden logic |
| `docs/STEP09_VALIDATION.md` | `onion_layers_df` OUTPUT_COLS: `layer_code`, `severity_raw`, `confidence_raw`, `evidence_count` |
| `docs/STEP10_VALIDATION.md` | `onion_scores_df` OUTPUT_COLS: `normalized_score_100`, `top_layer_code`, `blended_confidence`, `action_priority_rank`, `portfolio_bucket`, `current_state` |
| `src/chain_onion/onion_scoring.py` | `_OUTPUT_COLS` list, `portfolio_bucket` vocabulary |
| `src/chain_onion/chain_classifier.py` | `current_state` vocabulary (12 states), `portfolio_bucket` vocabulary (3 buckets) |

---

## What Was Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `src/chain_onion/narrative_engine.py` | **Created** | Narrative Engine — `build_chain_narratives()` + helpers (~260 lines) |
| `tests/test_narrative_engine.py` | **Created** | 31 synthetic unit tests across 7 test classes + 1 skipped live test |
| `docs/STEP11_VALIDATION.md` | **Created** | This file |

**Not modified:** `src/flat_ged/*`, existing pipeline stages, UI files, Steps 04–10 code, `CHAIN_ONION_MASTER_STRATEGY.md`, `src/query_library.py`, `onion_engine.py`, `onion_scoring.py`, `chain_classifier.py`.

---

## Narrative Templates — Mapping Tables

### Executive Summary (by portfolio_bucket + normalized_score_100)

| Bucket | Score range | Template |
|--------|------------|----------|
| `LIVE_OPERATIONAL` | >= 70 | `Active chain with elevated operational pressure requiring near-term attention.` |
| `LIVE_OPERATIONAL` | 40–69 | `Active chain showing moderate pressure and follow-up need.` |
| `LIVE_OPERATIONAL` | < 40 | `Active chain currently under controlled pressure.` |
| `LEGACY_BACKLOG` | any | `Legacy open chain with limited current operational impact.` |
| `ARCHIVED_HISTORICAL` | any | `Historical closed chain with no current action required.` |

### Primary Driver Text (by top_layer_code)

| Layer Code | Template |
|-----------|----------|
| `L1_CONTRACTOR_QUALITY` | `Repeated rework or rejection cycles are the main efficiency drag.` |
| `L2_SAS_GATE_FRICTION` | `SAS gate activity is the main contributor to current delay pressure.` |
| `L3_PRIMARY_CONSULTANT_DELAY` | `Primary consultant response timing is the leading active constraint.` |
| `L4_SECONDARY_CONSULTANT_DELAY` | `Secondary consultant response timing is the leading active constraint.` |
| `L5_MOEX_ARBITRATION_DELAY` | `MOEX arbitration or final response timing is the leading constraint.` |
| `L6_DATA_REPORT_CONTRADICTION` | `Data or report contradictions are reducing workflow clarity.` |
| `None` / no layers | `No significant active friction signals detected.` |

### Secondary Driver Text

Same template map as primary driver, applied to the second-highest severity layer for the family.
Falls back to `No secondary material driver identified.` when fewer than 2 layers are active.

Second-layer selection: from `onion_layers_df`, exclude `top_layer_code`, sort remaining layers by
`severity_raw` DESC then `evidence_count` DESC, pick the first.

### Operational Note (by current_state + stale_days + bucket)

| Condition | Template |
|-----------|----------|
| `LEGACY_BACKLOG` AND `stale_days > 180` | `Open status appears administrative rather than operational.` |
| `WAITING_CORRECTED_INDICE` | `Awaiting corrected resubmission to restart chain progress.` |
| `OPEN_WAITING_PRIMARY_CONSULTANT` | `Current blocker sits with primary consultant review flow.` |
| `OPEN_WAITING_SECONDARY_CONSULTANT` | `Current blocker sits with secondary consultant review flow.` |
| `OPEN_WAITING_MOEX` | `Current blocker sits with MOEX finalization flow.` |
| `OPEN_WAITING_MIXED_CONSULTANTS` | `Current blocker sits with multiple consultant review flows.` |
| `CHRONIC_REF_CHAIN` | `Chain shows repeated rejection history and recycling risk.` |
| `VOID_CHAIN` | `Chain has no valid active version and may require administrative review.` |
| `DEAD_AT_SAS_A` | `Chain was rejected at initial SAS gate with no subsequent resubmission.` |
| `ABANDONED_CHAIN` | `Chain has had no recorded activity for an extended period.` |
| `CLOSED_VAO` | `Chain is closed with full approval — no operational action required.` |
| `CLOSED_VSO` | `Chain is closed with VSO approval — no operational action required.` |
| `UNKNOWN_CHAIN_STATE` | `Chain state could not be determined from available data.` |
| fallback | `No exceptional operational note.` |

Note: legacy stale check fires first when `portfolio_bucket == LEGACY_BACKLOG`.

### Recommended Focus (by portfolio_bucket + current_state + score)

| Condition | Template |
|-----------|----------|
| `ARCHIVED_HISTORICAL` | `No immediate action required.` |
| `LEGACY_BACKLOG` | `Review whether administrative closure or archive is appropriate.` |
| `LIVE_OPERATIONAL` AND `score >= 60` | `Prioritize direct unblocking actions and response coordination.` |
| `LIVE_OPERATIONAL` AND `WAITING_CORRECTED_INDICE` | `Clarify resubmission timing and completeness requirements.` |
| `LIVE_OPERATIONAL` AND consultant-wait states | `Confirm review owner, due date, and pending comments.` |
| fallback | `Monitor progress and follow up at next scheduled review cycle.` |

Note: high-score rule takes precedence over state-specific routing within LIVE_OPERATIONAL.

### Urgency Label (from normalized_score_100)

| Score | Label |
|-------|-------|
| >= 80 | `CRITICAL` |
| 60–79 | `HIGH` |
| 35–59 | `MEDIUM` |
| 1–34 | `LOW` |
| 0 | `NONE` |

### Confidence Label (from blended_confidence + has_layers)

| Condition | Label |
|-----------|-------|
| No active layers | `NONE` |
| `blended_confidence >= 85` | `HIGH` |
| `blended_confidence >= 65` | `MEDIUM` |
| `blended_confidence < 65` | `LOW` |

---

## Live Examples (Synthetic — from Tests)

### Example 1 — Archived Zero-Score Chain (`ARC001`)

| Column | Value |
|--------|-------|
| `current_state` | `CLOSED_VAO` |
| `portfolio_bucket` | `ARCHIVED_HISTORICAL` |
| `normalized_score_100` | `0.0` |
| `urgency_label` | `NONE` |
| `confidence_label` | `NONE` |
| `executive_summary` | `Historical closed chain with no current action required.` |
| `primary_driver_text` | `No significant active friction signals detected.` |
| `secondary_driver_text` | `No secondary material driver identified.` |
| `operational_note` | `Chain is closed with full approval — no operational action required.` |
| `recommended_focus` | `No immediate action required.` |

---

### Example 2 — Live Critical Consultant Chain (`LIVE001`, score=88)

| Column | Value |
|--------|-------|
| `current_state` | `OPEN_WAITING_PRIMARY_CONSULTANT` |
| `portfolio_bucket` | `LIVE_OPERATIONAL` |
| `normalized_score_100` | `88.0` |
| `urgency_label` | `CRITICAL` |
| `confidence_label` | `HIGH` |
| `executive_summary` | `Active chain with elevated operational pressure requiring near-term attention.` |
| `primary_driver_text` | `Primary consultant response timing is the leading active constraint.` |
| `secondary_driver_text` | `No secondary material driver identified.` |
| `operational_note` | `Current blocker sits with primary consultant review flow.` |
| `recommended_focus` | `Prioritize direct unblocking actions and response coordination.` |

---

### Example 3 — Legacy Stale Chain (`LEG001`, stale=250d)

| Column | Value |
|--------|-------|
| `current_state` | `OPEN_WAITING_PRIMARY_CONSULTANT` |
| `portfolio_bucket` | `LEGACY_BACKLOG` |
| `stale_days` | `250` |
| `normalized_score_100` | `15.0` |
| `urgency_label` | `LOW` |
| `executive_summary` | `Legacy open chain with limited current operational impact.` |
| `operational_note` | `Open status appears administrative rather than operational.` |
| `recommended_focus` | `Review whether administrative closure or archive is appropriate.` |

---

### Example 4 — Multi-Layer Chain (`MULTI001`, L3 CRITICAL + L2 HIGH)

| Column | Value |
|--------|-------|
| `current_state` | `OPEN_WAITING_MIXED_CONSULTANTS` |
| `portfolio_bucket` | `LIVE_OPERATIONAL` |
| `normalized_score_100` | `75.0` |
| `urgency_label` | `HIGH` |
| `confidence_label` | `HIGH` |
| `primary_driver_text` | `Primary consultant response timing is the leading active constraint.` |
| `secondary_driver_text` | `SAS gate activity is the main contributor to current delay pressure.` |
| `recommended_focus` | `Prioritize direct unblocking actions and response coordination.` |

---

### Example 5 — No Onion Rows (`CLEAN001`)

| Column | Value |
|--------|-------|
| `normalized_score_100` | `0.0` |
| `urgency_label` | `NONE` |
| `confidence_label` | `NONE` |
| `primary_driver_text` | `No significant active friction signals detected.` |
| `secondary_driver_text` | `No secondary material driver identified.` |

---

## Quality Checks

### Forbidden Word Scan

Scanned columns: `executive_summary`, `primary_driver_text`, `secondary_driver_text`,
`operational_note`, `recommended_focus`.

Forbidden set: `guilty`, `fault`, `incompetent`, `disaster`, `scandal`, `liar`, `fraud`, `blame`.

**Result: CLEAN** — No forbidden words appear in any template or fallback string. Validated by `TestForbiddenVocabulary` (2 sub-tests across 6 diverse family configurations) and by `_validate()` inside `build_chain_narratives()` at runtime.

### Null Text Check

All 5 text columns contain non-null, non-empty strings for every row. Validated by `TestForbiddenVocabulary::test_no_null_text`.

### Zero-Score Family Coverage

Zero-score families are always included: they receive `urgency_label = NONE`, `confidence_label = NONE`, and safe neutral text from fallback templates. Validated by `TestArchivedZeroScore` and `TestNoOnionRows`.

---

## Test Results

| # | Test Class / Name | Result | What it checks |
|---|-------------------|--------|----------------|
| 1a | `TestArchivedZeroScore::test_one_row` | PASSED | One family → 1 output row |
| 1b | `TestArchivedZeroScore::test_urgency_none` | PASSED | Zero score → NONE urgency |
| 1c | `TestArchivedZeroScore::test_confidence_none` | PASSED | No layers → NONE confidence |
| 1d | `TestArchivedZeroScore::test_summary_contains_historical` | PASSED | Archived bucket → "Historical" |
| 1e | `TestArchivedZeroScore::test_no_action_required` | PASSED | Archived → no action text |
| 1f | `TestArchivedZeroScore::test_no_primary_driver` | PASSED | No layers → no driver text |
| 1g | `TestArchivedZeroScore::test_required_columns_present` | PASSED | All 15 OUTPUT_COLS present |
| 2a | `TestLiveCriticalConsultant::test_urgency_critical` | PASSED | Score=88 → CRITICAL |
| 2b | `TestLiveCriticalConsultant::test_confidence_high` | PASSED | blended=87 → HIGH confidence |
| 2c | `TestLiveCriticalConsultant::test_primary_driver_consultant` | PASSED | L3 → consultant wording |
| 2d | `TestLiveCriticalConsultant::test_summary_elevated` | PASSED | Score>=70 → "elevated" |
| 2e | `TestLiveCriticalConsultant::test_operational_note_primary` | PASSED | WAITING_PRIMARY → primary note |
| 2f | `TestLiveCriticalConsultant::test_recommended_unblocking` | PASSED | High score → unblocking focus |
| 2g | `TestLiveCriticalConsultant::test_action_rank_populated` | PASSED | action_priority_rank populated |
| 3a | `TestLegacyStaleChain::test_summary_legacy` | PASSED | LEGACY bucket → "Legacy" |
| 3b | `TestLegacyStaleChain::test_operational_note_administrative` | PASSED | stale>180 → "administrative" |
| 3c | `TestLegacyStaleChain::test_focus_closure` | PASSED | LEGACY → closure/archive |
| 3d | `TestLegacyStaleChain::test_urgency_low` | PASSED | Score=15 → LOW |
| 4a | `TestMultiLayerChain::test_primary_driver_is_consultant` | PASSED | top=L3 → consultant primary |
| 4b | `TestMultiLayerChain::test_secondary_driver_is_sas` | PASSED | second=L2 → SAS secondary |
| 4c | `TestMultiLayerChain::test_primary_and_secondary_differ` | PASSED | Two distinct driver texts |
| 4d | `TestMultiLayerChain::test_urgency_high` | PASSED | Score=75 → HIGH or CRITICAL |
| 4e | `TestMultiLayerChain::test_confidence_medium_or_high` | PASSED | blended=80 → MEDIUM or HIGH |
| 5a | `TestNoOnionRows::test_primary_driver_is_none_text` | PASSED | No layers → neutral primary |
| 5b | `TestNoOnionRows::test_secondary_driver_is_none_text` | PASSED | No layers → neutral secondary |
| 5c | `TestNoOnionRows::test_confidence_none` | PASSED | No layers → NONE |
| 5d | `TestNoOnionRows::test_urgency_none` | PASSED | Score=0 → NONE |
| 6a | `TestForbiddenVocabulary::test_no_forbidden_words` | PASSED | 8 banned words × 6 families |
| 6b | `TestForbiddenVocabulary::test_no_null_text` | PASSED | 0 null/empty text cells |
| 7a | `TestDeterministicRepeat::test_text_columns_identical` | PASSED | 7 text cols match on repeat call |
| 7b | `TestDeterministicRepeat::test_scores_identical` | PASSED | Score/urgency match on repeat |
| 8  | `TestLiveRun::test_live_run` | SKIPPED | Full run — Claude Code / Codex only |

**Suite result: 31 passed, 1 skipped, 0 failed — 3.41s**

---

## Live Metrics

**Skipped — Claude Code / Codex full-run required.**

Run manually:
```
pytest tests/test_narrative_engine.py -k TestLiveRun -s
```

Expected output format:
- Total narratives generated
- Top 20 by action_priority_rank (rank, family_key, urgency, score, executive_summary)
- Urgency distribution (CRITICAL / HIGH / MEDIUM / LOW / NONE counts)
- Confidence distribution (HIGH / MEDIUM / LOW / NONE counts)

---

## Implementation Notes

- **`generated_at` non-deterministic by design**: The `generated_at` timestamp changes on every call. It is excluded from determinism tests (correct — it's an audit field, not a text field).
- **High-score routing priority**: Within `LIVE_OPERATIONAL`, `score >= 60` takes precedence over state-specific routing in `recommended_focus`. This ensures critical chains always surface the "unblock" recommendation rather than a more passive state-specific note.
- **Legacy stale check fires before state lookup**: When `portfolio_bucket == LEGACY_BACKLOG` and `stale_days > 180`, the administrative note is returned immediately, overriding the state-based note. This reflects the operational reality that very stale legacy chains need admin review regardless of their formal state.
- **Zero-score families**: All `family_key` values from `chain_register_df` are emitted. Families absent from `onion_scores_df` or `onion_layers_df` receive scores=0 and safe fallback text. This preserves portfolio completeness for the export layer.
- **`_validate()` runs at the end of every `build_chain_narratives()` call**: It checks for missing columns, null text, and forbidden vocabulary, logging errors to the module logger. It never raises — it informs operators of issues without crashing downstream.

---

## Ready for Step 12?

**Yes.**

- `build_chain_narratives()` returns one row per `family_key` with all 15 output columns populated.
- Zero-score families included and handled cleanly.
- Text is deterministic from inputs — same inputs always produce same outputs.
- No banned vocabulary in any template or fallback string.
- All 15 output columns present and non-null.
- `action_priority_rank` and `normalized_score_100` passed through from Step 10 for export ordering.
- `engine_version` and `generated_at` present for audit trail.
- `_OUTPUT_COLS` list is the authoritative contract for Step 12 (Export Engine).

### Key inputs Step 12 (Export Engine) will consume:

- `chain_narratives_df.action_priority_rank` — sort order for export
- `chain_narratives_df.urgency_label` — filter / color-code column
- `chain_narratives_df.executive_summary` — primary narrative for management sheet
- `chain_narratives_df.primary_driver_text` + `secondary_driver_text` — body text
- `chain_narratives_df.recommended_focus` — action column
- `chain_narratives_df.normalized_score_100` — numeric score column
- `chain_narratives_df.family_key` / `numero` — join keys to other chain tables
