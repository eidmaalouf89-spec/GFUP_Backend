#repo-map #persistence #memory #database

# Persistence: Run and Report Memory

> The two SQLite databases that give the system its cross-run memory.
> See [[12_DONT_TOUCH_WITHOUT_EXPLICIT_SCOPE]] for protection rules.

---

## Overview

| Database | File | What it holds | Risk if deleted |
|---|---|---|---|
| `run_memory.db` | `data/run_memory.db` | Artifact registry — sha256-verified record of every run and every output artifact | All cross-run artifact claims in UI become invalid; inheriting GF from previous runs breaks |
| `report_memory.db` | `data/report_memory.db` | Persistent consultant truth — 1,245+ active rows of matched consultant responses | All consultant-level intelligence is lost; re-import from PDFs required (slow, error-prone) |

Both are SQLite. Both live in `data/`. Neither should be deleted casually.

---

## run_memory.db

**Module:** `src/run_memory.py`

**Schema tables:** `runs`, `run_inputs`, `run_artifacts`, `run_corrections`, `run_invalidation_log`

**Purpose:**
- Records every pipeline execution with a `run_number`, `status`, timestamps
- Records every output artifact with its file path, `artifact_type`, sha256 hash
- The UI's `data_loader.py` resolves the latest COMPLETED run and its artifact paths from here
- `stage_finalize_run.py` writes all artifact rows; `mark_run_current` is called at the end

**Key behaviors:**
- If `stage_finalize_run` fails mid-registration, the run row stays `STARTED` → `orchestrator.finalize_run_failure` marks it FAILED
- Schema changes require explicit migration plans — there is NO automatic migration
- `journal_mode = DELETE` (switched from WAL in Phase 9A.6 as defensive hardening against FUSE/SQLite issues)
- Bootstrap script if it needs to be rebuilt: `scripts/bootstrap_run_zero.py`

**Current state:** holds Run 0 as the immutable baseline. Subsequent runs increment `run_number`.

---

## report_memory.db

**Module:** `src/report_memory.py`

**Purpose:**
- Persists consultant answer truth from PDF/XLSX reports across runs
- Holds 1,245+ active rows (as of README 2026-05-01)
- Once matched, a consultant answer survives all future GED rebuilds without re-importing reports
- Confidence gate: only HIGH and MEDIUM matches are ingested (enforced in `stage_report_memory.py::_ELIGIBLE_CONFIDENCE_VALUES`)

**Key behaviors:**
- Ingested via `stage_report_memory.py` during pipeline run (when `consultant_reports/` are provided)
- Also accessed directly by `src/chain_onion/source_loader.py` (reads effective_responses indirectly)
- NOT protected by sha256 — it accumulates row-by-row
- Bootstrap script if it needs to be rebuilt: `scripts/bootstrap_report_memory.py` (starts from empty)

**Do not lower the confidence gate (HIGH/MEDIUM only).** LOW-confidence matches are excluded — accepting them risks polluting the consultant truth with incorrect associations.

---

## How report truth survives future runs

```
PDF reports (input/consultant_reports/)
        │
        ▼
consultant_integration.run_consultant_integration()
  STEP A–E: load/rebuild consultant_reports.xlsx, match to GED universe
  STEP F: build enrichment records (HIGH/MEDIUM only)
        │
        ▼
output/consultant_match_report.xlsx
        │
        ▼ (ingested in stage_report_memory)
data/report_memory.db  ←── persisted across runs
        │
        ▼ (loaded every run by stage_report_memory)
effective_responses_df  ←── composed at runtime
```

Once a consultant answer is persisted in `report_memory.db`:
- It survives even if the user doesn't provide reports on the next run
- It enriches `effective_responses_df` via `effective_responses.build_effective_responses`
- It is LEFT-anchored on GED rows (cannot inject brand-new workflow rows)

---

## run_memory.db artifact resolution (UI path)

```python
# data_loader.py
load_run_context(BASE_DIR)
  → queries run_memory.db: SELECT latest COMPLETED run
  → reads run_artifacts for that run_number
  → resolves artifact_type="FLAT_GED" → path
  → checks pickle cache freshness (schema version + mtime)
  → returns RunContext
```

The UI always reads the **latest completed** run. There is no UI mechanism to select a specific historical run for the main dashboard (the Runs page shows history but doesn't switch the active context).

---

## runs/run_0000/ — immutable baseline

`runs/run_0000/` is the immutable baseline created from the initial clean run.
- `scripts/nuke_and_rebuild_run0.py` and `scripts/reset_to_clean_run0.py` are the only scripts allowed to mutate it
- Manual editing breaks sha256 verification on the next run
- Run 0 baseline metrics (from `docs/VALIDATION_BASELINE.md`): `docs_total=6491`, `responses_total=31586`, `final_gf_rows=4728`, `artifacts_registered_count=30`, `consultant_report_memory_rows_loaded=1245`

---

## SQLite safety rules (from context/11_TOOLING_HAZARDS.md §H-7)

1. Do not declare a SQLite DB "corrupt" from sandbox-side reads alone — the FUSE mount can make a healthy DB look malformed
2. `app.py::_query_db` uses `mode=ro&immutable=1` URI fallback — safe under all conditions
3. New diagnostic tools that read SQLite must mirror this immutable-mode fallback pattern

---

*Back to [[00_START_HERE]]*
