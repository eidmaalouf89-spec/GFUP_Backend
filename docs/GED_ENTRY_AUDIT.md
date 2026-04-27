# GED Entry Audit

**Step:** 3 — Inventory current GED entry points in the engine  
**Plan version:** v2  
**Date:** 2026-04-23  
**Author:** Generated from source read — no engine files modified  
**Output consumed by:** Step 3b (Backend Semantic Contract), Step 4 (Flat GED Adapter)

---

## Overview

This document maps exactly how raw GED data enters the current pipeline, what transformations are applied at each layer, and where the main integration points lie for the flat GED adapter. It is based on a literal reading of the eleven source files listed in the plan. No behaviour is inferred; every claim cites the function or class it comes from.

---

## A. Read Layer — `read_raw.py`

### What it does

`read_ged(filepath: str) -> tuple[docs_df, responses_df, approver_names]` is the single entry point for raw GED data. It opens the GED export workbook using `openpyxl` (read-only, data-only) and reads exactly one sheet: `"Doc. sous workflow, x versions"`.

### Header parsing

The sheet has a two-row merged header structure. `_parse_headers(row1, row2)` splits columns into two categories:

- **Base fields** — any column whose row-1 header matches the 14-item `BASE_FIELDS` constant: `AFFAIRE`, `PROJET`, `BATIMENT`, `PHASE`, `EMETTEUR`, `SPECIALITE`, `LOT`, `TYPE DE DOC`, `ZONE`, `NIVEAU`, `NUMERO`, `INDICE`, `Libellé du document`, `Créé le`.
- **Approver groups** — every other non-empty row-1 header is treated as an approver column name. For each approver, the parser records four consecutive column indices: `date_col`, `response_col`, `comment_col`, `pj_col` (sub-fields: "Date réponse", "Réponse", "Commentaire", "PJ").

### What `docs_df` contains

One row per non-empty data row in the sheet. Columns:

| Column | Source |
|--------|--------|
| `doc_id` | Generated `uuid4()` — not from GED |
| `affaire`, `projet`, `batiment`, `phase`, `emetteur`, `specialite`, `lot`, `type_de_doc`, `zone`, `niveau`, `numero`, `indice`, `lib_ll_du_document` | Base fields, snake_cased and accent-stripped |
| `cr_e_le` (or variant) | "Créé le" column — name varies by encoding |

### What `responses_df` contains

One row per (doc_id × approver group). Columns:

| Column | Source |
|--------|--------|
| `doc_id` | Links to `docs_df` |
| `approver_raw` | Raw approver column name from GED header |
| `response_date_raw` | Cell value from `date_col` — can be datetime, string, or None |
| `response_status_raw` | Cell value from `response_col` — the visa code string |
| `response_comment` | Cell value from `comment_col` |
| `pj_flag` | 1 if `pj_col` cell is non-null/non-zero, else 0 |

### What `approver_names` contains

Ordered list of all raw approver column name strings discovered in the sheet header. Length equals the number of approver group columns found.

---

## B. Normalize Layer — `normalize.py`

### `normalize_docs(docs_df, mapping) -> pd.DataFrame`

Adds the following columns to `docs_df`:

| Added column | Logic |
|---|---|
| `lot_normalized` | `normalize_lot()` — strips leading letter prefix(es), converts numeric part to int-string, preserves optional A/B suffix. E.g. `A041 → 41`, `I013B → 13B`. |
| `lot_prefix` | `get_lot_prefix()` — extracts the leading letter group (A, B, H, I, 0, …). |
| `numero_normalized` | `normalize_numero()` — casts to int then string, strips leading zeros. |
| `emetteur_canonical` | Set to raw `emetteur` value — a comment in the code notes that mapping to canonical name is handled in the routing step, not here. |
| `indice` | Stripped of whitespace. |
| `created_at` | `pd.to_datetime()` applied to the "Créé le" column, searched under several possible encoded column names (`cree_le`, `cr_e_le`, `cr__e_le`, `créé_le`, partial-match fallback). |

### `normalize_responses(responses_df, mapping) -> pd.DataFrame`

Adds:

