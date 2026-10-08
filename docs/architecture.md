# Architecture et pipeline technique

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 4. Architecture générale

Le système s'articule autour de trois composants clés :

```
┌─────────────────────┐      ┌──────────────────────────┐      ┌─────────────────┐
│   Tool externe      │      │   Mod Factorio           │      │  Runtime        │
│   Python            │ ───► │   data-stage             │ ───► │  control.lua    │
│                     │      │                          │      │                 │
│ • parse vanilla     │ seed │ • charge seed.lua        │      │ • placement des │
│ • génère le graphe  │ .lua │ • construit entités      │      │   patchs        │
│ • valide solvabilité│      │   ressources cachées     │      │ • déblocages    │
│ • écrit la seed     │      │ • construit recettes/    │      │   progressifs   │
│                     │      │   techs depuis la seed   │      │ • kit départ    │
└─────────────────────┘      └──────────────────────────┘      └─────────────────┘
```

### 4.1 Tool externe (Python)

La génération de la seed s'effectue en dehors du jeu grâce à un outil en Python.
Pourquoi ce choix ?

- L'API de Factorio interdit de modifier les ingrédients d'une recette au runtime : tout se fige durant le *data-stage*. L'outil Python prépare et écrit donc les fichiers requis pour cette phase ;
- La solvabilité de la seed (§15) est validée en amont, évitant de lancer Factorio pour se retrouver bloqué en cours de partie ;
- Python fournit un environnement idéal pour développer, tester et déboguer rapidement.

### 4.2 Formats de fichiers

- **YAML** pour configurer le mod de manière lisible et commentée ;
- **JSON** pour stocker la seed générée et ses définitions ;
- D'autres formats pourront s'ajouter selon les besoins futurs.

### 4.3 Mod Factorio

Pendant le *data-stage*, le mod charge uniquement la seed via `require("seed.seed")` (le fichier `seed.lua`). Aucun fichier `yaml` ou `json` n'est lu par les scripts `mod/*.lua`, et `seed.json` n'est jamais lu par le code Lua (le champ `pools` de la seed reste d'ailleurs une variable locale morte dans `mod/data.lua:18`). Le mod utilise ces données pour générer :

- Les entités de ressources au sol : le mod ne crée pas des centaines d'entités cachées. En réalité, `mod/data-updates.lua:125-155` génère uniquement les entités `randputf-minerai-*` et `randputf-oil-*` requises pour les patchs de la seed (entre 3 et 8 ressources dédupliquées). La liste complète `seed.pools` (qui contient 209 items et 8 fluides) sert exclusivement à `vehicle_range_scaling` dans `mod/data-updates.lua:18` ;
- L'ensemble des recettes générées ;
- L'intégralité de l'arbre technologique.

Pendant l'exécution en jeu (`control.lua`), le mod :

- Place les patchs de ressources lors de la génération de la carte selon les paramètres de la seed ;
- Gère les déblocages progressifs, distribue le kit de départ et attribue les recherches gratuites.

## 17. Pipeline technique

Voici les étapes clés, de la génération de la seed jusqu'au lancement de votre partie :

1. `config/defaults.yaml` centralise les paramètres généraux (seuils, poids, pools, récursion, armes embarquées, butin du site de crash §7). L'utilisateur peut surcharger ces valeurs dans `config/user.yaml`, l'ensemble étant validé par `config.py`.
2. L'outil Python entre en scène :
   1. Il extrait les prototypes de base de Factorio 2.0 (items sur convoyeurs, fluides en tuyaux, bâtiments et leurs emplacements par niveau) ;
   2. Il génère le graphe complet à partir de la seed (phases §6 à §14). Si le jalonnement des late raws est actif (voir la section des ressources §6 ou §6.5), il effectue deux passes sur la même source aléatoire : la passe A évalue les dépendances, puis la passe B relance le départ sur un pool restreint, l'état initial restant préservé via `StarterConfig.deferred` ;
   3. Il valide rigoureusement les règles de solvabilité (§15) ;
   4. Il écrit `seed.json` et ses fichiers annexes directement dans le répertoire du mod.
3. Lors du *data-stage*, le mod Factorio charge uniquement le fichier `seed.lua` pour assembler les ressources, les recettes et les technologies.
4. Enfin, le code d'exécution (`control.lua`) prend le relais en jeu : il façonne la carte (placement des patchs et remplacement des ressources d'origine), distribue le kit de départ, offre les recherches gratuites et orchestre les déblocages séquentiels.

