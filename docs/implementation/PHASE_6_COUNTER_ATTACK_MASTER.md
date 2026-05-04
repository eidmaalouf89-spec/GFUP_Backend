# Phase 6 — Counter-Attack Intelligence (MASTER PLAN)

**Location:** `docs/implementation/PHASE_6_COUNTER_ATTACK_MASTER.md`
**Status:** AUTHORITATIVE — single source of truth for Phase 6
**Project:** JANSA VISASIST / GFUP_Backend
**Companion protocol:** `docs/implementation/READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md`

---

## 0. Supersession Notice

> **This document supersedes all previous Phase 6 implementation plans in `docs/implementation`. Cowork and Claude Code must ignore older Phase 6 docs unless this file explicitly references them.**

The following older files are obsolete and must NOT be used as a source of truth:

```text
docs/implementation/PHASE_6A_INTELLIGENCE_ARTIFACT.md
docs/implementation/PHASE_6B_INTELLIGENCE_ENDPOINTS.md
docs/implementation/PHASE_6C_INTELLIGENCE_UI_PAGE.md
docs/implementation/PHASE_6D_INTELLIGENCE_EXPORT_AND_TREATED.md
```

These are moved to `docs/implementation/_superseded_phase6/` (or marked as superseded in place). Any concept they describe — `INTELLIGENCE_TAGS.csv` as the main artifact, a passive Intelligence filter/list page, UI-side analysis, or any old 6A/6B/6C/6D plan that does not match this master — is forbidden going forward.

---

## 1. Operational Objective

Phase 6 is called **Counter-Attack Intelligence**.

Phase 6 must build an operational cockpit that tells MOEX:

- What to close.
- What to decide.
- Who to relaunch.
- Who to attack.
- Which subject is becoming dangerous.
- What evidence supports it.

The cockpit must be usable by non-technical people. The user must not need to understand chain logic, onion scoring, consultant tiers, or workflow complexity.

---

## 2. Product Principle

**Phase 6 must not ask the user to analyze.**

It must say:

```text
Do this first.
Here is why.
Here is the evidence.
Here is the action.
```

Two operating modes:

- **Default mode** — simple, idiot-proof, action buckets. This is what ships.
- **Optional later mode** — expert / filters / forensic analysis. Only after the default mode works.

Reuse the existing repo logic — do not invent a parallel intelligence system:

- Document Command Center
- Focus ownership
- Chain timeline attribution
- Chain + Onion outputs
- Existing run/output conventions
- Existing bridge/API patterns

---

## 3. Non-Negotiable Rules

1. **No calculation in the UI.** Backend/pipeline produces truth. UI presents truth.
2. **No new database.** No DB schema change.
3. **No rewrites of existing logic.** Reuse Document Command Center, focus ownership, chain timeline attribution, chain/onion outputs, run memory, and existing bridge/API patterns.
4. **Additive changes only.** New files, new artifacts, new read-only endpoints, new UI page. Existing artifact contracts and existing dashboards stay unchanged.
5. **Deterministic artifacts.** Same inputs → same artifact.
6. **No DB write from treated state.** Treated state lives in `localStorage` only and is run-number scoped.
7. **No business logic in React.** Buckets, ownership, deadlines, MOEX exposure, attackability — all computed server-side.
8. **Action buckets, not lists.** The default cockpit shows action buckets, not raw filtered tables.
9. **Plain French operational text.** Reasons and actions are written for MOEX users, not engineers.

---

## 4. Phase 6A — Action Kernel / Evidence Artifact

### 4.1 Objective

Produce one deterministic backend artifact that converts existing chain/onion/focus/DCC logic into simple operational action items.

### 4.2 Required Artifact

```text
output/intermediate/COUNTER_ATTACK_ITEMS.csv
```

### 4.3 Optional Supporting Artifacts

```text
output/intermediate/SUBJECT_RISK_DOSSIERS.csv
output/intermediate/ACTOR_ATTACK_DOSSIERS.csv
```

### 4.4 Required Columns (`COUNTER_ATTACK_ITEMS.csv`)

```text
item_id
numero
indice
family_key
subject_label
emetteur_code
emetteur_name
primary_actor
actor_to_call
action_bucket
action_label
plain_reason
recommended_action
risk_level
evidence_summary
days_open
days_late
current_state
normalized_score_100
is_internal_moex_exposure
is_external_attackable
```

### 4.5 Minimum Action Buckets

```text
FERMER_MAINTENANT
DECISION_MOEX
SECONDAIRE_EXPIRE
ENTREPRISE_A_RELANCER
CONSULTANT_A_ATTAQUER
SUJET_REUNION
MOEX_SHAME_INTERNAL
```

### 4.6 Touchpoints

