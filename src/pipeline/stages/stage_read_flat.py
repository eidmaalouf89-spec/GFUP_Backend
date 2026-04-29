"""
stage_read_flat — Read FLAT_GED.xlsx and adapt into pipeline-compatible structures.

Step 4 — Flat GED Adapter (Feature Flag)
Activated when FLAT_GED_MODE = 'flat' in the pipeline namespace.

This stage replaces stage_read when mode='flat'. It consumes FLAT_GED.xlsx
(sheets: GED_RAW_FLAT, GED_OPERATIONS) and reconstructs docs_df and responses_df
in the same shape that stage_read produces, so that stage_normalize and all
downstream stages can run unchanged.

Semantic rules follow BACKEND_SEMANTIC_CONTRACT.md §3–4 strictly.

Key design decisions:
  - Decision 1: filter to instance_role=ACTIVE (already enforced by GED_OPERATIONS)
  - Decision 2: responsible_party synthesised here using is_blocking (not is_completed==False)
  - Decision 3: SAS RAPPEL+pre-2026 filter reproduced before building docs_df/responses_df
  - Decision 4: lateness from phase_deadline/data_date; RAPPEL granularity limited (see map)
  - Decision 5: visa_global verified per three points; SAS REF gap documented
  - Decision 6: delay fields read from flat GED directly — no recomputation

━━━ TEMPORARY_COMPAT_LAYER (see FLAT_GED_ADAPTER_MAP.md §8) ━━━━━━━━━━━━━━━━━━
  The responses_df construction fakes legacy response_date_raw strings
  ("En attente visa ...", "Rappel : ...") so that the still-running
  normalize_responses() → interpret_date_field() pipeline produces the
  correct date_status_type.  This is backward engineering: flat GED → fake
  raw text → re-parsed.  It works, but it re-enters the fragile text-parsing
  layer we wanted to escape.

  REMOVAL PLAN: When stage_normalize is updated for flat mode (Step 8 /
  clean_GF reconstruction), this compat layer must be replaced by injecting
  date_status_type, date_limite, and date_reponse directly.  At that point,
  response_date_raw can be dropped from the flat responses_df entirely.
  The flat_* pass-through columns are already the clean layer to build on.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━ VISA GLOBAL — AUTHORITATIVE SOURCE RULE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  In flat mode, visa_global MUST be read from ctx.flat_ged_doc_meta, NOT
  from WorkflowEngine.compute_visa_global_with_date().  The engine path
  silently returns (None, None) for SAS REF documents.

  Use: get_visa_global(ctx, doc_id, engine) — exported from this module.
  It enforces the rule automatically based on ctx.flat_ged_mode.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Outputs added to ctx beyond the standard stage_read contract:
  - ctx.flat_ged_mode    : "flat" (set here; "raw" when stage_read runs)
  - ctx.flat_ged_ops_df  : raw GED_OPERATIONS DataFrame (for parity harness, Step 5)
  - ctx.flat_ged_doc_meta: per-doc {closure_mode, visa_global, responsible_party, data_date}
"""

import logging
import uuid
from pathlib import Path

import pandas as pd

from normalize import load_mapping
from pipeline.utils import _safe_console_print

_LOG = logging.getLogger(__name__)

# ── Sheet names (FLAT_GED_CONTRACT.md §1) ─────────────────────
_SHEET_RAW = "GED_RAW_FLAT"
_SHEET_OPS = "GED_OPERATIONS"

# ── Pending text templates (used to reconstruct response_date_raw) ──
# normalize_responses() reads these strings back via interpret_date_field()
_RAPPEL_PREFIX = "Rappel : En attente visa"
_EN_ATTENTE_PREFIX = "En attente visa"

# ── Boolean column names in both sheets ───────────────────────
_BOOL_COLS = ("is_completed", "is_blocking", "is_sas", "requires_new_cycle")


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────

