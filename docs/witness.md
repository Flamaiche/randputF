# Témoin de déterminisme

Retour : [docs/README.md](README.md).

Le témoin est le md5 du mod assemblé, calculé de façon reproductible. Il mesure
l'assemblage, pas la jouabilité de la seed. Cette page sépare la garantie,
l'implémentation, les faits anciens et les corrections attendues.

## État de la page

- Garantie actuelle : un même contenu de mod donne le même md5 canonique.
- Implémentation actuelle : le zip de référence est trié, stocké sans
  compression et fixé dans le temps.
- Fait historique : le hash `c9566134864507d900f65806ade277d9` et les 722 tests
  appartiennent au jalon `v0.0.1`.
- Spécification historique : elle demande de ne pas nier l'existence du
  zip de release ; le dépôt n'a pas de mod pré-généré.

## Ce que ça change pour le joueur

- La même graine redonne le même mod, octet pour octet.
- Une divergence bloque le contrôle en CI et signale une dérive.
- Les vues HTML ne font pas partie du témoin.

## Mots à connaître

- [Témoin](glossaire.md) — empreinte du mod assemblé.
- [Canonisation](glossaire.md) — normalisation avant calcul de l'empreinte.
- [Seed](glossaire.md) — graine qui fixe les tirages.
- [Mod](glossaire.md) — ensemble de fichiers installé dans Factorio.
- [Rapport HTML](glossaire.md) — vue régénérable du graphe ou du profil.

## Règles de vérification

- `randputf witness --seed <n>` assemble le mod puis calcule son md5 canonique.
- `--expect` compare le résultat à la valeur attendue et échoue en cas d'écart.
- Le témoin courant de la seed 5 est `74dcb6f89c28ef1277a0e854d9a21a4a`.
- Le préfixe du zip de référence est `randputF_<version>`, lu dans `info.json`.
- Le job CI recalcule le témoin depuis `/tmp`, hors du checkout.
- Le workflow de release lance le témoin sans `--expect` ; seule la réussite de
  la génération y est contrôlée.
- Le workflow de release vise `randputF_<version>.zip` sans les trois vues HTML ;
  sa source doit encore être alignée.
- Le workflow de CI ne publie pas de zip : il vérifie les tests, les ancres et
  le témoin.

## Ce qui est exclu

- `seed.graph.html` dépend de Graphviz présent sur la machine.
- `seed.difficulty.html` compare la seed au vanilla et se régénère.
- `seed.complexity.html` est une vue de complexité régénérable.
- Les trois fichiers sont écrits dans `output/reports/randputF_<version>/`.
- `seed.json`, `seed.lua` et les fichiers Lua restent couverts par le témoin.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Le md5 est stable pour un même contenu. | La jouabilité de la seed. |
| Une dérive d'assemblage est détectée en CI. | La stabilité des vues HTML. |
| Un zip de release est prévu sans les vues HTML une fois la source alignée. | Un mod pré-généré dans le dépôt. |

## Aller plus loin

- [nondeterminism.md](nondeterminism.md) — à lire pour le déterminisme de la seed.
- [release.md](release.md) — à lire pour la publication et le zip.
- [pipeline.md](pipeline.md) — à lire pour l'assemblage avant hachage.
- [graphe-interactif.md](graphe-interactif.md) — à lire pour les vues exclues.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [seed.md](seed.md#seed-et-configuration-1) — à lire pour la graine active.
- [historique-nondeterminisme.md](historique-nondeterminisme.md) — à lire pour les hash anciens.
