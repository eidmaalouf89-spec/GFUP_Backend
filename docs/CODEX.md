# CODEX.md

Codex is the conservative code review and verification layer for this repository. It should focus on correctness, regression risk, architecture boundaries, and scope discipline.

## Read First

Before reviewing or changing meaningful code, read:

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/UI_RUNTIME_ARCHITECTURE.md`
4. `docs/VALIDATION_BASELINE.md`
5. `docs/DEVELOPMENT_RULES.md`
6. `docs/JANSA_FINAL_AUDIT.md`

For UI work, read the relevant `docs/JANSA_PARITY_STEP_*.md` file.

## Current Repo Truth

This repository has two validated layers:

- deterministic backend pipeline: `main.py` -> `src/run_orchestrator.py` -> pipeline stages
- production JANSA desktop UI: `app.py` -> `ui/jansa-connected.html`

The old Vite UI is legacy/reference only and should not be reviewed as the shipped runtime unless a task explicitly changes runtime architecture.

Contractors are intentionally deferred for redesign. Do not mark contractor gaps as unexpected unless the task targets that scope.

## Review Priorities

1. Correctness
2. Determinism
3. Regression safety
4. Architecture boundaries
5. Scope control
6. Maintainability

Avoid style nitpicks when there are behavioral or architectural risks.

## Backend Review Checklist

Use for pipeline, domain, persistence, run modes, reconciliation, writer, and artifact changes.

Check:

- GED/GF/report-memory truth model preserved
- `run_orchestrator.py` still controls production execution
- stage order preserved
- `PipelineState` handoffs remain coherent
- run memory and artifact registration preserved
- output filenames/contracts unchanged unless explicitly intended
- metrics can be validated against `docs/VALIDATION_BASELINE.md`

High-risk areas:

- `src/pipeline/compute.py`
- discrepancy classification
- SAS/MOEX logic
- run baseline/current-run logic
- inherited GF resolution
- report memory merge
- artifact registration

## JANSA Runtime Review Checklist

Use for `app.py`, `src/reporting/`, `ui/jansa-connected.html`, and `ui/jansa/`.

Check:

- `python app.py` resolves only `ui/jansa-connected.html`
- no dual-UI fallback or old Vite runtime path is reintroduced
- bridge methods match JANSA data contracts
- Focus, Overview, Consultants, Fiche, Drilldowns, Exports, Runs, Executer, and Utilities remain intact
- stale-days selector and reports export remain wired
- old Vite build/lint issues are not treated as production blockers unless they affect JANSA runtime
- `docs/JANSA_FINAL_AUDIT.md` remains the truth sheet before push/review

## Validation Expectations

Backend changes require pipeline validation against `docs/VALIDATION_BASELINE.md`.

JANSA UI/runtime changes require parity/final-audit style validation against:

- `docs/UI_RUNTIME_ARCHITECTURE.md`
- relevant `docs/JANSA_PARITY_STEP_*.md`
- `docs/JANSA_FINAL_AUDIT.md`

These validation layers are separate. Compile success alone is not sufficient.

## Pushback Criteria

Push back if a change:

- mixes backend logic and UI presentation without need
- changes source-of-truth assumptions
- bypasses run memory or report memory
- silently changes run modes or artifacts
- touches broad architecture for a narrow request
- reintroduces legacy UI runtime behavior
- claims full parity despite deferred contractor scope

## Review Output

Lead with findings, ordered by severity, with file/line references. Then list validation gaps or residual risk. Keep summaries short and concrete.
