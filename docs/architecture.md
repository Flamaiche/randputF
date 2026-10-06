# Architecture et pipeline technique

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 4. Architecture générale

Le système comprend trois parties distinctes :

```
┌─────────────────────┐      ┌──────────────────────────┐      ┌─────────────────┐
│   Tool externe      │      │   Mod Factorio           │      │  Runtime        │
│   Python            │ ───► │   data-stage             │ ───► │  control.lua    │
│                     │      │                          │      │                 │
│ • parse vanilla     │ YAML │ • lit config + seed      │      │ • placement des │
│ • génère le graphe  │ JSON │ • construit entités      │      │   patchs        │
│ • valide solvabilité│      │   ressources cachées     │      │ • déblocages    │
│ • écrit la seed     │      │ • construit recettes/    │      │   progressifs   │
│                     │      │   techs depuis la seed   │      │ • kit départ    │
└─────────────────────┘      └──────────────────────────┘      └─────────────────┘
```

### 4.1 Tool externe (Python)

La génération de la seed se fait entièrement hors du jeu via un outil Python.
Motifs :

- Factorio ne permet pas de modifier les ingrédients d'une recette au runtime
  par l'API : tout s'effectue en *data-stage*. Le tool écrit donc les fichiers
  nécessaires pour cette étape ;
- la solvabilité d'une seed (§15) se vérifie en amont, avant de lancer
  Factorio, ce qui évite les parties bloquées ;
- Python offre un cadre simple pour le développement et le débogage.

### 4.2 Formats de fichiers

- **YAML** pour les paramètres de configuration (accessibles et commentables) ;
- **JSON** pour les données de la seed et les définitions générées lues par le
  mod ;
- d'autres formats viendront s'ajouter si nécessaire.

### 4.3 Mod Factorio

Durant le *data-stage*, le mod charge la configuration et la seed pour créer :

- une entité ressource cachée pour chaque item transportable par convoyeur et
  chaque fluide transportable par tuyau éligible (plusieurs centaines), sans
  autoplace par défaut — leur apparition dépend uniquement du runtime ;
- l'ensemble des recettes générées ;
- l'intégralité de l'arbre technologique.

Pendant l'exécution (*control.lua*), le mod :

- applique les patchs de ressources lors de la génération de la surface selon
  les choix de la seed ;
- pilote les déblocages progressifs, le kit de départ et les recherches
  gratuites.

## 17. Pipeline technique

Le déroulement complet, de la création d'une seed au lancement d'une partie :

1. `config/defaults.yaml` regroupe les paramètres généraux (seuils, poids,
   pools, récursion/armes embarquées, butin du site de crash §7). Les réglages
   de `config/user.yaml` s'y ajoutent avant d'être validés (§Note config).
2. L'outil Python s'exécute :
   1. il analyse les prototypes de base de Factorio 2.0 (items sur convoyeurs,
      fluides en tuyaux, bâtiments et leurs emplacements par niveau) ;
   2. il calcule le graphe complet à partir de la seed (phases §6 à §14) en
      effectuant deux passes sur la même source aléatoire si le jalonnement
      des late raws est actif (§6.3 : la passe A mesure les dépendances, la
      passe B relance le départ sur un pool réduit, l'état initial étant
      conservé via `StarterConfig.deferred`) ;
   3. il contrôle les règles de solvabilité (§15) ;
   4. il enregistre `seed.json` et ses annexes dans le dossier du mod.
3. Le mod Factorio lit les fichiers YAML et JSON en *data-stage* pour bâtir les
   ressources cachées, les recettes et les technologies.
