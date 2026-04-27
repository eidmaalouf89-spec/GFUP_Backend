# GF Updater V3 — RC1 Release Notes

## 1. Release Identity

- **Release:** GF Updater V3 — RC1
- **Release date:** 2026-04-27
- **Project:** 17&CO Tranche 2
- **Scope:** local, single-user, single-project operational engine
- **Frozen on:** Clean Run 0 baseline (after CLEAN Step 17A reset)

---

## 2. Final Verdict

**RC1 READY**

Repo is frozen as the RC1 baseline. The pipeline produces a clean, validated Run 0 from a fresh state, and the artifact-first UI loads it without degradation.

---

## 3. Validated Baseline

- **Clean Run 0 only** — all polluted runs (1–11) wiped before RC1 was declared.
- **Run 0 status:** `COMPLETED`
- **Run 0 DB row:** `(0, 'COMPLETED', None)`
- **Total artifacts registered:** 33
- **Required artifacts (all present):**
  - `FLAT_GED`
  - `FLAT_GED_RUN_REPORT`
  - `FLAT_GED_DEBUG_TRACE`
  - `FINAL_GF`
  - `GF_TEAM_VERSION`
- **UI loader smoke:** last non-empty stdout line = `0 False True` (artifact-first load, not degraded mode, FLAT_GED artifact path resolved).

---

## 4. What RC1 Does

- reads the GED export (`input/GED_export.xlsx`)
- auto-builds **Flat GED** into `output/intermediate/FLAT_GED.xlsx` on every run
- reconstructs a clean **Grand Fichier** (`output/GF_V0_CLEAN.xlsx`)
- integrates **`report_memory.db`** (consultant truth, persistent across runs)
- generates **`GF_TEAM_VERSION.xlsx`** with retry + fallback
- registers run artifacts in **`run_memory.db`** with hash + lineage
- powers the **artifact-first UI** (JANSA connected) — loads artifacts directly from the run history, no raw rebuild required
- exports **Tableau de suivi de visa** and other operational deliverables from the UI

---

## 5. User Workflow

1. Place `GED_export.xlsx` in `input/`
2. Place `Grandfichier_v3.xlsx` in `input/` (optional — inherited from run history if absent)
3. Place consultant report PDFs in `input/consultant_reports/` (optional)
4. Run the pipeline:
   ```bat
   python main.py
   ```
5. Launch the desktop UI:
   ```bat
   python app.py
   ```
6. Use UI exports (Tableau de suivi de visa, drilldowns, consultant fiches, …)

---

## 6. Protected Assets

These must not be regenerated, deleted, or overwritten without explicit ceremony:

- `src/flat_ged/` — frozen builder (FGIC contract v1.0)
- `data/report_memory.db` — persistent consultant truth across runs
- `data/run_memory.db` — RC1 baseline run history (only Run 0 present)
- `runs/run_0000/` — Run 0 artifact tree (immutable baseline)
- `ui/jansa-connected.html` — production UI entrypoint
- `ui/jansa/` — JANSA UI assets

---

## 7. Known Minor Limitations

- `FLAT_GED_MODE` default in `src/pipeline/paths.py` remains `"raw"`, but `src/run_orchestrator.py` overrides to `"flat"` before each run. (Cosmetic asymmetry; functional behavior is consistent.)
- Legacy raw-fallback code path still exists in the loader; logged as `[LEGACY_RAW_FALLBACK]` when triggered. Not required for RC1 operation.
- `openpyxl` emits date-format warnings during reads; non-blocking, no functional impact.
- **Chain + Onion** (next phase) is **not started**; only unlocked.
- The reset script's UI-loader smoke validator was patched in Step 17B *after* a false-fail caused by an info line on stdout (`[1/7] Reading FLAT_GED (flat mode)...`) preceding the smoke `print(...)`. The functional run was correct on the first attempt; only the validator string match was too strict.

---

## 8. Final Scores

| Dimension | Score |
|-----------|-------|
| Runtime stability | 9/10 |
| Repo cleanliness | 9/10 |
| Product readiness | 9/10 |

---

## 9. Next Phase

**Chain + Onion** (Phase 6) can begin **after RC1 freeze**. RC1 is the immutable baseline that Phase 6 will derive from. Do not start Chain + Onion work without an explicit "begin Phase 6" handoff and the corresponding gate (Gate 4) opened.

---

## 10. Verification Pointers

For anyone re-validating RC1 from a clean checkout:

```bat
cd /d "C:\Users\GEMO 050224\Desktop\cursor\GF updater v3"

python -m py_compile scripts\reset_to_clean_run0.py app.py main.py src\run_orchestrator.py src\reporting\data_loader.py src\run_memory.py

python -c "import sqlite3; c=sqlite3.connect(r'data\run_memory.db'); print(c.execute('SELECT run_number,status,error_message FROM runs ORDER BY run_number').fetchall()); print(c.execute('SELECT COUNT(*) FROM run_artifacts WHERE run_number=0').fetchone())"
```

Expected:

```
[(0, 'COMPLETED', None)]
(33,)
```
