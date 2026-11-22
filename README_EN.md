# randputF

![MIT License](https://img.shields.io/badge/licence-MIT-blue)

**Full deterministic randomizer for Factorio 2.1, base game, no Space Age.**

randputF rebuilds a complete game from a seed: surface resources, recipes,
unlocked buildings, tech tree and starting kit. The same seed always produces
the same world. The run stays playable until the rocket is launched.

This README covers installation and use. Start with
[the documentation](docs/README.md) to understand how the system works.

## Before you start

Four terms are enough to follow this README:

- a **seed** fixes every draw in a run;
- a **vanilla dump** is a snapshot of the game prototypes, used as raw material;
- **randput** replaces the content of an input or output with another element of
  the same type;
- the **runtime** is the Lua part that applies the seed inside Factorio.

The [glossary](docs/glossaire.md) defines the other terms. It is currently in
French.

## What changes for the player

- Resources, recipes, buildings, technologies and the starting kit change with
  the seed.
- Machine inputs and outputs follow the randput rule: an item slot receives
  another item, a fluid slot receives another fluid.
- The goal stays vanilla: launch the rocket. Vanilla infinite technologies are
  disabled; only `randputf-` technologies remain.
- The target is Factorio 2.1 base game. Third-party mods are out of scope.

## How it works

1. The Factorio exporter produces the vanilla dump.
2. The Python tool reads the dump and the seed, then builds recipes, the tech
   tree and the mod content.
3. The Lua mod applies the seed when the game starts; HTML reports describe the
   production graph, complexity and difficulty.

## Installation

### Requirements

- Factorio 2.1, base game;
- Python 3.11 or newer.

Factorio 2.0 corresponds to the historical tags `v0.0.0` and `v0.0.1`.

### `mods` folder by operating system

| System | Path |
|---|---|
| Windows | `%APPDATA%\Factorio\mods` |
| Linux | `~/.factorio/mods` |
| Linux Flatpak | `~/.var/app/com.valvesoftware.Steam/.factorio/mods` |

### Python environment

```bash
python3 -m venv .venv
.venv/bin/pip install .
```

On Windows, use `.venv\Scripts\` instead of `.venv/bin/`.

The install embeds `mod/`, `data/` and `config/` in the package. The
`randputf` command is then available from any directory.

### Generate a seed

```bash
randputf generate
randputf generate --seed <number>
```

The `--demo` and `--no-html` options cover a synthetic test base and generation
without HTML reports.

A seed drives all draws. `generate` assembles the mod in `output/mods/<mod>/`.
HTML views go to `output/reports/randputF_<version>/`: complexity is always
computed, while the graph and difficulty may be omitted. `--no-html` skips all
HTML output. The console prints `Seed <valeur> valide, mod assemblé dans
<chemin>` when generation succeeds.

### Install the mod into Factorio

```bash
randputf generate --seed <number> --install
```

`--install` copies the assembled mod into the Factorio folder set by
`paths.factorio_mods` in `config/user.yaml`, then enables it in `mod-list.json`.
HTML reports remain in `output/reports/` unless `--no-html` is used. If the mods
folder cannot be found, the mod stays in `output/mods/` and the path is printed.
Factorio's **Mods** menu can disable the mod.

## Configuration

`config/defaults.yaml` holds the default settings. `config/user.yaml` holds
local overrides. Both files are merged and validated: an unknown key or an
impossible value raises an explicit error.

The main sections are `paths`, `map`, `starter` and `recursive`. The full
reference is in [config.md](docs/config.md).

## Generation outputs

| Output | Content |
|---|---|
| `output/mods/<mod>/` | assembled Lua mod, without HTML reports |
| `output/reports/randputF_<version>/seed.graph.html` | interactive production graph |
| `output/reports/randputF_<version>/seed.difficulty.html` | cumulative difficulty against vanilla |
| `output/reports/randputF_<version>/seed.complexity.html` | real tree cost, unfolded down to raw resources |

These outputs are described in
[graphe-interactif.md](docs/graphe-interactif.md). The repository contains no
prebuilt mod: the mod is produced by `generate`.

## Current reference points

- Output is deterministic: the same seed produces a byte-identical mod,
  independently of the process and of generation order.
- The current witness for seed 5 is
  `74dcb6f89c28ef1277a0e854d9a21a4a`.
- The test suite contains 861 tests.
- Witness details are in [witness.md](docs/witness.md).

## Where to go next

| Need | Reading |
|---|---|
| Understand the words and principle | [glossary](docs/glossaire.md), [model](docs/model.md) |
| Follow run creation | [resources](docs/ressources.md), [starter](docs/starter.md), [recipes](docs/recettes.md), [technologies](docs/tech.md) |
| Check a seed | [solvability](docs/solvabilite.md), [witness](docs/witness.md), [tester](docs/testeur.md) |
| Work on the code | [architecture](docs/architecture.md), [pipeline](docs/pipeline.md), [runtime](docs/runtime.md) |
| Read the history | [CHANGELOG.md](CHANGELOG.md), [release](docs/release.md) |

The full documentation index is in [docs/README.md](docs/README.md). The French
README is [README.md](README.md).

---

*randputF — every run is a game nobody has ever seen.*

License: MIT — see [`LICENSE`](LICENSE).
