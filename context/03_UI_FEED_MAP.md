# 03 — UI Feed Map

> Per-screen mapping: which UI component, which JS bridge call, which Api
> method, which backend module ultimately produces the data.
>
> Reconstructed from `ui/jansa-connected.html`, `ui/jansa/*.jsx`,
> `ui/jansa/data_bridge.js`, `app.py`, and `src/reporting/*`.

---

## A. Globals populated by `data_bridge.js`

`data_bridge.js:bridge.init()` is called once on shell mount with `(focusMode, staleDays)`.
It calls three bridge methods in parallel via `Promise.allSettled` and stamps
the responses onto `window`:

| Window global | Source call | Backend method | Backend builder |
|---|---|---|---|
| `window.OVERVIEW` | `api.get_overview_for_ui(focus, stale)` | `Api.get_overview_for_ui` | `Api.get_dashboard_data` (kpis + monthly|weekly + consultants + contractors + focus) → `reporting.ui_adapter.adapt_overview` |
| `window.CONSULTANTS` | `api.get_consultants_for_ui(focus, stale)` | `Api.get_consultants_for_ui` | `Api.get_consultant_list` → `reporting.aggregator.compute_consultant_summary` → `reporting.ui_adapter.adapt_consultants` |
| `window.CONTRACTORS`, `window.CONTRACTORS_LIST` | `api.get_contractors_for_ui(focus, stale)` | `Api.get_contractors_for_ui` | `Api.get_contractor_list` → `reporting.aggregator.compute_contractor_summary` → `reporting.ui_adapter.adapt_contractors_lookup` + `adapt_contractors_list` |
| `window.FICHE_DATA` | `api.get_fiche_for_ui(name, focus, stale)` (on consultant nav) | `Api.get_fiche_for_ui` | `Api.get_consultant_fiche` → `reporting.consultant_fiche.build_consultant_fiche` (or `build_sas_fiche` if name == "MOEX SAS") |
| `window.CONTRACTOR_FICHE_DATA` | `loadContractorFiche` (ui/jansa/data_bridge.js:124-150) → `api.get_contractor_fiche_for_ui(code, focus, stale)` (on contractor nav) | `Api.get_contractor_fiche_for_ui` | `reporting.contractor_quality.build_contractor_quality` (+ `reporting.contractor_fiche.build_contractor_fiche` for header) |
| `window.CHAIN_INTEL` | `api.get_chain_onion_intel(20)` | `Api.get_chain_onion_intel` | reads `output/chain_onion/top_issues.json` (list, sliced to limit) + `output/chain_onion/dashboard_summary.json` (summary dict); applies `reporting.narrative_translation.translate_top_issue` per issue (FR overlay); returns `{top_issues, summary}`. Phase 4 (2026-05-01): each `top_issues` entry now carries `emetteur_code`, `emetteur_name`, `titre` appended at exporter time. |
| (drawer payload, not on `window`) | `jansaBridge.loadDrilldown(kind, params, focusMode, staleDays)` | `Api.get_documents_drilldown` | `reporting.drilldown_builder.build_drilldown(ctx, kind, params, focus_result)`. Returns `{rows, total_count, truncated, kind, params}`. Phase 3 backend wired 2026-05-01 (recovery cycle); see `02_DATA_FLOW.md` "Dashboard drilldown lane". |

If `window.pywebview.api` is unavailable within 5s, `data_bridge.js`
populates **placeholder zero values** so the React app still renders. This
is the "Backend not connected — running in preview mode" path.

`data_bridge.js` defends against stale responses with a `_loadGen` counter:
when Focus toggles or stale-days slider moves, only the latest reload's
result is applied to `window.*`.

---

## B. Per-page data dependencies

### `OverviewPage` (`ui/jansa/overview.jsx`)

Renders the dashboard. Reads `window.OVERVIEW`. Specifically uses:

- `OVERVIEW.run_number`, `total_runs`, `data_date_str`, `week_num`
- `total_docs`, `total_docs_delta`
- `pending_blocking`, `pending_blocking_delta`
- `refus_rate`, `refus_rate_delta`
- `best_consultant {name, slug, pass_rate, delta}`
- `best_contractor {code, name, pass_rate, delta}`
- `visa_flow {submitted, answered, vso, vao, ref, hm, pending, on_time, late}`
- `weekly: [...]` (sparkline values)
- `focus {focused, p1_overdue, p2_urgent, p3_soon, p4_ok, total_dernier, excluded, stale, resolved, by_consultant, by_contractor}` (Phase 5: `by_contractor` added 2026-04-29 — list of `{code, name, p1, p2, p3, p4, total}` keyed on uppercase 3-letter emetteur code with canonical company name resolved via `reporting.contractor_fiche.resolve_emetteur_name`)
- `legacy_backlog_count` (when focus on)
- `priority_queue` (when focus on)

Click-throughs:
- "Tableau de Suivi VISA" button → `api.export_team_version()` → opens with
  `api.open_file_in_explorer(res.path)`.

Data sources (Python):
- KPIs: `reporting.aggregator.compute_project_kpis`
- Monthly/weekly: `compute_monthly_timeseries` / `compute_weekly_timeseries`
- Consultants: `compute_consultant_summary`
- Contractors: `compute_contractor_summary`
- Focus stats: `reporting.focus_filter.apply_focus_filter` + chain_onion
  narrowing in `app._apply_live_narrowing`.

### `ConsultantsPage` (`ui/jansa/consultants.jsx`)

Reads `window.CONSULTANTS` and groups by `c.group ∈ {"MOEX","Primary","Secondary"}`.
Click on a card triggers `navigateTo("ConsultantFiche", c)` in shell.jsx,
which calls `jansaBridge.loadFiche(c.canonical_name || c.name, focusMode, staleDays)`,
populating `window.FICHE_DATA`.

