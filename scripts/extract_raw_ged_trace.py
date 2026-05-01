#!/usr/bin/env python3
"""
scripts/extract_raw_ged_trace.py  —  Phase 8B, Step 8B.1
---------------------------------------------------------
RAW GED Event Extraction.

Reads input/GED_export.xlsx sheet "Doc. sous workflow, x versions" and emits
one row per (data-row, approver-block) combination, plus one DOCUMENT_VERSION
row per data row. Output: output/debug/raw_ged_trace.csv

═══════════════════════════════════════════════════════════════════════════════
RESOLVED OPEN QUESTIONS (§23 of PHASE_8B_RAW_TO_FLAT_RECONCILIATION.md)
═══════════════════════════════════════════════════════════════════════════════

1. Multi-cycle SAS representation in RAW (OQ-1):
   "0-SAS" appears TWICE in row 1 — at Excel col 232 (C1) and col 236 (C2).
   "Sollicitation supplémentaire" also appears twice (C1 at col 344, C2 at 348).
   Both are assigned cycle_id "C1"/"C2" by occurrence order.

2. FLAT cycle index (OQ-2):
   GED_OPERATIONS.step_order carries sequence position but NOT a cycle label.
   There is NO cycle_id column in FLAT. SAS rows carry step_type="SAS" only.
   Consequence: every RAW multi-cycle SAS pair is a SAS_CYCLE_COLLAPSED
   candidate in the §5 taxonomy.

3. Actor canonical map source (OQ-3):
   Source: consultant_mapping.RAW_TO_CANONICAL (which mirrors
   normalize._GED_APPROVER_MAPPING). Re-implemented INLINE below per §8.3
   step 6 — src/flat_ged/* is NOT imported anywhere in this script.

4. status_clean mapping (OQ-4):
   Source: normalize.clean_status(). Re-implemented inline:
     strip() → if empty/none/nan → None; lstrip('.') → strip() → upper()

5. Report-ingest scope: §15 only (8B.8). Not relevant here.
6. OPEN_DOC/SAS/CONSULTANT/MOEX: step_type aggregates inside GED_OPERATIONS,
   not separate sheets. No "OPEN_DOC sheet" in FLAT_GED.xlsx.

═══════════════════════════════════════════════════════════════════════════════
GED SHEET STRUCTURE (verified by inspection)
═══════════════════════════════════════════════════════════════════════════════

Sheet: "Doc. sous workflow, x versions"
  max_row = 6903, max_col = 355
  Row 1: meta cols (1-15) + approver names starting at col 16 (one per 4-col block)
  Row 2: sub-headers per block: Date réponse | Réponse | Commentaire | PJ
  Rows 3-6903: data rows (6901 rows; 4848 unique (numero, indice) pairs)

Meta columns (1-indexed):
  1=blank  2=AFFAIRE  3=PROJET  4=BATIMENT  5=PHASE  6=EMETTEUR
  7=SPECIALITE  8=LOT  9=TYPE DE DOC  10=ZONE  11=NIVEAU
  12=NUMERO  13=INDICE  14=Libellé du document  15=Créé le

Approver blocks: 84 total, starting at col 16, each 4 cols wide.
Multi-cycle: 0-SAS (C1=col232, C2=col236); Sollicitation supplémentaire
             (C1=col344, C2=col348).

═══════════════════════════════════════════════════════════════════════════════
COLUMN SEMANTICS AND IDENTITY-PARITY FILTER (8B.3 contract)
═══════════════════════════════════════════════════════════════════════════════

numero/indice column semantics:
  Every event type (DOCUMENT_VERSION, ACTOR_CALLED, RESPONSE) emitted for a
  given GED data row carries the SAME numero and indice values — they are
  inherited from the submission-instance. There is no footgun: event-type rows
  share the same identity as the DOCUMENT_VERSION row they annotate.

_MISSING_ synthetic keys:
  746 GED data rows have NUMERO=None (PPSPS, BdT docs without standard document
  numbers); the remaining 6155 of the 6901 data rows carry a named NUMERO.
  The 746 rows carry valid SAS REF responses and are NOT skipped. They receive
  the synthetic key numero="_MISSING_{excel_row}" so they appear in the trace
  CSV and are counted toward sas_ref_unique_pairs.
  Consequence: raw CSV unique_numero=3565, unique_pairs=5594 when counted naively.
  The stdout counters (2819 / 4848) exclude these rows; they match §7 baselines.

Filter that 8B.3 raw_flat_reconcile.py MUST apply before building identity sets:
  df = df[~df['numero'].str.startswith('_MISSING_')]
  Bake this into raw_flat_reconcile.py at 8B.3 time.

sas_ref metrics (two distinct counts):
  sas_ref_rows        = total RESPONSE rows in CSV where actor_raw=="0-SAS"
                        and status_clean=="REF" (counts C1 and C2 separately)
                        Verified: 837
  sas_ref_unique_pairs = unique source_excel_row values where any 0-SAS cycle
                        has REF (OR-distinct GED data rows) — matches §7 / L0
                        audit definition. Verified: 836
  One GED data row has both C1 and C2 == REF → contributes 2 to sas_ref_rows
  but only 1 to sas_ref_unique_pairs.
"""

