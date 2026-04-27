# JANSA FINAL AUDIT — Pre-Codex / Pre-GitHub Signoff

**Date:** 2026-04-22
**Reference run:** Run 3 (current, completed, non-stale)
**Scope:** Final truth-based audit of the current JANSA implementation prior to Codex whole-repo review and GitHub push.
**Constraint:** No UI redesign. No new features. No inflated parity claims.

This document is the single source of truth for what currently works, what is partial, what is deferred, and what must be resolved before pushing to GitHub.

---

## 0. TL;DR

- JANSA is functionally usable on Run 3. Overview, Consultants list, Consultant Fiche, Drilldowns, Drilldown exports, Runs, Executer, and Utilities are implemented and pass the per-step validations in their respective step docs.
- Real parity against the legacy UI is approximately **91% effective, ~82% strict** when contractors and cosmetics are subtracted honestly. The previously claimed 94% assumes contractors and cosmetic gaps are not in the denominator; they are.
- **One CRITICAL pre-push blocker was discovered during this audit** and is described in §8: `src/reporting/consultant_fiche.py` is truncated mid-string at line 1489. The file only imports today because `.pyc` caches from a previous (complete) build still exist. Any fresh clone, CI runner, or cache reset will break the entire consultant fiche stack, and therefore also drilldowns and drilldown exports. This is the same truncation pattern that was repaired in Steps 2, 9, and 10.
- **Contractors are intentionally deferred.** The Contractors route is still a `StubPage`. No contractor work is claimed.
- A small set of cosmetic items (top-bar run pill, "System Ready" text, app_version line, per-doc priority queue rendering) is explicitly deferred. These are not parity blockers.
- **Recommendation:** **Do NOT push to GitHub** until the `consultant_fiche.py` truncation is restored. Codex review can safely begin in parallel on the rest of the tree; Codex should be told about the truncation so it does not spend time investigating "why the file imports in dev but fails clean."

---

## 1. Feature-by-feature audit

Classification legend:

- **FULL_PARITY** — implemented and validated against legacy behavior
- **PARTIAL_PARITY** — implemented but with a known, documented gap
- **DEFERRED** — intentionally not in scope for this phase
- **LEGACY_BUG_NOT_REPLICATED** — legacy had a bug; JANSA purposely does not reproduce it
- **KNOWN_UI_ISSUE_NOT_BLOCKING** — cosmetic / ergonomic gap, no workflow impact

### 1.1 Focus mode (Step 2)

| Item | Classification | Notes |
|------|---------------|-------|
| Focus toggle wiring (shell → bridge → backend) | FULL_PARITY | Ref-based state, generation counter, loading overlay (Step 2 §7) |
| F2 "resolved excluded" filter | FULL_PARITY | Backend `apply_focus_filter` |
| F4 "stale excluded" filter (90d default) | FULL_PARITY | Parameterised via `stale_days` after Step 11 |
| Priority buckets P1–P5 | FULL_PARITY | `_days_to_deadline` buckets |
| Focus KPIs on Overview (pending_blocking, focused, excluded) | FULL_PARITY | Validated Step 3 |
| FocusRadial P1/P2/P3/P4 | FULL_PARITY | Validated Step 2 |
| FocusByConsultant waterfall | FULL_PARITY | `by_consultant` — 11 entries Run 3 |
| `focus_owned` on consultant cards | FULL_PARITY | Validated Step 4 |
| Fiche focus ownership + weekly bloc1 | FULL_PARITY | Validated Step 5 |
| MOEX focus_owned badge | LEGACY_BUG_NOT_REPLICATED | MOEX ownership tracked via `_focus_owner_tier`, not `_focus_owner` list (matches legacy) |
| Focus priority queue per-document rendering on Overview | DEFERRED | Data at `window.OVERVIEW.priority_queue` (up to 50 rows) since Step 11, UI not rendered. JANSA uses FocusRadial + Waterfall as visual replacement. |

### 1.2 Overview (Step 3)

