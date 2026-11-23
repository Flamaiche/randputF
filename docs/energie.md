# L'électricité et la chaleur

Retour : [docs/README.md](README.md).

Cette page décrit le réseau électrique. La chaleur possède sa propre page, liée ici pour garder le chemin historique. Les deux réseaux ont des règles de déblocage proches, mais des objets distincts.

## Ce que ça change pour le joueur

- Le premier générateur et le premier pylône sont fabriquables sans courant.
- Les machines à fluide acceptent le fluide choisi par la seed.
- Les générateurs restent les seuls bâtiments sans filtre de fluide imposé.

## Mots à connaître

- [prototype](glossaire.md) — définition d'un objet du jeu dans le dump.
- [data-stage](glossaire.md) — chargement des données avant le début de la partie.
- [runtime](glossaire.md) — partie du mod qui s'exécute pendant la partie.
- [compagnon](glossaire.md) — objet lié à un autre pour rester utilisable.

## Règles de génération

### L'électricité

- La phase n'agit que si un bâtiment déjà débloqué demande du courant.
- Un générateur fonctionnel est choisi, puis un pylône est débloqué.
- Un accumulateur n'est jamais choisi comme générateur : c'est un stockage avec une entrée et une sortie.
- Le premier générateur et le pylône d'amorçage utilisent des ingrédients fabriquables sans électricité.
- Un générateur à fluide dépend d'un lac pompable sans courant. Quand aucun générateur n'est fonctionnel, la génération peut ajouter une ressource puis réessayer.
- Le combustible est tiré selon le type du générateur.

### Fluides et data-stage

- Au chargement des données, les filtres génériques des entrées et sorties de fluide sont retirés.
- Les assignations de la seed sont ensuite réappliquées depuis `building_fluid_assignments`.
- Seuls les générateurs restent sans filtre. Les autres bâtiments reçoivent leur fluide d'entrée et, quand le prototype le prévoit, leur fluide de sortie.
- Tous les fluides partagent une valeur de combustible générique. La température ne distingue pas deux fluides dans le modèle randput.

### La chaleur

- La triade thermique est décrite dans [chaleur.md](chaleur.md#la-chaleur).

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Un générateur et un pylône quand un besoin électrique apparaît. | Le type du générateur tiré. |
| Un filtre remis sur les bâtiments non générateurs. | Un fluide imposé sur les générateurs. |

## Aller plus loin

- [chaleur.md](chaleur.md#la-chaleur) — à lire quand le sujet concerne la source, le transport ou le consommateur thermique.
- [recettes.md](recettes.md#cadence-garantie-des-pylônes) — à lire pour la cadence des pylônes pendant la récursion.
- [ressources.md](ressources.md) — à lire quand aucun générateur n'est fonctionnel et qu'une ressource doit être ajoutée.
- [solvabilite.md](solvabilite.md) — à lire pour vérifier l'amorçage sans courant.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [ressources.md](ressources.md) — lacs, patchs et ajout de ressource.
- [chaleur.md](chaleur.md) — source unique de la triade thermique.
- [recettes.md](recettes.md) — pylônes et déblocage sur le tas.
- [solvabilite.md](solvabilite.md) — amorçage pré-électrique et invariants.
