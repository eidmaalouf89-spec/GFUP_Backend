# Flat GED Input Contract (FGIC)

**Contract version:** v1.0  
**Date:** 2026-04-23  
**Source:** `ged_flat_builder/` frozen snapshot — DO NOT modify the builder to satisfy this contract. If a discrepancy is found, fix the contract first, then raise a flag for Eid.  
**Produced by:** `ged_flat_builder/writer.py` (`R_COLS`, `O_COLS`, `D_COLS`)  
**Applicable to:** `FLAT_GED.xlsx` output and `run_report.json`

---

## 1. Overview

The flat GED builder (`ged_flat_builder/`) reads a GED Excel export (`GED_export.xlsx`) and produces:

| File | Mode | Contents |
|------|------|----------|
| `FLAT_GED.xlsx` | batch & single | Main output workbook |
| `DEBUG_TRACE.csv` | **batch only** | Full audit trail as CSV (separate file — NOT in workbook) |
| `run_report.json` | batch & single | Machine-readable run summary |

`FLAT_GED.xlsx` always contains two sheets: `GED_RAW_FLAT` and `GED_OPERATIONS`.  
In **single mode** only, it also contains a third sheet: `DEBUG_TRACE` (inside the workbook).  
In **batch mode**, `DEBUG_TRACE` is written as a separate `DEBUG_TRACE.csv` file (not in the workbook) for performance reasons (~90× faster than Excel at 400k+ rows).

---

## 2. Batch vs Single Mode Differences

| Aspect | Single mode | Batch mode |
|--------|-------------|------------|
| Target | One (numero, indice) | All documents |
| FLAT_GED.xlsx sheets | GED_RAW_FLAT, GED_OPERATIONS, **DEBUG_TRACE** | GED_RAW_FLAT, GED_OPERATIONS (no DEBUG_TRACE sheet) |
| DEBUG_TRACE output | Sheet 3 of FLAT_GED.xlsx (styled, with per-cell fills) | Separate `DEBUG_TRACE.csv` (no per-cell styling) |
| Per-cell colours | Yes (all three sheets) | Headers only; data rows are plain values |
| Write mode | Normal openpyxl workbook | `write_only=True` streaming (lower memory) |
| CLI args | `--mode single --numero N --indice X` | `--mode batch` |
| Row-index override | `--row-index N` (for debugging duplicate rows) | Not applicable |

---

## ⚠ Known Limitation — Submission Instances

The current flat GED model operates at the `(numero, indice)` level — but this is **not** always a unique document identity.

Multiple real submission instances (resubmissions, parallel submissions, corrections) may exist under the same `(numero, indice)`. The resolver classifies these using `instance_role`:

- `ACTIVE` — the selected candidate for this (numero, indice)
- `INACTIVE_DUPLICATE` — same date as ACTIVE; true duplicate
- `SEPARATE_INSTANCE` — different date from ACTIVE; distinct submission event
- `INCOMPLETE_BUT_TRACKED` — zero-score winner; data is incomplete

**However:**
- `GED_OPERATIONS` reflects **only the ACTIVE instance** for each (numero, indice)
- Non-ACTIVE instances are visible only in `DEBUG_TRACE` via `instance_role` and `submission_instance_id`
- True multi-cycle reconstruction (distinguishing `SEPARATE_INSTANCE` rows as independent workflow cycles) is **deferred to future layers (Chain/Onion, Step 12)**

This limitation is accepted for Phase 2 (integration and validation). Steps 8 and 9 explicitly operate at document-code level and treat submission-instance collapsing as a declared, auditable constraint — not a silent loss.

---

## 3. Sheet 1 — GED_RAW_FLAT

**Grain:** One row per called, non-exception-list approver per document.  
NOT_CALLED approvers and Exception List columns are excluded.

Source list in `writer.py`: `R_COLS` (21 columns).

