# Phase 6X â€” ACTION MOEX Data Truth Correction

**Owner:** Eid (eid.maalouf89@gmail.com)
**Created:** 2026-05-04
**Status:** VALIDATED - PHASE 6X CLOSED. Phase 6C and 6D are RESUMABLE.
**Audits this plan supersedes consolidating:**
- `outputs/PHASE_6X_0_AUDIT.md` (source-of-truth audit)
- `outputs/PHASE_6X_0B_AUDIT.md` (DCC/deadline audit, partial)
- `outputs/PHASE_6X_AB_AUDIT.md` (date.today scan; flagged inclusion-vs-display ambiguity)
- `outputs/PHASE_6X_A3_AUDIT.md` (DCC deadline truth audit, definitive)

---

## 1. Context

ACTION MOEX is the cockpit reader over `output/intermediate/COUNTER_ATTACK_ITEMS.csv`, which is built by `src/reporting/counter_attack_builder.py` from DCC tags + Chain & Onion artifacts and consumed by `src/reporting/counter_attack_query.py` (Phase 6B read API).

The artifact is mis-aligned with the validated operational truth in eight ways. The audit phase (6X.0 â†’ 6X.A3) confirmed root causes and proved the correct fix path.

---

## 2. Binding Rules (do not override)

These are user-issued and authoritative. Every implementation step must honour them.

1. **ONE chain â†’ ONE row, latest indice only.** When indice C exists, B and A are implicitly closed and not monitored. Latest-indice dedup at `counter_attack_builder.py:632-655` already enforces this â€” it must not regress.
2. **Canonical title.** Queue rows must start with the canonical contractor name (`AXIMA â€” â€¦`), not raw lot codes (`B003 / â€¦`).
3. **Queue sorting.** Each bucket sorted ascending by deadline-truth lateness; non-late items must not appear in late-action buckets.
4. **No closed chains.** VAO/VSO chains are excluded; REF only routes to ENTREPRISE_A_RELANCER when contractor resubmission is expected.
5. **No non-MOEX workflows in MOEX buckets.** If MOEX is not the current blocker, the row is excluded from FERMER_MAINTENANT, DECISION_MOEX, MOEX_SHAME_INTERNAL.
6. **Consultants Ã  relancer = deadline truth, not chain dwell.** Use DCC `responses[n].deadline` and `responses[n].is_open` against `ctx.data_date`. **NO threshold (5/10/15/30 days). NO `CHAIN_METRICS.{primary,secondary}_wait_days` as consultant lateness. NO `today()`.**
7. **Entreprises Ã  relancer = tag/state consistency.** `current_state == "WAITING_CORRECTED_INDICE"` AND DCC primary_tag indicates contractor-owned action AND no other actor is currently blocking AND `emetteur_name` non-empty.
8. **MOEX interne â€” exposition = strict four signals.** MOEX is current blocker; primary/secondary at 0; `moex_wait_days > 100`; DCC primary_tag in `{Att MOEX â€” Facile, Att MOEX â€” Arbitrage}`. CHRONIC_REF_CHAIN path dropped.
9. **`data_date` is the GED export snapshot date.** Every business lateness/deadline/countdown evaluation uses `ctx.data_date`. NEVER `date.today()`, `datetime.now()`, `pd.Timestamp.now()`, cache `generated_at`, or system runtime date. UI display fallbacks are tolerated; business logic is not.
10. **Reuse what already exists.** No new lifecycle truth. No parallel models. No new helpers in chain_onion. The DCC functions already compute deadline truth â€” expose what they compute, don't reinvent.

---

## 3. Confirmed Truths (established by audits)

| Fact | Source |
|---|---|
| Current GED export `data_date = 2026-04-10` | Raw GED Excel "DÃ©tails" sheet, cell `[15,4]`, loaded by `data_loader.py:340-402` (`_read_ged_data_date`) |
| Prior audits' `2026-05-04` was wrong â€” it was the FLAT_GED cache `generated_at` field, not the business data_date | `FLAT_GED_cache_meta.json` |
| 133005 indice C: BET primaire Ã©chÃ©ance = `2026-04-17`, all 5 primary consultants have `is_open=True`, `response_date=None`, **7 days remaining**, NOT LATE | `build_document_command_center(ctx, "133005", "C")` reproduction |
| Latest-indice dedup is working (0 duplicate `family_key` in current 1,869-row artifact) | `counter_attack_builder.py:632-655` |
| Implicit closure of B by C: dernier_df contains A/B/C; latest-indice dedup keeps only C | confirmed via reproduction |
| DCC deadline truth lives in `responses[n].deadline` (raw `date_limite` from responses_df) and `responses[n].is_open` boolean | `document_command_center.py:237-271` (`_get_latest_responses_for_doc`) |
| Bug location for wrong `days_late=15` on 133005 C: `counter_attack_builder.py:728` writes `stale_days` (chain dwell), not consultant deadline lateness | `counter_attack_builder.py:728` |
| **Two date.today() business-impacting fallbacks confirmed** | `consultant_fiche.py:1255` (final fallback in `_resolve_data_date`); `contractor_quality.py:322` and `:452` (silent `or date.today()`) |
| **Safe (uses data_date correctly):** DCC, all of `chain_onion/`, `counter_attack_builder.py`, `focus_ownership.py`, `pipeline/compute.py` (uses are non-business-impacting), `ui_adapter.py:92` (display-only) | grep audit |

