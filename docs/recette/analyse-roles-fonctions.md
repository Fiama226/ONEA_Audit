# Analyse : rôles applicatifs et fonctions ONEA

Date : 02/11/2026. Branche analysée : `develop` (commit `b6822e3`). Analyse en lecture seule :
aucun test ni serveur lancé. Les écarts signalés « d'après le code » sont à confirmer par un test.

## 1. Question posée

La plateforme a 5 rôles applicatifs (`backend/apps/users/models.py:6-11`) : ADMIN, RAI, AUDITEUR,
AUDITE, DG. Les documents ONEA citent 12 fonctions : Président du Comité d'Audit, Audité, Auditeur,
Responsable Audité, Directeur pilote, DoQ, Chef du Département Audit Interne, Directeur Général,
Président du Conseil d'Administration, Directeur Audit Interne, Chef de mission, Superviseur.
Chaque fonction doit-elle devenir un rôle applicatif ?

**Réponse courte : non.** Aucune de ces fonctions ne justifie un 6e rôle. Les droits dépendent
de trois choses que la plateforme sépare déjà :

1. le **rôle global** (5 valeurs) : ce que la personne peut faire dans toute la plateforme ;
2. le **rôle dans la mission** (`RoleMission`, `backend/apps/missions/models.py:64-68` :
   CHEF_MISSION, AUDITEUR, SUPERVISEUR, AUDITE), porté par `AffectationMission`
   (`missions/models.py:254-289`) : ce qu'elle fait sur *cette* mission ;
3. la **fonction** (champ texte libre `User.fonction`, `users/models.py:30`, 128 caractères,
   déjà modifiable dans l'écran de profil `frontend/src/features/utilisateurs/components/ProfileForm.tsx:17`,
   l'import CSV et l'annuaire) : le titre officiel, imprimé dans les documents.

S'y ajoute la **liste de diffusion** du rapport (`DestinataireDiffusion`,
`communication/models.py:400-456`), qui accepte des destinataires externes (nom + qualité) sans
compte.

## 2. Sources consultées et limites

- Spécification : `docs/superpowers/specs/2026-10-27-plateforme-audit-interne-design.md`
  (§5 l. 79-90, §6.5-6.6 l. 120-135, §13-14 l. 214-245).
- Domaine : `docs/domaine/processus-ifaci.md`, `docs/domaine/cartographie-risques-onea.md`,
  `docs/domaine/documents-mission.md` ; référentiel `backend/apps/referentiel/data/referentiel-onea.csv`.
- Contrats de gabarits : `docs/documents/contrats/*.md`, `docs/documents/gabarits-manquants.md`.
- Sources ONEA hors dépôt (dossier OneDrive) : `Fiches Methodologiques de Conduite mission.pdf`,
  `Normes internationales d'audit interne Français-2025.pdf`, `Cartographie des risques stratégiques.docx`.
- Code : `users`, `missions` (acces, equipe, etapes), `communication` (droits, permissions,
  diffusion, validation), `signatures`, `recommandations`, `suivi`, `programmation`,
  `tableaux_de_bord`, `documents/generators/missions.py`.

**Limite importante.** Hormis Audité, Auditeur, Chef de mission, Superviseur, DG et DOQ,
**les fonctions de la liste n'apparaissent dans aucun fichier du dépôt ni dans les sources ONEA
lisibles**. « Président du Comité d'Audit », « PCA », « Directeur pilote », « Responsable Audité »,
« Chef du Département Audit Interne », « Directeur Audit Interne » viennent très probablement des
22 gabarits Word non reçus (le dossier `__Audit Internes Recueil_Besoin` ne contient que des
fichiers `*_Error.txt` « RemoteAccessDenied », dont `Lettre DG au DC audit du processus de
passation des marchés.docx`). Les recommandations ci-dessous pour ces fonctions reposent donc sur
des hypothèses à confirmer (§7).

## 3. Ce que fait le code aujourd'hui (résumé)

