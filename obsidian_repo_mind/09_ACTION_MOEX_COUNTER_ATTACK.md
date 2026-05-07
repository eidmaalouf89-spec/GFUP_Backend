#repo-map #counter-attack #action-moex #phase6

# Action MOEX / Counter-Attack Layer

> Phase 6A–D implementation. Fully wired as of 2026-05-04.
> See `context/03_UI_FEED_MAP.md §D` and `docs/implementation/PHASE_6*` for full implementation records.

---

## What it is

The **Action MOEX** (internally "Counter-Attack") layer is a MOEX-facing priority queue and action cockpit. It answers: "for every document chain where MOEX must act, what should happen next, ranked by urgency?"

It has three sub-layers built across Phase 6:
- **Phase 6A** — artifact builder (`counter_attack_builder.py`) → produces `COUNTER_ATTACK_ITEMS.csv`
- **Phase 6B** — read API (`counter_attack_query.py`) → 3 backend query endpoints
- **Phase 6C** — UI page (`counter_attack.jsx`) — user-facing label: **ACTION MOEX**
- **Phase 6D** — AI Audit Pack export (`counter_attack_ai_pack.py`)

---

## Phase 6A — Artifact builder

**File:** `src/reporting/counter_attack_builder.py`

**Run via:** `python scripts/build_counter_attack.py`

**Output:** `output/intermediate/COUNTER_ATTACK_ITEMS.csv`

**What it builds:**
- One row per chain (latest indice, deduped — 1,524 distinct `family_key` rows as of Phase 6X R3 validation)
- Assigns each chain to an `action_bucket` based on DCC split deadline truth + Chain/Onion wait-day fields
- Computes `days_late`, `risk_level`, `is_internal_moex_exposure`, `is_external_attackable`
- Generates `evidence_summary`, `chain_observations_summary`, `consultant_reports_summary`
- `subject_label` format: `"AXIMA — titre…"`, `"BENTIN — titre…"` (canonical emetteur name)

**Key output columns:**

```
item_id, numero, indice, family_key, subject_label,
emetteur_code, emetteur_name, primary_actor, actor_to_call,
action_bucket, action_label, plain_reason, recommended_action,
risk_level, evidence_summary, days_open, days_late,
current_state, normalized_score_100,
is_internal_moex_exposure, is_external_attackable,
chain_observations_summary/full/refs,
consultant_reports_summary/full/refs/available
```

**Terminal states excluded from artifact:**
`CLOSED_VAO`, `CLOSED_VSO`, `DEAD_AT_SAS_A`, `ABANDONED_CHAIN`, `VOID_CHAIN`, `UNKNOWN_CHAIN_STATE`

**IDENTITY_COLUMNS** (read as string dtype to preserve leading zeros): `item_id`, `numero`, `indice`, `family_key`, `emetteur_code`

---

## Phase 6B — Read API

**File:** `src/reporting/counter_attack_query.py`

**Reads from:** `output/intermediate/COUNTER_ATTACK_ITEMS.csv`

**Missing artifact behavior:** returns `available=false` empty state (does not crash)

**Three endpoints (all exposed on `app.py::Api`):**

| Endpoint | Signature | Returns |
|---|---|---|
| `get_counter_attack_home()` | — | Home payload: bucket summary, counts, total |
| `get_counter_attack_queue(bucket, limit=500)` | bucket name | List of items for bucket, sorted `days_late ASC` (NaN last), then `days_open`, `numero`, `indice` |
| `get_counter_attack_item(item_id)` | item_id | Single item detail; `timeline=[]` by design — Chronologie reached via DCC |

**Bucket display order:**

```
FERMER_MAINTENANT
SECONDAIRE_EXPIRE
DECISION_MOEX
ENTREPRISE_A_RELANCER
CONSULTANT_A_ATTAQUER
SUJET_REUNION
MOEX_SHAME_INTERNAL
```

