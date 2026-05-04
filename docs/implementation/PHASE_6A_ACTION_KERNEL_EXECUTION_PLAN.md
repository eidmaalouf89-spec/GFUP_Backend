# Phase 6A — Action Kernel Execution Plan (DEFINITIVE)

**Location:** `docs/implementation/PHASE_6A_ACTION_KERNEL_EXECUTION_PLAN.md`
**Status:** APPROVED PLAN — implementation patch NOT YET AUTHORIZED.
**Supersedes:** `docs/implementation/PHASE_6A_DRAFT.md` (deleted on plan approval).
**Master plan:** `docs/implementation/PHASE_6_COUNTER_ATTACK_MASTER.md`
**Protocol:** `docs/implementation/READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md`

---

## 0. Scope and Approval State

This document is the frozen, product-approved plan for Phase 6A of the Counter-Attack Intelligence initiative. It captures every decision needed to implement `output/intermediate/COUNTER_ATTACK_ITEMS.csv` without further architectural debate.

**Scope:** plan only. No code, no module modifications, no context inventory updates yet.

**Implementation status:** NOT AUTHORIZED. Implementation requires a separate approval gate (§14). The implementation patch will: add one additive function to DCC, create `src/reporting/counter_attack_builder.py`, create `scripts/build_counter_attack.py`, and produce `output/intermediate/COUNTER_ATTACK_ITEMS.csv`. Context inventory updates (§13) happen during/after the implementation patch, not now.

**Out of scope for 6A:** UI, API, run_memory schema, pipeline stage integration, dossier artifacts, rich subject taxonomy.

---

## 1. Architectural Principle

Phase 6A is a **read-only consumer** that builds a single deterministic artifact by reusing existing repo intelligence. It must not create a parallel system.

The hierarchy of source-of-truth is:

1. **Document Command Center (DCC)** — primary source for per-document operational tags. DCC reuses `focus_ownership`, `moex_countdown`, and chain timeline upstream. Phase 6A reuses DCC's tag computation in bulk.
2. **chain_onion artifacts** — fallback source for buckets DCC doesn't directly express (`MOEX_SHAME_INTERNAL`, `SUJET_REUNION`) and for join-only enrichment columns (scores, narratives, family_key).
3. **`responses_df` / `effective_responses`** — evidence source for observations and consultant report enrichment. Already composed by `effective_responses.py` and exposed on `ctx.responses_df`.

Forbidden: recomputing ownership, recomputing tags, introducing new mapping logic, creating new DBs, modifying any existing artifact contract, modifying focus_ownership, modifying chain_onion logic, modifying UI/API, or modifying run_memory schema.

---

## 2. Output Contract: `COUNTER_ATTACK_ITEMS.csv`

**Path:** `output/intermediate/COUNTER_ATTACK_ITEMS.csv`
**Granularity:** one row per `(numero, latest_indice)` for actionable rows (`focus_owner_tier ≠ "CLOSED"`).
**Total columns:** 28 — 21 original + 7 evidence.

### 2.1 Original 21 columns (in order)

