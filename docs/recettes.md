# La phase récursive : génération des recettes

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 9. La phase récursive

Après le starter, la génération devient récursive. Le début utilise des pourcentages pour obtenir divers éléments, mais ceux-ci servent ici de manière massive et systématique :

### 9.1 Tirages pondérés

- Chaque catégorie (bâtiments, armes, science packs, transports avancés…) dispose d'un **pourcentage d'obtention**.
- Ce pourcentage dépend du **type du bâtiment** et du **nombre total de bâtiments** déjà présents dans la partie.
- Plus la progression avance dans les recettes implémentées, plus le déblocage d'éléments supplémentaires devient possible, élargissant ainsi le pool.

### 9.2 Génération des recettes

La forme des recettes demeure simple :

1. analyser **tout ce que le joueur peut obtenir** (pool atteignable) ;
2. contrôler les **bâtiments** à disposition du joueur (leurs types, slots et directives) ;
3. générer la recette à partir d'éléments pris **aléatoirement** au sein de ces ensembles compatibles.

**Temps de craft randomisé** : le `energy_required` de chaque recette n'est pas figé à 0,5 s. Un temps de base est tiré pour chaque recette dans la liste configurable `recipes.energies` (défaut `[0.5, 1.0, 2.0]`), puis multiplié par `(1 + recipes.energy_per_ingredient × nb_d_ingrédients)` (défaut 0,25). Une recette lourde demande ainsi **proportionnellement plus de temps** qu'une recette simple, ce qui ajuste légèrement le gameplay sans compromettre la solvabilité (une durée accrue ne modifie jamais le pool atteignable).

**Équilibre production/consommation** : à chaque recette posée, le générateur suit **ce que la seed produit** et **ce qu'elle consomme** via des compteurs cumulés par item. Une cible d'équilibre `cons/prod` est tirée uniformément une seule fois par seed dans `recipes.balance_min..balance_max` (défaut `3/16..2/3`). Lorsqu'un item passe **sous la cible**, il est qualifié de « pléthore » (produit mais peu consommé) : sa consommation comme ingrédient est **récompensée** pour écouler le surplus, et sa production comme produit est **freinée** (`_pick_product`, 1 / facteur). L'inverse s'applique à un item rare. Le déséquilibre est plafonné au quota `recipes.max_overproduced_ratio` (défaut `1/3`), ce qui évite d'encourager la consommation d'un flux excessif. Par conséquent, les quantités consommées tendent vers les quantités produites (« on n'accumule pas ce qu'on ne se sert pas »), sans modifier le pool atteignable et en préservant la solvabilité (§15).

### 9.3 Déblocage sur le tas

Toutes les ressources étant plus ou moins déblocables :

- une recette peut soudainement introduire le besoin d'une ressource brute encore inconnue dans la partie, que le randomizer intègre immédiatement ;
- si une recette emploie une ressource non automatisable, la méthode pour la créer ou l'obtenir est débloquée **au même moment** ;
- si un élément supplémentaire est requis pour ce déblocage, il est réalisé **sur le tas** en fonction du type de ressource demandé. Si le joueur ne le possède pas encore, le craft correspondant est généré simultanément.

Il en résulte l'absence d'impasse possible, conjuguée à l'imprévisibilité totale du chemin.

**Claim des ateliers débloqués « sur le tas » (anti-recette-orpheline)** : lorsqu'un bâtiment de craft est débloqué pendant la génération d'un élément (via `_pick_building` → `_unlock_building`, généralement un assembleur de tier supérieur exigé par une recette récursive), il génère une recette `randputf-<bâtiment>` qui doit impérativement être **claimée par la tech de l'élément en cours de génération**. Sans cela, elle devient **orpheline** (jamais unlockée, ce qui permet au joueur de crafter le bâtiment sans jamais pouvoir le débloquer). `_generate_for_element` compare donc l'état de `unlocked_buildings` avant et après l'élément, puis ajoute tout nouveau bâtiment à `step_buildings`/`unlocks_buildings` de la tech avec déduplication et conservation de l'ordre. Ce mécanisme couvre **l'ensemble** des déblocages d'ateliers sur le tas, peu importe l'élément — aucune recette orpheline n'a été mesurée sur 200 seeds.