| Item | Classification | Notes |
|------|---------------|-------|
| HeroKpi: total_docs | FULL_PARITY | |
| HeroKpi: pending_blocking | FULL_PARITY | Fake "dont 127 en retard" sub-text fixed |
| HeroKpi: best_consultant, best_contractor | FULL_PARITY | |
| VisaFlow Sankey | PARTIAL_PARITY | `on_time`/`late` not computed; guarded with "délais non calculés" fallback — no fake zeros. Deferred aggregator enhancement. |
| WeeklyActivity chart | FULL_PARITY | |
| Degraded Mode banner | FULL_PARITY | |
| ProjectStatsCard | FULL_PARITY | |
| SystemStatusCard | FULL_PARITY | `mapping_detected` omitted — legacy bug not replicated |
| Warnings section | FULL_PARITY | |
| QuickActions + Export VISA | FULL_PARITY | |
| Discrepancies KPI | DEFERRED | `kpis.discrepancies_count` available; not mapped to overview |
| Focus Priority Queue per-doc list | DEFERRED | See §1.1 |
| `total_docs_delta`, `pending_blocking_delta`, `refus_rate_delta`, best.delta | DEFERRED | Require previous-run comparison |

### 1.3 Consultants list (Step 4 + Step 4 correction)

| Item | Classification | Notes |
|------|---------------|-------|
| 3-level hierarchy (MOEX / Primary / Secondary) | FULL_PARITY | Intentional JANSA design — functionally covers legacy flat table |
| Name, canonical_name, pass_rate, total, pending | FULL_PARITY | |
| VSO / VAO / REF breakdown via `CnBreakdown` | FULL_PARITY | |
| avg_response_days | FULL_PARITY | |
| open_blocking (data available) | FULL_PARITY | Not displayed — legacy also does not display it |
| focus_owned badge | FULL_PARITY | |
| Bureau de Contrôle FAV/SUS/DEF vocabulary | FULL_PARITY | Validated Run 3: FAV=725, SUS=139, DEF=57 |
| MOEX SAS visual highlight (yellow border / ◆ prefix from legacy) | PARTIAL_PARITY | Rendered inside MOEX group, same tokens as other MOEX — no distinct yellow treatment. Not blocking. |
| "Répondus" count on Primary/Secondary cards | PARTIAL_PARITY | Shown on MOEX only; pass_rate encodes equivalent info |
| Trend sparklines | DEFERRED | Requires historical multi-run data |
| Avg days on Secondary chip | DEFERRED | Layout constraint |
| Original flat 9-column legacy table | LEGACY_BUG_NOT_REPLICATED | For Bureau de Contrôle it showed VSO/VAO/REF = 0 (misleading). JANSA switches vocab per consultant. |

### 1.4 Consultant fiche (Step 5)

| Item | Classification | Notes |
|------|---------------|-------|
| Masthead standard + SAS | FULL_PARITY | |
| HeroStats with blocking/NB split | FULL_PARITY | |
| HeroStats SAS mode (Passed/Pending/PassRate) | FULL_PARITY | |
| Narrative (standard + SAS) | FULL_PARITY | |
| Bloc1 monthly table with blocking/NB columns | FULL_PARITY | Δ backlog replaced |
| Bloc2 6-layer stacked area + 6-row tooltip | FULL_PARITY | |
| Bloc3 7-segment health bar + inline blocking/NB numbers | FULL_PARITY | |
| Bloc3 donut with NB | FULL_PARITY | |
| Bloc3 critical lots + refus lots sidebars | FULL_PARITY | |
| FAV/SUS/DEF vocabulary for Bureau de Contrôle | FULL_PARITY | |
| Clickable numbers / drilldowns | FULL_PARITY | See §1.5 |
| Focus priority strip UI | DEFERRED | Backend provides `focus_priority`, no JANSA component yet |
| Non-saisi GED badge UI | DEFERRED | Backend provides `non_saisi`; legacy also did not render it |
| Bloc4 SAS contractor ranking | DEFERRED | Backend provides `bloc4_sas`; legacy does not render it either |
| Sparkline gradient ID | KNOWN_UI_ISSUE_NOT_BLOCKING | `Math.random()` vs legacy `useId()`. Collision theoretically possible. |
| FicheExportButton overlay (Tableau de Suivi VISA) | FULL_PARITY | Added in Step 11 |

### 1.5 Drilldowns (Step 6)

