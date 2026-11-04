# Performance de l'API : budgets et mesures (lot 9, tâche 23)

Budgets D10 (mono-utilisateur, volumétrie réduite) : p95 ≤ 300 ms par liste ou détail ; nombre
de requêtes SQL par route sous un budget, identique pour une page de 10 et de 50 éléments.

## Ce qui est vérifié

| Test | Marqueur | Contenu |
|---|---|---|
| `backend/tests/performance/test_budgets_requetes.py` | (par défaut) | une épreuve par route GET du schéma OpenAPI : route sans budget = échec ; requêtes ≤ budget ; même nombre de requêtes pour `page_size=10` et `page_size=50` |
| `backend/tests/performance/test_temps_reponse.py` | `perf` (exclu par défaut) | p95 de 20 appels ≤ 300 ms par route (`PERF_P95_MS` pour une machine plus lente, `PERF_RAPPORT=<fichier>` pour relever les p95) |

Les budgets sont dans `backend/tests/performance/budgets.py` (mesure + 2, plancher 5). Toute
nouvelle route GET doit y déclarer le sien.

Données : `peupler_tout` profil volumétrie échelle 0,2 (comme la commande `peupler_demo`), jouées
dans une transaction annulée en fin de module, **plus** un semis de test (`seed.py`) : les
peuplements de démonstration des lots 5 à 8 sont vides, on crée donc une mission chargée de 52
constats avec recommandations, actions, suivis, preuves, demandes de report, relances, réponses,
acceptations, rapport, rapport provisoire, 52 réponses au provisoire, 52 destinataires et 52 pièces.

Lancer :

```powershell
cd backend
python -m pytest tests/performance --create-db                 # budgets de requêtes
python -m pytest tests/performance -m perf --create-db         # p95 par route
```

## Mesure avant / après

Un seul point d'accès dépassait le budget : `GET /api/v1/documents/available/` (N+1).

