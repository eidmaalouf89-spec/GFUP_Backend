"""
tests/test_extract_raw_ged_trace.py  —  Phase 8B, Step 8B.1
------------------------------------------------------------
Unit tests for scripts/extract_raw_ged_trace.py.

All tests are mock-friendly and do NOT read input/GED_export.xlsx.
Mark any live-xlsx tests as @pytest.mark.slow so they can be skipped
in sandbox (H-4/H-5) and confirmed on Windows shell.
"""

from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

import pytest

# Tested module lives in scripts/ — add to path before import
import sys
_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from extract_raw_ged_trace import (
    RAW_TO_CANONICAL,
    _build_blocks,
    _clean_status,
    _extract_deadline,
    _interpret_date,
    extract,
)


# ── _clean_status ──────────────────────────────────────────────────────────────

class TestCleanStatus:
    def test_none_returns_none(self):
        assert _clean_status(None) is None

    def test_empty_string_returns_none(self):
        assert _clean_status("") is None
        assert _clean_status("   ") is None

    def test_nan_string_returns_none(self):
        assert _clean_status("nan") is None
        assert _clean_status("NaN") is None
        assert _clean_status("none") is None

    def test_strips_leading_dot(self):
        assert _clean_status(".REF") == "REF"
        assert _clean_status("..VSO") == "VSO"

    def test_uppercases(self):
        assert _clean_status("ref") == "REF"
        assert _clean_status("Vso") == "VSO"

    def test_vso_sas(self):
        assert _clean_status("VSO-SAS") == "VSO-SAS"

    def test_strips_whitespace(self):
        assert _clean_status("  REF  ") == "REF"


# ── _interpret_date ────────────────────────────────────────────────────────────

class TestInterpretDate:
    def test_none_is_not_called(self):
        resp_date, dl, dst = _interpret_date(None)
        assert resp_date is None
        assert dl is None
        assert dst == "NOT_CALLED"

    def test_empty_string_is_not_called(self):
        _, _, dst = _interpret_date("")
        assert dst == "NOT_CALLED"

    def test_datetime_is_answered(self):
        import datetime
        dt = datetime.datetime(2026, 4, 30, 12, 0)
        resp_date, dl, dst = _interpret_date(dt)
        assert resp_date == "2026-04-30"
        assert dl is None
        assert dst == "ANSWERED"

    def test_date_is_answered(self):
        import datetime
        d = datetime.date(2026, 4, 30)
        resp_date, dl, dst = _interpret_date(d)
        assert resp_date == "2026-04-30"
        assert dst == "ANSWERED"

    def test_en_attente_is_pending_in_delay(self):
        _, dl, dst = _interpret_date("En attente visa (2026/05/10)")
        assert dst == "PENDING_IN_DELAY"
        assert dl == "2026-05-10"

    def test_rappel_is_pending_late(self):
        _, dl, dst = _interpret_date("Rappel : En attente visa (2026/05/10)")
        assert dst == "PENDING_LATE"
        assert dl == "2026-05-10"


# ── _build_blocks ──────────────────────────────────────────────────────────────

class TestBuildBlocks:
    def _row1(self, **kw):
        """Build a minimal row1 with None padding + named approver positions."""
        row = [None] * 360
        for ci, name in kw.items():
            row[int(ci)] = name
        return row

    def test_single_approver(self):
        row1 = self._row1(**{"15": "0-AMO HQE"})
        blocks = _build_blocks(row1)
        assert len(blocks) == 1
        assert blocks[0] == (15, "0-AMO HQE", None)

    def test_duplicate_name_gets_cycle(self):
        row1 = self._row1(**{"15": "0-SAS", "20": "0-SAS"})
        blocks = _build_blocks(row1)
        assert blocks[0] == (15, "0-SAS", "C1")
        assert blocks[1] == (20, "0-SAS", "C2")

    def test_unique_name_has_no_cycle(self):
        row1 = self._row1(**{"15": "0-AMO HQE"})
        blocks = _build_blocks(row1)
        assert blocks[0][2] is None

    def test_meta_cols_before_15_ignored(self):
        row1 = self._row1(**{"5": "should_be_ignored", "15": "0-AMO HQE"})
        blocks = _build_blocks(row1)
        assert len(blocks) == 1  # only the one at index 15


