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

## Antivirus (point d'extension)

`ANTIVIRUS_MOTEUR` : `aucun` (défaut, aucune analyse) ou `clamd`. Avec `clamd`, le fichier est
envoyé au démon ClamAV (protocole INSTREAM, `ANTIVIRUS_CLAMD_HOTE`, `ANTIVIRUS_CLAMD_PORT`,
délai 30 s) avant toute écriture : détection → 400 « Le fichier a été refusé par l'analyse
antivirus. » ; démon injoignable, en erreur ou trop lent → 503 « Analyse antivirus
indisponible : réessayez plus tard. » (le fichier n'est jamais accepté sans analyse). Régler
`StreamMaxLength` du démon à 50 Mo au moins. Le service ClamAV lui-même n'est pas livré
(décision U4).

## Sauvegarde

`scripts/backup.sh` (à lancer en root, `sudo` : le dossier appartient à l'utilisateur 10001 en mode `0750`) sauvegarde, dans cet ordre, la base applicative, la base Keycloak, puis
archive le dossier des documents (`documents-AAAAMMJJ-HHMMSS.tar.gz`, écrite en `.tmp` puis
renommée ; 14 archives conservées). Les bases passent en premier : l'archive contient donc
tout fichier référencé par le dump.

**Copie hors serveur recommandée** : copier chaque nuit le dossier de sauvegarde vers un
autre site ou un autre support (`rsync`, partage réseau de l'ONEA, bande). Une sauvegarde
qui reste sur le serveur ne protège pas d'une perte du serveur.

## Restauration

1. Arrêter `web` et `worker`.
2. Restaurer la base : `pg_restore` du dump choisi (voir `docs/deploy.md`).
3. Vider puis restaurer le dossier des documents depuis l'archive du même horodatage :
   `tar -xzf documents-AAAAMMJJ-HHMMSS.tar.gz -C /srv/onea/documents`, puis
   `chown -R 10001:10001` et `chmod 0750` sur le dossier.
4. Redémarrer `web` et `worker`.
5. Vérifier la cohérence base/fichiers avec la commande `verifier_documents` (tâche T6 du
   lot 4) : elle signale tout fichier référencé mais absent ou altéré.

## Bascule future vers S3

Le stockage S3 compatible (par exemple un service interne de l'ONEA) se branche sans
changement de code : `DOCUMENTS_STORAGE=s3` avec `DOCUMENTS_S3_BUCKET`,
`DOCUMENTS_S3_ENDPOINT_URL`, `DOCUMENTS_S3_ACCESS_KEY` et `DOCUMENTS_S3_SECRET_KEY` (les
quatre sont obligatoires). Les objets sont écrits sans écrasement et sans accès public.
Migration : copier le dossier vers le bucket en conservant les clés, puis changer la
configuration.
