#repo-map #execution-flow #pipeline #runtime

# Execution Flow

> What happens step-by-step when you run the two entrypoints.
> See [[04_PIPELINE_STAGES]] for per-stage detail, [[06_JANSA_UI_RUNTIME]] for UI detail.

---

## `python main.py`

```mermaid
flowchart TD
    A["main.py __main__"] --> B["run_orchestrator.run_pipeline_controlled(run_mode=FULL)"]
    B --> C["_patched_main_context()\nmutates main.GED_FILE / GF_FILE / CONSULTANT_REPORTS_ROOT"]
    C --> D["flat_ged_runner.build_flat_ged_artifacts(ged_path)"]
    D --> E["FLAT_GED.xlsx → output/intermediate/"]
    E --> F{"reports_dir provided?"}
    F -- yes --> G["consultant_integration.run_consultant_integration()"]
    G --> H["consultant_match_report.xlsx"]
    F -- no --> I
    H --> I["pipeline.runner._run_pipeline_impl(main_module)"]
    I --> J["11 stages — see §Pipeline stages below"]
    J --> K["run_memory.db COMPLETED row\nsha256-verified artifacts\nruns/run_NNNN/ snapshot"]
```

Key points:
- `main.py` is intentionally tiny — delegates immediately to `run_orchestrator`
- `_patched_main_context` mutates path globals on the `main` module namespace; restored in `finally`
- `pipeline.runner._run_pipeline_impl` reads paths from `sys.modules["main"]`, NOT from `pipeline.paths`
- On any exception: `finalize_run_failure` marks the run row as FAILED in `run_memory.db`

---

## `python app.py`

```mermaid
flowchart TD
    A["app.py"] --> B["_resolve_ui() → ui/jansa-connected.html"]
    B --> C["webview.create_window()"]
    C --> D["_prewarm_cache thread starts"]
    D --> E["load_run_context(BASE_DIR)"]
    E --> F["FLAT_GED pickle cache check\n(schema version + mtime)"]
    F -- HIT --> G["unpickle docs_df + responses_df (~3s)"]
    F -- MISS --> H["stage_read_flat + normalize (~30s)\n→ save new cache"]
    G --> I["WorkflowEngine(responses_df) — strips SAS rows"]
    H --> I
    I --> J["build_effective_responses\n→ ctx.effective_responses_df"]
    J --> K["focus_ownership.compute_focus_ownership on dernier_df"]
    K --> L["RunContext ready (module-level cache)"]

    L --> M["_ensure_chain_data_fresh()\nwrites CHAIN_TIMELINE_ATTRIBUTION.{json,csv}"]

    C --> N["webview.start() → JANSA UI loads"]
    N --> O["data_bridge.js:bridge.init(focusMode, staleDays)"]
    O --> P["Promise.allSettled over 3 calls:\nget_overview_for_ui\nget_consultants_for_ui\nget_contractors_for_ui"]
    P --> Q["window.OVERVIEW / CONSULTANTS / CONTRACTORS populated"]
    Q --> R["React renders dashboard"]
```

Key points:
- `app._resolve_ui()` raises `FileNotFoundError` if `ui/jansa-connected.html` is missing — no fallback
- `--browser` mode: same HTML opens in system browser, but `window.pywebview.api` is unavailable; `data_bridge.js` times out after 5s and renders placeholder data only
- `RunContext` is cached at module level; cleared by `clear_cache()` after a new pipeline run

---

## `python run_chain_onion.py`

This is an **independent runner** — separate from the main pipeline.

```mermaid
flowchart TD
    A["run_chain_onion.py"] --> B["source_loader.load_chain_sources\n(reads FLAT_GED.xlsx + DEBUG_TRACE.csv + report_memory.db)"]
    B --> C["family_grouper → CHAIN_VERSIONS + CHAIN_REGISTER"]
    C --> D["chain_builder → CHAIN_EVENTS"]
    D --> E["chain_classifier → portfolio_bucket on CHAIN_REGISTER"]
    E --> F["chain_metrics → CHAIN_METRICS"]
    F --> G["onion_engine → ONION_LAYERS"]
    G --> H["onion_scoring → ONION_SCORES"]
    H --> I["narrative_engine → CHAIN_NARRATIVES"]
    I --> J["exporter → 7 CSV + 1 XLSX + 2 JSON → output/chain_onion/"]
    J --> K["validation_harness → 40-check acceptance report"]
```

Key coupling: Chain+Onion reads `output/intermediate/*` directly (NOT `run_memory.db`). It is coupled to "the most recent run that wrote intermediate", not to a specific `run_number`.

---

## Execution mode selection (orchestrator)

The orchestrator supports four modes based on what files are provided:

| Mode | Inputs | GF resolution |
|---|---|---|
| `GED_ONLY` | GED only | Inherited from latest valid completed run, or Run 0 |
| `GED_GF` | GED + GF | Provided directly |
| `GED_REPORT` | GED + reports | GF inherited |
| `FULL` | GED + reports + GF | Direct or inherited |

Inherited GF fallback order:
1. Latest completed non-stale run with a valid `FINAL_GF` artifact
2. Run 0 `FINAL_GF`
3. Clear failure if neither exists

---

## What `GFUP_FORCE_RAW=1` does

Setting this env variable forces `stage_read` (raw GED path) instead of `stage_read_flat` (default flat path). This is a developer fallback only — the raw path has more schema drift risk. Do not use in production.

---

*Back to [[00_START_HERE]]*
