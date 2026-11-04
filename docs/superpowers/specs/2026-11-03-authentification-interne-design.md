# Remplacement de Keycloak par une authentification interne — conception

Date : 2026-11-03. Statut : brouillon soumis à relecture, **non approuvé**.

## Intention

Aujourd'hui l'identité (mot de passe, connexion, sessions) dépend de Keycloak, alors que les
rôles et les droits sont déjà dans l'application. Les deux systèmes doivent être synchronisés
(états « en attente » / « échec », secret d'API d'administration, conteneur et base en plus,
adresse publique à configurer). Pour cinq rôles et un nombre limité d'agents, c'est
disproportionné. Décision de l'utilisateur (2026-11-03) : **l'application gère elle-même
l'authentification, la création des comptes et leur administration**, sans Keycloak.

## Buts

1. Connexion par identifiant ou courriel professionnel et mot de passe, gérée par l'application.
2. Création d'un compte par l'administrateur (ou un délégué) : mot de passe temporaire généré,
   courriel de bienvenue professionnel envoyé par défaut ; l'envoi est désactivable, le mot de
   passe temporaire est alors affiché une fois à l'écran.
3. Changement de mot de passe obligatoire à la première connexion.
4. Mot de passe oublié : l'agent reçoit un code à usage unique (OTP) par courriel, puis choisit
   lui-même un nouveau mot de passe.
5. Code OTP par courriel à la connexion : **option désactivée par défaut**, activable et
   désactivable uniquement par le propriétaire du compte (« Mon compte »).
6. Délégation : l'administrateur choisit, par personne, parmi quatre actions : créer des
   comptes, réinitialiser des mots de passe, changer des rôles, désactiver des comptes. Droits
   modifiables et révocables à tout moment.
7. Suppression complète de Keycloak (code, conteneur, thème, secrets, documentation, tests).
8. Piste d'audit de toute action de compte (qui, quand, sur quel compte, quoi).

## Non-buts

- Pas de fédération d'identité, pas de connexion sociale, pas d'annuaire LDAP/AD.
- Pas d'application mobile, pas de WebAuthn/clé de sécurité (évolution possible).
- Pas de nouveau modèle de rôles : les cinq rôles globaux existants (ADMIN, RAI, AUDITEUR,
  AUDITE, DG) sont conservés tels quels.
- Pas d'IA, pas de service payant (règles de `CLAUDE.md`).

## Anti-buts (échec même si « ça marche »)

- Un compte désactivé qui peut encore se connecter ou réinitialiser son mot de passe.
- Un message de « mot de passe oublié » qui révèle si un courriel a un compte.
- Un mot de passe ou un code stocké en clair, journalisé, ou renvoyé par l'API après coup.
- Un délégué qui s'élève lui-même en administrateur.
- Perdre l'audit de sécurité ASVS L2 sans le rejouer sur la nouvelle authentification.

## Contraintes

- 100 % open source, licences autorisées par `CLAUDE.md` ; français dans l'interface, anglais
  dans le code ; soft delete et piste d'audit ; tests d'abord.
- Le projet est mené sur une branche dédiée, fusionnée dans `develop` seulement après suites
  complètes vertes. Le site de test partagé reste sur l'ancienne version tant que ce n'est pas fait.
- Le serveur SMTP de l'ONEA n'est pas fourni : tout le flux doit fonctionner **sans courriel**
  (repli administrateur) et avec Mailpit en développement.

## Décisions de l'utilisateur

- Comptes actuels : six comptes de test uniquement (admin, rai, auditeur1, auditeur2, audite1,
  dg) ; ils sont conservés avec leur rôle, sans migration de mots de passe réels.
- Mot de passe oublié : OTP par courriel puis changement par l'agent.
- OTP à la connexion : possible, désactivé par défaut, activé par le propriétaire du compte.
- Délégation : les quatre actions (création, réinitialisation, rôles, désactivation),
  paramétrables par l'administrateur, révocables.

## Hypothèses présentées en conversation, non contredites par l'utilisateur

- Un compte désactivé ne peut ni se connecter ni réinitialiser son mot de passe.
- Le changement de mot de passe termine toutes les sessions ouvertes.
- Le message de « mot de passe oublié » est identique que le courriel existe ou non.
- Un délégué ne peut ni se donner des droits, ni modifier ou désactiver un administrateur, ni
  attribuer le rôle Administrateur, ni déléguer à un tiers, ni se désactiver lui-même.
- L'administrateur ne peut pas activer l'OTP à la place d'un agent.

## Choix du concepteur (à valider ou corriger, non décidés par l'utilisateur)

- **Identifiant** : le courriel professionnel suffit comme identifiant (l'identifiant existant
  reste accepté pour les six comptes de test).