**Important:** these 3 endpoints are **on-demand** — NOT part of the startup `Promise.allSettled` in `data_bridge.js`. They don't populate any `window.*` global.

---

## Phase 6C — UI page (ACTION MOEX)

**File:** `ui/jansa/counter_attack.jsx`

**Internal page id:** `ActionMoex`
**Component:** `window.ActionMoexPage`

**Wiring in `ui/jansa-connected.html`:** loaded between `document_panel.jsx` and `shell.jsx`

**Bridge methods consumed:**
- `jansaBridge.loadCounterAttackHome()` — on mount
- `jansaBridge.loadCounterAttackQueue(bucket, 500)` — on bucket click (per-bucket cache)
- `jansaBridge.loadCounterAttackItem(item_id)` — on row click

**Stale-promise guards:** `queueGenRef`, `itemGenRef` for rapid clicks.

**Cockpit rule:** performs **no business logic**. Bucket rules, ownership, deadlines, risk, MOEX exposure, attackability, and recommended actions are all decided by the backend (Phase 6A/6X).

**Bucket presentation order** in JSX: `AM_BUCKET_PRESENTATION` array — counts are looked up by enum key, not by index. Backend display order remains free to evolve.

**"Ouvrir le détail"** button uses `window.openDocumentCommandCenter(numero, indice)` — no new DCC surface added.

**"Voir preuves / Masquer preuves"** toggles evidence locally without a backend call.

---

## Phase 6D — AI Audit Pack export

**File:** `src/reporting/counter_attack_ai_pack.py`

**App method:** `Api.generate_counter_attack_ai_audit_pack()`

**UI trigger:** Reports page → "Générer Pack Audit IA" button (`shell.jsx` lines 877–910)

**Bridge:** `window.jansaBridge.generateAiAuditPack()` (`data_bridge.js` lines 329–360)

**Output:** `output/exports/JANSA_AI_AUDIT_PACK_<YYYYMMDD>_<HHMMSS>.zip`

---

## SAS administrative status — explicit constraint

From `README.md` inline note:
> SAS administrative statuses (VAO-SAS / VSO-SAS / REF-SAS where applicable) must never be used to create technical MOEX arbitration. SAS remains visible in history and may drive SAS-gate analytics, but MOEX arbitration is based only on real technical consultant responses.

---

## Files not fully present / gaps

- `COUNTER_ATTACK_ITEMS.csv` is produced by `scripts/build_counter_attack.py` (not by the main pipeline or `run_chain_onion.py`) — requires an explicit separate run
- Phase 6A builder requires Chain+Onion outputs to already exist in `output/chain_onion/`
- Phase 6 sub-plans (`PHASE_6A_INTELLIGENCE_ARTIFACT.md`, `6B`, `6C`, `6D`) exist in `docs/implementation/` as closed records
- **Phase 6 (Intelligence layer as a full page)** is listed as the next "killer module" work-stream in `README.md §Implementation status` — the sub-plans are implemented but the broader Intelligence layer concept is partially realized

---

**Related:** [[07_CHAIN_ONION_MENTAL_MODEL]] · [[08_DOCUMENT_COMMAND_CENTER]] · [[05_REPORTING_AND_UI_ADAPTERS]] · [[16_OPEN_QUESTIONS_AND_RISKS]]

*Back to [[00_START_HERE]]*

---

## Scope clarification (2026-05-07)

ACTION MOEX is a curated action plan, not a full operational
backlog. The authoritative operational backlog lives in the
operational dashboard
(src/reporting/aggregator.py::compute_operational_dashboard,
exposed as window.OVERVIEW.operational). ACTION MOEX presents the
subset of that backlog for which counter_attack_builder has assigned
an action bucket.

Known gap: 1,659 operational rows currently have no action_bucket.
Bucket-coverage extension is a follow-up phase, out of scope for the
operational dashboard redesign.

Cross-reference: `docs/implementation/OPERATIONAL_DASHBOARD_REDESIGN.md`
§5 (Action MOEX relationship) and §Phase 5 Decision.
