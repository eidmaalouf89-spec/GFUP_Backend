# CLOSED — Phase 8B RAW → FLAT Reconciliation

**Status: CLOSED (2026-05-01).**

**Outcome (§17 decision gate): C — existing reason logic incomplete + partially incorrect.**

Identity contract PASS:
- RAW unique numero == FLAT unique numero == **2,819**
- RAW unique (numero, indice) == FLAT == **4,848**

SAS REF decomposition: **99.3% covered (830 / 836 rows)**.

Sheet 07 SAS REF row classification: 283 matched canonical, 345
DUPLICATE_FAVORABLE_KEPT, 143 DUPLICATE_MERGED, 32
ACTIVE_VERSION_PROJECTION, 27 MALFORMED_RESPONSE, **6 UNEXPLAINED**.

Reasons audit: 389 sites total — 40 VALID, 1 INVALID (`GEDDocumentSkip`
declared but never raised), 30 AMBIGUOUS, 318 MISSING.

Report integration: 1,245 reports → 0 NO_MATCH, 942 enrich FLAT, 58 supply
primary, 226 blocked on confidence.

Shadow model: 27,134 shadow operational rows; UNEXPLAINED residual = 6.

Phase 8 audit one-liner unchanged throughout:
`AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX`.

Residual unexplained rows + GEDDocumentSkip cleanup are routed to future
backlog / **Phase 8C optional cleanup (NOT ACTIVE for current release)**.
See `context/07_OPEN_ITEMS.md` "Phase 8 family — closed for current release"
section. Final report: `output/debug/PHASE_8B_FINAL_REPORT.md`. Canonical
RAW/FLAT reference: `docs/RAW_TO_FLAT_GED_KNOWLEDGE.md`.

Read-only reference. Do not continue implementation in this file without
explicit reopening.

---

# Phase 8B — RAW → FLAT Reconciliation + Report Integration

> **Original status (charter dated 2026-04-30) — superseded by closure banner above.**
>
> Plan doc only. No step has shipped. Steps 8B.1 through 8B.10 are read-only investigation; production source under `src/flat_ged/*` becomes the focus area only after the §15 decision gate, and only with written approval.

This MD is **self-contained**. An agent or engineer assigned only this phase can execute it cold without reading any other file in `docs/implementation/`. Each numbered step below is also self-contained — it states its objective, files to read, files to create, validation, and risk in isolation.

Phase 8 (Count Lineage Fix) shipped the audit harness that surfaced the gap this phase will close. The audit's only remaining FAIL is `status_SAS_REF@L1_FLAT_GED_XLSX` — RAW GED has 836+1 SAS REF rows, FLAT_GED.xlsx has 284. That 552-row gap is the headline target. See `docs/implementation/PHASE_8_COUNT_LINEAGE_FIX.md` for context (closed; reference only).

---

## 1. Mission

**One-line:** Phase 8B does not try to make RAW and FLAT look identical. Phase 8B proves that every RAW GED event and every report event has a named destination — or a named reason for absence — in FLAT.

**Paragraph:** RAW GED is the operational source of truth (Doc. sous workflow, x versions). FLAT GED is a normalized projection produced by `src/flat_ged/transformer.py`. Today the projection drops events that may or may not be intended; we cannot tell which because there is no event-level trace between the two. Phase 8B builds that trace, classifies every difference into a documented category (active-version projection, duplicate merge, old-cycle supersession, SAS-cycle collapse, exception column, malformed response, …), and demands that the residual `UNEXPLAINED` count reach zero before any production-code change is even discussed. Reports (consultant report ingest) currently merge into responses downstream of FLAT via `effective_responses`; Phase 8B also asks whether reports should appear at the FLAT level, with explicit confidence and provenance.

---

## 2. Hard Constraints

- App must keep starting and serving across every step.
- Steps 8B.1 through 8B.9 are **read-only investigation**. Production source is untouched until the §15 decision gate.
- No pipeline rerun in Cowork unless explicitly authorised. The trace must work against the existing `runs/run_0000/` artifact and the existing `output/intermediate/FLAT_GED.xlsx`.
- No business logic moved into JSX. UI is out of scope for Phase 8B.
- The Phase 8 do-not-touch list largely carries forward, except that `src/flat_ged/*` becomes the focus area **after** the §15 gate. See §17 for the per-step do-not-touch list.

---

## 3. Risk Summary

| Step | Risk | Why |
|------|------|-----|
| 8B.1 RAW event extraction | Low | New script under `scripts/`. Reads `input/GED_export.xlsx`, writes `output/debug/raw_ged_trace.csv`. No production touched. |
| 8B.2 FLAT event extraction | Low | New script. Reads `output/intermediate/FLAT_GED.xlsx`, writes `output/debug/flat_ged_trace.{csv,xlsx}`. |
| 8B.3 Base identity parity | Low | Hard equality check on `numero` and `numero+indice` sets. Pure read. **BLOCKER on mismatch** — STOP and report; do not auto-explain. |
| 8B.4 Actor call parity | Low | Set comparison + per-version diffs. Audit-only. |
| 8B.5 Response/status parity (D-011 trace) | Low | The headline trace. Decomposes the 836 → 284 SAS REF gap into the named explanation taxonomy. Audit-only. |
| 8B.6 Date/comment parity | Low | Field-level comparison. Audit-only. Format normalisation allowed; value drift not. |
| 8B.7 Reason logic audit | Low | Read-only audit of existing exclusion / reason code. **Do not remove or modify reason code in this step.** |
| 8B.8 Report integration trace | Low (audit-only) → **Medium** if a FLAT schema extension is later proposed | Records how reports would attach at the FLAT level. The trace itself is read-only. The decision to extend the FLAT schema is taken at the §15 gate. |
| 8B.9 Shadow corrected FLAT model | Low | Writes to `output/debug/SHADOW_FLAT_GED_*`. Never to `output/intermediate/`. Never replaces the production FLAT artifact. |
| 8B.10 Decision gate | n/a — checkpoint, not a code step | After this gate: production patches under `src/flat_ged/*` become possible, **HIGH risk**, with explicit written approval. |

