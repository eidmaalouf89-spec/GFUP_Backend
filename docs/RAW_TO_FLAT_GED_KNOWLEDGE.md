# RAW GED ↔ FLAT GED — Knowledge Reference

## 0. Purpose

This document is the canonical reference for every "why does RAW have X and
FLAT have Y" question on this project. It was authored at the close of
Phase 8B (2026-05-01) and consolidates everything the Phase 8B audit chain
proved or measured. After this lands, future engineers asking about a
RAW/FLAT discrepancy should be answered from this file alone — without
re-running any trace, without re-reading `src/flat_ged/`, without
debugging from scratch.

Read top-to-bottom on first contact. Use the section index after that.
Numbers are accurate as of the run that produced
`output/debug/raw_flat_reconcile.xlsx` (size ≈ 695 KB, 11 sheets) and
`output/debug/SHADOW_FLAT_GED_OPERATIONS.csv` (27,134 rows). Re-run with
the validation commands in §14 if any number here looks stale.

## 1. The two artifacts

### 1.1 RAW GED

**Location:** `input/GED_export.xlsx`, sheet `Doc. sous workflow, x versions`.

**Shape:** ~6,901 data rows in the project's run-0 export. One row per
document submission instance — every distinct (doc, indice, submission)
the GEMO operations team ever opened a workflow for. Each row carries a
`NUMERO` (which may be empty for special submissions like PPSPS / BdT /
"instruction" docs), an `INDICE`, ~24 actor-column groups (each
`{date, response, comment, pj}`), and the metadata core (LOT, EMETTEUR,
titre, "Créé le", etc.).

**RAW is the operational source of truth.** It carries every submission,
every approver call, every response, every comment, every date —
**including operator manipulation errors** like accidental REF + VAO
co-existing on the same instance, or duplicate cycle-2 entries when
cycle 1 closes. RAW is messy by design; FLAT cleans it up.

The Phase 8B trace flattens RAW into 38,898 events (one row per
{ACTOR_CALLED, RESPONSE, DOCUMENT_VERSION, OPEN_DOC} event) at
`output/debug/raw_ged_trace.csv`. Use the trace, not the raw GED file
directly, for all numeric comparisons.

### 1.2 FLAT GED

**Location:** `output/intermediate/FLAT_GED.xlsx`, sheets `GED_OPERATIONS`
(32,099 rows) and `GED_RAW_FLAT` (27,261 rows).

**Producer:** `src/flat_ged/transformer.py` (with help from `reader.py`,
`resolver.py`, `validator.py`, `writer.py`). Driver: `src/flat_ged/cli.py`.

**Shape:** A normalised projection of RAW. One row per *workflow step*
on the *active version* of each document:

* `GED_OPERATIONS` is the operational view — synthetic OPEN_DOC,
  real or synthetic SAS, sorted CONSULTANT block, forced-last MOEX —
  with computed deadlines, retard/avance, cumulative delay, cycle
  closure. This is the file the rest of the pipeline consumes.

* `GED_RAW_FLAT` is the factual view — one row per called approver on
  the active version, no synthetic rows, no computed deadlines, raw
  status text and raw response date preserved alongside the parsed
  values. Use this when you need the closest-to-RAW projection FLAT
  produces.

The Phase 8B trace flattens FLAT into 59,360 events at
`output/debug/flat_ged_trace.csv` (the trace combines both sheets plus
the synthetic OPEN_DOC step type so cross-side comparisons can run
against a unified shape).

### 1.3 Why both exist

RAW carries operational truth + operator errors. FLAT applies the
project's documented projection rules to produce a single canonical
operational view per document. The downstream pipeline
(`workflow_engine.py`, `effective_responses.py`, `report_memory.py`,
`reporting/aggregator.py`, the JANSA UI) reads ONLY FLAT — never RAW.

If RAW changes (re-export from GED), FLAT must be regenerated. If FLAT
disagrees with RAW on a specific document, either RAW has an error
that FLAT correctly cleaned up (one of the §5 buckets), or FLAT has a
bug. The audit determines which.

## 2. The identity contract (proved)

### 2.1 Numero parity

After the `_MISSING_` filter (see §2.3), RAW unique numero count equals
FLAT unique numero count: **2,819**. Sheet 01 verdict: PASS. Missing in
FLAT: 0. Extra in FLAT: 0.

### 2.2 (numero, indice) parity

After `_MISSING_` filter, RAW unique (numero, indice) pair count equals
FLAT OPEN_DOC count: **4,848**. Sheet 01 verdict: PASS.

The pipeline's `audit_counts_lineage.py` baseline confirms the same
numbers: `raw_unique_numero=2819`, `raw_unique_numero_indice=4848`,
`open_doc_rows=4848`.

### 2.3 What `_MISSING_` means

746 RAW data rows have no assigned NUMERO. These are PPSPS (Plan
Particulier de Sécurité et de Protection de la Santé), BdT (Bordereau
de Travaux), "instruction" docs, and other submissions that GEMO
processes but doesn't track via the standard NUMERO scheme.

