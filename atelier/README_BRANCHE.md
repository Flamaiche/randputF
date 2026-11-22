# Description des branches (randputF)

> **Document de travail : plans et idées non livrés.** Ce fichier décrit
> l'usage des branches conservées dans le dépôt ; il n'est pas un engagement de
> livraison. L'état courant de la documentation est dans
> [`docs/README.md`](../docs/README.md) ; les notes de release publiées sont
> dans [`notes/README.md`](../notes/README.md).

Ce fichier est propre à chaque branche : il doit refléter l'état réel du
travail, pas une ancienne feuille de route.

## Branche actuelle : `docs-refonte-archive`

**Objectif : refondre la documentation à partir de l'archive des branches sans
rétrograder le code de HEAD.**

La branche part de `testeur-dump-modpack-tags` (`4c9d57e`). Elle modifie aussi
la CLI (`tool/__main__.py`, `--no-html`) et la CI
(`.github/workflows/ci.yml`, témoin seed 5). Les textes visibles de `mod/*.lua`,
de `exporter/control.lua` et de `config/defaults.yaml` sont alignés, sans
changement de comportement. Le reste porte sur les documents dont l'archive
montrait des faits périmés.

Deux règles s'appliquent ici :

- les chiffres et les numéros de ligne sont vérifiés sur le code de HEAD ;
- l'ancien garde-fou qui refusait un dump produit sous randputF est abandonné :
  le dump moddé est canonisé à la lecture, pas rejeté à l'écriture.

## Familles de branches

| Famille | Branches | Rôle |
|---|---|---|
| Intégration | `master`, `dev` | Historique publié (`v0.0.0`, `v0.0.1`) et ligne de développement courante. |
| Documentation | `docs`, `docs-correctif-documentation`, `docs-rewrite-improve`, `docs-refonte-archive`, `test/ancres-index-docs` | Relecture, correction des références, refonte ciblée et contrôle des ancres. |
| Export / test | `testeur-dump-modpack-tags`, `refonte-exporter-joueur`, `feat/testeur-unifie` | Canonisation des dumps, schéma 2, outil de test unifié. |
| Analyse / difficulté | `feature/craft-moyens`, `player-simulation`, `feat/rejoueur-garde-generation` | Rapports de complexité, simulation joueur, garde-fou du rejoueur. |
| Monde / cartographie | `feat/lake-tiles-mod-data`, `test/tags-vanilla-medium` | Mapping canonique des lacs, mediums vanilla et tags. |

Branches distantes présentes dans l'archive : `origin/dev`, `origin/docs`,
`origin/feature/craft-moyens`, `origin/master`, `origin/player-simulation`,
`origin/refonte-exporter-joueur`.

## Convention

Une branche ne doit pas annoncer une tâche déjà intégrée dans HEAD. Quand une
fonctionnalité passe dans la ligne principale, sa branche devient historique :
le document doit le dire explicitement plutôt que de laisser une section
« À faire » devenue fausse.

Le fichier `README_BRANCHE.md` est un état des lieux, pas un engagement de
fusion. Aucune branche n'est nettoyée, fusionnée ou poussée sans décision
explicite.
