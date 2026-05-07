#repo-map #open-items #risks #backlog

# Open Questions and Risks

> Only items documented in `README.md`, `context/07_OPEN_ITEMS.md`, `context/00_PROJECT_MISSION.md`, or code.
> No speculation.

---

## Documented open items (from `context/07_OPEN_ITEMS.md` and README)

### D-003 — RAW → FLAT SAS REF projection gap (upstream, deferred)

- **What:** L0 RAW GED has 836 SAS REF rows; L1 FLAT GED has 284. Phase 8B explained 99.3% (830/836 rows).
- **6 remaining:** UNEXPLAINED rows in the 28xxx/A C1 cluster
- **Status:** Upstream of Phase 8 scope; `src/flat_ged/transformer.py` is on do-not-touch list
- **Risk if ignored:** The L1 SAS REF count is structurally incomplete; SAS REF rate analytics undercount real history

### D-006 — AAI 1-row mystery

- **What:** One AAI row discrepancy between RAW and FLAT GED; cause unconfirmed
- **Status:** Under investigation; Phase 8 deferred item
- **Risk:** May represent a genuine RAW→FLAT transformation inconsistency

### D-010 — Route `_precompute_focus_columns` through `resolve_visa_global`

- **What:** Phase 8A item — `_precompute_focus_columns` currently computes `visa_global` independently; should route through the authoritative `resolve_visa_global` path (same as aggregator after Phase 8 Step 3)
- **Status:** Medium-risk hardening; deferred post-Phase 8A

### H38 — Escalated chain count > 25% of live chains

- **What:** `escalated_chain_count = 2453 > 25% of live_chains = 1968` — triggers WARN in Chain+Onion validation harness
- **Status:** Pre-existing; would need operational review of escalation-trigger thresholds in `onion_scoring.py`
- **Risk:** WARN-only, not FAIL; escalation thresholds may need calibration

---

## Phase 6 (Intelligence layer) — partially realized

- **What:** `PHASE_6A_INTELLIGENCE_ARTIFACT.md`, `6B`, `6C`, `6D` are implemented (Counter-Attack/Action MOEX wired and live)
- **The broader Phase 6 vision** (full Intelligence UI page surfacing chain narratives, scores, and Onion analytics) is listed in README as "the next killer module work-stream"
- **What's NOT yet in the UI:** `CHAIN_NARRATIVES.csv`, full Onion score visualization, the 24+ unused `query_hooks.*` functions

---

## Known UI stubs

From `context/00_PROJECT_MISSION.md §Current pain points`:

| Page | Status |
|---|---|
| Discrepancies | `<StubPage title="Écarts" …>` — no backend consumer yet |
| Settings | `<StubPage title="Paramètres" …>` — no backend consumer |
| Reports (most) | Only "Tableau de Suivi VISA" export wired; "Autres rapports" is stub (partially replaced by Pack Audit IA in Phase 6D) |

---

## Mapping.xlsx — unclear role

- Present in `input/`
- UI Executer page exposes a "Mapping" file picker
- `app.Api.run_pipeline_async` does NOT pass it to the orchestrator
- Comment in JSX line 277: `"informatif — non transmis au backend"`
- May be the source for hardcoded values refreshed periodically
- **Risk:** Users may expect the file picker to do something — it doesn't

---

## FLAT_GED_MODE default not flipped

- `FLAT_GED_MODE = "raw"` is the static default in `paths.py`
- Overridden to `"flat"` by orchestrator at runtime
- Default not yet flipped to avoid breaking scripts that import `paths.py` directly
- **Risk:** A script that imports `paths.py` without going through the orchestrator will use raw mode

---

## `output/` contains stale validation artifacts

From `context/00_PROJECT_MISSION.md §Current pain points`:
- Folders `parity/`, `parity_raw_r1/`, `parity_raw_run1/`, `parity_raw_run2/`, `step9/legacy/`
- `tmp63o7zaid.xlsx`, `tmpxkmaioec.db`, `tmpyw_386pd.db` at repo root
- No production code references them at runtime
- **Risk:** Confuse artifact picture; no blocking issue

---

## TEMPORARY_COMPAT_LAYER markers in `stage_read_flat.py`

- Cosmetic markers indicating transition code that should be cleaned up
- Not functional issues
- **Risk:** None at runtime; cosmetic

---

## `WorkflowEngine.responses_df` dual-attribute fragility (ongoing)

- The two attributes sharing a name-pattern (`ctx.workflow_engine.responses_df` vs `ctx.responses_df`) is a structural fragility
- Every new analytics module must explicitly choose the correct frame
- **Risk:** New modules written without awareness of H-3 will silently get wrong SAS counts

---

## Chain+Onion not registered in run_memory.db

- Chain+Onion outputs (`output/chain_onion/`) are NOT keyed to a specific run number
- If FLAT_GED is regenerated without re-running Chain+Onion, the two layers drift
- `chain_onion_source_check.json` (WARN-only) detects this
- **Risk:** Focus narrowing and DCC Chronologie from out-of-sync data

---

## Gate G1 — Final Acceptance Gate (pending)

- From `README.md §Gate Status`: `G1 — Final Acceptance Gate — Live portfolio run against real output artifacts — ⏳ PENDING`
- Not a blocker for current use; a sign-off requirement for release quality

---

---

## Operational dashboard redesign — open follow-ups (2026-05-07)

> Cross-reference: `docs/implementation/OPERATIONAL_DASHBOARD_REDESIGN.md`.

### OD-01 — Action-bucket coverage gap (1,659 rows)

Of the 2,460 operational rows, 1,659 currently have no `action_bucket` assignment
in `COUNTER_ATTACK_ITEMS.csv`. Action MOEX covers only the 1,524 curated rows.
Extending bucket coverage to the unassigned 1,659 rows is a follow-up phase, out of
scope for the operational dashboard redesign.

### OD-02 — `*.pre_patch_backup` housekeeping

`app.py.pre_patch_backup`, `src/reporting/aggregator.py.pre_patch_backup`, and
`ui/jansa/overview.jsx.pre_patch_backup` are present in the working tree but not
covered by `.gitignore`. Housekeeping: add `*.pre_patch_backup` to `.gitignore` or
delete the backup files after confirming patch stability.

---

**Related:** [[11_DEBUGGING_SEAMS]] · [[13_SAFE_DEBUGGING_PROTOCOL]] · [[09_ACTION_MOEX_COUNTER_ATTACK]]

*Back to [[00_START_HERE]]*