| Added column | Logic |
|---|---|
| `approver_canonical` | `map_approver(raw_name, mapping)` — looks up raw header name in the hardcoded mapping dict. Falls back to the raw name if not found. |
| `is_exception_approver` | True if `approver_canonical == "Exception List"`. Also forced True for `approver_raw == "0-SAS"`. |
| `date_answered` | From `interpret_date_field()` — the actual date object if status is ANSWERED, else None. |
| `date_status_type` | From `interpret_date_field()` — one of: `NOT_CALLED`, `PENDING_IN_DELAY`, `PENDING_LATE`, `ANSWERED`. |
| `date_limite` | From `interpret_date_field()` — `date` object extracted from parenthesized `(YYYY/MM/DD)` in the "Date réponse" text field. |
| `status_clean` | `clean_status()` — strips leading dots, uppercases. E.g. `.VAO → VAO`. |

### `interpret_date_field(raw) -> dict`

Core classification function. Rules:
- `None` or empty string → `NOT_CALLED`
- `datetime`/`date` object → `ANSWERED`, `date` = the value, `date_limite = None`
- String starting with `"rappel"` (case-insensitive) → `PENDING_LATE`, extracts `date_limite` from `(YYYY/MM/DD)`
- String containing `"en attente"` (no "rappel") → `PENDING_IN_DELAY`, extracts `date_limite`
- Other non-empty string → `PENDING_IN_DELAY` (fallback)

### `load_mapping() -> dict`

Returns the hardcoded `_GED_APPROVER_MAPPING` dict. The file formerly loaded `Mapping.xlsx`; as of 2026-04-20 the mapping is fully inlined. Contains ~70 entries: per-building prefixed column names (`0-`, `A-`, `B-`, `H-`) mapped to canonical names, plus ~30 lot-specific exception entries mapped to `"Exception List"`. The canonical `0-SAS` key maps to itself (not to "Exception List") — SAS is excluded by a separate code path.

---

## C. SAS Handling — `domain/sas_helpers.py` + `normalize.py`

### SAS states in the old engine (4 states)

The old engine defines four distinct SAS states derived from the `0-SAS` approver row:

| Old engine state | Detection condition |
|---|---|
| `NOT_CALLED` | No `0-SAS` row, or row is fully empty |
| `PENDING_IN_DELAY` | `response_date_raw` contains "en attente" (no "Rappel") |
| `PENDING_LATE` | `response_date_raw` is any string but NOT a "Rappel" string and NOT empty (fallback) — note: this also covers `PENDING_IN_DELAY` fallback path |
| `RAPPEL` | `response_date_raw` contains "rappel" (case-insensitive) — distinct bucket in `_build_sas_lookup()` |
| `ANSWERED` | `response_date_raw` is a datetime or date object |

Note: `normalize_responses()` maps "Rappel" strings to `date_status_type = PENDING_LATE`, while `_build_sas_lookup()` (used for the GF output lookup) uses a separate `RAPPEL` state. There are therefore five distinct SAS outcome labels across the codebase: `NOT_CALLED`, `PENDING_IN_DELAY`, `PENDING_LATE` (normalize layer), `RAPPEL`, `ANSWERED` (_build_sas_lookup layer).

### SAS states in flat GED (3 states)

Per `docs/FLAT_GED_CONTRACT.md` §SAS, the flat builder produces three states:

| Flat GED state | Meaning |
|---|---|
| `ABSENT` | Approver column is empty / never called |
| `PENDING` | Approver was called but has not responded (covers both first-request and reminder) |
| `ANSWERED` | A date object was present in the approver column |

**Semantic difference — PENDING granularity.** The flat builder's single `PENDING` state collapses what the old engine separates into `PENDING_IN_DELAY` / `PENDING_LATE` / `RAPPEL`. The deadline date (`date_limite`) is preserved in the flat builder via `response_deadline`, so the distinction between first-request and reminder can be partially recovered — but the old engine's `RAPPEL` state (requiring the presence of the word "Rappel") is not explicitly reproduced as a separate field.

**Semantic difference — SAS filter.** `_apply_sas_filter()` (called in `stage_normalize`) permanently removes documents from processing when: (a) the `0-SAS` approver has a "Rappel" in `response_date_raw` AND (b) `created_at` year < 2026. The flat builder applies no such filter — all documents are passed through. The adapter (Step 4) must decide whether to apply this filter post-load or accept a different document scope.

---

## D. Version / Family Layer — `version_engine.py`

### What `VersionEngine.run()` produces

`VersionEngine` takes the normalized `docs_df` (all versions of all documents) and adds the following columns:

| Output column | Meaning |
|---|---|
| `is_dernier_indice` | `True` on the chronologically last row in a lifecycle (the "current" version) |
| `lifecycle_id` | UUID grouping all versions in the same lifecycle chain |
| `chain_position` | 1-based position within the lifecycle (oldest = 1) |
| `is_excluded_lifecycle` | `True` on rows from old lifecycles superseded by a reused numero |
| `anomaly_flags` | List of flags: `MISSING_INDICE`, `OUT_OF_ORDER_INDICE`, `REUSED_NUMERO` |
| `version_confidence` | Float 0–1; reduced by 0.1 per MISSING_INDICE, 0.2 per OUT_OF_ORDER |
| `resolution_status` | `OK` / `AUTO_RESOLVED` / `REVIEW_REQUIRED` / `IGNORED` |
| `coarse_group_key` | String key of the coarse group `emetteur|lot_normalized|type_de_doc|numero_normalized` |
| `family_cluster_id` | UUID for the sub-cluster within a coarse group |
| `lifecycle_key` | `coarse_group_key::family_cluster_id[:8]` |

### Processing logic

1. **Coarse grouping** by `(emetteur, lot_normalized, type_de_doc, numero_normalized)`.
2. **Family clustering** within each coarse group by `lot_prefix` + `zone`/`niveau` match OR libelle Jaccard similarity ≥ 0.75 vs cluster representative.
3. **Lifecycle split detection** within each family cluster: if consecutive documents have similarity < 0.50 AND date gap > 180 days → split into separate lifecycles; older ones are tagged `REUSED_NUMERO` + `is_excluded_lifecycle = True`.
4. **Active lifecycle processing**: sort by `created_at`, detect missing/out-of-order indices, mark chronologically last row as `is_dernier_indice = True`.

**Flat GED equivalent:** None. The flat builder does not reconstruct version chains. It uses GED's own instance classification (`instance_role`: `ACTIVE` / `INACTIVE_DUPLICATE` / `SEPARATE_INSTANCE` / `INCOMPLETE_BUT_TRACKED`) to distinguish the current submission. The adapter must map flat GED's `instance_role = ACTIVE` as the proxy for `is_dernier_indice`, while accepting that the underlying computation differs.

---

## E. Workflow Engine Inputs — `workflow_engine.py`

### What `WorkflowEngine` consumes

`WorkflowEngine(responses_df)` takes the normalized responses DataFrame (exception approvers are filtered out in `__init__`). It pre-builds two internal lookup structures:

- `self._lookup: dict[(doc_id, approver_canonical), entry]` — best-state entry per (doc, approver) pair. Priority: ANSWERED > PENDING > NOT_CALLED. Within ANSWERED, most recent date wins.
- `self._doc_approvers: dict[doc_id, list[entry]]` — all per-approver best-state entries for each document.

### Methods consumed by the GF writer and discrepancy stages

| Method | Returns | Used for |
|---|---|---|
| `get_approver_status(doc_id, approver, gf_name_to_ged)` | `{date_answered, status_clean, date_status_type, comment}` | Filling per-approver cells in the GF output |
| `get_all_approver_statuses(doc_id)` | DataFrame (approver_canonical, date_answered, status_clean, date_status_type) | Full per-doc approver summary |
| `compute_visa_global_with_date(doc_id)` | `(visa_status: str\|None, visa_date: date\|None)` | VISA GLOBAL and Date réel de visa columns |
| `compute_global_state(doc_id)` | `{ALL_PRIMARY_DONE, MOEX_DONE, FULLY_COMPLETE, any_pending}` | Document-level completion flags |
| `compute_visa_global(doc_id)` | `visa_status: str\|None` | Convenience wrapper over `compute_visa_global_with_date` |
| `compute_responsible_party(engine, doc_ids)` | `{doc_id: responsible_party}` | Responsibility assignment (module-level function) |
| `compute_moex_countdown(engine, doc_ids, data_date)` | `{doc_id: countdown dict}` | MOEX 10-day countdown tracking |

### `compute_visa_global_with_date` business rules

