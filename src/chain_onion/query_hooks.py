"""
src/chain_onion/query_hooks.py
-------------------------------
Step 13 — Query Hooks Engine.

Fast, reusable Python query functions for UI / dashboard / reporting.

This module ONLY reads finalized outputs.  It does NOT recompute pipeline logic.

Public API
----------
QueryContext(...)               lightweight context with cached DataFrames / paths

Core priority
    get_top_issues(ctx, limit=20)
    get_escalated_chains(ctx, limit=50)
    get_live_operational(ctx, limit=None)
    get_legacy_backlog(ctx, limit=None)
    get_archived(ctx, limit=None)

Blocking ownership
    get_waiting_primary(ctx, limit=None)
    get_waiting_secondary(ctx, limit=None)
    get_waiting_moex(ctx, limit=None)
    get_waiting_corrected(ctx, limit=None)
    get_mixed_blockers(ctx, limit=None)

Theme drivers
    get_contractor_quality(ctx, limit=None)
    get_sas_friction(ctx, limit=None)
    get_primary_consultant_delay(ctx, limit=None)
    get_secondary_consultant_delay(ctx, limit=None)
    get_moex_delay(ctx, limit=None)
    get_data_contradictions(ctx, limit=None)

Metrics
    get_high_pressure(ctx, min_score=70)
    get_stale_chains(ctx, min_days=60)
    get_zero_score_chains(ctx)
    get_recently_active(ctx, days=30)

Search
    search_family_key(ctx, text)
    search_numero(ctx, text)

Summary
    get_dashboard_summary(ctx)
    get_portfolio_snapshot(ctx)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

_LOG = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = Path("output/chain_onion")
_SORT_RANK = ["action_priority_rank", "family_key"]

_THEME_COLS = [
    "contractor_impact_score",
    "sas_impact_score",
    "consultant_primary_impact_score",
    "consultant_secondary_impact_score",
    "moex_impact_score",
    "contradiction_impact_score",
]


# =============================================================================
# QueryContext
# =============================================================================

@dataclass
class QueryContext:
    """Lightweight context object.  Holds pre-loaded DataFrames and paths.

    Pass DataFrames directly (fast, for pipeline integration):
        ctx = QueryContext(onion_scores_df=df)

    Or let it load from disk on first access (for UI / reporting):
        ctx = QueryContext(output_dir=Path("output/chain_onion"))

    DataFrames are cached on first access — no repeated disk reads.
    """

    # In-memory DataFrames (preferred source)
    onion_scores_df: Optional[pd.DataFrame] = None
    chain_narratives_df: Optional[pd.DataFrame] = None
    chain_metrics_df: Optional[pd.DataFrame] = None

    # Pre-loaded JSON (optional)
    _dashboard_summary: Optional[dict] = field(default=None, repr=False)
    _top_issues: Optional[list] = field(default=None, repr=False)

    # Disk fallback path
    output_dir: Path = field(default_factory=lambda: Path("output/chain_onion"))

    # Internal read-through cache (not set by callers)
    _scores_cache: Optional[pd.DataFrame] = field(default=None, repr=False, init=False)
    _narratives_cache: Optional[pd.DataFrame] = field(default=None, repr=False, init=False)
    _metrics_cache: Optional[pd.DataFrame] = field(default=None, repr=False, init=False)
    _dashboard_cache: Optional[dict] = field(default=None, repr=False, init=False)
    _top_issues_cache: Optional[list] = field(default=None, repr=False, init=False)

    def __post_init__(self) -> None:
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)

    # ── Accessors ─────────────────────────────────────────────────────────────

    def scores(self) -> pd.DataFrame:
        """ONION_SCORES — primary filter table."""
        if self._scores_cache is not None:
            return self._scores_cache
        if self.onion_scores_df is not None:
            self._scores_cache = self.onion_scores_df.copy()
            return self._scores_cache
        self._scores_cache = _load_csv(self.output_dir / "ONION_SCORES.csv")
        return self._scores_cache

    def narratives(self) -> pd.DataFrame:
        """CHAIN_NARRATIVES — text / label table."""
        if self._narratives_cache is not None:
            return self._narratives_cache
        if self.chain_narratives_df is not None:
            self._narratives_cache = self.chain_narratives_df.copy()
            return self._narratives_cache
        self._narratives_cache = _load_csv(self.output_dir / "CHAIN_NARRATIVES.csv")
        return self._narratives_cache

    def metrics(self) -> pd.DataFrame:
        """CHAIN_METRICS — lifecycle / stale metrics."""
        if self._metrics_cache is not None:
            return self._metrics_cache
        if self.chain_metrics_df is not None:
            self._metrics_cache = self.chain_metrics_df.copy()
            return self._metrics_cache
        self._metrics_cache = _load_csv(self.output_dir / "CHAIN_METRICS.csv")
        return self._metrics_cache

    def dashboard(self) -> dict:
        """dashboard_summary.json dict."""
        if self._dashboard_cache is not None:
            return self._dashboard_cache
        if self._dashboard_summary is not None:
            self._dashboard_cache = dict(self._dashboard_summary)
            return self._dashboard_cache
        self._dashboard_cache = _load_json_dict(self.output_dir / "dashboard_summary.json")
        return self._dashboard_cache

    def top_issues_raw(self) -> list:
        """top_issues.json list."""
        if self._top_issues_cache is not None:
            return self._top_issues_cache
        if self._top_issues is not None:
            self._top_issues_cache = list(self._top_issues)
            return self._top_issues_cache
        self._top_issues_cache = _load_json_list(self.output_dir / "top_issues.json")
        return self._top_issues_cache


# =============================================================================
# Private helpers
# =============================================================================

def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        _LOG.warning("CSV not found: %s — returning empty DataFrame", path)
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as exc:
        _LOG.error("Failed to read %s: %s", path, exc)
        return pd.DataFrame()


def _load_json_dict(path: Path) -> dict:
    if not path.exists():
        _LOG.warning("JSON not found: %s — returning empty dict", path)
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _LOG.error("Failed to read %s: %s", path, exc)
        return {}


def _load_json_list(path: Path) -> list:
    if not path.exists():
        _LOG.warning("JSON not found: %s — returning empty list", path)
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:
        _LOG.error("Failed to read %s: %s", path, exc)
        return []


def _sort_by_rank(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in _SORT_RANK if c in df.columns]
    if not cols:
        return df
    return df.sort_values(cols, ascending=True).reset_index(drop=True)


def _apply_limit(df: pd.DataFrame, limit: Optional[int]) -> pd.DataFrame:
    if limit is None or limit <= 0:
        return df
    return df.head(limit)


def _col_numeric(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce").fillna(0)


def _filter_eq(df: pd.DataFrame, col: str, value: object) -> pd.DataFrame:
    if col not in df.columns:
        _LOG.debug("Column %r absent — empty result", col)
        return df.iloc[0:0].copy()
    return df[df[col] == value].copy()


def _filter_gt(df: pd.DataFrame, col: str, threshold: float) -> pd.DataFrame:
    if col not in df.columns:
        return df.iloc[0:0].copy()
    return df[_col_numeric(df, col) > threshold].copy()


def _filter_gte(df: pd.DataFrame, col: str, threshold: float) -> pd.DataFrame:
    if col not in df.columns:
        return df.iloc[0:0].copy()
    return df[_col_numeric(df, col) >= threshold].copy()


def _filter_eq0(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col not in df.columns:
        return df.iloc[0:0].copy()
    return df[_col_numeric(df, col) == 0].copy()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# =============================================================================
# Core Priority
# =============================================================================

def get_top_issues(ctx: QueryContext, limit: int = 20) -> pd.DataFrame:
    """Top chains by action_priority_rank ascending (rank 1 = most urgent)."""
    df = ctx.scores()
    df = _sort_by_rank(df)
    return _apply_limit(df, limit).reset_index(drop=True)


def get_escalated_chains(ctx: QueryContext, limit: int = 50) -> pd.DataFrame:
    """Chains where escalation_flag == True, sorted by rank."""
    df = ctx.scores()
    if "escalation_flag" not in df.columns:
        return pd.DataFrame()
    mask = df["escalation_flag"].astype(str).str.lower().isin({"true", "1", "yes"})
    result = df[mask].copy()
    return _apply_limit(_sort_by_rank(result), limit).reset_index(drop=True)


def get_live_operational(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains with portfolio_bucket == LIVE_OPERATIONAL, sorted by rank."""
    return _apply_limit(_sort_by_rank(_filter_eq(ctx.scores(), "portfolio_bucket", "LIVE_OPERATIONAL")), limit).reset_index(drop=True)


