# PIPELINE FLOW

Input:
- GED export
- GF (optional)
- consultant reports
- report_memory.db

Flow:
GED → normalize → version → routing → GF structure
→ report memory merge → workflow
→ write GF → discrepancy → diagnosis → artifacts

Output:
- FINAL_GF
- discrepancy reports
- reconciliation logs
- debug artifacts
- run history

State passing:
All data moves through PipelineState