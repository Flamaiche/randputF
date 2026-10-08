# Développement : roadmap et mise en route

Partie de la doc de conception randputF (dev). Retour : [docs/README.md](README.md).

## 19. Roadmap

1. **v1 — vanilla seul** : implémentation complète (starter récursif, électricité, armes, arbre linéaire, fusée).
2. **Évolutions v1** :
   - Transition possible de l'arbre linéaire vers un arbre **branché**.
   - Génération automatique de seed (date/heure) — fait (§16).
3. **Exploiter le moteur du jeu (vision extracteur)** : déporter l'extraction des prototypes côté jeu via l'exporter Lua. Le jeu contenant déjà tous les prototypes (vanilla et mods), l'exporter évaluera les capacités côté moteur. L'outil Python se concentrera sur le tri et la validation. Objectif : supporter les **mods tiers** sans modifier le code de l'outil.
   - Le classement fonctionnel des bâtiments (`research/transformer/generator/distribution/extractor/other`) sera transféré dans `exporter/control.lua` (déduit des propriétés natives de Factorio 2.0).
   - Gestion de la stackabilité réelle, des types de munitions, de la compatibilité des combustibles et des dépendances (robot↔roboport, solaire↔accumulateur).
   - Réduction au strict minimum des heuristiques codées en dur dans `tool/common/db.py` pour séparer la conception des données du moteur.
   Le rôle de l'outil Python restera identique : trier, générer la seed et valider la solvabilité (§15).

> **Lacs : génération déterministe au runtime** (fait, remplace l'autoplace des ressources, voir §7.5). Les raisons de ce choix (génération via `control.lua`, abandon de l'autoplace) sont détaillées dans [DEVIANCES.md](DEVIANCES.md) §1.

## 20. Mise en route

### 20.1 Environnement de développement

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

L'installation standard via `pip install .` inclut les assets (`mod/`, `data/`, `config/` avec `defaults.yaml`) dans le wheel. Le chemin `tool.common.assets.asset_path` résout ces fichiers avec un repli sur le dépôt. C'est la méthode requise pour une installation sans copie de travail (voir le témoin de release).

### 20.2 Récupérer la base vanilla (une fois par version du jeu)

L'outil ne devine rien : il utilise un **dump JSON des prototypes** extrait de votre jeu par le mod compagnon `exporter/` :

1. Copiez ou liez `exporter/` dans `~/.factorio/mods/randputf-exporter_0.1.0/` (utilisez une copie directe si Flatpak bloque les liens symboliques).
2. **Désactivez `randputF` pour cet export** sous peine de rejet par l'exporter. Lancez Factorio quelques secondes : le jeu génère `script-output/randputF/vanilla_dump.json` dans votre dossier utilisateur.
3. Déplacez ce fichier vers `data/vanilla_dump.json` dans le projet.
4. Cet exporter est un outil de transition. Il sera intégré au mod principal ou supprimé.

> **Pourquoi désactiver `randputF` pendant l'export** : exporter avec les deux mods actifs modifie directement les prototypes vanilla (par exemple, `fuel_value` passe à 200 000 au lieu de 0 sur `crude-oil`, altération des filtres de chaudières et de `fuel_categories`). Ces valeurs faussent la génération de la seed sans bloquer le jeu. Pour éviter cela : l'exporter bloque tout export altéré (pas de fichier généré, alerte dans les logs), l'outil rejette les dumps modifiés (via l'invariant vanilla 2.0 `fuel_value == 0`), et `test_dump_pollution.py` valide la propreté de l'export.

### 20.3 Générer et jouer une seed

```bash
.venv/bin/python -m tool parse --demo      # vérifie la base (mode synthétique)
.venv/bin/python -m tool generate          # génère + valide (seed temporelle par défaut)
.venv/bin/python -m tool generate --seed 5 # seed figée, déterministe (reproductible)
```

Sans l'argument `--seed`, la seed est générée à partir de l'heure système (en millisecondes, §16). Utiliser `--seed <n>` garantit une génération identique et reproductible.

**Installation dans Factorio** : configurez le chemin absolu de vos mods dans `config/user.yaml` via la clé `paths.factorio_mods` (par exemple `~/.var/app/com.valvesoftware.Steam/.factorio/mods` pour Steam sous Flatpak). La valeur par défaut `""` est définie dans `config/defaults.yaml`. Lancez ensuite :

```bash
.venv/bin/python -m tool generate --seed 5 --install
```

L'option `--install` package le mod dans `factorio_mods/randputF_<version>/` (la version est lue dans `mod/info.json`) et met à jour `mod-list.json`. Si le dossier `factorio_mods` est introuvable, le mod est généré dans `output/` pour vous laisser le copier manuellement. En jeu, les patchs remplacent toutes les ressources vanilla de la zone de départ, le kit initial est fourni et les technologies gratuites sont débloquées.

### 20.4 État actuel du code

