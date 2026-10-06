# Configuration

randputF charge l'intégralité de sa configuration depuis deux fichiers YAML. Aucune valeur n'est codée en dur :

| Fichier | Rôle | Modifiable |
|---|---|---|
| `config/defaults.yaml` | **Source unique** des réglages par défaut | Non |
| `config/user.yaml` | Surcharges (facultatives) | Oui |

Ces fichiers subissent une fusion profonde puis une validation stricte avant chaque génération. La configuration finale est complète : le moteur ne génère aucune valeur de secours par lui-même.

Retour : [README.md](../README.md) · [seed.md](seed.md) (§16).

---

## 1. Principes

1. **Source unique.** Chaque paramètre provient de `config/defaults.yaml`. Le moteur y accède exclusivement via `config.default_value(...)`, évitant toute duplication de littéraux.
2. **Préservation de `defaults.yaml`.** Écris tes modifications uniquement dans `config/user.yaml`.
3. **Fusion profonde.** Le fichier `user.yaml` surcharge les clés définies. Les valeurs absentes sont complétées par les valeurs par défaut.
4. **Validation stricte.** Le système contrôle les types, les plages de valeurs, les bornes `min <= max` et les contraintes croisées. Une clé inconnue, un type incorrect ou une valeur hors limites déclenche une erreur explicite immédiate. Rien n'est ignoré en silence.
5. **Déterminisme.** Modifier `defaults.yaml` altère l'espace des seeds et invalide le témoin. Les constantes de structure, comme la forme des gisements ou les règles de solvabilité, restent codées en dehors du YAML (consulte [nondeterminism.md](nondeterminism.md)).

## 2. Exemple de surcharge

Renseigne uniquement tes modifications dans `config/user.yaml`. Exemple pour définir le chemin du dossier des mods avec une installation Steam Flatpak :

```yaml
paths:
  factorio_mods: ~/.var/app/com.valvesoftware.Steam/.factorio/mods
```

Les sections `map`, `recursive`, `tree` et les autres conservent leurs valeurs par défaut.

## 3. Sections

La configuration compte 17 entrées de premier niveau : 16 sections et la racine `factorio_version`. Les sections signalées comme **inertes** sont lues et validées, mais le moteur ne les exploite pas encore.

### `factorio_version` (racine)

Version cible de Factorio (`"2.0"`). Cette clé est inerte : la véritable version est lue dans `mod/info.json` via `tool/common/version.py`.

### `paths`

Emplacements des dossiers. L'application résout d'elle-même `mod_dir` et `vanilla_dump` selon l'environnement (paquet wheel ou dépôt). La clé `factorio_mods` sert à la commande `randputf generate --install` ; modifie-la pour cibler ton installation de Factorio.

### `map` — gisements au sol

| Clé | Défaut | Rôle |
|---|---|---|
| `patches_min` / `patches_max` | 3 / 8 | Nombre **total** de gisements posés au sol, items + fluides confondus, tiré une fois dans la fourchette (§6). Le tirage est sans remise : une ressource n'apparaît qu'une fois sur la carte |
| `richness_item` / `richness_fluid` | [400000, 1500000] / [100000, 600000] | Richesse d'un champ |
| `wells_per_patch` | [3, 8] | Blocs/puits par gisement (§6.5) |
| `item_patch_radius` | [9, 17] | Rayon du champ item (mapgen) |
| `cluster_radius` | [9, 16] | Dispersion des puits fluides autour du centre |
| `first_center_dist` | 25 | Distance du 1er gisement au spawn |
| `center_ring_step` | 24 | Pas des anneaux de centres suivants |

### `starter` — kit de départ

| Clé | Défaut | Rôle |
|---|---|---|
| `free_researches_count` | [1, 2] | **Inerte** (non lue). Le nombre est fixé par `starter_chain.build_tech_steps` (§7) |
| `ammo_count` | 50 | Munitions du kit |
| `inserter_chance` | 0.5 | Probabilité d'un inserter dans le kit |
| `spawn_fuel_count` | 50 | Combustible du starter (burner) |
| `deferred` | [] | **Interne** (pipeline/late raws) — à ne pas renseigner |