```text
src/reporting/document_command_center.py        read-only
src/reporting/focus_ownership.py                read-only
src/reporting/chain_timeline_attribution.py     read-only
output/chain_onion/*                            read-only
src/reporting/counter_attack_builder.py         NEW
src/pipeline/stages/stage_finalize_run.py       additive — register artifact only
context docs                                    update
```

### 4.7 Constraints

- Do not rewrite existing ownership logic.
- Do not invent a parallel chain/onion calculation.
- Do not modify existing artifacts.
- Pipeline must remain runnable end-to-end.

### 4.8 Risk

**HIGH** — touches pipeline/output layer.

### 4.9 Validation Gate

- `COUNTER_ATTACK_ITEMS.csv` exists at expected path.
- Row count plausible against the run.
- Same inputs → identical artifact.
- Buckets are non-empty where the run data supports them.
- `SECONDAIRE_EXPIRE` rows match existing ownership/countdown rules (primary replied, secondary expired beyond 10 days).
- All other pipeline outputs unchanged.

---

## 5. Phase 6B — Counter-Attack Read API

### 5.1 Objective

Expose read-only backend endpoints that serve ready-made screens, not raw filter data.

### 5.2 Required Methods

```text
get_counter_attack_home()
get_counter_attack_queue(bucket, limit=500)
get_counter_attack_item(item_id)
```

### 5.3 Optional Methods (V2)

```text
get_counter_attack_subjects()
get_counter_attack_actors()
```

### 5.4 Expected Payload Shapes

`get_counter_attack_home()`:

```json
{
  "summary": {
    "total_today": 47,
    "recommended_first_bucket": "FERMER_MAINTENANT"
  },
  "buckets": [
    {
      "bucket": "FERMER_MAINTENANT",
      "label": "À fermer maintenant",
      "count": 12,
      "priority": 1,
      "description": "Tous les avis sont disponibles, MOEX doit émettre le visa."
    }
  ]
}
```

`get_counter_attack_queue(bucket)`:

```json
{
  "bucket": "SECONDAIRE_EXPIRE",
  "rows": [
    {
      "item_id": "...",
      "subject_label": "CVC / Armoires climatisation",
      "actor": "Axima",
      "reason": "Secondaire expiré depuis 18 jours.",
      "recommended_action": "MOEX doit reprendre la main.",
      "risk_level": "High"
    }
  ]
}
```

`get_counter_attack_item(item_id)`:

```json
{
  "header": {},
  "why_here": [],
  "timeline": [],
  "recommended_action": "",
  "evidence": [],
  "open_dcc_ref": { "numero": "049512", "indice": "B" }
}
```

### 5.5 Touchpoints

```text
src/reporting/counter_attack_query.py     NEW
app.py                                    additive — read-only endpoints only
ui/jansa/data_bridge.js                   additive — bridge methods only
```

### 5.6 Constraints

- No DB.
- No pipeline mutation.
- No UI calculations.
- Missing artifact returns a friendly empty state, not an error.

### 5.7 Risk

**MEDIUM** — read-only over an existing artifact.

### 5.8 Validation Gate

- Home returns bucket counts.
- Queue returns rows for each bucket.
- Item detail returns evidence, timeline, and DCC opener.
- Missing artifact returns empty state cleanly.
- No regression on existing API endpoints.

---

## 6. Phase 6C — Counter-Attack Cockpit UI

### 6.1 Objective

Add a new sidebar page that lets a non-technical MOEX user know exactly what to do.

### 6.2 Page Naming

- Sidebar entry: **Contre-attaque**
- Operational header inside the page may read: **Cuisine d’attaque**

### 6.3 User Flow

```text
Home
→ Bucket
→ Queue
→ Item detail
→ Open DCC / Export / Mark treated
```

### 6.4 Home Screen

Top-level message in plain French. Example shape:

```text
Aujourd’hui, vous devez traiter 47 sujets.
Commencez par les 12 faciles.
```

Big action cards (priority order):

```text
1. À fermer maintenant
2. Secondaires expirés
3. Décisions MOEX
4. Entreprises à relancer
5. Consultants à attaquer
6. Sujets réunion critique
7. Honte MOEX interne
```

### 6.5 Queue Row Format

Forbidden (technical):

```text
245028 | normalized_score=82 | WAITING_CORRECTED_INDICE
```

Required (operational):

```text
SNI — Câblage éclairage R1
Entreprise doit resoumettre
Bloqué depuis 35 jours après REF MOEX
Action: relancer SNI
[Ouvrir] [Preuves] [Traité]
```

### 6.6 Item Detail Format

Every item must answer, in order:

1. **What is it?**
2. **Why is it here?**
3. **What should I do?**
4. **What evidence supports it?**

Details (full timeline, raw chain events, scoring) live behind:

```text
Voir preuves
Voir chronologie
Ouvrir DCC
```

### 6.7 Touchpoints