**Phase 5 (2026-04-29) — Focus-aware cards.** `ConsultantsPage` accepts
`focusMode` from `shell.jsx` and looks up
`window.OVERVIEW.focus.by_consultant` keyed on `c.canonical_name`. Each
card type (`MoexCard`, `PrimaryCard`, `SecondaryChip`) swaps its headline
KPI from `c.total` to `c.focus_owned` ("À traiter") when `focusMode` is
true, with the all-time `c.total` retained as a smaller secondary slot
("Total docs"). A 4-segment `P1·P2·P3·P4` mini-bar (`FocusPriBar`,
defined at the top of the file) renders under each card whose actor has
a `by_consultant` entry, regardless of focus mode. Existing
`FOCUS {n}` / `F{n}` chips are preserved.

Data source: `reporting.aggregator.compute_consultant_summary` →
`reporting.ui_adapter.adapt_consultants`.

The "group" classification comes from the canonical → tier mapping in
`src/reporting/focus_ownership.py` (PRIMARY/SECONDARY/MOEX) and is mapped
to `Primary/Secondary/MOEX` strings in `ui_adapter.adapt_consultants`.

### `ConsultantFichePage` (`ui/jansa/fiche_page.jsx` + `fiche_base.jsx`)

Reads `window.FICHE_DATA`. The fiche payload has:
- `consultant {id, slug, name, canonical_name, role, ...}`
- `header {totals, answered, open, on_time, late, ...}`
- `week_delta`
- `bloc1` (per-month or per-week breakdown)
- `bloc2` (status totals)
- `bloc3` (per-lot drilldown)
- `non_saisi` (when applicable)
- status labels `s1`, `s2`, `s3` (e.g. VSO/VAO/REF or FAV/SUS/DEF)

Click on a numeric cell → `handleDrilldown({filterKey, lotName, label})` →
`api.get_doc_details(consultantName, filterKey, lotName, focus)` →
opens `DrilldownDrawer` with returned docs.

Drilldown export → `api.export_drilldown_xlsx(...)` → produces
`output/Drilldown_<consultant>_<filter>_DDMMYYYY.xlsx`.

"Tableau de Suivi VISA" header button → `api.export_team_version()`.

Data sources:
- Fiche build: `reporting.consultant_fiche.build_consultant_fiche` (or
  `build_sas_fiche` for MOEX SAS).
- Drilldown filter: `app.Api.get_doc_details` re-derives via
  `_filter_for_consultant` + `_attach_derived` then matches `filter_key`
  against `_status_for_consultant`, `_is_open`, `_is_blocking`, `_on_time`.

**2026-05-10 consultant fiche rework:** `Api.get_consultant_fiche` keeps the
pre-patch fiche-wide focus scope for header KPIs. Do not apply
Chain+Onion live-operational narrowing to this full fiche payload unless the KPI
contract is explicitly changed. In focus mode the fiche payload emits
`bloc1_title="Activité hebdomadaire"` and `bloc1_period_label="Semaine"`;
`bloc1`/`bloc2` weekly bloquant and non-bloquant counts are built from the
consultant-owned focused scope in `src/reporting/consultant_fiche.py`, not
from JSX. The payload also emits `blocking_legend.{blocking,non_blocking}`.
`fiche_page.jsx` calls `data_bridge.js:loadFicheDrilldown(...)`, which forwards
`focus`, `stale_days`, and optional `period_label` to `Api.get_doc_details`.
Activity-table numeric cells use backend period filtering; row click still
opens the existing Document Command Center via
`window.openDocumentCommandCenter(numero, indice)`. `bloc3.lots[*]`,
`bloc3.critical_lots[*]`, and `bloc3.refus_lots[*]` carry backend-resolved
canonical contractor names via `reporting.contractor_fiche.resolve_emetteur_name`;
JSX renders those payload fields only. Cumulative chart week labels are
cosmetically compacted in JSX from `YYYY-SWW` / `SWW-YYYY` to `SWW-YY`, and tick
font size is slightly reduced.

**2026-05-10 focus-reload fix:** `shell.jsx` now holds `activeRef` and
`selectedConsultantRef` mirrors so that a `useEffect([focusMode, staleDays])`
can call `window.jansaBridge.loadFiche(apiName, focusMode, staleDays)` whenever
those values change **while the active page is `ConsultantFiche`**. This fires
after `refreshForFocus` (which reloads OVERVIEW/CONSULTANTS/CONTRACTORS) and
independently updates `window.FICHE_DATA` for the active consultant, then calls
`setDataVersion` to trigger a re-render. Pipeline rerun is not required for this
fix. App restart is required after any app.py change.