### `recursive` — phase récursive

Contient les poids des catégories (`weight_transformer` 30, `weight_extractor` 15, `weight_generator` 10, `weight_distribution` 10, `weight_combat` 15, `weight_science` 20), le facteur `progressive_factor` (0.15), les bâtiments exclus `excluded_buildings` (`[character, lab]`), la limite `max_iterations` (120) et le seuil `stall_threshold` (10). Elle règle aussi la distribution des pylônes (`dist_marks`, `dist_guaranteed`), les limites `recipes_per_building_min`/max, `tech_count_min`/max, `science_cost_min`/max, les paires d'objets liées `companions`, et les **armes embarquées** (§12.1) : `armed_vehicles`, `vehicle_weapons`, `vehicle_slots_min`/max, `vehicle_slots_with_replacement`, `vehicle_range_base_size` et `vehicle_range_scale`.

### `tree` — arbre technologique

Gère `group_chances` (probabilité d'étendre un groupe d'objets), `research_time` (durée de recherche fixée à 60 s par unité de coût), `max_cost_packs` (maximum de 4 packs de science différents requis) et `max_per_tech` (limite de 5 déblocages par technologie).

### `recipes`

Définit la pondération du nombre d'ingrédients et de produits, les paramètres `energies` et `energy_per_ingredient` (durée de fabrication), l'équilibre entre consommation et production (`balance_min`/max, `balance_steepness`, `balance_max_factor`, `max_overproduced_ratio`), la quantité d'ingrédients, le préfixe `recipe_prefix` (`randputf-`) et le poids des ressources de l'environnement.

### `relay`

Configure le préfixe `prefix` (`randputf-relay-`) et la limite `max_dispatch_steps` (3) pour les recettes relais associées aux ressources épuisables (§9.5).

### `easeup`

Définit le préfixe `prefix`, le nombre `max_recipes` (8), le seuil `depth_threshold` (5) et la valeur `unlocks_per_tech` (5) pour générer des recettes de secours lorsque les fabrications s'avèrent trop complexes (§9.3).

### `usage`

Contient `enabled` (true), `strict_order` (U2), `terminal_buildings` (`[lab, rocket-silo]`) et `kit_exempt` pour assurer la garantie d'utilisation stricte (D2).

### `wreck` — site de crash

Définit `t` / `a` / `b` pour la loi pondérée des raretés 0..3 (formule paramétrique sous contraintes `6t + 3a < 100` et `b >= 1`), et le butin `loot` composé de matériaux intermédiaires pour la phase de démarrage.

### `lakes`

Détermine le nombre minimal et maximal de lacs (`min` / `max`) et la taille via `richness_fluid`.

### `late_raws`

Comprend `enabled` (désactivé par défaut avec false), `share` et `pick_chance`. Ces paramètres restent inertes car l'injection est déterministe à 100 %. Le plan v2 associé est une simple note de travail, non intégrée à la version publiée.

### `nonfinite` — **inerte**

Contient les coefficients de randomisation des ressources inépuisables (A1), avec `enabled: false`.

### `craft_quantity` — **inerte**

Définit les multiplicateurs de volume par recette (B3), avec `enabled: false`.

### `pools`, `weights` — **inertes**

Pondérations et exclusions réservées pour un usage futur, sans effet actuel sur le moteur. Les exclusions réelles sont converties en listes exportées directement dans la seed.

## 4. Sections commentées mais non câblées

Le fichier `defaults.yaml` se termine par deux blocs désactivés sous forme de commentaires : `difficulty` (lié à `randputf difficulty`) et `rare_resources`. Ils ne sont pas connectés au pipeline. Les modifier dans ta configuration n'aura aucun impact tant qu'ils ne seront pas raccordés.

## 5. Où sont lues les valeurs

La fonction `pipeline.generate_seed` harmonise la configuration à l'aide de `tool.common.config.full_config`. Elle la transmet ensuite aux classes de données de `tool/prototypes/*.py` et aux différents modules de génération. La commande `randputf difficulty` exploite exactement la même configuration que le processus `generate`.
