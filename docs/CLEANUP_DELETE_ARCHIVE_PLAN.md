# CLEANUP DELETE / ARCHIVE PLAN
## Step 13 — Forensic Cleanup Audit

**Date:** 2026-04-26  
**Step:** CLEAN Step 13  
**Status:** ✅ AUDIT COMPLETE — Awaiting Step 14 execution  
**Repo root:** `GF updater v3/` (also mounted as workspace `GFUP CLEAN BASE + CLEAN IO`)

---

## SECTION A — REPO SCAN RESULTS

### Root-Level Files Found

| File | Classification |
|---|---|
| `app.py` | KEEP_ACTIVE |
| `main.py` | KEEP_ACTIVE |
| `README.md` | KEEP_ACTIVE |
| `.gitignore` | KEEP_ACTIVE |
| `COWORK_PATCH_consultant_fiche_bugs.md` | ARCHIVE_NOW |
| `GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md` | ARCHIVE_NOW |
| `JANSA Dashboard - Standalone.html` | ARCHIVE_NOW |
| `package-lock.json` (root) | DELETE_NOW |

### Root-Level Folders Found

| Folder | Classification |
|---|---|
| `src/` | KEEP_ACTIVE |
| `docs/` | KEEP_ACTIVE (mixed — see below) |
| `scripts/` | KEEP_ACTIVE (mixed — see below) |
| `ui/` | KEEP_ACTIVE (mixed — see below) |
| `data/` | KEEP_ACTIVE |
| `runs/` | KEEP_ACTIVE (gitignored, runtime artifacts) |
| `output/` | KEEP_ACTIVE (gitignored, runtime artifacts) |
| `input/` | KEEP_ACTIVE (gitignored, source data) |
| `tests/` | KEEP_ACTIVE |
| `codex prompts/` | ARCHIVE_NOW |
| `.claude/` | KEEP_ACTIVE base, worktrees DELETE_NOW |
| `.claude/worktrees/` | DELETE_NOW (via `git worktree remove`) |

---

## SECTION B — FULL FILE CLASSIFICATION

### src/ — ALL KEEP_ACTIVE

All 30+ runtime production files. No deletions.

Key files confirmed:
- `src/run_orchestrator.py` — KEEP_ACTIVE
- `src/flat_ged_runner.py` — KEEP_ACTIVE
- `src/pipeline/paths.py` — KEEP_ACTIVE (single path source of truth)
- `src/pipeline/runner.py` — KEEP_ACTIVE
- `src/pipeline/context.py` — KEEP_ACTIVE
- `src/pipeline/stages/stage_build_team_version.py` — KEEP_ACTIVE
- `src/pipeline/stages/stage_read_flat.py` — KEEP_ACTIVE
- `src/pipeline/stages/stage_write_gf.py` — KEEP_ACTIVE
- `src/pipeline/stages/stage_report_memory.py` — KEEP_ACTIVE
- `src/pipeline/stages/stage_finalize_run.py` — KEEP_ACTIVE
- `src/reporting/data_loader.py` — KEEP_ACTIVE
- `src/reporting/aggregator.py` — KEEP_ACTIVE
- `src/reporting/focus_filter.py` — KEEP_ACTIVE
- `src/reporting/ui_adapter.py` — KEEP_ACTIVE
- `src/flat_ged/` (entire frozen snapshot) — KEEP_ACTIVE (FROZEN, DO NOT MODIFY)
- `src/workflow_engine.py` — KEEP_ACTIVE
- `src/version_engine.py` — KEEP_ACTIVE
- `src/run_memory.py` — KEEP_ACTIVE
- `src/report_memory.py` — KEEP_ACTIVE
- `src/effective_responses.py` — KEEP_ACTIVE
- `src/query_library.py` — KEEP_ACTIVE
- All other src/ modules — KEEP_ACTIVE

### docs/ — 18 files, mixed

