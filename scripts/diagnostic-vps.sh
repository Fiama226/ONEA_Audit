#!/bin/sh
# Diagnostic d'un VPS AVANT d'y installer la plateforme ONEA. LECTURE SEULE : aucune commande ne
# modifie le serveur (ni paquet, ni fichier, ni pare-feu, ni service). Les rubriques qui exigent
# root (processus des autres comptes, règles de pare-feu) sont signalées si on n'est pas root.
#
#   sh scripts/diagnostic-vps.sh            (idéalement : sudo sh scripts/diagnostic-vps.sh)
#   sh scripts/diagnostic-vps.sh > diagnostic.txt
#
# docs/deploiement-vps-existant.md, section 1.
set -u

titre() { printf '\n===== %s =====\n' "$1"; }
existe() { command -v "$1" >/dev/null 2>&1; }
# exec_si <commande> [arguments] : exécute si la commande existe, sinon l'indique.
exec_si() {
  if existe "$1"; then "$@" 2>&1; else echo "($1 absent)"; fi
}

echo "Diagnostic ONEA - $(date -u '+%Y-%m-%d %H:%M:%S UTC') - hôte $(hostname 2>/dev/null)"
if [ "$(id -u)" -eq 0 ]; then
  echo "Exécuté en root : informations complètes."
else
  echo "ATTENTION : non root. Processus des autres comptes, pare-feu et configuration Nginx peuvent être incomplets."
fi

titre "Système"
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  ( . /etc/os-release; echo "Distribution : ${PRETTY_NAME:-inconnue}"; echo "ID=${ID:-?} VERSION_ID=${VERSION_ID:-?} CODENAME=${VERSION_CODENAME:-?}" )
else
  echo "/etc/os-release illisible"
fi
echo "Noyau        : $(uname -r) ($(uname -m))"
echo "Uptime       : $(uptime 2>/dev/null)"
if existe systemd-detect-virt; then echo "Virtualisation : $(systemd-detect-virt 2>/dev/null)"; fi
echo "Init         : $(ps -p 1 -o comm= 2>/dev/null)"
echo "Fuseau       : $(date '+%Z %z')"

titre "Mémoire et swap (la pile ONEA demande 6 Go de RAM au minimum recommandé, ClamAV seul 3 Go)"
exec_si free -h
if [ -r /proc/meminfo ]; then
  mem_ko=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
  [ -n "$mem_ko" ] && echo "MemAvailable : $((mem_ko / 1024)) Mo"
fi

titre "CPU"
if existe nproc; then echo "Coeurs : $(nproc)"; fi
if [ -r /proc/cpuinfo ]; then grep -m1 'model name' /proc/cpuinfo; fi
if [ -r /proc/loadavg ]; then echo "Charge (1/5/15 min) : $(cut -d' ' -f1-3 /proc/loadavg)"; fi

titre "Disque (20 Go libres minimum ; documents et sauvegardes en plus)"
exec_si df -hT -x tmpfs -x devtmpfs -x squashfs -x overlay
echo "--- inodes"
exec_si df -i / /var /srv /opt
echo "--- /var/lib/docker (placé sur quel système de fichiers ?)"
if [ -d /var/lib/docker ]; then df -h /var/lib/docker 2>&1; else df -h /var/lib 2>&1; echo "(/var/lib/docker n'existe pas encore : Docker écrira dans /var/lib)"; fi

titre "Ports TCP en écoute (ss -tlnp)"
if existe ss; then
  ss -tlnp 2>&1
elif existe netstat; then
  netstat -tlnp 2>&1
else
  echo "(ni ss ni netstat)"
fi
echo "--- ports UDP en écoute"
if existe ss; then ss -ulnp 2>&1; fi
echo "--- ports visés par ONEA :"
for p in 80 443 8080 5432 6379 7700 3000 3310; do
  if existe ss && ss -tln 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${p}\$"; then
    echo "  $p : DEJA UTILISE"
  else
    echo "  $p : libre"
  fi
