# PATCH 7 — Contractor Fiche Ownership-Based Focus Filtering

## OBJECTIVE

Change `build_contractor_fiche` so that in Focus Mode, it shows ONLY documents this contractor OWNS per the ownership rules:
- **REF docs** (VISA GLOBAL = REF, contractor must resubmit) — `_focus_owner_tier == "CONTRACTOR"`
- **Open docs still in review** — where consultants or MOEX haven't finished, the contractor can see them as "in progress" but they are NOT the contractor's responsibility

In Focus Mode the contractor fiche should show:
- Block 3 (document table): only open docs + REF docs (hide resolved VSO/VAO/HM/SAS REF)
- Block 4 (quality metrics): recomputed from the focused set
- A new `focus_summary` field showing how many docs the contractor must act on (REF only) vs how many are in review

Also fix `compute_contractor_summary` in the aggregator to add a `focus_owned` count (REF docs this contractor must resubmit).

## RULES

- PATCH `src/reporting/contractor_fiche.py` — 3 edits
- PATCH `src/reporting/aggregator.py` — 1 edit
- Do NOT modify any other files
- Do NOT create test files
- Non-focus behavior MUST remain identical

## PREREQUISITE

Patches 3, 4, and 5 must be applied. `dernier_df` has `_visa_global`, `_focus_owner`, `_focus_owner_tier`.

---

## EDIT 1 — Replace focus filter in `build_contractor_fiche`

In `src/reporting/contractor_fiche.py`, find the focus filter block (around lines 67-71):

```python
    # Focus filter
    focus_enabled = (focus_result is not None and
                     focus_result.stats.get("focus_enabled"))
    if focus_enabled and dernier is not None:
        dernier = dernier[dernier["doc_id"].isin(focus_result.focused_doc_ids)].copy()
```

REPLACE with:

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

---

## EDIT 2 — Add focus_summary and ownership info to Block 3 rows and return dict

Find Block 3 document table section (around lines 219-249). The loop builds `block3` list. Inside the loop, find:

```python
            block3.append({
                "numero": _safe_str(row.get("numero_normalized")),
                "indice": _safe_str(row.get("indice")),
                "titre": _safe_str(row.get("libelle_du_document") or row.get("lib_ll_du_document")),
                "type_doc": _safe_str(row.get("type_de_doc")),
                "sas_result": sas_result or "-",
                "visa_global": visa or "-",
                "date_submitted": str(created.date()) if created and not pd.isna(created) else "-",
                "date_visa": str(vdate.date()) if vdate and not pd.isna(vdate) else "-",
                "status": "Open" if visa is None else visa,
            })
```

REPLACE with:

```python
            # Add ownership info for focus mode
            owner_tier = None
            days_to_dl = None
            focus_priority = None
            if focus_enabled and "_focus_owner_tier" in row.index:
                owner_tier = _safe_str(row.get("_focus_owner_tier"))
                dtd = row.get("_days_to_deadline")
                if dtd is not None and not (isinstance(dtd, float) and math.isnan(dtd)):
                    days_to_dl = int(dtd)
                fp = row.get("_focus_priority")
                if fp is not None and not (isinstance(fp, float) and math.isnan(fp)):
                    focus_priority = int(fp)

            block3.append({
                "numero": _safe_str(row.get("numero_normalized")),
                "indice": _safe_str(row.get("indice")),
                "titre": _safe_str(row.get("libelle_du_document") or row.get("lib_ll_du_document")),
                "type_doc": _safe_str(row.get("type_de_doc")),
                "sas_result": sas_result or "-",
                "visa_global": visa or "-",
                "date_submitted": str(created.date()) if created and not pd.isna(created) else "-",
                "date_visa": str(vdate.date()) if vdate and not pd.isna(vdate) else "-",
                "status": "Open" if visa is None else visa,
                "owner_tier": owner_tier,
                "days_to_deadline": days_to_dl,
                "focus_priority": focus_priority,
            })
```

---

## EDIT 3 — Add focus_summary to the return dict

Find the return dict at the end of `build_contractor_fiche` (around lines 283-298):

