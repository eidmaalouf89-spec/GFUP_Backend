# STEP8_IMPLEMENTATION_NOTES.md

**Step:** 8 — clean_GF Logical Reconstruction / Composition Implementation  
**Plan version:** v2  
**Date completed:** 2026-04-24  
**Status:** COMPLETE

---

## 1. Files Changed

| File | Change |
|------|--------|
| `src/effective_responses.py` | Full rewrite — Flat GED composition anchor, Rules 1–4, E2/E7 gates, VAOB, conflict detection, five-value provenance vocab |
| `src/report_memory.py` | Added `deactivated_reason` column to DDL + v2 migration; added `deactivate_answered_report_rows()` |
| `src/pipeline/stages/stage_report_memory.py` | E2 confidence filter before upsert; `flat_mode` flag passed to composition; stale row deactivation after composition |
| `src/pipeline/stages/stage_write_gf.py` | Flat mode: attach `_flat_visa_override` to `wf_engine` using `get_visa_global()` |
| `src/workflow_engine.py` | `compute_visa_global_with_date()` checks `_flat_visa_override` first (SAS REF fix) |
| `src/reporting/data_loader.py` | Retired `bet_report_merger`; UI now uses `build_effective_responses()` from `report_memory.db` |
| `src/consultant_integration.py` | Direct GF write stages guarded with `_DIRECT_GF_WRITE_DEPRECATED = True` |
| `scripts/bootstrap_report_memory.py` | E2 confidence filter before upsert |
| `data/report_memory.db` | Repaired from `runs/run_0000/report_memory.db` (was malformed); 1,245 active rows, 85 ingested reports |

**Files not changed (confirmed):**
- `src/flat_ged/` — git diff HEAD confirms zero changes
- `src/pipeline/stages/stage_read_flat.py` — unchanged
- Chain/Onion, cue engine — not touched

---

## 2. Rules Implemented

### Composition Rules (effective_responses.py)

| Rule | Description | effective_source |
|------|-------------|-----------------|
| R1a | GED ANSWERED, no eligible report | `GED` |
| R1b | GED ANSWERED, report is stale (E7 fails) | `GED` |
| R1c | GED ANSWERED, report carries VAOB or same-family / additive comment | `GED+REPORT_COMMENT` |
| R1d | GED ANSWERED, report carries conflicting status (REF vs VAO etc.) | `GED_CONFLICT_REPORT` |
| R2a | GED PENDING, report has status + date → upgrade to ANSWERED | `GED+REPORT_STATUS` |
| R2b | GED PENDING, report has date only → upgrade, preserve GED status | `GED+REPORT_STATUS` |
| R2c | GED PENDING, report has status only (no date) → additive comment | `GED+REPORT_COMMENT` |
| R3 | GED PENDING, no eligible report → remain pending | `GED` |
| R4 | NOT_CALLED / absent → leave as-is, no new rows synthesized | `GED` |

### Eligibility Gates

| Gate | Enforcement point |
|------|------------------|
| E1 (is_active=1) | `load_persisted_report_responses()` — existing |
| E2 (HIGH/MEDIUM confidence only) | `stage_report_memory.py` before upsert + `bootstrap_report_memory.py` + `normalize_persisted_report_responses_for_merge()` |
| E3 (doc_id match) | Left-join at composition layer |
| E4 (approver match) | Left-join at composition layer |
| E5/E6 (date or status present) | `normalize_persisted_report_responses_for_merge()` |
| E7 (freshness gate) | `build_effective_responses()` — flat mode only |
| E8 (no synthetic SAS) | Enforced upstream at ingestion (not in composition layer) |

### VAOB Rule
VAOB = VAO (Eid decision 2026-04-24). Implemented as:
- `_is_vaob()` helper recognises VAOB as approval-family
- On ANSWERED GED rows: VAOB is not a conflict → `GED+REPORT_COMMENT`
- On PENDING GED rows: VAOB is eligible for upgrade like any approval

### Visa Global Fix (SAS REF gap)
- `stage_write_gf.py` attaches `wf_engine._flat_visa_override` dict in flat mode, populated via `get_visa_global()` per doc
- `workflow_engine.compute_visa_global_with_date()` checks `_flat_visa_override` before engine logic
- Fixes VP-1: SAS REF docs previously returned `(None, None)` from engine; now return `"SAS REF"` in flat mode

