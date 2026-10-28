# Lot 3 — Mission et stepper : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer la conduite d'une mission jusqu'à la fin de l'étape IV : création par le RAI à partir de la cartographie validée, affectations (chef de mission, auditeurs, superviseur, audités), déclarations d'indépendance confirmées et horodatées, cycle de vie de la mission, stepper des 18 étapes IFACI avec ses règles (terminer, valider, renvoyer, rouvrir, non applicable), fiche de suivi, réunions, entretiens et cartographie des risques de la mission, avec les écrans français correspondants.

**Architecture:** Deux nouvelles apps Django : `apps.signatures` (mode « confirmation » : enregistrement immuable, horodaté, empreinte SHA-256) et `apps.missions` (modèles sur `BaseModel`, registre des 18 étapes dans `etapes.py`, droits calculés par une seule source `acces.py` + `droits_mission` / `actions_possibles`, logique dans le paquet `services/`, gardes de gel dans les services **et** dans `save()` / QuerySets). Les ViewSets DRF exposent des routes plates sous `/api/v1/` ; chaque réponse de mission et d'étape porte les droits calculés par le serveur, que le frontend (`src/features/missions/`) affiche sans les recalculer. Le contrat OpenAPI est figé à la fin de la tâche 5.

**Tech Stack:** existants des lots 1 et 2 (Django 5.1, DRF, drf-spectacular, django-filter, django-fsm, django-auditlog, pytest, factory_boy ; React 19, TanStack Query 5 / Table, react-hook-form + zod, shadcn/ui, Vitest, MSW, Playwright). **Aucune nouvelle dépendance** (`hashlib`, `json` de la bibliothèque standard ; `django.contrib.contenttypes` déjà installé).

**Spec:** `docs/superpowers/specs/2026-10-27-plateforme-audit-interne-design.md` (§5 rôles, §6.2 Missions, §7 modèle, §8 workflow, §9 interface, §11 lot 3, §14 « Validations et jalons », « Séquencement du stepper », « Confidentialité », « Cartographie », §15.1 signature « confirmation » livrée au lot 3) ; `docs/domaine/processus-ifaci.md` (fiches étapes I à XVIII, outil I « Entretien ») ; `docs/domaine/documents-mission.md` ; `docs/domaine/normes-iia-sommaire.md` (2.1–2.3, 5.2, 12.x, 14.6) ; `docs/design/charte-graphique.md` (« Stepper de mission »).

**Prérequis :** la vague de corrections finale du lot 2 (`.superpowers/sdd/2026-10-28-lot2-referentiel/final-review.md`, I1, I2, M1–M10) est fusionnée sur la branche de base. Le lot 3 ne s'appuie que sur `version_courante()`, `Risque`, `Processus`, `Direction`, `CelluleMatrice`, `CelluleMatriceSerializer`, `RolePermission`, `RiskMatrix`, `DataTable`, `EmptyState` ; il référence un risque de cartographie **par clé étrangère**, jamais par son code (I2).

## Global Constraints

- Aucune fonctionnalité IA / LLM ; dépendances open source uniquement (liste de `CLAUDE.md`) ; **aucune nouvelle dépendance** backend ni frontend dans ce lot.
- Interface, messages d'erreur, textes de confirmation en français, vouvoiement, boutons à l'infinitif ; identifiants, routes d'API et commits en anglais (Conventional Commits).
- Rôles globaux exactement `ADMIN`, `RAI`, `AUDITEUR`, `AUDITE`, `DG` ; rôles dans la mission `CHEF_MISSION`, `AUDITEUR`, `SUPERVISEUR`, `AUDITE`. Matrice des droits : D4. Les droits ne sont calculés qu'à un endroit (`apps/missions/acces.py` + `droits_mission` + `actions_possibles`) ; vues, sérialiseurs et frontend les consomment.
- Toute entité hérite de `core.models.BaseModel` et est enregistrée via `core.audit.register` (M2M déclarés dans `m2m_fields`) ; jamais de suppression physique ; unicités conditionnées par `deleted_at IS NULL` sauf la référence de mission (jamais réutilisée).
- Format d'erreur unique `{"detail": str, "errors": {champ: [messages]}}` ; 400 validation de sérialiseur, 403 droit refusé, 404 mission invisible pour l'utilisateur (ne révèle pas son existence), 422 (`RegleMetierError`) règle métier.
- Statuts de mission (§8) : `BROUILLON, PLANIFIEE, EN_PLANIFICATION, EN_ACCOMPLISSEMENT, EN_COMMUNICATION, RAPPORT_DIFFUSE, EN_SUIVI, CLOTUREE, SUSPENDUE, ANNULEE`. Statuts d'étape : `A_FAIRE, EN_COURS, TERMINEE, VALIDEE, RENVOYEE, A_REVALIDER, NON_APPLICABLE`.
- Phases IFACI : Planification I–X, Accomplissement XI–XIV, Communication XV–XVIII ; jalons RAI **VI, X, XIII, XVIII** ; superviseur délégué : VI, X, XIII seulement ; le valideur n'est jamais l'auteur.
- Dates prévues en `DateField` (dates calendaires) ; horodatages en UTC ; « aujourd'hui » calculé en `Africa/Ouagadougou` ; affichage `JJ/MM/AAAA` via `lib/dates.ts`.
- Probabilité et impact dans [1, 5] (CHECK en base) ; score = produit (colonne générée) ; niveaux FAIBLE 1–7, MOYEN 8–14, ÉLEVÉ 15–25 (réutiliser `referentiel.scoring`).
- Tests backend sur PostgreSQL réel ; couverture 85 % backend, 80 % frontend ; `django_assert_max_num_queries` sur chaque liste.
- `frontend/src/api/schema.d.ts` régénéré par `sh scripts/gen-api.sh` et vérifié par `sh scripts/check-api-fresh.sh` à chaque tâche qui touche l'API.
- Charte : tokens CSS uniquement, aucune couleur hexadécimale dans un composant ; statuts en texte **et** couleur ; impression propre (`print:hidden` sur les actions).
- Version affichée et versions techniques alignées : `0.3.0` dans `backend/config/__init__.py`, `backend/pyproject.toml`, `frontend/package.json`, et « Version 0.3 · lot 3 » dans `fr.ts` (leçon M5 du lot 2).

## Décisions (prises par le rédacteur du plan ; « à confirmer avec ONEA » = hypothèse métier)

- **D1 — Périmètre.** Livrés : mission, affectations, déclarations, cycle de vie, 18 étapes et leur moteur, fiche de suivi, réunions (ouverture, lancement, clôture), entretiens, risques de mission (étape IV), confirmation horodatée. Différés : génération des documents Word/PDF (ordre de mission, PV, fiche de suivi, planning des entretiens) au lot 4 ; écran de paramétrage du mode de signature et signature PAdES au lot 7 bis ; livrables des étapes III et V à XVIII aux lots 5–7 (D7). Les transitions `RAPPORT_DIFFUSE`, `EN_SUIVI`, `CLOTUREE` sont déclarées dans l'énumération mais implémentées aux lots 7 et 8.
- **D2 — Cycle de vie de la mission.** `BROUILLON` (saisie RAI) → `planifier` → `PLANIFIEE` (inscrite au programme, référence attribuée) → `lancer` → `EN_PLANIFICATION` (étape I passe EN_COURS). Changements de phase **automatiques** dans le service qui remplit la dernière condition : → `EN_ACCOMPLISSEMENT` quand les étapes I–X sont closes (TERMINEE, VALIDEE ou NON_APPLICABLE), X VALIDEE et aucune étape I–X `RENVOYEE`/`A_REVALIDER` ; → `EN_COMMUNICATION` quand XI–XIV sont closes, XIII VALIDEE et aucune étape I–XIV `RENVOYEE`/`A_REVALIDER` (réconciliation de §8 et §14, voir contradictions). `suspendre` (motif) depuis PLANIFIEE, EN_PLANIFICATION, EN_ACCOMPLISSEMENT, EN_COMMUNICATION ; `reprendre` revient à `statut_avant_suspension` ; `annuler` (motif) depuis PLANIFIEE et les trois phases, définitif. Seul un BROUILLON se supprime (logiquement). Une mission SUSPENDUE, ANNULEE ou CLOTUREE refuse **toute** écriture sur elle-même et ses objets (422).
- **D3 — Référence de mission** `DAI/{annee}/M{numero:02d}` (ex. `DAI/2026/M07`, `M100` au-delà de 99), attribuée à `planifier`, `annee` = année de `date_debut_prevue`, `numero` = max des numéros de l'année (missions supprimées et annulées incluses) + 1 sous `pg_advisory_xact_lock(LOCK_REFERENCE_MISSION)` ; jamais réattribuée ni modifiable. Le format paramétrable des documents reste au lot 4. *À confirmer avec ONEA* (format et année de rattachement).
- **D4 — Droits.** Source unique `apps/missions/acces.py` :

| Action | Qui |
|---|---|
| Voir une mission | RAI : toutes ; AUDITEUR : missions où il est CHEF_MISSION/AUDITEUR/SUPERVISEUR, hors BROUILLON ; AUDITE : missions où il est affecté AUDITE, une fois l'ordre de mission émis ; **ADMIN et DG : aucune (403)**. Mission non visible → 404. |
| Créer, modifier, planifier, lancer, émettre l'ordre, suspendre, reprendre, annuler, supprimer, affecter, désaffecter, remplacer le chef, arbitrer un conflit | RAI |
| Confirmer une déclaration | l'auditeur concerné seulement |
| Démarrer une étape ; créer/modifier/supprimer réunions, entretiens, risques de mission | RAI ou intervenant (CHEF/AUDITEUR/SUPERVISEUR) **dont la déclaration est confirmée ou arbitrée** ; sinon 403 « Confirmez votre déclaration d'indépendance avant de contribuer à la mission. » |
| Terminer une étape (sauf I), non applicable, rétablir | chef de mission (déclaration confirmée) |
| Planifier une étape (dates prévues, charges) | RAI ou chef de mission |
| Valider / renvoyer un jalon | RAI ; superviseur pour VI, X, XIII ; jamais l'auteur (`terminee_par`) |
| Rouvrir une étape (motif) | RAI ; superviseur sauf XVIII |
| Voir étapes, fiche de suivi, risques de mission, déclarations de l'équipe | RAI et intervenants |
| AUDITE | en-tête de mission (champs internes à `null`), équipe, réunions, entretiens où il est interlocuteur ; 403 sur étapes, suivi, risques, déclarations, affectations |
| `GET /api/v1/users/` | RAI, AUDITEUR, ADMIN |

  *À confirmer avec ONEA* : exclusion de l'ADMIN (rôle technique, norme 5.2) et du DG (§14 : rapports diffusés uniquement) des missions.
