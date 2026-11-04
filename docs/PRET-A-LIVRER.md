# Prêt à livrer — liste de contrôle go / no-go (T36 « vérification finale »)

Établie le 2026-11-03 d'après le dépôt (branche `develop`) ; mise à jour le 2026-11-04 pour le remplacement de
Keycloak par l'authentification interne (branche `feat/auth-interne`, non fusionnée), puis le même jour pour la
revue de sécurité de l'authentification et le rejeu de l'audit ASVS (B1, B8). Légende du statut :
**OK** = preuve lue dans le dépôt (le fichier cité) ; **à vérifier** = non exécuté ni constaté par l'auteur de
cette liste, à rejouer ; **à faire** = travail restant de l'équipe ; **bloqué par ONEA** = dépend d'une
décision ou d'une information de l'ONEA (voir `docs/HANDOFF.md` §5). Aucune commande n'a été exécutée pour
dresser cette liste : « OK » ne signifie donc jamais « testé aujourd'hui ».

Règle de décision : **go** si tous les critères A à D sont OK ; les critères E sont des décisions ONEA qui
bloquent la mise en production (pas la livraison du logiciel), chacune avec son comportement par défaut.

## A. Qualité du code (sur un clone propre)

| # | Critère | Comment vérifier | Statut |
|---|---|---|---|
| A1 | Lint et typage back et front | `make lint` | à vérifier |
| A2 | Tests back et front (une seule exécution complète) | `make test` (backend : `pytest`, couverture ≥ 80 % en CI). Sur `feat/auth-interne` les tests du backend ont été lancés **application par application** (disque insuffisant pour une exécution complète unique) et ceux du frontend ciblés ; aucune exécution complète unique n'a eu lieu | à vérifier |
| A3 | Schéma d'API à jour | `sh scripts/check-api-fresh.sh` (ou `make check-api`) | à vérifier |
| A4 | Tests e2e | `sh scripts/e2e.sh` (Playwright, base jetable, comptes créés par `creer_comptes_e2e`) ; couvrent aujourd'hui connexion par formulaire, référentiel, missions, accessibilité, clavier, impression. Les specs ont été vérifiées par `tsc` mais **n'ont pas été exécutées** depuis le remplacement de Keycloak | à vérifier |
| A5 | e2e des lots 6 (T14), 7 (T17), 8 (T17) | aucune spec dans `frontend/e2e/` pour accomplissement, communication, suivi | à faire |
| A6 | Accessibilité stricte sur toutes les zones | `A11Y_STRICT=1` avec `scripts/e2e.sh` ; rapport `docs/qualite/audit-accessibilite.md` | à vérifier |
| A7 | Budget frontend | `cd frontend && npm run build && npm run budget` (`scripts/verifier-budget-frontend.mjs`) | à vérifier |
| A8 | Version `0.9.0` posée (backend `__init__.py` et `pyproject.toml`, `package.json`, `package-lock.json`, libellé « Version 0.9 » de `fr.ts`) | lecture des fichiers : encore `0.6.0` | à faire |
| A9 | Intégration continue verte (GitHub Actions `.github/workflows/ci.yml`, compatibilité Gitea `scripts/ci/gitea-local.sh`) | exécution du pipeline | à vérifier |

## B. Sécurité et dépendances

