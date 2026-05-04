# Phase 6B — Intelligence Endpoints (Facets + Filtered Documents)

This MD is **self-contained**. An agent assigned only this phase can execute it cold without reading any other file in `docs/implementation/`.

> **Phase 6 has been split into four sub-phases (6A → 6B → 6C → 6D).** This is 6B. **Phase 6A must already be merged** and `output/intermediate/INTELLIGENCE_TAGS.csv` must exist. Do NOT proceed to 6C/6D in the same implementation pass.

---

## 1. Objective

Expose two read-only endpoints in `app.py` that the future Intelligence UI page will call:

1. `get_intelligence_facets()` — counts per filter chip, computed from `INTELLIGENCE_TAGS.csv`.
2. `get_intelligence_documents(filters, limit=1000, sort="newest")` — filtered list of documents.

Plus the matching bridge methods in `ui/jansa/data_bridge.js`.

This phase does not add a UI page. UI page = Phase 6C. Export + treated state = Phase 6D.

---

## 2. Risk

**MEDIUM.** Read-only endpoints over an existing CSV. No pipeline change, no schema change, no chain_onion touch.

If the agent finds `INTELLIGENCE_TAGS.csv` does not exist, **stop and escalate** — Phase 6A is the prerequisite.

---

## 3. Standard Rules (embedded — do not skip)

### Tooling note — read before any investigation
Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) to verify file content, file size, or function presence in Windows-mounted source files (`app.py`, `src/reporting/*.py`, `ui/jansa/*.jsx`, etc.). The Cowork sandbox's Linux mount caches a stale view of Windows files and has, in past sessions, falsely reported `app.py` as 864 lines when it was actually ~1200, and missed methods like `get_chain_onion_intel` that demonstrably existed. If a bash inspection contradicts the Read tool, the Read tool wins. Do not raise "repo is broken / method missing / file truncated" alarms from bash-only evidence — cross-check with Read first. Bash is fine for *executing* scripts (running `python main.py`, `pytest`, etc.); just don't use it to reason about source-file state. See `context/11_TOOLING_HAZARDS.md`.

### Priorities
1. App must always run.
2. Backend stays source of truth — UI calculates nothing.
3. Preserve working logic.
4. Minimal safe changes.
5. No fake certainty.

### Mandatory behavior
- Read every listed file fully before editing.
- Endpoints read `INTELLIGENCE_TAGS.csv` once and cache by file mtime. Do not re-read on every call.
- All filtering, sorting, and aggregation happen in the backend. UI calculates nothing.
- Filter semantics: within a category (e.g. multiple primary_tags), values are OR-combined. Across categories (primary_tag AND secondary_tag AND lot etc.), AND-combined.
- Default sort: `last_action_date DESC` (newest first), tie-break by `numero ASC`.
- Hard cap: 1000 rows server-side; if the bucket exceeds the cap, return the most recent 1000 + `truncated: true` + `total_count`.
- Missing artifact: every endpoint returns `{"error": "intelligence artifact not yet produced — run the pipeline once to generate it."}` (and empty/zero defaults), so the UI can show a friendly empty state.

### Forbidden moves
- Do NOT modify `src/pipeline/stages/*` or any pipeline file.
- Do NOT modify `src/flat_ged/`, `src/chain_onion/`, `src/run_memory.py`, `src/report_memory.py`.
- Do NOT modify `src/reporting/intelligence_builder.py` (that's Phase 6A's territory; only consume the artifact it produces).
- Do NOT add UI files in this phase. UI is Phase 6C.
- Do NOT add export logic. Export is Phase 6D.
- Do NOT add a new database, ORM, or caching layer beyond a simple in-memory mtime cache.
- Do NOT introduce a new dependency.

### Risk policy
MEDIUM. Apply directly after the plan is restated. Stop and escalate if the artifact is missing (Phase 6A not merged) or if filter semantics described in this MD conflict with what the operator actually wants — confirm filter semantics with the user before coding if any ambiguity arises.

