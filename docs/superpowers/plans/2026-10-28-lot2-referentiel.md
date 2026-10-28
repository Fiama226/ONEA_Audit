# Lot 2 — Référentiel : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer le référentiel de l'audit interne : directions et départements, processus ONEA, objets auditables (domaine → opération), cartographie annuelle des risques versionnée et figée à la validation, matrice 5×5 interactive, comparaison de versions, export CSV/XLSX, chargement explicite des listes de référence, avec les écrans français correspondants.

**Architecture:** Nouvelle app Django `apps.referentiel` (modèles sur `core.models.BaseModel`, logique dans `services.py`, contraintes en base, gel garanti à la fois dans les services et dans `save()`), exposée par des ViewSets DRF sous `/api/v1/` avec une permission par rôles lecture/écriture. Le contrat OpenAPI est figé à la fin de la tâche 3 ; le frontend (`src/features/referentiel/`) le consomme via `schema.d.ts`, TanStack Query et un `DataTable` partagé, et réutilise `components/RiskMatrix` rendu cliquable.

**Tech Stack:** existants du lot 1 (Django 5.1, DRF, drf-spectacular, django-filter, django-fsm, django-auditlog, pytest, factory_boy ; React 19, TanStack Query 5 / Table, react-hook-form + zod, shadcn/ui, Vitest, MSW, Playwright) + **openpyxl ≥ 3.1 (MIT)** pour le XLSX et `types-openpyxl` (Apache-2.0, dev). CSV par la bibliothèque standard `csv`.

**Spec:** `docs/superpowers/specs/2026-10-27-plateforme-audit-interne-design.md` (§5 rôles, §6.1 Référentiel, §7 modèle de données, §9 interface, §11 lot 2, §14 « Cartographie » et « Confidentialité », §15.2 démarrage à vide) ; `docs/domaine/cartographie-risques-onea.md` ; `docs/design/charte-graphique.md`.

## Global Constraints

- Aucune fonctionnalité IA / LLM ; dépendances open source uniquement (liste de `CLAUDE.md`). Seules nouvelles dépendances : `openpyxl` (runtime) et `types-openpyxl` (dev). Côté frontend, aucune nouvelle dépendance runtime (composants shadcn générés sur `radix-ui` déjà présent).
- Interface, messages d'erreur, en-têtes d'export en français ; identifiants, routes d'API et commits en anglais (Conventional Commits).
- Rôles exactement `ADMIN`, `RAI`, `AUDITEUR`, `AUDITE`, `DG`. Matrice des droits : voir décision D4.
- Toute entité hérite de `core.models.BaseModel` et est enregistrée via `core.audit.register` ; jamais de suppression physique (`soft_delete`), unicités conditionnées par `deleted_at IS NULL`.
- Format d'erreur unique `{"detail": str, "errors": {champ: [messages]}}` ; 400 pour la validation de sérialiseur, 422 (`RegleMetierError`) pour les règles métier.
- Probabilité et impact entiers dans [1, 5] (contrainte CHECK en base) ; score = probabilité × impact (colonne générée) ; niveau **FAIBLE 1–7, MOYEN 8–14, ÉLEVÉ 15–25**.
- Code risque `<numero>-<CODE_PROCESSUS>-R<rang>`, regex `^[1-9][0-9]*-[A-Z]{2,5}-R[1-9][0-9]*$`, unique par version de cartographie.
- Code processus `^[A-Z]{2,5}$` ; code direction `^[A-Z][A-Z0-9-]{1,15}$` (ASCII majuscule, sans accent). Les libellés acceptent tout Unicode.
- **Démarrage à vide** (§15.2) : aucune migration de données, aucun seed automatique, aucun outil d'import dans l'interface. Seule la commande explicite `import_referentiel` charge directions et processus ; aucun risque n'est importé.
- Tests backend sur PostgreSQL réel ; couverture cible 85 % backend, 80 % frontend ; `assertNumQueries` sur les listes.
- `frontend/src/api/schema.d.ts` régénéré par `sh scripts/gen-api.sh` et vérifié par `sh scripts/check-api-fresh.sh` à chaque tâche qui touche l'API.
- Charte : tokens CSS uniquement (`bg-risk-low|medium|high`, `text-risk-foreground`…), aucune couleur hexadécimale dans un composant ; dates affichées `JJ/MM/AAAA` via `lib/dates.ts`.

## Décisions (prises par le rédacteur du plan, à confirmer par le client)

- **D1 — 11 processus, pas 13.** La spec annonce « 13 » mais ne cite que 11 codes, comme le document de domaine (EST, PSM, CGP, FEP, PAS, GCL, GRH, GSI, GAC, GFI, AFO). Le modèle n'énumère pas les codes : le RAI ajoute les deux manquants à l'écran dès qu'ils sont connus. Le fichier de référence livré contient les 11 processus et leurs 17 directions.
- **D2 — Une cartographie par année.** `CartographieVersion` unique par `annee` (hors supprimées), statuts `BROUILLON` → `VALIDEE`. Une version validée est **immuable et non supprimable** ; aucune « dévalidation ». Une nouvelle année peut être créée en copiant les risques d'une version existante. `version_courante()` = dernière version validée (consommée au lot 3, étape IV).
- **D3 — Numérotation serveur.** `numero` = max du numéro dans la version (supprimés inclus) + 1, `rang` = max du rang du processus dans la version + 1, sous `select_for_update` de la version. Le code est calculé une fois, stocké, jamais modifiable ; le processus d'un risque n'est pas modifiable. La copie conserve les codes : un même code dans deux versions désigne le même risque (base de la comparaison).
- **D4 — Droits.** `directions` et `processes` : lecture par tout rôle authentifié (listes non sensibles, utiles aux lots suivants), écriture RAI et ADMIN (§5 « référentiels »). `auditable-objects`, `risk-maps` (matrice, comparaison, export inclus) et `risks` : lecture ADMIN, RAI, AUDITEUR, DG ; **AUDITE → 403** ; écriture **RAI seul** (§14 : l'ADMIN n'a qu'un rôle technique). Le RAI tient et valide la cartographie : pas de séparation auteur/valideur pour cet objet.
- **D5 — Navigation inchangée.** L'entrée « Référentiel » reste réservée à ADMIN, RAI, AUDITEUR (lot 1). Le DG lit l'API pour ses tableaux de bord du lot 8 ; la matrice statique du tableau de bord RAI n'est pas branchée dans ce lot.
- **D6 — Import par commande seulement.** `python manage.py import_referentiel <fichier.csv> --user <login> [--dry-run]`, lancée par l'exploitant sur demande du RAI (`--user` doit être RAI ou ADMIN, il signe la piste d'audit). Idempotente (upsert par code, jamais de suppression), atomique, 5 000 lignes au plus.
- **D7 — Réponse et priorité.** `reponse` ∈ {TRAITER, TRANSFERER, TERMINER, TOLERER} (vide permis) ; `priorite` ∈ {1 Prioritaire, 2 Amélioration, 3 Observation}, par défaut dérivée du niveau (ÉLEVÉ → 1, MOYEN → 2, FAIBLE → 3), modifiable.
- **D8 — Recherche.** Paramètre `q` en `icontains` sur code et libellé : insensible à la casse, **sensible aux accents** ; la recherche plein texte sans accents arrive au lot 8 (Meilisearch).
- **D9 — Export.** `GET …/export/?type=csv|xlsx` (pas `?format=`, réservé par DRF à la négociation de rendu). CSV UTF-8 avec BOM, séparateur `;` (Excel en français) ; toute cellule commençant par `= + - @` (ou tabulation / retour chariot) est préfixée d'une apostrophe.
- **D10 — Arbre des objets auditables à deux niveaux** (DOMAINE sans parent → OPERATION dont le parent est un domaine du même processus). Un risque peut viser un objet auditable du même processus. L'objectif de contrôle et le dispositif de contrôle interne sont portés par le risque (grille à cinq colonnes du domaine).
- **D11 — Divers.** Une cartographie sans risque ne peut pas être validée. Codes de processus et de direction immuables après création (supprimer puis recréer libère le code). Supprimer un brouillon supprime logiquement ses risques. `FSMField(protected=False)` : un champ protégé casse `refresh_from_db()` ; l'immuabilité est garantie par les gardes `save()` et les services. Routes d'API au pluriel anglais.

