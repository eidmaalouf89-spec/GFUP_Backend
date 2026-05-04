# Phase 6B — Counter-Attack Read API (IMPLEMENTATION RECORD)

**Location:** `docs/implementation/PHASE_6B_READ_API.md`
**Status:** IMPLEMENTED — validated against the live `output/intermediate/COUNTER_ATTACK_ITEMS.csv` (3,369 rows).
**Master plan:** `docs/implementation/PHASE_6_COUNTER_ATTACK_MASTER.md`
**Protocol:** `docs/implementation/READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md`
**Predecessor:** `docs/implementation/PHASE_6A_ACTION_KERNEL_EXECUTION_PLAN.md`
**Risk:** MEDIUM (read-only over an existing artifact; touches `app.py` + `data_bridge.js`).

---

## 1. What Was Built

A read-only screen-payload adapter over the Phase 6A artifact
`output/intermediate/COUNTER_ATTACK_ITEMS.csv`.

Three pywebview `Api` methods + matching JS bridge methods. No UI page in
6B. No artifact mutation. No business-logic recomputation.

| Layer | Symbol | Location |
|---|---|---|
| Backend query | `get_counter_attack_home()` | `src/reporting/counter_attack_query.py` |
| Backend query | `get_counter_attack_queue(bucket, limit=500)` | `src/reporting/counter_attack_query.py` |
| Backend query | `get_counter_attack_item(item_id)` | `src/reporting/counter_attack_query.py` |
| `Api` method | `Api.get_counter_attack_home()` | `app.py` (after `get_chain_timeline`) |
| `Api` method | `Api.get_counter_attack_queue(bucket, limit=500)` | `app.py` |
| `Api` method | `Api.get_counter_attack_item(item_id)` | `app.py` |
| Bridge method | `jansaBridge.loadCounterAttackHome()` | `ui/jansa/data_bridge.js` (after `loadDrilldown`) |
| Bridge method | `jansaBridge.loadCounterAttackQueue(bucket, limit)` | `ui/jansa/data_bridge.js` |
| Bridge method | `jansaBridge.loadCounterAttackItem(itemId)` | `ui/jansa/data_bridge.js` |

---

## 2. Why It Exists

Phase 6 demands a non-technical cockpit that says "Do this first. Here is
why. Here is the action." Phase 6A produced the deterministic action
artifact. Phase 6B is the thin adapter layer that turns that artifact into
ready-made screen payloads, so the future cockpit (Phase 6C) renders only
— it never calculates buckets, ownership, deadlines, exposure, or
attackability. That guarantee is enforced here.

---

## 3. Files Read

```
docs/implementation/READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md
docs/implementation/PHASE_6_COUNTER_ATTACK_MASTER.md
docs/implementation/PHASE_6A_ACTION_KERNEL_EXECUTION_PLAN.md
context/guardrail.txt
context/03_UI_FEED_MAP.md
context/05_OUTPUT_ARTIFACTS.md
README.md
app.py                                         (lines 25–55, 100–140, 820–1195)
ui/jansa/data_bridge.js                        (full file)
src/reporting/document_command_center.py       (path-pattern reference only)
src/reporting/counter_attack_builder.py        (path-pattern + column-contract reference)
output/intermediate/COUNTER_ATTACK_ITEMS.csv   (header row + sample row only)
```

---

## 4. Files Created

```
src/reporting/counter_attack_query.py          (NEW; 433 lines)
docs/implementation/PHASE_6B_READ_API.md       (this file)
```

## 5. Files Modified (additive)

```
app.py                                         (+58 lines; 3 Api methods after get_chain_timeline)
ui/jansa/data_bridge.js                        (+98 lines; 3 bridge methods after loadDrilldown)
```

`git diff -- app.py` and `git diff -- ui/jansa/data_bridge.js` show only
`+` lines after the diff hunk headers — no removals, no rewording, no
existing-block edits.

## 6. Files NOT Touched (forbidden set, all confirmed clean for this session)

```
src/reporting/counter_attack_builder.py
src/reporting/document_command_center.py
src/reporting/focus_ownership.py
src/reporting/chain_timeline_attribution.py
src/chain_onion/**
src/pipeline/**
src/flat_ged/**
src/run_memory.py
src/report_memory.py
src/effective_responses.py
data/run_memory.db
data/report_memory.db
output/intermediate/COUNTER_ATTACK_ITEMS.csv
output/chain_onion/**
ui/jansa/counter_attack.jsx                    (does not exist; not created in 6B)
ui/jansa/shell.jsx
ui/jansa-connected.html
scripts/build_counter_attack.py
```

---

## 7. Payload Contracts

### 7.1 `get_counter_attack_home()` — present artifact