| # | Column | Type | Nullable | One-line meaning | Source |
|---|--------|------|----------|------------------|--------|
| 1 | `numero` | int | N | Document number (from GED `NUMERO` column) | Raw GED |
| 2 | `indice` | str | N | Revision index (A, B, C… from GED `INDICE`) | Raw GED |
| 3 | `lot` | str | N | Lot code (e.g. A041, B013A) | Raw GED |
| 4 | `emetteur` | str | N | Contractor short code (e.g. LGD, AXI) | Raw GED |
| 5 | `titre` | str | N | Document title (`Libellé du document`) | Raw GED |
| 6 | `approver_raw` | str | N | Exact GED column header for this approver (e.g. `"A-BET Structure"`) | Raw GED |
| 7 | `approver_canonical` | str | N | Mapped internal name from `RAW_TO_CANONICAL`; `"UNKNOWN"` if no mapping found | Computed |
| 8 | `actor_type` | str | N | Role category: `SAS` / `CONSULTANT` / `MOEX` / `EMETTEUR` | Computed |
| 9 | `response_status_raw` | str/None | Y | Raw "Réponse" string from GED (e.g. `".VAO"`, `"VSO"`); None if empty | Raw GED |
| 10 | `response_status_clean` | str | Y | Cleaned status code after dot-strip + uppercase (e.g. `"VAO"`, `"VSO"`); empty string if no valid status | Computed |
| 11 | `response_status_code` | str | Y | Same value as `response_status_clean` (duplicate for legacy compatibility) | Computed |
| 12 | `response_status_scope` | str | Y | `"SAS"` if status suffix contains "SAS"; otherwise `"STANDARD"`; empty if no status | Computed |
| 13 | `response_date_raw` | datetime/str/None | Y | Raw "Date réponse" cell value — may be a datetime object or a French pending text string | Raw GED |
| 14 | `response_date` | str | Y | Parsed response date as ISO string `YYYY-MM-DD`; empty string if not answered | Computed |
| 15 | `date_status_type` | str | N | Approver state: `NOT_CALLED` / `PENDING_IN_DELAY` / `PENDING_LATE` / `ANSWERED` (see §8 for definitions) | Computed |
| 16 | `deadline_raw` | str | Y | Deadline text extracted from the pending text (e.g. `"2025/11/30"`); empty if not present | Computed |
| 17 | `deadline` | str | Y | Parsed GED-embedded deadline as ISO string `YYYY-MM-DD`; empty if not extractable | Computed |
| 18 | `commentaire` | str/None | Y | Free-text comment from GED "Commentaire" sub-column | Raw GED |
| 19 | `pj_flag` | int | N | `1` if attachment present in GED "PJ" sub-column; `0` otherwise | Computed |
| 20 | `is_sas` | bool | N | `True` if this approver is the SAS (0-SAS) approver | Computed |
| 21 | `raw_trace_key` | str | N | Traceability key: `"{numero}|{approver_raw}"` | Computed |

**Note on row inclusion:** A row is included in GED_RAW_FLAT only if `approver_canonical != "Exception List"` AND `date_status_type != "NOT_CALLED"`. This means GED_RAW_FLAT contains only approvers who were actually solicited.

**Note on `response_status_code`:** This field (col 11) is a duplicate of `response_status_clean` (col 10), kept for legacy compatibility with backend logic that referenced it before the clean/code split was formalised. New code should always read `response_status_clean`. Both fields always contain identical values.

**Note on synthetic SAS:** When SAS was never called in the GED (`sas_state = ABSENT`), a synthetic SAS row is inserted with `response_status_raw = "SYNTHETIC_VSO-SAS"`, `response_date = submittal_date`, `is_sas = True`, and `commentaire = "Synthetic SAS (auto-cleared — not called in GED)"`.

---

## 4. Sheet 2 — GED_OPERATIONS

**Grain:** One step row per document phase. Each document produces steps in this order: `OPEN_DOC` → `SAS` → `CONSULTANT` row(s) → `MOEX`. If SAS is PENDING, CONSULTANT and MOEX steps are omitted.

Source list in `writer.py`: `O_COLS` (37 columns).