The Phase 8B extractor assigns a synthetic key `_MISSING_{excel_row}`
to each so downstream tooling can still address them, but they are
**explicitly excluded from the identity sets**. They never appear in
FLAT — `src/pipeline/stages/stage_read_flat.py` filters them out before
FLAT is built.

For Phase 8B.5 (sheet 07), 27 `_MISSING_` rows that have actor=0-SAS
and status=REF ARE included in the SAS REF trace baseline (so the 836
unique source_excel_row baseline is preserved); they are classified
MALFORMED_RESPONSE.

### 2.4 Why row counts NEVER match

RAW is one-row-per-submission; FLAT is one-row-per-step. A single RAW
row with 24 approver columns can produce up to ~24 FLAT rows. Beyond
that:

* RAW SAS REF count (836) ≠ FLAT SAS REF count (283). The 553-row gap
  is explained by the §5 taxonomy in §3 / §4.
* FLAT SAS REF count (283) ≠ UI SAS REF count. The UI may merge REF
  and SAS_REF buckets into a single display category — FLAT is the
  authoritative number, the UI is a presentation layer.

If you find row counts that "should" match according to a casual
intuition, walk through §3 and §5 before filing a bug. Most apparent
mismatches are documented projections.

## 3. The projection rules (the §5 taxonomy, with concrete counts)

This is the canonical taxonomy. Every numeric difference between RAW
and FLAT must map to one of these buckets, or it is UNEXPLAINED and a
candidate §17 input.

### 3.1 ACTIVE_VERSION_PROJECTION

**Definition:** RAW carries a row for an *old* indice that has been
superseded by a later indice. FLAT keeps only the active version
(highest progression score per the resolver). RAW row count: ~2,053
DOCUMENT_VERSION events for old indices in this run.

**Counts (current data):** sheet 07 = 32 (SAS REF subset);
sheet 03 = 155 (actor calls); shadow rule total = 189.

**Example:** numero=149520 with indices A, B, C — RAW has actor calls
for A and B, FLAT keeps only C's calls (the active version per the
resolver scoring).

**Implementation:** emergent. The resolver at `src/flat_ged/resolver.py`
classifies non-active candidates as INACTIVE_DUPLICATE (line 184-206
of resolver.py). Only the ACTIVE candidate is passed to the
transformer. INACTIVE candidates' actor rows never make it into FLAT.

### 3.2 DUPLICATE_MERGED

**Definition:** Multiple RAW rows for the same (numero, indice, actor)
on the active version. The resolver picks one as canonical (highest
progression score, tie-break by earliest row index) and FLAT projects
that single row.

**Counts:** sheet 07 = 143 (SAS REF); sheet 03 = 4,184 (actor calls,
across all actors). Shadow rule total = 2,286 (after `_MISSING_`
filter and other prior drops).

**Example:** numero=152012/A had two GED rows (operator-side
duplicate); resolver picked the row with higher score; FLAT kept just
one entry.

**Implementation:** emergent — resolver scoring + INACTIVE_DUPLICATE
assignment in `classify_candidates`. The
`sas_pre2026_confirmation.json` artifact's `structural_normalization_rows: 1`
explicitly identifies this for the SAS pre-2026 case.

### 3.3 DUPLICATE_FAVORABLE_KEPT

**This rule was discovered during 8B.5 — the project owner had not seen
it documented anywhere before the audit surfaced it.** Document it in
detail.

**Definition:** Same contractor submission appears in RAW with both
REF and a favorable status (VAO, VSO, VSO-SAS) at the same
(numero, indice, 0-SAS) actor key. FLAT keeps only the favorable;
the REF row is the dropped one. Operator-manipulation pattern: the
contractor first received REF, fixed the issue, resubmitted, and the
GED operator entered both rows — the resolver's progression scoring
prefers the row with the favorable response, leaving the REF behind.

Submission dates may differ between the REF and favorable rows in the
actual GED data, so the rule does NOT enforce a same-date constraint.
What matters: both rows exist in RAW for the same (numero, indice,
actor), and FLAT has only the favorable.

**Counts:** sheet 07 = 345 (SAS REF subset); shadow rule total = 314.
This is the largest single bucket of "missing" SAS REF rows — without
this rule the 836 RAW SAS REFs would lose 345 to UNEXPLAINED.

**Example (verified by project owner):** 249101/B, 245027/D, 245026/B,
246000/A, 246012/A. For each, RAW has two rows at (numero, indice,
0-SAS): one with `status_clean=REF`, one with VAO or VSO. FLAT has
only the favorable row.

**Implementation:** emergent. There is **no single function** that
implements DUPLICATE_FAVORABLE_KEPT. It is the consequence of:

1. The resolver's progression scoring (`score_candidate` in
   `src/flat_ged/resolver.py:73-105`) gives +20 / +50 / +100 for
   ANSWERED rows of any status. Both REF and VAO score the same
   weight, BUT —
2. When two RAW rows differ on response date, the row with the
   *later* response date typically has more *other* answered rows
   too (the contractor resubmitted and approvers continued
   processing), so the score on that row outweighs the older row.
3. INACTIVE_DUPLICATE assignment then drops the older REF row.

