"""
chain_timeline_attribution.py -- Per-chain timing + responsibility breakdown

Reads chain_onion CSV outputs (CHAIN_EVENTS, CHAIN_REGISTER, CHAIN_VERSIONS)
and produces a structured timeline for every document chain.

Cap-application rule (Phase 1 finding):
    chain_onion's delay_contribution_days for SECONDARY_CONSULTANT rows is NOT
    capped at SECONDARY_WINDOW_DAYS=10. This module applies the cap itself.
    Excess delay is re-attributed to synthetic MOEX rows ("MOEX_CAP_REATTRIBUTED").
    The original chain_onion CSV is never modified.

Outputs (disk-only, NOT registered in run_memory.db):
    output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.json
    output/intermediate/CHAIN_TIMELINE_ATTRIBUTION.csv
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

CYCLE_REVIEW_DAYS = 30
CYCLE_REWORK_DAYS = 15
CHAIN_LONG_THRESHOLD_DAYS = 120
SECONDARY_WINDOW_DAYS = 10

_JSON_FILENAME = "CHAIN_TIMELINE_ATTRIBUTION.json"
_CSV_FILENAME = "CHAIN_TIMELINE_ATTRIBUTION.csv"

_ACTOR_TYPE_TIER = {
    "PRIMARY_CONSULTANT": "PRIMARY",
    "SECONDARY_CONSULTANT": "SECONDARY",
    "MOEX": "MOEX",
    "SAS": "SAS",
    "CONTRACTOR": "CONTRACTOR",
    "SYSTEM": "SYSTEM",
}

_MOEX_REF_STEP_TYPES = {"CYCLE_REQUIRED"}
_MOEX_REF_STATUSES = {"REF"}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_event_date(val) -> Optional[date]:
    """Parse an event_date cell (ISO string or NaN) to datetime.date or None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:10]).date()
    except ValueError:
        return None


