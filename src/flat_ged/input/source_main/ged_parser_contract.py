"""
ged_parser_contract.py
----------------------
Extracted from: src/read_raw.py

Specification of the GED Excel file structure.
Not executable code — a contract for any parser to satisfy.

Use ONLY for: knowing which sheet to open, how to read the 2-row header,
which columns are base fields vs. approver groups, and what sub-fields each group contains.
DO NOT add: normalization, routing, or business processing.
"""

# The only sheet in the GED export that contains workflow documents.
GED_SHEET_NAME = "Doc. sous workflow, x versions"


# ── HEADER LAYOUT ────────────────────────────────────────────────────────────
# Row 1: base field names  |  approver name (merged across 4 cols)  |  next...
# Row 2: (empty)           |  Date réponse | Réponse | Commentaire | PJ | ...
# Data starts at row 3.
HEADER_STRUCTURE = {
    "header_rows":            2,
    "data_starts_at_row":     3,   # 1-indexed
    "columns_per_approver":   4,   # each approver group spans exactly 4 columns
    "approver_detection":     "row1 value is non-empty AND not in CORE_COLUMNS",
}


# ── BASE DOCUMENT COLUMNS ────────────────────────────────────────────────────
# Appear as standalone columns in row 1. One GED row = one document.
CORE_COLUMNS = [
    "AFFAIRE",              # project/operation code
    "PROJET",               # project name
    "BATIMENT",             # building (A, B, H, ...)
    "PHASE",                # construction phase
    "EMETTEUR",             # contractor short code (e.g. LGD, AXI)
    "SPECIALITE",           # trade/specialty code
    "LOT",                  # lot code (e.g. A041, B013A)
    "TYPE DE DOC",          # document type (PLAN, NOTE, FICHE...)
    "ZONE",                 # zone within building
    "NIVEAU",               # floor level
    "NUMERO",               # document number (integer in GED)
    "INDICE",               # revision index (A, B, C...)
    "Libellé du document",  # document title
    "Créé le",              # creation date (datetime)
]


# ── APPROVER SUB-FIELDS ───────────────────────────────────────────────────────
# Each approver group has 4 consecutive columns with these sub-field labels in row 2.
APPROVER_SUB_FIELDS = ["Date réponse", "Réponse", "Commentaire", "PJ"]

APPROVER_SUB_OFFSETS = {
    "Date réponse":  0,   # datetime or French pending text
    "Réponse":       1,   # status string (e.g. ".VAO", "VSO")
    "Commentaire":   2,   # free-text comment (may be None)
    "PJ":            3,   # attachment flag: any non-None/non-zero value → flag = 1
}


# ── OUTPUT SHAPE ──────────────────────────────────────────────────────────────
# Reading the GED produces two tables joined by a doc identifier:
#   docs table:      one row per GED document (snake_case CORE_COLUMNS)
#   responses table: one row per (document × approver), long format
RESPONSES_FIELDS = [
    "approver_raw",          # exact GED column header (e.g. "A-BET Structure")
    "response_date_raw",     # raw "Date réponse" value (datetime or text)
    "response_status_raw",   # raw "Réponse" value (e.g. ".VAO")
    "response_comment",      # free text or None
    "pj_flag",               # 1 if attachment present, else 0
]
