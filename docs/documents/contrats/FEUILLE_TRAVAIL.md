# Feuille de travail

Code du type : `FEUILLE_TRAVAIL` — version du contrat : 1

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
| `test` | bloc | Test prévu |
| `test.code` | texte | Code du test |
| `test.libelle` | texte | Libellé du test |
| `test.objectif_audit` | texte | Objectif d'audit (code et libellé) |
| `test.objectif_test` | texte long | Objectif du test |
| `test.nature` | texte | Nature du test |
| `test.procedure` | texte long | Procédure |
| `test.population` | texte long | Population |
| `test.taille_echantillon` | texte | Taille de l'échantillon prévue |
| `test.methode_selection` | texte | Méthode de sélection |
| `test.auditeur` | texte | Auditeur chargé du test |
| `test.charge_prevue_jours` | texte | Charge prévue en jours |
| `realisation` | bloc | Réalisation du test |
| `realisation.date_realisation` | texte | Date de réalisation (JJ/MM/AAAA) |
| `realisation.travaux_realises` | texte long | Travaux réalisés |
| `realisation.echantillon_teste` | texte long | Échantillon testé |
| `realisation.taille_testee` | texte | Taille testée |
| `realisation.nombre_exceptions` | texte | Nombre d'exceptions |
| `realisation.taux_exception` | texte | Taux d'exception (vide si non calculable) |
| `realisation.resultat` | texte long | Résultat |
| `realisation.conclusion` | texte | Conclusion du test |
| `realisation.commentaire_conclusion` | texte long | Commentaire de la conclusion |
| `realisation.charge_reelle_jours` | texte | Charge réelle en jours |
| `validation` | bloc | Rédaction et validation de la fiche |
| `validation.statut` | texte | Statut de la fiche |
| `validation.auteur` | texte | Auteur de la fiche |
| `validation.soumise_le` | texte | Date de soumission (JJ/MM/AAAA) |
| `validation.soumise_par` | texte | Personne ayant soumis |
| `validation.validee_le` | texte | Date de validation (JJ/MM/AAAA) |
| `validation.validee_par` | texte | Personne ayant validé |
| `constats` | liste | Constats issus de la fiche |
| `constats[].reference` | texte | Référence du constat |
| `constats[].titre` | texte | Titre du constat |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in constats %}`, `{{ l.reference }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