```python
    return {
        "contractor_name": contractor_code,
        "contractor_code": contractor_code,
        "degraded_mode": False,
        "warnings": [],
        "lots": lots,
        "buildings": buildings,
        "gf_sheets": gf_sheets,
        "total_submitted": total_submitted,
        "total_current": total_current,
        "block1_submission_timeline": block1,
        "block2_visa_chart": block2,
        "block3_document_table": block3,
        "block4_quality": block4,
        "focus_enabled": bool(focus_enabled),
    }
```

REPLACE with:

```python
    # Focus summary: how many docs the contractor must act on
    focus_summary = None
    if focus_enabled and dernier is not None and "_focus_owner_tier" in dernier.columns:
        contractor_owned = int((dernier["_focus_owner_tier"] == "CONTRACTOR").sum())
        in_review = int(
            dernier["_focus_owner_tier"].isin(["PRIMARY", "SECONDARY", "MOEX"]).sum()
        )
        focus_summary = {
            "docs_to_resubmit": contractor_owned,
            "docs_in_review": in_review,
            "total_focused": len(dernier),
        }

    return {
        "contractor_name": contractor_code,
        "contractor_code": contractor_code,
        "degraded_mode": False,
        "warnings": [],
        "lots": lots,
        "buildings": buildings,
        "gf_sheets": gf_sheets,
        "total_submitted": total_submitted,
        "total_current": total_current,
        "block1_submission_timeline": block1,
        "block2_visa_chart": block2,
        "block3_document_table": block3,
        "block4_quality": block4,
        "focus_enabled": bool(focus_enabled),
        "focus_summary": focus_summary,
    }
```

---

## EDIT 4 — Add focus_owned to contractor summary in aggregator

In `src/reporting/aggregator.py`, inside `compute_contractor_summary`, find where the result dict is built (around lines 439-451):

```python
        result.append({
            "name": em,
            "code": em,
            "lots": sorted(data["lots"]),
            "total_submitted": total,
            "visa_vso": data["vso"],
            "visa_vao": data["vao"],
            "visa_ref": data["ref"],
            "visa_sas_ref": data["sas_ref"],
            "visa_open": data["open"],
            "sas_ref_rate": round((data["ref"] + data["sas_ref"]) / max(total, 1), 4),
            "approval_rate": round((data["vso"] + data["vao"]) / max(total, 1), 4),
        })
```

REPLACE with:

```python
        # Focus: count docs this contractor must resubmit (REF owned)
        focus_owned = 0
        if focus_result is not None and focus_result.stats.get("focus_enabled"):
            focused_df = getattr(focus_result, 'focused_df', None)
            if focused_df is not None and "_focus_owner_tier" in focused_df.columns:
                focus_owned = int(
                    ((focused_df["emetteur"] == em) &
                     (focused_df["_focus_owner_tier"] == "CONTRACTOR")).sum()
                )

        result.append({
            "name": em,
            "code": em,
            "lots": sorted(data["lots"]),
            "total_submitted": total,
            "visa_vso": data["vso"],
            "visa_vao": data["vao"],
            "visa_ref": data["ref"],
            "visa_sas_ref": data["sas_ref"],
            "visa_open": data["open"],
            "sas_ref_rate": round((data["ref"] + data["sas_ref"]) / max(total, 1), 4),
            "approval_rate": round((data["vso"] + data["vao"]) / max(total, 1), 4),
            "focus_owned": focus_owned,
        })
```

---

## VERIFICATION

### Check 1 — Syntax
```bash
python -c "import ast; ast.parse(open('src/reporting/contractor_fiche.py').read()); print('contractor_fiche.py syntax OK')"
python -c "import ast; ast.parse(open('src/reporting/aggregator.py').read()); print('aggregator.py syntax OK')"
```

### Check 2 — Import chain
```bash
python -c "
import sys; sys.path.insert(0, 'src')
from reporting.contractor_fiche import build_contractor_fiche
from reporting.aggregator import compute_contractor_summary
print('All imports OK')
"
```

### Check 3 — Verify edits exist
```bash
grep -n "focus_summary\|_focus_owner_tier\|docs_to_resubmit\|owner_tier" src/reporting/contractor_fiche.py | head -10
grep -n "focus_owned\|CONTRACTOR" src/reporting/aggregator.py | head -10
```

All checks must pass before reporting. Do NOT create test files.
