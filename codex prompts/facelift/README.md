# JANSA — Implementation Handoff

You are a non-coder. Hand this folder to **Claude Code** or **Codex** and follow the prompts in `PROMPTS.md` in order. Each prompt is copy-paste ready.

## What's in this folder

```
handoff/
├── README.md                ← you are here
├── PROMPTS.md               ← 6 prompts to copy-paste, in order
├── 00-context.md            ← paste this FIRST into any new agent session
├── spec/
│   ├── data-contracts.md    ← JSON shapes (API contract)
│   ├── design-tokens.md     ← colors, fonts, spacing
│   └── ux-rules.md          ← interaction + animation rules
└── prototype/               ← the validated HTML prototype (the visual spec)
    └── (copy of your files here)
```

## The 6-step plan

| # | What | Who does it | How long |
|---|---|---|---|
| 1 | Set up backend (FastAPI wraps `calculator.py`) | Claude Code | 2 h |
| 2 | Set up frontend (Vite + React + TS) | Claude Code | 1 h |
| 3 | Port the prototype JSX files into the frontend | Claude Code | 3 h |
| 4 | Wire backend ↔ frontend (replace mocks with API calls) | Claude Code | 2 h |
| 5 | Add AxeoBIM GED connector | Claude Code + you (credentials) | 4 h |
| 6 | Deploy (single Docker container) | Claude Code | 2 h |

**Total ~14 hours of agent work**, spread over 2–3 sessions.

## How to run this

1. Open Claude Code (or Codex) in an empty folder on your laptop.
2. Paste `00-context.md` first — the agent now knows the project.
3. Paste prompt **#1** from `PROMPTS.md`. Let it finish. Test it works.
4. Paste prompt **#2**. Test. Repeat.
5. If something breaks, paste the error back and say "fix this". Don't touch the code yourself.

## Non-negotiables (tell the agent)

- Keep `calculator.py` **unchanged** — it's the source of truth.
- Keep the exact JSON shape from the prototype (see `spec/data-contracts.md`).
- Keep the Apple/Tesla aesthetic — no Material/Tailwind defaults, no Recharts.
- Keep the 4 status colors semantic: VSO=green, VAO=yellow, REF=red, HM=gray.
