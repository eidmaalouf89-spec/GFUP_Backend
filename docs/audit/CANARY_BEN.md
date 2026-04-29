# CANARY_BEN — Phase 0 Step 0.2

> Canary contractor trace for **BEN** (Bentin). Walks every metric in §5 of
> `PHASE_0_BACKEND_DEBUGGING.md` backwards through every pipeline stage,
> printing actual counts at each stage. Each metric ends with **AGREES**
> or **DIVERGES at stage X — reason: …**.
>
> Source: `outputs/canary_ben.py` (one-off canary script, kept under
> `outputs/` outside the project tree). Run against the cached
> `runs/run_0000/` artifact on 2026-04-29 with `ctx.data_date = 2026-04-10`.
> Stage codes follow `docs/audit/PIPELINE_INVENTORY.md`.

---

## 0. Environment + provenance

| Quantity | Value |
|---|---|
| Run number | 0 (only registered run) |
| `ctx.data_date` | 2026-04-10 |
| `FLAT_GED.xlsx` mtime | 2026-04-27 08:59 |
| `FLAT_GED_cache_meta.json` mtime (post-load) | 2026-04-29 19:08 (rewritten this session) |
| `ctx.docs_df` rows (project) | 4,834 |
| `ctx.dernier_df` rows (project) | 4,834 (in flat mode docs_df ≡ dernier_df) |
| `ctx.responses_df` rows (project) | 27,237 |
| `ctx.workflow_engine.responses_df` rows (project) | 22,403 |
| Δ (rows dropped by `is_exception_approver` filter) | **4,834** — one per active doc → matches the SAS-row count exactly |

