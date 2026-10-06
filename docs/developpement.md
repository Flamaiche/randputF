# Développement : roadmap et mise en route

Partie de la doc de conception randputF (dev). Retour : [docs/README.md](README.md).

## 19. Roadmap

1. **v1 — vanilla seul** : mise en œuvre intégrale (starter récursif, électricité, armes, arbre linéaire, fusée).
2. **Évolutions v1** :
   - Évolution possible de l'arbre linéaire vers un arbre **branché**.
   - Création automatique de seed (date/heure) — fait (§16).
3. **Utiliser le moteur du jeu (vision extracteur)** : basculer l'extraction des prototypes côté jeu (exporter Lua). Le jeu intègre l'ensemble de ses prototypes (vanilla + mods) : l'exporter évalue les capacités côté moteur, l'outil Python se charge uniquement du tri et de la validation. Finalité : accepter les **mods tiers** sans réécrire le code de l'outil.
   - Classement fonctionnel des bâtiments (`research/transformer/generator/distribution/extractor/other`) transféré dans `exporter/control.lua` (dérivé des aptitudes natives de Factorio 2.0).
   - Stackabilité réelle, types de munitions, compatibilité des combustibles, dépendances (robot↔roboport, solaire↔accumulateur).
   - Diminution des heuristiques inscrites en dur dans `tool/common/db.py` au strict minimum (séparer choix de conception et données moteur).
   Le rôle du Python demeure inchangé : trier, produire la seed, contrôler la solvabilité (§15).

> **Lacs : pose runtime déterministe** (fait, substitut à l'autoplace resource, cf. §7.5). Les motivations de ce choix (creusage `control.lua`, abandon de l'autoplace) figurent dans [DEVIANCES.md](DEVIANCES.md) §1.

## 20. Mise en route

### 20.1 Environnement de développement

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

`pip install .` (standard) intègre les assets (`mod/`, `data/`, `config/` avec `defaults.yaml`) au sein du wheel — ``tool.common.assets.asset_path`` résout ces éléments avec un repli sur le dépôt ; il s'agit de la procédure documentée pour une installation sans copie de travail (consulter le témoin de la release).

### 20.2 Récupérer la base vanilla (une fois par version du jeu)

L'outil n'effectue aucune déduction : il exploite un **dump JSON des prototypes** issu de votre propre partie, via le mod compagnon `exporter/` :

1. copiez (ou créez un lien symbolique vers) `exporter/` dans `~/.factorio/mods/randputf-exporter_0.1.0/` ; en l'absence de détection du lien symbolique (isolation Flatpak), recourez à une copie du répertoire ;
2. **désactivez `randputF` pour cet export** (l'action sera rejetée par l'exporter dans le cas contraire) ; exécutez Factorio durant quelques secondes — l'initialisation génère le fichier `script-output/randputF/vanilla_dump.json` au sein du répertoire user-data ;
3. transférez ce fichier vers `data/vanilla_dump.json` dans le projet ;
4. l'exporter demeure un utilitaire de développement connexe, voué à disparaître ou à être intégré au mod principal.

> **Pourquoi désactiver `randputF` pour l'export** : la pollution induite par un export avec « les deux mods actifs » ne se limite pas à l'ajout de recettes `randputf-*` — certains prototypes vanilla subissent des MODIFICATIONS sur place (par ex. `fuel_value` initialisé à 200 000 au lieu de 0 sur `crude-oil`, filtres de chaudières, `fuel_categories`), soit des valeurs proches d'un contenu authentique provoquant la divergence de la seed sans altérer le fonctionnement. Mesures de protection : l'exporter bloque un export altéré (journalisation, absence de fichier), l'outil rejette un dump déjà modifié (invariant vanilla 2.0 `fuel_value == 0`), le filtre `randputf-` prend en charge le canal additif des exports antérieurs (`test_dump_pollution.py`).

### 20.3 Générer et jouer une seed