4. Le code d'exécution (`control.lua`) prend le relais pour façonner la carte
   (placement des patchs, substitution des ressources d'origine), distribuer
   le kit de départ, attribuer les recherches gratuites et gérer les
   déblocages séquentiels.

Ce résumé présente les grandes étapes. Le détail des jalons, des flux de
génération aléatoire et des contrôles se trouve dans [`pipeline.md`](pipeline.md),
tandis que la description du code Lua fichier par fichier est accessible dans
[`runtime.md`](runtime.md).

## 18. Structure du projet

```
randputF/
├── README.md            # utilisateur : installation / jouer
├── README_EN.md         # version anglophone du README
├── CHANGELOG.md         # résumé des versions (hautes lumières par version)
├── docs/                # conception : ce dossier + tags.md, nondeterminism.md
├── .gitignore
├── pyproject.toml       # package Python (randputf, ≥3.11)
├── config/              # configurations YAML
│   ├── defaults.yaml    # réglages par défaut (source unique, non modifiable)
│   └── user.yaml        # surcharges utilisateur (facultatives, validées)
├── data/                # dump des prototypes vanilla
│   └── vanilla_dump.json
├── tool/                # générateur externe Python
│   ├── __main__.py      # CLI : parse, audit, generate
│   ├── common/          # VanillaDB, ItemDef, demo, WeightedPicker, config
│   │   ├── db.py
│   │   ├── demo.py
│   │   ├── png_icon.py        # génération d'icônes PNG (seed_graph)
│   │   ├── rng.py             # make_seeded_rng : flux RNG déterministe par phase
│   │   ├── tagsets.py         # ensembles de noms figés (source unique, tags.md §14)
│   │   ├── weighted_picker.py
│   │   ├── config.py          # les deux YAML : fusion profonde + validation stricte
│   │   ├── assets.py          # résolution des assets (prototypes, icônes)
│   │   ├── version.py         # version unique (source : mod/info.json)
│   │   └── witness.py         # témoin de déterminisme (docs/witness.md)
│   ├── audit/           # audits : tags (invariants C8), difficulté
│   │   ├── tags.py
│   │   └── difficulty.py      # ardoise des ressources brutes pour finir une run
│   ├── parsers/         # extraction des prototypes vanilla
│   │   └── vanilla.py
│   ├── generator/       # moteur de tirage & graphe
│   │   ├── pipeline.py          # orchestrateur (generate_seed, passes A/B)
│   │   ├── map_patches.py       # phase 1 : ressources au sol
│   │   ├── lakes.py             # phase 1bis : lacs de fluide
│   │   ├── starter_chain.py     # phase 2 : chaîne initiale
│   │   ├── building_fluids.py   # phase 2bis : fluides des bâtiments fixes (§6)
│   │   ├── recursive_phase.py   # phase 3 : récursion + balayage contenu
│   │   ├── electricity.py       # phase 3 : résolution électricité
│   │   ├── endgame_phase.py     # phase 4 : chaîne fusée
│   │   ├── relay_phase.py       # relais ressources non-infinies + prologue
│   │   ├── easeup_phase.py      # recettes alternatives crafts lourds (§9.3)
│   │   ├── recipes.py           # primitives recettes (make_recipe, ensure_obtainable)
│   │   ├── extractor_timing.py  # timing de déblocage C3 (+ boîte D4bis)
│   │   ├── late_raws.py         # jalons late raws (§6.3) : plan passe A + dégradation
│   │   ├── early_oracle.py      # watershed « obtenable avant le réseau » (§10ter)
│   │   ├── bootstrap_guard.py   # DIAGNOSTIC seul (tests) — plus une passe pipeline
│   │   ├── usage_pass.py        # U1/U2 : rattachement d'usage, gardes anti-cycle
│   │   ├── heat.py              # phase chaleur (triade source/transport/sink, §10bis)
│   │   ├── craft_quantity.py    # C1 : facteur multiplicatif sur les quantités
│   │   ├── tech_tree.py         # arbre technologique linéaire
│   │   └── wreck_loot.py        # loot du site de crash
│   ├── prototypes/      # classes de config (RecipeConfig, RecursiveConfig…)
│   │   ├── base.py             # PrototypeConfig (base)
│   │   ├── recipes.py          # RecipeConfig (§9.2 : énergie, équilibre)
│   │   ├── recursive.py        # RecursiveConfig (§9 : poids, armes montées §12.1)
│   │   ├── starter.py          # StarterConfig (§7/§8 : ammo_count, inserter_chance, deferred)
│   │   ├── relay.py            # RelayConfig (§9.5)
│   │   ├── easeup.py           # EaseupConfig (§9.3)
│   │   ├── craft_quantity.py   # CraftQuantityConfig (miroir du module generator)
│   │   ├── usage.py            # UsageConfig (D2 : garantie d'usage dure)
│   │   ├── difficulty_knobs.py # expérimental — testé, non branché
│   │   ├── nonfinite_randomisation.py # A1 — BRANCHÉ (map_patches.apply_nonfinite_randomisation)
│   │   ├── rare_resources.py   # expérimental — testé, non branché
│   │   └── progressive_extractors.py # expérimental — testé, non branché
│   ├── exporters/       # écriture seed.json / seed.lua / locale / graphe
│   │   ├── mod_seed.py         # seed.json + seed.lua
│   │   └── seed_graph.py       # graphe interactif HTML (seed.graph.html)
│   ├── replay/          # audit externe : rejoueur de seed (player.py)
│   └── validator/       # vérification de solvabilité
│       ├── pipeline_validator.py  # 7 checks sur ProgressionState
│       └── solver.py              # validation du seed dict assemblé
├── tools/               # scripts dev : audit_playthrough, audit_usage, classify_late_raws
├── mod/                 # le mod Factorio 2.0
│   ├── data.lua         # data-stage : lecture seed, construction
│   ├── data-updates.lua # réarmement véhicules, lacs, fuel unifié
│   ├── control.lua      # runtime : carte, déblocages, kit
│   ├── locale/          # localisations (en, fr)
│   └── seed/            # seed.json et données générées
├── exporter/            # mod compagnon (dump JSON des prototypes)
├── tests/               # tests unitaires (pytest)
└── output/              # mod assemblé (généré)
```

Le graphe interactif (`seed.graph.html`, produit par `tool/exporters/seed_graph.py`)
est documenté pour les joueurs dans le README principal (section « Le graphe
interactif ») et pour sa conception dans [graphe-interactif.md](graphe-interactif.md).
Il sert à la fois de visualisation pour l'utilisateur et d'élément du système,
combinant l'exploitation des données du produit, les icônes du jeu et un
format de fichier autonome.

L'organisation interne pourra évoluer au fil des développements, mais les rôles
principaux restent ceux présentés au §4.
