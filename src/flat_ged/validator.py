"""
validator.py — Invariant and consistency checks.

All checks are preserved exactly from prototype_v4.py.
Raises GEDValidationError instead of sys.exit() so the batch runner
can catch per-document failures without aborting the entire batch.
"""

import datetime

from transformer import GEDValidationError


def check_delay_invariants(ops: list[dict]) -> None:
    """Check four delay invariants across all steps.

    Check 1 — cumulative never decreases
    Check 2 — contribution >= 0
    Check 3 — contribution <= step_delay
    Check 4 — sum(contributions) == final cumulative

    Raises GEDValidationError if any check fails (lists all failures first).
    """
    failures        = []
    prev_cumulative = 0
    sum_contributions = 0

    for s in ops:
        label = f"step_order={s['step_order']} actor={s['actor_clean']}"
        dc = s["delay_contribution_days"]
        sd = s["step_delay_days"]
        cu = s["cumulative_delay_days"]

        if dc < 0:
            failures.append(f"[INVARIANT FAIL] Check 2 (dc >= 0): dc={dc} at {label}")
        if dc > sd:
            failures.append(
                f"[INVARIANT FAIL] Check 3 (dc <= step_delay): dc={dc} > sd={sd} at {label}"
            )
        if cu < prev_cumulative:
            failures.append(
                f"[INVARIANT FAIL] Check 1 (cumulative non-decreasing): "
                f"cu={cu} < prev={prev_cumulative} at {label}"
            )
        prev_cumulative    = cu
        sum_contributions += dc

    final_cumulative = ops[-1]["cumulative_delay_days"] if ops else 0
    if sum_contributions != final_cumulative:
        failures.append(
            f"[INVARIANT FAIL] Check 4 (sum contributions == final cumulative): "
            f"sum={sum_contributions} != final={final_cumulative}"
        )

    if failures:
        msg = "\n".join(failures)
        raise GEDValidationError(f"Delay invariant check failed:\n{msg}")


def check_global_delay_consistency(
    ops:                      list[dict],
    sas_state:                str,
    closure_mode:             str,
    cm_dl_source:             str,
    global_deadline:          datetime.date,
    effective_cycle_end_date: datetime.date,
) -> str | None:
    """Check that step-by-step cumulative delay matches global shortcut.

    This check is skipped when any of the following hold (shortcut is unreliable):
      - sas_state == PENDING         → incomplete ops set
      - closure_mode in (MOEX_VISA, ALL_RESPONDED_NO_MOEX) → MOEX marginal delay missed
      - cm_dl_source == COMPUTED_15D_AFTER_LATE_SAS → SAS lateness counted separately

    Returns None on pass or skip.
    Raises GEDValidationError on mismatch.
    """
    skip_conditions = (
        sas_state == "PENDING",
        closure_mode in ("MOEX_VISA", "ALL_RESPONDED_NO_MOEX"),
        cm_dl_source == "COMPUTED_15D_AFTER_LATE_SAS",
        not global_deadline,
        not ops,
    )
    if any(skip_conditions):
        return None  # check skipped — not applicable

    expected = max(0, (effective_cycle_end_date - global_deadline).days)
    actual   = ops[-1]["cumulative_delay_days"]

    if expected != actual:
        raise GEDValidationError(
            f"[FAIL] Global delay mismatch: "
            f"expected={expected} actual={actual} "
            f"(cycle_end={effective_cycle_end_date} global_dl={global_deadline})"
        )

    return "PASS"


def print_delay_summary(ops: list[dict]) -> None:
    """Print the delay validation summary (single-mode verbose output)."""
    final_cumulative  = ops[-1]["cumulative_delay_days"] if ops else 0
    sum_contributions = sum(s["delay_contribution_days"] for s in ops)
    print(f"\n── Delay Validation Summary ──────────────────────────────")
    print(f"  Total steps:            {len(ops)}")
    print(f"  Final cumulative delay: {final_cumulative} days")
    print(f"  Sum of contributions:   {sum_contributions} days")
    print(f"  Invariant status:       PASS")
    print(f"──────────────────────────────────────────────────────────\n")
    print(f"[OK] GED_OPERATIONS: {len(ops)} steps  "
          f"(total cumulative delay: {final_cumulative} days)")
