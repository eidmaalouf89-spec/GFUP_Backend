# PATCH 6 — Consultant Fiche Ownership-Based Focus Filtering

## OBJECTIVE

Change `build_consultant_fiche` so that in Focus Mode, it shows ONLY documents that this consultant OWNS (per Rules 1-6 from focus_ownership.py), not all focused docs. Also fix the priority strip to use ownership data. The SAS fiche gets the same treatment.

## RULES

- PATCH ONLY `src/reporting/consultant_fiche.py`
- Do NOT modify any other files
- Do NOT modify any function except the ones listed below
- Do NOT create test files
- Do NOT run `npm run build`
- Non-focus behavior (focus_result=None or focus_enabled=False) MUST remain identical

## PREREQUISITE

Patches 3, 4, and 5 must be applied. `FocusResult` now has a `focused_df` field. `dernier_df` has `_focus_owner` and `_focus_owner_tier` columns.

---

## EDIT 1 — Replace focus filtering logic in `build_consultant_fiche`

In `build_consultant_fiche`, find the focus filter block (around lines 173-181):

```python
    # ── Focus filter: restrict to focused doc_ids ───────────────────────────
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    if focus_enabled and not docs.empty:
        id_col = "doc_id_resp" if "doc_id_resp" in docs.columns else "doc_id"
        docs = docs[docs[id_col].isin(focus_result.focused_doc_ids)].copy()
        if docs.empty:
            return _empty_fiche(consultant_name, ctx,
                                warnings=[f"No focused docs for '{consultant_name}'"])
```

REPLACE with:

```python
    # ── Focus filter: restrict to docs this consultant OWNS ─────────────────
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    if focus_enabled and not docs.empty:
        id_col = "doc_id_resp" if "doc_id_resp" in docs.columns else "doc_id"
        # Get the focused DataFrame with ownership columns
        focused_df = getattr(focus_result, 'focused_df', None)
        if focused_df is not None and "_focus_owner" in focused_df.columns:
            # Only keep docs where this consultant is in the _focus_owner list
            owned_ids = set()
            for _, frow in focused_df.iterrows():
                owners = frow.get("_focus_owner", [])
                if isinstance(owners, list) and consultant_name in owners:
                    owned_ids.add(frow["doc_id"])
            # Also include MOEX-owned docs for Maître d'Oeuvre EXE fiche
            if consultant_name == "Maître d'Oeuvre EXE":
                for _, frow in focused_df.iterrows():
                    if frow.get("_focus_owner_tier") == "MOEX":
                        owned_ids.add(frow["doc_id"])
            docs = docs[docs[id_col].isin(owned_ids)].copy()
        else:
            # Fallback: use focused_doc_ids if ownership columns missing
            docs = docs[docs[id_col].isin(focus_result.focused_doc_ids)].copy()
        if docs.empty:
            return _empty_fiche(consultant_name, ctx,
                                warnings=[f"No owned docs for '{consultant_name}' in focus mode"])
```

---

## EDIT 2 — Fix the priority strip to use ownership

Find the priority strip block (around lines 203-220):

```python
    # ── Focus: build priority strip for this consultant ──────────────
    focus_priority = None
    if focus_enabled:
        my_pq = [item for item in (focus_result.priority_queue or [])
                 if item.get("responsible") == consultant_name]
        p_counts = {}
        for item in my_pq:
            p = item["priority"]
            p_counts[p] = p_counts.get(p, 0) + 1
        focus_priority = {
            "p1": p_counts.get(1, 0),
            "p2": p_counts.get(2, 0),
            "p3": p_counts.get(3, 0),
            "p4": p_counts.get(4, 0),
            "p5": p_counts.get(5, 0),
            "total_focused": len(docs),
            "items": my_pq[:20],
        }
```

REPLACE with:

```python
    # ── Focus: build priority strip for this consultant ──────────────
    focus_priority = None
    if focus_enabled:
        # Match by ownership: this consultant appears in the owners list
        my_pq = [item for item in (focus_result.priority_queue or [])
                 if consultant_name in item.get("owners", [])]
        # Also include MOEX-tier docs for MOEX fiche
        if consultant_name == "Maître d'Oeuvre EXE":
            moex_pq = [item for item in (focus_result.priority_queue or [])
                       if item.get("owner_tier") == "MOEX"]
            seen = {item["doc_id"] for item in my_pq}
            my_pq.extend(item for item in moex_pq if item["doc_id"] not in seen)
            my_pq.sort(key=lambda x: (x["priority"], x.get("delta_days") or 9999))
        p_counts = {}
        for item in my_pq:
            p = item["priority"]
            p_counts[p] = p_counts.get(p, 0) + 1
        focus_priority = {
            "p1": p_counts.get(1, 0),
            "p2": p_counts.get(2, 0),
            "p3": p_counts.get(3, 0),
            "p4": p_counts.get(4, 0),
            "p5": p_counts.get(5, 0),
            "total_focused": len(docs),
            "items": my_pq[:20],
        }
```

