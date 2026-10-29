# PV de la réunion d'ouverture

Code du type : `PV_OUVERTURE` — version du contrat : 1

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
| `reunion` | bloc | Réunion d'ouverture |
| `reunion.date` | texte | Date de la réunion (JJ/MM/AAAA) |
| `reunion.heure` | texte | Heure de la réunion (HH:MM) |
| `reunion.lieu` | texte | Lieu de la réunion |
| `reunion.ordre_du_jour` | texte long | Ordre du jour |
| `reunion.decisions` | texte long | Décisions prises |
| `reunion.compte_rendu` | texte long | Compte rendu |
| `reunion.tenue_le` | texte | Date à laquelle la réunion a été tenue |
| `reunion.participants` | liste | Participants |
| `reunion.participants[].nom` | texte | Nom du participant |
| `reunion.participants[].fonction` | texte | Fonction |
| `reunion.participants[].direction` | texte | Direction (code) |
| `reunion.participants_externes` | liste | Participants externes |
| `reunion.redacteur` | texte | Rédacteur du PV (chef de mission) |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
