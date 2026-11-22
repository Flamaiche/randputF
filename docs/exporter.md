# Exporter Factorio

Retour : [docs/README.md](README.md).

L'exporter est un petit mod compagnon qui photographie les prototypes du jeu. Il écrit un JSON consommé ensuite par l'outil Python. Il ne génère ni seed, ni mod, ni rapport HTML.

## Ce que ça change pour l'utilisateur

- Le dump est produit par Factorio lui-même, pas deviné par Python.
- Une nouvelle partie est nécessaire pour déclencher l'export.
- Un dump moddé est accepté et canonisé à la lecture.

## Mots à connaître

- [dump vanilla](glossaire.md) — photographie des prototypes du jeu de base.
- [prototype](glossaire.md) — définition d'un objet du jeu.
- [canonisation](glossaire.md) — normalisation d'un dump moddé à la lecture.
- [mod](glossaire.md) — mod compagnon installé dans Factorio.

## Fonctionnement

### Installation

Le dossier source est `exporter/`. Il contient `info.json` et `control.lua`. Il est copié dans le dossier mods Factorio sous le nom exact `randputf-exporter_0.1.8`.

| Système | Dossier mods |
|---|---|
| Windows | `%APPDATA%\Factorio\mods` |
| Linux | `~/.factorio/mods` |
| Linux Flatpak | `~/.var/app/com.valvesoftware.Steam/.factorio/mods` |

Une copie réelle est préférable à un lien symbolique sous Flatpak. La version déclarée dans `exporter/info.json` est écrite dans `meta.exporter_version`.

### Déclenchement

L'export se produit à la création d'une nouvelle partie, via `script.on_init`. Aucune commande ni interface n'est nécessaire. Le mod n'écrit rien dans une partie déjà chargée.

Deux fichiers de contenu identique sont écrits. Le fichier qualifié porte le nom `dump_mods_<label>_exporter_0.1.8.json`. L'alias stable est `randputF/vanilla_dump.json`. Le fichier qualifié conserve l'identité des mods actifs.

### Le contenu du dump

La version installée est 0.1.8 et le schéma est `2`. Le dump contient `meta`, `inventory`, `tiles`, `items`, `fluids`, `entities`, `recipes`, `technologies` et, quand le jeu l'expose, `mod_data`.

`meta` porte la version du jeu, le numéro de schéma, la version de l'exporteur, la liste des mods actifs et le libellé du dump. Le mod d'extraction ne fait pas partie de cette liste. `base` reste présent, mais n'entre pas dans le libellé.

Les sections brutes sont copiées telles quelles. Les champs indisponibles sont omis. `energy_source.buffer_capacity` fait partie des champs exportés.

### Dumps vanilla et moddés

Le dump vanilla sert de référence au générateur. Le dump moddé décrit l'état réel d'une partie où randputF est actif. Il contient des recettes préfixées, des prototypes neutralisés et des mutations de prototypes.

L'ancien garde-fou qui refusait ces dumps a été retiré. La canonisation à la lecture l'a remplacé. Le tool choisit une recette `randputf-X` active comme recette canonique du produit `X`. Les artefacts à double préfixe sont ignorés.

### Consommation

| Étape | Fichier ou commande |
|---|---|
| Acquisition | `exporter/control.lua` |
| Copie | `data/vanilla_dump.json` |
| Lecture | `tool/parsers/vanilla.py` |
| Génération | `tool/generator/pipeline.py` |
| Assemblage | `tool/exporters/mod_seed.py` |
| Navigation | `randputf dump` |
| Rapport complet | `randputf report` |
| Contrôle et rejeu | `randputf test` |

`generate` écrit les vues HTML disponibles sauf `--no-html` ; le graphe et la difficulté peuvent être omis. Le détail est dans [graphe-interactif.md](graphe-interactif.md).

### Écart connu

D'anciens textes annonçaient un refus explicite des dumps moddés. Le comportement courant est l'acceptation puis la canonisation. Reste à faire : remplacer ces avertissements par la description du comportement actuel.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| L'exporter copie les faits exposés par le runtime Factorio. | Certains champs dépendent de la version du jeu. |
| Les dumps moddés sont acceptés et canonisés. | Un dump moddé peut donner une seed différente. |
| Le schéma 2 est associé à l'exporteur 0.1.8. | Aucune version 0.1.9 n'est annoncée. |

## Aller plus loin

- [vanilladb.md](vanilladb.md) — à lire quand le schéma consommé doit être compris.
- [runtime.md](runtime.md) — à lire quand l'origine d'une mutation de dump est cherchée.
- [developpement.md](developpement.md) — à lire quand le dump doit être régénéré.
- [testeur.md](testeur.md) — à lire quand un dump doit être contrôlé.
- [config.md](config.md) — à lire quand le chemin du dump doit être changé.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [architecture.md](architecture.md) — place de l'exporter dans le projet.
- [modules.md](modules.md) — rôle du parseur dans l'outillage.
- [DEVIANCES.md](DEVIANCES.md) — écarts assumés liés au dump.
