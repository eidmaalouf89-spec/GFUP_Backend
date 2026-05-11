# Archive — Reconstruction copies of counter_attack_builder

**Date:** 2026-05-11 (Step 5 — archive reconstruction copies)

## Context

These three files are historical reconstruction copies of
`src/reporting/counter_attack_builder.py`, produced during the
6X.F2-bis / R1 / R2C reconstruction phases (ref. Step 0 forensic,
`context/11_TOOLING_HAZARDS.md` H-1.1 change-log entries at lines 306-307).

They were moved here from `src/reporting/` during Step 5 cleanup.
They are **not** the active source of truth.

## Important

- The active builder is `src/reporting/counter_attack_builder.py`.
- **Do not import, reference, or consult these files for current bucket
  logic.** The bucket model was rewritten in Step 1 (4-bucket model) and
  is documented in `obsidian_repo_mind/` and
  `scripts/diag/step1_baseline.json`.
- These files are retained for forensic record only.

## File inventory

| Filename | Size (bytes) | Step 0 readability |
|---|---|---|
| `counter_attack_builder.RECONSTRUCTION_R1_PREWRITE.py` | 0 | Unreadable (empty/encoding issue at Step 0 forensic) |
| `counter_attack_builder.RECONSTRUCTION_R1_VALIDATED.py` | 23 208 | Readable; `_assign_bucket` at lines 337-382 |
| `counter_attack_builder.R2C_PREWRITE.py` | 23 208 | Readable; `_assign_bucket` at lines 337-382, structurally identical to R1_VALIDATED |

## Retention policy

Do not modify. Do not delete without explicit user approval.

Closing date: 2026-05-11.