| # | Column | Type | Nullable | One-line meaning | Source |
|---|--------|------|----------|------------------|--------|
| 1 | `numero` | int | N | Document number | Raw GED |
| 2 | `indice` | str | N | Revision index | Raw GED |
| 3 | `lot` | str | N | Lot code | Raw GED |
| 4 | `emetteur` | str | N | Contractor short code | Raw GED |
| 5 | `titre` | str | N | Document title | Raw GED |
| 6 | `step_order` | int | N | 1-based position of this step in the document's sequence (OPEN_DOC=1, then SAS, then CONSULTANTs in chrono order, MOEX last) | Computed |
| 7 | `step_type` | str | N | Phase category: `OPEN_DOC` / `SAS` / `CONSULTANT` / `MOEX` | Computed |
| 8 | `actor_type` | str | N | Role category: `EMETTEUR` / `SAS` / `CONSULTANT` / `MOEX` | Computed |
| 9 | `actor_raw` | str | N | Raw GED column header for this actor | Raw GED |
| 10 | `actor_clean` | str | N | Display name for the actor (from `CANONICAL_TO_DISPLAY`) | Computed |
| 11 | `status_raw` | str | Y | Raw status string (e.g. `".VAO"`); empty string if synthetic step | Raw GED |
| 12 | `status_clean` | str | Y | Cleaned status code (e.g. `"VAO"`); empty string if none | Computed |
| 13 | `status_code` | str | Y | Same as `status_clean` (explicit duplicate field) | Computed |
| 14 | `status_scope` | str | Y | `"SAS"` or `"STANDARD"`; empty if no status | Computed |
| 15 | `status_family` | str | N | Grouped status: `PENDING` / `APPROVED` / `APPROVED_WITH_REMARKS` / `REFUSED` / `OPENED` | Computed |
| 16 | `is_completed` | bool | N | `True` if status code is in `ALL_COMPLETED` set or `date_status_type = ANSWERED` | Computed |
| 17 | `is_blocking` | bool | N | `True` if step is currently blocking (date_status_type is `PENDING_IN_DELAY` or `PENDING_LATE`); set to `False` for pending consultants once MOEX_VISA is achieved | Computed |
| 18 | `requires_new_cycle` | bool | N | `True` if status code is `REF` or `DEF` — response requires a new submission cycle | Computed |
| 19 | `submittal_date` | str | N | Document creation date (`Créé le`) as ISO string `YYYY-MM-DD` — used as Phase A start | Raw GED |
| 20 | `sas_response_date` | str | Y | SAS response date as ISO string; empty if SAS is still pending | Computed |
| 21 | `response_date` | str | Y | This step's response date as ISO string; empty if not yet answered | Raw GED / Computed |
| 22 | `data_date` | str | N | Reference date read from `Détails!D15` — used for delay calculations; never `datetime.now()` | Raw GED |
| 23 | `global_deadline` | str | N | `submittal_date + 30 days` as ISO string — the outer deadline for all consultant/MOEX phases | Computed |
| 24 | `phase_deadline` | str | Y | This step's computed deadline as ISO string (see §9 Business Rule 5); empty for OPEN_DOC | Computed |
| 25 | `deadline_source` | str | N | Rule that produced `phase_deadline`: `COMPUTED_SAS_15D` / `GLOBAL_30D_AFTER_ON_TIME_SAS` / `COMPUTED_15D_AFTER_LATE_SAS` / `WAITING_FOR_SAS` / `NONE` | Computed |
| 26 | `retard_avance_days` | int | Y | Days ahead (`>0`) or late (`<0`) relative to `phase_deadline`; empty string for OPEN_DOC | Computed |
| 27 | `retard_avance_status` | str | Y | `"RETARD"` if late, `"AVANCE"` if ahead, empty string otherwise | Computed |
| 28 | `step_delay_days` | int | Y | `max(0, effective_date - phase_deadline)` — raw delay for this step before deduplication | Computed |
| 29 | `delay_contribution_days` | int | Y | This step's unique contribution to total delay after deduplication: `max(0, step_delay - cumulative_so_far)` | Computed |
| 30 | `cumulative_delay_days` | int | Y | Running sum of all delay contributions up to and including this step | Computed |
| 31 | `delay_actor` | str | Y | Display name of the actor owning the delay; `"NONE"` if no contribution | Computed |
| 32 | `chrono_source` | str | N | What drove step ordering: `"response_date"` / `"ged_order"` / `"SYNTHETIC"` | Computed |
| 33 | `observation` | str | Y | Comment/observation from the source GED row; empty if none | Raw GED |
| 34 | `pj_flag` | int/str | Y | `1` if attachment present; `0` or empty for synthetic steps | Raw GED |
| 35 | `source_trace` | str | N | Traceability key: `"{numero}|{step_label}"` (e.g. `"248000|OPEN_DOC"`) | Computed |
| 36 | `source_rows` | int | N | Number of raw GED rows that produced this step (0 for synthetic OPEN_DOC, 1 for real steps) | Computed |
| 37 | `operation_rule_used` | str | N | Rule label that generated this step (e.g. `"OPEN_DOC_INIT"`, `"SAS_FROM_0-SAS"`, `"SYNTHETIC_SAS_IF_NOT_CALLED"`) | Computed |

