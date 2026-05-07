#repo-map #debugging #seams #hazards

# Debugging Seams

> The most common bug hotspots. Each seam has caused at least one production bug.
> Source: `context/11_TOOLING_HAZARDS.md`, `context/02_DATA_FLOW.md`, `README.md §Phase 0`.

---

## Seam 1 — WorkflowEngine dual-attribute hazard

**Reference:** `context/11_TOOLING_HAZARDS.md §H-3`

**Symptom:** SAS-track metrics (SAS REF rate, SAS-gate analytics) report 0% / 0 rows despite SAS rows existing in raw data. SNI SAS REF = 0% was a real production bug from this seam.

**Root cause:** `WorkflowEngine.__init__` filters `is_exception_approver == True`, stripping ALL SAS rows. Two attributes named similarly return different datasets:
- `ctx.workflow_engine.responses_df` — FILTERED (no SAS rows) — correct for visa_global, deadline
- `ctx.responses_df` — FULL (includes SAS rows) — required for SAS analytics

**First diagnostic:** check `len(ctx.workflow_engine.responses_df)` vs `len(ctx.responses_df)`. If they differ, you have SAS rows in the full frame. Any code reading the engine's frame for SAS analytics is wrong.

**Likely files:** `src/reporting/aggregator.py`, `src/reporting/contractor_quality.py`, any new analytics module

---

## Seam 2 — FLAT_GED pickle cache staleness

**Reference:** `context/11_TOOLING_HAZARDS.md §H-2`

**Symptom:** A number that should have changed after a code change stays the same. SAS REF rate reported 0 for an unknown duration because the cache served stale data silently.

**Root cause:** `data_loader._flat_cache_is_fresh` uses file mtime only (pre-Phase 8 D-001). Schema drift in `stage_read_flat.py` or upstream code is invisible to consumers.

**Fix landed (Phase 8 D-001, 2026-04-29):** `CACHE_SCHEMA_VERSION` in `data_loader.py` — cache is rejected if version mismatches. Bump this constant whenever `stage_read_flat.py` emitted columns change.

**First diagnostic:** delete the three cache files:
```bash
rm -f output/intermediate/FLAT_GED_cache_docs.pkl \
      output/intermediate/FLAT_GED_cache_resp.pkl \
      output/intermediate/FLAT_GED_cache_meta.json
```
If the number changes after the next `load_run_context`, the cache was stale.

**Likely files:** `src/reporting/data_loader.py`, `src/pipeline/stages/stage_read_flat.py`

---

## Seam 3 — Identity mismatch across layers

**Reference:** `context/02_DATA_FLOW.md §Three identity systems`

**Symptom:** A join that should match rows returns 0 results or wrong results. Leading zeros stripped from `numero` causing `045080 → 45080` (real Phase 4 bug with validation_harness F32).

**Root cause:** Three identity systems coexist and are NOT automatically bridged:
- `(numero, indice)` — flat_ged + chain_onion (use for cross-run joins)
- `doc_id` (UUID) — pipeline runtime only, session-scoped, never persist
- `family_key = str(numero)` — chain_onion CSVs

When `pd.read_csv` infers numeric dtype, `family_key` gets cast to int64 and leading zeros are stripped.

**First diagnostic:** check dtypes of identity columns in the join. Force string dtype: `pd.read_csv(path, dtype={"family_key": str, "numero": str, "version_key": str})`.

**Likely files:** `src/chain_onion/validation_harness.py`, any new cross-layer join code

---

## Seam 4 — `visa_global` source mismatch

**Reference:** `README.md §Phase 8 Step 3`

**Symptom:** `visa_global` for a document differs between the UI KPI and the flat GED meta. Could cause count-category shifts at L4 aggregator.

**Root cause (pre-Phase 8):** `aggregator.py` was computing `visa_global` via `WorkflowEngine.compute_visa_global_with_date` (recomputed from engine state) instead of reading `RunContext.flat_ged_doc_meta` (authoritative, written by the builder).

**Fix landed (Phase 8 Step 3, 2026-04-30):** aggregator now routes `visa_global` through `flat_ged_doc_meta`. Date is still pulled from WorkflowEngine because `flat_doc_meta` does not carry `visa_global_date`.

**First diagnostic:** compare `ctx.flat_ged_doc_meta["visa_global"]` vs `ctx.workflow_engine.compute_visa_global_with_date(...)` for the suspect document. If they differ, the meta is authoritative.

**Likely files:** `src/reporting/aggregator.py`

---

## Seam 5 — Chain+Onion source coupling

**Reference:** `context/02_DATA_FLOW.md §Hand-off contracts`

**Symptom:** Chain+Onion outputs are stale relative to the latest pipeline run. `source_loader` reads a different FLAT_GED than the pipeline used.

**Root cause:** Chain+Onion reads `output/intermediate/*` directly — it is coupled to "the most recent run that wrote intermediate", NOT to a specific `run_number` in `run_memory.db`.

