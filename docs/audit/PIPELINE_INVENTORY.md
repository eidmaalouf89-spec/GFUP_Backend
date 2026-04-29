# PIPELINE_INVENTORY — Phase 0 Step 0.1

> Stage-by-stage map of every transformation, filter, dropna, type-coercion,
> and row-count change point from raw GED to the JANSA UI globals.
> File:line references are authoritative; the §4 narrative in
> `docs/implementation/PHASE_0_BACKEND_DEBUGGING.md` is the human-readable
> companion.
>
> **Read-only artifact.** Produced 2026-04-29 from the current working tree.
> Subsequent audit steps (0.2–0.6) reference this map by stage code (A1, B1,
> C5, …). Update IN PLACE if a new transformation lands; bump the change-log.

---

## A — Raw Sources

| Stage | Asset | Path | Loader | Notes |
|---|---|---|---|---|
| A1 | Raw GED export | `input/GED_export.xlsx` | `read_raw.read_ged` (legacy fallback only — see C0) | Sheet "Doc. sous workflow, x versions". |
| A2 | Consultant report PDFs/XLSXs | `input/consultant_reports/` | `src/pipeline/stages/stage_report_memory.py` | Eligibility gate: `_ELIGIBLE_CONFIDENCE_VALUES = {"HIGH", "MEDIUM"}`. LOW dropped. |
| A3 | Normalised consultant reports | `runs/run_0000/consultant_reports.xlsx` | snapshot of A2 ingestion | Per-run artifact. |
| A4 | Persistent consultant memory | `data/report_memory.db` | `report_memory.load_persisted_report_responses` | SQLite. Survives runs. |

**Audit relevance.** A1 is the human-counted truth set ("operator's count of SNI SAS REF ≈ 184"). A2/A4 feeds the SOCOTEC SUS rate at E2 / SAS rate at the Bureau de Contrôle column. Any divergence A1 ≠ B1 is an upstream-rework finding (TRIAGE).

---

## B — Flat GED Pipeline

### B1 — `stage_read_flat.py` (default flat path)

File: `src/pipeline/stages/stage_read_flat.py`

| Op | Lines | Effect on row count |
|---|---|---|
| Read sheet `GED_RAW_FLAT` | `133` (`pd.read_excel(..., sheet_name=_SHEET_RAW, dtype=str)`) | populates `raw_df` |
| Read sheet `GED_OPERATIONS` | `134` | populates `ops_df` |
| `_normalise_bool_cols` (string→bool for `is_completed`, `is_blocking`, `is_sas`, `requires_new_cycle`) | `136-137`, defn `650-656` | none (mutation in place) |
| Strip `numero` / `indice` | `139-141` | none |
| `_apply_sas_filter_flat` — RAPPEL proxy + pre-2026 SAS exclusion (Decision 3) | `150` (call) / `202-274` (defn) | **drops** (numero, indice) pairs on `LOT…`-pre-2026 with PENDING_LATE SAS step from BOTH `ops_df` and `raw_df`. Logs `sas_excluded` count. |
| `doc_codes_df = ops_df[["numero","indice"]].drop_duplicates()` | `156-158` | dedupe — silent row-count change relative to ops_df. |
| Assign stable `doc_id` per (numero, indice) | `162-167` | one UUID per active doc. |
| `_compute_doc_meta` — closure_mode / visa_global / responsible_party / data_date per doc | `170` (call) / `281-324` | populates `flat_ged_doc_meta`. |
| `_derive_visa_global` — MOEX visa OR SAS REF fallback | `353-397` | row count unchanged; sets per-doc `visa_global`. **VP-2:** any `status.endswith("-SAS")` returns `None`. **VP-1:** SAS REF returned only if no MOEX row exists. |
| `_build_docs_df` — one row per OPEN_DOC | `175` (call) / `440-484` | rows = `len(open_docs)` after `step_type=="OPEN_DOC"` filter and doc_id mapping (`463`). Drops rows with `doc_id.isna()`. |
| `_build_responses_df` — per-step rows (excludes OPEN_DOC) | `179` (call) / `491-643` | **row-count change point.** Filter `step_type != "OPEN_DOC"` at `538`; `step_rows = step_rows[step_rows["doc_id"].notna()]` at `548`. |
| approver_raw forced to `"0-SAS"` for SAS rows | `568-569` (`np.where(step_type == "SAS", "0-SAS", actor_raw)`) | renames in place; downstream filters key on this. |
| TEMPORARY_COMPAT_LAYER — synth `response_date_raw` text from flat fields | `571-602` | none (encodes timestamps and pending text). |
| **Adapter writes back to ctx** | `188-195` | sets `ctx.docs_df`, `ctx.responses_df`, `ctx.ged_approver_names`, `ctx.mapping`, `ctx.flat_ged_mode = "flat"`, `ctx.flat_ged_ops_df`, `ctx.flat_ged_doc_meta`. |