```text
ui/jansa/counter_attack.jsx      NEW
ui/jansa/shell.jsx               additive — sidebar entry only
ui/jansa-connected.html          additive — script tag only
```

### 6.8 Constraints

- No business logic in JSX.
- No raw scoring shown by default.
- No filter-first / list-first journey by default.
- No regression to existing UI tabs.

### 6.9 Risk

**MEDIUM** — UI-only addition.

### 6.10 Validation Gate

- Page opens without console errors.
- Buckets display the counts returned by `get_counter_attack_home`.
- Bucket click opens the queue.
- Row click opens the item detail.
- Item detail answers the four required questions.
- Existing pages unchanged.

---

## 7. Phase 6D — Export / Treated / Monthly AI Pack

### 7.1 Objective

Add operator workflow tools so the user can work through the backlog and produce an external evidence pack.

### 7.2 Required Actions

- Export current bucket.
- Export selected rows.
- Mark selected rows treated.
- Auto-mark exported rows as treated.
- Reset treated state for the current run.
- Generate monthly AI evidence pack.

### 7.3 Treated State Rules

```text
localStorage only
run-number scoped
no DB write
no deterministic artifact mutation
```

Suggested key:

```text
counter_attack_treated_<run_number>__<item_id>
```

### 7.4 Exports

```text
output/exports/CounterAttack_<bucket>_<timestamp>.xlsx
output/exports/CounterAttack_AI_Pack_<timestamp>.zip
```

### 7.5 Monthly AI Pack Contents

```text
COUNTER_ATTACK_ITEMS.csv
SUBJECT_RISK_DOSSIERS.csv
ACTOR_ATTACK_DOSSIERS.csv
CHAIN_EVENTS.csv
ONION_LAYERS.csv
ONION_SCORES.csv
CHAIN_REGISTER.csv
top_issues.json
dashboard_summary.json
README_FOR_AI.md
```

`README_FOR_AI.md` must brief the external AI that it is analyzing a MOEX counter-attack pack and that its job is to produce: (1) MOEX recovery report, (2) actor attack dossiers, (3) subject risk dossiers, (4) meeting agenda, (5) draft letter angles.

### 7.6 Touchpoints

```text
ui/jansa/counter_attack.jsx                    additive
ui/jansa/data_bridge.js                        additive
app.py                                         additive — export endpoints
src/reporting/counter_attack_export.py         NEW
output/exports/                                output dir
```

### 7.7 Constraints

- No DB write for treated state.
- No mutation of deterministic pipeline artifacts.
- New run resets treated state automatically (because key is run-scoped).

### 7.8 Risk

**MEDIUM** — additive exports + local UI state.

### 7.9 Validation Gate

- Export creates an XLSX.
- Exported rows match the queue.
- Treated rows visually grey out.
- Reload preserves treated state for the current run.
- A new run resets treated state.
- AI pack zip contains the expected files.
- No DB modified.
- No deterministic artifact modified.

---

## 8. Forbidden Behaviors

The following are forbidden in any Phase 6 sub-phase unless explicitly re-authorized in writing:

```text
Treating INTELLIGENCE_TAGS.csv as the Phase 6 artifact
Building a passive "Intelligence" filter/list page as the default journey
Performing bucket / ownership / deadline / scoring calculations in JSX
Rebuilding the frontend framework
Replacing PyWebView
Replacing the backend bridge
Introducing a new database
Changing run_memory schema
Rewriting chain/onion logic
Rewriting Document Command Center logic
Creating duplicate ownership logic
Modifying unrelated dashboards
Renaming or breaking existing artifact contracts
Deleting existing outputs
Broad refactors
```

---

## 9. Validation Gates Summary

```text
6A passes when COUNTER_ATTACK_ITEMS.csv is deterministic, plausible, and the rest of the pipeline is unchanged.
6B passes when home/queue/item endpoints serve ready data with no UI calc and no API regression.
6C passes when a non-technical user can open the page, pick a bucket, see what to do, and reach DCC.
6D passes when exports work, treated state is local-only and run-scoped, and the AI pack zip is correct.
```

No sub-phase may begin until the previous gate is signed off.

---

## 10. Cowork Execution Workflow

Cowork must follow `READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md`. Specifically, for every Phase 6 sub-phase:

1. Read this master file and the protocol.
2. Return a step-by-step execution plan **before** any code change.
3. Wait for ChatGPT/User approval of that plan.
4. Split the plan into single-result agent tasks.
5. Assign each task the right model (Haiku for read-only inspection, Sonnet for moderate code, Opus for high-risk pipeline reasoning, Claude Code for repo edits).
6. Validate each task’s return package against the Phase 6 plan.
7. Compile a Cowork phase compilation package.
8. Hand back to ChatGPT for review.
9. Update context docs after every validated sub-phase.

Cowork does NOT directly execute "Implement Phase 6" or "Implement Phase 6A" from a single prompt.

