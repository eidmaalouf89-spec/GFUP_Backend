# Phase 6D — Team AI Audit Pack (PLAN + STEP 1 RECON)

**Location:** `docs/implementation/PHASE_6D_TEAM_AI_AUDIT_PACK.md`
**Status:** PLANNING — Step 1 (recon) complete. No code written. Awaiting approval to dispatch Step 2.
**Master plan:** `docs/implementation/PHASE_6_COUNTER_ATTACK_MASTER.md`
**Protocol:** `docs/implementation/READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md`
**Predecessors (all VALIDATED):**

- `docs/implementation/PHASE_6A_ACTION_KERNEL_EXECUTION_PLAN.md`
- `docs/implementation/PHASE_6B_READ_API.md`
- `docs/implementation/PHASE_6C_COUNTER_ATTACK_UI.md`
- `docs/implementation/PHASE_6X_ACTION_MOEX_DATA_TRUTH_CORRECTION.md`

**Risk:** MEDIUM. Additive only. Export-only. No AI API call. No DB write. No deterministic-artifact mutation.

> **Tooling note (read before any investigation):** Use the `Read` tool — never bash `wc`/`grep`/`cat`/`head`/`tail` — to verify file content, size, or function presence in Windows-mounted source files. The Linux sandbox mount caches a stale view that has falsely reported missing methods and truncated files in past sessions. If a bash inspection contradicts the Read tool, the Read tool wins. Do not raise "repo is broken" alarms from bash-only evidence. See `context/11_TOOLING_HAZARDS.md`.

---

## 1. Operational Objective

Add **one button** in the JANSA Reports tab — `Générer Pack Audit IA` — that produces a deterministic ZIP under `output/exports/JANSA_AI_AUDIT_PACK_<YYYYMMDD>_<HHMMSS>.zip`. The ZIP bundles existing JANSA evidence (Counter-Attack items, Chain+Onion CSVs, chain timeline attribution, a curated Flat-GED extract, optional dossiers) plus five French-first prompt files keyed to the six accepted attack angles, plus a `README_FOR_AI.md` that frames the pack and forbids invention.

JANSA does not call any AI. The team uploads the ZIP wherever they want.

---

## 2. Six Accepted AI Attack Angles

Per phase brief §4 — these are the only behavioral patterns the prompts target:

1. **CROSS_NUMERO_RESUBMISSION** — a document refused under one numéro reappears under another.
2. **SAS_REF_DISEASE** — a company has many SAS REF, especially on indice A or repeated after correction.
3. **CONSULTANT_POSITION_SHIFT** — a consultant changes position between indices (VAO then REF, etc.).
4. **CONSULTANT_COMMENT_INFLATION** — a consultant adds many new comments later, suggesting a weak first review.
5. **LATE_SECONDARY_DISRUPTS_VISA** — a secondary consultant answers after MOEX visa, especially with REF / SUS / contradictory advice.
6. **CONTRACTOR_FAKE_CORRECTION** — a contractor resubmits but the same blocking comments repeat.

AI output is advisory. It must not change deterministic JANSA buckets.

---

## 3. Corrections applied to the prior planning round (2026-05-05)

Five corrections were issued by the project owner before Step 1 was dispatched. They are now binding for every subsequent step:

1. **No dependency on `ctx.run_number` for ZIP naming.** The ZIP filename is timestamp-only: `JANSA_AI_AUDIT_PACK_<YYYYMMDD>_<HHMMSS>.zip`. `data_loader.py` and `RunContext` must NOT be modified for this phase.
2. **Single payload convention everywhere — `success`, never `ok`.** Every layer (Python module, `Api`, bridge, JSX) returns the same shape:

   Success:
   ```json
   {
     "success": true,
     "path": "...",
     "filename": "...",
     "included_files": [],
     "missing_optional_files": [],
     "error": null
   }
   ```
   Failure:
   ```json
   {
     "success": false,
     "path": null,
     "filename": null,
     "included_files": [],
     "missing_optional_files": [],
     "error": "..."
   }
   ```
3. **UI opens Explorer only if `success === true` and `path` is truthy.** No optimistic open. No fallback path.
4. **Prompt files are French-first.** A short English note inside `README_FOR_AI.md` is acceptable; the five operational prompts under `PROMPTS/` are French.
5. **No row added to `context/artifact_inventory.csv`** unless the existing schema clearly supports on-demand export ZIPs. Prefer updating only `context/05_OUTPUT_ARTIFACTS.md` and `context/03_UI_FEED_MAP.md`. The on-demand artifact is documented in markdown context, not in the run-numbered inventory CSV.

---

## 4. Non-negotiable Constraints

- No AI API call.
- No AI model integration.
- No DB write.
- No `run_memory` schema change.
- No `report_memory` change.
- No pipeline mutation.
- No deterministic artifact mutation.
- No bucket recalculation.
- No business logic in React.
- No raw GED-first logic if composed artifacts already contain the needed data.
- Preserve leading zeros in identity columns (`numero`, `indice`, `doc_id`, `family_key`).
- Missing **optional** files do not fail ZIP generation.
- Missing **required** files return a clean error payload — no app crash.
- The forbidden phrase `"Honte MOEX"` must not appear in any artifact, code, or documentation produced by this phase.

---

## 5. File Impact Map

### READ (read-only)

```
docs/implementation/READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md
docs/implementation/PHASE_6_COUNTER_ATTACK_MASTER.md
docs/implementation/PHASE_6A_ACTION_KERNEL_EXECUTION_PLAN.md
docs/implementation/PHASE_6B_READ_API.md
docs/implementation/PHASE_6C_COUNTER_ATTACK_UI.md
docs/implementation/PHASE_6X_ACTION_MOEX_DATA_TRUTH_CORRECTION.md
context/guardrail.txt
context/02_DATA_FLOW.md
context/03_UI_FEED_MAP.md
context/05_OUTPUT_ARTIFACTS.md
context/07_OPEN_ITEMS.md
context/10_VALIDATION_COMMANDS.md
context/11_TOOLING_HAZARDS.md
README.md

app.py                                           (export_team_version, get_counter_attack_*, _sanitize_for_json pattern)
ui/jansa/shell.jsx                               (ReportsPage section only — lines 778–867)
ui/jansa/data_bridge.js                          (loadCounterAttack* pattern — lines 230–320)
src/reporting/counter_attack_query.py            (artifact-path + dtype contract)
src/reporting/data_loader.py                     (RunContext fields ONLY — no edits)

# Headers + small samples only — never full bulk read in sandbox (H-5):
output/intermediate/COUNTER_ATTACK_ITEMS.csv
output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv
output/chain_onion/CHAIN_EVENTS.csv
output/chain_onion/CHAIN_REGISTER.csv
output/chain_onion/CHAIN_VERSIONS.csv
output/chain_onion/CHAIN_NARRATIVES.csv
output/chain_onion/ONION_LAYERS.csv
output/chain_onion/ONION_SCORES.csv
output/chain_onion/dashboard_summary.json
output/chain_onion/top_issues.json
```

### MODIFY (additive only)

```
ui/jansa/shell.jsx              (+ one card in ReportsPage; replaces "Autres rapports" placeholder at lines 853–864)
ui/jansa/data_bridge.js         (+ one bridge method: generateAiAuditPack)
app.py                          (+ one Api method: generate_counter_attack_ai_audit_pack)
context/05_OUTPUT_ARTIFACTS.md  (+ row for JANSA_AI_AUDIT_PACK_*.zip)
context/03_UI_FEED_MAP.md       (+ ReportsPage AI Pack action mapping)
```

### CREATE

```
src/reporting/counter_attack_ai_pack.py             (NEW)
docs/implementation/PHASE_6D_TEAM_AI_AUDIT_PACK.md  (THIS FILE — accumulates per-step records)
output/exports/                                     (created by code on first run; mkdir(parents=True, exist_ok=True))
```

### DO NOT TOUCH

```
src/flat_ged/**
src/chain_onion/**
src/run_memory.py
src/report_memory.py
src/effective_responses.py
src/reporting/counter_attack_builder.py
src/reporting/document_command_center.py
src/reporting/focus_ownership.py
src/reporting/chain_timeline_attribution.py
src/reporting/aggregator.py
src/reporting/consultant_fiche.py
src/reporting/contractor_fiche.py
src/reporting/contractor_quality.py
src/reporting/focus_filter.py
src/reporting/data_loader.py        (read-only consumer; no edits — confirmed by Correction #1)
src/reporting/counter_attack_query.py (read-only consumer)
src/pipeline/**
data/run_memory.db
data/report_memory.db
output/intermediate/COUNTER_ATTACK_ITEMS.csv
output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.{csv,json}
output/chain_onion/**
ui/jansa/counter_attack.jsx          (Phase 6C cockpit — must not be modified by 6D)
ui/jansa/overview.jsx, consultants.jsx, contractors.jsx, fiche_*.jsx, runs.jsx, executer.jsx, document_panel.jsx
ui/jansa-connected.html
context/artifact_inventory.csv       (per Correction #5 — not updated by this phase)
README.md                            (per 6C precedent — not updated unless user explicitly asks)
```

---

## 6. Step-by-step Execution Plan

Eight steps. Each produces one verified result. Cowork dispatches one at a time, validates each, then moves on.

