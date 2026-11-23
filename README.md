# randputF

![Licence MIT](https://img.shields.io/badge/licence-MIT-blue)

**Randomiseur total pour Factorio 2.1, jeu de base, sans Space Age.**

randputF reconstruit une partie entière à partir d'une graine : ressources au
sol, recettes, bâtiments débloqués, arbre technologique et kit de départ. Une
même graine produit toujours le même monde. Le parcours reste jouable jusqu'au
lancement de la fusée.

Ce README explique comment installer et utiliser l'outil. Pour comprendre le
fonctionnement, commencez par [la documentation](docs/README.md).

## Avant de commencer

Quatre mots suffisent pour lire la suite :

- une **seed** est la graine qui fixe tous les tirages ;
- un **dump vanilla** est la photographie des prototypes du jeu, utilisée comme
  matière première ;
- le **randput** est le remplacement du contenu d'une entrée ou d'une sortie par
  un autre élément du même type ;
- le **runtime** est la partie Lua qui applique la seed dans Factorio.

Le [glossaire](docs/glossaire.md) donne les autres définitions.

## Ce que ça change pour le joueur

- Les gisements, les recettes, les bâtiments, les technologies et le kit de
  départ changent à chaque seed.
- Les entrées et sorties des machines suivent le principe du randput : un
  emplacement d'item reçoit un autre item, un emplacement de fluide reçoit un
  autre fluide.
- L'objectif reste vanilla : lancer la fusée. Les technologies infinies vanilla
  sont désactivées ; seules les technologies `randputf-` restent disponibles.
- Le contenu ciblé est Factorio 2.1 de base, sans Space Age. Les mods tiers sont
  hors périmètre.

## Comment ça marche

1. L'exporteur Factorio produit le dump vanilla.
2. L'outil Python lit le dump et la seed, puis construit les recettes,
   l'arbre technologique et le contenu du mod.
3. Le mod Lua applique la seed au lancement de la partie ; les rapports HTML
   décrivent le graphe, la complexité et la difficulté.

## Installation

### Prérequis

- Factorio 2.1, jeu de base ;
- Python 3.11 ou plus récent.

Les versions 2.0 correspondent aux tags historiques `v0.0.0` et `v0.0.1`.

### Dossier `mods` selon le système

| Système | Chemin |
|---|---|
| Windows | `%APPDATA%\Factorio\mods` |
| Linux | `~/.factorio/mods` |
| Linux Flatpak | `~/.var/app/com.valvesoftware.Steam/.factorio/mods` |

### Environnement Python

```bash
python3 -m venv .venv
.venv/bin/pip install .
```

Sous Windows, utiliser `.venv\Scripts\` à la place de `.venv/bin/`.

L'installation embarque `mod/`, `data/` et `config/` dans le paquet. La
commande `randputf` est alors disponible depuis n'importe quel répertoire.

### Générer une seed

```bash
randputf generate
randputf generate --seed <nombre>
```

Les options `--demo` et `--no-html` couvrent respectivement une base synthétique
de tests et une génération sans rapports HTML.

Une seed impose tous les tirages. `generate` assemble le mod dans
`output/mods/<mod>/`. Les vues HTML vont dans
`output/reports/randputF_<version>/` : la complexité est toujours calculée, le
graphe et la difficulté peuvent être omis. `--no-html` supprime toutes les
écritures HTML. La console affiche `Seed <valeur> valide, mod assemblé dans
<chemin>` quand la génération aboutit.

### Installer le mod dans Factorio

```bash
randputf generate --seed <nombre> --install
```

`--install` copie le mod assemblé dans le dossier Factorio défini par
`paths.factorio_mods` dans `config/user.yaml`, puis active le mod dans
`mod-list.json`. Les rapports HTML restent dans `output/reports/`, sauf avec
`--no-html`. Si le dossier mods est introuvable, le mod reste dans
`output/mods/` et le chemin est affiché. Le menu **Mods** de Factorio permet de
désactiver le mod.

## Configuration

`config/defaults.yaml` contient les réglages par défaut. `config/user.yaml`
contient les surcharges locales. Les deux fichiers sont fusionnés puis validés :
une clé inconnue ou une valeur impossible provoque une erreur explicite.

Les sections principales sont `paths`, `map`, `starter` et `recursive`. La
référence complète figure dans [config.md](docs/config.md).

## Sorties d'une génération

| Sortie | Contenu |
|---|---|
| `output/mods/<mod>/` | mod Lua assemblé, sans rapport HTML |
| `output/reports/randputF_<version>/seed.graph.html` | graphe de production interactif |
| `output/reports/randputF_<version>/seed.difficulty.html` | difficulté cumulée comparée à vanilla |
| `output/reports/randputF_<version>/seed.complexity.html` | coût réel de l'arbre, déplié jusqu'aux ressources brutes |

Ces sorties sont décrites dans [graphe-interactif.md](docs/graphe-interactif.md).
Le dépôt ne contient pas de mod pré-généré : le mod est produit par `generate`.

## Repères courants

- La sortie est déterministe : une même seed produit le même mod, octet pour
  octet, indépendamment du processus et de l'ordre des générations.
- Le témoin courant de la seed 5 est
  `e61667692c486e5b9c30efa9f4fbc891`.
- La suite de tests compte 873 tests.
- Le détail du témoin figure dans [witness.md](docs/witness.md).

## Par où continuer

| Besoin | Lecture |
|---|---|
| Comprendre les mots et le principe | [glossaire](docs/glossaire.md), [modèle](docs/model.md) |
| Suivre la création d'une partie | [ressources](docs/ressources.md), [starter](docs/starter.md), [recettes](docs/recettes.md), [technologies](docs/tech.md) |
| Vérifier qu'une seed est valide | [solvabilité](docs/solvabilite.md), [witness](docs/witness.md), [testeur](docs/testeur.md) |
| Travailler sur le code | [architecture](docs/architecture.md), [pipeline](docs/pipeline.md), [runtime](docs/runtime.md) |
| Consulter l'historique | [CHANGELOG.md](CHANGELOG.md), [release](docs/release.md) |

L'index complet de la documentation est dans [docs/README.md](docs/README.md).
Le miroir anglais du README est dans [README_EN.md](README_EN.md).

---

*randputF — chaque partie est un jeu que personne n'a jamais vu.*

Licence : MIT — voir [`LICENSE`](LICENSE).