| File | Classification | Reason |
|---|---|---|
| `docs/ARCHITECTURE.md` | KEEP_ACTIVE | Step 3 canonical architecture doc |
| `docs/CLEAN_IO_CONTRACT.md` | KEEP_ACTIVE | Step 4 IO contract |
| `docs/CLEAN_INPUT_OUTPUT_TARGET.md` | KEEP_ACTIVE | Step 4 folder contract |
| `docs/FLAT_BUILDER_INTEGRATION_AUDIT.md` | KEEP_ACTIVE | Step 5 builder audit |
| `docs/UI_LOADER_PRODUCTIZATION_AUDIT.md` | KEEP_ACTIVE | Step 10 UI audit |
| `docs/TEAM_GF_PRESERVATION_AUDIT.md` | KEEP_ACTIVE | Step 9 TEAM_GF audit |
| `docs/UI_SOURCE_OF_TRUTH_MAP.md` | KEEP_ACTIVE | Runtime reference |
| `docs/QUERY_LIBRARY_SPEC.md` | KEEP_ACTIVE | Runtime reference |
| `docs/FLAT_GED_REPORT_COMPOSITION.md` | KEEP_ACTIVE | Runtime reference |
| `docs/UI_RUNTIME_ARCHITECTURE.md` | KEEP_ACTIVE | Runtime reference |
| `docs/CLAUDE.md` | KEEP_REFERENCE | AI behavior guidelines for this repo |
| `docs/CODEX.md` | KEEP_REFERENCE | Conservative code review instructions |
| `docs/DEVELOPMENT_RULES.md` | KEEP_REFERENCE | Development guidelines |
| `docs/REPORTS_INGESTION_AUDIT.md` | KEEP_REFERENCE | Historical audit, useful background |
| `docs/STEP7_IMPLEMENTATION_NOTES.md` | ARCHIVE_NOW → `archive/step_logs/` | Implementation log, superseded |
| `docs/STEP8_IMPLEMENTATION_NOTES.md` | ARCHIVE_NOW → `archive/step_logs/` | Implementation log (old pipeline v2) |
| `docs/STEP8_CLEAN_IMPLEMENTATION_NOTES.md` | ARCHIVE_NOW → `archive/step_logs/` | Implementation log (CLEAN track) |
| `docs/CLEAN_GF_DIFF_SUMMARY.md` | ARCHIVE_NOW → `archive/validation_history/` | Step 9 validation result, historical |

### scripts/ — 7 files, mixed

| File | Classification | Reason |
|---|---|---|
| `scripts/repo_health_check.py` | KEEP_ACTIVE | Step 1 health tool, still valid for periodic runs |
| `scripts/bootstrap_run_zero.py` | KEEP_REFERENCE | Baseline setup utility |
| `scripts/bootstrap_report_memory.py` | KEEP_REFERENCE | Report memory init utility |
| `scripts/parity_harness.py` | ARCHIVE_NOW → `archive/dev_tools/` | Step 5c reclassifier, hard-coded old session path, dead |
| `scripts/clean_gf_diff.py` | ARCHIVE_NOW → `archive/dev_tools/` | Step 9 diff tool, validation done, no longer needed |
| `scripts/ui_parity_harness.py` | ARCHIVE_NOW → `archive/dev_tools/` | Step 11 parity harness, validation done |
| `scripts/_run_one_mode.py` | ARCHIVE_NOW → `archive/dev_tools/` | Helper for clean_gf_diff.py — orphaned if clean_gf_diff archived |

### ui/ — mixed

| Path | Classification | Reason |
|---|---|---|
| `ui/jansa-connected.html` | KEEP_ACTIVE | **Production UI entrypoint** — confirmed in app.py |
| `ui/README.md` | KEEP_REFERENCE | UI documentation |
| `ui/index.html` | DELETE_NOW | Legacy Vite entry, app.py does NOT reference it |
| `ui/package.json` | ARCHIVE_NOW → `archive/ui_legacy/` | Vite config, no longer needed |
| `ui/package-lock.json` | DELETE_NOW | Gitignored, no longer needed |
| `ui/src/` (entire folder) | DELETE_NOW | Old Vite/React source (App.jsx, main.jsx, etc.) — production uses jansa-connected.html |
| `ui/dist/` (entire folder) | DELETE_NOW | Built Vite output — NOT referenced by app.py, gitignored |
| `ui/node_modules/` (entire folder) | DELETE_NOW | Massive NPM tree for Vite, gitignored, no longer needed |

