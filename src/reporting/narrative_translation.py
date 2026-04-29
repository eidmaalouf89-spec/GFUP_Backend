"""
src/reporting/narrative_translation.py
---------------------------------------
Deterministic English → French translation for the three narrative text fields
emitted by narrative_engine.py:

  executive_summary, primary_driver_text, recommended_focus

Rules:
- Static dictionary lookup only. No LLM. No dynamic generation.
- English fields are preserved in the output (untouched). This module only adds
  the three _fr keys as a shallow-copy overlay.
- If a template string is not found in the dictionary, the French field falls
  back to the English original. Never returns None or "" unless the English
  input was already None/"".
- Each dictionary entry corresponds to exactly one template string emitted by
  narrative_engine.py. If narrative_engine.py ever adds a new template, add
  the corresponding entry here — until then the UI renders the English fallback.
"""
from __future__ import annotations

# ── Executive summary ─────────────────────────────────────────────────────────
# Source: narrative_engine._executive_summary() — LIVE_OPERATIONAL ×3 buckets,
#         LEGACY_BACKLOG, ARCHIVED_HISTORICAL, plus the catch-all fallback.
_EXEC_SUMMARY_FR: dict[str, str] = {
    "Active chain with elevated operational pressure requiring near-term attention.":
        "Chaîne active sous pression opérationnelle élevée — action requise à court terme.",
    "Active chain showing moderate pressure and follow-up need.":
        "Chaîne active sous pression modérée — suivi requis.",
    "Active chain currently under controlled pressure.":
        "Chaîne active sous pression maîtrisée.",
    "Legacy open chain with limited current operational impact.":
        "Chaîne héritée — impact opérationnel actuel limité.",
    "Historical closed chain with no current action required.":
        "Chaîne historique close — aucune action requise.",
    "Chain status requires review.":
        "Statut de la chaîne à examiner.",
}

# ── Primary driver ────────────────────────────────────────────────────────────
# Source: narrative_engine._PRIMARY_DRIVER (6 layer codes) + _PRIMARY_DRIVER_NONE.
_DRIVER_FR: dict[str, str] = {
    "Repeated rework or rejection cycles are the main efficiency drag.":
        "Cycles répétés de rejet/reprise — principal frein à l'efficacité.",
    "SAS gate activity is the main contributor to current delay pressure.":
        "Activité au filtre SAS — principal contributeur à la pression de délai.",
    "Primary consultant response timing is the leading active constraint.":
        "Délais de réponse du consultant principal — contrainte active dominante.",
    "Secondary consultant response timing is the leading active constraint.":
        "Délais de réponse du consultant secondaire — contrainte active dominante.",
    "MOEX arbitration or final response timing is the leading constraint.":
        "Délais d'arbitrage / réponse finale MOEX — contrainte active dominante.",
    "Data or report contradictions are reducing workflow clarity.":
        "Contradictions entre données et rapports — clarté du flux dégradée.",
    "No significant active friction signals detected.":
        "Aucun signal de friction active significatif.",
}

# ── Recommended focus ─────────────────────────────────────────────────────────
# Source: narrative_engine._recommended_focus() — ARCHIVED, LEGACY, LIVE high,
#         WAITING_CORRECTED_INDICE, waiting-consultant states, catch-all.
_FOCUS_FR: dict[str, str] = {
    "No immediate action required.":
        "Aucune action immédiate requise.",
    "Review whether administrative closure or archive is appropriate.":
        "Évaluer une clôture administrative ou un archivage.",
    "Prioritize direct unblocking actions and response coordination.":
        "Prioriser le déblocage direct et la coordination des réponses.",
    "Clarify resubmission timing and completeness requirements.":
        "Clarifier le calendrier de resoumission et les exigences de complétude.",
    "Confirm review owner, due date, and pending comments.":
        "Confirmer le propriétaire de revue, la date butoir et les commentaires en attente.",
    "Monitor progress and follow up at next scheduled review cycle.":
        "Suivre l'avancement et relancer au prochain cycle de revue.",
}


def translate_top_issue(issue: dict) -> dict:
    """Return a shallow-copy of `issue` with three additional keys:
    - executive_summary_fr
    - primary_driver_fr
    - recommended_focus_fr
    English keys are preserved untouched. If a template is not in the
    dictionary, the FR field falls back to the English original. Never
    returns None or empty for any of the three FR fields if the EN field
    has a value.
    """
    out = dict(issue)
    en_exec = issue.get("executive_summary") or ""
    en_driver = issue.get("primary_driver_text") or ""
    en_focus = issue.get("recommended_focus") or ""
    out["executive_summary_fr"] = _EXEC_SUMMARY_FR.get(en_exec, en_exec)
    out["primary_driver_fr"] = _DRIVER_FR.get(en_driver, en_driver)
    out["recommended_focus_fr"] = _FOCUS_FR.get(en_focus, en_focus)
    return out
