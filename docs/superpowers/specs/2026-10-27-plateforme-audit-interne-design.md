# Conception — Plateforme de digitalisation de l'audit interne ONEA

Date : 27/10/2026. Statut : **approuvé le 27/10/2026** (réponses client intégrées en section 15).
Auteur : IKA SOLUTION LTD (rédigé avec assistance IA). Client : ONEA, Département Audit Interne (DAI).

## 1. Intention

Remplacer la conduite des missions d'audit interne sur fichiers Word et Excel dispersés par
une plateforme web unique qui guide l'équipe d'audit à travers les 18 étapes de la
méthodologie IFACI, produit automatiquement les documents officiels ONEA à partir des
données saisies, impose les validations du Responsable de l'Audit Interne (RAI) aux jalons,
conserve une piste d'audit complète conforme aux Normes IIA 2024, et suit la mise en œuvre
des recommandations jusqu'à clôture.

Pourquoi maintenant : le DAI dispose d'une cartographie des risques stratégiques, d'une
décomposition en objets auditables et d'une vingtaine de gabarits de documents, mais aucun
outil ne relie ces éléments. La traçabilité, la supervision et le suivi des recommandations
reposent sur la discipline individuelle.

Succès : une mission complète (ordre de mission, rapport validé, suivi des actions) se
déroule intégralement dans la plateforme, chaque document officiel en sort au format Word
ONEA sans retouche manuelle, et le RAI voit en un écran l'état de toutes les missions et
de toutes les recommandations ouvertes.

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**
1. Guider une mission à travers les 3 phases et 18 étapes IFACI avec les livrables de chaque étape.
2. Gérer le référentiel : processus ONEA, directions, objets auditables, cartographie des risques (matrice 5×5).
3. Générer les documents officiels ONEA (gabarits Word) depuis les données saisies, les versionner, les exporter en PDF.
4. Imposer les circuits de validation (RAI) et l'indépendance (déclaration signée, séparation auteur/valideur).
5. Suivre les recommandations et plans d'actions avec échéances, responsables, relances, statut.
6. Offrir des tableaux de bord par rôle (RAI, auditeur, audité, DG).
7. Historiser toute action (piste d'audit) et protéger la confidentialité par rôle et périmètre.

**Non-objectifs (v1)**
- Planification annuelle du programme d'audit (norme 9.4) : saisie simple d'une liste de missions planifiées, pas d'algorithme de priorisation.
- Gestion du temps / feuilles d'heures des auditeurs.
- Édition collaborative en temps réel des documents.
- Application mobile native (le web responsive suffit, mobile en lecture).
- Intégration avec un ERP ou le SI ONEA (hors annuaire Keycloak/AD).

**Anti-objectifs**
- **Aucune fonctionnalité d'intelligence artificielle ni appel à un LLM dans le produit.** Une proposition en ce sens est un défaut.
- Aucune dépendance payante ou propriétaire.
- Un outil qui remplace le jugement de l'auditeur par des automatismes : la plateforme structure et trace, elle ne décide pas.

## 3. Contraintes

- Open source exclusivement (MIT, BSD, Apache 2.0, PostgreSQL, LGPL, AGPL).
- Interface, documents et notifications en français ; fuseau `Africa/Ouagadougou`.
- Hébergement sur site ONEA (serveur Linux, Docker). Pas de dépendance à Internet en production.
- Conformité aux Normes IIA 2024 : documentation des missions (14.6), supervision (12.x), suivi (15.2), confidentialité (5.2).
- Gabarits Word ONEA : 22 des 27 fichiers du recueil n'ont pas pu être récupérés (accès OneDrive refusé). Leur structure exacte sera intégrée dès réception ; le moteur de génération est conçu pour accueillir n'importe quel gabarit docx.
- Volumétrie : quelques dizaines d'utilisateurs, quelques dizaines de missions par an, documents jusqu'à ~50 Mo (pièces justificatives scannées).

## 4. Stack (décidée)

| Couche | Choix |
|---|---|
| Backend | Python 3.12, Django 5.x, Django REST Framework, drf-spectacular, django-fsm, django-auditlog, django-filter, django-environ, django-storages |
| Frontend | React 19, TypeScript strict, Vite, React Router, TanStack Query + Table, shadcn/ui (Radix, Tailwind), react-hook-form + zod, Lucide |
| Données | PostgreSQL 16 |
| Fond | Celery + Redis (Valkey) |
| Documents | docxtpl pour remplir les gabarits Word, Gotenberg (conteneur) pour PDF |
| Recherche | Meilisearch |
| Fichiers | MinIO (S3) |
| Auth | Keycloak (OIDC) ; connexion possible à l'annuaire ONEA ; auth locale Django en dev |
| Tests | pytest, factory_boy, Vitest, Testing Library, MSW, Playwright |
| Qualité | ruff, mypy, ESLint, Prettier, pre-commit |
| Infra | Docker Compose (dev et prod), Nginx, Gitea Actions ou GitHub Actions |

Justification : application métier centrée formulaires, workflow et documents Word ; Django
fournit ORM, migrations, permissions et admin ; Python est le meilleur écosystème pour
remplir des gabarits docx ; React + shadcn donne une interface institutionnelle propre.

## 5. Acteurs et rôles

| Rôle | Description | Droits |
|---|---|---|
| ADMIN | administrateur technique (DSI) | utilisateurs, rôles, référentiels, gabarits, paramètres |
| RAI | Responsable de l'Audit Interne, chef du DAI | crée/affecte les missions, valide les jalons, diffuse les rapports, voit tout |
| AUDITEUR | auditeur interne ; l'un d'eux est **chef de mission** | saisit et documente les missions où il est affecté ; le chef de mission soumet à validation |
| AUDITE | responsable d'une entité auditée | voit les missions de son périmètre (ordre de mission, PV, rapport diffusé, plan d'actions), répond aux constats, met à jour ses actions |
| DG | Direction Générale, comité d'audit | lecture des rapports validés, des tableaux de bord et du suivi des recommandations |

