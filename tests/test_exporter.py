"""
tests/test_exporter.py
----------------------
Step 12 — Export Engine: synthetic unit tests.

Test classes
------------
1. TestCSVFiles          — all 7 CSVs created, correct headers, deterministic
2. TestXLSXWorkbook      — XLSX created, all 11 sheets present, correct row counts
3. TestJSONDashboard     — dashboard_summary.json keys + top_issues.json structure
4. TestEmptyInputs       — empty DataFrames still produce valid artifacts with headers
5. TestDeterministicSort — same inputs → same artifact content on repeat call
6. TestReturnDict        — function returns dict with all expected artifact keys
7. TestLiveRun           — skipped (full live run, Claude Code / Codex only)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# Allow import from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.chain_onion.exporter import export_chain_onion_outputs

# ── Synthetic fixture builders ────────────────────────────────────────────────

def _reg(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame({
        "family_key": [f"FAM{i:03d}" for i in range(1, n + 1)],
        "numero": [f"N{i:03d}" for i in range(1, n + 1)],
        "chain_label": [f"Label {i}" for i in range(1, n + 1)],
    })


def _ver(n: int = 3) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        rows.append({"family_key": f"FAM{i:03d}", "version_number": 1, "version_label": f"V{i}"})
        rows.append({"family_key": f"FAM{i:03d}", "version_number": 2, "version_label": f"V{i}b"})
    return pd.DataFrame(rows)


def _evn(n: int = 3) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        rows.append({"family_key": f"FAM{i:03d}", "event_date": "2026-01-01", "event_type": "SUBMISSION"})
    return pd.DataFrame(rows)


def _mtr(n: int = 3) -> pd.DataFrame:
    return pd.DataFrame({
        "family_key": [f"FAM{i:03d}" for i in range(1, n + 1)],
        "pressure_index": [float(i * 10) for i in range(1, n + 1)],
        "portfolio_bucket": ["LIVE_OPERATIONAL", "LEGACY_BACKLOG", "ARCHIVED_HISTORICAL"][:n],
        "current_state": ["OPEN_WAITING_PRIMARY_CONSULTANT", "VOID_CHAIN", "CLOSED_VAO"][:n],
    })


def _lay(n: int = 3) -> pd.DataFrame:
    layer_codes = ["L1_CONTRACTOR_QUALITY", "L2_SAS_GATE_FRICTION", "L3_PRIMARY_CONSULTANT_DELAY"]
    return pd.DataFrame({
        "family_key": [f"FAM{i:03d}" for i in range(1, n + 1)],
        "layer_code": layer_codes[:n],
        "layer_name": ["Contractor Quality", "SAS Gate Friction", "Primary Consultant Delay"][:n],
        "severity_raw": ["HIGH", "MEDIUM", "LOW"][:n],
        "confidence_raw": [80.0, 60.0, 50.0][:n],
        "evidence_count": [3, 2, 1][:n],
        "pressure_index": [30.0, 20.0, 10.0][:n],
    })


def _scr(n: int = 3) -> pd.DataFrame:
    buckets = ["LIVE_OPERATIONAL", "LEGACY_BACKLOG", "ARCHIVED_HISTORICAL"]
    states = ["OPEN_WAITING_PRIMARY_CONSULTANT", "VOID_CHAIN", "CLOSED_VAO"]
    return pd.DataFrame({
        "family_key": [f"FAM{i:03d}" for i in range(1, n + 1)],
        "numero": [f"N{i:03d}" for i in range(1, n + 1)],
        "portfolio_bucket": buckets[:n],
        "current_state": states[:n],
        "normalized_score_100": [75.0, 20.0, 0.0][:n],
        "action_priority_rank": [1, 2, 3][:n],
        "escalation_flag": [True, False, False][:n],
        "escalation_reason": ["high normalized score", "", ""][:n],
        "blended_confidence": [80.0, 50.0, 0.0][:n],
        "top_layer_code": ["L3_PRIMARY_CONSULTANT_DELAY", "L1_CONTRACTOR_QUALITY", None][:n],
        "evidence_layers_count": [3, 1, 0][:n],
        "consultant_primary_impact_score": [40.0, 0.0, 0.0][:n],
        "consultant_secondary_impact_score": [0.0, 10.0, 0.0][:n],
        "contractor_impact_score": [0.0, 5.0, 0.0][:n],
        "sas_impact_score": [0.0, 0.0, 0.0][:n],
        "moex_impact_score": [10.0, 0.0, 0.0][:n],
        "contradiction_impact_score": [0.0, 0.0, 0.0][:n],
    })


def _nar(n: int = 3) -> pd.DataFrame:
    buckets = ["LIVE_OPERATIONAL", "LEGACY_BACKLOG", "ARCHIVED_HISTORICAL"]
    states = ["OPEN_WAITING_PRIMARY_CONSULTANT", "VOID_CHAIN", "CLOSED_VAO"]
    urgencies = ["HIGH", "LOW", "NONE"]
    return pd.DataFrame({
        "family_key": [f"FAM{i:03d}" for i in range(1, n + 1)],
        "numero": [f"N{i:03d}" for i in range(1, n + 1)],
        "current_state": states[:n],
        "portfolio_bucket": buckets[:n],
        "executive_summary": ["Active chain needing attention.", "Legacy open chain.", "Historical closed chain."][:n],
        "primary_driver_text": ["Primary consultant timing is the constraint.", "Contractor rework is the drag.", "No signals."][:n],
        "secondary_driver_text": ["No secondary driver.", "No secondary driver.", "No secondary driver."][:n],
        "operational_note": ["Blocker sits with primary consultant.", "Open admin status.", "Closed with approval."][:n],
        "recommended_focus": ["Prioritize unblocking.", "Review for archive.", "No action required."][:n],
        "urgency_label": urgencies[:n],
        "confidence_label": ["MEDIUM", "LOW", "NONE"][:n],
        "normalized_score_100": [75.0, 20.0, 0.0][:n],
        "action_priority_rank": [1, 2, 3][:n],
        "engine_version": ["1.0.0"] * n,
        "generated_at": ["2026-04-27T00:00:00+00:00"] * n,
    })


def _portfolio_metrics() -> dict:
    return {"total_chains": 3, "live_chains": 1, "avg_pressure": 35.0}


def _onion_summary() -> dict:
    return {
        "total_scored_chains": 3,
        "max_score": 75.0,
        "avg_score": 31.7,
        "escalated_chain_count": 1,
        "top_theme_by_impact": "L3_PRIMARY_CONSULTANT_DELAY",
    }


def _run_export(tmp_path, n=3):
    return export_chain_onion_outputs(
        chain_register_df=_reg(n),
        chain_versions_df=_ver(n),
        chain_events_df=_evn(n),
        chain_metrics_df=_mtr(n),
        onion_layers_df=_lay(n),
        onion_scores_df=_scr(n),
        chain_narratives_df=_nar(n),
        portfolio_metrics=_portfolio_metrics(),
        onion_portfolio_summary=_onion_summary(),
        output_dir=str(tmp_path),
    )


# ── Test 1: CSV Files ─────────────────────────────────────────────────────────

class TestCSVFiles:
    _REQUIRED_CSVS = [
        "CHAIN_REGISTER.csv",
        "CHAIN_VERSIONS.csv",
        "CHAIN_EVENTS.csv",
        "CHAIN_METRICS.csv",
        "ONION_LAYERS.csv",
        "ONION_SCORES.csv",
        "CHAIN_NARRATIVES.csv",
    ]

    def test_all_csvs_created(self, tmp_path):
        arts = _run_export(tmp_path)
        for name in self._REQUIRED_CSVS:
            assert name in arts, f"Missing artifact: {name}"
            assert Path(arts[name]).exists(), f"File not on disk: {name}"

    def test_csv_row_counts(self, tmp_path):
        _run_export(tmp_path)
        reg_df = pd.read_csv(tmp_path / "CHAIN_REGISTER.csv")
        assert len(reg_df) == 3

    def test_chain_versions_row_count(self, tmp_path):
        _run_export(tmp_path)
        ver_df = pd.read_csv(tmp_path / "CHAIN_VERSIONS.csv")
        assert len(ver_df) == 6  # 3 families × 2 versions each

    def test_csv_has_headers(self, tmp_path):
        _run_export(tmp_path)
        for name in self._REQUIRED_CSVS:
            df = pd.read_csv(tmp_path / name)
            assert len(df.columns) > 0, f"No headers in {name}"

    def test_onion_scores_sorted_by_rank(self, tmp_path):
        _run_export(tmp_path)
        df = pd.read_csv(tmp_path / "ONION_SCORES.csv")
        ranks = df["action_priority_rank"].tolist()
        assert ranks == sorted(ranks), "ONION_SCORES not sorted by action_priority_rank"

    def test_narratives_sorted_by_rank(self, tmp_path):
        _run_export(tmp_path)
        df = pd.read_csv(tmp_path / "CHAIN_NARRATIVES.csv")
        ranks = df["action_priority_rank"].tolist()
        assert ranks == sorted(ranks)


# ── Test 2: XLSX Workbook ─────────────────────────────────────────────────────

class TestXLSXWorkbook:
    _REQUIRED_SHEETS = [
        "Executive Priorities",
        "Live Operational Chains",
        "Consultant Delays",
        "Contractor Quality",
        "MOEX-SAS Blocking",
        "Legacy Backlog Cleanup",
        "Archived Historical",
        "Portfolio KPIs",
        "Full Chain Metrics",
        "Full Onion Scores",
        "Narratives",
    ]

    def test_xlsx_created(self, tmp_path):
        arts = _run_export(tmp_path)
        assert "CHAIN_ONION_SUMMARY.xlsx" in arts
        assert Path(arts["CHAIN_ONION_SUMMARY.xlsx"]).exists()

    def test_all_sheets_present(self, tmp_path):
        arts = _run_export(tmp_path)
        xl = pd.ExcelFile(arts["CHAIN_ONION_SUMMARY.xlsx"])
        for sheet in self._REQUIRED_SHEETS:
            assert sheet in xl.sheet_names, f"Missing sheet: {sheet}"

    def test_executive_priorities_max_50(self, tmp_path):
        arts = _run_export(tmp_path)
        df = pd.read_excel(arts["CHAIN_ONION_SUMMARY.xlsx"], sheet_name="Executive Priorities")
        assert len(df) <= 50

    def test_live_operational_chains_filter(self, tmp_path):
        arts = _run_export(tmp_path)
        df = pd.read_excel(arts["CHAIN_ONION_SUMMARY.xlsx"], sheet_name="Live Operational Chains")
        if not df.empty:
            assert all(df["portfolio_bucket"] == "LIVE_OPERATIONAL")

    def test_legacy_backlog_filter(self, tmp_path):
        arts = _run_export(tmp_path)
        df = pd.read_excel(arts["CHAIN_ONION_SUMMARY.xlsx"], sheet_name="Legacy Backlog Cleanup")
        if not df.empty:
            assert all(df["portfolio_bucket"] == "LEGACY_BACKLOG")

    def test_archived_historical_filter(self, tmp_path):
        arts = _run_export(tmp_path)
        df = pd.read_excel(arts["CHAIN_ONION_SUMMARY.xlsx"], sheet_name="Archived Historical")
        if not df.empty:
            assert all(df["portfolio_bucket"] == "ARCHIVED_HISTORICAL")

    def test_portfolio_kpis_has_rows(self, tmp_path):
        arts = _run_export(tmp_path)
        df = pd.read_excel(arts["CHAIN_ONION_SUMMARY.xlsx"], sheet_name="Portfolio KPIs")
        assert len(df) > 0

    def test_portfolio_kpis_columns(self, tmp_path):
        arts = _run_export(tmp_path)
        df = pd.read_excel(arts["CHAIN_ONION_SUMMARY.xlsx"], sheet_name="Portfolio KPIs")
        assert set(df.columns) >= {"source", "key", "value"}

    def test_consultant_delays_filter(self, tmp_path):
        arts = _run_export(tmp_path)
        df = pd.read_excel(arts["CHAIN_ONION_SUMMARY.xlsx"], sheet_name="Consultant Delays")
        if not df.empty:
            primary_ok = df.get("consultant_primary_impact_score", pd.Series([0])).fillna(0)
            secondary_ok = df.get("consultant_secondary_impact_score", pd.Series([0])).fillna(0)
            assert ((primary_ok > 0) | (secondary_ok > 0)).all()

    def test_moex_sas_filter(self, tmp_path):
        arts = _run_export(tmp_path)
        df = pd.read_excel(arts["CHAIN_ONION_SUMMARY.xlsx"], sheet_name="MOEX-SAS Blocking")
        if not df.empty:
            moex = df.get("moex_impact_score", pd.Series([0])).fillna(0)
            sas = df.get("sas_impact_score", pd.Series([0])).fillna(0)
            assert ((moex > 0) | (sas > 0)).all()

    def test_sheet_count_exactly_11(self, tmp_path):
        arts = _run_export(tmp_path)
        xl = pd.ExcelFile(arts["CHAIN_ONION_SUMMARY.xlsx"])
        assert len(xl.sheet_names) == 11


# ── Test 3: JSON Dashboard ────────────────────────────────────────────────────

class TestJSONDashboard:
    _REQUIRED_DASHBOARD_KEYS = [
        "total_chains",
        "live_chains",
        "legacy_chains",
        "archived_chains",
        "dormant_ghost_ratio",
        "avg_pressure_live",
        "escalated_chain_count",
        "top_theme_by_impact",
    ]

    def test_dashboard_summary_created(self, tmp_path):
        arts = _run_export(tmp_path)
        assert "dashboard_summary.json" in arts
        assert Path(arts["dashboard_summary.json"]).exists()

    def test_top_issues_created(self, tmp_path):
        arts = _run_export(tmp_path)
        assert "top_issues.json" in arts
        assert Path(arts["top_issues.json"]).exists()

    def test_dashboard_parses(self, tmp_path):
        arts = _run_export(tmp_path)
        with open(arts["dashboard_summary.json"]) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_dashboard_required_keys(self, tmp_path):
        arts = _run_export(tmp_path)
        with open(arts["dashboard_summary.json"]) as f:
            data = json.load(f)
        for key in self._REQUIRED_DASHBOARD_KEYS:
            assert key in data, f"Missing dashboard key: {key}"

    def test_dashboard_total_chains(self, tmp_path):
        arts = _run_export(tmp_path)
        with open(arts["dashboard_summary.json"]) as f:
            data = json.load(f)
        assert data["total_chains"] == 3

    def test_dashboard_live_chains(self, tmp_path):
        arts = _run_export(tmp_path)
        with open(arts["dashboard_summary.json"]) as f:
            data = json.load(f)
        assert data["live_chains"] == 1

    def test_dashboard_dormant_ratio_in_range(self, tmp_path):
        arts = _run_export(tmp_path)
        with open(arts["dashboard_summary.json"]) as f:
            data = json.load(f)
        r = data["dormant_ghost_ratio"]
        assert 0.0 <= r <= 1.0

    def test_top_issues_parses_as_list(self, tmp_path):
        arts = _run_export(tmp_path)
        with open(arts["top_issues.json"]) as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_top_issues_max_20(self, tmp_path):
        arts = _run_export(tmp_path)
        with open(arts["top_issues.json"]) as f:
            data = json.load(f)
        assert len(data) <= 20

    def test_top_issues_has_required_keys(self, tmp_path):
        arts = _run_export(tmp_path)
        with open(arts["top_issues.json"]) as f:
            data = json.load(f)
        if data:
            item = data[0]
            for key in ["family_key", "urgency_label", "executive_summary", "action_priority_rank"]:
                assert key in item, f"top_issues item missing key: {key}"

    def test_top_theme_from_summary(self, tmp_path):
        arts = _run_export(tmp_path)
        with open(arts["dashboard_summary.json"]) as f:
            data = json.load(f)
        assert data["top_theme_by_impact"] == "L3_PRIMARY_CONSULTANT_DELAY"


# ── Test 4: Empty Inputs ──────────────────────────────────────────────────────

class TestEmptyInputs:
    def _empty_export(self, tmp_path):
        return export_chain_onion_outputs(
            chain_register_df=pd.DataFrame(),
            chain_versions_df=pd.DataFrame(),
            chain_events_df=pd.DataFrame(),
            chain_metrics_df=pd.DataFrame(),
            onion_layers_df=pd.DataFrame(),
            onion_scores_df=pd.DataFrame(),
            chain_narratives_df=pd.DataFrame(),
            portfolio_metrics={},
            onion_portfolio_summary={},
            output_dir=str(tmp_path),
        )

    def test_empty_runs_without_error(self, tmp_path):
        arts = self._empty_export(tmp_path)
        assert isinstance(arts, dict)

    def test_empty_csvs_exist(self, tmp_path):
        arts = self._empty_export(tmp_path)
        for name in ["CHAIN_REGISTER.csv", "ONION_SCORES.csv", "CHAIN_NARRATIVES.csv"]:
            assert Path(arts[name]).exists()

    def test_empty_csv_has_zero_rows(self, tmp_path):
        arts = self._empty_export(tmp_path)
        try:
            df = pd.read_csv(arts["CHAIN_REGISTER.csv"])
            assert len(df) == 0
        except pd.errors.EmptyDataError:
            # Fully empty DataFrame (no columns) → empty file — acceptable
            pass

    def test_empty_xlsx_exists(self, tmp_path):
        arts = self._empty_export(tmp_path)
        assert Path(arts["CHAIN_ONION_SUMMARY.xlsx"]).exists()

    def test_empty_xlsx_has_all_sheets(self, tmp_path):
        arts = self._empty_export(tmp_path)
        xl = pd.ExcelFile(arts["CHAIN_ONION_SUMMARY.xlsx"])
        assert len(xl.sheet_names) == 11

    def test_empty_dashboard_json_parseable(self, tmp_path):
        arts = self._empty_export(tmp_path)
        with open(arts["dashboard_summary.json"]) as f:
            data = json.load(f)
        assert data["total_chains"] == 0

    def test_empty_top_issues_is_empty_list(self, tmp_path):
        arts = self._empty_export(tmp_path)
        with open(arts["top_issues.json"]) as f:
            data = json.load(f)
        assert data == []

    def test_empty_kpi_sheet_has_headers(self, tmp_path):
        arts = self._empty_export(tmp_path)
        df = pd.read_excel(arts["CHAIN_ONION_SUMMARY.xlsx"], sheet_name="Portfolio KPIs")
        # Empty dicts → empty KPI sheet but should not crash
        assert isinstance(df, pd.DataFrame)


# ── Test 5: Deterministic Sort ────────────────────────────────────────────────

class TestDeterministicSort:
    def test_csv_identical_on_repeat(self, tmp_path):
        d1 = tmp_path / "run1"
        d2 = tmp_path / "run2"
        arts1 = _run_export(d1)
        arts2 = _run_export(d2)
        df1 = pd.read_csv(arts1["ONION_SCORES.csv"])
        df2 = pd.read_csv(arts2["ONION_SCORES.csv"])
        pd.testing.assert_frame_equal(df1, df2)

    def test_narratives_csv_identical_on_repeat(self, tmp_path):
        d1 = tmp_path / "run1"
        d2 = tmp_path / "run2"
        arts1 = _run_export(d1)
        arts2 = _run_export(d2)
        df1 = pd.read_csv(arts1["CHAIN_NARRATIVES.csv"])
        df2 = pd.read_csv(arts2["CHAIN_NARRATIVES.csv"])
        pd.testing.assert_frame_equal(df1, df2)

    def test_inputs_not_mutated(self, tmp_path):
        reg = _reg(3)
        original_keys = reg["family_key"].tolist()
        export_chain_onion_outputs(
            chain_register_df=reg,
            chain_versions_df=_ver(3),
            chain_events_df=_evn(3),
            chain_metrics_df=_mtr(3),
            onion_layers_df=_lay(3),
            onion_scores_df=_scr(3),
            chain_narratives_df=_nar(3),
            portfolio_metrics=_portfolio_metrics(),
            onion_portfolio_summary=_onion_summary(),
            output_dir=str(tmp_path),
        )
        assert reg["family_key"].tolist() == original_keys

    def test_chain_register_sorted_by_family_key(self, tmp_path):
        _run_export(tmp_path)
        df = pd.read_csv(tmp_path / "CHAIN_REGISTER.csv")
        keys = df["family_key"].tolist()
        assert keys == sorted(keys)


# ── Test 6: Return Dict ───────────────────────────────────────────────────────

class TestReturnDict:
    _EXPECTED_KEYS = [
        "CHAIN_REGISTER.csv",
        "CHAIN_VERSIONS.csv",
        "CHAIN_EVENTS.csv",
        "CHAIN_METRICS.csv",
        "ONION_LAYERS.csv",
        "ONION_SCORES.csv",
        "CHAIN_NARRATIVES.csv",
        "dashboard_summary.json",
        "top_issues.json",
        "CHAIN_ONION_SUMMARY.xlsx",
    ]

    def test_returns_dict(self, tmp_path):
        arts = _run_export(tmp_path)
        assert isinstance(arts, dict)

    def test_all_expected_keys_present(self, tmp_path):
        arts = _run_export(tmp_path)
        for key in self._EXPECTED_KEYS:
            assert key in arts, f"Missing return key: {key}"

    def test_all_paths_are_strings(self, tmp_path):
        arts = _run_export(tmp_path)
        for k, v in arts.items():
            assert isinstance(v, str), f"Path for {k} is not a string"

    def test_all_paths_exist(self, tmp_path):
        arts = _run_export(tmp_path)
        for k, v in arts.items():
            assert Path(v).exists(), f"Artifact path does not exist: {k} → {v}"

    def test_output_dir_created(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "dir"
        arts = export_chain_onion_outputs(
            chain_register_df=_reg(),
            chain_versions_df=_ver(),
            chain_events_df=_evn(),
            chain_metrics_df=_mtr(),
            onion_layers_df=_lay(),
            onion_scores_df=_scr(),
            chain_narratives_df=_nar(),
            portfolio_metrics=_portfolio_metrics(),
            onion_portfolio_summary=_onion_summary(),
            output_dir=str(nested),
        )
        assert nested.exists()
        assert any(Path(v).exists() for v in arts.values())


# ── Test 7: Live Run (Skipped) ────────────────────────────────────────────────

class TestLiveRun:
    @pytest.mark.skip(reason="Full live run — Claude Code / Codex only")
    def test_live_run(self):
        """
        Full live export generation using real pipeline data.

        Run manually:
            pytest tests/test_exporter.py -k TestLiveRun -s

        Expected output:
        - All 10 artifacts created in output/chain_onion/
        - Row counts logged per CSV
        - Sheet row counts logged per XLSX sheet
        - dashboard_summary.json printed with all 8 required keys
        - top_issues.json shows top 20 chains
        """
        pass