from __future__ import annotations

import csv
import datetime as _dt
import re
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

# ── Paths ──────────────────────────────────────────────────────────────────────
_ROOT    = Path(__file__).resolve().parent.parent
_GED     = _ROOT / "input" / "GED_export.xlsx"
_OUT_DIR = _ROOT / "output" / "debug"
_OUT_CSV = _OUT_DIR / "raw_ged_trace.csv"
_SHEET   = "Doc. sous workflow, x versions"

# ── Inline actor canonical map ─────────────────────────────────────────────────
# Re-implemented from consultant_mapping.RAW_TO_CANONICAL per §8.3 step 6.
# src/flat_ged/* is NEVER imported from this script.

_CONSULTANT_ROLES: list[str] = [
    "AMO HQE", "ARCHITECTE", "BET Acoustique", "BET Ascenseur",
    "BET CVC", "BET Electricité", "BET EV", "BET Façade",
    "BET Plomberie", "BET POL", "BET SPK", "BET Structure",
    "BET VRD", "Bureau de Contrôle", "Maître d'Oeuvre EXE",
]

RAW_TO_CANONICAL: dict[str, str] = {}
for _pfx in ("0-", "A-", "B-", "H-"):
    for _role in _CONSULTANT_ROLES:
        RAW_TO_CANONICAL[f"{_pfx}{_role}"] = _role

# Conformity gate — kept distinct, never treated as a consultant
RAW_TO_CANONICAL["0-SAS"] = "0-SAS"

# Exception columns — lot/trade-specific columns excluded from consultant processing
_EXCEPTION_COLS: frozenset[str] = frozenset({
    "0-BET Géotech", "0-BET Synthèse", "0-BIM Manager", "0-CSPS",
    "A05-MNS EXT", "A06-REVET FAC", "A07-CSQ PREFA", "A08-MR",
    "A22-SDB Préfa", "A31-33-34-ELEC", "A41-CVC", "A42 PLB",
    "B05-MNS EXT", "B06 - REVÊTEMENT EXT", "B13 - METALLERIE SERRURERIE",
    "B31-33-34-CFO-CFA", "B35-GTB", "B41-CVC", "B42 PLB",
    "H05-MNS EXT", "H06-REVET FAC", "H07-CSQ PREFA", "H08-MUR RIDEAUX",
    "H31-33-34-CFO-CFA", "H35-GTB", "H41-CVC", "H42 PLB", "H51-ASC",
    "00-TCE", "01-TERRASSEMENTS", "02-FONDATIONS SPECIALES", "03-GOE",
    "08-MURS RIDEAUX", "35-GTB", "41-CVC", "42-PLB",
    "Sollicitation supplémentaire",
})
for _ec in _EXCEPTION_COLS:
    RAW_TO_CANONICAL[_ec] = "Exception List"

del _pfx, _role, _ec  # clean up loop vars


# ── Inline status_clean (from normalize.clean_status) ─────────────────────────

