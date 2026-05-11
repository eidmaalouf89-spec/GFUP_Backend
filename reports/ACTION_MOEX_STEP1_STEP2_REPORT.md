# ACTION MOEX -- Rapport de modifications Step 1 & Step 2

**Date** : 11 mai 2026
**Auteur** : Eid Maalouf + Claude Code
**Branche** : `main`

---

## Vue d'ensemble

Le module **Action MOEX** (contre-attaque) identifie les documents en retard
dans la chaine de visa et les classe en 4 buckets d'action. Deux etapes de
corrections majeures ont ete realisees.

| Bucket | Avant | Apres | Description |
|---|---|---|---|
| FERMER_MAINTENANT | 712 | **687** | MOEX doit emettre le visa (facile) |
| DECISION_MOEX | 98 | **98** | MOEX doit arbitrer (arbitrage) |
| ENTREPRISE_A_RELANCER | 23 | **107** | Entreprise doit resoumettre |
| CONSULTANT_A_ATTAQUER | 283 | **146** | Consultant en retard |
| **Total** | **1116** | **1038** | |

---

## STEP 1 -- Correction du routage DCC -> Bucket

### Probleme initial

Le builder utilisait les tags DCC de **tous les indices** d'un numero. La
deduplication par `family_key` (`drop_duplicates(keep="first")`) pouvait
selectionner un ancien indice avec un tag perime. Exemple : document 139130
avait le tag "Att Entreprise -- Hors delais" de l'indice C, alors que l'indice
courant D avait le tag "Att BET Secondaire".

### Correction : filtre dernier indice

Ajout d'un filtre dans `build_counter_attack_items()` qui ne conserve que le
dernier indice par numero **avant** l'assignation de bucket :

```python
# counter_attack_builder.py, build_counter_attack_items()
if "latest_indice" in merged.columns:
    li = merged["latest_indice"].map(_norm_key)
    idx = merged["indice"].map(_norm_key)
    merged = merged[(idx == li) | (li == "")].copy()
```