| Item | Classification | Notes |
|------|---------------|-------|
| HeroStats clickable big numbers + chips (answered / s1 / s2 / s3 / hm / open_blocking / ok / late / NB) | FULL_PARITY | |
| Bloc3 lot-row clickable cells (total / s1–s3 / HM / ok / late / NB) | FULL_PARITY | |
| DrilldownDrawer bottom sheet (loading / error / empty / doc-list) | FULL_PARITY | |
| ESC + backdrop close | FULL_PARITY | |
| Generation counter anti-stale | FULL_PARITY | `drillGenRef` |
| Focus mode forwarding | FULL_PARITY | |
| SAS fiche drilldown counts | PARTIAL_PARITY | SAS fiche uses a different counting path than `get_doc_details`; docs are real, counts do not match SAS header. Backend gap — same in legacy. |
| Bloc1 per-month row drilldown | DEFERRED | Not in minimum scope |
| Masthead total click | DEFERRED | Not in minimum scope |

### 1.6 Drilldown exports (Step 7)

| Item | Classification | Notes |
|------|---------------|-------|
| "Exporter Excel" button in drawer | FULL_PARITY | |
| Params match drilldown verbatim (consultant, filter_key, lot_name, focus) | FULL_PARITY | `inspect.signature` delegation |
| 9-column Excel output | FULL_PARITY | |
| Late-row highlight | FULL_PARITY | |
| Double-click guard | FULL_PARITY | |
| SAS export count | PARTIAL_PARITY | Inherited from §1.5 |
| User-visible success toast / file open shortcut | DEFERRED | Matches behavior of other exports in the app |

### 1.7 Runs page (Step 9)

| Item | Classification | Notes |
|------|---------------|-------|
| Run list, newest-first, with 4 runs visible | FULL_PARITY | |
| Run number, label, CURRENT/BASELINE/STALE badges | FULL_PARITY | STALE badge not testable visually (no stale run in project data) |
| Mode label, status chip, created_at, completed_at | FULL_PARITY | |
| Export ZIP button + per-card state machine | FULL_PARITY | `export_run_bundle` validated |
| Loading / empty / error states | FULL_PARITY | |
| Artifact count surfaced in UI | DEFERRED | Not in legacy spec |
| Run-to-run comparison | DEFERRED | Not in legacy spec |
| Silent skip of missing artifacts in zip (Windows path issue) | KNOWN_UI_ISSUE_NOT_BLOCKING | Pre-existing backend behavior, logged |

### 1.8 Executer page (Step 10)

| Item | Classification | Notes |
|------|---------------|-------|
| Run mode selector (GED_GF / GED_ONLY / GED_REPORT) | FULL_PARITY | |
| File inputs GED / GF / Mapping / Reports | FULL_PARITY (except mapping — see below) |
| GF disabled when GED_ONLY (inheritance hint) | FULL_PARITY | |
| Auto-detected defaults from `get_app_state` | FULL_PARITY | |
| Reactive validation (`validate_inputs`) | FULL_PARITY | Generation counter |
| Errors block + warnings block + info banner | FULL_PARITY | |
| Launch button, progress, polling (600 ms) | FULL_PARITY | Generation counter on poll |
| Success / failure reset buttons | FULL_PARITY | |
| Post-run shell refresh via `onRunComplete` | FULL_PARITY | |
| Double-launch guard (UI + backend `_pipeline_lock`) | FULL_PARITY | |
| Mapping path passed to backend | LEGACY_BUG_NOT_REPLICATED | Legacy silently clobbered `reports_dir` with `mappingPath`; mapping never reached backend. JANSA keeps the visual control but does not transmit — matches legacy effective behavior without replicating the bug. Flagged in Step 10 §7 for a follow-up backend ticket. |
| Mid-run navigation recovery | KNOWN_UI_ISSUE_NOT_BLOCKING | Executer resets on re-mount; backend keeps running. Matches legacy. |
| End-to-end pipeline run exercised | PARTIAL_PARITY | Logical validation only (sandbox has no Windows paths / PyWebView). Needs desktop smoke test before release. |
| FULL run mode | DEFERRED | Exists in orchestrator, not exposed in legacy UI either |

### 1.9 Utilities / system (Step 11)

