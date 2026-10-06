# Le graphe interactif (`seed.graph.html`)

À côté de `seed/seed.json`, l'export `--out` génère **un** fichier
supplémentaire : `seed.graph.html`, qui correspond à un **graphe de production
cliquable et autonome** propre à la seed. Ce document détaille sa conception ;
l'usage est décrit côté utilisateur dans le README racine, sous la section
« Le graphe interactif ».

Retour : [docs/README.md](README.md).

---

## 1. Ce que c'est

Le graphe comprend un nœud par item ou fluide, ainsi qu'une arête par
**dépendance de craft** (produit vers ingrédient). Chaque arête est étiquetée par
la **quantité** nécessaire au craft (`amount`). Visuellement, le graphe s'affiche
en disposition left-to-right sur fond sombre.

Le code HTML est **autonome** : le SVG y est intégré, les icônes sont embarquées
en **data-URI**, et le script de navigation réside directement dans le fichier.
Ce dernier s'ouvre localement sans requérir de serveur et fonctionne de manière
autonome. Il fait l'objet d'une régénération à chaque export.

Il est produit par l'export `--out` (`.venv/bin/python -m tool generate --out …`),
mais **jamais** inclus dans le mod installé (`mod/`). De plus, il est **exclu du
témoin** de déterminisme, tel que précisé dans [witness.md](witness.md) puisque
le `<svg>` intègre une version de Graphviz.

## 2. Construction, étape par étape

1. **Collecte des nœuds** : chaque item ou fluide de la seed forme un nœud. La
   structure produit → ingrédient des recettes de la seed détermine les arêtes.
2. **Icônes** : chaque nœud récupère **l'icône réellement affichée par le jeu**. La
   résolution suit cet ordre précis (`_icon_path`) :
   - fichier exact `<name>.png` ;
   - fluide : `fluid/<name>.png` ;
   - sinon l'icône **déclarée dans les prototypes installés** (par exemple
     `raw-fish`→`fish.png`, `stone-wall`→`wall.png`, issus de la lecture des
     prototypes `.lua`) ;
   - sinon un fût vide pour les `*-barrel`.
   Les variantes de stades (`-1/-2/-3`) ainsi que les icônes de type
   `technology/` sont écartées.
3. **Icônes en data-URI** (`_embed_icons`) : chaque PNG est lu puis converti en
   base64 à l'intérieur du SVG. Par conséquent, le fichier HTML se passe du
   dossier d'icônes vanilla.
4. **Rendu SVG** : la fonction `build_seed_graph_dot` génère un fichier `.dot`,
   ensuite converti par `dot -Tsvg` (**Graphviz requis**). En l'absence de
   Graphviz, l'export HTML est simplement **ignoré** en affichant un message
   clair, sans lever d'erreur.
5. **Assemblage HTML** : le contenu SVG, les métadonnées des nœuds, les recettes
   et les technologies sont injectés dans un gabarit de référence
   (`_HTML_TEMPLATE`).

## 3. Le côté interactif (le JS embarqué)

Le fichier forme **un document unique**. Le code JavaScript intégré prend en
charge :

- les actions de **zoom et pan** à la souris (via molette et glisser-déposer) sur
  le SVG ;
- l'affichage d'une **fiche au clic** sur un nœud, détaillant son nom, son icône
  agrandie, ses ingrédients, ses utilisateurs et les technologies reliées (récupérées
  depuis les prototypes, ce qui explique la présence des `packs` de science dans
  les fiches).

Les données injectées (`info`, `recips`, `techs`) consistent en du JSON sérialisé
au cœur du HTML et bâti à partir de la seed.

## 4. Déterminisme de la sortie

Le fichier `seed.graph.html` **n'entre pas dans le périmètre du témoin**
octet-pour-octet, car le code `<svg>` embarque un commentaire de version lié à
Graphviz qui fluctue selon les machines. Il demeure néanmoins **régénérable** :
lancer deux exports d'une même seed fournit un graphe *logique* identique (mêmes
nœuds et mêmes arêtes), même si le code SVG diffère au bit près. Cette limite
est documentée explicitement pour le témoin.

## 5. Pourquoi une doc de conception ici

Le graphe joue un double rôle : c'est à la fois une **sortie joueur** (décrite
dans le README) et une **pièce du système** (qui détaille la lecture de la seed,
la structure produit → ingrédient et le respect des icônes du jeu). La revue
documentaire a mis en lumière cet angle mort, que le présent document vient
combler. Il ne se substitue pas à la lecture du README par l'utilisateur.

Retour : [docs/README.md](README.md).