```json
{
  "available": true,
  "summary": {
    "total_today": 3369,
    "recommended_first_bucket": "FERMER_MAINTENANT"
  },
  "buckets": [
    {"bucket": "FERMER_MAINTENANT",     "label": "À fermer maintenant",                          "count": 1466, "priority": 1, "description": "..."},
    {"bucket": "SECONDAIRE_EXPIRE",     "label": "Secondaire expiré — décision MOEX requise",     "count": 0,    "priority": 2, "description": "..."},
    {"bucket": "DECISION_MOEX",         "label": "Décision MOEX — arbitrage requis",              "count": 216,  "priority": 3, "description": "..."},
    {"bucket": "ENTREPRISE_A_RELANCER", "label": "Entreprise à relancer",                         "count": 807,  "priority": 4, "description": "..."},
    {"bucket": "CONSULTANT_A_ATTAQUER", "label": "Consultant à attaquer",                         "count": 643,  "priority": 5, "description": "..."},
    {"bucket": "SUJET_REUNION",         "label": "Sujet réunion critique",                        "count": 0,    "priority": 6, "description": "..."},
    {"bucket": "MOEX_SHAME_INTERNAL",   "label": "MOEX interne — exposition à traiter",           "count": 237,  "priority": 7, "description": "..."}
  ]
}
```

Display order is fixed in `BUCKET_DISPLAY_ORDER` and is intentionally
distinct from the Phase 6A first-match-wins assignment order documented
in `context/05_OUTPUT_ARTIFACTS.md`. The forbidden phrase `"Honte MOEX"`
appears nowhere in the payload, code, or this doc.

### 7.2 `get_counter_attack_home()` — missing artifact (empty state)

```json
{
  "available": false,
  "message": "Le module Contre-attaque n'est pas encore généré.",
  "summary": {"total_today": 0, "recommended_first_bucket": null},
  "buckets": []
}
```

### 7.3 `get_counter_attack_queue(bucket, limit=500)` — present artifact

```json
{
  "available": true,
  "bucket": "CONSULTANT_A_ATTAQUER",
  "bucket_label": "Consultant à attaquer",
  "count": 643,
  "rows": [
    {
      "item_id": "...",
      "numero": "245028",
      "indice": "B",
      "subject_label": "...",
      "actor": "...",
      "reason": "En attente de ... depuis N jours.",
      "recommended_action": "Relancer ...; escalader si pas de réponse sous 5 jours.",
      "risk_level": "HIGH",
      "days_open": 35,
      "days_late": 18,
      "open_dcc_ref": {"numero": "245028", "indice": "B"}
    }
  ]
}
```

Actor fallback chain (binding):
`actor_to_call → primary_actor → emetteur_name → emetteur_code → ""`.

### 7.4 `get_counter_attack_queue(bucket)` — missing artifact

```json
{
  "available": false,
  "message": "Le module Contre-attaque n'est pas encore généré.",
  "bucket": "SECONDAIRE_EXPIRE",
  "bucket_label": "Secondaire expiré — décision MOEX requise",
  "count": 0,
  "rows": []
}
```

### 7.5 `get_counter_attack_item(item_id)` — present artifact, found

```json
{
  "available": true,
  "found": true,
  "header": {
    "item_id": "248001__A",
    "numero": "248001",
    "indice": "A",
    "subject_label": "...",
    "actor": "...",
    "bucket": "CONSULTANT_A_ATTAQUER",
    "bucket_label": "Consultant à attaquer",
    "risk_level": "LOW"
  },
  "what_is_it": "...",
  "why_here": ["...", "Retard accumulé : N jours.", "Sujet ouvert depuis N jours."],
  "recommended_action": "Relancer ...; escalader si pas de réponse sous 5 jours.",
  "evidence": ["...", "[A 0-SAS] ...", "[A BET Electricité <GED+REPORT_COMMENT>] ..."],
  "timeline": [],
  "open_dcc_ref": {"numero": "248001", "indice": "A"}
}
```

`timeline` is intentionally `[]` in 6B. The cockpit reaches the existing
chain timeline through the Document Command Center using `open_dcc_ref`
(via `window.openDocumentCommandCenter(numero, indice)`).

### 7.6 `get_counter_attack_item(item_id)` — unknown id (artifact present)

```json
{
  "available": true,
  "found": false,
  "message": "Élément introuvable dans la contre-attaque actuelle."
}
```

### 7.7 `get_counter_attack_item(item_id)` — missing artifact

```json
{
  "available": false,
  "found": false,
  "message": "Le module Contre-attaque n'est pas encore généré."
}
```

---

## 8. Identity / dtype Lock

`COUNTER_ATTACK_ITEMS.csv` is read with:

```python
pd.read_csv(
    _artifact_path(),
    dtype={
        "item_id": "string",
        "numero": "string",
        "indice": "string",
        "family_key": "string",
        "emetteur_code": "string",
    },
    keep_default_na=False,
)
```

This is a hard requirement: the Phase 4 leading-zero bug (`045080 →
45080`) must not re-emerge. Verified at runtime: every identity column
reports `dtype.name == "string"` and the artifact contains numeros that
start with `0` after read.

---

## 9. Validation Performed

### 9.1 Compile

```
python -m py_compile src/reporting/counter_attack_query.py
python -m py_compile app.py
node --check ui/jansa/data_bridge.js
```
All three returned success.

### 9.2 API surface check (sandbox-stubbed pywebview)

```
get_counter_attack_home  -> True
get_counter_attack_queue -> True
get_counter_attack_item  -> True
```

