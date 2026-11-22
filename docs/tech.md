# L'arbre technologique et la fin de partie

Retour : [docs/README.md](README.md).

Cette page explique comment les étapes de génération deviennent des recherches. L'arbre forme une chaîne linéaire, avec une tech finale pour la fusée. Le coût des recherches utilise les packs de science créés plus tôt.

## Ce que ça change pour le joueur

- Chaque recherche dépend de la précédente.
- Une recherche peut débloquer plusieurs objets, sauf les cas isolés.
- La victoire passe toujours par la chaîne de la fusée.

## Mots à connaître

- [science pack](glossaire.md) — objet consommé par un laboratoire.
- [lab](glossaire.md) — bâtiment vanilla de recherche.
- [jalon](glossaire.md) — étape qui garantit une catégorie de contenu.
- [déblocage sur le tas](glossaire.md) — création d'un prérequis au moment du besoin.

## Règles de génération

### L'arbre technologique

- Les macro-techs du départ, de l'électricité, de la récursion, des relais et de la fin de partie sont parcourues dans leur ordre d'apparition.
- Chaque tech a la précédente comme prérequis : la chaîne ne forme pas de branche.
- Une recette est débloquée par la première tech qui la revendique. Les doublons sont écartés au montage.

### Du step à la technologie

- Une tech groupable peut débloquer jusqu'à cinq objets avec les chances configurées.
- Le premier tirage raté arrête le groupe.
- Restent isolés le départ gratuit, les prologues, l'apparition d'un pack, les objets dépendants, la tech finale, les pylônes et les armes de poing.

### Coût des recherches

- Le premier pack est craftable et débloqué gratuitement au départ.
- Un pack n'est jamais fabriqué directement à partir d'une ressource brute.
- Chaque pack suivant possède sa recette avant la tech qui le consomme.
- Le coût affiche une unité par pack, jusqu'à quatre packs distincts. Le nombre de cycles augmente avec la profondeur.
- Les prologues n'ont pas de coût en packs. Leur nombre de crafts est calculé dans `relay_phase.py` avec `round(2 ** (n + 1/4))`. L'exposant est calé sur la première science, à l'indice 1, puis réutilisé tel quel.

### Fin de partie

- `ensure_rocket_chain`, dans `endgame_phase.py`, garantit une recette aux objets de `db.rocket_chain_items()` réunis à ceux du silo repérés par tag.
- Le silo reçoit aussi sa recette si la récursion ne l'a pas déjà fait.
- Ces recettes sont rattachées à `randputf-endgame-rocket`, un nœud dédié qui paie son coût avec les packs les plus avancés.
- Les objets de la chaîne fusée sont écartés du balayage de contenu et des patches.

### Écart connu

Les exclusions de patches sont définies dans `map_patches.py` : packs de science, objets de recherche et objets de la chaîne fusée avec le silo. La spécification historique demande de n'exclure que les packs de science.
 Les autres exclusions restent actives et ne sont pas une correction appliquée.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Une chaîne linéaire de recherches jusqu'à la victoire. | Le nombre de recherches et de recettes par seed. |
| Une recette pour les objets de la chaîne fusée et du silo. | L'absence d'exclusion des objets de recherche dans les patches. |

## Aller plus loin

- [aiguillage.md](aiguillage.md#groupement-en-une-technologie) — à lire quand il faut savoir pourquoi deux objets sont groupés.
- [recettes.md](recettes.md#relais-des-ressources-non-infinies) — à lire pour le déclenchement des prologues.
- [solvabilite.md](solvabilite.md) — à lire quand il faut vérifier l'atteignabilité de la victoire.
- [witness.md](witness.md) — à lire quand il faut comparer deux générations de la même seed.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [aiguillage.md](aiguillage.md) — rattachement des nœuds aux technologies.
- [recettes.md](recettes.md) — recettes de la chaîne fusée.
- [solvabilite.md](solvabilite.md) — garantie d'atteignabilité de la victoire.
- [witness.md](witness.md) — reproductibilité de l'arbre généré.
