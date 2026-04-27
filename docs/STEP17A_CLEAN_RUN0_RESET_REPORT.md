# CLEAN Step 17A — Clean Run 0 Reset Report

**Status:** ✅ DONE / PASS
**Date prepared:** 2026-04-27 (worktree)
**Date executed:** 2026-04-27 (main repo)
**Branch / worktree:** `claude/interesting-hopper-ee96ab` (worktree at `.claude/worktrees/interesting-hopper-ee96ab/`)
**Author:** Claude Code

> **Note on initial FAIL exit:**
> The first execution exited with code `4` solely because the UI loader smoke validator compared full stdout against `"0 False True"`. The actual rebuild was functionally correct — the smoke `print(...)` was preceded by an info line emitted by `stage_read_flat`:
>
> ```
> [1/7] Reading FLAT_GED (flat mode)...
> 0 False True
> ```
>
> The validator was patched in Step 17B to match the **last non-empty stdout line** rather than the full buffer. No destructive rerun was required. All Run 0 state, artifacts, and filesystem layout were correct on the first run.

---

## Execution facts (main repo)

| Field | Value |
|------|-------|
| Backup location | `backup/pre_rc1_run_history_20260427_1059/` |
| Items deleted | `data/run_memory.db`, `runs/` (entire tree) |
| Items preserved | `data/report_memory.db`, `input/GED_export.xlsx`, `input/Grandfichier_v3.xlsx`, `input/consultant_reports/` |
| Rebuild command | `python scripts/reset_to_clean_run0.py` |
| Run 0 DB row | `(0, 'COMPLETED', None)` |
| Total artifacts registered (Run 0) | **33** |
| Required artifacts present | `FLAT_GED`, `FLAT_GED_RUN_REPORT`, `FLAT_GED_DEBUG_TRACE`, `FINAL_GF`, `GF_TEAM_VERSION` |
| Files on disk | `output/GF_V0_CLEAN.xlsx`, `output/GF_TEAM_VERSION.xlsx`, `output/intermediate/FLAT_GED.xlsx`, `output/intermediate/flat_ged_run_report.json`, `output/intermediate/DEBUG_TRACE.csv`, `runs/run_0000/` |
| UI loader smoke | **PASS** — last non-empty stdout line = `0 False True` |
| RC1 freeze can proceed | **YES** |

---

## Why the worktree didn't execute the reset

The targets — `data/run_memory.db`, `runs/`, `output/` — are gitignored and live only in the main project directory at `C:\Users\GEMO 050224\Desktop\cursor\GF updater v3`. They do not exist inside the Claude Code worktree.

**Decision (user, Option A):** Claude Code prepared the script + docs in the worktree only; the user executed the reset manually in the main repo.

---

## Deliverables

| File (worktree path) | Purpose | Status |
|------|---------|--------|
| `scripts/reset_to_clean_run0.py` | Reset orchestrator: backup → wipe → rebuild via `python main.py` → validate | Created (17A), patched (17B) |
| `docs/STEP17A_CLEAN_RUN0_RESET_REPORT.md` | This report | Updated to PASS (17B) |
| `docs/RC1_RELEASE_NOTES.md` | RC1 release notes | Created (17B) |
| `docs/RC1_README_INSERT.md` | README snippet for main repo | Created (17B) |
| `GFUP_STEP_TRACKER.md` | Patch fragment for master tracker (17A + 17B entries) | Updated (17B) |

No business logic, no `src/`, no `ui/`, no pipeline stage was touched at any point.

---

## Script behavior summary (`scripts/reset_to_clean_run0.py`)

Five phases:

1. **Backup** → `backup/pre_rc1_run_history_<TS>/` (DB, runs/, key intermediates)
2. **Destructive delete** → removes `data/run_memory.db` (+ `-wal`/`-shm`/`-journal`), removes `runs/`, recreates empty `runs/`
3. **Rebuild** → `python main.py`
4. **Validate**
   - DB: exactly one run, `run_number=0`, `status='COMPLETED'`, `error_message IS NULL`
   - Artifacts: required types registered (`FLAT_GED`, `FLAT_GED_RUN_REPORT`, `FINAL_GF`, `GF_TEAM_VERSION`); soft-check `FLAT_GED_DEBUG_TRACE`
   - Filesystem: `runs/run_0000/`, intermediates, primary outputs
   - UI loader smoke: last non-empty stdout line == `"0 False True"`
5. **Summary**

Hard rules respected — no `src/`, `ui/`, `docs/`, or business-logic changes; `data/report_memory.db` and `input/*` preserved; backup before delete; interactive `RESET` confirm with `--yes` override.

---

## Step 17B validator patch (applied to `validate_ui_loader`)

Diff (conceptual):

- Before: `if out == expected:` — compared full stdout buffer.
- After: extract `last_line = next((ln.strip() for ln in reversed(out.splitlines()) if ln.strip()), "")`, then `if last_line == expected:`.

This accommodates pipeline-stage info lines emitted to stdout before the smoke `print(...)` call (e.g. `stage_read_flat`'s `[1/7] Reading FLAT_GED (flat mode)...`).

Compile check: `python -m py_compile scripts/reset_to_clean_run0.py` → `OK`.

No runtime code was changed. No destructive operation was rerun.

---

## RC1 freeze gate

| Gate | State |
|------|-------|
| Step 17A script prepared | ✅ |
| Step 17A executed in main repo | ✅ |
| Step 17A validation passed (functional) | ✅ |
| Step 17B validator patched | ✅ |
| Step 17B docs prepared | ✅ |
| Step 17B RC1 Freeze can begin | ✅ — proceed to RC1 release notes |