Les **déclencheurs hand-craft** des techs (prologue §13, ainsi que les tirages aléatoires ultérieurs parmi les techs) suivent cette même règle : l'item requis doit être **available AVANT** la tech qui le demande. Pour éviter le bug classique consistant à tirer les candidats depuis une liste de recettes **étendue après coup** par une phase postérieure (ce qui introduirait des items débloqués tardivement comme le four électrique, le réacteur nucléaire ou le silo, bloquant la tech **pour toujours** §9.3), les candidats sont calculés exclusivement à partir des **seules recettes des techs gratuites du starter** (accessibles au bootstrap). Chaque déclencheur est vérifié strictement en amont de sa tech (voir `test_craft_trigger_prologue_craftable_des_le_starter`). La quantité à hand-crafter n'est jamais un singleton trivial : chaque prologue exige un **nombre d'items** (`research_trigger` `craft-item` avec `count`) égal à **`round(2^(n + 1/4))`**, avec `n` tiré par `randint(2, 6)` (`relay_phase.py:185`). L'exposant est **fixé et calé sur la première science** (indice 1, `relay_phase.py:183`), réutilisable tel quel ; n'étant jamais un singleton, le moindre craft du bootstrap ne peut pas auto-compléter la tech. Les bornes aboutissent à 2^2.25 ≈ 5 jusqu'à 2^6.25 ≈ 76 items.

Le `craft_trigger_count` est propagé aux techs par le tech tree (`tech_tree.py:311`). Un tirage aléatoire parmi des techs plus profondes applique la même contrainte en restreignant le pool aux items des recettes déjà unlockées, à l'exclusion des produits de recettes futures.

### 9.4 Cadence garantie des pylônes

La distribution du courant (§10) s'avère vitale pour la progression : en l'absence de poteau, un générateur ne transmet rien de jouable. Afin d'éviter le pire scénario où le premier pylône n'apparaîtrait qu'en profondeur dans l'arbre, une **cadence de 3 pôles** est imposée durant la phase récursive, indépendamment du hasard :

- **3 pôles verrouillés** (`dist_marks = (8, 28, 48)` par défaut) : un premier pôle précoce (dès ~8 steps récursifs), un deuxième environ 20 steps plus loin, et un troisième environ 20 steps après.
- Chaque pôle forcé tire un **type différent** (petit, puis moyen, puis grand / substation via `_pick_element`, sans doublon avec un type déjà déployé).
- Si le starter a déjà débloqué un pylône **craftable** (électricité au bootstrap, §10), le premier jalon est **déjà satisfait** et aucun ancrage n'est forcé tant que les jalons suivants ne sont pas atteints. Un pylône posé **en patch** au sol (§6) ne compte pas : il n'est pas constructible et le joueur ne peut pas l'utiliser pour étendre son réseau (§9.6, `_has_product_recipe`).
- Les pylônes situés **au-delà** de ces 3 jalons demeurent randomisés comme de simples items ou bâtiments (§9.1), sans sur-cadence.

Ce paramétrage est modifiable dans `RecursiveConfig` (`dist_marks`, `dist_guaranteed`) via `recursive` dans les `settings` (§16).

### 9.5 Relais des ressources non-infinies

Les ressources non automatisables (arbres → `wood`, rochers → `stone`, poissons → `raw-fish`) sont obtenues dès le départ mais s'épuisent, ce qui empêche d'en faire la colonne vertébrale d'un run. Le bootstrap reposant précisément sur ces ressources rares, **les recettes du démarrage (craftables à la main, §10) DOUBLENT la quantité de leurs ingrédients environnementaux**, ce qui fait de la transition vers les recettes propres du relais un objectif économique. Exécutée **après l'ensemble des phases productrices de recettes**, la phase relais garantit leur remplacement :

