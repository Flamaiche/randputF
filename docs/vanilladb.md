# VanillaDB — base de données normalisée du contenu vanilla

## 1. Rôle du module et position dans le pipeline

Le module `tool/common/db.py` centralise la **base de données normalisée**, source de vérité pour toutes les phases du générateur. Il convertit le `vanilla_dump.json` en une structure interne, `VanillaDB`, exploitée par le pipeline.

Définie dans `tool/parsers/vanilla.py` (lignes 154‑226) et appelée par `tool/generator/pipeline.py`, la fonction `load_db_from_dump()` initialise l'objet `VanillaDB` à partir du dump : items, fluides, bâtiments taggés par capacités, recettes, puis pools dérivés. Cette base est ensuite transmise à `randputf` pour la génération.

```
# Position dans le pipeline
# ──────────────────────────────────────
1. Objet et périmètre (pipeline.md:13‑21)
2. Les trois fonctions d'orchestration (pipeline.py:23‑32)
3. Chronologie des jalons (pipeline.md:39‑50)
```

## 2. Format d'entrée : `vanilla_dump.json` et métadonnées

Le `vanilla_dump.json` (version 2.0) fournit les données brutes exploitées par `VanillaDB` :

* **`meta`** – métadonnées : `game_version` est exportée (ex. « 2.0.77 ») ; `game_version_numeric` est absente, d'où `seed_value = 0` par défaut (ligne 161).
* **`items`** – objets solides (armes, munitions, outils, science), filtrés par `is_junk` (lignes 163‑166). Chaque entrée est un `ItemDef` (§3).
* **`fluids`** – fluides (liquides, gaz), filtrés par `is_junk` (lignes 191‑194). Chaque entrée est un `FluidDef` (§3).
* **`entities`** – entités du monde, filtrées par `is_junk` (lignes 200‑204) puis taggées par capacités (`tag_parse_entity`).
* **`recipes`** – recettes brutes avec `name`, `category`, `ingredients`, `products` et `energy` (lignes 209‑216).

La `seed_value` est lue depuis `meta.game_version_numeric` (défaut 0 si absente, §7.1) et stockée dans `VanillaDB.seed_value` (ligne 316) pour initialiser les flux aléatoires du pipeline (§1).

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
    fuel_category: str = ""
    burnt_result: str | None = None
    stack_size: int = 0
    is_environmental: bool = False
    is_virtual_item: bool = False
    is_module: bool = False
    is_capsule_throwable: bool = False
```

Champs clés :
- **Identification** – `name` et `subgroup` (lignes 117‑119).
- **Placement** – `place_result` (où l'item est posé).
- **Combustion** – `fuel_value` (valeur énergétique).
- **Tags** – `is_environmental`, `is_virtual_item`, `is_module`, `is_capsule_throwable` (lignes 117‑143).
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
| `beltable_items` | `VanillaDB.beltable_items()` | Items solides posables sur tapis, HORS outils (`not is_tool`), triés par nom (lignes 326‑331). |
| `pipable_fluids` | `VanillaDB.pipable_fluids()` | TOUS les fluides du dump, triés par nom (lignes 333‑335). |
| `extraction_only_fluids` | `VanillaDB.extraction_only_fluids` | Fluides sans recette de production directe (eau, pétrole brut, vapeur) ; barillage exclu (cycle fluide → baril → fluide) (lignes 338‑350). |
| `raw_resources` | `VanillaDB.raw_resources(patch_resources)` | Patches posés + `ENVIRONMENTAL_ITEMS` + `extraction_only_fluids` (lignes 352‑357). |
| `fuel_items` | `VanillaDB.fuel_items()` | Items combustibles triés (lignes 359‑365). |
| `fuels_for(b)` | méthode | Combustibles compatibles par bâtiment (lignes 366‑378). |
| `fuel_residues(b)` | méthode | Résidus de combustion (lignes 379‑386). |
| `fuel_item_flow(b)` | méthode | Flux normalisé : combustible vers résidu (lignes 387‑404). |
| `has_fuel_item_flow(b)` | méthode | Vrai si le bâtiment produit un résidu item (lignes 399‑404). |
| `fuel_fluids()` | méthode | Fluides combustibles triés (lignes 405‑411). |
| `buildings_with_tag(tag)` | méthode | Bâtiments possédant le tag (lignes 412‑418). |
| `extractors_for_medium(medium)` | méthode | Extracteurs par milieu (lignes 420‑430). |

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

Précisions d'extraction (vanilla.py:462‑465) : `is_mining_drill` = `type == 'mining-drill'` (tout minerai) ; `is_pumpjack` = `mining-drill` **avec** `resource_categories ⊇ basic-fluid` ; `is_offshore_pump` = le seul extracteur `medium == 'water'` ; `is_well_pump` = `type == 'pump'`.

### 5.4 Tags de logistique & transport
- `is_belt`, `is_splitter`, `is_inserter` : Logistique de flux.
- `is_pipe`, `is_pipe_to_ground` : Logistique fluide.
- `is_chest`, `is_logistics_chest` : Stockage.
- `is_roboport`, `is_robot` : Logistique robotique — `is_robot` = robot logistique/construction uniquement ; le robot de combat est `is_combat_robot` (jamais confondu).

### 5.5 Tags spécialisés
- `is_power_pole` : Pylône électrique (`type == 'electric-pole'` ; l'ancien `is_beam_pole` a disparu au chantier D3).
- `is_beacon` : Transmission d'effet.
- `is_accumulator` : Stockage électrique.
- `is_energy_storage` : Stockage d'énergie — le dump n'exporte pas `buffer_capacity`, tag rabattu sur `is_accumulator` (vanilla.py:394‑397).
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

## 7. Notes d'implémentation

### 7.1 `seed_value`
Identifiant de la graine guidant toute la génération, lu depuis `meta.game_version_numeric` (défaut 0 sinon, vanilla.py:161) et stocké dans `VanillaDB.seed_value` (ligne 316). Le dump livré n'exporte que `game_version` : `seed_value` vaut donc 0 à l'entrée, puis est surchargé par le CLI (`randputf gen --seed` ou, par défaut, l'horodatage courant).

### 7.2 `fuel_residues`
Les résidus (`burnt_result` des combustibles du bâtiment) sont calculés à la fin du parse (vanilla.py:223‑225) : ils dépendent de la base items, indisponible à la volée. Ils alimentent `fuel_item_flow` et `has_fuel_item_flow`, et estampent `has_hidden_recipe` (§4.1) — le réacteur est ainsi révélé sans liste de noms.

### 7.3 Relation avec `tags.md`
Les TAGS sont calculés PAR CAPACITÉS dans `tool/parsers/vanilla.py` (`tag_parse_entity`) — aucune liste de noms. `tool/common/tagsets.py` ne porte que les ENSEMBLES FIGÉS (ENVIRONMENTAL_ITEMS, VEHICLE_GUNS, ROCKET_CHAIN…, docs/tags.md §14) ; `tool/common/db.py` les re-exporte pour compatibilité. L'audit (`tool/audit/tags.py`) vérifie orthogonalité et cohérence de ces règles.

---
*Document généré à partir de `tool/common/db.py`, `tool/parsers/vanilla.py` et `docs/tags.md`.*
*Version 1.1 – 2026‑10‑07*