**Note on OPEN_DOC:** `OPEN_DOC` is a **synthetic step** that does not exist in the GED. It represents the document submittal event (`Créé le` date). It has no status, no phase deadline, no delay values, and no source GED row (`source_rows = 0`). It is always `is_completed = True` and `is_blocking = False`. Downstream code must not attempt to derive workflow state from the OPEN_DOC step.

**Note on `is_blocking` (dynamic):** Blocking state is not static. A pending consultant step is blocking only while the cycle is open. Once `MOEX_VISA` is achieved, all remaining pending consultant rows are de-flagged (`is_blocking = False`) by the builder — even though they still have no response date. Code reading `is_blocking` must not infer that a `False` value means "responded"; it may mean "cycle closed by MOEX". Use `is_completed` to test for an actual response.

**Reading a single ops row:** Given a row where `numero=248000`, `indice=A`, `step_type=CONSULTANT`, `actor_clean="BET Structure"`, `is_completed=False`, `is_blocking=True`, `response_date=""`, `data_date="2025-11-15"`, `phase_deadline="2025-09-30"`, `step_delay_days=46`, `delay_contribution_days=20`, `cumulative_delay_days=46`: BET Structure has not yet responded on document 248000/A, their phase deadline was 2025-09-30, as of data date 2025-11-15 they are 46 days past deadline, contributing 20 days of unique delay (the other 26 were already counted by an earlier step), and this step is currently blocking progression.

---

## 5. Sheet 3 — DEBUG_TRACE

**Grain:** One row per GED approver column per document — **all** columns including NOT_CALLED and Exception List. This is the full audit trail for understanding how a document was classified.

In **single mode**: Sheet 3 of `FLAT_GED.xlsx`.  
In **batch mode**: Separate file `DEBUG_TRACE.csv` (not in workbook).

Source list in `writer.py`: `D_COLS` (23 columns).

