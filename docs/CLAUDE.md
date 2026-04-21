# CLAUDE.md

Purpose:
This file defines how Claude should work with this repository in all modes:
- Claude Chat
- Claude Cowork
- Claude Code

Claude is used primarily for:
1. repo understanding
2. architectural reasoning
3. scoped implementation planning
4. code generation / refactoring execution
5. documentation drafting
6. UI/report/export design support

Claude is NOT the source of truth.
The source of truth is:
- the code
- the validated baseline
- the project docs in `/docs`
- the current repository state

---

## 1. FIRST FILES TO READ

Before doing anything important, Claude must read these files first:

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `docs/PIPELINE_FLOW.md`
4. `docs/DEVELOPMENT_RULES.md`
5. `docs/VALIDATION_BASELINE.md`
6. `docs/KNOWN_LIMITATIONS.md`

---

## 2. PROJECT IDENTITY

This repository is a deterministic reconstruction and enrichment engine for GED → GF processing.

Core principles:
- GED is the primary operational truth
- `report_memory.db` is persistent secondary truth
- GF is a reconstructed/enriched output, not the primary truth
- `run_memory.db` tracks run history, artifacts, lineage, and baseline state

Claude must preserve this mental model in all reasoning and code changes.

---

## 3. CURRENT ARCHITECTURE

Current architecture is staged and stabilized.

High-level structure:
- `main.py` = thin entrypoint
- `src/pipeline/stages/` = ordered execution stages
- `src/pipeline/context.py` = shared pipeline state
- `src/domain/` = deterministic business logic helpers
- `src/pipeline/compute.py` = heavy non-pure pipeline computation
- `src/run_memory.py` = run history persistence
- `src/report_memory.py` = consultant report persistence
- `src/run_orchestrator.py` = controlled execution layer

Claude must respect the staged architecture and avoid re-centralizing logic into `main.py`.

---

## 4. HOW CLAUDE SHOULD WORK

Claude should work in this order:

1. Understand the task
2. Identify the exact layer involved
3. Identify the exact files involved
4. Propose a minimal change plan
5. Modify only the necessary files
6. Validate against the baseline rules

Claude must prefer small, scoped changes over broad rewrites.

---

## 5. LAYER RESPONSIBILITIES

Use this routing logic:

### A. Entry / execution contract
Use for:
- run mode behavior
- inherited GF resolution
- execution path control
- startup / orchestration boundary

Main files:
- `main.py`
- `src/run_orchestrator.py`

### B. Pipeline stage flow
Use for:
- stage ordering
- stage data handoff
- state propagation
- end-to-end execution behavior

Main files:
- `src/pipeline/context.py`
- `src/pipeline/stages/*`

### C. Business logic
Use for:
- discrepancy logic
- SAS logic
- normalization
- family grouping
- GF comparison rules
- classification rules

Main files:
- `src/domain/*`
- `src/pipeline/compute.py`

### D. Persistence
Use for:
- run history
- baseline state
- artifact registration
- report persistence
- consultant truth reuse

Main files:
- `src/run_memory.py`
- `src/report_memory.py`
- `src/run_explorer.py`

### E. Presentation / exploitation layer
Use for:
- report generation
- export shaping
- UI-facing data structures
- future dashboards / adapters

Important note:
This layer is still underdeveloped.
Do not assume there is already a clean product/output adapter layer.

---

## 6. STRICT WORKING RULES

Claude must follow these rules:

### NEVER
- rewrite the architecture broadly unless explicitly asked
- bypass `run_orchestrator.py` without justification
- treat GF as the primary source of truth
- delete `report_memory.db` unless explicitly instructed for a deliberate full reset
- silently change output filenames or artifact contracts
- change stage order casually
- collapse staged logic back into monolithic files
- make speculative refactors unrelated to the task

### ALWAYS
- preserve deterministic behavior first
- keep changes minimal and scoped
- respect the validated baseline
- use existing docs as project memory
- identify touched files before coding
- explain risks and regressions before large edits
- prefer extraction over redesign

---

## 7. CHANGE STRATEGY

Claude must use one of these modes explicitly in its reasoning:

### Mode 1 — Analysis only
Used when:
- understanding the repo
- locating files
- planning a feature
- diagnosing a bug
- mapping stage impact

Deliverables:
- relevant files
- current behavior
- probable change location
- minimal plan

### Mode 2 — Scoped implementation
Used when:
- changing one feature
- fixing one bug
- refactoring one bounded area

Deliverables:
- exact files changed
- exact logic changed
- regression risks
- validation steps

### Mode 3 — Documentation
Used when:
- updating docs after architecture or behavior change
- adding context optimization files
- clarifying limitations / rules

Deliverables:
- concise docs
- no fluff
- aligned with current code

---

## 8. VALIDATION RULE

After any non-trivial code change, Claude must recommend a full validation run.

Minimum baseline expectations:
- run completes successfully
- run status = `COMPLETED`
- `FINAL_GF` exists
- artifacts are registered
- metrics remain consistent with `docs/VALIDATION_BASELINE.md`

Claude must treat the validation baseline as the regression reference.

---

## 9. HOW TO HANDLE FEATURES

For any feature request, Claude must first answer:

1. What layer does this belong to?
2. What stage(s) are involved?
3. What files are definitely relevant?
4. What files should not be touched?
5. Is this a business logic change, orchestration change, persistence change, or presentation change?

Claude should not start coding before answering those questions internally or explicitly.

---

## 10. HOW TO HANDLE UI / REPORT / EXPORT REQUESTS

This project has a known limitation:
the backend logic is strong, but exploitation for UI/report/export is not yet cleanly separated.

Therefore Claude must be careful:
- do not entangle new report/UI/export logic deeply into core stages if avoidable
- prefer adapter-like structures
- prefer reusable structured output models
- do not force repeated repo-wide re-analysis for every presentation change

Long-term direction:
core engine → structured output model → presentation/export adapters

---

## 11. WHAT CLAUDE SHOULD DO WHEN CONTEXT IS LIMITED

If context is limited, Claude should read in this priority order:

1. `docs/ARCHITECTURE.md`
2. `docs/PIPELINE_FLOW.md`
3. `docs/DEVELOPMENT_RULES.md`
4. the exact stage file(s)
5. the exact domain module(s)
6. the exact persistence module(s), only if needed

Claude should avoid loading the whole repo when a smaller file set is sufficient.

---

## 12. PREFERRED PROMPT STYLE FOR CLAUDE

Best style:
- clear goal
- exact relevant files
- explicit constraints
- exact deliverable
- strict scope control

Preferred pattern:

- Goal
- Source of truth files
- Relevant files
- Constraints
- Deliverable
- Validation expectations

---

## 13. CLAUDE ROLE SPLIT

Recommended use:

### Claude Chat
- understanding
- architecture
- feature scoping
- debugging guidance
- doc drafting

### Claude Cowork
- medium-size implementation
- structured refactor execution
- multi-file code changes
- validation-oriented changes

### Claude Code
- direct code manipulation
- patch execution
- bounded implementation tasks
- doc updates

Claude should not mix analysis, redesign, implementation, and validation into one giant step unless explicitly required.

---

## 14. FINAL INSTRUCTION

Claude must treat this repository as a deterministic production engine with a validated staged architecture.

Priority order:
1. preserve correctness
2. preserve determinism
3. preserve baseline compatibility
4. improve structure only when needed
5. improve speed of future work through better context isolation
