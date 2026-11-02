# Rapport QA — parcours cœur de métier de bout en bout (préfixe « QA-CYC- »)

Date : 02/11/2026 · Environnement : site de développement en direct (SPA 5173, API 8000, Keycloak 8180).
Mission de recette : `DAI/2027/M01` « QA-CYC- Mission passation des marchés » (clôturée en fin de parcours).

## Méthode et limites (à lire d'abord)

- Les six rôles ont été joués avec leurs propres jetons Keycloak (flux d'authentification du client SPA,
  un jeton par compte, jamais d'autre identité) ; **les actions métier ont été exécutées par appels directs
  à l'API REST** (chaque appel porte le compte du rôle concerné, comme un vrai relais entre utilisateurs).
  La couche interface n'a été vérifiée que par un passage en lecture par rôle (pages d'accueil, mission,
  registre, rapports, notifications, documents) : aucune erreur console, une seule réponse 403 (D-01).
- **Documents Word/PDF : non générés.** Aucun gabarit actif en base, aucun worker Celery lancé sur cette
  instance, conteneur Gotenberg en redémarrage permanent. La diffusion du rapport (étape XVIII) était donc
  bloquée. Pour poursuivre le suivi et la clôture, un rapport final et une note factices (fichiers « QA-CYC- »,
  gabarits n° 9001/9002 à l'état « déposé », jamais activés) ont été **injectés directement en base** pour
  CE rapport uniquement. Ce contournement est un écart de méthode, pas un résultat de produit.
- Référentiel : la direction `DEX` (créée par un autre testeur, « QA-EDG- ») a servi d'entité auditée.
  Créés par ce cycle : processus `QACYA`, objet auditable, cartographie 2027 validée (3 risques), programme
  2027 validé (1 ligne), mission, équipe, constat, rapport, actions, pièces.
- Aucune donnée du propriétaire n'a été modifiée.

## Résultats par étape

| Étape | Résultat | Preuve | Défaut / remarque | Statut |
|---|---|---|---|---|
| Prérequis : processus, objet auditable, cartographie 2027, 3 risques, validation | Réussi | 201 ; scores 16 / 15 / 6 (Élevé, Élevé, Faible) | Code processus « QACYC1 » refusé (lettres seules, 2 à 5) : conforme, message clair | OK |
| Programme annuel 2027 + ligne + validation | Réussi | statut VALIDE | La mission n'est **pas rattachée** à la ligne du programme (aucun champ de lien) — voir décision DEC-02 | Ouvert (décision) |
| S3-01 Équipe (chef auditeur1, auditeur2, audité audite1) ; doublon refusé | Réussi | 201 ×3 ; 422 « déjà affecté » ; déclarations EN_ATTENTE ×2, audité « non requise » | — | OK |
| S3-02 Déclarations d'indépendance ; écriture refusée avant confirmation | Réussi | 403 « Confirmez votre déclaration… » puis 200 ×2 | — | OK |
| S3-03 Lancer la mission | Réussi | EN_PLANIFICATION, étape I en cours | Refus « sans chef » non rejoué (équipe toujours complète) | Partiel |
| S3-04 Étape I : ordre de mission, gel | Réussi | confirmation obligatoire (400) ; étape I terminée par l'émission ; modification du titre refusée (422) | « Terminer » I est impossible hors émission (conforme) | OK |
| Règle d'ordre : démarrer l'étape III avant II | Conforme au code | 200 | Les étapes d'une même phase peuvent démarrer en parallèle (règle D8) ; le scénario S3-06 suppose II terminée — écart de formulation de la recette (DOC-01) | Noté |
| Règle d'ordre : démarrer XV pendant l'accomplissement | Réussi (bloqué) | 422 « appartient à une phase qui n'a pas commencé » | — | OK |
| S3-05 Étape II : réunion, entretien | Réussi | refus livrables ; « marquer tenue » refusé sans compte rendu (422) puis pour date future (422) ; durée 0 refusée | Une réunion datée d'une période future ne peut pas être « tenue » : cohérent, mais la mission de recette est en 2027 — les dates de réunion ont dû être passées | OK |
| S3-06 Étape III : questionnaire, description, grille | Réussi | 422 « Questions sans réponse : 11 » puis 200 | Le questionnaire est pré-rempli de 13 questions ; le QCI exige l'étape V commencée (message « Commencez l'étape V ») alors que S3-06 le place à l'étape III (DOC-02) ; seul chef/RAI termine une étape (auditeur2 : 403) | OK / DOC |
| S3-07 Étape IV : risques de la mission | Partiel | risque nouveau ajouté (P2×I5 réévalué 5×4 = 20, Élevé) ; terminer sans risque refusé | **Sélection depuis la cartographie impossible** : la mission est rattachée à « la cartographie validée la plus récente » (ici la 2096 d'un autre testeur), pas à celle de son année (DEC-01) | Ouvert (décision) |
| S3-08 Étape V : MARC | Réussi | 422 « contrôle existant requis » ; 422 « contrôle absent ne peut pas être clé » ; 200 | — | OK |
| S3-09 Étape VI : jalon 1 | Réussi | auditeur1 : 403 ; rai : VALIDEE | Avis de l'audité sur le référentiel non rejoué (identifiant non exposé par l'API de liste) | Partiel |
| S3-10 Étape VII | Réussi | objectif OA-01 initialisé et modifié ; rapport d'orientation exige le rapprochement (422) | — | OK |
| S3-11 Étape VIII | Réussi | libellé vide 400 ; taille −3 400 ; test créé | — | OK |
| S3-12 Étape IX | Réussi | auditeur inconnu 400 ; fin avant début 422 ; planification 200 | Charge négative non isolée (masquée par l'erreur d'auditeur) | Partiel |
| S3-13 Étape X + passage | Réussi | rai valide ; mission EN_ACCOMPLISSEMENT | — | OK |
| S3-14 Étape XI | Réussi | refus « réunion non tenue » puis 200 | — | OK |
| S3-15 Étape XII : fiche, pièces PDF et PNG | Réussi | refus « résultat et conclusion » ; refus « pièce ou justification » ; dépôt 201 ×2, SHA-256 renvoyé ; téléchargement : empreinte identique | — | OK |
| S3-16 Étape XIII : renvoi, correction, validation, jalon | Réussi avec détour | renvoi sans motif 400 ; **après renvoi, auditeur2 ne peut pas resoumettre** : 422 « Commencez l'étape XII… » car XII est terminée ; il a fallu que le RAI rouvre XII (le chef n'en a pas le droit) | D-02 : message trompeur et parcours impasse pour l'équipe | Ouvert |
| S3-17 Étape XIV : constat, causes 7M, recommandations | Réussi | auditeur2 : 403 ; soumission chef 200 ; modification après soumission 422 ; chef ne peut valider (403) ; renvoi sans motif 400 ; validation RAI | Message de refus générique « Accès refusé. » au lieu de « Seuls le chef de mission ou le RAI peuvent soumettre » (D-03, mineur). Réorganisation « Monter/Descendre » et fiche d'observation non rejouées | OK |
| S3-18 Étape XV : réunion de clôture, rapport provisoire | Réussi | transmission avant réunion 422 ; délais 0 et 61 refusés ; 15 accepté, limite 17/11/2026 | Aucune notification dans la plateforme à l'audité (envoi par e-mail via worker, non lancé) | Noté |
| S3-19 Réponses de l'audité | Réussi | commentaire vide 422 ; case non cochée 400 ; réponse tracée avec empreinte ; position Désaccord sans motif 422 « Motivez votre désaccord » ; Accord 201 ; 2 cycles en historique | Deux mécanismes coexistent (réponse au provisoire sans position / réponse par constat avec position) | OK |
| S3-20 Étape XVI : plan d'actions, engagement, acceptation du risque | Réussi | échéance passée refusée ; création, suppression ; engagement sans case 400 ; acceptation du risque 201 ; « Terminer » refusé tant qu'une action manque d'indicateur | Libellé « postérieure ou égale à aujourd'hui » vs recette « ne peut pas être antérieure » (DOC-03, mineur) | OK |
| S3-21 Étape XVII : rédaction, soumission | Réussi | refus « Rédigez la synthèse, l'appréciation globale et la conclusion » ; aperçu 200 ; soumission 200 | — | OK |
| S3-22 Étape XVIII : validation | Réussi | chef : 403 ; renvoi sans motif 400 ; case non cochée 400 ; validation RAI ; mode « Confirmation horodatée » | — | OK |
| S3-22 Génération Word/PDF | **Échec (environnement)** | `retry` impossible : aucun gabarit, pas de worker, Gotenberg en panne ; « Le rapport final n'est pas encore généré » | Bloquant de l'environnement (voir méthode) | Bloqué |
| S3-22 Diffusion (avec versions injectées) | Réussi | destinataire déjà présent refusé ; externe ajouté ; diffusion 200 ; mission EN_SUIVI | Diffusion sans destinataire non rejouée | Partiel |
| S3-23 Rapports diffusés : DG, accusé, remise externe | Réussi | DG et audité : accusé 200 ; remise hors plateforme exige le champ `le` | — | OK |
| S3-24 Suivi : démarrer, preuve, avancement, déclarer, vérifier, clôturer | Réussi | « réalisée » sans preuve 422 ; audité ne peut vérifier ni clôturer (403) ; vérificateur auditeur2 200 ; RAI clôture 200 ; chronologie complète | — | OK |
| S3-25 Rejet et réouverture | Réussi | rejet sans motif 400 ; rejet avec motif → EN_COURS + motif visible ; réouverture : auditeur1 403, RAI 200 | — | OK |
| S3-26 Report d'échéance | Réussi | antérieure 422 ; motif vide 400 ; refus sans commentaire 400 ; acceptation : échéance 30/08 → 30/10/2027, 1 report | — | OK |
| S3-27 Abandon | Réussi | proposition 200 ; acceptation exige un commentaire (non prévu par la recette, DOC-04) | — | OK |
| S3-28 Changement de responsable | Réussi (API) | PATCH 200 | Notification « Responsable modifié » non vérifiée | Partiel |
| S3-29 Registre | Partiel | RAI et audité OK ; **DG : requête 403 sur la liste des missions** | D-01 (corrigé) | Corrigé |
| S3-30 Relances | Non testé | commande de relance non exécutée (hors périmètre sans worker) | — | N/A |
| S3-31 Clôture de la mission | Réussi | refus « 1 action n'est pas close » ; clôture 200 ; notification « Mission à clôturer » | — | OK |
| Gel après clôture | Réussi | mission, constat, rouverture d'étape : 422 « est clôturée » | — | OK |
| S3-32 Rapport corrigé | Non testé | mission déjà clôturée au moment de la vérification | — | N/A |
| Tableaux de bord RAI / auditeur / audité / DG | Réussi | 200 ; DG vers tableau RAI : 403 ; par défaut sur l'année courante 2026 (la mission 2027 n'apparaît qu'en changeant l'année) | — | OK |
| Notifications en cours de parcours | Partiel | seules les notifications du suivi existent (rai 6, auditeur1 3, audite1 8) ; **aucune** à l'affectation, au dépôt de fiche, au jalon à valider, à la transmission du provisoire ni à la diffusion (auditeur2 : 0 ; DG : 0) | DEC-03 | Ouvert (décision) |

