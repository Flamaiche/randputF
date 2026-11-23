# Modules du tool

Retour : [docs/README.md](README.md).

Le package Python est organisé en petits modules aux rôles distincts. Certains construisent la seed. Les autres observent, écrivent des rapports ou restent hors du chemin de génération.

## Ce que ça change pour l'utilisateur

- Seuls les modules branchés font évoluer le contenu généré.
- Les modules d'audit et d'export ne modifient pas la construction de la seed.
- Les modules non branchés sont conservés pour leurs tests, sans effet sur le jeu.

## Mots à connaître

- [pipeline](glossaire.md) — suite ordonnée de phases de génération.
- [validateur](glossaire.md) — contrôle appliqué à une seed.
- [rejeu](glossaire.md) — simulation de la progression sans interface Factorio.
- [rapport HTML](glossaire.md) — vue générée du graphe ou de la difficulté.

## Fonctionnement

### Vue d'ensemble

| Paquet | Modules hors `__init__.py` | Rôle |
|---|---|---|
| `tool/common/` | 11 | configuration, base, RNG, tags, version, témoin |
| `tool/audit/` | 5 | tags, difficulté, profil, champs, graphe |
| `tool/exporters/` | 9 | seed du mod et trois vues HTML |
| `tool/generator/` | 20 | phases de génération |
| `tool/prototypes/` | 12 | objets de configuration |
| `tool/parsers/` | 1 | lecture du dump |
| `tool/validator/` | 2 | structure et solvabilité |
| `tool/replay/` | 1 | rejoueur Python |

`tool/__main__.py` expose la CLI et `tool/service.py` fournit l'orchestration partagée.

### Les quatre statuts

| Statut | Signification |
|---|---|
| Pipeline | appelé pendant la construction de la seed |
| Conditionnel | appelé seulement si une clé de configuration l'active |
| Accessoire | utilisé par la CLI, l'audit, l'export ou les tests |
| Non branché | testé, mais jamais importé par la construction |

Les modules `late_raws.py` et `craft_quantity.py` sont conditionnels. `bootstrap_guard.py` sert uniquement au diagnostic de cycles. `difficulty_knobs.py` n'est pas utilisé par le pipeline, mais il est importé par sa suite de tests.

### tool/exporters

`mod_seed.py` écrit `seed.json`, `seed.lua` et les localisations. `seed_graph.py`, `complexity_graph.py` et `difficulty_graph.py` écrivent les trois vues HTML. `report.py`, `dump_html.py`, `vanilla_complexity.py`, `profile.py` et `html_ui.py` servent aux rapports et à l'interface.

`seed.graph.html` dépend de Graphviz ; `seed.difficulty.html` et `seed.complexity.html` écrivent leur SVG en Python. L'absence de Graphviz n'empêche ni la seed ni le mod d'être produits.

### La CLI

Neuf commandes sont disponibles : `parse`, `audit`, `difficulty`, `compare`, `report`, `test`, `dump`, `generate` et `witness`.

Les options `--demo` et `--dump` existent sur `parse`, `audit`, `difficulty`, `compare`, `generate` et `witness`. Elles ne sont pas communes à toutes les commandes. `report` et `test` utilisent un dump sans `--demo`.

`generate` est la seule commande à passer par `generate_with_retry`. `difficulty` et `witness` appellent `generate_seed` directement. `generate` accepte `--install` et `--no-html`.

### Historique

D'anciens documents présentaient `--demo` et `--dump` comme des options globales. Le code les déclare commande par commande ; les anciennes listes ne sont pas la source courante.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Les modules branchés sont distincts des modules d'observation. | Un module testé peut rester hors pipeline. |
| L'inventaire des modules exclut les fichiers `__init__.py`. | Les noms de modules peuvent changer lors d'un refactoring. |
| Les vues HTML disponibles sont générées par `generate` sauf `--no-html`. | Graphviz peut manquer pour `seed.graph.html` ; les technologies peuvent manquer pour la difficulté. |

## Aller plus loin

- [pipeline.md](pipeline.md) — à lire quand l'ordre réel des appels importe.
- [architecture.md](architecture.md) — à lire quand il faut situer les paquets.
- [etat-code.md](etat-code.md) — à lire quand un composant doit être qualifié.
- [config.md](config.md) — à lire quand une clé pilote un module conditionnel.
- [testeur.md](testeur.md) — à lire quand le module `test` est utilisé.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [developpement.md](developpement.md) — environnement de développement.
- [exporter.md](exporter.md) — origine du dump consommé par `tool/parsers/`.
- [graphe-interactif.md](graphe-interactif.md) — sorties des exporteurs HTML.