def get_visa_global(ctx, doc_id: str, engine=None) -> tuple:
    """
    Authoritative visa_global accessor — enforces the flat mode rule.

    In flat mode  → returns (visa_global, visa_date) from ctx.flat_ged_doc_meta.
                    WorkflowEngine result is NOT used (split-brain rule).
    In raw mode   → delegates to engine.compute_visa_global_with_date(doc_id).

    Usage in any downstream stage:
        from pipeline.stages.stage_read_flat import get_visa_global
        visa, date = get_visa_global(ctx, doc_id, ctx.wf_engine)

    This is the single authoritative call site for visa_global in flat mode.
    Replaces direct calls to engine.compute_visa_global_with_date() when
    ctx.flat_ged_mode == 'flat'.
    """
    if getattr(ctx, "flat_ged_mode", "raw") == "flat":
        meta = (ctx.flat_ged_doc_meta or {}).get(doc_id, {})
        visa  = meta.get("visa_global")
        # date is not pre-computed by the adapter (not needed for Phase 2 parity);
        # return None for date — downstream that needs the date must handle this.
        return visa, None
    # Raw mode: delegate to engine
    if engine is None:
        raise ValueError("engine must be provided in raw mode")
    return engine.compute_visa_global_with_date(doc_id)


def stage_read_flat(ctx, log):
    """
    Read FLAT_GED.xlsx and produce pipeline-compatible docs_df and responses_df.

    Context reads:
      - ctx.FLAT_GED_FILE   path to FLAT_GED.xlsx

    Context writes (standard, same as stage_read):
      - ctx.docs_df
      - ctx.responses_df
      - ctx.ged_approver_names
      - ctx.mapping

    Context writes (flat mode extras):
      - ctx.flat_ged_ops_df    raw GED_OPERATIONS DataFrame
      - ctx.flat_ged_doc_meta  per-doc dict with closure_mode / visa_global /
                               responsible_party / data_date
    """
    _safe_console_print("\n[1/7] Reading FLAT_GED (flat mode)...")

    flat_path = Path(ctx.FLAT_GED_FILE)
    if not flat_path.exists():
        raise FileNotFoundError(f"FLAT_GED file not found: {flat_path}")

    # ── Load sheets ────────────────────────────────────────────
    raw_df = pd.read_excel(flat_path, sheet_name=_SHEET_RAW, dtype=str)
    ops_df = pd.read_excel(flat_path, sheet_name=_SHEET_OPS, dtype=str)

    _normalise_bool_cols(raw_df)
    _normalise_bool_cols(ops_df)

    for df in (raw_df, ops_df):
        df["numero"] = df["numero"].astype(str).str.strip()
        df["indice"] = df["indice"].astype(str).str.strip()

    log(f"[flat] GED_RAW_FLAT : {len(raw_df)} rows")
    log(f"[flat] GED_OPERATIONS: {len(ops_df)} rows")

    # ── Decision 3 — SAS filter (RAPPEL proxy + pre-2026) ─────
    # Exclude docs where SAS step is PENDING_LATE in GED_RAW_FLAT AND
    # submittal_date year < 2026.  This reproduces _apply_sas_filter() in
    # sas_helpers.py for Phase 2 parity (BACKEND_SEMANTIC_CONTRACT §4 Decision 3).
    ops_df, raw_df, sas_excluded = _apply_sas_filter_flat(ops_df, raw_df)
    log(f"[flat] SAS filter (RAPPEL proxy + pre-2026): {sas_excluded} docs excluded")

    # ── Decision 1 — ACTIVE instances ─────────────────────────
    # GED_OPERATIONS already reflects only ACTIVE instances (FLAT_GED_CONTRACT §Known Limitation).
    # No additional filter needed; confirm count.
    doc_codes_df = (
        ops_df[["numero", "indice"]].drop_duplicates().reset_index(drop=True)
    )
    log(f"[flat] Active docs after SAS filter: {len(doc_codes_df)}")

    # ── Assign stable doc_id per (numero, indice) ──────────────
    doc_code_to_id: dict[tuple, str] = {
        (r["numero"], r["indice"]): str(uuid.uuid4())
        for _, r in doc_codes_df.iterrows()
    }
    # Reverse map for convenience
    id_to_pair: dict[str, tuple] = {v: k for k, v in doc_code_to_id.items()}

    # ── Compute per-doc semantics ──────────────────────────────
    flat_ged_doc_meta = _compute_doc_meta(ops_df, doc_code_to_id)

    _log_closure_distribution(flat_ged_doc_meta, log)

    # ── Reconstruct docs_df ────────────────────────────────────
    docs_df = _build_docs_df(ops_df, doc_code_to_id)
    log(f"[flat] docs_df: {len(docs_df)} rows")

    # ── Reconstruct responses_df ───────────────────────────────
    responses_df = _build_responses_df(ops_df, raw_df, doc_code_to_id)
    log(f"[flat] responses_df: {len(responses_df)} rows (OPEN_DOC excluded)")

    # ── Approver names + hardcoded mapping ────────────────────
    ged_approver_names = ops_df["actor_raw"].dropna().unique().tolist()
    mapping = load_mapping()
    log(f"[flat] Approvers discovered : {len(ged_approver_names)}")
    log(f"[flat] Mapping entries      : {len(mapping)} (hardcoded)")

    # ── Write to context ───────────────────────────────────────
    ctx.docs_df              = docs_df
    ctx.responses_df         = responses_df
    ctx.ged_approver_names   = ged_approver_names
    ctx.mapping              = mapping
    ctx.flat_ged_mode        = "flat"          # authoritative mode marker
    ctx.flat_ged_ops_df      = ops_df
    ctx.flat_ged_doc_meta    = flat_ged_doc_meta


