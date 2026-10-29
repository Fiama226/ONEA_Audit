# Ordre de mission

Code du type : `ORDRE_MISSION` — version du contrat : 1

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
| `ordre` | bloc | Ordre de mission tel que confirmé |
| `ordre.objectifs` | texte long | Objectifs de la mission |
| `ordre.perimetre` | texte long | Périmètre de la mission |
| `ordre.exclusions` | texte long | Exclusions |
| `ordre.clients` | texte long | Clients de la mission |
| `ordre.livrables_attendus` | texte long | Livrables attendus |
| `ordre.periode` | texte | Période auditée |
| `ordre.date_debut_prevue` | texte | Date de début prévue (JJ/MM/AAAA) |
| `ordre.date_fin_prevue` | texte | Date de fin prévue (JJ/MM/AAAA) |
| `ordre.equipe` | liste | Équipe de la mission |
| `ordre.equipe[].nom` | texte | Nom de l'intervenant |
| `ordre.equipe[].role` | texte | Rôle dans la mission |
| `signature` | bloc | Confirmation horodatée de l'ordre |
| `signature.signataire` | texte | Nom du signataire |
| `signature.fonction` | texte | Fonction du signataire |
| `signature.date` | texte | Date de la confirmation (JJ/MM/AAAA) |
| `signature.heure` | texte | Heure de la confirmation (HH:MM) |
| `signature.empreinte` | texte | Empreinte SHA-256 de la confirmation |
| `signature.texte` | texte long | Texte confirmé |
| `signature.mode` | texte | Mode de signature |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
