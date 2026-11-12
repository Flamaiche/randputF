# Les vues HTML de la génération (`seed.graph.html`, `seed.complexity.html`, `seed.difficulty.html`)

À côté de `seed/seed.json`, l'export `--out` écrit **trois vues HTML autonomes**
dans le dossier du mod : le graphe de production cliquable, le rapport de
complexité et la courbe de difficulté comparée au vanilla. La commande
`randputf compare` régénère seule la vue de difficulté (même rendu, nommé
`seed.difficulty.<seed>.html` dans `output/`). Ce document explique leur
construction ; le mode d'emploi est côté utilisateur (README racine,
sections « Le graphe interactif » et « La difficulté »).

Retour : [docs/README.md](README.md).

---

## 1. `seed.graph.html` — le graphe de production

### Ce que c'est

Un nœud par item/fluide, une arête par **dépendance de craft** (produit →
ingrédient) étiquetée par la **quantité** nécessaire au craft (`amount`). La
disposition est en left-to-right sur fond sombre.

Le code HTML est **autonome** : le SVG est intégré, les icônes sont embarquées
en **data-URI** et le JS de navigation est dans le fichier. Il s'ouvre en
local, sans serveur, et se déplace seul. Il est régénéré à chaque export par
la commande `.venv/bin/python -m tool generate --out …` (jamais avec
`--install`).

### Construction, étape par étape

1. **Collecte des nœuds** : chaque item/fluide du graphe devient un nœud ; la
   structure produit → ingrédient des recettes de la seed définit les arêtes.
2. **Icônes** : l'icône de chaque nœud est **celle que le jeu affiche
   réellement**. Résolution, dans l'ordre (`_icon_path`) :
   - fichier exact `<name>.png` ;
   - fluide : `fluid/<name>.png` ;
   - sinon l'icône **déclarée dans les prototypes installés** (ex.
     `raw-fish`→`fish.png`, `stone-wall`→`wall.png` ; lu depuis les `.lua`
     prototypes) ;
   - sinon fût vide pour les `*-barrel`.

   Les variantes de stades (`-1/-2/-3`) et les icônes `technology/` sont
   exclues.
3. **Icônes en data-URI** (`_embed_icons`) : chaque PNG est lu puis encodé en
   base64 dans le SVG → le fichier HTML n'a plus besoin du dossier d'icônes
   vanilla.
4. **Rendu SVG** : `build_seed_graph_dot` retourne une chaîne DOT, rendue par
   `dot -Tsvg` (**Graphviz requis**). Sans Graphviz, l'export HTML est
   simplement **ignoré** (message honnête, pas d'erreur).
5. **Assemblage HTML** : le SVG, les infos de nœuds, les recettes et les
   technos sont injectés dans le gabarit (`_HTML_TEMPLATE`).

### Le côté interactif (le JS embarqué)

Le fichier est **un seul document** ; le JS intégré gère :

- **zoom / pan** à la souris (molette + drag) sur le SVG ;
- **fiche au clic** sur un nœud : nom, icône agrandie, ingrédients et
  utilisateurs, technos associées ; un item multi-recettes y offre un
  sélecteur **autre recette** (la cascade se recalcule) ;
- **sous-graphe** : isolation de la cascade de l'item sélectionné ; les
  ressources brutes y sont des terminaux — on n'explore pas leurs ingrédients,
  même si elles ont un craft ;
- panneau latéral redimensionnable, légende des sciences, numéro de tech
  d'apparition.

Les données injectées (`info`, `recips`, `techs`) sont du JSON sérialisé dans
le HTML, construit depuis la seed. Note : bien que les données de science
soient présentes dans la seed, le script ne les affiche pas dans les fiches.

## 2. `seed.complexity.html` — le rapport de complexité

Le modèle suit **ce que ferait réellement un joueur pour terminer l'arbre** :

- pour chaque technologie, on prend les packs de science exigés par son
  `unit` (`count × amount`) ;
- on déplie récursivement la recette de chaque pack jusqu'aux
  `pools.raw_resources` / au kit de départ, en comptant les crafts ;
- chaque craft utilise l'atelier `crafted_in` de la recette (ou la main) ;
- le temps d'un craft vaut `energy / crafting_speed` du bâtiment.

Mesures produites :

- **courbes par tech** : temps de recherche, ressources brutes consommées,
  nombre d'ateliers de fabrication distincts, ratio ressources / atelier ;
- **résumé** : score de complexité, temps de craft total (comme si un joueur
  faisait tous les crafts), temps de recherche total, fabricateur le plus
  utilisé, ressource la plus consommée pendant la partie.

Le fichier est **autonome** : CSS et SVG sont générés en Python, aucun CDN,
**aucun JavaScript** — il s'ouvre hors ligne. `analyze_playthrough` (la partie
simulée sous-jacente) est partagé avec le rapport vanilla de la commande
`randputf report`.

