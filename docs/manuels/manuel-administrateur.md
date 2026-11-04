# Manuel de l'administrateur fonctionnel

Plateforme d'audit interne ONEA — Département Audit Interne (DAI).
Ce manuel s'adresse au compte au rôle « Administrateur ». L'administrateur crée et gère les comptes
utilisateurs (mots de passe temporaires, rôles, activation, délégation), les gabarits de documents, leur numérotation, le mode de signature et, avec le RAI, la structure
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

1. Ouvrez la plateforme : la page « Connexion » s'affiche.
2. Saisissez votre « Identifiant ou courriel professionnel » et votre « Mot de passe », puis cliquez sur
   « Se connecter ».
3. Vous arrivez sur l'écran « Administration de la plateforme ».

**Première connexion.** Le premier administrateur est créé par l'exploitant (commande `creer_administrateur`),
qui lui remet un mot de passe temporaire valable 72 heures. À la première connexion, la plateforme affiche
« Changer le mot de passe » : saisissez le mot de passe temporaire dans « Mot de passe actuel », choisissez un
nouveau mot de passe d'au moins 12 caractères (évitez un mot de passe courant ou proche de votre identifiant),
confirmez-le, puis « Changer le mot de passe ». Il est recommandé de disposer d'au moins **deux** administrateurs
nominatifs, afin que l'un puisse réinitialiser le mot de passe de l'autre.

**Mot de passe oublié.** « Mot de passe oublié ? » sur la page « Connexion », puis « Recevoir un code » : un code à
6 chiffres, valable 10 minutes, est envoyé par courriel (le message affiché est le même que le compte existe ou
non), puis « Saisir le code reçu », le code et un nouveau mot de passe, « Enregistrer le mot de passe ». Sans
courriel, un autre administrateur réinitialise votre mot de passe (2.6) ; à défaut, l'exploitant relance
`creer_administrateur` sur votre identifiant.

**Connexion refusée.** « Identifiant ou mot de passe incorrect. » est le message unique, quelle qu'en soit la
cause. Après cinq échecs consécutifs, le compte est bloqué 15 minutes. La session se ferme après 8 heures, ou
30 minutes sans activité.

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
il propose « Mon compte », « Changer mon mot de passe », « Visite guidée de la plateforme » et « Se déconnecter ».
Dans « Mon compte », le réglage facultatif « Demander un code par courriel à chaque connexion » (désactivé par
défaut) ajoute, après le mot de passe, l'étape « Vérification en deux étapes » (code à 6 chiffres reçu par courriel,
valable 10 minutes). Vous seul pouvez l'activer, et seulement si l'envoi de courriels est configuré. Il n'existe pas
d'entrée « Aide » à ce jour (voir « À confirmer »).

---

## 2. Gérer les utilisateurs

Les comptes sont créés et administrés dans la plateforme : il n'y a pas d'annuaire externe. Vous créez le compte
d'un agent avec son **rôle** (obligatoire), un mot de passe temporaire lui est attribué, et vous gérez ensuite son
profil (direction, fonction, matricule), son rôle, son activation, la réinitialisation de son mot de passe et les
droits que vous lui déléguez. Ces actions sont tracées dans l'« Historique du compte ».

### 2.1 Consulter et filtrer la liste

1. « Administration », puis « Utilisateurs » (adresse `/administration/utilisateurs`).
2. Recherchez par nom, identifiant ou matricule.
3. Filtrez par rôle, direction et statut (« Actifs », « Désactivés », « En attente de première connexion »).
   « Effacer les filtres » réinitialise.

[Capture à insérer : CAP-ADM-03 — Liste des utilisateurs avec filtres]

### 2.2 Créer un agent

1. « Nouvel agent ». Saisissez l'« Identifiant » (lettres sans accent, chiffres et caractères . + - _ ; 150 caractères au plus)
   et choisissez le « Rôle » (obligatoire). Le courriel professionnel, le nom, le prénom, le matricule, la direction
   et la fonction peuvent être renseignés dès la création ou plus tard.
2. Laissez cochée « Envoyer le courriel de bienvenue » pour que l'agent reçoive son identifiant et son mot de passe
   temporaire par courriel (il faut alors une adresse de courriel et un envoi configuré).
