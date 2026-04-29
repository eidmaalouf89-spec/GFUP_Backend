# Phase 6C — Intelligence UI Page (Filter Rail + Work-Tray List)

This MD is **self-contained**. An agent assigned only this phase can execute it cold without reading any other file in `docs/implementation/`.

> **Phase 6 has been split into four sub-phases (6A → 6B → 6C → 6D).** This is 6C. **Phase 6A and 6B must already be merged** (the CSV artifact and the endpoints both exist). Do NOT add export/treated state in this phase — that is Phase 6D.

---

## 1. Objective

Add a new sidebar entry **Intelligence** (also labelled "Cuisine d'attaque" in the page header) and a new page `IntelligencePage` that renders:

- A left filter rail with chips grouped by category, showing live facet counts.
- A right work-tray list of matching documents (newest first), with row click → existing Document Command Center.
- Saved presets ("Gain facile", "Arbitrage MOEX dormants", "Refus multiples", "Backlog secondaire") as one-click filter combinations.
- An empty state (friendly French message + "Lancer le pipeline" CTA) when the artifact is missing.

This phase does **not** include:
- Bulk export (Phase 6D)
- "Treated" localStorage state (Phase 6D)
- Per-row checkboxes (Phase 6D)
- Pipeline edits (Phase 6A)
- Endpoints (Phase 6B)

---

## 2. Risk

**MEDIUM.** New JSX page, new sidebar entry, new HTML script tag. No backend touch (endpoints already shipped in 6B).

If 6B endpoints are missing, **stop and escalate** — this page cannot function without them.

---

## 3. Standard Rules (embedded — do not skip)

### Tooling note — read before any investigation
Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) to verify file content, file size, or function presence in Windows-mounted source files (`app.py`, `ui/jansa/*.jsx`, `ui/jansa-connected.html`, etc.). The Cowork sandbox's Linux mount caches a stale view of Windows files and has, in past sessions, falsely reported `app.py` as 864 lines when it was actually ~1200, and missed methods like `get_chain_onion_intel` that demonstrably existed. If a bash inspection contradicts the Read tool, the Read tool wins. Do not raise "repo is broken / method missing / file truncated" alarms from bash-only evidence — cross-check with Read first. Bash is fine for *executing* scripts (running `python main.py`, `pytest`, etc.); just don't use it to reason about source-file state. See `context/11_TOOLING_HAZARDS.md`.

### Priorities
1. App must always run.
2. Backend stays source of truth — UI calculates nothing.
3. Preserve working logic.
4. Minimal safe changes.
5. No fake certainty.

### Mandatory behavior
- Read every listed file fully before editing.
- All filtering, counting, sorting happens via 6B endpoints. UI never recomputes any aggregate.
- Match existing JSX style: inline `style` objects with CSS variables, fontFamily from `window.JANSA_FONTS`, no Tailwind, no external libraries.
- Follow the existing card/section visual language used in `consultants.jsx` and `contractors.jsx`.
- Filter changes are **debounced ~300ms** before triggering an endpoint call; rapid chip-toggling does not flood the bridge.
- Empty state must be graceful: when the endpoint returns `{"error": "...artifact not yet produced..."}`, render a friendly French message and a button routing to `Executer`. No console error trace shown to the user.
- Row click opens the existing Document Command Center via `window.openDocumentCommandCenter(numero, indice)`.

