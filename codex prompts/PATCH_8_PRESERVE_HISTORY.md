# PATCH 8 — Preserve Historical Avis in Focus Mode

## OBJECTIVE

Focus Mode currently strips resolved docs before building charts and tables, which removes all VSO/VAO/REF/HM history — the charts show only open docs. This is wrong. Historical avis are performance data and must stay visible.

The correct behavior: in Focus Mode, **historical avis (VSO, VAO, REF, HM) stay in all charts and tables**. Only the "Ouverts" (open) counts use the ownership-filtered focused set.

This patch fixes:
1. `consultant_fiche.py` — use all_docs for charts/history, focused_docs only for open counts
2. `contractor_fiche.py` — same split
3. `aggregator.py` — `compute_weekly_timeseries` and `compute_project_kpis` use full dernier for history
4. `aggregator.py` — `compute_consultant_summary` and `compute_contractor_summary` use full data for answered counts

## RULES

- PATCH 3 files: `src/reporting/consultant_fiche.py`, `src/reporting/contractor_fiche.py`, `src/reporting/aggregator.py`
- Do NOT modify `focus_filter.py`, `focus_ownership.py`, `data_loader.py`, `app.py`, or any UI files
- Non-focus behavior MUST remain identical
- Do NOT create test files

---

## EDIT 1 — consultant_fiche.py: two-DataFrame approach

Find the focus filter block and everything through the block builders (around lines 173-215):

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

    # ── Status label resolution (s1/s2/s3) ───────────────────────────────────
    s1, s2, s3 = _resolve_status_labels(ctx, consultant_name)

    # ── Attach derived columns used by all blocks ────────────────────────────
    docs = _attach_derived(docs, data_date, s1=s1, s2=s2, s3=s3, ctx=ctx)

    # ── Build blocks ─────────────────────────────────────────────────────────
    consultant = _build_consultant_meta(ctx, consultant_name)
    header     = _build_header(docs, data_date, s1, s2, s3)
    week_delta = _build_week_delta(docs, data_date, prev_date, s1, s2, s3)
    if focus_enabled:
        bloc1 = _build_bloc1_weekly(docs, data_date, s1, s2, s3)
    else:
        bloc1 = _build_bloc1(docs, data_date, s1, s2, s3)
    bloc2      = _build_bloc2(bloc1)
    bloc3      = _build_bloc3(docs, ctx, s1, s2, s3)
