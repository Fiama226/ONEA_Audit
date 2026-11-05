---
name: django-conventions
description: Conventions backend du projet ONEA Audit (Django 5, DRF, django-fsm, auditlog, Celery, docxtpl). À lire avant d'écrire ou relire du code Python backend.
---

# Conventions backend

## Arborescence
```
backend/
  config/            settings (base, dev, prod), urls, celery
  apps/
    core/            modèle de base abstrait, mixins, permissions communes, utils
    users/           comptes, rôles (RAI, AUDITEUR, AUDITE, DG, ADMIN), authentification par sessions, délégation
    referentiel/     processus ONEA, directions, objets auditables, cartographie des risques
    missions/        Mission, étapes IFACI, fiche de suivi, réunions, entretiens
    programme/       référentiel d'audit, objectifs d'audit, programme de travail, fiches de test
    constats/        observations, forces/faiblesses, causes, recommandations
    actions/         plan d'actions, suivi des recommandations, relances
    documents/       gabarits docx, générateurs docxtpl, versions figées, export PDF
  tests/             conftest, factories, tests par app
```

## Modèle de base
Toute entité métier hérite de `core.models.BaseModel` : `id` UUID, `created_at`,
`updated_at`, `created_by`, `updated_by`, `deleted_at` + manager qui exclut les supprimés.
Enregistrée dans `auditlog.register()`.

## Machines à états (django-fsm)
```python
class Mission(BaseModel):
    status = FSMField(default=Statut.BROUILLON, choices=Statut.choices, protected=True)

    @transition(field=status, source=Statut.BROUILLON, target=Statut.PLANIFIEE,
                permission=lambda instance, user: user.has_role("RAI"))
    def planifier(self, by):
        ...
```
Chaque transition : source, target, garde de rôle, effet de bord dans un service, test.

## Services
`apps/<app>/services.py` : fonctions `verbe_objet(…, by: User) -> Objet`. Les vues
n'orchestrent jamais la logique. Les services lèvent `core.exceptions.RegleMetierError`
(convertie en HTTP 422 par le handler DRF).

## API
- drf-spectacular pour OpenAPI ; chaque vue documentée (`@extend_schema`).
- Routes : `/api/v1/<ressource>/`, nommage pluriel anglais (`/api/v1/missions/`).
- Pagination `PageNumberPagination`, filtres django-filter, tri `ordering`.
- Erreurs : format unique `{"detail": str, "errors": {champ: [messages]}}`, messages en français.
- Permissions : `IsRAI`, `IsAuditeurDeLaMission`, `IsAuditeDuPerimetre`, `ReadOnlyDG`.

## Documents
- Un gabarit `.docx` par document, nom identique au type (`pv_ouverture.docx`).
- `documents/generators/<domaine>.py` expose `build_context(obj) -> dict` et `render(obj) -> bytes`.
- Rendu docx via docxtpl, PDF via Gotenberg (`POST /forms/libreoffice/convert`).
- Chaque rendu validé crée un `DocumentVersion` immuable (sha256, clé de stockage, auteur).

## Tâches Celery
Génération de documents, indexation Meilisearch, relances d'échéances. Idempotentes,
`acks_late=True`, retry borné.

## Tests
pytest, `factory_boy`, `pytest-django` avec base PostgreSQL réelle (pas SQLite).
Un test par transition et par permission. `assertNumQueries` sur les listes.

## Qualité
ruff (format + lint), mypy strict sur `apps/`, pre-commit. Pas de `# type: ignore` sans motif.
