# DEVELOPMENT RULES

## Non-Negotiables

1. GED remains the primary operational truth.
2. GF remains a reconstructed output, not a source of truth.
3. Do not delete `data/report_memory.db` casually.
4. Do not bypass `src/run_orchestrator.py`.
5. Do not change pipeline stage order casually.
6. Do not silently change output filenames, artifact contracts, or run-mode behavior.
7. Do not reintroduce dual-UI runtime selection.

## Backend / Pipeline Changes

Use this path for changes to pipeline stages, domain logic, persistence, run modes, reconciliation, writer outputs, or artifact registration.

Required discipline:

- locate the exact stage/module first
- make the smallest deterministic change
- preserve run memory and report memory semantics
- validate against `docs/VALIDATION_BASELINE.md`
- explain any metric difference as intentional business behavior

Full pipeline validation is required for meaningful backend changes.

## UI / Runtime Changes

Production UI is JANSA connected UI only:

```text
python app.py -> ui/jansa-connected.html
```

Use this path for changes to JANSA components, bridge methods, reporting adapters, pywebview API methods, focus behavior, drilldowns, exports, Runs, Executer, and utility controls.

Required discipline:

- review `docs/UI_RUNTIME_ARCHITECTURE.md`
- review `docs/JANSA_FINAL_AUDIT.md`
- keep changes scoped to JANSA runtime files
- preserve Focus, Overview, Consultants, Fiche, Drilldowns, Exports, Runs, Executer, and Utilities
- do not treat old Vite-only lint/build issues as production blockers unless they affect JANSA runtime

UI parity/final-audit validation is required for meaningful JANSA changes.

## Documentation Changes

Docs must distinguish pipeline validation from UI parity validation.

Historical context may remain, but misleading runtime claims must be corrected. Contractors must be marked deferred unless the contractor redesign is explicitly in scope.

## Preferred Workflow

1. Define the issue.
2. Identify the layer: backend pipeline, persistence, reporting adapter, JANSA runtime, or docs.
3. Identify files that must change and files that must not change.
4. Apply a minimal patch.
5. Run the validation layer that matches the change.
6. Update docs when runtime behavior, architecture, or validation expectations change.
