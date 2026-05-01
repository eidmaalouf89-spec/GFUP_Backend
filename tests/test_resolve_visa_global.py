"""
Pure-function unit tests for aggregator.resolve_visa_global.

Uses a SimpleNamespace ctx with a mocked WorkflowEngine — no real RunContext
or pipeline data required.  All paths test the (visa, vdate) tuple shape.

Step-3 addendum (2026-04-30): resolve_visa_global now fetches vdate from
WorkflowEngine even when flat_doc_meta supplies the visa, so avg_days_to_visa
is not silently broken. Two tests that previously asserted vdate is None for
flat hits were updated to assert vdate == "WE_DATE" (engine value).
"""
import sys
import os
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from reporting.aggregator import resolve_visa_global


# ── Helpers ───────────────────────────────────────────────────────────────────

class _MockEngine:
    """Minimal WorkflowEngine stand-in that always returns a known value."""
    def compute_visa_global_with_date(self, doc_id):
        return "WE_VISA", "WE_DATE"


def _ctx(flat_ged_doc_meta=None, attach_attr=True):
    """Build a minimal ctx SimpleNamespace."""
    ctx = types.SimpleNamespace()
    ctx.workflow_engine = _MockEngine()
    if attach_attr:
        ctx.flat_ged_doc_meta = flat_ged_doc_meta if flat_ged_doc_meta is not None else {}
    return ctx


# ── Test 1: returns meta visa when entry has non-empty visa_global ─────────────

def test_returns_meta_visa_when_present():
    ctx = _ctx({"doc1": {"visa_global": "VSO", "responsible_party": "MOEX"}})
    visa, vdate = resolve_visa_global(ctx, "doc1")
    assert visa == "VSO"


def test_meta_hit_uses_engine_vdate():
    """Step-3 addendum: when meta supplies visa, vdate comes from WorkflowEngine
    (not None). Preserves avg_days_to_visa at compute_project_kpis:84."""
    ctx = _ctx({"doc1": {"visa_global": "REF"}})
    _, vdate = resolve_visa_global(ctx, "doc1")
    assert vdate == "WE_DATE"   # engine mock returns "WE_DATE"


# ── Test 2: falls through to WorkflowEngine when doc_id not in meta ───────────

def test_fallthrough_when_doc_not_in_meta():
    ctx = _ctx({})  # empty meta
    visa, vdate = resolve_visa_global(ctx, "unknown_doc")
    assert visa == "WE_VISA"
    assert vdate == "WE_DATE"


# ── Test 3: falls through when meta entry exists but visa_global is falsy ─────

def test_fallthrough_when_visa_is_none():
    ctx = _ctx({"doc1": {"visa_global": None}})
    visa, vdate = resolve_visa_global(ctx, "doc1")
    assert visa == "WE_VISA"
    assert vdate == "WE_DATE"


def test_fallthrough_when_visa_is_empty_string():
    ctx = _ctx({"doc1": {"visa_global": ""}})
    visa, vdate = resolve_visa_global(ctx, "doc1")
    assert visa == "WE_VISA"
    assert vdate == "WE_DATE"


def test_fallthrough_when_visa_key_missing_from_entry():
    """Entry exists but has no visa_global key at all (e.g. only closure_mode)."""
    ctx = _ctx({"doc1": {"closure_mode": "WAITING_RESPONSES", "responsible_party": "MOEX"}})
    visa, vdate = resolve_visa_global(ctx, "doc1")
    assert visa == "WE_VISA"
    assert vdate == "WE_DATE"


# ── Test 4: falls through gracefully when ctx has no flat_ged_doc_meta attr ───

def test_fallthrough_when_no_flat_ged_doc_meta_attribute():
    """Legacy raw-mode RunContext: attribute absent → falls through safely."""
    ctx = _ctx(attach_attr=False)
    visa, vdate = resolve_visa_global(ctx, "any_doc")
    assert visa == "WE_VISA"
    assert vdate == "WE_DATE"


def test_fallthrough_when_flat_ged_doc_meta_is_none():
    """Attribute present but explicitly None (defensive guard)."""
    ctx = types.SimpleNamespace(workflow_engine=_MockEngine(), flat_ged_doc_meta=None)
    visa, vdate = resolve_visa_global(ctx, "any_doc")
    assert visa == "WE_VISA"
    assert vdate == "WE_DATE"


# ── Test 5: (visa, vdate) tuple shape in every path ───────────────────────────

@pytest.mark.parametrize("doc_meta, doc_id, expect_from_flat", [
    ({"d1": {"visa_global": "VSO"}},  "d1",     True),   # flat hit
    ({"d1": {"visa_global": "VSO"}},  "d2",     False),  # miss → WE
    ({"d1": {"visa_global": None}},   "d1",     False),  # falsy → WE
    ({},                               "d1",     False),  # empty meta → WE
])
def test_always_returns_two_tuple(doc_meta, doc_id, expect_from_flat):
    ctx = _ctx(doc_meta)
    result = resolve_visa_global(ctx, doc_id)
    assert isinstance(result, tuple), "return value must be a tuple"
    assert len(result) == 2, "tuple must have exactly 2 elements (visa, vdate)"
    # step-3 addendum: vdate always comes from the engine regardless of path
    assert result[1] == "WE_DATE"


# ── Step-3 addendum: engine vdate used for flat meta hits ─────────────────────

def test_meta_visa_uses_engine_vdate():
    """When meta supplies visa_global, vdate must come from the engine so that
    avg_days_to_visa in compute_project_kpis is not broken (§21.8)."""
    from datetime import date as _date

    class _EngineWithDate:
        def compute_visa_global_with_date(self, doc_id):
            return "VAO", _date(2026, 1, 15)

    ctx = types.SimpleNamespace(
        workflow_engine=_EngineWithDate(),
        flat_ged_doc_meta={"doc42": {"visa_global": "VSO"}},
    )
    visa, vdate = resolve_visa_global(ctx, "doc42")
    assert visa == "VSO"                   # meta visa preserved
    assert vdate == _date(2026, 1, 15)     # engine date used
