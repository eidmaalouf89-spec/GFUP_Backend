# OPERATIONAL DASHBOARD — REDESIGN CONTRACT

Status: Phase 0 lock. Author date: 2026-05-07.

---

## 1. Operational universe

**Definition:** Latest indice only (one row per `numero`); terminal/closed
documents excluded; `ARCHIVED_HISTORICAL` portfolio bucket excluded; stale
(>90 days since last activity) **INCLUDED** as a visible segment of old
operational debt — stale is NOT excluded.

**Source frame:** `ctx.dernier_df` exclusively. No other data frame is
a valid source of operational rows.

**Operational mask:** `portfolio_bucket in {"LIVE_OPERATIONAL", "LEGACY_BACKLOG"}`.
This mask already excludes terminal states and `ARCHIVED_HISTORICAL`; no
additional state filter is required.

**Stale threshold:** 90 days (constant; matches the threshold used by
`focus_filter.py` `apply_focus_filter`). The field tested is
`_days_since_last_activity`.

**Fresh sub-segment:** operational rows where `_days_since_last_activity <= 90`.

**Stale sub-segment:** operational rows where `_days_since_last_activity > 90`.
These rows represent old open operational debt and are surfaced visibly, never
hidden.

---

## 2. Historical / performance universe

**Scope:** all indices (not just the latest); chain timeline; onion evidence
per layer; delay and no-show statistics; audit, evidence, and revision
history.

**Owner:** Chain+Onion (`src/chain_onion/`) + Document Command Center
(`src/reporting/document_command_center.py`).

**Location:** NOT in the operational dashboard. Historical / performance
intelligence lives in the Chain+Onion panel, DCC Chronologie section, and
related read-only analytical screens.

**Boundary rule:** any count or metric that requires reading non-latest
indices, closed chains, or the full `docs_df` / `responses_df` history
belongs to the historical universe, not the operational dashboard.

---

## 3. Baseline counts (acceptance baseline 2026-05-07 — LOCKED)

These counts are the acceptance baseline for the operational dashboard.
They are locked. No phase may adjust them. If an implementation returns
a different value, the implementation must stop and report — it must NOT
"correct" this table.

| Field | Value |
|---|---|
| `operational_total` | 2,460 |
| `fresh_total` | 927 |
| `stale_total` | 1,533 |
| `moex_total` | 1,711 |
| `moex_fresh` | 505 |
| `moex_stale` | 1,206 |
| `primary_total` | 670 |
| `secondary_total` | 79 |
| `consultants_total` | 749 |
| `priority_p1` (no stale exclusion) | 2,095 |
| `priority_p2` | 13 |
| `priority_p3` | 90 |
| `priority_p4` | 262 |
| `priority_p5` | 0 |
| `enterprise_ref_sas_candidates` | 194 |
| `enterprise_action_rows` (currently in `ENTREPRISE_A_RELANCER`) | 100 |
| `old_debt_age_days_min` | 91 |
| `old_debt_age_days_median` | 204 |
| `old_debt_age_days_max` | 801 |
| `stale_threshold_days` | 90 |

**Derivation notes (for Phase 2 implementation):**

- `operational_total` = rows in `ctx.dernier_df` where
  `portfolio_bucket in {"LIVE_OPERATIONAL", "LEGACY_BACKLOG"}`.
  This gives 2,460, consistent with: 4,834 total latest rows minus 1,111
  terminal/closed minus 1,263 `ARCHIVED_HISTORICAL`.
- `moex_total` = operational rows where `_focus_owner_tier == "MOEX"`.
- `primary_total` / `secondary_total` = operational rows where
  `_focus_owner_tier == "PRIMARY"` / `"SECONDARY"`.
- `consultants_total` = `primary_total + secondary_total` = 749.
- `enterprise_ref_sas_candidates` = operational rows where
  `_visa_global in {"REF", "SAS REF"}` (using the canonical resolved
  `_visa_global` column; no independent recomputation). **Phase 1 must
  confirm the exact mask that reproduces 194.**
