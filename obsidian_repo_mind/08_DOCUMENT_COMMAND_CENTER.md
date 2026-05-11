#repo-map #dcc #document-command-center #ui

# Document Command Center

> The search and inspection panel embedded in the JANSA UI.
> Backend: `src/reporting/document_command_center.py`. Frontend: `ui/jansa/document_panel.jsx`.

---

## What it is

The Document Command Center (DCC) is a right-side drawer panel that opens from any JANSA page. It has two modes:
- **Search mode:** full-text search across the document universe
- **Doc mode:** full 7-section panel for a specific `(numero, indice)`

---

## Search

- Full-text search over `dernier_df` — fields: `numero`, `titre`, `emetteur`, `lot`, `indice`
- Returns a ranked list of matching documents
- Backend: `document_command_center.search_documents(query, focus, stale_days, limit)`
- When caller passes `numero` without `indice`, `_resolve_doc_rows` picks the alphabetically latest indice (e.g. A < B < C → picks C)

---

## Document panel — 7 sections

| Section | Content |
|---|---|
| **Header** | Document identity and latest status |
| **Responses** | All workflow responses for the selected indice |
| **Comments** | Decisive responses with associated comments |
| **Revision history** | All indices for the same family (chain) |
| **Chronologie** | Chain timeline with delay attribution (from `CHAIN_TIMELINE_ATTRIBUTION.json`) |
| **Tags** | Primary ownership tag + secondary signal tags |
| **Warnings** | Data quality flags |

---

## Tag taxonomy

### Primary tags (exactly one per document)

| Tag | Meaning |
|---|---|
| `Att Entreprise — Dans les délais` | Contractor's turn, within deadline |
| `Att Entreprise — Hors délais` | Contractor's turn, overdue |
| `Att BET Primaire` | Primary consultant's turn |
| `Att BET Secondaire` | Secondary consultant's turn |
| `Att MOEX — Facile` | MOEX turn, easy arbitration |
| `Att MOEX — Arbitrage` | MOEX turn, arbitration needed |
| `Clos / Visé` | Terminal (closed/approved) |

### Secondary tags (multi-valued, optional)

| Tag | Threshold |
|---|---|
| `Refus multiples` | Multiple rejections |
| `Commentaire manquant` | Missing decisive comment |
| `Secondaire expiré` | Secondary window expired |
| `Très ancien` | `TRES_ANCIEN_THRESHOLD_DAYS = 60` |
| `Cycle dépassé` | Any phase over budget |
| `Chaîne longue` | Total chain > 120 days |

**All tag computation is in the backend** (`document_command_center.py`). Frontend renders only.

Constants in `document_command_center.py`:
- `ENTREPRISE_DELAY_THRESHOLD_DAYS = 15`
- `TRES_ANCIEN_THRESHOLD_DAYS = 60`
- See `context/06_EXCEPTIONS_AND_MAPPINGS.md §I.3` before modifying.

---

## API endpoints

| Method | Signature | Returns |
|---|---|---|
| `search_documents` | `(query, focus, stale_days, limit)` | Match list |
| `get_document_command_center` | `(numero, indice, focus, stale_days)` | Full panel payload incl. chronologie |
| `get_chain_timeline` | `(numero)` | Standalone chain timeline; normalizes to 6-digit zero-padded `family_key` |

`get_chain_timeline` blocks on `_chain_data_ready` (the pre-warm guard). Returns `{"error": ...}` if data unavailable.

---

## Entry points to the panel

Any JANSA page can open the DCC via the global:
```js
window.openDocumentCommandCenter(numero, indice)
```
Pass `null` for `indice` to let the backend resolve to the latest indice.

Active entry points:
1. Topbar search button → opens in search mode
2. Drilldown row click → opens in doc mode
3. ChainOnionPanel issue rows (`overview.jsx`) → `window.openDocumentCommandCenter(issue.family_key, null)`
4. Action MOEX "Ouvrir le détail" button → same global

**Standing rule:** any new UI component that renders a list of documents MUST wire this global.

---

## Backend files

| File | Role |
|---|---|
| `src/reporting/document_command_center.py` | Sole source of all business logic: tag computation, search ranking, response grouping, revision history, comment extraction |
| `src/reporting/chain_timeline_attribution.py` | Produces `CHAIN_TIMELINE_ATTRIBUTION.json` consumed by the Chronologie section |
| `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json` | Pre-computed per-chain timing (refreshed at app startup) |

---

## Frontend files

| File | Role |
|---|---|
| `ui/jansa/document_panel.jsx` | The drawer component. Pure rendering — no business logic. Mounted once at App root in `shell.jsx` |
| `ui/jansa/shell.jsx` | `panelState` useState, `<DocumentCommandCenterPanel>` mount, topbar search button, `window.openDocumentCommandCenter` global setter |
| `ui/jansa/data_bridge.js` | `searchDocuments()` and `loadDocumentCommandCenter()` bridge methods |
| `ui/jansa/fiche_base.jsx` | `DrilldownDrawer` — accepts `onRowClick` prop; rows call `window.openDocumentCommandCenter` |
| `ui/jansa/fiche_page.jsx` | Passes `onRowClick={(doc) => window.openDocumentCommandCenter(doc.numero, doc.indice)}` to DrilldownDrawer |
| `ui/jansa-connected.html` | Loads `document_panel.jsx` between `executer.jsx` and `shell.jsx` |

---

## Architecture rule

> The backend (`document_command_center.py`) is the **sole source of truth** for tag computation, response grouping, search ranking, and all business logic. The `document_panel.jsx` JSX layer renders only. Do not move logic into the JSX.

---

## Phase 9 (`latest_enriched_view`, 2026-05-11)

- `compute_dcc_tags_bulk(ctx)` now iterates
  `reporting.latest_chain_view.latest_enriched_view(ctx)` instead of
  `ctx.dernier_df`. The duplicate copy of `compute_dcc_tags_bulk` at
  line 667 was removed during Step 6 (one canonical implementation
  remains). Current row count: 2,553.
- `_resolve_doc_rows(ctx, numero, indice)` resolves `indice=None` via
  `ctx.latest_chain_df.latest_indice` (canonical chain truth) with an
  existence guard: if the resolved indice is not present in
  `ctx.dernier_df` for that numero, the helper falls back to the
  alphabetical-max indice and emits a `logger.warning`. This is the
  Step 6b existence-guard that handles the permanent Decision-3 N≈1
  asymmetry for numero 253100. See
  `context/06_EXCEPTIONS_AND_MAPPINGS.md` §F-3 and
  `context/11_TOOLING_HAZARDS.md` §H-9.
- `search_documents` deduplicates results by latest indice using the
  `_is_latest` tiebreaker (Step 6).
- Revision history view (`_build_revision_history`) intentionally
  reads `latest_enriched_view(ctx)` to scope to the latest-indice
  chain context, then renders all indices from the chain timeline
  (the chain timeline itself comes from
  `CHAIN_TIMELINE_ATTRIBUTION.json`).

See `README.md §Phase 9` for the full migration summary.

---

**Related:** [[07_CHAIN_ONION_MENTAL_MODEL]] · [[05_REPORTING_AND_UI_ADAPTERS]] · [[09_ACTION_MOEX_COUNTER_ATTACK]] · [[06_JANSA_UI_RUNTIME]]

*Back to [[00_START_HERE]]*
