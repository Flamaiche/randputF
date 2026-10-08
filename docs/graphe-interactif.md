# Le graphe interactif (`seed.graph.html`)

À la racine du mod (`<out>/randputF_1.0.1/seed.graph.html`), soit un niveau au-dessus de `seed/seed.json`, l'export `--out` génère un fichier supplémentaire : un graphe de production cliquable et autonome. Ce document détaille sa conception ; l'usage est décrit pour l'utilisateur dans le README racine, section « Le graphe interactif ».

Retour : [docs/README.md](README.md).

---

## 1. Ce que c'est

Le graphe affiche un nœud par item ou fluide et une arête par dépendance de craft (produit vers ingrédient). Chaque arête porte la quantité nécessaire (`amount`). La disposition est de type left-to-right sur fond sombre.

Le code HTML est autonome : le SVG est intégré, les icônes sont embarquées en data-URI et le script de navigation est inclus. Il s'ouvre localement sans serveur. Le fichier est régénéré à chaque export par la commande `.venv/bin/python -m tool generate --out …`. Il n'est jamais inclus dans le dossier `mod/` et reste exclu du témoin de déterminisme décrit dans [witness.md](witness.md) car le `<svg>` dépend de la version de Graphviz.

## 2. Construction, étape par étape

1. **Collecte des nœuds** : chaque item ou fluide de la seed devient un nœud. Les arêtes suivent la structure produit → ingrédient des recettes.
2. **Icônes** : `_icon_path` cherche l'image réelle du jeu selon cet ordre :
   - fichier `<name>.png` ;
   - fluide : `fluid/<name>.png` ;
   - icône déclarée dans les prototypes (ex : `raw-fish`→`fish.png`, `stone-wall`→`wall.png`) ;
   - fût vide pour les `*-barrel`.
   Les icônes de type `technology/` sont écartées.
3. **Icônes en data-URI** : `_embed_icons` convertit chaque PNG en base64. Le HTML se passe ainsi des fichiers originaux.
4. **Rendu SVG** : la fonction `build_seed_graph_dot` retourne une chaîne DOT. Elle est convertie par `dot -Tsvg` (**Graphviz requis**). Sans Graphviz, l'export est ignoré avec un message d'information.
5. **Assemblage HTML** : le SVG, les métadonnées, les recettes et les technologies sont injectés dans le gabarit `_HTML_TEMPLATE`.

## 3. Le côté interactif (le JS embarqué)

Le fichier est un document unique. Le JavaScript gère :

- le zoom et le pan (molette et glisser-déposer) sur le SVG ;
- l'affichage d'une fiche au clic : nom, icône, ingrédients, utilisateurs et technologies liées.

Ces informations (`info`, `recips`, `techs`) sont extraites de la seed et injectées en JSON. Note : bien que les données de science soient présentes dans la seed, le script ne les affiche pas dans les fiches.

## 4. Déterminisme de la sortie

Le fichier `seed.graph.html` n'entre pas dans le périmètre du témoin octet-pour-octet. Le code `<svg>` contient des commentaires liés à la version de Graphviz qui varient selon l'environnement. Le graphe reste cependant régénérable : deux exports d'une même seed produisent un résultat logique identique (nœuds et arêtes), même si le bit-à-bit diffère.

## 5. Pourquoi une doc de conception ici

Le graphe est à la fois une sortie joueur et une pièce du système. Il illustre la lecture de la seed, la hiérarchie des recettes et la gestion des icônes. Cette documentation comble un angle mort identifié lors de la revue documentaire, sans remplacer le mode d'emploi du README.

Retour : [docs/README.md](README.md).