This is fragile: if the older REF row happened to have a higher score
(e.g., MOEX answered before the resubmit), the rule would NOT fire and
RAW's REF would survive into FLAT. We have not observed this in the
current data but it's a latent edge case.

The reason audit (sheet 10) has no row that explicitly names
DUPLICATE_FAVORABLE_KEPT — because the rule isn't implemented as a
named filter. This is one of the things the §17 follow-on phase should
clean up, either by writing an explicit favorable-wins tie-breaker into
the resolver or by adding a comment block at
`src/flat_ged/resolver.py:179` documenting the emergent behavior.

### 3.4 SAS_CYCLE_COLLAPSED

**Definition:** RAW captures cycle 1 and cycle 2 of the same SAS step
as separate rows; FLAT collapses them into a single step row keeping
the latest decision.

**Counts (current data):** **zero**. The rule exists in the §5
taxonomy and the trace classifier (`_classify_raw_only` in
`scripts/raw_flat_reconcile.py:159-163`) but did not fire in run 0.

This is expected — SAS cycles 1 and 2 are rare in the current
dataset. Recorded for completeness.

### 3.5 EXCEPTION_COLUMN

**Definition:** Some GED columns are not actor calls (e.g., a column
labelled "Exception" or used for ad-hoc operator notes). Their values
are dropped from FLAT.

**Counts:** subsumed into UNKNOWN_ACTOR for the current data. The
Exception List actor (§3.8) is the only EXCEPTION_COLUMN producer
observed.

### 3.6 NON_OPERATIONAL_RESPONSE

**Definition:** A response with a status outside the operational set
{VAO, VSO, VSO-SAS, REF, HM, FAV, SUS, DEF}. FLAT drops these — they
are typically operator typos or experimental status codes.

**Counts:** the shadow rule run shows 0 rows in this bucket because
RAW data in run 0 does not have non-operational status values
surviving extraction. The classifier guards against the case but it
hasn't fired. Recorded for completeness.

### 3.7 MALFORMED_RESPONSE

**Definition:** RAW row that cannot be projected because it lacks a
core identity field — most commonly a NULL numero (PPSPS, BdT, etc.).

**Counts:** sheet 07 = 27 (SAS REF subset of `_MISSING_`); shadow rule
total = 2,580. The 2,580 figure is the F-1 entry in §17: 746 NULL-
numero RAW submissions × ~3.5 events per submission on average.

**Implementation:** filtered upstream in
`src/pipeline/stages/stage_read_flat.py` (NULL numero is dropped
before FLAT receives the row). Note that `src/flat_ged/resolver.py:17`
declares `class GEDDocumentSkip(Exception)` with a docstring
*claiming* to handle this case — but the class is NEVER raised. The
filter happens elsewhere. This is the single INVALID_REASON entry in
sheet 10 (§11).

### 3.8 UNKNOWN_ACTOR

**Definition:** RAW carries actor calls in columns that the canonical
mapping (`src/flat_ged/input/source_main/consultant_mapping.py`) does
not recognise. Most commonly the "Exception List" actor — a catch-all
column for non-standard approvers.

**Counts:** sheet 03 = 203 (RAW_ONLY actor-call rows where actor is
"Exception List"); shadow rule total = 6,395 (includes Exception
List + empty actor + other unmapped columns).

**Implementation:** explicit. `src/flat_ged/transformer.py:121-122`:
`if canonical == "Exception List" or ds == "NOT_CALLED": continue` —
this is the one actual row-drop in the transformer file.

### 3.9 UNEXPLAINED

**Definition:** A RAW event that doesn't fit any of §3.1–§3.8 and
doesn't appear in FLAT. These are the §17 gate inputs.

**Counts:** sheet 07 = **6** (the 28xxx /A C1 cluster); sheet 06 = 67
(non-SAS responses); sheet 03 = 132 (actor calls). Some overlap —
the actor-call UNEXPLAINED includes events that didn't surface as
response UNEXPLAINED because actor calls are at a different
granularity than responses.

The 6 SAS REF UNEXPLAINED are the most actionable. See §9 for the
deep dive.

## 4. The full SAS REF decomposition (the headline)

This is the equation to remember. Whenever someone asks "why does FLAT
have 283 SAS REF when RAW has 836," walk them through this:

```
836 RAW SAS REF unique pairs
  =  283 matched (canonical, present in FLAT GED_RAW_FLAT)
  +  345 DUPLICATE_FAVORABLE_KEPT    (same-day VAO/VSO won)
  +  143 DUPLICATE_MERGED            (multiple RAW rows → one FLAT)
  +   32 ACTIVE_VERSION_PROJECTION   (RAW carries old indice)
  +   27 MALFORMED_RESPONSE          (NULL-numero submission)
  +    6 UNEXPLAINED                 (28xxx /A C1 cluster)
```

ASCII flow:

```
  RAW SAS REF (836) ─┬─ MATCHED            ──→ FLAT SAS REF (283)
                     ├─ DUP_FAVORABLE_KEPT ──→ DROPPED
                     ├─ DUPLICATE_MERGED   ──→ MERGED
                     ├─ ACTIVE_VER_PROJ    ──→ DROPPED (old indice)
                     ├─ MALFORMED          ──→ FILTERED (NULL numero)
                     └─ UNEXPLAINED ──┐
                                       ├─→ §17 GATE INPUT
                                       └─→ 6 rows in 28xxx /A C1
```