# ── RAW_TO_CANONICAL ──────────────────────────────────────────────────────────

class TestRawToCanonical:
    def test_sas_stays_sas(self):
        assert RAW_TO_CANONICAL["0-SAS"] == "0-SAS"

    def test_building_prefix_collapses(self):
        for prefix in ("0-", "A-", "B-", "H-"):
            assert RAW_TO_CANONICAL[f"{prefix}AMO HQE"] == "AMO HQE"

    def test_exception_column_maps_to_exception_list(self):
        assert RAW_TO_CANONICAL["0-BET Géotech"] == "Exception List"
        assert RAW_TO_CANONICAL["Sollicitation supplémentaire"] == "Exception List"

    def test_bureau_de_controle_canonical(self):
        assert RAW_TO_CANONICAL["0-Bureau de Contrôle"] == "Bureau de Contrôle"


# ── extract (mock-based) ───────────────────────────────────────────────────────

def _build_mock_xlsx(tmp_path: Path) -> Path:
    """
    Build a minimal fake xlsx that the extract() function can read.
    Structure mirrors the real GED: 2-header rows + 3 data rows.
    Columns: 0-14 = meta; 15-18 = approver block for "0-AMO HQE";
             19-22 = approver block for "0-SAS" (C1); 23-26 = "0-SAS" (C2).
    """
    import openpyxl
    import datetime

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Doc. sous workflow, x versions"

    # Row 1: meta col names + approver names
    row1 = [None] * 27
    row1[1]  = "AFFAIRE"
    row1[5]  = "EMETTEUR"
    row1[7]  = "LOT"
    row1[11] = "NUMERO"
    row1[12] = "INDICE"
    row1[13] = "Libellé du document"
    row1[14] = "Créé le"
    row1[15] = "0-AMO HQE"   # block at ci=15: Date|Réponse|Commentaire|PJ
    row1[19] = "0-SAS"       # C1 at ci=19
    row1[23] = "0-SAS"       # C2 at ci=23
    ws.append(row1)

    # Row 2: sub-headers
    row2 = [None] * 27
    for base in (15, 19, 23):
        row2[base]     = "Date réponse"
        row2[base + 1] = "Réponse"
        row2[base + 2] = "Commentaire"
        row2[base + 3] = "PJ"
    ws.append(row2)

    # Data rows
    def data_row(num, ind, lot, emet, titre, cree_le,
                 amo_resp=None, sas_c1_resp=None, sas_c2_resp=None):
        r = [None] * 27
        r[11] = num; r[12] = ind; r[7] = lot; r[5] = emet
        r[13] = titre; r[14] = cree_le
        # AMO HQE block: just the Réponse at offset+1
        if amo_resp:
            r[16] = amo_resp
        # SAS C1
        if sas_c1_resp:
            r[20] = sas_c1_resp
        # SAS C2
        if sas_c2_resp:
            r[24] = sas_c2_resp
        return r

    ws.append(data_row(100001, "A", "L01", "API", "doc1.pdf",
                       datetime.datetime(2025, 1, 1), amo_resp="VAO", sas_c1_resp="REF"))
    ws.append(data_row(100002, "A", "L02", "API", "doc2.pdf",
                       datetime.datetime(2025, 1, 2), sas_c1_resp="VSO-SAS"))
    ws.append(data_row(100001, "B", "L01", "API", "doc1b.pdf",
                       datetime.datetime(2025, 1, 3), sas_c1_resp="REF", sas_c2_resp="REF"))

    out = tmp_path / "mock_ged.xlsx"
    wb.save(str(out))
    return out


