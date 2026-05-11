#repo-map #ui #jansa #pywebview #runtime

# JANSA UI Runtime

> Architecture of the desktop UI: PyWebView bridge, data_bridge.js, JSX components.
> See [[05_REPORTING_AND_UI_ADAPTERS]] for the backend data layer.

---

## Production entry point

```
ui/jansa-connected.html
```

This is the **only** production UI entrypoint. `app.py::_resolve_ui()` raises `FileNotFoundError` if it is missing. There is no fallback to `ui/dist/index.html` or a Vite dev server.

The HTML loads:
- React + Babel from CDN (no build step required)
- `ui/jansa/tokens.js` (design tokens, fonts, theme)
- `ui/jansa/data_bridge.js` (PyWebView bridge)
- All JSX component files in order (overview, consultants, fiche_base, fiche_page, contractors, contractor_fiche_page, runs, executer, document_panel, counter_attack, shell)

---

## Browser mode

```bash
python app.py --browser
```

Opens `ui/jansa-connected.html` in the system default browser. The PyWebView JS bridge (`window.pywebview.api`) is unavailable. `data_bridge.js` times out after 5 seconds and renders **placeholder zero data only**. No backend calls succeed. Use only for CSS/layout development.

---

## PyWebView bridge architecture

```
Python (app.py)              │  JavaScript (ui/jansa/)
─────────────────────────────┼─────────────────────────────────────
class Api:                   │  window.pywebview.api.*
  get_overview_for_ui()      │  data_bridge.js:bridge.init()
  get_consultants_for_ui()   │    → bridge._loadCoreData()
  get_contractors_for_ui()   │    → bridge._loadContractorFiche()
  get_fiche_for_ui()         │    → bridge.loadDrilldown()
  get_contractor_fiche_for_ui() │  → bridge.loadFiche()
  search_documents()         │    → bridge.searchDocuments()
  get_document_command_center() │ → bridge.loadDocumentCommandCenter()
  get_chain_timeline()       │    → bridge.loadChainTimeline()
  get_documents_drilldown()  │    → bridge.loadDrilldown()
  get_counter_attack_home()  │    → bridge.loadCounterAttackHome()
  get_counter_attack_queue() │    → bridge.loadCounterAttackQueue()
  get_counter_attack_item()  │    → bridge.loadCounterAttackItem()
  run_pipeline_async()       │    → bridge.runPipeline()
  get_pipeline_status()      │    → bridge.getPipelineStatus()
  export_team_version()      │    → bridge.exportTeamVersion()
  generate_counter_attack_ai_audit_pack() │ → bridge.generateAiAuditPack()
  get_all_runs()             │    → bridge.getAllRuns()
  export_run_bundle()        │    → bridge.exportRunBundle()
```

`_sanitize_for_json()` in `app.py` recursively replaces NaN / Infinity / -Infinity / pandas Timestamps with JSON-safe values before returning to the bridge.

---

## Window globals contract

Four globals are populated at startup by `data_bridge.js:_loadCoreData()` (parallel Promise.allSettled):

| Global | Content | Set by |
|---|---|---|
| `window.OVERVIEW` | Full dashboard payload | `Api.get_overview_for_ui` → `ui_adapter.adapt_overview` |
| `window.CONSULTANTS` | List of consultant dicts | `Api.get_consultants_for_ui` → `ui_adapter.adapt_consultants` |
| `window.CONTRACTORS` + `window.CONTRACTORS_LIST` | Lookup dict + enriched card list | `Api.get_contractors_for_ui` → `ui_adapter.adapt_contractors_*` |
| `window.CONTRACTOR_FICHE_DATA` | Per-contractor quality payload | `Api.get_contractor_fiche_for_ui` (on navigation) |
| `window.FICHE_DATA` | Per-consultant fiche | `Api.get_fiche_for_ui` (on navigation) |
| `window.CHAIN_INTEL` | top_issues + dashboard_summary | `Api.get_chain_onion_intel` |