- Finds the MOEX entry (approver matching `_is_moex()`: "MOEX", "GEMO", or "OEUVRE" in canonical name).
- Returns `(None, None)` if no MOEX entry, or MOEX is not `ANSWERED`.
- Status `VAO-SAS` / `VSO-SAS` → returns `(None, None)` (SAS-stage approval only, no final MOEX visa yet).
- Status `REF` from `approver_raw == "0-SAS"` → returns `("SAS REF", date)`.
- Status `REF` from full-workflow track → returns `("REF", date)`.
- All other ANSWERED MOEX statuses → returns `(status, date)` verbatim.

### `compute_responsible_party` rules (module-level, 5 rules)

1. visa == "REF" → "CONTRACTOR"
2. visa == "SAS REF" → "CONTRACTOR"
3. Any PENDING_IN_DELAY / PENDING_LATE consultants: if one → that approver's canonical name; if multiple → "MULTIPLE_CONSULTANTS"
4. No pending, visa is None → "MOEX"
5. No pending, visa exists and not REF → `None` (closed)

---

## F. Pipeline Stages

### `stage_read` (`pipeline/stages/stage_read.py`)

**Reads from context:** `ctx.GED_FILE`, `ctx.GF_FILE`, `ctx.RUN_MEMORY_DB`, `ctx.REPORT_MEMORY_DB`, `ctx.CONSULTANT_MATCH_REPORT`, `ctx.CONSULTANT_REPORTS_ROOT`, `ctx._run_number`.

**Writes to context:** `ctx.docs_df` (raw docs DataFrame), `ctx.responses_df` (raw responses DataFrame), `ctx.ged_approver_names` (list of raw approver header strings), `ctx.mapping` (hardcoded approver mapping dict).

Calls `read_ged()` (read_raw.py) then `load_mapping()` (normalize.py). Also registers all input files (GED export, GF file, report memory DB, consultant reports) into the run memory SQLite database.

### `stage_normalize` (`pipeline/stages/stage_normalize.py`)

**Reads from context:** `ctx.docs_df`, `ctx.responses_df`, `ctx.mapping`.

**Writes to context:** `ctx.docs_df` (mutated — normalized), `ctx.responses_df` (mutated — normalized + canonical approver names), `ctx.sas_filtered_df` (DataFrame of docs removed by SAS filter).

Calls `normalize_docs()`, `normalize_responses()`, then `_apply_sas_filter()`. After this stage, `ctx.docs_df` and `ctx.responses_df` are the cleaned, canonical forms consumed by all downstream stages.

### `stage_version` (`pipeline/stages/stage_version.py`)

**Reads from context:** `ctx.docs_df` (post-normalize).

**Writes to context:** `ctx.versioned_df` (full enriched DataFrame with version chain columns), `ctx.total` (row count), `ctx.dernier_count` (number of `is_dernier_indice == True` rows), `ctx.anomaly_count` (rows with non-empty `anomaly_flags`), `ctx.excluded_count` (rows with `is_excluded_lifecycle == True`).

Instantiates `VersionEngine(ctx.docs_df)` and calls `.run()`. This is the heaviest computation stage — it groups, clusters, detects splits, and reconstructs version chains across all documents.

---

## Gap Matrix

