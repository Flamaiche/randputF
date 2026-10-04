# Pipeline de génération — chronologie complète

Ce document décrit **action par action** la génération d'une seed randputF :
l'ordre exact des jalons, l'appel Python responsible de chacun, les structures
d'entrée et de sortie, le flux RNG consommé, l'invariant que le jalon garantit et
le test qui le couvre.

Toute référence `fichier:ligne` pointe le code réel vérifié à la date de
rédaction. Les numéros de ligne bougent : vérifier avant de citer.

---

## 1. Objet et périmètre

| Question | Réponse |
|----------|---------|
| Que produit le pipeline ? | Un `dict` `seed` — la structure décrite dans `tool/exporters/mod_seed.py:8-32` |
| Qui l'appelle ? | `tool/__main__.py:153` (`randputf generate`), `tool/__main__.py:204` (`randputf difficulty`), `tool/__main__.py:217` (`randputf witness`) |
| Le pipeline écrit-il des fichiers ? | Non. L'écriture est le fait de `write_seed_files` (`tool/exporters/mod_seed.py:45`) et `_build_mod` (`tool/__main__.py:62`) |
| Le pipeline est-il déterministe ? | Oui, à triplet `(dump vanilla, config, seed_value)` identique — voir [`nondeterminism.md`](nondeterminism.md) |
| Le pipeline valide-t-il ? | Oui, mais **après** construction : la validation (`tool/generator/pipeline.py:412`) n'échoue jamais la génération, elle loggue |

## 2. Les trois fonctions d'orchestration

Tout le pipeline tient dans trois fonctions de `tool/generator/pipeline.py`.

| Fonction | Ligne | Rôle | Retourne |
|----------|-------|------|----------|
| `_build_prefix` | `tool/generator/pipeline.py:34` | Préfixe rejouable : starter → électricité → gel → fluides → gisements → nonfinite → snapshot `base` | `(starter, base, patches, lake_list, lake_res, bfa)` |
| `generate_seed` | `tool/generator/pipeline.py:135` | Config, distribution, tirages lakes/patches, arbitrage des passes A/B | `seed` complet |
| `_finalize_pipeline` | `tool/generator/pipeline.py:269` | Suffixe : récursion → fusée → usage → relais → prologue → ease-up → techs → validation → assemblage | `seed` complet |

`_build_prefix` et `_finalize_pipeline` existent **pour** le rejeu des late raws
(§6.2/§6.3) : le gating exige de rejouer le préfixe *depuis avant le starter*, pas
seulement la récursion — voir `tool/generator/pipeline.py:38-45`.

## 3. Chronologie des jalons

### 3.1 Préparation

| # | Jalon | Appel exact | Effet |
|---|-------|-------------|-------|
| 0 | Normalisation de la config | `tool/generator/pipeline.py:143` — `_cfg.full_config(config, strict_sections=False)` | Fusionne `config/defaults.yaml` + surcharges, valide contre le schéma (`tool/common/config.py:392`). `strict_sections=False` tolère les clés racine hors schéma (`seed`…) des sweeps et tests ; **le contenu des sections connues reste validé strictement** (`tool/common/config.py:265-268`). Le résultat est une copie profonde : les mutations locales ne fuient jamais vers l'appelant |
| 1 | Distribution de la config | `tool/generator/pipeline.py:146-151` — `recipes`, `starter_chain`, `recursive_phase`, `relay_phase`, `tech_tree`, `easeup_phase` `.set_config(cfg)` | Chaque module lit ses réglages via `default_value` ; aucun module n'a de valeur de secours codée en dur (`tool/common/config.py:10-12`) |
| 2 | Flux RNG principal | `tool/generator/pipeline.py:153` — `map_patches.make_rng(db.seed_value)` | Flux partagé par toutes les phases qui reçoivent `rng` en paramètre |

### 3.2 Tirages de carte (avant le préfixe)

| # | Jalon | Appel exact | Entrée → sortie | RNG |
|---|-------|-------------|-----------------|-----|
| 3 | **Phase 1bis** — Lacs de fluide | `tool/generator/pipeline.py:159` — `lakes.generate_lakes(lakes.make_rng(db.seed_value), db, cfg)` | `VanillaDB`, config `lakes` → `list[Lake]` (`tool/generator/lakes.py:26-35`) | `randputF:lakes:` (`tool/generator/lakes.py:41`) |
| 4 | **Phase 1** — Patchs de ressources | `tool/generator/pipeline.py:164` — `map_patches.generate_patches(rng, db, cfg, lake_resources=...)` | `VanillaDB`, resources des lacs → `list[Patch]` (`tool/generator/map_patches.py:20-49`) | `randputF:` (`tool/generator/map_patches.py:54`) |