| Step | Title | Risk | Agent |
|---|---|---|---|
| 1 | Recon: artifact contracts + ReportsPage anchor + run-context fields + exports dir | Low | Sonnet (recon) |
| 2 | Backend pack-generator design (no code) | Low | Opus (design) |
| 3 | Implement `src/reporting/counter_attack_ai_pack.py` | Med | Claude Code |
| 4 | Add `app.py` Api method | Low | Claude Code |
| 5 | Add `data_bridge.js` bridge method | Low | Claude Code |
| 6 | Add the button in `ReportsPage` (shell.jsx) | Low | Claude Code + Windows-shell smoke |
| 7 | Documentation + context updates | Low | Sonnet (doc) |
| 8 | Cowork final compilation + verification against §7.9 of the master plan | — | Cowork (Opus) |

Per-step contract (objective, files, validation, return package) is documented inline in the prior planning response. The corrections in §3 of this file override any conflicting line in the prior response.

---

## 7. Step 1 Recon — Results (executed 2026-05-05)

**Objective.** Confirm artifact column contracts, the ReportsPage insertion anchor, the run-context fields used by the generator, and the `output/exports/` directory convention. No code, no edits.

### 7.1 Artifact column maps (header rows, Read tool only)

**`output/intermediate/COUNTER_ATTACK_ITEMS.csv`** — 28 columns:

```
item_id, numero, indice, family_key, subject_label, emetteur_code, emetteur_name,
primary_actor, actor_to_call, action_bucket, action_label, plain_reason,
recommended_action, risk_level, evidence_summary, days_open, days_late,
current_state, normalized_score_100, is_internal_moex_exposure,
is_external_attackable, chain_observations_summary, chain_observations_full,
chain_observations_refs, consultant_reports_summary, consultant_reports_full,
consultant_reports_refs, consultant_reports_available
```

Identity columns (string-typed in 6B): `item_id`, `numero`, `indice`, `family_key`, `emetteur_code`. Sample row 2 confirms leading zero on `numero=049215`. Pack generator must read with the same dtype lock as `counter_attack_query._artifact_path`.

**`output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv`** — 14 columns:

```
family_key, numero, indice, version_key, phase, start, end, days_actual,
days_expected, delay_days, is_open, attributed_to_actor, attributed_to_tier,
attributed_days
```

**`output/chain_onion/CHAIN_REGISTER.csv`** — 23 columns:

```
family_key, numero, total_versions, total_rows_ops, first_submission_date,
latest_submission_date, latest_indice, latest_version_key, total_blocking_versions,
total_versions_requiring_cycle, total_completed_rows, current_blocking_actor_count,
waiting_primary_flag, waiting_secondary_flag, has_debug_trace, has_effective_rows,
current_state, portfolio_bucket, stale_days, last_real_activity_date,
operational_relevance_score, classifier_reason, classifier_priority_hit
```

**`output/chain_onion/CHAIN_VERSIONS.csv`** — 14 columns:

```
family_key, version_key, numero, indice, row_count_ops, first_submission_date,
latest_submission_date, latest_response_date, has_blocking_rows,
blocking_actor_count, requires_new_cycle_flag, completed_row_count,
source_row_count, version_sort_order
```

**`output/chain_onion/CHAIN_EVENTS.csv`** — 18 columns:

```
family_key, version_key, instance_key, event_seq, event_date, source,
source_priority, actor, actor_type, step_type, status, is_blocking, is_completed,
requires_new_cycle, delay_contribution_days, issue_signal, raw_reference, notes
```

**`output/chain_onion/CHAIN_NARRATIVES.csv`** — 15 columns:

```
family_key, numero, current_state, portfolio_bucket, executive_summary,
primary_driver_text, secondary_driver_text, operational_note, recommended_focus,
urgency_label, confidence_label, normalized_score_100, action_priority_rank,
engine_version, generated_at
```

**`output/chain_onion/ONION_LAYERS.csv`** — 18 columns:

```
family_key, numero, layer_code, layer_name, layer_rank, issue_type, severity_raw,
confidence_raw, evidence_count, evidence_event_refs, trigger_metrics,
first_trigger_date, latest_trigger_date, current_state, portfolio_bucket,
pressure_index, engine_version, generated_at
```

**`output/chain_onion/ONION_SCORES.csv`** — 22 columns:

```
family_key, numero, current_state, portfolio_bucket, total_onion_score,
normalized_score_100, action_priority_rank, top_layer_code, top_layer_name,
top_layer_score, contractor_impact_score, sas_impact_score,
consultant_primary_impact_score, consultant_secondary_impact_score,
moex_impact_score, contradiction_impact_score, blended_confidence,
evidence_layers_count, escalation_flag, escalation_reason, engine_version,
generated_at
```

**`output/chain_onion/dashboard_summary.json`** — 11 keys, all primitives:

```
total_chains, live_chains, legacy_chains, archived_chains, dormant_ghost_ratio,
avg_pressure_live, escalated_chain_count, top_theme_by_impact, generated_at,
engine_version
```

**`output/chain_onion/top_issues.json`** — 14 fields per record (per Phase 4 contract):

```
family_key, numero, action_priority_rank, normalized_score_100, urgency_label,
portfolio_bucket, current_state, executive_summary, primary_driver_text,
recommended_focus, escalation_flag, emetteur_code, emetteur_name, titre
```

### 7.2 Required vs optional pack contents (frozen for Step 2)

Per phase brief §5, with the corrected mapping based on what actually exists today:

**Required (pack fails if missing):**

| Pack path | Source on disk |
|---|---|
| `DATA/01_COUNTER_ATTACK_ITEMS.csv` | `output/intermediate/COUNTER_ATTACK_ITEMS.csv` |
| `DATA/02_CHAIN_EVENTS.csv` | `output/chain_onion/CHAIN_EVENTS.csv` |
| `DATA/03_CHAIN_REGISTER.csv` | `output/chain_onion/CHAIN_REGISTER.csv` |
| `DATA/04_CHAIN_VERSIONS.csv` | `output/chain_onion/CHAIN_VERSIONS.csv` |
| `DATA/05_CHAIN_NARRATIVES.csv` | `output/chain_onion/CHAIN_NARRATIVES.csv` |
| `DATA/06_ONION_LAYERS.csv` | `output/chain_onion/ONION_LAYERS.csv` |
| `DATA/07_ONION_SCORES.csv` | `output/chain_onion/ONION_SCORES.csv` |
| `DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv` | `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv` |
| `DATA/09_FLAT_GED_EXTRACT.csv` | Built by the generator from `ctx.docs_df` + `ctx.responses_df` |
| `README_FOR_AI.md` | Generated string |
| `PROMPTS/01_GENERAL_MOEX_AUDIT.md` | Generated string |
| `PROMPTS/02_SIX_ATTACK_ANGLES.md` | Generated string |
| `PROMPTS/03_CONTRACTOR_BEHAVIOR_AUDIT.md` | Generated string |
| `PROMPTS/04_CONSULTANT_BEHAVIOR_AUDIT.md` | Generated string |
| `PROMPTS/05_MEETING_AGENDA_GENERATOR.md` | Generated string |

**Optional (recorded into `missing_optional_files` if absent — never fail):**

| Pack path | Source on disk |
|---|---|
| `DATA/SUBJECT_RISK_DOSSIERS.csv` | `output/intermediate/SUBJECT_RISK_DOSSIERS.csv` |
| `DATA/ACTOR_ATTACK_DOSSIERS.csv` | `output/intermediate/ACTOR_ATTACK_DOSSIERS.csv` |
| `DATA/dashboard_summary.json` | `output/chain_onion/dashboard_summary.json` |
| `DATA/top_issues.json` | `output/chain_onion/top_issues.json` |

> **Note for Step 2 design:** the brief lists `dashboard_summary.json` and `top_issues.json` as optional in §5, even though both exist today. Pack treats them as optional per the brief — they are included when present, recorded as missing when not.

### 7.3 ReportsPage insertion anchor (confirmed)

The Reports tab is **`ReportsPage()` defined inline at the bottom of `ui/jansa/shell.jsx`**, lines 778–867. There is no `ui/jansa/reports.jsx` file (the prior phase brief contained a path that does not exist in this repo).

The disabled placeholder card the new button replaces is at **lines 853–864**:

- Container `<div>` with `opacity: 0.5` styling.
- Title text: `Autres rapports`.
- Subtitle text: `Fiches consultants, bilans entreprises — à venir.`

The active sibling pattern to mirror is the **`Tableau de Suivi VISA`** card at lines 815–851:

- State pair `(exporting, exportResult)` driven by `useState`.
- Async handler `handleExport` calling `window.jansaBridge.api.export_team_version()`.
- On success → `window.jansaBridge.api.open_file_in_explorer(res.path)`.
- Visual feedback inside the button label: `Export en cours…` → `✓ Exporté` / `✗ Erreur` → reset after 4 s.

The Phase 6D button must mirror this pattern verbatim, substituting:

- State pair `(aiPacking, aiPackResult)`.
- Handler `handleAiPack` calling `window.jansaBridge.generateAiAuditPack()` (note: through the bridge, not directly through `bridge.api`, to keep the failure-mode envelope consistent with Phase 6B's bridge-side `try/catch`).
- On success **only when `success === true && path`** (Correction #3) → call `window.jansaBridge.api.open_file_in_explorer(res.path)`.
- Button label: `Générer Pack Audit IA`.
- Subtitle: `Prépare un dossier ZIP avec les données JANSA + prompts IA pour analyse externe.`

### 7.4 Run-context fields (no `data_loader` edit needed)

`src/reporting/data_loader.py` already exposes (verified by Read of lines 36–53):

- `RunContext.run_number: int` — present.
- `RunContext.data_date: Optional[date]` — present.
- `RunContext.docs_df: Optional[pd.DataFrame]` — present.
- `RunContext.responses_df: Optional[pd.DataFrame]` — present.

Per Correction #1, the ZIP filename does **not** use `run_number`. Filename is timestamp-only:

```
JANSA_AI_AUDIT_PACK_<YYYYMMDD>_<HHMMSS>.zip
```

`data_date` is also not used in the filename (it would create date confusion against the actual generation timestamp). The pack generator's only `RunContext` consumer is the Flat-GED extract step (Step 2 / Step 3) which reads `ctx.docs_df` and `ctx.responses_df`. **No edit to `data_loader.py` or `RunContext`.**

### 7.5 `output/exports/` directory convention

Confirmed via Read of `app.py`:

- `OUTPUT_DIR = BASE_DIR / "output"` (line 33).
- Existing precedent for `output/exports/` — `Api.export_run_bundle` writes to `OUTPUT_DIR / "exports"` (line 377) for run-bundle ZIPs. Pattern: `mkdir(parents=True, exist_ok=True)` then write.

The directory does not exist on disk today (`Glob output/exports` returned no entries). The pack generator must create it on first call exactly the way `export_run_bundle` does. No new dependency, no new convention.

### 7.6 Open design questions surfaced for Step 2

Step 1 is recon only; the following are explicitly deferred to the Step 2 design doc, NOT decided here:

1. **`09_FLAT_GED_EXTRACT.csv` shape — single joined table or split?** The brief lists doc-level columns (`numero`, `indice`, `doc_id`, `emetteur`, `titre`, `lot`) AND response-level columns (`approver_canonical`, `status_clean`, `response_date`, `response_comment`, `date_limite`) in a single CSV. `docs_df` and `responses_df` are two separate DataFrames keyed on `doc_id`. Step 2 must decide: (a) one CSV that left-joins responses onto docs (one row per `(doc_id, response)`, possibly multi-row per doc), or (b) two CSVs (`09a_FLAT_GED_DOCS.csv` + `09b_FLAT_GED_RESPONSES.csv`). The brief reads as (a). The Step 2 design must commit explicitly and justify.
2. **`visa_global` and `effective_source` source.** Neither is a `responses_df` column today. `visa_global` is computed by `WorkflowEngine`; `effective_source` is on `effective_responses_df`. Step 2 must decide whether the pack pulls them (requires a careful read of the right composed layer) or omits them. Per the project guardrail, the highest-level composed layer wins — likely `ctx.effective_responses_df` if present.
3. **Determinism of the Flat-GED extract under non-deterministic DataFrame ordering.** Step 2 must specify a stable sort key (suggested: `(numero, indice, doc_id, response_seq)` ascending) so that the same ctx produces the same CSV bytes.
4. **`README_FOR_AI.md` structure.** French-first per Correction #4; Step 2 must draft the full text and the short English subsection.
5. **Empty `included_files` / `missing_optional_files` arrays vs `null`.** Per Correction #2 the failure shape uses `[]` (empty arrays) — Step 2 design must replicate.

These are flagged so Step 2 cannot silently invent answers.

### 7.7 Files Read in Step 1

```
docs/implementation/READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md
docs/implementation/PHASE_6_COUNTER_ATTACK_MASTER.md
docs/implementation/PHASE_6B_READ_API.md
docs/implementation/PHASE_6C_COUNTER_ATTACK_UI.md
context/guardrail.txt
context/02_DATA_FLOW.md (front section)
context/05_OUTPUT_ARTIFACTS.md (full)
context/10_VALIDATION_COMMANDS.md (full)
context/11_TOOLING_HAZARDS.md (full)
context/03_UI_FEED_MAP.md (front section)
ui/jansa/shell.jsx (lines 778–867 — ReportsPage)
ui/jansa/data_bridge.js (lines 230–320 — Counter-Attack methods)
app.py (lines 33, 374–377, 630–671, 1196–1252 — exports + Counter-Attack methods)
src/reporting/counter_attack_query.py (lines 1–80 — header + bucket maps)
src/reporting/data_loader.py (RunContext field grep, lines 28–53 confirmed)
src/normalize.py (normalize_docs / normalize_responses signatures + key columns produced)
output/intermediate/COUNTER_ATTACK_ITEMS.csv (header + 1 row)
output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv (header + 1 row)
output/chain_onion/CHAIN_EVENTS.csv (header + 1 row)
output/chain_onion/CHAIN_REGISTER.csv (header + 1 row)
output/chain_onion/CHAIN_VERSIONS.csv (header + 1 row)
output/chain_onion/CHAIN_NARRATIVES.csv (header + 1 row)
output/chain_onion/ONION_LAYERS.csv (header + 1 row)
output/chain_onion/ONION_SCORES.csv (header + 1 row)
output/chain_onion/dashboard_summary.json (full — 11 keys)
output/chain_onion/top_issues.json (first 25 lines — confirmed 14-field record shape)
scripts/build_counter_attack.py (full — pattern reference for any future CLI runner)
```

### 7.8 Files Modified in Step 1

None. Step 1 was recon only. The only file created is **this file** (`PHASE_6D_TEAM_AI_AUDIT_PACK.md`), per the project owner's instruction.

### 7.9 Validation of Step 1

- All artifact headers were read with the Read tool, never via bash (H-1 discipline).
- ReportsPage anchor confirmed by direct Read of `shell.jsx` lines 778–867; the `Autres rapports` placeholder is at 853–864 as expected.
- `RunContext.run_number` and `RunContext.data_date` confirmed present without modifying `data_loader.py`. Correction #1 holds: timestamp-only ZIP naming.
- `output/exports/` convention confirmed via `app.py` `Api.export_run_bundle` precedent.
- Forbidden-file set unchanged. No file in §5 DO NOT TOUCH was opened for write.

### 7.10 Recommendation

**Step 1 PASS.** The plan in §3–§6 is now sufficiently anchored to dispatch Step 2 (backend pack-generator design, no code) on approval. The five open design questions in §7.6 are the only things that must be resolved before any code is written in Step 3.

---

## 8. What happens next

Step 2 will produce a code-free design doc covering: function signature, ZIP layout, exact `09_FLAT_GED_EXTRACT.csv` columns and join logic, deterministic sort key, full draft text of `README_FOR_AI.md` and the five `PROMPTS/*.md` files, error-payload shape (matching Correction #2), and answers to the §7.6 open questions.

Cowork will dispatch Step 2 only after the project owner approves Step 1 and the corrected plan in this file.

---

## 9. Change log

| Date | Step | Note |
|---|---|---|
| 2026-05-05 | Plan v1 | Initial 8-step plan delivered in chat (no file). |
| 2026-05-05 | Plan v1 → v2 | Five corrections applied (timestamp-only filename; `success` payload contract; UI explorer guard; French-first prompts; no `artifact_inventory.csv` row). |
| 2026-05-05 | Step 1 | Recon executed. Artifact headers, ReportsPage anchor, RunContext fields, and `output/exports/` convention all confirmed. No code written. Five design questions queued for Step 2. |
| 2026-05-05 | Step 2 | Backend pack-generator design landed (§10). All five §7.6 open questions resolved: 09 = single joined CSV; visa_global + effective_source both included via `ctx.flat_ged_doc_meta` and `ctx.responses_df`; sort key `(numero, indice, doc_id, approver_canonical)`; `README_FOR_AI.md` + five PROMPTS drafted French-first; failure payload arrays are `[]`. No code written. |
| 2026-05-05 | Step 3 | Implementation of `src/reporting/counter_attack_ai_pack.py` (630 lines). Public entrypoint `build_ai_audit_pack`, 15 required + 4 optional pack paths, byte-for-byte copy of 8 source CSVs, in-memory build of `DATA/09_FLAT_GED_EXTRACT.csv` with mergesort by `(numero, indice, doc_id, approver_canonical)`, French-first README + 5 PROMPTS strings, §10.8 payload contract honoured on every code path. All sandbox validations passed: compile, import, forbidden-phrase, ctx=None failure, success-path determinism with cross-run sha256 match. |
| 2026-05-05 | Step 4 | `Api.generate_counter_attack_ai_audit_pack` added to `app.py` (lines 1255–1287). One module-level import at line 39. Run-context loader pattern mirrored from `Api.get_dashboard_data` (not `Api.export_run_bundle` — the latter takes `run_number` directly and does not load a `RunContext`). Note: the Step 4 brief incorrectly named `Api.export_run_bundle` as the precedent; the implementing agent correctly fell back to the dominant `load_run_context(BASE_DIR)` pattern. |
| 2026-05-05 | Step 5 | `generateAiAuditPack` bridge method added to `ui/jansa/data_bridge.js` (lines 329–360). ES5-style to match the file's existing convention. Defensive guard tightened beyond sibling pattern (typeof-check on the API method) to guarantee the §10.8 envelope on every code path. |
| 2026-05-05 | Step 6 | `Générer Pack Audit IA` button added to `ReportsPage` in `ui/jansa/shell.jsx`. Replaced the disabled "Autres rapports" placeholder (pre-edit lines 853–864) with an active card (post-edit lines 877–910). State pairs `(aiPacking, aiPackResult)` added at lines 782–783. `handleAiPack` at lines 807–827. Explorer-open guard at line 818 enforces Correction #3 verbatim: `result && result.success === true && result.path`. |
| 2026-05-05 | Step 7 | Documentation + context updates — `context/05_OUTPUT_ARTIFACTS.md` and `context/03_UI_FEED_MAP.md` updated; `context/artifact_inventory.csv` deliberately NOT modified per Correction #5; `README.md` deliberately NOT modified per Phase 6C precedent. End-to-end smoke test confirmed by user: pack generated successfully and ingested by external AI on first attempt. |

---

## 10. Step 2 — Backend Pack-Generator Design

This section is design-only. No `.py` or `.jsx` file was created or modified by Step 2. The corrections in §3 and the recon findings in §7 are binding here.

### 10.1 Function signature and module docstring

```python
"""Phase 6D — JANSA AI Audit Pack generator (design — Step 2).

Builds a deterministic ZIP under output/exports/ that bundles JANSA evidence
artifacts (Counter-Attack items, Chain+Onion CSVs, chain timeline attribution,
Flat-GED extract, optional dossiers) plus a French-first README and five
French-first PROMPTS for an external AI audit.

Public entrypoint:
    build_ai_audit_pack(ctx: RunContext, output_dir: Path) -> dict

Contract:
- No AI API call. No DB write. No deterministic-artifact mutation.
- Identity columns (numero, indice, doc_id, family_key, emetteur_code,
  item_id) are read and written as strings, leading zeros preserved.
- Missing required source files -> clean error payload, no exception.
- Missing optional source files -> recorded in missing_optional_files,
  pack still ships.
- Same RunContext + same on-disk artifacts -> byte-identical pack
  contents (modulo the timestamp embedded in the ZIP filename).
- The phrase forbidden by §4 of this phase plan must not appear in any generated string.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

# ── Module-level constants ─────────────────────────────────────
PACK_FILENAME_TEMPLATE: str = "JANSA_AI_AUDIT_PACK_{ts}.zip"      # ts = YYYYMMDD_HHMMSS

# Mapping: pack-relative path -> on-disk source path (relative to repo root).
# 09_FLAT_GED_EXTRACT.csv is built in-memory; sentinel "<BUILT>".
REQUIRED_FILES: Dict[str, str] = {
    "DATA/01_COUNTER_ATTACK_ITEMS.csv":         "output/intermediate/COUNTER_ATTACK_ITEMS.csv",
    "DATA/02_CHAIN_EVENTS.csv":                 "output/chain_onion/CHAIN_EVENTS.csv",
    "DATA/03_CHAIN_REGISTER.csv":               "output/chain_onion/CHAIN_REGISTER.csv",
    "DATA/04_CHAIN_VERSIONS.csv":               "output/chain_onion/CHAIN_VERSIONS.csv",
    "DATA/05_CHAIN_NARRATIVES.csv":             "output/chain_onion/CHAIN_NARRATIVES.csv",
    "DATA/06_ONION_LAYERS.csv":                 "output/chain_onion/ONION_LAYERS.csv",
    "DATA/07_ONION_SCORES.csv":                 "output/chain_onion/ONION_SCORES.csv",
    "DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv":   "output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv",
    "DATA/09_FLAT_GED_EXTRACT.csv":             "<BUILT>",
    # Generated strings:
    "README_FOR_AI.md":                         "<GENERATED>",
    "PROMPTS/01_GENERAL_MOEX_AUDIT.md":         "<GENERATED>",
    "PROMPTS/02_SIX_ATTACK_ANGLES.md":          "<GENERATED>",
    "PROMPTS/03_CONTRACTOR_BEHAVIOR_AUDIT.md":  "<GENERATED>",
    "PROMPTS/04_CONSULTANT_BEHAVIOR_AUDIT.md":  "<GENERATED>",
    "PROMPTS/05_MEETING_AGENDA_GENERATOR.md":   "<GENERATED>",
}
OPTIONAL_FILES: Dict[str, str] = {
    "DATA/SUBJECT_RISK_DOSSIERS.csv":           "output/intermediate/SUBJECT_RISK_DOSSIERS.csv",
    "DATA/ACTOR_ATTACK_DOSSIERS.csv":           "output/intermediate/ACTOR_ATTACK_DOSSIERS.csv",
    "DATA/dashboard_summary.json":              "output/chain_onion/dashboard_summary.json",
    "DATA/top_issues.json":                     "output/chain_onion/top_issues.json",
}

# Identity-column dtype lock (mirrors counter_attack_query._IDENTITY_DTYPES,
# extended with the doc-side identity columns that 09_FLAT_GED_EXTRACT carries).
_IDENTITY_DTYPES: Dict[str, str] = {
    "numero":          "string",
    "indice":          "string",
    "family_key":      "string",
    "doc_id":          "string",
    "emetteur_code":   "string",
    "item_id":         "string",
    "version_key":     "string",
}

# ── Public entrypoint (signature only) ──────────────────────────
def build_ai_audit_pack(ctx: "RunContext", output_dir: Path) -> dict:
    """Build the pack ZIP and return the success/failure payload.

    Reads:
      - ctx.docs_df, ctx.responses_df              (Flat-GED extract)
      - ctx.flat_ged_doc_meta                      (visa_global override)
      - on-disk required + optional source files
    Writes:
      - output_dir / PACK_FILENAME_TEMPLATE.format(ts=...)
    Returns:
      - dict matching the §10.8 success or failure shape (NEVER raises).
    """

# ── Internal helpers (signatures only — no body) ────────────────
def _validate_inputs(ctx: "RunContext", output_dir: Path) -> Optional[str]: ...
    # Returns None on success; an error string on failure (e.g. "ctx is None",
    # "missing ctx.docs_df", "output/exports/ not writable").

def _check_required_sources_on_disk() -> List[str]: ...
    # Returns the list of pack-relative REQUIRED paths whose on-disk source is
    # missing (excluding "<BUILT>" and "<GENERATED>"). Empty list = OK.

def _check_optional_sources_on_disk() -> List[str]: ...
    # Returns pack-relative OPTIONAL paths whose on-disk source is missing.

def _build_flat_ged_extract(ctx: "RunContext") -> pd.DataFrame: ...
    # Reads ctx.docs_df + ctx.responses_df (in memory), produces the joined
    # DataFrame for 09_FLAT_GED_EXTRACT.csv per §10.3. Identity columns cast
    # to string. No disk I/O. Stable sort per §10.5.

def _render_readme_for_ai(ctx: "RunContext") -> str: ...
    # Returns the full text of README_FOR_AI.md per §10.6.

def _render_prompt_general_moex_audit() -> str: ...        # PROMPTS/01 (§10.7)
def _render_prompt_six_attack_angles() -> str: ...         # PROMPTS/02
def _render_prompt_contractor_behavior_audit() -> str: ... # PROMPTS/03
def _render_prompt_consultant_behavior_audit() -> str: ... # PROMPTS/04
def _render_prompt_meeting_agenda_generator() -> str: ...  # PROMPTS/05

def _copy_required_csv(src_disk_path: Path, zf, pack_path: str) -> None: ...
    # Copies the CSV byte-for-byte into the open ZipFile. No reparse, no
    # dtype coercion, no row reordering. The source artifact is already
    # deterministic (Phase 6A/6X for COUNTER_ATTACK_ITEMS; chain_onion
    # exporter for the seven chain_onion/intermediate CSVs).

def _write_built_csv(df: pd.DataFrame, zf, pack_path: str) -> None: ...
    # Serializes the in-memory DataFrame to CSV with quoting that preserves
    # leading zeros on identity columns; writes into the ZipFile.

def _write_generated_text(text: str, zf, pack_path: str) -> None: ...
    # UTF-8 encoded, LF line endings, no BOM.

def _success_payload(zip_path: Path, included: List[str], missing_opt: List[str]) -> dict: ...
def _failure_payload(error_msg: str) -> dict: ...
```

### 10.2 Final ZIP layout

```
JANSA_AI_AUDIT_PACK_<YYYYMMDD>_<HHMMSS>.zip
├── README_FOR_AI.md
├── PROMPTS/
│   ├── 01_GENERAL_MOEX_AUDIT.md
│   ├── 02_SIX_ATTACK_ANGLES.md
│   ├── 03_CONTRACTOR_BEHAVIOR_AUDIT.md
│   ├── 04_CONSULTANT_BEHAVIOR_AUDIT.md
│   └── 05_MEETING_AGENDA_GENERATOR.md
└── DATA/
    ├── 01_COUNTER_ATTACK_ITEMS.csv         (required, copied verbatim)
    ├── 02_CHAIN_EVENTS.csv                 (required, copied verbatim)
    ├── 03_CHAIN_REGISTER.csv               (required, copied verbatim)
    ├── 04_CHAIN_VERSIONS.csv               (required, copied verbatim)
    ├── 05_CHAIN_NARRATIVES.csv             (required, copied verbatim)
    ├── 06_ONION_LAYERS.csv                 (required, copied verbatim)
    ├── 07_ONION_SCORES.csv                 (required, copied verbatim)
    ├── 08_CHAIN_TIMELINE_ATTRIBUTION.csv   (required, copied verbatim)
    ├── 09_FLAT_GED_EXTRACT.csv             (required, BUILT — see §10.3)
    ├── SUBJECT_RISK_DOSSIERS.csv           (optional)
    ├── ACTOR_ATTACK_DOSSIERS.csv           (optional)
    ├── dashboard_summary.json              (optional)
    └── top_issues.json                     (optional)
```

Filename template: `JANSA_AI_AUDIT_PACK_<YYYYMMDD>_<HHMMSS>.zip` (timestamp only — Correction #1). No `run_number`, no `data_date`.

### 10.3 `09_FLAT_GED_EXTRACT.csv` — Open Question #1 resolved

**Decision: option (a) — single joined CSV.** A LEFT JOIN of `ctx.responses_df` onto `ctx.docs_df` on `doc_id`, producing one row per `(doc_id × response)` and one row per doc that has zero responses (response columns NaN). Justification: the brief reads as (a); a single file is simpler for an external AI to load (one `pd.read_csv` instead of two with a join contract); it preserves doc-level visibility for unanswered docs without forcing the AI to learn JANSA's two-frame topology.

Docs with zero responses are **preserved** (LEFT JOIN semantics). Reason: an unanswered doc is itself an audit signal (e.g. NEW_SUBMITTAL never reviewed). Dropping them would hide a class of CONSULTANT_COMMENT_INFLATION / LATE_SECONDARY_DISRUPTS_VISA precursors.

**Exact column order** for `09_FLAT_GED_EXTRACT.csv`:

| # | Target column | Source DataFrame | Source column | dtype |
|---|---|---|---|---|
| 1 | `numero` | `ctx.docs_df` | `numero` (or `numero_normalized`; see notes) | string |
| 2 | `indice` | `ctx.docs_df` | `indice` | string |
| 3 | `doc_id` | `ctx.docs_df` | `doc_id` | string |
| 4 | `emetteur_code` | `ctx.docs_df` | `emetteur` (raw 3-letter code in flat mode) | string |
| 5 | `emetteur_canonical` | `ctx.docs_df` | `emetteur_canonical` | string |
| 6 | `titre` | `ctx.docs_df` | `titre` | string |
| 7 | `lot` | `ctx.docs_df` | `lot` | string |
| 8 | `lot_normalized` | `ctx.docs_df` | `lot_normalized` | string |
| 9 | `created_at` | `ctx.docs_df` | `created_at` | ISO-8601 date or empty |
| 10 | `visa_global` | `ctx.flat_ged_doc_meta` | `flat_ged_doc_meta[doc_id]["visa_global"]` (NaN if key absent) | string |
| 11 | `approver_raw` | `ctx.responses_df` | `approver_raw` | string |
| 12 | `approver_canonical` | `ctx.responses_df` | `approver_canonical` | string |
| 13 | `is_exception_approver` | `ctx.responses_df` | `is_exception_approver` | bool/empty |
| 14 | `status_clean` | `ctx.responses_df` | `status_clean` | string |
| 15 | `date_status_type` | `ctx.responses_df` | `date_status_type` | string |
| 16 | `date_answered` | `ctx.responses_df` | `date_answered` | ISO-8601 date or empty |
| 17 | `date_limite` | `ctx.responses_df` | `date_limite` | ISO-8601 date or empty |
| 18 | `response_comment` | `ctx.responses_df` | `response_comment` | string |
| 19 | `effective_source` | `ctx.responses_df` | `effective_source` (added by `effective_responses.build_effective_responses` and present on `ctx.responses_df` after `data_loader.load_run_context` rebuild — `02_DATA_FLOW.md` "→ ctx.responses_df is replaced with the effective frame for downstream") | string |
| 20 | `report_memory_applied` | `ctx.responses_df` | `report_memory_applied` | bool/empty |

Notes:
- `numero` is written as a string with leading zeros preserved. Step 3 implementer must confirm whether `ctx.docs_df["numero"]` is already string-typed (post `normalize_docs`) or whether `numero_normalized` (line 328 of `[normalize.py](http://normalize.py)`) is the safer pick. If `numero` is integer-typed in `ctx.docs_df`, fall back to `numero_normalized` and rename to `numero`. Same dtype lock applies.
- `created_at`, `date_answered`, `date_limite` are formatted as `YYYY-MM-DD` (or empty string when NaT). No timestamps; the AI receives dates only.
- Columns 1–10 come from docs (one set per doc); columns 11–20 come from responses (one set per response). Docs with no response have NaN in columns 11–20.
- The CSV is written with `quoting=csv.QUOTE_MINIMAL` and `dtype` preserved by writing identity columns through `df[col] = df[col].astype("string")` before `to_csv`. Writing with `lineterminator="\n"` and `encoding="utf-8"` (no BOM).

### 10.4 `visa_global` and `effective_source` — Open Question #2 resolved

**Both are INCLUDED.** Sources:

- **`visa_global`**: NOT a column on any DataFrame today; it is *computed* by `WorkflowEngine.compute_visa_global_with_date(doc_id)` (`src/workflow_engine.py:228`). The pre-computed value is also attached to the engine in flat mode via `_flat_visa_override` (line 250) and is stored per-doc in `ctx.flat_ged_doc_meta[doc_id]["visa_global"]` (declared on `RunContext` at `src/reporting/data_loader.py:57`). The pack reads from `ctx.flat_ged_doc_meta`, NOT from `ctx.workflow_engine`, to avoid touching the SAS-filtered dual-view hazard (H-3). When `flat_ged_doc_meta` is empty (legacy raw-mode fallback), the column is written as empty string for every row. This is a known degraded-mode behavior, not an error.
- **`effective_source`**: lives on `ctx.responses_df` after `data_loader.load_run_context` rebuilds the engine over the effective frame. Citation: `effective_responses.py:329` (`effective["effective_source"] = EFFECTIVE_SOURCE_GED`) and `02_DATA_FLOW.md` lines 130-131 ("ctx.responses_df is replaced with the effective frame for downstream"). The pack reads `ctx.responses_df["effective_source"]` directly. If the column is missing (defensive fallback for an unexpected ctx shape), Step 3 writes empty strings — never raises.

The pack does NOT call `WorkflowEngine.compute_visa_global*`. No engine method invocation, no rebuild, no SAS-filter side-effect. This honours the §4 constraint "no business logic re-execution".

### 10.5 Deterministic sort key — Open Question #3 resolved

**For BUILT CSVs (only `09_FLAT_GED_EXTRACT.csv`):** sort ascending by `("numero", "indice", "doc_id", "approver_canonical")`. Tie-break: `na_position="last"`. Sort kind: `mergesort` (stable). Rationale: `numero` is the primary operational identity, `indice` collates a chain in lifecycle order, `doc_id` disambiguates across runs, `approver_canonical` orders the responses inside a doc consistently across runs. Same `ctx` → same sort.

**For COPIED CSVs (the eight required artifact CSVs and any optional CSV that exists):** byte-for-byte copy via `zipfile.ZipFile.write(disk_path, arcname=pack_path)`. No `pd.read_csv` + `to_csv` round-trip, no dtype coercion, no row reordering. Justification: each source CSV is already deterministic by construction (Phase 6A/6X enforces sha256 stability for `COUNTER_ATTACK_ITEMS.csv`; `chain_onion/exporter.py` is deterministic; `chain_timeline_attribution.write_chain_timeline_artifact` is deterministic). A reparse-and-rewrite would risk dtype drift (the same Phase 4 leading-zero risk that 6B's identity dtype lock guards against). Copying preserves the exact bytes that the existing pipeline already validates.

**Result:** for a fixed `ctx` and fixed on-disk artifacts, every byte inside the ZIP is identical across runs except the timestamp embedded in the ZIP's central-directory metadata and the filename. ZIP-level reproducibility (zeroed mtime in the central directory) is NOT required by this phase — only content-level reproducibility.

### 10.6 `README_FOR_AI.md` — full draft (French-first)

```markdown
# JANSA — Pack Audit IA (lecture obligatoire)

## 1. Objet du pack

Ce dossier ZIP contient les preuves opérationnelles d'un projet de chantier
suivi par l'équipe MOEX (Maîtrise d'Œuvre d'Exécution) JANSA. Votre rôle, en
tant qu'IA externe, est d'auditer ces preuves selon les six angles d'attaque
acceptés (voir §3) et de produire des constats sourcés.

Le pack a été généré automatiquement par JANSA. Aucune information n'a été
résumée, retraitée, ou inventée pour vous : vous lisez les mêmes données que
l'équipe MOEX.

## 2. Source des données

| Fichier | Origine | Niveau |
|---|---|---|
| `DATA/01_COUNTER_ATTACK_ITEMS.csv` | Plan d'action MOEX (Phase 6A/6X) | Sujet |
| `DATA/02_CHAIN_EVENTS.csv` | Moteur Chain+Onion | Événement |
| `DATA/03_CHAIN_REGISTER.csv` | Moteur Chain+Onion | Chaîne |
| `DATA/04_CHAIN_VERSIONS.csv` | Moteur Chain+Onion | Version d'indice |
| `DATA/05_CHAIN_NARRATIVES.csv` | Moteur Chain+Onion | Narratif par chaîne |
| `DATA/06_ONION_LAYERS.csv` | Moteur Onion | Couche d'enjeu |
| `DATA/07_ONION_SCORES.csv` | Moteur Onion | Score agrégé |
| `DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv` | Attribution de chronologie | Phase de cycle |
| `DATA/09_FLAT_GED_EXTRACT.csv` | GED projetée (docs ⨯ réponses) | Document/réponse |
| `DATA/SUBJECT_RISK_DOSSIERS.csv` (facultatif) | Dossier sujet | Sujet |
| `DATA/ACTOR_ATTACK_DOSSIERS.csv` (facultatif) | Dossier acteur | Acteur |
| `DATA/dashboard_summary.json` (facultatif) | Synthèse dashboard | Projet |
| `DATA/top_issues.json` (facultatif) | Top sujets prioritaires | Projet |

## 3. Six angles d'attaque acceptés

1. **CROSS_NUMERO_RESUBMISSION** — un document refusé sous un numéro réapparaît sous un autre.
2. **SAS_REF_DISEASE** — une entreprise accumule des SAS REF, surtout en indice A ou après correction.
3. **CONSULTANT_POSITION_SHIFT** — un consultant change d'avis entre indices (VAO puis REF).
4. **CONSULTANT_COMMENT_INFLATION** — un consultant ajoute beaucoup de commentaires tardivement, signe d'une première revue faible.
5. **LATE_SECONDARY_DISRUPTS_VISA** — un consultant secondaire répond après le visa MOEX, avec REF / SUS / avis contraire.
6. **CONTRACTOR_FAKE_CORRECTION** — l'entreprise resoumet mais les mêmes commentaires bloquants reviennent.

## 4. Ce que l'IA DOIT faire

- Lire les CSV avec les colonnes d'identité (`numero`, `indice`, `doc_id`, `family_key`, `emetteur_code`, `item_id`) en chaîne de caractères pour conserver les zéros de tête.
- Citer chaque constat avec au minimum `family_key` et `numero` (et `indice` si pertinent).
- Justifier chaque sévérité par les colonnes utilisées (ex. `CHAIN_EVENTS.is_blocking`, `ONION_SCORES.normalized_score_100`).
- Suivre les prompts dans `PROMPTS/` un à un, dans l'ordre.

## 5. Ce que l'IA NE DOIT PAS faire

- Inventer un numéro, un acteur, un commentaire, ou une date qui n'apparaît pas dans les CSV.
- Remplacer ou recalculer les buckets JANSA (`action_bucket` dans `01_COUNTER_ATTACK_ITEMS.csv`). Vous pouvez signaler des sujets, jamais réclasser.
- Reproduire des données personnelles au-delà de ce qui est déjà dans les CSV.
- Produire un constat sans citation `family_key` / `numero`.
- Sortir du périmètre des six angles d'attaque listés au §3.

## 6. Comment lire chaque CSV

- **`01_COUNTER_ATTACK_ITEMS.csv`** — 28 colonnes. Une ligne = un sujet à traiter. Colonnes clés : `item_id`, `numero`, `indice`, `family_key`, `subject_label`, `action_bucket`, `action_label`, `plain_reason`, `recommended_action`, `risk_level`, `evidence_summary`, `days_open`, `days_late`, `current_state`, `is_internal_moex_exposure`, `is_external_attackable`, `chain_observations_full`, `consultant_reports_full`.
- **`02_CHAIN_EVENTS.csv`** — 18 colonnes. Une ligne = un événement de chaîne. Colonnes clés : `family_key`, `version_key`, `event_seq`, `event_date`, `actor`, `actor_type`, `step_type`, `status`, `is_blocking`, `is_completed`, `requires_new_cycle`, `delay_contribution_days`, `issue_signal`.
- **`03_CHAIN_REGISTER.csv`** — 23 colonnes. Une ligne = une chaîne (un sujet documentaire suivi sur plusieurs indices). Colonnes clés : `family_key`, `numero`, `total_versions`, `latest_indice`, `current_state`, `portfolio_bucket`, `stale_days`, `operational_relevance_score`.
- **`04_CHAIN_VERSIONS.csv`** — 14 colonnes. Une ligne = une version d'indice. Colonnes clés : `family_key`, `version_key`, `numero`, `indice`, `has_blocking_rows`, `requires_new_cycle_flag`.
- **`05_CHAIN_NARRATIVES.csv`** — 15 colonnes. Une ligne = un narratif synthétique par chaîne. Colonnes clés : `family_key`, `executive_summary`, `primary_driver_text`, `secondary_driver_text`, `recommended_focus`, `urgency_label`, `confidence_label`, `normalized_score_100`.
- **`06_ONION_LAYERS.csv`** — 18 colonnes. Une ligne = une couche d'enjeu. Colonnes clés : `family_key`, `layer_code`, `layer_name`, `issue_type`, `severity_raw`, `confidence_raw`, `evidence_count`, `pressure_index`.
- **`07_ONION_SCORES.csv`** — 22 colonnes. Une ligne = score agrégé par chaîne. Colonnes clés : `family_key`, `total_onion_score`, `normalized_score_100`, `top_layer_code`, `contractor_impact_score`, `sas_impact_score`, `consultant_primary_impact_score`, `consultant_secondary_impact_score`, `moex_impact_score`, `contradiction_impact_score`, `escalation_flag`.
- **`08_CHAIN_TIMELINE_ATTRIBUTION.csv`** — 14 colonnes. Une ligne = une phase de cycle attribuée à un acteur. Colonnes clés : `family_key`, `numero`, `indice`, `phase`, `days_actual`, `days_expected`, `delay_days`, `attributed_to_actor`, `attributed_to_tier`, `attributed_days`.
- **`09_FLAT_GED_EXTRACT.csv`** — 20 colonnes. Une ligne = un document × une réponse (ou un document sans réponse). Colonnes clés : `numero`, `indice`, `doc_id`, `emetteur_canonical`, `titre`, `visa_global`, `approver_canonical`, `status_clean`, `date_status_type`, `date_answered`, `date_limite`, `response_comment`, `effective_source`.

## 7. Comment utiliser les fichiers PROMPTS/

Lisez les fichiers `PROMPTS/01` à `PROMPTS/05` dans l'ordre. Chaque prompt définit un objectif, les CSV à inspecter, le format de sortie attendu, et la règle d'or (interdiction d'inventer). N'enchaînez pas les prompts sans avoir produit la sortie du précédent.

## 8. Glossaire

- **MOEX** — Maîtrise d'Œuvre d'Exécution. L'équipe qui pilote le chantier côté maître d'ouvrage.
- **SAS** — Bureau de Contrôle Safety Assurance. Premier filtre conformité avant la chaîne consultant complète.
- **REF** — Refusé. Statut d'un visa.
- **VAO** — Visé Avec Observations.
- **VSO** — Visé Sans Observations.
- **EMD** — Émetteur (entreprise qui soumet le document).
- **family_key** — clé d'identification d'une chaîne documentaire (un sujet suivi sur plusieurs indices).
- **numero** — numéro GED du document (chaîne, zéros de tête conservés).
- **indice** — version du document (A, B, C...).

---

### Note for English-speaking AI

This pack contains French-language project data from a French construction
project. The CSV column names are stable identifiers (English-like) but the
free-text fields (`response_comment`, `executive_summary`,
`primary_driver_text`, `subject_label`, `plain_reason`,
`recommended_action`) are in French. The five PROMPTS files in `PROMPTS/`
are written in French and define the audit scope. Do not translate the
column names; do read the French free-text. Cite findings using
`family_key` and `numero`. Follow the §5 prohibition on invention.
```

### 10.7 Five `PROMPTS/*.md` — full drafts (French-first)

#### `PROMPTS/01_GENERAL_MOEX_AUDIT.md`

```markdown
# Prompt 01 — Audit MOEX général

## Objectif
Identifier les 10 chaînes documentaires les plus dangereuses pour MOEX en ce moment, tous angles confondus.

## CSV à inspecter
- `DATA/01_COUNTER_ATTACK_ITEMS.csv`
- `DATA/03_CHAIN_REGISTER.csv`
- `DATA/05_CHAIN_NARRATIVES.csv`
- `DATA/07_ONION_SCORES.csv`
- `DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv`

## Méthode
1. Joindre `01_COUNTER_ATTACK_ITEMS` (sur `family_key`) avec `07_ONION_SCORES` (`normalized_score_100`, `escalation_flag`) et `05_CHAIN_NARRATIVES` (`urgency_label`, `recommended_focus`).
2. Filtrer sur `escalation_flag == True` OR `normalized_score_100 >= 70` OR `risk_level == "HIGH"`.
3. Trier par `normalized_score_100` décroissant.
4. Garder les 10 premières chaînes uniques par `family_key`.

## Format de sortie
Un tableau avec : `rang`, `family_key`, `numero`, `indice`, `subject_label`, `urgency_label`, `normalized_score_100`, `risque_principal_2_lignes`, `action_recommandée_1_ligne`.

## Règle d'or
Ne jamais inventer un `family_key` ou un `numero` qui n'apparaît pas dans les CSV. Ne jamais réécrire `action_bucket`. Si moins de 10 chaînes remplissent les critères, dites-le explicitement.
```

#### `PROMPTS/02_SIX_ATTACK_ANGLES.md`

```markdown
# Prompt 02 — Six angles d'attaque

## Objectif
Pour chacun des six angles définis au §3 du `README_FOR_AI.md`, produire les constats sourcés.

## Format de sortie commun (par constat)
| Champ | Description |
|---|---|
| `family_key` | clé de la chaîne |
| `numero` | numéro GED |
| `indice` | indice incriminé |
| `evidence_columns_cited` | liste des colonnes utilisées comme preuve |
| `severity_estimate` | LOW / MEDIUM / HIGH (avec justification chiffrée) |
| `recommended_action` | une phrase, en français, opérationnelle |

Si l'angle n'est pas soutenu par les données, écrivez explicitement : « Aucun constat — données insuffisantes » et passez au suivant.

## Angle 1 — CROSS_NUMERO_RESUBMISSION
- À chercher : un document refusé sous un `numero` qui réapparaît, sous un autre `numero`, avec le même `emetteur_code`/`emetteur_canonical` et un `titre` similaire.
- CSV : `09_FLAT_GED_EXTRACT.csv` (joindre par `emetteur_canonical` + similarité `titre`), recouper avec `03_CHAIN_REGISTER.csv` pour le `current_state`.
- Indices forts : `status_clean == "REF"` sur l'ancien `numero`, `created_at` postérieur sur le nouveau, mêmes mots-clés dans `titre`.

## Angle 2 — SAS_REF_DISEASE
- À chercher : entreprises avec un nombre élevé de réponses `0-SAS` REF ou `SAS REF`.
- CSV : `09_FLAT_GED_EXTRACT.csv` (`approver_raw == "0-SAS"` AND `status_clean` contient "REF") agrégé par `emetteur_canonical`. Recouper avec `07_ONION_SCORES.sas_impact_score`.
- Indices forts : ratio SAS REF / SAS total > 30 %, ou répétition après correction (même `family_key`, indice B+).

## Angle 3 — CONSULTANT_POSITION_SHIFT
- À chercher : un même `approver_canonical` change de statut (VAO → REF, ou inverse) entre deux indices d'une même chaîne.
- CSV : `09_FLAT_GED_EXTRACT.csv` agrégé par (`family_key` ou `numero`, `approver_canonical`), trier par `indice`. Recouper avec `02_CHAIN_EVENTS.csv` (`actor`, `status`, `is_blocking`).
- Indices forts : VAO en indice A puis REF en indice B sans nouveau commentaire substantiel.

## Angle 4 — CONSULTANT_COMMENT_INFLATION
- À chercher : un consultant primaire avec peu de commentaires en première revue, beaucoup en revue tardive.
- CSV : `09_FLAT_GED_EXTRACT.csv` (longueur de `response_comment` par `(family_key, approver_canonical, indice)`). Recouper avec `07_ONION_SCORES.consultant_primary_impact_score`.
- Indices forts : longueur de `response_comment` indice A < 50 caractères ET indice B > 300 caractères pour le même `approver_canonical`.

## Angle 5 — LATE_SECONDARY_DISRUPTS_VISA
- À chercher : un consultant secondaire (`actor_type` distinct de `MOEX_PRIMARY`) répond après le visa MOEX et provoque un nouveau cycle.
- CSV : `02_CHAIN_EVENTS.csv` (filtrer `actor_type` secondaire, `event_date` postérieur au MOEX visa de la même chaîne, `status ∈ {REF, SUS}` ou `requires_new_cycle == True`). Recouper avec `08_CHAIN_TIMELINE_ATTRIBUTION.csv` (`attributed_to_tier`, `attributed_days`).
- Indices forts : `is_blocking == True` côté secondaire APRÈS la phase MOEX, `attributed_days > 0` sur le secondaire.

## Angle 6 — CONTRACTOR_FAKE_CORRECTION
- À chercher : entreprise resoumet (nouvel `indice`) mais les mêmes commentaires bloquants reviennent.
- CSV : `09_FLAT_GED_EXTRACT.csv` (mêmes mots-clés dans `response_comment` entre indices). Recouper avec `02_CHAIN_EVENTS.csv` (`is_blocking`, `issue_signal`) et `07_ONION_SCORES.contractor_impact_score`.
- Indices forts : `requires_new_cycle == True` sur deux indices consécutifs avec `actor_type` consultant identique.

## Règle d'or
Aucun constat sans citation `family_key` + `numero`. Aucune réécriture des buckets JANSA. Si l'angle n'est pas soutenu : « Aucun constat — données insuffisantes ».
```

#### `PROMPTS/03_CONTRACTOR_BEHAVIOR_AUDIT.md`

```markdown
# Prompt 03 — Audit comportement entreprise (côté CONTRACTOR)

## Objectif
Identifier les entreprises (emetteur) dont le comportement de soumission révèle un risque opérationnel.

## CSV à inspecter
- `DATA/03_CHAIN_REGISTER.csv` (`family_key`, `numero`, `total_versions`, `total_blocking_versions`, `requires_new_cycle_flag`, `current_state`, `stale_days`)
- `DATA/04_CHAIN_VERSIONS.csv` (`requires_new_cycle_flag`, `has_blocking_rows`, `blocking_actor_count`)
- `DATA/06_ONION_LAYERS.csv` (filtrer `layer_code` côté contracteur, ex. `L1_CONTRACTOR_QUALITY`)
- `DATA/07_ONION_SCORES.csv` (`contractor_impact_score`, `sas_impact_score`)
- `DATA/09_FLAT_GED_EXTRACT.csv` (`emetteur_canonical`, `approver_raw == "0-SAS"`, `status_clean`)

## Patterns recherchés
1. **CONTRACTOR_FAKE_CORRECTION** : indice B+ avec `requires_new_cycle_flag == True` sur la même chaîne.
2. **SAS_REF répétés** : agrégation par `emetteur_canonical` du nombre de SAS REF ; outliers (>10 sur le projet, ou >30 % du total SAS de l'entreprise).
3. **Churn d'indices** : chaînes avec `total_versions > 4` et `current_state` toujours bloquant.

## Format de sortie
Un tableau par entreprise : `emetteur_canonical`, `nombre_chaînes_concernées`, `pattern`, `family_keys_exemples (max 3)`, `contractor_impact_score`, `sas_impact_score`, `recommended_action`.

## Règle d'or
Ne jamais inventer une entreprise. N'utilisez `emetteur_canonical` que tel qu'il apparaît dans les CSV. Si aucun pattern ne sort : « Aucun constat — données insuffisantes ».
```

#### `PROMPTS/04_CONSULTANT_BEHAVIOR_AUDIT.md`

```markdown
# Prompt 04 — Audit comportement consultant

## Objectif
Identifier les consultants (primaires et secondaires) dont le comportement révèle un risque opérationnel pour MOEX.

## CSV à inspecter
- `DATA/02_CHAIN_EVENTS.csv` (`actor`, `actor_type`, `step_type`, `status`, `is_blocking`, `event_date`, `delay_contribution_days`)
- `DATA/06_ONION_LAYERS.csv`
- `DATA/07_ONION_SCORES.csv` (`consultant_primary_impact_score`, `consultant_secondary_impact_score`, `contradiction_impact_score`)
- `DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv` (`attributed_to_actor`, `attributed_to_tier`, `attributed_days`)
- `DATA/09_FLAT_GED_EXTRACT.csv` (`approver_canonical`, `status_clean`, `response_comment`, `effective_source`)

## Patterns recherchés
1. **CONSULTANT_POSITION_SHIFT** (cf. Prompt 02 §3) — agréger côté consultant.
2. **CONSULTANT_COMMENT_INFLATION** (cf. Prompt 02 §4) — agréger longueur de `response_comment` par `(approver_canonical, indice)`.
3. **LATE_SECONDARY_DISRUPTS_VISA** (cf. Prompt 02 §5) — agréger les événements secondaires post-visa.
4. **Lenteur chronique** : `attributed_days` cumulés par `attributed_to_actor` côté consultant.

## Format de sortie
Un tableau par consultant : `approver_canonical`, `tier (PRIMARY/SECONDARY)`, `pattern`, `family_keys_exemples (max 3)`, `attributed_days_cumulés`, `consultant_*_impact_score`, `recommended_action`.

## Règle d'or
Aucune attaque ad hominem. Citez les colonnes. Si l'angle n'est pas soutenu : « Aucun constat — données insuffisantes ».
```

#### `PROMPTS/05_MEETING_AGENDA_GENERATOR.md`

```markdown
# Prompt 05 — Générateur d'ordre du jour réunion MOEX

## Objectif
Produire un ordre du jour d'une page pour la prochaine réunion MOEX, en français exclusivement.

## CSV à inspecter
- Toutes les sorties des Prompts 01 à 04 ci-dessus, plus :
- `DATA/01_COUNTER_ATTACK_ITEMS.csv` (`action_bucket`, `risk_level`, `recommended_action`)
- `DATA/05_CHAIN_NARRATIVES.csv` (`recommended_focus`, `urgency_label`)

## Structure de l'ordre du jour
1. **Top 5 sujets à décider** — chacun avec `family_key`, `numero`, une phrase de décision attendue.
2. **Top 3 entreprises à relancer** — chacune avec `emetteur_canonical`, motif (1 ligne), `family_keys_exemples`.
3. **Top 3 consultants à challenger** — chacun avec `approver_canonical`, motif (1 ligne), `family_keys_exemples`.
4. **Annexes** : la liste brute des `family_key` cités, dans l'ordre d'apparition.

## Format
Markdown, français exclusivement. Une seule page imprimable. Pas de tableaux multi-pages, pas d'annexes longues.

## Règle d'or
Aucune ligne sans citation `family_key` ou `numero`. Aucune décision inventée. Si une catégorie a moins d'éléments que demandé, écrivez « Aucun élément supplémentaire » plutôt que de combler.
```

### 10.8 Error-payload shape — Open Question #5 resolved

Reproduced verbatim from §3 Correction #2:

**Success:**
```json
{
  "success": true,
  "path": "...",
  "filename": "...",
  "included_files": [],
  "missing_optional_files": [],
  "error": null
}
```

**Failure:**
```json
{
  "success": false,
  "path": null,
  "filename": null,
  "included_files": [],
  "missing_optional_files": [],
  "error": "..."
}
```

**Field semantics:**

- `success`: `bool`. Always present. `true` iff the ZIP was written successfully and every required file is included.
- `path`: absolute string path to the ZIP on success; `null` on failure. Never empty string.
- `filename`: the basename only (`JANSA_AI_AUDIT_PACK_<...>.zip`) on success; `null` on failure.
- `included_files`: list of pack-relative paths actually written into the ZIP. Always an array — `[]` if empty, **never `null`**. On success this lists all 14 required pack paths plus any optional path that was found on disk.
- `missing_optional_files`: list of pack-relative paths from `OPTIONAL_FILES` whose source was missing. Always an array — `[]` if empty, **never `null`**. On failure (e.g. required file missing) this may be `[]`.
- `error`: `null` on success; non-empty string on failure. Never empty string, never `null` on failure.

**Failure conditions Step 3 must produce a clean payload for (NOT raise):**

1. `ctx is None`.
2. `ctx.docs_df` is `None` or empty.
3. `ctx.responses_df` is `None` or empty.
4. Any required source file in `REQUIRED_FILES` (excluding the `<BUILT>` and `<GENERATED>` sentinels) absent on disk.
5. `output/exports/` cannot be created or is not writable.
6. `_build_flat_ged_extract` raises (caught and converted to a payload with `error="Flat-GED extract failed: <repr>"`).
7. `zipfile.ZipFile.write` raises (disk full, permission, etc.).

**Confirmed:** missing OPTIONAL files NEVER fail. They are recorded in `missing_optional_files` and ZIP generation continues. Step 3 must enforce this with a unit-style sandbox check (point any required source path to a non-existent location → expect failure payload; point any optional source path to a non-existent location → expect success payload with the missing path listed).

### 10.9 Worked example

**Successful return value (illustrative — paths and filenames are realistic, not from a real run):**

```json
{
  "success": true,
  "path": "C:/Users/GEMO 050224/Desktop/cursor/GF updater v3/output/exports/JANSA_AI_AUDIT_PACK_20260505_174213.zip",
  "filename": "JANSA_AI_AUDIT_PACK_20260505_174213.zip",
  "included_files": [
    "DATA/01_COUNTER_ATTACK_ITEMS.csv",
    "DATA/02_CHAIN_EVENTS.csv",
    "DATA/03_CHAIN_REGISTER.csv",
    "DATA/04_CHAIN_VERSIONS.csv",
    "DATA/05_CHAIN_NARRATIVES.csv",
    "DATA/06_ONION_LAYERS.csv",
    "DATA/07_ONION_SCORES.csv",
    "DATA/08_CHAIN_TIMELINE_ATTRIBUTION.csv",
    "DATA/09_FLAT_GED_EXTRACT.csv",
    "DATA/dashboard_summary.json",
    "DATA/top_issues.json",
    "README_FOR_AI.md",
    "PROMPTS/01_GENERAL_MOEX_AUDIT.md",
    "PROMPTS/02_SIX_ATTACK_ANGLES.md",
    "PROMPTS/03_CONTRACTOR_BEHAVIOR_AUDIT.md",
    "PROMPTS/04_CONSULTANT_BEHAVIOR_AUDIT.md",
    "PROMPTS/05_MEETING_AGENDA_GENERATOR.md"
  ],
  "missing_optional_files": [
    "DATA/SUBJECT_RISK_DOSSIERS.csv",
    "DATA/ACTOR_ATTACK_DOSSIERS.csv"
  ],
  "error": null
}
```

**Failure return value (illustrative — `COUNTER_ATTACK_ITEMS.csv` missing on disk):**

```json
{
  "success": false,
  "path": null,
  "filename": null,
  "included_files": [],
  "missing_optional_files": [],
  "error": "Required source missing: output/intermediate/COUNTER_ATTACK_ITEMS.csv. Run scripts/build_counter_attack.py first."
}
```

### 10.10 Risk callouts for Step 3

The implementing agent (Claude Code) must read this list before opening `[counter_attack_ai_pack.py](http://counter_attack_ai_pack.py)`:

1. **H-1 / H-1.1 — Windows-mounted source.** Use the `Read` tool exclusively to verify file content, size, and presence. Do NOT use bash `wc`/`grep`/`cat`/`head`/`tail` on `src/`, `ui/`, or `output/intermediate/`. Do NOT run in-place rewrites (`sed -i`, `python -c "open(p,'w').write(...)"`) on Windows-mounted source. Make a `.pre-step3` copy of any untracked file before any patch script.
2. **H-3 — Dual-attribute SAS hazard.** Read responses from `ctx.responses_df` (not `ctx.workflow_engine.responses_df`). The 0-SAS rows are filtered out of the WorkflowEngine view but are present on `ctx.responses_df`. The pack's Flat-GED extract MUST surface SAS rows (Angle 2 SAS_REF_DISEASE depends on it).
3. **Leading zeros.** Cast `numero`, `indice`, `doc_id`, `family_key`, `emetteur_code`, `item_id`, `version_key` to pandas `string` dtype before any `to_csv` call. The 8 copied CSVs are written byte-for-byte (no reparse) — leading zeros are already preserved by the source artifact's own dtype lock. Only the BUILT `09_FLAT_GED_EXTRACT.csv` needs explicit casting at write time.
4. **Filename — no `run_number`, no `data_date`.** Only `<YYYYMMDD>_<HHMMSS>` (Correction #1).
5. **French-first prompts.** All five `PROMPTS/*.md` files plus the body of `README_FOR_AI.md` are French. Only the trailing "Note for English-speaking AI" subsection in `README_FOR_AI.md` is English.
6. **Forbidden phrase.** The phrase forbidden by §4 of this phase plan (the legacy operator-shame label that §4 prohibits explicitly) must not appear in any generated string, comment, docstring, or test fixture in `[counter_attack_ai_pack.py](http://counter_attack_ai_pack.py)`. Add a self-test in the Step 3 validation that greps the generated `README_FOR_AI.md` and the five PROMPTS for that exact phrase as defined in §4 and fails if present.
7. **Payload contract.** `success`/`error` (Correction #2). Empty arrays `[]`, never `null` (Open Question #5). UI explorer-open guard `success === true && path` (Correction #3) — the JSX side enforces it; the backend must never return `path: ""`.
8. **No engine invocation.** Do not call `ctx.workflow_engine.compute_visa_global*`. Read `ctx.flat_ged_doc_meta[doc_id]["visa_global"]` instead. If `flat_ged_doc_meta` is empty, write `visa_global` as empty string. No fallback that touches the engine.
9. **No `data_loader.py` edit.** Confirmed by Step 1 §7.4. The fields used (`docs_df`, `responses_df`, `flat_ged_doc_meta`) already exist on `RunContext`.
10. **Determinism.** Mergesort everywhere `09` is sorted. Copy bytes for the eight required artifact CSVs. Same `ctx` + same on-disk artifacts → same pack content (modulo the timestamp embedded in the filename).

---

## 11. Phase compilation summary

### 11.1 What was built

Phase 6D adds a single on-demand export path to JANSA. A `Générer Pack Audit IA` button in the Reports tab invokes a new Python module (`src/reporting/counter_attack_ai_pack.py`) that assembles a timestamp-named ZIP under `output/exports/`. The ZIP bundles existing JANSA evidence — 8 required source CSVs copied verbatim, 1 in-memory-built Flat-GED extract (LEFT JOIN of docs × responses, 20 columns, mergesorted), 1 French-first README, and 5 French-first PROMPTS covering the six accepted attack angles — plus up to 4 optional files when present. No AI API call, no DB write, no deterministic-artifact mutation. Smoke-test validated 2026-05-05: pack generated and ingested by external AI on first attempt.

### 11.2 Files created

- `src/reporting/counter_attack_ai_pack.py`
- `docs/implementation/PHASE_6D_TEAM_AI_AUDIT_PACK.md`

### 11.3 Files modified

- `app.py` (1 module-level import at line 39 + 1 Api method at lines 1255–1287)
- `ui/jansa/data_bridge.js` (1 bridge method: `generateAiAuditPack`, lines 329–360)
- `ui/jansa/shell.jsx` (2 state pairs at lines 782–783 + 1 handler at lines 807–827 + 1 card replacement at post-edit lines 877–910)
- `context/05_OUTPUT_ARTIFACTS.md` (1 On-demand exports section + 1 row)
- `context/03_UI_FEED_MAP.md` (1 entry in the ReportsPage section + 1 row in the section D summary table)

### 11.4 Files deliberately NOT modified

- `context/artifact_inventory.csv` — Correction #5: the on-demand pack's timestamp-only naming does not fit the run-numbered inventory schema; documented in markdown context only (`context/05_OUTPUT_ARTIFACTS.md`).
- `README.md` — Phase 6C precedent: README is not updated unless the user explicitly requests it.
- All DO-NOT-TOUCH files listed in §5: `src/flat_ged/**`, `src/chain_onion/**`, `src/run_memory.py`, `src/report_memory.py`, `src/effective_responses.py`, `src/reporting/counter_attack_builder.py`, `src/reporting/document_command_center.py`, `src/reporting/focus_ownership.py`, `src/reporting/chain_timeline_attribution.py`, `src/reporting/aggregator.py`, `src/reporting/data_loader.py`, `src/reporting/counter_attack_query.py`, `src/pipeline/**`, `data/run_memory.db`, `data/report_memory.db`, all intermediate/chain_onion output CSVs and JSONs, `ui/jansa/counter_attack.jsx`, all other JSX/HTML files listed in §5.

### 11.5 Validation summary

Sandbox-side validations passed across Steps 3–6: `python -m py_compile` (compile check), module import, structural shape (all 14 required pack paths present in the built ZIP), forbidden-phrase check (the phrase prohibited by §4 absent from all generated strings and comments), payload shape (§10.8 success/failure envelope returned on every code path including ctx=None, missing required file, and missing optional file), and determinism (consecutive sha256 match on pack contents for a fixed ctx and fixed on-disk artifacts). Windows-shell end-to-end smoke test confirmed by user 2026-05-05: pack generated successfully under `output/exports/` and ingested by external AI on first attempt.

### 11.6 Known limitations / follow-ups

- `numero` dtype probe in `_build_flat_ged_extract` takes the `numero_normalized` fallback when pandas reports `dtype` as `"str"` instead of `"object"`/`"string"` (functionally identical output; one-line tightening possible in a future patch).
- The `if ctx is None` guard in `Api.generate_counter_attack_ai_audit_pack` is defensive dead code (`load_run_context` returns a degraded `RunContext`, never `None`); the failure path still routes correctly through `_validate_inputs`.
- `var result = ...` in `handleAiPack` (`shell.jsx` line 812) uses ES5 syntax; the file convention is `const`. Cosmetic; no behavior change.
- Module-level `from reporting.counter_attack_ai_pack import build_ai_audit_pack` in `app.py` is a structural deviation from the file's method-local `reporting.*` import convention; required by the validation contract; harmless functionally.

### 11.7 Recommendation

`VALIDATED`.
