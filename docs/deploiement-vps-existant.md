# Déploiement sur un VPS qui héberge déjà d'autres services

Procédure pas à pas pour installer la plateforme ONEA (Docker Compose) sur un VPS Linux **qui
fait déjà tourner d'autres services sans Docker**, derrière **un sous-domaine** (enregistrement
DNS `A`), sans toucher à ces services.

Principe : la pile ONEA vit dans ses propres conteneurs, réseaux et volumes (projet Compose
`onea-prod`). Le seul point de contact avec l'hôte est **un port en boucle locale**
(`127.0.0.1:8080`). Le Nginx déjà présent sur l'hôte reçoit le trafic public (80/443), termine le TLS
pour ce sous-domaine **seulement**, et le transmet à ce port. Une variante (section 11) existe si
l'hôte n'a **aucun** serveur web et que la pile peut prendre elle-même 80/443.

Ce document complète, sans le remplacer : [`deploy.md`](deploy.md) (référence du déploiement),
[`exploitation/runbook.md`](exploitation/runbook.md) (incidents) et
[`exploitation/mise-en-production.md`](exploitation/mise-en-production.md) (liste de contrôle).

## 0. Ce qui a été vérifié et ce qui ne l'a pas été

Vérifié (poste de développement, 2026-11-05) :

- `docker compose -f docker/compose.prod.yml -f docker/compose.vps-hote.yml config` (Compose v5.1.1) réussit avec
  l'exemple d'environnement : le nginx de l'application ne publie que `127.0.0.1:8080->80`, le réseau
  `edge` reçoit le sous-réseau `172.30.11.0/28`, `compose.prod.yml` seul reste valide.
- `nginx -t` réussit sur `docker/nginx/prod-hote.conf` (image `nginx:1.27.5-alpine`, hôtes `web` et
  `frontend` simulés).
- `scripts/diagnostic-vps.sh` : syntaxe `sh -n` correcte, et exécution sous Git Bash (Windows) sans
  erreur bloquante. `shellcheck` n'était pas installé : **non passé**.

**Non vérifié** : aucun essai sur un vrai VPS, ni sous Ubuntu, ni sous Debian ; ni installation de
Docker, ni émission de certificat, ni `docker compose up` complet, ni mesure de consommation mémoire.
Les commandes `apt`, `ufw`, `certbot`, `systemd` ci-dessous suivent la documentation officielle des
outils mais **n'ont pas été exécutées**. Les points les plus incertains sont signalés « à vérifier ».
Le vhost du Nginx de l'hôte est fourni en modèle : il doit être relu face aux vhosts existants.

## 1. Audit préalable du VPS (lecture seule)

Objectif : savoir ce qui occupe le serveur **avant** d'y toucher. Aucune commande de cette section ne
modifie quoi que ce soit.

```
# depuis un poste de travail : récupérer le dépôt n'est pas encore nécessaire,
# copier simplement le script sur le VPS
scp scripts/diagnostic-vps.sh utilisateur@IP_DU_VPS:/tmp/
ssh utilisateur@IP_DU_VPS
sudo sh /tmp/diagnostic-vps.sh | tee ~/diagnostic-avant.txt
```

Le script affiche : distribution et noyau, RAM et swap, CPU, disques, ports en écoute (`ss -tlnp`),
présence de Nginx/Apache/Caddy et leurs directives `listen`/`server_name`, Docker (version, réseaux et
sous-réseaux déjà pris), pare-feu (`ufw`, `nftables`, `iptables`), utilisateurs, services en cours.
Il se lit aussi commande par commande :

```
cat /etc/os-release; uname -r
free -h; nproc; df -hT -x tmpfs -x devtmpfs
sudo ss -tlnp
sudo nginx -T 2>/dev/null | grep -E 'listen|server_name'      # si Nginx est présent
sudo ufw status verbose; sudo nft list ruleset | head -50
docker --version 2>&1; docker compose version 2>&1
ip -4 route
```

Critères pour continuer :

| Point | Attendu | Si ce n'est pas le cas |
|---|---|---|
| Distribution | Ubuntu 22.04/24.04 LTS ou Debian 12/13 (64 bits) | autre : la section 3 ne s'applique pas telle quelle |
| RAM disponible | 4 Go libres au minimum selon `deploy.md` ; **6 Go libres recommandés** ici car le serveur porte déjà d'autres services (ClamAV seul réserve jusqu'à 3 Go ; chiffre à confirmer par un essai de charge, non mesuré) | ajouter de la RAM ou du swap ; ne pas descendre `CLAMAV_MEM_LIMIT` sous 2g |
| Disque | 20 Go libres + place pour les documents et les sauvegardes ; `/var/lib/docker` sur un volume qui a de la marge | repérer le volume avec `df -h /var/lib` |
| Ports | **80/443 déjà pris par un Nginx/Apache/Caddy de l'hôte** : cas probable, c'est la voie principale (sections 8 à 10). Rien sur 80/443 : variante possible (section 11) | |
| Port 8080 | libre sur 127.0.0.1 ; sinon choisir un autre `PORT_HOTE` | |
| Sous-réseaux | `172.30.10.0/28` et `172.30.11.0/28` absents des routes (`ip -4 route`) et des réseaux Docker | changer `ONEA_SUBNET_WEB`, `ONEA_NGINX_IP`, `ONEA_IP_RANGE_WEB`, `ONEA_SUBNET_EDGE` (section 7) |
| Docker | absent : section 3. Présent : noter sa version, ne **pas** le réinstaller, voir section 3.4 | |
| UID 10001 | non utilisé (les conteneurs ONEA écrivent en `10001:10001`) | un autre compte l'utilise : voir `docs/stockage-fichiers.md` |

Conserver `diagnostic-avant.txt` : il sert à prouver, en fin de procédure et en cas de
désinstallation, que les autres services n'ont pas bougé (comparer avec une seconde exécution).

## 2. DNS

Créer chez le gestionnaire de la zone un enregistrement :

```
audit.exemple.org.   IN  A     203.0.113.10      ; IP publique du VPS
audit.exemple.org.   IN  AAAA  2001:db8::10      ; seulement si le VPS est joignable en IPv6
```

`audit.exemple.org` est le **sous-domaine** (variable `PUBLIC_HOST` plus loin) ; `203.0.113.10` est une
adresse de documentation à remplacer. TTL court (300 s) pendant la mise en place.

- Ne créer un `AAAA` que si le vhost écoute aussi en IPv6 (`listen [::]:443`) : un `AAAA` sans réponse
  fait échouer Let's Encrypt.
- Pas de `CAA` à ajouter, sauf si la zone en a déjà : dans ce cas autoriser `letsencrypt.org`.

Vérifier depuis n'importe quel poste (la propagation peut prendre de quelques minutes à quelques heures) :

```
dig +short A audit.exemple.org
dig +short AAAA audit.exemple.org
```

Ne pas continuer à la section 10 (certificat) tant que le nom ne résout pas vers ce VPS.

