# Flat GED Adapter Map

**Step:** 4 — Flat GED Mode (Feature Flag)  
**Plan version:** v2  
**Date:** 2026-04-23  
**Author:** Step 4 implementation  
**Depends on:** `docs/FLAT_GED_CONTRACT.md` (v1.0), `docs/BACKEND_SEMANTIC_CONTRACT.md`  
**Consumed by:** Step 5 (Parity Harness), Steps 8–11 (reconstruction and UI)

---

## 1. Purpose

This document records every legacy field → flat GED source → adapter transformation
implemented in `src/pipeline/stages/stage_read_flat.py`.

It also documents the status of the three VISA GLOBAL verification points required by
BACKEND_SEMANTIC_CONTRACT §4 Decision 5, and any KNOWN_GAP items that must be
resolved in later steps.

---

## 2. Semantic Mapping Table

| Legacy concept | Old source | Flat GED source | Adapter rule | Status |
|---|---|---|---|---|
| **Effective response** (`date_status_type = ANSWERED`) | `normalize_responses()` → `interpret_date_field()` on `response_date_raw` | `GED_OPERATIONS.is_completed = True` + `response_date` non-empty | Adapter sets `response_date_raw = pd.Timestamp(response_date)` so `interpret_date_field()` returns `ANSWERED` | ✅ CONFIRMED |
| **Blocking** (`date_status_type = PENDING_*`) | `date_status_type ∈ {PENDING_IN_DELAY, PENDING_LATE}` derived by `interpret_date_field()` | `GED_OPERATIONS.is_blocking = True` + `retard_avance_status` | Adapter sets `response_date_raw` to pending text based on `is_blocking` (not `is_completed == False`). Post-MOEX de-flagged rows (`is_blocking=False, is_completed=False`) become `NOT_CALLED`. | ✅ CONFIRMED |
| **PENDING_IN_DELAY** | "En attente" text in `response_date_raw` | `GED_OPERATIONS.is_blocking=True` AND `retard_avance_status ≠ RETARD` (for non-SAS); `date_status_type = PENDING_IN_DELAY` in GED_RAW_FLAT (for SAS) | `response_date_raw = "En attente visa (YYYY/MM/DD)"` | ✅ CONFIRMED |
| **PENDING_LATE / RAPPEL** | "Rappel" text in `response_date_raw` | `GED_OPERATIONS.is_blocking=True` AND `retard_avance_status = RETARD` (for non-SAS); `date_status_type = PENDING_LATE` in GED_RAW_FLAT (for SAS rows, Concept 7G proxy) | `response_date_raw = "Rappel : En attente visa (YYYY/MM/DD)"` | ✅ CONFIRMED (limited — see RAPPEL note) |
| **NOT_CALLED** (post-MOEX de-flagged) | `date_status_type = NOT_CALLED` via empty `response_date_raw` | `GED_OPERATIONS.is_blocking=False` AND `is_completed=False` | `response_date_raw = None` → `interpret_date_field` → `NOT_CALLED` | ✅ CONFIRMED |
| **Cycle closure** (`closure_mode`) | Implicit: derived at query time from `compute_visa_global_with_date()` + `compute_global_state()` | Derived from GED_OPERATIONS step states per doc | Explicit `closure_mode` computed per doc in `flat_ged_doc_meta`. Three states: `MOEX_VISA`, `ALL_RESPONDED_NO_MOEX`, `WAITING_RESPONSES`. | ✅ CONFIRMED |
| **VISA GLOBAL** | `WorkflowEngine.compute_visa_global_with_date()` | `GED_OPERATIONS` MOEX step (`step_type=MOEX`) | Pre-computed in `flat_ged_doc_meta["visa_global"]`. WorkflowEngine also runs on reconstructed responses_df; VP-1 gap noted below. | ⚠ VP-1 GAP |
| **SAS REF** | `moex.approver_raw == "0-SAS"` + `status == REF` in WorkflowEngine | SAS step (`step_type=SAS`) with `is_completed=True`, `status_clean=REF`, no MOEX row | Pre-computed in `flat_ged_doc_meta["visa_global"] = "SAS REF"`. WorkflowEngine cannot detect this path in flat mode (VP-1). | ⚠ KNOWN_GAP |
| **Responsible party** | `compute_responsible_party()` in `workflow_engine.py` (5 rules) | Synthesised from `GED_OPERATIONS.is_blocking`, `actor_clean`, `visa_global` | Pre-computed in `flat_ged_doc_meta["responsible_party"]` using the same 5-rule logic with `is_blocking` replacing `date_status_type ∈ PENDING_*` (Decision 2). | ✅ CONFIRMED |
| **SAS scope filter** (`_apply_sas_filter`) | `response_date_raw` containing "rappel" for `approver_raw=0-SAS` + `created_at < 2026` | `GED_RAW_FLAT.date_status_type = PENDING_LATE` for SAS row + `submittal_date < 2026` | Pre-filtered in adapter before docs_df/responses_df construction. `stage_normalize`'s `_apply_sas_filter` finds nothing to exclude (correct). | ✅ CONFIRMED |
| **SAS ABSENT (synthetic)** | No special handling — SAS was never called | `operation_rule_used` contains `SYNTHETIC_SAS`; `is_completed=True`, `response_date=submittal_date` | `response_date_raw = pd.Timestamp(submittal_date)` → `ANSWERED`. Synthetic flag preserved in `flat_step_type = "SAS"` pass-through column. | ✅ CONFIRMED |
| **Operational lateness** (`PENDING_LATE`) | `interpret_date_field()` on "Rappel" text; deadline from parenthesized date | `GED_OPERATIONS.retard_avance_status = RETARD`; `phase_deadline`; `data_date` | `retard_avance_status = RETARD` → PENDING_LATE text. `phase_deadline` embedded as `(YYYY/MM/DD)` in pending string so `normalize_responses` extracts `date_limite`. | ✅ CONFIRMED |
| **RAPPEL reminder-history** | First-class `RAPPEL` state in `_build_sas_lookup()` | No dedicated field in flat GED; proxy: `date_status_type = PENDING_LATE` in GED_RAW_FLAT | Proxy used (Concept 7G). Any GF column that specifically depends on the RAPPEL/non-RAPPEL distinction beyond scope filtering must be assessed per column in Step 8. | ⚠ LIMITED (see note) |
| **Delay fields** | Legacy: recomputed per step from raw dates | `GED_OPERATIONS`: `step_delay_days`, `delay_contribution_days`, `cumulative_delay_days`, `delay_actor` | Read directly. Pass-through in `responses_df` as `flat_step_delay_days`, `flat_delay_contribution_days`, `flat_cumulative_delay_days`, `flat_delay_actor`. Full `ops_df` in `ctx.flat_ged_ops_df`. | ✅ CONFIRMED |
| **data_date** (reference date) | `data_date` from `Détails!D15` (read in legacy by `read_raw`) | `GED_OPERATIONS.data_date` (read from `Détails!D15` by flat builder) | Stored in `docs_df["data_date"]` and `flat_ged_doc_meta[doc_id]["data_date"]`. `datetime.now()` is never used anywhere in this adapter. | ✅ CONFIRMED |
| **`is_dernier_indice` proxy** | `VersionEngine` — Jaccard + date lifecycle | `instance_role = ACTIVE` in flat GED (per Decision 1) | GED_OPERATIONS already contains only ACTIVE instances. VersionEngine runs on flat docs_df; it groups by (emetteur, lot_normalized, type_de_doc, numero_normalized) and sets `is_dernier_indice` per lifecycle. Accepted limitation: submission-instance fidelity deferred to Step 12. | ✅ ACCEPTED (Phase 2 scope) |
| **`date_limite`** | `_extract_date_limite()` on raw pending text | `GED_OPERATIONS.phase_deadline` | Embedded in reconstructed pending text `"En attente visa (YYYY/MM/DD)"` so `normalize_responses` extracts it correctly via `_extract_date_limite()`. | ✅ CONFIRMED |