---

## 4. Source-of-Truth Mapping

| Bucket | Current source | Correct source | Required change |
|---|---|---|---|
| FERMER_MAINTENANT (VISA facile) | `primary_tag == "Att MOEX â€” Facile"` | Same + chain-state guard: `current_state == "OPEN_WAITING_MOEX"` AND `moex_wait_days > 0` | Add chain-state gate to `_assign_bucket` |
| DECISION_MOEX (Arbitrage) | `primary_tag == "Att MOEX â€” Arbitrage"` | Same guard | Add gate |
| MOEX_SHAME_INTERNAL | `current_state == "CHRONIC_REF_CHAIN"` OR `(L5 âˆ§ stale>30)` | Drop CHRONIC path. Require: `focus_owner_tier == "MOEX"` AND `current_state == "OPEN_WAITING_MOEX"` AND `moex_wait_days > 100` AND `primary_wait_days == 0` AND `secondary_wait_days == 0` AND `primary_tag in {Att MOEX â€” Facile, Att MOEX â€” Arbitrage}` | Replace predicate |
| ENTREPRISE_A_RELANCER | `current_state == "WAITING_CORRECTED_INDICE"` OR `primary_tag in {"Att Entreprise â€” â€¦"}` | Tag/state consistency. Require: `current_state == "WAITING_CORRECTED_INDICE"` AND `primary_tag` is contractor-owned AND no MOEX/BET wait > 0 AND `emetteur_name` non-empty | Tighten predicate |
| CONSULTANT_A_ATTAQUER | `primary_tag in {"Att BET Primaire", "Att BET Secondaire"}` | Same + deadline gate: at least one open consultant response has `deadline < ctx.data_date` | Add deadline gate via DCC truth |
| SECONDAIRE_EXPIRE | `"Secondaire expirÃ©" in secondary_tags` | Same | No change |
| SUJET_REUNION | `escalation_flag âˆ§ urgency_label âˆˆ {CRITICAL, HIGH}` | Same | No change |

`days_late` field for the row (used by 6B sort and display): for **consultant rows**, derive from DCC deadline truth (`max(0, (data_date âˆ’ earliest_open_consultant_deadline).days)`); for **MOEX rows**, use `moex_wait_days`; for **entreprise rows**, keep current semantics. Currently all rows use chain `stale_days` â€” that is the bug at line 728.

---

## 5. Forbidden Patterns

Any implementation step that produces these is rejected:

- `primary_wait_days > N` or `secondary_wait_days > N` as a consultant-lateness gate
- Any 5/10/15/30-day threshold for consultant lateness
- `date.today()`, `datetime.today()`, `datetime.now()`, `pd.Timestamp.today()`, `pd.Timestamp.now()` in business logic paths
- Use of FLAT_GED cache `generated_at` as `data_date`
- New deadline computation in `counter_attack_builder.py` (must reuse DCC)
- Changes to `chain_onion/`
- Changes to React UI lifecycle / filtering for ACTION MOEX (UI must reflect backend truth only)
- Silent fallback chains for `data_date` (must raise loudly)

---

## 6. Execution DAG

