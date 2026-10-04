# randputF

![Licence MIT](https://img.shields.io/badge/licence-MIT-blue)

**Full deterministic randomizer for [Factorio](https://factorio.com) 2.0 (base game, no Space Age).**

randputF doesn't just shuffle recipes against each other: it regenerates the
entire game — surface resources, recipes (inputs *and* outputs), unlocked
buildings, tech tree, starting kit — while guaranteeing every seed (*seed
value*) a valid, loop-free run from the first pick to rocket launch.

> This is the English README. The full reference (in French) lives in
> [`docs/`](docs/README.md); the French README is [`README.md`](README.md).

## Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [What a generation produces](#what-a-generation-produces)
4. [The interactive graph](#the-interactive-graph)
5. [Project structure](#project-structure)

---

## Installation

### Requirements

- **Factorio 2.0** (base game, no Space Age);
- **Python 3.11+** to generate seeds (the generator is a standalone CLI tool,
  not a runtime dependency of the mod).

### 1. Set up the Python environment

```bash
python3 -m venv .venv
.venv/bin/pip install .          # package + assets (mod/, data/, config/) embedded
```

A regular (non-editable) install embeds the asset folders in the wheel, so
`randputf` works from any directory. For development on this repository,
`pip install -e .` works too (paths fall back to the checkout). The tool is
called `randputf` (via `python -m tool`). It consumes an embedded **vanilla
prototype dump** (`data/vanilla_dump.json`) — nothing to do to play. How to
regenerate that dump is documented in [docs/developpement.md](docs/developpement.md).

### 2. Generate a seed

By default the seed is drawn from the current instant (milliseconds): every
generation produces a unique mod. You can force a value to replay exactly the
same world.

```bash
.venv/bin/python -m tool generate              # time-based, unique seed
.venv/bin/python -m tool generate --seed 5     # fixed, reproducible seed
.venv/bin/python -m tool generate --demo       # synthetic vanilla base (tests)
```

### 3. Install the mod into Factorio

Set your mods folder as an override in `config/user.yaml`, key
`paths.factorio_mods` (e.g.
`~/.var/app/com.valvesoftware.Steam/.factorio/mods` for a Steam flatpak
install; the default `""` lives in `config/defaults.yaml`).

```bash
.venv/bin/python -m tool generate --seed 5 --install
```

`--install` assembles the mod and copies it into
`factorio_mods/randputF_<version>/` (version read from `mod/info.json`), then
enables it in `mod-list.json`. If the mods folder can't be found, the mod is
assembled into `output/` and the path is printed for manual copying.

On launch: the drawn patches replace vanilla resources around your spawn, the
starting kit is injected, and the free researches are granted. The classic goal
remains: **launch the rocket**.

## Configuration

Configuration is read from two YAML files, never from hardcoded values:

| File | Role |
|---|---|
| `config/defaults.yaml` | **Single source of truth** for all default settings (do not edit) |
| `config/user.yaml` | Your optional overrides |

The two are deep-merged then **validated** (types, ranges, `min <= max`,
cross-field constraints): an unknown key or an impossible value is an explicit
error, never a silent fallback. The merged config is always complete (all
sections/keys present), so the engine never carries a hardcoded default.

The four main sections (`paths`, `map`, `starter`, `recursive`), every key, and
the validation rules are documented in [`docs/config.md`](docs/config.md).

## What a generation produces

In `output/randputF_<version>/` (or directly in `<factorio_mods>/` with
`--install`):

```
randputF_<version>/
├── control.lua            # runtime: patch placement, starting kit, unlocks
├── data.lua               # data-stage: reads the seed, builds recipes/techs
├── data-updates.lua       # lake tiles, vehicle rearm, unified fuel
├── data-final-fixes.lua
├── info.json              # mod metadata
├── locale/                # French and English translations
├── graphics/              # icons / textures
├── seed/
│   ├── seed.json          # the generated seed: patches, recipes, techs, pools
│   └── seed.lua           # the same seed in Lua format, loaded by the mod
└── seed.graph.html        # interactive production graph (see below)
```

The output is **deterministic**: the same seed produces exactly the same mod
(byte-for-byte), verified by tests **across processes** and **independently of
order** (a seed generated after 1400 others in the same process stays
byte-identical to a clean process). The seed is injected as a string into
`random.Random` — values with dozens of digits are accepted.

## The interactive graph

Each generation exports **`seed.graph.html`**: the production map of your seed,
self-contained, to open in a browser. It shows, for every item, its crafting
chain (ingredients → recipe → product), the tech that unlocks it, the required
science packs, and the raw items extracted from the ground.

Navigation:

- click an item in the list **or** on a graph node to open its **card**:
  ingredients, alternative recipes, "used by" items;
- a multi-recipe item shows an **alternative recipe** selector in the card;
- **zoom / pan** on the large graph: wheel to zoom, drag to navigate,
  double-click to fit, resizable side panel;
- the **sub-graph** box isolates the selected item's cascade; **raw resources**
  are detection terminals (their ingredients are not explored);
- the science legend and appearance tech number help locate where to unlock each
  link.

> The graph is only generated by `generate` **without** `--install`. Run
> `generate --seed <n>` without `--install` to get `seed.graph.html`.

## Project structure

See [`docs/architecture.md`](docs/architecture.md) for the per-file breakdown.

## Licence

MIT — see [`LICENSE`](LICENSE).

## Development

- **Full history**: `master` carries the whole development history. Versions are
  tags on top ([`v1.0.0`](https://github.com/Flamaiche/randputF/releases/tag/v1.0.0),
  [`v1.0.1`](https://github.com/Flamaiche/randputF/releases/tag/v1.0.1)): a tag
  is the published state, nothing is rewritten afterwards.
- **Work branch**: [`dev`](https://github.com/Flamaiche/randputF/tree/dev) takes
  the changes in progress. `master` is never pushed directly: everything goes
  through `dev`, then through the tag, and `master` is aligned onto that tag.
  Procedure: [`docs/release.md`](docs/release.md).
- **Changelog**: [`CHANGELOG.md`](CHANGELOG.md).
- **AI assistant**: parts of the documentation and code were written or
  reviewed with the help of an AI assistant. All design, decisions and fixes
  were driven and validated by the maintainer.