**Special focus per §0.1:**
- Lines `538-569` mark the entry into the responses-df construction. Step rows in `ops_df` whose `step_type ∈ {SAS, CONSULTANT, MOEX}` cross this barrier; OPEN_DOC rows are dropped at `538`. SAS rows are tagged `approver_raw = "0-SAS"` at `568-569` so the downstream SAS-track audit (`approver_raw == "0-SAS"`) works.
- Empty `step_rows` short-circuit returns an empty DataFrame at `551`.

### B2 — `FLAT_GED.xlsx` (debugging/re-entry artifact)

Path: `output/intermediate/FLAT_GED.xlsx`. Sheets: `GED_RAW_FLAT`, `GED_OPERATIONS`. Built by `src/flat_ged_runner.build_flat_ged_artifacts` → `src/flat_ged.build_flat_ged` (frozen module). Registered as `FLAT_GED` artifact in `run_memory.db`.

`src/flat_ged/transformer.py` is the upstream builder of B2. Key transformations (operating on a single document at a time):
- `compute_phase_deadlines` (`278-307`) — derives `sas_phase_deadline` and `cm_deadline` from SAS response timing (`SAS_WINDOW_DAYS`, `GLOBAL_WINDOW_DAYS`). NOTE: `cm_deadline` is the SAME for primary and secondary consultants (no 10-day cap at this layer — see context/06 §F and `07_OPEN_ITEMS.md` #16).
- `compute_delay_contribution` (`539-577`) — distributes step delay across actors: `step_delay = max(0, eff_date - phase_deadline)`, `contribution = max(0, step_delay - cumulative_so_far)`. **Actor-type-agnostic** (PRIMARY/SECONDARY share `cm_deadline`).
- `determine_cycle_closure` (`581-619`) — three-state cycle: `MOEX_VISA` / `ALL_RESPONDED_NO_MOEX` / `WAITING_RESPONSES`. Mirrors stage_read_flat's `_derive_closure_mode`.

### B3 — Pickle cache layer (audit-critical)

File: `src/reporting/data_loader.py`

| Op | Lines | Effect |
|---|---|---|
| `_flat_cache_paths` — three sidecar pickles + json | `78-85` | docs_pkl, resp_pkl, meta_json next to FLAT_GED.xlsx. |
| `_flat_cache_is_fresh` — **mtime-only** freshness check | `88-97` | returns True iff every cache file's mtime > xlsx mtime. **No code-version key.** This is the H-2 hazard from `context/11_TOOLING_HAZARDS.md`: schema drift in `stage_read_flat.py` is invisible to the cache. P0 fix-now candidate (CACHE_SCHEMA_VERSION). |
| `_save_flat_normalized_cache` | `100-117` | writes pickles after first parse; non-fatal on error. |
| `_load_flat_normalized_cache` | `120-139` | returns cache content or `(None, None, None, None)` on miss. |

**Audit consequence.** When the cache is fresh, `responses_df` and `docs_df` returned to the consumer are the LAST PARSE'S OUTPUT. If `stage_read_flat.py` was changed (e.g. SAS row emission) between the cache's write time and now, the new logic is bypassed. This was the silent-zero SAS REF bug.

---

## C — Run Context (`load_run_context`)

File: `src/reporting/data_loader.py`. Public entry: `load_run_context(BASE_DIR, run_number=None)` (`639-881`).

### C0 — Path selection

| Branch | Lines | Trigger |
|---|---|---|
| Cache hit | `670-671` | same `run_number` since last call. |
| **FLAT_ARTIFACT** (default product path) | `710-719` | `_load_from_flat_artifacts` returned a non-None ctx. |
| **LEGACY_RAW_FALLBACK** | `721-873` | flat artifact missing or load failed. Logs `[LEGACY_RAW_FALLBACK]`. Re-parses raw GED via `read_ged`. |

### C1–C2 — `docs_df` / `dernier_df`

In flat mode, all rows in `ops_df` are ACTIVE so VersionEngine is skipped:
- `docs_df["is_dernier_indice"] = True` (`414`)
- `dernier_df = docs_df.copy()` (`415`)

Per `data_loader.py:414` (also documented in §4 of the Phase 0 plan): in FLAT_GED mode, `docs_df ≡ dernier_df`.

In legacy/raw mode (`766-779`): `VersionEngine(docs_df).run()` produces `versioned_df`; `dernier_df = versioned_df[versioned_df["is_dernier_indice"] == True]`. Reference: `src/version_engine.py:190` (class), `:201` (`run`), `:365` / `:497` (rows where `is_dernier_indice` is set True).

### C3 — `ctx.responses_df` (UNFILTERED)

Constructed by `normalize_responses(...)` (`src/normalize.py:392-423`). Adds:
- `approver_canonical` (mapped via `map_approver`, line 405-406)
- `is_exception_approver` (line 408)
- **Forced override:** `df.loc[df["approver_raw"] == "0-SAS", "is_exception_approver"] = True` (line 412). This means EVERY SAS row carries `is_exception_approver = True`, which is what the WorkflowEngine filter strips at C5.
- `date_answered`, `date_status_type`, `date_limite`, `status_clean`

This frame is what `ctx.responses_df` ultimately exposes. **It still includes SAS rows** because the filter happens later, on the WorkflowEngine's local copy.

### C4 — `ctx.workflow_engine`

`src/workflow_engine.py:WorkflowEngine`. Built at `data_loader.py:418` (flat path) or `:782` (legacy path).

After report-memory composition rebuilds the engine using effective responses (`data_loader.py:449` flat / `:809` legacy), `responses_df` IS replaced by the `effective_responses_df` for downstream consumers (`:451` / `:812`).

### C5 — `ctx.workflow_engine.responses_df` (FILTERED — silent dual-attribute)

File: `src/workflow_engine.py`. Lines `54-57`:

```
self.responses_df = responses_df.copy()
# Filter out exception approvers
self.responses_df = self.responses_df[
    ~self.responses_df["is_exception_approver"]
]
```

**Effect.** Drops every row where `is_exception_approver == True`. By C3 line 412, that includes every `approver_raw == "0-SAS"` row plus any other approver tagged as exception by `is_exception` (Exception List approvers from `consultant_mapping.py`, e.g. `"0-BET Géotech"`, the EXCEPTION_COLUMNS contractor columns).

The `_lookup` (`62-91`) and `_doc_approvers` (`93-98`) caches are built from this filtered frame.

**Operational dual-attribute hazard (H-3 in `context/11_TOOLING_HAZARDS.md`):**
- Code that needs the SAS track → MUST use `ctx.responses_df`.
- Code that drives MOEX visa / `_lookup` / deadline tracking → uses `ctx.workflow_engine.responses_df` (filter is correct here).

`contractor_quality._sas_refusal_rate` (`src/reporting/contractor_quality.py:184-196`) correctly reads `ctx.responses_df`. `_socotec_sus_rate` (`:206`) correctly reads `ctx.workflow_engine.responses_df` (Bureau de Contrôle is NOT an exception approver).

### C6 — `ctx.workflow_engine._lookup`

`src/workflow_engine.py:62-91`. Key: `(doc_id, approver_canonical)`. Stored values: `date_answered`, `status_clean`, `date_status_type`, `comment`, `approver_raw`. Tie-breaking priority `ANSWERED (2) > PENDING (1) > NOT_CALLED (0)`; ANSWERED ties broken by latest `date_answered`.

### C7 — Pre-computed focus columns (DERNIER ONLY)

File: `src/reporting/data_loader.py`. `_precompute_focus_columns(dernier_df, responses_df, workflow_engine, data_date_val)` at `526-636`.

Columns added IN PLACE on `dernier_df`:

| Column | Lines | Source |
|---|---|---|
| `_visa_global` | `557` | from `workflow_engine.compute_visa_global_with_date(doc_id)` (`549-551`). NOTE: in flat mode, the documented authoritative source is `ctx.flat_ged_doc_meta` via `get_visa_global` (`stage_read_flat.py:80-105`), but `_precompute_focus_columns` calls the engine directly (`data_loader.py:550`). For SAS REF docs the engine returns `(None, None)`, but those rows are typically backfilled by the meta path elsewhere — this is a known gap (see KNOWN_GAP at `stage_read_flat.py:368-371`). |
| `_visa_global_date` | `558` | same source as above; mapped to `.date()` if datetime. |
| `_last_activity_date` | `582` | max of `created_at` and grouped max `responses_df.date_answered` per doc_id (`562-580`). |
| `_days_since_last_activity` | `594` | `(data_date - _last_activity_date).days`. |
| `_earliest_deadline` | `610` | grouped min `date_limite` over PENDING responses (`597-606`). |
| `_days_to_deadline` | `622` | `(earliest_deadline - data_date).days`. |
| `_focus_priority` | `636` | tier 1-5 from `_days_to_deadline`. |

Also called: `compute_focus_ownership(dernier_df, workflow_engine, data_date_val)` (`data_loader.py:472` flat / `:840` legacy) — adds `_focus_owner` and `_focus_owner_tier`.

**Subtle:** `_precompute_focus_columns` returns silently if `data_date_val is None` (`541-542`). Downstream code that assumes the columns exist must guard.

---

## D — Chain Attribution

### D1 — `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json`

Refreshed at desktop startup by `Api._ensure_chain_data_fresh` (`app.py`) via `compute_all_chain_timelines` + `write_chain_timeline_artifact` (file `src/reporting/chain_timeline_attribution.py`). Disk-only, NOT in `run_memory.db`.

Per-chain JSON shape (sample chain `000001` from current artifact):

```
{
  "family_key": "000001",
  "numero": "000001",
  "indices": [{ indice, version_key, created_at, is_dernier, closure_type,
                review {start, end, days_actual, days_expected, delay_days,
                        is_open, attributed_to[]},
                rework {…} | null }],
  "totals": {"days_actual": int, "days_expected": int, "delay_days": int},
  "chain_long": bool,           # totals.days_actual > 120
  "cycle_depasse": bool,
  "attribution_breakdown": {actor_str: int_days, …},   # MOEX_CAP_REATTRIBUTED folded into "Maitre d'Oeuvre EXE"
  "attribution_cap_reattributed": int                  # raw days re-attributed by the cap
}
```

Constants:
- `CYCLE_REVIEW_DAYS = 30` (`chain_timeline_attribution.py:29`)
- `CYCLE_REWORK_DAYS = 15` (`:30`)
- `CHAIN_LONG_THRESHOLD_DAYS = 120` (`:31`)
- `SECONDARY_WINDOW_DAYS = 10` (`:32`)

Key transformations (audit-critical):
- `_cap_secondary_delays` (`113-158`) — applies the 10-day cap to `SECONDARY_CONSULTANT` rows; excess re-attributed to synthetic `MOEX_CAP_REATTRIBUTED` rows tagged `cap_synthetic=True`.
- `_attribute_phase_delay` (`161-226`) — review-closed (proportional), review-open (equal split among `focus_owners`), rework (100% to ENTREPRISE).
- `_build_indice_phases` (`229-395`) — closure_type ∈ {`MOEX_TERMINAL`, `MOEX_REF`, `IMPLICIT_NEXT_INDICE`, `BET_COMPLETE_NO_MOEX`, `OPEN`}; SAS-CYCLE_REQUIRED-REF special path at `321-341`.
- `_aggregate_breakdown` (`398-419`) — folds `MOEX_CAP_REATTRIBUTED` into canonical MOEX actor `"Maitre d'Oeuvre EXE"`; raw cap days surface separately.
- Dead-version override map (`580-593`) — relabels `attributed_to_actor` to `"DEAD"` / `"NO_ATTRIBUTION"` and zeroes `attributed_days` for the 30 entries in `context/dead_version_overrides.csv`. **JSON is unaffected** — the override only rewrites the CSV emission. Audit scripts that read JSON see the original attribution values.

### D2 — Chain + Onion CSVs

Path: `output/chain_onion/`. Files: `CHAIN_REGISTER.csv`, `CHAIN_VERSIONS.csv`, `CHAIN_EVENTS.csv`, `CHAIN_METRICS.csv`, `ONION_LAYERS.csv`, `ONION_SCORES.csv`, `CHAIN_NARRATIVES.csv`, `dashboard_summary.json`, `top_issues.json`, `CHAIN_ONION_SUMMARY.xlsx`.

Loader: `chain_timeline_attribution._load_chain_data` (`71-89`) reads `CHAIN_EVENTS`, `CHAIN_REGISTER`, `CHAIN_VERSIONS` only. Other CSVs are read by `chain_onion.query_hooks` and (indirectly) by `app.Api.get_chain_onion_intel`.

**Audit relevance.** Source for chain count, chain_long count, attribution_breakdown.

---

## E — Reporting Builders

### E1 — `contractor_fiche.build_contractor_fiche`

File: `src/reporting/contractor_fiche.py:37-373`.

Inputs: `ctx`, `contractor_code`, `focus_result`. Operates on `ctx.docs_df[ctx.docs_df["emetteur"] == contractor_code]` (`63`). No legacy filter applied here.

Outputs four blocks:
- **Block 1** (`110-183`) — submission timeline (monthly default; weekly when focus_enabled). New vs re-submission counted by `indice ∈ {"A","?","0","1"}`. SAS enrichment uses `we.compute_visa_global_with_date(did)` per doc (`138`, `175`).
- **Block 2** (`185-245`) — VISA result chart over `dernier_df` per emetteur. `visa ∈ {VSO, VAO, REF, SAS REF, Open}`.
- **Block 3** (`247-309`) — document table. Per-row `sas_result` from `ctx.responses_df` filtered to `(doc_id, approver_raw=="0-SAS")` (`257-262`).
- **Block 4** (`311-341`) — quality metrics: `sas_refusal_rate` here is `(REF + SAS REF)/total_current` over dernier (`335`) — DIFFERENT FORMULA from `contractor_quality._sas_refusal_rate` (which uses `ctx.responses_df` SAS-track answered rows). The two metrics are reported under the same name in different layers.

Block 4's `sas_refusal_rate` is a doc-level dernier rate; `contractor_quality.kpis.sas_refusal_rate.value` (E2) is the historical SAS-track REF rate. Phase 0 must verify which one the UI consumes for which surface.

### E2 — `contractor_quality.build_contractor_quality`

File: `src/reporting/contractor_quality.py:395-533`.

Inputs: `ctx`, `contractor_code`, `peer_stats`, `chain_timelines`.

Filters applied:
- `ctx.docs_df[ctx.docs_df["emetteur"] == contractor_code]` (`426`)
- `ctx.dernier_df[ctx.dernier_df["emetteur"] == contractor_code]` (`430`)
- `_apply_legacy_filter(emetteur_docs, contractor_code)` (`434`) — drops BENTIN_OLD rows for BEN only (no-op for other contractors).

Computations:
- Open / finished split (`438-446`) — uses `_visa_col(emetteur_dernier)` to find the visa column dynamically.
- `sas_refusal_rate` (`449`) — `_sas_refusal_rate(ctx, emetteur_docs)` at `167-196`. Uses `ctx.responses_df` (SAS-track including exception approvers): `(approver_raw == "0-SAS") AND date_answered.notna() → REF / total`.
- `dormant_ref` and `dormant_sas_ref` (`453-454`) — `_dormant_list` (`254-284`); filters `dernier` by `_visa_global == "REF"` / `"SAS REF"`, computes `_days_dormant = ref_today - date_visa`.
- `dormant_days_by_numero` (`457-464`) — used to extend contractor delay attribution (the 199% bug input).
- `chains` for this contractor (`467`) — `_chains_for_contractor(emetteur_docs, chain_timelines)` joins via `numero_set` (lines `125-131`).
- `pct_chains_long` (`470`) — `n_long / n_chains`.
- `delays` (`472-475`) — `[ _contractor_delay_for_chain(ch, canonical, code, dormant_days_by_numero) for ch in chains ]`. Per chain, sum is `attribution_breakdown[ENTREPRISE] + breakdown[canonical] + breakdown[code if != canonical] + dormant_days[numero]`. Defn `142-164`.
- `avg_contractor_delay_days` (`476`) — mean of `delays`.
- `polar_histogram` (`479`) — `_polar_histogram(delays)` (`224-251`); 12 displayed buckets `[10,20)..[110,120),120+`; `under_10_count` separated.
- **Long-chains panel (`481-493`) — AMP 199% bug location:**
  - `total_delay_in_long = sum(ch.totals.delay_days for ch in long_chains)` (`483-485`) — DOES NOT include dormant days.
  - `contractor_delay_in_long = sum(_contractor_delay_for_chain(ch, …, dormant_days_by_numero) for ch in long_chains)` (`486-489`) — DOES include dormant days.
  - `share_contractor_in_long = contractor_delay_in_long / total_delay_in_long` (`490-493`) — denominator excludes dormant; numerator includes dormant; ratio can exceed 1.0 when dormant time is large relative to attributed long-chain delay. **Phase 0 fix-now candidate.**
- `socotec_sus_rate` (`499`) — `_socotec_sus_rate` (`199-221`). Uses `ctx.workflow_engine.responses_df` (correct: Bureau de Contrôle is not an exception approver), groups Socotec answers, returns SUS share or None.

### E3 — `contractor_quality.build_contractor_quality_peer_stats`

Same file, `306-392`. Iterates `CONTRACTOR_REFERENCE` (29 codes), runs the per-contractor block above, computes median/p25/p75 across 29 (`_percentiles`, `287-299`). For `socotec_sus_rate`, `exclude_none=True` so contractors with no Socotec coverage do not skew the median.

### E4 — `consultant_fiche.build_consultant_fiche`

File `src/reporting/consultant_fiche.py`. Out of audit scope per §5 (consultant audit not yet ticketed); referenced for shape.

### E5 — `aggregator.compute_*`

File: `src/reporting/aggregator.py`.
- `compute_project_kpis` (`33-160`) — computes `by_visa_global` over `dernier_df` using `we.compute_visa_global_with_date`. SAS pending and SAS REF active counts at `120-130` (`approver_raw == "0-SAS"` over `ctx.responses_df`).
- `compute_contractor_summary` (`433-510`) — groups dernier by `emetteur`, counts visa per-emetteur. KPI `sas_ref_rate = (ref + sas_ref) / total` (`496`). NO legacy filter applied. NO dormant extension.
- `compute_consultant_summary` (`276+`) — out of scope for this audit step, referenced.

### E6 — `ui_adapter.adapt_*`

File: `src/reporting/ui_adapter.py`.
- `adapt_overview` (`61-…`) — flattens `dashboard_data` into `window.OVERVIEW` shape; computes `best_contractor` / `best_consultant` (≥10 docs, by `(VSO+VAO)/total`).
- `adapt_consultants` (`241-`) — sets `c.group ∈ {MOEX, Primary, Secondary}`.
- `adapt_contractors_list` (`287-314`) — filters `total_submitted ≥ 5` (`298-299`); calls `resolve_emetteur_name(code)` (from `contractor_fiche.py:17-25`) for canonical names; sorts by `docs DESC` (or `(focus_owned, docs) DESC` when focus enabled); caps at 50 (`314`).
- `adapt_contractors_lookup` (`317-323`) — code→canonical name dict.

---

## F — UI Adapters (`app.py`)

File: `app.py`.

| Method | Lines | Backing modules / pipeline |
|---|---|---|
| `get_dashboard_data` | `528-…` | `aggregator.compute_*` + `focus_filter.apply_focus_filter` + chain_onion narrowing. |
| `get_consultant_list` | (around `~570`) | `aggregator.compute_consultant_summary`. |
| `get_contractor_list` | `590-…` | `aggregator.compute_contractor_summary`. |
| `get_consultant_fiche` | `606-…` | `consultant_fiche.build_consultant_fiche`. |
| `get_contractor_fiche` | `623-637` | `contractor_fiche.build_contractor_fiche` + focus_result. |
| `get_overview_for_ui` | `1020-1033` | `get_dashboard_data` + `get_app_state` → `adapt_overview`. |
| `get_consultants_for_ui` | `1035-1047` | `get_consultant_list` → `adapt_consultants`. |
| `get_contractors_for_ui` | `1049-1064` | `get_contractor_list` → `adapt_contractors_lookup` + `adapt_contractors_list`. |
| `get_fiche_for_ui` | `1066-1068` | thin alias for `get_consultant_fiche`. |
| `get_contractor_fiche_for_ui` | `1070-1106` | `get_contractor_fiche` (E1) + canonical-name enrich + merge `payload["quality"] = build_contractor_quality(ctx, code, peer_stats=peer)` (E2/E3). |
| `get_chain_onion_intel` | `1108-1131` | reads `output/chain_onion/{top_issues,dashboard_summary}.json`; FR overlay from `narrative_translation.translate_top_issue`. |
| `get_chain_timeline` | `1133-1163` | `chain_timeline_attribution.load_chain_timeline_artifact` (D1). |

`_sanitize_for_json` wraps every public response (NaN scrubbing).

---

## G — Bridge + UI

| Window global | Source method | Path |
|---|---|---|
| `window.OVERVIEW` | `get_overview_for_ui` | `ui/jansa/data_bridge.js` |
| `window.CONSULTANTS` | `get_consultants_for_ui` | same |
| `window.CONTRACTORS` (lookup) | `get_contractors_for_ui` → `lookup` field | same |
| `window.CONTRACTORS_LIST` | `get_contractors_for_ui` → `list` field | same |
| `window.FICHE_DATA` | `get_fiche_for_ui` | same |
| `window.CONTRACTOR_FICHE_DATA` | `get_contractor_fiche_for_ui` | same |
| `window.CHAIN_INTEL` | `get_chain_onion_intel` | overview.jsx via bridge |

The UI is OUT-OF-SCOPE per §3 of the Phase 0 plan. Audit scripts stop at F (`get_contractor_fiche_for_ui` payload) and emit `[requires manual UI inspection]` for stage G.

---

## Row-count change points (consolidated audit checklist)

For each metric the audit script must compare counts at every step in this list that applies to it.

| Stage | Op | What can change a row count |
|---|---|---|
| A1 | `read_excel("Doc. sous workflow…")` | Excel sheet selection. |
| B1.1 | `_apply_sas_filter_flat` | Drops pre-2026 SAS-RAPPEL pairs. |
| B1.2 | `step_type=="OPEN_DOC"` (docs_df) | One row per active doc. |
| B1.3 | `step_type!="OPEN_DOC"` (responses_df) | One row per non-OPEN_DOC step. |
| B1.4 | `step_rows[step_rows.doc_id.notna()]` | Drops rows whose doc_id mapping failed (numero/indice mismatch). |
| B3 | Cache hit | Returns OLD parse — silent staleness. |
| C0 | `dernier_df = docs_df.copy()` (flat) / `is_dernier_indice==True` (raw) | All-active in flat; subset in raw. |
| C3 | `normalize_responses` adds `is_exception_approver`; force-true for `0-SAS` | No row drops, but tags SAS rows for downstream. |
| C5 | `~is_exception_approver` filter | Drops every SAS row + Exception List approver rows. |
| E2 | `_apply_legacy_filter` (BEN only) | Drops BENTIN_OLD sheet rows + pre-2026 BEN sheet rows. |
| E2 | `_chains_for_contractor` (numero set match) | Per-emetteur narrowing. |
| E2 | `_dormant_list` filters by `_visa_global == REF / SAS REF` | Defines dormant set; feeds `dormant_days_by_numero` extension. |
| E2 | `long_chains = [ch for ch in chains if ch.chain_long]` | Subset for share computation. |
| E5 | None except per-emetteur grouping. | |
| E6 | `total_submitted >= 5` | Drops emetteurs with <5 docs from CONTRACTORS_LIST. |
| E6 | `[:50]` cap | Truncates list to top 50. |

---

## Cross-references between layers

- **`ctx.responses_df` vs `ctx.workflow_engine.responses_df`** — see C5 above and `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B.0. The first is unfiltered (post-effective-responses composition); the second drops every `is_exception_approver=True` row. Audit scripts must explicitly state which one they read for each stage count.
- **Visa global source priority in flat mode** — `flat_ged_doc_meta` is authoritative (`stage_read_flat.py:80-105`), but `_precompute_focus_columns` and several reporters call `we.compute_visa_global_with_date(doc_id)` directly. For SAS REF docs the engine returns `(None, None)`. Known gap (`stage_read_flat.py:368-371`).
- **BENTIN legacy filter** — `_apply_legacy_filter` in `contractor_quality.py:41-70` is a CONTRACTOR-LAYER local filter; the canonical project-wide filter is `ExclusionConfig.SHEET_YEAR_FILTERS` applied during `stage_route` (NOT applied to `docs_df` in flat mode because flat mode skips the route stage's exclusion path). Result: BEN docs that pre-2026 survive in `ctx.docs_df` and must be stripped here.
- **10-day secondary cap** — `chain_timeline_attribution._cap_secondary_delays` re-attributes excess to `MOEX_CAP_REATTRIBUTED`. The Flat GED transformer's `compute_delay_contribution` does NOT cap (context/06 §F, 07_OPEN_ITEMS #16). chain_onion outputs (D2) are uncapped; the cap is applied only in the chain_timeline reader.

---

## Inventory of Phase 0 special-focus items (§0.1 deliverable list)

Each item below maps to an audit script (or scripts) that must verify it.

1. **`stage_read_flat.py:538-569`** — how many rows enter, how many exit, per row type.
   - Audit: `audit_visa_distribution.py` (count by step_type before/after the OPEN_DOC filter).
2. **`data_loader._load_flat_normalized_cache`** — cache freshness.
   - Audit: any script run twice (cache cold + cache warm); divergence post-rebuild flags H-2.
3. **`WorkflowEngine.__init__` filter `is_exception_approver`** — rows it removes.
   - Audit: `audit_sas_ref.py` (SAS rows before vs after C5).
4. **`data_loader._precompute_focus_columns`** — fields added on dernier_df vs docs_df.
   - Audit: spot-check `_visa_global` parity vs `flat_ged_doc_meta`.
5. **`contractor_quality._apply_legacy_filter`** — BENTIN_OLD filter.
   - Audit: `audit_visa_distribution.py` for BEN with/without filter.
6. **`aggregator` per-contractor counts** — `compute_contractor_summary` vs `contractor_fiche.block2`.
   - Audit: `audit_visa_distribution.py` cross-check.

---

## Change log

| Date | Change |
|---|---|
| 2026-04-29 | Initial inventory (Phase 0 Step 0.1, executed cold from PHASE_0_BACKEND_DEBUGGING.md). |