| Engine artifact | Source (file + function) | Flat GED equivalent | Gap |
|---|---|---|---|
| `is_dernier_indice` | `version_engine.py` / `VersionEngine._process_lifecycle()` — chronologically last row per lifecycle | `GED_OPERATIONS.instance_role = ACTIVE` | Both select the "current" submission, but by different methods. Old engine uses date-based lifecycle reconstruction + Jaccard similarity; flat builder uses GED's own instance classification. Adapter must use `instance_role` as the proxy. Downstream code that queries `is_dernier_indice == True` must be rewritten to filter `instance_role == ACTIVE`. |
| `lifecycle_id` / `chain_position` / `version_confidence` / `family_cluster_id` | `version_engine.py` / `VersionEngine.run()` — full version-chain reconstruction | Nothing in flat GED | Flat GED has no version-chain concept. These columns are produced entirely by the old version engine with no flat GED counterpart. Adapter must stub them (None / 0 / 1.0) or omit; downstream code that reads `lifecycle_id` for grouping must be assessed for impact. |
| `date_status_type` (4-state: NOT_CALLED / PENDING_IN_DELAY / PENDING_LATE / RAPPEL) | `normalize.py` / `interpret_date_field()` and `domain/sas_helpers.py` / `_build_sas_lookup()` | `GED_OPERATIONS.response_status_clean` (3-state: ABSENT / PENDING / ANSWERED) | Flat builder's PENDING collapses PENDING_IN_DELAY + PENDING_LATE + RAPPEL. Adapter cannot reconstruct PENDING sub-type from flat GED alone. `response_deadline` is available to infer lateness relative to `data_date`, but the "Rappel" distinction (whether a reminder was sent) is not preserved as a separate field. |
| `visa_global` / `visa_global_date` | `workflow_engine.py` / `compute_visa_global_with_date()` — derived from the MOEX approver entry | `GED_OPERATIONS.visa_global` + `GED_OPERATIONS.visa_date_global` (per Step 1 contract: MOEX GEMO column verbatim) | Direct pass-through — no gap. Both old engine and flat builder derive VISA GLOBAL from the MOEX column verbatim. The SAS REF / VAO-SAS exclusion rules must be verified to match, but conceptually aligned. |
| `responsible_party` (CONTRACTOR / approver / MULTIPLE_CONSULTANTS / MOEX / None) | `workflow_engine.py` / `compute_responsible_party()` — 5-rule decision tree | No single column in flat GED | Flat GED provides the ingredients (`is_blocking`, `is_completed`, `response_status_clean` per step/approver row). Adapter must reimplement the 5 `compute_responsible_party()` rules by iterating GED_OPERATIONS rows. This is a synthesize gap — logic, not data. |
| `sas_filtered_df` (docs removed: 0-SAS RAPPEL + `created_at` < 2026) | `domain/sas_helpers.py` / `_apply_sas_filter()`, called from `stage_normalize` | Not present in flat GED | Flat builder passes all documents through regardless of SAS state or creation year. If adapter does not apply the same filter post-load, the flat GED path will process ~N additional documents that the old path excludes. This changes document scope, not just field values. Adapter must apply the filter or explicitly accept scope difference. |
| `date_limite` (deadline date extracted from parenthesized `(YYYY/MM/DD)` in "Date réponse" text) | `normalize.py` / `interpret_date_field()` — embedded in the raw text field | `GED_OPERATIONS.response_deadline` (per Step 1 contract) | Direct mapping — flat builder already extracts this from the same source. No computation needed in adapter; `GED_OPERATIONS.response_deadline` maps directly to `date_limite`. |
| `approver_canonical` (from `_GED_APPROVER_MAPPING`, collapsing per-building prefixes to shared names) | `normalize.py` / `load_mapping()` + `map_approver()` | `GED_OPERATIONS.approver_canonical` / interlocutor column (per Step 1 contract) | Both systems normalize per-building-prefixed column names to canonical names. Canonical name strings may differ (e.g. old engine uses `"Maître d'Oeuvre EXE"`, flat builder may use a different label). Adapter must verify that all canonical name strings used in downstream GF column lookup match flat GED's output before Step 4. |
| `sas_reponse` per doc (best SAS result joined onto docs_df) | `normalize.py` / `enrich_docs_with_sas()` — joins 0-SAS response onto docs | `GED_OPERATIONS` rows where `approver = 0-SAS` (if present) | Flat GED exposes SAS as individual operation rows in GED_OPERATIONS, not as a pre-joined column on the doc. Adapter must either query GED_OPERATIONS to replicate `sas_reponse`, or pull it from the `_build_sas_lookup()` pattern. |

---

## Key Findings for Step 3b

1. **The version engine has no flat GED equivalent.** `is_dernier_indice` is the most-consumed output but the underlying computation is entirely absent from flat GED. The proxy (`instance_role = ACTIVE`) works for Phase 2 but carries the submission-instance limitation declared in the plan.

2. **`responsible_party` must be synthesized by the adapter.** It is not a flat GED field — it is a 5-rule computation over per-approver statuses. Step 4 must implement this logic in `stage_read_flat`.

3. **The SAS filter changes document scope, not just field values.** This must be an explicit adapter decision, not a silent omission.

4. **PENDING granularity is lost in flat GED.** If any downstream GF column or dashboard metric distinguishes PENDING_IN_DELAY from PENDING_LATE, it cannot be reproduced from flat GED without a new derivation using `response_deadline` vs `data_date`. Step 3b must assess whether any such distinction is operationally required.

5. **`visa_global` is the cleanest mapping** — both paths derive it from the MOEX column verbatim. Confirm canonical name match only.
