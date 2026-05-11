---
name: 253100 flat GED stale — indice B missing from dernier_df
description: Numero 253100 has latest_indice=B in CHAIN_REGISTER but flat GED export only contains indice A; needs pipeline re-export to fix
type: project
---

Numero 253100: CHAIN_REGISTER correctly identifies indice B as latest, but the flat GED export has not been refreshed — `dernier_df` only contains indice A. Indice A should show `implicit_next_indice` closure since B was submitted before A was closed.

**Why:** Discovered during Step 6 (DCC latest-chain migration). `_latest_enriched_view` correctly omits this numero (can't compute DCC tags without a dernier_df row for indice B), resulting in 2,553 rows instead of 2,554.

**How to apply:** Next pipeline run (flat GED + chain+onion rebuild) should resolve this. After re-export, `compute_dcc_tags_bulk` should emit exactly `len(ctx.latest_chain_df)` rows with zero unjoinable gaps. Verify G-DCC-1 gate shows 0 unjoinable chains after the next pipeline run.