---

## 3. VISA GLOBAL Verification Points (BACKEND_SEMANTIC_CONTRACT §4 Decision 5)

### VP-1 — SAS REF distinguishable from full-workflow REF

**Finding:** In flat GED, a SAS refusal is represented as the SAS step (`step_type=SAS`)
having `status_clean=REF` and `is_completed=True`, with no MOEX step in GED_OPERATIONS
(because the builder skips consultant/MOEX steps when SAS refuses).

**Adapter behaviour:** The adapter pre-computes `visa_global = "SAS REF"` in
`flat_ged_doc_meta` for these documents.

**Gap:** `WorkflowEngine.compute_visa_global_with_date()` returns `(None, None)` for
SAS-refused docs in flat mode because it finds no MOEX entry in `responses_df`.
Legacy stages that call the engine method directly (e.g. `stage_write_gf`) will miss
the SAS REF value.

**Classification:** KNOWN_GAP — requires `stage_write_gf` to use
`ctx.flat_ged_doc_meta[doc_id]["visa_global"]` when `FLAT_GED_MODE = "flat"`. Deferred
to Step 8 (clean_GF reconstruction).

**Note on legacy `approver_raw == "0-SAS"` check:** The WorkflowEngine checks
`moex.get("approver_raw") == "0-SAS"` to detect SAS REF. This path is unreachable in
both raw and flat modes because `normalize_responses()` forces all `approver_raw=0-SAS`
rows to `is_exception_approver=True`, excluding them from the engine's lookup. The
SAS REF check in the engine code is therefore a legacy dead path regardless of mode.

