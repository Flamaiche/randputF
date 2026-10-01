# Le graphe interactif (`seed.graph.html`)

À côté de `seed/seed.json`, l'export `--out` produit **une** sortie
supplémentaire : `seed.graph.html`, un **graphe de production cliquable et
autonome** de la seed. Ce document explique comment il est construit ; le
mode d'emploi est côté utilisateur (README racine, section « Le graphe
interactif »).

Retour : [docs/README.md](README.md).

---

## 1. Ce que c'est

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

## 2. Construction, étape par étape

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

## 3. Le côté interactif (le JS embarqué)

Le fichier est **un seul document** : le JS intégré gère :

- **zoom / pan** à la souris (molette + drag) sur le SVG ;
- **fiche au clic** sur un nœud : nom, icône agrandie, ingrédients et
  utilisateurs, avec les technos associées (extraites des prototypes, d'où la
  présence des `packs` de science dans les fiches).

Les données injectées (`info`, `recips`, `techs`) sont du JSON sérialisé dans
le HTML, construit depuis la seed.

## 4. Déterminisme de la sortie

Le `seed.graph.html` **n'est pas couvert par le témoin** d'octet-pour-octet
(le `<svg>` porte un commentaire de version de Graphviz qui varie d'une
machine à l'autre). Il reste **régénérable** : deux exports de la même seed
produisent le même graphe *logique* (mêmes nœuds, mêmes arêtes), même si le
SVG n'est pas bit-à-bit identique. C'est explicitement la limite documentée du
témoin.

## 5. Pourquoi une doc de conception ici

Le graphe est à la fois une **sortie joueur** (README) et une **pièce du
système** (comment on lit la seed, structure produit → ingrédient, icônes
fidèles au jeu). La revue documentaire pointait cet angle mort ; ce document
le couvre. Il ne remplace pas la lecture utilisateur du README.

Retour : [docs/README.md](README.md).