**Detection:** `output/debug/chain_onion_source_check.json` (produced at each run by `_check_flat_ged_alignment` in `source_loader.py`). Check `result == "OK"` vs `result == "MISMATCH"`.

**First diagnostic:** compare the mtime of `output/chain_onion/CHAIN_REGISTER.csv` vs `output/intermediate/FLAT_GED.xlsx`. If FLAT_GED is newer, re-run `run_chain_onion.py`.

**Likely files:** `src/chain_onion/source_loader.py`

---

## Seam 6 — Adapter drift (aggregator vs ui_adapter)

**Reference:** `README.md §Phase 8 Step 6`

**Symptom:** UI shows a number that doesn't match what `compute_project_kpis` returns. Field exists in aggregator but not passed through `adapt_overview`.

**Root cause:** `aggregator.compute_project_kpis` and `reporting.ui_adapter.adapt_overview` can diverge when aggregator adds a field but adapter forgets to pass it through. 7 fields are intentionally aggregator-only (not on `adapt_overview`); 2 fields are intentionally merged (REF/SAS_REF merge in adapter).

**Detection:** `scripts/audit_counts_lineage.py` runs a `UI_PAYLOAD` comparison block: `compare=10 matches=10 mismatches=0` is the healthy baseline.

**Likely files:** `src/reporting/aggregator.py`, `src/reporting/ui_adapter.py`

---

## Seam 7 — Bucket derivation drift (Focus + Chain+Onion)

**Symptom:** Focus mode includes chains that should be excluded (LEGACY_BACKLOG, ARCHIVED_HISTORICAL) or vice versa.

**Root cause:** `app.py::_build_live_operational_numeros` queries `query_hooks.get_live_operational(ctx)` which reads `ONION_SCORES.csv`. If the CSV is stale or has different `portfolio_bucket` values than expected, Focus narrowing drifts.

**First diagnostic:** check `output/chain_onion/ONION_SCORES.csv` — is it up to date? Does `portfolio_bucket` distribution match expectations?

**Likely files:** `src/chain_onion/chain_classifier.py`, `src/chain_onion/exporter.py`, `src/chain_onion/query_hooks.py`

---

## Seam 8 — Special-case mapping gap

**Symptom:** A contractor code appears as raw code (e.g. `BEN`) instead of canonical name (`Bentin`) in the UI. A consultant name is not matched to its canonical form.

**Root cause:** Hardcoded mappings in:
- `src/flat_ged/input/source_main/consultant_mapping.py` — `RAW_TO_CANONICAL`, `SPECIAL_CASES`
- `src/reporting/contractor_fiche.py::resolve_emetteur_name` — code → company name
- `src/reporting/consultant_fiche.py::CONSULTANT_DISPLAY_NAMES`, `COMPANY_TO_CANONICAL`

New contractors/consultants on the project require explicit additions to these files.

**First diagnostic:** grep for the raw code in all mapping files. If absent, add the mapping.

**Likely files:** `src/flat_ged/input/source_main/consultant_mapping.py`, `src/reporting/contractor_fiche.py`, `src/reporting/consultant_fiche.py`

---

## Seam 9 — Unknown document classification gap

**Symptom:** A document appears in `DISCREPANCY_REPORT.xlsx` as `REVIEW_REQUIRED` but the classification doesn't match expectations. Or a document lands in the wrong GF sheet.

**Root cause:** `stage_route.py` applies `ExclusionConfig` from `src/config_loader.py`. `stage_discrepancy.py` Part H-1 handles BENTIN_LEGACY_EXCEPTION. If a new lot, emetteur, or year pattern isn't in the config, documents fall through to unexpected buckets.

**First diagnostic:** check `SHEET_EMETTEUR_FILTER` and `SHEET_YEAR_FILTERS` in `src/config_loader.py`. Check `BENTIN_TARGET_TYPES` in `stage_discrepancy.py`.

**Likely files:** `src/config_loader.py`, `src/pipeline/stages/stage_discrepancy.py`

---

## Seam 10 — RAW → FLAT SAS REF projection gap

**Reference:** `README.md §Phase 8` (D-011 open item)

**Symptom:** L0 (RAW) SAS REF count = 836; L1 (FLAT) = 284. A 836 → 284 drop that is partially explained (99.3% per Phase 8B) but has 6 UNEXPLAINED rows in the 28xxx/A C1 cluster.

**Status:** Documented open item (backlog). `src/flat_ged/transformer.py` is on the do-not-touch list. Do not attempt to fix this without an explicit phase plan.

---

## Seam 11 — Stale is a segment, not an exclusion (operational dashboard)

**Reference:** `docs/implementation/OPERATIONAL_DASHBOARD_REDESIGN.md` §1

**Context:** In the **legacy Focus path**, `focus_filter.py::apply_focus_filter` excludes
documents where `_days_since_last_activity > stale_days` (90-day threshold). This produces
the old Focus universe where stale rows are invisible.