| Route | Requêtes avant | Requêtes après | Cause et correction |
|---|---|---|---|
| `/api/v1/documents/available/` (mission chargée, 52 constats) | **137** | **27** | une requête `missions_mission` par objet (`objet.mission` paresseux : 60) et un `EXISTS` de visibilité par constat (52). La mission déjà chargée est rattachée aux objets ; les constats exposent `ids_consultables` (une requête en lot) |
| même route, mission de démonstration | 25 à 28 | 25 à 28 | inchangé (peu d'objets) |

Les 133 autres routes sont à 1 à 12 requêtes (maximum : `dashboards/rai/` avec 12), sans
dépendance à la taille de page. Le temps de `documents/available/` est passé d'environ 370 ms à
80 ms sur la base chargée.

## Index

Aucun index n'est ajouté. Raison mesurée : sur la volumétrie réduite, tous les plans
`EXPLAIN (ANALYZE, BUFFERS)` des requêtes les plus fréquentes sont des tris en mémoire sur
quelques dizaines de lignes (0,04 à 0,17 ms), et les tables chaudes disposent déjà d'index
composites adaptés :

- `constats_constat` : `(mission_id, numero)` et `(mission_id, reference)` uniques ;
- `suivi_suiviaction` : `(statut, echeance)`, `(responsable_id, statut)` ;
- `notifications_notification` : `(destinataire_id, lue_le, created_at)` ;
- `documents_document` : `(mission_id, type_document)` et unicité partielle `deleted_at IS NULL`.

Un index sans gain démontré alourdirait les écritures et les déclencheurs de la tâche 10
(`apps/core/gardes_sql.py`) sans bénéfice ; aucune migration n'est donc créée
(`makemigrations --check` propre). Si la volumétrie réelle l'exige, relever les plans avec
`pg_stat_statements` (activé en recette) sur une base à l'échelle 1 puis créer l'index par
migration numérotée après les existantes.

Requêtes de diagnostic (recette) :

```sql
SELECT calls, round(mean_exec_time::numeric, 2) AS ms_moyen, left(query, 120)
FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;
```

## Import de 5 000 lignes (référentiel, lot 2 T4 M8)

`importer_referentiel` sur 5 000 directions (limite du fichier), base de volumétrie, poste de
développement : **≈ 70 s** (14 ms par ligne : toutes les écritures passent par les services, avec
piste d'audit ; le mode `dry_run` coûte autant car il écrit puis annule). Acceptable pour un
import administrateur ponctuel ; à relancer en tâche de fond si la limite devait être relevée.

## p95 par route (20 appels, ms)

| Route | p95 (ms) |
|---|---|
| `/api/v1/action-plan-commitments/` | 13 |
| `/api/v1/action-plan-commitments/texte/` | 8 |
| `/api/v1/action-plans/summary/` | 23 |
| `/api/v1/analysis-questionnaires/` | 20 |
| `/api/v1/analysis-questionnaires/{id}/` | 13 |
| `/api/v1/analysis-questions/` | 17 |
| `/api/v1/analysis-questions/{id}/` | 10 |
| `/api/v1/auditable-objects/` | 7 |
| `/api/v1/auditable-objects/{id}/` | 4 |
| `/api/v1/auditable-objects/tree/` | 13 |
| `/api/v1/audit-frameworks/{id}/` | 19 |
| `/api/v1/audit-frameworks/{id}/snapshot/` | 9 |
| `/api/v1/audit-log/` | 11 |
| `/api/v1/audit-log/{id}/` | 7 |
| `/api/v1/audit-objectives/` | 16 |
| `/api/v1/audit-objectives/{id}/` | 8 |
| `/api/v1/audit-plan-lines/` | 18 |
| `/api/v1/audit-plan-lines/{id}/` | 10 |
| `/api/v1/audit-plans/` | 9 |
| `/api/v1/audit-plans/{id}/` | 7 |
| `/api/v1/audit-plans/{id}/export/` | 1 |
| `/api/v1/audit-plans/{id}/summary/` | 12 |
| `/api/v1/corrective-actions/` | 17 |
| `/api/v1/corrective-actions/{id}/` | 21 |
| `/api/v1/dashboards/auditee/` | 15 |
| `/api/v1/dashboards/auditor/` | 18 |
| `/api/v1/dashboards/dg/` | 24 |
| `/api/v1/dashboards/implementation-rates/export/` | 72 |
| `/api/v1/dashboards/rai/` | 37 |
| `/api/v1/directions/` | 10 |
| `/api/v1/directions/{id}/` | 6 |
| `/api/v1/documents/` | 75 |
| `/api/v1/documents/{id}/` | 84 |
| `/api/v1/documents/available/` | 117 |
| `/api/v1/document-types/` | 250 |
| `/api/v1/document-versions/{id}/` | 27 |
| `/api/v1/document-versions/{id}/consultations/` | 21 |
| `/api/v1/document-versions/{id}/download/` | 70 |
| `/api/v1/draft-report-responses/` | 63 |
| `/api/v1/draft-report-responses/texte/` | 4 |
| `/api/v1/draft-reports/` | 33 |
| `/api/v1/draft-reports/{id}/` | 20 |
| `/api/v1/evidence/` | 31 |
| `/api/v1/evidence/{id}/` | 13 |
| `/api/v1/evidence/{id}/download/` | 11 |
| `/api/v1/finding-responses/` | 20 |
| `/api/v1/finding-responses/{id}/` | 14 |
| `/api/v1/findings/` | 293 |
| `/api/v1/findings/{id}/` | 61 |
| `/api/v1/follow-up/actions/` | 276 |
| `/api/v1/follow-up/actions/{id}/` | 94 |
| `/api/v1/follow-up/actions/{id}/events/` | 36 |
| `/api/v1/follow-up/actions/export/` | 123 |
| `/api/v1/follow-up/evidence/` | 24 |
| `/api/v1/follow-up/evidence/{id}/` | 18 |
| `/api/v1/follow-up/evidence/{id}/download/` | 11 |
| `/api/v1/follow-up/extension-requests/` | 19 |
| `/api/v1/follow-up/extension-requests/{id}/` | 13 |
| `/api/v1/follow-up/missions/` | 11 |
| `/api/v1/follow-up/recommendations/` | 48 |
| `/api/v1/follow-up/recommendations/{id}/` | 18 |
| `/api/v1/follow-up/recommendations/export/` | 88 |
| `/api/v1/health/` | 1 |
| `/api/v1/independence-declarations/` | 45 |
| `/api/v1/independence-declarations/{id}/` | 20 |
| `/api/v1/interviews/` | 24 |
| `/api/v1/interviews/{id}/` | 15 |
| `/api/v1/marc-lines/` | 14 |
| `/api/v1/marc-lines/{id}/` | 12 |
| `/api/v1/me/` | 2 |
| `/api/v1/meetings/` | 21 |
| `/api/v1/meetings/{id}/` | 10 |
| `/api/v1/mission-assignments/` | 16 |
| `/api/v1/mission-assignments/{id}/` | 9 |
| `/api/v1/mission-risks/` | 20 |
| `/api/v1/mission-risks/{id}/` | 8 |
| `/api/v1/missions/` | 35 |
| `/api/v1/missions/{id}/` | 59 |
| `/api/v1/missions/{id}/default-auditees/` | 41 |
| `/api/v1/missions/{id}/risk-matrix/` | 29 |
| `/api/v1/missions/{id}/tracking/` | 37 |
| `/api/v1/mission-steps/` | 13 |
| `/api/v1/mission-steps/{id}/` | 18 |
| `/api/v1/notifications/` | 5 |
| `/api/v1/notifications/unread-count/` | 3 |
| `/api/v1/numbering-formats/` | 6 |
| `/api/v1/numbering-formats/{type_document}/` | 6 |
| `/api/v1/orientation-reports/{id}/` | 13 |
| `/api/v1/planned-tests/` | 22 |
| `/api/v1/planned-tests/{id}/` | 44 |
| `/api/v1/process-descriptions/` | 22 |
| `/api/v1/process-descriptions/{id}/` | 17 |
| `/api/v1/processes/` | 23 |
| `/api/v1/processes/{id}/` | 21 |
| `/api/v1/recommendations/` | 19 |
| `/api/v1/recommendations/{id}/` | 8 |
| `/api/v1/reminders/` | 22 |
| `/api/v1/report-recipients/` | 16 |
| `/api/v1/report-recipients/{id}/` | 8 |
| `/api/v1/reports/` | 76 |
| `/api/v1/reports/{id}/` | 42 |
| `/api/v1/reports/{id}/download/` | 53 |
| `/api/v1/reports/{id}/preview/` | 151 |
| `/api/v1/reports/{id}/validation-text/` | 23 |
| `/api/v1/risk-acceptances/` | 23 |
| `/api/v1/risk-acceptances/{id}/` | 9 |
| `/api/v1/risk-maps/` | 9 |
| `/api/v1/risk-maps/{id}/` | 5 |
| `/api/v1/risk-maps/{id}/compare/` | 18 |
| `/api/v1/risk-maps/{id}/export/` | 1 |
| `/api/v1/risk-maps/{id}/matrix/` | 19 |
| `/api/v1/risks/` | 51 |
| `/api/v1/risks/{id}/` | 36 |
| `/api/v1/search/` | 2 |
| `/api/v1/segregation-grids/` | 7 |
| `/api/v1/segregation-grids/{id}/` | 5 |
| `/api/v1/signature-settings/` | 5 |
| `/api/v1/strengths-weaknesses/` | 17 |
| `/api/v1/strengths-weaknesses/{id}/` | 6 |
| `/api/v1/templates/` | 12 |
| `/api/v1/templates/{id}/` | 6 |
| `/api/v1/templates/{id}/file/` | 11 |
| `/api/v1/test-sheets/` | 21 |
| `/api/v1/test-sheets/{id}/` | 48 |
| `/api/v1/user-accounts/` | 11 |
| `/api/v1/user-accounts/{id}/` | 9 |
| `/api/v1/users/` | 7 |
| `/api/v1/work-programs/` | 15 |
| `/api/v1/work-programs/{id}/` | 10 |
| `/api/v1/work-programs/snapshots/` | 7 |
| `/api/v1/work-programs/snapshots/{id}/` | 6 |
| `/api/v1/work-programs/summary/` | 13 |

Aucune route n'atteint 300 ms. Trois routes sont proches du seuil (`findings/`,
`follow-up/actions/`, `document-types/`), mais uniquement sous la charge du poste de mesure
(agents en parallèle) : leur médiane est d'environ 50 ms, le temps est passé en sérialisation
Python (0 à 30 ms de SQL) et non en base. Sur une machine chargée, relever `PERF_P95_MS`.
Deux routes sont exclues du test de temps car dominées par un service externe :
`templates/{id}/preview/` (conversion Gotenberg) et `user-accounts/directory-search/` (Keycloak).

## Limites

- Le semis imite la volumétrie, il ne la remplace pas : une revue à l'échelle 1 sur la recette
  reste utile pour les index.
- Les routes de téléchargement et d'export sont mesurées sur leur première réponse (fichier
  généré à la volée).

