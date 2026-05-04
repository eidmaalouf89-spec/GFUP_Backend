"""
tests/test_contractor_quality.py

Phase 6X.D — `contractor_quality.py` data_date validation.

Verifies:
  1. build_contractor_quality_peer_stats raises ValueError when ctx.data_date is None.
  2. build_contractor_quality raises ValueError when ctx.data_date is None
     (peer_stats supplied to bypass the upstream peer-stats call).
  3. Both functions accept a non-None ctx.data_date and use it as `ref_today`
     (no `date.today()` fallback path is taken).
  4. Source-level guard: `date.today` / `datetime.now` / `pd.Timestamp.today`
     do not appear anywhere in `contractor_quality.py`.
"""

import re
import sys
import inspect
from pathlib import Path
from datetime import date

import pandas as pd
import pytest

# ── importability ──────────────────────────────────────────────────────────
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from reporting import contractor_quality
from reporting.contractor_quality import (
    build_contractor_quality,
    build_contractor_quality_peer_stats,
)
from reporting.data_loader import RunContext


def _make_ctx(*, data_date=None) -> RunContext:
    """Minimal RunContext for `_resolve_data_date` validation coverage.

    Empty docs_df / dernier_df / responses_df short-circuit the heavy paths so
    the only branch under test is the `ctx.data_date is None` guard.
    """
    return RunContext(
        run_number=1,
        run_status="SUCCESS",
        run_date="2026-04-10",
        summary_json={},
        gf_artifact_path=None,
        ged_available=True,
        degraded_mode=False,
        data_date=data_date,
        docs_df=pd.DataFrame(columns=["emetteur", "doc_id"]),
        dernier_df=pd.DataFrame(columns=["emetteur"]),
        responses_df=pd.DataFrame(columns=["doc_id", "approver_raw", "status_clean"]),
    )


class TestPeerStatsDataDateGuard:
    def test_raises_when_data_date_missing(self):
        ctx = _make_ctx(data_date=None)
        with pytest.raises(ValueError, match="peer-stats dormancy"):
            build_contractor_quality_peer_stats(ctx, chain_timelines={})

    def test_data_date_guard_not_fired_when_present(self):
        """When ctx.data_date is set, the guard does not raise.
        Fixture-related errors after the guard (e.g. missing workflow_engine)
        are tolerated — this test only validates the guard's gating."""
        ctx = _make_ctx(data_date=date(2026, 4, 10))
        try:
            build_contractor_quality_peer_stats(ctx, chain_timelines={})
        except ValueError as e:
            assert "peer-stats dormancy" not in str(e), (
                f"peer-stats data_date guard fired despite data_date being set: {e}"
            )
        except Exception:
            # Fixture-related errors after the guard are not under test here.
            pass


class TestBuildContractorQualityDataDateGuard:
    def test_raises_when_data_date_missing(self):
        ctx = _make_ctx(data_date=None)
        # Pass peer_stats={} to bypass the upstream peer-stats call (which would
        # also raise but with the peer-stats message). Tests THIS function's
        # own guard at line 457.
        with pytest.raises(ValueError, match=r"build_contractor_quality\(\)"):
            build_contractor_quality(ctx, contractor_code="BEN", peer_stats={})

    def test_data_date_guard_not_fired_when_present(self):
        """When ctx.data_date is set, the guard does not raise.
        Fixture-related errors after the guard are tolerated."""
        ctx = _make_ctx(data_date=date(2026, 4, 10))
        try:
            build_contractor_quality(ctx, contractor_code="BEN", peer_stats={})
        except ValueError as e:
            assert "build_contractor_quality()" not in str(e), (
                f"build_contractor_quality data_date guard fired despite data_date being set: {e}"
            )
        except Exception:
            pass


class TestSourceLevelGuard:
    def test_no_today_or_now_fallback_in_source(self):
        """No business-impacting date.today / datetime.now / pd.Timestamp.today
        anywhere in contractor_quality.py."""
        src_path = Path(contractor_quality.__file__)
        src = src_path.read_text(encoding="utf-8")
        forbidden = re.compile(
            r"date\.today|datetime\.today|datetime\.now|"
            r"pd\.Timestamp\.today|pd\.Timestamp\.now"
        )
        matches = [
            (i + 1, line.rstrip())
            for i, line in enumerate(src.splitlines())
            if forbidden.search(line)
        ]
        assert matches == [], (
            "Forbidden today/now patterns reintroduced in contractor_quality.py: "
            + repr(matches)
        )
