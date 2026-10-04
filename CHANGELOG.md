# Changelog

Résumé des versions, format « highlights ». Le détail technique et le
catalogue des corrections seed par seed vivent dans
[`docs/`](docs/README.md) — notamment [DEVIANCES.md](docs/DEVIANCES.md) (bugs et
dérives), [solvabilite.md](docs/solvabilite.md) (preuves) et
[nondeterminism.md](docs/nondeterminism.md).

Format : les faits sont repris des docs, jamais inventés ici. « gaté » est le
vocabulaire du projet (gating, §16 de `seed.md`), pas une faute.

---

## v1.0.1

Configuration en deux YAML et parcours joueur. Le contenu du mod pour une seed
donnée est inchangé ; ce sont la configuration, l'installation et la doc qui
bougent.

### ⚠️ Changement de configuration — migration requise

`config/settings.yaml` est **remplacé** par deux fichiers :

- `config/defaults.yaml` — tous les réglages par défaut, source unique, non
  modifiable ;
- `config/user.yaml` — les surcharges du joueur, facultatives.

Vos surcharges se recopient telles quelles dans `user.yaml` (mêmes clés, mêmes
sections). `settings.yaml` n'est plus lu. La config fusionnée est **validée**
(type, plage, `min <= max`, contraintes croisées) : une clé inconnue ou une
valeur impossible est une erreur explicite, jamais un défaut silencieux. Plus
aucune valeur en dur dans le moteur — prototypes, générateurs, CLI et pipeline
lisent tout depuis le YAML.

### Installation

- **Voie sans Python** : le zip attaché à la release est le mod complet, déjà
  généré. On le copie tel quel dans le dossier `mods`, on l'active, on joue.
  Le zip ne pèse que **52 Ko**.
- **Dossier `mods` documenté par système** : Windows, Linux, Steam Flatpak,
  macOS. Les commandes `venv` Windows (`Scripts\`) sont données.

### Déterminisme vérifiable

- **Témoin** : `randputf witness --seed 5 --expect ce428c2140ec7031f9604637ecf70cbc`.
  Le contenu du mod pour la seed 5 est inchangé depuis la v1.0.0, mais le
  témoin **change** au bump : le zip de référence a pour racine
  `randputF_<version>`, qui fait partie des entrées hachées.

### Documentation

- **Parcours joueur** : voie rapide sans Python, tableau des dossiers `mods`,
  section dépannage / FAQ (mod invisible, warning des fours, seed
  injouable, retrouver sa seed, erreur de config).
- **Conception** : index `docs/` complété (`modules.md`, `pipeline.md`,
  `runtime.md`, `vanilladb.md`), `docs/config.md`, `docs/witness.md`,
  `docs/release.md` (procédure de publication). `docs/architecture.md` §18
  remis à jour contre le code réel.
- `README_EN.md` aligné sur le README français.

### Outillage

- La publication est **automatique** : la promotion `dev` → `master` déclenche le
  build, le témoin, le zip et la publication de la note. Plus de tag à créer à
  la main. La suite de tests est exécutée **dans** le job de publication : une
  release ne peut plus sortir sur des tests rouges.
- Le zip de release exclut `seed.graph.html` (vue de debug de 5 Mo, déjà écartée
  du témoin) : 5,2 Mo → 52 Ko.
- Les tests ne dépendent plus de la version en dur : ils lisent
  `MOD_NAME_VERSIONED`.

### Garanties mesurées

- **722 tests** verts.
- **1501/1501** parties rejouées victorieuses (seeds 0-1500), rejoueur « fake
  player » ; invariants de solvabilité garantis pour toute seed acceptée.
- Balayages 0-2000 à **2000/2000** victoires, avertissement des fours inclus.

### Numération

La configuration à deux YAML est un changement visible par l'utilisateur, qui
relèverait d'un numéro mineur (1.1.0) en semver. Cette version sort en
**1.0.1** par choix du mainteneur ; le semver reprend ses règles dès la
prochaine version.

---

## v1.0.0

Première release publique. Randomizer total déterministe pour Factorio 2.0
(base, sans Space Age).

### Déterminisme vérifiable

- **Témoin de reproductibilité** : `randputf witness --seed 5 --expect
  12ac143e06174df126537b978ff928d3`. Le même contenu de mod, à l'octet près,
  vérifiable par n'importe qui (le hash est dans la CI et la release).
- **Canonisation indépendante de la machine et de la version de Python/zlib**
  (détail dans `docs/witness.md`).

### Garanties mesurées

- **722 tests** verts, rendus indépendants de l'environnement.
- **Rejoueur « fake player »** : **1501/1501 parties** rejouées victorieuses sur
  le balayage de seeds 0-1500 (rejouer une seed = la simuler comme un joueur la
  découvre). Invariants de solvabilité §15 garantis pour toute seed acceptée.
- **Déterminisme entre processus** et **indépendant de l'ordre** : une seed
  générée après 1400 autres reste byte-identique à celle d'un processus vierge
  (multi-sous-processus sous `PYTHONHASHSEED` 0/1/2).

### Corrections emblématiques (le chemin parcouru)

Le détail seed par seed est dans [DEVIANCES.md](docs/DEVIANCES.md). Les plus
significatifs :

- **Bootstrap sûr (seed 13)** : un cycle où l'électricité exigeait déjà
  l'électricité (turbine → landfill → tuyau → atelier électrique) rendait la seed
  injouable. Le redesign du bootstrap (graphe initial correct par construction)
  résout ce cas ; `bootstrap_guard` n'est plus une passe de production, il
  reste un diagnostic de test.
- **Fabrication d'atelier avec des ingrédients fluides (seed 426)** : la recette
  d'un bâtiment à ≥ 2 slots fluides se retrouvait hébergée dans un atelier
  fluide unlocké tard, donc jamais disponible à temps ; les bâtiments se
  fabriquent désormais uniquement avec des items.
- **Cycles d'hébergement (seeds 255, 1043)** : cycles mutuel (U2) et long (U1)
  créés par le ré-hébergement, cassés par les passes d'usage.
- **Ordre des effets `unlock-recipe` non déterministe (seed 1299)** : un `set`
  non trié rendait l'ordre des déblocages dépendant du hash de Python ; trié.
- **Jalon de raw gatée au 1er ingrédient (seed 1299)** : plancher recalculé sur
  l'usage réel (ingredients + ateliers).
- **Gating inerte (seed 1757)** : jalons tous ≤ 0 ; la passe B rejouée ne
  cassait plus rien.
- **Dépendance à l'ordre des seeds (seed 1269)** : la passe B mutait alors le
  config partagé ; état vierge porté par `StarterConfig.deferred`.

### Produit

- Mod Lua (`mod/`) produit par une CLI Python (`tool/`) ; dump JSON des
  prototypes vanilla embarqué (pas de dépendance runtime à l'exporter).
- Packaging wheel avec assets (`mod/`, `data/`, `config/`), vérifié par le job CI
  « wheel » (témoin exécuté hors checkout).
- Licence MIT. Documentation de conception complète dans [`docs/`](docs/README.md).

[v1.0.0]: https://github.com/Flamaiche/randputF/releases/tag/v1.0.0