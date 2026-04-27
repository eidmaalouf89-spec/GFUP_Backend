# COWORK PATCH — Consultant Fiche: 4 Bug Fixes

**Repo:** `eidmaalouf89-spec/GFUP_Backend`  
**Branch:** `main`  
**Date:** 2026-04-20  
**Scope:** PATCH ONLY — do NOT redesign adjacent areas, do NOT create test files, do NOT loop.  
Apply each fix, run once to verify, report result or traceback and stop.

---

## Status

Implementation status for this patch:

- `BUG 1` fixed
- `BUG 2` fixed
- `BUG 3` fixed
- `BUG 4` fixed

Verification status:

- `date_limite extracted`: `13613` rows
- `PENDING_LATE`: `13345` rows
- `Bureau de Contrôle` labels: `FAV / SUS / DEF`
- `MOEX called (excluding 0-SAS)`: `4059`
- `Dernier indice docs`: `4639`
- `SOCOTEC` fiche resolves to canonical `Bureau de Contrôle`
- `GEMO` fiche resolves to canonical `Maître d'Oeuvre EXE`

Conclusion:

- The 4 consultant fiche bugs covered by this MD have been fixed in code.
- The fixes are implemented in `src/normalize.py`, `src/reporting/data_loader.py`, `src/reporting/consultant_fiche.py`, and `app.py`.
- The runtime verification for the intended app/backend flow passes.

---

## Context

The GFUP_Backend reporting layer has 4 interrelated bugs causing wrong consultant fiche calculations. The bugs are in `src/normalize.py`, `src/reporting/data_loader.py`, and `src/reporting/consultant_fiche.py`. This patch fixes all 4.

---

## BUG 1 — DATA_DATE extraction fails

**File:** `src/reporting/data_loader.py`  
**Function:** `_read_ged_data_date()`

**Problem:** The function searches for cells containing `"extraction"` or `"export"`, but the actual GED Détails sheet says `"Date & heure de la demande"` at row 15, col B. The keyword `"demande"` is never checked. Additionally, the date value is at col D (column+2), not col+1 — col C contains a decorative dot `"∙"`.

**Fix:** Replace the entire `_read_ged_data_date` function with:

```python
def _read_ged_data_date(ged_path: str) -> Optional[date]:
    """Extract DATA_DATE from the GED workbook's Détails sheet.

    The AxeoBIM export places the export timestamp at row ~15:
      Col B: "Date & heure de la demande"
      Col C: "∙"  (decorative dot)
      Col D: datetime value

    We scan for any cell containing 'date' AND one of: 'demande', 'extraction', 'export'.
    Then we look at column+2 first (skipping the dot separator), then column+1.
    """
    import openpyxl
    try:
        wb = openpyxl.load_workbook(ged_path, read_only=True, data_only=True)
        details_sheet = None
        for sn in wb.sheetnames:
            if sn.lower().replace("é", "e").replace("È", "e") in ("details", "détails"):
                details_sheet = wb[sn]
                break
        if details_sheet is None:
            wb.close()
            return None

        for row in details_sheet.iter_rows(min_row=1, max_row=30, max_col=10, values_only=False):
            for cell in row:
                val = str(cell.value or "").lower()
                if "date" not in val:
                    continue
                # Match any of the known label patterns
                if not any(kw in val for kw in ("demande", "extraction", "export")):
                    continue

                ws = cell.parent
                # Try col+2 first (AxeoBIM uses col B=label, col C=dot, col D=value)
                for offset in (2, 1, 3):
                    adj = ws.cell(row=cell.row, column=cell.column + offset).value
                    if adj is None:
                        continue
                    if isinstance(adj, datetime):
                        wb.close()
                        return adj.date()
                    if isinstance(adj, date):
                        wb.close()
                        return adj
                    try:
                        wb.close()
                        return datetime.strptime(str(adj).strip(), "%d/%m/%Y").date()
                    except Exception:
                        pass

                # Try cell below as last resort
                below = ws.cell(row=cell.row + 1, column=cell.column).value
                if below is not None:
                    if isinstance(below, datetime):
                        wb.close()
                        return below.date()
                    if isinstance(below, date):
                        wb.close()
                        return below
        wb.close()
    except Exception:
        pass
    return None
```

