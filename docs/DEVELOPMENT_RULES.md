# DEVELOPMENT RULES

1. NEVER modify pipeline stages blindly
2. ALWAYS run full pipeline after change
3. ALWAYS compare against VALIDATION_BASELINE.md
4. DO NOT delete report_memory.db
5. DO NOT bypass run_orchestrator
6. DO NOT change output formats casually
7. Refactor = extraction only, not redesign

Workflow:
- define issue
- locate stage
- modify minimal code
- run full pipeline
- validate metrics