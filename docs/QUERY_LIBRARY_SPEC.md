# QUERY_LIBRARY_SPEC.md

**Step:** 9c — Flat GED Query Library  
**Plan version:** v2  
**Date:** 2026-04-26  
**Status:** COMPLETE  
**Author:** Step 9c implementation  
**Depends on:** `docs/FLAT_GED_CONTRACT.md` (v1.0), `docs/FLAT_GED_REPORT_COMPOSITION.md`, `docs/BACKEND_SEMANTIC_CONTRACT.md`  
**Consumed by:** Step 10 (UI Source-of-Truth Map), Step 11 (UI Parity Harness), all UI pages

---

## 1. Purpose

`src/query_library.py` is the single query layer for all dashboard, KPI, fiche, and queue metrics. It replaces scattered, ad hoc calculations in UI pages and export scripts with deterministic, read-only functions that share the same data source and status vocabulary.

**The contract in one sentence:**
> Any metric displayed in the UI or exported to a report must be computable by calling one function from `query_library.py` — no ad hoc derivations in UI code.

---

## 2. Source Inputs

### 2.1 `flat_ged_ops_df` — GED_OPERATIONS (Required)

The structural backbone. One step row per `(numero, indice, actor)`. Source: `FLAT_GED.xlsx` sheet `GED_OPERATIONS` (37 columns, per `docs/FLAT_GED_CONTRACT.md` §4).

| Key Column | Type | Meaning |
|---|---|---|
| `numero` | int | Document number |
| `indice` | str | Revision index (A, B, C…) |
| `lot` | str | Lot code |
| `emetteur` | str | Contractor short code |
| `titre` | str | Document title |
| `step_type` | str | OPEN_DOC / SAS / CONSULTANT / MOEX |
| `actor_clean` | str | Display name for the actor |
| `status_clean` | str | Cleaned visa code (VAO, VSO, REF, HM, VAOB, …) |
| `status_family` | str | APPROVED / APPROVED_WITH_REMARKS / REFUSED / PENDING / OPENED |
| `status_scope` | str | SAS or STANDARD |
| `is_completed` | bool | True if the step has a real response |
| `is_blocking` | bool | True if the step is currently blocking progression |
| `response_date` | str (ISO) | Response date; empty if not answered |
| `phase_deadline` | str (ISO) | This step's computed deadline |
| `data_date` | str (ISO) | GED reference date (`Détails!D15`) |
| `submittal_date` | str (ISO) | Document creation date (OPEN_DOC row) |
| `global_deadline` | str (ISO) | submittal_date + 30 days |
| `retard_avance_days` | int | Days ahead (>0) or late (<0) vs phase_deadline |
| `retard_avance_status` | str | RETARD / AVANCE / "" |
| `step_delay_days` | int | max(0, effective_date − phase_deadline) |
| `delay_contribution_days` | int | Unique delay contribution after deduplication |
| `cumulative_delay_days` | int | Running sum of all delay contributions |
| `delay_actor` | str | Display name of actor owning the delay |

**Document identity in this source:** `(numero, indice)` → `doc_key = f"{numero}_{indice}"`

**OPEN_DOC exclusion rule:** OPEN_DOC is a synthetic step that models the document submittal event. It has no approver, no status, no deadline. All query functions exclude OPEN_DOC rows before computing step metrics.

### 2.2 `effective_responses_df` — Composed Truth (Required)

Output of `build_effective_responses()` in `src/effective_responses.py`. One row per `(doc_id, approver_canonical)`. Reflects Flat GED baseline **plus** eligible report_memory enrichments.

| Key Column | Type | Meaning |
|---|---|---|
| `doc_id` | str (UUID) | Pipeline-session-specific document identifier |
| `approver_canonical` | str | Canonical actor name |
| `date_status_type` | str | ANSWERED / PENDING_IN_DELAY / PENDING_LATE / NOT_CALLED |
| `status_clean` | str | Cleaned visa code after composition |
| `date_answered` | datetime | Response date (may come from report_memory) |
| `response_comment` | str | Free-text comment (may include `[report: ...]` tags) |
| `effective_source` | str | Five-value provenance tag (see §2.4) |
| `report_memory_applied` | bool | True when a PENDING step was promoted to ANSWERED |
| `flat_step_type` | str | Pass-through: OPEN_DOC / SAS / CONSULTANT / MOEX |
| `flat_actor_clean` | str | Pass-through: display name |
| `flat_phase_deadline` | str (ISO) | Pass-through: phase deadline |
| `flat_step_delay_days` | int | Pass-through: step delay days |
| `flat_data_date` | str (ISO) | Pass-through: reference data_date |

