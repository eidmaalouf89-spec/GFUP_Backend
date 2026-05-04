# Phase 6X.B2 — `_resolve_data_date` Caller Audit

**Phase:** 6X.B2 (read-only)  
**Date:** 2026-05-04  
**Status:** AUDIT COMPLETE — awaiting user review before 6X.C / 6X.D  
**Predecessor audits:** 6X.A, 6X.A3 (date.today scan + DCC deadline truth)

---

## 1. Scope

This audit traces every call site of `_resolve_data_date()` and all places where `ctx.data_date` is consumed or checked, to determine whether the function's silent fallback to `date.today()` (at `consultant_fiche.py:1255`) and the two parallel fallbacks at `contractor_quality.py:322,452` can be safely removed without breaking production or test code. The audit follows the data flow from `RunContext` construction (where `data_date` is populated) through all reporting modules, to confirm whether `data_date` is guaranteed non-None at runtime.

---

## 2. Method

**Files inspected:**
- `src/reporting/consultant_fiche.py` — defines `_resolve_data_date`, 2 direct call sites
- `src/reporting/contractor_quality.py` — 2 fallback sites (`ref_today = ctx.data_date or date.today()`)
- `src/reporting/data_loader.py` — `RunContext` construction, `_read_ged_data_date()` function
- `src/reporting/document_command_center.py` — reads `ctx.data_date` directly
- `src/reporting/chain_timeline_attribution.py` — validates `ctx.data_date` is non-None
- `src/reporting/aggregator.py` — logs `ctx.run_date`
- `app.py` — 1 direct call to `_resolve_data_date()`
- `main.py` — entry point, does not call `_resolve_data_date()`
- All scripts under `scripts/` — traced for `load_run_context()` calls

**Tools used:** Grep for `_resolve_data_date(`, `RunContext(`, `ctx.data_date`, `ctx.run_date` ; Read for line-by-line inspection and function boundaries.

**Key search terms:**
- `_resolve_data_date(` → 3 call sites (2 in consultant_fiche.py, 1 in app.py)
- `RunContext(` → 4 constructor sites (all in data_loader.py)
- `ctx.data_date or date.today()` → 2 sites (contractor_quality.py lines 322, 452)
- `ctx.data_date` direct reads → 5 additional modules

---

## 3. RunContext construction sites (where `data_date` is set)

| # | File | Line(s) | Function / context | How `data_date` is populated | Can be None? | Notes |
|---|---|---|---|---|---|---|
| 1 | `data_loader.py` | 551–569 | `_load_from_flat_artifacts()` inside `_load_run_context()` | Via `flat_doc_meta` dict lookup: `meta.get("data_date", "")` parsed to `date` object at line 488 | **YES** — if `flat_doc_meta` is empty or dict values lack `"data_date"` key | Called when FLAT_GED.xlsx cache is available; this is the **fast path** for UI loader |
| 2 | `data_loader.py` | 716–721 | `_load_run_context()` fallback (no run found) | **NOT SET** — defaults to `None` (dataclass default) | **YES** — intentional | Degraded mode; returns `data_date=None` because no run row exists in DB |
| 3 | `data_loader.py` | 734–739 | `_load_run_context()` fallback (run not found) | **NOT SET** — defaults to `None` | **YES** — intentional | Degraded mode; run_number exists but row not found |
| 4 | `data_loader.py` | 909–930 | `_load_run_context()` main path (GED available) | Via `_read_ged_data_date(ged_path)` at line 804; can return `None` if GED Détails sheet missing or parsing fails | **YES** — if GED Détails sheet not found or date cell unparseable | Main production path; **degraded_mode=False** but **data_date can still be None** |

**Summary:** All 4 constructor sites either (a) explicitly set `data_date=None` (fallback cases), or (b) call `_read_ged_data_date()` which returns `Optional[date]` and can be `None`. Only constructor #1 (flat mode) attempts parsing, and it can still fail silently and leave `data_date=None`.