```
                        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                        â”‚ 6X.B2 caller audit (read-only)     â”‚
                        â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                         â”‚
                â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
                â–¼                        â–¼                        â”‚
       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”             â”‚
       â”‚ 6X.C consultant_   â”‚  â”‚ 6X.D contractor_   â”‚             â”‚
       â”‚ fiche.py:1255 fix  â”‚  â”‚ quality.py:322,452 â”‚             â”‚
       â”‚ (raise instead of  â”‚  â”‚ fix (raise instead â”‚             â”‚
       â”‚ today fallback)    â”‚  â”‚ of today fallback) â”‚             â”‚
       â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜             â”‚
                â”‚                        â”‚                        â”‚
                â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                        â”‚
                             â–¼                                    â”‚
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”            â”‚
            â”‚ 6X.E extend compute_dcc_tags_bulk()    â”‚            â”‚
            â”‚ with consultant_days_remaining +       â”‚            â”‚
            â”‚ min_open_consultant_deadline columns   â”‚            â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜            â”‚
                             â”‚                                    â”‚
                             â–¼                                    â–¼
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚ 6X.F1 builder: expand CHAIN_METRICS    â”‚  â”‚ (parallel: docs &   â”‚
            â”‚ merge to bring in moex_wait_days,      â”‚  â”‚ 6X.J query layer    â”‚
            â”‚ primary_wait_days, secondary_wait_days â”‚  â”‚ when 6X.G is done)  â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â–¼
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚ 6X.F2 builder: MOEX bucket gates       â”‚
            â”‚ (FERMER_MAINTENANT, DECISION_MOEX,     â”‚
            â”‚ MOEX_SHAME_INTERNAL)                   â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â–¼
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚ 6X.F3 builder: ENTREPRISE_A_RELANCER   â”‚
            â”‚ tag/state consistency gate             â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â–¼
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚ 6X.F4 builder: CONSULTANT_A_ATTAQUER   â”‚
            â”‚ deadline-truth gate (uses 6X.E column) â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â–¼
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚ 6X.G builder line 728: per-bucket      â”‚
            â”‚ days_late derivation                   â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â–¼
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚ 6X.J counter_attack_query.py: sort by  â”‚
            â”‚ days_late ASC + canonical title format â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â–¼
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚ 6X.K rebuild artifact + diagnostics    â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â–¼
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚ 6X.L manual app smoke (USER GATE)      â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                             â–¼
            â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
            â”‚ 6X.M update context docs               â”‚
            â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

**Parallel pairs:**
- `6X.C` âˆ¥ `6X.D` (different files, same dependency)
- `6X.M` documentation may be drafted in parallel with `6X.L` smoke (but only finalised after smoke passes)

**Serial chain (no parallelism â€” all touch `counter_attack_builder.py`):**
- `6X.F1 â†’ 6X.F2 â†’ 6X.F3 â†’ 6X.F4 â†’ 6X.G`. Sequential to avoid edit conflicts.

**Stop gates (autonomous execution must HALT and wait for user):**
- After `6X.B2` â€” review caller audit before removing fallbacks.
- After `6X.E` â€” review the new DCC bulk columns before consuming them.
- After `6X.F2` â€” review MOEX bucket count diff (large bucket-population change expected).
- After `6X.F4` â€” verify 133005 C is now excluded from CONSULTANT_A_ATTAQUER.
- After `6X.K` â€” review diagnostics before manual smoke.
- After `6X.L` â€” user manual smoke is the final gate before docs are committed.

---

## 7. Steps

Each step below is dispatchable to a Claude Code agent (general-purpose) with the listed model and prompt scope. All paths absolute under the project root unless noted.

### Step 6X.B2 â€” Caller audit for `_resolve_data_date`

- **Subagent:** `general-purpose`
- **Model / effort:** Sonnet / medium
- **Why this model:** Cross-file trace (call sites of `_resolve_data_date` + upstream `RunContext` construction). Read-only.
- **Dependencies:** none
- **Parallelizable with:** none (this gate must complete first)
- **Stop gate after:** YES â€” user reviews before 6X.C/6X.D
- **Files to READ:**
  - `src/reporting/consultant_fiche.py` (around lines 164, 324, 1250â€“1258)
  - `src/reporting/contractor_quality.py:322,452`
  - `src/reporting/data_loader.py` (RunContext construction; trace `data_date` setter)
  - `app.py`, `main.py`, `scripts/*.py` â€” every entry point that builds a `RunContext`
- **Files to MODIFY:** none
- **Files FORBIDDEN:** any project file
- **Output:** `outputs/PHASE_6X_B2_CALLER_AUDIT.md` listing every call site, whether `ctx.data_date` can be `None`, whether path is business-impacting, recommended safe-fix shape (raise vs. require ctx-arg)
- **Validation:** the audit document is reviewed by user
- **Risk:** LOW

---

### Step 6X.C â€” Fix `consultant_fiche.py:1255` final fallback to `date.today()`

- **Subagent:** `general-purpose`
- **Model / effort:** Sonnet / medium
- **Why this model:** Small deterministic change with regression risk if upstream callers don't always provide `data_date`. The 6X.B2 audit informs whether to raise or to require an explicit param.
- **Dependencies:** 6X.B2
- **Parallelizable with:** 6X.D (different file)
- **Stop gate after:** NO (paired with 6X.D)
- **Files to READ:** `src/reporting/consultant_fiche.py`, 6X.B2 audit findings
- **Files to MODIFY:** `src/reporting/consultant_fiche.py:1250-1258` only
- **Files FORBIDDEN:** any other file
- **Change shape (description, not code):** Replace the chain `ctx.data_date â†’ ctx.run_date â†’ date.today()` with: prefer `ctx.data_date`; if absent, prefer parsed `ctx.run_date` and **log CRITICAL**; if both absent, **`raise ValueError("data_date required for consultant lateness; ctx.data_date and ctx.run_date are both unavailable")`**. Remove the silent `date.today()` final branch.
- **Validation:** unit test `tests/test_consultant_fiche.py::test_resolve_data_date_raises_when_both_missing` (new); existing test suite must still pass.
- **Risk:** MEDIUM â€” caller paths must always supply `data_date` after this change (6X.B2 verifies).

---

### Step 6X.D â€” Fix `contractor_quality.py:322,452` silent fallback

- **Subagent:** `general-purpose`
- **Model / effort:** Sonnet / medium
- **Why this model:** Same shape as 6X.C; deterministic.
- **Dependencies:** 6X.B2
- **Parallelizable with:** 6X.C (different file)
- **Stop gate after:** NO
- **Files to READ:** `src/reporting/contractor_quality.py`, 6X.B2 audit findings
- **Files to MODIFY:** `src/reporting/contractor_quality.py:322` and `:452` only
- **Files FORBIDDEN:** any other file
- **Change shape:** Replace `ref_today = ctx.data_date or date.today()` (both occurrences) with explicit None check that raises `ValueError("data_date required for dormant REF computation")`. Remove silent fallback.
- **Validation:** unit test `tests/test_contractor_quality.py::test_dormant_ref_raises_when_data_date_missing` (new); existing tests pass.
- **Risk:** MEDIUM.

---

### Step 6X.E â€” Extend `compute_dcc_tags_bulk()` with deadline-truth columns

- **Subagent:** `general-purpose`
- **Model / effort:** Sonnet / medium
- **Why this model:** Additive change to a core DCC function. Must reuse `_get_latest_responses_for_doc`-equivalent logic at the bulk layer. No new business logic â€” only exposing what DCC already computes per-doc, vectorised.
- **Dependencies:** 6X.C (data_date guaranteed valid)
- **Parallelizable with:** none (DCC is the upstream of every builder gate)
- **Stop gate after:** YES â€” user reviews bulk output schema before downstream consumes it
- **Files to READ:**
  - `src/reporting/document_command_center.py` (especially `_get_latest_responses_for_doc:237-271`, `compute_dcc_tags_bulk:551-627`)
  - `src/reporting/counter_attack_builder.py` (so the new columns match the merge contract)
- **Files to MODIFY:** `src/reporting/document_command_center.py` (add columns to `compute_dcc_tags_bulk` output)
- **Files FORBIDDEN:** `chain_onion/`, all other reporting modules
- **Change shape:** Add two columns to the DataFrame returned by `compute_dcc_tags_bulk(ctx)`:
  - `min_open_consultant_deadline` â€” earliest `deadline` across all `responses` rows where `is_open == True` for that doc; `NaT` if none. Vectorised via groupby on `doc_id` over `responses_df`, filtered on `is_open` derived from `status_clean` per the existing rule.
  - `consultant_days_remaining` â€” `(min_open_consultant_deadline âˆ’ ctx.data_date).days`; `None` if `min_open_consultant_deadline` is `NaT`. Negative values mean "late by N days".
- **Validation:**
  - Reproduction test: for `(numero=133005, indice=C)`, `min_open_consultant_deadline == date(2026, 4, 17)` and `consultant_days_remaining == 7`.
  - Existing DCC tests must still pass.
  - New unit test `tests/test_document_command_center.py::test_compute_dcc_tags_bulk_deadline_columns`.
- **Risk:** MEDIUM â€” DCC is core; additive but touched.

---

### Step 6X.F1 â€” Builder: expand CHAIN_METRICS merge

- **Subagent:** `general-purpose`
- **Model / effort:** Sonnet / medium
- **Why this model:** Small, deterministic merge expansion.
- **Dependencies:** 6X.E
- **Parallelizable with:** none (sequential builder edits to avoid conflicts)
- **Stop gate after:** NO
- **Files to READ:** `src/reporting/counter_attack_builder.py:570-620`, `output/chain_onion/CHAIN_METRICS.csv` columns
- **Files to MODIFY:** `src/reporting/counter_attack_builder.py` â€” the chain_metrics merge (currently brings in `open_days` and `stale_days` only at line 589). Expand to also include `moex_wait_days`, `primary_wait_days`, `secondary_wait_days`.
- **Change shape:** Add three columns to the columns-list slice on the chain_metrics DataFrame, then rely on the existing `merge(on="numero", how="left")`.
- **Validation:** rebuild artifact (`python scripts/build_counter_attack.py`); confirm new columns exist in the in-memory `merged` frame; no regressions in row count.
- **Risk:** LOW.

---

### Step 6X.F2 â€” Builder: MOEX bucket gates

- **Subagent:** `general-purpose`
- **Model / effort:** Sonnet / medium
- **Why this model:** Predicate edits in `_assign_bucket`; deterministic.
- **Dependencies:** 6X.F1
- **Parallelizable with:** none
- **Stop gate after:** YES â€” user reviews bucket-count diff
- **Files to READ:** `src/reporting/counter_attack_builder.py:162-233` (`_assign_bucket`)
- **Files to MODIFY:** `src/reporting/counter_attack_builder.py:_assign_bucket`
- **Change shape:**
  - **FERMER_MAINTENANT:** require `primary_tag == "Att MOEX â€” Facile"` AND `current_state == "OPEN_WAITING_MOEX"` AND `moex_wait_days > 0`.
  - **DECISION_MOEX:** require `primary_tag == "Att MOEX â€” Arbitrage"` AND `current_state == "OPEN_WAITING_MOEX"` AND `moex_wait_days > 0`.
  - **MOEX_SHAME_INTERNAL:** drop the `current_state == "CHRONIC_REF_CHAIN"` branch entirely. New predicate: `focus_owner_tier == "MOEX"` AND `current_state == "OPEN_WAITING_MOEX"` AND `moex_wait_days > 100` AND `primary_wait_days == 0` AND `secondary_wait_days == 0` AND `primary_tag in {"Att MOEX â€” Facile", "Att MOEX â€” Arbitrage"}`.
- **Validation:**
  - Document 128000: must NOT appear in any MOEX bucket.
  - MOEX_SHAME_INTERNAL count: ~50 CHRONIC_REF_CHAIN rows removed; ~18â€“20 retained.
  - No row in any MOEX bucket has `current_state != "OPEN_WAITING_MOEX"`.
- **Risk:** HIGH â€” bucket population shifts.

---

### Step 6X.F3 â€” Builder: ENTREPRISE_A_RELANCER tag/state consistency gate

- **Subagent:** `general-purpose`
- **Model / effort:** Sonnet / medium
- **Why this model:** Predicate edit; deterministic.
- **Dependencies:** 6X.F2
- **Parallelizable with:** none
- **Stop gate after:** NO
- **Files to READ:** `src/reporting/counter_attack_builder.py:_assign_bucket` (current rule lines 212â€“215)
- **Files to MODIFY:** `src/reporting/counter_attack_builder.py:_assign_bucket`
- **Change shape:** Require ALL of:
  - `current_state == "WAITING_CORRECTED_INDICE"`
  - `primary_tag` indicates contractor action (e.g., in `{"Att Entreprise â€” Dans les dÃ©lais", "Att Entreprise â€” Hors dÃ©lais"}`) â€” must NOT be `Att MOEX â€” *` or `Att BET *`
  - `primary_wait_days == 0` AND `secondary_wait_days == 0` AND `moex_wait_days == 0` (no other actor currently blocking)
  - `emetteur_name` non-empty (no NaN MOEX rows)
- **Validation:**
  - No row in ENTREPRISE_A_RELANCER has `actor_to_call` empty/NaN.
  - No row has DCC `primary_tag` contradicting contractor-owned action.
  - Bucket size remains in the same order of magnitude (~250 rows; Â±50 acceptable).
- **Risk:** MEDIUM.

---

### Step 6X.F4 â€” Builder: CONSULTANT_A_ATTAQUER deadline-truth gate

- **Subagent:** `general-purpose`
- **Model / effort:** Sonnet / medium
- **Why this model:** Predicate edit using new column from 6X.E.
- **Dependencies:** 6X.F3, 6X.E
- **Parallelizable with:** none
- **Stop gate after:** YES â€” verify 133005 C now excluded
- **Files to READ:** `src/reporting/counter_attack_builder.py:_assign_bucket` (current rule lines 226â€“227)
- **Files to MODIFY:** `src/reporting/counter_attack_builder.py:_assign_bucket`
- **Change shape:** Require BOTH:
  - `primary_tag in {"Att BET Primaire", "Att BET Secondaire"}` (existing)
  - `consultant_days_remaining is not None AND consultant_days_remaining <= 0` (the new column from 6X.E â€” at least one open consultant deadline has passed relative to `ctx.data_date`)
- **Validation:**
  - **133005 C:** must NOT appear in CONSULTANT_A_ATTAQUER (its `consultant_days_remaining = 7`).
  - For every row that survives in the bucket, `consultant_days_remaining <= 0`.
  - Bucket size drops by ~50â€“80 rows (rough estimate; reproduce after run).
- **Risk:** MEDIUM.

---

### Step 6X.G â€” Builder: per-bucket `days_late` derivation at line 728

- **Subagent:** `general-purpose`
- **Model / effort:** Sonnet / medium
- **Why this model:** Branch on `bucket` to derive `days_late` from the right field.
- **Dependencies:** 6X.F4
- **Parallelizable with:** none
- **Stop gate after:** NO
- **Files to READ:** `src/reporting/counter_attack_builder.py` row construction (line 728 area)
- **Files to MODIFY:** `src/reporting/counter_attack_builder.py:728`
- **Change shape:** Replace the single `_safe_int(row.get("stale_days"), 0)` with a bucket-aware derivation:
  - CONSULTANT_A_ATTAQUER â†’ `max(0, -consultant_days_remaining)` (positive = days late)
  - FERMER_MAINTENANT, DECISION_MOEX, MOEX_SHAME_INTERNAL, SECONDAIRE_EXPIRE â†’ `moex_wait_days`
  - ENTREPRISE_A_RELANCER â†’ keep `stale_days` (chain dwell is the right semantic for "days waiting on contractor since REF")
  - SUJET_REUNION â†’ keep `stale_days`
- **Validation:** for 133005 C (if it had still been in CONSULTANT_A_ATTAQUER, which it won't be), `days_late` would be 0; for retained MOEX_SHAME_INTERNAL rows, `days_late > 100`.
- **Risk:** MEDIUM.

---

### Step 6X.J â€” Query layer: sort + canonical title

- **Subagent:** `general-purpose`
- **Model / effort:** Sonnet / medium
- **Why this model:** Adapter-layer changes only, no new truth.
- **Dependencies:** 6X.G
- **Parallelizable with:** 6X.K diagnostics drafting (optional)
- **Stop gate after:** NO
- **Files to READ:** `src/reporting/counter_attack_query.py:_row_to_queue_row`, `get_counter_attack_queue`
- **Files to MODIFY:** `src/reporting/counter_attack_query.py`
- **Change shape:**
  - In `get_counter_attack_queue`: sort `sub` by `days_late` ascending before `head(limit_int)`; null/blank `days_late` last (e.g., `sub = sub.sort_values("days_late", ascending=True, na_position="last")`).
  - In `_row_to_queue_row`: build a display title field (e.g., `subject_label_display`) as `f"{emetteur_name} â€” {libelle_clean}"` where `libelle_clean` strips the leading `lot /` prefix. The artifact `subject_label` column stays unchanged (no migration); only the queue payload gets the canonical form.
  - Replace the row's `subject_label` in the queue payload with `subject_label_display`.
- **Validation:**
  - First 50 rows of every bucket: `days_late` non-decreasing.
  - First 50 titles of every bucket: start with canonical contractor name + " â€” " (no `B003 /`, `B12B /`, `A035 /` prefixes visible in queue rows).
  - `get_counter_attack_item(item_id)` is unaffected (artifact columns unchanged).
- **Risk:** LOW.

---

### Step 6X.K â€” Rebuild artifact + diagnostics

- **Subagent:** `general-purpose`
- **Model / effort:** Haiku / low
- **Why this model:** Mechanical script run + read-only diagnostic queries.
- **Dependencies:** 6X.J
- **Parallelizable with:** none
- **Stop gate after:** YES â€” review diagnostics before user smoke
- **Files to READ:** `output/intermediate/COUNTER_ATTACK_ITEMS.csv` (post-rebuild)
- **Files to MODIFY:** none (artifact regenerated by the script)
- **Commands to run:**
  ```bash
  python scripts/build_counter_attack.py
  ```
- **Validation queries (all must pass):**
  1. Duplicate `family_key` count = 0
  2. Duplicate `(numero, indice)` count = 0
  3. No row with `current_state` in `{"CLOSED_VAO", "CLOSED_VSO", "DEAD_AT_SAS_A", "ABANDONED_CHAIN", "VOID_CHAIN", "UNKNOWN_CHAIN_STATE"}`
  4. Numero 128000: not in FERMER_MAINTENANT, DECISION_MOEX, or MOEX_SHAME_INTERNAL
  5. Numero 133005 indice C: not in CONSULTANT_A_ATTAQUER
  6. Every CONSULTANT_A_ATTAQUER row: `consultant_days_remaining <= 0` (or equivalent â€” DCC says late)
  7. Every MOEX bucket row: `current_state == "OPEN_WAITING_MOEX"` AND `moex_wait_days > 0`
  8. Every MOEX_SHAME_INTERNAL row: `moex_wait_days > 100`
  9. Every ENTREPRISE_A_RELANCER row: `current_state == "WAITING_CORRECTED_INDICE"` AND `actor_to_call != ""`
  10. API smoke: `get_counter_attack_home()`, `get_counter_attack_queue("FERMER_MAINTENANT", 50)`, `get_counter_attack_item(item_id)` return non-error payloads. Queue rows sorted by `days_late` ascending. Queue titles start with canonical contractor name.
- **Output:** `outputs/PHASE_6X_K_DIAGNOSTICS.md` with bucket counts before/after, all 10 validation results, sample 5 rows per bucket.
- **Risk:** LOW.

---

### Step 6X.L â€” Manual app smoke (USER GATE)

- **Subagent:** N/A â€” user runs `python app.py`
- **Model / effort:** N/A
- **Why this gate:** Per project rule "DO NOT run the full app inside Cowork unless explicitly authorized" + RULE 1 "the app must always run".
- **Dependencies:** 6X.K
- **Parallelizable with:** 6X.M draft (docs may be drafted but not finalised)
- **Stop gate after:** YES â€” autonomous execution must HALT until user replies
- **User checklist:**
  - App boots without error.
  - Overview / Consultants / Contractors pages render.
  - ACTION MOEX page opens; all 7 bucket cards render.
  - Bucket counts plausible vs. diagnostics output.
  - Drilldown into ACTION MOEX queues: rows sorted by deadline-truth lateness ascending; titles start with canonical contractor name.
  - 133005 C not visible in Consultants Ã  relancer.
  - 128000 not visible in any MOEX bucket.
  - DCC drilldown opens correct latest indice (C for 133005, etc.).
- **Output:** user reply (approve / reject) in chat.
- **Risk:** gate.

---

### Step 6X.M â€” Update context docs

- **Subagent:** `general-purpose`
- **Model / effort:** Haiku / low
- **Why this model:** Pure documentation.
- **Dependencies:** 6X.L approved
- **Parallelizable with:** none
- **Stop gate after:** NO (final step)
- **Files to MODIFY:**
  - This file (`docs/implementation/PHASE_6X_ACTION_MOEX_DATA_TRUTH_CORRECTION.md`) â€” mark Status: COMPLETE; append "Final Return Package" section with measured before/after counts.
  - `context/03_UI_FEED_MAP.md` â€” note the new `consultant_days_remaining` field in the DCC-bulk â†’ builder feed.
  - `context/05_OUTPUT_ARTIFACTS.md` â€” note the change in `days_late` semantics per bucket.
  - `context/06_EXCEPTIONS_AND_MAPPINGS.md` â€” record the bucket gate predicates (DCC tag + chain state + wait-days).
  - `context/07_OPEN_ITEMS.md` â€” close items related to ACTION MOEX data truth.
  - `context/12_LESSONS_LEARNED.md` â€” add the data_date / cache `generated_at` confusion as a lesson.
- **Files FORBIDDEN:** any source code file
- **Validation:** files exist; cross-links from `PHASE_6_COUNTER_ATTACK_MASTER.md` updated to point to this doc; phase 6C/6D docs annotated as "PAUSED until 6X complete" (now updated to "RESUMABLE").
- **Risk:** LOW.

---

## 8. Validation Commands (full set)

Run after every step that touches code, before the next step is dispatched.

```bash
# Lint / static check (project standard, exact command per repo conventions)
python -m pyflakes src/reporting/counter_attack_builder.py
python -m pyflakes src/reporting/counter_attack_query.py
python -m pyflakes src/reporting/document_command_center.py

# Unit tests (only the modules touched in this phase)
pytest tests/test_consultant_fiche.py -xvs
pytest tests/test_contractor_quality.py -xvs
pytest tests/test_document_command_center.py -xvs
pytest tests/test_counter_attack_builder.py -xvs
pytest tests/test_counter_attack_query.py -xvs

# Artifact rebuild (ACTION MOEX only â€” does NOT trigger full pipeline)
python scripts/build_counter_attack.py

# Read-only diagnostics on the rebuilt artifact
python -c "
import pandas as pd
df = pd.read_csv('output/intermediate/COUNTER_ATTACK_ITEMS.csv', dtype={'numero': str, 'indice': str, 'family_key': str})
print('rows:', len(df))
print('duplicate family_key:', df.duplicated(subset=['family_key']).sum())
print('duplicate (numero,indice):', df.duplicated(subset=['numero','indice']).sum())
print('128000 in MOEX buckets:', df[(df['numero']=='128000') & (df['action_bucket'].isin(['FERMER_MAINTENANT','DECISION_MOEX','MOEX_SHAME_INTERNAL']))].shape[0])
print('133005 C in CONSULTANT_A_ATTAQUER:', df[(df['numero']=='133005') & (df['indice']=='C') & (df['action_bucket']=='CONSULTANT_A_ATTAQUER')].shape[0])
print('bucket counts:')
print(df['action_bucket'].value_counts())
"

# API smoke
python -c "
from src.reporting.counter_attack_query import get_counter_attack_home, get_counter_attack_queue, get_counter_attack_item
import json
print('home:', json.dumps(get_counter_attack_home()['summary'], indent=2))
for b in ['FERMER_MAINTENANT','DECISION_MOEX','CONSULTANT_A_ATTAQUER','ENTREPRISE_A_RELANCER','MOEX_SHAME_INTERNAL']:
    q = get_counter_attack_queue(b, 5)
    print(f'{b}: count={q[\"count\"]} sample_titles={[r[\"subject_label\"] for r in q[\"rows\"]]}')
"

# Verify no business-impacting today/now usage remains
grep -nE 'date\.today|datetime\.today|datetime\.now|pd\.Timestamp\.today|pd\.Timestamp\.now' \
  src/reporting/counter_attack_builder.py \
  src/reporting/counter_attack_query.py \
  src/reporting/document_command_center.py \
  src/reporting/consultant_fiche.py \
  src/reporting/contractor_quality.py \
  src/reporting/focus_ownership.py \
  src/reporting/data_loader.py \
  src/reporting/chain_timeline_attribution.py
# Expected: only display-only fallbacks (ui_adapter.py:92) and metadata timestamps (consultant_report_builder.py:147) remain. No business-logic occurrences in the listed files.
```

---

## 9. Rollback

If any step's validation fails:

1. The agent halts at the failing step's stop gate (no auto-progression).
2. The user is shown the diagnostic output and the failing assertion.
3. To roll back a code change: `git checkout HEAD -- <file>` for the specific file. The artifact regenerates automatically on the next `scripts/build_counter_attack.py` run.
4. No upstream pipeline state is touched; `chain_onion/` is never modified.

A full session rollback is `git reset --hard <commit-before-6X>`. The user keeps full control.

---

## 10. Final Return Package

**Final status:** VALIDATED - PHASE 6X CLOSED.

**Authorship note:** Cowork managed the initial audits and step planning for
Phase 6X. After the `src/reporting/counter_attack_builder.py` truncation
incident, final recovery/reconstruction and R1/R2/R3 validation were completed
by Codex.

**Files changed during closure path:**
- `src/reporting/counter_attack_builder.py` - reconstructed builder and R2-C routing refinement.
- `src/reporting/document_command_center.py` - DCC bulk deadline split fields.
- `tests/test_document_command_center.py` - targeted tests for DCC split deadline truth.
- `output/intermediate/COUNTER_ATTACK_ITEMS.csv` - regenerated ACTION MOEX artifact.
- `output/intermediate/COUNTER_ATTACK_ITEMS.PRE_R3_BACKUP.csv` - pre-R3 backup of the prior artifact.

**Bucket counts before vs. after R3:**

| Bucket | Before | After |
|---|---:|---:|
| `FERMER_MAINTENANT` | 1001 | 66 |
| `CONSULTANT_A_ATTAQUER` | 319 | 210 |
| `ENTREPRISE_A_RELANCER` | 269 | 122 |
| `DECISION_MOEX` | 209 | 8 |
| `MOEX_SHAME_INTERNAL` | 71 | 989 |
| `SECONDAIRE_EXPIRE` | 0 | 129 |
| `SUJET_REUNION` | 0 | 0 |

**R3 artifact validation:**
- Rows: 1524.
- 28 columns exactly.
- Duplicate `family_key`: 0.
- Duplicate `(numero, indice)`: 0.
- Terminal/unknown states: 0.
- Forbidden label `"Honte MOEX"`: absent.
- `133005 C`: absent from artifact and not in `CONSULTANT_A_ATTAQUER`.
- `128000`: `MOEX_SHAME_INTERNAL`, `days_late=741`, matching `secondary_wait_days=741`.
- `CONSULTANT_A_ATTAQUER`: 210 rows; every row has deadline-truth lateness (`primary_consultant_days_remaining < 0` or trusted `consultant_days_remaining < 0`).
- `SECONDAIRE_EXPIRE`: 129 rows; every row has `30 < secondary_wait_days <= 100`.
- `MOEX_SHAME_INTERNAL`: 989 rows; 969 from secondary backlog >100, 20 from direct MOEX wait >100, 0 other.

**6B read API smoke:**
- `get_counter_attack_home()` returned `available=True`, `total_today=1524`.
- `get_counter_attack_queue()` returned available payloads for all 7 buckets.
- `get_counter_attack_item()` returned `found=True` for one sample item from every non-empty bucket.

**Manual app smoke:** not run in this closure step. Phase 6C remains resumable,
but UI changes were not part of this phase closure.

---

## 11. Phase 6C / 6D Status

Phase 6X is closed.

- Phase 6C is **resumable**. It must consume the corrected `COUNTER_ATTACK_ITEMS.csv` and the existing Phase 6B read payloads.
- Phase 6D is **resumable** but requires Phase 6C to land first.
- The earlier freeze on 6C.6 is lifted.

---

## 12. Audit Trail

| Audit | File | Date | Outcome |
|---|---|---|---|
| 6X.0 â€” Source-of-truth audit | `outputs/PHASE_6X_0_AUDIT.md` | 2026-05-04 | Confirmed reusable: DCC, contractor name resolver. Flagged: no `build_ref_en_attente()` exists; no `get_consultant_remaining_days()` exists; no "MOEX called" boolean. |
| 6X.0B â€” DCC/deadline audit | `outputs/PHASE_6X_0B_AUDIT.md` | 2026-05-04 | Hypothesised data_date drift; proposed wait_days threshold (REJECTED by user). |
| 6X.A/B â€” Date.today scan + reproduction attempt | `outputs/PHASE_6X_AB_AUDIT.md` | 2026-05-04 | Confirmed 4 `date.today()` business-impacting fallbacks; failed to reproduce 133005 C (used wrong dernier_df); recommended wait_days again (REJECTED). |
| 6X.A3 â€” DCC deadline truth audit | `outputs/PHASE_6X_A3_AUDIT.md` | 2026-05-04 | Definitive. Confirmed `data_date=2026-04-10`. Reproduced 133005 C: deadline 17/04/2026, 7 days remaining, NOT LATE. Located bug at builder line 728. Identified DCC `responses[n].deadline + is_open` as the correct field. Confirmed prior `2026-05-04` was FLAT_GED cache `generated_at`. |
| R1/R2/R3 recovery and closure | chat return packages | 2026-05-04 | Codex reconstructed `counter_attack_builder.py` after truncation, added DCC primary/secondary deadline split fields, regenerated `COUNTER_ATTACK_ITEMS.csv`, and validated schema, bucket gates, 133005 C, 128000, and 6B read API smoke. |

---

**End of plan.**

