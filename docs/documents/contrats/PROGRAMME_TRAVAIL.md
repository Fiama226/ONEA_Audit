# Programme de travail

Code du type : `PROGRAMME_TRAVAIL` — version du contrat : 1

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
| `objectifs` | liste | Objectifs d'audit retenus et leurs tests |
| `objectifs[].code` | texte | Code de l'objectif (OA-01) |
| `objectifs[].libelle` | texte | Objectif d'audit |
| `objectifs[].techniques` | texte long | Techniques et sources d'information |
| `objectifs[].criteres_preuve` | texte long | Critères de preuve |
| `objectifs[].commentaire` | texte long | Commentaire |
| `objectifs[].tests` | liste | Tests prévus de l'objectif |
| `objectifs[].tests[].code` | texte | Code du test (T-01) |
| `objectifs[].tests[].libelle` | texte | Libellé du test |
| `objectifs[].tests[].objectif_test` | texte long | Objectif du test |
| `objectifs[].tests[].nature` | texte | Nature du test |
| `objectifs[].tests[].procedure` | texte long | Procédure |
| `objectifs[].tests[].population` | texte long | Population |
| `objectifs[].tests[].taille_echantillon` | texte | Taille de l'échantillon |
| `objectifs[].tests[].methode_selection` | texte | Méthode de sélection |
| `objectifs[].tests[].auditeur` | texte | Auditeur chargé du test |
| `objectifs[].tests[].charge_prevue_jours` | texte | Charge prévue en jours (nombre à la française) |
| `objectifs[].tests[].date_debut_prevue` | texte | Début prévu (JJ/MM/AAAA) |
| `objectifs[].tests[].date_fin_prevue` | texte | Fin prévue (JJ/MM/AAAA) |
| `objectifs[].tests[].complementaire` | texte | Test complémentaire : Oui ou Non |
| `ressources` | liste | Ressources : charge par auditeur |
| `ressources[].auditeur` | texte | Auditeur |
| `ressources[].nb_tests` | texte | Nombre de tests |
| `ressources[].charge_jours` | texte | Charge en jours |
| `tests_sans_auditeur` | liste | Codes des tests sans auditeur |
| `totaux` | bloc | Totaux du programme |
| `totaux.nb_tests` | texte | Nombre de tests prévus |
| `totaux.charge_jours` | texte | Charge totale en jours |
| `totaux.budget_jours` | texte | Budget de la mission en jours |
| `totaux.depassement_budget` | texte | Charge supérieure au budget : Oui ou Non |
| `instantane` | bloc | Dernier instantané validé du programme (vide avant la validation de l'étape X) |
| `instantane.le` | texte | Date de validation (JJ/MM/AAAA) |
| `instantane.par` | texte | Personne ayant validé |
| `instantane.empreinte` | texte | Empreinte SHA-256 de l'instantané |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in objectifs %}`, `{{ l.code }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
