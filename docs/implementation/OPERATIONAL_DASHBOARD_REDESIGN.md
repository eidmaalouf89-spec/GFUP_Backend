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

---

## Phase 1 Findings (date: 2026-05-07)

Read-only diagnostic. No source files were modified. Citations below use
file:line into the runtime tree at `feat/operational-dashboard` HEAD.

### Claim verification

**Claim 1 — `ctx.dernier_df` carries `_days_since_last_activity`,
`_visa_global`, `_focus_owner_tier`, `portfolio_bucket`, and `emetteur`
columns at runtime.**

Verdict: **AMENDED — 4/5 confirmed; `portfolio_bucket` REFUTED.**

- `_visa_global`: CONFIRMED. Assigned at
  `src/reporting/data_loader.py:611` inside `_precompute_focus_columns`.
  Source: `workflow_engine.compute_visa_global_with_date(doc_id)` at
  `src/reporting/data_loader.py:604` (NB: this is a direct WorkflowEngine
  call, not a route through `flat_ged_doc_meta`; the
  `flat_ged_doc_meta`-preferred path lives in
  `src/reporting/aggregator.py:33-50` `resolve_visa_global` and is called
  per-doc at aggregation time, not at column-precompute time).
- `_days_since_last_activity`: CONFIRMED. Assigned at
  `src/reporting/data_loader.py:648` from `_last_activity_date`
  (`data_loader.py:636`) and `data_date`.
- `_focus_owner_tier`: CONFIRMED. Assigned at
  `src/reporting/focus_ownership.py:195` inside `compute_focus_ownership`
  (signature at `focus_ownership.py:77`). Called from
  `src/reporting/data_loader.py:525` and again at `data_loader.py:894`.
  Verified runtime distribution from `audit_counts_lineage.py` log:
  `CLOSED=791, CONTRACTOR=320, MOEX=2647, PRIMARY=987, SECONDARY=89`
  (over the full 4,834 dernier rows, before operational masking).
- `emetteur`: CONFIRMED. Used as a column on `ctx.dernier_df` at
  `src/reporting/contractor_fiche.py:77`
  (`ctx.dernier_df[ctx.dernier_df["emetteur"] == contractor_code]`) and
  `src/reporting/contractor_quality.py:341-342`. Carried through from
  `docs_df` upstream.
- `portfolio_bucket`: **REFUTED on `ctx.dernier_df`.** Grep over
  `src/reporting/**` for `portfolio_bucket` assignment to `dernier_df`
  returns zero matches. The column lives on the chain register
  (`src/chain_onion/chain_classifier.py:565-585`
  `_assign_portfolio_bucket`), keyed by `family_key` (= numero), and is
  exported to `output/chain_onion/CHAIN_REGISTER.csv` and
  `output/chain_onion/ONION_SCORES.csv`. To apply the operational mask
  on dernier rows, a left-join (or `isin` against a precomputed numero
  set) by `numero_normalized` ↔ `family_key` is required. This is exactly
  how today's legacy Focus mode does it via
  `app.py:_build_live_operational_numeros` (line 558-583, calling
  `chain_onion.query_hooks.get_live_operational(ctx)`) and
  `app.py:_apply_live_narrowing` (line 585-597). Phase 2 must replicate
  this join (extended to LEGACY_BACKLOG too) inside
  `compute_operational_dashboard`.

This refutation does **not** trigger the Phase 1 STOP condition (the stop
applies if a *required column is missing such that adding pre-compute
would touch upstream pipeline files*). All required signals are
available; `portfolio_bucket` is reachable via a CSV join on
`family_key`, which is a reporting-layer operation and stays inside
Phase 2's allowed write zone. Phase 2 should NOT add `portfolio_bucket`
to `ctx.dernier_df` (that would touch `data_loader.py` and risk a
pickle-cache schema bump per `obsidian_repo_mind/11_DEBUGGING_SEAMS.md`
§Seam 2 / H-2). Instead, the implementation is:

```python
# inside compute_operational_dashboard(ctx)
from chain_onion.query_hooks import (
    QueryContext, get_live_operational, get_legacy_backlog,
)
qctx = QueryContext(output_dir=BASE_DIR / "output" / "chain_onion")
live = get_live_operational(qctx)
legacy = get_legacy_backlog(qctx)
operational_keys = (
    set(live["family_key"].dropna().astype(str))
    | set(legacy["family_key"].dropna().astype(str))
)
operational_dernier = ctx.dernier_df[
    ctx.dernier_df["numero_normalized"].astype(str).isin(operational_keys)
]
```

**Claim 2 (REVISED — see C-01) — `portfolio_bucket` carries values from
a closed enumerated set.**

Verdict: **AMENDED.** The actual cardinality of `portfolio_bucket` in
the runtime is **3**, not 7. The enumerated set is exactly:

| Value | Citation |
|---|---|
| `LIVE_OPERATIONAL` | `src/chain_onion/chain_classifier.py:582` |
| `LEGACY_BACKLOG` | `src/chain_onion/chain_classifier.py:585` |
| `ARCHIVED_HISTORICAL` | `src/chain_onion/chain_classifier.py:577` |

Module docstring confirmation:
`src/chain_onion/chain_classifier.py:8`
> `portfolio_bucket : LIVE_OPERATIONAL / LEGACY_BACKLOG / ARCHIVED_HISTORICAL`

The four labels listed in the original execution-plan claim
(`CLOSED_VAO`, `CLOSED_VSO`, `VOID_CHAIN`, `DEAD_AT_SAS_A`) are
**`current_state` values, not `portfolio_bucket` values.** They live in
`ARCHIVED_TERMINAL_STATES` at
`src/chain_onion/chain_classifier.py:114-119`, and `_assign_portfolio_bucket`
maps any of them to `ARCHIVED_HISTORICAL` via Priority 1
(`chain_classifier.py:575-577`). Counter-evidence in
`src/reporting/counter_attack_builder.py:51-58` confirms the same names
are `current_state` values used for terminal-state exclusion in the
Counter-Attack builder.

The operational mask in section 1 of this redesign
(`portfolio_bucket in {LIVE_OPERATIONAL, LEGACY_BACKLOG}`) is
**unaffected**: it excludes `ARCHIVED_HISTORICAL` (and therefore all
four terminal `current_state` values that map into it). No contract
amendment is required; the C-01 amendment is purely an evidence-
integrity correction.

**Plan amendment recommendation:** the execution-plan Phase 1 prompt
text at `OPERATIONAL_DASHBOARD_EXECUTION_PLAN.md:248-251` should be
re-worded for the next planning revision to read "`portfolio_bucket`
carries one of three values: `LIVE_OPERATIONAL`, `LEGACY_BACKLOG`,
`ARCHIVED_HISTORICAL`. The four terminal labels (`CLOSED_VAO`,
`CLOSED_VSO`, `VOID_CHAIN`, `DEAD_AT_SAS_A`) are `current_state` values
that map to `ARCHIVED_HISTORICAL`." This is a documentation correction
only; it does not affect the locked contract or the locked baseline.

**Claim 3 — `aggregator.compute_project_kpis` already accepts
`focus_result` and filters by `focused_doc_ids`.**

Verdict: **CONFIRMED.**

- Signature: `src/reporting/aggregator.py:53`:
  `def compute_project_kpis(ctx: RunContext, focus_result: Optional["FocusResult"] = None) -> dict:`
- `focused_ids` extracted at `src/reporting/aggregator.py:94-96`:
  `focused_ids = focus_result.focused_doc_ids if focus_result is not None and focus_result.stats.get("focus_enabled")`
- `focused_ids` filter applied to "Open" visa bucket at
  `src/reporting/aggregator.py:114-118`
  (`if did in focused_ids: visa_counts["Open"] += 1`).
- `focus_ids` filter applied to responsible-party counts at
  `src/reporting/aggregator.py:130-136`.