**Document identity in this source:** `doc_id` (UUID, pipeline-session-specific — changes each run).

### 2.3 `flat_ged_df` — GED_RAW_FLAT (Optional)

Source: `FLAT_GED.xlsx` sheet `GED_RAW_FLAT` (21 columns). Currently used only by provenance checks in Group G. May be None.

### 2.4 `flat_ged_doc_meta` — Per-Doc Metadata (Optional)

Dict `{doc_id: {visa_global, closure_mode, responsible_party, data_date}}` produced by `stage_read_flat._compute_doc_meta()`. Keys are UUID doc_ids matching `effective_responses_df`. May be None.

| Key | Values | Meaning |
|---|---|---|
| `visa_global` | str or None | Pre-computed MOEX visa status for the document |
| `closure_mode` | MOEX_VISA / ALL_RESPONDED_NO_MOEX / WAITING_RESPONSES | Cycle closure state |
| `responsible_party` | str or None | Current responsible actor |
| `data_date` | str (ISO) | GED reference date |

---

## 3. Metric Definitions

### 3.1 Document-Level Definitions

| Metric | Definition | Source |
|---|---|---|
| **Total docs** | Count of unique `(numero, indice)` pairs | `flat_ged_ops_df` |
| **Open doc** | Any non-OPEN_DOC step has `is_blocking = True` | `flat_ged_ops_df` |
| **Closed doc** | No non-OPEN_DOC step has `is_blocking = True` | `flat_ged_ops_df` |
| **visa_global** | MOEX step `is_completed=True` + non-SAS-scoped status → that status; or "SAS REF" if SAS refused without MOEX | `flat_ged_ops_df` (or `flat_ged_doc_meta`) |
| **responsible_party** | First blocking actor by `step_order` (highest-priority bottleneck) | `flat_ged_ops_df` |
| **total_delay_days** | Max `cumulative_delay_days` across all steps for a document | `flat_ged_ops_df` |

### 3.2 Step-Level Definitions

| Metric | Definition | Source |
|---|---|---|
| **Pending step** | `date_status_type ∈ {PENDING_IN_DELAY, PENDING_LATE}` | `effective_responses_df` |
| **Answered step** | `date_status_type == ANSWERED` | `effective_responses_df` |
| **Overdue step** | `date_status_type == PENDING_LATE` (= blocking + past deadline) | `effective_responses_df` |
| **Due next 7 days** | `PENDING_IN_DELAY` AND `flat_phase_deadline` between `data_date` and `data_date + 7d` | `effective_responses_df` |
| **step_delay_days** | `max(0, effective_date − phase_deadline)` where effective_date = response_date if answered, data_date if pending | `flat_ged_ops_df` (pre-computed) |

### 3.3 Status Families

| Family | Members | Notes |
|---|---|---|
| **Approval** | VAO, VSO, FAV, HM, VAOB | VAOB = VAO (Eid decision 2026-04-24) |
| **Rejection** | REF, DEF | |
| **HM** | HM | Subset of Approval — visa with remarks |
| **SAS REF** | REF on a SAS step | Detected via `flat_step_type == SAS` |

### 3.4 Effective Source Vocabulary

| Value | Meaning |
|---|---|
| `GED` | Step status and date come entirely from Flat GED; no report enrichment |
| `GED+REPORT_STATUS` | Step was PENDING in GED; promoted to ANSWERED using report_memory date/status |
| `GED+REPORT_COMMENT` | Step already ANSWERED in GED; report added an informational comment only |
| `GED_CONFLICT_REPORT` | Report carries a status that contradicts the GED answer; GED wins |
| `REPORT_ONLY` | Step has no GED anchor — PROHIBITED; indicates composition bug |

### 3.5 Queue Primitive Definitions

