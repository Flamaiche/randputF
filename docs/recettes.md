# La phase récursive : génération des recettes

Retour : [docs/README.md](README.md).

Cette page explique comment la seed fabrique les recettes après le départ. Les tirages choisissent une catégorie, puis un objet, puis ses ingrédients. Les garde-fous ajoutent ensuite les éléments sans lesquels la progression serait bloquée.

## Ce que ça change pour le joueur

- Deux seeds données produisent des recettes et des objets différents.
- Chaque objet visé reçoit une recette ou un autre moyen d'obtention.
- Les éléments essentiels, comme le courant et la chaleur, restent débloquables.

## Mots à connaître

- [pool](glossaire.md) — réserve d'objets parmi lesquels la seed tire.
- [tier](glossaire.md) — profondeur d'un objet dans la chaîne de fabrication.
- [déblocage sur le tas](glossaire.md) — création d'un prérequis au moment du besoin.
- [compagnon](glossaire.md) — objet lié à un autre pour rester utilisable.
- [jalon](glossaire.md) — étape qui garantit une catégorie de contenu.

## Règles de génération

### La phase récursive

- La phase suit le départ et l'électricité.
- Elle enchaîne des étapes. Chaque étape devient une macro-tech, puis une recherche de l'arbre linéaire décrit dans [tech.md](tech.md#larbre-technologique).

### Tirages pondérés

- Chaque catégorie possède un poids : transformation, extraction, génération, distribution, combat, science.
- Le facteur de progression multiplie tous les poids par la même valeur.
- Les objets déjà obtenus ou exclus par la configuration sortent de la réserve. Les déblocages sur le tas y ajoutent des objets.

### Génération des recettes

- La recette tire ses ingrédients dans le pool atteignable.
- L'atelier est choisi selon ses entrées, ses sorties et ses directives.
- Le temps de craft augmente avec le nombre d'ingrédients. Les quantités suivent une cible consommation/production tirée une seule fois par seed.

### Déblocage sur le tas

- Un besoin sans recette est traité pendant l'étape en cours.
- Une ressource brute, un atelier ou un craft intermédiaire peut être créé.
- Un nouvel atelier est rattaché à la technologie de l'objet en cours.
- Les prologues tirent leur déclencheur dans les recettes gratuites du départ. Le nombre de crafts vaut `round(2 ** (n + 1/4))` avec `n` entre 2 et 6, calculé dans `relay_phase.py`. L'exposant se cale sur la première science, à l'indice 1, puis est réutilisé tel quel.

### Cadence garantie des pylônes

- Un pylône réel est forcé aux jalons configurés, ou dès la première étape si aucun n'est disponible.
- Le décompte porte sur les pylônes pourvus d'une recette de production. Un pylône posé au sol ne suffit pas.
- Le pylône forcé est généré dans l'itération en cours. Cette itération est consommée : aucun autre tirage ordinaire n'a lieu.
- Un besoin électrique plus tôt est traité par la phase électricité, qui débloque un générateur puis un pylône.

### Relais des ressources non-infinies

- Le relais remplace les recettes qui consomment des ressources épuisables par une route durable.
- L'anti-cycle est vérifié sur les objets, pas sur l'ordre des recettes.
- Les prologues ne sont pas gratuits : chacun se débloque par un craft manuel.

### Couverture complète : le balayage de contenu

- Une passe finale donne une recette et une technologie aux objets restants.
- Les objets dépendants du réseau sont traités en fin de passe.
- La chaîne fusée, les armes montées et les objets virtuels sont écartés du balayage.
- Un objet non empilable reçoit une quantité d'une seule unité.

### Garantie de compagnons

- Les groupes configurés réunissent les robots avec le roboport et le panneau solaire avec l'accumulateur.
- Quand un membre est généré, la recette des membres manquants est créée.
- Les membres manquants sont placés dans au plus trois techs isolées après la tech du produit.
- Aucune vérification de la présence d'une source de courant ne précède le groupe solaire.

### Auto-sélection : ne pas ombrager une recette

- Les recettes portées par un même bâtiment auto-sélectionnable ne partagent pas leurs ingrédients.
- Un conflit détecté en aval est corrigé par déplacement, retrait d'ingrédient ou craft manuel.

### Écart connu

- Le pylône doit être décalé vers l'étape où un générateur est tiré sans pylône, selon la spécification historique.
 Le code actuel force le pylône dans l'itération courante et consomme cette itération. Le décalage propre aux générateurs n'est pas implémenté.
- Une vraie source de courant devrait exister avant la génération de l'accumulateur, selon la spécification historique.
 `_dispatch_companions` ne fait pas cette vérification. L'accumulateur reste un stockage avec entrée et sortie, et non un générateur.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Une recette ou un autre moyen d'obtention pour les objets visés. | L'ordre exact des catégories tirées. |
| Des pylônes réels aux jalons configurés. | Le décalage du pylône vers l'étape d'un générateur. |
| Des compagnons craftables quand un membre du groupe est généré. | Une source de courant vérifiée avant l'accumulateur. |

## Aller plus loin

- [aiguillage.md](aiguillage.md) — à lire quand il faut savoir dans quelle recherche un objet atterrit.
- [energie.md](energie.md#lélectricité) — à lire quand le besoin de courant apparaît.
- [tech.md](tech.md#larbre-technologique) — à lire pour comprendre l'arbre assemblé à partir des étapes.
- [solvabilite.md](solvabilite.md) — à lire pour vérifier ce qui reste vrai pour toute seed.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [aiguillage.md](aiguillage.md) — rattachement des éléments aux technologies.
- [energie.md](energie.md) — pylônes et résolution électrique.
- [tech.md](tech.md) — arbre technologique produit par la phase récursive.
