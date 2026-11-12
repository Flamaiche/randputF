# Changelog

Résumé des versions, format « highlights ». Le détail technique et le
catalogue des corrections seed par seed vivent dans
[`docs/`](docs/README.md) — notamment [DEVIANCES.md](docs/DEVIANCES.md) (bugs et
dérives), [solvabilite.md](docs/solvabilite.md) (preuves) et
[nondeterminism.md](docs/nondeterminism.md).

Format : les faits sont repris des docs, jamais inventés ici. « gaté » est le
vocabulaire du projet (gating, §16 de `seed.md`), pas une faute.

---

## v0.0.2 (en préparation)

Le pipeline devient entièrement piloté par les faits du dump : la résolution
du fluide pompé, les packs de science et la chaîne de victoire se déduisent
des données brutes, plus aucun nom vanilla en dur côté outil.

Le correctif d'auto-sélection des fours et la difficulté comparée à vanilla
figurent dans **cette** version : la v0.0.1 publiée ne les contient pas
(étiquetage erroné corrigé dans les docs — le tag `v0.0.1` et son témoin font
foi).

### Exporter 0.1.5 — le dump ne porte que du brut

- Le dump embarque désormais l'**inventaire complet** (39 tables A→Z), les
  **52 tuiles** (`collision_layers`, `fluid`) et les règles de placement
  par entité (`tile_buildability_rules`). Le littéral `pumped_fluid` disparaît
  du dump : la résolution est testable côté Python.
- `inject_pumped_fluids` résout le fluide pompé par les faits : fluidbox de
  sortie des **sources pures** (rien → fluide, la porte évite de confondre
  boiler/heat-exchanger), sinon **chaîne de tuiles** (`required_tiles` →
  tuiles → `fluid`, un seul fluide distinct sinon `None`). Idempotente.
  Validée sur le dump réel du jeu 2.1.24.

### Science et victoire par les faits

- `science_pack_names` : les packs de science reconnus par les coûts de
  techs ∪ `lab_inputs` (7 en vanilla — `space-science-pack` n'est dans aucun
  coût de tech) ; le `subgroup` « science-pack » n'est plus consulté.
- `rocket_chain_from_dump` → `VanillaDB.rocket_chain` : la **chaîne de
  lancement** dérivée des faits (`rocket_parts_required`, recettes de fusée,
  `rocket_launch_products`). Le rejoueur s'en sert comme condition de
  victoire — **plus aucun nom d'item en dur** (`VICTORY_ITEMS` et
  `"satellite"` supprimés, garde-fou lab par tag `is_research`) : un mod qui
  remplace la fusée reste vérifié tel quel. Verdicts inchangés sur les seeds
  de référence (victoires et compteurs identiques).
- Vérification approfondie du rejoueur : la chaîne fusée, les bâtiments et
  les **packs spatiaux** sont réellement fabriqués (pas seulement
  obtenables) — verrouillé par un test permanent.

### Recettes — auto-sélection des fours

- Les fours (`stone-furnace`, `steel-furnace`, `electric-furnace`) et le
  `rocket-silo` n'ont pas d'écran de choix de recette : à ingrédients égaux,
  Factorio retient la **première** recette du prototype et rendait la suivante
  **inatteignable**. Le générateur impose désormais des **ingrédients
  disjoints** par bâtiment auto-sélection : re-tirage à la création
  (`recipes.py`) et correction en aval dans la passe d'usage
  (`usage_pass._correct_auto_select` — déplacement, retrait d'ingrédient ou
  passage en craft manuel). Validé sur **2000 seeds** (zéro recette ombragée),
  tests `test_auto_select_ingredients_disjoints` et
  `test_auto_select_repli_four_1slot`.

### Difficulté comparée à vanilla

- `randputf compare` génère une seed et écrit `seed.difficulty.html` : la
  **courbe de difficulté cumulée** (ressources brutes par tech) de la seed
  superposée à une baseline **vanilla** dérivée du dump. La même sortie est
  écrite pendant `generate` quand le dump porte les technologies. Le calcul
  reste **à l'export**, jamais sur le chemin de génération.
- Le graphe est **interactif** : survoler une tech affiche un repère et une
  infobulle (numéro, nom, coût propre, cumul, items débloqués, écart
  mod − vanilla) ; un clic épingle ; la légende masque/affiche une série ; les
  tableaux par tech mettent le point correspondant en évidence. SVG généré en
  Python pur, aucune dépendance externe.

