"""
version_engine.py
-----------------
THE CORE MODULE.

Given a normalized docs DataFrame, reconstructs the true document lifecycle
for each (emetteur, lot_normalized, type_doc, numero_normalized) group.

Outputs per-document:
  - is_dernier_indice  : True if this row is the latest valid version
  - lifecycle_id       : UUID linking versions in the same chain
  - chain_position     : position in the reconstructed chain (1-based)
  - anomaly_flags      : list of flags (MISSING_INDICE, etc.)
  - confidence         : match confidence if applicable
  - is_excluded_lifecycle : True if lifecycle was replaced (reused numero)
"""

import re
import uuid
from typing import Optional

import pandas as pd


# ─────────────────────────────────────────────────────────────
# SIMILARITY SCORING
# ─────────────────────────────────────────────────────────────

FRENCH_STOPWORDS = {
    "de", "du", "des", "le", "la", "les", "un", "une", "et", "ou",
    "en", "au", "aux", "sur", "dans", "par", "pour", "avec", "sans",
    "est", "son", "sa", "ses", "qui", "que", "à", "d", "l", "n",
    "pdf", "p17", "t2", "exe", "in", "bx", "au", "ho",
}


def tokenize_libelle(text: Optional[str]) -> set:
    """Tokenize a document title into a set of meaningful words."""
    if not text:
        return set()
    # Remove file extension and code prefix patterns
    text = re.sub(r'\.pdf$', '', str(text), flags=re.IGNORECASE)
    # Split on underscores, spaces, hyphens
    tokens = re.split(r'[_\s\-:,\.]+', text.lower())
    # Remove stopwords, short tokens, pure numbers
    result = set()
    for t in tokens:
        t = t.strip()
        if len(t) > 2 and t not in FRENCH_STOPWORDS and not t.isdigit():
            result.add(t)
    return result


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two token sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def similarity_score(doc_a: dict, doc_b: dict) -> float:
    """
    Compute similarity between two document records.
    Weights per spec:
      Libellé Jaccard : 0.5
      Same zone/niveau: 0.2
      Same type_doc   : 0.1
      Same lot        : 0.1
      Date proximity  : 0.1
    """
    score = 0.0

    # 1. Libellé Jaccard (0.5)
    tokens_a = tokenize_libelle(doc_a.get("libelle_du_document") or doc_a.get("lib_ll_du_document"))
    tokens_b = tokenize_libelle(doc_b.get("libelle_du_document") or doc_b.get("lib_ll_du_document"))
    score += 0.5 * jaccard_similarity(tokens_a, tokens_b)

    # 2. Same zone/niveau (0.2)
    zone_match = (
        doc_a.get("zone") == doc_b.get("zone") and
        doc_a.get("niveau") == doc_b.get("niveau")
    )
    score += 0.2 if zone_match else 0.0

    # 3. Same type_doc (0.1)
    if doc_a.get("type_de_doc") == doc_b.get("type_de_doc"):
        score += 0.1

    # 4. Same lot_normalized (0.1)
    if doc_a.get("lot_normalized") == doc_b.get("lot_normalized"):
        score += 0.1

    # 5. Date proximity (0.1) — closer = higher
    date_a = doc_a.get("created_at")
    date_b = doc_b.get("created_at")
    if date_a is not None and date_b is not None:
        try:
            delta_days = abs((date_a - date_b).days)
            if delta_days < 30:
                score += 0.1
            elif delta_days < 90:
                score += 0.07
            elif delta_days < 365:
                score += 0.04
        except Exception:
            pass

    return score


# Thresholds
STRONG_MATCH = 0.75
WEAK_MATCH = 0.50


# ─────────────────────────────────────────────────────────────
# INDICE HELPERS
# ─────────────────────────────────────────────────────────────

def indice_to_int(indice: Optional[str]) -> int:
    """Convert letter indice to integer position (A=1, B=2, ..., Z=26)."""
    if not indice:
        return 0
    s = str(indice).strip().upper()
    if len(s) == 1 and s.isalpha():
        return ord(s) - ord('A') + 1
    return 0


def int_to_indice(n: int) -> str:
    """Convert integer to letter indice."""
    if n <= 0:
        return "?"
    return chr(ord('A') + n - 1)


# ─────────────────────────────────────────────────────────────
# ANOMALY TRIAGE
# ─────────────────────────────────────────────────────────────