| Sujet | Règle actuelle | Référence |
|---|---|---|
| Visibilité des missions | RAI : toutes ; AUDITEUR : celles où il est intervenant ; AUDITE : celles où il est affecté comme audité, après émission de l'ordre ; DG et ADMIN : aucune | `missions/acces.py:91-108` |
| Chef de mission | rôle de mission unique par mission ; doit avoir le rôle global AUDITEUR | `missions/models.py:277-282`, `missions/services/equipe.py:47-51` |
| Superviseur | unique par mission, différent du chef ; valide les jalons VI, X, XIII (pas XVIII), déclaration d'indépendance levée | `missions/models.py:283-287`, `equipe.py:56-63`, `missions/acces.py:65-75`, spec l. 228-229 |
| Rapport | chef soumet ; RAI valide (jamais le soumetteur) et diffuse | `communication/droits.py:90-108` |
| Constat, fiche de test, étape | valideur ≠ auteur (quatre yeux) | `constats/services/constats.py:77`, `accomplissement/services/fiches.py:36`, `missions/services/etapes.py:123` |
| « Responsable de l'entité » | tout AUDITE affecté dont `direction_code` = entité du constat | `missions/acces.py:82-88` |
| Acceptation du risque, réponse au provisoire | réservées au « responsable de l'entité » ci-dessus | `recommandations/services/acceptations.py:50-54`, `communication/services/provisoire.py:201-210` |
| DG | lecture seule partout ; voit **tous** les rapports diffusés, tout le suivi, les tableaux de bord DG | `users/permissions.py:27-36`, `communication/droits.py:111-120`, `suivi/droits.py:41-43`, `tableaux_de_bord/views.py:98,122` |
| Liste de diffusion | préremplie avec **tous** les DG actifs, les audités affectés et le chef ; le RAI ajoute des internes ou des externes (nom + qualité, « remis hors plateforme ») | `communication/services/diffusion.py:101-170` |
| Fonction du signataire de l'ordre de mission | **codée en dur** : « Responsable de l'Audit Interne » | `documents/generators/missions.py:27,223` |
| Programme annuel | validé par le RAI seul ; DG en lecture | `programmation/models.py:37-55`, `programmation/permissions.py:3-4` |

## 4. Analyse fonction par fonction

### 4.1 Président du Comité d'Audit

