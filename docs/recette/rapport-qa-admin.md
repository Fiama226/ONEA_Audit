# Rapport de recette QA — administration, accès, référentiel, gabarits

Périmètre : connexion/déconnexion des 6 rôles, navigation par rôle, accès direct refusé, administration des utilisateurs, référentiel (écriture ADMIN), gabarits et numérotation, mode de signature, piste d'audit, cloche, recherche, états vides/erreur, retour arrière. Site de développement en direct (http://localhost:5173), 2 novembre 2026.

Données créées, préfixées « QA-ADM- » : compte `qa-adm-u1` (importé en CSV, désactivé puis réactivé), une version de gabarit déposée sur ORDRE_MISSION (non activée), direction `QAADM1` (créée, modifiée, supprimée), réglage « piste d'audit » basculé puis rétabli sur « Complet ».

## Résultats

| Scénario | Résultat | Preuve | Défaut | Statut |
|---|---|---|---|---|
| S1-01/02 Connexion des 6 comptes | Réussi | Tableau de bord propre au rôle, rôle affiché correct, aucune erreur console | - | - |
| S1-03 Déconnexion + retour arrière | Réussi | `/connexion` ; `/missions` redirige vers `/connexion` | - | - |
| S1-04 Identifiants erronés (x2) | Réussi | « Nom d'utilisateur ou mot de passe invalide. » ; pas de verrouillage après 2 essais (attendu en dev) | - | - |
| S1-05 Accès direct sans session (4 URL) | Réussi | Redirection `/connexion`, retour sur l'URL demandée après connexion | - | - |
| S1-06 Menu par rôle | Réussi après correction | 5 menus conformes au tableau ; aucune entrée vers « Mode de signature » | D1 | Corrigé 04810e3 |
| S1-07 Accès refusé par URL (10 URL x 6 rôles) | Réussi | « Accès refusé / Votre rôle ne donne pas accès à cette page. » | - | - |
| S1-08 Page introuvable | Réussi (partiel) | `/page-inexistante` : « Page introuvable ». « Mission introuvable » non testé (ADMIN sans accès missions) | - | - |
| S1-09 Habillage | Réussi (partiel) | Tab puis Entrée met le focus sur `main#contenu` ; tiroir « Ouvrir le menu » ; aucun défilement horizontal à 375 px sur 4 pages admin. Menu replié non testé | - | - |
| S1-10 Recherche (ADMIN) | Réussi avec réserve | « La recherche n'est pas disponible pour votre profil. » ; erreur console 403 (appel inutile) | D7 | Ouvert (mineur) |
| S1-11/12 Cloche et page notifications (ADMIN, vide) | Réussi | « Aucune notification. » / « Vous n'avez aucune notification. » | - | - |
| S1-13 Notifications par compte | Non testé | Aucune notification en base | - | - |
| S2-03/04 Directions : validation et CRUD (ADMIN) | Réussi | Erreurs en français liées aux champs (`aria-invalid`, focus sur le 1er champ), « Ce code est déjà utilisé. », création 201, modification 200, suppression 204 | D8 | Ouvert (cosmétique) |
| S2-01/05 Référentiel en lecture | Réussi | Processus, objets auditables, cartographies affichés sans erreur ; `/referentiel/cadres` n'existe pas (404 propre) | - | - |
| S2-11 Liste et filtres utilisateurs | Réussi | Recherche, « Aucun utilisateur ne correspond aux filtres. », « Effacer les filtres » | - | - |
| S2-12 Fiche utilisateur / profil | Réussi après correction | Matricule de 40 caractères refusé (`aria-invalid`, focus), « Profil enregistré. » ; historique pollué de lignes techniques | D2 | Corrigé 46264e2 |
| S2-13 Désactiver / réactiver | Réussi (partiel) | « Le motif est obligatoire. » + focus ; désactivation et réactivation tracées. Connexion d'un compte désactivé non testée (compte non lié à Keycloak) | - | - |
| S2-14 Import CSV | Réussi | > 1 Mo : « Le fichier dépasse 1 Mo. » ; Importer désactivé avant vérification ; rapport de vérification puis « Import terminé » ; ligne `role=ADMIN` et ligne sans identifiant ignorées avec motif | - | - |
| S2-15 Import annuaire | Réussi (message) | « Saisissez au moins 2 caractères. » ; annuaire injoignable : « L'annuaire (Keycloak) est momentanément indisponible. » (client de synchronisation non configuré, V-01) | - | - |
| S2-26 Gabarits (liste, détail, balises) | Réussi | 19 types, « Aucun gabarit actif », balises avec « Copier » | - | - |
| S2-27 Dépôt de gabarit | Réussi (partiel) | `.doc` refusé, 11 Mo refusé, faux `.docx` refusé (liste de raisons), `.docx` valide déposé en v1. Aperçus et activation non testés (ne pas modifier l'état du propriétaire) | - | - |
| S2-28 Numérotation | Échec puis corrigé | 17 formats enregistrés en `{sequence:02d}` rejetés par le serveur (aperçu « — ») alors que l'écran, le manuel et le scénario annoncent `{sequence:02d}` comme permis ; la génération de ces documents échoue. Enregistrement d'un format non exercé en base (action refusée par la politique du harnais) ; « Saisissez un modèle. » vérifié | D3 | Corrigé 46264e2 (migration à appliquer) |
| S2-30 DG sur `/documents` | Réussi | « Accès refusé » | - | - |
| Mode de signature (ADMIN) | Réussi | 3 types, seule « Confirmation horodatée » sélectionnable (PAdES : « Disponible après… lot 7 bis ») | - | - |
| Piste d'audit complet/masqué | Réussi | Dialogue de confirmation, Échap annule, PATCH 200, valeur rétablie sur Complet, « Modifié le … par Admin ONEA » | - | - |
| Retour/avant navigateur, rechargement sur lien profond | Réussi | Navigation cohérente, URL admin conservées au rechargement | - | - |
| États d'erreur (500 simulé) | Réussi avec réserve | « Impossible de charger les comptes utilisateurs. » + « Réessayer », mais après ~7 s (3 rejeux) | D5 | Corrigé e13077d |
| Fiche utilisateur inexistante (`/9999`, `/abc`) | Échec puis corrigé | Squelette ~7 s (3 rejeux d'un 404) avant « Utilisateur introuvable. » ; vaut pour toute page 404/403 | D5 | Corrigé e13077d |
| Console DG sur `/recommandations` | Échec puis corrigé | 403 sur `GET /api/v1/missions/?page_size=100` (filtre « Mission » chargé pour un rôle sans accès) | D6 | Corrigé e13077d |
| Expiration / renouvellement de session | Partiel | Gestion 401 et renouvellement silencieux relus dans `AuthProvider` ; une session inactive depuis plus d'une heure a ramené à `/connexion`. Expiration du jeton non simulée | - | - |

## Défauts

| Id | Gravité | Description | Correctif |
|---|---|---|---|
| D1 | Moyenne | Aucune entrée de menu vers `/administration/signatures` (mode de signature + piste d'audit) : réglages inaccessibles sans connaître l'URL | Entrée « Mode de signature » (ADMIN, RAI) ; tests `navigation.lot7.test.ts`, `Sidebar.test.tsx` |
| D2 | Moyenne | Historique de compte : à la création, lignes techniques (`notifications : notifications.Notification.None`, `suivis_responsable`, `affectations_mission`, `keycloak_sync_manuel`, « Rôle provisoire : True ») | Champs masqués, booléen traduit ; test `history.test.ts` |
| D3 | Haute | Formats de numérotation enregistrés en `{sequence:02d}` refusés par le validateur : édition et génération impossibles ; libellé, manuel et scénario annonçaient `{sequence:02d}` | Migration de données `documents/0002`, libellé, manuel, scénarios ; test `test_numerotation_migration.py` |
| D5 | Moyenne | `QueryClient` rejoue 3 fois les erreurs 4xx : « introuvable » affiché après ~7 s | `api/queryClient.ts` (pas de rejeu des 4xx, un seul rejeu sinon) ; test `queryClient.test.ts` |
| D6 | Basse | DG : appel `/missions/` refusé (403) depuis le registre des recommandations | `useMissions(..., { enabled })` désactivé pour le DG ; test `RegisterPage.test.tsx` |
| D7 | Basse | ADMIN sur `/recherche` : requête 403 inutile (message correct par ailleurs) | Ouvert |
| D8 | Cosmétique | Code de direction vide : le message d'erreur répète l'aide au lieu de « Le code est obligatoire. » | Ouvert |

## Décisions nécessaires

1. Appliquer la migration `documents.0002` à la base de développement (non fait ici : serveurs et base à ne pas toucher).
2. Tableau de bord ADMIN : « Consulter la piste d'audit — Disponible au lot 8 » est un espace réservé ; confirmer que la page de consultation de la piste d'audit est bien prévue au lot 8.
3. Directions des comptes de recette (DAI, DSI, DG) « inconnues du référentiel » : fournir la liste officielle des directions.
4. Gabarits : aucun gabarit actif ; charger les gabarits provisoires (`gabarits_provisoires`) ou attendre les modèles officiels ONEA.
5. Signature électronique PAdES indisponible (lot 7 bis) : confirmer l'échéance.