Un utilisateur a un rôle global et des affectations par mission. Le RAI peut déléguer la
supervision d'une mission à un auditeur « superviseur » (note IFACI étape I).

## 6. Modules fonctionnels

### 6.1 Référentiel
- Processus ONEA (13, codés EST, PSM, CGP, FEP, PAS, GCL, GRH, GSI, GAC, GFI, AFO), directions et départements rattachés.
- Objets auditables : domaine, opérations, risques, objectif de contrôle, dispositif de contrôle interne.
- Cartographie des risques : risque codé `n-PROC-Rk`, probabilité et impact 1 à 5, score, niveau FAIBLE/MOYEN/ÉLEVÉ, commentaire de vulnérabilité, réponse, priorité. Vue matrice 5×5 interactive et export.
- Versions annuelles de la cartographie (figées).

### 6.2 Missions
- Création par le RAI : titre, type (assurance / conseil), processus et entités concernés, événement déclencheur, période, auditeurs affectés, chef de mission, dates prévisionnelles.
- **Stepper des 18 étapes** groupées en 3 phases. Chaque étape a : description IFACI, entrées, livrables obligatoires, formulaire(s), documents générables, bouton « Terminer l'étape » (chef de mission) et, aux jalons, « Valider » (RAI). Une étape se termine seulement si ses livrables obligatoires existent.
- Fiche de suivi de mission : journal automatique des étapes, dates réelles vs prévues, budget jours.
- Réunions (ouverture, lancement, clôture) : date, participants, ordre du jour, décisions, PV généré.
- Entretiens : planning, interlocuteurs, compte rendu, note de synthèse.
- Déclaration d'indépendance : un enregistrement par auditeur affecté, à confirmer avant l'étape II.

### 6.3 Analyse et référentiel d'audit (étapes III à VII)
- Questionnaire de prise de connaissance, grille de séparation des tâches, diagrammes de flux (pièce jointe), QCI.
- Matrice MARC : pour chaque objet auditable retenu : risque, objectif de contrôle, contrôle attendu, contrôle existant, évaluation de la conception, force/faiblesse.
- Tableau des forces et faiblesses apparentes.
- Référentiel d'audit soumis puis **validé par le RAI** (jalon VI).
- Objectifs d'audit sélectionnés, rapport d'orientation généré.

