"""
src/reporting/consultant_fiche.py

Per-consultant fiche data builder. Output shape matches fiche.jsx's
window.FICHE_DATA contract (see GFUP_REPORTING_ARCHITECTURE_SPEC_v1_2.md §6.4
and the fiche.jsx field schema).

Source of truth: GED dump. GF is used only for sheet/lot structure.
DATA_DATE comes from ctx.data_date (extracted from GED's Détails sheet upstream).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from .data_loader import RunContext

# ── BET consultants whose responses are merged from PDF reports ──────────────
BET_MERGE_KEYS = {
    "AVLS":     "AVLS",
    "SOCOTEC":  "SOCOTEC",
    "Le Sommer": "LeSommer",
    "LeSommer": "LeSommer",
    "Terrell":  "Terrell",   # OBS-ONLY: status from GED, observations from PDF
}

# ── Role resolution from consultant canonical name ───────────────────────────
ROLE_BY_NAME = {
    "MOX":      "Architecte (Hardel + Le Bihan)",
    "GEMO":     "MOEX",
    "Terrell":  "BET Structure",
    "AVLS":     "BET Acoustique",
    "SOCOTEC":  "Bureau de Contrôle",
    "Le Sommer": "AMO HQE",
    "LeSommer": "AMO HQE",
    # Add others as mapping extends. Fallback = "Consultant".
}


def build_consultant_fiche(ctx: RunContext, consultant_name: str) -> dict[str, Any]:
    """Build the fiche.jsx FICHE_DATA payload for one consultant.

    Args:
        ctx: Loaded RunContext (from data_loader.load_run_context).
        consultant_name: Canonical consultant name as used in GED Mission column.

    Returns:
        Dict matching window.FICHE_DATA shape. Always returns a dict; on degraded
        mode, fields are zero/empty but structure is complete.
    """
    # ── Degraded mode short-circuit ──────────────────────────────────────────
    if not ctx.ged_available or ctx.docs_df is None:
        return _empty_fiche(consultant_name, ctx)

    # ── DATA_DATE (anchor for all "current" logic) ───────────────────────────
    data_date = _resolve_data_date(ctx)
    prev_date = data_date - timedelta(days=7)

    # ── Filter GED docs/responses for this consultant ────────────────────────
    docs = _filter_for_consultant(ctx, consultant_name)
    if docs.empty:
        return _empty_fiche(consultant_name, ctx,
                            warnings=[f"No GED rows matched consultant '{consultant_name}'"])

    # ── Status label resolution (s1/s2/s3) ───────────────────────────────────
    s1, s2, s3 = _resolve_status_labels(ctx, consultant_name)

    # ── Attach derived columns used by all blocks ────────────────────────────
    docs = _attach_derived(docs, data_date, s1=s1, s2=s2, s3=s3)

    # ── Build blocks ─────────────────────────────────────────────────────────
    consultant = _build_consultant_meta(ctx, consultant_name)
    header     = _build_header(docs, data_date, s1, s2, s3)
    week_delta = _build_week_delta(docs, data_date, prev_date, s1, s2, s3)
    bloc1      = _build_bloc1(docs, data_date, s1, s2, s3)
    bloc2      = _build_bloc2(bloc1)
    bloc3      = _build_bloc3(docs, ctx, s1, s2, s3)

    return {
        "consultant":  consultant,
        "header":      header,
        "week_delta":  week_delta,
        "bloc1":       bloc1,
        "bloc2":       bloc2,
        "bloc3":       bloc3,
        "degraded_mode": False,
        "warnings":    list(ctx.warnings or []),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Builders
# ═════════════════════════════════════════════════════════════════════════════

def _build_consultant_meta(ctx: RunContext, name: str) -> dict[str, Any]:
    # Stable 1-based ID: alphabetical index in sorted consultant list.
    all_consultants = sorted(ctx.approver_names or [name])
    try:
        cid = all_consultants.index(name) + 1
    except ValueError:
        cid = 0

    merge_key = BET_MERGE_KEYS.get(name)
    role      = ROLE_BY_NAME.get(name, "Consultant")

    return {
        "id":            cid,
        "slug":          _slugify(name),
        "display_name":  name,
        "name":          name,
        "role":          role,
        "merge_key":     merge_key,
    }


def _build_header(docs: pd.DataFrame, data_date: date,
                  s1: str, s2: str, s3: str) -> dict[str, Any]:
    total       = len(docs)
    closed_mask = docs["_status_for_consultant"].isin([s1, s2, s3, "HM"])
    answered    = int(closed_mask.sum())

    s1_count = int((docs["_status_for_consultant"] == s1).sum())
    s2_count = int((docs["_status_for_consultant"] == s2).sum())
    s3_count = int((docs["_status_for_consultant"] == s3).sum())
    hm_count = int((docs["_status_for_consultant"] == "HM").sum())

    open_mask = docs["_is_open"]
    open_count = int(open_mask.sum())
    open_ok    = int((open_mask & docs["_on_time"]).sum())
    open_late  = int((open_mask & ~docs["_on_time"]).sum())

    return {
        "week_num":       data_date.isocalendar()[1],
        "data_date_str":  data_date.strftime("%d/%m/%Y"),
        "total":          total,
        "answered":       answered,
        "s1": s1, "s2": s2, "s3": s3,
        "s1_count": s1_count, "s2_count": s2_count, "s3_count": s3_count,
        "hm_count":   hm_count,
        "open_count": open_count,
        "open_ok":    open_ok,
        "open_late":  open_late,
    }


def _build_week_delta(docs: pd.DataFrame, data_date: date, prev_date: date,
                      s1: str, s2: str, s3: str) -> dict[str, Any]:
    closed_statuses = {s1, s2, s3, "HM"}

    # Docs that existed at each anchor (based on _created_date)
    cur = docs[docs["_created_date"] <= data_date]
    prv = docs[docs["_created_date"] <= prev_date]

    def _stats(df: pd.DataFrame) -> dict:
        if df.empty:
            return {"total": 0, "s1": 0, "s2": 0, "s3": 0, "hm": 0,
                    "open": 0, "open_late": 0, "refus_rate_pct": 0.0}
        closed   = df["_status_for_consultant"].isin(closed_statuses)
        answered = int(closed.sum())
        s1c = int((df["_status_for_consultant"] == s1).sum())
        s2c = int((df["_status_for_consultant"] == s2).sum())
        s3c = int((df["_status_for_consultant"] == s3).sum())
        hmc = int((df["_status_for_consultant"] == "HM").sum())
        opn = int(df["_is_open"].sum())
        olt = int((df["_is_open"] & ~df["_on_time"]).sum())
        refus_pct = round((s3c / answered) * 100, 1) if answered else 0.0
        return {
            "total": len(df), "s1": s1c, "s2": s2c, "s3": s3c, "hm": hmc,
            "open": opn, "open_late": olt, "refus_rate_pct": refus_pct,
        }

    c, p = _stats(cur), _stats(prv)
    return {
        "total":          c["total"] - p["total"],
        "s1":             c["s1"]    - p["s1"],
        "s2":             c["s2"]    - p["s2"],
        "s3":             c["s3"]    - p["s3"],
        "hm":             c["hm"]    - p["hm"],
        "open":           c["open"]  - p["open"],
        "open_late":      c["open_late"] - p["open_late"],
        "refus_rate_pct": round(c["refus_rate_pct"] - p["refus_rate_pct"], 1),
    }


def _build_bloc1(docs: pd.DataFrame, data_date: date,
                 s1: str, s2: str, s3: str) -> list[dict[str, Any]]:
    if docs.empty:
        return []

    closed_statuses = {s1, s2, s3, "HM"}

    # Month range: from first doc creation to DATA_DATE month (inclusive).
    first_created = docs["_created_date"].min()
    months = _month_range(first_created, data_date)
    current_ym = (data_date.year, data_date.month)

    # Limit to last 18 months max.
    if len(months) > 18:
        months = months[-18:]

    rows = []
    for y, m in months:
        month_start = date(y, m, 1)
        month_end   = _month_last_day(y, m)

        created_in_month = docs[
            (docs["_created_date"] >= month_start) & (docs["_created_date"] <= month_end)
        ]
        closed_in_month = docs[
            docs["_date_answered"].notna() &
            (docs["_date_answered"] >= month_start) & (docs["_date_answered"] <= month_end) &
            docs["_status_for_consultant"].isin(closed_statuses)
        ]

        nvx       = int(len(created_in_month))
        doc_ferme = int(len(closed_in_month))

        def _count(label: str) -> int:
            return int((closed_in_month["_status_for_consultant"] == label).sum())

        s1c = _count(s1); s2c = _count(s2); s3c = _count(s3); hmc = _count("HM")

        def _pct(c: int) -> float | None:
            return round((c / doc_ferme) * 100, 1) if doc_ferme else None

        # End-of-month open snapshot: docs existing by month_end, still open at month_end,
        # evaluated against month_end itself for on-time/late classification.
        snapshot = docs[docs["_created_date"] <= month_end]
        # A doc is open at month_end if it wasn't closed by month_end
        open_at_end = snapshot[snapshot.apply(
            lambda r: r["_open_at_date"](month_end), axis=1
        )]
        # For month-end snapshots, use _on_time which is derived from date_status_type.
        # This is an approximation: the late/on-time status at DATA_DATE is used for
        # historical snapshots too (we don't have per-month deadline data).
        open_ok    = int(open_at_end["_on_time"].sum())
        open_late  = int(len(open_at_end)) - open_ok

        rows.append({
            "label":      f"{y:04d}-{m:02d}",
            "is_current": (y, m) == current_ym,
            "nvx":        nvx,
            "doc_ferme":  doc_ferme,
            "s1": s1c, "s1_pct": _pct(s1c),
            "s2": s2c, "s2_pct": _pct(s2c),
            "s3": s3c, "s3_pct": _pct(s3c),
            "hm": hmc, "hm_pct": _pct(hmc),
            "open_ok":   open_ok,
            "open_late": open_late,
        })
    return rows


def _build_bloc2(bloc1: list[dict]) -> dict[str, Any]:
    labels, s1s, s2s, s3s, hms, opens, tots = [], [], [], [], [], [], []
    c1 = c2 = c3 = chm = 0
    for row in bloc1:
        c1  += row["s1"]
        c2  += row["s2"]
        c3  += row["s3"]
        chm += row["hm"]
        open_level = row["open_ok"] + row["open_late"]
        total = c1 + c2 + c3 + chm + open_level
        labels.append(row["label"])
        s1s.append(c1); s2s.append(c2); s3s.append(c3)
        hms.append(chm); opens.append(open_level); tots.append(total)
    return {
        "labels":       labels,
        "s1_series":    s1s,
        "s2_series":    s2s,
        "s3_series":    s3s,
        "hm_series":    hms,
        "open_series":  opens,
        "totals":       tots,
    }


def _build_bloc3(docs: pd.DataFrame, ctx: RunContext,
                 s1: str, s2: str, s3: str) -> dict[str, Any]:
    if docs.empty:
        return _empty_bloc3(s1, s2, s3)

    # Group by GF sheet (resolved from NUMERO → gf_sheet mapping in ctx).
    g = docs.groupby("_gf_sheet", dropna=True)

    lots = []
    for sheet_name, sub in g:
        vso = int((sub["_status_for_consultant"] == s1).sum())
        vao = int((sub["_status_for_consultant"] == s2).sum())
        ref = int((sub["_status_for_consultant"] == s3).sum())
        hm  = int((sub["_status_for_consultant"] == "HM").sum())
        ook = int((sub["_is_open"] & sub["_on_time"]).sum())
        olt = int((sub["_is_open"] & ~sub["_on_time"]).sum())
        total = int(len(sub))

        # Populate BOTH the dynamic-keyed fields (s1/s2/s3 values) AND the
        # canonical VSO/VAO/REF fields so the JSX can index either way.
        row = {
            "name":      str(sheet_name),
            "total":     total,
            "VSO":       vso,
            "VAO":       vao,
            "REF":       ref,
            "HM":        hm,
            "open_ok":   ook,
            "open_late": olt,
        }
        # If a consultant uses non-default s1/s2/s3 labels, also mirror them:
        row.setdefault(s1, vso)
        row.setdefault(s2, vao)
        row.setdefault(s3, ref)
        lots.append(row)

    lots.sort(key=lambda r: -r["total"])

    # Totals
    def _sum(key: str) -> int:
        return int(sum(r[key] for r in lots))

    total_row = {
        "total":     _sum("total"),
        "VSO":       _sum("VSO"),
        "VAO":       _sum("VAO"),
        "REF":       _sum("REF"),
        "HM":        _sum("HM"),
        "open_ok":   _sum("open_ok"),
        "open_late": _sum("open_late"),
    }
    total_row.setdefault(s1, total_row["VSO"])
    total_row.setdefault(s2, total_row["VAO"])
    total_row.setdefault(s3, total_row["REF"])

    donut_ok   = total_row["open_ok"]
    donut_late = total_row["open_late"]

    # Critical lots — top 5 by open_late desc (open_late > 0 only)
    critical_lots = [
        {"name": r["name"], "open_late": r["open_late"]}
        for r in sorted(lots, key=lambda r: -r["open_late"])
        if r["open_late"] > 0
    ][:5]

    # Rejection rate lots — lots with >=3 closed docs, top 5 by %
    def _refus_pct(r: dict) -> float:
        closed = r["VSO"] + r["VAO"] + r["REF"] + r["HM"]
        return round((r["REF"] / closed) * 100, 1) if closed >= 3 else -1.0

    refus_scored = [(r, _refus_pct(r)) for r in lots]
    refus_scored = [(r, p) for r, p in refus_scored if p >= 0]
    refus_scored.sort(key=lambda rp: -rp[1])
    refus_lots = [
        [{"name": r["name"]}, p] for r, p in refus_scored[:5]
    ]

    return {
        "s1": s1, "s2": s2, "s3": s3,
        "lots":          lots,
        "total_row":     total_row,
        "donut_total":   donut_ok + donut_late,
        "donut_ok":      donut_ok,
        "donut_late":    donut_late,
        "critical_lots": critical_lots,
        "refus_lots":    refus_lots,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _resolve_data_date(ctx: RunContext) -> date:
    d = getattr(ctx, "data_date", None)
    if d is None:
        # Fallback to run_date; warn.
        ctx.warnings.append("data_date missing on ctx; falling back to run_date")
        d = datetime.fromisoformat(ctx.run_date).date() if ctx.run_date else date.today()
    if isinstance(d, datetime):
        d = d.date()
    return d


def _resolve_status_labels(ctx: RunContext, name: str) -> tuple[str, str, str]:
    """Returns (s1, s2, s3) for the consultant.

    Reads ctx.ged_status_labels[name] if present. Default: (VSO, VAO, REF).
    Terrell is OBS-ONLY but still uses VSO/VAO/REF where present.
    """
    mapping = getattr(ctx, "ged_status_labels", {}) or {}
    labels = mapping.get(name) or mapping.get(_slugify(name)) or {}
    return (labels.get("s1", "VSO"),
            labels.get("s2", "VAO"),
            labels.get("s3", "REF"))


def _filter_for_consultant(ctx: RunContext, name: str) -> pd.DataFrame:
    """Return a merged DataFrame of docs + this consultant's responses.

    The GED data model has two tables:
      - docs_df:      one row per document (doc_id, lot, numero, created_at, ...)
      - responses_df: one row per approver per document (doc_id, approver_canonical,
                      status_clean, date_answered, date_status_type, ...)

    We filter responses_df for this consultant, then left-join onto docs_df to get
    all document-level columns. NOT_CALLED rows are excluded (consultant not called
    for that document).

    Returns a DataFrame with both doc columns and response columns.
    """
    if ctx.responses_df is None or ctx.responses_df.empty:
        return pd.DataFrame()

    resp = ctx.responses_df
    docs = ctx.docs_df

    # Filter responses for this consultant (exclude NOT_CALLED = not participating)
    cons_resp = resp[
        (resp["approver_canonical"] == name) &
        (resp["date_status_type"] != "NOT_CALLED")
    ].copy()

    if cons_resp.empty:
        return pd.DataFrame()

    # Merge with docs to get document-level columns (lot, created_at, etc.)
    # Use inner join: only docs that have a response row for this consultant.
    merged = cons_resp.merge(docs, on="doc_id", how="inner", suffixes=("_resp", "_doc"))

    return merged


def _attach_derived(df: pd.DataFrame, data_date: date,
                    s1: str, s2: str, s3: str) -> pd.DataFrame:
    """Attach all derived columns used by the block builders.

    The input df is a merged docs+responses DataFrame from _filter_for_consultant.
    Actual columns from the pipeline:
      - status_clean:      VSO / VAO / REF / HM / "" (from normalize_responses)
      - date_status_type:  ANSWERED / PENDING_IN_DELAY / PENDING_LATE
      - date_answered:     datetime or None (from normalize_responses)
      - created_at:        datetime (from normalize_docs)
      - lot_normalized:    str (from normalize_docs)

    Derived columns added:
      _status_for_consultant : str   (mapped from status_clean: s1/s2/s3/HM/"")
      _created_date          : date  (from created_at)
      _date_answered         : date  (from date_answered)
      _is_open               : bool  (not answered yet)
      _on_time               : bool  (PENDING_IN_DELAY, not PENDING_LATE)
      _gf_sheet              : str   (lot label for bloc3 grouping)
      _open_at_date          : callable (for bloc1 month-end snapshots)
    """
    closed_statuses = {s1, s2, s3, "HM"}

    # ── Status: use status_clean from responses (already normalised to VSO/VAO/REF/HM)
    if "status_clean" in df.columns:
        df["_status_for_consultant"] = df["status_clean"].fillna("").astype(str).str.upper()
    else:
        df["_status_for_consultant"] = ""

    # ── Dates: created_at comes from normalize_docs, date_answered from normalize_responses
    if "created_at" in df.columns:
        df["_created_date"] = pd.to_datetime(df["created_at"], errors="coerce").dt.date
    else:
        df["_created_date"] = pd.NaT

    # date_answered may exist from both tables after merge; prefer the response one
    da_col = "date_answered_resp" if "date_answered_resp" in df.columns else (
             "date_answered" if "date_answered" in df.columns else None)
    if da_col:
        df["_date_answered"] = pd.to_datetime(df[da_col], errors="coerce").dt.date
    else:
        df["_date_answered"] = pd.NaT

    # ── GF sheet: prefer gf_sheet, then lot_normalized, then lot
    for col in ("gf_sheet", "lot_normalized", "lot"):
        if col in df.columns:
            df["_gf_sheet"] = df[col].fillna("").astype(str)
            break
    else:
        df["_gf_sheet"] = ""

    # ── Open/closed: a doc is open if the consultant hasn't rendered a final status
    df["_is_open"] = ~df["_status_for_consultant"].isin(closed_statuses)

    # ── On-time / late: derived from date_status_type (PENDING_LATE = late)
    if "date_status_type" in df.columns:
        df["_on_time"] = df.apply(
            lambda r: (not r["_is_open"]) or (r["date_status_type"] != "PENDING_LATE"),
            axis=1,
        )
    else:
        df["_on_time"] = True

    # ── Open-at-date-d helper: for bloc1 end-of-month snapshots
    def _make_open_checker(status, answered_date):
        def _check(d: date) -> bool:
            if status in closed_statuses and pd.notna(answered_date) and answered_date <= d:
                return False
            return True
        return _check

    df["_open_at_date"] = df.apply(
        lambda r: _make_open_checker(r["_status_for_consultant"], r["_date_answered"]),
        axis=1,
    )
    return df


def _month_range(start: date, end: date) -> list[tuple[int, int]]:
    if pd.isna(start) or pd.isna(end):
        return []
    y, m = start.year, start.month
    out = []
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _month_last_day(y: int, m: int) -> date:
    if m == 12:
        return date(y, 12, 31)
    return date(y, m + 1, 1) - timedelta(days=1)


def _slugify(name: str) -> str:
    return "".join(ch for ch in name if ch.isalnum())


def _empty_fiche(name: str, ctx: RunContext,
                 warnings: list[str] | None = None) -> dict[str, Any]:
    s1, s2, s3 = "VSO", "VAO", "REF"
    return {
        "consultant": {
            "id": 0, "slug": _slugify(name), "display_name": name,
            "name": name, "role": ROLE_BY_NAME.get(name, "Consultant"),
            "merge_key": BET_MERGE_KEYS.get(name),
        },
        "header": {
            "week_num": 0, "data_date_str": "",
            "total": 0, "answered": 0,
            "s1": s1, "s2": s2, "s3": s3,
            "s1_count": 0, "s2_count": 0, "s3_count": 0,
            "hm_count": 0, "open_count": 0, "open_ok": 0, "open_late": 0,
        },
        "week_delta": {"total": 0, "s1": 0, "s2": 0, "s3": 0, "hm": 0,
                       "open": 0, "open_late": 0, "refus_rate_pct": 0.0},
        "bloc1": [],
        "bloc2": {"labels": [], "s1_series": [], "s2_series": [], "s3_series": [],
                  "hm_series": [], "open_series": [], "totals": []},
        "bloc3": _empty_bloc3(s1, s2, s3),
        "degraded_mode": True,
        "warnings": list(ctx.warnings or []) + (warnings or []),
    }


def _empty_bloc3(s1: str, s2: str, s3: str) -> dict[str, Any]:
    return {
        "s1": s1, "s2": s2, "s3": s3,
        "lots": [],
        "total_row": {"total": 0, "VSO": 0, "VAO": 0, "REF": 0, "HM": 0,
                      "open_ok": 0, "open_late": 0},
        "donut_total": 0, "donut_ok": 0, "donut_late": 0,
        "critical_lots": [], "refus_lots": [],
    }