done
echo "(Seul PORT_HOTE, 8080 par défaut, est publié par la pile, sur 127.0.0.1. Si 8080 est utilisé, choisir un autre PORT_HOTE.)"

titre "Serveurs web : Nginx, Apache, Caddy, HAProxy, Traefik"
for svc in nginx apache2 httpd caddy haproxy traefik; do
  if existe "$svc"; then
    printf '%s : installé (%s)\n' "$svc" "$(command -v "$svc")"
  fi
  if existe systemctl; then
    etat=$(systemctl is-active "$svc" 2>/dev/null)
    [ "$etat" = "active" ] && echo "  service $svc : ACTIF"
  fi
done
echo "--- processus à l'écoute sur 80/443"
if existe ss; then ss -tlnp 2>/dev/null | awk 'NR==1 || $4 ~ /[:.](80|443)$/'; fi

echo "--- Nginx"
if existe nginx; then
  nginx -v 2>&1
  if [ "$(id -u)" -eq 0 ]; then
    # nginx -T teste la configuration et l'affiche : lecture seule (aucun rechargement).
    echo "Directives listen et server_name (nginx -T) :"
    nginx -T 2>/dev/null | grep -E '^\s*(listen|server_name)\s|configuration file /' | sed 's/^\s*/  /'
  else
    echo "(relancer en root pour lister listen / server_name)"
  fi
  for d in /etc/nginx/sites-enabled /etc/nginx/conf.d; do
    if [ -d "$d" ]; then echo "Fichiers dans $d :"; ls -1 "$d" 2>&1 | sed 's/^/  /'; fi
  done
  if grep -rqs 'default_server' /etc/nginx 2>/dev/null; then
    echo "Un default_server existe déjà : le vhost ONEA doit porter son server_name exact, sans default_server."
  fi
else
  echo "(nginx absent)"
fi

echo "--- Apache"
for a in apache2ctl apachectl httpd; do
  if existe "$a"; then
    "$a" -v 2>&1 | head -2
    [ "$(id -u)" -eq 0 ] && "$a" -S 2>&1 | head -20
    break
  fi
done
for f in /etc/apache2/ports.conf; do [ -r "$f" ] && { echo "Contenu de $f :"; grep -v '^\s*#' "$f" | sed '/^\s*$/d;s/^/  /'; }; done

echo "--- Caddy"
if existe caddy; then
  caddy version 2>&1
  [ -r /etc/caddy/Caddyfile ] && { echo "/etc/caddy/Caddyfile (lignes non vides, 40 premières) :"; sed '/^\s*$/d' /etc/caddy/Caddyfile | head -40 | sed 's/^/  /'; }
else
  echo "(caddy absent)"
fi

titre "Docker"
if existe docker; then
  docker --version 2>&1
  docker compose version 2>&1 || echo "(plugin compose absent)"
  if docker info >/dev/null 2>&1; then
    echo "Démon joignable."
    docker info --format 'Racine : {{.DockerRootDir}}  Pilote de stockage : {{.Driver}}  Conteneurs : {{.Containers}}' 2>&1
    echo "--- conteneurs en cours (ne pas y toucher)"
    docker ps --format '  {{.Names}}  {{.Image}}  {{.Ports}}' 2>&1
    echo "--- réseaux Docker et sous-réseaux (ONEA veut 172.30.10.0/28 et 172.30.11.0/28)"
    docker network ls --format '{{.Name}}' 2>/dev/null | while read -r n; do
      printf '  %s : ' "$n"
      docker network inspect "$n" --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null
    done
  else
    echo "Démon non joignable pour cet utilisateur (service arrêté, ou droits insuffisants : relancer en root)."
  fi
else
  echo "Docker n'est pas installé (section 3 de la procédure)."
fi
echo "--- paquets Docker conflictuels (distribution)"
if existe dpkg; then
  dpkg -l 2>/dev/null | awk '/^ii/ && $2 ~ /^(docker\.io|docker-compose|docker-doc|podman-docker|containerd|runc)$/ {print "  " $2 " " $3}'
