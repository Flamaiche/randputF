# VanillaDB — base de données normalisée du contenu vanilla

## 1. Rôle du module et position dans le pipeline

Le module `tool/common/db.py` centralise la **base de données normalisée**, source de vérité pour toutes les phases du générateur. Il convertit le `vanilla_dump.json` en une structure interne, `VanillaDB`, exploitée par le pipeline.

Définie dans `tool/parsers/vanilla.py` (`load_db_from_dump`) et appelée par `tool/generator/pipeline.py`, la fonction `load_db_from_dump()` initialise l'objet `VanillaDB` à partir du dump : items, fluides, bâtiments taggés par capacités, recettes, puis pools dérivés. Avant le parse, trois enrichissements **par les faits** (le dump ne porte que du brut, aucun calculLua) :

* `inject_pumped_fluids(dump)` — résout le `pumped_fluid` des extracteurs d'eau (§6.5) ;
* `science_pack_names(dump)` — les packs de science, unis par faits (coûts de techs + lab_inputs) ;
* `rocket_chain_from_dump(dump)` — la chaîne de lancement (§6.7), stockée dans `VanillaDB.rocket_chain`.

Cette base est ensuite transmise à `randputf` pour la génération.

```
# Position dans le pipeline
# ──────────────────────────────────────
1. Objet et périmètre (pipeline.md:13‑21)
2. Les trois fonctions d'orchestration (pipeline.py:23‑32)
3. Chronologie des jalons (pipeline.md:39‑50)
```

## 2. Format d'entrée : `vanilla_dump.json` et métadonnées

Le `vanilla_dump.json` (exporter randputf **0.1.5**, jeu 2.1.24) fournit les données brutes exploitées par `VanillaDB` — du brut factuel uniquement, aucune interprétation côté Lua :

* **`meta`** – métadonnées : `game_version` (ex. « 2.1.24 ») ; `game_version_numeric` est absente, d'où `seed_value = 0` par défaut (§7.1).
* **`items`** / **`fluids`** – objets solides et fluides, filtrés par `is_junk` (§3).
* **`entities`** – entités du monde, filtrées par `is_junk` puis taggées par capacités (`tag_parse_entity`). Chacune peut porter `tile_buildability_rules` (règles de placement : `required_tiles` / `colliding_tiles` / `remove_on_collision`, voir §6.5).
* **`recipes`** – recettes brutes avec `name`, `category`, `ingredients`, `products` et `energy`.
* **`technologies`** – arbre de recherche (prérequis, effets, `unit`).
* **`inventory`** – inventaire complet A→Z du jeu : 39 tables par type de prototype (`item`, `entity`, `fluid`, `tile`, `recipe`, `technology`, …).
* **`tiles`** – 52 tuiles, chacune avec ses `collision_layers` et éventuellement son `fluid` (ex. `water`).

La `seed_value` est lue depuis `meta.game_version_numeric` (défaut 0 si absente, §7.1) et stockée dans `VanillaDB.seed_value` pour initialiser les flux aléatoires du pipeline (§1).

## 3. Schéma des données

### 3.1 `ItemDef` (item solide)

```python
@dataclass(frozen=True)
class ItemDef:
    name: str
    subgroup: str = ""
    place_result: str | None = None
    fuel_value: float | None = None
    is_ammo: bool = False
    is_gun: bool = False
    is_armor: bool = False
    is_science_pack: bool = False
    is_tool: bool = False
    ammo_category: str = ""
    item_type: str = ""
    fuel_categories: tuple[str, ...] = ()
    fuel_category: str = ""
    burnt_result: str | None = None
    stack_size: int = 0
    is_environmental: bool = False
    is_virtual_item: bool = False
    is_module: bool = False
    is_capsule_throwable: bool = False
```

