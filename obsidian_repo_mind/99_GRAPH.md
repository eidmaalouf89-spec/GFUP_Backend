#repo-map #graph #mermaid #data-flow

# System Graph

> Mermaid graphs of major modules and data flows.

---

## Full system data flow

```mermaid
flowchart TD
    GED["input/GED_export.xlsx\n(Raw GED — Rank 1)"]
    PDF["input/consultant_reports/\n(PDF reports — optional)"]
    FLATGED["output/intermediate/FLAT_GED.xlsx\n(Rank 2)"]
    RPMEM["data/report_memory.db\n(Rank 3)"]
    EFFR["effective_responses_df\n(Rank 4)"]
    GFV0["output/GF_V0_CLEAN.xlsx\n(Rank 5)"]
    GFTEAM["output/GF_TEAM_VERSION.xlsx\n(Rank 6)"]
    RUNMEM["data/run_memory.db\nArtifact registry"]
    RUNCONTEXT["RunContext\n(data_loader.py)"]
    ADAPTERS["src/reporting/*\nAggregators + adapters"]
    APPPY["app.py\nApi class\n(PyWebView)"]
    BRIDGE["ui/jansa/data_bridge.js\nwindow.OVERVIEW / CONSULTANTS / CONTRACTORS"]
    JANUI["ui/jansa/*.jsx\nPresentation only"]

    GED --> FLATBUILDER["src/flat_ged_runner.py\n+ src/flat_ged/ (FROZEN)"]
    PDF --> CONSULTINT["src/consultant_integration.py"]
    FLATBUILDER --> FLATGED
    CONSULTINT --> CMATRIX["output/consultant_match_report.xlsx"]
    CMATRIX --> STAGEMEM["stage_report_memory.py"]
    FLATGED --> STAGES["11-stage pipeline\nsrc/pipeline/stages/"]
    RPMEM --> STAGEMEM
    STAGEMEM --> EFFR
    EFFR --> STAGES
    STAGES --> GFV0
    STAGES --> GFTEAM
    STAGES --> RUNMEM

    RUNMEM --> RUNCONTEXT
    FLATGED --> RUNCONTEXT
    RPMEM --> RUNCONTEXT
    RUNCONTEXT --> ADAPTERS
    ADAPTERS --> APPPY
    APPPY --> BRIDGE
    BRIDGE --> JANUI
```

---

## Chain+Onion data flow

```mermaid
flowchart TD
    FLATGED["output/intermediate/FLAT_GED.xlsx"]
    DEBUG["output/intermediate/DEBUG_TRACE.csv"]
    RPMEM["data/report_memory.db"]

    FLATGED --> SL["source_loader.py (Step 04)"]
    DEBUG --> SL
    RPMEM --> SL

    SL --> FG["family_grouper.py (05)\nCHAIN_VERSIONS + CHAIN_REGISTER"]
    FG --> CB["chain_builder.py (06)\nCHAIN_EVENTS"]
    CB --> CC["chain_classifier.py (07)\nportfolio_bucket"]
    CC --> CM["chain_metrics.py (08)\nCHAIN_METRICS"]
    CM --> OE["onion_engine.py (09)\nONION_LAYERS"]
    OE --> OS["onion_scoring.py (10)\nONION_SCORES"]
    OS --> NE["narrative_engine.py (11)\nCHAIN_NARRATIVES"]
    NE --> EXP["exporter.py (12)\n7 CSV + XLSX + 2 JSON"]
    EXP --> VH["validation_harness.py (14)\nPASS/WARN/FAIL"]

    EXP --> QH["query_hooks.py (13)\n26 query functions"]
    QH --> FOCUS["app.py::_build_live_operational_numeros\nFocus narrowing"]
    QH --> CHAINTEL["window.CHAIN_INTEL\n(top_issues + dashboard_summary)"]
    EXP --> CTA["chain_timeline_attribution.py\nCHAIN_TIMELINE_ATTRIBUTION.json"]
    CTA --> DCC["DCC Chronologie section"]
    EXP --> CATB["counter_attack_builder.py\nCOUNTER_ATTACK_ITEMS.csv"]
    CATB --> CAQ["counter_attack_query.py\nAction MOEX API"]
    CAQ --> AMX["counter_attack.jsx\nACTION MOEX page"]
```

