# Captures d'écran à prendre pour les manuels

72 captures sont référencées dans les manuels par un repère « [Capture à insérer : CAP-xxx — titre] ».
Ce document donne, pour chacune, la route, le compte et l'état des données à préparer.

## Préparation commune

- **Jeu de données** : base de recette dédiée (jamais la base de développement `onea`), peuplée par
  `python manage.py peupler_demo --profil volumetrie --echelle 0.2` (comptes `admin`, `rai`, `auditeur1`,
  `auditeur2`, `audite1`, `dg` ; la commande affiche une seule fois leur mot de passe temporaire, à changer à la première connexion). Ce peuplement s'arrête à l'étape VIII :
  les écrans des étapes IX à XVIII, constats, rapports, recommandations et suivi exigent de rejouer les scénarios
  S3-01 à S3-31 de `docs/recette/scenarios-de-test.md` pour constituer la « mission de recette ».
- **Direction de `audite1`** : à fixer sur l'entité auditée de la mission de recette (scénario S2-12).
- **Services** : worker de tâches de fond et service de conversion PDF pour les captures de documents et de diffusion
  service de recherche pour CAP-RAI-… (recherche non capturée).
- **Format** : navigateur Chrome ou Edge, fenêtre de 1440 × 900, zoom 100 %, thème par défaut, PNG. Aucune
  adresse électronique réelle (utiliser `@example.org`). Masquer les identifiants et mots de passe temporaires réels.
- **Nom de fichier proposé** : `images/<repère en minuscules>.png` (exemple `images/cap-rai-01.png`).
- **Horloge** : prendre les captures à une date unique pour que les échéances (« en retard », « Il vous reste N jours »)
  soient cohérentes.
- **Mission de recette** : désigne ci-après la mission jouée en S3-xx, `auditeur1` chef de mission, `auditeur2` auditeur,
  `audite1` audité. Abréviation `<M>` pour son identifiant dans l'adresse.
- La mention « (état X) » renvoie aux états de données décrits en fin de document.

## Captures communes

| Repère | Écran | Route | Compte | État des données |
|---|---|---|---|---|
| CAP-COM-01 | Page de connexion « Audit interne ONEA », bouton « Se connecter » | `/connexion` | aucun (déconnecté) | aucune |
| CAP-COM-02 | Menu utilisateur ouvert (nom, adresse, rôle, « Mon compte », « Changer mon mot de passe », « Se déconnecter ») | n'importe quelle page, ex. `/` | `rai` | aucune |

## RAI (25)

| Repère | Écran | Route | Compte | État des données |
|---|---|---|---|---|
| CAP-RAI-01 | Tableau de bord du RAI | `/` | `rai` | état B (missions à plusieurs statuts, jalon à valider) |
| CAP-RAI-02 | Barre latérale et en-tête (cloche, recherche) | `/` | `rai` | état B, au moins 2 notifications non lues |
| CAP-RAI-03 | Référentiel, onglet « Processus » | `/referentiel` (onglet « Processus ») | `rai` | processus et directions présents |
| CAP-RAI-04 | Dialogue « Ajouter un risque » avec aperçu « Score 15 » | `/referentiel` (onglet « Cartographies », cartographie brouillon) | `rai` | cartographie en brouillon ; saisir probabilité 3, impact 5 |
| CAP-RAI-05 | Dialogue « Valider la cartographie » (avertissement) | idem, cartographie brouillon avec risques | `rai` | brouillon avec au moins un risque |
| CAP-RAI-06 | Programme annuel, vue « Calendrier » | `/programme-annuel` | `rai` | programme brouillon avec lignes sur plusieurs trimestres |
| CAP-RAI-07 | Formulaire « Ajouter une mission prévue » | `/programme-annuel/nouvelle-ligne` | `rai` | programme brouillon |
| CAP-RAI-08 | Formulaire « Créer une mission » | `/missions/nouvelle` | `rai` | cartographie validée |
| CAP-RAI-09 | Menu « Actions sur la mission » ouvert | `/missions/<M>` | `rai` | mission au statut Brouillon ou Planifiée |
| CAP-RAI-10 | Onglet « Équipe » et dialogue « Affecter une personne » | `/missions/<M>/equipe` | `rai` | mission planifiée |
| CAP-RAI-11 | Étape I : dialogue « Émettre l'ordre de mission » | `/missions/<M>/etapes/1` | `rai` | mission lancée, objectifs et périmètre renseignés |
| CAP-RAI-12 | Étape VI : « Valider le jalon » | `/missions/<M>/etapes/6` | `rai` | étape VI terminée par l'équipe |
| CAP-RAI-13 | Fiche de test soumise avec boutons « Valider la fiche » / « Renvoyer » | `/missions/<M>/fiches/<fiche>` | `rai` | fiche soumise (conclusion Anomalie, une pièce) par `auditeur2` |
| CAP-RAI-14 | Constat soumis avec « Valider » / « Renvoyer » | `/missions/<M>/constats/<constat>` | `rai` | constat soumis par `auditeur1` |
| CAP-RAI-15 | Étape XV : « Transmettre le rapport provisoire » | `/missions/<M>/etapes/15` | `rai` | réunion de clôture tenue, constat validé |
| CAP-RAI-16 | Tableau « Réponses des audités » | `/missions/<M>/reponses-rapport` | `rai` | rapport provisoire transmis, une réponse reçue |
| CAP-RAI-17 | Étape XVIII : validation du rapport et liste de diffusion | `/missions/<M>/rapport` | `rai` | rapport soumis par `auditeur1` ; destinataires saisis |
| CAP-RAI-18 | Suivi de la diffusion (Notifié le, Consulté le, Accusé le) | `/rapports/<rapport>` | `rai` | rapport diffusé, un accusé reçu |
| CAP-RAI-19 | Registre des recommandations et actions | `/recommandations` | `rai` | plusieurs actions à statuts variés dont une en retard |
| CAP-RAI-20 | Page d'une action (boutons Clôturer, Rouvrir, report, abandon) | `/recommandations/actions/<action>` | `rai` | action « Vérifiée » avec une demande de report |
| CAP-RAI-21 | Suivi des recommandations de la mission, bouton « Clôturer la mission » | `/missions/<M>/suivi-recommandations` | `rai` | toutes actions closes |
| CAP-RAI-22 | Registre des documents | `/documents` | `rai` | au moins 3 documents générés |
| CAP-RAI-23 | Gabarits de documents en lecture seule | `/administration/documents` | `rai` | gabarits provisoires chargés |
| CAP-RAI-24 | Mode de signature en lecture seule | `/administration/signatures` | `rai` | aucune |
| CAP-RAI-25 | Tableau de bord, bloc « File de décisions » (zoom) | `/` | `rai` | état B ; au moins une entrée par catégorie si possible |