On Focus toggle or stale-days change, `bridge.refreshForFocus()` repopulates all four globals. A `_loadGen` counter guards against stale responses from rapid reloads.

---

## JSX component map (`ui/jansa/`)

| File | Role | Notes |
|---|---|---|
| `shell.jsx` | App root, sidebar, router, focus toggle, theme toggle, DCC panel mount | Route decisions here |
| `tokens.js` | `window.JANSA_FONTS`, `window.applyJansaTheme` | Required by all components |
| `data_bridge.js` | All `window.pywebview.api.*` calls; populates window globals | Source of truth for bridge contract |
| `overview.jsx` | Dashboard KPIs, VisaFlow, WeeklyActivity, ChainOnionPanel, Focus radial | `window.OVERVIEW` |
| `consultants.jsx` | Consultants list (MOEX/Primary/Secondary groups), focus-aware cards | `window.CONSULTANTS` |
| `fiche_base.jsx` | Fiche layout primitives, DrilldownDrawer | Used by fiche_page + contractor_fiche_page |
| `fiche_page.jsx` | Consultant fiche wrapper | `window.FICHE_DATA` |
| `contractors.jsx` | Contractors page: enriched KPI cards (≥5 docs) + chip list (all others) | `window.CONTRACTORS_LIST` + `window.CONTRACTORS` |
| `contractor_fiche_page.jsx` | Per-contractor quality fiche (Phase 7) | `window.CONTRACTOR_FICHE_DATA` |
| `document_panel.jsx` | Document Command Center drawer (search mode + doc mode) | On-demand; DCC backend is source of truth for all logic |
| `counter_attack.jsx` | Action MOEX page (Phase 6C) — home / bucket queue / item detail | On-demand via 3 bridge methods |
| `runs.jsx` | Run history page | On-demand API call |
| `executer.jsx` | Pipeline launcher — GED/GF/reports path pickers + status polling | On-demand |

---

## Old Vite UI files

`ui/src/`, `ui/index.html`, `ui/dist/` are **archival/reference only**. They are not loaded at runtime and not part of the production entrypoint. Do not attempt to use them.

---

## Key production rules

1. **All business logic stays in the backend.** JSX renders, does not decide. If you find data-transformation code in a `.jsx` file, that is a bug.
2. **Never move `document_panel.jsx` logic into a new file** without moving its backend counterpart (`document_command_center.py`). They are tightly coupled.
3. **`data_bridge.js` shapes are the interface.** Backend `adapt_*` functions must produce exactly what the bridge expects. Both sides must change together.
4. **JSX text content uses real UTF-8 characters** — not `\uXXXX` escape sequences. Babel JSX text does not decode escape sequences. See `context/11_TOOLING_HAZARDS.md §H-6`.
5. **Mapping.xlsx file picker in Executer is informational only** — `app.Api.run_pipeline_async` does NOT pass it to the orchestrator.

---

---

## Operational dashboard tiles (shipped 2026-05-07)

**File:** `ui/jansa/overview.jsx`

**New tile components:**
- `OperationalDashboard` tiles A–F — segment totals (operational, fresh, stale, MOEX,
  consultants, enterprise).
- `OperationalPriorityRow` P1–P5 — priority counts (P1–P5) over the full operational
  mask (stale included, no exclusion).

**Removed:** `pendTrend reduce()` at former lines 112–115. That inline JS reduction was
the only known violation of the "no JSX arithmetic" rule. Replaced by the backend-supplied
`stale_total` / `fresh_total` fields from `window.OVERVIEW.operational`.

**Optional Fresh/Stale/All segment selector:** a display-only toggle (if shipped) controls
tile highlighting and grouping between the fresh and stale sub-segments. It drives no
backend filtering — the backend always returns both segments.