### 4.1 The +1 in-FLAT inconsistency

```
FLAT GED_OPERATIONS SAS REF = 283
FLAT GED_RAW_FLAT  SAS REF = 284   ← off-by-one
```

The +1 in `GED_RAW_FLAT` corresponds to one specific (numero, indice)
that has a SAS REF in RAW_FLAT but not in OPERATIONS. Per sheet 07's
matched-but-OPS-absent slice, this looks like 051020/A — the same pair
that the SAS pre-2026 filter excludes from OPERATIONS but leaves in
RAW_FLAT (`sas_pre2026_confirmation.json` — `excluded_doc_ids: ["051020|A"]`).

This 1-row difference is its own finding. It's documented in F-6 of
the §17 report. Resolution: confirm with project owner whether
RAW_FLAT should also be filtered, OR document the asymmetry.

## 5. Date and comment fidelity

### 5.1 No date data is lost

`RAW_NONBLANK_FLAT_BLANK = 0` rows in sheet 08. Every RAW date that
the trace can read is preserved in FLAT. The L0 → L1 projection does
not silently lose dates.

### 5.2 Deadline date is FLAT-computed

`deadline_date` is never populated in RAW (the GED file doesn't carry
deadlines — they're computed by the project's SAS-window /
global-window rules). The 16,187 RAW_BLANK_FLAT_NONBLANK rows in
sheet 08 are entirely deadline_date enrichment. This is expected —
FLAT computes `submittal_date + SAS_WINDOW_DAYS` for SAS,
`submittal_date + GLOBAL_WINDOW_DAYS` for global, and stores the
result in every step row.

### 5.3 443 DRIFTED dates

Both RAW and FLAT have a date for the same matched event but the
values differ. Top-5 drift sample:

* numero=1/A actor=0-SAS — drift on response_date
* numero=11/A actor=0-SAS — drift on response_date
* numero=12/A actor=0-SAS — drift on response_date
* numero=128400/C actor=0-SAS — drift on response_date
* numero=13/A actor=0-SAS — drift on response_date

Hypothesis: timezone or format normalisation. RAW reads Excel cells
which can be either datetime objects or strings; FLAT normalises to
ISO `YYYY-MM-DD`. If RAW had a datetime carrying a timezone offset
that nudged the date over midnight, the dates would diverge by one
day. To confirm, pull the top-20 drift rows and compute the day
difference; if all are ±1 day, it's timezone. If the deltas are
larger or random, it's a deeper bug.

This is in the F-7 entry of the §17 report — investigate in the
follow-on phase.

### 5.4 113 RAW_ONLY comments

Sheet 09 verdict RAW_ONLY = 113 rows. Pattern (per top-5 verified
during 8B.6): all 0-SAS events with FLAT-side reshaped comments. The
RAW comment carries operator notes that FLAT either truncates or
replaces with a structured summary. This is **comment information
loss** — the RAW comment is not preserved in FLAT.

This is the load-bearing finding of sheet 09. F-8 in the §17 report.

### 5.5 27 FLAT_ONLY comments

Sheet 09 verdict FLAT_ONLY = 27 rows. FLAT has a comment that has no
RAW counterpart. Likely consultant-report enrichment (the report
ingestion appended to the comment). Verify by joining with the 8B.8
report-to-flat trace: the GED+REPORT_COMMENT effective-source rows
should overlap heavily with these 27.

## 6. Actor canonical mapping

### 6.1 Source

`src/flat_ged/input/source_main/consultant_mapping.py` carries
`CANONICAL_TO_DISPLAY` (canonical id → human-readable label) and
`RAW_TO_CANONICAL` (raw GED column header → canonical id). The Phase
8B trace re-implements the mapping inline rather than importing
production code so the audit is independent of the code under audit.

### 6.2 17 actors observed in run 0

Sheet 02 is the canonical list. Top entries (ordered by call count):

* `0-SAS` (4,858 calls)
* `Bureau de Contrôle` (4,471 calls — corresponds to SOCOTEC)
* `AMO HQE` (4,228 — corresponds to LE_SOMMER consultant family)
* `Maître d'Oeuvre EXE` (3,492 — MOEX, GEMO own role)
* `ARCHITECTE` (3,234 — Hardel + Le Bihan Architectes)
* `BET Acoustique` (2,860 — corresponds to AVLS consultant family)
* `BET Structure` (1,188 — corresponds to TERRELL consultant family)
* …and 10 more.

See sheet 02 for raw_count, flat_count, delta per actor. All 17 have
delta=0 except those listed in sheet 03 (RAW_ONLY / FLAT_ONLY at
specific (numero, indice) keys).

### 6.3 The "Exception List" actor

203 RAW rows have actor canonical = "Exception List". Zero FLAT rows.
This is by design — Exception List is a catch-all GED column for
non-standard approvers (one-off invitees, ad-hoc reviewers). FLAT
drops it because the operational model only handles known actor
roles. See §3.8 (UNKNOWN_ACTOR).