Steps 8B.1 through 8B.9 are LOW risk. The §15 gate is the inflection point. Any production-source change after the gate is HIGH risk and follows the standard project rules (objective / findings / plan / files / validation / risk before any code lands).

---

## 4. Standard Rules (embedded — do not skip)

### Tooling

Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) for inspecting Windows-mounted source files. The Linux mount caches stale views — see `context/11_TOOLING_HAZARDS.md` H-1 and H-1.1. Bash IS fine for executing scripts (`python scripts/...`, `python -m py_compile`, `python scripts/audit_counts_lineage.py`).

For **bulk Windows-mounted xlsx I/O** (re-parsing `FLAT_GED.xlsx` or `GED_export.xlsx` end-to-end), expect H-5: sandbox times out, Windows-shell completes in seconds. The 8B.1 and 8B.2 extraction scripts both do bulk xlsx reads — assume Windows-shell verification will be needed for the full traces. Sandbox can validate small samples and the script logic.

For **pytest**, expect H-4: tests that import the reporting chain may hang in sandbox. Mock-only tests run fine. Plan to confirm test passes via Windows shell at each step.

### Priorities

1. App must always run.
2. Investigation-and-documentation first. Steps 8B.1 through 8B.9 ship NO production code.
3. No silent renames. No silent contract changes. No row drops.
4. Every patch in 8B.10+ (post-gate) is the smallest patch that makes the trace clean.
5. If the trace shows a divergence is **expected** (a documented projection rule), record it in the explanation taxonomy — do NOT patch code to "fix" it.

### Forbidden moves during Phase 8B (steps 8B.1 through 8B.9)

- Do NOT modify `src/flat_ged/*`. That comes after the §15 gate.
- Do NOT modify `src/reporting/data_loader.py`, `src/reporting/aggregator.py`, `src/reporting/ui_adapter.py`, `src/workflow_engine.py`, `src/effective_responses.py` during the trace.
- Do NOT modify the production FLAT artifact (`output/intermediate/FLAT_GED.xlsx`) or the cache (`output/intermediate/FLAT_GED_cache_*`). Shadow models live under `output/debug/`.
- Do NOT change column names anywhere in the pipeline.
- Do NOT remove or rewrite existing reason / exclusion code in step 8B.7. The step is an audit, not a refactor.

### Trust-but-verify (carried forward from Phase 8)

Across Phase 8, three Claude Code execution reports carried inaccuracies that mattered (silent KPI break, missing constant bump, missing section append). The pattern that catches these reliably:

- After any Claude Code-generated step, **read the actual file with the Read tool** before propagating into context. Spot-check version constants, section headers, key names, and line counts. Bash grep / wc on the cross-mount lies — Read does not.
- For any execution report claiming "§N appended" or "FOO = bar bumped", do a 1-second Read to verify before flipping status to ✅.
- Treat sandbox pytest hangs as inconclusive (H-4), not failures. Confirm via direct `python -c` invocation, then defer pytest to Windows shell.

---

## 5. Event Taxonomy

Every step in Phase 8B operates on the same event model. Both RAW and FLAT events flatten to:

```
Event = (
    source_file,           # e.g. "GED_export.xlsx" or "FLAT_GED.xlsx"
    source_sheet,          # e.g. "Doc. sous workflow, x versions" or "GED_RAW_FLAT"
    source_excel_row,      # 1-indexed Excel row reference for traceability
    numero,
    indice,
    cycle_id,              # e.g. "C1" / "C2" for SAS; or step_order for FLAT
    actor_raw,             # e.g. "0-SAS" / "GEMO" / "AUDISOL"
    actor_canonical,       # mapped via CANONICAL_TO_DISPLAY
    event_type,            # one of: DOCUMENT_VERSION, ACTOR_CALLED, RESPONSE,
                           #         COMMENT, DATE, DEADLINE
    status_raw,            # raw cell value, e.g. "VSO-SAS" / "REF" / "VAO"
    status_clean,          # normalised label, e.g. "VSO" / "REF" / "VAO"
    response_date,
    submission_date,
    deadline_date,
    comment_raw,
)
```

The RAW extractor (8B.1) emits `Event` rows directly from `input/GED_export.xlsx`. The FLAT extractor (8B.2) emits `Event` rows from `output/intermediate/FLAT_GED.xlsx`. Steps 8B.3 through 8B.6 pair up these two row sets and decompose every difference.

### Allowed explanation taxonomy (used in steps 8B.4, 8B.5, 8B.6)

When a RAW event has no direct FLAT counterpart, it must be classified as one of:

```
ACTIVE_VERSION_PROJECTION  RAW carries old indices; FLAT keeps only the active (numero, indice).
DUPLICATE_MERGED            Multiple RAW rows collapsed into one FLAT row.
OLD_CYCLE_SUPERSEDED        RAW cycle 1 superseded by cycle 2; FLAT keeps only the live cycle.
SAS_CYCLE_COLLAPSED         RAW SAS C1 + C2 collapsed into a single FLAT SAS step.
EXCEPTION_COLUMN            RAW row from a column / sheet excluded by design.
NON_OPERATIONAL_RESPONSE    RAW row not part of the operational workflow (e.g. informational).
MALFORMED_RESPONSE          RAW row malformed; deliberately dropped during normalisation.
UNKNOWN_ACTOR               RAW actor name not in canonical map; dropped or quarantined.
UNEXPLAINED                 The trace cannot classify this row. TARGET = 0.
```

`UNEXPLAINED == 0` is the precondition for closing Phase 8B (per §16).

### Layer reference (carried from Phase 8 §4)

```
L0_RAW_GED              input/GED_export.xlsx                                    (ground truth)
L1_FLAT_GED_XLSX        output/intermediate/FLAT_GED.xlsx                         (Phase 8B focus)
L2_STAGE_READ_FLAT      src/pipeline/stages/stage_read_flat.py output             (downstream — Phase 8 closed)
L3_RUNCONTEXT_CACHE     output/intermediate/FLAT_GED_cache_*                      (Phase 8 closed)
L4_AGGREGATOR           src/reporting/aggregator.py                               (Phase 8 closed)
L5_UI_ADAPTER           src/reporting/ui_adapter.py                               (Phase 8 closed)
```