---

## 4. Direct call sites of `_resolve_data_date` in `consultant_fiche.py`

| # | Line | Caller function | Args passed | Business-impacting? | Can `ctx.data_date` be None at this point? | Evidence |
|---|---|---|---|---|---|---|
| 1 | 164 | `build_consultant_fiche(ctx, consultant_name, ...)` | `ctx` | **YES** — result feeds `prev_date = data_date - timedelta(days=7)` (line 165) and downstream to `_attach_derived(docs, data_date, ...)` which uses it for lateness/deadline logic | **YES** — ctx passed from app.py line 686, which calls `load_run_context(BASE_DIR)` at line 682; no guarantee `data_date` is populated | See §3 constructor #4: `_read_ged_data_date()` can return None; warning added but fallback silently uses date.today() |
| 2 | 324 | `build_sas_fiche(ctx, ...)` | `ctx` | **YES** — result feeds SAS status logic and timeline fields; used for deputy-check lateness | **YES** — same path as #1; ctx.data_date can be None | Same upstream path |

**Details:**
- Line 164 is inside `build_consultant_fiche()` (starts line 143), which is a public API called by `app.py:686` (fast HTTP endpoint) and by audit scripts.
- Line 324 is inside `build_sas_fiche()` (starts ~line 310), which builds SAS-specific fiche (also called from `build_consultant_fiche` line 157 when consultant == "MOEX SAS").
- Both call sites are **business-critical** because the resulting `data_date` is used to compute:
  - `prev_date` for week-ago comparisons (line 165)
  - Dormant document flags (via `_attach_derived()`)
  - Lateness metrics in SAS and consultant workflows

---

## 5. Indirect / fallback callers (the `date.today()` branches we want to remove)

### 5.1 `consultant_fiche.py:1250–1258` — final fallback in `_resolve_data_date()`

**Exact code:**
```python
def _resolve_data_date(ctx: RunContext) -> date:
    d = getattr(ctx, "data_date", None)
    if d is None:
        # Fallback to run_date; warn.
        ctx.warnings.append("data_date missing on ctx; falling back to run_date")
        d = datetime.fromisoformat(ctx.run_date).date() if ctx.run_date else date.today()
    if isinstance(d, datetime):
        d = d.date()
    return d
```

**Condition:** Fires when:
1. `ctx.data_date` is `None` (which can happen per §3), AND
2. `ctx.run_date` is `None` or non-parseable (e.g., empty string or invalid ISO format)

**Result:** Falls back to `date.today()` and adds a warning to `ctx.warnings`.

**Business impact:** This is the **ultimate silent fallback**. If both `ctx.data_date` and `ctx.run_date` fail to parse or are missing, the consultant fiche will use today's date instead of the actual GED extract date. This affects:
- Dormancy counts (e.g., a document is dormant relative to today, not the actual data_date)
- Lateness metrics (deadlines computed from today instead of from the GED timestamp)
- SAS refusal rate trends (historical anchored to today)

### 5.2 `contractor_quality.py:322` — `build_contractor_quality_peer_stats()`

**Exact code (line 322):**
```python
ref_today = ctx.data_date or date.today()
```

**Calling function:** `build_contractor_quality_peer_stats(ctx, chain_timelines=None)` (line 306).

**Usage — CORRECTED (team-leader verification, supersedes earlier draft):** `ref_today` IS actively used inside the per-contractor loop at lines 362–363:

```python
for d in _dormant_list(emetteur_dernier, "REF", ref_today) + \
         _dormant_list(emetteur_dernier, "SAS REF", ref_today):
    nm = str(d.get("numero", "")).strip()
    if nm:
        dormant_days_by_numero[nm] = max(
            dormant_days_by_numero.get(nm, 0),
            int(d.get("days_dormant", 0))
        )
```

