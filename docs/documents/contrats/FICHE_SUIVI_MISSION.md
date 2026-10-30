# Fiche de suivi de la mission

Code du type : `FICHE_SUIVI_MISSION` — version du contrat : 1

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
| `lignes` | liste | Étapes de la mission |
| `lignes[].etape` | texte | Numéro et titre de l'étape |
| `lignes[].statut` | texte | Statut de l'étape |
| `lignes[].debut_prevu` | texte | Début prévu (JJ/MM/AAAA) |
| `lignes[].fin_prevue` | texte | Fin prévue (JJ/MM/AAAA) |
| `lignes[].debut_reel` | texte | Début réel (JJ/MM/AAAA) |
| `lignes[].fin_reelle` | texte | Fin réelle (JJ/MM/AAAA) |
| `lignes[].ecart` | texte | Écart en jours (positif = retard) |
| `lignes[].charge_prevue` | texte | Charge prévue en jours |
| `lignes[].charge_reelle` | texte | Charge réelle en jours |
| `totaux` | bloc | Charges de la mission |
| `totaux.budget_jours` | texte | Budget en jours |
| `totaux.charge_prevue` | texte | Total des charges prévues |
| `totaux.charge_reelle` | texte | Total des charges réelles |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in lignes %}`, `{{ l.etape }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
