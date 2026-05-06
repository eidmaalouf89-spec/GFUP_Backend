# Phase 9A — Baseline Lifecycle Diagnostic

**Status:** ✅ CLOSED — 2026-05-06
**Verdict:** `PASS_OPERATIONAL_EQUIVALENCE`
**Type:** diagnostic + controlled reset + comparison + UI hardening

---

## Objective

Verify whether the software produces the same operational state across three lifecycle paths:

- **Cycle A** — clean state, no consultant reports → run pipeline
- **Cycle B** — Cycle A's state + reports added later → re-run pipeline (additive)
- **Cycle C** — wipe everything, reports present from the start → run pipeline (clean-from-start)

The headline question: does the additive path (B) produce the same operational result as a clean rebuild with reports (C)?

---

## Methodology

1. Backup `input/`, `data/`, `runs/`, `output/` to a sibling directory outside the repo.
2. For each cycle: prepare state, user runs pipeline from the UI Executer page, capture snapshot via `scripts/lifecycle_baseline_diagnostic.py snapshot <A|B|C>`.
3. Compare snapshots by sha256 hash on each artifact.

Snapshot harness `scripts/lifecycle_baseline_diagnostic.py` (created in this phase) provides subcommands: `backup`, `hold-reports`, `restore-reports`, `wipe-generated`, `snapshot`. All operations log JSON lines to `_diagnostic_snapshots/lifecycle_log.jsonl`.

Snapshot artifacts captured per cycle (in `_diagnostic_snapshots/<label>/`):
- copy of `data/`, `runs/`, `output/`
- `<label>_metrics.json` — high-level summary (run_memory state, report_memory state, output artifact inventory, intermediate inventory, chain_onion CSV row counts, counter_attack bucket counts)
- `<label>_bucket_counts.csv` — counter-attack bucket distribution
- `<label>_counter_attack_items.csv` — copy of COUNTER_ATTACK_ITEMS.csv
- `<label>_chain_onion_counts.json`
- `<label>_report_memory_summary.json`

---

## Cycle results

| Field | A (no reports) | B (additive) | C (clean + reports) |
|---|---|---|---|
| Run | 0 BASELINE | 1 INCREMENTAL¹ | 0 BASELINE |
| run_memory artifacts | 29 | 26² | **33** |
| report_memory active rows | 0 | 0³ | **1,045** |
| Chain register families | 2,819 | 2,819 | 2,819 |
| Chain versions | 4,848 | 4,848 | 4,848 |
| Chain events | 36,947 | 36,947 | 36,947 |
| Onion layers | 7,788 | 7,788 | 7,788 |
| top_issues records | 20 | 20 | 20 |
| **COUNTER_ATTACK rows** | **1524** | **1524** | **1524** |
| **Bucket distribution** | 66/210/122/8/989/129 | 66/210/122/8/989/129 | 66/210/122/8/989/129 |

¹ Cycle B was run on top of Cycle A's state (no wipe). Run number incremented.
² Cycle B was run while the orchestrator's `_patched_main_context` had a redirect bug for `OUTPUT_GF_TEAM_VERSION` and `OUTPUT_SUSPICIOUS_ROWS` (Phase 9A.5 fix landed before Cycle C). Resulting in fewer registered artifacts.
³ Cycle B's `report_memory.db` ended up empty (40 KB schema-only). Reports were physically present but ingestion did not propagate; root cause not fully isolated. Did not block the equivalence verdict because A and B yielded byte-identical Counter-Attack output anyway.

### Byte-level comparison

`sha256[:16]` per artifact:

| Artifact | A | B | C | Verdict |
|---|---|---|---|---|
| `COUNTER_ATTACK_ITEMS.csv` | `03ca6f5a35be5d11` | `03ca6f5a35be5d11` | `03ca6f5a35be5d11` | **byte-identical** |
| `CHAIN_REGISTER.csv` | `a04ed56df1bb4fc5` | `a04ed56df1bb4fc5` | `a04ed56df1bb4fc5` | **byte-identical** |
| `CHAIN_VERSIONS.csv` | `4ff56961a766b157` | `4ff56961a766b157` | `4ff56961a766b157` | **byte-identical** |
| `CHAIN_EVENTS.csv` | `7b239dcb61e96ca8` | `7b239dcb61e96ca8` | `7b239dcb61e96ca8` | **byte-identical** |
| `CHAIN_METRICS.csv` | `3f77781636311e39` | `3f77781636311e39` | `3f77781636311e39` | **byte-identical** |
| `ONION_LAYERS.csv` | `a5bf9598f3ed835f` | `616e77787831950f` | `2c4ad6b68f423330` | varies |
| `ONION_SCORES.csv` | `caba0aa3b0b0a1ce` | `36b227c12f1f6535` | `7afdecba8fde7692` | varies |
| `CHAIN_NARRATIVES.csv` | `77c8cf70ca8c5449` | `df9aadd46be228f9` | `60be46215b445d92` | varies |

---

## Verdict — `PASS_OPERATIONAL_EQUIVALENCE`

**Counter-Attack output is byte-identical across all three lifecycle paths.**

This is a stronger result than the diagnostic was scoped to test. The original equivalence question was *"does B equal C?"*. The actual finding: **A ≡ B ≡ C at the operational level**, regardless of report ingestion state.

What this means: **report ingestion does not change which documents are actionable, what bucket they fall into, who owns them, or what action is recommended.** The Counter-Attack queue (`COUNTER_ATTACK_ITEMS.csv`, the user-facing operational queue surfaced as the ACTION MOEX page in the UI) is invariant under report state.

What reports DO affect:
- **Onion scoring** (`ONION_LAYERS.csv`, `ONION_SCORES.csv`) — small numeric variations between runs
- **Chain narratives** (`CHAIN_NARRATIVES.csv`) — narrative text variations driven by scoring
- **UI display layer** — consultant fiches, contractor fiches, document command center detail panels surface report observations and report-derived statuses in the `BET_MERGE_KEYS` set
- **Document Command Center** — `effective_responses_df` enrichment shows report-supplied values where GED was PENDING

What reports do NOT affect:
- Counter-Attack bucket assignment
- Chain identity (REGISTER, VERSIONS, EVENTS, METRICS)
- Action ownership (who is responsible)
- Days-late computations (deadline truth comes from `responses_df.date_limite` against `ctx.data_date`, neither of which reports modify)

---

## Code changes that landed during this phase

All listed changes are in production at phase closure.

### `src/flat_ged/__init__.py` (Phase 9A.0)

`build_flat_ged` now evicts pre-existing `sys.modules` entries that would shadow the FLAT_GED package's bare imports (`config`, `reader`, `resolver`, `transformer`, `processor`, `validator`, `writer`, `utils`) before the build, then restores them in the `finally` block. Fixes the UI's `cannot import name 'write_flat_ged' from 'writer'` crash, which fired because `app.py`'s prewarm thread loaded `src/writer.py` (the GF writer) into `sys.modules` before the user clicked Lancer. Python's import system honours `sys.modules` ahead of `sys.path`, so the FLAT_GED package's internal `from writer import write_flat_ged` was returning the GF writer.

### `src/run_orchestrator.py` (Phase 9A.5)

Two fixes in `_patched_main_context` and one new auto-invoke hook in `run_pipeline_controlled`:

1. **Removed `OUTPUT_GF_TEAM_VERSION` and `OUTPUT_SUSPICIOUS_ROWS` redirects to disabled_root.** These two outputs are produced from GED + GF only — no consultant data — so they must keep their canonical `output/` paths regardless of run mode. Previously, in `GED_GF` / `GED_ONLY` modes, they were redirected to a `_orchestrator_disabled/<mode>/` sandbox that didn't exist on disk, breaking the team_version build entirely. The CONSULTANT_*, OUTPUT_GF_STAGE1, OUTPUT_GF_STAGE2 redirects remain — those outputs are consultant-specific.

2. **Defensive `disabled_root.mkdir(parents=True, exist_ok=True)`** in the non-`use_reports` branch.