### codex prompts/ — ALL ARCHIVE_NOW

22 files total. All orphaned development prompt scratch files.

Archive destination: `docs/archive/prompts/`

Contents:
- `codex prompts/run0`
- `codex prompts/updatemds`
- `codex prompts/fullrepo_faclift`
- `codex prompts/UIchoice`
- `codex prompts/Step12corrections`
- `codex prompts/faceliftstep5v2`
- `codex prompts/facelift_step5.txt`
- `codex prompts/facelift/` (spec files, prototype JSX components, JANSA Dashboard.html prototype)

### Root-level docs (not in docs/)

| File | Classification | Reason |
|---|---|---|
| `COWORK_PATCH_consultant_fiche_bugs.md` | ARCHIVE_NOW → `archive/one_off_docs/` | Old patch tracking doc |
| `GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md` | ARCHIVE_NOW → `archive/old_specs/` | Superseded by docs/ARCHITECTURE.md |
| `JANSA Dashboard - Standalone.html` | ARCHIVE_NOW → `archive/ui_legacy/` | Old standalone dashboard, not connected to backend |

### .claude/worktrees/ — 6 STALE WORKTREES — DELETE_NOW

⚠️ **Must be removed via `git worktree remove`, NOT `rm -rf`.**

| Worktree | Classification |
|---|---|
| `.claude/worktrees/objective-kilby-52554c` | DELETE_NOW |
| `.claude/worktrees/dazzling-ardinghelli-6679ce` | DELETE_NOW |
| `.claude/worktrees/silly-agnesi-77b86d` | DELETE_NOW |
| `.claude/worktrees/blissful-hellman-c7e157` | DELETE_NOW |
| `.claude/worktrees/exciting-nobel-377a41` | DELETE_NOW |
| `.claude/worktrees/interesting-murdock-d39963` | DELETE_NOW |

Already in `.gitignore`. Not tracked by git. Safe to remove.  
Each worktree is a near-full copy of the repo. Total disk savings estimated at 500MB–2GB+.

### Root package-lock.json — DELETE_NOW

Empty lockfile (`"packages": {}`). Already covered by `.gitignore`. Delete directly.

---

## SECTION C — SPECIAL ATTENTION ITEMS INSPECTION

### 1. ui/src/
**Files:** App.jsx, index.css, main.jsx, components/ConsultantFiche.jsx, assets/vite.svg, assets/react.svg, App.css  
**Classification:** DELETE_NOW  
**Reason:** Legacy Vite/React source. Production UI is `ui/jansa-connected.html` (standalone HTML, no Vite build step). No Python file imports from ui/src/. Zero references found.

### 2. ui/dist/
**Files:** dist/index.html (Vite built output)  
**Classification:** DELETE_NOW  
**Reason:** Already in `.gitignore`. app.py does NOT reference `ui/dist`. `_resolve_ui()` in app.py only looks for `ui/jansa-connected.html`. Zero references found.

### 3. ui/index.html
**Classification:** DELETE_NOW  
**Reason:** Vite legacy entry point. `_resolve_ui()` in app.py only looks for `ui/jansa-connected.html`. Not imported or served anywhere.

### 4. ui/node_modules/
**Classification:** DELETE_NOW  
**Reason:** Already in `.gitignore`. Vite NPM dependencies. Huge tree. Not needed since production does not use a Vite build step.

### 5. JANSA Dashboard - Standalone.html
**Classification:** ARCHIVE_NOW → `archive/ui_legacy/`  
**Reason:** Old standalone dashboard prototype. Completely disconnected from backend. Historically useful as design reference.

### 6. codex prompts/
**Classification:** ARCHIVE_NOW → `docs/archive/prompts/`  
**Reason:** 22 orphaned dev prompt files from facelift planning, old codex steps, and one-off correction prompts. Not referenced by any code.

### 7. .claude/worktrees/
**Classification:** DELETE_NOW  
**Reason:** 6 stale Cowork worktrees, each a near-full snapshot of the repo. Already in `.gitignore`. Massive disk waste. Must be removed via `git worktree remove --force` (or `git worktree prune` if they have been abandoned).

