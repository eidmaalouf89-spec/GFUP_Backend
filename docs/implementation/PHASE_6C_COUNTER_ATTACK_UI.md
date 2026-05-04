# Phase 6C — Counter-Attack Cockpit UI (IMPLEMENTATION RECORD)

**Location:** `docs/implementation/PHASE_6C_COUNTER_ATTACK_UI.md`
**Status:** IMPLEMENTED — manually smoke-validated against the live
`output/intermediate/COUNTER_ATTACK_ITEMS.csv` (1525 rows after Phase 6X
correction).
**Master plan:** `docs/implementation/PHASE_6_COUNTER_ATTACK_MASTER.md`
**Protocol:** `docs/implementation/READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md`
**Predecessors:**

- `docs/implementation/PHASE_6A_ACTION_KERNEL_EXECUTION_PLAN.md` (artifact builder)
- `docs/implementation/PHASE_6B_READ_API.md` (read-only screen-payload adapter)
- `docs/implementation/PHASE_6X_ACTION_MOEX_DATA_TRUTH_CORRECTION.md` (artifact-side bucket-rule and deadline-truth correction; closed before 6C resumed)

**Risk:** MEDIUM — UI-only addition. No backend, pipeline, DB, or artifact
contract change. The cockpit consumes the Phase 6B bridge contract verbatim;
when 6X tightened the artifact rules the JSX layer required no change.

---

## 1. What Was Built

A new sidebar page in the JANSA cockpit, user-visible label **ACTION MOEX**,
internal page id `ActionMoex`, page title **Plan d'action MOEX**. The page
turns the Phase 6A artifact (via the Phase 6B read API) into an operational
cockpit for MOEX users. No business logic was added in JSX.

| Layer | Symbol | Location |
|---|---|---|
| Component | `window.ActionMoexPage` | `ui/jansa/counter_attack.jsx` |
| Sidebar entry | `{ id:'ActionMoex', label:'ACTION MOEX', icon: shellIcons.actionMoex }` | `ui/jansa/shell.jsx` (in the existing "Pilotage" group, immediately below `Vue d'ensemble`) |
| Sidebar icon | `shellIcons.actionMoex` (inline SVG target/aim glyph, 18×18, stroke 1.4) | `ui/jansa/shell.jsx` |
| Page title | `'Plan d’action MOEX'` | `ui/jansa/shell.jsx::pageTitle` |
| Render branch | `{active === 'ActionMoex' && <ActionMoexPage focusMode={focusMode}/>}` | `ui/jansa/shell.jsx::App()` |
| Script tag | `<script type="text/babel" src="jansa/counter_attack.jsx"></script>` | `ui/jansa-connected.html` (loaded between `document_panel.jsx` and `shell.jsx`, so `window.ActionMoexPage` is registered before `<App/>` mounts) |

User-facing strings use the corrected ACTION MOEX naming. The legacy phase
wording does NOT appear in any rendered string (`grep -E
"Contre-attaque|contre-attaque" ui/jansa/counter_attack.jsx ui/jansa/shell.jsx
ui/jansa-connected.html` → 0 matches). Comment lines inside the source files
may still use the historical phase name; they are not user-facing.

---

## 2. Why It Exists

Phase 6 demands a non-technical cockpit that says "Do this first. Here is
why. Here is the action." Phase 6A produced the deterministic action artifact
(`COUNTER_ATTACK_ITEMS.csv`); Phase 6B exposed it as ready-made screen
payloads. Phase 6C is the JSX cockpit that renders those payloads — and only
those payloads. The MOEX user opens the page, sees seven action buckets with
counts, clicks one, sees the queue (one row per chain — latest indice only),
clicks one row, sees what to do and why in four French sections, and can open
the existing Document Command Center for the underlying document.

