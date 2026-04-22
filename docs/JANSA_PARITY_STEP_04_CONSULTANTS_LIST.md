# JANSA PARITY — STEP 04: Consultants List Page

**Date:** 2026-04-22
**Run used for validation:** Run 3 (current, completed, non-stale)
**Status:** COMPLETE — CORRECTION APPLIED (Socotec vocab)

---

## 1. Legacy Consultants List Feature Inventory

All features observed in `ui/src/App.jsx` — `ConsultantsPage` component.

| Feature | Data Source / Field | Backend Method |
|---------|---------------------|----------------|
| Flat table, 9 columns | React grid layout | — |
| Name | `c.name` (raw canonical name from backend) | `compute_consultant_summary` |
| Called | `c.docs_called` | aggregator per consultant |
| Answered | `c.docs_answered` | aggregator per consultant |
| Rate | `c.response_rate * 100` (color-coded: ≥80% green, ≥50% amber, <50% red) | aggregator |
| Avg Days | `c.avg_response_days` (null → "—") | computed from answered rows vs doc created_at |
| VSO | `c.vso` (green column) | count of VSO status responses |
| VAO | `c.vao` (amber column) | count of VAO status responses |
| REF | `c.ref` (red column) | count of REF status responses |
| Open | `c.open` = `docs_called - docs_answered` (amber column) | aggregator |
| MOEX SAS highlight | `c.is_sas` → yellow border + `◆` prefix | synthetic row added by aggregator |
| Row count header | `{consultants.length} consultant(s) active` | — |
| Click → fiche | `setSelectedConsultant(c.name)` → `ConsultantFicheView` | `get_consultant_fiche(c.name)` |
| Focus mode | Data reloaded; list counts unchanged (no focus filtering of consultant list) | `apply_focus_filter` computes `focus_owned` but list unchanged |
| HM column | NOT shown (not in legacy table) | — |
| Open Blocking | NOT shown in legacy (computed but not displayed) | — |

---

## 2. JANSA Consultants List Feature Inventory (Before Fixes)

All features in `ui/jansa/consultants.jsx` — `ConsultantsPage` component.

| Feature | Data Source | Status Before Fix |
|---------|-------------|-------------------|
| 3-level hierarchy (MOEX / Primary / Secondary) | `window.CONSULTANTS[].group` from `adapt_consultants` | ✅ Intentional JANSA design |
| MOEX hero card: name, role, badge | `c.name`, `c.role`, `c.badge` | ✅ Correct |
| MOEX card: Documents (total), Répondus, En attente, Conformité% | `c.total`, `c.answered`, `c.pending`, `c.pass_rate` | ✅ Correct |
| Primary card: pass_rate, total, pending | `c.pass_rate`, `c.total`, `c.pending` | ✅ Correct |
| Secondary chip: pass_rate, total | `c.pass_rate`, `c.total` | ✅ Partial (missing open count) |
| VSO / VAO / REF breakdown | — | ❌ MISSING — adapter computed but did not return vso/vao/ref |
| avg_response_days | — | ❌ MISSING — not in adapter output |
| HM count | — | ❌ MISSING (not shown in legacy either — deferred) |
| open_blocking | — | ❌ MISSING from adapter output |
| focus_owned badge | — | ❌ MISSING — field was in adapter output but not displayed |
| Navigation: click → fiche | `onOpen(c)` → shell `navigateTo('ConsultantFiche', c)` → uses `c.canonical_name` | ✅ Correct |
| Focus mode reload | `window.jansaBridge.refreshForFocus()` → rebuilds `window.CONSULTANTS` | ✅ Correct |

---

## 3. Consultants List Parity Matrix

