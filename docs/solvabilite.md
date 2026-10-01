# Solvabilité : règles et vérification

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 10ter. Vérificateur en profondeur (bootstrap sûr)

Les techs **gratuites** du starter promettent des crafts disponibles dès le
spawn (extracteurs, transports, lab, premier générateur électrique…). Mais les
phases profondes (§9 récursif, §9.6 balayage de couverture, transformateurs
fixes) **regénèrent** les recettes de certains de ces produits : la chaîne de
production d'un craft starter peut alors finir par exiger l'**électricité**
qu'un début de partie ne peut pas encore fournir. Cas réel relevé par le
joueur (seed 13) : la turbine (premier générateur) exigeait `landfill`, qui
exige `pipe`, craftée dans un **assembling-machine-2 électrique** (et plus
profondément un fluide de patch pompé par pumpjack électrique) → pour avoir
l'électricité il fallait … déjà l'électricité.

Une passe de clôture historique (`bootstrap_guard`, après toutes les phases
productrices de recettes, avant l'arbre technologique) construisait le **graphe
de production complet** et **cassait** les cycles inaccessibles sans électricité
(ou de rendement net ≤ 0) en réécrivant / ajoutant des recettes de secours.

**Ce n'est plus le mécanisme actuel** : le redesign « bootstrap inline »
(plan de conception, non publié) a remplacé la passe de rattrapage par une
contrainte **à la création**. L'**oracle early**
(`tool/generator/early_oracle.py`) maintient le **watershed « obtenable avant
le réseau »** pendant les phases starter + électricité :

- initialisé depuis les sources dès le départ : environnement (bois/pierre/
  poisson), patchs items (minables par foreuse non-électrique) et lacs
  (fluides pompés par pompe offshore, sans électricité) ;
- le kit du spawn est **exclu** : stock fini de crash, pas une matière première
  re-fabriquable ;
- chaque recette créée pendant le mode « early » étend le watershed si son
  atelier est non-électrique (handcraft / burner).

Quand le mode « early » est actif, `recipes._make_recipe` tire les ingrédients
**uniquement dans ce watershed** et n'accepte que des ateliers non-électriques
→ toute recette promise du starter est jouable pré-électricité **par
construction**. Le cas seed 13 (turbine → landfill → pipe → atelier
électrique) ne peut plus se produire. L'atteignabilité pré-élec est garantie ;
seul le critère historique « rendement net ≤ 0 » n'est plus qu'un diagnostic.

**Ce qui reste de `bootstrap_guard`** : le **diagnostic** `find_cycles`
(`tool/generator/bootstrap_guard.py`), qui repère les composantes fortement
connexes (cycles produit → ingrédients produits, self-loops compris) et classe
chacune (atteignable sans électricité ? rendement net ?). Il est consommé par
les tests (`tests/test_bootstrap_guard.py`,
`tests/test_pipeline_invariants.py`) pour auditer des seeds, **pas par le
pipeline de génération**.

## 15ter. Rejoueur « fake player » (vérification par simulation)

Les invariants §15 raisonnent sur l'ORDRE (unlock avant usage) et les CYCLES —
ils ne disent rien d'un parcours réel : « cette recette est unlockée avant
celle-là » n'implique pas « le joueur peut la fabriquer à ce moment-là ».
Le rejoueur (`tool/replay/player.py`, balayage `tools/audit_playthrough.py`)
**simule une partie** sur la seed finale, comme un joueur qui la découvre :

- **départ** : kit spawn (`starter_kit`) + loot de l'épave (`wreck`) +
  environnement (bois/pierre/poisson, récolte à la main) ;
- **sources brutes** : chaque patch/lac n'est obtenu que si l'extracteur qui
  le mine est lui-même obtenable ET opérationnel (foreuse → combustible ou
  électricité ; pumpjack → électricité ; pompe offshore → énergie void) —
  mapping C3 de `seed["extractor_timing"]` ;
- **électricité** : disponible dès qu'un générateur (`produces_electricity`)
  obtenable PEUT TOURNER — fluide de lac assigné en entrée
  (`building_fluid_assignments`) s'il en consomme, combustible s'il brûle,
  solaire/hors-réseau autonome — et qu'un pylône est obtenable ;
- **ateliers** : une recette ne tourne que si son `crafted_in` est obtenable
  et alimenté (électricité / combustible / chaîne chaleur source+transport
  pour les bâtiments en énergie `heat`) ; sans `crafted_in` → craft à la main ;
- **recherche** : les techs gratuites (`free_researches`) sont déjà
  recherchées ; chaque tech suivante est recherchée dès que son coût (packs)
  ou son `craft_trigger` (prologue §7) est **produisible à ce moment** ;
- **victoire** : chaîne fusée atteignable en fin de parcours (silo +
  processing-unit + low-density-structure + rocket-fuel, §14).

C'est un audit EXTERNE (n'accède qu'à la seed finale) : ne modifie jamais la
génération. Le balayage `tools/audit_playthrough.py <lo> <hi>` affiche le taux
de victoires et, pour chaque échec, la **première tech bloquante** + un bordereau
d'explication multi-étapes (l'item manquant, remonté jusqu'à sa source).

**Résultat mesuré (balayage 0-1500)** : **1501 victoires / 0 échec** — au-delà du
modèle d'extraction PHYSIQUE (data-updates.lua) et des corrections générateur
D4ter :

- tout patch item est en `basic-solid` et **ramassable à la main** au starter
  (ressource finie, façon épave) ; une foreuse le rend infini ensuite ; un patch
  fluide exige un pumpjack (électricité) ; un lac se pompe par pompe offshore
  (void) — le rejoueur ajoute les patchs item aux buckets initiaux
  (`item_patch_resources`), il n'exige pas de foreuse pour le premier commerce ;
- **mineur non-électrique au starter** : quand la seed tire
  electric-mining-drill pour ses patchs item, la recette du foreuse burner
  (burner-mining-drill) naît dans le GRAPHE du starter (craft à la main, tech
  gratuite) — le joueur se le fabrique, pas d'exemplaire gratuit ni de remplaçant
  au kit. Son pool d'ingrédients interdit tout item qui dépend (même
  transitivement) d'une mine : sinon cycle (foreuse ← four-pierre ← plastic-bar
  <patch> ← foreuse), et rien n'est minable avant le réseau alors que les
  recettes gratuites peuvent consommer des patchs item ;
