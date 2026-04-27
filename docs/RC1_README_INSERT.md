# README RC1 Status Insert

> **Action for the user:** insert the markdown block below into the main repo's
> `README.md`, immediately **after the title and one-line tagline** and **before**
> the existing `## Quick Start` section. Do not rewrite the rest of the README.

---

## GF Updater V3 — RC1 Status

**RC1 READY** — frozen 2026-04-27 on a clean Run 0 baseline.

- ✅ **Clean Run 0 baseline** — single completed run, 33 registered artifacts, no polluted history.
- ✅ **`python main.py`** — full pipeline entrypoint; auto-builds Flat GED, rebuilds GF, generates `GF_TEAM_VERSION`.
- ✅ **`python app.py`** — JANSA connected desktop UI, artifact-first.
- ✅ **Flat GED auto-build** — produced into `output/intermediate/FLAT_GED.xlsx` on every run; users never need to provide it.
- ✅ **Artifact-first UI** — loads from registered run artifacts; raw rebuild is legacy fallback only.
- ✅ **`GF_TEAM_VERSION` auto-generation** — retry + fallback; registered as a run artifact.
- ✅ **Run history reset to clean Run 0** — see `docs/STEP17A_CLEAN_RUN0_RESET_REPORT.md` and `docs/RC1_RELEASE_NOTES.md`.

**Next phase:** Chain + Onion (locked until Gate 4 opens).

---
