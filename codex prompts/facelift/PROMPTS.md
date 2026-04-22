# The 6 prompts — paste in order

Between each prompt, wait for the agent to finish, test in your browser, then
paste the next one. If something fails, paste the error back verbatim and say
"fix this, then confirm it works before continuing."

---

## Prompt #1 — Project scaffold

```
Create this folder structure in the current directory:

jansa/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI entrypoint
│   │   ├── api.py           # route handlers
│   │   ├── models.py        # Pydantic schemas (match spec/data-contracts.md)
│   │   ├── calculator.py    # my existing logic (I'll paste it separately)
│   │   └── ged_client.py    # AxeoBIM stub for now
│   ├── requirements.txt     # fastapi, uvicorn[standard], pydantic, httpx, python-dotenv
│   └── Dockerfile
├── frontend/                # we'll scaffold with Vite next prompt
├── docker-compose.yml       # backend + frontend, volumes for dev
└── README.md

In backend/app/main.py:
- Create FastAPI app with CORS allowing http://localhost:5173
- Mount /api router
- Add /api/health returning {"ok": true}

In backend/app/api.py:
- 4 routes that all return mock data from spec/data-contracts.md for now:
  GET /overview
  GET /consultants
  GET /consultants/{slug}/fiche
  GET /runs
- Use the exact JSON shapes from spec/data-contracts.md.

Write requirements.txt with pinned versions.
Write a dev Dockerfile (python:3.11-slim, uvicorn with --reload).

Run `pip install -r backend/requirements.txt` and
`uvicorn app.main:app --reload --port 8000 --app-dir backend`.
Then curl http://localhost:8000/api/health and confirm it returns {"ok": true}.
```

---

## Prompt #2 — Frontend scaffold

```
In ./frontend, scaffold a Vite + React + TypeScript app:

npm create vite@latest . -- --template react-ts

Then:
- Delete App.css, index.css default content.
- Install: @tanstack/react-query
- Create src/api.ts: a typed fetch wrapper with base URL from
  import.meta.env.VITE_API_URL (default http://localhost:8000/api).
  Export: fetchOverview, fetchConsultants, fetchFiche, fetchRuns.
  Types copied from spec/data-contracts.md (turn every JSON key into a TS interface).
- Create src/tokens.ts: copy verbatim from prototype/jansa/tokens.js but export
  as TS. Keep applyTheme() function.
- src/main.tsx: wrap App in QueryClientProvider. Call applyTheme(localStorage
  .getItem('jansa_theme') || 'dark') before ReactDOM.createRoot.
- Update vite.config.ts to proxy /api to http://localhost:8000.

Run `npm run dev`. Confirm you see the default Vite page at localhost:5173.
```

---

## Prompt #3 — Port the prototype

```
Port the prototype into the frontend.

Source files (in ./prototype/jansa/):
  shell.jsx → src/shell/Shell.tsx, Sidebar.tsx, Topbar.tsx, FocusToggle.tsx,
              ThemeToggle.tsx, FocusCinema.tsx (one component per file)
  overview.jsx → src/pages/Overview.tsx + src/pages/overview/* for subcomponents
                 (KpiRow, HeroKpi, BestPerformerCard, VisaFlow, WeeklyActivity,
                  FocusPanel, FocusRadial, FocusByConsultant)
  consultants.jsx → src/pages/Consultants.tsx + src/pages/consultants/*
                    (MoexCard, PrimaryCard, SecondaryChip, Section)
  fiche_base.jsx → src/pages/ConsultantFiche.tsx + src/pages/fiche/*
                   (Masthead, HeroStats, Bloc1, Bloc2, Bloc3, Donut, SideList)

RULES:
- Convert .jsx → .tsx. Type every prop with interfaces.
- Replace window.X globals with ES imports.
- Rename any `const styles = {}` to component-specific names to avoid collision.
- Keep ALL styling inline (do not move to CSS files).
- Keep all SVG charts intact — do not swap for chart libs.
- Keep all CSS variable references (var(--bg) etc) — the theme system depends on them.

Keep mocks for now: create src/mocks.ts exporting CONSULTANTS, OVERVIEW,
FICHE_DATA from prototype/jansa/data.js. Pages import from mocks.ts.

Build a simple router (no react-router needed — the prototype uses a single
useState for active page). Preserve the Focus + Theme toggles.

Run `npm run dev`. Confirm every page renders identically to the prototype.
```

---

## Prompt #4 — Wire the API

```
Replace mock imports with real API calls, one page at a time.

1. Install @tanstack/react-query if not already.
2. In src/pages/Overview.tsx:
   Replace `import { OVERVIEW } from '../mocks'` with:
   const { data } = useQuery({ queryKey: ['overview'], queryFn: fetchOverview });
   if (!data) return <OverviewSkeleton/>;
   Create a subtle loading skeleton (shimmering cards) matching the layout.

3. Same pattern for Consultants.tsx → useQuery(['consultants'], fetchConsultants)
4. Same for ConsultantFiche.tsx → useQuery(['fiche', slug], () => fetchFiche(slug))

5. Delete src/mocks.ts.

6. Start backend on :8000 and frontend on :5173. Walk through every page and
   confirm data loads. Show me any errors verbatim.
```

---

## Prompt #5 — Calculator + GED

```
I'll paste my calculator.py now. Your job:

1. Copy it into backend/app/calculator.py, unchanged.
2. In backend/app/api.py, replace every mock response with a call to the
   corresponding calculator function:
   /overview → calculator.compute_overview(week_num)
   /consultants → calculator.list_consultants()
   /consultants/{slug}/fiche → calculator.compute_fiche(slug, week_num)
3. If the shapes don't match spec/data-contracts.md exactly, write a thin
   adapter layer in api.py — DO NOT modify calculator.py.
4. Pydantic-validate every response against the models.py schemas.

Then for AxeoBIM (the DMS):
5. In backend/app/ged_client.py, write an httpx-based async client with:
   - get_documents(since: datetime) → list[dict]
   - auth via env vars GED_URL, GED_USER, GED_PASSWORD
6. Add a /api/runs/trigger POST that:
   - Pulls new docs from GED
   - Re-runs calculator
   - Returns the new run_number
7. Add a APScheduler job that triggers every hour (configurable via env).

I will paste credentials into a .env file (gitignored). Write .env.example.
```

---

## Prompt #6 — Deploy

```
Production-ize:

1. backend/Dockerfile → multi-stage, no --reload, gunicorn+uvicorn workers.
2. frontend/Dockerfile → two stages:
   Stage 1: node:20-alpine, npm ci, npm run build.
   Stage 2: nginx:alpine, copy dist to /usr/share/nginx/html.
   Add nginx.conf that proxies /api to backend:8000.
3. docker-compose.yml for production:
   - backend service
   - frontend service (port 80)
   - shared .env
4. Write DEPLOY.md with:
   - How to build: docker compose build
   - How to run: docker compose up -d
   - How to see logs: docker compose logs -f
   - How to update: git pull && docker compose up -d --build
5. Run `docker compose up --build` locally. Open http://localhost and walk
   through every page. Confirm data loads, Focus + Theme toggles work,
   consultant-click navigates to fiche, Back button returns.

When that works, we're shipped.
```

---

## If you get stuck

Paste this: "The last step produced this error. Paste the relevant file,
explain the root cause in one sentence, propose a fix, apply it, re-run, and
confirm it works. Do not move on until green."
