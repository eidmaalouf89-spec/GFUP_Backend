# CLEAN Step 11 — UI Artifact Loader Implementation Notes

**Date:** 2026-04-26
**Status:** DONE

---

## Files Changed

| File | Change |
|------|--------|
| `src/reporting/data_loader.py` | Added `_load_from_flat_artifacts()`, rewired `load_run_context()` default path |
| `app.py` | No change — `export_team_version()` already present from Step 9b |

## Files Created

| File | Purpose |
|------|---------|
| `docs/STEP11_UI_ARTIFACT_LOADER_NOTES.md` | This document |

---

## Loader Order — Before vs After

### Before (Steps 1–10)

```
load_run_context()
  → resolve latest run from run_memory.db
  → verify raw GED provenance (hash check)
  → read_ged() → normalize_docs/responses → VersionEngine → WorkflowEngine
  → report memory composition (effective_responses)
  → focus columns
  → return RunContext
```

Always rebuilt from raw GED on every cache miss. Slow, no artifact reuse.

### After (Step 11)

```
load_run_context()
  → resolve latest run from run_memory.db
  → collect artifact paths (relocation-aware)
  → TRY: _load_from_flat_artifacts()
      → look up FLAT_GED artifact in run_memory.db
      → call stage_read_flat() to parse FLAT_GED.xlsx
      → normalize_docs + normalize_responses
      → skip VersionEngine (flat GED = all ACTIVE = all dernier)
      → WorkflowEngine + responsible parties
      → report memory composition (effective_responses)
      → focus columns + ownership
      → return RunContext    ← DEFAULT PRODUCT PATH
  → FALLBACK: legacy raw GED rebuild
      → [LEGACY_RAW_FALLBACK] warning logged
      → same as Before path
      → return RunContext    ← ONLY IF FLAT_GED MISSING
```

---

## Artifact Types Consumed

| Artifact Type | Usage | Required? |
|---------------|-------|-----------|
| `FLAT_GED` | Primary data source for artifact-first path | Yes (for artifact path) |
| `FLAT_GED_RUN_REPORT` | Available in artifact_paths; not directly parsed by loader | No |
| `FINAL_GF` | GF sheet structure parsing | Optional |
| `GF_TEAM_VERSION` | Used by `export_team_version()` in app.py | Optional |

---

## bet_report_merger Status

**Not used.** Already retired before Step 11 (Step 8 / FLAT_GED_REPORT_COMPOSITION.md §8). The import is commented out with `DO NOT RESTORE` marker. Both artifact-first and legacy paths use `build_effective_responses()` from the pipeline composition engine instead.

---

## export_team_version() Behavior

Already implemented in `app.py` Api class (added during Step 9b/9c, not Step 11). Behavior:

1. Load latest RunContext via `load_run_context()`
2. Look up `GF_TEAM_VERSION` in `ctx.artifact_paths`
3. Fallback: query `_get_artifact_path()` directly from run_memory.db
4. If found: copy to `output/Tableau de suivi de visa DD_MM_YYYY.xlsx`
5. If missing: return `{"success": False, "error": "..."}`

Date format uses `ctx.data_date` if available, otherwise today's date.

---

## Fallback Behavior

The legacy raw GED rebuild path is preserved but clearly marked:

- Guarded by `[LEGACY_RAW_FALLBACK]` log warning
- Only executes when `_load_from_flat_artifacts()` returns None
- Two failure cases trigger fallback:
  1. No `FLAT_GED` artifact registered for the run
  2. Exception during flat artifact loading (logged as `[FLAT_ARTIFACT] Failed: ...`)
- The legacy path is identical to the pre-Step 11 behavior

---

## VersionEngine Skip

In the artifact-first path, VersionEngine is **not run**. Rationale:

- Flat GED only contains ACTIVE submission instances (FLAT_GED_CONTRACT §Known Limitation)
- Every (numero, indice) pair in FLAT_GED is by definition the latest version
- `docs_df["is_dernier_indice"] = True` is set directly
- `dernier_df = docs_df.copy()` — all docs are dernier
- No UI code uses VersionEngine columns beyond `is_dernier_indice` (verified by grep)

The legacy fallback still runs VersionEngine for raw GED compatibility.

---

## Known Limitations

1. **Run 1 (and older runs)** have no FLAT_GED artifact — they always use the legacy fallback. This is expected and correct.
2. **data_date** in artifact-first path comes from `flat_ged_doc_meta` (ISO date string parsed from GED_OPERATIONS), not from the raw GED Détails sheet. Values should be identical.
3. **Report memory** composition depends on `report_memory.db` being accessible. If unavailable, responses_df uses GED-only data (non-fatal).
4. **visa_global** in focus columns uses `WorkflowEngine.compute_visa_global_with_date()` which may return (None, None) for SAS REF docs in flat mode. The `stage_read_flat` docstring documents this as a known gap — `get_visa_global(ctx, doc_id, engine)` is the authoritative accessor for pipeline stages, but the UI's `_precompute_focus_columns` still uses the engine directly.