**Expected result:** `ctx.data_date` should be `2026-04-10` (from the GED export dated April 10, 2026).

---

## BUG 2 — Definitive consultant reference tables + status labels

**Problem:** Multiple issues:
1. `consultant_fiche.py` uses hardcoded names like `"SOCOTEC"`, `"MOX"`, `"GEMO"` which don't match the actual canonical names from Mapping.xlsx (`"Bureau de Contrôle"`, `"ARCHITECTE"`, `"Maître d'Oeuvre EXE"`)
2. `ged_status_labels` is always `{}`, so Bureau de Contrôle (SOCOTEC) always gets default `(VSO, VAO, REF)` — but its actual statuses are `FAV/SUS/DEF`
3. `0-SAS` is mapped to `"Maître d'Oeuvre EXE"` in Mapping.xlsx, inflating MOEX numbers by 155%. SAS is a conformity gate, not a consultant.

**Fix — Part A:** In `src/reporting/consultant_fiche.py`, replace the `BET_MERGE_KEYS` and `ROLE_BY_NAME` dicts at the top of the file with the following definitive reference tables:

```python
# ══════════════════════════════════════════════════════════════════════════════
# DEFINITIVE PROJECT REFERENCE — P17&CO Tranche 2
# Hardcoded from full GED + Mapping.xlsx cross-reference (2026-04-20)
# ══════════════════════════════════════════════════════════════════════════════

# Canonical name (from Mapping.xlsx) → company display name
CONSULTANT_DISPLAY_NAMES = {
    "AMO HQE":              "Le Sommer Environnement",
    "ARCHITECTE":           "Hardel + Le Bihan Architectes",
    "BET Acoustique":       "AVLS",
    "BET Ascenseur":        "BET Ascenseur",
    "BET CVC":              "BET CVC",
    "BET Electricité":      "BET Electricité",
    "BET EV":               "BET EV",
    "BET Façade":           "BET Façade",
    "BET Plomberie":        "BET Plomberie",
    "BET POL":              "BET POL",
    "BET SPK":              "BET SPK",
    "BET Structure":        "Terrell",
    "BET VRD":              "BET VRD",
    "Bureau de Contrôle":   "SOCOTEC",
    "Maître d'Oeuvre EXE":  "GEMO",
}

# Canonical name → role label for display
ROLE_BY_CANONICAL = {
    "AMO HQE":              "AMO HQE (Le Sommer)",
    "ARCHITECTE":           "Architecte (Hardel + Le Bihan)",
    "BET Acoustique":       "BET Acoustique (AVLS)",
    "BET Ascenseur":        "BET Ascenseur",
    "BET CVC":              "BET CVC",
    "BET Electricité":      "BET Electricité",
    "BET EV":               "BET Espaces Verts",
    "BET Façade":           "BET Façade",
    "BET Plomberie":        "BET Plomberie",
    "BET POL":              "BET Pollution",
    "BET SPK":              "BET Sprinkler",
    "BET Structure":        "BET Structure (Terrell)",
    "BET VRD":              "BET VRD",
    "Bureau de Contrôle":   "Bureau de Contrôle (SOCOTEC)",
    "Maître d'Oeuvre EXE":  "MOEX (GEMO)",
}

# Status vocabulary per consultant.
# s1=approved, s2=approved-with-remarks, s3=refused.
# Most consultants use VSO/VAO/REF. Bureau de Contrôle uses FAV/SUS/DEF.
STATUS_LABELS_BY_CANONICAL = {
    "Bureau de Contrôle": {"s1": "FAV", "s2": "SUS", "s3": "DEF"},
    # All others default to VSO/VAO/REF — no entry needed
}

# BET consultants with PDF report merge (non-saisi-GED tracking)
BET_MERGE_KEYS = {
    "BET Acoustique":     "AVLS",
    "Bureau de Contrôle": "SOCOTEC",
    "AMO HQE":            "LeSommer",
    "BET Structure":      "Terrell",    # OBS-ONLY: status from GED, observations from PDF
}

# Company short name → canonical (for reverse lookup from UI or legacy references)
COMPANY_TO_CANONICAL = {
    "SOCOTEC":    "Bureau de Contrôle",
    "AVLS":       "BET Acoustique",
    "Terrell":    "BET Structure",
    "Le Sommer":  "AMO HQE",
    "LeSommer":   "AMO HQE",
    "GEMO":       "Maître d'Oeuvre EXE",
    "MOX":        "ARCHITECTE",
}

# Contractor (EMETTEUR) code → display name + lots
# From GED docs analysis (2026-04-20)
CONTRACTOR_REFERENCE = {
    "LGD":  {"name": "Legendre",           "lots": ["03", "07", "06B"]},
    "BEN":  {"name": "Bentin",             "lots": ["31", "33", "34"]},
    "SNI":  {"name": "SNIE",               "lots": ["31", "33", "34"]},
    "AXI":  {"name": "Axima",              "lots": ["41"]},
    "UTB":  {"name": "UTB",                "lots": ["42"]},
    "DUV":  {"name": "Duval",              "lots": ["08", "13A"]},
    "LAC":  {"name": "Lacroix",            "lots": ["12", "12A"]},
    "AMP":  {"name": "AMP / CLD",          "lots": ["11", "16A"]},
    "AAI":  {"name": "AAI",                "lots": ["43"]},
    "SMA":  {"name": "SMAC",               "lots": ["04", "06B"]},
    "ICM":  {"name": "ICM",                "lots": ["05"]},
    "FRS":  {"name": "France Sols",         "lots": ["18", "19"]},
    "API":  {"name": "Apilog / Schneider",  "lots": ["35"]},
    "FER":  {"name": "Fermeté",            "lots": ["06", "13", "14"]},
    "CMF":  {"name": "CMF BAT",            "lots": ["18"]},
    "SPA":  {"name": "SEPA",               "lots": ["61", "62"]},
    "SCH":  {"name": "Schindler",          "lots": ["51"]},
    "LIN":  {"name": "Lindner",            "lots": ["16B"]},
    "IST":  {"name": "IST",                "lots": ["11", "16", "12B"]},
    "CHV":  {"name": "Atchouel",           "lots": ["13"]},
    "VAL":  {"name": "Vallée",             "lots": ["19"]},
    "CPL":  {"name": "CPLC",               "lots": ["12B"]},
    "VTP":  {"name": "VTP",                "lots": ["01"]},
    "CRE":  {"name": "Créa Diffusion",     "lots": ["42B"]},
    "FKI":  {"name": "FKI",                "lots": ["02"]},
    "BAN":  {"name": "Bangui",             "lots": ["17"]},
    "FMC":  {"name": "FMC",                "lots": ["13B"]},
    "JLE":  {"name": "Jean Letuvé",        "lots": ["20"]},
    "DBH":  {"name": "DBH",                "lots": ["20"]},
    "HVA":  {"name": "HVA Concept",        "lots": ["22"]},
}
```