- **D5 — Périmètre de l'audité.** Explicite : affectation `AUDITE` sur la mission. Le rattachement sert de valeur par défaut : `audites_par_defaut(mission)` propose les utilisateurs AUDITE actifs dont `direction_code` est le code d'une entité de la mission ; l'écran Équipe les pré-coche, le RAI confirme. *À confirmer avec ONEA.*
- **D6 — Cartographie de référence.** `Mission.cartographie` = `version_courante()` à la création, obligatoire (sinon 422 `errors.cartographie` « Aucune cartographie des risques validée : validez une cartographie avant de créer une mission. »), inchangée pendant toute la mission même si une version plus récente est validée. *À confirmer avec ONEA.*
- **D7 — Livrables vérifiés au lot 3** (registre `etapes.py`, champ `lot_livrables`) : I « L'ordre de mission n'a pas été émis. » ; II « La réunion d'ouverture n'est pas marquée comme tenue. », « Aucun entretien n'est planifié. » (calendrier des premiers entretiens), « Déclarations d'indépendance en attente : {noms}. » ; IV « Aucun risque n'est sélectionné pour la mission. » ; XI « La réunion de lancement n'est pas marquée comme tenue. ». Les étapes III, V–X, XII–XVIII peuvent être démarrées ou marquées non applicables mais leur fin est refusée (422) avec « Les livrables de l'étape {romain} sont gérés à partir du lot {n}. » (`lot_livrables` : III, V, VI, VII → 5 ; VIII, IX, X, XII, XIII, XIV → 6 ; XV–XVIII → 7). Les lots suivants ajoutent leurs contrôles au registre sans changer le moteur. *À confirmer avec ONEA* : entretien planifié exigé pour finir II.
- **D8 — Moteur d'étapes.** `demarrer` (A_FAIRE → EN_COURS) : seulement pour une étape de la phase courante ; II et suivantes exigent toutes les déclarations confirmées ou arbitrées. `terminer` (EN_COURS ou RENVOYEE → TERMINEE) : livrables vérifiés ; l'étape I ne se termine que par `emettre_ordre_mission` (RAI). `valider` (TERMINEE ou A_REVALIDER → VALIDEE) et `renvoyer` (TERMINEE → RENVOYEE, motif) : jalons seulement. `rouvrir` (TERMINEE, VALIDEE ou A_REVALIDER → EN_COURS, motif) : `date_fin_reelle` effacée ; tout jalon VALIDEE de numéro supérieur passe A_REVALIDER (journalisé) ; la mission ne recule pas de phase mais le prochain changement de phase est bloqué tant qu'un jalon est A_REVALIDER. `non_applicable` (A_FAIRE ou EN_COURS → NON_APPLICABLE, motif) : missions CONSEIL seulement, jamais un jalon ; `retablir` (NON_APPLICABLE → A_FAIRE). Chaque transition verrouille la ligne de mission (`select_for_update`) et écrit un `EvenementEtape`. *À confirmer avec ONEA* : interdiction du « non applicable » sur un jalon.
- **D9 — Déclaration d'indépendance.** Créée EN_ATTENTE à chaque affectation CHEF_MISSION/AUDITEUR/SUPERVISEUR (une réaffectation en crée une nouvelle). L'auditeur confirme (CONFIRMEE) ou déclare une situation (CONFLIT_DECLARE, description obligatoire) ; le RAI arbitre un conflit (justification, l'auditeur reste affecté) ou désaffecte. Confirmable dès que la mission est visible par l'auditeur (hors BROUILLON). Texte provisoire figé dans `services/declarations.py` (gabarit ONEA « Déclaration d'indépendance collaborateur » non reçu) :
  « Je soussigné(e) {nom_complet}, affecté(e) à la mission {reference} « {titre} » en qualité de {role_mission}, déclare n'avoir, à ma connaissance, aucun conflit d'intérêts ni aucune relation personnelle, professionnelle ou financière avec les entités auditées ({entites}), ni avoir exercé de responsabilité opérationnelle sur les activités auditées au cours des douze derniers mois, de nature à porter atteinte à mon objectivité (Normes internationales d'audit interne, principe 2). Je m'engage à signaler sans délai au Responsable de l'Audit Interne toute situation nouvelle de cette nature. »
  *À confirmer avec ONEA* (texte, délai de douze mois).
- **D10 — Mode « confirmation » (§15.1).** `signatures.Confirmation` immuable : type de document, objet (contenttype + UUID), signataire authentifié, `confirme_le` horloge serveur, texte exact affiché, données confirmées (JSON), empreinte SHA-256 de `{"texte", "donnees"}` canonique (`sort_keys`, `ensure_ascii=False`, séparateurs compacts, `DjangoJSONEncoder`), adresse IP (`REMOTE_ADDR`). Pas de ré-authentification (la session Keycloak suffit ; le lot 7 bis pourra exiger `max_age`). Pas d'écran de paramétrage au lot 3 : le seul mode est `CONFIRMATION`. L'ordre de mission est émis et confirmé par le **RAI** ; texte : « Je soussigné(e) {nom_complet}, Responsable de l'Audit Interne, émets l'ordre de mission {reference} « {titre} » selon les objectifs, le périmètre, l'équipe et le calendrier enregistrés ce jour dans la plateforme. » *À confirmer avec ONEA* (le recueil cite une « Lettre DG au DC » : signataire réel de l'ordre de mission).
- **D11 — Équipe.** Intervenants : rôle global AUDITEUR obligatoire ; audités : rôle global AUDITE ; le RAI n'est jamais affecté. Un seul CHEF_MISSION actif, au plus un SUPERVISEUR, superviseur ≠ chef, un utilisateur une seule fois par mission. Le chef ne se retire pas après `lancer` : `remplacer_chef` (l'ancien chef devient AUDITEUR, sa déclaration est conservée ; le nouveau reçoit une déclaration s'il n'était pas intervenant). *À confirmer avec ONEA* (superviseur choisi parmi les auditeurs).
- **D12 — Fiche de suivi.** Par étape : dates prévues et charges prévues/réelles en jours (saisies par RAI ou chef, aucune feuille de temps), dates réelles posées par les transitions. `ecart_jours` = (date de fin réelle, ou aujourd'hui si l'étape est ouverte) − date de fin prévue ; **positif = retard** ; `null` sans date prévue ou pour une étape A_FAIRE/NON_APPLICABLE. Totaux : budget mission, Σ charges prévues, Σ charges réelles. Journal = `EvenementEtape` (ajout seul).
- **D13 — Réunions.** Une par type et par mission (OUVERTURE → étape II, LANCEMENT → XI, CLOTURE → XV) ; participants internes (M2M utilisateurs) + participants externes (texte, une ligne par personne) ; « Marquer comme tenue » exige un compte rendu et une date passée ; non modifiable quand l'étape associée est close. Le PV Word arrive au lot 4.
- **D14 — Entretiens.** Rattachement facultatif à une étape de la mission ; auditeurs = intervenants de la mission ; interlocuteurs internes (M2M) + autres interlocuteurs (texte) ; statuts PLANIFIE, REALISE (compte rendu exigé), ANNULE ; **note de synthèse par entretien** (le document « Note de synthèse entretiens » du lot 4 les assemble) ; non modifiable quand l'étape rattachée est close. *À confirmer avec ONEA* (note par entretien ou unique).
- **D15 — Risques de mission (étape IV).** Choisis parmi les risques actifs de `mission.cartographie` dont le processus est un processus de la mission ; copie figée de `code_source`, libellé, description, probabilité, impact, que l'équipe peut réévaluer (P, I, commentaire) pour la mission. Risque créé dans la mission : `risque_source` nul (« nouveau »), processus de la mission, libellé, P et I obligatoires. Ajout/modification seulement quand l'étape IV est EN_COURS ou RENVOYEE. Les risques nouveaux sont listés au RAI (lecture seule) sur la page d'une cartographie en brouillon : « Risques proposés par les missions » ; aucune insertion automatique. *À confirmer avec ONEA.*
- **D16 — Conventions d'API.** Routes plates au pluriel anglais ; listes enfants filtrées par `?mission=` ; `mission-steps` non paginé et `mission` obligatoire (400 sinon, 18 lignes) ; les autres listes paginées (`StandardPagination`) et chargées en entier côté front par `fetchAllPages`. `Mission.mes_droits` et `Etape.actions_possibles` sont la seule source des boutons affichés. Pas de `PUT`. La logique métier des missions vit dans le paquet `apps/missions/services/` (un module par sous-domaine) plutôt que dans un `services.py` unique, pour que T3 et T4 avancent en parallèle sans conflit ; la règle de `CLAUDE.md` (aucune logique dans les vues) est inchangée.
- **D17 — Champs gelés par l'étape I.** Après fin de l'étape I (ordre émis) : `titre, type, processus, entites, evenement_declencheur, evenement_precision, periode_debut, periode_fin, objectifs, perimetre, exclusions, clients, livrables_attendus` ne changent plus (422 `EtapeCloseError`) sauf réouverture de I, qui impose une nouvelle émission (nouvelle `Confirmation`, l'ancienne est conservée). Dates prévues, budget et équipe restent modifiables par le RAI.

## Review Focus

Leçons récurrentes du lot 2 (`final-review.md`, `task-3..7-review.md`) et cas que la spec implique ; chaque ligne a son test dans la tâche indiquée.

1. **Écritures sur un état figé** (I1/T2 du lot 2) : mission SUSPENDUE ou ANNULEE, étape II close pour la réunion d'ouverture, étape IV close pour les risques, étape I close pour les champs D17 — refus 422 par l'API, par le service **et** par `save()` / `QuerySet.update()` directs ; `reprendre` reste possible. Tests `test_gel_mission_suspendue_toutes_ecritures` (T3, paramétré sur chaque service), `test_save_direct_refuse_si_etape_close` (T2), `test_api_gel_422_sur_chaque_route_enfant` (T5).
2. **Cohérence des droits** (D4 dupliqué entre vue, permission et UI au lot 2) : matrice rôle × route paramétrée ; un intervenant non confirmé reçoit 403 en écriture ; un superviseur valide VI mais pas XVIII ; ADMIN et DG 403 ; mission invisible 404 ; et le front n'affiche que les boutons présents dans `mes_droits` / `actions_possibles`. Tests `test_matrice_droits_missions` (T5), `test_mes_droits_concorde_avec_les_permissions` (T5 : pour chaque droit vrai, l'appel correspondant ne renvoie pas 403), `MissionHeader.test.tsx` « aucun bouton absent de mes_droits » (T7), `StepPage.test.tsx` (T8).
3. **Courses de numérotation** (I2 du lot 2) : 8 `planifier_mission` concurrents sur la même année donnent M01…M08 sans doublon ni erreur ; un numéro de mission supprimée ou annulée n'est jamais réattribué. Tests `test_references_concurrentes_uniques` (`transaction=True`, `ThreadPoolExecutor`) et `test_numero_jamais_reattribue` (T3).
4. **Contrat inversé ou mal lu** (C1 « référence/cible » du lot 2) : `ecart_jours` positif = retard, mêmes valeurs testées des deux côtés ; `statut_avant_suspension` restauré ; `code_source` vide ⇔ `nouveau`. Les réponses MSW sont typées `satisfies components["schemas"][…]` et construites à partir des exemples de `backend/tests/missions/test_api_contrat.py`. Tests `test_ecart_positif_signifie_retard` (T4), `test_api_contrat_fiche_suivi` (T5), `TrackingPage.test.tsx` « 3 jours de retard » (T8).
5. **Listes tronquées** (I2 de la tâche 6 du lot 2) : sélecteurs d'utilisateurs, de processus, d'entités et de risques de cartographie au-delà de 200 éléments chargés par `fetchAllPages`, avec `ListIncompleteAlert` si `count > results`. Tests « deux pages MSW, 201 éléments affichés » dans `TeamPage.test.tsx` (T7) et `StepIVZone.test.tsx` (T8).
6. **Format d'erreur et messages sur les champs** : erreurs imbriquées (`processus.0`), 404 d'une mission invisible au format `{detail, errors}`, 422 posé sur le champ par `applyApiErrors` qui place le focus sur le premier champ en erreur. Tests `test_erreurs_au_format_unique` (T5), `MissionFormPage.test.tsx` « 422 cartographie affiché, focus sur le premier champ » (T7).
7. **Accessibilité** (T6/T7 du lot 2) : stepper en `<ol>` par phase, `aria-current="step"`, statut en texte ; actions irréversibles (émettre l'ordre, confirmer la déclaration, annuler la mission, valider un jalon) en `AlertDialog` ; aucun `<select>` qui navigue sur `change` ; alerte d'erreur qui ne vole pas le focus à chaque rendu ; formulaire en lecture seule sans opacité 50 % ; `axe` sans violation, dialogues ouverts compris. Tests dans T6–T9.
8. **Indépendance** (norme 2.x) : une déclaration confirmée est immuable et son empreinte se vérifie ; un auditeur ne peut confirmer que la sienne ; l'étape II ne démarre pas tant qu'une déclaration est en attente. Tests `test_confirmation_immuable_et_verifiable` (T1), `test_confirmer_la_declaration_d_un_autre_refuse` (T3), `test_demarrer_II_exige_les_declarations` (T4).

## Vagues d'exécution

| Vague | Tâches (∥ = en parallèle) | Agent / modèle | Dépend de |
|---|---|---|---|
| 1 | T1 socle partagé + signatures ∥ T2 modèles missions | backend-dev / sonnet ×2 | — |
| 2 | T3 services pilotage ∥ T4 services étapes et travaux | backend-dev / sonnet ×2 | T1, T2 |
| 3 | T5 API + contrat OpenAPI | backend-dev / sonnet | T3, T4 |
| 4 | T6 fondations frontend | frontend-dev / sonnet | `schema.d.ts` de T5 |
| 5 | T7 pilotage ∥ T8 étapes ∥ T9 réunions et entretiens | frontend-dev / sonnet ×3 | T6 |
| 6 | T10 e2e, documentation, vérification | test-engineer / sonnet | toutes |

T1 et T2 ne partagent aucun fichier (`Confirmation` est reliée par contenttype, pas par FK). T3 et T4 écrivent des modules distincts du paquet `services/` ; les fixtures partagées vivent seulement dans `tests/missions/conftest.py` (T2), les fixtures propres restent dans les modules de test. T7, T8, T9 n'éditent que leurs pages, leurs zones d'étape et leur section de `fr.ts`. Chaque tâche est relue par `reviewer` (opus) ; T7–T9 reçoivent la revue visuelle `ui-designer` (écran et impression).

---

### Task 1: Socle partagé (helpers de services, matrice générique) et app `signatures`

**Model:** sonnet (backend-dev)

**Files:**
- Create: `backend/apps/core/services.py`, `backend/apps/signatures/{__init__,apps,models,services,serializers,exceptions,managers}.py`, `backend/apps/signatures/migrations/{__init__,0001_initial}.py`
- Modify: `backend/apps/referentiel/services.py` (utilise les helpers de `core`, ajoute `matrice_de`), `backend/apps/referentiel/views.py` (importe `crud_schema` de `core.schema`), `backend/apps/core/schema.py` (reçoit `crud_schema`), `backend/config/settings/base.py` (`INSTALLED_APPS += ["apps.signatures"]`), `backend/tests/factories.py` (`ConfirmationFactory`)
- Test: `backend/tests/core/test_services_helpers.py`, `backend/tests/signatures/{__init__,test_confirmations}.py`, `backend/tests/referentiel/test_matrice_de.py`

**Interfaces:**
- Consumes: `BaseModel`, `actor_scope`, `RegleMetierError`, `core.audit.register` (lot 1) ; `CelluleMatrice`, `niveau_pour_score` (lot 2).
- Produces:
  - `core.services` (déplacés de `referentiel/services.py` sans changement de comportement ; `referentiel` les importe, ses 459 tests restent verts) : `refuser(message: str, **errors: str) -> RegleMetierError` ; `enregistrer(obj: BaseModel, *, by: User, creation: bool = False) -> None` (`full_clean(validate_constraints=False)` → `RegleMetierError("Données invalides.", erreurs)`, puis `save()` sous `actor_scope(by)` et `transaction.atomic()` ; l'unicité de code reste dans un wrapper de `referentiel`) ; `relire[T](obj: T) -> T` (`select_for_update`, `Http404`) ; `verrouiller_actif[T](obj: T, champ: str) -> T` ; `appliquer(obj, changes: dict[str, Any], autorises: set[str]) -> None` (ignore les M2M listés dans `m2m: set[str] = frozenset()` en paramètre mot-clé).
  - `core.schema.crud_schema(serializer, tag: str, nom: str)` (déplacé de `referentiel/views.py`).
  - `referentiel.services.matrice_de(lignes: Iterable[tuple[int, int, str]]) -> list[CelluleMatrice]` (25 cases, probabilité 5 → 1 puis impact 1 → 5, codes dans l'ordre reçu) ; `matrice(version)` délègue.
  - `signatures.models` : `TypeDocumentSignable(TextChoices)` ORDRE_MISSION « Ordre de mission », DECLARATION_INDEPENDANCE « Déclaration d'indépendance », VALIDATION_RAPPORT « Validation du rapport » ; `ModeSignature(TextChoices)` CONFIRMATION « Confirmation horodatée » ; `Confirmation(BaseModel)` : `type_document`, `mode` (défaut CONFIRMATION), `content_type` FK PROTECT, `object_id` UUID, `signataire` FK user PROTECT `related_name="+"`, `confirme_le` DateTime, `texte` Text, `donnees` JSON (`DjangoJSONEncoder`), `empreinte` Char(64) (CHECK `empreinte ~ '^[0-9a-f]{64}$'`), `adresse_ip` GenericIPAddress null. Index (`content_type`, `object_id`, `type_document`, `-confirme_le`). Enregistrée dans auditlog.
  - Immuabilité : `Confirmation.save()` hors création, `soft_delete`, `QuerySet.update/bulk_update` → `ConfirmationImmuableError(RegleMetierError)` « Une confirmation est définitive : elle ne peut être ni modifiée ni supprimée. ».
  - `signatures.services` : `empreinte(texte: str, donnees: dict[str, Any]) -> str` (D10) ; `confirmer(*, type_document: str, objet: BaseModel, texte: str, donnees: dict[str, Any], by: User, adresse_ip: str | None = None) -> Confirmation` (`confirme_le = timezone.now()`) ; `verifier(confirmation: Confirmation) -> bool` ; `derniere_confirmation(objet: BaseModel, type_document: str) -> Confirmation | None`.
  - `signatures.serializers.ConfirmationResumeSerializer` {id, type_document, signataire {id, nom_complet}, confirme_le, empreinte} (consommé par T5).

- [ ] **Step 1: Écrire les tests**
```python
def test_confirmation_immuable_et_verifiable(rai):
    objet = DirectionFactory()                     # tout BaseModel convient
    c = confirmer(type_document="ORDRE_MISSION", objet=objet, texte="Je soussigné(e)…",
                  donnees={"titre": "Achats – Ouaga", "auditeurs": ["A", "B"]}, by=rai)
    assert verifier(c) and len(c.empreinte) == 64
    c.texte = "autre"
    with pytest.raises(ConfirmationImmuableError):
        c.save()
    with pytest.raises(ConfirmationImmuableError):
        Confirmation.objects.filter(pk=c.pk).update(texte="x")
    with pytest.raises(ConfirmationImmuableError):
        c.soft_delete(by=rai)

def test_empreinte_canonique_independante_de_l_ordre_des_cles():
    assert empreinte("t", {"a": 1, "b": "é"}) == empreinte("t", {"b": "é", "a": 1})
    assert empreinte("t", {"a": 1}) != empreinte("t ", {"a": 1})
```
Plus : `test_derniere_confirmation` (deux confirmations, renvoie la plus récente) ; `test_donnees_alterees_en_base_detectees` (`update` SQL brut de `donnees` → `verifier` faux) ; `test_confirmation_historisee_avec_l_acteur` ; `test_matrice_de_25_cases_et_ordre` ; `test_helpers_deplaces_sans_regression` (import depuis `core.services` ; `pytest tests/referentiel` vert).
- [ ] **Step 2: `cd backend && pytest tests/signatures tests/core tests/referentiel -v`** → FAIL (app inconnue, `matrice_de` absent).
- [ ] **Step 3: Implémenter** le déplacement des helpers et de `crud_schema`, `matrice_de`, l'app `signatures` ; `python manage.py makemigrations signatures`.
- [ ] **Step 4: `pytest -v`** → PASS (lots 1 et 2 compris) ; `python manage.py makemigrations --check --dry-run` → aucun changement ; `ruff check . && mypy .` → 0.
- [ ] **Step 5: Commit** `feat(signatures): add immutable timestamped confirmation; refactor shared service helpers into core`.

### Task 2: App `missions` — modèles, registre des étapes, accès, gardes, migration

**Model:** sonnet (backend-dev), en parallèle de T1.

**Files:**
- Create: `backend/apps/missions/{__init__,apps,models,etapes,acces,gardes,managers,exceptions}.py`, `backend/apps/missions/migrations/{__init__,0001_initial}.py`
- Modify: `backend/config/settings/base.py` (`INSTALLED_APPS += ["apps.missions"]`), `backend/tests/factories.py`
- Test: `backend/tests/missions/{__init__,conftest,test_models,test_etapes_registre,test_acces,test_gardes}.py`

**Interfaces:**
- Consumes: `BaseModel`, `core.audit.register(model, m2m_fields)`, `RegleMetierError` ; `referentiel.models.{CartographieVersion, Processus, Direction, Risque, NiveauRisque}`, `referentiel.scoring` ; `Role`, `User`.
- Produces:
  - Énumérations (`TextChoices`, valeur ASCII, libellé français) : `TypeMission` ASSURANCE, CONSEIL ; `StatutMission` (les 10 de §8 ; libellés « Brouillon », « Planifiée », « En planification », « En accomplissement », « En communication », « Rapport diffusé », « En suivi », « Clôturée », « Suspendue », « Annulée ») ; `EvenementDeclencheur` PROGRAMME_ANNUEL « Mission inscrite au programme annuel », DEMANDE_MANAGEMENT « Demande du management », CHANGEMENT_MAJEUR « Changement majeur interne ou externe », EXIGENCE_REGLEMENTAIRE « Exigence réglementaire », AUTRE ; `RoleMission` CHEF_MISSION « Chef de mission », AUDITEUR, SUPERVISEUR, AUDITE « Audité » ; `Phase` PLANIFICATION, ACCOMPLISSEMENT, COMMUNICATION ; `StatutEtape` (7, « À faire », « En cours », « Terminée », « Validée », « Renvoyée », « À revalider », « Non applicable ») ; `TypeEvenementEtape` DEMARREE, TERMINEE, VALIDEE, RENVOYEE, ROUVERTE, A_REVALIDER, NON_APPLICABLE, RETABLIE ; `StatutDeclaration` EN_ATTENTE, CONFIRMEE, CONFLIT_DECLARE ; `TypeReunion` OUVERTURE « Réunion d'ouverture », LANCEMENT « Réunion de lancement », CLOTURE « Réunion de clôture » ; `StatutEntretien` PLANIFIE, REALISE, ANNULE.
  - `Mission` : `reference` Char(20) vide permis, `annee`, `numero` PositiveSmallInteger null, `titre` (300), `type`, `statut` `FSMField(default=BROUILLON, protected=False)`, `statut_avant_suspension` (choix, vide permis), `motif_suspension`, `motif_annulation` (Text), `processus` M2M `Processus` `related_name="missions"`, `entites` M2M `Direction` `related_name="missions"`, `evenement_declencheur` (choix, vide permis), `evenement_precision`, `periode_debut`, `periode_fin`, `date_debut_prevue`, `date_fin_prevue` (Date null), `budget_jours` Decimal(6,1) défaut 0, `objectifs`, `perimetre`, `exclusions`, `clients`, `livrables_attendus` (Text), `cartographie` FK PROTECT `related_name="missions"`, `ordre_mission_emis_le` DateTime null. Contraintes : unique `reference` si non vide (**supprimées incluses**) ; unique (`annee`, `numero`) si `numero` non nul ; CHECK dates prévues ordonnées, période ordonnée, `budget_jours >= 0`, `statut = BROUILLON OR reference <> ''`. Ordre `-created_at`. Propriété `phase -> Phase | None` (depuis `PHASE_DU_STATUT`).
  - `AffectationMission` : `mission` FK PROTECT `related_name="affectations"`, `utilisateur` FK PROTECT `related_name="affectations_mission"`, `role_mission`. Uniques actifs : (`mission`, `utilisateur`) ; `mission` si CHEF_MISSION ; `mission` si SUPERVISEUR.
  - `DeclarationIndependance` : `affectation` OneToOne PROTECT `related_name="declaration"`, `statut` (défaut EN_ATTENTE), `description_conflit`, `arbitrage_justification` (Text), `arbitre_par` FK null PROTECT, `arbitre_le` null. CHECK : CONFLIT_DECLARE ⇒ description non vide ; arbitrage ⇒ CONFLIT_DECLARE. Propriété `levee -> bool` (CONFIRMEE, ou CONFLIT_DECLARE arbitré).
  - `EtapeMission` : `mission` FK PROTECT `related_name="etapes"`, `numero` (CHECK 1–18), `statut` `FSMField(default=A_FAIRE, protected=False)` avec transitions `demarrer`, `terminer`, `valider`, `renvoyer`, `rouvrir`, `a_revalider`, `non_applicable`, `retablir` (sources/cibles de D8, appelées seulement par les services), dates prévues et réelles (Date null), `charge_prevue_jours`, `charge_reelle_jours` Decimal(5,1) null (CHECK ≥ 0), `terminee_par`, `validee_par` FK null PROTECT, `validee_le` null, `motif_non_applicable`. Unique actif (`mission`, `numero`) ; ordre `numero`. Propriété `definition -> DefinitionEtape`.
  - `EvenementEtape` : `etape` FK PROTECT `related_name="evenements"`, `type`, `par` FK PROTECT, `le` DateTime, `motif`, `statut_avant`, `statut_apres`. Ajout seul (modification → `RegleMetierError`). `EvenementEtape.journaliser(etape, type, *, par, motif="", statut_avant) -> EvenementEtape`.
  - `Reunion` : `mission` FK `related_name="reunions"`, `type`, `date` DateTime, `lieu` (200), `ordre_du_jour`, `participants` M2M user `related_name="+"`, `participants_externes`, `decisions`, `compte_rendu` (Text), `tenue_le` null. Unique actif (`mission`, `type`).
  - `Entretien` : `mission` FK `related_name="entretiens"`, `etape` FK `EtapeMission` null PROTECT, `objet` (300), `date_prevue` DateTime, `duree_minutes` PositiveSmallInteger null (CHECK 1–600), `lieu` (200), `auditeurs`, `interlocuteurs` M2M user `related_name="+"`, `autres_interlocuteurs`, `themes`, `compte_rendu`, `note_synthese` (Text), `statut` (défaut PLANIFIE), `realise_le` null, `motif_annulation`.
  - `RisqueMission` : `mission` FK `related_name="risques"`, `risque_source` FK `referentiel.Risque` null PROTECT `related_name="+"`, `processus` FK PROTECT `related_name="+"`, `code_source` (32, vide permis), `libelle` (500), `description`, `probabilite`, `impact` (CHECK 1–5), `score`, `niveau` (`GeneratedField`, mêmes expressions que `referentiel.Risque`), `commentaire`. Unique actif (`mission`, `risque_source`) si source non nulle ; CHECK `(risque_source IS NULL) = (code_source = '')`. Propriété `nouveau`.
  - `etapes.py` : `@dataclass(frozen=True) DefinitionEtape(numero: int, romain: str, titre: str, phase: Phase, jalon: bool, objectif: str, livrables: tuple[str, ...], acteurs: str, lot_livrables: int)` ; `ETAPES` (18 entrées : titres, objectifs, livrables et acteurs **recopiés de `docs/domaine/processus-ifaci.md`**, `lot_livrables` de D7) ; `JALONS = frozenset({6, 10, 13, 18})` ; `JALONS_DELEGABLES = frozenset({6, 10, 13})` ; `PHASE_DU_STATUT: dict[str, Phase]` ; `ETAPES_DE_PHASE: dict[Phase, range]` ; `JALON_DE_PHASE = {PLANIFICATION: 10, ACCOMPLISSEMENT: 13}` ; `ETAPE_DE_REUNION = {OUVERTURE: 2, LANCEMENT: 11, CLOTURE: 15}` ; `etape(numero: int) -> DefinitionEtape` ; `romain(numero: int) -> str`.
  - `exceptions.py` : `MissionFigeeError(RegleMetierError)` « La mission {reference} est {statut en minuscules} : aucune modification n'est possible. » ; `EtapeCloseError(RegleMetierError)` « L'étape {romain} est terminée : rouvrez-la pour modifier ses travaux. ».
  - `gardes.py` : `STATUTS_FIGES = {SUSPENDUE, ANNULEE, CLOTUREE}` ; `STATUTS_ETAPE_CLOSE = {TERMINEE, VALIDEE, A_REVALIDER}` ; `verrouiller_mission(mission: Mission | UUID) -> Mission` (`select_for_update`, `Http404` si absente, `MissionFigeeError` si figée) ; `exiger_etape_ouverte(mission_id, numero: int) -> None` (lecture en base). Gardes `save()` : `Mission` (ligne en base figée → refus, sauf la sauvegarde de `reprendre` qui ne touche que `statut, statut_avant_suspension, updated_by, updated_at` depuis SUSPENDUE ; champs D17 modifiés alors que l'étape I est close en base → `EtapeCloseError(1)`) ; `AffectationMission`, `DeclarationIndependance`, `EtapeMission`, `Reunion`, `Entretien`, `RisqueMission` (mission figée en base → refus) ; `Reunion` (étape `ETAPE_DE_REUNION[type]` close), `Entretien` (étape rattachée close), `RisqueMission` (étape IV close) → `EtapeCloseError`. Mêmes gardes dans `managers.MissionEnfantQuerySet.update/bulk_update/bulk_create` (modèle `referentiel/managers.py`).
  - `acces.py` (rôles seulement, pas d'état) : `role_dans_mission(user: User, mission: Mission) -> str | None` ; `est_intervenant(user, mission) -> bool` ; `est_chef(user, mission) -> bool` ; `est_superviseur(user, mission) -> bool` ; `declaration_levee(user, mission) -> bool` ; `peut_contribuer(user, mission) -> bool` (RAI, ou intervenant à déclaration levée) ; `peut_valider_jalon(user, mission, numero: int) -> bool` ; `missions_visibles(user) -> QuerySet[Mission]` (D4, une requête, `distinct()`).
  - Enregistrement auditlog : les 9 modèles ; `m2m_fields` : Mission {processus, entites}, Reunion {participants}, Entretien {auditeurs, interlocuteurs}.
  - Factories : `MissionFactory` (cartographie validée créée si besoin, `reference` vide, BROUILLON ; trait `avec_processus_et_entites` qui ajoute un processus et une entité), `AffectationFactory`, `DeclarationFactory`, `EtapeMissionFactory`, `ReunionFactory`, `EntretienFactory`, `RisqueMissionFactory`. `tests/missions/conftest.py` : `mission_lancee` (EN_PLANIFICATION, référence `DAI/2026/M01`, 18 étapes, étape I EN_COURS, fixtures `chef` et `auditeur_mission` affectés avec déclarations CONFIRMEE, `audite_affecte`), `forcer_etapes(mission, {numero: statut})` (via `update`, mission non figée).

- [ ] **Step 1: Écrire les tests**
```python
def test_save_direct_refuse_si_etape_close(mission_lancee):
    r = ReunionFactory(mission=mission_lancee, type="OUVERTURE")
    forcer_etapes(mission_lancee, {2: "TERMINEE"})
    r.refresh_from_db(); r.decisions = "contournement"
    with pytest.raises(EtapeCloseError):
        r.save()
    with pytest.raises(EtapeCloseError):
        Reunion.objects.filter(pk=r.pk).update(decisions="x")

def test_mission_suspendue_refuse_save_sauf_reprise(mission_lancee):
    Mission.objects.filter(pk=mission_lancee.pk).update(
        statut="SUSPENDUE", statut_avant_suspension="EN_PLANIFICATION")
    m = Mission.objects.get(pk=mission_lancee.pk); m.titre = "x"
    with pytest.raises(MissionFigeeError):
        m.save()
```
Plus : `test_reference_unique_meme_supprimee` ; `test_un_seul_chef_et_un_seul_superviseur_actifs` ; `test_dates_prevues_ordonnees_en_base` ; `test_risque_mission_hors_bornes_rejete` ; `test_code_source_vide_si_et_seulement_si_nouveau` ; `test_registre_18_etapes_phases_et_jalons` (I–X Planification, XI–XIV Accomplissement, XV–XVIII Communication, jalons VI X XIII XVIII, titre IV « Identifier et évaluer les risques ») ; `test_evenement_etape_ajout_seul` ; `test_missions_visibles_par_role` (RAI toutes ; auditeur non affecté 0 ; audité avant ordre 0, après 1 ; ADMIN et DG 0 ; BROUILLON invisible à l'auditeur affecté) ; `test_peut_contribuer_exige_declaration_levee` ; `test_m2m_historises`.
- [ ] **Step 2: `pytest tests/missions -v`** → FAIL.
- [ ] **Step 3: Implémenter** modèles, registre, accès, gardes, managers, factories ; `makemigrations missions`.
- [ ] **Step 4: `pytest tests/missions -v`** → PASS ; `makemigrations --check --dry-run` → aucun changement ; `ruff check . && mypy .` → 0.
- [ ] **Step 5: Commit** `feat(missions): add mission, assignment, step, meeting, interview and mission risk models with freeze guards`.

### Task 3: Services de pilotage — cycle de vie, référence, équipe, déclarations, droits

**Model:** sonnet (backend-dev), en parallèle de T4.

**Files:**
- Create: `backend/apps/missions/services/{__init__,missions,equipe,declarations,droits}.py`
- Test: `backend/tests/missions/{test_services_missions,test_services_equipe,test_services_declarations,test_references_concurrence,test_droits}.py`

**Interfaces:**
- Consumes: modèles, `etapes`, `gardes`, `acces` (T2) ; `core.services.*`, `signatures.services.confirmer` (T1) ; `referentiel.services.version_courante`.
- Produces (toutes `@transaction.atomic`, `by: User` en mot-clé, `RegleMetierError` avec `errors` par champ ; toute écriture commence par `verrouiller_mission`) :
  - `missions.creer_mission(*, titre: str, type: str, by: User, processus: Iterable[Processus] = (), entites: Iterable[Direction] = (), **champs) -> Mission` : cartographie = `version_courante()` (D6), crée les 18 `EtapeMission` A_FAIRE. `modifier_mission(mission, *, by, **changes) -> Mission` (D17). `supprimer_mission(mission, *, by)` (BROUILLON seulement : « Seule une mission en brouillon peut être supprimée ; annulez-la. » ; supprime logiquement étapes et affectations).
  - `planifier_mission(mission, *, by) -> Mission` : exige titre, type, ≥ 1 processus, ≥ 1 entité, dates prévues (messages par champ : « Ce champ est obligatoire pour planifier la mission. ») ; référence D3 sous `pg_advisory_xact_lock(LOCK_REFERENCE_MISSION)` (constante entière de `missions.services`).
  - `lancer_mission(mission, *, by) -> Mission` : PLANIFIEE, un chef requis (« Désignez un chef de mission avant de lancer la mission. ») ; étape I → EN_COURS (événement DEMARREE, `date_debut_reelle` = aujourd'hui Ouagadougou).
  - `emettre_ordre_mission(mission, *, by, adresse_ip: str | None = None) -> Confirmation` : EN_PLANIFICATION, étape I EN_COURS ou RENVOYEE, objectifs et périmètre non vides ; `confirmer(type_document=ORDRE_MISSION, objet=mission, texte=…, donnees=…)` (D10 ; `donnees` = reference, titre, type, objectifs, perimetre, exclusions, clients, livrables_attendus, codes processus et entités, période, dates prévues, équipe [{nom, role_mission}]) ; `ordre_mission_emis_le` posé s'il est vide ; étape I → TERMINEE (`terminee_par=by`, `date_fin_reelle`, événement).
  - `suspendre_mission(mission, *, motif, by)`, `reprendre_mission(mission, *, by)`, `annuler_mission(mission, *, motif, by)` (D2 ; motif vide → `errors.motif`).
  - `equipe.affecter(mission, *, utilisateur: User, role_mission: str, by) -> AffectationMission` (D11 ; crée la déclaration EN_ATTENTE des intervenants ; messages : « Un intervenant doit avoir le rôle Auditeur interne. », « Un audité doit avoir le rôle Audité. », « Cette mission a déjà un chef de mission. », « Cette mission a déjà un superviseur. », « Le superviseur ne peut pas être le chef de mission. », « Cet utilisateur est déjà affecté à la mission. ») ; `desaffecter(affectation, *, by)` (chef après lancement → « Le chef de mission ne peut être retiré qu'en le remplaçant. ») ; `remplacer_chef(mission, *, utilisateur, by) -> AffectationMission` ; `audites_par_defaut(mission) -> QuerySet[User]` (D5).
  - `declarations.texte_declaration(declaration) -> str` (D9, mot pour mot) ; `confirmer_declaration(declaration, *, by, conflit: bool = False, description_conflit: str = "", adresse_ip=None) -> DeclarationIndependance` (autre utilisateur → « Seul l'auditeur concerné peut confirmer sa déclaration. » ; déjà confirmée → « Cette déclaration est déjà confirmée. » ; mission BROUILLON refusée ; `confirmer(type_document=DECLARATION_INDEPENDANCE, …)` avec `donnees` {mission, reference, role_mission, conflit, description_conflit}) ; `arbitrer_conflit(declaration, *, justification, by)` ; `confirmation_de(declaration) -> Confirmation | None`.
  - `droits.@dataclass(frozen=True) DroitsMission(modifier, planifier, lancer, emettre_ordre, suspendre, reprendre, annuler, supprimer, affecter, contribuer, voir_travaux, confirmer_ma_declaration: bool)` ; `droits_mission(user, mission) -> DroitsMission` (rôle de D4 **et** état de la mission : p. ex. `lancer` vrai seulement pour le RAI sur une mission PLANIFIEE ; tout faux sur une mission figée sauf `reprendre`/`annuler` selon D2).

- [ ] **Step 1: Écrire les tests**
```python
@pytest.mark.django_db(transaction=True)
def test_references_concurrentes_uniques(rai):
    missions = [MissionFactory(date_debut_prevue=date(2026, 3, 1), date_fin_prevue=date(2026, 5, 1),
                               avec_processus_et_entites=True) for _ in range(8)]
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda m: _dans_un_thread(planifier_mission, m, by=rai), missions))
    refs = sorted(Mission.objects.values_list("reference", flat=True))
    assert refs == [f"DAI/2026/M{n:02d}" for n in range(1, 9)]

def test_gel_mission_suspendue_toutes_ecritures(mission_lancee, rai, chef):
    suspendre_mission(mission_lancee, motif="Arrêt demandé par la DG", by=rai)
    for appel in ECRITURES_PILOTAGE(mission_lancee, rai, chef):   # modifier, affecter, désaffecter,
        with pytest.raises(MissionFigeeError):                    # émettre, confirmer, planifier…
            appel()
    reprendre_mission(mission_lancee, by=rai)
    assert Mission.objects.get(pk=mission_lancee.pk).statut == "EN_PLANIFICATION"
```
Plus : `test_numero_jamais_reattribue` (M01 supprimée en BROUILLON n'a pas de référence ; M01 annulée → la suivante est M02) ; `test_creation_sans_cartographie_validee_422` (`errors.cartographie`) ; `test_creation_cree_18_etapes` ; `test_planifier_champs_manquants_par_champ` ; `test_lancer_sans_chef_refuse` ; `test_emettre_ordre_termine_I_et_gele_les_champs` (puis `modifier_mission(objectifs=…)` → `EtapeCloseError`, `budget_jours` accepté) ; `test_emettre_ordre_snapshot_verifiable` (`verifier(c)`, `donnees["equipe"]`) ; `test_affecter_regles` (chacun des six messages) ; `test_remplacer_chef` ; `test_audites_par_defaut_par_direction_code` ; `test_confirmer_la_declaration_d_un_autre_refuse` ; `test_conflit_puis_arbitrage_leve_la_declaration` ; `test_texte_declaration_exact` ; `test_droits_par_role_et_etat` (paramétré : RAI/PLANIFIEE → `lancer` vrai ; RAI/SUSPENDUE → seuls `reprendre` et `annuler` ; auditeur non confirmé → `contribuer` faux, `confirmer_ma_declaration` vrai) ; `test_transitions_historisees_avec_motif`.
- [ ] **Step 2: `pytest tests/missions -v`** → FAIL.
- [ ] **Step 3: Implémenter** les quatre modules.
- [ ] **Step 4: `pytest tests/missions -v`** → PASS ; `ruff check . && mypy .` → 0.
- [ ] **Step 5: Commit** `feat(missions): add mission lifecycle, reference numbering, team and independence declaration services`.

### Task 4: Services du stepper, de la fiche de suivi, des réunions, entretiens et risques de mission

**Model:** sonnet (backend-dev), en parallèle de T3.

**Files:**
- Create: `backend/apps/missions/services/{etapes,livrables,suivi,reunions,entretiens,risques}.py`
- Modify: `backend/apps/referentiel/services.py` seulement si `matrice_de` manque (livré par T1)
- Test: `backend/tests/missions/{test_services_etapes,test_livrables,test_suivi,test_services_reunions,test_services_entretiens,test_services_risques}.py`

**Interfaces:**
- Consumes: modèles, `etapes`, `gardes`, `acces`, fixtures `mission_lancee`, `forcer_etapes` (T2) ; `core.services.*`, `matrice_de`, `CelluleMatrice` (T1) ; `referentiel.scoring`.
- Produces (mêmes conventions que T3) :
  - `etapes` : `demarrer_etape(etape, *, by)`, `terminer_etape(etape, *, by)`, `valider_etape(etape, *, by)`, `renvoyer_etape(etape, *, motif, by)`, `rouvrir_etape(etape, *, motif, by)`, `marquer_non_applicable(etape, *, motif, by)`, `retablir_etape(etape, *, by)` → `EtapeMission`, règles D8 ; `planifier_etape(etape, *, by, **changes)` (dates prévues, charges ; CHECK de cohérence des dates prévues → `errors.date_fin_prevue`) ; `avancer_phase(mission, *, by) -> bool` (D2, appelé par `terminer_etape` et `valider_etape`) ; `ActionEtape(TextChoices)` DEMARRER, TERMINER, VALIDER, RENVOYER, ROUVRIR, NON_APPLICABLE, RETABLIR, PLANIFIER ; `actions_possibles(etape, user) -> list[str]` (statut, phase, rôle de D4, valideur ≠ auteur, type de mission — la même fonction sert de garde dans les vues). Messages : « L'étape {romain} appartient à une phase qui n'a pas commencé. », « L'étape I se termine par l'émission de l'ordre de mission. », « Le valideur ne peut pas être l'auteur de l'étape. », « Seules les missions de conseil peuvent avoir des étapes non applicables. », « Un jalon ne peut pas être marqué non applicable. », « Seuls les jalons VI, X, XIII et XVIII sont validés. », « Le motif est obligatoire. ».
  - `livrables` : `CONTROLES: dict[int, list[Callable[[EtapeMission], str | None]]]` (I, II, IV, XI ; D7) ; `livrables_manquants(etape) -> list[str]` (renvoie le message « gérés à partir du lot {n} » quand `lot_livrables > 3`) ; `terminer_etape` lève `RegleMetierError("Livrables manquants.", {"livrables": [...]})`.
  - `suivi` : `@dataclass LigneSuivi(numero: int, romain: str, titre: str, phase: str, jalon: bool, statut: str, debut_prevu: date | None, fin_prevue: date | None, debut_reel: date | None, fin_reelle: date | None, ecart_jours: int | None, charge_prevue: Decimal | None, charge_reelle: Decimal | None)` ; `@dataclass FicheSuivi(mission: Mission, budget_jours: Decimal, total_prevu: Decimal, total_reel: Decimal, lignes: list[LigneSuivi], evenements: list[EvenementEtape])` ; `fiche_de_suivi(mission, *, aujourd_hui: date | None = None) -> FicheSuivi` (D12 ; ≤ 3 requêtes).
  - `reunions` : `creer_reunion(mission, *, type, date, by, participants=(), **champs) -> Reunion` (doublon de type → `errors.type` « Cette réunion existe déjà pour la mission. ») ; `modifier_reunion(reunion, *, by, **changes)` ; `supprimer_reunion(reunion, *, by)` ; `marquer_reunion_tenue(reunion, *, by)` (« Saisissez le compte rendu avant de marquer la réunion comme tenue. », « Une réunion à venir ne peut pas être marquée comme tenue. »).
  - `entretiens` : `creer_entretien(mission, *, objet, date_prevue, by, etape=None, auditeurs=(), interlocuteurs=(), **champs) -> Entretien` (auditeur non intervenant → `errors.auditeurs` « Les auditeurs doivent faire partie de l'équipe de la mission. » ; étape d'une autre mission → `errors.etape`) ; `modifier_entretien`, `supprimer_entretien`, `marquer_entretien_realise(entretien, *, by)` (compte rendu exigé), `annuler_entretien(entretien, *, motif, by)`.
  - Les écritures de réunions, entretiens et risques passent par `verrouiller_mission` et exigent un statut de mission parmi PLANIFIEE, EN_PLANIFICATION, EN_ACCOMPLISSEMENT, EN_COMMUNICATION (« Les travaux commencent une fois la mission planifiée. »).
  - `risques` : `ajouter_risque_mission(mission, *, by, risque_source: Risque | None = None, processus: Processus | None = None, libelle: str = "", probabilite: int | None = None, impact: int | None = None, **details) -> RisqueMission` (D15 ; messages « Ce risque n'appartient pas à la cartographie de la mission. », « Le processus doit être un processus de la mission. », « Ce risque est déjà sélectionné. », « Commencez l'étape IV pour sélectionner les risques. ») ; `modifier_risque_mission(rm, *, by, **changes)` (libellé et description seulement pour un risque nouveau) ; `retirer_risque_mission(rm, *, by)` ; `matrice_mission(mission) -> list[CelluleMatrice]` (codes : `code_source` ou « Nouveau : {libellé tronqué à 40} ») ; `risques_proposes() -> QuerySet[RisqueMission]` (nouveaux, missions non supprimées ni annulées, `select_related("mission", "processus")`).

- [ ] **Step 1: Écrire les tests**
```python
def test_ecart_positif_signifie_retard(mission_lancee, chef):
    e4 = mission_lancee.etapes.get(numero=4)
    EtapeMission.objects.filter(pk=e4.pk).update(
        statut="TERMINEE", date_fin_prevue=date(2026, 3, 10), date_fin_reelle=date(2026, 3, 13))
    e3 = mission_lancee.etapes.get(numero=3)
    EtapeMission.objects.filter(pk=e3.pk).update(statut="EN_COURS", date_fin_prevue=date(2026, 3, 20))
    fiche = fiche_de_suivi(mission_lancee, aujourd_hui=date(2026, 3, 18))
    assert {l.numero: l.ecart_jours for l in fiche.lignes if l.numero in (3, 4)} == {4: 3, 3: -2}

def test_rouvrir_IV_met_VI_a_revalider_et_bloque_la_phase(mission_lancee, rai):
    forcer_etapes(mission_lancee, {n: "TERMINEE" for n in range(1, 11)} | {6: "VALIDEE", 10: "TERMINEE"})
    rouvrir_etape(mission_lancee.etapes.get(numero=4), motif="Risque oublié", by=rai)
    assert mission_lancee.etapes.get(numero=6).statut == "A_REVALIDER"
    valider_etape(mission_lancee.etapes.get(numero=10), by=rai)
    assert Mission.objects.get(pk=mission_lancee.pk).statut == "EN_PLANIFICATION"
```
Plus : `test_demarrer_II_exige_les_declarations` ; `test_demarrer_etape_d_une_phase_future_refuse` (XII en EN_PLANIFICATION) ; `test_terminer_II_livrables_manquants` (les trois messages de D7 dans `errors.livrables`) ; `test_terminer_V_renvoie_au_lot_5` ; `test_terminer_I_refuse` ; `test_valider_X_fait_passer_en_accomplissement` ; `test_xiii_valide_et_xiv_termine_passent_en_communication` (dans les deux ordres) ; `test_valideur_auteur_refuse` ; `test_superviseur_valide_VI_pas_XVIII` ; `test_non_applicable_assurance_ou_jalon_refuse` ; `test_retablir` ; `test_evenement_par_transition_avec_motif` ; `test_actions_possibles_par_role_et_statut` (paramétré, mêmes cas que les gardes) ; `test_fiche_de_suivi_totaux_et_requetes` (`django_assert_max_num_queries(3)`) ; `test_reunion_unique_par_type` ; `test_reunion_tenue_exige_compte_rendu_et_date_passee` ; `test_reunion_ouverture_gelee_apres_II` ; `test_entretien_auditeur_hors_equipe_refuse` ; `test_entretien_realise_exige_compte_rendu` ; `test_risque_hors_cartographie_ou_processus_refuse` ; `test_risque_nouveau_et_snapshot` (modifier le risque source en base n'altère pas la copie) ; `test_risques_figes_apres_IV` ; `test_matrice_mission` ; `test_risques_proposes_exclut_annulees`.
- [ ] **Step 2: `pytest tests/missions -v`** → FAIL.
- [ ] **Step 3: Implémenter** les six modules.
- [ ] **Step 4: `pytest tests/missions -v`** → PASS ; `ruff check . && mypy .` → 0.
- [ ] **Step 5: Commit** `feat(missions): add step engine, deliverable checks, tracking sheet, meetings, interviews and mission risks services`.

### Task 5: API REST des missions, annuaire des utilisateurs, contrat OpenAPI

**Model:** sonnet (backend-dev)

**Files:**
- Create: `backend/apps/missions/{permissions,filters,serializers,views,urls}.py`
- Modify: `backend/apps/users/{views,urls,serializers,filters}.py` (annuaire), `backend/config/urls.py` (`include("apps.missions.urls")`), `backend/config/settings/base.py` (`ENUM_NAME_OVERRIDES`), `backend/apps/referentiel/views.py` (rien d'autre que l'import de `crud_schema` si T1 l'a laissé), `frontend/src/api/schema.d.ts` (régénéré)
- Test: `backend/tests/missions/{test_api_permissions,test_api_missions,test_api_equipe,test_api_etapes,test_api_travaux,test_api_contrat}.py`, `backend/tests/users/test_users_directory.py`

**Interfaces:**
- Consumes: services T3/T4, `acces`, `droits_mission`, `actions_possibles` ; `crud_schema`, `ConfirmationResumeSerializer` (T1) ; `CelluleMatriceSerializer`, `ParNiveauSerializer`, `StandardPagination`, `StableOrderingFilter`, `ERROR_*`.
- Produces :
  - `missions.permissions.MissionAccessPermission` : refuse ADMIN et DG (403), et AUDITE sur les routes qui lui sont fermées (D4) ; le champ `mission` d'un POST enfant est résolu par `get_object_or_404(missions_visibles(user), pk=…)` avant le sérialiseur (mission invisible → 404, jamais 400) ; `get_queryset()` de chaque ViewSet filtre par `missions_visibles(user)` (objet invisible → 404) ; chaque action d'écriture appelle `exiger(condition: bool, message: str = FORBIDDEN)` avec **les mêmes** fonctions que `droits_mission` / `actions_possibles` / `peut_contribuer`. Adresse IP lue dans `request.META["REMOTE_ADDR"]`.
  - Endpoints (`http_method_names` sans `put` ; actions en `POST` renvoyant la représentation de lecture) :

| Route | Méthodes | Filtres / tri | Droits (D4) |
|---|---|---|---|
| `/api/v1/users/` | GET | `role`, `direction_code`, `q` (username, prénom, nom) ; `last_name` | RAI, AUDITEUR, ADMIN |
| `/api/v1/missions/` `{id}/` | GET, POST, PATCH, DELETE | `statut`, `type`, `annee`, `processus`, `q` (référence, titre) ; `reference`, `date_debut_prevue`, `created_at` | lecture visibles ; écriture RAI |
| `/api/v1/missions/{id}/plan/` `launch/` `issue-order/` `suspend/` `resume/` `cancel/` | POST (`suspend`, `cancel` : `{motif}` ; `issue-order` : `{confirme: true}`) | — | RAI |
| `/api/v1/missions/{id}/tracking/` | GET | — | RAI, intervenants |
| `/api/v1/missions/{id}/risk-matrix/` | GET | — | RAI, intervenants |
| `/api/v1/missions/{id}/default-auditees/` | GET (non paginé) | — | RAI |
| `/api/v1/mission-assignments/` `{id}/` | GET, POST, DELETE | `mission`, `role_mission` | lecture RAI, intervenants ; écriture RAI |
| `/api/v1/missions/{id}/replace-chief/` | POST `{utilisateur}` | — | RAI |
| `/api/v1/independence-declarations/` `{id}/` | GET | `mission`, `mine` (bool), `statut` | RAI, intervenants (`mine=true` : les siennes) |
| `…/independence-declarations/{id}/confirm/` | POST `{confirme: true, conflit, description_conflit}` | — | l'auditeur concerné |
| `…/independence-declarations/{id}/arbitrate/` | POST `{justification}` | — | RAI |
| `/api/v1/mission-steps/` `{id}/` | GET (liste non paginée, `mission` obligatoire), PATCH (planification) | `mission` | RAI, intervenants ; PATCH RAI ou chef |
| `/api/v1/mission-steps/{id}/start/` `complete/` `validate/` `return/` `reopen/` `not-applicable/` `restore/` | POST (`return`, `reopen`, `not-applicable` : `{motif}`) | — | `actions_possibles` |
| `/api/v1/meetings/` `{id}/` + `{id}/mark-held/` | GET, POST, PATCH, DELETE, POST | `mission`, `type` | lecture visibles (AUDITE inclus) ; écriture `peut_contribuer` |
| `/api/v1/interviews/` `{id}/` + `{id}/mark-done/` `{id}/cancel/` | GET, POST, PATCH, DELETE, POST | `mission`, `etape`, `statut` ; `date_prevue` | lecture RAI, intervenants, AUDITE interlocuteur ; écriture `peut_contribuer` |
| `/api/v1/mission-risks/` `{id}/` | GET, POST, PATCH, DELETE | `mission`, `nouveau` (bool), `niveau`, `processus` ; `score`, `code_source` | RAI, intervenants ; écriture `peut_contribuer` ; `nouveau=true` sans `mission` : RAI seul (`risques_proposes`) |

  - Sérialiseurs (noms = composants OpenAPI) : `UtilisateurResume` {id, username, nom_complet, role, direction_code, fonction} ; `MissionListe` {id, reference, titre, type, statut, phase, chef_mission: UtilisateurResume | null, date_debut_prevue, date_fin_prevue, etape_courante: {numero, romain} | null (plus petite EN_COURS), ma_declaration_en_attente: bool} ; `Mission` {…MissionListe, processus (ids, écriture), processus_detail [{id, code, libelle}], entites, entites_detail [{id, code, libelle}], evenement_declencheur, evenement_precision, periode_debut, periode_fin, budget_jours (chaîne décimale, `null` pour AUDITE), objectifs, perimetre, exclusions, clients, livrables_attendus, cartographie {id, annee} (`null` pour AUDITE), statut_avant_suspension, motif_suspension, motif_annulation (`null` pour AUDITE), ordre_mission: ConfirmationResume | null, ordre_mission_emis_le, equipe [Affectation], mes_droits: DroitsMission, created_at} ; `Affectation` {id, mission, utilisateur (écriture), utilisateur_detail, role_mission, declaration: {id, statut, levee, confirmee_le} | null} ; `Declaration` {id, affectation, mission, mission_reference, mission_titre, utilisateur_detail, role_mission, statut, levee, texte (texte_declaration), description_conflit, confirmation: ConfirmationResume | null, arbitrage_justification, arbitre_par: UtilisateurResume | null, arbitre_le} ; `Etape` {id, mission, numero, romain, titre, phase, jalon, objectif, livrables [str], acteurs, statut, date_debut_prevue, date_fin_prevue, date_debut_reelle, date_fin_reelle, charge_prevue_jours, charge_reelle_jours, terminee_par, validee_par: UtilisateurResume | null, validee_le, motif_non_applicable, actions_possibles [ActionEtapeEnum], livrables_manquants [str] (détail seulement, `[]` en liste), evenements [Evenement {type, par: UtilisateurResume, le, motif, statut_avant, statut_apres}] (détail seulement)} ; `FicheSuivi` {mission {id, reference, titre}, budget_jours, total_prevu, total_reel, lignes [LigneSuivi], evenements [Evenement + etape_romain]} ; `Reunion` {id, mission, type, date, lieu, ordre_du_jour, participants (ids), participants_detail, participants_externes, decisions, compte_rendu, tenue_le, etape_close: bool} ; `Entretien` {id, mission, etape, etape_romain, objet, date_prevue, duree_minutes, lieu, auditeurs, auditeurs_detail, interlocuteurs, interlocuteurs_detail, autres_interlocuteurs, themes, compte_rendu, note_synthese, statut, realise_le, motif_annulation, etape_close} ; `RisqueMission` {id, mission, mission_reference, risque_source, code_source, nouveau, processus, processus_code, libelle, description, probabilite, impact (`IntegerField(1, 5)`), score, niveau, commentaire, probabilite_reference, impact_reference (lecture, depuis la source)} ; `MatriceMission` {mission, total, par_niveau, cellules [CelluleMatrice]} ; `MotifRequest` {motif (1–2000)} ; `ConfirmationRequest` {confirme: `BooleanField` qui doit être vrai, conflit, description_conflit} ; `ArbitrageRequest` {justification} ; `RemplacerChefRequest` {utilisateur}.
  - `ENUM_NAME_OVERRIDES` : `TypeMissionEnum`, `StatutMissionEnum`, `EvenementDeclencheurEnum`, `RoleMissionEnum`, `PhaseEnum`, `StatutEtapeEnum`, `TypeEvenementEtapeEnum`, `StatutDeclarationEnum`, `TypeReunionEnum`, `StatutEntretienEnum`, `ActionEtapeEnum`, `TypeDocumentSignableEnum`.
  - Chaque action documentée par `@extend_schema` (`ERROR_400`, `ERROR_RESPONSES`, `ERROR_404`, `ERROR_422`) ; `crud_schema` pour les CRUD. **Contrat consommé par T6–T9 ; figé à la fin de cette tâche.**

- [ ] **Step 1: Écrire les tests**
```python
@pytest.mark.parametrize("qui,lire,ecrire_reunion,valider_VI", [
    ("rai", 200, 201, 200), ("chef", 200, 201, 403), ("superviseur", 200, 201, 200),
    ("auditeur_non_confirme", 200, 403, 403), ("auditeur_non_affecte", 404, 404, 404),
    ("audite_affecte", 200, 403, 403), ("admin", 403, 403, 403), ("dg", 403, 403, 403)])
def test_matrice_droits_missions(api_client, equipe_complete, qui, lire, ecrire_reunion, valider_VI):
    m, users = equipe_complete
    api_client.force_authenticate(users[qui])
    assert api_client.get(f"/api/v1/missions/{m.id}/").status_code == lire
    r = api_client.post("/api/v1/meetings/", {"mission": str(m.id), "type": "OUVERTURE",
                        "date": "2026-03-02T09:00:00Z"}, format="json")
    assert r.status_code == ecrire_reunion
    e6 = m.etapes.get(numero=6)
    assert api_client.post(f"/api/v1/mission-steps/{e6.id}/validate/").status_code == valider_VI
```
(`equipe_complete`, fixture locale au module : mission EN_PLANIFICATION, chef, superviseur et auditeur confirmés, un auditeur non confirmé, un audité affecté, VI TERMINEE par le chef ; `ECRITURES_PILOTAGE` et `_dans_un_thread` de T3 sont aussi locaux à leurs modules.) Plus : `test_mes_droits_concorde_avec_les_permissions` (pour chaque utilisateur, chaque droit vrai de `mes_droits` → l'appel correspondant ne renvoie pas 403, chaque droit faux → 403 ou 422) ; `test_actions_possibles_concorde_avec_les_routes` (idem par étape) ; `test_api_gel_422_sur_chaque_route_enfant` (mission suspendue : POST/PATCH/DELETE sur assignments, meetings, interviews, mission-risks, PATCH mission-steps et chaque action d'étape → 422 avec le `detail` de `MissionFigeeError`) ; `test_erreurs_au_format_unique` (404 d'une mission invisible, 400 `processus.0` UUID invalide, 422 `errors.cartographie`, 403 non confirmé : tous `{detail, errors}`) ; `test_audite_champs_internes_nuls_et_403_sur_etapes` ; `test_audite_ne_voit_que_ses_entretiens` ; `test_issue_order_sans_confirme_400` ; `test_confirm_declaration_d_un_autre_403` ; `test_mission_steps_sans_mission_400_et_18_lignes` ; `test_new_risks_rai_seul` ; `test_users_directory_droits_et_filtres` (AUDITE 403 ; `?role=AUDITEUR&q=oued`) ; `test_listes_requetes_bornees` (`django_assert_max_num_queries` : missions 6 pour 30 missions, mission-steps 4, meetings 4, interviews 5, mission-risks 3) ; `test_page_size_plafonne` ; `test_api_contrat_fiche_suivi` (JSON exact d'une fiche à deux lignes, `ecart_jours` 3 et -2, sauvegardé tel quel dans le test et recopié dans les fixtures MSW de T8) ; `test_schema_expose_les_routes_missions`.
- [ ] **Step 2: `pytest tests/missions tests/users -v`** → FAIL.
- [ ] **Step 3: Implémenter** permission, filtres, sérialiseurs, ViewSets (`select_related` / `prefetch_related` sur équipe, chef, processus, entités, participants), routeur `SimpleRouter`, annuaire.
- [ ] **Step 4: `pytest -v`** → PASS ; `python manage.py spectacular --validate` → 0 avertissement ; `sh scripts/gen-api.sh && sh scripts/check-api-fresh.sh` → OK après commit ; `ruff check . && mypy .` → 0.
- [ ] **Step 5: Commit** `feat(missions): expose role-gated rest api for missions, steps, meetings, interviews and mission risks`.

### Task 6: Fondations frontend des missions

**Model:** sonnet (frontend-dev). Dépend seulement du `schema.d.ts` de T5.

**Files:**
- Create: `frontend/src/api/allPages.ts`, `frontend/src/api/formErrors.ts`, `frontend/src/components/form/{FormField,NativeSelect}.tsx`, `frontend/src/components/ListIncompleteAlert.tsx`, `frontend/src/features/missions/{api,types,labels,keys}.ts`, `frontend/src/features/missions/components/{MissionStatusBadge,StepStatusBadge,MissionStepper,MissionHeader,MissionLayout,MotifDialog,ConfirmActionDialog,UserPicker}.tsx`, `frontend/src/features/missions/routes.tsx`, `frontend/src/features/missions/pages/{MissionListPage,MissionFormPage,StepPage,TeamPage,MeetingsPage,InterviewsPage,TrackingPage}.tsx` (squelettes), `frontend/src/features/missions/zones/{index.ts,StepIZone,StepIIZone,StepIIIZone,StepIVZone,GenericZone}.tsx` (squelettes), `frontend/src/features/missions/testUtils.tsx`
- Modify: `frontend/src/features/referentiel/**` (imports vers `api/allPages`, `api/formErrors`, `components/form/*`, `components/ListIncompleteAlert` ; supprimer `riskServerErrors.ts` et les anciens fichiers s'ils n'ont pas déjà été fusionnés par la vague de corrections du lot 2), `frontend/src/routes.tsx`, `frontend/src/layouts/{navigation.ts,Breadcrumbs.tsx}`, `frontend/src/i18n/fr.ts`
- Test: `frontend/src/features/missions/{api,labels}.test.ts(x)`, `frontend/src/features/missions/components/{MissionStepper,MissionHeader,UserPicker}.test.tsx`, `frontend/src/api/allPages.test.ts`, `frontend/src/layouts/Breadcrumbs.test.tsx`, `frontend/src/routes.test.tsx`

**Interfaces:**
- Consumes: `components["schemas"]` de T5 (`Mission`, `MissionListe`, `DroitsMission`, `Affectation`, `Declaration`, `Etape`, `FicheSuivi`, `Reunion`, `Entretien`, `RisqueMission`, `MatriceMission`, `UtilisateurResume`, `Paginated…List`, énumérations) ; `apiFetch`, `toQuery`, `DataTable`, `EmptyState`, `RiskMatrix`, `useRole`, `rolesFor`.
- Produces:
  - `api/allPages.ts` : `fetchAllPages<T>(resource: string, params?: QueryParams): Promise<{ results: T[]; count: number }>` (déplacé, `MAX_PAGES = 50`, `page_size = 200`) ; `api/formErrors.ts` : `applyApiErrors<T>(error, setError, fields): string | null` (focus sur le premier champ en erreur).
  - `features/missions/api.ts` : `missionKeys` (racine `["missions"]`) ; `useMissions(params)`, `useMission(id)`, `useSaveMission()` (`{id?, data}`), `useDeleteMission()`, `useMissionTransition()` (`{id, action: "plan" | "launch" | "issue-order" | "suspend" | "resume" | "cancel", body?}`), `useDefaultAuditees(id)`, `useAllUsers(params)`, `useAssignments(missionId)`, `useAssign()`, `useUnassign()`, `useReplaceChief()`, `useDeclarations(params)`, `useConfirmDeclaration()`, `useArbitrateDeclaration()`, `useSteps(missionId)`, `useStep(id)`, `useStepAction()` (`{id, action: "start" | "complete" | "validate" | "return" | "reopen" | "not-applicable" | "restore", motif?}`), `useUpdateStepPlanning()`, `useTracking(missionId)`, `useMeetings(missionId)`, `useSaveMeeting()`, `useDeleteMeeting()`, `useMarkMeetingHeld()`, `useInterviews(params)`, `useSaveInterview()`, `useDeleteInterview()`, `useInterviewAction()` (`"mark-done" | "cancel"`), `useMissionRisks(missionId)`, `useSaveMissionRisk()`, `useDeleteMissionRisk()`, `useMissionMatrix(missionId)`, `useProposedRisks()`. Les listes enfants passent par `fetchAllPages`. **Règle d'invalidation** : toute mutation d'un objet de mission invalide `missionKeys.detail(missionId)`, `steps`, `tracking` et sa propre liste (statut, phase et droits peuvent changer).
  - `labels.ts` : libellés français de toutes les énumérations de T5 ; `PHASE_LABELS` ; `ACTION_LABELS` (« Commencer l'étape », « Terminer l'étape », « Valider le jalon », « Renvoyer », « Rouvrir l'étape », « Marquer non applicable », « Rétablir l'étape »).
  - `MissionStepper` props `{ steps: Etape[]; missionId: string; selected?: number }` : trois `<section>` titrées (phase + étendue « I–X ») contenant chacune une `<ol>` ; chaque étape est un lien `/missions/:id/etapes/:numero` avec `aria-current="step"` si sélectionnée, numéro romain, titre, `StepStatusBadge` (texte + point), mention « Jalon » ; étapes d'une phase future en grisé lisible (contraste AA) ; coche pour VALIDEE.
  - `MissionHeader` props `{ mission: Mission }` : référence (ou « Brouillon »), titre, `MissionStatusBadge`, phase, dates prévues, chef et équipe ; menu d'actions construit **uniquement** depuis `mission.mes_droits` (T7 branche les actions) ; bandeau « Confirmez votre déclaration d'indépendance pour contribuer à la mission. » si `mes_droits.confirmer_ma_declaration`.
  - `MissionLayout` : `MissionHeader`, onglets `NavLink` (Étapes, Équipe, Réunions, Entretiens, Fiche de suivi ; seulement Réunions et Entretiens si `mes_droits.voir_travaux` est faux), `<Outlet />`, panneau latéral « Documents » avec « Les documents de la mission seront disponibles au lot 4. ».
  - `MotifDialog` (`AlertDialog`, textarea motif obligatoire, 422 affiché dans la boîte sans la fermer) ; `ConfirmActionDialog` (`AlertDialog`, texte à confirmer, case « Je confirme » obligatoire) ; `UserPicker` props `{ role: RoleEnum; value: string[]; onChange; exclude?: string[]; label: string }` (charge tout par `useAllUsers`, filtre local, `ListIncompleteAlert`).
  - `routes.tsx` : `missionRoutes` montées sous `guarded("/missions", …)` : index → `MissionListPage` ; `nouvelle` → `MissionFormPage` ; `:id` → `MissionLayout` { index → `Navigate` vers `etapes/<etape_courante ou 1>` (AUDITE : `reunions`) ; `modifier` → `MissionFormPage` ; `etapes/:numero` → `StepPage` ; `equipe` → `TeamPage` ; `reunions` → `MeetingsPage` ; `entretiens` → `InterviewsPage` ; `suivi` → `TrackingPage` }. `zones/index.ts` : `ZONES: Record<number, ComponentType<{ mission: Mission; step: Etape }>>` (1 → `StepIZone`, 2 → `StepIIZone`, 3 → `StepIIIZone`, 4 → `StepIVZone`, autres → `GenericZone`).
  - `navigation.ts` : `ROUTE_ROLES["/missions"] = ["RAI", "AUDITEUR", "AUDITE"]` ; `SEGMENT_LABELS` : nouvelle, modifier, etapes (« Étapes »), equipe, reunions, entretiens, suivi (« Fiche de suivi ») ; `Breadcrumbs` affiche « Étape IV » pour un segment numérique après `etapes`.
  - `fr.ts` : section `missions` (titres, champs, statuts, messages communs, « Version 0.3 · lot 3 ») et trois sections vides `missionPilotage: {}`, `missionEtapes: {}`, `missionTravaux: {}` à des endroits distincts du fichier (remplies par T7, T8, T9).
  - `testUtils.tsx` : `renderMission(path, role, { me?, handlers })`, fabriques typées `aMission(overrides): Mission`, `aStep(overrides): Etape`, `allRights(false|true): DroitsMission` (`satisfies` le schéma).

- [ ] **Step 1: Écrire les tests** : `MissionStepper` — 3 sections, 18 liens, `aria-current="step"` sur l'étape IV sélectionnée, texte « Validée » et « Jalon » présents, `axe` sans violation ; `MissionHeader` — avec `allRights(false)` aucun bouton d'action, avec `{...allRights(false), lancer: true}` seul « Lancer la mission » ; bandeau de déclaration ; `fetchAllPages` suit deux pages ; `useSteps` appelle `/api/v1/mission-steps/?mission=…` ; invalidation de `missionKeys.detail` après `useStepAction` ; fil d'Ariane de `/missions/<uuid>/etapes/4` = « Tableau de bord › Missions › Détail › Étapes › Étape IV » ; routes : DG et ADMIN sur `/missions` voient l'accès refusé, AUDITE sur `/missions/<id>` arrive sur `reunions` ; les tests du référentiel restent verts après les déplacements.
- [ ] **Step 2: `cd frontend && npm test`** → FAIL.
- [ ] **Step 3: Implémenter** déplacements, modules, composants, routes, squelettes.
- [ ] **Step 4: `npm test && npm run typecheck && npm run lint && npm run format:check`** → PASS.
- [ ] **Step 5: Commit** `feat(frontend): add mission api hooks, stepper, header, layout and routes`.

### Task 7: Écrans de pilotage — liste, création, équipe, déclarations, cycle de vie, étape I

**Model:** sonnet (frontend-dev), en parallèle de T8 et T9.

**Files:**
- Modify: `frontend/src/features/missions/pages/{MissionListPage,MissionFormPage,TeamPage}.tsx`, `frontend/src/features/missions/zones/StepIZone.tsx`, `frontend/src/features/missions/components/MissionHeader.tsx` (actions), `frontend/src/i18n/fr.ts` (section `missionPilotage` seulement)
- Create: `frontend/src/features/missions/schemas/mission.ts`, `frontend/src/features/missions/components/{MissionActions,DeclarationDialog,AssignDialog,ArbitrateDialog}.tsx`
- Test: `frontend/src/features/missions/pages/{MissionListPage,MissionFormPage,TeamPage}.test.tsx`, `frontend/src/features/missions/zones/StepIZone.test.tsx`, `frontend/src/features/missions/components/{MissionActions,DeclarationDialog}.test.tsx`

**Interfaces:**
- Consumes: hooks, composants, `testUtils` (T6) ; `useAllProcesses`, `useAllDirections` (référentiel).
- Produces:
  - `MissionListPage` : `DataTable` (Référence, Titre, Type, Statut, Phase, Chef de mission, Début prévu, Fin prévue), filtres statut, type, année, recherche reflétés dans l'URL (anti-rebond 300 ms, `keepPreviousData` limité aux mêmes filtres) ; pastille « Déclaration à confirmer » si `ma_declaration_en_attente` ; « Créer une mission » si rôle RAI. États vides : RAI « Aucune mission n'est encore enregistrée. » + action ; AUDITEUR « Vous n'êtes affecté à aucune mission. » ; AUDITE « Aucune mission ne concerne votre entité pour le moment. ».
  - `MissionFormPage` (création / modification) : sections « Identification » (titre 300, type), « Périmètre » (processus et entités en cases à cocher, toutes pages chargées ; événement déclencheur + précision ; période auditée), « Calendrier » (dates prévues, budget en jours ≥ 0), « Objectifs et livrables » (objectifs, périmètre, exclusions, clients, livrables attendus) ; zod : dates de fin ≥ dates de début (« La date de fin doit suivre la date de début. ») ; champs D17 désactivés (non grisés à 50 %) avec l'aide « Figé par l'ordre de mission : rouvrez l'étape I pour le modifier. » quand l'étape I est close ; 400/422 par `applyApiErrors` (focus) ; 422 `cartographie` affiché en alerte avec lien vers « Référentiel › Cartographies ».
  - `MissionActions` (dans l'en-tête, depuis `mes_droits`) : « Planifier la mission », « Lancer la mission », « Suspendre la mission » (`MotifDialog`), « Reprendre la mission », « Annuler la mission » (`MotifDialog`, texte d'irréversibilité « Une mission annulée ne peut plus être modifiée ni reprise. »), « Supprimer le brouillon » (`ConfirmActionDialog`), « Modifier » ; erreurs 422 dans la boîte (champs manquants de `planifier` listés).
  - `TeamPage` : tableau de l'équipe (Nom, Fonction, Rôle dans la mission, Déclaration : « En attente », « Confirmée le JJ/MM/AAAA », « Situation déclarée », « Arbitrée ») ; RAI : `AssignDialog` (rôle + `UserPicker` filtré sur AUDITEUR ou AUDITE, audités par défaut pré-cochés depuis `useDefaultAuditees`), « Retirer de la mission », « Remplacer le chef de mission », `ArbitrateDialog` sur une situation déclarée.
  - `DeclarationDialog` (ouvert depuis le bandeau de l'en-tête ou la ligne de l'utilisateur) : texte serveur `declaration.texte` affiché tel quel, choix « Je confirme cette déclaration » / « Je déclare une situation susceptible d'affecter mon indépendance » (description obligatoire), bouton « Confirmer la déclaration » ; après succès : « Déclaration confirmée le JJ/MM/AAAA à HH:MM. Empreinte : 3f2a…9c1b ».
  - `StepIZone` : rappel objectifs, périmètre, équipe, dates (lecture) avec lien « Modifier la mission » si `mes_droits.modifier` ; « Émettre l'ordre de mission » (RAI, étape I ouverte) via `ConfirmActionDialog` qui affiche le texte de D10 ; une fois émis : « Ordre de mission émis le … par … », empreinte, mention « Le document Word sera généré au lot 4. ».

- [ ] **Step 1: Écrire les tests** (MSW typé) : création envoie `{"titre": "Audit du processus de passation des marchés", "type": "ASSURANCE", "processus": [id], "entites": [id], "date_debut_prevue": "2026-03-02", "date_fin_prevue": "2026-05-29", …}` ; 422 `cartographie` → alerte et focus sur le premier champ ; fin avant début bloquée côté client ; champs D17 désactivés quand l'étape I est TERMINEE ; liste vide par rôle ; `MissionActions` n'affiche que les droits vrais (RAI sur PLANIFIEE : « Lancer » présent, « Planifier » absent) ; annulation : motif vide refusé, 422 affiché dans la boîte ; `TeamPage` : **201 utilisateurs sur deux pages MSW tous proposés** dans le sélecteur ; audités par défaut pré-cochés ; déclaration : confirmation envoie `{"confirme": true, "conflit": false, "description_conflit": ""}`, situation sans description bloquée ; `StepIZone` : émission confirmée → POST `issue-order/` puis bandeau « Ordre de mission émis » ; `axe` sans violation, dialogues ouverts compris.
- [ ] **Step 2: `npm test`** → FAIL.
- [ ] **Step 3: Implémenter** pages, schémas, composants, libellés `missionPilotage`.
- [ ] **Step 4: `npm test && npm run typecheck && npm run lint`** → PASS ; revue visuelle `ui-designer` (écran 1280/1024, impression de la liste et de l'en-tête) : 0 correction majeure.
- [ ] **Step 5: Commit** `feat(frontend): add mission list, form, team, independence declaration and lifecycle screens`.

### Task 8: Écrans du stepper — page d'étape, actions, étape IV, fiche de suivi, risques proposés

**Model:** sonnet (frontend-dev), en parallèle de T7 et T9.

**Files:**
- Modify: `frontend/src/features/missions/pages/{StepPage,TrackingPage}.tsx`, `frontend/src/features/missions/zones/{StepIVZone,GenericZone}.tsx`, `frontend/src/features/referentiel/pages/RiskMapDetailPage.tsx` (panneau des risques proposés), `frontend/src/i18n/fr.ts` (section `missionEtapes` seulement)
- Create: `frontend/src/features/missions/components/{StepActions,StepPlanningForm,StepJournal,MissionRiskDialog,ProposedRisksPanel}.tsx`, `frontend/src/features/missions/schemas/{stepPlanning,missionRisk}.ts`
- Test: `frontend/src/features/missions/pages/{StepPage,TrackingPage}.test.tsx`, `frontend/src/features/missions/zones/StepIVZone.test.tsx`, `frontend/src/features/referentiel/components/ProposedRisksPanel.test.tsx`

**Interfaces:**
- Consumes: hooks, `MissionStepper`, `ZONES`, `MotifDialog`, `ConfirmActionDialog`, `testUtils` (T6) ; `RiskMatrix` (prop `onSelect`, `size="large"`), `RiskLevelBadge`, `fetchAllPages("risks", {version, processus})` (référentiel) ; fixture JSON de `test_api_contrat_fiche_suivi` (T5).
- Produces:
  - `StepPage` : stepper à gauche, à droite l'en-tête d'étape (« Étape IV — Identifier et évaluer les risques », phase, `StepStatusBadge`, « Jalon validé par le RAI » si jalon), objectif IFACI, livrables attendus avec, pour chaque livrable manquant de `livrables_manquants`, une ligne « Manquant : … » ; `StepActions` (boutons **seulement** depuis `actions_possibles` : « Valider le jalon » en `ConfirmActionDialog`, « Renvoyer », « Rouvrir l'étape », « Marquer non applicable » en `MotifDialog` ; 422 `errors.livrables` affiché en liste dans une alerte) ; `StepPlanningForm` si `PLANIFIER` ∈ `actions_possibles` (dates prévues, charges prévue et réelle) ; la zone `ZONES[numero]` ; `StepJournal` (événements : date-heure, auteur, action, motif). Numéro hors 1–18 → page « Étape introuvable ».
  - `GenericZone` : « Les formulaires de cette étape seront disponibles au lot {lot_livrables}. » + livrables attendus.
  - `StepIVZone` : tableau des risques de mission (Code, Risque, Processus, P, I, Score, Niveau, Évaluation de référence « P×I » si réévalué, actions) ; « Sélectionner des risques de la cartographie {année} » (dialogue listant **tous** les risques de la cartographie de la mission filtrés par processus de la mission, cases à cocher, déjà sélectionnés désactivés) ; « Ajouter un risque nouveau » (`MissionRiskDialog` : processus de la mission, libellé, description, P, I, aperçu « Score 15 · Élevé ») ; réévaluation P/I/commentaire ; `RiskMatrix size="large"` alimentée par `useMissionMatrix`, clic sur une case → filtre du tableau (paramètres d'URL `probabilite`, `impact`) ; lecture seule si l'étape est close ou sans droit `contribuer`.
  - `TrackingPage` (« Fiche de suivi de la mission ») : bloc budget (« Budget : 40 j · Prévu : 38 j · Réalisé : 12,5 j »), tableau par phase (Étape, Statut, Début prévu, Fin prévue, Début réel, Fin réelle, Écart, Charge prévue, Charge réelle) ; écart affiché « 3 j de retard » (positif), « 2 j d'avance » (négatif), « À l'heure » (0), « — » (null) ; journal chronologique ; rendu print (en-tête référence de mission, sans actions).
  - `ProposedRisksPanel` (dans `RiskMapDetailPage`, RAI, cartographie en brouillon) : « Risques proposés par les missions ({n}) », tableau (Mission, Processus, Risque, P×I, Niveau), lecture seule, lien vers la mission.

- [ ] **Step 1: Écrire les tests** (MSW typé, fiche de suivi issue de la fixture de T5) : ligne de l'étape IV « 3 j de retard », étape III « 2 j d'avance » ; RAI sur VI TERMINEE → « Valider le jalon » présent, chef → absent (`actions_possibles` vide de VALIDER) ; « Terminer l'étape » sur II renvoie 422 → les trois livrables manquants listés ; « Rouvrir l'étape » exige un motif ; sélection : **risques de cartographie sur deux pages MSW (201) tous listés**, POST `mission-risks/` avec `risque_source` ; risque nouveau P 3 × I 5 → aperçu « Score 15 · Élevé » ; clic sur la case (3, 5) filtre le tableau ; étape IV TERMINEE → aucun bouton d'écriture ; `ProposedRisksPanel` absent pour une cartographie validée ; `axe` sans violation (dialogues ouverts).
- [ ] **Step 2: `npm test`** → FAIL.
- [ ] **Step 3: Implémenter** pages, zones, composants, libellés `missionEtapes`.
- [ ] **Step 4: `npm test && npm run typecheck && npm run lint`** → PASS ; revue visuelle `ui-designer` (stepper, matrice, fiche de suivi à l'écran et en impression A4) : 0 correction majeure.
- [ ] **Step 5: Commit** `feat(frontend): add step page, step actions, mission risk map, tracking sheet and proposed risks panel`.

### Task 9: Écrans des travaux — réunions, entretiens, zones des étapes II et III, vue de l'audité

**Model:** sonnet (frontend-dev), en parallèle de T7 et T8.

**Files:**
- Modify: `frontend/src/features/missions/pages/{MeetingsPage,InterviewsPage}.tsx`, `frontend/src/features/missions/zones/{StepIIZone,StepIIIZone}.tsx`, `frontend/src/i18n/fr.ts` (section `missionTravaux` seulement)
- Create: `frontend/src/features/missions/components/{MeetingCard,MeetingFormDialog,InterviewTable,InterviewFormDialog}.tsx`, `frontend/src/features/missions/schemas/{meeting,interview}.ts`
- Test: `frontend/src/features/missions/pages/{MeetingsPage,InterviewsPage}.test.tsx`, `frontend/src/features/missions/zones/{StepIIZone,StepIIIZone}.test.tsx`

**Interfaces:**
- Consumes: hooks, `UserPicker`, `ConfirmActionDialog`, `MotifDialog`, `testUtils` (T6).
- Produces:
  - `MeetingsPage` : trois `MeetingCard` (ouverture, lancement, clôture) : « Planifier la réunion » si absente et `mes_droits.contribuer` ; sinon date, lieu, participants, ordre du jour, décisions, compte rendu, statut « Prévue » / « Tenue le JJ/MM/AAAA » ; « Marquer comme tenue » (`ConfirmActionDialog`) ; mention « Le PV sera généré au lot 4. » ; carte en lecture seule si `etape_close`.
  - `MeetingFormDialog` : date et heure, lieu, ordre du jour, participants internes (`UserPicker` tous rôles), participants externes (une ligne par personne, aide « Nom — fonction — organisation »), décisions, compte rendu ; zod : date requise.
  - `InterviewsPage` : `InterviewTable` (Date, Objet, Étape, Interlocuteurs, Auditeurs, Statut, actions) triée par date, filtre statut ; « Planifier un entretien » ; actions « Saisir le compte rendu », « Marquer comme réalisé », « Annuler l'entretien » (`MotifDialog`) ; impression = « Planning des entretiens » (en-tête référence de mission).
  - `InterviewFormDialog` : objet (300), date et heure, durée (minutes, 1–600), lieu, étape (étapes de la mission), auditeurs (équipe de la mission seulement), interlocuteurs internes (`UserPicker` AUDITE et autres), autres interlocuteurs, thèmes, compte rendu, note de synthèse.
  - `StepIIZone` : réunion d'ouverture (`MeetingCard` OUVERTURE), « Calendrier des premiers entretiens » (`InterviewTable` filtré `etape` = II ou à venir), état des déclarations de l'équipe (lien vers Équipe).
  - `StepIIIZone` : entretiens rattachés à l'étape III + « Le questionnaire de prise de connaissance et la description des processus seront disponibles au lot 5. ».
  - Vue AUDITE : `MeetingsPage` et `InterviewsPage` en lecture seule (aucun bouton), entretiens limités à ceux où il est interlocuteur (filtrage serveur).

- [ ] **Step 1: Écrire les tests** (MSW typé) : planifier l'ouverture envoie `{"mission": id, "type": "OUVERTURE", "date": "2026-03-02T09:00:00+00:00", "participants": [ids], "participants_externes": "Mme Kaboré — Directrice — DCL"}` ; « Marquer comme tenue » sans compte rendu → 422 affiché ; carte en lecture seule quand `etape_close` ; entretien : auditeur hors équipe absent du sélecteur, durée 0 refusée côté client, réalisé sans compte rendu → 422 ; annulation exige un motif ; AUDITE : aucune action visible ; zone II : déclarations en attente signalées ; impression du planning sans boutons ; `axe` sans violation (dialogues ouverts).
- [ ] **Step 2: `npm test`** → FAIL.
- [ ] **Step 3: Implémenter** pages, zones, composants, libellés `missionTravaux`.
- [ ] **Step 4: `npm test && npm run typecheck && npm run lint`** → PASS ; revue visuelle `ui-designer` : 0 correction majeure.
- [ ] **Step 5: Commit** `feat(frontend): add meetings, interviews, step II and III zones and auditee read-only views`.

### Task 10: Parcours e2e, documentation, vérification du lot

**Model:** sonnet (test-engineer).

**Files:**
- Create: `frontend/e2e/missions.spec.ts`
- Modify: `frontend/e2e/api.ts` (préparation et nettoyage missions), `backend/README.md` (section « Missions »), `backend/config/__init__.py`, `backend/pyproject.toml`, `frontend/package.json` (`0.3.0`), `frontend/src/api/schema.d.ts` (régénéré pour la version)

**Interfaces:**
- Consumes: tout le lot ; comptes Keycloak de dev `rai`, `auditeur1`, `audite1` / `onea2026`.
- Produces: `e2e/api.ts` : `ensureValidatedRiskMap(token)` (si `version_courante` absente : cartographie 2097 + processus `ZZM` + un risque, validée par l'API) ; `provisionUsers()` (appelle `/api/v1/me/` avec chaque compte pour créer l'utilisateur Django) ; `cleanupMissions()` : suppression logique SQL (même mécanisme que le lot 2) des missions dont le titre commence par « E2E — » et de leurs objets, **refusée sauf si `E2E_ALLOW_DB_CLEANUP=1`** et le service compose `db` de dev est joignable (leçon M8).

- [ ] **Step 1: Écrire `missions.spec.ts`** : `beforeAll` → `provisionUsers`, `ensureValidatedRiskMap`, `cleanupMissions` ; RAI : crée « E2E — Audit de la gestion des achats » (assurance, un processus, une entité, dates), affecte `auditeur1` chef de mission et `audite1` audité, planifie (référence `DAI/AAAA/Mnn` affichée), lance, émet l'ordre de mission (dialogue de confirmation) → étape I « Terminée » ; `auditeur1` : bandeau de déclaration, confirme, commence l'étape II, planifie et tient la réunion d'ouverture, planifie un entretien, termine l'étape II ; commence l'étape IV, ajoute un risque nouveau P 3 × I 5, la case « Probabilité 3, impact 5 » affiche 1, termine l'étape IV ; la fiche de suivi montre I, II, IV « Terminée » ; `audite1` : voit la mission et la réunion d'ouverture, pas l'onglet « Étapes ».
- [ ] **Step 2: `make up && make backend` puis `cd frontend && E2E_ALLOW_DB_CLEANUP=1 npx playwright test e2e/missions.spec.ts`** → PASS ; seconde exécution → PASS (idempotence).
- [ ] **Step 3: Documenter** dans `backend/README.md` : cycle de vie (D2), matrice des droits (D4), livrables vérifiés et lots (D7), mode « confirmation » et vérification d'empreinte (D10), prérequis « une cartographie validée » ; passer la version à 0.3.0 partout et régénérer le schéma.
- [ ] **Step 4: Vérification complète** : `make lint && make test && make check-api && make e2e` → vert ; `python manage.py makemigrations --check --dry-run` → aucun changement ; couverture backend ≥ 85 %, frontend ≥ 80 %.
- [ ] **Step 5: Commit** `test(e2e): cover mission planning flow; docs: document missions lifecycle, rights and confirmation`.

---

## Critère de fin du lot 3

Sur une base où une cartographie est validée : le RAI crée une mission, constitue l'équipe (audités proposés par direction), la planifie (référence unique même en concurrence), la lance et émet l'ordre de mission par confirmation horodatée vérifiable ; chaque auditeur confirme sa déclaration avant de contribuer ; l'équipe tient la réunion d'ouverture, planifie et réalise des entretiens, sélectionne et évalue les risques de la mission sur la matrice ; les étapes I, II et IV se terminent sur leurs livrables, les autres renvoient au lot qui les gère ; réouverture, renvoi, validation par le RAI ou le superviseur et « non applicable » (conseil) suivent D8 et apparaissent dans la fiche de suivi ; une mission suspendue ou annulée n'accepte plus aucune écriture ; l'audité ne voit que son périmètre, l'ADMIN et le DG n'accèdent pas aux missions ; chaque action figure dans `/api/v1/audit-log/` ; `make lint && make test && make check-api && make e2e` verts.
