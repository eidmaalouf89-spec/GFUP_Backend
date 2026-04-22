# Paste this first, at the start of every new Claude Code / Codex session

You are helping me ship **JANSA · VisaSist** — an internal dashboard that
tracks visa (document-approval) flow for a large French construction project
(P17&CO, Tranche 2).

## Stack we chose
- **Backend**: Python 3.11, FastAPI, Pydantic, Uvicorn.
  Wraps an existing `calculator.py` file that already produces the data.
- **Frontend**: React 18 + TypeScript + Vite.
  Pure CSS (CSS variables for theming), hand-rolled SVG charts.
  NO Tailwind, NO Material UI, NO Recharts.
- **Deployment**: Single Docker image, nginx serves frontend, reverse-proxies `/api` to FastAPI.

## What already exists
1. A validated HTML/React prototype in `prototype/` — this is the visual spec.
   Every pixel has been approved. Do not redesign.
2. `calculator.py` — the business logic. I'll paste it when you ask.
3. Mock data in `prototype/jansa/data.js` — exact shape the API must return.

## Rules
- Never redesign the UI. Replicate the prototype exactly.
- Never replace SVG charts with a chart library.
- Never change the color tokens.
- Ask me before adding a new dependency.
- Commit small, logical chunks. Run what you build after each step.
- If a prompt is ambiguous, stop and ask me before guessing.

I am not a coder. I read and paste; I don't write code. Be explicit about what
to run, and surface errors so I can paste them back.

Acknowledge you understand, then wait for my first prompt.
