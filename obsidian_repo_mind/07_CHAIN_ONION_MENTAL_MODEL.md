#repo-map #chain-onion #portfolio-intelligence

# Chain+Onion Mental Model

> The portfolio intelligence layer built on top of pipeline outputs.
> Source: `README.md §Chain+Onion`, `context/00_PROJECT_MISSION.md`, `src/chain_onion/`.

---

## What it is

The Chain+Onion system is a **read-only analytical backend** stacked on top of the GED pipeline. It:
- Groups document families into **chains** (one logical file across all its versions and events)
- Scores each chain by operational impact through a six-layer **Onion** model
- Generates management narratives
- Exports a complete portfolio intelligence package

It does NOT modify any source data. It is invoked separately via `python run_chain_onion.py`.

---

## What a Chain is

A **chain** = the full lifecycle of one administrative file (`family_key = str(numero)`) across:
- All GED versions and indices
- Consultant report responses
- SAS decisions
- MOEX interventions

Every submitted/rejected/corrected/approved document version belongs to exactly one chain.

---

## The Onion (six-layer impact scoring)

Each chain is scored across six friction layers:

| Layer | Code | Theme | Score field |
|---|---|---|---|
| L1 | Contractor quality issues | Delay, dormancy, revisions | `contractor_impact_score` |
| L2 | SAS gate friction | SAS blocks, rejections | `sas_impact_score` |
| L3 | Primary consultant delay | Primary BET/bureau delay | `consultant_primary_impact_score` |
| L4 | Secondary consultant delay | Secondary BET delay | `consultant_secondary_impact_score` |
| L5 | MOEX arbitration delay | Arbitration slowdowns | `moex_impact_score` |
| L6 | Data / report contradiction | Conflict between GED and reports | `contradiction_impact_score` |

**Score formula (per layer):** `severity_weight × confidence_factor × pressure_factor × recency_factor × evidence_factor`

Layer scores sum to `total_onion_score` → normalized to `normalized_score_100` (0–100).

`action_priority_rank`: rank 1 = most operationally impacted chain.

---

## Module map — 10 steps

| Module | Step | Role |
|---|---|---|
| `source_loader.py` | 04 | Loads FLAT_GED, DEBUG_TRACE, report_memory. Identity model + exception logic |
| `family_grouper.py` | 05 | Groups all GED rows into families. Builds CHAIN_VERSIONS + CHAIN_REGISTER |
| `chain_builder.py` | 06 | Builds timeline events per family → CHAIN_EVENTS |
| `chain_classifier.py` | 07 | Assigns `current_state` + `portfolio_bucket` to each chain |
| `chain_metrics.py` | 08 | Computes `stale_days`, pressure index, activity dates → CHAIN_METRICS |
| `onion_engine.py` | 09 | Builds per-layer evidence rows → ONION_LAYERS |
| `onion_scoring.py` | 10 | Aggregates layer scores → chain-level ONION_SCORES |
| `narrative_engine.py` | 11 | Generates neutral management summaries → CHAIN_NARRATIVES |
| `exporter.py` | 12 | Exports 7 CSVs + 1 XLSX + 2 JSONs → `output/chain_onion/` |
| `query_hooks.py` | 13 | 26 query functions over `QueryContext` for UI/dashboard use |
| `validation_harness.py` | 14 | 40-check acceptance harness; returns `status ∈ {PASS, WARN, FAIL}` |

---

## Portfolio buckets

Every chain has exactly one `portfolio_bucket`:

| Bucket | Meaning | Terminal states |
|---|---|---|
| `LIVE_OPERATIONAL` | Active chains with open workflow steps | — |
| `LEGACY_BACKLOG` | Old open chains with no recent activity | — |
| `ARCHIVED_HISTORICAL` | Terminal chains | `CLOSED_VAO`, `CLOSED_VSO`, `VOID_CHAIN`, `DEAD_AT_SAS_A` |

---

## Output artifacts (`output/chain_onion/`)