```

REPLACE the entire block above with:

```python
    # ── Focus: compute owned_ids for this consultant ────────────────────────
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    owned_ids = None
    if focus_enabled and not docs.empty:
        id_col = "doc_id_resp" if "doc_id_resp" in docs.columns else "doc_id"
        focused_df = getattr(focus_result, 'focused_df', None)
        if focused_df is not None and "_focus_owner" in focused_df.columns:
            owned_ids = set()
            for _, frow in focused_df.iterrows():
                owners = frow.get("_focus_owner", [])
                if isinstance(owners, list) and consultant_name in owners:
                    owned_ids.add(frow["doc_id"])
            if consultant_name == "Maître d'Oeuvre EXE":
                for _, frow in focused_df.iterrows():
                    if frow.get("_focus_owner_tier") == "MOEX":
                        owned_ids.add(frow["doc_id"])
        else:
            owned_ids = focus_result.focused_doc_ids

    # ── Status label resolution (s1/s2/s3) ───────────────────────────────────
    s1, s2, s3 = _resolve_status_labels(ctx, consultant_name)

    # ── Attach derived columns used by all blocks ────────────────────────────
    # Use ALL docs (full history) for charts and tables
    all_docs = _attach_derived(docs, data_date, s1=s1, s2=s2, s3=s3, ctx=ctx)

    # ── Build blocks ─────────────────────────────────────────────────────────
    # Bloc1, Bloc2: FULL HISTORY (all avis: VSO, VAO, REF, HM + open)
    # Header, Week delta: FULL HISTORY for totals/answered, FOCUSED for open
    # Bloc3: FULL HISTORY for status counts, FOCUSED for open column
    consultant = _build_consultant_meta(ctx, consultant_name)
    header     = _build_header(all_docs, data_date, s1, s2, s3)
    week_delta = _build_week_delta(all_docs, data_date, prev_date, s1, s2, s3)
    if focus_enabled:
        bloc1 = _build_bloc1_weekly(all_docs, data_date, s1, s2, s3)
    else:
        bloc1 = _build_bloc1(all_docs, data_date, s1, s2, s3)
    bloc2      = _build_bloc2(bloc1)
    bloc3      = _build_bloc3(all_docs, ctx, s1, s2, s3)

    # ── Focus: override open counts in header/bloc3 with ownership-filtered values
    if focus_enabled and owned_ids is not None:
        id_col = "doc_id_resp" if "doc_id_resp" in all_docs.columns else "doc_id"
        focused_docs = all_docs[all_docs[id_col].isin(owned_ids)]
        # Override header open counts
        open_mask = focused_docs["_is_open"]
        header["open_count"] = int(open_mask.sum())
        header["open_ok"] = int((open_mask & focused_docs["_on_time"]).sum())
        header["open_late"] = int((open_mask & ~focused_docs["_on_time"]).sum())
        blocking_mask = focused_docs["_is_blocking"]
        header["open_blocking"] = int(blocking_mask.sum())
        header["open_blocking_ok"] = int((blocking_mask & focused_docs["_on_time"]).sum())
        header["open_blocking_late"] = int((blocking_mask & ~focused_docs["_on_time"]).sum())
        header["open_non_blocking"] = int((open_mask & ~blocking_mask).sum())
        # Override bloc3 open counts per lot
        for lot_row in bloc3.get("lots", []):
            lot_name = lot_row["name"]
            lot_focused = focused_docs[focused_docs["_gf_sheet"] == lot_name]
            lot_open = lot_focused["_is_open"]
            lot_row["open_ok"] = int((lot_open & lot_focused["_on_time"]).sum())
            lot_row["open_late"] = int((lot_open & ~lot_focused["_on_time"]).sum())
            if "_is_blocking" in lot_focused.columns:
                lot_blk = lot_focused["_is_blocking"]
                lot_row["open_blocking_ok"] = int((lot_blk & lot_focused["_on_time"]).sum())
                lot_row["open_blocking_late"] = int((lot_blk & ~lot_focused["_on_time"]).sum())
                lot_row["open_nb"] = int((lot_open & ~lot_blk).sum())
        # Recalculate bloc3 totals and donut from overridden lot rows
        lots = bloc3.get("lots", [])
        def _sum(key):
            return int(sum(r.get(key, 0) for r in lots))
        bloc3["total_row"]["open_ok"] = _sum("open_ok")
        bloc3["total_row"]["open_late"] = _sum("open_late")
        bloc3["total_row"]["open_blocking_ok"] = _sum("open_blocking_ok")
        bloc3["total_row"]["open_blocking_late"] = _sum("open_blocking_late")
        bloc3["total_row"]["open_nb"] = _sum("open_nb")
        bloc3["donut_ok"] = _sum("open_blocking_ok")
        bloc3["donut_late"] = _sum("open_blocking_late")
        bloc3["donut_total"] = bloc3["donut_ok"] + bloc3["donut_late"]
        bloc3["donut_nb"] = _sum("open_nb")
```

---

## EDIT 2 — contractor_fiche.py: keep full history, override open counts

Find the focus filter block (around lines 67-82):

```python
    # Focus filter: use ownership columns from focus_ownership.py
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    if focus_enabled and dernier is not None:
        focused_df = getattr(focus_result, 'focused_df', None)
        if focused_df is not None and "_focus_owner_tier" in focused_df.columns:
            # Get focused doc_ids for this contractor's docs
            # Include: CONTRACTOR-owned (REF, must resubmit) + open docs still in review
            contractor_focused = focused_df[
                focused_df["emetteur"] == contractor_code
            ]
            focused_ids = set(contractor_focused["doc_id"].tolist())
            dernier = dernier[dernier["doc_id"].isin(focused_ids)].copy()
        else:
            # Fallback to flat focused_doc_ids
            dernier = dernier[dernier["doc_id"].isin(focus_result.focused_doc_ids)].copy()
```

REPLACE with:

```python
    # Focus filter: compute focused_ids but do NOT filter dernier yet
    # Charts and tables need full history; only open counts use focused set
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    focused_ids = None
    if focus_enabled and dernier is not None:
        focused_df = getattr(focus_result, 'focused_df', None)
        if focused_df is not None and "_focus_owner_tier" in focused_df.columns:
            contractor_focused = focused_df[
                focused_df["emetteur"] == contractor_code
            ]
            focused_ids = set(contractor_focused["doc_id"].tolist())
        else:
            focused_ids = set(
                did for did in focus_result.focused_doc_ids
                if did in set(dernier["doc_id"].tolist())
            )