# ─────────────────────────────────────────────────────────────
# FILTER — SAS RAPPEL + PRE-2026 (Decision 3)
# ─────────────────────────────────────────────────────────────

def _apply_sas_filter_flat(
    ops_df: pd.DataFrame,
    raw_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """
    Exclude (numero, indice) pairs where:
      - SAS step is PENDING_LATE in GED_RAW_FLAT  (RAPPEL proxy, Concept 7G)
      - AND submittal_date year < 2026

    Returns (ops_filtered, raw_filtered, excluded_count).
    """
    # Identify SAS rows in GED_RAW_FLAT with PENDING_LATE
    if "is_sas" in raw_df.columns:
        sas_raw = raw_df[raw_df["is_sas"] == True].copy()
    else:
        # Fallback: identify by approver_raw (should not normally happen)
        sas_raw = raw_df[raw_df.get("approver_raw", pd.Series(dtype=str)) == "0-SAS"].copy()

    rappel_pairs: set[tuple] = set(
        zip(
            sas_raw.loc[sas_raw["date_status_type"] == "PENDING_LATE", "numero"],
            sas_raw.loc[sas_raw["date_status_type"] == "PENDING_LATE", "indice"],
        )
    )

    if not rappel_pairs:
        return ops_df, raw_df, 0

    # Cross with submittal_date < 2026 (from OPEN_DOC rows in GED_OPERATIONS)
    open_doc = ops_df[ops_df["step_type"] == "OPEN_DOC"][
        ["numero", "indice", "submittal_date"]
    ].copy()
    open_doc["_year"] = pd.to_datetime(
        open_doc["submittal_date"], errors="coerce"
    ).dt.year

    # Vectorized: build key column, filter in one pass — replaces iterrows loop
    rappel_keys = {f"{n}|{i}" for n, i in rappel_pairs}
    open_doc["_key"] = (
        open_doc["numero"].astype(str).str.strip()
        + "|"
        + open_doc["indice"].astype(str).str.strip()
    )
    excl_mask = (
        open_doc["_key"].isin(rappel_keys)
        & open_doc["_year"].notna()
        & (open_doc["_year"].astype(float) < 2026)
    )
    excl_sub = open_doc.loc[excl_mask]
    exclude_pairs: set[tuple] = set(
        zip(
            excl_sub["numero"].astype(str).str.strip(),
            excl_sub["indice"].astype(str).str.strip(),
        )
    )

    if not exclude_pairs:
        return ops_df, raw_df, 0

    # Vectorized exclusion filter — replaces df.apply row-by-row
    excl_keys = {f"{n}|{i}" for n, i in exclude_pairs}

    def _not_excluded(df: pd.DataFrame) -> pd.Series:
        keys = (
            df["numero"].astype(str).str.strip()
            + "|"
            + df["indice"].astype(str).str.strip()
        )
        return ~keys.isin(excl_keys)

    ops_out = ops_df[_not_excluded(ops_df)].copy().reset_index(drop=True)
    raw_out = raw_df[_not_excluded(raw_df)].copy().reset_index(drop=True)
    return ops_out, raw_out, len(exclude_pairs)


# ─────────────────────────────────────────────────────────────
# PER-DOC SEMANTICS
# ─────────────────────────────────────────────────────────────

def _compute_doc_meta(
    ops_df: pd.DataFrame,
    doc_code_to_id: dict[tuple, str],
) -> dict[str, dict]:
    """
    For every (numero, indice) compute:
      - closure_mode     : MOEX_VISA | ALL_RESPONDED_NO_MOEX | WAITING_RESPONSES
      - visa_global      : str | None  (MOEX visa or SAS REF)
      - responsible_party: str | None  (5-rule synthesis, Decision 2)
      - data_date        : ISO date string

    Returns {doc_id: {...}}.
    """
    result: dict[str, dict] = {}

    # Group ops_df once by (numero, indice) for efficiency
    grouped = ops_df.groupby(["numero", "indice"], sort=False)

    for (numero, indice), doc_ops in grouped:
        doc_id = doc_code_to_id.get((str(numero).strip(), str(indice).strip()))
        if doc_id is None:
            continue

        moex_rows  = doc_ops[doc_ops["step_type"] == "MOEX"]
        sas_rows   = doc_ops[doc_ops["step_type"] == "SAS"]
        cons_rows  = doc_ops[doc_ops["step_type"] == "CONSULTANT"]
        sas_cons   = doc_ops[doc_ops["step_type"].isin(["SAS", "CONSULTANT"])]

        closure    = _derive_closure_mode(moex_rows, sas_cons)
        visa       = _derive_visa_global(moex_rows, sas_rows)
        responsible = _derive_responsible_party(visa, cons_rows)

        data_date = ""
        if not doc_ops.empty:
            data_date = str(doc_ops.iloc[0].get("data_date", "")).strip()

        result[doc_id] = {
            "closure_mode":      closure,
            "visa_global":       visa,
            "responsible_party": responsible,
            "data_date":         data_date,
        }

    return result


def _derive_closure_mode(
    moex_rows: pd.DataFrame,
    sas_cons_rows: pd.DataFrame,
) -> str:
    """
    FLAT_GED_CONTRACT.md §8 Rule 7 / BACKEND_SEMANTIC_CONTRACT Concept 3.

    MOEX_VISA           : MOEX step exists, is_completed=True, response_date non-empty
    ALL_RESPONDED_NO_MOEX: no MOEX row, all SAS+CONSULTANT rows is_completed=True
    WAITING_RESPONSES   : neither condition met
    """
    if not moex_rows.empty:
        mr = moex_rows.iloc[0]
        if (
            mr.get("is_completed") is True
            and str(mr.get("response_date", "")).strip()
        ):
            return "MOEX_VISA"

    if moex_rows.empty and not sas_cons_rows.empty:
        if sas_cons_rows["is_completed"].eq(True).all():
            return "ALL_RESPONDED_NO_MOEX"

    return "WAITING_RESPONSES"


def _derive_visa_global(
    moex_rows: pd.DataFrame,
    sas_rows: pd.DataFrame,
) -> str | None:
    """
    Concept 4 — VISA GLOBAL (BACKEND_SEMANTIC_CONTRACT).

    Source: exclusively the MOEX step (step_type=MOEX).
    SAS REF: if SAS step answered with REF and there is no MOEX step.

    Verification points (documented in FLAT_GED_ADAPTER_MAP.md):
      VP-1: SAS REF distinguished via SAS step status_clean=REF + no MOEX.
            NOTE: the workflow_engine's compute_visa_global_with_date() will return
            (None, None) for SAS REF docs because it finds no MOEX entry in
            responses_df. The pre-computed value in flat_ged_doc_meta is the
            correct source. Downstream stages consuming the engine output must be
            updated for flat mode — KNOWN_GAP, deferred to Step 8.
      VP-2: SAS-only approvals (status ending "-SAS") correctly excluded.
      VP-3: Canonical MOEX name match — actor_raw from GED_OPERATIONS is used as
            approver_raw; the hardcoded mapping maps it to "Maître d'Oeuvre EXE"
            which satisfies _is_moex() in workflow_engine.py. VERIFIED.
    """
    # Primary: MOEX step
    if not moex_rows.empty:
        mr = moex_rows.iloc[0]
        if (
            mr.get("is_completed") is True
            and str(mr.get("response_date", "")).strip()
        ):
            status = str(mr.get("status_clean", "")).strip()
            if status.endswith("-SAS"):
                return None  # SAS-only approval — not final MOEX visa (VP-2)
            if status:
                return status

    # SAS REF fallback: SAS answered with REF and no MOEX step existed (VP-1)
    if moex_rows.empty and not sas_rows.empty:
        sr = sas_rows.iloc[0]
        if (
            sr.get("is_completed") is True
            and str(sr.get("status_clean", "")).strip() == "REF"
        ):
            return "SAS REF"

    return None


def _derive_responsible_party(
    visa: str | None,
    cons_rows: pd.DataFrame,
) -> str | None:
    """
    Concept 5 / Decision 2 — 5-rule responsible party.
    Uses is_blocking from flat GED, NOT is_completed==False.
    BACKEND_SEMANTIC_CONTRACT §3 Concept 5D.

    Rules (applied in order):
      1. visa == REF          → CONTRACTOR
      2. visa == SAS REF      → CONTRACTOR
      3. blocking consultants → name or MULTIPLE_CONSULTANTS
      4. no blocking + no visa → MOEX
      5. no blocking + visa    → None (closed)
    """
    # Rules 1 + 2
    if visa in ("REF", "SAS REF"):
        return "CONTRACTOR"

    # Rule 3: consultants where is_blocking=True
    blocking = cons_rows[cons_rows["is_blocking"] == True]
    if not blocking.empty:
        if len(blocking) == 1:
            name = str(blocking.iloc[0].get("actor_clean", "")).strip()
            return name if name else "UNKNOWN"
        return "MULTIPLE_CONSULTANTS"

    # Rule 4
    if visa is None:
        return "MOEX"

    # Rule 5
    return None


# ─────────────────────────────────────────────────────────────
# BUILD docs_df
# ─────────────────────────────────────────────────────────────

def _build_docs_df(
    ops_df: pd.DataFrame,
    doc_code_to_id: dict[tuple, str],
) -> pd.DataFrame:
    """
    Reconstruct docs_df (one row per document) from OPEN_DOC rows.

    Produces the same schema that stage_read / read_raw.read_ged() produces,
    so that normalize_docs() and VersionEngine can run unchanged.

    Fields not in flat GED (type_de_doc, zone, niveau, affaire, …) are set to
    None.  VersionEngine gracefully handles None for grouping columns.
    """
    open_docs = ops_df[ops_df["step_type"] == "OPEN_DOC"].copy()

    # Vectorized doc_id assignment via key map — replaces iterrows loop
    id_map = {f"{n}|{i}": v for (n, i), v in doc_code_to_id.items()}
    open_docs["_key"] = (
        open_docs["numero"].astype(str).str.strip()
        + "|"
        + open_docs["indice"].astype(str).str.strip()
    )
    open_docs["doc_id"] = open_docs["_key"].map(id_map)
    open_docs = open_docs[open_docs["doc_id"].notna()].copy()

    return pd.DataFrame({
        "doc_id":              open_docs["doc_id"].values,
        "numero":              open_docs["numero"].astype(str).str.strip().values,
        "indice":              open_docs["indice"].astype(str).str.strip().values,
        "lot":                 open_docs["lot"].fillna("").astype(str).values       if "lot"      in open_docs.columns else "",
        "emetteur":            open_docs["emetteur"].fillna("").astype(str).values  if "emetteur" in open_docs.columns else "",
        # libelle_du_document: VersionEngine reads this field name
        "libelle_du_document": open_docs["titre"].fillna("").astype(str).values     if "titre"    in open_docs.columns else "",
        # cree_le: normalize_docs creates created_at from this
        "cree_le":             pd.to_datetime(
                                   open_docs["submittal_date"].astype(str).str.strip()
                                   if "submittal_date" in open_docs.columns else pd.Series(dtype=str),
                                   errors="coerce",
                               ).values,
        # Reference date (BACKEND_SEMANTIC_CONTRACT Concept 6D)
        "data_date":           open_docs["data_date"].fillna("").astype(str).values if "data_date" in open_docs.columns else "",
        # Fields absent from flat GED — None; VersionEngine handles gracefully
        "type_de_doc": None, "zone": None, "niveau": None, "affaire": None,
        "projet":      None, "batiment": None, "phase": None, "specialite": None,
    }).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# BUILD responses_df
# ─────────────────────────────────────────────────────────────

def _build_responses_df(
    ops_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    doc_code_to_id: dict[tuple, str],
) -> pd.DataFrame:
    """
    Reconstruct responses_df (one row per step, excluding OPEN_DOC).

    The response_date_raw field is reconstructed from flat GED semantics so that
    normalize_responses() → interpret_date_field() produces the correct date_status_type:

      is_completed=True                   → response_date_raw = pd.Timestamp(response_date)
                                            → date_status_type = ANSWERED
      is_blocking=True, retard=RETARD     → "Rappel : En attente visa (YYYY/MM/DD)"
                                            → date_status_type = PENDING_LATE
      is_blocking=True, retard≠RETARD     → "En attente visa (YYYY/MM/DD)"
                                            → date_status_type = PENDING_IN_DELAY
      is_blocking=False, is_completed=False → None
                                            → date_status_type = NOT_CALLED
                                            (post-MOEX de-flagged consultants, Concept 2)

    For SAS rows specifically:
      - approver_raw is forced to "0-SAS" so _apply_sas_filter() in stage_normalize
        can find it (sas_helpers._apply_sas_filter checks approver_raw == "0-SAS").
      - RAPPEL proxy: uses date_status_type from GED_RAW_FLAT (is_sas=True rows)
        rather than retard_avance_status, per Concept 7G.

    Extra flat_* columns are appended for parity harness use (Step 5) and are
    ignored by all legacy stage functions.
    """
    # Build SAS RAPPEL proxy lookup from GED_RAW_FLAT (vectorized)
    # key: "numero|indice" → "PENDING_LATE" | "PENDING_IN_DELAY" | "ANSWERED" | ""
    sas_dst_lookup: dict[str, str] = {}
    if "is_sas" in raw_df.columns:
        sas_raw = raw_df[raw_df["is_sas"] == True].copy()
        if not sas_raw.empty:
            sas_raw["_key"] = (
                sas_raw["numero"].astype(str).str.strip()
                + "|"
                + sas_raw["indice"].astype(str).str.strip()
            )
            sas_dst_lookup = (
                sas_raw.set_index("_key")["date_status_type"]
                .astype(str).str.strip().to_dict()
            )

    # Only process non-OPEN_DOC rows
    step_rows = ops_df[ops_df["step_type"] != "OPEN_DOC"].copy()

    # ── Vectorized doc_id assignment ──────────────────────────────────────────
    id_map = {f"{n}|{i}": v for (n, i), v in doc_code_to_id.items()}
    step_rows["_key"] = (
        step_rows["numero"].astype(str).str.strip()
        + "|"
        + step_rows["indice"].astype(str).str.strip()
    )
    step_rows["doc_id"] = step_rows["_key"].map(id_map)
    step_rows = step_rows[step_rows["doc_id"].notna()].copy()

    if step_rows.empty:
        return pd.DataFrame()

    # ── Normalise string columns once ─────────────────────────────────────────
    def _col(df, name, default=""):
        return df[name].fillna(default).astype(str).str.strip() if name in df.columns \
               else pd.Series(default, index=df.index)

    step_type     = _col(step_rows, "step_type")
    retard_status = _col(step_rows, "retard_avance_status")
    phase_dl      = _col(step_rows, "phase_deadline")
    resp_date     = _col(step_rows, "response_date")
    actor_raw     = _col(step_rows, "actor_raw")

    is_completed = step_rows["is_completed"] == True
    is_blocking  = step_rows["is_blocking"]  == True

    # approver_raw: "0-SAS" for SAS steps, else actor_raw
    import numpy as np
    approver_raw = np.where(step_type == "SAS", "0-SAS", actor_raw)

    # ── TEMPORARY_COMPAT_LAYER — vectorized ───────────────────────────────────
    # Reconstruct response_date_raw strings expected by normalize_responses().
    # See removal plan in module docstring (Step 8).
    deadline_fmt = phase_dl.str.replace("-", "/", regex=False)

    # SAS RAPPEL proxy: lookup sas_dst_lookup by key
    sas_is_rappel = step_rows["_key"].map(sas_dst_lookup).fillna("") == "PENDING_LATE"
    non_sas_rappel = retard_status == "RETARD"
    is_rappel = np.where(step_type == "SAS", sas_is_rappel, non_sas_rappel)

    rappel_str = np.where(
        deadline_fmt != "",
        _RAPPEL_PREFIX + " (" + deadline_fmt + ")",
        _RAPPEL_PREFIX,
    )
    en_attente_str = np.where(
        deadline_fmt != "",
        _EN_ATTENTE_PREFIX + " (" + deadline_fmt + ")",
        _EN_ATTENTE_PREFIX,
    )

    # Build response_date_raw as object array (Timestamp | str | None)
    rdraw = pd.array([None] * len(step_rows), dtype=object)
    comp_idx  = is_completed.values
    block_idx = (~is_completed & is_blocking).values
    rdraw[comp_idx] = pd.to_datetime(
        resp_date[is_completed], errors="coerce"
    ).values
    rdraw[block_idx] = np.where(
        is_rappel[block_idx], rappel_str[block_idx], en_attente_str[block_idx]
    )
    # ── End TEMPORARY_COMPAT_LAYER ────────────────────────────────────────────

    # response_status_raw: prefer status_raw, fall back to status_clean
    status_raw_col   = _col(step_rows, "status_raw")
    status_clean_col = _col(step_rows, "status_clean")
    response_status_raw = np.where(
        status_raw_col != "", status_raw_col,
        np.where(status_clean_col != "", status_clean_col, None),
    )

    # pj_flag: vectorized safe-int
    if "pj_flag" in step_rows.columns:
        pj_flag = pd.to_numeric(step_rows["pj_flag"], errors="coerce").fillna(0).astype(int).values
    else:
        pj_flag = np.zeros(len(step_rows), dtype=int)

    def _int_col(name):
        if name not in step_rows.columns:
            return np.zeros(len(step_rows), dtype=int)
        return pd.to_numeric(step_rows[name], errors="coerce").fillna(0).astype(int).values

    return pd.DataFrame({
        # ── Standard stage_read schema ────────────────────────────────────────
        "doc_id":              step_rows["doc_id"].values,
        "approver_raw":        approver_raw,
        "response_date_raw":   rdraw,
        "response_status_raw": response_status_raw,
        "response_comment":    _col(step_rows, "observation").values,
        "pj_flag":             pj_flag,
        # ── Flat GED pass-through (parity harness, Step 5) ───────────────────
        "flat_is_blocking":             is_blocking.values,
        "flat_is_completed":            is_completed.values,
        "flat_step_type":               step_type.values,
        "flat_actor_clean":             _col(step_rows, "actor_clean").values,
        "flat_phase_deadline":          phase_dl.values,
        "flat_retard_avance_status":    retard_status.values,
        "flat_step_delay_days":         _int_col("step_delay_days"),
        "flat_delay_contribution_days": _int_col("delay_contribution_days"),
        "flat_cumulative_delay_days":   _int_col("cumulative_delay_days"),
        "flat_delay_actor":             _col(step_rows, "delay_actor").values,
        "flat_data_date":               _col(step_rows, "data_date").values,
    })


# ─────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────

def _normalise_bool_cols(df: pd.DataFrame) -> None:
    """Convert string "True"/"False" cells to Python bool in place."""
    for col in _BOOL_COLS:
        if col in df.columns:
            df[col] = df[col].map(
                {"True": True, "False": False, True: True, False: False}
            ).fillna(False)


def _safe_int(val, default: int = 0) -> int:
    """Convert val to int; return default on failure."""
    if val is None:
        return default
    s = str(val).strip()
    if s in ("", "nan", "None", "NaN"):
        return default
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _log_closure_distribution(doc_meta: dict, log) -> None:
    modes = [v["closure_mode"] for v in doc_meta.values()]
    log(
        f"[flat] Closure — "
        f"MOEX_VISA: {modes.count('MOEX_VISA')}, "
        f"ALL_RESPONDED_NO_MOEX: {modes.count('ALL_RESPONDED_NO_MOEX')}, "
        f"WAITING_RESPONSES: {modes.count('WAITING_RESPONSES')}"
    )
