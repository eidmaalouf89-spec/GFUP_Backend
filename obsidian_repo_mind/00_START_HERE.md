#repo-map #vault-index

# GF Updater V3 — Obsidian Vault

> **What this is:** A developer mental model for the GF Updater V3 repo (JANSA VISASIST). All notes are derived from actual repo files. Nothing is invented.

---

## What the repo does in one sentence

A **deterministic reconstruction and enrichment engine** that rebuilds a clean Grand Fichier (GF) from a raw GED export, persists consultant report truth across runs, exposes operational intelligence through a JANSA desktop UI, and scores every active document chain through a Chain+Onion portfolio intelligence layer.

Project: **17&CO Tranche 2** (single-project, single-user, local desktop app).

---

## How to read this vault

Start here, then follow the links:

1. [[01_SYSTEM_MENTAL_MODEL]] — one-page mental model of the whole system
2. [[02_SOURCE_OF_TRUTH_HIERARCHY]] — what layer is allowed to decide what
3. [[03_EXECUTION_FLOW]] — what happens when you run `main.py` / `app.py`
4. [[04_PIPELINE_STAGES]] — the 11 pipeline stages in detail
5. [[05_REPORTING_AND_UI_ADAPTERS]] — how backend modules feed UI screens
6. [[06_JANSA_UI_RUNTIME]] — PyWebView, data_bridge.js, JSX architecture
7. [[07_CHAIN_ONION_MENTAL_MODEL]] — Chain+Onion portfolio intelligence layer
8. [[08_DOCUMENT_COMMAND_CENTER]] — DCC search/panel architecture
9. [[09_ACTION_MOEX_COUNTER_ATTACK]] — Action MOEX / Counter-Attack layer
10. [[10_PERSISTENCE_RUN_AND_REPORT_MEMORY]] — run_memory.db + report_memory.db
11. [[11_DEBUGGING_SEAMS]] — known bug hotspots and diagnostics
12. [[12_DONT_TOUCH_WITHOUT_EXPLICIT_SCOPE]] — protected zones with rationale
13. [[13_SAFE_DEBUGGING_PROTOCOL]] — checklist for investigating issues
14. [[14_MODULE_INDEX]] — table of all important files/modules
15. [[15_DATA_ARTIFACT_INDEX]] — table of all important output artifacts
16. [[16_OPEN_QUESTIONS_AND_RISKS]] — documented gaps and deferred items
17. [[99_GRAPH]] — Mermaid data flow and module dependency graph
18. [[98_HOW_TO_USE_THIS_VAULT]] — Instructions for opening and navigating this vault

---

## Quick navigation by concern

| I want to understand… | Go to |
|---|---|
| The pipeline flow | [[03_EXECUTION_FLOW]], [[04_PIPELINE_STAGES]] |
| Why UI numbers may be wrong | [[11_DEBUGGING_SEAMS]] |
| Which file is source of truth | [[02_SOURCE_OF_TRUTH_HIERARCHY]] |
| How the UI gets its data | [[05_REPORTING_AND_UI_ADAPTERS]], [[06_JANSA_UI_RUNTIME]] |
| Chain+Onion intelligence | [[07_CHAIN_ONION_MENTAL_MODEL]] |
| What not to touch | [[12_DONT_TOUCH_WITHOUT_EXPLICIT_SCOPE]] |
| How to safely debug | [[13_SAFE_DEBUGGING_PROTOCOL]] |
| run_memory / report_memory | [[10_PERSISTENCE_RUN_AND_REPORT_MEMORY]] |
| Counter-Attack / Action MOEX | [[09_ACTION_MOEX_COUNTER_ATTACK]] |

---

## Operational dashboard (shipped 2026-05-07)

Focus mode is **retired as the default view**. The JANSA Overview now leads with the
operational dashboard, bound to `window.OVERVIEW.operational` (21 keys produced by
`src/reporting/aggregator.py::compute_operational_dashboard` lines 554–660 and
forwarded verbatim by `ui_adapter.adapt_overview`). The legacy Focus payload
(`window.OVERVIEW.focus`, 11 keys) remains exposed and callable but is no longer the
default. See [[05_REPORTING_AND_UI_ADAPTERS]], [[06_JANSA_UI_RUNTIME]], and
`docs/implementation/OPERATIONAL_DASHBOARD_REDESIGN.md` for the full contract.

---

## Key runtime commands

```bash
python main.py          # headless pipeline run
python app.py           # launch JANSA desktop UI (PyWebView)
python app.py --browser # open in system browser (no backend bridge)
python run_chain_onion.py  # run Chain+Onion intelligence layer
python scripts/audit_counts_lineage.py  # cross-layer data audit
```

---

*Vault generated 2026-05-07. Sources: README.md, context/00–12, docs/ARCHITECTURE.md, src/*, ui/jansa/*, app.py, main.py.*
