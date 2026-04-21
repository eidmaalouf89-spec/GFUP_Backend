# ARCHITECTURE

## Entry
main.py → run_orchestrator → pipeline stages

## Pipeline stages (order)
1. stage_init_run
2. stage_read
3. stage_normalize
4. stage_version
5. stage_route
6. stage_report_memory
7. stage_write_gf
8. stage_discrepancy
9. stage_diagnosis
10. stage_finalize_run

## Key modules
- domain/ → business logic
- pipeline/stages/ → execution flow
- pipeline/context.py → shared state
- persistence/ → run_memory + report_memory

## State model
PipelineState (77 fields)
- paths
- run metadata
- stage outputs

## Critical rules
- GED = primary truth
- report_memory = persistent secondary truth
- GF = reconstructed output
- run_memory = lineage system

DO NOT bypass pipeline stages.

## Current architectural gap

The deterministic backend engine is now stabilized, but the project still lacks a clean exploitation layer between:
- backend truth generation
- UI/report/export consumption

This means presentation and export changes are still too dependent on internal pipeline knowledge.

Long-term direction:
core engine → structured output model → presentation/export adapters