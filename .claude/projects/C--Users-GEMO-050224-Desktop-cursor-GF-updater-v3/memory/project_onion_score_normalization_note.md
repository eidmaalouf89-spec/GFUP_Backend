---
name: Onion score normalization — display framing
description: normalized_score_100=100 means "highest in current selection", not absolute danger. UI/export must label it accordingly.
type: project
---

`normalized_score_100` in `onion_scores_df` is relative to the portfolio max, not an absolute danger level. The chain ranked 1 always scores 100 — including in single-chain filtered views.

**Why:** Normalization is portfolio-relative by design (Step 10). A chain scoring 100 in a small filtered selection may be far less severe than a chain scoring 60 in the full portfolio.

**How to apply:** Step 11 (Narrative), Step 12 (Export), and any UI tooltip or label must NOT render `normalized_score_100 = 100` as "maximum danger" or "critical alert." The correct framing is "highest impact in current selection." Add a note in the export header or UI legend: "Scores are relative to the displayed portfolio — 100 = highest in this view."