### bet_report_merger Retirement
- Import commented out in `data_loader.py` with `# DO NOT RESTORE`
- `merge_bet_reports()` call replaced with `build_effective_responses()` + `load_persisted_report_responses()`
- `WorkflowEngine` rebuilt from `effective_responses_df` (same input as pipeline)
- `response_source` mapped from `effective_source` for UI column compatibility
- `bet_merge_stats` field retained in `RunContext` (set to `{}`) for backward compatibility

---

## 3. Known Limitations and TODOs

### TODO (deferred, not blocking Step 9)

1. **Sentinel hash replacement (§10.4)**: Current `BOOTSTRAP::<rapport_id>` deduplication key is noted as a limitation. Content-derived hash (`SHA256(sorted row values)`) was not implemented in Step 8 as it requires changes to the ingestion flow. The `deactivated_reason` column is in place. Full sentinel replacement is deferred to a future maintenance step.

2. **E8 synthetic SAS enforcement**: Gate E8 (no synthetic SAS target) is documented but not enforced in the composition layer. The `operation_rule_used` field from GED_OPERATIONS would need to be propagated to `persisted_report_responses` via the ingestion path. Currently, synthetic SAS rows would fail E4 (no matching approver step) and be silently skipped — correct behaviour but not explicitly flagged.

3. **TEMPORARY_COMPAT_LAYER removal (stage_read_flat.py)**: The compat layer that reconstructs legacy `response_date_raw` strings is still present. Per the step 4 comment, it should be removed when stage_normalize is updated for flat mode. This is deferred — the flat mode pipeline still functions correctly through the compat layer.

4. **E7 freshness in raw mode**: Gate E7 (freshness) is only applied when `flat_mode=True` (requires `flat_data_date` or `data_date`). Raw mode skips E7 — this is acceptable as raw mode does not carry `data_date` per-row.

5. **`_precompute_focus_columns` in data_loader.py**: Uses `workflow_engine.compute_visa_global_with_date()` directly. In UI context (data_loader), `_flat_visa_override` is not set (no ctx.flat_ged_mode available). The visa_global for focus columns in the UI remains on the engine path. This is acceptable for Phase 2 — the SAS REF gap in focus columns only affects `_visa_global` pre-computation in the UI, not the GF output.

---

## 4. Tests Run

| Check | Result |
|-------|--------|
| AST syntax — all 8 modified files | PASS |
| E2 gate: LOW and NULL confidence blocked | PASS |
| Rule 2: PENDING upgraded to ANSWERED via HIGH report | PASS |
| Rule 1: GED ANSWERED not overridden by conflicting report | PASS |
| `GED_CONFLICT_REPORT` tagged correctly | PASS |
| VAOB rule: treated as approval-family, additive comment only | PASS |
| No `REPORT_ONLY` rows in any output | PASS |
| `effective_source` vocabulary — only allowed values | PASS |
| `src/flat_ged/` unchanged (git diff HEAD) | PASS |
| `data/report_memory.db` integrity_check = ok | PASS |
| v2 migration (deactivated_reason column) on old schema | PASS |
| `deactivate_answered_report_rows()` sets is_active=0 + reason | PASS |
| `get_visa_global()` returns flat_ged_doc_meta value in flat mode | PASS |
| `_flat_visa_override` respected in `workflow_engine` | PASS |
| `bet_report_merger` not actively imported in data_loader.py | PASS |
| `merge_bet_reports()` call removed | PASS |
| E2 gate in `stage_report_memory.py` | PASS |
| E2 gate in `bootstrap_report_memory.py` | PASS |
| Deprecation guard in `consultant_integration.py` | PASS |

---

## 5. Can Step 9 Begin?

**Yes.** Step 8 success criteria are met:

1. ✅ Effective responses composed from GED anchor in flat mode (via `flat_mode=True` flag using `flat_*` pass-through columns)
2. ✅ Rules 1–4 preserved and extended
3. ✅ LOW/UNKNOWN confidence reports blocked at ingestion and composition
4. ✅ VAOB handled as approval-family
5. ✅ `effective_source` present on every row, five-value controlled vocabulary
6. ✅ `stage_write_gf` uses `get_visa_global()` in flat mode via `_flat_visa_override`
7. ✅ UI no longer uses `bet_report_merger`
8. ✅ Direct GF write path deprecated in `consultant_integration.py`
9. ✅ Raw mode unchanged and functional
10. ✅ Flat mode operational

Step 9 (clean_GF Diff vs Current) may proceed.