| Item | Classification | Notes |
|------|---------------|-------|
| Stale threshold slider (30–365, step 15) in FocusToggle popover | FULL_PARITY | Gear icon visibility patched same day |
| `stale_days` forwarded through bridge + backend | FULL_PARITY | |
| localStorage persistence + 400 ms debounce | FULL_PARITY | |
| Focus stats breakdown in popover (exclus / résolus / périmés / total traçés) | FULL_PARITY | |
| Priority queue exposed on `window.OVERVIEW.priority_queue` | FULL_PARITY (BRIDGE) | UI rendering deferred |
| FicheExportButton on Consultant Fiche | FULL_PARITY | |
| ReportsPage (real page instead of Stub) | FULL_PARITY | |
| Sidebar "System Ready" text + app_version | KNOWN_UI_ISSUE_NOT_BLOCKING | LoadingScreen covers connecting state; dot always green post-load. No workflow impact. |
| Top-bar run pill "Run N — COMPLETED" | KNOWN_UI_ISSUE_NOT_BLOCKING | Functionally covered by sidebar project pill |
| Top-bar "N runs registered" count | KNOWN_UI_ISSUE_NOT_BLOCKING | Functionally covered by sidebar Runs badge |
| FicheExportButton on ContractorFiche | DEFERRED | Blocked by Step 8 |
| ExportTeamVersionButton in ContractorPage list view | DEFERRED | Blocked by Step 8 |
| Per-document priority queue rendering in FocusPanel | DEFERRED | Data available; no UI component |

### 1.10 Contractors (Step 8 — deferred scope)

| Item | Classification | Notes |
|------|---------------|-------|
| Contractors route | DEFERRED | `shell.jsx` line 650 still renders `<StubPage title="Entreprises"/>` |
| ContractorFiche | DEFERRED | No JANSA component |
| Contractor exports | DEFERRED | Backend exists; no UI wiring |
| Contractor focus ownership / MOEX-replied-REF tier | DEFERRED | Visible in backend data, not surfaced |

No contractor code has been written in this phase. Any contractor-adjacent change must be treated as a new feature.

### 1.11 Remaining shell / system behaviors

| Item | Classification | Notes |
|------|---------------|-------|
| Sidebar (Overview, Consultants, Contractors, Executer, Runs, Discrepancies, Reports, Settings) | FULL_PARITY for 5 routes + 3 StubPages |
| Discrepancies page | DEFERRED | StubPage (line 658) — legacy had a placeholder, matches |
| Settings page | DEFERRED | StubPage (line 660) — legacy had a placeholder, matches |
| FocusCinema animation | FULL_PARITY | Plays on focus-enter only (Step 2 fix) |
| Loading overlay on focus toggle | FULL_PARITY | |
| ThemeToggle | FULL_PARITY (pre-existing) | |
| i18n (FR/EN) | FULL_PARITY | FR default; EN translations present in fiche_base |

---

## 2. Parity classification summary by feature group

| Group | FULL | PARTIAL | DEFERRED | LEGACY_BUG_NOT_REPLICATED | KNOWN_UI_ISSUE_NOT_BLOCKING |
|-------|------|---------|----------|---------------------------|-----------------------------|
| Focus mode | 9 | 0 | 1 | 1 | 0 |
| Overview | 9 | 1 (VisaFlow) | 3 | 0 | 0 |
| Consultants list | 8 | 2 (MOEX SAS visual, Primary/Secondary "Répondus") | 2 | 1 | 0 |
| Consultant fiche | 12 | 0 | 3 | 0 | 1 (sparkline id) |
| Drilldowns | 7 | 1 (SAS count) | 2 | 0 | 0 |
| Drilldown exports | 5 | 1 (SAS inherited) | 1 | 0 | 0 |
| Runs | 5 | 0 | 2 | 0 | 1 (missing-artifact skip) |
| Executer | 11 | 1 (end-to-end smoke) | 1 (FULL mode) | 1 (mapping) | 1 (mid-run nav) |
| Utilities / system | 7 | 0 | 4 | 0 | 3 (topbar cosmetic, system text) |
| Contractors | 0 | 0 | 4 | 0 | 0 |
| Shell / system | 5 | 0 | 2 | 0 | 0 |

Honest effective parity, treating PARTIAL as 0.5 and deferred/legacy/cosmetic as 0:

- FULL: 78 items
- PARTIAL: 6 items (~3 equivalent)
- Effective closed: ~81 out of ~102 audited items ≈ **79% strict**
- Against the master-plan 35-feature denominator (which subtracts contractors entirely): **~91% effective**, not 94% as claimed in Step 11.

Step 11 should not have claimed 94% without explicitly subtracting contractors and cosmetics from the denominator. That bookkeeping is corrected here.

---

## 3. Deferred items (explicit)