- **fin de l'auto-hébergement** : aucune recette n'est hébergée dans un
  bâtiment dont l'item EST son produit (`randputf-stone-furnace` dans
  stone-furnace) — cercle atelier=produit mort (garde dans `recipes._pick_building`
  et `usage_pass` U1/U2) ;
- **gardien pré-élec** : une recette unlockée par une tech gratuite ne change
  JAMAIS d'atelier pour un bâtiment électrique (usage_pass) — la promesse
  §10ter (recettes du starter jouables pré-électricité) est préservée.

Corrections ajoutées sur 0-500 (détail dans `docs/DEVIANCES.md`) :

- **cycle d'hébergement MUTUEL** (seed 255) : U2 ne ré-héberge plus une recette
  vers un bâtiment qui dépend déjà (fermeture transitive) de son produit
  (`_hosting_cycle` branché U1/U2) — `randputf-assembling-machine-2` ⇄
  `randputf-steel-furnace` tournait en rond ;
- **fabrication d'atelier SANS fluide** (seed 426) : un item de bâtiment
  (atelier OU extracteur) se fabrique uniquement avec des items
  (`recipes._is_building_item_recipe`) — une recette `randputf-chemical-plant`
  à ingrédients fluides condamnait les science packs (steps 11-12) derrière
  l'oil-refinery (unlock 45) ;
