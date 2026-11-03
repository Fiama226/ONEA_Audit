# Nettoyage des worktrees, branches et bases de test

Inventaire **en lecture seule** établi le 2026-11-03 ; rien n'a été supprimé. Les commandes sont à lancer par
l'utilisateur, depuis le dépôt principal (`onea-audit/`), **quand plus aucun agent ne travaille** : des agents
actifs possèdent des worktrees `agent-*` (celui-ci en fait partie, il est marqué `locked`). Ne jamais toucher
à la base `onea` (site de développement).

## 1. Worktrees (`git worktree list` : 172 entrées)

| Famille | Nombre | Chemin | Remarque |
|---|---|---|---|
| Checkout principal | 1 | `onea-audit/` (branche `preview`, 160bbd0) | à conserver |
| Worktrees courts de tâches | 79 | `C:/tmp-*` (`tmp-dev`, `tmp-l6`, `tmp-l7t1`…, `tmp-qa-*`, `tmp-roleA`…) | branches toutes fusionnées dans `develop`, sauf mention contraire ci-dessous |
| Worktrees d'agents | 83 | `onea-audit/.claude/worktrees/agent-*` | 82 branches `worktree-agent-*` fusionnées ; 1 non fusionnée (voir §2) ; `agent-a6f3ac7416082cd4f` est actif (`locked`) |
| Worktrees de plans | 8 | `onea-audit/.claude/worktrees/plan-*` | branches `docs/plan-*`, **non fusionnées dans `develop`** : à conserver (les plans de lots n'existent que là) |
| Pool Kilo | 1 | `C:/Users/KABORE/.local/share/kilo/worktree-pool/.../angry-salamander` (HEAD détaché, 478153a) | résidu de l'outil Kilo, à vérifier avant suppression |

À conserver : `preview`, `develop` (`C:/tmp-dev`, 88da06b), les 8 worktrees de plans, et tout worktree dont
le travail n'est pas fusionné. `C:/tmp-dev` est le worktree de `develop` : le supprimer seulement si
`develop` est aussi extraite ailleurs.

## 2. Branche `worktree-agent-*` orpheline

`worktree-agent-a6bb9c469ea3220f4` (cd9b928) : **seule branche d'agent non fusionnée dans `develop`**. Son
commit est `wip(constats): partial lot 6 T8 constats API (unfinished, untested)`. L'ancien état du projet indique
que le lot 6 T8 a été terminé ensuite dans `develop` : la branche est donc probablement obsolète, mais la
supersession n'a pas été vérifiée ligne à ligne. Prudence : l'archiver sous forme de tag avant de la supprimer
(commande en §4).

Les 82 autres branches `worktree-agent-*` sont fusionnées dans `develop` (`git branch --merged develop`). Deux
d'entre elles, `worktree-agent-aa80d1750cfac40dc` et `worktree-agent-adb4265e8d3a4812c`, portent les branches
`feat/finish-lot8-ui` et `feat/lot7-pades` (fusionnées) dans leur worktree : supprimer le worktree d'abord.

## 3. Bases PostgreSQL de test (conteneur `onea-db-1`)

Relevé : `docker exec onea-db-1 psql -U onea -d postgres -c '\l'`. Bases à ne **pas** supprimer : `onea`,
`postgres`, `template0`, `template1`.

Bases de test à supprimer (24) :
`onea_d5`, `onea_fullsuite2`, `onea_perf9`, `onea_qaedg`, `onea_t5`, `onea_test9f`,
`test_onea_a4`, `test_onea_a6`, `test_onea_flaky`, `test_onea_h2`, `test_onea_l63`, `test_onea_l9t26_test`,
`test_onea_roleA`, `test_onea_suivifix`, `test_onea_t3`, `test_onea_t5`, `test_onea_test13`, `test_onea_test7a`,
`test_onea_test7b`, `test_onea_test7e`, `test_onea_test8h`, `test_onea_test8i`, `test_onea_test8j`,
`test_onea_test9`. Une base de test en cours d'usage par une suite lancée refusera la suppression (`DROP
DATABASE` échoue si des connexions existent) : la laisser.

## 4. Commandes sûres (à lancer par l'utilisateur)

Toutes les commandes sont « sans force » : Git et PostgreSQL refusent si l'élément est utilisé ou modifié.

```sh
cd "C:/Users/KABORE/Desktop/ONEA projet audit interne/OneDrive_1_27-10-2026/onea-audit"

# 0. Archiver la branche orpheline avant toute suppression
git tag archive/worktree-agent-a6bb9c469ea3220f4 worktree-agent-a6bb9c469ea3220f4

# 1. Aperçu (rien n'est supprimé) : entrées orphelines dont le dossier est déjà absent
git worktree prune --dry-run -v

# 2. Retirer un worktree : refuse s'il contient des modifications non commitées (ne pas ajouter --force)
git worktree remove "C:/tmp-l7t1"
#    Répéter pour chaque dossier de la liste, ou en boucle (s'arrête à la première erreur) :
for w in $(git worktree list | awk '{print $1}' | grep -E '^C:/tmp-' | grep -v -E 'C:/tmp-dev$'); do
  git worktree remove "$w" || echo "CONSERVE : $w"
done
#    Worktrees d'agents (hors l'agent actif, déjà verrouillé et refusé automatiquement) :
for w in $(git worktree list | awk '{print $1}' | grep '/.claude/worktrees/agent-'); do
  git worktree remove "$w" || echo "CONSERVE : $w"
done
git worktree prune

# 3. Supprimer les branches fusionnées (-d refuse une branche non fusionnée)
git branch --merged develop | grep -E '^\s*(worktree-agent-|feat/lot[0-9]-t[0-9]+|feat/lot9-)' | xargs -r git branch -d
#    La branche orpheline, une fois archivée au tag ci-dessus :
git branch -D worktree-agent-a6bb9c469ea3220f4

# 4. Bases de test (jamais la base « onea »)
for db in onea_d5 onea_fullsuite2 onea_perf9 onea_qaedg onea_t5 onea_test9f \
          test_onea_a4 test_onea_a6 test_onea_flaky test_onea_h2 test_onea_l63 test_onea_l9t26_test \
          test_onea_roleA test_onea_suivifix test_onea_t3 test_onea_t5 test_onea_test13 test_onea_test7a \
          test_onea_test7b test_onea_test7e test_onea_test8h test_onea_test8i test_onea_test8j test_onea_test9; do
  docker exec onea-db-1 psql -U onea -d postgres -c "DROP DATABASE IF EXISTS \"$db\";"
done
docker exec onea-db-1 psql -U onea -d postgres -c '\l'     # contrôle final : onea, postgres, templates

# 5. Résidu Kilo (après vérification qu'aucun travail n'y est en cours)
git worktree remove "C:/Users/KABORE/.local/share/kilo/worktree-pool/onea-audit-d38c0ac98c93/angry-salamander"
```

Réserves : la boucle de l'étape 2 supprime aussi les branches associées **seulement** à l'étape 3 ; les
dossiers `C:/tmp-*` hors dépôt peuvent contenir des fichiers ignorés par Git (`node_modules`, `.venv`) : `git
worktree remove` les supprime avec le worktree, ce qui est attendu. Les worktrees `plan-*` ne figurent dans aucune boucle.
Sous Windows/OneDrive, un dossier verrouillé par un éditeur ou l'explorateur fera échouer la suppression : fermer
le programme et relancer.