**Pourquoi les lacs avant les patchs** : l'invariant C6 — un fluide déjà en lac
n'est jamais re-tiré en patch. Tirés dans l'autre ordre, il faudrait
défaire/rejouer des patchs ; ici l'exclusion est un simple filtre d'entrée
(`available()`, `tool/generator/map_patches.py:81`).

Tirages internes des lacs : `count = rng.randint(low, high)`
(`tool/generator/lakes.py:60`), `rng.shuffle(candidates)`
(`tool/generator/lakes.py:70`), richesse par `rng.randint`
(`tool/generator/lakes.py:75`).

### 3.3 Préfixe rejouable (`_build_prefix`, 8 jalons)

| # | Jalon | Ligne | Action | Entrée → sortie |
|---|-------|-------|--------|-----------------|
| 5 | **Phase 2** — Chaîne starter | `tool/generator/pipeline.py:55` — `starter_chain.build_starter_chain(rng, db, patches, has_lakes=..., lake_resources=...)` | `list[Patch]` → `StarterChain` (`tool/generator/starter_chain.py:40-60`) : extracteurs, transformateur, lab, premier pack, transports, kit |
| 6 | **Phase 3** — Électricité | `tool/generator/pipeline.py:69` — `electricity.resolve_electricity(rng, db, starter, lake_resources, used_resources)` | Choisit un générateur fonctionnel (C1). Retourne des **réparations** `(kind, value)` appliquées aux listes en place (`tool/generator/pipeline.py:72-76`) |
| 7 | Bootstrap inline | `tool/generator/pipeline.py:81-84` — `starter.state.early.add_sources(...)` | Les ressources ajoutées par les réparations sont obtenables **sans** électricité → intègrent le watershed de l'oracle actif |
| 8 | Rejeu des macro-techs starter | `tool/generator/pipeline.py:88` — `starter_chain.build_tech_steps(starter.state, db)` | Les recettes créées par l'électricité doivent être unlockées par une tech, jamais orphelines |
| 9 | Gel des promesses + extinction de l'oracle | `tool/generator/pipeline.py:95-100` — `starter.promises = {...}` puis `starter.state.early.deactivate()` | Snapshot des produits des recettes gratuites. Dès ici la récursion re-tire sans contrainte early ; `ensure_obtainable`/`make_recipe` garantissent qu'aucun produit promis n'est re-baké |
| 10 | **Phase 2bis** — Fluides de bâtiments | `tool/generator/pipeline.py:108` — `building_fluids.assign_building_fluids(rng, db, starter.state, lake_res)` | `{bâtiment: {input, output?}}`. Fusionné avec les assignations de l'électricité, la clé faisant autorité (`tool/generator/pipeline.py:113-115`) |
| 11 | **Phase 1ter** — Gisements | `tool/generator/pipeline.py:121` — `map_patches.assign_patch_gisements(patches, db.seed_value, cfg)` | Centre, rayon, `well_seed`, `count` par patch. Flux `randputF:wells:` (`tool/generator/map_patches.py:238`) |
| 12 | **Phase 1ter-bis** — Nonfinite | `tool/generator/pipeline.py:127` — `map_patches.apply_nonfinite_randomisation(patches, db.seed_value, cfg)` | Richesse/rayon/count × facteurs. Flux `randputF:nonfinite:` (`tool/generator/map_patches.py:328`) |
| 13 | **Instantané gelé `base`** | `tool/generator/pipeline.py:131` — `copy.deepcopy(starter.state)` | `base` est la **source exclusive du pool** des recettes relais (§9.3) et ease-up. Après cette ligne, plus rien n'y écrit |

> `patches` et `lake_list` sont modifiés **en place** par le jalon 6. L'appelant
> doit passer des copies — c'est ce que font les **quatre** appels de
> `_build_prefix` (`tool/generator/pipeline.py:181`, `192`, `214`, `236`), chacun
> sur `list(pre_patches)` / `list(pre_lake_list)`. Le jalon 14b et 14e rejouent
> ainsi le préfixe depuis le même état.

### 3.4 Arbitrage des passes (late raws)