**2026-05-10 KPI alignment fix (consultant fiche header):** `Api.get_consultant_fiche`
in `app.py` now applies `_apply_live_narrowing` when `focus=True`, matching
`get_dashboard_data` and `get_consultant_list`. Single source of truth for
focus-mode "à traiter" KPIs across dashboard, consultant card, and fiche header
is now `apply_focus_filter + _apply_live_narrowing`. Backend-verified: for
"Maître d'Oeuvre EXE" with `focus=True, stale_days=90`, fiche
`header.open_blocking == operational.moex_fresh == 392`. This **supersedes** the
prior obsidian note (`05_REPORTING_AND_UI_ADAPTERS.md` "Consultant fiche correction
pass") that said live narrowing should NOT be applied to the fiche.

**2026-05-10 hybrid fiche payload (afternoon):** `consultant_fiche._build_bloc1_weekly`
now accepts `(docs, data_date, s1, s2, s3, focus_docs=None)`. In focus mode,
`build_consultant_fiche` calls it with `docs=all_docs` (full consultant history)
and `focus_docs=focused_docs` (focus + live-narrowed scope). The full-history
`docs` drives the status histogram (nvx, doc_ferme, s1/s2/s3/hm and their
percentages) so VSO / VAO / REF / HM remain visible week by week, the card
sparklines retain content, and the cumulative bloc2 evolution graph still
shows historical statuses. The `focus_docs` scope drives only the open
backlog columns (open_ok/late, open_blocking_ok/late, open_nb). Header KPIs
still come from `_build_header(all_docs)` with focus-scope override on the
`open_*` fields only — answered, s1_count, s2_count, s3_count, hm_count,
total are full history. Net effect: focus mode shows the headline backlog
under focused scope while preserving all historical response data on the
fiche.

**2026-05-10 fiche drilldown drawer hardening:** `fiche_page.jsx` renders
the fiche drawer through `ReactDOM.createPortal(..., document.body)` so it
escapes any ancestor `transform` (sets the containing block on `<main>`
when focusMode is ON) or `overflow:auto` (inner-scroll wrapper) that
could clip a `position:fixed` child. (Originally introduced together with
a temporary "FICHE CLICK RECEIVED" debug badge; the badge was removed
once the root cause — a name collision, recorded below — was fixed.
The portal stays.)

**2026-05-10 fiche drilldown drawer naming collision (root-cause fix +
final cleanup):** Originally there were TWO components named
`DrilldownDrawer` — `fiche_base.jsx:1059` (prop contract
`{ state, onClose, onExport }`) and `overview.jsx:832` (prop contract
`{ drill, focusMode, staleDays, onClose }`, returns null when `drill` is
falsy). Each `<script type="text/babel">` runs in global script scope,
so each top-level `function` declaration becomes a `window.*` property.
Load order in `ui/jansa-connected.html` (`fiche_base.jsx` then
`overview.jsx`) caused the overview declaration to silently overwrite
`window.DrilldownDrawer`. fiche_page.jsx's
`<window.DrilldownDrawer state={drilldown}>` was therefore hitting the
overview component, which saw no `drill` prop and rendered null —
explaining why the drawer never opened. Final state:
- `fiche_base.jsx` exports the fiche drawer as both
  `window.DrilldownDrawer` (legacy) and `window.FicheDrilldownDrawer`
  (stable, unambiguous).
- `overview.jsx`'s component has been **renamed**
  `OverviewDrilldownDrawer`; it is no longer assigned to a window key
  (it's used purely via the local lexical reference in `OverviewPage`).
- `fiche_page.jsx` references `window.FicheDrilldownDrawer` so any
  future bare-name collision cannot recur.
Hard rule: any future drawer-style component declared at script-top
level MUST use a uniquely qualified name; if a `window.*` export is
needed, prefix with the surface name (e.g. `Fiche*`, `Overview*`,
`Contractor*`).

### `RunsPage` (`ui/jansa/runs.jsx`)

Calls `api.get_all_runs()` directly on mount → list of run dicts. Per-row
button: `api.export_run_bundle(n)` → produces ZIP under `output/exports/`.

Data sources:
- `src.run_explorer.get_all_runs(RUN_MEMORY_DB)` — direct SQL on `runs` and
  `run_artifacts` tables.

### `ExecuterPage` (`ui/jansa/executer.jsx`)

- On mount: `api.get_app_state()` → auto-fills detected GED/GF paths from `input/`.
- On any field change: `api.validate_inputs(runMode, ged, gf, reportsDir)` →
  inline error/warning rendering.
- On launch: `api.run_pipeline_async(runMode, ged, gf, reportsDir)` then
  polls `api.get_pipeline_status()` every 600 ms until `running=false`.
- On success: invokes `onRunComplete()` from shell.jsx, which calls
  `jansaBridge.refreshForFocus()` to rebuild OVERVIEW / CONSULTANTS /
  CONTRACTORS with the new run.

The "Mapping" file picker is purely informational — `app.Api.run_pipeline_async`
does NOT pass it. Comment in JSX line 277:
`hint="(informatif — non transmis au backend)"`.

Data sources:
- `app.Api.get_app_state` (direct sqlite read).
- `run_orchestrator.validate_run_inputs`.
- `run_orchestrator.run_pipeline_controlled` (run in worker thread).

### `ReportsPage` (defined in `shell.jsx`)

One real action: "Tableau de Suivi VISA" → `api.export_team_version()`.
Other reports section is a placeholder ("à venir").

**Phase 6D (2026-05-05):** `Générer Pack Audit IA` button added at post-edit
lines 877–910 (`ui/jansa/shell.jsx`). Replaces the disabled "Autres rapports"
placeholder (pre-edit lines 853–864). Full call chain:

1. UI: `Générer Pack Audit IA` button → `handleAiPack` handler (lines 807–827);
   state pairs `(aiPacking, aiPackResult)` at lines 782–783.
2. Bridge: `window.jansaBridge.generateAiAuditPack()` (`ui/jansa/data_bridge.js`
   lines 329–360); ES5-style; typeof-guard on the API method; wraps failure in
   the §10.8 envelope on every code path.
3. Api: `Api.generate_counter_attack_ai_audit_pack()` (`app.py` lines 1255–1287);
   module-level import at line 39; loads `RunContext` via `load_run_context(BASE_DIR)`.
4. Backend: `build_ai_audit_pack(ctx, output_dir)`
   (`src/reporting/counter_attack_ai_pack.py`).
5. Output: `output/exports/JANSA_AI_AUDIT_PACK_<YYYYMMDD>_<HHMMSS>.zip`.
6. Explorer-open guard (Correction #3): `result.success === true && result.path`
   enforced at line 818 in `shell.jsx`.

### Stub pages (rendered by `shell.jsx`)

- `Discrepancies` → `<StubPage title="Écarts" …>`.
- `Settings` → `<StubPage title="Paramètres" …>`.

### `ContractorsPage` (`ui/jansa/contractors.jsx`)

Reads `window.CONTRACTORS_LIST` (enriched cards) and `window.CONTRACTORS`
(full code→name lookup; chips for codes not in the enriched list).

**Phase 5 (2026-04-29) — All eligible emetteurs surface as cards + focus-aware reorientation.**
- `adapt_contractors_list` returns ALL contractors with ≥5 docs (29
  today) — previously sliced to top-5 by approval rate, which buried
  major emetteurs like BEN (374 docs) in the chip section. New sort:
  `docs DESC` normally, `(focus_owned, docs) DESC` in focus mode. Card
  ceiling is `[:50]` (defensive). Pass-rate sort is intentionally NOT
  used.
- Canonical company names (BEN→Bentin, LGD→Legendre, SNI→SNIE, …)
  applied via `reporting.contractor_fiche.resolve_emetteur_name` in
  both `adapt_contractors_list` and `adapt_contractors_lookup`. Cards
  AND chips both show canonical names.
- `ContractorsPage` accepts `focusMode` from `shell.jsx` and looks up
  `window.OVERVIEW.focus.by_contractor` keyed on uppercase code. In
  focus mode, `ContractorCard` renders three slots: focus_owned
  headline ("À traiter") / total docs ("Total docs") / pass_rate as a
  small soft-pill chip ("Conformité"). In non-focus mode the
  pre-Phase 5 two-slot layout (Conformité large / Documents) is
  preserved. `FocusPriBar` mini-bar appears when an entry exists.
  `ContractorChip` (code-only fallback) is unchanged.

---

## C. Backend → UI shape contract

### `OVERVIEW` (built by `reporting.ui_adapter.adapt_overview`)

Always emitted, even in degraded mode. Numeric fields default to 0 if data
is missing.

### `CONSULTANTS` (list of)

```python
{
  "id": int,
  "slug": str,
  "name": str,                 # display name
  "canonical_name": str,       # canonical form used for backend calls
  "group": "MOEX" | "Primary" | "Secondary",
  "role": str,
  "totals": {...}, "ratios": {...}, "delta": {...},
  ...
}
```

### `CONTRACTORS_LIST` and `CONTRACTORS` (lookup)

`CONTRACTORS_LIST` is a list of contractor dicts. `CONTRACTORS` is a dict
keyed by contractor code (LGD, BEN, etc.) → contractor dict.

### `FICHE_DATA`

Per-consultant payload; structure varies slightly between standard fiche
and MOEX SAS fiche (see `reporting.consultant_fiche._empty_fiche` and
`_empty_sas_fiche` for the always-present skeleton).

### `get_doc_details` return

```python
{
  "docs": [
    {"numero", "indice", "emetteur", "titre", "date_soumission",
     "date_limite", "remaining_days", "status", "lot"},
    ...
  ],
  "count": int,
  "filter_key": str,
  "consultant": str,
}
```

`remaining_days` is computed from `data_date - date_limite` and is the sort
key (lates first, then earliest deadline).

---

## D. UI screens → backend modules (one-line summary)

| UI Screen | Top-level Api method | Builder module |
|---|---|---|
| Overview | `get_overview_for_ui` | `reporting.aggregator.compute_*` + `ui_adapter.adapt_overview` |
| Consultants list | `get_consultants_for_ui` | `aggregator.compute_consultant_summary` + `ui_adapter.adapt_consultants` |
| Consultant fiche | `get_fiche_for_ui` → `get_consultant_fiche` | `consultant_fiche.build_consultant_fiche` |
| Drilldown | `get_doc_details` | inline in `app.py` over `consultant_fiche` helpers |
| Drilldown export | `export_drilldown_xlsx` | inline in `app.py` |
| Contractors (stub) | wired but UI shows StubPage | `aggregator.compute_contractor_summary` |
| Contractor fiche | `get_contractor_fiche_for_ui` | `contractor_fiche.build_contractor_fiche` + `contractor_quality.build_contractor_quality` |
| Runs | `get_all_runs`, `export_run_bundle` | `run_explorer` |
| Executer | `validate_inputs`, `run_pipeline_async`, `get_pipeline_status` | `run_orchestrator` |
| Reports / Tableau VISA | `export_team_version` | `data_loader` + shutil copy |
| Reports / Pack Audit IA (Phase 6D) | `generate_counter_attack_ai_audit_pack` | `reporting.counter_attack_ai_pack.build_ai_audit_pack` |
| Discrepancies (stub) | none today | (future: `DISCREPANCY_REPORT.xlsx` consumer) |
| Settings (stub) | none today | — |
| Document Command Center — search | `search_documents(query, focus, stale_days, limit)` | `document_command_center.search_documents` |
| Document Command Center — panel | `get_document_command_center(numero, indice, focus, stale_days)` | `document_command_center.build_document_command_center` |
| Document Command Center — chain timeline (Chronologie section) | `get_chain_timeline(numero)` | `chain_timeline_attribution.load_chain_timeline_artifact` (reads `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json`) |
| Counter-Attack — home (Phase 6B) | `get_counter_attack_home()` | `reporting.counter_attack_query.get_counter_attack_home` (reads `output/intermediate/COUNTER_ATTACK_ITEMS.csv`; identity columns locked as `string`; missing-artifact returns `available=false` empty state) |
| Counter-Attack — bucket queue (Phase 6B) | `get_counter_attack_queue(bucket, limit=500)` | `reporting.counter_attack_query.get_counter_attack_queue` (same artifact; bucket display order: FERMER_MAINTENANT, SECONDAIRE_EXPIRE, DECISION_MOEX, ENTREPRISE_A_RELANCER, CONSULTANT_A_ATTAQUER, SUJET_REUNION, MOEX_SHAME_INTERNAL) |
| Counter-Attack — item detail (Phase 6B) | `get_counter_attack_item(item_id)` | `reporting.counter_attack_query.get_counter_attack_item` (same artifact; `timeline=[]` by design — cockpit reaches existing chain timeline through DCC via `open_dcc_ref`) |

> **Counter-Attack note (Phase 6B):** these three endpoints are
> on-demand. They are NOT part of the four-call `Promise.allSettled` in
> `data_bridge.js:_loadCoreData` and do NOT populate any `window.*`
> global. The future Counter-Attack page (Phase 6C) owns its own state
> and calls `jansaBridge.loadCounterAttackHome / loadCounterAttackQueue /
> loadCounterAttackItem` only when the user navigates to the page. The
> bridge contract is the only allowed integration point — JSX must NOT
> read the CSV directly. See
> `docs/implementation/PHASE_6B_READ_API.md` for the full payload
> contracts and known limitations.
>
> **Phase 6X closure (2026-05-04):** the backend artifact now uses DCC
> split deadline truth (`primary_consultant_days_remaining`,
> `secondary_consultant_days_remaining`, `consultant_days_remaining`) and
> Chain/Onion wait-day fields to assign buckets and `days_late`. The
> Phase 6B endpoint shapes did not change; UI code still consumes only the
> read API payloads.
>
> **Phase 6C closure (2026-05-04):** the previously-forward-referenced
> Counter-Attack page is now built and live, user-facing label
> **ACTION MOEX**. Internal page id `ActionMoex`, component
> `window.ActionMoexPage`, file `ui/jansa/counter_attack.jsx` (loaded
> between `document_panel.jsx` and `shell.jsx` in `ui/jansa-connected.html`).
> The page consumes only the three Phase 6B bridge methods on demand
> (`loadCounterAttackHome` on mount, `loadCounterAttackQueue(bucket, 500)`
> on bucket click with per-bucket cache, `loadCounterAttackItem(item_id)`
> on row click), with `queueGenRef` and `itemGenRef` stale-promise guards
> for rapid clicks. The cockpit performs **no business logic**: bucket
> rules, ownership, deadlines, risk, MOEX exposure, attackability, and
> recommended actions are all decided by the backend (Phase 6A / Phase 6X).
> Bucket presentation order is overridden in JSX (`AM_BUCKET_PRESENTATION`
> array, counts looked up by enum, not by index — backend display order
> remains free to evolve). The "Ouvrir le détail" button uses the existing
> `window.openDocumentCommandCenter(numero, indice)` global from the DCC
> wiring; no new DCC-like surface is added. "Voir preuves / Masquer
> preuves" toggles locally without an extra backend call. See
> `docs/implementation/PHASE_6C_COUNTER_ATTACK_UI.md` for the full
> implementation record (files, edge-state matrix, manual smokes).
>
> **Phase 6C correction Set 1 — 2026-05-04:**
> (S3) Latest-indice dedup landed at the 6A builder; the artifact now has
> exactly one row per chain (1525 distinct family_keys). (S1) The 6B
> `get_counter_attack_queue` adapter sorts rows ascending by `days_late`
> (numeric coercion, NaN last) with stable tie-breakers `days_open`,
> `numero`, `indice`. Pure presentation order; `count` is unchanged.
> (S2) Canonical-name row title (`AXIMA — …`, `BENTIN — …`) is produced
> at the 6A builder under Phase 6X — the 6B adapter passes
> `subject_label` through verbatim, no JSX-side reformatting.

---

## E. Operational dashboard — shipped state (2026-05-07)

> This section supersedes the Focus-as-primary description in §B `OverviewPage` for
> the overview feed. See `docs/implementation/OPERATIONAL_DASHBOARD_REDESIGN.md`
> for the full contract and locked baseline.

**Default view:** The JANSA Overview now shows the **operational dashboard** as the
primary surface. It is bound to `window.OVERVIEW.operational` (21 keys), produced
by `src/reporting/aggregator.py::compute_operational_dashboard` (lines 554–660) and
forwarded verbatim by `ui_adapter.adapt_overview` (lines 236–239).

**Backend call chain:**
1. `app.py::get_dashboard_data` → calls `compute_operational_dashboard(ctx)` after
   the existing focus-filter block and merges result under key `"operational"`.
2. `ui_adapter.adapt_overview` passes `dashboard["operational"]` through verbatim.
3. `window.OVERVIEW.operational` is populated at startup with all 21 keys.

**21 keys at `window.OVERVIEW.operational`:**

```
operational_total, fresh_total, stale_total,
moex_total, moex_fresh, moex_stale,
primary_total, secondary_total, consultants_total,
priority_p1, priority_p2, priority_p3, priority_p4, priority_p5,
enterprise_ref_sas_candidates, enterprise_action_rows,
old_debt_age_days_min, old_debt_age_days_median, old_debt_age_days_max,
stale_threshold_days, universe_definition
```

**Operational universe rule:** latest-indice only (`ctx.dernier_df`, one row per
`numero`); `portfolio_bucket ∈ {LIVE_OPERATIONAL, LEGACY_BACKLOG}`; AND
`_visa_global ∉ {VSO, VAO, REF, SAS REF, HM}`. Stale (>90 d) is a **visible
segment**, not an exclusion.

**Legacy Focus payload (`window.OVERVIEW.focus`, 11 keys):**
`focused, p1_overdue, p2_urgent, p3_soon, p4_ok, total_dernier, excluded, stale, resolved, by_consultant, by_contractor`

This payload remains fully exposed and callable via `get_dashboard_data(focus=True,
stale_days=90)` but is **no longer the default** — it is a preserved legacy path.
The Focus toggle in the UI, if present, now acts as a segment selector
(Fresh / Stale / All) for display grouping only; it does not drive backend filtering.

**UI tiles:** `OperationalDashboard` A–F + `OperationalPriorityRow` P1–P5 in
`ui/jansa/overview.jsx`. No JSX arithmetic — all counts come from the backend dict.

---

### Document Command Center wiring (deployed 2026-04-28)

The right-side drawer panel built in Phase 4 of the DCC project. Pure
rendering; all business logic lives in
`src/reporting/document_command_center.py`.

**UI files:**
- `ui/jansa/document_panel.jsx` — the drawer component, mounted once at
  `App` root in `shell.jsx`. z-index 210 (above DrilldownDrawer 200,
  below FocusCinema 500). Two modes: `search` and `doc`. Backdrop +
  Esc + click-outside close.
- `ui/jansa/data_bridge.js` exposes `searchDocuments(query, ...)` and
  `loadDocumentCommandCenter(numero, indice, ...)`.
- `ui/jansa/shell.jsx` — `panelState` useState, `<DocumentCommandCenterPanel>`
  mount, topbar search button (line ~224), and `window.openDocumentCommandCenter`
  global opener.
- `ui/jansa/fiche_base.jsx` — `DrilldownDrawer` rows accept optional
  `onRowClick` prop (Phase 4C); when present, rows show `cursor: pointer`
  and clicking invokes the callback with the doc dict.
- `ui/jansa/fiche_page.jsx` — passes `onRowClick={(doc) => window.openDocumentCommandCenter(doc.numero, doc.indice)}`
  to the DrilldownDrawer.
- `ui/jansa-connected.html` — loads `document_panel.jsx` between
  `executer.jsx` and `shell.jsx`.

**Entry points to the panel (as of Phase 5 Mod 2, 2026-04-29):**
1. Topbar search button → opens in search mode.
2. Drilldown row click → opens in doc mode for that (numero, indice).
3. `ChainOnionPanel` issue rows in `overview.jsx` → `onClick` calls `window.openDocumentCommandCenter(issue.family_key, null)`; `indice=null` resolved to latest by backend.

**Standing rule — any future UI component that renders documents must wire the panel:**

Every component that renders a list of documents — drilldown tables, search results,
priority queues, lot-breakdown rows, chain/onion issue lists, or any future widget —
must include `onClick → window.openDocumentCommandCenter(numero, indice)` and
`cursor: pointer` on each document row **by default**, not as a follow-up.

Rules:
- Use `issue.family_key` (or the equivalent normalized campo) when `numero` comes
  from chain/onion data; use `doc.numero` when it comes from `get_doc_details`.
- Pass `null` for `indice` if the render site does not have a specific indice —
  the backend resolves to the latest indice automatically.
- Always guard: `if (window.openDocumentCommandCenter) { ... }` — the global is
  set by `App` on mount; the guard prevents errors in preview/degraded mode.
- Never compute or derive doc data in the click handler — pass the fields you
  already have; do not call the backend from within the handler.
- If the row already has a primary click action (e.g. navigating to a different
  page), do not override it — add a small secondary affordance (icon button or
  chevron) beside the doc label instead.

**`Api.get_chain_timeline(numero)`** blocks on `_chain_data_ready`,
normalizes the input numero to a 6-digit zero-padded `family_key`, and
returns either the per-chain payload or an `{"error": ...}` dict. The
panel calls this only when a user opens the Chronologie section (it's
embedded in `get_document_command_center` payload's `chronologie` field).

**Backend payload contract** — the `get_document_command_center` JSON
return shape is the source of truth for the panel; the JSX layer only
renders. Schema in `00_OVERALL_PLAN.md` and
`src/reporting/document_command_center.py` module docstring.

`comments[*].earlier_comments` items are dicts with keys
`{indice, status, comment}` (Phase 5 Mod 1, 2026-04-29). `status` is
`status_clean` from `responses_df` — e.g. `"VAO"`, `"REF"`, `""`.
The JSX label span renders `"{indice}) {status}:"` when status is
non-empty, otherwise just `"{indice}"`. No UI business logic — all
formatting stays in `_build_comments_section`.

**Convention — `_resolve_doc_rows`:** when caller passes `numero` without
`indice`, the helper picks the alphabetically latest indice (e.g. given
indices A, B, C → C). This is documented in
`context/06_EXCEPTIONS_AND_MAPPINGS.md` § I.

**Phase 5 Mod 2 (done 2026-04-29):** `ChainOnionPanel` issue rows in `overview.jsx`
are now clickable. Inventory confirmed no other active doc-reference sites remain
unwired. `priority_queue` exists in OVERVIEW data but is not rendered (no site to wire).

**Phase 2 (done 2026-04-29) — Direct fiche navigation + FR synthese:**

- `OverviewPage` now accepts an `onOpenConsultant` prop, threaded down to
  `KpiRow.BestPerformerCard` ("Consultant de la semaine") and
  `FocusByConsultant` per-row buttons. Both call sites replaced
  `onNavigate('Con
---

## 2026-05-09 — Operational priority strip P1..P4 (P5 retired)

`OperationalPriorityRow` in `ui/jansa/overview.jsx` now renders 4 cells
(P1, P2, P3, P4). The 5-column grid was changed to `repeat(4, 1fr)`.
Backend `compute_operational_dashboard` no longer emits `priority_p5`.

New backend fields on `data.operational`:

| Field | Meaning |
|---|---|
| `moex_total` | normal Maître d'Œuvre EXE only (excludes MOEX SAS pollution) |
| `moex_sas_total` | MOEX SAS / GEMO SAS — SAS-pending docs |
| `contractor_total` | tier `CONTRACTOR` (REF / DEF / SAS REF / no-MOEX-called negative-worst) |

The JSX continues to read `operational.priority_p1..p4`; no other UI
changes are required.

---

## 2026-05-10 — Dashboard drilldown unification (Step 1) + drilldown export (Step 1.5) + coverage extension (Step 2)

### Drawer reuse (Step 1)

`OverviewPage` in `ui/jansa/overview.jsx` now mounts a new
`OverviewFicheDrawerHost` adapter (~85 lines) that renders the canonical
`window.FicheDrilldownDrawer` (defined in `fiche_base.jsx`) via
`ReactDOM.createPortal(..., document.body)`. The legacy
`OverviewDrilldownDrawer` is left defined but unmounted (kept as a safety
net per scope; no `window.OverviewDrilldownDrawer` assignment is
introduced). The fiche_base aliases (`DrilldownDrawer`,
`FicheDrilldownDrawer`) are untouched.

`reporting.drilldown_builder._row_to_payload` was widened so the dashboard
drawer receives the same shape the fiche drawer expects. Existing keys
preserved (`numero, indice, titre, emetteur_code, lot, last_action_date,
latest_status, primary_owner`); new keys added: `emetteur, emetteur_name,
date_soumission, date_limite, remaining_days, status`. Fallbacks: `titre`
→ `libelle_du_document`; `date_soumission` → `created_at` / `cree_le`.
`_to_iso` now handles plain `datetime.date`.

### Drilldown Excel export (Step 1.5)

| UI surface | Bridge call | Backend Api method | Builder |
|---|---|---|---|
| Drilldown export (dashboard) | `jansaBridge.exportDocumentsDrilldown(kind, params, focusMode, staleDays)` (`ui/jansa/data_bridge.js` lines 231–250) | `Api.export_documents_drilldown_xlsx` (`app.py` lines 1168–1296) | inline in `app.py`; mirrors `Api.export_drilldown_xlsx`: same column set, header_font/header_fill, `freeze_panes="A2"`, `auto_filter`, late-row pink fill, atomic temp+rename, identity dtype preservation on `numero` / `indice`. Filename pattern `Drilldown_dashboard_{safe_kind}_{safe_params}_{YYYYMMDD_HHMMSS}.xlsx` under `output/`. `safe_params` extracts `segment` for `visa_segment`, `week_label` for `weekly`, `P{n}` for `focus_priority`. |

`OverviewFicheDrawerHost` wires `onExport` to the bridge; on success the
file is opened via `pywebview.api.open_file_in_explorer(res.path)`.

### Drilldown coverage extension (Step 2)

`reporting.aggregator.compute_operational_universe(ctx) -> (op_broad, op)`
is a new public helper extracted from the first 26 lines of
`compute_operational_dashboard`. The dashboard function delegates to it;
no behavior change in the dashboard dict (byte-for-byte identical
output). The helper is the single source of truth for the operational
mask, used by both `compute_operational_dashboard` and
`drilldown_builder`.

`reporting.drilldown_builder.build_drilldown` now dispatches 7 new kinds
(all funnel through `_row_to_payload` and inherit the export workbook):

| Kind | Params | Source mask |
|---|---|---|
| `operational_total` | — | all `op` rows |
| `operational_fresh` | — | `op[_days_since_last_activity <= 90]` |
| `operational_stale` | — | `op[_days_since_last_activity > 90]` |
| `operational_moex` | optional `scope ∈ {fresh, stale}` | `op[tier=="MOEX" & ~(_focus_owner == ["MOEX SAS"])]` (excludes MOEX SAS by design — counts match `moex_total`) |
| `operational_consultants` | optional `tier ∈ {PRIMARY, SECONDARY}` | `op[tier ∈ {PRIMARY, SECONDARY}]` |
| `operational_enterprise_ref` | — | `op_broad[_visa_global ∈ {REF, SAS REF}]` (uses `op_broad` — pre-visa-exclusion mask, mirrors `enterprise_ref_sas_candidates` per Seam 14) |
| `operational_priority` | `priority ∈ {1..4}` | `op[_focus_priority == n]` |

`OperationalDashboard` and `OperationalPriorityRow` accept `onDrill`;
clicks wired on 6 operational tiles (T1–T6) + 4 priority cells (P1–P4).
`_OV_DRILL_HEADERS` and `_ovDrillTitle` extended with branches for the 7
new kinds. Best Consultant + Best Entreprise unchanged (kept as fiche
navigation). T4/T5 sub-row clicks NOT wired — backend supports
`scope` / `tier` params, UI follow-up.

---

## 2026-05-10 — Action MOEX per-bucket Excel export (Step 5)

| UI surface | Bridge call | Backend Api method | Builder |
|---|---|---|---|
| Action MOEX bucket export | `jansaBridge.exportActionMoexBucket(bucket)` (`ui/jansa/data_bridge.js`) | `Api.export_action_moex_bucket_xlsx(bucket)` (`app.py`) | `reporting.counter_attack_export.build_action_moex_bucket_xlsx(ctx, bucket, dest_dir)` (new module, ~330 lines). Filters `output/intermediate/COUNTER_ATTACK_ITEMS.csv` by bucket; joins to `dernier_df` for `titre` + reception date; calls private `_get_latest_responses_for_doc` from `document_command_center.py` for the reviewer list; reuses CSV `plain_reason` verbatim; appends empty `MOEX AVIS` column; atomic temp+rename. Filename `ACTION_MOEX_{bucket}_{YYYYMMDD_HHMMSS}.xlsx` under `output/exports/`. Bucket validated against `BUCKET_DISPLAY_ORDER` (7-bucket enum from `counter_attack_query`). Returns `{success, path, filename, rows_exported, bucket, message, error}`. Empty bucket: header-only workbook with `success=True, message="Bucket vide..."`. |

`ui/jansa/counter_attack.jsx` adds an "Exporter Excel" button on each
queue panel header (state pair `exportingBucket` / `exportNotice`). On
success the file is opened via
`pywebview.api.open_file_in_explorer(res.path)`.

Workbook contract (Layout Y, 12 columns, French headers, real UTF-8) —
see `obsidian_repo_mind/09_ACTION_MOEX_COUNTER_ATTACK.md` Phase 6E.

Date contractuelle decision: `dernier_df` does NOT carry `date_limite`
(per `src/normalize.py:431`, `date_limite` is per-response, only on
`responses_df`); the export computes `created_at + 30 days` directly,
matching the documented 30-day workflow rule.

Residual coupling (logged in `context/07_OPEN_ITEMS.md`):
`_get_latest_responses_for_doc` is a private DCC symbol; imported because
protected-zone rules forbid modifying DCC. If DCC renames or repackages
the helper, the export breaks.

---

## 2026-05-11 — Phase 9 source-of-truth migration (operational metrics now read `latest_enriched_view`)

Every operational reporting feed below is now sourced (in backend) from
`reporting.latest_chain_view.latest_enriched_view(ctx)` — a one-row-per-
chain intersection of `ctx.dernier_df` and `ctx.latest_chain_df`
(~2,553 rows currently). The UI payload shapes are unchanged; only the
backend substrate moved. See `README.md §Phase 9` and
`reports/STEP1_DERNIER_DF_INVENTORY.md` for the per-call-site inventory.

| Feed | Backend reads | Notes |
|---|---|---|
| `window.OVERVIEW.operational.*` (Backlog opérationnel, MOEX, Consultants, Entreprises tiles) | `aggregator.compute_operational_dashboard` over `latest_enriched_view(ctx)` (via `compute_operational_universe`) | Already chain-appropriate terminology. No UI label change needed in Step 7c. |
| `window.OVERVIEW.kpis.total_docs_current` (legacy "Documents soumis" — renamed "Chaînes" in Step 7c) | `aggregator.compute_project_kpis` reading `latest_enriched_view(ctx)` | Chain count (~2,553). Pre-Phase-9 value was `dernier_df` row count (~4,360); migration removes the indice-pollution overcount. |
| `window.OVERVIEW.kpis.total_docs_all_indices` | `aggregator` reading `ctx.docs_df` directly | Historical raw OPEN_DOC count; retained for surfaces that need the full-indice count (e.g. contractor fiche "Documents soumis" all-time total). |
| `window.CONSULTANTS[*]` | `aggregator.compute_consultant_summary` over `latest_enriched_view(ctx)` | Per-consultant counts on canonical chain set. |
| `window.CONTRACTORS_LIST[*]` | `aggregator.compute_contractor_summary` over `latest_enriched_view(ctx)` | Per-contractor counts on canonical chain set. |
| `window.FICHE_DATA.*` (consultant fiche bloc1/bloc2/bloc3) | `consultant_fiche.build_consultant_fiche` over `latest_enriched_view(ctx)` (chain-level metrics) + `ctx.docs_df` (full-history sparklines) | Hybrid (Phase 9 + Phase 7 hybrid-payload contract from 2026-05-10). |
| `window.CONTRACTOR_FICHE_DATA.quality.*` (peer stats, dormant queues, polar) | `contractor_quality.build_contractor_quality` over `latest_enriched_view(ctx)`; `dormant_ref` continues to read Action MOEX artifact (§F-2) | Canonical post-Phase-9. |
| DCC search & panel | `document_command_center.compute_dcc_tags_bulk` iterates `latest_enriched_view(ctx)`; `_resolve_doc_rows` resolves indice via `ctx.latest_chain_df` with alphabetical-max fallback | Decision-3 numero 253100 trips the fallback (logger.warning). |
| Dashboard drilldown drawer | `drilldown_builder.build_drilldown` over `latest_enriched_view(ctx)` for operational kinds; `op_broad` mask still applies for `operational_enterprise_ref` | Counts match `window.OVERVIEW.operational.*`. |
| Action MOEX queue & item payloads | `counter_attack_builder.build_counter_attack_items` filters by `ctx.latest_chain_df.(family_key, latest_indice)` before bucket assignment; `counter_attack_export._resolve_dernier_row` reads `latest_enriched_view(ctx)` | Stable bucket counts 687 / 98 / 107 / 146 = 1,038. |

Surfaces that intentionally continue to read `ctx.dernier_df` or
`ctx.docs_df` directly (NOT migrated, by design):

- Revision history view in DCC (intentionally renders all indices from
  the chain timeline; scope filter via `latest_enriched_view` only
  selects the chain context).
- `_precompute_focus_columns` (mutator — adds `_visa_global` /
  `_focus_owner_tier` / `_focus_priority` columns onto `ctx.dernier_df`
  in place).
- `compute_focus_ownership` (mutator — adds `_focus_owner` /
  `_focus_owner_tier` onto `ctx.dernier_df` in place).
- `contractor_fiche` "Documents soumis" historical total field
  (`total_submitted` from `ctx.docs_df`, all-indices count).