## Administrateur (11)

| Repère | Écran | Route | Compte | État des données |
|---|---|---|---|---|
| CAP-ADM-01 | Écran d'accueil « Administration de la plateforme » | `/` | `admin` | aucune |
| CAP-ADM-02 | Barre latérale de l'administrateur | `/` | `admin` | aucune |
| CAP-ADM-03 | Liste des utilisateurs avec filtres | `/administration/utilisateurs` | `admin` | six comptes ou plus, dont un désactivé |
| CAP-ADM-04 | Fiche utilisateur : profil et « Historique du compte » | `/administration/utilisateurs` (fiche de `audite1`) | `admin` | au moins une modification de profil enregistrée |
| CAP-ADM-05 | Dialogue « Désactiver le compte » avec motif | fiche d'un compte de test | `admin` | compte de test actif (pas `admin`) |
| CAP-ADM-06 | Import CSV : rapport de vérification | `/administration/utilisateurs` (bouton « Importer un fichier CSV ») | `admin` | fichier CSV fictif de 5 lignes dont une ignorée (`role=ADMIN`) |
| CAP-ADM-07 | Liste des types de documents et gabarits | `/administration/documents` | `admin` | gabarits provisoires, bannière visible |
| CAP-ADM-08 | Dépôt et activation d'une version de gabarit | `/administration/documents` (un type ouvert) | `admin` | fichier `.docx` valide de test |
| CAP-ADM-09 | Onglet « Numérotation » | `/administration/documents` (onglet « Numérotation ») | `admin` | aucune |
| CAP-ADM-10 | Mode de signature | `/administration/signatures` | `admin` | aucune |
| CAP-ADM-11 | Référentiel, onglet « Directions » en écriture | `/referentiel` (onglet « Directions ») | `admin` | directions présentes |

## Auditeur et chef de mission (15)

| Repère | Écran | Route | Compte | État des données |
|---|---|---|---|---|
| CAP-AUD-01 | Tableau de bord de l'auditeur | `/` | `auditeur2` | mission en cours, tests à documenter |
| CAP-AUD-02 | Liste des missions de l'auditeur | `/missions` | `auditeur2` | deux missions dont une avec « Déclaration à confirmer » |
| CAP-AUD-03 | Bandeau et dialogue « Confirmer ma déclaration » | `/missions/<M>` | `auditeur2` | déclaration d'indépendance « En attente » |
| CAP-AUD-04 | Étape II : réunion d'ouverture planifiée | `/missions/<M>/reunions` | `auditeur1` | étape II commencée |
| CAP-AUD-05 | Planning des entretiens | `/missions/<M>/entretiens` | `auditeur1` | deux entretiens planifiés |
| CAP-AUD-06 | Étape III : grille de séparation des tâches avec alerte | `/missions/<M>/etapes/3` | `auditeur2` | 2 tâches, 2 acteurs, un cumul incompatible |
| CAP-AUD-07 | Étape IV : matrice des risques de la mission | `/missions/<M>/etapes/4` | `auditeur2` | plusieurs risques sélectionnés |
| CAP-AUD-08 | Étape V : matrice des risques et contrôles (MARC) | `/missions/<M>/referentiel-audit` | `auditeur2` | MARC initialisée, un contrôle clé |
| CAP-AUD-09 | Étape VII : objectifs d'audit | `/missions/<M>/etapes/7` | `auditeur2` | jalon VI validé |
| CAP-AUD-10 | Étape IX : planification des tests et synthèse du budget | `/missions/<M>/etapes/9` | `auditeur1` | tests planifiés |
| CAP-AUD-11 | Fiche de test avec pièce justificative (empreinte SHA-256) | `/missions/<M>/fiches/<fiche>` | `auditeur2` | une pièce PDF déposée |
| CAP-AUD-12 | Constat avec causes 7M et recommandations | `/missions/<M>/constats/<constat>` | `auditeur1` | constat en brouillon avec 2 causes et 2 recommandations |
| CAP-AUD-13 | Rapport en rédaction avec appréciation globale | `/missions/<M>/rapport` | `auditeur1` | étape XVII commencée |
| CAP-AUD-14 | Page d'une action « Réalisée, à vérifier » (Vérifier / Rejeter) | `/recommandations/actions/<action>` | `auditeur2` | action déclarée par `audite1` avec une preuve |
| CAP-AUD-15 | Fiche de suivi de la mission | `/missions/<M>/suivi` | `auditeur1` | mission avancée à l'étape XIV au moins |