| # | Jalon | Ligne | Action |
|---|-------|-------|--------|
| 14a | Lecture de la config late raws | `tool/generator/pipeline.py:179` — `late_raws.LateRawsConfig.from_config(cfg)` (`tool/generator/late_raws.py:44`) | `enabled=false` → chemin court, **une seule passe** (`tool/generator/pipeline.py:181-187`) : comportement historique |
| 14b | **Passe A** (mesure) | `tool/generator/pipeline.py:192-198` | Snapshot RNG (`getstate`, ligne 191) puis préfixe + suffixe complets avec `validate=False`. Produit `seed_a` : le graphe **non gaté** |
| 14c | Plan de gating | `tool/generator/pipeline.py:199` — `late_raws.plan_from_seed(seed_a, lr_cfg)` | Mesure la dépendance et décide un **jalon** par raw non-startup : échelon = tier du premier consommateur |
| 14d | Gating **inerte** | `tool/generator/pipeline.py:200-220` | Si aucune raw n'est réellement retenue (tous jalons ≤ 0), la passe B ne changerait que la forme de l'arbre sans changer la disponibilité. La seed A est rendue telle quelle (régression seed 1757) |
| 14e | **Passe B** (rejeu dégradé) | `tool/generator/pipeline.py:230-243` | Les jalons sont posés **dans la config** avant le run : `starter_cfg["deferred"] = sorted(map(list, plan.gated))` (ligne 231). `cfg` est **recopié** (lignes 232-233), jamais muté en place. Puis `rng.setstate(pre_rng_state)` (ligne 235) et rejeu du préfixe complet, `late_raws.degrade(starter.state, base, plan)` (ligne 239) |

**Invariant du rejeu** : les deux passes partent du **même** `rng.getstate()` et
des **mêmes** copies de `patches`/`lake_list`. Le code exécuté est identique ; seul
le `cfg["starter"]["deferred"]` diffère. C'est ce qui rend le rejeu déterministe.

> La copie défensive de `cfg` (14e) est un correctif de non-déterminisme *intra-processus* :
> sans elle, `deferred` fuyait vers la seed suivante du même process (régression
> seed 1269) — voir `nondeterminism.md` §7.

### 3.5 Suffixe (`_finalize_pipeline`, 12 jalons)

| # | Jalon | Ligne | Action | Sortie |
|---|-------|-------|--------|--------|
| 15 | **Phase 4** — Récursion pondérée | `tool/generator/pipeline.py:292` — `recursive_phase.expand_recursive(rng, db, patches, starter, lake_res, late_plan=...)` | Coverage items, armes de véhicules, packs science, bâtiments fluidiques. Peuple les pas de techs du module |
| 16 | **Phase 4ter** — Chaîne fusée | `tool/generator/pipeline.py:299` — `endgame_phase.ensure_rocket_chain(rng, db, starter.state)` | Passe **avant** les relais : aucun ingrédient environnemental n'entre dans les recettes de fusée |
| 17 | **Phase 4ter-bis** — Garantie d'usage dure | `tool/generator/pipeline.py:308` — `usage_pass.enforce_usage(db, starter.state, starter, steps, cfg)` | Corrige U1 (usage non nul) et U2 (bâtiment débloqué avant son premier usage). Ne touche que `crafted_in`/`category` |
| 18 | **Phase 4bis** — Relais | `tool/generator/pipeline.py:320` — `relay_phase.build_relay_recipes(rng, db, starter.state, base)` | Recettes « propres » pour les produits qui consommaient du environnemental. Pool d'ingrédients et bâtiments pris depuis `base` |
| 19 | **Phase 4ter** — Techs de prologue | `tool/generator/pipeline.py:336` — `relay_phase.consolidate_intro_steps(relay_phase.dispatch_relay_steps(relays, rng), trigger_candidates, rng)` | ≤ 5 unlocks par tech. Déclencheur = **hand-craft** d'un item du bootstrap : `unit` vide, `research_trigger` au craft |
| 20 | **Ease-up** | `tool/generator/pipeline.py:357` — `easeup_phase.build_ease_up_recipes(easeup_rng, db, starter.state, base, ..., steps_rng=easeup_rng)` | Recettes alternatives pour les crafts trop lourds. Détection sur le graphe **final** |
| 21 | **Phase 5** — Arbre technologique | `tool/generator/pipeline.py:371-373` puis `404` — `tech_tree.build_linear_tech_tree(all_tech_steps, rng, db)` | Ordre : techs starter gratuites → prologue → ease-up → récursif → fusée. Les seules gratuites sont celles du starter (`tool/generator/pipeline.py:409`) |
| 22 | **Phase 4quater** — Timing extracteurs | `tool/generator/pipeline.py:383` — `extractor_timing.apply_extractor_timing(db, starter, all_tech_steps, seed_value=..., patch_resources=..., lake_resources=...)` | « Juste-au-besoin » : `kept` / `moved` / `random`. Flux `randputf:extractor-timing:` (`tool/generator/extractor_timing.py:457`) |
| 23 | Ré-application de la garantie d'usage | `tool/generator/pipeline.py:396` | Les relais et ease-up ont été créés **après** la passe primaire ; leurs bâtiments d'hébergement peuvent être profonds. Passe idempotente, sur l'ordre final |
| 24 | **Phase 6** — Validation | `tool/generator/pipeline.py:412-427` — `pipeline_validator.validate_pipeline(state, technologies, db, patch_resources, lake_resources)` | **Loggue** (`log.warning` / `log.info`), ne lève pas. Recettes validées = `starter.recipes + recursive_phase.recipes_to_seed()` |
| 25 | Assemblage de la seed | `tool/generator/pipeline.py:430-485` | Voir §4 |
| 26 | Replan late raws | `tool/generator/pipeline.py:496-498` | Le plan exporté est **remesuré sur la seed finale**, pas sur la seed de mesure A : le trigger de la 1re tech payante et le rapport C3 de B peuvent différer de A |
| 27 | **Phase 6bis** — Quantités de craft | `tool/generator/pipeline.py:505` — `craft_quantity.apply_craft_quantity(seed, cfg)` | Post-assemblage, flux `randputF:craft_quantity:` (`tool/generator/craft_quantity.py:34`). Inerte si `craft_quantity.enabled` est faux |