1. **Scan** : chaque recette générée dont l'un des ingrédients est un item environnemental et dont le produit n'est pas environnemental est détectée.
2. **Pool gelé du début de run** : les ingrédients ainsi que le bâtiment de craft du relais sont tirés **uniquement dans l'instantané du pool pris APRÈS le starter + l'électricité, et AVANT le récursif**. Par conséquent, le relais ne dépend jamais d'un item ou d'un bâtiment débloqué uniquement en profondeur de seed (science pack, oil-refinery, AM3, etc.). Il s'utilise dès les premières recherches sans attendre 20 techs, ce qui rend la version relais du pumpjack ou de l'assembleur réellement jouable dès le début.
3. **Création du relais** : une **recette relais** est tirée pour ce produit via `_make_relay_recipe` (`relay_phase.py:79`), conservant le même résultat mais avec des ingrédients issus de ce pool gelé (patch, item fabriqué, fluide obtenu) ; les recettes ainsi produites sont regroupées sous la tech dédiée `randputf-relay-dispatch-<label>` (`relay_phase.py:126`). Le bâtiment de craft se limite à ceux de ce même instantané, interdisant tout déblocage sur le tas hors pool. Cette recette coexiste avec la recette bootstrap d'origine, qui demeure hand-craftable.
4. **Consolidation en prologue** : les recettes relais sont regroupées au sein de **techs de prologue** (`randputf-prologue-*`, §7, **≤ 5 unlocks par tech**, plafond §13), positionnées **immédiatement après les techs gratuites du starter** (une seule en cas de peu de recettes, aucune si aucune recette n'est présente).

   Elles ne constituent pas des free_researches et se débloquent par le **hand-craft** d'un item du bootstrap (§9.3). Le bootstrap demeure ainsi la voie de départ, tandis que le joueur bascule sur les versions propres et l'entrée en sciences dès la fabrication du déclencheur, sans dépendre durablement du bois, de la pierre ou du poisson.

Règles d'anti-cycle spécifiques au relais :

- interdiction des ingrédients suivants : items environnementaux, **le produit lui-même**, ainsi que les produits **déjà relayés** (selon l'ordre de création pour les relais, interdisant toute dépendance vers un relais plus ancien pour former un **DAG** par construction) ;
- les recettes relais ne peuvent **pas** utiliser un fluide comme ingrédient pour produire un **extracteur** (application de la règle items-only de §8) ;
- le scan est **relancé jusqu'à stabilisation** : une recette créée « sur le tas » lors d'un tirage (déblocage d'un bâtiment) peut elle-même consommer des ressources environnementales et justifier son propre relais.

En l'absence d'item durable disponible (cas limite d'une seed dépourvue de tout item de pool), le relais est **omis silencieusement** : la recette bootstrap constitue alors l'unique route, ce qui reste acceptable puisque la solvabilité demeure garantie.

**Conséquence sur la validation (§15)** : un relais représente une **route alternative** vers un produit et non un doublon cyclique. L'anti-cycle est donc vérifié au niveau de l'**item** (un item est jugé solvable dès qu'une seule de ses recettes l'est) et non plus par un tri topologique de Kahn appliqué aux recettes.

### 9.6 Couverture complète : le balayage de contenu

Sans cette étape supplémentaire, la récursion (§9) se limiterait aux 4 catégories fonctionnelles, au combat et à la science : une fois ces bâtiments recrutés, la boucle s'arrête (après environ 35 techs) et le reste du jeu **ne comporte aucune recette**. Exécutée **à la fin** de la récursion pondérée (`recursive_phase.py:198`, donc **avant** la chaîne fusée §14 et le relais §9.5), la phase **3bis** garantit à **chaque item restant** une recette `randputf-<item>` et une tech `randputf-content-<item>` :

- **Cibles** : tout item transportable par tapis sans recette de production, selon un ordre déterminé par la seed.
- **Coûts** : la récursion précédente ayant déjà unlocké **l'ensemble** des science packs, le coût de chaque tech de balayage repose systématiquement sur un pack déjà accessible (payé de la production à la consommation, §13).
- **Patches** : un item placé au sol (§6) conserve sa recette (`make_recipe` plutôt que `ensure_obtainable`), car « obtainable » est différent de « craftable ».
- **Exclusions** : la chaîne fusée (`processing-unit`, `low-density-structure`, `rocket-fuel`, `rocket-silo`, `rocket-part` — voir `_ROCKET_CHAIN_SWEEP_EXCLUDED`, `recursive_phase.py:73`), les armes montées rattachées à LEUR véhicule en §12 (jamais randomisées comme armes de poing), ainsi que les items de contrôle marqués par `is_virtual_item` (blueprint, planner, *remotes*, items `rail-planner` dépourvus de place_result…) ne génèrent ni recette ni patch.
- **Empilabilité** : Factorio refuse qu'une recette produise **ou** consomme plus de 1 exemplaire d'un item non-empilable (armure, arme à feu, véhicule, capsule/remote…), ce qui déclenche l'erreur de chargement « not stackable but has a max count of N ». Le générateur fixe donc l'attribut `amount` à **1** pour tout produit ou ingrédient non-stackable (`ItemDef.is_stackable`). Le `stack_size` réel du dump fait foi lorsqu'il est présent, tandis que les types déduisent la non-empilabilité (`gun`, `armor`, `item-with-entity-data`, capsules, etc., répertoriés dans `NON_STACKABLE_ITEM_TYPES`).
- **Nommage** : les identifiants se terminant par `-<nombre>` sont interprétés par Factorio comme des **paliers d'upgrade** et exigent des paliers contigus (par exemple, uranium-235 puis uranium-238 évalués comme des niveaux 235 et 238 non contigus provoquent une erreur de chargement). Les suffixes numériques des techs sont par conséquent **convertis en chiffres romains** (`_roman_value`), à l'exception de la chaîne volontaire `randputf-prologue-1/2` dont les paliers 1 et 2 sont contigus.

Le résultat produit de l'ordre de **93 techs (~58 de contenu)** et **~210 recettes** par seed (valeur mesurée), intégrant des techs de contenu (belts, inserters, chests, modules, robots, trains, isotopes, etc.).

### 9.7 Garantie de compagnons

Certains items ne sont **jouables qu'en relation avec un autre** : un robot (logistique ou de construction) est un contenu **inutilisable** sans son roboport, et un premier panneau solaire sans accumulateur engendre un blackout nocturne (§10). Sans garantie, le balayage de couverture (§9.6) risquerait de disperser ces paires ou de omettre l'une d'elles, rendant le contenu inexploitable.

La clé `companions` de `RecursiveConfig` (§16) répertorie des **groupes** de produits liés (par exemple `[["roboport","logistic-robot","construction-robot"], ["solar-panel","accumulator"]]`). Durant la génération d'un élément (qu'il s'agisse de contenu ou d'un bâtiment tel qu'un panneau solaire), la phase récursive vérifie via `_dispatch_companions` si l'item appartient à un groupe. Chaque compagnon non encore unlocké reçoit immédiatement sa recette, et des **techs isolées (≤ 3, `isolate=True`) sont distribuées juste APRÈS la tech du produit**, adoptant le même pattern de dispatch que pour les munitions de véhicules (§12.1). Par conséquent, les membres d'un groupe restent situés à ±3 techs les uns des autres, respectant l'invariant `test_companions_proches` sans dispersion en profondeur. Si un item d'un groupe est absent de la seed, il est ignoré ; si un groupe entier est absent, aucun ajout n'est effectué.

### 9.8 Quantités de craft aléatoires (C1)

Fonctionnalité optionnelle (section `craft_quantity:` de la configuration, désactivée par défaut via `enabled: false` - chantier C1) : une fois la seed assemblée, une **passe post-pipeline dotée d'un flux RNG dédié** (`randputF:craft_quantity:`) applique un **facteur multiplicatif aléatoire** aux quantités d'entrée et de sortie de chaque recette.

- `mode: symmetric` → un facteur unique par recette (toutes les lignes) ;
- `mode: asymmetric` → un facteur indépendant par ligne (générant plus de chaos) ;
- bornes par défaut définies à `factor_min: 0.5` et `factor_max: 3.0`, avec un minimum absolu `amount_min: 1` unité par ingrédient et par résultat ;
- **les noms, étapes, ordre et structure demeurent inchangés**. La solvabilité (§15) s'appuyant uniquement sur la structure et non sur les montants, cette passe ne peut altérer les garanties : elle modifie exclusivement l'économie (coûts supérieurs ou inférieurs) sans toucher à l'atteignabilité.