fi

titre "Réseau : sous-réseaux déjà utilisés par l'hôte (risque de collision avec 172.30.10.0/28 et 172.30.11.0/28)"
if existe ip; then
  ip -4 -brief addr 2>&1
  echo "--- routes"
  ip -4 route 2>&1
else
  echo "(commande ip absente)"
fi

titre "Pare-feu"
if existe ufw; then
  echo "ufw : $(ufw status 2>&1 | head -1)"
  [ "$(id -u)" -eq 0 ] && ufw status verbose 2>&1 | head -30
else
  echo "(ufw absent)"
fi
if existe firewall-cmd; then echo "firewalld : $(firewall-cmd --state 2>&1)"; fi
if existe nft; then
  if [ "$(id -u)" -eq 0 ]; then
    echo "nftables : $(nft list tables 2>&1 | tr '\n' ';')"
  else
    echo "nftables : présent (root requis pour lister)"
  fi
fi
if existe iptables; then
  if [ "$(id -u)" -eq 0 ]; then
    iptables -V 2>&1
    echo "Politique FORWARD actuelle : $(iptables -S FORWARD 2>/dev/null | head -1)"
  else
    echo "iptables : présent (root requis pour lister)"
  fi
else
  echo "(iptables absent : Docker en a besoin, paquet 'iptables')"
fi
if existe systemctl; then
  for s in ufw nftables firewalld fail2ban crowdsec; do
    e=$(systemctl is-active "$s" 2>/dev/null)
    [ "$e" = "active" ] && echo "service $s : ACTIF"
  done
fi
if [ -r /proc/sys/net/ipv4/ip_forward ]; then echo "net.ipv4.ip_forward = $(cat /proc/sys/net/ipv4/ip_forward) (Docker le passe à 1)"; fi

titre "TLS : certbot et certificats existants"
exec_si certbot --version
[ -d /etc/letsencrypt/live ] && { echo "Certificats Let's Encrypt présents :"; ls -1 /etc/letsencrypt/live 2>&1 | sed 's/^/  /'; }

titre "Utilisateurs"
echo "Comptes avec shell de connexion :"
awk -F: '$7 !~ /(nologin|false|sync|shutdown|halt)$/ && $7 != "" {print "  " $1 " (uid " $3 ") " $7}' /etc/passwd
if getent passwd onea >/dev/null 2>&1; then echo "L'utilisateur 'onea' EXISTE déjà : $(getent passwd onea)"; else echo "L'utilisateur 'onea' n'existe pas (à créer : section 4)."; fi
if getent passwd 10001 >/dev/null 2>&1; then echo "ATTENTION : l'UID 10001 est utilisé par $(getent passwd 10001 | cut -d: -f1) (les conteneurs ONEA écrivent en 10001:10001)."; fi
echo "Membres du groupe sudo / wheel / docker :"
for g in sudo wheel docker; do
  l=$(getent group "$g" 2>/dev/null | cut -d: -f4)
  [ -n "$l" ] && echo "  $g : $l"
done
echo "Connexions actuelles :"; exec_si who

titre "SSH (lecture de la configuration, ne pas se verrouiller dehors)"
if [ -r /etc/ssh/sshd_config ]; then
  grep -E '^\s*(Port|PermitRootLogin|PasswordAuthentication|PubkeyAuthentication)\s' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | sed 's/^/  /'
fi

titre "Services en cours (pour repérer ce qu'il ne faut pas toucher)"
if existe systemctl; then
  systemctl list-units --type=service --state=running --no-legend --no-pager 2>&1 | awk '{print "  " $1}' | head -60
fi

titre "DNS"
echo "Vérifier depuis un poste : dig +short A <sous-domaine> doit afficher l'IP publique de ce VPS (ip -4 -brief addr, ci-dessus)."

echo
echo "Fin du diagnostic. Rien n'a été modifié."