**Source of truth:** all counts read directly from `window.OVERVIEW.operational` (21 keys).
No JSX-side computation on document rows.

**Cross-reference:** `docs/implementation/OPERATIONAL_DASHBOARD_REDESIGN.md` §6 (UI rule)
and §Implementation summary.

---

## Dashboard drilldown drawer reuse + dashboard click coverage (shipped 2026-05-10)

**File:** `ui/jansa/overview.jsx`

**OverviewFicheDrawerHost adapter (Step 1).** A new ~85-line wrapper component
in `overview.jsx` reuses the canonical `window.FicheDrilldownDrawer` from
`fiche_base.jsx` for the dashboard's drilldown drawer. The drawer is rendered
via `ReactDOM.createPortal(..., document.body)` so it escapes any ancestor
`transform` / `overflow:auto` (same pattern adopted on the consultant fiche
in 2026-05-10). The legacy `OverviewDrilldownDrawer` is left defined but
unmounted (kept as a safety net per scope; no `window.OverviewDrilldownDrawer`
assignment is introduced). The fiche_base.jsx aliases (`DrilldownDrawer`,
`FicheDrilldownDrawer`) are untouched.

**Dashboard drilldown click coverage (Step 2).** `OperationalDashboard` and
`OperationalPriorityRow` now accept an `onDrill` prop. onClicks are wired on
6 operational tiles (T1–T6) and 4 priority cells (P1–P4); the 7 new backend
drilldown kinds (see `05_REPORTING_AND_UI_ADAPTERS.md` Phase 7 Step 2) feed
the drawer. Best Consultant + Best Entreprise cards remain fiche-navigation
shortcuts. T4/T5 sub-rows (Frais/Stale, PRIMAIRE/SECONDARY) are inert text
inside the now-clickable parent — backend supports `scope` / `tier` params
but JSX does not surface separate clicks (UI follow-up).

**Drilldown export trigger (Step 1.5).** `OverviewFicheDrawerHost` wires the
drawer's `onExport` prop to
`window.jansaBridge.exportDocumentsDrilldown(kind, params, focusMode, staleDays)`,
which calls `Api.export_documents_drilldown_xlsx`. On success the file is
opened via `pywebview.api.open_file_in_explorer(res.path)`. Same handler shape
as the consultant-fiche drawer — the drawer component itself is shared.

### Hard rule (re-affirmed)

Any drawer-style component declared at `<script>`-top level MUST use a
uniquely qualified name. If a `window.*` alias is needed, prefix with the
surface name (e.g. `FicheDrilldownDrawer`, `OverviewDrilldownDrawer`,
`ContractorDrilldownDrawer`). When reusing an existing drawer outside its
original surface, write a thin **adapter host** component (see
`OverviewFicheDrawerHost`) that owns the drawer-state shape conversion +
portal mount + on-export wiring; do NOT alias `window.FicheDrilldownDrawer`
to a second name. Cross-reference: this section and the analogous note in
`05_REPORTING_AND_UI_ADAPTERS.md` "Consultant fiche correction pass".

---

## Standalone HTML Snapshot — read-only frozen cockpit (2026-05-11)

**Goal.** A single self-contained timestamped `.html` under
`output/exports/` that opens directly in Chrome and reproduces the JANSA
cockpit with **1:1 parity** to the live software — no pywebview, no
backend, no recomputation. Read-only by construction.

**Trigger.** Reports tab → "Exporter snapshot HTML" →
`window.jansaBridge.exportStandaloneHtmlSnapshot()` →
`Api.export_standalone_html_snapshot()` →
`src/reporting/standalone_html_snapshot.write_standalone_html_snapshot()`.

**Output.** `JANSA_STANDALONE_HTML__run_<NNNN>__<YYYY-MM-DD>_<HHMM>.html`
— ~80 MB at current run size (design ceiling 100 MB). Build time
~40–45 min, dominated by per-period fiche drilldown pre-builds.