## Test de charge (lot 9, tâche 26)

### Ce qui est livré

| Fichier | Rôle |
|---|---|
| `loadtest/locustfile.py` | scénario Locust (MIT) et vérification des seuils D10 (code de sortie 1 si un seuil est dépassé) |
| `loadtest/requirements.in`, `requirements.txt` | Locust 2.47.0 épinglé, dépendances résolues avec empreintes SHA-256 (`uv pip compile --universal --generate-hashes`), installées par `pip install --require-hashes` |
| `scripts/recette/charge.sh` | lance le scénario sur la recette, relève `docker stats` toutes les 30 s, contrôle la file Celery 2 min après la fin |
| `.recette/comptes.txt` (fichier local, hors Git) | comptes `charge01…40` (2 RAI, 20 AUDITEUR, 15 AUDITE, 3 DG), créés par l'administration des comptes de l'application (le script `realm.sh` du realm Keycloak a été supprimé avec Keycloak) |

Licences : Locust et ses dépendances sont sous MIT, BSD, Apache-2.0, MPL-2.0 (bidict, certifi) ou PSF ;
`zope.event` et `zope.interface` sont sous ZPL-2.1 (licence permissive de type BSD, approuvée OSI,
non listée dans CLAUDE.md : à valider). Outil de test seulement, jamais livré avec l'application.