**Impact** : ENTREPRISE_A_RELANCER passe de 23 a 107 (les 84 documents
supplementaires etaient auparavant routes vers d'autres buckets a cause de tags
d'anciens indices).

**Fichier** : `src/reporting/counter_attack_builder.py` lignes 631-634

### Correction : etats terminaux

VOID_CHAIN et ABANDONED_CHAIN ont ete retires de `TERMINAL_STATES`. Ces etats
decrivent une situation (chaine morte depuis 180+ ou 270+ jours) mais ne
doivent pas exclure le document de l'analyse -- au contraire, ils servent a
prioriser le travail.

```python
# Avant
TERMINAL_STATES = {
    "CLOSED_VAO", "CLOSED_VSO", "DEAD_AT_SAS_A",
    "UNKNOWN_CHAIN_STATE", "VOID_CHAIN", "ABANDONED_CHAIN",
}

# Apres
TERMINAL_STATES = {
    "CLOSED_VAO", "CLOSED_VSO", "DEAD_AT_SAS_A",
    "UNKNOWN_CHAIN_STATE",
}
```

**Impact** : 84 documents supplementaires (51 VOID_CHAIN + 33
ABANDONED_CHAIN) reintegres dans les buckets.

**Fichier** : `src/reporting/counter_attack_builder.py` lignes 53-58

### Correction : filtre retard (`days_late > 0`)

Les documents dont le delai de retard est nul ou negatif (encore dans les
delais) n'ont pas leur place dans les buckets d'action. Un filtre a ete
ajoute apres la deduplication :

```python
# counter_attack_builder.py, build_counter_attack_items()
result = result[pd.to_numeric(result["days_late"], errors="coerce").fillna(0) > 0]
```

**Impact** : 162 documents retires (25 FERMER_MAINTENANT + 137
CONSULTANT_A_ATTAQUER). DECISION_MOEX et ENTREPRISE_A_RELANCER inchanges
(tous deja en retard).

**Fichier** : `src/reporting/counter_attack_builder.py` ligne 647

### Logique `_assign_bucket` inchangee

Le corps de `_assign_bucket` est reste identique. Le routage reste :

| DCC primary_tag | Bucket |
|---|---|
| Att MOEX Facile | FERMER_MAINTENANT |
| Att MOEX Arbitrage | DECISION_MOEX |
| Att Entreprise -- Hors delais | ENTREPRISE_A_RELANCER |
| Att BET Primaire | CONSULTANT_A_ATTAQUER |

---

## STEP 2 -- Tags d'alerte (warning_tags)

### Specification

Deux tags d'alerte sont calcules comme **signaux** sur les lignes existantes.
Ils ne modifient jamais le `action_bucket` et ne s'appliquent qu'aux buckets
MOEX (FERMER_MAINTENANT, DECISION_MOEX).

| Tag | Condition | Signification |
|---|---|---|
| Secondaire expire | `secondary_wait_days > 10` | Le secondaire attend depuis plus de 10 jours apres reponse du primaire |
| MOEX interne | Secondaire expire + `moex_wait_days > 30` | MOEX silencieux depuis plus de 30 jours |

**Invariant** : MOEX interne implique toujours Secondaire expire (sous-ensemble
strict).

### Implementation

**Fonction de calcul** (`counter_attack_builder.py`) :

```python
def _compute_warning_tags(row: pd.Series, bucket: str) -> str:
    if bucket not in ("FERMER_MAINTENANT", "DECISION_MOEX"):
        return ""
    secondary_wait = _safe_int(row.get("secondary_wait_days"))
    if secondary_wait <= 10:
        return ""
    tags = ["Secondaire expire"]
    moex_wait = _safe_int(row.get("moex_wait_days"))
    if moex_wait > 30:
        tags.append("MOEX interne")
    return ", ".join(tags)
```

**Colonne ajoutee** : `warning_tags` (position 30 dans `OUTPUT_COLUMNS`),
chaine comma-separated.

**Fichier** : `src/reporting/counter_attack_builder.py` lignes 358-368

### Propagation vers l'API et l'UI

**Read API** (`counter_attack_query.py`) : le champ `warning_tags` est
transmis dans les payloads `_row_to_queue_row()` (queue) et
`get_counter_attack_item()` (detail).

**UI** (`counter_attack.jsx`) : les tags sont rendus comme chips dans
`AmQueueRow` :

```jsx
{row.warning_tags && row.warning_tags.split(',').map(function(t) {
  var tag = t.trim();
  return tag ? <AmChip key={tag} tone="accent">{tag}</AmChip> : null;
})}
```

### Comptages valides

| Tag | FERMER | DECISION | ENTREPRISE | CONSULTANT | Total |
|---|---|---|---|---|---|
| Secondaire expire | 682 | 98 | 0 | 0 | **780** |
| MOEX interne | 6 | 1 | 0 | 0 | **7** |

---

## Correction REF dormant (contractor_quality.py)

### Probleme

`_dormant_list()` comptait comme REF dormant tout document ayant
`_visa_global = REF` sur `dernier_df`. Deux bugs :

1. **`dernier_df` contient tous les indices**, pas seulement le dernier
   (4360 lignes pour 2554 numeros, toutes marquees
   `is_dernier_indice=True`). Des REF d'anciens indices (ex: 128111/C et D)
   etaient comptes alors que le dernier indice (E) avait VAO.
2. **43 documents ENTREPRISE_A_RELANCER n'existent pas sur `dernier_df`**
   (chemin de donnees different), donc jamais comptabilises.

**Resultat** : REF dormant = 277, ENTREPRISE_A_RELANCER = 107. Ecart de 170.

### Correction

La source de verite pour les REF dormant est desormais l'artefact
contre-attaque (`COUNTER_ATTACK_ITEMS.csv`, bucket ENTREPRISE_A_RELANCER).
Nouvelle fonction :

```python
def _load_dormant_ref_from_artifact(contractor_code: str) -> list:
    # Charge l'artefact, filtre par ENTREPRISE_A_RELANCER + emetteur_code
    ...
```

Utilisee dans `build_contractor_quality()` et
`build_contractor_quality_peer_stats()` a la place de
`_dormant_list(..., "REF", ...)`.

`_dormant_list()` reste en service pour **SAS REF** uniquement (pas
d'equivalent dans l'artefact contre-attaque). Elle inclut desormais un filtre
dernier-indice interne pour eviter le meme probleme.

**Resultat** : REF dormant = **107** = ENTREPRISE_A_RELANCER. Les memes
documents sont distribues par emetteur dans les fiches consultant.

**Fichier** : `src/reporting/contractor_quality.py` lignes 254-334, 402-421,
503-521

---

## Scripts de diagnostic

Deux scripts de validation independants dans `scripts/diag/` :

### step1_equality_check.py

Reproduit le pipeline complet du builder (merge, filtre CLOSED, filtre
dernier indice, assign bucket, dedup, filtre days_late > 0) et compare
les comptages avec l'artefact sur disque. Verifie :

- Egalite pipeline/artefact par bucket (delta = 0)
- Absence de buckets supprimes (MOEX_SHAME_INTERNAL, SECONDAIRE_EXPIRE,
  SUJET_REUNION)
- Absence d'etats terminaux dans l'artefact
- Absence de doublons (numero+indice, family_key, item_id)
- Tags non emis par design

### step2_tag_check.py

Valide les warning_tags sur l'artefact :

- Comptages par tag et par bucket
- Invariant de sous-ensemble (MOEX interne => Secondaire expire)
- Pas de tags sans bucket
- Comptages de buckets conformes aux baselines Step 1

Les deux scripts retournent `ALL GATES PASSED` avec les comptages actuels.

---

## Resume des fichiers modifies

| Fichier | Modifications |
|---|---|
| `src/reporting/counter_attack_builder.py` | Filtre dernier indice, TERMINAL_STATES reduit, `_compute_warning_tags`, filtre `days_late > 0`, colonne `warning_tags` dans OUTPUT_COLUMNS |
| `src/reporting/counter_attack_query.py` | `warning_tags` ajoute dans `_row_to_queue_row` et `get_counter_attack_item` |
| `src/reporting/contractor_quality.py` | `_load_dormant_ref_from_artifact`, filtre dernier indice dans `_dormant_list`, source REF dormant = artefact |
| `ui/jansa/counter_attack.jsx` | Rendu chips warning_tags dans AmQueueRow |
| `scripts/diag/step1_equality_check.py` | Nouveau script diagnostic Step 1 |
| `scripts/diag/step2_tag_check.py` | Nouveau script diagnostic Step 2 |

---

## Baselines finales (11 mai 2026)

```
FERMER_MAINTENANT:     687
DECISION_MOEX:          98
ENTREPRISE_A_RELANCER: 107
CONSULTANT_A_ATTAQUER: 146
─────────────────────────
Total:                1038

Secondaire expire:     780  (682 FERMER + 98 DECISION)
MOEX interne:            7  (6 FERMER + 1 DECISION)
REF dormant:           107  (= ENTREPRISE_A_RELANCER)
```
