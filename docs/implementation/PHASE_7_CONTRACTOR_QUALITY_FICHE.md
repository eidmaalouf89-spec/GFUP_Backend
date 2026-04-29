# Phase 7 — Contractor Quality Fiche (RESCOPED)

This MD is **self-contained**. An agent assigned only this phase can execute it cold without reading any other file in `docs/implementation/`.

This phase **supersedes** the prior `PHASE_7_CONTRACTOR_FICHE_WIRING.md`, which proposed mirroring the consultant fiche. That approach is dead: the consultant fiche components in `fiche_base.jsx` are tightly coupled to a consultant-shaped data payload (`data.consultant`, `data.header.{week_num,total,s3_count,…}`, `data.bloc1`, etc.) that the contractor builder does not produce. The contractor fiche is now a **purpose-built quality dashboard** designed around contractor-specific operational signals.

The Step 2 wrapper (`get_contractor_fiche_for_ui`) and Step 3 bridge (`loadContractorFiche`) added under the prior plan **remain valid** and are reused. They will carry a richer payload after Step 5 below.

---

## 1. Objective

Build a contractor quality fiche that surfaces actionable operational signals — chain health, document quality, dormant work, and regulatory risk — for one contractor at a time, with peer comparison across all 29 contractors. Wire the existing dashboard "Entreprise de la semaine" card and Contractors-tab cards to open the new page.

---

## 2. Risk

**HIGH.** New backend module (`contractor_quality.py`), extension of `app.py` UI wrapper, new ~500-line UI page with a novel polar-histogram visual primitive, and shell/dashboard/contractors-tab wiring. Touches 7 files (1 new backend, 1 new UI, 5 modified).

Stop and escalate if:
- `ctx.workflow_engine.responses_df` does not contain `approver_canonical`, `status_clean`, `date_answered`, `doc_id` columns as expected.
- Chain attribution artifact at `output/intermediate/` is missing or empty (Phase 7 cannot compute long-chain contractor share without it).
- Any V1 widget below cannot be computed from the documented data sources without additional pipeline work.

---

## 3. Standard Rules (embedded — do not skip)

### Tooling note
Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) for inspecting Windows-mounted source files (`app.py`, `src/reporting/*.py`, `ui/jansa/*.jsx`). The Linux mount caches stale views. Bash is fine for *executing* scripts (running `python -c`, `pytest`, `python -m py_compile`). See `context/11_TOOLING_HAZARDS.md`.

### Priorities
1. App must always run.
2. Backend stays source of truth — the UI calculates nothing.
3. Preserve all existing logic. The new backend module is a **sibling** of `contractor_fiche.py`, never a mutation of it.
4. Minimal safe changes. Every metric in V1 has been justified by user instruction.
5. No fake certainty. If a metric cannot be computed cleanly, defer it to V2.

### Mandatory behavior
- Read `src/reporting/contractor_fiche.py`, `src/reporting/chain_timeline_attribution.py`, and `src/workflow_engine.py` before writing the new module.
- Confirm the chain attribution artifact at `output/intermediate/chain_timelines.json` (or whatever the canonical filename is — verify via `load_chain_timeline_artifact`) exists and contains `attribution_breakdown` per chain.
- Confirm `ctx.workflow_engine.responses_df` exposes the expected columns before writing the SOCOTEC SUS aggregation.
- The new page must inline-copy design tokens (FONT_UI, FONT_NUM, color palette, formatters `fmt`/`pct`) from `fiche_base.jsx` rather than editing `fiche_base.jsx` to expose them. Visual continuity through duplication is intentional.
- All KPI tiles in the strip must show a peer band (median + p25/p75) computed from the same module. This is what makes the fiche operationally useful — single numbers without context are noise.
- Loading and error states must be explicit (spinner during load, friendly message if payload `quality` field is `{error: …}`).

### Forbidden moves
- Do NOT modify `src/reporting/contractor_fiche.py` business logic. The new module is a sibling.
- Do NOT modify `ui/jansa/fiche_base.jsx`. Inline-copy what you need.
- Do NOT modify pipeline stages, chain_onion, run_memory, report_memory.
- Do NOT change routing names of existing routes (`Consultants`, `ConsultantFiche`, `Contractors`).
- Do NOT cache the quality payload on the Python side. Recompute per call. (Optimize later if perf becomes an issue.)
- Do NOT compute contractor metrics in the JSX. Backend is source of truth.

