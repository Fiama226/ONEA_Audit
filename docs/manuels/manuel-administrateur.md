# Manuel de l'administrateur fonctionnel

Plateforme d'audit interne ONEA — Département Audit Interne (DAI).
Ce manuel s'adresse au compte au rôle « Administrateur ». L'administrateur gère les comptes
utilisateurs, les gabarits de documents, leur numérotation, le mode de signature et, avec le RAI, la structure
du référentiel (directions et processus). Il n'accède à aucune mission.

## Sommaire

1. Prise en main
2. Gérer les utilisateurs
3. Gérer les gabarits de documents et leur numérotation
4. Choisir le mode de signature
5. Structure du référentiel
6. Règles à connaître
7. Messages fréquents
8. Questions fréquentes
9. À confirmer
10. Glossaire

---

## 1. Prise en main

### 1.1 Se connecter

1. Ouvrez la plateforme ; cliquez sur « Se connecter ».
2. Saisissez votre identifiant et votre mot de passe sur la page d'authentification de l'ONEA.
3. Vous arrivez sur l'écran « Administration de la plateforme ».

[Capture à insérer : CAP-COM-01 — Page de connexion]
[Capture à insérer : CAP-ADM-01 — Écran d'accueil de l'administrateur]

L'écran d'accueil est un écran d'attente : il annonce des fonctions à venir, comme « Consulter la piste
d'audit ». Utilisez la barre latérale.

### 1.2 Naviguer

| Groupe | Entrées visibles |
|---|---|
| (sans titre) | « Tableau de bord » |
| « Conduite des missions » | « Programme annuel » (lecture), « Référentiel » |
| « Paramétrage » | « Administration », « Gabarits de documents » |

Les entrées « Missions », « Recommandations », « Rapports diffusés » et « Documents » ne sont pas proposées : un
accès par adresse directe affiche « Accès refusé » (« Votre rôle ne donne pas accès à cette page. »). La
recherche globale n'est pas disponible pour votre profil.