## Review Focus

1. **Modifier ou supprimer un risque d'une version validée** (API, service, ou `save()` direct depuis le shell/admin) doit échouer en 422 avec « La cartographie 2026 est validée : elle ne peut plus être modifiée. », et la version elle-même ne peut être ni modifiée ni supprimée (tests Task 2 et Task 3).
2. **Codes de risque** : le même code dans deux versions est accepté ; un doublon dans une version est refusé par la base ; un numéro supprimé n'est jamais réattribué (tests Task 1 et Task 2).
3. **Probabilité ou impact hors [1, 5]** (0, 6, « abc », null) : 400 avec `errors.probabilite` à l'API, `IntegrityError` si l'on contourne le sérialiseur (tests Task 1 et Task 3).
4. **Supprimer un processus qui porte des risques ou objets actifs**, ou une direction rattachée, doit être refusé en 422 avec un message clair, et l'écran doit afficher ce message (tests Task 2 et Task 6).
5. **Accès par rôle** : AUDITE reçoit 403 sur cartographies, risques, objets ; AUDITEUR et DG en lecture seule ; ADMIN refusé en écriture sur les risques ; les boutons d'écriture n'apparaissent pas pour les rôles en lecture (tests Task 3, Task 6, Task 7).
6. **Import d'un CSV énorme ou invalide** (5 001 lignes, encodage Windows-1252, colonne manquante, champ géant) : arrêt sans aucune écriture, erreurs en français numérotées par ligne ; deuxième exécution identique sans effet (tests Task 4).
7. **Accents et injection de formule dans les exports** : « Défaillance du réseau d'eau – Ouagadougou » ressort intact en CSV (ouvert dans Excel) et en XLSX ; un libellé `=HYPERLINK(...)` est neutralisé ; un code « ÉST » est refusé à la saisie (tests Task 1 et Task 4).
8. **Plateforme vide** : sans processus ni cartographie, chaque écran affiche un état vide adapté au rôle (action pour le RAI, explication pour l'AUDITEUR), et la matrice d'une version vide renvoie 25 cases à zéro (tests Task 2, Task 6, Task 7).

## Vagues d'exécution

| Vague | Tâches | Agent / modèle | Dépend de |
|---|---|---|---|
| 1 | T1 modèles | backend-dev / sonnet | — |
| 2 | T2 services | backend-dev / sonnet | T1 |
| 3 | T3 API + contrat OpenAPI | backend-dev / sonnet | T2 |
| 4 | T4 export/import ∥ T5 fondations front | backend-dev / sonnet ∥ frontend-dev / sonnet | T3 (T5 : seulement `schema.d.ts` de T3) |
| 5 | T6 écrans structure ∥ T7 écrans cartographie | frontend-dev / sonnet ×2 | T5 (T7 utilise le contrat d'export décrit en T4, mocké par MSW) |
| 6 | T8 e2e, doc, vérification finale | test-engineer / sonnet | toutes |

Aucune tâche ne requiert opus : le modèle de gel et la matrice des droits sont fixés ici (D2–D4, D11). Chaque tâche est relue par `reviewer` (opus) ; T6 et T7 reçoivent aussi la revue visuelle `ui-designer`.

---

### Task 1: App `referentiel` — modèles, contraintes, migration, piste d'audit

**Model:** sonnet (backend-dev)

**Files:**
- Create: `backend/apps/referentiel/{__init__,apps,models,scoring,validators}.py`, `backend/apps/referentiel/migrations/{__init__,0001_initial}.py`
- Modify: `backend/config/settings/base.py` (`INSTALLED_APPS += ["apps.referentiel"]`), `backend/apps/core/audit.py`, `backend/tests/factories.py`
- Test: `backend/tests/referentiel/{__init__,test_models}.py`

**Interfaces:**
- Consumes: `BaseModel`, `core.audit.register`, `UserFactory` (lot 1).
- Produces:
  - `core.audit.register(model, m2m_fields: set[str] | None = None) -> None` (rétrocompatible).
  - Énumérations (`TextChoices`, valeur ASCII, libellé français) : `TypeEntite` DIRECTION « Direction », DEPARTEMENT « Département » ; `FamilleProcessus` PILOTAGE, REALISATION « Réalisation », SUPPORT ; `NatureObjet` DOMAINE, OPERATION « Opération » ; `StatutCartographie` BROUILLON, VALIDEE « Validée » ; `NiveauRisque` FAIBLE, MOYEN, ELEVE « Élevé » ; `ReponseRisque` TRAITER, TRANSFERER « Transférer », TERMINER, TOLERER « Tolérer ». `PrioriteRisque(IntegerChoices)` 1 « Prioritaire », 2 « Amélioration », 3 « Observation ».
  - `Direction` : `code` (16, validateur), `libelle` (200), `type`, `parent` FK self null PROTECT `related_name="departements"`. CHECK `direction_parent_coherent` : (DIRECTION et parent nul) ou (DEPARTEMENT et parent non nul). Unique `code` si non supprimé.
  - `Processus` : `code` (5, validateur), `libelle` (200), `famille`, `ordre` PositiveSmallInteger défaut 0, `directions` M2M `Direction` `related_name="processus"`. Unique `code` si non supprimé. Ordre par défaut `("ordre", "code")`.
  - `ObjetAuditable` : `processus` FK PROTECT `related_name="objets"`, `parent` FK self null PROTECT `related_name="operations"`, `nature`, `libelle` (300), `description` texte vide permis, `ordre`. CHECK `objet_parent_coherent` (DOMAINE ⇔ parent nul).
  - `CartographieVersion` : `annee` PositiveSmallInteger CHECK 2000–2100, `libelle` (200), `commentaire` texte vide permis, `statut` `FSMField(default=BROUILLON, protected=False)`, `source` FK self null SET_NULL, `validee_le` datetime null, `validee_par` FK user null PROTECT `related_name="+"`. Unique `annee` si non supprimée. Ordre `-annee`.
  - `Risque` : `version` FK PROTECT `related_name="risques"`, `processus` FK PROTECT `related_name="risques"`, `objet_auditable` FK null PROTECT, `numero`, `rang` (PositiveInteger, CHECK ≥ 1), `code` (32), `libelle` (500), `description`, `probabilite`, `impact` (PositiveSmallInteger, CHECK `risque_probabilite_1_5` et `risque_impact_1_5`), `score = GeneratedField(F("probabilite") * F("impact"), db_persist=True)`, `niveau = GeneratedField(Case(When(score ≥ 15 → "ELEVE"), When(≥ 8 → "MOYEN"), default "FAIBLE") sur l'expression produit, output CharField(8), db_persist=True)`, `vulnerabilite`, `reponse` (choix, vide permis), `priorite` (choix, CHECK 1–3), `objectif_controle`, `dispositif_controle` (textes vides permis). Uniques si non supprimé : (`version`, `code`), (`version`, `numero`), (`version`, `processus`, `rang`). Index (`version`, `probabilite`, `impact`).
  - `scoring.SEUIL_MOYEN = 8`, `scoring.SEUIL_ELEVE = 15`, `niveau_pour_score(score: int) -> NiveauRisque`, `priorite_par_defaut(niveau: NiveauRisque) -> PrioriteRisque`.
  - `validators.valider_code_processus`, `valider_code_direction`, `valider_code_risque` (`RegexValidator`, messages français).
  - Les cinq modèles enregistrés dans `ReferentielConfig.ready()` ; `Processus` avec `m2m_fields={"directions"}`.
  - Factories `DirectionFactory`, `ProcessusFactory`, `ObjetAuditableFactory`, `CartographieVersionFactory` (année séquentielle à partir de 2000), `RisqueFactory` (numéro séquentiel, `rang` = numéro, `code` calculé) dans `tests/factories.py`.

- [ ] **Step 1: Écrire les tests**
```python
@pytest.mark.parametrize("p,i", [(0, 3), (6, 3), (3, 0), (3, 6)])
def test_probabilite_impact_hors_bornes_rejetes_par_la_base(p, i):
    with pytest.raises(IntegrityError):
        RisqueFactory(probabilite=p, impact=i)

def test_score_et_niveau_generes_concordent_avec_scoring():
    for p in range(1, 6):
        for i in range(1, 6):
            r = RisqueFactory(probabilite=p, impact=i)
            assert (r.score, r.niveau) == (p * i, niveau_pour_score(p * i))

@pytest.mark.parametrize("score,niveau", [(1, "FAIBLE"), (7, "FAIBLE"), (8, "MOYEN"), (14, "MOYEN"), (15, "ELEVE"), (25, "ELEVE")])
def test_niveau_pour_score(score, niveau): assert niveau_pour_score(score) == niveau
```
Plus : `test_code_unique_par_version_mais_pas_entre_versions` (même code dans deux versions OK, doublon dans une version → `IntegrityError`) ; `test_une_seule_cartographie_par_annee_hors_supprimees` ; `test_code_processus_reutilisable_apres_soft_delete` ; `test_departement_sans_parent_rejete` ; `test_domaine_avec_parent_rejete` ; `test_code_processus_accentue_refuse` (`full_clean()` sur `code="ÉST"` → `ValidationError` sur `code`) ; `test_creation_et_m2m_historisees` (LogEntry à la création d'un `Risque` ; ajout d'une direction à un processus visible dans `changes`).
- [ ] **Step 2: `cd backend && pytest tests/referentiel -v`** → FAIL (app inconnue).
- [ ] **Step 3: Implémenter** app, modèles, validateurs, `scoring.py`, extension de `audit.register`, factories ; `python manage.py makemigrations referentiel`.
- [ ] **Step 4: `pytest tests/referentiel -v`** → PASS ; `python manage.py makemigrations --check --dry-run` → « No changes detected » ; `ruff check . && mypy .` → 0.
- [ ] **Step 5: Commit** `feat(referentiel): add reference and risk map models with db constraints and audit trail`.

### Task 2: Services métier — gardes, numérotation, gel, copie, matrice, comparaison

**Model:** sonnet (backend-dev)

**Files:**
- Create: `backend/apps/referentiel/{services,exceptions}.py`
- Modify: `backend/apps/referentiel/models.py` (transition FSM, gardes `save()`)
- Test: `backend/tests/referentiel/test_services_structure.py`, `backend/tests/referentiel/test_services_cartographie.py`

**Interfaces:**
- Consumes: modèles, énumérations, `scoring` (Task 1) ; `RegleMetierError` (lot 1).
- Produces (toutes les fonctions sont `@transaction.atomic`, prennent `by: User` en mot-clé, renseignent `created_by`/`updated_by`, lèvent `RegleMetierError` avec `errors` par champ) :
  - `exceptions.CartographieFigeeError(RegleMetierError)` ; message `"La cartographie {annee} est validée : elle ne peut plus être modifiée."`.
  - `creer_direction(*, code, libelle, type, parent=None, by) -> Direction` ; `modifier_direction(direction, *, by, **changes) -> Direction` ; `supprimer_direction(direction, *, by) -> None` (refus si rattachée à un processus actif ou porteuse de départements actifs : « Cette direction est rattachée à un processus ou porte des départements actifs. »). Parent d'un département : direction active de type DIRECTION, sinon `errors.parent` « Un département doit être rattaché à une direction. ».
  - `creer_processus(*, code, libelle, famille, ordre=0, directions=(), by) -> Processus` ; `modifier_processus` ; `supprimer_processus` (refus si risques ou objets actifs : « Ce processus porte des risques ou des objets auditables actifs : supprimez-les d'abord. »).
  - `creer_objet(*, processus, nature, libelle, parent=None, description="", ordre=0, by) -> ObjetAuditable` (opération : parent = domaine actif du même processus, sinon `errors.parent` « Une opération doit être rattachée à un domaine du même processus. ») ; `modifier_objet` ; `supprimer_objet` (refus si opérations ou risques actifs).
  - Tout `modifier_*` qui reçoit un `code` différent lève `errors.code` « Le code ne peut pas être modifié après création. ».
  - `creer_version(*, annee, libelle, commentaire="", source=None, by) -> CartographieVersion` (année déjà prise → `errors.annee` « Une cartographie existe déjà pour l'année {annee}. » ; avec `source`, copie de ses risques actifs en conservant numéro, rang, code et champs ; l'objet auditable n'est repris que s'il est actif) ; `modifier_version(version, *, by, **changes)` (libellé, commentaire) ; `supprimer_version(version, *, by)` (brouillon seulement ; supprime logiquement ses risques) ; `valider_version(version, *, by) -> CartographieVersion` (≥ 1 risque, sinon « Une cartographie sans risque ne peut pas être validée. » ; renseigne `validee_le`, `validee_par`).
  - `CartographieVersion.valider()` : `@transition(field=statut, source=BROUILLON, target=VALIDEE)`, appelée uniquement par le service.
  - Gardes : `CartographieVersion.save()` et `Risque.save()` lèvent `CartographieFigeeError` si la ligne de version **en base** a le statut VALIDEE (la sauvegarde qui valide passe, car la base dit encore BROUILLON) ; `soft_delete` passe par `save()` et est donc couvert.
  - `creer_risque(*, version, processus, libelle, probabilite, impact, objet_auditable=None, priorite=None, by, **details) -> Risque` (`details` ⊂ {description, vulnerabilite, reponse, objectif_controle, dispositif_controle}) : verrouille la version (`select_for_update`), calcule numéro/rang/code (D3), `priorite` par défaut `priorite_par_defaut(niveau_pour_score(p*i))`, objet d'un autre processus → `errors.objet_auditable` « L'objet auditable doit appartenir au processus du risque. ». `modifier_risque(risque, *, by, **changes)` (processus modifié → `errors.processus` « Le processus d'un risque ne peut pas être modifié. ») ; `supprimer_risque(risque, *, by)`.
  - `version_courante() -> CartographieVersion | None`.
  - `@dataclass(frozen=True) CelluleMatrice(probabilite: int, impact: int, score: int, niveau: str, nombre: int, codes: list[str])` ; `matrice(version) -> list[CelluleMatrice]` : 25 cases, probabilité 5 → 1 puis impact 1 → 5, codes triés par numéro, une seule requête.
  - `@dataclass RisqueModifie(code: str, changements: dict[str, tuple[str | None, str | None]])` ; `@dataclass Comparaison(ajoutes: list[Risque], retires: list[Risque], modifies: list[RisqueModifie])` ; `comparer_versions(reference, cible) -> Comparaison` : appariement par code, champs comparés libelle, description, probabilite, impact, score, niveau, vulnerabilite, reponse, priorite, objectif_controle, dispositif_controle, objet auditable (libellé) ; valeurs converties en `str`.

- [ ] **Step 1: Écrire les tests**
```python
def test_codes_attribues_par_processus(rai):
    v = CartographieVersionFactory()
    fep, gsi = ProcessusFactory(code="FEP"), ProcessusFactory(code="GSI")
    codes = [creer_risque(version=v, processus=p, libelle="x", probabilite=1, impact=1, by=rai).code
             for p in (fep, gsi, fep)]
    assert codes == ["1-FEP-R1", "2-GSI-R1", "3-FEP-R2"]

def test_risque_de_version_validee_immuable_meme_hors_service(rai):
    r = RisqueFactory(); valider_version(r.version, by=rai)
    with pytest.raises(CartographieFigeeError):
        modifier_risque(r, probabilite=2, by=rai)
    r.refresh_from_db(); r.libelle = "contournement"
    with pytest.raises(CartographieFigeeError):
        r.save()
```
Plus : `test_numero_supprime_jamais_reattribue` ; `test_priorite_par_defaut_depuis_niveau` (3×5 → 1) ; `test_valider_version_vide_refuse` ; `test_version_validee_ni_modifiable_ni_supprimable` ; `test_annee_deja_prise_422_sur_annee` ; `test_copie_conserve_les_codes_et_ignore_les_supprimes` ; `test_supprimer_brouillon_supprime_ses_risques` ; `test_supprimer_processus_avec_risque_actif_refuse` puis accepté après suppression du risque ; `test_supprimer_direction_rattachee_refuse` ; `test_code_non_modifiable` ; `test_operation_hors_processus_refusee` ; `test_objet_d_un_autre_processus_refuse` ; `test_matrice_version_vide_25_cases_a_zero` ; `test_matrice_regroupe_les_codes` (deux risques en (3, 5) → `nombre == 2`, niveau ELEVE, `assertNumQueries(1)`) ; `test_comparer_versions` (ajouté, retiré, `changements["probabilite"] == ("2", "4")`) ; `test_validation_historisee` (LogEntry avec `statut` BROUILLON → VALIDEE et l'acteur).
- [ ] **Step 2: `pytest tests/referentiel -v`** → FAIL.
- [ ] **Step 3: Implémenter** `exceptions.py`, `services.py`, la transition et les gardes `save()`.
- [ ] **Step 4: `pytest tests/referentiel -v`** → PASS ; `ruff check . && mypy .` → 0.
- [ ] **Step 5: Commit** `feat(referentiel): add services with numbering, freeze on validation, copy, matrix and comparison`.

### Task 3: API REST, permissions par rôle, filtres, contrat OpenAPI

**Model:** sonnet (backend-dev)

**Files:**
- Create: `backend/apps/referentiel/{permissions,filters,serializers,views,urls}.py`, `backend/apps/core/pagination.py`
- Modify: `backend/config/urls.py` (`path("api/v1/", include("apps.referentiel.urls"))`), `backend/config/settings/base.py` (`DEFAULT_PAGINATION_CLASS`, `SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"]`), `frontend/src/api/schema.d.ts` (régénéré)
- Test: `backend/tests/referentiel/conftest.py` (fixture `auth_rai` : `APIClient` authentifié avec la fixture `rai`, réutilisée en T4), `backend/tests/referentiel/test_api_permissions.py`, `test_api_structure.py`, `test_api_cartographies.py`, `test_api_risques.py`

**Interfaces:**
- Consumes: services et dataclasses (Task 2) ; `HasRole`, `Role` ; `apps.core.schema.ERROR_*`.
- Produces:
  - `core.pagination.StandardPagination` : `page_size=25`, `page_size_query_param="page_size"`, `max_page_size=200` (devient la pagination par défaut).
  - `referentiel.permissions.RolePermission` : lit `view.read_roles` / `view.write_roles` (tuples de `Role`) selon `SAFE_METHODS`. Constantes `TOUS_ROLES`, `LECTURE_CARTOGRAPHIE = (ADMIN, RAI, AUDITEUR, DG)`, `ECRITURE_STRUCTURE = (RAI, ADMIN)`, `ECRITURE_CARTOGRAPHIE = (RAI,)` (D4).
  - Les ViewSets n'ont aucune logique : `create`/`partial_update`/`destroy` appellent le service correspondant avec `serializer.validated_data` et `by=request.user`, puis renvoient le sérialiseur de lecture ; `destroy` → 204. Pas de `PUT` (`http_method_names` sans `put`).
  - Endpoints (filtres django-filter ; `q` = `icontains` sur code et libellé ; tri `ordering`) :

| Route | Méthodes | Filtres / tri | Droits |
|---|---|---|---|
| `/api/v1/directions/` `{id}/` | GET, POST, PATCH, DELETE | `type`, `parent`, `q` ; `code`, `libelle` | lecture tous, écriture RAI/ADMIN |
| `/api/v1/processes/` `{id}/` | idem | `famille`, `direction`, `q` ; `ordre`, `code` | idem |
| `/api/v1/auditable-objects/` `{id}/` | idem | `processus`, `parent`, `nature`, `q` | lecture cartographie, écriture RAI |
| `/api/v1/auditable-objects/tree/?processus=` | GET (non paginé ; 400 sans `processus`) | — | lecture cartographie |
| `/api/v1/risk-maps/` `{id}/` | GET, POST, PATCH, DELETE | `statut`, `annee` ; `annee` | lecture cartographie, écriture RAI |
| `/api/v1/risk-maps/{id}/validate/` | POST → 200 version | — | RAI |
| `/api/v1/risk-maps/{id}/matrix/` | GET | — | lecture cartographie |
| `/api/v1/risk-maps/{id}/compare/?with=` | GET (400 sans `with`) | — | lecture cartographie |
| `/api/v1/risks/` `{id}/` | GET, POST, PATCH, DELETE | `version`, `processus`, `objet_auditable`, `niveau`, `probabilite`, `impact`, `reponse`, `priorite`, `q` ; `numero`, `code`, `score` | lecture cartographie, écriture RAI |

  - Sérialiseurs explicites (noms = composants OpenAPI) : `DirectionSerializer` {id, code, libelle, type, parent, parent_code (lecture)} ; `ProcessusSerializer` {id, code, libelle, famille, ordre, directions (ids, écriture), directions_detail [{id, code, libelle}] (lecture)} ; `ObjetAuditableSerializer` {id, processus, parent, nature, libelle, description, ordre} ; `DomaineArbreSerializer` {id, libelle, description, ordre, operations: [ObjetAuditable]} ; `CartographieVersionSerializer` {id, annee, libelle, commentaire, statut (lecture), source (écriture à la création), validee_le, validee_par {id, username, nom_complet} (lecture), nb_risques (annotation), created_at} ; `RisqueSerializer` {id, version, version_annee, version_statut, processus, processus_code, objet_auditable, objet_auditable_libelle, numero, rang, code, score, niveau (lecture), libelle, description, probabilite, impact (`IntegerField(min_value=1, max_value=5)`), vulnerabilite, reponse, priorite (facultatif), objectif_controle, dispositif_controle, created_at, updated_at} ; `MatriceSerializer` {version, total, par_niveau {FAIBLE, MOYEN, ELEVE}, cellules: [CelluleMatrice]} ; `ComparaisonSerializer` {reference, cible, ajoutes, retires: [RisqueResume {id, code, libelle, score, niveau}], modifies: [{code, changements: {champ: [avant, après]}}]}.
  - `ENUM_NAME_OVERRIDES` : `TypeEntiteEnum`, `FamilleProcessusEnum`, `NatureObjetEnum`, `StatutCartographieEnum`, `NiveauRisqueEnum`, `ReponseRisqueEnum`, `PrioriteRisqueEnum`.
  - Chaque action documentée par `@extend_schema` avec `ERROR_400`, `ERROR_RESPONSES`, `ERROR_404`, `ERROR_422` selon le cas.

- [ ] **Step 1: Écrire les tests**
```python
@pytest.mark.parametrize("role,read,write", [
    ("ADMIN", 200, 403), ("RAI", 200, 201), ("AUDITEUR", 200, 403), ("AUDITE", 403, 403), ("DG", 200, 403)])
def test_droits_sur_les_risques(api_client, role, read, write):
    api_client.force_authenticate(make_user(role))
    v, p = CartographieVersionFactory(), ProcessusFactory(code="FEP")
    assert api_client.get("/api/v1/risks/").status_code == read
    body = {"version": str(v.id), "processus": str(p.id), "libelle": "Rupture", "probabilite": 3, "impact": 5}
    assert api_client.post("/api/v1/risks/", body, format="json").status_code == write
```
Même matrice paramétrée pour `directions`, `processes` (écriture ADMIN et RAI 201), `auditable-objects`, `risk-maps` et `validate`. Plus : `test_probabilite_hors_bornes_400` (6, 0, "abc", null → 400 et `"probabilite" in errors`) ; `test_modifier_risque_valide_422` (`detail` = message de gel) ; `test_supprimer_processus_avec_risques_422` ; `test_filtre_case_matrice` (`?version=&probabilite=3&impact=5` ne renvoie que ces risques) ; `test_matrix_renvoie_25_cellules` ; `test_compare_sans_with_400` ; `test_tree_imbrique_operations` ; `test_page_size_plafonne_a_200` ; `test_liste_risques_requetes_bornees` (`django_assert_max_num_queries(3)` pour 30 risques) ; `test_risque_supprime_absent_de_la_liste` ; `test_schema_expose_les_routes_referentiel` (`/api/schema/` contient `/api/v1/risks/` et `/api/v1/risk-maps/{id}/matrix/`).
- [ ] **Step 2: `pytest tests/referentiel -v`** → FAIL.
- [ ] **Step 3: Implémenter** pagination, permission, filtres, sérialiseurs, ViewSets (`select_related("version", "processus", "objet_auditable")`, `prefetch_related("directions")`), routeur `SimpleRouter`.
- [ ] **Step 4: `pytest -v`** → PASS (lot 1 compris) ; `sh scripts/gen-api.sh` puis `sh scripts/check-api-fresh.sh` → « OK » après commit du fichier ; `ruff check . && mypy .` → 0.
- [ ] **Step 5: Commit** `feat(referentiel): expose role-gated rest api for reference data and risk maps`.

### Task 4: Export CSV/XLSX et commande `import_referentiel`

**Model:** sonnet (backend-dev)

**Files:**
- Create: `backend/apps/referentiel/{exports,imports}.py`, `backend/apps/referentiel/management/{__init__,commands/__init__,commands/import_referentiel}.py`, `backend/apps/referentiel/data/referentiel-onea.csv`
- Modify: `backend/apps/referentiel/views.py` (action `export`), `backend/pyproject.toml` (`openpyxl>=3.1` ; dev `types-openpyxl`), `frontend/src/api/schema.d.ts` (régénéré)
- Test: `backend/tests/referentiel/test_exports.py`, `backend/tests/referentiel/test_import_referentiel.py`

**Interfaces:**
- Consumes: modèles, `matrice()`, services `creer_*`/`modifier_*` (Task 2), `RolePermission` (Task 3).
- Produces:
  - `exports.COLONNES` (ordre figé) : Code ; Processus ; Objet auditable ; Risque ; Description ; Probabilité ; Impact ; Score ; Niveau ; Vulnérabilité ; Réponse ; Priorité ; Objectif de contrôle ; Dispositif de contrôle interne. Valeurs d'énumération exportées par leur libellé français.
  - `exports.neutraliser_formule(valeur: str) -> str` ; `exporter_csv(version) -> bytes` (BOM UTF-8, `;`, `\r\n`) ; `exporter_xlsx(version) -> bytes` (feuille « Risques » : en-tête gras, volets figés en A2, filtre automatique ; feuille « Matrice » : 5×5, probabilité 5 → 1 en lignes, impact 1 → 5 en colonnes, codes séparés par des retours à la ligne, remplissages #CFE8D8 / #FFE8B3 / #F8C9C4 de la charte, titres d'axes « Probabilité » et « Impact » ; propriété `creator` « ONEA — Département Audit Interne ») ; `nom_fichier(version, extension) -> str` → `cartographie-2026.csv`, `cartographie-2026-brouillon.xlsx`.
  - `GET /api/v1/risk-maps/{id}/export/?type=csv|xlsx` (lecture cartographie) → 200, `Content-Type` `text/csv; charset=utf-8` ou `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `Content-Disposition: attachment; filename="…"` ; `type` absent ou inconnu → 400 `errors.type` ; schéma `OpenApiTypes.BINARY`. **Contrat consommé par T7.**
  - `imports.importer_referentiel(flux: TextIO, *, by: User, dry_run: bool = False) -> RapportImport` ; `@dataclass RapportImport(crees: dict[str, int], mis_a_jour: dict[str, int], inchanges: int)` ; `ImportReferentielError(erreurs: list[str])`. Format CSV : UTF-8 (BOM toléré), séparateur `;`, en-tête exact `type;code;libelle;famille;ordre;parent;directions` ; `type` ∈ DIRECTION, DEPARTEMENT, PROCESSUS ; `parent` = code de direction (départements) ; `directions` = codes séparés par `,` (processus) ; `famille` sans tenir compte de la casse ni des accents. Traitement en trois passes (directions, départements, processus), upsert par code actif via les services, rien n'est supprimé ; toute erreur annule tout. Messages : « Ligne 12 : code « ÉST » invalide. », « Fichier trop volumineux : 5 000 lignes au maximum. », « Encodage invalide : enregistrez le fichier en UTF-8. », « En-tête attendu : type;code;libelle;famille;ordre;parent;directions ». `csv.Error` (champ trop long) converti en message ligné.
  - Commande `import_referentiel <chemin> --user <login> [--dry-run]` : refuse un utilisateur ni RAI ni ADMIN, exécute sous `auditlog.context.set_actor(user)`, affiche « Directions : 17 créées, 0 mises à jour… », code de sortie 1 et liste des erreurs en cas d'échec ; `--dry-run` n'écrit rien.
  - `data/referentiel-onea.csv` : les 17 directions et 11 processus de `docs/domaine/cartographie-risques-onea.md`, libellés accentués (D1).

- [ ] **Step 1: Écrire les tests**
```python
def test_csv_conserve_les_accents_et_neutralise_les_formules(auth_rai):
    r = RisqueFactory(libelle="Défaillance du réseau d'eau – Ouagadougou", description="=HYPERLINK(\"x\")")
    resp = auth_rai.get(f"/api/v1/risk-maps/{r.version_id}/export/?type=csv")
    assert resp["Content-Disposition"].endswith('-brouillon.csv"')
    texte = resp.content.decode("utf-8")
    assert texte.startswith("﻿Code;Processus;")
    assert "Défaillance du réseau d'eau – Ouagadougou" in texte and ";'=HYPERLINK" in texte

def test_import_deux_fois_est_idempotent(rai):
    with open(REF_CSV, encoding="utf-8-sig") as f: importer_referentiel(f, by=rai)
    with open(REF_CSV, encoding="utf-8-sig") as f: rapport = importer_referentiel(f, by=rai)
    assert sum(rapport.crees.values()) == 0 and sum(rapport.mis_a_jour.values()) == 0
    assert Processus.objects.count() == 11 and Direction.objects.count() == 17
```
Plus : `test_xlsx_deux_feuilles_et_matrice` (rechargé par `openpyxl.load_workbook` : feuilles « Risques » et « Matrice », la case (P 3, I 5) contient le code) ; `test_export_type_invalide_400` ; `test_export_interdit_a_l_audite` ; `test_import_5001_lignes_refuse_sans_ecriture` ; `test_import_cp1252_refuse` ; `test_import_en_tete_incorrect` ; `test_import_erreur_ligne_annule_tout` (ligne 3 invalide → aucune direction créée, message « Ligne 3 : ») ; `test_import_dry_run_n_ecrit_rien` ; `test_commande_refuse_un_auditeur` (`call_command` → `CommandError`) ; `test_import_historise_avec_l_acteur`.
- [ ] **Step 2: `pytest tests/referentiel -v`** → FAIL.
- [ ] **Step 3: Implémenter** `exports.py`, l'action `export` (réponse `HttpResponse`, pas de renderer DRF), `imports.py`, la commande, le fichier de référence ; installer `openpyxl`.
- [ ] **Step 4: `pytest -v`** → PASS ; `python manage.py import_referentiel apps/referentiel/data/referentiel-onea.csv --user rai --dry-run` sur la base de dev → résumé sans écriture ; `sh scripts/gen-api.sh && sh scripts/check-api-fresh.sh` → OK ; `ruff check . && mypy .` → 0.
- [ ] **Step 5: Commit** `feat(referentiel): add csv/xlsx risk map export and idempotent import_referentiel command`.

### Task 5: Fondations frontend du Référentiel

**Model:** sonnet (frontend-dev). **Dépend uniquement du `schema.d.ts` de T3** (peut tourner en parallèle de T4).

**Files:**
- Create: `frontend/src/api/query.ts`, `frontend/src/lib/download.ts`, `frontend/src/components/DataTable.tsx`, `frontend/src/components/ui/{select,textarea,tabs,alert-dialog,checkbox}.tsx` (`npx shadcn add`), `frontend/src/features/referentiel/{api,types,permissions,labels}.ts`, `frontend/src/features/referentiel/components/{ReferentielLayout,RiskLevelBadge,VersionStatusBadge}.tsx`, `frontend/src/features/referentiel/routes.tsx`, `frontend/src/features/referentiel/pages/*.tsx` (squelettes nommés ci-dessous)
- Modify: `frontend/src/api/client.ts` (`apiDownload`), `frontend/src/components/RiskMatrix.tsx`, `frontend/src/components/EmptyState.tsx` (emplacement `children` pour actions actives), `frontend/src/i18n/fr.ts`, `frontend/src/routes.tsx`, `frontend/src/layouts/navigation.ts` (`SEGMENT_LABELS`), `frontend/src/layouts/Breadcrumbs.tsx`
- Test: `frontend/src/components/RiskMatrix.test.tsx`, `frontend/src/components/DataTable.test.tsx`, `frontend/src/api/client.test.ts`, `frontend/src/api/query.test.ts`, `frontend/src/features/referentiel/{permissions,api}.test.ts(x)`, `frontend/src/layouts/Breadcrumbs.test.tsx`, `frontend/src/routes.test.tsx`

**Interfaces:**
- Consumes: `components["schemas"]` de T3 (`Direction`, `Processus`, `ObjetAuditable`, `DomaineArbre`, `CartographieVersion`, `Risque`, `Matrice`, `Comparaison`, `Paginated…List`, énumérations `…Enum`) ; contrat d'export de T4 ; `apiFetch`, `useRole`, `rolesFor` (lot 1).
- Produces:
  - `toQuery(params: Record<string, string | number | null | undefined>) -> string` (omet vides, encode, préfixe `?`).
  - `apiDownload(path: string) -> Promise<{ blob: Blob; filename: string }>` (même en-tête Bearer et même `ApiError` que `apiFetch` ; nom lu dans `Content-Disposition`, `filename*=UTF-8''` prioritaire) ; `downloadBlob(blob, filename): void`.
  - `DataTable<T>` props `{ caption: string; columns: ColumnDef<T>[]; data: T[]; total: number; page: number; pageSize: number; onPageChange(page: number): void; ordering?: string; onOrderingChange?(o: string): void; isLoading: boolean; empty: ReactNode }` : pagination et tri serveur (`manualPagination`, `manualSorting`), lignes 44 px, en-tête collant, chiffres tabulaires, squelettes au chargement, « Page 1 sur 3 », boutons « Page précédente » / « Page suivante ».
  - `RiskMatrix` étendu, rétrocompatible : `RiskMatrixCell` gagne `codes?: string[]` ; nouvelles props `onSelect?(cell: { probability; impact }): void`, `selected?: { probability; impact } | null`, `size?: "compact" | "large"` (compact = rendu actuel). Avec `onSelect`, chaque case est un `<button aria-pressed>` au même `aria-label`.
  - `features/referentiel/api.ts` : `referentielKeys` (racine `["referentiel"]`) et hooks `useDirections(params)`, `useSaveDirection()`, `useDeleteDirection()`, `useProcesses(params)`, `useProcess(id)`, `useSaveProcess()`, `useDeleteProcess()`, `useAuditableTree(processId?)`, `useSaveAuditableObject()`, `useDeleteAuditableObject()`, `useRiskMaps(params)`, `useRiskMap(id)`, `useCreateRiskMap()`, `useUpdateRiskMap()`, `useValidateRiskMap()`, `useDeleteRiskMap()`, `useRiskMatrix(id)`, `useRiskMapComparison(id, withId?)`, `useRisks(params)`, `useRisk(id)`, `useSaveRisk()`, `useDeleteRisk()`, `exportRiskMap(id, type: "csv" | "xlsx"): Promise<void>`. Les mutations `useSave*` prennent `{ id?: string; data }` (POST sans id, PATCH sinon). Sauver/supprimer un risque invalide `risks`, la matrice et la liste des versions.
  - `permissions.ts` : `canEditStructure(role)` (RAI, ADMIN) ; `canEditCartographie(role)` (RAI).
  - `labels.ts` : libellés français des énumérations (D7 et Task 1) et `levelFromNiveau(n: NiveauRisqueEnum): RiskLevel`.
  - `RiskLevelBadge` (pastille + texte foncé sur `bg-risk-*`), `VersionStatusBadge` (Brouillon : `warning-text` ; Validée : `success-text`).
  - `fr.ts` : section `referentiel` (onglets « Cartographies », « Processus », « Directions », « Objets auditables » ; libellés de champs : Code, Libellé, Famille, Ordre, Directions rattachées, Type, Direction de rattachement, Nature, Domaine, Opération, Année, Statut, Probabilité, Impact, Score, Niveau, Vulnérabilité, Réponse au risque, Priorité, Objectif de contrôle, Dispositif de contrôle interne ; « Exporter en CSV », « Exporter en Excel ») et deux sections vides `refStructure: {}` et `refCartographie: {}` placées à des endroits distincts du fichier, remplies par T6 et T7 sans conflit.
  - `features/referentiel/routes.tsx` exporte `referentielRoutes: RouteObject[]`, monté dans `routes.tsx` sous `guarded("/referentiel", <ReferentielLayout />)` : index → `Navigate` vers `cartographies` ; `cartographies` → `RiskMapListPage` ; `cartographies/:id` → `RiskMapDetailPage` ; `cartographies/:id/comparer` → `RiskMapComparePage` ; `risques/nouveau` et `risques/:id` → `RiskFormPage` ; `processus` → `ProcessListPage` ; `processus/nouveau` et `processus/:id` → `ProcessFormPage` ; `directions` → `DirectionsPage` ; `objets-auditables` → `AuditableObjectsPage`. Chaque page est créée ici en squelette (titre seul) : T6 et T7 n'éditent que leurs pages.
  - `ReferentielLayout` : titre « Référentiel », onglets en `NavLink` (`aria-current`), `<Outlet />`.
  - `SEGMENT_LABELS` : cartographies, risques, processus, directions, objets-auditables, nouveau (« Nouveau »), comparer (« Comparaison ») ; `Breadcrumbs` affiche « Détail » pour un segment UUID.

- [ ] **Step 1: Écrire les tests** : `RiskMatrix` avec `onSelect` — clic sur la case « Probabilité 3, impact 5 : 2 risques, élevé » appelle `onSelect({probability: 3, impact: 5})`, la case `selected` a `aria-pressed="true"`, et sans `onSelect` aucun bouton (tests existants verts) ; `DataTable` — légende, pagination, `empty` affiché quand `data` est vide hors chargement ; `apiDownload` lit `filename*=UTF-8''cartographie-2026.csv` et lève `ApiError` 403 ; `toQuery({a: 1, b: undefined, q: "é"}) === "?a=1&q=%C3%A9"` ; `canEditCartographie("ADMIN") === false`, `canEditStructure("ADMIN") === true` ; fil d'Ariane de `/referentiel/cartographies/<uuid>` = « Tableau de bord › Référentiel › Cartographies › Détail » ; routes : un AUDITE sur `/referentiel/cartographies` voit `fr.errors.forbidden`, un RAI sur `/referentiel` arrive sur `/referentiel/cartographies` ; `useRisks` appelle `/api/v1/risks/?version=…&probabilite=3&impact=5` (MSW).
- [ ] **Step 2: `cd frontend && npm test`** → FAIL.
- [ ] **Step 3: Implémenter** les modules, composants et routes ci-dessus.
- [ ] **Step 4: `npm test && npm run typecheck && npm run lint && npm run format:check`** → PASS, 0 erreur.
- [ ] **Step 5: Commit** `feat(frontend): add referentiel api hooks, data table, interactive risk matrix and routes`.

### Task 6: Écrans Processus, Directions, Objets auditables

**Model:** sonnet (frontend-dev), en parallèle de T7.

**Files:**
- Modify: `frontend/src/features/referentiel/pages/{ProcessListPage,ProcessFormPage,DirectionsPage,AuditableObjectsPage}.tsx`, `frontend/src/i18n/fr.ts` (section `refStructure` seulement)
- Create: `frontend/src/features/referentiel/schemas/{process,direction,auditableObject}.ts`, `frontend/src/features/referentiel/components/{DirectionFormDialog,AuditableObjectFormDialog,ConfirmDeleteDialog}.tsx`
- Test: `frontend/src/features/referentiel/pages/{ProcessListPage,ProcessFormPage,DirectionsPage,AuditableObjectsPage}.test.tsx`

**Interfaces:**
- Consumes: hooks, `DataTable`, `EmptyState`, `permissions`, `labels`, squelettes de pages (Task 5).
- Produces:
  - `ProcessListPage` : `DataTable` (Code, Processus, Famille, Directions rattachées, Ordre), filtre famille et recherche reflétés dans l'URL ; bouton « Créer un processus » si `canEditStructure`. État vide RAI/ADMIN : « Aucun processus n'est encore enregistré. » + action « Créer un processus » + aide « La liste de référence ONEA peut aussi être chargée par l'administrateur (commande import_referentiel). » ; AUDITEUR : « Aucun processus n'a encore été saisi par le Responsable de l'audit interne. ».
  - `ProcessFormPage` (création / modification) : zod `code` `^[A-Z]{2,5}$` (« Deux à cinq lettres majuscules, sans accent. »), libellé requis (200), famille, ordre ≥ 0, directions (cases à cocher) ; code désactivé en modification ; erreurs 400/422 posées sur les champs par `setError`, `detail` sinon en alerte ; « Supprimer le processus » via `ConfirmDeleteDialog` qui affiche le `detail` 422 sans fermer ; en lecture seule pour AUDITEUR et DG.
  - `DirectionsPage` : tableau des directions avec leurs départements indentés sous elles ; `DirectionFormDialog` (code `^[A-Z][A-Z0-9-]{1,15}$`, libellé, type, direction de rattachement obligatoire pour un département).
  - `AuditableObjectsPage` : sélecteur de processus (paramètre d'URL `processus`), arbre domaine → opérations en listes imbriquées titrées ; « Ajouter un domaine » / « Ajouter une opération » / modifier / supprimer via `AuditableObjectFormDialog` (RAI seul) ; état vide sans processus sélectionné et sans domaine.
  - Les pages de liste et l'arbre s'impriment sans boutons (`print:hidden` sur les actions).

- [ ] **Step 1: Écrire les tests** (MSW, `renderRoutes` du lot 1) : liste vide pour RAI → bouton « Créer un processus » ; pour AUDITEUR → message sans bouton ; création envoie `{"code": "FEP", "libelle": "Fournir l'eau potable", "famille": "REALISATION", "ordre": 4, "directions": [id]}` ; code « ést » bloqué côté client ; 422 « Ce processus porte des risques… » affiché dans la boîte de confirmation ; département sans direction refusé ; arbre rendu avec un domaine et deux opérations ; `axe` sans violation sur chaque page.
- [ ] **Step 2: `npm test`** → FAIL.
- [ ] **Step 3: Implémenter** pages, schémas, boîtes de dialogue, libellés `refStructure`.
- [ ] **Step 4: `npm test && npm run typecheck && npm run lint`** → PASS ; revue visuelle `ui-designer` (check-list `charte-graphique`) : 0 correction majeure.
- [ ] **Step 5: Commit** `feat(frontend): add process, direction and auditable object screens`.

### Task 7: Écrans Cartographie, Risques, Matrice, Comparaison, Export

**Model:** sonnet (frontend-dev), en parallèle de T6.

**Files:**
- Modify: `frontend/src/features/referentiel/pages/{RiskMapListPage,RiskMapDetailPage,RiskMapComparePage,RiskFormPage}.tsx`, `frontend/src/i18n/fr.ts` (section `refCartographie` seulement)
- Create: `frontend/src/features/referentiel/schemas/{riskMap,risk}.ts`, `frontend/src/features/referentiel/components/{CreateRiskMapDialog,ValidateRiskMapDialog,RiskFilters,ExportButtons,FrozenBanner}.tsx`
- Test: `frontend/src/features/referentiel/pages/{RiskMapListPage,RiskMapDetailPage,RiskMapComparePage,RiskFormPage}.test.tsx`

**Interfaces:**
- Consumes: hooks, `exportRiskMap`, `RiskMatrix` interactif, `DataTable`, badges, `labels`, `permissions` (Task 5) ; contrat d'export (Task 4).
- Produces:
  - `RiskMapListPage` : tableau (Année, Libellé, Statut, Nombre de risques, Validée le, Validée par) ; « Créer une cartographie » (RAI) → `CreateRiskMapDialog` (année par défaut l'année en cours, libellé « Cartographie des risques {année} », « Copier les risques de » facultatif) ; 422 sur `annee` posé sur le champ. État vide RAI : « Aucune cartographie des risques n'a encore été créée. » + action ; autres rôles : explication.
  - `RiskMapDetailPage` : en-tête « Cartographie des risques 2026 » + `VersionStatusBadge` ; actions RAI sur brouillon : « Ajouter un risque » (→ `risques/nouveau?cartographie=<id>`), « Valider la cartographie » (`ValidateRiskMapDialog` : « Une fois validée, la cartographie est figée : aucun risque ne pourra plus être ajouté, modifié ou supprimé. » ; 422 affiché dans la boîte) ; pour tous : `ExportButtons` (CSV, Excel ; erreur affichée sans quitter la page) et « Comparer avec… » (liste des autres versions → `comparer?avec=`). Version validée : `FrozenBanner` « Cartographie validée le JJ/MM/AAAA par {nom} : lecture seule. ». Corps : `RiskMatrix size="large"` alimentée par `useRiskMatrix` ; un clic sur une case pose `?probabilite=&impact=` dans l'URL, filtre le tableau et affiche « Probabilité 3 × impact 5 · Effacer le filtre » ; `RiskFilters` (processus, niveau, recherche) ; colonnes Code, Risque, Processus, P, I, Score, Niveau (badge), Réponse, Priorité. Impression : matrice et tableau sans actions.
  - `RiskFormPage` : processus (désactivé en modification), objet auditable (filtré par processus, facultatif), libellé (500, requis), description, probabilité et impact (sélecteurs 1–5), aperçu « Score 15 · Élevé » calculé par `riskLevel`, vulnérabilité, réponse, priorité (pré-remplie depuis le niveau tant que l'utilisateur ne l'a pas changée), objectif de contrôle, dispositif de contrôle interne ; code affiché en lecture après création ; version validée ou rôle sans écriture : tous les champs désactivés, aucun bouton d'enregistrement ; suppression (RAI, brouillon) puis retour à la cartographie.
  - `RiskMapComparePage` : sélecteur de la version cible, sections « Risques ajoutés », « Risques retirés », « Risques modifiés » (Champ, Avant, Après) ; état vide « Aucune différence entre les deux cartographies. ».

- [ ] **Step 1: Écrire les tests** (MSW) : clic sur la case (3, 5) → requête `…&probabilite=3&impact=5` et seule la ligne `12-FEP-R1` affichée, puis « Effacer le filtre » rétablit la liste ; version validée → bannière, pas de « Ajouter un risque » ni « Valider », formulaire de risque entièrement désactivé ; AUDITEUR sur brouillon → aucun bouton d'écriture mais export présent ; validation d'une version vide → message 422 dans la boîte ; « Exporter en Excel » appelle `/export/?type=xlsx` ; probabilité 4 × impact 4 → aperçu « Score 16 · Élevé » et priorité « Prioritaire » ; liste vide RAI → action « Créer une cartographie » ; comparaison sans différence → état vide ; `axe` sans violation.
- [ ] **Step 2: `npm test`** → FAIL.
- [ ] **Step 3: Implémenter** pages, schémas, composants, libellés `refCartographie`.
- [ ] **Step 4: `npm test && npm run typecheck && npm run lint`** → PASS ; revue visuelle `ui-designer` (matrice à l'écran et en impression) : 0 correction majeure.
- [ ] **Step 5: Commit** `feat(frontend): add risk map, risk, matrix, comparison and export screens`.

### Task 8: Parcours e2e RAI, documentation, vérification du lot

**Model:** sonnet (test-engineer).

**Files:**
- Create: `frontend/e2e/referentiel.spec.ts`, `frontend/e2e/api.ts`
- Modify: `backend/README.md` (section « Référentiel : chargement initial »), `frontend/src/i18n/fr.ts` (`shell.version` → « Version 0.2 · lot 2 »), `frontend/e2e/login.spec.ts` seulement si le libellé de version y est vérifié

**Interfaces:**
- Consumes: tout le lot ; client Keycloak de dev `onea-dev-cli` (password grant, dev seulement) ; comptes `rai` / `onea2026`.
- Produces: `e2e/api.ts` : `devToken(username): Promise<string>` et `cleanupReferentiel(token)` qui supprime logiquement, s'ils existent, la cartographie 2099 (brouillon) puis le processus `ZZE`. Le parcours n'utilise pas la validation (une version validée est indestructible, D2) ; le gel est couvert par les tests des tâches 2, 3 et 7.

- [ ] **Step 1: Écrire `referentiel.spec.ts`** : `beforeAll` → `cleanupReferentiel` ; le RAI se connecte, ouvre Référentiel › Processus, crée `ZZE` « Processus de test e2e » (famille Support) ; ouvre Cartographies, crée la cartographie 2099 ; ajoute le risque « Risque de test e2e » sur `ZZE`, probabilité 3, impact 5 ; sur la page de la cartographie, la case « Probabilité 3, impact 5 » affiche 1 ; un clic filtre le tableau qui montre `1-ZZE-R1` et « Élevé » ; nettoyage par l'interface : suppression de la cartographie puis du processus, chacun disparaissant de sa liste.
- [ ] **Step 2: `make up && make backend` puis `cd frontend && npx playwright test e2e/referentiel.spec.ts`** → FAIL tant que la spec n'est pas finalisée, puis PASS ; relancer une seconde fois → PASS (idempotence).
- [ ] **Step 3: Documenter** dans `backend/README.md` : usage de `import_referentiel` (`--user`, `--dry-run`), format CSV avec un exemple de trois lignes, rappel « démarrage à vide : aucun risque n'est importé » ; mettre à jour la version affichée.
- [ ] **Step 4: Vérification complète** : `make lint && make test && make check-api && make e2e` → tout vert ; `python manage.py makemigrations --check --dry-run` → aucun changement ; couverture backend ≥ 85 %, frontend ≥ 80 %.
- [ ] **Step 5: Commit** `test(e2e): cover rai referentiel flow; docs: document import_referentiel`.

---

## Critère de fin du lot 2

Sur une base vide : `import_referentiel` charge 17 directions et 11 processus, une seconde exécution ne change rien ; le RAI crée objets auditables, une cartographie, des risques, voit la matrice, filtre par case, exporte en CSV et en Excel, valide la cartographie qui devient non modifiable, crée l'année suivante par copie et compare les deux versions ; l'AUDITEUR et le DG lisent sans pouvoir écrire, l'AUDITE reçoit 403 ; chaque action apparaît dans `/api/v1/audit-log/` ; `make lint && make test && make check-api && make e2e` verts.