| Primitive | Definition |
|---|---|
| **Easy wins** | Docs where ONLY MOEX is blocking AND all answered non-MOEX steps have approval-family status |
| **Conflicts** | Docs with mixed approval+rejection among answered steps, OR steps with `effective_source == GED_CONFLICT_REPORT` |
| **Waiting secondary** | Docs where ALL blocking actors are non-primary (no TERRELL/EGIS/BET/MOEX keywords) |
| **Waiting MOEX** | Docs where MOEX is the sole blocking step (superset of easy_wins) |
| **Stale pending** | Blocking steps where `step_delay_days > threshold` days past deadline |

---

## 4. Function Catalog

### A. Portfolio KPIs

| Function | Returns | Source |
|---|---|---|
| `get_total_docs(ctx)` | int — total distinct docs | `flat_ged_ops_df` |
| `get_open_docs(ctx)` | int — docs with ≥1 blocking step | `flat_ged_ops_df` |
| `get_closed_docs(ctx)` | int — docs with 0 blocking steps | `flat_ged_ops_df` |
| `get_pending_steps(ctx)` | int — steps in PENDING_* state | `effective_responses_df` |
| `get_answered_steps(ctx)` | int — steps in ANSWERED state | `effective_responses_df` |
| `get_overdue_steps(ctx)` | int — steps in PENDING_LATE state | `effective_responses_df` |
| `get_due_next_7_days(ctx)` | int — PENDING_IN_DELAY steps due within 7 days | `effective_responses_df` |

### B. Workflow Status Mix

| Function | Returns | Source |
|---|---|---|
| `get_status_breakdown(ctx)` | dict — counts by status category | `effective_responses_df` |

Keys: `approval`, `rejection`, `pending`, `overdue`, `not_called`, `hm`, `sas_ref`, `report_upgraded`, `total_decisive`

### C. Consultant Performance

| Function | Returns | Source |
|---|---|---|
| `get_consultant_kpis(ctx)` | DataFrame — per approver metrics | `effective_responses_df` |

Columns: `approver_canonical`, `assigned_steps`, `answered`, `pending`, `overdue`, `avg_delay_days`, `median_delay_days`, `approval_pct`, `rejection_pct`, `hm_pct`, `open_load`

Sorted by: `open_load DESC`, `overdue DESC`

### D. Document Lifecycle

| Function | Returns | Source |
|---|---|---|
| `get_doc_lifecycle(ctx)` | DataFrame — one row per `(numero, indice)` | `flat_ged_ops_df` |

Columns: `doc_key`, `numero`, `indice`, `lot`, `emetteur`, `titre`, `is_open`, `visa_global`, `responsible_party`, `pending_actors`, `overdue_actors`, `total_delay_days`, `submittal_date`, `data_date`

Note on `pending_actors` / `overdue_actors`: pipe-separated sorted list of actor display names.

Note on `source_counts`: per-doc source provenance (GED vs GED+REPORT) requires bridging between `flat_ged_ops_df` doc_key and `effective_responses_df` UUID doc_id. This bridge is not held in QueryContext. Use `get_effective_source_mix()` for aggregate provenance. Step 10 will formalize per-doc provenance mapping.

### E. Queue Engine Primitives

| Function | Returns | Source |
|---|---|---|
| `get_easy_wins(ctx)` | DataFrame — docs ready for MOEX closure | `flat_ged_ops_df` |
| `get_conflicts(ctx)` | DataFrame — docs with contradictory statuses | `flat_ged_ops_df` + `effective_responses_df` |
| `get_waiting_secondary(ctx)` | DataFrame — docs blocked only by secondary actors | `flat_ged_ops_df` |
| `get_waiting_moex(ctx)` | DataFrame — docs with MOEX as sole blocker | `flat_ged_ops_df` |
| `get_stale_pending(ctx, days=30)` | DataFrame — steps past deadline by > days | `flat_ged_ops_df` |

`get_easy_wins` columns: `doc_key`, `numero`, `indice`, `lot`, `emetteur`, `titre`, `total_delay_days`  
`get_conflicts` columns: `doc_key`, `numero`, `indice`, `source`, `conflict_type`, `detail`  
`get_waiting_secondary` columns: `doc_key`, `numero`, `indice`, `blocking_actors`  
`get_waiting_moex` columns: `doc_key`, `numero`, `indice`, `lot`, `emetteur`, `titre`, `total_delay_days`  
`get_stale_pending` columns: `doc_key`, `numero`, `indice`, `actor_clean`, `step_type`, `step_delay_days`, `phase_deadline`, `data_date`

