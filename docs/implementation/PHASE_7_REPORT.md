# Phase 7 — Contractor Quality Fiche (REPORT)

**Status:** ✅ SHIPPED 2026-05-01
**Plan files (kept for audit, marked SUPERSEDED/CLOSED):**
- `PHASE_7_CONTRACTOR_FICHE_WIRING.md` (original "wire existing builder" plan; superseded mid-phase by the rescope)
- `PHASE_7_CONTRACTOR_QUALITY_FICHE.md` (rescoped V1 plan; closed by this report)

---

## 1. Outcome

A new per-contractor quality fiche is live on the JANSA UI. Reachable from the dashboard "Entreprise de la semaine" card and from any enriched contractor card on the Contractors tab. Renders header (canonical name, code, lots, buildings, "Documents Actifs"), a 5-tile KPI strip with peer bands and ⓘ formula tooltips, a polar histogram of contractor-attributed delay per chain (12 sectors plus an "under 10 days" footer), a long-chains panel, an open/finished card, and two dormant-document queues (REF and SAS REF) clickable into the existing Document Command Center.

---

## 2. What shipped — V1 widgets

| # | Widget | Backend source |
|---|---|---|
| H | Header (name, code, lots, buildings, total active) | `payload.contractor_name/code/lots/buildings` + `quality.open_finished.total` |
| K1 | KPI: Taux SAS REF historique | `quality.kpis.sas_refusal_rate` |
| K2 | KPI: REF dormants | `quality.kpis.dormant_ref_count` |
| K3 | KPI: Chaînes > 120j | `quality.kpis.pct_chains_long` |
| K4 | KPI: Délai moyen entreprise (incl. REF dormants) | `quality.kpis.avg_contractor_delay_days` |
| K5 | KPI: Taux SUS SOCOTEC | `quality.kpis.socotec_sus_rate` |
| P | Polar delay histogram (12 sectors + under-10 footer) | `quality.polar_histogram` |
| L | Long-chains panel | `quality.long_chains` |
| O | Open/finished chains | `quality.open_finished` |
| D1 | Dormant REF queue → DCC | `quality.dormant_ref` |
| D2 | Dormant SAS REF queue → DCC | `quality.dormant_sas_ref` |

All KPI tiles carry a peer band (median + p25/p75 across all 29 contractors). All dormant rows drilldown to the existing Document Command Center via `window.openDocumentCommandCenter(numero, indice)`.

---

## 3. Backend metric definitions (the formulas behind each tile)

- **Taux SAS REF historique** = `count(responses_df where approver_raw == "0-SAS" AND status_clean == "REF" AND doc_id ∈ contractor_docs)` ÷ `count(responses_df where approver_raw == "0-SAS" AND date_answered ≠ null AND doc_id ∈ contractor_docs)`. Source: `ctx.responses_df` (NOT `ctx.workflow_engine.responses_df` — that view drops exception approvers including 0-SAS; see `context/06_EXCEPTIONS_AND_MAPPINGS.md` §B.0 and `context/11_TOOLING_HAZARDS.md` H-3).
- **REF dormants** = `count(dernier docs where visa_global == "REF")` for this contractor.
- **Chaînes > 120 j** = `count(chains where chain.totals.days_actual > 120)` ÷ `count(chains)`, scoped to chains for this contractor.
- **Délai moyen entreprise (incl. REF dormants)** = mean across this contractor's chains of `(attribution_breakdown["ENTREPRISE"] + attribution_breakdown[<contractor_name>] + attribution_breakdown[<contractor_code>])` plus, for chains currently dormant in the contractor's hands (latest indice REF or SAS REF, no resubmission), `(today - date_visa)` days.
- **Taux SUS SOCOTEC** = `count(responses_df where approver_canonical == "Bureau de Contrôle" AND status_clean == "SUS" AND doc_id ∈ contractor_docs)` ÷ `count(responses_df where approver_canonical == "Bureau de Contrôle" AND date_answered ≠ null AND doc_id ∈ contractor_docs)`.
- **Polar histogram** = histogram of contractor-attributed-delay (per the avg formula above, MINUS the dormant time — the polar uses CLOSED-cycle attribution only) bucketed into 13 buckets [0,10), [10,20), …, [110,120), [120+). The 0-10 bucket is exposed separately as `under_10_count` so the 12 displayed sectors don't get visually dominated.
- **Long-chains share** = sum of `_contractor_delay_for_chain(ch, …)` (CLOSED-cycle attribution only — Phase 0 D-004 stripped dormant time from the numerator to keep the share bounded ≤ 100%) ÷ sum of `chain.totals.delay_days` over chains where `chain.chain_long == True`.
- **Open/finished** = `dernier visa_global ∈ {VSO, VAO, HM}` → finished; everything else (REF, SAS REF, SUS, VSO-SAS, null) → open. `VSO-SAS` is a conformity gate, NOT a doc approval.