def _load_chain_data(
    chain_onion_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load CHAIN_EVENTS, CHAIN_REGISTER, CHAIN_VERSIONS from chain_onion_dir."""
    str_cols = {
        "family_key": str, "version_key": str,
        "instance_key": str, "numero": str,
    }
    for name in ("CHAIN_EVENTS.csv", "CHAIN_REGISTER.csv", "CHAIN_VERSIONS.csv"):
        p = chain_onion_dir / name
        if not p.exists():
            raise FileNotFoundError(
                f"Phase 2 cannot start -- {p} is missing. "
                "Please run `python run_chain_onion.py` and retry."
            )
    events = pd.read_csv(chain_onion_dir / "CHAIN_EVENTS.csv", dtype=str_cols)
    register = pd.read_csv(chain_onion_dir / "CHAIN_REGISTER.csv", dtype=str_cols)
    versions = pd.read_csv(chain_onion_dir / "CHAIN_VERSIONS.csv", dtype=str_cols)
    return events, register, versions


def _compute_last_primary_date_per_version(
    chain_events_df: pd.DataFrame,
) -> dict[str, Optional[date]]:
    """Return {version_key: last_completed_primary_date} for every version."""
    primary_mask = (
        (chain_events_df["actor_type"] == "PRIMARY_CONSULTANT")
        & (chain_events_df["is_completed"].astype(str).str.lower() == "true")
    )
    primary_rows = chain_events_df[primary_mask].copy()
    primary_rows["_pd"] = primary_rows["event_date"].apply(_parse_event_date)
    primary_rows = primary_rows[primary_rows["_pd"].notna()]

    result: dict[str, Optional[date]] = {}
    for vk, grp in primary_rows.groupby("version_key"):
        result[vk] = grp["_pd"].max()
    for vk in chain_events_df["version_key"].unique():
        if vk not in result:
            result[vk] = None
    return result


def _cap_secondary_delays(
    chain_events_df: pd.DataFrame,
    last_primary_dates: dict[str, Optional[date]],
    data_date: Optional[date] = None,
) -> pd.DataFrame:
    """Return a copy of chain_events_df with SECONDARY delays capped at 10 days.

    Adds bool column cap_synthetic. Does NOT mutate the input DataFrame.
    """
    df = chain_events_df.copy()
    df["cap_synthetic"] = False

    synthetic_rows: list[dict] = []
    secondary_mask = df["actor_type"] == "SECONDARY_CONSULTANT"

    for idx, row in df[secondary_mask].iterrows():
        vk = row["version_key"]
        last_primary = last_primary_dates.get(vk)
        if last_primary is None:
            continue

        deadline = last_primary + timedelta(days=SECONDARY_WINDOW_DAYS)
        event_d = _parse_event_date(row["event_date"])
        if event_d is None:
            event_d = data_date
        if event_d is None:
            continue

        raw = float(row["delay_contribution_days"]) if pd.notna(row["delay_contribution_days"]) else 0.0
        window_remaining = (deadline - event_d).days
        capped = max(0.0, min(raw, float(window_remaining)))
        excess = raw - capped

        df.at[idx, "delay_contribution_days"] = int(round(capped))

        if excess > 0:
            synth = row.to_dict()
            synth["actor"] = "MOEX_CAP_REATTRIBUTED"
            synth["actor_type"] = "MOEX"
            synth["delay_contribution_days"] = int(round(excess))
            synth["cap_synthetic"] = True
            synthetic_rows.append(synth)

    if synthetic_rows:
        df = pd.concat([df, pd.DataFrame(synthetic_rows)], ignore_index=True)
    return df


def _attribute_phase_delay(
    phase_kind: str,
    events_in_phase: pd.DataFrame,
    focus_owners: list[str],
    is_open: bool,
    delay_days: int,
) -> list[dict]:
    """Return list of attribution dicts for a phase.

    Rules (locked spec):
        review closed: distribute proportionally to delay_contribution_days
        review open:   equal split across focus_owners
        rework:        100% to ENTREPRISE
    """
    if delay_days <= 0:
        return []

    if phase_kind == "rework":
        return [{"actor": "ENTREPRISE", "tier": "CONTRACTOR", "days": delay_days}]

    # review phase
    if is_open:
        if not focus_owners:
            return [{"actor": "UNKNOWN", "tier": "UNKNOWN", "days": delay_days}]
        n = len(focus_owners)
        base = delay_days // n
        remainder = delay_days - base * n
        result = []
        for i, actor in enumerate(focus_owners):
            days = base + (1 if i < remainder else 0)
            result.append({"actor": actor, "tier": "PRIMARY", "days": days})
        return result

    # review closed: proportional attribution, then aggregate same-actor entries
    ops_rows = events_in_phase[
        (events_in_phase["source"] != "DEBUG")
        & (events_in_phase["actor_type"].isin(
            ["PRIMARY_CONSULTANT", "SECONDARY_CONSULTANT", "MOEX", "SAS"]
        ))
    ].copy()
    ops_rows["_delay"] = ops_rows["delay_contribution_days"].fillna(0).astype(float)

    # Aggregate contributions by (actor, tier) before distributing
    ops_rows["_tier"] = ops_rows["actor_type"].map(_ACTOR_TYPE_TIER).fillna("UNKNOWN")
    contrib_by_actor = (
        ops_rows.groupby(["actor", "_tier"])["_delay"].sum().reset_index()
    )
    contrib_by_actor = contrib_by_actor[contrib_by_actor["_delay"] > 0]
    total_contrib = contrib_by_actor["_delay"].sum()

    if total_contrib <= 0:
        return [{"actor": "UNKNOWN", "tier": "UNKNOWN", "days": delay_days}]

    attributions = []
    distributed = 0
    rows_list = contrib_by_actor.to_dict("records")
    for i, r in enumerate(rows_list):
        share = r["_delay"] / total_contrib
        if i == len(rows_list) - 1:
            days = delay_days - distributed
        else:
            days = round(share * delay_days)
        distributed += days
        attributions.append({"actor": r["actor"], "tier": r["_tier"], "days": days})

    return attributions


def _build_indice_phases(
    version_events: pd.DataFrame,
    version_key: str,
    indice: str,
    next_version_submittal: Optional[date],
    is_dernier: bool,
    focus_owners: list[str],
    data_date: Optional[date],
) -> dict:
    """Build the per-indice payload dict for one version."""
    # Filter to OPS rows only (exclude DEBUG / SYSTEM)
    ops = version_events[
        (version_events["source"] != "DEBUG")
        & (version_events["actor_type"] != "SYSTEM")
        & (version_events["cap_synthetic"] == False)  # noqa: E712
    ]

    # -- Review phase ---------------------------------------------------------
    submittal_rows = ops[ops["step_type"] == "SUBMITTAL"]
    review_start: Optional[date] = None
    if not submittal_rows.empty:
        review_start = _parse_event_date(submittal_rows.iloc[0]["event_date"])

    # created_at = review_start (first submission date for this version)
    created_at = review_start.isoformat() if review_start else None

    # MOEX terminal event (completed, non-DEBUG)
    moex_completed = version_events[
        (version_events["actor_type"] == "MOEX")
        & (version_events["is_completed"].astype(str).str.lower() == "true")
        & version_events["event_date"].notna()
        & (version_events["source"] != "DEBUG")
    ]

    # Determine MOEX outcome
    moex_complete_date: Optional[date] = None
    moex_ref = False
    if not moex_completed.empty:
        moex_row = moex_completed.iloc[0]
        moex_complete_date = _parse_event_date(moex_row["event_date"])
        step_t = str(moex_row.get("step_type", ""))
        status = str(moex_row.get("status", ""))
        moex_ref = (step_t in _MOEX_REF_STEP_TYPES) or (status in _MOEX_REF_STATUSES)

    # Determine effective review_end + closure_type (Precision #5)
    review_end: Optional[date] = None
    closure_type: str
    if moex_complete_date is not None and next_version_submittal is not None:
        if next_version_submittal < moex_complete_date:
            review_end = next_version_submittal
            closure_type = "IMPLICIT_NEXT_INDICE"
        else:
            review_end = moex_complete_date
            closure_type = "MOEX_REF" if moex_ref else "MOEX_TERMINAL"
    elif moex_complete_date is not None:
        review_end = moex_complete_date
        closure_type = "MOEX_REF" if moex_ref else "MOEX_TERMINAL"
    elif next_version_submittal is not None:
        review_end = next_version_submittal
        closure_type = "IMPLICIT_NEXT_INDICE"
    else:
        review_end = None
        closure_type = "OPEN"

    # Change 4: MOEX never called but all non-MOEX/non-SAS actors completed →
    # use max(response_dates) as effective review_end (delay collapses to 0)
    if review_end is None:
        non_moex_ops = ops[~ops["actor_type"].isin({"MOEX", "CONTRACTOR", "SAS"})]
        if not non_moex_ops.empty:
            all_done = (non_moex_ops["is_completed"].astype(str).str.lower() == "true").all()
            if all_done:
                completed_dates = [
                    d for d in (
                        _parse_event_date(v) for v in non_moex_ops["event_date"]
                    ) if d is not None
                ]
                if completed_dates:
                    review_end = max(completed_dates)
                    closure_type = "BET_COMPLETE_NO_MOEX"

    review_open = review_end is None
    eff_data_date = data_date  # guaranteed non-None by compute_all_chain_timelines guard

    if review_start is None:
        review_days_actual = 0
    elif review_open:
        review_days_actual = (eff_data_date - review_start).days
    else:
        review_days_actual = (review_end - review_start).days

    review_delay = max(0, review_days_actual - CYCLE_REVIEW_DAYS)

    # Change 2: SAS issued CYCLE_REQUIRED REF → attribute delay to contractor
    sas_ref_rows = ops[
        (ops["actor_type"] == "SAS")
        & (ops["step_type"] == "CYCLE_REQUIRED")
        & (ops["status"].fillna("").astype(str).str.strip() == "REF")
    ]
    sas_ref_date = (
        _parse_event_date(sas_ref_rows.iloc[0]["event_date"])
        if not sas_ref_rows.empty else None
    )
    if sas_ref_date is not None:
        r_end = review_end if review_end is not None else eff_data_date
        attributed_days = min(max(0, (r_end - sas_ref_date).days - 15), review_delay) if r_end is not None else 0
        contractor = (
            str(submittal_rows.iloc[0]["actor"])
            if not submittal_rows.empty else "ENTREPRISE"
        )
        review_attribution = (
            [{"actor": contractor, "tier": "CONTRACTOR", "days": attributed_days}]
            if attributed_days > 0 else []
        )
    else:
        # Change 3: fallback focus owners from BLOCKING_WAIT rows for open reviews
        effective_focus = focus_owners
        if review_open and not focus_owners:
            bw = version_events[
                (version_events["step_type"] == "BLOCKING_WAIT")
                & (version_events["is_completed"].astype(str).str.lower() == "false")
                & (~version_events["actor_type"].isin({"SYSTEM", "CONTRACTOR"}))
            ]
            if not bw.empty:
                effective_focus = bw["actor"].dropna().unique().tolist()
        review_attribution = _attribute_phase_delay(
            "review", version_events, effective_focus, review_open, review_delay,
        )

    review_phase = {
        "start": review_start.isoformat() if review_start else None,
        "end": review_end.isoformat() if review_end else None,
        "days_actual": review_days_actual,
        "days_expected": CYCLE_REVIEW_DAYS,
        "delay_days": review_delay,
        "is_open": review_open,
        "attributed_to": review_attribution,
    }

    # -- Rework phase (Precision #5: generate whenever next indice exists) ----
    rework_phase = None
    if next_version_submittal is not None and review_end is not None:
        rework_start = review_end  # never None when next_version_submittal is not None
        rework_end_val = next_version_submittal.isoformat()
        rework_days_actual = (next_version_submittal - rework_start).days
        rework_delay = max(0, rework_days_actual - CYCLE_REWORK_DAYS)
        rework_attribution = _attribute_phase_delay(
            "rework", version_events, focus_owners, False, rework_delay
        )
        rework_phase = {
            "start": rework_start.isoformat(),
            "end": rework_end_val,
            "days_actual": rework_days_actual,
            "days_expected": CYCLE_REWORK_DAYS,
            "delay_days": rework_delay,
            "is_open": False,
            "attributed_to": rework_attribution,
        }

    return {
        "indice": indice,
        "version_key": version_key,
        "created_at": created_at,
        "is_dernier": is_dernier,
        "closure_type": closure_type,
        "review": review_phase,
        "rework": rework_phase,
    }


def _aggregate_breakdown(indices: list[dict]) -> tuple[dict[str, int], int]:
    """Sum delay days per actor across all phases of all indices.

    MOEX_CAP_REATTRIBUTED rows are folded into the canonical MOEX actor
    ("Maitre d'Oeuvre EXE") in the breakdown. The raw cap total is returned
    separately as the second element of the tuple.
    """
    totals: dict[str, int] = {}
    cap_reattributed: int = 0
    for idx in indices:
        for phase_key in ("review", "rework"):
            phase = idx.get(phase_key)
            if not phase:
                continue
            for entry in phase.get("attributed_to", []):
                actor = entry["actor"]
                days = entry["days"]
                if actor == "MOEX_CAP_REATTRIBUTED":
                    cap_reattributed += days
                    actor = "Maitre d'Oeuvre EXE"
                totals[actor] = totals.get(actor, 0) + days
    return dict(sorted(totals.items(), key=lambda x: -x[1])), cap_reattributed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_chain_timeline(
    family_key: str,
    ctx,
    capped_events_df: pd.DataFrame,
    chain_register_df: pd.DataFrame,
    chain_versions_df: pd.DataFrame,
) -> dict:
    """Return per-chain timeline payload for one family_key."""
    # Data date and focus owner lookup from ctx
    data_date: Optional[date] = getattr(ctx, "data_date", None)
    dernier_df = getattr(ctx, "dernier_df", None)

    # Register row for this chain
    reg_row = chain_register_df[chain_register_df["family_key"] == family_key]
    if reg_row.empty:
        raise ValueError(f"family_key {family_key!r} not found in CHAIN_REGISTER")
    reg = reg_row.iloc[0]
    numero = str(reg["numero"])
    latest_indice = str(reg.get("latest_indice", ""))

    # Versions ordered by version_sort_order
    fam_versions = chain_versions_df[
        chain_versions_df["family_key"] == family_key
    ].copy()
    fam_versions["_sort"] = fam_versions["version_sort_order"].astype(int)
    fam_versions = fam_versions.sort_values("_sort").reset_index(drop=True)

    if fam_versions.empty:
        raise ValueError(f"No versions found for family_key {family_key!r}")

    # Focus owners for open attribution (from dernier_df if available)
    focus_owners: list[str] = []
    if dernier_df is not None and "_focus_owner" in dernier_df.columns and "numero" in dernier_df.columns:
        match = dernier_df[dernier_df["numero"].astype(str) == family_key]
        if not match.empty:
            val = match.iloc[0]["_focus_owner"]
            if isinstance(val, list):
                focus_owners = val
            elif isinstance(val, str) and val:
                focus_owners = [val]

    # Capped events for this chain
    fam_events = capped_events_df[capped_events_df["family_key"] == family_key]

    indices_payload: list[dict] = []
    n_versions = len(fam_versions)

    for i, ver_row in fam_versions.iterrows():
        vk = str(ver_row["version_key"])
        indice = str(ver_row["indice"])
        is_dernier = (indice == latest_indice)

        # Next version's submittal date (for rework_end)
        next_submittal: Optional[date] = None
        pos = fam_versions.index.get_loc(i)
        if pos + 1 < n_versions:
            next_ver_row = fam_versions.iloc[pos + 1]
            next_vk = str(next_ver_row["version_key"])
            next_ev = capped_events_df[
                (capped_events_df["version_key"] == next_vk)
                & (capped_events_df["step_type"] == "SUBMITTAL")
            ]
            if not next_ev.empty:
                next_submittal = _parse_event_date(next_ev.iloc[0]["event_date"])

        version_events = fam_events[fam_events["version_key"] == vk]
        indice_dict = _build_indice_phases(
            version_events, vk, indice, next_submittal, is_dernier, focus_owners, data_date
        )
        indices_payload.append(indice_dict)

    # Totals
    total_actual = sum(
        (idx["review"]["days_actual"] if idx["review"] else 0) +
        (idx["rework"]["days_actual"] if idx["rework"] else 0)
        for idx in indices_payload
    )
    n_idx = len(indices_payload)
    total_expected = n_idx * CYCLE_REVIEW_DAYS + max(0, n_idx - 1) * CYCLE_REWORK_DAYS
    total_delay = max(0, total_actual - total_expected)

    chain_long = total_actual > CHAIN_LONG_THRESHOLD_DAYS
    cycle_depasse = any(
        (idx["review"] and idx["review"]["delay_days"] > 0) or
        (idx["rework"] and idx["rework"]["delay_days"] > 0)
        for idx in indices_payload
    )

    attribution_breakdown, cap_reattributed = _aggregate_breakdown(indices_payload)

    return {
        "family_key": family_key,
        "numero": numero,
        "indices": indices_payload,
        "totals": {
            "days_actual": total_actual,
            "days_expected": total_expected,
            "delay_days": total_delay,
        },
        "chain_long": chain_long,
        "cycle_depasse": cycle_depasse,
        "attribution_breakdown": attribution_breakdown,
        "attribution_cap_reattributed": cap_reattributed,
    }


def compute_all_chain_timelines(
    ctx,
    chain_events_df: pd.DataFrame,
    chain_register_df: pd.DataFrame,
    chain_versions_df: pd.DataFrame,
) -> dict[str, dict]:
    """Apply cap once then build timeline for every family_key."""
    if ctx is None:
        raise ValueError("ctx is required: pass a RunContext from load_run_context(BASE_DIR)")
    if getattr(ctx, "data_date", None) is None:
        raise ValueError("ctx.data_date is required (got None)")
    if getattr(ctx, "dernier_df", None) is None:
        raise ValueError("ctx.dernier_df is required (got None)")
    data_date = getattr(ctx, "data_date", None)
    last_primary = _compute_last_primary_date_per_version(chain_events_df)
    capped = _cap_secondary_delays(chain_events_df, last_primary, data_date=data_date)

    family_keys = sorted(chain_register_df["family_key"].unique())
    timelines: dict[str, dict] = {}
    skipped: list[tuple[str, str]] = []

    for i, fk in enumerate(family_keys):
        if i > 0 and i % 100 == 0:
            logger.info("[CHAIN_TIMELINE] Processed %d / %d chains", i, len(family_keys))
        try:
            timelines[fk] = compute_chain_timeline(
                fk, ctx, capped, chain_register_df, chain_versions_df
            )
        except Exception as exc:
            logger.warning("[CHAIN_TIMELINE] Skipped %s: %s", fk, exc)
            skipped.append((fk, str(exc)))

    logger.info(
        "[CHAIN_TIMELINE] Done: %d processed, %d skipped",
        len(timelines), len(skipped),
    )
    return timelines


def write_chain_timeline_artifact(
    timelines: dict[str, dict],
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write JSON + CSV to output_dir. Returns (json_path, csv_path)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / _JSON_FILENAME
    csv_path = output_dir / _CSV_FILENAME

    # Load version overrides (context/dead_version_overrides.csv)
    # Maps version_key -> reason ("DEAD" or "NO_ATTRIBUTION")
    _override_map: dict[str, str] = {}
    _dead_path = output_dir.parent.parent / "context" / "dead_version_overrides.csv"
    if _dead_path.exists():
        try:
            _dead_df = pd.read_csv(_dead_path, dtype=str)
            for _, row in _dead_df.iterrows():
                vk_ = str(row["version_key"]).strip()
                reason_ = str(row["reason"]).strip()
                if vk_ and reason_:
                    _override_map[vk_] = reason_
        except Exception:
            pass

    # JSON: pretty-printed, sorted by family_key
    # Phase 0 D-005 (2026-04-29): atomic write. Pre-fix, a process kill mid-write
    # left CHAIN_TIMELINE_ATTRIBUTION.json truncated at the canonical path,
    # silently feeding partial data to consumers (audit found 132 chains missing
    # for AXI/UTB/FRS/SCH/LIN/DBH). Write to *.tmp then os.replace → final.
    import os
    ordered = dict(sorted(timelines.items()))
    json_tmp = json_path.with_suffix(".json.tmp")
    with open(json_tmp, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2, ensure_ascii=False, default=str)
    os.replace(str(json_tmp), str(json_path))

    # CSV: one row per (indice, phase, attributed_to entry)
    rows: list[dict] = []
    for fk, payload in ordered.items():
        numero = payload.get("numero", fk)
        for idx in payload.get("indices", []):
            indice = idx["indice"]
            vk = idx["version_key"]
            for phase_key in ("review", "rework"):
                phase = idx.get(phase_key)
                if phase is None:
                    continue
                base = {
                    "family_key": fk,
                    "numero": numero,
                    "indice": indice,
                    "version_key": vk,
                    "phase": phase_key,
                    "start": phase["start"],
                    "end": phase["end"],
                    "days_actual": phase["days_actual"],
                    "days_expected": phase["days_expected"],
                    "delay_days": phase["delay_days"],
                    "is_open": phase["is_open"],
                }
                attrs = phase.get("attributed_to", [])
                if attrs:
                    for a in attrs:
                        row = dict(base)
                        actor = a["actor"]
                        tier = a["tier"]
                        days = a["days"]
                        if vk in _override_map:
                            label = _override_map[vk]
                            actor, tier, days = label, label, 0
                        row["attributed_to_actor"] = actor
                        row["attributed_to_tier"] = tier
                        row["attributed_days"] = days
                        rows.append(row)
                else:
                    row = dict(base)
                    row["attributed_to_actor"] = ""
                    row["attributed_to_tier"] = ""
                    row["attributed_days"] = 0
                    rows.append(row)

    csv_df = pd.DataFrame(rows, columns=[
        "family_key", "numero", "indice", "version_key", "phase",
        "start", "end", "days_actual", "days_expected", "delay_days", "is_open",
        "attributed_to_actor", "attributed_to_tier", "attributed_days",
    ])
    csv_df.sort_values(["family_key", "indice", "phase"], inplace=True)
    # Phase 0 D-005 atomic write (see comment near JSON above)
    csv_tmp = csv_path.with_suffix(".csv.tmp")
    csv_df.to_csv(csv_tmp, index=False)
    os.replace(str(csv_tmp), str(csv_path))

    logger.info(
        "[CHAIN_TIMELINE] Wrote %s (%d bytes) and %s (%d rows)",
        json_path.name, json_path.stat().st_size,
        csv_path.name, len(csv_df),
    )
    return json_path, csv_path


def load_chain_timeline_artifact(output_dir: Path) -> dict[str, dict]:
    """Read CHAIN_TIMELINE_ATTRIBUTION.json. Raises FileNotFoundError if missing."""
    json_path = output_dir / _JSON_FILENAME
    if not json_path.exists():
        raise FileNotFoundError(
            f"CHAIN_TIMELINE_ATTRIBUTION.json not found at {json_path}. "
            "Run compute_all_chain_timelines + write_chain_timeline_artifact first."
        )
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)
