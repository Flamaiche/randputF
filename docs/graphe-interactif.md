# Les vues HTML de la génération

Retour : [docs/README.md](README.md).

La génération peut produire jusqu'à trois vues HTML en plus du mod. Elles expliquent le graphe, sa complexité et sa difficulté. Elles ne sont jamais lues par Factorio.

## Ce que ça change pour l'utilisateur

- Les vues générées sont écrites dans `output/reports/randputF_<version>/`.
- `generate --no-html` produit le mod sans ces fichiers.
- Les vues ne font pas partie du témoin de déterminisme.

## Mots à connaître

- [rapport HTML](glossaire.md) — vue interactive générée à côté du mod.
- [graphe](glossaire.md) — réseau de recettes, items et technologies.
- [témoin](glossaire.md) — empreinte de reproductibilité de la seed 5.
- [Graphviz](glossaire.md) — outil externe utilisé pour `seed.graph.html`.

## Fonctionnement

### Les trois fichiers et leur génération

| Fichier | Contenu |
|---|---|
| `seed.graph.html` | graphe cliquable des items, recettes et technologies |
| `seed.complexity.html` | rapport de complexité du graphe généré |
| `seed.difficulty.html` | comparaison vanilla contre mod |

Les fichiers disponibles sont écrits par `generate`, sauf `--no-html`. `seed.graph.html` dépend de Graphviz ; `seed.difficulty.html` et `seed.complexity.html` dessinent leur SVG en Python. La comparaison de difficulté exige des technologies dans le dump. Leur absence n'empêche pas la seed ni le mod d'être produits.

Chaque vue est inspectable sans installer le mod. Elle reprend la seed sérialisée, sans la modifier.

### Navigation du graphe

Le graphe affiche les nœuds de production et les liens de dépendance. La sélection d'un nœud met en avant ses entrées et ses sorties. La lecture suit le sens de fabrication, du départ vers la fusée.

La vue de complexité résume le nombre de recettes, de technologies et de prérequis. La vue de difficulté compare l'ardoise du mod à celle du dump vanilla.

## Complexité et difficulté, une seule section

Complexité et difficulté répondent à deux questions distinctes. La complexité mesure la forme du graphe. La difficulté mesure le coût en ressources brutes pour parcourir ce graphe.

Les deux chiffres viennent de la même seed. Aucun n'est utilisé pour construire la seed. Le total affiché dans le chat du mod est calculé à l'export, jamais pendant le pipeline.

### Profil multi-axes

Le profil regarde cinq axes : structure, volume, temps critique, nouveauté et infrastructure. Le temps critique n'est pas le temps écoulé. Il ne remplace pas le rejeu, qui reste le contrôle de jouabilité décrit dans [testeur.md](testeur.md).

## Périmètre du témoin et des releases

Les trois fichiers HTML sont exclus du témoin de déterminisme. Le témoin courant de la seed 5 est `e61667692c486e5b9c30efa9f4fbc891`, vérifié avec `randputf witness --seed 5 --expect e61667692c486e5b9c30efa9f4fbc891`.

Le workflow de release construit le mod dans `/tmp/modrel/randputF_${VERSION}` et zippe exactement ce dossier vers `/tmp/randputF_${VERSION}.zip`, sans les trois vues HTML. Le détail est dans [release.md](release.md).

D'anciens textes affirmaient qu'aucun zip n'était attaché à la release, ou décrivaient une source de zip différente du dossier généré. Ces deux formulations sont obsolètes.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Les vues sont générées à côté du mod, jamais dans le mod. | Graphviz peut manquer pour `seed.graph.html`. |
| Les fichiers HTML n'entrent pas dans le témoin. | Le zip de release dépend du chemin exact du script. |
| `--no-html` supprime uniquement les trois vues. | Les vues ne prouvent pas la jouabilité. |

## Aller plus loin

- [architecture.md](architecture.md) — à lire quand la place des rapports est cherchée.
- [modules.md](modules.md) — à lire quand l'exporteur HTML est recherché.
- [model.md](model.md) — à lire quand le vocabulaire du graphe est nécessaire.
- [testeur.md](testeur.md) — à lire quand la jouabilité doit être contrôlée.
- [release.md](release.md) — à lire quand le contenu du zip est vérifié.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [witness.md](witness.md) — déterminisme et exclusions.
- [config.md](config.md) — chemins de sortie.
- [DEVIANCES.md](DEVIANCES.md) — écarts encore ouverts.
