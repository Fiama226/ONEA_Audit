# Task 6 report - REST API analyse + OpenAPI

Status: DONE (commit c3dbaa5 on worktree-agent-abacfb838eaa268f1, based on merge of feat/lot5-analyse 88d3903).
Tests: tests/analyse (178) + tests/test_schema.py + missions api contract/permissions = 329 passed. ruff, ruff format, mypy strict, makemigrations --check, spectacular --validate (0 warning), check-api-fresh: OK.

Decisions / deviations
- Window/freeze: writes go through exiger_contribution (403) then services (422 for freeze/window); droits_analyse is NOT used as a 403 gate (it would turn the mandatory gel 422 into 403). mes_droits still exposes it and a test checks concordance (false => 403 or 422).
- ENUM_NAME_OVERRIDES: AppreciationMarcEnum omitted - same choice set as TypeForceFaiblesseEnum, spectacular errors on duplicate names. LigneMARC.appreciation uses TypeForceFaiblesseEnum.
- process-descriptions and segregation-grids POST are upserts (200 if already existing, else 201).
- AUDITE: permission class allows only GET + opinions; non-diffused => 403 message; audit-frameworks retrieve returns an empty synthesis.
- opinions returns 201 AvisAudite. initialize actions return 200 with the list of created rows.
- gardes.fenetre_marc_close added (pure helper for etape_close); mypy.ini override for analyse.filters.
- Test fixtures in tests/analyse/fixtures_api.py (not conftest, to avoid T7 conflicts).
- schema.d.ts regenerated; expect a mechanical conflict with other branches (regenerate, never hand-merge).

## Fix section (review F)
- I1: audit-objectives POST wrapped in transaction.atomic (ajouter + modifier); test_creation_objectif_invalide_est_atomique (422 leaves no objective, number 1 not burned).
- I2: test_api_gel_422_sur_chaque_route_analyse now parametrised (mission suspendue / etapes closes) over every write route (questionnaires, questions, descriptions, grilles, MARC, FFA, objectifs, orientation, opinions).
- I3: crud_schema(upsert=True) documents the 200 on process-descriptions and segregation-grids POST; openapi + schema.d.ts regenerated.
- m1: contract note - LigneMARC.appreciation uses TypeForceFaiblesseEnum (no AppreciationMarcEnum).
- m2: segregation-grid POST now merges with the existing grid (like description), no erasure.
- m3: exiger_fenetre_marc reuses fenetre_marc_close. m4: statut_v/statut_vi are ChoiceField(StatutEtape), no hard-coded string. m5: test_avis_avant_diffusion_422.
- Tests: tests/analyse + test_schema = 191 passed; ruff, mypy, spectacular validate OK.