3. « Créer le compte ». La fenêtre « Compte créé » indique si le courriel a été **mis en file d'envoi** : il part
   alors dans les instants qui suivent, par le service d'envoi de la plateforme. **Sinon** (case décochée, envoi non
   configuré, compte sans adresse, service d'envoi momentanément injoignable), le « Mot de passe temporaire »
   s'affiche **une seule fois** : copiez-le (« Copier le mot de passe ») ou notez-le et transmettez-le à l'agent par
   un moyen sûr, puis « J'ai noté le mot de passe, fermer ». Il ne sera plus jamais affiché.
   « Mis en file d'envoi » ne garantit pas la réception : si l'agent ne reçoit rien dans l'heure, réinitialisez son
   mot de passe en décochant l'envoi (2.6) et transmettez-lui le mot de passe affiché.
4. Le mot de passe temporaire est valable 72 heures et doit être changé à la première connexion. Passé ce délai, il
   faut le réinitialiser (2.6).

Seul un administrateur peut attribuer les rôles « Administrateur », « Responsable de l'audit interne » (RAI) et
« Direction générale » (DG) ; un délégué ne propose que « Auditeur interne » et « Audité ». L'identifiant ne
contient que des lettres non accentuées, des chiffres et les caractères . + - _ : un agent au nom accentué
(« Aïcha ») reçoit un identifiant sans accent (`aicha.ouedraogo`) et peut aussi se connecter avec son adresse de
courriel.

### 2.3 Renseigner le profil et changer le rôle

1. Ouvrez la fiche : identité, origine, première connexion, rôle.
2. Renseignez **Direction**, **Fonction** et **Matricule** (32 caractères au plus) ; le courriel professionnel se
   corrige ici aussi, il sert à la récupération du compte.
3. « Enregistrer le profil » : « Profil enregistré. »
4. Pour changer le rôle : bloc « Rôle », « Nouveau rôle », « Changer le rôle », puis « Confirmer le changement ». Les
   accès de l'agent changent dès sa prochaine action. Le rôle Administrateur donne tous les droits : n'y recourez
   qu'avec prudence.
5. Votre propre rôle ne se modifie pas (« Vous ne pouvez pas modifier votre propre rôle. »), et le dernier
   administrateur actif ne peut être ni désactivé ni rétrogradé.
6. L'« Historique du compte » liste chaque modification (date, auteur, changements).

La direction d'un audité est déterminante : elle décide des constats auxquels il peut répondre. Elle doit
être celle de l'entité auditée ou sa direction de rattachement.

[Capture à insérer : CAP-ADM-04 — Fiche utilisateur, profil et historique]

### 2.4 Désactiver et réactiver un compte

1. Fiche utilisateur, « Désactiver le compte ». Saisissez le motif (« Le motif est obligatoire. »), puis
   « Désactiver ».
2. L'utilisateur ne peut plus se connecter ni réinitialiser son mot de passe, et ses sessions ouvertes sont
   fermées. Ses affectations et ses travaux sont conservés.
3. « Réactiver le compte » rétablit l'accès. Vous ne pouvez pas désactiver votre propre compte, ni le dernier administrateur actif.

[Capture à insérer : CAP-ADM-05 — Dialogue de désactivation d'un compte]

### 2.5 Importer des comptes depuis un fichier CSV

1. « Importer un fichier CSV ». Le fichier est en UTF-8 avec les colonnes
   `identifiant;email;prenom;nom;role;direction;fonction;matricule` (`identifiant` et `role` obligatoires) ; séparateur
   « ; » ou « , » ; 300 lignes et 1 Mo au plus.
2. « Vérifier le fichier » : le rapport indique ce qui serait fait ; aucun compte n'est encore créé.
3. Laissez cochée « Envoyer le courriel de bienvenue à chaque compte créé » si l'envoi de courriels est configuré.
4. « Importer » (le bouton n'est actif qu'après vérification) : « Import terminé », avec les comptes créés et les
   lignes ignorées et leur motif. Chaque compte créé reçoit un mot de passe temporaire (72 heures).
5. **Fichier des mots de passe.** Les mots de passe qui n'ont pas été mis en file d'envoi par courriel sont réunis dans un fichier :
   « Télécharger le fichier des mots de passe ». Il ne peut être téléchargé qu'**une seule fois**, par vous qui avez
   lancé l'import, dans les 24 heures ; il est ensuite détruit (« Ce fichier n'est plus disponible : il a déjà été
   téléchargé ou a expiré »). Conservez-le en lieu sûr, transmettez chaque mot de passe à son titulaire par un moyen
   sûr, puis supprimez le fichier. En cas de perte, réinitialisez les comptes concernés (2.6). Un courriel mis en
   file mais jamais reçu n'est pas dans ce fichier : réinitialisez aussi ce compte.
6. Le rôle « ADMIN » n'est jamais attribué par fichier : la ligne est ignorée ; créez le compte, puis changez son rôle
   (2.3).

