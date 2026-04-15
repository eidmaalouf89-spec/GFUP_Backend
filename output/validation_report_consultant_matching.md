# Consultant Matching — Validation Report
**JANSA VISASIST | Generated: April 2026**

---

## 1. Overall Pipeline Results

| Metric | Value |
|--------|-------|
| Total consultant rows | 1 377 |
| **Matched** | **1 317** (95.6 %) |
| Unmatched | 60 (4.4 %) |
| Ambiguous (unresolved) | **0** |

---

## 2. Match Method Breakdown

| Method | Count | Description |
|--------|------:|-------------|
| `MATCH_BY_NUMERO_INDICE` | 977 | NUMERO + INDICE matched a unique GED candidate |
| `MATCH_BY_RECENT_INDICE_FALLBACK` | 172 | NUMERO + INDICE matched multiple GED candidates → most recently created selected |
| `MATCH_BY_DATE_PROXIMITY` | 131 | NUMERO alone had multiple candidates → resolved by date proximity to DATE_FICHE |
| `MATCH_BY_MIXED_HEURISTIC` | 37 | NUMERO had multiple candidates → resolved by SAS VAO/VSO filter then most recent |

> **Note on rows previously labelled "took first":**  
> The 172 rows now classified as `MATCH_BY_RECENT_INDICE_FALLBACK` were previously resolved by silently picking the first candidate in an arbitrary list. They are now explicitly labelled LOW confidence, fully traceable via `candidate_ids_considered` and `winning_candidate_id`, and **excluded from GF enrichment** until human review.

---

## 3. Confidence Breakdown

| Confidence | Count | GF Enrichment |
|------------|------:|---------------|
| **HIGH** | 954 | ✅ Auto-enriches GF |
| **MEDIUM** | 191 | ✅ Auto-enriches GF |
| **LOW** | 172 | ❌ Excluded — human review required |
| AMBIGUOUS_UNRESOLVED | 0 | ❌ Never enriches |

**Enrich-eligible total: 1 145 / 1 317 matched rows**  
→ GF Stage 1 and Stage 2 received 1 124 enriched rows (1 145 minus 21 that had no matching GF row found).

---

## 4. LOW Confidence Rows — Former "Took First" Cases (172 rows)

These rows use `MATCH_BY_RECENT_INDICE_FALLBACK`: NUMERO + INDICE matched multiple GED documents (typically the same NUMERO with two or more revision indices). The system now selects the **most recently created** GED document rather than the first in an arbitrary list.

**These 172 rows are excluded from GF enrichment.** To include them, a human reviewer should open `consultant_match_report.xlsx → MATCHED sheet` (filter Confidence = LOW), verify the `Winning Candidate ID` against `Candidates Considered`, and either confirm or override the match.

---

## 5. MEDIUM Confidence Rows (191 rows)

Three sub-types:

### 5a. MATCH_BY_DATE_PROXIMITY (131 rows)
NUMERO alone matched 2–N GED documents. The system selected the candidate whose GED `created_at` date is closest to the consultant's `DATE_FICHE`, within a 180-day window. The `Date Gap (days)` column records the winning gap.

### 5b. MATCH_BY_NUMERO_INDICE — INDICE not confirmed (23 rows)
NUMERO matched exactly one GED candidate but the consultant row carried no INDICE value. Confidence is MEDIUM rather than HIGH because the indice could not be cross-validated.

### 5c. MATCH_BY_MIXED_HEURISTIC (37 rows)
NUMERO had multiple candidates. The system filtered to those where the GED `0-SAS` approver column shows `VAO-SAS` or `VSO-SAS`, then selected the most recently created among survivors. Both SAS filter and recency selection recorded in rationale.

---

## 6. HIGH Confidence Rows (954 rows)

All matched via `MATCH_BY_NUMERO_INDICE` with a single unique GED candidate that confirms NUMERO **and** INDICE. Deterministic = YES. No heuristics involved.

---

## 7. Unmatched Rows (60 rows)

| Consultant Source | Unmatched Count |
|-------------------|----------------:|
| AVLS | 42 |
| SOCOTEC | 12 |
| TERRELL | 6 |
| LE_SOMMER | 0 |