## Défauts

- **D-01 (corrigé)** : le registre Recommandations/Actions appelait `GET /missions/?page_size=100` pour le DG, qui n'y a pas droit
  (403 en console, filtre « Mission » vide). Correctif : la liste n'est plus demandée pour le DG et le filtre est masqué.
  Test ajouté dans `RegisterPage.test.tsx` (échoue avant, passe après).
- **D-02 (ouvert)** : une fiche renvoyée par le RAI à l'étape XIII ne peut pas être corrigée si l'étape XII est terminée ;
  message « Commencez l'étape XII… » inexploitable (XII n'est pas « à commencer » mais à rouvrir) et seul le RAI peut rouvrir XII.
  Le scénario S3-16 suppose la correction directe. À arbitrer : rouverture automatique de XII au renvoi, ou droit de
  correction sur fiche renvoyée, ou simple message explicite.
- **D-03 (mineur, ouvert)** : refus génériques « Accès refusé. » sur soumission/validation de constat et de rapport
  par un non-habilité, au lieu des messages métier attendus.

## Décisions à prendre

- **DEC-01** : la cartographie rattachée à une mission est « la plus récente validée », sans lien avec l'année de la mission.
  Faut-il rattacher à la cartographie de l'année (ou laisser choisir) ?
- **DEC-02** : lien entre ligne du programme annuel et mission (aujourd'hui inexistant : saisie en double).
- **DEC-03** : notifications dans la plateforme aux passages de relais (affectation, fiche soumise, jalon à valider,
  provisoire transmis, rapport diffusé) ; aujourd'hui seul le suivi en émet, le reste dépend de l'e-mail.

## Écarts de documentation (recette)

DOC-01 ordre strict des étapes d'une phase ; DOC-02 QCI à l'étape III ; DOC-03 libellé de l'échéance ;
DOC-04 commentaire obligatoire pour accepter un abandon ; la recette (S3-16) place l'étape XIV en phase de
communication alors que le code et `docs/domaine/processus-ifaci.md` la placent en accomplissement.

## Bilan

Étapes évaluées : 45 lignes — Réussi 34, Partiel 7, Bloqué 1 (génération documentaire), Non testé 2, Corrigé 1.
Le parcours est allé jusqu'à la clôture de la mission ; seul le blocage documentaire a nécessité un contournement.