The Δ above is the empirical confirmation of the H-3 hazard: every active doc has one SAS row in `ctx.responses_df`, and the WorkflowEngine constructor strips them all from its local copy. Per `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B.0 / `context/11_TOOLING_HAZARDS.md` H-3.

**Cache anomaly observed during canary:**
On first run in this session the FLAT_GED pickle cache failed to load with `[FLAT_CACHE] Cache load failed (non-fatal): (<StringDtype(storage='python', na_value=nan)>, …)`. This is a pandas version-mismatch unpickle error: cache was written with an older pandas serialization that current pandas can't decode. The mtime check (`_flat_cache_is_fresh`, `data_loader.py:88-97`) said the cache was fresh, so `_load_flat_normalized_cache` was attempted; it failed gracefully and the slow xlsx parse path ran. **Direct evidence of the H-2 hazard: schema/version drift invisible to mtime.** Adds weight to the P0 fix-now CACHE_SCHEMA_VERSION patch.

**JSON artifact corruption observed during canary:**
`output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json` is truncated mid-object. Parsed cleanly: **0 chains** (`json.JSONDecodeError: Expecting property name enclosed in double quotes: line 176830 column 1 (char 4270982)`). Tolerant parse recovers **2,687** out of an expected ~2,819 (per `output/chain_onion/CHAIN_REGISTER.csv`). The `.csv` companion (`CHAIN_TIMELINE_ATTRIBUTION.csv`) is also truncated mid-row. A `.corrupted_bak` copy from 2026-04-28 exists. **NEW finding for TRIAGE — see §11 below.**

---

## 1. Total documents (active dernier count)

| Stage | Source | Count |
|---|---|---|
| B1 | `FLAT_GED.xlsx::GED_OPERATIONS` rows where `emetteur=='BEN' AND step_type=='OPEN_DOC'` | 583 |
| B1 | distinct `(numero, indice)` for BEN | 583 |
| C1 | `ctx.docs_df[emetteur=='BEN']` | 583 |
| C2 | `ctx.dernier_df[emetteur=='BEN']` | 583 |
| E2 | `_apply_legacy_filter(ben_dernier, "BEN")` rows | **98** (485 pre-2026 dropped) |
| E2 | `quality.open_finished.total` | 98 |
| E1 | `fiche.total_submitted` | 583 |
| E1 | `fiche.total_current` | 583 |
| F5 | `payload["total_submitted"]` | 583 |
| F5 | `payload["quality"]["open_finished"]["total"]` | 98 |

**Verdict — DIVERGES at E1 vs E2 (legacy filter scope mismatch).**
Reason: `contractor_quality._apply_legacy_filter` (`contractor_quality.py:41-70`) drops BEN's pre-2026 sheet rows (485 docs). `contractor_fiche.build_contractor_fiche` does NOT apply this filter. Both numbers ship to the UI under the same payload (`get_contractor_fiche_for_ui`). The UI consumer must know which scope it is reading; otherwise rendering "583 total / 98 open" looks like a bug. **TRIAGE candidate D-101: documentation/known-limitation.**

---

## 2. Total submission attempts (all indices, history)

| Stage | Source | Count |
|---|---|---|
| B1 | total ops rows for BEN, all step types | 3,610 |
| B1 | distinct `(numero, indice)` (= attempts) | 583 |
| C1 | `ctx.docs_df[emetteur=='BEN']` | 583 |

In flat mode, `docs_df ≡ dernier_df` (per `data_loader.py:414`). The flat artifact contains only ACTIVE instances, so there are no historical-version rows above the latest. "Total submission attempts" in the audit's metric sense (all indices) is identical to "active dernier count" here — 583.

**Verdict — AGREES.** (Caveat: the §5 "all indices, all history available" framing assumes raw-mode access; in flat mode this is the same as #1.)

---

## 3. VSO / VAO / REF / HM / SUS counts on dernier

| Stage | Source | VSO | VAO | REF | SAS REF | HM | Open |
|---|---|---:|---:|---:|---:|---:|---:|
| B1 | MOEX `is_completed=True` status_clean (project-wide raw) | 2 | 2 | 42 | n/a | 15 | n/a |
| C7 / E2 | `_visa_global` over `ben_dernier_filt` | 0 | 0 | 0 | 0 | 0 | 98 |
| E5 | `compute_contractor_summary` (no legacy filter) over `dernier`| would group by emetteur (project-wide value not isolated in canary) | | | | | |

The B1 row above is the COMPLETED MOEX rows in `GED_OPERATIONS` for BEN (all 583 docs, including pre-2026). Counts: REF=42, HM=15, VAO=2, VSO=2 — matches the visa shape one would expect for a high-friction contractor.

After legacy filter (post-2026 only), all 98 BEN dernier are `Open` — none have a terminal MOEX visa or SAS REF yet. Reason: BEN is a recent re-engagement; their post-2026 docs are still mid-cycle.

**Verdict — AGREES (within scope).** The B1 numbers describe BEN's all-time visa distribution; E2/C7 numbers describe their post-2026 active state. Different scopes by design.

---

## 4. SAS REF count + rate

| Stage | Source | Count |
|---|---|---|
| B1 | `GED_OPERATIONS` SAS rows for BEN where `is_completed AND status_clean=='REF'` | 52 |
| B1 | SAS rows for BEN total | 583 |
| B1 | SAS status_clean distribution | VSO=531, REF=52 |
| C3 | `ctx.responses_df[approver_raw=="0-SAS"]` for BEN (unfiltered) | 583 |
| C3 | `ctx.responses_df[approver_raw=="0-SAS"]` for BEN (legacy-filtered doc_ids) | 98 |
| C3 | …of those, `date_answered.notna()` | 98 |
| C3 | …of those, `status_clean=="REF"` (= **SAS REF count for BEN**) | **8** |
| C5 | `ctx.workflow_engine.responses_df` SAS rows for BEN | **0** (filter drops them, by design) |
| E2 | `_sas_refusal_rate(ctx, emetteur_docs)` = 8 / 98 | 0.0816 |

**Verdict — AGREES across C3 → E2.**
**DIVERGES B1 vs E2 (52 vs 8) — reason: BENTIN_OLD legacy filter intentionally drops 485 pre-2026 BEN docs, of which 44 are historical SAS REFs.** Known limitation; documented in `context/06_EXCEPTIONS_AND_MAPPINGS.md` §D/§E.

C5 is intentionally 0 (H-3); any reporter that needs SAS-track signal MUST read `ctx.responses_df`. Confirmed `contractor_quality._sas_refusal_rate` does the right thing (`contractor_quality.py:184-196`).

---

## 5. Dormant REF / Dormant SAS REF count

| Stage | Source | Count |
|---|---|---|
| E2 | `_dormant_list(ben_dernier_filt, "REF", ref_today)` | 0 |
| E2 | `_dormant_list(ben_dernier_filt, "SAS REF", ref_today)` | 0 |

Reason: all 98 BEN dernier rows have `_visa_global == None` (Open). None have terminal REF/SAS REF on their latest indice — pre-2026 historical REFs were stripped by the legacy filter; post-2026 active docs have not yet reached terminal REF.

**Verdict — AGREES.** Direct consequence of #3 (all 98 are Open).

---

## 6. Chain count + chain_long count

| Stage | Source | Count |
|---|---|---|
| D2 | `CHAIN_REGISTER.csv` total family_keys | 2,819 |
| D1 | `CHAIN_TIMELINE_ATTRIBUTION.json` parsed cleanly | **0 (file truncated)** |
| D1 | tolerant parse (this canary) | 2,687 |
| E2 | `_chains_for_contractor(ben_docs_filt, chain_timelines)` | 97 |
| E2 | `_chains_for_contractor(ben_docs, chain_timelines)` (no legacy filter) | 373 |
| E2 | `chain_long for BEN` (legacy-filtered): | **5** |
| E2 | `pct_chains_long` (5/97) | 0.0515 |
| F5 | `payload["quality"]["long_chains"]["pct_long"]` | 0.0515 |

**Verdict — DIVERGES at D1 (artifact corrupt).**
2,687 chains recovered vs 2,819 expected → ~132 chains missing. For BEN: 1 numero (≥ 345000) MAY be in the missing set; the per-BEN chain count of 97 might therefore be off by at most 1. **TRIAGE candidate D-102: fix-now (regenerate the artifact + add atomic-write in `chain_timeline_attribution.write_chain_timeline_artifact`).**

`pct_chains_long = 0.0515` is internally consistent (E2 returned the same value as our manual computation).

---

## 7. Per-chain attribution (ENTREPRISE / named contractor / MOEX / others)

Aggregated `attribution_breakdown` across BEN's 97 legacy-filtered chains:

| Actor | Total days |
|---|---:|
| MOEX (`Maitre d'Oeuvre EXE` raw key surfaces as `MOEX`) | 1,625 |
| ENTREPRISE | 1,166 |
| AVLS | 904 |
| Le Sommer Environnement | 526 |
| ARCHITECTE | 266 |
| BEN | 207 |
| Hardel + Le Bihan Architectes | 183 |
| SOCOTEC | 142 |
| BET Electricité | 101 |
| AMO HQE | 7 |

