# Backend Semantic Contract

**Step:** 3b — Backend Semantic Contract  
**Plan version:** v2  
**Date:** 2026-04-23  
**Depends on:** `docs/FLAT_GED_CONTRACT.md` (v1.0), `docs/GED_ENTRY_AUDIT.md`  
**Consumed by:** Step 4 (Flat GED Adapter), Step 5 (Parity Harness), Steps 8–11 (reconstruction and UI)

---

## 1. Purpose

This document defines the operational meanings that must survive the switch from raw GED input to flat GED input. It is not an adapter implementation spec. It does not tell Step 4 how to write code. It tells Step 4 what meanings it is not allowed to change.

**What this document protects:**
The business semantics of eight concepts that the current backend computes from raw GED data. When the adapter replaces raw GED with flat GED as the data source, these concepts must remain operationally identical to what the legacy engine produces — or any deviation must be explicitly declared, justified, and accepted by Eid before Step 4 is considered done.

**What this document does NOT do:**
- It does not specify adapter code structure or field mappings (that is Step 4's `FLAT_GED_ADAPTER_MAP.md`).
- It does not specify report-memory merge rules (that is Step 7).
- It does not address Chain/Onion, cue engine, or UI surface mappings.

**Builder status:** The flat GED builder is frozen. This contract is written against its output as-is. If a contract clause conflicts with builder output, the clause must be flagged to Eid — the builder is not modified to satisfy this document.

**Scope of this contract:** Phase 2 only. Where Phase 2 accepts a known limitation (e.g. submission-instance collapse), this is stated explicitly and not treated as a gap to fix here.

---

## 2. Scope

This document covers backend semantic concepts only: the meanings that flow through `src/` from GED entry to GF output. It does not cover:

- **Report-memory merge semantics** — referenced at high level in Concept 1 (Effective Response); fully specified in Step 7.
- **UI surface mapping** — out of scope; covered in Steps 10–11.
- **Chain/Onion** — out of scope; covered in Step 12.
- **Cue engine** — out of scope; covered in Step 13.
- **Formatting fidelity** — out of scope; deferred to Step 9b.

---

## ⚠ Important — Data Granularity Constraint

All semantics in this document operate at the `(numero, indice)` level and reflect only the **ACTIVE instance** selected by the flat GED builder.

Multiple real submission instances may exist for the same `(numero, indice)` — resubmissions, parallel submissions, corrections — but they are not represented as separate entities in `GED_OPERATIONS` at this stage. Non-ACTIVE instances are visible only in `DEBUG_TRACE` via `instance_role` and `submission_instance_id`.

This limitation is **accepted for Phase 2** and must not be silently "worked around" by the adapter. Any adapter behavior that attempts to surface or distinguish non-ACTIVE instances falls outside Phase 2 scope and must be deferred to Step 12 (Chain/Onion).

This constraint applies downstream to:
- **Step 8** (clean_GF reconstruction): operates at document-code level; non-ACTIVE instances logged in `collapsed_instances`, not merged into output.
- **Step 10** (UI source-of-truth map): values classified as `document-code level` are safe; values that require `submission-instance level` distinction are flagged explicitly.
- **Chain/Onion (Step 12)**: where submission-instance fidelity is restored.

---

## 3. Semantic Concepts

---

### Concept 1 — Effective Response

#### A. Definition

The operationally accepted response state of an approver step for a document — the answer the backend treats as the ground truth when computing blocking, cycle closure, responsible party, and GF output.

#### B. Current source in legacy backend

- `src/effective_responses.py` / `build_effective_responses()` — merges GED-normalized responses with persisted consultant report memory.
- `src/normalize.py` / `normalize_responses()` — produces the GED-only base layer (`date_status_type`, `status_clean`, `date_answered`).
- `src/workflow_engine.py` / `WorkflowEngine.__init__()` — consumes the merged effective responses and builds the per-(doc, approver) best-state lookup.

The merge rules in `build_effective_responses()` are:
- Rule 1: GED is already ANSWERED → GED is source of truth; report memory is not applied.
- Rule 2: GED is PENDING + report memory has an eligible answer → upgrade to ANSWERED using report data.
- Rule 3: GED is PENDING + no eligible report answer → remain pending.
- Rule 4: GED is NOT_CALLED → left as-is; report memory cannot invent workflow rows.

#### C. Flat GED source

For Phase 2, flat GED is the base truth before report enrichment:
- `GED_OPERATIONS.is_completed` — `True` if the step has a real response.
- `GED_OPERATIONS.response_status_clean` (alias `status_clean`) — the cleaned visa code.
- `GED_OPERATIONS.response_date` — the ISO date of the response, if answered.
- `GED_OPERATIONS.is_blocking` — current blocking state (see Concept 2).

Report-memory overlay on top of flat GED base is deferred to Step 7. For Phase 2, `is_completed = True` in GED_OPERATIONS is the effective response indicator.

#### D. Required adapter rule

The adapter must treat `GED_OPERATIONS.is_completed = True` as the Phase 2 effective response indicator. Where legacy code reads `date_status_type == "ANSWERED"` from the normalized responses DataFrame, the adapter must supply `is_completed = True` from GED_OPERATIONS as the equivalent signal. The adapter must not invent ANSWERED states for rows where flat GED shows `is_completed = False`.

#### E. Invariants

- A step where `is_completed = True` must never be treated as pending by downstream logic.
- A step where `is_completed = False` must never be treated as completed by downstream logic.
- `OPEN_DOC` rows (`step_type = "OPEN_DOC"`) are never an effective response. They exist as a synthetic timeline anchor, not as an approval event. Downstream code must filter them out when computing approval state.
- A synthetic SAS row (`operation_rule_used` contains `"SYNTHETIC_SAS"`) must never masquerade as a real consultant answer. It represents SAS absence, not SAS approval by a consultant.
- No step that is `NOT_CALLED` / `ABSENT` in flat GED may be promoted to ANSWERED by the adapter without going through the explicit report-memory merge layer (Step 7).

#### F. Known limitation

Report-memory overlay is not part of this phase's effective response computation. As a result, the Phase 2 effective response may show a step as PENDING that would have been upgraded to ANSWERED if report memory were applied. This is a declared, accepted limitation for Phase 2 parity. Step 7 closes this gap.

---

### Concept 2 — Blocking

#### A. Definition

A step is blocking if it is the active bottleneck preventing the document's workflow from progressing — meaning it is pending and the cycle has not yet been closed by MOEX or full-response consensus.

**Critical clarification:** Blocking is dynamic, not static. A step that was blocking at one point in the workflow may cease to be blocking without having received a response. Pending does not equal blocking.

#### B. Current source in legacy backend

- `src/workflow_engine.py` / `WorkflowEngine.__init__()` — `date_status_type` field per (doc, approver).
- `src/workflow_engine.py` / `compute_responsible_party()` — consumes blocking state to determine who holds up the document.
- `src/workflow_engine.py` / `compute_visa_global_with_date()` — MOEX_VISA closes the cycle and implicitly de-flags remaining pending consultants.

In the legacy engine, a consultant row is considered blocking when `date_status_type` is `PENDING_IN_DELAY` or `PENDING_LATE`. However, once `compute_visa_global_with_date()` returns a non-None value (MOEX has issued its visa), those same PENDING rows are no longer operationally blocking — the cycle is closed. The legacy engine handles this implicitly in `compute_responsible_party()` rule 5 (visa exists → closed → `None`).

#### C. Flat GED source

- `GED_OPERATIONS.is_blocking` — the explicit blocking flag per step, already de-flagged by the flat builder when `MOEX_VISA` is achieved.
- `GED_OPERATIONS.is_completed` — use this, not `is_blocking`, to test whether a step actually received a response.
- `GED_OPERATIONS.status_clean` — the visa code driving the blocking state.

The flat builder's `is_blocking` field encodes the dynamic de-flagging directly: once MOEX_VISA is reached, pending consultant rows have `is_blocking = False` even if `is_completed = False`. This behaviour is documented in `FLAT_GED_CONTRACT.md` §4 note on `is_blocking`.

#### D. Required adapter rule

The adapter must preserve the following distinction when supplying blocking state to downstream logic:

- Use `GED_OPERATIONS.is_blocking` as the authoritative blocking signal — not `is_completed == False`.
- Downstream code that currently checks `date_status_type in (PENDING_IN_DELAY, PENDING_LATE)` as a proxy for blocking must be updated to check `is_blocking = True` from flat GED.
- The adapter must never re-derive blocking state from scratch by treating all `is_completed = False` rows as blocking. That would lose the MOEX-closure de-flagging.

#### E. Invariants

- `is_blocking = False` does not mean the step responded. A step can be `is_completed = False` AND `is_blocking = False` simultaneously — this means the cycle was closed by MOEX before the consultant answered.
- Pending consultant rows after `MOEX_VISA` closure are not blocking. The adapter must preserve this.
- `OPEN_DOC` is never blocking. `GED_OPERATIONS` already enforces `is_blocking = False` for `OPEN_DOC` rows.
- A step that is `is_blocking = True` must have a non-null `phase_deadline` — it is waiting on a real deadline.
- There is never a state where `is_completed = True` and `is_blocking = True` on the same row. If this is observed, it is a data error, not a valid blocking state.

#### F. Known limitation

None for Phase 2. The flat builder's `is_blocking` field directly encodes the semantics needed.

---

### Concept 3 — Cycle Closure

#### A. Definition

The workflow cycle state for a document — whether it is fully closed, closed without MOEX, or still waiting. Cycle closure determines whether pending consultant rows remain operationally blocking, and whether a VISA GLOBAL can be issued.

#### B. Current source in legacy backend

The legacy engine does not have an explicit cycle closure field. It is implicitly derived by combining:
- `compute_visa_global_with_date()` — if MOEX has responded, the cycle is `MOEX_VISA`-closed.
- `compute_global_state()` / `ALL_PRIMARY_DONE` + `MOEX_DONE` flags — aggregated per document.

The legacy engine determines cycle closure reactively, at query time. There is no pre-computed `closure_mode` column in the legacy pipeline.

#### C. Flat GED source

The flat builder makes cycle closure explicit and pre-computed. From `FLAT_GED_CONTRACT.md` §8 Rule 7 and `run_report.json`:

| Closure mode | Condition | Effect |
|---|---|---|
| `MOEX_VISA` | MOEX step exists, `is_completed = True`, `response_date` is non-empty | Remaining pending consultant rows are de-flagged (`is_blocking = False`) |
| `ALL_RESPONDED_NO_MOEX` | No MOEX step, but all SAS + CONSULTANT rows are `is_completed = True` | Cycle closed without a final MOEX visa |
| `WAITING_RESPONSES` | Neither condition met | Cycle is open; at least one step is still pending |

The closure mode is also reflected in `run_report.json` under `closure.MOEX_VISA`, `closure.ALL_RESPONDED_NO_MOEX`, `closure.WAITING_RESPONSES` counts.

Note: Flat GED does not expose a per-document `closure_mode` column in GED_OPERATIONS directly. The adapter must derive the closure mode per document by inspecting GED_OPERATIONS step states (MOEX `is_completed`, all-responded test). The run_report.json closure counts are aggregate totals only.

#### D. Required adapter rule

The adapter must compute and expose `closure_mode` as an explicit per-document field using the three-state vocabulary:
- `MOEX_VISA`
- `ALL_RESPONDED_NO_MOEX`
- `WAITING_RESPONSES`

This field must be made available to downstream logic and parity validation. It is not optional — Step 5 (parity harness) and Step 10 (UI source-of-truth map) depend on it being an explicit, queryable output of the adapter.

The closure derivation rule from flat GED:
1. Find the MOEX row for the document (if any): `step_type = "MOEX"`.
2. If MOEX exists and `is_completed = True` and `response_date` is non-empty → `MOEX_VISA`.
3. Else if no MOEX row, and all rows where `step_type in ("SAS", "CONSULTANT")` have `is_completed = True` → `ALL_RESPONDED_NO_MOEX`.
4. Otherwise → `WAITING_RESPONSES`.

The `closure_mode` field must also drive the de-flagging of `is_blocking` — the adapter must not re-compute blocking without accounting for closure.

#### E. Invariants

- `MOEX_VISA` closure means the MOEX row must have `is_completed = True` AND a non-empty `response_date`. A MOEX row with `is_completed = False` is not a closed cycle.
- Once `MOEX_VISA` is achieved, no CONSULTANT row may have `is_blocking = True`. If any does, it is a data error from the builder.
- `ALL_RESPONDED_NO_MOEX` closure cannot coexist with any SAS or CONSULTANT row having `is_completed = False`.
- `WAITING_RESPONSES` cycles must always have `data_date` as the reference for lateness computation — never `datetime.now()`. This is enforced by the flat builder reading `data_date` from `Détails!D15`.
- Cycle closure is evaluated per `(numero, indice)` at the ACTIVE instance level (Phase 2 scope constraint).

#### F. Known limitation

Flat GED does not expose a pre-computed per-row `closure_mode` column in GED_OPERATIONS. The adapter must compute it from step states. This is a minor additional computation, not a semantic gap.

---

### Concept 4 — VISA GLOBAL

#### A. Definition

The final official visa issued by MOEX (Maître d'Oeuvre EXE / GEMO) for a document — the top-level approval result that determines whether the document is accepted, accepted with remarks, or refused.

#### B. Current source in legacy backend

- `src/workflow_engine.py` / `compute_visa_global_with_date(doc_id)` — returns `(visa_status, visa_date)`.

The function identifies the MOEX approver entry by matching canonical names containing `"MOEX"`, `"GEMO"`, or `"OEUVRE"` (via `_is_moex()`). It then applies four specific rules:
- No MOEX entry, or MOEX not ANSWERED → `(None, None)`
- Status `VAO-SAS` or `VSO-SAS` → `(None, None)` (SAS-stage only, not final MOEX visa)
- Status `REF` from `approver_raw == "0-SAS"` → `("SAS REF", date)`
- Status `REF` from full-workflow track → `("REF", date)`
- All other ANSWERED MOEX statuses → `(status, date)` verbatim

#### C. Flat GED source

Per `FLAT_GED_CONTRACT.md` §4:
- `GED_OPERATIONS.visa_global` (or equivalent MOEX row `status_clean`) — the MOEX visa code, derived from the MOEX GEMO column verbatim.
- The MOEX row is identifiable by `step_type = "MOEX"` in GED_OPERATIONS.

This is the **expected near-direct mapping** case. Both the legacy engine and the flat builder derive the visa from the MOEX column verbatim. However, this mapping requires explicit semantic verification on three points before the adapter can treat it as confirmed:

1. **SAS REF handling:** The legacy engine distinguishes a SAS-stage refusal (`approver_raw == "0-SAS"` + `status == "REF"`) from a full-workflow MOEX refusal. The flat builder must expose the same distinction. The adapter must confirm that `GED_OPERATIONS` carries sufficient information to reproduce this distinction — specifically, that SAS REF is either pre-computed or derivable from the SAS row's `status_clean` = `"REF"` combined with `step_type = "SAS"`.

2. **SAS-only approval exclusion:** Legacy engine returns `(None, None)` for `VAO-SAS` / `VSO-SAS` statuses — these indicate SAS first-pass approval, not a final MOEX visa. The adapter must confirm that flat GED does not surface these in the MOEX step row or in the `visa_global` field.

3. **Canonical MOEX identity:** The legacy engine identifies MOEX by checking for `"MOEX"`, `"GEMO"`, or `"OEUVRE"` in the approver canonical name. The flat builder uses `step_type = "MOEX"` to mark the MOEX step. The adapter must verify that the `actor_clean` or canonical approver name in the MOEX step row of GED_OPERATIONS matches what the downstream GF writer expects — a mismatch in canonical naming would silently break VISA GLOBAL output.

**The mapping is expected to be near-direct. These three verification points do not imply a likely gap — they are explicit confirmation tasks that Step 4 must complete before marking the adapter done.**

#### D. Required adapter rule

The adapter must:
- Source VISA GLOBAL exclusively from the MOEX step row (`step_type = "MOEX"`) in GED_OPERATIONS.
- Never derive VISA GLOBAL from arbitrary CONSULTANT or SAS rows.
- Reproduce the SAS REF distinction: if the document was refused at SAS stage, the visa must be `"SAS REF"`, not `"REF"`.
- Exclude SAS-only approvals (`status_scope = "SAS"` on non-MOEX rows) from VISA GLOBAL entirely.

#### E. Invariants

- VISA GLOBAL is derived solely from the MOEX step row. No consultant row, no SAS row, no OPEN_DOC row contributes to VISA GLOBAL.
- A SAS-stage approval (`VAO-SAS`, `VSO-SAS`) must never be returned as a final VISA GLOBAL value.
- A `"SAS REF"` result is distinct from `"REF"`. They must not be collapsed.
- VISA GLOBAL is `None` (no value) until MOEX has issued an ANSWERED response. A MOEX row with `is_completed = False` must not produce a VISA GLOBAL value.
- The canonical name string used to identify the MOEX approver in GED_OPERATIONS must exactly match what downstream GF column writers expect. This must be verified before Step 4 is closed.

#### F. Known limitation

The three verification points (SAS REF sourcing, SAS-only exclusion, canonical name match) are left as explicit confirmation tasks for Step 4. If any of them reveals a genuine semantic gap, it will be documented in `FLAT_GED_ADAPTER_MAP.md` with a `KNOWN_GAP` classification.

---

### Concept 5 — Responsibility / Responsible Party

#### A. Definition

The single entity currently holding up a document's progression — the party who must act before the workflow can advance.

#### B. Current source in legacy backend

- `src/workflow_engine.py` / `compute_responsible_party(engine, doc_ids)` — module-level function, 5-rule decision tree.

The five rules, applied in order:

1. `visa == "REF"` → `"CONTRACTOR"` (full-workflow refusal; contractor must resubmit)
2. `visa == "SAS REF"` → `"CONTRACTOR"` (SAS-stage refusal; submission itself was defective)
3. Any consultant has `date_status_type in (PENDING_IN_DELAY, PENDING_LATE)`:
   - Exactly one pending consultant → that consultant's canonical name
   - Two or more → `"MULTIPLE_CONSULTANTS"`
4. No pending consultants AND `visa is None` → `"MOEX"` (all consulted parties answered; MOEX must issue its visa)
5. No pending consultants AND visa is non-None → `None` (document is closed; no one is responsible)

#### C. Flat GED source

There is no `responsible_party` column in flat GED. This is a synthesis gap confirmed in Step 3. The flat GED fields that provide the raw ingredients are:
- `GED_OPERATIONS.is_blocking` — per-step blocking flag (post-MOEX de-flagging applied)
- `GED_OPERATIONS.is_completed` — per-step completion
- `GED_OPERATIONS.step_type` — to identify MOEX vs CONSULTANT vs SAS rows
- `GED_OPERATIONS.actor_clean` — the display name of the approver
- VISA GLOBAL (Concept 4) — to apply rules 1 and 2

#### D. Required adapter rule

The adapter must synthesize `responsible_party` from GED_OPERATIONS rows using exactly the legacy 5-rule logic from `compute_responsible_party()`. The adapter must not:
- Invent a sixth rule not present in the legacy engine.
- Collapse rules 1 and 2 (both map to `"CONTRACTOR"` but for different reasons — the distinction matters for reporting).
- Apply rule 3 using `is_completed = False` instead of `is_blocking = True`. This would falsely blame consultants whose blocking state was de-flagged by MOEX closure.

The adapter is allowed to implement the 5-rule logic in `stage_read_flat.py` as an internal computation, provided the output field name and possible values are identical to the legacy engine.

#### E. Invariants

- `"REF"` or `"SAS REF"` VISA GLOBAL → responsible party is always `"CONTRACTOR"`, never a consultant name.
- Exactly one `is_blocking = True` CONSULTANT row → responsible party is that consultant's canonical name.
- Two or more `is_blocking = True` CONSULTANT rows → `"MULTIPLE_CONSULTANTS"`.
- Zero `is_blocking = True` rows + no VISA GLOBAL → `"MOEX"`.
- Zero `is_blocking = True` rows + VISA GLOBAL exists (and is not REF/SAS REF) → `None` (closed).
- MOEX row with `is_blocking = True` must not appear in rule 3 — MOEX is evaluated separately as the VISA GLOBAL issuer, never as a pending consultant.
- `OPEN_DOC` rows are never considered in responsible-party computation.

#### F. Known limitation

The canonical name used in `actor_clean` (flat GED) for identifying MOEX and individual consultants must match the strings the GF column writer expects. If canonical names differ between legacy and flat GED, the responsible-party output will silently name the wrong entity. This is the same canonical-name verification risk noted in Concept 4.

---

### Concept 6 — Pending vs Late Semantics

#### A. Operational Lateness

**Definition:** A step is operationally late if it is still pending AND the current reference date (`data_date`) has passed the step's deadline (`phase_deadline`).

**Current source in legacy backend:** `src/normalize.py` / `interpret_date_field()` — classifies a step as `PENDING_IN_DELAY` (first-request, within deadline) or `PENDING_LATE` (reminder sent, implies past deadline). The deadline itself is extracted from the parenthesized date in the "Date réponse" text field.

**Flat GED source:**
- `GED_OPERATIONS.phase_deadline` — the computed deadline for this step.
- `GED_OPERATIONS.retard_avance_days` — pre-computed days ahead (`> 0`) or late (`< 0`) relative to `phase_deadline`.
- `GED_OPERATIONS.retard_avance_status` — `"RETARD"` (late) or `"AVANCE"` (ahead).
- `GED_OPERATIONS.data_date` — the reference date used (from `Détails!D15`).

**Conclusion:** Operational lateness is fully recoverable from flat GED fields. The adapter does not need to recompute lateness from scratch; it can read `retard_avance_status` or recompute from `phase_deadline` vs `data_date` directly.

#### B. Reminder-History / RAPPEL Semantics

**Definition:** A `RAPPEL` state in the legacy engine means that a second request (reminder) was sent to the approver, indicated by the presence of the word "Rappel" in the "Date réponse" text field of the GED. This is a distinct label in `_build_sas_lookup()` in `src/domain/sas_helpers.py`.

**Flat GED source:** There is no dedicated `RAPPEL` field in GED_OPERATIONS or GED_RAW_FLAT. The flat builder collapses `PENDING_IN_DELAY`, `PENDING_LATE`, and the RAPPEL condition into `date_status_type = "PENDING_LATE"` (in GED_RAW_FLAT) or `status_family = "PENDING"` (in GED_OPERATIONS). The underlying text that contained "Rappel" is not preserved as a first-class field.

**Important distinction:** Operational lateness (can a step be computed as overdue relative to `data_date`?) is YES recoverable from flat GED. RAPPEL reminder-history (was a reminder email sent? is the step in its second-request phase?) is NOT guaranteed as a preserved first-class semantic in Phase 2.

#### C. Required adapter rule

The adapter must:
- Use `GED_OPERATIONS.data_date` (from `Détails!D15`) as the reference date for all lateness computations. Never use `datetime.now()`.
- Treat `retard_avance_status = "RETARD"` or `retard_avance_days < 0` as the operational late signal.
- Not claim that the adapter fully preserves the legacy RAPPEL state, unless the flat builder is confirmed to expose it separately.

#### D. Invariants

- All lateness computation references `data_date` from `Détails!D15`. `datetime.now()` is never used anywhere in the pipeline.
- A step is operationally late if and only if: `is_blocking = True` AND `data_date > phase_deadline`.
- Operational lateness must be reproducible from flat GED fields without requiring the original raw "Date réponse" text string.
- RAPPEL reminder-history may remain a Phase 2 limitation if the flat builder does not expose it explicitly. Any downstream GF column that currently uses the `RAPPEL` label must be explicitly assessed in Step 4 and classified as `KNOWN_GAP` in the adapter map if it cannot be reproduced.

#### E. Known limitation

The legacy `RAPPEL` state is a separate label in `_build_sas_lookup()` but not exposed as a standalone field in flat GED. Whether any GF output column or dashboard display depends on this distinction must be determined in Step 4. If it does, the adapter cannot reproduce it from flat GED alone without a new flat GED field, which would require unfreezing the builder (not permitted in Phase 2).

---

### Concept 7 — SAS Semantics

#### A. Definition

SAS (the `0-SAS` approver / Bureau de Contrôle) is a conformity gate that must be cleared before consultant and MOEX phases begin. Its state determines whether the full workflow can proceed.

#### B. Current source in legacy backend

- `src/normalize.py` / `normalize_responses()` — maps SAS row to `date_status_type` (NOT_CALLED / PENDING_IN_DELAY / PENDING_LATE / ANSWERED).
- `src/normalize.py` / `enrich_docs_with_sas()` — joins the best SAS response onto `docs_df` as `sas_reponse`.
- `src/domain/sas_helpers.py` / `_build_sas_lookup()` — per-doc SAS status dict (ANSWERED / PENDING_IN_DELAY / NOT_CALLED / RAPPEL).
- `src/domain/sas_helpers.py` / `_apply_sas_filter()` — removes documents from the processing scope where SAS has an unresolved RAPPEL reminder AND `created_at` year < 2026.

#### C. Flat GED source

The flat builder defines three SAS states (FLAT_GED_CONTRACT.md §8 Rule 4):

| State | Condition | Flat GED behaviour |
|---|---|---|
| `ABSENT` | `0-SAS` column was never called in GED | Synthetic SAS row inserted with `response_status_raw = "SYNTHETIC_VSO-SAS"`, `response_date = submittal_date`, `is_sas = True` |
| `ANSWERED` | `0-SAS` has a real response date | Normal flow — SAS step `is_completed = True`; consultant and MOEX steps proceed |
| `PENDING` | `0-SAS` has pending text (any form) | CONSULTANT and MOEX steps are skipped entirely from GED_OPERATIONS |

Identifiable in GED_OPERATIONS via:
- `step_type = "SAS"` — the SAS step row.
- `is_sas = True` in GED_RAW_FLAT — the SAS approver row.
- `operation_rule_used` containing `"SYNTHETIC_SAS"` — synthetic rows.

#### D. SAS filter scope — explicit Phase 2 decision required

Step 3 confirmed that `_apply_sas_filter()` (`src/domain/sas_helpers.py`) removes documents from scope where:
- (a) The `0-SAS` approver has "Rappel" in `response_date_raw` (reminder was sent — SAS has not been cleared), AND
- (b) `created_at` year < 2026

This filter permanently excludes these documents from the processing pipeline in the legacy path — they do not appear in `versioned_df`, `dernier_df`, or the GF output.

The flat builder does not apply this filter. All documents pass through regardless of SAS state or creation year.

**Recommendation for Phase 2:** To preserve legacy scope during parity testing (Step 5), the adapter should reproduce the legacy SAS filter behavior explicitly — identifying documents in GED_OPERATIONS where the SAS step is `PENDING` AND the `submittal_date` year < 2026, and excluding them from the adapter's output before feeding downstream stages. This is the only way to achieve apples-to-apples parity in Step 5. **This recommendation must be explicitly accepted or overruled by Eid before Step 4 begins.**

#### E. Required adapter rule

- The adapter must treat `ABSENT` (synthetic SAS row) differently from `PENDING` (real SAS row awaiting response). An ABSENT SAS means the conformity gate was never needed — it should not be treated as a blocking gate. A PENDING SAS means the gate is actively blocking.
- The adapter must never treat a synthetic SAS response as a real consultant answer.
- The SAS scope filter (RAPPEL + pre-2026) must be an explicit decision in `FLAT_GED_ADAPTER_MAP.md` — either reproduced or explicitly waived by Eid.

#### F. Invariants

- The consultant phase cannot start if the SAS step is `PENDING` in flat GED (GED_OPERATIONS will have no CONSULTANT or MOEX rows for that document — the builder already enforces this).
- A synthetic SAS row (`operation_rule_used` contains `"SYNTHETIC_SAS"`) must never be counted as a real answered consultant response in downstream logic.
- SAS scope filtering (RAPPEL + pre-2026 exclusion) must be made explicit in the adapter. It must not be silently omitted, as doing so changes document scope — not just field values.
- SAS state is read from the `step_type = "SAS"` row in GED_OPERATIONS. There is one SAS row per document (real or synthetic).

#### G. Known limitation

The legacy RAPPEL state within SAS (the distinction between `PENDING_IN_DELAY` and `RAPPEL` in `_build_sas_lookup()`) is collapsed to `PENDING` in flat GED. For the SAS filter (RAPPEL + pre-2026), the adapter must identify PENDING SAS rows where the original GED source had a "Rappel" text. Since flat GED does not explicitly label RAPPEL, this may require checking `date_status_type = "PENDING_LATE"` in GED_RAW_FLAT for the SAS row as the nearest proxy. This must be confirmed in Step 4.

---

### Concept 8 — Delay Contribution

#### A. Definition

Each step's unique, non-double-counted contribution to the document's total cumulative delay — the portion of calendar days of lateness that is attributable specifically to this step and not already counted by an earlier step.

#### B. Current source in legacy backend

The legacy engine does not compute delay contribution. Delay logic previously existed in an earlier version and was moved into the flat GED builder as its ground-truth computation layer. The flat builder is now the authoritative source for delay semantics.

#### C. Flat GED source

From `FLAT_GED_CONTRACT.md` §8 Rule 6 and GED_OPERATIONS columns:

| Column | Meaning |
|---|---|
| `step_delay_days` | `max(0, effective_date - phase_deadline)` — raw delay before deduplication |
| `delay_contribution_days` | `max(0, step_delay - cumulative_so_far)` — this step's unique contribution |
| `cumulative_delay_days` | Running sum of all contributions up to and including this step |
| `delay_actor` | Display name of the actor owning the delay; `"NONE"` if no contribution |

Where `effective_date`:
- = `response_date` if the step is completed
- = `data_date` if the step is still open (pending)

#### D. Required adapter rule

The adapter must read delay values from GED_OPERATIONS directly. It must not recompute delay from scratch using alternative logic. The flat builder's delay computation is the backend contract — it replaces any prior legacy delay logic. Downstream code that previously computed delay differently must be updated to consume these flat GED fields.

The adapter must not apply any additional delay deduplication on top of what flat GED already computed — doing so would double-deduplicate and corrupt the values.

#### E. Invariants

These four invariants are guaranteed by the flat builder and must remain true after any adapter transformation of the delay fields:

1. `cumulative_delay_days` is monotonically non-decreasing across steps within a document (sorted by `step_order`).
2. `delay_contribution_days >= 0` for every step.
3. `delay_contribution_days <= step_delay_days` for every step.
4. `sum(delay_contribution_days) == final cumulative_delay_days` across all steps of a document.

Additionally:
- `OPEN_DOC` step always has `step_delay_days = 0`, `delay_contribution_days = 0`, `cumulative_delay_days = 0`. It never contributes delay.
- All delay computation uses `data_date` from `Détails!D15` as the reference for open steps. Never `datetime.now()`.
- If a step has `delay_contribution_days = 0`, it does not mean the step was on time — it may mean its delay was already covered by a prior step. Read `step_delay_days` to understand raw lateness.

#### F. Known limitation

None. The flat builder is the authoritative delay computation layer for Phase 2 and beyond. This is a new semantic contract, not a migration of legacy logic.

---

## 4. Phase 2 Integration Decisions

These are the concrete decisions that Step 4 must follow. They are not suggestions. Any deviation requires explicit sign-off from Eid before Step 4 is considered done.

---

**Decision 1 — `is_dernier_indice` proxy**

For Phase 2, `instance_role == "ACTIVE"` in GED_OPERATIONS (or DEBUG_TRACE) is the accepted proxy for `is_dernier_indice = True`. The adapter must filter GED_OPERATIONS to `instance_role == "ACTIVE"` rows before constructing the per-document view that downstream stages consume.

Accepted limitation: The underlying computation differs (legacy engine uses Jaccard + date-based lifecycle reconstruction; flat builder uses GED's own scoring-based candidate resolution). Submission-instance fidelity is deferred to Step 12 (Chain/Onion).

---

**Decision 2 — `responsible_party` synthesis**

The adapter must synthesize `responsible_party` in `stage_read_flat.py` by applying the legacy 5-rule logic from `compute_responsible_party()` over GED_OPERATIONS rows. Flat GED does not provide this field pre-computed. The synthesis must use `is_blocking` (not `is_completed == False`) as the pending-consultant signal, to preserve MOEX-closure de-flagging semantics.

---

**Decision 3 — Legacy SAS filter**

**Decision: ACCEPTED — the adapter WILL reproduce the legacy SAS filter behavior for Phase 2 parity.**

Documents meeting both conditions will be excluded from the adapter output before any downstream processing:
- SAS step is `PENDING` in flat GED, AND
- `submittal_date` year < 2026

This matches the behavior of `_apply_sas_filter()` in `src/domain/sas_helpers.py`, which removes these documents from `docs_df` and `responses_df` before the version engine and GF writer see them.

This is a **temporary constraint for Phase 2 parity validation (Step 5)**. It may be revisited after Gate 1 is passed. If revisited, any scope change must be explicitly decided and all resulting differences re-classified in a new parity run.

Rationale: preserving this filter makes Step 5's `REAL_DIVERGENCE = 0` target achievable on an apples-to-apples basis. Omitting it would force dozens of scope-difference rows into the parity report that are not real semantic divergences, complicating Gate 1 triage.

---

**Decision 4 — PENDING sub-type and RAPPEL granularity**

Operational lateness (a step is overdue relative to `data_date`) is fully recoverable from flat GED via `phase_deadline`, `retard_avance_status`, and `retard_avance_days`. The adapter must use `data_date` from `Détails!D15` for all lateness calculations.

The legacy `RAPPEL` reminder-history state (whether a second request was sent) is not guaranteed as a first-class preserved semantic in Phase 2. Any GF output column that currently surfaces this distinction must be identified in `FLAT_GED_ADAPTER_MAP.md` and classified as `KNOWN_GAP` if it cannot be reproduced from flat GED alone.

---

**Decision 5 — `visa_global` verification**

`visa_global` is treated as an expected near-direct mapping from flat GED's MOEX step row. Step 4 must explicitly verify three points before closing the adapter:

1. SAS REF is distinguishable from full-workflow REF in GED_OPERATIONS.
2. SAS-only approvals (`VAO-SAS`, `VSO-SAS`) do not appear in the MOEX step's `status_clean`.
3. Canonical MOEX actor name in GED_OPERATIONS matches what the GF writer expects.

Until these three points are confirmed, `visa_global` carries a pending verification status, not a confirmed pass.

---

**Decision 6 — Flat GED delay semantics are now part of the backend contract**

The flat builder's delay contribution computation (`step_delay_days`, `delay_contribution_days`, `cumulative_delay_days`) is the authoritative delay logic for the backend, replacing any prior legacy delay computation. The adapter must not bypass or recompute delay from scratch. Downstream stages that previously computed delay independently must be updated to consume flat GED delay fields directly.

---

## Summary

**Concepts documented:** 8 (Effective Response, Blocking, Cycle Closure, VISA GLOBAL, Responsible Party, Pending vs Late, SAS Semantics, Delay Contribution)

**Explicit Phase 2 decisions taken:**
1. `is_dernier_indice` proxy = `instance_role == "ACTIVE"` — accepted with submission-instance limitation
2. `responsible_party` must be synthesized by the adapter using the legacy 5-rule logic
3. Legacy SAS filter (RAPPEL + pre-2026) — **ACCEPTED (by Eid)**: adapter WILL reproduce this behavior for Phase 2 parity
4. Operational lateness is recoverable; RAPPEL reminder-history is not guaranteed
5. `visa_global` is expected near-direct mapping, pending three explicit verification points in Step 4
6. Flat GED delay semantics are now the backend contract; no recomputation in the adapter

**Unresolved risks left open for Step 4:**
- Canonical name alignment between legacy engine and flat GED for MOEX and consultant approvers (affects Concepts 4, 5)
- Whether any GF output column depends on the RAPPEL first-class state (Concept 6/7) — must be assessed per column
- SAS RAPPEL identification in flat GED requires confirming `date_status_type = "PENDING_LATE"` on the SAS row is sufficient proxy (Concept 7)
- Decision 3 (SAS filter preservation) is open until Eid decides

---

*End of BACKEND_SEMANTIC_CONTRACT.md*
