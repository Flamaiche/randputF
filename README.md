# randputF

![Licence MIT](https://img.shields.io/badge/licence-MIT-blue)

**Randomizer total pour Factorio 2.0 (base, sans Space Age).**

randputF ne se contente pas de mélanger des recettes entre elles : il régénère
l'intégralité du jeu — ressources au sol, recettes (entrées *et* sorties),
bâtiments débloqués, arbre technologique, kit de départ — en garantissant à
chaque graine (*seed*) un parcours valide, sans boucle, du premier coup de
pioche au lancement de la fusée.

Ce README couvre l'installation et l'utilisation. La référence de conception
(comment le système fonctionne, pourquoi il est construit ainsi) vit dans
[`docs/`](docs/README.md).

## Table des matières

1. [Installation](#installation)
2. [Configuration : `config/defaults.yaml`](#configuration--configdefaultsyaml)
3. [Ce que produit une génération](#ce-que-produit-une-génération)
4. [Le graphe interactif](#le-graphe-interactif)
5. [Dépannage / FAQ](#dépannage--faq)
6. [Système de dev (dump vanilla)](#système-de-dev-dump-vanilla)
7. [Structure du projet](#structure-du-projet)

---

## Installation

### Voie rapide : jouer sans installer Python

**Le mod est téléchargeable tout prêt.** Chaque release attache un
`randputF_<version>.zip` — c'est le mod complet, déjà généré. Aucune
installation, aucune ligne de commande.

1. Télécharge `randputF_<version>.zip` depuis la page
   [Releases](https://github.com/Flamaiche/randputF/releases).
2. Copie le zip **tel quel** dans le dossier `mods` de Factorio — il n'a pas
   besoin d'être décompressé.
3. Lance Factorio, menu **Mods**, active `randputF`.

C'est tout : tu joues. Le zip contient une seed déjà générée (seed 5, celle
utilisée pour les tests de déterminisme).

Pour **une autre seed**, il faut l'outil Python → [voie complète](#voie-complète-avec-python).

> Le zip ne contient pas `seed.graph.html`, la vue interactive de 5 Mo : elle se
> régénère chez toi avec la voie complète (`randputf generate`). Le mod lui-même
> n'en a pas besoin.

### Dossier `mods` selon ton système

| Système | Chemin |
|---|---|
| **Windows** | `%APPDATA%\Factorio\mods` |
| **Linux** | `~/.factorio/mods` |
| **Linux (Steam Flatpak)** | `~/.var/app/com.valvesoftware.Steam/.factorio/mods` |
| **macOS** | `~/Library/Application Support/factorio/mods` |

Linux : `xdg-open ~/.factorio/mods` pour l'ouvrir. Windows : `%APPDATA%` dans la
barre d'adresse de l'explorateur.

### Voie complète avec Python

Pour générer **d'autres seeds**, ou pour explorer le graphe interactif.

#### Prérequis

- **Factorio 2.0** (base, sans Space Age) installé ;
- **Python 3.11+**.

#### 1. Préparer l'environnement Python

```bash
python3 -m venv .venv
.venv/bin/pip install .          # paquet + assets (mod/, data/, config/) embarqués
```

Sous Windows, les commandes passent par `.venv\Scripts\` :

```bat
python -m venv .venv
.venv\Scripts\pip install .
```

L'install **classique** embarque les trois dossiers d'assets dans le wheel :
`randputf` fonctionne depuis n'importe quel répertoire. En développement sur
ce dépôt, `pip install -e .` marche aussi bien (les chemins retombent sur le
checkout).

> **Deux façons d'appeler l'outil, même programme.** Après `pip install .`, la
> commande `randputf` est disponible et c'est celle des exemples de ce README :
>
> ```bash
> randputf generate --seed 5
> ```
>
> Depuis un simple checkout du dépôt, sans installation, on passe par le module :
>
> ```bash
> .venv/bin/python -m tool generate --seed 5
> ```
>
> Les exemples ci-dessous utilisent la forme longue `python -m tool` parce
> qu'elles fonctionnent dans les deux cas.

L'outil consomme un **dump des prototypes vanilla** inclus
(`data/vanilla_dump.json`) — rien à faire pour jouer. La régénération de ce dump
est documentée dans la [section Système de dev](#système-de-dev-dump-vanilla).

#### 2. Générer une seed

Par défaut, la seed est tirée de l'instant présent (millisecondes) : chaque
génération produit un mod unique. On peut imposer une valeur pour rejouer
exactement le même monde.

```bash
.venv/bin/python -m tool generate              # seed temporelle, unique
.venv/bin/python -m tool generate --seed 5     # seed figée, reproductible
.venv/bin/python -m tool generate --demo       # base vanille synthétique (tests)
```

#### 3. Installer le mod dans Factorio

Le chemin du dossier mods se configure en surcharge dans `config/user.yaml`,
clé `paths.factorio_mods` (les chemins par système sont dans le tableau ci-dessus).
Le défaut (`""`) vit dans `config/defaults.yaml` (source unique) ;
`config/user.yaml` ne porte que tes surcharges (template déjà fourni dans le
dépôt).

```bash
.venv/bin/python -m tool generate --seed 5 --install
```

`--install` assemble le mod complet et le copie dans
`<factorio_mods>/randputF_<version>/` (la version est lue dans `mod/info.json`),
puis active le mod dans `mod-list.json`. Si
le dossier mods est introuvable, le mod est assemblé dans `output/` et le
chemin est affiché : il reste à le copier manuellement dans le dossier mods.
Désactivez le mod à tout moment via le menu Mods de Factorio.

Au lancement d'une partie : les gisements tirés remplacent les ressources
vanilles autour du spawn, le kit de départ est injecté, les recherches
gratuites débloquées. L'objectif reste classique — **lancer la fusée**.

## Configuration : `config/defaults.yaml`

`config/defaults.yaml` est la source UNIQUE des réglages (non modifiable à
l'usage) ; tes surcharges passent par `config/user.yaml`, fusionnées puis
VALIDÉES contre un schéma strict (type, plage, bornes `min <= max`,
contraintes croisées) : une clé inconnue ou une valeur impossible est une
erreur explicite, jamais une génération à l'aveugle. Un config fusionné est
toujours complet (toutes les sections/clés existent), donc aucune valeur de
secours n'est codée dans le moteur.

Les 4 sections principales :

| Section | Rôle |
|---|---|
| `paths` | Dossiers : *factorio_mods* (installation) — à surcharger dans `user.yaml` pour ton install |
| `map` | Nombre et richesse des gisements, blocs/puits par gisement, rayons |
| `starter` | Munitions du kit (`ammo_count`), bras optionnel (`inserter_chance`), combustible |
| `recursive` | Phase récursive : poids par catégorie, armes montées, véhicules |

La **référence complète** des 16 sections, de chaque clé et des règles de
validation est dans [`docs/config.md`](docs/config.md).

La signification détaillée de chaque clé est décrite dans
[`docs/config.md`](docs/config.md) et [`docs/seed.md`](docs/seed.md), et référencée
au fil des sections de conception.

## Ce que produit une génération

Dans `output/randputF_<version>/` (ou directement dans `<factorio_mods>/` avec
`--install`) :

```
randputF_<version>/
├── control.lua            # runtime : placement des gisements, kit départ, déblocages
├── data.lua               # data-stage : lecture de la seed, construction recettes/techs
├── data-updates.lua       # tuiles de lacs, réarmement des véhicules, fuel unifié
├── data-final-fixes.lua
├── info.json              # métadonnées du mod
├── locale/                # traductions françaises et anglaises
├── graphics/              # icônes / textures
├── seed/
│   ├── seed.json          # la seed générée : gisements, recettes, techs, pools
│   └── seed.lua           # la même seed au format Lua, chargée par le mod
└── seed.graph.html        # graphe de production interactif (voir plus bas)
```

`seed.graph.html` est **autonome mais lourd** (~7,2 Mo : les icônes vanilla sont
embarquées en base64). À ouvrir **en local**, pas à héberger : chaque génération
le régénère.

La sortie est **déterministe** : une même seed produit exactement le même mod
(octet-pour-octet), vérifié par les tests **entre processus** (y compris pour
le jalonnement late raws) **et indépendamment de l'ordre** : une seed générée
après 1400 autres dans le même process reste byte-identique à celle d'un
process vierge (régression gardée, seed 1269). La seed s'injecte comme chaîne
dans `random.Random` — les valeurs jusqu'à des dizaines de chiffres sont
acceptées.

> Warning runtime « fours » : si une console de partie affiche un message de
> recette four non satisfaite, sache qu'il est **documenté et assumé** —
> `docs/DEVIANCES.md` §3.1 (2000/2000 parties rejouées gagnées le prouvent).

## Le graphe interactif

Chaque génération exporte **`seed.graph.html`** : la carte de production de
ta seed, autonome, à ouvrir dans un navigateur. Il montre, pour chaque item de
la partie, sa chaîne de fabrication (ingrédients → recette → produit), la tech
qui le débloque, les sciences requises, et les items « bruts » extraits du sol.

Navigation :

- clique sur un item dans la liste **ou** sur un nœud du graphe pour ouvrir sa
  **fiche** : ingrédients, recettes alternatives (multi-recettes), items
  « utilisé par » ;
- un item multi-recettes affiche un sélecteur **autre recette** dans la fiche :
  la cascade se recalcule selon la recette en cours ;
- **zoom / pan** sur le grand graphe : molette pour zoomer, glisser pour
  naviguer, double-clic pour ré-adapter la vue, panneau latéral
  redimensionnable (poignée à droite de la liste) ;
- le **sous-graphe** (case « sous-graphe ») isole la cascade de l'item
  sélectionné ; les **ressources brutes** sont des terminaux de détection : on
  n'explore pas leurs ingrédients, même si elles ont un craft ;
- la légende des sciences et le numéro de tech d'apparition aident à repérer
  où débloquer chaque maillon.

> Le graphe n'est généré que par `generate` sans `--install`. Avec
> `--install`, le mod est copié tel quel (sans le graphe) ; relancez
> `generate --seed <n>` sans `--install` pour obtenir `seed.graph.html`.

## Dépannage / FAQ

**Le mod n'apparaît pas dans le menu Mods.**
Le zip doit être dans le dossier `mods` (tableau plus haut), pas dans un
sous-dossier. Vérifie aussi qu'il est **activé** dans le menu Mods — un mod
présent mais désactivé n'apparaît pas dans une partie. Avec la voie Python,
`generate --install` le copie et l'active tout seul, et affiche le chemin exact
utilisé.

**Le mod n'apparaît pas dans une partie déjà lancée.**
Factorio n'intègre pas un mod en cours de partie : relance la partie après
avoir activé le mod.

**« usage_pass warning: \<four\>: consommé mais aucun candidat à rattacher ».**
Avertissement **résiduel et non bloquant**, assumé. Il concerne les fours
(`stone-furnace`, `steel-furnace`, `electric-furnace`) : leur item est bien
consommé par d'autres recettes, mais ce four-là n'héberge aucune recette
propre. Balayages vérifiés à **2000/2000 victoires** avec ce warning présent.
Détail dans [`docs/DEVIANCES.md`](docs/DEVIANCES.md) §3.1.

**Ma seed est-elle vraiment jouable ?**
Oui — c'est une garantie mesurée, pas un espoir. **1501 parties sur 1501**
(seed 0 à 1500) ont été rejouées victorieuses par un rejoueur « fake player »,
et les invariants de solvabilité sont garantis pour toute seed acceptée.
[`CHANGELOG.md`](CHANGELOG.md) et [`docs/solvabilite.md`](docs/solvabilite.md) §15.

**Comment retrouver la seed d'un mod ?**
Elle est affichée à la génération (`Seed <valeur> valide`) et stockée dans le
mod, dans `seed/seed.json`, champ `meta.seed` (avec `meta.generator_version` et
`meta.factorio_version`). Le rejouer exactement : `generate --seed <valeur>`.

**Puis-je lancer la même seed deux fois et obtenir le même monde ?**
Oui. Le md5 canonique du mod est vérifiable par n'importe qui :
`randputf witness --seed 5 --expect <md5>`. Détail dans
[`docs/witness.md`](docs/witness.md).

**J'ai une erreur de configuration.**
Une clé inconnue ou une valeur hors plage est refusée à la génération, avec le
message qui dit quoi. Les clés valides sont listées dans
[`docs/config.md`](docs/config.md).

## Système de dev (dump vanilla)

Le tool ne devine rien : il consomme un **dump JSON des prototypes** produit
par ton propre jeu, via le mod compagnon `exporter/`. Nécessaire seulement
pour re-générer ce dump (ajout de contenu, nouvelle version du jeu) :

1. copie (ou symlink) `exporter/` dans `~/.factorio/mods/randputf-exporter_0.1.0/` ;
   si le symlink n'est pas détecté (sandbox Flatpak), utilise une copie du dossier ;
2. **désactive `randputF` pour cet export** (l'exporter refuse sinon) ; lance
   Factorio une partie quelques secondes — à l'init, il écrit
   `script-output/randputF/vanilla_dump.json` dans le dossier user-data ;
3. remplace `data/vanilla_dump.json` du dépôt par ce fichier. En install
   classique, le dump voyage dans le wheel (`data/vanilla_dump.json` sous le
   paquet) : sa régénération passe par un ré-install (`pip install .`) ou un
   checkout du dépôt ;
4. l'exporter reste un outil compagnon de développement, destiné à disparaître
   ou fusionner dans le mod principal.

> **Pourquoi désactiver `randputF` pour l'export** : exporter depuis une partie
> où randputF est actif écrirait un dump « pollué ». La pollution n'est pas que
> des recettes `randputf-*` ajoutées — surtout, des prototypes vanilla sont
> MUTÉS en place (ex. `fuel_value` 0 → 200 000 sur `crude-oil`), des valeurs qui
> ressemblent à du contenu légitime et qui changent la seed sans rien casser.
> Trois barrières s'en protègent : l'exporter **refuse** un export pollué (log
> explicite, aucun fichier écrit), le tool **rejette** un dump déjà muté au
> chargement (invariant vanilla 2.0 `fuel_value == 0`), et le filtre `randputf-`
> couvre le canal additif des dumps anciens. Pendant une partie normale, les
> deux mods peuvent rester actifs.

## Structure du projet

```
randputF/
├── README.md            # ce document (installation, utilisation)
├── README_EN.md         # version anglophone (doc de conception reste en FR)
├── CHANGELOG.md         # résumé des versions, corrections emblématiques
├── docs/                # documentation de conception (voir docs/README.md)
├── config/
│   ├── defaults.yaml     # réglages par défaut (source unique, non modifiable)
│   └── user.yaml         # surcharges utilisateur (facultatives, validées)
├── data/
│   └── vanilla_dump.json # dump des prototypes vanilla
├── tool/                # générateur externe Python (python -m tool)
│   ├── __main__.py      # CLI : parse, audit, difficulty, generate
│   ├── common/          # VanillaDB, ItemDef, demo, WeightedPicker
│   ├── audit/           # audit des tags bâtiments/items
│   ├── parsers/         # extraction des prototypes vanilla
│   ├── generator/       # moteur de tirage & graphe (phases, passe A/B)
│   ├── prototypes/      # classes de configuration
│   ├── exporters/       # écriture seed.json / seed.lua / graphe
│   ├── replay/          # rejoueur de seed (audit externe)
│   └── validator/       # vérification de solvabilité
├── tools/               # scripts dev (classify_late_raws, audits par paquet)
├── mod/                 # source du mod Factorio 2.0
├── exporter/            # mod compagnon (dump JSON des prototypes)
├── tests/               # tests unitaires (pytest)
└── output/              # mods assemblés (généré)
```

Le détail par fichier est décrit dans
[`docs/architecture.md`](docs/architecture.md#18-structure-du-projet).

---

## Licence

MIT — voir [`LICENSE`](LICENSE).

---

## Outils et développement

- **Tags** : les versions sont des tags Git posés sur `master`. Un tag est l'état
  publié, rien n'est réécrit après coup. La version publiée est
  [`v1.0.0`](https://github.com/Flamaiche/randputF/releases/tag/v1.0.0). La v1.0.1
  est en préparation sur `dev` et n'a jamais été publiée (procédure :
  [`docs/release.md`](docs/release.md)).
- **Branche de travail** : [`dev`](https://github.com/Flamaiche/randputF/tree/dev)
  accueille les changements en cours. `master` n'est jamais poussée
  directement : tout passe par `dev`, et la promotion `dev` → `master` **est** la
  release (elle déclenche le build et la publication). Procédure dans
  [`docs/release.md`](docs/release.md).
- **Changelog** : [`CHANGELOG.md`](CHANGELOG.md). Corrections seed par seed et
  garanties mesurées, en résumé.
- **English README** : [`README_EN.md`](README_EN.md) pour les joueurs
  anglophones (la doc de conception reste en français).
- **Assistant IA** : la documentation et certains passages de code ont été
  rédigés ou relus avec l'aide d'un assistant IA. Toute la conception, les
  décisions et les corrections ont été pilotées et validées par le
  mainteneur.

*randputF — chaque partie est un jeu que personne n'a jamais vu.*