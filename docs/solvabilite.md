# Solvabilité : vérifications

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## Vérificateur en profondeur (bootstrap sûr)

Les techs **gratuites** du starter promettent des crafts disponibles dès le
spawn (extracteurs, transports, lab, premier générateur électrique…). Mais les
phases profondes ([recettes.md](recettes.md#la-phase-récursive) récursif, [recettes.md](recettes.md#couverture-complète--le-balayage-de-contenu) balayage de couverture, transformateurs
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

## Rejoueur « fake player » (vérification par simulation)

Les invariants ([invariants.md](invariants.md#règles-de-solvabilité)) raisonnent sur l'ORDRE (unlock avant usage) et les CYCLES —
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
  ou son `craft_trigger` (prologue [starter.md](starter.md#la-phase-de-démarrage)) est **produisible à ce moment** ;
- **victoire** : chaîne fusée atteignable en fin de parcours (silo +
  processing-unit + low-density-structure + rocket-fuel, [tech.md](tech.md#fin-de-partie)).

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
  [solvabilite.md](solvabilite.md#vérificateur-en-profondeur-bootstrap-sûr) (recettes du starter jouables pré-électricité) est préservée.

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

## Règles de solvabilité

Les cinq invariants majeurs (et les deux vérifications complémentaires) que le
générateur doit respecter sont **énoncés une seule fois** dans
[invariants.md](invariants.md#règles-de-solvabilité). Ce document-ci décrit comment on les
**vérifie** : oracle early ([solvabilite.md](solvabilite.md#vérificateur-en-profondeur-bootstrap-sûr)) et rejoueur « fake player » ([solvabilite.md](solvabilite.md#rejoueur--fake-player--vérification-par-simulation)).

## Lectures associées

- **Parent** : [docs/README.md](README.md)
- **Enfants** : [invariants.md](invariants.md) — les invariants énoncés ;
  [nomenclature-rejoueur.md](nomenclature-rejoueur.md) — vocabulaire seed ↔ rejoueur
- **Concepts liés** : [pipeline.md](pipeline.md#invariants-du-pipeline) (invariants du pipeline) ;
  [tech.md](tech.md#larbre-technologique) ; [recettes.md](recettes.md#la-phase-récursive) ;
  [witness.md](witness.md#relation-avec-le-déterminisme-de-la-seed) (déterminisme de la seed) ;
  [DEVIANCES.md](DEVIANCES.md) (cas réels corrigés).
