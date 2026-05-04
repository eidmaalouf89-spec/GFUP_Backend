# READ ME FIRST — Phase Execution Protocol for Cowork and Claude Code

**Location:** `docs/implementation/READ_ME_FIRST_PHASE_EXECUTION_PROTOCOL.md`  
**Status:** Mandatory protocol  
**Applies to:** Cowork, Claude Code, Opus, Sonnet, Haiku, or any agent executing tasks in this repo  
**Project:** JANSA VISASIST / GFUP Backend  
**Current focus:** Phase 6 — Counter-Attack Intelligence

> **Phase 6 source of truth:** `docs/implementation/PHASE_6_COUNTER_ATTACK_MASTER.md`.
> That file supersedes every previous Phase 6 plan. Older Phase 6 files have been moved to `docs/implementation/_superseded_phase6/` and must not be used as a basis for implementation. Where this protocol and the master plan disagree on Phase 6 specifics, the master plan wins.

---

## 0. Mandatory Instruction

Before executing **any prompt, task, phase, sub-phase, code change, repo audit, or validation**, read this document first.

This document defines how work must be organized between:

- The User
- ChatGPT / Product Architect
- Cowork
- Claude Code
- Specialist Claude agents

Do not skip this protocol.

Do not directly implement a large phase from a high-level idea.

Do not freestyle product logic.

Do not rewrite architecture unless explicitly authorized.

---

# 1. Why This Protocol Exists

This software is already alive.

It already has:

- A working pipeline
- A working UI
- A working backend bridge
- Existing outputs
- Existing run artifacts
- Existing Chain + Onion intelligence logic
- Existing Document Command Center logic
- Existing reporting and dashboard logic

The goal is not to rebuild the software.

The goal is to add features surgically, safely, and with traceability.

The main risk is not that the code is impossible.

The main risk is:

```text
Lost context
Overengineering
Wrong file touched
Logic duplicated in UI
Existing outputs broken
Agent invents new architecture
Phase intent gets diluted
```

This protocol prevents that.

---

# 2. Actor Responsibilities

## 2.1 User — Operational Owner / MOEX Saviour

The User defines the operational result.

The User knows:

- What MOEX needs to decide
- What is useful on site
- What is operational bullshit
- What the cockpit must make obvious
- What action matters first

The User is **not** responsible for coding.

The User should not be forced to understand implementation details.

The User validates the final operational usefulness.

---

## 2.2 ChatGPT — Product Architect / Adapter / QA Strategist

ChatGPT is **not the coding executor**.

ChatGPT’s role is to:

- Translate the User’s operational idea into a technical feature plan
- Challenge bad or risky ideas
- Define MVP scope
- Identify touchpoints
- Classify risk
- Produce Cowork handoff packages
- Review Cowork / Claude Code outputs
- Approve, reject, or request rework

ChatGPT is the adapter between:

```text
User operational intent
        ↓
Technical implementation plan
        ↓
Cowork execution management
```

ChatGPT must protect the existing software.

---

## 2.3 Cowork — Phase Team Leader

Cowork is **not supposed to directly execute a vague phase**.

Cowork receives a phase package, for example:

```text
Phase 6A — Action Kernel / Evidence Artifact
```

Cowork’s role is to:

1. Read the phase package.
2. Read this protocol.
3. Break the phase into step-by-step executable tasks.
4. Ensure each step is small enough for one agent/session.
5. Assign the correct model/agent level.
6. Validate each result.
7. Compile the phase result.
8. Compare actual result against the phase plan.
9. Escalate ambiguity instead of inventing product decisions.

Cowork acts like a technical phase manager.

---

## 2.4 Claude Code — Repo Execution Agent

Claude Code executes repo changes.

Claude Code should:

- Modify only authorized files
- Avoid broad refactors
- Avoid architecture changes
- Preserve existing behavior
- Run validations
- Return exact modified files
- Return exact validation results
- Surface uncertainty

Claude Code must not redefine the product.

Claude Code must not add UI-side business logic unless explicitly authorized.

