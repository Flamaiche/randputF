# Développement : roadmap et mise en route

Partie de la doc de conception randputF (dev). Retour : [docs/README.md](README.md).

## 19. Roadmap

1. **v1 — vanilla seul** : implémentation complète de tout ce document
   (starter récursif, électricité, armes, arbre linéaire, fusée).
2. **Fins d'implémentation v1** :
   - passage possible de l'arbre technologique linéaire à un arbre **branché** ;
   - génération automatique de seed (date/heure) — *fait* (seed temporelle
     par défaut, §16).
3. **Utiliser le moteur du jeu (vision extracteur)** : au lieu d'encoder les
   règles de lecture du contenu en dur dans le tool Python, faire de
   l'exporter (= le jeu, qui CONNAÎT déjà tous ses prototypes et ceux des
   mods chargés) la source de vérité. À l'init d'une partie, l'exporter
   extrait **tout** (ressources + bâtiments déjà présents, vanilla et futurs
   mods confondus) et calcule **côté moteur** comment tout fonctionne, puis
   l'outil ne fait que **trier et valider** ces données. Conséquence directe :
   le support des **mods tiers** (Krastorio, Py, …) passe **sans rien recoder
   dans l'outil** — on ne parse plus le contenu à la main, le moteur le
   décrit.
   Cible précise de la refonte (aujourd'hui en dur dans le Python) :
   - classification fonctionnelle des bâtiments (`research`/`transformer`/
     `generator`/`distribution`/`extractor`/`other`) — déplacée dans
     `_parse_entity` c'est-à-dire `exporter/control.lua`, déduite des
     capacités prototypes (`crafting_categories`, `resource_categories`,
     `energy_source`, `get_max_power_output`, `stack_size`…) que Factorio 2.0
     expose déjà nativement ;
   - stackabilité réelle, catégories de munitions, compatibilité combustible,
     dépendances (robot↔roboport, solaire↔accumulateur) ;
- réduction des listes/heuristiques en dur de `tool/common/db.py`
      (`ROCKET_CHAIN`, `NON_STACKABLE_ITEM_TYPES`, `VEHICLE_GUNS`;
      `POWER_POLES` et `TOOL_LIKE_ITEMS` supprimés, migrés vers
      `is_power_pole` / `is_virtual_item`) à celles qui sont du *choix de
      conception* du randomizer et non une *donnée moteur*.
   Le Python garde son rôle réel : trier, générer la seed, vérifier la
   solvabilité §15 — il ne re-découvre plus le contenu à la main.
    **Lacs : pose runtime déterministe** (remplace l'autoplace resource, cf.
    §7.5). Le scatter `resource-autoplace` sur des TUILES fait chevaucher les
    nappes de départ et laisse un seul liquide (le dernier, d'ordre le plus
    élevé) dominer — vérifié headless, un rework `autoplace tile` seul ne
    garantissait pas non plus un équilibre. La pose a donc été migrée vers un
    **creusage `control.lua`** (`on_chunk_generated`) : une nappe discrète de
    rayon fixe par fluide choisi, positionnée sur un anneau équiréparti autour
    du spawn — aucune superposition, surface maîtrisée, tous les liquides
    pompables. Le mapgen pose **0** tuile de lac (override
    `property_expression_names["tile:<lac>:probability"]` = `randputf-no-water`,
    comme l'eau vanilla §7.5) ; la tuile reste créée/inscrite pour
    `set_tiles`, la palette et la liste du menu de génération. On conserve du
    système antérieur : la couleur/copie de tuile, la berge (tous les lacs
    bordés, redessinée au runtime par `set_tiles(..., correct_tiles = true)`,
    §7.5), la compatibilité pompe offshore (lien §7.5/§16).

## 20. Mise en route

### 20.1 Environnement de développement

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

`pip install .` (classique) embarque les assets (`mod/`, `data/`,
`config/` avec `defaults.yaml`) dans le wheel — ``tool.common.assets.asset_path``
les résout avec repli dépôt ; c'est le chemin documenté pour un install sans
checkout (voir le témoin de la release).

### 20.2 Récupérer la base vanilla (une fois par version du jeu)

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

### 20.3 Générer et jouer une seed

```bash
.venv/bin/python -m tool parse --demo      # vérifie la base (mode synthétique)
.venv/bin/python -m tool generate          # génère + valide (seed temporelle par défaut)
.venv/bin/python -m tool generate --seed 5 # seed figée, déterministe (reproductible)
```

Sans `--seed`, la seed est tirée de l'instant présent (millisecondes, §16) ;
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

### 20.4 État actuel du code

| Composant | État |
|---|---|
| `tool/common/rng.py` | `make_seeded_rng(seed_value, prefix)` : flux RNG par phase (préfixe `randputF:`/`randputf:` indexé par seed) — toute nouvelle phase DOIT prendre son propre flux, le préfixe étant **byte-identique** à travers les runs (déterminisme, cf. nondeterminism.md) |
| `tool/common/tagsets.py` | Ensembles de noms figés en UNE source (D3) : `ENVIRONMENTAL_ITEMS`, `ROCKET_CHAIN`, `VEHICLE_GUNS`, `NON_STACKABLE_ITEM_TYPES`, `VALID_RECIPE_CATEGORIES`, `RAIL_TYPES`, `VIRTUAL_ITEM_TYPES`, `FLUID_RECIPE_CATEGORIES`, `STARTER_TRANSFORMERS`, `EXCLUDED_BUILDINGS`, `ENDGAME_EXCLUDED` — index `docs/tags.md §14` |
| `tool/parsers/vanilla.py` | Normalisation dump → `VanillaDB` (items/fluides/bâtiments classés/recettes) |
| `tool/generator/map_patches.py` | Phase 1 implémentée (3–8 patchs, types aléatoires, richesse variable) ; briques garanties jamais en patch (lab §8, fusée + silo §14) ; **science packs jamais en patch** (§13) |
| `tool/generator/starter_chain.py` | Kit de départ (arme + munitions calées), extraction→transformation→transport, pool environnemental, extracteurs items-only, **bâtiment de recherche dans la 2e recherche gratuite** (§8) + **premier science pack craftable** (§13) + **landfill garanti si lacs** (§7) |
| `tool/generator/recursive_phase.py` | Phase récursive pondérée (déblocage sur le tas, **claim anti-recette-orpheline** §9.3) ; produits = intermédiaires (jamais un item de bâtiment ni la chaîne fusée ; **équilibre cons/prod** dans `_pick_product`) ; **coût systématique en science pack**, amorcé par le premier pack craftable du starter **avec repli garanti** (§13) ; **cadence garantie des pylônes** (§9.4) ; **garantie de compagnons** (§9.7) |
| `tool/generator/electricity.py` | Générateur + combustible à la demande (accumulateur exclu du tirage ; **shuffle des générateurs, test de fonctionnalité, réparation par patch forcé — 20 essais puis erreur** §10) + **pylône/construction de distribution** ; techs starter rejouées ensuite (§10) |
| `tool/generator/endgame_phase.py` | Chaîne fusée intable : les 3 ingrédients de `rocket-part` **et le rocket-silo** générés, tech finale `randputf-endgame-rocket` (§14) |
| `tool/generator/extractor_timing.py` | Timing de déblocage des extracteurs (C3 : kept/moved/random) + fermeture `_startup_raw_resources` (boîte D4bis) réutilisée par le plan des jalons (§6.3) |
| `tool/generator/late_raws.py` | Jalons « late raws » (§6.3) : plan mesuré sur la **passe A** (raws non-startup gatées, planchers via `_usage_floors` = ingrédients + ateliers `crafted_in` + fermeture coûts/déclencheurs) + **dégradation** du pool en passe B ; export `seed["late_raws"]` |
| `tool/prototypes/starter.py` | `StarterConfig` (§7/§8) porte aussi `deferred` : les raws gatées restent hors du pool de départ en passe B (état vierge) |
| `tool/replay/player.py` | Rejoueur de seed (audit externe) : maîtrise 10× sortie, point fixe worklist (worklist inverse), rapport `ReplayReport` (blocker, mastered, never_masterable, victory) |
| `tools/classify_late_raws.py` | Classification `(seed, extracteur, raw)` : bucket C3, fermeture boîte du spawn, échelon du 1er consommateur — outil de mesure des jalons |
| `tools/audit_playthrough.py` / `tools/audit_usage.py` | Balayages rejoueur par plage de seeds (audit par paquet, CSV incrémental) |
| `tool/common/demo.py` | Base vanilla synthétique pour dev/tests : inclut le building **rocket-silo** pour que la phase endgame licence `randputf-rocket-silo` (validation de complétude §15) |
| `tool/generator/relay_phase.py` | Recettes relais tirées dans le **pool gelé du début de run** (après starter+électricité) + techs de prologue `randputf-prologue-*` (≤5 unlocks, hand-craft) (§7, §9.5, §13) |
| `tool/generator/tech_tree.py` | Arbre linéaire assemblé depuis les macro-steps ; **unlock unique par recette** (premier claim gagne, §13/§15) |
| `tool/validator/pipeline_validator.py` | 7 checks §15 : anti-cycle par **point fixe de solvabilité** (routes relais = alternatives), progressivité, cohérence tech-recettes, coûts obtainables, règle des tuyaux, complétude fusée, packs sans ressource brute |
| `tool/validator/solver.py` | Validation du seed dict assemblé (format, champs requis) |
| `mod/data.lua` | Lit la seed : entités ressources cachées, recettes, technologies ; option désactivation arbre vanilla |
| `mod/data-updates.lua` | Réarmement véhicules (clonage armes §12.1), tuiles lacs + couleurs pastel, fuel unifié, pompe offshore extra-fluid |
| `mod/control.lua` | Runtime : destruction ressources vanilles, flood-fill lacs, placement patchs déterministe, kit départ, recherches gratuites |

La génération valide une seed complète sur la base vanilla réelle
(`data/vanilla_dump.json`, committée dans le dépôt). La graine est donnée via
`--seed N` (absente : tirée du temps courant) — le yaml de config ne porte
**aucune seed** par défaut. Le mode demo (`parse --demo`) reste utile pour
tester le moteur sur une base synthétique légère.