Champs clés :
- **Identification** – `name` et `subgroup`.
- **Placement** – `place_result` (où l'item est posé).
- **Combustion** – `fuel_value` (valeur énergétique), `fuel_categories` (liste complète, Factorio ≥ 2.1.20) et `fuel_category` (première catégorie, repli).
- **Tags** – `is_environmental`, `is_virtual_item`, `is_module`, `is_capsule_throwable`.
- **Science** – `is_science_pack` et `is_tool` : dérivés des FAITS via `science_pack_names()` (coûts `unit.ingredients` des techs ∪ `lab_inputs` des labs), pas du `subgroup` (§6.4).
- **Stack** – `stack_size` (définit l'empilement).
- **Catégories** – `item_type`, `fuel_category`, `subgroup`.

### 3.2 `FluidDef` (fluide)

```python
@dataclass(frozen=True)
class FluidDef:
    name: str
    fuel_value: float | None = None
```

Un fluide est défini uniquement par son nom.

### 3.3 `BuildingDef` (bâtiment)

```python
@dataclass(frozen=True)
class BuildingDef:
    name: str
    entity_type: str
    medium: str = ""
    is_research: bool = False
    is_crafter: bool = False
    is_generator: bool = False
    is_distribution: bool = False
    is_extractor: bool = False
    is_other: bool = False
    has_crafting: bool = False
    has_mining: bool = False
    has_pumping: bool = False
    has_fluid_input: bool = False
    has_fluid_output: bool = False
    has_fuel: bool = False
    has_target_temperature: bool = False
    has_rocket_parts: bool = False
    crafting_categories: tuple[str, ...] = ()
    resource_categories: tuple[str, ...] = ()
    energy_type: str = "burner"
    fuel_categories: tuple[str, ...] = ()
    item_input_slots: int = 0
    fluid_inputs: int = 0
    fluid_outputs: int = 0
    item_output_slots: int = 0
    # pumped_fluid : fluide pompé par un extracteur d'eau — RÉSOLU côté
    # Python (inject_pumped_fluids, §6.5) ; le dump 0.1.5 ne le porte plus.
    pumped_fluid: str | None = None
    produces_heat: bool = False
    produces_electricity: bool = False
    fuel_residues: frozenset[str] = frozenset()
    directives: dict = field(default_factory=dict)
    has_hidden_recipe: bool = False
    is_power_pole: bool = False
    is_beacon: bool = False
    is_accumulator: bool = False
    is_energy_storage: bool = False
    is_offgrid: bool = False
    consumes_electricity: bool = False
    is_water_extractor: bool = False
    is_fluid_extractor: bool = False
    is_ground_extractor: bool = False
    is_belt: bool = False
    is_underground_belt: bool = False
    is_splitter: bool = False
    is_inserter: bool = False
    is_pipe: bool = False
    is_pipe_to_ground: bool = False
    is_fluid_transport: bool = False
    is_chest: bool = False
    is_logistics_chest: bool = False
    is_storage: bool = False
    is_roboport: bool = False
    is_robot: bool = False
    # --- Tags §3 : train & véhicules (docs/tags.md §3) ---
    is_rail: bool = False             # voie (droite/courbe/surélevée)
    is_rail_support: bool = False     # rampes/piliers (rail-support)
    is_rail_signal: bool = False      # signal/chain
    is_train_stop: bool = False       # gare
    is_locomotive: bool = False       # locomotive
    is_wagon: bool = False            # wagon (cargo/fluide/artillerie)
    is_vehicle: bool = False          # tous véhicules
    is_spider_vehicle: bool = False   # spider (spidertron)
    # --- Tags §4 : production spécialisée (docs/tags.md §4) ---
    is_furnace: bool = False          # four (smelting)
    is_assembler: bool = False        # machine d'assemblage
    is_chemical_plant: bool = False   # usine chimique
    is_refinery: bool = False         # raffinerie (oil-processing)
    is_centrifuge: bool = False       # centrifugeuse
    is_rocket_parts_crafter: bool = False  # silo à fusée
    is_boiler: bool = False
    is_heat_exchanger: bool = False
    is_solar: bool = False
    is_reactor: bool = False
    is_heat_transport: bool = False
    is_heat_source: bool = False
    is_heat_sink: bool = False
    is_burner_generator: bool = False
    is_mining_drill: bool = False
    is_pumpjack: bool = False
    is_offshore_pump: bool = False
    is_well_pump: bool = False
    is_turret: bool = False
    is_gun_turret: bool = False
    is_laser_turret: bool = False
    is_flame_turret: bool = False
    is_artillery: bool = False
    is_defensive_wall: bool = False
    is_landmine: bool = False
    is_combat_robot: bool = False
    is_circuit_combinator: bool = False
    is_constant_combinator: bool = False
    is_circuit_io: bool = False
    is_rgb_lamp: bool = False
    is_radar: bool = False
```

#### 3.3.1 Pools dérivés

| Pool | Méthode | Description |
|------|---------|-------------|
| `beltable_items` | `VanillaDB.beltable_items()` | Items solides posables sur tapis, HORS outils (`not is_tool`), triés par nom. |
| `pipable_fluids` | `VanillaDB.pipable_fluids()` | TOUS les fluides du dump, triés par nom. |
| `extraction_only_fluids` | `VanillaDB.extraction_only_fluids` | Fluides sans recette de production directe (eau, pétrole brut, vapeur) ; barillage exclu (cycle fluide → baril → fluide). |
| `raw_resources` | `VanillaDB.raw_resources(patch_resources)` | Patches posés + `ENVIRONMENTAL_ITEMS` + `extraction_only_fluids`. |
| `fuel_items` | `VanillaDB.fuel_items()` | Items combustibles triés (`fuel_value` non nul). |
| `fuels_for(b)` | méthode | Combustibles compatibles par bâtiment. |
| `fuel_residues(b)` | méthode | Résidus de combustion. |
| `fuel_item_flow(b)` | méthode | Flux normalisé : combustible vers résidu. |
| `has_fuel_item_flow(b)` | méthode | Vrai si le bâtiment produit un résidu item. |
| `fuel_fluids()` | méthode | Fluides combustibles triés. |
| `buildings_with_tag(tag)` | méthode | Bâtiments possédant le tag. |
| `extractors_for_medium(medium)` | méthode | Extracteurs par milieu. |

## 4. Prédicats de détection par capacités

### 4.1 `has_hidden_recipe(b: BuildingDef) -> bool`

Détecte les bâtiments à recette cachée via leurs capacités intrinsèques :

1. Possède un tag de production (`is_research`, `is_crafter`, `is_generator`, `is_extractor`).
2. Possède une entrée (item, fluide, combustible) et une sortie (item, fluide, résidu).
3. Ne possède pas de catégorie de crafting valide.

```python
def has_hidden_recipe(b: "BuildingDef") -> bool:
    if not any(getattr(b, tag, False) for tag in PRODUCING_TAGS):
        return False
    has_atelier_category = any(
        c in VALID_RECIPE_CATEGORIES for c in getattr(b, "crafting_categories", ())
    )
    if has_atelier_category:
        return False
    has_input = (
        getattr(b, "item_input_slots", 0) > 0
        or getattr(b, "fluid_inputs", 0) > 0
        or bool(getattr(b, "fuel_categories", ()))
    )
    has_output = (
        getattr(b, "item_output_slots", 0) > 0
        or getattr(b, "fluid_outputs", 0) > 0
        or bool(getattr(b, "fuel_residues", ()))
    )
    return has_input and has_output
```

### 4.2 `is_fixed_fluid_crafter(b: BuildingDef) -> bool`

Détecte les générateurs de recettes fluide → fluide (ex: boiler, heat-exchanger).

```python
def is_fixed_fluid_crafter(b: "BuildingDef") -> bool:
    return (
        has_hidden_recipe(b)
        and getattr(b, "is_crafter", False)
        and getattr(b, "fluid_inputs", 0) > 0
        and getattr(b, "fluid_outputs", 0) > 0
    )
```

### 4.3 `is_fixed_crafter(b: BuildingDef) -> bool`

Détecte les bâtiments à recette fixe pouvant recevoir une recette randomisée : atelier `is_crafter` avec sortie (fluide ou item), OU bâtiment à résidu de combustible (le réacteur, item → résidu item).

```python
def is_fixed_crafter(b: "BuildingDef") -> bool:
    return (
        has_hidden_recipe(b)
        and (
            (getattr(b, "is_crafter", False) and (
                getattr(b, "fluid_outputs", 0) > 0 or getattr(b, "item_output_slots", 0) > 0))
            or bool(getattr(b, "fuel_residues", ()))
        )
    )
```

## 5. Tags orthogonaux cumulables et catégories

### 5.1 Tags de rôle fonctionnel
- `is_research` : Lab / pack de recherche.
- `is_crafter` : Atelier (sortie item/fluide).
- `is_generator` : Production d'énergie.
- `is_distribution` : Infrastructure électrique.
- `is_extractor` : Extraction de ressources.
- `is_other` : Aucune capacité reconnue.

### 5.2 Tags énergétiques & chaleur
- `is_boiler` : Type `boiler`, énergie `burner`.
- `is_heat_exchanger` : Type `boiler`, énergie `heat`.
- `is_solar` : Panneau solaire.
- `is_reactor` : Réacteur nucléaire.
- `is_heat_transport` : Pipe de chaleur.
- `is_heat_sink` : Consommateur de chaleur.

### 5.3 Tags d'extraction
- `is_mining_drill` : Mineur de solide.
- `is_pumpjack` : Pompe à fluide brut.
- `is_offshore_pump` : Pompe d'eau.
- `is_well_pump` : Pompe de fluide.

Précisions d'extraction : `is_mining_drill` = `type == 'mining-drill'` (tout minerai) ; `is_pumpjack` = `mining-drill` **avec** `resource_categories ⊇ basic-fluid` ; `is_offshore_pump` = `is_water_extractor` (le seul extracteur de milieu `water` du vanilla) ; `is_well_pump` = `type == 'pump'`. Le `medium` se déduit du `pumped_fluid` résolu (§6.5) puis des catégories de ressource.

### 5.4 Tags de logistique & transport
- `is_belt`, `is_splitter`, `is_inserter` : Logistique de flux.
- `is_pipe`, `is_pipe_to_ground` : Logistique fluide.
- `is_chest`, `is_logistics_chest` : Stockage.
- `is_roboport`, `is_robot` : Logistique robotique — `is_robot` = robot logistique/construction uniquement ; le robot de combat est `is_combat_robot` (jamais confondu).

### 5.5 Tags spécialisés
- `is_power_pole` : Pylône électrique (`type == 'electric-pole'` ; l'ancien `is_beam_pole` a disparu au chantier D3).
- `is_beacon` : Transmission d'effet.
- `is_accumulator` : Stockage électrique.
- `is_energy_storage` : Stockage d'énergie — le dump n'exporte pas `buffer_capacity`, tag rabattu sur `is_accumulator`.
- `is_offgrid` : Production hors réseau.
- `consumes_electricity` : Consommation électrique.
- `is_water_extractor` / `is_fluid_extractor` / `is_ground_extractor` : Extracteurs par milieu.
- `produces_electricity` : Production élec.
- `produces_heat` : Production chaleur.
- `is_heat_source` : Source de chaleur.

## 6. Règles d'inférence

### 6.1 `is_stackable`
Un item est empilable si `stack_size > 1` ou si son type n'est pas dans `NON_STACKABLE_ITEM_TYPES`.

### 6.2 `has_hidden_recipe`
Ne compte JAMAIS la chaleur ni l'électricité comme sortie recevable (§4.1). Le réacteur (item → résidu item) et les boiler/heat-exchanger (fluide → fluide) sont révélés ; les générateurs/extracteurs/lab restants n'ont pas cette signature.

### 6.3 `is_fixed_fluid_crafter`
Restreint `has_hidden_recipe` aux ateliers `is_crafter` à entrée ET sortie fluides : en vanilla, boiler et heat-exchanger. Les autres bâtiments à recette fixe (combusteur à résidu, générateurs, extracteurs) sont exclus.

### 6.4 `is_fixed_crafter`
Inclut les bâtiments à recette fixe pouvant recevoir une recette randomisée : un atelier `is_crafter` avec sortie (fluide ou item), OU un bâtiment à résidu de combustible (`fuel_residues` non vide — le réacteur item → résidu item).

### 6.5 `pumped_fluid` (résolution Python depuis 0.1.5)
L'exporter 0.1.5 ne porte plus le littéral `pumped_fluid` : le dump ne contient que des faits, la résolution est testable côté Python (`inject_pumped_fluids`, idempotente, injectée par `load_db_from_dump` ET `build_vanilla_seed`). Pour chaque entité :

1. **Fluidbox de sortie** — si l'entité est une **source pure** (`fluidboxes.input == 0`, ex. offshore-pump : rien → fluide), le fluide de sa seule fluidbox de sortie la désigne. La porte « source pure » évite de confondre un convertisseur (boiler, heat-exchanger : fluide → fluide) avec un extracteur.
2. **Chaîne de tuiles** — sinon, ses `tile_buildability_rules` exigent des couches (`required_tiles`) ; les tuiles portant ces couches exposent leur `fluid` ; **un seul fluide distinct** doit en émerger, sinon `None` (ambiguïté = rien inventé, l'entité part en « external » avec avertissement). `colliding_tiles` peut être `{}` (dict vide) — robuste via `or []`.

Exemple vanilla : l'offshore-pump exige la couche `water_tile` ; la tuile `water` porte cette couche et le fluide `water` → `pumped_fluid = "water"`. Une tuile peut porter une couche SANS fluide (water-wube) : la chaîne s'arrête proprement. Le `medium` suit : `pumped_fluid` résolu → `medium = "water"` (§5.3).

### 6.6 `science_pack_names` (packs par les faits)
Union des ingrédients de coût des technologies (`unit.ingredients`, formes dict ET listes gérées) et des entrées des labs (`lab_inputs`). Vanilla : 7 packs — `space-science-pack` n'est dans AUCUN coût de tech, il n'est reconnu que par les `lab_inputs`. C'est ce jeu de faits (pas le `subgroup` « science-pack ») qui alimente `ItemDef.is_science_pack`/`is_tool` et le tag `is_progression` du seed.

### 6.7 `rocket_chain_from_dump` (chaîne de lancement)
La chaîne de victoire est **dérivée des faits** et stockée dans `VanillaDB.rocket_chain` — aucun nom d'item n'est codé en dur, un mod qui remplace la fusée reste vérifié :

* **bâtiments de lancement** — entités avec `rocket_parts_required` (elles assemblent des pièces de fusée) ;
* **recettes de fusée** — recettes des catégories de craft de ces bâtiments, en ignorant les pseudo-recettes de paramétrage (sans ingrédients) ;
* **`victory_items`** — les bâtiments de lancement + les ingrédients de ces recettes ;
* **`launch_products`** — les `rocket_launch_products` des items et entités (science spatiale et équivalents moddés).

Vanilla : `rocket-silo` + `rocket-part` (catégorie `rocket-building`) → silo + processing-unit + low-density-structure + rocket-fuel ; produit `space-science-pack`. Le rejoueur s'en sert pour sa condition de victoire (docs/solvabilite.md).

## 7. Notes d'implémentation

### 7.1 `seed_value`
Identifiant de la graine guidant toute la génération, lu depuis `meta.game_version_numeric` (défaut 0 sinon) et stocké dans `VanillaDB.seed_value`. Le dump livré n'exporte que `game_version` : `seed_value` vaut donc 0 à l'entrée, puis est surchargé par le CLI (`randputf gen --seed` ou, par défaut, l'horodatage courant).

### 7.2 `fuel_residues`
Les résidus (`burnt_result` des combustibles du bâtiment) sont calculés à la fin du parse (`load_db_from_dump`) : ils dépendent de la base items, indisponible à la volée. Ils alimentent `fuel_item_flow` et `has_fuel_item_flow`, et estampent `has_hidden_recipe` (§4.1) — le réacteur est ainsi révélé sans liste de noms.

### 7.3 Relation avec `tags.md`
Les TAGS sont calculés PAR CAPACITÉS dans `tool/parsers/vanilla.py` (`tag_parse_entity`) — aucune liste de noms. `tool/common/tagsets.py` ne porte que les ENSEMBLES FIGÉS (ENVIRONMENTAL_ITEMS, VEHICLE_GUNS, ROCKET_CHAIN…, docs/tags.md §14) ; `tool/common/db.py` les re-exporte pour compatibilité. L'audit (`tool/audit/tags.py`) vérifie orthogonalité et cohérence de ces règles.

### 7.4 Chaîne de lancement côté rejoueur
`VanillaDB.rocket_chain` (§6.7) est consommée par le rejoueur (`tool/replay/player.py`) comme condition de victoire : tous les `victory_items` fabricables + tous les `launch_products` récupérés, une fois l'arbre de recherche consommé. Aucun nom vanilla n'y figure : la victoire se déduit des faits, comme un joueur qui découvre la seed.

---
*Document généré à partir de `tool/common/db.py`, `tool/parsers/vanilla.py` et `docs/tags.md`.*
*Version 1.2 – 2026‑11‑11 (dump exporter 0.1.5)*
