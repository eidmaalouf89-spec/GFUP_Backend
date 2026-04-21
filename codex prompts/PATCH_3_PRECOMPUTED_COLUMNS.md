# PATCH 3 — Pre-Computed Focus Columns on dernier_df

## OBJECTIVE

Add pre-computed date-distance columns to `dernier_df` inside `data_loader.py` so that Focus Mode filtering becomes a single DataFrame filter instead of per-doc loops. These columns are computed ONCE at load time and cached with RunContext.

## RULES

- PATCH ONLY `src/reporting/data_loader.py` — no other files
- Do NOT modify any existing code above the insertion point
- Do NOT modify RunContext dataclass (columns live on dernier_df, not on ctx)
- All date arithmetic uses DATA_DATE from `data_date_val` (already resolved in load_run_context)
- If data_date_val is None, skip the pre-computation (degraded mode handles this)

---

## THE PATCH

In `src/reporting/data_loader.py`, inside the `load_run_context` function, find this block (around line 425-429):

```python
            # Compute MOEX 10-day countdown for all dernier docs
            moex_countdown = compute_moex_countdown(workflow_engine, dernier_ids, data_date=data_date_val)

            logger.info("RunContext loaded: %d docs, %d dernier, %d responses",
                        len(docs_df), len(dernier_df), len(responses_df))
```

INSERT the following block BETWEEN the `moex_countdown` line and the `logger.info` line:

```python
            # ── Pre-compute focus columns on dernier_df ─────────────────
            # These columns enable Focus Mode to filter with DataFrame ops
            # instead of per-doc Python loops. Computed once, cached with ctx.
            try:
                _precompute_focus_columns(
                    dernier_df, responses_df, workflow_engine, data_date_val
                )
                logger.info("Focus columns pre-computed on dernier_df")
            except Exception as e:
                logger.warning("Focus column pre-computation failed (non-fatal): %s", e)
```

Then add the `_precompute_focus_columns` function BEFORE the `load_run_context` function (after the `_parse_gf_sheets` function, around line 264). Insert this:

```python
def _precompute_focus_columns(dernier_df: pd.DataFrame,
                              responses_df: pd.DataFrame,
                              workflow_engine,
                              data_date_val) -> None:
    """Add pre-computed focus columns to dernier_df IN PLACE.

    Columns added:
        _visa_global       : str or None — MOEX visa status
        _visa_global_date  : date or None — date of MOEX visa
        _last_activity_date: date or None — max(submission, any response date)
        _days_since_last_activity: int or None — DATA_DATE - _last_activity_date
        _earliest_deadline : date or None — min(date_limite) among pending responses
        _days_to_deadline  : int or None — earliest_deadline - DATA_DATE (negative = overdue)
        _focus_priority    : int 1-5 — urgency tier from _days_to_deadline
    """
    if data_date_val is None:
        return

    dd = data_date_val.date() if hasattr(data_date_val, 'date') else data_date_val

    # ── 1. VISA GLOBAL per doc (O(N) using cached _doc_approvers) ───
    visa_globals = {}
    visa_dates = {}
    for doc_id in dernier_df["doc_id"]:
        v, vd = workflow_engine.compute_visa_global_with_date(doc_id)
        visa_globals[doc_id] = v
        if vd is not None:
            visa_dates[doc_id] = vd.date() if hasattr(vd, 'date') else vd
        else:
            visa_dates[doc_id] = None

    dernier_df["_visa_global"] = dernier_df["doc_id"].map(visa_globals)
    dernier_df["_visa_global_date"] = dernier_df["doc_id"].map(visa_dates)

    # ── 2. Last activity date (O(M) grouped aggregation) ────────────
    # Get max date_answered per doc from responses
    resp_answered = responses_df[responses_df["date_answered"].notna()].copy()
    if not resp_answered.empty:
        resp_answered["_da_date"] = pd.to_datetime(
            resp_answered["date_answered"], errors="coerce"
        ).dt.date
        last_resp = resp_answered.groupby("doc_id")["_da_date"].max().to_dict()
    else:
        last_resp = {}

    # Compute last activity = max(created_at, last_response_date)
    def _compute_last_activity(row):
        created = row.get("created_at")
        if created is not None and not pd.isna(created):
            created = created.date() if hasattr(created, 'date') else created
        else:
            created = None
        resp_date = last_resp.get(row["doc_id"])
        dates = [d for d in [created, resp_date] if d is not None]
        return max(dates) if dates else None

    dernier_df["_last_activity_date"] = dernier_df.apply(_compute_last_activity, axis=1)

    # Days since last activity
    def _days_since(last_act):
        if last_act is None:
            return None
        try:
            la = last_act.date() if hasattr(last_act, 'date') else last_act
            return (dd - la).days
        except Exception:
            return None

    dernier_df["_days_since_last_activity"] = dernier_df["_last_activity_date"].apply(_days_since)

    # ── 3. Earliest deadline among PENDING responses (O(M) grouped) ─
    pending_resp = responses_df[
        (responses_df["date_status_type"].isin(["PENDING_IN_DELAY", "PENDING_LATE"])) &
        (responses_df["date_limite"].notna())
    ].copy()

    if not pending_resp.empty:
        pending_resp["_dl_date"] = pd.to_datetime(
            pending_resp["date_limite"], errors="coerce"
        ).dt.date
        earliest_dl = pending_resp.groupby("doc_id")["_dl_date"].min().to_dict()
    else:
        earliest_dl = {}

    dernier_df["_earliest_deadline"] = dernier_df["doc_id"].map(earliest_dl)

    # Days to deadline (negative = overdue)
    def _days_to_dl(dl):
        if dl is None or pd.isna(dl):
            return None
        try:
            d = dl.date() if hasattr(dl, 'date') else dl
            return (d - dd).days
        except Exception:
            return None

    dernier_df["_days_to_deadline"] = dernier_df["_earliest_deadline"].apply(_days_to_dl)

    # ── 4. Focus priority tier ──────────────────────────────────────
    def _priority(dtd):
        if dtd is None:
            return 5  # P5 — no deadline
        if dtd < 0:
            return 1  # P1 — overdue
        if dtd <= 5:
            return 2  # P2 — urgent
        if dtd <= 15:
            return 3  # P3 — soon
        return 4      # P4 — comfortable

    dernier_df["_focus_priority"] = dernier_df["_days_to_deadline"].apply(_priority)
```

---

## VERIFICATION

After applying the patch, run:

```bash
python -c "
import ast
ast.parse(open('src/reporting/data_loader.py').read())
print('data_loader.py syntax OK')
"
```

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from reporting.data_loader import _precompute_focus_columns
print('_precompute_focus_columns importable: OK')
"
```

Both must print OK. If either fails, fix before reporting.

Do NOT run the full pipeline or create test files. Apply the patch and verify syntax only.
