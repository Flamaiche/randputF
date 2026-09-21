# Seed et configuration

Partie de la doc de conception randputF (dev). Retour : [docs/README.md](README.md).

## 16. Seed et configuration

- **Défaut : seed temporelle.** Sans `--seed`, la commande génère une seed
  depuis l'instant présent — `int(time.time() * 1000)` = millisecondes écoulées
  depuis l'époque (Soit *aaaa-mm-jj hh:mm:ss.mmm*). Deux générations
  successives obtiennent donc presque toujours des seeds (et des mods)
  différents. La seed choisie est affichée en sortie pour reproductibilité.
- **Imposer une valeur.** `tool generate --seed <n>` (ou la key `seed` de
  `config/settings.yaml`, désormais réservée à un défaut explicite) fige une
  seed : relancer avec la même valeur reproduit exactement le même mod
  (déterminisme vérifié, octet-pour-octet). Le déterminisme tient **entre
  processus** : aucune itération de `set`/`frozenset` n'alimente un `rng`
  (sinon l'ordre de hachage Python varierait selon `PYTHONHASHSEED`) —
  régression gardée par `tests/test_determinism.py`, qui régénère la seed en
  sous-processus sous deux hashseeds et compare le résultat (inventaire
  détaillé dans `docs/nondeterminism.md`).
- **Pas de borne haute (« seed max »).** La seed est injectée comme *chaîne*
  dans `random.Random(f"randputF:{seed}")` (et `randputF:lakes:{seed}`), que
  Python hache déterministiquement. Aucune limite supérieure n'est imposée par
  le générateur ni le validateur : des valeurs jusqu'à 19+ chiffres
  (`12345678901234567890`, `10^30`, sys.maxsize, …) sont acceptées et
  produisent un mod valide. La seule limite pratique est l'entier Python
  (précision arbitraire). Le validateur ne vérifie que la **solvabilité**
  (anti-cycle, progressivité, complétude §15) — jamais la valeur numérique ;
  une seed qui tombe sur un cas non solvable est re-tirée automatiquement
  (boucle bornée à 10 essais) avant de rendre la main.
- **Diversité / unicité.** Sur 61 seeds consécutives + 8 aléatoires testées,
  aucune collision : chaque seed → un `seed.lua` unique (sha256 distinct).
- La config est **réellement consommée** par la génération. Sections actives
  (lues à chaque génération, dans `config/settings.yaml`) :
  - `seed`, `paths` ;
  - `map` : `patches_min/max` (nombre de gisements §6), `richness_item/fluid`
    (richesse §6), `wells_per_patch` (blocs/puits par gisement §6.5),
    `item_patch_radius` (rayon des champs items §6.5) ;
  - `starter` : `ammo_count` (munitions du kit, défaut 50 §11),
    `inserter_chance` (bras optionnel de la chaîne §8, défaut 0.5) —
    (la clé `free_researches_count` du yaml par défaut est **inerte** : le
    nombre de recherches gratuites est piloté par le build, §7) ;
  - `recursive` : poids des catégories (`weight_transformer/extractor/generator/
    distribution/combat/science`), `progressive_factor`, `max_iterations`,
    `stall_threshold`, `dist_marks` + `dist_guaranteed` (garantie de
    compagnons §9.7), `recipes_per_building_min/max`, `tech_count_min/max`,
    `science_cost_min/max`, et les **armes montées §12.1** (`armed_vehicles`,
    `vehicle_weapons`, `vehicle_slots_min/max`, `vehicle_slots_with_replacement`,
    `vehicle_range_base_size`, `vehicle_range_scale`) ;
  - `recipes` : poids du nb d'ingrédients/résultats (`weight_1_ingredient`…),
    `energies` + `energy_per_ingredient` (§9.2 temps de craft), équilibre
    cons/prod `balance_min/max`, `balance_max_factor` (§9.2) —
    **section optionnelle** : absente, le moteur utilise les défauts du
    prototype `tool/prototypes/recipes.py` ;
  - `relay` (optionnel, défauts `tool/prototypes/relay.py`) : `prefix`,
    `max_dispatch_steps` (recettes relais §9.5) ;
  - `easeup` : `max_recipes` (nb max de recettes ease-up), `depth_threshold`
    (profondeur déclencheuse), `unlocks_per_tech` (plafond §13) — crafts
    trop lourds §9.3.
  - `wreck` : `t`/`a`/`b` (loi pondérée du crash §7), `loot` (matériaux) ;
  - `lakes` : `min`/`max` (nombre de lacs §6), `richness_fluid` (taille) ;
  - `tree` : `group_chances` (nombre d'objets par tech §13).
  Toute la config est passée via `pipeline.set_config()` → prototypes dataclass
  (`tool/prototypes/*.py`) : aucune valeur d'algorithme codée en dur dans le
  moteur.
- Sections `pools` (`exclude_items`, `exclude_fluids`,
  `exclude_building_types`) et `weights` (`building_types`, `science_packs`)
  : présentes dans le yaml par défaut mais **non lues par le moteur** (clés
  mortes à ce jour — la randomisation complète les pools elle-même). Les
  exclusions effectives sont traduites en pools exportées dans la seed, pas en
  filtres de configuration.
- La seed exporte en plus des structures de documentation/jouabilité :
  `pools.vehicle_weapons` (items gun de la pool montée §12.1),
  `pools.vehicle_range_scaling` (`base_size` + `scale`, §12.1),
  `vehicle_armament` (assignation véhicule → armes de la graine courante) et
  `pools.raw_resources` (ressources brutes de la graine, §3 — vérifiable sans
  re-génération).
