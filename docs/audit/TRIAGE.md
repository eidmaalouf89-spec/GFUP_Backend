# TRIAGE — Phase 0 Step 0.5

> One row per real divergence found by Step 0.4 (`docs/audit/DIVERGENCE_REPORT.md`)
> plus the canary findings from Step 0.2 (`docs/audit/CANARY_BEN.md`) plus the
> §10 P0/P1 items in `docs/implementation/PHASE_0_BACKEND_DEBUGGING.md`.
>
> Classifications:
> - **fix-now** — clear bug with a local fix; addressed in Step 0.6.
> - **known limitation** — intentional behavior; document and move on.
> - **upstream rework** — requires changes to pipeline stages (out of Phase 0
>   scope); escalate as a separate ticket.
> - **needs investigation** — not enough info; schedule follow-up.
>
> Step 0.6 closes every fix-now row. Step 0.7 documents every known-limitation
> row in the appropriate context doc.

---

## Triage table

| ID | Stage | Metric | Contractor | Description | Classification | Action |
|---|---|---|---|---|---|---|
| **D-001** | B3 cache | All metrics relying on `responses_df` | All | `_flat_cache_is_fresh` checks file mtime only; pandas-version drift caused `[FLAT_CACHE] Cache load failed` despite "fresh" cache. Schema drift in `stage_read_flat.py` is invisible to the cache. (PHASE_0 §10 P0; CANARY §13/D-104; H-2 hazard.) | **fix-now** | Add `CACHE_SCHEMA_VERSION` constant in `data_loader.py`. Write into `cache_meta.json` on save. Reject cache if version differs in `_flat_cache_is_fresh`. |
| **D-002** | C5 vs C3 | SAS REF, SAS-track signals | All | `WorkflowEngine.__init__` filters `is_exception_approver=True` → strips ALL SAS rows from `ctx.workflow_engine.responses_df`. Δ = 4,834 rows (one per active doc). (PHASE_0 §10 P0; H-3.) | known limitation | Already documented in `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B.0 + `context/11_TOOLING_HAZARDS.md` H-3. Step 0.7 adds a runtime assertion to `data_loader._load_from_flat_artifacts` that `len(ctx.responses_df) - len(ctx.workflow_engine.responses_df) == sas_row_count` so any future drift is caught at load time. |
| **D-003** | A1 vs B1 | SAS REF count | SNI | Operator's raw-GED count ≈ 184, flat_ged extracts 52 (audit B1=52 confirms flat-side). Three numbers, three sources. PHASE_0 §10 P1. We never read raw GED directly — only FLAT_GED. Raw-side `RAPPEL` cells may inflate to ~184; SAS RAPPEL pre-2026 filter (`stage_read_flat._apply_sas_filter_flat`) excludes some pairs at the boundary. | **upstream rework** | Out of Phase 0 scope (would require reading `input/GED_export.xlsx` raw + reproducing the operator's count protocol). Escalate as a separate ticket. Action: open a ticket "Raw vs Flat SAS REF gap audit (SNI ~184 vs 52)" and attach this triage row. Note in `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B that SAS REF semantics differ between raw cell-counting and flat status_clean='REF' counting. |
| **D-004** | E2 long_chains | share_contractor_in_long_chains | AMP (only 199% case); SCH/LGD show inflation but stay <1 | `total_delay_in_long` (denom) excludes dormant time; `contractor_delay_in_long` (numer) includes dormant time after Phase 7 12a-fix2's extension. Numerator/denominator scope mismatch. AMP: 5050/2532 = 1.9945. (PHASE_0 §10 P1; CANARY §9; R-2.) | **fix-now** | Strip `dormant_days_by_numero` from the share-only numerator in `contractor_quality.build_contractor_quality` lines 486-489. Keep dormant extension in `avg_contractor_delay_days` (lines 472-476). Re-run `audit_share_long.py --contractor AMP` post-patch — expect share = 0.9115 (matches `control_no_dormant`). |
| **D-005** | D1 (artifact) | Chain count, chain_long count, attribution_breakdown | AXI (40 missing), UTB (53), FRS (18), SCH (6), LIN (2), **DBH (12, all)** | `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json` is truncated mid-object: 4,448,537 bytes on disk, valid JSON ends at byte 4,270,982. ~132 of 2,819 chains missing. `.csv` companion similarly truncated mid-row. `.corrupted_bak` from 2026-04-28 also corrupt. (CANARY §11 D-102; R-1.) | **fix-now** | (1) Regenerate the artifact from the existing chain_onion CSVs by running `compute_all_chain_timelines + write_chain_timeline_artifact` — this is NOT a pipeline rerun (the chain_timeline layer is independent of the GED pipeline; it is what `Api._ensure_chain_data_fresh` runs at app startup). (2) Harden `write_chain_timeline_artifact` (`src/reporting/chain_timeline_attribution.py:571-658`) with atomic-write semantics: write to `*.tmp` then `os.replace` → final path. Currently a process kill mid-write leaves a partial file in place. |
| **D-006** | B1 vs C3 | SAS REF count | AAI | B1 = 7 (FLAT_GED `GED_OPERATIONS` SAS+REF), C3 = 6 (`ctx.responses_df` SAS-track REF). 1 row lost between flat-ged extraction and the responses_df build. (R-3.) | **needs investigation** | Run a one-off diff: list (numero, indice) pairs with status_clean='REF' in `GED_OPERATIONS` for emetteur=AAI vs (numero, indice) pairs with status_clean='REF' AND approver_raw='0-SAS' in `ctx.responses_df` (post-legacy-filter). The diff is one (numero, indice). Check if it's caught by `_apply_sas_filter_flat` (`stage_read_flat.py:202-274`) or dropped at the `step_rows[step_rows.doc_id.notna()]` boundary (`stage_read_flat.py:548`). Single-row scope; low priority. |
| **D-007** | E1 vs E2 in same payload | total_submitted vs quality.open_finished.total | BEN (visible at 583 vs 98) | `contractor_fiche.build_contractor_fiche` does NOT apply the legacy filter (`total_submitted = 583` for BEN). `contractor_quality.build_contractor_quality` DOES apply it (`open_finished.total = 98`). Both ship to UI in the same `get_contractor_fiche_for_ui` payload. (CANARY §1; D-101.) | known limitation | Document in `context/06_EXCEPTIONS_AND_MAPPINGS.md` §C: "Contractor fiche payload exposes two `total` figures — `total_submitted` (all-time, no legacy filter) and `quality.open_finished.total` (post-2026 only, BENTIN_OLD-filtered for BEN). UI consumers must not assume they are the same number." Optional follow-up: rename one (Phase 7 territory). |
| **D-008** | E1 vs E2 in same payload | sas_refusal_rate (two formulas, same name) | BEN (0.072 vs 0.0816 example) | `block4_quality.sas_refusal_rate` = `(REF + SAS REF on dernier) / total_current` (terminal-visa rate over all 583 dernier; engine returns visa for pre-2026 docs). `quality.kpis.sas_refusal_rate.value` = SAS-track REF / SAS-track answered (over legacy-filtered docs via `ctx.responses_df`). Different formulas, different scopes, same name in the same payload. (CANARY §12; D-103; R-5.) | known limitation | Document in `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B that two `sas_refusal_rate` fields exist in the contractor fiche payload, with their definitions. Recommend renaming one to `dernier_refusal_rate` (Phase 7 territory). |
| **D-009** | E2 long_chains | share_contractor_in_long_chains (collateral) | SCH (0.8843 → 0.3784), LGD (0.7407 → 0.3311) | Collateral effect of the D-004 fix: SCH and LGD's share value will DECREASE substantially when dormant is stripped from the numerator. They were never >1.0, but the displayed rate inflates by 0.4-0.5 due to dormant docs in long chains. (R-2 collateral.) | known limitation | No code change. Note in `context/06` that the share metric reflects closed-cycle attribution only after the D-004 fix. The dormant-time view is captured by `avg_contractor_delay_days`. Eid should sanity-check the new SCH and LGD numbers (3-5 long chains each) post-fix. |
| **D-010** | C7 (precompute) | _visa_global on dernier in flat mode | All | `_precompute_focus_columns` (`data_loader.py:550`) calls `we.compute_visa_global_with_date(doc_id)` directly — but `flat_ged_doc_meta` is the documented authoritative source in flat mode (`stage_read_flat.py:80-105` `get_visa_global`). The engine returns `(None, None)` for SAS REF docs. Documented as KNOWN_GAP at `stage_read_flat.py:368-371`. | **needs investigation** | The discrepancy did not surface in the BEN canary (all 98 docs were Open). Need to verify on contractors with SAS REF dernier (per peer_stats top: dormant_ref_count for SNI/LGD/UTB). If `_visa_global` differs from `flat_ged_doc_meta.visa_global` for any dernier doc, surface as a separate fix-now ticket. Action in Step 0.6: write a quick spot-check script over all dernier docs comparing the two sources; if zero divergences, close as "engine and meta agree empirically". |

---

## Roll-up by classification

| Classification | Count | IDs |
|---|---:|---|
| fix-now              | 3 | D-001, D-004, D-005 |
| known limitation     | 4 | D-002, D-007, D-008, D-009 |
| upstream rework      | 1 | D-003 |
| needs investigation  | 2 | D-006, D-010 |
| **Total**            | **10** | |

---

## Step 0.6 plan (fix-now items)

For each fix-now row, the smallest safe patch + the audit script to re-run for verification.

### D-001 — `CACHE_SCHEMA_VERSION` in `data_loader.py`

**Files modified:**
- `src/reporting/data_loader.py`

**Changes:**
1. Add module-level constant `CACHE_SCHEMA_VERSION = "v1"` near the top of the cache section (line ~73).
2. Modify `_save_flat_normalized_cache` (lines 100-117) to include `"cache_schema_version": CACHE_SCHEMA_VERSION` in the meta dict.
3. Modify `_flat_cache_is_fresh` (lines 88-97) to also load `cache_meta.json` and reject when `meta.get("cache_schema_version") != CACHE_SCHEMA_VERSION`.

**Verification:**
- Bump `CACHE_SCHEMA_VERSION` to `"v2"` and reload → cache miss + rebuild expected.
- Restore `"v1"` → cache hit on subsequent loads.
- Re-run any audit script; cache load should succeed without the StringDtype warning.

**Manual operation post-fix:** Delete the three existing cache files (they have no version key and will be rejected once the patch lands; they would then be rebuilt automatically on next load). User approval required for `rm` per H-5.

### D-004 — Strip dormant from share-only numerator

**Files modified:**
- `src/reporting/contractor_quality.py`

**Changes:**
- Lines 486-489: change
  ```python
  contractor_delay_in_long = sum(
      _contractor_delay_for_chain(ch, canonical, contractor_code, dormant_days_by_numero)
      for ch in long_chains
  )
  ```
  to
  ```python
  contractor_delay_in_long = sum(
      _contractor_delay_for_chain(ch, canonical, contractor_code, None)
      for ch in long_chains
  )
  ```
  (i.e. pass `None` for `dormant_days_by_numero` so the share matches the closed-cycle attribution that `chain.totals.delay_days` describes).

**Why this and not "add dormant to denominator":** the denominator comes from chain_onion's `chain.totals.delay_days`, computed in `chain_timeline_attribution.compute_all_chain_timelines`. Modifying that denominator would require either (a) changing chain_timeline_attribution semantics for all consumers, or (b) recomputing the denominator inline in `contractor_quality`. Option (a) is high-risk; option (b) duplicates logic. Stripping dormant from the numerator is a 1-line change with no cross-system effects.

**Verification:**
- `python scripts/audit/audit_share_long.py --contractor AMP` → expect `share=0.9115`, no PATHOLOGY.
- `python scripts/audit/audit_share_long.py` (all 29) → expect 0 contractors with share > 1.0.
- `python scripts/audit/audit_peer_stats.py` → KPI distributions should change for `pct_chains_long` is unaffected; `share` is in `long_chains.share_contractor_in_long_chains`, not in the 5 KPI peer stats.
- Verify `avg_contractor_delay_days` is unchanged (the dormant extension is preserved at line 472-475).

### D-005 — Regenerate `CHAIN_TIMELINE_ATTRIBUTION.json` + atomic-write hardening

**Files modified:**
- `src/reporting/chain_timeline_attribution.py`

**Action 1 (regeneration — non-pipeline operation):**
Run a one-off Python script:
```python
from pathlib import Path
import sys
BASE = Path("...")
sys.path.insert(0, str(BASE / "src"))
from reporting.data_loader import load_run_context
from reporting.chain_timeline_attribution import (
    _load_chain_data, compute_all_chain_timelines, write_chain_timeline_artifact,
)
ctx = load_run_context(BASE)
co = BASE / "output" / "chain_onion"
events, register, versions = _load_chain_data(co)
timelines = compute_all_chain_timelines(ctx, events, register, versions)
out = BASE / "output" / "intermediate"
write_chain_timeline_artifact(timelines, out)
```
This rewrites both `CHAIN_TIMELINE_ATTRIBUTION.json` and `CHAIN_TIMELINE_ATTRIBUTION.csv` from the existing chain_onion CSVs. No pipeline run required.

**Action 2 (writer hardening):**
In `write_chain_timeline_artifact` (lines 571-658), wrap each write in atomic-replace semantics:
```python
import os
import tempfile

