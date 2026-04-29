---
step: FM-1
date: 2026-04-27
verdict: READY
---

# FM-1 Audit — Focus Mode Patch

## Confirmed Facts

| Check | Location | Status |
|-------|----------|--------|
| shell.jsx focusMode useState | shell.jsx:467 | ✅ EXISTS — `useState(() => localStorage.getItem('jansa_focus') === '1')` |
| numero_normalized in dernier_df | data_loader.py → normalize_docs() | ✅ EXISTS — created via `df["numero"].apply(normalize_numero)` |
| normalize_numero returns normalized string | src/normalize.py:154–165 | ✅ EXISTS — returns `str(int(numero))` or `str(numero).strip()` |
| Chain family_key contract | src/chain_onion/family_grouper.py:13–27 | ✅ CONFIRMED — `FAMILY_KEY = str(numero)` |
| ONION_SCORES has family_key | src/chain_onion/onion_scoring.py:94–105 | ✅ EXISTS — in `_OUTPUT_COLS` |
| priority_queue contains doc_id | src/reporting/focus_filter.py (FocusResult) + app.py | ✅ CONFIRMED — priority_queue items include doc_id |
| priority_queue contains numero | src/reporting/focus_filter.py | ✅ CONFIRMED — derived from dernier_df which has numero |
| aggregator reads focused_df / focused_doc_ids | src/reporting/aggregator.py:76–98 | ✅ EXISTS — filters by `focused_doc_ids` |
| ui_adapter passes priority_queue | src/reporting/ui_adapter.py:234 | ✅ EXISTS — `"priority_queue": list(dashboard_data.get("priority_queue", []))` |
| get_live_operational exists | src/chain_onion/query_hooks.py:274–276 | ✅ EXISTS — returns DataFrame with family_key column |
| get_legacy_backlog exists | src/chain_onion/query_hooks.py:279–281 | ✅ EXISTS — returns DataFrame with family_key column |
| QueryContext exists | src/chain_onion/query_hooks.py:80–114 | ✅ EXISTS — accepts output_dir, exposes .scores() |

## apply_focus_filter call sites in app.py

| Method | Line |
|--------|------|
| get_dashboard_data() | 361 |
| get_consultant_list() | 396 |
| get_contractor_list() | 409 |
| get_consultant_fiche() | 424 |
| get_contractor_fiche() | 440 |
| get_doc_details() | 504 |

Plan patches 4 of these: dashboard, consultant_list, contractor_list, doc_details.

## Missing (to be patched)

- `legacy_backlog_count` not yet in ui_adapter.py adapt_overview() → FM-4
- `_build_live_operational_numeros` / `_apply_live_narrowing` not yet in app.py → FM-3
- shell.jsx defaults to false for new users → FM-2
- No backlog badge in overview.jsx → FM-5

## Verdict: READY
