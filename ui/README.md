# UI Directory

`ui/jansa-connected.html` is the production frontend entrypoint for `python app.py`.

The JANSA runtime loads:

- `ui/jansa/tokens.js`
- `ui/jansa/data_bridge.js`
- `ui/jansa/*.jsx`

The Vite files under `ui/src/`, `ui/index.html`, and generated `ui/dist/` output are legacy/reference material only. They are not the runtime UI target and should not be used as the production review surface unless the runtime architecture is changed intentionally.

See `../docs/UI_RUNTIME_ARCHITECTURE.md` for the full policy.
