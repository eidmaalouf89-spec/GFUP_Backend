# BUILD_SOURCE.md — Flat GED Frozen Snapshot

This directory (`src/flat_ged/`) is a **frozen vendor snapshot** of the
`ged_flat_builder` package. It is not an editable copy. All business logic
is owned by the upstream builder.

---

## How to re-sync from upstream

If the upstream builder is updated (bug fix, new rule), re-sync by:

1. **Fix upstream first.** Apply the change in `GED_FLAT_Builder/ged_flat_builder/`.
2. **Copy changed files** verbatim into `src/flat_ged/`, preserving file names.
   - `main.py` (upstream) → `cli.py` (this snapshot). Keep the rename.
   - `input/source_main/*.py` → `src/flat_ged/input/source_main/*.py`.
3. **Do NOT copy** `__pycache__/`, `output/`, or the `input/GED_export.xlsx` data file.
4. Update `VERSION.txt`:
   - `source_commit` — record the upstream git SHA (or "manual-YYYY-MM-DD" if no git).
   - `snapshot_date` — today.
   - `contract_version` — bump only if `docs/FLAT_GED_CONTRACT.md` is also updated.
5. Run the smoke test: `pytest tests/flat_ged/test_smoke.py`
6. If the contract changes, update `docs/FLAT_GED_CONTRACT.md` and bump the version there.

---

## Files that must NOT be edited in this snapshot

| File / folder | Reason |
|---|---|
| `config.py` | Business constants and vocabulary. Change upstream only. |
| `resolver.py` | Candidate selection logic. Frozen. |
| `transformer.py` | Core GED row transformation. Frozen. |
| `validator.py` | Delay invariant checks. Frozen. |
| `utils.py` | Pure helpers. Frozen. |
| `input/source_main/` | Extracted from backend — change upstream only. |

---

## Permitted local-only edits (this snapshot only)

| File | Permitted change |
|---|---|
| `__init__.py` | Import path fixes; expose `build_flat_ged()` public API. |
| `cli.py` | Import path fixes only. No logic changes. |
| `reader.py` | File-path handling adjustments for package context only. |

**No other local edits are permitted.** If you find yourself editing
`transformer.py` or `resolver.py` here, stop — fix it upstream and re-sync.

---

## Why `input/source_main/` is included

`config.py` resolves the source_main reference layer at runtime via:

```python
_SOURCE_MAIN = Path(__file__).parent / "input" / "source_main"
```

To avoid editing `config.py`, the `source_main` Python files are placed at
`src/flat_ged/input/source_main/`. This is the only structural accommodation
made during vendoring. The data file (`GED_export.xlsx`) is **not** included.

---

## What goes in the adapter, not here

Any field mapping, gap-filling, or semantic bridging between flat GED output
and the backend pipeline belongs in:

```
src/pipeline/stages/stage_read_flat.py
```

See `docs/FLAT_GED_ADAPTER_MAP.md` (Step 4) for the field-by-field mapping.
