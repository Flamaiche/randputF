# Modèle randput : terminologie et classification des bâtiments

Retour : [docs/README.md](README.md).

Le modèle randput décrit le graphe généré, pas l'interface du jeu. Il donne un vocabulaire stable aux recettes, aux bâtiments et aux technologies. La classification repose sur des rôles, jamais sur des noms figés.

## Ce que ça change pour le joueur

- Les bâtiments sont classés par ce qu'ils savent faire.
- Une même machine peut remplir plusieurs rôles dans le graphe.
- Les technologies forment une progression unique, du départ à la fusée.

## Mots à connaître

- [graphe](glossaire.md) — ensemble des recettes, items et technologies liés entre eux.
- [atelier](glossaire.md) — bâtiment qui transforme des entrées en sorties.
- [extracteur](glossaire.md) — bâtiment qui prélève une ressource du monde.
- [tier](glossaire.md) — rang de progression dans l'arbre technologique.

## Terminologie

| Mot | Sens dans randputF |
|---|---|
| seed | graine qui fixe tous les tirages |
| dump | photographie des prototypes du jeu |
| base normalisée | lecture du dump, enrichie par des tags |
| pool | ensemble fini de candidats pour un tirage |
| step | lot logique de recettes et de déblocages |
| tech | technologie issue d'un step |
| jalon | garantie qu'une catégorie de contenu est disponible |
| rejeu | simulation de la progression sans interface Factorio |

La seed ne contient pas toutes les décisions internes. Elle contient les tirages, les pools retenus et les listes ordonnées que le mod doit appliquer. Le détail des sections sérialisées figure dans [seed.md](seed.md).

### Ce que le modèle ne dit pas

Le modèle ne fixe pas la place exacte des bâtiments dans le monde. Il ne décrit pas les graphismes ni les interfaces utilisateur. Il ne garantit pas qu'une seed soit jouable sans le validateur et le rejeu.

Le contenu vanilla n'est pas remplacé bout à bout. Il est neutralisé en data-stage, puis les prototypes randputF prennent le relais. La chaîne de fusée reste la seule partie exemptée.

### Modèle et rapport de complexité

La complexité mesure la taille et la profondeur du graphe. Elle compte les recettes, les technologies, les prérequis et les chemins de production. Le rapport HTML lit la même seed que le mod, sans la modifier.

Le coût de recherche ne se limite pas au nombre de packs. Il dépend des ressources brutes nécessaires pour obtenir ces packs. La vue de complexité est décrite dans [graphe-interactif.md](graphe-interactif.md).

## Le modèle randput : classification des bâtiments

La classification vient du dump et des tags calculés par le parseur. Elle remplace les anciens types fonctionnels exclusifs. Les rôles sont cumulables.

### Types fonctionnels

| Rôle | Lecture courte |
|---|---|
| recherche | consomme des packs et produit de la recherche |
| atelier | transforme des ingrédients en produit |
| générateur | produit courant ou chaleur |
| distribution | transporte courant ou effets |
| extracteur | prélève une ressource du monde |
| autre | aucun rôle reconnu |

Un échangeur thermique est à la fois atelier et générateur. Le personnage est à la fois atelier et extracteur. Ces cumuls sont voulus et vérifiés par l'audit.

### Slots typés

| Slot | Contenu |
|---|---|
| entrée item | ingrédient solide |
| entrée fluide | ingrédient liquide ou gazeux |
| sortie item | produit solide |
| sortie fluide | produit liquide ou gazeux |
| énergie | source de courant ou de chaleur |

Les recettes générées respectent ces slots. Un bâtiment à recette fixe reçoit une transformation unique qui correspond à ses slots. Les résidus de combustion restent des sorties distinctes.

### Directives : les possibilités par tier

Le plan de jalons associe chaque ressource à un rang minimal de disponibilité. Les ressources tardives peuvent être dégradées au rang zéro dans une seconde passe. Cette passe est conditionnelle et ne modifie pas les seeds pour lesquelles aucun jalon n'est actif.

La configuration est copiée avant cette passe. Aucune seed ne peut hériter de l'état d'une seed précédente dans le même processus. Le détail de cette mécanique figure dans [pipeline.md](pipeline.md) et [DEVIANCES.md](DEVIANCES.md).

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Le vocabulaire est stable d'une seed à l'autre. | Les rôles d'un mod tiers peuvent échapper au modèle. |
| Les tags sont dérivés des capacités du dump. | Les ensembles résiduels subsistent en attendant de meilleurs signaux. |
| Le rapport de complexité lit la seed sans la changer. | La complexité ne prédit pas le temps de jeu réel. |

## Aller plus loin

- [tags.md](tags.md) — à lire quand le détail d'un tag est recherché.
- [vanilladb.md](vanilladb.md) — à lire quand l'origine d'une capacité est cherchée.
- [pipeline.md](pipeline.md) — à lire quand les jalons sont appliqués.
- [solvabilite.md](solvabilite.md) — à lire quand la jouabilité est vérifiée.
- [graphe-interactif.md](graphe-interactif.md) — à lire quand la complexité est consultée.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [glossaire.md](glossaire.md) — définitions courtes.
- [modules.md](modules.md) — modules qui appliquent le modèle.
- [runtime.md](runtime.md) — passage du modèle au jeu.
