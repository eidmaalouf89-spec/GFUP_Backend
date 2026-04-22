# Step12corrections

**Date:** 2026-04-22  
**Scope:** Recover/verify `src/reporting/consultant_fiche.py` source integrity and remove `.pyc` dependency.

## Result

`src/reporting/consultant_fiche.py` was already complete in this checkout. The truncation described in the prompt was not present when this step was executed.

The current Python runtime is `Python 3.12.10`, so the matching cache file inspected before removal was:

```text
src/reporting/__pycache__/consultant_fiche.cpython-312.pyc
```

The cached code object confirmed that `_build_non_saisi` exists and has the expected constants, including:

```text
PDF_REPORT
GED+PDF_OBS
green
orange
red
obs_enriched
```

## Exact Restored Tail

The source already contained the recovered function tail:

```python
def _build_non_saisi(docs: pd.DataFrame, consultant_name: str) -> dict[str, Any] | None:
    """Compute non-saisi GED stats for BET merge consultants.

    Returns None for non-BET consultants (no badge shown).
    Returns dict with count, pct, badge color for BET consultants.
    """
    if consultant_name not in BET_MERGE_KEYS:
        return None

    if docs.empty or "response_source" not in docs.columns:
        return {"count": 0, "pct": 0.0, "badge": "green", "total_answered": 0}

    # Count answered docs (closed = has a final status)
    closed_mask = ~docs["_is_open"]
    total_answered = int(closed_mask.sum())

    if total_answered == 0:
        return {"count": 0, "pct": 0.0, "badge": "green", "total_answered": 0}

    # Count how many of the answered docs came from PDF only
    pdf_only = int(
        ((docs["response_source"] == "PDF_REPORT") & closed_mask).sum()
    ) if "response_source" in docs.columns else 0

    # Also count observation-enriched
    obs_enriched = int(
        (docs["response_source"] == "GED+PDF_OBS").sum()
    ) if "response_source" in docs.columns else 0

    pct = round((pdf_only / total_answered) * 100, 1) if total_answered else 0.0

    if pct < 5:
        badge = "green"
    elif pct < 10:
        badge = "orange"
    else:
        badge = "red"

    return {
        "count": pdf_only,
        "pct": pct,
        "badge": badge,
        "total_answered": total_answered,
        "obs_enriched": obs_enriched,
    }
```

## Validation

| Check | Result |
|---|---|
| `ast.parse(src/reporting/consultant_fiche.py)` | PASS |
| Parsed all `src/**/*.py` files | PASS, 61 files |
| Removed `src/reporting/__pycache__/` | PASS |
| Imported `reporting.consultant_fiche` with `PYTHONDONTWRITEBYTECODE=1` | PASS, source import |
| Confirmed `src/reporting/__pycache__/` stayed absent after import | PASS |
| Imported backend modules `app`, `reporting.consultant_fiche`, `reporting.focus_filter`, `reporting.aggregator` | PASS |
| `npm.cmd run build` in `ui/` | PASS |
| `npm.cmd run check:app` in `ui/` | PASS after elevated rerun for esbuild `spawn EPERM` |

## Cache Dependency

The reporting cache directory was deleted:

```text
src/reporting/__pycache__/
```

The consultant fiche module was then imported with bytecode writing disabled:

```text
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=src
```

This confirms the module imports from source and does not rely on stale `.pyc` files.

## Ambiguity

No source reconstruction ambiguity remained at execution time because the checked-out source already contained the complete `_build_non_saisi` tail and parsed cleanly before any edits. No logic changes were made to `src/reporting/consultant_fiche.py`.
