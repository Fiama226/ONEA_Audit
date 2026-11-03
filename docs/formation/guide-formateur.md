# Guide du formateur

## 1. Avant la session

### 1.1 Environnement
Utiliser une pile de **recette** dédiée (jamais la base de développement `onea`, jamais la production) :

1. Démarrer la pile et le realm : `scripts/recette/up.sh` puis `scripts/recette/realm.sh`
   (voir `docs/exploitation/runbook.md` §10 « Banc de recette »).
2. Peupler une base vide avec les données fictives de formation, depuis le conteneur web :
   `python manage.py peupler_demo --profil formation --recette`
   (la commande refuse la production et refuse une base qui contient déjà des objets métier).
3. Vérifier la connexion de chaque compte du tableau ci-dessous.

| Compte | Rôle | Mot de passe |
|---|---|---|
| `admin` | Administrateur | `onea2026` |
| `rai` | RAI | `onea2026` |
| `auditeur1` | Auditeur (chef de mission dans les exercices) | `onea2026` |
| `auditeur2` | Auditeur | `onea2026` |
| `audite1` | Audité | `onea2026` |
| `dg` | Direction générale | `onea2026` |

Le mot de passe `onea2026` est celui des comptes de **développement et de recette** (voir
`docs/HANDOFF.md`). Il ne doit jamais exister en production.

### 1.2 Salle et participants
Postes, salle, nombre de participants : voir [programme-demi-journee.md](programme-demi-journee.md),
rubrique logistique, **à renseigner par l'ONEA**. Prévoir un navigateur récent par poste, l'accès
réseau à la pile de recette, et une répartition des participants par compte (un compte par binôme au
plus, pour que les exercices à plusieurs rôles se déroulent sans conflit).

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

1. Arrêter la pile et supprimer ses volumes : `scripts/recette/down.sh` (vérifier dans le script qu'il
   supprime bien les volumes ; sinon `docker compose ... down -v` sur le projet de recette
   uniquement).
2. Supprimer le dossier de documents de la recette.
3. Relancer les étapes 1.1 (pile, realm, `peupler_demo`). La graine par défaut (2026) rend le jeu
   de données reproductible.

Ne jamais exécuter ces commandes sur la pile de développement ni sur la production.

## 5. Évaluation
Faire passer [evaluation.md](evaluation.md) (QCM par rôle) en fin de demi-journée. Seuil de réussite :
**non fixé par ce kit**, à décider par l'ONEA (proposition : 70 %).
