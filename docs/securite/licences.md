# Audit des dependances : licences, SBOM, vulnerabilites

Date de l'audit : 2026-10-30 (base `develop` @ 8ff70fe). Reproductible via
`scripts/audit-dependances.sh [dossier]` (sortie par defaut `build/audit/`, ignoree par git) ;
execute aussi par le job CI `dependency-audit`. Outils 100 % open source : `pip-audit`,
`pip-licenses`, `cyclonedx-bom`, `npm audit`, `license-checker-rseidelsohn`,
`@cyclonedx/cyclonedx-npm`, tous lances via `uvx` / `npx` (aucune installation globale).

Regle de reference : CLAUDE.md regle 2 (MIT, BSD, Apache-2.0, PostgreSQL, LGPL, AGPL, MPL-2.0,
ISC, OFL-1.1, 0BSD, BlueOak, CC0, CC-BY-4.0, Python-2.0, MIT-0, PSF-2.0 ; exception GPL-2.0 :
ClamAV, conteneur séparé uniquement, voir « Composants externes »).

## Resume

| Perimetre | Paquets | Hors liste | Vulnerabilites connues |
|---|---|---|---|
| Backend (Python, runtime, `uv.lock`) | 61 | 0 bloquant, 3 points d'attention | 0 (pip-audit) |
| Frontend (npm, prod + dev) | 538 | 0 bloquant, 2 points d'attention | 0 (npm audit, prod et dev) |

Aucune licence GPL seule, SSPL, BUSL, non commerciale, proprietaire ou inconnue. Aucune montee de
version n'a ete faite (T1 possede les fichiers de verrouillage). Les SBOM CycloneDX (JSON) sont
produits par le script : `sbom-backend.cdx.json`, `sbom-frontend.cdx.json`.

## Backend : licences notables

| Paquet | Licence | Statut | Decision proposee |
|---|---|---|---|
| django-fsm 5.0.1 | AGPL-3.0-or-later WITH viewflow-library-exception | Autorisee (AGPL) | Conserver. AGPL : si l'application est offerte a des tiers via le reseau, la source complete (y compris modifications de django-fsm) doit etre disponible ; usage interne ONEA sans modification de la bibliotheque : pas d'obligation de publication. Documenter dans le dossier de livraison. |
| docxtpl 0.20.2 | LGPL-2.1-only | Autorisee (LGPL) | Conserver ; utilisation par import sans modification de la bibliotheque. |
| psycopg / psycopg-binary 3.3.6 | LGPL-3.0-only | Autorisee (LGPL) | Conserver ; liaison dynamique, wheels non modifiees. |
| mozilla-django-oidc 5.0.2 (retire le 2026-11-04 avec Keycloak), certifi | MPL-2.0 | Autorisee | Conserver certifi ; argon2-cffi (MIT) a ete ajoute pour l'authentification interne. |
| cffi 2.1.1 | MIT-0 | Hors liste litterale, equivalent permissif (MIT sans condition d'attribution) | Proposer d'ajouter MIT-0 a la liste de CLAUDE.md. |
| typing_extensions 4.16.0 | PSF-2.0 | Equivalent de Python-2.0 | Accepter (meme famille que Python-2.0). |
| cryptography, packaging, python-dateutil, uritemplate | doubles licences (Apache-2.0 OR BSD) | Autorisees | Rien. |

Tout le reste est MIT / BSD / Apache-2.0 (liste complete : `licences-backend.csv`).

## Frontend : repartition (538 paquets)

MIT 458, Apache-2.0 27, ISC 23, BSD-2-Clause 9, MPL-2.0 5, BSD-3-Clause 4, MIT-0 2, CC0-1.0 2,
BlueOak-1.0.0 2, (MIT OR CC0-1.0) 2, OFL-1.1 1, Python-2.0 1, CC-BY-4.0 1, 0BSD 1.

| Paquet | Licence | Statut | Decision proposee |
|---|---|---|---|
| @csstools/color-helpers, css-syntax-patches-for-csstree | MIT-0 | Voir cffi ci-dessus | Idem : ajouter MIT-0 a la liste. Outillage de test uniquement (dev). |
| axe-core (vitest-axe), lightningcss | MPL-2.0 | Autorisee | Conserver (copyleft par fichier, non modifies, dev/build). |
| @fontsource/inter | OFL-1.1 | Autorisee | Conserver ; joindre la licence de police au livrable. |
| caniuse-lite | CC-BY-4.0 | Autorisee | Conserver (dev/build) ; attribution a conserver. |
| argparse | Python-2.0 | Autorisee | Rien. |
| BSD-2-Clause (9 paquets) | BSD-2-Clause | Famille BSD | Accepter. |

Le paquet `UNLICENSED` signale par license-checker est le projet lui-meme (`onea-audit-frontend`,
`private: true`), exclu du rapport CSV via `--excludePrivatePackages`.

## Vulnerabilites connues

- Backend : `pip-audit` sur l'export verrouille (`uv export --frozen`) : *No known vulnerabilities
  found*. Aucun correctif requis.
- Frontend : `npm audit` : *found 0 vulnerabilities*. Aucun correctif requis.

## Composants externes (conteneurs)

| Composant | Licence | Statut | Justification |
|---|---|---|---|
| ClamAV (`clamav/clamav`) | GPL-2.0 | Exception validée par l'utilisateur (SEC-04) | Antivirus open source de référence, sans équivalent libre. Exécuté dans un **conteneur séparé** : l'application ne l'incorpore pas, ne le lie pas et n'importe aucun de ses fichiers ; elle dialogue par un socket TCP (protocole INSTREAM de clamd, réimplémenté avec la bibliothèque standard Python, `backend/apps/core/antivirus.py`). La GPL s'applique au programme ClamAV lui-même ; elle ne s'étend pas à une application distincte qui l'appelle par un canal de communication ordinaire. Aucune modification de ClamAV : image officielle, non reconstruite. |

Règle de maintien : aucun paquet GPL ne peut entrer dans `backend/` ni `frontend/` ; l'exception
ne vaut que pour l'image ClamAV de `docker/compose.prod.yml`.

## Limites et suivi

- Les bases de vulnerabilites sont interrogees en ligne ; l'audit est un instantane daté. Le job CI
  le rejoue a chaque execution (echec si vulnerabilite ou licence interdite).
- Le filtre de licences du script est un refus par motifs (GPL hors LGPL/AGPL, SSPL, BUSL,
  non commercial, proprietaire, inconnu), pas une liste blanche stricte : une nouvelle licence
  atypique n'est donc pas bloquee automatiquement et doit etre relue dans le CSV.
- Les paquets transitifs (images Docker, systeme) ne sont pas couverts ; envisager Trivy/Grype
  (Apache-2.0) sur les images en production.