- Focus extras attached at `src/reporting/aggregator.py:174-177`
  (`result["focus_stats"] = focus_result.stats`,
  `result["focus_priority_queue"] = focus_result.priority_queue[:50]`).

Sibling functions also accept `focus_result`:
`compute_monthly_timeseries` at `aggregator.py:182-185`,
`compute_weekly_timeseries` at `aggregator.py:228`,
`compute_consultant_summary` at `aggregator.py:293-296`,
`compute_contractor_summary` at `aggregator.py:450-453`. This is the
"highest-level existing composed truth" the global guardrail prefers.

**Claim 4 — `ui_adapter.adapt_overview` already shapes
`window.OVERVIEW.focus` sub-dict.**

Verdict: **CONFIRMED.**

- Function: `src/reporting/ui_adapter.py:61` `adapt_overview(dashboard_data, app_state) -> dict`.
- Empty-default focus shape at `src/reporting/ui_adapter.py:180-185`:
  keys `focused, p1_overdue, p2_urgent, p3_soon, p4_ok, total_dernier,
  excluded, stale, resolved, by_consultant, by_contractor`.
- Populated focus shape at `src/reporting/ui_adapter.py:186-199`,
  reading `focused_count`, `p1_overdue`, `p2_urgent`, `p3_soon`,
  `p4_ok`, `total_dernier`, `stale_excluded`, `resolved_excluded`,
  `by_consultant`, `by_contractor` from the backend `focus` dict
  (which is `focus_result.stats`, attached in
  `app.py:get_dashboard_data` line 635).
- Subdict assigned to the returned overview at
  `src/reporting/ui_adapter.py:218`: `"focus": focus_stats`.
- Top-level overview also forwards `priority_queue` (line 236) and
  `legacy_backlog_count` (line 237). Phase 3 adds `"operational"` next
  to these (the no-arithmetic pass-through).

**Claim 5 — `counter_attack_builder` writes to `COUNTER_ATTACK_ITEMS.csv`
with `action_bucket` column and excludes terminal states.**

Verdict: **CONFIRMED.**

- Output filename and write site:
  `src/reporting/counter_attack_builder.py:629`
  (`out_path = output_dir / "COUNTER_ATTACK_ITEMS.csv"`) and
  `src/reporting/counter_attack_builder.py:664`
  (`result.to_csv(out_path, index=False, encoding="utf-8")`).
- `action_bucket` is in the output schema at
  `src/reporting/counter_attack_builder.py:28`
  (inside `OUTPUT_COLUMNS`) and assigned per row at
  `src/reporting/counter_attack_builder.py:608` via
  `_assign_bucket(row)`.
- Terminal-state exclusion: `TERMINAL_STATES` set at
  `src/reporting/counter_attack_builder.py:51-58`
  (`{CLOSED_VAO, CLOSED_VSO, DEAD_AT_SAS_A, ABANDONED_CHAIN, VOID_CHAIN,
  UNKNOWN_CHAIN_STATE}`). Exclusion fires inside `_assign_bucket` at
  `src/reporting/counter_attack_builder.py:335-336`
  (`if current_state in TERMINAL_STATES: return ""`); the upstream loop
  drops rows whose bucket is empty at
  `src/reporting/counter_attack_builder.py:649-650`
  (`if not bucket: continue`).
- Note: terminal exclusion in this module operates on `current_state`,
  not on `portfolio_bucket` — consistent with the C-01 finding above.
- A separate `focus_owner_tier == "CLOSED"` filter applies at
  `src/reporting/counter_attack_builder.py:643-644`, which excludes
  documents already at `_visa_global` terminal status.

### Mask logic lock

For each baseline count below, the exact mask that today produces (or
must produce) the locked figure is given, with file:line citations to
the column-derivation site and the filter site. Phase 2's
`compute_operational_dashboard` must reproduce these masks exactly.

**`operational_total = 2,460`**