[Capture à insérer : CAP-ADM-06 — Import CSV, rapport de vérification]

### 2.6 Réinitialiser un mot de passe ou désactiver le code de connexion

Agent qui a oublié son mot de passe sans pouvoir recevoir de courriel, compte bloqué, mot de passe temporaire
expiré : après avoir vérifié l'identité de la personne,

1. Ouvrez la fiche, bloc « Connexion et mot de passe », « Réinitialiser le mot de passe ».
2. Laissez cochée « Envoyer le nouveau mot de passe par courriel » si l'agent a une adresse et si l'envoi est
   configuré : le courriel est mis en file d'envoi ; sinon le mot de passe temporaire s'affiche une seule fois à
   l'écran (voir 2.2). Si l'agent ne reçoit rien, recommencez en décochant l'envoi.
3. Le nouveau mot de passe temporaire (72 heures) remplace l'actuel, le compte est débloqué et **toutes ses sessions
   sont fermées** ; l'agent choisira son mot de passe à la connexion suivante. Un compte désactivé ne peut pas être réinitialisé ; pour votre
   propre compte, utilisez « Changer mon mot de passe ».
4. Si l'agent a activé le code de connexion par courriel et ne le reçoit plus : « Désactiver le code de connexion ».
   L'agent se connecte alors avec son seul mot de passe. Seul lui pourra le réactiver, dans « Mon compte ».
   L'action est journalisée.

### 2.7 Déléguer la gestion des comptes

Depuis la fiche d'un agent, le bloc « Délégation de la gestion des comptes » vous permet de lui confier, par case à
cocher, tout ou partie de quatre droits : « Créer des comptes », « Réinitialiser les mots de passe et désactiver le
code de connexion », « Changer les rôles et la direction », « Désactiver et réactiver des comptes » ; puis
« Enregistrer la délégation ». Les droits prennent effet immédiatement et se retirent à tout moment de la même façon.

Limites : un délégué ne gère que les comptes **Auditeur interne et Audité**. Il n'agit jamais sur un administrateur,
un RAI, un DG, un autre délégué ni sur son propre compte (les boutons d'action n'apparaissent pas sur ces fiches) ;
il n'attribue que les rôles Auditeur interne et Audité ; il ne délègue pas. L'import CSV, la gestion des délégations
et toute action sur un compte RAI ou DG restent réservés aux administrateurs. **Attention** : un délégué qui peut
« créer des comptes » ou « réinitialiser les mots de passe » peut voir des mots de passe temporaires (envoi décoché)
et ainsi prendre la main sur un compte auditeur ou audité. Ne déléguez qu'à des agents de confiance, pour le besoin
strict, et retirez le droit dès qu'il n'est plus utile.

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
2. Tant que le certificat de signature de l'ONEA n'est pas configuré sur le serveur, seul le mode
   « Confirmation horodatée » est disponible : les modes électroniques sont présentés comme « Disponible
   lorsque le certificat de signature de l'ONEA est configuré sur le serveur » ; les choisir répond :
   « La signature électronique n'est pas encore disponible sur cette plateforme. » Une fois le certificat
   installé (voir `docs/exploitation/signature-electronique.md`), « Signature électronique (PAdES) » et
   « Confirmation et signature électronique » deviennent sélectionnables : le RAI doit alors signer le
   rapport validé avant de le diffuser.
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
- **Mots de passe** : jamais visibles après coup. Un mot de passe temporaire ne s'affiche qu'une fois (création,
  réinitialisation) ; le fichier d'un import ne se télécharge qu'une fois, sous 24 heures. Transmettez-les par un
  moyen sûr, jamais par un canal partagé.
- **Rôle** : attribué à la création, modifiable dans la fiche du compte ; seul un administrateur donne les rôles
  Administrateur, RAI et DG, et gère ces comptes.
- **Code de connexion par courriel** : seul le titulaire l'active ; vous (ou un délégué autorisé, pour un compte
  auditeur ou audité) pouvez le désactiver s'il bloque l'agent.
- **Courriels** : « mis en file d'envoi » signifie confié au service d'envoi de la plateforme, pas encore reçu. Un
  courriel qui n'arrive pas se rattrape par une réinitialisation avec affichage du mot de passe (2.6).
- **Mot de passe oublié** : après 15 codes erronés en 24 heures sur un compte, plus aucun code n'est accepté pour ce
  compte jusqu'à la fin de ces 24 heures ; votre réinitialisation (2.6) permet à l'agent de se reconnecter plus tôt.