def _triage_lifecycle(flags: list, n_versions: int) -> str:
    """
    Determine resolution_status for a lifecycle.

    OK               — no anomalies
    AUTO_RESOLVED    — anomaly is safe to handle automatically:
                         • MISSING_INDICE only (A→C gap, latest is dernier)
                         • OUT_OF_ORDER_INDICE with exactly 2 versions
                           (simple swap, latest date wins)
    REVIEW_REQUIRED  — complex or risky anomaly:
                         • REUSED_NUMERO
                         • OUT_OF_ORDER_INDICE with > 2 versions
                         • Multiple anomaly types together
    IGNORED          — set externally by exclusion config (Patch 5)
    """
    if not flags:
        return "OK"

    flag_set = set(flags)

    # REUSED_NUMERO always needs review
    if "REUSED_NUMERO" in flag_set:
        return "REVIEW_REQUIRED"

    # Multiple anomaly types → review
    if len(flag_set) > 1:
        return "REVIEW_REQUIRED"

    # Single anomaly:
    if "MISSING_INDICE" in flag_set:
        return "AUTO_RESOLVED"  # Gap in sequence, latest wins

    if "OUT_OF_ORDER_INDICE" in flag_set:
        if n_versions <= 2:
            return "AUTO_RESOLVED"  # Simple swap
        return "REVIEW_REQUIRED"   # Complex reordering

    # Unknown flag
    return "REVIEW_REQUIRED"


# ─────────────────────────────────────────────────────────────
# VERSION ENGINE MAIN CLASS
# ─────────────────────────────────────────────────────────────