### Scénario

40 utilisateurs, montée de 2 par seconde, 20 minutes, attente de 1 à 3 s entre deux actions.
Chaque utilisateur prend un compte `chargeNN`, obtient son jeton par le client `onea-charge`
(accès direct par mot de passe, recette seulement) et le renouvelle avant expiration. Poids des tâches :

| Part | Tâche | Routes |
|---|---|---|
| 30 % | listes | missions (pages de 25 et 50), documents, recommandations du suivi, notifications ; le DG n'a pas accès aux missions : suivi et rapports |
| 25 % | détail de mission et étapes | `missions/{id}/`, `mission-steps/?mission=` (pas pour l'AUDITE : 403 attendu) |
| 10 % | référentiel | directions, processus, risques (équipe d'audit) |
| 10 % | tableau de bord | `dashboards/{rai,auditor,auditee,dg}/` selon le rôle |
| 15 % | écritures courantes | compte rendu d'entretien (`PATCH interviews/{id}/`), fiche de test (`PATCH test-sheets/{id}/`), équipe d'audit |
| 5 % | génération de document | `documents/available/`, `POST documents/generate/`, puis attente de l'état `PRETE` : durée de bout en bout |
| 5 % | téléchargements | `document-versions/{id}/download/` (Word) |

Les écritures refusées par une règle de métier (400, 403, 404, 409, 422 : mission suspendue,
entretien annulé…) ne sont pas des échecs mais sont comptées et publiées (`refus_metier_ecriture`).
Toute réponse 5xx, 401, 429 ou lecture autre que 200 est un échec.

### Seuils D10 vérifiés

| Seuil | Règle appliquée |
|---|---|
| p95 lecture ≤ 800 ms | p95 de la **pire route** de lecture (pas une moyenne qui masquerait un point lent) |
| p95 écriture ≤ 1 500 ms | idem, routes d'écriture |
| génération de bout en bout p95 ≤ 20 s | de la demande à l'état `PRETE` du Word (la conversion PDF n'est pas attendue) |
| 0 réponse 5xx | compteur dédié |
| taux d'erreur < 1 % | échecs / requêtes (jetons compris) |
| file Celery vide 2 min après la fin | `charge.sh` (`LLEN celery`) ; hors Locust |

Une mesure absente (aucune écriture, aucune génération) est un échec : « non mesuré » n'est pas « conforme ».
Tout seuil relevé par variable (`SEUIL_*`) doit être consigné ici.

### Lancer

```sh
sh scripts/recette/up.sh && sh scripts/recette/certs.sh   # puis créer les comptes chargeNN (docs/recette.md)
# peuplement : exec web python manage.py peupler_demo --profil volumetrie --recette
sh scripts/recette/charge.sh      # 40 utilisateurs, 2/s, 20 min ; CHARGE_USERS / CHARGE_DUREE pour réduire
```

Sorties dans `.recette/charge/<horodatage>/` : CSV Locust, `resume.json`, `docker-stats.csv`, `locust.log`.

### État de la mesure : ce qui a été mesuré, et ce qui ne l'a pas été

**Note (2026-11-04).** Les mesures ci-dessous datent du 2026-11-02, avant le remplacement de Keycloak par l'authentification interne : les mentions de Keycloak, du client `onea-dev-cli` et de `user-accounts/directory-search/` y sont historiques (ces éléments n'existent plus). Les connexions se font désormais par session ; la mesure est à refaire sur la version courante.

