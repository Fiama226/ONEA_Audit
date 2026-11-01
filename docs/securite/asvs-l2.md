# Revue de sécurité OWASP ASVS 4.0.3 niveau 2 (lot 9, tâche 27)

Version relue : branche `develop` au commit `d99a03f` (worktree `feat/lot9-t27`).
Statut du document : **en cours**. Les constats sont ajoutés au fil de la revue ; le tableau
ASVS complet et l'analyse dynamique (ZAP) suivent.

Méthode : lecture du code et de la configuration ; chaque constat est confirmé par la lecture
du code, par un script ou par un test qui échoue. L'analyse dynamique se fait uniquement sur une
instance jetable (conteneurs `l9t27-*`, ports 15433, 16380 et 18181, base `onea_l9t27`), jamais
sur la pile de développement ni sur la recette.

Gravités : critique, élevé, moyen, faible. Les corrections sont à faire en T29.

## Constats

### SEC-01 — Élevé — Un UUID envoyé sous forme d'entier JSON contourne le contrôle d'accès à la création

**Où.**
- `backend/apps/missions/permissions.py:50-63` (`mission_du_corps`) :
  `identifiant = UUID(str(brut))` puis `except ValueError: return None`. Le commentaire dit
  « Champ absent ou illisible : `None`, le sérialiseur répondra 400 ».
- `backend/apps/missions/serializers.py:86-97` (`CleRelation`) : le `pk_field` est un
  `serializers.UUIDField()` de DRF. Ce champ accepte aussi un entier : `uuid.UUID(int=data)`.
- La même garde `_uuid(brut)` (`UUID(str(brut))` / `return None`) existe dans
  `accomplissement/views.py:81-91,104,623`, `analyse/views.py:60-64,87,186`,
  `communication/views.py:137,249,281`, `constats/views.py:70`,
  `recommandations/views.py:68,200,282,371` et `suivi/views.py:523,548`.

**Mécanisme (confirmé par script, sans base).** Pour `n = uuid.uuid4().int`, `UUID(str(n))`
lève `ValueError`, donc la garde renvoie `None` et ne fait **aucun** contrôle : ni visibilité
(404), ni contribution ou déclaration d'indépendance (403). Or
`serializers.UUIDField().to_internal_value(n)` renvoie bien l'UUID d'origine. Le sérialiseur
(`CleRelation(queryset=Mission.objects.all())`) résout ensuite la mission **sans borne de
visibilité**, et les services (`creer_reunion`, `creer_entretien`, `ajouter_risque_mission`,
`ajouter_question`, `engager`, etc.) ne contrôlent que l'état (gel, statut), pas le rôle de
l'acteur dans la mission.

**Scénarios d'exploitation.**
1. Un AUDITEUR affecté dont la déclaration d'indépendance n'est pas levée envoie
   `POST /api/v1/meetings/ {"mission": 1234…(int de l'UUID), "type": "OUVERTURE", …}`. Il
   devrait recevoir 403 « Confirmez votre déclaration ». Il obtient 201. Le contrôle
   d'indépendance (normes IIA) est contourné. Même chose sur les autres routes de création qui
   passent par `creer_pour_mission` (`missions/views.py:151-155`) : entretiens, risques de
   mission, questionnaires, lignes MARC, objectifs, forces et faiblesses, questions.
2. Un AUDITEUR non affecté, ou une mission encore en BROUILLON, dont l'UUID est connu (liens,
   exports, journaux) : l'auditeur écrit dans la mission B au lieu de recevoir 404. Effet
   secondaire : `_publier` relit l'objet par `get_queryset()` et lève `DoesNotExist`, d'où un
   500, alors que l'écriture est déjà validée (pas d'`ATOMIC_REQUESTS`).
3. `recommandations/views.py:280-290` (`EngagementViewSet.create`) : un AUDITE envoie la
   mission en entier, et `exiger(droits.contexte_plan(mission, acteur).audite)` est sauté.
   Il peut alors engager un plan d'actions sur une mission où il n'est pas l'audité
   (à confirmer de bout en bout, voir T29).

Limite : il faut connaître l'UUID de la mission ou du parent. Les UUID ne se devinent pas,
mais ils circulent. Les rôles ADMIN et DG restent refusés par `MissionAccessPermission`
(`missions/permissions.py:66-78`).

**Correction proposée (T29).**
1. Une seule fonction partagée (dans `apps/core`) qui résout l'identifiant du corps avec **le
   même** `UUIDField` que le sérialiseur, ou qui exige `isinstance(brut, str)` et répond 400
   sinon. Elle remplace `mission_du_corps` et tous les `_uuid` locaux.
2. Mieux : faire le contrôle de visibilité et de contribution **après** la validation, sur
   `serializer.validated_data["mission"]` (dans `perform_create` ou `validate_mission`), pour
   qu'aucun écart d'analyse entre la garde et le sérialiseur ne soit possible.
3. Défense en profondeur : un `CleRelation` qui refuse les entiers. Les services d'écriture
   revérifient `peut_contribuer`.
4. Tests : ajouter le cas `"mission": int(uuid)` (et `"questionnaire"`, `"fiche"`,
   `"constat"`…) à chaque matrice de droits (`backend/tests/*/test_api_permissions.py`).
   Réponse attendue : 404 si la mission n'est pas visible, 403 si la déclaration n'est pas
   levée, 400 si l'identifiant n'est pas une chaîne.

**Preuve.** Script (instance jetable, sans écriture en base) : `UUID(str(n))` lève
`ValueError` et `UUIDField().to_internal_value(n) == u` vaut `True`. La recherche
`grep -rn "_uuid(brut)\|mission_du_corps"` liste les points d'appel ci-dessus.