---

### VP-2 — SAS-only approvals excluded from VISA GLOBAL

**Finding:** In flat GED, the MOEX step's `status_clean` is derived from the MOEX GED
column verbatim. The builder applies `status_scope = "SAS"` to statuses with "-SAS"
suffix (e.g. `VAO-SAS`, `VSO-SAS`). The adapter checks `status.endswith("-SAS")` and
returns `None` for these.

**Classification:** ✅ CONFIRMED — SAS-only approvals correctly excluded.

---

### VP-3 — Canonical MOEX actor name matches GF writer expectations

**Finding:** `GED_OPERATIONS.actor_raw` for MOEX steps contains the raw GED column
header (e.g. `"0-Maître d'Oeuvre EXE"`, `"A-Maître d'Oeuvre EXE"`). The adapter uses
`actor_raw` as `approver_raw` in `responses_df`. `normalize_responses()` maps this via
`load_mapping()` to `approver_canonical = "Maître d'Oeuvre EXE"`. The
`_is_moex()` check in `workflow_engine.py` looks for `"OEUVRE"` in the canonical name —
`"Maître d'Oeuvre EXE"` contains `"OEUVRE"` → match succeeds.

**Classification:** ✅ CONFIRMED — canonical MOEX name alignment verified.

---

## 4. Known Gaps and Limitations

### GAP-1 — SAS REF lost in WorkflowEngine path (VP-1)

**Severity:** Medium  
**Scope:** `stage_write_gf` only  
**Resolution:** `stage_write_gf` must read `ctx.flat_ged_doc_meta[doc_id]["visa_global"]`
when `FLAT_GED_MODE = "flat"`, instead of calling `engine.compute_visa_global_with_date()`.
Deferred to Step 8.

---

### GAP-2 — RAPPEL reminder-history not a first-class field

**Severity:** Low  
**Scope:** Any GF output column that displays the RAPPEL/non-RAPPEL distinction beyond
scope filtering.  
**Resolution:** Must be assessed per GF column in Step 8 (clean_GF reconstruction). If
any column requires the exact RAPPEL label (not just operational lateness), it must be
classified as KNOWN_GAP in Step 8's output. The SAS scope filter itself is unaffected
— it uses the PENDING_LATE proxy which is correct.

---

### GAP-3 — `type_de_doc`, `zone`, `niveau` absent from flat GED

**Severity:** Low  
**Scope:** `VersionEngine` coarse grouping (column `type_de_doc`)  
**Resolution:** VersionEngine sets `None` for missing columns before grouping (line
227–233 of `version_engine.py`). All docs with the same (emetteur, lot_normalized,
numero_normalized) but `type_de_doc=None` are grouped together — correct behaviour
for parity since they share the same numero.

---

### GAP-4 — Report-memory overlay not applied in Phase 2 effective response

**Severity:** Declared, accepted  
**Resolution:** Deferred to Step 7 (Composition Spec). Declared in
BACKEND_SEMANTIC_CONTRACT §3 Concept 1F.

---

## 5. TEMPORARY_COMPAT_LAYER — response_date_raw string reconstruction

### What it is

`_build_responses_df()` reconstructs legacy pending text strings
(`"En attente visa (YYYY/MM/DD)"`, `"Rappel : En attente visa (YYYY/MM/DD)"`)
from flat GED's `is_blocking` and `retard_avance_status`, so that
`normalize_responses()` → `interpret_date_field()` produces the correct
`date_status_type` without requiring any change to `stage_normalize`.

### Why it's a problem

