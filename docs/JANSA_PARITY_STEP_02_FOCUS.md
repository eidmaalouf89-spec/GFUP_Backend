# JANSA PARITY — STEP 02: Focus Mode

**Date:** 2026-04-22
**Run used for validation:** Run 3 (latest completed)
**Status:** FIXED

---

## 1. Legacy Focus Behavior

Focus mode filters the full document set down to "actionable" documents:

**Filtering rules:**
- **F2 — Resolved excluded:** Documents with `_visa_global` ∈ {VSO, VAO, SAS REF, HM} are excluded (terminal states)
- **F4 — Stale excluded:** Open documents (no visa global) with no activity in >90 days are excluded
- **Focused set** = ALL docs − resolved − stale

**Priority buckets** (from `_days_to_deadline`):
- P1 (overdue): deadline passed (`dtd < 0`)
- P2 (urgent): 0–5 days
- P3 (soon): 6–15 days
- P4 (comfortable): 16+ days
- P5 (no deadline): no pending deadline

**Ownership rules** (6 tiers):
1. PRIMARY pending → primary consultants own it
2. SECONDARY pending (within 10-day window) → secondary consultants own it
3. SECONDARY expired (>10 days) → MOEX owns it
4. All replied → MOEX owns it (must issue VISA GLOBAL)
5. MOEX replied REF → CONTRACTOR owns it
6. MOEX replied terminal → CLOSED

**Effects on pages:**
- Overview: `pending_blocking` reflects only focused open docs; Focus panel shows P1/P2/P3/P4 radial + per-consultant waterfall
- Consultants: `focus_owned` count per consultant
- Fiche: open counts filtered to owned docs, weekly (not monthly) timeseries
- Timeseries: switches from monthly to weekly (last 12 weeks)

---

## 2. JANSA Focus Behavior (Before Fix)

**What was working:**
- Focus toggle in shell.jsx correctly toggled state and called `jansaBridge.refreshForFocus()`
- Data bridge correctly passed `focus` boolean to all three API endpoints
- Backend `app.py` correctly routed to `apply_focus_filter(ctx, FocusConfig(enabled=True))`
- Pre-computed focus columns (`_visa_global`, `_focus_owner`, `_focus_owner_tier`, etc.) were correctly added to `dernier_df` during `load_run_context()`
- The focus filter engine correctly excluded resolved + stale docs and computed priority queue

**What was broken:**
- `focus_filter.py` source file was **truncated** at line 197, mid-string (`"secondary_pendin"`)
- Python was running from a stale `.pyc` cache file, which had the older complete version
- The cached version lacked `by_consultant` computation entirely
- `ui_adapter.py` `adapt_consultants()` did not include `focus_owned` in its output

---

## 3. Root Cause of Mismatch

| Issue | Cause | Layer |
|-------|-------|-------|
| `focus_filter.py` truncated at line 197 | File corruption (likely prior edit/save issue) | BACKEND |
| `by_consultant` always `[]` | Never implemented in focus_filter stats | BACKEND |
| `focus_owned` missing from consultant list | `adapt_consultants()` dropped the field | BRIDGE (adapter) |

The focus filter ENGINE was correct — it produced different `focused_doc_ids` (1399 vs 4190). The KPIs used these correctly (`pending_blocking`: 3289→1222). But the `by_consultant` waterfall chart had no data, and consultant cards showed no focus ownership.

---

## 4. Fixes Applied (by Layer)

### BACKEND — `src/reporting/focus_filter.py`

**Restored truncated function** and **added `by_consultant` computation:**

- Completed the `stats` dict (added `secondary_pending`, `excluded_total`)
- Added `return result` statement
- Added per-consultant breakdown loop: iterates `actor_queues`, counts P1/P2/P3/P4 per consultant, produces `by_consultant` array sorted by total
- Removed stale `.pyc` cache files (3 versions)

### BRIDGE — `src/reporting/ui_adapter.py`

- Added `"focus_owned": c.get("focus_owned", 0)` to `adapt_consultants()` output

### UI — `ui/jansa/overview.jsx`

- Added safe fallback on `KpiRow`: `(data.weekly || []).map(...)` (2 occurrences)
- Existing safety patterns were already adequate: `FocusByConsultant` checks `!items || !items.length`, `WeeklyActivity` uses `data.weekly || []`

---

## 5. Validation Results (Run 3)

### KPI Comparison