Ce survol pose les bases. Pour plonger dans le détail des jalons, des flux aléatoires et des contrôles, consultez [`pipeline.md`](pipeline.md). L'analyse pas à pas du code Lua est disponible dans [`runtime.md`](runtime.md).

## 18. Structure du projet

```
randputF/
├── LICENSE              # licence du projet
├── README.md            # utilisateur : installation / jouer
├── README_EN.md         # version anglophone du README
├── CHANGELOG.md         # résumé des versions (hautes lumières par version)
├── conftest.py          # configuration des tests pytest
├── .gitignore
├── pyproject.toml       # package Python (randputf, ≥3.11)
├── atelier/             # outils de travail et scripts de build
├── notes/               # notes de recherche et de conception
├── docs/                # conception : ce dossier + tags.md, nondeterminism.md
├── config/              # configurations YAML
│   ├── defaults.yaml    # réglages par défaut (source unique, non modifiable)
│   └── user.yaml        # surcharges utilisateur (facultatives, validées)
├── data/                # dump des prototypes vanilla
│   └── vanilla_dump.json
├── tool/                # générateur externe Python
│   ├── __main__.py      # CLI : parse, audit, generate, difficulty, witness
│   ├── service.py       # service d'orchestration (202 lignes)
│   ├── common/          # VanillaDB, ItemDef, demo, WeightedPicker, config
│   │   ├── db.py
│   │   ├── demo.py
│   │   ├── png_icon.py        # génération d'icônes PNG (seed_graph)
│   │   ├── rng.py             # make_seeded_rng : flux RNG déterministe par phase
│   │   ├── tagsets.py         # ensembles de noms figés (source unique, tags.md §14)
│   │   ├── weighted_picker.py
│   │   ├── config.py          # les deux YAML : fusion profonde + validation stricte
│   │   ├── assets.py          # résolution des dossiers mod/ (info.json), data/ (vanilla_dump.json) et config/ (defaults.yaml)
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
│   │   ├── electricity.py       # Phase 3 : résolution électricité
│   │   ├── recursive_phase.py   # Phase 4 : récursion + balayage contenu
│   │   ├── endgame_phase.py     # Phase 4ter : chaîne fusée
│   │   ├── relay_phase.py       # relais ressources non-infinies + prologue
│   │   ├── easeup_phase.py      # recettes alternatives pour les crafts lourds (voir config.md ou la passe 20 de pipeline.md)
│   │   ├── recipes.py           # primitives recettes (make_recipe, ensure_obtainable)
│   │   ├── extractor_timing.py  # timing de déblocage C3 (+ boîte D4bis)
│   │   ├── late_raws.py         # jalons late raws (voir ressources.md §6 ou §6.5) : plan passe A + dégradation
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
│   │   ├── easeup.py           # EaseupConfig (voir config.md ou la passe 20 de pipeline.md)
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
│   ├── info.json        # métadonnées du mod
│   ├── data.lua         # data-stage : lecture seed, construction
│   ├── data-updates.lua # réarmement véhicules, lacs, fuel unifié
│   ├── data-final-fixes.lua # ajustements finaux du data-stage
│   ├── control.lua      # runtime : carte, déblocages, kit
│   ├── graphics/        # éléments graphiques du mod
│   ├── locale/          # localisations (en, fr)
│   └── seed/            # seed.json et données générées
├── exporter/            # mod compagnon (dump JSON des prototypes)
├── tests/               # tests unitaires (pytest)
└── output/              # mod assemblé (généré)
```

Le graphe interactif (`seed.graph.html`, généré par `tool/exporters/seed_graph.py`) est présenté aux joueurs dans le README principal (section « Le graphe interactif ») et détaillé techniquement dans [graphe-interactif.md](graphe-interactif.md). Cet outil sert d'interface visuelle et de brique système, unissant données générées, icônes du jeu et format autonome.

Bien que la structure interne puisse évoluer au fil du développement, les rôles fondamentaux restent fidèles à l'architecture du §4.