## 4. Structure de la seed en sortie

Assemblée à `tool/generator/pipeline.py:430-485`.

| Clé | Ligne | Contenu | Source |
|-----|-------|---------|--------|
| `meta` | 431 | `{seed, generator_version, factorio_version}` | `db.seed_value`, `VERSION`, `FACTORIO_VERSION` |
| `pools.item_resources` | 437 | Liste triée des items beltables | `db.beltable_items()` |
| `pools.fluid_resources` | 438 | Liste triée des fluides pipables | `db.pipable_fluids()` |
| `pools.vehicle_weapons` | 441 | Pool d'armes montées | `recursive_phase.vehicle_weapons_pool()` |
| `pools.vehicle_range_scaling` | 444 | `{base_size, scale}` | `recursive_phase.vehicle_range_scaling()` |
| `pools.raw_resources` | 448 | Patchs + environnement + fluides d'extraction, **lacs inclus** | `db.raw_resources(...)` |
| `map.patches` / `map.lakes` | 454 | Sérialisations | `p.to_seed()` / `la.to_seed()` |
| `starter_kit` | 456 | `[{type, name, count}]` | `starter.kit` |
| `free_researches` | 457 | IDs des techs starter | `starter.free_researches` |
| `extractor_timing` | 462 | Rapport kept/moved/random | Jalon 22. **Consommé par l'audit et les tests, ignoré par le mod** |
| `late_raws` | 469 | `{startup, gated}` ou `null` | `_export_late_raws` (`tool/generator/pipeline.py:246`). `null` = carte infinie d'office |
| `wreck` | 472 | `{loot, counts}` | `wreck_loot.build_wreck_config(cfg, db)`. `counts` = loi 0..3 par slot, somme = 100 |
| `recipes` | 473 | Recettes starter + récursif | `starter.recipes + recursive_phase.recipes_to_seed()` |
| `technologies` | 474 | Arbre linéaire | Jalon 21 |
| `progression_order` | 475 | IDs dans l'ordre | `[t["id"] for t in technologies]` |
| `vehicle_armament` | 476 | `{véhicule: [armes]}` | `recursive_phase.vehicle_armament()` |
| `building_fluid_assignments` | 481 | `{bâtiment: {input, output?}}` | Fusion : **les assignations du récursif écrasent** celles de `building_fluids` |

La clé `difficulty` est injectée **à l'export**, jamais dans le pipeline
(`tool/exporters/mod_seed.py:53-58`).

## 5. Les flux RNG du pipeline

Fabrique unique : `make_seeded_rng` (`tool/common/rng.py:15-23`), qui construit
`random.Random(f"{prefix}{seed_value}")`.