def get_legacy_backlog(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains with portfolio_bucket == LEGACY_BACKLOG, sorted by rank."""
    return _apply_limit(_sort_by_rank(_filter_eq(ctx.scores(), "portfolio_bucket", "LEGACY_BACKLOG")), limit).reset_index(drop=True)


def get_archived(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains with portfolio_bucket == ARCHIVED_HISTORICAL, sorted by rank."""
    return _apply_limit(_sort_by_rank(_filter_eq(ctx.scores(), "portfolio_bucket", "ARCHIVED_HISTORICAL")), limit).reset_index(drop=True)


# =============================================================================
# Blocking Ownership
# =============================================================================

def get_waiting_primary(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains in OPEN_WAITING_PRIMARY_CONSULTANT state."""
    return _apply_limit(_sort_by_rank(_filter_eq(ctx.scores(), "current_state", "OPEN_WAITING_PRIMARY_CONSULTANT")), limit).reset_index(drop=True)


def get_waiting_secondary(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains in OPEN_WAITING_SECONDARY_CONSULTANT state."""
    return _apply_limit(_sort_by_rank(_filter_eq(ctx.scores(), "current_state", "OPEN_WAITING_SECONDARY_CONSULTANT")), limit).reset_index(drop=True)


def get_waiting_moex(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains in OPEN_WAITING_MOEX state."""
    return _apply_limit(_sort_by_rank(_filter_eq(ctx.scores(), "current_state", "OPEN_WAITING_MOEX")), limit).reset_index(drop=True)


def get_waiting_corrected(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains in WAITING_CORRECTED_INDICE state."""
    return _apply_limit(_sort_by_rank(_filter_eq(ctx.scores(), "current_state", "WAITING_CORRECTED_INDICE")), limit).reset_index(drop=True)


def get_mixed_blockers(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains in OPEN_WAITING_MIXED_CONSULTANTS state."""
    return _apply_limit(_sort_by_rank(_filter_eq(ctx.scores(), "current_state", "OPEN_WAITING_MIXED_CONSULTANTS")), limit).reset_index(drop=True)


# =============================================================================
# Theme Drivers
# =============================================================================

def _theme_query(ctx: QueryContext, col: str, limit: Optional[int]) -> pd.DataFrame:
    return _apply_limit(_sort_by_rank(_filter_gt(ctx.scores(), col, 0)), limit).reset_index(drop=True)


def get_contractor_quality(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains where contractor_impact_score > 0."""
    return _theme_query(ctx, "contractor_impact_score", limit)


def get_sas_friction(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains where sas_impact_score > 0."""
    return _theme_query(ctx, "sas_impact_score", limit)


def get_primary_consultant_delay(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains where consultant_primary_impact_score > 0."""
    return _theme_query(ctx, "consultant_primary_impact_score", limit)


def get_secondary_consultant_delay(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains where consultant_secondary_impact_score > 0."""
    return _theme_query(ctx, "consultant_secondary_impact_score", limit)


def get_moex_delay(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains where moex_impact_score > 0."""
    return _theme_query(ctx, "moex_impact_score", limit)


def get_data_contradictions(ctx: QueryContext, limit: Optional[int] = None) -> pd.DataFrame:
    """Chains where contradiction_impact_score > 0."""
    return _theme_query(ctx, "contradiction_impact_score", limit)


# =============================================================================
# Metrics
# =============================================================================

def get_high_pressure(ctx: QueryContext, min_score: float = 70.0) -> pd.DataFrame:
    """Chains where normalized_score_100 >= min_score."""
    return _sort_by_rank(_filter_gte(ctx.scores(), "normalized_score_100", min_score)).reset_index(drop=True)


def get_stale_chains(ctx: QueryContext, min_days: int = 60) -> pd.DataFrame:
    """Chains where stale_days >= min_days.  Merges CHAIN_METRICS when needed."""
    scores = ctx.scores()
    if "stale_days" in scores.columns:
        source = scores
    else:
        metrics = ctx.metrics()
        if metrics.empty or "stale_days" not in metrics.columns:
            return pd.DataFrame()
        if scores.empty:
            source = metrics
        else:
            source = scores.merge(
                metrics[["family_key", "stale_days"]].drop_duplicates("family_key"),
                on="family_key",
                how="left",
            )
    return _sort_by_rank(_filter_gte(source, "stale_days", float(min_days))).reset_index(drop=True)


def get_zero_score_chains(ctx: QueryContext) -> pd.DataFrame:
    """Chains where normalized_score_100 == 0."""
    return _sort_by_rank(_filter_eq0(ctx.scores(), "normalized_score_100")).reset_index(drop=True)


def get_recently_active(ctx: QueryContext, days: int = 30) -> pd.DataFrame:
    """Chains active within the last N days relative to portfolio max date."""
    scores = ctx.scores()
    metrics = ctx.metrics()

    # Pick the best date column available
    date_col: Optional[str] = None
    date_source: Optional[pd.DataFrame] = None
    for col in ("last_real_activity_date", "latest_submission_date"):
        if col in scores.columns:
            date_col, date_source = col, scores
            break
        if col in metrics.columns:
            date_col, date_source = col, metrics
            break

    if date_col is None or date_source is None:
        return pd.DataFrame()

    parsed = pd.to_datetime(date_source[date_col], errors="coerce")
    if parsed.dropna().empty:
        return pd.DataFrame()

    cutoff = parsed.max() - pd.Timedelta(days=days)
    mask = parsed >= cutoff

    if date_source is scores:
        result = scores[mask].copy()
    else:
        # Bring date into scores via merge
        dated = date_source.loc[mask, ["family_key", date_col]].drop_duplicates("family_key")
        result = scores.merge(dated, on="family_key", how="inner")

    return _sort_by_rank(result).reset_index(drop=True)


# =============================================================================
# Search
# =============================================================================

def _rank_matches(series: pd.Series, text: str) -> pd.Series:
    """Integer rank: 1=exact, 2=startswith, 3=contains; 4=no match."""
    t = text.lower()
    s = series.astype(str).str.lower()
    ranks = pd.Series(4, index=series.index, dtype=int)
    ranks[s.str.contains(t, na=False, regex=False)] = 3
    ranks[s.str.startswith(t, na=False)] = 2
    ranks[s == t] = 1
    return ranks


def search_family_key(ctx: QueryContext, text: str) -> pd.DataFrame:
    """Case-insensitive search on family_key.  Returns ranked DataFrame (exact first)."""
    df = ctx.scores()
    if df.empty or "family_key" not in df.columns or not text:
        return pd.DataFrame()
    ranks = _rank_matches(df["family_key"], text)
    matched = df[ranks < 4].copy()
    matched["_search_rank"] = ranks[ranks < 4].values
    matched = matched.sort_values(["_search_rank", "family_key"]).drop(columns=["_search_rank"])
    return matched.reset_index(drop=True)


def search_numero(ctx: QueryContext, text: str) -> pd.DataFrame:
    """Case-insensitive search on numero.  Returns ranked DataFrame (exact first)."""
    df = ctx.scores()
    if df.empty or "numero" not in df.columns or not text:
        return pd.DataFrame()
    ranks = _rank_matches(df["numero"], text)
    matched = df[ranks < 4].copy()
    matched["_search_rank"] = ranks[ranks < 4].values
    matched = matched.sort_values(["_search_rank", "numero"]).drop(columns=["_search_rank"])
    return matched.reset_index(drop=True)


# =============================================================================
# Summary
# =============================================================================

def get_dashboard_summary(ctx: QueryContext) -> dict:
    """Return dashboard_summary dict.  Uses JSON cache; falls back to DataFrame compute."""
    cached = ctx.dashboard()
    if cached:
        return cached
    return _compute_snapshot(ctx)


def get_portfolio_snapshot(ctx: QueryContext) -> dict:
    """Always compute portfolio snapshot from DataFrames (authoritative read)."""
    return _compute_snapshot(ctx)


# =============================================================================
# Private summary helpers
# =============================================================================

def _compute_snapshot(ctx: QueryContext) -> dict:
    scores = ctx.scores()
    if scores.empty:
        return {
            "total_chains": 0,
            "live_chains": 0,
            "legacy_chains": 0,
            "archived_chains": 0,
            "escalated_chain_count": 0,
            "avg_live_score": 0.0,
            "top_theme_by_impact": "UNKNOWN",
            "generated_at": _now_iso(),
        }

    bucket_col = scores.get("portfolio_bucket", pd.Series(dtype=str)) if "portfolio_bucket" not in scores.columns else scores["portfolio_bucket"]
    live_mask     = scores["portfolio_bucket"] == "LIVE_OPERATIONAL"     if "portfolio_bucket" in scores.columns else pd.Series(False, index=scores.index)
    legacy_mask   = scores["portfolio_bucket"] == "LEGACY_BACKLOG"       if "portfolio_bucket" in scores.columns else pd.Series(False, index=scores.index)
    archived_mask = scores["portfolio_bucket"] == "ARCHIVED_HISTORICAL"  if "portfolio_bucket" in scores.columns else pd.Series(False, index=scores.index)

    avg_live = 0.0
    if "normalized_score_100" in scores.columns and live_mask.any():
        avg_live = round(float(scores.loc[live_mask, "normalized_score_100"].mean()), 2)

    escalated = 0
    if "escalation_flag" in scores.columns:
        esc = scores["escalation_flag"].astype(str).str.lower().isin({"true", "1", "yes"})
        escalated = int(esc.sum())

    # top_theme: prefer dashboard JSON, then compute from scores
    dash = ctx.dashboard()
    top_theme = dash.get("top_theme_by_impact") or _top_theme_from_scores(scores)

    return {
        "total_chains": len(scores),
        "live_chains": int(live_mask.sum()),
        "legacy_chains": int(legacy_mask.sum()),
        "archived_chains": int(archived_mask.sum()),
        "escalated_chain_count": escalated,
        "avg_live_score": avg_live,
        "top_theme_by_impact": top_theme,
        "generated_at": _now_iso(),
    }


def _top_theme_from_scores(scores: pd.DataFrame) -> str:
    present = [c for c in _THEME_COLS if c in scores.columns]
    if not present:
        return "UNKNOWN"
    totals = {c: pd.to_numeric(scores[c], errors="coerce").fillna(0).sum() for c in present}
    return max(totals, key=totals.get)