## 7. Report integration

### 7.1 Today

Reports merge into responses **downstream of FLAT** via
`src/effective_responses.py`. The function `build_effective_responses`
takes `ged_responses_df` (derived from FLAT) and
`persisted_report_responses_df` (loaded from
`data/report_memory.db`) and produces an `effective` DataFrame with
two extra columns: `effective_source` (controlled vocabulary) and
`report_memory_applied` (bool).

Eligibility gates (E1–E8) are documented in the function's docstring;
the audit-level summary is: confidence ≥ 0.75 (HIGH/MEDIUM only),
status or date present, doc_id matched, freshness window not
violated.

### 7.2 Phase 8B.8 finding

Trace covered 1,245 active persisted report responses across 4
consultant families (SOCOTEC, ACOUSTICIEN AVLS, AMO HQE LE SOMMER,
BET STR-TERRELL).

Headline distribution:

```
Match type:     EXACT 1026 / FAMILY 200 / FUZZY 19 / NO_MATCH 0
Confidence:     HIGH 1019 / LOW 226 / MEDIUM 0 / UNKNOWN 0
Applied:        ENRICHMENT 942 / BLOCKED_CONFIDENCE 226
                PRIMARY 58 / BLOCKED_GED 10 / NOT_APPLIED 9
Effective src:  GED+REPORT_COMMENT 942 / GED 235
                GED+REPORT_STATUS 58 / GED_CONFLICT_REPORT 10
```

Of the 226 BLOCKED_BY_CONFIDENCE rows, all are LOW confidence at
ingestion (E2 fail). They correspond to
`MATCH_BY_RECENT_INDICE_FALLBACK` in the consultant match report —
when the report's NUMERO/INDICE didn't directly match a GED doc, the
ingestion fell back to "most recent indice" of the same numero, which
is correctness-questionable; E2 blocks these from contaminating FLAT.

### 7.3 Open question for §17 outcome D

Should reports live at the FLAT level instead of merging downstream?
Arguments for: simpler downstream code, reports become first-class
operations rows, audit trail is uniform. Arguments against: schema
work, FLAT becomes dependent on report ingestion order, the current
58 APPLIED_AS_PRIMARY upgrades are easy to track but harder to
reason about if they happen at FLAT-build time.

The Phase 8B audit does NOT recommend outcome D. The report→FLAT
merge works correctly today (1,000 of 1,245 reports are applied as
PRIMARY+ENRICHMENT, only 9 NOT_APPLIED, 0 false positives observed).
Defer outcome D until a concrete pain point emerges.

## 8. The shadow model

### 8.1 What it produces

`scripts/build_shadow_flat_ged.py` reads `raw_ged_trace.csv` and
applies, in spec order, every §5 rule that produces a documented drop:

1. MALFORMED_RESPONSE drop (`_MISSING_` numeros)
2. UNKNOWN_ACTOR drop (Exception List + empty)
3. NON_OPERATIONAL_RESPONSE drop (status not in operational set)
4. ACTIVE_VERSION_PROJECTION drop (per audit sheet 03/06)
5. DUPLICATE_FAVORABLE_KEPT drop (per audit sheet 07)
6. DUPLICATE_MERGED drop (per audit + same-key duplicates)

The remaining rows are `OPERATIONAL_KEEP` (or `UNEXPLAINED_KEEP` for
the 6 §17 inputs).

Output: `output/debug/SHADOW_FLAT_GED_OPERATIONS.csv` (27,134 rows,
GED_OPERATIONS-shaped) + `output/debug/SHADOW_FLAT_GED_TRACE.xlsx`
(per-rule sheets).

### 8.2 Where it differs from production FLAT

Sheet 11 (`raw_flat_reconcile.xlsx → 11_SHADOW_DIFFS`) lists 4,832
(numero, indice) pairs where shadow row count differs from production
FLAT row count. The bulk of these differences are NOT bugs — they
exist because the shadow does not synthesise OPEN_DOC / synthetic SAS
the way the production transformer does. Production FLAT has 59,360
events vs shadow's 27,134; the ~32k delta is dominated by:

* OPEN_DOC synthetic step (one per active version, ~4,848)
* Synthetic SAS for never-called SAS docs (a few hundred)
* MOEX synthesis when MOEX answered (~3,492)
* Cycle-2 events the trace splits but shadow doesn't recombine

The shadow's purpose is NOT to reproduce FLAT exactly. Its purpose is
to confirm that the §5 taxonomy *captures every documented drop*. It
succeeds: shadow's UNEXPLAINED_KEEP = 6, which exactly matches the
sheet 07 UNEXPLAINED count.

### 8.3 What that delta tells us

The shadow + sheet 11 confirm:

1. The §5 taxonomy is **complete** for documented drops — no rule
   missing from the list.
2. The 6 UNEXPLAINED rows are real — they survive every applied rule
   in the shadow and are NOT in current FLAT either, so the
   production code is dropping them through some path the audit
   hasn't characterised.