---

## Source-of-truth hierarchy

```mermaid
graph TD
    R1["Rank 1: input/GED_export.xlsx\nDocument identity, lifecycle"]
    R2["Rank 2: FLAT_GED.xlsx\nNormalized operational layer"]
    R3["Rank 3: report_memory.db\nPersistent consultant truth"]
    R4["Rank 4: effective_responses_df\nComposed response truth (LEFT-anchored on GED)"]
    R5["Rank 5: GF_V0_CLEAN.xlsx\nReconstruction output — NOT source of truth"]
    R6["Rank 6: GF_TEAM_VERSION.xlsx\nTeam deliverable"]
    R7["Rank 7: UI\nPresentation only"]

    R1 --> R2 --> R3 --> R4 --> R5 --> R6 --> R7
```

---

## Pipeline stage sequence

```mermaid
flowchart LR
    S1[stage_init_run] --> S2[stage_read_flat]
    S2 --> S3[stage_normalize]
    S3 --> S4[stage_version]
    S4 --> S5[stage_route]
    S5 --> S6[stage_report_memory]
    S6 --> S7[stage_write_gf]
    S7 --> S8[stage_build_team_version]
    S8 --> S9[stage_discrepancy]
    S9 --> S10[stage_diagnosis]
    S10 --> S11[stage_finalize_run]
```

---

## UI screen → backend module mapping

```mermaid
flowchart LR
    OVR["Overview\noverview.jsx"] --> AGG["aggregator.compute_project_kpis\n+ timeseries\n+ consultant/contractor summaries"]
    CONS["Consultants\nconsultants.jsx"] --> CONSSUM["aggregator.compute_consultant_summary\n→ ui_adapter.adapt_consultants"]
    CFICHE["Consultant Fiche\nfiche_page.jsx"] --> CFICHEBL["consultant_fiche.build_consultant_fiche"]
    CONTR["Contractors\ncontractors.jsx"] --> CONTRSUM["aggregator.compute_contractor_summary\n→ ui_adapter.adapt_contractors_*"]
    CTRFICHE["Contractor Fiche\ncontractor_fiche_page.jsx"] --> CTRQUAL["contractor_quality.build_contractor_quality"]
    DCC["DCC\ndocument_panel.jsx"] --> DCCBL["document_command_center.py"]
    AMOX["Action MOEX\ncounter_attack.jsx"] --> CAQRY["counter_attack_query.py"]
    RUNS["Runs\nruns.jsx"] --> RE["run_explorer.get_all_runs"]
    EXEC["Executer\nexecuter.jsx"] --> ORC["run_orchestrator.run_pipeline_controlled"]
```

---

## Debugging flow (where to look first)

```mermaid
flowchart TD
    BUG["Wrong UI number"] --> Q1{"Is it a\nSAS metric?"}
    Q1 -- yes --> H3["Check: ctx.responses_df\nvs ctx.workflow_engine.responses_df\n(Seam 1 — H-3 hazard)"]
    Q1 -- no --> Q2{"Changed after\ncode edit?"}
    Q2 -- no --> CACHE["Delete FLAT_GED pkl cache\n(Seam 2 — H-2 hazard)"]
    Q2 -- yes --> Q3{"Join failing?"}
    Q3 -- yes --> DTYPE["Check identity column dtype\n(Seam 3 — str vs int64)"]
    Q3 -- no --> AUDIT["Run scripts/audit_counts_lineage.py\nCheck PASS/WARN/FAIL per layer"]
    AUDIT --> ROOT["Find divergence layer\n→ read relevant source files\n→ propose targeted fix"]
```

---

*Back to [[00_START_HERE]]*
```