**Non exécuté : `sh scripts/recette/charge.sh` sur la recette (critère d'acceptation de la tâche).**
La pile de recette tournait sur le poste mais n'appartenait pas à cette tâche et n'a pas été touchée.
`charge.sh` est écrit (`sh -n` passe) mais n'a **pas** été joué. Reste à faire
à la recette : `sh scripts/recette/charge.sh` en entier (20 min, 40 comptes distincts), puis y consigner
les résultats avec les `docker stats` des conteneurs de recette.

**Exécuté : une mesure locale, réduite, sur une instance jetable** (1er novembre 2026) :

| | Recette visée | Mesure locale |
|---|---|---|
| Machine | VPS | portable i5-11300H, 15,8 Go ; **générateur de charge, API, PostgreSQL, Keycloak, Redis, Celery sur le même hôte** (CPU de l'hôte 80 à 100 % pendant les essais) |
| API | gunicorn derrière nginx (TLS) | `runserver --noreload` (dev, HTTP, sans nginx ni limitation de débit périphérique D3) ; Celery 4 fils |
| Keycloak | realm de recette, client `onea-charge`, 40 comptes | Keycloak de développement, client `onea-dev-cli`, **5 comptes seulement** (`rai`, `auditeur1`, `auditeur2`, `audite1`, `dg`) partagés par les 40 utilisateurs virtuels (2 RAI, 20 AUDITEUR, 15 AUDITE, 3 DG) |
| Données | `peupler_demo --profil volumetrie` | idem à l'échelle 1 : 60 missions, 1 080 étapes, 39 entretiens, 189 documents, 423 versions, 30 directions, 61 comptes ; aucune fiche de test (les peuplements des lots 5 à 8 sont vides) |
| Gotenberg, Meilisearch | ceux de la recette | conteneurs jetables `gotenberg:8.37.0` et `meilisearch:v1.12.8` (index vide : la recherche n'est pas sollicitée) |
| Durée | 20 min | **8 min** (montée à 40 en 20 s) |
| Redis (jetons, débit, Celery) | dédié | base 9 du Redis de développement |

Les 40 utilisateurs virtuels ont été simultanés, mais le partage de 5 comptes a deux conséquences visibles : Keycloak refuse
environ un quart des connexions simultanées d'un même compte (401 transitoire, rejoué jusqu'à 3 fois ; chaque utilisateur a fini par
obtenir son jeton), et la limite de génération par utilisateur (20/min, D3) a produit 2 réponses 429. Ces deux écarts n'existent pas
avec 40 comptes distincts.

Résultat de la dernière mesure (8 min, environ 9 000 requêtes, aucune 5xx ; fichiers dans `docs/qualite/charge/2026-11-02-local/`) :

| Seuil | Mesure | Verdict |
|---|---|---|
| p95 lecture (pire route : `documents/available/`) | 360 ms (p95 global 230 ms) | tenu (≤ 800) |
| p95 écriture (pire route : compte rendu d'entretien) | 390 ms | tenu (≤ 1 500) |
| génération de bout en bout p95 | 1,7 s (23 générations, médiane 1,3 s) | tenu (≤ 20 s), **conversion PDF non incluse** |
| 5xx | 0 | tenu |
| taux d'erreur | 0,37 % (33 / 9 009 : 25 jetons 401, 3 reprises 401, 3 refus 403 du DG sur la liste de missions, 2 réponses 429) | tenu (< 1 %), avec les réserves ci-dessus |
| file Celery | 0 tâche en attente (contrôlée plus de 2 min après la fin) | tenu |

Ressources (relevés toutes les 30 s, `ressources.csv`) : PostgreSQL au plus 66 % d'un cœur et 196 Mio ; API Python 144 Mio ;
worker Celery 133 Mio ; Keycloak 484 Mio et au plus 3 % ; Redis 13 Mio ; Gotenberg au plus 36 % (294 Mio) ;
Meilisearch au plus 46 % (26 Mio). L'API (`runserver`) a consommé environ 300 s de CPU sur 8 min. **Ces chiffres ne valent pas pour le VPS
de recette** : ils montrent que le scénario fonctionne et qu'aucun point d'accès ne s'effondre ; ils ne qualifient ni la capacité ni la marge.

### Corrections issues de la mesure (avant / après)

| Constat | Avant | Correction | Après |
|---|---|---|---|
| Génération impossible (422 « format de numérotation invalide ») pour les types des lots 5 à 8 sur une base neuve : 5 fournisseurs déclaraient `{sequence:02d}`, que le validateur refuse | 16 refus sur 18 demandes (essai court) | modèle par défaut `{sequence}` (la séquence est déjà sur 2 chiffres) ; test `test_numerotation_defauts.py` qui valide le modèle de chaque type enregistré (rouge avant, vert après) | 0 refus de ce type |
| `GET documents/available/` lent pour un auditeur : 12 types refont les mêmes droits (rôle, déclaration, étapes) | 64 requêtes, 105 ms seul ; **p95 880 ms** sous 40 utilisateurs (seuil 800 dépassé ; médiane 360 ms) | mémo à portée de requête (`apps/core/memoire.py`), utilisé en lecture seule par cette route pour `droits_analyse`, `role_dans_mission`, `declaration_levee` | 18 requêtes, 40 ms seul ; **p95 360 ms**, médiane 140 ms sous 40 utilisateurs |
| Script : 403 sur `mission-steps` (AUDITE) et sur les téléchargements, 401 de jeton | 8,3 % d'erreurs (1re mesure, 6 min) | rôle respecté par tâche ; reprise du jeton | 0,37 % |

Le budget de requêtes de `documents/available/` (29, mesuré avec un RAI) n'a pas été modifié ; le test de budgets ne couvre pas un
auditeur, d'où l'écart passé inaperçu à la tâche 23.

### Limites et points ouverts

- La mesure de recette reste à faire (voir plus haut) : c'est elle qui valide les seuils D10 ; la mesure locale n'est qu'un essai du
  script et un détecteur de défauts.
- `pg_stat_statements` n'est pas activé sur la base locale : l'analyse s'est faite par comptage des requêtes et profilage de la vue,
  pas par les statistiques de PostgreSQL. À relever à la recette si un seuil y échoue.
- La conversion PDF est asynchrone (tâche `convertir_pdf`) : son délai n'entre pas dans la mesure de bout en bout.
- Aucune écriture sur les fiches de test (pas de données de départ) : seule la route `interviews` est exercée en écriture ;
  `test-sheets` s'active dès qu'une fiche existe. 360 tirages d'écriture sont restés sans cible (utilisateurs sans entretien visible)
  et 218 écritures ont été refusées par une règle de métier (missions suspendues notamment).
- Le test ne couvre ni la limitation de débit périphérique nginx (D3), ni la recherche Meilisearch, ni les téléversements.
- `tests/performance/test_budgets_requetes.py::test_budget_requetes[/api/v1/audit-log-settings/]` échoue sur `develop` : cette route
  n'a pas de budget déclaré (antérieur à cette tâche, non corrigé ici).