3. Production FLAT does additional projection (OPEN_DOC / synthetic
   SAS) on top of the §5 taxonomy. These are documented in
   `transformer.py` (`add_synthetic_sas`, the OPEN_DOC step in
   `build_operations`) and aren't taxonomy buckets — they're *step
   creation* rather than *row drops*.

## 9. The 6 remaining SAS REF UNEXPLAINED

### 9.1 The 28xxx cluster

Five doc keys explicitly identified by sheet 07's UNEXPLAINED slice:

* 28011/A (excel_row 2717)
* 28406/A (excel_row 3067)
* 28407/A (excel_row 3069)
* 28402/A (excel_row 3109)
* 28403/A (excel_row 3113)

The sixth row needs identification by reading sheet 07 directly —
filter by `classification = 'UNEXPLAINED'` to retrieve it.

### 9.2 What's known

For each of these 6 rows:

* `raw_cycle = C1` (no second cycle)
* No FLAT favorable response at same (numero, indice) — so
  DUPLICATE_FAVORABLE_KEPT does NOT apply
* No different-indice match in FLAT for the same numero — so
  ACTIVE_VERSION_PROJECTION does NOT apply
* Numero is not `_MISSING_` — so MALFORMED_RESPONSE does NOT apply
* No DUPLICATE_MERGED candidate at same key — so that rule does NOT
  apply

These are real REFs that vanished from FLAT with no documented
projection covering them.

### 9.3 Hypotheses (with evidence pointers)

1. **Pre-build cutoff filter (similar to D-012)** — there could be a
   submittal_date filter we haven't found. The D-012
   `_apply_sas_filter_flat` in `stage_read_flat.py` drops one pair
   (051020/A) for being before 2026; perhaps a similar filter targets
   the 28xxx range. Evidence pointer: check the submittal_date of the
   28xxx rows in sheet 07.

2. **Suppressed-pending docs** — the document or its submission was
   marked cancelled/pending-suppressed at the source. Evidence:
   inspect the source GED rows manually.

3. **A transformer rule not yet documented** — low likelihood. The
   transformer is small (729 lines, audited fully); we don't see a
   code path that would drop these specifically.

4. **A real bug in the FLAT projection** — most likely. The cluster
   is contiguous in the 28xxx range and shares C1 cycle, suggesting a
   shared upstream condition the audit hasn't surfaced. Most plausible:
   the resolver assigned all 5+1 rows to INACTIVE_DUPLICATE for some
   reason that doesn't fit the DUPLICATE_MERGED pattern — perhaps
   another row at a *different* (numero, indice) pair scored higher
   somehow.

### 9.4 What it would take to resolve

Manual inspection by the project owner: open `input/GED_export.xlsx`,
filter by NUMERO IN (28011, 28402, 28403, 28406, 28407, +1), examine
each row's full state. In parallel, run the resolver in single-mode
verbose output for each pair and inspect the candidate-resolution
report. If any row is being assigned INACTIVE_DUPLICATE
unexpectedly, that's the bug.

This is the primary §17 follow-on phase deliverable.

## 10. The DUPLICATE_FAVORABLE_KEPT rule (deep dive)

### 10.1 The pattern

A contractor submits the same (numero, indice). The first submission
is reviewed by the SAS approver and flagged REF. The contractor
addresses the flag and re-submits — sometimes the same day, sometimes
days later. The GED operator records both as separate rows with the
same (numero, indice). The second row receives VAO or VSO from the
SAS approver.

### 10.2 What FLAT does

Drops the REF row. Keeps the favorable. The "merged" row in
GED_RAW_FLAT carries the favorable status, the favorable response
date, and the favorable comment. The REF is invisible to all
downstream consumers (workflow_engine, reporting, JANSA UI).

### 10.3 Five spot-check cases verified by the project owner

* **249101/B** — RAW row 1: 0-SAS REF on submission_date X. RAW row
  2: 0-SAS VAO on submission_date X+N. FLAT row: VAO with row 2's
  date.
* **245027/D** — same pattern.
* **245026/B** — same pattern.
* **246000/A** — same pattern.
* **246012/A** — same pattern.

For exact excel rows, query sheet 07 with
`numero ∈ {249101, 245027, 245026, 246000, 246012}` and
`classification = 'DUPLICATE_FAVORABLE_KEPT'`.

### 10.4 Where the rule is implemented

**Nowhere as a single function.** As discussed in §3.3, the rule
emerges from:

* `src/flat_ged/resolver.py:73-105` (`score_candidate`) — additive
  progression scoring; ANSWERED rows of any status score the same.
* `src/flat_ged/resolver.py:179-206` (`classify_candidates`) — the
  highest-scored candidate becomes ACTIVE; others become
  INACTIVE_DUPLICATE.
* The transformer never sees INACTIVE_DUPLICATE candidates.
* The favorable row "wins" because it has more *other* answered rows
  alongside it (the contractor resubmitted, more approvers
  responded), so its score is higher.

The reason audit (sheet 10) does not flag this as a missing reason
because no `continue` or `raise` site explicitly handles
"DUPLICATE_FAVORABLE_KEPT" — the rule is a downstream consequence of
non-favorable INACTIVE_DUPLICATE assignment.