The result `dormant_days_by_numero` then feeds `_contractor_delay_for_chain(...)` at line 372 → `avg_delays.append(...)` at line 375 → final `avg_contractor_delay_days` percentile in the returned dict (line 389). This is **business-critical** input to the cross-contractor peer-stats payload consumed by ENTREPRISE quality reporting.

**Business impact:** Same shape as line 452. Silent fallback to `date.today()` causes `_dormant_list()` to anchor against a moving target; `dormant_days_by_numero` and ultimately `avg_contractor_delay_days` percentiles drift every day if `ctx.data_date` is None. NOT dead code.

### 5.3 `contractor_quality.py:452` — `build_contractor_quality()`

**Exact code (line 452):**
```python
ref_today = ctx.data_date or date.today()
```

**Calling function:** `build_contractor_quality(ctx, contractor_code, peer_stats=None, ...)` (line 395).

**Usage:** `ref_today` is passed immediately to dormancy functions at lines 453–454:
```python
dormant_ref = _dormant_list(emetteur_dernier, "REF", ref_today)
dormant_sas_ref = _dormant_list(emetteur_dernier, "SAS REF", ref_today)
```

**Function signature of `_dormant_list`:**
```python
def _dormant_list(df: pd.DataFrame, status_filter: str, ref_date: date) -> list[dict]:
    # Uses ref_date to compute (ref_date - visa_date).days
```

**Business impact:** This is **actively used** to compute dormant document counts. The `ref_date` parameter is critical for determining whether a document with status "REF" is dormant (days_dormant > threshold). If `ctx.data_date` is `None` and falls back to `date.today()`, dormancy metrics will be **wildly inaccurate** because the anchor date shifts every day instead of staying fixed to the GED extract date.

---

## 6. Other reporting modules that read `ctx.data_date` (for context only — NOT to be modified by 6X.C/6X.D)

| Module | Usage | Has fallback? | Notes |
|--------|-------|---|---|
| `document_command_center.py` | Line 286: `data_date = ctx.data_date`; used at line 289 to compute days since response; line 357: same pattern | **YES — implicit** | At line 287–288: `if data_date is None: return None`. Gracefully handles None by bailing out. No date.today() fallback here. |
| `chain_timeline_attribution.py` | Line 541–542: **raises ValueError** `"ctx.data_date is required (got None)"` | **NO — explicit raise** | This is a **hard requirement**; build_chain_timelines_attribution will crash if data_date is None. This is called by `build_contractor_quality()` indirectly via chain loading. |
| `aggregator.py` | Line 63: logs `ctx.run_date` (not data_date) | N/A | Summary reporting; no fallback needed. |

**Key insight:** `chain_timeline_attribution.py` **explicitly validates** that `ctx.data_date` must be non-None. This means:
- If you remove the fallback at contractor_quality.py:452 and pass None to `_dormant_list()`, and then later call chain timeline building, it will **crash at chain_timeline_attribution.py:542**.
- The two fallbacks (contractor_quality.py:322, :452) are **necessary guards** against chain-timeline failures in current code.

---

## 7. Per-call-site None-risk verdict

### Summary of upstream chains

**Path A: Production / App HTTP endpoint** (`app.py:686`)
```
app.py:686 _resolve_data_date(ctx)
  ↑
  ctx = load_run_context(BASE_DIR)  [app.py:682]
    ↑
    data_loader.py:_load_run_context() [constructor #4, main path]
      ↑
      data_date_val = _read_ged_data_date(ged_path) [line 804]
        ↓
        Returns Optional[date]; can be None if:
          - Détails sheet not found
          - Date cell unparseable
          - GED file not readable
```

**Verdict for Path A (app.py:686):**
- **Can `ctx.data_date` be None?** **YES**
- **Will it reach `_resolve_data_date`?** **YES**
- **Evidence:** If GED Détails sheet is missing or malformed, `_read_ged_data_date()` returns None (line 402). The RunContext is still created with `data_date=None` and `degraded_mode=False` (line 915). The app.py endpoint then calls `_resolve_data_date(ctx)` at line 686 with a None data_date, triggering the fallback at line 1255.

