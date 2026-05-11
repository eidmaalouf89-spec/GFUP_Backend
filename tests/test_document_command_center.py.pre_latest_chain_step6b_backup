"""
tests/test_document_command_center.py

Phase 6X.E — `compute_dcc_tags_bulk` deadline-truth columns.

Verifies the new columns:
  - min_open_consultant_deadline: earliest `deadline` among open consultant
    (non-MOEX) responses for the doc; None if no such response.
  - consultant_days_remaining: (min_open_consultant_deadline - ctx.data_date).days;
    None if min_open_consultant_deadline is None.

Reuses the same is_open / deadline truth as `_get_latest_responses_for_doc`.
"""

import sys
from pathlib import Path
from datetime import date

import pandas as pd
import pytest

# ── importability ──────────────────────────────────────────────────────────
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from reporting.document_command_center import compute_dcc_tags_bulk, MOEX_CANONICAL, _compute_primary_tag
from reporting.data_loader import RunContext


def _make_ctx(*, data_date, dernier_rows, response_rows) -> RunContext:
    """Minimal RunContext with the dataframe shape compute_dcc_tags_bulk reads."""
    dernier = pd.DataFrame(dernier_rows)
    responses = pd.DataFrame(response_rows)
    return RunContext(
        run_number=1,
        run_status="SUCCESS",
        run_date="2026-04-10",
        summary_json={},
        gf_artifact_path=None,
        ged_available=True,
        degraded_mode=False,
        data_date=data_date,
        docs_df=dernier,
        responses_df=responses,
        dernier_df=dernier,
    )


def _doc_row(doc_id="D1", numero="100001", indice="A", emetteur="BEN"):
    """Minimal dernier_df row matching the columns compute_dcc_tags_bulk reads."""
    return {
        "doc_id": doc_id,
        "numero": numero,
        "indice": indice,
        "emetteur": emetteur,
        "libelle_du_document": "Test doc",
        "lot": "LOT01",
        "_focus_owner_tier": "PRIMARY",
        "_visa_global": "REF",
    }


def _resp_row(*, doc_id="D1", reviewer="BET Structure", date_status_type="PENDING_IN_DELAY",
              date_limite=None, date_answered=None, status_clean="", approver_raw=""):
    """Minimal responses_df row — mirrors the keys _get_latest_responses_for_doc reads."""
    return {
        "doc_id": doc_id,
        "approver_canonical": reviewer,
        "approver_raw": approver_raw,
        "date_status_type": date_status_type,
        "date_limite": date_limite,
        "date_answered": date_answered,
        "status_clean": status_clean,
        "response_comment": "",
    }


