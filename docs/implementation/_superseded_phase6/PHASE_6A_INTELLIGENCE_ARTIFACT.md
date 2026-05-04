# Phase 6A — Intelligence Artifact (`INTELLIGENCE_TAGS.csv`)

This MD is **self-contained**. An agent assigned only this phase can execute it cold without reading any other file in `docs/implementation/`.

> **Phase 6 has been split into four sub-phases (6A → 6B → 6C → 6D).** This is 6A. Do NOT proceed to 6B/6C/6D in the same implementation pass. After 6A merges and the user validates the artifact, the next phase MD is picked up separately.

---

## 1. Objective

Produce a deterministic per-document tag artifact, written by the pipeline at the end of every run, registered in `run_memory`, and consumable by future read-side endpoints.

Artifact path: `output/intermediate/INTELLIGENCE_TAGS.csv`.

This phase **only** delivers the artifact. No new app endpoints, no new UI page, no export, no localStorage. Those live in 6B / 6C / 6D respectively.

---

## 2. Risk

**HIGH on the pipeline side.** Touches a pipeline finalization step (or adds a new stage after finalize). Per repo rules, no pipeline edits without explicit approval.

If the agent finds it has to modify any other stage (read, normalize, version, route, write_gf, build_team_version, discrepancy, diagnosis), **stop and escalate** — this phase is purely additive at the end of the pipeline.

---

## 3. Standard Rules (embedded — do not skip)

### Tooling note — read before any investigation
Use the **Read tool** (not bash `wc`/`grep`/`cat`/`head`/`tail`) to verify file content, file size, or function presence in Windows-mounted source files (`app.py`, `src/reporting/*.py`, `src/pipeline/stages/*.py`, etc.). The Cowork sandbox's Linux mount caches a stale view of Windows files and has, in past sessions, falsely reported `app.py` as 864 lines when it was actually ~1200, and missed methods like `get_chain_onion_intel` that demonstrably existed. If a bash inspection contradicts the Read tool, the Read tool wins. Do not raise "repo is broken / method missing / file truncated" alarms from bash-only evidence — cross-check with Read first. Bash is fine for *executing* scripts (running `python main.py`, `pytest`, etc.); just don't use it to reason about source-file state. See `context/11_TOOLING_HAZARDS.md`.

### Priorities
1. App must always run.
2. Pipeline determinism is sacred. Same inputs → same outputs.
3. Backend stays source of truth.
4. Preserve working logic.
5. Minimal safe changes.
6. No fake certainty.

### Mandatory behavior
- Read the listed files fully before editing.
- Tag computation logic must reuse `src/reporting/document_command_center.py` (the existing per-document tag function). DO NOT redefine the tag taxonomy.
- The new sub-step / stage runs **after** `stage_finalize_run` finishes its current work, OR is implemented as a new stage `stage_intelligence_tags` registered after finalize. Choose one at the design alignment step.
- The artifact build is wrapped in `try/except`. If it fails, log the error and let the pipeline complete. The artifact's absence is a soft state handled by the read-side phases.
- The artifact must be **idempotent**: same run inputs → same artifact contents (same rows, same column order, same values). Row order: `numero ASC, indice ASC` for determinism.
- Artifact registered via `run_memory` artifact API (existing function). No new DB schema, no new table.

### Forbidden moves
- Do NOT modify any of: `stage_init_run`, `stage_read_flat`, `stage_read`, `stage_normalize`, `stage_version`, `stage_route`, `stage_report_memory`, `stage_write_gf`, `stage_build_team_version`, `stage_discrepancy`, `stage_diagnosis`. (You may add to `stage_finalize_run` or insert a new stage AFTER it.)
- Do NOT modify `src/flat_ged/`.
- Do NOT modify `src/run_memory.py` schemas.
- Do NOT modify `data/run_memory.db` schema.
- Do NOT redefine tag taxonomy. Reuse `document_command_center.py`.
- Do NOT mutate `dernier_df` columns (read only).
- Do NOT run the pipeline from inside Cowork. Hand off to the user.
- Do NOT add new dependencies.
- Do NOT do any UI work in this phase. UI is 6C.
- Do NOT add app.py endpoints in this phase. Endpoints are 6B.

### Risk policy
HIGH. The agent must:
1. Read all listed files.
2. Complete §7 Step 0 (design alignment) and **wait for explicit approval** before editing any pipeline file.
3. Apply changes: tag-builder module → pipeline wiring.
4. Hand off pipeline rerun to the user via a Claude Code prompt.
5. Validate the artifact contents (after user re-runs).
6. Stop here. Do not start 6B in the same pass.