- **Session** : cookie de session Django `HttpOnly`, `SameSite=Lax`, avec protection CSRF, le
  front et l'API étant servis sous la même origine (Nginx en production, proxy en dev).
  Alternative écartée : jetons JWT stockés côté navigateur.
- **Hachage** : Argon2id (`argon2-cffi`, MIT) via les hasheurs de Django.
- **OTP** : code numérique à 6 chiffres, haché en base, valable 10 minutes, 5 essais maximum,
  usage unique, un seul code actif par agent et par objet (réinitialisation / connexion).
- **Politique de mot de passe** : 12 caractères minimum, validateurs Django (mots de passe
  courants, similarité, numérique seul).
- **Limitation de débit et verrouillage** : blocage temporaire après 5 échecs consécutifs
  (15 minutes), limitation par IP et par compte sur connexion et demandes de code.
- **Mot de passe temporaire** : généré aléatoirement, affiché une seule fois, expire après
  72 h s'il n'est pas utilisé ; première connexion = changement obligatoire.
- **Droit délégué** : modèle `DelegationGestionComptes` (agent, quatre booléens, accordé par,
  date), lisible et modifiable par l'administrateur seulement.
- **Champs Keycloak** du modèle `User` (`keycloak_id`, états de synchronisation, `role_provisoire`)
  supprimés par migration ; l'import d'annuaire / CSV reste, mais crée directement les comptes.

## Choix complémentaires du concepteur (issus de la relecture, à vérifier)

- **Clients de l'API** : navigateur seul. Les scripts de recette, de charge et les tests e2e se
  connectent par le point d'entrée de connexion et conservent le cookie ; aucun jeton Bearer.
  L'authentification DRF OIDC est supprimée.
- **Même origine partout** (site de test, recette, production) : Nginx ou le proxy sert le front
  et `/api` sous la même origine ; pas de CORS avec identifiants. `CORS_ALLOWED_ORIGINS` est retiré.
- **OTP à la connexion sans courriel opérationnel** : l'OTP ne peut être activé que si l'envoi de
  courriels est configuré. Si l'agent est ensuite bloqué, l'administrateur (ou un délégué ayant le
  droit « réinitialiser les mots de passe ») peut **désactiver** son OTP et réinitialiser son mot de
  passe ; l'action est journalisée. Cela ne contredit pas la règle : seul le propriétaire peut
  *activer* l'OTP.
- **Mot de passe oublié sans SMTP** : même repli, réinitialisation par l'administrateur ou un
  délégué (mot de passe temporaire affiché une fois).
- **Amorçage** : commande `creer_administrateur` (création ou réinitialisation de l'admin initial,
  en production et en recette). Après migration, les six comptes de test reçoivent un mot de passe
  temporaire à changer à la première connexion ; ceux de la base du site de test aussi.
- **Verrouillage** : la réponse de connexion est identique pour compte inexistant, mot de passe
  faux ou compte verrouillé (même message, même délai). Réinitialiser le mot de passe d'un compte
  le déverrouille (droit « réinitialiser les mots de passe »).
- **Sessions** : stockées en base, 8 h au plus et 30 min d'inactivité ; invalidation de toutes les
  sessions d'un agent au changement de mot de passe. Pas de Redis requis pour cela.
- **Import annuaire / CSV** : un mot de passe temporaire par ligne ; courriel de bienvenue envoyé
  si l'envoi est actif ; sinon un fichier de mots de passe temporaires téléchargeable **une seule
  fois** par l'importateur, puis détruit.
- **Rôle à la création** : obligatoire dans le formulaire ; plus de rôle « provisoire ». Les
  champs du tutoriel d'accueil sont conservés.
- **Purge** : codes OTP expirés supprimés après 24 h ; journal d'audit des comptes conservé comme
  le reste de la piste d'audit.

## Ce qui est laissé au réalisateur

Découpage en tâches, noms des endpoints et des modèles, forme exacte des écrans (conformes à
`docs/design/charte-graphique.md`), stratégie de migration des données de développement,
adaptation de la CI, du runbook de déploiement, des manuels, des scénarios de recette et de
l'audit ASVS L2 (à rejouer), suppression des tests Keycloak et ajout des tests de sécurité
(énumération de comptes, force brute, rejeu d'OTP, élévation de privilèges d'un délégué).

## Points ouverts hors périmètre technique

- Serveur SMTP de l'ONEA et adresse d'expédition professionnelle (sans eux, repli administrateur).
- Rôles pour lesquels l'OTP à la connexion pourrait devenir obligatoire plus tard (ancienne
  décision D19) : ici facultatif pour tous.