Top reasons (see UNMATCHED sheet for full detail):
- NUMERO not found in GED at all (document not yet in GED system)
- NUMERO exists in GED but date gap exceeded 180-day proximity window
- Consultant reference format could not be parsed to a valid NUMERO

---

## 8. Representative Examples

### HIGH Confidence (MATCH_BY_NUMERO_INDICE)
```
LE_SOMMER | NUMERO=145525 INDICE=C STATUT=REF DATE=23/12/2025
  Method:       MATCH_BY_NUMERO_INDICE
  Rationale:    Exact NUMERO=145525 + INDICE=C — 1 unique GED candidate
  Deterministic: YES  |  Date Gap: —

LE_SOMMER | NUMERO=145532 INDICE=A STATUT=VAO DATE=23/12/2025
  Method:       MATCH_BY_NUMERO_INDICE
  Rationale:    Exact NUMERO=145532 + INDICE=A — 1 unique GED candidate
  Deterministic: YES  |  Date Gap: —
```

### MEDIUM Confidence (MATCH_BY_DATE_PROXIMITY)
```
LE_SOMMER | NUMERO=049214 INDICE=  STATUT=VSO DATE=15/01/2026
  Method:       MATCH_BY_DATE_PROXIMITY
  Rationale:    3 candidates, resolved by date proximity: 79 days between
                DATE_FICHE (15/01/2026) and GED created_at — unique closest within 180d
  Deterministic: NO  |  Date Gap: 79 days

TERRELL | NUMERO=028283 INDICE=A STATUT=VAO DATE=28/02/2025
  Method:       MATCH_BY_DATE_PROXIMITY
  Rationale:    3 candidates, resolved by date proximity: 27 days between
                DATE_FICHE (28/02/2025) and GED created_at — unique closest within 180d
  Deterministic: NO  |  Date Gap: 27 days
```

### MEDIUM Confidence (MATCH_BY_MIXED_HEURISTIC — SAS filter)
```
LE_SOMMER | NUMERO=149525 INDICE=C STATUT=VSO DATE=29/09/2025
  Method:       MATCH_BY_MIXED_HEURISTIC
  Rationale:    4 candidates, 3 carry SAS VAO/VSO approval (VSO-SAS);
                selected most recently created SAS-approved doc (created 23/05/2025)
  Indice Fallback: YES  |  Deterministic: NO

LE_SOMMER | NUMERO=149529 INDICE=  STATUT=VSO DATE=10/03/2026
  Method:       MATCH_BY_MIXED_HEURISTIC
  Rationale:    2 candidates, 2 carry SAS VAO/VSO approval (VSO-SAS);
                selected most recently created SAS-approved doc (created 01/08/2025)
  Indice Fallback: YES  |  Deterministic: NO
```

### LOW Confidence (MATCH_BY_RECENT_INDICE_FALLBACK — former "took first")
*See consultant_match_report.xlsx → MATCHED sheet, filter Confidence = LOW for all 172 rows.*

---

## 9. Key Files Generated

| File | Contents |
|------|----------|
| `output/consultant_match_report.xlsx` | 4-sheet report: MATCHED (colour-coded), UNMATCHED, AMBIGUOUS, SUMMARY |
| `output/GF_consultant_enriched_stage1.xlsx` | GF with date + status from 1 145 eligible consultant matches |
| `output/GF_consultant_enriched_stage2.xlsx` | GF with date + status + OBSERVATIONS from 1 145 eligible consultant matches |

---

## 10. Recommended Next Steps

1. **Review LOW confidence rows (172):** Open MATCHED sheet, filter Confidence = LOW. For each, compare `Candidates Considered` vs `Winning Candidate ID`. Approve or override.
2. **Review UNMATCHED rows (60):** Open UNMATCHED sheet. Check if AVLS rows 42 can be found under alternate NUMERO formats.
3. **Use Stage 2 output** (`GF_consultant_enriched_stage2.xlsx`) as the working GF if observations are to be included; use Stage 1 if only dates/statuses are needed.