---

## 4. Current State (Findings)

### 4a. Artifact (must exist from Phase 6A)
File: `output/intermediate/INTELLIGENCE_TAGS.csv`. Frozen schema:

| Column | Type |
|---|---|
| `numero` | str |
| `indice` | str |
| `titre` | str |
| `emetteur_code` | str |
| `emetteur_name` | str |
| `lot` | str |
| `primary_tag` | str (one of 7) |
| `secondary_tags` | str (comma-joined; empty allowed) |
| `stale_days` | int |
| `days_to_deadline` | int or empty |
| `last_action_date` | ISO date or empty |
| `focus_priority` | int or empty |
| `focus_owner_tier` | str or empty |
| `primary_owner` | str or empty |

### 4b. Existing endpoint patterns
File: `app.py`, ~lines 1015–1100. Existing methods follow this pattern:
```python
def get_X_for_ui(self, ...):
    self._cache_ready.wait()
    try:
        ...
        return _sanitize_for_json(payload)
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"error": str(exc)}
```
Mirror it.

### 4c. Existing bridge patterns
File: `ui/jansa/data_bridge.js`. Existing methods (`loadFiche`, `loadDocumentCommandCenter`, etc.) follow:
```js
methodName: async function (...) {
  if (!bridge.api) return <empty>;
  try {
    var r = await bridge.api.<endpoint>(...);
    if (r && r.error) { console.error(...); return r; }
    return r;
  } catch (e) { console.error(...); return <empty>; }
}
```
Mirror.

---

## 5. User Value

- The Intelligence UI page (Phase 6C) becomes implementable: facet counts populate filter chips; filter combinations return list payloads.
- Operators get sub-second response on filter changes (in-memory mtime cache).

---

## 6. Files

### READ (required, before any edit)
- `output/intermediate/INTELLIGENCE_TAGS.csv` — read 5 rows + summary stats (`pandas.value_counts()` on each categorical column) so you know the actual distribution before writing code
- `app.py` — UI adapter section (~lines 1015–1100); `_sanitize_for_json` helper
- `ui/jansa/data_bridge.js` — full file
- `paths.py` (or wherever `OUTPUT_DIR` lives)
- `README.md` §What Not To Touch
- This MD

### MODIFY
- `app.py` — add `get_intelligence_facets()` and `get_intelligence_documents(filters, limit, sort)` methods.
- `ui/jansa/data_bridge.js` — add `loadIntelligenceFacets()` and `loadIntelligenceDocuments(filters, limit)`.

### CREATE
- `src/reporting/intelligence_query.py` — read-side helper module exposing:
  ```python
  def get_facets() -> dict
  def query_documents(filters: dict, limit: int = 1000, sort: str = "newest") -> dict
  ```
  Internal: a small mtime-keyed in-memory cache of the parsed CSV (one DataFrame).

