# Configuration

randputF lit **toute** sa configuration dans deux fichiers YAML, jamais dans des
valeurs codées en dur :

| Fichier | Rôle | Modifiable |
|---|---|---|
| `config/defaults.yaml` | **Source unique** de tous les réglages par défaut | Non |
| `config/user.yaml` | Tes surcharges, facultatives | Oui |

Les deux sont fusionnés en profondeur, puis **validés** avant chaque génération.
Un config fusionné est toujours complet : il n'existe aucun chemin par lequel le
moteur invente une valeur de secours.

Retour : [README.md](../README.md) · [seed.md](seed.md) (§16, seed et config).

---

## 1. Principes

1. **Source unique.** Une valeur de réglage existe à un seul endroit :
   `config/defaults.yaml`. Le moteur la lit via `config.default_value(section,
   key)`, jamais par un littéral dupliqué.
2. **Ne pas modifier `defaults.yaml`.** Il est livré avec le tool. Tes
   intentions vont dans `config/user.yaml`.
3. **Fusion profonde.** `user.yaml` écrase clé par clé ; les sections et les
   clés absentes de `user.yaml` viennent des defaults.
4. **Validation stricte.** Type, plage, bornes `min <= max`, contraintes
   croisées. Une clé inconnue, un mauvais type ou une valeur impossible est une
   **erreur explicite** au chargement, jamais une génération silencieuse.
5. **Déterminisme.** Changer une valeur dans `defaults.yaml` change l'espace des
   seeds (et invalide le témoin). Les constantes *structurelles* (formes de
   gisements, invariants de solvabilité) ne sont volontairement pas dans le YAML
   : les voir dans [nondeterminism.md](nondeterminism.md).

## 2. Exemple de surcharge

`config/user.yaml` n'écrit que ce que tu changes. Chemin du dossier mods pour un
install Steam flatpak :

```yaml
paths:
  factorio_mods: ~/.var/app/com.valvesoftware.Steam/.factorio/mods
```

Toute la section `map`, `recursive`, `tree`… reste celle des defaults.

## 3. Sections

16 sections, plus la racine `factorio_version` (17 entrées de premier niveau).
Les sections marquées **inertes** sont
écrites et validées mais **pas lues** par le moteur à ce jour.

### `factorio_version` (racine)

Version du jeu cible, `"2.0"`. Inerte : lue depuis `mod/info.json`, qui est la
source de vérité de la version (`tool/common/version.py`).

### `paths`

Dossiers. `mod_dir` et `vanilla_dump` sont résolus par l'asset (wheel ou dépôt).
`factorio_mods` est utilisé par `randputf generate --install` et doit être
surchargé pour installer dans Factorio.

### `map` — gisements au sol

| Clé | Défaut | Rôle |
|---|---|---|
| `patches_min` / `patches_max` | 3 / 8 | Nombre de gisements par ressource (§6) |
| `richness_item` / `richness_fluid` | [400000, 1500000] / [100000, 600000] | Richesse d'un champ |
| `wells_per_patch` | [3, 8] | Blocs / puits par gisement (§6.5) |
| `item_patch_radius` | [9, 17] | Rayon du champ item type mapgen |
| `cluster_radius` | [9, 16] | Dispersion des puits fluide autour du centre |
| `first_center_dist` | 25 | Distance du 1er gisement au spawn |
| `center_ring_step` | 24 | Pas des anneaux de centres suivants |

### `starter` — kit de départ

| Clé | Défaut | Rôle |
|---|---|---|
| `free_researches_count` | [1, 2] | Recherches gratuites du départ |
| `ammo_count` | 50 | Munitions du kit |
| `inserter_chance` | 0.5 | Probabilité d'un inserter dans le kit |
| `spawn_fuel_count` | 50 | Combustible du starter en burner |
| `deferred` | [] | **Interne** (pipeline, raws late) — ne pas renseigner |

### `recursive` — phase récursive

Poids par catégorie (`weight_transformer` 30, `weight_extractor` 15,
`weight_generator` 10, `weight_distribution` 10, `weight_combat` 15,
`weight_science` 20), `progressive_factor` (0.15), `excluded_buildings`
(`[character, lab]`), `max_iterations` (120), `stall_threshold` (10), cadence des
pylônes (`dist_marks`, `dist_guaranteed`), bornes `recipes_per_building_min/max`,
`tech_count_min/max`, `science_cost_min/max`, `companions` (paires d'items
jamais dissociées), et les **armes montées** (§12.1) : `armed_vehicles`,
`vehicle_weapons`, `vehicle_slots_min/max`, `vehicle_slots_with_replacement`,
`vehicle_range_base_size`, `vehicle_range_scale`.

### `tree` — arbre technologique

`group_chances` (proba d'extension du groupe d'objets), `research_time` (60 s
par unité de coût), `max_cost_packs` (4 packs différents max), `max_per_tech`
(5 unlocks max).

### `recipes`

Poids du nombre d'ingrédients / résultats, `energies` + `energy_per_ingredient`
(temps de craft), équilibre cons/prod (`balance_min/max`, `balance_steepness`,
`balance_max_factor`, `max_overproduced_ratio`), montants d'ingrédients,
`recipe_prefix` (`randputf-`), poids des ressources environnementales.

### `relay`

`prefix` (`randputf-relay-`) et `max_dispatch_steps` (3) : recettes relais des
ressources non-infinies (§9.5).

### `easeup`

`prefix`, `max_recipes` (8), `depth_threshold` (5), `unlocks_per_tech` (5) :
recettes alternatives pour les crafts trop lourds (§9.3).

### `usage`

`enabled` (true), `strict_order` (U2), `terminal_buildings`
(`[lab, rocket-silo]`), `kit_exempt` : garantie d'usage dure (D2).

### `wreck` — site de crash

`t` / `a` / `b` : loi pondérée des raretés 0..3 (formule paramétrique, contrainte
`6t + 3a < 100` et `b >= 1`) ; `loot` (matériaux non finis du bootstrap).

### `lakes`

`min` / `max` (nombre de lacs), `richness_fluid` (taille).

### `late_raws`

`enabled` (false par défaut), `share`, `pick_chance` (conservés, inertes :
injection déterministe à 100 %). Voir [plan-extracteurs-dispatche.md](plan-extracteurs-dispatche.md).

### `nonfinite` — **inerte**

Facteurs de randomisation des ressources non finies (A1), `enabled: false`.

### `craft_quantity` — **inerte**

Facteurs de quantité par recette (B3), `enabled: false`.

### `pools`, `weights` — **inertes**

Exclusions et pondérations réservées, sans consommateur dans le moteur. Les
exclusions effectives sont traduites en pools exportées dans la seed.

## 4. Sections commentées mais non câblées

En pied de `defaults.yaml`, deux blocs sont commentés : `difficulty`
(`randputf difficulty`) et `rare_resources`. Ils ne sont pas câblés au
pipeline ; les surcharger n'a aucun effet tant qu'ils ne le sont pas.

## 5. Où sont lues les valeurs

`pipeline.generate_seed` normalise la config via
`tool.common.config.full_config`, puis la passe aux prototypes dataclass
(`tool/prototypes/*.py`) et aux générateurs. `randputf difficulty` consomme la
même config que `generate`.