class TestExtractFunction:
    def test_extract_returns_correct_counts(self, tmp_path):
        mock_ged = _build_mock_xlsx(tmp_path)
        out_csv  = tmp_path / "raw_trace.csv"
        summary  = extract(ged_path=mock_ged, out_csv=out_csv)

        # 3 data rows → 3 unique (numero, indice) pairs
        assert summary["unique_numero_indice"] == 3, summary
        # numerors: 100001, 100002 → 2 unique
        assert summary["unique_numero"] == 2, summary
        # sas_ref_rows: row1 C1=REF (1) + row3 C1=REF + C2=REF (2) = 3 total RESPONSE rows
        assert summary["sas_ref_rows"] == 3, summary
        # sas_ref_unique_pairs: row1 and row3 → 2 unique excel data rows (OR-distinct)
        assert summary["sas_ref_unique_pairs"] == 2, summary

    def test_csv_written(self, tmp_path):
        mock_ged = _build_mock_xlsx(tmp_path)
        out_csv  = tmp_path / "raw_trace.csv"
        extract(ged_path=mock_ged, out_csv=out_csv)
        assert out_csv.exists()
        rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
        assert len(rows) > 0

    def test_document_version_rows_present(self, tmp_path):
        mock_ged = _build_mock_xlsx(tmp_path)
        out_csv  = tmp_path / "raw_trace.csv"
        extract(ged_path=mock_ged, out_csv=out_csv)
        rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
        dv_rows = [r for r in rows if r["event_type"] == "DOCUMENT_VERSION"]
        # 3 data rows → 3 DOCUMENT_VERSION events
        assert len(dv_rows) == 3

    def test_response_event_type_when_status_present(self, tmp_path):
        mock_ged = _build_mock_xlsx(tmp_path)
        out_csv  = tmp_path / "raw_trace.csv"
        extract(ged_path=mock_ged, out_csv=out_csv)
        rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
        resp_rows = [r for r in rows if r["event_type"] == "RESPONSE"]
        # AMO HQE VAO (row1), SAS C1 REF (row1), SAS C1 VSO-SAS (row2),
        # SAS C1 REF (row3), SAS C2 REF (row3) → 5 RESPONSE rows
        assert len(resp_rows) == 5

    def test_sas_cycle_id_assigned(self, tmp_path):
        mock_ged = _build_mock_xlsx(tmp_path)
        out_csv  = tmp_path / "raw_trace.csv"
        extract(ged_path=mock_ged, out_csv=out_csv)
        rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
        sas_rows = [r for r in rows if r["actor_raw"] == "0-SAS"]
        cycle_ids = {r["cycle_id"] for r in sas_rows}
        assert "C1" in cycle_ids
        assert "C2" in cycle_ids

    def test_actor_canonical_mapped(self, tmp_path):
        mock_ged = _build_mock_xlsx(tmp_path)
        out_csv  = tmp_path / "raw_trace.csv"
        extract(ged_path=mock_ged, out_csv=out_csv)
        rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
        amo_rows = [r for r in rows if r["actor_raw"] == "0-AMO HQE"]
        assert all(r["actor_canonical"] == "AMO HQE" for r in amo_rows)


# ── Live xlsx smoke test (skip in sandbox due to H-5) ─────────────────────────

@pytest.mark.slow
def test_live_extraction_baselines(tmp_path):
    """Full extraction against real GED_export.xlsx — run on Windows shell."""
    root    = Path(__file__).resolve().parent.parent
    ged     = root / "input" / "GED_export.xlsx"
    out_csv = tmp_path / "raw_trace_live.csv"
    if not ged.exists():
        pytest.skip("GED_export.xlsx not found")

    summary = extract(ged_path=ged, out_csv=out_csv)
    assert summary["unique_numero"]        == 2819, summary
    assert summary["unique_numero_indice"] == 4848, summary
    assert summary["sas_ref_rows"]         == 837,  summary
    assert summary["sas_ref_unique_pairs"] == 836,  summary
