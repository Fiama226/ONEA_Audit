# Scénarios de test et script de démonstration — plateforme d'audit interne ONEA

Document de recette manuelle. Il sert à deux usages :

1. **la démonstration** de la plateforme (section 2, déroulé guidé de 25 minutes) ;
2. **le test par les collègues** (sections 3 à 6 : 104 scénarios classés du plus simple au plus complexe).

Il a été rédigé à partir du code de la branche `develop` (backend `backend/apps/*`, frontend
`frontend/src/features/*`, libellés de `frontend/src/i18n/fr.ts`, plans de lot, revue ASVS
`docs/securite/asvs-l2.md`). **Les scénarios n'ont pas été exécutés par l'auteur du document** :
les résultats attendus sont ceux que le code promet. Tout écart constaté est une anomalie à noter
(section 1.5), pas une erreur du testeur. Ce que le code ne permet pas d'affirmer est marqué
**« à vérifier »** et récapitulé en section 8.

Langue de l'interface : français. Adresse locale : http://localhost:5173.

## Sommaire

1. Mode d'emploi (prérequis, comptes, jeu de données, notation, fiche d'anomalie)
2. Parcours de démonstration guidé (25 minutes)
3. Niveau 1 — Scénarios simples (S1-xx)
4. Niveau 2 — Scénarios courants (S2-xx)
5. Niveau 3 — Scénarios métier : les 18 étapes IFACI et le suivi (S3-xx)
6. Niveau 4 — Scénarios complexes et limites (S4-xx)
7. Matrice des droits attendus rôle × fonctionnalité
8. Limites connues, hors périmètre et points « à vérifier »
9. Récapitulatif de campagne

---

## 1. Mode d'emploi

### 1.1 Prérequis techniques

D'après `docs/HANDOFF.md` §4 (à adapter à votre poste) :

| Élément | Attendu |
|---|---|
| Docker Desktop lancé | conteneurs PostgreSQL, Keycloak et Redis démarrés |
| API Django | `runserver 127.0.0.1:8000` avec `DATABASE_URL` pointant sur **la base de recette** (voir 1.3) |
| Interface | `cd frontend && npm run dev`, puis http://localhost:5173 (utiliser `localhost`, pas `127.0.0.1`) |
| Keycloak | http://127.0.0.1:8180 (administration : `admin` / `admin-dev-password`), realm `onea` |
| Navigateur | Chrome ou Edge récent ; fenêtre d'au moins 1280 px de large ; une fenêtre de navigation privée par compte pour les scénarios à deux utilisateurs |

Services **facultatifs** selon les scénarios. La pile de développement du dépôt
(`make up`, soit `docker compose -f docker/compose.yml -f docker/compose.dev.yml`) définit en plus
Meilisearch, Gotenberg, Mailpit (interface http://127.0.0.1:8025), un worker et un beat Celery ;
la passation ne mentionne que PostgreSQL, Keycloak et Redis : **vérifier avec `docker ps` ce qui
tourne réellement** (V-05). Leur absence n'est pas une anomalie (voir section 8) :

| Service | Nécessaire pour | Sans lui |
|---|---|---|
| Worker Celery + Gotenberg | génération des documents Word/PDF (S2-29, S3-22, rapport final, diffusion) | le document reste « en cours de génération » ou « PDF pas prêt » ; la diffusion du rapport est bloquée |
| Meilisearch | recherche globale (S1-10, S4-24) | message « La recherche est momentanément indisponible » |
| Mailpit / serveur SMTP | e-mails (relances, diffusion) | pas d'e-mail ; les notifications dans la plateforme fonctionnent |
| ClamAV | analyse antivirus des pièces (S4-13) | moteur `aucun` par défaut : aucune analyse |

Avant la campagne, noter dans le tableau de la section 9 la version testée
(`git rev-parse --short HEAD`), le navigateur et la date.

### 1.2 Comptes

Mot de passe commun en développement : `onea2026`. Connexion par le bouton « Se connecter »
(redirection vers Keycloak, puis retour sur l'application).

| Compte | Rôle plateforme | Rôle tenu dans la mission de recette (S3-01) |
|---|---|---|
| `admin` | Administrateur (ADMIN) | n'accède à aucune mission |
| `rai` | Responsable de l'audit interne (RAI) | pilote, valide les jalons, diffuse |
| `auditeur1` | Auditeur (AUDITEUR) | **Chef de mission** |
| `auditeur2` | Auditeur (AUDITEUR) | **Auditeur** (auditeur des tests) |
| `audite1` | Audité (AUDITE) | **Audité** (répond aux constats, porte des actions) |
| `dg` | Direction générale (DG) | lecture : rapports diffusés, tableau de bord DG |

Condition pour tout le niveau 3 : la **direction** du compte `audite1` doit être celle (ou la
direction de rattachement) de l'entité auditée de la mission, sinon l'audité ne peut ni répondre
aux constats ni proposer d'actions (« Ce constat concerne une autre entité que votre direction. » ou
« Votre direction n'est pas renseignée sur votre profil »). Se règle en S2-12 (compte `admin`).
Que Keycloak fournisse l'attribut `direction` pour `audite1` est **à vérifier** (V-02).

### 1.3 Jeu de données

Deux cas.

**Cas A — environnement de développement existant.** Les six comptes existent déjà. La commande de
peuplement le refuse (elle exige une base vide). On part alors des données présentes et on crée ce
qui manque en suivant le niveau 2 (cartographie validée, processus, directions, programme).

**Cas B — base de recette dédiée et vide (recommandé pour la démonstration).** La commande
`python manage.py peupler_demo` (fichier `backend/apps/core/management/commands/peupler_demo.py`)
crée des données fictives par les services métier (piste d'audit alimentée, adresses en
`@example.org`). Elle ne se lance jamais seule.

| Option | Rôle |
|---|---|
| `--profil formation` ou `--profil volumetrie` | **obligatoire** |
| `--echelle X` | facteur de volume, 1 par défaut ; `0.2` suffit pour une démonstration |
| `--graine N` | graine aléatoire, 2026 par défaut (jeu reproductible) |
| `--a-blanc` | affiche le plan sans rien écrire |
| `--recette` | autorise l'environnement « recette » (jamais la production) |
| `--avec-pdf` | convertit aussi les documents en PDF (Gotenberg requis) |

Règles vérifiées dans le code :

- environnement `dev` ou `test` seulement ; `prod` est refusé ;
- **base vide exigée** : la commande s'arrête s'il existe déjà des directions, processus,
  cartographies, programmes, missions, documents, ou l'un des comptes réservés
  (`demo`, `admin`, `rai`, `dg`, `auditeur1`, `audite1`) ; relancée sur une base déjà peuplée, elle ne
  fait rien et ne crée pas de doublon ;
- profil **volumétrie** : crée les comptes `rai`, `dg`, `auditeur1` à `auditeur10`, `audite1` à
  `audite7`, `admin` (plus `charge01`…), **sans mot de passe** : ils se relient au compte Keycloak
  de même identifiant à la première connexion. Ce profil convient donc aux comptes du tableau 1.2 ;
- profil **formation** : crée `formation.rai`, `formation.auditeur1` à `3`, `formation.audite1` et
  `2`, `formation.dg`. Ces identifiants n'existent pas dans Keycloak : il faut les y créer pour s'y
  connecter (V-01) ;
- les missions de démonstration s'arrêtent à l'**étape VIII** au plus (profil formation : un brouillon,
  une planifiée, des missions aux étapes 1, 4, 7 et 8) ; les étapes IX à XVIII, constats,
  recommandations, rapports et suivi ne sont **pas** peuplés (fichiers `demo.py` des lots 6 à 8 : « aucune
  donnée de démonstration »). Les niveaux 3 et 4 se jouent donc en saisissant les données.

Exemple (poste Windows, voir `docs/HANDOFF.md` §4 ; **ne jamais viser la base `onea`**) :

```
# 1. créer une base vide, ex. onea_recette, puis appliquer les migrations
# 2. dans backend/ :
set DATABASE_URL=postgres://onea:onea-dev-password@127.0.0.1:5432/onea_recette
set DJANGO_SETTINGS_MODULE=config.settings.dev
python manage.py migrate
python manage.py peupler_demo --profil volumetrie --echelle 0.2 --a-blanc
python manage.py peupler_demo --profil volumetrie --echelle 0.2
```

Autres commandes utiles à la recette : `import_referentiel <fichier.csv> --user rai` (directions,
départements, processus ; idempotent), `envoyer_relances --simulation [--date AAAA-MM-JJ]` (S3-30),
`verifier_pieces [--mission DAI/2026/M01]` (S4-14), `envoyer_courriel_test <adresse>` (SMTP).

### 1.4 Comment noter un résultat

Chaque scénario se termine par une ligne de cases :

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

- **Réussi** : le résultat attendu est observé en entier.
- **Échec** : au moins un point diffère. Cocher « Échec », noter le n° d'étape fautive dans le
  commentaire et ouvrir une fiche d'anomalie (1.5).
- **N/A** : scénario non applicable (service facultatif absent, voir 1.1 ; donnée manquante). Justifier.
- Les étapes sont numérotées : citer « S3-15 étape 6 » dans les fiches.
- Faire une copie d'écran de chaque échec. Ne jamais cocher « Réussi » sur une étape sautée.
- Les scénarios d'un même niveau 3 se suivent : un échec bloquant en S3-xx peut rendre les suivants
  impossibles ; les marquer N/A avec la mention « bloqué par S3-xx ».

### 1.5 Gabarit de fiche d'anomalie

```
Anomalie n° : ____            Date : __/__/____          Testeur : __________
Scénario / étape : S_-__ / étape _        Version testée (commit) : _______
Compte et rôle : ________      Navigateur : ________      Largeur de fenêtre : ____
Gravité :  [ ] Bloquante (empêche de continuer)  [ ] Majeure (contournement lourd)
           [ ] Mineure (gêne)  [ ] Cosmétique (libellé, alignement)  [ ] Sécurité
Résultat attendu : ______________________________________________
Résultat observé : ______________________________________________
Étapes pour reproduire : 1) …  2) …  3) …
Message d'erreur exact affiché (copier) : ____________
Reproductible ?  [ ] toujours  [ ] parfois  [ ] une fois
Pièces jointes : copie d'écran n° __ ; heure précise : __:__ (pour retrouver la trace serveur)
```

Un échec de sécurité (accès à ce qui devrait être refusé) est toujours « Sécurité » et se signale
immédiatement au responsable du projet.

---

## 2. Parcours de démonstration guidé (25 minutes)

**Principe.** Les 18 étapes ne se jouent pas en 25 minutes. On prépare donc la veille une mission de
recette avancée jusqu'à l'étape XIV en rejouant S3-01 à S3-17, puis on joue en direct la fin de
l'histoire. Les créations courtes (programme, mission, déclaration) sont refaites en direct.

### 2.1 Préparation (la veille, 60 à 90 minutes)

1. Base de recette peuplée (cas B de 1.3, volumétrie, échelle 0,2) ; vérifier S1-02 (les six comptes se connectent).
2. Fixer la direction de `audite1` (S2-12) sur l'entité de la mission de démonstration.
3. Rejouer S3-01 à S3-16 pour une mission « Audit du processus achats » : équipe (`auditeur1` chef,
   `auditeur2` auditeur, `audite1` audité), étapes I à XIII validées, **une fiche de test en anomalie
   validée avec une pièce jointe**. Laisser l'étape XIV vide.
4. Avoir un second navigateur ou profil par compte, déjà connecté : `rai`, `auditeur1`, `audite1`, `dg`.
5. Si Gotenberg et le worker Celery ne tournent pas : prévoir de ne pas montrer la génération PDF (voir 8).
6. Repasser les écrans montrés une fois ; éviter les écrans qui affichent encore « lot 3 », « lot 4 »
   ou « Disponible dans un prochain lot » (V-11).

### 2.2 Déroulé minuté

| Min | Acte | Qui | Ce qu'on montre | Message à faire passer |
|---|---|---|---|---|
| 0–2 | 1. Connexion et tableau de bord | `rai` | « Se connecter » (SSO), tableau de bord du RAI : missions par statut, file de décisions, jalons à valider, cartographie 5×5 | un point d'entrée unique, des rôles distincts, tout est en français |
| 2–4 | 2. Le socle | `rai` | Référentiel › Cartographies (matrice 5×5, niveaux faible 1–7, moyen 8–14, élevé 15–25), comparaison de versions ; Programme annuel (calendrier, validé = figé) | la cartographie validée est figée et versionnée ; le programme découle des risques |
| 4–7 | 3. Créer et lancer une mission | `rai` | Nouvelle mission (S2-21), « Planifier » (référence `DAI/AAAA/Mnn` attribuée), équipe, « Lancer » | la référence est attribuée à la planification et ne sera jamais réutilisée |
| 7–9 | 4. Indépendance | `auditeur2`, puis `rai` | `auditeur2` : bandeau « Confirmez votre déclaration d'indépendance… », déclaration d'un conflit ; `rai` : « Arbitrer » | pas de contribution tant que la déclaration n'est pas levée |
| 9–11 | 5. Ordre de mission | `rai` | Étape I : « Émettre l'ordre de mission », confirmation horodatée avec empreinte | chaque validation est tracée (qui, quand, empreinte) |
| 11–13 | 6. Planification (vue rapide) | `auditeur1` | Sur la mission préparée : étape IV (matrice des risques de la mission), étape V (MARC), jalon VI validé avec empreinte | les 10 étapes de planification sont guidées, les jalons sont validés par le RAI |
| 13–16 | 7. Terrain | `auditeur2`, `rai` | Fiche de test : travaux, conclusion « Anomalie », dépôt d'une pièce (empreinte SHA-256), soumission ; `rai` valide la fiche (jalon XIII) | preuve inaltérable ; l'auteur ne valide pas sa propre fiche |
| 16–19 | 8. Constat | `auditeur1`, `rai` | Créer un constat depuis la fiche anomalie, causes 7M, recommandation, soumettre ; `rai` valide | de la preuve à la recommandation sans ressaisie |
| 19–21 | 9. Rapport provisoire et réponse | `rai`, `audite1` | Transmission du rapport provisoire avec délai ; `audite1` : « Répondre » (accord/désaccord motivé, case « Je confirme ») | contradictoire tracé |
| 21–23 | 10. Rapport et diffusion | `auditeur1`, `rai`, `dg` | Rédaction/soumission, validation par le RAI, liste de diffusion, diffusion ; `dg` : Rapports diffusés, tableau de bord DG | le DG lit sans pouvoir modifier |
| 23–25 | 11. Suivi et clôture | `audite1`, `auditeur2`, `rai` | Plan d'actions, action « Déclarer réalisée » avec preuve, « Vérifier », « Clôturer » ; notifications ; registre exportable | suivi jusqu'à la clôture, relances automatiques |

Si le temps manque, couper les actes 4 et 6. Le dernier acte (11) peut être montré sur des données
préparées.

### 2.3 Questions fréquentes du public (réponses issues du code)

- *Peut-on supprimer une mission ?* Seul un brouillon (« Supprimer le brouillon »). Ensuite : annuler
  avec motif ; les objets métier ne sont jamais supprimés physiquement.
- *Peut-on modifier un rapport validé ?* Non ; le RAI « Émet un rapport corrigé », qui remplace le précédent après nouvelle diffusion.
- *La signature électronique existe-t-elle ?* Le mode « Confirmation horodatée » est actif. La signature
  électronique (PAdES) n'est pas installée (lot 7 bis) : voir 8.
- *Y a-t-il de l'IA ?* Non, par règle du projet.

---

## 3. Niveau 1 — Scénarios simples

### S1-01 — Connexion du RAI
**Rôle** : `rai` · **Préconditions** : navigateur sans session ouverte.
1. Ouvrir http://localhost:5173.
2. Observer la page de connexion : titre « Audit interne ONEA », texte « Connectez-vous avec votre compte ONEA… ».
3. Cliquer « Se connecter ».
4. Sur Keycloak, saisir `rai` / `onea2026`.

**Résultat attendu** : retour sur l'application, tableau de bord du RAI (« Missions par phase » ou « Pilotage… »), nom et rôle visibles dans le menu utilisateur (« RAI »), aucune erreur.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-02 — Connexion de chacun des six comptes
**Rôle** : tous · **Préconditions** : S1-01 réussi.
1. Pour chaque compte (`admin`, `rai`, `auditeur1`, `auditeur2`, `audite1`, `dg`), se connecter dans une fenêtre privée.
2. Relever le titre du tableau de bord et le libellé du rôle dans le menu utilisateur.

**Résultat attendu** : chaque compte arrive sur un tableau de bord **propre à son rôle** : RAI « Pilotage de l'audit interne »/missions par statut ; Auditeur « Mes missions », « Étapes en cours » ; Audité « Constats à répondre », « Mes actions » ; DG « Synthèse de l'audit interne », taux de mise en œuvre ; Admin « Administration de la plateforme » (écran d'attente, V-08). Rôle affiché : Administrateur, RAI, Auditeur, Audité, DG.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-03 — Déconnexion
**Rôle** : `auditeur1` · **Préconditions** : connecté.
1. Ouvrir le menu utilisateur (en haut à droite).
2. Cliquer « Se déconnecter ».
3. Revenir en arrière avec le bouton « Précédent » du navigateur, puis tenter d'ouvrir `/missions`.

**Résultat attendu** : retour à l'écran de connexion ; `/missions` ne s'affiche plus sans nouvelle connexion (redirection vers `/connexion`).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-04 — Identifiants erronés
**Rôle** : aucun · **Préconditions** : déconnecté.
1. « Se connecter », saisir `rai` avec un mauvais mot de passe.
2. Recommencer 2 fois.

**Résultat attendu** : Keycloak refuse chaque tentative avec un message d'erreur ; aucun accès à l'application. (Le verrouillage après 5 échecs est une consigne de production, `docs/exploitation/mise-en-production.md`, non garantie en développement : noter ce qui se passe.)

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-05 — Accès direct sans être connecté
**Rôle** : aucun · **Préconditions** : déconnecté.
1. Taper dans la barre d'adresse `http://localhost:5173/missions`, puis `/programme-annuel`, `/documents`, `/administration/utilisateurs`.

**Résultat attendu** : chaque fois, redirection vers la page de connexion ; aucun contenu métier visible.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-06 — Menu de navigation selon le rôle
**Rôle** : les 5 rôles · **Préconditions** : S1-02.
1. Pour chaque compte, relever les entrées de la barre latérale (groupes « Conduite des missions », « Suivi », « Paramétrage »).
2. Comparer au tableau ci-dessous.

| Entrée | admin | rai | auditeur | audite | dg |
|---|---|---|---|---|---|
| Tableau de bord | oui | oui | oui | oui | oui |
| Programme annuel | oui | oui | oui | non | oui |
| Missions | non | oui | oui | oui | non |
| Référentiel | oui | oui | oui | non | oui |
| Recommandations | non | oui | oui | oui | oui |
| Rapports diffusés | non | oui | oui | oui | oui |
| Documents | non | oui | oui | oui | non |
| Administration | oui | non | non | non | non |
| Gabarits de documents | oui | oui | non | non | non |
| Mode de signature | oui | oui | non | non | non |

**Résultat attendu** : le menu correspond au tableau (source : `frontend/src/layouts/navigation.ts`). Un groupe sans entrée visible disparaît avec son titre.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-07 — Accès refusé par adresse directe
**Rôle** : `audite1`, `dg`, `auditeur1`, `rai`, `admin` · **Préconditions** : connecté.
1. Avec `audite1` : ouvrir `/programme-annuel`, `/referentiel`, `/administration/utilisateurs`.
2. Avec `dg` : ouvrir `/missions`, `/documents`.
3. Avec `auditeur1` : ouvrir `/administration/documents`.
4. Avec `rai` : ouvrir `/administration/utilisateurs`.
5. Avec `admin` : ouvrir `/missions`, `/recommandations`.

**Résultat attendu** : écran « Accès refusé » (« Votre rôle ne donne pas accès à cette page. ») avec le lien « Retour au tableau de bord ». Aucune donnée n'a clignoté avant le refus.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-08 — Page introuvable
**Rôle** : `rai` · **Préconditions** : connecté.
1. Ouvrir `/page-qui-n-existe-pas`.
2. Ouvrir `/missions/00000000-0000-0000-0000-000000000000`.

**Résultat attendu** : étape 1, « Page introuvable » et lien de retour. Étape 2 : message « Mission introuvable. » (pas d'écran blanc, pas de trace technique).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-09 — Habillage : menu replié, fil d'Ariane, lien d'évitement, petit écran
**Rôle** : `rai` · **Préconditions** : connecté.
1. Cliquer « Replier le menu » : le menu passe en icônes ; survoler une icône affiche une infobulle ; « Déplier le menu » restaure.
2. Ouvrir une mission puis une étape : lire le fil d'Ariane (Missions › référence › Étapes…) et cliquer un niveau supérieur.
3. Au clavier, recharger la page puis appuyer sur Tab une fois : un lien « Aller au contenu principal » apparaît ; Entrée place le focus sur le contenu.
4. Réduire la fenêtre sous 1024 px : le menu devient un tiroir (« Ouvrir le menu » / « Fermer le menu »).

**Résultat attendu** : comportements ci-dessus ; aucun défilement horizontal de la page à 375 px de large.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-10 — Recherche globale
**Rôle** : `rai`, `audite1`, `admin` · **Préconditions** : Meilisearch démarré et index construit (`reindexer`), sinon N/A (V-13).
1. Dans l'en-tête, saisir 1 seul caractère puis Entrée.
2. Saisir un fragment de titre de mission (ex. « achats ») puis Entrée.
3. Filtrer par type (« Missions », « Constats », « Recommandations », « Actions », « Documents »).
4. Avec `audite1`, répéter la recherche.
5. Avec `admin`, tenter la recherche.

**Résultat attendu** : 1) « Saisissez au moins 2 caractères. » ; 2) liste de résultats cliquables menant à l'objet ; 4) `audite1` ne voit pas les objets internes à l'équipe (le filtre de droits est appliqué) ; 5) « La recherche n'est pas disponible pour votre profil. » (l'ADMIN est exclu). Sans Meilisearch : « La recherche est momentanément indisponible. Réessayez plus tard. »

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-11 — Cloche de notifications
**Rôle** : `audite1` (après S3-19 ou S3-24) · **Préconditions** : au moins une notification reçue.
1. Repérer la cloche : « Notifications, N non lues » (« 9+ » au-delà de 9).
2. Ouvrir le menu : « Dernières notifications ».
3. Cliquer une notification : on est conduit à l'objet concerné.
4. Cliquer « Tout marquer comme lu ».

