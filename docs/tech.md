# L'arbre technologique et la fin de partie

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 13. L'arbre technologique

- **État actuel** : l'arbre est linéaire et valide. Il est exempt de boucles, chaque élément est déblocable et tout est géré automatiquement. Chaque maillon issu des phases précédentes y est intégré.
- **Un unlock par recette** : chaque recette est débloquée par une seule technologie. Il n'y a pas de double déblocage. (Les recettes d'extracteur partent de la tech d'extraction du starter, puis la passe `extractor_timing` les repositionne au premier consommateur.)
- **Aucune recette orpheline** : les macro-techs du starter sont rejouées après la phase d'électricité. Toute recette générée (générateur, combustible, lab) est rattachée à une technologie (set `unlocked_recipes`) ; le validateur signale tout écart (invariant 3, §15) sans rejeter la seed.
- **Branchement** : un arbre en branches est prévu pour une phase ultérieure. Ce point est mis de côté pour le moment.
- **Nombre d'objets par tech** : chaque technologie « groupable » débloque 1 objet de base, étendu en chaîne probabiliste : 75 % de chance pour un 2e objet, 65 % pour un 3e, 35 % pour un 4e, 15 % pour un 5e. Le premier tirage échoué stoppe le groupe (plafond de 5). Les probabilités sont configurables via `group_chances` (§16). Les nœuds dédiés (sciences, munitions, techs de prologue §7, endgame §14) conservent une forme isolée ; les pylônes, eux, ne fusionnent jamais deux de leurs steps dans la même tech (cadence) — tous capés à 5. Exception : la 2e recherche gratuite du starter (§8) reste monolithe ; elle débloque tout le bootstrap (lab, packs, premiers bâtiments).
- **Coûts de recherche** : le coût d'une recherche est toujours un science pack (le jeu de base admettrait un matériau arbitraire, mais le moteur n'utilise que des packs). Le coût doit être disponible dans la progression courante et utile pour la suite, sans jamais constituer un cul-de-sac.
- **Cohérence des sciences** : chaque pack utilisé comme coût possède une recette générée et débloquée avant la technologie qui le consomme. La production précède la consommation, ce qui est vérifié à la génération. Le lab étant garanti dès le starter (§8), l'économie de packs est exploitable.
- **JAMAIS de ressource brute dans un pack** : la recette d'un science pack ne consomme aucune matière extraite du sol (patchs, environnement, fluides d'extraction, §3). Elle se compose exclusivement d'intermédiaires craftés. Ceci est appliqué au tirage et vérifié par l'invariant 7 (§15).
- **Coût systématique** : toute technologie récursive nécessite un coût en science pack. Pour amorcer la filière, le premier science pack est craftable et débloqué gratuitement par le starter. Les technologies de prologue (`randputf-prologue-*`, §7) se débloquent par hand-craft (coût vide, §9.3) d'un item disponible dès le bootstrap. Le pool des déclencheurs est limité aux produits des recettes gratuites du starter. Seuls les science packs sont admis comme coût de recherche par le moteur. Chaque pack suivant se débloque en consommant le précédent, assurant une continuité.
- **Garantie d'amorçage** : si le starter ne peut pas générer le premier pack, la phase récursive amorce la filière avec un pack du jeu pour éviter qu'une technologie sans coût ne bloque la progression (`§seed`). Le pool de coût n'est jamais vide.
- Les science packs suivent les mêmes pourcentages d'obtention que les autres éléments (§9.1).
- **Affichage du coût** : le coût d'une technologie s'affiche en quantité de science packs (`amount = 1` par pack) — le `count` de la recherche est le nombre de cycles par pack, soit un total d'items = `count` × nombre de packs (1 à 4). La durée par unité est fixée (`time = 60 s`) ; le nombre d'items est l'affichage privilégié.
- **Icônes des items débloqués** : chaque nœud affiche les images des items ou recettes débloqués (jusqu'à 4 icônes en grille 2×2) au lieu de l'icône par défaut.

## 14. Fin de partie

Classique et inchangée :

- victoire = lancement de la fusée ;
- le joueur peut ensuite poursuivre vers les technologies infinies.

Le randomizer garantit l'atteignabilité de la fusée pour toute seed acceptée (§15).

**Phase endgame** : en base 2.0, `rocket-part` consomme `processing-unit`, `low-density-structure` et `rocket-fuel`. Leurs recettes vanilla étant désactivées, une phase située après le récursif et avant les relais garantit une recette générée pour ces 3 items. Les ingrédients sont tirés dans le pool profond et non environnementaux. Ils sont débloqués par la dernière technologie `randputf-endgame-rocket`.

La phase endgame garantit également le `rocket-silo`. `rocket-part` se fabrique dans le silo. L'item `rocket-silo` (jamais un patch, §6) reçoit sa recette générée dans la technologie finale `randputf-endgame-rocket`, ou via sa technologie récursive si celle-ci l'a déjà déployé.
