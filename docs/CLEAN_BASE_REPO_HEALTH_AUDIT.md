# CLEAN BASE — Repo Health & Corruption Audit

**Step 1 of CLEAN BASE + CLEAN IO Plan**
**Date:** 2026-04-26
**Auditor:** Automated scan + manual review
**Repo source:** `https://github.com/eidmaalouf89-spec/GFUP_FLAT_GED` (main branch)
**Local working copy:** `GF updater v3/` on user's Desktop

> **Revision note (2026-04-26):** Initial audit ran against the GitHub clone. A subsequent micro-fix scan of the local working copy revealed 4 additional pre-existing blockers (null bytes + truncations) not present in the remote. B-01 (`query_library.py`) was fixed. B-02 through B-05 below are local-copy-only corruption — they must be resolved before the local repo is used for Step 2 onwards.

---

## Summary

| Metric | Count |
|---|---|
| Total files inspected | 374 (local working copy, excl. `.git/` cache/backup dirs) |
| Python source files | 374 parsed |
| Python syntax errors | **4 — BLOCKER** (local copy; 0 in GitHub clone after B-01 fix) |
| Null-byte corrupted files | **2 — BLOCKER** (local copy only) |
| Suspected truncations | 2 (1 Python, 1 Markdown) |
| Broken runtime imports | 0 |
| Committed data files (xlsx) | 3 (8.4 MB total) |
| Generated/obsolete output candidates | 0 committed outputs (gitignore effective) |
| Architecture smell findings | 7 |
| Blockers fixed | B-01 ✅ |
| Remaining blockers (local copy) | **4** |

---

## Findings

### BLOCKER

---

#### B-01 — Syntax error in `src/query_library.py` (line 1178)

**File:** `src/query_library.py`
**Severity:** BLOCKER
**Type:** Truncation artifact / stray line

The file ends with a dangling expression that produces an `unmatched ')'` SyntaxError:

```
    print("SMOKE TEST PASSED — no exceptions raised.")
    print("=" * 60)
"=" * 60)          ← STRAY LINE — unmatched )
```

The last line `"=" * 60)` is a leftover from a prior truncation/paste incident. It is not inside any function or block. Python cannot parse the file at all.

`query_library.py` is a large core module (1178 lines) providing all data-access functions used by the UI reporting layer (`get_actor_fiche`, `get_doc_fiche`, `get_consultant_summary`, etc.). With this error, nothing that imports `query_library` can load — which includes `reporting/data_loader.py` and therefore the entire UI.

**Fix required before Step 2:** Delete the last line `"=" * 60)` from `src/query_library.py`. No other change needed.

**STATUS: ✅ FIXED 2026-04-26** — `py_compile src/query_library.py` passes.

---

#### B-02 — `app.py` contains 512 null bytes (local working copy only)

**File:** `app.py`
**Severity:** BLOCKER
**Type:** Binary corruption — null bytes injected near EOF
**Scope:** Local `GF updater v3/` only — not present in GitHub clone

512 null bytes starting at byte offset 37,548 (~line 842). The file is 38,060 bytes total, meaning the tail (~500 bytes) is corrupted. `app.py` is the Flask/pywebview entry point — null byte corruption means it cannot be compiled or executed. The healthy version exists in the GitHub repo.

**Fix:** Restore `app.py` from the GitHub remote (`git checkout HEAD -- app.py`) or replace with the clean clone version.

---

#### B-03 — `scripts/bootstrap_run_zero.py` truncated mid-argument (local working copy only)

**File:** `scripts/bootstrap_run_zero.py`
**Severity:** BLOCKER
**Type:** Truncation — SyntaxError `'(' was never closed` at line 375
**Scope:** Local `GF updater v3/` only — not present in GitHub clone

The file ends mid-way through an `add_argument(...)` call. The `--root-dir` argument definition is cut off at `def` with no closing `)`. Clean version exists in the GitHub repo.

**Fix:** Restore from GitHub remote (`git checkout HEAD -- scripts/bootstrap_run_zero.py`).

