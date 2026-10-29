# Fiche d'observation

Code du type : `FICHE_OBSERVATION` — version du contrat : 1

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
| `provisoire` | texte | « Oui » tant que le constat n'est pas validé, sinon vide |
| `constat` | bloc | Constat |
| `constat.reference` | texte | Référence du constat (C-01) |
| `constat.titre` | texte | Titre |
| `constat.entite` | texte | Entité concernée |
| `constat.processus` | texte | Processus concerné |
| `constat.fait_constate` | texte long | Fait constaté |
| `constat.referentiel` | texte long | Référentiel (critère) |
| `constat.consequence` | texte long | Conséquence |
| `constat.conclusion` | texte long | Conclusion |
| `constat.niveau` | texte | Niveau du constat (vide tant qu'il n'est pas évalué) |
| `constat.statut` | texte | Statut du constat |
| `constat.soumis_le` | texte | Date de soumission (JJ/MM/AAAA) |
| `constat.validee_le` | texte | Date de validation (JJ/MM/AAAA) |
| `causes` | liste | Causes groupées par catégorie (méthode des 7M) |
| `causes[].categorie` | texte | Catégorie de cause |
| `causes[].descriptions` | liste | Descriptions des causes de la catégorie |
| `recommandations` | liste | Recommandations |
| `recommandations[].numero` | texte | Numéro de la recommandation |
| `recommandations[].libelle` | texte long | Recommandation |
| `recommandations[].priorite` | texte | Priorité |
| `reponse` | bloc | Dernière réponse de l'audité (vide s'il n'a pas répondu) |
| `reponse.position` | texte | Accord ou Désaccord |
| `reponse.commentaire` | texte long | Commentaire de l'audité |
| `reponse.le` | texte | Date de la réponse (JJ/MM/AAAA) |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in causes %}`, `{{ l.categorie }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