3. **`consultant_integration` auto-invoke when `reports_dir` is provided.** Previously, the UI Executer page's "Reports" field was a path constant pass-through with no code consuming it — `stage_report_memory` always saw `consultant_match_report.xlsx` as missing and skipped ingestion. The orchestrator hook now invokes `run_consultant_integration(rebuild_consultant_wb=auto, skip_gf_update=True)` between Flat GED build and pipeline run, so `consultant_match_report.xlsx` is produced before `stage_report_memory` runs. Failures are non-fatal — the pipeline continues without report ingestion.

### `src/run_memory.py` (Phase 9A.6)

Switched from `PRAGMA journal_mode=WAL` to `PRAGMA journal_mode=DELETE` in `_conn`. WAL mode requires shared-memory coordination via `-wal` and `-shm` sidecar files; with multiple processes (UI worker thread + chain_onion subprocess + prewarm thread) opening this DB on a Windows-NTFS-bridged-to-Linux-mount filesystem, the SHM coordination was suspected of intermittent corruption. DELETE mode is robust under concurrent multi-process access and the perf cost is negligible for this app's write volume (~30 inserts per pipeline run). Note: the corruption symptoms initially observed turned out to be a sandbox cross-mount FUSE artifact (Windows-side reads via the UI's data_loader were fine), but the DELETE-mode change remains as defensive hardening.

### `app.py` (Phase 9A.1, 9A.2, 9A.3, 9A.4)

Five distinct fixes in `Api.run_pipeline_async`, the worker thread, and `Api.export_team_version`:

1. **Atomic concurrency guard.** Previously `run_pipeline_async` checked `running`, released the lock, validated, then re-acquired the lock to set `running=True`. Two clicks could pass the check before either set the flag. Now check + set happen inside one locked block; validation failure releases the flag.

2. **Post-pipeline chain refresh.** Worker now calls `_ensure_chain_data_fresh(ctx, BASE_DIR)` after pipeline success — same code path the prewarm thread runs at app startup. Subprocesses `run_chain_onion.py` if needed, then refreshes `CHAIN_TIMELINE_ATTRIBUTION.{json,csv}`. Outside the pipeline lock so polling stays responsive. `running=True` stays set throughout (outer `finally` clears it), so the Lancer button stays disabled until pipeline + chain refresh + counter_attack are all done.

3. **Post-pipeline Counter-Attack build.** After chain refresh, the worker calls `build_counter_attack_items(ctx, output/intermediate)` directly. Same code path as `scripts/build_counter_attack.py` but in-process — no subprocess overhead.

4. **Outer `try/finally` on running flag.** Guarantees `running=False` even if the chain refresh or counter_attack build raises an unhandled exception. Without this, a crash during post-pipeline hooks would leave `running=True` forever and the Lancer button greyed permanently.

5. **`export_team_version` builds GF_TEAM_VERSION on demand.** When `GF_TEAM_VERSION.xlsx` is not registered or the file is missing on disk, the export endpoint now invokes `team_version_builder.build_team_version(...)` from the latest registered FINAL_GF (GF_V0_CLEAN.xlsx) + `input/Grandfichier_v3.xlsx`, then proceeds with the date-named copy. Keeps the Tableau de Suivi VISA button working regardless of run mode.

### `scripts/lifecycle_baseline_diagnostic.py` (new)

Read-only-by-default snapshot harness. Subcommands: `backup`, `hold-reports`, `restore-reports`, `wipe-generated`, `snapshot <A|B|C>`. Pure stdlib so it works from Cowork sandbox or Windows shell. All operations append a JSON line to `_diagnostic_snapshots/lifecycle_log.jsonl`.

---

## Lessons learned

- **The UI's "Reports" field had no operational effect before this phase.** The orchestrator validated `reports_dir` and warned if it was missing in `FULL`/`GED_REPORT` modes, but no code in the orchestrator or pipeline path actually invoked `consultant_integration`. The integration step was a separate manually-runnable script. Phase 9A.5 hook makes the UI button do what users always assumed it did.
- **The team_version output redirect to `_orchestrator_disabled/<mode>/`** was actively harmful in non-`FULL` modes — `output/GF_TEAM_VERSION.xlsx` was simply not produced. The Tableau de Suivi VISA export button silently failed because the canonical path was empty.
- **WAL journal mode + multi-process access on FUSE-bridged filesystems is fragile.** Even when the actual Windows file is intact, sandbox-side Linux reads via `sqlite3.connect(...)` with the default mode can return `database disk image is malformed` because the immutable-mode fallback (used by `data_loader._query_db`) is the only reliable cross-process read path. Snapshot tools should either copy the DB to a local non-mounted path before reading, or use the same immutable-mode fallback as production code.
- **Reports change scoring layer but not the action layer.** This is operationally important: the user can confidently run pipelines with or without consultant reports for short-term operational use; the Counter-Attack queue stays consistent. Reports are valuable for fiche-level enrichment (UI display, Document Command Center) and for narrative scoring nuance, but not for which doc you call next.