This is backward engineering: **flat GED → fake raw text → re-parsed**.
It re-enters the fragile text-parsing layer flat GED was designed to replace.
If `interpret_date_field()` ever changes its keyword matching, the compat layer
breaks silently. It also creates false confidence in Step 5 parity: the test
would be validating the string-reconstruction trick, not the true semantic path.

### Removal plan

When `stage_normalize` is updated for flat mode (Step 8 — clean_GF
reconstruction), this compat layer must be replaced by:

1. `stage_read_flat` injecting `date_status_type`, `date_limite`, `date_reponse`
   directly into `responses_df` (using the `flat_*` pass-through columns as
   the clean foundation).
2. `stage_normalize` detecting `ctx.flat_ged_mode == "flat"` and bypassing
   `interpret_date_field()` re-processing, reading the pre-injected values
   instead.
3. `response_date_raw` dropped from the flat responses_df entirely.

The compat layer is marked with `# TEMPORARY_COMPAT_LAYER — begin/end` comments
in `stage_read_flat.py` for easy location.

---

## 6. VISA GLOBAL — Authoritative Source Rule

### Rule (mandatory)

> **In flat mode, `visa_global` MUST be read from `ctx.flat_ged_doc_meta`.
> `WorkflowEngine.compute_visa_global_with_date()` MUST NOT be used.**

`WorkflowEngine` returns `(None, None)` for SAS REF documents in flat mode
because there is no MOEX entry in `responses_df` (the builder never creates
one when SAS refuses). This is a silent, incorrect result.

### Enforcement mechanism

`get_visa_global(ctx, doc_id, engine)` is exported from `stage_read_flat.py`.
It enforces the rule automatically:

```python
from pipeline.stages.stage_read_flat import get_visa_global

# Correct usage in any stage:
visa, date = get_visa_global(ctx, doc_id, ctx.wf_engine)
# → in flat mode: reads flat_ged_doc_meta (authoritative)
# → in raw mode : calls engine.compute_visa_global_with_date(doc_id)
```

### Current gap

`stage_write_gf` still calls `engine.compute_visa_global_with_date()` directly.
This must be updated in Step 8 to use `get_visa_global()`.

**Until Step 8, SAS REF documents will have an incorrect (None) visa in the
GF output when running in flat mode.** This is a declared, tracked gap —
not a silent divergence.

---

## 7. Feature Flag Usage

```python
# To activate flat mode, set in main.py or test code:
import main
main.FLAT_GED_MODE = "flat"

# Default (raw mode, existing behaviour):
# FLAT_GED_MODE = "raw"  (defined in pipeline/paths.py)
```

FLAT_GED.xlsx must be placed at `input/FLAT_GED.xlsx` (same directory as `GED_export.xlsx`),
or override `main.FLAT_GED_FILE` to a different path before calling `run_pipeline()`.

---

## 8. Files Created / Modified

| File | Action | Notes |
|---|---|---|
| `src/pipeline/stages/stage_read_flat.py` | **CREATED** | Adapter implementation |
| `docs/FLAT_GED_ADAPTER_MAP.md` | **CREATED** | This document |
| `src/pipeline/stages/__init__.py` | **MODIFIED** | Added `stage_read_flat` export |
| `src/pipeline/runner.py` | **MODIFIED** | Added mode dispatch + `stage_read_flat` import |
| `src/pipeline/context.py` | **MODIFIED** | Added `FLAT_GED_FILE`, `flat_ged_ops_df`, `flat_ged_doc_meta` fields |
| `src/pipeline/paths.py` | **MODIFIED** | Added `FLAT_GED_FILE` + `FLAT_GED_MODE = "raw"` |

---

## 9. Constraints Respected

- ✅ `src/flat_ged/` builder code not touched
- ✅ Business rules not modified
- ✅ No new semantics invented
- ✅ Legacy `mode='raw'` path runs unchanged (default)
- ✅ `is_blocking` used for blocking determination (not `is_completed == False`)
- ✅ `data_date` from flat GED used for lateness; `datetime.now()` not used
- ✅ Delay fields read from GED_OPERATIONS, not recomputed
- ✅ SAS ABSENT (synthetic) rows handled correctly (not counted as pending)
- ✅ `closure_mode` exposed as explicit per-doc field in `flat_ged_doc_meta`
- ✅ `responsible_party` synthesised using 5-rule logic with `is_blocking`
- ✅ SAS scope filter (Decision 3) reproduced before building docs_df/responses_df

---

*End of FLAT_GED_ADAPTER_MAP.md*