| Artifact | Content |
|---|---|
| `CHAIN_REGISTER.csv` | One row per family — identity + state |
| `CHAIN_VERSIONS.csv` | All document versions per family |
| `CHAIN_EVENTS.csv` | Full event timeline per family |
| `CHAIN_METRICS.csv` | Pressure index, stale days, activity dates |
| `ONION_LAYERS.csv` | Per-layer evidence rows |
| `ONION_SCORES.csv` | Chain-level scores, ranks, escalation flags |
| `CHAIN_NARRATIVES.csv` | Management summaries with urgency/confidence labels |
| `dashboard_summary.json` | Portfolio KPI snapshot (totals, ratios, top theme) |
| `top_issues.json` | Top 20 chains by `action_priority_rank`; includes `emetteur_code`, `emetteur_name`, `titre` (Phase 4, 2026-05-01) |
| `CHAIN_ONION_SUMMARY.xlsx` | 11-sheet management workbook |

**Important:** these artifacts are NOT registered in `run_memory.db`. They are coupled to "the most recent run that wrote `output/intermediate/`", not to a specific run number.

---

## How the UI consumes Chain+Onion

The main JANSA UI consumes Chain+Onion **only** through:

1. `app.Api._build_live_operational_numeros()` → `query_hooks.get_live_operational(ctx)` → `live_numeros` set → Focus narrowing
2. `app.Api.get_chain_onion_intel(limit)` → reads `top_issues.json` + `dashboard_summary.json` → `window.CHAIN_INTEL` → ChainOnionPanel in overview.jsx
3. `chain_timeline_attribution.py` → reads `CHAIN_EVENTS.csv` + `CHAIN_REGISTER.csv` + `CHAIN_VERSIONS.csv` → produces `CHAIN_TIMELINE_ATTRIBUTION.json` → DCC Chronologie section

The other 24+ query functions (`get_top_issues`, `get_high_pressure`, `get_contractor_quality`, `get_sas_friction`, etc.) are available in Python but **not yet surfaced in the UI**.

### Consumers of `CHAIN_REGISTER.csv` (Phase 9, 2026-05-11)

Beyond chain_onion's own outputs and the three UI feeds above,
`CHAIN_REGISTER.csv` is now also consumed by the reporting context:

- `reporting.latest_chain_view.build_latest_chain_view(base_dir, docs_df=None)`
  is called by `data_loader._load_from_flat_artifacts` (and the parallel
  legacy path) to populate `ctx.latest_chain_df` (~2,554 rows). This is the
  canonical in-memory chain DataFrame.
- `reporting.latest_chain_view.latest_enriched_view(ctx)` then intersects
  `ctx.dernier_df` with `ctx.latest_chain_df.(numero, latest_indice)` to
  produce the operational view (~2,553 rows) used by every operational
  reporting module.

See `README.md §Phase 9` and [[05_REPORTING_AND_UI_ADAPTERS]] for the
full migration summary.

---

## Validation harness (Step 14)

```python
from src.chain_onion.validation_harness import run_chain_onion_validation
report = run_chain_onion_validation(output_dir="output/chain_onion")
print(report["status"])  # PASS / WARN / FAIL
```

40 checks across 8 categories. WARN thresholds (not FAIL):
- `dormant_ghost_ratio > 0.50`
- Escalated chains > 25% of live chains (H38 — pre-existing as of 2026-05-01)
- Zero-score chains > 40% of all chains
- Contradiction rows > 10% of all chains

---

## Key invariant: `doc_id` must NOT be persisted

`source_loader.py` (step 04) is explicit: `doc_id` (UUID) is session-scoped and must NEVER be persisted to chain output CSVs. Identity joins between pipeline outputs and chain outputs must use `(numero, indice)` or `family_key = str(numero)`.

---

## Chain Timeline Attribution (DCC bridge module)

`src/reporting/chain_timeline_attribution.py` sits between chain_onion and the DCC. It:
- Reads `CHAIN_EVENTS.csv`, `CHAIN_REGISTER.csv`, `CHAIN_VERSIONS.csv`
- Applies the **10-day secondary consultant delay cap** (raw chain_onion does NOT enforce this)
- Produces `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.{json,csv}`
- Is refreshed at app startup by `_ensure_chain_data_fresh()`

This module is in `src/reporting/` (not `src/chain_onion/`) because it's a reporting composition layer, not a chain builder.

---

**Related:** [[04_PIPELINE_STAGES]] · [[05_REPORTING_AND_UI_ADAPTERS]] · [[08_DOCUMENT_COMMAND_CENTER]] · [[09_ACTION_MOEX_COUNTER_ATTACK]] · [[14_MODULE_INDEX]]

*Back to [[00_START_HERE]]*
