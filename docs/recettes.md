# La phase récursive : génération des recettes

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 9. La phase récursive

Après le starter, la génération devient récursive. Le début aussi s'appuie
sur des pourcentages pour obtenir telle ou telle chose — mais ici ils sont
utilisés massivement et systématiquement :

### 9.1 Tirages pondérés

- Chaque catégorie (bâtiments, armes, science packs, transports avancés…)
  possède un **pourcentage d'obtention**.
- Ce pourcentage dépend du **type du bâtiment** et du **nombre total de
  bâtiments** déjà présents dans la partie.
- Plus on avance dans les recettes implémentées, plus il devient possible
  d'en débloquer davantage : le pool s'élargit avec la progression.

### 9.2 Génération des recettes

Les recettes restent simples dans leur forme :

1. regarder **tout ce que le joueur peut obtenir** (pool atteignable) ;
2. vérifier les **bâtiments** dont dispose le joueur (leurs types, slots et
   directives) ;
3. créer la recette à partir de choses prises **aléatoirement** dans ces
   ensembles compatibles.

**Temps de craft randomisé** : le `energy_required` de chaque recette
n'est pas fixé à 0,5 s. Chaque recette tire un temps de base dans la liste
configurable `recipes.energies` (défaut `[0.5, 1.0, 2.0]`), puis le multiplie
par `(1 + recipes.energy_per_ingredient × nb_d_ingrédients)` (défaut 0,25) :
une recette lourde prend **proportionnellement plus de temps** qu'une recette
simple — re-tune léger du gameplay, sans toucher à la solvabilité (une durée
plus longue ne change jamais le pool atteignable).

**Équilibre production/consommation** : le générateur suit, à chaque
recette posée, **ce que la seed produit** et **ce qu'elle consomme** (compteurs
cumulés par item). Une cible d'équilibre `cons/prod` est tirée une fois par
seed uniformément dans `recipes.balance_min..balance_max` (défaut `3/16..2/3`).
Un item dont le ratio passe **sous la cible** est « pléthore » (produit mais
peu consommé) : on **récompense sa consommation** comme ingrédient (on écoule
le surplus) et on **freine sa production** comme produit (`_pick_product`,
1 / facteur) ; l'inverse pour un item rare. Le déséquilibre est plafonné au
quota `recipes.max_overproduced_ratio` (défaut `1/3`) — on ne pousse jamais à
consommer un flux stupide. Effet : les quantités consommées tendent vers les
quantités produites (« on n'accumule pas ce qu'on ne se sert pas »), sans
jamais changer le pool atteignable (donc sans casser la solvabilité §15).

### 9.3 Déblocage sur le tas

Puisque toutes les ressources sont plus ou moins déblocables :

- une recette peut d'un coup ajouter le besoin d'une ressource brute encore
  inconnue de la partie : le randomizer l'intègre immédiatement ;
- si une recette prend une ressource non automatisable, on débloque **au même
  moment** la façon de la créer/l'obtenir ;
- si quelque chose de plus est nécessaire pour débloquer cette ressource, cela
  est fait **sur le tas** : on choisit en fonction du type de la ressource
  demandée, et si elle n'est pas encore en possession du joueur, le craft
  correspondant est généré en même temps.

Le résultat : aucune impasse possible, mais aussi aucun chemin prévisible.

