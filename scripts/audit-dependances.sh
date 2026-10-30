#!/usr/bin/env bash
# Audit des dependances (Lot 9 / T14) : licences, SBOM CycloneDX, vulnerabilites connues.
# Outils open source uniquement : uv, pip-audit, pip-licenses, cyclonedx-bom, npm audit,
# license-checker-rseidelsohn, @cyclonedx/cyclonedx-npm (via uvx/npx, aucune installation globale).
# Usage : scripts/audit-dependances.sh [repertoire-de-sortie]   (defaut : build/audit)
# Pre-requis : uv, node/npm ; frontend/node_modules installe (npm ci). Le reseau est requis pour les
# bases de vulnerabilites (PyPI/OSV, registre npm) ; les controles de licence fonctionnent hors ligne.
# Code de sortie : 1 si licence interdite/inconnue ou vulnerabilite connue, 0 sinon.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/build/audit}"
mkdir -p "$OUT"
FAIL=0
VENV="$(mktemp -d)/venv"

# Licences refusees (CLAUDE.md regle 2 : MIT, BSD, Apache-2.0, PostgreSQL, LGPL, AGPL, MPL-2.0, ISC,
# OFL-1.1, 0BSD, BlueOak, CC0, CC-BY-4.0, Python-2.0 sont autorisees). On signale GPL seule (hors L/A),
# SSPL, BUSL, licences non commerciales, proprietaires et inconnues.
DENY='(^|[^LA])GPL|SSPL|BUSL|Business Source|NonCommercial|CC-BY-NC|Proprietary|Commercial|UNKNOWN|UNLICENSED'

echo "== Backend : environnement verrouille (uv.lock) =="
(cd "$ROOT/backend" && UV_PROJECT_ENVIRONMENT="$VENV" uv sync --frozen --no-dev >/dev/null) || exit 2
PY="$VENV/Scripts/python.exe"
[ -f "$PY" ] || PY="$VENV/bin/python"

echo "== Backend : licences =="
uvx pip-licenses --python "$PY" --from=mixed --format=csv > "$OUT/licences-backend.csv"
if grep -Ei "$DENY" "$OUT/licences-backend.csv"; then echo "LICENCE A REVOIR (backend)"; FAIL=1; fi

echo "== Backend : SBOM CycloneDX =="
uvx --from cyclonedx-bom cyclonedx-py environment "$PY" --of JSON -o "$OUT/sbom-backend.cdx.json"

echo "== Backend : vulnerabilites (pip-audit) =="
(cd "$ROOT/backend" && uv export --frozen --no-dev --no-hashes --no-emit-project -o "$OUT/requirements-backend.txt" >/dev/null)
uvx pip-audit -r "$OUT/requirements-backend.txt" --no-deps --disable-pip 2>&1 | tee "$OUT/vulns-backend.txt" || FAIL=1

cd "$ROOT/frontend" || exit 2
[ -d node_modules ] || { echo "frontend/node_modules absent : lancer 'npm ci' d'abord" >&2; exit 2; }

echo "== Frontend : licences =="
npx --yes license-checker-rseidelsohn --csv --excludePrivatePackages > "$OUT/licences-frontend.csv"
if grep -Ei "$DENY" "$OUT/licences-frontend.csv"; then echo "LICENCE A REVOIR (frontend)"; FAIL=1; fi

echo "== Frontend : SBOM CycloneDX =="
npx --yes @cyclonedx/cyclonedx-npm --package-lock-only --output-format JSON --output-file "$OUT/sbom-frontend.cdx.json"

echo "== Frontend : vulnerabilites (npm audit) =="
npm audit | tee "$OUT/vulns-frontend.txt" || FAIL=1

echo "Rapports ecrits dans $OUT"
exit "$FAIL"