| # | Column | Type | Description |
|---|---|---|---|
| 1 | `item_id` | str | Stable composite `f"{family_key}__{latest_indice}"`. |
| 2 | `numero` | str | Document number from `dernier_df.numero`. |
| 3 | `indice` | str | Latest indice from `dernier_df.indice`. |
| 4 | `family_key` | str | From `CHAIN_REGISTER.family_key` (joined on `numero`). |
| 5 | `subject_label` | str | `f"{lot} / {titre}"`; falls back to `titre` if `lot` is empty. |
| 6 | `emetteur_code` | str | **`dernier_df.emetteur` directly.** No slug. No mapping lookup. Empty stays empty. |
| 7 | `emetteur_name` | str | `resolve_emetteur_name(emetteur_code)` from `src/reporting/contractor_fiche.py`. Same resolver chain_onion exporter uses. |
| 8 | `primary_actor` | str | From `CHAIN_TIMELINE_ATTRIBUTION.csv`: filter `numero=this`, `indice=latest_indice`, `is_open=True`, pick max `attributed_days`. Fallback `ONION_SCORES.top_layer_name`. Empty if neither resolves. |
| 9 | `actor_to_call` | str | Per-bucket assignment (see §4 column "actor_to_call"). |
| 10 | `action_bucket` | str | One of seven enum values (see §4). First-match-wins. |
| 11 | `action_label` | str | Static French label per bucket (see §4). |
| 12 | `plain_reason` | str | Per-bucket template + `CHAIN_NARRATIVES.primary_driver_text` (see §4). |
| 13 | `recommended_action` | str | Static template per bucket (see §4). |
| 14 | `risk_level` | str | `CHAIN_NARRATIVES.urgency_label`. Values: `CRITICAL` / `HIGH` / `MEDIUM` / `LOW`. |
| 15 | `evidence_summary` | str | `CHAIN_NARRATIVES.executive_summary` + ` | ` + `operational_note` (if present). Truncate ~500 chars. |
| 16 | `days_open` | int | `CHAIN_METRICS.open_days`. |
| 17 | `days_late` | int | `CHAIN_METRICS.stale_days`. |
| 18 | `current_state` | str | `CHAIN_REGISTER.current_state`. Surfaced for transparency and used in bucket predicates. |
| 19 | `normalized_score_100` | float | `ONION_SCORES.normalized_score_100`. |
| 20 | `is_internal_moex_exposure` | bool | `top_layer_code == "L5_MOEX_ARBITRATION_DELAY"` OR (`escalation_flag == True` AND DCC primary tag indicates MOEX-owned). |
| 21 | `is_external_attackable` | bool | `top_layer_code ∈ {"L1_CONTRACTOR_QUALITY", "L3_PRIMARY_CONSULTANT_DELAY", "L4_SECONDARY_CONSULTANT_DELAY"}`. |

### 2.2 New 7 evidence columns (in order)

| # | Column | Type | Description |
|---|---|---|---|
| 22 | `chain_observations_summary` | str | Concat of last ≤5 non-empty observations across all indices, formatted `"[indice reviewer] comment"`, hard-capped at 1000 chars. |
| 23 | `chain_observations_full` | str (JSON) | JSON array of all non-empty observations across all indices: `[{indice, reviewer, status, comment}, ...]` sorted by `(indice, reviewer)`. |
| 24 | `chain_observations_refs` | str (JSON) | JSON array of `[numero, indice, reviewer]` keys for traceability. |
| 25 | `consultant_reports_summary` | str | Concat of last ≤5 enriched-row comments, formatted `"[indice reviewer <effective_source>] comment"`, hard-capped at 1000 chars. |
| 26 | `consultant_reports_full` | str (JSON) | JSON array of all enriched rows: `[{indice, reviewer, status, comment, effective_source}, ...]`. |
| 27 | `consultant_reports_refs` | str (JSON) | JSON array of `[numero, indice, reviewer, effective_source]` keys. |
| 28 | `consultant_reports_available` | bool | `True` if at least one row in `responses_df` for this numero has `effective_source` in the report-enriched set (§7). |

**Evidence rule (binding):** observations and consultant reports are evidence/enrichment only. They MUST NOT change `action_bucket`, ownership, score, internal exposure, or external attackability. Bucket assignment uses DCC tags and chain/onion fallbacks only.

---

## 3. Input Sources

### 3.1 In-memory (via `ctx`)

| Source | Field | Used for |
|---|---|---|
| `ctx.dernier_df` | `numero, indice, doc_id, emetteur, libelle_du_document, lot, _focus_owner_tier, _visa_global` | Row enumeration; primary tag input to DCC bulk. |
| `ctx.docs_df` | `doc_id, numero, indice` | Per-numero indice history for evidence collection. |
| `ctx.responses_df` (== `effective_responses_df`) | `doc_id, approver_canonical, status_clean, response_comment, effective_source, date_answered, date_status_type, date_limite` | DCC tag inputs + observations + consultant reports. |
| `ctx.moex_countdown` | `{doc_id: {countdown_expired, ...}}` | Already consumed by DCC `_compute_secondary_tags`; no direct use. |
| `ctx.data_date` | `date` | Already consumed by DCC; no direct use. |