```bash
.venv/bin/python -m tool parse --demo      # vérifie la base (mode synthétique)
.venv/bin/python -m tool generate          # génère + valide (seed temporelle par défaut)
.venv/bin/python -m tool generate --seed 5 # seed figée, déterministe (reproductible)
```

En l'absence de l'argument `--seed`, la seed provient de l'horodatage actuel (millisecondes, §16) ; avec `--seed <n>`, la valeur identique réplique rigoureusement le même mod.

**Installation dans Factorio** — le chemin du répertoire de mods se configure dans `config/user.yaml`, via la clé `paths.factorio_mods` (chemin absolu, par exemple `~/.var/app/com.valvesoftware.Steam/.factorio/mods` dans le cadre d'une installation Steam sous flatpak ; la valeur par défaut `""` est définie dans `config/defaults.yaml`). Ensuite :

```bash
.venv/bin/python -m tool generate --seed 5 --install
```

L'option `--install` assemble le mod et le place dans `factorio_mods/randputF_<version>/` (version récupérée depuis `mod/info.json`) tout en actualisant `mod-list.json`. Si le dossier `factorio_mods` est introuvable ou absent, le mod est compilé dans `output/` et son chemin s'affiche afin de permettre une copie manuelle. Au démarrage de Factorio : les patchs générés remplacent l'intégralité des ressources vanilla autour de la zone d'apparition, le kit de départ est appliqué et les recherches gratuites sont débloquées.

### 20.4 État actuel du code

| Composant | État |
|---|---|
| `tool/common/rng.py` | `make_seeded_rng(seed_value, prefix)` : flux RNG par phase (préfixe `randputF:`/`randputf:` indexé par seed) — toute nouvelle phase DOIT exploiter son propre flux, le préfixe demeurant **byte-identique** d'une exécution à l'autre (déterminisme, cf. nondeterminism.md) |
| `tool/common/tagsets.py` | Ensembles d'identifiants centralisés en UNE source unique (D3) : `ENVIRONMENTAL_ITEMS`, `ROCKET_CHAIN`, `VEHICLE_GUNS`, `NON_STACKABLE_ITEM_TYPES`, `VALID_RECIPE_CATEGORIES`, `RAIL_TYPES`, `VIRTUAL_ITEM_TYPES`, `FLUID_RECIPE_CATEGORIES`, `STARTER_TRANSFORMERS`, `EXCLUDED_BUILDINGS`, `ENDGAME_EXCLUDED` — index `docs/tags.md §14` |
| `tool/parsers/vanilla.py` | Normalisation du dump vers `VanillaDB` (objets/fluides/bâtiments catégorisés/recettes) |
| `tool/generator/map_patches.py` | Phase 1 active (3–8 patchs, typologies aléatoires, richesses variables) ; éléments exclus des patchs par garantie (labo §8, fusée + silo §14) ; **packs de science exclus des patchs** (§13) |
| `tool/generator/starter_chain.py` | Équipement de départ (arme + munitions assorties), extraction→transformation→transport, pool environnemental, extracteurs réservés aux objets, **bâtiment de recherche inclus dans la seconde recherche gratuite** (§8) + **premier pack de science fabricable** (§13) + **remblai (landfill) garanti en présence de lacs** (§7) |
| `tool/generator/recursive_phase.py` | Phase récursive pondérée (déblocage progressif, **revendication anti-recette-orpheline** §9.3) ; productions = intermédiaires (exclusion des objets de type bâtiment et de la chaîne de la fusée ; **équilibre consommation/production** dans `_pick_product`) ; **coût systématique en pack de science**, amorcé par le premier pack fabricable du starter **avec solution de repli garantie** (§13) ; **cadence garantie des pylônes** (§9.4) ; **garantie d'éléments compagnons** (§9.7) |
| `tool/generator/electricity.py` | Générateur et combustible fournis à la demande (accumulateur exclu du tirage ; **mélange des générateurs, test opérationnel, correction par patch forcé — 20 tentatives avant échec** §10) + **pylône/infrastructure de distribution** ; technologies de départ rejouées par la suite (§10) |
| `tool/generator/endgame_phase.py` | Chaîne de la fusée inaltérable : les 3 composants de `rocket-part` **ainsi que le rocket-silo** sont générés, technologie finale `randputf-endgame-rocket` (§14) |
| `tool/generator/extractor_timing.py` | Chronologie de déblocage des extracteurs (C3 : kept/moved/random) avec réutilisation de la fermeture `_startup_raw_resources` (boîte D4bis) pour la planification des jalons (§6.3) |
| `tool/generator/late_raws.py` | Jalons « late raws » (§6.3) : planification évaluée sur la **passe A** (ressources brutes soumises à conditions non initiales, seuils via `_usage_floors` = composants + ateliers `crafted_in` + fermeture des coûts/déclencheurs) suivie d'une **dégradation** du pool lors de la passe B ; exportation de `seed["late_raws"]` |
| `tool/prototypes/starter.py` | `StarterConfig` (§7/§8) intègre également le paramètre `deferred` : les ressources brutes soumises à conditions demeurent exclues du pool initial durant la passe B (état vierge) |
| `tool/replay/player.py` | Simulateur de relecture de seed (audit externe) : validation 10× du rendement, point fixe de la liste de travail (worklist inverse), production d'un rapport `ReplayReport` (blocker, mastered, never_masterable, victory) |
| `tools/classify_late_raws.py` | Analyseur de classification `(seed, extracteur, raw)` : catégorie C3, fermeture de la zone d'apparition, échelon du premier consommateur — outil de mesure des jalons |
| `tools/audit_playthrough.py` / `tools/audit_usage.py` | Explorateurs du relecteur par plage de seeds (audit par lots, CSV incrémental) |
| `tool/common/demo.py` | Base vanilla synthétique dédiée au développement et aux tests : intègre le bâtiment **rocket-silo** afin de permettre à la phase finale de débloquer `randputf-rocket-silo` (validation d'exhaustivité §15) |
| `tool/generator/relay_phase.py` | Recettes relais sélectionnées au sein du **pool figé en début de partie** (après starter et électricité) accompagnées des technologies de prologue `randputf-prologue-*` (≤5 déblocages, fabrication manuelle) (§7, §9.5, §13) |
| `tool/generator/tech_tree.py` | Arbre linéaire constitué à partir des macro-étapes ; **déblocage unique par recette** (la première revendication l'emporte, §13/§15) |
| `tool/validator/pipeline_validator.py` | 7 contrôles §15 : prévention des cycles par **point fixe de solvabilité** (itinéraires relais considérés comme des alternatives), progression constante, cohérence entre technologies et recettes, obtention effective des coûts, application de la règle des tuyaux, complétude de la fusée, absence de ressource brute dans les packs |
| `tool/validator/solver.py` | Contrôle de conformité du dictionnaire de seed assemblé (structure, champs obligatoires) |
| `mod/data.lua` | Analyse de la seed : entités de ressources masquées, recettes, technologies ; option de neutralisation de l'arbre vanilla |
| `mod/data-updates.lua` | Réajustement des véhicules (duplication des armes §12.1), dalles de lacs et teintes pastel, uniformisation des combustibles, pompe offshore à haut débit |
| `mod/control.lua` | Exécution (runtime) : suppression des ressources vanilla, remplissage des lacs par propagation (flood-fill), placement déterministe des patchs, attribution du kit de départ, octroi des recherches gratuites |

La génération valide une seed complète en s'appuyant sur la base vanilla authentique (`data/vanilla_dump.json`, incluse dans le dépôt). La graine est spécifiée par l'intermédiaire de `--seed N` (en son absence : calculée à partir de l'heure courante) — le fichier de configuration yaml ne contient **aucune seed** par défaut. Le mode démonstration (`parse --demo`) demeure pertinent pour tester le moteur à partir d'une base synthétique allégée.
