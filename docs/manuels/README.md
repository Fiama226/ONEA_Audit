# Manuels utilisateur — plateforme d'audit interne ONEA

Ce dossier contient la documentation destinée aux utilisateurs de la plateforme du Département Audit
Interne (DAI) de l'ONEA. Il couvre les tâches 30, 32, 33 et 34 du lot 9.

## Sommaire

| Manuel | Destinataires | Fichier |
|---|---|---|
| Manuel du Responsable de l'audit interne (RAI) | compte au rôle « RAI » | [manuel-rai.md](manuel-rai.md) |
| Manuel de l'administrateur fonctionnel | compte au rôle « Administrateur » | [manuel-administrateur.md](manuel-administrateur.md) |
| Manuel de l'auditeur et du chef de mission | comptes au rôle « Auditeur » (y compris chef de mission et superviseur) | [manuel-auditeur.md](manuel-auditeur.md) |
| Manuel de l'audité | compte au rôle « Audité » | [manuel-audite.md](manuel-audite.md) |
| Manuel de la Direction générale | compte au rôle « DG » | [manuel-dg.md](manuel-dg.md) |
| Glossaire | tous | [glossaire.md](glossaire.md) |
| Liste des captures d'écran à prendre | équipe projet | [captures-a-prendre.md](captures-a-prendre.md) |

## Conventions de rédaction

- **Vouvoiement** et ton institutionnel, une tâche par section, des étapes numérotées.
- Les libellés de boutons, d'onglets et de messages sont cités **entre guillemets français** et tels
  qu'ils figurent dans l'interface (`frontend/src/i18n/fr.ts`). Un libellé entre guillemets est donc
  celui à chercher à l'écran.
- Les noms de menu sont ceux de la barre latérale : « Tableau de bord », « Programme annuel »,
  « Missions », « Référentiel », « Recommandations », « Rapports diffusés », « Documents »,
  « Administration », « Gabarits de documents ».
- Les dates s'affichent au format JJ/MM/AAAA, à l'heure d'Ouagadougou.
- Les jalons sont désignés par leur numéro d'étape en chiffres romains (VI, X, XIII, XVIII).
- Les écrans illustrés par une copie d'écran portent un repère de la forme
  « [Capture à insérer : CAP-xxx — titre] ». La liste complète, avec la route, le compte et l'état des
  données à préparer, est dans [captures-a-prendre.md](captures-a-prendre.md).
- Aucune donnée réelle ne doit figurer sur les captures : utiliser le jeu de données de formation
  (adresses en `@example.org`).
- Rubrique « À confirmer » en fin de chaque manuel : points que le code ne permet pas d'affirmer.
  Ils reprennent la liste « à vérifier » de `docs/recette/scenarios-de-test.md` (références V-xx) et
  doivent être levés avant diffusion du manuel.

## Statut et réserves

- Les manuels ont été rédigés à partir du code de la branche `develop` et des scénarios de recette
  (`docs/recette/scenarios-de-test.md`). Les procédures **n'ont pas encore été rejouées** sur
  l'application en fonctionnement : le rejeu de dix procédures par manuel (étape 3 de la tâche 34)
  reste à faire et pourra corriger des détails.
- Les gabarits Word actuels sont provisoires : le contenu des documents générés n'est pas décrit.
- La signature électronique (PAdES) n'est pas installée : seule la « Confirmation horodatée » est décrite.
- L'application ne comporte aucune fonction d'intelligence artificielle.

## Reste à faire pour la tâche 30 (non réalisé : accès en lecture seule au code)

- Entrée « Aide » dans le menu utilisateur (`frontend/src/layouts/UserMenu.tsx` ne propose aujourd'hui que
  « Se déconnecter ») et clés correspondantes dans `fr.ts`.
- Script de captures `frontend/e2e/captures-doc.spec.ts`, `scripts/docs/pdf.sh` (production des PDF dans
  `frontend/public/aide/`) et `scripts/docs/verifier.mjs` (images référencées existantes, libellés de
  navigation cités).
- Les manuels sont donc livrés en Markdown, sans PDF ni images.

## Prise en main commune à tous les rôles

La connexion, la navigation et la déconnexion sont identiques pour tous les rôles ; chaque manuel les
rappelle en section 1. Le menu utilisateur propose « Mon compte »
(changement du mot de passe, code de connexion facultatif par courriel) ; le nom, l'adresse électronique, le
rôle, la direction, la fonction et le matricule sont renseignés par l'administrateur (ou un délégué, pour les
comptes Auditeur interne et Audité seulement ; les comptes Administrateur, RAI et DG ne sont gérés que par un
administrateur) : ils ne sont pas modifiables par l'agent. Les comptes sont gérés dans la plateforme, sans
annuaire externe.
