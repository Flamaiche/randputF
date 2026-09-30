# L'arbre technologique et la fin de partie

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 13. L'arbre technologique

- **État actuel assumé** : l'arbre est **linéaire**, mais **valide** — sans
  boucle, tout y est déblocable et tout y est géré automatiquement. Chaque
  maillon généré par les phases précédentes y trouve sa place.
- **Un unlock par recette** : chaque recette est unlockée par **une seule**
  tech (jamais de double unlock — par ex. l'extracteur n'apparaît que dans la
  tech d'extraction, pas dans celle de transformation).
- **Aucune recette orpheline** : les macro-techs du starter sont **rejouées
  après la phase d'électricité** ; toute recette créée sur le tas au fil des
  phases (générateur, combustible, lab) est systématiquement rattachée à une
  tech — le validateur rejette toute seed avec une recette non déblocable.
- **Branchement** : un arbre en branches pourra être envisagé **à la fin de
  l'implémentation** ; ce point est explicitement mis de côté d'ici là.
- **Nombre d'objets par tech** : chaque tech « groupable » débloque **1 objet
  de base, étendu en chaîne probabiliste** — 75 % de chance d'un 2e objet,
  65 % d'un 3e, 35 % d'un 4e, 15 % d'un 5e (le premier tirage raté stoppe le
  groupe, plafond strict de 5). Probabilités configurables via
  `tree.group_chances` (§16). Les nœuds dédiés (sciences, pylônes, dispatch de
  munitions, techs de prologue §7, endgame §14) conservent leur forme isolée,
  capés à 5 aussi. Exception assumée : la **2e recherche gratuite du starter**
  (§8) reste monolithe — elle débloque tout le bootstrap d'un coup (lab, packs,
  premiers bâtiments), c'est la nature même du booster de départ.
- **Coûts de recherche** : le coût d'une recherche peut être un **matériau**
  arbitraire et pas seulement des packs de science (le jeu de base le permet,
  c'est juste rare). Point à ne surtout pas oublier : ce matériau doit être
  **à obtenir** dans la progression courante **et utile pour la suite** —
  jamais un cul-de-sac.
- **Cohérence des sciences** : chaque pack qui sert de coût possède une recette
  générée **et unlockée avant** la tech qui le consomme (production avant
  consommation, vérifié à la génération). Le lab étant garanti dès le starter
  (§8), l'économie de packs est réellement consommable.
- **JAMAIS de ressource brute dans un pack** : la recette d'un science pack ne
  consomme aucune matière extraite du sol — ni patch posé en ressource, ni item
  environnemental (bois/pierre/poisson), ni fluide d'extraction (eau, pétrole
  brut, vapeur — infinis ou non, §3). Elle se fabrique exclusivement à partir
  d'intermédiaires craftés. Appliqué au tirage (starter, branche science,
  balayage de contenu) et vérifié par l'invariant 7 (§15).
- **Coût systématique** : **toute tech récursive paie un coût en science pack**
  (bâtiments, armes, packs). Une tech gratuite en profondeur rendrait la
  progression triviale. Pour amorcer la filière, le **premier** science pack
  est rendu craftable et unlocké **gratuitement par le starter** (starter-
  transformation, façon red-science vanilla) — les techs de prologue
  (`randputf-prologue-*`, §7) se débloquent, elles, par **hand-craft**
  (cost vide, §9.3) d'un item **effectivement craftable dès le bootstrap** :
  le pool des déclencheurs est limité aux produits des recettes des techs
  gratuites du starter (jamais aux recettes étendues ensuite par les autres
  phases — §9.3), donc la quantité n'est jamais demandée avant d'être
  fabricable ; seuls les science
  packs (items type tool) sont admis comme coût de recherche par le moteur ;
  chaque pack suivant se débloque en consommation du pack précédent, donc
  chaque tech a toujours un pack déjà produit vers lequel pointer.
- **Garantie d'amorçage** : si le starter n'a pas pu seedé le premier pack
  (pool de packs non-obtenus vide), la phase récursive amorce quand même la
  filière avec un pack du jeu — sinon une tech sans coût planterait (`§seed`).
  Combiné à l'exclusion des packs du pool de patchs (§6), le pool de coût
  n'est jamais vide.
- Les **science packs** eux-mêmes suivent les pourcentages d'obtention, comme
  les bâtiments et tout le reste (§9.1).
- **Affichage du coût en nombre d'items** : le coût d'une tech s'affiche comme
  une **quantité de science packs** (le `count` de la recherche = nombre total
  d'items à fournir, `amount = 1` par pack), façon vanilla — la jauge de
  recherche compte exactement le nombre de packs, pas un « temps d'attente »
  dominant. La durée par unité reste fixée (`time = 60 s`) mais le nombre
  d'items est l'affichage privilégié.
- **Icônes des items débloqués** : chaque nœud de l'arbre affiche les **images
  des items/recettes qu'il débloque** (unités, bâtiments, armes, science packs)
  au lieu de l'icône par défaut du template (machine d'assemblage). Jusqu'à
  **4 icônes** en grille 2×2, comme les techs multi-icônes vanilla ; chaque
  nœud montre ainsi clairement ce qu'il déverrouille.

## 14. Fin de partie

Classique et inchangée :

- **victoire = lancement de la fusée** ;
- ensuite, le joueur peut continuer vers les **technologies infinies**, qui ne
  changent pas dans leur principe.

Le randomizer doit garantir l'atteignabilité de la fusée pour toute seed
acceptée (§15).

**Phase endgame** : en base 2.0, `rocket-part` (recette vanilla
exempte, jamais désactivée) consomme `processing-unit`, `low-density-structure`
et `rocket-fuel`. Leurs recettes vanilla étant désactivées par le randomizer,
une phase **après le récursif et avant les relais** garantit une recette
générée pour chacun de ces 3 items — ingrédients tirés dans le pool profond,
**jamais** environnementaux (pas de fusée au bois/pierre) — unlockés par la
dernière tech de l'arbre (`randputf-endgame-rocket`). Sans cette phase, la
fusée (et donc la victoire) serait inatteignable pour toutes les seeds.

La phase endgame garantit aussi le **rocket-silo lui-même** : `rocket-part` se
craft **dans** le silo. Si la récursion s'arrête sans déployer le silo, rien
ne peut lancer de fusée ; l'item `rocket-silo` (jamais un patch, §6) reçoit
donc sa recette générée dans la même tech finale `randputf-endgame-rocket`, ou
par sa tech récursive si la récursion l'a déjà déployé (chaque recette reste
débloquée par une seule tech, §15).
