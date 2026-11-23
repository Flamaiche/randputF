# État actuel du code

Retour : [docs/README.md](README.md).

Ce relevé qualifie les composants du projet. Il sépare ce qui construit la seed, ce qui l'observe et ce qui reste hors du chemin courant. La synthèse reste dans [developpement.md](developpement.md).

## Ce que ça change pour l'utilisateur

- Seuls les composants branchés influencent le mod généré.
- Les composants d'audit et de rapport n'écrivent pas la seed.
- Un module testé peut rester sans effet sur le jeu.

## Mots à connaître

- [pipeline](glossaire.md) — suite ordonnée de phases de génération.
- [validateur](glossaire.md) — contrôle appliqué à une seed.
- [rejeu](glossaire.md) — simulation de la progression.
- [témoin](glossaire.md) — empreinte qui vérifie la reproductibilité.

## Fonctionnement

### Composants de la seed

| Composant | État et rôle |
|---|---|
| `tool/common/rng.py` | branché ; fournit un flux RNG par phase |
| `tool/common/tagsets.py` | branché ; centralise les ensembles figés |
| `tool/parsers/vanilla.py` | branché ; normalise le dump et calcule les tags |
| `tool/generator/map_patches.py` | branché ; tire les gisements et les facteurs de richesse |
| `tool/generator/starter_chain.py` | branché ; construit le départ et la chaîne initiale |
| `tool/generator/recursive_phase.py` | branché ; couvre les recettes et les technologies |
| `tool/generator/electricity.py` | branché ; résout producteurs, accumulateurs et pylônes |
| `tool/generator/endgame_phase.py` | branché ; garantit la chaîne de fusée |
| `tool/generator/extractor_timing.py` | branché ; règle le déblocage des extracteurs |
| `tool/generator/relay_phase.py` | branché ; ajoute les recettes relais et les prologues |
| `tool/generator/tech_tree.py` | branché ; construit l'arbre linéaire |
| `tool/generator/late_raws.py` | conditionnel ; actif seulement avec les jalons de ressources tardives |
| `tool/prototypes/starter.py` | branché ; porte la configuration du départ |

### Composants d'observation et de sortie

| Composant | État et rôle |
|---|---|
| `tool/validator/pipeline_validator.py` | journalise les contrôles structurels |
| `tool/validator/solver.py` | vérifie la solvabilité et sert au rejeu |
| `tool/replay/player.py` | simule la progression sans interface Factorio |
| `tool/audit/tags.py` | contrôle les invariants de classement |
| `tool/audit/difficulty.py` | calcule l'ardoise affichée au spawn |
| `tool/exporters/mod_seed.py` | écrit `seed.json`, `seed.lua` et les localisations |
| `tool/exporters/seed_graph.py` | écrit le graphe interactif |
| `tool/exporters/complexity_graph.py` | écrit le rapport de complexité |
| `tool/exporters/difficulty_graph.py` | écrit la comparaison de difficulté |
| `tool/common/demo.py` | fournit une base synthétique pour les tests |

Les ensembles dérivés en dur sont décrits dans [tags.md](tags.md#ensembles-dérivés-en-dur-résiduels). Les rôles de modules et leur inventaire sont dans [modules.md](modules.md).

### Composants du mod

| Fichier | Rôle |
|---|---|
| `mod/data.lua` | construit recettes et technologies depuis `seed.lua` |
| `mod/data-updates.lua` | façonne ressources, lacs, fluides et armes montées |
| `mod/data-final-fixes.lua` | neutralise le vanilla et corrige l'autoplace |
| `mod/control.lua` | applique la seed au monde pendant la partie |
| `exporter/control.lua` | écrit le dump vanilla ou moddé |

### Composants hors chemin courant

`difficulty_knobs.py` n'est pas importé par le pipeline. Il est seulement utilisé par sa suite de tests. `bootstrap_guard.py` sert au diagnostic de cycles. `craft_quantity.py` et `late_raws.py` dépendent d'une clé de configuration active.

Les scripts de `tools/` explorent le rejoueur par plages de seeds. Ils ne participent pas à `generate`. Les brouillons de `atelier/` sont hors livrable.

### Repères courants

La suite compte 876 tests. Le témoin de la seed 5 est `647ab8833f639846ba36f9c52f38fb94`. La version courante vise Factorio 2.1 et reste en préparation de release.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Le statut des composants est séparé de leur simple présence dans le dépôt. | Les modules non branchés peuvent devenir actifs plus tard. |
| Le témoin et le compte de tests décrivent l'état courant. | Les valeurs historiques des tags anciens ne s'appliquent pas. |
| Les sorties HTML ne font pas partie du mod Lua. | Certains scripts de diagnostic restent manuels. |

## Aller plus loin

- [modules.md](modules.md) — à lire quand l'inventaire des paquets est nécessaire.
- [pipeline.md](pipeline.md) — à lire quand l'ordre réel des appels importe.
- [architecture.md](architecture.md) — à lire quand la structure générale est cherchée.
- [witness.md](witness.md) — à lire quand le témoin doit être vérifié.
- [DEVIANCES.md](DEVIANCES.md) — à lire quand un écart est constaté.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [developpement.md](developpement.md) — environnement et roadmap.
- [runtime.md](runtime.md) — rôle des fichiers Lua.
- [release.md](release.md) — état des versions.
