# Modules du tool — inventaire et rôle

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

Ce document liste **tous** les modules Python du package `tool`, ce qu'ils font,
qui les appelle, et — pour chacun — s'ils sont **branchés** au pipeline,
**accessoires**, ou **non branchés**.

Aucun numéro de ligne n'est nécessaire ici : les points d'entrée sont
nommés. Les références `fichier:ligne` des algorithms sont dans
[`pipeline.md`](pipeline.md) et [`nondeterminism.md`](nondeterminism.md).

---

## 1. Vue d'ensemble

| Paquet | Rôle | Modules |
|--------|------|---------|
| `tool/__main__.py` | CLI : 5 commandes | 1 |
| `tool/parsers/` | Lecture du dump vanilla | 1 |
| `tool/common/` | Socle : config, base, RNG, tags, version, witness | 10 |
| `tool/generator/` | Les phases de génération | 20 |
| `tool/prototypes/` | Objets de configuration par phase | 12 |
| `tool/validator/` | Validation structurelle et solvabilité | 2 |
| `tool/audit/` | Tags et difficulté | 2 |
| `tool/exporters/` | Écriture des artefacts | 2 |
| `tool/replay/` | Rejoueur « fake player » | 1 |

Les `__init__.py` des sous-domaines sont vides (7 fichiers, 0 ligne) et
`tool/prototypes/` n'en a même pas (namespace package implicite) ; seul
`tool/__init__.py` porte une docstring de module. Le tool est un **package à
plat**, pas une hiérarchie de sous-domaines.

## 2. État de branchement — les quatre statuts

| Statut | Signification |
|--------|---------------|
| **Pipeline** | Appelé par `generate_seed` ou par un de ses jalons |
| **Accessoire** | Utilisé par le CLI, l'audit, l'export ou les tests — jamais par la génération |
| **Conditionnel** | Appelé par le pipeline seulement si une config l'active |
| **Non branché** | Aucun import depuis le pipeline ; existe et est testé, mais n'influence aucune seed |

Ce tableau est le point important du document : **deux tiers du code n'est pas
sur le chemin d'une seed**.

## 3. `tool/generator/` — les phases

| Module | Lignes | Statut | Rôle |
|--------|--------|--------|------|
| `pipeline.py` | 506 | Pipeline | Orchestration : `generate_seed`, `_build_prefix`, `_finalize_pipeline` |
| `map_patches.py` | 343 | Pipeline | Phase 1 : ressources au sol, gisements, nonfinite |
| `lakes.py` | 76 | Pipeline | Lacs de fluide |
| `starter_chain.py` | 651 | Pipeline | Phase 2 : chaîne initiale, kit, techs gratuites |
| `electricity.py` | 277 | Pipeline | Phase 3 : générateur fonctionnel, réparations |
| `recursive_phase.py` | 1242 | Pipeline | Phase 4 : récursion pondérée, coverage, véhicules |
| `endgame_phase.py` | 76 | Pipeline | Chaîne de la fusée intable |
| `usage_pass.py` | 511 | Pipeline | Garantie d'usage dure (U1, U2) |
| `relay_phase.py` | 277 | Pipeline | Recettes propres pour les environnementales |
| `easeup_phase.py` | 347 | Pipeline | Recettes alternatives pour crafts lourds |
| `tech_tree.py` | 318 | Pipeline | Arbre technologique linéaire |
| `extractor_timing.py` | 571 | Pipeline | Déblocage juste-au-besoin des extracteurs |
| `late_raws.py` | 355 | Conditionnel | Jalons de ressources ; inerte si `late_raws.enabled` est faux |
| `craft_quantity.py` | 52 | Conditionnel | Phase 6bis ; inerte si `craft_quantity.enabled` est faux |
| `wreck_loot.py` | 65 | Pipeline | Loi de loot du crash site |
| `building_fluids.py` | 112 | Pipeline | Fluides des bâtiments à comportement fixe |
| `recipes.py` | 805 | Pipeline | Primitives partagées : `ProgressionState`, `ensure_obtainable`, `make_recipe` |
| `early_oracle.py` | 145 | Pipeline | Watershed obtenable sans électricité |
| `bootstrap_guard.py` | 173 | Accessoire | Diagnostic SCC du graphe — appelé par `extractor_timing`, donc **sur le chemin** d'une seed, mais comme garde |
| `heat.py` | 39 | Pipeline | Partition source / transport / consommateur ; importé par `recursive_phase` |

> `bootstrap_guard.py` est le seul module « guard » du tool : il ne construit
> rien, il **diagnostique** les cycles du graphe. Il est appelé depuis
> `extractor_timing`, donc son résultat est visible dans
> `seed["extractor_timing"]`.

## 4. `tool/prototypes/` — les objets de configuration

Tous dérivent de `PrototypeConfig` (`base.py`, 13 lignes).

