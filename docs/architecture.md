# Architecture et pipeline technique

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 4. Architecture générale

Le système repose sur trois composants distincts :

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

La génération complète est effectuée **hors du jeu**, par un outil Python.
Raisons :

- Factorio ne permet **pas** de modifier les ingrédients d'une recette au
  runtime via l'API : tout doit être construit en *data-stage*. Le tool écrit
  donc les fichiers que le mod consommera à ce moment-là ;
- la **solvabilité** d'une seed (§15) est vérifiable hors du jeu, avant même
  de lancer Factorio — on refuse une seed injouable plutôt que de laisser le
  joueur tomber sur un blocage ;
- Python est choisi pour sa simplicité de développement et de débogage.

### 4.2 Formats de fichiers

- **YAML** pour les fichiers de configuration (lisibles, commentables) ;
- **JSON** pour les données générées consommées par le mod (seed, graphe,
  définitions de recettes/techs) ;
- d'autres formats pourront compléter si besoin.

### 4.3 Mod Factorio

En *data-stage*, le mod lit la configuration et la seed puis construit :

- une **entité ressource cachée** pour chaque item beltable et chaque fluide
  pipable candidat (des centaines), sans autoplace par défaut — elles ne
  seront placées que sur décision du runtime ;
- toutes les **recettes** générées ;
- tout l'**arbre technologique**.

Au runtime (*control.lua*), le mod :

- remplace les champs de ressources vanilles lors de la génération de la
  surface et place les entités ressources tirées par la seed ;
- gère les déblocages progressifs, le kit de départ, les recherches
  gratuites.

## 17. Pipeline technique

Chaîne complète, de l'écriture d'une seed à une partie jouable :

1. `config/settings.yaml` — paramètres généraux (fourchettes, pondérations,
   pools, récursion/armes montées, loot du site de crash §7).
2. Tool Python :
   1. parse les prototypes vanilla 2.0 (items beltables, fluides pipables,
      bâtiments avec leurs slots/directives par tier) ;
   2. tire le graphe complet depuis la seed (phases §6 → §14) ;
   3. vérifie les invariants de solvabilité (§15) ;
   4. écrit `seed.json` (+ données associées) dans le dossier du mod.
3. Mod Factorio, data-stage : lecture YAML/JSON → construction des entités
   ressources cachées, des recettes et de l'arbre technologique.
4. Runtime (`control.lua`) : génération de la surface (placement des patchs
   tirés, remplacement des ressources vanilles), kit de départ, recherches
   gratuites, déblocages progressifs au fil des recherches.

## 18. Structure du projet

```
randputF/
├── README.md            # utilisateur : installation / jouer
├── IDEES.md             # idées / corrections workshop
├── docs/                # conception : ce dossier + tags.md, nondeterminism.md
├── .gitignore
├── pyproject.toml       # package Python (randputf, ≥3.11)
├── config/              # configurations YAML
│   └── settings.yaml
├── data/                # dump des prototypes vanilla
│   └── vanilla_dump.json
├── tool/                # générateur externe Python
│   ├── __main__.py      # CLI : parse, audit, generate
│   ├── common/          # VanillaDB, ItemDef, demo, WeightedPicker
│   │   ├── db.py
│   │   ├── demo.py
│   │   ├── png_icon.py        # génération d'icônes PNG (seed_graph)
│   │   └── weighted_picker.py
│   ├── audit/           # audit des tags bâtiments/items (invariants C8)
│   │   └── tags.py
│   ├── parsers/         # extraction des prototypes vanilla
│   │   └── vanilla.py
│   ├── generator/       # moteur de tirage & graphe
│   │   ├── pipeline.py          # orchestrateur (generate_seed)
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
│   │   ├── tech_tree.py         # arbre technologique linéaire
│   │   └── wreck_loot.py        # loot du site de crash
│   ├── prototypes/      # classes de config (RecipeConfig, RecursiveConfig…)
│   │   ├── base.py             # PrototypeConfig (base)
│   │   ├── recipes.py          # RecipeConfig (§9.2 : énergie, équilibre)
│   │   ├── recursive.py        # RecursiveConfig (§9 : poids, armes montées §12.1)
│   │   ├── starter.py          # StarterConfig (§7/§8 : ammo_count, inserter_chance)
│   │   ├── relay.py            # RelayConfig (§9.5)
│   │   ├── easeup.py           # EaseupConfig (§9.3)
│   │   ├── craft_quantity.py   # expérimental — testé, non branché à la pipeline
│   │   ├── difficulty_knobs.py # expérimental — testé, non branché
│   │   ├── nonfinite_randomisation.py # A1 — BRANCHÉ (map_patches.apply_nonfinite_randomisation)
│   │   ├── rare_resources.py   # expérimental — testé, non branché
│   │   └── progressive_extractors.py # expérimental — testé, non branché
│   ├── exporters/       # écriture seed.json / seed.lua / locale / graphe
│   │   ├── mod_seed.py         # seed.json + seed.lua
│   │   └── seed_graph.py       # graphe interactif HTML (seed.graph.html)
│   └── validator/       # vérification de solvabilité
│       ├── pipeline_validator.py  # 7 checks sur ProgressionState
│       └── solver.py              # validation du seed dict assemblé
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

Le graphe interactif (`seed.graph.html`, exporté par `tool/exporters/seed_graph.py`)
est documenté pour l'utilisateur dans le README racine (section « Le graphe
interactif ») — c'est une sortie joueur, pas une pièce de conception.

(La structure fine pourra évoluer pendant l'implémentation ; les rôles de
haut niveau restent ceux décrits en §4.)
