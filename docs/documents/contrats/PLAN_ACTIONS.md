# Plan d'actions de mise en œuvre des recommandations

Code du type : `PLAN_ACTIONS` — version du contrat : 1

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
| `provisoire` | texte | « Oui » tant que l'étape XVI n'est pas close, sinon vide |
| `recommandations` | liste | Recommandations des constats validés |
| `recommandations[].constat` | texte | Référence du constat |
| `recommandations[].reference` | texte | Référence de la recommandation |
| `recommandations[].priorite` | texte | Priorité |
| `recommandations[].libelle` | texte long | Recommandation |
| `recommandations[].statut` | texte | Statut dérivé des actions |
| `recommandations[].acceptation` | texte long | Justification de l'acceptation du risque (vide sinon) |
| `actions` | liste | Actions correctives |
| `actions[].reference` | texte | Référence de l'action (A-nn) |
| `actions[].recommandation` | texte | Référence de la recommandation |
| `actions[].libelle` | texte long | Mesure corrective |
| `actions[].responsable` | texte | Responsable |
| `actions[].echeance` | texte | Échéance (JJ/MM/AAAA) |
| `actions[].indicateur` | texte long | Indicateur de mise en œuvre |
| `actions[].moyens` | texte long | Moyens (ressources et budget) |
| `actions[].statut` | texte | Statut de l'action |
| `engagements` | liste | Engagement de chaque responsable |
| `engagements[].responsable` | texte | Responsable |
| `engagements[].nb_actions` | texte | Nombre d'actions |
| `engagements[].prochaine_echeance` | texte | Prochaine échéance (JJ/MM/AAAA) |
| `engagements[].etat` | texte | État de l'engagement |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in recommandations %}`, `{{ l.constat }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
