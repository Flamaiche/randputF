# Description des branches (randputF)

> **Document de travail : plans et idées non livrés.** Ce fichier décrit
> l'usage des branches conservées dans le dépôt ; il n'est pas un engagement de
> livraison. L'état courant de la documentation est dans
> [`docs/README.md`](../docs/README.md) ; les notes de release publiées sont
> dans [`notes/README.md`](../notes/README.md).

Ce fichier reflète l'état réel des branches locales conservées, pas une ancienne feuille de route.

## Branches conservées

| Branche | Rôle |
|---|---|
| `master` | Historique publié (`v0.0.0`, `v0.0.1`) et releases taguées. |
| `dev` | Ligne de développement courante, base des travaux intégrés. |
| `docs-refonte-archive` | Branche active : refonte documentaire, sorties HTML et note `v0.0.2`. |

Les anciennes branches intermédiaires ont été supprimées localement. Leur travail est intégré dans `docs-refonte-archive` ou conservé dans les références distantes `origin/...`.

## Convention

Une branche intermédiaire est supprimée quand son travail est intégré dans la branche active ou archivé dans une référence distante. Le présent fichier décrit l'état réel des branches locales conservées.