In the **operational dashboard** (shipped 2026-05-07), stale (>90 d) is a **visible
segment** — `stale_total = 1,533`. It is never hidden or excluded from the operational
mask. Seam: code that copies the focus-filter exclusion pattern into the operational
dashboard path would silently under-count by 1,533 rows.

**First diagnostic:** if `operational_total < 2,460`, check whether a stale-exclusion
filter (`_days_since_last_activity <= 90`) has been applied to the operational frame.

---

## Seam 12 — `portfolio_bucket` is NOT on `ctx.dernier_df`; join required

**Reference:** `docs/implementation/OPERATIONAL_DASHBOARD_REDESIGN.md` §Phase 1 Findings,
Claim 1 verdict; `src/chain_onion/chain_classifier.py:565–585`.

**Context (CO-4):** `portfolio_bucket` lives on
`output/chain_onion/CHAIN_REGISTER.csv` (and `ONION_SCORES.csv`), keyed by `family_key`
(= `numero`). It is **not** a column on `ctx.dernier_df`. To apply the operational mask
on dernier rows, `compute_operational_dashboard` reuses
`chain_onion.query_hooks.QueryContext + get_live_operational + get_legacy_backlog` —
the same pattern as `app.py::_build_live_operational_numeros` — and joins via
`family_key ↔ numero_normalized`.

**Seam:** any new analytics module that tries to read `ctx.dernier_df["portfolio_bucket"]`
will get a `KeyError`. The correct pattern is to build `operational_keys` from the chain
register and apply `.isin(operational_keys)` on `dernier_df["numero_normalized"]`.

**Do NOT** add `portfolio_bucket` as a column to `ctx.dernier_df` — that would require
touching `data_loader.py` and risks bumping `CACHE_SCHEMA_VERSION` (Seam 2).

---

## Seam 13 — `portfolio_bucket` has exactly 3 values; terminal labels are `current_state`

**Reference:** `src/chain_onion/chain_classifier.py:565–585`
`_assign_portfolio_bucket`; module docstring at `chain_classifier.py:8`.

**Context (CO-5):** `portfolio_bucket` takes exactly three values:

| Value | Citation |
|---|---|
| `LIVE_OPERATIONAL` | `chain_classifier.py:582` |
| `LEGACY_BACKLOG` | `chain_classifier.py:585` |
| `ARCHIVED_HISTORICAL` | `chain_classifier.py:577` |

The four labels `CLOSED_VAO`, `CLOSED_VSO`, `VOID_CHAIN`, `DEAD_AT_SAS_A` are
**`current_state` values** (defined at `chain_classifier.py:114–119` as
`ARCHIVED_TERMINAL_STATES`). `_assign_portfolio_bucket` maps them to
`ARCHIVED_HISTORICAL` (Priority 1). They also appear as `current_state` exclusion
targets in `counter_attack_builder.py:51–58`.

**Seam:** any code that checks `portfolio_bucket == "CLOSED_VAO"` (or the other three
terminal labels) will always return zero matches — those strings are `current_state`
values, never `portfolio_bucket` values.

---

## Seam 14 — Operational mask visa exclusion (CO-3): 332-doc gap

**Reference:** `docs/implementation/OPERATIONAL_DASHBOARD_REDESIGN.md` §1 (CO-3
refinement); `src/reporting/aggregator.py:565–570`.

**Context:** The operational universe is not simply `portfolio_bucket ∈ {LIVE_OPERATIONAL,
LEGACY_BACKLOG}`. Within that broad bucket set (≈ 2,792 rows), documents whose
`_visa_global ∈ {VSO, VAO, REF, SAS REF, HM}` are further excluded as
individually-resolved. The two-layer mask:

```
portfolio_bucket ∈ {LIVE_OPERATIONAL, LEGACY_BACKLOG}
AND _visa_global ∉ {VSO, VAO, REF, SAS REF, HM}
```

yields `operational_total = 2,460`. The 332-doc gap decomposes as:
- 138 CLOSED-visa (VSO + VAO + HM) within open chains
- 194 CONTRACTOR-tier (REF + SAS REF) — surfaced separately as `enterprise_ref_sas_candidates`

**Seam:** a bucket-only mask returns ≈ 2,792 rows instead of 2,460 — a 13% overcount.
The `enterprise_ref_sas_candidates = 194` field uses the **broad** bucket mask (before
visa exclusion) by design, because these are enterprise-responsibility docs needing
follow-up even though resolved.

---

## General first-diagnostic protocol

For any unexpected number in the UI:

1. Check the pickle cache: delete it and reload
2. Check which `responses_df` view the consumer is using (engine vs ctx)
3. Check identity dtype (str vs int64) if joining across layers
4. Run `scripts/audit_counts_lineage.py` — prints L0 → L6 comparison in one pass
5. Compare `ctx.flat_ged_doc_meta` vs WorkflowEngine recomputed values for the suspect metric

See [[13_SAFE_DEBUGGING_PROTOCOL]] for the full checklist.

---

*Back to [[00_START_HERE]]*
