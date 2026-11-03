# Prêt à livrer — liste de contrôle go / no-go (T36 « vérification finale »)

Établie le 2026-11-03 d'après le dépôt (branche `develop`). Légende du statut :
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
| A2 | Tests back et front (une seule exécution complète) | `make test` (backend : `pytest`, couverture ≥ 80 % en CI) | à vérifier |
| A3 | Schéma d'API à jour | `sh scripts/check-api-fresh.sh` (ou `make check-api`) | à vérifier |
| A4 | Tests e2e | `sh scripts/e2e.sh` (Playwright, base jetable) ; couvrent aujourd'hui connexion, référentiel, missions, accessibilité, clavier, impression | à vérifier |
| A5 | e2e des lots 6 (T14), 7 (T17), 8 (T17) | aucune spec dans `frontend/e2e/` pour accomplissement, communication, suivi | à faire |
| A6 | Accessibilité stricte sur toutes les zones | `A11Y_STRICT=1` avec `scripts/e2e.sh` ; rapport `docs/qualite/audit-accessibilite.md` | à vérifier |
| A7 | Budget frontend | `cd frontend && npm run build && npm run budget` (`scripts/verifier-budget-frontend.mjs`) | à vérifier |
| A8 | Version `0.9.0` posée (backend `__init__.py` et `pyproject.toml`, `package.json`, `package-lock.json`, libellé « Version 0.9 » de `fr.ts`) | lecture des fichiers : encore `0.6.0` | à faire |
| A9 | Intégration continue verte (GitHub Actions `.github/workflows/ci.yml`, compatibilité Gitea `scripts/ci/gitea-local.sh`) | exécution du pipeline | à vérifier |

## B. Sécurité et dépendances

| # | Critère | Comment vérifier | Statut |
|---|---|---|---|
| B1 | Revue ASVS niveau 2 : aucun constat critique, élevé ou moyen ouvert | `docs/securite/asvs-l2.md` : SEC-01 corrigé, SEC-02 résolu, SEC-03 corrigé, SEC-04 résolu ; SEC-05 à SEC-09 faibles corrigés ou acceptés (SEC-07 accepté par l'utilisateur) | OK |
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
| C2 | Recette depuis zéro selon `docs/deploy.md` et `docs/exploitation/mise-en-production.md` | `sh scripts/recette/up.sh`, `sh scripts/recette/realm.sh` ; checklist rejouée par un tiers (statut « non consigné » dans la checklist) | à vérifier |
| C3 | Bancs de la recette : périphérie, réseaux, TLS, journaux, secrets, restauration | `sh scripts/recette/tests/{edge,reseaux,tls,journaux,secrets,restauration}.sh` (+ `realm.sh`) | à vérifier |
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
| D5 | Kit de formation rejoué sur un environnement neuf, réinitialisation < 15 min | `sh scripts/recette/down.sh` puis `up.sh`, `realm.sh`, `peupler_demo --profil formation --recette` ; suivre les fiches | à faire |
| D6 | Document de passage `docs/exploitation/passage-0.9.0.md` (résultats, constats acceptés, conditions de la 1.0.0) | fichier absent | à faire |
| D7 | Revue visuelle de tous les écrans et corrections d'interface (T22, T24, T25) | rapports de QA design dans `docs/recette/` partiels | à faire |

## E. Décisions de l'ONEA (bloquent la mise en production)

| # | Décision | Statut |
|---|---|---|
| E1 | Destination de la copie hors serveur des sauvegardes et détenteurs du mot de passe restic (U1) | bloqué par ONEA |
| E2 | Hébergement, noms DNS, source du certificat TLS (U2) | bloqué par ONEA |
| E3 | SMTP (U3) : sans `EMAIL_URL`, la production refuse de démarrer | bloqué par ONEA |
| E4 | Réseau : proxy amont, réseau d'administration, supervision (U5) | bloqué par ONEA |
| E5 | 22 gabarits Word réels (provisoires acceptés pour la livraison, pas pour l'usage final) | bloqué par ONEA |
| E6 | Abréviations QPC, GST, QCI, MARC, FF, RO, PT, FCT, FDT, FIT, FO ; rôles OTP (D19) ; libellé de la direction des participants sur l'ordre de mission | bloqué par ONEA |
| E7 | Formation (U6) : participants, dates, salle, postes | bloqué par ONEA |
| E8 | ClamAV : accepté (6c982ec) ; reste l'accès sortant vers les signatures ou un miroir local | bloqué par ONEA |

## Synthèse au 2026-11-03
Logiciel : fonctionnellement intégré dans `develop` jusqu'au lot 8 et au lot 9 (T1 à T21, T23, T26 à T29, T31) ; **no-go
aujourd'hui** pour la livraison finale, faute des critères A5, A8, D2, D3, D5, D6, D7 (travail restant) et des
vérifications « à vérifier » non rejouées. Mise en production : en plus, E1 à E4 à lever par l'ONEA.