## Audité (11)

| Repère | Écran | Route | Compte | État des données |
|---|---|---|---|---|
| CAP-AU-01 | Tableau de bord de l'audité | `/` | `audite1` | un constat à répondre, deux actions dont une en retard |
| CAP-AU-02 | Barre latérale de l'audité | `/` | `audite1` | aucune |
| CAP-AU-03 | Cloche ouverte et page des notifications | `/` puis `/notifications` | `audite1` | au moins 3 notifications dont 2 non lues |
| CAP-AU-04 | Liste des missions de l'audité | `/missions` | `audite1` | ordre de mission émis, direction renseignée |
| CAP-AU-05 | Référentiel d'audit avec « Donner mon avis » | `/missions/<M>/referentiel-audit` | `audite1` | référentiel diffusé |
| CAP-AU-06 | Constats de mon entité et bouton « Répondre » | `/missions/<M>/reponses-rapport` | `audite1` | rapport provisoire transmis, délai ouvert |
| CAP-AU-07 | Dialogue de confirmation de la réponse (case « Je confirme ») | idem | `audite1` | réponse « Désaccord » saisie, avant envoi |
| CAP-AU-08 | Plan d'actions : « Ajouter une action » | `/missions/<M>/plan-actions` | `audite1` | étape XVI ouverte, une recommandation |
| CAP-AU-09 | Acceptation du risque | `/missions/<M>/plan-actions` | `audite1` | recommandation sans action |
| CAP-AU-10 | Page d'une action : Démarrer, preuve, Déclarer réalisée | `/recommandations/actions/<action>` | `audite1` | action « En cours » avec une preuve |
| CAP-AU-11 | Rapport diffusé avec « Accuser réception » | `/rapports/<rapport>` | `audite1` | rapport diffusé, `audite1` destinataire interne |

## Direction générale (8)

| Repère | Écran | Route | Compte | État des données |
|---|---|---|---|---|
| CAP-DG-01 | Tableau de bord « Synthèse de l'audit interne » | `/` | `dg` | rapports diffusés et actions à statuts variés |
| CAP-DG-02 | Barre latérale de la DG | `/` | `dg` | aucune |
| CAP-DG-03 | Bouton « Exporter les taux (Excel) » (zoom) | `/` | `dg` | idem CAP-DG-01 |
| CAP-DG-04 | Liste des rapports diffusés avec filtre « Année de diffusion » | `/rapports` | `dg` | au moins 2 rapports diffusés |
| CAP-DG-05 | Détail d'un rapport diffusé (synthèse, appréciation, téléchargements) | `/rapports/<rapport>` | `dg` | rapport diffusé et généré en PDF |
| CAP-DG-06 | Registre des recommandations en lecture (sans bouton d'action) | `/recommandations` | `dg` | plusieurs actions |
| CAP-DG-07 | Programme annuel en lecture | `/programme-annuel` | `dg` | programme validé |
| CAP-DG-08 | Cartographie des risques en lecture (matrice 5 × 5) | `/referentiel` (onglet « Cartographies ») | `dg` | cartographie validée |

## États de données

- **État B** : base de recette peuplée (volumétrie, échelle 0,2) enrichie de la mission de recette jouée au moins jusqu'à
  l'étape VI, avec un jalon « à valider » et des notifications non lues.
- **Mission de recette complète** : S3-01 à S3-31 rejoués, pour les écrans des étapes XIV à XVIII et du suivi.

## À vérifier au moment des captures

- Les routes `/administration/utilisateurs`, `/administration/documents`, `/administration/signatures` sont certaines ; les
  adresses des onglets et des dialogues sont indiquées par leur libellé car l'adresse exacte n'a pas été relevée.
- L'adresse exacte de l'écran de résultats de recherche est `/recherche` ; le paramètre de requête reste à relever.
- Si un écran affiche encore « lot 3 », « lot 4 » ou « Disponible dans un prochain lot » (point V-11), ne pas le capturer : corriger d'abord.