---

## 4. Notable design decisions

- **Sibling backend module, not mutation of contractor_fiche.py.** The new `contractor_quality.py` lives alongside the existing builder. The wrapper `get_contractor_fiche_for_ui` calls both and merges the quality payload under `payload.quality`. Existing builder semantics are preserved exactly.
- **BENTIN_OLD legacy filter applied at fiche time.** Pre-2026 BEN docs survive the FLAT_GED stage (the year filter only runs at clean-GF generation time). `_apply_legacy_filter` strips them at fiche computation, BEN-only, no-op for other 28 contractors. See `context/06_EXCEPTIONS_AND_MAPPINGS.md` §D/§E.
- **Avg delay extended; share kept bounded.** `avg_contractor_delay_days` includes dormant time per Eid's Q2 instruction (a 200-day dormant REF IS contractor delay). `share_contractor_in_long_chains` does NOT include dormant time in its numerator (would otherwise exceed denominator → AMP 199% bug). The two metrics answer two different questions.
- **Polar drops 0-10 from sectors but keeps the count.** Most contractors have many sub-10-day chains; including them as a sector visually crushed the rest. Solution: 12 sectors for 10-120+, 0-10 reported as a footer.
- **Inline-copy of design tokens in contractor_fiche_page.jsx.** The fiche page is self-contained: FONT_UI, FONT_NUM, color palette, `fmt`/`pct`/`pctFmt` formatters are inlined from `fiche_base.jsx` rather than imported (no edits to `fiche_base.jsx`).
- **React popover tooltip, not native title.** pywebview/CEF doesn't render native HTML title tooltips. KpiInfoIcon uses React state + hover/focus handlers + a positioned popover (Step 12c).
- **Cache invalidation as a class of bug.** Phase 0 surfaced that the FLAT_GED pickle cache freshness check used file mtime only — schema drift in upstream code was invisible. The Phase 0 patch added `CACHE_SCHEMA_VERSION` to `data_loader.py:89` (current value `"v2"`); cache_meta.json carries the version; mismatch forces a rebuild.

---

## 5. Files

### Created
- `src/reporting/contractor_quality.py` (~440 lines after all 12a/12a-fix2 edits)
- `ui/jansa/contractor_fiche_page.jsx` (792 lines after Step 12c)

### Modified (Phase 7)
- `app.py` — added `get_contractor_fiche_for_ui` (line 1070)
- `ui/jansa/data_bridge.js` — added `loadContractorFiche` (lines 124–150)
- `ui/jansa/shell.jsx` — added `selectedContractor` state, `ContractorFiche` route, `onOpenContractor` plumbing
- `ui/jansa/overview.jsx` — Entreprise BestPerformerCard now opens fiche
- `ui/jansa/contractors.jsx` — ContractorCard click → fiche; chip stays non-clickable
- `ui/jansa-connected.html` — script tag for `contractor_fiche_page.jsx`

### Modified (Phase 0, prerequisites)
- `src/reporting/data_loader.py` — `CACHE_SCHEMA_VERSION` constant + freshness check (Phase 0 D-001)
- `src/reporting/contractor_quality.py` — strip-dormant patch for share-only numerator (Phase 0 D-004)
- `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json` — regenerated (2819 chains) + atomic-write hardening (Phase 0 D-005)

### Untouched (verified)
- `src/reporting/contractor_fiche.py` business logic
- `src/reporting/consultant_fiche.py`
- `src/reporting/aggregator.py`, `focus_filter.py`, `focus_ownership.py`, `ui_adapter.py`
- `src/reporting/chain_timeline_attribution.py` business logic
- `src/chain_onion/`, `src/flat_ged/`, all pipeline stages
- `ui/jansa/fiche_base.jsx`, `fiche_page.jsx`, `consultants.jsx`, `document_panel.jsx`, `runs.jsx`, `executer.jsx`