### 8. scripts/parity_harness.py
**Classification:** ARCHIVE_NOW → `archive/dev_tools/`  
**Reason:** Step 5c BET EGIS reclassifier. Contains a hard-coded `/sessions/festive-lucid-carson/...` path (a stale Cowork session path). Completely dead. Cannot run without modification.

### 9. scripts/clean_gf_diff.py
**Classification:** ARCHIVE_NOW → `archive/dev_tools/`  
**Reason:** Step 9 flat vs raw pipeline diff tool. Validation complete. Not referenced anywhere.

### 10. scripts/ui_parity_harness.py
**Classification:** ARCHIVE_NOW → `archive/dev_tools/`  
**Reason:** Step 11 UI parity validation tool. Validation complete. Not referenced by runtime.

### 11. docs/STEP7_IMPLEMENTATION_NOTES.md, STEP8_*.md
**Classification:** ARCHIVE_NOW → `archive/step_logs/`  
**Reason:** Step implementation logs. Their work is now reflected in the live code. No longer needed as active docs. Good to keep as historical record.

### 12. docs/CLEAN_GF_DIFF_SUMMARY.md
**Classification:** ARCHIVE_NOW → `archive/validation_history/`  
**Reason:** Step 9 diff result. Historical validation artifact. Superseded by flat-first runtime.

### 13. Root-level COWORK_PATCH_consultant_fiche_bugs.md, GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md
**Classification:** ARCHIVE_NOW → `archive/one_off_docs/` and `archive/old_specs/`  
**Reason:** Stale patch docs and old architecture specs at root. Superseded by docs/ARCHITECTURE.md and the live codebase.

### 14. Root package-lock.json
**Classification:** DELETE_NOW  
**Reason:** Empty lockfile (`"packages": {}`). No dependencies listed. Gitignored. Safe to delete.

### 15. scripts/_run_one_mode.py
**Classification:** ARCHIVE_NOW → `archive/dev_tools/`  
**Reason:** Subprocess helper exclusively called by `scripts/clean_gf_diff.py`. Once clean_gf_diff is archived, this becomes an orphan. Archived together.

---

## SECTION D — STEP 14 EXECUTION PLAN

### Archive Bucket Structure

```
docs/archive/
├── ui_legacy/
│   ├── JANSA Dashboard - Standalone.html
│   ├── ui_package.json           (renamed from ui/package.json)
│   └── codex_prompts_facelift_prototype/  (JANSA Dashboard.html + jansa JSX components)
├── old_specs/
│   └── GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md
├── one_off_docs/
│   └── COWORK_PATCH_consultant_fiche_bugs.md
├── step_logs/
│   ├── STEP7_IMPLEMENTATION_NOTES.md
│   ├── STEP8_IMPLEMENTATION_NOTES.md
│   └── STEP8_CLEAN_IMPLEMENTATION_NOTES.md
├── validation_history/
│   └── CLEAN_GF_DIFF_SUMMARY.md
├── dev_tools/
│   ├── parity_harness.py
│   ├── clean_gf_diff.py
│   ├── ui_parity_harness.py
│   └── _run_one_mode.py
└── prompts/
    └── (all of codex prompts/ folder contents)
```

### DELETE Operations

```
DELETE:
  package-lock.json                  (root, empty lockfile)
  ui/index.html                      (Vite legacy entry)
  ui/package-lock.json               (Vite lockfile)
  ui/src/                            (entire folder — Vite React source)
  ui/dist/                           (entire folder — Vite built output)
  ui/node_modules/                   (entire folder — Vite NPM deps)

DELETE VIA GIT:
  (from repo root, run:)
  git worktree remove --force .claude/worktrees/objective-kilby-52554c
  git worktree remove --force .claude/worktrees/dazzling-ardinghelli-6679ce
  git worktree remove --force .claude/worktrees/silly-agnesi-77b86d
  git worktree remove --force .claude/worktrees/blissful-hellman-c7e157
  git worktree remove --force .claude/worktrees/exciting-nobel-377a41
  git worktree remove --force .claude/worktrees/interesting-murdock-d39963
  git worktree prune                 (clean up stale worktree refs)
```

