# UI Runtime Architecture

**Status:** JANSA connected UI is the only production frontend.

## Production Entrypoint

`python app.py` resolves exactly one UI file:

```text
ui/jansa-connected.html
```

The launcher no longer switches between JANSA, Vite dev server, or `ui/dist/index.html`. If `ui/jansa-connected.html` is missing, startup fails clearly instead of falling back to another frontend.

## Runtime Contract

Production runtime consists of:

- `app.py`
- `ui/jansa-connected.html`
- `ui/jansa/tokens.js`
- `ui/jansa/data_bridge.js`
- `ui/jansa/*.jsx`
- backend bridge methods exposed from `app.py`
- reporting adapters under `src/reporting/`

This is the review surface for shipped UI behavior.

## Legacy / Reference UI

The old Vite UI under `ui/src/`, `ui/index.html`, and generated `ui/dist/` output is no longer a production runtime target. It may remain in the repository as archival/reference material while the JANSA migration is finalized, but it should not be treated as the app users launch through `python app.py`.

Do not add new production behavior to the old Vite UI. Do not block JANSA runtime releases on old Vite UI cosmetic or lint issues unless the issue also affects the JANSA connected runtime.

## Validation Expectations

Meaningful checks for the production runtime:

```text
python -c "import app"
python -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8-sig')) for p in pathlib.Path('src').rglob('*.py')]"
```

For JANSA UI files, validate that `ui/jansa-connected.html` references the expected scripts in dependency order and that the app launches through `python app.py`.

`npm run build`, `npm run check:app`, and `npm run lint` currently target the old Vite/React build surface. They can still be useful for reference code health, but they are not production-runtime gates for JANSA unless the tooling is explicitly moved to `ui/jansa`.

## Review Guidance

Reviewers should focus on:

- deterministic launch through `ui/jansa-connected.html`
- pywebview bridge calls and `app.py` API methods
- JANSA components in `ui/jansa/`
- reporting adapters and data contracts consumed by JANSA
- parity-critical workflows: Focus, Overview, Consultants, Fiche, Drilldowns, Exports, Runs, Executer, Reports, and stale-days utilities

Reviewers should avoid treating old Vite-only files as shipped UI unless a change explicitly reintroduces them into the production runtime path.