### 3.2 On-disk artifacts (read by builder)

| Path | Columns read |
|---|---|
| `output/chain_onion/CHAIN_REGISTER.csv` | `numero, family_key, current_state, stale_days, current_blocking_actor_count` |
| `output/chain_onion/CHAIN_METRICS.csv` | `numero, open_days, stale_days` |
| `output/chain_onion/ONION_SCORES.csv` | `numero, normalized_score_100, top_layer_code, top_layer_name, escalation_flag, escalation_reason` |
| `output/chain_onion/CHAIN_NARRATIVES.csv` | `numero, urgency_label, executive_summary, primary_driver_text, operational_note` |
| `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv` | `numero, indice, is_open, attributed_to_actor, attributed_to_tier, attributed_days` |

### 3.3 Modules read

| Module | Symbols reused |
|---|---|
| `src/reporting/document_command_center.py` | private helpers `_get_latest_responses_for_doc`, `_compute_days_since_moex_ref`, `_compute_primary_tag`, `_compute_secondary_tags`; same `_CHAIN_TIMELINE_DIR` constant. |
| `src/reporting/contractor_fiche.py` | `resolve_emetteur_name(code)`. |
| `src/reporting/chain_timeline_attribution.py` | `load_chain_timeline_artifact(_CHAIN_TIMELINE_DIR)`. |
| `src/reporting/data_loader.py` | `get_run_context(...)` for the standalone script. |

No other modules are read or modified.

---

## 4. Bucket Rules (first-match-wins, 7 buckets)

Pre-filter: actionable rows only (`focus_owner_tier != "CLOSED"`, equivalently DCC primary tag != `"Clos / Visé"`).

| Pri | `action_bucket` (enum) | `action_label` (user-facing FR) | Predicate | `actor_to_call` | `plain_reason` template | `recommended_action` template |
|---|---|---|---|---|---|---|
| 1 | `MOEX_SHAME_INTERNAL` | **MOEX interne — exposition à traiter** | `current_state == "CHRONIC_REF_CHAIN"` **OR** (DCC primary ∈ {`Att MOEX — Facile`, `Att MOEX — Arbitrage`} AND `top_layer_code == "L5_MOEX_ARBITRATION_DELAY"` AND `stale_days > 30`) | `"MOEX"` | `"Cette chaîne expose MOEX en interne depuis {stale_days} jours. {primary_driver_text}"` | `"Décision MOEX requise immédiatement; remettre le sujet à l'ordre du jour interne."` |
| 2 | `SECONDAIRE_EXPIRE` | Secondaire expiré — décision MOEX requise | DCC secondary tags contain `"Secondaire expiré"` | `"MOEX"` | `"Le BET secondaire n'a pas répondu dans la fenêtre. {primary_driver_text}"` | `"MOEX doit reprendre la main et émettre/arbitrer le visa."` |
| 3 | `DECISION_MOEX` | Décision MOEX — arbitrage requis | DCC primary tag == `"Att MOEX — Arbitrage"` | `"MOEX"` | `"Plusieurs avis bloquants sur l'indice courant. MOEX doit arbitrer. {primary_driver_text}"` | `"MOEX doit trancher entre les avis BET avant émission du visa."` |
| 4 | `FERMER_MAINTENANT` | À fermer maintenant | DCC primary tag == `"Att MOEX — Facile"` | `"MOEX"` | `"Tous les avis sont disponibles. MOEX doit émettre le visa."` | `"Émettre le visa global maintenant."` |
| 5 | `ENTREPRISE_A_RELANCER` | Entreprise à relancer | DCC primary tag ∈ {`Att Entreprise — Dans les délais`, `Att Entreprise — Hors délais`} | `emetteur_name` (the contractor) | `"L'entreprise doit resoumettre après refus MOEX. Bloqué depuis {stale_days} jours."` | `"Relancer {emetteur_name} pour resoumission de l'indice corrigé."` |
| 6 | `CONSULTANT_A_ATTAQUER` | Consultant à attaquer | DCC primary tag ∈ {`Att BET Primaire`, `Att BET Secondaire`} | `primary_actor` | `"En attente de {primary_actor} depuis {days_late} jours."` | `"Relancer {primary_actor}; escalader si pas de réponse sous 5 jours."` |
| 7 | `SUJET_REUNION` | Sujet réunion critique | `escalation_flag == True` AND `urgency_label ∈ {"CRITICAL", "HIGH"}` AND not matched above | `"MOEX"` | `"Sujet à escalader en réunion. {executive_summary}"` | `"Mettre à l'ordre du jour de la prochaine réunion de chantier."` |