---

## 4. Current State (Findings)

### 4a. Tag taxonomy
File: `src/reporting/document_command_center.py`. Per `README.md` §Document Command Center:

- Primary tags (exactly one per document):
  `Att Entreprise — Dans les délais`, `Att Entreprise — Hors délais`, `Att BET Primaire`, `Att BET Secondaire`, `Att MOEX — Facile`, `Att MOEX — Arbitrage`, `Clos / Visé`
- Secondary tags (multi-valued, optional):
  `Refus multiples`, `Commentaire manquant`, `Secondaire expiré`, `Très ancien`, `Cycle dépassé`, `Chaîne longue`

These are the only allowed values.

### 4b. Where computation happens today
The tag computation is per-document, called by `get_document_command_center(numero, indice, ...)`. It takes `RunContext` + a doc reference and returns the tag set. To produce a per-document artifact for ALL documents, choose:

- **Path A (preferred):** call the existing single-doc function in a loop over `dernier_df` rows. Cost ≈ O(n), n ≈ 2,800. Acceptable.
- **Path B:** refactor the helper into a vectorized batch function. Avoid unless A is too slow.

Confirm at design alignment.

### 4c. Pipeline insertion point
File: `src/pipeline/stages/stage_finalize_run.py`. Currently performs run finalization, GF_TEAM_VERSION artifact registration, and run-memory commits. Two options:

- **Option 1:** append a sub-step at the end of `stage_finalize_run` that builds and writes the artifact.
- **Option 2:** create a new file `src/pipeline/stages/stage_intelligence_tags.py` registered after finalize in the runner.

Decide at design alignment based on diff size. Heuristic: if the diff in `stage_finalize_run` would be ≤40 lines and reads cleanly, Option 1 is simpler. Otherwise Option 2.

---

## 5. User Value

- The artifact is the foundation for 6B (endpoints) and 6C (UI page).
- Treats tag classification as a deterministic, auditable, run-keyed output — not a runtime computation hidden behind a UI request.

---

## 6. Files

### READ (required, before any edit)
- `src/reporting/document_command_center.py` — full file. Locate the public per-document tag function.
- `src/reporting/data_loader.py` — confirm `RunContext.dernier_df` columns (read only)
- `src/pipeline/stages/stage_finalize_run.py` — full file
- `src/pipeline/runner.py`
- `src/pipeline/__init__.py`
- `src/pipeline/stages/__init__.py`
- `src/run_memory.py` — locate the artifact registration API used by other stages (read only — do not modify)
- `paths.py` (or wherever `OUTPUT_DIR` lives)
- `README.md` §Backend Architecture, §Output Artifacts, §Document Command Center, §What Not To Touch
- This MD

### MODIFY (after design alignment approval)
- One of:
  - `src/pipeline/stages/stage_finalize_run.py` (append sub-step) — Option 1
  - `src/pipeline/runner.py` + new file (Option 2 — see CREATE)

### CREATE
- `src/reporting/intelligence_builder.py` — new module exposing:
  ```python
  def build_intelligence_table(ctx) -> "pd.DataFrame":
      """Returns a DataFrame with the schema documented in §7 Step 0."""
  ```
- (Option 2 only) `src/pipeline/stages/stage_intelligence_tags.py` — thin stage that calls `build_intelligence_table`, writes CSV, registers artifact.

