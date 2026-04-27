STEP 01 PROMPT
READ FIRST:
- docs/CHAIN_ONION_MASTER_STRATEGY.md
- docs/CHAIN_ONION_STEP_TRACKER.md

TASK:
Perform repository reconnaissance.

Identify exact files/functions producing:

1. FLAT_GED loading
2. DEBUG_TRACE handling
3. effective_responses generation
4. exports
5. query library hooks

DO NOT MODIFY CODE.

OUTPUT:
docs/STEP01_SOURCE_MAP.md

Include:
- files inspected
- key functions
- integration opportunities
- risks
- recommendation for Step 04

SUCCESS:
No code touched.
STEP 02 PROMPT
READ FIRST:
- docs/CHAIN_ONION_MASTER_STRATEGY.md
- docs/STEP01_SOURCE_MAP.md

TASK:
Create full data contract for chain outputs.

Design schemas for:

1. chain_register
2. chain_events
3. chain_metrics

DO NOT TOUCH CODE.

OUTPUT:
docs/STEP02_CHAIN_CONTRACT.md
STEP 03 PROMPT
READ FIRST:
- docs/STEP02_CHAIN_CONTRACT.md

TASK:
Create Onion data contract.

Tables:

1. onion_responsibility
2. onion_scores
3. onion_explanations

OUTPUT:
docs/STEP03_ONION_CONTRACT.md
STEP 04 PROMPT
READ FIRST:
- docs/STEP01_SOURCE_MAP.md
- docs/STEP02_CHAIN_CONTRACT.md

ONLY TOUCH:

src/chain_onion/source_loader.py

TASK:

Build safe read-only loaders for:

- FLAT_GED.xlsx
- DEBUG_TRACE.csv
- effective_responses latest outputs

Functions:

load_flat_ged()
load_debug_trace()
load_effective_responses()
load_all_sources()

TESTS:

Create smoke test script.

OUTPUT REPORT:

docs/STEP04_VALIDATION.md
STEP 05 PROMPT
ONLY TOUCH:

src/chain_onion/chain_builder.py
src/chain_onion/chain_models.py

TASK:

Create family grouping engine.

Build chains grouped by numero.

Include:

- ordered indices
- instance count
- first date
- last date

OUTPUT:
docs/STEP05_VALIDATION.md
STEP 06 PROMPT
ONLY TOUCH:

src/chain_onion/chain_builder.py

TASK:

Create chronological event engine.

Every chain gets ordered timeline:

submission
sas
consultant
moex
report corrections

Export internal dataframe.

OUTPUT:
docs/STEP06_VALIDATION.md
STEP 07 PROMPT
ONLY TOUCH:

src/chain_onion/chain_classifier.py

TASK:

Implement chain states:

- DEAD_AT_SAS_A
- WAITING_CORRECTED_INDICE
- OPEN_WAITING_CONSULTANT
- OPEN_WAITING_MOEX
- CLOSED_VAO
- CLOSED_VSO
- CHRONIC_REF_CHAIN
- VOID_CHAIN

Provide unit tests.

OUTPUT:
docs/STEP07_VALIDATION.md
STEP 08 PROMPT
ONLY TOUCH:

src/chain_onion/chain_metrics.py

TASK:

Compute:

- total cycle days
- cumulative delays
- nb rejections
- nb resubmissions
- blocked actor count

OUTPUT:
docs/STEP08_VALIDATION.md
STEP 09 PROMPT
ONLY TOUCH:

src/chain_onion/onion_engine.py

TASK:

Build responsibility layers:

1 contractor
2 sas
3 consultant delay
4 consultant conflict
5 moex
6 data discrepancy

OUTPUT:
docs/STEP09_VALIDATION.md
STEP 10 PROMPT
ONLY TOUCH:

src/chain_onion/onion_scoring.py

TASK:

Create severity model:

LOW
MEDIUM
HIGH
CRITICAL

And confidence score 0-100.

OUTPUT:
docs/STEP10_VALIDATION.md
STEP 11 PROMPT
ONLY TOUCH:

src/chain_onion/onion_narrative.py

TASK:

Generate deterministic explanations.

Example:

"Chain blocked 46 days by BET Structure after SAS approval."

OUTPUT:
docs/STEP11_VALIDATION.md
STEP 12 PROMPT
ONLY TOUCH:

src/chain_onion/exporter.py

TASK:

Export:

CHAIN_REGISTER.csv
CHAIN_EVENTS.csv
ONION_RESPONSIBILITY.csv
CHAIN_SUMMARY.xlsx

OUTPUT:
docs/STEP12_VALIDATION.md
STEP 13 PROMPT
ONLY TOUCH:

src/chain_onion/query_hooks.py

TASK:

Expose query functions for future UI.

Examples:

get_dead_chains()
get_waiting_moex_chains()
get_top_responsible_consultants()

OUTPUT:
docs/STEP13_VALIDATION.md
STEP 14 PROMPT
ONLY TOUCH:

src/chain_onion/validators.py

TASK:

Build validation harness.

Cross-check 20 sample docs manually.

Detect contradictions.

OUTPUT:

docs/STEP14_VALIDATION.md
docs/CHAIN_ONION_ACCEPTANCE.md|