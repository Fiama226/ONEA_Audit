# Fiche d'exercices — Administrateur fonctionnel (compte `admin`, mot de passe `onea2026`)

Manuel de référence : [manuel-administrateur.md](../manuels/manuel-administrateur.md). Durée indicative : 2 h.
Rappel : le rôle d'un utilisateur est attribué dans l'annuaire (Keycloak), pas dans la plateforme.

## Exercice 1 — Utilisateurs (manuel §2)
1. « Administration », « Utilisateurs » (`/administration/utilisateurs`).
2. Rechercher `auditeur1`, filtrer par rôle, par statut (« Actifs », « Désactivés »), puis « Effacer les filtres ».
3. Ouvrir un utilisateur et renseigner sa direction, sa fonction et son matricule.
4. Désactiver puis réactiver un compte de test (jamais `admin`).

Résultat attendu : les modifications sont enregistrées et visibles dans l'historique du compte.

## Exercice 2 — Imports (manuel §2.4 et §2.5)
1. Préparer un petit fichier CSV de comptes fictifs (adresses en `@example.org`) selon le format du manuel.
2. L'importer ; lire le compte rendu d'import.
3. Présenter l'import depuis l'annuaire (selon la configuration de la recette).

Résultat attendu : un compte rendu indique les comptes créés et les lignes refusées avec leur motif.

## Exercice 3 — Gabarits et numérotation (manuel §3)
1. « Gabarits de documents » : consulter la liste.
2. Déposer une version d'un gabarit (fichier Word fictif), la prévisualiser, l'activer.
3. Consulter la numérotation des documents (manuel §3.3).

Résultat attendu : la version active change et l'ancienne reste conservée. Rappel : les gabarits actuels
sont provisoires (22 modèles réels de l'ONEA en attente).

## Exercice 4 — Mode de signature et structure (manuel §4 et §5)
Consulter l'écran « Mode de signature » et expliquer la différence avec une signature électronique
(non installée : seule la « Confirmation horodatée » existe). Parcourir la structure du référentiel.

## Questions de synthèse
- Pourquoi un compte ne se supprime-t-il pas ? (piste d'audit, désactivation seulement)
- Où consulter l'historique d'un compte ?
