# Stockage des fichiers

Décision du maître d'ouvrage (28/10/2026) : les fichiers générés par la plateforme (gabarits
Word, versions Word et PDF des documents) sont écrits **sur le disque du serveur ONEA**.
Ils ne sont jamais versionnés dans Git et jamais servis par une URL publique : le
téléchargement passe uniquement par l'API authentifiée (droits vérifiés à chaque requête).

## Emplacement

| Élément | Valeur |
|---|---|
| Dossier de l'hôte | `DOCUMENTS_HOST_DIR` (recommandé : `/srv/onea/documents`) |
| Dans les conteneurs | `/var/lib/onea/documents` (`DOCUMENTS_ROOT`) |
| Conteneurs concernés | `web` et `worker` uniquement (ni `nginx`, ni `frontend`, ni `gotenberg`) |
| Propriétaire | `10001:10001` (utilisateur `onea` des images), mode `0750` |
| Fichiers / dossiers créés | `0640` / `0750` |

Les écritures sont atomiques et à écriture unique (fichier temporaire, `fsync`, lien définitif qui échoue si la clé existe, puis `fsync` du dossier) ; l'empreinte SHA-256 est calculée à l'écriture. Les suppressions et les liens symboliques sont refusés. Les clés de stockage sont construites côté serveur (identifiants UUID, numéro de version) :
`gabarits/<type>/<version>-<empreinte>.docx` et `versions/<uuid>/v001.docx|pdf`. Aucun nom
de fichier fourni par l'utilisateur n'entre dans un chemin. Une clé existante n'est jamais
réécrite (écriture unique).

## Création du dossier

À faire une fois, avant le premier démarrage, sur le serveur :

```
install -d -o 10001 -g 10001 -m 0750 /srv/onea/documents
```

puis renseigner `DOCUMENTS_HOST_DIR=/srv/onea/documents` dans `.env.prod`. Compose monte ce dossier sans le créer (`create_host_path: false`) et l'application ne le crée pas en production : s'il manque, `GET /api/v1/health/` renvoie `stockage_documents: indisponible`. L'application
refuse de démarrer si `DOCUMENTS_ROOT` n'est pas un chemin absolu situé hors de `/app` et du
dépôt.

Il est conseillé de placer ce dossier sur un **disque ou volume dédié** (LVM, partition ou
disque monté), afin que son remplissage ne puisse pas bloquer le système ni la base de
données.

## Seuils et surveillance

| Réglage | Défaut | Effet |
|---|---|---|
| `DOCUMENTS_ESPACE_MIN_LIBRE_MO` | 1024 | en dessous, l'écriture est refusée (« Espace disque insuffisant sur le serveur de documents ») et l'état passe à `faible` |
| `DOCUMENTS_QUOTA_MO` | 0 | quota unique, appliqué à chaque dépôt et à chaque génération (`documents.services.quota`) ; 0 = sans quota (voir « Quota » ci-dessous) |
| `DOCUMENTS_MAX_GABARIT_MO` | 10 | taille maximale d'un gabarit Word téléversé |

`GET /api/v1/health/` renvoie `stockage_documents` : `ok`, `faible` (espace libre sous le
seuil) ou `indisponible` (dossier absent ou non inscriptible). Cet indicateur n'altère pas
`status`. À surveiller par la supervision du serveur.

## Quota

`controler_quota` est la seule fonction de quota : elle additionne la taille des **gabarits**, des
**versions Word et PDF** des documents générés **et des pièces justificatives**, lignes
supprimées logiquement comprises (leurs fichiers restent sur le disque). Un dépôt (gabarit,
pièce) est refusé (422, « Le quota de stockage des documents est atteint : contactez
l'administrateur. ») si l'ajout dépasse le quota ; une génération, dont la taille est inconnue,
est refusée seulement si le quota est déjà atteint. Un pièce redéposée à l'identique (doublon)
n'est pas recomptée.

## Contrôle des téléversements

Tous les dépôts passent par `core.fichiers` : l'extension doit être autorisée par l'appelant
**et** concorder avec la signature d'octets du contenu (le `content-type` du client et le
nom ne comptent jamais) ; les formats texte (txt, csv, eml) sont balayés en entier à la
recherche d'octets de contrôle ; les archives Word, Excel et OpenDocument sont ouvertes :
macros (`vbaProject.bin`, extensions `docm`, `xlsm`...) refusées, 2 000 entrées au plus,
200 Mo décompressés au plus, 20 fois la taille du fichier au plus dès 16 Mo (décidé sur
l'annuaire de l'archive, sans décompresser). Un fichier vide est refusé. Tailles maximales :
gabarits 10 Mo, pièces justificatives 50 Mo (`nginx` : 55 Mo sur `/api/`). Les fichiers de plus de 5 Mo
passent par un fichier temporaire (`FILE_UPLOAD_MAX_MEMORY_SIZE`), le corps hors fichiers est limité à 5 Mo, 5 fichiers
au plus par requête. Les téléchargements sont toujours en `Content-Disposition: attachment`
avec `X-Content-Type-Options: nosniff`, et le type servi vient de l'extension de la liste blanche.