class VersionEngine:

    def __init__(self, docs_df: pd.DataFrame):
        """
        docs_df must have columns:
          doc_id, emetteur, lot_normalized, type_de_doc, numero_normalized,
          indice, lib_ll_du_document, created_at, zone, niveau, lot_prefix
        """
        self.docs_df = docs_df.copy()
        self._results = None

    def run(self) -> pd.DataFrame:
        """
        Run the full version engine.
        Returns enriched DataFrame with version chain metadata.

        Process:
          1. Coarse grouping: (emetteur, lot_normalized, type_de_doc, numero_normalized)
          2. Within each coarse group: family clustering by (lot_prefix, zone, niveau)
             + libelle Jaccard ≥ 0.75
          3. Lifecycle reconstruction inside each family cluster
        """
        df = self.docs_df.copy()

        # Initialize output columns
        df["lifecycle_id"]          = None
        df["chain_position"]        = 0
        df["is_dernier_indice"]     = False
        df["is_excluded_lifecycle"] = False
        df["anomaly_flags"]         = [[] for _ in range(len(df))]
        df["version_confidence"]    = 1.0
        df["resolution_status"]     = "OK"   # OK | AUTO_RESOLVED | REVIEW_REQUIRED | IGNORED
        df["coarse_group_key"]      = None
        df["family_cluster_id"]     = None
        df["lifecycle_key"]         = None

        # Coarse group keys
        group_keys = ["emetteur", "lot_normalized", "type_de_doc", "numero_normalized"]
        for k in group_keys:
            if k not in df.columns:
                df[k] = None

        grouped = df.groupby(
            [k for k in group_keys if k in df.columns],
            dropna=False
        )

        result_parts = []

        for group_key, group_df in grouped:
            # Build a readable coarse group key string
            coarse_key_str = "|".join(str(v) for v in (
                group_key if isinstance(group_key, tuple) else (group_key,)
            ))

            # Cluster into families
            families = self._cluster_families(group_df.copy())

            for family_cluster_id, family_df in families:
                # Tag coarse + family identifiers
                family_df = family_df.copy()
                family_df["coarse_group_key"] = coarse_key_str
                family_df["family_cluster_id"] = family_cluster_id
                family_df["lifecycle_key"] = f"{coarse_key_str}::{family_cluster_id[:8]}"

                processed = self._process_group(family_df)
                result_parts.append(processed)

        if result_parts:
            result = pd.concat(result_parts, ignore_index=True)
        else:
            result = df.copy()

        self._results = result
        return result

    def _cluster_families(self, group_df: pd.DataFrame):
        """
        Cluster documents within a coarse group into families.

        Two documents belong to the same family if:
          - Same lot_prefix (structural: same building)
          - Same zone AND niveau (location match), OR
          - Libelle Jaccard similarity ≥ 0.75 vs the cluster representative

        Returns list of (family_cluster_id_str, family_df) tuples.
        If all documents share the same coarse group, returns [(new_uuid, full_df)].
        """
        group_df = group_df.copy().reset_index(drop=True)
        n = len(group_df)

        if n == 1:
            return [(str(uuid.uuid4()), group_df)]

        # Sort by date for stable ordering
        group_df = group_df.sort_values("created_at", na_position="last").reset_index(drop=True)

        rows = group_df.to_dict("records")

        # Cluster assignments: cluster_id (int) per row
        assignments = [-1] * n
        cluster_reps: list = []  # (cluster_int_id, representative_row)

        for i, row in enumerate(rows):
            lot_prefix_i = row.get("lot_prefix")
            zone_i  = row.get("zone")
            niveau_i = row.get("niveau")
            tokens_i = tokenize_libelle(
                row.get("libelle_du_document") or row.get("lib_ll_du_document")
            )

            best_cluster = -1
            best_sim = 0.0

            for cid, rep in cluster_reps:
                # Must be same building (lot_prefix) — hard constraint when both known
                rep_prefix = rep.get("lot_prefix")
                if lot_prefix_i and rep_prefix and lot_prefix_i != rep_prefix:
                    continue

                # Compute libelle similarity to representative
                tokens_rep = tokenize_libelle(
                    rep.get("libelle_du_document") or rep.get("lib_ll_du_document")
                )
                lib_sim = jaccard_similarity(tokens_i, tokens_rep)

                # Boost for same zone+niveau
                zone_bonus = (
                    0.15 if (zone_i and zone_i == rep.get("zone") and
                             niveau_i and niveau_i == rep.get("niveau"))
                    else 0.0
                )

                combined = lib_sim + zone_bonus

                if combined > best_sim:
                    best_sim = combined
                    best_cluster = cid

            FAMILY_THRESHOLD = 0.75
            if best_cluster >= 0 and best_sim >= FAMILY_THRESHOLD:
                assignments[i] = best_cluster
            else:
                # Start a new cluster
                new_cid = len(cluster_reps)
                cluster_reps.append((new_cid, row))
                assignments[i] = new_cid

        # Build result
        families = []
        unique_clusters = sorted(set(assignments))
        for cid in unique_clusters:
            indices = [i for i, a in enumerate(assignments) if a == cid]
            family_df = group_df.iloc[indices].copy()
            families.append((str(uuid.uuid4()), family_df))

        return families

    def _process_group(self, group_df: pd.DataFrame) -> pd.DataFrame:
        """
        Process one family cluster (already separated from coarse group).
        Reconstruct version chain, detect anomalies, mark dernier indice.
        """
        # Sort by date ascending (nulls last)
        group_df = group_df.copy()
        group_df = group_df.sort_values("created_at", na_position="last")
        group_df = group_df.reset_index(drop=True)

        n = len(group_df)

        if n == 1:
            # Single document — trivially the dernier indice
            lifecycle_id = str(uuid.uuid4())
            group_df.at[0, "lifecycle_id"] = lifecycle_id
            group_df.at[0, "chain_position"] = 1
            group_df.at[0, "is_dernier_indice"] = True
            group_df.at[0, "version_confidence"] = 1.0
            return group_df

        # ── Step 1: Detect lifecycle splits (reused numero) ──
        split_points = self._detect_lifecycle_splits(group_df)

        # Split into sub-groups (lifecycles)
        lifecycles = []
        prev = 0
        for sp in split_points:
            lifecycles.append(group_df.iloc[prev:sp].copy())
            prev = sp
        lifecycles.append(group_df.iloc[prev:].copy())

        # ── Step 2: Mark old lifecycles as excluded ──
        active_lifecycle_idx = len(lifecycles) - 1
        for i, lc in enumerate(lifecycles):
            if i < active_lifecycle_idx:
                lc["is_excluded_lifecycle"] = True
                lc["anomaly_flags"] = lc["anomaly_flags"].apply(
                    lambda x: x + ["REUSED_NUMERO"]
                )
                lc["resolution_status"] = "REVIEW_REQUIRED"

        # ── Step 3: Process active lifecycle ──
        active_lc = lifecycles[active_lifecycle_idx]
        active_lc = self._process_lifecycle(active_lc)
        lifecycles[active_lifecycle_idx] = active_lc

        # ── Step 4: Reassemble ──
        result = pd.concat(lifecycles, ignore_index=True)
        return result

    def _detect_lifecycle_splits(self, group_df: pd.DataFrame) -> list:
        """
        Detect points where the numero was reused (new lifecycle start).
        Returns list of row indices where a new lifecycle begins.
        """
        splits = []
        n = len(group_df)

        if n < 2:
            return splits

        rows = group_df.to_dict("records")

        for i in range(1, n):
            prev = rows[i - 1]
            curr = rows[i]

            sim = similarity_score(prev, curr)
            prev_date = prev.get("created_at")
            curr_date = curr.get("created_at")

            # Compute date gap
            date_gap_days = None
            if prev_date is not None and curr_date is not None:
                try:
                    date_gap_days = (curr_date - prev_date).days
                except Exception:
                    pass

            # Large date gap + low similarity = new lifecycle
            if (
                sim < WEAK_MATCH and
                date_gap_days is not None and
                date_gap_days > 180
            ):
                splits.append(i)

        return splits

    def _process_lifecycle(self, lc_df: pd.DataFrame) -> pd.DataFrame:
        """
        For one lifecycle (no reuse split):
        1. Build chronological index sequence
        2. Detect missing/out-of-order indices
        3. Handle B-still-open-but-C-exists
        4. Mark dernier indice
        """
        lc_df = lc_df.copy()
        lifecycle_id = str(uuid.uuid4())
        n = len(lc_df)

        # Sort by date
        lc_df = lc_df.sort_values("created_at", na_position="last").reset_index(drop=True)

        # Get indice values
        indices = [lc_df.at[i, "indice"] for i in range(n)]
        indice_ints = [indice_to_int(idx) for idx in indices]

        # ── Check for out-of-order ──
        out_of_order = False
        for i in range(1, n):
            if indice_ints[i] < indice_ints[i - 1]:
                out_of_order = True
                break

        # ── Check for missing indices ──
        seen = set(idx for idx in indice_ints if idx > 0)
        if seen:
            max_idx = max(seen)
            expected = set(range(1, max_idx + 1))
            missing = expected - seen
        else:
            missing = set()

        # ── Detect Case B: older B open but newer C exists ──
        # If indice N+2 exists but N+1 does not: N+1 is obsolete/missing
        # The latest by date IS the dernier indice regardless

        # ── Assign lifecycle metadata ──
        all_flags = []
        if out_of_order:
            all_flags.append("OUT_OF_ORDER_INDICE")
        if missing:
            all_flags.append("MISSING_INDICE")

        # Determine resolution_status for the lifecycle
        resolution = _triage_lifecycle(all_flags, n)

        for i in range(n):
            lc_df.at[i, "lifecycle_id"] = lifecycle_id
            lc_df.at[i, "chain_position"] = i + 1

            flags = list(lc_df.at[i, "anomaly_flags"]) + all_flags
            lc_df.at[i, "anomaly_flags"] = flags
            lc_df.at[i, "resolution_status"] = resolution

        # ── Dernier indice = chronologically LAST valid document ──
        # Not necessarily highest letter — it's the most recent by date
        lc_df.at[n - 1, "is_dernier_indice"] = True

        # Compute confidence: if there are anomalies, lower confidence
        base_confidence = 1.0
        if out_of_order:
            base_confidence -= 0.2
        if missing:
            base_confidence -= 0.1
        lc_df["version_confidence"] = min(base_confidence, 1.0)

        return lc_df

    def get_dernier_indices(self) -> pd.DataFrame:
        """Return only the rows that are marked as dernier indice."""
        if self._results is None:
            self.run()
        return self._results[self._results["is_dernier_indice"] == True].copy()

    def get_anomalies(self) -> pd.DataFrame:
        """Return all rows with at least one anomaly flag."""
        if self._results is None:
            self.run()
        df = self._results.copy()
        df = df[df["anomaly_flags"].apply(lambda x: len(x) > 0)]
        return df

    def get_all_versions(self) -> pd.DataFrame:
        """Return full results DataFrame."""
        if self._results is None:
            self.run()
        return self._results.copy()