```

Then find Block 3 document table section (around line 260). Currently it iterates `dernier` and builds `block3`. Find the line that adds the `"status"` field:

```python
                "status": "Open" if visa is None else visa,
```

After that line (and the rest of the block3.append dict), but BEFORE `block3.sort(...)`, add a filter:

Find:
```python
    block3.sort(key=lambda x: x["numero"])
```

Insert BEFORE that line:

```python
    # Focus mode: mark non-focused open docs and filter block3 for display
    if focus_enabled and focused_ids is not None:
        for row_dict in block3:
            is_open = row_dict["status"] == "Open"
            doc_id_val = row_dict.get("_doc_id")  # we'll add this below
            if is_open and doc_id_val and doc_id_val not in focused_ids:
                row_dict["_excluded_by_focus"] = True
        # Remove excluded open docs from block3 (keep all resolved docs for history)
        block3 = [r for r in block3 if not r.get("_excluded_by_focus", False)]
```

But wait — the current block3 rows don't have `doc_id`. We need to add it. In the block3.append dict (around line 237), add `"_doc_id": did,` to the dict. Find:

```python
            block3.append({
                "numero": _safe_str(row.get("numero_normalized")),
```

REPLACE with:

```python
            block3.append({
                "_doc_id": did,
                "numero": _safe_str(row.get("numero_normalized")),
```

Then after the `block3.sort(...)` line, add cleanup to remove the internal `_doc_id` field:

Find:
```python
    block3.sort(key=lambda x: x["numero"])
```

Add AFTER:

```python
    # Clean up internal field
    for row_dict in block3:
        row_dict.pop("_doc_id", None)
        row_dict.pop("_excluded_by_focus", None)
```

Now fix the focus_summary computation. Find:

```python
    # Focus summary: how many docs the contractor must act on
    focus_summary = None
    if focus_enabled and dernier is not None and "_focus_owner_tier" in dernier.columns:
```

REPLACE with:

```python
    # Focus summary: how many docs the contractor must act on
    focus_summary = None
    if focus_enabled and focused_ids is not None and dernier is not None and "_focus_owner_tier" in dernier.columns:
        focused_dernier = dernier[dernier["doc_id"].isin(focused_ids)]
```

And update the counts to use `focused_dernier`:

Find:
```python
        contractor_owned = int((dernier["_focus_owner_tier"] == "CONTRACTOR").sum())
        in_review = int(
            dernier["_focus_owner_tier"].isin(["PRIMARY", "SECONDARY", "MOEX"]).sum()
        )
        focus_summary = {
            "docs_to_resubmit": contractor_owned,
            "docs_in_review": in_review,
            "total_focused": len(dernier),
        }
```

REPLACE with:

```python
        contractor_owned = int((focused_dernier["_focus_owner_tier"] == "CONTRACTOR").sum())
        in_review = int(
            focused_dernier["_focus_owner_tier"].isin(["PRIMARY", "SECONDARY", "MOEX"]).sum()
        )
        focus_summary = {
            "docs_to_resubmit": contractor_owned,
            "docs_in_review": in_review,
            "total_focused": len(focused_dernier),
        }
```

---

## EDIT 3 — aggregator.py: compute_weekly_timeseries uses full dernier

Find in `compute_weekly_timeseries` (around lines 214-216):

```python
    dernier = ctx.dernier_df
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        dernier = dernier[dernier["doc_id"].isin(focus_result.focused_doc_ids)]
```

REPLACE with:

```python
    # Use FULL dernier for historical avis (VSO/VAO/REF/HM are performance data)
    # Only the "open" bucket should reflect the focused set
    dernier = ctx.dernier_df
    focused_ids = None
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        focused_ids = focus_result.focused_doc_ids
```

Then in the loop where visa status is bucketed, find:

```python
        visa, _ = we.compute_visa_global_with_date(did)
        weekly[week_key]["total"] += 1
        if visa == "VSO":
            weekly[week_key]["vso"] += 1
        elif visa == "VAO":
            weekly[week_key]["vao"] += 1
        elif visa == "REF":
            weekly[week_key]["ref"] += 1
        elif visa == "SAS REF":
            weekly[week_key]["sas_ref"] += 1
        else:
            weekly[week_key]["open"] += 1
```

REPLACE with:

```python
        visa, _ = we.compute_visa_global_with_date(did)
        weekly[week_key]["total"] += 1
        if visa == "VSO":
            weekly[week_key]["vso"] += 1
        elif visa == "VAO":
            weekly[week_key]["vao"] += 1
        elif visa == "REF":
            weekly[week_key]["ref"] += 1
        elif visa == "SAS REF":
            weekly[week_key]["sas_ref"] += 1
        else:
            # In focus mode, only count as "open" if doc is in focused set
            if focused_ids is not None:
                if did in focused_ids:
                    weekly[week_key]["open"] += 1
                # else: open but excluded (stale/not owned) — don't count
            else:
                weekly[week_key]["open"] += 1
```

---

## EDIT 4 — aggregator.py: compute_project_kpis uses full dernier for history

Find in `compute_project_kpis` (around lines 73-75):

```python
    # Apply focus filter if provided
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        dernier = dernier[dernier["doc_id"].isin(focus_result.focused_doc_ids)].copy()
```

REPLACE with:

```python
    # Focus mode: use FULL dernier for visa distribution (historical performance)
    # Only override "Open" count to reflect focused (actionable) set
    focused_ids = None
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        focused_ids = focus_result.focused_doc_ids
```

Then in the visa_counts loop, find:

```python
        else:
            visa_counts["Open"] += 1
```

REPLACE with:

```python
        else:
            if focused_ids is not None:
                if did in focused_ids:
                    visa_counts["Open"] += 1
            else:
                visa_counts["Open"] += 1
```

Also update the responsible party section. Find (around lines 104-111):

```python
    resp_counts = defaultdict(int)
    focus_ids = (focus_result.focused_doc_ids
                 if (focus_result is not None and focus_result.stats.get("focus_enabled"))
                 else None)
    for doc_id, party in resp.items():
        if focus_ids is not None and doc_id not in focus_ids:
            continue
        resp_counts[party or "Closed"] += 1
```

This is correct — responsible party should only count focused docs. Leave it as-is.

---

## EDIT 5 — aggregator.py: compute_consultant_summary keeps full history

Find in `compute_consultant_summary` (around lines 275-277):

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

REPLACE with:

```python
    # Focus mode: do NOT filter responses — keep full history for called/answered/VSO/VAO/REF counts
    # The focus_owned field (computed below) tells the UI how many docs this consultant owns
    # This way the consultant list shows performance data alongside focus ownership
```

This means the consultant list always shows full data (called, answered, rates) — the `focus_owned` field already tells the UI how many docs each consultant owns in focus mode.

---

## EDIT 6 — aggregator.py: compute_contractor_summary keeps full history

Find in `compute_contractor_summary` (around lines 412-414):

```python
    dernier_iter = ctx.dernier_df
    if focus_result is not None and focus_result.stats.get("focus_enabled"):
        dernier_iter = ctx.dernier_df[ctx.dernier_df["doc_id"].isin(focus_result.focused_doc_ids)]
```

REPLACE with:

```python
    # Use FULL dernier for historical counts (VSO/VAO/REF/SAS REF are performance data)
    # The focus_owned field tells the UI how many docs each contractor must act on
    dernier_iter = ctx.dernier_df
```

---

## VERIFICATION

### Check 1 — Syntax
```bash
python -c "import ast; ast.parse(open('src/reporting/consultant_fiche.py').read()); print('consultant_fiche.py syntax OK')"
python -c "import ast; ast.parse(open('src/reporting/contractor_fiche.py').read()); print('contractor_fiche.py syntax OK')"
python -c "import ast; ast.parse(open('src/reporting/aggregator.py').read()); print('aggregator.py syntax OK')"
```

### Check 2 — Import chain
```bash
python -c "
import sys; sys.path.insert(0, 'src')
from reporting.consultant_fiche import build_consultant_fiche
from reporting.contractor_fiche import build_contractor_fiche
from reporting.aggregator import compute_weekly_timeseries, compute_project_kpis
print('All imports OK')
"
```

### Check 3 — Verify key patterns
```bash
echo "=== consultant_fiche: all_docs ===" && grep -n "all_docs" src/reporting/consultant_fiche.py | head -5
echo "=== contractor_fiche: focused_ids ===" && grep -n "focused_ids" src/reporting/contractor_fiche.py | head -5
echo "=== aggregator: focused_ids ===" && grep -n "focused_ids" src/reporting/aggregator.py | head -10
```

All checks must pass. Do NOT create test files.