### Forbidden moves
- Do NOT modify `app.py` or `data_bridge.js` (those are 6B's territory; only consume them).
- Do NOT modify any backend file.
- Do NOT add export logic (Phase 6D).
- Do NOT add localStorage / "treated" state (Phase 6D).
- Do NOT add row checkboxes or bulk-action toolbar (Phase 6D).
- Do NOT modify `fiche_base.jsx` or any other shared UI module beyond what is listed in §6 MODIFY.
- Do NOT introduce a virtualization library. If list length > 1000, the truncation banner from 6B suffices; for ≤1000 rows a plain scrollable container is fine.
- Do NOT redefine filter taxonomy. Filter values come from the 6B facets endpoint.

### Risk policy
MEDIUM. Apply directly after the plan is restated. Stop and escalate if visual integration with the existing JANSA shell becomes ambiguous (e.g. the sidebar layout doesn't accept a new entry cleanly).

---

## 4. Current State (Findings)

### 4a. Sidebar / shell
File: `ui/jansa/shell.jsx`. Sidebar entries today (per existing structure): Overview, Discrepancies (focus only), Consultants, Contractors, Runs, Executer, Utilities. New entry **Intelligence** goes between **Contractors** and **Runs**.

The shell exposes `navigateTo(name)` and tracks `active`. Each page is rendered conditionally based on `active === 'PageName'`.

### 4b. Bridge methods (must exist from 6B)
- `window.jansaBridge.loadIntelligenceFacets()`
- `window.jansaBridge.loadIntelligenceDocuments(filters, limit, sort)`

If either is missing, stop — Phase 6B is the prerequisite.

### 4c. Document Command Center hook
`window.openDocumentCommandCenter(numero, indice)` is global (per `README.md` §Document Command Center). Calling it opens the right-side drawer over any page.

### 4d. Existing visual primitives
- Section header pattern: `consultants.jsx:Section` (~line 56).
- Card with halo + title + content: `OvCard` in `overview.jsx` (~line 15).
- Empty state styling: `consultants.jsx`/`contractors.jsx` empty-state divs.

Reuse these patterns; do not invent new ones.

---

## 5. User Value

- One screen combining tag filters visually → instant attackable list.
- Operators click "Gain facile" preset and see every quick-win document.
- Counts on every chip show what's currently in scope.
- Click a row → DCC drawer opens with full evidence; UI navigation context preserved.

---

## 6. Files

### READ (required, before any edit)
- `ui/jansa/shell.jsx` — full file (focus on Sidebar entries and the active-page render block)
- `ui/jansa/overview.jsx` — for the `OvCard` / `OvEyebrow` patterns
- `ui/jansa/consultants.jsx` — for the `Section` and Card patterns
- `ui/jansa/contractors.jsx` — for the chip pattern
- `ui/jansa/document_panel.jsx` — confirm `window.openDocumentCommandCenter` signature
- `ui/jansa/data_bridge.js` — confirm `loadIntelligenceFacets` and `loadIntelligenceDocuments` exist (Phase 6B)
- `ui/jansa-connected.html` — script tag list and load order
- `ui/jansa/tokens.js` — design tokens
- `README.md` §Document Command Center, §JANSA UI Architecture, §What Not To Touch
- This MD

### MODIFY
- `ui/jansa/shell.jsx` —
  - Add `Intelligence` sidebar entry between Contractors and Runs.
  - Add the route block: `{active === 'Intelligence' && <IntelligencePage focusMode={focusMode} onNavigate={navigateTo}/>}`.
- `ui/jansa-connected.html` — add `<script type="text/babel" data-presets="react" src="ui/jansa/intelligence.jsx"></script>` next to the other JSX script tags.

### CREATE
- `ui/jansa/intelligence.jsx` — new page exporting `IntelligencePage` to `window`.

### DO NOT TOUCH
- `app.py`, all backend files
- `ui/jansa/data_bridge.js` (Phase 6B's territory; consume only)
- `ui/jansa/fiche_base.jsx`, `fiche_page.jsx`, `document_panel.jsx`, `executer.jsx`, `runs.jsx`, `consultants.jsx`, `contractors.jsx`, `overview.jsx` (read only as patterns)
- `runs/run_0000/`, `data/*.db`
- `output/intermediate/INTELLIGENCE_TAGS.csv` (artifact — produced by 6A)

---

## 7. Plan

### Step 1 — Build `ui/jansa/intelligence.jsx` skeleton
```jsx
const { useState: useStateInt, useEffect: useEffectInt, useMemo: useMemoInt, useRef: useRefInt } = React;

function IntelligencePage({ focusMode, onNavigate }) {
  const F = window.JANSA_FONTS;
  const [facets, setFacets] = useStateInt(null);
  const [filters, setFilters] = useStateInt({});         // {primary_tags:[], secondary_tags:[], lots:[], emetteur_codes:[], owner_tiers:[], stale_days_min, stale_days_max}
  const [docs, setDocs] = useStateInt({rows: [], total_count: 0, truncated: false});
  const [loading, setLoading] = useStateInt(true);
  const [error, setError] = useStateInt(null);
  const debounceRef = useRefInt(null);

  // Load facets once on mount
  useEffectInt(() => {
    (async () => {
      const f = await window.jansaBridge.loadIntelligenceFacets();
      if (f && f.error) { setError(f.error); setLoading(false); return; }
      setFacets(f);
    })();
  }, []);

  // Reload documents when filters change (debounced)
  useEffectInt(() => {
    if (!facets) return;
    setLoading(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      const r = await window.jansaBridge.loadIntelligenceDocuments(filters, 1000, "newest");
      if (r && r.error) setError(r.error);
      setDocs(r || {rows: [], total_count: 0, truncated: false});
      setLoading(false);
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [filters, facets]);

  if (error && !facets) return <IntEmpty onNavigate={onNavigate}/>;

  return (
    <div style={{padding:'32px 40px 60px', display:'grid', gridTemplateColumns:'320px 1fr', gap:24, animation:'fadeInUp 0.4s cubic-bezier(.4,0,.2,1)'}}>
      <IntFilterRail facets={facets} filters={filters} setFilters={setFilters} onNavigate={onNavigate}/>
      <IntWorkTray docs={docs} loading={loading} filters={filters} clearFilters={() => setFilters({})}/>
    </div>
  );
}
```

### Step 2 — Filter rail (`IntFilterRail`)
Layout (top → bottom):

1. **Page eyebrow + title**: "Intelligence · Cuisine d'attaque" / large header.
2. **Presets section**: 4 buttons:
   - "Gain facile" → `setFilters({primary_tags:["Att MOEX — Facile"]})`
   - "Arbitrage MOEX" → `setFilters({primary_tags:["Att MOEX — Arbitrage"]})`
   - "Refus multiples" → `setFilters({secondary_tags:["Refus multiples"]})`
   - "Backlog secondaire" → `setFilters({primary_tags:["Att BET Secondaire"], secondary_tags:["Très ancien"]})`
3. **Filters** sections, each a collapsible section:
   - Primary tag (7 chips, count next to each from `facets.primary_tags`)
   - Secondary tag (6 chips, count from `facets.secondary_tags`)
   - Lot (multi-select; populate from `facets.lots`)
   - Émetteur (search box + chip list, from `facets.emetteurs` sorted by count desc)
   - Owner tier (chips: PRIMARY / SECONDARY / MOEX / CONTRACTOR / CLOSED, count from `facets.owner_tiers`)
   - Stale days (range: min/max number inputs)
4. **Clear all filters** button at the bottom.

Chip toggle behavior: clicking a chip toggles its presence in the corresponding filter array. Visual: selected chip uses `var(--accent-soft)` background and `var(--accent)` border.

### Step 3 — Work tray (`IntWorkTray`)
Layout:

1. **Toolbar**: shows total count, truncation banner if any, "Effacer les filtres" button. **No checkboxes, no export button in this phase.**
2. **Table** with columns: Numéro · Titre · Émetteur · Tag principal · Tags secondaires · Stale · Échéance · Tier.
3. Row visual: similar to `consultants.jsx` cards (compact, cursor pointer, hover background change).
4. Row click: `window.openDocumentCommandCenter(row.numero, row.indice)`.

Empty body state: if filters return zero rows, show "Aucun document ne correspond." in French, with a "Réinitialiser les filtres" button.

### Step 4 — Empty state when artifact missing (`IntEmpty`)
```jsx
function IntEmpty({ onNavigate }) {
  return (
    <div style={{padding:'80px 40px', textAlign:'center'}}>
      <div style={{fontSize:14, color:'var(--text-2)', marginBottom:16}}>
        Le fichier d'intelligence n'a pas encore été produit.
      </div>
      <div style={{fontSize:13, color:'var(--text-3)', marginBottom:24}}>
        Lancez le pipeline pour générer les tags par document.
      </div>
      <button onClick={() => onNavigate('Executer')} style={{
        padding:'10px 22px', fontSize:13, fontWeight:600,
        background:'var(--accent-soft)', color:'var(--accent)',
        border:'1px solid var(--accent-border)', borderRadius:9,
        cursor:'pointer', fontFamily:'inherit',
      }}>Lancer le pipeline →</button>
    </div>
  );
}
```

### Step 5 — Loading state
A simple "Chargement…" text in the work-tray area while a request is in flight. Do not freeze the filter rail — chips remain interactive (debounce handles fast toggling).

### Step 6 — Wire shell
In `ui/jansa/shell.jsx`:

1. Locate the Sidebar `nav` array. Add an entry for `Intelligence` between Contractors and Runs:
   ```js
   { id:'Intelligence', label:'Intelligence', icon: shellIcons.intelligence || shellIcons.search }
   ```
   Use an existing icon if available; otherwise reuse a "spark" / "filter" / "search" icon already in `shellIcons`.
2. Locate the active-page render block. Add:
   ```jsx
   {active === 'Intelligence' && <IntelligencePage focusMode={focusMode} onNavigate={navigateTo}/>}
   ```

### Step 7 — Register the script
In `ui/jansa-connected.html`, add next to existing JSX script tags:
```html
<script type="text/babel" data-presets="react" src="ui/jansa/intelligence.jsx"></script>
```

Order: after `data_bridge.js` (must be loaded for the bridge), after `tokens.js`, after `fiche_base.jsx` is fine (no dependency on it).

### Step 8 — Stop
Do NOT add export, checkboxes, or localStorage in this pass. Phase 6D handles all three.

---

## 8. Validation

| Check | How |
|---|---|
| App starts | `python app.py` launches |
| Sidebar entry | "Intelligence" visible in sidebar between Contractors and Runs |
| Empty state | Rename `INTELLIGENCE_TAGS.csv` temporarily; navigate to Intelligence → friendly French empty-state with CTA to Executer; no console error trace |
| Restored | Restore the file; reload; page renders normally |
| Facet counts | Each chip shows its count from the facets endpoint |
| Filter primary | Click "Att MOEX — Facile" chip → list shrinks; count matches facet |
| AND across categories | Add a secondary tag chip → list shrinks; count matches manual intersection |
| Preset Gain facile | Click "Gain facile" → only `Att MOEX — Facile` rows remain |
| Sort newest first | First row's `last_action_date` ≥ last row's |
| Truncation banner | Force a filter that matches > 1000 rows → banner appears |
| Row click | Click any row → DCC drawer opens for that doc |
| Debounce | Toggle 5 chips quickly → only one document call fires after the burst settles |
| No regression | Phase 1–5 + 6A + 6B unaffected |
| No console errors | All flows clean |

---

## 9. Cowork Handoff Prompt (paste-ready)

```
Objective:
Phase 6C — Add a sidebar entry "Intelligence" and a new IntelligencePage with a filter rail (chips per category, facet counts, presets) and a work-tray list of matching documents (newest first; row click opens DCC). NO export, NO checkboxes, NO localStorage in this phase. Those are Phase 6D.

Repository: GFUP_Backend / GF Updater v3 / 17&CO Tranche 2. Risk level: MEDIUM.

PREREQUISITE: Phase 6A and 6B must already be merged. window.jansaBridge.loadIntelligenceFacets and window.jansaBridge.loadIntelligenceDocuments must exist. output/intermediate/INTELLIGENCE_TAGS.csv must exist (Phase 6A). If absent, stop and escalate.

Read fully before editing:
- ui/jansa/shell.jsx (full file — Sidebar nav + active-page render block)
- ui/jansa/overview.jsx (OvCard / OvEyebrow patterns)
- ui/jansa/consultants.jsx (Section / card patterns)
- ui/jansa/contractors.jsx (chip patterns)
- ui/jansa/document_panel.jsx (confirm window.openDocumentCommandCenter signature)
- ui/jansa/data_bridge.js (confirm loadIntelligenceFacets + loadIntelligenceDocuments)
- ui/jansa-connected.html (script tag list and load order)
- ui/jansa/tokens.js (design tokens)
- README.md §Document Command Center, §JANSA UI Architecture, §What Not To Touch
- docs/implementation/PHASE_6C_INTELLIGENCE_UI_PAGE.md (this spec)

Do not touch:
- app.py and all backend files
- ui/jansa/data_bridge.js (Phase 6B's territory — consume only)
- ui/jansa/fiche_base.jsx, fiche_page.jsx, document_panel.jsx, executer.jsx, runs.jsx, consultants.jsx, contractors.jsx, overview.jsx (read only as patterns)
- runs/run_0000/, data/*.db
- output/intermediate/INTELLIGENCE_TAGS.csv (artifact — Phase 6A's output)

Implement:
1. Create ui/jansa/intelligence.jsx exporting IntelligencePage({focusMode, onNavigate}) to window. Page layout: 320px filter rail (left) + 1fr work-tray (right).
   • On mount, call window.jansaBridge.loadIntelligenceFacets(). If error → render IntEmpty (friendly French message + "Lancer le pipeline" button routing to Executer).
   • When filters change, debounce 300ms, then call loadIntelligenceDocuments(filters, 1000, "newest").
   • Filter rail sections (top→bottom):
     - Page eyebrow + title "Intelligence · Cuisine d'attaque"
     - Presets buttons: "Gain facile" / "Arbitrage MOEX" / "Refus multiples" / "Backlog secondaire" — each one-click sets the filters object directly.
     - Primary tag chips (7 + counts from facets.primary_tags)
     - Secondary tag chips (6 + counts from facets.secondary_tags)
     - Lot multi-select (from facets.lots)
     - Émetteur search + chip list (from facets.emetteurs)
     - Owner tier chips (from facets.owner_tiers)
     - Stale days min/max range inputs
     - "Effacer tous les filtres" button
   • Work tray:
     - Toolbar: total_count, truncation banner if truncated, "Effacer les filtres" button
     - Table columns: Numéro · Titre · Émetteur · Tag principal · Tags secondaires · Stale · Échéance · Tier
     - Row click: window.openDocumentCommandCenter(row.numero, row.indice)
     - Loading state: "Chargement…" while a request is in flight
     - Empty result: "Aucun document ne correspond." + "Réinitialiser les filtres" button
   • NO checkboxes, NO export button, NO localStorage / treated state — those are Phase 6D.
2. ui/jansa/shell.jsx: add Sidebar entry "Intelligence" between Contractors and Runs (reuse an existing icon — search/filter/spark). Add render line {active === 'Intelligence' && <IntelligencePage focusMode={focusMode} onNavigate={navigateTo}/>}.
3. ui/jansa-connected.html: add <script type="text/babel" data-presets="react" src="ui/jansa/intelligence.jsx"></script> next to other JSX tags, after data_bridge.js + tokens.js.
4. Match existing JSX style: inline style objects with CSS variables, fontFamily from window.JANSA_FONTS, no Tailwind, no external libraries.
5. STOP. Do not start 6D. Report completion.

Validation (must pass before reporting done):
- python app.py launches
- Sidebar shows "Intelligence" between Contractors and Runs
- Empty state renders gracefully when CSV is absent (rename test); restoring it makes the page work
- Each chip shows facet count
- Selecting "Gain facile" preset shows only Att MOEX — Facile rows
- AND across categories shrinks results correctly
- Sort: first row last_action_date ≥ last row's
- Truncation banner appears for buckets > 1000
- Row click opens DCC drawer
- Debounce: rapid chip toggling fires one document call after the burst settles
- Phase 1–5 + 6A + 6B unaffected
- No console errors

Report back:
- Diff of intelligence.jsx (new), shell.jsx, jansa-connected.html
- Sample facet counts and a sample filter-applied result count
- Confirmation of all validation steps

Hard rules:
- Backend stays source of truth. UI does NOT recompute counts or aggregate.
- All filtering / sorting via Phase 6B endpoints.
- Match existing JANSA visual language.
- NO export, NO checkboxes, NO localStorage in 6C — those are 6D.
- Do NOT proceed to 6D in the same pass.
```

---

## 10. Context Update (after merge)

- `context/01_RUNTIME_MAP.md` — note the new `Intelligence` route in shell.jsx.
- `context/03_UI_FEED_MAP.md` — record the Intelligence page → `loadIntelligenceFacets` / `loadIntelligenceDocuments` mapping.

If `context/` is missing the file, skip — do not create new context files in this phase.

---

## 11. Done Definition

- App launches cleanly with the new sidebar entry.
- IntelligencePage renders, filters work, presets work, row click opens DCC.
- Empty state graceful.
- Debounce works.
- Phase 1–5 + 6A + 6B unaffected.
- Diff scoped to: `ui/jansa/intelligence.jsx` (new), `ui/jansa/shell.jsx`, `ui/jansa-connected.html`.
- 6D NOT started.