- `enterprise_action_rows` = rows in `COUNTER_ATTACK_ITEMS.csv` where
  `action_bucket == "ENTREPRISE_A_RELANCER"`.
- `priority_p*` counts are computed over the full operational mask (stale
  included), not over the stale-excluded set that the current Focus mode
  uses.
- `old_debt_age_days_*` = min/median/max of `_days_since_last_activity`
  over the stale sub-segment (>90d).

---

## 4. Focus mode retirement

- The **default view** of the application becomes the operational dashboard
  (section 1 universe).
- The **Focus mode toggle** is retired from the default view. It may be
  relabelled to a display-only "Fresh / Stale / All" segment selector that
  controls tile highlighting and grouping only, never backend filtering.
- The **legacy Focus backend is PRESERVED in full**:
  - `src/reporting/focus_filter.py` and `apply_focus_filter` are unchanged.
  - `app.py` functions `_apply_focus_filter`, `_build_live_operational_numeros`,
    and `_apply_live_narrowing` are unchanged.
  - `get_dashboard_data(focus=True, stale_days=90)` remains fully callable
    and returns the pre-redesign Focus payload.
- **Removal of the legacy Focus backend** — if ever desired — is a separate
  out-of-scope phase that requires its own explicit approval. It is NOT part
  of this redesign.
- The Focus result still carries: `focused`, `p1_overdue`, `p2_urgent`,
  `p3_soon`, `p4_ok`, `total_dernier`, `excluded`, `stale`, `resolved`,
  `by_consultant`, `by_contractor`.

---

## 5. Action MOEX relationship — open question (Phase 5)

**Default working assumption:** ACTION MOEX (`counter_attack.jsx` /
`COUNTER_ATTACK_ITEMS.csv`) is a **curated action-plan subset**, not the
full operational cockpit.

**Rationale:** `COUNTER_ATTACK_ITEMS.csv` contains ~1,524 rows (terminal
states excluded). Of the 2,460 operational open rows, 1,659 currently
have no `action_bucket` assignment. Treating ACTION MOEX as "the full
backlog" would silently undercount by a factor of approximately 1.6×.

**Final decision:** deferred to Phase 5. Phase 5 will lock the
interpretation and update the UI label accordingly (candidate:
`"Plan d'action — sous-ensemble curé"`).

**This redesign does not modify** `counter_attack_builder.py`,
`counter_attack_query.py`, or `counter_attack.jsx` body logic.

---

## 6. UI rule — no computation in JS

Backend payload is the single source of truth for all counts, rates, and
derived metrics.

- JS / JSX **selects** fields, formats labels, and renders tiles.
- JS / JSX **never reduces, sums, derives, or re-computes** any count
  from raw document rows.
- The existing `pendTrend = [...].reduce(...)` at `overview.jsx` lines 112–115
  is the known violation; Phase 4 must remove it and replace with a
  backend-supplied value.
- If a backend field is absent, the UI renders `"—"`, never a computed
  fallback.
- The backend arithmetic in `ui_adapter.adapt_overview` (e.g.
  `answered = vso + vao + ref + sas_ref + hm`, `refus_rate`, consultant
  `pass_rate`) is Python-side and is **consistent with this rule** — it
  stays as-is.

---

## 7. Backend ownership (proposal, confirmed in Phase 1)

**Proposed owner function:** `src/reporting/aggregator.py` →
`compute_operational_dashboard(ctx) -> dict`.

**Rationale:**
- `aggregator.py` already owns dernier-driven KPI composition and already
  accepts `focus_result` / `focused_doc_ids`; adding a sibling composed
  function there honours the "highest-level existing composed truth first"
  guardrail.
- All required signals (`portfolio_bucket`, `_visa_global`,
  `_focus_owner_tier`, `_days_since_last_activity`, `emetteur` REF/SAS REF)
  are pre-computed on `ctx.dernier_df` upstream — no new pre-computation
  step is required (Phase 1 must confirm).