## 3. Docker Engine et plugin Compose (dépôt officiel Docker)

### 3.1 Avant d'installer : l'effet de Docker sur le pare-feu

À lire, car le VPS héberge d'autres services :

- Docker écrit **ses propres règles `iptables`** (chaînes `DOCKER`, `DOCKER-USER`, `FORWARD`,
  `nat/POSTROUTING`). Un port publié par `-p 8080:80` ou `ports:` est ouvert **en contournant `ufw`**
  (les règles `ufw allow/deny` n'agissent pas sur les ports Docker). C'est pourquoi la surcouche ONEA
  publie **uniquement** `127.0.0.1:8080` : le port n'est pas joignable de l'extérieur, quel que soit `ufw`.
  **Ne jamais écrire un port sans `127.0.0.1:` dans un fichier Compose de ce serveur.**
- Docker active `net.ipv4.ip_forward=1` et fixe la politique de la chaîne `FORWARD` à `DROP`. Les
  services de l'hôte qui écoutent normalement (Nginx, SSH, bases) ne sont pas concernés. Seul un
  service qui **fait suivre des paquets** (VPN, routeur, conteneurs LXC/libvirt) peut être gêné :
  vérifier `iptables -S FORWARD` avant et après (le diagnostic l'affiche).
- Docker crée des ponts `docker0` et `br-xxxx` et réserve des sous-réseaux (par défaut `172.17.0.0/16`
  puis `172.18.0.0/16` et suivants). En cas de conflit avec un réseau de l'hébergeur ou un VPN, voir
  la section 19 (dépannage).
- Docker exige le paquet `iptables` (ou `nftables` avec la couche de compatibilité). Sous Debian 13
  minimal, il peut manquer : `sudo apt-get install -y iptables`.
- Le moteur nftables natif de Docker est encore présenté comme expérimental : **garder le moteur par
  défaut**.

### 3.2 Ubuntu (22.04, 24.04)

Commandes de la documentation officielle (https://docs.docker.com/engine/install/ubuntu/) :

```
# 1. Retirer d'éventuels paquets non officiels EN CONFLIT (ne retire PAS les images/conteneurs existants,
#    mais lire la liste proposée par apt avant de confirmer)
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
  dpkg -l "$pkg" >/dev/null 2>&1 && echo "présent : $pkg"
done
# si une ligne « présent » apparaît : s'arrêter et voir la section 3.4

# 2. Dépôt officiel
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

# 3. Installation
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 3.3 Debian (12, 13)

Documentation officielle : https://docs.docker.com/engine/install/debian/

```
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Vérifier l'empreinte de la clé contre la page officielle (ne pas se fier à ce document seul) :

```
sudo gpg --show-keys --with-fingerprint /etc/apt/keyrings/docker.asc
```

### 3.4 Contrôles et cas particuliers

```
sudo systemctl status docker --no-pager        # actif
sudo docker --version
sudo docker compose version                    # 2.24.4 ou plus récent exigé par !override (seuil à vérifier dans les notes de version Compose)
sudo iptables -S FORWARD | head -3             # constater la politique DROP
```

**Pas** de `docker run hello-world` obligatoire ; ne **pas** ajouter l'utilisateur d'exploitation au
groupe `docker` : ce groupe donne un accès équivalent à root. Les commandes de ce document passent par
`sudo`.

Cas « Docker est déjà installé sur ce VPS » : ne pas le réinstaller ni le mettre à jour sans accord du
propriétaire des conteneurs existants (un redémarrage du démon arrête ces conteneurs, sauf
`"live-restore": true` dans `/etc/docker/daemon.json`). Vérifier seulement `docker compose version` ;
si le plugin manque ou est trop ancien, `sudo apt-get install -y docker-compose-plugin` suffit, sans
toucher au démon. Si Docker vient d'une autre source (snap, `docker.io`), le plugin officiel peut ne
pas s'y installer : demander au propriétaire plutôt que de remplacer le paquet.

Option utile (facultative, **ne la créer que si le démon vient d'être installé** par vous) :

```
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "live-restore": true,
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
sudo systemctl restart docker
```

## 4. Utilisateur dédié et arborescence

```
# Compte sans mot de passe, ni sudo, ni groupe docker : propriétaire du code uniquement
sudo adduser --disabled-password --gecos "" onea
id onea                                         # l'UID n'est PAS 10001

sudo install -d -o onea -g onea -m 0755 /opt/onea           # dépôt (les unités systemd du dépôt supposent ce chemin)
sudo install -d -m 0700 /etc/onea                            # secrets, certificats, configuration de sauvegarde
sudo install -d -m 0755 /etc/onea/certs                      # VIDE : exigé par compose.prod.yml, non monté ici
sudo install -d -o 10001 -g 10001 -m 0750 /srv/onea/documents    # documents générés (docs/stockage-fichiers.md)
sudo install -d -m 0700 /srv/onea-backups                    # sauvegardes locales
sudo install -d -m 0755 /var/www/onea-acme                   # défi ACME http-01 (section 10)
```

| Chemin | Contenu | Propriétaire |
|---|---|---|
| `/opt/onea` | dépôt Git, `.env.prod` | `onea` (le `.env.prod` : `root`, 0600) |
| `/etc/onea/secrets` | fichiers de secrets | `10001:10001`, dossier 0700 |
| `/etc/onea/sauvegarde.env`, `/etc/onea/restic.pass` | sauvegarde | `root`, 0600 |
| `/srv/onea/documents` | documents Word/PDF | `10001:10001`, 0750 |
| `/srv/onea-backups` | jeux de sauvegarde | `root`, 0700 |
| volumes Docker `onea-prod_*` | base, Redis, Meilisearch, pièces justificatives, signatures ClamAV | gérés par Docker (`/var/lib/docker`) |

Si le disque est partitionné, placer `/srv/onea` et `/srv/onea-backups` sur un volume qui a de la marge
(l'application surveille l'espace libre, `DOCUMENTS_ESPACE_MIN_LIBRE_MO`).

Le compte `onea` ne sert qu'à récupérer le code (`git`) : les conteneurs ont leur propre utilisateur
interne (UID 10001) et les commandes d'exploitation utilisent `sudo`.

## 5. Récupérer le code

```
# Remplacer <URL> par l'adresse du dépôt ONEA (non connue de ce document) et <étiquette> par la version
sudo -u onea git clone <URL> /opt/onea
cd /opt/onea
sudo -u onea git checkout <étiquette>            # une étiquette de version, pas une branche mouvante
sudo -u onea git describe --tags --always
```

Sans accès Git depuis le VPS : envoyer une archive `git archive --format=tar.gz -o onea.tar.gz <étiquette>`
puis `sudo -u onea tar -xzf onea.tar.gz -C /opt/onea`. Le build des images a besoin d'accès sortant
(Docker Hub, registre npm, PyPI) : vérifier avec `curl -sSI https://registry-1.docker.io/v2/ | head -1`
(un `401` est normal).

## 6. Secrets (fichiers `*_FILE`)

Les secrets ne sont **jamais** dans `.env.prod` : un fichier par secret, monté en lecture seule sous
`/run/secrets` dans les conteneurs ; Django lit `<NOM>_FILE` en priorité.

```
cd /opt/onea
sudo sh scripts/generer-secrets.sh --dossier /etc/onea/secrets      # crée ce qui manque, n'écrase jamais
sudo sh scripts/generer-secrets.sh --verifier --dossier /etc/onea/secrets
sudo ls -l /etc/onea/secrets                                         # 0600, propriétaire 10001:10001
```

Huit fichiers sont créés (`secret_key`, `secret_key_fallbacks` vide, `postgres_password`,
`postgres_app_password`, `redis_password`, `meili_master_key`, `metrics_token`, `email_password` vide).
Si le relais SMTP exige un mot de passe :

```
read -rsp "Mot de passe SMTP : " P; echo
printf '%s' "$P" | sudo tee /etc/onea/secrets/email_password >/dev/null; unset P
sudo chown 10001:10001 /etc/onea/secrets/email_password; sudo chmod 0600 /etc/onea/secrets/email_password
```

**Sauvegarder `/etc/onea/secrets` dans un coffre** (hors du serveur et hors du dépôt) : une sauvegarde
de base sans ses secrets ne permet pas de reconstruire le service. Ne jamais coller un secret dans un
courriel, un ticket ou l'historique du shell.

## 7. Fichier d'environnement `.env.prod`

```
sudo install -m 0600 -o root -g root /opt/onea/.env.prod.example /opt/onea/.env.prod
sudo nano /opt/onea/.env.prod
```

Contenu **complet** à obtenir (remplacer l'exemple de domaine ; aucun secret ici) :

```
# --- Secrets : dossier des fichiers de la section 6 ---
ONEA_SECRETS_DIR=/etc/onea/secrets

# --- Nom public : sous-domaine du DNS (section 2) ---
PUBLIC_HOST=audit.exemple.org
# Exigé par compose.prod.yml mais non monté avec la surcouche : dossier vide
TLS_CERT_DIR=/etc/onea/certs
ACME_WEBROOT=/var/www/onea-acme
CA_BUNDLE_PATH=

# --- Réseaux Docker de la pile (isolés : aucun lien avec les services de l'hôte) ---
ONEA_SUBNET_WEB=172.30.10.0/28
ONEA_NGINX_IP=172.30.10.2
ONEA_IP_RANGE_WEB=172.30.10.8/29
ONEA_SUBNET_EDGE=172.30.11.0/28
# Port local sur lequel le Nginx HÔTE trouvera l'application (127.0.0.1 uniquement)
PORT_HOTE=8080

# --- Version des images ---
APP_VERSION=1.0.0

# --- Django ---
DJANGO_ADMIN_ENABLED=false
EMAIL_URL=smtp+tls://compte@smtp.exemple.org:587

# --- PostgreSQL ---
POSTGRES_DB=onea
POSTGRES_USER=onea
POSTGRES_APP_USER=onea_app

# --- Documents ---
DOCUMENTS_HOST_DIR=/srv/onea/documents

# --- Antivirus ClamAV ---
ANTIVIRUS_MOTEUR=clamav
ANTIVIRUS_ECHEC_FERME=true
ANTIVIRUS_AUTORISER_AUCUN=false
CLAMAV_MEM_LIMIT=3g

# --- Facultatif ---
# COMPOSE_PROJECT_NAME=onea-prod
# WEB_CONCURRENCY=3
```

Explication de chaque variable :

| Variable | Rôle et valeur sur ce VPS |
|---|---|
| `ONEA_SECRETS_DIR` | dossier des fichiers de secrets (section 6). Absolu, 0700. |
| `PUBLIC_HOST` | **sous-domaine seul**, sans `https://`. Alimente `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS=https://<hôte>`, `PLATEFORME_URL` (liens des courriels) et `VITE_API_URL` du frontend **construit dans l'image** : changer de domaine impose de reconstruire (`build`). |
| `TLS_CERT_DIR` | **sans effet** avec la surcouche (le TLS est celui de l'hôte) mais Compose l'exige : laisser le dossier vide `/etc/onea/certs`. |
| `ACME_WEBROOT`, `CA_BUNDLE_PATH` | `ACME_WEBROOT` n'est plus monté ; `CA_BUNDLE_PATH` : chemin **dans le conteneur** d'un PEM de `/opt/onea/certs/` seulement si le relais SMTP a un certificat d'une autorité interne (il **remplace** le magasin de confiance : y mettre toutes les autorités utiles). Vide sinon. |
| `ONEA_SUBNET_WEB`, `ONEA_NGINX_IP`, `ONEA_IP_RANGE_WEB` | réseau interne entre le Nginx de la pile et l'application. **`ONEA_NGINX_IP` est l'unique adresse que Django croit** (voir l'encadré ci-dessous). `ONEA_IP_RANGE_WEB` doit être dans le sous-réseau et **ne pas contenir** `ONEA_NGINX_IP`. À changer seulement en cas de conflit avec `ip -4 route`. |
| `ONEA_SUBNET_EDGE` | sous-réseau fixe du pont qui relie le Nginx de la pile à l'hôte (surcouche). Sa passerelle (`.1`) est l'adresse vue lorsque le Nginx hôte se connecte : c'est la seule plage dont `X-Forwarded-For` est cru par le Nginx de la pile (`TRUSTED_UPSTREAM_CIDRS`). |
| `PORT_HOTE` | port de `127.0.0.1` où la pile écoute (défaut 8080). Doit être libre ; identique dans le vhost de la section 9. |
| `APP_VERSION` | étiquette des images `onea-backend` / `onea-frontend` ; la changer à chaque version, elle permet le retour arrière. |
| `DJANGO_ADMIN_ENABLED` | `/admin/` désactivé ; ne l'activer que ponctuellement. |
| `EMAIL_URL` | relais SMTP de l'ONEA **sans mot de passe** : `smtp+tls://` (STARTTLS, 587), `smtps://` (TLS direct, 465), `smtp://` (relais interne en clair). Le mot de passe va dans le secret `email_password`. `dummymail://` n'envoie rien (mode dégradé, `deploy.md` §5.5). La sortie SMTP du VPS doit être autorisée (port 587/465 sortant). Mailpit n'existe pas en production. |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_APP_USER` | base, propriétaire (migrations, sauvegardes) et rôle applicatif sans DELETE/TRUNCATE. `POSTGRES_APP_USER` doit différer de `POSTGRES_USER`. PostgreSQL n'écoute que dans le réseau Docker `backend` : le PostgreSQL éventuel de l'hôte n'est pas concerné (pas de conflit de port). |
| `DOCUMENTS_HOST_DIR` | dossier de la section 4, créé à l'avance (`create_host_path: false`). |
| `ANTIVIRUS_*` | ClamAV est un conteneur de la pile, joint par `clamav:3310` sur un réseau interne (valeur fixée par `compose.prod.yml`, rien à régler). `aucun` est refusé en production. Échec fermé : tant que ClamAV n'est pas `healthy`, les dépôts de fichiers sont refusés. |
| `CLAMAV_MEM_LIMIT` | plafond mémoire du conteneur ClamAV (3g conseillé). |

> **Piège `TRUSTED_PROXY_CIDRS` et `X-Real-IP`.** `TRUSTED_PROXY_CIDRS` n'est **pas** une ligne de
> `.env.prod` : `compose.prod.yml` la fixe à `ONEA_NGINX_IP`. Django ne croit `X-Real-IP` que s'il vient
> du Nginx **de la pile** (172.30.10.2), jamais de l'hôte. Ne pas y mettre l'adresse du Nginx hôte
> ni `0.0.0.0/0` : vide ou faux, tous les agents partageraient le même compteur anti-force-brute
> (30 échecs de n'importe qui bloquent tout le monde), et la production refuse de démarrer si la
> liste est vide. La chaîne de confiance est : client -> Nginx hôte (pose `X-Forwarded-For` = adresse
> réelle, **en écrasant** ce que le client envoie) -> Nginx de la pile (croit cette valeur uniquement
> de l'`edge`, puis pose `X-Real-IP`) -> Django (croit `X-Real-IP` du seul Nginx de la pile).
>
> **`ONEA_IGNORE_DOTENV`** concerne un hébergement **sans** Docker (un `.env` oublié dans le dépôt
> serait lu par Django). Ici `.dockerignore` exclut `**/.env*` des images : rien à régler.
> **Hôte antivirus** : également propre à l'hébergement sans Docker (`ANTIVIRUS_CLAMD_HOTE` vaut `clamav`
> par défaut) ; ici `compose.prod.yml` le fixe, aucune action.

Valider, puis créer une commande courte qui évite d'oublier la surcouche (**oublier le second `-f`
ferait publier 80/443 par la pile au prochain `up`**) :

```
sudo tee /usr/local/bin/onea-dc >/dev/null <<'EOF'
#!/bin/sh
exec docker compose --env-file /opt/onea/.env.prod \
  -f /opt/onea/docker/compose.prod.yml -f /opt/onea/docker/compose.vps-hote.yml "$@"
EOF
sudo chmod 0755 /usr/local/bin/onea-dc
sudo onea-dc config -q && echo "configuration valide"
sudo onea-dc config | grep -A6 'ports:' | head -12      # attendu : host_ip 127.0.0.1, published "8080"
```

Dans la suite, `onea-dc` remplace le `dc` des autres documents (`dc` = `docker compose --env-file
.env.prod -f docker/compose.prod.yml`).

## 8. Démarrage de la pile derrière le Nginx de l'hôte

```
cd /opt/onea
sudo onea-dc up -d --build        # première fois : 10 à 25 minutes (images, ~300 Mo de signatures ClamAV)
sudo onea-dc ps
```

Le service `migrate` s'exécute d'abord (migrations, index de recherche, fichiers statiques) ; `web`,
`worker`, `worker-auth` et `beat` attendent sa fin réussie. Attendre que tout soit `healthy`
(`clamav` en dernier : 1 à 3 minutes après le téléchargement) :

```
sudo onea-dc ps --format 'table {{.Service}}\t{{.State}}\t{{.Health}}'
sudo onea-dc logs migrate | tail -20
sudo ss -tlnp | grep -E ':8080\b'      # attendu : 127.0.0.1:8080, jamais 0.0.0.0:8080
sudo ss -tlnp | grep -E ':(80|443)\b'  # inchangé par rapport au diagnostic : toujours les services de l'hôte
curl -fsS -H 'Host: audit.exemple.org' http://127.0.0.1:8080/api/v1/health/ready/
```

Si `migrate` échoue : `sudo onea-dc logs migrate` (cause la plus fréquente : `ImproperlyConfigured`
sur une variable manquante, voir la section 19).

## 9. Vhost du Nginx de l'hôte

Le Nginx de l'hôte garde ses vhosts existants ; on **ajoute un fichier**, on ne modifie aucun autre.
Le Nginx de la pile envoie déjà tous les en-têtes de sécurité (HSTS, CSP, `X-Frame-Options`,
`Referrer-Policy`, `Permissions-Policy`, COOP/CORP) : **ne pas les redéclarer** dans le vhost hôte
(ils apparaîtraient deux fois).

Créer d'abord le vhost HTTP seul, pour l'émission du certificat (section 10) :

```
sudo tee /etc/nginx/sites-available/onea-audit-http.conf >/dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;                 # retirer si le VPS n'a pas d'IPv6 (et pas d'enregistrement AAAA)
    server_name audit.exemple.org;

    location /.well-known/acme-challenge/ {
        root /var/www/onea-acme;
        default_type text/plain;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}
EOF
sudo ln -s /etc/nginx/sites-available/onea-audit-http.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

(Sur une distribution sans `sites-available`, placer le fichier dans `/etc/nginx/conf.d/` en `.conf`.)
Le `server_name` exact fait que ce vhost ne répond qu'à ce sous-domaine : les autres vhosts, y compris
un éventuel `default_server`, ne sont pas modifiés. Le rechargement (`reload`) ne coupe pas les
connexions en cours.

Le vhost HTTPS complet vient **après** le certificat (section 10). Voici le fichier à créer à ce moment :

```
# /etc/nginx/sites-available/onea-audit.conf
server {
    listen 443 ssl;
    listen [::]:443 ssl;                       # retirer sans IPv6
    # nginx >= 1.25.1 : ajouter la ligne   http2 on;
    # nginx < 1.25.1 (Ubuntu 24.04 : 1.24) : écrire plutôt   listen 443 ssl http2;
    server_name audit.exemple.org;

    ssl_certificate     /etc/letsencrypt/live/audit.exemple.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/audit.exemple.org/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:ONEA_SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    # ssl_protocols/ssl_ciphers : si d'autres vhosts partagent 443, c'est la valeur du
    # serveur par défaut de l'adresse qui s'applique à la négociation. Ne pas toucher aux leurs.

    server_tokens off;

    # Téléversement des pièces : 50 Mo + enveloppe multipart. Le Nginx de la pile refuse au-delà
    # (55m sur /api/, 1m ailleurs) ; ce plafond ne fait que ne pas être plus bas.
    client_max_body_size 55m;

    access_log /var/log/nginx/onea-audit.access.log;
    error_log  /var/log/nginx/onea-audit.error.log warn;
    # Le format "combined" par défaut écrit l'URL complète, query string comprise : à relire avec
    # docs/securite/auth-interne-modele.md si un format sans query string est exigé.

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        # SET, jamais "append" : ne PAS utiliser $proxy_add_x_forwarded_for. Tout ce que le client a
        # envoyé dans X-Forwarded-For / X-Real-IP est ignoré, c'est ce qui rend les limites par adresse sûres.
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host  $host;
        proxy_set_header Connection        "";
        proxy_read_timeout 130s;               # gunicorn : 120 s
        proxy_send_timeout 130s;
        proxy_connect_timeout 5s;
    }
}
```

Points d'attention :

- **WebSockets** : l'application n'en utilise aucun (ni Channels ni SSE, vérifié par recherche dans le
  code). Aucun `Upgrade`/`Connection upgrade` à ajouter.
- Si l'hôte est lui-même derrière un CDN ou un répartiteur, `$remote_addr` y est l'adresse de ce
  répartiteur : y configurer `set_real_ip_from`/`real_ip_header` **dans ce Nginx hôte** avant d'ouvrir
  l'application, sinon toutes les limites par adresse retombent sur un seul compteur.
- Si l'hôte est Apache ou Caddy plutôt que Nginx : même principe (proxy vers `127.0.0.1:8080`, `Host`
  conservé, `X-Forwarded-Proto: https`, `X-Real-IP`/`X-Forwarded-For` **écrasés** par l'adresse du pair).
  Gabarit non fourni ni testé.
- Activer après le certificat : `sudo ln -s /etc/nginx/sites-available/onea-audit.conf
  /etc/nginx/sites-enabled/` puis `sudo nginx -t && sudo systemctl reload nginx`.

## 10. TLS avec certbot, pour ce sous-domaine seulement

Prérequis : le DNS résout vers ce VPS (section 2), le vhost HTTP (section 9) est actif, le pare-feu
laisse passer 80 et 443 (déjà le cas si l'hôte sert d'autres sites).

```
sudo apt-get install -y certbot            # sans le greffon nginx : il ne modifiera aucun autre vhost
sudo certbot --version
sudo certbot certonly --webroot -w /var/www/onea-acme -d audit.exemple.org \
  --cert-name audit.exemple.org --email dsi@exemple.org --agree-tos --no-eff-email \
  --deploy-hook "systemctl reload nginx" --dry-run          # essai à blanc, serveur de test
sudo certbot certonly --webroot -w /var/www/onea-acme -d audit.exemple.org \
  --cert-name audit.exemple.org --email dsi@exemple.org --agree-tos --no-eff-email \
  --deploy-hook "systemctl reload nginx"
sudo ls -l /etc/letsencrypt/live/audit.exemple.org/
```

- `-d` ne désigne **que** ce nom : aucun autre certificat n'est créé ni modifié. Si l'hôte utilise déjà
  certbot pour d'autres sites, `--cert-name` isole ce certificat ; `certbot certificates` les liste tous.
- Renouvellement : le paquet `certbot` installe sa minuterie (`systemctl list-timers | grep certbot`) ;
  si l'hôte a installé certbot par `snap`, c'est le renouvellement `snap` qui s'applique (déjà actif).
  L'option `--deploy-hook` est mémorisée dans `/etc/letsencrypt/renewal/audit.exemple.org.conf`.
  Essai : `sudo certbot renew --dry-run`.
- `scripts/tls/certbot.sh` et `onea-certificat.timer` du dépôt servent à la variante où **la pile**
  porte le TLS (section 11) : ne pas les activer ici.

Puis installer le vhost HTTPS de la section 9 et recharger :

```
sudo tee /etc/nginx/sites-available/onea-audit.conf >/dev/null    # coller le fichier de la section 9, domaine adapté
sudo ln -s /etc/nginx/sites-available/onea-audit.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
curl -sSI https://audit.exemple.org/ | head -15
```

Attendu : `HTTP/2 200` (ou `HTTP/1.1 200`), un seul `Strict-Transport-Security`, un `Content-Security-Policy`,
`X-Frame-Options: DENY`. Contrôle externe facultatif (service tiers) : https://www.ssllabs.com/ssltest/.

## 11. Variante : la pile prend elle-même 80 et 443

**Uniquement** si le diagnostic montre que **rien** n'écoute sur 80/443 et que rien d'autre ne le fera
(sinon, rester sur les sections 8 à 10). On n'utilise alors **pas** la surcouche :

```
# 1. Le DNS résout déjà (section 2). Ouvrir 80/443 si ufw est actif
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
# 2. .env.prod : TLS_CERT_DIR=/etc/onea/certs, ACME_WEBROOT=/var/www/onea-acme, LETSENCRYPT_EMAIL=dsi@exemple.org
# 3. Démarrer la pile seule (sans -f compose.vps-hote.yml)
sudo docker compose --env-file /opt/onea/.env.prod -f /opt/onea/docker/compose.prod.yml up -d --build
# 4. Certificat (voie B de deploy.md §2.2) : essai, puis réel
sudo sh scripts/tls/certbot.sh --dry-run
sudo sh scripts/tls/certbot.sh --production
# 5. Renouvellement automatique
sudo cp docker/ops/onea-certificat.* /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now onea-certificat.timer
```

Le premier `up` échoue (nginx ne trouve pas les certificats) tant que `fullchain.pem` et `privkey.pem`
n'existent pas : pour l'amorçage, voir `deploy.md` §2.2. Dans cette variante, remplacer `onea-dc` par la
commande de l'étape 3. **Si un Nginx hôte est installé un jour, repasser à la voie principale** : deux
serveurs ne partagent pas 80/443.

## 12. Migrations, premier administrateur et comptes

Les migrations ont déjà été appliquées par le service `migrate` (section 8). Contrôle explicite :

```
sudo onea-dc run --rm migrate python manage.py showmigrations | grep -c '\[ \]'          # 0 attendu
sudo onea-dc run --rm migrate python manage.py installer_gardes_sql --verifier --exiger-role   # code 0
```

Premier administrateur (la base démarre sans compte) :

```
sudo onea-dc exec web python manage.py creer_administrateur --identifiant <identifiant> --courriel <adresse>
```

- Le mot de passe temporaire (16 caractères, valable 72 h) est affiché **une seule fois** : le noter
  immédiatement, ne pas le rediriger vers un fichier. Il sera à changer à la première connexion
  (12 caractères minimum).
- Créer ensuite un **second administrateur nominatif** (écran *Utilisateurs*) : pas de compte partagé.
- Test du courrier (depuis le `worker`, seul conteneur qui joint le relais) :
  `sudo onea-dc exec worker python manage.py envoyer_courriel_test destinataire@exemple.org`.

Comptes existants sans mot de passe (reprise d'une base qui venait de l'ancienne authentification) :

```
sudo onea-dc exec web python manage.py donner_mots_de_passe_temporaires --a-blanc     # liste, ne modifie rien
sudo onea-dc exec web python manage.py donner_mots_de_passe_temporaires               # donne et affiche UNE fois
```

La sortie `identifiant<TAB>mot de passe` se transmet par un canal sûr puis s'efface.

Migrer la base de démonstration : le chemin prévu et documenté est un **jeu de sauvegarde produit par
`scripts/backup.sh`** sur l'ancienne pile, copié dans `/srv/onea-backups`, puis `restore.sh`
(section 14.3) et `donner_mots_de_passe_temporaires`. Un `pg_dump` brut d'une base de développement
n'est ni prévu ni testé ici : rôles, propriétaires et gardes SQL diffèrent. Pour une recette, il est plus
sûr de partir d'une base vide et d'importer les comptes (`import_accounts`, `deploy.md` §5.2).

## 13. Vérifications de santé

```
sudo onea-dc ps                                                         # tout « running », health « healthy »
curl -fsS https://audit.exemple.org/api/v1/health/ready/                # 200
curl -fsS https://audit.exemple.org/api/v1/health/                      # {"status":"ok", ...} avec la version
sudo onea-dc exec worker sh -c 'celery -A config inspect ping -d celery@$HOSTNAME -t 5'
sudo onea-dc exec worker-auth sh -c 'celery -A config inspect ping -d auth@$HOSTNAME -t 5'
curl -sI http://audit.exemple.org/ | head -3                            # 301 vers https
```

Contrôle de l'adresse réelle du client (garantit que les limites par adresse sont par agent) :

```
curl -s -o /dev/null https://audit.exemple.org/api/v1/health/
sudo onea-dc logs --tail=3 nginx | grep health
```

Le champ `remote_addr` du journal JSON doit être **votre adresse publique**, pas `172.30.11.1` (passerelle
`edge`) ni `172.30.10.x`. Si c'est la passerelle : `X-Forwarded-For` n'est pas cru, vérifier
`TRUSTED_UPSTREAM_CIDRS` (`sudo onea-dc exec nginx cat /etc/nginx/conf.d/realip.conf`) et l'adresse de
l'hôte vue par le conteneur (`ip -4 addr show | grep -A2 br-`). *À vérifier sur le VPS : c'est le point de
la surcouche que le poste de développement ne pouvait pas tester.*

Contrôle que la pile n'est **pas** exposée en direct, depuis un poste extérieur :

```
curl -m 5 http://IP_DU_VPS:8080/        # attendu : refus/délai
nmap -Pn -p 8080,5432,6379,7700,3000,3310 IP_DU_VPS   # tous « closed » ou « filtered »
```

## 14. Sauvegardes et restauration

### 14.1 Configuration

```
sudo tee /etc/onea/sauvegarde.env >/dev/null <<'EOF'
ONEA_SAUVEGARDE_DIR=/srv/onea-backups
# IMPORTANT sur ce serveur : sans cette ligne, backup.sh/restore.sh appellent compose sans la surcouche
# et restore.sh recréerait nginx en publiant 80/443 (conflit avec le Nginx de l'hôte).
ONEA_COMPOSE_FICHIERS=/opt/onea/docker/compose.vps-hote.yml
# Copie hors serveur chiffrée (restic), décision U1 : laisser vide tant qu'elle n'est pas prise
ONEA_SAUVEGARDE_OPTIONS=
# RESTIC_REPOSITORY=sftp:sauvegarde@serveur2:/srv/restic-onea
# RESTIC_PASSWORD_FILE=/etc/onea/restic.pass
ALERTE_SMTP_URL=smtp://relais.exemple.org:587
ALERTE_MAIL_DE=sauvegarde@exemple.org
ALERTE_MAIL_A=dsi@exemple.org
EOF
sudo chmod 0600 /etc/onea/sauvegarde.env
```

Copie hors serveur : `sudo apt-get install -y restic`, puis `deploy.md` §7.2 (initialisation du dépôt,
mot de passe confié à deux personnes). Une sauvegarde qui reste sur le serveur ne protège pas de sa perte.

### 14.2 Planification (minuteries systemd, recommandé)

```
cd /opt/onea
sudo cp docker/ops/onea-sauvegarde.* docker/ops/onea-verification-sauvegarde.* docker/ops/onea-alerte@.service /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/onea-sauvegarde.service /etc/systemd/system/onea-sauvegarde.timer
sudo systemctl daemon-reload
sudo systemctl enable --now onea-sauvegarde.timer          # chaque nuit à 02:00 UTC
sudo systemctl enable --now onea-verification-sauvegarde.timer   # seulement si la copie restic est configurée
systemctl list-timers 'onea-*'
sudo systemctl start onea-sauvegarde.service && journalctl -u onea-sauvegarde.service -n 30 --no-pager
```

Alternative cron (si l'on préfère ne pas utiliser systemd) :

```
sudo tee /etc/cron.d/onea-sauvegarde >/dev/null <<'EOF'
0 2 * * * root set -a; . /etc/onea/sauvegarde.env; set +a; cd /opt/onea && sh scripts/backup.sh $ONEA_SAUVEGARDE_OPTIONS $ONEA_SAUVEGARDE_DIR >> /var/log/onea-sauvegarde.log 2>&1
EOF
```

Un jeu complet contient `onea-<h>.dump`, `fichiers-<h>.tar.gz`, `documents-<h>.tar.gz` et
`manifeste-<h>.sha256` (écrit en dernier : sans lui le jeu est incomplet). 14 jeux sont conservés.

### 14.3 Test de restauration

```
ls /srv/onea-backups
sudo env ONEA_COMPOSE_FICHIERS=/opt/onea/docker/compose.vps-hote.yml \
  sh /opt/onea/scripts/restore.sh <AAAAMMJJ-HHMMSS> --verifier --dossier /srv/onea-backups     # contrôle seul
```

Faire **une restauration réelle avant l'ouverture aux agents** (la base est encore vide ou jetable ;
après l'ouverture, elle est destructive) :

```
sudo env ONEA_COMPOSE_FICHIERS=/opt/onea/docker/compose.vps-hote.yml \
  sh /opt/onea/scripts/restore.sh <AAAAMMJJ-HHMMSS> --oui --dossier /srv/onea-backups
```

Le script contrôle les empreintes, restaure la base, rétablit les gardes SQL, les documents et les
pièces, redémarre, réindexe, puis exécute `verifier_documents` et `verifier_pieces` (code 1 si échec).
Reprise sur un serveur neuf et exercice trimestriel : `deploy.md` §7.4 et `runbook.md` §7.

## 15. Mises à jour et retour arrière

Mise à jour (sauvegarde d'abord) :

```
cd /opt/onea
curl -fsS https://audit.exemple.org/api/v1/health/ | tee /tmp/version-avant.json     # noter la version en service
sudo systemctl start onea-sauvegarde.service                                         # ou backup.sh à la main
ls -t /srv/onea-backups/manifeste-*.sha256 | head -1                                 # un nouveau jeu complet existe
sudo -u onea git fetch --tags && sudo -u onea git checkout <nouvelle-étiquette>
sudo sed -i 's/^APP_VERSION=.*/APP_VERSION=1.1.0/' /opt/onea/.env.prod                # nouvelle étiquette
sudo onea-dc build
sudo onea-dc up -d --remove-orphans
sudo onea-dc ps
curl -fsS https://audit.exemple.org/api/v1/health/ready/
sudo onea-dc run --rm migrate python manage.py installer_gardes_sql --verifier --exiger-role
```

Les notes de version peuvent exiger une fenêtre de maintenance (`deploy.md` §6 : arrêter `web worker beat`
avant `up` quand une migration supprime des colonnes). Lire les notes **avant** d'appliquer.

Retour arrière : les images de la version précédente restent sur le serveur (étiquette `APP_VERSION`).

```
sudo -u onea git checkout <étiquette-précédente>
sudo sed -i 's/^APP_VERSION=.*/APP_VERSION=1.0.0/' /opt/onea/.env.prod
sudo onea-dc up -d --no-build --remove-orphans
```

Le retour du code **ne défait pas une migration** : si le schéma a changé, restaurer en plus le jeu de
sauvegarde pris juste avant (section 14.3). Ne pas lancer `docker image prune -a` sur ce serveur (il
supprimerait les images de retour arrière, et celles des autres propriétaires de Docker, s'il y en a).

## 16. Supervision et journaux

```
sudo onea-dc logs -f --tail=100 web worker worker-auth nginx      # journaux JSON, sans donnée personnelle
sudo onea-dc logs --since=1h migrate beat
sudo journalctl -u docker --since today --no-pager
sudo docker stats --no-stream                                      # RAM par conteneur
df -h /var/lib/docker /srv/onea /srv/onea-backups
```

- Les journaux des conteneurs sont tournants (`json-file`, 10 Mo x 3 par service) : pas de
  `logrotate` à ajouter pour eux. Les journaux du vhost hôte (`/var/log/nginx/onea-audit.*.log`) sont
  couverts par le `logrotate` de Nginx s'il est configuré pour `/var/log/nginx/*.log` (c'est le défaut Debian/Ubuntu).
- Lecture par `correlation_id` : `runbook.md` §3. Contrôle quotidien de 5 minutes : `runbook.md` §4.
- Sonde externe simple (hors du serveur, via un outil de supervision libre) : `GET /api/v1/health/ready/` = 200.
  Sur le serveur, en dernier recours :
  ```
  sudo tee /etc/cron.d/onea-sonde >/dev/null <<'EOF'
  */5 * * * * root curl -fsS -m 10 https://audit.exemple.org/api/v1/health/ready/ >/dev/null || (set -a; . /etc/onea/sauvegarde.env; set +a; sh /opt/onea/scripts/alerte-mail.sh "ONEA : sonde en echec" "ready ne repond plus")
  EOF
  ```
  (non testé ; produit un courriel toutes les 5 minutes tant que la panne dure).

## 17. Durcissement

- **Pare-feu de l'hôte** : ne rien ouvrir de plus. 80/443 sont déjà servis par le Nginx hôte ; 22 reste
  ouvert comme avant. Vérifier qu'il n'existe aucune règle pour 8080 : `sudo ufw status numbered`.
  Ne pas activer `ufw` s'il ne l'est pas déjà sans avoir autorisé SSH et les ports des services existants.
- **Ne publier sur l'hôte qu'en `127.0.0.1`** (section 3.1). Contrôle périodique :
  `sudo docker ps --format '{{.Names}} {{.Ports}}' | grep -v '127.0.0.1' | grep '0.0.0.0'` ne doit rien
  renvoyer pour les conteneurs `onea-prod-*`.
- **Isolation** : la pile n'utilise que ses réseaux `onea-prod_*` (4 des 7 sont `internal`, sans route
  vers l'extérieur) ; `cap_drop: ALL`, `no-new-privileges`, images épinglées. Elle ne monte aucun
  dossier de l'hôte hors `DOCUMENTS_HOST_DIR`, et n'utilise ni `network_mode: host` ni `privileged`.
- **Sorties autorisées** : `worker` et `worker-auth` vers le relais SMTP, ClamAV vers
  `database.clamav.net` (HTTPS). Si l'hôte filtre le trafic sortant, autoriser ces destinations.
- **Secrets** : `/etc/onea/secrets` en 0700, `.env.prod` en 0600 `root` ; sauvegarde du coffre séparée de celle des données.
- **Mises à jour de sécurité** : l'hôte reçoit les correctifs système (`unattended-upgrades`) ; le paquet
  Docker vient du dépôt officiel et se met à jour par `apt` (un redémarrage du démon redémarre la pile, d'où
  `live-restore`). Les images de la pile se mettent à jour par `APP_VERSION` (section 15).
- **Compte d'exploitation** : accès SSH par clé, `PermitRootLogin no`, au moins deux personnes capables
  d'agir (deux administrateurs applicatifs, deux détenteurs du mot de passe restic).
- `/admin/` Django désactivé, `/api/docs/` réservé aux administrateurs, `/api/v1/metrics/` protégé par jeton.

## 18. Check-list de recette avant ouverture aux agents

- [ ] `diagnostic-vps.sh` rejoué : les ports, services et vhosts de l'hôte sont identiques à `diagnostic-avant.txt` (hors port 8080 sur 127.0.0.1 et ponts Docker).
- [ ] `https://audit.exemple.org/` charge l'application, certificat valide, redirection 80 -> 443, un seul HSTS.
- [ ] Les autres sites de l'hôte répondent exactement comme avant (liste fournie par leur propriétaire).
- [ ] `onea-prod-*` : tous les conteneurs `healthy` ; `clamav` inclus.
- [ ] `ss -tlnp` : 8080 seulement sur 127.0.0.1 ; `nmap` externe : aucun port de la pile ouvert.
- [ ] Connexion de l'administrateur, changement du mot de passe temporaire, second administrateur créé.
- [ ] Un code de connexion (courriel) arrive en moins d'une minute ; `envoyer_courriel_test` reçu.
- [ ] Le `remote_addr` du journal Nginx est l'adresse réelle ; 6 échecs de connexion depuis un poste ne bloquent pas un autre poste.
- [ ] Dépôt d'un PDF sain accepté ; fichier de test EICAR refusé (`runbook.md` §11) ; ClamAV arrêté -> dépôt refusé (503), puis redémarré.
- [ ] Génération d'un document Word -> PDF (Gotenberg) ; recherche (Meilisearch) trouve une fiche créée.
- [ ] Une sauvegarde complète a tourné (minuterie) ; `restore.sh --verifier` passe ; une restauration réelle a été jouée sur la base vide.
- [ ] Copie hors serveur configurée (ou décision U1 consignée) ; secrets sauvegardés dans le coffre.
- [ ] Renouvellement du certificat : `certbot renew --dry-run` réussit.
- [ ] `deploy.md`, `mise-en-production.md` (sections A à J) parcourus ; contacts d'astreinte connus.

## 19. Dépannage des erreurs probables

| Symptôme | Cause probable | Action |
|---|---|---|
| `docker compose config` : `unknown tag !override` / `services.nginx.ports ... invalid` | plugin Compose < 2.24.4 | `sudo apt-get install --only-upgrade docker-compose-plugin` (dépôt officiel, section 3) |
| `required variable ... is missing` | variable absente de `.env.prod` | lire le nom dans le message et le renseigner (section 7) |
| `Pool overlaps with other one on this address space` | `172.30.10.0/28` ou `172.30.11.0/28` déjà utilisé | `docker network ls`, `ip -4 route` ; changer les quatre variables de réseau, puis `onea-dc down` et `up -d` |
| `bind: address already in use` sur 8080 | autre service sur 127.0.0.1:8080 | choisir `PORT_HOTE=18080`, le même dans le vhost, `onea-dc up -d nginx`, recharger Nginx hôte |
| `migrate` en échec, `ImproperlyConfigured` | variable manquante (`EMAIL_URL`, `TRUSTED_PROXY_CIDRS` vide...) ou secret `CHANGE_ME` | `sudo onea-dc logs migrate` ; `generer-secrets.sh --verifier` |
| `web` redémarre en boucle, `SESSION_COOKIE_SECURE must be true` | variable écrasée | ne pas surcharger `SESSION_COOKIE_SECURE` (fixée à `true`) |
| `clamav` jamais `healthy`, `Killed` | RAM insuffisante (OOM) ou téléchargement bloqué | `free -h`, `dmesg \| grep -i oom`, ajouter du swap/RAM ; vérifier la sortie HTTPS vers `database.clamav.net` |
| dépôts de fichiers en 503 | ClamAV pas prêt ou arrêté (échec fermé voulu) | attendre `healthy` ; `runbook.md` §11 |
| `400 Bad Request` (DisallowedHost) | `Host` reçu différent de `PUBLIC_HOST` | `proxy_set_header Host $host;` présent, `server_name` identique à `PUBLIC_HOST` |
| `403` « CSRF verification failed » à la connexion | `X-Forwarded-Proto` non `https`, ou domaine différent de `PUBLIC_HOST` | vérifier l'en-tête dans le vhost hôte et `PUBLIC_HOST` (le frontend est construit avec ; reconstruire si changé) |
| boucle de redirections (`ERR_TOO_MANY_REDIRECTS`) | l'application croit être en HTTP | `X-Forwarded-Proto $scheme` manquant dans le vhost hôte, ou accès direct à `:8080` en HTTP sans cet en-tête (le Nginx de la pile le force à `https`) |
| `502 Bad Gateway` du Nginx hôte | pile arrêtée ou `PORT_HOTE` différent | `onea-dc ps`, `curl -H 'Host: ...' http://127.0.0.1:8080/api/v1/health/ready/` |
| `413 Request Entity Too Large` | plafond d'upload du Nginx hôte trop bas | `client_max_body_size 55m;` dans le vhost |
| `429` pour tout le monde dès quelques échecs | `remote_addr` = passerelle : `X-Forwarded-For` non cru, ou `$proxy_add_x_forwarded_for` employé | section 13 (contrôle de l'adresse réelle) ; `X-Forwarded-For $remote_addr` dans le vhost |
| Let's Encrypt : `Timeout during connect` / `404` sur le défi | DNS pas encore propagé, `AAAA` erroné, pare-feu 80, vhost HTTP absent | `dig`, `curl -I http://audit.exemple.org/.well-known/acme-challenge/x` (404 attendu, pas un délai), section 9 |
| `nginx -t` : `duplicate listen options` | `listen 443 ssl http2` déjà déclaré pour la même adresse dans un autre vhost avec options différentes | harmoniser les options `listen` sur 443, sans modifier le comportement des autres sites |
| un service de l'hôte qui fait suivre des paquets (VPN, routeur) cesse de fonctionner après l'installation de Docker | politique `FORWARD DROP` posée par Docker | comparer `iptables -S FORWARD` avec le diagnostic d'avant ; lire la documentation « Docker and iptables » (chaîne `DOCKER-USER`) avant d'ajouter une règle pour ce service précis ; cas non testé ici |
| `/var/lib/docker` remplit le disque | images/logs/volumes | `docker system df` ; déplacer `data-root` dans `/etc/docker/daemon.json` (ne pas purger les images d'autres propriétaires) |
| courriels non envoyés | `worker-auth` arrêté, SMTP bloqué en sortie, identifiants | `runbook.md` §5 (« Courriels non envoyés ») |

## 20. Désinstallation propre, sans impact sur les autres services

Les étapes touchent **uniquement** ce qui porte le nom `onea` ou `onea-prod`. Lister avant d'effacer,
et faire une dernière sauvegarde si les données comptent. L'effacement des données est **irréversible**.

```
# 0. Dernière sauvegarde, copiée hors du serveur
sudo systemctl start onea-sauvegarde.service

# 1. Retirer le vhost de l'hôte (les autres vhosts ne sont pas touchés)
sudo rm /etc/nginx/sites-enabled/onea-audit.conf /etc/nginx/sites-enabled/onea-audit-http.conf
sudo nginx -t && sudo systemctl reload nginx

# 2. Planifications ONEA
sudo systemctl disable --now onea-sauvegarde.timer onea-verification-sauvegarde.timer 2>/dev/null
sudo rm -f /etc/systemd/system/onea-* /etc/cron.d/onea-*
sudo systemctl daemon-reload

# 3. Arrêter la pile et retirer ses conteneurs et réseaux (les volumes de données sont CONSERVÉS)
sudo onea-dc down --remove-orphans
# 3bis. Seulement pour effacer aussi les données (base, pièces, index, signatures) : irréversible
#       sudo onea-dc down --volumes --remove-orphans

# 4. Images de la pile (par nom, jamais prune -a)
sudo docker image ls | grep -E '^onea-(backend|frontend) '
sudo docker image rm $(sudo docker image ls -q 'onea-backend') $(sudo docker image ls -q 'onea-frontend') 2>/dev/null

# 5. Certificat de ce sous-domaine uniquement
sudo certbot delete --cert-name audit.exemple.org

# 6. Fichiers, après vérification de ce qu'on supprime
sudo ls -la /opt/onea /etc/onea /srv/onea /srv/onea-backups
sudo rm -rf /opt/onea /etc/onea /usr/local/bin/onea-dc /var/www/onea-acme /etc/nginx/sites-available/onea-audit*.conf
# /srv/onea (documents) et /srv/onea-backups : à supprimer seulement si les données ne sont plus utiles
sudo deluser --remove-home onea

# 7. Contrôle : l'hôte est revenu à son état initial
sudo sh /tmp/diagnostic-vps.sh > ~/diagnostic-apres.txt; diff ~/diagnostic-avant.txt ~/diagnostic-apres.txt
sudo docker network ls | grep onea ; sudo docker volume ls | grep onea       # rien attendu après 3bis
```

Docker lui-même n'est **pas** désinstallé : il peut servir à d'autres usages. Si c'est vous qui l'avez
installé pour ONEA seul et que plus rien ne l'utilise (`docker ps -a` vide) :
`sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`,
`sudo rm /etc/apt/sources.list.d/docker.list /etc/apt/keyrings/docker.asc`, puis `sudo rm -rf /var/lib/docker`
(irréversible). Retirer ensuite le DNS (`audit.exemple.org`) chez le gestionnaire de la zone.