`_contractor_delay_for_chain(ch, "Bentin", "BEN", dormant)` adds:
`ENTREPRISE + breakdown["Bentin"] (=0, key absent) + breakdown["BEN"] (=207) + dormant_days[numero] (=0)` per chain. Sum across 97 chains → 1,166 + 0 + 207 + 0 = **1,373 contractor-attributable days**, of which **1,025** fall in the 5 long chains (see §9).

**Verdict — AGREES** between direct breakdown sum and the helper's accumulation. Note: the canonical name `"Bentin"` does not appear as an attribution key — only the code form `"BEN"` does. The helper's `code != canonical` branch at `contractor_quality.py:159` does the right thing here.

---

## 8. avg_contractor_delay_days

| Stage | Source | Value |
|---|---|---|
| E2 | mean of `_contractor_delay_for_chain` over 97 chains | 14.1546 |
| F5 | `payload["quality"]["kpis"]["avg_contractor_delay_days"]["value"]` | 14.1546 |

For BEN, `dormant_days_by_numero` is empty (no dormant REF/SAS REF on dernier — see §5), so the dormant-time extension contributes zero. The numerator and denominator are both purely from `attribution_breakdown` here.

**Verdict — AGREES.** The dormant-time extension does not affect BEN; this metric is the same with or without the extension for this contractor.