- **No new module** unless `compute_operational_dashboard` grows beyond
  ~200 lines; in that case Phase 1 findings will recommend
  `src/reporting/operational_dashboard.py` as the fallback location.

**Wire-up (Phase 2):** in `app.py::get_dashboard_data`, after the existing
focus filter call, also call `compute_operational_dashboard(ctx)` and
merge its dict into the payload under the key `"operational"`. The
existing focus block is not modified.

**UI bridge (Phase 3):** `ui_adapter.adapt_overview` passes through
`dashboard["operational"]` into the overview dict under the same key,
making it available at `window.OVERVIEW.operational` with all 19 fields
listed in section 3.

---

## 8. Vault contradictions found during Phase 0

The following discrepancies were identified between the vault notes / context
files read during Phase 0 and the locked contract above. None of these
require a pipeline or chain_onion logic change; they are documentation
staleness issues to be resolved in Phase 7.

**C-01 — Portfolio bucket enumeration (plan Phase 1 claim vs. vault)**

`OPERATIONAL_DASHBOARD_EXECUTION_PLAN.md §3 Phase 1` lists the claim to
verify as:
> "`portfolio_bucket` carries values `LIVE_OPERATIONAL`, `LEGACY_BACKLOG`,
> `ARCHIVED_HISTORICAL`, `CLOSED_VAO`, `CLOSED_VSO`, `VOID_CHAIN`,
> `DEAD_AT_SAS_A`."

However, `obsidian_repo_mind/07_CHAIN_ONION_MENTAL_MODEL.md` (Portfolio
buckets table) shows only **three** `portfolio_bucket` values:
`LIVE_OPERATIONAL`, `LEGACY_BACKLOG`, `ARCHIVED_HISTORICAL`. The values
`CLOSED_VAO`, `CLOSED_VSO`, `VOID_CHAIN`, `DEAD_AT_SAS_A` appear there as
`current_state` sub-states that map **to** `ARCHIVED_HISTORICAL`, not as
`portfolio_bucket` values themselves.

**Impact:** The operational mask in section 1 ("`portfolio_bucket in
{LIVE_OPERATIONAL, LEGACY_BACKLOG}`") is not affected — it excludes
`ARCHIVED_HISTORICAL` and by extension all its terminal sub-states.
**Phase 1 must confirm the actual cardinality of `portfolio_bucket` on
`ctx.dernier_df` with an exact file:line citation.**

**C-02 — COUNTER_ATTACK_ITEMS.csv row count**

`obsidian_repo_mind/09_ACTION_MOEX_COUNTER_ATTACK.md` states
"1,525 distinct `family_key` rows as of Phase 6C S3 correction."

`context/05_OUTPUT_ARTIFACTS.md` states "1524 rows after Phase 6X R3
validation."

The execution plan Phase 5 also states "1,524 (terminal-excluded)."

The vault note (09) appears to pre-date the Phase 6X R3 validation and
reflects the count before Phase 6X corrections. This is a stale vault
note, not a contract contradiction. The locked baseline does not reference
the total row count of `COUNTER_ATTACK_ITEMS.csv`; it references only
`enterprise_action_rows = 100` (`ENTREPRISE_A_RELANCER` bucket count).
**Phase 7 should update `09_ACTION_MOEX_COUNTER_ATTACK.md` to reflect
the 1,524 figure.**

**C-03 — Focus mode description in context notes**

`context/03_UI_FEED_MAP.md §A` describes `data_bridge.js:bridge.init()` as
called with `(focusMode, staleDays)` and `§B OverviewPage` shows the
`OVERVIEW.focus` sub-dict as the primary source of P1/P2/P3/P4 tile data.
These notes accurately describe the **current** (pre-redesign) state.
After Phase 3 and Phase 4 ship, this mapping will be superseded by
`window.OVERVIEW.operational`. **Phase 7 must update `context/03_UI_FEED_MAP.md`
to reflect the new `window.OVERVIEW.operational` contract.**

No contradiction requires a stop. No vault statement forces a pipeline or
chain_onion logic change.

---

*End of Phase 0 contract lock.*
