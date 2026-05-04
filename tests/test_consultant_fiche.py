"""
tests/test_consultant_fiche.py

Phase 6X.C — `_resolve_data_date` coverage.

Verifies the fallback chain after removal of the silent `date.today()` branch:
  1. ctx.data_date is used when present.
  2. ctx.run_date is used only when ctx.data_date is missing.
  3. Both missing/unparseable → ValueError.
  4. No `date.today()` fallback remains in `_resolve_data_date`.
"""

import sys
import inspect
from pathlib import Path
from datetime import date

import pytest

# ── importability ──────────────────────────────────────────────────────────
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from reporting.consultant_fiche import _resolve_data_date
from reporting.data_loader import RunContext


def _make_ctx(*, data_date=None, run_date: str = "") -> RunContext:
    """Minimal RunContext for `_resolve_data_date` coverage."""
    return RunContext(
        run_number=1,
        run_status="SUCCESS",
        run_date=run_date,
        summary_json={},
        gf_artifact_path=None,
        ged_available=True,
        degraded_mode=False,
        data_date=data_date,
    )


class TestResolveDataDate:
    def test_uses_data_date_when_present(self):
        ctx = _make_ctx(data_date=date(2026, 4, 10), run_date="2026-05-04")
        assert _resolve_data_date(ctx) == date(2026, 4, 10)
        assert ctx.warnings == []

    def test_falls_back_to_run_date_when_data_date_missing(self):
        ctx = _make_ctx(data_date=None, run_date="2026-05-04")
        assert _resolve_data_date(ctx) == date(2026, 5, 4)
        assert any("data_date missing" in w for w in ctx.warnings)

    def test_raises_when_both_missing(self):
        ctx = _make_ctx(data_date=None, run_date="")
        with pytest.raises(ValueError, match="data_date is required"):
            _resolve_data_date(ctx)

    def test_raises_when_run_date_unparseable(self):
        ctx = _make_ctx(data_date=None, run_date="not-a-date")
        with pytest.raises(ValueError, match="data_date is required"):
            _resolve_data_date(ctx)

    def test_no_date_today_fallback_in_source(self):
        """Static guard: source of `_resolve_data_date` must not contain `date.today` or `datetime.now`."""
        src = inspect.getsource(_resolve_data_date)
        assert "date.today" not in src, "silent date.today() fallback must not be reintroduced"
        assert "datetime.now" not in src, "silent datetime.now() fallback must not be reintroduced"