def _clean_status(raw) -> str | None:
    """Strip leading dots and normalize; returns None for blank/none/nan."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s.lower() in ("", "none", "nan"):
        return None
    s = s.lstrip(".")
    s = s.strip()
    return s.upper() if s else None


# ── Inline date interpretation (from normalize.interpret_date_field) ───────────

_DL_RE = re.compile(r'\((\d{4})/(\d{2})/(\d{2})\)')


def _extract_deadline(raw_str: str) -> str | None:
    m = _DL_RE.search(raw_str)
    if m:
        try:
            d = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return d.isoformat()
        except ValueError:
            pass
    return None


def _interpret_date(raw) -> tuple[str | None, str | None, str]:
    """
    Returns (response_date_iso, deadline_date_iso, date_status_type).
    Maps the "Date réponse" cell to the same classifications as normalize.interpret_date_field.
    """
    if raw is None:
        return None, None, "NOT_CALLED"
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None, None, "NOT_CALLED"
        lower = s.lower()
        dl = _extract_deadline(s)
        if lower.startswith("rappel"):
            return None, dl, "PENDING_LATE"
        if "en attente" in lower:
            return None, dl, "PENDING_IN_DELAY"
        # Non-standard text — treat as unknown pending
        return None, dl, "PENDING_IN_DELAY"
    if isinstance(raw, _dt.datetime):
        return raw.date().isoformat(), None, "ANSWERED"
    if isinstance(raw, _dt.date):
        return raw.isoformat(), None, "ANSWERED"
    return None, None, "NOT_CALLED"


# ── Build approver block list from header row ──────────────────────────────────

def _build_blocks(row1: list) -> list[tuple[int, str, str | None]]:
    """
    Parse row 1 to find all approver blocks.
    Returns list of (col_0idx, approver_name, cycle_id).
    col_0idx is the 0-indexed start of the block (Date réponse sub-column).
    cycle_id is None for unique names; "C1"/"C2" for repeated names.
    Approver columns start at 0-indexed position 15 (1-indexed col 16).
    """
    raw_blocks: list[tuple[int, str]] = [
        (ci, str(v)) for ci, v in enumerate(row1) if ci >= 15 and v is not None
    ]
    name_count: Counter[str] = Counter(name for _, name in raw_blocks)
    name_seq: dict[str, int] = defaultdict(int)

    result = []
    for ci, name in raw_blocks:
        seq = name_seq[name]
        name_seq[name] += 1
        cycle_id = f"C{seq + 1}" if name_count[name] > 1 else None
        result.append((ci, name, cycle_id))
    return result


# ── CSV columns ────────────────────────────────────────────────────────────────

_COLS: list[str] = [
    "source_file", "source_sheet", "source_excel_row",
    "numero", "indice", "lot", "emetteur", "titre",
    "cycle_id", "actor_raw", "actor_canonical",
    "event_type",
    "status_raw", "status_clean",
    "response_date", "submission_date", "deadline_date", "date_status_type",
    "comment_raw", "pj_flag",
]

# Meta column indices (0-indexed, from GED_export.xlsx row-1 inspection)
_CI_LOT    = 7   # col 8
_CI_EMET   = 5   # col 6
_CI_NUMERO = 11  # col 12
_CI_INDICE = 12  # col 13
_CI_TITRE  = 13  # col 14
_CI_SUBDAT = 14  # col 15 (Créé le)


# ── Main extraction function ───────────────────────────────────────────────────

def extract(ged_path: Path = _GED, out_csv: Path = _OUT_CSV) -> dict:
    """
    Extract RAW GED events to CSV.
    Returns summary dict with total_rows, unique_numero, unique_numero_indice,
    sas_ref_rows (total CSV RESPONSE rows), sas_ref_unique_pairs (OR-distinct).
    """
    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    # data_only=True reads cached formula values. read_only=True is intentionally
    # OMITTED here: in read_only mode openpyxl skips some cached values for formula
    # cells, causing silent undercounting (verified: 810 vs 836 REF cells).
    wb   = openpyxl.load_workbook(str(ged_path), data_only=True)
    ws   = wb[_SHEET]
    rows = ws.iter_rows(values_only=True)

    # Single-pass: read headers first, then data
    row1 = list(next(rows))  # Excel row 1: approver names
    _    = next(rows)        # Excel row 2: sub-headers (Date réponse / Réponse / …)
    blocks = _build_blocks(row1)

    total_rows    = 0
    all_numeros:  set[str] = set()
    all_pairs:    set[tuple] = set()
    missing_numero_count: int = 0
    # sas_ref_unique_rows: unique Excel data row indices where any 0-SAS cycle
    # has Réponse=="REF" (OR-distinct). Matches L0 audit definition. Verified: 836.
    sas_ref_unique_rows: set[int] = set()
    # sas_ref_total: total RESPONSE rows in CSV with actor_raw=="0-SAS" and
    # status_clean=="REF" (C1 and C2 counted separately). Verified: 837.
    sas_ref_total: int = 0

    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_COLS)
        writer.writeheader()

        for excel_row_0idx, data_row in enumerate(rows, 3):  # data starts at Excel row 3
            # Safe cell access helper
            def cell(ci: int):
                return data_row[ci] if ci < len(data_row) else None

            # Skip only all-blank rows (all 355 cells are None)
            # Rows with NUMERO=None but other data present (e.g. PPSPS, BdT docs
            # that appear in the GED without a standard NUMERO) are kept — they
            # may carry SAS REF responses that must be counted for D-011.
            if all(v is None for v in data_row):
                continue

            numero_raw = cell(_CI_NUMERO)
            if numero_raw is None:
                # No NUMERO — synthetic key for traceability; excluded from unique counts
                numero = f"_MISSING_{excel_row_0idx}"
                missing_numero_count += 1
            else:
                try:
                    numero = str(int(float(numero_raw)))
                except (ValueError, TypeError):
                    numero = str(numero_raw).strip()

            indice   = str(cell(_CI_INDICE)).strip() if cell(_CI_INDICE) is not None else ""
            lot      = str(cell(_CI_LOT)).strip()    if cell(_CI_LOT)    is not None else ""
            emetteur = str(cell(_CI_EMET)).strip()   if cell(_CI_EMET)   is not None else ""
            titre    = str(cell(_CI_TITRE)).strip()  if cell(_CI_TITRE)  is not None else ""

            sub_date, _, _ = _interpret_date(cell(_CI_SUBDAT))

            if not numero.startswith("_MISSING_"):
                all_numeros.add(numero)
                all_pairs.add((numero, indice))

            # ── DOCUMENT_VERSION row (one per data row) ────────────────────
            writer.writerow({
                "source_file":      "GED_export.xlsx",
                "source_sheet":     _SHEET,
                "source_excel_row": excel_row_0idx,
                "numero": numero, "indice": indice,
                "lot": lot, "emetteur": emetteur, "titre": titre,
                "cycle_id": None, "actor_raw": None, "actor_canonical": None,
                "event_type":       "DOCUMENT_VERSION",
                "status_raw": None, "status_clean": None,
                "response_date": None, "submission_date": sub_date,
                "deadline_date": None, "date_status_type": None,
                "comment_raw": None, "pj_flag": None,
            })
            total_rows += 1

            # ── Approver-block rows ────────────────────────────────────────
            for ci, actor_raw, cycle_id in blocks:
                date_cell    = cell(ci)
                status_cell  = cell(ci + 1)
                comment_cell = cell(ci + 2)
                pj_cell      = cell(ci + 3)

                # Skip blocks where all 4 sub-cells are None (actor not involved)
                if (date_cell is None and status_cell is None
                        and comment_cell is None and pj_cell is None):
                    continue

                actor_canonical = RAW_TO_CANONICAL.get(actor_raw, actor_raw)
                sc              = _clean_status(status_cell)
                resp_date, dl_date, dst = _interpret_date(date_cell)
                event_type = "RESPONSE" if status_cell is not None else "ACTOR_CALLED"

                writer.writerow({
                    "source_file":      "GED_export.xlsx",
                    "source_sheet":     _SHEET,
                    "source_excel_row": excel_row_0idx,
                    "numero": numero, "indice": indice,
                    "lot": lot, "emetteur": emetteur, "titre": titre,
                    "cycle_id":         cycle_id,
                    "actor_raw":        actor_raw,
                    "actor_canonical":  actor_canonical,
                    "event_type":       event_type,
                    "status_raw":       str(status_cell) if status_cell is not None else None,
                    "status_clean":     sc,
                    "response_date":    resp_date,
                    "submission_date":  sub_date,
                    "deadline_date":    dl_date,
                    "date_status_type": dst,
                    "comment_raw":      str(comment_cell) if comment_cell is not None else None,
                    "pj_flag":          1 if pj_cell else 0,
                })
                total_rows += 1

                if actor_raw == "0-SAS" and sc == "REF" and event_type == "RESPONSE":
                    sas_ref_unique_rows.add(excel_row_0idx)
                    sas_ref_total += 1

    wb.close()

    return {
        "total_rows":             total_rows,
        "unique_numero":          len(all_numeros),
        "unique_numero_indice":   len(all_pairs),
        "missing_numero_rows":    missing_numero_count,
        "sas_ref_rows":           sas_ref_total,
        "sas_ref_unique_pairs":   len(sas_ref_unique_rows),
    }


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    summary = extract()
    print(
        f"RAW_TRACE: rows={summary['total_rows']} "
        f"unique_numero={summary['unique_numero']} "
        f"unique_numero_indice={summary['unique_numero_indice']} "
        f"missing_numero_rows={summary['missing_numero_rows']} "
        f"sas_ref_rows={summary['sas_ref_rows']} "
        f"sas_ref_unique_pairs={summary['sas_ref_unique_pairs']}"
    )
