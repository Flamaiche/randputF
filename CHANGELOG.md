# Changelog

Résumé des versions, format « faits saillants ». Le détail technique et le
catalogue des corrections seed par seed vivent dans
[`docs/`](docs/README.md) — notamment [DEVIANCES.md](docs/DEVIANCES.md) (bugs et
dérives), [solvabilite.md](docs/solvabilite.md) (preuves) et
[nondeterminism.md](docs/nondeterminism.md).

Format : les faits sont repris des docs, jamais inventés ici. « gaté » est le
vocabulaire du projet (gating, la section [« Seed et configuration »](docs/seed.md#seed-et-configuration-1) de `seed.md`), pas une faute.

---

## v0.0.2 (en préparation)

Le pipeline devient piloté par les faits du dump : la résolution du fluide
pompé, les packs de science et la chaîne de victoire se déduisent des données
brutes. Les ensembles figés résiduels restent documentés dans
[`docs/tags.md`](docs/tags.md).

Le correctif d'auto-sélection des fours et la difficulté comparée à vanilla
figurent dans **cette** version : la v0.0.1 publiée ne les contient pas
(étiquetage erroné corrigé dans les docs — le tag `v0.0.1` et son témoin font
foi).

### État courant

- Cible : Factorio 2.1, jeu de base, sans Space Age. Les versions 2.0 restent
  historiques (`v0.0.0`, `v0.0.1`).
- Documentation réécrite : 35 pages dans [`docs/`](docs/README.md), dont
  [`glossaire.md`](docs/glossaire.md), `etat-code.md`,
  `historique-nondeterminisme.md` et `lacs.md`. L'index est organisé par portes ;
  chaque page distingue le fonctionnement courant, les garanties et les écarts
  connus.
- `randputf generate --no-html` produit le mod et crée le dossier de rapports
  sans écrire de HTML. Sorties : mod dans `output/mods/randputF_<version>/`,
  rapports dans `output/reports/randputF_<version>/` (racine réglable par
  `--out`).
- `randputf compare` écrit `output/reports/compare/seed.difficulty.<seed>.html`
  et `randputf dump` écrit `output/reports/vanilla/vanilla.dump.html` (racine
  réglable par `--out`).
- Vues HTML plus lisibles : gros tableaux repliables, graphes de difficulté
  contextualisés et en échelle log quand nécessaire, navigateur adapté au
  mobile avec zoom tactile et navigation clavier, titres de dumps moddés et
  libellés de comparaison explicites, icônes de graphe dédupliquées.
- Un commentaire Lua invalide dans l'initialisation des épaves empêchait le
  chargement du mod ; il est corrigé et le témoin est recalculé en conséquence.
- Repères confirmés : 873 tests et témoin seed 5
  `e61667692c486e5b9c30efa9f4fbc891`, recalculé depuis le dépôt et depuis
  `/tmp`. Le dépôt n'a pas de mod pré-généré ; le workflow de release zippe le
  dossier `randputF_<version>` réellement généré, sans les trois HTML.
- Précisions : `--playthrough` ne déclenche pas le rejeu, il affiche seulement
  la section « partie simulée » du rapport.
- Textes visibles alignés sans changement de comportement : libellé des puits
  fluides (`N puits de pétrole`), `randputf-neutre` (« Fluide fantôme »), aide de
  `randputf audit` (« tags bâtiments et items (invariants C8/§9) »), messages
  `wreck` (`5t + 2a ≤ 100`, `a ≥ 1 et 6t + 3a < 100`), raison HTML « Version
  affichée et fournie au titre » et commentaires Lua/exporter.
- Écarts documentés, non corrigés : source du zip de release, commentaire
  `buffer_capacity`, sections `pools`/`weights` inertes, exclusions de patches,
  munitions, pylône et source de courant avant accumulateur. Le détail est dans
  [`DEVIANCES.md`](docs/DEVIANCES.md).

### Outils — inférence depuis le dump

- `tool/audit/difficulty.py` lit la chaîne de lancement dans `meta.rocket`
  (bâtiments, recette, pièce, quantité, produits) : plus de recette ni de
  quantité codées en dur.
- `tool/exporters/seed_graph.py` prend les packs et leur ordre dans
  `meta.science_packs` ; l'ancien fallback `*-barrel` d'icône disparaît.
- `tool/generator/late_raws.py`, `tool/replay/player.py` et
  `tools/classify_late_raws.py` n'acceptent un pack que s'il est déclaré par
  le dump ; `tool/__main__.py` affiche les produits de lancement dérivés.
- `tool/exporters/complexity_graph.py` reconnaît un bâtiment de lancement par
  `rocket_parts_required`, et `tool/common/db.py` les barils par leur
  sous-groupe. La baseline `build_vanilla_seed` garde ses exclusions
  historiques (rapport vanilla uniquement).

### Testeur — progression par étape

- `randputf test` affiche une barre Python pure, sans dépendance : nom de
  l'étape, barre, pourcentage de l'étape courante, numéro `n/5`, action, temps
  écoulé et fin estimée. Sur un terminal la ligne est rafraîchie sur place
 ;
  sinon un changement visible produit une ligne.
- Le découpage en cinq étapes vient de `tool.tester.STAGES` et
  `STAGE_LABELS` : acquisition du dump, contrôle de l'état, rejeu joueur,
  mesure de la difficulté et rapport HTML. Le contrôle et le rejeu remontent
  leur progression réelle à chaque affichage, sans saut direct de 0 à 100 %.
- Le testeur unifié joueur + contrôle est la source commune : la commande
  `test` enchaîne validation, rejeu et trois vues HTML dans
  `output/reports/<source>/`, pour vanilla, le mod seul et le modpack.
- La mesure de la difficulté est découpée : ardoise, série par technologie et
  tableau remontent leur progression. Le total calculé pour le rapport est
  réutilisé au lieu d'être recalculé une seconde fois.
- Le rapport ajoute un profil multi-axes (`tool/audit/profile.py`) : structure,
  volume, temps critique, nouveauté et infrastructure, normalisés contre la
  baseline vanilla. Chaque axe agrège ses indicateurs en moyenne géométrique ;
  l'indice global pondère les axes 25/20/20/20/15. Volumes et temps sont
  comparés en `log10(1 + valeur)` avec la valeur brute conservée dans le
  tableau. Avec `--mod-dir`, la baseline reste le dump vanilla par défaut au
  lieu du dump d'entrée, pour que la comparaison ne soit pas identique à la
  seed testée. Le détail est dans `#profil-difficulte-table` et disparaît avec
   `--no-difficulty`.
- Les rapports affichent les ratios `×N` directement à côté des valeurs de
  complexité, des classements ateliers/ressources et du profil. Les volumes et
  temps du profil restent comparés en échelle logarithmique, avec la valeur
  brute conservée dans le tableau.
- La complexité et la partie simulée remontent aussi leur progression : dépliage
  des recettes, tableau de complexité, simulation technologique et assemblage
  du rapport avancent la barre sans bloc muet sur les gros dumps. Le dépliage
  affiche `i/N techs · E étapes` ; son ETA est estimée après la première
   technologie terminée depuis le coût moyen des techs récentes et le débit
   d'étapes, sans pré-comptage coûteux. Le dépliage affiche en plus la profondeur,
   la fin du chemin de recettes et la quantité en cours pour montrer où il en est.
- Complexité et profil partagent un seul calcul mémoïsé
  (`tool/audit/graph.py`), au lieu d'un dépliage récursif par chemin : les
  cycles sont cassés une fois, le rapport modpack ne reste plus bloqué dans
  l'ancienne explosion d'étapes, et les scores de complexité changent par
  rapport au modèle exact précédent. C'est la source par défaut de
  `randputf test` et `randputf report` : la complexité lit les recettes et les
  stats du dump sans rejouer la partie. `--playthrough` active la simulation
  détaillée ; dans ce mode, la complexité réutilise ses compteurs au lieu de
  refaire un dépliage. Le choix de recette de la simulation est mémoïsé par lot
  de déblocages : les vraies recettes restent suivies, sans rescanner les
  producteurs à chaque appel. Le résultat complet est persisté dans le dump
  sous `randputf_cache.playthrough_v1`, avec une empreinte de la seed, du dump
  et de la version de l'outil : une commande suivante relit cette analyse au
  lieu de rejouer la partie. `--no-cache` force un recalcul.

- Le rejeu affiche `techs recherchées/total` dans son détail et en tire son ETA.
  L'ETA par pourcentage reste figée au dernier changement au lieu de grandir
  avec le seul temps écoulé ; les phases sans total connu affichent
  `fin étape —`.
- `randputf test` accepte `--playthrough` pour afficher la section « partie
  simulée » du rapport ; le rejeu reste exécuté sans lui. Il accepte aussi
  `--no-checks`, `--no-complexity`,
  `--no-difficulty`, `--no-cache`, `--no-report-html`, `--no-dump-html`,
  `--no-graph-html` et `--no-html` pour ignorer sélectivement calculs, cache
  et pages HTML. `randputf report` accepte aussi `--playthrough`. Les sections
   omises ne sont pas écrites dans le rapport.

### Performance du pipeline et des rapports

- Le navigateur HTML réutilise les icônes déjà recadrées au lieu de relire et
  recadrer chaque PNG une seconde fois (`tool/exporters/seed_graph.py`) : le
  graphe modpack reste byte-identique (`ff523822…f1905`) et son export passe
  de `6,34s` à `3,38s` sur le profil isolé. `tool/exporters/mod_seed.py` calcule
  une seule fois le classement des bâtiments par catégorie au lieu de le
  reconstruire pour chaque recette (`6,34s` → `5,61s` sur le même profil).
- Le rejeu joueur incrémentalise sa détection de maîtrise
  (`tool/replay/player.py`) : seuls les nouveaux déblocages, objectifs relevés,
  objets maîtrisés et changements de palier relancent un balayage, la file
  déduplique les objets déjà prêts et l'invalidation de cache n'est plus
  appelée deux fois par technologie. Sur le modpack, `Rejeu joueur` passe de
  `352,4s` à `165,3s` et le total de `371,9s` à `183,3s`, avec le même résultat
  (`934/934 techs, victoire`).
- Les vues HTML de débogage (`seed.graph.html`, `seed.difficulty.html`,
  `seed.complexity.html`) sont exclues du témoin de reproductibilité et de
  l'archive de release : le contrôle ne dépend plus de fichiers non
  déterministes, tandis que les rapports restent publiés.
- Le rapport allégé reconstruit sa table des matières depuis les sections
  réellement émises : les liens morts de `#difficulte` disparaissent avec
  `--no-difficulty`, et la progression de `#progression` reste strictement
   croissante même quand des sections entières sont omises.

### Sorties — rapports et mods séparés

- Les trois HTML du testeur vont désormais dans
  `output/reports/<source>/` (`vanilla`, `randputF_0.0.1` ou le label du
  modpack). Le dossier et les fichiers portent le même nom canonique :
  `<source>.report.html`, `<source>.dump.html`, `<source>.graph.html`.
- `randputf generate` assemble toujours le mod dans
  `output/mods/randputF_<version>/` et ses vues `seed.*.html` dans
  `output/reports/randputF_<version>/`. Aucun HTML n'est plus déposé dans le
  dossier du mod, y compris avec `--install`.
- Les noms `randputF-<version>` sont normalisés en `randputF_<version>` pour
  que le dossier du mod et celui du rapport utilisent la même étiquette.
- `compare`, `dump` et `report` écrivent aussi sous `output/reports/` ;
  `witness` continue de n'assembler qu'un mod, sous `output/mods/`.

### Rochers — le charbon devient de la pierre

- `huge-rock` produit en vanilla de la pierre **et du charbon**. Le charbon
  n'appartient pas au pool environnemental (`wood`, `stone`, `raw-fish`) ;
  `mod/data-final-fixes.lua` remplace donc chaque résultat `coal` d'un
  `simple-entity` rocheux par le **même montant** de `stone`.
- Vérifié sur un dump réel du jeu avec le mod chargé : `huge-rock` ne contient
  plus que deux résultats `stone` (`24..50` chacun), sans erreur de prototype.

### Exporter 0.1.8 — dump schéma 2, liaisons brutes

- `exporter/control.lua` émet `meta.game_version_numeric`,
  `meta.schema_version = 2` et `meta.exporter_version`. `seed_value` n'est plus
  figé à 0 : il vient de la version réelle du jeu.
- Le dump expose les faits déjà présents dans les prototypes : `order` sur les
  items/entités/recettes/technologies, `main_product`, `used_by_labs`,
  `science_capacity`, `selection_box`, `guns`, `energy_source.buffer_capacity`,
  les températures/couleurs de fluides et `research_unit_count_formula`.
- `mod/data-updates.lua` publie aussi `randputf-water-tiles`
  (`data_type = "randputf.water_tiles"`) ; `mod/control.lua` lit ce `mod-data`
  en priorité, avec repli statique pour les jeux sans `mod-data`.
- L'outil consomme ces liaisons
 au lieu de recréer des listes : packs de science
  et leur ordre, chaîne de fusée, armes montées (`entity.guns`), recette/parts
  de lancement. Les champs legacy restent émis pour les dumps anciens.
- `ITEM_LIKE_TYPES` inclut désormais `blueprint-book` et `spidertron-remote`.
- Dump clean régénéré : SHA-256
  `3a272ee9440e020ebc36f9a92c222720af1c53c4c6b65ce2b136d7ebee2c84ea`.
  Témoin seed 5 : `e61667692c486e5b9c30efa9f4fbc891` (vérifié depuis un wheel
  installé hors checkout). **873 tests** verts.

### Exporter 0.1.7 — `mod-data` pour les lacs

- `mod/data-updates.lua` publie le prototype `mod-data` `randputf-lake-tiles`
  (`data_type = "randputf.lake_tiles"`) : tuile fantôme source, fluide fantôme,
  `results` (fantôme → tuiles de lac) et `fluids` (tuile → fluide). C'est la
  source unique du mapping, lue au runtime et exportée dans le dump.
- `exporter/control.lua` ajoute `dump_mod_data()` et le champ `mod_data` du
  payload. `mod/control.lua` lit `prototypes.mod_data` en priorité (fluides
  et nom réel de tuile), avec repli sur la seed pour les versions sans
  `mod-data` (< 2.1.20).
- `inject_pumped_fluids` pose `pumped_fluids` quand plusieurs lacs partagent
  `water_tile` : la pompe offshore n'est plus ambiguë, et le fluide fantôme
  n'est jamais compté comme ressource. `pumped_fluid` reste renseigné quand un
  seul lac est réellement pompé.
- `VanillaDB.pumped_fluids`, les ressources brutes, le graphe de complexité et
  le navigateur de dump prennent en compte l'ensemble des fluides pompés.
- Validé sur un dump moddé réel Factorio 2.1.24 (seed 5) : `mod_data` et
  `pumped_fluid = "heavy-oil"` sont produits. **764 tests** verts.

### Exporter 0.1.6 — export moddé autorisé

- Le garde-fou qui annulait l'export quand `randputF` était actif est retiré :
  l'exporter écrit désormais le dump même depuis une partie randomisée, pour
  inspecter le contenu généré (`python -m tool dump`).
- Le dump moddé est désormais exploitable : l'exporter ajoute `enabled` et
  `hidden` aux recettes et technologies, ce qui permet de distinguer les
  prototypes vanilla neutralisés des prototypes randputF actifs sans supprimer
  aucun lien.
- Le tool canonise les recettes préfixées : pour un produit `X`, une recette
  `randputf-X` active remplace la recette vanilla `X` dans la génération. La
  clé logique est normalisée (`X`), le nom réel `randputf-X` reste conservé
  dans la DB. Les artefacts `randputf-randputf-…` restent ignorés.

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

- `randputf compare` génère une seed et écrit
  `output/reports/compare/seed.difficulty.<seed>.html` : la
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
  recettes, technologies, avec recherche globale.
  `output/reports/vanilla/vanilla.dump.html`.

### Documentation

- `docs/graphe-interactif.md` couvre désormais les **trois vues HTML** de la
  génération (`seed.graph.html`, `seed.complexity.html`,
  `seed.difficulty.html`) et la commande `compare` — la fusion de branches
  avait conservé une version antérieure à la courbe de difficulté interactive
  (infobulle, épinglage, légende, tableaux liés).
- `docs/modules.md` : la section [« `tool/exporters/` »](docs/modules.md#toolexporters) complète l'inventaire des exporters (9 modules —
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
  e61667692c486e5b9c30efa9f4fbc891` (état courant du dépôt, dump 0.1.8 ;
  vérifié depuis un wheel installé hors checkout, comme le job CI). Il
  **changera** au bump vers 0.0.2 (préfixe racine `randputF_<version>`) et la
  seed 5 est touchée par le correctif d'auto-sélection. Les sorties HTML
   (`seed.graph.html`, `seed.difficulty.html`, `seed.complexity.html`) sont
   **exclues** du témoin, comme

  le graphe de production l'était déjà.

### Garanties mesurées

- **873 tests** verts sur le dump réel 0.1.8 (schéma 2).
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
valeur impossible est une erreur explicite, jamais un défaut silencieux. Les
réglages du moteur viennent du YAML ; les ensembles figés résiduels restent
documentés dans [`docs/tags.md`](docs/tags.md).

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
  section dépannage / FAQ (mod invisible, avertissement des fours, seed
  injouable, retrouver sa seed, erreur de config).
- **Conception** : index `docs/` complété (`modules.md`, `pipeline.md`,
  `runtime.md`, `vanilladb.md`), `docs/config.md`, `docs/witness.md`,
  `docs/release.md` (procédure de publication). Dans `docs/architecture.md`, la
  section [« Structure du projet »](docs/architecture.md#structure-du-projet) a
  été remise à jour contre le code réel.
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

Première release publique. Randomiseur total déterministe pour Factorio 2.0
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
  découvre). Les invariants de solvabilité sont garantis pour toute seed acceptée ; voir la section [« Règles de solvabilité »](docs/solvabilite.md#règles-de-solvabilité).
- **Déterminisme entre processus** et **indépendant de l'ordre** : une seed
  générée après 1400 autres reste byte-identique à celle d'un processus vierge
  (multi-sous-processus sous `PYTHONHASHSEED` 0/1/2).

### Corrections emblématiques (le chemin parcouru)

Le détail seed par seed est dans [DEVIANCES.md](docs/DEVIANCES.md). Les plus
significatifs :

- **Bootstrap sûr (seed 13)** : un cycle où l'électricité exigeait déjà
  l'électricité (turbine → landfill → tuyau → atelier électrique) rendait la seed
  injouable. La refonte du bootstrap (graphe initial correct par construction)
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