### Path B: Scripts via `load_run_context()`
All scripts that call `load_run_context(BASE_DIR)` follow Path A (constructor #4). They all face the same risk.

**Scripts affected:**
- `audit_counts_lineage.py:575`
- `build_counter_attack.py:24`
- `audit_focus_visa_source.py:190`
- `audit_ui_payload_full_surface.py:728`
- `audit/_common.py:79`
- Potentially others via imports of shared functions

### Path C: Unit tests (UNKNOWN — no test files audited)
If there are unit tests that construct `RunContext()` manually without setting `data_date`, they **will break** if the fallback is removed. This is a **blind spot** in the current audit (tests are not in src/ or scripts/).

---

## 8. Recommended safe-fix shape (per file)

### 8.1 `consultant_fiche.py:1250–1258` final fallback

**Current behavior:**
```python
def _resolve_data_date(ctx: RunContext) -> date:
    d = getattr(ctx, "data_date", None)
    if d is None:
        ctx.warnings.append("data_date missing on ctx; falling back to run_date")
        d = datetime.fromisoformat(ctx.run_date).date() if ctx.run_date else date.today()
    ...
```

**Recommendation: RAISE**

```python
def _resolve_data_date(ctx: RunContext) -> date:
    d = getattr(ctx, "data_date", None)
    if d is None:
        # Try fallback to run_date
        if ctx.run_date:
            try:
                d = datetime.fromisoformat(ctx.run_date).date()
            except (ValueError, TypeError):
                pass
        if d is None:
            raise ValueError(
                "data_date is required for all reporting operations; "
                "both ctx.data_date (from GED Détails) and ctx.run_date (from run_memory) are unavailable. "
                "Ensure load_run_context() successfully parsed GED, or provide explicit data_date."
            )
    if isinstance(d, datetime):
        d = d.date()
    return d
```

**Justification:**
- Callers in production (app.py, scripts) all derive ctx from `load_run_context()`, which is responsible for populating `data_date`.
- If `_read_ged_data_date()` fails, **that is a data integrity issue** that should be visible (log warning, but don't silently use today).
- If data_date is truly missing, the entire reporting pipeline is degraded, and silently anchoring to today will give **incorrect lateness metrics** (especially dangerous in SAS refusal trends).
- **Run_date as secondary fallback is reasonable** (it's set to `completed_at` from the run_memory DB, which is reliable). Try parsing it first.
- **Raising makes the failure explicit** and will alert the team (via error log) if GED extraction starts failing.

---

### 8.2 `contractor_quality.py:322`

**Current behavior:**
```python
ref_today = ctx.data_date or date.today()
```

**Status — CORRECTED:** Actively used at lines 362–363 by `_dormant_list(...)` calls inside the per-contractor loop. NOT dead code (earlier draft of this audit erred on that point and is overridden here).

**Recommendation: RAISE** (same shape as §8.3)

```python
if ctx.data_date is None:
    raise ValueError(
        "data_date is required for peer-stats dormancy computations in "
        "build_contractor_quality_peer_stats(); ctx.data_date is None. "
        "Ensure load_run_context() successfully parsed GED."
    )
ref_today = ctx.data_date
```

**Justification:**
- `ref_today` flows into `_dormant_list()` → `dormant_days_by_numero` → `_contractor_delay_for_chain()` → `avg_contractor_delay_days` percentile in the returned peer-stats dict.
- Silent fallback to `date.today()` makes `avg_contractor_delay_days` time-variant: a doc that was dormant N days at GED extract appears as N + (today − data_date) days when peer stats are computed days later. This corrupts the cross-contractor ranking.
- The validation should fire **before** the per-contractor loop, not inside it (loop runs 29× so failing fast is preferable).

---

### 8.3 `contractor_quality.py:452`

**Current behavior:**
```python
ref_today = ctx.data_date or date.today()
dormant_ref = _dormant_list(emetteur_dernier, "REF", ref_today)
dormant_sas_ref = _dormant_list(emetteur_dernier, "SAS REF", ref_today)
```

**Recommendation: RAISE**

```python
if ctx.data_date is None:
    raise ValueError(
        "data_date is required for dormancy and lateness computations in "
        "build_contractor_quality(); ctx.data_date is None. "
        "Ensure load_run_context() successfully parsed GED."
    )
ref_today = ctx.data_date
dormant_ref = _dormant_list(emetteur_dernier, "REF", ref_today)
dormant_sas_ref = _dormant_list(emetteur_dernier, "SAS REF", ref_today)
```

**Justification:**
- `ref_today` **is actively used** to compute dormancy metrics (days since last response, etc.).
- Dormancy data is **business-critical** for identifying stuck/delayed documents.
- Silently falling back to `date.today()` means:
  - Dormant REF counts will shift every single day (if a doc was dormant yesterday at GED date, it's "more dormant" today).
  - SAS refusal trends will be anchored incorrectly (historical data will shift).
  - This violates the audit-log principle: reports should be reproducible and time-invariant.
- **Raising ensures data integrity** and fails loudly if data_date is missing.

---

## 9. Risks of removing the fallback

**Concrete failure modes:**

1. **If GED Détails sheet is missing or malformed:**
   - `_read_ged_data_date()` returns None (line 402).
   - `RunContext` is created with `data_date=None` and `degraded_mode=False`.
   - App endpoint calls `_resolve_data_date(ctx)` at line 686.
   - **Currently:** Falls back to `date.today()` (silent, warning added).
   - **After fix:** Raises ValueError (loud, visible failure).
   - **Risk level:** **MEDIUM** — GED Détails sheet should be stable, but if it's not, the error will be visible (good) but the UI will show an error (bad UX).

2. **If run_date is not populated or is malformed:**
   - This is a data_loader bug, not normal.
   - **Currently:** Falls back to `date.today()`.
   - **After fix (with run_date secondary fallback):** Raises if run_date also fails.
   - **Risk level:** **LOW** — run_date comes from the run_memory DB and is always set.

3. **If unit tests construct bare `RunContext(...)` without data_date:**
   - Example: `ctx = RunContext(run_number=1, run_status="SUCCESS", run_date="", ...)` (omits data_date).
   - **Currently:** Falls back to `date.today()` silently.
   - **After fix:** Raises ValueError.
   - **Risk level:** **MEDIUM** — depends on test coverage. If tests don't set data_date, they will fail. This is **fixable** (update test fixtures), but it's **not visible** until tests run.
   - **Audit note:** We have not audited test files; they may exist in `tests/` or `test_*.py` files.

4. **If scripts call `_resolve_data_date()` directly (not via load_run_context):**
   - Unlikely, but possible.
   - **Risk level:** **LOW** — grep found only 3 call sites, all via load_run_context or app.py.

5. **If `chain_timeline_attribution.py` validation is reached:**
   - If contractor_quality.py line 452 raises instead of falling back, and `build_contractor_quality()` is called with None data_date:
   - **Currently:** Falls back to date.today(), silently.
   - **After fix:** Raises at contractor_quality.py:452, chain_timeline_attribution.py:542 is not reached.
   - **Risk level:** **NONE** — the fix at :452 prevents the crash at :542.

---

## 10. Recommended order for 6X.C / 6X.D

### Can they run in parallel?

**YES — with caveats.**

Both patches are **independent** in the sense that they don't modify the same lines in the same file. However:

- **6X.C (consultant_fiche.py:1255)** raises an error if data_date is None.
- **6X.D (contractor_quality.py:322 & :452)** also raises errors if data_date is None (line 452).

**Order recommendation:**

1. **Run 6X.C first** (patch consultant_fiche.py).
   - This is the **root validator**. If data_date is None, the error will surface here.
   - Tests that call `build_consultant_fiche()` will fail if data_date is missing.

2. **Then run 6X.D** (patch contractor_quality.py).
   - This is a **secondary validator**. It catches cases where code calls `build_contractor_quality()` directly (scripts, tests) without going through consultant_fiche.
   - Errors at :452 will be caught by tests for contractor_quality.

**Parallel execution:** If you run both patches in a CI/CD pipeline, they can be applied in parallel because:
- They touch different files.
- They don't have cross-file dependencies (the error cascade is one-way: consultant_fiche calls contractor_quality, not vice versa).

**However:** If either patch causes test failures, **revert both** and fix test fixtures before retrying.

---

## 11. Appendix — raw findings

### A. Full grep output for `_resolve_data_date(`

```
C:\Users\GEMO 050224\Desktop\cursor\GF updater v3\app.py:686:            data_date = _resolve_data_date(ctx)
C:\Users\GEMO 050224\Desktop\cursor\GF updater v3\src\reporting\consultant_fiche.py:164:    data_date = _resolve_data_date(ctx)
C:\Users\GEMO 050224\Desktop\cursor\GF updater v3\src\reporting\consultant_fiche.py:324:    data_date = _resolve_data_date(ctx)
C:\Users\GEMO 050224\Desktop\cursor\GF updater v3\src\reporting\consultant_fiche.py:1250:def _resolve_data_date(ctx: RunContext) -> date:
```

**Summary:** 3 call sites + 1 definition. Call sites are:
1. `app.py:686` — HTTP endpoint for consultant documents list
2. `consultant_fiche.py:164` — inside `build_consultant_fiche()`
3. `consultant_fiche.py:324` — inside `build_sas_fiche()`

---

### B. Full grep output for `RunContext(`

```
src/reporting/data_loader.py:551:        return RunContext(
src/reporting/data_loader.py:716:        return RunContext(
src/reporting/data_loader.py:734:        return RunContext(
src/reporting/data_loader.py:909:    ctx = RunContext(
```

**Summary:** 4 constructor sites, all in `data_loader.py`:
1. Line 551 — `_load_from_flat_artifacts()` (fast path, FLAT_GED cache)
2. Line 716 — `_load_run_context()` fallback (no completed run found)
3. Line 734 — `_load_run_context()` fallback (run not found in DB)
4. Line 909 — `_load_run_context()` main path (GED available or degraded mode)

Constructors at lines 716, 734 explicitly set `data_date=None` (no argument, defaults via dataclass).
Constructors at lines 551, 909 set `data_date=data_date_val`, which comes from either:
- `flat_doc_meta` dict (line 551)
- `_read_ged_data_date(ged_path)` (line 804, returned to line 926 as `data_date_val`)

---

### C. Full grep output for `ctx.data_date` and `ctx.run_date` in `src/reporting/`

```
contractor_quality.py:322:    ref_today = ctx.data_date or date.today()
contractor_quality.py:452:    ref_today = ctx.data_date or date.today()
document_command_center.py:284:    Returns (ctx.data_date - response_date).days if found, else None.
document_command_center.py:286:    data_date = ctx.data_date
document_command_center.py:357:    data_date = ctx.data_date
aggregator.py:63:        "run_date": ctx.run_date,
chain_timeline_attribution.py:542:        raise ValueError("ctx.data_date is required (got None)")
consultant_fiche.py:9:DATA_DATE comes from ctx.data_date (extracted from GED's Détails sheet upstream).
consultant_fiche.py:1255:        d = datetime.fromisoformat(ctx.run_date).date() if ctx.run_date else date.today()
```

**Breakdown:**
- **contractor_quality.py:322, :452** — the two fallback sites (focus of audit)
- **document_command_center.py:286, :357** — explicit None-check, bails gracefully
- **chain_timeline_attribution.py:542** — hard requirement (raises if None)
- **aggregator.py:63** — logs run_date (not data_date), no fallback needed
- **consultant_fiche.py:1255** — the ultimate fallback (focus of audit)

---

