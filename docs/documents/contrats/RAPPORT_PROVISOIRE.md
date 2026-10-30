# Rapport provisoire

Code du type : `RAPPORT_PROVISOIRE` — version du contrat : 1

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
| `rapport` | bloc | Identification du rapport |
| `rapport.numero_version` | texte | Numéro de version du rapport |
| `rapport.mention_correction` | texte | Mention du rapport corrigé (vide sinon) |
| `rapport.provisoire` | texte | « Oui » pour le rapport provisoire, sinon vide |
| `rapport.date_limite_reponses` | texte | Date limite des réponses (JJ/MM/AAAA) |
| `sections` | bloc | Sections rédigées par l'équipe |
| `sections.synthese` | texte long | Synthèse pour l'encadrement supérieur |
| `sections.appreciation` | texte | Appréciation globale |
| `sections.commentaire_appreciation` | texte long | Commentaire de l'appréciation |
| `sections.contexte` | texte long | Contexte |
| `sections.objectifs` | texte long | Objectifs |
| `sections.perimetre` | texte long | Périmètre |
| `sections.methodologie` | texte long | Méthodologie |
| `sections.conclusion` | texte long | Conclusion |
| `sections.annexes` | texte long | Annexes |
| `constats` | liste | Constats validés, par niveau décroissant puis référence |
| `constats[].reference` | texte | Référence du constat |
| `constats[].titre` | texte | Titre du constat |
| `constats[].entite` | texte | Entité concernée |
| `constats[].niveau` | texte | Niveau de risque |
| `constats[].fait_constate` | texte long | Fait constaté |
| `constats[].referentiel` | texte long | Référentiel |
| `constats[].causes_texte` | texte long | Causes, par catégorie |
| `constats[].consequence` | texte long | Conséquence |
| `constats[].conclusion` | texte long | Conclusion |
| `constats[].position_audite` | texte long | Position de l'audité sur le constat |
| `constats[].reponse_direction` | texte long | Réponse de la direction au rapport provisoire |
| `constats[].recommandations_texte` | texte long | Recommandations, une par ligne |
| `constats[].plan_actions` | liste | Actions correctives du constat |
| `constats[].plan_actions[].reference` | texte | Référence de l'action (A-nn) |
| `constats[].plan_actions[].libelle` | texte long | Mesure corrective |
| `constats[].plan_actions[].responsable` | texte | Responsable |
| `constats[].plan_actions[].echeance` | texte | Échéance (JJ/MM/AAAA) |
| `constats[].plan_actions[].indicateur` | texte long | Indicateur de mise en œuvre |
| `points_forts` | liste | Points forts relevés |
| `points_forts[].code` | texte | Code du test |
| `points_forts[].libelle` | texte | Libellé du test |
| `points_forts[].commentaire` | texte long | Commentaire de conclusion |
| `totaux` | bloc | Totaux du rapport |
| `totaux.nb_constats` | texte | Nombre de constats |
| `totaux.nb_eleves` | texte | Constats de niveau élevé |
| `totaux.nb_moyens` | texte | Constats de niveau moyen |
| `totaux.nb_faibles` | texte | Constats de niveau faible |
| `totaux.nb_recommandations` | texte | Nombre de recommandations |
| `totaux.nb_actions` | texte | Nombre d'actions correctives |
| `engagements` | liste | Engagement de chaque responsable sur ses actions (rapport final) |
| `engagements[].responsable` | texte | Responsable |
| `engagements[].nb_actions` | texte | Nombre d'actions |
| `engagements[].etat` | texte | État de l'engagement |
| `validation` | bloc | Validation du rapport par le RAI (vide tant que le rapport n'est pas validé) |
| `validation.par` | texte | Personne ayant validé |
| `validation.le` | texte | Date de validation (JJ/MM/AAAA) |
| `validation.heure` | texte | Heure de validation (HH:MM) |
| `validation.empreinte` | texte | Empreinte SHA-256 de la confirmation |
| `validation.mode` | texte | Mode de signature |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in constats %}`, `{{ l.reference }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