### 10.5 Total impact

345 SAS REF rows absorbed by this rule. This is the largest single
bucket of "missing" SAS REF rows. Without this rule the 836 RAW SAS
REFs would have 351 unexplained instead of 6.

## 11. Production-source rules vs taxonomy

Cross-reference table — for each §5 bucket, where it gets implemented
in production code:

| §5 taxonomy bucket          | Implementation in src/                                        | Sheet 10 reason audit row |
| --------------------------- | ------------------------------------------------------------- | ------------------------- |
| ACTIVE_VERSION_PROJECTION   | `src/flat_ged/resolver.py:classify_candidates`                | (emergent, no explicit reason text) |
| DUPLICATE_MERGED            | `src/flat_ged/resolver.py:classify_candidates` (INACTIVE_DUPLICATE) | (emergent) |
| DUPLICATE_FAVORABLE_KEPT    | **Nowhere named** — emerges from resolver scoring + ACTIVE selection | (none — flag for follow-on) |
| SAS_CYCLE_COLLAPSED         | (not yet observed — rule defined but unused)                  | (not in src/flat_ged/) |
| EXCEPTION_COLUMN            | Subsumed under UNKNOWN_ACTOR                                  | — |
| NON_OPERATIONAL_RESPONSE    | (defensive — not observed in run 0)                           | — |
| MALFORMED_RESPONSE          | `src/pipeline/stages/stage_read_flat.py` (NULL numero filter) | sheet 10 INVALID — `GEDDocumentSkip` doc is wrong |
| UNKNOWN_ACTOR               | `src/flat_ged/transformer.py:121-122`                         | sheet 10 VALID |
| UNEXPLAINED                 | (residual)                                                    | — |

**The §17 outcome leans on this table.** Two buckets
(DUPLICATE_FAVORABLE_KEPT and MALFORMED_RESPONSE) have implementation
gaps relative to documentation:

* DUPLICATE_FAVORABLE_KEPT has no named function — flag for follow-on
  to either implement explicitly or document the emergent behavior.
* MALFORMED_RESPONSE has a class (`GEDDocumentSkip`) declared with a
  drop docstring but never raised — flag for follow-on to delete or
  wire up.

These two are the substantive findings of sheet 10.

## 12. Tooling hazards observed during Phase 8B

### 12.1 H-1 at extreme

The Linux cross-mount served stale views of
`output/debug/raw_flat_reconcile.xlsx` for the entire phase. After
every workbook write, openpyxl-from-Linux read back data from a
buffered version that didn't reflect the most recent save. The
mitigation: every from-disk verification must use a Windows-shell
fresh-process Python call. The reconcile script and
`build_shadow_flat_ged.py` both invoke a `subprocess.run(["python",
"-c", check_code])` immediately after `wb.save()` for exactly this
reason.

If you write to the workbook without that subprocess check and then
read back, the values you see may be from a stale cache. Don't trust
the in-process read — always verify via subprocess.

### 12.2 H-4

`pytest` hangs against the reporting chain. Fast-only test runs work
fine (`pytest -m "not slow"`); avoid `pytest tests/test_reporting/`
in the audit pipeline.

### 12.3 H-5

Bulk xlsx I/O times out in sandbox. The reconcile workbook sits at
~700 KB after sheet 11 lands; reading all 11 sheets in one openpyxl
read-only pass is fine, but writing more than ~10 sheets in one save
risks timing out on large datasets. Sheet 11's 4,832 rows are well
within limits.

### 12.4 Excel-lock pollution

`input/~$GED_export.xlsx` (the lock file Excel creates when the file
is open) breaks `audit_counts_lineage.py`'s glob pattern when Excel
has the GED export open. Close Excel before running the audit
one-liner, or add a guard to the glob.

## 13. The artifacts directory

Every file under `output/debug/` produced by Phase 8B and what
question it answers:

| File                                     | Purpose / question answered                                            |
| ---------------------------------------- | ---------------------------------------------------------------------- |
| `raw_ged_trace.csv`                      | "What does the RAW GED look like, flattened to events?" 38,898 rows. |
| `raw_ged_trace.xlsx`                     | Same as csv, formatted for Excel viewers.                             |
| `flat_ged_trace.csv`                     | "What does the FLAT GED look like, flattened?" 59,360 rows.          |
| `flat_ged_trace.xlsx`                    | Same as csv.                                                          |
| `raw_flat_reconcile.xlsx`                | The canonical Phase 8B audit. 11 sheets covering all comparisons.    |
| `chain_onion_source_check.json`          | Phase 8 chain+onion data sourcing audit (predates 8B).                |
| `counts_lineage_audit.{json,xlsx}`       | The audit one-liner's underlying probe.                               |
| `counts_lineage_probe.{json,xlsx}`       | Earlier counts-lineage probe (predates 8B).                           |
| `sas_pre2026_confirmation.json`          | D-012 SAS pre-2026 filter confirmation. Auto-regenerated by `audit_counts_lineage.py`. |
| `report_to_flat_trace.{xlsx,json}`       | Phase 8B.8 report→FLAT trace. 1,245 reports analysed.               |
| `SHADOW_FLAT_GED_OPERATIONS.csv`         | Phase 8B.9 shadow operations. 27,134 rows.                            |
| `SHADOW_FLAT_GED_TRACE.xlsx`             | Phase 8B.9 per-rule view of shadow projections.                       |
| `PHASE_8B_FINAL_REPORT.md`               | The §17 decision gate report.                                         |
| (other files predate Phase 8B)           | Not modified during this phase.                                       |

