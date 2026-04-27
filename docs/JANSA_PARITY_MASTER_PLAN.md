# JANSA PARITY MASTER PLAN — EXECUTION VERSION

**Date:** 2026-04-22
**Goal:** Achieve 100% functional parity between Legacy UI and JANSA UI
**Constraint:** Preserve JANSA visuals — no redesign

---

# 🎯 DEFINITION OF 100% PARITY

A feature is at parity when:

1. Same data (identical values on same run)
2. Same actions (buttons, exports, navigation)
3. Same workflows (end-to-end)
4. Same filters (focus, thresholds, etc.)
5. No fake values (explicit warning if missing)

---

# ⚙️ CORE EXECUTION RULES (MANDATORY)

* One step = one objective
* One step = one feature group
* NEVER mix features in same step
* NEVER mix layers unless required
* NO UI redesign
* NO new architecture
* NO fake data
* Always test on **Run 3**
* Always compare with legacy

---

# 🧱 LAYER CLASSIFICATION (MANDATORY)

Every change must be classified:

* **BACKEND** → Python logic / computation
* **BRIDGE** → data_bridge.js / adapter
* **UI** → React components

If not explicitly classified → step is invalid

---

# 🧪 VALIDATION PROTOCOL (MANDATORY)

Each step MUST:

1. Compare JANSA vs Legacy (same run)
2. Validate:

   * numbers match
   * behavior matches
   * no crash
   * no missing data
3. If mismatch exists:
   → Step is NOT complete

---

# 📊 PARITY TRACKING

TOTAL FEATURES: 35

After each step update:

* Closed features:
* Remaining features:
* Parity %:

Example:
After Step 2:
Closed: 3
Remaining: 32
Parity: 28%

---

# 📄 STEP OUTPUT FORMAT (MANDATORY)

Each step must produce:

`docs/JANSA_PARITY_STEP_XX.md`

Content:

1. What was analyzed
2. Root cause
3. Fix (by layer: backend/bridge/ui)
4. Proof (numbers/screenshots/comparison)
5. Remaining issues

---

# 🧭 EXECUTION ORDER (STRICT)

## PHASE A — DATA CORRECTNESS

Goal: All numbers and logic are correct

* STEP 2 — Focus parity
* STEP 3 — Overview parity
* STEP 4 — Consultants list parity
* STEP 5 — Consultant fiche parity

---

## PHASE B — USER INTERACTION

Goal: User can explore data

* STEP 6 — Drilldowns
* STEP 7 — Drilldown exports

---

## PHASE C — SYSTEM OPERATIONS

Goal: User can operate system

* STEP 9 — Runs page
* STEP 10 — Executer page

---

## PHASE D — FULL COVERAGE

Goal: No missing features

* STEP 8 — Contractors
* STEP 11 — Utilities
* STEP 12 — Final audit

---

# 🚫 EXCLUDED / DEFERRED FEATURES

Do NOT implement now:

* Trend sparklines (requires DB)
* Any UI improvement not in legacy
* Any redesign of JANSA layout

---

# 🔥 CRITICAL EXECUTION RULE

DO NOT START WITH EXECUTER

Start with:

👉 STEP 2 — Focus

Reason:

* No async complexity
* No file dialogs
* Pure data logic
* Fast validation

---

# 🧠 STEP EXECUTION TEMPLATE

Every step must follow:

1. Analyze legacy behavior
2. Analyze JANSA behavior
3. Identify mismatch
4. Fix mismatch
5. Validate vs legacy
6. Document

---

# 📌 CURRENT BASELINE

* Full parity: 7/35 (20%)
* Partial: 13/35 (37%)
* Missing: 22/35 (63%)

(This is the reference starting point)

---

# 🎯 NEXT STEP

👉 Execute STEP 2 — Focus parity

Do NOT proceed until:

* Focus values differ from normal mode
* No UI crash
* Consultant breakdown correct
* Legacy comparison validated

---

# 🧭 FINAL OBJECTIVE

End state:

* All 35 features = FULL_PARITY
* Final audit confirms 100% parity
* JANSA becomes production UI


## ⚠️ SPECIAL CASE — BUREAU DE CONTRÔLE (SOCOTEC) STATUS VOCABULARY

The Bureau de Contrôle (e.g. SOCOTEC) does NOT follow the standard VISA status vocabulary.

### Standard consultants:

* VSO
* VAO
* REF
* HM

### Bureau de Contrôle / SOCOTEC:

* FAV (Favorable)
* SUS (Suspendu)
* DEF (Défavorable)
* HM (Hors Mission)

---

### 🔒 Mandatory Rule

For all JANSA UI displays:

* Bureau de Contrôle MUST use:
  → **FAV / SUS / DEF / HM**

* It must NEVER be displayed as:
  → VSO / VAO / REF (even if values are 0)

---

### 🧠 Interpretation Rule

* Do NOT force mapping:

  * FAV ≠ VSO
  * SUS ≠ VAO
  * DEF ≠ REF

* These are **different semantic systems**, not equivalents.

---

### 🧱 Implementation Rule

When rendering consultant breakdowns:

* Detect Bureau de Contrôle via:

  * canonical name (e.g. SOCOTEC)
  * or consultant type (bureau de contrôle)

* Switch breakdown labels dynamically:

  * standard consultants → VSO / VAO / REF / HM
  * bureau de contrôle → FAV / SUS / DEF / HM

---

### ❌ Forbidden Behavior

* Showing VSO/VAO/REF = 0 for Bureau de Contrôle
* Mapping DEF/SUS/FAV into generic VISA statuses
* Mixing both vocabularies in the same consultant

---

### ✅ Validation Requirement

For Bureau de Contrôle (Run 3):

* UI must show:

  * FAV, SUS, DEF, HM counts
* Values must match backend raw data
* No VSO/VAO/REF visible for that consultant

---

### 🎯 Rationale

The Bureau de Contrôle follows a **regulatory validation logic**, not the same approval workflow as other consultants.

Displaying the wrong vocabulary:

* breaks parity with legacy
* misleads interpretation
* invalidates consultant analysis

This rule is **mandatory for parity compliance**.
