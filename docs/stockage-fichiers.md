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
| `DOCUMENTS_QUOTA_MO` | 0 | réglage réservé : le quota (somme des tailles en base) sera appliqué par la couche documents (tâches suivantes du lot 4) ; le stockage seul ne l'applique pas ; 0 = sans quota |
| `DOCUMENTS_MAX_GABARIT_MO` | 10 | taille maximale d'un gabarit Word téléversé |

`GET /api/v1/health/` renvoie `stockage_documents` : `ok`, `faible` (espace libre sous le
seuil) ou `indisponible` (dossier absent ou non inscriptible). Cet indicateur n'altère pas
`status`. À surveiller par la supervision du serveur.

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
