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