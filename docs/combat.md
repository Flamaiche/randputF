# Combat, armement et transports

Retour : [docs/README.md](README.md).

Cette page décrit le contenu de combat tiré par la seed. Le comportement des ennemis et la pollution restent ceux du jeu de base. Les armes, les munitions et l'armement des véhicules changent d'une seed à l'autre.

## Ce que ça change pour le joueur

- Une arme de poing reçoit une munition compatible quand aucune n'est disponible.
- Les véhicules armés reçoivent des armes tirées dans une réserve configurée.
- La portée des armes montées dépend de la taille du véhicule.

## Mots à connaître

- [pool](glossaire.md) — réserve d'objets parmi lesquels la seed tire.
- [prototype](glossaire.md) — définition d'un bâtiment ou d'une arme dans le dump.
- [déblocage sur le tas](glossaire.md) — création d'un prérequis au moment du besoin.
- [slot](glossaire.md) — entrée ou sortie d'un bâtiment ou d'une recette.

## Règles de génération

### Combat et armement

- Une arme de poing est débloquée par les tirages de la catégorie combat.
- Si aucune munition compatible n'a de recette, une munition est créée dans la même tech.
- Si une munition compatible existe déjà, rien n'est ajouté. Il n'y a pas de pourcentage de non-génération.
- Deux étapes qui débloquent chacune une arme de poing ne sont pas fusionnées.

### Transports avancés

- Véhicules, trains et logistique avancée suivent les tirages des autres catégories.
- Aucune contrainte n'impose un appariement entre rails et locomotives.

### Armes montées randomisées

- Les armes montées sont repérées par les liens d'entité du dump. Elles ne sont pas craftées pour elles-mêmes.
- Chaque véhicule armé reçoit un nombre d'armes tiré dans la réserve configurée, avec ou sans remise selon la configuration.
- Les doublons sont retirés après le tirage, y compris quand le tirage autorise le remplacement.
- Chaque arme tirée est clonée pour le véhicule, avec une portée ajustée à sa taille. Les items d'origine gardent leur recette normale.
- Les munitions manquantes sont créées puis placées dans au plus trois techs isolées après celle du véhicule.

### Écart connu

La spécification historique demande une munition pour chaque arme, avec une chance de ne pas l'ajouter quand une munition compatible existe déjà.
 Le code crée une munition seulement quand aucune n'existe, et n'applique aucune chance.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Une munition quand aucune munition compatible n'existe. | Une munition ajoutée quand une munition compatible existe. |
| Des armes distinctes montées sur chaque véhicule armé. | Le nombre d'armes retenues après déduplication. |

## Aller plus loin

- [aiguillage.md](aiguillage.md#nœuds-isolés-et-dispatch) — à lire quand il faut situer la tech des munitions.
- [recettes.md](recettes.md#couverture-complète--le-balayage-de-contenu) — à lire pour comprendre pourquoi les armes montées sont écartées du balayage.
- [model.md](model.md) — à lire quand il faut distinguer les types de bâtiments.
- [config.md](config.md) — à lire quand il faut régler la réserve d'armes et la portée.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [aiguillage.md](aiguillage.md) — dispatch des armes et munitions.
- [recettes.md](recettes.md) — balayage de contenu et recettes de véhicules.
- [model.md](model.md) — classification des bâtiments et directives.
- [tech.md](tech.md) — déblocage des technologies de combat.