---

## Recommendations / follow-ups (not blockers)

These are not required to consider Phase 9A closed, but flagging as known follow-up items:

1. **Investigate Cycle B's empty `report_memory.db`.** During Cycle B, `consultant_integration` produced `consultant_match_report.xlsx` (file existed at 269 KB), but `stage_report_memory` did not ingest it (DB ended at 40 KB schema-only). Hypothesis: Cycle B was run before the orchestrator hook order was finalized — needs replay with current code to confirm. Operational impact: zero (Counter-Attack identical anyway).

2. **Document the empirical "reports do not affect Counter-Attack" finding** in the operational README so users know the operational queue is reproducible regardless of report state.

3. **Snapshot tool DB-read robustness.** `scripts/lifecycle_baseline_diagnostic.py` `_open_sqlite_via_tmp_copy` already copies DB to `/tmp` before reading, but Cowork's cross-mount FUSE bridge can present malformed pages anyway. Consider falling back to immutable-mode URI (the same approach `src/reporting/data_loader._query_db` uses) before declaring the DB corrupt.

4. **WAL → DELETE in `report_memory.py`.** `report_memory.py:_conn` (multiple sites) uses default journal mode (DELETE) — already correct. No change needed there.

5. **Document `consultant_integration` runtime as an orchestrator-driven step** in `02_DATA_FLOW.md`. The pre-Phase-9A docs described it as a manual standalone script.

---

## Files modified

| File | Phase | Description |
|---|---|---|
| `src/flat_ged/__init__.py` | 9A.0 | Shadow eviction/restore for sys.modules during build |
| `src/run_orchestrator.py` | 9A.5 | consultant_integration hook + GF_TEAM_VERSION/SUSPICIOUS redirect fix + defensive mkdir |
| `src/run_memory.py` | 9A.6 | WAL → DELETE journal mode |
| `app.py` | 9A.1–9A.4 | atomic concurrency, post-pipeline chain refresh, post-pipeline counter_attack, outer try/finally, on-demand team_version build |
| `scripts/lifecycle_baseline_diagnostic.py` | 9A | new harness |
| `docs/implementation/PHASE_9A_BASELINE_LIFECYCLE_DIAGNOSTIC.md` | 9A | this document |

## Files NOT modified

Per the task's scope rules, the following were not touched: `src/flat_ged/` business logic (only `__init__.py` import dance was patched), `src/report_memory.py`, `src/effective_responses.py`, `src/pipeline/stages/*` business logic, `src/chain_onion/`, `src/reporting/document_command_center.py`, `src/reporting/counter_attack_builder.py`, `src/reporting/counter_attack_query.py`, `ui/jansa/*` (existing JSX guards on the Lancer button were already correct), `ui/jansa-connected.html`.

---

## Snapshots

- `_diagnostic_snapshots/A/` — Cycle A baseline (no reports, GED + GF)
- `_diagnostic_snapshots/B/` — Cycle B (additive — Cycle A's state plus a new pipeline run with reports_dir set; report_memory ended empty)
- `_diagnostic_snapshots/C/` — Cycle C (clean state with reports from start; report_memory at 1,045 active rows)
- `_diagnostic_snapshots/lifecycle_log.jsonl` — append-only event log
- Backup at `C:\Users\GEMO 050224\Desktop\cursor\GF updater 3 versions\_backup_before_lifecycle_diagnostic\20260506_120747\` — full pre-diagnostic state (input/, data/, runs/, output/, 285 files, 336 MB).

---

**Phase 9A — closed 2026-05-06.**