- **Motif obligatoire** pour désactiver un compte.
- **Traçabilité** : chaque modification de compte est consignée dans l'« Historique du compte » ; rien n'est supprimé physiquement.
- **Gabarits** : seule la version activée sert aux nouveaux documents ; les documents existants gardent leur version.
- **Limites de débit** : les imports, les créations de comptes et les réinitialisations de mot de passe sont limités ; au-delà : « Trop de requêtes : réessayez dans quelques instants. »
- **Journal d'audit global** : accessible par l'interface de programmation seulement (aucun écran) ; il est réservé au RAI et à l'administrateur.

---

## 7. Messages fréquents

| Message | Signification |
|---|---|
| « Accès refusé » | Page non autorisée pour votre rôle. |
| « Le motif est obligatoire. » | Motif de désactivation manquant. |
| « Vérifiez d'abord le fichier » | L'import CSV exige la vérification préalable. |
| « Le fichier dépasse 1 Mo. » | Fichier CSV trop gros. |
| « Identifiant ou mot de passe incorrect. » | Message unique de la page de connexion (mot de passe erroné, compte inconnu, désactivé ou verrouillé) : réinitialisez le mot de passe de l'agent (2.6). |
| « Si un compte correspond, un code vous a été envoyé. » | Réponse de « Mot de passe oublié », identique que le compte existe ou non. |
| « Seul un administrateur peut attribuer les rôles Administrateur, Responsable de l'audit interne et Direction générale. » | Action réservée aux administrateurs (un délégué ne donne que les rôles Auditeur interne et Audité). |
| « Vous n'avez pas le droit d'effectuer cette action sur ce compte. » | Un délégué a tenté d'agir sur un compte qui lui est fermé (administrateur, RAI, DG, autre délégué, son propre compte). |
| « Trop de demandes, réessayez plus tard. » / « Trop de requêtes : réessayez dans… » | Limite de débit atteinte. |
| « Ce fichier n'est plus disponible… » | Fichier des mots de passe déjà téléchargé ou expiré (2.5). |
| « La signature électronique n'est pas encore disponible sur cette plateforme. » | Mode électronique non installé. |

---

## 8. Questions fréquentes

**Un audité ne peut pas répondre à un constat.** Vérifiez sa direction dans sa fiche (2.2) : elle doit correspondre à l'entité du constat.

**Un agent n'arrive plus à se connecter.** Réinitialisez son mot de passe (2.6) ; s'il avait activé le code de connexion par courriel et ne le reçoit pas, désactivez-le aussi.

**L'agent ne reçoit pas son mot de passe temporaire par courriel.** « Mis en file d'envoi » ne garantit pas la réception (service d'envoi arrêté, relais en panne, adresse erronée) : réinitialisez son mot de passe en décochant l'envoi (2.6) et relevez le mot de passe affiché une fois à l'écran. Signalez-le à l'exploitant, qui contrôle le service d'envoi.

**Plusieurs agents d'un même site reçoivent « Trop de tentatives, réessayez dans quelques minutes. » à la connexion.** Les limites de connexion comptent par adresse réseau ; derrière une même adresse, de nombreuses erreurs de mot de passe bloquent les connexions de ce site jusqu'à 15 minutes. Attendez, puis signalez-le à l'exploitant si cela se répète.

**Je ne trouve pas le rôle à modifier.** Ouvrez la fiche du compte, bloc « Rôle » (2.3).

**Puis-je supprimer un compte ?** Non : on le désactive (réversible).

**Un document existant est-il modifié si j'active un nouveau gabarit ?** Non.

---

## 9. À confirmer

- V-04 : piste d'audit globale sans écran ; l'entrée « Consulter la piste d'audit » est annoncée pour plus tard.
- V-08 : écran d'accueil d'attente.
- V-15 : accès direct à l'interface de programmation du référentiel par un rôle sans droit d'écriture.
- Emplacement exact de « Mode de signature » dans la page « Administration » (la route `/administration/signatures` existe ; le libellé du lien reste à relever à l'écran).
- Procédures de ce manuel (création, réinitialisation, import, délégation) non encore rejouées sur l'application en fonctionnement.
- Envoi des courriels (bienvenue, code de connexion, mot de passe oublié) : dépend du relais SMTP de l'ONEA, non encore fourni, et du service d'envoi de la plateforme ; sans eux, appliquer les replis décrits en 2.2 et 2.6.
- Libellés exacts des écrans de délégation et de création après la restriction des délégués aux comptes auditeur et audité : à relever à l'écran.

## 10. Glossaire

Voir [glossaire.md](glossaire.md).
