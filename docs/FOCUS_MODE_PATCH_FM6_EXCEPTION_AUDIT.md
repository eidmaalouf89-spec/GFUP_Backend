---
step: FM-6
date: 2026-04-27
verdict: PASS
---

# FM-6 Exception Order Audit

## Execution Order (post-patch)

```
load_run_context()
    ↓
apply_focus_filter(ctx, focus_config)
    → stale/resolved exclusions applied internally (focus_filter.py)
    → blocked_upstream_ids computed
    → priority_queue built from focused_df
    ↓
_build_live_operational_numeros()
    → local import of chain_onion.query_hooks (no module-level import)
    → graceful fallback: returns (None, 0) on any error or missing output
    ↓
_apply_live_narrowing(focus_result, live_numeros, legacy_count)
    → only executes if live_numeros is not None
    → narrows focused_df to LIVE_OPERATIONAL family keys
    → rebuilds focused_doc_ids from narrowed focused_df
    → rebuilds priority_queue to surviving doc_ids only
    → updates stats["focused_count"] and stats["legacy_backlog_count"]
    ↓
KPI engine / consultant / contractor (reads narrowed focus_result)
    ↓
UI adapter (passes legacy_backlog_count through)
    ↓
Overview UI (shows backlog badge if count > 0)
```

## Protection Guarantees

| Protection | Preserved? | Reason |
|-----------|-----------|--------|
| Stale filter (>90d) | ✅ YES | Applied by apply_focus_filter() BEFORE live narrowing |
| Resolved filter | ✅ YES | Applied by apply_focus_filter() BEFORE live narrowing |
| Blocked upstream exclusion | ✅ YES | Computed by apply_focus_filter(), not touched by narrowing |
| focus=False path | ✅ YES | _apply_live_narrowing is only called after apply_focus_filter; if focus=False, focused_df is None → early return |
| No chain_onion output | ✅ YES | _build_live_operational_numeros returns (None, 0) → _apply_live_narrowing early-returns, no change to focus_result |
| ARCHIVED excluded | ✅ YES | get_live_operational filters to portfolio_bucket == LIVE_OPERATIONAL, so ARCHIVED is never in live_numeros |

## Verdict: PASS

Old protections (stale/resolved) are applied by apply_focus_filter() which runs BEFORE _apply_live_narrowing(). The live narrowing is an additive filter on top — it can only remove docs that were already excluded by stale/resolved logic; it cannot re-add them. All fallbacks are safe: failures return (None, 0) which is a no-op in _apply_live_narrowing.
