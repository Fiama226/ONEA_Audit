# Note synthétique

Code du type : `NOTE_SYNTHETIQUE` — version du contrat : 1

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
| `synthese` | texte long | Note synthétique saisie, à défaut la synthèse du rapport |
| `appreciation` | texte | Appréciation globale |
| `commentaire_appreciation` | texte long | Commentaire de l'appréciation |
| `constats_eleves` | liste | Constats de niveau élevé |
| `constats_eleves[].reference` | texte | Référence du constat |
| `constats_eleves[].titre` | texte | Titre du constat |
| `constats_eleves[].recommandation_principale` | texte long | Recommandation principale |
| `totaux` | bloc | Totaux du rapport |
| `totaux.nb_constats` | texte | Nombre de constats |
| `totaux.nb_eleves` | texte | Constats de niveau élevé |
| `totaux.nb_moyens` | texte | Constats de niveau moyen |
| `totaux.nb_faibles` | texte | Constats de niveau faible |
| `totaux.nb_recommandations` | texte | Nombre de recommandations |
| `totaux.nb_actions` | texte | Nombre d'actions correctives |
| `validation` | bloc | Validation du rapport par le RAI (vide tant que le rapport n'est pas validé) |
| `validation.par` | texte | Personne ayant validé |
| `validation.le` | texte | Date de validation (JJ/MM/AAAA) |
| `validation.heure` | texte | Heure de validation (HH:MM) |
| `validation.empreinte` | texte | Empreinte SHA-256 de la confirmation |
| `validation.mode` | texte | Mode de signature |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in constats_eleves %}`, `{{ l.reference }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