---

## 9. share_contractor_in_long_chains (the AMP 199% bug location)

| Quantity | Value |
|---|---:|
| `total_delay_in_long` (sum of `chain.totals.delay_days` for 5 long chains) | 2,177 |
| `contractor_delay_in_long` WITH dormant ext (current code) | 1,025 |
| `contractor_delay_in_long` WITHOUT dormant ext (control) | 1,025 |
| `share_contractor_in_long_chains` (current code) | **0.4708** |
| `share_contractor_in_long_chains` (dormant stripped from numerator) | 0.4708 |

**Verdict — AGREES for BEN (and the value is mathematically valid: 47% ≤ 100%).**

**Why BEN doesn't show 199%:** `dormant_days_by_numero` is empty (BEN has 0 dormant REF / 0 dormant SAS REF — all 98 are Open). The numerator = denominator-input contribution; the formula's pathology requires (a) dormant REF/SAS REF docs AND (b) those numeros being in `long_chains`. AMP must satisfy both. The audit script for this metric (Step 0.3 `audit_share_long.py`) must verify this pathology across all 29 contractors — BEN proves the formula is consistent in the no-dormant case but does NOT prove the AMP path.

---

## 10. SOCOTEC FAV/SUS/DEF + SUS rate

| Stage | Source | Count |
|---|---|---|
| C5 | SOCOTEC answered (project-wide via `workflow_engine.responses_df` filtered to Bureau de Contrôle) | 890 |
| C5 | SOCOTEC answered for BEN (legacy-filtered doc_ids) | 4 |
| C5 | distribution | FAV=4, SUS=0, DEF=0 |
| E2 | `socotec_sus_rate` = 0/4 | 0.0 |

**Verdict — AGREES.** Sample size is tiny (4) — not statistically meaningful, but the audit just verifies traceability.

---

## 11. Polar histogram bucket distribution

| Bucket | Count |
|---|---:|
| 0-10 (under_10_count, displayed separately) | 89 |
| 10-20 | 1 |
| 20-30 | 0 |
| 30-40 | 1 |
| 40-50 | 0 |
| 50-60 | 0 |
| 60-70 | 2 |
| 70-80 | 0 |
| 80-90 | 0 |
| 90-100 | 0 |
| 100-110 | 0 |
| 110-120 | 0 |
| 120+ | 4 |
| **Total** | 97 |

`max_count` (over the 12 displayed buckets) = 4 (the `120+` bucket).

**Verdict — AGREES.** `under_10` (89) + displayed buckets (1+1+2+4 = 8) = 97 = chain count. Conservation holds.

---

## 12. E1 vs E2 `sas_refusal_rate` (different formulas, same name)

| Surface | Formula | Value for BEN | Scope |
|---|---|---:|---|
| E1 `block4_quality.sas_refusal_rate` | `(REF + SAS REF on dernier) / total_current` | 0.072 | Over all 583 BEN dernier rows (no legacy filter); engine returns visa for pre-2026 docs |
| E2 `kpis.sas_refusal_rate.value` | SAS-track REF count / SAS-track answered count (over `ctx.responses_df`, legacy-filtered) | 0.0816 | Over the 98 post-legacy-filter BEN docs |

Both fields ship to the UI inside the same `get_contractor_fiche_for_ui` payload. UI must know which is which.

**Verdict — DIVERGES at E1 vs E2 (different formulas under the same name).**
Reason: legacy-filter scope + numerator/denominator definitions both differ. **TRIAGE candidate D-103: documentation/known-limitation. The two values are both legitimate; renaming one would be the cleanest fix.** Currently a UI consumer cannot know which one is the "operationally correct" rate without reading both modules' source.