---

## 6. Validation evidence (Step 11a smoke, 2026-05-01)

Backend smoke (`api.get_contractor_fiche_for_ui` per contractor):

| Code | open | sas_ref | avg_delay | sus | long_share | dormant | polar |
|---|---|---|---|---|---|---|---|
| BEN | 98 | 8.2 % | 14.2 j | 0.0 % | 47.1 % | 0 | 12 sectors, sum=8, u10=89 |
| SNI | 594 | 8.3 % | 56.9 j | 1.5 % | 10.9 % | 48 | 12 sectors, sum=82, u10=340 |
| AXI | 518 | 1.4 % | 23.3 j | 10.3 % | 9.8 % | 8 | 12 sectors, sum=44, u10=214 |
| UTB | 274 | 2.1 % | 38.1 j | 0.0 % | 5.7 % | 28 | 12 sectors, sum=31, u10=214 |
| LGD | 1102 | 4.3 % | 74.1 j | 57.5 % | 33.1 % | 119 | 12 sectors, sum=144, u10=422 |
| ZZZ | 0 | 0 % | 0 j | n/a | 0 % | 0 | 12 sectors, sum=0, u10=0 |

- **AMP canary:** `share_contractor_in_long_chains = 91.2 %` — bounded (was 199.45 % pre-fix). Phase 0 D-004 fix confirmed live.
- **Phase 1-6 regressions:** all 5 guards pass (`get_overview_for_ui`, `get_consultants_for_ui`, `get_contractors_for_ui`, `get_consultant_fiche("GEMO")`, `get_contractor_fiche("BEN")` still raw — no leak).
- **UI checklist:** 25 / 25 items confirmed by project owner.
- **App launch:** clean. No Python traceback. CEF teardown message at exit is benign.

---

## 7. V2 backlog (deferred from Phase 7)

- **Polar histogram visual polish.** Reads cleanly, but Eid flagged "still not pretty." Candidates: clearer radial scale, sector labels visible on hover, a more legible palette ramp, possibly an outer ring with bucket-edge tick marks. No backend change.
- **Drilldowns from polar / long-chains / KPI tiles.** V1 only the dormant queues drill into the DCC. V2 candidates: polar sector → list of chains in that 10-day bucket → chain timeline; long-chains panel → list of long chains → chain timeline; KPI tiles → list of underlying docs.
- **Focus mode behavior on contractor fiche.** V1 shows a "sans effet sur cette fiche (V2)" notice. V2 should highlight/sort/emphasize recent issues without filtering historical data (per Eid's intent).
- **Phase 0 deferred items** (carried forward, owned outside Phase 7):
  - **D-003** — Raw↔flat SAS REF gap (SNI: raw ~184 vs flat 52). Upstream rework.
  - **D-006** — AAI 1-row mystery, needs investigation.
  - **D-010** — Engine vs meta visa source spot-check, needs investigation.
- **"Best contractor" selection criteria** (`ui_adapter.adapt_overview` line 125 uses `(VSO+VAO)/total_submitted`; Eid noted this is not the right "taux de conformité"). Out of scope at Phase 7 (lives in dashboard adapter, not contractor fiche). Tracked here for visibility.

---

## 8. Resumption / V2 starting points

Anyone picking up V2 should:
1. Read this report end-to-end.
2. Read `docs/implementation/PHASE_7_CONTRACTOR_QUALITY_FICHE.md` (closed plan with full design rationale).
3. Read `docs/audit/SIGN_OFF.md` and `docs/audit/TRIAGE.md` for Phase 0 deferred items.
4. Read `context/07_OPEN_ITEMS.md` "V2 backlog — Phase 7 follow-ups."
5. Inspect the live fiche in the running app to ground the visual context before designing changes.

---

## 9. Sign-off

Phase 7 is closed as of 2026-05-01.
Step 11a UI smoke: 25 / 25 items PASS.
Backend smoke: 0 failures across 6 contractors × 5 KPIs × all structural invariants.
Phase 0 prerequisite: SIGNED 2026-04-29 by project owner.