### DO NOT TOUCH
- Every other `stage_*.py`
- `src/flat_ged/`
- `src/run_memory.py` (read API only)
- `src/report_memory.py`, `src/team_version_builder.py`, `src/effective_responses.py`
- `src/chain_onion/` (entire directory)
- `src/reporting/document_command_center.py` business logic (only consume its public function; do not rename or rewrite)
- `src/reporting/aggregator.py`, `data_loader.py`, `focus_filter.py`, `focus_ownership.py`, `ui_adapter.py`, `consultant_fiche.py`, `contractor_fiche.py` — read only
- `data/run_memory.db`, `data/report_memory.db` schemas
- `runs/run_0000/`, `output/chain_onion/`
- `app.py` (no endpoint work in this phase — that's 6B)
- All UI files (no UI work in this phase — that's 6C)
- `output/exports/` (no export work — that's 6D)

---

## 7. Plan

### Step 0 — Design alignment (MANDATORY GATE)
Before touching any file in `src/pipeline/`:
1. Read all files listed in §6 READ.
2. Determine Path A vs Path B for tag computation (single-row loop vs batch).
3. Determine Option 1 vs Option 2 for pipeline insertion.
4. Confirm artifact filename: `output/intermediate/INTELLIGENCE_TAGS.csv`.
5. Confirm column schema (frozen below).
6. Restate the plan to the user with the exact file diff outline.
7. **Wait for explicit approval before editing any pipeline file.**

Frozen column schema:

| Column | Type | Source |
|---|---|---|
| `numero` | str | `dernier_df.numero` |
| `indice` | str | `dernier_df.indice` |
| `titre` | str | `dernier_df.titre` |
| `emetteur_code` | str | `dernier_df.emetteur` |
| `emetteur_name` | str | `resolve_emetteur_name(code)` (canonical, BEN→Bentin) |
| `lot` | str | `dernier_df.lot_normalized` (or `lot`) |
| `primary_tag` | str | from `document_command_center.py` |
| `secondary_tags` | str | comma-joined; empty string allowed |
| `stale_days` | int | `dernier_df._days_since_last_activity` |
| `days_to_deadline` | int or null | `dernier_df._days_to_deadline` |
| `last_action_date` | ISO date or null | computed |
| `focus_priority` | int 1–5 or null | `dernier_df._focus_priority` if populated |
| `focus_owner_tier` | str or null | `dernier_df._focus_owner_tier` |
| `primary_owner` | str or null | first element of `dernier_df._focus_owner` |

Row order: `numero ASC, indice ASC`.

### Step 1 — Build `src/reporting/intelligence_builder.py`
```python
from typing import TYPE_CHECKING
import pandas as pd

if TYPE_CHECKING:
    from .data_loader import RunContext

def build_intelligence_table(ctx: "RunContext") -> pd.DataFrame:
    """Per-document tag table. Schema frozen in PHASE_6A §7 Step 0."""
    # 1. Resolve helper imports lazily (avoid circular)
    from .document_command_center import compute_tags_for_doc   # actual symbol TBD; locate during reads
    try:
        from .contractor_fiche import resolve_emetteur_name
    except ImportError:
        resolve_emetteur_name = lambda c: c  # fallback if helper not yet centralized

    df = ctx.dernier_df
    if df is None:
        return pd.DataFrame(columns=[...])  # empty with correct headers

    rows = []
    for _, r in df.iterrows():
        try:
            tags = compute_tags_for_doc(ctx, r)   # adapt to actual signature
            primary = tags.get("primary_tag") or ""
            secondary = ",".join(tags.get("secondary_tags") or [])
        except Exception:
            primary, secondary = "", ""
        code = (r.get("emetteur") or "").strip()
        rows.append({
            "numero":          r.get("numero"),
            "indice":          r.get("indice"),
            "titre":           r.get("titre") or "",
            "emetteur_code":   code,
            "emetteur_name":   resolve_emetteur_name(code) or code,
            "lot":             r.get("lot_normalized") or r.get("lot") or "",
            "primary_tag":     primary,
            "secondary_tags":  secondary,
            "stale_days":      _to_int(r.get("_days_since_last_activity")),
            "days_to_deadline": _to_int_or_null(r.get("_days_to_deadline")),
            "last_action_date": _to_iso(r.get("last_real_activity_date") or r.get("response_date") or r.get("submittal_date")),
            "focus_priority":  _to_int_or_null(r.get("_focus_priority")),
            "focus_owner_tier": r.get("_focus_owner_tier"),
            "primary_owner":   _first_or_null(r.get("_focus_owner")),
        })
    out = pd.DataFrame(rows)
    out = out.sort_values(["numero", "indice"]).reset_index(drop=True)
    return out
```

Helpers `_to_int`, `_to_int_or_null`, `_to_iso`, `_first_or_null` are local to the module; do not duplicate from elsewhere.

If the existing tag function in `document_command_center.py` does not accept a row but only `(numero, indice)`, call it that way per-row. Performance budget: < 10 seconds total. If exceeded, stop and consider a batch refactor only with approval.

### Step 2 — Wire into the pipeline (Option 1 OR Option 2)

**Option 1** — append in `stage_finalize_run.py`:
```python
# At the end of stage_finalize_run, after existing finalize work:
try:
    from reporting.intelligence_builder import build_intelligence_table
    df = build_intelligence_table(ctx)
    out_path = OUTPUT_DIR / "intermediate" / "INTELLIGENCE_TAGS.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    register_artifact(run_id, "INTELLIGENCE_TAGS", str(out_path))   # use the actual existing API name
except Exception:
    import logging, traceback
    logging.getLogger(__name__).warning("Intelligence artifact build failed; pipeline continues.\n" + traceback.format_exc())
```

**Option 2** — `stage_intelligence_tags.py`:
```python
from reporting.intelligence_builder import build_intelligence_table
# ... uses the same try/except + register_artifact pattern
```
Then add to runner stage list AFTER `stage_finalize_run`.

### Step 3 — Hand off pipeline rerun to user
Provide this Claude Code prompt:
```
TASK: Re-run pipeline so the new INTELLIGENCE_TAGS artifact is produced.
cd "C:\Users\GEMO 050224\Desktop\cursor\GF updater v3"
python main.py
Verify:
  ls -la output/intermediate/INTELLIGENCE_TAGS.csv
  python -c "import pandas as pd; df=pd.read_csv('output/intermediate/INTELLIGENCE_TAGS.csv'); print(df.shape); print(df.head()); print(df['primary_tag'].value_counts())"
Bring back: shape, head(), primary_tag distribution, run completion log message.
```
DO NOT run the pipeline inside Cowork.

### Step 4 — Validate artifact (after user re-runs)
After the user reports back:
- Check the row count is plausible (≈ docs count, e.g. 2,800).
- Check every primary_tag value is in the allowed set (7 values).
- Check column order matches the frozen schema.
- Check row order is `numero ASC, indice ASC`.
- Run the pipeline a SECOND time (user does this) and confirm `diff` of `INTELLIGENCE_TAGS.csv` shows zero lines changed (idempotency).

### Step 5 — Stop
Do NOT start 6B in the same pass. Report completion. Wait for the user to pick up Phase 6B.

---

## 8. Validation

| Check | How |
|---|---|
| Module compiles | `python -m py_compile src/reporting/intelligence_builder.py` |
| Pipeline file compiles | `python -m py_compile src/pipeline/stages/stage_finalize_run.py` (and stage_intelligence_tags.py if Option 2) |
| App starts | `python app.py` opens — no UI changes here, but the app must boot |
| Artifact present (after user re-run) | `output/intermediate/INTELLIGENCE_TAGS.csv` exists |
| Schema correct | Column headers match §7 Step 0 frozen list, in that order |
| Row count plausible | ≈ docs count |
| Primary tags valid | All values ∈ {7 allowed} |
| Idempotency | Run pipeline twice → CSV byte-identical OR equivalent ignoring trailing newline (verify with `cmp` or `md5sum`) |
| No regression | All other artifacts (`GF_V0_CLEAN.xlsx`, `GF_TEAM_VERSION.xlsx`, `DISCREPANCY_REPORT.xlsx`) retain identical columns, row counts, and business-field values across the change |
| Failure soft | Force `compute_tags_for_doc` to raise once; pipeline still completes; artifact missing or partial; log entry recorded |

---

## 9. Cowork Handoff Prompt (paste-ready)

```
Objective:
Phase 6A — Produce a deterministic per-document tag artifact `output/intermediate/INTELLIGENCE_TAGS.csv` at the end of every pipeline run. No app endpoints, no UI page, no export, no localStorage in this phase. Those live in 6B/6C/6D — pick those up separately.

Repository: GFUP_Backend / GF Updater v3 / 17&CO Tranche 2. Risk level: HIGH (pipeline edit).

CRITICAL GATE — design alignment:
Before editing any file in src/pipeline/, complete a design alignment step:
1. Read all files listed below.
2. Decide Path A (per-row tag function loop) vs Path B (batch refactor — avoid unless A is too slow).
3. Decide Option 1 (sub-step at end of stage_finalize_run) vs Option 2 (new stage stage_intelligence_tags after finalize).
4. Confirm filename `output/intermediate/INTELLIGENCE_TAGS.csv` and the frozen column schema (see PHASE_6A §7 Step 0).
5. Restate the plan to the user with the file-level diff outline.
6. Wait for explicit approval before editing any pipeline file.

Read fully before any edit:
- src/reporting/document_command_center.py (locate per-document tag function)
- src/reporting/data_loader.py (RunContext.dernier_df schema, read only)
- src/pipeline/stages/stage_finalize_run.py
- src/pipeline/runner.py
- src/pipeline/__init__.py
- src/pipeline/stages/__init__.py
- src/run_memory.py (artifact registration API, read only)
- paths.py (OUTPUT_DIR)
- README.md §Backend Architecture, §Output Artifacts, §Document Command Center, §What Not To Touch
- docs/implementation/PHASE_6A_INTELLIGENCE_ARTIFACT.md (this spec)

Do not touch:
- Any other stage_*.py — pipeline order is frozen except for an additive step at the end
- src/flat_ged/
- src/run_memory.py / src/report_memory.py / src/team_version_builder.py / src/effective_responses.py — schemas unchanged
- src/chain_onion/ — entire directory off-limits
- src/reporting/document_command_center.py business logic (read only — only consume its public tag function)
- src/reporting/aggregator.py, data_loader.py, focus_filter.py, focus_ownership.py, ui_adapter.py, consultant_fiche.py, contractor_fiche.py — read only
- data/run_memory.db, data/report_memory.db schemas
- runs/run_0000/, output/chain_onion/
- app.py (NO endpoints in 6A)
- All UI files (NO UI in 6A)
- output/exports/ (NO export in 6A)

Implement (after approval at the design alignment gate):

1. Create src/reporting/intelligence_builder.py exposing build_intelligence_table(ctx) -> DataFrame.
   Schema (frozen): numero | indice | titre | emetteur_code | emetteur_name | lot | primary_tag | secondary_tags | stale_days | days_to_deadline | last_action_date | focus_priority | focus_owner_tier | primary_owner.
   Row order: numero ASC, indice ASC.
   Reuse the per-document tag function from src/reporting/document_command_center.py — never redefine taxonomy.
   Use resolve_emetteur_name from src/reporting/contractor_fiche.py if present, else fallback to code as name.

2. Wire into pipeline (Option 1: append sub-step in stage_finalize_run; OR Option 2: new stage_intelligence_tags after finalize). Wrap in try/except — failure logs a warning and lets the pipeline complete. Write to output/intermediate/INTELLIGENCE_TAGS.csv. Register via the existing run_memory artifact API.

3. Hand off pipeline rerun to user via Claude Code prompt. NEVER run pipeline in Cowork.

4. After user re-runs, validate:
   - artifact exists, schema matches §7 Step 0, row count plausible, primary_tag values ∈ allowed set
   - idempotency: second run produces byte-identical (or equivalent) CSV
   - all other pipeline outputs retain identical columns/row counts/business-field values

5. STOP. Do not start 6B. Report completion and wait for the user to pick up Phase 6B.

Pipeline rerun handoff prompt (give to user once code lands):
---
TASK: Re-run pipeline to produce INTELLIGENCE_TAGS artifact.
cd "C:\Users\GEMO 050224\Desktop\cursor\GF updater v3"
python main.py
Verify:
  ls -la output/intermediate/INTELLIGENCE_TAGS.csv
  python -c "import pandas as pd; df=pd.read_csv('output/intermediate/INTELLIGENCE_TAGS.csv'); print(df.shape); print(df.head()); print(df['primary_tag'].value_counts())"
Then run pipeline a SECOND time and check `diff` between the two CSVs is empty (idempotency).
Bring back: shape, head(), tag distribution, idempotency check result.
---

Hard rules:
- Backend stays source of truth. NO UI work in 6A. NO endpoints in 6A.
- Pipeline determinism is sacred. The new step is purely additive at the end.
- Tag taxonomy lives in document_command_center.py — never redefined.
- Failure soft: if tag computation throws, log and continue; pipeline must always finish.
- Re-run pipeline handed off to user — never run from Cowork.
- Stop and escalate if design forces edits to any frozen module.
- Do NOT proceed to 6B in the same implementation pass.
```

---

## 10. Context Update (after merge)

- `context/02_DATA_FLOW.md` — note `INTELLIGENCE_TAGS.csv` produced after `stage_finalize_run`.
- `context/04_PIPELINE_STAGES.md` — append the new sub-step or stage to the order list.
- `context/05_OUTPUT_ARTIFACTS.md` — add the new artifact row.
- `context/06_EXCEPTIONS_AND_MAPPINGS.md` — confirm tag taxonomy source-of-truth is `document_command_center.py`.
- `context/10_VALIDATION_COMMANDS.md` — add idempotency check command.
- `README.md` §Output Artifacts — add INTELLIGENCE_TAGS.csv row.

If `context/` is missing the file, skip — do not create new context files in this phase.

---

## 11. Done Definition

- App launches cleanly.
- Pipeline produces `output/intermediate/INTELLIGENCE_TAGS.csv` deterministically.
- All other pipeline outputs unchanged in schema and business fields.
- Idempotency verified.
- Failure soft (tag throw doesn't break pipeline).
- Diff scoped to: `src/reporting/intelligence_builder.py` (new), `src/pipeline/stages/stage_finalize_run.py` (Option 1) OR `src/pipeline/stages/stage_intelligence_tags.py` (new) + `src/pipeline/runner.py` (Option 2).
- 6B / 6C / 6D NOT started.