- **Où** : absent du dépôt sous ce nom. La spec fond le comité d'audit dans le rôle DG
  (spec l. 87 : « DG | Direction Générale, comité d'audit ») ; `processus-ifaci.md:17` et `:43`
  le citent comme « client » de l'audit. Normes 2025 : Norme 8.1 (relation avec le Conseil),
  9.4 (« Le Conseil doit approuver le plan »), 11.3 et 15.1 (communication des résultats).
- **Doit voir** : rapports finaux ou leur synthèse, programme annuel, état du suivi des
  recommandations. **Ne fait rien** dans le cycle de mission.
- **Recommandation** : **destinataire de diffusion** (externe, « remis hors plateforme ») par
  défaut. S'il doit consulter la plateforme : **rôle DG existant** + fonction « Président du
  Comité d'Audit ». Pas de nouveau rôle.
- **Attention** : le rôle DG voit *tous* les rapports diffusés et il est ajouté d'office à toutes
  les listes de diffusion (`diffusion.py:115`). Acceptable pour un comité d'audit (IIA), à
  confirmer par l'ONEA.

### 4.2 Audité

- **Où** : rôle `AUDITE` (`users/models.py:10`) et rôle de mission `AUDITE` (`missions/models.py:68`) ;
  spec l. 86 ; `processus-ifaci.md:58,97,263,280`.
- **Fait** : donne son avis sur le référentiel et les constats, répond au rapport provisoire,
  propose et met à jour ses actions.
- **Recommandation** : **rôle applicatif existant** (AUDITE) + affectation par mission. Couvert.

### 4.3 Auditeur

- **Où** : rôle `AUDITEUR` (`users/models.py:9`), rôle de mission `AUDITEUR` (`missions/models.py:66`) ;
  spec l. 85 ; `processus-ifaci.md:78,152,170`.
- **Recommandation** : **rôle applicatif existant**. Couvert.

### 4.4 Responsable Audité

- **Où** : spec l. 86 (« AUDITE | responsable d'une entité auditée ») ; `processus-ifaci.md:115,134,293-298,317`
  (« responsables du domaine audité » valident les observations, étape XIV, et portent le plan
  d'actions, étape XV). Dans le code : `est_responsable_entite` (`missions/acces.py:82-88`).
- **Doit faire** : valider les observations au nom de la direction, répondre au rapport
  provisoire, accepter un risque, s'engager sur le plan d'actions.
- **Écart** : le code ne distingue pas le responsable de ses collaborateurs. **Tout audité
  affecté de la même direction** peut accepter un risque « au nom de ma direction »
  (`recommandations/services/acceptations.py:32,50-54`) ou répondre au provisoire.
- **Recommandation** : **attribut par mission** (case « responsable de l'entité » sur
  l'affectation d'un audité), fonction informative sur le profil. Pas de nouveau rôle.

### 4.5 Directeur pilote

- **Où** : absent du dépôt. Hypothèse la plus probable : **pilote de processus** au sens du
  système de management de la qualité (ISO 9001). Le référentiel rattache chaque processus à une
  ou plusieurs directions (`referentiel-onea.csv:19-29`, ex. GAC → DM, DL). Hypothèse
  alternative : directeur qui pilote la mise en œuvre d'un plan d'actions transverse.
- **Doit faire** : même chose que le responsable audité pour le processus audité, et souvent
  recevoir le rapport.
- **Recommandation** : **attribut par mission** (même case « responsable de l'entité ») et
  **destinataire de diffusion**. Si l'ONEA confirme que chaque processus a un directeur pilote
  unique, ajouter ensuite un champ « direction pilote » au processus dans le référentiel (évolution
  optionnelle, hors périmètre minimal).

### 4.6 DoQ (Direction de l'Organisation et de la Qualité)

- **Où** : `referentiel-onea.csv:8` (direction DOQ), `:20` (processus PSM « Piloter le Système
  de Management de la Qualité » rattaché à DOQ) ; `cartographie-risques-onea.md:10`.
- **Nature** : c'est une **entité**, pas une fonction de l'audit. Son directeur est un
  utilisateur AUDITE (direction `DOQ`).
- **Doit voir** : vraisemblablement les rapports (lien avec les revues de direction qualité) ;
  est audité quand la mission porte sur PSM.
- **Recommandation** : **destinataire de diffusion** (catégorie « Autre ») ; AUDITE affecté
  seulement quand la DOQ est auditée.
- **Écart** : voir §5.1, un destinataire interne non affecté ne peut pas ouvrir le rapport.

### 4.7 Chef du Département Audit Interne

- **Où** : spec l. 4 (DAI = Département Audit Interne) et l. 84 (« RAI | Responsable de l'Audit
  Interne, chef du DAI ») ; `referentiel-onea.csv:7` ; glossaire `docs/manuels/glossaire.md:17`.
- **Recommandation** : **rôle applicatif existant RAI**, fonction « Chef du Département Audit
  Interne » sur le profil.
- **Écart** : l'ordre de mission imprime toujours « Responsable de l'Audit Interne »
  (`documents/generators/missions.py:27,223`), quelle que soit la fonction du signataire.

### 4.8 Directeur Général

- **Où** : rôle `DG` (`users/models.py:11`), compte de démonstration « Directeur général »
  (`users/demo.py:36`) ; spec l. 87 ; `processus-ifaci.md:43` (client de l'audit).
- **Fait** : lit les rapports diffusés, les tableaux de bord, le suivi (`users/permissions.py:27-36`).
- **Question ouverte** : le fichier non reçu « Lettre DG au DC audit du processus de passation
  des marchés » laisse penser que **le DG signe la lettre d'annonce ou de mandat** de la mission.
  La plateforme fait signer l'ordre de mission par le RAI ; le DG est en lecture seule.
- **Recommandation** : **rôle applicatif existant DG**. Si le DG doit signer, traiter la lettre
  comme document généré par le RAI et signé hors plateforme, plutôt que d'ouvrir l'écriture au DG.

### 4.9 Président du Conseil d'Administration

- **Où** : absent du dépôt. Normes 2025, Norme 9.4 : le Conseil approuve le plan d'audit.
- **Doit voir** : programme annuel, rapports ou synthèses, état du suivi ; rarement un compte
  sur la plateforme.
- **Recommandation** : **destinataire de diffusion** (externe). Rôle DG seulement si l'ONEA veut
  qu'il consulte en ligne.
- **Écart** : le programme annuel n'a qu'une validation RAI (`programmation/models.py:47-55`) ;
  rien ne trace l'approbation par le Conseil (date, référence de délibération).

### 4.10 Directeur Audit Interne

- **Où** : absent du dépôt. Deux lectures : même personne que le chef du DAI (titre différent),
  ou niveau hiérarchique au-dessus.
- **Recommandation** : **rôle RAI**, fonction « Directeur de l'Audit Interne ». Le code
  n'impose pas un RAI unique : deux personnes peuvent avoir le rôle RAI, chacune voit et valide
  tout. Si l'ONEA veut un seul valideur, c'est une règle d'organisation.

### 4.11 Chef de mission

- **Où** : `RoleMission.CHEF_MISSION` (`missions/models.py:65`), unique par mission
  (`:278-282`) ; spec l. 85 ; `processus-ifaci.md:223,334` ; balise `mission.chef_mission` de
  tous les contrats (`docs/documents/contrats/*.md:26`).
- **Recommandation** : **attribut par mission** (existant). Couvert.

### 4.12 Superviseur

- **Où** : `RoleMission.SUPERVISEUR` (`missions/models.py:67`), unique, distinct du chef
  (`equipe.py:56-63`) ; droits `missions/acces.py:65-75`, `missions/services/etapes.py:168-180` ;
  spec l. 90, 216, 228-229 ; `processus-ifaci.md:20,187,223`.
- **Recommandation** : **attribut par mission** (existant). Couvert.

## 5. Écarts réels

### 5.1 Destinataire interne non affecté : lien mort (gravité moyenne)

`ajouter_destinataire` accepte n'importe quel utilisateur actif (`diffusion.py:143-170`) et
`_envoyer` lui adresse un e-mail avec un lien vers le rapport (`diffusion.py:254`). Mais la
lecture passe par `rapports_lisibles` / `rapports_diffuses_visibles`
(`communication/permissions.py:49-56`, `communication/droits.py:111-120`) : un AUDITE ou un
AUDITEUR **non affecté à la mission** n'y a pas accès (404) et ne peut pas accuser réception
(`destinataires_lisibles`, `permissions.py:83-94`). Concerne DoQ, directeur pilote, tout
directeur en copie. Aucun test ne couvre ce cas (`backend/tests/communication/`). Contournement
actuel : l'inscrire comme destinataire externe et cocher « remis hors plateforme ».

### 5.2 Responsable audité non distingué (gravité moyenne)

Voir §4.4 : n'importe quel collaborateur audité de la direction peut accepter un risque ou
répondre au rapport provisoire pour la direction. Contraire à `processus-ifaci.md:293-298`
(validation par les *responsables* du domaine audité).

### 5.3 Fonction du signataire codée en dur (gravité faible)

`FONCTION_RAI = "Responsable de l'Audit Interne"` (`documents/generators/missions.py:27`)
alors que `User.fonction` existe. Les documents officiels porteront un titre inexact si l'ONEA
dit « Chef du Département » ou « Directeur ».

### 5.4 Rôle DG trop large pour des membres du Conseil (à arbitrer)

Le rôle DG voit tous les rapports diffusés, même si le RAI le retire de la liste de diffusion
(`communication/droits.py:115-116`), et il est ajouté d'office à chaque liste
(`diffusion.py:113-116`). Pour un PCA ou un président de comité d'audit, c'est conforme à l'IIA ;
si l'ONEA veut une diffusion sélective, il faut les traiter en destinataires externes.

### 5.5 Approbation du programme par le Conseil non tracée (gravité faible)

Norme 9.4. Pas de champ « approuvé par le Conseil le / référence ». Hors cycle de mission.

### 5.6 Pas d'intérim du RAI sur le jalon XVIII (à arbitrer)

Seul un utilisateur RAI valide et diffuse le rapport (`communication/droits.py:97-103`, spec
l. 229). Si l'ONEA n'a qu'un RAI, son absence bloque la diffusion. Contournement : un second
compte RAI (rien ne l'interdit dans le code).

### 5.7 Séparation des tâches et quatre yeux : correcte

Valideur ≠ auteur pour constats, fiches, étapes et rapport ; superviseur ≠ chef ; chef et
superviseur obligatoirement AUDITEUR ; déclaration d'indépendance levée avant de contribuer
(`missions/acces.py:59-62`). Aucun écart trouvé. Seule nuance : le RAI peut contribuer
(`peut_contribuer` renvoie vrai pour le RAI) et valider, mais le contrôle auteur ≠ valideur
s'applique aussi à lui.

## 6. Plus petit changement proposé

Aucun nouveau rôle. Trois changements, par ordre de priorité :

| # | Changement | Modèle | API | UI | Tests | Effort |
|---|---|---|---|---|---|---|
| A | Case « responsable de l'entité » sur l'affectation d'un audité (`AffectationMission.responsable_entite`, booléen, défaut faux) ; `est_responsable_entite` (`missions/acces.py:82`) l'exige. Compatibilité : si aucune affectation de la direction n'est cochée, garder la règle actuelle (à arbitrer, Q3) | 1 champ + 1 migration (contrainte : refusé si `role_mission` ≠ AUDITE) | sérialiseur d'affectation + service `affecter` / nouvelle action « désigner responsable » | case à cocher dans l'écran Équipe de la mission | ~8 appelants de `est_responsable_entite` à re-tester (acceptation du risque, réponse au provisoire, réponses aux constats), + tests de la contrainte | ~1 à 1,5 j |
| B | Destinataire interne non affecté : l'ajouter à la lecture des rapports diffusés (`rapports_diffuses_visibles` et `rapports_lisibles` : `OR destinataires__utilisateur=user`) pour le rapport et la note seulement, pas pour la mission | aucun | 2 fonctions de droits | aucun (la page « Rapports diffusés » existe) | 3 à 5 tests (lecture, téléchargement, accusé de réception, pas d'accès à la mission) | ~0,5 j |
| C | Fonction réelle du signataire : remplacer `FONCTION_RAI` par `confirmation.signataire.fonction or FONCTION_RAI` (repli) dans `documents/generators/missions.py:223` | aucun | aucun | aucun | 1 test de génération | ~1 h |
| D (option) | Approbation du programme par le Conseil : 2 champs facultatifs `approuve_conseil_le`, `reference_deliberation` sur `ProgrammeAnnuel`, saisis par le RAI | 2 champs + migration | sérialiseur | 2 champs dans le formulaire | 2 tests | ~0,5 j |

Le champ « fonction » sur le compte **existe déjà** (texte libre). Le transformer en liste
fermée n'apporte rien aux droits ; si l'ONEA veut une liste, une liste de suggestions côté UI
suffit, sans migration.

Mode opératoire immédiat, sans code : renseigner la fonction de chaque compte ; donner RAI au
chef du DAI (et au directeur de l'audit interne si distinct), DG au Directeur Général, AUDITE aux
directeurs et agents des entités ; inscrire PCA, président du comité d'audit et DoQ comme
destinataires externes « remis hors plateforme » tant que B n'est pas fait.

## 7. Questions métier à poser à l'ONEA

1. **Gabarits** : merci de transmettre les 22 fichiers Word ; où apparaissent exactement
   « Président du Comité d'Audit », « PCA », « Directeur pilote », « Responsable Audité »,
   « DoQ » (en-tête, signature, liste de diffusion) ?
2. **Chef du DAI / Directeur Audit Interne** : une seule personne ou deux niveaux ? Si deux,
   qui valide le rapport final (jalon XVIII) ?
3. **Responsable audité** : seul le directeur de l'entité peut-il accepter un risque, répondre au
   rapport provisoire et engager le plan d'actions, ou un collaborateur délégué le peut-il aussi ?
4. **Directeur pilote** : s'agit-il du pilote de processus (SMQ) ? Chaque processus a-t-il un seul
   directeur pilote ? Doit-il valider quelque chose ou seulement recevoir le rapport ?
5. **DoQ** : la DOQ reçoit-elle systématiquement les rapports et plans d'actions ? Doit-elle
   suivre les actions (lecture du registre de suivi) ?
6. **Comité d'audit et PCA** : auront-ils un compte sur la plateforme ou reçoivent-ils les
   documents par courrier ? Doivent-ils voir **tous** les rapports ou seulement ceux qui leur
   sont adressés (rapport complet ou note synthétique) ?
7. **Directeur Général** : signe-t-il la lettre d'annonce ou l'ordre de mission ? Accepte-t-il des
   risques au niveau de l'entreprise ?
8. **Programme annuel** : est-il approuvé par le Conseil d'administration ou le comité d'audit ?
   Faut-il tracer la date et la référence de la délibération ?
9. **Superviseur** : à l'ONEA, est-ce un auditeur senior (comme dans la plateforme) ou le chef du
   DAI lui-même ?
10. **Intérim** : qui valide et diffuse un rapport quand le chef du DAI est absent ?