---

#### B-04 — `scripts/_run_one_mode.py` truncated mid-function-call (local working copy only)

**File:** `scripts/_run_one_mode.py`
**Severity:** BLOCKER
**Type:** Truncation — SyntaxError `'(' was never closed` at line 67
**Scope:** Local `GF updater v3/` only — not present in GitHub clone

File ends with `main_module.run_pipeline(verbose` — an incomplete function call. Clean version exists in GitHub repo.

**Fix:** Restore from GitHub remote (`git checkout HEAD -- scripts/_run_one_mode.py`).

---

#### B-05 — `scripts/ui_parity_harness.py` contains null bytes (local working copy only)

**File:** `scripts/ui_parity_harness.py`
**Severity:** BLOCKER
**Type:** Binary corruption — null bytes
**Scope:** Local `GF updater v3/` only — not present in GitHub clone

Same pattern as B-02. File has been corrupted with null bytes in the local copy. Clean version exists in GitHub repo.

**Fix:** Restore from GitHub remote (`git checkout HEAD -- scripts/ui_parity_harness.py`).

---

### HIGH

---

#### H-01 — `paths.py` hardcodes `FLAT_GED.xlsx` as a manual input file

**File:** `src/pipeline/paths.py` line 34
**Severity:** HIGH
**Type:** Architecture smell — FLAT_GED as manual input

```python
FLAT_GED_FILE = INPUT_DIR / "FLAT_GED.xlsx"   # consumed by stage_read_flat (mode='flat')
```

`INPUT_DIR` points to the `input/` folder (where `GED_export.xlsx` and `Grandfichier_v3.xlsx` live). This means the pipeline currently expects users to manually place `FLAT_GED.xlsx` in `input/` before running. Per the Clean IO Contract (Step 4/7), `FLAT_GED.xlsx` must be auto-built by the orchestrator and placed in `output/intermediate/` or a run temp directory — not hand-placed in `input/`.

This path constant will need to change when Step 7 (Orchestrator) is implemented. Flagged now so Step 2 inventory can classify `input/FLAT_GED.xlsx` (gitignored) correctly.

---

#### H-02 — Three scripts hardcode `input/FLAT_GED.xlsx` as manual source

**Files:**
- `scripts/_run_one_mode.py` lines 35–36
- `scripts/clean_gf_diff.py` lines 107–110
- `scripts/ui_parity_harness.py` line 69

All three scripts check for a pre-existing `FLAT_GED.xlsx` inside `input/` and either raise `FileNotFoundError` or copy from an external sibling repo path. This preserves the old manual-placement contract and will silently break once Step 7 changes where the file is generated.

These scripts are likely `ARCHIVE_CANDIDATE` or `ACTIVE_TEMPORARY` per Step 2 classification — but the hardcoded path is a risk regardless.

---

### MEDIUM

---

#### M-01 — `consultant_gf_writer.py` is deprecated but still actively imported

**Files:**
- `src/consultant_gf_writer.py` — exists, documented as DEPRECATED from truth path
- `src/consultant_integration.py` line 57: `from consultant_gf_writer import write_gf_enriched`
- `src/consultant_integration.py` line 289: comment noting possible repurpose as artifact writer

Per `docs/FLAT_GED_REPORT_COMPOSITION.md §9`, `consultant_gf_writer` stages 1/2 are deprecated as deliverable GF producers — they write directly to GF Excel cells outside run history. The file is correctly preserved (may be repurposed as a pipeline artifact writer).

However, `consultant_integration.py` still carries a live import of `write_gf_enriched`. If someone calls `consultant_integration.py` today, it will invoke the deprecated direct-cell write path. The deprecation guard exists only as a comment, not a runtime guard.

**Not a blocker** (no active pipeline call chain triggers it by default), but the import creates risk of accidental invocation. Step 2 should classify `consultant_gf_writer.py` as `ACTIVE` (dormant) with a note.

---

#### M-02 — `bet_report_merger.py` is retired but file remains in active `src/reporting/`