### F. Fiche Inputs

| Function | Returns | Source |
|---|---|---|
| `get_doc_fiche(ctx, doc_key)` | dict — full lifecycle record for one document | `flat_ged_ops_df` |
| `get_actor_fiche(ctx, actor)` | dict — full performance record for one approver | `effective_responses_df` |

`get_doc_fiche` dict keys: `doc_key`, `numero`, `indice`, `lot`, `emetteur`, `titre`, `is_open`, `visa_global`, `responsible_party`, `submittal_date`, `global_deadline`, `data_date`, `pending_actors` (list), `overdue_actors` (list), `total_delay_days`, `step_details` (list of step dicts)

`get_actor_fiche` dict keys: `actor`, `assigned_steps`, `answered`, `pending`, `overdue`, `not_called`, `approval_pct`, `rejection_pct`, `hm_pct`, `avg_delay_days`, `median_delay_days`, `max_delay_days`, `open_load`, `report_upgraded`, `answered_docs` (list), `pending_docs` (list), `overdue_docs` (list)

Note: `doc_key` format for `get_doc_fiche` is `"{numero}_{indice}"` (e.g. `"248000_A"`).  
Note: `actor` for `get_actor_fiche` is the exact `approver_canonical` string (case-sensitive).

### G. Provenance & Quality

| Function | Returns | Source |
|---|---|---|
| `get_effective_source_mix(ctx)` | dict — distribution of `effective_source` values | `effective_responses_df` |
| `get_report_upgrades(ctx)` | DataFrame — PENDING→ANSWERED promotions via report_memory | `effective_responses_df` |
| `get_conflict_rows(ctx)` | DataFrame — `GED_CONFLICT_REPORT` rows requiring manual review | `effective_responses_df` |

`get_effective_source_mix` keys: `GED`, `GED+REPORT_STATUS`, `GED+REPORT_COMMENT`, `GED_CONFLICT_REPORT`, `REPORT_ONLY`, `total`, `report_influence_pct`

---

## 5. Known Assumptions

| # | Assumption | Rationale |
|---|---|---|
| A1 | A document is **closed** if `is_blocking = False` for all non-OPEN_DOC steps | Mirrors `closure_mode ∈ {MOEX_VISA, ALL_RESPONDED_NO_MOEX}` from `flat_ged_doc_meta` |
| A2 | VAOB is **approval-family** (same as VAO) | Eid decision 2026-04-24; recorded in `effective_responses.py` |
| A3 | **Overdue** = `PENDING_LATE` in `effective_responses_df` | Set by adapter when `is_blocking=True AND retard_avance_status=RETARD` |
| A4 | **Stale** = blocking step where `step_delay_days > threshold` | step_delay_days is pre-computed in GED_OPERATIONS; threshold default = 30 days |
| A5 | **Easy win** requires ALL answered non-MOEX steps to be approval-family | A document with any rejected consultant is NOT an easy win even if MOEX is the only remaining blocker |
| A6 | **Responsible party** = first blocking actor by `step_order` | Mirrors the 5-rule logic in `stage_read_flat._compute_responsible_party()`; the highest-priority active bottleneck |
| A7 | **visa_global** is derived from GED_OPERATIONS MOEX/SAS step data | Mirrors `stage_read_flat._compute_doc_meta()`; SAS-scoped statuses (suffix `-SAS`) do not count as VISA GLOBAL |
| A8 | OPEN_DOC rows are **excluded** from all step-level metrics | OPEN_DOC is a synthetic event (submittal anchor), not an approval step |
| A9 | `doc_key = f"{numero}_{indice}"` | Stable, deterministic identifier for `flat_ged_ops_df`-based functions; distinct from UUID doc_id in `effective_responses_df` |
| A10 | `step_delay_days = max(0, effective_date − phase_deadline)` | Pre-computed by GED_OPERATIONS builder; effective_date = response_date if completed, data_date if pending |

---

## 6. Identity Systems and Bridging

Two identity systems coexist in this library:

