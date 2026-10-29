# Fiche de test

Code du type : `FICHE_TEST` — version du contrat : 1

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
| `fiche` | bloc | Fiche de test |
| `fiche.date_realisation` | texte | Date de réalisation (JJ/MM/AAAA) |
| `fiche.conclusion` | texte | Conclusion du test |
| `fiche.justification_sans_piece` | texte long | Justification de l'absence de pièce |
| `fiche.statut` | texte | Statut de la fiche |
| `fiche.auteur` | texte | Auteur de la fiche |
| `fiche.soumise_le` | texte | Date de soumission (JJ/MM/AAAA) |
| `fiche.soumise_par` | texte | Personne ayant soumis |
| `fiche.validee_le` | texte | Date de validation (JJ/MM/AAAA) |
| `fiche.validee_par` | texte | Personne ayant validé |
| `pieces` | liste | Pièces justificatives |
| `pieces[].numero` | texte | Numéro de la pièce |
| `pieces[].libelle` | texte | Libellé |
| `pieces[].nom_fichier` | texte | Nom du fichier d'origine |
| `pieces[].empreinte` | texte | Empreinte SHA-256 abrégée (8 premiers…8 derniers caractères) |
| `journal` | liste | Journal des transitions de la fiche |
| `journal[].evenement` | texte | Événement |
| `journal[].le` | texte | Date (JJ/MM/AAAA) |
| `journal[].par` | texte | Personne |
| `journal[].motif` | texte long | Motif |

## Utilisation dans le gabarit Word

- Valeur simple : `{{ mission.reference }}`

- Tableau répété : trois lignes de tableau contenant `{%tr for l in pieces %}`, `{{ l.numero }}` puis `{%tr endfor %}`.

- Les balises inconnues, les fautes de frappe et la syntaxe invalide sont refusées au dépôt du gabarit.