**Claim des ateliers débloqués « sur le tas » (anti-recette-orpheline)** : un
bâtiment de craft débloqué pendant la génération d'un élément (via
`_pick_building` → `_unlock_building`, typiquement un assembleur de tier
supérieur requis par une recette récursive) produit une recette
`randputf-<bâtiment>` qui doit être **claimée par la tech de l'élément en cours
de génération** — sinon elle reste **orpheline** (jamais unlockée : le joueur
peut crafter le bâtiment mais jamais le débloquer). `_generate_for_element`
compare donc `unlocked_buildings` avant/après l'élément et ajoute tout
bâtiment nouvellement débloqué à `step_buildings`/`unlocks_buildings` de la
tech (dédup en conservant l'ordre). Couvre **tout** déblocage d'atelier sur le
tas, quel que soit l'élément — zéro recette orpheline mesurée sur 200 seeds.

Les **déclencheurs hand-craft** des techs (prologue §13, et plus tard les
tirages aléatoires parmi les techs) obéissent à la même règle : l'item
demandé doit être **available AVANT** la tech qui le réclame. Bug classique à
éviter (et corrigé ici) : ne jamais tirer les candidats depuis une liste de
recettes **étendue après coup** par une phase postérieure — on prendrait des
items unlockés bien plus tard (four électrique, réacteur nucléaire, silo…),
et la tech resterait **bloquée pour toujours** (§9.3). Les candidats sont donc
calculés à partir des **seules recettes des techs gratuites du starter**
(disponibles au bootstrap), et chaque déclencheur est vérifié strictement
avant sa tech (voir `test_craft_trigger_prologue_craftable_des_le_starter`).
La quantité à hand-crafter n'est jamais un singleton trivial : chaque prologue
demande un **nombre d'items** (`research_trigger` `craft-item` avec `count`)
égal à **2^(n + indice_science/4)**, où `n` est tiré au hasard dans (1, 6]
(1 exclu, 6 inclu) et `indice_science` est la position de la science dans
l'ordre du tech tree. Le prologue précède la chaîne des sciences (indice 1) :
les bornes donnent donc 2^2.25 ≈ 5 à 2^6.25 ≈ 76 items.

L'indice de science rend le mécanisme directement réutilisable pour un tirage
aléatoire parmi les techs plus profondes : plus la science est avancée dans
l'arbre, plus le nombre d'items à fabriquer est grand. Pour ce tirage, la
même contrainte s'applique : restreindre le pool aux items de recettes déjà
unlockées, jamais aux produits de recettes futures.

### 9.4 Cadence garantie des pylônes

La distribution du courant (§10) est vitale pour la progression : sans poteau,
un générateur ne transporte rien de jouable. Pour éviter le pire cas où le
premier pylône n'apparaît qu'en profondeur de l'arbre, on force une **cadence
de 3 pôles** pendant la phase récursive, indépendamment du hasard :

- **3 pôles verrouillés** (`dist_marks = (8, 28, 48)` par défaut) : un pôle tôt
  (dès ~8 steps récursifs), un deuxième ~20 steps plus loin, un troisième ~20
  encore après.
- Chaque pôle forcé tire un **type différent** (petit → moyen → grand /
  substation via `_pick_element`, jamais déjà déployé — donc pas de doublon).
- Si le starter a déjà débloqué un pylône **craftable** (électricité au
  bootstrap, §10), le premier jalon est **déjà satisfait** : on ne force rien
  tant que les jalons suivants ne sont pas atteints. Un pylône posé **en patch**
  au sol (§6) ne compte pas : il n'est pas constructible, le joueur ne peut pas
  s'en servir pour étendre son réseau (§9.6, `_has_product_recipe`).
- Les pylônes **au-delà** de ces 3 jalons restent randomisés comme de simples
  items/bâtiments (§9.1) — pas de sur-cadence.

Configurable dans `RecursiveConfig` (`dist_marks`, `dist_guaranteed`) via
`recursive` dans `settings` (§16).

### 9.5 Relais des ressources non-infinies

Les ressources non automatisables (arbres → `wood`, rochers → `stone`, poissons
→ `raw-fish`) sont obtenues dès le départ, mais s'épuisent : elles ne peuvent
pas être la colonne vertébrale d'un run. Comme le bootstrap se joue précisément
sur ces ressources rares, **les recettes du démarrage (craftables à la main,
§10) DOUBLENT la quantité de leurs ingrédients environnementaux** — la bascule
vers les recettes « propres » du relais devient aussi un objectif économique.
La phase relais, qui tourne **après toutes les phases productrices de
recettes**, garantit leur remplacement :

1. **Scan** : on détecte chaque recette générée dont un ingrédient est un item
   environnemental, et dont le produit n'est pas lui-même environnemental.
2. **Pool gelé du début de run** : les ingrédients et le bâtiment de craft du
   relais sont tirés **uniquement dans l'instantané du pool pris APRÈS le
   starter + l'électricité, AVANT le récursif**. Un relais ne dépend donc
   jamais d'un item ou d'un bâtiment uniquement débloqué en profondeur de seed
   (science pack, oil-refinery, AM3, …) — il est utilisable dès les premières
   recherches, pas au bout de 20 techs. Ce gel est ce qui rend la version
   relais du pumpjack (ou de l'assembleur) réellement jouable dès le début.
3. **Création du relais** : pour ce produit, on tire une **recette relais**
   (`randputf-relay-<produit>`) — même produit, mais ingrédients tirés dans ce
   pool gelé (patch, item fabriqué, fluide obtenu), bâtiment de craft limité à
   ceux du même instantané (jamais de déblocage sur le tas hors pool). Le
   relais coexiste avec la recette bootstrap d'origine, qui reste
   hand-craftable.
4. **Consolidation en prologue** : les recettes relais sont regroupées en
   **techs de prologue** (`randputf-prologue-*`, §7, **≤ 5 unlocks chacune**,
   plafond §13), placées **immédiatement après les techs gratuites du starter**
   (une seule si peu de recettes, aucune si rien).

   Elles ne sont pas des free_researches et se débloquent par **hand-craft** d'un
   item du bootstrap (§9.3) : le bootstrap reste la route de départ, et le
   joueur bascule sur les versions propres + l'entrée en sciences dès qu'il
   fabrique le déclencheur, sans compter sur le bois/pierre/poisson sur la
   durée.

Règles d'anti-cycle spécifiques au relais :

- ingrédients interdits : environnementaux + **le produit lui-même** + les
  produits **déjà relayés** (dans l'ordre de création pour les relais, jamais
  de dépendance vers un relais plus ancien → **DAG** par construction) ;
- les recettes relais ne peuvent **pas** référencer un fluide en ingrédient
  pour produire un **extracteur** (même règle items-only que §8) ;
- le scan est **relancé jusqu'à stabilité** : une recette créée « sur le tas »
  pendant un tirage (déblocage d'un bâtiment) peut à son tour consommer des
  environnementaux et mériter son propre relais.

Si aucun item durable n'est disponible (cas limite d'une seed sans aucun pool
item), le relais est simplement **manqué silencieusement** : la recette bootstrap
reste l'unique route — acceptable puisque la solvabilité, elle, est garantie.

**Conséquence sur la validation (§15)** : un relais n'est qu'une **route
alternative** à un produit — pas un doublon cyclique. L'anti-cycle est donc
vérifié au niveau **item** (un item est solvable dès que l'une de ses recettes
l'est), et non plus en tri topologique de Kahn au niveau recette.

### 9.6 Couverture complète : le balayage de contenu

Sans étape supplémentaire, la récursion (§9) ne touche que les 4 catégories
fonctionnelles + combat + science : une fois les bâtiments de ces catégories
recrutés, la boucle s'arrête (~35 techs) et le reste du jeu **n'a jamais de
recette**. Une phase **3bis**, exécutée **après** la récursion pondérée et
**après** la chaîne fusée (§14), garantit à **chaque item restant** sa recette
`randputf-<item>` et sa tech `randputf-content-<item>` :

- **Cibles** : tout item beltable sans recette produit, dans un ordre déterminé
  par la seed.
- **Coûts** : la récursion précédente a déjà unlocké **tous** les science packs,
  donc le coût de chaque tech de balayage est toujours un pack déjà disponible
  (payable production → consommation, §13).
- **Patches** : un item posé au sol (§6) garde quand même sa recette
  (`make_recipe`, pas `ensure_obtainable`) : « obtainable » ≠ « craftable ».
- **Exclusions** : chaîne fusée (`processing-unit`, `low-density-structure`,
  `rocket-fuel`, `rocket-silo` — sinon doublon d'unlock avec `randputf-endgame-*`),
  armes montées (rattachées à LEUR véhicule en §12 — jamais randomisées comme
  armes de poing), items de contrôle (`is_virtual_item` : blueprint, planner,
  *remotes*, items `rail-planner` sans place_result…) — jamais de recette ni de
  patch.
- **Empilabilité** : Factorio refuse qu'une recette produise **ou** consomme
  plus de 1 exemplaire d'un item non-empilable (armure, arme à feu, véhicule,
  capsule/remote…) — erreur de chargement « not stackable but has a max count
  of N ». Le générateur clampe donc `amount` à **1** pour tout produit ou
  ingrédient non-stackable (`ItemDef.is_stackable`) : le `stack_size` réel du
  dump fait foi quand il en porte un, sinon le type (`gun`, `armor`,
  `item-with-entity-data`, capsules…) déduit la non-empilabilité
  (`NON_STACKABLE_ITEM_TYPES`).
- **Nommage** : un ID finissant par `-<nombre>` est lu par Factorio comme un
  **palier d'upgrade** et exige des paliers contigus (uranium-235 puis
  uranium-238 → niveaux 235 puis 238 non contigus → erreur de chargement). Les
  suffixes numériques des techs sont donc **convertis en chiffres romains**
  (`_roman_value`), sauf la chaîne volontaire `randputf-prologue-1/2` dont les
  paliers 1→2 sont contigus.

Résultat : ~180 techs / ~200 recettes par seed, dont des techs de contenu
(belts, inserters, chests, modules, robots, trains, isotopes…).

### 9.7 Garantie de compagnons

Certains items ne sont **jouables que relativement à un autre** : un robot
(logistic/construction) est du contenu **mort** sans son roboport, un premier
solaire sans accumulateur provoque un blackout la nuit (§10). Sans garantie,
le balayage de couverture (§9.6) pouvait diffuser ces paires loin l'une de
l'autre, ou l'une jamais — du contenu inutilisable.

`RecursiveConfig.companions` (clé `companions`, §16) liste des **groupes** de
produits liés (défaut `[["roboport","logistic-robot","construction-robot"],
["solar-panel","accumulator"]]`). La phase récursive détecte, au fil de la
génération d'un élément (contenu **ou** bâtiment — ex. solaire), si l'item
appartient à un groupe, via `_dispatch_companions` : chaque compagnon non
encore unlocké reçoit immédiatement sa recette, puis des **techs isolées
(≤ 3, `isolate=True`) sont dispatchées juste APRÈS la tech du produit** — le
même pattern de dispatch que les munitions de véhicules (§12.1). Résultat :
tous les membres d'un groupe restent à ±3 techs l'un de l'autre (invariant
`test_companions_proches`), jamais diffusés en profondeur. Un item d'un groupe
absent de la seed est ignoré ; un groupe entièrement absent n'ajoute rien.

### 9.8 Quantités de craft aléatoires (C1)

Optionnel (section `craft_quantity:` de la config, `enabled: false` par
défaut — chantier C1) : après l'assemblage de la seed, une **passe post-pipeline
à flux RNG dédié** (`randputF:craft_quantity:`) applique un **facteur
multiplicatif aléatoire** aux quantités d'entrée/sortie de chaque recette.

- `mode: symmetric` → un facteur par recette (toutes les lignes) ;
  `mode: asymmetric` → un facteur indépendant par ligne (plus chaotique) ;
- bornes par défaut `factor_min: 0.5` / `factor_max: 3.0`, minimum absolu
  `amount_min: 1` unité par ingrédient et par résultat ;
- **noms, étapes, ordre et structure inchangés** — et la solvabilité (§15) ne
  lit que la structure (pas les montants), donc cette passe ne peut pas casser
  les garanties : elle ne change que l'économie (plus/moins cher), pas
  l'atteignabilité.
