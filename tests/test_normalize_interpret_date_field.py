"""
tests/test_normalize_interpret_date_field.py

Unit tests for normalize.interpret_date_field().

Regression coverage for the int/float nanosecond timestamp branch added in the
2026-05-04 date-hotfix: openpyxl returns Excel date cells as raw Python ints
(nanosecond epoch) when the column has object dtype.  The previous code fell
through to NOT_CALLED for these values, causing answered=0 across all dashboards.
"""
from __future__ import annotations

import datetime
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from normalize import interpret_date_field


# ── helpers ──────────────────────────────────────────────────────────────────

def _date(result: dict):
    """Extract the date value, normalised to datetime.date for comparison."""
    d = result["date"]
    if d is None:
        return None
    if isinstance(d, datetime.datetime):
        return d.date()
    return d


# ── NOT_CALLED cases ──────────────────────────────────────────────────────────

def test_none_is_not_called():
    r = interpret_date_field(None)
    assert r["date_status_type"] == "NOT_CALLED"
    assert r["date"] is None


def test_empty_string_is_not_called():
    r = interpret_date_field("")
    assert r["date_status_type"] == "NOT_CALLED"
    assert r["date"] is None


def test_whitespace_string_is_not_called():
    r = interpret_date_field("   ")
    assert r["date_status_type"] == "NOT_CALLED"
    assert r["date"] is None


def test_float_nan_is_not_called():
    r = interpret_date_field(float("nan"))
    assert r["date_status_type"] == "NOT_CALLED"
    assert r["date"] is None


# ── ANSWERED — existing datetime/date branch ──────────────────────────────────

def test_datetime_object_is_answered():
    dt = datetime.datetime(2025, 5, 7, 10, 0, 0)
    r = interpret_date_field(dt)
    assert r["date_status_type"] == "ANSWERED"
    assert _date(r) == datetime.date(2025, 5, 7)


def test_date_object_is_answered():
    d = datetime.date(2025, 5, 7)
    r = interpret_date_field(d)
    assert r["date_status_type"] == "ANSWERED"
    assert _date(r) == datetime.date(2025, 5, 7)


# ── ANSWERED — new int/float nanosecond timestamp branch ─────────────────────

def test_int_ns_timestamp_2025_05_07():
    """1746576000000000000 ns == 2025-05-07 (confirmed from live cache sample)."""
    r = interpret_date_field(1746576000000000000)
    assert r["date_status_type"] == "ANSWERED"
    assert _date(r) == datetime.date(2025, 5, 7)
    assert r["date_limite"] is None


def test_int_ns_timestamp_2025_06_02():
    """1748822400000000000 ns == 2025-06-02 (second live cache sample)."""
    r = interpret_date_field(1748822400000000000)
    assert r["date_status_type"] == "ANSWERED"
    assert _date(r) == datetime.date(2025, 6, 2)


def test_float_ns_timestamp_is_answered():
    """openpyxl can produce float for a date cell; should still parse."""
    r = interpret_date_field(float(1746576000000000000))
    assert r["date_status_type"] == "ANSWERED"
    assert _date(r) == datetime.date(2025, 5, 7)


# ── PENDING cases — must not be affected by the new branch ───────────────────

def test_en_attente_is_pending_in_delay():
    r = interpret_date_field("En attente visa (2025/06/04)")
    assert r["date_status_type"] == "PENDING_IN_DELAY"
    assert r["date"] is None


def test_rappel_en_attente_is_pending_late():
    r = interpret_date_field("Rappel : En attente visa (2025/06/04)")
    assert r["date_status_type"] == "PENDING_LATE"
    assert r["date"] is None


def test_unknown_string_is_pending_in_delay():
    r = interpret_date_field("some unrecognised text")
    assert r["date_status_type"] == "PENDING_IN_DELAY"
    assert r["date"] is None
