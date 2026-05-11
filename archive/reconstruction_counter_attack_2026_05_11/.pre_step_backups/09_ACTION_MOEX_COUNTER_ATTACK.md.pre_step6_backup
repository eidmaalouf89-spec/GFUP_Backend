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

---

## Phase 6E — Per-bucket Excel export (2026-05-10)

**Files:**
- `src/reporting/counter_attack_export.py` (new, ~330 lines)
- `app.py::Api.export_action_moex_bucket_xlsx` (new method)
- `ui/jansa/data_bridge.js::exportActionMoexBucket` (new bridge wrapper)
- `ui/jansa/counter_attack.jsx` — "Exporter Excel" button on each queue
  panel header; state pair `exportingBucket` / `exportNotice`

**Builder:** `build_action_moex_bucket_xlsx(ctx, bucket: str, dest_dir: Path) -> dict`.
Reads `output/intermediate/COUNTER_ATTACK_ITEMS.csv` filtered by bucket,
joins to `dernier_df` for `titre` + reception date, calls
`_get_latest_responses_for_doc` from `document_command_center.py` for the
reviewer list, reuses CSV `plain_reason` verbatim, appends an empty
`MOEX AVIS` column, atomic temp+rename write.

**Workbook contract — Layout Y, one row per item, French headers, real UTF-8:**

| # | Header | Source / formatting |
|---:|---|---|
| 1 | Numéro | string, `number_format="@"` preserves leading zeros |
| 2 | Indice | string |
| 3 | Émetteur | canonical via `resolve_emetteur_name(emetteur_code)`; fallback CSV `emetteur_name`, then code |
| 4 | Titre | `dernier_df.libelle_du_document`; fallback to `subject_label` minus `"emetteur — "` prefix |
| 5 | Date de réception | `dernier_df.created_at`, ISO |
| 6 | Date contractuelle de réponse | `created_at + 30 days`, ISO (see decision rationale) |
| 7 | Réviseurs | multi-line; tier order PRIMARY → SECONDARY → MOEX → MOEX_SAS → unknown; alphabetic by canonical within tier |
| 8 | Statuts | multi-line; `"En attente"` for empty |
| 9 | Dates de réponse | multi-line, ISO or empty |
| 10 | Commentaires | multi-line, raw text |
| 11 | Pourquoi il est ici | CSV `plain_reason` verbatim |
| 12 | MOEX AVIS | always empty — manual team input |

**Filename:** `ACTION_MOEX_{bucket}_{YYYYMMDD_HHMMSS}.xlsx` under
`output/exports/`. `bucket` is validated against `BUCKET_DISPLAY_ORDER`
(7-bucket enum from `counter_attack_query`). The `Api` returns a rich
envelope `{success, path, filename, rows_exported, bucket, message,
error}`; `success=True` and a header-only workbook are returned for an
empty bucket with `message="Bucket vide..."`.

**Identity-dtype preservation.** `numero` and `indice` are written as
strings with `number_format="@"` so leading zeros never collapse. Mirrors
the Phase 1.5 dashboard drilldown export pattern.

**Atomic write.** Temp file in the same directory, write workbook, fsync,
rename to final path. No partial-file artifacts on failure.

**"Date contractuelle de réponse" decision rationale.** `dernier_df` does
NOT carry a `date_limite` column — per `src/normalize.py:431`, `date_limite`
is per-response and only on `responses_df`. The `_earliest_deadline`
column on `dernier_df` is the synthetic earliest pending-response deadline,
semantically different from "30 days from doc submission". The export
therefore computes `created_at + 30 days` directly, matching the documented
30-day workflow business rule (per the 2026-05-09 SAS routing patch — see
`context/06_EXCEPTIONS_AND_MAPPINGS.md` "SAS routing + P5 removal").

**Residual coupling (see `context/07_OPEN_ITEMS.md`).**
`_get_latest_responses_for_doc` is a private DCC symbol (leading
underscore). Imported directly because protected-zone rules forbid
modifying DCC. If DCC renames or repackages this helper, the export
breaks. Either formalize a public re-export or add a regression test that
imports the symbol.

**Backups:** `backups/step5_20260510_143451/`.

---

## Step 4 attempt — SUJET_REUNION removal cascade (ROLLED BACK)

A Step 4 attempt to introduce a SUJET_REUNION removal cascade in
`_assign_bucket` was rolled back by the user on 2026-05-10 after a
bucket-count regression appeared on artifact rebuild. All three Step 4
files were restored from `backups/step4_20260510_134214/` via `cp` at
14:17 on 2026-05-10. Verified via Read tool: `return "SUJET_REUNION"` is
back at line 384 in `counter_attack_builder.py`; the cascade-only literal
`"L5_MOEX_ARBITRATION_DELAY"` appears only at line 509 inside the original
`_internal_moex_exposure` helper (not in `_assign_bucket`). SUJET_REUNION
references restored across `counter_attack_builder.py` (5),
`counter_attack_query.py` (3), `ui/jansa/counter_attack.jsx` (4).

**Bucket-count delta observed at the moment of rebuild** (845 → 1116 rows
total; user did not rerun upstream chain+onion):

