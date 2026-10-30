#!/bin/sh
# Generates the nginx `geo` map used to gate the Keycloak admin console from ADMIN_ALLOW_CIDR
# (comma- or space-separated IPs/CIDRs, e.g. "10.20.0.0/16,192.0.2.7"). Empty = deny everyone
# (default). Runs from /docker-entrypoint.d before the templates are rendered.
set -eu
out=/etc/nginx/conf.d/admin-allow.conf
{
  echo 'geo $onea_admin_ok {'
  echo '    default 0;'
  for cidr in $(echo "${ADMIN_ALLOW_CIDR:-}" | tr ',' ' '); do
    case "$cidr" in
      *[!0-9a-fA-F:./]*) echo "ADMIN_ALLOW_CIDR: invalid entry '$cidr'" >&2; exit 1 ;;
    esac
    echo "    $cidr 1;"
  done
  echo '}'
  # Keycloak admin REST sync: the original TCP peer must be in the web subnet.
  echo 'geo $realip_remote_addr $onea_kc_sync_ok {'
  echo '    default 0;'
  case "${ONEA_SUBNET_WEB:-}" in
    *[!0-9a-fA-F:./]*) echo "ONEA_SUBNET_WEB: invalid value" >&2; exit 1 ;;
    '') ;;
    *) echo "    ${ONEA_SUBNET_WEB} 1;" ;;
  esac
  echo '}'
} > "$out"
