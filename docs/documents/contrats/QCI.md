# Questionnaire de contrôle interne (QCI)

Code du type : `QCI` — version du contrat : 1

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
| `questionnaires` | liste | Questionnaires de la mission |
| `questionnaires[].titre` | texte | Titre du questionnaire |
| `questionnaires[].processus` | texte | Processus concerné (vide si général) |
| `questionnaires[].themes` | liste | Thèmes |
| `questionnaires[].themes[].theme` | texte | Intitulé du thème |
| `questionnaires[].themes[].questions` | liste | Questions du thème |
| `questionnaires[].themes[].questions[].numero` | texte | Numéro de la question |
| `questionnaires[].themes[].questions[].libelle` | texte | Question |
| `questionnaires[].themes[].questions[].appreciation` | texte | Appréciation : Oui, Non, Sans objet ou vide |
| `questionnaires[].themes[].questions[].reponse` | texte long | Réponse |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in questionnaires %}`, `{{ l.titre }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
