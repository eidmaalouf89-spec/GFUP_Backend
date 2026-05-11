#repo-map #debugging #protocol #safety

# Safe Debugging Protocol

> A practical checklist for investigating accuracy issues or unexpected behavior.
> Source: `context/09_PROMPT_PROTOCOL.md`, `context/11_TOOLING_HAZARDS.md`, `context/08_DO_NOT_TOUCH.md`.

---

## The golden rule

> **One issue per chat. Diagnose before patching. Propose before applying.**

Never start patching until you have read the relevant source files, traced the data path, and confirmed the exact seam where the value diverges.

---

## Pre-investigation checklist

Before touching any code:

- [ ] **Read, don't bash.** Use the `Read` tool for file content — not `grep`, `cat`, `wc`. The Linux sandbox mount can serve stale views of Windows-mounted source files (`context/11_TOOLING_HAZARDS.md §H-1`).
- [ ] **Do not declare files broken** from bash-only evidence. If `grep` or `wc` says a function is missing, verify with `Read` before concluding.
- [ ] **Do not raise "DB corrupt" alarms** from sandbox SQLite reads — the FUSE mount can make a healthy DB look malformed (`context/11_TOOLING_HAZARDS.md §H-7`).
- [ ] **Do not re-run the pipeline** during an investigation unless you intend to. Pipeline runs mutate `data/run_memory.db`, `data/report_memory.db`, and `runs/`.

---

## Step-by-step investigation flow

### Step 1 — Locate the symptom layer

What kind of issue?

| Symptom | Start here |
|---|---|
| Wrong number in UI | [[02_SOURCE_OF_TRUTH_HIERARCHY]] — trace from UI layer down |
| Wrong document in report | [[04_PIPELINE_STAGES]] — check stage_discrepancy / stage_route |
| Focus/chain list wrong | [[07_CHAIN_ONION_MENTAL_MODEL]] — check ONION_SCORES.csv, query_hooks |
| DCC showing wrong tags/data | [[08_DOCUMENT_COMMAND_CENTER]] — backend is sole tag logic source |
| Action MOEX showing wrong buckets | [[09_ACTION_MOEX_COUNTER_ATTACK]] — check COUNTER_ATTACK_ITEMS.csv |
| Consultant data wrong | Check effective_responses_df composition + report_memory ingestion |

---

### Step 2 — Run the cross-layer audit

```bash
python scripts/audit_counts_lineage.py
```

This compares L0_RAW_GED → L1_FLAT_GED → L2_STAGE_READ_FLAT → L3_RUNCONTEXT_CACHE → L4_AGGREGATOR → L5_UI_ADAPTER → L6_CHAIN_ONION.

Healthy output looks like:
```
AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match
```

The persistent FAIL is the known D-011 SAS REF projection gap (upstream, do-not-touch). Any new FAIL or WARN is worth investigating.

---

### Step 3 — Check the pickle cache

If a number changed unexpectedly (or didn't change when it should have):

```bash
rm -f output/intermediate/FLAT_GED_cache_docs.pkl \
      output/intermediate/FLAT_GED_cache_resp.pkl \
      output/intermediate/FLAT_GED_cache_meta.json
```

Next `load_run_context` will rebuild from `FLAT_GED.xlsx` (~30s one-time cost). If the number changes, the cache was stale.

---

### Step 4 — Compare composed truth vs artifact vs UI payload

For a specific metric (e.g. `visa_global` for document `045080/B`):

1. **Artifact truth:** Read `output/intermediate/FLAT_GED.xlsx` GED_OPERATIONS sheet
2. **Composed truth:** `ctx.flat_ged_doc_meta` (authoritative for `visa_global`)
3. **WorkflowEngine:** `ctx.workflow_engine.compute_visa_global_with_date(...)` (may differ from meta)
4. **Aggregator output:** `compute_project_kpis(ctx)` — does the KPI use the right source?
5. **UI adapter output:** `adapt_overview(...)` — is the field passed through?
6. **UI global:** `window.OVERVIEW[field]` in browser devtools

If they diverge at a specific layer, the bug is at that transition.

---

### Step 5 — Check identity dtypes in joins

If a join returns 0 results unexpectedly:

```python
# Check the dtype of identity columns
print(df["family_key"].dtype)  # should be object (string)
print(df["numero"].dtype)      # should be object (string)

# Leading zeros check
print(df["numero"].head())     # should be "045080", not 45080
```

Force string dtype when reading CSVs:
```python
pd.read_csv(path, dtype={"family_key": str, "numero": str, "version_key": str})
```

---

### Step 6 — Check WorkflowEngine vs RunContext responses_df

For any SAS-related metric:

```python
print(len(ctx.responses_df))             # FULL — includes SAS rows
print(len(ctx.workflow_engine.responses_df))  # FILTERED — no SAS rows

sas_count = (ctx.responses_df["approver_raw"] == "0-SAS").sum()
print(f"SAS rows in full frame: {sas_count}")
```

If the consumer is using `ctx.workflow_engine.responses_df` for SAS analytics, that's the bug. Switch to `ctx.responses_df`.

---

### Step 7 — Compile before running

Before any code change, verify the file compiles:
```bash
python -m py_compile src/reporting/aggregator.py
python -m py_compile app.py
```

Do NOT use `wc -l` or `tail` to verify file state — use the `Read` tool.

---

## Validation evidence requirements

**Every patch must include validation evidence:**

For UI metric fixes:
```bash
python scripts/audit_counts_lineage.py
# → paste AUDIT one-liner + UI_PAYLOAD one-liner
```

For pipeline changes:
```bash
# Must validate against docs/VALIDATION_BASELINE.md numbers:
# docs_total=6491, responses_total=31586, final_gf_rows=4728
```

For Chain+Onion changes:
```bash
python run_chain_onion.py
# → validation_harness status PASS/WARN/FAIL
```

---

## Risk levels (from context/09_PROMPT_PROTOCOL.md)

| Risk | Scope | Examples |
|---|---|---|
| **Low** | Docs, README, logging, CSS, comments | No approval needed |
| **Medium** | UI feeds, adapters, exports, filters, dashboard metrics | State what you intend before applying |
| **High** | Pipeline stages, data model, Team GF builder, row insertion, startup files, app.py routing, chain/onion scoring, file loaders, output contracts | Stop and wait for explicit approval |

---

## Forbidden investigation moves

- Do NOT silently re-run the pipeline (`context/09_PROMPT_PROTOCOL.md §F`)
- Do NOT use `sed -i` or in-place bash rewrites against source files (`context/11_TOOLING_HAZARDS.md §H-1.1`)
- Do NOT edit `src/flat_ged/*` business code
- Do NOT replace `_patched_main_context` with config injection
- Do NOT delete `output/parity*` or repo-root `.log` files without explicit cleanup task
- Do NOT lower the HIGH/MEDIUM report confidence gate

---

*Back to [[00_START_HERE]]*