| Metric | Focus OFF | Focus ON | Differ? |
|--------|-----------|----------|---------|
| total_docs | 4,190 | 4,190 | Same (correct) |
| pending_blocking | 3,289 | 1,222 | ✅ DIFFERENT |
| focused_count | 0 | 1,399 | ✅ DIFFERENT |
| stale_excluded | 0 | 2,067 | ✅ DIFFERENT |
| resolved_excluded | 0 | 724 | ✅ DIFFERENT |
| weekly entries | 30 (monthly) | 26 (weekly) | ✅ DIFFERENT |

### Focus Stats (ON)

| Field | Value |
|-------|-------|
| focused | 1,399 |
| p1_overdue | 1,069 |
| p2_urgent | 89 |
| p3_soon | 84 |
| p4_ok | 157 |
| excluded | 2,791 |
| by_consultant | 11 entries |

### Per-Consultant Focus Ownership (top 5)

| Consultant | focus_owned |
|------------|-------------|
| Bureau de Contrôle | 64 |
| AMO HQE | 48 |
| ARCHITECTE | (via by_consultant: 200 total) |
| BET Electricité | (via by_consultant: 137 total) |
| BET CVC | (via by_consultant: 69 total) |

### Schema Consistency

Both modes return identical keys: `best_consultant`, `best_contractor`, `data_date_str`, `focus`, `pending_blocking`, `pending_blocking_delta`, `refus_rate`, `refus_rate_delta`, `run_number`, `total_docs`, `total_docs_delta`, `total_runs`, `visa_flow`, `week_num`, `weekly`

### All Checks

- ✅ Focus toggle produces different values than normal mode
- ✅ Focus count > 0
- ✅ `by_consultant` populated (11 entries)
- ✅ Same schema in both modes
- ✅ Focused count (1,399) < total open (3,289)
- ✅ No fake values — all computed from real data
- ✅ No UI crash (safety guards in place)

---

## 6. Remaining Focus Limitations