Phase 8B operates on the **L0 → L1 boundary**. Steps 8B.1 / 8B.2 extract L0 and L1 to a common event model; steps 8B.3 through 8B.6 trace the projection.

---

## 6. What Must Be Equal (the contract)

### Must equal exactly (BLOCKER on failure)

```
RAW unique numero                    =  FLAT unique numero
RAW unique numero+indice              =  FLAT OPEN_DOC count (= active version count in GED_OPERATIONS)
RAW document version set              =  FLAT document version set
```

Current expected values (carry from Phase 8):

```
RAW unique numero          = 2819
FLAT unique numero         = 2819
RAW unique numero+indice   = 4848
FLAT OPEN_DOC              = 4848
```

If 8B.3 surfaces any deviation here, STOP — it is a true bug or a stale extraction, not a rule.

### Must equal by trace (not necessarily direct row count)

```
RAW actor calls          =  FLAT actor calls   + explained transformations
RAW responses            =  FLAT responses     + explained transformations
RAW dates / comments     =  FLAT dates/comments + explained transformations
RAW SAS REF              =  FLAT SAS REF       + explained transformations
```

Differences here are accepted only if every leftover row falls into the explanation taxonomy from §5.

### Must NOT be blindly equal

```
RAW row count            ≠  FLAT row count   (RAW is one-row-per-submission, FLAT is one-row-per-step)
RAW submission rows      ≠  FLAT workflow rows
RAW SAS REF              ≠  UI SAS REF       (UI may merge REF + SAS_REF into one bucket)
```

The contract is event-level and trace-based, not row-count-based.

---

## 7. Initial Expected Checks

These values are the baseline at phase open (carried from Phase 8 §4 + closure):

```
RAW submission rows                = 6901
RAW unique numero                  = 2819
RAW unique numero+indice           = 4848
RAW SAS REF                        = 836 + 1 (cycle 1 + cycle 2; OR-distinct = 836 unique pairs)

FLAT GED_RAW_FLAT rows             = 27261
FLAT GED_OPERATIONS rows           = 32099
FLAT OPEN_DOC (= step_type count)  = 4848
FLAT SAS (= step_type count)       = 4848
FLAT CONSULTANT (= step_type count)= 18911
FLAT MOEX (= step_type count)      = 3492
FLAT SAS REF (is_sas=True AND
              status_clean="REF")  = 284

RunContext docs_df rows            = 4834   (= 4848 − 14 SAS pre-2026 filtered)
```

### Headline open issue

```
D-011: RAW SAS REF (836 distinct pairs) vs FLAT SAS REF (284) — 552-row gap
```

The §11 step (8B.5) decomposes this into the explanation taxonomy.

---

## 8. Step 8B.1 — RAW GED Event Extraction (LOW risk)

### 8.1 Why this comes first

The trace requires both sides expressed in the same event shape. RAW comes first because it is the ground truth — every later step references it.

### 8.2 Files

```
READ:
  input/GED_export.xlsx                                    (sheet: "Doc. sous workflow, x versions")
  src/normalize.py                                          (READ ONLY — for the canonical actor map; do NOT call it from the script)
  src/flat_ged/input/source_main/consultant_mapping.py      (READ ONLY — CANONICAL_TO_DISPLAY)

CREATE:
  scripts/extract_raw_ged_trace.py
  output/debug/raw_ged_trace.csv

DO NOT TOUCH:
  src/flat_ged/*
  src/reporting/*
  src/workflow_engine.py
  src/effective_responses.py
  data/*.db
  runs/*
  ui/jansa/*
  output/intermediate/FLAT_GED*           (this step does not touch the FLAT side)
```

### 8.3 What `scripts/extract_raw_ged_trace.py` must do

1. Open `input/GED_export.xlsx`, sheet `Doc. sous workflow, x versions`.
2. Read row 1 (top-level approver names) and row 2 (sub-column labels: Date réponse / Réponse / Commentaire / PJ).
3. Iterate data rows (Excel rows 3..6903 today; verify `ws.max_row` and use the actual range).
4. For each data row, emit one or more `Event` records:
   - One `DOCUMENT_VERSION` event per (numero, indice) carrying submission_date, raw_document_title, raw_emetteur, raw_lot.
   - For each approver block in row 1 that is non-empty for this row: emit `ACTOR_CALLED` + (if response present) `RESPONSE` + (if comment present) `COMMENT` + (if dates present) `DATE` / `DEADLINE`.
   - For multi-cycle approvers (notably `0-SAS` with two response blocks), emit one event per cycle with `cycle_id = "C1"`, `"C2"`.
5. Resolve `actor_canonical` from `actor_raw` via the canonical map.
6. Compute `status_clean` from `status_raw` using the same normalisation `src/normalize.py` applies (read it; DO NOT IMPORT — re-implement the small deterministic mapping inside the script so the trace is independent of the production normalize step).
7. Write `output/debug/raw_ged_trace.csv` with the column set declared in §5.

### 8.4 Validation

```
python -m py_compile scripts/extract_raw_ged_trace.py
python scripts/extract_raw_ged_trace.py
# Confirm:
#   output/debug/raw_ged_trace.csv exists
#   row count > 0
#   summary stdout line:
#     RAW_TRACE: rows=<n> unique_numero=2819 unique_numero_indice=4848 sas_ref_pairs=836
```

If `unique_numero != 2819` or `unique_numero_indice != 4848`, STOP and report — likely the extractor is mis-counting (header off-by-one, multi-cycle double-count, etc.). Do not adjust the baseline.

### 8.5 Risk: **Low**.

---

## 9. Step 8B.2 — FLAT GED Event Extraction (LOW risk)

### 9.1 Why

Mirror of 8B.1 against the FLAT side, in the same event shape. After this step, both sides are comparable row-by-row at the event level.

