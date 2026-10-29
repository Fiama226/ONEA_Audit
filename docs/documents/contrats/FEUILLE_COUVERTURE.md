# Feuille de couverture des tests

Code du type : `FEUILLE_COUVERTURE` — version du contrat : 1

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
| `tests_prevus` | liste | Tests prévus |
| `tests_prevus[].code` | texte | Code du test |
| `tests_prevus[].objectif` | texte | Code de l'objectif d'audit |
| `tests_prevus[].libelle` | texte | Libellé du test |
| `tests_prevus[].nature` | texte | Nature du test |
| `tests_prevus[].auditeur` | texte | Auditeur (« Non affecté » à défaut) |
| `tests_prevus[].statut_fiche` | texte | Statut de la fiche (« Aucune fiche » à défaut) |
| `tests_prevus[].conclusion` | texte | Conclusion du test |
| `tests_prevus[].constats` | texte | Références des constats liés, séparées par des virgules |
| `tests_complementaires` | liste | Tests complémentaires |
| `tests_complementaires[].code` | texte | Code du test |
| `tests_complementaires[].objectif` | texte | Code de l'objectif d'audit |
| `tests_complementaires[].libelle` | texte | Libellé du test |
| `tests_complementaires[].nature` | texte | Nature du test |
| `tests_complementaires[].auditeur` | texte | Auditeur (« Non affecté » à défaut) |
| `tests_complementaires[].statut_fiche` | texte | Statut de la fiche (« Aucune fiche » à défaut) |
| `tests_complementaires[].conclusion` | texte | Conclusion du test |
| `tests_complementaires[].constats` | texte | Références des constats liés, séparées par des virgules |
| `tests_abandonnes` | liste | Tests abandonnés |
| `tests_abandonnes[].code` | texte | Code du test |
| `tests_abandonnes[].objectif` | texte | Code de l'objectif d'audit |
| `tests_abandonnes[].libelle` | texte | Libellé du test |
| `tests_abandonnes[].nature` | texte | Nature du test |
| `tests_abandonnes[].auditeur` | texte | Auditeur (« Non affecté » à défaut) |
| `tests_abandonnes[].statut_fiche` | texte | Statut de la fiche (« Aucune fiche » à défaut) |
| `tests_abandonnes[].conclusion` | texte | Conclusion du test |
| `tests_abandonnes[].constats` | texte | Références des constats liés, séparées par des virgules |
| `tests_abandonnes[].motif` | texte long | Motif de l'abandon |
| `synthese` | bloc | Synthèse de la couverture |
| `synthese.nb_prevus` | texte | Nombre de tests prévus |
| `synthese.nb_complementaires` | texte | Nombre de tests complémentaires |
| `synthese.nb_abandonnes` | texte | Nombre de tests abandonnés |
| `synthese.nb_fiches_validees` | texte | Nombre de fiches validées |
| `synthese.taux_validation` | texte | Part des tests retenus dont la fiche est validée |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in tests_prevus %}`, `{{ l.code }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
