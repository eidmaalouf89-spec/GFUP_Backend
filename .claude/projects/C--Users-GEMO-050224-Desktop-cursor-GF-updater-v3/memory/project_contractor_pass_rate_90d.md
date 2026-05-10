---
name: Contractor pass_rate / taux de conformité — 90-day window
description: Contractor pass_rate is now computed over the last 90 days (not all-time). Consultant pass_rate is unchanged (answered/called).
type: project
---

As of 2026-05-10, contractor **taux de conformité / pass_rate** is computed over a **90-day rolling window**:

```
pass_rate_90d = count(dernier docs where created_at >= data_date - 90d AND visa_global IN [VSO, VAO])
              / count(dernier docs where created_at >= data_date - 90d)
```

**Submission date field**: `created_at` on `ctx.dernier_df` (= "Créé le" from GED export).
**Reference date**: `ctx.data_date` from RunContext.

**Single metric owner**: `src/reporting/aggregator.py::compute_contractor_summary`
- Adds `total_submitted_90d`, `visa_vso_90d`, `visa_vao_90d` to each contractor dict.
- Fields are `None` when `ctx.data_date` is unavailable (consumers fall back to all-time).

**Consumers updated**:
- `src/reporting/ui_adapter.py::adapt_contractors_list` → `c.pass_rate` (window.CONTRACTORS_LIST)
- `src/reporting/ui_adapter.py::adapt_overview` → `best_contractor.pass_rate` (window.OVERVIEW)

**Unchanged**:
- Consultant pass_rate = `answered / called` (response_rate × 100) — NOT modified.
- All-time fields (`total_submitted`, `visa_vso`, `visa_vao`, `approval_rate`) still emitted for other consumers.
- No pipeline, Flat GED, run_memory, or report_memory changes.
- No computation added to the UI layer.

**Why**: Business decision to surface recent contractor conformance performance only, not accumulated historical rate.

**How to apply**: If asked about contractor taux de conformité, it is 90-day rolling. If asked to revert or change the window, edit `compute_contractor_summary` in aggregator.py (the `pd.Timedelta(days=90)` constant) and the two adapt_* functions in ui_adapter.py.