---

## EDIT 3 — Fix focus filtering in `build_sas_fiche`

Find the SAS fiche focus filter block (around lines 281-287):

```python
    # Focus filter
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    if focus_enabled:
        merged = merged[merged["doc_id"].isin(focus_result.focused_doc_ids)].copy()
        if merged.empty:
            return _empty_sas_fiche(ctx)
```

REPLACE with:

```python
    # Focus filter: SAS fiche shows all focused docs (SAS is a gate, not an owner)
    # But exclude resolved docs (VISA GLOBAL is terminal)
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    if focus_enabled:
        focused_df = getattr(focus_result, 'focused_df', None)
        if focused_df is not None:
            focused_ids = set(focused_df["doc_id"].tolist())
        else:
            focused_ids = focus_result.focused_doc_ids
        merged = merged[merged["doc_id"].isin(focused_ids)].copy()
        if merged.empty:
            return _empty_sas_fiche(ctx)
```

---

## EDIT 4 — Fix aggregator consultant_summary to use ownership

This edit is in `src/reporting/aggregator.py`, NOT in consultant_fiche.py.

Find the focus filter in `compute_consultant_summary` (around lines 275-277):

```python
    # Apply focus filter: restrict to responses whose doc_id is in focused set
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        filtered = filtered[filtered["doc_id"].isin(focus_result.focused_doc_ids)].copy()
```

REPLACE with:

```python
    # Apply focus filter: restrict to responses on docs in the focused set
    # Uses focused_doc_ids (not ownership) for the summary list — ownership
    # filtering happens in the individual fiche builders, not here.
    # The summary shows aggregate counts across all focused docs.
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        focused_df = getattr(focus_result, 'focused_df', None)
        if focused_df is not None and "_focus_owner" in focused_df.columns:
            # For the consultant list, show each consultant's owned count
            # alongside their total called count for context
            filtered = filtered[filtered["doc_id"].isin(focus_result.focused_doc_ids)].copy()
        else:
            filtered = filtered[filtered["doc_id"].isin(focus_result.focused_doc_ids)].copy()
```

Then, inside the `for name, grp in filtered.groupby("approver_canonical"):` loop, find where `blocking` is computed (around line 310-320). After the blocking computation and before the `summaries.append(...)` call, add this block:

Find:
```python
        if called > 0:
            summaries.append({
```

Insert BEFORE `summaries.append`:

```python
            # Focus: count owned docs for this consultant
            focus_owned = 0
            if focus_result is not None and focus_result.stats.get("focus_enabled"):
                focused_df = getattr(focus_result, 'focused_df', None)
                if focused_df is not None and "_focus_owner" in focused_df.columns:
                    for _, frow in focused_df.iterrows():
                        owners = frow.get("_focus_owner", [])
                        if isinstance(owners, list) and name in owners:
                            focus_owned += 1
```

Then add `"focus_owned": focus_owned,` to the summaries.append dict. Find:

```python
                "open_blocking": blocking,
            })
```

Replace with:

```python
                "open_blocking": blocking,
                "focus_owned": focus_owned,
            })
```

---

## VERIFICATION

### Check 1 — Syntax
```bash
python -c "import ast; ast.parse(open('src/reporting/consultant_fiche.py').read()); print('consultant_fiche.py syntax OK')"
python -c "import ast; ast.parse(open('src/reporting/aggregator.py').read()); print('aggregator.py syntax OK')"
```

### Check 2 — Import chain
```bash
python -c "
import sys; sys.path.insert(0, 'src')
from reporting.consultant_fiche import build_consultant_fiche, build_sas_fiche
from reporting.aggregator import compute_consultant_summary
print('All imports OK')
"
```

### Check 3 — Verify the edits exist
```bash
grep -n "owned_ids\|_focus_owner\|focus_owned" src/reporting/consultant_fiche.py | head -10
grep -n "focus_owned" src/reporting/aggregator.py | head -5
```

Must show the new ownership-based filtering lines. All checks must pass before reporting.