### What gets baked into the file

Every payload comes from existing composed `Api.*_for_ui` methods. **No
business logic is recomputed** in the snapshot or the offline UI.

| Slot | Source(s) | Per-focus duality |
|---|---|---|
| `overview` | `Api.get_overview_for_ui` | yes (`focus_off`/`focus_on`) |
| `consultants` | `Api.get_consultants_for_ui` | yes |
| `contractors` | `Api.get_contractors_for_ui` | yes |
| `consultant_fiches[name]` | `Api.get_fiche_for_ui` | yes |
| `contractor_fiches[code]` | `Api.get_contractor_fiche_for_ui` | yes |
| `chain_intel` | `Api.get_chain_onion_intel(50)` | no (focus-invariant) |
| `counter_attack_home` | `Api.get_counter_attack_home` | no |
| `counter_attack_queues[bucket]` | `Api.get_counter_attack_queue(bucket, 500)` | no |
| `counter_attack_items[item_id]` | `Api.get_counter_attack_item` | no |
| `drilldowns[kind\|paramsJSON\|focus]` | `Api.get_documents_drilldown` | yes |
| `fiche_drilldowns[name\|fk\|lot\|focus[\|period]]` | `Api.get_doc_details` | yes |
| `dcc_panels[numero\|indice]` | `Api.get_document_command_center` | no (always focus=False, stale=30) |
| `chain_timelines[numero]` | `Api.get_chain_timeline` | no |
| `search_index` | derived from `dcc_panels` headers | no |

**Dashboard drilldown matrix** (kind × params × focus — 48 entries):
`submitted`, `pending_blocking`, `focus_priority {priority ∈ 1..4}`,
`operational_total/fresh/stale`, `operational_moex {scope ∈ {fresh,stale}?}`,
`operational_consultants {tier ∈ {PRIMARY,SECONDARY}?}`,
`operational_enterprise_ref`, `operational_priority {priority ∈ 1..4}`,
`visa_segment {segment}` (segments discovered dynamically from
`overview.visa_flow` keys). All for both focus modes.

**Fiche drilldown matrix** (per consultant × per focus mode):
- Global keys: `answered`, `open_count`, `open_blocking`, `s1/s2/s3/hm`,
  `open_ok`, `open_late`, `open_blocking_ok`, `open_blocking_late`,
  `open_non_blocking`.
- Per-lot keys (each `bloc3.lots[*].name`): `total`, `s1/s2/s3/hm`,
  `open_blocking_ok/late`, `open_non_blocking`.
- Per-period keys (each `bloc1[*].label`): `period_opened`,
  `period_closed`, `s1/s2/s3/hm`, `open_blocking_ok/late`,
  `open_non_blocking`.

This is the full set used by [fiche_base.jsx](../ui/jansa/fiche_base.jsx)
in `Bloc1::periodCell`, the bloc1 inline open-blocking spans, the bloc2
status headers, and bloc3 lot rows.

### Snapshot mode in data_bridge.js

`data_bridge.js` detects snapshot mode at the bottom of its IIFE:

```js
var IS_SNAPSHOT_MODE = Boolean(window.JANSA_SNAPSHOT_DATA)
  || Boolean(document.getElementById("jansa-snapshot-data"));
```

When true:
- `bridge.api` becomes a `Proxy` that returns
  `{success:false, disabled:true, error:"Action désactivée en mode snapshot (lecture seule)."}`
  for every mutating method (every `export_*_xlsx`,
  `generate_counter_attack_ai_audit_pack`, `run_pipeline_async`,
  `save_corrections`, `import_ged`, `import_reports`).
- `bridge.isSnapshot === true`. Reports cards read this flag to dim/
  disable the live exports.