| Bucket | Step 0 baseline | Post-rebuild | Delta |
|---|---:|---:|---:|
| FERMER_MAINTENANT | 336 | 49 | -287 |
| DECISION_MOEX | 22 | 0 | -22 |
| ENTREPRISE_A_RELANCER | 87 | 212 | +125 |
| CONSULTANT_A_ATTAQUER | 153 | 151 | -2 |
| MOEX_SHAME_INTERNAL | 148 | 639 | +491 |
| SECONDAIRE_EXPIRE | 98 | 65 | -33 |
| SUJET_REUNION | 1 | 0 | -1 |
| TOTAL | 845 | 1116 | +271 |

**Diagnostic conclusion (read-only investigation, Read/Grep tools only).**
The cascade alone could NOT have caused the deltas:

- Steps 1–5 of `_assign_bucket` are byte-identical pre vs post Step 4
  (line-by-line diff against `backups/step4_20260510_134214/`).
- `_merge_sources` is byte-identical.
- The cascade gate `escalation_flag AND urgency_label.upper() in
  {"CRITICAL", "HIGH"}` is byte-identical to the pre-edit gate.
- The cascade is correctly placed as the LAST conditional in
  `_assign_bucket`, properly indented, after Steps 1–5.
- 624 of the 639 MOEX_SHAME_INTERNAL rows are LOW+MEDIUM urgency — they
  CANNOT have hit the cascade gate (gate requires CRITICAL/HIGH). They
  were routed by Step 5 / 5b (code unchanged).
- 0 of the 49 FERMER_MAINTENANT rows came from the cascade. All 49 routed
  via Step 5 / 5b.
- 0 of the 212 ENTREPRISE_A_RELANCER rows came from the cascade. All 212
  routed via Step 2 / 3.

**Most plausible explanation** (not proven — open investigation): the
845-row baseline was generated by an earlier code revision than what was
on disk at Step 4 backup time. The repo carries historical reconstruction
copies in `src/reporting/` named
`counter_attack_builder.RECONSTRUCTION_R1_PREWRITE.py`,
`counter_attack_builder.RECONSTRUCTION_R1_VALIDATED.py`, and
`counter_attack_builder.R2C_PREWRITE.py`; `context/11_TOOLING_HAZARDS.md`
2026-05-04 entry documents the Phase 6X.F2-bis R1/R2/R3 reconstruction
done outside Cowork (by Codex) when the file was corrupted. Investigation
needed before any future Action MOEX bucket-routing work.

**Bounded defect that the cascade DID have** (≤15 high-urgency
MOEX_SHAME rows max — NOT the 491 delta): the cascade's `primary_tag`
literal set matched only the U+2014 em-dash variant, while the rest of
the file's tag predicates (`MOEX_FACILE_TAGS`, `MOEX_ARBITRAGE_TAGS`,
`_is_contractor_tag`) accept three byte-variants (hyphen, em-dash,
mojibake). If a future cascade or any other primary_tag matching is
needed, MUST reuse the existing helpers `_is_moex_facile()`,
`_is_moex_arbitrage()`, `_is_contractor_tag()`, `_is_primary_tag()`,
`_is_secondary_tag()` (lines 285-302 of `counter_attack_builder.py`)
rather than inline literal sets — they already handle three byte-variants
per tag.

**Backups available:** `backups/step4_20260510_134214/`. Open items
recorded in `context/07_OPEN_ITEMS.md`.

---

## Phase 9 (`latest_chain_df` filtering + defense-in-depth, 2026-05-11)

- **Builder (Step 4).** `counter_attack_builder.build_counter_attack_items`
  filters merged rows via `ctx.latest_chain_df.(family_key,
  latest_indice)` before bucket assignment. This ensures the Action
  MOEX artifact is built from canonical one-row-per-chain truth, not
  from the polluted `(numero, indice)` cross-product. Legacy fallback
  to the post-merge `latest_indice` column is preserved for legacy
  mode (when `ctx.latest_chain_df` is absent).
- **Export (Step 7 defense-in-depth).**
  `counter_attack_export._resolve_dernier_row` reads
  `reporting.latest_chain_view.latest_enriched_view(ctx)` rather than
  `ctx.dernier_df` directly. The titre / reception-date join is now
  scoped to canonical latest-chain rows.
- **Stable bucket counts (post-Step-4 rebuild, current data):**
  - FERMER_MAINTENANT: 687
  - DECISION_MOEX / SECONDAIRE_EXPIRE / etc. (composite second slot): 98
  - ENTREPRISE_A_RELANCER: 107
  - MOEX_SHAME_INTERNAL: 146
  - **Total: 1,038 rows.**
- The pre-Phase-9 1,524-row total (Phase 6X.F2-bis R3 validation) and
  the rolled-back 1,116-row drift (`OS-2026-05-10-01` in
  `context/07_OPEN_ITEMS.md`) both reflect different code/data
  snapshots and are not directly comparable to the post-Phase-9 1,038
  baseline.
- The `_load_dormant_ref_from_artifact` rehabilitation (Step 5b) makes
  `ENTREPRISE_A_RELANCER` (107 rows) the canonical source of "dormant
  REF" for the contractor quality fiche. See
  `context/06_EXCEPTIONS_AND_MAPPINGS.md` §F-2.

References: `README.md §Phase 9`,
`reports/STEP1_DERNIER_DF_INVENTORY.md`,
[[05_REPORTING_AND_UI_ADAPTERS]].