| # | Column | Type | Nullable | One-line meaning | Source |
|---|--------|------|----------|------------------|--------|
| 1 | `numero` | int | N | Document number | Raw GED |
| 2 | `approver_raw` | str | N | Exact GED column header; synthetic rows append `" [SYNTHETIC]"` | Raw GED |
| 3 | `actor_type` | str | N | Role category; `"—"` for Exception List and UNKNOWN | Computed |
| 4 | `ged_ref_date` | str | N | Excel cell reference for the date sub-column (e.g. `"C1842"`); `"SYNTHETIC"` for synthetic rows | Computed |
| 5 | `ged_ref_resp` | str | N | Excel cell reference for the response sub-column | Computed |
| 6 | `ged_ref_cmt` | str | N | Excel cell reference for the comment sub-column | Computed |
| 7 | `raw_date` | str | Y | Raw "Date réponse" value stringified; empty if None | Raw GED |
| 8 | `raw_status` | str | Y | Raw "Réponse" value stringified; empty if None | Raw GED |
| 9 | `raw_comment` | str | Y | Raw "Commentaire" value stringified; empty if None | Raw GED |
| 10 | `mapped_canonical` | str | N | Canonical name after `RAW_TO_CANONICAL` lookup; `"UNKNOWN"` if no mapping | Computed |
| 11 | `mapped_status_clean` | str | Y | Cleaned status code; empty string if none | Computed |
| 12 | `status_code` | str | Y | Same as `mapped_status_clean` | Computed |
| 13 | `status_scope` | str | Y | `"SAS"` or `"STANDARD"`; empty if no status | Computed |
| 14 | `ged_extracted_deadline` | str | Y | Deadline date extracted from pending text pattern `(YYYY/MM/DD)`; empty if absent | Computed |
| 15 | `date_status_type` | str | N | Approver state: `NOT_CALLED` / `PENDING_IN_DELAY` / `PENDING_LATE` / `ANSWERED` | Computed |
| 16 | `computed_sas_deadline` | str | N | `submittal_date + 15 days` as ISO string — Phase A deadline for this document | Computed |
| 17 | `computed_phase_deadline` | str | Y | Phase deadline for this approver (SAS: same as `computed_sas_deadline`; consultants/MOEX: Phase B deadline); empty for Exception List / UNKNOWN | Computed |
| 18 | `deadline_source` | str | N | Rule label that produced `computed_phase_deadline`: `COMPUTED_SAS_15D` / `GLOBAL_30D_AFTER_ON_TIME_SAS` / `COMPUTED_15D_AFTER_LATE_SAS` / `WAITING_FOR_SAS` / `N/A` | Computed |
| 19 | `data_date_used` | str | N | `data_date` as ISO string — the `Détails!D15` value used in this run | Raw GED |
| 20 | `doc_code` | str | N | Compound key: `"{numero}|{indice}"` | Computed |
| 21 | `submission_instance_id` | str | N | Unique ID assigned to this GED row's submission instance (used by the resolver to distinguish duplicates) | Computed |
| 22 | `instance_role` | str | N | Resolver verdict: `ACTIVE` / `INACTIVE_DUPLICATE` / `SEPARATE_INSTANCE` / `INCOMPLETE_BUT_TRACKED` (see §9 Business Rule 8) | Computed |
| 23 | `instance_resolution_reason` | str | N | Human-readable explanation of why this instance received its `instance_role` | Computed |

---

## 6. run_report.json Schema

Written by `writer.py::write_run_report()`. All date values serialised as ISO strings.

> **Note:** Values in the example below are illustrative. Real counts depend on the project dataset (the actual GED export for this project has ~6 900 rows and ~4 800 documents).