### Chaîne de progression

- La seed porte un tag `is_progression` (vrai/faux) sur items et fluides :
  ce que la partie doit produire pour avancer, jusqu'aux packs de science.
  64 entrées en vanilla. Le rapport HTML affiche la colonne tags
  « science »/« progression » et la ligne de contrôle correspondante.

### Navigateur du dump

- `randputf dump` : page HTML unique sans dépendance — inventaire A→Z,
  tuiles, entités (fluidbox, énergie, règles de placement), items/fluides,
  recettes, technologies, avec recherche globale. `output/vanilla.dump.html`.

### Documentation

- `docs/graphe-interactif.md` couvre désormais les **trois vues HTML** de la
  génération (`seed.graph.html`, `seed.complexity.html`,
  `seed.difficulty.html`) et la commande `compare` — la fusion de branches
  avait conservé une version antérieure à la courbe de difficulté interactive
  (infobulle, épinglage, légende, tableaux liés).
- `docs/modules.md` §9 : inventaire des exporters complété (8 modules —
  `complexity_graph`, `difficulty_graph`, `vanilla_complexity`, `dump_html`,
  `report`, `html_ui` manquaient) ; arbre de `docs/architecture.md` aligné.
- **Auto-sélection & difficulté** : `docs/invariants.md` (invariant n°8),
  `docs/recettes.md`, `docs/tags.md`, `docs/vanilladb.md` (champ `auto_select`),
  `docs/pipeline.md` et `docs/modules.md` (graphe de difficulté), et
  `docs/graphe-interactif.md` (les vues HTML).
- Récit des versions remis à plat : la v0.0.1 publiée ne contient **ni** le
  correctif des fours **ni** la difficulté comparée (tag `v0.0.1` et témoin
  `c956613…` vérifiés) — la note et le CHANGELOG les étiquetaient v0.0.1 à
  tort ; ils sont documentés en v0.0.2. CI : le témoin attendu est celui de
  l'état courant du dépôt.

### Déterminisme vérifiable

- **Témoin de reproductibilité** : `randputf witness --seed 5 --expect
  0e767f5d91c3d0e7838e0c75c0dbd064` (état courant du dépôt, dump 0.1.5 ;
  vérifié depuis un wheel installé hors checkout, comme le job CI). Il
  **changera** au bump vers 0.0.2 (préfixe racine `randputF_<version>`) et la
  seed 5 est touchée par le correctif d'auto-sélection. Les sorties HTML
  (`seed.graph.html`, `seed.difficulty.html`) sont **exclues** du témoin, comme
  le graphe de production l'était déjà.

### Garanties mesurées

- **762 tests** verts sur le dump réel 0.1.5.
- Parité du rapport vanilla inchangée (64 entrées, 10 090 834 crafts,
  13 850 040 s de minage, 3 lancements, offshore-pump en bâtiments).

---

## v0.0.1

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

- **Témoin** : `randputf witness --seed 5 --expect c9566134864507d900f65806ade277d9`.
  Le contenu du mod pour la seed 5 est inchangé depuis la v0.0.0, mais le
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
- L'orchestration de génération est factorisée dans `tool/service.py`, désormais
  partagée entre la CLI et l'interface graphique (à venir). **Aucun changement
  de comportement** : c'est un déplacement de code, pour que la future
  IG ne puisse pas diverger de la CLI — si elle réimplémentait la génération,
  le témoin ne garantirait plus rien pour le joueur qui passe par elle.

### Garanties mesurées

- **722 tests** verts.
- **1501/1501** parties rejouées victorieuses (seeds 0-1500), rejoueur « fake
  player » ; invariants de solvabilité garantis pour toute seed acceptée.
- Balayages 0-2000 à **2000/2000** victoires, avertissement des fours inclus.

### Numération

La configuration à deux YAML est un changement visible par l'utilisateur, qui
relèverait d'un numéro mineur (0.1.0) en semver. Cette version sort en
**0.0.1** par choix du mainteneur ; le semver reprend ses règles dès la
prochaine version.

---

## v0.0.0

Première release publique. Randomizer total déterministe pour Factorio 2.0
(base, sans Space Age).

### Déterminisme vérifiable

- **Témoin de reproductibilité** : `randputf witness --seed 5 --expect
  f41e065e606ce24c8855d458c661988f`. Le même contenu de mod, à l'octet près,
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

[v0.0.0]: https://github.com/Flamaiche/randputF/releases/tag/v0.0.0