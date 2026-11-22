# La chaleur

Retour : [docs/README.md](README.md).

Cette page réunit les règles de la chaleur. Elle sert de point unique pour la triade source, transport et consommateur. L'électricité est décrite dans [energie.md](energie.md#lélectricité).

## Ce que ça change pour le joueur

- Un consommateur de chaleur tente d'ajouter les éléments qui l'alimentent ; la réussite n'est pas garantie.
- Le réacteur n'exige pas de chaîne d'uranium dédiée.
- Sans consommateur, la chaleur n'ajoute aucune contrainte.

## Mots à connaître

- [prototype](glossaire.md) — définition d'un bâtiment dans le dump.
- [slot](glossaire.md) — entrée ou sortie d'un bâtiment ou d'une recette.
- [déblocage sur le tas](glossaire.md) — création d'un prérequis au moment du besoin.
- [jalon](glossaire.md) — étape qui garantit une catégorie de contenu.

## Règles de génération

### La chaleur

- Les rôles sont détectés dans le dump avec `is_heat_source`, `is_heat_transport` et `is_heat_sink`.
- La source produit la chaleur, le transport l'achèmine et le consommateur l'utilise pour transformer un fluide.
- `_ensure_heat_prereq` tente d'ajouter la source puis le transport quand un consommateur reçoit sa recette.
- La phase pose une marque avant la tentative et n'émet qu'une seule fois par seed.
- Une erreur `ValueError` est interceptée : la triade reste une tentative déterministe, et non une garantie absolue.
- Le réacteur utilise des catégories de combustible unifiées. Aucune chaîne d'uranium dédiée n'est requise.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Une tentative de triade au premier consommateur. | La réussite de chaque élément de la triade. |
| Une seule émission de la phase par seed. | L'ajout de la triade quand le pool est vide ou bloqué. |

## Aller plus loin

- [energie.md](energie.md#lélectricité) — à lire quand le sujet est le courant plutôt que la chaleur.
- [tags.md](tags.md) — à lire quand il faut retrouver les tags de rôle.
- [recettes.md](recettes.md#la-phase-récursive) — à lire pour situer la phase dans la chronologie.
- [solvabilite.md](solvabilite.md) — à lire pour comparer avec les invariants vérifiés.

## Lectures associées

- **Parent** : [energie.md](energie.md) — l'électricité, premier réseau spécial.
- [tags.md](tags.md) — tags de rôle de la triade.
- [vanilladb.md](vanilladb.md) — tags énergétiques du dump.
- [amorcage.md](amorcage.md) — ordre des prérequis.
