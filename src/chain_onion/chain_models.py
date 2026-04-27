"""
src/chain_onion/chain_models.py
--------------------------------
Step 05 — Lightweight dataclasses for chain grouper outputs.

These are optional typed containers — useful for IDE support and
explicit field documentation. The grouper functions return DataFrames;
these dataclasses are helpers for downstream consumers that prefer
object access over column indexing.

Only two types are defined here. Both are intentionally thin wrappers
around the column contracts in STEP02.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class VersionSummary:
    """
    Typed view of one row from chain_versions DataFrame.

    Mirrors the _CHAIN_VERSIONS_COLS contract from family_grouper.py.
    All date fields are pandas Timestamps or NaT.
    """
    family_key: str
    version_key: str
    numero: str
    indice: str
    row_count_ops: int
    first_submission_date: Optional[pd.Timestamp]
    latest_submission_date: Optional[pd.Timestamp]
    latest_response_date: Optional[pd.Timestamp]
    has_blocking_rows: bool
    blocking_actor_count: int
    requires_new_cycle_flag: bool
    completed_row_count: int
    source_row_count: int
    version_sort_order: int

    @classmethod
    def from_row(cls, row: pd.Series) -> "VersionSummary":
        return cls(
            family_key=str(row["family_key"]),
            version_key=str(row["version_key"]),
            numero=str(row["numero"]),
            indice=str(row["indice"]),
            row_count_ops=int(row["row_count_ops"]),
            first_submission_date=row["first_submission_date"] if pd.notna(row["first_submission_date"]) else None,
            latest_submission_date=row["latest_submission_date"] if pd.notna(row["latest_submission_date"]) else None,
            latest_response_date=row["latest_response_date"] if pd.notna(row["latest_response_date"]) else None,
            has_blocking_rows=bool(row["has_blocking_rows"]),
            blocking_actor_count=int(row["blocking_actor_count"]),
            requires_new_cycle_flag=bool(row["requires_new_cycle_flag"]),
            completed_row_count=int(row["completed_row_count"]),
            source_row_count=int(row["source_row_count"]),
            version_sort_order=int(row["version_sort_order"]),
        )


@dataclass
class FamilySummary:
    """
    Typed view of one row from chain_register DataFrame.

    Mirrors the _CHAIN_REGISTER_COLS contract from family_grouper.py.
    Classification fields (current_state, portfolio_bucket, etc.) are
    NOT present here — they belong to Step 07 (chain_classifier).
    """
    family_key: str
    numero: str
    total_versions: int
    total_rows_ops: int
    first_submission_date: Optional[pd.Timestamp]
    latest_submission_date: Optional[pd.Timestamp]
    latest_indice: str
    latest_version_key: str
    total_blocking_versions: int
    total_versions_requiring_cycle: int
    total_completed_rows: int
    current_blocking_actor_count: int
    waiting_primary_flag: bool
    waiting_secondary_flag: bool
    has_debug_trace: bool
    has_effective_rows: bool

    @classmethod
    def from_row(cls, row: pd.Series) -> "FamilySummary":
        return cls(
            family_key=str(row["family_key"]),
            numero=str(row["numero"]),
            total_versions=int(row["total_versions"]),
            total_rows_ops=int(row["total_rows_ops"]),
            first_submission_date=row["first_submission_date"] if pd.notna(row["first_submission_date"]) else None,
            latest_submission_date=row["latest_submission_date"] if pd.notna(row["latest_submission_date"]) else None,
            latest_indice=str(row["latest_indice"]),
            latest_version_key=str(row["latest_version_key"]),
            total_blocking_versions=int(row["total_blocking_versions"]),
            total_versions_requiring_cycle=int(row["total_versions_requiring_cycle"]),
            total_completed_rows=int(row["total_completed_rows"]),
            current_blocking_actor_count=int(row["current_blocking_actor_count"]),
            waiting_primary_flag=bool(row["waiting_primary_flag"]),
            waiting_secondary_flag=bool(row["waiting_secondary_flag"]),
            has_debug_trace=bool(row["has_debug_trace"]),
            has_effective_rows=bool(row["has_effective_rows"]),
        )
