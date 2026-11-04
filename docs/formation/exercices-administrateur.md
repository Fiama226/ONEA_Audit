# Fiche d'exercices — Administrateur fonctionnel (compte `admin`, mot de passe fourni par le formateur)

Manuel de référence : [manuel-administrateur.md](../manuels/manuel-administrateur.md). Durée indicative : 2 h.
Rappel : les comptes sont créés et gérés dans la plateforme (pas d'annuaire externe) ; le rôle s'attribue à la
création et se modifie dans la fiche du compte.

## Exercice 1 — Première connexion et mot de passe (manuel §1)
1. Se connecter avec le mot de passe temporaire remis par le formateur ; à l'écran « Changer le mot de passe »,
   choisir un nouveau mot de passe d'au moins 12 caractères.
2. Se déconnecter, puis tester « Mot de passe oublié ? » : indiquer un identifiant, lire le message affiché
   (identique que le compte existe ou non), saisir le code reçu dans Mailpit (recette) et choisir un mot de passe.
3. Ouvrir « Mon compte » : repérer « Changer mon mot de passe » et le réglage « Demander un code par courriel à
   chaque connexion ».

Résultat attendu : connexion réussie avec le nouveau mot de passe ; le message de « Mot de passe oublié » ne
révèle pas l'existence du compte.

## Exercice 2 — Utilisateurs (manuel §2.1 à §2.4)
1. « Administration », « Utilisateurs » (`/administration/utilisateurs`).
2. Rechercher `auditeur1`, filtrer par rôle, par statut (« Actifs », « Désactivés »), puis « Effacer les filtres ».
3. « Nouvel agent » : créer un agent fictif (identifiant sans accent, adresse en `@example.org`, rôle obligatoire) ;
   observer le mot de passe temporaire affiché une seule fois, ou le message indiquant que le courriel de bienvenue
   a été **mis en file d'envoi** (il arrive ensuite dans Mailpit, en recette) ; le noter.
4. Ouvrir la fiche d'un utilisateur et renseigner sa direction, sa fonction et son matricule ; changer le rôle de l'agent fictif.
5. Réinitialiser le mot de passe de l'agent fictif (§2.6), puis le désactiver et le réactiver (jamais `admin`).

Résultat attendu : les modifications sont enregistrées et visibles dans l'historique du compte ; le mot de passe
temporaire n'est plus consultable après fermeture de la fenêtre.

## Exercice 3 — Import CSV et délégation (manuel §2.5 et §2.7)
1. Préparer un petit fichier CSV de comptes fictifs (adresses en `@example.org`) selon le format du manuel.
2. « Vérifier le fichier », puis « Importer » ; lire le compte rendu d'import.
3. « Télécharger le fichier des mots de passe » (une seule fois) ; constater qu'un second téléchargement est refusé.
4. Sur la fiche d'un agent fictif, déléguer les droits « Créer des comptes » et « Réinitialiser les mots de passe et
   désactiver le code de connexion » ; se connecter avec cet agent et vérifier qu'il peut réinitialiser un audité ou
   un auditeur, mais pas un administrateur, ni le compte `rai`, ni le compte `dg` (aucun bouton d'action sur ces
   fiches) ; créer un compte et constater que seuls les rôles Auditeur interne et Audité sont proposés ; retirer
   ensuite les droits.

Résultat attendu : un compte rendu indique les comptes créés et les lignes refusées avec leur motif ; le fichier de
mots de passe n'est téléchargeable qu'une fois ; le délégué ne gère que les comptes auditeur et audité : il ne peut
agir ni sur un administrateur, ni sur le RAI, ni sur le DG, ni attribuer ces rôles.

## Exercice 4 — Gabarits et numérotation (manuel §3)
1. « Gabarits de documents » : consulter la liste.
2. Déposer une version d'un gabarit (fichier Word fictif), la prévisualiser, l'activer.
3. Consulter la numérotation des documents (manuel §3.3).

Résultat attendu : la version active change et l'ancienne reste conservée. Rappel : les gabarits actuels
sont provisoires (22 modèles réels de l'ONEA en attente).

## Exercice 5 — Mode de signature et structure (manuel §4 et §5)
Consulter l'écran « Mode de signature » et expliquer la différence avec une signature électronique
(non installée : seule la « Confirmation horodatée » existe). Parcourir la structure du référentiel.

## Questions de synthèse
- Pourquoi un compte ne se supprime-t-il pas ? (piste d'audit, désactivation seulement)
- Que faire pour un agent qui ne reçoit plus le code de connexion par courriel ? (désactiver le code sur sa fiche ; seul lui pourra le réactiver)
- Pourquoi ne déléguer « créer des comptes » ou « réinitialiser les mots de passe » qu'à des agents de confiance ?
  (le délégué peut voir un mot de passe temporaire et prendre la main sur un compte auditeur ou audité)
- Pourquoi un délégué ne peut-il pas toucher aux comptes RAI et DG ? (ils valident et signent : seul un
  administrateur les gère)
- Un agent dit ne pas avoir reçu le courriel « mis en file d'envoi » : que faire ? (réinitialiser son mot de passe
  en décochant l'envoi et lui transmettre le mot de passe affiché ; prévenir l'exploitant)
- Où consulter l'historique d'un compte ?
