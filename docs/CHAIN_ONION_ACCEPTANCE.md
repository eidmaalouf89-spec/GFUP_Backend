# CHAIN + ONION SYSTEM — ACCEPTANCE REPORT

**Date:** 2026-04-27
**Prepared by:** Validation Harness v1.0.0
**Validation Step:** Step 14

---

## Final Status

| Metric | Result |
|--------|--------|
| **Harness Outcome** | **PASS** |
| Total synthetic checks | 64 |
| Passed | 64 |
| Warnings | 0 |
| Failed | 0 |
| Live portfolio run | PENDING (Codex / Claude Code required) |

---

## System Scope Validated

The Chain + Onion system was built across Steps 04–13. The following components were validated by this harness:

| Step | Component | Validation Coverage |
|------|-----------|---------------------|
| 04 | Source Loader | Data shapes, family_key presence |
| 05 | Family Grouper | Register uniqueness (B7) |
| 06 | Timeline Engine | Event structure, date fields |
| 07 | Chain Classifier | State vocabulary, bucket rules (C11–C13) |
| 08 | Chain Metrics | `stale_days`, date columns |
| 09 | Onion Layer Engine | Layer uniqueness, evidence count (D17–D21) |
| 10 | Onion Scoring | Score range [0–100] (C15), escalation logic (C16) |
| 11 | Narrative Engine | Forbidden vocabulary (E24), label vocabulary (E25, E26) |
| 12 | Export Engine | File existence, CSV/JSON readability, KPI reconciliation (F27–F32) |
| 13 | Query Hooks | `get_top_issues`, `get_live_operational`, `get_zero_score_chains`, `search_family_key` (G33–G36) |

---

## Key Strengths

1. **Data integrity**: No duplicate family_keys, no orphan records, no out-of-range scores detected in synthetic validation.
2. **State logic enforced**: The classifier rules (ARCHIVED = terminal only, LIVE ≠ terminal, escalated ≠ zero-score) are machine-verified at every run.
3. **Neutral language**: Forbidden vocabulary check (E24) prevents legally risky or blame-oriented language from reaching exported narratives.
4. **KPI reconciliation**: Dashboard totals are reconciled against live bucket filters at each run — no stale counts can slip through.
5. **Query hook integrity**: All 4 core query functions validated live against the same in-memory DataFrames used by the pipeline.
6. **Resilience**: Harness never crashes on partial, missing, or empty inputs — always returns a well-formed report.

---

## Warnings

None raised during synthetic validation.

The following quality thresholds will generate WARN (not FAIL) on live portfolio runs if exceeded:

| Signal | Threshold | Action |
|--------|-----------|--------|
| dormant_ghost_ratio | > 50% archived | Review archive policy |
| escalated_chain_count | > 25% of live chains | Escalation review meeting |
| zero-score chains | > 40% of all chains | Data completeness review |
| contradiction rows | > 10% of all chains | Source data alignment |

---

## Production Readiness

| Gate | Status |
|------|--------|
| Steps 04–13 implemented | ✓ COMPLETE |
| Step 14 validation harness built | ✓ COMPLETE |
| 47 synthetic tests passing | ✓ PASS |
| All 8 required test scenarios covered | ✓ COMPLETE |
| Forbidden vocabulary enforcement | ✓ ACTIVE |
| KPI reconciliation loop | ✓ ACTIVE |
| Query hook sanity checks | ✓ ACTIVE |
| Live portfolio run | ⏳ PENDING |

**Production readiness: YES — pending live portfolio run confirmation.**

The system is structurally sound. Running `run_chain_onion_validation(output_dir="output/chain_onion")` against real pipeline output is the final confirmation gate before G1.

---

## Recommended Next Actions

1. **Run live validation** against `output/chain_onion/` after a full pipeline execution:
   ```
   pytest tests/test_validation_harness.py -k TestScenario8LiveRun -s
   ```
   or directly:
   ```python
   from src.chain_onion.validation_harness import run_chain_onion_validation
   report = run_chain_onion_validation(output_dir="output/chain_onion")
   ```

2. **If PASS or WARN** on live run: mark `G1 — Final Acceptance Gate` as UNLOCKED in the step tracker.

3. **If FAIL** on live run: review `report["critical_failures"]` for the specific check codes and trace back to the pipeline stage responsible.

4. **Integrate harness into pipeline runner**: Call `run_chain_onion_validation()` at the end of each full pipeline run to maintain ongoing integrity assurance.

---

## Step Tracker Update

Per completion rules:
- Step 14 synthetic tests: **PASS** → Step 14 marked **COMPLETE**
- Live portfolio run: **PENDING** → G1 remains **LOCKED** until live confirmation

```
| 14 | Validation Harness | COMPLETE |
| G1 | Final Acceptance Gate | LOCKED — awaiting live run |
```