```json
{
  "mode": "batch",
  "input_file": "input/GED_export.xlsx",
  "data_date": "2025-11-15",
  "total_rows_scanned": 3200,
  "rows_excluded_no_numero": 12,
  "unique_doc_codes": 847,
  "docs_with_duplicates": 23,
  "synthetic_sas_count": 140,
  "pending_sas_count": 5,
  "closure": {
    "MOEX_VISA": 612,
    "ALL_RESPONDED_NO_MOEX": 80,
    "WAITING_RESPONSES": 155
  },
  "success_count": 847,
  "skipped_count": 0,
  "failure_count": 0,
  "warning_count": 0,
  "failures": [],
  "elapsed_seconds": 14.2
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `mode` | str | `"batch"` or `"single"` |
| `input_file` | str | Path to the GED input file relative to the run directory |
| `data_date` | str (ISO date) | Reference date read from `Détails!D15`; used for all delay calculations |
| `total_rows_scanned` | int | All GED data rows read (before exclusions) |
| `rows_excluded_no_numero` | int | Rows skipped because NUMERO was missing, empty, or zero |
| `unique_doc_codes` | int | Count of distinct `(numero, indice)` pairs processed |
| `docs_with_duplicates` | int | Count of `(numero, indice)` pairs that had more than one GED row |
| `synthetic_sas_count` | int | Documents where SAS was never called — synthetic SAS row inserted |
| `pending_sas_count` | int | Documents where SAS exists but has not yet responded — consultant/MOEX steps skipped |
| `closure.MOEX_VISA` | int | Documents with cycle closure state `MOEX_VISA` |
| `closure.ALL_RESPONDED_NO_MOEX` | int | Documents with cycle closure state `ALL_RESPONDED_NO_MOEX` |
| `closure.WAITING_RESPONSES` | int | Documents still waiting (open cycle) |
| `success_count` | int | Documents processed without error |
| `skipped_count` | int | Documents skipped (zero-score resolution, etc.) |
| `failure_count` | int | Documents that raised a hard `GEDValidationError`; non-zero means data needs investigation |
| `warning_count` | int | Documents processed with a soft warning |
| `failures` | list[str] | Error messages for each failed document |
| `elapsed_seconds` | float | Wall-clock time for the run |

---

## 7. Enum / Vocabulary Reference

### date_status_type (used in GED_RAW_FLAT col 15 and DEBUG_TRACE col 15)

| Value | Meaning |
|-------|---------|
| `NOT_CALLED` | Approver never solicited — date field was empty/None |
| `PENDING_IN_DELAY` | Request sent, awaiting response, within deadline — date field contains "en attente" text |
| `PENDING_LATE` | Request sent, awaiting response, past deadline — date field contains "rappel" text |
| `ANSWERED` | Approver has replied — date field contains a real date |

### step_type (GED_OPERATIONS col 7)

| Value | Meaning |
|-------|---------|
| `OPEN_DOC` | Synthetic first step — models document submittal event |
| `SAS` | GEMO visa step (real or synthetic) |
| `CONSULTANT` | Any third-party consultant approver |
| `MOEX` | MOEX approval step (always last in sequence) |

### status_family (GED_OPERATIONS col 15)

| Value | Meaning |
|-------|---------|
| `OPENED` | OPEN_DOC synthetic step |
| `APPROVED` | VSO or VAO response |
| `APPROVED_WITH_REMARKS` | HM (with remarks) |
| `REFUSED` | REF or DEF |
| `PENDING` | No response yet (PENDING_IN_DELAY or PENDING_LATE) |

### instance_role (DEBUG_TRACE col 22)

| Value | Meaning |
|-------|---------|
| `ACTIVE` | Highest-scoring candidate selected for this (numero, indice) |
| `INACTIVE_DUPLICATE` | Same date as ACTIVE row — true duplicate |
| `SEPARATE_INSTANCE` | Different date from ACTIVE — distinct submission event |
| `INCOMPLETE_BUT_TRACKED` | Zero-score winner — kept in audit trail but data is incomplete |

### deadline_source (GED_OPERATIONS col 25 / DEBUG_TRACE col 18)

| Value | Meaning |
|-------|---------|
| `COMPUTED_SAS_15D` | SAS deadline = submittal + 15 days |
| `GLOBAL_30D_AFTER_ON_TIME_SAS` | Phase B deadline = submittal + 30 days (SAS responded on time) |
| `COMPUTED_15D_AFTER_LATE_SAS` | Phase B deadline = SAS response date + 15 days (SAS responded late) |
| `WAITING_FOR_SAS` | Phase B deadline not yet computable — SAS has not responded |
| `NONE` | No deadline applicable (OPEN_DOC step) |
| `N/A` | Exception List or UNKNOWN approver |

---

## 8. Business Rules (verbatim from README)

The following nine rules are carried over exactly from `prototype_v4.py` and are preserved in the frozen builder. Any downstream code must rely on these rules as stated here — do not infer them from the engine's legacy implementation.

### Rule 1 — DATA_DATE

Read from `Détails!D15`. Tool exits loudly if this cell is missing or not a date.

### Rule 2 — No NUMERO rule

Documents with a missing, empty, or zero NUMERO are fully excluded from GED_FLAT. Counted in `rows_excluded_no_numero`.

### Rule 3 — Status normalization

Raw GED status strings are normalized to a `(status_code, status_scope)` pair:
- Leading dots stripped, uppercased
- First token before `-` is the semantic code (VSO, VAO, REF, HM, FAV, SUS, DEF)
- Suffix containing "SAS" → `scope = SAS`; otherwise `scope = STANDARD`
- Unknown codes map to `"UNKNOWN"` (not silently dropped)

### Rule 4 — SAS state — three states

| State | Condition | Behaviour |
|-------|-----------|-----------|
| `ABSENT` | `0-SAS` column never called | Synthetic SAS inserted (VSO/SAS, `response_date = submittal_date`) |
| `ANSWERED` | `0-SAS` has a real response date | Normal flow — consultant phase proceeds |
| `PENDING` | `0-SAS` has pending text | Consultant + MOEX steps are skipped entirely |

### Rule 5 — Two-phase deadline model

- **Phase A — SAS deadline**: `submittal_date + 15 days`
- **Phase B — consultant/MOEX deadline**:
  - If SAS responded on time (≤ 15 days): `submittal_date + 30 days`
  - If SAS responded late (> 15 days): `sas_response_date + 15 days`

### Rule 6 — Delay contribution (no double-counting)

For each step in chronological order:
```
effective_date  = response_date  (if step closed)
                  data_date      (if step still open)