Limite connue : les anciens formats OLE (`doc`, `xls`, `msg`) sont reconnus par signature mais
leurs macros ne sont pas inspectées ; l'antivirus est le recours.

## Antivirus

`ANTIVIRUS_MOTEUR` : `aucun` (développement seulement) ou `clamav` (synonyme historique :
`clamd`). En production, `clamav` est le défaut et `aucun` est refusé au démarrage sauf
`ANTIVIRUS_AUTORISER_AUCUN=true`. Le service `clamav` est livré dans `docker/compose.prod.yml`
(conteneur séparé, GPL-2.0). Chaque téléversement (gabarits, preuves, pièces, import CSV des
comptes) est envoyé au démon (INSTREAM, `ANTIVIRUS_CLAMD_HOTE`, `ANTIVIRUS_CLAMD_PORT`, délai
30 s) avant toute écriture : détection, 400 « Le fichier a été refusé par l'analyse
antivirus. » ; fichier de plus de 50 Mo, 400 « trop volumineux pour être analysé » ; démon
injoignable, en erreur ou trop lent, 503 « Analyse antivirus indisponible : réessayez plus
tard. » (échec fermé, `ANTIVIRUS_ECHEC_FERME=true` par défaut ; `false` accepte sans analyse et
journalise en ERROR). Procédures : `docs/exploitation/runbook.md` §11.

## Sauvegarde

Deux emplacements de fichiers sont à protéger : le **dossier des documents** (`DOCUMENTS_HOST_DIR`,
cette page) et le **volume Docker `onea-fichiers`** (pièces justificatives du lot 6, `FICHIERS_RACINE`,
jamais exposé par nginx). `scripts/backup.sh` (en root, `sudo` : le dossier appartient à 10001, mode
`0750`) sauvegarde, dans cet ordre : la base applicative, la base Keycloak, le volume `onea-fichiers`
(`fichiers-<horodatage>.tar.gz`), puis le dossier des documents (`documents-<horodatage>.tar.gz`). Chaque
archive est écrite en `.tmp`, vérifiée (`tar -tzf`) puis renommée ; un manifeste `manifeste-<horodatage>.sha256`
(SHA-256 des dumps et archives) est écrit en dernier. 14 jeux sont conservés.

Les bases passent en premier : l'archive contient tout fichier référencé par le dump. Un fichier
écrit entre le dump et l'archive est un **orphelin** (aucune ligne en base) : inoffensif grâce à
l'écriture unique, il est listé par `verifier_documents --orphelins` (et par `verifier_pieces` pour les
pièces) et **jamais supprimé automatiquement**.

**Copie hors serveur** : `backup.sh --hors-serveur` envoie le dossier de sauvegarde dans un dépôt
restic chiffré (destinations acceptées, mot de passe, minuteries et alerte par courriel :
`docs/deploy.md`, §7). Une sauvegarde qui reste sur le serveur ne protège pas de sa perte.

## Restauration

`sudo sh scripts/restore.sh <horodatage> --oui --dossier <dossier de sauvegarde>` automatise la
procédure ; le détail et les garde-fous sont dans `docs/deploy.md`, §7.4. En résumé :

1. contrôle du manifeste (refus d'un jeu altéré), arrêt de `web`, `worker`, `beat`, `keycloak` ;
2. `pg_restore --clean --if-exists --single-transaction` des deux bases, puis `installer_gardes_sql`
   (déclencheurs de gel et droits de `onea_app`, que le dump ne suffit pas à garantir) ;
3. le dossier des documents est **déplacé** en `<DOCUMENTS_HOST_DIR>-avant-restauration-<horodatage>`,
   l'archive est extraite, puis `chown -R 10001:10001` et `chmod 0750` ;
4. le volume `onea-fichiers` est copié dans `avant-restauration-fichiers-<horodatage>.tar.gz` puis remplacé ;
5. redémarrage ; `verifier_documents` (code 1 si un fichier référencé manque ou est altéré),
   `verifier_documents --orphelins` (informatif) et `verifier_pieces`.

Restauration d'un seul document : extraire son fichier de l'archive
(`tar -xzf documents-<h>.tar.gz -C <dossier> versions/<uuid>/v001.docx`), rétablir
`10001:10001`, puis lancer `verifier_documents`.

## Bascule future vers S3

Le stockage S3 compatible (par exemple un service interne de l'ONEA) se branche sans
changement de code : `DOCUMENTS_STORAGE=s3` avec `DOCUMENTS_S3_BUCKET`,
`DOCUMENTS_S3_ENDPOINT_URL`, `DOCUMENTS_S3_ACCESS_KEY` et `DOCUMENTS_S3_SECRET_KEY` (les
quatre sont obligatoires). Les objets sont écrits sans écrasement et sans accès public.
Migration : copier le dossier vers le bucket en conservant les clés, puis changer la
configuration.