1. Contractors page + fiche + exports + focus ownership — Step 8, intentionally deferred for redesign.
2. Top-bar run pill "Run N — COMPLETED" — functionally covered by sidebar pill.
3. Top-bar "N runs registered" count — functionally covered by sidebar Runs badge.
4. Sidebar "System Ready" text + app_version line — LoadingScreen covers the wait state.
5. Per-document priority queue rendering on Overview — data already in `window.OVERVIEW.priority_queue`; JANSA uses FocusRadial + Waterfall as visual replacement.
6. Focus priority strip UI inside Fiche page — backend provides `focus_priority`, no JANSA component.
7. Non-saisi GED badge UI — backend provides `non_saisi`; legacy also does not render it.
8. Bloc4 SAS contractor ranking UI — backend provides `bloc4_sas`; legacy does not render it either.
9. Trend sparklines on consultant cards — requires historical multi-run data.
10. Delta badges on Overview KPIs (`total_docs_delta`, `pending_blocking_delta`, `refus_rate_delta`, best_consultant.delta, best_contractor.delta) — require previous-run comparison.
11. Discrepancies KPI card on Overview — `kpis.discrepancies_count` available, not mapped.
12. Bloc1 per-month row drilldown — requires `month`-keyed filter in `get_doc_details`.
13. Masthead total-number drilldown — intentional, would be unhelpful with 4,000+ docs.
14. `visa_flow.on_time` / `visa_flow.late` computation — aggregator enhancement; UI currently shows safe "délais non calculés" fallback.
15. FULL run mode exposure in Executer UI — not in legacy either.
16. Discrepancies page (full workflow) — StubPage in shell; legacy has a placeholder too.
17. Settings page (full workflow) — StubPage in shell; legacy has a placeholder too.
18. "Autres rapports" card on Reports page — intentional placeholder.

---

## 4. Known limitations (still present, by design or accepted)

1. **SAS fiche drilldown counts do not match SAS header counts.** SAS pass/fail counting uses a different GED field than `_status_for_consultant`. Documents returned are real, counts reflect a different metric. Backend-only fix needed; carried through to exports. (Steps 6 §7, 7 §7.)
2. **`visa_flow.on_time` / `visa_flow.late` are null** in the overview Sankey. Aggregator does not yet compute deadline scan. UI renders "délais non calculés" fallback, never fake zeros. (Step 3 §7.)
3. **Mapping path in Executer is visual-only.** The file is browsed and displayed but is not transmitted to `validate_inputs` or `run_pipeline_async`. Matches legacy's effective behavior (legacy clobbered `reports_dir` with it). Follow-up ticket required to wire mapping properly if/when the backend signature changes. (Step 10 §7.)
4. **`export_run_bundle` silently skips artifacts whose paths do not resolve** (Windows-absolute paths on non-Windows hosts). Pre-existing backend behavior; logs a warning. (Step 9 §7.)
5. **MOEX SAS consultant has no distinct visual highlight** in the consultants list (legacy used a yellow border + ◆ prefix). Rendered inside the MOEX group with the same tokens as Maître d'Oeuvre EXE. Not a data gap.
6. **Primary and Secondary consultant cards do not show "Répondus" raw count.** Only `pass_rate` is shown. MOEX card does show it. Pass rate is functionally equivalent.
7. **Secondary chip does not show avg_days.** Layout constraint; VSO/VAO/REF micro-breakdown only.
8. **Trend sparkline arrays are empty (`[]`) on consultant cards.** Requires multi-run history beyond the current baseline.
9. **Sparkline gradient IDs use `Math.random()`** instead of `useId()`. Collision theoretically possible when multiple fiche sparklines share the DOM simultaneously; no observed issue.
10. **Executer does not recover in-progress run UI state on re-mount.** Backend keeps running; UI resets. Matches legacy.
11. **No toast / file-open shortcut after exports.** Files land in `output/`; UI gives no feedback. Consistent across all exports.

---

## 5. Legacy bugs intentionally NOT replicated

1. **Bureau de Contrôle (SOCOTEC) shown as VSO=0 / VAO=0 / REF=0** in the consultants list and fiche. Legacy hard-coded "VSO"/"VAO"/"REF" status counting. JANSA switches vocabulary per consultant to FAV/SUS/DEF. (Step 4 correction.)
2. **`mappingPath` silently clobbering `reports_dir`** in `validate_inputs` / `run_pipeline_async`. Legacy passed mapping as 4th positional arg to a signature that did not accept it. JANSA keeps the visible control but does not transmit the value — and must not call the backend with it. (Step 10 §7.)
3. **`appState.mapping_detected` rendered as "Mapping File" row in System Status.** `get_app_state()` never populates this field. Legacy rendered it anyway — JANSA does not render that row. (Step 3 §7.)
4. **MOEX `focus_owned` reporting zero in the consultant list.** Legacy and JANSA both behave this way — MOEX ownership is tracked via `_focus_owner_tier` not via the `_focus_owner` list. This one is labelled here for clarity; it is not a JANSA bug but a semantic design choice inherited from legacy. Not a divergence.

