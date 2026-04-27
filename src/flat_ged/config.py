"""
config.py — Central configuration for ged_flat_builder.

Imports reference constants from input/source_main/ and defines
derived constants used throughout the pipeline.

The source_main layer is the authoritative source for:
  - Consultant/approver mapping
  - Status normalization rules
  - GED file structure assumptions

DO NOT duplicate those definitions here — import them.
"""

import sys
from pathlib import Path

# ── Source-main reference layer ───────────────────────────────────────────────
_SOURCE_MAIN = Path(__file__).parent / "input" / "source_main"
if str(_SOURCE_MAIN) not in sys.path:
    sys.path.insert(0, str(_SOURCE_MAIN))

from consultant_mapping import (
    RAW_TO_CANONICAL,
    EXCEPTION_COLUMNS,
    CANONICAL_TO_DISPLAY,
)
from status_mapping import (
    VALID_STATUSES,
    BUREAU_CONTROLE_STATUSES,
    EMPTY_STATUS_VALUES,
    PENDING_KEYWORDS,
    DEADLINE_DATE_PATTERN,
)
from ged_parser_contract import (
    GED_SHEET_NAME,
    CORE_COLUMNS,
    HEADER_STRUCTURE,
)

# ── Phase window constants (contractual) ─────────────────────────────────────
SAS_WINDOW_DAYS    = 15   # Phase A: SAS response deadline
GLOBAL_WINDOW_DAYS = 30   # Phase B: consultant/MOEX deadline (if SAS on time)

# ── Canonical actor identifiers ───────────────────────────────────────────────
MOEX_CANONICAL = "Maître d'Oeuvre EXE"
SAS_CANONICAL  = "0-SAS"

# ── Status vocabulary ─────────────────────────────────────────────────────────
# Union of standard + Bureau de Contrôle vocabularies (matches prototype_v4.py)
VALID_STATUS_CODES: set[str] = VALID_STATUSES | BUREAU_CONTROLE_STATUSES | {"HM", "DEF"}

# Statuses that mark a step as completed (response received, cycle progresses)
ALL_COMPLETED: set[str] = {"VAO", "VSO", "FAV", "SUS", "DEF", "REF", "HM"}

# ── Display names (canonical → company name) ──────────────────────────────────
# Start from source_main's CANONICAL_TO_DISPLAY, then add the SAS display name
# (source_main uses "MOEX SAS" → "GEMO (SAS)" but the pipeline uses "0-SAS")
DISPLAY: dict[str, str] = {**CANONICAL_TO_DISPLAY}
DISPLAY[SAS_CANONICAL] = "SAS (GEMO)"

# ── Base document field names (as a set, for fast header detection) ───────────
BASE_FIELD_NAMES: set[str] = set(CORE_COLUMNS)
