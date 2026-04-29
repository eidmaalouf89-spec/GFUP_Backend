# 09 — Prompt Protocol

> How to write prompts for this repo so future tasks land cleanly.
> Built from the project rules (CLAUDE.md, project instructions) and from
> what we already know about how this code is organised.

---

## A. The non-negotiables (read these into every prompt header)

1. **The app must always run.** Never knowingly break startup, UI loading,
   pipeline execution, or exports.
2. **Preserve working parts.** No cosmetic rewrites. No "clean architecture"
   migrations unless the task explicitly asks.
3. **Inspect before acting.** Read the files first. Trace the runtime first.
   Never guess structure.
4. **Minimal changes win.** 20 safe lines beat 400 elegant risky ones.
5. **Maintain context.** Update `/context/*` when meaningful runtime, flow,
   output, UI feed, mapping, or exception change happens.
6. **No fake certainty.** If you're unsure, say what is unknown, say what
   needs to be inspected, say what test confirms truth.
7. **Do not overengineer.** No frameworks, abstractions, wrappers,
   speculative scalability you weren't asked for.
8. **Respect source of truth.** Flat GED + report memory + run_memory.db
   are the authoritative layers. Don't bypass them.
   Chain + Onion is the operational intelligence layer for
   live/legacy/archive buckets, top issues, scores, and narratives;
   it reads pipeline outputs and is consumed read-only by the UI
   (Focus narrowing) and by `query_hooks.*`.

---

## B. Standard task template

Every task to Claude/Codex on this repo should start with this structure:

```
Objective:
  [one sentence]

Findings (pre-inspection — what you already think):
  - ...
  - ...

Plan:
  1. ...
  2. ...

Files:
  READ:
    [paths]
  MODIFY:
    [paths]
  CREATE:
    [paths]
  DO NOT TOUCH:
    [paths]

Validation:
  - [how you'll prove it worked]

Risk: Low / Medium / High
```

Risk levels (from project instructions):
- **Low:** docs, README, logging, badges, CSS, comments, tiny UI text.
- **Medium:** UI feeds, adapters, summaries, exports, filters, dashboard
  metrics, list logic.
- **High:** pipeline stages, data model, Team GF builder, row insertion,
  startup files, app.py routing, chain/onion scoring, file loaders,
  output contracts, anything touching multiple systems.

For Medium and High, **stop and wait for approval** before changing code.

---

## C. Validation template

Pick the validations relevant to your task. Don't run more than necessary.

```
Compile / parse:
  python -m py_compile app.py main.py
  python -m py_compile src/run_orchestrator.py src/pipeline/runner.py

UI surface:
  python app.py --browser              # opens jansa-connected.html in default browser
  # then visually verify the page renders, no JS console errors

Pipeline run (only when intentional):
  python main.py                       # full headless run, writes to runs/run_NNNN/
  # Validate by:
  #   - run_memory.db has a new COMPLETED row
  #   - output/GF_TEAM_VERSION.xlsx is updated
  #   - output/DISCREPANCY_REPORT.xlsx is updated

Chain + Onion:
  python run_chain_onion.py            # writes output/chain_onion/*

Specific checks:
  grep -n EXCEPTION_COLUMNS src/flat_ged/input/source_main/consultant_mapping.py
  grep -n BENTIN_TARGET_TYPES src/pipeline/stages/stage_discrepancy.py

Smoke tests:
  python -m pytest tests/              # if relevant test exists
  python scripts/repo_health_check.py
```

---

## D. Hand-off prompts (when Cowork can't do it itself)

Two situations are gated:

### D.1 — Pipeline reruns

**Do not rerun the pipeline inside Cowork** unless explicitly authorized.
The pipeline mutates `data/run_memory.db`, the user's GF, and `runs/`.
Instead, hand the user a Claude Code prompt that includes:
- Exact commands.
- Expected success signals (status COMPLETED, run_number incremented,
  artifact_count ≈ 33 for FULL mode, no errors in `pipeline_run.log`).
- What artifacts to expect under `runs/run_NNNN/`.
- What files/results to bring back before continuing.

### D.2 — Long backfills, multi-run experiments

Same pattern: hand off, don't drive.

---

## E. Things to ask the user before guessing

- Whether the change should affect `output/GF_TEAM_VERSION.xlsx` (the team
  deliverable) or only internal artifacts.
- Whether a hardcoded value (status label, contractor code, sheet name)
  is a typo or a contractual term.
- Whether a missing UI screen is "intentionally a stub" or "unfinished".
- When the user says "broken", whether they mean "doesn't run", "renders
  wrong values", or "exports the wrong file".

---

## F. Forbidden moves

- Silently rerunning the pipeline.
- Silent column / file / mapping renames.
- Edits to `src/flat_ged/*` business code.
- Edits to `data/run_memory.db` schema without a migration plan.
- Replacing `_patched_main_context` with config injection.
- Replacing the production UI with a Vite-built variant ("dist/index.html"
  is explicitly NOT a fallback per `app._resolve_ui`).
- "Improving" the data_bridge contract (the four window globals are the
  shared interface).
- Deleting `output/parity*`, `output/step9/`, repo-root `.log` files
  without an explicit cleanup task.

---

## G. Allowed casual moves (no approval needed)

- README typo fixes.
- `/context/*.md` updates after a confirmed change.
- New entries in `/context/exceptions_*.csv` if discovered.
- Adding logging at WARN/INFO level.
- Adding docstrings (without changing the contract).

---

## H. Talking to Claude (style)

The project rules say:
- Be direct, technical, concise.
- Don't speech-make. Don't oversell.
- Don't create giant plans unless asked.

For this repo specifically:
- Always restate the runtime path you're touching (UI / pipeline /
  chain_onion / report_memory).
- When in doubt about a hardcoded value, find its grep result and quote
  it back to the user instead of paraphrasing.
- Cite the file + line for any claim about what the code does.
