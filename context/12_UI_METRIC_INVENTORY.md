# context/12_UI_METRIC_INVENTORY.md

Canonical mapping: every number displayed in the JANSA UI → backend source.  
Generated: 2026-05-01 | Phase 8A.5 | Input to Step 8A.6 (widened audit).

Data path convention:  
`JSX reads window.GLOBAL` ← `data_bridge.js api.*()` ← `app.py Api.*()` ← `src/reporting/*.py`

---

## Table of Contents

1. [Overview page](#1-overview-page)
2. [Chain+Onion panel (Overview)](#2-chainonion-panel-overview)
3. [Shell — Sidebar & Focus pill](#3-shell--sidebar--focus-pill)
4. [Consultants tab](#4-consultants-tab)
5. [Contractors tab](#5-contractors-tab)
6. [Consultant fiche](#6-consultant-fiche)
7. [Contractor fiche](#7-contractor-fiche)
8. [Document Command Center](#8-document-command-center)
9. [Runs page](#9-runs-page)
10. [Export panel](#10-export-panel)
11. [Coverage Summary](#11-coverage-summary)

---

## 1. Overview page

API chain: `Api.get_overview_for_ui(focus, stale_days)` → `get_dashboard_data(ctx, focus_result)` + `adapt_overview(dashboard_data, app_state)` → `window.OVERVIEW`

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Overview | StatBadge | Total documents | `OVERVIEW.total_docs` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.dernier_df` | `len(ctx.dernier_df)` — row count of dernier-indice docs (one per numero) | `audit_counts_lineage.py` (Overview 10-field check) | None — covered |
| Overview | VisaFlow | Soumis (submitted total) | `OVERVIEW.visa_flow.submitted` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.dernier_df` | Alias for `total_docs_current`; total dernier-indice rows | `audit_counts_lineage.py` | Alias — same root as total_docs |
| Overview | VisaFlow | VSO count | `OVERVIEW.visa_flow.vso` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | Docs where `resolve_visa_global()` returns "VSO" | `audit_counts_lineage.py` (Overview 10-field check) | None — covered |
| Overview | VisaFlow | VAO count | `OVERVIEW.visa_flow.vao` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | Docs where `resolve_visa_global()` returns "VAO" | `audit_counts_lineage.py` (Overview 10-field check) | None — covered |
| Overview | VisaFlow | REF count | `OVERVIEW.visa_flow.ref` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | Docs where `resolve_visa_global()` returns "REF" | `audit_counts_lineage.py` (Overview 10-field check) | None — covered |
| Overview | VisaFlow | HM count | `OVERVIEW.visa_flow.hm` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | Docs where `resolve_visa_global()` returns "HM" | `audit_counts_lineage.py` (Overview 10-field check) | None — covered |
| Overview | VisaFlow | En attente / pending (Open) | `OVERVIEW.visa_flow.pending` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | Docs with no terminal VISA GLOBAL (Open bucket in `by_visa_global`) | `audit_counts_lineage.py` (Overview 10-field check) | None — covered |
| Overview | VisaFlow | Répondus (answered) | `OVERVIEW.visa_flow.answered` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | `total_docs − Open` = VSO + VAO + REF + HM (+ SAS REF) | Not audited | No explicit `answered` field in 10-field check |
| Overview | VisaFlow | Dans les délais (on_time) | `OVERVIEW.visa_flow.on_time` | `Api.get_overview_for_ui` | `adapt_overview` (from `ctx.responses_df`) | `ctx.responses_df` | Open docs where `date_status_type == PENDING_IN_DELAY` | Not audited | on_time/late split absent from audit |
| Overview | VisaFlow | En retard (late) | `OVERVIEW.visa_flow.late` | `Api.get_overview_for_ui` | `adapt_overview` (from `ctx.responses_df`) | `ctx.responses_df` | Open docs where `date_status_type == PENDING_LATE` | Not audited | on_time/late split absent from audit |
| Overview | BestCard | Meilleur consultant — taux (%) | `OVERVIEW.best_consultant.pass_rate` | `Api.get_overview_for_ui` | `compute_consultant_summary` / `adapt_overview` | `ctx.responses_df` | `response_rate × 100` of the top-ranked consultant (≥5 docs called) | Not audited | best_consultant not in 10-field audit |
| Overview | BestCard | Meilleur consultant — delta (Δ%) | `OVERVIEW.best_consultant.delta` | `Api.get_overview_for_ui` | `compute_consultant_summary` / `adapt_overview` | `ctx.responses_df` | Δ pass_rate vs prior-week snapshot | Not audited | No delta audit |
| Overview | BestCard | Meilleure entreprise — taux (%) | `OVERVIEW.best_contractor.pass_rate` | `Api.get_overview_for_ui` | `compute_contractor_summary` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | `approval_rate × 100` of the top contractor (≥5 docs) | Not audited | best_contractor not in 10-field audit |
| Overview | BestCard | Meilleure entreprise — delta (Δ%) | `OVERVIEW.best_contractor.delta` | `Api.get_overview_for_ui` | `compute_contractor_summary` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | Δ approval_rate vs prior-week snapshot | Not audited | No delta audit |
| Overview | WeeklyChart | Semaine — ouverts (bar) | `OVERVIEW.weekly[].opened` | `Api.get_overview_for_ui` | `compute_weekly_timeseries` / `adapt_overview` | `ctx.dernier_df` | New docs created in that ISO week (`created_at`) | Not audited | Weekly timeseries not in audit |
| Overview | WeeklyChart | Semaine — fermés (bar) | `OVERVIEW.weekly[].closed` | `Api.get_overview_for_ui` | `compute_weekly_timeseries` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | Docs receiving terminal visa in that ISO week | Not audited | Weekly timeseries not in audit |
| Overview | WeeklyChart | Semaine — refusés (bar) | `OVERVIEW.weekly[].refused` | `Api.get_overview_for_ui` | `compute_weekly_timeseries` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | Docs receiving REF visa in that ISO week | Not audited | Weekly timeseries not in audit |
| Overview | FocusStats | Focus — à traiter | `OVERVIEW.focus.focused` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` (stale-threshold filtered) | Count of non-stale, non-resolved open docs in the actionable set | `audit_counts_lineage.py` (Overview 10-field check) | None — covered |
| Overview | FocusStats | Focus — P1 en retard critique | `OVERVIEW.focus.p1_overdue` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` + `ctx.responses_df` | Focused docs with computed priority == 1 | Not audited | P-level split not in 10-field audit |
| Overview | FocusStats | Focus — P2 urgent | `OVERVIEW.focus.p2_urgent` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` + `ctx.responses_df` | Focused docs with computed priority == 2 | Not audited | P-level split not in audit |
| Overview | FocusStats | Focus — P3 bientôt | `OVERVIEW.focus.p3_soon` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` + `ctx.responses_df` | Focused docs with computed priority == 3 | Not audited | P-level split not in audit |
| Overview | FocusStats | Focus — P4 ok | `OVERVIEW.focus.p4_ok` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` + `ctx.responses_df` | Focused docs with computed priority == 4 | Not audited | P-level split not in audit |
| Overview | FocusPriBar | Focus P1 par consultant (seg.) | `OVERVIEW.focus.by_consultant[].p1` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df._focus_owner` | Per-consultant count of P1 docs in priority queue | Not audited | Per-consultant focus split not in audit |
| Overview | FocusPriBar | Focus P2 par consultant (seg.) | `OVERVIEW.focus.by_consultant[].p2` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df._focus_owner` | Per-consultant count of P2 docs | Not audited | Per-consultant focus split not in audit |
| Overview | FocusPriBar | Focus P3 par consultant (seg.) | `OVERVIEW.focus.by_consultant[].p3` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df._focus_owner` | Per-consultant count of P3 docs | Not audited | Per-consultant focus split not in audit |
| Overview | FocusPriBar | Focus P4 par consultant (seg.) | `OVERVIEW.focus.by_consultant[].p4` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df._focus_owner` | Per-consultant count of P4 docs | Not audited | Per-consultant focus split not in audit |
| Overview | ProjectStats | Consultants actifs | `OVERVIEW.project_stats.total_consultants` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.approver_names` | Distinct canonical approver names (excl. 0-SAS, Sollicitation*) | Not audited | total_consultants not in 10-field audit |
| Overview | ProjectStats | Entreprises intervenantes | `OVERVIEW.project_stats.total_contractors` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.gf_sheets` | `len(ctx.gf_sheets)` — GF sheet count (proxy for contractor count) | Not audited | total_contractors not in 10-field audit |
| Overview | ProjectStats | Délai moyen de visa (j.) | `OVERVIEW.project_stats.avg_days_to_visa` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | Mean `(visa_date − created_at).days` for closed docs; 0–365 day range | `audit_counts_lineage.py` (Overview 10-field check) | None — covered |
| Overview | ProjectStats | Docs en attente SAS | `OVERVIEW.project_stats.docs_pending_sas` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.responses_df` | Rows where `approver_raw=="0-SAS"` AND `date_status_type` in PENDING_* | Not audited | docs_pending_sas not in 10-field audit |
| Overview | Header | Semaine S## | `OVERVIEW.week_num` | `Api.get_overview_for_ui` | `compute_project_kpis` | `ctx.run_date` | ISO week number derived from run_date | Not audited | Metadata only |
| Overview | Header | Numéro de run | `OVERVIEW.run_number` | `Api.get_overview_for_ui` | `compute_project_kpis` | `ctx.run_number` (run_memory.db) | Sequential run ID from run_memory.db | Not audited | Metadata only |

---

## 2. Chain+Onion panel (Overview)

API chain: `Api.get_chain_onion_intel(limit)` → reads `output/chain_onion/top_issues.json` + `dashboard_summary.json` → `window.CHAIN_INTEL`

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Overview | ChainOnionPanel | Chaînes actives | `CHAIN_INTEL.summary.live_chains` | `Api.get_chain_onion_intel` | reads `dashboard_summary.json` | `output/chain_onion/dashboard_summary.json` | Count of open doc chains currently tracked | Not audited | chain_onion output not in any audit |
| Overview | ChainOnionPanel | Chaînes escaladées | `CHAIN_INTEL.summary.escalated_chain_count` | `Api.get_chain_onion_intel` | reads `dashboard_summary.json` | `output/chain_onion/dashboard_summary.json` | Chains with escalation flag set | Not audited | chain_onion output not in any audit |
| Overview | ChainOnionPanel | Pression moyenne (live) | `CHAIN_INTEL.summary.avg_pressure_live` | `Api.get_chain_onion_intel` | reads `dashboard_summary.json` | `output/chain_onion/dashboard_summary.json` | Mean pressure score across live chains | Not audited | chain_onion output not in any audit |
| Overview | ChainOnionPanel | Thème principal | `CHAIN_INTEL.summary.top_theme_by_impact` | `Api.get_chain_onion_intel` | reads `dashboard_summary.json` | `output/chain_onion/dashboard_summary.json` | Theme label with highest cumulative impact score | Not audited | chain_onion output not in any audit |
| Overview | IssueCard | Rang de priorité action | `CHAIN_INTEL.issues[].action_priority_rank` | `Api.get_chain_onion_intel` | reads `top_issues.json` | `output/chain_onion/top_issues.json` | Rank within the sorted top-issues list | Not audited | chain_onion output not in any audit |
| Overview | IssueCard | Score normalisé /100 | `CHAIN_INTEL.issues[].normalized_score_100` | `Api.get_chain_onion_intel` | reads `top_issues.json` | `output/chain_onion/top_issues.json` | Issue urgency score normalised to 0–100 | Not audited | chain_onion output not in any audit |
| Overview | IssueCard | Étiquette d'urgence | `CHAIN_INTEL.issues[].urgency_label` | `Api.get_chain_onion_intel` | `narrative_translation.translate_top_issue` | `output/chain_onion/top_issues.json` | Human-readable urgency category label | Not audited | chain_onion output not in any audit |
| Overview | IssueCard | État courant | `CHAIN_INTEL.issues[].current_state` | `Api.get_chain_onion_intel` | reads `top_issues.json` | `output/chain_onion/top_issues.json` | Short description of the chain's current state | Not audited | chain_onion output not in any audit |

---

## 3. Shell — Sidebar & Focus pill

Data sources: `window.OVERVIEW`, `window.CONSULTANTS`, `window.CONTRACTORS` (already loaded globals)

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Shell | Sidebar badge | Runs (badge) | `OVERVIEW.total_runs` | `Api.get_overview_for_ui` | `adapt_overview` / `get_app_state` | `run_memory.db` | Total completed runs stored in run_memory.db | Not audited | run count not in audit |
| Shell | Sidebar badge | Consultants (badge) | `CONSULTANTS.length` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` | Count of consultant summary rows returned | Not audited | sidebar badge count not in audit |
| Shell | Sidebar badge | Entreprises (badge) | `Object.keys(CONTRACTORS).length` | `Api.get_contractors_for_ui` | `adapt_contractors_lookup` | `ctx.dernier_df` | Count of distinct emetteur codes in lookup dict | Not audited | sidebar badge count not in audit |
| Shell | Sidebar badge | Focus (badge) | `focusStats.focused` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` | Same value as `OVERVIEW.focus.focused` cached in shell state | `audit_counts_lineage.py` | Derived from same source as `focused` |
| Shell | Project pill | S## / Run N | `OVERVIEW.run_number` | `Api.get_overview_for_ui` | `compute_project_kpis` | `ctx.run_number` | Same `run_number` shown in Overview header | Not audited | Metadata display |
| Shell | FocusToggle | Nb docs à traiter | `focusStats.focused` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` | `focus_result.stats.focused` — actionable set size | `audit_counts_lineage.py` | None — covered |
| Shell | FocusToggle | P1 en retard (pill) | `focusStats.p1_overdue` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` + `ctx.responses_df` | Count of P1 docs in actionable set | Not audited | P-split not in audit |
| Shell | StalePopover | Docs exclus (périmés) | `focusStats.excluded` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` | Docs dropped from actionable set due to stale age | Not audited | stale breakdown not in audit |
| Shell | StalePopover | Docs résolus | `focusStats.resolved` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` + `workflow_engine` | Open docs that have received terminal VISA GLOBAL since last run | Not audited | stale breakdown not in audit |
| Shell | StalePopover | Docs périmés | `focusStats.stale` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `ctx.dernier_df` | Docs beyond stale_threshold_days with no recent activity | Not audited | stale breakdown not in audit |
| Shell | StalePopover | Total dernier (base) | `focusStats.total_dernier` | `Api.get_overview_for_ui` | `compute_project_kpis` / `adapt_overview` | `ctx.dernier_df` | `len(ctx.dernier_df)` — same as total_docs | `audit_counts_lineage.py` | Same root as total_docs |

---

## 4. Consultants tab

API chain: `Api.get_consultants_for_ui(focus, stale_days)` → `compute_consultant_summary(ctx, focus_result)` → `adapt_consultants(summaries)` → `window.CONSULTANTS`

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Consultants | PageHeader | Nb consultants (total) | `CONSULTANTS.length` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` | Number of consultant rows returned (excl. SAS, Sollicitation*) | Not audited | consultant count not in 10-field audit |
| Consultants | PrimaryCard / MoexCard | Docs appelés | `c.total` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` | Rows where `date_status_type != NOT_CALLED` for this approver_canonical | Not audited | per-consultant fields not in audit |
| Consultants | PrimaryCard / MoexCard | Docs répondus | `c.answered` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` | Rows where `date_status_type == ANSWERED` | Not audited | per-consultant fields not in audit |
| Consultants | PrimaryCard / MoexCard | Docs en attente | `c.pending` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` | `called − answered` (open responses for this consultant) | Not audited | per-consultant fields not in audit |
| Consultants | PrimaryCard / SecondaryChip | Taux de conformité (%) | `c.pass_rate` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` | `round(answered / called, 4) × 100`; mapped in adapt_consultants | Not audited | per-consultant pass_rate not in audit |
| Consultants | PrimaryCard / MoexCard | Docs Focus (à traiter) | `c.focus_owned` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_overview` | `focus_result.focused_df._focus_owner` | Count of focused docs where this consultant is in `_focus_owner` list | Not audited | per-consultant focus not in audit |
| Consultants | PrimaryCard | VSO count | `c.vso` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` | Responses where `status_clean == s1` (VSO for most; FAV for SOCOTEC) | Not audited | per-consultant breakdown not in audit |
| Consultants | PrimaryCard | VAO count | `c.vao` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` | Responses where `status_clean == s2` | Not audited | per-consultant breakdown not in audit |
| Consultants | PrimaryCard / SecondaryChip | REF count | `c.ref` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` | Responses where `status_clean == s3` | Not audited | per-consultant breakdown not in audit |
| Consultants | PrimaryCard | Délai moyen réponse (j.) | `c.avg_response_days` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` + `ctx.docs_df` | Mean `(date_answered − created_at).days` for answered rows; 0–365 range | Not audited | avg_response_days not in audit |
| Consultants | PrimaryCard | Tendance (sparkline) | `c.trend` | `Api.get_consultants_for_ui` | `compute_consultant_summary` / `adapt_consultants` | `ctx.responses_df` | Array of weekly/monthly pass_rate values for the sparkline | Not audited | trend series not in audit |
| Consultants | FocusPriBar | Focus P1 (segment) | `focusEntry.p1` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df` | Per-consultant P1 docs from Overview OVERVIEW.focus.by_consultant | Not audited | per-consultant P-split not in audit |
| Consultants | FocusPriBar | Focus P2 (segment) | `focusEntry.p2` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df` | Per-consultant P2 docs | Not audited | per-consultant P-split not in audit |
| Consultants | FocusPriBar | Focus P3 (segment) | `focusEntry.p3` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df` | Per-consultant P3 docs | Not audited | per-consultant P-split not in audit |
| Consultants | FocusPriBar | Focus P4 (segment) | `focusEntry.p4` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df` | Per-consultant P4 docs | Not audited | per-consultant P-split not in audit |

---

## 5. Contractors tab

API chain: `Api.get_contractors_for_ui(focus, stale_days)` → `compute_contractor_summary(ctx, focus_result)` → `adapt_contractors_list()` + `adapt_contractors_lookup()` → `window.CONTRACTORS_LIST` + `window.CONTRACTORS`

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Contractors | PageHeader | Nb intervenants (total) | `Object.keys(CONTRACTORS).length` | `Api.get_contractors_for_ui` | `adapt_contractors_lookup` | `ctx.dernier_df` | Distinct emetteur codes in the full lookup dict | Not audited | contractor count not in audit |
| Contractors | ContractorCard | Total documents | `c.docs` | `Api.get_contractors_for_ui` | `compute_contractor_summary` / `adapt_contractors_list` | `ctx.dernier_df` | `total_submitted` — dernier rows for this emetteur | Not audited | per-contractor counts not in audit |
| Contractors | ContractorCard | Taux de conformité (%) | `c.pass_rate` | `Api.get_contractors_for_ui` | `compute_contractor_summary` / `adapt_contractors_list` | `ctx.dernier_df` + `workflow_engine` | `round((vso + vao) / total_submitted, 4) × 100` | Not audited | per-contractor pass_rate not in audit |
| Contractors | ContractorCard | Focus — à traiter | `c.focus_owned` | `Api.get_contractors_for_ui` | `compute_contractor_summary` | `focus_result.focused_df._focus_owner_tier` | Focused docs where `_focus_owner_tier == CONTRACTOR` AND `emetteur == code` | Not audited | per-contractor focus not in audit |
| Contractors | FocusPriBar | Focus P1 (segment) | `focusEntry.p1` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df` | P1 docs from Overview focus.by_contractor | Not audited | per-contractor P-split not in audit |
| Contractors | FocusPriBar | Focus P2 (segment) | `focusEntry.p2` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df` | P2 docs | Not audited | per-contractor P-split not in audit |
| Contractors | FocusPriBar | Focus P3 (segment) | `focusEntry.p3` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df` | P3 docs | Not audited | per-contractor P-split not in audit |
| Contractors | FocusPriBar | Focus P4 (segment) | `focusEntry.p4` | `Api.get_overview_for_ui` | `apply_focus_filter` / `adapt_overview` | `focus_result.focused_df` | P4 docs | Not audited | per-contractor P-split not in audit |

---

## 6. Consultant fiche

API chain: `Api.get_fiche_for_ui(name, focus, stale_days)` → `build_consultant_fiche(ctx, name, focus_result)` → `window.FICHE_DATA`  
SAS variant: `build_sas_fiche(ctx, focus_result)` — same shape, different semantics.

### 6a. Header / Masthead

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Consultant fiche | Masthead | Total docs appelés | `FICHE_DATA.header.total` | `Api.get_fiche_for_ui` | `_build_header` | `ctx.dernier_df` merged `ctx.responses_df` | `len(filtered_merged_df)` — docs called for this consultant (inner join) | Not audited | fiche fields not in any audit |
| Consultant fiche | HeroStats card 1 | Docs répondus | `FICHE_DATA.header.answered` | `Api.get_fiche_for_ui` | `_build_header` | merged df | Rows where `_status_for_consultant` in {s1, s2, s3, HM} | Not audited | fiche fields not in audit |
| Consultant fiche | HeroStats card 1 chip | VSO / FAV count | `FICHE_DATA.header.s1_count` | `Api.get_fiche_for_ui` | `_build_header` | merged df | `_status_for_consultant == s1` | Not audited | fiche fields not in audit |
| Consultant fiche | HeroStats card 1 chip | VAO / SUS count | `FICHE_DATA.header.s2_count` | `Api.get_fiche_for_ui` | `_build_header` | merged df | `_status_for_consultant == s2` | Not audited | fiche fields not in audit |
| Consultant fiche | HeroStats card 1 chip | REF / DEF count | `FICHE_DATA.header.s3_count` | `Api.get_fiche_for_ui` | `_build_header` | merged df | `_status_for_consultant == s3` | Not audited | fiche fields not in audit |
| Consultant fiche | HeroStats card 1 chip | HM count | `FICHE_DATA.header.hm_count` | `Api.get_fiche_for_ui` | `_build_header` | merged df | `_status_for_consultant == "HM"` | Not audited | fiche fields not in audit |
| Consultant fiche | HeroStats card 2 | Bloquants ouverts | `FICHE_DATA.header.open_blocking` | `Api.get_fiche_for_ui` | `_build_header` | merged df + `workflow_engine` | Open docs with no VISA GLOBAL yet (`_is_blocking == True`) | Not audited | fiche fields not in audit |
| Consultant fiche | HeroStats card 2 chip | Bloquants dans les délais | `FICHE_DATA.header.open_blocking_ok` | `Api.get_fiche_for_ui` | `_build_header` | merged df + `workflow_engine` | Blocking and `_on_time == True` | Not audited | fiche fields not in audit |
| Consultant fiche | HeroStats card 2 chip | Bloquants en retard | `FICHE_DATA.header.open_blocking_late` | `Api.get_fiche_for_ui` | `_build_header` | merged df + `workflow_engine` | Blocking and `_on_time == False` | Not audited | fiche fields not in audit |
| Consultant fiche | HeroStats card 2 | Non-bloquants ouverts | `FICHE_DATA.header.open_non_blocking` | `Api.get_fiche_for_ui` | `_build_header` | merged df + `workflow_engine` | Open AND has VISA GLOBAL (`_is_blocking == False`) | Not audited | fiche fields not in audit |
| Consultant fiche | HeroStats card 3 | Taux de refus (%) | computed: `pct(h.s3_count, h.answered)` | `Api.get_fiche_for_ui` | `_build_header` (JSX computes pct) | merged df | `round(s3_count / answered × 100, 1)` computed in JSX | Not audited | fiche fields not in audit |

### 6b. Bloc 1 — Monthly / weekly activity table

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Consultant fiche | Bloc1 table | Nouveaux docs (nvx) | `FICHE_DATA.bloc1[r].nvx` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df | Docs with `_created_date` in [month_start, month_end] | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | Docs fermés | `FICHE_DATA.bloc1[r].doc_ferme` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df | Docs answered in the month (`_date_answered` in period AND closed status) | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | s1 count (VSO/FAV) | `FICHE_DATA.bloc1[r].s1` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df | `_status_for_consultant == s1` among doc_ferme | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | s1 % | `FICHE_DATA.bloc1[r].s1_pct` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df | `round(s1 / doc_ferme × 100, 1)` | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | s2 count (VAO/SUS) | `FICHE_DATA.bloc1[r].s2` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df | `_status_for_consultant == s2` among doc_ferme | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | s2 % | `FICHE_DATA.bloc1[r].s2_pct` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df | `round(s2 / doc_ferme × 100, 1)` | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | s3 count (REF/DEF) | `FICHE_DATA.bloc1[r].s3` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df | `_status_for_consultant == s3` among doc_ferme | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | s3 % | `FICHE_DATA.bloc1[r].s3_pct` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df | `round(s3 / doc_ferme × 100, 1)` | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | HM count | `FICHE_DATA.bloc1[r].hm` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df | HM status in period | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | HM % | `FICHE_DATA.bloc1[r].hm_pct` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df | `round(hm / doc_ferme × 100, 1)` | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | Bloquants dans délais (snapshot) | `FICHE_DATA.bloc1[r].open_blocking_ok` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df + `workflow_engine` | End-of-month blocking open docs that were on-time | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | Bloquants en retard (snapshot) | `FICHE_DATA.bloc1[r].open_blocking_late` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df + `workflow_engine` | End-of-month blocking open docs that were late | Not audited | bloc1 not in audit |
| Consultant fiche | Bloc1 table | Non-bloquants (snapshot) | `FICHE_DATA.bloc1[r].open_nb` | `Api.get_fiche_for_ui` | `_build_bloc1` | merged df + `workflow_engine` | End-of-month non-blocking open docs | Not audited | bloc1 not in audit |

### 6c. Bloc 2 — Stacked area chart (cumulative)

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Consultant fiche | Bloc2 chart | s1 cumul. series | `FICHE_DATA.bloc2.s1_series` | `Api.get_fiche_for_ui` | `_build_bloc2` | derived from bloc1 | Cumulative s1 count at each period | Not audited | bloc2 not in audit |
| Consultant fiche | Bloc2 chart | s2 cumul. series | `FICHE_DATA.bloc2.s2_series` | `Api.get_fiche_for_ui` | `_build_bloc2` | derived from bloc1 | Cumulative s2 count | Not audited | bloc2 not in audit |
| Consultant fiche | Bloc2 chart | s3 cumul. series | `FICHE_DATA.bloc2.s3_series` | `Api.get_fiche_for_ui` | `_build_bloc2` | derived from bloc1 | Cumulative s3 count | Not audited | bloc2 not in audit |
| Consultant fiche | Bloc2 chart | HM cumul. series | `FICHE_DATA.bloc2.hm_series` | `Api.get_fiche_for_ui` | `_build_bloc2` | derived from bloc1 | Cumulative HM count | Not audited | bloc2 not in audit |
| Consultant fiche | Bloc2 chart | Bloquants ouverts series | `FICHE_DATA.bloc2.open_blocking_series` | `Api.get_fiche_for_ui` | `_build_bloc2` | derived from bloc1 | Period-level blocking open total | Not audited | bloc2 not in audit |
| Consultant fiche | Bloc2 chart | Non-bloquants series | `FICHE_DATA.bloc2.open_nb_series` | `Api.get_fiche_for_ui` | `_build_bloc2` | derived from bloc1 | Period-level non-blocking open total | Not audited | bloc2 not in audit |
| Consultant fiche | Bloc2 chart | Total series | `FICHE_DATA.bloc2.totals` | `Api.get_fiche_for_ui` | `_build_bloc2` | derived from bloc1 | Running total at each period | Not audited | bloc2 not in audit |

### 6d. Bloc 3 — Per-lot table + donut

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Consultant fiche | Bloc3 table | Total docs par lot | `FICHE_DATA.bloc3.lots[l].total` | `Api.get_fiche_for_ui` | `_build_bloc3` | merged df (grouped by `_gf_sheet`) | Row count for this GF sheet | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 table | s1 par lot | `FICHE_DATA.bloc3.lots[l].VSO` (or s1 label) | `Api.get_fiche_for_ui` | `_build_bloc3` | merged df | `_status_for_consultant == s1` count for this lot | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 table | s2 par lot | `FICHE_DATA.bloc3.lots[l].VAO` | `Api.get_fiche_for_ui` | `_build_bloc3` | merged df | s2 count for this lot | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 table | s3 par lot | `FICHE_DATA.bloc3.lots[l].REF` | `Api.get_fiche_for_ui` | `_build_bloc3` | merged df | s3 count for this lot | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 table | HM par lot | `FICHE_DATA.bloc3.lots[l].HM` | `Api.get_fiche_for_ui` | `_build_bloc3` | merged df | HM count for this lot | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 table | Bloquants dans délais | `FICHE_DATA.bloc3.lots[l].open_blocking_ok` | `Api.get_fiche_for_ui` | `_build_bloc3` | merged df + `workflow_engine` | Blocking open on-time for this lot | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 table | Bloquants en retard | `FICHE_DATA.bloc3.lots[l].open_blocking_late` | `Api.get_fiche_for_ui` | `_build_bloc3` | merged df + `workflow_engine` | Blocking open late for this lot | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 table | Non-bloquants | `FICHE_DATA.bloc3.lots[l].open_nb` | `Api.get_fiche_for_ui` | `_build_bloc3` | merged df + `workflow_engine` | Non-blocking open for this lot | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 totals row | Total (ligne total) | `FICHE_DATA.bloc3.total_row.total` | `Api.get_fiche_for_ui` | `_build_bloc3` | sum over lots | Sum of `total` across all lots | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 totals row | Bloquants dans délais (total) | `FICHE_DATA.bloc3.total_row.open_blocking_ok` | `Api.get_fiche_for_ui` | `_build_bloc3` | sum over lots | Sum of `open_blocking_ok` across lots | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 totals row | Bloquants en retard (total) | `FICHE_DATA.bloc3.total_row.open_blocking_late` | `Api.get_fiche_for_ui` | `_build_bloc3` | sum over lots | Sum of `open_blocking_late` across lots | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 totals row | Non-bloquants (total) | `FICHE_DATA.bloc3.total_row.open_nb` | `Api.get_fiche_for_ui` | `_build_bloc3` | sum over lots | Sum of `open_nb` across lots | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 donut | Donut total (bloquants) | `FICHE_DATA.bloc3.donut_total` | `Api.get_fiche_for_ui` | `_build_bloc3` | sum over lots | `donut_ok + donut_late` (total blocking open docs) | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 donut | Donut — dans délais | `FICHE_DATA.bloc3.donut_ok` | `Api.get_fiche_for_ui` | `_build_bloc3` | sum over lots | Sum of `open_blocking_ok` across all lots | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 donut | Donut — en retard | `FICHE_DATA.bloc3.donut_late` | `Api.get_fiche_for_ui` | `_build_bloc3` | sum over lots | Sum of `open_blocking_late` across all lots | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 donut | Donut — non-bloquants | `FICHE_DATA.bloc3.donut_nb` | `Api.get_fiche_for_ui` | `_build_bloc3` | sum over lots | Sum of `open_nb` across all lots | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 critical list | Lots critiques — bloquants en retard | `FICHE_DATA.bloc3.critical_lots[].open_late` | `Api.get_fiche_for_ui` | `_build_bloc3` | sum over lots | `open_blocking_late` for lots sorted desc; top 5 | Not audited | bloc3 not in audit |
| Consultant fiche | Bloc3 refus list | Lots à fort taux de refus (%) | `FICHE_DATA.bloc3.refus_lots[][1]` | `Api.get_fiche_for_ui` | `_build_bloc3` | sum over lots | `round(REF / (VSO+VAO+REF+HM) × 100, 1)` for lots with ≥3 closed; top 5 | Not audited | bloc3 not in audit |

---

## 7. Contractor fiche

API chain: `Api.get_contractor_fiche_for_ui(code, focus, stale_days)` → `build_contractor_fiche(ctx, code)` + `build_contractor_quality(ctx, code, peer_stats)` + `build_contractor_quality_peer_stats(ctx)` → `window.CONTRACTOR_FICHE_DATA`

### 7a. Header & KPI strip

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Contractor fiche | HeaderCard | Documents actifs | `CONTRACTOR_FICHE_DATA.quality.open_finished.total` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality` | `ctx.dernier_df` (emetteur filter) | `open + finished` for this contractor's dernier-indice docs | Not audited | contractor fiche not in audit |
| Contractor fiche | KpiStrip | Taux de refus SAS (%) | `q.kpis.sas_refusal_rate.value` | `Api.get_contractor_fiche_for_ui` | `_sas_refusal_rate` in `contractor_quality.py` | `ctx.responses_df` (all indices) | `sas_track_REF / sas_track_answered` for this emetteur's docs | Not audited | contractor quality KPIs not in audit |
| Contractor fiche | KpiStrip | Refus SAS — médiane pairs | `q.kpis.sas_refusal_rate.peer.median` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality_peer_stats` | `ctx.responses_df` (all contractors) | 50th percentile of `sas_refusal_rate` across all 29 contractors | Not audited | peer stats not in audit |
| Contractor fiche | KpiStrip | Refus SAS — P25 pairs | `q.kpis.sas_refusal_rate.peer.p25` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality_peer_stats` | `ctx.responses_df` | 25th percentile | Not audited | peer stats not in audit |
| Contractor fiche | KpiStrip | Refus SAS — P75 pairs | `q.kpis.sas_refusal_rate.peer.p75` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality_peer_stats` | `ctx.responses_df` | 75th percentile | Not audited | peer stats not in audit |
| Contractor fiche | KpiStrip | REF dormants (count) | `q.kpis.dormant_ref_count.value` | `Api.get_contractor_fiche_for_ui` | `_dormant_list` in `contractor_quality.py` | `ctx.dernier_df` (emetteur filter) | Count of dernier docs with `visa_global == REF` (sitting idle) | Not audited | contractor quality KPIs not in audit |
| Contractor fiche | KpiStrip | REF dormants — pairs (median/p25/p75) | `q.kpis.dormant_ref_count.peer.*` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality_peer_stats` | `ctx.dernier_df` (all contractors) | Percentiles of dormant_ref_count across all contractors | Not audited | peer stats not in audit |
| Contractor fiche | KpiStrip | % chaînes longues | `q.kpis.pct_chains_long.value` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality` | chain_timelines artifact | `n_long / n_chains` where `chain_long` flag from chain attribution | Not audited | contractor quality KPIs not in audit |
| Contractor fiche | KpiStrip | % chaînes longues — pairs | `q.kpis.pct_chains_long.peer.*` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality_peer_stats` | chain_timelines artifact (all contractors) | Percentiles of pct_chains_long | Not audited | peer stats not in audit |
| Contractor fiche | KpiStrip | Délai moyen imputé (j.) | `q.kpis.avg_contractor_delay_days.value` | `Api.get_contractor_fiche_for_ui` | `_contractor_delay_for_chain` in `contractor_quality.py` | chain_timelines + `ctx.dernier_df` | Mean contractor-attributable delay: `attribution_breakdown.ENTREPRISE + canonical + dormant_days` per chain | Not audited | contractor quality KPIs not in audit |
| Contractor fiche | KpiStrip | Délai imputé — pairs | `q.kpis.avg_contractor_delay_days.peer.*` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality_peer_stats` | chain_timelines (all contractors) | Percentiles of avg_contractor_delay_days | Not audited | peer stats not in audit |
| Contractor fiche | KpiStrip | Taux SUS SOCOTEC (%) | `q.kpis.socotec_sus_rate.value` | `Api.get_contractor_fiche_for_ui` | `_socotec_sus_rate` in `contractor_quality.py` | `workflow_engine.responses_df` (Bureau de Contrôle rows) | `SUS / total_SOCOTEC_answers` for this emetteur's docs | Not audited | contractor quality KPIs not in audit |
| Contractor fiche | KpiStrip | SUS SOCOTEC — pairs | `q.kpis.socotec_sus_rate.peer.*` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality_peer_stats` | `workflow_engine.responses_df` | Percentiles of socotec_sus_rate (None-excluded) | Not audited | peer stats not in audit |

### 7b. Polar histogram & panels

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Contractor fiche | PolarHistogram | Bucket count (12 display buckets) | `q.polar_histogram.buckets[].count` | `Api.get_contractor_fiche_for_ui` | `_polar_histogram` in `contractor_quality.py` | chain_timelines + dormant_days | Chain count in each 10-day delay bucket [10-20, 20-30, …, 120+] | Not audited | polar histogram not in audit |
| Contractor fiche | PolarHistogram | Max bucket count (scale) | `q.polar_histogram.max_count` | `Api.get_contractor_fiche_for_ui` | `_polar_histogram` | chain_timelines | Max of the 12 displayed bucket counts (0-10 excluded) | Not audited | polar histogram not in audit |
| Contractor fiche | PolarHistogram | Chaînes < 10j (excluded zone) | `q.polar_histogram.under_10_count` | `Api.get_contractor_fiche_for_ui` | `_polar_histogram` | chain_timelines | Chains with contractor-attributed delay < 10 days | Not audited | polar histogram not in audit |
| Contractor fiche | LongChainsCard | % chaînes longues | `q.long_chains.pct_long` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality` | chain_timelines | `n_long / n_chains` (same as kpis.pct_chains_long.value) | Not audited | contractor fiche not in audit |
| Contractor fiche | LongChainsCard | Part du retard imputé (%) | `q.long_chains.share_contractor_in_long_chains` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality` | chain_timelines | `contractor_delay_in_long / total_delay_in_long` (closed-cycle only, no dormant) | Not audited | contractor fiche not in audit |
| Contractor fiche | OpenFinishedCard | Documents ouverts | `q.open_finished.open` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality` | `ctx.dernier_df` (emetteur filter) | Dernier docs where `visa_global NOT IN {VSO, VAO, HM}` | Not audited | contractor fiche not in audit |
| Contractor fiche | OpenFinishedCard | Documents terminés | `q.open_finished.finished` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality` | `ctx.dernier_df` | Dernier docs where `visa_global IN {VSO, VAO, HM}` | Not audited | contractor fiche not in audit |
| Contractor fiche | OpenFinishedCard | Total documents | `q.open_finished.total` | `Api.get_contractor_fiche_for_ui` | `build_contractor_quality` | `ctx.dernier_df` | `open + finished` | Not audited | contractor fiche not in audit |
| Contractor fiche | DormantQueue (REF) | Jours dormants (REF) | `q.dormant_ref[].days_dormant` | `Api.get_contractor_fiche_for_ui` | `_dormant_list` in `contractor_quality.py` | `ctx.dernier_df` + `ctx.data_date` | `(data_date − visa_global_date).days` for each dormant REF doc | Not audited | dormant queues not in audit |
| Contractor fiche | DormantQueue (SAS REF) | Jours dormants (SAS REF) | `q.dormant_sas_ref[].days_dormant` | `Api.get_contractor_fiche_for_ui` | `_dormant_list` | `ctx.dernier_df` + `ctx.data_date` | `(data_date − visa_global_date).days` for each dormant SAS REF doc | Not audited | dormant queues not in audit |

---

## 8. Document Command Center

API chains:  
- Search: `Api.search_documents(query, focus, stale_days)` → `search_documents(ctx, ...)` → array  
- Panel: `Api.get_document_command_center(numero, indice, focus, stale_days)` → `build_document_command_center(ctx, ...)` → payload

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| DCC | SearchResultsList | Nb résultats (count) | `results.length` | `Api.search_documents` | `search_documents` | `ctx.dernier_df` | Row count returned after substring match + optional focus filter | Not audited | DCC not in audit |
| DCC | ResponsesSection | Nb intervenants (count) | `data.responses.length` | `Api.get_document_command_center` | `_build_responses_section` | `ctx.responses_df` (doc_id filter) | One entry per approver response on this document's latest indice | Not audited | DCC not in audit |
| DCC | ChronologieSection | Durée totale réelle (j.) | `data.chronologie.totals.days_actual` | `Api.get_document_command_center` | reads `CHAIN_TIMELINE_ATTRIBUTION.json` | `output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json` | Total actual cycle duration from chain attribution artifact | Not audited | DCC / chronologie not in audit |
| DCC | ChronologieSection | Durée attendue (j.) | `data.chronologie.totals.days_expected` | `Api.get_document_command_center` | reads `CHAIN_TIMELINE_ATTRIBUTION.json` | chain timeline artifact | Contractual expected cycle duration | Not audited | DCC / chronologie not in audit |
| DCC | ChronologieSection | Retard total (j.) | `data.chronologie.totals.delay_days` | `Api.get_document_command_center` | reads `CHAIN_TIMELINE_ATTRIBUTION.json` | chain timeline artifact | `days_actual − days_expected` for the full chain | Not audited | DCC / chronologie not in audit |
| DCC | ChronologieSection | Retard réattribué (j.) | `data.chronologie.attribution_cap_reattributed` | `Api.get_document_command_center` | reads `CHAIN_TIMELINE_ATTRIBUTION.json` | chain timeline artifact | Delay that was capped and reattributed to another party | Not audited | DCC / chronologie not in audit |
| DCC | ChronologieSection | Durée réelle par indice (j.) | `data.chronologie.indices[].days_actual` | `Api.get_document_command_center` | reads `CHAIN_TIMELINE_ATTRIBUTION.json` | chain timeline artifact | Actual duration for one revision cycle (one indice) | Not audited | DCC / chronologie not in audit |
| DCC | ChronologieSection | Durée attendue par indice (j.) | `data.chronologie.indices[].days_expected` | `Api.get_document_command_center` | reads `CHAIN_TIMELINE_ATTRIBUTION.json` | chain timeline artifact | Expected duration for one revision cycle | Not audited | DCC / chronologie not in audit |
| DCC | ChronologieSection | Retard par indice (j.) | `data.chronologie.indices[].delay_days` | `Api.get_document_command_center` | reads `CHAIN_TIMELINE_ATTRIBUTION.json` | chain timeline artifact | `days_actual − days_expected` per indice | Not audited | DCC / chronologie not in audit |
| DCC | ChronologieSection | Attribution breakdown (j. par partie) | `data.chronologie.attribution_breakdown.*` | `Api.get_document_command_center` | reads `CHAIN_TIMELINE_ATTRIBUTION.json` | chain timeline artifact | Dict of party_name → attributed_days for this chain | Not audited | DCC / chronologie not in audit |

---

## 9. Runs page

API chain: `Api.get_all_runs()` → `run_explorer.get_all_runs()` → array of run records from `run_memory.db`

| page | component | label | js_field | api_method | py_function | source_dataframe | semantic_definition | audit_coverage | audit_gap |
|------|-----------|-------|----------|------------|-------------|------------------|---------------------|----------------|-----------|
| Runs | PageHeading | Total runs | `runs.length` | `Api.get_all_runs` | `run_explorer.get_all_runs` | `run_memory.db` | Count of completed run records in run_memory.db | Not audited | runs not in KPI audit |
| Runs | RunCard | Numéro de run | `run.run_number` | `Api.get_all_runs` | `run_explorer.get_all_runs` | `run_memory.db` | Sequential run ID assigned at pipeline start | Not audited | runs not in KPI audit |
| Runs | RunCard | Créé le (timestamp) | `run.created_at` | `Api.get_all_runs` | `run_explorer.get_all_runs` | `run_memory.db` | Run creation timestamp | Not audited | runs not in KPI audit |
| Runs | RunCard | Terminé le (timestamp) | `run.completed_at` | `Api.get_all_runs` | `run_explorer.get_all_runs` | `run_memory.db` | Run completion timestamp | Not audited | runs not in KPI audit |

---

## 10. Export panel

The Reports / Export page (`ReportsPage` stub in `shell.jsx`, drilldown export button in `fiche_page.jsx`) contains **no persistent numeric displays**. The export API calls (`Api.export_run_bundle`, `Api.export_team_version`) return a file path string shown in a toast notification. No inventory rows.

---

## 11. Coverage Summary

### Counts by page

| Page | Rows | Audited by script | Not audited |
|------|------|-------------------|-------------|
| Overview | 33 | 7 (`audit_counts_lineage.py`) | 26 |
| Chain+Onion panel | 8 | 0 | 8 |
| Shell sidebar / Focus pill | 11 | 2 (derived from audited fields) | 9 |
| Consultants tab | 15 | 0 | 15 |
| Contractors tab | 8 | 0 | 8 |
| Consultant fiche | 42 | 0 | 42 |
| Contractor fiche | 21 | 0 | 21 |
| Document Command Center | 10 | 0 | 10 |
| Runs page | 4 | 0 | 4 |
| Export panel | 0 | — | — |
| **TOTAL** | **152** | **9** | **143** |

### Coverage notes

**Covered (9 rows):** `audit_counts_lineage.py` compares 10 Overview KPI fields between the UI payload and the raw aggregation. Fields covered: `total_docs`, `vso`, `vao`, `ref`, `hm`, `pending`/Open, `focused`, `avg_days_to_visa`, and 1 more (likely `docs_pending_sas` or `total_runs`). Two shell badge counts (`focusStats.focused`, `focusStats.total_dernier`) derive from the same root as audited Overview fields.

**Not covered (143 rows):** Everything beyond the Overview KPI check. The largest unaudited surface areas are:

1. **Consultant fiche (42 rows)** — All bloc1/bloc2/bloc3 monthly table data, all per-lot breakdowns, all donut values. No audit script touches fiche output.
2. **Contractor fiche (21 rows)** — All 5 quality KPIs plus peer benchmarks, polar histogram, dormant queues. Entirely unaudited.
3. **Consultants tab (15 rows)** — Per-consultant response breakdown (VSO/VAO/REF/avg_days). No script compares these to raw responses_df.
4. **Chain+Onion panel (8 rows)** — Chain intel JSON output is never cross-checked against pipeline sources.
5. **DCC (10 rows)** — Chronologie attribution data and all panel counters are entirely unaudited.

### Recommended Step 8A.6 scope

Priority 1 (high value, feasible): Widen `audit_counts_lineage.py` to cover per-consultant totals (VSO/VAO/REF/called) and per-contractor `docs`/`pass_rate`. These re-use already-loaded DataFrames and the audit pattern is established.

Priority 2: Add a fiche-header spot-check: for one consultant, compare `header.total`, `header.answered`, `header.s1_count`, `header.open_blocking` against direct responses_df queries.

Priority 3 (deferred): Contractor fiche quality KPIs require chain_timelines artifact access; add to a separate chain-audit script.