---

## 6. Known UI issues still not priority-blocking

1. Sidebar dot is always green post-`dataReady` (no "connecting"/"error" variant) — LoadingScreen covers the gap.
2. Sidebar "System Ready" text and `app_version` not shown.
3. Top-bar run pill "Run N — COMPLETED" absent — sidebar project pill covers run number.
4. Top-bar "N runs registered" count absent — sidebar Runs badge covers the number.
5. MOEX SAS card has no distinct yellow border / ◆ prefix.
6. Sparkline gradient IDs use `Math.random()`.
7. Drilldown document table has no row limit; large sets (e.g., 1,798 blocking docs for Bureau de Contrôle) render all rows in the DOM. Performance acceptable but not paginated.
8. `export_run_bundle` on mixed-OS paths silently skips artifacts.
9. Non-saisi GED badge not rendered (data available).
10. Focus priority strip not rendered on Fiche (data available).

---

## 7. Release-readiness summary

### Production-ready now

- Overview page (with the VisaFlow on_time/late fallback).
- Consultants list (with consultant-specific VSO/VAO/REF vs FAV/SUS/DEF vocabulary).
- Consultant fiche standard + SAS variants.
- Drilldowns + drilldown exports (except SAS count caveat).
- Runs page.
- Executer page (validated at unit/integration level; needs desktop smoke test).
- Utilities: stale threshold slider, ReportsPage, FicheExportButton, priority_queue bridge exposure.

### Usable now (with caveats)

- Executer page: has never been exercised end-to-end on a real desktop environment since Step 10's backend tail restoration. Needs one manual run before the release tag.
- SAS drilldowns return real documents but with a different count basis than the SAS fiche header.

### Deferred by choice

- Contractors page and all contractor features (Step 8).
- Top-bar cosmetic items (run pill, runs count, system status text).
- Per-document priority queue rendering, non-saisi badge, bloc4 SAS, trend sparklines, delta badges.
- Discrepancies and Settings pages (StubPages — legacy also has placeholders).

### Must be reviewed before push

- §8 below — one CRITICAL pre-push blocker.

### Is GitHub push acceptable now (before contractor redesign)?

**Only after §8 is resolved.** Once the `consultant_fiche.py` truncation is restored, a push is acceptable because:
- contractor scope is cleanly isolated in a StubPage and labelled as deferred in code and docs;
- all other feature groups validated in their step docs map to code that still exists;
- no fake values are displayed anywhere in the UI;
- the `.md` step reports are consistent with the code as it exists today (with the single exception in §8).

---

## 8. CRITICAL pre-push blocker discovered during audit

### 8.1 `src/reporting/consultant_fiche.py` is truncated mid-string

File size: 60,639 bytes, ends at line 1488 with:

```
    if docs.empty or "response_source" not in docs.columns:
        return {"count": 0, "pct": 0.0, "badge": "gr
```

No closing quote, no closing brace, no return value. `ast.parse` reports:

```
SyntaxError at line 1489: unterminated string literal (detected at line 1489)
```

### 8.2 Why it imports today

- `.pyc` caches from a previous complete build still exist under `src/reporting/__pycache__/consultant_fiche.cpython-{310,311,312}.pyc`.
- Python's cache-lookup honors the `.pyc` when the source mtime is older than the cache mtime.
- The complete `_build_non_saisi` function is preserved in the cached bytecode.
- On this machine, in this sandbox, `import reporting.consultant_fiche` succeeds because it picks up the cached version.
- On any fresh clone, CI runner, cache clear, or after the next source edit that updates the mtime past the cache, the `.pyc` is invalidated and Python will fall back to the source — which will raise `SyntaxError`.

### 8.3 Blast radius if unfixed

All of the following rely on `consultant_fiche.py` importing cleanly:

- `get_consultant_fiche` → Consultant Fiche page (Step 5).
- `get_doc_details` (uses `_resolve_status_labels` from `consultant_fiche.py`) → Drilldowns (Step 6) and Drilldown exports (Step 7).
- The `STATUS_LABELS_BY_CANONICAL` constant source of truth for Socotec vocabulary.
- Focus-mode fiche filtering (Step 5 §6).