**Résultat attendu** : le compteur diminue puis disparaît. Sans notification : « Aucune notification. »

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-12 — Page des notifications
**Rôle** : `rai` · **Préconditions** : plusieurs notifications (suivi ouvert, action déclarée, report demandé…).
1. Ouvrir « Voir toutes les notifications » (`/notifications`).
2. Basculer entre « Non lues » et « Toutes ».
3. Si plus d'une page : « Page suivante » / « Page précédente ».

**Résultat attendu** : liste paginée, mention « Non lue » sur les nouvelles, titres du type « Action déclarée réalisée », « Report demandé », « Mission à clôturer » ; liste vide : « Vous n'avez aucune notification. »

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S1-13 — Un compte ne voit que ses notifications
**Rôle** : `auditeur2`, `audite1` · **Préconditions** : S1-11.
1. Noter le contenu de la page Notifications de `audite1`.
2. Se connecter avec `auditeur2` et ouvrir la page Notifications.

**Résultat attendu** : les notifications de `audite1` n'apparaissent pas chez `auditeur2`.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

---

## 4. Niveau 2 — Scénarios courants

### 4.A Référentiel

### S2-01 — Consulter directions, processus et objets auditables (lecture)
**Rôle** : `dg`, puis `auditeur1` · **Préconditions** : données de référentiel présentes.
1. Ouvrir Référentiel : onglets Cartographies, Processus, Directions, Objets auditables.
2. Processus : chercher par code ou libellé, filtrer par famille.
3. Ouvrir un processus.
4. Objets auditables : choisir un processus, parcourir l'arbre (domaines › opérations) aux flèches haut/bas.

**Résultat attendu** : tout est consultable ; **aucun bouton** de création/modification/suppression ; mention « Votre rôle donne un accès en lecture seule ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-02 — Créer, modifier, supprimer un processus
**Rôle** : `rai` (puis `admin`) · **Préconditions** : au moins une direction.
1. Processus › « Créer un processus ». Saisir un code de 3 lettres majuscules (ex. `ZZT`), un libellé, une famille, cocher des directions rattachées.
2. Enregistrer, puis rouvrir : le code est verrouillé (« Le code ne peut plus être modifié après la création »).
3. Modifier le libellé.
4. « Supprimer le processus » et confirmer.

**Résultat attendu** : création, modification et suppression logique réussies, tracées ; processus disparu de la liste. `admin` voit les mêmes boutons (écriture de la structure : RAI et ADMIN).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-03 — Validation des codes du référentiel
**Rôle** : `rai` · **Préconditions** : S2-02.
1. Créer un processus avec le code `a1`, puis `ABCDEFG`, puis `ÉCO`.
2. Laisser libellé et famille vides.
3. Créer une direction avec le code `1ABC`.

**Résultat attendu** : messages de champ : « Deux à cinq lettres majuscules, sans accent. », « Le libellé est obligatoire. », « Choisissez une famille. », « Une lettre majuscule suivie de 1 à 15 majuscules, chiffres ou tirets… ». Rien n'est enregistré ; le focus se place sur le premier champ en erreur.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-04 — Directions et départements
**Rôle** : `rai` · **Préconditions** : S2-03.
1. Directions › « Ajouter une direction ou un département ».
2. Créer un **département** sans choisir de direction parente.
3. Recommencer en choisissant la direction parente.
4. Modifier puis supprimer ce département.

**Résultat attendu** : étape 2 « Un département doit être rattaché à une direction. » ; étapes 3-4 réussies et tracées.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-05 — Objets auditables
**Rôle** : `rai` puis `admin` · **Préconditions** : un processus.
1. Objets auditables : choisir un processus, « Ajouter un domaine ».
2. Dans ce domaine, « Ajouter une opération ».
3. Modifier, puis supprimer l'opération.
4. Se reconnecter avec `admin` et ouvrir la même page.

**Résultat attendu** : étapes 1-3 réussies. `admin` n'a **pas** de bouton d'édition (écriture réservée au RAI, aligné sur le serveur).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-06 — Créer une cartographie brouillon
**Rôle** : `rai` · **Préconditions** : aucune cartographie du même millésime.
1. Cartographies › « Créer une cartographie » : année (ex. 2027), libellé, source « Aucune » puis, séparément, « Copier les risques de » une version existante.
2. Essayer de créer une seconde cartographie pour la même année.

**Résultat attendu** : version créée en brouillon ; avec une source, les risques sont copiés. Une année déjà utilisée est refusée.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-07 — Ajouter un risque avec calcul du score 5×5
**Rôle** : `rai` · **Préconditions** : brouillon S2-06.
1. « Ajouter un risque » : choisir un processus, saisir un libellé, probabilité 3, impact 5.
2. Lire l'aperçu : « Score 15 » et niveau.
3. Tester les limites : probabilité 2 × impact 3 (score 6, faible) ; 3 × 3 (9, moyen) ; 5 × 5 (25, élevé).
4. Enregistrer ; retrouver le risque dans la matrice 5×5 et la liste (colonnes P, I, Score, Niveau, Priorité).
5. Cliquer une case de la matrice : la liste est filtrée ; « Effacer le filtre ».

**Résultat attendu** : score = probabilité × impact ; niveau faible (1–7), moyen (8–14), élevé (15–25) ; l'aperçu est « indicatif », le serveur recalcule. Libellé vide : « Le libellé est obligatoire. » ; valeur hors 1–5 : « Choisissez une valeur de 1 à 5. »

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-08 — Valider une cartographie (gel)
**Rôle** : `rai` · **Préconditions** : brouillon avec au moins un risque.
1. « Valider la cartographie », lire l'avertissement (figée), « Valider définitivement ».
2. Tenter de modifier ou supprimer un risque, ou d'ajouter un risque.
3. Se reconnecter avec `dg` et ouvrir la cartographie.

**Résultat attendu** : bandeau « Cartographie validée le … par … — lecture seule » ; plus aucun bouton d'édition ; `dg` la consulte en lecture seule. Une cartographie validée devient la « version courante » pour les nouvelles missions.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-09 — Comparer deux cartographies
**Rôle** : `rai` ou `dg` · **Préconditions** : deux versions.
1. Ouvrir une cartographie › « Comparer avec… », choisir une autre version, « Comparer ».

**Résultat attendu** : listes « Risques ajoutés », « Risques retirés », « Risques modifiés » (champ, avant, après) ou « Aucune différence entre les deux cartographies. »

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-10 — Export et impression de la cartographie
**Rôle** : `rai` · **Préconditions** : cartographie avec risques.
1. « Exporter la cartographie » › CSV, puis Excel. Ouvrir les fichiers.
2. « Imprimer » : lire l'aperçu avant impression (A4).

**Résultat attendu** : CSV UTF-8 séparé par « ; » lisible sous Excel (accents corrects) ; classeur Excel ouvert sans alerte ; impression avec pied de page « CONFIDENTIEL · USAGE INTERNE ONEA », page « n sur N ». Voir aussi S4-19 et S4-20.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### 4.B Utilisateurs

### S2-11 — Liste et filtres des utilisateurs
**Rôle** : `admin` · **Préconditions** : plusieurs comptes.
1. Administration › Utilisateurs.
2. Rechercher par nom, identifiant ou matricule.
3. Filtrer par rôle, direction, statut (Actifs, Désactivés, En attente de première connexion), synchronisation Keycloak.
4. « Effacer les filtres ».