## 3. `seed.difficulty.html` — la courbe de difficulté

Écrite par `generate --out` **quand le dump porte les technologies**
(`randputf compare` produit le même HTML, nommé `seed.difficulty.<seed>.html`
dans `output/`). C'est une **courbe de difficulté cumulée** : en abscisse la
progression (une tech par point, suivie d'un point « Lancement (fusée) »), en
ordonnée le **total de ressources brutes** déjà investies pour arriver là.

- La difficulté est calculée par `tool/audit/difficulty.py`
  (`compute_difficulty`, puis `difficulty_series` pour la courbe point par
  point) : chaque tech rapporte ses coûts de recherche **réduits à leurs
  ressources brutes** (patch au sol, item environnemental, fluide
  d'extraction) en remontant le graphe primaire des recettes, plus la chaîne
  de la fusée pour le point final.
- Deux courbes sont superposées : la seed **mod** et une baseline **vanilla**
  dérivée du même dump (`build_vanilla_seed`) — les recherches vanilla
  débloquent des recettes réelles, donc la baseline a une difficulté propre.
  L'écart entre les deux courbes est l'effet du mod sur le coût cumulé.
- Le calcul est **conditionné à l'export** : comme `difficulty` dans
  `seed.json`, il ne biaise jamais la construction de la seed (`mod_seed.py`
  l'injecte à l'écriture).

### Lecture interactive

Le SVG est écrit **en Python pur** (aucune dépendance externe, contrairement à
`seed.graph.html` qui exige Graphviz) et embarque une petite couche JS :

- **Survol d'une colonne** (une zone transparente par indice de tech) : un
  repère vertical s'affiche et une **infobulle** donne, pour les deux séries à
  la fois, le numéro et le nom de la tech, son coût propre, le coût cumulé et
  les items débloqués ; l'écart mod − vanilla est ajouté quand les deux courbes
  existent à cet indice.
- **Clic** : épingle l'infobulle (re-clic pour détacher ; un clic dans le vide
  ferme).
- **Légende cliquable** : masque/affiche chaque série (courbe + points) ; la
  valeur masquée disparaît aussi de l'infobulle.
- **Tableaux par tech** (juste en dessous) : le survol d'une ligne met le
  point en évidence, le clic y amène la vue.

Les données injectées (`points`, `labels`, `colors`) sont du JSON sérialisé :
aucune géométrie n'est recalculée côté JS.

## 4. Déterminisme et périmètre du témoin

Le témoin **assemble sa propre copie du mod**, sans les vues HTML (elles ne
sont écrites que par l'export `--out`). De plus, `seed.graph.html` et
`seed.difficulty.html` sont **explicitement exclus** du hash
(`WITNESS_EXCLUDED`, voir [witness.md](witness.md)) :

- `seed.graph.html` : le `<svg>` embarque un commentaire de version de
  Graphviz qui varie d'une machine à l'autre ;
- `seed.difficulty.html` : sortie régénérable (comparaison à vanilla), sans
  garantie au bit près.

`seed.complexity.html` est en SVG Python pur : deux exports d'une même seed
le reproduisent à l'identique. Dans le **zip de release**, `seed.graph.html`
est écarté (vue de debug volumineuse) ; les deux autres vues sont embarquées.

## 5. Pourquoi une doc de conception ici

Le graphe est à la fois une **sortie joueur** (README) et une **pièce du
système** (comment on lit la seed, structure produit → ingrédient, icônes
fidèles au jeu). La revue documentaire pointait cet angle mort ; ce document
le couvre. Il ne remplace pas la lecture utilisateur du README.

Retour : [docs/README.md](README.md).

## Lectures associées

- **Parent** : [architecture.md](architecture.md) — architecture et outillage
- **Concepts liés** : [seed.md](seed.md#seed-et-configuration) ;
  [witness.md](witness.md#ce-qui-est-exclu-du-témoin) ;
  [runtime.md](runtime.md#les-cinq-fichiers-lua)
