# Grille de séparation des tâches

Code du type : `GRILLE_SEPARATION_TACHES` — version du contrat : 1

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
| `grilles` | liste | Grilles de séparation des tâches (une par processus) |
| `grilles[].processus` | texte | Processus |
| `grilles[].acteurs` | liste | Acteurs (colonnes) |
| `grilles[].lignes` | liste | Tâches (lignes) |
| `grilles[].lignes[].tache` | texte | Tâche |
| `grilles[].lignes[].roles_par_acteur` | liste | Rôles de chaque acteur, dans l'ordre des acteurs : E, A, En, C séparés par « / » |
| `grilles[].cumuls` | liste | Cumuls de rôles incompatibles |
| `grilles[].cumuls[].tache` | texte | Tâche |
| `grilles[].cumuls[].acteur` | texte | Acteur |
| `grilles[].cumuls[].roles` | texte | Rôles cumulés |
| `grilles[].taches_sans_acteur` | liste | Tâches sans acteur |
| `grilles[].taches_multi_executants` | liste | Tâches à plusieurs exécutants |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in grilles %}`, `{{ l.processus }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
