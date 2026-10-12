# Développement : roadmap et mise en route

Partie de la doc de conception randputF (dev). Retour : [docs/README.md](README.md).

## Roadmap

1. **v1 — vanilla seul** : implémentation complète (starter récursif, électricité,
   armes, arbre linéaire, fusée).
2. **Évolutions v1** :
   - Passage possible de l'arbre linéaire à un arbre **branché**.
   - Génération automatique de seed (date/heure) — fait ([seed.md](seed.md#seed-et-configuration)).
3. **Utiliser le moteur du jeu (vision extracteur)** : déplacer l'extraction
   des prototypes côté jeu (exporter Lua). Le jeu connaît déjà tous ses
   prototypes (vanilla + mods) : l'exporter calcule les capacités côté moteur,
   l'outil Python se contente de trier et de valider. Objectif : permettre le
   support de **mods tiers** sans tout recoder dans l'outil.
   - Classification fonctionnelle des bâtiments (`research/transformer/generator/
     distribution/extractor/other`) déplacée dans `exporter/control.lua`
     (déduite des capacités natives de Factorio 2.0).
   - Stackabilité réelle, catégories de munitions, compatibilité combustible,
     dépendances (robot↔roboport, solaire↔accumulateur).
   - Réduction des heuristiques codées en dur dans `tool/common/db.py` au
     strict nécessaire (différencier choix de conception vs données moteur).
   Le Python reste sur son rôle : trier, générer la seed, vérifier la
   solvabilité ([invariants.md](invariants.md#règles-de-solvabilité)).

> **Lacs : pose runtime déterministe** (fait, remplace l'autoplace resource,
> cf. [starter.md](starter.md#la-phase-de-démarrage) (point 5)). Le détail du choix (creusage `control.lua`, pourquoi l'autoplace
> a été abandonné) est dans [DEVIANCES.md](DEVIANCES.md#dérives-de-gameplay-assumées-design-du-mod).

## Mise en route

### Environnement de développement

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

`pip install .` (classique) embarque les assets (`mod/`, `data/`,
`config/` avec `defaults.yaml`) dans le wheel — ``tool.common.assets.asset_path``
les résout avec repli dépôt ; c'est le chemin documenté pour un install sans
checkout (voir le témoin de la release).

### Récupérer la base vanilla (une fois par version du jeu)

Le tool ne devine rien : il consomme un **dump JSON des prototypes** produit
par ton propre jeu, via le mod compagnon `exporter/` :

1. copie (ou symlink) `exporter/` dans `~/.factorio/mods/randputf-exporter_0.1.0/` ;
   si le symlink n'est pas détecté (sandbox Flatpak), utilise une copie du dossier ;
2. **désactive `randputF` pour cet export** (l'exporter refuse sinon) ; lance
   Factorio une partie quelques secondes — à l'init, il écrit
   `script-output/randputF/vanilla_dump.json` dans le dossier user-data ;
3. copie ce fichier dans `data/vanilla_dump.json` du projet ;
4. l'exporter reste un outil compagnon de développement, destiné à disparaître
   ou fusionner dans le mod principal.

> **Pourquoi désactiver `randputF` pour l'export** : la pollution d'un export
> « les deux mods actifs » n'est pas que des recettes `randputf-*` ajoutées —
> des prototypes vanilla sont MUTÉS en place (ex. `fuel_value` 0 → 200 000 sur
> `crude-oil`, filtres boiler, `fuel_categories`), des valeurs qui ressemblent à
> du contenu légitime et qui font diverger la seed sans rien casser. Barrières :
> l'exporter refuse un export pollué (log, aucun fichier), le tool rejette un
> dump déjà muté (invariant vanilla 2.0 `fuel_value == 0`), le filtre `randputf-`
> couvre le canal additif des dumps anciens (`test_dump_pollution.py`).

### Générer et jouer une seed

```bash
.venv/bin/python -m tool parse --demo      # vérifie la base (mode synthétique)
.venv/bin/python -m tool generate          # génère + valide (seed temporelle par défaut)
.venv/bin/python -m tool generate --seed 5 # seed figée, déterministe (reproductible)
```

Sans `--seed`, la seed est tirée de l'instant présent (millisecondes, [seed.md](seed.md#seed-et-configuration)) ;
avec `--seed <n>`, la même valeur reproduit exactement le même mod.

**Installation dans Factorio** — le chemin du dossier mods se surcharge dans
`config/user.yaml`, clé `paths.factorio_mods` (dossier complet, ex.
`~/.var/app/com.valvesoftware.Steam/.factorio/mods` pour un install Steam
flatpak ; le défaut `""` vit dans `config/defaults.yaml`). Ensuite :

```bash
.venv/bin/python -m tool generate --seed 5 --install
```

`--install` assemble le mod et le copie dans `factorio_mods/randputF_<version>/`
(version lue dans `mod/info.json`)
en mettant à jour `mod-list.json`. Si `factorio_mods` est absent ou
introuvable, le mod est assemblé dans `output/` et son chemin est affiché
pour copie manuelle. Au lancement de Factorio : les patchs tirés remplacent
toutes les ressources vanilles autour du spawn, le kit de départ est injecté,
les recherches gratuites déblocées.

### État actuel du code

| Composant | État |
|---|---|
| `tool/common/rng.py` | `make_seeded_rng(seed_value, prefix)` : flux RNG par phase (préfixe `randputF:`/`randputf:` indexé par seed) — toute nouvelle phase DOIT prendre son propre flux, le préfixe étant **byte-identique** à travers les runs (déterminisme, cf. nondeterminism.md) |
| `tool/common/tagsets.py` | Ensembles de noms figés en UNE source (D3) : `ENVIRONMENTAL_ITEMS`, `ROCKET_CHAIN`, `VEHICLE_GUNS`, `NON_STACKABLE_ITEM_TYPES`, `VALID_RECIPE_CATEGORIES`, `RAIL_TYPES`, `VIRTUAL_ITEM_TYPES`, `FLUID_RECIPE_CATEGORIES`, `STARTER_TRANSFORMERS`, `EXCLUDED_BUILDINGS`, `ENDGAME_EXCLUDED` — index [`docs/tags.md`](tags.md#ensembles-dérivés-en-dur-résiduels) |
| `tool/parsers/vanilla.py` | Normalisation dump → `VanillaDB` (items/fluides/bâtiments classés/recettes) |
| `tool/generator/map_patches.py` | Phase 1 implémentée (3–8 patchs, types aléatoires, richesse variable) ; briques garanties jamais en patch (lab [starter.md](starter.md#la-chaîne-initiale-starter), fusée + silo [tech.md](tech.md#fin-de-partie)) ; **science packs jamais en patch** ([tech.md](tech.md#larbre-technologique)) |
| `tool/generator/starter_chain.py` | Kit de départ (arme + munitions calées), extraction→transformation→transport, pool environnemental, extracteurs items-only, **bâtiment de recherche dans la 2e recherche gratuite** ([starter.md](starter.md#la-chaîne-initiale-starter)) + **premier science pack craftable** ([tech.md](tech.md#larbre-technologique)) + **landfill garanti si lacs** ([starter.md](starter.md#la-phase-de-démarrage)) |
| `tool/generator/recursive_phase.py` | Phase récursive pondérée (déblocage sur le tas, **claim anti-recette-orpheline** [recettes.md](recettes.md#déblocage-sur-le-tas)) ; produits = intermédiaires (jamais un item de bâtiment ni la chaîne fusée ; **équilibre cons/prod** dans `_pick_product`) ; **coût systématique en science pack**, amorcé par le premier pack craftable du starter **avec repli garanti** ([tech.md](tech.md#larbre-technologique)) ; **cadence garantie des pylônes** ([recettes.md](recettes.md#cadence-garantie-des-pylônes)) ; **garantie de compagnons** ([recettes.md](recettes.md#garantie-de-compagnons)) |
| `tool/generator/electricity.py` | Générateur + combustible à la demande (accumulateur exclu du tirage ; **shuffle des générateurs, test de fonctionnalité, réparation par patch forcé — 20 essais puis erreur** [energie.md](energie.md#lélectricité)) + **pylône/construction de distribution** ; techs starter rejouées ensuite ([energie.md](energie.md#lélectricité)) |
| `tool/generator/endgame_phase.py` | Chaîne fusée intable : les 3 ingrédients de `rocket-part` **et le rocket-silo** générés, tech finale `randputf-endgame-rocket` ([tech.md](tech.md#fin-de-partie)) |
| `tool/generator/extractor_timing.py` | Timing de déblocage des extracteurs (C3 : kept/moved/random) + fermeture `_startup_raw_resources` (boîte D4bis) réutilisée par le plan des jalons ([pipeline.md](pipeline.md#arbitrage-des-passes-late-raws)) |
| `tool/generator/late_raws.py` | Jalons « late raws » (pipeline.md) : plan mesuré sur la **passe A** (raws non-startup gatées, planchers via `_usage_floors` = ingrédients + ateliers `crafted_in` + fermeture coûts/déclencheurs) + **dégradation** du pool en passe B ; export `seed["late_raws"]` |
| `tool/prototypes/starter.py` | `StarterConfig` ([starter.md](starter.md#la-phase-de-démarrage)/[starter.md](starter.md#la-chaîne-initiale-starter)) porte aussi `deferred` : les raws gatées restent hors du pool de départ en passe B (état vierge) |
| `tool/replay/player.py` | Rejoueur de seed (audit externe) : maîtrise 10× sortie, point fixe worklist (worklist inverse), rapport `ReplayReport` (blocker, mastered, never_masterable, victory) |
| `tools/classify_late_raws.py` | Classification `(seed, extracteur, raw)` : bucket C3, fermeture boîte du spawn, échelon du 1er consommateur — outil de mesure des jalons |
| `tools/audit_playthrough.py` / `tools/audit_usage.py` | Balayages rejoueur par plage de seeds (audit par paquet, CSV incrémental) |
| `tool/common/demo.py` | Base vanilla synthétique pour dev/tests : inclut le building **rocket-silo** pour que la phase endgame licence `randputf-rocket-silo` (validation de complétude [invariants.md](invariants.md#règles-de-solvabilité)) |
| `tool/generator/relay_phase.py` | Recettes relais tirées dans le **pool gelé du début de run** (après starter+électricité) + techs de prologue `randputf-prologue-*` (≤5 unlocks, hand-craft) ([starter.md](starter.md#la-phase-de-démarrage), [recettes.md](recettes.md#relais-des-ressources-non-infinies), [tech.md](tech.md#larbre-technologique)) |
| `tool/generator/tech_tree.py` | Arbre linéaire assemblé depuis les macro-steps ; **unlock unique par recette** (premier claim gagne, [tech.md](tech.md#larbre-technologique)/[invariants.md](invariants.md#règles-de-solvabilité)) |
| `tool/validator/pipeline_validator.py` | 7 checks [invariants.md](invariants.md#règles-de-solvabilité) : anti-cycle par **point fixe de solvabilité** (routes relais = alternatives), progressivité, cohérence tech-recettes, coûts obtainables, règle des tuyaux, complétude fusée, packs sans ressource brute |
| `tool/validator/solver.py` | Validation du seed dict assemblé (format, champs requis) |
| `mod/data.lua` | Lit la seed : entités ressources cachées, recettes, technologies ; option désactivation arbre vanilla |
| `mod/data-updates.lua` | Réarmement véhicules (clonage armes [combat.md](combat.md#armes-montées-randomisées)), tuiles lacs + couleurs pastel, fuel unifié, pompe offshore extra-fluid |
| `mod/control.lua` | Runtime : destruction ressources vanilles, flood-fill lacs, placement patchs déterministe, kit départ, recherches gratuites |

La génération valide une seed complète sur la base vanilla réelle
(`data/vanilla_dump.json`, committée dans le dépôt). La graine est donnée via
`--seed N` (absente : tirée du temps courant) — le yaml de config ne porte
**aucune seed** par défaut. Le mode demo (`parse --demo`) reste utile pour
tester le moteur sur une base synthétique légère.

## Lectures associées

- **Concepts liés** : [modules.md](modules.md) ; [release.md](release.md) ; [config.md](config.md) ; [witness.md](witness.md)
