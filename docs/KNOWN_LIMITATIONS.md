# KNOWN LIMITATIONS

This file lists current limitations, rough edges, and non-blocking issues in the pipeline.
These are not bugs unless stated otherwise.

---

## 1. Consultant match report not auto-generated

- `consultant_match_report.xlsx` is not produced in the main pipeline run.
- Requires separate execution via `consultant_integration.py` (if needed).
- Current system relies on `report_memory.db` (1242 persisted responses).

Impact:
- No direct visibility of matching quality in standard outputs.

---

## 2. report_memory.db dependency

- Pipeline behavior can depend on pre-seeded `report_memory.db`.
- Fresh DB produces identical outputs in current baseline, but this may not always hold.

Rule:
- DO NOT delete `report_memory.db` unless performing a full system reset.

---

## 3. Large PipelineState (77 fields)

- State object contains all intermediate data across stages.
- Hard to reason about dependencies at a glance.

Impact:
- Future modifications require careful tracking of which stage reads/writes which fields.

Note:
- Acceptable for now. Refactoring into sub-objects can be considered later.

---

## 4. Discrepancy computation complexity

- `_compute_discrepancies` (in pipeline/compute.py) is large and central.
- Handles multiple responsibilities:
  - GED vs GF comparison
  - classification
  - subtype logic
  - debug data

Impact:
- High-risk area for regressions if modified.

Rule:
- Modify only in small, isolated changes.
- Always validate against baseline after changes.

---

## 5. Excel output non-deterministic hashes

- Output `.xlsx` files have different file hashes between runs.
- Caused by Excel metadata (timestamps, internal IDs).

Impact:
- Cannot use file hash for regression validation.

Rule:
- Validate using metrics (row counts, discrepancies, etc.), not hashes.

---

## 6. openpyxl warnings

- Warning: "Cell date serial value outside limits"
- Occurs during Excel read/write.

Impact:
- Non-blocking.
- Does not affect pipeline results.

---

## 7. Debug artifacts always generated

- 14 debug files generated in `output/debug/`.
- No toggle to disable them.

Impact:
- Extra I/O and clutter.

---

## 8. Tight coupling to file structure

- Pipeline expects:
  - `input/`
  - `output/`
  - `data/`
  - `runs/`

Impact:
- Not easily relocatable or configurable without code changes.

---

## 9. No partial pipeline execution

- Pipeline must run fully (FULL mode).
- No support for running only specific stages.

Impact:
- Slower iteration during development.

---

## 10. No formal test suite

- Validation relies on full pipeline runs and baseline comparison.
- No unit tests for domain logic.

Impact:
- Changes must always be validated via full run.

---

## 11. Run history reset is destructive

- Reset requires deleting:
  - `runs/`
  - `output/`
  - `run_memory.db`

Impact:
- Must always backup before reset.

---

## 12. Performance not optimized

- Large datasets (6k+ docs, 500k+ responses).
- Multiple full DataFrame passes.

Impact:
- Execution time may increase with scale.

---

# Summary

The system is:
- functionally correct
- deterministic
- stable under current baseline

But:
- not fully modular internally
- not optimized for incremental execution
- dependent on strict execution flow

All changes must follow:
1. small scope
2. full pipeline run
3. baseline validation

## 13. Backend capabilities are not yet easily exploitable

- The codebase already contains a large amount of valuable business logic and deterministic processing.
- However, this logic is still difficult to exploit rapidly for:
  - UI adaptation
  - dashboard/report redesign
  - Excel export variants
  - custom presentation layers
  - alternative output formats

Current problem:
- changing reports, exports, or UI behavior may require re-understanding a large part of the pipeline
- output generation is still too close to internal processing logic
- there is not yet a clean “product layer” exposing reusable structured results for multiple frontends/exports

Impact:
- slows down iteration
- increases change risk
- makes rapid experimentation difficult
- forces repeated re-analysis of the codebase before making presentation/output changes

What is needed later:
- a clearer separation between:
  1. core deterministic engine
  2. structured intermediate/output data model
  3. presentation adapters (UI, reports, Excel exports, dashboards)

Target direction:
- the pipeline should produce stable, reusable structured outputs
- UI/report/export layers should consume those outputs without needing to understand the whole backend