| Composant | État |
|---|---|
| `tool/common/rng.py` | `make_seeded_rng(seed_value, prefix)` : flux RNG par phase (préfixe `randputF:`/`randputf:` indexé par la seed). Chaque nouvelle phase doit utiliser son propre flux. Le préfixe reste strictement identique d'une exécution à l'autre pour garantir le déterminisme (voir nondeterminism.md). |
| `tool/common/tagsets.py` | Centralisation des identifiants en une source unique (D3) : `ENVIRONMENTAL_ITEMS`, `ROCKET_CHAIN`, `VEHICLE_GUNS`, `NON_STACKABLE_ITEM_TYPES`, `VALID_RECIPE_CATEGORIES`, `RAIL_TYPES`, `VIRTUAL_ITEM_TYPES`, `FLUID_RECIPE_CATEGORIES`, `STARTER_TRANSFORMERS`, `EXCLUDED_BUILDINGS`, `ENDGAME_EXCLUDED` (indexé dans `docs/tags.md §14`). |
| `tool/parsers/vanilla.py` | Normalisation du dump vers `VanillaDB` (objets, fluides, bâtiments catégorisés et recettes). |
| `tool/generator/map_patches.py` | Phase 1 active (3 à 8 patchs de types et richesses aléatoires). Exclusion garantie des laboratoires (§8), de la fusée et du silo (§14), ainsi que des packs de science (§13). |
| `tool/generator/starter_chain.py` | Kit de départ (arme et munitions adaptées), chaîne extraction-transformation-transport, pool environnemental et extracteurs limités aux objets. Intégration garantie du bâtiment de recherche dans la seconde recherche gratuite (§8), du premier pack de science fabricable (§13) et du remblai (landfill) si des lacs sont générés (§7). |
| `tool/generator/recursive_phase.py` | Phase récursive pondérée pour un déblocage progressif sans recette orpheline (§9.3). Les productions sont limitées aux intermédiaires (bâtiments et chaîne de la fusée exclus, équilibre consommation/production assuré dans `_pick_product`). Coût systématique en packs de science, initié par le premier pack du starter avec solution de repli garantie (§13). Cadence des pylônes (§9.4) et présence d'éléments compagnons (§9.7) garanties. |
| `tool/generator/electricity.py` | Générateur et combustible fournis à la demande (accumulateurs exclus). Gestion du mélange des générateurs avec test de fonctionnement et correction par patch forcé (20 tentatives max, §10). Fourniture des pylônes et infrastructures de distribution. Les technologies de départ sont rejouées plus tard (§10). |
| `tool/generator/endgame_phase.py` | Chaîne de la fusée fixe : génération des 3 composants de `rocket-part` et du rocket-silo. Technologie finale : `randputf-endgame-rocket` (§14). |
| `tool/generator/extractor_timing.py` | Planification du déblocage des extracteurs (C3 : kept/moved/random) via la fermeture `_startup_raw_resources` (boîte D4bis) pour jalonner la progression (§6.3). |
| `tool/generator/late_raws.py` | Jalons « late raws » (§6.3) : planification évaluée lors de la passe A (ressources brutes sous conditions non initiales, seuils définis par `_usage_floors` combinant composants, ateliers `crafted_in` et fermeture des coûts/déclencheurs), suivie d'une dégradation du pool en passe B. Export de `seed["late_raws"]`. |
| `tool/prototypes/starter.py` | `StarterConfig` (§7/§8) gère le paramètre `deferred` : les ressources brutes sous conditions restent exclues du pool de départ en passe B (état vierge). |
| `tool/replay/player.py` | Simulateur de relecture de seed pour audit externe : validation décuplée du rendement, point fixe sur la liste de travail inversée et génération d'un rapport `ReplayReport` (contenant blocker, mastered, never_masterable, victory). |
| `tools/classify_late_raws.py` | Analyseur de classification `(seed, extracteur, raw)` : catégorie C3, fermeture de la zone de départ et échelon du premier consommateur. Mesure les jalons et produit le CSV incrémental (`tools/classify_late_raws.py:14,208`). |
| `tools/audit_playthrough.py` / `tools/audit_usage.py` | Explorateurs du relecteur par plage de seeds (audit par lots via de simples affichages `print`). |
| `tool/common/demo.py` | Base vanilla synthétique pour le développement et les tests. Elle inclut le rocket-silo pour permettre à la phase finale de débloquer `randputf-rocket-silo` (validation d'exhaustivité, §15). |
| `tool/generator/relay_phase.py` | Recettes relais choisies dans le pool figé de début de partie (après le starter et l'électricité), avec les technologies de prologue `randputf-prologue-*` (maximum 5 déblocages, fabrication manuelle) (§7, §9.5, §13). |
| `tool/generator/tech_tree.py` | Arbre linéaire construit à partir des macro-étapes. Chaque recette a un déblocage unique (la première revendication l'emporte, §13/§15). |
| `tool/validator/pipeline_validator.py` | Exécute 7 contrôles (§15) : prévention des cycles par point fixe de solvabilité (les recettes relais servent d'alternatives), progression constante, cohérence technologies/recettes, accessibilité des coûts, règle des tuyaux, complétude de la fusée et absence de ressources brutes dans les packs. |
| `tool/validator/solver.py` | Vérifie uniquement la solvabilité de la seed (absence de cycles, progressivité, complétude, `solver.py:15-23`). |
| `mod/data.lua` | Gère uniquement les recettes, les technologies et la désactivation de l'arbre vanilla (`disable_vanilla_techs`, 234 lignes). |
| `mod/data-updates.lua` | Ajuste les véhicules (duplication des armes §12.1), applique les dalles de lacs aux teintes pastel, uniformise les combustibles et renomme la pompe (lignes 684-691). |
| `mod/data-final-fixes.lua` | Masquage des entités de ressources (`mod/data-final-fixes.lua:56-83` via autoplace et `size = 0`) et suppression des ressources vanilla au data-stage (lignes 79-83). |
| `mod/control.lua` | Exécution (runtime) : gère uniquement la purge de l'eau (`WATER_PURGE`, lignes 205-215), le remplissage des lacs par propagation (flood-fill), le placement déterministe des patchs, l'attribution du kit de départ et l'octroi des recherches gratuites (`free_researches`, ligne 688). |

La génération valide une seed complète à partir de la base vanilla réelle (`data/vanilla_dump.json`, incluse dans le dépôt). La graine est définie via `--seed N` (par défaut, elle est calculée sur l'heure courante). Le fichier de configuration yaml ne contient **aucune seed** par défaut. Le mode démonstration (`parse --demo`) permet de tester le moteur sur une base synthétique allégée.