---

## 2.5 Specialist Claude Agents

Use agents based on task type:

| Task Type | Recommended Agent |
|---|---|
| Reading docs / extracting repo context | Haiku |
| Moderate implementation | Sonnet |
| Complex reasoning / high-risk pipeline logic | Opus 4.7 1M |
| Repo-wide code editing / validation | Claude Code |
| Product ambiguity / operational decision | Escalate to ChatGPT + User |

---

# 3. Golden Rules

## Rule 1 — No Large Phase Execution From One Prompt

Never execute:

```text
Implement Phase 6.
```

This is forbidden.

Correct process:

```text
Take Phase 6A.
Create a step-by-step execution plan.
Each step must produce one verified result.
Do not code yet.
Return the plan for review.
```

---

## Rule 2 — One Step = One Verified Result

Every implementation step must be self-contained.

A valid step has:

- Clear objective
- Exact input
- Exact files to read
- Exact files allowed to modify
- Files forbidden to touch
- Expected output
- Validation command or validation method
- Return package

A bad step:

```text
Improve the counter-attack feature.
```

A good step:

```text
Create src/reporting/counter_attack_builder.py that reads existing DCC/focus/chain-onion artifacts and writes output/intermediate/COUNTER_ATTACK_ITEMS.csv with the required columns. Do not modify UI. Do not modify existing ownership logic. Validate artifact creation and bucket counts.
```

---

## Rule 3 — No Calculation in the UI

The UI must not calculate business decisions.

The UI displays prepared backend truth.

Forbidden in UI:

- Ownership scoring
- Deadline decision logic
- Bucket classification
- Chain interpretation
- Onion responsibility logic
- MOEX exposure calculation
- Contractor/consultant attackability logic

Allowed in UI:

- Displaying rows
- Filtering already-provided fields
- Sorting already-provided fields
- Opening detail panels
- Export button
- Treated visual state if explicitly local-only

The backend/pipeline produces the truth.

The UI presents the truth.

---

## Rule 4 — Reuse Existing Logic

Do not rewrite existing logic if a source already exists.

For Phase 6, reuse:

- Document Command Center logic
- Focus ownership logic
- Chain timeline attribution
- Chain + Onion outputs
- Existing run/output conventions
- Existing bridge/API patterns

Do not create a parallel intelligence system unless explicitly approved.

---

## Rule 5 — Additive Changes First

Prefer additive files and read-only APIs.

Safer:

```text
src/reporting/counter_attack_builder.py
src/reporting/counter_attack_query.py
ui/jansa/counter_attack.jsx
```

Riskier:

```text
Rewrite document_command_center.py
Rewrite focus_ownership.py
Rewrite app.py architecture
Change database schema
Change existing output contracts
```

If a change touches pipeline logic, run memory, DB, or artifact contracts, classify it as high risk and escalate.

---

## Rule 6 — Context Must Be Updated

After each validated phase or sub-phase, update a context document.

Recommended files:

```text
docs/implementation/PHASE_6A_ACTION_KERNEL.md
docs/implementation/PHASE_6B_READ_API.md
docs/implementation/PHASE_6C_COUNTER_ATTACK_UI.md
docs/implementation/PHASE_6D_EXPORT_TREATED_AI_PACK.md
```

Each context file must include:

1. What was built
2. Why it exists
3. Files modified
4. Files read
5. Data inputs
6. Data outputs
7. Validation results
8. Known limitations
9. Next phase dependencies

This prevents context loss between chats and agents.

In addition to the phase-specific doc above, the agent MUST update the `/context` inventory (the `00_…` through `10_…` markdown files plus the machine-readable inventories: `artifact_inventory.csv`, `software_tree.json`, `module_dependency_map.csv`, `ui_endpoint_map.csv`, `data_columns_map.csv`, exception/rule CSVs) AND `README.md` after every validated phase or sub-phase, in the same way they were originally created and to respect the intent for which they exist. The `/context` folder is the living source of truth for runtime, data flow, UI feeds, pipeline stages, artifacts, exceptions, validation commands, do-not-touch zones, and tooling hazards; leaving it stale defeats the reason it exists. After-phase context updates are part of the phase's definition-of-done — not optional, not deferred.