- Every read method is replaced with an embedded-JSON resolver:
  - `init(focus)`, `refreshForFocus(focus)`, `loadFiche(name, focus)`,
    `loadContractorFiche(code, focus)` use `_pickFocus(bundle, focus)`
    that picks `focus_on` or `focus_off` (with opposite-focus fallback
    when one variant is missing or errored — relevant because the
    pre-existing `consultant_fiche._build_bloc1` datetime bug only fires
    on one focus side for one consultant).
  - `loadDrilldown(kind, params, focus)` looks up by
    `<kind>|<paramsJSON sort_keys=true>|<focus 0|1>` with opposite-
    focus fallback.
  - `loadFicheDrilldown(name, filterKey, lotName, focus, _stale, periodLabel)`
    looks up by `<name>|<filterKey>|<lot>|<focus>` with optional
    `|<period>` suffix; falls back to opposite-focus, then to the
    no-period variant when an exact key misses.
  - `loadDocumentCommandCenter(numero, indice)` does
    `numero|indice` → `numero|""` → `numero|*` fallback.
  - `searchDocuments(query)` substring-matches the offline
    `search_index` (numero, indice, titre, emetteur_code, emetteur_name,
    lot, status).
  - Counter-Attack home/queue/item resolve from
    `counter_attack_home/queues/items` verbatim.
- A fixed yellow bottom banner is rendered at DOMContentLoaded:
  `"MODE SNAPSHOT HTML — LECTURE SEULE — run … — data … — généré …"`,
  with `data-jansa-no-print="1"` so it disappears in print preview.

Live mode is untouched when no snapshot data is present (the snapshot
branch only runs inside `if (IS_SNAPSHOT_MODE) { … }`).

### HTML composer

`src/reporting/standalone_html_snapshot.py::_compose_html` inlines:
1. The production `<style>` block (verbatim from
   `ui/jansa-connected.html`, incl. print CSS).
2. React 18 + ReactDOM 18 + Babel-standalone from unpkg (same CDN as
   live; needs internet on first open).
3. `window.JANSA_SNAPSHOT_META` + `window.JANSA_SNAPSHOT_DATA` as
   inline JS literals, defended against `</script>` and U+2028/U+2029.
4. `ui/jansa/tokens.js` verbatim, then `applyJansaTheme('dark')`.
5. `ui/jansa/data_bridge.js` verbatim — single source of truth; the
   snapshot-mode branch lives there, NOT in a duplicate file.
6. Every `ui/jansa/*.jsx` component verbatim, in the same order as
   `jansa-connected.html`.
7. `ReactDOM.createRoot(...).render(React.createElement(window.App))`.

### Hard rules for future changes

- **Add a new read endpoint to `data_bridge.js` → also add a snapshot
  resolver inside `if (IS_SNAPSHOT_MODE)`.** The snapshot bridge is the
  same file as the live bridge; new read methods must declare a
  snapshot behavior or that surface will be silently empty offline.
- **Add a new clickable cell in a fiche/overview JSX → also add the
  corresponding `(kind, params)` or `(filterKey, lot, period)` entry
  to `_DASHBOARD_DRILLDOWNS` / `_FICHE_FILTER_KEYS_*` in
  `standalone_html_snapshot.py`.** Otherwise the snapshot returns
  "non disponible" on that click.
- **Add a new mutating action → also add it to the snapshot Proxy's
  mutating-list and confirm the Reports/page card honors
  `bridge.isSnapshot`.** Mutating actions must NOT silently no-op in
  live mode — only in snapshot mode.
- **Do NOT bake business logic into the snapshot bridge.** The bridge
  only filters, slices, and substring-matches embedded payloads. KPI
  arithmetic, bucket logic, latest-indice logic, DCC tags, Chain+Onion,
  pass rates stay on the Python side and are baked into `data` at build
  time.
- **Snapshot file size budget: 100 MB.** Adding new pre-built endpoints
  must respect this. If a new endpoint would push the file over the
  limit, gate it behind a sampling/cap parameter in the builder.

---

*Back to [[00_START_HERE]]*