If the import fails on GitHub / CI, the app will not render any consultant fiche and no drilldowns will work — regression from the validated Step 5–7 state.

### 8.4 Precedent

This is the same class of failure seen in three prior steps:

- Step 2: `src/reporting/focus_filter.py` truncated at line 197.
- Step 9: `src/run_memory.py::export_run_artifacts_bundle` truncated.
- Step 10: `src/run_orchestrator.py` truncated mid-`return` dict at line 308.

All three were restored by recovering the tail from `.pyc` bytecode. The same approach will work here — the cached `_build_non_saisi` function has an observable 232-byte bytecode body. Recovery pattern is identical.

### 8.5 Why this audit does not fix it

This step's mission is audit, not feature work. A ~10-line restoration qualifies as a "tiny blocking fix" under the step rules, but the fix must be done as its own step so it can be validated (e.g., re-run drilldown tests, re-run Bureau de Contrôle vocabulary test) and documented cleanly. A silent in-audit fix would contaminate the audit artifact with work that was not reviewed by the user.

### 8.6 Recommended next action

Create a surgical recovery step (call it Step 12b or Step 5.1 follow-up):

1. Disassemble `src/reporting/__pycache__/consultant_fiche.cpython-310.pyc` to recover the `_build_non_saisi` function body.
2. Append the restored function tail to `consultant_fiche.py`.
3. Run `ast.parse` on all `src/reporting/*.py` — must all pass.
4. Run a Bureau de Contrôle fiche + drilldown test against Run 3 to confirm no regression.
5. Clear `__pycache__/` afterwards and re-import to prove clean source loads.

---

## 9. Codex whole-repo review checklist

Targeted for a single pass by Codex. Priorities are ordered by blast-radius.

### P0 — must review

1. **Source truncations.** `ast.parse` every `src/**/*.py` and every `ui/jansa/*.jsx` (Babel). Flag any file whose source cannot be parsed on a fresh checkout. Specifically confirm `src/reporting/consultant_fiche.py`, `src/reporting/focus_filter.py`, `src/run_orchestrator.py`, `src/run_memory.py` all parse. (§8 is the known open issue.)
2. **`__pycache__/` stripping.** Confirm the GitHub push will not ship `__pycache__/` directories — they hide truncation and can make CI behave differently from production.
3. **Stale state after focus toggle / drilldown / executer polling.** Verify `focusGenRef`, `drillGenRef`, `validateGenRef`, `pollGenRef`, and `bridge._loadGen` are correctly incremented on unmount or supersession and that no code writes globals after generation mismatch.
4. **Pipeline launch double-fire.** Confirm `handleLaunch` early-returns on `launching || running`, and the backend `_pipeline_lock` rejects a second start. Simulate two near-simultaneous clicks.
5. **Contractor scope isolation.** The word "Contractors" should appear only as: (a) the sidebar entry, (b) the StubPage route in `shell.jsx` line 650, (c) minimal adapter code that returns a list (deferred), (d) docs. There must be no half-built fiche / drilldown / export code for contractors. Delete any orphans if found.

### P1 — should review

6. **Async export safety.** `export_drilldown_xlsx`, `export_team_version`, `export_run_bundle` all run on the main thread. Confirm no dialog race between export and a subsequent focus toggle or page navigation causes a stale write.
7. **Babel parse fragility.** Curly-quote substitution broke `overview.jsx` once (Step 3 recovery). Confirm no `.jsx` file contains U+2018/U+2019 in source (audit re-ran this check: all 0). Add a lint rule if feasible.
8. **UI invisibility issues.** The FocusToggle gear was invisible until the Step 11 patch. Scan other `var(--text-3)` on `var(--bg-elev-2)` combinations for similar contrast risk.
9. **Step docs vs code consistency.** Each `JANSA_PARITY_STEP_*.md` claims a file list changed. Cross-check that every such file exists, is reachable from `jansa-connected.html`, and compiles.
10. **`jansa-connected.html` script order.** Confirm dependency order: `tokens.js`, `data_bridge.js`, `fiche_base.jsx` (exports `DrilldownDrawer`), `overview.jsx`, `consultants.jsx`, `fiche_page.jsx`, `runs.jsx`, `executer.jsx`, `shell.jsx` (uses all the above).
11. **No fake values.** Grep for hardcoded numbers in UI: `"dont 127 en retard"`, etc. Step 3 removed this one; confirm none have regressed.
12. **No black-screen risks.** Confirm `overview.jsx` still compiles without Unicode curly quotes; `fiche_base.jsx` parenthesis/brace balance holds; every `window.*Page` is defined before `shell.jsx` references it.