### 6.4 Programme de travail (étapes VIII à XI)
- Programme de travail : par objectif d'audit, tests prévus (nature, procédure, échantillon, auditeur, charge).
- Budget et ressources ; organisation de mission **validée par le RAI** (jalon X).
- Réunion de lancement, PV.

### 6.5 Accomplissement (étapes XII à XIV)
- Fiches de test : objectif, procédure, échantillon, pièces justificatives (upload MinIO), résultat, conclusion (satisfaisant / point fort / anomalie). Feuille de couverture de test et feuille de travail générées.
- Validation des preuves par le RAI ou superviseur (jalon XIII) ; renvoi possible avec commentaire.
- Fiches d'observation (constats) : fait constaté, référentiel, cause (diagramme cause/effet en champs), conséquence, niveau de risque, recommandation(s). Validation par l'audité (accord / désaccord motivé).

### 6.6 Communication (étapes XV à XVIII)
- Réunion de clôture, PV.
- Plan d'actions : pour chaque recommandation, action, responsable (audité), échéance, indicateur.
- Rapport : assemblage automatique (synthèse, contexte, objectifs, méthodologie, constats, recommandations, plan d'actions, annexes) en Word ONEA + PDF ; note synthétique.
- Circuit : brouillon, relu (chef de mission), **validé** (RAI, jalon XVIII), diffusé (liste de diffusion, DG, audités). Toute version diffusée est figée.

### 6.7 Suivi des recommandations
- Registre transverse de toutes les recommandations ouvertes : mission, entité, priorité, responsable, échéance, statut (à lancer / en cours / réalisée / abandonnée justifiée), preuves de mise en œuvre.
- Mise à jour par l'audité, vérification par l'auditeur, clôture par le RAI.
- Relances automatiques (e-mail) à J-15, J et J+15 ; tableau des retards.

### 6.8 Documents
- Gabarits docx ONEA stockés dans la plateforme, versionnés, modifiables par l'ADMIN.
- Génération docxtpl à partir du contexte métier ; aperçu PDF ; téléchargement Word.
- Chaque document a des versions ; une version validée est immuable (hash SHA-256, auteur, date).
- Numérotation automatique (ex. `DAI/2026/M07/RAP-01`), paramétrable.

### 6.9 Tableaux de bord et recherche
- RAI : missions par phase et statut, retards, jalons à valider, recommandations en retard par direction, cartographie.
- Auditeur : mes missions, mes étapes en cours, mes tests à documenter.
- Audité : mes constats à répondre, mes actions et échéances.
- DG : rapports diffusés, taux de mise en œuvre des recommandations, risques élevés couverts/non couverts.
- Recherche plein texte Meilisearch sur missions, constats, recommandations, documents.

### 6.10 Administration et sécurité
- Utilisateurs via Keycloak (rôles mappés), gestion des affectations dans la plateforme.
- Piste d'audit consultable par l'ADMIN et le RAI : qui, quand, quoi, avant/après.
- Journal des consultations des documents sensibles.
- Sauvegardes PostgreSQL et MinIO planifiées (script fourni).

## 7. Modèle de données (vue d'ensemble)

Entités principales (détail laissé à l'agent `db-architect`) :

`Processus`, `Direction`, `ObjetAuditable` (arbre domaine/opération), `Risque`, `CartographieVersion`,
`Mission` (FSM), `AffectationMission` (utilisateur, rôle dans la mission, déclaration d'indépendance),
`EtapeMission` (18 par mission, statut, dates), `Reunion`, `Entretien`,
`QuestionnaireReponse`, `LigneMARC`, `ReferentielAudit` (FSM), `ObjectifAudit`,
`ProgrammeDeTravail`, `TestPrevu`, `FicheDeTest` (FSM), `PieceJustificative`,
`Constat` (FSM), `Recommandation`, `ActionPlan` (FSM), `Rapport` (FSM), `Diffusion`,
`GabaritDocument`, `DocumentVersion`, `Notification`, entrées `auditlog`.

Règles en base : probabilité et impact dans [1,5] ; score = produit ; unicité du code risque par
version de cartographie ; une seule version « validée » par rapport ; `deleted_at` pour soft delete.

## 8. Workflow de mission (états)

`Mission` : BROUILLON, PLANIFIEE, EN_PLANIFICATION, EN_ACCOMPLISSEMENT, EN_COMMUNICATION, RAPPORT_DIFFUSE, EN_SUIVI, CLOTUREE (plus SUSPENDUE, ANNULEE).

Transitions de phase conditionnées par la validation RAI du jalon de fin de phase.
`EtapeMission` : A_FAIRE, EN_COURS, TERMINEE (puis VALIDEE aux jalons, RENVOYEE si refus).
Objets soumis à validation (`ReferentielAudit`, `FicheDeTest`, `Constat`, `Rapport`) :
BROUILLON, SOUMIS, VALIDE ou RENVOYE. Le valideur ne peut pas être l'auteur.

## 9. Interface

Charte : `docs/design/charte-graphique.md`. Shell : sidebar (Tableau de bord, Missions,
Référentiel, Recommandations, Documents, Administration), header avec recherche globale,
fil d'Ariane, menu utilisateur. Écran mission = en-tête (référence, titre, statut, dates,
équipe) + stepper des étapes + zone de travail de l'étape courante + panneau documents.
Tous les écrans de document ont un rendu print. Responsive 1280/1024/tablette ; mobile en lecture.

## 10. Déploiement

Docker Compose : `web` (Django + gunicorn), `worker` (Celery), `beat`, `frontend` (build
statique servi par Nginx), `db` (PostgreSQL), `redis`, `meilisearch`, `minio`, `gotenberg`,
`keycloak`, `nginx` (reverse proxy TLS). Variables dans `.env`. Script de sauvegarde et
de restauration. CI : lint + tests + build d'images à chaque push.

## 11. Découpage en lots (ordre de construction suggéré)

1. Socle : dépôt, Docker, Django + React vides, auth Keycloak, rôles, modèle de base, piste d'audit, shell UI.
2. Référentiel : processus, directions, objets auditables, cartographie (matrice).
3. Mission et stepper : création, affectations, déclaration d'indépendance, étapes, fiche de suivi, réunions, entretiens.
4. Moteur de documents : gabarits, génération docxtpl, versions, PDF, numérotation ; premiers documents (ordre de mission, PV d'ouverture).
5. Analyse : questionnaires, MARC, forces/faiblesses, référentiel d'audit + validation, objectifs, rapport d'orientation.
6. Programme et accomplissement : programme de travail, fiches de test, pièces, validation des preuves, constats.
7. Communication : plan d'actions, rapport, validation, diffusion.
8. Suivi des recommandations, relances, tableaux de bord, recherche.
9. Durcissement : sécurité, performance, sauvegardes, documentation utilisateur, formation.

## 12. Laissé au constructeur

- Détail des champs de chaque formulaire d'étape (à dériver de `docs/domaine/processus-ifaci.md` et des gabarits ONEA quand ils seront disponibles).
- Schéma physique, index, découpage des apps Django.
- Choix des composants shadcn par écran, maquettes détaillées (agent `ui-designer`).
- Format exact de numérotation des documents (paramétrable).
- Stratégie de seed et de données de démonstration.

## 13. Décisions prises par le rédacteur (à vérifier par le client)

- Le RAI est le seul valideur des jalons ; délégation possible à un superviseur par mission.
- L'audité répond aux constats dans la plateforme (accord/désaccord) avant la réunion de clôture.
- Les relances de recommandations partent par e-mail (SMTP ONEA) ; pas de SMS.
- Les gabarits Word restent la source de vérité du format des documents ; la plateforme ne redessine pas les documents en HTML.
- Keycloak est retenu même si l'ONEA n'a pas d'annuaire : il gère alors les comptes localement.

## 14. Précisions apportées après relecture constructeur (décisions du rédacteur)

**Validations et jalons.** Le RAI valide quatre jalons : VI (référentiel d'audit), X (organisation),
XIII (preuves), XVIII (rapport). Avant la validation RAI de VI et de XIV, les audités donnent
un avis (accord / remarques) sur le référentiel et sur les constats ; cet avis est tracé mais ne
bloque pas. Le passage Accomplissement vers Communication se fait quand le chef de mission
termine l'étape XIV avec au moins un constat validé. Un superviseur délégué peut valider VI, X
et XIII ; XVIII reste au RAI.

**Séquencement du stepper.** Les étapes d'une même phase peuvent être en cours en parallèle ;
le changement de phase est verrouillé par le jalon. Le RAI (ou superviseur) peut rouvrir une
étape terminée ou validée avec un motif obligatoire ; les validations en aval passent alors
à l'état « À revalider » et sont historisées. Les missions de type conseil suivent les mêmes
18 étapes, chaque étape pouvant être marquée « non applicable » par le chef de mission avec motif.

**Constats contestés.** Un désaccord de l'audité ne bloque rien : le constat figure au rapport
avec la réponse de l'audité. Le valideur de la FSM Constat est le RAI (ou superviseur), jamais
l'auteur. Une recommandation peut être sans plan d'actions si le risque est accepté par la
direction concernée, avec justification saisie.

**Confidentialité.** Le périmètre d'un AUDITE est la liste explicite des entités désignées sur
chaque mission ; son rattachement à une direction sert de valeur par défaut. L'audité voit les
constats à partir de leur soumission pour avis. Un AUDITEUR ne voit que les missions où il est
affecté ; le RAI voit tout. Le DG voit les rapports diffusés uniquement. Documents sensibles
journalisés à la consultation : feuilles de travail, fiches de test, pièces justificatives,
rapport avant diffusion.

**Gabarits Word.** IKA SOLUTION pose les balises docxtpl ; le contrat de données de chaque
gabarit est documenté et versionné dans `docs/documents/contrats/`. L'ADMIN peut remplacer un
gabarit uniquement par une version respectant le même contrat (vérification automatique des
balises). Les gabarits `.doc` sont convertis en `.docx` via LibreOffice (Gotenberg). Les lots 4
à 7 démarrent sur des gabarits provisoires fidèles aux noms de documents ; les gabarits officiels
sont substitués à réception sans changement de code.

**Recommandations et actions.** Une recommandation porte une ou plusieurs actions. Statut,
responsable et échéance sont portés par l'action ; le statut de la recommandation est dérivé
(réalisée quand toutes ses actions le sont). Les relances portent sur l'action. Un report
d'échéance est demandé par l'audité et approuvé par le RAI. La mission passe à CLOTUREE sur
décision du RAI, proposée automatiquement quand toutes les actions sont closes.

**Cartographie.** Les risques d'une mission (étape IV) sont choisis dans la version figée de
la cartographie globale ; un risque créé au niveau mission est marqué « nouveau » et proposé
pour la version suivante. La cartographie est tenue par le RAI ; l'ADMIN n'a qu'un rôle technique.

## 15. Réponses du client (27/10/2026)

1. **Signature paramétrable.** L'ADMIN choisit, par type de document (déclaration
   d'indépendance, validation de rapport, ordre de mission), le mode de signature :
   confirmation authentifiée et horodatée dans la plateforme, signature électronique
   (certificat X.509, PDF signé PAdES via pyHanko, open source), ou les deux. Un lot
   « Signature » est ajouté (lot 7 bis) ; le mode « confirmation » est livré dès le lot 3.
2. **Démarrage à vide.** Aucune reprise de l'existant ; pas d'outil d'import en v1.
3. **Infrastructure.** L'ONEA dispose d'un annuaire AD/LDAP (fédéré via Keycloak) et d'un
   serveur SMTP interne (relances e-mail). Aucune échéance contractuelle ; priorité à la
   vitesse de livraison : le plan est découpé pour maximiser le travail en parallèle
   d'agents indépendants, avec un contrat d'API figé en amont de chaque lot.