- **cycle d'hébergement LONG** (seed 1043) : `_hosting_cycle` parcourt le
  graphe FORWARD (ce que l'atelier cible exige, jusqu'au produit) au lieu du
  sens inverse — un rehome U1 refermait une boucle à 4 maillons
  `AM2→AM3→rocket-silo→oil-refinery→AM2` (pistol dans AM-2, atelier intraçable
  → utility-science-pack impayable en tech 18).

Premier passage à 99/201 ? Le rejoueur liait chaque ressource à SON extracteur
mappé (foreuse électrique pour tel patch) → faux négatifs massifs. Passé en
capacité physique + extracteurs du spawn gardés au starter (D4bis) : 178/201
identique sur annexe et C3. Puis D4ter : 201/201 sur 0-200, niveau porté à
**1001/1001 sur 0-1000** puis **1501/1501 sur 0-1500** par les corrections
ci-dessus — aucune graine ne se fige au spawn ni au fil de l'arbre.

## 15. Règles de solvabilité

Cinq invariants majeurs, plus deux vérifications complémentaires, tous vérifiés
par le tool externe avant validation d'une seed (`pipeline_validator.py`) :

1. **Anti-cycle** : aucun maillon ne peut dépendre de sa propre production.

   Toute entrée auxiliaire d'un bâtiment provient d'une branche déjà valide ;
   les tuyaux d'un fluide requis peuvent être faits de ce fluide ou d'une
   autre ressource, jamais de la ressource qui en a besoin (règle des tuyaux,
   §8).

   La vérification se fait au niveau **item** par point fixe
   (`_detect_unreachable_products`) : un item est solvable dès que **l'une**
   de ses recettes l'est. Les recettes relais (§9.5) sont des routes
   alternatives, pas des doubles-arêtes cycliques : un aller-retour
   `relais-A → bootstrap-B → relais-A` n'est pas une boucle bloquante tant
   que chaque item de la paire reste solvable par une autre route.
2. **Progressivité** : chaque nouveau maillon (recette, bâtiment, combustible,
   ressource) n'est ajouté que si ses prérequis sont satisfaits par le pool
   atteignable — ou rendus satisfaits immédiatement par déblocage sur le tas
   (§9.5), lui-même soumis à la règle 1.
3. **Complétude** : la chaîne générée mène nécessairement à tous les
   composants requis par le lancement de fusée (les 3 ingrédients de
   `rocket-part` ET le rocket-silo générés et unlockés, §14) ; les coûts de
   recherche en matériaux sont couverts par la progression (chaque pack de
   coût possède une recette unlockée avant la tech qui le consomme, §13).
4. **Unlock unique** : toute recette de la seed est déblocable par **au moins
   une** tech et **une seule**. Les phases peuvent réclamer plusieurs fois la
   même `randputf-<item>` (une recette de bâtiment d'abord créée comme produit
   d'un autre bâtiment, un item de fusée, ...) : au montage de l'arbre, seule
   la **première** tech qui la revendique compte — l'invariant est garanti par
   construction, pas par chance (§13).
5. **Packs sans ressource brute** : aucune recette de science pack ne consomme
   une ressource brute (patch au sol, item environnemental récolté à la main,
   fluide d'extraction — infinis ou non, §3/§13). Vérifié en fin de pipeline
   sur les recettes de la graine (`_check_packs_no_raw`), en plus de
   l'exclusion appliquée au tirage par la génération.
6. **Cohérence tech-recettes** (warning) : chaque recette créée par le pipeline
   apparaît dans les effects d'exactement UNE tech — pas de recette orpheline
   (jamais débloquée) et pas de double déblocage. Les orphelins émettent un
   warning plutôt qu'une erreur (certaines recettes créées « sur le tas » sont
   disponibles dès le début sans unlock explicite).
7. **Coûts obtainables** : les matériaux de recherche de chaque tech payante
   doivent être produibles par le joueur au moment de sa place dans l'arbre.
   Simulation de la progression : on parcourt les techs dans l'ordre, on ajoute
   les produits débloqués au pool, et on vérifie que chaque coût est couvert.

Une seed qui viole l'un de ces invariants est rejetée et régénérée par le tool,
jamais livrée au joueur.
