# Rapport d'orientation

Code du type : `RAPPORT_ORIENTATION` — version du contrat : 1

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
| `variante` | texte | Variante : complet ou simplifié |
| `rappel_ordre` | bloc | Rappel de l'ordre de mission |
| `rappel_ordre.objectifs` | texte long | Objectifs |
| `rappel_ordre.perimetre` | texte long | Périmètre |
| `rappel_ordre.exclusions` | texte long | Exclusions |
| `rappel_ordre.clients` | texte long | Clients de la mission |
| `rappel_ordre.livrables_attendus` | texte long | Livrables attendus |
| `rappel_ordre.emis_le` | texte | Date d'émission de l'ordre (JJ/MM/AAAA) |
| `contexte` | texte long | Contexte |
| `approche` | texte long | Approche d'audit |
| `risques_majeurs` | liste | Risques de niveau élevé |
| `risques_majeurs[].code` | texte | Code du risque |
| `risques_majeurs[].libelle` | texte | Libellé du risque |
| `risques_majeurs[].score` | texte | Score |
| `forces` | liste | Forces |
| `forces[].numero` | texte | Numéro |
| `forces[].libelle` | texte | Libellé |
| `forces[].processus` | texte | Processus concerné |
| `forces[].commentaire` | texte long | Commentaire |
| `faiblesses` | liste | Faiblesses |
| `faiblesses[].numero` | texte | Numéro |
| `faiblesses[].libelle` | texte | Libellé |
| `faiblesses[].processus` | texte | Processus concerné |
| `faiblesses[].consequence` | texte long | Conséquence |
| `faiblesses[].commentaire` | texte long | Commentaire |
| `objectifs_retenus` | liste | Objectifs d'audit retenus |
| `objectifs_retenus[].code` | texte | Code de l'objectif (OA-01) |
| `objectifs_retenus[].libelle` | texte | Objectif d'audit |
| `objectifs_retenus[].risque_code` | texte | Code du risque couvert |
| `objectifs_retenus[].controle` | texte long | Contrôle attendu |
| `objectifs_non_retenus` | liste | Objectifs d'audit non retenus |
| `objectifs_non_retenus[].code` | texte | Code de l'objectif (OA-01) |
| `objectifs_non_retenus[].libelle` | texte | Objectif d'audit |
| `objectifs_non_retenus[].motif` | texte | Motif de non-test |
| `objectifs_non_retenus[].justification` | texte long | Justification |
| `couverture` | bloc | Couverture de l'ordre de mission |
| `couverture.valeur` | texte | Couverture exacte ou élargie |
| `couverture.justification` | texte long | Justification |
| `calendrier` | bloc | Calendrier et budget |
| `calendrier.date_debut_prevue` | texte | Date de début prévue (JJ/MM/AAAA) |
| `calendrier.date_fin_prevue` | texte | Date de fin prévue (JJ/MM/AAAA) |
| `calendrier.budget_jours` | texte | Budget en jours |
| `equipe` | liste | Équipe de la mission |
| `equipe[].nom` | texte | Nom |
| `equipe[].role` | texte | Rôle dans la mission |
| `validation_referentiel` | bloc | Validation du référentiel d'audit |
| `validation_referentiel.le` | texte | Date de validation (JJ/MM/AAAA) |
| `validation_referentiel.par` | texte | Personne ayant validé |
| `validation_referentiel.empreinte` | texte | Empreinte SHA-256 de l'instantané validé |
| `observations` | texte long | Observations |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in risques_majeurs %}`, `{{ l.code }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
