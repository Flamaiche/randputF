# VanillaDB — base de données normalisée du contenu vanilla

## 1. Rôle du module et position dans le pipeline

Le module `tool/common/db.py` fournit la **base de données normalisée** qui constitue la source de vérité en lecture pour toutes les phases du générateur. Elle convertit le `vanilla_dump.json` (export du jeu) en une structure interne (`VanillaDB`) utilisée par les autres composants du pipeline de génération.

Dans le pipeline de génération (`tool/generator/pipeline.py`), la fonction `load_db_from_dump()` (ligne 154‑226) charge le dump et construit un objet `VanillaDB` qui contient les entités (items, fluides, bâtiments, recettes) ainsi que les pools dérivés. Cette base est ensuite passée à `randputf` pour la génération finale.

```
# Position dans le pipeline
# ──────────────────────────────────────
1. Objet et périmètre (pipeline.md:13‑21)
2. Les trois fonctions d'orchestration (pipeline.py:23‑32)
3. Chronologie des jalons (pipeline.md:39‑50)
```

## 2. Format d'entrée : `vanilla_dump.json` et métadonnées

Le fichier `vanilla_dump.json` est le dump brut du jeu (version 2.0). Il contient les sections suivantes qui sont exploitées par `VanillaDB` :

* **`meta`** – métadonnées du jeu, notamment `game_version_numeric` (ligne 161) qui détermine la `seed_value` (ligne 316).
* **`items`** – tous les objets solides (armes, munitions, outils, packs de science, etc.). Chaque entrée est un `ItemDef` (voir §3).
* **`fluids`** – tous les fluides (liquides, gaz, etc.). Chaque entrée est un `FluidDef` (voir §3).
* **`entities`** – entités du monde (minéraux, biologiques, etc.), filtrées par `is_junk` (ligne 163).
* **`recipes`** – recettes brutes du dump, chacune avec `name`, `category`, `ingredients`, `products` et `energy` (ligne 209‑216).

La `seed_value` est extraite de `meta.game_version` (ou `meta.game_version_numeric` par défaut) et initialise le flux aléatoire utilisé par le pipeline (ligne 316).

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

Champs clés :
- **Nom et sous‑groupe** – identification unique (ligne 117‑119).
- **Place de sortie** – où l'item est posé (`item_output_slots` / `fluid_outputs`).
- **Valeur combustible** – `fuel_value` (brûlable).
- **Tags cumulables** – `is_environmental`, `is_virtual_item`, `is_module`, `is_capsule_throwable` (ligne 117‑143).
- **Propriétés de stackabilité** – `stack_size` (si > 1, empileable ; sinon déduit du type).
- **Catégories** – `item_type`, `fuel_category`, `subgroup` (catégories de craft, énergie, etc.).

### 3.2 `FluidDef` (fluide)

```python
@dataclass(frozen=True)
class FluidDef:
    name: str
    fuel_value: float | None = None
```