| # | Critère | Comment vérifier | Statut |
|---|---|---|---|
| B1 | Revue ASVS niveau 2 : aucun constat critique, élevé ou moyen ouvert | `docs/securite/asvs-l2.md`, **rejouée le 2026-11-04 sur l'authentification interne** (revue statique, commit `ccd12f8`) : V2, V3, V4 et V7 exigence par exigence, lignes touchées de V8, V9, V13, V14. Décompte (Conforme / Partiel / Non conforme / Non applicable) : V2 21/9/7/15, V3 13/2/1/2, V4 6/2/1/0, V7 7/5/0/0. Aucun constat critique, élevé ou moyen ouvert (SEC-01 corrigé, SEC-02 résolu, SEC-04 résolu, SEC-03/05/06 sans objet depuis le retrait de Keycloak, AUTH-01 à AUTH-06 corrigés). Non-conformités L2 restantes, toutes faibles ou fonctionnelles : indicateur de robustesse et affichage du mot de passe (2.1.8, 2.1.12), notifications au titulaire (2.2.3, 2.5.5 = AUTH-10), WebAuthn (2.3.2), poivre (2.4.5), mot de passe temporaire envoyé en clair par courriel (2.5.1), liste des sessions (3.3.4), second facteur obligatoire des administrateurs (4.3.1, décision ONEA). **Analyse dynamique (ZAP) non rejouée** depuis Keycloak | OK (statique) ; à vérifier (dynamique, B6) |
| B8 | Revue de sécurité de l'authentification interne, constats critiques et élevés corrigés | Revue statique faite le 2026-11-04 (constats AUTH-01 à AUTH-20 : 0 critique, 3 élevés, 3 moyens, 7 faibles, 7 informations ; synthèse et statut de chaque constat dans `docs/securite/asvs-l2.md` §2.2). Corrections appliquées (commits `39163e0`, `f77d1ff`, `f713854`, `91222a0`, `ccd12f8`) et **relues** ; second tour de re-revue (constats N1 à N9) corrigé dans le commit `7f6b9dc` (plafonds par adresse limités aux mauvais secrets, file Celery `auth` et service `worker-auth`, ligne `ERROR` « Mot de passe temporaire perdu » à surveiller, plafond `AUTH_CODES_CONNEXION_MAX`, variables transmises et validées, migration `users.0011`), relu statiquement ; tests du développeur lancés sur une sélection (pas de suite complète). Les 3 élevés et les 3 moyens sont corrigés. Suites du frontend dans le commit `8addfca` (rôles proposés à un délégué, en-tête d'arrière-plan AUTH-08, libellés « mis en file d'envoi », message 429). Restent ouverts : AUTH-09 (délai d'inactivité des sessions admin), AUTH-11 (unicité insensible à la casse en base), AUTH-10 et AUTH-13 (arbitrages), AUTH-18 (TLS vers le relais non exigé), les constats d'information ; `AUTH_REINITIALISATION_ECHECS_MAX` et `AUTH_CODES_CONNEXION_MAX` sont désormais transmis par `docker/compose.prod.yml`. **Comportement non vérifié sur une pile en fonctionnement** (envoi par `worker-auth` et repli du `worker`, démarrage du nouveau service, 429 derrière le NAT, navigateur) ; scénarios S4-29 à S4-41 de `docs/recette/scenarios-de-test.md` non joués ; modèle : `docs/securite/auth-interne-modele.md` | OK (revue faite, élevés et moyens corrigés) ; à vérifier (pile réelle, scénarios) |
| B2 | Licences : aucune hors liste, SBOM produit | `bash scripts/audit-dependances.sh` ; rapport daté du 2026-10-30 dans `docs/securite/licences.md` (0 bloquant) à rejouer, la liste ayant évolué le 2026-11-02 | à vérifier |
| B3 | Vulnérabilités connues | même script (pip-audit, npm audit) ; 0 au 2026-10-30 | à vérifier |
| B4 | Images et dépendances épinglées | `sh scripts/verifier-epinglage.sh` | à vérifier |
| B5 | Aucun secret dans le dépôt | `gitleaks detect` (configuration `.gitleaks.toml`) | à vérifier |
| B6 | Scan dynamique | `sh scripts/recette/zap.sh` sur la pile de recette | à vérifier |
| B7 | Aucune fonction IA dans le produit | `grep -riE "openai|anthropic|llm|embedding" backend/apps frontend/src` doit ne rien trouver d'applicatif | à vérifier |

## C. Recette, exploitation et performance