### 4.1 Label rule

- The internal enum `MOEX_SHAME_INTERNAL` is preserved.
- The user-facing label is `"MOEX interne — exposition à traiter"`.
- The label `"Honte MOEX interne"` is **forbidden** anywhere in code, output, or documentation.

### 4.2 Bucket registry guarantee

The artifact's bucket distribution always references all 7 buckets. A bucket may have zero rows for a given run; the implementation report will document any zero-count bucket with a one-line explanation.

---

## 5. Function: `compute_dcc_tags_bulk(ctx)` — additive to DCC

**Location (future implementation):** appended to `src/reporting/document_command_center.py` as a new public function. No existing DCC function or constant is modified.

**Signature:**

```python
def compute_dcc_tags_bulk(ctx) -> pd.DataFrame:
    """Bulk variant of DCC tag computation, reusing DCC private helpers.

    Returns one row per latest-indice document with columns:
        doc_id, numero, indice, emetteur, libelle_du_document, lot,
        focus_owner_tier, primary_tag, secondary_tags,
        days_since_moex_ref, blocking_bet_count, countdown_expired, visa_global

    - Loads chain timeline ONCE via load_chain_timeline_artifact(_CHAIN_TIMELINE_DIR).
    - Iterates ctx.dernier_df rows, calling the existing private helpers:
        _get_latest_responses_for_doc(ctx, doc_row)
        _compute_days_since_moex_ref(ctx, latest_responses)
        _compute_primary_tag(focus_owner_tier, latest_responses, days_since_moex_ref)
        _compute_secondary_tags(ctx, doc_row, latest_responses, chain_timeline.get(numero))
    - Does NOT mutate ctx.
    - Does NOT recompute ownership.
    - Does NOT introduce new tag rules.
    - Returns an empty DataFrame in degraded mode.
    """
```

**Reuse contract:** every tag value produced by `compute_dcc_tags_bulk` for a given `(numero, indice)` is byte-for-byte identical to the corresponding fields returned by `build_document_command_center(ctx, numero, indice)`. This is a validation requirement (§9, check c).

**Rationale:** the only mechanical difference between bulk and per-doc is the location of the chain_timeline load (once at the top vs. once per call). Both call paths use the same private helpers, the same `_CHAIN_TIMELINE_DIR`, and the same `ctx`.

---

## 6. Builder: `src/reporting/counter_attack_builder.py` — to be created

**Public entry point:**

```python
def build_counter_attack_items(ctx, output_dir: Path) -> Path:
    """Phase 6A artifact builder. Returns path to written CSV."""
```

**Algorithm (sequential, deterministic):**

```
1. dcc_df = compute_dcc_tags_bulk(ctx)
2. actionable = dcc_df[dcc_df.focus_owner_tier != "CLOSED"].copy()
3. Load CHAIN_REGISTER, CHAIN_METRICS, ONION_SCORES, CHAIN_NARRATIVES,
   CHAIN_TIMELINE_ATTRIBUTION from output_dir.
4. Merge actionable ← chain artifacts on `numero` (left joins).
   Resolve column-name collisions (e.g. stale_days appears in both
   CHAIN_REGISTER and CHAIN_METRICS; keep CHAIN_METRICS as the
   authoritative time-based field, suffix the other).
5. For each row, call _assign_bucket(row) (first-match-wins, 7 buckets).
6. For each row, derive:
       item_id, subject_label, emetteur_code, emetteur_name,
       primary_actor, actor_to_call, action_label, plain_reason,
       recommended_action, risk_level, evidence_summary, days_open,
       days_late, is_internal_moex_exposure, is_external_attackable.
7. For each numero, build evidence columns (§7, §8).
8. Reorder columns to the canonical 28-column order (§2).
9. Write CSV with utf-8, no index.
10. Return the written Path.
```