class TestMinOpenConsultantDeadline:
    def test_two_open_consultant_deadlines_returns_earliest(self):
        ctx = _make_ctx(
            data_date=date(2026, 4, 10),
            dernier_rows=[_doc_row()],
            response_rows=[
                _resp_row(reviewer="BET Structure", date_limite=date(2026, 4, 17)),
                _resp_row(reviewer="BET CVC",       date_limite=date(2026, 4, 25)),
            ],
        )
        df = compute_dcc_tags_bulk(ctx)
        assert len(df) == 1
        assert df.iloc[0]["min_open_consultant_deadline"] == date(2026, 4, 17)

    def test_consultant_days_remaining_uses_data_date(self):
        # Reproduces 133005 indice C: data_date 2026-04-10, deadline 2026-04-17 → 7 days.
        ctx = _make_ctx(
            data_date=date(2026, 4, 10),
            dernier_rows=[_doc_row(doc_id="D-133005-C", numero="133005", indice="C")],
            response_rows=[
                _resp_row(doc_id="D-133005-C", reviewer="BET Structure",
                          date_limite=date(2026, 4, 17)),
            ],
        )
        df = compute_dcc_tags_bulk(ctx)
        assert df.iloc[0]["min_open_consultant_deadline"] == date(2026, 4, 17)
        assert df.iloc[0]["consultant_days_remaining"] == 7

    def test_closed_consultant_response_is_ignored(self):
        # Answered response (response_date present) is NOT open; only the open one counts.
        ctx = _make_ctx(
            data_date=date(2026, 4, 10),
            dernier_rows=[_doc_row()],
            response_rows=[
                # Closed: has date_answered, status_type ANSWERED.
                _resp_row(reviewer="BET Structure", date_status_type="ANSWERED_ON_TIME",
                          date_limite=date(2026, 4, 12),
                          date_answered=date(2026, 4, 8), status_clean="VSO"),
                # Open: still pending.
                _resp_row(reviewer="BET CVC", date_status_type="PENDING_IN_DELAY",
                          date_limite=date(2026, 4, 25)),
            ],
        )
        df = compute_dcc_tags_bulk(ctx)
        # Closed deadline 2026-04-12 must be ignored; open deadline 2026-04-25 wins.
        assert df.iloc[0]["min_open_consultant_deadline"] == date(2026, 4, 25)
        assert df.iloc[0]["consultant_days_remaining"] == 15  # 25-Apr − 10-Apr

    def test_no_open_deadline_returns_none(self):
        ctx = _make_ctx(
            data_date=date(2026, 4, 10),
            dernier_rows=[_doc_row()],
            response_rows=[
                # Open but no deadline.
                _resp_row(reviewer="BET Structure", date_status_type="PENDING_IN_DELAY",
                          date_limite=None),
            ],
        )
        df = compute_dcc_tags_bulk(ctx)
        assert df.iloc[0]["min_open_consultant_deadline"] is None
        assert df.iloc[0]["consultant_days_remaining"] is None

    def test_moex_open_deadline_excluded_from_consultant_min(self):
        # MOEX_CANONICAL response, even if open with a deadline, must NOT be
        # counted toward min_open_CONSULTANT_deadline.
        ctx = _make_ctx(
            data_date=date(2026, 4, 10),
            dernier_rows=[_doc_row()],
            response_rows=[
                _resp_row(reviewer=MOEX_CANONICAL, date_status_type="PENDING_IN_DELAY",
                          date_limite=date(2026, 4, 12)),
                _resp_row(reviewer="BET Structure", date_status_type="PENDING_IN_DELAY",
                          date_limite=date(2026, 4, 17)),
            ],
        )
        df = compute_dcc_tags_bulk(ctx)
        # MOEX 2026-04-12 must be excluded → consultant min = 2026-04-17.
        assert df.iloc[0]["min_open_consultant_deadline"] == date(2026, 4, 17)
        assert df.iloc[0]["consultant_days_remaining"] == 7

    def test_primary_and_secondary_deadlines_are_split(self):
        ctx = _make_ctx(
            data_date=date(2026, 4, 10),
            dernier_rows=[_doc_row()],
            response_rows=[
                _resp_row(reviewer="BET Structure", date_limite=date(2026, 4, 17)),
                _resp_row(reviewer="BET Acoustique", date_limite=date(2026, 4, 13)),
            ],
        )
        row = compute_dcc_tags_bulk(ctx).iloc[0]
        assert row["min_open_consultant_deadline"] == date(2026, 4, 13)
        assert row["consultant_days_remaining"] == 3
        assert row["primary_open_consultant_deadline"] == date(2026, 4, 17)
        assert row["primary_consultant_days_remaining"] == 7
        assert row["secondary_open_consultant_deadline"] == date(2026, 4, 13)
        assert row["secondary_consultant_days_remaining"] == 3

    def test_split_days_remaining_use_data_date_and_can_be_late(self):
        ctx = _make_ctx(
            data_date=date(2026, 4, 10),
            dernier_rows=[_doc_row()],
            response_rows=[
                _resp_row(reviewer="BET Structure", date_limite=date(2026, 4, 9)),
                _resp_row(reviewer="BET Acoustique", date_limite=date(2026, 4, 8)),
            ],
        )
        row = compute_dcc_tags_bulk(ctx).iloc[0]
        assert row["primary_consultant_days_remaining"] == -1
        assert row["secondary_consultant_days_remaining"] == -2

    def test_answered_and_moex_responses_do_not_affect_split_deadlines(self):
        ctx = _make_ctx(
            data_date=date(2026, 4, 10),
            dernier_rows=[_doc_row()],
            response_rows=[
                _resp_row(reviewer=MOEX_CANONICAL, date_limite=date(2026, 4, 5)),
                _resp_row(reviewer="BET Structure", date_status_type="ANSWERED_ON_TIME",
                          date_limite=date(2026, 4, 6), date_answered=date(2026, 4, 6),
                          status_clean="VSO"),
                _resp_row(reviewer="BET Acoustique", date_limite=date(2026, 4, 18)),
            ],
        )
        row = compute_dcc_tags_bulk(ctx).iloc[0]
        assert row["primary_open_consultant_deadline"] is None
        assert row["primary_consultant_days_remaining"] is None
        assert row["secondary_open_consultant_deadline"] == date(2026, 4, 18)
        assert row["secondary_consultant_days_remaining"] == 8


def test_document_command_center_has_no_today_or_now_business_fallbacks():
    source = (Path(__file__).resolve().parent.parent / "src" / "reporting" / "document_command_center.py").read_text(
        encoding="utf-8"
    )
    forbidden = [
        "date.today",
        "datetime.today",
        "datetime.now",
        "pd.Timestamp.today",
        "pd.Timestamp.now",
    ]
    assert not any(pattern in source for pattern in forbidden)


class TestMoexTechnicalArbitration:
    def test_sas_status_is_not_technical_arbitrage(self):
        responses = [
            {"reviewer": "0-SAS", "tier": "UNKNOWN", "status": "VSO-SAS"},
            {"reviewer": "BET Electricité", "tier": "PRIMARY", "status": "REF"},
            {"reviewer": MOEX_CANONICAL, "tier": "MOEX", "status": ""},
        ]
        assert _compute_primary_tag("MOEX", responses, None) == "Att MOEX — Facile"

    def test_two_real_technical_consultants_disagree_is_arbitrage(self):
        responses = [
            {"reviewer": "BET Electricité", "tier": "PRIMARY", "status": "REF"},
            {"reviewer": "BET Structure", "tier": "PRIMARY", "status": "VAO"},
            {"reviewer": MOEX_CANONICAL, "tier": "MOEX", "status": ""},
        ]
        assert _compute_primary_tag("MOEX", responses, None) == "Att MOEX — Arbitrage"

    def test_sas_only_approval_is_moex_facile(self):
        responses = [
            {"reviewer": "0-SAS", "tier": "UNKNOWN", "status": "VSO-SAS"},
            {"reviewer": "BET Structure", "tier": "PRIMARY", "status": "VAO"},
            {"reviewer": MOEX_CANONICAL, "tier": "MOEX", "status": ""},
        ]
        assert _compute_primary_tag("MOEX", responses, None) == "Att MOEX — Facile"