## 14. How to repeat this verification end-to-end

The exact sequence the project owner can run from a fresh checkout to
re-derive every number in this document:

```bash
# Re-extract traces (slow — full RAW + FLAT scan)
python scripts/extract_raw_ged_trace.py
python scripts/extract_flat_ged_trace.py

# Run the six reconciliation steps in order
python scripts/raw_flat_reconcile.py --step identity
python scripts/raw_flat_reconcile.py --step actor_calls
python scripts/raw_flat_reconcile.py --step responses
python scripts/raw_flat_reconcile.py --step dates_comments
python scripts/raw_flat_reconcile.py --step reasons_audit
python scripts/raw_flat_reconcile.py --step shadow

# Phase 8B.8 — report integration trace
python scripts/report_to_flat_trace.py

# Phase 8 audit one-liner — must remain unchanged
python scripts/audit_counts_lineage.py
# Expected last two lines (verbatim):
#   AUDIT: PASS=16 WARN=0 FAIL=1; first_unexpected_divergence=status_SAS_REF@L1_FLAT_GED_XLSX
#   UI_PAYLOAD: compared=10 matches=10 mismatches=0; OK - all compared fields match

# Fast tests
python -m pytest tests/test_raw_flat_reconcile.py \
                 tests/test_report_to_flat_trace.py \
                 tests/test_build_shadow_flat_ged.py \
                 -v -m "not slow"
# Expected: 89 passed
```

If any number diverges from this document, the document is stale —
update it before filing a bug. The numbers in §3 and §4 are the
load-bearing ones.

## 15. Glossary

* **L0 / L1 / L2 / L3 / L4 / L5 / L6** — layer chain in the project's
  audit model. L0 = RAW GED. L1 = FLAT GED. L2 = `effective_responses`
  output. L3 = `workflow_engine`. L4 = aggregator. L5 = UI payload.
  L6 = chain+onion intelligence. The Phase 8B audit lives at L0 ↔ L1.

* **Operational status set** — VAO, VSO, VSO-SAS, REF, HM, FAV, SUS,
  DEF. Any status outside this set in RAW is NON_OPERATIONAL_RESPONSE.

* **VAO / VSO / VSO-SAS** — favorable approval variants. VAO = Validé
  Avec Observations. VSO = Validé Sans Observation. VSO-SAS is the
  scope-tagged form when 0-SAS responds.

* **REF** — refused. The negative response that triggers a new cycle.

* **HM** — Hors Marché (out of scope).

* **FAV / SUS / DEF** — additional positive/conditional/deferred
  variants used by some actors.

* **SAS** — *the* approver step. 0-SAS is the canonical SAS actor.
  SAS approval gates downstream consultant + MOEX phases.

* **MOEX** — Maître d'Oeuvre EXE. The forced-last step. When MOEX
  answers, the cycle closes via the MOEX_VISA rule.

* **OPEN_DOC** — synthetic step inserted at the start of every FLAT
  step list. Marks the moment the document was opened in the GED.
  Always step_order 1.

* **CONSULTANT** — generic catch-all step type for all non-SAS,
  non-MOEX, non-OPEN_DOC actor calls (Architecte, BET *, AMO HQE,
  Bureau de Contrôle, etc.).

* **`_MISSING_` synthetic numero** — assigned by the trace extractor
  to RAW rows with NULL numero. Format: `_MISSING_{excel_row}`. Used
  so downstream tooling can address the row even though it has no
  real numero. Filtered out before identity comparison.

* **cycle_id (C1 / C2)** — RAW SAS rows can carry C1 (first cycle)
  or C2 (second cycle, after REF + resubmit). Most actors don't
  carry cycle markers. C2 → SAS_CYCLE_COLLAPSED candidate (rare).

* **indice** — the document version letter (A, B, C, D, ...). Each
  re-issue increments the indice. Multiple indices for the same
  numero may exist; FLAT keeps only the active one.

* **numero** — the document number (e.g., "152012"). Stable across
  versions.

* **doc_id** — internal UUID assigned per (numero, indice) by the
  pipeline at run time. Not stable across pipeline runs. Used by
  `report_memory.db` to bridge persisted reports to FLAT documents.

* **actor_canonical** — the canonical id from
  `consultant_mapping.RAW_TO_CANONICAL`. Stable across the project.
  Used as the join key in §6.

---

*End of knowledge reference. If a future Phase introduces new
projection rules, expand §3 (taxonomy) and §11 (production-source
table). If new artifacts are produced, expand §13. Treat the
load-bearing numbers in §3 and §4 as canonical until a re-run of §14
disagrees.*