step_delay      = max(0, effective_date - phase_deadline)
contribution    = max(0, step_delay - cumulative_so_far)
cumulative     += contribution
```

Four invariants are checked after computing contributions:
1. Cumulative never decreases
2. Contribution ≥ 0
3. Contribution ≤ step_delay
4. sum(contributions) == final cumulative

### Rule 7 — Cycle closure

- **MOEX_VISA**: MOEX step exists, is completed, has a response date. Remaining pending consultant rows are de-flagged (`is_blocking = False`).
- **ALL_RESPONDED_NO_MOEX**: No MOEX, but all SAS + CONSULTANT rows have responded.
- **WAITING_RESPONSES**: Neither condition met — cycle is open.

### Rule 8 — Candidate resolution (duplicate rows)

Multiple GED rows can match the same (NUMERO, INDICE). The resolver:
1. Collects **all** matching rows — never stops at first match
2. Scores each row by progression evidence (MOEX +100, consultant +50, SAS +20, SAS pending +10)
3. Selects the highest-scoring row as `ACTIVE`
4. Ties broken by earliest GED row index
5. Same-date duplicates → `INACTIVE_DUPLICATE`
6. Different-date rows → `SEPARATE_INSTANCE`
7. Zero-score winner → `INCOMPLETE_BUT_TRACKED`

### Rule 9 — Step ordering in GED_OPERATIONS

`OPEN_DOC` → `SAS` → `CONSULTANT` rows (sorted: response_date ASC, then ged_order) → `MOEX` (forced last)

---

## 9. Source-Main Reference Layer

`config.py` imports from `input/source_main/` (link to main software preserved):

| File | Provides |
|------|----------|
| `consultant_mapping.py` | `RAW_TO_CANONICAL`, `EXCEPTION_COLUMNS`, `CANONICAL_TO_DISPLAY` |
| `status_mapping.py` | `VALID_STATUSES`, `PENDING_KEYWORDS`, `DEADLINE_DATE_PATTERN` |
| `ged_parser_contract.py` | `GED_SHEET_NAME`, `CORE_COLUMNS`, `HEADER_STRUCTURE` |

---

## 10. What the builder does NOT produce

Downstream code must not expect:
- Version/family groupings (e.g. `family_v1`, `v_count`) — no equivalent in flat GED
- Any computed `clean_GF` columns (merged cells, colours, row heights)
- Cue engine outputs
- Report memory overlays
- Chain/Onion logic
- Any use of `datetime.now()` — all dates are relative to `data_date`

---

*End of FLAT_GED_CONTRACT.md v1.0*
