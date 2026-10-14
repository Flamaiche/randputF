# Les graphes HTML (`seed.graph.html`, `seed.difficulty.html`)

À côté de `seed/seed.json`, l'export `--out` produit des sorties
supplémentaires : `seed.graph.html`, un **graphe de production cliquable et
autonome** de la seed, et — quand le dump porte les technologies —
`seed.difficulty.html`, la **comparaison de difficulté vanilla vs mod**. Ce
document explique comment ils sont construits ; le mode d'emploi est côté
utilisateur (README racine, section « Le graphe interactif »).

Retour : [docs/README.md](README.md).

---

## Ce que c'est

Un nœud par item/fluide, une arête par **dépendance de craft** (produit →
ingrédient) étiquetée par la **quantité** nécessaire au craft (`amount`). Le
graphe est laid en left-to-right sur fond sombre.

Le HTML est **autonome** : le SVG est intégré, les icônes sont embarquées en
**data-URI**, le JS de navigation est dans le fichier. Il s'ouvre en local,
sans serveur, et se déplace seul. Il est régénéré à chaque export.

Il accompagne l'export `--out` (`.venv/bin/python -m tool generate --out …`),
**jamais** dans le mod installé (`mod/`), et il est **exclu du témoin** de
déterminisme (voir [witness.md](witness.md) : le `<svg>` embarque une version
de Graphviz).

## Construction, étape par étape

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
4. **Rendu SVG** : `build_seed_graph_dot` produit un fichier `.dot`, rendu par
   `dot -Tsvg` (**Graphviz requis**). Sans Graphviz, l'export HTML est
   simplement **ignoré** (message honnête, pas d'erreur).
5. **Assemblage HTML** : le SVG, les infos de nœuds, les recettes et les
   technos sont injectés dans un gabarit (`_HTML_TEMPLATE`).

## Le côté interactif (le JS embarqué)

Le fichier est **un seul document** : le JS intégré gère :

- **zoom / pan** à la souris (molette + drag) sur le SVG ;
- **fiche au clic** sur un nœud : nom, icône agrandie, ingrédients et
  utilisateurs, avec les technos associées (extraites des prototypes, d'où la
  présence des `packs` de science dans les fiches).

Les données injectées (`info`, `recips`, `techs`) sont du JSON sérialisé dans
le HTML, construit depuis la seed.

## Le graphe de difficulté (`seed.difficulty.html`)

À côté du graphe de production, `randputf generate` écrit
`seed.difficulty.html` dans le dossier du mod **quand le dump porte les
technologies** (`randputf compare` produit le même HTML, nommé
`seed.difficulty.<seed>.html` dans `output/`). C'est une **courbe de difficulté
cumulée** : en abscisse la progression (une tech par point, suivie d'un point
« Lancement (fusée) »), en ordonnée le **total de ressources brutes** déjà
investies pour arriver là.

- La difficulté est calculée par `tool/audit/difficulty.py`
  (`compute_difficulty`, puis `difficulty_series` pour la courbe point par
  point) : chaque tech rapporte ses coûts de recherche **réduits à leurs
  ressources brutes** (patch au sol, item environnemental, fluide
  d'extraction) en remontant le graphe primaire des recettes.
- Deux courbes sont superposées : la seed **mod** et une baseline **vanilla**
  dérivée du même dump (`vanilla_seed_from_dump`) — les recherches vanilla
  débloquent des recettes réelles, donc la baseline a une difficulté propre.
  L'écart entre les deux courbes est l'effet du mod sur le coût cumulé.
- Le calcul est **conditionné à l'export** : comme `difficulty` dans
  `seed.json`, il ne biaise jamais la construction de la seed
  (`mod_seed.py` l'injecte à l'écriture).
- Le fichier est **autonome** (SVG + données sérialisées dans le HTML) et
  n'est **pas** couvert par le témoin de déterminisme, pour la même raison que
  `seed.graph.html`.

## Déterminisme de la sortie

Le `seed.graph.html` **n'est pas couvert par le témoin** d'octet-pour-octet
(le `<svg>` porte un commentaire de version de Graphviz qui varie d'une
machine à l'autre). Il reste **régénérable** : deux exports de la même seed
produisent le même graphe *logique* (mêmes nœuds, mêmes arêtes), même si le
SVG n'est pas bit-à-bit identique. C'est explicitement la limite documentée du
témoin.

## Pourquoi une doc de conception ici

Le graphe est à la fois une **sortie joueur** (README) et une **pièce du
système** (comment on lit la seed, structure produit → ingrédient, icônes
fidèles au jeu). La revue documentaire pointait cet angle mort ; ce document
le couvre. Il ne remplace pas la lecture utilisateur du README.

Retour : [docs/README.md](README.md).

## Lectures associées

- **Parent** : [architecture.md](architecture.md) — architecture et outillage
- **Concepts liés** : [seed.md](seed.md#seed-et-configuration) ; [witness.md](witness.md#ce-qui-est-exclu-du-témoin) ; [runtime.md](runtime.md#les-cinq-fichiers-lua)