### 9.3 Empty-state (monkey-patched `_artifact_path`)

Three calls, three friendly empty payloads, no exceptions raised.
Real artifact untouched.

### 9.4 Real-artifact payload check

```
home OK:  total_today=3369  recommended=FERMER_MAINTENANT
queue OK: FERMER_MAINTENANT          count=1466  rows_returned=5
queue OK: SECONDAIRE_EXPIRE          count=0     rows_returned=0
queue OK: DECISION_MOEX              count=216   rows_returned=5
queue OK: ENTREPRISE_A_RELANCER      count=807   rows_returned=5
queue OK: CONSULTANT_A_ATTAQUER      count=643   rows_returned=5
queue OK: SUJET_REUNION              count=0     rows_returned=0
queue OK: MOEX_SHAME_INTERNAL        count=237   rows_returned=5
item OK:  id=248000__A  bucket=FERMER_MAINTENANT  evidence_count=3
unknown-item OK
dtype lock OK  (any leading-zero numero in artifact: True)
ALL CHECKS PASS
```

Forbidden phrase `"Honte MOEX"` absent in every payload (asserted in
home and per-bucket queue payloads).

### 9.5 Scope of changes (this session only)

```
src/reporting/counter_attack_query.py    NEW  (433 lines)
app.py                                   +58 lines (additive only)
ui/jansa/data_bridge.js                  +98 lines (additive only)
docs/implementation/PHASE_6B_READ_API.md NEW  (this file)
```

No forbidden file in §6 was modified by this session.

---

## 10. Known Limitations

1. **No caching.** Each call re-reads the CSV. The artifact is small
   (3,369 rows × 28 cols), so this is fine for V1; revisit only if
   profiling shows it's a bottleneck.
2. **No `focus`/`stale_days` parameters.** The artifact is already
   focus-agnostic (Phase 6A pre-filters by `focus_owner_tier != "CLOSED"`).
   Adding these later would require both a 6A schema change and a 6B
   contract bump.
3. **`timeline` is always `[]`.** Phase 6B does not invent timeline data.
   The cockpit uses `open_dcc_ref` to reach the existing
   `get_chain_timeline` endpoint via DCC.
4. **Evidence is read-only derivation.** `evidence` is a list of
   plain-French strings derived from `evidence_summary`,
   `chain_observations_full` (last 3), and `consultant_reports_full`
   (last 3). No raw JSON is exposed to the UI. Phase 6A's evidence
   columns are the source of truth — 6B does not enrich them.
5. **V2 methods deferred.** `get_counter_attack_subjects()`,
   `get_counter_attack_actors()`, advanced filters, exports, treated
   state, and AI pack generation are NOT in 6B. They belong to Phase 6D.
6. **No `_loadCoreData` change.** The new bridge methods are on-demand.
   They do NOT participate in the four-call `Promise.allSettled` that
   runs at shell mount. The 6C cockpit will own its own state.

---

## 11. Risks / Uncertainty

1. **Artifact-side observation: `primary_actor` carries an Onion layer
   name in some `CONSULTANT_A_ATTAQUER` rows** (e.g.
   `"Secondary Consultant Delay"` instead of a real consultant entity).
   This originates in Phase 6A's fallback to `ONION_SCORES.top_layer_name`
   when `CHAIN_TIMELINE_ATTRIBUTION` cannot resolve a true actor. 6B
   passes the value through unchanged (correct per the §11 boundary in
   the Phase 6B prompt: "If a needed field is missing from the artifact,
   escalate. Do not patch Phase 6A silently."). Flagging here for Phase
   6A authors to consider whether a non-empty entity-name fallback (e.g.
   the contractor name when the layer is `L1_CONTRACTOR_QUALITY`) would
   be a better display string. **No 6B change recommended.**
2. **Two zero-count buckets** (`SECONDAIRE_EXPIRE`, `SUJET_REUNION`) in
   the current run. The contract still ships them with `count: 0` so the
   future cockpit always renders 7 cards. This reflects the artifact's
   actual content, not a 6B bug.
3. **No app startup smoke run.** `python app.py` requires PyWebView and
   was not executed in the sandbox; only static `py_compile` and the
   sandbox-stubbed class-method check were run. The implementing
   environment should run `python app.py` once before sign-off to confirm
   no startup regression.

---

## 12. Dependency for Phase 6C

Phase 6C must consume these three bridge methods only. It must NOT:

- Re-read `COUNTER_ATTACK_ITEMS.csv` directly from JSX.
- Add or modify computation in JSX.
- Bypass `open_dcc_ref` by computing DCC parameters itself.
- Eager-load Counter-Attack data in `_loadCoreData` (the cockpit owns
  its own state, populated only when the user navigates to the page).

The 6B bridge contract is the only allowed integration point.

---

## 13. Recommendation

**VALIDATED.**

All payload shapes match the §8/§9 contract from the Phase 6B prompt.
Empty-state behaves correctly. Forbidden phrase absent. Identity dtype
lock holds. Diffs are strictly additive. No forbidden files touched in
this session. One minor observation on a Phase 6A artifact display
string is noted in §11 — not a 6B blocker.