Un fluide est identifié uniquement par son nom (la température n'est pas une dimension).

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
    # Tags cumulables (rôle fonctionnel)
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
    # Tags spécialisés
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
    # Tags combat & défense
    is_turret: bool = False
    is_gun_turret: bool = False
    is_laser_turret: bool = False
    is_flame_turret: bool = False
    is_artillery: bool = False
    is_defensive_wall: bool = False
    is_landmine: bool = False
    is_combat_robot: bool = False
    # Tags réseau & électronique
    is_circuit_combinator: bool = False
    is_constant_combinator: bool = False
    is_circuit_io: bool = False
    is_rgb_lamp: bool = False
    is_radar: bool = False
```

#### 3.3.1 Pools dérivés

| Pool | Méthode | Description |
|------|---------|-------------|
| `beltable_items` | `VanillaDB.beltable_items()` | Items posables sur tapis (hors outils). Calculé à partir des bâtiments `is_belt` et `is_underground_belt` (lignes 326‑327). |
| `pipable_fluids` | `VanillaDB.pipable_fluids()` | Fluides pipables (eau, pétrole, vapeur, etc.). Calculé à partir des fluides sans recette de production directe (lignes 333‑350). |
| `extraction_only_fluids` | `VanillaDB.extraction_only_fluids` | Fluides sans recette de production directe (eau, pétrole brut, vapeur). Exclut les barils (cycles barril → fluide). (lignes 338‑350). |
| `raw_resources` | `VanillaDB.raw_resources()` | Ressources brutes du patch + `ENVIRONMENTAL_ITEMS` + `extraction_only_fluids`. (lignes 352‑357). |
| `fuel_items` | `VanillaDB.fuel_items()` | Items à valeur combustible, triés par nom. (lignes 359‑365). |
| `fuels_for(b)` | méthode | Combustibles qu'un bâtiment peut brûler (catégories `fuel_categories`). (lignes 366‑378). |
| `fuel_residues(b)` | méthode | Résidus de combustion (item) issus des combustibles du bâtiment. (lignes 379‑386). |
| `fuel_item_flow(b)` | méthode | Vue normalisée d'une machine à combustible (entrée = item, sorties = résidus). (lignes 387‑404). |
| `has_fuel_item_flow(b)` | méthode | Vrai si le bâtiment produit un résidu item (combustible → résidu). (lignes 399‑404). |
| `fuel_fluids()` | méthode | Fluides à valeur combustible, triés par nom. (lignes 405‑411). |
| `buildings_with_tag(tag)` | méthode | Bâtiments portant un tag donné. (lignes 412‑418). |
| `extractors_for_medium(medium)` | méthode | Extracteurs du dump pour un milieu donné (item/fluid). (lignes 420‑430). |

## 4. Prédicats de détection par capacités

### 4.1 `has_hidden_recipe(b: BuildingDef) -> bool`

Détecte les bâtiments possédant une **recette cachée** (code de fabrication codé en dur, non accessible avant la transformation du mod). La détection est faite **par capacités intrinsèques** (aucune liste de noms) :

1. Le bâtiment doit porter au moins un tag de production (`is_research`, `is_crafter`, `is_generator`, `is_extractor`).
2. Il doit avoir une entrée (item, fluide ou combustible) et une sortie (item/fluide ou résidu).
3. Il ne doit **pas** posséder de catégorie de crafting valide (`is_crafter`, `is_generator`, `is_constructor`).

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

**Exemples** :
- `boiler` (fluide → fluide) et `heat-exchanger` (fluide → fluide) → `True`.
- `nuclear-reactor` (item → résidu item) → `True`.
- Un générateur classique (turbine, panneau solaire) → `False` car il n'a ni entrée ni sortie de type produit.

### 4.2 `is_fixed_fluid_crafter(b: BuildingDef) -> bool`

Sous‑ensemble de `has_hidden_recipe` où le générateur crée une **recette fluide → fluide** randomisée (boiler, heat‑exchanger). Les autres bâtiments à recette fixe (combusteurs à résidu, etc.) sont exclus.

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

Bâtiment à recette **fixe** pouvant héberger une recette randomisée. Inclut les bâtiments à recette fixe (boiler, heat‑exchanger) ET les générateurs/extracteurs/lab qui produisent un résidu (combustible → résidu item).

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

### 5.1 Tags de rôle fonctionnel (cumulables)

| Tag | Signification | Déterminé par | Consommé par |
|------|---------------|---------------|--------------|
| `is_research` | Lab / pack de recherche | `PRODUCING_TAGS` + entrée | `starter_chain`, `map_patches`, `recipes` |
| `is_crafter` | Atelier (sortie item/fluide) | catégories de craft, `rocket_parts_required`, `target_temperature` | `recursive_phase`, `recipes`, `building_fluids` |
| `is_generator` | Produit d'énergie (élec/ chaleur) | `max_power_output > 0`, `production > 0`, `produces_heat` | `recursive_phase`, `building_fluids` |
| `is_distribution` | Infrastructure de distribution (pylônes) | `supply_area_distance ≠ 0` | `recursive_phase`, `electricity` |
| `is_extractor` | Extrait une ressource (minéral, fluide, solide) | `resource_categories`, `pumped_fluid` | `recipes`, `starter_chain`, `extractors_for_medium` |
| `is_other` | Aucune capacité reconnue | = ¬(tous les rôles ci‑dessus) | `summarize_db` (uniquement) |

### 5.2 Tags énergétiques & chaleur

| Tag | Signification | Déterminé par | Consommé par |
|------|---------------|---------------|--------------|
| `is_boiler` | Four (type `boiler`, `energy_type = burner`) | `type == 'boiler'` + `energy_type == 'burner'` | `is_fixed_fluid_crafter`, `building_fluids` |
| `is_heat_exchanger` | Échangeur (type `boiler`, `energy_type = heat`) | `type == 'boiler'` + `energy_type == 'heat'` | `is_fixed_fluid_crafter`, `building_fluids` |
| `is_solar` | Panneau solaire | `type == 'solar-panel'` | `audit`, tests |
| `is_reactor` | Réacteur nucléaire | `type == 'reactor'` | `audit` (via `fuel_residues`) |
| `is_heat_transport` | Pipe de chaleur | `type == 'heat-pipe'` | `recursive_phase` |
| `is_heat_sink` | Consommateur de chaleur | `energy_type == 'heat'` | `recursive_phase` |

### 5.3 Tags d'extraction

| Tag | Signification | Déterminé par | Consommé par |
|------|---------------|---------------|--------------|
| `is_mining_drill` | Mineur (minerai solide) | `type == 'mining-drill'` + `resource_categories ⊇ basic-fluid` | `starter_chain`, `map_patches` |
| `is_pumpjack` | Pompe à fluide brut | `type == 'mining-drill'` + `resource_categories ⊇ basic-fluid` | `starter_chain` (fluides profonds) |
| `is_offshore_pump` | Pompe d'eau | `is_water_extractor` (médium = eau) | `starter_chain`, `map_patches` |
| `is_well_pump` | Pompe de fluide brut | `type == 'pump'` | `starter_chain` (patch water) |

### 5.4 Tags de logistique & transport

| Tag | Signification | Déterminé par | Consommé par |
|------|---------------|---------------|--------------|
| `is_belt` | Transport‑belt | `type == 'transport-belt'` | `starter_chain` (rôle `belt`) |
| `is_splitter` | Splitter de flux | `type == 'splitter'` | `starter_chain` (rôle `splitter`) |
| `is_inserter` | Inserter de flux | `type == 'inserter'` | `starter_chain` (rôle `inserter`) |
| `is_pipe` | Pipe (fluide) | `type == 'pipe'` | `starter_chain` (rôle `pipe`) |
| `is_pipe_to_ground` | Pipe sous‑terrain | `type == 'pipe-to-ground'` | `starter_chain` (rôle `pipe_to_ground`) |
| `is_fluid_transport` | Union `pipe` + `pipe_to_ground` | dérivé des deux précédents | – |
| `is_chest` | Conteneur (stockage) | `type == 'container'` | `starter_chain` (raffinage usage‑view) |
| `is_logistics_chest` | Logistics‑chest | `type == 'logistic-container'` | `starter_chain` (raffinage usage‑view) |
| `is_storage` | Stockage (chest/chest) | `is_chest` ou `is_logistics_chest` | – |
| `is_roboport` | Roboport (C3 ↔ roboport) | `type == 'roboport'` | – |
| `is_robot` | Robot logistique/construction | `is_mounted_gun` absent, `type` dans les catégories robot | – |

### 5.5 Tags spécialisés

| Tag | Signification | Déterminé par | Consommé par |
|------|---------------|---------------|--------------|
| `is_boiler`, `is_heat_exchanger` | Boiler / Heat‑exchanger | `type == 'boiler'` + `energy_type` | – |
| `is_solar` | Panneau solaire | `type == 'solar-panel'` | – |
| `is_reactor` | Réacteur nucléaire | `type == 'reactor'` | – |
| `is_beam_pole` | Pile électrique (type `electric-pole`) | `type == 'electric-pole'` | `electricity`, `tech_tree`, `recursive_phase` |
| `is_beacon` | Module de transmission d'effet | `type == 'beacon'` | raffinage usage‑view |
| `is_accumulator` | Stockeur d'énergie | `type == 'accumulator'` | audit |
| `is_energy_storage` | Stockage d'énergie | `buffer_capacity > 0` (sans production) | raffinage |
| `is_offgrid` | Producteur hors réseau (solaire, burner‑generator) | `produces_electricity` + énergie non `electric` | audit |
| `consumes_electricity` | Consomme du courant | `energy_type == 'electric'` sans production ni stockage | audit |
| `is_water_extractor` / `is_fluid_extractor` / `is_ground_extractor` | Extracteur par médium | `is_extractor` + `medium` (water/fluid/ground) | `extractors_for_medium`, `starter_chain` |
| `produces_electricity` | Producteur de courant (turbine, steam‑engine, solar‑panel) | – | `electricity`, `building_fluids` |
| `produces_heat` | Producteur de chaleur (nuclear‑reactor) | – | `electricity` (exclut le réacteur du réseau), `recursive_phase` |
| `is_heat_source` | Source de chaleur (réacteur) | `type == 'reactor'` ou (`has_heat_output` ET `energy_type == 'burner'`) | `recursive_phase._ensure_heat_prereq` |
| `is_heat_sink` | Consommateur de chaleur (heat‑exchanger) | `energy_type == 'heat'` | `recursive_phase._ensure_heat_prereq` |
| `is_boiler`, `is_heat_exchanger` | Distinction source vs transport de chaleur | – | – |

## 6. Règles d'inférence

### 6.1 `is_stackable`

Une entrée est **empilable** si son `stack_size` est supérieur à 1. Sinon, on se fie au type :

```python
def is_stackable(self) -> bool:
    if self.stack_size:
        return self.stack_size > 1
    return self.item_type not in NON_STACKABLE_ITEM_TYPES
```

Les types non‑stackables (armure, arme, véhicule, etc.) sont toujours non‑empilables.

### 6.2 `has_hidden_recipe` (rappel)

Comme décrit en §4.1, ce prédicat détecte les bâtiments à recette cachée. Il **ne compte jamais** la chaleur ou l'électricité : les réacteurs (item → résidu) et les boilers/heat‑exchangers sont considérés comme `has_hidden_recipe = True` mais **ne sont pas** des `is_fixed_fluid_crafter` (car ils ne produisent pas de fluide).

### 6.3 `is_fixed_fluid_crafter` (rappel)

Restreint `has_hidden_recipe` aux bâtiments qui créent une recette **fluide → fluide** randomisée (boiler, heat‑exchanger). Les autres bâtiments à recette fixe (combusteurs à résidu, générateurs, extracteurs) sont exclus.

### 6.4 `is_fixed_crafter` (rappel)

Inclut les bâtiments à recette fixe pouvant recevoir une recette randomisée :
- `is_crafter` + sortie fluide ou item
- `is_crafter` + résidu item (combustible → résidu)

Ces bâtiments reçoivent effectivement une recette aléatoire lors de la génération.

## 7. Notes d'implémentation

### 7.1 `seed_value`

La `seed_value` est l'identifiant de la graine aléatoire qui guide toute la génération. Elle provient de `meta.game_version` (ou `meta.game_version_numeric` par défaut) dans le dump (ligne 161). La valeur est stockée dans `VanillaDB.seed_value` (ligne 316) et utilisée par le flux aléatoire partagé (`db.seed_value`) dans toutes les phases du pipeline (lignes 153, 151, 167, 177, 203, 215, 221).

### 7.2 `fuel_residues` remplis après parse

Après le parsing du dump, les `fuel_residues` de chaque bâtiment sont calculés à partir des `burnt_result` des combustibles (lignes 379‑386). Ces résidus sont remplis **après** la création de la base `VanillaDB` et servent à :
- Activer le tag `has_hidden_recipe` pour les bâtiments correspondants (ligne 224).
- Alimenter `fuel_item_flow` et `fuel_residues` pour les méthodes de pool (lignes 399‑404).

### 7.3 Relation avec `tags.md`

Tous les tags définis dans `tool/common/tagsets.py` (section 1‑13 de `docs/tags.md`) sont appliqués sur les entités via les capacités intrinsèques. La base `VanillaDB` expose les méthodes de filtrage (`buildings_with_tag`, `extractors_for_medium`) qui correspondent aux sections du document de tags. L'audit (`tool/audit/tags.py`) vérifie l'orthogonalité et la cohérence des tags par rapport à ces règles.

---

*Document généré à partir de `tool/common/db.py` et `docs/tags.md`.*
*Version 1.0 – 2026‑10‑02*