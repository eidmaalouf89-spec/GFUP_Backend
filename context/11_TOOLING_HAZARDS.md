# 11 — Tooling Hazards (Cowork / Cross-Mount Sandbox)

This file documents tooling pitfalls observed during Cowork sessions on this repo. Read this before any investigation that depends on file state, repo structure, or git status.

---

## H-1 — Sandbox bash sees a stale/truncated view of Windows-mounted source files

**What it looks like.** `wc -l app.py` returns 864 when the file is actually ~1200 lines. `grep -n "def get_chain_onion_intel" app.py` returns no matches when the function exists at line 1070. `cat`, `head`, `tail`, `head -n N`, file size in `ls -la` — all stale. `git status`, `git diff` may be misleading too.

**Root cause.** The repo lives on Windows (`C:\Users\GEMO 050224\Desktop\cursor\GF updater v3\`). The Cowork sandbox is Linux. The Windows folder is exposed to the sandbox through a host-side bind/share at `/sessions/<session>/mnt/GF updater v3/`. The cross-OS mount caches metadata and content for performance and has no inotify channel back to Windows. After certain editor write patterns (atomic-replace saves, large appends from a different session) the Linux mount can hold a stale snapshot until it is forced to re-stat. Bash inherits that snapshot and produces wrong answers.

**The two read paths in this sandbox are not equivalent.**

| Tool | Path | Cache behavior | Authority for reading file state |
|---|---|---|---|
| `Read`, `Edit`, `Write` (file tools) | Cowork host bridge → live Windows disk | None observed | ✅ Authoritative |
| `mcp__workspace__bash` (`wc`, `grep`, `cat`, etc.) | Linux mount projection of the Windows share | Cached, can be stale | ❌ Not reliable for content/size of mounted source files |

The system prompt itself flags this: *"Paths in bash differ from what file tools (Read/Write/Edit) see."*

**Operational rules — non-negotiable.**

1. **For "what is in the file?" questions, use the `Read` tool. Never use bash to verify file content, file size, function existence, line counts, or "did this method get added?" Use Read.**
2. Use bash for **execution** (running `python main.py`, `pytest`, etc.) and for actions where Linux is not reading Windows source (e.g. operating on artifacts already produced under `/sessions/<session>/mnt/outputs/`). Bash is fine when the script itself runs and produces fresh output.
3. **If a bash inspection produces a surprising result that affects decision-making, cross-check with the Read tool against the same byte range BEFORE drawing conclusions.** Surprising = "this method should be here but I can't find it", "this file is unexpectedly short", "this commit is missing something obvious".
4. **Do not raise alarms about the repo being "broken" or "degraded" based on bash inspection alone.** Bash-based diagnoses of code structure are not safe.
5. If the truth-set is the live Windows disk, the **only** safe path to it is the file tools.

**What this looks like in practice.**

- ❌ Wrong: `grep -n "def foo" app.py` returns 0 matches → conclude `foo` is missing → propose a recovery phase.
- ✅ Right: `Read app.py` at offset where `foo` is expected → confirm presence → proceed.

- ❌ Wrong: `wc -l app.py` says 864 → assume the file ends there → assume nothing exists past line 864.
- ✅ Right: `Read app.py offset=1015 limit=30` → read the actual content → know what's really there.

**Recovery if you've already drawn a wrong conclusion from bash.** Retract immediately and re-verify with the Read tool against the relevant byte range. Do not commit changes, do not start "recovery" phases, until the Read tool confirms.

### H-1.1 — Linux-side writes that READ stale mount content can OVERWRITE Windows

**What it looks like.** A bash command that both reads and writes the same file (e.g. `sed -i`, `cat file > file`, in-place rewrites via Python `open("path", "w")`) propagates the stale Linux-mount snapshot back to the Windows file. The canonical Windows file is then truncated/wrong.

**Discovery (Phase 0 Step 0.6, 2026-04-29).** After applying a 17-line Edit to `src/reporting/contractor_quality.py`, `python -m py_compile` from bash failed with `SyntaxError: unterminated string literal`. The bash mount still showed the pre-Edit truncated view. Running `sed -i.bak '$a\\' contractor_quality.py` to "force a refresh" caused sed to read the stale truncated view and write it back. The Windows file was overwritten with the truncated content. The Edit was lost. Restore required a fresh Edit-tool patch to re-add the missing tail.

**Operational rules.**

1. **Never run in-place rewrites** (`sed -i`, `awk -i inplace`, `python ... open(p, 'w').write(...)`) against a Windows-mounted source file from bash. The Linux read may be stale; writing it back corrupts Windows.
2. **For test-time validation against patched source:** mirror the project to `/tmp/proj` with `cp -r`, then OVERWRITE any Edit-modified files in `/tmp/proj` with their canonical content from the Read tool (via the connected outputs directory). Run Python from `/tmp/proj` with `PYTHONPATH=/tmp/proj/src`. Never validate against the live mount.
3. **If you suspect the mount is stale on a recently-edited file**, do NOT try to "force a refresh" via sed/touch/cat. The Read tool already has the canonical view. The mount catches up eventually (sometimes after several minutes); until it does, validate from a /tmp mirror.
4. **Recovery if you've corrupted the Windows file via a stale-mount roundtrip.** Re-Read via the Read tool to confirm corruption, then re-Edit to restore the missing content. Verify via Read tool only (not bash). Note the incident in this file's change log.

---

## H-2 — `git status` / branch inspection from sandbox bash

`git status` from inside the sandbox sees the same Linux-mount projection. Reported uncommitted changes, file modifications, and merge state may not reflect the actual Windows working tree. If a git observation is load-bearing for a decision, confirm it from the Windows side or by Read-tool inspection of the relevant files (e.g. read `.git/HEAD`, read the actual file content rather than `git diff`).

---

## H-3 — `output/` / `runs/` / `data/` files that the pipeline produced inside this session

When the pipeline writes outputs from inside the sandbox during this session, those files are produced under the same mount and may be visible to bash without staleness (the Linux side is the writer, so its cache is fresh). The hazard above mostly applies to Windows-edited source files. Outputs the user produced from a previous session by running `python app.py` on Windows have the same staleness risk as source files.

---

## H-4 — `Glob` tool with `path=` parameter

When using the `Glob` tool, providing the `path` parameter limits the search root. If the pattern does not match relative to that root, no files are returned. To list everything under a known directory, prefer the absolute path with a simple pattern (e.g. `pattern: "*.md"`, `path: "C:\Users\...\context"`) rather than recursive globs that depend on path interpretation.

---

## H-5 — File deletion via bash needs explicit permission

`rm` from sandbox bash returns "Operation not permitted" by default for files in the user's working folder. Use the `mcp__cowork__allow_cowork_file_delete` tool to enable deletion for a path; the user is prompted to approve. After approval, `rm` succeeds. This is by design (data safety), not a sandbox failure.

---

## Reminders to embed in every implementation phase

Every phase MD in `docs/implementation/` carries this short rule block:

> **Tooling note (read before any investigation):** Use the `Read` tool — never bash `wc`/`grep`/`cat`/`head`/`tail` — to verify file content, size, or function presence in Windows-mounted source files. The Linux sandbox mount caches a stale view that has, in past sessions, falsely reported missing methods and truncated files. If a bash inspection contradicts the Read tool, the Read tool wins. Do not raise "repo is broken" alarms from bash-only evidence. See `context/11_TOOLING_HAZARDS.md`.

---

## H-2 — FLAT_GED pickle cache freshness uses mtime only (schema drift invisible)

**What it looks like.** `ctx.workflow_engine.responses_df` returns 0 rows for `approver_raw == "0-SAS"` even though `stage_read_flat.py:538-569` clearly emits SAS rows. UI metrics that depend on SAS-track responses (e.g. SAS REF rate) silently report 0 for every contractor. No error, no warning.

**Root cause.** `data_loader._load_flat_normalized_cache` skips a fresh re-parse of `FLAT_GED.xlsx` whenever the three pickle files (`FLAT_GED_cache_docs.pkl`, `FLAT_GED_cache_resp.pkl`, `FLAT_GED_cache_meta.json`) are newer than the xlsx mtime. The freshness check is purely temporal — it has no notion of code-version. If `stage_read_flat.py` (or any upstream code that influences the cache contents) changes its emitted schema while the xlsx file itself does not change, the OLD cache is served forever. SAS rows were stripped silently for an unknown duration on this project for exactly that reason; discovered Phase 7 12a-fix2 (2026-04-29).

**Operational rules.**

1. After ANY change to `src/pipeline/stages/stage_read_flat.py`, `src/flat_ged/transformer.py`, or any code that influences `_save_flat_normalized_cache`'s output: **manually delete the three cache files**:
   ```bash
   rm -f output/intermediate/FLAT_GED_cache_docs.pkl \
         output/intermediate/FLAT_GED_cache_resp.pkl \
         output/intermediate/FLAT_GED_cache_meta.json
   ```
   The next `load_run_context` will rebuild from `FLAT_GED.xlsx` (~30 s one-time cost).

2. **Landed 2026-04-29 (Phase 0 D-001):** `CACHE_SCHEMA_VERSION = "v1"` constant in `data_loader.py` is written into `cache_meta.json` by `_save_flat_normalized_cache` and checked by `_flat_cache_is_fresh`. The freshness check now rejects the cache (and forces an xlsx rebuild) whenever the version key is absent or differs. Bump the constant whenever `stage_read_flat.py` emitted columns change, `normalize_responses` / `normalize_docs` add or rename columns, `flat_doc_meta` structure changes, or pandas-side pickle compatibility breaks. See `data_loader.py:73-149`.

   **Production confirmation observed during Phase 0 canary (2026-04-29):** the FIRST run after pandas was upgraded showed `[FLAT_CACHE] Cache load failed (non-fatal): (<StringDtype(storage='python', na_value=nan)>, …)` despite the mtime check declaring the cache fresh. The cache pickles had been written by an older pandas; current pandas could not unpickle them. With D-001 in place, this exact failure mode is now caught preemptively: the cache is rejected before any unpickle attempt, and the rebuild path runs cleanly. See `docs/audit/CANARY_BEN.md` §13 / D-104.

3. When debugging "this number looks wrong" symptoms downstream of `responses_df` or `docs_df`, **delete the cache as the first diagnostic step**. If the number changes after rebuild, the cache was stale.

---

## H-3 — `WorkflowEngine.responses_df` ≠ `RunContext.responses_df` (silent dual-attribute hazard)

**What it looks like.** Two attributes that both look like the canonical "responses dataframe" return different row sets. Code that reads `ctx.workflow_engine.responses_df` is missing rows that exist in `ctx.responses_df`. SAS rows in particular (`approver_raw == "0-SAS"`) are absent from the workflow_engine view.

**Root cause.** `WorkflowEngine.__init__` (`src/workflow_engine.py:54-57`) makes a copy of the input responses_df and immediately filters out any row where `is_exception_approver == True`. The 0-SAS approver carries that flag (it's structurally an "exception approver" in the GED schema), so all SAS rows are dropped from the engine's local copy. The original `ctx.responses_df` is unaffected.

**Operational rules.**

1. **For any logic that needs SAS-track or other "exception" approver rows** (SAS REF detection, SAS-vs-full-track tracing, raw response auditing): use `ctx.responses_df`, NOT `ctx.workflow_engine.responses_df`.

2. **For workflow logic** (visa_global computation, deadline tracking, the WorkflowEngine `_lookup`): the filtered view is correct; keep using `ctx.workflow_engine.responses_df` as before.

3. When writing a new analytics module, ASK explicitly which row set you want. The two attributes share a name but have different semantics. The dual-access pattern is fragile; treat the choice as a deliberate decision.

4. To verify which view you're consuming: `len(ctx.workflow_engine.responses_df)` will be smaller than `len(ctx.responses_df)` by the count of exception-approver rows (typically ~SAS row count + a few others).

Both H-2 and H-3 were discovered during Phase 7 (contractor quality fiche) when SAS REF rate appeared as 0 % for SNI despite ~184 historical SAS REF events visible in raw GED. The two hazards compounded: the cache was stale (H-2) AND any consumer pivoting to the workflow_engine view would still have seen 0 rows (H-3). Either alone would have produced the bug; both together made it look like the data simply did not exist.

---

## Change log

| Date | Note |
|---|---|
| 2026-04-29 | File created after a Phase 2 false alarm caused by bash-cached view of `app.py` reporting 864 lines instead of ~1200, and the sandbox-side `data_bridge.js` view missing 60 lines. Read tool was authoritative both times. |
| 2026-04-29 | H-2 (cache mtime-only freshness check) and H-3 (WorkflowEngine.responses_df dual-attribute hazard) added after Phase 7 12a-fix2 surfaced both compounded as the SNI SAS REF = 0 % bug. |
| 2026-04-29 | H-1.1 added after Phase 0 Step 0.6: `sed -i.bak` round-trip overwrote `contractor_quality.py` on Windows with the stale Linux-mount truncated view. Recovery via Edit tool. H-2 production-confirmation note added (StringDtype unpickle drift) and D-001 fix landed. |
