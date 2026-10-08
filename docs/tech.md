# L'arbre technologique et la fin de partie

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 13. L'arbre technologique

- **État actuel** : l'arbre est linéaire, valide et sans boucles. Tout est géré automatiquement pour intégrer les maillons des phases précédentes.
- **Un unlock par recette** : chaque recette est débloquée par une seule technologie. Les recettes d'extracteur, issues du starter, sont repositionnées par `extractor_timing` au niveau de leur premier consommateur. Si le batch n'est jamais utilisé, une technologie payante est tirée aléatoirement (`extractor_timing.py:5-45`).
- **Aucune recette orpheline** : les macro-techs du starter sont rejouées après la phase d'électricité. Toute recette générée (générateur, combustible, lab) est rattachée à une technologie via la clé `unlocked_recipes`. Le validateur signale tout écart (invariant 3 du code = **item 6** de §15) sans rejeter la seed.
- **Branchement** : un arbre en branches est prévu pour plus tard. Ce point est pour l'instant mis de côté.
- **Nombre d'objets par tech** : une technologie « groupable » débloque 1 objet de base, puis s'étend selon une chaîne probabiliste : 75 % de chance pour un 2e objet, 65 % pour un 3e, 35 % pour un 4e et 15 % pour un 5e. Le premier tirage échoué arrête le groupe (plafond de 5). Les probabilités sont configurables via `group_chances` (§16). Les nœuds dédiés (sciences, munitions, techs de prologue §7, endgame §14) restent isolés. Les pylônes ne fusionnent jamais deux de leurs steps dans la même tech (cadence), avec un maximum de 5. Exception : la 2e recherche gratuite du starter (§8) reste un monolithe débloquant tout le bootstrap (lab, packs, premiers bâtiments).
- **Coûts de recherche** : le coût est toujours un science pack. Le moteur n'utilise que des packs, qui doivent être disponibles dans la progression et utiles pour la suite, sans créer de cul-de-sac.
- **Cohérence des sciences** : chaque pack utilisé comme coût possède une recette générée et débloquée avant la technologie qui le consomme. La production précède la consommation. Le lab étant garanti dès le starter (§8), l'économie de packs est exploitable.
- **JAMAIS de ressource brute dans un pack** : la recette d'un science pack ne consomme aucune matière extraite du sol (patchs, environnement, fluides d'extraction, §3). Elle utilise exclusivement des intermédiaires craftés. Cette règle est appliquée au tirage et vérifiée par l'invariant 7 du code = **item 5** de §15.
- **Coût systématique** : toute technologie récursive nécessite un coût en science pack. Pour amorcer la filière, le premier pack est craftable et débloqué gratuitement par le starter. Les technologies de prologue (`randputf-prologue-*`, §7) se débloquent par hand-craft (coût vide, §9.3) d'un item disponible dès le bootstrap. Le pool des déclencheurs est limité aux produits des recettes gratuites du starter. Seuls les science packs sont admis comme coût par le moteur. Chaque pack suivant se débloque en consommant le précédent.
- **Garantie d'amorçage** : si le starter ne peut pas générer le premier pack, la phase récursive amorce la filière avec un pack du jeu pour éviter qu'une technologie sans coût ne bloque la progression (`§seed`). Le pool de coût n'est jamais vide.
- Les science packs suivent les mêmes pourcentages d'obtention que les autres éléments (§9.1).
- **Affichage du coût** : le coût d'une technologie affiche la quantité de science packs (`amount = 1` par pack). Le `count` de la recherche représente le nombre de cycles, soit un total d'items égal à `count` × nombre de packs (1 à 4). La durée par unité est fixée à `time = 60 s`. Le nombre d'items reste l'affichage privilégié.
- **Icônes des items débloqués** : chaque nœud affiche les images des items ou recettes débloqués (jusqu'à 4 icônes en grille 2×2) au lieu de l'icône par défaut.

## 14. Fin de partie

Classique et inchangée :

- victoire = lancement de la fusée ;
- le joueur peut ensuite poursuivre vers les technologies infinies.

Le randomizer garantit l'atteignabilité de la fusée pour toute seed acceptée (§15).

**Phase endgame** : en base 2.0, `rocket-part` consomme `processing-unit`, `low-density-structure` et `rocket-fuel`. Leurs recettes vanilla étant désactivées, une phase située après le récursif et avant les relais garantit une recette générée pour ces 3 items. Les ingrédients sont tirés dans le pool profond et ne sont pas environnementaux. Ils sont débloqués par la dernière technologie `randputf-endgame-rocket`.

La phase endgame garantit également le `rocket-silo`. La `rocket-part` se fabrique dans le silo. L'item `rocket-silo` (qui n'est jamais un patch, §6) reçoit sa recette générée dans la technologie finale `randputf-endgame-rocket`, ou via sa technologie récursive si celle-ci l'a déjà déployé.