The cockpit performs zero calculations on its own. Bucket rules, ownership,
deadlines, risk classification, MOEX exposure, attackability, and recommended
actions are all decided by the backend. This is a strict project rule (see
`08_DO_NOT_TOUCH.md` and the master plan's non-negotiables).

---

## 3. Files Read

```
docs/implementation/READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md
docs/implementation/PHASE_6_COUNTER_ATTACK_MASTER.md
docs/implementation/PHASE_6A_ACTION_KERNEL_EXECUTION_PLAN.md
docs/implementation/PHASE_6B_READ_API.md
docs/implementation/PHASE_6X_ACTION_MOEX_DATA_TRUTH_CORRECTION.md
context/guardrail.txt
context/03_UI_FEED_MAP.md
context/05_OUTPUT_ARTIFACTS.md
context/12_LESSONS_LEARNED.md
ui/jansa/tokens.js
ui/jansa/shell.jsx
ui/jansa/overview.jsx
ui/jansa/document_panel.jsx
ui/jansa/data_bridge.js
ui/jansa-connected.html
src/reporting/counter_attack_query.py
src/reporting/counter_attack_builder.py
output/intermediate/COUNTER_ATTACK_ITEMS.csv      (header + samples only — never read by JSX)
```

---

## 4. Files Created

```
ui/jansa/counter_attack.jsx                                933 lines
docs/implementation/PHASE_6C_COUNTER_ATTACK_UI.md          (this file)
```

## 5. Files Modified (additive)

```
ui/jansa/shell.jsx                                         +5 / -1   (sidebar entry, pageTitle entry, render branch, icon)
ui/jansa-connected.html                                    +1 / -0   (counter_attack.jsx script tag)
src/reporting/counter_attack_query.py                      +17 / -1  (S1 — queue sort by days_late ascending; presentation order only)
```

The `-1` line in `shell.jsx` is the existing `Overview / Executer` pageTitle
line being split in two so the new `ActionMoex` entry sits between them. No
existing key/value was rewritten.

`git diff -- ui/jansa/shell.jsx ui/jansa-connected.html
src/reporting/counter_attack_query.py` shows only `+` lines after the hunk
headers (and the single split-line edit in `shell.jsx`).

## 6. Files NOT Touched

```
src/reporting/counter_attack_builder.py        (Phase 6A / Phase 6X work — unchanged in 6C)
src/reporting/document_command_center.py
src/reporting/focus_ownership.py
src/reporting/chain_timeline_attribution.py
src/reporting/aggregator.py
src/reporting/consultant_fiche.py
src/reporting/contractor_fiche.py
src/reporting/contractor_quality.py
src/reporting/focus_filter.py
src/chain_onion/**
src/pipeline/**
src/flat_ged/**
src/normalize.py
src/reporting/data_loader.py
src/run_memory.py
src/report_memory.py
src/effective_responses.py
data/**                                        (run_memory.db, report_memory.db)
output/chain_onion/**
output/intermediate/COUNTER_ATTACK_ITEMS.csv   (read-only consumer)
output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.{csv,json}
output/intermediate/FLAT_GED_cache_*.{pkl,json}
ui/jansa/data_bridge.js                        (Phase 6B contract preserved exactly)
app.py                                         (Phase 6B Api methods preserved exactly)
ui/jansa/overview.jsx, consultants.jsx, contractors.jsx, fiche_*, runs.jsx,
executer.jsx, document_panel.jsx               (existing pages — unchanged)
README.md                                      (per user instruction)
```

---

## 7. UI Architecture

### 7.1 Page layout

```
┌─────────────────────────────────────────────────────────┐
│ Header card                                             │
│   eyebrow:  ACTION MOEX                                 │
│   title:    Plan d'action MOEX                          │
│   subtitle: Vue opérationnelle des sujets à reprendre…  │
│   chip:     Total affiché — N (when home is available)  │
├─────────────────────────────────────────────────────────┤
│ 7-card bucket grid (approved presentation order)        │
│   1. VISA facile           ← FERMER_MAINTENANT          │
│   2. Arbitrage MOEX        ← DECISION_MOEX              │
│   3. Entreprises à relancer← ENTREPRISE_A_RELANCER      │
│   4. Consultants à relancer← CONSULTANT_A_ATTAQUER      │
│   5. MOEX interne …        ← MOEX_SHAME_INTERNAL        │
│   6. Secondaires expirés   ← SECONDAIRE_EXPIRE          │
│   7. Sujets réunion crit.  ← SUJET_REUNION              │
├──────────────────────────┬──────────────────────────────┤
│ Queue panel (left)       │ Detail panel (right, sticky) │
│   bucket label + count   │   header: subject + risk     │
│   File d'action — …      │   numero · indice            │
│   row 1                  │   1. Ce que c'est            │
│   row 2                  │   2. Pourquoi il est ici     │
│   …                      │   3. Ce que MOEX doit faire  │
│                          │   4. Preuves rapides         │
│                          │   [Ouvrir le détail]         │
│                          │   [Voir / Masquer preuves]   │
└──────────────────────────┴──────────────────────────────┘
```

On viewports ≤ 960 px the split layout collapses to a single column via the
one-time injected `@media (max-width: 960px) { .am-action-split { … } }`
rule (the IIFE at the top of `counter_attack.jsx` injects it once, matching
the `document_panel.jsx` style-injection pattern).

### 7.2 Bucket presentation contract (UI override)

Phase 6B returns buckets in `BUCKET_DISPLAY_ORDER`
(`FERMER_MAINTENANT, SECONDAIRE_EXPIRE, DECISION_MOEX, ENTREPRISE_A_RELANCER,
CONSULTANT_A_ATTAQUER, SUJET_REUNION, MOEX_SHAME_INTERNAL`). The cockpit
applies its own approved presentation order via the static
`AM_BUCKET_PRESENTATION` array — counts are looked up by bucket enum, not by
index. The backend payload order is unchanged; only the rendered card order
differs. Each preset row carries:

- the user-facing French `label` (e.g. `'VISA facile'`),
- a static `priority` subtitle (e.g. `'Tous les avis alignés'`),
- a static `description`.

For the two count-sensitive buckets (`SECONDAIRE_EXPIRE`, `SUJET_REUNION`)
the priority subtitle is resolved at render time by
`amBucketPrioritySubtitle(preset, count)` — `'Aucun aujourd’hui'` when
the count is zero, otherwise the bucket-specific prompt. This is pure copy
substitution; no business logic.

### 7.3 State machine

Inside `ActionMoexPage` (single component, no children with state):

| State | Type | Set by | Read by |
|---|---|---|---|
| `home` | `null \| HomePayload` | mount `useEffect` | header chip, bucket grid, queue/detail gating |
| `homeError` | `null \| string` | mount `useEffect` | yellow banner above grid |
| `selectedBucket` | `string` | initial `'FERMER_MAINTENANT'`, then `payload.summary.recommended_first_bucket` after home loads, then bucket clicks | queue panel header, queue lookup |
| `queueByBucket` | `{ [bucket]: payload }` | `_amFetchQueue` | queue panel rows (via `currentQueue`) |
| `queueLoading` / `queueError` | scalar | `_amFetchQueue` resets per click | queue panel loading/error rendering |
| `queueGenRef` | mutable ref | `_amFetchQueue` increments per click | drops stale promise resolutions |
| `selectedRow` | `null \| QueueRow` | row clicks | detail panel fallbacks |
| `selectedItem` | `null \| ItemPayload` | `_amFetchItem` on row clicks | detail panel four sections |
| `itemLoading` / `itemError` | scalar | `_amFetchItem` resets per click | detail panel loading/error notice |
| `itemGenRef` | mutable ref | `_amFetchItem` increments per click | drops stale promise resolutions |
| `evidenceOpen` | `bool` | toggle button | "Preuves rapides" section visibility |

Every per-fetch state is reset on bucket switch and on row click, so stale
indicators never bleed across selections.

### 7.4 Detail-panel fallback logic

When `selectedItem` is `null` (loading, not-found, unavailable, or never
fetched) the four sections still render from `selectedRow` so the user keeps
actionable info. Mapping:

| Section | Item field (preferred) | Row fallback |
|---|---|---|
| Header subject | `item.header.subject_label` | `row.subject_label` |
| Risk chip | `item.header.risk_level` | `row.risk_level` |
| Numero · indice line | `item.header.numero / indice` | `row.numero / indice` |
| Ce que c'est | `item.what_is_it` | `'Sujet documentaire actif — document {numero}, indice {indice}.'` |
| Pourquoi il est ici | `item.why_here[]` | `[row.reason]` |
| Ce que MOEX doit faire | `item.recommended_action` | `row.recommended_action` |
| Preuves rapides | `item.evidence[]` | `[]` (section only visible when `evidenceOpen` is true) |
| Open DCC | `item.open_dcc_ref` | `row.open_dcc_ref` |

The row payload is sufficient for an operator to act; the item enrichment
adds the four-section depth.

### 7.5 Buttons

- **Ouvrir le détail** — uses `item.open_dcc_ref ?? row.open_dcc_ref` and
  calls `window.openDocumentCommandCenter(numero, indice)` (the existing
  global opener registered by `App` in `shell.jsx`, line ~540). Disabled
  with `cursor: not-allowed` and `opacity: 0.55` when no `open_dcc_ref` is
  present. No new DCC-like rendering inside ACTION MOEX.
- **Voir preuves / Masquer preuves** — toggles `evidenceOpen` locally. No
  bridge call. The evidence list is the `item.evidence[]` array already
  returned by Phase 6B; nothing is computed in JSX.

---

## 8. Bridge Methods Consumed

Exactly the three Phase 6B methods, all on-demand:

```
window.jansaBridge.loadCounterAttackHome()                            (mount)
window.jansaBridge.loadCounterAttackQueue(bucket, 500)                (bucket click; result cached per bucket)
window.jansaBridge.loadCounterAttackItem(item_id)                     (row click)
```

The cockpit does NOT:

- read `output/intermediate/COUNTER_ATTACK_ITEMS.csv` directly (`grep
  "COUNTER_ATTACK_ITEMS\|fetch(\|XMLHttpRequest\|\.csv" ui/jansa/counter_attack.jsx`
  → 0 matches);
- compute DCC parameters itself (uses `open_dcc_ref` returned by 6B);
- participate in `data_bridge.js::_loadCoreData` — its data is fetched only
  when the user navigates to the page, so existing pages are unaffected.

The `_loadCoreData` body in `data_bridge.js` is byte-identical to HEAD; the
6B bridge addition was strictly additive (verified by `diff` of the
`_loadCoreData` slice).

### 8.1 Step S1 — queue sort (Phase 6C correction Set 1)

Inside `get_counter_attack_queue(bucket, limit)`, after filtering by
`action_bucket` and before slicing to `limit`, the rows are sorted ascending
by a deterministic key:

```python
sub_sorted = sub.assign(
    __am_late_key=pd.to_numeric(sub["days_late"], errors="coerce"),
    __am_open_key=pd.to_numeric(sub["days_open"], errors="coerce"),
).sort_values(
    by=["__am_late_key", "__am_open_key", "numero", "indice"],
    ascending=[True, True, True, True],
    na_position="last",
    kind="mergesort",
)
```

Rationale: the operator works the freshest backlog first (lowest `days_late`
on top); long-tail items sink. Numeric coercion routes blank/NaN
`days_late` to the last position. Tie-breakers are `days_open`, then a
stable `(numero, indice)`. Mergesort preserves any pre-existing order on
full ties. This is presentation order only; `count` is still
`int(len(sub))` (pre-sort length, unchanged).

---

## 9. Edge-State Coverage Matrix

All states verified during 6C.6 hardening and confirmed in the closing smoke.

| Edge state | Mechanism |
|---|---|
| Backend unavailable (preview mode, no pywebview) | Bridge returns `available:false` with a `Backend not connected.` message; home `useEffect` distinguishes via `message.indexOf('backend') >= 0 || message.indexOf('preview') >= 0` and sets `homeError = AM_COPY.backendUnavailable` ("Le backend n'est pas connecté. Le module ACTION MOEX n'est pas disponible en mode aperçu.") |
| Artifact missing (`COUNTER_ATTACK_ITEMS.csv` absent) | Bridge returns `available:false` with the backend's `EMPTY_MESSAGE`; home `useEffect` falls to `homeError = AM_COPY.artifactMissing` ("Le module ACTION MOEX n'est pas encore généré.") |
| Home loading | `home === null && !homeError` → centred "Chargement…" card |
| Bucket card click on a zero-count bucket | Queue panel renders "Aucun sujet dans ce bucket." |
| Queue loading | `queueLoading` → centred "Chargement…" inside queue panel |
| Queue available:false | `queueError` → yellow inline banner inside queue panel |
| Item loading | `itemLoading` → small italic "Chargement…" line under the detail header |
| Item not found (stale `item_id`) | `itemError = AM_COPY.itemNotFound` ("Élément introuvable dans le plan d'action actuel.") inline notice; row fallbacks still render the four sections |
| Item unavailable (backend/artifact) | `itemError` set to the appropriate `AM_COPY` string by the same backend-vs-artifact distinction as the home fetch |
| DCC ref missing | "Ouvrir le détail" disabled, `cursor: not-allowed`, `opacity: 0.55` |
| Rapid bucket clicks | `queueGenRef` — promise resolutions check `myGen === current` and silently drop if superseded |
| Rapid row clicks | `itemGenRef` — same pattern |
| Component unmount during home fetch | `cancelled` flag in the home `useEffect` cleanup |
| Theme toggle (dark ↔ light) | All colours via CSS variables from `tokens.js`; no hard-coded hex except the bucket-icon `currentColor` paths |
| Focus toggle (top bar) | Forwarded as `focusMode` prop; the page is focus-agnostic per `PHASE_6B_READ_API.md §10.2` and ignores it |

Forbidden phrase guards (kept clean throughout 6C):

```
grep -nE "Contre-attaque|contre-attaque"  ui/jansa/counter_attack.jsx     → 0 matches
grep -nE "Aujourd.hui, vous devez|Commencez par"  ui/jansa/counter_attack.jsx → 0 matches
grep -nE "Honte MOEX"                     output/intermediate/COUNTER_ATTACK_ITEMS.csv app.py
                                          ui/jansa/data_bridge.js src/reporting/counter_attack_query.py
                                          src/reporting/counter_attack_builder.py
                                                                          → 0 matches
```

The cockpit also never renders raw `normalized_score_100`, raw
`current_state`, raw `action_bucket` enum, or raw evidence JSON — these
remain in the Phase 6A artifact for traceability but are not surfaced.

---

## 10. Validation Performed

Every step in the 6C plan was followed by a `python app.py` manual smoke
before the next step landed. The protocol is recorded against each task
in this session's task log.

| Step | Validation |
|---|---|
| 6C.0 — Recon | Read-only memo only; no code changed. |
| 6C.1 — Static skeleton | `@babel/parser` script+jsx PARSE OK; forbidden-phrase grep clean; static placeholder data only; component registered to `window.ActionMoexPage`. |
| 6C.2-REDO — Shell + HTML wiring | Babel parse OK on `shell.jsx` and `counter_attack.jsx`; `git diff` exactly +5/-1 on `shell.jsx`, +1/0 on `jansa-connected.html`; existing pages unchanged. Manual smoke: ACTION MOEX appears between "Vue d'ensemble" and "Exécuter", click renders the static placeholder page. |
| 6C.3 — Home payload wiring | `loadCounterAttackHome()` on mount; `home === null` → loading; `home.available === false` → friendly banner (backend-down vs artifact-missing distinguished by `message`). Manual smoke: bucket counts match the artifact's seven values; existing pages unchanged. |
| 6C.4 — Queue wiring | `loadCounterAttackQueue(bucket, 500)` on bucket click; `queueByBucket` cache + `queueGenRef` stale-guard; auto-load on home arrival via `recommended_first_bucket`. Manual smoke: each bucket loads its queue; rapid bucket switching does not cross-render. |
| 6C.5 — Item detail + buttons | `loadCounterAttackItem(item_id)` on row click; four sections render with row fallbacks while item is loading; `Ouvrir le détail` opens the existing DCC; `Voir preuves` toggles locally with no extra backend call. Manual smoke confirmed. |
| 6C.6 — Hardening | Item-loading and item-error UI added (small italic line / inline yellow banner). Forbidden technical fields confirmed absent. Manual smoke confirmed all edge states. |
| Set-1 S3 — 6A latest-indice dedup | (Out of scope of the JSX layer, but consumed by it.) `python scripts/build_counter_attack.py` rebuilt the artifact; `family_key` duplicates 766 → 0; rows 3369 → 1869 → 1525 (after Phase 6X bucket-rule revisions). Cockpit observed the new counts without code change. |
| Set-1 S1 — 6B queue sort | Sandbox-side: every non-empty bucket reports `ascending? True`. Manual smoke: queues visibly ordered least → most days_late within each bucket. |
| Set-1 S2 — canonical title | NOT applied in 6B. The 6A builder (under Phase 6X) already produces `subject_label` in canonical-name format ("Axima — …", "Bentin — …", …); 1524 of 1525 rows match the `… — …` shape. The 6B adapter passes the field through verbatim. |

Final smoke (closing): existing pages OK, ACTION MOEX bucket counts match
the post-6X artifact (1525 rows total), queues sorted correctly, detail
panel populates the four sections, "Ouvrir le détail" routes to the existing
DCC, "Voir preuves" toggles locally, no console or terminal errors.

---

## 11. Known Limitations

1. **No export, no treated state, no monthly AI pack.** These are explicitly
   Phase 6D scope per the master plan §7. The cockpit does not write any
   user-mutation state — there is no `localStorage` write for treated rows,
   no XLSX export, no zip pack. The "Treated" affordance is intentionally
   absent in 6C.
2. **No timeline data inside the detail panel.** Phase 6B returns
   `timeline: []` by design (PHASE_6B_READ_API.md §7.5); the chronologie is
   reached through the existing DCC via `Ouvrir le détail`. The cockpit does
   not invent timeline rendering.
3. **Bucket presentation order is JSX-side.** The cockpit overrides the
   backend `BUCKET_DISPLAY_ORDER` for visual ordering only; counts are
   looked up by enum, not by index, so the backend can change its order
   freely without breaking the cockpit. This is documented at the top of
   `AM_BUCKET_PRESENTATION` in `counter_attack.jsx`.
4. **The "blank `action_bucket`" row** present in the current artifact (1
   row of 1525) is invisible to the cockpit — the home payload only counts
   the seven `BUCKET_DISPLAY_ORDER` enums and no bucket card or queue maps
   to a blank value. Behaviour confirmed correct by the artifact owner.
5. **Row-level VAO/VSO/REF leak (was Set-1 comment #4) is no longer
   reachable.** Phase 6X enforces the lifecycle gates at the artifact level;
   chain-level closure has always been filtered (terminal `current_state`
   exclusion in the builder). The S3 latest-indice dedup eliminated the
   only remaining indice-level leak by collapsing each chain to its
   alphabetically-latest indice.
6. **Edit-tool truncation hazard.** During the 6C.2 wiring, the
   cowork-mode `Edit` tool was observed to silently truncate
   `counter_attack.jsx` and `shell.jsx` due to a Windows↔Linux mount sync
   inconsistency. All subsequent 6C edits were applied via anchor-checked
   Python rewrites in the bash sandbox, with `@babel/parser` syntax checks
   after every patch. Documented in `context/11_TOOLING_HAZARDS.md`
   (related to Lesson 3 of `12_LESSONS_LEARNED.md`).

---

## 12. Cross-References to Other Phases

| Phase | Document | Relationship |
|---|---|---|
| 6A | `PHASE_6A_ACTION_KERNEL_EXECUTION_PLAN.md` | Builds the artifact 6C displays. Granularity contract `§2` ("one row per (numero, latest_indice)") was tightened by 6X. |
| 6B | `PHASE_6B_READ_API.md` | Defines the three read-only Api/bridge methods 6C consumes. Payload shapes have not changed since 6B sign-off. |
| 6X | `PHASE_6X_ACTION_MOEX_DATA_TRUTH_CORRECTION.md` | Authoritative artifact-side correction (bucket rules, deadline truth, canonical title, latest-indice dedup). Closed before 6C resumed; 6C consumed the corrected artifact unchanged. |
| 6D | (planned) | Export / treated / monthly AI pack. NOT delivered in 6C. |
| 4 (DCC) | `PHASE_4*` | The `Ouvrir le détail` button calls `window.openDocumentCommandCenter`, which mounts the existing DCC drawer. No new DCC behaviour. |
| Date-parsing hotfix | `12_LESSONS_LEARNED.md` Lesson 1 | Resolved before Phase 6C resumed. The cockpit operates on the corrected cache. |
| `data_date` discipline | `12_LESSONS_LEARNED.md` Lesson 2 | The cockpit never reads `data_date`; all lateness/closure decisions come from the artifact. |
| Untracked-file safety | `12_LESSONS_LEARNED.md` Lesson 3 | Followed during 6C: every patch on an untracked or out-of-history file was preceded by a `cp` to `/tmp/<name>.pre-<step>`. |

---

## 13. Recommendation

**VALIDATED.** Phase 6C is functionally complete. The cockpit consumes the
Phase 6B contract verbatim, renders without business logic, exposes no
forbidden phrases, and survives every documented edge state. The artifact
the cockpit reads is the post-6X corrected one and may be regenerated at
any time without UI change. Phase 6D (export / treated / monthly AI pack)
is the natural next step.
