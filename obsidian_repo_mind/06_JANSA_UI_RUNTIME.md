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

*Back to [[00_START_HERE]]*