**Fix — Part B:** Remove the old `ROLE_BY_NAME` dict entirely and update `_build_consultant_meta` to use the new tables:

```python
def _build_consultant_meta(ctx: RunContext, name: str) -> dict[str, Any]:
    all_consultants = sorted(ctx.approver_names or [name])
    try:
        cid = all_consultants.index(name) + 1
    except ValueError:
        cid = 0

    merge_key = BET_MERGE_KEYS.get(name)
    role = ROLE_BY_CANONICAL.get(name, "Consultant")
    display = CONSULTANT_DISPLAY_NAMES.get(name, name)

    return {
        "id":            cid,
        "slug":          _slugify(name),
        "canonical_name": name,
        "display_name":  display,
        "name":          name,
        "role":          role,
        "merge_key":     merge_key,
    }
```

**Fix — Part C:** Update `_resolve_status_labels` to read from the hardcoded table instead of the empty `ctx.ged_status_labels`:

```python
def _resolve_status_labels(ctx: RunContext, name: str) -> tuple[str, str, str]:
    """Returns (s1, s2, s3) for the consultant.

    Bureau de Contrôle (SOCOTEC) uses FAV/SUS/DEF.
    All others use VSO/VAO/REF.
    """
    labels = STATUS_LABELS_BY_CANONICAL.get(name, {})
    return (labels.get("s1", "VSO"),
            labels.get("s2", "VAO"),
            labels.get("s3", "REF"))
```

