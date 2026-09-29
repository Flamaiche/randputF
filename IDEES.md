# Idées et chantiers à développer (randputF)

Ce document ne contient que ce qui **reste à faire**. Tout ce qui est terminé
(ou renoncé) est retiré : il est décrit dans le README et `docs/`.

Quatre chantiers logiques :

- **A. Ressources au sol** — matières premières, carte, ravitaillement ;
- **B. Difficulté & monde** — knobs par seed, biters, évolution, pollution ;
- **C. Progression & crafts** — déblocages, paliers, fin de partie ;
- **D. Cohérence & garanties** — appariements utiles, invariants manquants.

Règles de lecture :

- une entrée **sans code** est un chantier à écrire ; une entrée marquée
  *prototypé* a déjà du code mais n'est pas branchée au pipeline ;
- une entrée **désactivée par défaut** (`enabled: false`) est écrite et testée
  mais absente d'une partie normale — la basculer fait partie du chantier ;
- **ne jamais supprimer un chantier non terminé** : c'est le contraire du tri
  historique, on ne garde que l'avenir.

**Ordre conseillé** : A1 et A2 (la carte conditionne B1, qui alimente ensuite les
quantités de craft B3), puis C (progression), puis D (cohérence).

---

## A. Ressources au sol

### A1. Randomiser les ressources non-infinies

Les ressources **non-infinies** (patches finis, environnement bois/pierre/poisson,
fluides non infinis) restent telles quelles alors que les lacs/fluides infinis sont
randomisés. Deux voies :

**(a) Les randomiser** — identité, richesse et volume finis, sans casser le
bootstrap. Facteurs multiplicatifs **aléatoires** (flux RNG dédié
`randputF:nonfinite:`) par gisement, sur la richesse totale et le rayon.

- *Prototypé et branché* : section `nonfinite:` (`enabled: false`) →
  `map_patches.apply_nonfinite_randomisation`. Invariant runtime préservé : le
  `count` d'un ITEM est réévalué via `item_field_tiles(radius, well_seed)`, le
  champ posé reste exactement le disque bruité.
- *Reste* : décider le **défaut** (`enabled: true` ou non), vérifier que le
  bootstrap tient avec les facteurs (0.4 → 2.5) sur le champ de ressources de
  départ, et couvrir les fluides non-infinis — aujourd'hui seuls les gisements
  sont factorisés.
- Tests : `tests/test_nonfinite_randomisation.py`,
  `tests/test_nonfinite_pipeline.py`.

**(b) Variante minimaliste** — bois, pierre et poisson inchangés, et le charbon
**n'apparaît plus en patch** : remplacé par moitié bois / moitié roche (le rôle de
combustible se reporte sur les deux). Change le bootstrap sans toucher aux
quantités ni aux identités des autres ressources.

> Les deux voies sont exclusives : trancher une fois le reste fait.

### A2. Gisements profilés par la difficulté

Les gisements sont réglés **en fonction du niveau de difficulté** de la seed
(les knobs B1) : difficulté haute → patches **petits**, **pauvres**,
**éloignés** ; difficulté basse → **grands**, **riches**, **proches**. Le triplet
(taille, richesse, espacement) dérive du profil de difficulté et s'applique à
**tous** les gisements — patches items, patchs fluides et lacs — pour rester
cohérent : pas de nappes riches sur une seed infernale, pas de désert minéral sur
une seed tranquille.

Attention solvabilité : même en difficulté maximale le bootstrap reste jouable —
le starter garantit des gisements minimums pour les ressources de départ (iron,
copper, coal, eau), assez grands, assez proches pour les premiers crafts. La
« rareté » pousse à l'exploration, jamais à l'impasse.

- *Prototypé mais mal orienté* : `tool/prototypes/rare_resources.py` pose la
  brique (facteurs richesse/count) mais son axe est la **distance au spawn** — à
  réorienter vers le profil B1, **non branché**.
- Dépend de B1 (knobs de difficulté).

---

## B. Difficulté & monde

### B1. Knobs de difficulté par seed