Les champs des dataclasses portent des **défauts** (par exemple
`max_iterations: int = 120`, `tool/prototypes/recursive.py:39`) : ils servent à
construire un prototype seul, typiquement dans un test. Le chemin du pipeline
passe toujours par `from_config`, qui retombe sur `default_value` — donc sur
`config/defaults.yaml` — et **jamais** sur le défaut du champ
(`tool/prototypes/recursive.py:84-101`). C'est ce qui permet d'affirmer que
`defaults.yaml` est la source unique des réglages.

| Module | Lignes | Statut | Domaine |
|--------|--------|--------|---------|
| `base.py` | 14 | Socle | `PrototypeConfig` : accès typé au config fusionné |
| `recipes.py` | 145 | Pipeline | `RecipeConfig` — poids, énergie, équilibrage |
| `recursive.py` | 150 | Pipeline | `RecursiveConfig` — poids par catégorie, distances, véhicules |
| `starter.py` | 42 | Pipeline | `StarterConfig` — dont `deferred`, la porte du rejeu late raws |
| `relay.py` | 33 | Pipeline | `RelayConfig` — préfixe, pas de dispatch |
| `easeup.py` | 42 | Pipeline | `EaseupConfig` — seuil de profondeur, unlocks par tech |
| `usage.py` | 55 | Pipeline | `UsageConfig` — bâtiments terminaux, exemptions du kit |
| `craft_quantity.py` | 148 | Pipeline | `CraftQuantityConfig` — mode symétrique/asymétrique |
| `nonfinite_randomisation.py` | 118 | Pipeline | `NonfiniteConfig` — facteurs de richesse/rayon/count |
| `difficulty_knobs.py` | 101 | **Non branché** | Knobs de difficulté par seed — testé, jamais importé |
| `progressive_extractors.py` | 115 | **Non branché** | Ancien prototype d'extracteurs progressifs — remplacé par `extractor_timing` |
| `rare_resources.py` | 137 | **Non branché** | Mode exploration « ressources rares » — aucun sélecteur de mode dans le CLI |

> `progressive_extractors.py` est le **prédécesseur** de
> `tool/generator/extractor_timing.py` : même invariant (« l'extracteur arrive
> quand on en a besoin »), mais résolu au niveau seed plutôt que par prototype.
> Les deux coexistent ; seul le second est branché.

## 5. `tool/common/` — le socle

| Module | Lignes | Statut | Rôle |
|--------|--------|--------|------|
| `config.py` | 490 | Pipeline | Fusion defaults + surcharges, **schéma strict**, `ConfigError` |
| `db.py` | 430 | Pipeline | `VanillaDB` : base normalisée, pools, tags |
| `rng.py` | 23 | Pipeline | `make_seeded_rng` — **fabrique unique** des flux RNG |
| `tagsets.py` | 120 | Pipeline | Ensembles de noms figés (D3), source unique par ensemble |
| `version.py` | 37 | Accessoire | `VERSION`, `FACTORIO_VERSION`, `MOD_NAME_VERSIONED` — lus depuis `mod/info.json` |
| `witness.py` | 86 | Accessoire | md5 canonique du mod assemblé |
| `assets.py` | 59 | Accessoire | Résolution de `mod/`, `data/`, `config/` en dépôt comme en wheel |
| `demo.py` | 179 | Accessoire | Base vanilla synthétique : `randputf --demo` |
| `png_icon.py` | 184 | Accessoire | Recadrage des icônes Factorio pour le graphe HTML |
| `weighted_picker.py` | 126 | Pipeline | Tirage pondéré à pourcentages ; utilisé par `prototypes/recipes.py` |

### 5.1 `config.py` en détail

Seul module où la **validation** est une erreur et non un log.

| Fonction | Ligne | Rôle |
|----------|-------|------|
| `full_config` | 259 | Fusion + validation stricte ; `strict_sections=False` tolère les clés racine hors schéma |
| `runtime_config` | 279 | Defaults + `config/user.yaml` — le chemin du CLI |
| `default_value` | 248 | Valeur unitaire lue du defaults, jamais d'un littéral |
| `validate` | 392 | Schéma par section, **clés obligatoires absentes signalées**, contraintes croisées |
| `_wreck_constraints` | 462 | Contraintes non linéaires du loot de crash |

Les 16 types de spécification du schéma sont définis en tête de fichier
(`tool/common/config.py:30-46`).

**Invariant** : un config fusionné est **toujours complet** — chaque clé lue par
le moteur existe, donc aucun module n'a besoin de valeur de secours
(`tool/common/config.py:10-12`). Une clé obligatoire absente est un défaut de
maintenance, pas une tolérance (`tool/common/config.py:418-423`).

## 6. `tool/parsers/vanilla.py` — l'entrée

608 lignes. Normalise `vanilla_dump.json` (produit par `exporter/control.lua`)
vers `VanillaDB`.

| Responsabilité | Détail |
|----------------|--------|
| Ignore les objets randputF | `_RANDPUTF_PREFIX = "randputf-"` (`tool/parsers/vanilla.py:61`) — un dump pollué est filtré, pas refusé |
| Empile les doublons | Rejette les noms déjà préfixés plutôt que de créer `randputf-randputf-…` |
| Calcule les tags | Dérive `is_crafter`, `is_extractor`, `is_generator`… depuis les capacités |
| Rejette un dump invalide | `DumpInvalidError` avec message → le CLI sort en 1 (`tool/__main__.py:53-55`) |

