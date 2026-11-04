# Guide du formateur

## 1. Avant la session

### 1.1 Environnement
Utiliser une pile de **recette** dédiée (jamais la base de développement `onea`, jamais la production) :

1. Démarrer la pile : `scripts/recette/up.sh` (voir `docs/exploitation/runbook.md` §10 « Banc de
   recette »), puis créer l'administrateur par `creer_administrateur` et, depuis l'écran *Utilisateurs*,
   les comptes des participants (`docs/recette.md`, section « Comptes »). Chacun choisit son mot de
   passe définitif à sa première connexion : prévoir ce temps au début de la session.
2. Peupler une base vide avec les données fictives de formation, depuis le conteneur web :
   `python manage.py peupler_demo --profil formation --recette`
   (la commande refuse la production et refuse une base qui contient déjà des objets métier).
3. Donner un mot de passe aux comptes de formation. La commande `peupler_demo` crée des comptes locaux à mot de
   passe temporaire (72 h, à changer à la première connexion). Avec le profil `volumetrie`, elle affiche **une seule
   fois** le mot de passe temporaire de `admin`, `rai`, `auditeur1`, `auditeur2`, `audite1` et `dg` : le noter
   aussitôt. Les autres comptes (profil `formation` : `formation.rai`, `formation.auditeur1`…) n'en reçoivent
   aucun visible : l'administrateur réinitialise leur mot de passe depuis l'écran *Utilisateurs* (manuel de
   l'administrateur §2.6) et le remet à chaque participant. Si le mot de passe d'un compte `admin` est perdu ou
   expiré, relancer `python manage.py creer_administrateur --identifiant admin`.
4. Vérifier la connexion de chaque compte du tableau ci-dessous (chacun choisit son mot de passe définitif à la
   première connexion).

| Compte | Rôle | Mot de passe |
|---|---|---|
| `admin` | Administrateur | temporaire, affiché une fois (voir ci-dessus) |
| `rai` | RAI | temporaire, affiché une fois |
| `auditeur1` | Auditeur (chef de mission dans les exercices) | temporaire, affiché une fois |
| `auditeur2` | Auditeur | temporaire, affiché une fois |
| `audite1` | Audité | temporaire, affiché une fois |
| `dg` | Direction générale | temporaire, affiché une fois |

Les mots de passe temporaires sont propres à l'environnement de formation (jamais ceux de la production) et
valables 72 heures : créer ou réinitialiser les comptes la veille ou le matin de la session. Le courrier de la
recette (codes de connexion, « Mot de passe oublié », courriels de bienvenue) se lit dans Mailpit
(`docs/recette.md`). Ces courriels sont envoyés par le `worker` Celery : vérifier avant la session qu'il est
démarré, sinon l'écran annonce un courriel « mis en file d'envoi » qui n'arrive jamais. L'exercice de délégation
(fiche administrateur, exercice 3) suppose les comptes `rai` et `dg` existants : un délégué ne doit pas pouvoir y
toucher.

### 1.2 Salle et participants
Postes, salle, nombre de participants : voir [programme-demi-journee.md](programme-demi-journee.md),
rubrique logistique, **à renseigner par l'ONEA**. Prévoir un navigateur récent par poste, l'accès
réseau à la pile de recette, et une répartition des participants par compte (un compte par binôme au
plus, pour que les exercices à plusieurs rôles se déroulent sans conflit).

**Message à faire passer pendant la formation** (détails : [manuels/README.md](../manuels/README.md#session-déconnexion-et-onglets)) :
la session reste ouverte tant que l'agent tape ou clique, mais une saisie non enregistrée est perdue après plus de
30 minutes sans frappe ni clic (pause, réunion) : enregistrer avant de s'absenter. Sur un poste partagé, toujours
« Se déconnecter » ; si l'écran annonce que la déconnexion n'a pas pu être confirmée, fermer le navigateur. Une
connexion ou une déconnexion s'applique à tous les onglets du même navigateur : on ne travaille pas sous deux
comptes dans deux onglets d'un même navigateur (prendre un autre navigateur ou une fenêtre de navigation privée).

### 1.3 Matériel
Imprimer ou diffuser : le manuel du rôle, la fiche d'exercices du rôle, le glossaire. Le questionnaire
[evaluation.md](evaluation.md) se distribue en fin de session ; le corrigé reste chez le formateur.

## 2. Principes d'animation
- Un rôle par fiche ; l'exercice commence toujours par une démonstration de 5 à 10 minutes, puis la
  manipulation par les participants.
- Faire constater le résultat attendu à l'écran avant de passer à l'étape suivante.
- Rappeler les règles structurantes : piste d'audit (rien ne se supprime physiquement), « le valideur
  n'est jamais l'auteur », jalons validés par le RAI, confirmation horodatée (pas de signature PAdES).
- La plateforme ne comporte aucune fonction d'intelligence artificielle : le dire explicitement si la
  question est posée.
- Noter chaque écart entre le manuel et l'écran dans un relevé (fichier à tenir par le formateur) : il
  alimente la rubrique « À confirmer » des manuels.

## 3. Fil rouge
Les fiches d'exercices suivent une mission unique jouée par rôles, sur les données fictives de la
formation : le RAI prépare et lance, l'auditeur conduit les étapes, l'audité répond et propose des
actions, le DG consulte. Les libellés précis des missions du jeu de données ne sont pas fixés dans ce
kit : **le formateur relève, avant la session, le nom des missions présentes** (menu « Missions »)
et les reporte sur la fiche. Le jeu de formation contient six missions réparties sur les phases ; choisir
une mission au bon statut pour chaque exercice (indiqué en tête de fiche).

## 4. Réinitialisation entre deux sessions
Objectif : revenir à un état identique en moins de 15 minutes (cible du plan, **non mesurée**).

1. Exécuter `sh scripts/recette/down.sh` : il supprime conteneurs, volumes, dossier de documents
   et `.recette/` du projet `onea-recette` (lu dans le script).
2. Relancer les étapes 1.1 (pile, comptes, `peupler_demo`). La graine par défaut (2026) rend le jeu
   de données reproductible.

Ne jamais exécuter ces commandes sur la pile de développement ni sur la production.

## 5. Évaluation
Faire passer [evaluation.md](evaluation.md) (QCM par rôle) en fin de demi-journée. Seuil de réussite :
**non fixé par ce kit**, à décider par l'ONEA (proposition : 70 %).