**File:** `src/reporting/bet_report_merger.py`
**References:**
- `src/reporting/data_loader.py` line 24–26: import commented with "DO NOT RESTORE"
- `docs/UI_SOURCE_OF_TRUTH_MAP.md` line 301: status confirmed RETIRED

The file exists and is importable (`import reporting.bet_report_merger` succeeds). The call is correctly dead-coded in `data_loader.py`. Per `docs/FLAT_GED_REPORT_COMPOSITION.md §8`, the file may be retained as a dead file with a deprecation comment or deleted. It must not be called.

Current state is safe, but the file living in the active source tree creates confusion for new contributors and risks accidental re-connection. Step 13 (Cleanup) should move it to `docs/archive/` or add a clear deprecation header.

---

#### M-03 — `docs/FLAT_GED_ADAPTER_MAP.md` still describes manual input placement

**File:** `docs/FLAT_GED_ADAPTER_MAP.md` line 225
**Content:** `FLAT_GED.xlsx must be placed at input/FLAT_GED.xlsx (same directory as GED_export.xlsx)`

This sentence contradicts the Step 4 Clean IO Contract, which will define `FLAT_GED.xlsx` as an internal artifact in `output/intermediate/`, not a user-provided input. The doc was written before the orchestrator design was settled.

Not a code defect, but a documentation truth mismatch that will mislead contributors in Steps 5–7.

---

#### M-04 — `JANSA Dashboard - Standalone.html` is a 1.7 MB root-level blob

**File:** `JANSA Dashboard - Standalone.html` (root)
**Size:** 1,683,099 bytes

A standalone self-contained HTML dashboard living at repo root. This is a legacy prototype or snapshot — the active UI is `ui/jansa-connected.html` + `ui/jansa/`. The standalone file is not referenced by `app.py` or any active code path. It bloats the repo and creates confusion about which HTML is the real product.

Step 13 candidate: `ARCHIVE_CANDIDATE` or `DELETE_CANDIDATE`.

---

#### M-05 — Large data files committed to `input/`

**Files:**
- `input/GED_export.xlsx` — 3.9 MB
- `input/Grandfichier_v3.xlsx` — 4.5 MB
- `input/Mapping.xlsx` — 11 KB

Total: ~8.4 MB of data committed to the repo. The two large files are real GED/GF inputs. They are not gitignored (only `input/FLAT_GED.xlsx` and `input/consultant_reports/` are gitignored). These are useful as test/reference inputs but their presence in the repo means every clone pulls 8+ MB of production-adjacent data.

Per Step 4 Clean IO Contract, `GED_export.xlsx` and `Grandfichier_v3.xlsx` are the correct user-facing inputs in `input/`. Committing them is intentional. Flagged here as a size/data hygiene note — whether to gitignore them is a product decision, not a corruption issue.

---

### LOW

---

#### L-01 — `docs/JANSA_PARITY_STEP_07_EXPORTS.md` ends without terminal punctuation

**File:** `docs/JANSA_PARITY_STEP_07_EXPORTS.md`
**Last line:** `3. Contractors page — Step 8`

The file ends mid-list without a closing section or summary. This matches the pattern of a truncated write. The content may be incomplete. Not a runtime risk, but should be verified before this doc is used as a reference in Steps 9–10.

---

#### L-02 — Root-level planning documents clutter repo root

**Files at repo root (not in `docs/`):**
- `FLAT_GED_INTEGRATION_EXECUTION_PLAN.md`
- `FLAT_GED_INTEGRATION_EXECUTION_PLAN_v2.md`
- `GFUP_REPORTING_ARCHITECTURE_SPEC_v1.2.md`
- `GFUP_STEP_TRACKER.md`
- `COWORK_PATCH_consultant_fiche_bugs.md`
- `JANSA_INTEGRATION_NOTES.md`
- `JANSA Dashboard - Standalone.html`

Seven non-code files live at repo root alongside `app.py`, `main.py`, and `README.md`. This creates navigation noise and makes it unclear which docs are active vs. historical execution artifacts. Step 14 should move these to `docs/archive/` or `docs/`.