Definition: rows in `ctx.dernier_df` whose chain `family_key`
(=`numero_normalized`) has `portfolio_bucket ∈ {LIVE_OPERATIONAL,
LEGACY_BACKLOG}` in the chain register.

Mask:
```python
operational_keys = (
    set(get_live_operational(qctx)["family_key"].dropna().astype(str))
    | set(get_legacy_backlog(qctx)["family_key"].dropna().astype(str))
)
operational_mask = (
    ctx.dernier_df["numero_normalized"].astype(str).isin(operational_keys)
)
```

Citations:
- `portfolio_bucket` derivation:
  `src/chain_onion/chain_classifier.py:565-585` `_assign_portfolio_bucket`.
- `LIVE_OPERATIONAL` selector: `src/chain_onion/query_hooks.py:274-276`
  `get_live_operational`.
- `LEGACY_BACKLOG` selector: `src/chain_onion/query_hooks.py:279-281`
  `get_legacy_backlog`.
- `numero_normalized` join key on dernier: used at `app.py:594`
  (`fdf["numero_normalized"].astype(str).isin(live_numeros)`); column
  guaranteed by the data_loader pipeline.
- Live-only narrowing today: `app.py:558-583`
  `_build_live_operational_numeros` (legacy Focus mode uses
  LIVE-only — Phase 2 must add LEGACY_BACKLOG to match the operational
  contract).

**`moex_total = 1,711`**

Mask: `operational_mask & (ctx.dernier_df["_focus_owner_tier"] == "MOEX")`.

Citations:
- `_focus_owner_tier` derivation:
  `src/reporting/focus_ownership.py:195`
  (`dernier_df["_focus_owner_tier"] = tiers_list`).
- Tier values vocabulary: `src/reporting/focus_ownership.py:84`
  (`"PRIMARY", "SECONDARY", "MOEX", "CONTRACTOR", "CLOSED"`).
- `value_counts` precedent on `_focus_owner_tier`:
  `src/reporting/focus_filter.py:127, 283`.

**`primary_total = 670` / `secondary_total = 79`**

Masks:
- `operational_mask & (ctx.dernier_df["_focus_owner_tier"] == "PRIMARY")`
  → 670.
- `operational_mask & (ctx.dernier_df["_focus_owner_tier"] == "SECONDARY")`
  → 79.

Citations as above (focus_ownership.py:195, 84). The pre-mask raw
values from this Phase 1 audit run are PRIMARY=987, SECONDARY=89; the
operational mask removes terminal/archived rows leaving 670/79.
`consultants_total = primary_total + secondary_total = 749`.

**`enterprise_ref_sas_candidates = 194` ← CRITICAL**

Definitive mask:
```python
operational_mask & ctx.dernier_df["_visa_global"].isin(["REF", "SAS REF"])
```

- **Live vs legacy:** full operational mask (LIVE_OPERATIONAL ∪
  LEGACY_BACKLOG). Justification: section 0 of the execution plan
  enumerates the 194 figure under "Operational open
  (`LIVE_OPERATIONAL` + `LEGACY_BACKLOG`) | 2,460" lineage, not the
  Live-only universe; and the locked redesign §1 fixes the operational
  mask as LIVE ∪ LEGACY.
- **Latest-indice rule:** `ctx.dernier_df` only (one row per `numero`).
  No indices_df read. This matches the Phase 0 contract §1.
- **`_visa_global` canonicalisation:** the column on `ctx.dernier_df`
  populated at `src/reporting/data_loader.py:611` from
  `workflow_engine.compute_visa_global_with_date` is the canonical
  value the system uses for Focus mode (`focus_filter.py:187` reads
  the same column). The aggregator's `resolve_visa_global`
  (`aggregator.py:33-50`) prefers `flat_ged_doc_meta["visa_global"]`
  when present and falls back to the engine value; for Phase 2 the
  cleanest choice is to **read the precomputed
  `dernier_df["_visa_global"]` column directly** (no per-doc helper
  call), because (a) it is the same column today's Focus mode reads,
  (b) this avoids the per-row engine call latency, and (c) it
  preserves the no-recomputation guardrail. If a future cleanup ever
  routes `_precompute_focus_columns` through `resolve_visa_global` (a
  pre-existing D-010 backlog item), the column value will not change
  meaningfully, only its provenance.