# JSON
tmp_json = json_path.with_suffix(".json.tmp")
with open(tmp_json, "w", encoding="utf-8") as f:
    json.dump(ordered, f, indent=2, ensure_ascii=False, default=str)
os.replace(tmp_json, json_path)

# CSV (similar pattern)
tmp_csv = csv_path.with_suffix(".csv.tmp")
csv_df.to_csv(tmp_csv, index=False)
os.replace(tmp_csv, csv_path)
```
A process kill mid-write now leaves the previous good file in place rather than truncating the canonical path.

**Verification:**
- After regeneration: `python -c "import json; print(len(json.load(open('output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json'))))"` should print 2,819 (matches `CHAIN_REGISTER`).
- `python scripts/audit/audit_chains.py` → expect zero D2 vs D1 mismatches across all 29 contractors.
- Atomic write tested by simulated kill: write, kill mid-process, verify canonical file is the previous good copy not a partial.

---

## Step 0.7 plan (known-limitation context updates)

| Context doc | What to add |
|---|---|
| `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B | D-007 (two `total` numbers in same payload), D-008 (two `sas_refusal_rate` formulas), D-009 (share_long collateral SCH/LGD) |
| `context/11_TOOLING_HAZARDS.md` H-2 | D-001 confirmation: real production pandas version drift observed during canary |
| `context/07_OPEN_ITEMS.md` | D-003 (raw vs flat SAS REF gap, escalated), D-006 (AAI 1-row mystery), D-010 (engine vs meta visa source spot-check) |
| `context/02_DATA_FLOW.md` | refine to show the cache layer + WorkflowEngine `is_exception_approver` filter as named transformations (per PHASE_0 §0.7) |

---

## What this triage explicitly does NOT close

- The 131 false-positive DIVERGENCE verdicts in `DIVERGENCE_REPORT.md` (naive convergence rule). These are not real divergences and need no fix.
- Any UI-side adjustment to display the corrected AMP share, the BEN total nuance, or the rename of the duplicate `sas_refusal_rate`. UI work resumes at Phase 7 Step 11a after Phase 0 sign-off.
- Any change to `chain_timeline_attribution`'s 10-day secondary cap logic. That's a Phase 1 (DCC) finding (`07_OPEN_ITEMS.md` #16), separate scope.