**Private helpers (single-use, kept inside this module):**

```
_assign_bucket(row) -> str
_collect_observations(numero, docs_df, responses_df) -> dict
_collect_consultant_reports(numero, docs_df, responses_df) -> dict
_build_item_id(family_key, latest_indice) -> str
_build_subject_label(lot, titre) -> str
_pick_primary_actor(numero, latest_indice, attribution_df, top_layer_name) -> str
_pick_actor_to_call(bucket, row) -> str
_build_plain_reason(bucket, narrative_row, metrics_row) -> str
_build_recommended_action(bucket, actor_to_call, emetteur_name, primary_actor) -> str
_compute_internal_moex_exposure(row) -> bool
_compute_external_attackable(row) -> bool
```

**No `_slug` helper. No Mapping.xlsx lookup. `emetteur_code` is `dernier_df.emetteur` verbatim; if empty, both `emetteur_code` and `emetteur_name` remain empty.**

---

## 7. Evidence Collection — Observations Across All Indices

For each `numero` in the actionable set:

```
doc_ids = ctx.docs_df.loc[ctx.docs_df.numero == numero, "doc_id"].tolist()
doc_id_to_indice = dict(
    ctx.docs_df.loc[ctx.docs_df.numero == numero, ["doc_id", "indice"]].values
)
resp = ctx.responses_df[ctx.responses_df.doc_id.isin(doc_ids)]

records = []
for _, r in resp.iterrows():
    comment = str(r.get("response_comment") or "").strip()
    if not comment or comment.lower() == "nan":
        continue
    records.append({
        "indice":   doc_id_to_indice[r.doc_id],
        "reviewer": r.approver_canonical,
        "status":   r.status_clean,
        "comment":  comment,
    })

records.sort(key=lambda x: (x["indice"], x["reviewer"]))

chain_observations_summary = " | ".join(
    f"[{r['indice']} {r['reviewer']}] {r['comment'][:160]}"
    for r in records[-5:]
)[:1000]
chain_observations_full = json.dumps(records, ensure_ascii=False)
chain_observations_refs = json.dumps(
    [[numero, r["indice"], r["reviewer"]] for r in records],
    ensure_ascii=False,
)
```

This guarantees observations from previous indices are included, not only the latest indice.

---

## 8. Evidence Collection — Consultant Reports via `effective_source`

The composed `responses_df` (== `effective_responses_df`) carries the `effective_source` controlled vocabulary defined in `src/effective_responses.py`. The report-enriched values are:

```
REPORT_SOURCES = {
    "GED+REPORT_STATUS",
    "GED+REPORT_COMMENT",
    "GED_CONFLICT_REPORT",
}
```

For each `numero`:

```
enriched = resp[resp.effective_source.isin(REPORT_SOURCES)]
consultant_reports_available = bool(len(enriched))

records = []
for _, r in enriched.iterrows():
    records.append({
        "indice":           doc_id_to_indice[r.doc_id],
        "reviewer":         r.approver_canonical,
        "status":           r.status_clean,
        "comment":          str(r.get("response_comment") or "").strip(),
        "effective_source": r.effective_source,
    })
records.sort(key=lambda x: (x["indice"], x["reviewer"]))

consultant_reports_summary = " | ".join(
    f"[{r['indice']} {r['reviewer']} <{r['effective_source']}>] {r['comment'][:120]}"
    for r in records[-5:]
)[:1000]
consultant_reports_full = json.dumps(records, ensure_ascii=False)
consultant_reports_refs = json.dumps(
    [[numero, r["indice"], r["reviewer"], r["effective_source"]] for r in records],
    ensure_ascii=False,
)
```

**Safety:** if `effective_source` is missing from `ctx.responses_df` (legacy non-flat fallback), all consultant_reports_* columns default to empty string / `False` for every row. No exception. No fabricated data.

---

## 9. Validation Plan (to be executed AFTER implementation)

These commands are part of the future implementation patch. They are listed here for the implementation phase only and must NOT be run during plan finalization.