---

## 4. V1 / V2 Scope

### V1 — this phase

| # | Widget | Backend metric | Source |
|---|---|---|---|
| H | Header | `contractor_name` (canonical), `contractor_code`, `lots[]`, `buildings[]`, `total_submitted`, `total_open` | `build_contractor_fiche` (existing) + `total_open` derived |
| K1 | KPI: SAS REF rate | `sas_refusal_rate` + peer median + p25/p75 | `block4_quality.sas_refusal_rate` (existing) + new peer aggregation |
| K2 | KPI: Dormant REF count | count of REF docs where contractor has not yet resubmitted | docs_df + dernier_df |
| K3 | KPI: % chains > 120d | per contractor: chains exceeding threshold / total chains | `chain_long` from chain_timeline_attribution |
| K4 | KPI: Avg contractor-attributed delay per chain | mean of `attribution_breakdown.ENTREPRISE` (and the contractor's named attribution if present) per chain | chain_timeline_attribution |
| K5 | KPI: SOCOTEC SUS rate | per contractor: SUS Socotec answers / total Socotec answers | `responses_df` filtered to "Bureau de Contrôle" |
| O | Open/finished chains | open_count, finished_count, ratio | derived from CHAIN_REGISTER + docs_df |
| P | Polar delay histogram | 13 buckets (12 × 10-day + 120+) of contractor-attributed delay days per chain | `attribution_breakdown.ENTREPRISE` per chain, bucketed |
| L | Long-chains panel | `pct_long_chains` + `share_contractor_attributed_in_long_chains` | derived from chain_long flag + attribution_breakdown |
| D1 | Dormant REF queue | docs where last visa = REF and no newer indice exists | docs_df + dernier_df, sorted newest→oldest by date_visa |
| D2 | Dormant SAS REF queue | same with last visa = "SAS REF" | docs_df + dernier_df |

All KPI tiles K1–K5 carry a peer band (project-wide median + p25/p75 across all 29 contractors).

### V2 — deferred (future Phase 8 or later)

- Top 5 worst chains (by contractor-attributed delay) with chain timeline drilldown
- Rework intensity timeline (monthly stacked chart)
- First-pass success rate (% docs VAO/VSO at indice A)
- Aging buckets for open submittals (0–30 / 30–60 / 60–90 / 90+ days)
- Lot exposure × performance (per-lot sub-stats)

---

## 5. Backend Data Sources (verified — all cache-backed, NO xlsx reads)

The pipeline already maintains an intermediate cache layer. The new module MUST use these fast paths exclusively. No `pd.read_excel`, no flat_ged xlsx parsing.

| Need | Source | Format | Access pattern |
|---|---|---|---|
| Contractor docs | `ctx.docs_df` | pickle cache `FLAT_GED_cache_docs.pkl` (auto-loaded by `data_loader._load_flat_normalized_cache`) | already used by `build_contractor_fiche` — filter by `emetteur` |
| Latest indice per doc | `ctx.dernier_df` | derived in-memory from cached docs | already used |
| Approver responses (incl. Socotec) | `ctx.workflow_engine.responses_df` | pickle cache `FLAT_GED_cache_resp.pkl` (auto-loaded) | filter `approver_canonical == "Bureau de Contrôle"`, `status_clean.notna() & date_answered.notna()`, then join `doc_id → docs_df.emetteur` |
| Chain attribution | `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json` | JSON | `from reporting.chain_timeline_attribution import load_chain_timeline_artifact; load_chain_timeline_artifact(BASE_DIR / "output" / "intermediate")` — same call site pattern as `app.py:1108` and `document_command_center.py:170`. Returns `dict[family_key → chain_payload]` where `chain_payload["attribution_breakdown"]` is `dict[actor_name → total_delay_days]` for that chain. |
| Visa global per doc | `ctx.docs_df.visa_global` | already in cached docs_df (set by `WorkflowEngine.compute_visa_global`) | already used |

**Performance discipline:**
- Load `CHAIN_TIMELINE_ATTRIBUTION.json` **once per request** at the entry point (e.g. `build_contractor_quality_peer_stats`) and pass into per-contractor calls. Do NOT reload per contractor.
- Same for `responses_df` filtering: pre-filter to Socotec-answered rows once, then group by emetteur.
- Both source structures are already in memory via `ctx`; the only real I/O is the JSON load (~tens of ms at most).

**Actor name matching for contractor-attributed delay:**
- `attribution_breakdown` keys are actor names (strings). Per the attribution rules in `chain_timeline_attribution.py:178-179`, **rework** delay is always tagged with actor `"ENTREPRISE"` (the umbrella contractor bucket — by definition this maps to the chain's emetteur). **Review** delay attributed to a contractor uses the actor's actual name (line 339: `actor = str(submittal_rows.iloc[0]["actor"])`).
- Per-chain contractor-attributed delay = `attribution_breakdown.get("ENTREPRISE", 0) + attribution_breakdown.get(<contractor_canonical_name>, 0)`.
- Verify the canonical-name format used in `actor` during Step 4 implementation. If actor is the emetteur code rather than the canonical name, adjust the lookup accordingly. **Do not assume; print one chain's `attribution_breakdown` during smoke test to confirm.**

**Constants already in code** (do not redefine):
- `CHAIN_LONG_THRESHOLD_DAYS = 120` (chain_timeline_attribution.py:31)
- `CYCLE_REVIEW_DAYS = 30`, `CYCLE_REWORK_DAYS = 15`
- Socotec status codes: `FAV / SUS / DEF` (consultant_transformers.py, aggregator.py:273)
- MOEX visa codes: `{VAO, VSO, REF, HM, SUS}` (normalize.py:23 `VALID_STATUSES`); plus derived `SAS REF` and `VSO-SAS`.

**Visa code semantics for "finished" vs "open" chains** (per user spec — see §7 Step 4):
- **Finished (terminal approval): `{VSO, VAO, HM}` only.**
- **Open: `{REF, SAS REF, SUS, VSO-SAS, ""/null}`**. `VSO-SAS` is a conformity gate, not a final document approval — it does NOT count as finished.

---

## 6. Files

### READ (required, before any edit)
- `src/reporting/contractor_fiche.py` — full file (existing builder, preserves contract)
- `src/reporting/chain_timeline_attribution.py` — `load_chain_timeline_artifact` + `_aggregate_breakdown` shape
- `src/workflow_engine.py` lines 50–100 — `responses_df` columns + `_doc_approvers` shape
- `src/reporting/data_loader.py` — `RunContext` shape, `dernier_df` columns
- `app.py` lines 620–640 (existing `get_contractor_fiche`) and 1066–1085 (`get_fiche_for_ui` + `get_contractor_fiche_for_ui` from prior step)
- `ui/jansa/fiche_base.jsx` lines 75–95 (design tokens, formatters) — for inline-copying only
- `ui/jansa/data_bridge.js` lines 124–150 (`loadContractorFiche` from prior step)
- `ui/jansa/shell.jsx` (consultant fiche nav handler ~lines 600–680, route map)
- `ui/jansa/overview.jsx` (BestPerformerCard for Entreprise ~line 154)
- `ui/jansa/contractors.jsx` (ContractorCard ~line 119)
- `ui/jansa-connected.html` (script tag list)

### MODIFY
- `app.py` — extend `get_contractor_fiche_for_ui` (line 1070) to also call `build_contractor_quality(ctx, code)` and merge result under `payload["quality"]`.
- `ui/jansa/shell.jsx` — add `selectedContractor` state, `onOpenContractor` handler, `ContractorFiche` route, pass `onOpenContractor` to `OverviewPage` and `ContractorsPage`.
- `ui/jansa/overview.jsx` — `OverviewPage` and `KpiRow` accept `onOpenContractor`; Entreprise `BestPerformerCard` `onClick` → `onOpenContractor(data.best_contractor)`.
- `ui/jansa/contractors.jsx` — `ContractorsPage` accepts `onOpenContractor`; `ContractorCard` becomes clickable; `ContractorChip` (low-doc fallback) stays non-clickable, with a brief comment explaining why.
- `ui/jansa-connected.html` — add `<script src="ui/jansa/contractor_fiche_page.jsx">` next to existing JSX tags, after `fiche_base.jsx`.

### CREATE
- `src/reporting/contractor_quality.py` — new sibling module. Public function `build_contractor_quality(ctx, contractor_code: str) -> dict`. Also exports `build_contractor_quality_peer_stats(ctx) -> dict` (computed once per call when needed for peer bands).
- `ui/jansa/contractor_fiche_page.jsx` — new file. Exports `ContractorFichePage`. Self-contained: inline tokens from `fiche_base.jsx`, polar histogram as inline SVG.

### DO NOT TOUCH
- `src/reporting/contractor_fiche.py` business logic
- `src/reporting/consultant_fiche.py`
- `src/reporting/data_loader.py`
- `src/reporting/aggregator.py`, `focus_filter.py`, `focus_ownership.py`, `ui_adapter.py`, `chain_timeline_attribution.py` (read only)
- `src/chain_onion/`, `src/flat_ged/`, `src/run_memory.py`, `src/report_memory.py`, `src/team_version_builder.py`, `src/effective_responses.py`, `src/pipeline/stages/*`
- `runs/run_0000/`, `data/*.db`, `output/intermediate/*` (read only for the artifact)
- `ui/jansa/fiche_base.jsx` (read only — inline-copy tokens; do NOT edit to expose them)
- `ui/jansa/fiche_page.jsx`, `consultants.jsx`, `document_panel.jsx`, `runs.jsx`, `executer.jsx`
- All other UI files except those in §MODIFY/CREATE

---

## 7. Plan (high-level — per-step Cowork prompts will be generated by the team lead inline at execution time)

### Step 4 — Build `src/reporting/contractor_quality.py`
Public surface:
```python
def build_contractor_quality(ctx, contractor_code: str, peer_stats: dict | None = None) -> dict:
    """Return V1 quality payload for one contractor. Pass precomputed peer_stats
    to avoid recomputing across multiple contractors in one request."""

def build_contractor_quality_peer_stats(ctx) -> dict:
    """Precompute project-wide peer stats (median + p25/p75) across all 29
    contractors for the 5 KPI metrics. Returns {metric_name: {median, p25, p75}}."""
```

Return shape (from `build_contractor_quality`):
```python
{
    "contractor_code": str,
    "kpis": {
        "sas_refusal_rate":          {"value": float, "peer": {median, p25, p75}},
        "dormant_ref_count":         {"value": int,   "peer": {median, p25, p75}},
        "pct_chains_long":           {"value": float, "peer": {median, p25, p75}},
        "avg_contractor_delay_days": {"value": float, "peer": {median, p25, p75}},
        "socotec_sus_rate":          {"value": float, "peer": {median, p25, p75}},
    },
    "open_finished": {"open": int, "finished": int, "total": int},
    "polar_histogram": {
        "buckets": [
            {"label": "0-10",   "lo": 0,   "hi": 10,  "count": int},
            …  # 12 fixed-width 10-day buckets
            {"label": "110-120","lo": 110, "hi": 120, "count": int},
            {"label": "120+",   "lo": 120, "hi": None,"count": int},
        ],
        "max_count": int,
    },
    "long_chains": {
        "pct_long":                       float,
        "share_contractor_in_long_chains": float,  # of total delay in long chains, % attributable to ENTREPRISE
    },
    "dormant_ref":      [ {"numero", "indice", "titre", "date_visa", "days_dormant", "lot_normalized"}, …],
    "dormant_sas_ref":  [ same shape ],
}
```

Implementation notes:
- "Dormant" = doc where latest indice's visa is REF (or SAS REF) AND that doc's emetteur is the contractor AND no newer indice exists in dernier for that numero. Sort: newest-first by `date_visa` (= least dormant at top).
- **Polar histogram metric (per user spec): contractor-share only, NOT total chain delay.** Per chain owned by this contractor: take `attribution_breakdown.get("ENTREPRISE", 0) + attribution_breakdown.get(<contractor_canonical>, 0)` — this is days of delay this contractor specifically caused inside that chain, ignoring delays caused by other actors. Bucket each chain by this contractor-attributed total. Buckets: 12 fixed-width 10-day buckets `[0,10) [10,20) … [110,120)` plus a 13th `120+` outlier bucket (`hi: None`).
- Peer stats: precompute once per request (one pass over all contractors) and pass into `build_contractor_quality` to avoid 29× recomputation. Same applies to the chain attribution JSON — load once at the entry point, pass `chain_timelines` dict into per-contractor calls.
- SOCOTEC SUS: filter `responses_df` to `approver_canonical == "Bureau de Contrôle"`, drop nulls (`status_clean.notna() & date_answered.notna()`), join `doc_id → docs_df.emetteur`. Per emetteur: `(status_clean == "SUS").sum() / answered.count()`. Project-wide peer band same way over all emetteurs.
- **Open/finished chains (per user spec): a chain is "finished" if its dernier indice's `visa_global` is in `{VSO, VAO, HM}`. Open otherwise — including REF, SAS REF, SUS, VSO-SAS, or no visa.** `VSO-SAS` is a conformity gate, NOT a document approval, so it counts as open.
- Chain attribution requires loading `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json` artifact. If the artifact is missing or unreadable, the module's entry point should return `{"error": "chain attribution artifact missing — run pipeline"}`. The wrapper in app.py wraps in try/except so a missing artifact degrades the quality payload to `{error: …}` without breaking the rest of the fiche.
- **No xlsx reads anywhere.** All data flows through `ctx.docs_df` / `ctx.dernier_df` / `ctx.workflow_engine.responses_df` (cache-backed) and the JSON artifact.

### Step 5 — Extend `app.py::get_contractor_fiche_for_ui`
After the existing canonical-name enrichment, also call `build_contractor_quality(ctx, contractor_code)` and merge under `payload["quality"]`. Wrap in try/except so a quality-payload error degrades to `payload["quality"] = {"error": str(exc)}` rather than failing the whole fiche.

The `_for_ui` wrapper now has TWO ctx-using calls. To avoid loading the run context twice, refactor only the wrapper internals — do not touch `get_contractor_fiche` (line 623) or change its public signature. Use a single `load_run_context(BASE_DIR)` call at the wrapper level and pass `ctx` explicitly to a refactored helper, OR accept the duplicate load if it's fast enough (~hundreds of ms). Prefer the simpler path; optimize only if smoke tests show >2s latency.

### Step 6 — Create `ui/jansa/contractor_fiche_page.jsx`
Self-contained file. Structure:
1. Inline design tokens copied from `fiche_base.jsx` (FONT_UI, FONT_NUM, color palette `C`, `TOK`, formatters `fmt` and `pct`). ~30 lines.
2. Helper components: `KpiTileWithPeerBand`, `PolarHistogram` (inline SVG), `DormantQueueRow`, `OpenFinishedRing`.
3. `ContractorFichePage({ contractor, onBack, focusMode })` — reads `window.CONTRACTOR_FICHE_DATA`, handles loading + error states, renders sections in order: Header → KPI strip → Polar histogram → Long-chains panel → Open/finished → Dormant REF queue → Dormant SAS REF queue.
4. `Object.assign(window, { ContractorFichePage });`

Drilldowns:
- Dormant REF/SAS REF rows: `onClick={() => window.openDocumentCommandCenter(numero, indice)}`.
- KPI tiles, polar histogram sectors, long-chains panel: no drilldown in V1 (deferred to V2).

### Step 7 — Wire `ui/jansa/shell.jsx`
Add `selectedContractor` state alongside `selectedConsultant`. Add async `onOpenContractor(c)` handler that calls `jansaBridge.loadContractorFiche(c.code, focusMode, staleDays)` then `navigateTo('ContractorFiche')`. Add route `{active === 'ContractorFiche' && <ContractorFichePage contractor={selectedContractor} onBack={() => navigateTo('Contractors')} focusMode={focusMode}/>}`. Pass `onOpenContractor` to `<OverviewPage>` and `<ContractorsPage>`.

### Step 8 — Wire `ui/jansa/overview.jsx`
`OverviewPage` accepts `onOpenContractor`. `KpiRow` passes it and `data.best_contractor` to the Entreprise `BestPerformerCard`. Replace `onClick={() => onNavigate('Contractors')}` with `onClick={() => onOpenContractor(data.best_contractor)}`.

### Step 9 — Wire `ui/jansa/contractors.jsx`
`ContractorsPage` accepts `onOpenContractor`. `ContractorCard` becomes clickable (`onClick={() => onOpenContractor(c)}`, `cursor: 'pointer'`, hover styling). `ContractorChip` (low-doc fallback) stays non-clickable with a brief comment ("backend builder may have insufficient data for a useful fiche on these").

### Step 10 — Register JSX in `ui/jansa-connected.html`
Add `<script type="text/babel" data-presets="react" src="ui/jansa/contractor_fiche_page.jsx"></script>` next to existing JSX tags, after `fiche_base.jsx` (which exposes `DrilldownDrawer`).

### Step 11 — Validation, report, context update
See §8 below.

---

## 8. Validation

| Check | How |
|---|---|
| Module compiles | `python -m py_compile src/reporting/contractor_quality.py app.py` |
| Backend smoke | `python -c "from app import Api; api=Api(); api._cache_ready.wait(); p=api.get_contractor_fiche_for_ui('BEN'); assert 'quality' in p; assert 'kpis' in p['quality']; assert all(k in p['quality']['kpis'] for k in ['sas_refusal_rate','dormant_ref_count','pct_chains_long','avg_contractor_delay_days','socotec_sus_rate']); print('OK')"` |
| Polar buckets sum | sum of bucket counts == total chains for that contractor |
| Peer band non-degenerate | for at least 3 of 5 KPIs, p25 < median < p75 (not all equal — confirms peer stats computed across multiple contractors) |
| App starts | `python app.py` — UI loads, no console errors |
| Best-entreprise click | "Entreprise de la semaine" → fiche page renders (Bentin canonical name in header) |
| Card click | Any enriched ContractorCard → fiche renders |
| Chip non-click | `ContractorChip` (low-doc fallback) does not navigate |
| Back nav | "Retour" returns to Contractors list |
| Dormant drilldown | Click dormant REF row → Document Command Center opens |
| Polar histogram render | SVG renders with 13 sectors, sector radius proportional to count, total chain count matches K3's denominator |
| Peer bands render | Each KPI tile shows median tick + p25/p75 band |
| Error state | Force quality module to raise → `payload.quality = {error: …}` → fiche shows degraded panel for quality widgets but header + KPI source values still render from `block4_quality` |
| No regression | Phase 1–6: consultant fiche works, dashboard drilldowns work, intelligence tab loads, BEN/Bentin everywhere correct |
| Latency | First fiche open < 3 seconds; subsequent opens for other contractors should reuse cached `ctx` (acceptable up to 5 seconds in dev) |

---

## 9. Context Update (after merge)

- `context/03_UI_FEED_MAP.md` — record the new `ContractorFiche` route, `loadContractorFiche` bridge method, `get_contractor_fiche_for_ui` endpoint (now extended), and `contractor_quality.build_contractor_quality` data source.
- `context/01_RUNTIME_MAP.md` — note `ContractorFiche` route mounted in shell.jsx; note `contractor_quality.py` exists alongside `contractor_fiche.py`.
- `context/02_DATA_FLOW.md` — add the contractor-quality computation lane (responses_df → Socotec filter; chain attribution artifact → polar histogram; cross-contractor peer aggregation).
- `context/07_OPEN_ITEMS.md` — close the README open item: "`get_contractor_fiche` is not wired"; add open item for V2 widgets (top-5 worst chains, rework timeline, etc.).
- `context/08_DO_NOT_TOUCH.md` — add `contractor_quality.py` business logic to the protected list once stabilized.
- `README.md` §Contractors Page — replace "fiche drill-down not yet wired" with the new behavior.

If any `context/` file is missing, skip — do not create new context files in this phase.

---

## 10. Done Definition

- App launches cleanly.
- `contractor_quality.build_contractor_quality('BEN')` returns a payload matching the shape in §7 Step 4 with non-zero values for at least the V1 KPIs.
- Clicking "Entreprise de la semaine" or any enriched `ContractorCard` opens a working contractor quality fiche.
- Fiche renders all 8 V1 widgets: Header, KPI strip with peer bands, Polar histogram, Long-chains panel, Open/finished, Dormant REF, Dormant SAS REF, SOCOTEC SUS rate (the rate is one of the K1–K5 KPIs).
- Dormant REF/SAS REF row click opens Document Command Center for that doc.
- `ContractorChip` items remain non-clickable.
- Phase 1–6 functionality unaffected.
- Diff scoped to: `src/reporting/contractor_quality.py` (new), `app.py`, `ui/jansa/contractor_fiche_page.jsx` (new), `ui/jansa/shell.jsx`, `ui/jansa/overview.jsx`, `ui/jansa/contractors.jsx`, `ui/jansa-connected.html`. No edits to `src/reporting/contractor_fiche.py`, `ui/jansa/fiche_base.jsx`, or any DO-NOT-TOUCH file.