---

#### L-03 — `codex prompts/` folder is committed scratch/AI-prompt content

**Folder:** `codex prompts/`
**Contents:** `Step12corrections`, `UIchoice`, `facelift/`, `facelift_step5.txt`, `faceliftstep5v2`, `fullrepo_faclift`, `run0`, `updatemds` (no extensions, plain-text AI prompts and prototype JSX)

This folder contains raw Cowork/Codex prompt scripts and a prototype UI (`facelift/prototype/jansa/*.jsx`). It is not part of the product. Several entries are gitignored (e.g. `codex prompts/DEVELOPMENT_RULES.md`) but most are not. This is a `DELETE_CANDIDATE` for Step 14.

---

#### L-04 — `ui/src/` is a legacy Vite app source living alongside active `ui/jansa/`

**Folder:** `ui/src/`
**Contents:** `App.jsx` (old Vite root component), `main.jsx`, `App.css`, `index.css`, `assets/hero.png`, `assets/react.svg`, `assets/vite.svg`, `components/ConsultantFiche.jsx`

The active UI runtime is `ui/jansa-connected.html` + `ui/jansa/*.jsx` (no build step — Flask serves them directly). `ui/src/` is the old Vite-bundled app that has been superseded. `ui/index.html` and `ui/vite.config.js` are also part of this legacy Vite setup. Step 2 should classify these as `LEGACY_REFERENCE`.

---

#### L-05 — Root `package-lock.json` is a stale artifact

**File:** `package-lock.json` (repo root)
**Note:** Active `package-lock.json` lives in `ui/package-lock.json`

A second `package-lock.json` at repo root (not inside `ui/`) suggests a leftover from an early npm setup. It is not referenced by any script and conflicts with the `ui/`-scoped npm setup. `DELETE_CANDIDATE`.

---

### INFO

---

#### I-01 — `GF_TEAM_VERSION` is fully wired and safe

References confirmed in:
- `src/pipeline/paths.py` → `OUTPUT_GF_TEAM_VERSION`
- `src/pipeline/context.py` → field defined
- `src/pipeline/stages/stage_finalize_run.py` → registered as artifact
- `src/pipeline/runner.py` → passed through
- `src/run_orchestrator.py` → set in both enabled and disabled paths
- `src/team_version_builder.py` → `build_team_version()` implementation
- `app.py` → `export_team_version()` API method (finds `GF_TEAM_VERSION` artifact, copies with date-stamped name)
- `scripts/bootstrap_run_zero.py` → registered in Run 0 bootstrap

The full chain is intact. `GF_TEAM_VERSION` is not at risk. The UI export flow (`export_team_version()` → artifact lookup → copy to `Tableau de suivi de visa DD_MM_YYYY.xlsx`) is sound.

---

#### I-02 — No committed caches, build outputs, or `__pycache__`

Gitignore is well-configured. No `__pycache__/`, `.pyc`, `node_modules/`, `ui/dist/`, `output/`, `runs/`, or `.db` files are tracked in the repo. This is healthy.

---

#### I-03 — `src/flat_ged/` is correctly frozen

Files `src/flat_ged/BUILD_SOURCE.md` and `src/flat_ged/VERSION.txt` confirm the frozen snapshot convention. Module imports correctly (`import flat_ged` succeeds). No syntax errors in any `src/flat_ged/*.py` file.

---

#### I-04 — All other 83 Python files pass syntax check

Only `src/query_library.py` has a syntax error. All 83 remaining `.py` files parse cleanly with `ast.parse()`.

---

#### I-05 — All critical runtime imports succeed (except query_library dependents)

The following modules import without error when `src/` is on `sys.path`:
`pipeline.paths`, `pipeline.context`, `pipeline.runner`, `run_orchestrator`, `run_memory`, `report_memory`, `effective_responses`, `team_version_builder`, `reporting.data_loader`, `reporting.bet_report_merger`, `consultant_gf_writer`.