```bash
# (a) Smoke import of the modified DCC module
python -c "from src.reporting.document_command_center import build_document_command_center, compute_dcc_tags_bulk; print('ok')"

# (b) Existing DCC behavior unchanged for one numero
python -c "
from src.reporting.data_loader import get_run_context
from src.reporting.document_command_center import build_document_command_center
ctx = get_run_context()
sample_num = ctx.dernier_df['numero'].iloc[0]
out = build_document_command_center(ctx, sample_num)
print(out['header']['primary_tag'], out['tags']['secondary'])
"

# (c) Bulk vs per-doc parity (5 random rows must produce identical primary_tag and secondary_tags)
# (throwaway script run during validation; not a permanent test file)

# (d) Build the artifact
python scripts/build_counter_attack.py

# (e) Schema check
python -c "
import pandas as pd
df = pd.read_csv('output/intermediate/COUNTER_ATTACK_ITEMS.csv')
assert len(df.columns) == 28, df.columns
print('rows:', len(df), 'cols:', len(df.columns))
print(df['action_bucket'].value_counts(dropna=False))
"

# (f) SECONDAIRE_EXPIRE rows match DCC tag
python -c "
import pandas as pd
from src.reporting.data_loader import get_run_context
from src.reporting.document_command_center import build_document_command_center
ctx = get_run_context()
df = pd.read_csv('output/intermediate/COUNTER_ATTACK_ITEMS.csv')
sub = df[df.action_bucket=='SECONDAIRE_EXPIRE'].head(3)
for _, r in sub.iterrows():
    panel = build_document_command_center(ctx, r['numero'], r['indice'])
    assert 'Secondaire expiré' in panel['tags']['secondary']
print('parity OK')
"

# (g) Observations include previous indices
python -c "
import pandas as pd, json
df = pd.read_csv('output/intermediate/COUNTER_ATTACK_ITEMS.csv')
multi = sum(
    1 for _, r in df.head(50).iterrows()
    if len({x['indice'] for x in json.loads(r['chain_observations_full'] or '[]')}) > 1
)
print('rows with multi-indice observations (out of 50):', multi)
"

# (h) Consultant report fields populate when reports exist; safe when absent
python -c "
import pandas as pd, json
df = pd.read_csv('output/intermediate/COUNTER_ATTACK_ITEMS.csv')
have = df[df.consultant_reports_available==True].head(3)
none = df[df.consultant_reports_available==False].head(3)
for _, r in have.iterrows():
    recs = json.loads(r['consultant_reports_full'])
    assert recs and all(x['effective_source'] in
        {'GED+REPORT_STATUS','GED+REPORT_COMMENT','GED_CONFLICT_REPORT'} for x in recs)
for _, r in none.iterrows():
    val = r['consultant_reports_full']
    assert (val in ('[]','', None)) or pd.isna(val)
print('consultant report parity OK')
"

# (i) Forbidden label not present
python -c "
import pandas as pd
df = pd.read_csv('output/intermediate/COUNTER_ATTACK_ITEMS.csv')
assert not df['action_label'].astype(str).str.contains('Honte MOEX').any()
print('label rule OK')
"

# (j) Scope of changes
git status --short output/
# Expected: only output/intermediate/COUNTER_ATTACK_ITEMS.csv is new; nothing else modified.

git diff --stat
# Expected:
#   src/reporting/document_command_center.py | <small> + 0 -
#   src/reporting/counter_attack_builder.py  | NEW
#   scripts/build_counter_attack.py          | NEW (small)
```

---

## 10. Risk Classification

**Risk: HIGH.**

Reasons:
- Adds a new artifact `COUNTER_ATTACK_ITEMS.csv` to `output/intermediate/`. Future Phase 6B/6C consumers will treat its 28-column contract as authoritative.
- Modifies `src/reporting/document_command_center.py`, a load-bearing module. Modification is strictly additive (one new public function), with a parity validation gate (§9 check c).

The implementation patch will require explicit user approval before execution per `READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md`.

---

## 11. File Impact (planned for the future implementation patch)