### DO NOT TOUCH
- `src/pipeline/stages/*`
- `src/flat_ged/`, `src/chain_onion/`
- `src/reporting/intelligence_builder.py` (Phase 6A artifact builder — read its output, don't change it)
- `src/run_memory.py`, `src/report_memory.py`, `src/team_version_builder.py`, `src/effective_responses.py`
- `src/reporting/aggregator.py`, `data_loader.py`, `focus_filter.py`, `focus_ownership.py`, `ui_adapter.py`, `document_command_center.py` — read only
- `runs/run_0000/`, `data/*.db`
- All UI `.jsx` files (no UI work in 6B; that's 6C)
- `output/exports/` (no export in 6B; that's 6D)

---

## 7. Plan

### Step 1 — Build `src/reporting/intelligence_query.py`
```python
from pathlib import Path
from typing import Optional
import pandas as pd
from paths import OUTPUT_DIR     # or whichever module exposes it

_CSV_PATH = OUTPUT_DIR / "intermediate" / "INTELLIGENCE_TAGS.csv"

# mtime-keyed cache
_CACHE = {"mtime": None, "df": None}

def _load() -> Optional[pd.DataFrame]:
    if not _CSV_PATH.exists():
        return None
    mtime = _CSV_PATH.stat().st_mtime
    if _CACHE["mtime"] != mtime:
        df = pd.read_csv(_CSV_PATH, dtype=str).fillna("")
        # type coercions where useful
        for col in ("stale_days", "days_to_deadline", "focus_priority"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        _CACHE["mtime"] = mtime
        _CACHE["df"] = df
    return _CACHE["df"]

def get_facets() -> dict:
    df = _load()
    if df is None:
        return {"error": "intelligence artifact not yet produced — run the pipeline once to generate it.",
                "primary_tags": {}, "secondary_tags": {}, "lots": {},
                "emetteurs": [], "owner_tiers": {}, "total": 0}
    # primary_tags
    primary = df["primary_tag"].value_counts().to_dict()
    # secondary_tags — explode comma-joined strings
    sec_series = df["secondary_tags"].fillna("")
    secs = []
    for s in sec_series:
        if s:
            secs.extend([t.strip() for t in s.split(",") if t.strip()])
    secondary = pd.Series(secs).value_counts().to_dict()
    # lots
    lots = df["lot"].value_counts().to_dict()
    # emetteurs (top + counts)
    emetteurs_grp = (df.groupby(["emetteur_code", "emetteur_name"]).size()
                     .reset_index(name="count")
                     .sort_values("count", ascending=False))
    emetteurs = emetteurs_grp.to_dict(orient="records")
    # owner_tiers
    tiers = df["focus_owner_tier"].fillna("").value_counts().to_dict()
    return {
        "primary_tags":   primary,
        "secondary_tags": secondary,
        "lots":           lots,
        "emetteurs":      emetteurs,
        "owner_tiers":    tiers,
        "total":          int(len(df)),
    }

def query_documents(filters: dict, limit: int = 1000, sort: str = "newest") -> dict:
    df = _load()
    if df is None:
        return {"error": "intelligence artifact not yet produced — run the pipeline once to generate it.",
                "rows": [], "total_count": 0, "truncated": False, "applied_filters": filters or {}}
    f = filters or {}
    out = df

    # Within-category OR; across-category AND
    if f.get("primary_tags"):
        out = out[out["primary_tag"].isin(f["primary_tags"])]
    if f.get("secondary_tags"):
        wanted = set(f["secondary_tags"])
        out = out[out["secondary_tags"].fillna("").apply(
            lambda s: bool(wanted & {t.strip() for t in s.split(",") if t.strip()})
        )]
    if f.get("lots"):
        out = out[out["lot"].isin(f["lots"])]
    if f.get("emetteur_codes"):
        out = out[out["emetteur_code"].isin(f["emetteur_codes"])]
    if f.get("owner_tiers"):
        out = out[out["focus_owner_tier"].isin(f["owner_tiers"])]
    if f.get("stale_days_min") is not None:
        out = out[out["stale_days"].fillna(-1) >= f["stale_days_min"]]
    if f.get("stale_days_max") is not None:
        out = out[out["stale_days"].fillna(10**9) <= f["stale_days_max"]]

    # Sort
    if sort == "newest":
        out = out.sort_values(["last_action_date", "numero"], ascending=[False, True], na_position="last")
    elif sort == "stalest":
        out = out.sort_values(["stale_days", "numero"], ascending=[False, True], na_position="last")
    # default fallback: newest

    total = int(len(out))
    truncated = total > limit
    rows = out.head(limit).to_dict(orient="records")
    return {"rows": rows, "total_count": total, "truncated": truncated, "applied_filters": f}
```

Notes:
- `dtype=str` + `pd.to_numeric` keeps the loader robust to empty cells.
- `_CACHE` is a tiny in-memory single-instance cache; that's enough for the desktop app's single-user model.
- Filter semantics frozen here; do not extend without approval.

### Step 2 — Add app.py endpoints
```python
def get_intelligence_facets(self) -> dict:
    self._cache_ready.wait()
    try:
        from reporting.intelligence_query import get_facets
        return _sanitize_for_json(get_facets())
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"error": str(exc)}

def get_intelligence_documents(self, filters: dict = None, limit: int = 1000, sort: str = "newest") -> dict:
    self._cache_ready.wait()
    try:
        from reporting.intelligence_query import query_documents
        return _sanitize_for_json(query_documents(filters or {}, int(limit or 1000), sort or "newest"))
    except Exception as exc:
        import traceback; traceback.print_exc()
        return {"error": str(exc), "rows": [], "total_count": 0, "truncated": False}
```

### Step 3 — Add bridge methods
In `ui/jansa/data_bridge.js`:
```js
loadIntelligenceFacets: async function () {
  if (!bridge.api) return { error: "no backend" };
  try {
    var r = await bridge.api.get_intelligence_facets();
    if (r && r.error) console.warn("[data_bridge] facets:", r.error);
    return r;
  } catch (e) { console.error("[data_bridge] facets exception:", e); return { error: e.message }; }
},

loadIntelligenceDocuments: async function (filters, limit, sort) {
  if (!bridge.api) return { rows: [], total_count: 0, truncated: false };
  try {
    var r = await bridge.api.get_intelligence_documents(
      filters || {},
      limit != null ? limit : 1000,
      sort || "newest"
    );
    if (r && r.error) console.warn("[data_bridge] documents:", r.error);
    return r;
  } catch (e) { console.error("[data_bridge] documents exception:", e); return { rows: [], total_count: 0, truncated: false, error: e.message }; }
}
```

### Step 4 — Stop
Do NOT start 6C in the same pass. Report completion. Wait for the user to pick up Phase 6C.

---

## 8. Validation

| Check | How |
|---|---|
| Module compiles | `python -m py_compile app.py src/reporting/intelligence_query.py` |
| App starts | `python app.py` |
| Facets non-empty | `python -c "from reporting.intelligence_query import get_facets; print(get_facets())"` returns counts (assuming Phase 6A artifact present) |
| Facets empty-state | Temporarily rename the CSV; call returns `{"error": ...}` payload with empty defaults; do NOT crash |
| Filter primary | `query_documents({"primary_tags":["Att MOEX — Facile"]})` returns only those rows |
| Filter intersection | Add a secondary tag filter — count shrinks; matches manual pandas check |
| Sort newest | First row's `last_action_date` ≥ last row's |
| Truncation | If a filter matches > 1000, `truncated: true` and `len(rows) == 1000` |
| Sub-second | Repeated calls hit the mtime cache; no disk I/O on the second call |
| No regression | All other endpoints unchanged; Phase 1–5 + 6A unaffected |

---

## 9. Cowork Handoff Prompt (paste-ready)

```
Objective:
Phase 6B — Add backend read-only endpoints get_intelligence_facets and get_intelligence_documents that read output/intermediate/INTELLIGENCE_TAGS.csv (produced by Phase 6A) and serve facet counts + filtered/sorted document lists. Also add the matching data_bridge.js methods. NO UI page in this phase (that's 6C). NO export (that's 6D).

Repository: GFUP_Backend / GF Updater v3 / 17&CO Tranche 2. Risk level: MEDIUM.

PREREQUISITE: Phase 6A must already be merged. output/intermediate/INTELLIGENCE_TAGS.csv must exist. If absent, stop and escalate.

Read fully before editing:
- output/intermediate/INTELLIGENCE_TAGS.csv (5 rows + value_counts on categorical columns)
- app.py UI adapter section (~lines 1015–1100); _sanitize_for_json helper
- ui/jansa/data_bridge.js (full file)
- paths.py (OUTPUT_DIR)
- README.md "What Not To Touch"
- docs/implementation/PHASE_6B_INTELLIGENCE_ENDPOINTS.md (this spec)

Do not touch:
- src/pipeline/stages/*
- src/flat_ged/, src/chain_onion/
- src/reporting/intelligence_builder.py (Phase 6A — consume its output only)
- src/run_memory.py, src/report_memory.py, src/team_version_builder.py, src/effective_responses.py
- src/reporting/aggregator.py, data_loader.py, focus_filter.py, focus_ownership.py, ui_adapter.py, document_command_center.py — read only
- runs/run_0000/, data/*.db
- All .jsx UI files (no UI in 6B)
- output/exports/

Implement:
1. Create src/reporting/intelligence_query.py with:
   - mtime-keyed in-memory cache of the CSV (single DataFrame)
   - get_facets() returning {primary_tags, secondary_tags, lots, emetteurs, owner_tiers, total}
   - query_documents(filters, limit=1000, sort="newest") returning {rows, total_count, truncated, applied_filters}
   - Filter semantics: within-category OR; across-category AND
   - Default sort newest first (last_action_date DESC, tie-break numero ASC)
   - Hard cap 1000 rows
   - Missing-artifact contract: return {"error": "intelligence artifact not yet produced..."} with empty/zero defaults — never crash
2. Add app.py methods get_intelligence_facets() and get_intelligence_documents(filters, limit, sort) — mirror the existing get_X_for_ui pattern (try/except, _sanitize_for_json, traceback on exception).
3. Add data_bridge.js methods loadIntelligenceFacets() and loadIntelligenceDocuments(filters, limit, sort) — mirror the existing loadFiche/loadDocumentCommandCenter style.
4. STOP. Do not start 6C. Report completion and wait for the user to pick up Phase 6C.

Validation (must pass before reporting done):
- python -m py_compile app.py src/reporting/intelligence_query.py
- python app.py launches
- python -c "from reporting.intelligence_query import get_facets; print(get_facets())" returns non-empty counts
- query_documents({primary_tags:["Att MOEX — Facile"]}) returns only those rows
- AND across categories shrinks results correctly
- Sort newest: first row last_action_date ≥ last row's
- Truncation: filters matching > 1000 return truncated=true, len(rows)==1000
- Mtime cache: second call doesn't re-read the CSV
- Missing artifact (rename CSV) returns the error contract without crash
- Phase 1–5 + 6A unaffected

Hard rules:
- Backend stays source of truth. UI calculates nothing.
- Filter semantics frozen: within-category OR, across-category AND.
- Sort frozen: newest first by default. Stalest available as second option.
- Cache by mtime only. No new caching layer.
- Missing artifact = soft error contract.
- Do NOT proceed to 6C in the same pass.
```

---

## 10. Context Update (after merge)

- `context/03_UI_FEED_MAP.md` — record `get_intelligence_facets` / `get_intelligence_documents` endpoints and the `loadIntelligenceFacets` / `loadIntelligenceDocuments` bridge methods.
- `context/02_DATA_FLOW.md` — note the read-side query module reads `INTELLIGENCE_TAGS.csv` with mtime cache.
- `context/10_VALIDATION_COMMANDS.md` — add the smoke commands.

If `context/` is missing the file, skip — do not create new context files in this phase.

---

## 11. Done Definition

- App launches cleanly.
- Both endpoints return correct payloads against the Phase 6A artifact.
- Bridge methods present and exercised by smoke calls.
- Empty-state contract works.
- mtime cache works.
- Phase 1–5 + 6A unaffected.
- Diff scoped to: `src/reporting/intelligence_query.py` (new), `app.py`, `ui/jansa/data_bridge.js`.
- 6C / 6D NOT started.