**Fix — Part D:** Update `_attach_derived` — the `_status_for_consultant` must map the raw `status_clean` to the consultant's vocabulary AND correctly identify closed docs. Currently it does a raw passthrough, but the closed-status check uses `{s1, s2, s3, "HM"}`. For Bureau de Contrôle with FAV/SUS/DEF, this already works IF `status_clean` contains "FAV"/"SUS"/"DEF" — which it does (verified). So the closed check `_status_for_consultant.isin([s1, s2, s3, "HM"])` will correctly match "FAV"/"SUS"/"DEF"/"HM" when s1/s2/s3 are set to FAV/SUS/DEF. **No change needed in `_attach_derived` for status mapping** — the fix is entirely in `_resolve_status_labels` returning the right labels.

**Fix — Part E:** Add a `resolve_consultant_name` helper at the top of the file that the UI/API can call to translate between company names and canonical names:

```python
def resolve_consultant_name(name: str) -> str:
    """Resolve a consultant name to its canonical form.

    Accepts either canonical names ('Bureau de Contrôle') or company
    shortnames ('SOCOTEC') and returns the canonical name.
    """
    if name in CONSULTANT_DISPLAY_NAMES:
        return name  # already canonical
    return COMPANY_TO_CANONICAL.get(name, name)
```

**Fix — Part F:** In `app.py`, update `get_consultant_fiche` to resolve names before calling the builder:

```python
def get_consultant_fiche(self, consultant_name):
    """Full fiche data for one consultant."""
    import traceback
    try:
        from reporting.data_loader import load_run_context
        from reporting.consultant_fiche import build_consultant_fiche, resolve_consultant_name
        ctx = load_run_context(BASE_DIR)
        canonical = resolve_consultant_name(consultant_name)
        result = build_consultant_fiche(ctx, canonical)
        return _sanitize_for_json(result)
    except Exception as exc:
        traceback.print_exc()
        return _sanitize_for_json({"error": str(exc), "consultant_name": consultant_name})
```

**Fix — Part G:** In `Mapping.xlsx` or in `normalize.py`, the `0-SAS` rows must NOT be mapped to `"Maître d'Oeuvre EXE"`. SAS is a conformity gate, not a consultant. Add special handling in `normalize_responses`:

In `src/normalize.py`, in the `normalize_responses` function, after the line `df["approver_canonical"] = df["approver_raw"].apply(lambda x: map_approver(x, mapping))`, add:

```python
    # SAS is a conformity gate, not a consultant — must never merge with MOEX
    df.loc[df["approver_raw"] == "0-SAS", "approver_canonical"] = "0-SAS"
    df.loc[df["approver_raw"] == "0-SAS", "is_exception_approver"] = True
```

This ensures 0-SAS rows are excluded from all consultant computations regardless of what Mapping.xlsx says.

---

## BUG 3 — Late/retard classification broken (zero PENDING_LATE)

**File:** `src/normalize.py`  
**Function:** `interpret_date_field()`

**Problem:** The GED uses these formats:
- `"Rappel : En attente visa (2025/02/13)"` → should be late if deadline < DATA_DATE
- `"En attente visa (2026/04/22)"` → should be on-time if deadline >= DATA_DATE

The current code:
1. Checks `"rappel en attente"` which never matches because actual text is `"rappel : en attente"` (colon breaks the substring)
2. Discards the `date_limite` inside parentheses — this is the deadline date needed for on-time/late

**Fix:** Replace the `interpret_date_field` function AND add a new `extract_date_limite` function:

```python
def interpret_date_field(raw) -> dict:
    """
    The 'Date réponse' field can contain:
      - empty/None → NOT_CALLED
      - a datetime → ANSWERED
      - 'En attente visa (YYYY/MM/DD)' → PENDING_IN_DELAY (first request)
      - 'Rappel : En attente visa (YYYY/MM/DD)' → PENDING_LATE (reminder sent)

    The date in parentheses is the date_limite (deadline).

    Returns dict: {date: ..., date_status_type: ..., date_limite: date|None}
    """
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return {"date": None, "date_status_type": "NOT_CALLED", "date_limite": None}

    if isinstance(raw, str):
        lower = raw.strip().lower()

        # Extract date_limite from parentheses: (YYYY/MM/DD)
        dl = _extract_date_limite(raw)

        # "Rappel" prefix means a reminder was sent — indicates lateness
        if lower.startswith("rappel"):
            return {"date": None, "date_status_type": "PENDING_LATE", "date_limite": dl}

        # "En attente" without "Rappel" — first request, still in delay window
        if "en attente" in lower:
            return {"date": None, "date_status_type": "PENDING_IN_DELAY", "date_limite": dl}

        # Non-matching text — treat as unknown pending
        return {"date": None, "date_status_type": "PENDING_IN_DELAY", "date_limite": dl}

    # datetime or date object → ANSWERED
    import datetime as _dt
    if isinstance(raw, (_dt.datetime, _dt.date)):
        return {"date": raw, "date_status_type": "ANSWERED", "date_limite": None}

    # Fallback
    return {"date": None, "date_status_type": "NOT_CALLED", "date_limite": None}


def _extract_date_limite(raw: str):
    """Extract deadline date from parenthesized YYYY/MM/DD in GED date field."""
    import re
    import datetime as _dt
    m = re.search(r'\((\d{4})/(\d{2})/(\d{2})\)', raw)
    if m:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None
```

Then update `normalize_responses` to extract and store `date_limite`:

Replace the date interpretation block:
```python
    # Interpret date field
    date_interp = df["response_date_raw"].apply(interpret_date_field)
    df["date_answered"] = date_interp.apply(lambda x: x["date"])
    df["date_status_type"] = date_interp.apply(lambda x: x["date_status_type"])
```

With:
```python
    # Interpret date field (includes date_limite extraction)
    date_interp = df["response_date_raw"].apply(interpret_date_field)
    df["date_answered"] = date_interp.apply(lambda x: x["date"])
    df["date_status_type"] = date_interp.apply(lambda x: x["date_status_type"])
    df["date_limite"] = date_interp.apply(lambda x: x.get("date_limite"))
```

Now update `src/reporting/consultant_fiche.py` `_attach_derived` to compute on-time/late from `date_limite` vs `data_date` instead of relying on `date_status_type`:

Replace the `_on_time` block (the section starting with `# ── On-time / late`):

```python
    # ── On-time / late: compare date_limite against data_date ──────────────
    # A pending doc is late if its deadline (date_limite) is before data_date.
    # A closed doc is always "on time" (it's done).
    # If date_limite is missing, fall back to date_status_type heuristic.
    dl_col = "date_limite_resp" if "date_limite_resp" in df.columns else (
             "date_limite" if "date_limite" in df.columns else None)
    if dl_col and dl_col in df.columns:
        def _compute_on_time(row):
            if not row["_is_open"]:
                return True  # closed = not late
            dl = row.get(dl_col)
            if dl is not None and not pd.isna(dl):
                if isinstance(dl, pd.Timestamp):
                    dl = dl.date()
                return dl >= data_date
            # Fallback: PENDING_LATE from Rappel prefix
            return row.get("date_status_type") != "PENDING_LATE"
        df["_on_time"] = df.apply(_compute_on_time, axis=1)
    elif "date_status_type" in df.columns:
        df["_on_time"] = df.apply(
            lambda r: (not r["_is_open"]) or (r["date_status_type"] != "PENDING_LATE"),
            axis=1,
        )
    else:
        df["_on_time"] = True
```

---

## BUG 4 — Fiche uses ALL doc versions instead of dernier indice

**File:** `src/reporting/consultant_fiche.py`  
**Function:** `_filter_for_consultant()`

**Problem:** The function joins `responses_df` with `docs_df` (all versions). A document revised 3 times counts 3× in the consultant's stats. Total docs = 6,901 but dernier = 4,639.

**Fix:** Filter to dernier indice docs only. Replace `_filter_for_consultant`:

```python
def _filter_for_consultant(ctx: RunContext, name: str) -> pd.DataFrame:
    """Return a merged DataFrame of dernier-indice docs + this consultant's responses.

    Uses ctx.dernier_df (latest version per document) as the doc base,
    then inner-joins with this consultant's response rows.
    """
    if ctx.responses_df is None or ctx.responses_df.empty:
        return pd.DataFrame()
    if ctx.dernier_df is None or ctx.dernier_df.empty:
        return pd.DataFrame()

    resp = ctx.responses_df
    docs = ctx.dernier_df

    # Filter responses for this consultant (exclude NOT_CALLED)
    cons_resp = resp[
        (resp["approver_canonical"] == name) &
        (resp["date_status_type"] != "NOT_CALLED")
    ].copy()

    if cons_resp.empty:
        return pd.DataFrame()

    # Merge with dernier-indice docs only
    merged = cons_resp.merge(docs, on="doc_id", how="inner", suffixes=("_resp", "_doc"))

    return merged
```

---

## Verification after applying all 4 fixes

After applying all patches, run this one-shot test from the repo root:

```python
python3 -c "
import sys
sys.path.insert(0, 'src')
from read_raw import read_ged
from normalize import load_mapping, normalize_docs, normalize_responses
from version_engine import VersionEngine

docs_df, responses_df, approver_names = read_ged('input/GED_export.xlsx')
mapping = load_mapping('input/Mapping.xlsx')
docs_df = normalize_docs(docs_df, mapping)
responses_df = normalize_responses(responses_df, mapping)

ve = VersionEngine(docs_df)
versioned = ve.run()
dernier = versioned[versioned['is_dernier_indice'] == True]

# Check SAS is excluded
sas = responses_df[responses_df['approver_raw'] == '0-SAS']
assert (sas['approver_canonical'] == '0-SAS').all(), 'SAS must not map to MOEX'
assert sas['is_exception_approver'].all(), 'SAS must be exception'

# Check date_limite extraction
has_dl = responses_df['date_limite'].notna().sum()
print(f'date_limite extracted: {has_dl} rows (expect ~13600)')

# Check PENDING_LATE
late = (responses_df['date_status_type'] == 'PENDING_LATE').sum()
print(f'PENDING_LATE: {late} rows (expect ~13300)')

# Check Bureau de Contrôle status matching
from reporting.consultant_fiche import _resolve_status_labels, STATUS_LABELS_BY_CANONICAL
s1, s2, s3 = _resolve_status_labels(None, 'Bureau de Contrôle')
print(f'Bureau de Contrôle labels: s1={s1}, s2={s2}, s3={s3} (expect FAV/SUS/DEF)')

# Check MOEX count without SAS
moex = responses_df[
    (responses_df['approver_canonical'] == \"Maître d'Oeuvre EXE\") &
    (responses_df['date_status_type'] != 'NOT_CALLED')
]
print(f'MOEX called (excl SAS): {len(moex)} (expect ~4059)')

# Check dernier doc count
print(f'Dernier indice docs: {len(dernier)} (expect ~4639)')
print()
print('ALL CHECKS PASSED' if has_dl > 13000 and late > 13000 and s1 == 'FAV' and len(moex) < 5000 else 'SOME CHECKS FAILED')
"
```

**Expected output:**
```
date_limite extracted: ~13613 rows
PENDING_LATE: ~13345 rows
Bureau de Contrôle labels: s1=FAV, s2=SUS, s3=DEF
MOEX called (excl SAS): ~4059
Dernier indice docs: ~4639
ALL CHECKS PASSED
```

---

## Files modified (summary)

| File | Changes |
|------|---------|
| `src/normalize.py` | `interpret_date_field()` rewritten with date_limite extraction; `_extract_date_limite()` added; `normalize_responses()` extracts date_limite + forces 0-SAS to exception |
| `src/reporting/data_loader.py` | `_read_ged_data_date()` rewritten to match actual AxeoBIM format |
| `src/reporting/consultant_fiche.py` | New definitive reference tables; `_resolve_status_labels()` reads from hardcoded table; `_filter_for_consultant()` uses dernier_df; `_build_consultant_meta()` uses new tables; `resolve_consultant_name()` added; `_attach_derived()` _on_time uses date_limite |
| `app.py` | `get_consultant_fiche()` calls `resolve_consultant_name()` |