Chantier **difficulté pure** (ce n'est pas du contenu) : la seed devient un
profil de difficulté — `starting_area`, densité de nids/évolution, taux de
pollution par bâtiment, densité de falaises, biomes de départ (forêt = bootstrap
bois facile / désert = eau+bois durs). Ça colle au concept (« aléatoire contrôlé »).

**Solvabilité 100 % garantie** : la difficulté ne touche **jamais** à
l'atteignabilité — tout reste déblocable, aucune voie coupée. Elle se joue
**principalement sur le nombre de ressources nécessaires** : les quantités
requises par recette / tech / science pack, pas sur des impasses. Pas de forêt
trop pauvre en bois pendant le bootstrap environnemental.

- *Prototypé* : `tool/prototypes/difficulty_knobs.py`
  (`DifficultyProfile.to_map_settings`) ; mesures via
  `tool/audit/difficulty.py` (`compute_difficulty`, `summarize_difficulty`, exposé
  par la sous-commande `difficulty`), tests `tests/test_difficulty*.py` —
  **non branché** au pipeline.
- Reste : câbler `DifficultyProfile` → `map_patches` (patches, lac, rayons), puis
  laisser A2 dériver ses facteurs dessus.

### B2. Biters / évolution / pollution

Inchangés (assumé §11). À revisiter **via B1** : les knobs de difficulté sont la
brique naturelle pour les randomiser proprement (densité de nids, facteur
d'évolution, diffusion de pollution).

### B3. Quantités de craft (désactivé par défaut) — **un levier de difficulté**

C'est le levier le plus direct de la difficulté : **tout le reste est tiré au
hasard, lui se règle**. Aujourd'hui chaque recette garde ses quantités vanilla ;
l'idée est d'y appliquer un facteur aléatoire — une science pack peut demander
trois fois plus de plaques, une recette intermédiaire deux fois moins.

- *Écrit, testé, branché mais **inert*** : passe post-assemblage
  `tool/generator/craft_quantity.py`, flux RNG dédié, section `craft_quantity:`
  (`enabled: false`), montants jamais < `amount_min`, structure et solvabilité
  intactes (le validateur ne lit que la structure). Voir `docs/recettes.md §9.8`,
  tests `tests/test_craft_quantity{,_pipeline}.py`.
- *Reste* : c'est un **knob de difficulté**, donc à brancher sur le profil B1
  plutôt que tiré seul au hasard — un facteur 0.5–3 par recette, puis 1.5–4 sur
  une seed difficile, 0.7–1.5 sur une seed facile. Le mode `symmetric`
  (un facteur par recette) / `asymmetric` (un facteur par ligne d'ingrédient)
  existe déjà. Calibrer les bornes en mesurant le rejoueur avant de basculer :
  un facteur 4 sur une science pack peut la rendre hors de portée.

---

## C. Progression & crafts

### C1. Listes blanches / noires de la graine

Contrôle direct du contenu, en symétrie autour de la seed.

**Listes blanches du starter** — deux listes dans `config/settings.yaml`, à étendre
à `StarterConfig` (qui ne lit aujourd'hui que `ammo_count` et `inserter_chance`) :

- **`starter.inventory`** — ce que le joueur reçoit **dans son inventaire** au
  spawn, en plus du fabricateur / extracteur / combustible déduits par la chaîne.
  Aujourd'hui `_roll_starter_kit` (`starter_chain.py:522`) pioche **n'importe
  quelle** arme `is_handheld_gun` + ses munitions, et `_pick_spawn_fuel` (`:626`)
  glisse **le combustible de plus forte `fuel_value` du pool obtenu** — donc
  potentiellement `nuclear-fuel` / `uranium-fuel-cell` : des seeds au **départ
  dégénéré**. La liste restreint le tirage ; hors liste ⇒ rien n'est tiré (filtre,
  pas quota).
- **`starter.craft_tags`** — les **items dont la recette doit être débloquée dès
  le début**, parce que le joueur en a besoin avant toute automatisation.
  Vocation typique : `is_chest` / `is_storage` (stocker l'épave), `is_logistics_chest`.
  Aujourd'hui ces garanties sont des cas particuliers codés en dur —
  `_ensure_chest_craftable` (`:493`, chest tirée au hasard) et `_ensure_landfill`
  (`:480`) — le chantier est de les **fusionner en un seul parcours de liste**.
- Contraintes : un item de la liste d'inventaire doit rester craftable
  (`_ensure_kit_craftable`, `:547`), un item de la liste de craft doit avoir un
  atelier jouable au spawn (U2). Liste non satisfaite = `warning`, jamais un
  démarrage cassé. Tests visés : `tests/test_starter_chain.py`.

**Listes noires de la graine** — le pendant négatif, aujourd'hui **déclaré mais
mort** : `pools.exclude_items`, `pools.exclude_fluids`,
`pools.exclude_building_types` et `weights.building_types` /
`weights.science_packs` ne sont **lus par rien**. La seule exclusion réelle est
`RecursiveConfig.excluded_buildings`, deux entrées en dur
(`prototypes/recursive.py:36`).

- `pools.exclude_items` / `exclude_fluids` — l'item / le fluide listé n'entre
  **jamais** dans le graphe : ni ingrédient (`recipes._eligible_ingredients`), ni
  produit de récursion, ni couvert par le balayage §9.6, ni ressource de patch/lac
  (§6). Un patch ne peut pas être tiré sur un fluide exclu.
- `pools.exclude_building_types` — idem sur les bâtiments (nom ou type
  fonctionnel).
- `weights.building_types` — surcharge de `RecursiveConfig.category_weights` :
  graine « sans électricité » = `generator: 0`, graine « logistique » =
  `distribution` à 40.
- `weights.science_packs` — biais sur le tirage des packs (early game =
  `automation`/`logistics`, tardif = `military`/`chemical`) : aucun effet sur la
  solvabilité, seulement sur la forme de l'arbre.
- Contrainte : une liste noire ne doit **jamais** rendre le graphe insoluble (§15)
  — si elle retire une ressource indispensable à la chaîne fusée / électricité /
  chaleur, `warning` explicite plutôt qu'une seed cassée.

### C2. Objectif de fin de partie randomisé

La victoire est **constante** : `endgame_phase.ensure_rocket_chain`
(`tool/generator/endgame_phase.py:30`) garantit toujours `rocket-silo` +
`rocket-part` + ses 3 ingrédients, dans **une seule** tech `randputf-endgame-rocket`
; le rejoueur déclare la victoire sur
`all_techs_researched and "satellite" in items and all(VICTORY_ITEMS)`
(`tool/replay/player.py:878`). Le **contenu** est randomisé, le **but** ne l'est
pas.

Tirer l'objectif dans une **liste blanche**, annoncée dès le début
(`seed.graph.html` peut l'afficher) :

- `rocket` — lancer une fusée (défaut actuel, garantie inchangée) ;
- `rocket_n` — en lancer `n` : le silo devient une boucle, pas une finish line ;
- `research_pct` — atteindre `x` % de researched : l'arbre devient la course ;
- `rank` — atteindre la tech de rang `k` : une branche profonde plutôt que la
  fusée.

Contraintes : l'objectif ne doit **jamais** être plus strict que l'atteignabilité
garantie (§15) — `research_pct` bas et `rank` modéré par défaut. La chaîne fusée
reste **garantie même quand l'objectif n'est pas `rocket`**, sinon on perd la
définition de victoire du rejoueur. Coût mod-side : exposer le statut de victoire
au joueur dans `data-final-fixes.lua` + `control.lua`.

### C3. Paliers d'équipement militaire dissociés (armure / arme / véhicule)

L'axe militaire est tenu en **trois pièces sans doctrine commune** :

- **arme de poing** (`is_handheld_gun`) : garantie d'une arme par tech, munition
  calée sur elle (§11) — le mieux tenu des trois ;
- **véhicule armé** (`recursive.armed_vehicles`, §12.1) : **purement décoratif** —
  les armes montées sont exclues du pool et **clonées** par le mod (« AUCUNE
  recette/unlock n'est généré pour ces armes »). Un tank peut entrer dans le graphe
  sans qu'aucune de ses armes n'ait de place, et son armement n'est conditionné
  par aucune tech ;
- **armure** (`is_armor`) : **aucune garantie, aucun traitement** — « raffinage
  usage en vue (audit) » seulement (`docs/tags.md:271`). Sa recette est randputée
  comme celle d'un item ordinaire, mais sa **`protection` reste celle de vanilla**,
  cumulative et jamais tirée : une graine peut offrir un `heavy-armor` à 80 % dès
  la première tech, ou aucune armure jouable. C'est le dernier pan du jeu où la
  **valeur vanilla** de l'objet compte encore et n'est pas randputée.

Idée — **trois courbes de paliers indépendantes et espacées** :

1. chaque famille (armure / arme / véhicule) est une **timeline séparée**, qui
   tire son propre ordre de paliers et son propre **espacement** : le palier N est
   garanti unlocké **au moins K techs après** le palier N−1 (K configurable, ~3-5)
   — sinon une famille entière déboule dans un seul bloc de techs ;
2. les trois timelines sont **dissociées** : rien n'impose que l'armure et les
   armes montées arrivent dans la même bande de techs. Un tirage par seed de
   l'**orientation relative** des trois courbes (« run centré arme », « run centré
   blindé », « run centré véhicules ») supprime la tech unique où tout le militaire
   tombe d'un coup ;
3. la **valeur** est randputée avec le calendrier : `protection` réécrite au
   data-stage (`mod/data-updates.lua`) en valeurs tirées par seed mais **monotones**
   sur la famille (le palier suivant protège toujours plus) — la progression reste
   lisible, l'ordre ne l'est plus.

Généralisation naturelle de **D1 (pairing)** à l'axe militaire :
`armure → protection`, `arme → munition`, `véhicule → arme montée` sont trois
paires du même type.

### C4. Extracteur à entrée fluide

Un extracteur peut exiger un **liquide en entrée** pour fonctionner (recette qui
existe dans le jeu ; typiquement les **foreuses minières électriques**). Aujourd'hui
§8 interdit tout fluide dans la **recette de craft** d'un extracteur — mais le cas
serait l'inverse : ce serait le **FONCTIONNEMENT** qui demanderait un apport
liquide.

- Besoin : un **nouveau tag** dans le dump vanilla (`requires_liquid` /
  extracteur à input fluide) pour détecter ces entités.
- Raisonnement : un extracteur qui boit un fluide est un **consommateur** de la
  ressource-liquide — le déblocage juste-au-besoin doit tenir compte de sa propre
  source (une source inexistante = extracteur mort).
- Voir aussi la garantie « extracteur avant besoin » §7 et l'anti-boucle §8.

---

## D. Cohérence & garanties

### D1. Détecter automatiquement les dépendances entre objets

Certains objets n'ont aucun sens tout seuls : un roboport sans robot, une arme
sans munition, un train sans rail. Si le joueur débloque l'un et pas l'autre,
l'autre arrivera plus tard — le balayage de couverture (§9.6) donne une tech à
**tout** item restant, donc rien n'est perdu : c'est **différé**, pas mort.
L'objet devient un objectif, pas un déchet.

Le remède existe déjà, mais il est **écrit à la main** : quelques paires sont
listées en dur (`RecursiveConfig.companions` : `roboport` + robots de logistique +
robots de construction, `solar-panel` + `accumulator`), plus les armes (§11, une
arme arrive toujours avec ses munitions) et les véhicules (§12.1). Tout objet qui
n'est pas dans ces listes peut donc arriver seul.

**Le chantier : supprimer la liste et la remplacer par une détection.**

1. **Trouver automatiquement, depuis le dump vanilla, quels objets sont
   dépendants les uns des autres.** C'est le point dur : il faut un signal dans le
   dump, donc le travail commence probablement dans **`exporter/control.lua`**,
   qui est le seul endroit où le jeu peut nous dire ce qu'il sait. Pistes : une
   entité qui ne sert qu'à étayer une autre, un objet dont la recette vanilla
   ne consomme que le second, une catégorie de fabrication ou un tag commun.
2. **Une fois la dépendance connue, garder l'aléatoire** : quand le joueur reçoit
   un objet, **X % de chance** (50 % ?) que sa dépendance parte dans la **même
   tech**. Pas de règle fixe — on garde le hasard du randomizer. Dans le cas
   contraire, la dépendance n'est pas perdue (§9.6), elle arrive simplement plus
   tard : on évite le « je l'ai eu, je sais pas à quoi ça sert » en le repoussant,
   pas en le supprimant.

Le résultat doit être **vérifiable** comme le reste : un audit qui liste, par
partie, les objets débloqués et leurs dépendances manquantes.

C'est un renfort de cohérence, pas une brique de contenu.

### D2. Garantie « bâtiment terminal réellement terminal »

Les bâtiments terminaux (`lab`, `rocket-silo`, générateurs) sont **exemptés** de U1
parce que leur usage est leur rôle moteur — vérifié « via le graphe ». Cette
vérification est la partie la moins testée du dispositif.

- Reste : transformer la vérification en **invariant** (le lab du starter a bien sa
  recette, le silo est atteignable), pas en commentaire.

### D3. Centraliser les tags et listes en dur

La logique « ceci est un terminal / ceci est interdit au starter / ceci est une
arme montée » est aujourd'hui dispersée sur une dizaine d'emplacements, sous
forme de `frozenset` littéraux, de `default_factory` et de **constantes qui ne se
parlent pas**. Trois notions d'exclusion cohabitent, avec trois valeurs
différentes pour le même concept :

| ensemble | valeur | emplacement |
|---|---|---|
| interdits au starter | 8 noms | `starter_chain._EXCLUDED_BUILDINGS` (`:356`) |
| exclus de la récursion | 2 noms | `RecursiveConfig.excluded_buildings` (`prototypes/recursive.py:36`) |
| terminaux (usage moteur) | `lab`, `rocket-silo` | `usage.terminal_buildings` (config) |
| terminaux, **audit** | + `steam-generator` | `TERMINALS` (`tools/audit_usage.py:18`) |
| terminaux, **défaut du prototype** | `lab`, `rocket-silo` | `UsageConfig` (`prototypes/usage.py:37`) |

L'audit et le générateur ne voient donc **pas le même** ensemble de terminaux :
`steam-generator` est terminal pour l'audit, pas pour la passe. Même problème sur
les autres listes en dur : `ENVIRONMENTAL_ITEMS` / `VALID_RECIPE_CATEGORIES` /
`ROCKET_CHAIN` / `VEHICLE_GUNS` (`common/db.py`), `RAIL_TYPES` /
`_VIRTUAL_ITEM_TYPES` (`parsers/vanilla.py`), `FLUID_RECIPE_CATEGORIES`
(`recipes.py:45`), `_STARTER_TRANSFORMERS` et `_ENDGAME_EXCLUDED`
(`easeup_phase.py:47`) — plus des littéraux isolés sans constante
(`_SPAWN_FUEL_COUNT = 50`, `"landfill"`, `"wood"` dans `starter_chain.py`).

**Objectif à deux étages** :

1. **une source unique par ensemble** — un module dédié (`tool/common/tagsets.py`)
   regroupant les ensembles nommés, référencés par `docs/tags.md §14` qui en
   devient l'index (il les inventorie déjà) ;
2. **ce qui est un knob de tuning part en config**, pas en constante de module :
   quantité de spawn, terminaux U1, exclusions de bâtiments. C'est la condition
   pour pouvoir les changer sans toucher au code — c'est le but du chantier.

**Règle à adopter** : un ensemble en dur n'est acceptable que si **aucune
capacité du dump** ne peut le dériver ; dans ce cas il porte un commentaire
expliquant pourquoi (comme `VEHICLE_GUNS` aujourd'hui), sinon il devient un tag.
Corollaire côté exporter : certains tags ne sont pas dérivables parce que le dump ne
les expose pas — `is_mounted_gun` (« can be used by hand ») est déjà référencé
comme **« gap IDEES »** dans `docs/tags.md` §3 et §14 sans entrée correspondante.
Ajouter ce signal à `exporter/control.lua` ferme le gap et transforme
`VEHICLE_GUNS` et la constante de test `ARMED_VEHICLES` en tags dérivés.

