# CODEX READ ME FIRST — Claude Code & Cowork

This Obsidian vault is a navigation and reasoning aid for any Claude Code session or Cowork agent working on GFUP_Backend / JANSA VISASIST.

Use it as:
- a starting map before exploring the repo,
- a guide to data flow and module boundaries,
- a reference for protected zones and do-not-touch rules,
- a glossary of business invariants and known hazards,
- a pointer to source files and output artifacts.

Do NOT treat it as source of truth over the actual code, output artifacts, or official context files.

---

## Priority order for all Claude Code / Cowork sessions

1. **User prompt / current task** — explicit instructions always win
2. **Actual source code and generated artifacts** — what the files say right now
3. **Official context files** — `README.md`, `guardrail.txt`, `your-role-main-debugger.txt`, `context/*`, `docs/*`
4. **This Obsidian vault** — navigation support and orientation only

If the vault and the source code disagree: **trust the source code, report the conflict.**

---

## How to use this vault in a session

1. Start at [[00_START_HERE]] for the full note index.
2. Use [[01_SYSTEM_MENTAL_MODEL]] to orient before reading any source file.
3. Use [[02_SOURCE_OF_TRUTH_HIERARCHY]] before deciding which layer to modify.
4. Use [[11_DEBUGGING_SEAMS]] as the first stop for any unexpected number or broken behavior.
5. Use [[12_DONT_TOUCH_WITHOUT_EXPLICIT_SCOPE]] before proposing any edit to protected files.
6. Use [[13_SAFE_DEBUGGING_PROTOCOL]] as the investigation checklist.
7. Use [[14_MODULE_INDEX]] and [[15_DATA_ARTIFACT_INDEX]] to locate files quickly.

---

## Before any patch

- Locate the relevant source file(s) using [[14_MODULE_INDEX]].
- Read the file — do not infer from the vault note alone.
- Compare the vault explanation against the actual code.
- Report any mismatch between vault and code before proceeding.
- Do not modify modules not directly named in the task.
- State your plan before applying changes to any HIGH-risk file (see [[12_DONT_TOUCH_WITHOUT_EXPLICIT_SCOPE]]).

---

## Cowork-specific rules

- Each Cowork agent session starts cold — load this note first for orientation.
- Do not share partial RunContext state between agents — each session resolves its own context.
- Validate output evidence after any change: run `scripts/audit_counts_lineage.py` and paste the one-liner result.
- Do not silently re-run the pipeline during investigation — it mutates `data/run_memory.db`.

---

## If a vault note conflicts with source code

1. Stop.
2. Quote the conflicting vault statement.
3. Quote the relevant source code.
4. Report the conflict to the user before proceeding.
5. Do not patch based on the vault note — patch based on the code and user instruction.