- **REF vs SAS REF:** both included
  (`_visa_global.isin(["REF", "SAS REF"])`). Visa-global vocabulary
  with `SAS REF` as a distinct terminal status is defined at
  `src/chain_onion/chain_classifier.py:79-96` `_derive_visa_global` and
  in the focus terminal set at `src/reporting/focus_filter.py:29`
  (`TERMINAL_STATUSES = {"VSO", "VAO", "REF", "SAS REF", "HM"}`).
- **`emetteur` filter:** **none.** Every dernier row has an `emetteur`
  (contractor code); the "entreprise responsibility" framing in the
  contract describes ownership semantics, not a column value. No
  filter such as `emetteur != "ENTREPRISE"` should be applied — there
  is no such literal value in the runtime data; `emetteur` carries
  contractor codes resolved by
  `src/reporting/contractor_fiche.py::resolve_emetteur_name`.

**194 reproducibility status:** the mask above is the cleanest mask
defendable from runtime evidence, and it directly implements the
contract in §3 of this document. **It cannot be empirically verified to
return exactly 194 in Phase 1 because Phase 1 is read-only (no
implementation in `aggregator.py` exists yet to run).** The empirical
verification gate is `scripts/check_operational_payload.py`, a Phase 2
deliverable. The strongest evidence available in Phase 1 is:

- `python scripts/audit_counts_lineage.py` reports
  `UI_PAYLOAD: compared=10 matches=10 mismatches=0` — the regression
  baseline (REF, SAS_REF, total dernier, portfolio_bucket counts on
  the chain register, etc.) is healthy.
- The single AUDIT FAIL (`status_SAS_REF@L1_FLAT_GED_XLSX`) is the
  long-standing D-011 RAW→FLAT SAS REF projection gap documented at
  `obsidian_repo_mind/11_DEBUGGING_SEAMS.md` §Seam 10. It is unrelated
  to operational dashboard logic and was already FAIL before this
  branch was cut; it is **not** a Phase 1 regression and **not** a
  Phase 1 STOP condition.

Phase 2 must therefore implement the mask exactly as written above.
If `check_operational_payload.py` returns a count other than 194 on
the first run, Phase 2 must STOP per the plan (do not adjust the
baseline). The most likely sources of a 194 mismatch would be (a)
forgetting to include LEGACY_BACKLOG in the mask (Live-only would
under-count), (b) using `_visa_global == "REF"` instead of `isin(["REF",
"SAS REF"])`, or (c) routing visa via `resolve_visa_global` per-doc
which can return `flat_ged_doc_meta`-sourced values that differ from
the precomputed column for a small number of edge documents — Phase 2
should use the column.

### C-01 resolution

The actual `portfolio_bucket` value set is **three values, not seven**:
`{LIVE_OPERATIONAL, LEGACY_BACKLOG, ARCHIVED_HISTORICAL}`. Citation:
`src/chain_onion/chain_classifier.py:565-585`
`_assign_portfolio_bucket`, returning one of
`("ARCHIVED_HISTORICAL", False)` (line 577),
`("LIVE_OPERATIONAL", False)` (line 582), or
`("LEGACY_BACKLOG", False)` (line 585). Module docstring at
`chain_classifier.py:8` lists exactly the same three values.

The four terminal labels in the original Phase 1 claim
(`CLOSED_VAO`, `CLOSED_VSO`, `VOID_CHAIN`, `DEAD_AT_SAS_A`) are
**`current_state` values**, defined as `ARCHIVED_TERMINAL_STATES` at
`src/chain_onion/chain_classifier.py:114-119`, and mapped to
`portfolio_bucket = ARCHIVED_HISTORICAL` by Priority 1 of
`_assign_portfolio_bucket` (lines 575-577). Same names appear as
`current_state` (not bucket) values at
`src/reporting/counter_attack_builder.py:51-58` for the
terminal-exclusion mask in the Counter-Attack builder.