---

## 13. Cache + WorkflowEngine filter behavior (audit-critical)

| Quantity | Project-wide | BEN |
|---|---:|---:|
| `ctx.responses_df` rows | 27,237 | 583 (unfiltered) / 98 (filtered) |
| `ctx.workflow_engine.responses_df` rows | 22,403 | (BEN SAS rows) 0 |
| Δ (filter drop) | 4,834 | (the 583 unfiltered SAS rows for BEN are inside this 4,834) |

Δ exactly equals `len(ctx.dernier_df)` (4,834) → one SAS row dropped per active doc. Empirical proof of the dual-attribute hazard (H-3).

**Verdict — AGREES with the documented hazard.**
**Phase 0 also surfaced a NEW direct manifestation of H-2:** the cache load failed on first run this session due to pandas version drift (the StringDtype unpickle error). Mtime-only freshness was not sufficient to keep the cache valid. **Strongest possible evidence for the CACHE_SCHEMA_VERSION fix-now patch in §0.6.**

---

## 14. NEW Findings (feed into TRIAGE.md at Step 0.5)

| ID candidate | Stage | Description | Classification (proposed) |
|---|---|---|---|
| **D-101** | E1 vs E2 (same payload) | `total_submitted` (583, no legacy filter) vs `quality.open_finished.total` (98, with legacy filter) under same fiche payload | known limitation — document or rename one |
| **D-102** | D1 (artifact) | `CHAIN_TIMELINE_ATTRIBUTION.json` truncated (4,448,537 bytes on disk; valid JSON ends at byte 4,270,982). 132 chains missing. `.csv` similarly truncated mid-row. | **fix-now** — regenerate artifact + add atomic write to `write_chain_timeline_artifact` |
| **D-103** | E1 vs E2 | Two different `sas_refusal_rate` formulas under same name in same UI payload | known limitation — document or rename |
| **D-104** | B3 cache | `[FLAT_CACHE] Cache load failed (non-fatal)` due to pandas StringDtype unpickle drift, even though mtime check said cache was fresh | **fix-now** — confirms CACHE_SCHEMA_VERSION P0 |
| **D-105** | C5 (project-wide) | `len(ctx.responses_df) - len(ctx.workflow_engine.responses_df) = 4,834 = len(ctx.dernier_df)` | known limitation — already documented (H-3); add the equality as a sanity-check assertion in `data_loader._load_from_flat_artifacts` |
| **D-106** | (out of scope here) | The 199% bug for AMP cannot be observed from BEN alone — Step 0.4 must verify across 29 contractors | needs investigation — assigned to `audit_share_long.py` |

---

## 15. Audit script template (BEN canary as reference)

The canary script `outputs/canary_ben.py` defines the count-extraction pattern Step 0.3 will productize. Key reusable helpers to extract into `scripts/audit/_common.py`:

1. `load_ctx_with_pyc_shim(BASE)` → wraps `load_run_context` with the stale-pyc workaround (inject `resolve_emetteur_name` if missing).
2. `load_chain_timelines_tolerant(path)` → reads JSON; on `JSONDecodeError`, falls back to bracket-matched per-key parser. Used until D-102 is fixed.
3. `apply_legacy_filter(df, code)` → wraps `contractor_quality._apply_legacy_filter` (BEN-only no-op for others).
4. `count_table(stage_counts: dict[str, int])` → renders the §6 stage-by-stage table format.
5. `convergence_verdict(stage_counts)` → returns `"ALL EQUAL"` or `"DIVERGENCE AT <stage>"`.

---

## 16. Change log

| Date | Note |
|---|---|
| 2026-04-29 | Initial canary trace from `outputs/canary_ben.py`. Surfaced D-101..D-106. Tolerant parse used for the corrupt JSON. |