---

## Rule 7 — Check Context Before Escalating

Before escalating any ambiguity, conflict, missing-symbol, or unanswered question, the agent MUST first check:

1. The `/context` folder (the `00_…` through `10_…` markdown files plus `artifact_inventory.csv`, `software_tree.json`, `module_dependency_map.csv`, `ui_endpoint_map.csv`, `data_columns_map.csv`, and the exception/rule CSVs).
2. `README.md` and any phase-specific READMEs in `docs/implementation/`.
3. The current phase's master plan and execution plan.

The `/context` folder exists precisely to answer recurring questions about runtime, data flow, UI feeds, pipeline stages, output artifacts, exceptions, validation commands, do-not-touch zones, and tooling hazards. Skipping it and escalating directly is a protocol violation.

Only escalate after a documented context check fails to resolve the conflict. The escalation note MUST include a one-line citation of the files consulted, e.g.: "Context checked: `02_DATA_FLOW.md`, `05_OUTPUT_ARTIFACTS.md` — no resolution found." If the answer IS found in `/context`, the agent applies it (citing file + line) and proceeds without escalating.

---

# 4. Required Phase Workflow

Every phase follows this workflow.

```text
User defines operational outcome
        ↓
ChatGPT creates technical phase package
        ↓
Cowork creates step-by-step execution plan
        ↓
ChatGPT/User review Cowork plan
        ↓
Cowork assigns agents step by step
        ↓
Agents execute one verified result per session
        ↓
Cowork compiles results
        ↓
Cowork validates against phase package
        ↓
ChatGPT reviews final return package
        ↓
User approves operational result
```

---

# 5. Cowork Mandatory Workflow

When Cowork receives a phase package, Cowork must not code immediately.

Cowork must first return:

```text
1. Understanding of the phase objective
2. Risk classification
3. Files likely to read
4. Files likely to modify
5. Files forbidden to touch
6. Step-by-step execution plan
7. Agent/model assignment per step
8. Validation required per step
9. Escalation points
10. Final expected return package
```

Only after approval should execution start.

---

# 6. Agent Task Template

Every individual agent task must use this structure.

```markdown
# Agent Task — [Step ID / Name]

## Objective

What this step must achieve.

## Context

Why this step exists in the phase.

## Files To Read

- path/to/file.py
- path/to/file.jsx

## Files Allowed To Modify

- path/to/new_or_existing_file.py

## Files Forbidden To Touch

- path/to/sensitive_file.py
- path/to/existing_logic.py

## Required Work

1. ...
2. ...
3. ...

## Constraints

- Do not rewrite existing architecture.
- Do not move business logic into UI.
- Do not modify unrelated files.
- Preserve existing outputs.
- Prefer additive changes.

## Validation

Run or perform:

```bash
python -m py_compile path/to/file.py
```

Then verify:

- Expected output exists
- Row count plausible
- Existing outputs unchanged
- No UI console errors if UI task

## Required Return Package

1. Files modified
2. Summary of changes
3. Validation performed
4. Validation results
5. Risks / uncertainty
6. Anything not completed
```

---

# 7. Mandatory Return Package After Any Coding Step

Every coding agent must return:

```text
1. Files modified
2. Files read
3. Summary of changes
4. Validation commands run
5. Validation results
6. Produced artifacts
7. Risks / compromises
8. Uncertainty
9. Screenshots if UI
```

No vague statements.

Forbidden:

```text
Done.
Implemented.
All good.
Should work.
```

Required:

```text
Created COUNTER_ATTACK_ITEMS.csv at output/intermediate/.
Rows: 482.
Buckets populated: 7/7.
Validation: python -m py_compile passed.
No existing output files modified except expected new artifact.
```

---

# 8. Cowork Final Compilation Package

At the end of a phase or sub-phase, Cowork must return:

```text
# Cowork Phase Compilation — [Phase Name]

## Phase Objective

## What Was Planned

## What Was Actually Built

## Files Modified

## Files Created

## Files Read

## Validation Results

## Comparison Against Phase Plan

- Requirement 1: PASS / FAIL / PARTIAL
- Requirement 2: PASS / FAIL / PARTIAL

## Risks

## Deviations From Plan

## Escalations Needed

## Recommendation

VALIDATED
or
VALIDATED WITH MINOR RISK
or
REWORK REQUIRED
or
ESCALATION REQUIRED
```

---

# 9. ChatGPT Review Decision

After Cowork returns the final compilation package, ChatGPT reviews it and gives one decision:

```text
APPROVE
REWORK SMALL
REWORK MAJOR
REJECT
```

Review criteria:

- Did Cowork overmodify?
- Were wrong files touched?
- Was UI business logic introduced?
- Was existing logic duplicated?
- Were validations real?
- Were artifacts deterministic?
- Was the phase objective respected?
- Is there hidden regression risk?
- Is the next phase safe to start?

---

# 10. Phase 6 Specific Protocol

Phase 6 is called:

```text
Counter-Attack Intelligence
```

Its operational objective:

```text
Tell MOEX:
- What to close
- What to decide
- Who to relaunch
- Who to attack
- Which subject is becoming dangerous
- What evidence supports it
```

Phase 6 must be simple for non-technical users.

The user should not need to understand:

- Chain logic
- Onion scoring
- Consultant tiers
- Workflow complexity
- Raw intelligence tags

The system must translate complexity into action.

---

## 10.1 Recommended Phase 6 Structure

```text
Phase 6A — Action Kernel / Evidence Artifact
Phase 6B — Counter-Attack Read API
Phase 6C — Counter-Attack Cockpit UI
Phase 6D — Export / Treated / Monthly AI Pack
```

---

## 10.2 Phase 6A — Action Kernel / Evidence Artifact

Objective:

```text
Produce one deterministic backend artifact that converts existing chain/onion/focus/DCC logic into simple operational action items.
```

Recommended artifact:

```text
output/intermediate/COUNTER_ATTACK_ITEMS.csv
```

Optional supporting artifacts:

```text
output/intermediate/SUBJECT_RISK_DOSSIERS.csv
output/intermediate/ACTOR_ATTACK_DOSSIERS.csv
```

Minimum action buckets:

```text
FERMER_MAINTENANT
DECISION_MOEX
SECONDAIRE_EXPIRE
ENTREPRISE_A_RELANCER
CONSULTANT_A_ATTAQUER
SUJET_REUNION
MOEX_SHAME_INTERNAL
```

Required principle:

```text
Do not rewrite existing ownership logic.
Reuse existing DCC / focus / chain-onion logic.
```

Risk:

```text
HIGH, because this touches pipeline/output artifacts.
```

Gate to pass before 6B:

```text
COUNTER_ATTACK_ITEMS.csv exists
Buckets are non-empty
Same inputs produce same artifact
Pipeline still runs
Existing outputs unchanged
Secondaire expiré matches existing ownership/countdown logic
Context doc updated
```

---

## 10.3 Phase 6B — Counter-Attack Read API

Objective:

```text
Expose read-only backend endpoints that serve ready-made screens, not raw filter data.
```

Possible files:

```text
src/reporting/counter_attack_query.py
app.py
ui/jansa/data_bridge.js
```

Expected methods:

```text
get_counter_attack_home()
get_counter_attack_queue(bucket, limit=500)
get_counter_attack_item(item_id)
```

Risk:

```text
MEDIUM, because this touches app/API bridge but should remain read-only.
```

Gate to pass before 6C:

```text
Home returns bucket counts
Queue returns rows for each bucket
Item detail returns evidence
Missing artifact returns friendly empty state
No DB added
No API regression
Context doc updated
```

---

## 10.4 Phase 6C — Counter-Attack Cockpit UI

Objective:

```text
Create a new sidebar page that lets a non-technical MOEX user know exactly what to do.
```

