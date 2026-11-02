# Rapport QA — scénarios complexes et limites (niveau 4)

Date : 2026-11-02. Cible : pile de développement locale (SPA 5173, API 8000, Keycloak 8180).
Méthode : appels API authentifiés (jetons des six comptes) et navigateur (contextes isolés).
Données créées, toutes préfixées `QA-EDG-` : direction DEX, processus QAEDG, cartographie 2096
validée et 2095 brouillon, missions DAI/2096/M01 à M03 (M01 équipe complète, M02 sans `auditeur2`
ni `audite1`, M03 pour la concurrence). Les brouillons de test ont été supprimés.
Antivirus : moteur `aucun` en développement, donc aucune détection EICAR possible (noté, non testé).

Légende résultat : OK, KO (défaut), NT (non testé : fixture ou service absent).

| Scénario | Résultat | Preuve | Défaut | Statut |
|---|---|---|---|---|
| S4-01 modification concurrente | KO partiel | deux PATCH simultanés de la mission : 200 et 200, le dernier écrase le premier, aucun avertissement | D-06 | décision (connu) |
| S4-02 double validation | OK (actions de mission) | 5 `launch`, `suspend`, `resume`, `issue-order` simultanés : 1 succès, 4 refus « déjà… » ; 4 `confirm` de déclaration : 1 succès. Fiches, constats, rapports NT | | OK |
| S4-03 double soumission | OK | affectation du même utilisateur x6 : 1 création ; un seul ordre de mission (une empreinte) | | OK |
| S4-04 gel mission suspendue | OK | écritures du RAI refusées : « La mission … est suspendue : aucune modification n'est possible. » (réunion, PATCH, affectation) | | OK |
| S4-05 réouverture d'étape | NT | parcours étapes IV à VI non atteint | | NT |
| S4-06 déclaration non levée | OK | `auditeur2` : 403 « Confirmez votre déclaration d'indépendance… » à l'écriture, lecture 200 ; après arbitrage, écriture 201 | | OK |
| S4-07 conflit et arbitrage | OK | écriture refusée tant que le conflit n'est pas arbitré ; non-RAI refusé à l'arbitrage ; justification vide 400 ; second arbitrage 422 | | OK |
| S4-08 quatre yeux | NT | fiches et constats non atteints | | NT |
| S4-09 remplacement du chef | NT | non joué | | NT |
| S4-10 accès à l'objet d'une autre mission | OK avec écart | `auditeur2` sur M02 : 404, sous-ressources vides ou 404, identique à un UUID inexistant (pas d'oracle). DG et ADMIN : 403. Écart UI : mission introuvable restait ~8 s en chargement | D-04 | corrigé |
| S4-11 audité d'une autre direction | NT | un seul compte audité | | NT |
| S4-12 ce que l'audité ne voit pas | OK | `audite1` : étapes, équipe, déclarations, risques, programme, fiches, pièces, objectifs, grilles : 403 | | OK |
| SEC-08 conflits visibles | OK partiel | déclarant, chef et RAI voient la description ; audité, DG, ADMIN : 403. Cas du collègue auditeur non chef non joué (deux auditeurs seulement) | | NT partiel |
| SEC-09 réunion non tenue | OK | compte rendu et décisions vides pour `audite1` (liste et détail), lisibles par le RAI | | OK |
| S4-13 fichiers invalides (gabarit) | OK | vide 400, texte déguisé en .docx 400, .exe 400, double extension 400, traversée de chemin 400, SVG 400, > 10 Mo 422 ; non-admin 403. EICAR refusé comme faux .docx, détection antivirus NT. Nom de 5 000 caractères : 400 mais message anglais | D-03 | corrigé |
| S4-13 pièces de fiche, preuves d'action | NT | fiche non atteinte | | NT |
| S4-14 intégrité des pièces | NT | accès serveur interdit | | NT |
| S4-15 session expirée | KO | un 401 reçu après le chargement du profil laissait l'écran en place sans redirection ; jeton invalide au rechargement : retour à la connexion | D-02 | corrigé |
| S4-16 champs invalides, bornes | OK avec réserves | titre 301 : 400 français ; dates inversées 422 ; budget négatif, trop grand, décimales : 400 ; NUL refusé ; espaces rognés ; HTML, emoji, arabe, hébreu, formule acceptés et rendus en texte. Réserves : dates 1900 et 9999 acceptées, texte libre sans plafond (1 Mo accepté), caractère bidi U+202E accepté | D-07, D-08 | décision |
| S4-17 clavier, S4-19 impression | NT | non couverts | | NT |
| S4-18 compte désactivé | NT | non joué (comptes du propriétaire) | | NT |
| S4-20 exports | OK | CSV : BOM UTF-8, séparateur « ; », `=`, `+`, `-`, `@`, tabulation et retour chariot préfixés d'une apostrophe ; XLSX sans formule ; `type=pdf` 400 | | OK |
| S4-21, S4-22, S4-23 | NT | tableaux de bord, journal, signature non rejoués | | NT |
| S4-24 recherche | N/A | Meilisearch absent : 503 « La recherche est momentanément indisponible » (message conforme) | | N/A |
| S4-25 limitation de débit | OK avec réserve | dépôt de gabarit : 429 au 14e appel, `Retry-After` présent. Le message annonce « 1680 secondes » (28 min) ; le compte admin est resté bloqué en dépôt pendant ce délai | D-09 | décision |
| S4-26 superviseur | NT | non joué | | NT |
| S4-27 dégradation sans service | partiel | recherche : 503 français ; Gotenberg et worker non arrêtés (interdit) | | NT |
| S4-28 commande de peuplement | NT | interdite | | NT |
| IDOR par corps (SEC-01) | OK | identifiants entiers, chaînes, listes, objets, nuls, énormes dans `mission` et `utilisateur` : 400 « Identifiant invalide » ou 404, jamais 500 | | OK |
| Écriture DG et audité | OK | DG : 403 sur création de mission, réunion, direction, PATCH ; audité : 403 | | OK |
| XSS dans les champs libres | OK | `<script>`, `<img onerror>`, Markdown : stockés bruts, affichés en texte (liste et détail), aucun script ni dialogue ; export CSV neutre. PDF et Word NT | | OK |
| Pagination et filtres | OK | page hors limites 404 « Page non valide. » ; `page_size` ignoré ; filtres invalides 400 français | | OK |
| Jeton absent, invalide, falsifié | OK | 401 français avec `WWW-Authenticate: Bearer` | | OK |
| CORS, en-têtes | OK avec réserve | aucune autorisation CORS pour une origine tierce ; `nosniff`, `X-Frame-Options: DENY`, `no-store` présents. Pas de CSP ni HSTS sur l'API de développement | | noté |
| Route SPA inconnue | OK | « Page introuvable » avec lien de retour | | OK |
| URL /api/ inconnue, JSON mal formé, corps imbriqué | KO | HTML au lieu de JSON ; message anglais du décodeur ; JSON de 5 000 niveaux : erreur 500 (RecursionError) | D-01, D-03, D-05 | corrigé |

## Défauts

| Id | Sévérité | Description | Statut |
|---|---|---|---|
| D-01 | Basse | URL `/api/` inconnue ou panne 500 : page HTML Django au lieu de `{detail, errors}` | Corrigé `ccf04db` |
| D-02 | Moyenne | 401 en cours d'utilisation sans retour à la connexion ni message de session expirée | Corrigé `6c3b7b1` |
| D-03 | Basse | Message anglais pour JSON ou multipart illisible | Corrigé `ccf04db` |
| D-04 | Basse | Ressource introuvable : chargement ~8 s (404 rejoué 3 fois) avant le message | Corrigé `6c3b7b1` |
| D-05 | Moyenne (authentifié) | JSON très imbriqué : erreur 500 non maîtrisée | Corrigé `ccf04db` |
| D-06 | Moyenne | Pas de verrou optimiste : deux enregistrements simultanés, le second écrase le premier sans avertissement | Ouvert, décision |
| D-07 | Basse | Aucun plafond de longueur sur les champs libres et dates 1900 ou 9999 acceptées | Ouvert, décision |
| D-08 | Basse | Caractères de contrôle bidirectionnels acceptés dans les libellés | Ouvert, décision |
| D-09 | Basse | Limitation de débit annoncée en secondes (« 1680 secondes ») ; seuil de dépôt bas | Ouvert, décision |

## Décisions à prendre

1. Verrou optimiste (en-tête `If-Match` ou champ de version) sur les objets modifiables à plusieurs (D-06).
2. Plafonds de longueur du texte libre, plage de dates admise (D-07), neutralisation des caractères bidi (D-08).
3. Seuil et formulation de la limite de dépôt (D-09).
4. CSP et HSTS : à poser au niveau du proxy de production (hors périmètre dev).