```
READ:
  src/reporting/document_command_center.py
  src/reporting/focus_ownership.py            (read-only; relied on via dernier_df._focus_owner_tier)
  src/reporting/data_loader.py
  src/reporting/chain_timeline_attribution.py
  src/reporting/contractor_fiche.py           (resolve_emetteur_name)
  src/effective_responses.py                  (vocabulary constants)
  output/chain_onion/CHAIN_REGISTER.csv
  output/chain_onion/CHAIN_METRICS.csv
  output/chain_onion/ONION_SCORES.csv
  output/chain_onion/CHAIN_NARRATIVES.csv
  output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv

MODIFY:
  src/reporting/document_command_center.py    (additive only: compute_dcc_tags_bulk)

CREATE:
  src/reporting/counter_attack_builder.py
  scripts/build_counter_attack.py
  output/intermediate/COUNTER_ATTACK_ITEMS.csv

DO NOT TOUCH:
  src/reporting/focus_ownership.py
  src/chain_onion/**                          (any logic change forbidden)
  ui/**
  src/api_v2/**
  src/pipeline/**                             (no new stage in 6A)
  any existing artifact contract
  existing DCC tag behavior
```

---

## 12. CLI Integration

**Approved: C1 — standalone script** at `scripts/build_counter_attack.py`.

```python
# pseudocode for the future script
from pathlib import Path
from src.reporting.data_loader import get_run_context
from src.reporting.counter_attack_builder import build_counter_attack_items

def main():
    ctx = get_run_context()
    out = Path("output/intermediate")
    path = build_counter_attack_items(ctx, out)
    print(f"wrote: {path}")

if __name__ == "__main__":
    main()
```

**Rejected/deferred: C2 — new pipeline stage.** No pipeline orchestration change in 6A. Pipeline integration is reconsidered after the artifact is validated and consumers (6B/6C) exist.

---

## 13. Context Inventory Updates (deferred to implementation patch)

The following `/context` updates will occur **during/after the implementation patch**, not in this plan:

```
context/04_PIPELINE_STAGES.md       — append note that COUNTER_ATTACK_ITEMS.csv
                                      is built by a standalone script (C1), not a stage.
context/05_OUTPUT_ARTIFACTS.md      — add COUNTER_ATTACK_ITEMS.csv with column list
                                      and bucket enum.
context/artifact_inventory.csv      — add row for COUNTER_ATTACK_ITEMS.csv.
```

These are not touched in the plan-finalization step.

---

## 14. Implementation Approval Gate

Implementation of this plan requires a fresh approval. The implementation patch will:

1. Re-state this plan's scope.
2. Add `compute_dcc_tags_bulk` to `document_command_center.py`.
3. Create `counter_attack_builder.py`.
4. Create `scripts/build_counter_attack.py`.
5. Run the validation suite in §9.
6. Update the three `/context` files in §13.
7. Return the result package below.

The implementation patch must NOT begin until the user issues an explicit "implement now" approval referring to this plan.

---

## 15. Expected Implementation Result Package

When the implementation patch is approved and executed, the return will include:

1. **Modified/created files** — one-line diff summary per file, confirming `git diff --stat` matches §11 exactly.
2. **Validation log** — pass/fail for each command in §9 (a–j).
3. **Bucket distribution** — counts per `action_bucket` from the produced artifact, with one-line explanation for any zero-count bucket.
4. **DCC parity confirmation** — sample of N rows showing `compute_dcc_tags_bulk` produces identical `primary_tag` / `secondary_tags` to `build_document_command_center`.
5. **Evidence sample** — 3 rows showing previous-indice observations are included; 3 rows showing `consultant_reports_*` populated when `consultant_reports_available == True`, empty when `False`.
6. **Context doc diffs** — for `04_PIPELINE_STAGES.md`, `05_OUTPUT_ARTIFACTS.md`, `artifact_inventory.csv`.
7. **Confirmation that no forbidden file was modified** — explicit list from the DO NOT TOUCH set in §11.

---

## 16. End of Plan

This document is the single source of truth for Phase 6A. Older Phase 6A drafts are deleted. Any deviation from this plan during implementation requires a new approval round — silent expansion of scope is forbidden per project rules.
