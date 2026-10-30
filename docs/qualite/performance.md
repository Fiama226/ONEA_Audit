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
