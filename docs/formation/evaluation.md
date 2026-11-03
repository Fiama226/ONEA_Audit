# Questionnaire d'évaluation

Une seule bonne réponse par question, sauf mention contraire. Chaque question renvoie au manuel dont elle
est tirée. **Le corrigé (section 4) ne doit pas être distribué aux participants.** Seuil de réussite : à
décider par l'ONEA (voir le guide du formateur).

## 1. Questions communes (tous les rôles)

**Q1.** Combien d'étapes compte la méthode et en combien de phases ?
a) 12 étapes, 2 phases  b) 18 étapes, 3 phases  c) 16 étapes, 4 phases

**Q2.** Quelle phase regroupe les étapes XI à XIII ?
a) Planification  b) Accomplissement  c) Communication

**Q3.** Peut-on supprimer définitivement une mission ou un constat dans la plateforme ?
a) Oui, le RAI le peut  b) Oui, l'administrateur seulement  c) Non : tout est historisé, jamais de suppression physique

**Q4.** Au format d'affichage de la plateforme, la date du 5 mars 2027 s'écrit :
a) 2027-03-05  b) 03/05/2027  c) 05/03/2027

**Q5.** La plateforme utilise-t-elle une fonction d'intelligence artificielle ?
a) Oui, pour rédiger les constats  b) Non, aucune  c) Oui, pour la recherche

## 2. Questions par rôle

### Administrateur
**Q6.** Où est attribué le rôle d'un utilisateur ? a) dans la plateforme, par l'administrateur  b) dans l'annuaire (Keycloak)  c) par le RAI

**Q7.** Que renseigne l'administrateur sur un utilisateur ? a) direction, fonction, matricule  b) mot de passe  c) rôle

**Q8.** Que faire pour retirer l'accès d'une personne qui quitte l'ONEA ? a) supprimer le compte  b) désactiver le compte  c) changer son nom

**Q9.** Les gabarits Word actuels sont : a) définitifs  b) provisoires, en attente des modèles officiels de l'ONEA  c) générés par IA

**Q10.** La signature électronique avancée (PAdES) est-elle installée ? a) oui  b) non : seule la « Confirmation horodatée » existe

### RAI
**Q6.** Probabilité 3 et impact 5 donnent un score de : a) 8  b) 15  c) 35

**Q7.** Qui valide les jalons VI, X et XIII ? a) le chef de mission  b) l'audité  c) le RAI

**Q8.** Le motif est-il obligatoire pour « Renvoyer » une étape ? a) oui  b) non

**Q9.** Un livrable peut-il être validé par son auteur ? a) oui  b) non : le valideur n'est jamais l'auteur

**Q10.** Que signifie la mention « Manquant : … » sous une étape ? a) des livrables empêchent de terminer l'étape  b) l'étape est en retard  c) l'étape est annulée

### Auditeur et chef de mission
**Q6.** Avant de contribuer à une mission, l'auditeur doit : a) confirmer sa déclaration d'indépendance  b) valider un jalon  c) attendre la diffusion

**Q7.** Qui transmet le rapport provisoire à l'audité (étape XV) ? a) l'auditeur  b) le chef de mission  c) le DG

**Q8.** Une pièce justificative déposée : a) peut être remplacée silencieusement  b) est conservée avec son empreinte SHA-256, sans modification possible

**Q9.** Les étapes IX et X (budget, organisation) sont réservées : a) au chef de mission  b) à l'audité

**Q10.** Un auditeur peut-il valider le jalon XIII ? a) oui  b) non, c'est le RAI

### Audité
**Q6.** Un audité en désaccord avec un constat doit : a) ne rien faire  b) motiver son désaccord (commentaire obligatoire)

**Q7.** Peut-on modifier une réponse déjà envoyée ? a) oui, à tout moment  b) non, on envoie une nouvelle réponse ; l'historique est conservé

**Q8.** Une réponse après la date limite est marquée : a) « Hors délai »  b) refusée

**Q9.** Que demande-t-on pour repousser l'échéance d'une action ? a) un report d'échéance, soumis à décision  b) la suppression de l'action

**Q10.** Quelles missions voit l'audité ? a) toutes  b) seulement celles qui concernent son entité

### Direction générale
**Q6.** Le DG peut-il modifier un constat ? a) oui  b) non : rôle de consultation

**Q7.** Quel indicateur figure au tableau de bord du DG ? a) taux de mise en œuvre des recommandations  b) mot de passe des utilisateurs

**Q8.** « Exporter les taux (Excel) » télécharge : a) les taux de mise en œuvre  b) tous les rapports

**Q9.** Quelle mention porte l'impression du tableau de bord ? a) « CONFIDENTIEL · USAGE INTERNE ONEA »  b) aucune

**Q10.** Où le DG lit-il les rapports finalisés ? a) « Rapports diffusés »  b) « Gabarits de documents »

## 3. Barème
1 point par bonne réponse (10 points par rôle : Q1 à Q5 communes et Q6 à Q10 du rôle).

## 4. Corrigé (formateur uniquement)

| Question | Réponse | Source |
|---|---|---|
| Q1 | b | `CLAUDE.md`, manuel RAI §4 |
| Q2 | b | manuel RAI §4 |
| Q3 | c | manuels (règles à connaître), `CLAUDE.md` règle 4 |
| Q4 | c | `manuels/README.md` (JJ/MM/AAAA) |
| Q5 | b | `CLAUDE.md` règle 1 |

| Rôle | Q6 | Q7 | Q8 | Q9 | Q10 |
|---|---|---|---|---|---|
| Administrateur | b | a | b | b | b |
| RAI | b | c | a | b | a |
| Auditeur | a | b | b | a | b |
| Audité | b | b | a | a | b |
| DG | b | a | a | a | a |

Références des corrigés par rôle : administrateur (manuel-administrateur §2, §3, §4) ; RAI (manuel-rai
§2.4, §8.1, §8.2, §4) ; auditeur (manuel-auditeur §2, §5.2, §4.2, §3.9-3.10, §4.3) ; audité (manuel-audite
§4, §6.2) ; DG (manuel-dg §2 à §4).

**À contrôler avant usage** : les réponses sont tirées des manuels, eux-mêmes non rejoués sur
l'application ; revérifier chaque réponse lors du rejeu du kit.
