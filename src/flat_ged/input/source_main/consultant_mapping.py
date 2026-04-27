"""
consultant_mapping.py
---------------------
Extracted from: src/normalize.py (_GED_APPROVER_MAPPING)
               src/reporting/consultant_fiche.py (CONSULTANT_DISPLAY_NAMES)

Purpose: Map raw GED approver column headers → canonical names → display (company) names.

Use ONLY for:
  - Identifying which GED columns represent consultants
  - Normalizing approver names to a single canonical form across buildings
  - Resolving the company name behind each canonical

DO NOT add: routing, workflow states, priority, fiche-building, or reporting.
"""

# ─────────────────────────────────────────────────────────────
# RAW → CANONICAL
# Maps each GED approver column header to a canonical consultant name.
# Building prefixes (0-, A-, B-, H-) all collapse to the same canonical.
# "0-SAS" is a conformity gate — kept distinct, never treated as a consultant.
# ─────────────────────────────────────────────────────────────
RAW_TO_CANONICAL: dict[str, str] = {}

_CONSULTANT_ROLES = [
    "AMO HQE", "ARCHITECTE", "BET Acoustique", "BET Ascenseur",
    "BET CVC", "BET Electricité", "BET EV", "BET Façade",
    "BET Plomberie", "BET POL", "BET SPK", "BET Structure",
    "BET VRD", "Bureau de Contrôle", "Maître d'Oeuvre EXE",
]

# Build mappings for all four building prefixes automatically
for _prefix in ("0-", "A-", "B-", "H-"):
    for _role in _CONSULTANT_ROLES:
        # Not all roles appear under every prefix — the GED omits some.
        # The mapping is inclusive: if a column appears, it maps correctly.
        RAW_TO_CANONICAL[f"{_prefix}{_role}"] = _role

# 0- prefix only: roles that only appear at the global level
RAW_TO_CANONICAL["0-BET EV"]  = "BET EV"   # already covered above, explicit for clarity
RAW_TO_CANONICAL["0-BET POL"] = "BET POL"
RAW_TO_CANONICAL["0-BET SPK"] = "BET SPK"
RAW_TO_CANONICAL["0-BET VRD"] = "BET VRD"

# Conformity gate — NOT a consultant
RAW_TO_CANONICAL["0-SAS"] = "0-SAS"

# Exception: roles that GED maps to Exception List at 0- prefix
RAW_TO_CANONICAL["0-BET Géotech"] = "Exception List"
RAW_TO_CANONICAL["0-BET Synthèse"] = "Exception List"
RAW_TO_CANONICAL["0-BIM Manager"] = "Exception List"
RAW_TO_CANONICAL["0-CSPS"] = "Exception List"


# ─────────────────────────────────────────────────────────────
# EXCEPTION COLUMNS
# These GED column headers are lot/trade-specific — NOT consultant approvers.
# Any column found in this set must be skipped during response processing.
# ─────────────────────────────────────────────────────────────
EXCEPTION_COLUMNS: set[str] = {
    # Building A
    "A05-MNS EXT", "A06-REVET FAC", "A07-CSQ PREFA", "A08-MR",
    "A22-SDB Préfa", "A31-33-34-ELEC", "A41-CVC", "A42 PLB",
    # Building B
    "B05-MNS EXT", "B06 - REVÊTEMENT EXT", "B13 - METALLERIE SERRURERIE",
    "B31-33-34-CFO-CFA", "B35-GTB", "B41-CVC", "B42 PLB",
    # Building H
    "H05-MNS EXT", "H06-REVET FAC", "H07-CSQ PREFA", "H08-MUR RIDEAUX",
    "H31-33-34-CFO-CFA", "H35-GTB", "H41-CVC", "H42 PLB", "H51-ASC",
    # Global / unprefix
    "00-TCE", "01-TERRASSEMENTS", "02-FONDATIONS SPECIALES", "03-GOE",
    "08-MURS RIDEAUX", "35-GTB", "41-CVC", "42-PLB",
    "Sollicitation supplémentaire",
    # 0- prefixed exceptions (also in RAW_TO_CANONICAL above)
    "0-BET Géotech", "0-BET Synthèse", "0-BIM Manager", "0-CSPS",
}

# Update RAW_TO_CANONICAL for all exception columns
for _col in EXCEPTION_COLUMNS:
    RAW_TO_CANONICAL[_col] = "Exception List"


# ─────────────────────────────────────────────────────────────
# CANONICAL → DISPLAY (company name)
# ─────────────────────────────────────────────────────────────
CANONICAL_TO_DISPLAY: dict[str, str] = {
    "AMO HQE":              "Le Sommer Environnement",
    "ARCHITECTE":           "Hardel + Le Bihan Architectes",
    "BET Acoustique":       "AVLS",
    "BET Ascenseur":        "BET Ascenseur",
    "BET CVC":              "BET CVC",
    "BET Electricité":      "BET Electricité",
    "BET EV":               "BET EV",
    "BET Façade":           "BET Façade",
    "BET Plomberie":        "BET Plomberie",
    "BET POL":              "BET POL",
    "BET SPK":              "BET SPK",
    "BET Structure":        "Terrell",
    "BET VRD":              "BET VRD",
    "Bureau de Contrôle":   "SOCOTEC",
    "Maître d'Oeuvre EXE":  "GEMO",
    "MOEX SAS":             "GEMO (SAS)",
}


# ─────────────────────────────────────────────────────────────
# SPECIAL CASES
# Three identifiers with non-standard behaviour.
# ─────────────────────────────────────────────────────────────
SPECIAL_CASES: dict[str, str] = {
    # Conformity gate column. Present in GED but not a consultant.
    # Exclude from all consultant response processing.
    "0-SAS": "conformity_gate",

    # Uses a different status vocabulary: FAV / SUS / DEF
    # instead of the standard VSO / VAO / REF.
    "Bureau de Contrôle": "non_standard_status_vocab",

    # The SAS role for GEMO. Its responses live in the "0-SAS" column.
    # Must never be merged with "Maître d'Oeuvre EXE".
    "MOEX SAS": "sas_only_consultant",
}