### ARCHIVE Operations

```
ARCHIVE TO docs/archive/ui_legacy/:
  JANSA Dashboard - Standalone.html          (from root)
  ui/package.json                            (from ui/)

ARCHIVE TO docs/archive/old_specs/:
  GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md   (from root)

ARCHIVE TO docs/archive/one_off_docs/:
  COWORK_PATCH_consultant_fiche_bugs.md      (from root)

ARCHIVE TO docs/archive/step_logs/:
  docs/STEP7_IMPLEMENTATION_NOTES.md
  docs/STEP8_IMPLEMENTATION_NOTES.md
  docs/STEP8_CLEAN_IMPLEMENTATION_NOTES.md

ARCHIVE TO docs/archive/validation_history/:
  docs/CLEAN_GF_DIFF_SUMMARY.md

ARCHIVE TO docs/archive/dev_tools/:
  scripts/parity_harness.py
  scripts/clean_gf_diff.py
  scripts/ui_parity_harness.py
  scripts/_run_one_mode.py

ARCHIVE TO docs/archive/prompts/:
  codex prompts/                             (entire folder, all 22 files)
```

### KEEP (no action)

```
KEEP_ACTIVE:
  app.py
  main.py
  README.md
  .gitignore
  src/                               (all files)
  tests/
  data/                              (*.db files — NOT modified)
  runs/                              (runtime artifacts — NOT modified)
  output/                            (runtime artifacts — NOT modified)
  input/                             (source data — NOT modified)
  ui/jansa-connected.html
  scripts/repo_health_check.py
  docs/ARCHITECTURE.md
  docs/CLEAN_IO_CONTRACT.md
  docs/CLEAN_INPUT_OUTPUT_TARGET.md
  docs/FLAT_BUILDER_INTEGRATION_AUDIT.md
  docs/UI_LOADER_PRODUCTIZATION_AUDIT.md
  docs/TEAM_GF_PRESERVATION_AUDIT.md
  docs/UI_SOURCE_OF_TRUTH_MAP.md
  docs/QUERY_LIBRARY_SPEC.md
  docs/FLAT_GED_REPORT_COMPOSITION.md
  docs/UI_RUNTIME_ARCHITECTURE.md

KEEP_REFERENCE:
  ui/README.md
  scripts/bootstrap_run_zero.py
  scripts/bootstrap_report_memory.py
  docs/CLAUDE.md
  docs/CODEX.md
  docs/DEVELOPMENT_RULES.md
  docs/REPORTS_INGESTION_AUDIT.md
```

---

## SECTION E — RISK CHECK

| Item | Still Referenced? | Safe to Remove? | Notes |
|---|---|---|---|
| `ui/dist/index.html` | **NO** — not in app.py, not in any `.py` | ✅ YES | Confirmed: app.py uses only `ui/jansa-connected.html` |
| `ui/index.html` | **NO** — not in app.py, not in any `.py` | ✅ YES | `_resolve_ui()` confirmed: only checks `ui/jansa-connected.html` |
| `ui/src/` | **NO** — no Python file imports from here | ✅ YES | Production is standalone HTML; no Vite dependency |
| `ui/node_modules/` | **NO** — not imported or referenced | ✅ YES | Already in `.gitignore`; build step not used in production |
| `scripts/parity_harness.py` | **NO** — no import found | ✅ YES | Also has dead hard-coded Cowork session path |
| `scripts/clean_gf_diff.py` | **NO** — standalone script, not imported | ✅ YES | Calls `_run_one_mode.py` as subprocess but both are archived together |
| `scripts/ui_parity_harness.py` | **NO** — standalone script, not imported | ✅ YES | No production dependency |
| `scripts/_run_one_mode.py` | **ONLY** by `clean_gf_diff.py` (archived) | ✅ YES | Archive both together |
| `.claude/worktrees/` | **NO** — gitignored, not tracked | ✅ YES | Use `git worktree remove --force` not `rm -rf` |
| `GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md` | **NO** — not referenced by code | ✅ YES | Superseded by `docs/ARCHITECTURE.md` |
| `codex prompts/` | **NO** — not referenced by code | ✅ YES | `.gitignore` partially covers this folder |
| `package-lock.json` (root) | **NO** — empty packages | ✅ YES | `"packages": {}` — completely empty |

