# Matrice d'analyse des risques et contrôles (MARC)

Code du type : `MARC` — version du contrat : 1

Les blocs `onea` et `document` sont communs à tous les documents : voir [COMMUN.md](COMMUN.md). Toutes les valeurs sont des textes déjà formatés (dates `JJ/MM/AAAA`) ; une valeur absente est une chaîne vide.

## Balises

| Balise | Type | Description |
|---|---|---|
| `mission` | bloc | Mission d'audit |
| `mission.reference` | texte | Référence de la mission |
| `mission.titre` | texte | Titre de la mission |
| `mission.type` | texte | Type de mission |
| `mission.processus` | liste | Processus audités |
| `mission.processus[].code` | texte | Code du processus |
| `mission.processus[].libelle` | texte | Libellé du processus |
| `mission.processus_texte` | texte | Processus audités, séparés par des virgules |
| `mission.entites` | liste | Entités auditées |
| `mission.entites[].code` | texte | Code de l'entité |
| `mission.entites[].libelle` | texte | Libellé de l'entité |
| `mission.entites_texte` | texte | Entités auditées, séparées par des virgules |
| `mission.periode` | texte | Période auditée |
| `mission.date_debut_prevue` | texte | Date de début prévue (JJ/MM/AAAA) |
| `mission.date_fin_prevue` | texte | Date de fin prévue (JJ/MM/AAAA) |
| `mission.chef_mission` | texte | Chef de mission |
| `provisoire` | texte | « Oui » tant que le document n'est pas définitif, sinon vide |
| `lignes` | liste | Lignes de la matrice |
| `lignes[].numero` | texte | Numéro de la ligne |
| `lignes[].risque_code` | texte | Code du risque |
| `lignes[].risque_libelle` | texte | Libellé du risque |
| `lignes[].niveau` | texte | Niveau du risque |
| `lignes[].objet_auditable` | texte | Objet auditable |
| `lignes[].operation` | texte | Opération |
| `lignes[].objectif_controle` | texte long | Objectif de contrôle |
| `lignes[].controle_attendu` | texte long | Contrôle attendu |
| `lignes[].controle_existant` | texte long | Contrôle existant |
| `lignes[].composante` | texte | Composante du contrôle interne |
| `lignes[].nature` | texte | Nature du contrôle |
| `lignes[].evaluation` | texte | Évaluation de la conception |
| `lignes[].appreciation` | texte | Force ou faiblesse |
| `lignes[].cle` | texte | Contrôle clé : Oui ou Non |
| `validation` | bloc | Validation du référentiel d'audit (vide tant qu'il n'est pas validé) |
| `validation.le` | texte | Date de validation (JJ/MM/AAAA) |
| `validation.par` | texte | Personne ayant validé |
| `validation.empreinte` | texte | Empreinte SHA-256 de l'instantané validé |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in lignes %}`, `{{ l.numero }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