| System | Field | Where | Format |
|---|---|---|---|
| **Structural** | `doc_key` | `flat_ged_ops_df`-based functions | `"{numero}_{indice}"` e.g. `"248000_A"` |
| **Composed** | `doc_id` | `effective_responses_df`-based functions | UUID string e.g. `"3f2a7b12-..."` |

The UUID `doc_id` is assigned by `stage_read_flat.py` at pipeline startup and changes each session. It is not stored in `flat_ged_doc_meta` alongside `numero`/`indice`.

**Bridging requirement:** To correlate doc-level structural metrics (from ops_df) with composed step metrics (from effective_responses_df), callers must provide the pipeline's `id_to_pair` mapping (a `{doc_id: (numero, indice)}` dict available inside `stage_read_flat` as a local variable). Step 10 (UI Source-of-Truth Map) will define how UI pages obtain and use this bridge.

**Where bridging is NOT required:** All Group A/D/E/F functions that work entirely from `flat_ged_ops_df` use `doc_key` and need no bridge. All Group C/G functions that work entirely from `effective_responses_df` use `doc_id` and need no bridge. Only cross-group joins need it.

---

## 7. Data Validation Contract

Every function that calls `_require_df(ctx, attr)` will:
- Raise `ValueError` if the DataFrame is `None` — with a message identifying which field to populate
- Raise `ValueError` if the DataFrame is empty
- Raise `TypeError` if the field is not a DataFrame

Functions validate that required columns exist before use; missing columns are logged as warnings and handled gracefully (returning 0 or empty DataFrame rather than crashing).

`_smoke_test(ctx)` validates that all function groups run without exceptions against a real context.

---

## 8. Future Hooks for Chain/Onion (Step 12)

This library is designed to be extended without modification when Chain/Onion logic is added.

| Extension Point | How Chain/Onion connects |
|---|---|
| `get_easy_wins` | Chain/Onion may filter easy_wins by submission-instance state (SEPARATE_INSTANCE docs excluded from easy_wins if an earlier instance was refused) |
| `get_conflicts` | Chain/Onion resolves multi-instance status conflicts (same doc, different submission cycles) that appear here as GED-internal conflicts |
| `get_doc_fiche` | `step_details` already returns all steps; Chain/Onion adds `instance_role` column to contextualize steps across cycles |
| `get_doc_lifecycle` | Add `instance_count` and `active_cycle` columns once Chain/Onion supplies submission-instance data |
| `get_consultant_kpis` | Delay metrics become more accurate once Chain/Onion removes cross-cycle step contamination |
| `QueryContext` | Add `chain_onion_df` as an optional fifth DataFrame; all existing functions remain unchanged |

The key design principle: Chain/Onion data is **additive** to QueryContext. No existing function signature changes. New functions (e.g., `get_cycle_history(ctx, doc_key)`) are added alongside the existing catalog.

---

## 9. Usage Pattern

### From PipelineState (flat mode)

```python
from src.query_library import QueryContext, get_total_docs, get_consultant_kpis, _smoke_test

# After pipeline runs in flat mode:
ctx = QueryContext(
    flat_ged_ops_df        = ps.flat_ged_ops_df,      # GED_OPERATIONS sheet
    effective_responses_df = ps.responses_df,          # composed effective responses
    flat_ged_doc_meta      = ps.flat_ged_doc_meta,     # optional per-doc meta
)

print(get_total_docs(ctx))
print(get_consultant_kpis(ctx).head())
_smoke_test(ctx)
```

### From RunContext (UI / data_loader.py)

```python
from src.query_library import QueryContext

# After load_run_context():
ctx = QueryContext(
    flat_ged_ops_df        = run_ctx.flat_ged_ops_df,   # if available
    effective_responses_df = run_ctx.responses_df,
)
```

### For doc and actor fiches

```python
from src.query_library import get_doc_fiche, get_actor_fiche

fiche = get_doc_fiche(ctx, "248000_A")
print(fiche["visa_global"], fiche["pending_actors"])

actor_data = get_actor_fiche(ctx, "BET Structure")
print(actor_data["approval_pct"], actor_data["open_load"])
```

---

*End of QUERY_LIBRARY_SPEC.md*  
*Step 9c output — paired with `src/query_library.py`*