**No false-positive risks found.** All items classified DELETE_NOW are confirmed unreferenced.

---

## SECTION F — FINAL OUTPUT

### Summary Statistics

| Metric | Value |
|---|---|
| Files scanned (excl. node_modules, runs, output, input/reports) | ~300+ |
| Cleanup score BEFORE Step 14 | **4 / 10** |
| DELETE_NOW items (files + folders) | **11** |
| Worktrees to remove via git | **6** |
| ARCHIVE_NOW items | **~38 files** across 6 archive buckets |
| KEEP_ACTIVE | **~55 files** |
| KEEP_REFERENCE | **~8 files** |

### Cleanup Score Breakdown (Before Step 14)

Deductions from 10:
- `.claude/worktrees/` (6 full repo copies on disk): **−2**
- `ui/node_modules/` (massive NPM tree, gitignored but on disk): **−1**
- `ui/dist/`, `ui/src/`, `ui/index.html` (dead Vite artifacts): **−1**
- `codex prompts/` (22 orphaned dev prompts at root): **−0.5**
- Stale parity/validation scripts in scripts/: **−0.5**
- Root-level docs clutter (COWORK_PATCH, GFUP_SPEC, standalone HTML): **−0.5**
- Step implementation logs in docs/ (not archived yet): **−0.5**

**Score: 4/10 → Expected 9.5/10 after Step 14**

### Top 10 Highest-Value Cleanup Wins

1. **`.claude/worktrees/` (6 worktrees)** — Largest single disk savings. 6 near-full repo copies. Estimated 500MB–2GB+ freed. Remove via `git worktree remove`.
2. **`ui/node_modules/`** — Massive NPM dependency tree. Already gitignored. Delete immediately.
3. **`ui/dist/`** — Vite build output. Not used. Gitignored. Delete.
4. **`ui/src/`** — Old Vite/React source. Production is `jansa-connected.html`. No references. Delete.
5. **`codex prompts/`** — 22 orphaned dev prompt files at root level. Archive to `docs/archive/prompts/`.
6. **`ui/index.html`** — Dead Vite entry point confirmed not referenced by app.py. Delete.
7. **Parity/validation scripts** (`parity_harness.py`, `clean_gf_diff.py`, `ui_parity_harness.py`, `_run_one_mode.py`) — 4 scripts, validation done. Archive to `archive/dev_tools/`.
8. **Root-level doc clutter** (`COWORK_PATCH_consultant_fiche_bugs.md`, `GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md`, `JANSA Dashboard - Standalone.html`, `package-lock.json`) — 4 files at root. Archive/delete.
9. **`docs/` step logs** (`STEP7_IMPLEMENTATION_NOTES.md`, `STEP8_IMPLEMENTATION_NOTES.md`, `STEP8_CLEAN_IMPLEMENTATION_NOTES.md`) — Move to `archive/step_logs/`.
10. **`docs/CLEAN_GF_DIFF_SUMMARY.md`** — Historical validation artifact. Move to `archive/validation_history/`.

### Blockers Before Step 14

1. **Worktree removal method**: `.claude/worktrees/` must be removed with `git worktree remove --force <path>` (once per worktree), then `git worktree prune`. A plain `rm -rf` will leave dangling git refs. Step 14 must use the git commands.

2. **Confirm ui/src/ is not a backup you need**: If there is any feature from the old Vite/React ConsultantFiche.jsx that has not been ported to `ui/jansa-connected.html`, flag before deletion. Based on the audit, production does not use it. Conservative call: move to archive instead of delete if uncertain.

### Final Verdict

```
READY_FOR_STEP_14
```

All risky items verified. No false positives found. All DELETE_NOW items are confirmed unreferenced. All ARCHIVE_NOW items are safe to move. Worktree removal method is documented. Step 14 can execute this plan in one clean pass.

---

*Audit performed: 2026-04-26 — CLEAN Step 13*