The operational mask in §1 of this redesign
(`portfolio_bucket ∈ {LIVE_OPERATIONAL, LEGACY_BACKLOG}`) is
**unchanged** by this finding — it already excludes
`ARCHIVED_HISTORICAL` and therefore all four terminal `current_state`
sub-values. C-01 is an evidence-integrity correction, not a contract
change. No vault note update is forced by this finding (Phase 7 should
already track this under the existing C-01 entry in §8 of this doc).

### Owner recommendation

**Choice: (A) Extend `src/reporting/aggregator.py` with a new public
function `compute_operational_dashboard(ctx) -> dict`.**

Reason: `aggregator.py` is the existing highest-level composed-truth
owner for dernier-driven KPI composition. It already accepts a
`focus_result` (`aggregator.py:53`) and filters by `focused_doc_ids`
(`aggregator.py:114-118, 130-136`); it already uses
`_visa_global` semantics through `resolve_visa_global`
(`aggregator.py:33-50`); it already iterates `ctx.dernier_df` row-wise
for KPI counts (`aggregator.py:101, 122`); and it already carries the
focus-extras attachment pattern at `aggregator.py:174-177` that Phase 3
will follow for the new `operational` payload key. Extending it with a
sibling function preserves the global guardrail "highest-level existing
composed truth first." Adding a new module
(`src/reporting/operational_dashboard.py`) would create a parallel
reporting surface and split the dernier-driven composition truth across
two modules — there is no structural reason in `aggregator.py` that
prevents (A). The function is expected to be ~80-120 lines (well under
the ~200-line threshold the redesign §7 names), so the (B) fallback is
not triggered.

The new function should:

1. Build the operational numero set by joining
   `output/chain_onion/CHAIN_REGISTER.csv` (or `ONION_SCORES.csv` via
   `query_hooks`) on `family_key` against
   `ctx.dernier_df["numero_normalized"]`, taking
   `LIVE_OPERATIONAL ∪ LEGACY_BACKLOG`.
2. Apply the segmentation masks (fresh/stale, MOEX/PRIMARY/SECONDARY,
   priority bins, REF/SAS REF) over the resulting `operational_dernier`
   subframe using the precomputed columns
   (`_focus_owner_tier`, `_visa_global`, `_days_since_last_activity`,
   `_focus_priority`).
3. Read `output/counter_attack/COUNTER_ATTACK_ITEMS.csv` (or whatever
   path `build_counter_attack.py` writes to) for
   `enterprise_action_rows` count where `action_bucket ==
   "ENTREPRISE_A_RELANCER"`. Return `None` with a warning if the
   artifact is missing (per redesign §3 derivation note).
4. Return the 19-field dict named in the locked baseline.

### Open issues for Phase 2

Items Phase 2 must know that the plan body does not already cover:

1. **`portfolio_bucket` is not on `ctx.dernier_df`.** Phase 2 must
   read it via the chain register / onion scores and join by
   `family_key` ↔ `numero_normalized`. Do **not** add a column to
   `ctx.dernier_df` — that would require touching `data_loader.py` and
   risks bumping `CACHE_SCHEMA_VERSION`
   (`obsidian_repo_mind/11_DEBUGGING_SEAMS.md` §H-2). The redesign §3
   wording ("rows in `ctx.dernier_df` where `portfolio_bucket in
   {LIVE_OPERATIONAL, LEGACY_BACKLOG}`") should be read semantically,
   not as a literal column read.

2. **Today's legacy `_build_live_operational_numeros` is LIVE-only.**
   `app.py:558-583` calls only `get_live_operational(ctx)`; the
   `legacy_count` it returns (`app.py:579`) is for the
   `legacy_backlog_count` stat field, not for narrowing. Phase 2 must
   build a **new** numero set that is the union of LIVE and LEGACY for
   the operational mask. Do **not** alter
   `_build_live_operational_numeros` — that helper still serves the
   preserved legacy Focus backend (redesign §4) and changing it would
   break the focus payload contract.

3. **`_visa_global` source on `ctx.dernier_df` is the WorkflowEngine
   path, not `flat_ged_doc_meta`.** `data_loader.py:604` calls
   `workflow_engine.compute_visa_global_with_date` directly. The
   `flat_ged_doc_meta`-preferred fallback in
   `aggregator.resolve_visa_global` is per-doc and only kicks in when
   that helper is invoked. For
   `enterprise_ref_sas_candidates`, Phase 2 should read the
   precomputed `_visa_global` column on `ctx.dernier_df` (no per-row
   `resolve_visa_global` call) — this matches what Focus mode reads
   today (`focus_filter.py:187`) and is the simplest, fastest path. The
   D-010 follow-up (route precompute through `resolve_visa_global`) is
   noted in execution plan §9 and is OUT OF SCOPE for this redesign.

4. **`enterprise_action_rows` is not produced by `aggregator.py`
   today.** The 100 figure is a row-count over
   `output/counter_attack/COUNTER_ATTACK_ITEMS.csv` (or the equivalent
   path under `output/`) where `action_bucket == "ENTREPRISE_A_RELANCER"`.
   Phase 2 must read this CSV directly and count, returning `None` with
   a warning string in `universe_definition` if the artifact is
   missing. The CSV is produced by `scripts/build_counter_attack.py`
   (which calls `counter_attack_builder.build_counter_attack_items`,
   `counter_attack_builder.py:625`) and is not regenerated by the
   dashboard endpoint.

5. **The audit script reports one pre-existing AUDIT FAIL.**
   `python scripts/audit_counts_lineage.py` outputs
   `AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=
   status_SAS_REF@L1_FLAT_GED_XLSX`. This is the documented D-011 gap
   (`obsidian_repo_mind/11_DEBUGGING_SEAMS.md` §Seam 10) — the
   RAW→FLAT SAS REF projection drop from 836 to 284, with 6
   unexplained rows in the 28xxx/A C1 cluster. It is a long-standing
   open item, **not** a Phase 1 regression, and the operational
   dashboard does not depend on the L0→L1 SAS REF projection. The
   regression-baseline gate
   (`UI_PAYLOAD: compared=10 matches=10 mismatches=0`) is **clean**.
   Phase 2 / Phase 6 should treat the same single FAIL as expected
   noise and gate on `mismatches=0` from the UI_PAYLOAD line.

6. **`app.py` has no `_apply_focus_filter` method.** The execution plan
   Phase 1 prompt (line 223) names it; the actual code uses inline
   `apply_focus_filter(ctx, focus_config)` calls at app.py:616, 655,
   671, 689, 705, 806, 1073. This is a doc/naming drift only — the
   semantics (focus filter applied, then live-narrowed, then KPIs
   computed) are unchanged. No action required for Phase 2 beyond
   noting the actual call sites when wiring `compute_operational_dashboard`
   into `get_dashboard_data` (`app.py:601-645`).

7. **Validation evidence captured for this Phase 1 run:**
   - `python -m py_compile src/reporting/aggregator.py
     src/reporting/focus_filter.py src/reporting/ui_adapter.py` → exit 0,
     no output (clean).
   - `python scripts/audit_counts_lineage.py` →
     `UI_PAYLOAD: compared=10 matches=10 mismatches=0` (clean) plus the
     expected-noise D-011 FAIL described in item 5. RunContext loaded
     `4834 docs, 4834 dernier, 27237 responses, data_date=2026-04-10`,
     focus ownership distribution
     `CLOSED=791, CONTRACTOR=320, MOEX=2647, PRIMARY=987, SECONDARY=89`
     over the unmasked dernier.
   - `git status` after Phase 1 work shows only this redesign doc
     modified (no source-file edits).

*End of Phase 1 Findings.*