| Préfixe | Fabriquée | Consommée par |
|---------|----------|---------------|
| `randputF:` | `tool/generator/map_patches.py:54` | **Flux principal** partagé : patchs, starter, électricité, récursion, relais, tech tree |
| `randputF:lakes:` | `tool/generator/lakes.py:41` | Lacs |
| `randputF:wells:` | `tool/generator/map_patches.py:238` | Gisements par patch |
| `randputF:nonfinite:` | `tool/generator/map_patches.py:328` | Facteurs nonfinite |
| `randputf:bootstrap-miner:` | `tool/generator/starter_chain.py:110` | Foreuse pré-alimentation du kit |
| `randputf:chest:` | `tool/generator/starter_chain.py:141` | Coffre(s) du kit |
| `randputF:easeup:` | `tool/generator/easeup_phase.py:57` | Ease-up (flux isolé : additif pur, une seed régénérée = la précédente + les ease-up) |
| `randputf:extractor-timing:` | `tool/generator/extractor_timing.py:457` | Timing extracteurs |
| `randputF:craft_quantity:` | `tool/generator/craft_quantity.py:34` | Montants de craft |

Deux flux sont **positionnés et rejoués** plutôt que recréés : le flux principal
via `getstate()`/`setstate()` aux jalons 14b/14d/14e. C'est le mécanisme qui
permet aux deux passes de partir du même point.

## 6. Invariants du pipeline

| Invariant | Garanti par | Test |
|-----------|-------------|------|
| C6 — un fluide n'est jamais patch **et** lac | `available()` (`tool/generator/map_patches.py:81`) | `tests/test_pipeline_invariants.py` |
| Aucun produit promis n'est re-baké après le gel | `starter.promises` + `ensure_obtainable`/`make_recipe` | `tests/test_pipeline_invariants.py` |
| `base` n'est jamais écrit après le gel | `copy.deepcopy` au jalon 13 ; seules des copies en sont lues | `tests/test_pipeline_invariants.py` |
| Les recettes du starter sont unlockées, jamais orphelines | rejeu des techs au jalon 8 | `tests/test_pipeline_invariants.py` |
| La seed est byte-à-byte identique entre processus | `tests/test_determinism.py:50` (seeds 1337 et 1299, `PYTHONHASHSEED` 0/1) | — |
| La seed ne dépend pas de sa position dans un même process | copie défensive de `cfg` au jalon 14e | `test_seed_1757_gating_inerte_victoire_comme_baseline` |
| L'ordre des modules ne fuit pas entre deux seeds du même process | reset des globals en tête de `expand_recursive` (`tool/generator/recursive_phase.py:121-127`) | `tests/test_seed_graph.py` |
| La victoire reste possible (chaîne fusée non bloquée) | jalon 16 | `tests/test_witness.py` |

## 7. État global des modules

`recursive_phase` est le seul module à état global significatif
(`tool/generator/recursive_phase.py:38-49`) : `_tech_steps`,
`_unlocked_science_packs`, `_raw_resources`, `_heat_prereq_emitted`, `_fluid_pity`,
`_fluid_steps`.

Ces listes sont **remises à zéro** en tête de `expand_recursive`
(`tool/generator/recursive_phase.py:121-127`) — une graine par process est donc
isolée, mais **une graine par appel** l'est aussi : les lectures publiques
`steps()` (ligne 585), `recipes_to_seed()` (591), `vehicle_armament()` (344) ne
sont valides qu'immédiatement après `expand_recursive`.

## 8. Chemin d'échec et reprise du CLI

`randputf generate` (`tool/__main__.py:140`) ne fait pas confiance à la
validation logguée : il relance `validate_seed` (`tool/validator/solver.py:15`,
indépendante de `pipeline_validator`) et **retente avec une graine dérivée**.

| Situation | Comportement |
|-----------|--------------|
| `--seed N` fourni | Dérive déterministe `N+1, N+2…` (`tool/__main__.py:167`) — l'horloge ne remplace jamais la valeur demandée |
| `--seed` absent | Base = `int(time.time() * 1000)` re-tirée au début de la boucle (`tool/__main__.py:158`) |
| 10 tentatives infructueuses | `sys.exit(2)` après impression des 10 premiers problèmes (`tool/__main__.py:163-166`) |

## 9. Lectures associées

- [`architecture.md`](architecture.md) — vue d'ensemble du dépôt et de la data-stage.
- [`nondeterminism.md`](nondeterminism.md) — les flux RNG, les pièges corrigés, les gardes.
- [`seed.md`](seed.md) — la structure `seed.json` et le sens de chaque champ.
- [`solvabilite.md`](solvabilite.md) — `pipeline_validator` (structure) vs `solver` (solvabilité).
- [`DEVIANCES.md`](DEVIANCES.md) — écarts assumés, dont le raccourci de gating inerte.