### 9.2 Files

```
READ:
  output/intermediate/FLAT_GED.xlsx     (sheets: GED_RAW_FLAT, GED_OPERATIONS)
  src/flat_ged/input/source_main/consultant_mapping.py      (READ ONLY)

CREATE:
  scripts/extract_flat_ged_trace.py
  output/debug/flat_ged_trace.csv
  output/debug/flat_ged_trace.xlsx

DO NOT TOUCH: same list as 8B.1.
```

### 9.3 What the script must do

1. Open `output/intermediate/FLAT_GED.xlsx`.
2. Read both sheets fully:
   - `GED_RAW_FLAT` (~27261 rows): one row per (doc, approver, step). Emit one `RESPONSE` or `ACTOR_CALLED` event per row, depending on whether `response_status_clean` is populated.
   - `GED_OPERATIONS` (~32099 rows): one row per workflow step. Emit `ACTOR_CALLED` + (if response present) `RESPONSE` + (if dates present) `DATE`.
3. Compute `submission_instance_id = (numero, indice)`.
4. For each event, populate flags from the FLAT sheet columns: `is_sas`, `is_moex`, `is_consultant` (read from `step_type` if present, else from `actor_raw`).
5. Write `output/debug/flat_ged_trace.{csv,xlsx}` with the column set in the charter (§9.2 in this doc carries the user's spec).

### 9.4 Validation

```
python -m py_compile scripts/extract_flat_ged_trace.py
python scripts/extract_flat_ged_trace.py
# Confirm:
#   output/debug/flat_ged_trace.{csv,xlsx} exist
#   summary stdout line:
#     FLAT_TRACE: rows=<n> unique_numero=2819 unique_numero_indice=4848 \
#                 step_OPEN_DOC=4848 step_SAS=4848 step_CONSULTANT=18911 step_MOEX=3492 \
#                 sas_ref_rows=284
```

If counts deviate from the §7 baselines, STOP and report.

### 9.5 Risk: **Low**.

---

## 10. Step 8B.3 — Base Identity Parity (LOW risk; BLOCKER on failure)

### 10.1 Goal

Prove the identity contract from §6: RAW and FLAT cover the same set of (numero) and the same set of (numero, indice). This is the foundation; if it fails, every later step is moot.

### 10.2 Files

```
READ:
  output/debug/raw_ged_trace.csv
  output/debug/flat_ged_trace.csv

CREATE / EXTEND:
  scripts/raw_flat_reconcile.py        (NEW driver script, reused by 8B.3 through 8B.9)
  output/debug/raw_flat_reconcile.xlsx (sheet 01_IDENTITY_PARITY appended/created)
```

### 10.3 What the script must do (8B.3 portion)

1. Load both traces as pandas DataFrames.
2. Compute `raw_numero_set = set(raw["numero"])` and same for FLAT; same for `(numero, indice)` pairs.
3. Compare:
   - `missing_in_flat = raw_numero_set − flat_numero_set`
   - `extra_in_flat = flat_numero_set − raw_numero_set`
   - Same for `(numero, indice)` pairs.
4. Write sheet `01_IDENTITY_PARITY` with columns:
   `set_name`, `raw_count`, `flat_count`, `missing_in_flat_count`, `extra_in_flat_count`, `verdict` (`PASS` / `BLOCKER`).
5. Print stdout summary:
   ```
   IDENTITY_PARITY: numero PASS/BLOCKER, numero_indice PASS/BLOCKER, missing=<n>, extra=<n>
   ```

### 10.4 Failure rule

```
Any missing RAW numero+indice in FLAT  =  BLOCKER (stop the phase, escalate)
Any extra FLAT numero+indice not in RAW =  BLOCKER (stop the phase, escalate)
```

If 8B.3 BLOCKs, do NOT proceed to 8B.4. Treat it as a true bug or extractor error and report.

### 10.5 Validation

```
python -m py_compile scripts/raw_flat_reconcile.py
python scripts/raw_flat_reconcile.py --step identity
# Expected: IDENTITY_PARITY: numero PASS, numero_indice PASS, missing=0, extra=0
```

### 10.6 Risk: **Low** for the audit; **HIGH** as a signal if BLOCKER fires.

---

## 11. Step 8B.4 — Actor Call Parity (LOW risk)

### 11.1 Goal

Verify every actor call in RAW has a counterpart in FLAT, or a documented explanation. Compare totals AND per-document-version sets.

### 11.2 What the script must do (8B.4 portion)

1. From RAW trace: build set `(numero, indice, actor_canonical, cycle_id_or_call_slot)`.
2. From FLAT trace: build set `(numero, indice, actor_clean, step_type)`.
3. Map cycle_id (RAW) ↔ step_type (FLAT) where the mapping is obvious (e.g. `0-SAS C1` → `step_type=SAS`).
4. Compute per-version diffs:
   - actors_raw_only: RAW actors missing from FLAT for this version.
   - actors_flat_only: FLAT actors missing from RAW for this version.
   - actors_match: present in both.
5. Aggregate into:
   - **Sheet `02_ACTOR_CALL_COUNTS`**: per-actor totals on each side (raw_count, flat_count, delta, expected_explanation_category).
   - **Sheet `03_ACTOR_CALL_DIFFS`**: per-version diffs where `actors_raw_only ≠ ∅` or `actors_flat_only ≠ ∅`.
6. For each diff row, attempt classification using the §5 taxonomy. Rows the script cannot classify automatically remain `UNEXPLAINED` and become Phase 8B work to investigate manually.

### 11.3 Compared categories

```
Global actor call counts             (totals)
Actor call counts by numero+indice   (per-version detail)
Actor call sets per document version (set-equality)
SAS call count
MOEX call count
Consultant call count
```

The user's charter explicitly says: *do not only compare totals; also compare per document version.*

### 11.4 Validation

```
python scripts/raw_flat_reconcile.py --step actor_calls
# Expected: ACTOR_CALL_PARITY: total_diffs=<n> unexplained=<n>
```

A non-zero `unexplained` is allowed at the script level; the goal of Phase 8B is to drive it to zero by manual investigation + extending the explanation taxonomy where genuinely new categories surface.

### 11.5 Risk: **Low** (audit-only).

---

## 12. Step 8B.5 — Response / Status Parity, including D-011 SAS REF Trace (LOW risk; HIGH-VALUE)

### 12.1 Goal

Decompose the headline gap: RAW 836 SAS REF unique pairs vs FLAT 284. Every missing pair must land in one of the §5 taxonomy buckets.

### 12.2 What the script must do

1. From RAW trace: `raw_responses = (numero, indice, actor_canonical, cycle_id, status_clean)`.
2. From FLAT trace: `flat_responses = (numero, indice, actor_clean, step_type, status_clean)`.
3. Join by `(numero, indice, actor_canonical=actor_clean)` first; for SAS, also pivot cycle_id ↔ step_type.
4. For each RAW response with no FLAT counterpart, attempt classification:
   - Same `(numero, indice)` exists in FLAT but with a different `actor` → likely `EXCEPTION_COLUMN` or `UNKNOWN_ACTOR`.
   - Old indice for the same numero → `ACTIVE_VERSION_PROJECTION`.
   - SAS C1 + SAS C2 both REF → `SAS_CYCLE_COLLAPSED` (FLAT keeps the latest decision).
   - Multiple RAW rows for one `(numero, indice, actor)` → `DUPLICATE_MERGED`.
   - Status_raw not in the operational set → `NON_OPERATIONAL_RESPONSE` or `MALFORMED_RESPONSE`.
   - None of the above → `UNEXPLAINED`.
5. Output sheets:
   - **`04_RESPONSE_COUNTS_BY_STATUS`**: status × side × count.
   - **`05_RESPONSE_COUNTS_BY_ACTOR`**: actor × status × side × count.
   - **`06_RESPONSE_DIFFS`**: per-row diffs with attempted classification.
   - **`07_SAS_REF_TRACE`**: focused trace of the 836 → 284 gap. One row per RAW SAS REF pair, columns: numero, indice, actor=0-SAS, raw_cycle, status_raw, status_clean, flat_present (bool), flat_status_clean (if present), classification (one of the §5 categories), evidence_excel_row.

### 12.3 Targets

```
UNEXPLAINED SAS REF rows = 0
UNEXPLAINED all response rows = 0
```

If `UNEXPLAINED > 0` after the automatic classifier, the residual rows go into the §15 decision gate. The phase does NOT close until the residual is zero — either by manual classification, taxonomy extension, or a documented intentional drop.

### 12.4 Validation

```
python scripts/raw_flat_reconcile.py --step responses
# Expected stdout:
#   RESPONSE_PARITY: total_raw=<n> total_flat=<n> matched=<n>
#   SAS_REF_TRACE: raw=836 flat=284 classified=<n> unexplained=<n>
```

### 12.5 Risk: **Low** (audit-only). The output drives the §15 decision.

---

## 13. Step 8B.6 — Date / Comment Parity (LOW risk)

### 13.1 Goal

Verify no important information was lost in the L0 → L1 transition.

### 13.2 What the script must do

For every matched event from §12 (the diagonal of the response join), compare:
```
submission_date     RAW vs FLAT
response_date       RAW vs FLAT
deadline_date       RAW vs FLAT
comment_raw         RAW vs FLAT (called "observation" in FLAT)
```

### 13.3 Rules

```
Date format normalization allowed.        (e.g. "10/04/2026" ↔ "2026-04-10")
Date value drift not allowed unless explained.
Blank RAW → blank FLAT allowed.
Nonblank RAW → blank FLAT must be explained.
```

### 13.4 Output sheets

```
08_DATE_DIFFS      (one row per (numero, indice, actor, date_field) where values differ)
09_COMMENT_DIFFS   (one row per (numero, indice, actor) where comment_raw was non-empty but the FLAT observation is empty or different)
```

### 13.5 Validation

```
python scripts/raw_flat_reconcile.py --step dates_comments
# Expected stdout:
#   DATE_PARITY: matched=<n> drifted=<n> raw_blank_flat_blank=<n> raw_nonblank_flat_blank=<n>
#   COMMENT_PARITY: matched=<n> raw_only=<n> flat_only=<n>
```

A non-zero `raw_nonblank_flat_blank` is the load-bearing signal — those are events where information appears to be lost. Each must be explained or taxonomied.

### 13.6 Risk: **Low**.

---

## 14. Step 8B.7 — Existing Reason / Exclusion Logic Audit (LOW risk; READ-ONLY)

### 14.1 Goal

Audit the existing exclusion / reason / "skipped" code in `src/flat_ged/*` **without changing it**. Classify every existing reason by quality.

### 14.2 What the script (or this step's narrative report) must do

1. Walk `src/flat_ged/*` and identify every place a row is dropped or annotated with a reason / exclusion code. Common locations to expect (verify by reading):
   - `src/flat_ged/transformer.py`
   - `src/flat_ged/reader.py`
   - `src/flat_ged/validator.py`
   - `src/flat_ged/utils.py`
2. For each reason, classify as:
   ```
   VALID_REASON       Documented, traceable, makes sense in the trace model.
   INVALID_REASON     Reason does not match what the code actually does.
   MISSING_REASON     Drop happens with no reason recorded.
   AMBIGUOUS_REASON   Reason exists but its meaning is unclear or covers too many cases.
   ```
3. Output sheet `10_EXISTING_REASON_AUDIT` with columns: `file`, `function`, `line`, `reason_string` (verbatim), `classification`, `notes`.

### 14.3 Important

```
Do NOT remove reason code in this step.
Do NOT modify src/flat_ged/* in this step.
The audit is READ-ONLY.
```

Decisions about removing or replacing reason code happen at the §15 gate.

### 14.4 Validation

```
# This step is mostly narrative. Mechanical validation:
python -c "import pandas as pd; df = pd.read_excel('output/debug/raw_flat_reconcile.xlsx', sheet_name='10_EXISTING_REASON_AUDIT'); print('reason audit rows:', len(df))"
```

### 14.5 Risk: **Low**.

---

## 15. Step 8B.8 — Report Integration Trace (LOW audit; potentially MEDIUM at gate)

### 15.1 Goal

Record how reports (consultant report ingest) would attach at the FLAT level. Currently reports merge into responses downstream of FLAT via `effective_responses` (called from `data_loader._load_from_flat_artifacts`). The charter asks: should reports also be visible at the FLAT level, with explicit confidence and provenance?

### 15.2 Files

```
READ:
  src/effective_responses.py            (READ ONLY — current merge contract)
  src/report_memory.py                  (READ ONLY — report ingest model)
  data/report_memory.db                 (READ ONLY — current report data)
  output/debug/flat_ged_trace.csv       (from 8B.2)

CREATE:
  scripts/report_to_flat_trace.py
  output/debug/report_to_flat_trace.xlsx
  output/debug/report_to_flat_trace.json
```

### 15.3 What the script must do

For every persisted report response in `data/report_memory.db`:

1. Resolve `report_doc_key = (numero, indice)`.
2. Resolve `report_actor` (canonical).
3. Read `report_status` (e.g. VAO / REF / VSO).
4. Read `report_comment`.
5. Read `report_confidence` (HIGH / MEDIUM / LOW / UNKNOWN).
6. Compute `report_match_type`:
   - `EXACT` — exact (numero, indice, actor) match in FLAT.
   - `FAMILY` — matched on numero only (different indice).
   - `FUZZY` — matched via the consultant_matcher fuzzy path.
   - `NO_MATCH` — no FLAT counterpart.
7. Compute `report_applied`:
   - `APPLIED_AS_PRIMARY` — report supplied the answer, GED was empty.
   - `APPLIED_AS_ENRICHMENT` — report added comment / date / detail to a GED answer.
   - `BLOCKED_BY_GED` — GED already had a high-confidence answer; report ignored.
   - `BLOCKED_BY_CONFIDENCE` — report below the E2 confidence gate (LOW/UNKNOWN).
   - `NOT_APPLIED` — no merge happened.
8. Compute `effective_status` and `effective_source` per the existing `effective_responses` rules:
   ```
   GED answered beats low-confidence report.
   High-confidence report may enrich pending GED.
   Report-only answer must be visible as report-only trace.
   No silent overwrite.
   ```

### 15.4 Output shape

`output/debug/report_to_flat_trace.json`:
```
{
  "generated_at": "<iso>",
  "report_count": <int>,
  "match_type_counts":     {"EXACT": <n>, "FAMILY": <n>, ...},
  "applied_counts":        {"APPLIED_AS_PRIMARY": <n>, ...},
  "by_doc": [
    {
      "report_source_file": "<path>",
      "report_doc_key": "<numero>|<indice>",
      "report_actor": "<canonical>",
      "report_status": "<VAO|REF|...>",
      "report_comment": "<...>",
      "report_confidence": "<HIGH|MEDIUM|LOW|UNKNOWN>",
      "report_match_type": "<EXACT|FAMILY|FUZZY|NO_MATCH>",
      "report_applied": "<APPLIED_AS_PRIMARY|...>",
      "effective_status": "<final status>",
      "effective_source": "<GED|REPORT|GED+REPORT>"
    },
    ...
  ]
}
```

### 15.5 Open question for the §17 gate

Do reports belong at the FLAT level (extending `FLAT_GED.xlsx` schema) or do they stay where they are (downstream merge in `effective_responses`)? This step produces the trace; the gate decides.

### 15.6 Validation

```
python scripts/report_to_flat_trace.py
# Expected: report_count > 0; match_type and applied breakdowns logged to stdout.
```

### 15.7 Risk: **Low** (audit-only). **Medium** at the gate if a FLAT schema extension is approved.

---

## 16. Step 8B.9 — Shadow Corrected FLAT Model (LOW risk)

### 16.1 Goal

Before proposing any modification to `src/flat_ged/transformer.py`, generate a **shadow** FLAT artifact that shows what FLAT would look like if the trace gaps from steps 8B.4–8B.6 were corrected. The shadow lives entirely under `output/debug/`. It is never read by production code.

### 16.2 Files

```
READ:
  output/debug/raw_ged_trace.csv
  output/debug/flat_ged_trace.csv
  output/debug/raw_flat_reconcile.xlsx   (sheets 01..10)
  output/debug/report_to_flat_trace.json (from 8B.8 if applicable)

CREATE:
  scripts/build_shadow_flat_ged.py
  output/debug/SHADOW_FLAT_GED_TRACE.xlsx
  output/debug/SHADOW_FLAT_GED_OPERATIONS.csv
```

### 16.3 What the script must do

1. Start from `raw_ged_trace.csv` (the ground-truth event set).
2. Apply each documented projection rule from the §5 taxonomy:
   - Drop OLD_CYCLE_SUPERSEDED rows where the cycle is superseded.
   - Collapse SAS_CYCLE_COLLAPSED pairs into a single step row.
   - Drop EXCEPTION_COLUMN rows.
   - Drop NON_OPERATIONAL_RESPONSE rows.
   - …
3. The set of applied rules MUST match the explanation taxonomy from §5. Any rule applied here must already be documented in the audit sheets `02..09`.
4. Emit `SHADOW_FLAT_GED_OPERATIONS.csv` with the same column shape as production `GED_OPERATIONS`.
5. Emit `SHADOW_FLAT_GED_TRACE.xlsx` with one sheet per rule application showing what changed.

### 16.4 Output sheet (in `raw_flat_reconcile.xlsx`)

`11_SHADOW_DIFFS` — for every doc-version, what differs between current FLAT and shadow FLAT.

### 16.5 The shadow is NOT production

```
output/debug/SHADOW_*  is debug-only.
output/intermediate/FLAT_GED.xlsx is unchanged.
src/flat_ged/* is unchanged.
```

### 16.6 Validation

```
python scripts/build_shadow_flat_ged.py
python scripts/raw_flat_reconcile.py --step shadow
# Expected: SHADOW_DIFFS rows ≥ 0; UNEXPLAINED in shadow = 0.
```

### 16.7 Risk: **Low**.

---

## 17. Step 8B.10 — Decision Gate (CHECKPOINT — not a code step)

### 17.1 The gate

After steps 8B.1 through 8B.9 land and `UNEXPLAINED == 0` is achieved, evaluate one of four outcomes:

```
A. UNEXPLAINED = 0; current FLAT builder is correct in substance.
   → Keep current builder.
   → Document the projection rules from the trace as the canonical contract
     (extend src/flat_ged/BUILD_SOURCE.md or an equivalent contract file).
   → Phase 8B closes here.

B. UNEXPLAINED = 0 only after applying a documented set of rules to the
   shadow model that the production builder does NOT currently apply.
   → Propose a controlled patch to src/flat_ged/transformer.py implementing
     exactly those rules. HIGH risk. Written approval required.
   → New phase (8B-PATCH) opens with its own self-contained plan doc.

C. The reason / exclusion logic in src/flat_ged/* turned out wrong (per
   the §14 audit — INVALID_REASON or AMBIGUOUS_REASON entries).
   → Propose replacing the affected reason logic.
   → Treated as a focused sub-phase, MEDIUM-HIGH risk.

D. The report-integration trace shows reports SHOULD appear at the FLAT
   level (not just downstream).
   → Propose a FLAT schema extension. HIGH risk; affects every FLAT
     consumer. New phase (8B-REPORT-SCHEMA) opens.
```

### 17.2 No production patch before this gate

```
Steps 8B.1 through 8B.9 ship NO src/* changes.
Step 8B.10 is a decision, not a code change.
Any code that follows the gate runs as a separate phase with its own plan doc.
```

### 17.3 Final report

The phase closes with a written final report (likely §13 or §14 inside this doc, appended after step execution) answering:

```
Why does RAW GED have X and FLAT GED have Y?
Which rows were merged?
Which rows were excluded?
Which rows are old cycles?
Which rows are report-only?
Which rows are true bugs?
What must be changed, if anything?
```

---

## 18. Files To Create

```
docs/implementation/PHASE_8B_RAW_TO_FLAT_RECONCILIATION.md   (this file — already created)

scripts/extract_raw_ged_trace.py                              (8B.1)
scripts/extract_flat_ged_trace.py                             (8B.2)
scripts/raw_flat_reconcile.py                                 (8B.3 through 8B.6, 8B.9)
scripts/report_to_flat_trace.py                               (8B.8)
scripts/build_shadow_flat_ged.py                              (8B.9)

output/debug/raw_ged_trace.csv                                (8B.1)
output/debug/flat_ged_trace.csv                               (8B.2)
output/debug/flat_ged_trace.xlsx                              (8B.2)
output/debug/raw_flat_reconcile.xlsx                          (8B.3 through 8B.7, 8B.9 — sheets 01..11)
output/debug/report_to_flat_trace.xlsx                        (8B.8)
output/debug/report_to_flat_trace.json                        (8B.8)
output/debug/SHADOW_FLAT_GED_TRACE.xlsx                       (8B.9)
output/debug/SHADOW_FLAT_GED_OPERATIONS.csv                   (8B.9)

tests/test_extract_raw_ged_trace.py                           (8B.1)
tests/test_extract_flat_ged_trace.py                          (8B.2)
tests/test_raw_flat_reconcile.py                              (8B.3 through 8B.7, 8B.9)
tests/test_report_to_flat_trace.py                            (8B.8)
tests/test_build_shadow_flat_ged.py                           (8B.9)
```

## 19. Files To Modify (only after the §17 gate, with written approval)

Possibilities, ordered by likelihood:

```
src/flat_ged/transformer.py     (if outcome B)
src/flat_ged/validator.py       (if outcome B or C)
src/flat_ged/reader.py          (rare; only if outcome B requires it)
src/flat_ged/BUILD_SOURCE.md    (outcome A — document existing rules)
src/flat_ged/CONTRACT.md / docs/FLAT_GED_CONTRACT.md   (outcome D — schema extension)
```

No file under `src/` is touched in steps 8B.1 through 8B.9.

## 20. Files NEVER To Touch In This Phase (steps 8B.1 through 8B.9)

```
src/flat_ged/*                       (until §17 gate, with approval)
src/reporting/data_loader.py
src/reporting/aggregator.py
src/reporting/ui_adapter.py
src/workflow_engine.py
src/effective_responses.py
src/run_memory.py
src/report_memory.py
src/team_version_builder.py
src/pipeline/*
data/*.db                            (READ ONLY)
runs/*
ui/jansa/*
ui/jansa-connected.html
app.py
main.py
run_chain_onion.py
output/intermediate/FLAT_GED*        (production FLAT — never overwritten by this phase)
context/*.md                         (project owner updates these in chat)
README.md                            (same)
docs/implementation/PHASE_8_COUNT_LINEAGE_FIX.md   (closed; reference only)
```

---

## 21. Combined Validation Commands

Each step is independently validatable. Listed in execution order.

```
# 8B.1
python -m py_compile scripts/extract_raw_ged_trace.py
python scripts/extract_raw_ged_trace.py
# Expect: RAW_TRACE: rows=<n> unique_numero=2819 unique_numero_indice=4848 sas_ref_pairs=836

# 8B.2
python -m py_compile scripts/extract_flat_ged_trace.py
python scripts/extract_flat_ged_trace.py
# Expect: FLAT_TRACE: rows=<n> unique_numero=2819 unique_numero_indice=4848 \
#                    step_OPEN_DOC=4848 step_SAS=4848 step_CONSULTANT=18911 step_MOEX=3492 \
#                    sas_ref_rows=284

# 8B.3
python -m py_compile scripts/raw_flat_reconcile.py
python scripts/raw_flat_reconcile.py --step identity
# Expect: IDENTITY_PARITY: numero PASS, numero_indice PASS, missing=0, extra=0

# 8B.4
python scripts/raw_flat_reconcile.py --step actor_calls

# 8B.5 (D-011 trace)
python scripts/raw_flat_reconcile.py --step responses
# Expect: SAS_REF_TRACE: raw=836 flat=284 classified=<n> unexplained=<n>

# 8B.6
python scripts/raw_flat_reconcile.py --step dates_comments

# 8B.7
python scripts/raw_flat_reconcile.py --step reasons_audit
# (Or narrative — see step 14.)

# 8B.8
python -m py_compile scripts/report_to_flat_trace.py
python scripts/report_to_flat_trace.py

# 8B.9
python -m py_compile scripts/build_shadow_flat_ged.py
python scripts/build_shadow_flat_ged.py
python scripts/raw_flat_reconcile.py --step shadow

# Cross-cut: ensure Phase 8 audit still passes throughout.
python scripts/audit_counts_lineage.py
# Expect (unchanged from Phase 8 closure):
#   AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
#   UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match
```

H-5 reminder: bulk xlsx I/O may time out in sandbox. Defer end-to-end runs to Windows shell. Sandbox can validate script logic, small-sample runs, and read of already-produced traces.

---

## 22. Final Cowork Prompt (for handing this phase to a fresh agent)

```
Objective:
  Trace every RAW GED event into FLAT GED — prove every row has a named
  destination or a named reason for absence. Produce the explanation
  decomposition for D-011 (RAW SAS REF 836 vs FLAT SAS REF 284). No
  production code change before the §17 gate.

Plan: docs/implementation/PHASE_8B_RAW_TO_FLAT_RECONCILIATION.md (self-contained).

Hard constraints:
  - Steps 8B.1 through 8B.9 ship NO production source change.
  - src/flat_ged/* is the do-not-touch list until the §17 decision gate.
  - Trust-but-verify on every Claude Code execution report (read the file,
    check version constants, headers, key names).

Tasks (one self-contained Claude Code prompt per step):
  8B.1  RAW event extraction      → output/debug/raw_ged_trace.csv
  8B.2  FLAT event extraction     → output/debug/flat_ged_trace.{csv,xlsx}
  8B.3  Identity parity           → sheet 01_IDENTITY_PARITY (BLOCKER on fail)
  8B.4  Actor call parity         → sheets 02 + 03
  8B.5  Response/status parity    → sheets 04..07; D-011 trace target
  8B.6  Date/comment parity       → sheets 08 + 09
  8B.7  Existing reason audit     → sheet 10 (READ-ONLY)
  8B.8  Report integration trace  → output/debug/report_to_flat_trace.{xlsx,json}
  8B.9  Shadow corrected FLAT     → output/debug/SHADOW_FLAT_GED_*
  8B.10 Decision gate             → checkpoint, not a code step

Final acceptance:
  RAW unique docs == FLAT unique docs   (BLOCKER if not)
  UNEXPLAINED == 0
  D-011 explained
  Report integration path defined
  Shadow model generated if needed
  Production patch plan approved or explicitly rejected

Validation per step: see §21 of the plan doc.

Return per step:
  1. Files created (paths + line counts)
  2. Validation results (verbatim)
  3. Stdout summary line(s)
  4. Sheet sizes if xlsx written
  5. UNEXPLAINED counts where applicable
  6. Proposed §-report content for the project owner to verify before context updates
```

---

## 23. Open Questions

These need answers before steps 8B.1 / 8B.2 actually run. The plan doc captures them; the answers come either from inspection during the first step or from the project owner.

1. **Multi-cycle SAS rows in RAW.** RAW has two `0-SAS` response blocks in `Doc. sous workflow, x versions` (cycle 1 + cycle 2). Cycle 1 had 836 REF responses; cycle 2 had 1 REF, on the same physical row that already had a cycle-1 REF (per Phase 8 §22's `OR-distinct = 836` finding). Confirmation needed: does FLAT collapse cycle 2 into cycle 1 by design, or is cycle 2 lost? §11 (8B.4) and §12 (8B.5) should surface this on first run.

2. **Cycle ID representation in FLAT.** Does FLAT preserve a cycle index anywhere (e.g. `step_order`)? If yes, the §11 mapping from `cycle_id` to `step_type` is mechanical. If no, every multi-cycle RAW pair becomes a `SAS_CYCLE_COLLAPSED` candidate and we need to verify FLAT keeps the *latest* decision, not the first.

3. **`actor_canonical` map source.** `src/normalize.py` has a normalisation that the production pipeline uses; `consultant_mapping.py` has `CANONICAL_TO_DISPLAY`. Are they consistent? The trace scripts must use exactly one canonical map; we don't want the trace to claim a divergence that's actually a map mismatch.

4. **`status_clean` normalisation.** Same question as #3 for status labels. The 8B.1 script should re-implement the small deterministic mapping inside the script (per §8.3 step 6) rather than importing production normalize, so the trace is independent. List the actual mapping used by reading `src/normalize.py` first.

5. **Report ingest scope.** §15 (8B.8) attaches reports at the FLAT level for the trace. Today, reports merge in `effective_responses` downstream of FLAT. The §17 gate decides whether to move them to FLAT. The trace itself should not assume the answer — it should record what each report would do under each placement option.

6. **Exception sheets in FLAT_GED.xlsx.** The plan §8 OPEN_DOC / SAS / CONSULTANT / MOEX values were treated as `step_type` aggregates inside `GED_OPERATIONS` during Phase 8 (no separate sheets exist). Confirm during 8B.2 that the 8B.4 / 8B.5 actor-call breakdown uses the same convention; do NOT re-introduce the "OPEN_DOC sheet" misconception.

7. **Performance.** Both extractors do bulk xlsx reads. RAW is ~6900 data rows × 350 columns; FLAT is 27261 + 32099 rows × ~30 columns. On Windows native both should finish in under a minute. In sandbox, expect H-5 timeouts — plan validation accordingly.

8. **Test discipline.** All test files listed in §18 are mock-friendly where possible; tests that genuinely need the live xlsx data should be marked `@pytest.mark.slow` or equivalent so the sandbox-side fast tests don't drag in H-4 hangs.
