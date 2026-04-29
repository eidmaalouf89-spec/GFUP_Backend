# Phase 1 — Dashboard Layout Reorder & Chain+Onion Expansion — REPORT

**Status:** ✅ COMPLETED
**Date:** 2026-04-29
**Risk:** LOW (executed as planned)
**Scope:** UI only, single file. No backend, no adapter, no pipeline.

This file replaces the original Phase 1 plan. The plan content is no longer reproduced here; what follows is the as-built record.

---

## 1. Objective (recap)

Reorganize the Overview dashboard so operational priorities (Chain+Onion table, KPIs, focus panel) are above ambient project metadata (Project Stats, System Status), and let the user expand the Chain+Onion priority list beyond the default slice.

Three sub-changes, all in `ui/jansa/overview.jsx`:

1. Move `ProjectStatsCard` + `SystemStatusCard` to the end of the page (after Quick Actions).
2. Promote `ChainOnionPanel` to render directly after the VisaFlow / WeeklyActivity grid; default visible slice raised from 15 to 25.
3. Replace the static `+N autres chaînes prioritaires` line with an expand/collapse button.

Applies to both Focus and Regular modes.

---

## 2. As-built render order (`OverviewPage`, `ui/jansa/overview.jsx` lines 720–775)

1. `OvDegradedBanner` (conditional)
2. Section header
3. `KpiRow`
4. `FocusPanel` (focus mode only)
5. `legacy_backlog_count` line (focus mode + count > 0)
6. VisaFlow + WeeklyActivity grid
7. **`ChainOnionPanel`** *(moved up)*
8. `OvWarnings`
9. `QuickActions`
10. **`ProjectStatsCard` + `SystemStatusCard`** *(moved to end)*

---

## 3. ChainOnionPanel — as-built behavior (lines 819–969)

- New local state: `const [expanded, setExpanded] = useStateOv(false);`
  - `useStateOv` is the local alias destructured from `React` at line 6, matching the convention used by `QuickActions` (lines 656–657). Not `React.useState`.
- New constant: `const COLLAPSED_LIMIT = 25;`
- `visible = expanded ? allIssues : allIssues.slice(0, COLLAPSED_LIMIT);`
- `overflow = allIssues.length - COLLAPSED_LIMIT;` *(note: stable when expanded — drives whether the button renders, regardless of expand state)*
- Footer rendered only when `overflow > 0`:
  - Collapsed label: `Voir les ${overflow} autre${overflow > 1 ? 's' : ''} chaîne${overflow > 1 ? 's' : ''} prioritaire${overflow > 1 ? 's' : ''} →`
  - Expanded label: `Réduire ↑`
  - Style: transparent background, `1px solid var(--line)` border, `borderRadius: 8`, `padding: 8px 14px`, `fontSize: 11`, `color: var(--text-3)`, `fontFamily: inherit`, `cursor: pointer`. Hover swaps background to `var(--bg-elev-2)`.
- When total issues ≤ 25: no button, no empty footer.

---

## 4. Files modified

| File | Change |
|---|---|
| `ui/jansa/overview.jsx` | OverviewPage render order; ChainOnionPanel state + slice + footer button |

`git diff --stat` scope: only the file above. (A pre-existing staged deletion of `docs/implementation/05_PHASE_5_REPORT.md` was unrelated to Phase 1 and was already present at session open.)

---

## 5. Validation results

| Check | Result |
|---|---|
| `python -m py_compile app.py` | ✓ pass |
| App boots (`python app.py`) | ✓ pass |
| Regular mode render order matches §2 | ✓ pass |
| Focus mode render order matches §2 | ✓ pass |
| No console errors on initial render (both modes) | ✓ pass |
| Chain+Onion default = 25 rows (when total > 25) | ✓ pass |
| Expand button reveals all rows; collapse restores 25 | ✓ pass |
| Button hidden when total issues ≤ 25 | ✓ pass |
| QuickActions navigation, Export button, row → Document Command Center — no regression | ✓ pass |

---

## 6. Deviations from plan

- **`useStateOv` instead of `React.useState`.** The phase prompt allowed either, requesting whichever matched the local convention. The file destructures `React.useState` as `useStateOv` at line 6, so the local form was used — consistent with `QuickActions` at lines 656–657. Not a real deviation; in line with §3 mandatory behavior ("match existing JSX style").
- **`marginBottom: 20` on the ProjectStats/SystemStatus container** left untouched. The plan permitted setting it to 0 OR leaving it; leaving it produced the smaller diff. Container is now last in the page; the residual bottom margin is harmless.

No other deviations.

---

## 7. Pre-existing observations (not actioned)

- `useMemo` is destructured at line 6 but appears unused in `overview.jsx`. Per surgical-changes rule it was not removed; flagged here for a future cleanup pass.

---

## 8. Context / README updates

- `/context/` folder does not exist at repo root → no `/context/03_UI_FEED_MAP.md` or `/context/07_OPEN_ITEMS.md` updates made (per original plan §10: "If `context/` does not contain these files, skip — do not create new context files in this phase").
- `README.md` reviewed for conflicts with the new dashboard order:
  - "What Not To Touch" (line 111+) lists only `src/*` files — no conflict.
  - "JANSA UI Architecture" (line 449+) describes data flow, not screen layout. The `overview.jsx` row in the file table reads "Dashboard KPIs" — still accurate.
  - **No README change required.**

---

## 9. Done definition (from original plan §11)

- ✅ App launches cleanly in both Focus and Regular modes.
- ✅ Render order matches §2 above.
- ✅ Chain+Onion default = 25 rows; expand/collapse works; button hidden when ≤ 25 total.
- ✅ Diff scoped only to `ui/jansa/overview.jsx`.
- ✅ No console errors.

Phase 1 closed.

---

## 10. Lesson learned (added retroactively)

Mid-session investigation of Phase 2 surfaced a sandbox tooling hazard that affected diagnosis (not Phase 1's actual work, which was UI-only and verified via the Read tool and a live app run). For all subsequent phases:

> Use the **Read tool** — never bash `wc`/`grep`/`cat`/`head`/`tail` — to verify file content, size, or function presence in Windows-mounted source files. The Cowork sandbox's Linux mount caches a stale view that has falsely reported `app.py` as 864 lines when it was actually ~1200. If bash contradicts the Read tool, the Read tool wins. Bash is fine for executing scripts; not for reasoning about source-file state.

Documented in `context/11_TOOLING_HAZARDS.md` and embedded in every other phase MD's standard rules block.
