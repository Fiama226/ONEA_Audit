---
name: domaine-audit
description: Vocabulaire et règles métier de l'audit interne (IFACI 18 étapes, Normes IIA 2024, cartographie des risques ONEA, documents de mission). À lire avant de modéliser, nommer ou implémenter toute règle métier.
---

# Domaine : audit interne ONEA

Sources détaillées : `docs/domaine/processus-ifaci.md`, `docs/domaine/cartographie-risques-onea.md`,
`docs/domaine/documents-mission.md`, `docs/domaine/normes-iia-sommaire.md`.

## Acteurs et rôles plateforme
| Rôle | Qui | Pouvoirs principaux |
|---|---|---|
| ADMIN | DSI / administrateur | utilisateurs, référentiels, paramétrage |
| RAI | Responsable de l'audit interne (chef du DAI) | crée les missions, affecte, valide chaque jalon, diffuse le rapport |
| AUDITEUR | auditeurs internes, chef de mission | saisit, documente, propose |
| AUDITE | responsables des entités auditées | consulte son périmètre, répond, s'engage sur le plan d'actions |
| DG | Direction Générale / comité d'audit | lecture des rapports validés et du suivi |

## Cycle de vie d'une mission (3 phases, 18 étapes IFACI)
- **Planification (I à X)** : ordre de mission, réunion d'ouverture, analyse des processus,
  risques, dispositif de contrôle, référentiel d'audit validé, objectifs d'audit,
  programme de travail, budget/ressources, organisation validée.
- **Accomplissement (XI à XIV)** : réunion de lancement, collecte des preuves (fiches de test),
  validation des preuves, analyse des causes et recommandations (fiches d'observation).
- **Communication (XV à XVIII)** : réunion de clôture, plan d'actions, rédaction du rapport,
  validation et diffusion. Puis **suivi des actions de progrès** (norme 2500 / 15.2).

Jalons avec validation RAI obligatoire : référentiel d'audit (VI), organisation de la
mission (X), preuves (XIII), rapport (XVIII).

## Objets métier clés
- **ObjetAuditable** : domaine, opérations, risques, objectif de contrôle, dispositif.
- **Risque** : probabilité 1 à 5, impact 1 à 5, score = produit, niveau FAIBLE (1 à 7) /
  MOYEN (8 à 14) / ÉLEVÉ (15 à 25), code `n-PROC-Rk`.
- **RéférentielAudit** : liste des risques et contrôles clés retenus pour la mission.
- **ObjectifAudit**, **ProgrammeDeTravail**, **FicheDeTest** (objectif, procédure,
  échantillon, résultat, conclusion), **Constat** (force ou faiblesse, cause, conséquence,
  recommandation), **Recommandation** (priorité, responsable, échéance, statut de suivi),
  **PlanActions**, **Rapport** (versions, validation, diffusion).
- **DocumentVersion** : rendu figé d'un gabarit, immuable.

## Règles invariantes
- Aucune étape ne se valide sans ses livrables obligatoires.
- Un auditeur ne peut pas valider ce qu'il a lui-même rédigé.
- Un audité ne voit que les missions de son périmètre et jamais les feuilles de travail.
- Une déclaration d'indépendance signée par auditeur affecté avant le démarrage.
- Toute modification est historisée ; un document validé n'est jamais modifié, il est versionné.