[Capture à insérer : CAP-ADM-02 — Barre latérale de l'administrateur]

### 1.3 Profil, aide, déconnexion

Le menu utilisateur (en haut à droite) affiche votre nom, votre adresse et votre rôle « Administrateur » ;
il propose « Se déconnecter ». Il n'existe pas d'entrée « Aide » à ce jour (voir « À confirmer »).

---

## 2. Gérer les utilisateurs

Les comptes sont créés dans l'annuaire de l'ONEA (Keycloak). La plateforme les relie à la première
connexion. Le **rôle** est attribué dans l'annuaire : il n'est pas modifiable dans la plateforme. Vous gérez
la direction, la fonction et le matricule, l'activation et les imports.

### 2.1 Consulter et filtrer la liste

1. « Administration », puis « Utilisateurs » (adresse `/administration/utilisateurs`).
2. Recherchez par nom, identifiant ou matricule.
3. Filtrez par rôle, direction, statut (« Actifs », « Désactivés », « En attente de première connexion ») et
   synchronisation Keycloak. « Effacer les filtres » réinitialise.

[Capture à insérer : CAP-ADM-03 — Liste des utilisateurs avec filtres]

### 2.2 Renseigner le profil d'un utilisateur

1. Ouvrez la fiche : identité, origine, première connexion, rôle.
2. Renseignez **Direction**, **Fonction** et **Matricule** (32 caractères au plus).
3. « Enregistrer le profil » : « Profil enregistré. »
4. L'« Historique du compte » liste chaque modification (date, auteur, changements).

La direction d'un audité est déterminante : elle décide des constats auxquels il peut répondre. Elle doit
être celle de l'entité auditée ou sa direction de rattachement.

Une fois saisis dans la plateforme, direction et fonction ne suivent plus l'annuaire ; « Rétablir la
synchronisation » les rend de nouveau synchronisés.

[Capture à insérer : CAP-ADM-04 — Fiche utilisateur, profil et historique]

### 2.3 Désactiver et réactiver un compte

1. Fiche utilisateur, « Désactiver le compte ». Saisissez le motif (« Le motif est obligatoire. »), puis
   « Désactiver ».
2. La plateforme indique l'état de la synchronisation avec l'annuaire (sessions fermées, ou échec avec
   « Relancer la synchronisation »).
3. L'utilisateur voit l'écran « Compte indisponible » à sa prochaine connexion.
4. « Réactiver le compte » rétablit l'accès. Ne désactivez pas votre propre compte (comportement du serveur dans ce cas : à confirmer).

[Capture à insérer : CAP-ADM-05 — Dialogue de désactivation d'un compte]

### 2.4 Importer des comptes depuis un fichier CSV

1. « Importer un fichier CSV ». Le fichier est en UTF-8 avec les colonnes
   `identifiant;email;prenom;nom;role;direction;fonction;matricule` ; taille maximale 1 Mo.
2. « Vérifier le fichier » : le rapport indique ce qui serait fait ; aucun compte n'est encore créé.
3. « Importer » (le bouton n'est actif qu'après vérification) : « Import terminé », avec les comptes créés, mis à
   jour et les lignes ignorées et leur motif.
4. Le rôle « ADMIN » n'est jamais attribué par fichier : la ligne est ignorée.

[Capture à insérer : CAP-ADM-06 — Import CSV, rapport de vérification]

### 2.5 Importer depuis l'annuaire

1. « Importer depuis l'annuaire » ; saisissez au moins deux caractères (« Saisissez au moins 2 caractères. »).
2. Cochez les comptes (jusqu'à 50) puis « Importer la sélection ». Les comptes déjà présents sont marqués
   « Déjà présent ».
3. Si l'annuaire est arrêté : « L'annuaire (Keycloak) est momentanément indisponible. »

---

## 3. Gérer les gabarits de documents et leur numérotation

Les documents (ordre de mission, procès-verbaux, rapport…) sont produits à partir de modèles Word. Les
modèles actuels sont **provisoires** : une bannière indique « n documents utilisent un gabarit provisoire en attente
du modèle officiel ONEA ».

### 3.1 Consulter

« Gabarits de documents » (ou « Administration » puis la page des gabarits) : liste des types avec gabarit actif,
étape et contrat. Ouvrez un type pour voir l'historique des versions et les balises du contrat (bouton « Copier »).

[Capture à insérer : CAP-ADM-07 — Liste des types de documents et gabarits]

### 3.2 Déposer, prévisualiser et activer une version

1. Ouvrez le type ; « Déposer une nouvelle version » ; choisissez un fichier `.docx` de 10 Mo au plus ; ajoutez un commentaire
   si utile ; « Déposer ».
2. « Aperçu Word » (et « Aperçu PDF » si disponible) pour contrôler le rendu.
3. « Activer » la version et confirmez. Les prochains documents utiliseront cette version ; **les documents déjà
   générés ne changent pas**.

Refus possibles : « Les fichiers .doc ne sont pas acceptés… », « Le fichier dépasse 10 Mo. », « Le fichier n'est
pas un document Word .docx valide. », et, pour un gabarit non conforme, la liste « Le gabarit est refusé pour les
raisons suivantes ».

[Capture à insérer : CAP-ADM-08 — Dépôt et activation d'une version de gabarit]

### 3.3 Numérotation des documents

1. Onglet « Numérotation » : modèle, portée (« Par mission » ou « Par année »), abréviation, aperçu.
2. Modifiez un modèle avec les champs permis `{mission}`, `{annee}`, `{code}`, `{sequence}` (exemple
   `{mission}-{code}-{sequence}`). L'aperçu est calculé par le serveur ; enregistrez.
3. L'abréviation ne dépasse pas 8 caractères.

Le nouveau format ne s'applique qu'aux documents créés ensuite.

[Capture à insérer : CAP-ADM-09 — Numérotation des documents]

---

## 4. Choisir le mode de signature

1. « Administration », « Mode de signature » (`/administration/signatures`). Le tableau liste les types
   (ordre de mission, déclaration d'indépendance, validation du rapport), le mode en vigueur, la date et l'auteur de la dernière modification.
2. Seul le mode « Confirmation horodatée » est disponible. Le mode « Signature électronique (PAdES) » est
   présenté comme « Disponible après l'installation de la signature électronique (lot 7 bis) » ; le choisir
   répond : « La signature électronique n'est pas encore disponible sur cette plateforme. »
3. Un changement de mode ne concerne que les validations futures.

Le RAI voit la même page en lecture seule.

[Capture à insérer : CAP-ADM-10 — Mode de signature]

---

## 5. Structure du référentiel

Vous créez, modifiez et supprimez (suppression logique) les **directions** et les **processus**, comme le RAI.
Les cartographies, risques et objets auditables sont en lecture seule pour vous.

1. « Référentiel », onglet « Processus » : « Créer un processus » (code de 3 lettres majuscules, libellé, famille,
   directions rattachées). Le code ne se modifie plus après création.
2. Onglet « Directions » : « Ajouter une direction ou un département ». Un département exige une direction parente.
3. Messages de contrôle : « Deux à cinq lettres majuscules, sans accent. », « Le libellé est obligatoire. », « Choisissez une
   famille. »

[Capture à insérer : CAP-ADM-11 — Référentiel, onglet Directions (écriture)]

---

## 6. Règles à connaître

- **Aucun accès aux missions** : vous ne voyez ni missions, ni constats, ni rapports, ni recommandations.
- **Rôle et annuaire** : le rôle se règle dans l'annuaire ; la plateforme ne l'affecte pas.
- **Motif obligatoire** pour désactiver un compte.
- **Traçabilité** : chaque modification de compte est consignée dans l'« Historique du compte » ; rien n'est supprimé physiquement.
- **Gabarits** : seule la version activée sert aux nouveaux documents ; les documents existants gardent leur version.
- **Limites de débit** : les imports et la recherche d'annuaire sont limités ; au-delà : « Trop de requêtes : réessayez dans quelques instants. »
- **Journal d'audit global** : accessible par l'interface de programmation seulement (aucun écran) ; il est réservé au RAI et à l'administrateur.

---

## 7. Messages fréquents

| Message | Signification |
|---|---|
| « Accès refusé » | Page non autorisée pour votre rôle. |
| « Le motif est obligatoire. » | Motif de désactivation manquant. |
| « Vérifiez d'abord le fichier » | L'import CSV exige la vérification préalable. |
| « Le fichier dépasse 1 Mo. » | Fichier CSV trop gros. |
| « Compte indisponible » | Ce que voit un utilisateur désactivé. |
| « L'annuaire (Keycloak) est momentanément indisponible. » | Panne de l'annuaire ; réessayez plus tard. |
| « La signature électronique n'est pas encore disponible sur cette plateforme. » | Mode électronique non installé. |

---

## 8. Questions fréquentes

**Un audité ne peut pas répondre à un constat.** Vérifiez sa direction dans sa fiche (2.2) : elle doit correspondre à l'entité du constat.

**Je ne trouve pas le rôle à modifier.** Il se règle dans l'annuaire, pas dans la plateforme.

**Puis-je supprimer un compte ?** Non : on le désactive (réversible).

**Un document existant est-il modifié si j'active un nouveau gabarit ?** Non.

---

## 9. À confirmer

- V-01 : rattachement dans l'annuaire des comptes de formation (`formation.rai`, etc.), qui n'y existent pas.
- V-02 : l'annuaire fournit-il l'attribut « direction » ? Sinon, il faut le saisir (2.2).
- V-04 : piste d'audit globale sans écran ; l'entrée « Consulter la piste d'audit » est annoncée pour plus tard.
- V-08 : écran d'accueil d'attente.
- V-10 : délai exact de prise en compte d'une désactivation sur une session ouverte.
- V-15 : accès direct à l'interface de programmation du référentiel par un rôle sans droit d'écriture.
- Emplacement exact de « Mode de signature » dans la page « Administration » (la route `/administration/signatures` existe ; le libellé du lien reste à relever à l'écran).
- Procédure de création d'un compte dans l'annuaire : non décrite ici, elle relève de l'exploitation.

## 10. Glossaire

Voir [glossaire.md](glossaire.md).
