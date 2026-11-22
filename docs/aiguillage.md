# L'aiguillage : mise en technologies

Retour : [docs/README.md](README.md).

Cette page explique comment un objet produit par une phase rejoint une technologie. Le générateur le rattache à une recherche existante ou lui en réserve une. Certains objets restent seuls pour rester utilisables au bon moment.

## Ce que ça change pour le joueur

- Une recherche débloque parfois plusieurs objets.
- Une arme de poing et sa munition arrivent dans la même recherche quand aucune munition n'est disponible.
- Les objets dépendants d'un autre restent proches de leur déclencheur.

## Mots à connaître

- [jalon](glossaire.md) — étape qui garantit une catégorie de contenu.
- [compagnon](glossaire.md) — objet lié à un autre pour rester utilisable.
- [déblocage sur le tas](glossaire.md) — création d'un prérequis au moment du besoin.
- [pool](glossaire.md) — réserve d'objets parmi lesquels la seed tire.

## Règles de génération

### Tirages pondérés

- Les catégories suivent les mêmes poids que dans la phase récursive. Le détail figure dans [recettes.md](recettes.md#tirages-pondérés).
- Le facteur de progression est commun à toutes les catégories.

### Groupement en une technologie

- Une tech groupable débloque un premier objet.
- Le groupe peut s'étendre jusqu'à cinq objets avec les chances configurées. Le premier tirage raté arrête l'extension.
- Restent seuls le départ gratuit, les prologues à craft manuel, l'apparition d'un pack de science, les objets isolés, les pylônes et les armes de poing.

### Nœuds isolés et dispatch

- Les recettes créées sur le tas sont placées juste après l'étape qui les rend nécessaires, dans au plus trois techs isolées.
- Les munitions de véhicule suivent ce patron avec des packs déjà débloqués.
- Les compagnons suivent le même patron quand un membre du groupe est généré.
- Le pylône forcé occupe l'itération en cours, qui est alors consommée.

### Munitions d'armes de poing

- La catégorie de munitions est lue sur l'arme au moment de sa génération.
- Si aucune munition compatible n'a de recette, une seule munition est créée dans la même tech.
- Si une munition compatible existe déjà, rien n'est ajouté. Il n'y a aucun pourcentage de non-génération.

### Écart connu

- La spécification historique demande
 une munition pour chaque arme, avec une chance de ne pas l'ajouter quand une munition compatible existe déjà. Le code ajoute une munition seulement quand aucune n'existe, sans appliquer de chance.
- La spécification historique demande
 de vérifier une source d'électricité avant de dispatcher le panneau solaire et l'accumulateur. `_dispatch_companions` ne le fait pas. L'accumulateur reste un stockage, et non un générateur.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Une munition quand l'arme n'en a aucune de compatible. | Une munition supplémentaire quand une munition compatible existe. |
| Des techs isolées pour les objets dépendants. | Une source d'électricité vérifiée avant l'accumulateur. |

## Aller plus loin

- [recettes.md](recettes.md#la-phase-récursive) — à lire quand il faut savoir comment l'objet est fabriqué.
- [tech.md](tech.md#larbre-technologique) — à lire quand il faut voir l'ordre des recherches.
- [combat.md](combat.md#combat-et-armement) — à lire quand le sujet concerne les armes et les véhicules.

## Lectures associées

- **Parent** : [recettes.md](recettes.md) — la phase récursive.
- [tech.md](tech.md) — arbre technologique et fin de partie.
- [combat.md](combat.md) — combat et transports avancés.
- [starter.md](starter.md) — la phase de démarrage.
