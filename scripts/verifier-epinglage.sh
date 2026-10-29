#!/bin/sh
# Verifie que chaque image de conteneur est epinglee.
#   sh scripts/verifier-epinglage.sh [fichiers...]
# Regles :
#   - toute ligne `FROM`, `COPY --from=<image>` ou `image:` doit porter une version exacte
#     (au moins 3 composantes numeriques, ex. 1.27.5 ; 2 pour postgres, ex. 16.14) ;
#     `latest`, les etiquettes absentes ou partielles (`16`, `1.27-alpine`) sont refusees ;
#   - dans compose.prod.yml et les Dockerfile, l'image doit en plus finir par @sha256:<64 hex>.
# Sans argument : les Dockerfile, les compose et la CI du depot. Code 1 si une ligne echoue.
set -eu

cd "$(dirname "$0")/.."
if [ "$#" -eq 0 ]; then
  set -- docker/backend.Dockerfile docker/frontend.Dockerfile \
    docker/compose.yml docker/compose.dev.yml docker/compose.prod.yml .github/workflows/ci.yml
fi

status=0
for f in "$@"; do
  need_hash=0
  case "$(basename "$f")" in
    compose.prod.yml | *Dockerfile*) need_hash=1 ;;
  esac
  awk -v file="$f" -v need_hash="$need_hash" '
    function fail(msg) { printf "%s:%d: %s\n", file, NR, msg; bad = 1 }
    function check(ref,   img, tag, hash, n, parts, base, count, need, ok, i) {
      gsub(/["\047]/, "", ref)
      if (ref ~ /^\$\{/ || ref ~ /^onea-(backend|frontend):/) return   # images construites ici
      if (ref in stages) return                                        # FROM <stade precedent>
      if (ref == "scratch") return
      hash = ""
      if (index(ref, "@sha256:")) {
        hash = substr(ref, index(ref, "@sha256:") + 8)
        ref = substr(ref, 1, index(ref, "@sha256:") - 1)
      }
      tag = ""
      img = ref
      n = split(ref, parts, "/")
      if (index(parts[n], ":")) {
        tag = substr(parts[n], index(parts[n], ":") + 1)
        img = substr(ref, 1, length(ref) - length(tag) - 1)
      }
      if (tag == "") { fail("etiquette absente (flottante) : " ref); return }
      if (tag == "latest") { fail("etiquette flottante : " img ":" tag); return }
      base = tag; sub(/^v/, "", base); sub(/-.*/, "", base)
      count = split(base, parts, ".")
      need = (img ~ /(^|\/)postgres$/) ? 2 : 3
      ok = (count >= need)
      for (i = 1; i <= count; i++) if (parts[i] !~ /^[0-9]+$/) ok = 0
      if (!ok) fail("version non exacte (" need " composantes numeriques minimum) : " img ":" tag)
      if (need_hash == 1 && hash !~ /^[0-9a-f]+$/ || need_hash == 1 && length(hash) != 64)
        fail("empreinte @sha256:<64 hex> manquante : " img ":" tag)
    }
    /^[[:space:]]*#/ { next }
    tolower($1) == "from" {
      i = 2
      while ($i ~ /^--/) i++
      check($i)
      for (j = i + 1; j < NF; j++) if (tolower($j) == "as") stages[$(j + 1)] = 1
      next
    }
    tolower($1) == "copy" {
      for (i = 2; i <= NF; i++) if ($i ~ /^--from=/) {
        r = substr($i, 8)
        if (!(r in stages) && r !~ /^[0-9]+$/) check(r)
      }
      next
    }
    $1 == "image:" || ($1 == "-" && $2 == "image:") { check($1 == "-" ? $3 : $2) }
    END { exit bad }
  ' "$f" || status=1
done
exit "$status"