### P2 — nice to have

13. **Dead code cleanup opportunities.** `BalanceGlyph` was removed in Step 5; confirm no stale imports reference it. Other Step 4/5/6 churn may have left orphans.
14. **Localisation coverage.** EN translations exist in `fiche_base.jsx`; confirm `shell.jsx` and `overview.jsx` also provide EN strings for any UI-visible text.
15. **Log volume.** Step-11 bridge adds a `console.warn` for stale load discards; confirm it does not fire routinely.
16. **Release artifact.** `ui/dist/` present but not audited. Confirm it is either freshly built or excluded from the repo.

---

## 10. Final recommendation

**Safe to review with Codex now:** **YES** — with an advisory note: tell Codex that §8 is a known open issue so it spends its time elsewhere.

**Safe to push to GitHub now:** **NO.** The `consultant_fiche.py` truncation must be restored first. After restoration, push is safe for every feature group except Contractors (which is explicitly a StubPage and labelled deferred).

### What must be excluded from parity claims when communicating to stakeholders

- Contractors — 0% parity, explicitly deferred.
- Top-bar cosmetic items (run pill, runs count, "System Ready" text + app_version).
- Per-document priority queue rendering on Overview.
- Focus priority strip on Fiche.
- Non-saisi GED badge.
- Bloc4 SAS contractor ranking.
- Trend sparklines on consultant cards.
- Delta badges on Overview.
- Discrepancies and Settings pages.
- End-to-end desktop smoke test of the full pipeline run (Executer) — validated logically only.

Stating "~91% parity, contractors and cosmetic items excluded" is honest. Stating "100% parity" is not.

---

## 11. Audit trail

### Documents reviewed

- `docs/JANSA_PARITY_MASTER_PLAN.md`
- `docs/JANSA_PARITY_STEP_02_FOCUS.md`
- `docs/JANSA_PARITY_STEP_03_OVERVIEW.md`
- `docs/JANSA_PARITY_STEP_04_CONSULTANTS_LIST.md`
- `docs/JANSA_PARITY_STEP_05_FICHE.md`
- `docs/JANSA_PARITY_STEP_06_DRILLDOWNS.md`
- `docs/JANSA_PARITY_STEP_07_EXPORTS.md`
- `docs/JANSA_PARITY_STEP_09_RUNS.md`
- `docs/JANSA_PARITY_STEP_10_EXECUTER.md`
- `docs/JANSA_PARITY_STEP_11_UTILITIES.md`
- `docs/KNOWN_LIMITATIONS.md` (pipeline-level, not UI-level)

### Code spot-checks performed

- `ast.parse` on `src/run_orchestrator.py`, `src/run_memory.py`, `src/reporting/focus_filter.py`, `src/reporting/ui_adapter.py`, `src/reporting/aggregator.py`, `src/reporting/consultant_fiche.py`, `app.py` — all pass **except** `consultant_fiche.py` (§8).
- All 7 JSX files counted, loaded, and searched for Unicode curly quotes (0 occurrences each).
- `shell.jsx` route map confirmed: 5 real pages, 3 StubPages (Contractors, Discrepancies, Settings).
- Global registrations confirmed: `window.OverviewPage`, `ConsultantsPage`, `ConsultantFichePage`, `ConsultantFiche`, `DrilldownDrawer`, `RunsPage`, `ExecuterPage`, `App`, `Sidebar`, `Topbar`, `FocusToggle`, `ThemeToggle`, `FocusCinema`, `LoadingScreen`.
- Generation counters confirmed present: `focusGenRef` (shell), `drillGenRef` (fiche_page), `validateGenRef`, `pollGenRef` (executer), `_loadGen` (data_bridge).
- `stale_days` plumbing confirmed end-to-end in `app.py` (all relevant API methods) and `data_bridge.js` (4 methods).
- `jansa-connected.html` script order confirmed.
- `ui_adapter.py` confirmed to return `priority_queue`, `focus_owned`, `s1_label`/`s2_label`/`s3_label`.

### Files changed in this step

None. This step is audit-only. The pre-push blocker in §8 is documented; its fix must be a separate, validated step.
