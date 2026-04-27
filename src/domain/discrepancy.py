"""
src/domain/discrepancy.py
-------------------------
Pure discrepancy classification helpers extracted from main.py.

Every function here is a pure helper: no globals, no file writes, no external state mutation.
"""


def classify_discrepancy(record: dict) -> str:
    """
    Part 6 / Patch E: Unified severity classification.

    REVIEW_REQUIRED — operational truth affected; human must act
    COSMETIC        — values differ but meaning is equivalent
    INFO            — non-blocking observation (historical rows, minor diffs)
    EXCLUDED        — excluded population (traceability only)
    """
    flag_type = record.get("flag_type", "")
    is_excluded = record.get("is_excluded_population", False)

    if is_excluded:
        return "EXCLUDED"

    # ── Final pass: BENTIN legacy exceptions ─────────────────
    if flag_type == "BENTIN_LEGACY_EXCEPTION":
        return "EXCLUDED"

    # ── Hard REVIEW_REQUIRED ──────────────────────────────────
    if flag_type == "SHEET_MISMATCH":
        return "REVIEW_REQUIRED"

    # ── Part 1: INDICE_MISMATCH is no longer blocking ────────
    # Identity is confirmed by emetteur/lot match; indice differences are cosmetic.
    if flag_type == "INDICE_MISMATCH":
        return "INFO"

    # Legacy flat types (backward compat — should not appear after Patch E)
    if flag_type in ("MISSING_IN_GF", "MISSING_IN_GED"):
        return "REVIEW_REQUIRED"

    # ── MISSING_IN_GF subtypes (Part 5 / Patch E) ────────────
    if flag_type == "MISSING_IN_GF_TRUE":
        return "REVIEW_REQUIRED"
    if flag_type == "MISSING_IN_GF_SAME_KEY_COLLISION":
        return "REVIEW_REQUIRED"
    if flag_type in (
        "MISSING_IN_GF_PENDING_SAS",
        "MISSING_IN_GF_RECENT_SAS_REMINDER",
        "MISSING_IN_GF_RECENT_REFUSAL",
        "MISSING_IN_GF_RECENT_ACCEPTED_SAS",
        "MISSING_IN_GF_AMBIGUOUS",
    ):
        return "INFO"

    # ── MISSING_IN_GED subtypes (Part 4 / Patch E) ────────────
    if flag_type == "MISSING_IN_GED_TRUE":
        return "REVIEW_REQUIRED"
    if flag_type == "MISSING_IN_GED_FAMILY_MATCH_MISSED":
        return "REVIEW_REQUIRED"
    if flag_type in (
        "MISSING_IN_GED_HISTORICAL",
        "MISSING_IN_GED_GF_SAS_REF",
        "MISSING_IN_GED_GF_DUPLICATE_ROW",
        "MISSING_IN_GED_EXCLUDED",
        "MISSING_IN_GED_AMBIGUOUS",
    ):
        return "INFO"

    # ── Reconciliation subtypes (Patch F — numero-based) ─────
    if flag_type == "MISSING_IN_GED_HISTORICAL":
        return "INFO"
    if flag_type in (
        "MISSING_IN_GED_RECONCILED_BY_FUZZY",
        "MISSING_IN_GF_RECONCILED_BY_FUZZY",
    ):
        return "INFO"
    if flag_type in (
        "MISSING_IN_GED_POSSIBLE_NUMERO_ERROR",
        "MISSING_IN_GF_POSSIBLE_NUMERO_ERROR",
    ):
        return "REVIEW_REQUIRED"
    if flag_type in (
        "MISSING_IN_GED_POSSIBLE_TITLE_VARIANT",
        "MISSING_IN_GF_POSSIBLE_TITLE_VARIANT",
    ):
        return "REVIEW_REQUIRED"
    if flag_type in (
        "MISSING_IN_GED_AMBIGUOUS_RECONCILIATION",
        "MISSING_IN_GF_AMBIGUOUS_RECONCILIATION",
    ):
        return "REVIEW_REQUIRED"

    # ── Reconciliation subtypes (Patch G — title-first) ──────
    # Confirmed GF numero typo: same document, emetteur, title, indice — only numero differs
    if flag_type in (
        "MISSING_IN_GED_GF_NUMERO_TYPO_CONFIRMED",
        "MISSING_IN_GF_GF_NUMERO_TYPO",
    ):
        return "INFO"   # GED is truth; GF had a typo — not a real missing
    # Reconciled by title (routing mismatch or naming variant)
    if flag_type in (
        "MISSING_IN_GED_RECONCILED_BY_TITLE",
        "MISSING_IN_GF_RECONCILED_BY_TITLE",
    ):
        return "INFO"
    # Ambiguous title match — needs human check but not REVIEW_REQUIRED urgency
    if flag_type in (
        "MISSING_IN_GED_AMBIGUOUS_TITLE_MATCH",
        "MISSING_IN_GF_AMBIGUOUS_TITLE_MATCH",
    ):
        return "REVIEW_REQUIRED"

    # ── Patch C: title variant accepted (TITRE_MISMATCH relaxed) ──
    if flag_type == "TITRE_VARIANT_ACCEPTED":
        return "INFO"

    # ── Patch D: indice variant accepted for reconstruction ──────
    if flag_type == "INDICE_VARIANT_ACCEPTED_BY_GED":
        return "COSMETIC"

    # ── Other INFO types ──────────────────────────────────────
    if flag_type == "DUPLICATE_ACTIVE_IN_GF":
        return "INFO"

    # ── Part 1: TITRE_MISMATCH is no longer blocking ────────────
    # Title is not a reliable identifier; emetteur+lot+numero confirm identity.
    # Kept in logs for traceability but downgraded from REVIEW_REQUIRED.
    if flag_type == "TITRE_MISMATCH":
        return "INFO"

    # ── Part 4: DATE_MISMATCH is no longer blocking ─────────────
    # Date cannot be trusted as a matching field; title determines identity.
    # Remove from REVIEW_REQUIRED; keep as INFO for traceability.
    if flag_type == "DATE_MISMATCH":
        return "INFO"

    return "INFO"


def _is_excluded_sheet_for_discrepancy(
    sheet_name: str,
    excluded_sheets: set,
    sheet_year_filters: dict,
) -> bool:
    """
    Patch C: Return True if an entire sheet should be skipped in discrepancy.
    We skip fully excluded sheets and let year-filtered sheets pass through
    (they are handled at document level).
    """
    return sheet_name in excluded_sheets