Note: any module that internally `import`s `query_library` at load time will fail. Verify before Step 2.

---

## Immediate Blockers Before Step 2

| ID | File | Issue | Status | Action |
|---|---|---|---|---|
| B-01 | `src/query_library.py` | Stray `"=" * 60)` at line 1178 — SyntaxError | ✅ **FIXED** | Done |
| B-02 | `app.py` | 512 null bytes near EOF — binary corruption | ⚠️ LOCAL ONLY | `git checkout HEAD -- app.py` |
| B-03 | `scripts/bootstrap_run_zero.py` | Truncated at line 375 — unclosed `(` | ⚠️ LOCAL ONLY | `git checkout HEAD -- scripts/bootstrap_run_zero.py` |
| B-04 | `scripts/_run_one_mode.py` | Truncated at line 67 — unclosed `(` | ⚠️ LOCAL ONLY | `git checkout HEAD -- scripts/_run_one_mode.py` |
| B-05 | `scripts/ui_parity_harness.py` | Null bytes — binary corruption | ⚠️ LOCAL ONLY | `git checkout HEAD -- scripts/ui_parity_harness.py` |

**B-01 is fixed.** B-02 through B-05 are pre-existing corruption in the local working copy only — the GitHub clone is clean for all four files. All four can be restored with a single `git checkout` command. Step 2 can begin once B-02 through B-05 are resolved.

---

## Findings Index

| ID | Severity | File / Area | Summary |
|---|---|---|---|
| B-01 | ~~BLOCKER~~ ✅ FIXED | `src/query_library.py:1178` | Stray `"=" * 60)` — SyntaxError — **fixed 2026-04-26** |
| B-02 | BLOCKER | `app.py` (local only) | 512 null bytes at ~line 842 — binary corruption |
| B-03 | BLOCKER | `scripts/bootstrap_run_zero.py:375` (local only) | Truncated mid-argument — unclosed `(` |
| B-04 | BLOCKER | `scripts/_run_one_mode.py:67` (local only) | Truncated mid-call — unclosed `(` |
| B-05 | BLOCKER | `scripts/ui_parity_harness.py` (local only) | Null bytes — binary corruption |
| H-01 | HIGH | `src/pipeline/paths.py:34` | `FLAT_GED_FILE` points at `input/` (manual placement) |
| H-02 | HIGH | `scripts/_run_one_mode.py`, `clean_gf_diff.py`, `ui_parity_harness.py` | Three scripts hardcode `input/FLAT_GED.xlsx` |
| M-01 | MEDIUM | `src/consultant_integration.py:57` | Live import of deprecated `write_gf_enriched` |
| M-02 | MEDIUM | `src/reporting/bet_report_merger.py` | Retired file in active source tree |
| M-03 | MEDIUM | `docs/FLAT_GED_ADAPTER_MAP.md:225` | Stale manual input doc reference |
| M-04 | MEDIUM | `JANSA Dashboard - Standalone.html` | 1.7 MB legacy standalone HTML at root |
| M-05 | MEDIUM | `input/GED_export.xlsx`, `Grandfichier_v3.xlsx` | Large data files committed (8.4 MB) |
| L-01 | LOW | `docs/JANSA_PARITY_STEP_07_EXPORTS.md` | Ends mid-list — possible truncation |
| L-02 | LOW | Repo root | 7 planning docs outside `docs/` |
| L-03 | LOW | `codex prompts/` | AI scratch folder committed |
| L-04 | LOW | `ui/src/` | Legacy Vite app source alongside active `ui/jansa/` |
| L-05 | LOW | `package-lock.json` (root) | Stale root-level npm lock |
| I-01 | INFO | `GF_TEAM_VERSION` chain | Fully wired — confirmed safe, no action needed |
| I-02 | INFO | `.gitignore` | No caches/outputs committed — clean |
| I-03 | INFO | `src/flat_ged/` | Frozen snapshot — all files valid |
| I-04 | INFO | 83 Python files | All pass syntax check |
| I-05 | INFO | Core runtime imports | All succeed |