## 7. `tool/validator/` — deux validations distinctes

| Module | Lignes | Ce qu'il vérifie |
|--------|--------|------------------|
| `pipeline_validator.py` | 537 | **Structure** : le graphe est-il cohérent ? Stats, issues, warnings |
| `solver.py` | 84 | **Solvabilité** : la seed est-elle finissable ? Liste de problèmes |

Le pipeline appelle le validateur **structurel** et ne fait qu'**logger**
(`tool/generator/pipeline.py:412-427`). Le CLI appelle le **solver** et
**retente avec une graine dérivée** jusqu'à 10 fois
(`MAX_ATTEMPTS = 10`, `tool/service.py:50`).

C'est la distinction à retenir : une seed peut être structurellement valide et
non solvable — et c'est le cas qui déclenche la reprise du CLI. Voir
[`solvabilite.md`](solvabilite.md).

## 8. `tool/audit/`

| Module | Lignes | Statut | Rôle |
|--------|--------|--------|------|
| `tags.py` | 263 | Accessoire | Audit des tags de bâtiments et d'items (invariant C8) ; exit 1 si violation |
| `difficulty.py` | 182 | Pipeline (à l'export) | Ardoise de ressources brutes ; **injectée dans la seed à l'export** |

`compute_difficulty` est le seul audit sur le chemin d'une seed, et il ne
s'exécute qu'à l'écriture (`tool/exporters/mod_seed.py:54`) : le calcul ne peut
donc pas biaiser la construction.

## 9. `tool/exporters/`

| Module | Lignes | Statut | Rôle |
|--------|--------|--------|------|
| `mod_seed.py` | 126 | Pipeline | Écrit `seed.json` + `seed.lua` + `locale/*/seed.cfg` ; injecte `difficulty` |
| `seed_graph.py` | 1720 | Accessoire | Graphe HTML interactif ; **optionnel** (Graphviz absent → ignoré sans erreur) |

`seed_graph.py` est le plus gros fichier du tool et le seul à dépendre d'un
binaire externe. Son absence ne bloque jamais une génération
(`tool/__main__.py:127-130`).

## 10. `tool/replay/player.py` — le rejoueur

1074 lignes. Simule une partie complète sur la seed finale pour **prouver** la
solvabilité. Ce n'est pas le validateur : c'est une preuve par simulation
(1501/1501 victoires mesurées, `docs/solvabilite.md` §15ter).

Il est **accessoire** : la CLI ne l'expose pas comme commande. Il est appelé par
la suite de tests et par les sweeps.

## 11. `tool/__main__.py` — la CLI

209 lignes, 5 commandes.

| Commande | Ligne | Rôle | Sortie |
|----------|-------|------|--------|
| `parse` | 58 | Charge et résume la base vanilla | Résumé texte |
| `audit` | 64 | Audite les tags | exit 1 si violation |
| `difficulty` | 133 | Génère puis affiche l'ardoise | Tableau texte |
| `generate` | 85 | Génère, valide, assemble le mod | Dossier `output/randputF_<version>/` |
| `witness` | 145 | Assemble et hache | md5 ; exit 1 si `--expect` diverge |

Options communes à toutes : `--demo` (base synthétique) et `--dump` (dump
vanilla alternatif).

`generate` a une option propre : `--install`, qui copie le mod dans
`paths.factorio_mods` et met à jour `mod-list.json`
(`tool/__main__.py:106-120`) — et **désactive** `randputf-exporter`, pour
qu'aucun dump ne puisse être pris depuis une partie randomisée.

## 12. Récapitulatif des statuts

| Statut | Nombre | Modules |
|--------|--------|---------|
| Pipeline | 33 | 17 phases `generator/*` ; 5 `common` (`config`, `db`, `rng`, `tagsets`, `weighted_picker`) ; 8 prototypes ; `pipeline_validator` ; `audit/difficulty` (à l'export) ; `exporters/mod_seed` |
| Conditionnel | 2 | `late_raws.py`, `craft_quantity.py` |
| Accessoire | 10 | `version`, `witness`, `assets`, `demo`, `png_icon`, `tags`, `seed_graph`, `solver`, `player`, `bootstrap_guard` |
| Non branché | 3 | `prototypes/difficulty_knobs`, `prototypes/progressive_extractors`, `prototypes/rare_resources` |

Les trois modules non branchés sont **testés** : leurs tests passent et
documentent l'invariant qu'ils implémentaient. Les supprimer casserait des
tests, pas des seeds — c'est le marqueur d'une fonctionnalité retirée du
câblage mais non nettoyée.

## 13. Lectures associées

- [`pipeline.md`](pipeline.md) — l'ordre réel d'appel de ces modules.
- [`architecture.md`](architecture.md) — la structure du projet (§18).
- [`developpement.md`](developpement.md) — environnement de dev, ajout d'une phase.
- [`config.md`](config.md) — chaque clé de config et sa validation.