**Résultat attendu** : filtres cumulables ; message « Aucun utilisateur ne correspond aux filtres » si vide.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-12 — Fiche utilisateur et profil (direction)
**Rôle** : `admin` · **Préconditions** : compte `audite1` connu.
1. Ouvrir la fiche de `audite1`.
2. Relever identité, origine, première connexion, rôle (texte « Le rôle est attribué dans l'annuaire… »).
3. Renseigner **Direction** (celle de l'entité auditée de la recette), Fonction, Matricule (> 32 caractères pour tester l'erreur).
4. « Enregistrer le profil ».
5. Consulter l'« Historique du compte ».

**Résultat attendu** : le rôle n'est pas modifiable ici ; message « Profil enregistré. » ; la mention précise que direction et fonction sont désormais figées dans la plateforme avec le bouton « Rétablir la synchronisation » ; l'historique liste la modification (date, auteur, changements).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-13 — Désactiver puis réactiver un compte
**Rôle** : `admin` puis le compte visé · **Préconditions** : un compte de test (pas `admin`).
1. Fiche › « Désactiver le compte », motif vide : refus ; saisir un motif ; « Désactiver ».
2. Avec ce compte, tenter de se connecter.
3. Revenir, « Réactiver le compte ».

**Résultat attendu** : motif obligatoire (« Le motif est obligatoire. ») ; compte désactivé = écran « Compte indisponible » à la connexion ; état de synchronisation Keycloak affiché (« sessions fermées » ou échec avec « Relancer la synchronisation ») ; réactivation rétablit l'accès.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-14 — Import CSV de comptes
**Rôle** : `admin` · **Préconditions** : fichier CSV UTF-8 (colonnes `identifiant;email;prenom;nom;role;direction;fonction;matricule`).
1. « Importer un fichier CSV ».
2. Tenter « Importer » sans vérification : refusé (« Vérifiez d'abord le fichier »).
3. « Vérifier le fichier » : lire le rapport « aucun compte n'a encore été créé ».
4. « Importer ».
5. Rejouer avec une ligne `role=ADMIN`, une ligne sans identifiant, un fichier de plus de 1 Mo.

**Résultat attendu** : rapport de vérification puis « Import terminé » (comptes créés, mis à jour, lignes ignorées avec motif) ; le rôle ADMIN n'est jamais attribué par fichier (ligne ignorée) ; fichier trop gros : « Le fichier dépasse 1 Mo. »

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-15 — Import depuis l'annuaire (Keycloak)
**Rôle** : `admin` · **Préconditions** : Keycloak joignable avec le client de synchronisation (V-01).
1. « Importer depuis l'annuaire », chercher avec 1 caractère, puis 2 caractères.
2. Sélectionner des comptes (limite de 50), « Importer la sélection ».
3. Rechercher un compte déjà présent.

**Résultat attendu** : « Saisissez au moins 2 caractères. » ; comptes déjà présents marqués « Déjà présent » ; si l'annuaire est injoignable : « L'annuaire (Keycloak) est momentanément indisponible. »

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### 4.C Programme annuel

### S2-16 — Créer un programme annuel
**Rôle** : `rai` · **Préconditions** : aucun programme pour l'année choisie.
1. Programme annuel › « Créer un programme » : année (4 chiffres), libellé.
2. Essayer l'année `26`, puis une année déjà prise.
3. Modifier libellé et commentaire.

**Résultat attendu** : programme créé en brouillon ; « L'année doit comporter quatre chiffres. » ; année déjà utilisée refusée ; modification possible tant que brouillon.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-17 — Ajouter des missions prévues
**Rôle** : `rai` · **Préconditions** : programme brouillon ; processus existants.
1. « Ajouter une mission prévue » : titre, type (Assurance/Conseil), processus, objet auditable, entités concernées, début et fin prévus, charge (jours), justification.
2. Tester : fin avant début ; début hors de l'année du programme ; charge `-1` ; titre vide ; justification trop longue.
3. Enregistrer et en ajouter deux autres dans des trimestres différents.

**Résultat attendu** : erreurs « La fin prévue doit suivre le début prévu. », « La mission prévue doit commencer pendant l'année AAAA. », « La charge prévue doit être un nombre positif ou nul… », « Le titre est obligatoire. » ; lignes groupées par trimestre avec « n missions prévues ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-18 — Vues liste, calendrier, filtres, synthèse
**Rôle** : `rai`, `auditeur1`, `dg` · **Préconditions** : S2-17.
1. Basculer « Liste » / « Calendrier ».
2. Filtrer par processus, type, trimestre, recherche sur l'intitulé ; « Effacer les filtres ».
3. Lire la synthèse (Assurance/Conseil, missions par trimestre, charge totale).
4. Répéter avec `auditeur1` et `dg`.

**Résultat attendu** : mêmes données ; `auditeur1` et `dg` en lecture seule (pas de bouton d'ajout) ; `audite1` n'a pas accès (S1-07).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-19 — Valider un programme (gel)
**Rôle** : `rai` · **Préconditions** : programme brouillon avec lignes.
1. « Valider le programme », lire l'avertissement, « Valider définitivement ».
2. Tenter d'ajouter, modifier, supprimer une mission prévue ; supprimer le programme.

**Résultat attendu** : « Programme validé le … par … — lecture seule » ; plus de modification ; seul un brouillon est supprimable (« Supprimer le programme » absent après validation).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-20 — Export et impression du programme
**Rôle** : `rai` · **Préconditions** : programme avec lignes.
1. « Exporter le programme » › CSV et Excel.
2. « Imprimer ».

**Résultat attendu** : fichiers lisibles ; une valeur commençant par `=` dans un titre est exportée comme texte, jamais comme formule (voir S4-20 pour le test).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### 4.D Missions

### S2-21 — Créer une mission (brouillon)
**Rôle** : `rai` · **Préconditions** : une cartographie **validée** existe (S2-08).
1. Missions › « Créer une mission ».
2. Renseigner : titre, type, processus audités, entités auditées, événement déclencheur, période auditée, dates prévues, budget (jours), objectifs, périmètre, exclusions, clients, livrables attendus.
3. « Enregistrer ».
4. Essayer sans titre, sans type, avec fin avant début, avec budget négatif.
5. (Si possible, dans une base sans cartographie validée) créer une mission.

**Résultat attendu** : mission en statut « Brouillon », sans référence ; « La mission a été enregistrée. » ; erreurs « Le titre est obligatoire. », « Choisissez un type de mission. », « La date de fin doit suivre la date de début. », « Le budget doit être un nombre de jours supérieur ou égal à 0. » ; sans cartographie validée : « Aucune cartographie des risques validée : validez une cartographie avant de créer une mission. »

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-22 — Liste des missions et filtres
**Rôle** : `rai`, `auditeur1`, `audite1` · **Préconditions** : plusieurs missions.
1. Missions : recherche par référence/titre, filtres Année, Statut, Type.
2. Comparer ce que voient `rai`, `auditeur1` (missions où il est affecté, hors brouillons) et `audite1` (missions dont l'ordre est émis et où il est affecté comme audité).

**Résultat attendu** : le RAI voit tout ; l'auditeur seulement ses missions non brouillon ; l'audité seulement celles dont l'ordre de mission est émis. Message vide adapté : « Vous n'êtes affecté à aucune mission. » / « Aucune mission ne concerne votre entité pour le moment. »

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-23 — Planifier la mission (référence)
**Rôle** : `rai` · **Préconditions** : brouillon S2-21.
1. Menu « Actions sur la mission » › « Planifier la mission ». Au préalable, vider un champ obligatoire (processus, entités, dates) et tenter : message d'informations manquantes.
2. Compléter et confirmer « Planifier ».

**Résultat attendu** : statut « Planifiée » ; référence `DAI/AAAA/Mnn` (AAAA = année du début prévu, nn = rang, jamais réutilisé).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-24 — Supprimer un brouillon
**Rôle** : `rai` · **Préconditions** : un brouillon.
1. « Supprimer le brouillon », confirmer.
2. Sur une mission déjà planifiée, chercher l'action de suppression.

**Résultat attendu** : le brouillon disparaît de la liste (suppression logique). Sur une mission planifiée, l'action n'existe pas (« Seule une mission en brouillon peut être supprimée ; annulez-la »).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-25 — Suspendre, reprendre, annuler
**Rôle** : `rai` · **Préconditions** : mission en planification.
1. « Suspendre la mission » avec motif vide (refus), puis avec motif.
2. Observer la mission : bandeau, plus d'édition.
3. « Reprendre la mission ».
4. « Annuler la mission » avec motif.

**Résultat attendu** : suspendue = lecture seule (mêmes droits réduits à reprendre/annuler) ; reprise = retour au statut d'avant ; annulée = définitif, « ne peut plus être modifiée ni reprise ». Voir le gel détaillé en S4-04.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### 4.E Documents, gabarits, registre

### S2-26 — Consulter les gabarits (lecture)
**Rôle** : `rai`, puis `admin` · **Préconditions** : gabarits provisoires chargés (commande `gabarits_provisoires`, V-05).
1. Gabarits de documents : lister les types (ordre de mission, PV, rapport…) avec gabarit actif, étape, contrat.
2. Lire la bannière « n documents utilisent un gabarit provisoire en attente du modèle officiel ONEA ».
3. Ouvrir un type : historique des versions, balises du contrat (« Copier »).

**Résultat attendu** : `rai` lit sans pouvoir déposer ni activer ; `admin` a les boutons « Déposer une nouvelle version », « Activer ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-27 — Déposer, prévisualiser et activer un gabarit
**Rôle** : `admin` · **Préconditions** : un fichier `.docx` valide (≤ 10 Mo).
1. Ouvrir un type › « Déposer une nouvelle version », choisir le .docx, commentaire facultatif, « Déposer ».
2. « Aperçu Word » (et « Aperçu PDF » si Gotenberg).
3. « Activer » la version, lire la confirmation, confirmer.
4. Essayer un `.doc`, un fichier de 11 Mo, un fichier renommé en `.docx` sans l'être.

**Résultat attendu** : nouvelle version listée ; activation = « Les prochains documents… utiliseront la version N. Les documents déjà générés ne changent pas. » ; refus : « Les fichiers .doc ne sont pas acceptés… », « Le fichier dépasse 10 Mo. », « Le fichier n'est pas un document Word .docx valide. » ; gabarit invalide : liste des raisons « Le gabarit est refusé pour les raisons suivantes ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-28 — Numérotation des documents
**Rôle** : `admin` (écriture), `rai` (lecture) · **Préconditions** : aucune.
1. Gabarits › Numérotation : lire le tableau (modèle, portée Par mission/Par année, abréviation, aperçu).
2. Modifier un format : essayer un modèle vide, une abréviation de plus de 8 caractères, un champ non permis.
3. Saisir un modèle valide `{mission}-{code}-{sequence}` ; observer l'aperçu calculé par le serveur ; enregistrer.

**Résultat attendu** : champs permis `{mission}`, `{annee}`, `{code}`, `{sequence}` ; erreurs « Saisissez un modèle. », « L'abréviation ne peut pas dépasser 8 caractères. » ; le nouveau format ne vaut que pour les documents créés ensuite.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-29 — Générer un document et le retrouver au registre
**Rôle** : `rai` · **Préconditions** : mission planifiée avec ordre émis (S3-04) ; worker Celery et Gotenberg pour le PDF (V-05).
1. Sur la mission (panneau Documents ou étape concernée), « Générer ».
2. Attendre « Génération en cours… ».
3. « Télécharger (Word) » puis « Télécharger (PDF) ».
4. Ouvrir Documents (registre) : chercher par numéro, filtrer par type.
5. Ouvrir le document : versions, empreinte (« Copier l'empreinte »), consultations (qui a téléchargé, quand, format, IP).
6. « Régénérer ».

**Résultat attendu** : numéro attribué selon le format ; nouvelle version à chaque régénération (ancienne conservée) ; chaque téléchargement apparaît dans « Consultations ». Si le PDF n'est pas prêt : « Le PDF n'est pas encore disponible. » avec « Relancer le PDF ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S2-30 — Registre des documents vu par l'audité et refus pour le DG
**Rôle** : `audite1`, `dg` · **Préconditions** : S2-29.
1. `audite1` : Documents.
2. `dg` : ouvrir `/documents`.

**Résultat attendu** : `audite1` ne voit que les documents que le fournisseur autorise sur ses missions ; message « Aucun document ne concerne vos missions pour le moment » si aucun ; `dg` : « Accès refusé ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

---

## 5. Niveau 3 — Scénarios métier : les 18 étapes IFACI et le suivi

**Fil conducteur.** Une même mission, appelée ici **« mission de recette »**, est menée du début à la fin.
Les scénarios S3-01 à S3-33 se jouent **dans l'ordre**. Prérequis communs : cartographie validée
(S2-08), au moins un processus et une entité auditée rattachée à la direction de `audite1` (S2-12),
mission créée et planifiée (S2-21, S2-23) avec **objectifs et périmètre renseignés**.

Rappel du cycle : les statuts de mission progressent *Brouillon › Planifiée › En planification (étapes
I à X) › En accomplissement (XI à XIII) › En communication (XIV à XVIII) › Rapport diffusé › En suivi ›
Clôturée*. Le passage de phase est automatique : il se produit quand toutes les étapes de la phase
sont closes **et** que le jalon de la phase (X, puis XIII) est validé. Les jalons validés par le RAI
sont les étapes **VI, X, XIII et XVIII** (la validation de VI, X et XIII peut être déléguée à un
superviseur, voir S4-26).

Chaque étape propose, selon les droits : « Commencer l'étape », « Terminer l'étape », « Valider le
jalon », « Renvoyer », « Rouvrir l'étape », « Marquer non applicable ». « Terminer » est refusé tant que
les livrables manquent (liste « Manquant : … » sous l'étape).

### 5.A Planification (étapes I à X)

### S3-01 — Constituer l'équipe
**Rôle** : `rai` · **Préconditions** : mission planifiée.
1. Ouvrir la mission › onglet « Équipe » › « Affecter une personne ».
2. Affecter `auditeur1` avec le rôle **Chef de mission**.
3. Affecter `auditeur2` avec le rôle **Auditeur**.
4. Affecter `audite1` avec le rôle **Audité** (les audités rattachés aux entités de la mission sont pré-cochés).
5. Relever la colonne « Déclaration » : « En attente » pour les intervenants, « Non requise » pour l'audité.
6. Essayer d'affecter une seconde fois la même personne ou de ne choisir personne.

**Résultat attendu** : trois lignes dans « Membres de l'équipe » ; « Choisissez au moins une personne. » si rien n'est choisi ; chaque intervenant reçoit une déclaration d'indépendance « En attente ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-02 — Déclarations d'indépendance
**Rôle** : `auditeur1`, `auditeur2` · **Préconditions** : S3-01.
1. Se connecter avec `auditeur1` : repérer la mention « Déclaration à confirmer » dans la liste des missions et le bandeau « Confirmez votre déclaration d'indépendance pour contribuer à la mission ».
2. Ouvrir « Confirmer ma déclaration », choisir « Je confirme cette déclaration », puis « Confirmer la déclaration ».
3. Lire le message : « Déclaration confirmée le … à … Empreinte : … ».
4. Faire de même avec `auditeur2`.
5. Retourner à l'équipe avec `rai` : « Confirmée le … ».

**Résultat attendu** : déclaration confirmée avec date, heure et empreinte ; le bandeau disparaît ; l'auditeur peut désormais contribuer. Tant que la déclaration est en attente, toute écriture est refusée (voir S4-06).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-03 — Lancer la mission
**Rôle** : `rai` · **Préconditions** : S3-01 ; pour tester le refus, une seconde mission planifiée **sans chef**.
1. Sur la mission sans chef : « Lancer la mission » (confirmer « Lancer »).
2. Sur la mission de recette : « Lancer la mission ».

**Résultat attendu** : refus sans chef de mission (message sur le chef de mission) ; sinon statut « En planification », étape I « En cours ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-04 — Étape I : objectifs, périmètre, ordre de mission
**Rôle** : `rai`, puis `audite1` · **Préconditions** : S3-03.
1. Ouvrir l'étape I : lire « Rappel de la mission » (objectifs, périmètre, équipe, dates). « Modifier la mission » pour compléter.
2. Sans objectifs ni périmètre : tenter « Émettre l'ordre de mission ».
3. Compléter objectifs et périmètre, puis « Émettre l'ordre de mission » : lire le texte « Je soussigné(e) … émets l'ordre de mission … », « Émettre l'ordre ».
4. Lire : « Ordre de mission émis le … par … Empreinte : … ».
5. « Terminer l'étape » (étape I).
6. Retenter de modifier le titre de la mission.
7. Avec `audite1` : la mission apparaît désormais dans sa liste.

**Résultat attendu** : étape 2 refusée (informations obligatoires manquantes) ; étape 3 confirmation horodatée ; après l'étape I terminée, les champs figés (titre, type, période, objectifs, périmètre…) ne sont plus modifiables (« Figé par l'ordre de mission : rouvrez l'étape I pour le modifier ») ; l'audité ne voit la mission qu'après l'émission de l'ordre. Un texte « Le document Word sera généré au lot 4 » peut encore s'afficher (V-11).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-05 — Étape II : réunion d'ouverture et entretiens
**Rôle** : `auditeur1` (ou `rai`) · **Préconditions** : étape I terminée (ordre émis).
1. « Commencer l'étape » II.
2. Onglet « Réunions » : « Planifier la réunion » d'ouverture (date et heure, lieu, ordre du jour, participants internes/externes « Nom — fonction — organisation »).
3. Essayer « Terminer l'étape » : lire les livrables manquants (réunion non tenue, aucun entretien planifié, déclarations).
4. Saisir décisions et compte rendu, « Marquer comme tenue ».
5. Onglet « Entretiens » : « Planifier un entretien » (objet, durée 1 à 600 min, étape, auditeurs, interlocuteurs, thèmes). Durée `0` et objet vide : erreurs. « Imprimer le planning ».
6. « Terminer l'étape » II.

**Résultat attendu** : « Terminer » est refusé tant que : la réunion d'ouverture n'est pas tenue, aucun entretien (non annulé) n'est planifié, une déclaration est en attente ; « Marquer comme tenue » exige que le compte rendu soit saisi. Étape II terminée une fois les trois conditions remplies. Un texte « Le PV sera généré au lot 4 » peut rester affiché (V-11).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-06 — Étape III : processus, questionnaire, QCI, séparation des tâches
**Rôle** : `auditeur2` · **Préconditions** : étape II terminée.
1. « Commencer l'étape » III.
2. « Créer le questionnaire » de prise de connaissance : répondre à quelques questions (« Enregistrer la réponse »), « Ajouter une question », « Retirer la question ».
3. Pour chaque processus de la mission : saisir la description (typologie, catégories d'objectifs, description narrative, objectifs, indicateurs, sources), « Enregistrer la description ».
4. « Créer le QCI » du processus.
5. Grille de séparation des tâches : ajouter 2 tâches et 2 acteurs, affecter les rôles E/A/En/C ; faire exécuter et contrôler la même tâche par le même acteur.
6. « Terminer l'étape » avec un processus non décrit, puis avec tous décrits.

**Résultat attendu** : alertes de grille (« Cumul incompatible : … », « Tâche sans acteur : … », « Tâche à plusieurs exécutants : … ») ; limites de 100 tâches et 30 acteurs ; étape refusée tant que « Description manquante pour les processus : … » ; progression « n / N questions renseignées ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-07 — Étape IV : risques de la mission et matrice 5×5
**Rôle** : `auditeur2`, `rai` · **Préconditions** : étape III terminée.
1. « Commencer l'étape » IV ; « Terminer » immédiatement : refus « Aucun risque n'est sélectionné pour la mission ».
2. « Sélectionner des risques de la cartographie AAAA » : cocher plusieurs risques ; « Ajouter la sélection ».
3. Lire la matrice des risques de la mission ; cliquer une case : la liste se filtre ; « Effacer le filtre ».
4. « Réévaluer » un risque (probabilité 5, impact 4) : aperçu « Score 20 · Élevé ».
5. « Ajouter un risque nouveau » (processus, libellé, P, I, commentaire).
6. « Retirer » un risque (confirmation).
7. Avec `rai` : dans le panneau « Risques proposés par les missions », constater le risque nouveau (en attente d'intégration à la cartographie).
8. « Terminer l'étape » IV.

**Résultat attendu** : score = P × I, niveaux faible/moyen/élevé aux seuils 8 et 15 ; libellé obligatoire (« Le libellé est obligatoire. », 500 caractères max) ; les risques déjà sélectionnés ne sont plus proposés (« Déjà sélectionné »).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-08 — Étape V : matrice des risques et contrôles (MARC)
**Rôle** : `auditeur2` · **Préconditions** : étape IV terminée.
1. « Commencer l'étape » V ; ouvrir « Référentiel d'audit ».
2. « Initialiser depuis les risques de la mission ».
3. « Ajouter un contrôle » sur un risque : objet auditable, opération, objectif de contrôle, contrôle attendu, contrôle existant, composante, nature, évaluation de la conception, « Contrôle clé » oui/non, commentaire.
4. Tester : évaluation renseignée sans « contrôle existant » ; contrôle absent marqué clé.
5. Marquer au moins un contrôle comme clé. Lire l'alerte « Risques moyens ou élevés sans contrôle analysé : … ».
6. « Modifier » puis « Supprimer » une ligne.
7. « Terminer l'étape » V.

**Résultat attendu** : « Le contrôle existant est obligatoire quand la conception est évaluée. » ; « Un contrôle absent ne peut pas être un contrôle clé. » ; étape refusée si la matrice est vide, si des lignes n'ont pas d'évaluation de la conception, ou si des risques moyens/élevés restent sans contrôle analysé.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-09 — Étape VI : référentiel d'audit validé (jalon 1)
**Rôle** : `auditeur2`, `audite1`, `rai` · **Préconditions** : étape V terminée.
1. `auditeur2` : « Commencer l'étape » VI ; compléter « Forces apparentes » et « Faiblesses apparentes » (lignes issues de la MARC en lecture seule, ajouts manuels « Ajouter une force/faiblesse »).
2. « Terminer l'étape » VI (soumet le référentiel au RAI).
3. `audite1` : ouvrir le référentiel d'audit ; s'il n'est pas diffusé : « Le référentiel d'audit n'est pas encore diffusé » ; sinon « Donner mon avis » (type d'avis ; commentaire obligatoire pour des remarques).
4. `rai` : dans le tableau de bord, jalon VI « à valider » ; ouvrir l'étape VI › « Valider le jalon ».
5. Relire : « Validé le … par … — empreinte … — vérifiée » et « Version validée ».

**Résultat attendu** : jalon validé, version figée avec empreinte vérifiée ; l'avis de l'audité est enregistré mais « ne bloque pas la suite » ; le jalon disparaît de la file du RAI. « Renvoyer » (motif obligatoire) renvoie l'étape à l'équipe.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-10 — Étape VII : objectifs d'audit et rapport d'orientation
**Rôle** : `auditeur2` · **Préconditions** : jalon VI validé (sinon : « Le référentiel d'audit doit être validé (jalon VI) avant de sélectionner les objectifs d'audit »).
1. « Commencer l'étape » VII ; « Proposer un objectif par contrôle clé ».
2. Modifier un libellé d'objectif ; « Enregistrer le libellé ».
3. Sur un autre objectif : « Ne pas tester » avec motif et justification (champs obligatoires).
4. Rédiger le rapport d'orientation : variante, contexte, approche, observations, rapprochement avec l'ordre de mission (couverture, justification obligatoire hors couverture exacte) ; enregistrer.
5. Essayer « Terminer » avec un contrôle clé sans décision, puis après décision.

**Résultat attendu** : objectifs codés OA (codes jamais réutilisés) ; « Contrôles clés sans décision de test : … » bloque l'étape ; « Aucun objectif d'audit n'est retenu. » si aucun.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-11 — Étape VIII : programme de travail
**Rôle** : `auditeur2` · **Préconditions** : étape VII terminée.
1. « Commencer l'étape » VIII.
2. Pour un objectif, « Créer le programme » : techniques et sources, critères de preuve.
3. « Ajouter un test » : libellé, nature (Entretien, Examen documentaire, Échantillonnage…), procédure, population, taille d'échantillon, méthode de sélection, risque. Essayer libellé vide, taille `-3`.
4. Ajouter au moins un test par objectif retenu.
5. « Imprimer le programme ».
6. « Terminer l'étape » VIII.

**Résultat attendu** : tests codés ; « La taille de l'échantillon doit être un entier positif. » ; sans objectif retenu : « Aucun objectif d'audit n'est retenu : sélectionnez les objectifs à l'étape VII… ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-12 — Étape IX : budget et ressources
**Rôle** : `auditeur1` (chef) · **Préconditions** : étape VIII terminée.
1. « Commencer l'étape » IX.
2. Pour chaque test, « Planifier » : affecter **`auditeur2`** comme auditeur du test, charge prévue (jours), dates. Tester charge négative et fin avant début.
3. Lire la synthèse : « Par objectif », « Par auditeur », « Total : x j · Budget : y j ».
4. Faire dépasser le budget de la mission : lire l'avertissement.
5. Laisser un test sans auditeur : « Tests sans auditeur : … ».
6. Corriger et « Terminer l'étape » IX.

**Résultat attendu** : « La charge prévue doit être un nombre positif. », « La date de fin ne peut pas précéder la date de début. », « Les charges prévues dépassent le budget de la mission de x j. » ; **l'auditeur du test est celui qui rédigera la fiche** (S3-15).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-13 — Étape X : organisation validée (jalon 2) et passage en accomplissement
**Rôle** : `auditeur1`, `rai` · **Préconditions** : étapes VIII et IX terminées.
1. `auditeur1` : « Terminer l'étape » X avec une étape VIII ou IX non terminée (refus « Terminez les étapes VIII et IX… »), puis après.
2. `rai` : « Valider le jalon » X.
3. Observer la mission : statut, fiche de suivi.

**Résultat attendu** : une fois I à X closes et X validée, la mission passe automatiquement à « En accomplissement » ; l'étape XI devient disponible.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### 5.B Accomplissement (étapes XI à XIII)

### S3-14 — Étape XI : réunion de lancement
**Rôle** : `auditeur1` · **Préconditions** : S3-13.
1. « Commencer l'étape » XI ; planifier la réunion de lancement ; « Marquer comme tenue » (compte rendu requis) ; « Terminer l'étape ».

**Résultat attendu** : refus « La réunion de lancement n'est pas marquée comme tenue » tant qu'elle ne l'est pas.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-15 — Étape XII : fiche de test et pièces justificatives
**Rôle** : `auditeur2` (auditeur du test), `auditeur1` · **Préconditions** : étape XI terminée ; fichier PDF et fichier image de test.
1. `auditeur2` : « Commencer » XII (avant : message « Commencez l'étape XII pour saisir les fiches de test »).
2. Écran « Tests complémentaires » : filtre « Mes tests » / « Tous les tests ». « Documenter le test » : travaux réalisés, échantillon testé, taille, exceptions, résultat, date, charge réelle.
3. « Enregistrer le brouillon ».
4. « Soumettre la fiche » sans conclusion : refus. Choisir la conclusion **Anomalie** (autres choix : Satisfaisant, Point fort).
5. Pièces justificatives : saisir un libellé, choisir un PDF, « Déposer la pièce » ; observer la barre « Envoi en cours », puis la ligne (n°, libellé, fichier, taille, empreinte SHA-256, déposée par). « Copier l'empreinte », « Renommer », « Télécharger ».
6. Soumettre sans pièce et sans justification : refus. Puis avec pièce : « Soumettre la fiche ».
7. Sur un autre test : « Abandonner le test » (motif obligatoire) ; sur un autre : « Ajouter un test complémentaire ».
8. Avec `auditeur1` (chef de mission) : documenter le test d'`auditeur2` est possible (le chef rédige). Un membre d'équipe qui n'est ni chef ni auditeur du test n'a pas ce droit.

**Résultat attendu** : « Saisissez le résultat et la conclusion avant de soumettre. » ; « Déposez une pièce justificative ou justifiez son absence. » ; libellé de pièce obligatoire ; empreinte affichée ; fiche « Soumise » ; journal de la fiche (Fiche soumise, par, date). Voir S4-13 pour les fichiers refusés.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-16 — Étape XIII : validation des fiches (jalon 3) et passage en communication
**Rôle** : `rai` · **Préconditions** : fiches soumises ; étape XII terminée par l'équipe.
1. `rai` : « Commencer » XIII ; lire « Fiches à valider » et la progression « n fiches validées sur N ».
2. Ouvrir une fiche, relire les pièces, « Renvoyer » avec motif (le motif apparaît chez l'auteur : « Fiche renvoyée — Motif du renvoi »).
3. `auditeur2` corrige et resoumet.
4. `rai` « Valider la fiche » (confirmer). Valider toutes les fiches.
5. « Terminer » XIII puis « Valider le jalon » XIII.
6. Contrôler la mission : statut.

**Résultat attendu** : validation tracée au journal de la fiche ; l'étape XIII n'est terminable que si **toutes** les fiches sont validées (« La fiche du test … n'est pas validée. ») ; la mission passe à « En communication ». « Rouvrir » une fiche validée exige un motif.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### 5.C Communication (étapes XIV à XVIII)

### S3-17 — Étape XIV : constats, causes 7M, recommandations
**Rôle** : `auditeur1` (chef), `rai` · **Préconditions** : au moins une fiche en Anomalie validée.
1. `auditeur1` : « Commencer » XIV ; onglet « Constats » ; lire « Fiches ANOMALIE sans constat ».
2. « Créer un constat à partir de cette fiche » : titre, entité concernée (celle de `audite1`), processus, risque, fait constaté, référentiel (critère), conséquence, conclusion, probabilité et impact (aperçu « Score … · niveau »).
3. « Enregistrer le constat » (avant toute autre action : message « Enregistrez vos modifications… »).
4. **Causes (7M)** : ajouter une cause dans au moins deux rubriques (Main-d'œuvre, Méthodes, Matériel, Milieu, Matière, Management, Moyens financiers).
5. **Recommandations** : ajouter 2 recommandations avec priorité ; les réordonner (« Monter » / « Descendre »), en retirer une.
6. « Imprimer la fiche d'observation ».
7. Soumettre le constat. Essayer ensuite de le modifier.
8. `rai` : ouvrir le constat soumis, « Renvoyer » (motif obligatoire), `auditeur1` corrige et resoumet ; `rai` « Valider ».
9. Tenter de valider avec `auditeur1` un constat qu'il a lui-même créé ou soumis.

**Résultat attendu** : constat Brouillon › Soumis › Validé (ou Renvoyé) ; « Seuls le chef de mission ou le RAI peuvent soumettre un constat. » pour les autres ; « Vous ne pouvez pas traiter un constat dont vous êtes l'auteur ou le soumetteur. » (quatre yeux) ; « Le motif du renvoi est obligatoire. » ; seuls un brouillon ou un renvoyé sont modifiables. « Terminer » XIV est refusé s'il y a une anomalie et « Aucun constat n'est validé ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-18 — Étape XV : réunion de clôture et rapport provisoire
**Rôle** : `auditeur1` (ou `rai`), `rai` · **Préconditions** : constat validé ; l'audité doit pouvoir répondre.
1. « Commencer » XV (zone « Rapport provisoire ») : lire « Constats validés à présenter en réunion ».
2. Planifier et « Marquer comme tenue » la réunion de clôture (PV de clôture).
3. « Transmettre le rapport provisoire » avant la réunion tenue : refus (« Tenez la réunion de clôture avant… »).
4. Après la réunion : si le rapport n'existe pas, « Créer le rapport » ; « Transmettre le rapport provisoire » avec délai de réponse : essayer 0, 61, puis 15 jours.
5. Lire « Transmis le …. Réponses attendues au plus tard le … » et le tableau « Réponses des audités » (Attendu de, Reçu le, « En attente »).

**Résultat attendu** : délai accepté entre 1 et 60 jours (« Le délai de réponse doit être compris entre 1 et 60 jours. ») ; seuls le chef de mission ou le RAI transmettent ; les audités concernés reçoivent une notification.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-19 — Réponses de l'audité au rapport provisoire
**Rôle** : `audite1`, puis `rai` · **Préconditions** : S3-18 ; direction de `audite1` = entité du constat.
1. `audite1` : notification, puis mission › « Rapport provisoire » : lire le décompte (« Il vous reste N jours pour répondre »).
2. « Constats de mon entité » : « Répondre ».
3. Choisir **Désaccord** sans commentaire : refus (« Le commentaire est obligatoire. » ou « Motivez votre désaccord. » selon l'écran). Saisir un commentaire, « Continuer ».
4. Lire le texte à confirmer (chargé du serveur), cocher « Je confirme », « Envoyer ma réponse ».
5. Lire : « Réponse enregistrée le … à … Empreinte : … ».
6. Refaire une réponse en **Accord**.
7. `rai` : « Réponses des audités » : reçu le, position ; historique des réponses (cycle, position, empreinte).
8. Tester le dépassement de délai : une réponse après la date limite est marquée « Hors délai ».

**Résultat attendu** : on ne peut pas confirmer sans cocher la case ; la réponse est tracée avec empreinte ; plusieurs réponses forment un historique par cycle ; un audité d'une autre direction ne peut pas répondre (S4-11). Après clôture de la période : « La période de réponse au rapport provisoire est close. »

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-20 — Étape XVI : plan d'actions
**Rôle** : `audite1`, `auditeur1`, `rai` · **Préconditions** : étape XV terminée ; constat validé avec recommandations.
1. `auditeur1` : « Terminer » XV puis « Commencer » XVI.
2. `audite1` : Plan d'actions › sous une recommandation, « Ajouter une action » : mesure corrective (obligatoire), responsable, échéance (une date passée est refusée), indicateur, moyens.
3. Ajouter une seconde action ; « Modifier », « Supprimer ».
4. Lire « Contrôles du plan d'actions » : « Actions incomplètes… », « Engagements manquants ou à renouveler… ».
5. `audite1` (responsable d'actions) : « Confirmer mon engagement » (case + confirmation) ; modifier ensuite une action : l'engagement passe à « À renouveler ».
6. `auditeur1` : lire le tableau « Engagement par responsable » ; « Terminer » XVI.

**Résultat attendu** : « L'échéance ne peut pas être antérieure à aujourd'hui. » ; une recommandation sans action ni acceptation figure dans « Recommandations sans suite » ; le plan n'est modifiable que pendant la fenêtre (étapes XV/XVI ouvertes), sinon lecture seule.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-21 — Étape XVII : rédaction et soumission du rapport
**Rôle** : `auditeur1` (chef) · **Préconditions** : étape XVI terminée.
1. « Commencer » XVII ; onglet « Rapport » ; « Créer le rapport » s'il n'existe pas.
2. Rédiger les sections : synthèse, commentaire sur l'appréciation, contexte, objectifs, périmètre, méthodologie, conclusion, note synthétique, annexes ; compteur de caractères ; **appréciation globale** (Maîtrise satisfaisante / perfectible / insuffisante). « Enregistrer ».
3. « Aperçu du rapport » (bandeau « Aperçu — non figé », constats retenus).
4. « Terminer » XVII sans synthèse, appréciation et conclusion : lire l'erreur.
5. Compléter, « Terminer » XVII.
6. « Soumettre au RAI » (le rapport est figé dans son état).

**Résultat attendu** : « Rédigez la synthèse, l'appréciation globale et la conclusion du rapport. » ; « Soumettez le rapport depuis l'écran du rapport. » ; après soumission : « Le rapport est soumis : il attend la validation du RAI. », plus de modification sauf renvoi. Seul le chef de mission soumet.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-22 — Étape XVIII : validation, signature selon le mode paramétré, diffusion
**Rôle** : `rai` (et `auditeur1` pour la vérification de non-validation) · **Préconditions** : rapport soumis ; pour la diffusion : worker Celery + Gotenberg (V-05).
1. `auditeur1` : vérifier qu'il n'a ni bouton « Valider » ni « Diffuser ».
2. `rai` : zone « Validation du rapport » : lire « Mode de signature en vigueur » (par défaut **Confirmation horodatée**).
3. « Renvoyer » avec motif vide (refus) puis avec motif ; `auditeur1` corrige, resoumet.
4. « Valider le rapport » : lire le texte de validation, cocher « Je confirme », valider. Lire « Validé le … à … Empreinte : … ».
5. Si le mode a été changé en signature électronique (S4-23) : constater que seule la confirmation est proposée tant qu'aucun signataire n'est installé.
6. Attendre « Le rapport final et la note de synthèse sont en cours de génération » puis les liens Word/PDF « Rapport final » et « Note de synthèse ».
7. **Liste de diffusion** : ajouter des destinataires internes (avec catégorie) et un destinataire externe (nom, qualité). Essayer « Diffuser le rapport » avec liste vide.
8. « Diffuser le rapport » (message d'accompagnement facultatif, confirmer).
9. Observer le statut de la mission : « Rapport diffusé ».

**Résultat attendu** : « Le valideur ne peut pas être la personne qui a soumis le rapport. » ; diffusion refusée si : rapport non généré, PDF pas prêt, signature requise non disponible, aucun destinataire (« Ajoutez au moins un destinataire ») ; la diffusion est irréversible et tracée (« Diffusé le … par … »).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-23 — Rapports diffusés : accusé de réception, DG, suivi de diffusion
**Rôle** : `dg`, destinataire interne (`audite1`/`auditeur2`), `rai` · **Préconditions** : S3-22.
1. `dg` : « Rapports diffusés » : filtre « Année de diffusion » ; ouvrir le rapport : synthèse, appréciation globale, téléchargements Word/PDF du rapport et de la note.
2. Destinataire interne : ouvrir le rapport › « Accuser réception » (confirmer).
3. `rai` : « Suivi de la diffusion » : Notifié le, Consulté le, Accusé le ; pour un externe, « Marquer comme remis » avec date.
4. `dg` : constater qu'aucune action de modification n'est offerte.

**Résultat attendu** : « Accusé de réception enregistré le … » ; colonne « Accusé de réception » ; le DG lit sans agir ; un destinataire non interne ne voit pas le bouton d'accusé.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### 5.D Suivi des recommandations et clôture

### S3-24 — Ouverture du suivi et traitement d'une action jusqu'à la clôture
**Rôle** : `audite1` (responsable), `auditeur2` (vérificateur), `rai` · **Préconditions** : rapport diffusé (S3-22) ; au moins une action au plan.
1. `rai` : lire la notification « Suivi ouvert » ; Recommandations › registre.
2. `audite1` : ouvrir l'action › « Démarrer ».
3. Déposer une **preuve de mise en œuvre** (libellé + fichier) ; « Ajouter un point d'avancement ».
4. `audite1` : « Déclarer réalisée » (commentaire obligatoire). Sans preuve : « Déposez au moins une preuve de mise en œuvre. »
5. `audite1` : tenter « Vérifier » sa propre déclaration (« Vous avez déclaré cette action : sa vérification revient à une autre personne. »).
6. `auditeur2` (intervenant à déclaration levée) : « Vérifier ».
7. `rai` : « Clôturer ».
8. Relire la chronologie (Suivi ouvert, Action démarrée, Preuve déposée, Déclarée réalisée, Vérifiée, Clôturée) avec auteur et date.

**Résultat attendu** : statuts À lancer › En cours › Réalisée, à vérifier › Vérifiée › Clôturée ; chaque transition n'est offerte qu'au bon rôle (l'audité ne vérifie ni ne clôture) ; mission en statut « En suivi » après l'ouverture du premier suivi.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-25 — Rejet et réouverture d'une action
**Rôle** : `auditeur2`, `rai` · **Préconditions** : une action « Réalisée, à vérifier » et une action « Clôturée ».
1. `auditeur2` : « Rejeter » l'action réalisée (motif obligatoire).
2. L'action retourne au responsable ; lire « Motif du dernier rejet ».
3. `rai` : sur l'action clôturée, « Rouvrir ».

**Résultat attendu** : rejet = retour au responsable avec motif visible ; seule la réouverture par le RAI est permise sur une action close ; notifications correspondantes (« Action rejetée »).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-26 — Demande de report d'échéance
**Rôle** : `audite1`, `rai` · **Préconditions** : action ouverte.
1. `audite1` : « Demander un report » : nouvelle échéance antérieure à l'actuelle (refus), sans motif (refus), puis valide.
2. `rai` : voir « Reports en attente » (tableau de bord) ; « Accepter le report ».
3. Refaire une demande et « Refuser le report » sans commentaire (refus), puis avec commentaire.

**Résultat attendu** : « La nouvelle échéance doit être postérieure à l'échéance courante », « Le motif est obligatoire. », « Commentaire (obligatoire pour un refus) » ; l'échéance courante change à l'acceptation ; la page de l'action garde l'échéance initiale et le nombre de reports ; notifications « Report demandé » et « Décision sur le report ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-27 — Abandon d'une action
**Rôle** : `audite1`, `rai` · **Préconditions** : action ouverte.
1. `audite1` : « Proposer l'abandon » (justification).
2. `rai` : « Accepter l'abandon » (ou « Rejeter »).
3. Lire le statut « Abandonnée (justifiée) » et la justification.

**Résultat attendu** : statut Abandon proposé puis Abandonnée ; les abandons figurent distinctement dans le tableau « Actions par direction » du RAI (« abandons inclus »).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-28 — Changer le responsable d'une action
**Rôle** : `rai` · **Préconditions** : action ouverte.
1. « Changer le responsable », choisir un autre audité ; enregistrer.
2. Se connecter avec l'ancien et le nouveau responsable.

**Résultat attendu** : le nouveau responsable est notifié (« Responsable modifié ») et voit l'action dans « Mes actions » ; seul le RAI a ce droit.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-29 — Registre des recommandations et des actions
**Rôle** : `rai`, `dg`, `auditeur1`, `audite1` · **Préconditions** : plusieurs actions.
1. Recommandations : onglets « Recommandations » / « Actions ».
2. Filtres : Année, Mission, Entité, Priorité, Statut, « En retard », « Mes actions » ; « Réinitialiser ».
3. « Exporter » CSV puis Excel ; « Imprimer ».
4. Comparer les lignes visibles par rôle.

**Résultat attendu** : le RAI et le DG voient tout (le DG sans bouton d'action) ; l'auditeur et l'audité seulement leurs missions ; l'audité, ses entités ou ses actions ; export limité à 5 000 lignes (au-delà : erreur).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-30 — Relances automatiques
**Rôle** : `rai` (et opérateur technique) · **Préconditions** : action ouverte avec échéance proche ou dépassée.
1. En ligne de commande : `python manage.py envoyer_relances --simulation` puis `--simulation --date AAAA-MM-JJ` (jour simulé).
2. Observer les paliers : « Échéance dans 15 jours », « Échéance aujourd'hui », « En retard de 15 jours » (un seul palier à la fois, le plus haut atteint).
3. Sans `--simulation`, exécuter ; lire le nombre d'e-mails traités.
4. Se connecter avec le responsable : notification « Relance » ; avec `rai` : au palier J+15, notification et copie.
5. Si le SMTP est absent : constater l'échec dans la file de décisions du RAI (« Relances en échec »).

**Résultat attendu** : `--simulation` n'écrit rien ; la relance est planifiée une fois par palier ; sans adresse e-mail, « Relances sans adresse » ; les relances partent aussi chaque jour à 7 h par la tâche planifiée (Celery beat). Il n'existe pas d'écran dédié aux relances (V-06).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-31 — Clôturer la mission
**Rôle** : `rai` · **Préconditions** : toutes les actions closes ou abandonnées.
1. Avant : avec des actions ouvertes, ouvrir « Suivi des recommandations » de la mission : « n action(s) restent ouvertes » et « La mission ne peut pas être clôturée pour le moment ».
2. Clôturer les dernières actions : notification « Mission à clôturer » ; file de décisions « Missions à clôturer ».
3. « Clôturer la mission » (confirmer).
4. Essayer ensuite de modifier quoi que ce soit.

**Résultat attendu** : statut « Clôturée » ; « Cette mission est clôturée. » ; tout est en lecture seule (voir S4-04) ; notification « Mission clôturée ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-32 — Rapport corrigé après diffusion
**Rôle** : `rai`, `auditeur1` · **Préconditions** : mission au statut « Rapport diffusé ».
1. `rai` : sur le rapport diffusé, « Émettre un rapport corrigé » (confirmer).
2. `auditeur1` : modifier le brouillon du rapport corrigé, soumettre.
3. `rai` valide puis diffuse.
4. Rapports diffusés : comparer les deux rapports.

**Résultat attendu** : un nouveau rapport en brouillon est créé ; l'ancien reste consultable avec le statut « Remplacé par un rapport corrigé » après la nouvelle diffusion ; la correction ne modifie ni les étapes ni le statut de la mission ; le journal du rapport montre « Rapport corrigé émis ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S3-33 — Acceptation du risque (recommandation sans action)
**Rôle** : `audite1`, `rai` · **Préconditions** : étape XVI ouverte, une recommandation sans action.
1. `audite1` : « Accepter le risque » : justification obligatoire ; cocher « Je confirme accepter ce risque au nom de ma direction. » ; « Confirmer l'acceptation ».
2. Lire « Risque accepté le … par … ». Le texte confirmé est affiché.
3. Essayer d'ajouter une action à cette recommandation (l'acceptation doit d'abord être retirée).
4. « Retirer l'acceptation » (auteur ou RAI).

**Résultat attendu** : l'acceptation n'est offerte que pour une recommandation **sans action** ; une recommandation « Risque accepté » n'est plus listée dans « Recommandations sans suite » ; le retrait la remet « sans suite ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

---

## 6. Niveau 4 — Scénarios complexes et limites

Ces scénarios cherchent à **mettre l'application en défaut** : accès croisés, états limites, fichiers
hostiles, erreurs de saisie, pannes de service. Un comportement « refus clair avec message français »
est un **succès**. Un écran blanc, une trace technique, une donnée affichée à tort ou une action
acceptée à tort est un échec (gravité « Sécurité » pour toute fuite de données).

### S4-01 — Concurrence : deux utilisateurs modifient la même chose
**Rôle** : `rai` dans deux fenêtres (A et B), puis `auditeur1`/`auditeur2` · **Préconditions** : mission en brouillon ; une fiche de test en brouillon.
1. Fenêtres A et B ouvertes sur « Modifier la mission » (même mission). Dans A, changer le titre, enregistrer. Dans B (formulaire resté ouvert), changer l'objectif, enregistrer.
2. Relire la mission : le titre de A est-il conservé, écrasé ou signalé ?
3. Même exercice sur une fiche de test : `auditeur2` (fenêtre A) et `auditeur1` (fenêtre B) modifient le même champ.
4. Dans A, « Planifier » la mission ; dans B (page restée ouverte), « Supprimer le brouillon ».

**Résultat attendu** : aucune corruption ni écran d'erreur technique. Le code verrouille les lignes à l'écriture (`select_for_update`), mais **aucun verrou optimiste visible** (avertissement « modifié par un autre utilisateur ») n'a été trouvé : à l'étape 2, le comportement attendu est « dernier enregistrement gagnant » (V-03). À l'étape 4, B doit recevoir un refus clair (statut non compatible), jamais une suppression d'une mission planifiée. Noter exactement ce qui est observé.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-02 — Concurrence : double validation simultanée
**Rôle** : `rai` (fenêtres A et B) · **Préconditions** : une fiche (ou un constat, ou un rapport) soumis.
1. Ouvrir la même fiche soumise dans A et B.
2. Dans A, « Valider la fiche » ; dans B (écran non rafraîchi), cliquer « Valider la fiche » ou « Renvoyer » aussitôt.
3. Rafraîchir B.

**Résultat attendu** : une seule décision est enregistrée ; la seconde est refusée avec un message (l'état a changé) ; le journal de la fiche ne contient qu'un événement « Fiche validée ». Idem pour constat et rapport.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-03 — Double soumission (double clic, rafraîchissement)
**Rôle** : `rai` · **Préconditions** : dialogues de confirmation disponibles.
1. Dans « Émettre l'ordre de mission », double-cliquer très vite « Émettre l'ordre ».
2. Idem sur « Diffuser », « Transmettre le rapport provisoire », « Créer une mission », « Déposer la pièce » (double clic).
3. Après une action réussie, utiliser « Précédent » puis valider de nouveau le dialogue si l'écran le permet.

**Résultat attendu** : une seule confirmation d'ordre (une seule empreinte), une seule diffusion (irréversible), une seule mission créée, une seule pièce par dépôt ; le bouton se désactive pendant l'envoi (« Enregistrement… », « Transmission en cours… »). Aucune ligne en double dans les listes.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-04 — Gel d'une mission suspendue, annulée ou clôturée
**Rôle** : `rai`, `auditeur1`, `audite1` · **Préconditions** : trois missions : suspendue (S2-25), annulée, clôturée (S3-31).
1. `rai` : sur la mission suspendue, tenter : modifier, affecter, terminer une étape, saisir une fiche. Seuls « Reprendre » et « Annuler » sont offerts.
2. `auditeur1` : tenter d'écrire (fiche, constat, entretien) sur la mission suspendue.
3. Mission clôturée : parcourir toutes les pages en lecture ; chercher un bouton d'écriture.
4. Rejouer un ancien lien d'action (onglet resté ouvert avant la suspension) : clic sur « Enregistrer ».

**Résultat attendu** : message « La mission DAI/AAAA/Mnn est suspendue : aucune modification n'est possible. » (ou annulée, clôturée) ; boutons d'écriture absents ; rien n'est enregistré, même depuis un onglet périmé.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-05 — Étape close, réouverture et jalons « à revalider »
**Rôle** : `auditeur2`, `rai` · **Préconditions** : mission avec étapes IV et V terminées, jalon VI validé.
1. Sur l'étape IV terminée, tenter d'ajouter un risque : refus « L'étape IV est terminée : rouvrez-la pour modifier ses travaux. »
2. `rai` : « Rouvrir l'étape » IV (motif obligatoire ; lire l'avertissement « Les jalons validés des étapes suivantes devront être revalidés »).
3. Constater le statut « À revalider » sur les étapes aval et sur le jalon VI.
4. Retenter, avant de commencer XII, de saisir une fiche (« Commencez l'étape XII pour saisir les fiches de test »).
5. « Marquer non applicable » une étape (motif), puis « Rétablir l'étape ».
6. Relire le « Journal de l'étape » : Rouverte, À revalider, Non applicable, Rétablie (auteur, date, motif).

**Résultat attendu** : travaux gelés quand l'étape est terminée, validée ou à revalider ; la réouverture est tracée ; la mission ne change pas de phase tant qu'une étape antérieure est rouverte.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-06 — Déclaration d'indépendance non levée : contribution refusée
**Rôle** : `auditeur2` · **Préconditions** : mission où `auditeur2` est affecté mais n'a **pas** confirmé sa déclaration.
1. Ouvrir la mission : lire le bandeau.
2. Tenter d'ajouter un risque, d'enregistrer une fiche, de planifier un entretien.
3. Confirmer la déclaration (S3-02) et recommencer.

**Résultat attendu** : avant : « Confirmez votre déclaration d'indépendance avant de contribuer à la mission. » ; la lecture reste possible, l'écriture non. Après : tout fonctionne. L'entrée en « Terminer l'étape » II est aussi bloquée par « Déclarations d'indépendance en attente : … ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-07 — Conflit d'intérêts déclaré et arbitrage
**Rôle** : `auditeur2`, `rai`, `auditeur1` · **Préconditions** : déclaration d'`auditeur2` en attente.
1. `auditeur2` : choisir « Je déclare une situation susceptible d'affecter mon indépendance » ; valider avec description vide (refus « Décrivez la situation que vous déclarez. »), puis avec description.
2. Lire « Situation déclarée le … Empreinte : … ». Tenter de contribuer.
3. `rai` : « Arbitrer » (justification obligatoire), « Enregistrer l'arbitrage ». Lire : l'auditeur reste affecté.
4. `auditeur2` : contribuer de nouveau.
5. `auditeur1` (collègue) : ouvrir l'équipe et lire la description du conflit d'`auditeur2` (constat SEC-08).
6. `rai` : retirer `auditeur2` de l'équipe (« Retirer de la mission ») et relire sa déclaration.

**Résultat attendu** : tant qu'un conflit n'est pas arbitré, pas de contribution ; après arbitrage, contribution possible ; retirer un membre = sa déclaration n'est plus requise. **Point connu** : la description du conflit et la justification d'arbitrage sont lisibles par toute l'équipe (étape 5) : le noter, ce n'est pas une anomalie nouvelle (limite, section 8).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-08 — Séparation des tâches (« quatre yeux »)
**Rôle** : `rai`, `auditeur1`, `auditeur2` · **Préconditions** : S3-15 à S3-21.
1. `rai` crée lui-même une fiche (le RAI peut rédiger), la soumet, puis tente de la valider : le bouton « Valider la fiche » est absent (seul « Renvoyer »).
2. `auditeur2` ne peut pas valider ses fiches (il n'est pas valideur).
3. `rai` crée et soumet un constat ; tentative de validation du même constat.
4. `auditeur1` soumet le rapport ; `rai` valide. Faire soumettre le rapport par `rai` s'il est chef : la validation par le même est refusée.
5. `audite1` déclare une action réalisée ; tentative de vérification par le même.

**Résultat attendu** : « Le valideur ne peut pas être l'auteur de la fiche. » / « Vous ne pouvez pas traiter un constat dont vous êtes l'auteur ou le soumetteur. » / « Le valideur ne peut pas être la personne qui a soumis le rapport. » / « Vous avez déclaré cette action : sa vérification revient à une autre personne. » Ces refus valent aussi par accès direct à l'API.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-09 — Remplacement du chef de mission et retrait d'un membre
**Rôle** : `rai` · **Préconditions** : mission en cours avec `auditeur1` chef et `auditeur2` auditeur.
1. Équipe › « Remplacer le chef de mission » : choisir `auditeur2` parmi les auditeurs, « Remplacer ».
2. Lire les rôles : `auditeur1` devient auditeur, sa déclaration est conservée.
3. Avec `auditeur2` (nouveau chef) : « Soumettre » un constat / le rapport (droits de chef).
4. Avec `auditeur1` : vérifier qu'il ne peut plus soumettre.
5. « Retirer de la mission » un membre : confirmation « Retirer cette personne de la mission ? ».

**Résultat attendu** : les droits de chef (soumettre constats et rapport, transmettre le provisoire) suivent le rôle ; le retrait est tracé ; l'historique de l'équipe est conservé.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-10 — Accès à l'objet d'une autre mission
**Rôle** : `auditeur2`, `audite1`, `dg` · **Préconditions** : deux missions M1 (où `auditeur2` et `audite1` sont affectés) et M2 (où ils ne le sont pas) ; un identifiant d'objet de M2 (fiche, constat, action, document) copié depuis la session `rai`.
1. `auditeur2` : coller dans la barre d'adresse `/missions/<id M2>`, `/missions/<id M2>/constats/<id constat M2>`, `/missions/<id M2>/fiches/<id fiche M2>`.
2. `auditeur2` : mélanger les identifiants (id mission M1 avec id de fiche M2).
3. `audite1` : mêmes essais ; puis `/recommandations/actions/<id action M2>`, `/documents/<id document M2>`.
4. `dg` : `/rapports/<id rapport non diffusé>`.
5. Observer les messages et la liste (le nom de la mission M2 n'apparaît nulle part : liste, recherche, notifications).

**Résultat attendu** : « Mission introuvable. », « Cette fiche est introuvable ou vous n'y avez pas accès. », « Ce constat est introuvable. », « Action introuvable. », « Ce document est introuvable ou n'est pas accessible. » : **jamais** le contenu, et le refus ne révèle pas l'existence de l'objet (introuvable plutôt qu'interdit). Toute fuite = anomalie « Sécurité ».

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-11 — Audité d'une autre direction ou sans direction
**Rôle** : `rai`, `audite1` · **Préconditions** : constat validé sur l'entité E1 ; rapport provisoire transmis.
1. `rai` modifie temporairement la direction de `audite1` (S2-12) vers une direction **sans lien** avec E1. `audite1` (reconnecté) tente « Répondre ».
2. Même compte avec la direction **vide**.
3. Rétablir la direction de E1 (ou de sa direction de rattachement) : la réponse redevient possible.
4. Plan d'actions : `audite1` (autre direction) tente « Ajouter une action » sur le constat de E1.

**Résultat attendu** : « Ce constat concerne une autre entité que votre direction. » ; « Votre direction n'est pas renseignée sur votre profil : vous ne pouvez pas répondre. » ; « Seul l'audité responsable de l'entité du constat peut répondre. » ; plan d'actions fermé à cet audité.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-12 — Ce que l'audité ne voit pas
**Rôle** : `audite1` · **Préconditions** : mission avec fiches, pièces, constats brouillon, rapport non diffusé.
1. Ouvrir l'onglet « Fiches de test » et les pièces (adresse directe d'une fiche).
2. « Constats » : seuls les constats soumis ou validés de son entité apparaissent.
3. Rapport (avant diffusion) : `/missions/<id>/rapport`.
4. Entretiens : notes internes de synthèse.
5. Réunions : compte rendu d'une réunion **non tenue** (SEC-09, corrigé : champs vides pour l'audité).
6. Fiche de suivi, référentiel d'audit (avant diffusion).

**Résultat attendu** : fiches, pièces, brouillons et rapport interne : refusés ou absents ; notes internes d'entretien masquées. Le compte rendu et les décisions d'une réunion pas encore tenue sont vides pour l'audité (SEC-09, corrigé).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-13 — Dépôt de fichiers invalides, trop gros, interdits, antivirus
**Rôle** : `auditeur2` (pièce de fiche), `admin` (gabarit), `audite1` (preuve d'action) · **Préconditions** : fiche modifiable, action « En cours ». Préparer les fichiers (PowerShell, dossier de test) :
```
New-Item vide.pdf -ItemType File                                   # 0 octet
Copy-Item $env:WINDIR\System32\notepad.exe faux.pdf                 # exécutable renommé
Copy-Item $env:WINDIR\System32\notepad.exe malware.exe              # extension interdite
$o=[IO.File]::OpenWrite("gros.pdf"); $o.Write([Text.Encoding]::ASCII.GetBytes("%PDF-1.4`n"),0,9); $o.SetLength(52MB); $o.Close()   # 52 Mo
[IO.File]::WriteAllBytes("binaire.txt",[byte[]](72,105,0,0,1,2))    # « texte » avec octets nuls
```
Plus : un `.xlsm` ou `.docm` (macros), un `.docx` valide renommé en `.pdf`, un PDF valide de quelques Ko (cas témoin).
1. Déposer chaque fichier comme pièce justificative de fiche (libellé obligatoire).
2. Déposer le PDF témoin : doit passer.
3. Déposer un `.doc` comme gabarit (S2-27), puis un `.docx` de plus de 10 Mo.
4. Si ClamAV est actif (`ANTIVIRUS_MOTEUR=clamd`) : déposer le fichier de test EICAR (fichier texte standard d'essai antivirus).
5. Annuler un envoi en cours (« Annuler l'envoi ») sur un fichier de 40 Mo.

**Résultat attendu** : refus **avant écriture**, message français sous le champ : vide « Le fichier est vide. » ; exécutable/extension interdite « Ce type de fichier n'est pas accepté. » ; contenu qui ne correspond pas à l'extension « Le contenu du fichier ne correspond pas à son extension. » ; macros « Les fichiers contenant des macros ne sont pas acceptés. » ; trop gros « Le fichier dépasse la taille maximale de 50 Mo. » (gabarit : « Le fichier dépasse 10 Mo. ») ; EICAR « Le fichier a été refusé par l'analyse antivirus. » ; si le démon antivirus est injoignable : « Analyse antivirus indisponible : réessayez plus tard. » (jamais accepté sans analyse). Après tous ces refus : aucune pièce fantôme dans la liste. Sans ClamAV : l'étape 4 est N/A (V-17).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-14 — Intégrité des pièces
**Rôle** : opérateur technique (accès au serveur) puis `auditeur2`, `rai` · **Préconditions** : **environnement de recette uniquement** ; une pièce déposée (S3-15).
1. Noter l'empreinte SHA-256 affichée de la pièce.
2. Télécharger la pièce et calculer son empreinte (`Get-FileHash -Algorithm SHA256 fichier`) : elle doit être identique.
3. Exécuter `python manage.py verifier_pieces --mission DAI/AAAA/Mnn` : aucun écart (code retour 0).
4. Sur le disque (dossier `FICHIERS_RACINE`, par défaut `var/fichiers`), modifier un octet du fichier stocké de cette pièce.
5. Rejouer `verifier_pieces` ; puis tenter le téléchargement dans l'interface.

**Résultat attendu** : étape 3 sans écart ; étape 5 : écart signalé (code 1) ; téléchargement **bloqué** avec « L'intégrité de la pièce n'a pas pu être vérifiée : le fichier est signalé comme altéré. Contactez le RAI. ». Même contrôle pour les versions de documents Word/PDF (« L'intégrité du fichier n'a pas pu être vérifiée : le téléchargement est bloqué ») et pour les empreintes des confirmations.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-15 — Session expirée
**Rôle** : `rai` · **Préconditions** : connecté, un formulaire rempli mais non enregistré.
1. Dans la console Keycloak (realm `onea` › Sessions), « Se déconnecter » la session de `rai` (ou attendre l'expiration du jeton).
2. Dans l'application, cliquer « Enregistrer » ou changer de page.
3. Se reconnecter.

**Résultat attendu** : redirection vers l'écran de connexion avec « Votre session a expiré. Veuillez vous reconnecter. » ; aucune donnée perdue silencieusement, aucune écriture partielle ; après reconnexion on revient sur l'application. Durée de vie réelle des jetons et saisie non enregistrée : à vérifier (V-10).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-16 — Champs invalides, bornes et caractères spéciaux
**Rôle** : `rai`, `auditeur2` · **Préconditions** : formulaires ouverts.
1. Titre de mission de 301 caractères ; libellé de risque de 501 caractères ; matricule de 33 caractères ; justification de 5 001 caractères.
2. Champs obligatoires vides (soumettre le formulaire) : l'erreur doit s'afficher **sous le champ**, le focus se placer dessus, et un lecteur d'écran l'annoncer (`aria-describedby`).
3. Dates : fin avant début (mission, étape, programme, test), échéance passée (action), année du programme `abcd`.
4. Nombres : budget `-1`, charge `1,55` (une décimale), durée d'entretien `601`, délai de rapport provisoire `0`, taille d'échantillon `1.5`.
5. Texte avec `<script>alert(1)</script>`, `' OR 1=1 --`, des emojis et des caractères arabes/accentués dans un titre, un commentaire, un fait constaté.
6. Chaînes ne contenant que des espaces.

**Résultat attendu** : chaque limite produit un message français précis (« Le titre ne doit pas dépasser 300 caractères. », « Le matricule ne peut pas dépasser 32 caractères. »…) ; rien d'enregistré quand invalide ; les caractères spéciaux sont affichés tels quels, **jamais interprétés** (pas de fenêtre d'alerte) ; les espaces seuls sont refusés pour un champ obligatoire.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-17 — Accessibilité au clavier (sans souris)
**Rôle** : `rai`, `auditeur1` · **Préconditions** : débrancher la souris ou ne pas l'utiliser.
1. Tab depuis le haut de page : premier arrêt = « Aller au contenu principal » (visible), Entrée déplace le focus sur le contenu.
2. Parcourir la barre latérale, la recherche, la cloche, le menu utilisateur : focus **toujours visible**, ordre logique.
3. Ouvrir un dialogue (« Valider le jalon ») au clavier : le focus entre dans le dialogue, Tab y reste piégé, **Échap** ferme et rend le focus au bouton d'origine.
4. Matrice 5×5 (risques) : activer une case au clavier ; arbre des objets auditables : flèches haut/bas.
5. Tableaux (missions, registre) : atteindre et ouvrir une ligne au clavier.
6. Formulaire avec erreur : le focus va au premier champ en erreur.
7. Faire zoomer à 200 % : pas de contenu coupé ni de perte de fonction.

**Résultat attendu** : toutes les fonctions sont accessibles sans souris, aucun piège clavier ; états non portés par la couleur seule (texte + icône). Le contrôle automatisé (`frontend/e2e/a11y.spec.ts`, `clavier.spec.ts`) **n'a jamais été exécuté** (V-14) : cette passe manuelle est donc la seule vérification.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-18 — Compte désactivé ou rôle modifié en cours de session
**Rôle** : `admin` et `audite1` · **Préconditions** : `audite1` connecté dans une fenêtre.
1. `admin` désactive le compte `audite1` (S2-13).
2. Dans la fenêtre d'`audite1`, naviguer ou actualiser.
3. `admin` réactive le compte ; `audite1` se reconnecte.

**Résultat attendu** : accès coupé avec l'écran « Compte indisponible » (ou retour à la connexion) ; aucune donnée métier n'est servie après la désactivation (les jetons déjà émis ne suffisent pas, le compte est contrôlé côté serveur ; délai de cache d'informations utilisateur ≤ 60 s). Note : le délai exact est à observer (V-10).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-19 — Impression A4
**Rôle** : `rai`, `auditeur1` · **Préconditions** : navigateur Chrome/Edge, « Imprimer » ou Ctrl+P, destination « Enregistrer en PDF », format A4, marges par défaut.
1. Imprimer : cartographie des risques, programme annuel, fiche de suivi de mission, planning des entretiens, programme de travail, fiche de test, fiche d'observation (constat), plan d'actions, référentiel d'audit, registre des recommandations, tableau de bord RAI et DG.
2. Contrôler pour chacun : lisibilité en A4, pas de menu latéral ni boutons imprimés, tableaux non coupés au milieu d'une ligne, en-tête (Office National de l'Eau et de l'Assainissement · Département Audit Interne, référence), pied de page (« CONFIDENTIEL · USAGE INTERNE ONEA », « Imprimé le … par … », « Page n sur N »).
3. Imprimer un tableau long (plus d'une page) et une liste à 100 lignes.

**Résultat attendu** : documents propres, une information par ligne, aucun texte tronqué. Le rendu A4 n'a jamais été validé visuellement (V-14) : toute dérive est à noter avec capture du PDF.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-20 — Exports CSV/Excel et neutralisation des formules
**Rôle** : `rai` · **Préconditions** : programme brouillon, cartographie brouillon.
1. Créer une mission prévue dont le titre est `=HYPERLINK("http://exemple.test","cliquez")` et une autre commençant par `+1+1`, `@SUM(A1)`, `-2+3`.
2. Exporter le programme en CSV puis en Excel ; ouvrir dans Excel/LibreOffice.
3. Même test avec un libellé de risque dans la cartographie et une action du registre.
4. Vérifier l'accentuation (é, ç, œ) et les dates au format JJ/MM/AAAA.
5. Exporter les taux de mise en œuvre (tableau de bord RAI/DG : « Exporter les taux (Excel) »).

**Résultat attendu** : les valeurs commençant par `=`, `+`, `-`, `@` apparaissent **comme du texte** (pas de formule évaluée, pas de lien actif) ; CSV en UTF-8 avec BOM, séparateur « ; » ; nom de fichier cohérent ; export du registre limité à 5 000 lignes.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-21 — Tableaux de bord par rôle
**Rôle** : les cinq · **Préconditions** : mission au moins avancée à l'étape XVIII, quelques actions en retard.
1. **RAI** : tuiles (Missions en cours, Missions en retard, Jalons à valider, Actions en retard), « Missions par statut » (cliquer une barre → liste filtrée), « File de décisions » (Actions à clôturer, Abandons proposés, Reports en attente, Missions à clôturer, Relances en échec, Relances sans adresse), « Actions par direction », cartographie 5×5, filtre « Année ».
2. **Auditeur** : Mes missions, Étapes en cours (avec « En retard »), Tests à documenter (« Fiche à créer »/« Fiche commencée »), Actions à vérifier.
3. **Audité** : Constats à répondre, Actions ouvertes, En retard, Mes demandes de report.
4. **DG** : Taux de mise en œuvre global et des actions échues, par direction, risques élevés couverts/non couverts, rapports diffusés ; « Exporter les taux (Excel) ».
5. **Admin** : écran d'attente (V-08).
6. Recouper les chiffres avec le registre et la liste des missions.
7. Imprimer le tableau RAI et DG (S4-19).

**Résultat attendu** : chaque rôle ne voit que ses indicateurs ; chiffres cohérents avec les listes ; états de chargement/erreur explicites (« Le tableau de bord n'a pas pu être chargé. » + « Réessayer »), jamais présentés comme « vide ». Les entrées de la file de décisions « Reports en attente », « Relances en échec » et « Relances sans adresse » mènent au registre **non filtré** (limite connue, V-07).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-22 — Journal d'audit (piste d'audit)
**Rôle** : `admin`, `rai`, `auditeur1` · **Préconditions** : plusieurs écritures réalisées.
1. Repérer les journaux **visibles dans l'interface** : « Journal de l'étape », « Journal de la fiche », « Journal du rapport », « Chronologie » d'une action, « Historique du compte » (fiche utilisateur), consultations d'un document.
2. Vérifier que chacun indique qui, quand, quoi (et motif le cas échéant).
3. (Opérateur technique) Interroger `GET /api/v1/audit-log/` avec un jeton `rai` puis `admin` puis `auditeur1` (filtres d'acteur, d'objet).
4. Constater qu'aucune suppression physique n'apparaît : les objets supprimés restent tracés.

**Résultat attendu** : le journal global n'a **pas d'écran** : il est accessible par l'API aux seuls RAI et ADMIN (`auditeur1` : refusé). Le tableau de bord ADMIN annonce « Consulter la piste d'audit » comme disponible dans un lot ultérieur (V-04). Écart de sécurité connu SEC-02 : l'ADMIN lit par cette API le contenu de toutes les missions alors qu'il n'a accès à aucune mission dans l'interface (arbitrage du propriétaire en attente).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-23 — Réglages admin : mode de signature
**Rôle** : `admin`, `rai` · **Préconditions** : aucun certificat de signature configuré (sinon, les modes électroniques sont sélectionnables : voir `docs/exploitation/signature-electronique.md`).
1. `admin` : Administration › Mode de signature (`/administration/signatures`) : lire le tableau (types : ordre de mission, déclaration d'indépendance, validation du rapport ; mode en vigueur ; modifié le, par).
2. Ouvrir la liste des modes d'un type : constater lesquels sont proposés.
3. Tenter de choisir « Signature électronique (PAdES) ».
4. `rai` : ouvrir la même page.
5. Confirmer qu'un changement de mode ne touche que les validations futures.

**Résultat attendu** : seul « Confirmation horodatée » est disponible (« Disponible lorsque le certificat de signature de l'ONEA est configuré sur le serveur ») ; tentative électronique : « La signature électronique n'est pas encore disponible sur cette plateforme. » ; `rai` : « Lecture seule : seul l'administrateur peut modifier le mode de signature. » ; le mode « Confirmation » appliqué au rapport (S3-22) produit une confirmation horodatée avec empreinte, pas une signature qualifiée (SEC-07 : empreinte non scellée par clé).

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-24 — Recherche par rôle et indexation
**Rôle** : `rai`, `auditeur1`, `audite1`, `dg`, `admin` · **Préconditions** : Meilisearch actif et index à jour (`reindexer`), sinon N/A (V-13).
1. Créer une mission au titre unique « ZEBRA-test », un constat « ZEBRA-constat », une action « ZEBRA-action ».
2. Chercher « ZEBRA » avec chaque compte.
3. Chercher le même terme dans une mission où le compte n'est pas affecté.
4. Filtrer par type de résultat.

**Résultat attendu** : le RAI voit les contenus d'équipe ; l'auditeur uniquement ceux de ses missions ; l'audité uniquement ses éléments « audité » (constats soumis/validés de son entité, actions, documents autorisés) ; le DG uniquement ce qui concerne des missions dont le rapport est diffusé ; `admin` : « La recherche n'est pas disponible pour votre profil. ». Aucun résultat vers une mission non visible. Le délai d'indexation des nouveaux objets est à noter.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-25 — Limitation de débit
**Rôle** : `rai` · **Préconditions** : outil de test ou rafale de recherches manuelles.
1. Lancer plus de 60 recherches en une minute (global search), plus de 30 téléversements en une heure, plus de 20 générations de document en une minute.
2. Observer la réponse.

**Résultat attendu** : au-delà du seuil : « Trop de requêtes : réessayez dans quelques instants. » (recherche : « Trop de recherches en peu de temps : patientez une minute. ») ; le service reprend ensuite. Seuils par défaut : génération 20/min, aperçu 30/min, téléversement 30/h, import 10/h, export 30/min, annuaire 60/min, recherche 60/min (réglables). Scénario optionnel, souvent N/A en test manuel.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-26 — Superviseur : validation déléguée des jalons VI, X, XIII
**Rôle** : `rai`, `auditeur2` (rôle Superviseur), `auditeur1` · **Préconditions** : une seconde mission où `auditeur2` est affecté comme **Superviseur** (et `auditeur1` chef, déclarations levées).
1. `auditeur2` (superviseur) : valider les jalons VI, X puis XIII lorsqu'ils sont prêts.
2. `auditeur2` : essayer de valider le jalon XVIII ou de diffuser le rapport.
3. `auditeur2` : valider une fiche soumise par `auditeur1`.
4. Supprimer la levée de déclaration de `auditeur2` (nouvelle déclaration en attente) et recommencer.

**Résultat attendu** : le superviseur à déclaration levée valide VI, X, XIII et les fiches (jamais les siennes) ; **jamais** le jalon XVIII (RAI seul) ni la diffusion ; sans déclaration levée, tout est refusé avec le message de déclaration.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-27 — Dégradation sans service annexe
**Rôle** : `rai` · **Préconditions** : environnement de recette ; arrêter tour à tour Gotenberg, le worker Celery, Meilisearch, le SMTP (un seul à la fois, le remettre ensuite). Ne jamais toucher aux conteneurs d'une autre personne.
1. Sans Gotenberg : « Générer » un document ; ouvrir un rapport validé.
2. Sans worker : demander une génération.
3. Sans Meilisearch : recherche globale.
4. Sans SMTP : déclencher une relance (`envoyer_relances`) et une diffusion.
5. Sans Keycloak (arrêt court) : actualiser l'application ; essayer l'import depuis l'annuaire.
6. Remettre chaque service et vérifier la reprise (« Relancer le PDF »).

**Résultat attendu** : messages clairs et non techniques (« Le PDF n'est pas encore disponible », « La recherche est momentanément indisponible », « Le serveur ou le service d'authentification est injoignable. Veuillez réessayer dans quelques instants. », « L'annuaire (Keycloak) est momentanément indisponible. ») ; les opérations métier internes (saisie, validation) ne sont pas bloquées ; la diffusion refuse tant que le PDF n'est pas prêt ; un échec d'envoi d'e-mail est visible côté RAI sans perdre l'action.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

### S4-28 — Idempotence et sûreté de la commande de peuplement
**Rôle** : opérateur technique · **Préconditions** : base de recette peuplée (cas B).
1. Relancer `peupler_demo --profil volumetrie --echelle 0.2`.
2. Tenter la commande avec `DJANGO_SETTINGS_MODULE=config.settings.prod` (sur un poste de test uniquement, sans base réelle).
3. Tenter sur une base non vide contenant déjà des comptes `rai`/`auditeur1` (cas A).
4. `--a-blanc` : lire le plan sans écriture.

**Résultat attendu** : étape 1 « Données de démonstration déjà présentes : rien à faire (aucun doublon créé). » ; étape 2 « Interdit en production. » ; étape 3 « la base contient déjà des objets métier ou des comptes réservés : le peuplement exige une base vide » ; étape 4 affiche volumes et profil, n'écrit rien.

`[ ] Réussi   [ ] Échec   [ ] N/A     Commentaire : ______`

---

## 7. Matrice des droits attendus rôle × fonctionnalité

Légende : **L** lecture seule ; **E** lecture et écriture/action ; **—** refusé (menu absent, accès direct « Accès refusé » côté interface, 403 ou 404 côté serveur). Mention « (c) » : sous condition précisée dans la note. Sources : `frontend/src/layouts/navigation.ts`, `backend/apps/*/permissions.py`, `droits.py`, `acces.py`.

| Fonctionnalité | ADMIN | RAI | AUDITEUR | AUDITE | DG |
|---|---|---|---|---|---|
| Tableau de bord | écran d'attente | E (pilotage) | propre | propre | propre (+ export des taux) |
| Programme annuel | L | E (créer, modifier, valider, supprimer brouillon, exporter) | L | — | L |
| Référentiel : cartographies, risques, objets auditables | L | E | L | — | L |
| Référentiel : directions et processus | E | E | L | — | L |
| Administration › utilisateurs, import CSV/annuaire, désactivation | E | — | — | — | — |
| Gabarits de documents, numérotation | E | L | — | — | — |
| Mode de signature | E | L | — | — | — |
| Missions : liste | — | toutes | siennes, hors brouillon | celles de son entité, ordre émis | — |
| Créer, modifier, planifier, lancer, suspendre, annuler, supprimer brouillon | — | E | — | — | — |
| Équipe : affecter, retirer, remplacer le chef, arbitrer | — | E | — | — | — |
| Confirmer sa déclaration d'indépendance | — | — | E (la sienne) | — | — |
| Étapes : commencer, terminer, renvoyer, rouvrir, non applicable | — | E | E (c : déclaration levée) | — | — |
| Valider les jalons VI, X, XIII | — | E | E (c : superviseur, déclaration levée) | — | — |
| Valider le jalon XVIII (rapport) | — | E | — | — | — |
| Réunions, entretiens (planifier, tenir) | — | E | E (c : levée) | L (réunions) | — |
| Étapes III à IX (analyse, MARC, programme) | — | E | E (c : levée) | L (référentiel diffusé, avis) | — |
| Fiches de test : rédiger, déposer des pièces | — | E | E (c : chef ou auditeur du test, levée) | — | — |
| Fiches de test : valider, renvoyer | — | E (≠ auteur pour valider) | E (c : superviseur levée, ≠ auteur) | — | — |
| Constats : créer, modifier, supprimer | — | E | E (c : levée, étape XIV active) | — | — |
| Constats : soumettre | — | E | E (c : chef) | — | — |
| Constats : valider, renvoyer, rouvrir | — | E (≠ auteur, soumetteur) | E (c : superviseur levée) | — | — |
| Constats : consulter | — | tous | tous (équipe) | soumis/validés de son entité | — |
| Répondre à un constat / au rapport provisoire | — | — | — | E (c : sa direction = entité) | — |
| Transmettre le rapport provisoire | — | E | E (c : chef) | — | — |
| Rapport : rédiger | — | E | E (c : levée) | — | — |
| Rapport : soumettre | — | — (sauf s'il est chef) | E (c : chef, étape XVII close) | — | — |
| Rapport : valider, renvoyer, diffuser, émettre un corrigé | — | E (valider ≠ soumetteur) | — | — | — |
| Rapports diffusés : consulter | — | L | L (ses missions) | L (ses missions) | L |
| Accuser réception d'un rapport | — | E (c : destinataire interne) | E (c : destinataire) | E (c : destinataire) | E (c : destinataire) |
| Plan d'actions : proposer, modifier, supprimer des actions | — | E | E (c : levée) | E (c : son entité, ses actions) | — |
| Plan d'actions : accepter un risque | — | retirer | — | E (c : recommandation sans action) | — |
| Confirmer son engagement sur le plan | — | — | — | E (c : responsable d'actions) | — |
| Suivi : registre, page d'une action (lecture) | — | L | L (ses missions) | L (son périmètre) | L |
| Suivi : démarrer, déclarer réalisée, déposer une preuve, demander un report, proposer l'abandon | — | E | — | E (c : responsable) | — |
| Suivi : vérifier, rejeter | — | E | E (c : levée, ≠ déclarant) | — | — |
| Suivi : clôturer, rouvrir, accepter l'abandon, décider un report, changer le responsable, clôturer la mission | — | E | — | — | — |
| Documents : registre, générer, télécharger | — | E | selon le type de document | selon le type de document | — |
| Notifications (les siennes) | oui | oui | oui | oui | oui |
| Recherche globale | — | équipe | ses missions | ses éléments « audité » | missions diffusées |
| Tableau de bord RAI / auditeur / audité / DG (API) | — | RAI et DG | Auditeur | Audité | DG |
| Export des taux de mise en œuvre | — | E | — | — | E |
| Journal d'audit (API seulement) | L | L | — | — | — |

Remarques de lecture :
- Pour l'ADMIN, l'API de la piste d'audit expose le contenu des missions (SEC-02) alors que l'interface le lui interdit : l'écart est volontairement noté, voir S4-22.
- L'audité n'accède à une mission que si son ordre de mission est émis et s'il y est affecté comme « Audité ».
- Les droits d'écriture sur les travaux nécessitent toujours une **déclaration d'indépendance levée** et une **mission non figée** (suspendue, annulée, clôturée) et une **étape ouverte**.
- Directions et processus : la route est interdite à l'AUDITE dans l'interface ; le serveur autorise la lecture à tous les rôles (`TOUS_ROLES`). L'accès direct à l'API par l'audité n'est pas testé par l'interface (V-15).

---

## 8. Limites connues, hors périmètre et points « à vérifier »

### 8.1 Limites connues (vérifiées dans le dépôt)

| Limite | Source | Conséquence pour les tests |
|---|---|---|
| **Courrier sortant** : l'adresse par défaut est `smtp://mailpit:1025`. La pile de développement (`docker/compose.dev.yml`) fournit Mailpit (interface http://127.0.0.1:8025) mais la passation (`HANDOFF.md` §4) ne liste que PostgreSQL, Keycloak et Redis. Sans SMTP, aucun e-mail ne part | `base.py`, `compose.dev.yml` | relances et diffusion : notifications internes seules ; échec visible dans « Relances en échec » |
| **Recherche Meilisearch** : service fourni par `make up`, absent de la passation locale ; sans lui, recherche indisponible. L'ADMIN n'a jamais accès à la recherche | `compose.dev.yml`, `recherche/visibilite.py` | S1-10, S4-24 en N/A |
| **Worker Celery + Gotenberg** : la génération Word/PDF et la conversion se font en tâche de fond ; sans eux le PDF n'est jamais prêt et la diffusion du rapport est refusée | `documents/services/generation.py`, `communication/services/diffusion.py` | S2-29, S3-22 dégradés |
| **Signature électronique PAdES (lot 7 bis) non installée** : seuls les modes « Confirmation horodatée » sont utilisables ; les modes électroniques sont refusés | `signatures/electronique.py`, `parametres.py` | S4-23 |
| **Confirmations horodatées non scellées par clé** (empreinte SHA-256 sans HMAC) | ASVS SEC-07 | une confirmation n'est pas une signature qualifiée |
| **Gabarits Word provisoires** : les 22 gabarits officiels ONEA restent à récupérer ; les documents générés utilisent des modèles vierges provisoires | `docs/HANDOFF.md`, `docs/documents/gabarits-manquants.md` | ne pas juger la mise en page des documents Word |
| **Tests de bout en bout (Playwright) jamais exécutés** ; audit d'accessibilité automatisé « outillage livré, exécution en attente » ; bancs réseau du lot 9 non lancés ; suites de tests complètes non relancées | `docs/HANDOFF.md`, `docs/qualite/audit-accessibilite.md` | la présente recette manuelle est la première vérification navigateur réelle |
| **Antivirus** : `ANTIVIRUS_MOTEUR=aucun` par défaut, ClamAV (conteneur séparé) non livré en développement ; les formats OLE (`doc`, `xls`, `msg`) ne sont pas inspectés pour les macros | `core/antivirus.py`, ASVS SEC-04 | S4-13 étape 4 N/A sans ClamAV |
| **OTP des comptes à privilèges** et politique de mots de passe : non appliqués en développement | ASVS SEC-03 | S1-04 : pas de verrouillage garanti |
| **Piste d'audit sans écran** : API seule ; lecture du contenu des missions possible par l'ADMIN | ASVS SEC-02, `core/views.py` | S4-22 |
| **Conflits d'intérêts lisibles par toute l'équipe** | ASVS SEC-08 | constat connu à ne pas rouvrir (SEC-09, compte rendu d'une réunion non tenue, est corrigé) |
| ~~File de décisions du RAI : liens vers le registre non filtré~~ : corrigé, les liens mènent aux écrans `/recommandations/reports` et `/recommandations/relances` filtrés | `docs/HANDOFF.md` §2ter | S4-21 (clos) |
| **Relances** : aucun écran dédié (API réservée au RAI, commande `envoyer_relances`, tâche quotidienne à 7 h) | `suivi/urls_relances.py` | S3-30 |
| **Tableau de bord ADMIN** : écran d'attente | `DashboardAdmin.tsx` | S1-02 |
| **Revues visuelles « ui-designer » et revues de sécurité des plans non faites** | `docs/HANDOFF.md` | remarques d'ergonomie attendues |
| **Données de démonstration** limitées à l'étape VIII ; aucune donnée fictive pour constats, rapports, recommandations, suivi | `*/demo.py` | niveaux 3 et 4 saisis à la main |
| **Mots de passe de démonstration** : comptes `peupler_demo` sans mot de passe utilisable (liaison Keycloak) | `users/demo.py` | cas B de 1.3 |

### 8.2 Hors périmètre de cette recette

Charge et performance (voir `docs/qualite/performance.md`), sauvegarde et restauration, durcissement
réseau et TLS, mise en production (`docs/exploitation/mise-en-production.md`), compatibilité de
navigateurs anciens, application mobile, intégrations externes (SIRH, messagerie ONEA), et tout
traitement par intelligence artificielle (exclu du produit par règle du projet).

### 8.3 Points « à vérifier »

Éléments que le code ne permet pas d'affirmer ; à confirmer pendant la campagne puis à lever.

| Réf. | Point | Où |
|---|---|---|
| V-01 | Les comptes du profil `formation` (`formation.rai`, etc.) n'existent pas dans Keycloak : procédure de rattachement à confirmer | 1.3 |
| V-02 | Keycloak fournit-il l'attribut `direction` des comptes de test (`audite1`) ? Sinon le renseigner en S2-12 | 1.2, S3-19 |
| V-03 | Comportement exact de deux modifications simultanées d'un même enregistrement (aucun verrou optimiste repéré) | S4-01 |
| V-04 | Aucun écran pour la piste d'audit globale ; l'entrée « Consulter la piste d'audit » du tableau de bord ADMIN est annoncée pour un lot ultérieur | S4-22 |
| V-05 | Le worker Celery, Gotenberg et les gabarits provisoires sont-ils démarrés/chargés (`gabarits_provisoires`) dans l'environnement de recette ? | 1.1, S2-26, S2-29 |
| V-06 | Aucun écran des relances (seul l'état d'échec est visible dans la file du RAI) | S3-30 |
| V-07 | Filtres manquants de la file de décisions du RAI | S4-21 |
| V-08 | Tableau de bord ADMIN : écran d'attente (« Administration de la plateforme ») | S1-02 |
| V-09 | Pied du menu : « Version 0.5 · lot 5 » semble obsolète (texte de version) | S1-09 |
| V-10 | Durée de vie des jetons Keycloak, délai de prise en compte d'une désactivation, devenir d'un formulaire non enregistré à l'expiration | S4-15, S4-18 |
| V-11 | Textes résiduels de lots antérieurs (« sera généré au lot 4 », « Disponible dans un prochain lot », « sera complétée dans la suite du lot 3 ») : lesquels s'affichent encore ? À éviter en démonstration | 2.1, S3-04, S3-05 |
| V-12 | Plusieurs rôles dans une même mission pour une même personne (affectation unique ?) | S3-01, S4-26 |
| V-13 | Index de recherche : délai d'indexation d'un nouvel objet et nécessité de `reindexer` | S1-10, S4-24 |
| V-14 | Rendu d'impression A4 et accessibilité réelle : jamais vérifiés dans un navigateur | S4-17, S4-19 |
| V-15 | Accès direct à l'API du référentiel de structure par un audité (le serveur autorise la lecture à tous les rôles ; l'interface l'interdit) | 7 |
| V-16 | Messages exacts affichés pour un dépassement de débit (HTTP 429) dans chaque écran | S4-25 |
| V-17 | Disponibilité du conteneur ClamAV en recette | S4-13 |
| V-18 | Contenu exact des documents générés (étape, numéro, rendu) tant que les gabarits officiels manquent | S2-29 |

Récapitulatif : **18 points « à vérifier »**.

---

## 9. Récapitulatif de campagne

| Champ | Valeur |
|---|---|
| Version testée (commit) | |
| Date de début / fin | |
| Testeur(s) | |
| Navigateur(s) | |
| Base de recette (nom, profil de données) | |
| Services actifs (Celery, Gotenberg, Meilisearch, SMTP, ClamAV) | |

| Niveau | Scénarios | Réussis | Échecs | N/A |
|---|---|---|---|---|
| 1 — simples (S1-01 à S1-13) | 13 | | | |
| 2 — courants (S2-01 à S2-30) | 30 | | | |
| 3 — métier (S3-01 à S3-33) | 33 | | | |
| 4 — complexes (S4-01 à S4-28) | 28 | | | |
| **Total** | **104** | | | |

Anomalies ouvertes : bloquantes ___ · majeures ___ · mineures ___ · cosmétiques ___ · sécurité ___.

Décision de recette : `[ ] Acceptée   [ ] Acceptée avec réserves   [ ] Refusée`
Signatures : testeur ______________  responsable du projet ______________  date __/__/____