| # | Critère | Comment vérifier | Statut |
|---|---|---|---|
| C1 | Configuration de production valide | `make prod-config` | à vérifier |
| C2 | Recette depuis zéro selon `docs/deploy.md` et `docs/exploitation/mise-en-production.md` | `sh scripts/recette/up.sh`, puis `creer_administrateur` et création des comptes (`docs/recette.md`) ; checklist rejouée par un tiers (statut « non consigné » dans la checklist) | à vérifier |
| C3 | Bancs de la recette : périphérie, réseaux, TLS, journaux, secrets, restauration | `sh scripts/recette/tests/{edge,reseaux,tls,journaux,secrets,restauration}.sh` | à vérifier |
| C4 | Restauration en moins de 30 minutes, documents identiques à l'octet | `sh scripts/recette/tests/restauration.sh` | à vérifier |
| C5 | Test de charge : 40 utilisateurs simultanés dans les budgets | `sh scripts/recette/charge.sh` ; résultats locaux du 2026-11-02 dans `docs/qualite/charge/2026-11-02-local/` (le fichier d'échecs y contient des 401, 403 et 429 à interpréter) | à vérifier |
| C6 | Budgets de requêtes de l'API | `cd backend && python -m pytest tests/performance --create-db` | à vérifier |
| C7 | Journaux sans données personnelles | `sh scripts/recette/tests/journaux.sh` ; test `test_aucune_donnee_personnelle_dans_les_journaux` | à vérifier |
| C8 | Runbook et checklist de mise en production présents | `docs/exploitation/runbook.md`, `docs/exploitation/mise-en-production.md` | OK (présents ; non rejoués) |

## D. Documentation et formation

| # | Critère | Comment vérifier | Statut |
|---|---|---|---|
| D1 | Un manuel par rôle en français | `docs/manuels/` (administrateur, RAI, auditeur, audité, DG, glossaire) | OK (présents) |
| D2 | Manuels rejoués sur l'application (10 procédures par manuel), rubrique « À confirmer » levée | relecture sur la recette « formation » | à faire |
| D3 | Manuels accessibles depuis l'application (menu « Aide »), PDF et captures | `docs/manuels/README.md` : non réalisé (tâche T30) | à faire |
| D4 | Kit de formation présent | `docs/formation/` | OK (présent) |
| D5 | Kit de formation rejoué sur un environnement neuf, réinitialisation < 15 min | `sh scripts/recette/down.sh` puis `up.sh`, création des comptes (`docs/formation/guide-formateur.md` §1.1), `peupler_demo --profil formation --recette` ; suivre les fiches | à faire |
| D6 | Document de passage `docs/exploitation/passage-0.9.0.md` (résultats, constats acceptés, conditions de la 1.0.0) | fichier absent | à faire |
| D7 | Revue visuelle de tous les écrans et corrections d'interface (T22, T24, T25) | rapports de QA design dans `docs/recette/` partiels | à faire |

## E. Décisions de l'ONEA (bloquent la mise en production)

| # | Décision | Statut |
|---|---|---|
| E1 | Destination de la copie hors serveur des sauvegardes et détenteurs du mot de passe restic (U1) | bloqué par ONEA |
| E2 | Hébergement, nom DNS (un seul : plus de nom pour un serveur d'identité), source du certificat TLS (U2) | bloqué par ONEA |
| E3 | SMTP (U3) : sans `EMAIL_URL`, la production refuse de démarrer ; il porte aussi les codes de connexion, le « mot de passe oublié » et le courriel de bienvenue, tous envoyés par le `worker` (repli sans courriel : `EMAIL_URL=dummymail://` et réinitialisation par un administrateur, `docs/deploy.md` §2.3 et §5.5) | bloqué par ONEA |
| E4 | Réseau : proxy amont, réseau d'administration, supervision (U5) | bloqué par ONEA |
| E5 | 22 gabarits Word réels (provisoires acceptés pour la livraison, pas pour l'usage final) | bloqué par ONEA |
| E6 | Abréviations QPC, GST, QCI, MARC, FF, RO, PT, FCT, FDT, FIT, FO ; rôles pour lesquels le code de connexion par courriel deviendrait obligatoire (D19, aujourd'hui facultatif) ; libellé de la direction des participants sur l'ordre de mission | bloqué par ONEA |
| E7 | Formation (U6) : participants, dates, salle, postes | bloqué par ONEA |
| E8 | ClamAV : accepté (6c982ec) ; reste l'accès sortant vers les signatures ou un miroir local | bloqué par ONEA |

## Synthèse au 2026-11-04
Logiciel : fonctionnellement intégré dans `develop` jusqu'au lot 8 et au lot 9 (T1 à T21, T23, T26 à T29, T31) ; **no-go
aujourd'hui** pour la livraison finale, faute des critères A5, A8, D2, D3, D5, D6, D7 (travail restant) et des
vérifications « à vérifier » non rejouées. Mise en production : en plus, E1 à E4 à lever par l'ONEA.

Authentification interne (`feat/auth-interne`, non fusionnée dans `develop`) : le remplacement de Keycloak est
écrit, documenté (`docs/deploy.md` §5, runbook, manuels, scénarios) et ses tests ont été lancés par application ;
la revue de sécurité statique (B8) est faite et ses constats élevés et moyens sont corrigés (corrections relues,
non éprouvées sur une pile réelle) ; l'audit ASVS L2 est rejoué en statique (B1). **Ne sont pas faits** : suite
complète en une exécution, specs Playwright (typage vérifié, exécution non faite), parcours manuel sur le site de
test (scénarios S4-29 à S4-41), analyse dynamique, et les constats ouverts listés en B8. Ce qui reste à
fournir par l'ONEA pour l'authentification : le relais SMTP (E3), le certificat TLS réel, le nom DNS et
l'hébergement (E2), la copie hors serveur des sauvegardes (E1), et, hors authentification, les 22 gabarits Word
réels (E5). Verdict inchangé tant que ces points ne sont pas levés : on ne peut pas dire « prêt à livrer ».