| Legacy Feature | JANSA Equivalent | Status | Root Cause |
|----------------|-----------------|--------|------------|
| Name display | `c.name` (with display suffix from CONSULTANT_DISPLAY_NAMES) | FULL_PARITY | — |
| Canonical name for navigation | `c.canonical_name` → fiche API | FULL_PARITY | — |
| Called (docs_called) | `c.total` on MOEX + Primary cards | PARTIAL_PARITY | — (Secondary chip now shows total too) |
| Answered (docs_answered) | `c.answered` on MOEX card | PARTIAL_PARITY | — (Primary/Secondary don't show answered count) |
| Rate (response_rate%) | `c.pass_rate` on all cards | FULL_PARITY | — |
| Avg Days | — before fix | MISSING → FIXED | BRIDGE (not in adapter output) |
| VSO count | — before fix | MISSING → FIXED | BRIDGE (vso computed but not returned) |
| VAO count | — before fix | MISSING → FIXED | BRIDGE (vao computed but not returned) |
| REF count | — before fix | MISSING → FIXED | BRIDGE (ref not in adapter output) |
| Open (called − answered) | `c.pending` on MOEX + Primary | FULL_PARITY | — |
| MOEX SAS highlight | `is_sas: True` in adapter | FULL_PARITY | — (JANSA renders MOEX group separately) |
| Row count header | `{all.length} ÉQUIPES` in masthead | FULL_PARITY | — |
| Click → fiche navigation | `onOpen(c)` → `navigateTo('ConsultantFiche', c)` | FULL_PARITY | — |
| Focus mode list refresh | `refreshForFocus` → rebuilds CONSULTANTS | FULL_PARITY | — |
| focus_owned display | — before fix | MISSING → FIXED | UI (field present in adapted data, badge not rendered) |
| HM count | Not shown in legacy either | N/A | — |
| Open blocking | Not shown in legacy either | N/A | — |

---

## 4. Root Cause of Each Mismatch

| Issue | Root Cause | Layer |
|-------|-----------|-------|
| `vso` not in adapter output | `adapt_consultants` declared `vso = c.get("vso",0)` locally but never put it in the returned dict | BRIDGE |
| `vao` not in adapter output | Same — `vao` declared locally, not returned | BRIDGE |
| `ref` not in adapter output | Never extracted from raw data in adapter | BRIDGE |
| `hm` not in adapter output | Never extracted from raw data in adapter | BRIDGE |
| `avg_response_days` not in adapter output | Never extracted from raw data in adapter | BRIDGE |
| `open_blocking` not in adapter output | Never extracted from raw data in adapter | BRIDGE |
| VSO/VAO/REF not displayed on any card | No breakdown component existed in consultants.jsx | UI |
| avg_response_days not displayed | No display code in any card component | UI |
| focus_owned badge not displayed | Field was in adapter output but no rendering logic existed | UI |

---

## 5. Fixes Applied

### BRIDGE — `src/reporting/ui_adapter.py`

Added six missing fields to `adapt_consultants()` return dict. The local variables `vso` and `vao` were already declared (dead code); they now flow into the output. Four new fields are read directly from the raw entry:

```python
"vso": vso,                              # was declared locally, now returned
"vao": vao,                              # was declared locally, now returned
"ref": c.get("ref", 0),                  # NEW
"hm": c.get("hm", 0),                   # NEW
"avg_response_days": c.get("avg_response_days"),  # NEW — float or None
"open_blocking": c.get("open_blocking", 0),       # NEW
```

No computation added. All values come directly from `compute_consultant_summary()` output which already computed them.

### UI — `ui/jansa/consultants.jsx`

**1. Added `CnBreakdown` component:**

Compact inline display of VSO / VAO / REF counts (color-coded) + avg days. Renders nothing if all values are null. Used by all three card tiers.

```jsx
function CnBreakdown({ vso, vao, ref_, avg_days }) { ... }
```

VSO in green (`var(--good)`), VAO in accent blue (`var(--accent)`), REF in red (`var(--bad)`), avg days in muted text.

**2. Updated `MoexCard`:**

- Added `focus_owned` badge to the badge row (only renders when `c.focus_owned > 0`)
- Added full-width `CnBreakdown` row below the KPI stat blocks, separated by a border-top line
- Uses `gridColumn: '1 / -1'` to span the 3-column card grid

**3. Updated `PrimaryCard`:**

- Added `focus_owned` badge (compact "F{n}" label) next to the consultant name
- Added `CnBreakdown` as a new bottom section below the stats bar

**4. Updated `SecondaryChip`:**

- Added VSO / VAO / REF as a micro breakdown (`40 / 32 / 5` format in green/accent/red) below the total count in the right column
- Added `focus_owned` display ("F{n}") when non-zero

---

## 6. Validation Results — Run 3

### All 16 fields present check

Every adapted consultant entry now has all required fields present (validated via Python field check):

```
[Primary  ] Bureau de Contrôle             OK
[Secondary] AMO HQE                        OK
[MOEX     ] Maître d'Oeuvre EXE            OK
[Primary  ] ARCHITECTE                     OK
[Secondary] BET Acoustique                 OK
[Primary  ] BET Structure                  OK
[Primary  ] BET Electricité                OK
[Primary  ] BET CVC                        OK
[Secondary] BET Façade                     OK
[Primary  ] BET Plomberie                  OK
[Secondary] BET POL                        OK
[Secondary] BET SPK                        OK
[Secondary] BET VRD                        OK
[Secondary] BET Ascenseur                  OK
[Secondary] BET EV                         OK
[MOEX     ] MOEX SAS                       OK
```

### Representative consultant spot-checks

| Consultant | Group | vso | vao | ref | avg_days | pass_rate | pending | match vs legacy |
|-----------|-------|-----|-----|-----|----------|-----------|---------|-----------------|
| MOEX SAS | MOEX | 4,929 | 0 | 837 | 2.5j | 91% | 538 | ✅ All match raw |
| Maître d'Oeuvre EXE | MOEX | 49 | 717 | 350 | 61.3j | 32% | 2,757 | ✅ All match raw |
| ARCHITECTE | Primary | 368 | 1,347 | 392 | 37.1j | 78% | 788 | ✅ All match raw |
| BET SPK | Secondary | 40 | 32 | 5 | 27.0j | 86% | 13 | ✅ All match raw |
| Bureau de Contrôle | Primary | 0 | 0 | 0 | 107.8j | 19% | 3,896 | ✅ All match raw |

All adapted values exactly match the raw `compute_consultant_summary()` output — no computation in the adapter, only field mapping.

### Focus mode validation

In focus mode, `focus_owned` is correctly non-zero for 11 consultants:

| Consultant | focus_owned |
|-----------|------------|
| ARCHITECTE | 200 |
| BET Electricité | 137 |
| Bureau de Contrôle | 64 |
| BET CVC | 69 |
| BET Acoustique | 59 |
| AMO HQE | 48 |
| BET VRD | 13 |
| BET Façade | 11 |
| BET EV | 8 |
| BET Plomberie | 3 |
| BET Structure | 3 |

In normal mode, all `focus_owned` values are 0 → no focus badges rendered → no visual clutter.

### Fiche navigation validation

All 16 `canonical_name` values resolve correctly through `resolve_consultant_name()` without remapping or errors. Navigation from JANSA card to fiche page is confirmed correct.

### Babel/JSX parse check

All 5 JANSA JSX files parse without errors after changes:

```
ui/jansa/shell.jsx:       PARSE OK (29816 chars)
ui/jansa/overview.jsx:    PARSE OK (33874 chars)
ui/jansa/consultants.jsx: PARSE OK (16731 chars)
ui/jansa/fiche_base.jsx:  PARSE OK (36258 chars)
ui/jansa/fiche_page.jsx:  PARSE OK (1948 chars)
```

### Regression checks

- ✅ No crash risk — only additive changes (new fields in bridge output, new components in UI)
- ✅ No fake values — all vso/vao/ref/avg come from real backend computation
- ✅ Overview page untouched
- ✅ Fiche pages untouched (navigation API unchanged)
- ✅ Shell untouched
- ✅ No other page modified
- ✅ Focus mode: focus_owned badge auto-hides when 0 (normal mode looks identical to before)

---

## 7. Remaining Consultants List Limitations

1. **`answered` count not shown on Primary and Secondary cards** — MOEX card shows it, but Primary and Secondary cards don't have an explicit "Répondus" stat block. The `pass_rate` (Conformité%) encodes the same ratio, so functional parity is met; showing the raw count is a display enhancement, not a parity gap.

2. **HM (Hors Mission) not displayed** — Field now present in adapted data but not rendered. Legacy table also does not show HM. Not a parity gap.

3. **`trend` sparkline is empty `[]`** — Requires historical run data (multiple runs stored). Not available in single-run mode. All cards gracefully skip sparkline rendering when `trend` is empty.

4. **Secondary chip does not show avg_days** — Only VSO/VAO/REF micro breakdown is shown. The chip layout is compact; avg_days would require a wider chip. This is a layout constraint, not a data gap.

5. **MOEX SAS card** — Renders in the MOEX group (correct), but `is_sas: True` could trigger a distinct visual treatment (e.g., yellow highlight like legacy). Currently uses the same MOEX group visual. Low priority.

6. **HM count in `adapt_consultants`** — Now included in bridge output for future use. The aggregator computes HM correctly (e.g., AMO HQE has 2,346 HM responses).

---

## 8. Updated Parity Tracking

| Category | Before Step 04 | After Step 04 |
|----------|---------------|--------------|
| Closed (FULL_PARITY) | 13 | 19 |
| Remaining | 22 | 16 |
| Parity % | ~37% | ~54% |

### Features Closed This Step

1. VSO count per consultant (bridge: now in adapter output; UI: CnBreakdown component)
2. VAO count per consultant (bridge: now in adapter output; UI: CnBreakdown component)
3. REF count per consultant (bridge: now in adapter output; UI: CnBreakdown component)
4. avg_response_days per consultant (bridge + UI)
5. open_blocking per consultant (bridge — data now available for future use)
6. focus_owned badge display in focus mode (UI)

### Files Changed

| File | Layer | Change |
|------|-------|--------|
| `src/reporting/ui_adapter.py` | BRIDGE | Added `vso`, `vao`, `ref`, `hm`, `avg_response_days`, `open_blocking`, `s1_label`, `s2_label`, `s3_label` to `adapt_consultants()` output |
| `ui/jansa/consultants.jsx` | UI | Added `CnBreakdown` component; enriched `MoexCard`, `PrimaryCard`, `SecondaryChip` with breakdown + focus_owned badge |
| `src/reporting/aggregator.py` | BACKEND | Added `_CONSULTANT_STATUS_VOCAB` constant; fixed `compute_consultant_summary` to use per-consultant status labels for vso/vao/ref counting; added `s1_label`, `s2_label`, `s3_label` to output dict |

---

## STEP 4 CORRECTION — Consultant-Specific Status Vocabularies

**Date:** 2026-04-22
**Trigger:** Bureau de Contrôle (SOCOTEC) showed VSO=0, VAO=0, REF=0 in JANSA — misleading zeros because the generic counting never matched their actual statuses.

### Bureau de Contrôle / SOCOTEC — Root Cause Analysis

**Observed status values in responses_df for Bureau de Contrôle:**

| status_clean | count |
|-------------|-------|
| FAV | 725 |
| SUS | 139 |
| DEF | 57 |
| HM | 4 |
| VSO | 0 |
| VAO | 0 |
| REF | 0 |

SOCOTEC uses a native French status vocabulary:
- **FAV** (Favorable) — semantic equivalent of VSO (approved)
- **SUS** (Suspendu) — semantic equivalent of VAO (approved with reservations)
- **DEF** (Défavorable) — semantic equivalent of REF (refused)

**Legacy behavior:** The legacy `ConsultantsPage` shows columns labeled "VSO / VAO / REF". For Bureau de Contrôle, these columns all show 0 because `compute_consultant_summary` hardcoded `status_clean == "VSO"` etc. This is a **pre-existing bug in legacy** — the legacy also shows misleading zeros for Socotec.

**Existing authority:** `consultant_fiche.py` already documented this mapping:
```python
STATUS_LABELS_BY_CANONICAL = {
    "Bureau de Contrôle": {"s1": "FAV", "s2": "SUS", "s3": "DEF"},
    # All others default to VSO/VAO/REF
}
```
The fiche page already uses FAV/SUS/DEF correctly. The bug existed only in `compute_consultant_summary` (list-level) which had never adopted the same lookup.

**Other consultants requiring non-standard vocabulary:** Only Bureau de Contrôle in this project. All other 15 consultants use VSO/VAO/REF/HM natively — confirmed by cross-tabulation of `approver_canonical × status_clean`.

### Fix Applied

**Layer classification:** BACKEND + BRIDGE + UI

**BACKEND — `src/reporting/aggregator.py`**

Added `_CONSULTANT_STATUS_VOCAB` constant (mirrors `STATUS_LABELS_BY_CANONICAL` from `consultant_fiche.py`):
```python
_CONSULTANT_STATUS_VOCAB = {
    "Bureau de Contrôle": {"s1": "FAV", "s2": "SUS", "s3": "DEF"},
}
```

Changed status counting from hardcoded to per-consultant:
```python
# Before (hardcoded — wrong for Bureau de Contrôle):
vso = len(grp[grp["status_clean"] == "VSO"])
vao = len(grp[grp["status_clean"] == "VAO"])
ref = len(grp[grp["status_clean"] == "REF"])

# After (per-consultant vocabulary):
_s_labels = _CONSULTANT_STATUS_VOCAB.get(name, {})
_s1 = _s_labels.get("s1", "VSO")
_s2 = _s_labels.get("s2", "VAO")
_s3 = _s_labels.get("s3", "REF")
vso = len(grp[grp["status_clean"] == _s1])
vao = len(grp[grp["status_clean"] == _s2])
ref = len(grp[grp["status_clean"] == _s3])
```

Also added `"s1_label": _s1, "s2_label": _s2, "s3_label": _s3` to the output dict.

**BRIDGE — `src/reporting/ui_adapter.py`**

Added three fields to `adapt_consultants()` output:
```python
"s1_label": c.get("s1_label", "VSO"),
"s2_label": c.get("s2_label", "VAO"),
"s3_label": c.get("s3_label", "REF"),
```

The MOEX SAS synthetic row (generated separately in the aggregator) does not include s-label fields in the raw dict, so the `c.get(..., "VSO")` default applies correctly — MOEX SAS displays VSO/VAO/REF labels as expected.

**UI — `ui/jansa/consultants.jsx`**

`CnBreakdown` updated to accept `s1_label`, `s2_label`, `s3_label` props and use them instead of hardcoded "VSO"/"VAO"/"REF":
```jsx
function CnBreakdown({ vso, vao, ref_, avg_days, s1_label, s2_label, s3_label }) {
  const l1 = s1_label || 'VSO';
  const l2 = s2_label || 'VAO';
  const l3 = s3_label || 'REF';
  const items = [
    { label: l1, value: vso ?? 0, color: 'var(--good)' },
    { label: l2, value: vao ?? 0, color: 'var(--accent)' },
    { label: l3, value: ref_ ?? 0, color: 'var(--bad)' },
  ];
```

All three card types (MoexCard, PrimaryCard, SecondaryChip) now pass `s1_label`/`s2_label`/`s3_label` to the breakdown component. The SecondaryChip micro-breakdown adds a `title` tooltip showing the full label+count for each status.

### Validation — Bureau de Contrôle on Run 3

| Field | Expected | Actual | Match |
|-------|---------|--------|-------|
| s1_label | FAV | FAV | ✅ |
| vso (=FAV count) | 725 | 725 | ✅ |
| s2_label | SUS | SUS | ✅ |
| vao (=SUS count) | 139 | 139 | ✅ |
| s3_label | DEF | DEF | ✅ |
| ref (=DEF count) | 57 | 57 | ✅ |
| hm | 4 | 4 | ✅ |
| open | 3896 | 3896 | ✅ |
| pass_rate | 19% | 19% | ✅ |

### Regression — Standard Consultants on Run 3

| Consultant | s1_label | vso | s2_label | vao | s3_label | ref | OK |
|-----------|---------|-----|---------|-----|---------|-----|-----|
| ARCHITECTE | VSO | 368 | VAO | 1347 | REF | 392 | ✅ |
| BET SPK | VSO | 40 | VAO | 32 | REF | 5 | ✅ |
| Maître d'Oeuvre EXE | VSO | 49 | VAO | 717 | REF | 350 | ✅ |
| MOEX SAS | VSO | 4929 | VAO | 0 | REF | 837 | ✅ |

All 5 JSX files parse clean after correction. No regressions.