---

## 11. Agent Task Split Rules

Each agent task must be small enough that one session produces one verified result. A valid agent task includes:

```text
Objective
Context
Files to read
Files allowed to modify
Files forbidden to touch
Required work
Constraints
Validation method
Required return package
```

Forbidden agent task shapes:

```text
"Build the counter-attack feature."
"Improve the UI."
"Make Phase 6 work."
```

Required agent task shape (example):

```text
Create src/reporting/counter_attack_builder.py that reads existing
DCC/focus/chain-onion artifacts and writes
output/intermediate/COUNTER_ATTACK_ITEMS.csv with the required columns.
Do not modify UI. Do not modify existing ownership logic.
Validate artifact creation, column set, and bucket counts.
```

---

## 12. Final Return Package Format

After every Phase 6 sub-phase, Cowork must return:

```text
# Cowork Phase Compilation — Phase 6X

## Phase Objective
## What Was Planned
## What Was Actually Built
## Files Created
## Files Modified
## Files Read
## Artifacts Produced
## Validation Commands Run
## Validation Results
## Comparison Against Phase Plan
- Requirement 1: PASS / FAIL / PARTIAL
- Requirement 2: PASS / FAIL / PARTIAL
## Risks
## Deviations From Plan
## Escalations Needed
## Recommendation
VALIDATED
or VALIDATED WITH MINOR RISK
or REWORK REQUIRED
or ESCALATION REQUIRED
```

After every coding agent task inside a sub-phase, the agent must return:

```text
1. Files modified
2. Files read
3. Summary of changes
4. Validation commands run
5. Validation results
6. Produced artifacts
7. Risks / compromises
8. Uncertainty
9. Screenshots (if UI)
```

Vague returns ("Done.", "Implemented.", "Should work.") are not accepted.

---

## 13. Authority

If anything in an older Phase 6 document, prompt, or chat history conflicts with this master file, **this master file wins**. Older Phase 6 docs are superseded and must not be used as a basis for implementation.

---

## 14. Phase 6X — ACTION MOEX Data Truth Correction (closed 2026-05-04)

Phase 6X was an emergency mid-Phase-6 sub-phase: it corrected eight bucket-routing
defects in the ACTION MOEX cockpit before Phase 6C (UI page) and Phase 6D (export +
treated) could resume. Authoritative plan and final return package:
`docs/implementation/PHASE_6X_ACTION_MOEX_DATA_TRUTH_CORRECTION.md`.

**Status: VALIDATED — closed.** The freeze on Phase 6C.6 is lifted.

**Scope:** corrected `_resolve_data_date` in `consultant_fiche.py` and
`contractor_quality.py` (no more silent `date.today()`), added per-tier deadline
truth columns (`primary_consultant_days_remaining`,
`secondary_consultant_days_remaining`) to `compute_dcc_tags_bulk`, widened the
chain_metrics merge to expose `moex_wait_days` / `primary_wait_days` /
`secondary_wait_days` to the builder, added a closed/unknown-state filter
upstream of `_assign_bucket`, and replaced `_assign_bucket` itself with the
6-priority operational rule tree documented in
`context/06_EXCEPTIONS_AND_MAPPINGS.md` §L.

**Final R3 artifact (`output/intermediate/COUNTER_ATTACK_ITEMS.csv`, 2026-05-04):**
1524 rows × 28 columns, 0 duplicate `family_key`, 0 duplicate `(numero, indice)`,
0 terminal/unknown chain states. Bucket distribution:

| Bucket | Pre-6X | Post-6X (R3) |
|---|---:|---:|
| FERMER_MAINTENANT | 1001 | 66 |
| CONSULTANT_A_ATTAQUER | 319 | 210 |
| ENTREPRISE_A_RELANCER | 269 | 122 |
| DECISION_MOEX | 209 | 8 |
| MOEX_SHAME_INTERNAL | 71 | 989 |
| SECONDAIRE_EXPIRE | 0 | 129 |
| SUJET_REUNION | 0 | 0 |

**Phase 6C / 6D status:** RESUMABLE. Both must consume the corrected
`COUNTER_ATTACK_ITEMS.csv`. Phase 6B's read API (`get_counter_attack_home`,
`get_counter_attack_queue`, `get_counter_attack_item`) is unchanged in shape
and was smoke-tested green at closure.

**Authorship:** Cowork ran the audits, planning, and steps 6X.B2–6X.F2 in
parallel with the differential audit that rejected the first F2 attempt.
After the `counter_attack_builder.py` truncation incident
(`context/11_TOOLING_HAZARDS.md` 2026-05-04 row), final recovery and R1/R2/R3
reconstruction completed by Codex outside Cowork.

**Manual app smoke (`python app.py`):** not run as part of 6X closure. Required
before declaring the cockpit operational.