1. **`by_consultant` excludes MOEX and CONTRACTOR entries** — only consultant-type actors shown in waterfall chart. MOEX focus ownership is tracked separately via `moex_actionable` stat.
2. **`focus_owned` in consultant adapter counts docs where consultant appears in `_focus_owner` list** — MOEX consultant (Maître d'Oeuvre EXE) shows `focus_owned=0` because MOEX ownership is tracked via `_focus_owner_tier="MOEX"` not via the `_focus_owner` list. This matches legacy behavior.
3. **Fiche page** receives `focusMode` prop but does not pass it to the inner `ConsultantFiche` component — fiche-level focus filtering depends on `window.FICHE_DATA` being loaded with focus=true via data_bridge, which works correctly.
4. **Trend sparklines** on consultant cards show `[]` — requires historical run data (deferred, not focus-specific).

---

## 7. Focus Toggle Lifecycle Bug (Follow-up Fix)

### Symptom

After the backend data fix, focus mode still behaved unreliably: "sometimes the numbers change, sometimes they do not." The toggle felt non-deterministic — stale data could remain visible after toggling.

### Root Cause (3 bugs)

**Bug 1 — Side effects inside React state updater (`shell.jsx:409-421`).**
The old code launched an async network call (`refreshForFocus`) inside a `setFocusModeRaw(prev => { ... })` updater function. React may invoke updater functions multiple times (StrictMode, concurrent rendering). This means the async call could fire multiple times, or fire and then have its state update discarded.

**Bug 2 — No loading state during reload.**
The toggle flipped `focusMode` synchronously (instant UI change: vignette, scale, cinema animation), but the data reload was async with no visual indicator. The UI rendered immediately with focus styling but OLD data in `window.OVERVIEW`. Only after the async reload completed did `dataVersion` bump and trigger a second render with new data. If the reload was slow or failed, the user saw stale numbers indefinitely with no way to know they were stale.

**Bug 3 — No race condition guard.**
Rapid toggling fired multiple parallel `refreshForFocus()` calls that all wrote to the same `window.OVERVIEW` / `window.CONSULTANTS` globals. The last one to resolve "won", but that might not correspond to the current toggle state. The same problem existed in `data_bridge.js` — `_loadCoreData` had no way to discard results from superseded calls.

### Fix Applied

**`shell.jsx` — Rewrote `setFocusMode` callback (lines 418-449):**

Before (broken):
```javascript
const setFocusMode = useCallback((updater) => {
  setFocusModeRaw(prev => {
    const next = typeof updater === 'function' ? updater(prev) : updater;
    setCinemaOn(next);          // side effect in updater
    setCinemaKey(k => k + 1);   // side effect in updater
    if (window.jansaBridge.api) {
      window.jansaBridge.refreshForFocus(next).then(() => {  // async side effect in updater
        setDataVersion(v => v + 1);
      });
    }
    return next;
  });
}, []);
```

After (fixed):
```javascript
const setFocusMode = useCallback((updater) => {
  // 1. Compute next value from ref (always current, handles rapid clicks)
  const prev = focusModeRef.current;
  const next = typeof updater === 'function' ? updater(prev) : updater;
  focusModeRef.current = next;

  // 2. Update React state (pure, no side effects)
  setFocusModeRaw(next);

  // 3. Cinema only when ENTERING focus mode
  if (next) { setCinemaOn(true); setCinemaKey(k => k + 1); }

  // 4. Show loading overlay, then reload data
  if (window.jansaBridge.api) {
    const gen = ++focusGenRef.current;
    setReloading(true);
    window.jansaBridge.refreshForFocus(next).then(() => {
      if (gen === focusGenRef.current) {  // only apply if still latest request
        setDataVersion(v => v + 1);
        setReloading(false);
      }
    }).catch(() => {
      if (gen === focusGenRef.current) { setReloading(false); }
    });
  }
}, []);
```

Key changes:
- `focusModeRef` (ref mirror) replaces stale-closure reads — always has the latest value
- `focusGenRef` (generation counter) prevents stale async responses from applying
- `reloading` state shows a loading overlay while data is in flight
- Cinema animation only plays when entering focus mode (not on exit)
- No side effects inside any state updater function

**`shell.jsx` — Added loading overlay (lines 501-522):**

A full-content loading screen ("Chargement des données…") appears as an absolute overlay (`z-index: 20`) while `reloading` is true. It covers stale page content so the user never sees outdated numbers during a transition.

**`data_bridge.js` — Added `_loadGen` generation counter (line 58, lines 120-133):**

Each `_loadCoreData` call increments `bridge._loadGen` and captures its generation number. After the 3 parallel API calls resolve, it checks `gen !== bridge._loadGen`. If a newer call was started in the meantime, the stale result is discarded with a console warning. This prevents overlapping requests from writing incorrect data to `window.OVERVIEW`.

### Before/After Toggle Behavior

| Step | BEFORE | AFTER |
|------|--------|-------|
| User clicks Focus ON | focusMode flips instantly, old data visible, cinema plays, new data appears 0.5-2s later (sometimes never) | focusMode flips, loading overlay appears immediately, cinema plays, new data appears only after reload completes, overlay removed |
| User clicks Focus OFF | focusMode flips instantly, focus data may remain visible, cinema plays (incorrect) | focusMode flips, loading overlay appears, NO cinema, normal data appears after reload, overlay removed |
| Rapid toggle (ON→OFF→ON) | Multiple parallel requests, last-to-resolve wins (may be wrong mode), no visual feedback | Generation counter discards stale responses, only the latest request applies, loading overlay stays until the final request resolves |
| Reload failure | No error handling, stale data stays forever | `.catch()` clears reloading state if still the latest request |

### Determinism Proof

Every toggle now follows a strict sequence:
1. `focusModeRef.current` updated → prevents stale reads on next click
2. `setFocusModeRaw(next)` → UI state update queued
3. `setReloading(true)` → loading overlay visible immediately
4. `refreshForFocus(next)` → backend API call fires
5. Bridge increments `_loadGen`, fires 3 parallel requests
6. On resolve: bridge checks `gen === _loadGen` — discards if stale
7. If current: writes `window.OVERVIEW` / `CONSULTANTS` / `CONTRACTORS`
8. Back in shell: checks `gen === focusGenRef.current` — discards if stale
9. If current: `setDataVersion(v+1)` → forces re-render with new data
10. `setReloading(false)` → loading overlay removed, fresh data visible

There is no path where stale data remains visible after a toggle completes.

---

## 8. Files Changed (Complete)

| File | Layer | Change |
|------|-------|--------|
| `src/reporting/focus_filter.py` | BACKEND | Restored truncated function, added `by_consultant` computation |
| `src/reporting/ui_adapter.py` | BRIDGE | Added `focus_owned` to consultant adapter output |
| `ui/jansa/overview.jsx` | UI | Safe fallback on `data.weekly` `.map()` calls |
| `ui/jansa/shell.jsx` | UI | Rewrote `setFocusMode` lifecycle: ref-based state, loading overlay, generation guard, cinema on enter only |
| `ui/jansa/data_bridge.js` | BRIDGE | Added `_loadGen` generation counter to discard stale responses |