Possible files:

```text
ui/jansa/counter_attack.jsx
ui/jansa/shell.jsx
ui/jansa-connected.html
```

UI journey:

```text
Home
→ Bucket
→ Queue
→ Item detail
→ Open DCC / Export / Mark treated
```

The first screen must answer:

```text
What should I do first?
How many items?
Which bucket is most urgent?
```

Each item detail must answer:

```text
What is it?
Why is it here?
What should I do?
What evidence supports it?
```

Risk:

```text
MEDIUM, because this adds a UI page but should not change backend logic.
```

Gate to pass before 6D:

```text
Page opens
Buckets show counts
Bucket click opens queue
Item detail is understandable
No UI calculations
No console errors
Existing pages unchanged
Context doc updated
```

---

## 10.5 Phase 6D — Export / Treated / Monthly AI Pack

Objective:

```text
Add operator workflow tools for exporting, marking treated, and generating an AI evidence pack.
```

Possible files:

```text
ui/jansa/counter_attack.jsx
ui/jansa/data_bridge.js
app.py
src/reporting/counter_attack_export.py
output/exports/
```

Allowed treated state:

```text
localStorage only
run-number scoped
no DB write
no deterministic artifact mutation
```

Export examples:

```text
output/exports/CounterAttack_<bucket>_<timestamp>.xlsx
output/exports/CounterAttack_AI_Pack_<timestamp>.zip
```

AI pack should contain:

```text
COUNTER_ATTACK_ITEMS.csv
SUBJECT_RISK_DOSSIERS.csv
ACTOR_ATTACK_DOSSIERS.csv
CHAIN_EVENTS.csv
ONION_LAYERS.csv
ONION_SCORES.csv
CHAIN_REGISTER.csv
top_issues.json
dashboard_summary.json
README_FOR_AI.md
```

Risk:

```text
MEDIUM, because it adds exports and local operator workflow.
```

Final Phase 6 gate:

```text
Export creates XLSX
Exported rows match queue
Treated rows grey out
Reload keeps treated state
New run resets treated state
AI pack zip contains expected files
No DB modified
No deterministic artifact modified
Context doc updated
```

---

# 11. Forbidden Behaviors

Do not do any of the following unless explicitly approved:

```text
Rebuild the frontend framework
Replace PyWebView
Replace the backend bridge
Introduce a new database
Change run_memory schema
Rewrite chain/onion logic
Rewrite Document Command Center logic
Move calculation logic into React
Create duplicate ownership logic
Modify unrelated dashboards
Delete existing outputs
Rename existing artifacts
Change existing artifact contracts
Perform broad refactors
```

---

# 12. Escalation Rules

**Pre-escalation check (mandatory).** Before escalating, run the Rule 7 check: read the `/context` folder and the relevant READMEs first. Cite the files consulted in the escalation note. If `/context` resolves the question, do NOT escalate — apply the answer (citing file + line) and proceed.

Escalate to ChatGPT + User only if, after that check, you still see:

```text
A product decision is unclear
Existing logic conflicts with Phase 6 objective
A required field is missing from available artifacts
A change requires modifying high-risk pipeline logic
A DB/schema change seems necessary
Existing output contracts would change
A safer MVP alternative exists
The requested implementation would duplicate major logic
```

Do not invent answers silently.

---

# 13. Default Decision Principle

When uncertain, choose the safest useful version.

Prefer:

```text
Read existing artifact
Create additive artifact
Expose read-only endpoint
Display prepared data
Update context docs
```

Avoid:

```text
Rewrite logic
Change schema
Add hidden calculations
Patch many files
Create second source of truth
```

---

# 14. Final Reminder

This project is not a toy prototype.

It is an operational cockpit.

Every change must be:

```text
Fast
Clean
Useful
Low-friction
Traceable
Deterministic
Safe for existing outputs
```

The correct working rhythm is:

```text
Plan
Split
Execute one verified step
Validate
Compile
Review
Document
Then move to the next phase
```

Never skip the process.
