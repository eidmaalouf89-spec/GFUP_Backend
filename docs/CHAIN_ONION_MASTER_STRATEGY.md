# CHAIN + ONION MASTER STRATEGY
Version: v1.0
Owner: Eid
Execution Model: ChatGPT Strategy / Claude Cowork Implementation

---

## PURPOSE

Build a new analytical layer on top of the stable GFUP backend.

Do NOT modify the frozen Flat GED builder logic.

Chain + Onion must consume existing outputs and create advanced responsibility / lifecycle intelligence.

---

## CORE DEFINITIONS

### CHAIN

A Chain = full lifecycle of one document family.

Identity:

- Primary family key = numero
- Secondary = indice
- Submission instance = submission_instance_id
- Event = actor response / workflow step

Chain reconstructs:

A → B → C → REF → corrected B → VAO etc.

---

### ONION

Onion = layered responsibility attribution around a chain.

Layers:

1. Contractor quality
2. SAS conformity gate
3. Consultant delay
4. Consultant rejection/conflict
5. MOEX arbitration
6. Data/report discrepancy

---

## INPUT SOURCES

1. FLAT_GED.xlsx
2. DEBUG_TRACE.csv
3. effective_responses output
4. run metadata

---

## PROTECTED FILES

Never modify:

- src/flat_ged/*
- stable pipeline core unless explicit step says so
- legacy UI runtime

---

## NEW MODULE TARGET

src/chain_onion/

Files expected:

- __init__.py
- source_loader.py
- chain_models.py
- chain_builder.py
- chain_classifier.py
- chain_metrics.py
- onion_engine.py
- onion_scoring.py
- onion_narrative.py
- exporter.py
- validators.py
- query_hooks.py

---

## OUTPUT TARGET

output/chain_onion/

- CHAIN_REGISTER.csv
- CHAIN_EVENTS.csv
- ONION_RESPONSIBILITY.csv
- CHAIN_SUMMARY.xlsx
- validation_report.md

---

## RULES

1. Deterministic only
2. No AI guesses inside engine
3. Reproducible
4. Explainable
5. Read-only over source data
6. All assumptions logged

---

## SUCCESS CRITERIA

1. Detect dead chains
2. Detect void chains
3. Detect chronic chains
4. Attribute responsibility fairly
5. Produce usable exports
6. Ready for future UI integration